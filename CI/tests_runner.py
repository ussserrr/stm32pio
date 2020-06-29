import os
from pathlib import Path
import subprocess

import yaml


if __name__ == '__main__':
    lockfile = yaml.safe_load(Path(__file__).parent.joinpath('lockfile.yml').read_text())['variables']
    cases = yaml.safe_load(lockfile['test_cases'])

    Path('./pytest.ini').write_text("[pytest]\njunit_family = xunit2\n")

    for case in cases:
        print('========================================')
        print(f"Test case: {case}")
        print('========================================')
        os.environ['STM32PIO_TEST_CASE'] = case
        args = ['pytest', 'tests', '--junitxml=junit/test-results.xml', '--cov=stm32pio/core', '--cov=stm32pio/cli', '--cov-branch', '--cov-report=xml']
        subprocess.run(args)
