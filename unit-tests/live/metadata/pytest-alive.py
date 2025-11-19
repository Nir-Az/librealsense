# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2023 RealSense, Inc. All Rights Reserved.

"""
Metadata Alive Test

Tests that metadata values (frame counter, timestamps) are properly increasing.
Tests all default profiles for each sensor.
"""

import pytest
import pyrealsense2 as rs
import time

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.nightly,
    pytest.mark.live
]

QUEUE_CAPACITY = 1
FRAMES_TO_TEST = 50


def is_contain_profile(profiles: dict, new_profile) -> bool:
    """
    Check if a given stream type exists in a dictionary.
    
    Args:
        profiles: Dictionary of profiles and sensors
        new_profile: Profile to check
    
    Returns:
        True if profile type already exists
    """
    if new_profile:
        for pr in profiles.keys():
            if pr.stream_type() == new_profile.stream_type():
                return True
    return False


def append_testing_profiles(dev) -> dict:
    """
    Fill dictionary of testing profiles and their sensors.
    Only picks default profiles to avoid unsupported configurations.
    
    Args:
        dev: RealSense device
    
    Returns:
        Dictionary mapping profiles to their sensors
    """
    testing_profiles = {}
    for s in dev.sensors:
        for p in s.profiles:
            if not is_contain_profile(testing_profiles, p) and p.is_default():
                testing_profiles[p] = s
    return testing_profiles


def verify_metadata_increasing(frame_queue, metadata_type, frames_to_test=FRAMES_TO_TEST):
    """
    Verify that metadata values keep increasing.
    
    Args:
        frame_queue: Queue to pull frames from
        metadata_type: Metadata type to check
        frames_to_test: Number of frames to verify
    """
    prev_value = -1
    
    for _ in range(frames_to_test):
        f = frame_queue.wait_for_frame()
        current_value = f.get_frame_metadata(metadata_type)
        
        assert prev_value < current_value, \
            f"Metadata {metadata_type} not increasing: prev={prev_value}, current={current_value}"
        
        prev_value = current_value


def verify_metadata_different(frame_queue, metadata_type_1, metadata_type_2, frames_to_test=FRAMES_TO_TEST):
    """
    Verify that two metadata types have different values.
    
    Args:
        frame_queue: Queue to pull frames from
        metadata_type_1: First metadata type
        metadata_type_2: Second metadata type
        frames_to_test: Number of frames to verify
    """
    for _ in range(frames_to_test):
        f = frame_queue.wait_for_frame()
        value_1 = f.get_frame_metadata(metadata_type_1)
        value_2 = f.get_frame_metadata(metadata_type_2)
        
        assert value_1 != value_2, \
            f"Metadata values should differ: {metadata_type_1}={value_1}, {metadata_type_2}={value_2}"


def test_metadata_alive(test_device):
    """Test metadata values are properly updating for all default profiles."""
    dev, ctx = test_device
    
    testing_profiles = append_testing_profiles(dev)
    assert testing_profiles, "No default profiles found"
    
    camera_name = dev.get_info(rs.camera_info.name)
    
    for profile, sensor in testing_profiles.items():
        frame_queue = rs.frame_queue(QUEUE_CAPACITY)
        
        try:
            sensor.open(profile)
            sensor.start(frame_queue)
            
            # Wait for first frame to check metadata support
            first_frame = frame_queue.wait_for_frame()
            
            # Test #1: Increasing frame counter
            if first_frame.supports_frame_metadata(rs.frame_metadata_value.frame_counter):
                verify_metadata_increasing(frame_queue, rs.frame_metadata_value.frame_counter)
            
            # Test #2: Increasing frame timestamp
            if first_frame.supports_frame_metadata(rs.frame_metadata_value.frame_timestamp):
                verify_metadata_increasing(frame_queue, rs.frame_metadata_value.frame_timestamp)
            
            # Test #3: Increasing sensor timestamp
            if first_frame.supports_frame_metadata(rs.frame_metadata_value.sensor_timestamp):
                verify_metadata_increasing(frame_queue, rs.frame_metadata_value.sensor_timestamp)
                
                # On D457, sensor timestamp == frame timestamp, so we skip this check
                if 'D457' not in camera_name:
                    if first_frame.supports_frame_metadata(rs.frame_metadata_value.frame_timestamp):
                        verify_metadata_different(
                            frame_queue,
                            rs.frame_metadata_value.frame_timestamp,
                            rs.frame_metadata_value.sensor_timestamp
                        )
        
        finally:
            if len(sensor.get_active_streams()) > 0:
                sensor.stop()
                sensor.close()
            
            # Better sleep before stopping/starting streaming for device recovery
            time.sleep(1)
