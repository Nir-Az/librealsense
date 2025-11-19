# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2020 RealSense, Inc. All Rights Reserved.

"""
Out of Range Throw Test

Tests that setting option values outside their valid range throws RuntimeError.
Verifies both below-minimum and above-maximum values are properly rejected.
"""

import pytest
import pyrealsense2 as rs
from rspy import tests_wrapper as tw

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D555"),
    pytest.mark.live
]


def check_min_max_throw(sensor):
    """Check that setting options outside their range throws exceptions.
    
    Args:
        sensor: The sensor to test options on
    """
    options_to_check = [rs.option.exposure, rs.option.enable_auto_exposure]
    
    for option in options_to_check:
        if not sensor.supports(option):
            continue
        
        option_range = sensor.get_option_range(option)
        
        # Test below min
        with pytest.raises(RuntimeError, match="out of range value for argument \"value\""):
            sensor.set_option(option, option_range.min - 1)
        
        # Test above max
        with pytest.raises(RuntimeError, match="out of range value for argument \"value\""):
            sensor.set_option(option, option_range.max + 1)


def test_options_out_of_range_throw(test_device):
    """Test that all sensors throw exceptions for out-of-range option values."""
    dev, ctx = test_device
    
    tw.start_wrapper(dev)
    
    try:
        sensors = dev.query_sensors()
        
        for sensor in sensors:
            check_min_max_throw(sensor)
    finally:
        tw.stop_wrapper(dev)
