# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
LRS_LOG_LEVEL is read by the C++ logger only at first import of pyrealsense2
(see src/log.h try_get_log_severity). pyrealsense2 is already imported by the
parent pytest session, so we run the actual check in a fresh interpreter.

Without LRS_LOG_LEVEL the error-severity callback would see 1 message (error
only). With LRS_LOG_LEVEL=WARN the threshold is forced to warning, so it sees 2
(warning + error).
"""

import os
import pathlib
import subprocess
import sys


def test_with_lrs_log_level_warn():
    env = dict( os.environ )
    env['LRS_LOG_LEVEL'] = 'WARN'

    child = pathlib.Path( __file__ ).parent / '_env_log_level_child.py'
    expected = '2'  # warning + error

    result = subprocess.run( [sys.executable, str(child), expected],
                             env=env, capture_output=True, text=True )
    assert result.returncode == 0, f'child failed:\nstdout: {result.stdout}\nstderr: {result.stderr}'
