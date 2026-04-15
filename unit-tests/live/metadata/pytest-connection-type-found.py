# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

import pytest
import pyrealsense2 as rs
import logging
log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.device_exclude("D401"),
]


def test_connection_type_detected(test_device):
    """Test that connection type can be detected and matches expected type per device"""
    dev, ctx = test_device

    assert dev.supports(rs.camera_info.connection_type), "Device should support connection_type info"
    connection_type = dev.get_info(rs.camera_info.connection_type)
    camera_name = dev.get_info(rs.camera_info.name)
    assert connection_type, f"Connection type should not be empty for {camera_name}"

    if 'D457' in camera_name:
        assert connection_type == "GMSL", f"D457 should have GMSL connection, got: {connection_type}"
    elif 'D555' in camera_name:
        assert connection_type == "DDS", f"D555 should have DDS connection, got: {connection_type}"
    else:
        assert connection_type == "USB", f"{camera_name} should have USB connection, got: {connection_type}"
