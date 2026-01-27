# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
Demo test to show pytest formatting
"""

import pytest

def test_first_example():
    """First test example"""
    assert 1 + 1 == 2

def test_second_example():
    """Second test example"""
    result = "hello" + " world"
    assert result == "hello world"

def test_third_example():
    """Third test example"""
    assert [1, 2, 3] == [1, 2, 3]
