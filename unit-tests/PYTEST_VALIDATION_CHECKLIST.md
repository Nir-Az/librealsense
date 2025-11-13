# Pytest Migration - Validation Checklist

Use this checklist to validate the pytest migration on your system.

## Prerequisites

- [ ] Librealsense built with Python bindings
- [ ] At least one RealSense device connected (D400 or D500 series)
- [ ] Device hub connected (Acroname, Ykush, or Unify) - optional but recommended
- [ ] Python 3.x installed
- [ ] pytest installed (`pip install pytest`)

## Step 1: Environment Check

```bash
cd c:\work\git\librealsense\unit-tests
```

- [ ] Verify you're in the unit-tests directory
- [ ] Check Python version: `python --version` (should be 3.6+)
- [ ] Check pytest installed: `pytest --version` (should be 6.0+)

## Step 2: Run Validation Script

```bash
python validate-pytest-migration.py
```

Expected output: "VALIDATION PASSED - All checks successful!"

If validation fails, check:
- [ ] All required files exist (conftest.py, pytest.ini, test-t2ff-pipeline.py)
- [ ] rspy modules can be imported
- [ ] pyrealsense2 can be imported
- [ ] Devices are detected

## Step 3: Check Device Detection

```bash
python -c "from rspy import devices; devices.query(); devs = devices.all(); print(f'Found {len(devs)} device(s)'); [print(f'  - {d.name} ({sn})') for sn, d in devs.items()]"
```

- [ ] At least one device is detected
- [ ] Device name matches test requirements (D400* or D500*)

## Step 4: Check Device Hub (Optional)

```bash
python -c "from rspy import devices; devices.query(); print(f'Hub: {devices.hub}'); print(f'Connected: {devices.hub.is_connected() if devices.hub else False}')"
```

- [ ] Hub is detected (or you accept tests without power cycling)
- [ ] Hub is connected

## Step 5: Test Discovery

```bash
pytest --collect-only live/frames/test-t2ff-pipeline.py
```

Expected: Should list 2 test functions
- [ ] `test_pipeline_first_depth_frame_delay`
- [ ] `test_pipeline_first_color_frame_delay`

## Step 6: Check Markers

```bash
pytest --collect-only -v live/frames/test-t2ff-pipeline.py
```

Look for markers in output:
- [ ] Tests have `device` or `device_each` markers
- [ ] Tests have `live` marker
- [ ] Markers match device requirements (D400*, D500*)

## Step 7: Dry Run (No Execution)

```bash
pytest --collect-only --markers
```

- [ ] `device(pattern)` marker is registered
- [ ] `device_each(pattern)` marker is registered
- [ ] `live` marker is registered

## Step 8: Run the Migrated Test

```bash
pytest live/frames/test-t2ff-pipeline.py -s -v
```

Expected behavior:
- [ ] Test session starts
- [ ] Devices are queried
- [ ] Device hub enables target device(s)
- [ ] Device is power cycled
- [ ] Test module setup completes
- [ ] First test runs: `test_pipeline_first_depth_frame_delay`
- [ ] Second test runs or skips: `test_pipeline_first_color_frame_delay` (skips if no color sensor)
- [ ] Tests pass (frame delays within limits)
- [ ] Session teardown (hub ports disabled)

## Step 9: Verify Output

Check the test output contains:
- [ ] "Test session starting" (from conftest.py)
- [ ] Device information (product line, name)
- [ ] Timing measurements (delay in seconds)
- [ ] PASSED status for tests
- [ ] "Test session ending" (from conftest.py)

## Step 10: Verify Device Hub Behavior

If you have a device hub:
- [ ] Only target device port was enabled during test
- [ ] Other device ports were disabled
- [ ] All ports disabled after session end

To verify:
```bash
python -c "from rspy import devices; devices.query(); enabled = devices.enabled(); print(f'Enabled devices: {list(enabled)}')"
```
After test completion, this should show no devices (ports disabled).

## Step 11: Test Filtering

Try different pytest filters:

```bash
# By test name
pytest -k "depth" live/frames/test-t2ff-pipeline.py -v
```
- [ ] Only depth test runs

```bash
# By marker
pytest -m live live/frames/ -v --collect-only
```
- [ ] Only tests with 'live' marker are collected

```bash
# Specific test function
pytest live/frames/test-t2ff-pipeline.py::test_pipeline_first_depth_frame_delay -v
```
- [ ] Only specified test runs

## Step 12: Test with Different Options

```bash
# Quiet mode
pytest live/frames/test-t2ff-pipeline.py -q
```
- [ ] Minimal output, just pass/fail

```bash
# Very verbose
pytest live/frames/test-t2ff-pipeline.py -vv
```
- [ ] Detailed output including full paths

```bash
# Show durations
pytest live/frames/test-t2ff-pipeline.py --durations=5
```
- [ ] Slowest tests are listed

## Step 13: Check Error Handling

Disconnect all devices and run:
```bash
pytest live/frames/test-t2ff-pipeline.py -v
```

- [ ] Tests are skipped (not failed) with message "No device found" or similar

Reconnect devices before continuing.

## Step 14: Verify Log Output

Run with debug logging:
```bash
pytest live/frames/test-t2ff-pipeline.py -s --log-cli-level=DEBUG
```

- [ ] Debug messages from conftest.py visible
- [ ] Device setup messages visible
- [ ] Test messages visible

## Step 15: Compare with Old System (Optional)

If you still have the old system working:

**Old way:**
```bash
py -3 run-unit-tests.py -s live/frames/test-t2ff-pipeline.py
```

**New way:**
```bash
pytest live/frames/test-t2ff-pipeline.py -s
```

- [ ] Both produce similar results
- [ ] Same tests pass/fail
- [ ] Device behavior is the same

## Common Issues and Solutions

### ❌ "No module named pyrealsense2"
**Solution:** Ensure build directory with .pyd/.so is accessible
```bash
$env:PYTHONPATH = "C:\path\to\build\Debug" # PowerShell
pytest ...
```

### ❌ "No device found"
**Solution:** Check device connection
```bash
python -c "import pyrealsense2 as rs; print(rs.context().devices)"
```

### ❌ Tests fail with assertion errors
**Solution:** Check device compatibility
- Ensure device matches test requirements (D400 or D500)
- Check if timing limits are realistic for your system
- Some delays may vary by OS/hardware

### ❌ "Hub not connected"
**Solution:** 
- Check hub USB connection
- Verify hub drivers installed
- Tests can run without hub (but no power cycling)

### ❌ Import errors from conftest.py
**Solution:** Run from unit-tests directory
```bash
cd unit-tests
pytest ...
```

## Final Verification

After completing all steps:

- [ ] Validation script passes
- [ ] Device detection works
- [ ] Test discovery works
- [ ] Migrated test runs successfully
- [ ] Device hub controls devices correctly
- [ ] Power cycling happens between modules
- [ ] Test filtering works
- [ ] Output is clear and informative

## Sign-Off

Date: _______________

Tested by: _______________

System: 
- [ ] Windows
- [ ] Linux
- [ ] WSL

Devices tested:
- [ ] D400 series: _______________
- [ ] D500 series: _______________

Hub tested:
- [ ] Acroname
- [ ] Ykush
- [ ] Unify
- [ ] No hub

Results:
- [ ] All tests passed
- [ ] Some tests failed (document below)
- [ ] Tests skipped due to device requirements

Notes:
_____________________________________
_____________________________________
_____________________________________

## Next Steps After Validation

Once validation is complete and successful:

1. [ ] Review migration guide: `PYTEST_MIGRATION.md`
2. [ ] Read quick start: `PYTEST_QUICK_START.md`
3. [ ] Understand implementation: `PYTEST_IMPLEMENTATION.md`
4. [ ] Plan gradual migration of other tests
5. [ ] Consider migrating similar simple tests next
6. [ ] Update team documentation
7. [ ] Update CI/CD pipelines

---

**Questions or issues?** Refer to the troubleshooting section in `PYTEST_QUICK_START.md` or `PYTEST_MIGRATION.md`.
