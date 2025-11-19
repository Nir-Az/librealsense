# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2023 RealSense, Inc. All Rights Reserved.

"""
Record Software Device Test

Tests recording frames from a software device (synthetic frames) and playing them back.
Verifies that synthetic video and motion frames can be recorded and their data is preserved.
"""

import pytest
import pyrealsense2 as rs
import os
import tempfile
import numpy as np

# Module-level markers
pytestmark = [
    pytest.mark.live
]

# Test configuration
W = 640
H = 480
BPP = 2


def prepare_video_stream():
    """Create a synthetic video stream with intrinsics."""
    depth_intrinsics = rs.intrinsics()
    depth_intrinsics.width = W
    depth_intrinsics.height = H
    depth_intrinsics.ppx = W / 2
    depth_intrinsics.ppy = H / 2
    depth_intrinsics.fx = W
    depth_intrinsics.fy = H
    depth_intrinsics.model = rs.distortion.brown_conrady
    depth_intrinsics.coeffs = [0, 0, 0, 0, 0]
    
    vs = rs.video_stream()
    vs.type = rs.stream.depth
    vs.index = 0
    vs.uid = 0
    vs.width = W
    vs.height = H
    vs.fps = 60
    vs.bpp = BPP
    vs.fmt = rs.format.z16
    vs.intrinsics = depth_intrinsics
    return vs


def prepare_motion_stream():
    """Create a synthetic motion stream with intrinsics."""
    motion_intrinsics = rs.motion_device_intrinsic()
    motion_intrinsics.data = [[1.0] * 4] * 3
    motion_intrinsics.noise_variances = [2, 2, 2]
    motion_intrinsics.bias_variances = [3, 3, 3]
    
    motion_stream = rs.motion_stream()
    motion_stream.type = rs.stream.accel
    motion_stream.index = 0
    motion_stream.uid = 1
    motion_stream.fps = 200
    motion_stream.fmt = rs.format.motion_raw
    motion_stream.intrinsics = motion_intrinsics
    
    return motion_stream


def prepare_depth_frame(pixels, depth_stream_profile):
    """Create a synthetic depth frame."""
    video_frame = rs.software_video_frame()
    video_frame.pixels = pixels
    video_frame.bpp = BPP
    video_frame.stride = W * BPP
    video_frame.timestamp = 10000
    video_frame.domain = rs.timestamp_domain.hardware_clock
    video_frame.frame_number = 0
    video_frame.profile = depth_stream_profile.as_video_stream_profile()
    return video_frame


def prepare_motion_frame(motion_data, motion_stream_profile):
    """Create a synthetic motion frame."""
    motion_frame = rs.software_motion_frame()
    motion_frame.data = motion_data
    motion_frame.timestamp = 20000
    motion_frame.domain = rs.timestamp_domain.hardware_clock
    motion_frame.frame_number = 0
    motion_frame.profile = motion_stream_profile.as_motion_stream_profile()
    return motion_frame


def test_record_software_device():
    """Test recording and playback of software device frames."""
    temp_dir = tempfile.mkdtemp()
    filename = os.path.join(temp_dir, "recording.bag")
    
    try:
        # Create synthetic data
        pixels = np.array([100 for i in range(W * H * BPP)], dtype=np.uint8)
        motion_data = rs.vector()
        motion_data.x = 1.0
        motion_data.y = 2.0
        motion_data.z = 3.0
        
        # Setup software device
        sd = rs.software_device()
        sensor = sd.add_sensor("Synthetic")
        
        vs = prepare_video_stream()
        depth_stream_profile = sensor.add_video_stream(vs).as_video_stream_profile()
        
        motion_stream = prepare_motion_stream()
        motion_stream_profile = sensor.add_motion_stream(motion_stream)
        
        sync = rs.syncer()
        stream_profiles = [depth_stream_profile, motion_stream_profile]
        
        video_frame = prepare_depth_frame(pixels, depth_stream_profile)
        motion_frame = prepare_motion_frame(motion_data, motion_stream_profile)
        
        # Record frames
        recorder = rs.recorder(filename, sd)
        sensor.open(stream_profiles)
        sensor.start(sync)
        
        sensor.on_video_frame(video_frame)
        sensor.on_motion_frame(motion_frame)
        
        sensor.stop()
        sensor.close()
        
        recorder.pause()
        recorder = None
        
        # Playback and verify
        ctx = rs.context()
        player_dev = ctx.load_device(filename)
        player_dev.set_real_time(False)
        player_sync = rs.syncer()
        s = player_dev.query_sensors()[0]
        s.open(s.get_stream_profiles())
        s.start(player_sync)
        
        recorded_depth = None
        recorded_accel = None
        
        success, fset = player_sync.try_wait_for_frames()
        while success:
            if fset.first_or_default(rs.stream.depth):
                recorded_depth = fset.first_or_default(rs.stream.depth)
            if fset.first_or_default(rs.stream.accel):
                recorded_accel = fset.first_or_default(rs.stream.accel)
            success, fset = player_sync.try_wait_for_frames()
        
        # Verify depth frame
        assert recorded_depth is not None, "No depth frame recorded"
        recorded_depth_data = np.hstack(np.asarray(recorded_depth.as_depth_frame().get_data())).view(dtype=np.uint8)
        for i, pixel in enumerate(pixels):
            assert pixel == recorded_depth_data[i], f"Depth pixel mismatch at {i}"
        
        assert video_frame.frame_number == recorded_depth.get_frame_number(), "Frame number mismatch"
        assert video_frame.domain == recorded_depth.get_frame_timestamp_domain(), "Timestamp domain mismatch"
        assert video_frame.timestamp == recorded_depth.get_timestamp(), "Timestamp mismatch"
        
        # Verify motion frame
        assert recorded_accel is not None, "No accel frame recorded"
        recorded_accel_data = recorded_accel.as_motion_frame().get_motion_data()
        assert motion_data.x == recorded_accel_data.x, "Motion X mismatch"
        assert motion_data.y == recorded_accel_data.y, "Motion Y mismatch"
        assert motion_data.z == recorded_accel_data.z, "Motion Z mismatch"
        assert motion_frame.frame_number == recorded_accel.get_frame_number(), "Motion frame number mismatch"
        assert motion_frame.domain == recorded_accel.get_frame_timestamp_domain(), "Motion domain mismatch"
        assert motion_frame.timestamp == recorded_accel.get_timestamp(), "Motion timestamp mismatch"
        
        s.stop()
        s.close()
        
        # Release all references before cleanup
        player_sync = None
        s = None
        player_dev = None
        ctx = None
        
    finally:
        # Cleanup - use ignore_errors for Windows file locking issues
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
