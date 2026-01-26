# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

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
# Pytest Hooks
# ============================================================================

def pytest_addoption(parser):
    """
    Add custom command-line options for device filtering.
    """
    parser.addoption(
        "--device-exclude",
        action="append",
        default=[],
        help="Exclude devices matching pattern (e.g., --device-exclude D455). Can be used multiple times."
    )


def pytest_configure(config):
    """
    Register custom markers for device-based testing.
    """
    # Configure test file discovery pattern
    config.addinivalue_line("python_files", "pytest-*.py")
    
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
    
    # Suppress paramiko debug logs and warnings
    import logging
    import warnings
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    
    # Suppress paramiko deprecation warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="paramiko")
    warnings.filterwarnings("ignore", message=".*CryptographyDeprecationWarning.*")
    warnings.filterwarnings("ignore", message=".*TripleDES.*")
    warnings.filterwarnings("ignore", message=".*Blowfish.*")
    
    # Enable rspy debug logging if pytest log level is DEBUG
    log_cli_level = config.getoption('--log-cli-level', default=None)
    if log_cli_level and log_cli_level.upper() == 'DEBUG':
        log.debug_on()
    
    # Query devices early for test parametrization
    # This needs to happen during configure phase so pytest_generate_tests can access them
    # hub_reset=True will discover and reset the hub (just like old run-unit-tests.py)
    try:
        devices.query(hub_reset=True)
        # Map unknown ports - required to associate devices with hub ports
        # Without this, device.port will be None and enable_only won't work correctly
        devices.map_unknown_ports()
    except Exception as e:
        log.w(f"Failed to query devices during configuration: {e}")


def pytest_generate_tests(metafunc):
    """
    Parametrize tests based on device_each markers.
    
    For tests with device_each markers, this creates separate test instances
    for each matching device, so the test runs once per device with only that
    device enabled.
    """
    # Check if this test has device_each markers
    device_each_markers = [m for m in metafunc.definition.iter_markers("device_each")]
    
    if device_each_markers:
        # Collect all matching devices from device_each markers
        all_serials = []
        
        # Get exclusion patterns from markers
        exclude_markers = [m for m in metafunc.definition.iter_markers("device_exclude")]
        exclude_patterns = [m.args[0] for m in exclude_markers if m.args]
        
        # Also get exclusion patterns from CLI --device-exclude option
        cli_excludes = metafunc.config.getoption("--device-exclude", default=[])
        exclude_patterns.extend(cli_excludes)
        
        for marker in device_each_markers:
            if marker.args:
                pattern = marker.args[0]
                # Find all devices matching this pattern
                for sn in devices.all():
                    device = devices.get(sn)
                    if _device_matches_pattern(device, pattern):
                        # Check exclusions
                        excluded = any(_device_matches_pattern(device, exp) for exp in exclude_patterns)
                        if not excluded and sn not in all_serials:
                            all_serials.append(sn)
        
        if all_serials:
            # Store the list of serials in the test's custom data
            # This will be accessed by module_device_setup fixture
            ids = [f"{devices.get(sn).name}-{sn}" for sn in all_serials]
            # Add a custom fixture that will be requested automatically
            metafunc.fixturenames.append('_test_device_serial')
            metafunc.parametrize("_test_device_serial", all_serials, ids=ids, scope="function")

def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to:
    1. Handle nightly tests (skip by default unless explicitly requested)
    2. Handle DDS tests (skip by default unless explicitly requested)
    3. Sort tests by priority (lower numbers run first)
    
    By default, nightly and DDS tests are skipped unless explicitly requested.
    This matches LibCI behavior: #test:donotrun:!nightly and #test:donotrun:!dds
    
    To run nightly tests:
    - Use: pytest -m nightly (only nightly)
    - Use: pytest -m "nightly or not nightly" (all tests including nightly)
    
    To run DDS tests:
    - Use: pytest -m dds (only DDS)
    
    Priority system (matches LibCI test:priority):
    - Tests sorted by priority value (lower numbers run first)
    - Priority 1-499: Run before normal tests (high priority)
    - Priority 500: Default for tests without explicit priority
    - Priority 501-999: Run after normal tests (low priority)
    """
    # Check if user explicitly requested nightly or DDS tests
    markexpr = config.getoption("-m", default="")
    
    # Skip nightly tests unless explicitly included in marker expression
    # Examples that include nightly: "nightly", "nightly or not nightly", "nightly and device_each"
    if markexpr and "nightly" in markexpr:
        # User explicitly mentioned nightly in marker expression, don't skip
        pass
    else:
        # No marker expression or nightly not mentioned - skip nightly tests
        skip_nightly = pytest.mark.skip(reason="Nightly test (use -m nightly to run)")
        for item in items:
            if "nightly" in item.keywords:
                item.add_marker(skip_nightly)
    
    # Skip DDS tests unless explicitly included in marker expression
    if markexpr and "dds" in markexpr:
        # User explicitly mentioned dds in marker expression, don't skip
        pass
    else:
        # No marker expression or dds not mentioned - skip DDS tests
        skip_dds = pytest.mark.skip(reason="DDS test (use -m dds to run)")
        for item in items:
            if "dds" in item.keywords:
                item.add_marker(skip_dds)
    
    # Sort tests by priority (lower numbers first)
    def get_priority(item):
        """Extract priority value from test item, default to 500."""
        marker = item.get_closest_marker("priority")
        if marker and marker.args:
            return marker.args[0]
        return 500  # Default priority for tests without explicit priority
    
    items.sort(key=get_priority)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """
    Hook called for each test to add visual separators and indentation.
    """
    # Visual separator and test start
    log.i("")
    log.i("-" * 80)
    log.i(f"Test: {item.nodeid}")
    log.i("-" * 80)
    log.debug_indent()
    
    # Execute the test (setup, call, teardown)
    outcome = yield
    
    log.debug_unindent()
    print()  # Plain newline without log prefix
    log.i("-" * 80)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook called after each test phase (setup, call, teardown) to log results.
    Only logs for the 'call' phase (actual test execution).
    """
    outcome = yield
    report = outcome.get_result()
    
    # Only log for the actual test call phase (not setup/teardown)
    if call.when == "call":
        duration = report.duration
        # Just log the timing - pytest already shows PASSED/FAILED status
        log.d(f"Test execution took {duration:.3f}s")





# ============================================================================
# Session-Scoped Fixtures (Setup/Teardown)
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def session_setup_teardown():
    """
    Session-level setup and teardown.
    Initializes devices and hub, and cleans up at the end.
    """
    log.i("")
    log.i("=" * 80)
    log.i("Pytest Session Starting")
    log.i("=" * 80)
    
    # Log pyrealsense2 module location (INFO level so it's always visible)
    if rs:
        log.i(f"Using pyrealsense2 from: {rs.__file__ if hasattr(rs, '__file__') else 'built-in'}")
    
    # Log build directory
    if hasattr(repo, 'build'):
        log.i(f"Build directory: {repo.build}")
    
    log.i("=" * 80)
    log.i("")
    
    yield  # Run all tests
    
    # Session teardown
    log.i("")
    log.i("=" * 80)
    log.i("Pytest Session Ending")
    log.i("=" * 80)
    
    # Disconnect from hub and disable all ports
    if devices.hub and devices.hub.is_connected():
        log.i("Disconnecting from hub(s)")
        try:
            devices.hub.disable_ports()
            devices.wait_until_all_ports_disabled()
            devices.hub.disconnect()
        except Exception as e:
            log.w(f"Error during hub cleanup: {e}")
    
    log.i("=" * 80)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    Add a custom test summary to the log output.
    """
    log.i("")
    log.i("=" * 80)
    log.i("Test Summary")
    log.i("=" * 80)
    
    # Get test statistics
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


@pytest.fixture
def _test_device_serial(request):
    """
    Internal fixture to receive device serial from parametrization.
    This is automatically injected for tests with device_each markers.
    """
    return request.param


@pytest.fixture(scope="function")
def module_device_setup(request):
    """
    Function-level fixture that handles device selection and power cycling.
    
    This fixture:
    1. Determines which device the test needs (from _test_device_serial parameter or markers)
    2. Enables only that device port via the hub
    3. Powers cycles the device
    
    Yields the serial number of the enabled device.
    """
    serial_number = None
    
    # Check if test was parametrized with _test_device_serial
    # The parametrization from pytest_generate_tests adds it to the test's callspec
    # We can access it via the node's callspec params
    if hasattr(request.node, 'callspec') and '_test_device_serial' in request.node.callspec.params:
        serial_number = request.node.callspec.params['_test_device_serial']
        log.d(f"Test using parametrized device: {serial_number}")
    else:
        # Not parametrized, fall back to marker-based detection (for device() marker)
        device_markers = []
        for marker in request.node.iter_markers():
            if marker.name in ['device', 'device_each', 'device_exclude']:
                device_markers.append(marker)
        
        if not device_markers:
            # No device requirements, yield None
            log.d(f"Test {request.node.name} has no device requirements")
            yield None
            return
        
        # Find matching devices (only first one for device() marker)
        serial_numbers = _find_matching_devices(device_markers, each=False)
        
        if not serial_numbers:
            pytest.skip(f"No devices found matching requirements")
        
        serial_number = serial_numbers[0]
        log.d(f"Test will use first matching device: {serial_number}")
    
    # Enable only this specific device and power cycle
    device = devices.get(serial_number)
    device_name = device.name if device else serial_number
    log.i(f"Configuration: {device_name} [{serial_number}]")
    log.debug_indent()
    try:
        log.d(f"Recycling device via hub...")
        devices.enable_only([serial_number], recycle=True)
        log.d(f"Device enabled and ready")
    except Exception as e:
        log.debug_unindent()
        pytest.fail(f"Failed to enable device {serial_number}: {e}")
    finally:
        log.debug_unindent()
    
    yield serial_number
    
    # Function teardown - device will be power cycled by next test's setup


def _find_matching_devices(device_markers, each=True) -> List[str]:
    """
    Find devices that match the given markers.
    
    Args:
        device_markers: List of pytest markers with device requirements
        each: If True, return all matches; if False, return only first match
        
    Returns:
        List of serial numbers matching the requirements
    """
    all_device_sns = devices.all()
    matching_sns = []
    exclude_patterns = []
    
    # First, collect all exclusion patterns
    for marker in device_markers:
        if marker.name == 'device_exclude' and marker.args:
            exclude_patterns.append(marker.args[0])
            log.d(f"Excluding devices matching pattern: {marker.args[0]}")
    
    # Then find matching devices
    for marker in device_markers:
        if marker.name not in ['device', 'device_each'] or not marker.args:
            continue
            
        pattern = marker.args[0]
        log.d(f"Looking for devices matching pattern: {pattern}")
        
        # Find devices matching this pattern
        for sn in all_device_sns:
            device = devices.get(sn)
            if _device_matches_pattern(device, pattern):
                # Check if device should be excluded
                excluded = False
                for exclude_pattern in exclude_patterns:
                    if _device_matches_pattern(device, exclude_pattern):
                        log.d(f"  Device {device.name} ({sn}) excluded by pattern: {exclude_pattern}")
                        excluded = True
                        break
                
                if not excluded and sn not in matching_sns:
                    matching_sns.append(sn)
                    log.d(f"  Found matching device: {device.name} ({sn})")
                
                # If not 'each', just take the first match
                if not each:
                    return matching_sns
    
    return matching_sns


def _device_matches_pattern(device, pattern: str) -> bool:
    """
    Check if a device matches a pattern like 'D400*', 'D455', etc.
    
    Args:
        device: Device object from devices module
        pattern: Pattern string to match against
        
    Returns:
        True if device matches the pattern
    """
    # Convert pattern to regex
    # D400* -> D400.*
    # D455 -> D455
    regex_pattern = pattern.replace('*', '.*')
    regex_pattern = f'^{regex_pattern}$'
    
    # Check against product line (e.g., "D400")
    if device.product_line and re.match(regex_pattern, device.product_line):
        return True
    
    # Check against device name (e.g., "D455")
    if device.name and re.match(regex_pattern, device.name):
        return True
    
    return False


# ============================================================================
# Test-Level Fixtures
# ============================================================================

@pytest.fixture
def test_context(module_device_setup):
    """
    Provides a pyrealsense2 context that only sees the device enabled for this test.
    
    The device hub has already filtered which devices are visible by enabling only
    a specific port, so a standard context will work correctly.
    """
    if not rs:
        pytest.skip("pyrealsense2 not available")
    
    ctx = rs.context()
    
    # Verify device is available
    if module_device_setup and len(list(ctx.devices)) == 0:
        pytest.fail("No devices visible in context after device setup")
    
    return ctx


@pytest.fixture
def module_test_device(test_context):
    """
    Provides the first (and only) available device for the test.
    
    Use this fixture when you need to set up device configuration at the start of a test,
    such as determining product line or capabilities.
    """
    devices_list = list(test_context.devices)
    if not devices_list:
        pytest.skip("No device available for test")
    
    dev = devices_list[0]
    log.d(f"Test using device: {dev.get_info(rs.camera_info.name) if dev.supports(rs.camera_info.name) else 'Unknown'}")
    
    return dev, test_context


@pytest.fixture
def test_device(test_context):
    """
    Provides the first available device for the test (function-scoped).
    
    Equivalent to the old test.find_first_device_or_exit() pattern.
    Use this for tests that need a fresh device reference per test.
    """
    devices_list = list(test_context.devices)
    if not devices_list:
        pytest.skip("No device available for test")
    
    dev = devices_list[0]
    log.d(f"Test using device: {dev.get_info(rs.camera_info.name) if dev.supports(rs.camera_info.name) else 'Unknown'}")
    
    return dev, test_context


@pytest.fixture
def test_wrapper_info(request):
    """
    Provides test metadata for logging and reporting.
    """
    test_name = request.node.name
    test_file = request.node.fspath.basename
    
    log.d(f"Starting test: {test_name} in {test_file}")
    
    # This info can be used by tests if needed
    info = {
        'name': test_name,
        'file': test_file,
        'node': request.node
    }
    
    yield info
    
    # Test finished - pytest handles pass/fail reporting
