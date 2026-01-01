# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2021 RealSense, Inc. All Rights Reserved.

"""
Test time-to-first-frame for pipeline API.

This test measures the time from pipeline.start() until the first frame arrives
for both depth and color streams. It verifies that the startup time does not exceed
the maximum allowed delay.

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
# Test Fixtures and Setup
# ============================================================================

@pytest.fixture
def device_config(module_test_device):
    """
    Set up device and determine maximum allowed delays based on product line.
    """
    dev, ctx = module_test_device
    
    # The device starts at D0 (Operational) state, allow time for it to get into idle state
    time.sleep(3)
    
    product_line = dev.get_info(rs.camera_info.product_line)
    product_name = dev.get_info(rs.camera_info.name)
    
    # Set maximum delay for first frame according to product line
    if product_line == "D400":
        max_delay_depth = 1
        max_delay_color = 1
    elif product_line == "D500":
        max_delay_depth = 1
        max_delay_color = 1
    else:
        pytest.fail(f"Not supported product line: {product_line}")
    
    # Check if device has color sensor
    has_color = not any(model in product_name for model in ['D421', 'D405', 'D430'])
    
    return {
        'dev': dev,
        'ctx': ctx,
        'product_line': product_line,
        'product_name': product_name,
        'max_delay_depth': max_delay_depth,
        'max_delay_color': max_delay_color,
        'has_color': has_color,
        'platform': platform.system()
    }


def time_to_first_frame(ctx, config):
    """
    Measure time from pipeline.start() to first frame arrival.
    
    Args:
        ctx: RealSense context
        config: Pipeline configuration
        
    Returns:
        Elapsed time in seconds
    """
    pipe = rs.pipeline(ctx)
    start_call_stopwatch = Stopwatch()
    pipe.start(config)
    pipe.wait_for_frames()
    delay = start_call_stopwatch.get_elapsed()
    pipe.stop()
    return delay


# ============================================================================
# Tests
# ============================================================================

def test_pipeline_first_depth_frame_delay(device_config):
    """
    Test that the time from pipeline.start() to first depth frame arrival
    does not exceed the maximum allowed delay.
    """
    ctx = device_config['ctx']
    product_line = device_config['product_line']
    max_delay = device_config['max_delay_depth']
    os_name = device_config['platform']
    
    log.i(f"Testing pipeline first depth frame delay on {product_line} device - {os_name} OS")
    
    # Configure depth stream
    depth_cfg = rs.config()
    depth_cfg.enable_stream(rs.stream.depth, rs.format.z16, 30)
    
    # Measure delay
    frame_delay = time_to_first_frame(ctx, depth_cfg)
    
    log.i(f"Delay from pipeline.start() until first depth frame is: {frame_delay:.3f} [sec] "
          f"max allowed is: {max_delay:.1f} [sec]")
    
    # Assert delay is within acceptable range
    assert frame_delay < max_delay, \
        f"Depth frame delay {frame_delay:.3f}s exceeds maximum {max_delay:.1f}s"


def test_pipeline_first_color_frame_delay(device_config):
    """
    Test that the time from pipeline.start() to first color frame arrival
    does not exceed the maximum allowed delay.
    
    Skipped for devices without a color sensor (D421, D405, D430).
    """
    # Skip if device has no color sensor
    if not device_config['has_color']:
        pytest.skip(f"Device {device_config['product_name']} has no color sensor")
    
    ctx = device_config['ctx']
    product_line = device_config['product_line']
    max_delay = device_config['max_delay_color']
    os_name = device_config['platform']
    
    log.i(f"Testing pipeline first color frame delay on {product_line} device - {os_name} OS")
    
    # Configure color stream
    color_cfg = rs.config()
    color_cfg.enable_stream(rs.stream.color, rs.format.rgb8, 30)
    
    # Measure delay
    frame_delay = time_to_first_frame(ctx, color_cfg)
    
    log.i(f"Delay from pipeline.start() until first color frame is: {frame_delay:.3f} [sec] "
          f"max allowed is: {max_delay:.1f} [sec]")
    
    # Assert delay is within acceptable range
    assert frame_delay < max_delay, \
        f"Color frame delay {frame_delay:.3f}s exceeds maximum {max_delay:.1f}s"
