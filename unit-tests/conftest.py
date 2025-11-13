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
# Pytest Hooks
# ============================================================================

def pytest_configure(config):
    """
    Register custom markers for device-based testing.
    """
    config.addinivalue_line(
        "markers", "device(pattern): mark test to run on devices matching pattern (e.g., D400*, D455)"
    )
    config.addinivalue_line(
        "markers", "device_each(pattern): mark test to run on each device matching pattern separately"
    )
    config.addinivalue_line(
        "markers", "live: tests requiring live devices"
    )
    
    # Enable rspy debug logging if pytest log level is DEBUG
    log_cli_level = config.getoption('--log-cli-level', default=None)
    if log_cli_level and log_cli_level.upper() == 'DEBUG':
        log.debug_on()


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to handle nightly tests.
    
    By default, nightly tests are skipped unless explicitly requested.
    This matches LibCI behavior: #test:donotrun:!nightly
    
    To run nightly tests:
    - Use: pytest -m nightly (only nightly)
    - Use: pytest -m "nightly or not nightly" (all tests including nightly)
    """
    # Check if user explicitly requested nightly tests
    markexpr = config.getoption("-m", default="")
    
    # Skip nightly tests unless explicitly included in marker expression
    # Examples that include nightly: "nightly", "nightly or not nightly", "nightly and device_each"
    if markexpr and "nightly" in markexpr:
        # User explicitly mentioned nightly in marker expression, don't skip
        return
    
    # No marker expression or nightly not mentioned - skip nightly tests
    skip_nightly = pytest.mark.skip(reason="Nightly test (use -m nightly to run)")
    for item in items:
        if "nightly" in item.keywords:
            item.add_marker(skip_nightly)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """
    Hook called for each test to log device state changes and test duration.
    """
    import time
    
    # Log test starting
    log.d(f"Running test: {item.nodeid}")
    
    # Track start time
    start_time = time.time()
    
    # Execute the test
    yield
    
    # Log test completion with duration
    duration = time.time() - start_time
    log.d(f"Test took {duration:.3f} seconds")


# ============================================================================
# Session-Scoped Fixtures (Setup/Teardown)
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def session_setup_teardown():
    """
    Session-level setup and teardown.
    Initializes devices and hub, and cleans up at the end.
    """
    log.d("=== Pytest Session Starting ===")
    
    # Log pyrealsense2 module location (INFO level so it's always visible)
    if rs:
        log.i(f"Using pyrealsense2 from: {rs.__file__ if hasattr(rs, '__file__') else 'built-in'}")
    
    # Log build directory
    log.d(f"Build directory: {repo.build if hasattr(repo, 'build') else 'unknown'}")
    
    # Initialize devices (this will query and enumerate all connected devices)
    log.i("Discovering devices...")
    try:
        devices.query()
        all_devices = devices.all()
        log.d(f"Found {len(all_devices)} device(s)")
        
        # Log each discovered device
        for sn in all_devices:
            dev = devices.get(sn)
            if dev:
                log.d(f"    ... {sn}: {dev}")
        
        # Log hub information if available
        if devices.hub and devices.hub.is_connected():
            log.d(f"Device hub connected: {type(devices.hub).__name__}")
    except Exception as e:
        log.w(f"Failed to query devices: {e}")
    
    yield  # Run all tests
    
    # Session teardown
    log.d("=== Pytest Session Ending ===")
    
    # Disconnect from hub and disable all ports
    if devices.hub and devices.hub.is_connected():
        log.d("Disconnecting from hub(s)")
        try:
            devices.hub.disable_ports()
            devices.wait_until_all_ports_disabled()
            devices.hub.disconnect()
        except Exception as e:
            log.w(f"Error during hub cleanup: {e}")


@pytest.fixture(scope="module")
def module_device_setup(request):
    """
    Module-level fixture that handles device selection and power cycling.
    
    This fixture:
    1. Determines which device(s) the module needs based on markers
    2. Enables only those device port(s) via the hub
    3. Powers cycles devices between modules
    
    Yields the serial numbers of enabled devices.
    """
    # Get device markers from the test module
    device_markers = []
    for item in request.session.items:
        if item.fspath == request.fspath:
            # Collect all device markers from this module's tests
            for marker in item.iter_markers():
                if marker.name in ['device', 'device_each']:
                    device_markers.append(marker)
            break
    
    if not device_markers:
        # No device requirements, yield None
        log.d(f"Module {request.module.__name__} has no device requirements")
        yield None
        return
    
    # Find matching devices
    serial_numbers = _find_matching_devices(device_markers)
    
    if not serial_numbers:
        pytest.skip(f"No devices found matching requirements: {device_markers}")
    
    log.d(f"Module {request.module.__name__} will use devices: {serial_numbers}")
    
    # Enable only the required device(s) and power cycle
    try:
        devices.enable_only(serial_numbers, recycle=True)
        log.d(f"Enabled and recycled devices: {serial_numbers}")
    except Exception as e:
        pytest.fail(f"Failed to enable devices {serial_numbers}: {e}")
    
    yield serial_numbers
    
    # Module teardown - devices will be power cycled by next module's setup


def _find_matching_devices(device_markers) -> List[str]:
    """
    Find devices that match the given markers.
    
    Args:
        device_markers: List of pytest markers with device requirements
        
    Returns:
        List of serial numbers matching the requirements
    """
    all_device_sns = devices.all()
    matching_sns = []
    
    for marker in device_markers:
        if not marker.args:
            continue
            
        pattern = marker.args[0]
        log.d(f"Looking for devices matching pattern: {pattern}")
        
        # Find devices matching this pattern
        for sn in all_device_sns:
            device = devices.get(sn)
            if _device_matches_pattern(device, pattern):
                if sn not in matching_sns:
                    matching_sns.append(sn)
                    log.d(f"  Found matching device: {device.name} ({sn})")
                
                # If not 'each', just take the first match
                if marker.name != 'device_each':
                    break
    
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

@pytest.fixture(scope="module")
def test_context(module_device_setup):
    """
    Provides a pyrealsense2 context that only sees the devices enabled for this module.
    
    The device hub has already filtered which devices are visible by enabling only
    specific ports, so a standard context will work correctly.
    
    This is module-scoped so all tests in a module share the same context.
    """
    if not rs:
        pytest.skip("pyrealsense2 not available")
    
    ctx = rs.context()
    
    # Verify devices are available
    if module_device_setup and len(list(ctx.devices)) == 0:
        pytest.fail("No devices visible in context after device setup")
    
    return ctx


@pytest.fixture(scope="module")
def module_test_device(test_context):
    """
    Provides the first available device for the entire module (module-scoped).
    
    Use this fixture when you need to set up device configuration once for all tests
    in a module, such as determining product line or capabilities.
    """
    devices_list = list(test_context.devices)
    if not devices_list:
        pytest.skip("No device available for module")
    
    dev = devices_list[0]
    log.d(f"Module using device: {dev.get_info(rs.camera_info.name) if dev.supports(rs.camera_info.name) else 'Unknown'}")
    
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
