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
from rspy.pytest.device_helpers import find_matching_devices, find_matching_devices_multi
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


class TestFindMatchingDevicesMulti:
    """Multi-device marker resolution: device("D400*", "D400*") etc."""

    @pytest.fixture(autouse=True)
    def _patch_devices(self):
        import rspy.devices as dev
        orig_by_spec, orig_get = dev.by_spec, dev.get
        dev.by_spec, dev.get = fake_by_spec, fake_get
        yield
        dev.by_spec, dev.get = orig_by_spec, orig_get

    def test_two_d400_devices(self):
        """device("D400*", "D400*") should return 2 unique D400 serial numbers."""
        markers = [make_device_marker('device', 'D400*', 'D400*')]
        sns, had = find_matching_devices_multi(markers)
        assert len(sns) == 2
        assert sns[0] != sns[1]
        assert had is True

    def test_d400_plus_d500(self):
        """device("D400*", "D500*") should return one D400 and one D500."""
        from helpers import DEVICES
        markers = [make_device_marker('device', 'D400*', 'D500*')]
        sns, had = find_matching_devices_multi(markers)
        assert len(sns) == 2
        d400_sns = {sn for name, (sn, pl) in DEVICES.items() if pl == 'D400'}
        d500_sns = {sn for name, (sn, pl) in DEVICES.items() if pl == 'D500'}
        assert sns[0] in d400_sns
        assert sns[1] in d500_sns

    def test_specific_devices(self):
        """device("D455", "D435") should return exact matches."""
        markers = [make_device_marker('device', 'D455', 'D435')]
        sns, _ = find_matching_devices_multi(markers)
        assert sns == ['111', '222']

    def test_three_devices(self):
        """device("D400*", "D400*", "D400*") should return 3 unique D400 devices."""
        markers = [make_device_marker('device', 'D400*', 'D400*', 'D400*')]
        sns, _ = find_matching_devices_multi(markers)
        assert len(sns) == 3
        assert len(set(sns)) == 3  # all unique

    def test_insufficient_devices(self):
        """device("D500*", "D500*", "D500*") with only 2 D500 devices should return fewer than requested."""
        markers = [make_device_marker('device', 'D500*', 'D500*', 'D500*')]
        sns, had = find_matching_devices_multi(markers)
        assert len(sns) < 3  # only D515 and D555 exist, requested 3
        assert had is True

    def test_with_exclusion(self):
        """device("D400*", "D400*") + device_exclude("D455") should skip D455."""
        markers = [make_device_marker('device', 'D400*', 'D400*'),
                   make_device_marker('device_exclude', 'D455')]
        sns, _ = find_matching_devices_multi(markers)
        assert len(sns) == 2
        assert '111' not in sns  # D455 serial excluded

    def test_no_device_marker(self):
        """No device marker should return empty."""
        markers = [make_device_marker('device_exclude', 'D455')]
        sns, had = find_matching_devices_multi(markers)
        assert sns == [] and had is False
