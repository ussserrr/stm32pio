import collections
import inspect
import os
import pathlib
import platform


# Environment variable indicating we are running on a CI server and should tweak some parameters
CI_ENV_VARIABLE = os.environ.get('AGENT_TOOLSDIRECTORY')
if CI_ENV_VARIABLE is not None:
    import yaml
    lockfile = yaml.safe_load(open(pathlib.Path(__file__).parent / '../../CI/lockfile.yml'))['variables']

my_os = platform.system()

config_default = collections.OrderedDict(
    app={
        'java_cmd': 'java',
        'platformio_cmd': 'platformio',
        'cubemx_cmd': str(pathlib.Path(os.getenv('CUBEMX_CACHE_FOLDER')).joinpath('STM32CubeMX.exe'))
    } if CI_ENV_VARIABLE is not None else {
        # (default is OK) How do you start Java from the command line? (edit if Java not in PATH). Set to 'None'
        # (string) if in your setup the CubeMX can be invoked straightforwardly
        'java_cmd': 'java',

        # (default is OK) How do you start PlatformIO from the command line? (edit if not in PATH, if you use PlatformIO
        # IDE check https://docs.platformio.org/en/latest/installation.html#install-shell-commands)
        'platformio_cmd': 'platformio',

        # (default is OK) Trying to guess the STM32CubeMX location. STM actually had changed the installation path
        # several times already. Note that STM32CubeMX will be invoked as 'java -jar CUBEMX'
        'cubemx_cmd':
            # macOS default: 'Applications' folder
            "/Applications/STMicroelectronics/STM32CubeMX.app/Contents/Resources/STM32CubeMX" if my_os == 'Darwin' else
            # Linux (Ubuntu) default: home directory
            str(pathlib.Path.home().joinpath("cubemx/STM32CubeMX.exe")) if my_os == 'Linux' else
            # Windows default: Program Files
            "C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX.exe" if my_os == 'Windows' else None
    },
    project={
        # (default is OK) See CubeMX user manual PDF (UM1718) to get other useful options
        'cubemx_script_content': inspect.cleandoc('''
            config load ${ioc_file_absolute_path}
            generate code ${project_dir_absolute_path}
            exit
        ''') + '\n',

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
        ''') + '\n',

        # Runtime-determined values
        'board': '',
        'ioc_file': ''  # required, the file name (not a full path)
    }
)

config_file_name = 'stm32pio.ini'

# CubeMX 0 return code doesn't necessarily means the correct generation (e.g. migration dialog has appeared and 'Cancel'
# was chosen, or CubeMX_version < ioc_file_version, etc.), we should analyze the actual output (STDOUT)
cubemx_str_indicating_success = 'Code succesfully generated'
cubemx_str_indicating_error = '[ERROR]'

# Longest name (not necessarily a method so a little bit tricky...)
# log_fieldwidth_function = max([len(member) for member in dir(stm32pio.lib.Stm32pio)]) + 1
log_fieldwidth_function = 25 + 1
