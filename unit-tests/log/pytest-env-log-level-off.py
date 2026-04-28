# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
Counterpart of pytest-env-log-level-on.py: when LRS_LOG_LEVEL is unset, the
default severity (error) applies, so an error-severity callback sees 1 message.

Runs in a fresh interpreter with LRS_LOG_LEVEL explicitly removed from the
environment so the result is independent of how the parent pytest was invoked.
"""

import os
import pathlib
import subprocess
import sys


def test_without_lrs_log_level():
    env = dict( os.environ )
    env.pop( 'LRS_LOG_LEVEL', None )

    child = pathlib.Path( __file__ ).parent / '_env_log_level_child.py'
    expected = '1'  # error only

    result = subprocess.run( [sys.executable, str(child), expected],
                             env=env, capture_output=True, text=True )
    assert result.returncode == 0, f'child failed:\nstdout: {result.stdout}\nstderr: {result.stderr}'
