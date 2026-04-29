# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
Shared helpers for the log/ pytest cases.

Each test file does `import log_helpers as common` and gets:
  * the same domain helpers as the legacy `common.py` (`log_all`, `message_counter`,
    `message_counter_2`, `count_lines`, `n_messages`, `n_messages_2`)
  * an autouse fixture (`_reset_logger_state`) re-exported via `conftest.py`, so
    every test starts with a clean global logger and zeroed counters
  * `run_env_log_level_child(env_overrides, expected)` for the two LRS_LOG_LEVEL
    cases that need a fresh interpreter (the C++ logger reads LRS_LOG_LEVEL only
    at first import of pyrealsense2; see src/log.h `try_get_log_severity`)

This file is also the subprocess child: when invoked as `python log_helpers.py
<expected>` the `__main__` block at the bottom imports pyrealsense2, registers an
error-severity callback, calls `log_all()`, and exits 0/non-zero based on the
observed message count.
"""

import os
import sys

# When run as the env-var subprocess child, sys.path needs to know where
# pyrealsense2 lives BEFORE we import it below. The parent pytest's conftest
# already did this for in-process imports.
if __name__ == '__main__':
    _here = os.path.dirname( os.path.abspath( __file__ ) )
    sys.path.insert( 0, os.path.join( _here, '..', 'py' ) )
    from rspy import repo
    _pyrs_dir = repo.find_pyrs_dir()
    if _pyrs_dir and _pyrs_dir not in sys.path:
        sys.path.insert( 0, _pyrs_dir )

import logging
import pathlib
import subprocess
import pytest
import pyrealsense2 as rs

log = logging.getLogger(__name__)


# =============================================================================
# Domain helpers (mirror legacy common.py)
# =============================================================================

def log_all():
    rs.log( rs.log_severity.debug, "debug message" )
    rs.log( rs.log_severity.info, "info message" )
    rs.log( rs.log_severity.warn, "warn message" )
    rs.log( rs.log_severity.error, "error message" )
    # NOTE: fatal messages will exit the process and so cannot be tested
    #rs.log( rs.log_severity.fatal, "fatal message" )
    rs.log( rs.log_severity.none, "no message" )  # ignored; no callback


n_messages = 0
def message_counter( severity, message ):
    global n_messages
    n_messages += 1
    log.debug( message.full() )
    #
    assert str(message) == message.raw()
    assert repr(message) == message.full()


n_messages_2 = 0
def message_counter_2( severity, message ):
    global n_messages_2
    n_messages_2 += 1
    log.debug( message.full() )


def count_lines( filename ):
    # -1 because the text always has an extra \n
    return len( open( filename, 'rt' ).read().split( '\n' )) - 1


# =============================================================================
# Pytest fixture — re-exported via log/conftest.py
# =============================================================================
#
# rs.log_to_callback / log_to_file register handlers on a global C++ singleton
# and the message-counter globals above persist across tests in a single pytest
# session. Tests opt in by naming `reset_logger` in their signature (same shape
# as `test_device` in the parent conftest); the legacy framework got equivalent
# isolation for free by running each test in its own subprocess.

@pytest.fixture
def reset_logger():
    global n_messages, n_messages_2
    rs.reset_logger()
    n_messages = 0
    n_messages_2 = 0
    yield
    rs.reset_logger()


# =============================================================================
# Env-var subprocess helper
# =============================================================================
#
# `LRS_LOG_LEVEL` is read by the C++ logger only at first import of
# pyrealsense2 (src/log.h:165, `try_get_log_severity` called from logger_type
# ctor). By the time pytest runs, pyrealsense2 is already loaded, so flipping
# the env var in-process has no effect — `rs.reset_logger()` only reconfigures
# the existing singleton, it does NOT re-read the env. Solution: spawn a fresh
# interpreter where the env var is set before pyrealsense2 is imported. The
# legacy framework had the same constraint (rspy.test.set_env_vars re-execs
# the script) — this preserves that behavior.

def run_env_log_level_child( env_overrides, expected ):
    """
    Spawn a fresh interpreter with `env_overrides` applied on top of os.environ
    (use value=None to unset a key). The child runs this same module's __main__
    block which exits 0 iff the error-severity callback received exactly
    `expected` messages.
    """
    env = dict( os.environ )
    for k, v in env_overrides.items():
        if v is None:
            env.pop( k, None )
        else:
            env[k] = v

    me = pathlib.Path( __file__ )
    result = subprocess.run( [sys.executable, str(me), str(expected)],
                             env=env, capture_output=True, text=True, timeout=30 )
    assert result.returncode == 0, \
        f'child failed:\nstdout: {result.stdout}\nstderr: {result.stderr}'


# =============================================================================
# Subprocess child entry point
# =============================================================================
# Invoked indirectly via run_env_log_level_child() above. Do NOT run pytest
# against this file as a script — it has no test_* functions.

if __name__ == '__main__':
    expected_arg = int( sys.argv[1] )

    _n = 0
    def _counter( severity, message ):
        global _n
        _n += 1

    rs.log_to_callback( rs.log_severity.error, _counter )
    log_all()

    print( f'LRS_LOG_LEVEL={os.environ.get("LRS_LOG_LEVEL")!r} n_messages={_n} expected={expected_arg}' )
    sys.exit( 0 if _n == expected_arg else 1 )
