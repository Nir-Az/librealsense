# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
HDR Configurations Test

Tests various HDR configurations with different resolutions and modes.
Platform-aware: Uses D457 on Jetson, D455 on Windows/Linux.
"""

import pytest
import pyrealsense2 as rs
from conftest import is_jetson_platform
import json

# Import helper functions and configurations
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from hdr_helper import load_and_perform_test, HDR_CONFIGURATIONS, MANUAL_HDR_CONFIG_1

# Platform-aware device marker
_device_pattern = "D457" if is_jetson_platform() else "D455"

pytestmark = [
    pytest.mark.device(_device_pattern),
    pytest.mark.nightly,
    pytest.mark.live
]

# Different depth resolutions to test
DEPTH_RESOLUTIONS = [
    (640, 480),
    (848, 480),
    (1280, 720),
]


@pytest.fixture
def hdr_context(test_device):
    """Setup HDR test environment."""
    dev, ctx = test_device
    am = rs.rs400_advanced_mode(dev)
    sensor = dev.first_depth_sensor()
    pipe = rs.pipeline(ctx)
    
    # Initialize helper module globals
    import hdr_helper
    hdr_helper.device = dev
    hdr_helper.ctx = ctx
    hdr_helper.am = am
    hdr_helper.sensor = sensor
    hdr_helper.pipe = pipe
    hdr_helper.batch_size = 0
    
    yield dev, ctx, am, sensor, pipe
    
    # Cleanup
    try:
        pipe.stop()
    except:
        pass


@pytest.mark.parametrize("config_idx", range(len(HDR_CONFIGURATIONS)))
@pytest.mark.parametrize("resolution", DEPTH_RESOLUTIONS)
def test_hdr_configuration(hdr_context, config_idx, resolution):
    """Test HDR configuration with different resolutions."""
    dev, ctx, am, sensor, pipe = hdr_context
    
    config = HDR_CONFIGURATIONS[config_idx]
    config_type = "Auto" if "depth-ae" in json.dumps(config) else "Manual"
    num_items = len(config["hdr-preset"]["items"])
    resolution_name = f"{resolution[0]}x{resolution[1]}"
    test_name = f"Config {config_idx + 1} ({config_type}, {num_items} items) @ {resolution_name}"
    
    load_and_perform_test(config, test_name, resolution)


def test_disable_auto_hdr(hdr_context):
    """Test disabling Auto-HDR and returning to default behavior."""
    dev, ctx, am, sensor, pipe = hdr_context
    
    cfg = rs.config()
    
    # First enable HDR
    am.load_json(json.dumps(MANUAL_HDR_CONFIG_1))
    assert sensor.get_option(rs.option.hdr_enabled) == 1, "HDR should be enabled"
    
    # Disable HDR
    sensor.set_option(rs.option.hdr_enabled, 0)
    assert sensor.get_option(rs.option.hdr_enabled) == 0, "HDR should be disabled"
    
    # Verify we're back to default single-frame behavior
    cfg.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
    pipe.start(cfg)
    
    for i in range(30):
        data = pipe.wait_for_frames()
        depth_frame = data.get_depth_frame()
        
        # In default mode, sequence size should be 0
        seq_size = depth_frame.get_frame_metadata(rs.frame_metadata_value.sequence_size)
        assert seq_size == 0, f"Frame {i}: Expected sequence size 0 in default mode, got {seq_size}"
        
        # Sequence ID should always be 0 in single-frame mode
        seq_id = depth_frame.get_frame_metadata(rs.frame_metadata_value.sequence_id)
        assert seq_id == 0, f"Frame {i}: Expected sequence ID 0 in default mode, got {seq_id}"
    
    pipe.stop()
    cfg.disable_all_streams()
