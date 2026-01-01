# Unit-Tests

## Running the Unit-Tests

When running **CMake** please make sure the following flag is passed:
`-DBUILD_UNIT_TESTS=true`
After running `make && sudo make install`, you can execute `live-test` to run library unit-tests. 
Make sure you have Intel® RealSense™ device connected. 

## Testing just the Software

If not all unit-tests are passing this can be related to faulty device or problems with the environment setup. 
We support recording test flows at the backend level and running tests on top of mock hardware. This helps us distinguish between hardware problems and software issues. 

* You can record unit-test into file using:
`./live-test into <filename>`

* To run unit-tests without actual hardware, based on recorded data, run:
`./live-test from <filename>`

This mode of operation lets you test your code on a variety of simulated devices.  

## Test Data

If you would like to run and debug unit-tests locally on your machine but you don't have a RealSense device, we publish a set of *unit-test* recordings. These files capture expected execution of the test-suite over several types of hardware (D415, D435, etc..) 
Please see [Github Actions](https://docs.github.com/en/actions) for the exact URLs. 

> These recordings do not contain any imaging data and therefore can only be useful for unit-tests. If you would like to run your algorithms on top of captured data, please review our [playback and record](https://github.com/IntelRealSense/librealsense/tree/master/src/media) capabilities. 

In addition to running the tests locally, it is very easy to replicate our continuous integration process for your fork of the project - just sign-in to [Github Actions](https://docs.github.com/en/actions) and enable builds on your fork of `librealsense`. 

## Python Unit Tests (Pytest Migration)

Python unit tests are being migrated from the proprietary LibCI infrastructure to pytest. Migrated tests use the `pytest-*.py` naming convention, while legacy tests remain as `test-*.py`.

### Quick Start

```bash
# Install pytest-timeout (required for timeout support)
pip install pytest-timeout

# Run all migrated tests
py -3.13 -m pytest -v

# Run specific test
py -3.13 -m pytest live/frames/pytest-t2ff-pipeline.py -v

# Run only nightly tests
py -3.13 -m pytest -m nightly

# Skip nightly tests (default behavior)
py -3.13 -m pytest -m "not nightly"

# Validate setup
py -3.13 validate-pytest-migration.py
```

### Key Features

- **Device Hub Control**: Maintains full device hub integration for power cycling
- **Device Markers**: Tests specify which devices they need (e.g., `@pytest.mark.device_each("D400*")`)
- **Timeouts**: Default 200s, configurable per-test (e.g., `@pytest.mark.timeout(1500)`)
- **Nightly Tests**: Automatically skipped unless explicitly requested

See [PYTEST_MIGRATION_GUIDE.md](PYTEST_MIGRATION_GUIDE.md) for complete documentation on migrating tests and available fixtures.

## Controlling Test Execution

We are using [Catch](https://github.com/philsquared/Catch) as our test framework for C++ tests. 

To see the list of passing tests (and not just the failures), add `-d yes` to test command line.
