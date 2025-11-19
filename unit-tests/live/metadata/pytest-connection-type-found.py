# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
Connection Type Test

Tests that connection type can be detected and matches expected value:
- D457: GMSL
- D555: DDS
- Others: USB
"""

import pytest
import pyrealsense2 as rs

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.live
]


def test_connection_type_found(test_device):
    """Test that connection type can be detected."""
    dev, ctx = test_device
    
    assert dev.supports(rs.camera_info.connection_type), \
        "Device should support connection type info"
    
    connection_type = dev.get_info(rs.camera_info.connection_type)
    assert connection_type, "Connection type should not be empty"
    
    camera_name = dev.get_info(rs.camera_info.name)
    
    # Verify expected connection type based on device model
    if 'D457' in camera_name:
        assert connection_type == "GMSL", \
            f"D457 should use GMSL, got {connection_type}"
    elif 'D555' in camera_name:
        assert connection_type == "DDS", \
            f"D555 should use DDS, got {connection_type}"
    else:
        assert connection_type == "USB", \
            f"Device should use USB, got {connection_type}"
