# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
Basic Depth Image Quality Test

Tests depth accuracy at specific points on a calibrated target setup.
Requires lab setup with ArUco markers (IDs 4,5,6,7), cube at known distance, and background.

Note: Test is disabled by default - requires special lab equipment and setup.
"""

import pytest
import pyrealsense2 as rs
import numpy as np
import cv2
import time

# Import helper functions
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from iq_helper import find_roi_location, get_roi_from_frame, WIDTH, HEIGHT

# Module-level markers
pytestmark = [
    pytest.mark.device("D400*"),
    pytest.mark.skip(reason="Requires special lab setup with ArUco markers and depth calibration target"),
    pytest.mark.live
]

NUM_FRAMES = 100
DEPTH_TOLERANCE = 0.05  # meters
FRAMES_PASS_THRESHOLD = 0.8

DISTANCE_FROM_CUBE = 0.53  # meters
DISTANCE_FROM_BACKGROUND = 0.67  # meters


@pytest.fixture
def depth_pipeline(test_device):
    """Setup depth and infrared streaming pipeline."""
    dev, ctx = test_device
    pipe = rs.pipeline(ctx)
    yield pipe, ctx, dev
    try:
        pipe.stop()
        cv2.destroyAllWindows()
    except:
        pass


def test_basic_depth_1280x720_30fps(depth_pipeline):
    """Test depth accuracy at 1280x720@30fps."""
    pipe, ctx, dev = depth_pipeline
    _run_depth_test(pipe, ctx, dev, (1280, 720), 30)


@pytest.mark.parametrize("resolution,fps", [
    pytest.param((640, 480), 15, marks=pytest.mark.nightly),
    pytest.param((640, 480), 30, marks=pytest.mark.nightly),
    pytest.param((640, 480), 60, marks=pytest.mark.nightly),
    pytest.param((848, 480), 15, marks=pytest.mark.nightly),
    pytest.param((848, 480), 30, marks=pytest.mark.nightly),
    pytest.param((848, 480), 60, marks=pytest.mark.nightly),
    pytest.param((1280, 720), 5, marks=pytest.mark.nightly),
    pytest.param((1280, 720), 10, marks=pytest.mark.nightly),
    pytest.param((1280, 720), 15, marks=pytest.mark.nightly),
])
def test_basic_depth_configurations(depth_pipeline, resolution, fps):
    """Test depth accuracy across multiple resolutions and frame rates."""
    pipe, ctx, dev = depth_pipeline
    _run_depth_test(pipe, ctx, dev, resolution, fps)


def _run_depth_test(pipe, ctx, dev, resolution, fps):
    """Run depth accuracy test for given configuration."""
    cfg = rs.config()
    cfg.enable_stream(rs.stream.depth, resolution[0], resolution[1], rs.format.z16, fps)
    cfg.enable_stream(rs.stream.infrared, 1, 640, 480, rs.format.y8, 30)  # For ArUco detection
    
    if not cfg.can_resolve(pipe):
        pytest.skip(f"Configuration {resolution[0]}x{resolution[1]}@{fps}fps not supported")
    
    profile = pipe.start(cfg)
    time.sleep(2)
    
    depth_sensor = profile.get_device().first_depth_sensor()
    depth_scale = depth_sensor.get_depth_scale()
    
    # Find ArUco markers and get transformation matrix
    find_roi_location(pipe, (4, 5, 6, 7), False)
    
    # Known test points and expected depths
    depth_points = {
        "cube": ((HEIGHT // 2, WIDTH // 2), DISTANCE_FROM_CUBE),
        "background": ((HEIGHT // 2, int(WIDTH * 0.1)), DISTANCE_FROM_BACKGROUND)
    }
    
    depth_passes = {name: 0 for name in depth_points}
    
    for i in range(NUM_FRAMES):
        frames = pipe.wait_for_frames()
        depth_frame = frames.get_depth_frame()
        
        if not depth_frame:
            continue
        
        depth_image = get_roi_from_frame(depth_frame)
        
        for point_name, ((x, y), expected_depth) in depth_points.items():
            raw_depth = depth_image[y, x]
            depth_value = raw_depth * depth_scale
            
            if abs(depth_value - expected_depth) <= DEPTH_TOLERANCE:
                depth_passes[point_name] += 1
    
    # Verify pass threshold
    min_passes = int(NUM_FRAMES * FRAMES_PASS_THRESHOLD)
    for point_name, count in depth_passes.items():
        assert count >= min_passes, \
            f"{point_name.title()} failed: {count}/{NUM_FRAMES} frames passed (need {min_passes})"
