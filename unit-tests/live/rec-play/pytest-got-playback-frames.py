# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2021 RealSense, Inc. All Rights Reserved.

"""
Got Playback Frames Test

Tests recording and playback using different interfaces (pipeline, sensor, sensor with syncer).
Also checks for frame drops during recording and playback. Verifies that recommended filters
are preserved in recorded files.
"""

import pytest
import pyrealsense2 as rs
import os
import time
import tempfile

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*", exclude="D555"),
    pytest.mark.nightly,
    pytest.mark.live
]

# Frame drop tolerance
ALLOWED_DROPS = 1  # Single frame drop is allowed (KPI is to prevent sequential drops)


def check_frame_drops(frame, previous_frame_number, allowed_drops, is_d400):
    """Check for frame drops using frame counter metadata."""
    if not frame.supports_frame_metadata(rs.frame_metadata_value.frame_counter):
        return frame.get_frame_number()
    
    current_frame_number = frame.get_frame_metadata(rs.frame_metadata_value.frame_counter)
    
    if previous_frame_number >= 0:
        # D400 devices may reset frame counter
        if current_frame_number < previous_frame_number and is_d400:
            pass  # Frame counter reset is allowed for D400
        elif current_frame_number > previous_frame_number + 1:
            dropped = current_frame_number - previous_frame_number - 1
            assert dropped <= allowed_drops, \
                f"Too many frame drops: {dropped} (allowed: {allowed_drops})"
    
    return current_frame_number


def stop_sensor(sensor):
    """Safely stop and close a sensor."""
    if sensor and sensor.get_active_streams():
        try:
            sensor.stop()
            sensor.close()
        except RuntimeError as rte:
            if "not streaming" not in str(rte).lower():
                raise


@pytest.fixture
def device_info(test_device):
    """Get device information and sensors."""
    dev, ctx = test_device
    
    depth_sensor = dev.first_depth_sensor()
    color_sensor = dev.first_color_sensor()
    
    product_line = dev.get_info(rs.camera_info.product_line)
    is_d400 = (product_line == "D400")
    
    return {
        'dev': dev,
        'ctx': ctx,
        'depth_sensor': depth_sensor,
        'color_sensor': color_sensor,
        'is_d400': is_d400
    }


@pytest.fixture
def profile_settings(device_info):
    """Find default profile settings with lowest color FPS."""
    color_sensor = device_info['color_sensor']
    depth_sensor = device_info['depth_sensor']
    
    # Find default color profile
    color_format = color_fps = color_width = color_height = None
    for p in color_sensor.profiles:
        if p.is_default() and p.stream_type() == rs.stream.color:
            color_format = p.format()
            color_fps = p.fps()
            vp = p.as_video_stream_profile()
            color_width = vp.width()
            color_height = vp.height()
            break
    
    # Find lowest FPS for color with same format/resolution
    for p in color_sensor.profiles:
        if (p.stream_type() == rs.stream.color and 
            p.format() == color_format and
            p.fps() < color_fps):
            vp = p.as_video_stream_profile()
            if vp.width() == color_width and vp.height() == color_height:
                color_fps = p.fps()
    
    # Find default depth profile
    depth_format = depth_fps = depth_width = depth_height = None
    for p in depth_sensor.profiles:
        if p.is_default() and p.stream_type() == rs.stream.depth:
            depth_format = p.format()
            depth_fps = p.fps()
            vp = p.as_video_stream_profile()
            depth_width = vp.width()
            depth_height = vp.height()
            break
    
    return {
        'color_format': color_format,
        'color_fps': color_fps,
        'color_width': color_width,
        'color_height': color_height,
        'depth_format': depth_format,
        'depth_fps': depth_fps,
        'depth_width': depth_width,
        'depth_height': depth_height
    }


def get_profiles(sensor, settings, stream_type):
    """Get profiles matching the settings."""
    if stream_type == rs.stream.color:
        return next(p for p in sensor.profiles
                   if p.fps() == settings['color_fps']
                   and p.stream_type() == stream_type
                   and p.format() == settings['color_format']
                   and p.as_video_stream_profile().width() == settings['color_width']
                   and p.as_video_stream_profile().height() == settings['color_height'])
    else:  # depth
        return next(p for p in sensor.profiles
                   if p.fps() == settings['depth_fps']
                   and p.stream_type() == stream_type
                   and p.format() == settings['depth_format']
                   and p.as_video_stream_profile().width() == settings['depth_width']
                   and p.as_video_stream_profile().height() == settings['depth_height'])


@pytest.fixture
def temp_recording_file():
    """Create temporary file for recording."""
    temp_dir = tempfile.TemporaryDirectory(prefix='recordings_')
    file_name = os.path.join(temp_dir.name, 'rec.bag')
    yield file_name


def test_pipeline_record_playback(device_info, temp_recording_file):
    """Test record and playback using pipeline interface."""
    ctx = device_info['ctx']
    
    # Record
    pipeline = rs.pipeline(ctx)
    cfg = rs.config()
    cfg.enable_record_to_file(temp_recording_file)
    pipeline.start(cfg)
    time.sleep(3)
    pipeline.stop()
    
    # Playback
    pipeline = rs.pipeline(ctx)
    cfg = rs.config()
    cfg.enable_device_from_file(temp_recording_file)
    pipeline.start(cfg)
    
    # Verify we get frames
    frames = pipeline.wait_for_frames()
    assert frames is not None, "No frames received during playback"
    
    pipeline.stop()


def test_sensor_record_playback(device_info, profile_settings, temp_recording_file):
    """Test record and playback using sensor interface."""
    dev = device_info['dev']
    ctx = device_info['ctx']
    is_d400 = device_info['is_d400']
    
    # Record
    recorder = rs.recorder(temp_recording_file, dev)
    depth_sensor = dev.first_depth_sensor()
    color_sensor = dev.first_color_sensor()
    
    dp = get_profiles(depth_sensor, profile_settings, rs.stream.depth)
    cp = get_profiles(color_sensor, profile_settings, rs.stream.color)
    
    depth_sensor.open(dp)
    depth_sensor.start(lambda f: None)
    color_sensor.open(cp)
    color_sensor.start(lambda f: None)
    
    time.sleep(3)
    
    recorder.pause()
    
    stop_sensor(depth_sensor)
    stop_sensor(color_sensor)
    
    # Get filters before playback
    color_filters = [f.get_info(rs.camera_info.name) for f in color_sensor.get_recommended_filters()]
    depth_filters = [f.get_info(rs.camera_info.name) for f in depth_sensor.get_recommended_filters()]
    
    assert len(color_filters) > 0, "No color filters found"
    assert len(depth_filters) > 0, "No depth filters found"
    
    recorder = None
    
    # Playback
    playback = ctx.load_device(temp_recording_file)
    depth_sensor = playback.first_depth_sensor()
    color_sensor = playback.first_color_sensor()
    
    # Verify filters are preserved
    playback_color_filters = [f.get_info(rs.camera_info.name) for f in color_sensor.get_recommended_filters()]
    playback_depth_filters = [f.get_info(rs.camera_info.name) for f in depth_sensor.get_recommended_filters()]
    
    assert playback_color_filters == color_filters, "Color filters mismatch"
    assert playback_depth_filters == depth_filters, "Depth filters mismatch"
    
    # Start playback and verify frames
    dp = get_profiles(depth_sensor, profile_settings, rs.stream.depth)
    cp = get_profiles(color_sensor, profile_settings, rs.stream.color)
    
    got_depth = False
    got_color = False
    prev_depth_fn = -1
    prev_color_fn = -1
    
    def depth_callback(frame):
        nonlocal got_depth, prev_depth_fn
        got_depth = True
        prev_depth_fn = check_frame_drops(frame, prev_depth_fn, ALLOWED_DROPS, is_d400)
    
    def color_callback(frame):
        nonlocal got_color, prev_color_fn
        got_color = True
        prev_color_fn = check_frame_drops(frame, prev_color_fn, ALLOWED_DROPS, is_d400)
    
    depth_sensor.open(dp)
    depth_sensor.start(depth_callback)
    color_sensor.open(cp)
    color_sensor.start(color_callback)
    
    time.sleep(3)
    
    stop_sensor(depth_sensor)
    stop_sensor(color_sensor)
    
    assert got_depth, "No depth frames received during playback"
    assert got_color, "No color frames received during playback"


def test_sensor_syncer_record_playback(device_info, profile_settings, temp_recording_file):
    """Test record and playback using sensor interface with syncer."""
    dev = device_info['dev']
    ctx = device_info['ctx']
    
    # Record
    sync = rs.syncer()
    recorder = rs.recorder(temp_recording_file, dev)
    depth_sensor = dev.first_depth_sensor()
    color_sensor = dev.first_color_sensor()
    
    dp = get_profiles(depth_sensor, profile_settings, rs.stream.depth)
    cp = get_profiles(color_sensor, profile_settings, rs.stream.color)
    
    depth_sensor.open(dp)
    depth_sensor.start(sync)
    color_sensor.open(cp)
    color_sensor.start(sync)
    
    time.sleep(3)
    
    recorder.pause()
    
    stop_sensor(depth_sensor)
    stop_sensor(color_sensor)
    
    recorder = None
    
    # Playback
    playback = ctx.load_device(temp_recording_file)
    depth_sensor = playback.first_depth_sensor()
    color_sensor = playback.first_color_sensor()
    
    dp = get_profiles(depth_sensor, profile_settings, rs.stream.depth)
    cp = get_profiles(color_sensor, profile_settings, rs.stream.color)
    
    sync = rs.syncer()
    depth_sensor.open(dp)
    depth_sensor.start(sync)
    color_sensor.open(cp)
    color_sensor.start(sync)
    
    # Verify we get frames
    frames = sync.wait_for_frames()
    assert frames is not None, "No frames received from syncer during playback"
    
    stop_sensor(depth_sensor)
    stop_sensor(color_sensor)
