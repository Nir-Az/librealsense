# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
HDR Performance Test

Tests HDR performance with various configurations to ensure FPS meets requirements.
Platform-aware: Uses D457 on Jetson, D455 on Windows/Linux.
"""

import pytest
import pyrealsense2 as rs
from conftest import is_jetson_platform
import json
import time

# Import helper functions and configurations
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from hdr_helper import verify_json_load, HDR_CONFIGURATIONS

# Platform-aware device marker
_device_pattern = "D457" if is_jetson_platform() else "D455"

pytestmark = [
    pytest.mark.device(_device_pattern),
    pytest.mark.nightly,
    pytest.mark.live
]

EXPECTED_FPS = 30
ACCEPTABLE_FPS = EXPECTED_FPS * 0.9
TIME_FOR_STEADY_STATE = 3
TIME_TO_COUNT_FRAMES = 5


class FrameCounter:
    """Helper class to count frames via callback."""
    def __init__(self):
        self.count = 0
        self.count_frames = False
    
    def callback(self, frame):
        if not self.count_frames:
            return
        self.count += 1
    
    def reset(self):
        self.count = 0
        self.count_frames = False


@pytest.fixture
def hdr_context(test_device):
    """Setup HDR test environment."""
    dev, ctx = test_device
    am = rs.rs400_advanced_mode(dev)
    sensor = dev.first_depth_sensor()
    
    # Initialize helper module globals
    import hdr_helper
    hdr_helper.device = dev
    hdr_helper.ctx = ctx
    hdr_helper.am = am
    hdr_helper.sensor = sensor
    hdr_helper.batch_size = 0
    
    yield dev, ctx, am, sensor
    
    # Cleanup
    try:
        sensor.stop()
        sensor.close()
    except:
        pass


@pytest.mark.parametrize("config_idx", range(len(HDR_CONFIGURATIONS)))
def test_hdr_performance(hdr_context, config_idx):
    """Test HDR performance with various configurations."""
    dev, ctx, am, sensor = hdr_context
    
    config = HDR_CONFIGURATIONS[config_idx]
    config_type = "Auto" if "depth-ae" in json.dumps(config) else "Manual"
    num_items = len(config["hdr-preset"]["items"])
    test_name = f"Config {config_idx + 1} ({config_type}, {num_items} items)"
    
    # Load configuration and get batch size
    import hdr_helper
    hdr_helper.verify_json_load(config, test_name)
    batch_size = hdr_helper.batch_size
    
    # Setup frame counter
    counter = FrameCounter()
    
    # Start streaming with callback
    depth_profile = next(p for p in sensor.get_stream_profiles() 
                        if p.stream_type() == rs.stream.depth)
    sensor.open(depth_profile)
    sensor.start(counter.callback)
    
    # Wait for steady state
    time.sleep(TIME_FOR_STEADY_STATE)
    
    # Count frames
    counter.count_frames = True
    time.sleep(TIME_TO_COUNT_FRAMES)
    counter.count_frames = False
    
    # Stop streaming
    sensor.stop()
    sensor.close()
    
    # Calculate and verify FPS
    measured_fps = counter.count / TIME_TO_COUNT_FRAMES
    
    assert measured_fps > ACCEPTABLE_FPS, \
        f"FPS too low for {test_name}: {measured_fps:.2f} < {ACCEPTABLE_FPS:.2f}"
