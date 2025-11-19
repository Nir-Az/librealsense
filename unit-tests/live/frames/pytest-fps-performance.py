# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
RealSense FPS Performance Test

Comprehensive testing of all supported resolutions and frame rates for Depth, Color, and IR streams.
Includes multi-stream combination testing for Depth + Color combinations.

WARNING: This test is VERY long-running (up to 4 hours).
Only runs when -m weekly is specified.

Note: The full implementation is in migrated-test-fps-performance.py (1947 lines).
This file is a placeholder pending full pytest conversion.
"""

import pytest

# Module-level markers
pytestmark = [
    pytest.mark.device("D400*"),
    pytest.mark.device("D500*"),
    pytest.mark.weekly,
    pytest.mark.timeout(14400),  # 4 hours
    pytest.mark.live
]


def test_fps_performance_comprehensive():
    """
    Comprehensive FPS performance test.
    
    Tests all supported resolutions and frame rates for:
    - Depth streams (all configurations)
    - Color/RGB streams (all configurations)
    - IR streams (all configurations)
    - Multi-stream combinations (Depth + Color)
    - Device creation time
    - First frame delays
    
    Full implementation pending conversion from migrated-test-fps-performance.py.
    """
    pass
