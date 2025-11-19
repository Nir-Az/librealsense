# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2021 RealSense, Inc. All Rights Reserved.

"""
Metadata Enabled Test

Checks that metadata is enabled for the device.
Priority 1 - runs first in test suite.
"""

import pytest
import pyrealsense2 as rs

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.priority(1),  # Run this test first
    pytest.mark.windows,
    pytest.mark.live
]


def test_metadata_enabled(test_device):
    """Verify metadata is enabled on device."""
    dev, ctx = test_device
    assert dev.is_metadata_enabled(), "Metadata should be enabled"
