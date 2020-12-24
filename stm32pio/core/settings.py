import collections
import inspect
import logging
import os
from pathlib import Path
import platform


# Environment variable indicating we are running on a CI server and should tweak some parameters
CI_ENV_VARIABLE = os.environ.get('PIPELINE_WORKSPACE')

TEST_FIXTURES_PATH = Path(os.environ.get('STM32PIO_TEST_FIXTURES',
                                         default=Path(__file__).parent.joinpath('../../tests/fixtures')))
TEST_CASE = os.environ.get('STM32PIO_TEST_CASE')

patch_mixin = ''
if TEST_FIXTURES_PATH is not None and TEST_CASE is not None:
    platformio_ini_lockfile = TEST_FIXTURES_PATH / TEST_CASE / 'platformio.ini.lockfile'
    if platformio_ini_lockfile.exists():
        patch_mixin = '\n\n' + platformio_ini_lockfile.read_text()


my_os = platform.system()

# Values to match with on user input (both config and CLI) (use in conjunction with .lower() to ignore case)
none_options = ['none', 'no', 'null', '0']
no_options = ['n', 'no', 'false', '0']
yes_options = ['y', 'yes', 'true', '1']

config_file_name = 'stm32pio.ini'

config_default = collections.OrderedDict(
    app={
        # (default is OK) How do you start Java from the command line? (edit if Java not in PATH). Set to 'None'
        # (string) if in your setup the CubeMX can be invoked straightforwardly
        'java_cmd': 'java',

        # (default is OK) How do you start PlatformIO from the command line? (edit if not in PATH, if you use PlatformIO
        # IDE check https://docs.platformio.org/en/latest/installation.html#install-shell-commands)
        'platformio_cmd': 'platformio',

        # (default is OK) Trying to guess the STM32CubeMX location. STM actually had changed the installation path
        # several times already. Note that STM32CubeMX will be invoked as 'java -jar CUBEMX'
        'cubemx_cmd':
            str(Path.home().joinpath("cubemx/STM32CubeMX.exe")) if my_os in ['Darwin', 'Linux'] else
            "C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX.exe" if my_os == 'Windows' else None
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
        ''') + patch_mixin,

        'board': '',
        'ioc_file': '',  # required, the file name (relative to the project path)

        'cleanup_ignore': '',
        'cleanup_use_gitignore': False  # if True, 'clean' command will be purging only files/folders listed in .gitignore
                                        # (if present)
    }
)

# Do not distract the user with this CI s**t, take out from the main dict definition above
if CI_ENV_VARIABLE is not None:
    config_default['app'] = {
        'java_cmd': 'java',
        'platformio_cmd': 'platformio',
        'cubemx_cmd': str(Path(os.getenv('STM32PIO_CUBEMX_CACHE_FOLDER')).joinpath('STM32CubeMX.exe'))
    }

# CubeMX 0 return code doesn't necessarily means the correct generation (e.g. migration dialog has appeared and 'Cancel'
# was chosen, or CubeMX_version < ioc_file_version, etc.), we should analyze the actual output (STDOUT)
cubemx_str_indicating_success = 'Code succesfully generated'
cubemx_str_indicating_error = 'Exception in code generation'  # TODO: or line "KO"

# Longest name (not necessarily a method so a little bit tricky...)
# log_fieldwidth_function = max([len(member) for member in dir(stm32pio.lib.Stm32pio)]) + 1
log_fieldwidth_function = 20

show_traceback_threshold_level: int = logging.DEBUG  # when log some error and need to print the traceback

pio_boards_cache_lifetime: float = 5.0  # in seconds
