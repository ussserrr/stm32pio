# TODO: how we will be set these parameters if the app will be run after the 'setup' process? Or even obtained by 'pip'?
#  Maybe we should describe the config file to the user instead of this Python source.

import platform
import pathlib
import string


my_os = platform.system()

# (default is OK) How do you start Java from the command line? (edit if Java not in PATH)
java_cmd = 'java'

# (default is OK) How do you start PlatformIO from the command line? (edit if not in PATH, check
# https://docs.platformio.org/en/latest/installation.html#install-shell-commands)
platformio_cmd = 'platformio'

# (default is OK) We trying to guess STM32CubeMX location. You can just avoid this and hard-code it.
# Note that STM32CubeMX will be invoked as 'java -jar CUBEMX'
# macOS default: 'Applications' folder
if my_os == 'Darwin':
    cubemx_path = "/Applications/STMicroelectronics/STM32CubeMX.app/Contents/Resources/STM32CubeMX"
# Linux (Ubuntu) default:
elif my_os == 'Linux':
    cubemx_path = pathlib.Path.home().joinpath("STM32CubeMX/STM32CubeMX")
# Windows default:
elif my_os == 'Windows':
    cubemx_path = "C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX.exe"

# (default is OK) choose a file name in which we store the CubeMX script
cubemx_script_filename = 'cubemx-script'

# (default is OK) see CubeMX user manual PDF to see other useful options
cubemx_script_content = string.Template('''\
config load $cubemx_ioc_full_filename
generate code $project_path
exit
''')

# (default is OK)
platformio_ini_patch_content = '''\
[platformio]
include_dir = Inc
src_dir = Src
'''
