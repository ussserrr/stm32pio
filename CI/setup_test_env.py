#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path
import subprocess
import tempfile

import yaml


def install_cubemx_mcu_packages(query):
    """Install software packages for CubeMX (which are used for code generation)
    """
    # Use mkstemp() instead of the higher-level API for the compatibility with Windows (see tempfile docs for
    # more details)
    cubemx_script_file, cubemx_script_name = tempfile.mkstemp()
    # buffering=0 leads to the immediate flushing on writing
    with open(cubemx_script_file, mode='w+b', buffering=0) as cubemx_script:
        cubemx_script_content = '\n'.join([f"swmgr install stm32cube_{series}_{version} accept"
                                           for series, version in query.items()]) + "\nexit"
        cubemx_script.write(cubemx_script_content.encode())  # encode since mode='w+b'
        subprocess.run(['java', '-jar', Path(os.getenv('STM32PIO_CUBEMX_CACHE_FOLDER')) / 'STM32CubeMX.exe', '-q',
                        cubemx_script_name, '-s'])


if __name__ == '__main__':
    lockfile = yaml.safe_load(Path(__file__).parent.joinpath('lockfile.yml').read_text())['variables']

    install_cubemx_mcu_packages(yaml.safe_load(lockfile['cubemx_packages']))
