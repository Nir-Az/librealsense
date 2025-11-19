# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2020 RealSense, Inc. All Rights Reserved.

"""
Options Set Frame Drops Test

Tests that setting camera options during streaming doesn't cause frame drops.
Currently excludes D457 & D555 due to known issues.

Monitors frame counters to detect drops when changing options like laser power,
gain, exposure, etc.
"""

import pytest
import pyrealsense2 as rs
import time
import platform
from rspy import tests_wrapper as tw

# Module-level markers
pytestmark = [
    pytest.mark.device("D400*", exclude="D457"),
    pytest.mark.nightly,
    pytest.mark.live
]

# Frame drop tolerance
# On Linux, up to 4 frame drops can occur after setting controls (RS5-7148)
# Our KPI is to prevent sequential frame drops, so single drop is allowed
ALLOWED_DROPS_LINUX_AFTER_SET = 4
ALLOWED_DROPS_DEFAULT = 1


@pytest.fixture
def streaming_sensors(test_device):
    """Setup streaming depth and color sensors."""
    dev, ctx = test_device
    product_name = dev.get_info(rs.camera_info.name)
    product_line = dev.get_info(rs.camera_info.product_line)
    
    depth_sensor = dev.first_depth_sensor()
    color_sensor = None
    
    try:
        color_sensor = dev.first_color_sensor()
    except RuntimeError:
        # Cameras with no color sensor (D421, D405) may fail
        if 'D421' not in product_name and 'D405' not in product_name:
            raise
    
    # Use default profiles
    depth_profile = next(p for p in depth_sensor.profiles if p.is_default())
    
    depth_frames = []
    color_frames = []
    
    def depth_callback(frame):
        depth_frames.append(frame)
    
    def color_callback(frame):
        color_frames.append(frame)
    
    tw.start_wrapper(dev)
    
    depth_sensor.open(depth_profile)
    depth_sensor.start(depth_callback)
    
    if color_sensor:
        color_profile = next(p for p in color_sensor.profiles if p.is_default())
        color_sensor.open(color_profile)
        color_sensor.start(color_callback)
    
    yield dev, depth_sensor, color_sensor, depth_frames, color_frames, product_line
    
    try:
        depth_sensor.stop()
        depth_sensor.close()
        if color_sensor:
            color_sensor.stop()
            color_sensor.close()
    except:
        pass
    finally:
        tw.stop_wrapper(dev)


def check_frame_drops(frames, allowed_drops, product_line):
    """Check for frame drops using hardware frame counters."""
    prev_frame_number = None
    
    for frame in frames:
        if not frame.supports_frame_metadata(rs.frame_metadata_value.frame_counter):
            continue
        
        current_frame_number = frame.get_frame_metadata(rs.frame_metadata_value.frame_counter)
        
        if prev_frame_number is not None:
            # D400 devices may reset frame counter
            is_d400 = (product_line == "D400")
            
            if current_frame_number < prev_frame_number and is_d400:
                # Frame counter reset, allowed for D400
                pass
            elif current_frame_number > prev_frame_number + 1:
                dropped = current_frame_number - prev_frame_number - 1
                assert dropped <= allowed_drops, \
                    f"Too many frame drops: {dropped} (allowed: {allowed_drops})"
        
        prev_frame_number = current_frame_number


def test_laser_power_changes(streaming_sensors):
    """Test frame drops when setting laser power multiple times."""
    dev, depth_sensor, color_sensor, depth_frames, color_frames, product_line = streaming_sensors
    
    depth_frames.clear()
    
    curr_value = depth_sensor.get_option(rs.option.laser_power)
    opt_range = depth_sensor.get_option_range(rs.option.laser_power)
    
    new_value = opt_range.min
    while new_value <= opt_range.max:
        depth_sensor.set_option(rs.option.laser_power, new_value)
        time.sleep(0.5)  # Collect frames
        new_value += opt_range.step
    
    depth_sensor.set_option(rs.option.laser_power, curr_value)  # Restore
    time.sleep(0.5)
    
    # Check for frame drops (allow more on Linux after set_option)
    allowed = ALLOWED_DROPS_LINUX_AFTER_SET if platform.system() == 'Linux' else ALLOWED_DROPS_DEFAULT
    check_frame_drops(depth_frames, allowed, product_line)


def test_depth_sensor_options(streaming_sensors):
    """Test frame drops when setting various depth sensor options."""
    dev, depth_sensor, color_sensor, depth_frames, color_frames, product_line = streaming_sensors
    
    depth_frames.clear()
    
    # Options to ignore
    options_to_ignore = []
    if product_line == "D400":
        # Frame drops expected or not allowed during streaming
        options_to_ignore = [
            rs.option.visual_preset,
            rs.option.inter_cam_sync_mode,
            rs.option.emitter_frequency,
            rs.option.auto_exposure_mode
        ]
    
    options = depth_sensor.get_supported_options()
    
    for option in options:
        if option in options_to_ignore or depth_sensor.is_option_read_only(option):
            continue
        
        orig_opt_value = depth_sensor.get_option_value(option)
        if orig_opt_value.type in (rs.option_type.integer, rs.option_type.float):
            old_value = orig_opt_value.value
            range_val = depth_sensor.get_option_range(option)
            new_value = range_val.min if old_value != range_val.min else range_val.max
            
            depth_sensor.set_option(option, new_value)
            time.sleep(0.5)
            depth_sensor.set_option(option, old_value)
            time.sleep(0.5)
    
    allowed = ALLOWED_DROPS_LINUX_AFTER_SET if platform.system() == 'Linux' else ALLOWED_DROPS_DEFAULT
    check_frame_drops(depth_frames, allowed, product_line)


def test_color_sensor_options(streaming_sensors):
    """Test frame drops when setting various color sensor options."""
    dev, depth_sensor, color_sensor, depth_frames, color_frames, product_line = streaming_sensors
    
    if not color_sensor:
        pytest.skip("No color sensor available")
    
    color_frames.clear()
    
    options = color_sensor.get_supported_options()
    
    for option in options:
        if color_sensor.is_option_read_only(option):
            continue
        
        orig_opt_value = color_sensor.get_option_value(option)
        if orig_opt_value.type in (rs.option_type.integer, rs.option_type.float):
            old_value = orig_opt_value.value
            range_val = color_sensor.get_option_range(option)
            new_value = range_val.min if old_value != range_val.min else range_val.max
            
            color_sensor.set_option(option, new_value)
            time.sleep(0.5)
            color_sensor.set_option(option, old_value)
            time.sleep(0.5)
    
    allowed = ALLOWED_DROPS_LINUX_AFTER_SET if platform.system() == 'Linux' else ALLOWED_DROPS_DEFAULT
    check_frame_drops(color_frames, allowed, product_line)
