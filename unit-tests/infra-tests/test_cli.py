# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
Tests for rspy/pytest/cli.py (consume_legacy_flags, apply_pending_flags).

Verifies translation of legacy run-unit-tests.py flags to pytest equivalents:
- -r/--regex pattern → -k pattern (keyword filter)
- --tag name → -m name (marker filter)
- apply_pending_flags applies the translated -k / -m to pytest config
- Existing -k / -m values are not overridden
"""

import sys
from unittest.mock import MagicMock
from rspy.pytest.cli import _consume_flag_with_arg, apply_pending_flags


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

    def test_tag_flag(self):
        """--tag <name> should be consumed and translated to -m <name>."""
        with self._with_argv(['pytest', '--tag', 'dds', 'file.py']):
            result = _consume_flag_with_arg(['--tag'], '-m')
            assert result == 'dds'
            assert '--tag' not in sys.argv and '-m' in sys.argv
            assert sys.argv[sys.argv.index('-m') + 1] == 'dds'

    def test_apply_pending_flags_marker(self):
        """apply_pending_flags should set markexpr from injected -m."""
        with self._with_argv(['pytest', '-m', 'dds']):
            config = MagicMock()
            config.option.keyword = ""
            config.option.markexpr = ""
            apply_pending_flags(config)
            assert config.option.markexpr == 'dds'

    def test_apply_pending_flags_marker_no_override(self):
        """Should NOT override an existing -m value."""
        with self._with_argv(['pytest', '-m', 'dds']):
            config = MagicMock()
            config.option.keyword = ""
            config.option.markexpr = "already_set"
            apply_pending_flags(config)
            assert config.option.markexpr == "already_set"
