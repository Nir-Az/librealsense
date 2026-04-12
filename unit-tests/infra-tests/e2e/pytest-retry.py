# Test that fails on first attempt, passes on retry.
# Used to verify --retries triggers device recycle on retry.
import pytest

pytestmark = [pytest.mark.device("D455")]

_attempt = 0

def test_fails_then_passes(module_device_setup):
    """Fail on first run, pass on retry."""
    global _attempt
    _attempt += 1
    if _attempt == 1:
        assert False, "intentional first-run failure"
