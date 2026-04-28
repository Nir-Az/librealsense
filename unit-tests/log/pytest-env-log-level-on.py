# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

import log_helpers as common


def test_with_lrs_log_level_warn():
    # With LRS_LOG_LEVEL=WARN the C++ logger forces minimum severity to warn,
    # so an error-severity callback sees 2 messages (warning + error). Without
    # LRS_LOG_LEVEL it would see only 1 (error). Runs in a fresh interpreter
    # because LRS_LOG_LEVEL is read once at first pyrealsense2 import.
    common.run_env_log_level_child( {'LRS_LOG_LEVEL': 'WARN'}, expected=2 )
