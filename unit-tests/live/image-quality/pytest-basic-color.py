# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
Basic Color Image Quality Test

Tests color accuracy by detecting a 3x3 grid of colored squares on an A4 target.
Requires lab setup with ArUco markers (IDs 0,1,2,3) and color calibration target.

Note: Test is disabled by default - requires special lab equipment and setup.
"""

import pytest
import pyrealsense2 as rs
import numpy as np
import cv2

# Import helper functions
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from iq_helper import find_roi_location, get_roi_from_frame, is_color_close, WIDTH, HEIGHT

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.live
]

NUM_FRAMES = 100
COLOR_TOLERANCE = 60
FRAMES_PASS_THRESHOLD = 0.8
DEBUG_MODE = False

# Expected colors for 3x3 grid (row-major order)
EXPECTED_COLORS = {
    "red": (132, 60, 60),
    "green": (40, 84, 72),
    "blue": (20, 67, 103),
    "black": (35, 35, 35),
    "white": (150, 150, 150),
    "gray": (90, 90, 90),
    "purple": (56, 72, 98),
    "orange": (136, 86, 70),
    "yellow": (166, 142, 80),
}

COLOR_NAMES = list(EXPECTED_COLORS.keys())

# Grid center sampling points
xs = [1.5 * WIDTH / 6.0, WIDTH / 2.0, 4.5 * WIDTH / 6.0]
ys = [1.5 * HEIGHT / 6.0, HEIGHT / 2.0, 4.5 * HEIGHT / 6.0]
CENTERS = [(x, y) for y in ys for x in xs]


@pytest.fixture
def color_pipeline(test_device):
    """Setup color streaming pipeline."""
    dev, ctx = test_device
    pipe = rs.pipeline(ctx)
    yield pipe, ctx
    try:
        pipe.stop()
        cv2.destroyAllWindows()
    except:
        pass


def test_basic_color_1280x720_30fps(color_pipeline):
    """Test color accuracy at 1280x720@30fps."""
    pipe, ctx = color_pipeline
    _run_color_test(pipe, ctx, (1280, 720), 30)


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
def test_basic_color_configurations(color_pipeline, resolution, fps):
    """Test color accuracy across multiple resolutions and frame rates."""
    pipe, ctx = color_pipeline
    _run_color_test(pipe, ctx, resolution, fps)


def _run_color_test(pipe, ctx, resolution, fps):
    """Run color accuracy test for given configuration."""
    cfg = rs.config()
    cfg.enable_stream(rs.stream.color, resolution[0], resolution[1], rs.format.bgr8, fps)
    
    if not cfg.can_resolve(pipe):
        pytest.skip(f"Configuration {resolution[0]}x{resolution[1]}@{fps}fps not supported")
    
    pipe.start(cfg)
    
    # Skip initial frames
    for _ in range(60):
        pipe.wait_for_frames()
    
    # Find ArUco markers and get transformation matrix
    find_roi_location(pipe, (0, 1, 2, 3), DEBUG_MODE)
    
    # Sample colors from grid centers
    color_match_count = {color: 0 for color in EXPECTED_COLORS.keys()}
    
    for i in range(NUM_FRAMES):
        frames = pipe.wait_for_frames()
        color_frame = frames.get_color_frame()
        color_frame_roi = get_roi_from_frame(color_frame)
        
        for idx, (x, y) in enumerate(CENTERS):
            color = COLOR_NAMES[idx]
            expected_rgb = EXPECTED_COLORS[color]
            x, y = int(round(x)), int(round(y))
            
            b, g, r = (int(v) for v in color_frame_roi[y, x])
            pixel = (r, g, b)
            
            if is_color_close(pixel, expected_rgb, COLOR_TOLERANCE):
                color_match_count[color] += 1
    
    # Verify pass threshold
    min_passes = int(NUM_FRAMES * FRAMES_PASS_THRESHOLD)
    for name, count in color_match_count.items():
        assert count >= min_passes, \
            f"{name.title()} failed: {count}/{NUM_FRAMES} frames passed (need {min_passes})"
