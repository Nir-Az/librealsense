# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
E2E: Context gating, --live filtering, and priority ordering in a real subprocess.

Tests the full collection pipeline (conftest hooks → filter_and_sort_items)
by running pytest in a subprocess with mocked hardware.
"""

from helpers import run_e2e, assert_outcomes


class TestContextGatingE2E:
    """@context('nightly') tests should skip/run based on --context."""

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
    """--live should skip non-device tests."""

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


class TestPriorityOrderingE2E:
    """Tests should execute in priority order (lower first)."""

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
