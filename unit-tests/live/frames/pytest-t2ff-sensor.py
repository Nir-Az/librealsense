# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
Test time-to-first-frame for sensor API.

This test measures the time from sensor.open() until the first frame arrives
for both depth and color streams using the lower-level sensor API (as opposed
to the pipeline API). It verifies that startup time does not exceed maximum
allowed delays.

Note: Using Windows Media Foundation to handle power management between USB actions
can add ~27ms to the startup time.
"""

import pytest
import pyrealsense2 as rs
from rspy.stopwatch import Stopwatch
from rspy import log
import time
import platform

# Mark this module to run on D400 and D500 devices
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.live
]


# ============================================================================
# Helper Functions
# ============================================================================

def time_to_first_frame(sensor, profile, max_delay_allowed):
    """
    Wait for the first frame for 'max_delay_allowed' + 1 extra second.
    
    Args:
        sensor: RealSense sensor object
        profile: Stream profile to use
        max_delay_allowed: Maximum time allowed in seconds
        
    Returns:
        Time in seconds from open() call until first frame arrives,
        or max_delay_allowed if timeout occurs
    """
    first_frame_time = max_delay_allowed
    open_call_stopwatch = Stopwatch()

    def frame_cb(frame):
        nonlocal first_frame_time, open_call_stopwatch
        if first_frame_time == max_delay_allowed:
            first_frame_time = open_call_stopwatch.get_elapsed()

    open_call_stopwatch.reset()
    sensor.open(profile)
    sensor.start(frame_cb)

    # Wait condition:
    # 1. first frame did not arrive yet
    # 2. timeout of 'max_delay_allowed' + 1 extra second reached
    while first_frame_time == max_delay_allowed and open_call_stopwatch.get_elapsed() < max_delay_allowed + 1:
        time.sleep(0.05)

    sensor.stop()
    sensor.close()

    return first_frame_time


# ============================================================================
# Test Fixtures and Setup
# ============================================================================

@pytest.fixture(scope="module")
def device_config(module_test_device):
    """
    Set up device and determine maximum allowed delays based on product line.
    """
    dev, ctx = module_test_device
    
    # The device starts at D0 (Operational) state, allow time for it to get into idle state
    time.sleep(3)
    
    product_line = dev.get_info(rs.camera_info.product_line)
    product_name = dev.get_info(rs.camera_info.name)
    is_dds = dev.supports(rs.camera_info.connection_type) and \
             dev.get_info(rs.camera_info.connection_type) == "DDS"
    
    # Set maximum delays
    max_delay_depth = 1
    max_delay_color = 1
    
    # Check if device has color sensor
    has_color = not any(model in product_name for model in ['D421', 'D405', 'D430'])
    
    return {
        'dev': dev,
        'ctx': ctx,
        'product_line': product_line,
        'product_name': product_name,
        'is_dds': is_dds,
        'max_delay_depth': max_delay_depth,
        'max_delay_color': max_delay_color,
        'has_color': has_color,
        'platform': platform.system()
    }


# ============================================================================
# Tests
# ============================================================================

def test_device_creation_time(test_context):
    """
    Test that device creation time does not exceed maximum allowed time.
    
    DDS devices are allowed up to 5 seconds, regular USB devices up to 1 second.
    """
    device_creation_stopwatch = Stopwatch()
    
    # Create context and query devices
    ctx = rs.context({"dds": {"enabled": False}})
    devs = ctx.devices
    
    if len(devs) == 0:
        # No devices found, try with DDS enabled
        device_creation_stopwatch.reset()
        ctx = rs.context({"dds": {"enabled": True}})
        devs = ctx.devices
    
    assert len(devs) > 0, "No devices found"
    
    dev = devs[0]
    device_creation_time = device_creation_stopwatch.get_elapsed()
    
    # Determine max time based on connection type
    is_dds = dev.supports(rs.camera_info.connection_type) and \
             dev.get_info(rs.camera_info.connection_type) == "DDS"
    max_time_for_device_creation = 5 if is_dds else 1
    
    os_name = platform.system()
    log.i(f"Testing device creation time on {os_name} OS")
    log.i(f"Device creation time is: {device_creation_time:.3f} [sec] "
          f"max allowed is: {max_time_for_device_creation:.1f} [sec]")
    
    assert device_creation_time < max_time_for_device_creation, \
        f"Device creation time {device_creation_time:.3f}s exceeds maximum {max_time_for_device_creation:.1f}s"


def test_sensor_first_depth_frame_delay(device_config):
    """
    Test that time from sensor.open() to first depth frame arrival
    does not exceed the maximum allowed delay using sensor API.
    """
    dev = device_config['dev']
    product_line = device_config['product_line']
    max_delay = device_config['max_delay_depth']
    os_name = device_config['platform']
    
    log.i(f"Testing first depth frame delay on {product_line} device - {os_name} OS")
    
    # Get depth sensor and default profile
    ds = dev.first_depth_sensor()
    dp = next(p for p in ds.profiles 
              if p.fps() == 30
              and p.stream_type() == rs.stream.depth
              and p.format() == rs.format.z16
              and p.is_default())
    
    # Measure time to first frame
    frame_delay = time_to_first_frame(ds, dp, max_delay)
    
    log.i(f"Time until first depth frame is: {frame_delay:.3f} [sec] "
          f"max allowed is: {max_delay:.1f} [sec]")
    
    # Assert delay is within acceptable range
    assert frame_delay < max_delay, \
        f"Depth frame delay {frame_delay:.3f}s exceeds maximum {max_delay:.1f}s"


def test_sensor_first_color_frame_delay(device_config):
    """
    Test that time from sensor.open() to first color frame arrival
    does not exceed the maximum allowed delay using sensor API.
    
    Skipped for devices without a color sensor (D421, D405, D430).
    """
    # Skip if device has no color sensor
    if not device_config['has_color']:
        pytest.skip(f"Device {device_config['product_name']} has no color sensor")
    
    dev = device_config['dev']
    product_line = device_config['product_line']
    max_delay = device_config['max_delay_color']
    os_name = device_config['platform']
    
    log.i(f"Testing first color frame delay on {product_line} device - {os_name} OS")
    
    # Get color sensor and default profile
    try:
        cs = dev.first_color_sensor()
    except RuntimeError as e:
        pytest.fail(f"Failed to get color sensor: {e}")
    
    cp = next(p for p in cs.profiles
              if p.fps() == 30
              and p.stream_type() == rs.stream.color
              and p.format() == rs.format.rgb8
              and p.is_default())
    
    # Measure time to first frame
    frame_delay = time_to_first_frame(cs, cp, max_delay)
    
    log.i(f"Time until first color frame is: {frame_delay:.3f} [sec] "
          f"max allowed is: {max_delay:.1f} [sec]")
    
    # Assert delay is within acceptable range
    assert frame_delay < max_delay, \
        f"Color frame delay {frame_delay:.3f}s exceeds maximum {max_delay:.1f}s"
