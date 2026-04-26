# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

import os
import subprocess
import sys
import logging
import pytest
from rspy import repo

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.device("D455"),
    pytest.mark.context("linux"),
]


def test_rest_api_wrapper(module_device_setup):
    rest_api_test = os.path.join(repo.root, "wrappers", "rest-api", "tests", "test_api_service.py")
    p = subprocess.run(
        [sys.executable, "-m", "pytest", rest_api_test],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        timeout=10,
        check=False,
    )
    if p.returncode != 0:
        log.error("Subprocess failed (rc=%s):\n%s", p.returncode, p.stdout)
    else:
        log.debug(p.stdout)
    assert p.returncode == 0
