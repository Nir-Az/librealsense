# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2023 RealSense, Inc. All Rights Reserved.

"""
Motion Intrinsics Test

Tests existence of motion intrinsic data in accel and gyro profiles.
Handles both separate accel/gyro streams and combined motion stream (D555).
"""

import pytest
import pyrealsense2 as rs
from conftest import is_jetson_platform

# Module-level markers - platform-aware device selection
_device_pattern = "D457" if is_jetson_platform() else "D455"
pytestmark = [
    pytest.mark.device(_device_pattern),
    pytest.mark.device_each("D500*"),
    pytest.mark.live
]


def test_motion_intrinsics(test_device):
    """Check intrinsics in motion sensor."""
    dev, ctx = test_device
    
    motion_sensor = dev.first_motion_sensor()
    assert motion_sensor, "No motion sensor found"
    
    # Check if device uses combined motion stream (D555) or separate accel/gyro streams
    stream_types = [p.stream_type() for p in motion_sensor.profiles]
    
    if rs.stream.motion in stream_types:
        # D555 uses combined motion stream
        motion_profile = next(p for p in motion_sensor.profiles if p.stream_type() == rs.stream.motion)
        motion_profiles = [motion_profile]
    else:
        # Separate accel and gyro streams
        motion_profile_accel = next((p for p in motion_sensor.profiles if p.stream_type() == rs.stream.accel), None)
        motion_profile_gyro = next((p for p in motion_sensor.profiles if p.stream_type() == rs.stream.gyro), None)
        
        assert motion_profile_accel and motion_profile_gyro, \
            "Both accel and gyro profiles required"
        
        motion_profiles = [motion_profile_accel, motion_profile_gyro]
    
    # Verify intrinsics exist for all motion profiles
    for motion_profile in motion_profiles:
        motion_profile = motion_profile.as_motion_stream_profile()
        intrinsics = motion_profile.get_motion_intrinsics()
        
        intrinsics_str = str(intrinsics)
        assert len(intrinsics_str) > 0, \
            f"Motion intrinsics data missing for {motion_profile.stream_type()}"
