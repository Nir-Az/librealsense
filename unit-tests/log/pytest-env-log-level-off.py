# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

import log_helpers as common


def test_without_lrs_log_level():
    # When LRS_LOG_LEVEL is unset the default minimum severity (error) applies,
    # so an error-severity callback sees 1 message. Runs in a fresh interpreter
    # with LRS_LOG_LEVEL explicitly removed so the result is independent of how
    # the parent pytest was invoked.
    common.run_env_log_level_child( {'LRS_LOG_LEVEL': None}, expected=1 )
