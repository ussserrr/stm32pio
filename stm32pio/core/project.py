"""
Core library
"""

import collections
import configparser
import contextlib
import copy
import logging
import pathlib
import shlex
import shutil
import string
import subprocess
import tempfile
import weakref
from typing import Mapping, Any, Union, Tuple

import stm32pio.core.logging
import stm32pio.core.settings
import stm32pio.core.util
import stm32pio.core.validate
import stm32pio.core.config
from stm32pio.core.state import ProjectStage, ProjectState


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
            self.logger = stm32pio.core.logging.ProjectLoggerAdapter(underlying_logger, {'project_id': id(self)})

        # The path is a primary entity of the project so we process it first and foremost. Handle 'path/to/proj',
        # 'path/to/proj/', '.', '../proj', etc., make the path absolute and check for existence. Also, the .ioc file can
        # be specified instead of the directory. In this case it is assumed that the parent path is an actual project
        # path and the provided .ioc file is used on a priority basis
        path = pathlib.Path(dirty_path).expanduser().resolve(strict=True)
        ioc_file = None
        if path.is_file() and path.suffix == '.ioc':  # if .ioc file was supplied instead of the directory
            ioc_file = path
            path = path.parent
        elif not path.is_dir():
            raise Exception(f"the supplied project path {path} is not a directory. It should be a directory with an "
                            ".ioc file or an .ioc file itself")
        self.path = path

        self.config = stm32pio.core.config.Config(self.path, runtime_parameters=parameters, logger=self.logger)

        self.ioc_file = self._find_ioc_file(explicit_file=ioc_file)
        self.config.set('project', 'ioc_file', self.ioc_file.name)  # save only the name of file to the config

        if len(self.config.get('project', 'cleanup_ignore', fallback='')) == 0:
            # By-default, we preserve only the .ioc file on cleanup
            self.config.set('project', 'cleanup_ignore', self.ioc_file.name)

        if len(self.config.get('project', 'last_error', fallback='')):  # only if the config file already exist
            self.config.set('project', 'last_error', '')
            self.config.save()

        # Put away unnecessary processing as the string still will be formed even if the logging level doesn't allow a
        # propagation of this message
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"resolved config:\n{self.config}")

        # Save the config on an instance destruction
        if instance_options['save_on_destruction']:
            self._finalizer = weakref.finalize(self, self.config.save)


    def __repr__(self):
        """String representation of the project (use an absolute path for this)"""
        return f"Stm32pio project: {self.path}"


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
        stages_conditions[ProjectStage.INITIALIZED] = [self.path.joinpath(stm32pio.core.settings.config_file_name).is_file()]
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
                    self.logger.debug(f"'{candidates[0].name}' is selected")
                    result_file = candidates[0]
                else:
                    self.logger.warning(f"there are multiple .ioc files, '{candidates[0].name}' is selected")
                    result_file = candidates[0]

        # Check for the file correctness
        try:
            content = result_file.read_text()  # should be a text file
            if len(content) == 0:
                raise ValueError("the file is empty")
            return result_file
        except Exception as e:
            raise Exception(f"{result_file.name} is incorrect") from e


    def save_config(self, parameters: Mapping[str, Mapping[str, Any]] = None) -> int:
        """
        Pass the call to the config instance. This method exist mainly for the consistency in available project actions.
        """
        return self.config.save(parameters)


    def _cubemx_execute_script(self, script_content: str) -> Tuple[subprocess.CompletedProcess, str]:
        # Use mkstemp() instead of the higher-level API for the compatibility with the Windows (see tempfile docs for
        # more details)
        cubemx_script_file, cubemx_script_name = tempfile.mkstemp()

        # We must remove the temp directory, so do not let any exception break our plans
        try:
            # buffering=0 leads to the immediate flushing on writing
            with open(cubemx_script_file, mode='w+b', buffering=0) as cubemx_script:
                cubemx_script.write(script_content.encode())  # should encode, since mode='w+b'

                command_arr = []
                java_cmd = self.config.get('app', 'java_cmd')
                # CubeMX can be invoked directly, without a need in Java command
                if java_cmd and (java_cmd.lower() not in stm32pio.core.settings.none_options):
                    command_arr += [java_cmd, '-jar']
                # -q: read the commands from the file, -s: silent performance
                command_arr += [self.config.get('app', 'cubemx_cmd'), '-q', cubemx_script_name, '-s']
                # Redirect the output of the subprocess into the logging module (with DEBUG level)
                with stm32pio.core.logging.LogPipe(self.logger, logging.DEBUG) as log:
                    result = subprocess.run(command_arr, stdout=log.pipe, stderr=log.pipe)
                    result_output = log.value

        except Exception as e:
            raise e  # re-raise an exception after the 'finally' block
        else:
            return result, result_output
        finally:
            pathlib.Path(cubemx_script_name).unlink()


    def generate_code(self) -> int:
        """
        Call STM32CubeMX app as 'java -jar' file to generate the code from the .ioc file. Pass the commands to the
        STM32CubeMX in a temp file.

        Returns:
            return code on success, raises an exception otherwise
        """

        self.logger.info("starting to generate a code from the CubeMX .ioc file...")

        cubemx_script_template = string.Template(self.config.get('project', 'cubemx_script_content'))
        # It's important to wrap paths into quotation marks as they can contain spaces
        cubemx_script_content = cubemx_script_template.substitute(ioc_file_absolute_path=f'"{self.ioc_file}"',
                                                                  project_dir_absolute_path=f'"{self.path}"')
        result, result_output = self._cubemx_execute_script(cubemx_script_content)

        error_msg = "code generation error"
        if result.returncode == 0:
            if stm32pio.core.settings.cubemx_str_indicating_success in result_output:
                self.logger.info("successful code generation")
                return result.returncode
            else:  # guessing
                error_lines = [line for line in result_output.splitlines(keepends=True)
                               if stm32pio.core.settings.cubemx_str_indicating_error in line]
                if len(error_lines):
                    self.logger.error(error_lines, extra={ 'from_subprocess': True })
                    raise Exception(error_msg)
                else:
                    self.logger.warning("Undefined result from the CubeMX (neither error or success symptoms were "
                                        "found in the logs). Keep going but there might be an error")
                    return result.returncode
        else:
            # Most likely the 'java' error (e.g. no CubeMX is present)
            self.logger.error(f"Return code is {result.returncode}", extra={ 'from_subprocess': True })
            if not self.logger.isEnabledFor(logging.DEBUG):
                # In DEBUG mode the output has already been printed
                self.logger.error(f"Output:\n{result_output}", extra={ 'from_subprocess': True })
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

        command_arr = [self.config.get('app', 'platformio_cmd'), 'project', 'init',
                       '--project-dir', str(self.path),
                       '--board', self.config.get('project', 'board'),
                       '--project-option', 'framework=stm32cube']
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

        if self.platformio_ini_is_patched:
            self.logger.info("'platformio.ini' has been already patched")
        else:
            self.logger.debug("patching 'platformio.ini' file...")

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

            # Save, overwriting (mode='w') the original file (deletes all comments!)
            with self.path.joinpath('platformio.ini').open(mode='w') as platformio_ini_file:
                platformio_ini_config.write(platformio_ini_file)
                self.logger.debug("'platformio.ini' has been patched")

        try:
            shutil.rmtree(self.path.joinpath('include'))
            self.logger.debug("'include' folder has been removed")
        except Exception:
            self.logger.info("cannot delete 'include' folder",
                             exc_info=self.logger.isEnabledFor(stm32pio.core.settings.show_traceback_threshold_level))

        # Remove 'src' directory too but on case-sensitive file systems 'Src' == 'src' == 'SRC' so we need to check
        if not self.path.joinpath('SRC').is_dir():
            try:
                shutil.rmtree(self.path.joinpath('src'))
                self.logger.debug("'src' folder has been removed")
            except Exception:
                self.logger.info("cannot delete 'src' folder", exc_info=
                                 self.logger.isEnabledFor(stm32pio.core.settings.show_traceback_threshold_level))

        self.logger.info("project has been patched")


    def build(self) -> int:
        """
        Initiate a build of the PlatformIO project by the PlatformIO ('run' command). PlatformIO prints warning and
        error messages by itself to the STDERR so there is no need to catch it and output by us

        Returns:
            passes a return code of the PlatformIO
        """

        self.logger.info("starting PlatformIO project build...")

        command_arr = [self.config.get('app', 'platformio_cmd'), 'run', '--project-dir', str(self.path)]
        if not self.logger.isEnabledFor(logging.DEBUG):
            command_arr.append('--silent')

        # In the non-verbose mode (logging.INFO) there would be a '--silent' option so if the PlatformIO will decide to
        # output something then it's really important and we use logging.WARNING as a level
        log_level = logging.DEBUG if self.logger.isEnabledFor(logging.DEBUG) else logging.WARNING
        with stm32pio.core.logging.LogPipe(self.logger, log_level) as log:
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

        self.logger.info(f"starting an editor '{sanitized_input}'...")
        try:
            with stm32pio.core.logging.LogPipe(self.logger, logging.DEBUG) as log:
                # Works unstable on some Windows 7 systems, but correct on Win10...
                # result = subprocess.run([editor_command, self.path], check=True)
                result = subprocess.run(f'{sanitized_input} "{self.path}"', shell=True, check=True,
                                        stdout=log.pipe, stderr=log.pipe)
            self.logger.debug(result.stdout, extra={ 'from_subprocess': True })

            return result.returncode
        except subprocess.CalledProcessError as e:
            self.logger.error(f"failed to start the editor '{sanitized_input}': {e.stdout}")
            return e.returncode


    def clean(self, quiet_on_cli: bool = True) -> None:
        """
        Clean-up the project folder. The method uses whether its own algorithm or can delegate the task to the git (`git
        clean` command). This behavior is controlled by the project config's `cleanup_use_gitignore` parameter. Note
        that the results may not be as you initially expected with `git clean`, refer to its docs for clarification. For
        example, with a fresh new repository you actually need to run `git add --all` first otherwise nothing will be
        removed by the git.

        Args:
            quiet_on_cli: should the function ask a user before actually removing any file/folder
        """

        if self.config.getboolean('project', 'cleanup_use_gitignore', fallback=False):
            self.logger.info("'cleanup_use_gitignore' option is true, git will be used to perform the cleanup...")
            # Remove files listed in .gitignore
            args = ['git', 'clean', '-d', '--force', '-X']
            if not quiet_on_cli:
                args.append('--interactive')
            if not self.logger.isEnabledFor(logging.DEBUG):
                args.append('--quiet')
            with stm32pio.core.logging.LogPipe(self.logger, logging.INFO) as log:
                subprocess.run(args, check=True, cwd=str(self.path), stdout=log.pipe, stderr=log.pipe)  # TODO: str() - 3.6 compatibility
            self.logger.info("Done", extra={ 'from_subprocess': True })
        else:
            removal_list = stm32pio.core.util.get_folder_contents(
                self.path, ignore_list=self.config.get_ignore_list('project', 'cleanup_ignore'))
            if len(removal_list):
                if not quiet_on_cli:
                    removal_str = '\n'.join(f'  {path.relative_to(self.path)}' for path in removal_list)
                    while True:
                        reply = input(f"These files/folders will be deleted:\n{removal_str}\nAre you sure? (y/n) ")
                        if reply.lower() in stm32pio.core.settings.yes_options:
                            break
                        elif reply.lower() in stm32pio.core.settings.no_options:
                            return

                for entry in removal_list:
                    if entry.is_dir():
                        shutil.rmtree(entry)  # use shutil.rmtree() to delete non-empty directories
                        self.logger.debug(f'del "{entry.relative_to(self.path)}"/')
                    elif entry.is_file():
                        entry.unlink()
                        self.logger.debug(f'del "{entry.relative_to(self.path)}"')
                self.logger.info("project has been cleaned")
            else:
                self.logger.info("no files/folders to remove")


    def validate_environment(self) -> stm32pio.core.validate.ToolsValidationResults:
        """Verify tools specified in the 'app' section of the current configuration"""

        def java_runner(java_cmd):
            with stm32pio.core.logging.LogPipe(self.logger, logging.DEBUG) as log:
                java = subprocess.run([java_cmd, '-version'], stdout=log.pipe, stderr=log.pipe)
                java_output = log.value
            return java, java_output

        def cubemx_runner(_):
            return self._cubemx_execute_script('exit\n')  # just start and exit

        def platformio_runner(platformio_cmd):
            with stm32pio.core.logging.LogPipe(self.logger, logging.DEBUG) as log:
                platformio = subprocess.run([platformio_cmd], stdout=log.pipe, stderr=log.pipe)
                platformio_output = log.value
            return platformio, platformio_output


        return stm32pio.core.validate.ToolsValidationResults(
            stm32pio.core.validate.ToolValidator(
                param,
                self.config.get('app', param),
                runner,
                required,
                self.logger
            ).validate() for param, runner, required in [
                ('java_cmd', java_runner, False),
                ('cubemx_cmd', cubemx_runner, True),
                ('platformio_cmd', platformio_runner, True)
            ])
