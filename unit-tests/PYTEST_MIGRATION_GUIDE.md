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
# Run all migrated tests (pytest-*.py files)
python -m pytest -v

# Run specific test file
python -m pytest live/frames/pytest-t2ff-pipeline.py -s -v

# Run with debug logging
python -m pytest -s -v --log-cli-level=DEBUG

# Filter by marker
python -m pytest -m live

# Filter by test name pattern
python -m pytest -k "depth"
```

### Validation

Run the validation script to check your setup:

```bash
cd unit-tests
python validate-pytest-migration.py
```

## File Naming Convention

**IMPORTANT**: We use a clear naming convention to separate migrated and legacy tests:

- **`pytest-*.py`** — Migrated pytest tests (discovered by pytest)
- **`test-*.py`** — Legacy LibCI tests (ignored by pytest, run via `run-unit-tests.py`)

This allows gradual migration without interference between old and new infrastructure.

## CLI Command Reference

| run-unit-tests.py | pytest equivalent |
|---|---|
| `-r, --regex <pat>` | `-k <pat>` |
| `-t, --tag <tag>` | `-m <marker>` |
| `--debug` | `--log-cli-level=DEBUG` |
| `-s, --stdout` | `-s` |
| `-v, --verbose` | `-v` |
| `--device <spec>` | `--device <spec>` (custom) |
| `--exclude-device <spec>` | `--device-exclude <spec>` (custom) |
| `--context <ctx>` | `--context <ctx>` (custom) |
| `--retry <N>` | `--retries <N>` (pytest-retry) |
| `--repeat <N>` | `--count <N>` (pytest-repeat) |
| `--rslog` | `--rslog` (custom) |
| `--no-reset` | `--no-reset` (custom) |
| `--hub-reset` | `--hub-reset` (custom) |
| `--live` | `-m live` |
| `--not-live` | `-m "not live"` |
| `--list-tests` | `--collect-only` |
| `--list-tags` | `--collect-only -m` |
| `--skip-disconnected` | Default behavior (pytest.skip) |

## Directive to Marker Mapping

| LibCI directive | pytest marker |
|---|---|
| `#test:device D400*` | `pytest.mark.device("D400*")` |
| `#test:device each(D400*)` | `pytest.mark.device_each("D400*")` |
| `#test:donotrun:!nightly` | `pytest.mark.nightly` |
| `#test:donotrun:!dds` | `pytest.mark.dds` |
| `#test:timeout 1500` | `pytest.mark.timeout(1500)` |
| `#test:priority 1` | `pytest.mark.priority(1)` |

## Migration Steps

### Step 1: Convert Test Structure

**Before (LibCI):**
```python
from rspy import test, log
import pyrealsense2 as rs

#test:device each(D400*)
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
| `test.start("Name")` | `def test_name():` |
| `test.check(condition)` | `assert condition` |
| `test.check_equal(a, b)` | `assert a == b` |
| `log.f("Skip reason")` | `pytest.skip("Skip reason")` |
| `test.finish()` | *(automatic)* |
| `test.print_results_and_exit()` | *(automatic)* |

### Step 3: Convert Device Markers

**Module-level markers (recommended):**
```python
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_each("D500*"),
    pytest.mark.live
]
```

**Function-level markers:**
```python
@pytest.mark.device_each("D400*")
@pytest.mark.live
def test_something(test_device):
    ...
```

### Step 4: Rename File

After conversion, rename from `test-*.py` to `pytest-*.py`.

## Fixture Reference

### `test_device`
Provides `(device, context)` tuple. Equivalent to `test.find_first_device_or_exit()`.

```python
def test_something(test_device):
    dev, ctx = test_device
    product_line = dev.get_info(rs.camera_info.product_line)
```

### `module_test_device`
Alias for `test_device` — same `(device, context)` tuple.

### `test_context`
Provides just the `rs.context()`. Enables `--rslog` if specified.

```python
def test_something(test_context):
    ctx = test_context
    devices = ctx.query_devices()
```

### `module_device_setup`
Internal fixture for device port control. Used by `test_context`. Yields serial number.

### `test_context_var`
Provides the context list (e.g., `['nightly', 'weekly']`).

```python
def test_something(test_context_var):
    if 'nightly' in test_context_var:
        iterations = 1000
```

## Device Exclusion

### Using Markers (in code)

```python
pytestmark = [
    pytest.mark.device_each("D400*"),
    pytest.mark.device_exclude("D457"),
    pytest.mark.device_exclude("D405"),
]
```

### Using CLI (at runtime)

```bash
python -m pytest --device-exclude D455
python -m pytest --device-exclude D455 --device-exclude D457
```

CLI exclusions are merged with marker-based exclusions.

## Device Include Filter

```bash
# Only run on D455 devices
python -m pytest --device D455

# Only run on D400 series
python -m pytest --device "D400*"
```

## Timeout Configuration

Default timeout: 200 seconds (set in `pytest.ini`).

```python
# Per-test override
@pytest.mark.timeout(300)
def test_something():
    ...

# Module-level override
pytestmark = pytest.mark.timeout(1500)
```

```bash
# CLI override
python -m pytest --timeout=300
python -m pytest --timeout=0  # disable
```

## Nightly Tests

```python
pytestmark = pytest.mark.nightly
```

- Default: nightly tests are **skipped**
- Run only nightly: `python -m pytest -m nightly`
- Run all including nightly: `python -m pytest -m "nightly or not nightly"`

## Migration Checklist

When migrating a test file:

- [ ] Remove LibCI imports (`from rspy import test`)
- [ ] Convert `test.start()/finish()` to pytest functions
- [ ] Replace `test.check()` with `assert`
- [ ] Convert device comments to `pytestmark` markers
- [ ] Add fixtures (`test_device`, `test_context`)
- [ ] Replace `log.f()` with `pytest.skip()`
- [ ] Rename from `test-*.py` to `pytest-*.py`
- [ ] Test: `python -m pytest path/to/pytest-file.py -v`
- [ ] Verify collection: `python -m pytest --collect-only`

## Files in This Migration

| File | Purpose |
|---|---|
| `conftest.py` | Pytest fixtures, hooks, device management, and configuration |
| `validate-pytest-migration.py` | Setup validation script |
| `PYTEST_MIGRATION_GUIDE.md` | This file |
| `live/frames/pytest-t2ff-pipeline.py` | Migrated test example |
