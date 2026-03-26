# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
Regression tests for the pytest infrastructure in unit-tests/conftest.py and rspy.pytest.*.

These tests validate that markers, CLI flags, collection logic, log naming, and device
helpers work correctly — without requiring cameras or pyrealsense2.

Run with:
    cd unit-tests && python -m pytest infra-tests/ -v
"""

import sys
import os
import types
import re
from unittest.mock import patch, MagicMock
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeDevice:
    """Minimal stand-in for rspy.devices.Device."""
    def __init__(self, sn, name):
        self.sn = sn
        self.name = name


def _fake_by_spec(pattern, ignored):
    """Mock devices.by_spec: expand pattern against a fixed device inventory.

    Mirrors the real by_spec logic: 'D400*' matches by product LINE (D400),
    exact name like 'D455' matches by device name, serial number matches directly.
    """
    # name -> (serial, product_line)
    inventory = {
        'D455':  ('111', 'D400'),
        'D435':  ('222', 'D400'),
        'D435i': ('333', 'D400'),
        'D405':  ('444', 'D400'),
        'D401':  ('777', 'D400'),
        'D457':  ('888', 'D400'),
        'D515':  ('555', 'D500'),
        'D555':  ('666', 'D500'),
    }
    sn_to_name = {info[0]: name for name, info in inventory.items()}

    if pattern.endswith('*'):
        # Wildcard: match by product line prefix (e.g. D400* -> product_line == "D400")
        product_line = pattern[:-1]
        for name, (sn, pl) in inventory.items():
            if pl == product_line:
                yield sn
    elif pattern in inventory:
        # Exact device name match
        yield inventory[pattern][0]
    elif pattern in sn_to_name:
        # Exact serial number match
        yield pattern


def _fake_get(sn):
    """Mock devices.get: return a FakeDevice for known serial numbers."""
    sn_to_name = {
        '111': 'D455', '222': 'D435', '333': 'D435i',
        '444': 'D405', '555': 'D515', '666': 'D555',
        '777': 'D401', '888': 'D457',
    }
    name = sn_to_name.get(sn)
    if name:
        return FakeDevice(sn, name)
    return None


# ---------------------------------------------------------------------------
# 1. collection.py — filter_and_sort_items
# ---------------------------------------------------------------------------

class TestContextGating:
    """Tests for @pytest.mark.context() skipping logic."""

    def _make_item(self, markers=None):
        """Create a mock test item with given markers."""
        item = MagicMock()
        item.name = "test_example"
        item.module = types.ModuleType("fake_module")
        del item.callspec  # ensure hasattr(item, 'callspec') is False
        marks = []
        for m in (markers or []):
            marks.append(m)

        def iter_markers(name=None):
            for m in marks:
                if name is None or m.name == name:
                    yield m

        item.iter_markers = iter_markers
        item.get_closest_marker = lambda name: next(
            (m for m in marks if m.name == name), None
        )
        return item

    def _make_config(self, context="", live=False, markexpr=""):
        config = MagicMock()
        def getoption(key, default=None):
            opts = {
                "--context": context,
                "--live": live,
                "-m": markexpr,
            }
            return opts.get(key, default)
        config.getoption = getoption
        return config

    def test_context_skip_when_not_provided(self):
        """Tests with @context('nightly') should be skipped when --context is empty."""
        from rspy.pytest.collection import filter_and_sort_items

        marker = pytest.mark.context("nightly")
        item = self._make_item([marker])
        config = self._make_config(context="")

        filter_and_sort_items(config, [item])

        item.add_marker.assert_called_once()
        skip_marker = item.add_marker.call_args[0][0]
        assert skip_marker.name == "skip"
        assert "nightly" in skip_marker.kwargs.get("reason", skip_marker.args[0] if skip_marker.args else "")

    def test_context_not_skipped_when_provided(self):
        """Tests with @context('nightly') should NOT be skipped when --context includes 'nightly'."""
        from rspy.pytest.collection import filter_and_sort_items

        marker = pytest.mark.context("nightly")
        item = self._make_item([marker])
        config = self._make_config(context="nightly")

        filter_and_sort_items(config, [item])

        item.add_marker.assert_not_called()

    def test_context_not_skipped_via_m_flag(self):
        """Tests with @context('nightly') should NOT be skipped when -m includes 'nightly'."""
        from rspy.pytest.collection import filter_and_sort_items

        marker = pytest.mark.context("nightly")
        item = self._make_item([marker])
        config = self._make_config(context="", markexpr="nightly")

        filter_and_sort_items(config, [item])

        item.add_marker.assert_not_called()

    def test_context_multiple_values(self):
        """--context 'nightly weekly' should satisfy @context('nightly')."""
        from rspy.pytest.collection import filter_and_sort_items

        marker = pytest.mark.context("nightly")
        item = self._make_item([marker])
        config = self._make_config(context="nightly weekly")

        filter_and_sort_items(config, [item])

        item.add_marker.assert_not_called()

    def test_context_wrong_value_still_skips(self):
        """--context 'weekly' should NOT satisfy @context('nightly')."""
        from rspy.pytest.collection import filter_and_sort_items

        marker = pytest.mark.context("nightly")
        item = self._make_item([marker])
        config = self._make_config(context="weekly")

        filter_and_sort_items(config, [item])

        item.add_marker.assert_called_once()

    def test_no_context_marker_never_skipped(self):
        """Tests without @context should never be context-skipped."""
        from rspy.pytest.collection import filter_and_sort_items

        item = self._make_item([])
        config = self._make_config(context="")

        filter_and_sort_items(config, [item])

        item.add_marker.assert_not_called()


class TestLiveFiltering:
    """Tests for --live flag filtering."""

    def _make_item(self, marker_names):
        item = MagicMock()
        item.name = "test_example"
        marks = [MagicMock(name=n) for n in marker_names]
        # MagicMock's name attr is special, set it explicitly
        for m, n in zip(marks, marker_names):
            m.name = n
            m.args = ("D455",)

        def iter_markers(name=None):
            for m in marks:
                if name is None or m.name == name:
                    yield m

        item.iter_markers = iter_markers
        item.get_closest_marker = lambda n: next(
            (m for m in marks if m.name == n), None
        )
        # For sorting — need module and callspec
        item.module = types.ModuleType("fake_module")
        item.callspec = MagicMock()
        item.callspec.params = {}
        delattr(item, 'callspec')  # remove so hasattr returns False
        return item

    def _make_config(self, live=False):
        config = MagicMock()
        def getoption(key, default=None):
            opts = {
                "--context": "",
                "--live": live,
                "-m": "",
            }
            return opts.get(key, default)
        config.getoption = getoption
        return config

    def test_live_skips_non_device_tests(self):
        """--live should skip tests without device/device_each markers."""
        from rspy.pytest.collection import filter_and_sort_items

        item = self._make_item([])  # no device markers
        config = self._make_config(live=True)

        filter_and_sort_items(config, [item])

        item.add_marker.assert_called_once()
        skip_marker = item.add_marker.call_args[0][0]
        assert skip_marker.name == "skip"

    def test_live_keeps_device_tests(self):
        """--live should NOT skip tests with device marker."""
        from rspy.pytest.collection import filter_and_sort_items

        item = self._make_item(["device"])
        config = self._make_config(live=True)

        filter_and_sort_items(config, [item])

        item.add_marker.assert_not_called()

    def test_live_keeps_device_each_tests(self):
        """--live should NOT skip tests with device_each marker."""
        from rspy.pytest.collection import filter_and_sort_items

        item = self._make_item(["device_each"])
        config = self._make_config(live=True)

        filter_and_sort_items(config, [item])

        item.add_marker.assert_not_called()

    def test_no_live_keeps_everything(self):
        """Without --live, non-device tests should NOT be skipped."""
        from rspy.pytest.collection import filter_and_sort_items

        item = self._make_item([])
        config = self._make_config(live=False)

        filter_and_sort_items(config, [item])

        item.add_marker.assert_not_called()


class TestPrioritySorting:
    """Tests for @pytest.mark.priority() sorting."""

    def _make_item(self, name, priority=None):
        item = MagicMock()
        item.name = name

        marker = None
        if priority is not None:
            marker = MagicMock()
            marker.name = "priority"
            marker.args = (priority,)

        def iter_markers(n=None):
            if marker and (n is None or n == "priority"):
                yield marker
            # No context markers
            return

        item.iter_markers = iter_markers
        item.get_closest_marker = lambda n: marker if (marker and n == "priority") else None

        # For device grouping sort key
        item.module = types.ModuleType("fake_module")
        try:
            del item.callspec
        except AttributeError:
            pass
        return item

    def _make_config(self):
        config = MagicMock()
        config.getoption = lambda key, default=None: {
            "--context": "", "--live": False, "-m": "",
        }.get(key, default)
        return config

    def test_priority_ordering(self):
        """Lower priority values should come first."""
        from rspy.pytest.collection import filter_and_sort_items

        items = [
            self._make_item("test_low", priority=100),
            self._make_item("test_default"),  # 500
            self._make_item("test_high", priority=900),
            self._make_item("test_first", priority=1),
        ]
        config = self._make_config()

        filter_and_sort_items(config, items)

        names = [i.name for i in items]
        assert names[0] == "test_first"
        assert names[1] == "test_low"
        # test_default (500) and test_high (900) come after
        # They may reorder due to device grouping, but priority order is maintained
        # within same module
        assert names.index("test_default") < names.index("test_high")

    def test_default_priority_is_500(self):
        """Tests without @priority should get default 500."""
        from rspy.pytest.collection import filter_and_sort_items

        items = [
            self._make_item("test_no_prio"),
            self._make_item("test_below_default", priority=499),
            self._make_item("test_above_default", priority=501),
        ]
        config = self._make_config()

        filter_and_sort_items(config, items)

        names = [i.name for i in items]
        assert names[0] == "test_below_default"
        # test_no_prio (500) should come before test_above_default (501)
        assert names.index("test_no_prio") < names.index("test_above_default")


class TestDeviceGrouping:
    """Tests for device-grouping sort (tests grouped by module+serial)."""

    def _make_item(self, name, module_name, serial=None):
        item = MagicMock()
        item.name = name
        item.module = types.ModuleType(module_name)

        if serial:
            item.callspec = MagicMock()
            item.callspec.params = {'_test_device_serial': serial}
        else:
            # Ensure hasattr(item, 'callspec') returns False
            del item.callspec

        def iter_markers(n=None):
            return iter([])
        item.iter_markers = iter_markers
        item.get_closest_marker = lambda n: None
        return item

    def _make_config(self):
        config = MagicMock()
        config.getoption = lambda key, default=None: {
            "--context": "", "--live": False, "-m": "",
        }.get(key, default)
        return config

    def test_grouped_by_module_and_device(self):
        """Tests should be grouped so all tests for one device in a module run together."""
        from rspy.pytest.collection import filter_and_sort_items

        items = [
            self._make_item("test_a[D455-111]", "mod_frames", "111"),
            self._make_item("test_a[D435-222]", "mod_frames", "222"),
            self._make_item("test_b[D455-111]", "mod_frames", "111"),
            self._make_item("test_b[D435-222]", "mod_frames", "222"),
        ]
        config = self._make_config()

        filter_and_sort_items(config, items)

        names = [i.name for i in items]
        # All D455 tests should be adjacent, all D435 tests should be adjacent
        d455_indices = [i for i, n in enumerate(names) if "D455" in n]
        d435_indices = [i for i, n in enumerate(names) if "D435" in n]
        assert d455_indices == [0, 1] or d455_indices == [2, 3]
        assert d435_indices == [0, 1] or d435_indices == [2, 3]
        # And they shouldn't overlap
        assert set(d455_indices) & set(d435_indices) == set()


# ---------------------------------------------------------------------------
# 2. device_helpers.py — find_matching_devices
# ---------------------------------------------------------------------------

class TestFindMatchingDevices:
    """Tests for device pattern resolution and filtering."""

    @pytest.fixture(autouse=True)
    def mock_devices(self):
        import rspy.devices as dev_module
        orig_by_spec = dev_module.by_spec
        orig_get = dev_module.get
        dev_module.by_spec = _fake_by_spec
        dev_module.get = _fake_get
        yield
        dev_module.by_spec = orig_by_spec
        dev_module.get = orig_get

    def _marker(self, name, pattern):
        m = MagicMock()
        m.name = name
        m.args = (pattern,)
        return m

    def test_basic_pattern_match(self):
        """device_each('D455') should find the D455 device."""
        from rspy.pytest.device_helpers import find_matching_devices

        markers = [self._marker('device_each', 'D455')]
        sns, had = find_matching_devices(markers, each=True)

        assert sns == ['111']
        assert had is True

    def test_wildcard_pattern(self):
        """device_each('D400*') should find all D4xx devices."""
        from rspy.pytest.device_helpers import find_matching_devices

        markers = [self._marker('device_each', 'D400*')]
        sns, had = find_matching_devices(markers, each=True)

        # D455(111), D435(222), D435i(333), D405(444), D401(777), D457(888)
        assert len(sns) == 6
        assert '111' in sns
        assert '222' in sns
        assert had is True

    def test_exclude_pattern(self):
        """device_exclude('D401') should remove D401 from results."""
        from rspy.pytest.device_helpers import find_matching_devices

        markers = [
            self._marker('device_each', 'D400*'),
            self._marker('device_exclude', 'D401'),
        ]
        sns, had = find_matching_devices(markers, each=True)

        assert '777' not in sns  # D401 excluded
        assert '111' in sns      # D455 still present
        assert had is True

    def test_cli_include_filter(self):
        """--device D455 should restrict results to only D455."""
        from rspy.pytest.device_helpers import find_matching_devices

        markers = [self._marker('device_each', 'D400*')]
        sns, had = find_matching_devices(markers, each=True, cli_includes=['D455'])

        assert sns == ['111']
        assert had is True

    def test_cli_exclude_filter(self):
        """--exclude-device D455 should remove D455 from results."""
        from rspy.pytest.device_helpers import find_matching_devices

        markers = [self._marker('device_each', 'D400*')]
        sns, had = find_matching_devices(markers, each=True, cli_excludes=['D455'])

        assert '111' not in sns
        assert '222' in sns  # D435 still there

    def test_each_false_returns_first(self):
        """each=False should return only the first matching device."""
        from rspy.pytest.device_helpers import find_matching_devices

        markers = [self._marker('device', 'D400*')]
        sns, had = find_matching_devices(markers, each=False)

        assert len(sns) == 1
        assert had is True

    def test_no_match_returns_empty(self):
        """Pattern that matches nothing should return empty list."""
        from rspy.pytest.device_helpers import find_matching_devices

        markers = [self._marker('device_each', 'D999')]
        sns, had = find_matching_devices(markers, each=True)

        assert sns == []
        assert had is False

    def test_multiple_device_each_markers(self):
        """Multiple device_each markers should union their results."""
        from rspy.pytest.device_helpers import find_matching_devices

        markers = [
            self._marker('device_each', 'D455'),
            self._marker('device_each', 'D515'),
        ]
        sns, had = find_matching_devices(markers, each=True)

        assert '111' in sns  # D455
        assert '555' in sns  # D515
        assert len(sns) == 2

    def test_exclude_plus_cli_include(self):
        """Both marker exclude and CLI include should stack."""
        from rspy.pytest.device_helpers import find_matching_devices

        markers = [
            self._marker('device_each', 'D400*'),
            self._marker('device_exclude', 'D401'),
        ]
        # CLI further restricts to D455 and D435 only
        sns, had = find_matching_devices(markers, each=True, cli_includes=['D455', 'D435'])

        assert set(sns) == {'111', '222'}

    def test_no_duplicate_serials(self):
        """Overlapping markers should not produce duplicate serial numbers."""
        from rspy.pytest.device_helpers import find_matching_devices

        markers = [
            self._marker('device_each', 'D455'),
            self._marker('device_each', 'D400*'),  # also includes D455
        ]
        sns, had = find_matching_devices(markers, each=True)

        assert sns.count('111') == 1  # D455 appears once


# ---------------------------------------------------------------------------
# 3. cli.py — legacy flag translation
# ---------------------------------------------------------------------------

class TestLegacyCliFlags:
    """Tests for legacy CLI flag consumption and translation."""

    def test_regex_short_flag(self):
        """'-r pattern' should be consumed and translated to '-k pattern'."""
        from rspy.pytest.cli import _consume_flag_with_arg

        original_argv = sys.argv.copy()
        try:
            sys.argv = ['pytest', '-r', 'test_depth', 'some_file.py']
            result = _consume_flag_with_arg(['-r', '--regex'], '-k')

            assert result == 'test_depth'
            assert '-r' not in sys.argv
            assert '-k' in sys.argv
            assert 'test_depth' in sys.argv
        finally:
            sys.argv = original_argv

    def test_regex_long_flag(self):
        """'--regex pattern' should be consumed and translated to '-k pattern'."""
        from rspy.pytest.cli import _consume_flag_with_arg

        original_argv = sys.argv.copy()
        try:
            sys.argv = ['pytest', '--regex', 'test_depth', 'some_file.py']
            result = _consume_flag_with_arg(['-r', '--regex'], '-k')

            assert result == 'test_depth'
            assert '--regex' not in sys.argv
            assert '-k' in sys.argv
        finally:
            sys.argv = original_argv

    def test_no_flag_present(self):
        """When neither -r nor --regex is present, nothing should change."""
        from rspy.pytest.cli import _consume_flag_with_arg

        original_argv = sys.argv.copy()
        try:
            sys.argv = ['pytest', 'some_file.py']
            result = _consume_flag_with_arg(['-r', '--regex'], '-k')

            assert result is None
            assert sys.argv == ['pytest', 'some_file.py']
        finally:
            sys.argv = original_argv

    def test_apply_pending_flags(self):
        """apply_pending_flags should set config.option.keyword from sys.argv -k."""
        from rspy.pytest.cli import apply_pending_flags

        original_argv = sys.argv.copy()
        try:
            sys.argv = ['pytest', '-k', 'test_depth']
            config = MagicMock()
            config.option.keyword = ""

            apply_pending_flags(config)

            assert config.option.keyword == 'test_depth'
        finally:
            sys.argv = original_argv

    def test_apply_pending_flags_no_override(self):
        """apply_pending_flags should NOT override an existing -k value."""
        from rspy.pytest.cli import apply_pending_flags

        original_argv = sys.argv.copy()
        try:
            sys.argv = ['pytest', '-k', 'test_depth']
            config = MagicMock()
            config.option.keyword = "already_set"

            apply_pending_flags(config)

            # Should not change because keyword was already set
            assert config.option.keyword == "already_set"
        finally:
            sys.argv = original_argv


# ---------------------------------------------------------------------------
# 4. logging_setup.py — test_log_name and _log_key
# ---------------------------------------------------------------------------

class TestLogNaming:
    """Tests for per-test log file naming."""

    def _make_item(self, fspath, name):
        item = MagicMock()
        item.fspath = fspath
        item.name = name
        return item

    def test_log_name_with_device_param(self):
        """test[D455-111] should produce pytest-depth_D455-111.log."""
        from rspy.pytest.logging_setup import test_log_name

        item = self._make_item(
            "live/frames/pytest-depth.py",
            "test_depth_laser_on[D455-104623060005]"
        )
        result = test_log_name(item)

        assert result == "pytest-depth_D455-104623060005.log"

    def test_log_name_without_device_param(self):
        """test without brackets should produce pytest-depth.log."""
        from rspy.pytest.logging_setup import test_log_name

        item = self._make_item(
            "live/frames/pytest-depth.py",
            "test_depth_basic"
        )
        result = test_log_name(item)

        assert result == "pytest-depth.log"

    def test_log_name_special_chars_sanitized(self):
        """Special characters in device IDs should be replaced with underscores."""
        from rspy.pytest.logging_setup import test_log_name

        item = self._make_item(
            "live/frames/pytest-depth.py",
            "test_depth[D455<special>]"
        )
        result = test_log_name(item)

        # < and > should be replaced with _
        assert "<" not in result
        assert ">" not in result
        assert result.endswith(".log")

    def test_log_key_with_brackets(self):
        """_log_key should extract device_id from brackets."""
        from rspy.pytest.logging_setup import _log_key

        item = self._make_item("live/frames/pytest-depth.py", "test_x[D455-111]")
        key = _log_key(item)

        assert key == ("live/frames/pytest-depth.py", "D455-111")

    def test_log_key_without_brackets(self):
        """_log_key should return None device_id when no brackets."""
        from rspy.pytest.logging_setup import _log_key

        item = self._make_item("live/frames/pytest-depth.py", "test_x")
        key = _log_key(item)

        assert key == ("live/frames/pytest-depth.py", None)

    def test_log_key_none_item(self):
        """_log_key(None) should return None."""
        from rspy.pytest.logging_setup import _log_key

        assert _log_key(None) is None


# ---------------------------------------------------------------------------
# 5. pytester integration tests — end-to-end with real pytest subprocess
# ---------------------------------------------------------------------------

# The conftest.py source that pytester will use. We embed the parts of the
# infrastructure that don't require pyrealsense2 or real hardware.

# We need to point pytester at the real conftest, but with devices mocked.
# The simplest approach: copy the infra modules and patch device queries.

_MOCK_CONFTEST = r'''
"""
Pytester conftest: mock ONLY the hardware layer, then exec() the REAL conftest.py.

This ensures we test the actual hooks, fixtures, and skip/fail logic — not a copy.
If someone changes conftest.py, these tests exercise the real change.
"""
import sys
import os
import types

# ---------------------------------------------------------------------------
# 1. Paths
# ---------------------------------------------------------------------------
_py_dir = r"{py_dir}"
if _py_dir not in sys.path:
    sys.path.insert(0, _py_dir)

# ---------------------------------------------------------------------------
# 2. Fake pyrealsense2 — just enough for the real conftest to load
# ---------------------------------------------------------------------------
_rs = types.ModuleType("pyrealsense2")
_rs.__file__ = "fake_pyrealsense2"
_rs.log_to_console = lambda level: None

class _CameraInfo:
    name = "name"
    product_line = "product_line"
    physical_port = "physical_port"
    connection_type = "connection_type"
_rs.camera_info = _CameraInfo

class _LogSeverity:
    debug = 0
_rs.log_severity = _LogSeverity

class _FakeContext:
    @property
    def devices(self):
        return []
_rs.context = _FakeContext

sys.modules["pyrealsense2"] = _rs

# ---------------------------------------------------------------------------
# 3. Mock rspy.devices hardware layer (before the real conftest imports it)
# ---------------------------------------------------------------------------
class FakeDevice:
    def __init__(self, sn, name):
        self.sn = sn
        self.name = name

# name -> (serial, product_line)
_inventory = {{
    "D455": ("111", "D400"),
    "D435": ("222", "D400"),
    "D515": ("555", "D500"),
    "D401": ("777", "D400"),
}}
_sn_map = {{"111": "D455", "222": "D435", "555": "D515", "777": "D401"}}

import rspy.devices as _dev

def _mock_by_spec(pattern, ignored):
    if pattern.endswith("*"):
        product_line = pattern[:-1]
        for name, (sn, pl) in _inventory.items():
            if pl == product_line:
                yield sn
    elif pattern in _inventory:
        yield _inventory[pattern][0]
    elif pattern in _sn_map:
        yield pattern

def _mock_get(sn):
    name = _sn_map.get(sn)
    return FakeDevice(sn, name) if name else None

_dev.by_spec = _mock_by_spec
_dev.get = _mock_get
_dev._device_by_sn = {{sn: FakeDevice(sn, n) for sn, n in _sn_map.items()}}
_dev.hub = None
_dev._context = None
_dev.query = lambda **kw: None
_dev.map_unknown_ports = lambda: None
_dev.enable_only = lambda serials, recycle=True: None
_dev.wait_until_all_ports_disabled = lambda: None

# ---------------------------------------------------------------------------
# 4. exec() the REAL conftest.py — all hooks and fixtures come from there
# ---------------------------------------------------------------------------
_conftest_path = r"{conftest_path}"
with open(_conftest_path) as _f:
    _src = _f.read()

# Pre-set variables that the real conftest computes from __file__ so its
# os.path.dirname(__file__) resolves to the real unit-tests/ directory.
# We must NOT override __file__ itself — pytest validates conftest path identity.
_real_unit_tests_dir = os.path.dirname(_conftest_path)
current_dir = _real_unit_tests_dir
py_dir = os.path.join(_real_unit_tests_dir, "py")
if py_dir not in sys.path:
    sys.path.insert(0, py_dir)

exec(compile(_src, _conftest_path, "exec"), globals())
'''

# Common args to disable installed plugins that interfere with pytester subprocess
_NO_PLUGINS = ["-p", "no:retry", "-p", "no:timeout", "-p", "no:repeat"]


@pytest.fixture
def pytester_with_infra(pytester):
    """Set up pytester with a conftest that mocks only hardware, then exec()s the real conftest.py.

    Uses subprocess mode to isolate from plugins installed in the parent process
    (pytest-retry, pytest-timeout, etc.) that would interfere.
    """
    py_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', 'py')
    )
    conftest_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', 'conftest.py')
    )
    conftest_src = _MOCK_CONFTEST.format(
        py_dir=py_dir.replace('\\', '\\\\'),
        conftest_path=conftest_path.replace('\\', '\\\\'),
    )
    pytester.makeconftest(conftest_src)

    # Wrap runpytest to always use subprocess with plugin isolation
    _original = pytester.runpytest_subprocess

    def _run(*args, **kwargs):
        return _original(*_NO_PLUGINS, *args, **kwargs)

    pytester.runpytest = _run
    return pytester


class TestMarkerRegistration:
    """Verify all custom markers are registered (no unknown-marker warnings)."""

    def test_no_marker_warnings(self, pytester_with_infra):
        """Using custom markers should not produce PytestUnknownMarkWarning."""
        pytester_with_infra.makepyfile(**{"pytest-markers": """
            import pytest

            pytestmark = [
                pytest.mark.device_each("D455"),
                pytest.mark.device_exclude("D401"),
                pytest.mark.context("nightly"),
                pytest.mark.priority(100),
            ]

            def test_example(_test_device_serial):
                pass
        """})
        result = pytester_with_infra.runpytest(
            "--context", "nightly", "-W", "error::pytest.PytestUnknownMarkWarning", "-v")
        result.assert_outcomes(passed=1)

    def test_device_marker_registered(self, pytester_with_infra):
        """@device marker should be recognized."""
        pytester_with_infra.makepyfile(**{"pytest-devmark": """
            import pytest
            pytestmark = [pytest.mark.device("D455")]

            def test_with_device():
                pass
        """})
        result = pytester_with_infra.runpytest("-W", "error::pytest.PytestUnknownMarkWarning")
        result.assert_outcomes(passed=1)


class TestContextGatingE2E:
    """End-to-end context gating with real pytest collection."""

    def test_nightly_skipped_by_default(self, pytester_with_infra):
        """@context('nightly') test should be skipped without --context nightly."""
        pytester_with_infra.makepyfile(**{"pytest-ctx": """
            import pytest
            pytestmark = [pytest.mark.context("nightly")]

            def test_nightly_only():
                pass
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(skipped=1)

    def test_nightly_runs_with_context(self, pytester_with_infra):
        """@context('nightly') test should run when --context nightly is provided."""
        pytester_with_infra.makepyfile(**{"pytest-ctx": """
            import pytest
            pytestmark = [pytest.mark.context("nightly")]

            def test_nightly_only():
                pass
        """})
        result = pytester_with_infra.runpytest("--context", "nightly", "-v")
        result.assert_outcomes(passed=1)

    def test_mixed_context_and_normal(self, pytester_with_infra):
        """Normal tests should run while nightly tests are skipped."""
        pytester_with_infra.makepyfile(**{"pytest-mixed": """
            import pytest

            def test_always():
                pass

            @pytest.mark.context("nightly")
            def test_nightly_only():
                pass
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(passed=1, skipped=1)


class TestLiveFilteringE2E:
    """End-to-end --live flag filtering."""

    def test_live_skips_no_device_tests(self, pytester_with_infra):
        """--live should skip tests without device markers."""
        pytester_with_infra.makepyfile(**{"pytest-nolive": """
            def test_no_device():
                pass
        """})
        result = pytester_with_infra.runpytest("--live", "-v")
        result.assert_outcomes(skipped=1)

    def test_live_keeps_device_each_tests(self, pytester_with_infra):
        """--live should keep tests with @device_each."""
        pytester_with_infra.makepyfile(**{"pytest-withlive": """
            import pytest
            pytestmark = [pytest.mark.device_each("D455")]

            def test_with_device(_test_device_serial):
                pass
        """})
        result = pytester_with_infra.runpytest("--live", "-v")
        result.assert_outcomes(passed=1)

    def test_live_mixed(self, pytester_with_infra):
        """--live with mixed tests: device tests pass, non-device skipped."""
        pytester_with_infra.makepyfile(**{"pytest-livemix": """
            import pytest

            def test_no_device():
                pass

            @pytest.mark.device_each("D455")
            def test_with_device(_test_device_serial):
                pass
        """})
        result = pytester_with_infra.runpytest("--live", "-v")
        result.assert_outcomes(passed=1, skipped=1)


class TestDeviceEachParametrization:
    """End-to-end device_each parametrization."""

    def test_device_each_creates_instances(self, pytester_with_infra):
        """@device_each('D400*') should create one test per matching device."""
        pytester_with_infra.makepyfile(**{"pytest-each": """
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]

            def test_per_device(_test_device_serial):
                assert _test_device_serial in ('111', '222', '777')
        """})
        result = pytester_with_infra.runpytest("-v")
        # D400* matches D455(111), D435(222), D401(777) in our mock inventory
        result.assert_outcomes(passed=3)

    def test_device_each_with_exclude(self, pytester_with_infra):
        """@device_each + @device_exclude should exclude matching devices."""
        pytester_with_infra.makepyfile(**{"pytest-exclude": """
            import pytest
            pytestmark = [
                pytest.mark.device_each("D400*"),
                pytest.mark.device_exclude("D401"),
            ]

            def test_per_device(_test_device_serial):
                assert _test_device_serial != '777'  # D401 excluded
        """})
        result = pytester_with_infra.runpytest("-v")
        # D400* minus D401 = D455(111), D435(222)
        result.assert_outcomes(passed=2)

    def test_device_each_with_cli_device_filter(self, pytester_with_infra):
        """--device D455 should restrict device_each to only D455."""
        pytester_with_infra.makepyfile(**{"pytest-clifilt": """
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]

            def test_per_device(_test_device_serial):
                assert _test_device_serial == '111'
        """})
        result = pytester_with_infra.runpytest("--device", "D455", "-v")
        result.assert_outcomes(passed=1)

    def test_device_each_cli_exclude(self, pytester_with_infra):
        """--exclude-device D455 should remove D455 from device_each results."""
        pytester_with_infra.makepyfile(**{"pytest-cliexcl": """
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]

            def test_per_device(_test_device_serial):
                assert _test_device_serial != '111'  # D455 excluded by CLI
        """})
        result = pytester_with_infra.runpytest("--exclude-device", "D455", "-v")
        # D400* minus D455 = D435(222), D401(777)
        result.assert_outcomes(passed=2)

    def test_device_each_no_match_collected_zero(self, pytester_with_infra):
        """device_each with no matching devices should not parametrize any instances."""
        pytester_with_infra.makepyfile(**{"pytest-nomatch": """
            import pytest
            pytestmark = [pytest.mark.device_each("D999")]

            def test_per_device():
                # No _test_device_serial param since device_each matched nothing
                pass
        """})
        result = pytester_with_infra.runpytest("-v")
        # Test runs once (un-parametrized) since device_each found no matches
        result.assert_outcomes(passed=1)

    def test_multiple_device_each_union(self, pytester_with_infra):
        """Multiple device_each markers should union their device sets."""
        pytester_with_infra.makepyfile(**{"pytest-union": """
            import pytest
            pytestmark = [
                pytest.mark.device_each("D455"),
                pytest.mark.device_each("D515"),
            ]

            def test_per_device(_test_device_serial):
                assert _test_device_serial in ('111', '555')
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(passed=2)

    def test_test_ids_contain_device_name(self, pytester_with_infra):
        """Parametrized test IDs should contain device name and serial."""
        pytester_with_infra.makepyfile(**{"pytest-ids": """
            import pytest
            pytestmark = [pytest.mark.device_each("D455")]

            def test_check(_test_device_serial):
                pass
        """})
        result = pytester_with_infra.runpytest("-v")
        result.stdout.fnmatch_lines(["*D455-111*"])


class TestDeviceSkipFailBehavior:
    """Test that @device fails and @device_each skips when no devices match."""

    def test_device_fails_when_no_match(self, pytester_with_infra):
        """@device('D999') with no matching device should fail (error in setup)."""
        pytester_with_infra.makepyfile(**{"pytest-devfail": """
            import pytest
            pytestmark = [pytest.mark.device("D999")]

            def test_needs_device(module_device_setup):
                pass
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(errors=1)
        result.stdout.fnmatch_lines(["*No devices found*"])

    def test_device_each_skips_when_no_match(self, pytester_with_infra):
        """@device_each('D999') should SKIP (not fail) when no device matches.

        Unlike @device which fails hard, device_each skips gracefully — a test
        requesting "each D585S" on a machine with no D585S should not be a failure.
        """
        pytester_with_infra.makepyfile(**{"pytest-devskip": """
            import pytest
            pytestmark = [pytest.mark.device_each("D999")]

            def test_needs_device(module_device_setup):
                pass
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(skipped=1)

    def test_device_skips_when_all_excluded(self, pytester_with_infra):
        """@device('D455') + @device_exclude('D455') should SKIP (had candidates, all excluded)."""
        pytester_with_infra.makepyfile(**{"pytest-devexcl": """
            import pytest
            pytestmark = [
                pytest.mark.device("D455"),
                pytest.mark.device_exclude("D455"),
            ]

            def test_needs_device(module_device_setup):
                pass
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(skipped=1)

    def test_device_each_skips_when_all_excluded(self, pytester_with_infra):
        """@device_each('D455') + --exclude-device D455 should SKIP."""
        pytester_with_infra.makepyfile(**{"pytest-eachexcl": """
            import pytest
            pytestmark = [pytest.mark.device_each("D455")]

            def test_needs_device(module_device_setup):
                pass
        """})
        result = pytester_with_infra.runpytest("--exclude-device", "D455", "-v")
        # device_each parametrization finds no serials after exclusion → not parametrized
        # module_device_setup sees device_each marker, had_candidates=True → skip
        result.assert_outcomes(skipped=1)

    def test_device_passes_when_match_exists(self, pytester_with_infra):
        """@device('D455') should pass when the device is available."""
        pytester_with_infra.makepyfile(**{"pytest-devpass": """
            import pytest
            pytestmark = [pytest.mark.device("D455")]

            def test_needs_device(module_device_setup):
                assert module_device_setup == '111'
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_no_device_markers_yields_none(self, pytester_with_infra):
        """Test without device markers should get None from module_device_setup."""
        pytester_with_infra.makepyfile(**{"pytest-nodev": """
            def test_no_device(module_device_setup):
                assert module_device_setup is None
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(passed=1)


class TestPriorityOrderingE2E:
    """End-to-end priority-based test ordering."""

    def test_priority_order(self, pytester_with_infra):
        """Tests should run in priority order (lower first)."""
        pytester_with_infra.makepyfile(**{"pytest-prio": """
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
                # This runs with default priority 500, after test_first (100)
                # but ordering among same-priority is stable
                assert execution_order == ['first', 'middle']
        """})
        result = pytester_with_infra.runpytest("-v")
        # All 4 should pass; verify_order checks first and middle ran before it
        result.assert_outcomes(passed=4)


class TestCliOptionsRegistered:
    """Verify all custom CLI options are registered and usable."""

    def test_device_option(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-opt": "def test_pass(): pass"})
        result = pytester_with_infra.runpytest("--device", "D455")
        assert result.ret == 0

    def test_exclude_device_option(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-opt": "def test_pass(): pass"})
        result = pytester_with_infra.runpytest("--exclude-device", "D455")
        assert result.ret == 0

    def test_context_option(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-opt": "def test_pass(): pass"})
        result = pytester_with_infra.runpytest("--context", "nightly")
        assert result.ret == 0

    def test_live_option(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-opt": "def test_pass(): pass"})
        result = pytester_with_infra.runpytest("--live")
        # test_pass has no device marker, so it's skipped
        result.assert_outcomes(skipped=1)

    def test_no_reset_option(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-opt": "def test_pass(): pass"})
        result = pytester_with_infra.runpytest("--no-reset")
        assert result.ret == 0

    def test_hub_reset_option(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-opt": "def test_pass(): pass"})
        result = pytester_with_infra.runpytest("--hub-reset")
        assert result.ret == 0

    def test_rslog_option(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-opt": "def test_pass(): pass"})
        result = pytester_with_infra.runpytest("--rslog")
        assert result.ret == 0

    def test_rs_help_option(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-opt": "def test_pass(): pass"})
        result = pytester_with_infra.runpytest("--rs-help")
        assert result.ret == 0

    def test_multiple_device_flags(self, pytester_with_infra):
        """--device should be usable multiple times (append mode)."""
        pytester_with_infra.makepyfile(**{"pytest-opt": """
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]

            def test_multi(_test_device_serial):
                assert _test_device_serial in ('111', '222')
        """})
        result = pytester_with_infra.runpytest("--device", "D455", "--device", "D435", "-v")
        result.assert_outcomes(passed=2)

    def test_multiple_exclude_device_flags(self, pytester_with_infra):
        """--exclude-device should be usable multiple times (append mode)."""
        pytester_with_infra.makepyfile(**{"pytest-opt": """
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]

            def test_multi(_test_device_serial):
                # D455(111) and D435(222) excluded, only D401(777) remains
                assert _test_device_serial == '777'
        """})
        result = pytester_with_infra.runpytest(
            "--exclude-device", "D455", "--exclude-device", "D435", "-v")
        result.assert_outcomes(passed=1)

    def test_device_and_exclude_device_combined(self, pytester_with_infra):
        """--device and --exclude-device should work together."""
        pytester_with_infra.makepyfile(**{"pytest-opt": """
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]

            def test_filtered(_test_device_serial):
                # Include D400* but only D455 and D435, then exclude D435
                assert _test_device_serial == '111'
        """})
        result = pytester_with_infra.runpytest(
            "--device", "D455", "--device", "D435",
            "--exclude-device", "D435", "-v")
        result.assert_outcomes(passed=1)
