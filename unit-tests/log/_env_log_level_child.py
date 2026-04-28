# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
Child script invoked by pytest-env-log-level-{on,off}.py via subprocess.

The C++ logger reads LRS_LOG_LEVEL only at first import of pyrealsense2 — see
src/log.h try_get_log_severity. To exercise it we must spawn a fresh interpreter
where the env var is set (or unset) before pyrealsense2 is imported.

Usage: python _env_log_level_child.py <expected_count>
Exits 0 if the error-severity callback received exactly <expected_count> messages,
non-zero otherwise.
"""

import os
import sys

# Locate pyrealsense2 the same way unit-tests/conftest.py does — via repo helper
_here = os.path.dirname( os.path.abspath( __file__ ) )
sys.path.insert( 0, os.path.join( _here, '..', 'py' ) )
from rspy import repo
pyrs_dir = repo.find_pyrs_dir()
if pyrs_dir and pyrs_dir not in sys.path:
    sys.path.insert( 0, pyrs_dir )

import pyrealsense2 as rs


expected = int( sys.argv[1] )

n_messages = 0
def _counter( severity, message ):
    global n_messages
    n_messages += 1

rs.log_to_callback( rs.log_severity.error, _counter )

rs.log( rs.log_severity.debug, "debug message" )
rs.log( rs.log_severity.info,  "info message" )
rs.log( rs.log_severity.warn,  "warn message" )
rs.log( rs.log_severity.error, "error message" )
rs.log( rs.log_severity.none,  "no message" )

print( f'LRS_LOG_LEVEL={os.environ.get("LRS_LOG_LEVEL")!r} n_messages={n_messages} expected={expected}' )
sys.exit( 0 if n_messages == expected else 1 )
