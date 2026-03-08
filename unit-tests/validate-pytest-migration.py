#!/usr/bin/env python3
# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2026 RealSense, Inc. All Rights Reserved.

"""
Validation script for pytest migration.

Checks Python version, pyrealsense2 import, device detection, and fixture availability.
Run this before attempting to run actual tests.
"""

import sys
import os

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(current_dir, 'py'))


def check_imports():
    """Check that all required modules can be imported."""
    print("Checking imports...")

    errors = []

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"  Python version: {python_version}")

    try:
        import pytest
        print(f"  OK pytest {pytest.__version__}")
    except ImportError as e:
        errors.append(f"  FAIL pytest not found: {e}")

    try:
        from rspy import log
        print("  OK rspy.log")
    except ImportError as e:
        errors.append(f"  FAIL rspy.log: {e}")

    try:
        from rspy import devices
        print("  OK rspy.devices")
    except ImportError as e:
        errors.append(f"  FAIL rspy.devices: {e}")

    try:
        from rspy import repo
        print("  OK rspy.repo")

        pyrs_dir = repo.find_pyrs_dir()
        if pyrs_dir:
            print(f"  OK Found pyrealsense2 directory: {pyrs_dir}")
            import re as re_mod
            pyrs_files = [f for f in os.listdir(pyrs_dir)
                          if f.startswith('pyrealsense2') and (f.endswith('.pyd') or f.endswith('.so'))]
            if pyrs_files:
                pyrs_file = pyrs_files[0]
                print(f"    Found: {pyrs_file}")
                match = re_mod.search(r'cp(\d)(\d+)', pyrs_file)
                if match:
                    built_major = int(match.group(1))
                    built_minor = int(match.group(2))
                    if sys.version_info.major != built_major or sys.version_info.minor != built_minor:
                        print(f"  WARNING: pyrealsense2 built for Python {built_major}.{built_minor} "
                              f"but running Python {sys.version_info.major}.{sys.version_info.minor}")
    except ImportError as e:
        errors.append(f"  FAIL rspy.repo: {e}")

    try:
        import pyrealsense2 as rs
        print("  OK pyrealsense2")
        print(f"    Version: {rs.__version__ if hasattr(rs, '__version__') else 'unknown'}")
    except ImportError as e:
        print(f"  WARNING pyrealsense2 not found (tests will be skipped): {e}")

    return errors


def check_conftest():
    """Check that conftest.py exists and is valid."""
    print("\nChecking conftest.py...")

    conftest_path = os.path.join(current_dir, 'conftest.py')
    if not os.path.exists(conftest_path):
        return [f"  FAIL conftest.py not found at {conftest_path}"]

    print("  OK conftest.py exists")

    try:
        import conftest
        print("  OK conftest.py imports successfully")

        fixtures = ['session_setup_teardown', 'module_device_setup', 'test_context', 'test_device']
        for fixture_name in fixtures:
            if hasattr(conftest, fixture_name):
                print(f"  OK fixture '{fixture_name}' found")
            else:
                print(f"  WARNING fixture '{fixture_name}' not found (may be decorated)")

    except Exception as e:
        return [f"  FAIL Error importing conftest.py: {e}"]

    return []


def check_pytest_config():
    """Check that pytest configuration is set up in conftest.py."""
    print("\nChecking pytest configuration...")

    conftest_path = os.path.join(current_dir, 'conftest.py')
    try:
        with open(conftest_path, 'r') as f:
            content = f.read()

        for setting in ['python_files', 'python_functions', 'timeout']:
            if setting in content:
                print(f"  OK '{setting}' configured in conftest.py")
            else:
                print(f"  WARNING '{setting}' not found in conftest.py")

    except Exception as e:
        return [f"  FAIL Error reading conftest.py: {e}"]

    return []


def check_test_files():
    """Check that migrated test files exist."""
    print("\nChecking migrated test files...")

    errors = []
    test_file = os.path.join(current_dir, 'live', 'frames', 'pytest-t2ff-pipeline.py')
    if not os.path.exists(test_file):
        errors.append(f"  FAIL pytest-t2ff-pipeline.py not found at {test_file}")
    else:
        print("  OK pytest-t2ff-pipeline.py exists")
        with open(test_file, 'r') as f:
            content = f.read()
        if 'def test_' in content:
            print("  OK Contains pytest test functions")
        else:
            errors.append("  FAIL No pytest test functions found")
        if 'import pytest' in content:
            print("  OK Imports pytest")

    return errors


def check_devices():
    """Check if devices can be queried."""
    print("\nChecking device detection...")

    try:
        from rspy import devices
        import pyrealsense2 as rs

        devices.query()
        all_device_sns = devices.all()

        print(f"  OK Found {len(all_device_sns)} device(s)")

        for sn in all_device_sns:
            dev = devices.get(sn)
            print(f"    - {dev.name} (SN: {sn})")

        if len(all_device_sns) == 0:
            print("  WARNING No devices connected (tests will be skipped)")

        if devices.hub:
            print(f"  OK Device hub detected: {type(devices.hub).__name__}")
        else:
            print("  WARNING No device hub detected (power cycling will not work)")

    except ImportError:
        print("  WARNING pyrealsense2 not available, skipping device check")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return [f"  FAIL Error querying devices: {e}"]

    return []


def main():
    """Run all validation checks."""
    print("=" * 70)
    print("Pytest Migration Validation")
    print("=" * 70)

    all_errors = []

    all_errors.extend(check_imports())
    all_errors.extend(check_conftest())
    all_errors.extend(check_pytest_config())
    all_errors.extend(check_test_files())
    all_errors.extend(check_devices())

    print("\n" + "=" * 70)

    if all_errors:
        print("VALIDATION FAILED - Issues found:")
        for error in all_errors:
            print(error)
        print("\nPlease fix these issues before running pytest.")
        return 1
    else:
        print("VALIDATION PASSED - All checks successful!")
        print("\nYou can now run the migrated test:")
        print("  cd unit-tests")
        print("  python -m pytest live/frames/pytest-t2ff-pipeline.py -s -v")
        return 0


if __name__ == '__main__':
    sys.exit(main())
