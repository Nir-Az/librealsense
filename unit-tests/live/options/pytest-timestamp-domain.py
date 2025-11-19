# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2022 RealSense, Inc. All Rights Reserved.

"""
Timestamp Domain Test

Tests the global_time_enabled option and verifies that frame timestamp domains
are correctly set based on this option. Tests both depth and color sensors.
"""

import pytest
import pyrealsense2 as rs
import time

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*", exclude="D555"),
    pytest.mark.nightly,
    pytest.mark.live
]

QUEUE_CAPACITY = 1
SLEEP_TIME = 0.5  # Waiting for new frame from device (needed for low FPS)


def set_and_verify_timestamp_domain(sensor, frame_queue, global_time_enabled, sleep_time=SLEEP_TIME):
    """Perform sensor test according to given global time setting.
    
    Args:
        sensor: Depth or color sensor in device
        frame_queue: Frame queue to receive frames
        global_time_enabled: True if timestamp should be enabled, False otherwise
        sleep_time: Time to wait for frames to arrive
    """
    sensor.set_option(rs.option.global_time_enabled, global_time_enabled)
    time.sleep(sleep_time)
    
    frame = frame_queue.wait_for_frame()
    assert frame is not None, "Failed to receive frame"
    
    expected_ts_domain = (
        rs.timestamp_domain.global_time if global_time_enabled
        else rs.timestamp_domain.hardware_clock
    )
    
    assert bool(sensor.get_option(rs.option.global_time_enabled)) == global_time_enabled, \
        f"Global time enabled option mismatch: expected {global_time_enabled}"
    
    assert frame.get_frame_timestamp_domain() == expected_ts_domain, \
        f"Frame timestamp domain mismatch: expected {expected_ts_domain}, got {frame.get_frame_timestamp_domain()}"


@pytest.fixture
def streaming_depth_sensor(test_device):
    """Setup streaming depth sensor."""
    dev, ctx = test_device
    
    depth_frame_queue = rs.frame_queue(QUEUE_CAPACITY, keep_frames=False)
    
    depth_sensor = dev.first_depth_sensor()
    depth_profile = next(p for p in depth_sensor.profiles if p.stream_type() == rs.stream.depth and p.is_default())
    depth_sensor.open(depth_profile)
    depth_sensor.start(depth_frame_queue)
    
    yield depth_sensor, depth_frame_queue
    
    # Cleanup
    try:
        if len(depth_sensor.get_active_streams()) > 0:
            depth_sensor.stop()
            depth_sensor.close()
    except:
        pass


@pytest.fixture
def streaming_color_sensor(test_device):
    """Setup streaming color sensor."""
    dev, ctx = test_device
    product_name = dev.get_info(rs.camera_info.name)
    
    try:
        color_sensor = dev.first_color_sensor()
    except RuntimeError:
        # Cameras with no color sensor (D421, D405) may fail
        if 'D421' not in product_name and 'D405' not in product_name:
            raise
        pytest.skip("No color sensor available")
    
    color_frame_queue = rs.frame_queue(QUEUE_CAPACITY, keep_frames=False)
    
    color_profile = next(p for p in color_sensor.profiles if p.stream_type() == rs.stream.color and p.is_default())
    color_sensor.open(color_profile)
    color_sensor.start(color_frame_queue)
    
    yield color_sensor, color_frame_queue
    
    # Cleanup
    try:
        if len(color_sensor.get_active_streams()) > 0:
            color_sensor.stop()
            color_sensor.close()
    except:
        pass


def test_depth_sensor_timestamp_domain_off(streaming_depth_sensor):
    """Test depth sensor with global time domain OFF (hardware clock)."""
    depth_sensor, depth_frame_queue = streaming_depth_sensor
    set_and_verify_timestamp_domain(depth_sensor, depth_frame_queue, False)


def test_depth_sensor_timestamp_domain_on(streaming_depth_sensor):
    """Test depth sensor with global time domain ON (global time)."""
    depth_sensor, depth_frame_queue = streaming_depth_sensor
    set_and_verify_timestamp_domain(depth_sensor, depth_frame_queue, True)


def test_color_sensor_timestamp_domain_off(streaming_color_sensor):
    """Test color sensor with global time domain OFF (hardware clock)."""
    color_sensor, color_frame_queue = streaming_color_sensor
    set_and_verify_timestamp_domain(color_sensor, color_frame_queue, False)


def test_color_sensor_timestamp_domain_on(streaming_color_sensor):
    """Test color sensor with global time domain ON (global time)."""
    color_sensor, color_frame_queue = streaming_color_sensor
    set_and_verify_timestamp_domain(color_sensor, color_frame_queue, True)
