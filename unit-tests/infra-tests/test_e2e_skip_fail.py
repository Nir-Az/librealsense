# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
E2E: Skip vs fail behavior in module_device_setup.

- @device with no matching device -> FAIL (error in setup)
- @device_each with no matching device -> SKIP (graceful, e.g. D585S on Jetson with no D585S)
- When candidates exist but are all excluded -> SKIP for both
- No device markers at all -> module_device_setup yields None (no skip, no fail)
"""

from helpers import run_e2e, assert_outcomes


class TestDeviceSkipFailBehavior:

    def test_device_fails_when_no_match(self):
        rc, out, *_ = run_e2e("pytest-device-setup.py", "-k", "test_d999_no_match")
        assert_outcomes(out, error=1)
        assert "No devices" in out

    def test_device_each_skips_when_no_match(self):
        rc, out, *_ = run_e2e("pytest-each-setup.py", "-k", "test_d999_no_match")
        assert_outcomes(out, skipped=1)

    def test_device_skips_when_all_excluded(self):
        rc, out, *_ = run_e2e("pytest-device-setup.py", "-k", "test_d455_excluded")
        assert_outcomes(out, skipped=1)

    def test_device_each_skips_when_all_excluded(self):
        rc, out, *_ = run_e2e("pytest-each-setup.py", "-k", "test_d455_excluded", "--exclude-device", "D455")
        assert_outcomes(out, skipped=1)

    def test_device_passes_when_match_exists(self):
        rc, out, *_ = run_e2e("pytest-device-setup.py", "-k", "test_d455 and not excluded")
        assert_outcomes(out, passed=1)

    def test_no_markers_yields_none(self):
        rc, out, *_ = run_e2e("pytest-device-setup.py", "-k", "test_no_markers")
        assert_outcomes(out, passed=1)
