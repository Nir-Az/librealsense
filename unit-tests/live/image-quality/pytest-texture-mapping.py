# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
Texture Mapping Image Quality Test

Tests accuracy of depth-to-color alignment (texture mapping) using calibrated target.
Verifies both color accuracy and depth accuracy on aligned frames.
Requires lab setup with ArUco markers (IDs 4,5,6,7) and combined color/depth calibration target.

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
    pytest.mark.device("D400*"),
    pytest.mark.skip(reason="Requires special lab setup with ArUco markers and texture mapping target"),
    pytest.mark.live
]

NUM_FRAMES = 100
COLOR_TOLERANCE = 60
DEPTH_TOLERANCE = 0.05  # meters
FRAMES_PASS_THRESHOLD = 0.8
EXPECTED_DEPTH = 0.53  # meters
R = 20  # Sampling radius around center (pixels)

# Expected colors for 3x3 grid
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
def aligned_pipeline(test_device):
    """Setup depth and color streaming with alignment."""
    dev, ctx = test_device
    pipe = rs.pipeline(ctx)
    yield pipe, ctx, dev
    try:
        pipe.stop()
        cv2.destroyAllWindows()
    except:
        pass


def test_texture_mapping_basic(aligned_pipeline):
    """Test texture mapping at 1280x720@30fps for both depth and color."""
    pipe, ctx, dev = aligned_pipeline
    _run_texture_mapping_test(pipe, ctx, dev, (1280, 720), 30, (1280, 720), 30)


@pytest.mark.parametrize("depth_cfg,color_cfg", [
    pytest.param(((640, 480), 30), ((640, 480), 30), marks=pytest.mark.nightly),
    pytest.param(((1280, 720), 30), ((1280, 720), 30), marks=pytest.mark.nightly),
])
def test_texture_mapping_configurations(aligned_pipeline, depth_cfg, color_cfg):
    """Test texture mapping across multiple configurations."""
    pipe, ctx, dev = aligned_pipeline
    depth_res, depth_fps = depth_cfg
    color_res, color_fps = color_cfg
    _run_texture_mapping_test(pipe, ctx, dev, depth_res, depth_fps, color_res, color_fps)


def _run_texture_mapping_test(pipe, ctx, dev, depth_res, depth_fps, color_res, color_fps):
    """Run texture mapping test for given configuration."""
    cfg = rs.config()
    cfg.enable_stream(rs.stream.depth, depth_res[0], depth_res[1], rs.format.z16, depth_fps)
    cfg.enable_stream(rs.stream.color, color_res[0], color_res[1], rs.format.bgr8, color_fps)
    
    if not cfg.can_resolve(pipe):
        pytest.skip(f"Configuration not supported: Depth {depth_res}@{depth_fps}fps, Color {color_res}@{color_fps}fps")
    
    pipeline_profile = pipe.start(cfg)
    depth_sensor = pipeline_profile.get_device().first_depth_sensor()
    depth_scale = depth_sensor.get_depth_scale()
    
    # Skip initial frames
    for _ in range(60):
        pipe.wait_for_frames()
    
    # Setup alignment to color
    align = rs.align(rs.stream.color)
    
    # Find ArUco markers
    find_roi_location(pipe, (4, 5, 6, 7), False)
    
    color_passes = {name: 0 for name in COLOR_NAMES}
    depth_passes = {name: 0 for name in COLOR_NAMES}
    
    for i in range(NUM_FRAMES):
        frames = pipe.wait_for_frames()
        aligned_frames = align.process(frames)
        depth_frame = aligned_frames.get_depth_frame()
        color_frame = aligned_frames.get_color_frame()
        
        if not depth_frame or not color_frame:
            continue
        
        color_frame_roi = get_roi_from_frame(color_frame)
        depth_frame_roi = get_roi_from_frame(depth_frame)
        
        # Check each grid cell
        for idx, (x, y) in enumerate(CENTERS):
            color = COLOR_NAMES[idx]
            expected_rgb = EXPECTED_COLORS[color]
            x, y = int(round(x)), int(round(y))
            
            # Check color accuracy
            b, g, r = (int(v) for v in color_frame_roi[y, x])
            pixel = (r, g, b)
            if is_color_close(pixel, expected_rgb, COLOR_TOLERANCE):
                color_passes[color] += 1
            
            # Check depth accuracy (sample area to reduce noise)
            sample_area = depth_frame_roi[y - R:y + R, x - R:x + R]
            valid_values = sample_area[sample_area >= 300]  # Filter invalid depths
            
            # Skip if too many invalid values
            if valid_values.size < sample_area.size * 0.6:
                continue
            
            raw_depth = valid_values.mean()
            depth_value = raw_depth * depth_scale
            
            if abs(depth_value - EXPECTED_DEPTH) <= DEPTH_TOLERANCE:
                depth_passes[color] += 1
    
    # Verify pass thresholds
    min_passes = int(NUM_FRAMES * FRAMES_PASS_THRESHOLD)
    
    for name, count in color_passes.items():
        assert count >= min_passes, \
            f"{name.title()} color failed: {count}/{NUM_FRAMES} frames passed (need {min_passes})"
    
    for name, count in depth_passes.items():
        assert count >= min_passes, \
            f"{name.title()} depth failed: {count}/{NUM_FRAMES} frames passed (need {min_passes})"
