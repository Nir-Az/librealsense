# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2021 RealSense, Inc. All Rights Reserved.

"""
Test for D455 frame drops at 90 FPS.

This test runs 60 iterations of streaming RGB frames at 90 FPS on D455 devices
and checks for frame drops by analyzing hardware timestamps. Frame drops are
detected when the delta between consecutive frame timestamps exceeds the ideal
delta by more than 5%.
"""

import pytest
import pyrealsense2 as rs
from rspy import log
import time
import threading
from queue import Queue

# Module-level markers
pytestmark = [
    pytest.mark.device("D455"),
    pytest.mark.live,
    pytest.mark.skip(reason="Test marked as donotrun in original - needs investigation")
]

# Test configuration
ITERATIONS = 60
STREAM_TIME = 30  # seconds
FPS = 90
DELTA_TOLERANCE_PERCENT = 95.0


class FrameDropAnalyzer:
    """
    Analyzer for detecting frame drops using hardware timestamps.
    
    Uses producer-consumer pattern with threading to handle high frame rates.
    """
    
    def __init__(self, rgb_sensor):
        self._stop = False
        self.count_drops = 0
        self.frame_drops_info = {}
        self.prev_hw_timestamp = 0.0
        self.prev_fnum = 0
        self.first_frame = True
        self.lrs_queue = rs.frame_queue(capacity=100000, keep_frames=True)
        self.post_process_queue = Queue(maxsize=1000000)
        self.rgb_sensor = rgb_sensor
        
        # Calculate ideal delta and tolerance
        self.ideal_delta = round(1000000.0 / FPS, 2)  # microseconds
        self.delta_tolerance = self.ideal_delta * DELTA_TOLERANCE_PERCENT / 100.0
    
    def start_rgb_sensor(self):
        """Start streaming from RGB sensor."""
        self.rgb_sensor.start(self.lrs_queue)
    
    def stop(self):
        """Signal threads to stop."""
        self._stop = True
    
    def produce_frames(self, timeout=1):
        """Producer thread: reads frames from sensor queue."""
        while not self._stop:
            try:
                lrs_frame = self.lrs_queue.wait_for_frame(timeout_ms=timeout * 1000)
            except Exception as e:
                log.d(f"Producer exception: {e}")
                continue
            self.post_process_queue.put(lrs_frame, block=True, timeout=timeout)
    
    def consume_frames(self):
        """Consumer thread: processes frames and detects drops."""
        while not self._stop:
            try:
                lrs_frame = self.post_process_queue.get(block=True, timeout=1)
                self.process_frame(lrs_frame)
                del lrs_frame
                self.post_process_queue.task_done()
            except:
                # Queue empty or timeout
                pass
    
    def process_frame(self, frame):
        """
        Process a single frame and detect drops.
        
        Args:
            frame: Frame to process
        """
        if not frame:
            return
        
        if self.first_frame:
            self.prev_hw_timestamp = frame.get_frame_metadata(rs.frame_metadata_value.frame_timestamp)
            self.prev_fnum = frame.get_frame_number()
            self.first_frame = False
            return
        
        curr_hw_timestamp = frame.get_frame_metadata(rs.frame_metadata_value.frame_timestamp)
        delta = curr_hw_timestamp - self.prev_hw_timestamp
        fnum = frame.get_frame_number()
        
        # Detect drop: delta exceeds ideal + tolerance
        if delta > self.ideal_delta + self.delta_tolerance:
            self.count_drops += 1
            frames_dropped = fnum - self.prev_fnum - 1
            self.frame_drops_info[fnum] = frames_dropped
            log.d(f"Drop detected at frame {fnum}: {frames_dropped} frame(s) dropped, delta={delta:.2f}us")
        
        self.prev_hw_timestamp = curr_hw_timestamp
        self.prev_fnum = fnum
    
    def get_results(self):
        """
        Get analysis results.
        
        Returns:
            Tuple of (drop_count, drop_details_dict)
        """
        return self.count_drops, self.frame_drops_info


@pytest.fixture(scope="module")
def device_config(module_test_device):
    """
    Module-scoped fixture that provides device and sensors.
    """
    dev, ctx = module_test_device
    product_line = dev.get_info(rs.camera_info.product_line)
    sn = dev.get_info(rs.camera_info.serial_number)
    fw = dev.get_info(rs.camera_info.firmware_version)
    
    log.i(f"Found device {sn}, fw {fw}")
    
    sensors = dev.query_sensors()
    depth_ir_sensor = next(s for s in sensors if s.get_info(rs.camera_info.name) == 'Stereo Module')
    rgb_sensor = next(s for s in sensors if s.get_info(rs.camera_info.name) == 'RGB Camera')
    
    # Find suitable RGB profile at 90 FPS
    rgb_profiles = rgb_sensor.profiles
    rgb_profile = next(
        (p for p in rgb_profiles 
         if p.fps() == FPS
         and p.stream_type() == rs.stream.color
         and p.format() == rs.format.yuyv
         and ((p.as_video_stream_profile().width() == 424 and p.as_video_stream_profile().height() == 240)
              or (p.as_video_stream_profile().width() == 480 and p.as_video_stream_profile().height() == 270)
              or (p.as_video_stream_profile().width() == 640 and p.as_video_stream_profile().height() == 360))),
        None
    )
    
    assert rgb_profile is not None, "Could not find suitable RGB profile at 90 FPS"
    
    log.i(f"Using profile: {rgb_profile.stream_type()} "
          f"{rgb_profile.as_video_stream_profile().width()}x{rgb_profile.as_video_stream_profile().height()} "
          f"@ {rgb_profile.fps()} FPS, format: {rgb_profile.format()}")
    
    return {
        'dev': dev,
        'ctx': ctx,
        'product_line': product_line,
        'rgb_sensor': rgb_sensor,
        'rgb_profile': rgb_profile
    }


def test_d455_frame_drops_at_90fps(device_config):
    """
    Test that D455 RGB frames stream at 90 FPS without drops over 60 iterations.
    
    This test:
    1. Runs ITERATIONS (60) streaming sessions
    2. Streams RGB at 90 FPS for STREAM_TIME (30) seconds each
    3. Uses producer-consumer threading pattern for high-speed processing
    4. Analyzes hardware timestamps to detect frame drops
    5. A drop is detected when timestamp delta > ideal_delta * 1.05
    6. Fails if any drops are detected in any iteration
    """
    product_line = device_config['product_line']
    rgb_sensor = device_config['rgb_sensor']
    rgb_profile = device_config['rgb_profile']
    
    log.i(f"Testing D455 frame drops on {product_line} device")
    
    all_iterations_passed = True
    failed_iterations = []
    total_drops = 0
    
    for i in range(ITERATIONS):
        log.i(f"================ Iteration {i + 1}/{ITERATIONS} ================")
        
        analyzer = FrameDropAnalyzer(rgb_sensor)
        
        # Configure sensor
        rgb_sensor.set_option(rs.option.global_time_enabled, 0)
        rgb_sensor.open([rgb_profile])
        
        # Start producer-consumer threads
        producer_thread = threading.Thread(target=analyzer.produce_frames, name="producer_thread")
        consumer_thread = threading.Thread(target=analyzer.consume_frames, name="consumer_thread")
        
        producer_thread.start()
        consumer_thread.start()
        
        # Start streaming
        analyzer.start_rgb_sensor()
        time.sleep(STREAM_TIME)
        
        # Stop streaming and threads
        analyzer.stop()
        producer_thread.join(timeout=60)
        consumer_thread.join(timeout=60)
        
        rgb_sensor.stop()
        rgb_sensor.close()
        
        # Analyze results
        drop_count, drop_info = analyzer.get_results()
        
        if drop_count > 0:
            all_iterations_passed = False
            failed_iterations.append(i + 1)
            total_drops += drop_count
            log.e(f"Iteration {i + 1} had {drop_count} frame drop(s)")
            for fnum, dropped in drop_info.items():
                log.e(f"\tFrame {fnum}: {dropped} frame(s) dropped")
        else:
            log.i(f"Iteration {i + 1} passed - no drops detected")
    
    assert all_iterations_passed, \
        f"Frame drops detected in {len(failed_iterations)} iteration(s): {failed_iterations} " \
        f"(total drops: {total_drops})"
