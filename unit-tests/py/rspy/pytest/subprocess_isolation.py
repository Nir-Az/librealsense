# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""Run each (file, device) group of pytest items in an isolated child pytest process.

A native crash (SIGSEGV / SIGABRT) in the child terminates only that group instead
of the whole pytest session, so subsequent groups still run. Group key matches the
per-test log file's (fspath, device-id-from-brackets) so the granularity lines up
with the existing log file naming: parametrized device-each tests still get one
subprocess per device; non-parametrized tests in the same file share one subprocess.

Same one-subprocess pattern legacy run-unit-tests.py and the ROS CI script
(realsense-ros/realsense2_camera/test/live_camera/rosci.py) already use: launch
sys.executable, pipe stdout/stderr straight into the per-test log file, honour the
test's timeout. The only addition here is pytest-reportlog, which writes structured
TestReport entries the parent forwards to listeners.

Conftest registers this module as a plugin under the name "rs_subprocess_isolation".
The parent invokes the child with `-p no:rs_subprocess_isolation`, which blocks the
plugin in the child so the tests run normally there. No env var or user-visible CLI
flag is involved.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest
from _pytest.reports import TestReport

from rspy import devices, repo
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

# Default per-test timeout when no @pytest.mark.timeout marker is present
# (matches conftest.py's default).
_DEFAULT_TEST_TIMEOUT = 200

# nodeid -> list[TestReport] for items already covered by an earlier group's
# subprocess. The protocol hook drains this for every item it's called for.
_pending_reports = {}

# Set of device serials enabled for the previous group; lets us recycle the
# hub only when the target device set actually changes between groups (matches
# the legacy module_device_setup per-module recycling cadence).
_last_target_serials = None


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    """Run the (fspath, device-id) group containing *item* in a child pytest.

    Returning True short-circuits the default protocol; setup/call/teardown
    reports come back from the child via pytest-reportlog and are forwarded to
    listeners here so the terminal reporter, JUnit XML, log handlers, etc. see
    them. The conftest hookwrapper at pytest_runtest_protocol still fires
    per item, so per-test log files are opened/closed normally.
    """
    if item.nodeid in _pending_reports:
        # Already ran as part of a previous group's subprocess.
        for report in _pending_reports.pop(item.nodeid):
            item.ihook.pytest_runtest_logreport(report=report)
        return True

    group = _find_group(item)
    by_nodeid = _run_group_in_subprocess(item.config, group)
    _pending_reports.update(by_nodeid)

    for report in _pending_reports.pop(item.nodeid, []):
        item.ihook.pytest_runtest_logreport(report=report)
    return True


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

def _group_key(item):
    """(fspath, device-id-from-brackets) — same key the per-test log handler uses,
    so per-file/per-device subprocess granularity aligns with the .log file naming.
    """
    device_id = None
    m = re.search(r"\[(.+)\]", item.name)
    if m:
        device_id = m.group(1)
    return (str(item.fspath), device_id)


def _find_group(item):
    """Consecutive items in session.items sharing the group key with *item*.

    pytest_collection_modifyitems already sorts by (module, device_serial) — see
    rspy.pytest.collection.filter_and_sort_items — so a group is always contiguous.
    """
    items = item.session.items
    try:
        start = items.index(item)
    except ValueError:
        return [item]
    key = _group_key(item)
    group = []
    for i in range(start, len(items)):
        if _group_key(items[i]) == key:
            group.append(items[i])
        else:
            break
    return group


# ---------------------------------------------------------------------------
# Child invocation
# ---------------------------------------------------------------------------

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


def _fabricate_failed(item, longrepr):
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


def _parse_reportlog(path):
    """All TestReport objects from a pytest-reportlog file."""
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
            try:
                report = TestReport._from_json(data)
            except Exception as e:
                log.warning("Failed to deserialize TestReport: %s", e)
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

    Streams in chunks rather than reading everything into memory — a big test
    group's output plus a crash backtrace can be sizable.

    When no per-test FileHandler is active (e.g. -s / capture=no), or when live
    logging is on, also write to sys.stdout so interactive runs still show
    subprocess output.
    """
    child_output.seek(0)
    handler = logging_setup._current_file_handler
    forward_to_terminal = handler is None or getattr(logging_setup, "live_logging", False)

    if log_path and handler is not None:
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
            sys.stdout.buffer.write(child_output.read())
            sys.stdout.flush()
        except Exception as e:
            log.debug("Could not forward child stdout to terminal: %s", e)


def _resolve_group_serials(items, config):
    """Determine which device serial(s) the items in this group will need.

    Mirrors module_device_setup's resolution: parametrized via @device_each →
    take the bracketed serial; otherwise resolve @device markers (single or
    multi-device) against the parent's currently-known devices.
    """
    from rspy.pytest.device_helpers import find_matching_devices, find_matching_devices_multi

    serials = set()
    cli_includes = config.getoption("--device", default=[])
    cli_excludes = config.getoption("--exclude-device", default=[])

    for item in items:
        callspec = getattr(item, "callspec", None)
        if callspec and "_test_device_serial" in getattr(callspec, "params", {}):
            serials.add(callspec.params["_test_device_serial"])
            continue

        device_markers = [
            m for m in item.iter_markers()
            if m.name in ("device", "device_each", "device_exclude")
        ]
        if not device_markers:
            continue

        multi = next(
            (m for m in device_markers if m.name == "device" and len(m.args) > 1),
            None,
        )
        if multi:
            sns, _ = find_matching_devices_multi(
                device_markers, cli_includes=cli_includes, cli_excludes=cli_excludes
            )
            serials.update(sns)
            continue

        sns, _ = find_matching_devices(
            device_markers, each=False,
            cli_includes=cli_includes, cli_excludes=cli_excludes,
        )
        serials.update(sns)

    return serials


def _enable_target_devices_for_group(items, config):
    """Restrict the hub to the group's target device(s) before launching the child.

    Matches the legacy run-unit-tests.py pattern: parent owns the hub and
    enables only the device(s) the next test needs, then the child trusts the
    state with --no-reset. Recycle only when the target set changes between
    groups (same cadence as module_device_setup's per-module recycling).
    Group-key granularity ((fspath, device-id)) means items in one group
    always want the same device.
    """
    global _last_target_serials

    if devices.hub is None:
        return  # No hub on this machine — devices are statically connected.
    if config.getoption("--no-reset", default=False):
        return  # Caller asked us not to touch hub state.

    target = _resolve_group_serials(items, config)
    if not target:
        return  # No device markers / parametrization → leave hub state as-is.

    recycle = (_last_target_serials != target)
    try:
        devices.enable_only(list(target), recycle=recycle)
    except Exception as e:
        log.warning(
            "Could not enable target devices %s for group %s: %s",
            sorted(target), items[0].nodeid, e,
        )
    _last_target_serials = target


def _run_group_in_subprocess(config, items):
    """Run *items* in a fresh pytest child process and return {nodeid: [TestReports]}.

    Reports cover setup/call/teardown via pytest-reportlog. Tests with no
    matching report (child crashed before reaching them, or while running them)
    get a fabricated failed TestReport so each nodeid produces a terminal
    outcome and longrepr pointing at the per-test log file.
    """
    _enable_target_devices_for_group(items, config)

    nodeids = [it.nodeid for it in items]
    # Sum of per-test timeouts as the parent-side budget; pytest-timeout in the
    # child still enforces individual test timeouts. +60s slack covers startup +
    # hub init + final teardown.
    child_timeout = sum((_marker_timeout(it) or _DEFAULT_TEST_TIMEOUT) for it in items) + 60

    fd, report_log_path = tempfile.mkstemp(prefix="rs-subproc-", suffix=".jsonl")
    os.close(fd)
    child_output = tempfile.TemporaryFile(mode="w+b")
    handler = logging_setup._current_file_handler
    log_path = getattr(handler, "baseFilename", None) if handler else None

    try:
        cmd = [
            sys.executable, "-u",
            "-m", "pytest", *nodeids,
            f"--report-log={report_log_path}",
            "-p", f"no:{PLUGIN_NAME}",
            "-p", "no:cacheprovider",
            "--no-header",
            "--tb=short",
        ]
        cmd.extend(_forwarded_args(config))

        log.debug("subprocess isolation: %d nodeid(s) in group; cmd=%s", len(nodeids), " ".join(cmd))
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

        all_reports = _parse_reportlog(report_log_path)
        by_nodeid = {nid: [] for nid in nodeids}
        for r in all_reports:
            if r.nodeid in by_nodeid:
                by_nodeid[r.nodeid].append(r)

        # Synthesize a failed report for every nodeid the child didn't fully cover.
        item_by_nodeid = {it.nodeid: it for it in items}
        for nid, reports in by_nodeid.items():
            phases = {r.when for r in reports}
            if not reports:
                summary = (
                    "did not run; earlier test in group crashed"
                    if returncode != 0 else
                    "did not run (no report from child)"
                )
                longrepr = f"{summary}; see {log_path}" if log_path else summary
                reports.append(_fabricate_failed(item_by_nodeid[nid], longrepr))
            elif "call" not in phases and returncode != 0:
                summary = _summary_for(returncode)
                longrepr = f"{summary}; see {log_path}" if log_path else summary
                reports.append(_fabricate_failed(item_by_nodeid[nid], longrepr))

        return by_nodeid
    finally:
        try:
            child_output.close()
        except Exception:
            pass
        try:
            os.unlink(report_log_path)
        except OSError:
            pass
