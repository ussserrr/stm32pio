"""
Core class representing a single STM32CubeMX + PlatformIO project. This interface should be sufficient enough for most
3rd-party applications (CLI, GUI, embedding, ...).
"""

import copy
import logging
import shutil
import subprocess
import weakref
from os import PathLike
from pathlib import Path
from typing import Mapping, Any

import stm32pio.core.config
import stm32pio.core.cubemx
import stm32pio.core.log
import stm32pio.core.pio
import stm32pio.core.settings
import stm32pio.core.state
import stm32pio.core.util
import stm32pio.core.validate


class Stm32pio:
    """
    Main class reflects a single stm32pio project. Normally, this will automatically set such members for you:
      ``logger`` – powerful and flexible tool on top of the builtin ``logging`` module providing to client code all
        possible features it might need. In case this is not enough it can be easily overridden on initialization.
        This is your primary source of getting a feedback from the internals about the project state and operations.
        Default implementation will use builtin id() procedure creating a unique identifier allowing to distinguish
        several projects on logging events
        Refer to: ``log.py``
      ``config`` – tweaked ``ConfigParser`` instance containing merged settings from multiple sources.
        Refer to: ``config.py``
      ``cubemx``, ``platformio`` – service classes handling requests to corresponding programs when there is a need to.
        See ``cubemx.py``, ``pio.py``
    Most of the times you'll ended up using only methods and not touching these attributes manually. Majority of methods
    are just thin wrappers around some other module – it helps both in leaner architecture and providing convenient set
    of available actions (i.e. user needs to know only the single interface to leverage whole functionality and an
    action can be invoked even having only a name of it – by utilizing getattr())
    """

    def __init__(self, path: PathLike, parameters: Mapping = None, save_on_destruction: bool = False,
                 logger: stm32pio.core.log.Logger = None):
        """
        Minimal requirement for the file system directory to be considered as project is to have a CubeMX .ioc file so
        it (or its containing directory) is the primary identifier that should be supplied on initialization. In case of
        multiple .ioc files at one folder, the given one or the first available will be picked.

        :param path: relative or absolute path to the .ioc file or its parent
        :param parameters: config-compatible parameters mapping to merge
        :param save_on_destruction: if True, the config will be flushed to file automatically on instance destruction
        :param logger: override an internal logger
        """

        if logger is not None:
            self.logger = logger
        else:
            # Individual loggers for every single project allows to fine-tune the output when multiple projects are
            # created by some client code. Here we utilize id() for this
            underlying_logger = logging.getLogger('stm32pio.projects')
            self.logger = stm32pio.core.log.ProjectLoggerAdapter(underlying_logger, {'project_id': id(self)})

        path = Path(path).expanduser().resolve(strict=True)
        explicit_ioc_file_name = None
        if path.is_file() and path.suffix == '.ioc':  # if .ioc file was supplied instead of the directory
            explicit_ioc_file_name = path.name
            path = path.parent
        elif not path.is_dir():
            raise ValueError(f"project path '{path}' is incorrect. It should be a directory with an .ioc file or"
                             "an .ioc file itself")
        self.path = path

        self.config = stm32pio.core.config.Config(self.path, runtime_parameters=parameters, logger=self.logger)

        self.cubemx = stm32pio.core.cubemx.CubeMX(
            work_dir=self.path,
            ioc_file_name=explicit_ioc_file_name or self.config.get('project', 'ioc_file'),
            exe_cmd=self.config.get('app', 'cubemx_cmd'),
            java_cmd=self.config.get('app', 'java_cmd'),
            logger=self.logger
        )
        self.config.set('project', 'ioc_file', self.cubemx.ioc.path.name)  # save only the name of file to the config

        self.platformio = stm32pio.core.pio.PlatformIO(
            project_path=self.path,
            exe_cmd=self.config.get('app', 'platformio_cmd'),
            patch_content=self.config.get('project', 'platformio_ini_patch_content'),
            logger=self.logger
        )

        if not len(self.config.get('project', 'cleanup_ignore', fallback='')):
            # By-default, we preserve only the .ioc file on cleanup
            self.config.set('project', 'cleanup_ignore', self.cubemx.ioc.path.name)

        if len(self.config.get('project', 'last_error', fallback='')):
            self.config.set('project', 'last_error', '')  # reset last error
            self.config.save()

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"resolved config:\n{self.config}")

        if save_on_destruction:
            self._finalizer = weakref.finalize(self, self.config.save)

    def __repr__(self) -> str:
        """Short string representation of the project – just use an absolute path"""
        return f"Stm32pio project: {self.path}"

    @property
    def state(self) -> 'stm32pio.core.state.ProjectState':
        """Getter for the read-only ``state`` attribute. Evaluate, construct and return the project state"""
        return stm32pio.core.state.ProjectState(self)

    def save_config(self, parameters: Mapping[str, Mapping[str, Any]] = None) -> int:
        """
        Flush the config to its associated file.

        :param parameters: mapping to merge into the result
        :return: 0 on success, -1 otherwise
        """
        return self.config.save(parameters)

    def generate_code(self) -> int:
        """
        Invoke CubeMX with the predefined script.

        :return: subprocess return code
        """
        return self.cubemx.generate_code(script_template=self.config.get('project', 'cubemx_script_content'))

    def pio_init(self) -> int:
        """
        Invoke PlatformIO CLI to setup a new project with appropriate parameters.

        :return: subprocess return code
        """
        return self.platformio.init(board=self.config.get('project', 'board'))

    def patch(self) -> None:
        """
        Tweak resources in the way PlatformIO will understand the CubeMX project structure:
          - merge platformio.ini with provided patch config
          - remove default directories
        **Note:** this operation does not preserve comments both from platformio.ini an patch content so make sure
        you've saved all meaningful information somewhere else. Also, the order may be left violated.
        """

        self.platformio.ini.patch()

        stm32pio.core.util.remove_folder(self.path / 'include', logger=self.logger)
        # Remove 'src' directory as well but on case-sensitive file systems 'Src' == 'src' == 'SRC' so we need to check
        if not self.path.joinpath('SRC').is_dir():
            stm32pio.core.util.remove_folder(self.path / 'src', logger=self.logger)

        self.logger.info("project has been patched")

    def build(self) -> int:
        """
        Initiate PlatformIO build attempt (``platformio run`` command).

        :return: subprocess return code
        """
        return self.platformio.build()

    def start_editor(self, editor_command: str) -> int:
        """
        Execute a simple command line instruction to launch the editor.

        :param editor_command: how do you start your editor? Passing options is allowed
        :return: subprocess return code
        """
        return stm32pio.core.util.run_command(editor_command, self.path, self.logger)

    def clean(self, quiet_on_cli: bool = True) -> None:
        """
        Clean-up the project folder. The method uses whether its own algorithm or can delegate the task to git (``git
        clean`` command). This behavior is controlled by the project config's ``cleanup_use_git`` option. Note that the
        results may not be as you initially expected with ``git clean``, refer to its docs for clarification. For
        example, with a fresh new repository given, you actually need to run ``git add --all`` first, otherwise nothing
        will be removed by git.

        :param quiet_on_cli: should the function ask a user (on CLI, currently) before actually removing any file/folder
        """

        if self.config.getboolean('project', 'cleanup_use_git', fallback=False):
            self.logger.info("'cleanup_use_git' option is true, git will be used to perform the cleanup...")
            # Remove files listed in .gitignore
            args = ['git', 'clean', '-d', '--force', '-X']
            if not quiet_on_cli:
                args.append('--interactive')
            if not self.logger.isEnabledFor(logging.DEBUG):
                args.append('--quiet')
            with stm32pio.core.log.LogPipe(self.logger, logging.INFO) as log:
                # TODO: str(self.path) - 3.6 compatibility
                subprocess.run(args, check=True, cwd=str(self.path), stdout=log.pipe, stderr=log.pipe)
            self.logger.info("Done", extra={'from_subprocess': True})
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

    def inspect_ioc_config(self) -> None:
        """
        Check the current .ioc configuration PlatformIO compatibility. MCU matching is not used at the moment as we
        don't have a reliable way to obtain one from the platformio.ini (where it can be possibly specified?)
        """
        # TODO: use platformio_mcu matching, too
        #  (see https://docs.platformio.org/en/latest/projectconf/section_env_platform.html#board-build-mcu)
        self.cubemx.ioc.inspect(platformio_board=self.config.get('project', 'board'))

    def validate_environment(self) -> stm32pio.core.validate.ToolsValidationResults:
        """
        Verify CLI tools specified in the "app" config section.

        :return: results in the form suitable fpr printing
        """
        return stm32pio.core.validate.validate_environment(self.config, self.cubemx, self.logger)
