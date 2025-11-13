# Quick Start: Running Pytest Tests

## Prerequisites

1. **Build librealsense** with Python bindings (pyrealsense2)
2. **Connect devices** that match your test requirements
3. **Install pytest** (if not already installed):
   ```bash
   pip install pytest
   ```

## Basic Usage

### Run the Migrated Test

From the `unit-tests` directory:

```bash
# Run with output to console
pytest live/frames/test-t2ff-pipeline.py -s -v

# Run with debug output
pytest live/frames/test-t2ff-pipeline.py -s -v --log-cli-level=DEBUG
```

### Expected Output

You should see something like:

```
============================= test session starts =============================
platform win32 -- Python 3.x.x, pytest-7.x.x
collected 2 items

live/frames/test-t2ff-pipeline.py::test_pipeline_first_depth_frame_delay PASSED
live/frames/test-t2ff-pipeline.py::test_pipeline_first_color_frame_delay PASSED

============================== 2 passed in 10.23s ==============================
```

## Common Options

| Old Command | New Command | Description |
|------------|-------------|-------------|
| `py -3 run-unit-tests.py -s -r metadata` | `pytest -k metadata -s` | Run tests matching "metadata" with console output |
| `py -3 run-unit-tests.py --debug` | `pytest -v --log-cli-level=DEBUG` | Verbose with debug logs |
| `py -3 run-unit-tests.py -t live` | `pytest -m live` | Run only live tests |
| `py -3 run-unit-tests.py` | `pytest` | Run all tests |

## Filter Tests

```bash
# By file path pattern
pytest live/frames/

# By test name pattern
pytest -k "depth"

# By marker
pytest -m "device"

# Combined filters
pytest -k "pipeline" -m "live"

# Specific test function
pytest live/frames/test-t2ff-pipeline.py::test_pipeline_first_depth_frame_delay
```

## Viewing Output

```bash
# See print statements and logs immediately (like -s flag in old system)
pytest -s

# Verbose output (test names, results)
pytest -v

# Very verbose (show full paths)
pytest -vv

# Quiet mode (minimal output)
pytest -q
```

## Device Selection

The pytest infrastructure automatically handles device selection based on the `#test:device` comments in test files:

```python
# test:device D400*        # Runs on first D400 device found
# test:device each(D400*)  # Runs on each D400 device separately
# test:device D455         # Runs only on D455
```

Tests will be **automatically skipped** if no matching device is found.

## Troubleshooting

### Test Skipped: "No device found"

Check connected devices:
```bash
python -c "import pyrealsense2 as rs; ctx = rs.context(); print(f'Found {len(ctx.devices)} device(s)'); [print(f'  - {d.get_info(rs.camera_info.name)}') for d in ctx.devices]"
```

### ImportError: No module named 'pyrealsense2'

Ensure the build directory is in PYTHONPATH:
```bash
# Windows PowerShell
$env:PYTHONPATH = "C:\path\to\build\Debug"
pytest ...

# Or let conftest.py find it automatically (it searches for .pyd/.so files)
```

### Device Hub Issues

Check hub connection:
```bash
python -c "from rspy import devices; devices.query(); print(f'Hub connected: {devices.hub is not None}')"
```

### See Full Error Details

```bash
# Show full traceback
pytest --tb=long

# Show local variables in traceback
pytest --tb=auto -l
```

## Advanced Usage

### Run Tests in Parallel

Install pytest-xdist:
```bash
pip install pytest-xdist
```

Run tests in parallel (be careful with device tests!):
```bash
pytest -n auto
```

### Generate Coverage Report

Install pytest-cov:
```bash
pip install pytest-cov
```

Run with coverage:
```bash
pytest --cov=rspy --cov-report=html
# Open htmlcov/index.html to view report
```

### Generate HTML Test Report

Install pytest-html:
```bash
pip install pytest-html
```

Generate report:
```bash
pytest --html=report.html --self-contained-html
```

### Show Slowest Tests

```bash
pytest --durations=10  # Show 10 slowest tests
pytest --durations=0   # Show all test durations
```

## Pytest Configuration

The `pytest.ini` file contains default settings. You can override them:

```bash
# Override markers validation
pytest --strict-markers=false

# Change verbosity level
pytest -v        # verbose
pytest -vv       # very verbose
pytest -q        # quiet
pytest -qq       # very quiet

# Change log level
pytest --log-cli-level=INFO
pytest --log-cli-level=DEBUG
pytest --log-cli-level=WARNING
```

## Example Workflow

```bash
# 1. Navigate to unit-tests directory
cd c:\work\git\librealsense\unit-tests

# 2. Run the migrated test to verify setup
pytest live/frames/test-t2ff-pipeline.py -s -v

# 3. Run all tests matching "metadata"
pytest -k metadata -s

# 4. Run only live tests
pytest -m live -v

# 5. Generate a report
pytest --html=test-report.html --self-contained-html

# 6. View slowest tests
pytest --durations=20
```

## Getting Help

```bash
# List all available markers
pytest --markers

# List all collected tests (without running)
pytest --collect-only

# Show available fixtures
pytest --fixtures

# General pytest help
pytest --help
```

## Next Steps

1. **Verify the migration** works with your setup
2. **Review failing tests** if any (check device connections)
3. **Migrate more tests** following the same pattern
4. **Explore pytest features** like parametrization, fixtures, and plugins

For detailed migration instructions, see [PYTEST_MIGRATION.md](PYTEST_MIGRATION.md)
