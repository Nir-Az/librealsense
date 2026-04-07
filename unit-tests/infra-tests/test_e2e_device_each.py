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
        rc, out, *_ = run_e2e("pytest-each.py", "-k", "test_d400 and not exclude")
        assert_outcomes(out, passed=3)  # D455, D435, D401

    def test_with_exclude_marker(self):
        rc, out, *_ = run_e2e("pytest-each.py", "-k", "test_d400_exclude")
        assert_outcomes(out, passed=2)  # D455, D435

    def test_no_match_runs_unparametrized(self):
        rc, out, *_ = run_e2e("pytest-each.py", "-k", "test_d999_no_match")
        assert_outcomes(out, passed=1)

    def test_multiple_markers_union(self):
        rc, out, *_ = run_e2e("pytest-each.py", "-k", "test_multi")
        assert_outcomes(out, passed=2)

    def test_ids_contain_device_name(self):
        rc, out, *_ = run_e2e("pytest-each.py", "-k", "test_ids")
        assert "D455-111" in out
