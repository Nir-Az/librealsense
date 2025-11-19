# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2024 RealSense, Inc. All Rights Reserved.

"""
Test that verifies the relationship between hardware timestamp and sensor timestamp.
Tests both depth and color sensors by setting the time domain to hardware (HW) and
validating that the hardware timestamp occurs right before the sensor timestamp.
"""

import pytest
import pyrealsense2 as rs
import time

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
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


def test_depth_sensor_hw_vs_sensor_timestamp(device_config):
    """
    Test that hardware timestamp is right before sensor timestamp for depth frames.
    
    This test:
    1. Sets the depth sensor time domain to hardware (HW)
    2. Captures depth frames and validates timestamp relationship
    3. Verifies hw_ts is between sensor_ts and sensor_ts + time_between_frames
    4. Restores original time domain setting
    """
    dev = device_config['dev']
    depth_sensor = dev.first_depth_sensor()
    
    # Save original time domain setting
    is_global_time_enabled_orig = depth_sensor.get_option(rs.option.global_time_enabled)
    
    try:
        # Set time domain to HW
        if is_global_time_enabled_orig:
            depth_sensor.set_option(rs.option.global_time_enabled, 0)
        
        assert int(depth_sensor.get_option(rs.option.global_time_enabled)) == 0, \
            "Failed to set depth sensor time domain to HW"
        
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
            
            # Check metadata support
            frame_ts_supported = frame.supports_frame_metadata(rs.frame_metadata_value.frame_timestamp)
            sensor_ts_supported = frame.supports_frame_metadata(rs.frame_metadata_value.sensor_timestamp)
            
            if not (frame_ts_supported and sensor_ts_supported):
                validation_errors.append("Frame or sensor timestamp metadata not supported")
                return
            
            # Get timestamps
            hw_ts = frame.get_frame_metadata(rs.frame_metadata_value.frame_timestamp)
            sensor_ts = frame.get_frame_metadata(rs.frame_metadata_value.sensor_timestamp)
            delta = hw_ts - sensor_ts
            time_between_frames = 1 / FPS * 1000000
            
            # Validate: hw_ts should be right before sensor_ts (within one frame time)
            if not (0 <= delta <= time_between_frames):
                validation_errors.append(
                    f"Timestamp delta out of range: hw_ts={hw_ts}, sensor_ts={sensor_ts}, "
                    f"delta={delta}, expected range=[0, {time_between_frames}]"
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
        if is_global_time_enabled_orig:
            depth_sensor.set_option(rs.option.global_time_enabled, 1)
        
        # Verify restoration
        current_setting = int(depth_sensor.get_option(rs.option.global_time_enabled))
        assert current_setting == int(is_global_time_enabled_orig), \
            f"Failed to restore depth sensor time domain (expected {int(is_global_time_enabled_orig)}, got {current_setting})"


def test_color_sensor_hw_vs_sensor_timestamp(device_config):
    """
    Test that hardware timestamp is right before sensor timestamp for color frames.
    
    This test:
    1. Sets the color sensor time domain to hardware (HW)
    2. Captures color frames and validates timestamp relationship
    3. Verifies hw_ts is between sensor_ts and sensor_ts + time_between_frames
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
        # Set time domain to HW
        if is_global_time_enabled_orig:
            color_sensor.set_option(rs.option.global_time_enabled, 0)
        
        assert int(color_sensor.get_option(rs.option.global_time_enabled)) == 0, \
            "Failed to set color sensor time domain to HW"
        
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
            
            # Check metadata support
            frame_ts_supported = frame.supports_frame_metadata(rs.frame_metadata_value.frame_timestamp)
            sensor_ts_supported = frame.supports_frame_metadata(rs.frame_metadata_value.sensor_timestamp)
            
            if not (frame_ts_supported and sensor_ts_supported):
                validation_errors.append("Frame or sensor timestamp metadata not supported")
                return
            
            # Get timestamps
            hw_ts = frame.get_frame_metadata(rs.frame_metadata_value.frame_timestamp)
            sensor_ts = frame.get_frame_metadata(rs.frame_metadata_value.sensor_timestamp)
            delta = hw_ts - sensor_ts
            time_between_frames = 1 / FPS * 1000000
            
            # Validate: hw_ts should be right before sensor_ts (within one frame time)
            if not (0 <= delta <= time_between_frames):
                validation_errors.append(
                    f"Timestamp delta out of range: hw_ts={hw_ts}, sensor_ts={sensor_ts}, "
                    f"delta={delta}, expected range=[0, {time_between_frames}]"
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
        if is_global_time_enabled_orig:
            color_sensor.set_option(rs.option.global_time_enabled, 1)
        
        # Verify restoration
        current_setting = int(color_sensor.get_option(rs.option.global_time_enabled))
        assert current_setting == int(is_global_time_enabled_orig), \
            f"Failed to restore color sensor time domain (expected {int(is_global_time_enabled_orig)}, got {current_setting})"
