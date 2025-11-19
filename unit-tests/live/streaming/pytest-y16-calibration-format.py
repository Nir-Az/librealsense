# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2023 RealSense, Inc. All Rights Reserved.

"""
Y16 Calibration Format Test

Tests Y16 format streaming on depth sensors.
Verifies that Y16 profiles can be streamed successfully.

Note: Disables D457 until driver issue RSDSO-20168 is resolved.
"""

import pytest
import pyrealsense2 as rs
import time

# Module-level markers
pytestmark = [
    pytest.mark.device("D400*", exclude="D457"),
    pytest.mark.device_each("D555"),
    pytest.mark.live
]


def test_y16_streaming(test_device):
    """Test that Y16 format can be streamed from depth sensor."""
    dev, ctx = test_device
    depth_sensor = dev.first_depth_sensor()
    
    # Find Y16 profile
    profile_y16 = None
    for p in depth_sensor.profiles:
        if p.format() == rs.format.y16:
            profile_y16 = p
            break
    
    assert profile_y16, "Device should support Y16 format"
    
    # Track if we received Y16 frames
    y16_received = []
    
    def frame_callback(frame):
        if frame.get_profile().format() == rs.format.y16:
            y16_received.append(True)
    
    try:
        depth_sensor.open(profile_y16)
        depth_sensor.start(frame_callback)
        
        # Wait up to 5 seconds for Y16 frame
        timeout = 5.0
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if y16_received:
                break
            time.sleep(0.1)
        
        assert y16_received, "Should receive at least one Y16 frame within 5 seconds"
    
    finally:
        if len(depth_sensor.get_active_streams()) > 0:
            depth_sensor.stop()
            depth_sensor.close()
