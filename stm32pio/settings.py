import platform
import pathlib
import collections


my_os = platform.system()

config_default = collections.OrderedDict(
    app={
        # (default is OK) How do you start Java from the command line? (edit if Java not in PATH)
        'java_cmd': 'java',

        # (default is OK) How do you start PlatformIO from the command line? (edit if not in PATH, check
        # https://docs.platformio.org/en/latest/installation.html#install-shell-commands)
        'platformio_cmd': 'platformio',

        # (default is OK) We trying to guess STM32CubeMX location. You can just avoid this and hard-code it.
        # Note that STM32CubeMX will be invoked as 'java -jar CUBEMX'
        'cubemx_cmd':
            # macOS default: 'Applications' folder
            "/Applications/STMicroelectronics/STM32CubeMX.app/Contents/Resources/STM32CubeMX" if my_os == 'Darwin' else
            # Linux (Ubuntu) default:
            pathlib.Path.home().joinpath("STM32CubeMX/STM32CubeMX") if my_os == 'Linux' else
            # Windows default:
            "C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX.exe" if my_os == 'Windows' else None
    },
    project={
        # (default is OK) see CubeMX user manual PDF to get other useful options
        'cubemx_script_content': "config load $cubemx_ioc_full_filename\ngenerate code $project_path\nexit",

        # override the defaults to comply with CubeMX project structure
        'platformio_ini_patch_content': "[platformio]\ninclude_dir = Inc\nsrc_dir = Src\n"
    }
)
