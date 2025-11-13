# LibCI to Pytest Migration Guide

## Overview

This guide covers the migration from the proprietary LibCI unit test infrastructure to pytest. The migration maintains device hub control for power cycling while leveraging pytest's mature testing framework.

**Key Benefits:**
- Standard pytest interface and ecosystem
- Better IDE support and debugging
- Parallel test execution support
- Rich plugin ecosystem
- Maintains all device hub functionality

## Quick Start

### Running Tests

```bash
# Make sure you're using the correct Python version
py -3.13 -m pytest --collect-only -v  # Check what tests are found

# Run all migrated tests (pytest-*.py files)
py -3.13 -m pytest -v

# Run specific test file
py -3.13 -m pytest live/frames/pytest-t2ff-pipeline.py -s -v

# Run with debug logging
py -3.13 -m pytest -s -v --log-cli-level=DEBUG

# Filter by marker
py -3.13 -m pytest -m device_each

# Filter by test name pattern
py -3.13 -m pytest -k "depth"
```

### Validation

Run the validation script to check your setup:

```bash
cd unit-tests
py -3.13 validate-pytest-migration.py
```

## File Naming Convention

**IMPORTANT**: We use a clear naming convention to separate migrated and legacy tests:

- **`pytest-*.py`** - Migrated pytest tests (discovered by pytest)
- **`test-*.py`** - Legacy LibCI tests (ignored by pytest)

This allows gradual migration without interference between old and new infrastructure.

## Special Directives

### Timeout Configuration

**LibCI:**
```python
#test:timeout 1500
```

**Pytest:**
```python
pytestmark = pytest.mark.timeout(1500)  # seconds
```

Or for individual tests:
```python
@pytest.mark.timeout(300)
def test_something():
    ...
```

**Configuration:**
- Default timeout: 200 seconds (set in pytest.ini)
- Requires: `pip install pytest-timeout`
- Method: thread-based (for Windows compatibility)

### Nightly Tests (donotrun)

**LibCI:**
```python
#test:donotrun:!nightly
```
Means: Skip this test UNLESS running in nightly context.

**Pytest:**
```python
pytestmark = pytest.mark.nightly
```

**Behavior:**
- By default: Nightly tests are **skipped** automatically
- To run only nightly tests: `pytest -m nightly`
- To run all tests including nightly: `pytest -m "nightly or not nightly"`
- To exclude nightly: Default behavior (no `-m` flag needed)

This is implemented in `conftest.py` via `pytest_collection_modifyitems` hook.

## Migration Steps

### Step 1: Convert Test Structure

**Before (LibCI):**
```python
from rspy import test, log
import pyrealsense2 as rs

#test:device D400*
#test:device each(D500*)

dev, ctx = test.find_first_device_or_exit()

test.start("Test name")
# ... test code ...
test.check(some_condition)
test.finish()

test.print_results_and_exit()
```

**After (Pytest):**
```python
import pytest
from rspy import log
import pyrealsense2 as rs

# Mark this module to run on D400 and D500 devices
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.live
]

def test_name(test_device):
    dev, ctx = test_device
    # ... test code ...
    assert some_condition
```

### Step 2: Convert Test Functions

| LibCI | Pytest |
|-------|--------|
| `test.start("Name")` | `def test_name():` (function name becomes test name) |
| `test.check(condition)` | `assert condition` |
| `test.check_equal(a, b)` | `assert a == b` |
| `log.f("Skip reason")` | `pytest.skip("Skip reason")` |
| `test.finish()` | (automatic - no need) |
| `test.print_results_and_exit()` | (automatic - no need) |

### Step 3: Convert Device Markers

**Option 1: Module-level markers (recommended)**
```python
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.live
]
```

**Option 2: Function-level markers**
```python
@pytest.mark.device_each("D400*")
@pytest.mark.live
def test_something(test_device):
    ...
```

### Step 4: Rename File

After conversion, rename from `test-*.py` to `pytest-*.py`:

```bash
mv test-my-test.py pytest-my-test.py
```

## Available Fixtures

### `test_device`
Provides the first available device and context:

```python
def test_something(test_device):
    dev, ctx = test_device
    product_line = dev.get_info(rs.camera_info.product_line)
    assert product_line == "D400"
```

### `module_test_device`
Module-scoped version of `test_device` (shared across all tests in module):

```python
@pytest.fixture(scope="module")
def device_config(module_test_device):
    dev, ctx = module_test_device
    # expensive setup here
    return {'dev': dev, 'ctx': ctx, 'data': ...}

def test_one(device_config):
    # uses cached device_config
    ...

def test_two(device_config):
    # reuses same device_config
    ...
```

### `test_context`
Provides just the RealSense context:

```python
def test_something(test_context):
    ctx = test_context
    devices = ctx.query_devices()
    assert len(devices) > 0
```

## Device Markers

### `device(pattern)`
Test runs once with any device matching the pattern:

```python
pytestmark = pytest.mark.device("D455")  # Runs on first D455 found

def test_something(test_device):
    ...
```

### `device_each(pattern)`
Test runs separately for each matching device:

```python
pytestmark = [
    pytest.mark.device_each("D400*"),  # Runs on all D400 series devices
    pytest.mark.device_each("D500*")   # Runs on all D500 series devices
]

def test_something(test_device):
    ...  # This test will run multiple times, once per device
```

### Pattern Matching

Patterns support wildcards:
- `D400*` - Matches D415, D435, D455, etc.
- `D455` - Exact match only
- `D500*` - Matches D555, etc.

The pattern matches against both `product_line` and device `name`.

## Device Hub Integration

The pytest infrastructure fully maintains device hub control:

### Session Level
- Initializes device enumeration at session start
- Queries all connected devices
- Cleans up and disconnects hub at session end

### Module Level
- Parses device markers to determine requirements
- Enables only required device ports via `devices.enable_only()`
- **Power cycles devices between modules** (`recycle=True`)
- Ensures tests only see their target devices

### Test Level
- Provides filtered context showing only target devices
- No changes needed - hub state managed automatically

## Common Patterns

### Conditional Test Execution

**Skip if device doesn't support feature:**
```python
def test_color_sensor(test_device):
    dev, ctx = test_device
    product_name = dev.get_info(rs.camera_info.name)
    
    if product_name in ['D421', 'D405', 'D430']:
        pytest.skip(f"Device {product_name} has no color sensor")
    
    # test color sensor...
```

**Parametrize tests:**
```python
@pytest.mark.parametrize("width,height,fps", [
    (640, 480, 30),
    (1280, 720, 30),
    (1920, 1080, 30),
])
def test_resolution(test_device, width, height, fps):
    dev, ctx = test_device
    # test with different resolutions...
```

### Module-Scoped Setup

For expensive setup that should be shared across tests:

```python
@pytest.fixture(scope="module")
def device_config(module_test_device):
    """Set up device configuration once for all tests in module."""
    dev, ctx = module_test_device
    
    # Expensive initialization
    product_line = dev.get_info(rs.camera_info.product_line)
    
    # Wait for device to stabilize
    time.sleep(3)
    
    return {
        'dev': dev,
        'ctx': ctx,
        'product_line': product_line,
        'max_delay': 1.0
    }

def test_one(device_config):
    # Uses cached device_config
    assert device_config['product_line'] == "D400"

def test_two(device_config):
    # Reuses same device_config (no re-initialization)
    dev = device_config['dev']
    ...
```

## Testing Your Migration

### 1. Check Test Discovery
```bash
py -3.13 -m pytest --collect-only -v
```

Should show your migrated tests (pytest-*.py files only).

### 2. Verify Device Matching

With device connected:
```bash
py -3.13 -m pytest -v
```

Without device:
```bash
py -3.13 -m pytest -v
```

Should show tests SKIPPED with message: "No devices found matching requirements"

### 3. Run Validation Script
```bash
py -3.13 validate-pytest-migration.py
```

Checks:
- Python version matches pyrealsense2 build
- All required imports available
- Configuration files valid
- Devices detected
- Fixtures work correctly

## Troubleshooting

### "No module named 'pyrealsense2'"

**Cause**: Python version mismatch. The pyrealsense2.pyd is built for a specific Python version.

**Solution**:
```bash
# Check your .pyd file version (e.g., cp313 = Python 3.13)
# Then use that version explicitly:
py -3.13 -m pytest
```

### "No devices found matching requirements"

**Cause**: No connected devices match your test markers.

**Solution**:
- Check device is connected: `devices.query()` in Python
- Verify device matches pattern (D455 matches D400*, not D500*)
- Connect appropriate device for your test

### Tests collected but not running

**Cause**: Tests still named `test-*.py` instead of `pytest-*.py`.

**Solution**: Rename files after migration:
```bash
mv test-my-test.py pytest-my-test.py
```

## Migration Checklist

When migrating a test file:

- [ ] Remove LibCI imports (`from rspy import test`)
- [ ] Convert `test.start()/finish()` to pytest functions
- [ ] Replace `test.check()` with `assert`
- [ ] Convert device comments to `pytestmark` markers
- [ ] Add fixtures (`test_device`, `test_context`)
- [ ] Replace `log.f()` with `pytest.skip()`
- [ ] Test the conversion: `py -3.13 -m pytest path/to/pytest-file.py -v`
- [ ] Rename from `test-*.py` to `pytest-*.py`
- [ ] Verify in full test run: `py -3.13 -m pytest --collect-only`

## Files in This Migration

### Core Infrastructure
- **`conftest.py`** - Pytest fixtures, hooks, and device management
- **`pytest.ini`** - Pytest configuration
- **`validate-pytest-migration.py`** - Validation script

### Documentation  
- **`PYTEST_MIGRATION_GUIDE.md`** - This file

### Example Test
- **`live/frames/pytest-t2ff-pipeline.py`** - Migrated test example

## Next Steps

1. **Validate setup**: Run `py -3.13 validate-pytest-migration.py`
2. **Test the example**: Run `py -3.13 -m pytest live/frames/pytest-t2ff-pipeline.py -v`
3. **Migrate more tests**: Follow the migration steps above
4. **Update CI/CD**: Update build pipelines to use pytest commands

## Command Reference

| Task | Command |
|------|---------|
| List all tests | `py -3.13 -m pytest --collect-only` |
| Run all migrated tests | `py -3.13 -m pytest` |
| Run with output | `py -3.13 -m pytest -s -v` |
| Run specific file | `py -3.13 -m pytest path/to/pytest-file.py` |
| Run by marker | `py -3.13 -m pytest -m device_each` |
| Run by pattern | `py -3.13 -m pytest -k "depth"` |
| Debug mode | `py -3.13 -m pytest -s -v --log-cli-level=DEBUG` |
| Run only nightly tests | `py -3.13 -m pytest -m nightly` |
| Run all including nightly | `py -3.13 -m pytest -m "nightly or not nightly"` |
| Override timeout | `py -3.13 -m pytest --timeout=300` |
| Disable timeout | `py -3.13 -m pytest --timeout=0` |
| Validate setup | `py -3.13 validate-pytest-migration.py` |
