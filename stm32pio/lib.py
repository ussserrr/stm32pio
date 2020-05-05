"""
Core library
"""

import collections
import configparser
import contextlib
import copy
import enum
import logging
import pathlib
import shlex
import shutil
import string
import subprocess
import tempfile
import weakref
from typing import Mapping, Any, Union

import stm32pio.settings
import stm32pio.util


_stages_string_representations = {
    'UNDEFINED': 'The project is messed up',
    'EMPTY': '.ioc file is present',
    'INITIALIZED': 'stm32pio initialized',
    'GENERATED': 'CubeMX code generated',
    'PIO_INITIALIZED': 'PlatformIO project initialized',
    'PATCHED': 'PlatformIO project patched',
    'BUILT': 'PlatformIO project built'
}

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
        return _stages_string_representations[self.name]


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
        ProjectStage.BUILT:             False
      }
    It is also extended with additional properties providing useful information such as obtaining the project current
    stage.

    The class has no special constructor so its filling - both stages and their order - is a responsibility of the
    external code. It also has no protection nor checks for its internal correctness. Anyway, it is intended to be used
    (i.e. creating) only by the internal code of this library so there shouldn't be any worries.
    """

    def __str__(self):
        """
        Pretty human-readable complete representation of the project state (not including the service one UNDEFINED to
        not confuse the end-user)
        """
        # Need 2 spaces between the icon and the text to look fine
        return '\n'.join(f"{'[*]' if stage_value else '[ ]'}  {str(stage_name)}"
                         for stage_name, stage_value in self.items() if stage_name != ProjectStage.UNDEFINED)

    @property
    def current_stage(self) -> ProjectStage:
        last_consistent_stage = ProjectStage.UNDEFINED
        not_fulfilled_stage_found = False

        # Search for a consecutive sequence of True's and find the last of them. For example, if the array is
        #   [1,1,1,0,0,0,0]
        #        ^
        # we should consider 2 as the last index
        for stage_name, stage_fulfilled in self.items():
            if stage_fulfilled:
                if not_fulfilled_stage_found:
                    # Fall back to the UNDEFINED stage if we have breaks in conditions results array. E.g., for
                    #   [1,1,1,0,1,0,0]
                    # we should return UNDEFINED as it doesn't look like a correct set of files actually
                    last_consistent_stage = ProjectStage.UNDEFINED
                    break
                else:
                    last_consistent_stage = stage_name
            else:
                not_fulfilled_stage_found = True

        return last_consistent_stage

    @property
    def is_consistent(self) -> bool:
        """Whether the state has been went through the stages consequentially or not"""
        return self.current_stage != ProjectStage.UNDEFINED


class Stm32pio:
    """
    Main class.

    Represents a single project, encapsulating file system path to the project (main mandatory identifier) and some
    parameters in a configparser .ini file. As stm32pio can be installed via pip and has no global config we also
    storing global parameters (such as Java or STM32CubeMX invoking commands) in this config .ini file so the user can
    specify settings on a per-project basis. The config can be saved in a non-disturbing way automatically on the
    instance destruction (e.g. by garbage collecting it) (use save_on_destruction=True flag), otherwise a user should
    explicitly save the config if he wants to (using config.save() method).

    The typical life cycle consists of project creation, passing mandatory 'dirty_path' argument. If also 'parameters'
    dictionary is specified these settings are processed (see _load_config method). Then it is possible to perform API
    operations.

    WARNING. Please be careful with the 'clean' method as it deletes all the content of the project directory except
    the main .ioc file.
    """

    INSTANCE_OPTIONS_DEFAULTS = {  # TODO: use Python 3.8 TypedDict
        'save_on_destruction': False,
        'logger': None
    }

    def __init__(self, dirty_path: Union[str, pathlib.Path], parameters: Mapping[str, Any] = None,
                 instance_options: Mapping[str, Any] = None):
        """
        Args:
            dirty_path: path to the project (required)
            parameters: additional parameters to set on initialization stage (format is same as for project' config
                        configparser.ConfigParser (see settings.py), values are merging via _load_config method)
            instance_options: some parameters, related more to the instance itself than to the project:
                save_on_destruction (bool=True): register or not the finalizer that saves the config to file
                logger (logging.Logger=None): if an external logger is given, it will be used, otherwise the new one
                                              will be created (unique for every instance)
        """

        if parameters is None:
            parameters = {}

        if instance_options is None:
            instance_options = copy.copy(Stm32pio.INSTANCE_OPTIONS_DEFAULTS)
        else:
            # Create a shallow copy of the argument, a mutable mapping, as we probably going to add some pairs to it
            instance_options = dict(instance_options)
            # Insert missing pairs but do not touch any extra ones if there is any
            for key, value in copy.copy(Stm32pio.INSTANCE_OPTIONS_DEFAULTS).items():
                if key not in instance_options:
                    instance_options[key] = value

        # The individual loggers for every single project allows to fine-tune the output when the multiple projects are
        # created by the third-party code
        if instance_options['logger'] is not None:
            self.logger = instance_options['logger']
        else:
            underlying_logger = logging.getLogger('stm32pio.projects')
            self.logger = stm32pio.util.ProjectLoggerAdapter(underlying_logger, { 'project_id': id(self) })

        # The path is a primary entity of the project so we process it first and foremost. Handle 'path/to/proj',
        # 'path/to/proj/', '.', '../proj', etc., make the path absolute and check for existence. Also, the .ioc file can
        # be specified instead of the directory. In this case it is assumed that the parent path is an actual project
        # path and the provided .ioc file is used on a priority basis
        path = pathlib.Path(dirty_path).expanduser().resolve(strict=True)
        ioc_file = None
        if path.is_file() and path.suffix == '.ioc':  # if .ioc file was supplied instead of the directory
            ioc_file = path
            path = path.parent
        self.path = path

        self.config = self._load_config(parameters)

        self.ioc_file = self._find_ioc_file(explicit_file=ioc_file)
        self.config.set('project', 'ioc_file', self.ioc_file.name)  # save only the name of file to the config

        # Notify the caller about the board presence
        if 'board' in parameters and parameters['board'] is not None:
            try:
                boards = stm32pio.util.get_platformio_boards(self.config.get('app', 'platformio_cmd'))
            except Exception as e:
                self.logger.warning(f"There was an error while obtaining possible PlatformIO boards: {e}",
                                    exc_info=self.logger.isEnabledFor(logging.DEBUG))
                boards = []
            if parameters['board'] not in boards:
                self.logger.warning(f"'{parameters['board']}' was not found in PlatformIO. "
                                    "Run 'platformio boards' for possible names")

        # Save the config on an instance destruction
        if instance_options['save_on_destruction']:
            self._finalizer = weakref.finalize(self, self._save_config, self.config, self.path, self.logger)


    def __repr__(self):
        """String representation of the project (use an absolute path for this)"""
        return f"Stm32pio project: {str(self.path)}"


    @property
    def state(self) -> ProjectState:
        """Constructing and returning the current state of the project (tweaked dict, see ProjectState docs)"""

        pio_is_initialized = False
        with contextlib.suppress(Exception):  # we just want to know the status and don't care about the details
            # Is present, is correct and is not empty
            pio_is_initialized = len(self.platformio_ini_config.sections()) != 0

        platformio_ini_is_patched = False
        if pio_is_initialized:  # make no sense to proceed if there is something happened in the first place
            with contextlib.suppress(Exception):  # we just want to know the status and don't care about the details
                platformio_ini_is_patched = self.platformio_ini_is_patched

        # Create the temporary ordered dictionary and fill it with the conditions results arrays
        stages_conditions = collections.OrderedDict()
        stages_conditions[ProjectStage.UNDEFINED] = [True]
        stages_conditions[ProjectStage.EMPTY] = [self.ioc_file.is_file()]
        stages_conditions[ProjectStage.INITIALIZED] = [self.path.joinpath(stm32pio.settings.config_file_name).is_file()]
        stages_conditions[ProjectStage.GENERATED] = [self.path.joinpath('Inc').is_dir() and
                                                     len(list(self.path.joinpath('Inc').iterdir())) > 0,
                                                     self.path.joinpath('Src').is_dir() and
                                                     len(list(self.path.joinpath('Src').iterdir())) > 0]
        stages_conditions[ProjectStage.PIO_INITIALIZED] = [pio_is_initialized]
        stages_conditions[ProjectStage.PATCHED] = [platformio_ini_is_patched,
                                                   not self.path.joinpath('include').is_dir()]
        # Hidden folder! Can be not visible in your file manager and cause a confusion
        stages_conditions[ProjectStage.BUILT] = [
            self.path.joinpath('.pio').is_dir() and
            any([item.is_file() for item in self.path.joinpath('.pio').rglob('*firmware*')])]

        # Fold arrays and save results in ProjectState instance
        conditions_results = ProjectState()
        for state, conditions in stages_conditions.items():
            conditions_results[state] = all(condition is True for condition in conditions)

        return conditions_results


    def _find_ioc_file(self, explicit_file: pathlib.Path = None) -> pathlib.Path:
        """
        Find, check (that this is a non-empty text file) and return an .ioc file. If there are more than one - return
        first. If no .ioc file is present - raise the FileNotFoundError exception. Use explicit_file if it was provided.

        Returns:
            absolute path to the .ioc file
        """

        result_file = None

        # 1. If explicit file was provided use it
        if explicit_file is not None:
            self.logger.debug(f"using explicitly provided '{explicit_file.name}' file")
            result_file = explicit_file

        else:
            # 2. Check the value from the config file
            ioc_file = self.config.get('project', 'ioc_file', fallback=None)  # TODO: Python 3.8 walrus operator (elif ...)
            if ioc_file:
                ioc_file = self.path.joinpath(ioc_file).resolve(strict=True)
                self.logger.debug(f"using '{ioc_file.name}' file from the INI config")
                result_file = ioc_file

            # 3. Otherwise search for an appropriate file by yourself
            else:
                self.logger.debug("searching for any .ioc file...")
                candidates = list(self.path.glob('*.ioc'))
                if len(candidates) == 0:  # TODO: good candidate for the new Python 3.8 assignment expression feature :)
                    raise FileNotFoundError("CubeMX project .ioc file")
                elif len(candidates) == 1:
                    self.logger.debug(f"{candidates[0].name} is selected")
                    result_file = candidates[0]
                else:
                    self.logger.warning(f"there are multiple .ioc files, {candidates[0].name} is selected")
                    result_file = candidates[0]

        # Check for the file correctness
        try:
            content = result_file.read_text()  # should be a text file
            if len(content) == 0:
                raise ValueError("the file is empty")
            return result_file
        except Exception as e:
            raise Exception(f"{result_file.name} is incorrect") from e


    def _load_config(self, runtime_parameters: Mapping[str, Any] = None) -> configparser.ConfigParser:
        """
        Prepare ConfigParser config for the project. Order of getting values (masking) (higher levels overwrites lower):

            default dict (settings module)  =>  config file stm32pio.ini  =>  user-given (runtime) values
                                                                              (via CLI or another way)

        Returns:
            new configparser.ConfigParser instance
        """

        if runtime_parameters is None:
            runtime_parameters = {}

        config = configparser.ConfigParser(interpolation=None)

        # Fill with default values ...
        config.read_dict(copy.deepcopy(stm32pio.settings.config_default))

        # ... then merge with user's config file values (if exist) ...
        self.logger.debug(f"searching for {stm32pio.settings.config_file_name}...")
        config.read(self.path.joinpath(stm32pio.settings.config_file_name))

        ini_config = configparser.ConfigParser(interpolation=None)
        ini_config.read(self.path.joinpath(stm32pio.settings.config_file_name))
        runtime_config = configparser.ConfigParser(interpolation=None)
        runtime_config.read_dict(runtime_parameters)

        if len(ini_config.sections()):
            if len(runtime_config.sections()):
                for ini_sect in ini_config.sections():
                    if runtime_config.has_section(ini_sect):
                        for ini_key, ini_value in ini_config.items(ini_sect):
                            if runtime_config.get(ini_sect, ini_key, fallback=None) not in [None, ini_value]:
                                self.logger.info(f"given '{ini_key}' has taken a precedence over the .ini one")
        else:
            self.logger.debug(f"no or empty {stm32pio.settings.config_file_name} config file, will use the default one")

        # ... finally merge with the given in this session CLI parameters
        config.read_dict(runtime_parameters)

        # Put away unnecessary processing as the string still will be formed even if the logging level doesn't allow a
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
        Writes the ConfigParser 'config' to the file 'path' and logs using the Logger 'logger'.

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
            logger.debug(f"{stm32pio.settings.config_file_name} config file has been saved")
            return 0
        except Exception as e:
            logger.warning(f"cannot save the config: {e}", exc_info=logger.isEnabledFor(logging.DEBUG))
            return -1

    def save_config(self, parameters: Mapping[str, Mapping[str, Any]] = None) -> int:
        """
        Invokes base _save_config function. Preliminarily, updates the config with the given 'parameters' dictionary. It
        should has the following format:
            {
                'project': {
                    'board': 'nucleo_f031k6',
                    'ioc_file': 'fan_controller.ioc'
                },
                ...
            }

        Returns:
            passes forward the _save_config() result
        """

        if parameters is None:
            parameters = {}

        self.config.read_dict(parameters)
        return self._save_config(self.config, self.path, self.logger)


    def generate_code(self) -> int:
        """
        Call STM32CubeMX app as 'java -jar' file to generate the code from the .ioc file. Pass the commands to the
        STM32CubeMX in a temp file.

        Returns:
            return code on success, raises an exception otherwise
        """

        self.logger.info("starting to generate a code from the CubeMX .ioc file...")

        # Use mkstemp() instead of the higher-level API for the compatibility with the Windows (see tempfile docs for
        # more details)
        cubemx_script_file, cubemx_script_name = tempfile.mkstemp()

        # We must remove the temp directory, so do not let any exception break our plans
        try:
            # buffering=0 leads to the immediate flushing on writing
            with open(cubemx_script_file, mode='w+b', buffering=0) as cubemx_script:
                cubemx_script_template = string.Template(self.config.get('project', 'cubemx_script_content'))
                cubemx_script_content = cubemx_script_template.substitute(ioc_file_absolute_path=self.ioc_file,
                                                                          project_dir_absolute_path=self.path)
                cubemx_script.write(cubemx_script_content.encode())  # should encode, since mode='w+b'

                command_arr = [self.config.get('app', 'java_cmd'), '-jar', self.config.get('app', 'cubemx_cmd'), '-q',
                               cubemx_script_name, '-s']  # -q: read the commands from the file, -s: silent performance
                # Redirect the output of the subprocess into the logging module (with DEBUG level)
                with stm32pio.util.LogPipe(self.logger, logging.DEBUG) as log:
                    result = subprocess.run(command_arr, stdout=log.pipe, stderr=log.pipe)
                    result_output = log.value

        except Exception as e:
            raise e  # re-raise an exception after the 'finally' block
        finally:
            pathlib.Path(cubemx_script_name).unlink()

        error_msg = "code generation error"
        if result.returncode == 0:
            # CubeMX 0 return code doesn't necessarily means the correct generation (e.g. migration dialog has appeared
            # and 'Cancel' was chosen, or CubeMX_version < ioc_file_version), should analyze the output
            if 'Code succesfully generated' in result_output:
                self.logger.info("successful code generation")
                return result.returncode
            else:
                # GUESSING
                error_lines = [line for line in result_output.splitlines(keepends=True) if '[ERROR]' in line]
                if len(error_lines):
                    self.logger.error(error_lines, extra={ 'from_subprocess': True })
                    raise Exception(error_msg)
                else:
                    self.logger.warning("Undefined result from the CubeMX (neither error or success symptoms were "
                                        "found in the logs). Keep going but there might be an error")
                    return result.returncode
        else:
            # Most likely the 'java' error (e.g. no CubeMX is present)
            self.logger.error(f"Return code is {result.returncode}. Output:\n\n{result_output}",
                              extra={ 'from_subprocess': True })
            raise Exception(error_msg)


    def pio_init(self) -> int:
        """
        Call PlatformIO CLI to initialize a new project. It uses parameters (path, board) collected before so the
        confirmation about the data presence is lying on the invoking code.

        Returns:
            return code of the PlatformIO on success, raises an exception otherwise
        """

        self.logger.info("starting PlatformIO project initialization...")

        try:
            if len(self.platformio_ini_config.sections()):
                self.logger.warning("'platformio.ini' file is already exist")
            # else: file is empty (PlatformIO should overwrite it)
        except FileNotFoundError:
            pass  # no file
        except Exception:
            self.logger.warning("'platformio.ini' file is already exist and incorrect")

        command_arr = [self.config.get('app', 'platformio_cmd'), 'init', '-d', str(self.path), '-b',
                       self.config.get('project', 'board'), '-O', 'framework=stm32cube']
        if not self.logger.isEnabledFor(logging.DEBUG):
            command_arr.append('--silent')

        result = subprocess.run(command_arr, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        error_msg = "PlatformIO project initialization error"
        if result.returncode == 0:
            # PlatformIO returns 0 even on some errors (e.g. no '--board' argument)
            if 'error' in result.stdout.lower():  # GUESSING
                self.logger.error(result.stdout, extra={ 'from_subprocess': True })
                raise Exception(error_msg)
            self.logger.debug(result.stdout, extra={ 'from_subprocess': True })
            self.logger.info("successful PlatformIO project initialization")
            return result.returncode
        else:
            self.logger.error(f"Return code is {result.returncode}. Output:\n\n{result.stdout}",
                              extra={ 'from_subprocess': True })
            raise Exception(error_msg)


    @property
    def platformio_ini_config(self) -> configparser.ConfigParser:
        """
        Reads and parses the 'platformio.ini' PlatformIO config file into a newly created configparser.ConfigParser
        instance. Note, that the file may change over time and subsequent calls may produce different results because
        of this.

        Raises FileNotFoundError if no 'platformio.ini' file is present. Passes out all other exceptions, most likely
        caused by parsing errors (i.e. corrupted .INI format), e.g.

            configparser.MissingSectionHeaderError: File contains no section headers.

        It doesn't use any interpolation as we do not interested in the particular values, just presence and correctness
        When using this property for comparing, make sure your other config doesn't use the interpolation either so we
        just can match raw unprocessed strings.
        """

        platformio_ini = configparser.ConfigParser(interpolation=None)
        platformio_ini.read(self.path.joinpath('platformio.ini').resolve(strict=True))
        return platformio_ini


    @property
    def platformio_ini_is_patched(self) -> bool:
        """
        Check whether 'platformio.ini' config file is patched or not. It doesn't check for complete project patching
        (e.g. unnecessary folders deletion). Throws errors on non-existing file and on incorrect patch or file.

        Returns:
            boolean indicating a result
        """

        try:
            platformio_ini = self.platformio_ini_config  # existing .ini file
        except FileNotFoundError as e:
            raise Exception("Cannot determine is project patched: 'platformio.ini' file not found") from e
        except Exception as e:
            raise Exception("Cannot determine is project patched: 'platformio.ini' file is incorrect") from e

        patch_config = configparser.ConfigParser(interpolation=None)  # our patch has the INI config format, too
        try:
            patch_config.read_string(self.config.get('project', 'platformio_ini_patch_content'))
        except Exception as e:
            raise Exception("Cannot determine is project patched: desired patch content is invalid (should satisfy "
                            "INI-format requirements)") from e

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
        Patch the 'platformio.ini' config file by a user's patch. By default, it sets the created earlier (by CubeMX
        'Src' and 'Inc') folders as sources specifying it in the [platformio] INI section. configparser doesn't preserve
        any comments unfortunately so keep in mind that all of them will be lost at this stage. Also, the order may be
        violated. In the end, removes an old empty folders.
        """

        self.logger.debug("patching 'platformio.ini' file...")

        if self.platformio_ini_is_patched:
            self.logger.info("'platformio.ini' has been already patched")
        else:
            platformio_ini_config = self.platformio_ini_config  # existing .ini file

            patch_config = configparser.ConfigParser(interpolation=None)  # our patch has the INI config format, too
            patch_config.read_string(self.config.get('project', 'platformio_ini_patch_content'))

            # Merge 2 configs
            for patch_section in patch_config.sections():
                if not platformio_ini_config.has_section(patch_section):
                    self.logger.debug(f"[{patch_section}] section was added")
                    platformio_ini_config.add_section(patch_section)
                for patch_key, patch_value in patch_config.items(patch_section):
                    self.logger.debug(f"set [{patch_section}]{patch_key} = {patch_value}")
                    platformio_ini_config.set(patch_section, patch_key, patch_value)

            # Save, overwriting (node='w') the original file (deletes all comments!)
            with self.path.joinpath('platformio.ini').open(mode='w') as platformio_ini_file:
                platformio_ini_config.write(platformio_ini_file)
                self.logger.debug("'platformio.ini' has been patched")

        try:
            shutil.rmtree(self.path.joinpath('include'))
            self.logger.debug("'include' folder has been removed")
        except Exception:
            self.logger.info("cannot delete 'include' folder", exc_info=self.logger.isEnabledFor(logging.DEBUG))

        # Remove 'src' directory too but on case-sensitive file systems 'Src' == 'src' == 'SRC' so we need to check
        if not self.path.joinpath('SRC').is_dir():
            try:
                shutil.rmtree(self.path.joinpath('src'))
                self.logger.debug("'src' folder has been removed")
            except Exception:
                self.logger.info("cannot delete 'src' folder", exc_info=self.logger.isEnabledFor(logging.DEBUG))

        self.logger.info("project has been patched")


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

        # In the non-verbose mode (logging.INFO) there would be a '--silent' option so if the PlatformIO will decide to
        # output something then it's really important and we use logging.WARNING as a level
        log_level = logging.DEBUG if self.logger.isEnabledFor(logging.DEBUG) else logging.WARNING
        with stm32pio.util.LogPipe(self.logger, log_level) as log:
            result = subprocess.run(command_arr, stdout=log.pipe, stderr=log.pipe)

        if result.returncode == 0:
            self.logger.info("successful PlatformIO build")
        else:
            self.logger.error("PlatformIO build error")
        return result.returncode


    def start_editor(self, editor_command: str) -> int:
        """
        Start the editor specified by the 'editor_command' with a project opened (assuming that
            $ [editor] [folder]
        format works)

        Args:
            editor_command: editor command as you start it in the terminal

        Returns:
            passes a return code of the command
        """

        sanitized_input = shlex.quote(editor_command)

        self.logger.info(f'starting an editor "{sanitized_input}"...')
        try:
            # Works unstable on some Windows 7 systems, but correct on Win10...
            # result = subprocess.run([editor_command, str(self.path)], check=True)
            result = subprocess.run(f"{sanitized_input} {str(self.path)}", shell=True, check=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.logger.debug(result.stdout, extra={ 'from_subprocess': True })

            return result.returncode
        except subprocess.CalledProcessError as e:
            self.logger.error(f"failed to start the editor {sanitized_input}: {e.stdout}")
            return e.returncode


    def clean(self) -> None:
        """
        Clean-up the project folder preserving only an '.ioc' file
        """

        for child in self.path.iterdir():
            if child.name != f"{self.path.name}.ioc":
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                    self.logger.debug(f"del {child}/")
                elif child.is_file():
                    child.unlink()
                    self.logger.debug(f"del {child}")

        self.logger.info("project has been cleaned")
