import logging
import pathlib
import platform
import sys


my_os = platform.system()
home_dir = str(pathlib.Path.home())

logger = logging.getLogger('')


# We trying to guess STM32CubeMX path. You can just avoid this and hard-code it

# macOS default: 'Applications' folder
if my_os == 'Darwin':
    cubemx_path = "/Applications/STMicroelectronics/STM32CubeMX.app/Contents/Resources/STM32CubeMX"
# not exactly default STM32CubeMX path on Linux but general convention on it
elif my_os == 'Linux':
    cubemx_path = "/usr/local/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX"
# Windows is not implemented yet
elif my_os == 'Windows':
	cubemx_path = "C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX.exe"
    # logger.error("Windows is not supported!")
    # sys.exit()

cubemx_script_filename = 'cubemx-script'

cubemx_script_text = "config load {cubemx_ioc_full_filename}\n" \
                     "generate code {project_path}\n" \
                     "exit\n"

platformio_ini_patch_text = "\n[platformio]\n" \
                            "include_dir = Inc\n" \
                            "src_dir = Src\n"
