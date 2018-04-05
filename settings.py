import platform, pathlib

myOS = platform.system()
homeDir = str(pathlib.Path.home())

# we trying to guess STM32CubeMX path. You can just avoid this and hardcode it

# macOS default: Applications folder
if myOS == 'Darwin':
	cubemxPath = '/Applications/STMicroelectronics/STM32CubeMX.app/Contents/Resources/STM32CubeMX'

# not exactly default STM32CubeMX path on Linux but general convention on it
elif myOS == 'Linux':
	cubemxPath = '{homeDir}/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX'.format(homeDir=homeDir)

# Windows not implemented yet
elif myOS == 'Windows':
	cubemxPath = '?'


cubemxScriptFilename = 'cubemx-script'

platformio_ini_patch = '\n[platformio]\n'\
						 'include_dir = Inc\n'\
						 'src_dir = Src\n'
