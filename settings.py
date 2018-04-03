import platform, pathlib

myOS = platform.system()
homeDir = str(pathlib.Path.home())

if myOS == 'Darwin':
	cubemxPath = '/Applications/STMicroelectronics/STM32CubeMX.app/Contents/Resources/STM32CubeMX'
elif myOS == 'Linux':
	cubemxPath = '{homeDir}/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX'.format(homeDir=homeDir)
elif myOS == 'Windows':
	cubemxPath = '?'
