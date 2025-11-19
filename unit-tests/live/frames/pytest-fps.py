# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2022 RealSense, Inc. All Rights Reserved.

"""
Test FPS accuracy for depth and color sensors.

This test verifies that actual FPS matches requested FPS for various frame rates
(5, 6, 15, 30, 60, 90 Hz). It uses sensor API to stream frames and measures
actual FPS by counting frames over a period of time. Validates that actual FPS
is within 5% of requested FPS (10% for 5 FPS).
"""

import pytest
import pyrealsense2 as rs
from rspy.stopwatch import Stopwatch
from rspy import log
import time
import platform

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.device_exclude("D555"),
    pytest.mark.nightly,
    pytest.mark.live
]

# Test configuration
TESTED_FPS = [5, 6, 15, 30, 60, 90]
TIME_TO_TEST_FPS = [25, 20, 13, 10, 5, 4]  # Seconds to count frames for each FPS
SECONDS_TILL_STEADY_STATE = 4  # Wait time before counting frames


def measure_fps(sensor, profile, seconds_to_count_frames=10):
    """
    Measure actual FPS by counting frames over a period of time.
    
    Waits for steady state, then counts frames for specified duration.
    Also logs frame drops and time to first frame.
    
    Args:
        sensor: Sensor to stream from
        profile: Stream profile to use
        seconds_to_count_frames: How long to count frames
        
    Returns:
        Tuple of (fps, time_to_first_frame)
    """
    steady_state = False
    first_frame_received = False
    frames_received = 0
    first_frame_stopwatch = Stopwatch()
    prev_frame_number = 0
    first_frame_seconds = 0.0
    
    def frame_cb(frame):
        nonlocal steady_state, frames_received, first_frame_received, prev_frame_number, first_frame_seconds
        current_frame_number = frame.get_frame_number()
        
        if not first_frame_received:
            first_frame_seconds = first_frame_stopwatch.get_elapsed()
            first_frame_received = True
        else:
            if current_frame_number > prev_frame_number + 1:
                log.w(f'Frame drop detected. Current frame number {current_frame_number} previous was {prev_frame_number}')
        
        if steady_state:
            frames_received += 1
        
        prev_frame_number = current_frame_number
    
    sensor.open(profile)
    sensor.start(frame_cb)
    first_frame_stopwatch.reset()
    
    # Wait for steady state
    time.sleep(SECONDS_TILL_STEADY_STATE)
    
    # Start counting frames
    steady_state = True
    time.sleep(seconds_to_count_frames)
    steady_state = False
    
    sensor.stop()
    sensor.close()
    
    fps = frames_received / seconds_to_count_frames
    return fps, first_frame_seconds


@pytest.fixture(scope="module")
def device_config(module_test_device):
    """
    Module-scoped fixture that provides device info and sensors.
    """
    dev, ctx = module_test_device
    product_line = dev.get_info(rs.camera_info.product_line)
    camera_name = dev.get_info(rs.camera_info.name)
    
    return {
        'dev': dev,
        'ctx': ctx,
        'product_line': product_line,
        'camera_name': camera_name
    }


def test_depth_fps(device_config):
    """
    Test that depth sensor achieves requested FPS across various frame rates.
    
    This test:
    1. Tests multiple FPS values: 5, 6, 15, 30, 60, 90 Hz
    2. Enables auto-exposure for D400 devices
    3. For each supported FPS, streams frames and measures actual FPS
    4. Validates actual FPS is within 5% of requested FPS
    5. Logs time to first frame and any frame drops
    
    Note: On D585S, 60 fps only available in bypass mode, 1280x960 only in service mode
    """
    dev = device_config['dev']
    product_line = device_config['product_line']
    camera_name = device_config['camera_name']
    
    log.i(f"Testing depth fps {product_line} device - {platform.system()} OS")
    
    ds = dev.first_depth_sensor()
    
    # Set auto-exposure option as it might take precedence over requested FPS
    if product_line == "D400":
        if ds.supports(rs.option.enable_auto_exposure):
            ds.set_option(rs.option.enable_auto_exposure, 1)
    
    tested_count = 0
    results = []
    
    for i in range(len(TESTED_FPS)):
        requested_fps = TESTED_FPS[i]
        
        try:
            dp = next(p for p in ds.profiles
                      if p.fps() == requested_fps
                      and p.stream_type() == rs.stream.depth
                      and p.format() == rs.format.z16
                      # On D585S the operational depth resolution is 1280x720
                      # 1280x960 is also available but only allowed in service mode
                      # 60 fps is only available in bypass mode
                      and ((p.as_video_stream_profile().height() == 720 and p.fps() != 60) if "D585S" in camera_name else True))
        
        except StopIteration:
            log.i(f"Requested fps: {requested_fps:.1f} [Hz], not supported")
            continue
        
        fps, time_to_first = measure_fps(ds, dp, TIME_TO_TEST_FPS[i])
        log.i(f"Requested fps: {requested_fps:.1f} [Hz], actual fps: {fps:.1f} [Hz]. Time to first frame {time_to_first:.6f}")
        
        delta_Hz = requested_fps * 0.05  # Validation KPI is 5%
        within_tolerance = (requested_fps - delta_Hz) <= fps <= (requested_fps + delta_Hz)
        
        results.append({
            'requested': requested_fps,
            'actual': fps,
            'delta': delta_Hz,
            'passed': within_tolerance
        })
        
        tested_count += 1
    
    # Validate all tested FPS rates passed
    failed_fps = [r for r in results if not r['passed']]
    
    assert len(failed_fps) == 0, \
        f"FPS validation failed for {len(failed_fps)}/{tested_count} rates: " + \
        ", ".join([f"{r['requested']} Hz (actual: {r['actual']:.1f}, tolerance: ±{r['delta']:.1f})" 
                   for r in failed_fps])
    
    log.i(f"All {tested_count} depth FPS rates validated successfully")


def test_color_fps(device_config):
    """
    Test that color sensor achieves requested FPS across various frame rates.
    
    This test:
    1. Tests multiple FPS values: 5, 6, 15, 30, 60, 90 Hz
    2. Enables auto-exposure and disables AE priority for D400 devices
    3. For each supported FPS, streams frames and measures actual FPS
    4. Validates actual FPS is within 5% of requested FPS (10% for 5 FPS)
    5. Logs time to first frame and any frame drops
    
    Note: Skips test for devices without color sensor (D421, D405)
    """
    dev = device_config['dev']
    product_line = device_config['product_line']
    product_name = dev.get_info(rs.camera_info.name)
    
    log.i(f"Testing color fps {product_line} device - {platform.system()} OS")
    
    # Check if device has color sensor
    try:
        cs = dev.first_color_sensor()
    except RuntimeError:
        if 'D421' not in product_name and 'D405' not in product_name:
            # Unexpected - device should have color sensor
            raise
        pytest.skip(f"Device {product_name} does not have a color sensor")
    
    # Set auto-exposure option as it might take precedence over requested FPS
    if product_line == "D400":
        if cs.supports(rs.option.enable_auto_exposure):
            cs.set_option(rs.option.enable_auto_exposure, 1)
        if cs.supports(rs.option.auto_exposure_priority):
            cs.set_option(rs.option.auto_exposure_priority, 0)  # AE priority should be 0 for constant FPS
    
    tested_count = 0
    results = []
    
    for i in range(len(TESTED_FPS)):
        requested_fps = TESTED_FPS[i]
        
        try:
            cp = next(p for p in cs.profiles
                      if p.fps() == requested_fps
                      and p.stream_type() == rs.stream.color
                      and p.format() == rs.format.rgb8)
        
        except StopIteration:
            log.i(f"Requested fps: {requested_fps:.1f} [Hz], not supported")
            continue
        
        fps, time_to_first = measure_fps(cs, cp, TIME_TO_TEST_FPS[i])
        log.i(f"Requested fps: {requested_fps:.1f} [Hz], actual fps: {fps:.1f} [Hz]. Time to first frame {time_to_first:.6f}")
        
        # Validation KPI is 5% for all non-5 FPS rates, 10% for 5 FPS
        delta_Hz = requested_fps * (0.10 if requested_fps == 5 else 0.05)
        within_tolerance = (requested_fps - delta_Hz) <= fps <= (requested_fps + delta_Hz)
        
        results.append({
            'requested': requested_fps,
            'actual': fps,
            'delta': delta_Hz,
            'passed': within_tolerance
        })
        
        tested_count += 1
    
    # Validate all tested FPS rates passed
    failed_fps = [r for r in results if not r['passed']]
    
    assert len(failed_fps) == 0, \
        f"FPS validation failed for {len(failed_fps)}/{tested_count} rates: " + \
        ", ".join([f"{r['requested']} Hz (actual: {r['actual']:.1f}, tolerance: ±{r['delta']:.1f})" 
                   for r in failed_fps])
    
    log.i(f"All {tested_count} color FPS rates validated successfully")
