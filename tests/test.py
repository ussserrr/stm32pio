"""
Common preparations for all test suites. Use this as a source of constants for test cases. Find the tests themself at
concrete files

NOTE: make sure the test project tree is clean before running the tests!

'pyenv' was used to execute tests with different Python versions (under Ubuntu):
https://www.tecmint.com/pyenv-install-and-manage-multiple-python-versions-in-linux/

To get the test coverage install and use 'coverage' package:
    $  coverage run -m stm32pio.tests.test -b
    $  coverage html
"""

import inspect
import pathlib
import shutil
import sys
import tempfile
import unittest

import stm32pio.app


# Absolute path to the main stm32pio script (make sure what repo we are testing
STM32PIO_MAIN_SCRIPT: str = inspect.getfile(stm32pio.app)
# Absolute path to the Python executable (no need to guess whether it's 'python' or 'python3' and so on)
PYTHON_EXEC: str = sys.executable

# Test data
TEST_PROJECT_PATH = pathlib.Path('stm32pio-test-project').resolve(strict=True)
if not TEST_PROJECT_PATH.joinpath('stm32pio-test-project.ioc').is_file():
    raise FileNotFoundError("No test project is present")
# Make sure you have F0 framework installed (try to run code generation from STM32CubeMX manually at least once before
# proceeding)
TEST_PROJECT_BOARD = 'nucleo_f031k6'

# Instantiate a temporary folder on every test suite run. It is used across all the tests and is deleted on shutdown
# automatically
TEMP_DIR = tempfile.TemporaryDirectory()
FIXTURE_PATH = pathlib.Path(TEMP_DIR.name).joinpath(TEST_PROJECT_PATH.name)

print(f"The file of 'stm32pio.app' module: {STM32PIO_MAIN_SCRIPT}")
print(f"Python executable: {PYTHON_EXEC} {sys.version}")
print(f"Temp test fixture path: {FIXTURE_PATH}")
print()


class CustomTestCase(unittest.TestCase):
    """
    These pre- and post-tasks are common for all test cases
    """

    def setUp(self):
        """
        Copy the test project from the repo to our temp directory. WARNING: make sure the test project folder (one from
        this repo, not a temporarily created one) is clean (i.e. contains only an .ioc file) before running the test
        """
        shutil.rmtree(FIXTURE_PATH, ignore_errors=True)
        shutil.copytree(TEST_PROJECT_PATH, FIXTURE_PATH)

    def tearDown(self):
        """
        Clean up the temp directory
        """
        shutil.rmtree(FIXTURE_PATH, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
