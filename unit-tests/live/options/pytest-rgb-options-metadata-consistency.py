# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2021 RealSense, Inc. All Rights Reserved.

"""
RGB Options Metadata Consistency Test

Tests that color sensor options match their corresponding frame metadata values.
For each option, sets min/max/default values and verifies both get_option() and
get_frame_metadata() return the same values after waiting for frames to propagate.
"""

import pytest
import pyrealsense2 as rs

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*", exclude=["D421", "D405"]),
    pytest.mark.device_each("D500*"),
    pytest.mark.nightly,
    pytest.mark.live
]

# Color options and their corresponding metadata
COLOR_OPTIONS = [
    rs.option.backlight_compensation,
    rs.option.brightness,
    rs.option.contrast,
    rs.option.gamma,
    rs.option.hue,
    rs.option.saturation,
    rs.option.sharpness,
    rs.option.enable_auto_white_balance,
    rs.option.white_balance
]

COLOR_METADATA = [
    rs.frame_metadata_value.backlight_compensation,
    rs.frame_metadata_value.brightness,
    rs.frame_metadata_value.contrast,
    rs.frame_metadata_value.gamma,
    rs.frame_metadata_value.hue,
    rs.frame_metadata_value.saturation,
    rs.frame_metadata_value.sharpness,
    rs.frame_metadata_value.auto_white_balance_temperature,
    rs.frame_metadata_value.manual_white_balance
]

# Number of frames to wait between set_option and checking metadata
# Expected delay is ~120ms for Win and ~80-90ms for Linux
NUM_FRAMES_TO_WAIT = 15


@pytest.fixture
def streaming_color_sensor(test_device):
    """Setup streaming color sensor with frame queue."""
    dev, ctx = test_device
    
    try:
        color_sensor = dev.first_color_sensor()
    except RuntimeError:
        pytest.skip("No color sensor available")
    
    # Using a profile common to known cameras
    color_profile = next(
        (p for p in color_sensor.profiles
         if p.fps() == 30
         and p.stream_type() == rs.stream.color
         and p.format() == rs.format.yuyv
         and p.as_video_stream_profile().width() == 640
         and p.as_video_stream_profile().height() == 480),
        None
    )
    
    if not color_profile:
        pytest.skip("Required color profile (640x480 YUYV @30fps) not available")
    
    color_sensor.open(color_profile)
    lrs_queue = rs.frame_queue(capacity=10, keep_frames=False)
    color_sensor.start(lrs_queue)
    
    yield color_sensor, lrs_queue
    
    # Cleanup
    try:
        if len(color_sensor.get_active_streams()) > 0:
            color_sensor.stop()
            color_sensor.close()
    except:
        pass


def check_option_and_metadata_values(color_sensor, option, metadata, value_to_set, frame):
    """Verify option value matches metadata value.
    
    Args:
        color_sensor: The color sensor
        option: The option to check
        metadata: The corresponding metadata value
        value_to_set: The expected value
        frame: The frame to get metadata from
    """
    changed = color_sensor.get_option(option)
    assert changed == value_to_set, \
        f"Option {option} value {changed} doesn't match expected {value_to_set}"
    
    if frame.supports_frame_metadata(metadata):
        changed_md = float(frame.get_frame_metadata(metadata))
        assert changed_md == value_to_set, \
            f"Metadata {metadata} value {changed_md} doesn't match expected {value_to_set}"


def test_color_options_metadata_consistency(streaming_color_sensor):
    """Test that color options and metadata values stay consistent.
    
    For each option, sets min/max/default values and verifies both
    get_option() and get_frame_metadata() return the same values.
    """
    color_sensor, lrs_queue = streaming_color_sensor
    
    for option, metadata in zip(COLOR_OPTIONS, COLOR_METADATA):
        if not color_sensor.supports(option):
            continue
        
        option_range = color_sensor.get_option_range(option)
        
        # Workaround for FW bug DSO-17221 - to be removed after bug is solved
        if option == rs.option.white_balance:
            color_sensor.set_option(rs.option.enable_auto_white_balance, 0)
            assert color_sensor.get_option(rs.option.enable_auto_white_balance) == 0.0
        
        # Test min value
        value_to_set = option_range.min
        color_sensor.set_option(option, value_to_set)
        
        # Wait for frames to propagate
        for _ in range(NUM_FRAMES_TO_WAIT):
            lrs_queue.wait_for_frame(5000)
        
        frame = lrs_queue.wait_for_frame(5000)
        check_option_and_metadata_values(color_sensor, option, metadata, value_to_set, frame)
        
        # Test max value
        value_to_set = option_range.max
        color_sensor.set_option(option, value_to_set)
        
        # Wait for frames to propagate
        for _ in range(NUM_FRAMES_TO_WAIT):
            lrs_queue.wait_for_frame(5000)
        
        frame = lrs_queue.wait_for_frame(5000)
        check_option_and_metadata_values(color_sensor, option, metadata, value_to_set, frame)
        
        # Test default value
        value_to_set = option_range.default
        color_sensor.set_option(option, value_to_set)
        
        # Wait for frames to propagate
        for _ in range(NUM_FRAMES_TO_WAIT):
            lrs_queue.wait_for_frame(5000)
        
        frame = lrs_queue.wait_for_frame(5000)
        check_option_and_metadata_values(color_sensor, option, metadata, value_to_set, frame)
