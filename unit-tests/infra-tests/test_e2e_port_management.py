# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
E2E: Device hub port management — verify enable_only calls.

Tests that module_device_setup calls enable_only with the correct serial
numbers and recycle flag, and that it reuses devices across tests in the
same module without re-enabling.
"""

from helpers import run_e2e, assert_outcomes


class TestDevicePortManagement:

    def test_device_marker_enables_correct_port(self):
        """@device('D455') should call enable_only(['111'], recycle=True)."""
        rc, out, calls = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device("D455")]
            def test_check(module_device_setup):
                assert module_device_setup == '111'
        """)
        assert_outcomes(out, passed=1)
        assert len(calls) == 1
        assert calls[0]['serials'] == ['111']
        assert calls[0]['recycle'] is True

    def test_device_each_enables_one_port_per_test(self):
        """@device_each('D400*') should call enable_only once per device, each with recycle=True."""
        rc, out, calls = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]
            def test_check(_test_device_serial, module_device_setup):
                assert module_device_setup == _test_device_serial
        """)
        assert_outcomes(out, passed=3)
        assert len(calls) == 3
        serials_enabled = [c['serials'][0] for c in calls]
        assert set(serials_enabled) == {'111', '222', '777'}
        assert all(c['recycle'] is True for c in calls)
        assert all(len(c['serials']) == 1 for c in calls)

    def test_second_test_same_device_no_recycle(self):
        """Two tests on the same device: first recycles, second reuses (no enable_only call)."""
        rc, out, calls = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device("D455")]
            def test_first(module_device_setup):
                assert module_device_setup == '111'
            def test_second(module_device_setup):
                assert module_device_setup == '111'
        """)
        assert_outcomes(out, passed=2)
        assert len(calls) == 1

    def test_no_device_marker_no_enable(self):
        """Tests without device markers should not call enable_only."""
        rc, out, calls = run_e2e("""
            def test_no_device(module_device_setup):
                assert module_device_setup is None
        """)
        assert_outcomes(out, passed=1)
        assert len(calls) == 0

    def test_device_no_match_fails_without_enabling(self):
        """@device('D999') with no match should fail and never call enable_only."""
        rc, out, calls = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device("D999")]
            def test_needs_device(module_device_setup):
                pass
        """)
        assert_outcomes(out, error=1)
        assert len(calls) == 0

    def test_device_each_no_match_skips_without_enabling(self):
        """@device_each('D999') with no match should skip and never call enable_only."""
        rc, out, calls = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device_each("D999")]
            def test_needs_device(module_device_setup):
                pass
        """)
        assert_outcomes(out, skipped=1)
        assert len(calls) == 0
