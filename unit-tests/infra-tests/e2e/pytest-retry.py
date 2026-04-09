# Test that fails on first attempt, passes on retry.
# Used to verify --retries triggers device recycle on retry.
import os
import pytest

pytestmark = [pytest.mark.device("D455")]

_counter_file = os.path.join(os.path.dirname(__file__), '_retry_counter')

def test_fails_then_passes(module_device_setup):
    """Fail on first run, pass on retry."""
    if os.path.exists(_counter_file):
        os.remove(_counter_file)
        return  # second run: pass
    with open(_counter_file, 'w') as f:
        f.write('1')
    assert False, "intentional first-run failure"
