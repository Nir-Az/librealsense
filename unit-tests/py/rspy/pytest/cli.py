# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""Legacy CLI flag translation — intercept flags that clash with pytest built-ins."""

import sys


def _find_flag(flag):
    """Find a flag in sys.argv, returning its index or None."""
    try:
        return sys.argv.index(flag)
    except ValueError:
        return None


def _consume_flag_with_arg(flags, pytest_equiv):
    """Consume a flag+argument from sys.argv, translate to pytest equivalent."""
    for flag in flags:
        idx = _find_flag(flag)
        if idx is not None:
            if idx + 1 >= len(sys.argv):
                print(f'-F- {flag} requires an argument', file=sys.stderr)
                sys.exit(1)
            value = sys.argv[idx + 1]
            del sys.argv[idx:idx + 2]
            sys.argv.extend([pytest_equiv, value])
            return value
    return None


def consume_legacy_flags():
    """Translate legacy run-unit-tests.py flags to pytest equivalents.

    Call this before pytest parses sys.argv.
    """
    _consume_flag_with_arg(['-r', '--regex'], '-k')  # -r/--regex -> pytest's -k (keyword filter)
