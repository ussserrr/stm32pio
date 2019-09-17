import logging
import pathlib
import shutil
import subprocess

import settings

logger = logging.getLogger()



def _get_project_path(dirty_path):
    """
    Handle '/path/to/proj' and '/path/to/proj/', . (current directory) and other cases

    Args:
        dirty_path: some filesystem path
    """
    correct_path = pathlib.Path(dirty_path).resolve()
    if not correct_path.exists():
        logger.error("incorrect project path")
        raise FileNotFoundError(correct_path)
    else:
        return correct_path



def generate_code(dirty_path):
    """
    Call STM32CubeMX app as a 'java -jar' file with the automatically prearranged 'cubemx-script' file

    Args:
        dirty_path: path to the project (folder with a .ioc file)
    """

    project_path = _get_project_path(dirty_path)

    # Assuming the name of the '.ioc' file is the same as the project folder, we extract it from the given string
    project_name = project_path.name
    logger.debug(f"searching for {project_name}.ioc file...")
    cubemx_ioc_full_filename = project_path.joinpath(f'{project_name}.ioc')
    if cubemx_ioc_full_filename.exists():
        logger.debug(f"{project_name}.ioc file was found")
    else:
        logger.error(f"there is no {project_name}.ioc file")
        raise FileNotFoundError(cubemx_ioc_full_filename)

    # Find/create 'cubemx-script' file
    logger.debug(f"searching for '{settings.cubemx_script_filename}' file...")
    cubemx_script_full_filename = project_path.joinpath(settings.cubemx_script_filename)
    if not cubemx_script_full_filename.is_file():
        logger.debug(f"'{settings.cubemx_script_filename}' file wasn't found, creating one...")
        cubemx_script_content = settings.cubemx_script_content.format(project_path=project_path,
                                                                      cubemx_ioc_full_filename=cubemx_ioc_full_filename)
        cubemx_script_full_filename.write_text(cubemx_script_content)
        logger.debug(f"'{settings.cubemx_script_filename}' file has been successfully created")
    else:
        logger.debug(f"'{settings.cubemx_script_filename}' file is already there")

    logger.info("starting to generate a code from the CubeMX .ioc file...")
    command_arr = [settings.java_cmd, '-jar', settings.cubemx_path, '-q', str(cubemx_script_full_filename)]
    if logger.level <= logging.DEBUG:
        result = subprocess.run(command_arr)
    else:
        result = subprocess.run(command_arr, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Or, for Python 3.7 and above:
        # result = subprocess.run(command_arr, capture_output=True)
    if result.returncode == 0:
        logger.info("successful code generation")
    else:
        logger.error(f"code generation error (CubeMX return code is {result.returncode}).\n"
                     "Try to enable a verbose output or generate a code from the CubeMX itself.")
        raise Exception("code generation error")


def pio_init(dirty_path, board):
    """
    Call PlatformIO CLI to initialize a new project

    Args:
        dirty_path: path to the project (folder with a .ioc file)
        board: string displaying PlatformIO name of MCU/board (from 'pio boards' command)
    """

    project_path = _get_project_path(dirty_path)

    # Check board name
    logger.debug("searching for PlatformIO board...")
    result = subprocess.run([settings.platformio_cmd, 'boards'], encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Or, for Python 3.7 and above:
    # result = subprocess.run(['platformio', 'boards'], encoding='utf-8', capture_output=True)
    if result.returncode == 0:
        if board not in result.stdout.split():
            logger.error("wrong STM32 board. Run 'platformio boards' for possible names")
            raise Exception("wrong STM32 board")
    else:
        logger.error("failed to start PlatformIO")
        raise Exception("failed to start PlatformIO")

    logger.info("starting PlatformIO project initialization...")
    command_arr = [settings.platformio_cmd, 'init', '-d', str(project_path), '-b', board, '-O', 'framework=stm32cube']
    if logger.level > logging.DEBUG:
        command_arr.append('--silent')
    result = subprocess.run(command_arr)
    if result.returncode == 0:
        logger.info("successful PlatformIO project initialization")
    else:
        logger.error("PlatformIO project initialization error")
        raise Exception("PlatformIO error")



def patch_platformio_ini(dirty_path):
    """
    Patch platformio.ini file to use created earlier by CubeMX 'Src' and 'Inc' folders as sources

    Args:
        dirty_path: path to the project (folder with .ioc and platformio.ini files)
    """

    project_path = _get_project_path(dirty_path)

    logger.debug("patching 'platformio.ini' file...")

    platformio_ini_file = project_path.joinpath('platformio.ini')
    if platformio_ini_file.is_file():
        with platformio_ini_file.open(mode='a') as f:
            f.write(settings.platformio_ini_patch_content)
        logger.info("'platformio.ini' patched")
    else:
        logger.warning("'platformio.ini' file not found")

    shutil.rmtree(str(project_path.joinpath('include')), ignore_errors=True)
    if not project_path.joinpath('SRC').is_dir():  # case sensitive file system
        shutil.rmtree(str(project_path.joinpath('src')), ignore_errors=True)



def start_editor(dirty_path, editor_command):
    """
    Start 'editor' with project at 'project_path' opened

    Args:
        dirty_path: path to the project
        editor: editor keyword
    """

    project_path = _get_project_path(dirty_path)

    logger.info("starting an editor...")

    try:
        if settings.my_os == 'Windows':
            subprocess.run([editor_command, str(project_path)], check=True, shell=True)
        else:
            subprocess.run([editor_command, str(project_path)], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start the editor {editor_command}: {e.stderr}")



def pio_build(dirty_path):
    """
    Initiate a build of the PlatformIO project by the PlatformIO ('run' command)

    Args:
        dirty_path: path to the project
    Returns:
        0 if success, raise an exception otherwise
    """

    project_path = _get_project_path(dirty_path)

    logger.info("starting PlatformIO build...")
    command_arr = [settings.platformio_cmd, 'run', '-d', str(project_path)]
    if logger.level > logging.DEBUG:
        command_arr.append('--silent')
    result = subprocess.run(command_arr)
    if result.returncode == 0:
        logger.info("successful PlatformIO build")
        return result.returncode
    else:
        logger.error("PlatformIO build error")
        raise Exception("PlatformIO build error")



def clean(dirty_path):
    """
    Clean-up the project folder and preserve only an '.ioc' file

    Args:
        dirty_path: path to the project
    """

    project_path = _get_project_path(dirty_path)

    for child in project_path.iterdir():
        if child.name != f"{project_path.name}.ioc":
            if child.is_dir():
                shutil.rmtree(str(child), ignore_errors=True)
                logger.debug(f"del {child}/")
            elif child.is_file():
                child.unlink()
                logger.debug(f"del {child}")

    logger.info("project has been cleaned")
