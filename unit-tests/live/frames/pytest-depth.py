# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2023 RealSense, Inc. All Rights Reserved.

"""
Test depth frame quality and meaningfulness.

This test verifies that:
1. Depth frames are captured successfully
2. Frames contain meaningful depth data (not all zeros or uniform)
3. Depth variance is sufficient across the frame
4. The laser emitter functions properly when enabled

The test checks multiple frames to ensure consistent depth quality.
"""

import pytest
import pyrealsense2 as rs
from rspy import log
from rspy import tests_wrapper as tw
import numpy as np
import os
import time

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.live
]

# Configuration constants
DETAIL_LEVEL = 5  # How far in cm pixels have to be to be considered different distance
BLACK_PIXEL_THRESHOLD = 0.8  # Fail if more than 80% pixels are zero
DEPTH_PERCENTAGE = 0.5  # Percentage of pixels that need different values for meaningful depth
FRAMES_TO_CHECK = 30  # Number of frames to check for meaningful depth
DEBUG_MODE = False  # Set to True to save/display images for debugging


@pytest.fixture(scope="module")
def depth_pipeline_config(module_test_device):
    """
    Module-scoped fixture that sets up and tears down the depth pipeline.
    """
    dev, ctx = module_test_device
    
    # Start wrapper
    tw.start_wrapper(dev)
    
    # Configure pipeline for depth streaming
    cfg = rs.config()
    cfg.enable_stream(rs.stream.depth, rs.format.z16, 30)
    if DEBUG_MODE:
        cfg.enable_stream(rs.stream.color, rs.format.bgr8, 30)
    
    pipeline = rs.pipeline(ctx)
    pipeline_profile = pipeline.start(cfg)
    pipeline.wait_for_frames()
    time.sleep(2)  # Wait for auto-exposure to stabilize
    
    yield {'dev': dev, 'ctx': ctx, 'pipeline': pipeline, 'profile': pipeline_profile}
    
    # Teardown
    pipeline.stop()
    tw.stop_wrapper(dev)


def get_distances(depth_frame):
    """
    Analyze depth frame and return distance distribution.
    
    Args:
        depth_frame: Depth frame to analyze
        
    Returns:
        Tuple of (distances_dict, total_pixels) where distances_dict maps
        rounded depth values to pixel counts
    """
    MAX_METERS = 10  # max distance that can be detected, in meters
    
    depth_m = np.asanyarray(depth_frame.get_data()).astype(np.float32) * depth_frame.get_units()
    
    valid_mask = (depth_m < MAX_METERS)
    valid_depths = depth_m[valid_mask]  # ignore invalid pixels
    
    # convert to cm and round according to DETAIL_LEVEL
    rounded_depths = (np.floor(valid_depths * 100.0 / DETAIL_LEVEL) * DETAIL_LEVEL).astype(np.int32)
    
    unique_vals, counts = np.unique(rounded_depths, return_counts=True)
    
    dists = dict(zip(unique_vals.tolist(), counts.tolist()))
    total = valid_depths.size
    
    log.d("Distances detected in frame are:", dists)
    return dists, total


def is_depth_meaningful(pipeline, save_image=False, show_image=False):
    """
    Checks if the camera is showing a frame with meaningful depth.
    
    Args:
        pipeline: Active pipeline to get frames from
        save_image: If True, save the depth image to disk
        show_image: If True, display the depth image
        
    Returns:
        Tuple of (is_meaningful, num_blank_pixels)
    """
    frames = pipeline.wait_for_frames()
    depth = frames.get_depth_frame()
    color = frames.get_color_frame() if DEBUG_MODE else None
    
    if not depth:
        log.f("Error getting depth frame")
        return False, 0
    
    if DEBUG_MODE and not color:
        log.e("Error getting color frame")
    
    dists, total = get_distances(depth)
    num_blank_pixels = dists.get(0, 0)
    
    # Check for mostly black image
    if num_blank_pixels > total * BLACK_PIXEL_THRESHOLD:
        percent_blank = 100.0 * num_blank_pixels / total if total > 0 else 0
        log.f(f"Too many blank pixels: {num_blank_pixels}/{total} ({percent_blank:.1f}%)")
        return False, num_blank_pixels
    
    # Remove zero values from dists for meaningful depth check
    dists_no_zero = {k: v for k, v in dists.items() if k != 0}
    
    if save_image or show_image:
        frames_to_image(depth, color, save_image, show_image)
    
    # If any distance is the same on more than DEPTH_PERCENTAGE of the pixels, no meaningful depth
    # Find the largest non-zero depth bin
    max_nonzero_count = max(dists_no_zero.values()) if dists_no_zero else 0
    max_nonzero_percent = 100.0 * max_nonzero_count / total if total > 0 else 0
    meaningful_depth = not (max_nonzero_count > total * DEPTH_PERCENTAGE)
    fill_rate = 100.0 * (total - num_blank_pixels) / total if total > 0 else 0
    
    log.i(f"Depth fill rate: {fill_rate:.1f}% (blank pixels: {num_blank_pixels}/{total}), "
          f"meaningful depth: {meaningful_depth} (largest bin: {max_nonzero_percent:.1f}% - "
          f"max allowed {DEPTH_PERCENTAGE * 100:.1f}%)")
    
    return meaningful_depth, num_blank_pixels


def frames_to_image(depth, color, save, display):
    """
    Transform depth and color frames to an image and save/display.
    
    If color frame is given, it will be concatenated with the depth frame.
    
    Args:
        depth: Depth frame
        color: Color frame (optional)
        save: If True, save image to disk
        display: If True, display image in a window
    """
    import cv2
    
    colorizer = rs.colorizer()
    depth_image = np.asanyarray(colorizer.colorize(depth).get_data())
    img = depth_image
    
    if color:  # if color frame was successfully captured, merge it and the depth frame
        from scipy.ndimage import zoom
        color_image = np.asanyarray(color.get_data())
        depth_rows, _, _ = depth_image.shape
        color_rows, _, _ = color_image.shape
        # resize the image with the higher resolution to look like the smaller one
        if depth_rows < color_rows:
            color_image = zoom(color_image, (depth_rows / color_rows, depth_rows / color_rows, 1))
        elif color_rows < depth_rows:
            depth_image = zoom(depth_image, (color_rows / depth_rows, color_rows / depth_rows, 1))
        img = np.concatenate((depth_image, color_image), axis=1)
    
    if save:
        file_name = f"output_stream.png"
        log.i("Saved image in", os.getcwd() + "\\" + file_name)
        cv2.imwrite(file_name, img)
    
    if display:
        window_title = "Output Stream"
        cv2.imshow(window_title, img)
        while cv2.getWindowProperty(window_title, cv2.WND_PROP_VISIBLE) > 0:
            k = cv2.waitKey(33)
            if k == 27:  # Esc key to stop
                cv2.destroyAllWindows()
                break
            elif k == -1:  # normally -1 returned
                pass


def test_depth_frame_with_laser_on(depth_pipeline_config):
    """
    Test that depth frames contain meaningful depth data with laser enabled.
    
    This test:
    1. Enables the laser emitter at maximum power
    2. Captures multiple frames (up to FRAMES_TO_CHECK)
    3. Verifies that at least one frame has meaningful depth
    4. Checks that pixels aren't mostly black (< 80% blank)
    5. Checks that depth has sufficient variance (no single distance > 50% of pixels)
    """
    dev = depth_pipeline_config['dev']
    pipeline = depth_pipeline_config['pipeline']
    pipeline_profile = depth_pipeline_config['profile']
    
    log.i(f"Testing depth frame - laser ON - {dev.get_info(rs.camera_info.name)}")
    
    # Enable laser at maximum power
    sensor = pipeline_profile.get_device().first_depth_sensor()
    if sensor.supports(rs.option.laser_power):
        max_laser_power = sensor.get_option_range(rs.option.laser_power).max
        sensor.set_option(rs.option.laser_power, max_laser_power)
        log.d(f"Set laser power to maximum: {max_laser_power}")
    
    sensor.set_option(rs.option.emitter_enabled, 1)  # Enable emitter
    log.d("Emitter enabled")
    
    has_depth = False
    last_blank_pixels = 0
    
    # Check multiple frames to try and detect meaningful depth
    for frame_num in range(FRAMES_TO_CHECK):
        has_depth, blank_pixels = is_depth_meaningful(
            pipeline, 
            save_image=DEBUG_MODE, 
            show_image=DEBUG_MODE
        )
        last_blank_pixels = blank_pixels
        
        if has_depth:
            log.i(f"Found meaningful depth in frame #{frame_num + 1}")
            break
        else:
            log.d(f"Frame #{frame_num + 1}/{FRAMES_TO_CHECK} did not have meaningful depth")
    
    assert has_depth, \
        f"No meaningful depth detected in {FRAMES_TO_CHECK} frames " \
        f"(last frame had {last_blank_pixels} blank pixels)"
