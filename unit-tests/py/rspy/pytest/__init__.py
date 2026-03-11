# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
rspy.pytest — Modular pytest infrastructure for RealSense unit tests.

Sub-modules:
- logging_setup: Per-test log files, build dir detection, rspy.log bridging
- cli: Legacy CLI flag translation (e.g. -r/--regex → -k)
- device_helpers: Device resolution from markers and CLI filters
"""

from rspy.pytest.logging_setup import (
    setup_test_logging, bridge_rspy_log, configure_logging,
    start_test_log, stop_test_log, print_terminal_summary,
)
from rspy.pytest.cli import consume_legacy_flags
from rspy.pytest.device_helpers import find_matching_devices, resolve_device_each_serials
from rspy.pytest.collection import filter_and_sort_items
