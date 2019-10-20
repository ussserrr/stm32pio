import logging
import pathlib
import shutil
import subprocess
# import enum

import stm32pio.settings

logger = logging.getLogger()



# TODO: add states and check the current state for every operation (so we can't, for example, go to build stage without
#  a pio_init performed before). Also, it naturally helps us to construct the GUI in which we manage the list of
#  multiple projects. (use enum for this)
#  Also, we would probably need some method to detect a current project state on program start (or store it explicitly
#  in the dotted system file)
# @enum.unique
# class ProjectState(enum.Enum):
#     """
#     """
#
#     INITIALIZED = enum.auto()
#     GENERATED = enum.auto()
#     PIO_INITIALIZED = enum.auto()
#     PIO_INI_PATCHED = enum.auto()
#     BUILT = enum.auto()
#
#     ERROR = enum.auto()


class Stm32pio:
    """
    Main class
    """

    def __init__(self, dirty_path: str):
        self.project_path = self._resolve_project_path(dirty_path)


    @staticmethod
    def _resolve_project_path(dirty_path: str) -> pathlib.Path:
        """
        Handle 'path/to/proj' and 'path/to/proj/', '.' (current directory) and other cases

        Args:
            dirty_path: some directory in the filesystem
        """
        correct_path = pathlib.Path(dirty_path).expanduser().resolve()
        if not correct_path.exists():
            logger.error("incorrect project path")
            raise FileNotFoundError(correct_path)
        else:
            return correct_path


    def generate_code(self) -> None:
        """
        Call STM32CubeMX app as a 'java -jar' file with the automatically prearranged 'cubemx-script' file
        """

        # Assuming the name of the '.ioc' file is the same as the project folder, we extract it from the given string
        project_name = self.project_path.name
        logger.debug(f"searching for {project_name}.ioc file...")
        cubemx_ioc_full_filename = self.project_path.joinpath(f'{project_name}.ioc')
        if cubemx_ioc_full_filename.exists():
            logger.debug(f"{project_name}.ioc file was found")
        else:
            logger.error(f"there is no {project_name}.ioc file")
            raise FileNotFoundError(cubemx_ioc_full_filename)

        # Find/create 'cubemx-script' file
        logger.debug(f"searching for '{stm32pio.settings.cubemx_script_filename}' file...")
        cubemx_script_full_filename = self.project_path.joinpath(stm32pio.settings.cubemx_script_filename)
        if not cubemx_script_full_filename.is_file():
            logger.debug(f"'{stm32pio.settings.cubemx_script_filename}' file wasn't found, creating one...")
            cubemx_script_content = stm32pio.settings.cubemx_script_content.format(
                project_path=self.project_path, cubemx_ioc_full_filename=cubemx_ioc_full_filename)
            cubemx_script_full_filename.write_text(cubemx_script_content)
            logger.debug(f"'{stm32pio.settings.cubemx_script_filename}' file has been successfully created")
        else:
            logger.debug(f"'{stm32pio.settings.cubemx_script_filename}' file is already there")

        logger.info("starting to generate a code from the CubeMX .ioc file...")
        command_arr = [stm32pio.settings.java_cmd, '-jar', stm32pio.settings.cubemx_path, '-q',
                       str(cubemx_script_full_filename)]
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


    def pio_init(self, board: str) -> None:
        """
        Call PlatformIO CLI to initialize a new project

        Args:
            board: string displaying PlatformIO name of MCU/board (from 'pio boards' command)
        """

        # Check board name
        logger.debug("searching for PlatformIO board...")
        result = subprocess.run([stm32pio.settings.platformio_cmd, 'boards'], encoding='utf-8',
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
        command_arr = [stm32pio.settings.platformio_cmd, 'init', '-d', str(self.project_path), '-b', board,
                       '-O', 'framework=stm32cube']
        if logger.level > logging.DEBUG:
            command_arr.append('--silent')
        result = subprocess.run(command_arr)
        if result.returncode == 0:
            logger.info("successful PlatformIO project initialization")
        else:
            logger.error("PlatformIO project initialization error")
            raise Exception("PlatformIO error")


    def patch_platformio_ini(self) -> None:
        """
        Patch platformio.ini file to use created earlier by CubeMX 'Src' and 'Inc' folders as sources
        """

        logger.debug("patching 'platformio.ini' file...")

        platformio_ini_file = self.project_path.joinpath('platformio.ini')
        if platformio_ini_file.is_file():
            with platformio_ini_file.open(mode='a') as f:
                f.write(stm32pio.settings.platformio_ini_patch_content)
            logger.info("'platformio.ini' patched")
        else:
            logger.warning("'platformio.ini' file not found")

        shutil.rmtree(str(self.project_path.joinpath('include')), ignore_errors=True)
        if not self.project_path.joinpath('SRC').is_dir():  # case sensitive file system
            shutil.rmtree(str(self.project_path.joinpath('src')), ignore_errors=True)


    def start_editor(self, editor_command: str) -> None:
        """
        Start the editor specified by 'editor_command' with the project opened

        Args:
            editor_command: editor command (as we start in the terminal)
        """

        logger.info("starting an editor...")

        try:
            subprocess.run([editor_command, str(self.project_path)], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start the editor {editor_command}: {e.stderr}")


    def pio_build(self) -> int:
        """
        Initiate a build of the PlatformIO project by the PlatformIO ('run' command)

        Returns:
            0 if success, raise an exception otherwise
        """

        if self.project_path.joinpath('platformio.ini').is_file():
            logger.info("starting PlatformIO build...")
        else:
            logger.error("no 'platformio.ini' file, build is impossible")
            return -1

        command_arr = [stm32pio.settings.platformio_cmd, 'run', '-d', str(self.project_path)]
        if logger.level > logging.DEBUG:
            command_arr.append('--silent')
        result = subprocess.run(command_arr)
        if result.returncode == 0:
            logger.info("successful PlatformIO build")
            return result.returncode
        else:
            logger.error("PlatformIO build error")
            raise Exception("PlatformIO build error")


    def clean(self) -> None:
        """
        Clean-up the project folder and preserve only an '.ioc' file
        """

        for child in self.project_path.iterdir():
            if child.name != f"{self.project_path.name}.ioc":
                if child.is_dir():
                    shutil.rmtree(str(child), ignore_errors=True)
                    logger.debug(f"del {child}/")
                elif child.is_file():
                    child.unlink()
                    logger.debug(f"del {child}")

        logger.info("project has been cleaned")
