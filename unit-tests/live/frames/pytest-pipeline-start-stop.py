# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2023-2024 RealSense, Inc. All Rights Reserved.

"""
Test pipeline start/stop reliability.

This test verifies that the pipeline can be started and stopped multiple times
in succession, and that frames are received after each start. This tests the
stability of the streaming infrastructure under repeated start/stop cycles.

Note: On D455 and other units with IMU, it takes ~4 seconds per iteration.
"""

import pytest
import pyrealsense2 as rs
from rspy.stopwatch import Stopwatch
from rspy import log
import time

# Module-level markers
# Currently excluding D457 as it's failing
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.device_exclude("D457"),
    pytest.mark.nightly,
    pytest.mark.timeout(220)
]

# Run multiple start/stop of all streams and verify we get a frame for each once
# Relaxed to 3 as 50 was failing often, See [LRS-1213]
ITERATIONS_COUNT = 3


@pytest.fixture(scope="module")
def pipeline_config(module_test_device):
    """
    Module-scoped fixture that provides pipeline configured with test device.
    """
    dev, ctx = module_test_device
    pipe = rs.pipeline(ctx)
    pipe.set_device(dev)
    return {'pipe': pipe, 'dev': dev, 'ctx': ctx}


def test_pipeline_start_stop_iterations(pipeline_config):
    """
    Test pipeline start/stop reliability over multiple iterations.
    
    This test:
    1. Runs ITERATIONS_COUNT (3) start/stop cycles
    2. After each start, waits for frames to verify streaming works
    3. Logs timing for each iteration
    4. Verifies no failures occur during any iteration
    
    Note: When enable_all_streams() was used, the pipeline failed on second
    iteration on D455 (IR frames did not arrive). This is investigated in LRS-972.
    """
    pipe = pipeline_config['pipe']
    dev = pipeline_config['dev']
    
    log.out(f"Testing pipeline start/stop with {ITERATIONS_COUNT} iterations on device: {dev}")
    
    iteration_stopwatch = Stopwatch()
    
    for i in range(ITERATIONS_COUNT):
        iteration_stopwatch.reset()
        log.out(f"Starting iteration #{i + 1}/{ITERATIONS_COUNT}")
        
        # Start pipeline and wait for frames
        start_call_stopwatch = Stopwatch()
        pipe.start()
        
        try:
            # wait_for_frames will throw if no frames received
            f = pipe.wait_for_frames()
            delay = start_call_stopwatch.get_elapsed()
            log.out(f"After {delay} [sec] got first frame of {f}")
            
            assert f is not None, f"No frames received in iteration {i + 1}"
            
        finally:
            pipe.stop()
        
        iteration_time = iteration_stopwatch.get_elapsed()
        log.out(f"Iteration {i + 1} took {iteration_time} [sec]")
        
        # Verify iteration completed in reasonable time (should be < 10s normally, but allow 30s buffer)
        assert iteration_time < 30.0, \
            f"Iteration {i + 1} took too long: {iteration_time}s (expected < 30s)"
    
    log.out(f"All {ITERATIONS_COUNT} iterations completed successfully")
