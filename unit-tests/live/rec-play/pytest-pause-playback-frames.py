# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2021 RealSense, Inc. All Rights Reserved.

"""
Pause Playback Frames Test

Verifies that pause & resume did not mess up the recorded timestamps and the sleep time
between frames is reasonable. Tests multiple pause/resume scenarios to ensure recorded
bag file "capture time" doesn't cause huge sleep times. See [RSDSO-14342].
"""

import pytest
import pyrealsense2 as rs
import os
import time
import tempfile
from rspy import log
from playback_helper import PlaybackStatusVerifier

# Module-level markers
pytestmark = [
    pytest.mark.device("D400*", exclude="D457"),
    pytest.mark.device("D585S"),
    pytest.mark.nightly,
    pytest.mark.live
]

# Test configuration
STREAMING_DURATION = 3
TIMEOUT_BUFFER = 3  # Extra time for runtime hiccups


def calc_playback_timeout(iterations, pause_delay):
    """
    Calculate expected playback timeout.
    Note: resume_delay is not reflected in playback (stream is paused).
    """
    return iterations * (pause_delay + STREAMING_DURATION) + TIMEOUT_BUFFER


def record_with_pause(file_name, iterations, pause_delay=0, resume_delay=0):
    """Record with pause/resume cycles."""
    pipeline = rs.pipeline()
    cfg = rs.config()
    cfg.enable_record_to_file(file_name)
    pipeline_record_profile = pipeline.start(cfg)
    device = pipeline_record_profile.get_device()
    device_recorder = device.as_recorder()
    
    for i in range(iterations):
        if pause_delay > 0:
            log.d(f'Sleeping for {pause_delay} sec before pause')
            time.sleep(pause_delay)
        log.d('Pausing...')
        rs.recorder.pause(device_recorder)
        
        if resume_delay > 0:
            log.d(f'Sleeping for {resume_delay} sec before resume')
            time.sleep(resume_delay)
        log.d('Resumed...')
        rs.recorder.resume(device_recorder)
        time.sleep(STREAMING_DURATION)
    
    pipeline.stop()
    return calc_playback_timeout(iterations, pause_delay)


def playback_file(pipeline, file_name):
    """Play back a recorded file in realtime."""
    cfg = rs.config()
    cfg.enable_device_from_file(file_name, repeat_playback=False)
    log.d('Playing...')
    pipeline_playback_profile = pipeline.start(cfg)
    device = pipeline_playback_profile.get_device()
    playback_dev = device.as_playback()
    # Force realtime=True to ensure sleep between frames
    playback_dev.set_real_time(True)
    pipeline.wait_for_frames()
    assert playback_dev.current_status() == rs.playback_status.playing
    return playback_dev


@pytest.fixture
def temp_recording_file():
    """Create temporary file for recording."""
    temp_dir = tempfile.TemporaryDirectory(prefix='recordings_')
    file_name = os.path.join(temp_dir.name, 'rec.bag')
    yield file_name
    # Cleanup happens automatically with TemporaryDirectory


def test_immediate_pause(temp_recording_file):
    """Test immediate pause & resume (before recording base time is set)."""
    timeout = record_with_pause(temp_recording_file, iterations=1, pause_delay=0, resume_delay=0)
    
    pipeline = rs.pipeline()
    device_playback = playback_file(pipeline, temp_recording_file)
    psv = PlaybackStatusVerifier(device_playback)
    psv.wait_for_status(timeout, rs.playback_status.stopped)


def test_immediate_pause_delayed_resume(temp_recording_file):
    """Test immediate pause with delayed resume (pause before base time, resume after)."""
    timeout = record_with_pause(temp_recording_file, iterations=1, pause_delay=0, resume_delay=5)
    
    pipeline = rs.pipeline()
    device_playback = playback_file(pipeline, temp_recording_file)
    psv = PlaybackStatusVerifier(device_playback)
    psv.wait_for_status(timeout, rs.playback_status.stopped)


def test_delayed_pause_and_resume(temp_recording_file):
    """Test delayed pause & resume (after recording base time is set)."""
    timeout = record_with_pause(temp_recording_file, iterations=1, pause_delay=3, resume_delay=2)
    
    pipeline = rs.pipeline()
    device_playback = playback_file(pipeline, temp_recording_file)
    psv = PlaybackStatusVerifier(device_playback)
    psv.wait_for_status(timeout, rs.playback_status.stopped)


def test_multiple_pause_resume(temp_recording_file):
    """Test multiple pause/resume cycles to verify accumulated capture time."""
    timeout = record_with_pause(temp_recording_file, iterations=2, pause_delay=0, resume_delay=2)
    
    pipeline = rs.pipeline()
    device_playback = playback_file(pipeline, temp_recording_file)
    psv = PlaybackStatusVerifier(device_playback)
    psv.wait_for_status(timeout, rs.playback_status.stopped)
