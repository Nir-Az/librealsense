# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
E2E: Skip vs fail behavior in module_device_setup.

- @device with no matching device → FAIL (error in setup)
- @device_each with no matching device → SKIP (graceful, e.g. D585S on a machine with no D585S)
- When candidates exist but are all excluded → SKIP for both
"""

from helpers import run_e2e, assert_outcomes


class TestDeviceSkipFailBehavior:

    def test_device_fails_when_no_match(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device("D999")]
            def test_needs_device(module_device_setup):
                pass
        """)
        assert_outcomes(out, error=1)
        assert "No devices found" in out

    def test_device_each_skips_when_no_match(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device_each("D999")]
            def test_needs_device(module_device_setup):
                pass
        """)
        assert_outcomes(out, skipped=1)

    def test_device_skips_when_all_excluded(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [
                pytest.mark.device("D455"),
                pytest.mark.device_exclude("D455"),
            ]
            def test_needs_device(module_device_setup):
                pass
        """)
        assert_outcomes(out, skipped=1)

    def test_device_each_skips_when_all_excluded(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device_each("D455")]
            def test_needs_device(module_device_setup):
                pass
        """, "--exclude-device", "D455")
        assert_outcomes(out, skipped=1)

    def test_device_passes_when_match_exists(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device("D455")]
            def test_needs_device(module_device_setup):
                assert module_device_setup == '111'
        """)
        assert_outcomes(out, passed=1)

    def test_no_markers_yields_none(self):
        rc, out, *_ = run_e2e("""
            def test_no_device(module_device_setup):
                assert module_device_setup is None
        """)
        assert_outcomes(out, passed=1)
