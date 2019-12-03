"""
Main library
"""

import collections
import logging
import pathlib
import shutil
import subprocess
import enum
import configparser
import string
import sys
import tempfile
import traceback
import weakref

import stm32pio.settings

# Child logger
logger = logging.getLogger('stm32pio.util')


@enum.unique
class ProjectState(enum.IntEnum):
    """
    Codes indicating a project state at the moment. Should be the sequence of incrementing integers to be suited for
    state determining algorithm

    Hint: Files/folders to be present on every project state:
        UNDEFINED: use this state to indicate none of the states below. Also, when we do not have any .ioc file the
                   Stm32pio class cannot be instantiated (constructor raises an exception)
        INITIALIZED: ['project.ioc', 'stm32pio.ini']
        GENERATED: ['Inc', 'Src', 'project.ioc', 'stm32pio.ini']
        PIO_INITIALIZED (on case-sensitive FS): ['test', 'include', 'Inc', 'platformio.ini', '.gitignore', 'Src', 'lib',
                                                 'project.ioc', '.travis.yml', 'src']
        PIO_INI_PATCHED: ['test', 'Inc', 'platformio.ini', '.gitignore', 'Src', 'lib', 'project.ioc', '.travis.yml']
        BUILT: same as above + '.pio' folder with build artifacts (such as .pio/build/nucleo_f031k6/firmware.bin,
                                                                           .pio/build/nucleo_f031k6/firmware.elf)
    """
    UNDEFINED = enum.auto()
    INITIALIZED = enum.auto()
    GENERATED = enum.auto()
    PIO_INITIALIZED = enum.auto()
    PIO_INI_PATCHED = enum.auto()
    BUILT = enum.auto()


class Stm32pio:
    """
    Main class.

    Represents a single project, encapsulating file system path to the project (main mandatory identifier) and some
    parameters in a configparser .ini file. As stm32pio can be installed via pip and has no global config we also
    storing global parameters (such as Java or STM32CubeMX invoking commands) in this config .ini file so the user can
    specify settings on a per-project base. The config can be saved in a non-disturbing way automatically on the
    instance destruction (e.g. by garbage collecting it) (use save_on_destruction=True flag), otherwise user should
    explicitly save the config if he wants to (using save_config() method).

    The typical life cycle consists of project creation, passing mandatory 'dirty_path' argument. If also 'parameters'
    dictionary is specified also these settings are processed (white-list approach is used so we set only those
    parameters that are listed in the constructor code) (currently only 'board' parameter is included). Then it is
    possible to perform API operations. WARNING. Please be careful with the 'clean' method as it deletes all the content
    of the project directory except the main .ioc file.

    Args:
        dirty_path (str): path to the project
        parameters (dict): additional parameters to set on initialization stage
        save_on_destruction (bool): register or not the finalizer that saves the config to file
    """

    def __init__(self, dirty_path: str, parameters: dict = None, save_on_destruction: bool = True):
        if parameters is None:
            parameters = {}

        self.project_path = self._resolve_project_path(dirty_path)
        self.config = self._load_settings_file()

        ioc_file = self._find_ioc_file()
        self.config.set('project', 'ioc_file', str(ioc_file))

        cubemx_script_template = string.Template(self.config.get('project', 'cubemx_script_content'))
        cubemx_script_content = cubemx_script_template.substitute(project_path=self.project_path,
            cubemx_ioc_full_filename=self.config.get('project', 'ioc_file'))
        self.config.set('project', 'cubemx_script_content', cubemx_script_content)

        board = ''
        if 'board' in parameters and parameters['board'] is not None:
            try:
                board = self._resolve_board(parameters['board'])
            except Exception as e:
                logger.warning(e)
            self.config.set('project', 'board', board)
        elif self.config.get('project', 'board', fallback=None) is None:
            self.config.set('project', 'board', board)

        if save_on_destruction:
            self._finalizer = weakref.finalize(self, self.save_config)


    def save_config(self) -> int:
        """
        Tries to save the configparser config to file and gently log if error occurs
        """

        try:
            with self.project_path.joinpath(stm32pio.settings.config_file_name).open(mode='w') as config_file:
                self.config.write(config_file)
            logger.debug("stm32pio.ini config file has been saved")
            return 0
        except Exception as e:
            logger.warning(f"cannot save config: {e}")
            if logger.getEffectiveLevel() <= logging.DEBUG:
                traceback.print_exception(*sys.exc_info())
            return -1


    @property
    def state(self) -> ProjectState:
        """
        Property returning the current state of the project. Calculated at every request.
        """

        logger.debug("calculating the project state...")
        logger.debug(f"project content: {[item.name for item in self.project_path.iterdir()]}")

        # Fill the ordered dictionary with conditions results
        states_conditions = collections.OrderedDict()
        states_conditions[ProjectState.UNDEFINED] = [True]
        states_conditions[ProjectState.INITIALIZED] = [
            self.project_path.joinpath(stm32pio.settings.config_file_name).is_file()]
        states_conditions[ProjectState.GENERATED] = [self.project_path.joinpath('Inc').is_dir() and
                                                     len(list(self.project_path.joinpath('Inc').iterdir())) > 0,
                                                     self.project_path.joinpath('Src').is_dir() and
                                                     len(list(self.project_path.joinpath('Src').iterdir())) > 0]
        states_conditions[ProjectState.PIO_INITIALIZED] = [
            self.project_path.joinpath('platformio.ini').is_file() and
            len(self.project_path.joinpath('platformio.ini').read_text()) > 0]
        states_conditions[ProjectState.PIO_INI_PATCHED] = [
            self.project_path.joinpath('platformio.ini').is_file() and
            self.config.get('project', 'platformio_ini_patch_content') in
            self.project_path.joinpath('platformio.ini').read_text(),
            not self.project_path.joinpath('include').is_dir()]
        states_conditions[ProjectState.BUILT] = [
            self.project_path.joinpath('.pio').is_dir() and
            any([item.is_file() for item in self.project_path.joinpath('.pio').rglob('*firmware*')])]

        # Use (1,0) instead of (True,False) because on debug printing it looks better
        conditions_results = []
        for state, conditions in states_conditions.items():
            conditions_results.append(1 if all(condition is True for condition in conditions) else 0)

        # Put away unnecessary processing as the string still will be formed even if the logging level doesn't allow
        # propagation of this message
        if logger.getEffectiveLevel() <= logging.DEBUG:
            states_info_str = '\n'.join(f"{state.name:20}{conditions_results[state.value-1]}" for state in ProjectState)
            logger.debug(f"determined states:\n{states_info_str}")

        # Search for a consecutive raw of 1's and find the last of them. For example, if the array is
        #   [1,1,0,1,0,0]
        #      ^
        last_true_index = 0  # UNDEFINED is always True, use as a start value
        for index, value in enumerate(conditions_results):
            if value == 1:
                last_true_index = index
            else:
                break

        # Fall back to the UNDEFINED state if we have breaks in conditions results array. For example, in [1,1,0,1,0,0]
        # we still return UNDEFINED as it doesn't look like a correct combination of files actually
        project_state = ProjectState.UNDEFINED
        if 1 not in conditions_results[last_true_index + 1:]:
            project_state = ProjectState(last_true_index + 1)

        return project_state


    def _find_ioc_file(self) -> pathlib.Path:
        """
        Find and return an .ioc file. If there are more than one, return first. If no .ioc file is present raise
        FileNotFoundError exception
        """

        ioc_file = self.config.get('project', 'ioc_file', fallback=None)
        if ioc_file:
            return pathlib.Path(ioc_file).resolve()
        else:
            logger.debug("searching for any .ioc file...")
            candidates = list(self.project_path.glob('*.ioc'))
            if len(candidates) == 0:
                raise FileNotFoundError("Not found: CubeMX project .ioc file")
            elif len(candidates) == 1:
                logger.debug(f"{candidates[0].name} is selected")
                return candidates[0]
            else:
                logger.warning(f"there are multiple .ioc files, {candidates[0].name} is selected")
                return candidates[0]


    def _load_settings_file(self) -> configparser.ConfigParser:
        """
        Prepare configparser config for the project. First, read the default config and then mask these values with user
        ones
        """

        logger.debug(f"searching for {stm32pio.settings.config_file_name}...")
        stm32pio_ini = self.project_path.joinpath(stm32pio.settings.config_file_name)

        config = configparser.ConfigParser()

        # Fill with default values
        config.read_dict(stm32pio.settings.config_default)
        # Then override by user values (if exist)
        config.read(str(stm32pio_ini))

        # Put away unnecessary processing as the string still will be formed even if the logging level doesn't allow
        # propagation of this message
        if logger.getEffectiveLevel() <= logging.DEBUG:
            debug_str = 'resolved config:'
            for section in config.sections():
                debug_str += f"\n=========== {section} ===========\n"
                for value in config.items(section):
                    debug_str += f"{value}\n"
            logger.debug(debug_str)

        return config


    @staticmethod
    def _resolve_project_path(dirty_path: str) -> pathlib.Path:
        """
        Handle 'path/to/proj' and 'path/to/proj/', '.' (current directory) and other cases

        Args:
            dirty_path (str): some directory in the filesystem
        """
        resolved_path = pathlib.Path(dirty_path).expanduser().resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"not found: {resolved_path}")
        else:
            return resolved_path


    def _resolve_board(self, board: str) -> str:
        """
        Check if given board is a correct board name in the PlatformIO database

        Returns:
            same board that has been given, raise an exception otherwise
        """

        logger.debug("searching for PlatformIO board...")
        result = subprocess.run([self.config.get('app', 'platformio_cmd'), 'boards'], encoding='utf-8',
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Or, for Python 3.7 and above:
        # result = subprocess.run(['platformio', 'boards'], encoding='utf-8', capture_output=True)
        if result.returncode == 0:
            if board not in result.stdout.split():
                raise Exception("wrong PlatformIO STM32 board. Run 'platformio boards' for possible names")
            else:
                logger.debug(f"PlatformIO board {board} was found")
                return board
        else:
            raise Exception("failed to search for PlatformIO boards")


    def generate_code(self) -> None:
        """
        Call STM32CubeMX app as a 'java -jar' file to generate the code from the .ioc file. Pass commands to the
        STM32CubeMX in a temp file
        """

        # Use mkstemp() instead of higher-level API for compatibility with Windows (see tempfile docs for more details)
        cubemx_script_file, cubemx_script_name = tempfile.mkstemp()

        # buffering=0 leads to the immediate flushing on writing
        with open(cubemx_script_file, mode='w+b', buffering=0) as cubemx_script:
            cubemx_script.write(self.config.get('project', 'cubemx_script_content').encode())  # encode since mode='w+b'

            logger.info("starting to generate a code from the CubeMX .ioc file...")
            command_arr = [self.config.get('app', 'java_cmd'), '-jar', self.config.get('app', 'cubemx_cmd'), '-q',
                           cubemx_script_name, '-s']  # -q: read commands from file, -s: silent performance
            if logger.getEffectiveLevel() <= logging.DEBUG:
                result = subprocess.run(command_arr)
            else:
                result = subprocess.run(command_arr, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # Or, for Python 3.7 and above:
                # result = subprocess.run(command_arr, capture_output=True)
            if result.returncode == 0:
                logger.info("successful code generation")
            else:
                logger.error(f"code generation error (CubeMX return code is {result.returncode}).\n"
                             "Enable a verbose output or try to generate a code from the CubeMX itself.")
                raise Exception("code generation error")

        pathlib.Path(cubemx_script_name).unlink()


    def pio_init(self) -> int:
        """
        Call PlatformIO CLI to initialize a new project. It uses parameters (path, board) collected before so the
        confirmation of the data presence is on a user
        """

        logger.info("starting PlatformIO project initialization...")

        # TODO: check whether there is already a platformio.ini file and warn in this case

        # TODO: move out to config a 'framework' option and to settings a 'platformio.ini' file name
        command_arr = [self.config.get('app', 'platformio_cmd'), 'init', '-d', str(self.project_path), '-b',
                       self.config.get('project', 'board'), '-O', 'framework=stm32cube']
        if logger.getEffectiveLevel() > logging.DEBUG:
            command_arr.append('--silent')

        result = subprocess.run(command_arr, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        error_msg = "PlatformIO project initialization error"
        if result.returncode == 0:
            # PlatformIO returns 0 even on some errors (e.g. no '--board' argument)
            for output in [result.stdout, result.stderr]:
                if 'ERROR' in output.upper():
                    logger.error(output)
                    raise Exception(error_msg)
            logger.info("successful PlatformIO project initialization")
            return result.returncode
        else:
            raise Exception(error_msg)


    def patch(self) -> None:
        """
        Patch platformio.ini file to use created earlier by CubeMX 'Src' and 'Inc' folders as sources
        """

        logger.debug("patching 'platformio.ini' file...")

        platformio_ini_file = self.project_path.joinpath('platformio.ini')
        if platformio_ini_file.is_file():
            with platformio_ini_file.open(mode='a') as f:
                # TODO: check whether there is already a patched platformio.ini file, warn in this case and do not proceed
                f.write(self.config.get('project', 'platformio_ini_patch_content'))
            logger.info("'platformio.ini' has been patched")
        else:
            raise Exception("'platformio.ini' file not found, the project cannot be patched successfully")

        shutil.rmtree(self.project_path.joinpath('include'), ignore_errors=True)

        if not self.project_path.joinpath('SRC').is_dir():  # check for case sensitive file system
            shutil.rmtree(self.project_path.joinpath('src'), ignore_errors=True)


    def start_editor(self, editor_command: str) -> int:
        """
        Start the editor specified by 'editor_command' with the project opened

        Args:
            editor_command: editor command as we start it in the terminal. Note that only single-word command is
            currently supported

        Returns:
            return code of the editor on success, -1 otherwise
        """

        logger.info(f"starting an editor '{editor_command}'...")

        try:
            # result = subprocess.run([editor_command, str(self.project_path)], check=True)
            # TODO: need to clarify
            result = subprocess.run(f"{editor_command} {str(self.project_path)}", check=True, shell=True)
            return result.returncode if result.returncode != -1 else 0
        except subprocess.CalledProcessError as e:
            logger.error(f"failed to start the editor {editor_command}: {e.stderr}")
            return -1


    def pio_build(self) -> int:
        """
        Initiate a build of the PlatformIO project by the PlatformIO ('run' command). PlatformIO prints error message
        by itself to the STDERR so there is a no need to catch it and outputs by us

        Returns:
            0 if success, raise an exception otherwise
        """

        command_arr = [self.config.get('app', 'platformio_cmd'), 'run', '-d', str(self.project_path)]
        if logger.getEffectiveLevel() > logging.DEBUG:
            command_arr.append('--silent')

        result = subprocess.run(command_arr)
        if result.returncode == 0:
            logger.info("successful PlatformIO build")
        else:
            logger.error("PlatformIO build error")
        return result.returncode


    def clean(self) -> None:
        """
        Clean-up the project folder preserving only an '.ioc' file
        """

        for child in self.project_path.iterdir():
            if child.name != f"{self.project_path.name}.ioc":
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                    logger.debug(f"del {child}/")
                elif child.is_file():
                    child.unlink()
                    logger.debug(f"del {child}")

        logger.info("project has been cleaned")
