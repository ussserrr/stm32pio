import sys, os, subprocess, logging
import settings


logger = logging.getLogger('')


def generate_code(path):
	projectName = path.split('/')[-1]
	cubemxIocFileFullName = '{path}/{projectName}.ioc'.format(path=path, projectName=projectName)
	if not os.path.exists(cubemxIocFileFullName):
		logger.error('there is no .ioc file')
		sys.exit()

	# There should be correct 'cubemx-script' file, otherwise STM32CubeMX will fail
	cubemxScriptFileFullName = '{path}/cubemx-script'.format(path=path)
	if not os.path.isfile(cubemxScriptFileFullName):
		cubemxScript = "config load {cubemxIocFileFullName}\n"\
					   "generate code {path}\n"\
					   "exit\n".format(path=path, cubemxIocFileFullName=cubemxIocFileFullName)
		cubemxScriptFile = open(cubemxScriptFileFullName, 'w')
		cubemxScriptFile.write(cubemxScript)
		cubemxScriptFile.close()

	logger.info("starting generate code from CubeMX' .ioc file...")
	rslt = subprocess.run(['java', '-jar', settings.cubemxPath,\
						   '-q', cubemxScriptFileFullName], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	if rslt.returncode != 0:
		logger.error('code generation error (return code is {returncode}). '\
					 'Try to enable verbose output or generate code from the CubeMX itself.'\
					 .format(returncode=rslt.returncode))
		sys.exit()
	else:
		logger.info('successful code generation')


def pio_init(path, board):
	# Check board name
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
	rslt = subprocess.run('platformio init -d {path} -b {board} --ide atom -O framework=stm32cube'\
						  .format(path=path, board=board), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
	# rslt = subprocess.run(['platformio', 'init', '-d', path, '-b', board, '--ide', 'atom', '-O', 'framework=stm32cube'],\
	# 					  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	if rslt.returncode != 0:
		logger.error('PlatformIO project initialization error')
		sys.exit()
	else:
		logger.info('successful PlatformIO project initialization')


def patch_platformio_ini(path):
	if settings.myOS in ['Darwin', 'Linux']:
		# Patch 'platformio.ini' to include source folders
		platformioIniFile = open('{path}/platformio.ini'.format(path=path), 'a')
		platformioIniFile.write('\n[platformio]\n'\
								  'include_dir = Inc\n'\
								  'src_dir = Src\n')
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

	logger.info("'platformio.ini' corrected")


def start_editor(path, editor):
	logger.info('starting editor...')

	if editor == 'atom':
		subprocess.run(['atom', path])
	elif editor == 'vscode':
		subprocess.run(['code', path])
