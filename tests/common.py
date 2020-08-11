"""
Common preparations for all test suites. Use this as a source of constants for test cases. Find the tests themselfs at
the concrete files

NOTE: make sure the test project tree is clean before running the tests!

'pyenv' was used to execute tests with different Python versions (under Linux):
https://github.com/pyenv/pyenv
https://www.tecmint.com/pyenv-install-and-manage-multiple-python-versions-in-linux/

To get the test coverage install and use 'coverage' package:
    $  coverage run -m unittest -b
    $  coverage html

This will not cover subprocess calls, though. To get them covered too, use pytest and its pytest-cov plugin
    $  pip install pytest pytest-cov
    $  pytest --cov=stm32pio --cov-branch --cov-report=html
"""

import inspect
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


CASES_ROOT = Path(os.environ.get('STM32PIO_TEST_FIXTURES', default=Path(__file__).parent / 'fixtures')).resolve(strict=True)
os.environ['STM32PIO_TEST_FIXTURES'] = str(CASES_ROOT)

CASE = os.environ.get('STM32PIO_TEST_CASE', default='nucleo_f031k6')
PROJECT_PATH = CASES_ROOT.joinpath(CASE).resolve(strict=True)
PROJECT_BOARD = CASE  # currently (board == folder_name)
os.environ['STM32PIO_TEST_CASE'] = CASE


import stm32pio.cli.app


if not next(PROJECT_PATH.glob('*.ioc'), False):
    raise FileNotFoundError(f"No .ioc file is present for '{PROJECT_PATH.name}' test case")
else:
    PROJECT_IOC_FILENAME = next(PROJECT_PATH.glob('*.ioc')).name
print(PROJECT_IOC_FILENAME)

# PROJECT_PATH = pathlib.Path('stm32pio-test-project').resolve(strict=True)
# if not PROJECT_PATH.joinpath('stm32pio-test-project.ioc').is_file():
#     raise FileNotFoundError("No test project is present")

# Gently ask a user running tests to remove all irrelevant files from the PROJECT_PATH as they can interfere with
# execution
# if len(list(PROJECT_PATH.iterdir())) > 1:
#     raise Warning(f"There are extrinsic files in the test project directory '{PROJECT_PATH}'. Please persist only "
#                   "the .ioc file and restart")

# Make sure you have F0 framework installed (both for PlatformIO and CubeMX) (try to run a code generation and build
# manually at least once before proceeding)
# PROJECT_BOARD = 'nucleo_f031k6'

# Instantiate a temporary folder on every test suite run. It is used across all the tests and is deleted on shutdown
# automatically
TEMP_DIR = tempfile.TemporaryDirectory()
STAGE_PATH = Path(TEMP_DIR.name).joinpath(PROJECT_PATH.name)

# Absolute path to the main stm32pio script (make sure what we are testing)
STM32PIO_MAIN_SCRIPT: str = inspect.getfile(stm32pio.cli.app.main)
# Absolute path to the Python executable (no need to guess whether it's 'python' or 'python3' and so on)
PYTHON_EXEC: str = sys.executable

print(f"Test case: {PROJECT_BOARD}")
print(f"The file of 'stm32pio.app' module: {STM32PIO_MAIN_SCRIPT}")
print(f"Python executable: {PYTHON_EXEC} {sys.version}")
print(f"Temp test stage path: {STAGE_PATH}")
print()


class CustomTestCase(unittest.TestCase):
    """These pre- and post-tasks are common for all test cases"""

    def setUp(self):
        """
        Copy the test project from the repo to our temp directory. WARNING: make sure the test project folder (one from
        this repo, not a temporarily created one) is clean (i.e. contains only an .ioc file) before running the test
        """
        shutil.rmtree(STAGE_PATH, ignore_errors=True)
        # ignore: copy only an .ioc files (there should be only 1)
        shutil.copytree(PROJECT_PATH, STAGE_PATH,
                        ignore=lambda folder, files: [folder] + list(filter(lambda name: '.ioc' not in name, files)))

    def tearDown(self):
        """
        Clean up the temp directory
        """
        shutil.rmtree(STAGE_PATH, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
