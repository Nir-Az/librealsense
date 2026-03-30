# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
E2E: All custom CLI options should be accepted without error.

Verifies that pytest_addoption in conftest.py correctly registers
--device, --exclude-device, --context, --live, --no-reset, --hub-reset,
--rslog, --rs-help, and --debug.
"""

from helpers import run_e2e, assert_outcomes


class TestCliOptionsRegistered:

    def test_device(self):
        rc, *_ = run_e2e("def test_pass(): pass", "--device", "D455")
        assert rc == 0

    def test_exclude_device(self):
        rc, *_ = run_e2e("def test_pass(): pass", "--exclude-device", "D455")
        assert rc == 0

    def test_context(self):
        rc, *_ = run_e2e("def test_pass(): pass", "--context", "nightly")
        assert rc == 0

    def test_live(self):
        rc, out, *_ = run_e2e("def test_pass(): pass", "--live")
        assert_outcomes(out, skipped=1)

    def test_no_reset(self):
        rc, *_ = run_e2e("def test_pass(): pass", "--no-reset")
        assert rc == 0

    def test_hub_reset(self):
        rc, *_ = run_e2e("def test_pass(): pass", "--hub-reset")
        assert rc == 0

    def test_rslog(self):
        rc, *_ = run_e2e("def test_pass(): pass", "--rslog")
        assert rc == 0

    def test_rs_help(self):
        rc, *_ = run_e2e("def test_pass(): pass", "--rs-help")
        assert rc == 0

    def test_debug(self):
        rc, *_ = run_e2e("def test_pass(): pass", "--debug")
        assert rc == 0

    def test_multiple_device_flags(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]
            def test_multi(_test_device_serial):
                assert _test_device_serial in ('111', '222')
        """, "--device", "D455", "--device", "D435")
        assert_outcomes(out, passed=2)

    def test_multiple_exclude_device_flags(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]
            def test_multi(_test_device_serial):
                assert _test_device_serial == '777'
        """, "--exclude-device", "D455", "--exclude-device", "D435")
        assert_outcomes(out, passed=1)

    def test_device_and_exclude_combined(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]
            def test_filtered(_test_device_serial):
                assert _test_device_serial == '111'
        """, "--device", "D455", "--device", "D435", "--exclude-device", "D435")
        assert_outcomes(out, passed=1)
