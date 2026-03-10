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
from typing import List

# unit-tests/py/ contains rspy — the shared helper library used by all RealSense tests
current_dir = os.path.dirname(os.path.abspath(__file__))
py_dir = os.path.join(current_dir, 'py')
if py_dir not in sys.path:
    sys.path.insert(0, py_dir)

# Consume --debug before any rspy imports (rspy.log also consumes it from sys.argv)
_debug_requested = '--debug' in sys.argv

import logging
from rspy import devices, repo
from rspy.signals import register_signal_handlers

log = logging.getLogger('librealsense')


# ============================================================================
# Legacy CLI Flag Translation
# ============================================================================
# The old run-unit-tests.py used flags like -r/--regex that clash with pytest built-ins.
# We intercept and translate them here, before pytest parses sys.argv.

def _find_flag(flag):
    """Find a flag in sys.argv, returning its index or None."""
    try:
        return sys.argv.index(flag)
    except ValueError:
        return None


def _consume_flag_with_arg(flags, pytest_equiv):
    """Consume a flag+argument from sys.argv, translate to pytest equivalent."""
    for flag in flags:
        idx = _find_flag(flag)
        if idx is not None:
            if idx + 1 >= len(sys.argv):
                print(f'-F- {flag} requires an argument', file=sys.stderr)
                sys.exit(1)
            value = sys.argv[idx + 1]
            del sys.argv[idx:idx + 2]
            sys.argv.extend([pytest_equiv, value])
            return value
    return None

_consume_flag_with_arg(['-r', '--regex'], '-k')  # -r/--regex -> pytest's -k (keyword filter)


# ============================================================================
# pyrealsense2 Import
# ============================================================================
# pyrealsense2 is built as part of the CMake build — repo.find_pyrs_dir() locates the .pyd/.so
pyrs_dir = repo.find_pyrs_dir()
if pyrs_dir and pyrs_dir not in sys.path:
    sys.path.insert(1, pyrs_dir)

try:
    import pyrealsense2 as rs
except ImportError:
    log.warning('No pyrealsense2 library available!')
    rs = None


# ============================================================================
# Platform Detection
# ============================================================================

def is_jetson_platform():
    """Detect NVIDIA Jetson — some tests behave differently on embedded platforms."""
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
    """Walk up from unit-tests/ to find the CMake build dir (contains CMakeCache.txt)."""
    search_dir = current_dir
    while True:
        cmake_cache = os.path.join(search_dir, 'CMakeCache.txt')
        if os.path.isfile(cmake_cache):
            log.debug(f'Found build dir: {search_dir}')
            return search_dir
        parent = os.path.dirname(search_dir)
        if parent == search_dir:
            if hasattr(repo, 'build') and repo.build:
                log.debug(f'Using repo.build: {repo.build}')
                return repo.build
            break
        search_dir = parent

    log.debug('Could not find build directory, using default')
    return None


def _setup_test_logging(config):
    """Set up per-test log directory and JUnit XML output path (<build_dir>/<config>/unit-tests/)."""
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
                            log.debug(f'Found CMAKE_BUILD_TYPE: {configuration}')
                            break
        except Exception as e:
            log.debug(f'Could not read CMAKE_BUILD_TYPE from CMakeCache.txt: {e}')

        if configuration:
            logdir = os.path.join(build_dir, configuration, 'unit-tests')
        else:
            logdir = os.path.join(build_dir, 'unit-tests')
    else:
        logdir = os.path.join(current_dir, 'logs')

    os.makedirs(logdir, exist_ok=True)
    log.debug(f'Test logs directory: {logdir}')

    if not config.getoption('--junitxml', default=None):
        junit_xml_path = os.path.join(logdir, 'pytest-results.xml')
        config.option.xmlpath = junit_xml_path
        log.info(f'JUnit XML results: {junit_xml_path}')

    config._test_logdir = logdir


# ============================================================================
# Pytest Hooks
# ============================================================================

def pytest_addoption(parser):
    """Register RealSense-specific CLI options (device filters, hub control, etc.)."""
    group = parser.getgroup('librealsense', 'RealSense unit test options')
    group.addoption(
        "--device",
        action="append",
        default=[],
        help="Include only devices matching pattern (e.g., --device D455). Can be used multiple times."
    )
    group.addoption(
        "--device-exclude",
        action="append",
        default=[],
        help="Exclude devices matching pattern (e.g., --device-exclude D455). Can be used multiple times."
    )
    group.addoption(
        "--context",
        action="store",
        default="",
        help="Context for test configuration (e.g., --context \"nightly weekly\"). Space-separated list."
    )
    group.addoption(
        "--rslog",
        action="store_true",
        default=False,
        help="Enable LibRS debug logging (rs.log_to_console)."
    )
    group.addoption(
        "--no-reset",
        action="store_true",
        default=False,
        help="Don't recycle (power-cycle) devices between tests."
    )
    group.addoption(
        "--hub-reset",
        action="store_true",
        default=False,
        help="Reset the hub itself during initialization."
    )
    group.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Only run tests that require a live device (have at least one device/device_each marker)."
    )
    # --debug and -r/--regex conflict with pytest built-ins and are consumed before
    # pytest parses args. Document them here so they show up in --help:
    group.addoption(
        "--rs-help",
        action="store_true",
        default=False,
        help="Pre-parsed flags (no need for --rs-help): "
             "--debug (enable -D- debug logs), "
             "-r/--regex <pattern> (filter tests by name, maps to -k), "
             "--retries N (retry failed tests N times)."
    )


# Shared context tags (e.g. "nightly", "weekly") — tests check this to adjust behavior
context_list = []


def pytest_configure(config):
    """Early setup: register markers, configure defaults, and query connected devices."""
    global context_list

    # Parse and store context
    context_str = config.getoption("--context", default="")
    if context_str:
        context_list = context_str.split()
        log.info(f"Test context: {context_list}")

    # Set up test log directory
    _setup_test_logging(config)

    # Test discovery defaults (replaces pytest.ini which is .gitignored)
    config.addinivalue_line("python_files", "pytest-*.py")
    config.addinivalue_line("python_classes", "Test*")
    config.addinivalue_line("python_functions", "test_*")

    # Default timeout: 200s, thread-based (Windows-compatible)
    if not config.getoption("--timeout", default=None):
        config.option.timeout = 200
        config.option.timeout_method = "thread"

    # Suppress paramiko and cryptography deprecation warnings
    config.addinivalue_line("filterwarnings", "ignore::DeprecationWarning:cryptography")
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

    # Configure standard logging with format matching legacy rspy.log output
    global _debug_requested
    if not _debug_requested:
        log_cli_level = config.getoption('--log-cli-level', default=None)
        if log_cli_level and log_cli_level.upper() == 'DEBUG':
            _debug_requested = True
    log_level_name = 'DEBUG' if _debug_requested else 'INFO'
    logging.getLogger().setLevel(getattr(logging, log_level_name))
    config.option.log_cli_level = log_level_name
    config.option.log_cli_format = '-%(levelname).1s- %(message)s'
    config.option.log_cli_date_format = ''
    if _debug_requested:
        logging.getLogger('paramiko').setLevel(logging.WARNING)

    # Query devices early for test parametrization
    try:
        hub_reset = config.getoption("--hub-reset", default=False)
        enable_dds = 'dds' in context_list
        devices.query(hub_reset=hub_reset, disable_dds=not enable_dds)
        devices.map_unknown_ports()
    except Exception as e:
        log.warning(f"Failed to query devices during configuration: {e}")


def pytest_generate_tests(metafunc):
    """Expand @device_each into one test instance per matching device (e.g. test[D455-SN123])."""
    device_each_markers = [m for m in metafunc.definition.iter_markers("device_each")]

    if not device_each_markers:
        return

    all_serials = []

    # Resolve exclusion patterns (markers + CLI) to a set of excluded serial numbers
    exclude_markers = [m for m in metafunc.definition.iter_markers("device_exclude")]
    exclude_patterns = [m.args[0] for m in exclude_markers if m.args]
    cli_excludes = metafunc.config.getoption("--device-exclude", default=[])
    exclude_patterns.extend(cli_excludes)
    excluded_sns = set()
    for pattern in exclude_patterns:
        excluded_sns.update(devices.by_spec(pattern, []))

    # Resolve CLI --device includes to a set of allowed serial numbers (None = no filter)
    cli_includes = metafunc.config.getoption("--device", default=[])
    included_sns = None
    if cli_includes:
        included_sns = set()
        for inc in cli_includes:
            included_sns.update(devices.by_spec(inc, []))

    for marker in device_each_markers:
        if not marker.args:
            continue
        pattern = marker.args[0]
        for sn in devices.by_spec(pattern, []):
            if sn in excluded_sns:
                continue
            if included_sns is not None and sn not in included_sns:
                continue
            if sn not in all_serials:
                all_serials.append(sn)

    if all_serials:
        ids = [f"{devices.get(sn).name}-{sn}" for sn in all_serials]
        metafunc.fixturenames.append('_test_device_serial')
        metafunc.parametrize("_test_device_serial", all_serials, ids=ids, scope="function")


def pytest_collection_modifyitems(config, items):
    """Auto-skip nightly/dds tests unless opted in, filter --live, and sort by priority."""
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


def _ensure_newline():
    """Pytest's progress dots (F/.) don't end with newline — force one before our log output."""
    sys.stdout.write('\n')
    sys.stdout.flush()


def _test_log_name(item):
    """Convert a node id like 'live/frames/pytest-t2ff.py::test_x[D455-SN]' to a log filename."""
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
    """Wrap each test with log separators and write per-test log file via logging FileHandler."""
    _ensure_newline()
    log.info("-" * 80)
    log.info(f"Test: {item.nodeid}")
    log.info("-" * 80)

    # Add per-test log file handler (only when stdout is captured, i.e. -s not passed)
    logdir = getattr(item.config, '_test_logdir', None)
    file_handler = None
    capture = item.config.getoption('capture', default='fd')

    if logdir and capture != 'no':
        log_name = _test_log_name(item)
        log_path = os.path.join(logdir, log_name)
        try:
            file_handler = logging.FileHandler(log_path, mode='w')
            file_handler.setFormatter(logging.Formatter('-%(levelname).1s- %(message)s'))
            file_handler.setLevel(logging.DEBUG)
            logging.getLogger().addHandler(file_handler)
        except Exception as e:
            log.warning(f"Could not create test log file {log_path}: {e}")
            file_handler = None

    outcome = yield

    # Remove per-test file handler
    if file_handler is not None:
        logging.getLogger().removeHandler(file_handler)
        file_handler.close()

    _ensure_newline()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Log test duration after each test call phase."""
    outcome = yield
    report = outcome.get_result()

    if call.when == "call":
        _ensure_newline()
        log.debug(f"Test execution took {report.duration:.3f}s")


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print a clear pass/fail/skip summary at the end of the run."""
    _ensure_newline()
    log.info("")
    log.info("=" * 80)
    log.info("Test Summary")
    log.info("=" * 80)

    passed = len(terminalreporter.stats.get('passed', []))
    failed = len(terminalreporter.stats.get('failed', []))
    skipped = len(terminalreporter.stats.get('skipped', []))
    error = len(terminalreporter.stats.get('error', []))
    total = passed + failed + skipped + error

    log.info(f"Total tests run: {total}")
    if passed > 0:
        log.info(f"Passed: {passed}")
    if failed > 0:
        log.info(f"Failed: {failed}")
    if skipped > 0:
        log.info(f"Skipped: {skipped}")
    if error > 0:
        log.info(f"Errors: {error}")

    log.info("=" * 80)


# ============================================================================
# Session-Scoped Fixtures
# ============================================================================

def _cleanup_devices():
    """Release hub and rs.context — required so BrainStem threads don't prevent exit."""
    if devices.hub:
        try:
            if devices.hub.is_connected():
                log.debug("Cleanup: disconnecting from hub(s)")
                devices.hub.disable_ports()
                devices.wait_until_all_ports_disabled()
            devices.hub.disconnect()
        except Exception:
            pass
        devices.hub = None
    devices._context = None
    import gc
    gc.collect()  # Force release so BrainStem USB hub threads shut down


@pytest.fixture(scope="session", autouse=True)
def session_setup_teardown():
    """Runs once per session: log startup info, yield, then clean up hub/devices on exit."""
    register_signal_handlers(_cleanup_devices)

    log.info("")
    log.info("=" * 80)
    log.info("Pytest Session Starting")
    log.info("=" * 80)

    if rs:
        log.info(f"Using pyrealsense2 from: {rs.__file__ if hasattr(rs, '__file__') else 'built-in'}")

    if hasattr(repo, 'build'):
        log.info(f"Build directory: {repo.build}")

    log.info("=" * 80)
    log.info("")

    yield

    _ensure_newline()
    log.info("")
    log.info("=" * 80)
    log.info("Pytest Session Ending")
    log.info("=" * 80)

    try:
        _cleanup_devices()
    except Exception as e:
        log.warning(f"Error during cleanup: {e}")

    log.info("=" * 80)


# ============================================================================
# Device Fixtures
# ============================================================================

@pytest.fixture
def _test_device_serial(request):
    """Receives the device serial injected by pytest_generate_tests parametrization."""
    return request.param


@pytest.fixture(scope="function")
def module_device_setup(request):
    """Enable the target device via the hub. Recycles (power-cycles) once per test file, not per test case."""
    serial_number = None

    # Check parametrized serial from device_each
    if hasattr(request.node, 'callspec') and '_test_device_serial' in request.node.callspec.params:
        serial_number = request.node.callspec.params['_test_device_serial']
        log.debug(f"Test using parametrized device: {serial_number}")
    else:
        # Fall back to marker-based detection (for device() marker)
        device_markers = []
        for marker in request.node.iter_markers():
            if marker.name in ['device', 'device_each', 'device_exclude']:
                device_markers.append(marker)

        if not device_markers:
            log.debug(f"Test {request.node.name} has no device requirements")
            yield None
            return

        serial_numbers = _find_matching_devices(device_markers, each=False,
                                                  cli_includes=request.config.getoption("--device", default=[]),
                                                  cli_excludes=request.config.getoption("--device-exclude", default=[]))

        if not serial_numbers:
            pytest.skip("No devices found matching requirements")

        serial_number = serial_numbers[0]
        log.debug(f"Test will use first matching device: {serial_number}")

    # Enable only this device; recycle only once per module (like run-unit-tests.py),
    # but also recycle on retries (same test running again after failure).
    device = devices.get(serial_number)
    device_name = device.name if device else serial_number
    log.info(f"Configuration: {device_name} [{serial_number}]")

    module = request.node.module
    nodeid = request.node.nodeid
    no_reset = request.config.getoption("--no-reset", default=False)
    already_reset = getattr(module, '_hub_reset_done', False)
    last_test = getattr(module, '_last_test_nodeid', None)
    is_retry = (last_test == nodeid)
    recycle = not no_reset and (not already_reset or is_retry)

    try:
        log.debug(f"{'Recycling' if recycle else 'Enabling'} device via hub...")
        devices.enable_only([serial_number], recycle=recycle)
        module._hub_reset_done = True
        module._last_test_nodeid = nodeid
        log.debug(f"Device enabled and ready")
    except Exception as e:
        pytest.fail(f"Failed to enable device {serial_number}: {e}")

    yield serial_number


@pytest.fixture
def test_context(request, module_device_setup):
    """Create a fresh rs.context() for the test. Depends on module_device_setup for hub state."""
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
    """Return (device, context) for the first visible device, or skip if none found."""
    devices_list = list(test_context.devices)
    if not devices_list:
        pytest.skip("No device available for test")

    dev = devices_list[0]
    log.debug(f"Test using device: {dev.get_info(rs.camera_info.name) if dev.supports(rs.camera_info.name) else 'Unknown'}")

    return dev, test_context



@pytest.fixture
def test_context_var():
    """Expose the --context tags (e.g. ['nightly', 'weekly']) so tests can branch on them."""
    return context_list


# ============================================================================
# Helper Functions
# ============================================================================

def _find_matching_devices(device_markers, each=True, cli_includes=None, cli_excludes=None) -> List[str]:
    """Resolve device markers + CLI filters into a list of matching serial numbers."""
    matching_sns = []

    if cli_includes is None:
        cli_includes = []
    if cli_excludes is None:
        cli_excludes = []

    # Resolve exclusion patterns (markers + CLI) to a set of excluded serial numbers
    exclude_patterns = []
    for marker in device_markers:
        if marker.name == 'device_exclude' and marker.args:
            exclude_patterns.append(marker.args[0])
            log.debug(f"Excluding devices matching pattern: {marker.args[0]}")
    exclude_patterns.extend(cli_excludes)

    excluded_sns = set()
    for pattern in exclude_patterns:
        excluded_sns.update(devices.by_spec(pattern, []))

    # Resolve CLI includes to a set of allowed serial numbers (None = no filter)
    included_sns = None
    if cli_includes:
        included_sns = set()
        for inc in cli_includes:
            included_sns.update(devices.by_spec(inc, []))

    # Find matching devices
    for marker in device_markers:
        if marker.name not in ['device', 'device_each'] or not marker.args:
            continue

        pattern = marker.args[0]
        log.debug(f"Looking for devices matching pattern: {pattern}")

        for sn in devices.by_spec(pattern, []):
            if sn in excluded_sns:
                log.debug(f"  Device {devices.get(sn).name} ({sn}) excluded")
                continue
            if included_sns is not None and sn not in included_sns:
                continue

            if sn not in matching_sns:
                matching_sns.append(sn)
                log.debug(f"  Found matching device: {devices.get(sn).name} ({sn})")

            if not each:
                return matching_sns

    return matching_sns
