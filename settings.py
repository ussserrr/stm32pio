import logging
import pathlib
import platform


my_os = platform.system()
home_dir = str(pathlib.Path.home())

logger = logging.getLogger('')


# How you start Java from command line?
java_cmd = 'java'

# We trying to guess STM32CubeMX location. You can just avoid this and hard-code it. Note that STM32CubeMX will be
# called as 'java -jar'
# macOS default: 'Applications' folder
if my_os == 'Darwin':
    cubemx_path = "/Applications/STMicroelectronics/STM32CubeMX.app/Contents/Resources/STM32CubeMX"
# Linux (Ubuntu) default:
elif my_os == 'Linux':
    cubemx_path = "/usr/local/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX"
# Windows default:
elif my_os == 'Windows':
    cubemx_path = "C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX.exe"

cubemx_script_filename = 'cubemx-script'

cubemx_script_text = "config load {cubemx_ioc_full_filename}\n" \
                     "generate code {project_path}\n" \
                     "exit\n"

platformio_ini_patch_text = "\n[platformio]\n" \
                            "include_dir = Inc\n" \
                            "src_dir = Src\n"
