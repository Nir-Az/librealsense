# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

# The autouse fixture and all helpers live in log_helpers.py; importing the
# fixture here is what registers it with pytest for tests in this directory.
from log_helpers import _reset_logger_state  # noqa: F401
