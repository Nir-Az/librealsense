#!/usr/bin/env python3
# License: Apache 2.0. See LICENSE file in root directory.
# Copyright(c) 2025 RealSense, Inc. All Rights Reserved.

"""
Validation script for pytest migration.

This script performs basic checks to ensure the pytest infrastructure is set up correctly.
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
    
    # Check Python version
    import sys
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"  Python version: {python_version}")
    
    # Check pytest
    try:
        import pytest
        print(f"  ✓ pytest {pytest.__version__}")
    except ImportError as e:
        errors.append(f"  ✗ pytest not found: {e}")
    
    # Check rspy modules
    try:
        from rspy import log
        print("  ✓ rspy.log")
    except ImportError as e:
        errors.append(f"  ✗ rspy.log: {e}")
    
    try:
        from rspy import devices
        print("  ✓ rspy.devices")
    except ImportError as e:
        errors.append(f"  ✗ rspy.devices: {e}")
    
    try:
        from rspy import repo
        print("  ✓ rspy.repo")
        
        # Check if pyrealsense2 .pyd/.so file exists
        pyrs_dir = repo.find_pyrs_dir()
        if pyrs_dir:
            print(f"  ✓ Found pyrealsense2 directory: {pyrs_dir}")
            # Check for version mismatch
            pyrs_files = [f for f in os.listdir(pyrs_dir) if f.startswith('pyrealsense2') and (f.endswith('.pyd') or f.endswith('.so'))]
            if pyrs_files:
                pyrs_file = pyrs_files[0]
                print(f"    Found: {pyrs_file}")
                # Check for Python version in filename (e.g., cp313, cp314)
                import re
                match = re.search(r'cp(\d)(\d+)', pyrs_file)
                if match:
                    built_major = int(match.group(1))
                    built_minor = int(match.group(2))
                    if sys.version_info.major != built_major or sys.version_info.minor != built_minor:
                        print(f"  ⚠ WARNING: pyrealsense2 was built for Python {built_major}.{built_minor} but you're running Python {sys.version_info.major}.{sys.version_info.minor}")
                        print(f"    You need to either:")
                        print(f"      - Use Python {built_major}.{built_minor}, OR")
                        print(f"      - Rebuild pyrealsense2 with Python {sys.version_info.major}.{sys.version_info.minor}")
    except ImportError as e:
        errors.append(f"  ✗ rspy.repo: {e}")
    
    # Check pyrealsense2
    try:
        import pyrealsense2 as rs
        print(f"  ✓ pyrealsense2")
        print(f"    Version: {rs.__version__ if hasattr(rs, '__version__') else 'unknown'}")
    except ImportError as e:
        print(f"  ⚠ pyrealsense2 not found (tests will be skipped): {e}")
    
    return errors


def check_conftest():
    """Check that conftest.py exists and is valid."""
    print("\nChecking conftest.py...")
    
    conftest_path = os.path.join(current_dir, 'conftest.py')
    if not os.path.exists(conftest_path):
        return [f"  ✗ conftest.py not found at {conftest_path}"]
    
    print(f"  ✓ conftest.py exists")
    
    # Try to import it
    try:
        import conftest
        print("  ✓ conftest.py imports successfully")
        
        # Check for key fixtures
        fixtures = ['session_setup_teardown', 'module_device_setup', 'test_context', 'test_device']
        for fixture_name in fixtures:
            if hasattr(conftest, fixture_name):
                print(f"  ✓ fixture '{fixture_name}' found")
            else:
                print(f"  ⚠ fixture '{fixture_name}' not found (may be decorated)")
        
    except Exception as e:
        return [f"  ✗ Error importing conftest.py: {e}"]
    
    return []


def check_pytest_ini():
    """Check that pytest.ini exists and is valid."""
    print("\nChecking pytest.ini...")
    
    pytest_ini = os.path.join(current_dir, 'pytest.ini')
    if not os.path.exists(pytest_ini):
        return [f"  ✗ pytest.ini not found at {pytest_ini}"]
    
    print("  ✓ pytest.ini exists")
    
    # Read and check contents
    try:
        with open(pytest_ini, 'r') as f:
            content = f.read()
            
        required_sections = ['markers', 'testpaths', 'python_files']
        for section in required_sections:
            if section in content:
                print(f"  ✓ '{section}' configured")
            else:
                print(f"  ⚠ '{section}' not found in pytest.ini")
                
    except Exception as e:
        return [f"  ✗ Error reading pytest.ini: {e}"]
    
    return []


def check_test_file():
    """Check that the migrated test file exists."""
    print("\nChecking migrated test file...")
    
    test_file = os.path.join(current_dir, 'live', 'frames', 'test-t2ff-pipeline.py')
    if not os.path.exists(test_file):
        return [f"  ✗ test-t2ff-pipeline.py not found at {test_file}"]
    
    print("  ✓ test-t2ff-pipeline.py exists")
    
    # Check for pytest-style functions
    try:
        with open(test_file, 'r') as f:
            content = f.read()
            
        if 'def test_' in content:
            print("  ✓ Contains pytest test functions")
        else:
            return ["  ✗ No pytest test functions found (should have 'def test_...')"]
        
        if '#test:device' in content or '# test:device' in content:
            print("  ✓ Contains device markers")
        else:
            print("  ⚠ No device markers found")
        
        if 'import pytest' in content:
            print("  ✓ Imports pytest")
        else:
            print("  ⚠ Does not import pytest")
            
    except Exception as e:
        return [f"  ✗ Error reading test file: {e}"]
    
    return []


def check_devices():
    """Check if devices can be queried."""
    print("\nChecking device detection...")
    
    try:
        from rspy import devices
        import pyrealsense2 as rs
        
        devices.query()
        all_device_sns = devices.all()
        
        print(f"  ✓ Found {len(all_device_sns)} device(s)")
        
        for sn in all_device_sns:
            dev = devices.get(sn)
            print(f"    - {dev.name} (SN: {sn})")
        
        if len(all_device_sns) == 0:
            print("  ⚠ No devices connected (tests will be skipped)")
        
        # Check hub
        if devices.hub:
            print(f"  ✓ Device hub detected: {type(devices.hub).__name__}")
        else:
            print("  ⚠ No device hub detected (power cycling will not work)")
        
    except ImportError:
        print("  ⚠ pyrealsense2 not available, skipping device check")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return [f"  ✗ Error querying devices: {e}"]
    
    return []


def main():
    """Run all validation checks."""
    print("=" * 70)
    print("Pytest Migration Validation")
    print("=" * 70)
    
    all_errors = []
    
    all_errors.extend(check_imports())
    all_errors.extend(check_conftest())
    all_errors.extend(check_pytest_ini())
    all_errors.extend(check_test_file())
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
        print("  pytest live/frames/test-t2ff-pipeline.py -s -v")
        return 0


if __name__ == '__main__':
    sys.exit(main())
