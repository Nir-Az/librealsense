# Pytest Migration - Changes Summary

## Changes Made - Pure Pytest Markers

Date: November 11, 2025

### What Changed

Converted from comment-based device markers to pure pytest markers for a more native pytest experience.

### Removed from conftest.py

❌ **Removed**:
- `pytest_collection_modifyitems()` hook - No longer parsing comments
- `_parse_device_markers_from_file()` function - Not needed
- `find_first_device_or_exit()` compatibility function - Use fixtures instead
- Unused imports: `Optional`, `Set`

### Updated in conftest.py

✅ **Simplified**:
- `pytest_configure()` - Just registers markers, no dynamic parsing
- Cleaner, more maintainable code
- ~70 lines of code removed

### Updated Test File Format

**Before** (Comment-based):
```python
# test:device each(D400*)
# test:device each(D500*)

import pytest
import pyrealsense2 as rs
...

def test_something(device_config):
    ...
```

**After** (Pure pytest):
```python
import pytest
import pyrealsense2 as rs
...

# Mark entire module to run on D400 and D500 devices
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.live
]

def test_something(device_config):
    ...
```

### Migration Pattern for Other Tests

When migrating other tests, use this pattern:

**Module-level markers** (all tests in file use same device):
```python
pytestmark = [
    pytest.mark.device("D400*"),
    pytest.mark.live
]
```

**Per-function markers** (different tests need different devices):
```python
@pytest.mark.device("D455")
@pytest.mark.live
def test_d455_specific(test_device):
    ...

@pytest.mark.device("D500*")
@pytest.mark.live  
def test_d500_features(test_device):
    ...
```

### Benefits

✅ **IDE Support**: IDEs can autocomplete and validate markers  
✅ **Explicit**: Clear what markers apply to each test  
✅ **Pytest-native**: Standard pytest approach  
✅ **Faster collection**: No file parsing overhead  
✅ **Better tooling**: Works with pytest plugins and reporting  
✅ **Maintainable**: Less magic, easier to understand  

### Test Execution - Same as Before

All commands work the same:

```bash
# Run all tests
py -3.13 -m pytest live/frames/test-t2ff-pipeline.py -s -v

# Filter by marker
py -3.13 -m pytest -m live -v
py -3.13 -m pytest -m device_each -v

# Filter by name
py -3.13 -m pytest -k depth -v

# Collect only
py -3.13 -m pytest --collect-only live/frames/test-t2ff-pipeline.py
```

### Validation

✅ Tests still run correctly  
✅ Device selection works  
✅ Module-level markers apply to all tests  
✅ Filtering by markers works  
✅ Same functionality, cleaner code  

### Files Modified

1. **conftest.py**
   - Removed: `pytest_collection_modifyitems()` and `_parse_device_markers_from_file()`
   - Removed: `find_first_device_or_exit()` compatibility function
   - Simplified: `pytest_configure()`
   - ~70 lines removed

2. **test-t2ff-pipeline.py**
   - Removed: `# test:device` comments
   - Added: `pytestmark` with pytest markers
   - Same test logic, just different marker syntax

### Next Steps

When migrating other test files:
1. Remove `# test:device` comments
2. Add `pytestmark = [pytest.mark.device("pattern"), pytest.mark.live]` at module level
3. Or add `@pytest.mark.device()` decorators per function
4. Use fixtures instead of `test.find_first_device_or_exit()`

### Documentation Updates Needed

Update these files to reflect pure pytest marker usage:
- `PYTEST_MIGRATION.md` - Update migration examples
- `PYTEST_QUICK_START.md` - Update command examples  
- `PYTEST_README.md` - Update overview

---

**Result**: Cleaner, more maintainable, pytest-native implementation! ✨
