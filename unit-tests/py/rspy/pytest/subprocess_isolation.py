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
import shutil
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

# Sentinel returncode meaning subprocess.TimeoutExpired (child was killed by us).
_TIMED_OUT = "__rs_timed_out__"


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

    Device selection and context options are forwarded so the child sees the
    same target device set as the parent invocation. --no-reset is always
    forwarded because device setup happens in the child's own fixtures and the
    child should not perform an extra hub recycle. --hub-reset is intentionally
    not forwarded.
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


def _summary_for(returncode):
    if returncode == _TIMED_OUT:
        return "child pytest timed out and was killed"
    if returncode in _CRASH_SIGNALS:
        return f"child pytest crashed ({_CRASH_SIGNALS[returncode]})"
    return f"child pytest exited with code {returncode}"


def _fabricate_failed_report(item, returncode, log_path):
    summary = _summary_for(returncode)
    longrepr = f"{summary}; see {log_path} for full output" if log_path else summary
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
                report = TestReport._from_json(data)
            except Exception as e:
                log.warning("Failed to deserialize TestReport for %s: %s", item_nodeid, e)
                continue
            # Skip-report longrepr is a (filename, lineno, reason) tuple in pytest;
            # JSON round-trip turns it into a list and the terminal reporter then
            # asserts isinstance(longrepr, tuple). Restore the tuple type.
            if report.outcome == "skipped" and isinstance(report.longrepr, list):
                report.longrepr = tuple(report.longrepr)
            reports.append(report)
    return reports


def _forward_child_output(child_output, log_path):
    """Stream the child's captured output into the parent's per-test log file.

    Streams in chunks rather than reading the full child output into memory —
    pytest crash backtraces can be sizable.

    When no per-test FileHandler is active (e.g. -s / capture=no), or when live
    logging is on, also write to sys.stdout so interactive runs still show
    subprocess output. Returns the path of the file the child output landed
    in (per-test log) so the fabricated-crash longrepr can point at it.
    """
    child_output.seek(0)
    handler = logging_setup._current_file_handler
    forward_to_terminal = handler is None or getattr(logging_setup, "live_logging", False)

    if log_path:
        try:
            handler.stream.flush()
            with open(log_path, "ab") as f:
                shutil.copyfileobj(child_output, f)
            handler.stream.seek(0, os.SEEK_END)
        except Exception as e:
            log.debug("Could not append child stdout to per-test log: %s", e)
            forward_to_terminal = True  # at least show it somewhere

    if forward_to_terminal:
        try:
            child_output.seek(0)
            data = child_output.read()
            sys.stdout.buffer.write(data)
            sys.stdout.flush()
        except Exception as e:
            log.debug("Could not forward child stdout to terminal: %s", e)

    return log_path


def _run_test_in_subprocess(item):
    """Run *item* in a fresh pytest child process and return its TestReport list."""
    timeout = _marker_timeout(item)
    child_timeout = (timeout + 30) if timeout else None

    fd, report_log_path = tempfile.mkstemp(prefix="rs-subproc-", suffix=".jsonl")
    os.close(fd)
    child_output = tempfile.TemporaryFile(mode="w+b")
    handler = logging_setup._current_file_handler
    log_path = getattr(handler, "baseFilename", None) if handler else None

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
            returncode = _TIMED_OUT
            try:
                child_output.write(
                    f"\nchild pytest exceeded timeout {child_timeout}s and was killed\n".encode()
                )
            except Exception:
                pass

        _forward_child_output(child_output, log_path)

        reports = _parse_reportlog(report_log_path, item.nodeid)
        if reports:
            if returncode != 0 and returncode != _TIMED_OUT and not any(r.failed for r in reports):
                # Child exited non-zero but reportlog says everything passed —
                # likely a late crash after the call report was flushed.
                reports.append(_fabricate_failed_report(item, returncode, log_path))
            return reports

        return [_fabricate_failed_report(item, returncode, log_path)]
    finally:
        try:
            child_output.close()
        except Exception:
            pass
        try:
            os.unlink(report_log_path)
        except OSError:
            pass
