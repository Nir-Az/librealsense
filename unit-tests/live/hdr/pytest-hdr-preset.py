# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
HDR Preset Test

Tests HDR presets with manual and auto configurations.
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
from hdr_helper import load_and_perform_test

# Platform-aware device marker
_device_pattern = "D457" if is_jetson_platform() else "D455"

pytestmark = [
    pytest.mark.device(_device_pattern),
    pytest.mark.live
]

MANUAL_HDR_CONFIG = {
    "hdr-preset": {
        "id": "0",
        "iterations": "0",
        "items": [
            {"iterations": "1", "controls": {"depth-gain": "16", "depth-exposure": "1"}},
            {"iterations": "2", "controls": {"depth-gain": "61", "depth-exposure": "10"}},
            {"iterations": "1", "controls": {"depth-gain": "116", "depth-exposure": "100"}},
            {"iterations": "3", "controls": {"depth-gain": "161", "depth-exposure": "1000"}},
            {"iterations": "1", "controls": {"depth-gain": "22", "depth-exposure": "10000"}},
            {"iterations": "2", "controls": {"depth-gain": "222", "depth-exposure": "4444"}},
        ]
    }
}

AUTO_HDR_CONFIG = {
    "hdr-preset": {
        "id": "0",
        "iterations": "0",
        "items": [
            {"iterations": "1", "controls": {"depth-ae": "1"}},
            {"iterations": "2", "controls": {"depth-ae-exp": "2000", "depth-ae-gain": "30"}},
            {"iterations": "2", "controls": {"depth-ae-exp": "-2000", "depth-ae-gain": "20"}},
            {"iterations": "3", "controls": {"depth-ae-exp": "3000", "depth-ae-gain": "10"}},
            {"iterations": "3", "controls": {"depth-ae-exp": "-3000", "depth-ae-gain": "40"}},
        ]
    }
}


@pytest.fixture
def hdr_context(test_device):
    """Setup HDR test environment."""
    dev, ctx = test_device
    am = rs.rs400_advanced_mode(dev)
    sensor = dev.first_depth_sensor()
    pipe = rs.pipeline(ctx)
    
    yield dev, ctx, am, sensor, pipe
    
    # Cleanup
    try:
        pipe.stop()
    except:
        pass


def test_manual_hdr_preset(hdr_context):
    """Test HDR with manual mode configuration."""
    dev, ctx, am, sensor, pipe = hdr_context
    
    # Use helper to load and test
    import hdr_helper
    hdr_helper.device = dev
    hdr_helper.ctx = ctx
    hdr_helper.am = am
    hdr_helper.sensor = sensor
    hdr_helper.pipe = pipe
    hdr_helper.batch_size = 0
    
    load_and_perform_test(MANUAL_HDR_CONFIG, "Auto HDR - Sanity - Manual mode")


def test_auto_hdr_preset(hdr_context):
    """Test HDR with auto mode configuration."""
    dev, ctx, am, sensor, pipe = hdr_context
    
    # Use helper to load and test
    import hdr_helper
    hdr_helper.device = dev
    hdr_helper.ctx = ctx
    hdr_helper.am = am
    hdr_helper.sensor = sensor
    hdr_helper.pipe = pipe
    hdr_helper.batch_size = 0
    
    load_and_perform_test(AUTO_HDR_CONFIG, "Auto HDR - Sanity - Auto mode")
