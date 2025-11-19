# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
UVC Power Stress Test

Tests the locking mechanism on UVC devices (MIPI classes extend UVC).
Uses multiple threads to simultaneously change visual presets, which internally
issue many commands (PU, XU, HWM), while also sending GVD commands.
This tests the robustness of device locking under concurrent access.
"""

import pytest
import pyrealsense2 as rs
import threading
import time

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.nightly,
    pytest.mark.live
]


def change_presets(dev, index, delay):
    """Change visual presets repeatedly on a device.
    
    Args:
        dev: The device to operate on
        index: Thread index for logging
        delay: Initial delay before starting
    """
    depth_sensor = dev.first_depth_sensor()
    assert depth_sensor.supports(rs.option.visual_preset), \
        f"Thread {index}: Visual preset not supported"
    
    time.sleep(delay)
    
    for i in range(10):
        # Set high_accuracy preset
        start_time = time.perf_counter()
        depth_sensor.set_option(rs.option.visual_preset, int(rs.rs400_visual_preset.high_accuracy))
        end_time = time.perf_counter()
        
        # Set default preset
        start_time = time.perf_counter()
        depth_sensor.set_option(rs.option.visual_preset, int(rs.rs400_visual_preset.default))
        end_time = time.perf_counter()


@pytest.fixture
def uvc_context():
    """Create context with DDS disabled to test UVC locking."""
    ctx = rs.context({'dds': {'enabled': False}})  # We want to test UVC locking so no DDS
    yield ctx


@pytest.fixture
def devices_for_stress_test(uvc_context):
    """Setup devices for stress testing."""
    ctx = uvc_context
    devices = ctx.query_devices()
    
    assert len(devices) > 0, "No devices found for testing"
    
    yield devices


def test_uvc_power_stress_concurrent_presets(devices_for_stress_test):
    """Test concurrent preset changes across multiple threads and devices.
    
    Opens 2 threads per device, each calling devices[i] to create different device objects
    for the same camera. This tests the UVC locking mechanism under concurrent access.
    """
    devices = devices_for_stress_test
    threads = []
    
    # Create 2 threads per device with slightly offset delays
    for i in range(len(devices)):
        t1 = threading.Thread(target=change_presets, args=(devices[i], i * 2, 0.05))
        threads.append(t1)
        t2 = threading.Thread(target=change_presets, args=(devices[i], i * 2 + 1, 0.1))
        threads.append(t2)
    
    # Start all threads
    for t in threads:
        t.start()
    
    # Issue GVD commands in the middle while threads are running
    raw_command = rs.debug_protocol(devices[0]).build_command(0x10)  # 0x10 is GVD opcode
    
    for i in range(10):
        for j in range(len(devices)):
            start_time = time.perf_counter()
            raw_result = rs.debug_protocol(devices[j]).send_and_receive_raw_data(raw_command)
            end_time = time.perf_counter()
            
            assert raw_result is not None, f"GVD command failed for device {j}"
        
        time.sleep(0.5)
    
    # Wait for threads to finish
    for t in threads:
        t.join()
