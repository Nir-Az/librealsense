# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
Regression tests for the pytest infrastructure (conftest.py + rspy/pytest/*.py).

No cameras or pyrealsense2 required. Only the hardware layer is mocked.

Run with:
    cd unit-tests && python -m pytest infra-tests/ -v
"""

import sys
import os
import types
from unittest.mock import MagicMock
import pytest

from rspy.pytest.collection import filter_and_sort_items
from rspy.pytest.device_helpers import find_matching_devices
from rspy.pytest.cli import _consume_flag_with_arg, apply_pending_flags
from rspy.pytest.logging_setup import test_log_name as derive_log_name, _log_key


# =============================================================================
# Shared fake device inventory (used by both unit tests and pytester E2E tests)
# =============================================================================
#
#   name   serial  product_line
#   D455   111     D400
#   D435   222     D400
#   D435i  333     D400
#   D405   444     D400
#   D401   777     D400
#   D457   888     D400
#   D515   555     D500
#   D555   666     D500
#
# The pytester E2E conftest uses a subset (D455, D435, D515, D401) — enough to
# test wildcards, excludes, and multi-device parametrization without noise.

DEVICES = {
    #  name:  (serial, product_line)
    'D455':  ('111', 'D400'),
    'D435':  ('222', 'D400'),
    'D435i': ('333', 'D400'),
    'D405':  ('444', 'D400'),
    'D401':  ('777', 'D400'),
    'D457':  ('888', 'D400'),
    'D515':  ('555', 'D500'),
    'D555':  ('666', 'D500'),
}

SN_TO_NAME = {sn: name for name, (sn, _) in DEVICES.items()}


class FakeDevice:
    """Minimal stand-in for rspy.devices.Device."""
    def __init__(self, sn, name):
        self.sn = sn
        self.name = name


def fake_by_spec(pattern, ignored):
    """Mock devices.by_spec against the DEVICES inventory."""
    if pattern.endswith('*'):
        product_line = pattern[:-1]
        for name, (sn, pl) in DEVICES.items():
            if pl == product_line:
                yield sn
    elif pattern in DEVICES:
        yield DEVICES[pattern][0]
    elif pattern in SN_TO_NAME:
        yield pattern


def fake_get(sn):
    """Mock devices.get against the DEVICES inventory."""
    name = SN_TO_NAME.get(sn)
    return FakeDevice(sn, name) if name else None


# =============================================================================
# Shared mock builders for unit tests
# =============================================================================

def make_mock_item(name="test_example", markers=None, module_name="fake_module",
                   device_serial=None):
    """Build a mock pytest Item for unit-testing collection/filter logic.

    Args:
        name:          Test name (shown in output).
        markers:       List of pytest markers (e.g. pytest.mark.context("nightly")).
        module_name:   Module name for device-grouping sort key.
        device_serial: If set, simulates a parametrized device_each test.
    """
    item = MagicMock()
    item.name = name
    item.module = types.ModuleType(module_name)

    # Parametrized device serial (from device_each)
    if device_serial:
        item.callspec = MagicMock()
        item.callspec.params = {'_test_device_serial': device_serial}
    else:
        del item.callspec  # so hasattr(item, 'callspec') is False

    marks = list(markers or [])

    def iter_markers(match_name=None):
        for m in marks:
            if match_name is None or m.name == match_name:
                yield m

    item.iter_markers = iter_markers
    item.get_closest_marker = lambda n: next(
        (m for m in marks if m.name == n), None
    )
    return item


def make_mock_config(context="", live=False, markexpr=""):
    """Build a mock pytest Config for unit-testing collection/filter logic."""
    config = MagicMock()
    opts = {"--context": context, "--live": live, "-m": markexpr}
    config.getoption = lambda key, default=None: opts.get(key, default)
    return config


def make_device_marker(name, pattern):
    """Build a mock marker (device/device_each/device_exclude) for find_matching_devices tests."""
    m = MagicMock()
    m.name = name
    m.args = (pattern,)
    return m


# =============================================================================
# 1. collection.py — context gating
# =============================================================================

class TestContextGating:
    """@pytest.mark.context() should skip tests unless --context or -m matches."""

    def test_skipped_when_context_not_provided(self):
        item = make_mock_item(markers=[pytest.mark.context("nightly")])
        filter_and_sort_items(make_mock_config(context=""), [item])

        item.add_marker.assert_called_once()
        assert item.add_marker.call_args[0][0].name == "skip"

    def test_runs_when_context_matches(self):
        item = make_mock_item(markers=[pytest.mark.context("nightly")])
        filter_and_sort_items(make_mock_config(context="nightly"), [item])

        item.add_marker.assert_not_called()

    def test_runs_when_m_flag_matches(self):
        item = make_mock_item(markers=[pytest.mark.context("nightly")])
        filter_and_sort_items(make_mock_config(markexpr="nightly"), [item])

        item.add_marker.assert_not_called()

    def test_multiple_context_values(self):
        """--context 'nightly weekly' should satisfy @context('nightly')."""
        item = make_mock_item(markers=[pytest.mark.context("nightly")])
        filter_and_sort_items(make_mock_config(context="nightly weekly"), [item])

        item.add_marker.assert_not_called()

    def test_wrong_context_still_skips(self):
        """--context 'weekly' should NOT satisfy @context('nightly')."""
        item = make_mock_item(markers=[pytest.mark.context("nightly")])
        filter_and_sort_items(make_mock_config(context="weekly"), [item])

        item.add_marker.assert_called_once()

    def test_no_context_marker_never_skipped(self):
        item = make_mock_item(markers=[])
        filter_and_sort_items(make_mock_config(), [item])

        item.add_marker.assert_not_called()


# =============================================================================
# 2. collection.py — --live filtering
# =============================================================================

class TestLiveFiltering:
    """--live should skip tests that have no device/device_each markers."""

    def _device_marker(self, name):
        m = MagicMock()
        m.name = name
        m.args = ("D455",)
        return m

    def test_skips_non_device_tests(self):
        item = make_mock_item()
        filter_and_sort_items(make_mock_config(live=True), [item])

        item.add_marker.assert_called_once()
        assert item.add_marker.call_args[0][0].name == "skip"

    def test_keeps_device_tests(self):
        item = make_mock_item(markers=[self._device_marker("device")])
        filter_and_sort_items(make_mock_config(live=True), [item])

        item.add_marker.assert_not_called()

    def test_keeps_device_each_tests(self):
        item = make_mock_item(markers=[self._device_marker("device_each")])
        filter_and_sort_items(make_mock_config(live=True), [item])

        item.add_marker.assert_not_called()

    def test_no_live_flag_keeps_everything(self):
        item = make_mock_item()
        filter_and_sort_items(make_mock_config(live=False), [item])

        item.add_marker.assert_not_called()


# =============================================================================
# 3. collection.py — priority sorting
# =============================================================================

class TestPrioritySorting:
    """@pytest.mark.priority(N) should sort tests — lower values run first."""

    def test_priority_ordering(self):
        items = [
            make_mock_item("test_low", markers=[pytest.mark.priority(100)]),
            make_mock_item("test_default"),  # default = 500
            make_mock_item("test_high", markers=[pytest.mark.priority(900)]),
            make_mock_item("test_first", markers=[pytest.mark.priority(1)]),
        ]
        filter_and_sort_items(make_mock_config(), items)

        names = [i.name for i in items]
        assert names[0] == "test_first"
        assert names[1] == "test_low"
        assert names.index("test_default") < names.index("test_high")

    def test_default_priority_is_500(self):
        items = [
            make_mock_item("test_no_prio"),
            make_mock_item("test_below", markers=[pytest.mark.priority(499)]),
            make_mock_item("test_above", markers=[pytest.mark.priority(501)]),
        ]
        filter_and_sort_items(make_mock_config(), items)

        names = [i.name for i in items]
        assert names[0] == "test_below"
        assert names.index("test_no_prio") < names.index("test_above")


# =============================================================================
# 4. collection.py — device grouping
# =============================================================================

class TestDeviceGrouping:
    """Tests should be grouped by (module, device_serial) so hub recycling is minimized."""

    def test_grouped_by_module_and_device(self):
        items = [
            make_mock_item("test_a[D455-111]", module_name="mod_frames", device_serial="111"),
            make_mock_item("test_a[D435-222]", module_name="mod_frames", device_serial="222"),
            make_mock_item("test_b[D455-111]", module_name="mod_frames", device_serial="111"),
            make_mock_item("test_b[D435-222]", module_name="mod_frames", device_serial="222"),
        ]
        filter_and_sort_items(make_mock_config(), items)

        names = [i.name for i in items]
        # All D455 tests should be adjacent, all D435 tests should be adjacent
        d455 = [i for i, n in enumerate(names) if "D455" in n]
        d435 = [i for i, n in enumerate(names) if "D435" in n]
        assert d455 == [0, 1] or d455 == [2, 3]
        assert d435 == [0, 1] or d435 == [2, 3]
        assert set(d455) & set(d435) == set()


# =============================================================================
# 5. device_helpers.py — find_matching_devices
# =============================================================================

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


# =============================================================================
# 6. cli.py — legacy flag translation
# =============================================================================

class TestLegacyCliFlags:
    """-r/--regex should be consumed from sys.argv and translated to -k."""

    def _with_argv(self, argv):
        """Context manager to temporarily replace sys.argv."""
        class _Ctx:
            def __enter__(self_):
                self_.saved = sys.argv.copy()
                sys.argv[:] = argv
                return self_
            def __exit__(self_, *exc):
                sys.argv[:] = self_.saved
        return _Ctx()

    def test_short_flag(self):
        with self._with_argv(['pytest', '-r', 'test_depth', 'file.py']):
            result = _consume_flag_with_arg(['-r', '--regex'], '-k')
            assert result == 'test_depth'
            assert '-r' not in sys.argv and '-k' in sys.argv

    def test_long_flag(self):
        with self._with_argv(['pytest', '--regex', 'test_depth', 'file.py']):
            result = _consume_flag_with_arg(['-r', '--regex'], '-k')
            assert result == 'test_depth'
            assert '--regex' not in sys.argv and '-k' in sys.argv

    def test_no_flag_present(self):
        with self._with_argv(['pytest', 'file.py']):
            assert _consume_flag_with_arg(['-r', '--regex'], '-k') is None
            assert sys.argv == ['pytest', 'file.py']

    def test_apply_pending_flags(self):
        with self._with_argv(['pytest', '-k', 'test_depth']):
            config = MagicMock()
            config.option.keyword = ""
            apply_pending_flags(config)
            assert config.option.keyword == 'test_depth'

    def test_apply_pending_flags_no_override(self):
        """Should NOT override an existing -k value."""
        with self._with_argv(['pytest', '-k', 'test_depth']):
            config = MagicMock()
            config.option.keyword = "already_set"
            apply_pending_flags(config)
            assert config.option.keyword == "already_set"


# =============================================================================
# 7. logging_setup.py — log file naming
# =============================================================================

class TestLogNaming:
    """test_log_name() and _log_key() derive per-test log filenames."""

    def _item(self, fspath, name):
        item = MagicMock()
        item.fspath = fspath
        item.name = name
        return item

    def test_with_device_param(self):
        item = self._item("live/frames/pytest-depth.py", "test_x[D455-104623060005]")
        assert derive_log_name(item) == "pytest-depth_D455-104623060005.log"

    def test_without_device_param(self):
        item = self._item("live/frames/pytest-depth.py", "test_depth_basic")
        assert derive_log_name(item) == "pytest-depth.log"

    def test_special_chars_sanitized(self):
        item = self._item("live/frames/pytest-depth.py", "test_x[D455<special>]")
        name = derive_log_name(item)
        assert "<" not in name and ">" not in name and name.endswith(".log")

    def test_log_key_with_brackets(self):
        item = self._item("live/frames/pytest-depth.py", "test_x[D455-111]")
        assert _log_key(item) == ("live/frames/pytest-depth.py", "D455-111")

    def test_log_key_without_brackets(self):
        item = self._item("live/frames/pytest-depth.py", "test_x")
        assert _log_key(item) == ("live/frames/pytest-depth.py", None)

    def test_log_key_none(self):
        assert _log_key(None) is None


# =============================================================================
# 8. End-to-end integration tests (pytester subprocess)
#
# These tests spawn a real pytest subprocess. The subprocess conftest mocks
# only hardware (rspy.devices + pyrealsense2), then exec()s the REAL
# unit-tests/conftest.py. So all hooks, fixtures, and logic come from
# production code — if someone changes conftest.py, these tests break.
# =============================================================================

_MOCK_CONFTEST = r'''
"""
Pytester conftest: mock ONLY the hardware layer, then exec() the REAL conftest.py.
If someone changes conftest.py, these tests exercise the real change.
"""
import sys, os, types

# --- Paths ---
_py_dir = r"{py_dir}"
if _py_dir not in sys.path:
    sys.path.insert(0, _py_dir)

# --- Fake pyrealsense2 (just enough for the real conftest to load) ---
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

# --- Mock rspy.devices (before the real conftest imports it) ---
class FakeDevice:
    def __init__(self, sn, name):
        self.sn = sn
        self.name = name

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
        pl = pattern[:-1]
        for name, (sn, p) in _inventory.items():
            if p == pl:
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

# --- exec() the REAL conftest.py (all hooks and fixtures come from there) ---
_conftest_path = r"{conftest_path}"
with open(_conftest_path) as _f:
    _src = _f.read()

_real_unit_tests_dir = os.path.dirname(_conftest_path)
current_dir = _real_unit_tests_dir
py_dir = os.path.join(_real_unit_tests_dir, "py")
if py_dir not in sys.path:
    sys.path.insert(0, py_dir)

exec(compile(_src, _conftest_path, "exec"), globals())
'''

# Disable installed plugins that interfere with pytester subprocess
_NO_PLUGINS = ["-p", "no:retry", "-p", "no:timeout", "-p", "no:repeat"]


@pytest.fixture
def pytester_with_infra(pytester):
    """Pytest subprocess that mocks only hardware, then exec()s the real conftest.py."""
    py_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'py'))
    conftest_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'conftest.py'))
    pytester.makeconftest(_MOCK_CONFTEST.format(
        py_dir=py_dir.replace('\\', '\\\\'),
        conftest_path=conftest_path.replace('\\', '\\\\'),
    ))

    # Always run as subprocess with plugin isolation
    _original = pytester.runpytest_subprocess
    pytester.runpytest = lambda *args, **kw: _original(*_NO_PLUGINS, *args, **kw)
    return pytester


# --- Marker registration ---

class TestMarkerRegistration:
    """All custom markers should be registered (no PytestUnknownMarkWarning)."""

    def test_all_markers(self, pytester_with_infra):
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

    def test_device_marker(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-devmark": """
            import pytest
            pytestmark = [pytest.mark.device("D455")]
            def test_with_device():
                pass
        """})
        result = pytester_with_infra.runpytest("-W", "error::pytest.PytestUnknownMarkWarning")
        result.assert_outcomes(passed=1)


# --- Context gating E2E ---

class TestContextGatingE2E:
    """End-to-end: @context('nightly') tests should skip/run based on --context."""

    def test_nightly_skipped_by_default(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-ctx": """
            import pytest
            pytestmark = [pytest.mark.context("nightly")]
            def test_nightly_only():
                pass
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(skipped=1)

    def test_nightly_runs_with_context(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-ctx": """
            import pytest
            pytestmark = [pytest.mark.context("nightly")]
            def test_nightly_only():
                pass
        """})
        result = pytester_with_infra.runpytest("--context", "nightly", "-v")
        result.assert_outcomes(passed=1)

    def test_mixed_context_and_normal(self, pytester_with_infra):
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


# --- --live filtering E2E ---

class TestLiveFilteringE2E:
    """End-to-end: --live should skip non-device tests."""

    def test_skips_non_device(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-nolive": """
            def test_no_device():
                pass
        """})
        result = pytester_with_infra.runpytest("--live", "-v")
        result.assert_outcomes(skipped=1)

    def test_keeps_device_each(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-withlive": """
            import pytest
            pytestmark = [pytest.mark.device_each("D455")]
            def test_with_device(_test_device_serial):
                pass
        """})
        result = pytester_with_infra.runpytest("--live", "-v")
        result.assert_outcomes(passed=1)

    def test_mixed(self, pytester_with_infra):
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


# --- device_each parametrization E2E ---

class TestDeviceEachParametrization:
    """End-to-end: @device_each should create one test instance per matching device."""

    def test_creates_per_device_instances(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-each": """
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]
            def test_per_device(_test_device_serial):
                assert _test_device_serial in ('111', '222', '777')
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(passed=3)  # D455, D435, D401

    def test_with_exclude_marker(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-exclude": """
            import pytest
            pytestmark = [
                pytest.mark.device_each("D400*"),
                pytest.mark.device_exclude("D401"),
            ]
            def test_per_device(_test_device_serial):
                assert _test_device_serial != '777'
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(passed=2)  # D455, D435

    def test_cli_device_filter(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-clifilt": """
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]
            def test_per_device(_test_device_serial):
                assert _test_device_serial == '111'
        """})
        result = pytester_with_infra.runpytest("--device", "D455", "-v")
        result.assert_outcomes(passed=1)

    def test_cli_exclude_device(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-cliexcl": """
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]
            def test_per_device(_test_device_serial):
                assert _test_device_serial != '111'
        """})
        result = pytester_with_infra.runpytest("--exclude-device", "D455", "-v")
        result.assert_outcomes(passed=2)  # D435, D401

    def test_no_match_runs_unparametrized(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-nomatch": """
            import pytest
            pytestmark = [pytest.mark.device_each("D999")]
            def test_per_device():
                pass
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_multiple_markers_union(self, pytester_with_infra):
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

    def test_ids_contain_device_name(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-ids": """
            import pytest
            pytestmark = [pytest.mark.device_each("D455")]
            def test_check(_test_device_serial):
                pass
        """})
        result = pytester_with_infra.runpytest("-v")
        result.stdout.fnmatch_lines(["*D455-111*"])


# --- device/device_each skip vs fail behavior ---

class TestDeviceSkipFailBehavior:
    """@device with no match should FAIL. @device_each with no match should SKIP.
    When candidates exist but are all excluded, both should SKIP."""

    def test_device_fails_when_no_match(self, pytester_with_infra):
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
        """device_each skips gracefully — e.g. D585S test on a machine with no D585S."""
        pytester_with_infra.makepyfile(**{"pytest-devskip": """
            import pytest
            pytestmark = [pytest.mark.device_each("D999")]
            def test_needs_device(module_device_setup):
                pass
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(skipped=1)

    def test_device_skips_when_all_excluded(self, pytester_with_infra):
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
        pytester_with_infra.makepyfile(**{"pytest-eachexcl": """
            import pytest
            pytestmark = [pytest.mark.device_each("D455")]
            def test_needs_device(module_device_setup):
                pass
        """})
        result = pytester_with_infra.runpytest("--exclude-device", "D455", "-v")
        result.assert_outcomes(skipped=1)

    def test_device_passes_when_match_exists(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-devpass": """
            import pytest
            pytestmark = [pytest.mark.device("D455")]
            def test_needs_device(module_device_setup):
                assert module_device_setup == '111'
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(passed=1)

    def test_no_markers_yields_none(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-nodev": """
            def test_no_device(module_device_setup):
                assert module_device_setup is None
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(passed=1)


# --- Priority ordering E2E ---

class TestPriorityOrderingE2E:
    """End-to-end: tests should execute in priority order."""

    def test_priority_order(self, pytester_with_infra):
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
                assert execution_order == ['first', 'middle']
        """})
        result = pytester_with_infra.runpytest("-v")
        result.assert_outcomes(passed=4)


# --- CLI options registration E2E ---

class TestCliOptionsRegistered:
    """All custom CLI options should be accepted without error."""

    def _run_with_flag(self, pytester_with_infra, *flags):
        pytester_with_infra.makepyfile(**{"pytest-opt": "def test_pass(): pass"})
        return pytester_with_infra.runpytest(*flags)

    def test_device(self, pytester_with_infra):
        assert self._run_with_flag(pytester_with_infra, "--device", "D455").ret == 0

    def test_exclude_device(self, pytester_with_infra):
        assert self._run_with_flag(pytester_with_infra, "--exclude-device", "D455").ret == 0

    def test_context(self, pytester_with_infra):
        assert self._run_with_flag(pytester_with_infra, "--context", "nightly").ret == 0

    def test_live(self, pytester_with_infra):
        result = self._run_with_flag(pytester_with_infra, "--live")
        result.assert_outcomes(skipped=1)  # test_pass has no device marker

    def test_no_reset(self, pytester_with_infra):
        assert self._run_with_flag(pytester_with_infra, "--no-reset").ret == 0

    def test_hub_reset(self, pytester_with_infra):
        assert self._run_with_flag(pytester_with_infra, "--hub-reset").ret == 0

    def test_rslog(self, pytester_with_infra):
        assert self._run_with_flag(pytester_with_infra, "--rslog").ret == 0

    def test_rs_help(self, pytester_with_infra):
        assert self._run_with_flag(pytester_with_infra, "--rs-help").ret == 0

    def test_multiple_device_flags(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-opt": """
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]
            def test_multi(_test_device_serial):
                assert _test_device_serial in ('111', '222')
        """})
        result = pytester_with_infra.runpytest("--device", "D455", "--device", "D435", "-v")
        result.assert_outcomes(passed=2)

    def test_multiple_exclude_device_flags(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-opt": """
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]
            def test_multi(_test_device_serial):
                assert _test_device_serial == '777'
        """})
        result = pytester_with_infra.runpytest(
            "--exclude-device", "D455", "--exclude-device", "D435", "-v")
        result.assert_outcomes(passed=1)  # only D401 remains

    def test_device_and_exclude_combined(self, pytester_with_infra):
        pytester_with_infra.makepyfile(**{"pytest-opt": """
            import pytest
            pytestmark = [pytest.mark.device_each("D400*")]
            def test_filtered(_test_device_serial):
                assert _test_device_serial == '111'
        """})
        result = pytester_with_infra.runpytest(
            "--device", "D455", "--device", "D435",
            "--exclude-device", "D435", "-v")
        result.assert_outcomes(passed=1)
