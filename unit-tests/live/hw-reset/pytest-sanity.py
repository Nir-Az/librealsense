# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2023 RealSense, Inc. All Rights Reserved.

"""
Hardware Reset Sanity Test

Verifies that hardware reset properly disconnects and reconnects the device.
Tests device removal and addition detection after HW reset command.
"""

import pytest
import pyrealsense2 as rs
from rspy import devices
import time

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_exclude("D457"),  # D457 has known HW reset issues
    pytest.mark.device_each("D500*"),
    pytest.mark.live
]

MAX_WAIT_TIME = 10  # seconds to wait for device removal
MAX_ENUMERATION_TIME = devices.MAX_ENUMERATION_TIME  # seconds to wait for device addition


class DeviceMonitor:
    """Monitor device addition/removal events."""
    def __init__(self, device, device_sn):
        self.device = device
        self.device_sn = device_sn
        self.device_removed = False
        self.device_added = False
        self.removal_time = None
        self.addition_time = None
    
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


def test_hw_reset_disconnect_reconnect(test_device):
    """Test that hardware reset causes device to disconnect and reconnect."""
    dev, ctx = test_device
    device_sn = dev.get_info(rs.camera_info.serial_number)
    
    # Setup device monitoring
    monitor = DeviceMonitor(dev, device_sn)
    ctx.set_devices_changed_callback(monitor.callback)
    
    # Allow callback to be registered
    time.sleep(1)
    
    # Send hardware reset command
    dev.hardware_reset()
    
    # Wait for device removal
    start_time = time.perf_counter()
    while (time.perf_counter() - start_time) < MAX_WAIT_TIME:
        if monitor.device_removed:
            break
        time.sleep(0.1)
    
    assert monitor.device_removed, \
        f"Device removal not detected within {MAX_WAIT_TIME} seconds after HW reset"
    
    # Wait for device addition
    start_time = time.perf_counter()
    while (time.perf_counter() - start_time) < MAX_ENUMERATION_TIME:
        if monitor.device_added:
            break
        time.sleep(0.1)
    
    assert monitor.device_added, \
        f"Device addition not detected within {MAX_ENUMERATION_TIME} seconds after removal"
