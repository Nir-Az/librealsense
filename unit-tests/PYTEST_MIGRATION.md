# LibCI to Pytest Migration Guide

## Overview

This document describes the migration from the proprietary LibCI unit test infrastructure to pytest. The migration maintains device hub control for power cycling while leveraging pytest's mature testing framework.

## What Changed

### Infrastructure

**Before (LibCI):**
```bash
py -3 run-unit-tests.py -s --debug -r metadata
```

**After (Pytest):**
```bash
pytest -k metadata -s
```

### Test File Structure

**Before:**
```python
from rspy import test, log
import pyrealsense2 as rs

dev, ctx = test.find_first_device_or_exit()

test.start("Test name")
# ... test code ...
test.check(some_condition)
test.finish()

test.print_results_and_exit()
```

**After:**
```python
import pytest
from rspy import log
import pyrealsense2 as rs

def test_name(test_device):
    dev, ctx = test_device
    # ... test code ...
    assert some_condition
```

### Device Markers

**Before:**
```python
# test:device D400*
# test:device each(D500*)
```

**After:**
The same comments are supported! The pytest infrastructure automatically reads these and converts them to pytest markers. You can also use native pytest markers:

```python
@pytest.mark.device("D400*")
@pytest.mark.device_each("D500*")
def test_something(test_device):
    ...
```

## Key Features

### 1. Device Hub Control

The pytest infrastructure maintains full compatibility with the device hub system:
- **Session-level**: Initializes devices and hub at the start
- **Module-level**: Power cycles devices between test modules
- **Test-level**: Ensures only target devices are visible to tests

### 2. Fixtures

#### `test_device`
Provides the first available device and context (replaces `test.find_first_device_or_exit()`):

```python
def test_something(test_device):
    dev, ctx = test_device
    # use dev and ctx
```

#### `test_context`
Provides just the context:

```python
def test_something(test_context):
    ctx = test_context
    devices = ctx.devices
```

#### `module_device_setup`
Automatically handles device selection based on markers. You typically don't need to use this directly.

### 3. Assertions

**Before:**
```python
test.check(frame_delay < max_delay)
test.check_equal(result, expected)
test.check_throws(lambda: some_function(), ExpectedException)
```

**After:**
```python
assert frame_delay < max_delay
assert result == expected
with pytest.raises(ExpectedException):
    some_function()
```

### 4. Test Selection

**Filter by name pattern:**
```bash
# Before
py -3 run-unit-tests.py -r metadata

# After
pytest -k metadata
```

**Filter by marker:**
```bash
# Before
py -3 run-unit-tests.py -t live

# After
pytest -m live
```

**Specific test file:**
```bash
# Before
py -3 run-unit-tests.py live/frames/test-t2ff-pipeline.py

# After
pytest live/frames/test-t2ff-pipeline.py
```

**Specific test function:**
```bash
pytest live/frames/test-t2ff-pipeline.py::test_pipeline_first_depth_frame_delay
```

### 5. Output Control

**See stdout immediately:**
```bash
# Before
py -3 run-unit-tests.py -s

# After
pytest -s
```

**Verbose output:**
```bash
# Before
py -3 run-unit-tests.py --debug

# After
pytest -v
```

**Quiet mode:**
```bash
# Before
py -3 run-unit-tests.py -q

# After
pytest -q
```

## Migration Checklist for New Tests

When migrating a test file from LibCI to pytest:

1. **Remove old imports:**
   - Remove: `from rspy import test`
   - Keep: `from rspy import log` (still useful)

2. **Add pytest import:**
   ```python
   import pytest
   ```

3. **Convert test structure:**
   - Remove: `test.start("name")`
   - Remove: `test.finish()`
   - Remove: `test.print_results_and_exit()`
   - Convert to: `def test_name(fixtures):`

4. **Convert device setup:**
   - Replace: `dev, ctx = test.find_first_device_or_exit()`
   - With: Use `test_device` fixture parameter

5. **Convert assertions:**
   - `test.check(x)` → `assert x`
   - `test.check_equal(a, b)` → `assert a == b`
   - `test.check_throws(...)` → `with pytest.raises(...):`

6. **Keep device markers:**
   - The `#test:device` comments work as-is
   - Or use `@pytest.mark.device("pattern")`

7. **Handle skip conditions:**
   - Replace: `log.f("message")` (which exits)
   - With: `pytest.skip("message")`

## Example Migration

### Original Test (LibCI)

```python
# test:device D400*

from rspy import test, log
import pyrealsense2 as rs

dev, ctx = test.find_first_device_or_exit()

test.start("Test streaming")
config = rs.config()
config.enable_stream(rs.stream.depth)
pipe = rs.pipeline(ctx)
pipe.start(config)
frames = pipe.wait_for_frames()
test.check(frames.size() > 0)
pipe.stop()
test.finish()

test.print_results_and_exit()
```

### Migrated Test (Pytest)

```python
# test:device D400*

import pytest
from rspy import log
import pyrealsense2 as rs

def test_streaming(test_device):
    """Test that streaming returns frames."""
    dev, ctx = test_device
    
    config = rs.config()
    config.enable_stream(rs.stream.depth)
    pipe = rs.pipeline(ctx)
    pipe.start(config)
    
    frames = pipe.wait_for_frames()
    assert frames.size() > 0
    
    pipe.stop()
```

## Advanced Features

### Parametrization

Run the same test with different parameters:

```python
@pytest.mark.parametrize("width,height", [
    (640, 480),
    (1280, 720),
])
def test_resolution(test_device, width, height):
    dev, ctx = test_device
    # test with width and height
```

### Fixtures with Setup/Teardown

```python
@pytest.fixture
def configured_pipeline(test_context):
    pipe = rs.pipeline(test_context)
    config = rs.config()
    config.enable_stream(rs.stream.depth)
    pipe.start(config)
    
    yield pipe  # Test runs here
    
    pipe.stop()  # Cleanup

def test_with_pipeline(configured_pipeline):
    frames = configured_pipeline.wait_for_frames()
    assert frames.size() > 0
```

### Multiple Devices

For tests that need to run on each device separately:

```python
# test:device each(D400*)

def test_on_each_device(test_device):
    # This will run once per D400 device
    dev, ctx = test_device
    # ...
```

## Benefits of Pytest

1. **Industry Standard**: Well-documented, widely-used testing framework
2. **Rich Ecosystem**: Plugins for coverage, parallel execution, HTML reports, etc.
3. **Better IDE Integration**: VS Code, PyCharm, etc. have native pytest support
4. **Cleaner Syntax**: Standard Python assertions instead of custom check functions
5. **Advanced Features**: Parametrization, fixtures, marks, and more
6. **Better Reporting**: Clear output with detailed failure information

## Common Commands

```bash
# Run all tests
pytest

# Run tests in specific directory
pytest live/frames/

# Run tests matching pattern
pytest -k "pipeline or metadata"

# Run tests with specific marker
pytest -m live

# Run with stdout visible
pytest -s

# Run with detailed output
pytest -v

# Run and show 20 slowest tests
pytest --durations=20

# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Generate HTML report (requires pytest-html)
pytest --html=report.html

# Run with coverage (requires pytest-cov)
pytest --cov=rspy --cov-report=html
```

## Troubleshooting

### "No device found"
- Ensure devices are connected
- Check that device hub is functioning
- Verify pyrealsense2 can see devices: `python -c "import pyrealsense2 as rs; print(rs.context().devices)"`

### "Module not found: pyrealsense2"
- Ensure pyrealsense2 is built and in the correct location
- Check PYTHONPATH includes the build directory
- The conftest.py should handle this automatically

### Tests skipped unexpectedly
- Check device markers match your connected devices
- Use `pytest -v` to see skip reasons
- Verify device patterns are correct (e.g., `D400*` vs `D455`)

### Device hub not releasing ports
- The session teardown should handle this
- Manually run: `python -c "from rspy import devices; devices.hub.disable_ports()"`

## Next Steps

1. Review this guide
2. Run the migrated test: `pytest live/frames/test-t2ff-pipeline.py -s -v`
3. Verify device selection and power cycling work correctly
4. Gradually migrate other tests following the same pattern
5. Consider adding pytest plugins for enhanced functionality

## Support

For questions or issues with the migration:
1. Review pytest documentation: https://docs.pytest.org/
2. Check the `conftest.py` for fixture implementations
3. Look at migrated tests for examples
4. Consult the team for LibRS-specific concerns
