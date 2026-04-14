import pytest
pytestmark = [
    pytest.mark.device_each("D455"),
    pytest.mark.device_exclude("D401"),
    pytest.mark.context("nightly"),
    pytest.mark.priority(100),
]
def test_example(_test_device_serial):
    pass
