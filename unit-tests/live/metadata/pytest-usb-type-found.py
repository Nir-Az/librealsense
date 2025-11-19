# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2023 RealSense, Inc. All Rights Reserved.

"""
USB Type Test

Tests that USB type descriptor can be detected for USB-connected devices.
Excludes D457 (GMSL) and D555 (DDS) which don't use USB.
"""

import pytest
import pyrealsense2 as rs

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*", exclude="D457"),
    pytest.mark.device_each("D500*", exclude="D555"),
    pytest.mark.live
]


def test_usb_type_found(test_device):
    """Test that USB type descriptor can be detected."""
    dev, ctx = test_device
    
    supports = dev.supports(rs.camera_info.usb_type_descriptor)
    assert supports, "Device should support USB type descriptor"
    
    usb_type = dev.get_info(rs.camera_info.usb_type_descriptor)
    assert usb_type and usb_type != "Undefined", \
        f"USB type should be defined, got '{usb_type}'"
