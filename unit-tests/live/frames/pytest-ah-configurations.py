# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2023 RealSense, Inc. All Rights Reserved.

"""
Test various sensor configuration permutations for D585S (AH device).

This test verifies that different combinations of sensors can stream simultaneously
at the expected FPS without drops or performance issues. Tests multiple permutations
including depth, color, safety, occupancy, labeled point cloud, accel, and gyro.
"""

import pytest
import pyrealsense2 as rs
from rspy import log, tests_wrapper
import fps_helper

# Module-level markers
pytestmark = [
    pytest.mark.device("D585S"),
    pytest.mark.nightly,
    pytest.mark.live
]

# Configuration constants
VGA_RESOLUTION = (640, 360)
HD_RESOLUTION = (1280, 720)


def get_sensors_and_profiles(device):
    """
    Returns an array of pairs of (sensor, profile) for each of its profiles.
    
    Args:
        device: Device to get sensors and profiles from
        
    Returns:
        List of (sensor, profile) tuples
    """
    sensor_profiles_arr = []
    
    for sensor in device.query_sensors():
        profile = None
        
        if sensor.is_depth_sensor():
            if sensor.supports(rs.option.enable_auto_exposure):
                sensor.set_option(rs.option.enable_auto_exposure, 1)
            profile = fps_helper.get_profile(sensor, rs.stream.depth, VGA_RESOLUTION, 30)
            
        elif sensor.is_color_sensor():
            if sensor.supports(rs.option.enable_auto_exposure):
                sensor.set_option(rs.option.enable_auto_exposure, 1)
            if sensor.supports(rs.option.auto_exposure_priority):
                sensor.set_option(rs.option.auto_exposure_priority, 0)  # AE priority should be 0 for constant FPS
            profile = fps_helper.get_profile(sensor, rs.stream.color, HD_RESOLUTION, 30)
            
        elif sensor.is_motion_sensor():
            sensor_profiles_arr.append((sensor, fps_helper.get_profile(sensor, rs.stream.accel)))
            sensor_profiles_arr.append((sensor, fps_helper.get_profile(sensor, rs.stream.gyro)))
            
        elif sensor.is_safety_sensor():
            profile = fps_helper.get_profile(sensor, rs.stream.safety)
            
        elif sensor.name == "Depth Mapping Camera":
            sensor_profiles_arr.append((sensor, fps_helper.get_profile(sensor, rs.stream.labeled_point_cloud)))
            sensor_profiles_arr.append((sensor, fps_helper.get_profile(sensor, rs.stream.occupancy)))
        
        if profile is not None:
            sensor_profiles_arr.append((sensor, profile))
    
    return sensor_profiles_arr


@pytest.fixture(scope="module")
def device_config(module_test_device):
    """
    Module-scoped fixture that sets up and tears down the test device.
    """
    dev, ctx = module_test_device
    
    tests_wrapper.start_wrapper(dev)
    
    yield {'dev': dev, 'ctx': ctx}
    
    tests_wrapper.stop_wrapper(dev)


def test_ah_sensor_configurations(device_config):
    """
    Test various sensor configuration permutations on D585S device.
    
    This test:
    1. Gets all available sensor profiles from the device
    2. Tests multiple permutations of sensor combinations:
       - Depth + Color
       - Depth + Color + Safety
       - Depth + Color + Safety + Occupancy
       - Depth + Color + Safety + Labeled Point Cloud
       - Depth + Color + Accel + Gyro
    3. Verifies that each permutation streams at expected FPS
    4. Checks for frame drops and timing issues
    """
    dev = device_config['dev']
    
    log.i(f"Testing sensor configurations on {dev.get_info(rs.camera_info.name)}")
    
    # Get all sensor profiles
    sensor_profiles_array = get_sensors_and_profiles(dev)
    
    log.i(f"Found {len(sensor_profiles_array)} sensor/profile pairs")
    for sensor, profile in sensor_profiles_array:
        log.d(f"  {sensor.name}: {profile.stream_type()} @ {profile.fps()} FPS")
    
    # Define permutations to test
    permutations_to_run = [
        ["Depth", "Color"],
        ["Depth", "Color", "Safety"],
        ["Depth", "Color", "Safety", "Occupancy"],
        ["Depth", "Color", "Safety", "Labeled Point Cloud"],
        ["Depth", "Color", "Accel", "Gyro"]
    ]
    
    log.i(f"Testing {len(permutations_to_run)} configuration permutations")
    
    # Run FPS test for all permutations
    fps_helper.perform_fps_test(sensor_profiles_array, permutations_to_run)
    
    log.i("All configuration permutations tested successfully")
