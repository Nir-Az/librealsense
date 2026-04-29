# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

# The reset_logger fixture lives in log_helpers.py; importing it here is what
# registers it with pytest for tests in this directory.
from log_helpers import reset_logger  # noqa: F401
