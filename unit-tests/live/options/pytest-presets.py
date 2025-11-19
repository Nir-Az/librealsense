# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2023 RealSense, Inc. All Rights Reserved.

"""
Visual Presets Test

Tests visual preset functionality including:
- Setting and verifying presets
- Saving and loading preset configurations
- Color sensor options behavior with presets (D400 vs D500)

Note: See FW stability issue RSDSO-18908 for retry requirement.
"""

import pytest
import pyrealsense2 as rs
from rspy import tests_wrapper as tw

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*", exclude="D555"),
    pytest.mark.nightly,
    pytest.mark.live,
    pytest.mark.flaky(reruns=2)
]


@pytest.fixture
def device_with_sensors(test_device):
    """Setup device with depth and color sensors."""
    dev, ctx = test_device
    product_line = dev.get_info(rs.camera_info.product_line)
    product_name = dev.get_info(rs.camera_info.name)
    
    tw.start_wrapper(dev)
    
    depth_sensor = dev.first_depth_sensor()
    color_sensor = None
    
    try:
        color_sensor = dev.first_color_sensor()
    except RuntimeError:
        # Cameras with no color sensor (D421, D405) may fail
        if 'D421' not in product_name and 'D405' not in product_name:
            raise
    
    yield dev, depth_sensor, color_sensor, product_line, product_name
    
    tw.stop_wrapper(dev)


def test_visual_preset_support(device_with_sensors):
    """Test that visual preset option is supported."""
    dev, depth_sensor, color_sensor, product_line, product_name = device_with_sensors
    
    # No use continuing the test if there is no preset support
    assert depth_sensor.supports(rs.option.visual_preset), \
        "Depth sensor should support visual preset option"


def test_set_presets(device_with_sensors):
    """Test setting different visual presets."""
    dev, depth_sensor, color_sensor, product_line, product_name = device_with_sensors
    
    # Skip if no preset support
    if not depth_sensor.supports(rs.option.visual_preset):
        pytest.skip("Visual preset not supported")
    
    # Set high accuracy preset
    depth_sensor.set_option(rs.option.visual_preset, int(rs.rs400_visual_preset.high_accuracy))
    assert depth_sensor.get_option(rs.option.visual_preset) == rs.rs400_visual_preset.high_accuracy
    
    # Set default preset
    depth_sensor.set_option(rs.option.visual_preset, int(rs.rs400_visual_preset.default))
    assert depth_sensor.get_option(rs.option.visual_preset) == rs.rs400_visual_preset.default


def test_save_load_preset(device_with_sensors):
    """Test saving and loading custom preset configurations."""
    dev, depth_sensor, color_sensor, product_line, product_name = device_with_sensors
    
    # Skip if no preset support
    if not depth_sensor.supports(rs.option.visual_preset):
        pytest.skip("Visual preset not supported")
    
    am_dev = rs.rs400_advanced_mode(dev)
    saved_values = am_dev.serialize_json()
    
    # Modify depth control settings
    depth_control_group = am_dev.get_depth_control()
    depth_control_group.textureCountThreshold = 250
    am_dev.set_depth_control(depth_control_group)
    
    # Verify preset changed to custom
    assert depth_sensor.get_option(rs.option.visual_preset) == rs.rs400_visual_preset.custom
    
    # Load saved values
    am_dev.load_json(saved_values)
    assert am_dev.get_depth_control().textureCountThreshold != 250, \
        "Texture count threshold should be restored to original value"


def test_color_options_preset_behavior(device_with_sensors):
    """Test that D400 and D500 devices handle color options differently with presets."""
    dev, depth_sensor, color_sensor, product_line, product_name = device_with_sensors
    
    # Skip if no preset support
    if not depth_sensor.supports(rs.option.visual_preset):
        pytest.skip("Visual preset not supported")
    
    # Skip if no color sensor or Hue not supported
    if not color_sensor or not color_sensor.supports(rs.option.hue):
        pytest.skip("Color sensor with Hue option not available")
    
    # Using Hue to test if setting visual preset changes color sensor settings.
    # Not all cameras support Hue (e.g. D457) but using common setting like Gain or Exposure is dependant on auto-exposure logic
    # This test is intended to check new D500 modules logic of not updating color sensor setting, while keeping legacy
    # D400 devices behavior of updating it.
    
    color_sensor.set_option(rs.option.hue, 123)
    assert color_sensor.get_option(rs.option.hue) == 123
    
    depth_sensor.set_option(rs.option.visual_preset, int(rs.rs400_visual_preset.default))
    
    if product_line == "D400":
        # D400 devices set color options as part of preset setting
        assert color_sensor.get_option(rs.option.hue) != 123, \
            "D400 should change color option when setting preset"
    elif product_line == "D500":
        # D500 devices do not set color options as part of preset setting
        assert color_sensor.get_option(rs.option.hue) == 123, \
            "D500 should not change color option when setting preset"
    else:
        pytest.fail(f"Unsupported product line: {product_line}")
