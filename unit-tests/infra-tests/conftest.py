# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
Minimal conftest for infra regression tests.

These tests validate the pytest infrastructure itself (markers, CLI flags, collection
logic, log naming, etc.) — no cameras or pyrealsense2 required.
"""

import sys
import os

# Add unit-tests/py/ to sys.path so we can import rspy.pytest modules directly
_unit_tests_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
_py_dir = os.path.join(_unit_tests_dir, 'py')
if _py_dir not in sys.path:
    sys.path.insert(0, _py_dir)

# Enable pytester fixture for integration tests
pytest_plugins = ["pytester"]
