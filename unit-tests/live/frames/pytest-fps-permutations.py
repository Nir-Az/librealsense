# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2023 RealSense, Inc. All Rights Reserved.

"""
Test FPS accuracy for various sensor stream combinations (permutations).

This test verifies that different pairs of sensor streams can run simultaneously
at the expected FPS without interference. Tests all pair-wise combinations of
available streams (depth, IR, color, accel, gyro, motion).
"""

import pytest
import pyrealsense2 as rs
from rspy import log
from itertools import combinations
import fps_helper

# Module-level markers
pytestmark = [
    pytest.mark.device("D400*"),
    pytest.mark.device_exclude("D457"),
    pytest.mark.nightly,
    pytest.mark.timeout(300),
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
            
            depth_resolutions = []
            for p in sensor.get_stream_profiles():
                res = fps_helper.get_resolution(p)
                if res not in depth_resolutions:
                    depth_resolutions.append(res)
            
            for res in depth_resolutions:
                # Skip 1280x800 resolution for infrared since it's Y16 calibration format
                if res == (1280, 800):
                    log.d(f"Skipping resolution {res} for infrared (calibration format)")
                    continue
                
                depth = fps_helper.get_profile(sensor, rs.stream.depth, res)
                irs = fps_helper.get_profiles(sensor, rs.stream.infrared, res)
                ir = next(irs)
                while ir is not None and ir.stream_index() != 1:
                    ir = next(irs)
                
                if ir and depth:
                    log.d(f"{ir}, {depth}")
                    sensor_profiles_arr.append((sensor, depth))
                    sensor_profiles_arr.append((sensor, ir))
                    break
                    
        elif sensor.is_color_sensor():
            if sensor.supports(rs.option.enable_auto_exposure):
                sensor.set_option(rs.option.enable_auto_exposure, 1)
            if sensor.supports(rs.option.auto_exposure_priority):
                sensor.set_option(rs.option.auto_exposure_priority, 0)  # AE priority should be 0 for constant FPS
            profile = fps_helper.get_profile(sensor, rs.stream.color, HD_RESOLUTION)
            
        elif sensor.is_motion_sensor():
            connection_type = "USB"
            if device.supports(rs.camera_info.connection_type):
                connection_type = device.get_info(rs.camera_info.connection_type)
            
            if connection_type == "DDS":
                sensor_profiles_arr.append((sensor, fps_helper.get_profile(sensor, rs.stream.motion)))
            else:
                sensor_profiles_arr.append((sensor, fps_helper.get_profile(sensor, rs.stream.accel)))
                sensor_profiles_arr.append((sensor, fps_helper.get_profile(sensor, rs.stream.gyro)))
        
        if profile is not None:
            sensor_profiles_arr.append((sensor, profile))
    
    return sensor_profiles_arr


@pytest.fixture(scope="module")
def device_config(module_test_device):
    """
    Module-scoped fixture that provides device and sensor profiles.
    """
    dev, ctx = module_test_device
    
    sensor_profiles_array = get_sensors_and_profiles(dev)
    
    return {
        'dev': dev,
        'ctx': ctx,
        'sensor_profiles': sensor_profiles_array
    }


def test_fps_permutations(device_config):
    """
    Test FPS accuracy for all pair-wise combinations of sensor streams.
    
    This test:
    1. Gets all available sensor profiles from the device
    2. Generates all pair-wise combinations (e.g., depth+IR, depth+color, IR+color)
    3. For each pair, verifies both streams achieve expected FPS simultaneously
    4. Uses fps_helper.perform_fps_test() to validate FPS
    
    Timeout calculation: ((N choose 2) + 1) * (TIME_FOR_STEADY_STATE + TIME_TO_COUNT_FRAMES)
    where N is number of streams (up to 8)
    
    Note: Currently does not test all streams simultaneously (commented out in original)
    """
    dev = device_config['dev']
    sensor_profiles_array = device_config['sensor_profiles']
    
    log.i(f"Testing FPS permutations on {dev.get_info(rs.camera_info.name)}")
    log.i(f"Found {len(sensor_profiles_array)} sensor/profile combinations")
    
    # Generate all pair-wise combinations
    all_pairs = [
        [a[1].stream_name(), b[1].stream_name()] 
        for a, b in combinations(sensor_profiles_array, 2)
    ]
    
    # Note: Testing all streams simultaneously is currently commented out as it fails on CI
    # all_streams = [[profile.stream_name() for _, profile in sensor_profiles_array]]
    
    permutations_to_run = all_pairs  # + all_streams
    
    log.i(f"Testing {len(permutations_to_run)} stream pair permutations")
    
    # Run FPS test for all permutations
    fps_helper.perform_fps_test(sensor_profiles_array, permutations_to_run)
    
    log.i(f"All {len(permutations_to_run)} permutations tested successfully")
