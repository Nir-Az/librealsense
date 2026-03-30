# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
Tests for rspy/pytest/device_helpers.py (find_matching_devices).

Verifies how device markers resolve to serial numbers:
- Exact name match: device_each("D455") finds serial 111
- Wildcard by product line: device_each("D400*") finds all D400-family devices
- Exclusion: device_exclude("D401") removes a device from results
- CLI filters: --device and --exclude-device narrow results
- Union: multiple device_each markers combine their matches
- Deduplication: overlapping patterns don't produce duplicate serials
"""

import pytest
from rspy.pytest.device_helpers import find_matching_devices
from helpers import fake_by_spec, fake_get, make_device_marker


class TestFindMatchingDevices:
    """Device pattern resolution: wildcards, excludes, CLI filters."""

    @pytest.fixture(autouse=True)
    def _patch_devices(self):
        """Temporarily replace rspy.devices.by_spec/get with our fakes."""
        import rspy.devices as dev
        orig_by_spec, orig_get = dev.by_spec, dev.get
        dev.by_spec, dev.get = fake_by_spec, fake_get
        yield
        dev.by_spec, dev.get = orig_by_spec, orig_get

    def test_exact_name(self):
        sns, had = find_matching_devices([make_device_marker('device_each', 'D455')], each=True)
        assert sns == ['111'] and had is True

    def test_wildcard(self):
        """D400* should match all 6 devices in the D400 product line."""
        sns, had = find_matching_devices([make_device_marker('device_each', 'D400*')], each=True)
        assert len(sns) == 6 and '111' in sns and '222' in sns and had is True

    def test_exclude_marker(self):
        markers = [make_device_marker('device_each', 'D400*'),
                   make_device_marker('device_exclude', 'D401')]
        sns, _ = find_matching_devices(markers, each=True)
        assert '777' not in sns and '111' in sns

    def test_cli_include(self):
        sns, _ = find_matching_devices(
            [make_device_marker('device_each', 'D400*')], each=True, cli_includes=['D455'])
        assert sns == ['111']

    def test_cli_exclude(self):
        sns, _ = find_matching_devices(
            [make_device_marker('device_each', 'D400*')], each=True, cli_excludes=['D455'])
        assert '111' not in sns and '222' in sns

    def test_each_false_returns_first_only(self):
        sns, had = find_matching_devices([make_device_marker('device', 'D400*')], each=False)
        assert len(sns) == 1 and had is True

    def test_no_match(self):
        sns, had = find_matching_devices([make_device_marker('device_each', 'D999')], each=True)
        assert sns == [] and had is False

    def test_multiple_markers_union(self):
        markers = [make_device_marker('device_each', 'D455'),
                   make_device_marker('device_each', 'D515')]
        sns, _ = find_matching_devices(markers, each=True)
        assert set(sns) == {'111', '555'}

    def test_exclude_plus_cli_include(self):
        markers = [make_device_marker('device_each', 'D400*'),
                   make_device_marker('device_exclude', 'D401')]
        sns, _ = find_matching_devices(markers, each=True, cli_includes=['D455', 'D435'])
        assert set(sns) == {'111', '222'}

    def test_no_duplicates(self):
        """D455 + D400* (which includes D455) should not produce duplicate serials."""
        markers = [make_device_marker('device_each', 'D455'),
                   make_device_marker('device_each', 'D400*')]
        sns, _ = find_matching_devices(markers, each=True)
        assert sns.count('111') == 1
