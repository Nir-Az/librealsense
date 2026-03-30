# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
E2E: @device_each parametrization — one test instance per matching device.

Verifies that resolve_device_each_serials creates the right parametrized
instances, respects excludes and CLI filters, and generates correct test IDs.
"""

from helpers import run_e2e, assert_outcomes


class TestDeviceEachParametrization:

    def test_creates_per_device_instances(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]
            def test_per_device(_test_device_serial):
                assert _test_device_serial in ('111', '222', '777')
        """)
        assert_outcomes(out, passed=3)  # D455, D435, D401

    def test_with_exclude_marker(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [
                pytest.mark.device_each("D400*"),
                pytest.mark.device_exclude("D401"),
            ]
            def test_per_device(_test_device_serial):
                assert _test_device_serial != '777'
        """)
        assert_outcomes(out, passed=2)  # D455, D435

    def test_cli_device_filter(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]
            def test_per_device(_test_device_serial):
                assert _test_device_serial == '111'
        """, "--device", "D455")
        assert_outcomes(out, passed=1)

    def test_cli_exclude_device(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]
            def test_per_device(_test_device_serial):
                assert _test_device_serial != '111'
        """, "--exclude-device", "D455")
        assert_outcomes(out, passed=2)  # D435, D401

    def test_no_match_runs_unparametrized(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device_each("D999")]
            def test_per_device():
                pass
        """)
        assert_outcomes(out, passed=1)

    def test_multiple_markers_union(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [
                pytest.mark.device_each("D455"),
                pytest.mark.device_each("D515"),
            ]
            def test_per_device(_test_device_serial):
                assert _test_device_serial in ('111', '555')
        """)
        assert_outcomes(out, passed=2)

    def test_ids_contain_device_name(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device_each("D455")]
            def test_check(_test_device_serial):
                pass
        """)
        assert "D455-111" in out
