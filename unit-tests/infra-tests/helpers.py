# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""Shared helpers for infra regression tests — fake devices, mock builders, E2E runner."""

import sys
import os
import re
import types
import subprocess
import tempfile
import textwrap
import json
from unittest.mock import MagicMock
import pytest


# =============================================================================
# Fake device inventory
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
# The E2E conftest uses a subset (D455, D435, D515, D401) — enough to
# test wildcards, excludes, and multi-device parametrization without noise.

DEVICES = {
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
# Mock builders for unit tests
# =============================================================================

def make_mock_item(name="test_example", markers=None, module_name="fake_module",
                   device_serial=None):
    """Build a fake pytest Item for unit-testing collection/filter logic.

    Uses SimpleNamespace so that `hasattr(item, 'callspec')` is genuinely False
    when no device_serial is set (MagicMock auto-creates attributes on access).
    """
    marks = list(markers or [])

    item = types.SimpleNamespace()
    item.name = name
    item.module = types.ModuleType(module_name)
    item.add_marker = MagicMock()

    if device_serial:
        item.callspec = types.SimpleNamespace(
            params={'_test_device_serial': device_serial}
        )

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
# E2E subprocess runner
# =============================================================================

_PY_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'py'))
_REAL_CONFTEST = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'conftest.py'))


def run_e2e(test_file_content, *extra_pytest_args):
    """Run a pytest subprocess in a temp dir with mocked hardware and the real conftest.

    Returns (returncode, stdout, enable_only_calls).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        conftest_src = textwrap.dedent(f'''\
            import sys, os, types

            _py_dir = r"{_PY_DIR}"
            if _py_dir not in sys.path:
                sys.path.insert(0, _py_dir)

            # Fake pyrealsense2
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

            # Mock rspy.devices
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
            _dev.wait_until_all_ports_disabled = lambda: None

            # Track enable_only calls so tests can verify hub port behavior
            import json as _json
            _enable_only_log = os.path.join(os.path.dirname(__file__), '_enable_only_calls.json')
            _enable_only_calls = []
            def _mock_enable_only(serials, recycle=True):
                _enable_only_calls.append({{"serials": list(serials), "recycle": recycle}})
                with open(_enable_only_log, 'w') as _f:
                    _json.dump(_enable_only_calls, _f)
            _dev.enable_only = _mock_enable_only

            # exec() the REAL conftest.py
            _conftest_path = r"{_REAL_CONFTEST}"
            with open(_conftest_path) as _f:
                _src = _f.read()
            _real_dir = os.path.dirname(_conftest_path)
            current_dir = _real_dir
            py_dir = os.path.join(_real_dir, "py")
            if py_dir not in sys.path:
                sys.path.insert(0, py_dir)
            exec(compile(_src, _conftest_path, "exec"), globals())
        ''')

        with open(os.path.join(tmpdir, 'conftest.py'), 'w') as f:
            f.write(conftest_src)

        with open(os.path.join(tmpdir, 'pytest-e2e.py'), 'w') as f:
            f.write(textwrap.dedent(test_file_content))

        p = subprocess.run(
            [sys.executable, "-m", "pytest", "pytest-e2e.py", "-v", *extra_pytest_args],
            cwd=tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=30,
        )

        if p.returncode != 0 and 'no tests ran' not in p.stdout and 'passed' not in p.stdout \
                and 'skipped' not in p.stdout and 'error' not in p.stdout:
            pytest.fail(f"Subprocess crashed (rc={p.returncode}):\n{p.stdout}")

        calls_file = os.path.join(tmpdir, '_enable_only_calls.json')
        enable_only_calls = json.loads(open(calls_file).read()) if os.path.exists(calls_file) else []

        return p.returncode, p.stdout, enable_only_calls


def parse_outcomes(stdout):
    """Parse pytest summary line into a dict like {'passed': 3, 'skipped': 1}."""
    matches = re.findall(r'=+ (.+?) =+\s*$', stdout, re.MULTILINE)
    if not matches:
        return {}
    summary = matches[-1]
    outcomes = {}
    for match in re.finditer(r'(\d+) (\w+)', summary):
        outcomes[match.group(2)] = int(match.group(1))
    return outcomes


def assert_outcomes(stdout, **expected):
    """Assert pytest outcomes from subprocess stdout."""
    actual = parse_outcomes(stdout)
    for key, val in expected.items():
        assert actual.get(key, 0) == val, \
            f"Expected {key}={val}, got {actual.get(key, 0)}. Full output:\n{stdout}"
