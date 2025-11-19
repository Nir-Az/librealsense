# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
Test that backend timestamp is greater than frame timestamp.

This test verifies the relationship between frame timestamp and backend timestamp
for both depth and color sensors. Backend timestamp should always be greater than
frame timestamp as it represents when the frame was received by the backend,
which occurs after the frame was captured.
"""

import pytest
import pyrealsense2 as rs
from rspy import log
import time

# Module-level markers
pytestmark = [
    pytest.mark.device("D400*"),
    pytest.mark.device_exclude("D457"),
    pytest.mark.live
]

FPS = 30


@pytest.fixture(scope="module")
def device_config(module_test_device):
    """
    Module-scoped fixture that provides device and context for all tests.
    """
    dev, ctx = module_test_device
    return {'dev': dev, 'ctx': ctx}


def test_depth_sensor_backend_vs_frame_timestamp(device_config):
    """
    Test that backend timestamp is greater than frame timestamp for depth frames.
    
    This test:
    1. Sets the depth sensor time domain to Global
    2. Captures depth frames and validates timestamp relationship
    3. Verifies backend_ts > frame_ts (backend receives frames after capture)
    4. Restores original time domain setting
    """
    dev = device_config['dev']
    depth_sensor = dev.first_depth_sensor()
    
    # Save original time domain setting
    is_global_time_enabled_orig = depth_sensor.get_option(rs.option.global_time_enabled)
    
    try:
        # Set time domain to Global
        if not is_global_time_enabled_orig:
            depth_sensor.set_option(rs.option.global_time_enabled, 1)
        
        assert int(depth_sensor.get_option(rs.option.global_time_enabled)) == 1, \
            "Failed to set depth sensor time domain to Global"
        
        # Find depth profile
        depth_profile = next(
            (p for p in depth_sensor.profiles 
             if p.fps() == FPS
             and p.stream_type() == rs.stream.depth
             and p.format() == rs.format.z16
             and p.as_video_stream_profile().width() == 1280
             and p.as_video_stream_profile().height() == 720),
            None
        )
        assert depth_profile is not None, "Could not find suitable depth profile"
        
        # Capture and validate frames
        has_frame = False
        validation_errors = []
        
        def check_timestamps(frame):
            nonlocal has_frame, validation_errors
            has_frame = True
            
            # Check backend timestamp support
            backend_ts_supported = frame.supports_frame_metadata(rs.frame_metadata_value.backend_timestamp)
            
            if not backend_ts_supported:
                validation_errors.append("Backend timestamp metadata not supported")
                return
            
            # Get timestamps
            frame_ts = frame.get_frame_timestamp()
            backend_ts = frame.get_frame_metadata(rs.frame_metadata_value.backend_timestamp)
            delta = backend_ts - frame_ts
            
            # Validate: backend_ts should be greater than frame_ts
            if delta <= 0:
                validation_errors.append(
                    f"Backend timestamp not greater than frame timestamp: "
                    f"frame_ts={frame_ts}, backend_ts={backend_ts}, delta={delta} (should be positive)"
                )
        
        depth_sensor.open(depth_profile)
        depth_sensor.start(check_timestamps)
        time.sleep(1)
        depth_sensor.stop()
        depth_sensor.close()
        
        # Verify results
        assert has_frame, "No frames arrived during test"
        assert len(validation_errors) == 0, f"Timestamp validation errors: {'; '.join(validation_errors)}"
        
    finally:
        # Restore original time domain setting
        if not is_global_time_enabled_orig:
            depth_sensor.set_option(rs.option.global_time_enabled, 0)
        
        # Verify restoration
        expected_val = 1 if is_global_time_enabled_orig else 0
        current_setting = int(depth_sensor.get_option(rs.option.global_time_enabled))
        assert current_setting == expected_val, \
            f"Failed to restore depth sensor time domain (expected {expected_val}, got {current_setting})"


def test_color_sensor_backend_vs_frame_timestamp(device_config):
    """
    Test that backend timestamp is greater than frame timestamp for color frames.
    
    This test:
    1. Sets the color sensor time domain to Global
    2. Captures color frames and validates timestamp relationship
    3. Verifies backend_ts > frame_ts (backend receives frames after capture)
    4. Restores original time domain setting
    """
    dev = device_config['dev']
    
    # Check if device has color sensor
    try:
        color_sensor = dev.first_color_sensor()
    except StopIteration:
        pytest.skip("Device does not have a color sensor")
    
    # Save original time domain setting
    is_global_time_enabled_orig = color_sensor.get_option(rs.option.global_time_enabled)
    
    try:
        # Set time domain to Global
        if not is_global_time_enabled_orig:
            color_sensor.set_option(rs.option.global_time_enabled, 1)
        
        assert int(color_sensor.get_option(rs.option.global_time_enabled)) == 1, \
            "Failed to set color sensor time domain to Global"
        
        # Find color profile
        color_profile = next(
            (p for p in color_sensor.profiles 
             if p.fps() == FPS
             and p.stream_type() == rs.stream.color
             and p.format() == rs.format.rgb8
             and p.as_video_stream_profile().width() == 1280
             and p.as_video_stream_profile().height() == 720),
            None
        )
        assert color_profile is not None, "Could not find suitable color profile"
        
        # Capture and validate frames
        has_frame = False
        validation_errors = []
        
        def check_timestamps(frame):
            nonlocal has_frame, validation_errors
            has_frame = True
            
            # Check backend timestamp support
            backend_ts_supported = frame.supports_frame_metadata(rs.frame_metadata_value.backend_timestamp)
            
            if not backend_ts_supported:
                validation_errors.append("Backend timestamp metadata not supported")
                return
            
            # Get timestamps
            frame_ts = frame.get_frame_timestamp()
            backend_ts = frame.get_frame_metadata(rs.frame_metadata_value.backend_timestamp)
            delta = backend_ts - frame_ts
            
            # Validate: backend_ts should be greater than frame_ts
            if delta <= 0:
                validation_errors.append(
                    f"Backend timestamp not greater than frame timestamp: "
                    f"frame_ts={frame_ts}, backend_ts={backend_ts}, delta={delta} (should be positive)"
                )
        
        color_sensor.open(color_profile)
        color_sensor.start(check_timestamps)
        time.sleep(1)
        color_sensor.stop()
        color_sensor.close()
        
        # Verify results
        assert has_frame, "No frames arrived during test"
        assert len(validation_errors) == 0, f"Timestamp validation errors: {'; '.join(validation_errors)}"
        
    finally:
        # Restore original time domain setting
        if not is_global_time_enabled_orig:
            color_sensor.set_option(rs.option.global_time_enabled, 0)
        
        # Verify restoration
        expected_val = 1 if is_global_time_enabled_orig else 0
        current_setting = int(color_sensor.get_option(rs.option.global_time_enabled))
        assert current_setting == expected_val, \
            f"Failed to restore color sensor time domain (expected {expected_val}, got {current_setting})"
