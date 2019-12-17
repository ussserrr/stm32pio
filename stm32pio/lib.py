"""
Main library
"""

import collections
import configparser
import enum
import logging
import pathlib
import shutil
import string
import subprocess
import tempfile
import weakref

import stm32pio.settings

# Child logger, inherits parameters of the parent that has been set in more high-level code
logger = logging.getLogger('stm32pio.util')


@enum.unique
class ProjectState(enum.IntEnum):
    """
    Codes indicating a project state at the moment. Should be the sequence of incrementing integers to be suited for
    state determining algorithm. Starting from 1

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
    UNDEFINED = enum.auto()  # note: starts from 1
    INITIALIZED = enum.auto()
    GENERATED = enum.auto()
    PIO_INITIALIZED = enum.auto()
    PATCHED = enum.auto()
    BUILT = enum.auto()


class Config(configparser.ConfigParser):
    """
    A simple subclass that has additional save() method for the better logic encapsulation
    """

    def __init__(self, location: pathlib.Path, *args, **kwargs):
        """
        Args:
            location: project path (where to store the config file)
            *args, **kwargs: passes to the parent's constructor
        """
        super().__init__(*args, **kwargs)
        self._location = location

    def save(self) -> int:
        """
        Tries to save the config to the file and gently log if any error occurs
        """
        try:
            with self._location.joinpath(stm32pio.settings.config_file_name).open(mode='w') as config_file:
                self.write(config_file)
            logger.debug("stm32pio.ini config file has been saved")
            return 0
        except Exception as e:
            logger.warning(f"cannot save the config: {e}", exc_info=logger.getEffectiveLevel() <= logging.DEBUG)
            return -1


class Stm32pio:
    """
    Main class.

    Represents a single project, encapsulating file system path to the project (main mandatory identifier) and some
    parameters in a configparser .ini file. As stm32pio can be installed via pip and has no global config we also
    storing global parameters (such as Java or STM32CubeMX invoking commands) in this config .ini file so the user can
    specify settings on a per-project base. The config can be saved in a non-disturbing way automatically on the
    instance destruction (e.g. by garbage collecting it) (use save_on_destruction=True flag), otherwise a user should
    explicitly save the config if he wants to (using config.save() method).

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

        # The path is a unique identifier of the project so it would be great to remake Stm32pio class as a subclass of
        # pathlib.Path and then reference it like self and not self.project_path. It is more consistent also, as now
        # project_path is perceived like any other config parameter that somehow is appeared to exist outside of a
        # config instance but then it will be a core identifier, a truly 'self' value. But currently pathlib.Path is not
        # intended to be subclassable by-design, unfortunately. See https://bugs.python.org/issue24132
        self.project_path = self._resolve_project_path(dirty_path)

        self.config = self._load_config_file()

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
            self._finalizer = weakref.finalize(self, self.config.save)


    @property
    def state(self) -> ProjectState:
        """
        Property returning the current state of the project. Calculated at every request

        Returns:
            enum value representing a project state
        """

        logger.debug("calculating the project state...")
        logger.debug(f"project content: {[item.name for item in self.project_path.iterdir()]}")

        try:
            platformio_ini_is_patched = self.platformio_ini_is_patched()
        except:
            platformio_ini_is_patched = False

        states_conditions = collections.OrderedDict()
        # Fill the ordered dictionary with the conditions results
        states_conditions[ProjectState.UNDEFINED] = [True]
        states_conditions[ProjectState.INITIALIZED] = [
            self.project_path.joinpath(stm32pio.settings.config_file_name).is_file()]
        states_conditions[ProjectState.GENERATED] = [self.project_path.joinpath('Inc').is_dir() and
                                                     len(list(self.project_path.joinpath('Inc').iterdir())) > 0,
                                                     self.project_path.joinpath('Src').is_dir() and
                                                     len(list(self.project_path.joinpath('Src').iterdir())) > 0]
        states_conditions[ProjectState.PIO_INITIALIZED] = [
            self.project_path.joinpath('platformio.ini').is_file() and
            self.project_path.joinpath('platformio.ini').stat().st_size > 0]
        states_conditions[ProjectState.PATCHED] = [
            platformio_ini_is_patched, not self.project_path.joinpath('include').is_dir()]
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
            states_info_str = '\n'.join(
                f"{state.name:20}{conditions_results[state.value - 1]}" for state in ProjectState)
            logger.debug(f"determined states:\n{states_info_str}")

        # Search for a consecutive sequence of 1's and find the last of them. For example, if the array is
        #   [1,1,0,1,0,0]
        #      ^
        # we should consider 1 as the last index
        last_true_index = 0  # ProjectState.UNDEFINED is always True, use as a start value
        for index, value in enumerate(conditions_results):
            if value == 1:
                last_true_index = index
            else:
                break

        # Fall back to the UNDEFINED state if we have breaks in conditions results array. For example, in [1,1,0,1,0,0]
        # we still return UNDEFINED as it doesn't look like a correct combination of files actually
        if 1 in conditions_results[last_true_index + 1:]:
            project_state = ProjectState.UNDEFINED
        else:
            project_state = ProjectState(last_true_index + 1)

        return project_state


    def _find_ioc_file(self) -> pathlib.Path:
        """
        Find and return an .ioc file. If there are more than one, return first. If no .ioc file is present raise
        FileNotFoundError exception

        Returns:
            absolute path to the .ioc file
        """

        ioc_file = self.config.get('project', 'ioc_file', fallback=None)
        if ioc_file:
            ioc_file = pathlib.Path(ioc_file).resolve()
            logger.debug(f"use {ioc_file.name} file from the INI config")
            return ioc_file
        else:
            logger.debug("searching for any .ioc file...")
            candidates = list(self.project_path.glob('*.ioc'))
            if len(candidates) == 0:  # good candidate for the new Python 3.8 assignment expressions feature :)
                raise FileNotFoundError("not found: CubeMX project .ioc file")
            elif len(candidates) == 1:
                logger.debug(f"{candidates[0].name} is selected")
                return candidates[0]
            else:
                logger.warning(f"there are multiple .ioc files, {candidates[0].name} is selected")
                return candidates[0]


    def _load_config_file(self) -> Config:
        """
        Prepare configparser config for the project. First, read the default config and then mask these values with user
        ones

        Returns:
            custom configparser.ConfigParser instance
        """

        logger.debug(f"searching for {stm32pio.settings.config_file_name}...")
        stm32pio_ini = self.project_path.joinpath(stm32pio.settings.config_file_name)

        config = Config(self.project_path, interpolation=None)

        # Fill with default values
        config.read_dict(stm32pio.settings.config_default)
        # Then override by user values (if exist)
        config.read(str(stm32pio_ini))

        # Put away unnecessary processing as the string still will be formed even if the logging level doesn't allow
        # propagation of this message
        if logger.getEffectiveLevel() <= logging.DEBUG:
            debug_str = 'resolved config:'
            for section in config.sections():
                debug_str += f"\n========== {section} ==========\n"
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

        Returns:
            expanded absolute pathlib.Path instance
        """
        resolved_path = pathlib.Path(dirty_path).expanduser().resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"not found: {resolved_path}")
        else:
            return resolved_path


    def _resolve_board(self, board: str) -> str:
        """
        Check if given board is a correct board name in the PlatformIO database

        Args:
            board: string representing PlatformIO board name (for example, 'nucleo_f031k6')

        Returns:
            same board that has been given if it was found, raise an exception otherwise
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


    def generate_code(self) -> int:
        """
        Call STM32CubeMX app as a 'java -jar' file to generate the code from the .ioc file. Pass commands to the
        STM32CubeMX in a temp file

        Returns:
            return code on success, raises an exception otherwise
        """

        # Use mkstemp() instead of higher-level API for compatibility with Windows (see tempfile docs for more details)
        cubemx_script_file, cubemx_script_name = tempfile.mkstemp()

        # We should necessarily remove the temp directory, so do not let any exception break our plans
        try:
            # buffering=0 leads to the immediate flushing on writing
            with open(cubemx_script_file, mode='w+b', buffering=0) as cubemx_script:
                # encode since mode='w+b'
                cubemx_script.write(self.config.get('project', 'cubemx_script_content').encode())

                logger.info("starting to generate a code from the CubeMX .ioc file...")
                command_arr = [self.config.get('app', 'java_cmd'), '-jar', self.config.get('app', 'cubemx_cmd'), '-q',
                               cubemx_script_name, '-s']  # -q: read commands from file, -s: silent performance
                if logger.getEffectiveLevel() <= logging.DEBUG:
                    result = subprocess.run(command_arr)
                else:
                    result = subprocess.run(command_arr, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    # Or, for Python 3.7 and above:
                    # result = subprocess.run(command_arr, capture_output=True)
        except Exception as e:
            raise e  # re-raise an exception after the final block
        finally:
            pathlib.Path(cubemx_script_name).unlink()

        if result.returncode == 0:
            logger.info("successful code generation")
            return result.returncode
        else:
            logger.error(f"code generation error (CubeMX return code is {result.returncode}).\n"
                         "Enable a verbose output or try to generate a code from the CubeMX itself.")
            raise Exception("code generation error")

    def pio_init(self) -> int:
        """
        Call PlatformIO CLI to initialize a new project. It uses parameters (path, board) collected before so the
        confirmation of the data presence is on a user

        Returns:
            return code of the PlatformIO on success, raises an exception otherwise
        """

        logger.info("starting PlatformIO project initialization...")

        platformio_ini_file = self.project_path.joinpath('platformio.ini')
        if platformio_ini_file.is_file() and platformio_ini_file.stat().st_size > 0:
            logger.warning("'platformio.ini' file is already exist")

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


    def platformio_ini_is_patched(self) -> bool:
        """
        Check whether 'platformio.ini' config file is patched or not. It doesn't check for complete project patching
        (e.g. unnecessary folders deletion). Throws an error on non-existing file and on incorrect patch or file

        Returns:
            boolean indicating a result
        """

        platformio_ini = configparser.ConfigParser(interpolation=None)
        try:
            if len(platformio_ini.read(self.project_path.joinpath('platformio.ini'))) == 0:
                raise FileNotFoundError("not found: 'platformio.ini' file")
        except FileNotFoundError as e:
            raise e
        except Exception as e:
            raise Exception("'platformio.ini' file is incorrect") from e

        patch_config = configparser.ConfigParser(interpolation=None)
        try:
            patch_config.read_string(self.config.get('project', 'platformio_ini_patch_content'))
        except Exception as e:
            raise Exception("Desired patch content is invalid (should satisfy INI-format requirements)") from e

        for patch_section in patch_config.sections():
            if platformio_ini.has_section(patch_section):
                for patch_key, patch_value in patch_config.items(patch_section):
                    platformio_ini_value = platformio_ini.get(patch_section, patch_key, fallback=None)
                    if platformio_ini_value != patch_value:
                        logger.debug(f"[{patch_section}]{patch_key}: patch value is\n{patch_value}\nbut "
                                     f"platformio.ini contains\n{platformio_ini_value}")
                        return False
            else:
                logger.debug(f"platformio.ini has not {patch_section} section")
                return False
        return True


    def patch(self) -> None:
        """
        Patch platformio.ini file by a user's patch. By default, it sets the created earlier (by CubeMX 'Src' and 'Inc')
        folders as sources. configparser doesn't preserve any comments unfortunately so keep in mid that all of them
        will be lost at this stage. Also, the order may be violated. In the end, remove old empty folders
        """

        logger.debug("patching 'platformio.ini' file...")

        if self.platformio_ini_is_patched():
            logger.info("'platformio.ini' has been already patched")
        else:
            # Existing .ini file
            platformio_ini_config = configparser.ConfigParser(interpolation=None)
            platformio_ini_config.read(self.project_path.joinpath('platformio.ini'))

            # Our patch has the config format too
            patch_config = configparser.ConfigParser(interpolation=None)
            patch_config.read_string(self.config.get('project', 'platformio_ini_patch_content'))

            # Merge 2 configs
            for patch_section in patch_config.sections():
                if not platformio_ini_config.has_section(patch_section):
                    logger.debug(f"[{patch_section}] section was added")
                    platformio_ini_config.add_section(patch_section)
                for patch_key, patch_value in patch_config.items(patch_section):
                    logger.debug(f"set [{patch_section}]{patch_key} = {patch_value}")
                    platformio_ini_config.set(patch_section, patch_key, patch_value)

            # Save, overwriting the original file (deletes all comments!)
            with self.project_path.joinpath('platformio.ini').open(mode='w') as platformio_ini_file:
                platformio_ini_config.write(platformio_ini_file)

            logger.info("'platformio.ini' has been patched")

        try:
            shutil.rmtree(self.project_path.joinpath('include'))
        except:
            logger.info("cannot delete 'include' folder", exc_info=logger.getEffectiveLevel() <= logging.DEBUG)
        # Remove 'src' directory too but on case-sensitive file systems 'Src' == 'src' == 'SRC' so we need to check
        if not self.project_path.joinpath('SRC').is_dir():
            try:
                shutil.rmtree(self.project_path.joinpath('src'))
            except:
                logger.info("cannot delete 'src' folder", exc_info=logger.getEffectiveLevel() <= logging.DEBUG)


    def start_editor(self, editor_command: str) -> int:
        """
        Start the editor specified by 'editor_command' with the project opened (assume
            $ [editor] [folder]
        form works)

        Args:
            editor_command: editor command as we start it in the terminal

        Returns:
            passes a return code of the command
        """

        logger.info(f"starting an editor '{editor_command}'...")

        try:
            # Works unstable on some Windows 7 systems, but correct on latest Win7 and Win10...
            # result = subprocess.run([editor_command, str(self.project_path)], check=True)
            result = subprocess.run(f"{editor_command} {str(self.project_path)}", shell=True, check=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.returncode
        except subprocess.CalledProcessError as e:
            output = e.stdout if e.stderr is None else e.stderr
            logger.error(f"failed to start the editor {editor_command}: {output}")
            return e.returncode


    def build(self) -> int:
        """
        Initiate a build of the PlatformIO project by the PlatformIO ('run' command). PlatformIO prints warning and
        error messages by itself to the STDERR so there is no need to catch it and output by us

        Returns:
            passes a return code of the PlatformIO
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
                    logger.debug(f"del {child}")
                elif child.is_file():
                    child.unlink()
                    logger.debug(f"del {child}")

        logger.info("project has been cleaned")
