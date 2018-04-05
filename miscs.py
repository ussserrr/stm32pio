import sys, os, shutil, subprocess, logging
import settings


logger = logging.getLogger('')


def _getProjectNameByPath(path):
	return path.split('/')[-1]


def generate_code(path):
	"""
	Call STM32CubeMX as a 'java -jar' file with automatically prearranged 'cubemx-script' file

	Arguments:
		path: path to project (folder with .ioc file)
	"""

	logger.debug('searching for .ioc file...')
	projectName = _getProjectNameByPath(path)
	cubemxIocFullFilename = '{path}/{projectName}.ioc'.format(path=path, projectName=projectName)
	if not os.path.exists(cubemxIocFullFilename):
		logger.error('there is no .ioc file')
		sys.exit()
	logger.debug('.ioc file was found')

	# There should be correct 'cubemx-script' file, otherwise STM32CubeMX will fail
	logger.debug('checking {} file...'.format(settings.cubemxScriptFilename))
	cubemxScriptFullFilename = path + '/' + settings.cubemxScriptFilename
	if not os.path.isfile(cubemxScriptFullFilename):
		logger.debug(settings.cubemxScriptFilename + " file wasn't found, creating one...")
		cubemxScript = "config load {cubemxIocFullFilename}\n"\
					   "generate code {path}\n"\
					   "exit\n".format(path=path, cubemxIocFullFilename=cubemxIocFullFilename)
		cubemxScriptFile = open(cubemxScriptFullFilename, 'w')
		cubemxScriptFile.write(cubemxScript)
		cubemxScriptFile.close()
		logger.debug('cubemx-script file has been successfully created')
	else:
		logger.debug('cubemx-script file is already there')

	logger.info("starting generate code from CubeMX' .ioc file...")
	if logger.level <= logging.DEBUG:
		rslt = subprocess.run(['java', '-jar', settings.cubemxPath, '-q', cubemxScriptFullFilename])
	else:
		rslt = subprocess.run(['java', '-jar', settings.cubemxPath, '-q', cubemxScriptFullFilename],
							  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	if rslt.returncode != 0:
		logger.error('code generation error (return code is {returncode}). '\
					 'Try to enable verbose output or try to generate code from the CubeMX itself.'\
					 .format(returncode=rslt.returncode))
		sys.exit()
	else:
		logger.info('successful code generation')


def pio_init(path, board):
	"""
	Call PlatformIO CLI to initialize new project

	Arguments:
		path: path to project (folder with .ioc file)
		board: string displaying PlatformIO name of MCU/board (from 'pio boards' command)
	"""

	# Check board name
	logger.debug("searching for platformio' board...")
	rslt = subprocess.run(['platformio', 'boards'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	if rslt.returncode != 0:
		logger.error('failed to start PlatformIO')
		sys.exit()
	else:
		if board not in rslt.stdout.decode('utf-8').split():
			logger.error("wrong STM32 board. Run 'pio boards' for possible names")
			sys.exit()

	logger.info('starting PlatformIO project initialization...')
	# 02.04.18: both versions work but second is much more slower
	if logger.level <= logging.DEBUG:
		rslt = subprocess.run('platformio init -d {path} -b {board} -O framework=stm32cube'\
							  .format(path=path, board=board), shell=True)
	else:
		rslt = subprocess.run('platformio init -d {path} -b {board} -O framework=stm32cube'\
							  .format(path=path, board=board),  shell=True,
							  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	# rslt = subprocess.run(['platformio', 'init', '-d', path, '-b', board, '--ide',
	#						'atom', '-O', 'framework=stm32cube'],
	# 					    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	if rslt.returncode != 0:
		logger.error('PlatformIO project initialization error')
		sys.exit()
	else:
		logger.info('successful PlatformIO project initialization')


def patch_platformio_ini(path):
	"""
	Patch platformio.ini file to use created earlier by STM32CubeMX Src and Inc folders as sources

	Arguments:
		path: path to project (folder with .ioc and platformio.ini files)
	"""

	logger.debug('patching platformio.ini file...')
	if settings.myOS in ['Darwin', 'Linux']:
		# Patch 'platformio.ini' to include source folders
		platformioIniFile = open('{path}/platformio.ini'.format(path=path), 'a')
		platformioIniFile.write(settings.platformio_ini_patch)
		platformioIniFile.close()

		try:
			os.rmdir(path + '/' + 'inc')
		except Exception as e:
			pass

		try:
			os.rmdir(path + '/' + 'src')
		except Exception as e:
			pass

	# Windows
	else:
		pass

	logger.info("'platformio.ini' patched")


def start_editor(path, editor):
	"""
	Start 'editor' with project at 'path' opened

	Arguments:
		path: path to the project
		editor: editor' key
	"""

	logger.info('starting editor...')

	if editor == 'atom':
		subprocess.run(['atom', path])
	elif editor == 'vscode':
		subprocess.run(['code', path])


def clean(path):
	content = os.listdir(path)
	try:
		content.remove(_getProjectNameByPath(path)+'.ioc')
	except:
		pass
	# content = ['Src', 'src', 'Inc', 'inc', 'platformio.ini', settings.cubemxScriptFilename,
	#            '.pioenvs']
	for item in content:
		if os.path.isdir(path + '/' + item):
			shutil.rmtree(path + '/' + item)
			logger.debug('del ./' + item)
		elif os.path.isfile(path + '/' + item):
			os.remove(path + '/' + item)
			logger.debug('del ' + item)

	logger.info('project cleaned')
