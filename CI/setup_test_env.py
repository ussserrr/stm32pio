#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pathlib
import subprocess
import tempfile

import yaml


def install_cubemx_mcu_packages(query):
    # Use mkstemp() instead of the higher-level API for the compatibility with Windows (see tempfile docs for
    # more details)
    # cubemx_script_file, cubemx_script_name = tempfile.mkstemp()
    # # buffering=0 leads to the immediate flushing on writing
    # with open(cubemx_script_file, mode='w+b', buffering=0) as cubemx_script:
    if True:
        cubemx_script_content = '\n'.join([f"swmgr install stm32cube_{series}_{version} accept"
                                           for series, version in query.items()])
        print(cubemx_script_content)
        # cubemx_script.write(cubemx_script_content.encode())
        # subprocess.run([str(pathlib.Path(os.getenv('CUBEMX_CACHE_FOLDER')).joinpath('STM32CubeMX.exe')), '-q',
        #                 cubemx_script_name, '-s'])


def lock_platformio_ini(config):
    pass


if __name__ == '__main__':
    lockfile = yaml.safe_load(open('lockfile.yml'))['variables']

    install_cubemx_mcu_packages(lockfile['cubemx_packages'])
