import pytest

@pytest.mark.device_each("D400*")
def test_d400(_test_device_serial):
    assert _test_device_serial in ('111', '222', '777')

@pytest.mark.device_each("D400*")
@pytest.mark.device_exclude("D401")
def test_d400_exclude(_test_device_serial):
    assert _test_device_serial != '777'

@pytest.mark.device_each("D999")
def test_d999_no_match():
    pass

@pytest.mark.device_each("D455")
@pytest.mark.device_each("D515")
def test_multi(_test_device_serial):
    assert _test_device_serial in ('111', '555')

@pytest.mark.device_each("D455")
def test_ids(_test_device_serial):
    pass
