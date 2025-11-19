# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2021 RealSense, Inc. All Rights Reserved.

"""
Set Gain Stress Test

Tests multiple set_pu commands checking that the set control event polling works as expected.
Rapidly sets gain option through various values to stress test the control mechanism.
No exceptions should be thrown - See DSO-17185.
"""

import pytest
import pyrealsense2 as rs
import time
from rspy import tests_wrapper as tw

# Module-level markers
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.nightly,
    pytest.mark.live,
    pytest.mark.timeout(600)
]

# Test parameters
TEST_ITERATIONS = 200
GAIN_VALUES = [16, 74, 132, 190, 248]


@pytest.fixture
def depth_sensor_idle(test_device):
    """Setup depth sensor with device in idle state."""
    dev, ctx = test_device
    
    # The device starts at D0 (Operational) state, allow time for it to get into idle state
    time.sleep(3)
    
    tw.start_wrapper(dev)
    
    depth_ir_sensor = dev.first_depth_sensor()
    
    # Test only devices that support set gain option
    if not depth_ir_sensor.supports(rs.option.gain):
        pytest.skip("Gain option not supported")
    
    yield depth_ir_sensor
    
    tw.stop_wrapper(dev)


def test_set_gain_stress(depth_sensor_idle):
    """Stress test for setting PU (gain) option repeatedly.
    
    Sets gain to various values repeatedly, verifying each set operation succeeds
    without throwing exceptions. This tests the robustness of the control event
    polling mechanism.
    """
    depth_ir_sensor = depth_sensor_idle
    
    for i in range(TEST_ITERATIONS):
        # Reset control values
        if depth_ir_sensor.supports(rs.option.enable_auto_exposure):
            depth_ir_sensor.set_option(rs.option.enable_auto_exposure, 0)
        
        if depth_ir_sensor.supports(rs.option.exposure):
            depth_ir_sensor.set_option(rs.option.exposure, 1)
        
        depth_ir_sensor.set_option(rs.option.gain, 248)
        
        time.sleep(0.1)
        
        # Cycle through gain values
        for val in GAIN_VALUES:
            depth_ir_sensor.set_option(rs.option.gain, val)
            get_val = depth_ir_sensor.get_option(rs.option.gain)
            
            assert val == get_val, \
                f"Iteration {i}: Expected gain {val}, got {get_val}"
