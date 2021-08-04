"""
This file provides all kinds of configurable parameters for different application modules. Also, this is a source of the
default project config file stm32pio.ini. None of the variables here should be edited in runtime.

Bottom part of the file contains some definitions specifically targeting continuous integration environment. They have
no effect on normal or test (local) runs. Probably, they should be removed from the source code entirely and some
another solution need to be prepared.
"""

import collections
import inspect
import logging
import os
from pathlib import Path
import platform


my_os = platform.system()

config_file_name = 'stm32pio.ini'

config_default = collections.OrderedDict(  # guarantees printing to the file in the same order
    app={
        # How do you start Java from the command line? (edit if Java not in PATH). Can be safely set to 'None' (string)
        # if in your setup the CubeMX can be invoked directly
        'java_cmd': 'None',

        # How do you start PlatformIO from the command line? (edit if not in PATH, if you use PlatformIO IDE see
        # https://docs.platformio.org/en/latest/core/installation.html#piocore-install-shell-commands).
        # Note: "python -m platformio" isn't supported yet
        'platformio_cmd': 'platformio',

        # Trying to guess the STM32CubeMX location. ST actually had changed the installation path several times already.
        # It also depends on how do one obtain a distribution archive (logging in on web-site or just downloading by the
        # direct link). STM32CubeMX will be invoked as 'java -jar [cubemx_cmd]'
        'cubemx_cmd':
            # macOS default: 'Applications' folder
            '/Applications/STMicroelectronics/STM32CubeMX.app/Contents/MacOs/STM32CubeMX' if my_os == 'Darwin' else
            # Linux (Ubuntu) default: home directory
            str(Path.home() / 'STM32CubeMX/STM32CubeMX') if my_os == 'Linux' else
            # Windows default: Program Files
            'C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX.exe' if my_os == 'Windows' else None
    },
    project={
        # (default is OK) See CubeMX user manual PDF (UM1718) to get other useful options
        'cubemx_script_content': inspect.cleandoc('''
            config load ${ioc_file_absolute_path}
            generate code ${project_dir_absolute_path}
            exit
        '''),

        # Override the defaults to comply with CubeMX project structure. This should meet INI-style requirements. You
        # can include existing sections, too (e.g.
        #
        #   [env:nucleo_f031k6]
        #   key = value
        #
        # will add a 'key' parameter)
        'platformio_ini_patch_content': inspect.cleandoc('''
            [platformio]
            include_dir = Inc
            src_dir = Src
        '''),

        'board': '',
        'ioc_file': '',  # required, the file name (relative to the project path)

        'cleanup_ignore': '',
        'cleanup_use_git': False  # if True, 'clean' command use git to perform the task
    }
)

# Values to match with on user input (both config and CLI) (use in conjunction with .lower() to ignore case)
none_options = ['none', 'no', 'null', '0']
no_options = ['n', 'no', 'false', '0']
yes_options = ['y', 'yes', 'true', '1']

# CubeMX 0 return code doesn't necessarily means the correct generation (e.g. migration dialog has appeared and 'Cancel'
# was chosen, or CubeMX_version < ioc_file_version, etc.), we should analyze the actual output (STDOUT)
cubemx_str_indicating_success = 'Code succesfully generated'
cubemx_str_indicating_error = 'Exception in code generation'  # final line "KO" is also a good sign of an error

# Longest name (not necessarily a method so a little bit tricky...)
# log_fieldwidth_function = max([len(member) for member in dir(stm32pio.lib.Stm32pio)]) + 1
log_fieldwidth_function = 20

show_traceback_threshold_level: int = logging.DEBUG  # when log some error and need to print the traceback

pio_boards_cache_lifetime: float = 5.0  # in seconds


#
# Do not distract end-user with this CI s**t, take out from the main dict definition above
#
# Environment variable indicating we are running on a CI server and should tweak some parameters
CI_ENV_VARIABLE = os.environ.get('PIPELINE_WORKSPACE')
if CI_ENV_VARIABLE is not None:
    config_default['app'] = {
        'java_cmd': 'java',
        'platformio_cmd': 'platformio',
        'cubemx_cmd': str(Path(os.getenv('STM32PIO_CUBEMX_CACHE_FOLDER')) / 'STM32CubeMX.exe')
    }

    TEST_FIXTURES_PATH = Path(os.environ.get('STM32PIO_TEST_FIXTURES',
                                             default=Path(__file__).parent.joinpath('../../tests/fixtures')))
    TEST_CASE = os.environ.get('STM32PIO_TEST_CASE')
    patch_mixin = ''
    if TEST_FIXTURES_PATH is not None and TEST_CASE is not None:
        platformio_ini_lockfile = TEST_FIXTURES_PATH / TEST_CASE / 'platformio.ini.lockfile'
        if platformio_ini_lockfile.exists():
            patch_mixin = '\n\n' + platformio_ini_lockfile.read_text()
    config_default['project']['platformio_ini_patch_content'] += patch_mixin
