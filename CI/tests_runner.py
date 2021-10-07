#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Run tests on CI
"""

import os
from pathlib import Path
import platform
import subprocess

import yaml


# Environment variable indicating we are running on a CI server and should tweak some parameters
CI_ENV_VARIABLE = os.environ.get('PIPELINE_WORKSPACE')


if __name__ == '__main__':
    lockfile = yaml.safe_load(Path(__file__).parent.joinpath('lockfile.yml').read_text())['variables']
    cases = yaml.safe_load(lockfile['test_cases'])

    if CI_ENV_VARIABLE and platform.system() == 'Linux':
        Path('./pytest.ini').write_text("[pytest]\njunit_family = xunit2\n")  # temp config for pytest

    for case in cases:
        print('========================================', flush=True)
        print(f"Test case: {case}", flush=True)
        print('========================================', flush=True)
        os.environ['STM32PIO_TEST_CASE'] = case
        # On Linux also form code coverage report
        if platform.system() == 'Linux':
            args = ['pytest', 'tests', '--junitxml=junit/test-results.xml', '--cov=stm32pio/core', '--cov=stm32pio/cli',
                    '--cov-branch', '--cov-report=xml']
        else:
            args = ['python', '-m', 'unittest', '-b', '-v']
        subprocess.run(args)
