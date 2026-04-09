# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

import time
import pytest
import pyrealsense2 as rs
import logging
log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.device_exclude("D401"),
    pytest.mark.context("nightly"),
]


def close_resources(sensor):
    """Stop and close a sensor if it has active streams"""
    if len(sensor.get_active_streams()) > 0:
        sensor.stop()
        sensor.close()


def get_testing_profiles(dev):
    """
    Build a dictionary of one default profile per stream type, mapped to its sensor.
    We only pick default profiles to avoid starting unsupported profiles.
    """
    testing_profiles = {}
    for s in dev.sensors:
        for p in s.profiles:
            if p.is_default():
                # Only add if this stream type isn't already represented
                already_has_type = any(pr.stream_type() == p.stream_type() for pr in testing_profiles)
                if not already_has_type:
                    testing_profiles[p] = s
    return testing_profiles


def check_value_keeps_increasing(frame_queue, metadata_type, number_frames_to_test=50):
    """Check that a given metadata counter increases across frames"""
    prev_value = -1
    for _ in range(number_frames_to_test):
        f = frame_queue.wait_for_frame()
        current_value = f.get_frame_metadata(metadata_type)
        log.debug(f"  {metadata_type}: prev={prev_value}, current={current_value}")
        assert prev_value < current_value, \
            f"Metadata {metadata_type} not increasing: prev={prev_value}, current={current_value}"
        prev_value = current_value


def check_metadata_values_different(frame_queue, metadata_type_1, metadata_type_2, number_frames_to_test=50):
    """Check that two metadata types always have different values"""
    for _ in range(number_frames_to_test):
        f = frame_queue.wait_for_frame()
        value_1 = f.get_frame_metadata(metadata_type_1)
        value_2 = f.get_frame_metadata(metadata_type_2)
        log.debug(f"  {metadata_type_1}={value_1}, {metadata_type_2}={value_2}")
        assert value_1 != value_2, \
            f"Metadata values should differ: {metadata_type_1}={value_1}, {metadata_type_2}={value_2}"


def test_metadata_alive(test_device):
    """Validate metadata counters and timestamps increase correctly across all default profiles"""
    device, ctx = test_device
    camera_name = device.get_info(rs.camera_info.name)
    testing_profiles = get_testing_profiles(device)

    for profile, sensor in testing_profiles.items():
        frame_queue = rs.frame_queue(1)

        try:
            sensor.open(profile)
            sensor.start(frame_queue)
            # Test 1: Increasing frame counter
            if frame_queue.wait_for_frame().supports_frame_metadata(rs.frame_metadata_value.frame_counter):
                log.info(f"Verifying increasing counter for profile {profile}")
                check_value_keeps_increasing(frame_queue, rs.frame_metadata_value.frame_counter)

            # Test 2: Increasing frame timestamp
            if frame_queue.wait_for_frame().supports_frame_metadata(rs.frame_metadata_value.frame_timestamp):
                log.info(f"Verifying increasing time for profile {profile}")
                check_value_keeps_increasing(frame_queue, rs.frame_metadata_value.frame_timestamp)

            # Test 3: Increasing sensor timestamp
            if frame_queue.wait_for_frame().supports_frame_metadata(rs.frame_metadata_value.sensor_timestamp):
                log.info(f"Verifying increasing sensor timestamp for profile {profile}")
                check_value_keeps_increasing(frame_queue, rs.frame_metadata_value.sensor_timestamp)

                # On D457, sensor timestamp == frame timestamp, so we skip this check
                if 'D457' not in camera_name:
                    log.info(f"Verifying sensor timestamp differs from frame timestamp for profile {profile}")
                    check_metadata_values_different(
                        frame_queue,
                        rs.frame_metadata_value.frame_timestamp,
                        rs.frame_metadata_value.sensor_timestamp,
                    )
        finally:
            close_resources(sensor)
            time.sleep(1)  # Let the device recover before next profile
