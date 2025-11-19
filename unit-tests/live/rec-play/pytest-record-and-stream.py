# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2023 RealSense, Inc. All Rights Reserved.

"""
Record and Stream Test

Tests that the camera can record to a file, then stream again after stopping,
and finally play back the recording. This verifies a bug fix where the viewer
crashed when starting stream after finishing a record session.
"""

import pytest
import pyrealsense2 as rs
import os
import time
import tempfile

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.nightly,
    pytest.mark.live
]


def find_default_profile(sensor):
    """Find the default depth profile for the sensor."""
    return next(p for p in sensor.profiles 
                if p.is_default() and p.stream_type() == rs.stream.depth)


def restart_profile(sensor, default_profile):
    """
    Recreate a profile with the same parameters.
    You can't use the same profile twice, so we need to find it again.
    """
    return next(p for p in sensor.profiles 
                if p.fps() == default_profile.fps()
                and p.stream_type() == rs.stream.depth
                and p.format() == default_profile.format()
                and p.as_video_stream_profile().width() == default_profile.as_video_stream_profile().width()
                and p.as_video_stream_profile().height() == default_profile.as_video_stream_profile().height())


def test_record_stream_playback(test_device):
    """Test recording, then streaming, then playback using sensor interface with frame queue."""
    dev, ctx = test_device
    
    # Create temporary file for recording
    temp_dir = tempfile.mkdtemp()
    file_name = os.path.join(temp_dir, "recording.bag")
    
    try:
        depth_sensor = dev.first_depth_sensor()
        default_profile = find_default_profile(depth_sensor)
        
        # Step 1: Record
        frame_queue = rs.frame_queue(10)
        depth_profile = restart_profile(depth_sensor, default_profile)
        depth_sensor.open(depth_profile)
        depth_sensor.start(frame_queue)
        
        recorder = rs.recorder(file_name, dev)
        time.sleep(3)
        recorder.pause()
        recorder = None
        
        depth_sensor.stop()
        depth_sensor.close()
        
        # Step 2: Try streaming again (this used to crash)
        frame_queue = rs.frame_queue(10)
        depth_profile = restart_profile(depth_sensor, default_profile)
        depth_sensor.open(depth_profile)
        depth_sensor.start(frame_queue)
        time.sleep(3)
        depth_sensor.stop()
        depth_sensor.close()
        
        # Step 3: Play recording
        playback = ctx.load_device(file_name)
        depth_sensor = playback.first_depth_sensor()
        
        frame_queue = rs.frame_queue(10)
        depth_profile = restart_profile(depth_sensor, default_profile)
        depth_sensor.open(depth_profile)
        depth_sensor.start(frame_queue)
        time.sleep(3)
        depth_sensor.stop()
        depth_sensor.close()
        
        # Verify we got frames during playback
        assert frame_queue.poll_for_frame(), "No frames received during playback"
        
        # Release all references
        playback = None
        depth_sensor = None
        frame_queue = None
    
    finally:
        # Cleanup temporary file - use shutil for Windows file locking issues
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
