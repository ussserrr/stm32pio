import collections
import inspect
import pathlib
import platform


my_os = platform.system()

config_default = collections.OrderedDict(
    app={
        # (default is OK) How do you start Java from the command line? (edit if Java not in PATH)
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
            pathlib.Path.home().joinpath("STM32CubeMX/STM32CubeMX") if my_os == 'Linux' else
            # Windows default: Program Files
            "C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX.exe" if my_os == 'Windows' else None
    },
    project={
        # (default is OK) See CubeMX user manual PDF (UM1718) to get other useful options
        'cubemx_script_content': "config load $cubemx_ioc_full_filename\ngenerate code $project_path\nexit",

        # Override the defaults to comply with CubeMX project structure. This should meet INI-style requirements. You
        # can include existing sections, too (e.g.
        #   [env:nucleo_f031k6]
        #   key=value
        # will add a 'key' parameter)
        'platformio_ini_patch_content': inspect.cleandoc('''
            [platformio]
            include_dir = Inc
            src_dir = Src
        ''') + '\n'
    }
)

config_file_name = 'stm32pio.ini'

log_function_fieldwidth = 26
