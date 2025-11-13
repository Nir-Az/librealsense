# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
Playback stress test.

This test performs 250 iterations of loading and playing back a bag file to verify
stability and detect potential deadlocks or memory issues. Each iteration validates
that playback starts, stops correctly, and produces the expected number of frames.

Note: This is a nightly test that takes approximately 25 minutes to complete.
"""

import pytest
import pyrealsense2 as rs
import os
from rspy import log, repo
from playback_helper import PlaybackStatusVerifier

# Mark this as a nightly test with extended timeout
pytestmark = [
    pytest.mark.nightly,
    pytest.mark.timeout(1500)  # 25 minutes (vs default 200 seconds)
]

# Test configuration
FRAMES_IN_BAG_FILE = 64
NUMBER_OF_ITERATIONS = 250


@pytest.fixture(scope="module")
def bag_file():
    """
    Locate the test bag file.
    
    Returns:
        Path to the bag file used for playback testing
    """
    file_path = os.path.join(repo.build, 'unit-tests', 'recordings', 'all_combinations_depth_color.bag')
    
    if not os.path.exists(file_path):
        pytest.skip(f"Bag file not found: {file_path}")
    
    log.d('Playback file:', file_path)
    return file_path


def test_playback_stress(bag_file):
    """
    Stress test playback by repeatedly loading and playing a bag file.
    
    This test performs 250 iterations of:
    1. Loading a bag file into a context
    2. Opening and starting all sensors
    3. Waiting for playback to start and stop
    4. Verifying status changes and frame count
    5. Properly cleaning up sensors
    
    The test validates:
    - No deadlocks occur during repeated playback
    - Playback status transitions correctly (playing -> stopped)
    - All expected frames are received
    - Resources are properly cleaned up between iterations
    """
    log.i(f"Starting playback stress test with {NUMBER_OF_ITERATIONS} iterations")
    log.i(f"Playing back: {bag_file}")
    
    for iteration in range(NUMBER_OF_ITERATIONS):
        log.d(f"Iteration #{iteration + 1}/{NUMBER_OF_ITERATIONS}")
        
        # Track frames received in this iteration
        frames_count = 0
        
        def frame_callback(f):
            nonlocal frames_count
            frames_count += 1
        
        dev = None
        sensors = []
        
        try:
            # Load the bag file
            ctx = rs.context()
            dev = ctx.load_device(bag_file)
            psv = PlaybackStatusVerifier(dev)
            dev.set_real_time(False)
            
            sensors = dev.query_sensors()
            
            # Open all sensors
            log.d("Opening sensors")
            for sensor in sensors:
                sensor.open(sensor.get_stream_profiles())
            
            # Start all sensors with callback
            log.d("Starting sensors")
            for sensor in sensors:
                sensor.start(frame_callback)
            
            # Wait for playback to complete
            # We allow 15 seconds to verify the playback_stopped event
            timeout = 15
            number_of_statuses = 2  # Expect: playing -> stopped
            psv.wait_for_status_changes(number_of_statuses, timeout)
            
            # Verify playback status transitions
            statuses = psv.get_statuses()
            assert len(statuses) == number_of_statuses, \
                f"Expected {number_of_statuses} status changes, got {len(statuses)}"
            assert statuses[0] == rs.playback_status.playing, \
                f"Expected first status to be PLAYING, got {statuses[0]}"
            assert statuses[1] == rs.playback_status.stopped, \
                f"Expected second status to be STOPPED, got {statuses[1]}"
            
            # Stop all sensors
            log.d("Stopping sensors")
            for sensor in sensors:
                sensor.stop()
            
            # Close all sensors
            log.d("Closing sensors")
            for sensor in sensors:
                sensor.close()
            
            # Verify frame count
            assert frames_count == FRAMES_IN_BAG_FILE, \
                f"Expected {FRAMES_IN_BAG_FILE} frames, received {frames_count}"
            
            log.d(f"Iteration #{iteration + 1} completed successfully")
            
        except Exception as e:
            log.e(f"Iteration #{iteration + 1} failed: {e}")
            raise
        
        finally:
            # Ensure cleanup happens even if test fails
            dev = None
            sensors = []
    
    log.i(f"Playback stress test completed: all {NUMBER_OF_ITERATIONS} iterations passed")
