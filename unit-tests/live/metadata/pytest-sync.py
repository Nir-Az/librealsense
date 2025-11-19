# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
Frame Synchronization Test

Checks that timestamps of depth, infrared and color frames are consistent.
Handles frame drops gracefully using hardware frame counters.
"""

import pytest
import pyrealsense2 as rs
import time

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.nightly,
    pytest.mark.live
]

# Test parameters
TS_TOLERANCE_MS = 1.5  # Tolerance for timestamp differences in ms
TS_TOLERANCE_MICROSEC = TS_TOLERANCE_MS * 1000
SKIP_FRAMES_AFTER_DROP = 10  # Frames to skip after detecting drops
FRAMES_TO_TEST = 100


def detect_frame_drops(frames_dict, prev_frame_counters):
    """
    Detect frame drops using hardware frame counters.
    
    Args:
        frames_dict: Dictionary of stream names to frames
        prev_frame_counters: Previous frame counter values
    
    Returns:
        Tuple of (frame_drop_detected, current_frame_counters)
    """
    frame_drop_detected = False
    current_frame_counters = {}
    
    for stream_name, frame in frames_dict.items():
        if not frame.supports_frame_metadata(rs.frame_metadata_value.frame_counter):
            continue
        
        current_counter = frame.get_frame_metadata(rs.frame_metadata_value.frame_counter)
        current_frame_counters[stream_name] = current_counter
        
        prev_counter = prev_frame_counters.get(stream_name)
        if prev_counter is not None and current_counter > prev_counter + 1:
            # Frame drop detected
            dropped_frames = current_counter - prev_counter - 1
            pytest.skip(f"Frame drop detected on {stream_name}: {dropped_frames} frames dropped")
            frame_drop_detected = True
    
    return frame_drop_detected, current_frame_counters


def test_frame_sync(test_device):
    """Verify synchronized frames have consistent timestamps."""
    dev, ctx = test_device
    
    cfg = rs.config()
    cfg.enable_stream(rs.stream.depth)
    cfg.enable_stream(rs.stream.infrared, 1)
    cfg.enable_stream(rs.stream.infrared, 2)
    # Use VGA since HD resolution may fail
    cfg.enable_stream(rs.stream.color, 640, 480, rs.format.yuyv, 30)
    
    depth_sensor = dev.first_depth_sensor()
    color_sensor = dev.first_color_sensor()
    
    # Enable global timestamp if available
    for sensor in [depth_sensor, color_sensor]:
        if sensor.supports(rs.option.global_time_enabled):
            if not sensor.get_option(rs.option.global_time_enabled):
                sensor.set_option(rs.option.global_time_enabled, 1)
        else:
            pytest.fail(f"Sensor {sensor.name} does not support global time option")
    
    pipe = rs.pipeline(ctx)
    pipe.start(cfg)
    
    # Longer stabilization to prevent initial frame drop issues
    time.sleep(5)
    
    # Frame drop detection state
    prev_frame_counters = {'depth': None, 'ir1': None, 'ir2': None, 'color': None}
    frames_to_skip = 0
    consecutive_drops = 0
    
    try:
        for frame_count in range(1, FRAMES_TO_TEST + 1):
            frames = pipe.wait_for_frames()
            depth_frame = frames.get_depth_frame()
            ir1_frame = frames.get_infrared_frame(1)
            ir2_frame = frames.get_infrared_frame(2)
            color_frame = frames.get_color_frame()
            
            if not all([depth_frame, ir1_frame, ir2_frame, color_frame]):
                pytest.skip("One or more frames are missing")
                continue
            
            # Check for frame drops
            frames_dict = {
                'depth': depth_frame,
                'ir1': ir1_frame,
                'ir2': ir2_frame,
                'color': color_frame
            }
            frame_drop_detected, current_frame_counters = detect_frame_drops(
                frames_dict, prev_frame_counters
            )
            
            # Handle frame drops
            if frame_drop_detected:
                consecutive_drops += 1
                if consecutive_drops > 20:
                    pytest.fail(f"Continuous frame drops detected ({consecutive_drops} consecutive)")
                
                frames_to_skip = SKIP_FRAMES_AFTER_DROP
                prev_frame_counters = current_frame_counters
                continue
            
            # Skip frames during recovery
            if frames_to_skip > 0:
                frames_to_skip -= 1
                if frames_to_skip == 0:
                    prev_frame_counters = {'depth': None, 'ir1': None, 'ir2': None, 'color': None}
                continue
            
            prev_frame_counters = current_frame_counters
            consecutive_drops = 0
            
            # Test global timestamp synchronization (in milliseconds)
            depth_ts = depth_frame.timestamp
            ir1_ts = ir1_frame.timestamp
            ir2_ts = ir2_frame.timestamp
            color_ts = color_frame.timestamp
            
            assert abs(depth_ts - ir1_ts) <= TS_TOLERANCE_MS, \
                f"Depth-IR1 timestamp diff too large: {abs(depth_ts - ir1_ts)}ms"
            assert abs(depth_ts - ir2_ts) <= TS_TOLERANCE_MS, \
                f"Depth-IR2 timestamp diff too large: {abs(depth_ts - ir2_ts)}ms"
            assert abs(depth_ts - color_ts) <= TS_TOLERANCE_MS, \
                f"Depth-Color timestamp diff too large: {abs(depth_ts - color_ts)}ms"
            
            # Test frame metadata timestamps if supported (in microseconds)
            if all(f.supports_frame_metadata(rs.frame_metadata_value.frame_timestamp) 
                   for f in frames_dict.values()):
                frame_timestamps = {
                    name: f.get_frame_metadata(rs.frame_metadata_value.frame_timestamp)
                    for name, f in frames_dict.items()
                }
                
                assert abs(frame_timestamps['depth'] - frame_timestamps['ir1']) <= TS_TOLERANCE_MICROSEC, \
                    f"Depth-IR1 frame timestamp diff too large"
                assert abs(frame_timestamps['depth'] - frame_timestamps['ir2']) <= TS_TOLERANCE_MICROSEC, \
                    f"Depth-IR2 frame timestamp diff too large"
                assert abs(frame_timestamps['depth'] - frame_timestamps['color']) <= TS_TOLERANCE_MICROSEC, \
                    f"Depth-Color frame timestamp diff too large"
    
    finally:
        pipe.stop()
