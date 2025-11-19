# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2023 RealSense, Inc. All Rights Reserved.

"""
Hardware Reset to Enumeration Time Test

Verifies that device enumeration after HW reset completes within expected time limits.
Tests device-specific enumeration time requirements for D400/D500 families.
"""

import pytest
import pyrealsense2 as rs
import time

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_exclude("D457"),  # D457 has known HW reset issues
    pytest.mark.device_each("D500*"),
    pytest.mark.nightly,
    pytest.mark.live
]

# Maximum enumeration time by device family
MAX_ENUM_TIME_D400 = 5  # seconds
MAX_ENUM_TIME_D500 = 15  # seconds
MAX_REMOVAL_WAIT_TIME = 10  # seconds


class DeviceMonitor:
    """Monitor device addition/removal events and timing."""
    def __init__(self, device, device_sn):
        self.device = device
        self.device_sn = device_sn
        self.device_removed = False
        self.device_added = False
        self.removal_time = None
        self.addition_time = None
        self.reset_time = None
    
    def callback(self, info):
        """Device change callback."""
        # Check for removal using was_removed method
        if info.was_removed(self.device):
            self.removal_time = time.perf_counter()
            self.device_removed = True
        
        # Check for addition
        for added_dev in info.get_new_devices():
            if added_dev.get_info(rs.camera_info.serial_number) == self.device_sn:
                self.addition_time = time.perf_counter()
                self.device_added = True
    
    def get_enumeration_time(self):
        """Get time from reset to device enumeration."""
        if self.reset_time and self.addition_time:
            return self.addition_time - self.reset_time
        return None


def get_max_enum_time(dev):
    """Get maximum expected enumeration time for device."""
    product_line = dev.get_info(rs.camera_info.product_line)
    
    if product_line == "D400":
        return MAX_ENUM_TIME_D400
    elif product_line == "D500":
        # DDS devices need extra time for discovery and initialization
        if dev.get_info(rs.camera_info.connection_type) == "DDS":
            return MAX_ENUM_TIME_D500 + 3
        return MAX_ENUM_TIME_D500
    
    return MAX_ENUM_TIME_D500  # Default fallback


def test_hw_reset_enumeration_time(test_device):
    """Test that device enumeration after HW reset meets time requirements."""
    dev, ctx = test_device
    device_sn = dev.get_info(rs.camera_info.serial_number)
    product_line = dev.get_info(rs.camera_info.product_line)
    
    # Get device-specific enumeration time limit
    max_enum_time = get_max_enum_time(dev)
    
    # Setup device monitoring
    monitor = DeviceMonitor(dev, device_sn)
    ctx.set_devices_changed_callback(monitor.callback)
    
    # Allow callback to be registered
    time.sleep(1)
    
    # Send hardware reset command
    monitor.reset_time = time.perf_counter()
    dev.hardware_reset()
    
    # Wait for device removal
    start_time = time.perf_counter()
    while (time.perf_counter() - start_time) < MAX_REMOVAL_WAIT_TIME:
        if monitor.device_removed:
            break
        time.sleep(0.1)
    
    assert monitor.device_removed, \
        f"Device removal not detected within {MAX_REMOVAL_WAIT_TIME} seconds"
    
    removal_time = time.perf_counter() - start_time
    assert removal_time < MAX_REMOVAL_WAIT_TIME, \
        f"Device removal took too long: {removal_time:.2f}s"
    
    # Wait for device addition with buffer
    buffer = 5  # Extra time to capture near-limit cases
    timeout = max_enum_time + buffer
    start_time = time.perf_counter()
    
    while (time.perf_counter() - start_time) < timeout:
        if monitor.device_added:
            break
        time.sleep(0.1)
    
    assert monitor.device_added, \
        f"Device addition not detected within {timeout} seconds"
    
    # Verify enumeration time
    enum_time = monitor.get_enumeration_time()
    assert enum_time is not None, "Failed to calculate enumeration time"
    
    assert enum_time < max_enum_time, \
        f"Enumeration time {enum_time:.2f}s exceeds max {max_enum_time}s for {product_line}"
