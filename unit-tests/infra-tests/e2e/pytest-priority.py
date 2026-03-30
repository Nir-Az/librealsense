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
