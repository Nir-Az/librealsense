# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2021 RealSense, Inc. All Rights Reserved.

"""
Depth Units Test

Verifies depth units metadata value matches the depth sensor option value.
"""

import pytest
import pyrealsense2 as rs

# Module-level markers
pytestmark = [
    pytest.mark.device("D400*"),
    pytest.mark.device("D500*", exclude="D555"),
    pytest.mark.live
]


def test_depth_unit(test_device):
    """Check depth units on metadata matches sensor option."""
    dev, ctx = test_device
    depth_sensor = dev.first_depth_sensor()
    assert depth_sensor, "No depth sensor found"
    
    pipe = rs.pipeline(ctx)
    cfg = rs.config()
    
    try:
        profile = pipe.start(cfg)
        
        # Get depth frame and check metadata depth units
        frameset = pipe.wait_for_frames()
        depth_frame = frameset.get_depth_frame()
        assert depth_frame, "No depth frame received"
        
        depth_units_from_metadata = depth_frame.get_units()
        assert depth_units_from_metadata > 0, \
            f"Depth units should be positive, got {depth_units_from_metadata}"
        
        # Check metadata depth unit value matches option value
        device = profile.get_device()
        ds = device.first_depth_sensor()
        
        assert ds.supports(rs.option.depth_units), \
            "Depth sensor should support depth_units option"
        
        depth_units_from_option = ds.get_option(rs.option.depth_units)
        assert depth_units_from_metadata == depth_units_from_option, \
            f"Depth units mismatch: metadata={depth_units_from_metadata}, option={depth_units_from_option}"
    
    finally:
        pipe.stop()
