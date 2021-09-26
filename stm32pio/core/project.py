"""
Core class representing a single stm32pio project.
"""

import copy
import logging
import pathlib
import shutil
import subprocess
import weakref
from typing import Mapping, Any, Union

import stm32pio.core.log
import stm32pio.core.settings
import stm32pio.core.util
import stm32pio.core.config
import stm32pio.core.cubemx
import stm32pio.core.pio
import stm32pio.core.validate
import stm32pio.core.state


class Stm32pio:
    """
    Main class.

    Represents a single project, encapsulating a file system path to the project (the primary mandatory identifier) and
    some parameters in a configparser .ini file. As stm32pio can be installed via pip and has no global config we also
    storing global parameters (such as Java or STM32CubeMX invoking commands) in this config .ini file so the user can
    specify settings on a per-project basis. The config can be saved in a non-disturbing way automatically on the
    instance destruction (e.g. by garbage collecting it) (use save_on_destruction=True flag), otherwise a user should
    explicitly save the config if he wants to (using config.save() method).

    The typical life-cycle consists of the new project creation, passing mandatory 'dirty_path' argument. Optional
    'parameters' dictionary will be merged into the project config. 'instance_options' controls how the runtime entity
    will behave in some aspects (logging, destructing). Then it is possible to perform API operations.
    """

    INSTANCE_OPTIONS_DEFAULTS = {  # TODO: use Python 3.8 TypedDict (or maybe some other more appropriate feature)
        'save_on_destruction': False,
        'logger': None
    }

    # TODO: is instance_options ugly?
    def __init__(self, dirty_path: Union[str, pathlib.Path], parameters: Mapping[str, Any] = None,
                 instance_options: Mapping[str, Any] = None):
        """
        Args:
            dirty_path: path to the project (required)
            parameters: additional project parameters to set on initialization stage (format is same as for project'
                config (see settings.py), passed values will be merged)
            instance_options:
                some parameters related more to the instance itself rather than a project's "business logic":
                    save_on_destruction (bool=True): register or not the finalizer that saves the config to a file
                    logger (logging.Logger=None): if an external logger is given, it will be used, otherwise the new
                        ProjectLoggerAdapter for 'stm32pio.projects' prefix will be created automatically (unique for
                        every instance)
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
            self.logger = stm32pio.core.log.ProjectLoggerAdapter(underlying_logger, {'project_id': id(self)})

        # The path is a primary entity of the project so we process it first and foremost. Handle 'path/to/proj',
        # 'path/to/proj/', '.', '../proj', etc., make the path absolute and check for existence. Also, the .ioc file can
        # be specified instead of the directory. In this case it is assumed that the parent path is an actual project
        # path and the provided .ioc file is used on a priority basis
        path = pathlib.Path(dirty_path).expanduser().resolve(strict=True)
        explicit_ioc_file_name = None
        if path.is_file() and path.suffix == '.ioc':  # if .ioc file was supplied instead of the directory
            explicit_ioc_file_name = path.name
            path = path.parent
        elif not path.is_dir():
            raise Exception(f"the supplied project path {path} is not a directory. It should be a directory with an "
                            ".ioc file or an .ioc file itself")
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
            exe_cmd=self.config.get('app', 'platformio_cmd'),
            project_path=self.path,
            patch_content=self.config.get('project', 'platformio_ini_patch_content'),
            logger=self.logger
        )

        if len(self.config.get('project', 'cleanup_ignore', fallback='')) == 0:
            # By-default, we preserve only the .ioc file on cleanup
            self.config.set('project', 'cleanup_ignore', self.cubemx.ioc.path.name)

        if len(self.config.get('project', 'last_error', fallback='')):
            self.config.set('project', 'last_error', '')  # reset last error
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
    def state(self) -> 'stm32pio.core.state.ProjectState':
        return stm32pio.core.state.ProjectState(self)

    def save_config(self, parameters: Mapping[str, Mapping[str, Any]] = None) -> int:
        """
        Pass the call to the config instance. This method exist primarily for the consistency in available project
        actions.
        """
        return self.config.save(parameters)

    def generate_code(self) -> int:
        return self.cubemx.generate_code(script_template=self.config.get('project', 'cubemx_script_content'))

    def pio_init(self) -> int:
        return self.platformio.init(board=self.config.get('project', 'board'))

    def patch(self) -> None:
        """
        Patch the 'platformio.ini' config file with a user's patch. By default, it sets the created earlier (by CubeMX
        'Src' and 'Inc') folders as build sources for PlatformIO specifying it in the [platformio] INI section.
        configparser doesn't preserve any comments unfortunately so keep in mind that all of them will be lost at this
        point. Also, the order may be violated. In the end, removes these old empty folders.
        """

        self.platformio.ini.patch()

        stm32pio.core.util.remove_folder(self.path / 'include', logger=self.logger)
        # Remove 'src' directory as well but on case-sensitive file systems 'Src' == 'src' == 'SRC' so we need to check
        if not self.path.joinpath('SRC').is_dir():
            stm32pio.core.util.remove_folder(self.path / 'src', logger=self.logger)

        self.logger.info("project has been patched")

    def build(self) -> int:
        return self.platformio.build()

    def start_editor(self, editor_command: str) -> int:
        return stm32pio.core.util.run_command(editor_command, self.path, self.logger)

    def clean(self, quiet_on_cli: bool = True) -> None:
        """
        Clean-up the project folder. The method uses whether its own algorithm or can delegate the task to the git (`git
        clean` command). This behavior is controlled by the project config's `cleanup_use_git` parameter. Note that the
        results may not be as you initially expected with `git clean`, refer to its docs for clarification if necessary.
        For example, with a fresh new repository you actually need to run `git add --all` first, otherwise nothing will
        be removed by the git.

        Args:
            quiet_on_cli: should the function ask a user (on CLI, currently) before actually removing any file/folder
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

    def inspect_ioc_config(self):
        """
        Check the current .ioc configuration PlatformIO compatibility. MCU matching is not used at the moment as we
        don't have a reliable way to obtain one from the platformio.ini (where it can be possibly specified?)

        :return: None (outputs warnings through the logging module)
        """

        # TODO: use platformio_mcu matching, too
        #  (see https://docs.platformio.org/en/latest/projectconf/section_env_platform.html#board-build-mcu)
        self.cubemx.ioc.inspect(platformio_board=self.config.get('project', 'board'))

    def validate_environment(self) -> stm32pio.core.validate.ToolsValidationResults:
        return stm32pio.core.validate.validate_environment(self.config, self.cubemx, self.logger)
