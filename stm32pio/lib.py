"""
Core library
"""

from __future__ import annotations

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
import stm32pio.util


@enum.unique
class ProjectStage(enum.IntEnum):
    """
    Codes indicating a project state at the moment. Should be the sequence of incrementing integers to be suited for
    state determining algorithm. Starts from 1

    Hint: Files/folders to be present on every project state:
        UNDEFINED: use this state to indicate none of the states below. Also, when we do not have any .ioc file the
                   Stm32pio class instance cannot be created (constructor raises an exception)
        EMPTY: ['project.ioc']
        INITIALIZED: ['project.ioc', 'stm32pio.ini']
        GENERATED: ['Inc', 'Src', 'project.ioc', 'stm32pio.ini']
        PIO_INITIALIZED (on case-sensitive FS): ['test', 'include', 'Inc', 'platformio.ini', '.gitignore', 'Src', 'lib',
                                                 'project.ioc', '.travis.yml', 'src']
        PATCHED: ['test', 'Inc', 'platformio.ini', '.gitignore', 'Src', 'lib', 'project.ioc', '.travis.yml']
        BUILT: same as above + '.pio' folder with build artifacts (such as .pio/build/nucleo_f031k6/firmware.bin,
                                                                           .pio/build/nucleo_f031k6/firmware.elf)
    """
    UNDEFINED = enum.auto()  # note: starts from 1
    EMPTY = enum.auto()
    INITIALIZED = enum.auto()
    GENERATED = enum.auto()
    PIO_INITIALIZED = enum.auto()
    PATCHED = enum.auto()
    BUILT = enum.auto()

    def __str__(self):
        string_representations = {
            'UNDEFINED': 'The project is messed up',
            'EMPTY': '.ioc file is present',
            'INITIALIZED': 'stm32pio initialized',
            'GENERATED': 'CubeMX code generated',
            'PIO_INITIALIZED': 'PlatformIO project initialized',
            'PATCHED': 'PlatformIO project patched',
            'BUILT': 'PlatformIO project built'
        }
        return string_representations[self.name]


class ProjectState(collections.OrderedDict):
    """
    The ordered dictionary subclass suitable for storing the Stm32pio instances state. For example:
      {
        ProjectStage.UNDEFINED:         True,  # doesn't necessarily means that the project is messed up, see below
        ProjectStage.EMPTY:             True,
        ProjectStage.INITIALIZED:       True,
        ProjectStage.GENERATED:         False,
        ProjectStage.PIO_INITIALIZED:   False,
        ProjectStage.PATCHED:           False,
        ProjectStage.BUILT:             False,
      }
    It is also extended with additional properties providing useful information such as obtaining the project current
    stage.

    The class has no special constructor so its filling - both stages and their order - is a responsibility of the
    external code. It also has no protection nor checks for its internal correctness. Anyway, it is intended to be used
    (i.e. creating) only by the internal code of this library so there should not be any worries.
    """

    def __str__(self):
        """
        Pretty human-readable complete representation of the project state (not including the service one UNDEFINED to
        not confuse the end-user)
        """
        # Need 2 spaces between the icon and the text to look fine
        return '\n'.join(f"{'✅' if stage_value else '❌'}  {str(stage_name)}"
                         for stage_name, stage_value in self.items() if stage_name != ProjectStage.UNDEFINED)

    @property
    def current_stage(self) -> ProjectStage:
        last_consistent_stage = ProjectStage.UNDEFINED
        zero_found = False

        # Search for a consecutive sequence of True's and find the last of them. For example, if the array is
        #   [1,1,1,0,0,0,0]
        #        ^
        # we should consider 2 as the last index
        for name, value in self.items():
            if value:
                if zero_found:
                    # Fall back to the UNDEFINED stage if we have breaks in conditions results array. E.g., for
                    #   [1,1,1,0,1,0,0]
                    # we should return UNDEFINED as it doesn't look like a correct set of files actually
                    last_consistent_stage = ProjectStage.UNDEFINED
                    break
                else:
                    last_consistent_stage = name
            else:
                zero_found = True

        return last_consistent_stage

    @property
    def is_consistent(self) -> bool:
        """
        Whether the state has been went through the stages consequentially or not (the method is currently unused)
        """
        return self.current_stage != ProjectStage.UNDEFINED


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
        logger (logging.Logger): if an external logger is given, it will be used, otherwise the new one will be created
                                 (unique for every instance)
    """

    def __init__(self, dirty_path: str, parameters: dict = None, save_on_destruction: bool = True,
                 logger: logging.Logger = None):

        if parameters is None:
            parameters = {}

        # The individual loggers for every single project allow to fine-tune the output when multiple projects are
        # created by the third-party code.
        if logger is not None:
            self.logger = logger
        else:
            self.logger = logging.getLogger(f"{__name__}.{id(self)}")  # use id() as uniqueness guarantee

        # The path is a unique identifier of the project so it would be great to remake Stm32pio class as a subclass of
        # pathlib.Path and then reference it like self and not self.path. It is more consistent also, as now path is
        # perceived like any other config parameter that somehow is appeared to exist outside of a config instance but
        # then it will be a core identifier, a truly 'self' value. But currently pathlib.Path is not intended to be
        # subclassable by-design, unfortunately. See https://bugs.python.org/issue24132
        self.path = self._resolve_project_path(dirty_path)

        self.config = self._load_config()

        self.ioc_file = self._find_ioc_file()
        self.config.set('project', 'ioc_file', str(self.ioc_file))

        cubemx_script_template = string.Template(self.config.get('project', 'cubemx_script_content'))
        cubemx_script_content = cubemx_script_template.substitute(project_path=self.path,
                                                                  cubemx_ioc_full_filename=self.ioc_file)
        self.config.set('project', 'cubemx_script_content', cubemx_script_content)

        # General rule: given parameter takes precedence over the saved one
        board = ''
        if 'board' in parameters and parameters['board'] is not None:
            if parameters['board'] in stm32pio.util.get_platformio_boards():
                board = parameters['board']
            else:
                self.logger.warning(f"'{parameters['board']}' was not found in PlatformIO. "
                                    "Run 'platformio boards' for possible names")
            self.config.set('project', 'board', board)
        elif self.config.get('project', 'board', fallback=None) is None:
            self.config.set('project', 'board', board)

        if save_on_destruction:
            # Save the config on an instance destruction
            self._finalizer = weakref.finalize(self, self._save_config, self.config, self.path, self.logger)


    def __repr__(self):
        return f"Stm32pio project: {str(self.path)}"


    @property
    def state(self) -> ProjectState:
        """
        Constructing and returning the current state of the project (tweaked dict, see ProjectState docs)
        """

        # self.logger.debug(f"project content: {[item.name for item in self.path.iterdir()]}")

        try:
            platformio_ini_is_patched = self.platformio_ini_is_patched()
        except (FileNotFoundError, ValueError):
            platformio_ini_is_patched = False

        # Create the temporary ordered dictionary and fill it with the conditions results arrays
        stages_conditions = collections.OrderedDict()
        stages_conditions[ProjectStage.UNDEFINED] = [True]
        stages_conditions[ProjectStage.EMPTY] = [self.ioc_file.is_file()]
        stages_conditions[ProjectStage.INITIALIZED] = [self.path.joinpath(stm32pio.settings.config_file_name).is_file()]
        stages_conditions[ProjectStage.GENERATED] = [self.path.joinpath('Inc').is_dir() and
                                                     len(list(self.path.joinpath('Inc').iterdir())) > 0,
                                                     self.path.joinpath('Src').is_dir() and
                                                     len(list(self.path.joinpath('Src').iterdir())) > 0]
        stages_conditions[ProjectStage.PIO_INITIALIZED] = [
            self.path.joinpath('platformio.ini').is_file() and
            self.path.joinpath('platformio.ini').stat().st_size > 0]
        stages_conditions[ProjectStage.PATCHED] = [
            platformio_ini_is_patched, not self.path.joinpath('include').is_dir()]
        stages_conditions[ProjectStage.BUILT] = [
            self.path.joinpath('.pio').is_dir() and
            any([item.is_file() for item in self.path.joinpath('.pio').rglob('*firmware*')])]

        # Fold arrays and save results in ProjectState instance
        conditions_results = ProjectState()
        for state, conditions in stages_conditions.items():
            conditions_results[state] = all(condition is True for condition in conditions)

        return conditions_results


    def _find_ioc_file(self) -> pathlib.Path:
        """
        Find and return an .ioc file. If there are more than one return first. If no .ioc file is present raise
        FileNotFoundError exception

        Returns:
            absolute path to the .ioc file
        """

        error_message = "not found: CubeMX project .ioc file"

        ioc_file = self.config.get('project', 'ioc_file', fallback=None)
        if ioc_file:
            ioc_file = pathlib.Path(ioc_file).expanduser().resolve()
            self.logger.debug(f"use {ioc_file.name} file from the INI config")
            if not ioc_file.is_file():
                raise FileNotFoundError(error_message)
            return ioc_file
        else:
            self.logger.debug("searching for any .ioc file...")
            candidates = list(self.path.glob('*.ioc'))
            if len(candidates) == 0:  # good candidate for the new Python 3.8 assignment expression feature :)
                raise FileNotFoundError(error_message)
            elif len(candidates) == 1:
                self.logger.debug(f"{candidates[0].name} is selected")
                return candidates[0]
            else:
                self.logger.warning(f"there are multiple .ioc files, {candidates[0].name} is selected")
                return candidates[0]


    def _load_config(self) -> configparser.ConfigParser:
        """
        Prepare ConfigParser config for the project. First, read the default config and then mask these values with user
        ones.

        Returns:
            new configparser.ConfigParser instance
        """

        self.logger.debug(f"searching for {stm32pio.settings.config_file_name}...")

        config = configparser.ConfigParser(interpolation=None)

        # Fill with default values
        config.read_dict(stm32pio.settings.config_default)
        # Then override by user values (if exist)
        config.read(str(self.path.joinpath(stm32pio.settings.config_file_name)))

        # Put away unnecessary processing as the string still will be formed even if the logging level doesn't allow
        # propagation of this message
        if self.logger.isEnabledFor(logging.DEBUG):
            debug_str = 'resolved config:'
            for section in config.sections():
                debug_str += f"\n========== {section} ==========\n"
                for value in config.items(section):
                    debug_str += f"{value}\n"
            self.logger.debug(debug_str)

        return config

    @staticmethod
    def _save_config(config: configparser.ConfigParser, path: pathlib.Path, logger: logging.Logger) -> int:
        """
        Writes ConfigParser config to the file path and logs using Logger logger.

        We declare this helper function which can be safely invoked by both internal methods and outer code. The latter
        case is suitable for using in weakref' finalizer objects as one of its main requirement is to not keep
        references to the destroyable object in any of the finalizer argument so the ordinary bound class method does
        not fit well.

        Returns:
            0 on success, -1 otherwise
        """
        try:
            with path.joinpath(stm32pio.settings.config_file_name).open(mode='w') as config_file:
                config.write(config_file)
            logger.debug("stm32pio.ini config file has been saved")
            return 0
        except Exception as e:
            logger.warning(f"cannot save the config: {e}", exc_info=logger.isEnabledFor(logging.DEBUG))
            return -1

    def save_config(self, parameters: dict = None) -> int:
        """
        Invokes base _save_config function. Preliminarily, updates the config with given parameters dictionary. It
        should has the following format:
            {
                'section1_name': {
                    'key1': 'value1',
                    'key2': 'value2'
                },
                ...
            }

        Returns:
            passes forward _save_config result
        """
        if parameters is not None:
            for section_name, section_value in parameters.items():
                for key, value in section_value.items():
                    self.config.set(section_name, key, value)
        return self._save_config(self.config, self.path, self.logger)


    @staticmethod
    def _resolve_project_path(dirty_path: str) -> pathlib.Path:
        """
        Handle 'path/to/proj', 'path/to/proj/', '.', '../proj' and other cases

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


    def generate_code(self) -> int:
        """
        Call STM32CubeMX app as 'java -jar' file to generate the code from the .ioc file. Pass commands to the
        STM32CubeMX in a temp file

        Returns:
            return code on success, raises an exception otherwise
        """

        # Use mkstemp() instead of the higher-level API for the compatibility with the Windows (see tempfile docs for
        # more details)
        cubemx_script_file, cubemx_script_name = tempfile.mkstemp()

        # We should necessarily remove the temp directory, so do not let any exception break our plans
        try:
            # buffering=0 leads to the immediate flushing on writing
            with open(cubemx_script_file, mode='w+b', buffering=0) as cubemx_script:
                # should encode, since mode='w+b'
                cubemx_script.write(self.config.get('project', 'cubemx_script_content').encode())

                self.logger.info("starting to generate a code from the CubeMX .ioc file...")
                command_arr = [self.config.get('app', 'java_cmd'), '-jar', self.config.get('app', 'cubemx_cmd'), '-q',
                               cubemx_script_name, '-s']  # -q: read the commands from the file, -s: silent performance
                # Redirect the output of the subprocess into the logging module (with DEBUG level)
                with stm32pio.util.LogPipe(self.logger, logging.DEBUG) as log_pipe:
                    result = subprocess.run(command_arr, stdout=log_pipe, stderr=log_pipe)
        except Exception as e:
            raise e  # re-raise an exception after the 'finally' block
        finally:
            pathlib.Path(cubemx_script_name).unlink()

        if result.returncode == 0:
            self.logger.info("successful code generation")
            return result.returncode
        else:
            self.logger.error(f"code generation error (CubeMX return code is {result.returncode}).\n"
                              "Enable a verbose output or try to generate a code from the CubeMX itself.")
            raise Exception("code generation error")


    def pio_init(self) -> int:
        """
        Call PlatformIO CLI to initialize a new project. It uses parameters (path, board) collected before so the
        confirmation of the data presence is lying on the invoking code

        Returns:
            return code of the PlatformIO on success, raises an exception otherwise
        """

        self.logger.info("starting PlatformIO project initialization...")

        platformio_ini_file = self.path.joinpath('platformio.ini')
        if platformio_ini_file.is_file() and platformio_ini_file.stat().st_size > 0:
            self.logger.warning("'platformio.ini' file is already exist")

        command_arr = [self.config.get('app', 'platformio_cmd'), 'init', '-d', str(self.path), '-b',
                       self.config.get('project', 'board'), '-O', 'framework=stm32cube']
        if not self.logger.isEnabledFor(logging.DEBUG):
            command_arr.append('--silent')

        result = subprocess.run(command_arr, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        error_msg = "PlatformIO project initialization error"
        if result.returncode == 0:
            # PlatformIO returns 0 even on some errors (e.g. no '--board' argument)
            if 'error' in result.stdout.lower():
                self.logger.error(result.stdout)
                raise Exception('\n' + error_msg)
            self.logger.debug(result.stdout, 'from_subprocess')
            self.logger.info("successful PlatformIO project initialization")
            return result.returncode
        else:
            self.logger.error(result.stdout)
            raise Exception(error_msg)


    def platformio_ini_is_patched(self) -> bool:
        """
        Check whether 'platformio.ini' config file is patched or not. It doesn't check for complete project patching
        (e.g. unnecessary folders deletion). Throws errors on non-existing file and on incorrect patch or file

        Returns:
            boolean indicating a result
        """

        platformio_ini = configparser.ConfigParser(interpolation=None)
        try:
            if len(platformio_ini.read(self.path.joinpath('platformio.ini'))) == 0:
                raise FileNotFoundError("not found: 'platformio.ini' file")
        except FileNotFoundError as e:
            raise e
        except Exception as e:
            # Re-raise parsing exceptions as ValueError
            raise ValueError("'platformio.ini' file is incorrect") from e

        patch_config = configparser.ConfigParser(interpolation=None)
        try:
            patch_config.read_string(self.config.get('project', 'platformio_ini_patch_content'))
        except Exception as e:
            raise ValueError("Desired patch content is invalid (should satisfy INI-format requirements)") from e

        for patch_section in patch_config.sections():
            if platformio_ini.has_section(patch_section):
                for patch_key, patch_value in patch_config.items(patch_section):
                    platformio_ini_value = platformio_ini.get(patch_section, patch_key, fallback=None)
                    if platformio_ini_value != patch_value:
                        self.logger.debug(f"[{patch_section}]{patch_key}: patch value is\n  {patch_value}\nbut "
                                          f"platformio.ini contains\n  {platformio_ini_value}")
                        return False
            else:
                self.logger.debug(f"platformio.ini has no '{patch_section}' section")
                return False
        return True


    def patch(self) -> None:
        """
        Patch platformio.ini file by a user's patch. By default, it sets the created earlier (by CubeMX 'Src' and 'Inc')
        folders as sources. configparser doesn't preserve any comments unfortunately so keep in mind that all of them
        will be lost at this stage. Also, the order may be violated. In the end, remove old empty folders
        """

        self.logger.debug("patching 'platformio.ini' file...")

        if self.platformio_ini_is_patched():
            self.logger.info("'platformio.ini' has been already patched")
        else:
            # Existing .ini file
            platformio_ini_config = configparser.ConfigParser(interpolation=None)
            platformio_ini_config.read(self.path.joinpath('platformio.ini'))

            # Our patch has the config format too
            patch_config = configparser.ConfigParser(interpolation=None)
            patch_config.read_string(self.config.get('project', 'platformio_ini_patch_content'))

            # Merge 2 configs
            for patch_section in patch_config.sections():
                if not platformio_ini_config.has_section(patch_section):
                    self.logger.debug(f"[{patch_section}] section was added")
                    platformio_ini_config.add_section(patch_section)
                for patch_key, patch_value in patch_config.items(patch_section):
                    self.logger.debug(f"set [{patch_section}]{patch_key} = {patch_value}")
                    platformio_ini_config.set(patch_section, patch_key, patch_value)

            # Save, overwriting the original file (deletes all comments!)
            with self.path.joinpath('platformio.ini').open(mode='w') as platformio_ini_file:
                platformio_ini_config.write(platformio_ini_file)
                self.logger.debug("'platformio.ini' has been patched")

        try:
            shutil.rmtree(self.path.joinpath('include'))
            self.logger.debug("'include' folder has been removed")
        except:
            self.logger.info("cannot delete 'include' folder", exc_info=self.logger.isEnabledFor(logging.DEBUG))
        # Remove 'src' directory too but on case-sensitive file systems 'Src' == 'src' == 'SRC' so we need to check
        if not self.path.joinpath('SRC').is_dir():
            try:
                shutil.rmtree(self.path.joinpath('src'))
                self.logger.debug("'src' folder has been removed")
            except:
                self.logger.info("cannot delete 'src' folder", exc_info=self.logger.isEnabledFor(logging.DEBUG))

        self.logger.info("Project has been patched")


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

        self.logger.info(f"starting an editor '{editor_command}'...")

        try:
            # Works unstable on some Windows 7 systems, but correct on latest Win7 and Win10...
            # result = subprocess.run([editor_command, str(self.path)], check=True)
            result = subprocess.run(f"{editor_command} {str(self.path)}", shell=True, check=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.logger.debug(result.stdout, 'from_subprocess')

            return result.returncode
        except subprocess.CalledProcessError as e:
            self.logger.error(f"failed to start the editor {editor_command}: {e.stdout}")
            return e.returncode


    def build(self) -> int:
        """
        Initiate a build of the PlatformIO project by the PlatformIO ('run' command). PlatformIO prints warning and
        error messages by itself to the STDERR so there is no need to catch it and output by us

        Returns:
            passes a return code of the PlatformIO
        """

        self.logger.info("starting PlatformIO project build...")

        command_arr = [self.config.get('app', 'platformio_cmd'), 'run', '-d', str(self.path)]
        if not self.logger.isEnabledFor(logging.DEBUG):
            command_arr.append('--silent')

        with stm32pio.util.LogPipe(self.logger, logging.DEBUG) as log_pipe:
            result = subprocess.run(command_arr, stdout=log_pipe, stderr=log_pipe)
        if result.returncode == 0:
            self.logger.info("successful PlatformIO build")
        else:
            self.logger.error("PlatformIO build error")
        return result.returncode


    def clean(self) -> None:
        """
        Clean-up the project folder preserving only an '.ioc' file
        """

        for child in self.path.iterdir():
            if child.name != f"{self.path.name}.ioc":
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                    self.logger.debug(f"del {child}")
                elif child.is_file():
                    child.unlink()
                    self.logger.debug(f"del {child}")

        self.logger.info("project has been cleaned")
