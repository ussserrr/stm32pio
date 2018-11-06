import logging
import os
import shutil
import subprocess
import sys

import settings


logger = logging.getLogger('')


def generate_code(project_path):
    """
    Call STM32CubeMX app as a 'java -jar' file with the automatically prearranged 'cubemx-script' file

    Args:
        project_path: path to the project (folder with a .ioc file)
    """

    # Assuming the name of the '.ioc' file is the same as the project folder, we extract it from the given string
    project_name = os.path.basename(project_path)
    logger.debug(f"searching for {project_name}.ioc file...")
    cubemx_ioc_full_filename = os.path.join(project_path, f'{project_name}.ioc')
    if os.path.exists(cubemx_ioc_full_filename):
        logger.debug(f"{project_name}.ioc file was found")
    else:
        logger.error(f"there is no {project_name}.ioc file")
        sys.exit()

    # There should be correct 'cubemx-script' file, otherwise STM32CubeMX will fail
    logger.debug(f"searching for '{settings.cubemx_script_filename}' file...")
    cubemx_script_full_filename = os.path.join(project_path, settings.cubemx_script_filename)
    if not os.path.isfile(cubemx_script_full_filename):
        logger.debug(settings.cubemx_script_filename + " file wasn't found, creating one...")
        cubemx_script_text = settings.cubemx_script_text.format(project_path=project_path,
                                                                cubemx_ioc_full_filename=cubemx_ioc_full_filename)
        with open(cubemx_script_full_filename, 'w') as cubemx_script_file:
            cubemx_script_file.write(cubemx_script_text)
        logger.debug(f"'{settings.cubemx_script_filename}' file has been successfully created")
    else:
        logger.debug(f"'{settings.cubemx_script_filename}' file is already there")

    logger.info("starting to generate a code from the CubeMX .ioc file...")
    if logger.level <= logging.DEBUG:
        result = subprocess.run(['java', '-jar', settings.cubemx_path, '-q', cubemx_script_full_filename])
    else:
        result = subprocess.run(['java', '-jar', settings.cubemx_path, '-q', cubemx_script_full_filename],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Or, for Python 3.7 and above:
        # result = subprocess.run(['java', '-jar', settings.cubemx_path, '-q', cubemx_script_full_filename],
        #                         capture_output=True)
    if result.returncode != 0:
        logger.error(f"code generation error (return code is {result.returncode}).\n"
                     "Try to enable a verbose output or generate a code from the CubeMX itself.")
        sys.exit()
    else:
        logger.info("successful code generation")



def pio_init(project_path, board):
    """
    Call PlatformIO CLI to initialize a new project

    Args:
        project_path: path to the project (folder with a .ioc file)
        board: string displaying PlatformIO name of MCU/board (from 'pio boards' command)
    """

    # Check board name
    logger.debug("searching for PlatformIO' board...")
    result = subprocess.run(['platformio', 'boards'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
    # Or, for Python 3.7 and above:
    # result = subprocess.run(['platformio', 'boards'], capture_output=True, encoding='utf-8')
    if result.returncode != 0:
        logger.error("failed to start PlatformIO")
        sys.exit()
    else:
        if board not in result.stdout.split():
            logger.error("wrong STM32 board. Run 'pio boards' for possible names")
            sys.exit()

    logger.info("starting PlatformIO project initialization...")
    # 02.04.18: both versions work but second one is much more slower
    # 06.11.18: all versions have the same speed
    if logger.level <= logging.DEBUG:
        # result = subprocess.run(f"platformio init -d {project_path} -b {board} -O framework=stm32cube", shell=True)
        result = subprocess.run(['platformio', 'init', '-d', project_path, '-b', board, '-O', 'framework=stm32cube'])
    else:
        # result = subprocess.run(f"platformio init -d {project_path} -b {board} -O framework=stm32cube", shell=True,
        #                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result = subprocess.run(['platformio', 'init', '-d', project_path, '-b', board, '-O', 'framework=stm32cube',
                                 '--silent'])
        # Or, for Python 3.7 and above:
        # result = subprocess.run(['platformio', 'init', '-d', project_path, '-b', board, '-O', 'framework=stm32cube'],
        #                         capture_output=True)
    if result.returncode != 0:
        logger.error("PlatformIO project initialization error")
        sys.exit()
    else:
        logger.info("successful PlatformIO project initialization")



def patch_platformio_ini(project_path):
    """
    Patch platformio.ini file to use created earlier by CubeMX 'Src' and 'Inc' folders as sources

    Args:
        project_path: path to the project (folder with .ioc and platformio.ini files)
    """

    logger.debug("patching 'platformio.ini' file...")

    if settings.my_os in ['Darwin', 'Linux']:
        with open(f"{project_path}/platformio.ini", mode='a') as platformio_ini_file:
            platformio_ini_file.write(settings.platformio_ini_patch_text)

        shutil.rmtree(os.path.join(project_path, 'include'), ignore_errors=True)
        shutil.rmtree(os.path.join(project_path, 'src'), ignore_errors=True)

    # Windows
    else:
        logger.warning("Windows is not supported")

    logger.info("'platformio.ini' patched")



def start_editor(project_path, editor):
    """
    Start 'editor' with project at 'project_path' opened

    Args:
        project_path: path to the project
        editor: editor keyword
    """

    # TODO: handle errors if there is no editor

    logger.info("starting editor...")

    if editor == 'atom':
        subprocess.run(['atom', project_path])
    elif editor == 'vscode':
        subprocess.run(['code', project_path])
    elif editor == 'sublime':
        subprocess.run(['subl', project_path])



def clean(project_path):
    """
    Clean-up the project folder and preserve only a '.ioc' file

    Args:
        project_path: path to the project
    """

    folder_content = os.listdir(project_path)
    if (os.path.basename(project_path) + '.ioc') in folder_content:
        folder_content.remove(os.path.basename(project_path) + '.ioc')

    for item in folder_content:
        if os.path.isdir(os.path.join(project_path, item)):
            shutil.rmtree(os.path.join(project_path, item))
            logger.debug('del ./' + item)
        elif os.path.isfile(os.path.join(project_path, item)):
            os.remove(os.path.join(project_path, item))
            logger.debug('del ' + item)

    logger.info("project has been cleaned")
