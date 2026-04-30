# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""Run every pytest item in an isolated child pytest process.

A native crash (SIGSEGV / SIGABRT) in the child terminates only that test instead
of the whole pytest session, so subsequent tests still run.

Same one-subprocess-per-test pattern legacy run-unit-tests.py and the ROS CI
script (realsense-ros/realsense2_camera/test/live_camera/rosci.py) already use:
launch sys.executable, pipe stdout/stderr straight into the per-test log file,
honour the test's timeout. The only addition here is pytest-reportlog, which
writes structured TestReport entries the parent forwards to listeners.

Conftest registers this module as a plugin under the name "rs_subprocess_isolation".
The parent invokes the child with `-p no:rs_subprocess_isolation`, which blocks
the plugin in the child so the test runs normally there. No env var or
user-visible CLI flag is involved.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile

import pytest
from _pytest.reports import TestReport

from rspy import repo
from rspy.pytest import logging_setup

log = logging.getLogger(__name__)

PLUGIN_NAME = "rs_subprocess_isolation"

# Returncode values that mean the child died from a fatal signal. Python's
# subprocess returns -signo on POSIX; many shells / waitpid wrappers report
# 128+signo. Windows access violations surface as 0xC0000005 / -1073741819.
_CRASH_SIGNALS = {
    -11:          "SIGSEGV",
    139:          "SIGSEGV",
    -6:           "SIGABRT",
    134:          "SIGABRT",
    -1073741819:  "access violation",
    3221225477:   "access violation",
}


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    """Run *item* in a fresh pytest child process.

    Returning True short-circuits the default protocol; setup/call/teardown
    reports come back from the child via pytest-reportlog and are forwarded
    to listeners here so the terminal reporter, JUnit XML, log handlers, etc.
    see them. The conftest hookwrapper at pytest_runtest_protocol still wraps
    this call, so per-test log files are opened/closed normally.
    """
    reports = _run_test_in_subprocess(item)
    for report in reports:
        item.ihook.pytest_runtest_logreport(report=report)
    return True


def _forwarded_args(config):
    """Mirror parent-side librealsense flags onto the child pytest invocation.

    --no-reset is always forwarded: the parent has already enabled the device
    via the hub, and the child must not recycle it. --hub-reset is never
    forwarded for the same reason.
    """
    args = []
    for value in config.getoption("--device", default=[]) or []:
        args.extend(["--device", value])
    for value in config.getoption("--exclude-device", default=[]) or []:
        args.extend(["--exclude-device", value])
    context = config.getoption("--context", default="")
    if context:
        args.extend(["--context", context])
    if config.getoption("--rslog", default=False):
        args.append("--rslog")
    # --debug is consumed before pytest parses sys.argv (rspy.pytest.cli), so
    # config doesn't track it. Re-detect from the original invocation argv.
    invocation_args = getattr(getattr(config, "invocation_params", None), "args", ())
    if "--debug" in invocation_args or "--debug" in sys.argv:
        args.append("--debug")
    args.append("--no-reset")
    return args


def _child_env():
    env = os.environ.copy()
    pyrs_dir = repo.find_pyrs_dir()
    if pyrs_dir:
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = pyrs_dir + os.pathsep + existing if existing else pyrs_dir
    return env


def _marker_timeout(item):
    marker = item.get_closest_marker("timeout")
    if marker is None:
        return None
    if marker.args:
        return marker.args[0]
    return marker.kwargs.get("timeout")


def _location(item):
    loc = getattr(item, "location", None)
    if loc and len(loc) == 3:
        return loc
    return (str(getattr(item, "fspath", "")), 0, item.nodeid)


def _fabricate_crash_report(item, returncode, log_path):
    label = _CRASH_SIGNALS.get(returncode, f"exit code {returncode}")
    if log_path:
        longrepr = f"child pytest crashed ({label}); see {log_path} for full output"
    else:
        longrepr = f"child pytest crashed ({label})"
    return TestReport(
        nodeid=item.nodeid,
        location=_location(item),
        keywords={},
        outcome="failed",
        longrepr=longrepr,
        when="call",
        sections=[],
        duration=0.0,
        user_properties=[],
    )


def _parse_reportlog(path, item_nodeid):
    """Yield TestReport objects pertaining to *item_nodeid* from a pytest-reportlog file."""
    if not os.path.isfile(path):
        return []
    reports = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("$report_type") != "TestReport":
                continue
            if data.get("nodeid") != item_nodeid:
                continue
            try:
                reports.append(TestReport._from_json(data))
            except Exception as e:
                log.warning("Failed to deserialize TestReport for %s: %s", item_nodeid, e)
    return reports


def _emit_to_test_log(text):
    """Append the child's captured stdout to the parent's per-test log file.

    Returns the log file path (for the fabricated-crash longrepr), or None when
    logging is off (-s). The FileHandler's TextIOWrapper buffers writes and
    re-translates "\\n", which corrupts child output that already contains
    "\\r\\n" on Windows. Open a fresh binary append fd to dodge both issues,
    flush the FileHandler before so its own buffered separators are on disk,
    then seek it to end so subsequent parent log writes stay sequential.
    """
    handler = logging_setup._current_file_handler
    if handler is None:
        return None
    log_path = getattr(handler, "baseFilename", None)
    if not text or not log_path:
        return log_path
    try:
        handler.stream.flush()
        data = text.encode("utf-8", errors="replace")
        with open(log_path, "ab") as f:
            f.write(data)
            if not data.endswith(b"\n"):
                f.write(b"\n")
        handler.stream.seek(0, os.SEEK_END)
    except Exception as e:
        log.debug("Could not append child stdout to per-test log: %s", e)
    return log_path


def _run_test_in_subprocess(item):
    """Run *item* in a fresh pytest child process and return its TestReport list.

    Child stdout/stderr is captured to a temp file (not piped via PIPE — pytest's
    own crash backtrace can be large, and PIPE blocks if the child fills the OS
    buffer) then forwarded into the parent's per-test log file. Reports cover
    setup/call/teardown via pytest-reportlog. If the child crashes natively
    (SIGSEGV/SIGABRT) the reportlog may be empty or partial — fabricate a single
    failed TestReport in that case so the failure surfaces in the terminal
    summary and JUnit XML.
    """
    timeout = _marker_timeout(item)
    child_timeout = (timeout + 30) if timeout else None

    fd, report_log_path = tempfile.mkstemp(prefix="rs-subproc-", suffix=".jsonl")
    os.close(fd)
    child_output = tempfile.TemporaryFile(mode="w+b")

    try:
        cmd = [
            sys.executable, "-u",
            "-m", "pytest", item.nodeid,
            f"--report-log={report_log_path}",
            "-p", f"no:{PLUGIN_NAME}",
            "-p", "no:cacheprovider",
            "--no-header",
            "--tb=short",
        ]
        cmd.extend(_forwarded_args(item.config))

        log.debug("subprocess isolation: %s", " ".join(cmd))
        try:
            p = subprocess.run(
                cmd,
                stdout=child_output,
                stderr=subprocess.STDOUT,
                env=_child_env(),
                timeout=child_timeout,
                check=False,
            )
            returncode = p.returncode
        except subprocess.TimeoutExpired:
            returncode = -1
            try:
                child_output.write(
                    f"\nchild pytest exceeded timeout {child_timeout}s and was killed\n".encode()
                )
            except Exception:
                pass

        child_output.seek(0)
        stdout = child_output.read().decode("utf-8", errors="replace")
        log_path = _emit_to_test_log(stdout)

        reports = _parse_reportlog(report_log_path, item.nodeid)
        if reports:
            if returncode != 0 and not any(r.failed for r in reports):
                # Child exited non-zero but reportlog says everything passed —
                # likely a late crash after the call report was flushed.
                reports.append(_fabricate_crash_report(item, returncode, log_path))
            return reports

        return [_fabricate_crash_report(item, returncode, log_path)]
    finally:
        try:
            child_output.close()
        except Exception:
            pass
        try:
            os.unlink(report_log_path)
        except OSError:
            pass
