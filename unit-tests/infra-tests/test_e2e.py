# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
End-to-end integration tests using subprocess.run.

Each test spawns a real pytest subprocess with mocked hardware and the real
conftest.py (via exec). If someone changes conftest.py or rspy/pytest/*,
these tests break.
"""

from helpers import run_e2e, assert_outcomes


class TestMarkerRegistration:
    """All custom markers should be registered (no PytestUnknownMarkWarning)."""

    def test_all_markers(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [
                pytest.mark.device_each("D455"),
                pytest.mark.device_exclude("D401"),
                pytest.mark.context("nightly"),
                pytest.mark.priority(100),
            ]
            def test_example(_test_device_serial):
                pass
        """, "--context", "nightly", "-W", "error::pytest.PytestUnknownMarkWarning")
        assert_outcomes(out, passed=1)

    def test_device_marker(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device("D455")]
            def test_with_device():
                pass
        """, "-W", "error::pytest.PytestUnknownMarkWarning")
        assert_outcomes(out, passed=1)


class TestContextGatingE2E:
    """End-to-end: @context('nightly') tests should skip/run based on --context."""

    def test_nightly_skipped_by_default(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.context("nightly")]
            def test_nightly_only():
                pass
        """)
        assert_outcomes(out, skipped=1)

    def test_nightly_runs_with_context(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.context("nightly")]
            def test_nightly_only():
                pass
        """, "--context", "nightly")
        assert_outcomes(out, passed=1)

    def test_mixed_context_and_normal(self):
        rc, out, *_ = run_e2e("""
            import pytest
            def test_always():
                pass
            @pytest.mark.context("nightly")
            def test_nightly_only():
                pass
        """)
        assert_outcomes(out, passed=1, skipped=1)


class TestLiveFilteringE2E:
    """End-to-end: --live should skip non-device tests."""

    def test_skips_non_device(self):
        rc, out, *_ = run_e2e("""
            def test_no_device():
                pass
        """, "--live")
        assert_outcomes(out, skipped=1)

    def test_keeps_device_each(self):
        rc, out, *_ = run_e2e("""
            import pytest
            pytestmark = [pytest.mark.device_each("D455")]
            def test_with_device(_test_device_serial):
                pass
        """, "--live")
        assert_outcomes(out, passed=1)

    def test_mixed(self):
        rc, out, *_ = run_e2e("""
            import pytest
            def test_no_device():
                pass
            @pytest.mark.device_each("D455")
            def test_with_device(_test_device_serial):
                pass
        """, "--live")
        assert_outcomes(out, passed=1, skipped=1)


class TestDeviceEachParametrization:
    """End-to-end: @device_each should create one test instance per matching device."""

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


class TestDeviceSkipFailBehavior:
    """@device with no match should FAIL. @device_each with no match should SKIP.
    When candidates exist but are all excluded, both should SKIP."""

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
        """device_each skips gracefully — e.g. D585S test on a machine with no D585S."""
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


class TestPriorityOrderingE2E:
    """End-to-end: tests should execute in priority order."""

    def test_priority_order(self):
        rc, out, *_ = run_e2e("""
            import pytest
            execution_order = []

            @pytest.mark.priority(900)
            def test_last():
                execution_order.append('last')

            @pytest.mark.priority(100)
            def test_first():
                execution_order.append('first')

            @pytest.mark.priority(500)
            def test_middle():
                execution_order.append('middle')

            def test_verify_order():
                assert execution_order == ['first', 'middle']
        """)
        assert_outcomes(out, passed=4)


class TestCliOptionsRegistered:
    """All custom CLI options should be accepted without error."""

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


class TestDevicePortManagement:
    """Verify that module_device_setup calls enable_only with the correct serial and recycle flag."""

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
