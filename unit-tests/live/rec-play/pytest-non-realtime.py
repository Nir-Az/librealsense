# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2021 RealSense, Inc. All Rights Reserved.

"""
Non-Realtime Playback Test

Tests that stop of pipeline with playback file and non-realtime mode is not
stuck due to deadlock between pipeline stop thread and syncer blocking enqueue
thread (DSO-15157).
"""

import pytest
import pyrealsense2 as rs
import os
from rspy import log, repo

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.nightly,
    pytest.mark.timeout(20),
    pytest.mark.live
]


@pytest.fixture
def deadlock_bag_file():
    """Locate the test bag file for deadlock testing."""
    filename = os.path.join(repo.build, 'unit-tests', 'recordings', 'recording_deadlock.bag')
    
    if not os.path.exists(filename):
        pytest.skip(f"Required bag file not found: {filename}")
    
    log.d('Deadlock file:', filename)
    return filename


def test_non_realtime_playback_stop(deadlock_bag_file):
    """Test that non-realtime playback can stop without deadlock."""
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_all_streams()
    config.enable_device_from_file(deadlock_bag_file, repeat_playback=False)
    
    profile = pipeline.start(config)
    device = profile.get_device().as_playback().set_real_time(False)
    
    # Process all frames
    success = True
    while success:
        success, _ = pipeline.try_wait_for_frames(1000)
    
    # This should not deadlock
    log.d("Stopping pipeline...")
    pipeline.stop()
    log.d("Pipeline stopped successfully")
