# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2021 RealSense, Inc. All Rights Reserved.

"""
Test for color frame drops.

This test runs multiple iterations of streaming color frames at high FPS (60)
and checks for frame drops by analyzing hardware timestamps. Frame drops are
detected when the delta between consecutive frame timestamps exceeds the
expected delta by more than 95%.
"""

import pytest
import pyrealsense2 as rs
from rspy import log
from lrs_frame_queue_manager import LRSFrameQueueManager
import time

# Module-level markers
pytestmark = [
    pytest.mark.device("D400*"),
    pytest.mark.live,
    pytest.mark.skip(reason="Test marked as donotrun in original - needs investigation")
]

# Test configuration
ITERATIONS = 4
SLEEP_TIME = 10  # seconds
FPS = 60
WIDTH = 640
HEIGHT = 480
FORMAT = rs.format.rgb8


@pytest.fixture(scope="module")
def device_config(module_test_device):
    """
    Module-scoped fixture that provides device and context.
    """
    dev, ctx = module_test_device
    product_line = dev.get_info(rs.camera_info.product_line)
    
    # Configure color sensor
    color_sensor = dev.first_color_sensor()
    if color_sensor.supports(rs.option.auto_exposure_priority):
        color_sensor.set_option(rs.option.auto_exposure_priority, 0)
    
    return {'dev': dev, 'ctx': ctx, 'product_line': product_line}


def test_color_frame_drops(device_config):
    """
    Test that color frames stream without drops over multiple iterations.
    
    This test:
    1. Runs ITERATIONS (4) streaming sessions
    2. Streams color at 60 FPS for SLEEP_TIME (10) seconds each
    3. Collects hardware timestamps for all frames
    4. Analyzes timestamp deltas to detect frame drops
    5. A drop is detected when delta > expected_delta * 1.95
    6. Fails if any drops are detected in any iteration
    """
    dev = device_config['dev']
    ctx = device_config['ctx']
    product_line = device_config['product_line']
    
    log.i(f"Testing color frame drops on {product_line} device")
    
    lrs_fq = LRSFrameQueueManager()
    pipe = rs.pipeline(ctx)
    
    hw_timestamps = []
    
    def timestamp_callback(frame, ts):
        """Callback to collect hardware timestamps"""
        nonlocal hw_timestamps
        hw_timestamps.append(frame.get_frame_metadata(rs.frame_metadata_value.frame_timestamp))
    
    lrs_fq.register_callback(timestamp_callback)
    
    all_iterations_passed = True
    failed_iterations = []
    
    for i in range(ITERATIONS):
        log.i(f"Iteration #{i + 1}/{ITERATIONS}")
        hw_timestamps = []
        
        lrs_fq.start()
        
        log.d(f"\tStart stream")
        cfg = rs.config()
        cfg.enable_stream(rs.stream.color, WIDTH, HEIGHT, FORMAT, FPS)
        pipe.start(cfg, lrs_fq.lrs_queue)
        
        time.sleep(SLEEP_TIME)
        
        log.d(f"\tStop stream")
        pipe.stop()
        lrs_fq.stop()
        
        # Analyze timestamps for drops
        expected_delta = 1000 / FPS  # Expected time between frames in microseconds / 1000
        deltas_ms = [(ts1 - ts2) / 1000 for ts1, ts2 in zip(hw_timestamps[1:], hw_timestamps[:-1])]
        
        iteration_has_drops = False
        drop_details = []
        
        for idx, delta in enumerate(deltas_ms, 1):
            if delta > (expected_delta * 1.95):
                iteration_has_drops = True
                drop_details.append(f"Drop #{idx}: actual delta {delta:.2f}ms vs expected {expected_delta:.2f}ms")
        
        if iteration_has_drops:
            all_iterations_passed = False
            failed_iterations.append(i + 1)
            log.e(f"\tIteration #{i + 1} had frame drops:")
            for detail in drop_details:
                log.e(f"\t\t{detail}")
        else:
            log.i(f"\tIteration #{i + 1} passed - no drops detected")
    
    assert all_iterations_passed, \
        f"Frame drops detected in iteration(s): {failed_iterations}"
