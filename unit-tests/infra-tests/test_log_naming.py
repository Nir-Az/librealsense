# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""Tests for rspy/pytest/logging_setup.py — per-test log file naming."""

from unittest.mock import MagicMock
from rspy.pytest.logging_setup import test_log_name as derive_log_name, _log_key


class TestLogNaming:
    """derive_log_name() and _log_key() derive per-test log filenames."""

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
