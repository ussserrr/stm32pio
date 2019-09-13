import platform


my_os = platform.system()

# (default is OK) How do you start Java from command line? (edit if Java not in PATH)
java_cmd = 'java'

# (default is OK) We trying to guess STM32CubeMX location. You can just avoid this and hard-code it.
# Note that STM32CubeMX will be invoked as 'java -jar CUBEMX'
# macOS default: 'Applications' folder
if my_os == 'Darwin':
    cubemx_path = "/Applications/STMicroelectronics/STM32CubeMX.app/Contents/Resources/STM32CubeMX"
# Linux (Ubuntu) default:
elif my_os == 'Linux':
    cubemx_path = "/usr/local/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX"
# Windows default:
elif my_os == 'Windows':
    cubemx_path = "C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX.exe"

# (default is OK) choose a file name in which we store the CubeMX script
cubemx_script_filename = 'cubemx-script'

# (default is OK) see CubeMX user manual PDF to see other useful options
cubemx_script_text = "config load {cubemx_ioc_full_filename}\n" \
                     "generate code {project_path}\n" \
                     "exit\n"

# (default is OK)
platformio_ini_patch_text = "\n[platformio]\n" \
                            "include_dir = Inc\n" \
                            "src_dir = Src\n"
