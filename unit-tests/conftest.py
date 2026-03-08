# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
Pytest configuration and fixtures for RealSense unit tests.

This module provides the pytest infrastructure to replace the proprietary LibCI system.
It manages:
- Device hub control for power cycling
- Device selection based on markers
- Context filtering to ensure tests only see intended devices
- Session-scoped device management
"""

import pytest
import sys
import os
import re
import warnings
from typing import List

# Add py directory to path for rspy imports
current_dir = os.path.dirname(os.path.abspath(__file__))
py_dir = os.path.join(current_dir, 'py')
if py_dir not in sys.path:
    sys.path.insert(0, py_dir)

from rspy import log, devices, repo

# Find and add pyrealsense2 to path
pyrs_dir = repo.find_pyrs_dir()
if pyrs_dir and pyrs_dir not in sys.path:
    sys.path.insert(1, pyrs_dir)

try:
    import pyrealsense2 as rs
except ImportError:
    log.w('No pyrealsense2 library available!')
    rs = None


# ============================================================================
# Platform Detection
# ============================================================================

def is_jetson_platform():
    """
    Detect if running on NVIDIA Jetson platform.
    """
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read()
            return 'jetson' in model.lower()
    except:
        return False


# ============================================================================
# Logging Setup
# ============================================================================

def _find_build_dir():
    """
    Find the build directory by searching upward from current directory.
    Matches the logic in run-unit-tests.py.
    """
    search_dir = current_dir
    while True:
        cmake_cache = os.path.join(search_dir, 'CMakeCache.txt')
        if os.path.isfile(cmake_cache):
            log.d(f'Found build dir: {search_dir}')
            return search_dir
        parent = os.path.dirname(search_dir)
        if parent == search_dir:
            if hasattr(repo, 'build') and repo.build:
                log.d(f'Using repo.build: {repo.build}')
                return repo.build
            break
        search_dir = parent

    log.d('Could not find build directory, using default')
    return None


def _setup_test_logging(config):
    """
    Set up test logging to match run-unit-tests.py behavior.

    Logs are written to: <build_dir>/<CONFIGURATION>/unit-tests/
    """
    build_dir = _find_build_dir()

    if build_dir:
        cmake_cache_path = os.path.join(build_dir, 'CMakeCache.txt')
        configuration = None

        try:
            with open(cmake_cache_path, 'r') as f:
                for line in f:
                    if line.startswith('CMAKE_BUILD_TYPE:'):
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            configuration = parts[1].strip()
                            log.d(f'Found CMAKE_BUILD_TYPE: {configuration}')
                            break
        except Exception as e:
            log.d(f'Could not read CMAKE_BUILD_TYPE from CMakeCache.txt: {e}')

        if configuration:
            logdir = os.path.join(build_dir, configuration, 'unit-tests')
        else:
            logdir = os.path.join(build_dir, 'unit-tests')
    else:
        logdir = os.path.join(current_dir, 'logs')

    os.makedirs(logdir, exist_ok=True)
    log.d(f'Test logs directory: {logdir}')

    if not config.getoption('--junitxml', default=None):
        junit_xml_path = os.path.join(logdir, 'pytest-results.xml')
        config.option.xmlpath = junit_xml_path
        log.i(f'JUnit XML results: {junit_xml_path}')

    config._test_logdir = logdir


# ============================================================================
# Pytest Hooks
# ============================================================================

def pytest_addoption(parser):
    """
    Add custom command-line options — full CLI parity with run-unit-tests.py.
    """
    parser.addoption(
        "--device",
        action="append",
        default=[],
        help="Include only devices matching pattern (e.g., --device D455). Can be used multiple times."
    )
    parser.addoption(
        "--device-exclude",
        action="append",
        default=[],
        help="Exclude devices matching pattern (e.g., --device-exclude D455). Can be used multiple times."
    )
    parser.addoption(
        "--context",
        action="store",
        default="",
        help="Context for test configuration (e.g., --context \"nightly weekly\"). Space-separated list."
    )
    parser.addoption(
        "--rslog",
        action="store_true",
        default=False,
        help="Enable LibRS debug logging (rs.log_to_console)."
    )
    parser.addoption(
        "--no-reset",
        action="store_true",
        default=False,
        help="Don't recycle (power-cycle) devices between tests."
    )
    parser.addoption(
        "--hub-reset",
        action="store_true",
        default=False,
        help="Reset the hub itself during initialization."
    )
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Only run tests that require a live device (have at least one device/device_each marker)."
    )
    # Note: --debug is consumed by rspy.log at import time (before pytest parses args)
    # and enables rspy debug logging (-D- lines) in test output and per-test log files.
    # It also triggers pytest's built-in debug mode (pytestdebug.log) — this is harmless.


# Global context variable to match old LibCI behavior
context_list = []


def pytest_configure(config):
    """
    Register custom markers and perform early setup.
    """
    global context_list

    # Parse and store context
    context_str = config.getoption("--context", default="")
    if context_str:
        context_list = context_str.split()
        log.i(f"Test context: {context_list}")

    # Set up test log directory
    _setup_test_logging(config)

    # Configure test discovery and defaults (replaces pytest.ini)
    config.addinivalue_line("python_files", "pytest-*.py")
    config.addinivalue_line("python_classes", "Test*")
    config.addinivalue_line("python_functions", "test_*")

    # Default timeout: 200s, thread-based (Windows-compatible)
    if not config.getoption("--timeout", default=None):
        config.option.timeout = 200
        config.option.timeout_method = "thread"

    # Suppress paramiko and cryptography deprecation warnings
    config.addinivalue_line("filterwarnings", "ignore::cryptography.utils.CryptographyDeprecationWarning")
    config.addinivalue_line("filterwarnings", "ignore::DeprecationWarning:paramiko")
    config.addinivalue_line("filterwarnings", "ignore:TripleDES has been moved")
    config.addinivalue_line("filterwarnings", "ignore:Blowfish has been moved")

    # Register custom markers
    config.addinivalue_line(
        "markers", "device(pattern): mark test to run on devices matching pattern (e.g., D400*, D455)"
    )
    config.addinivalue_line(
        "markers", "device_each(pattern): mark test to run on each device matching pattern separately"
    )
    config.addinivalue_line(
        "markers", "device_exclude(pattern): exclude devices matching pattern from test execution"
    )
    config.addinivalue_line(
        "markers", "live: tests requiring live devices"
    )
    config.addinivalue_line(
        "markers", "nightly: tests that only run in nightly context"
    )
    config.addinivalue_line(
        "markers", "dds: tests requiring DDS support"
    )
    config.addinivalue_line(
        "markers", "priority(value): test execution priority (lower runs first, default 500)"
    )

    # Enable rspy debug logging:
    # --debug is consumed by rspy.log at import time and calls log.debug_on()
    # --log-cli-level=DEBUG is an alternative way to enable it
    if not log.is_debug_on():
        log_cli_level = config.getoption('--log-cli-level', default=None)
        if log_cli_level and log_cli_level.upper() == 'DEBUG':
            log.debug_on()
    if log.is_debug_on():
        import logging
        logging.getLogger('paramiko').setLevel(logging.WARNING)

    # Query devices early for test parametrization
    try:
        hub_reset = config.getoption("--hub-reset", default=False)
        enable_dds = 'dds' in context_list
        devices.query(hub_reset=hub_reset, disable_dds=not enable_dds)
        devices.map_unknown_ports()
    except Exception as e:
        log.w(f"Failed to query devices during configuration: {e}")


def pytest_generate_tests(metafunc):
    """
    Parametrize tests based on device_each markers.

    Creates one test instance per matching device, with IDs like {name}-{serial}.
    Respects --device include filter, --device-exclude CLI filter, and device_exclude markers.
    """
    device_each_markers = [m for m in metafunc.definition.iter_markers("device_each")]

    if not device_each_markers:
        return

    all_serials = []

    # Collect exclusion patterns from markers
    exclude_markers = [m for m in metafunc.definition.iter_markers("device_exclude")]
    exclude_patterns = [m.args[0] for m in exclude_markers if m.args]

    # Add CLI --device-exclude patterns
    cli_excludes = metafunc.config.getoption("--device-exclude", default=[])
    exclude_patterns.extend(cli_excludes)

    # Get CLI --device include patterns (if any, only matching devices are considered)
    cli_includes = metafunc.config.getoption("--device", default=[])

    for marker in device_each_markers:
        if not marker.args:
            continue
        pattern = marker.args[0]
        for sn in devices.all():
            device = devices.get(sn)
            if not _device_matches_pattern(device, pattern):
                continue
            # Check CLI include filter
            if cli_includes and not any(_device_matches_pattern(device, inc) for inc in cli_includes):
                continue
            # Check exclusions
            if any(_device_matches_pattern(device, exp) for exp in exclude_patterns):
                continue
            if sn not in all_serials:
                all_serials.append(sn)

    if all_serials:
        ids = [f"{devices.get(sn).name}-{sn}" for sn in all_serials]
        metafunc.fixturenames.append('_test_device_serial')
        metafunc.parametrize("_test_device_serial", all_serials, ids=ids, scope="function")


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection:
    1. Skip nightly tests unless -m nightly specified
    2. Skip dds tests unless -m dds specified
    3. Sort by priority marker (lower first, default 500)
    """
    markexpr = config.getoption("-m", default="")

    if not (markexpr and "nightly" in markexpr):
        skip_nightly = pytest.mark.skip(reason="Nightly test (use -m nightly to run)")
        for item in items:
            if "nightly" in item.keywords:
                item.add_marker(skip_nightly)

    if not (markexpr and "dds" in markexpr):
        skip_dds = pytest.mark.skip(reason="DDS test (use -m dds to run)")
        for item in items:
            if "dds" in item.keywords:
                item.add_marker(skip_dds)

    # Skip non-device tests when --live is specified
    if config.getoption("--live", default=False):
        skip_no_device = pytest.mark.skip(reason="--live: test has no device requirement")
        for item in items:
            has_device = any(item.iter_markers("device")) or any(item.iter_markers("device_each"))
            if not has_device:
                item.add_marker(skip_no_device)

    def get_priority(item):
        marker = item.get_closest_marker("priority")
        if marker and marker.args:
            return marker.args[0]
        return 500

    items.sort(key=get_priority)


class _TeeWriter:
    """
    Tee stdout to both the original stream and a log file.
    """
    def __init__(self, original, log_file):
        self._original = original
        self._log_file = log_file

    def write(self, data):
        self._original.write(data)
        try:
            self._log_file.write(data)
        except Exception:
            pass

    def flush(self):
        self._original.flush()
        try:
            self._log_file.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._original, name)


def _test_log_name(item):
    """
    Derive a log file name from a pytest node id.
    E.g., 'unit-tests/live/frames/pytest-t2ff-pipeline.py::test_func[D455-SN]'
      ->  'pytest-t2ff-pipeline[D455-SN].log'
    """
    # Get the test file basename without extension
    file_path = item.fspath
    basename = os.path.splitext(os.path.basename(str(file_path)))[0]  # 'pytest-t2ff-pipeline'

    # Get the test name with parametrize suffix
    test_name = item.name  # 'test_func[D455-SN]'

    # Combine: pytest-t2ff-pipeline_test_func[D455-SN].log
    # Sanitize for filesystem
    log_name = f"{basename}_{test_name}"
    log_name = re.sub(r'[<>:"/\\|?*]', '_', log_name)
    return log_name + ".log"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """
    Visual separators around each test, and per-test log file creation.
    """
    log.i("-" * 80)
    log.i(f"Test: {item.nodeid}")
    log.i("-" * 80)
    log.debug_indent()

    # Set up per-test log file if logdir is available
    logdir = getattr(item.config, '_test_logdir', None)
    log_file = None
    original_stdout = None

    if logdir:
        log_name = _test_log_name(item)
        log_path = os.path.join(logdir, log_name)
        try:
            log_file = open(log_path, 'w')
            original_stdout = sys.stdout
            sys.stdout = _TeeWriter(original_stdout, log_file)
        except Exception as e:
            log.w(f"Could not create test log file {log_path}: {e}")
            log_file = None

    outcome = yield

    # Restore stdout and close log file
    if original_stdout is not None:
        sys.stdout = original_stdout
    if log_file is not None:
        try:
            log_file.close()
        except Exception:
            pass

    log.debug_unindent()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Log test execution timing after the call phase.
    """
    outcome = yield
    report = outcome.get_result()

    if call.when == "call":
        log.d(f"Test execution took {report.duration:.3f}s")


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    Summary with pass/fail/skip counts.
    """
    log.i("")
    log.i("=" * 80)
    log.i("Test Summary")
    log.i("=" * 80)

    passed = len(terminalreporter.stats.get('passed', []))
    failed = len(terminalreporter.stats.get('failed', []))
    skipped = len(terminalreporter.stats.get('skipped', []))
    error = len(terminalreporter.stats.get('error', []))
    total = passed + failed + skipped + error

    log.i(f"Total tests run: {total}")
    if passed > 0:
        log.i(f"Passed: {passed}")
    if failed > 0:
        log.i(f"Failed: {failed}")
    if skipped > 0:
        log.i(f"Skipped: {skipped}")
    if error > 0:
        log.i(f"Errors: {error}")

    log.i("=" * 80)


# ============================================================================
# Session-Scoped Fixtures
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def session_setup_teardown():
    """
    Session-level setup and teardown.
    Logs session start, yields, then disconnects hub and disables ports.
    """
    log.i("")
    log.i("=" * 80)
    log.i("Pytest Session Starting")
    log.i("=" * 80)

    if rs:
        log.i(f"Using pyrealsense2 from: {rs.__file__ if hasattr(rs, '__file__') else 'built-in'}")

    if hasattr(repo, 'build'):
        log.i(f"Build directory: {repo.build}")

    log.i("=" * 80)
    log.i("")

    yield

    log.i("")
    log.i("=" * 80)
    log.i("Pytest Session Ending")
    log.i("=" * 80)

    if devices.hub and devices.hub.is_connected():
        log.i("Disconnecting from hub(s)")
        try:
            devices.hub.disable_ports()
            devices.wait_until_all_ports_disabled()
            devices.hub.disconnect()
        except Exception as e:
            log.w(f"Error during hub cleanup: {e}")

    log.i("=" * 80)


# ============================================================================
# Device Fixtures
# ============================================================================

@pytest.fixture
def _test_device_serial(request):
    """
    Internal fixture to receive device serial from parametrization.
    Automatically injected for tests with device_each markers.
    """
    return request.param


@pytest.fixture(scope="function")
def module_device_setup(request):
    """
    Enable only the required device port, optionally recycle (--no-reset check).
    Yields the serial number of the enabled device.
    """
    serial_number = None

    # Check parametrized serial from device_each
    if hasattr(request.node, 'callspec') and '_test_device_serial' in request.node.callspec.params:
        serial_number = request.node.callspec.params['_test_device_serial']
        log.d(f"Test using parametrized device: {serial_number}")
    else:
        # Fall back to marker-based detection (for device() marker)
        device_markers = []
        for marker in request.node.iter_markers():
            if marker.name in ['device', 'device_each', 'device_exclude']:
                device_markers.append(marker)

        if not device_markers:
            log.d(f"Test {request.node.name} has no device requirements")
            yield None
            return

        serial_numbers = _find_matching_devices(device_markers, each=False,
                                                  cli_includes=request.config.getoption("--device", default=[]),
                                                  cli_excludes=request.config.getoption("--device-exclude", default=[]))

        if not serial_numbers:
            pytest.skip("No devices found matching requirements")

        serial_number = serial_numbers[0]
        log.d(f"Test will use first matching device: {serial_number}")

    # Enable only this device; recycle unless --no-reset
    device = devices.get(serial_number)
    device_name = device.name if device else serial_number
    log.i(f"Configuration: {device_name} [{serial_number}]")
    log.debug_indent()
    try:
        no_reset = request.config.getoption("--no-reset", default=False)
        recycle = not no_reset
        log.d(f"{'Recycling' if recycle else 'Enabling'} device via hub...")
        devices.enable_only([serial_number], recycle=recycle)
        log.d(f"Device enabled and ready")
    except Exception as e:
        log.debug_unindent()
        pytest.fail(f"Failed to enable device {serial_number}: {e}")
    finally:
        log.debug_unindent()

    yield serial_number


@pytest.fixture
def test_context(request, module_device_setup):
    """
    Create rs.context(), optionally enable --rslog.
    """
    if not rs:
        pytest.skip("pyrealsense2 not available")

    # Enable LibRS debug logging if --rslog
    if request.config.getoption("--rslog", default=False):
        rs.log_to_console(rs.log_severity.debug)

    ctx = rs.context()

    if module_device_setup and len(list(ctx.devices)) == 0:
        pytest.fail("No devices visible in context after device setup")

    return ctx


@pytest.fixture
def test_device(test_context):
    """
    Find first device in context or pytest.skip.
    Equivalent to the old test.find_first_device_or_exit().
    """
    devices_list = list(test_context.devices)
    if not devices_list:
        pytest.skip("No device available for test")

    dev = devices_list[0]
    log.d(f"Test using device: {dev.get_info(rs.camera_info.name) if dev.supports(rs.camera_info.name) else 'Unknown'}")

    return dev, test_context


@pytest.fixture
def module_test_device(test_context):
    """
    Alias for test_device — provides (device, context) tuple.
    """
    devices_list = list(test_context.devices)
    if not devices_list:
        pytest.skip("No device available for test")

    dev = devices_list[0]
    log.d(f"Test using device: {dev.get_info(rs.camera_info.name) if dev.supports(rs.camera_info.name) else 'Unknown'}")

    return dev, test_context


@pytest.fixture
def test_context_var():
    """
    Provides the test context list (e.g., ['nightly', 'weekly']).
    Matches the old LibCI test.context behavior.
    """
    return context_list


# ============================================================================
# Helper Functions
# ============================================================================

def _device_matches_pattern(device, pattern: str) -> bool:
    """
    Wildcard matching against product_line and name.
    E.g., 'D400*' matches product_line 'D400'; 'D455' matches name 'D455'.
    """
    regex_pattern = pattern.replace('*', '.*')
    regex_pattern = f'^{regex_pattern}$'

    if device.product_line and re.match(regex_pattern, device.product_line):
        return True

    if device.name and re.match(regex_pattern, device.name):
        return True

    return False


def _find_matching_devices(device_markers, each=True, cli_includes=None, cli_excludes=None) -> List[str]:
    """
    Collect serial numbers from markers + filters.
    """
    all_device_sns = devices.all()
    matching_sns = []
    exclude_patterns = []

    if cli_includes is None:
        cli_includes = []
    if cli_excludes is None:
        cli_excludes = []

    # Collect exclusion patterns from markers
    for marker in device_markers:
        if marker.name == 'device_exclude' and marker.args:
            exclude_patterns.append(marker.args[0])
            log.d(f"Excluding devices matching pattern: {marker.args[0]}")

    # Add CLI exclusions
    exclude_patterns.extend(cli_excludes)

    # Find matching devices
    for marker in device_markers:
        if marker.name not in ['device', 'device_each'] or not marker.args:
            continue

        pattern = marker.args[0]
        log.d(f"Looking for devices matching pattern: {pattern}")

        for sn in all_device_sns:
            device = devices.get(sn)
            if not _device_matches_pattern(device, pattern):
                continue

            # Check CLI include filter
            if cli_includes and not any(_device_matches_pattern(device, inc) for inc in cli_includes):
                continue

            # Check exclusions
            excluded = any(_device_matches_pattern(device, exp) for exp in exclude_patterns)
            if excluded:
                log.d(f"  Device {device.name} ({sn}) excluded")
                continue

            if sn not in matching_sns:
                matching_sns.append(sn)
                log.d(f"  Found matching device: {device.name} ({sn})")

            if not each:
                return matching_sns

    return matching_sns
