# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2024 RealSense, Inc. All Rights Reserved.

"""
Options Watcher Test

Tests the options watcher callback mechanism that monitors option changes.
Verifies that callbacks are triggered when options change and that multiple
options can be tracked simultaneously.
"""

import pytest
import pyrealsense2 as rs
import time

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D555"),
    pytest.mark.nightly,
    pytest.mark.live
]


@pytest.fixture
def depth_sensor_with_watcher(test_device):
    """Setup depth sensor with options watcher."""
    dev, ctx = test_device
    depth_sensor = dev.first_depth_sensor()
    
    changed_options = []
    
    def notification_callback(opt_list):
        """Callback for option changes."""
        for opt in opt_list:
            if not depth_sensor.is_option_read_only(opt.id):  # Ignore accidental temperature changes
                changed_options.append((opt.id, opt.value))
    
    depth_sensor.on_options_changed(notification_callback)
    
    yield depth_sensor, changed_options
    
    # Cleanup
    pass


def test_disable_auto_exposure(depth_sensor_with_watcher):
    """Test disabling auto exposure before manual option changes."""
    depth_sensor, changed_options = depth_sensor_with_watcher
    
    # Need to disable or changing gain/exposure might automatically disable it
    depth_sensor.set_option(rs.option.enable_auto_exposure, 0)
    assert depth_sensor.get_option(rs.option.enable_auto_exposure) == 0.0
    
    time.sleep(1.5)  # default options-watcher update interval is 1 second


def test_set_single_option(depth_sensor_with_watcher):
    """Test that setting a single option triggers callback once."""
    depth_sensor, changed_options = depth_sensor_with_watcher
    
    # Disable auto exposure first
    depth_sensor.set_option(rs.option.enable_auto_exposure, 0)
    time.sleep(1.5)
    
    changed_options.clear()
    
    current_gain = depth_sensor.get_option(rs.option.gain)
    depth_sensor.set_option(rs.option.gain, current_gain + 1)
    assert depth_sensor.get_option(rs.option.gain) == current_gain + 1
    
    time.sleep(1.5)  # default options-watcher update interval is 1 second
    assert len(changed_options) == 1, f"Expected 1 option change, got {len(changed_options)}"


def test_set_multiple_options(depth_sensor_with_watcher):
    """Test that setting multiple options triggers callbacks for each."""
    depth_sensor, changed_options = depth_sensor_with_watcher
    
    # Disable auto exposure first
    depth_sensor.set_option(rs.option.enable_auto_exposure, 0)
    time.sleep(1.5)
    
    changed_options.clear()
    
    current_gain = depth_sensor.get_option(rs.option.gain)
    depth_sensor.set_option(rs.option.gain, current_gain + 1)
    assert depth_sensor.get_option(rs.option.gain) == current_gain + 1
    
    current_exposure = depth_sensor.get_option(rs.option.exposure)
    depth_sensor.set_option(rs.option.exposure, current_exposure + 1)
    assert depth_sensor.get_option(rs.option.exposure) == current_exposure + 1
    
    time.sleep(2.5)  # default options-watcher update interval is 1 second, multiple options might be updated on different intervals
    assert len(changed_options) == 2, f"Expected 2 option changes, got {len(changed_options)}"


def test_no_sporadic_changes(depth_sensor_with_watcher):
    """Test that no callbacks occur when no options are changed."""
    depth_sensor, changed_options = depth_sensor_with_watcher
    
    # Disable auto exposure first
    depth_sensor.set_option(rs.option.enable_auto_exposure, 0)
    time.sleep(1.5)
    
    changed_options.clear()
    
    time.sleep(3)
    assert len(changed_options) == 0, f"Expected 0 option changes, got {len(changed_options)}"


def test_cancel_subscription(test_device):
    """Test that getting a new sensor instance cancels previous subscription."""
    dev, ctx = test_device
    depth_sensor = dev.first_depth_sensor()
    
    changed_options = []
    
    def notification_callback(opt_list):
        """Callback for option changes."""
        for opt in opt_list:
            if not depth_sensor.is_option_read_only(opt.id):
                changed_options.append((opt.id, opt.value))
    
    depth_sensor.on_options_changed(notification_callback)
    
    # Disable auto exposure
    depth_sensor.set_option(rs.option.enable_auto_exposure, 0)
    time.sleep(1.5)
    
    # Get new sensor, old sensor subscription is canceled
    depth_sensor = dev.first_depth_sensor()
    changed_options.clear()
    
    current_gain = depth_sensor.get_option(rs.option.gain)
    depth_sensor.set_option(rs.option.gain, current_gain + 1)
    assert depth_sensor.get_option(rs.option.gain) == current_gain + 1
    
    time.sleep(1.5)  # default options-watcher update interval is 1 second
    assert len(changed_options) == 0, f"Expected 0 option changes after cancellation, got {len(changed_options)}"
