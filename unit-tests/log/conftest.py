# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

import pytest
import pyrealsense2 as rs

import log_helpers


@pytest.fixture(autouse=True)
def _reset_logger_state():
    # The C++ logger is a global singleton; log_to_callback / log_to_file register
    # globally and persist across tests in a single pytest session. log_helpers
    # also keeps module-level message counters. Reset both around every test.
    rs.reset_logger()
    log_helpers.n_messages = 0
    log_helpers.n_messages_2 = 0
    yield
    rs.reset_logger()
