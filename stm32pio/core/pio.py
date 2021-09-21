import logging
import shutil
import subprocess
from configparser import ConfigParser
from pathlib import Path

import stm32pio.core.log
import stm32pio.core.settings


class PlatformioINI(ConfigParser):
    def __init__(self, path: Path, patch_content: str, logger: logging.Logger):
        # TODO: save comments header (see IOC parsing)
        self.logger = logger
        self.path = path
        try:
            self.patch_config = ConfigParser(interpolation=None)  # our patch has the INI config format, too
            self.patch_config.read_string(patch_content)
        except Exception as e:
            self.patch_config = None
            self.patch_config_exception = e
        else:
            self.patch_config_exception = None
        super().__init__(interpolation=None)

    def sync(self):
        for section in self.sections():
            self.remove_section(section)
        self.path.resolve(strict=True)  # existing .ini file
        self.read(self.path)

    @property
    def is_initialized(self):
        """Is present, is correct and is not empty"""
        self.sync()
        return len(self.sections()) > 0

    @property
    def is_patched(self) -> bool:
        """
        Check whether 'platformio.ini' config file is patched or not. It doesn't check for complete project patching
        (e.g. unnecessary folders deletion).

        Returns:
            boolean indicating a result

        Raises:
            throws errors on non-existing file and on incorrect patch/file
        """

        try:
            if not self.is_initialized:
                self.logger.warning('platformio.ini file is empty')
        except FileNotFoundError as e:
            raise Exception("Cannot determine is project patched: 'platformio.ini' file not found") from e
        except Exception as e:
            raise Exception("Cannot determine is project patched: 'platformio.ini' file is incorrect") from e

        if self.patch_config_exception is not None:
            raise Exception("Cannot determine is project patched: desired patch content is invalid (should satisfy "
                            "INI-format requirements)") from self.patch_config_exception

        for patch_section in self.patch_config.sections():
            if self.has_section(patch_section):
                for patch_key, patch_value in self.patch_config.items(patch_section):
                    platformio_ini_value = self.get(patch_section, patch_key, fallback=None)
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
        Patch the 'platformio.ini' config file with a user's patch. By default, it sets the created earlier (by CubeMX
        'Src' and 'Inc') folders as build sources for PlatformIO specifying it in the [platformio] INI section.
        configparser doesn't preserve any comments unfortunately so keep in mind that all of them will be lost at this
        point. Also, the order may be violated. In the end, removes these old empty folders.
        """

        if self.is_patched:
            self.logger.info("'platformio.ini' has been already patched")
        else:
            self.logger.debug("patching 'platformio.ini' file...")

            # for s in self.sections():
            #     print(f'[{s}]')
            #     for k, v in self[s].items():
            #         print(f'{k}: {v}')
            #     print()
            # Merge 2 configs
            for patch_section in self.patch_config.sections():
                if not self.has_section(patch_section):
                    self.logger.debug(f"[{patch_section}] section was added")
                    self.add_section(patch_section)
                for patch_key, patch_value in self.patch_config.items(patch_section):
                    self.logger.debug(f"set [{patch_section}]{patch_key} = {patch_value}")
                    self.set(patch_section, patch_key, patch_value)

            # Save, overwriting (mode='w') the original file (deletes all comments!)
            with self.path.open(mode='w') as platformio_ini_file:
                self.write(platformio_ini_file)
                self.logger.debug("'platformio.ini' has been patched")

        try:
            shutil.rmtree(self.path.parent / 'include')
            self.logger.debug("'include' folder has been removed")
        except Exception:
            self.logger.info("cannot delete 'include' folder",
                             exc_info=self.logger.isEnabledFor(stm32pio.core.settings.show_traceback_threshold_level))

        # Remove 'src' directory too but on case-sensitive file systems 'Src' == 'src' == 'SRC' so we need to check
        if not self.path.parent.joinpath('SRC').is_dir():
            try:
                shutil.rmtree(self.path.parent / 'src')
                self.logger.debug("'src' folder has been removed")
            except Exception:
                self.logger.info("cannot delete 'src' folder", exc_info=
                                 self.logger.isEnabledFor(stm32pio.core.settings.show_traceback_threshold_level))

        self.logger.info("project has been patched")


class PlatformIO:
    def __init__(self, exe_cmd: str, project_path: Path, patch_content: str, logger: logging.Logger):
        self.exe_cmd = exe_cmd
        self.project_path = project_path
        self.logger = logger
        self.ini = PlatformioINI(project_path / 'platformio.ini', patch_content, logger)

    def init(self, board: str) -> int:
        """
        Call PlatformIO CLI to initialize a new project. It uses parameters (path, board) collected earlier so the
        confirmation about data presence is lying on the invoking code.

        Returns:
            return code of the PlatformIO

        Raises:
            Exception: if the return code of subprocess is not 0
        """

        self.logger.info("starting PlatformIO project initialization...")

        try:
            if len(self.ini.sections()):
                self.logger.warning("'platformio.ini' file already exist")
            # else: file is empty (PlatformIO should overwrite it)
        except FileNotFoundError:
            pass  # no file, see above
        except Exception:
            self.logger.warning("'platformio.ini' file is incorrect")

        command_arr = [self.exe_cmd, 'project', 'init',
                       '--project-dir', str(self.project_path),
                       '--board', board,
                       '--project-option', 'framework=stm32cube']
        if not self.logger.isEnabledFor(logging.DEBUG):
            command_arr.append('--silent')

        completed_process = subprocess.run(command_arr, encoding='utf-8',
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        error_msg = "PlatformIO project initialization error"
        if completed_process.returncode == 0:
            # PlatformIO returns 0 even on some errors (e.g. no '--board' argument)
            if 'error' in completed_process.stdout.lower():  # guessing
                self.logger.error(completed_process.stdout, extra={'from_subprocess': True})
                raise Exception(error_msg)
            self.logger.debug(completed_process.stdout, extra={'from_subprocess': True})
            self.logger.info("successful PlatformIO project initialization")
            return completed_process.returncode
        else:
            self.logger.error(f"Return code is {completed_process.returncode}. Output:\n\n{completed_process.stdout}",
                              extra={'from_subprocess': True})
            raise Exception(error_msg)

    def build(self) -> int:
        """
        Initiate a build by the PlatformIO ('platformio run' command)

        Returns:
            passes a return code of the PlatformIO
        """

        self.logger.info("starting PlatformIO project build...")

        command_arr = [self.exe_cmd, 'run', '--project-dir', str(self.project_path)]
        if not self.logger.isEnabledFor(logging.DEBUG):
            command_arr.append('--silent')

        # In the non-verbose mode (logging.INFO) there would be a '--silent' option so if the PlatformIO will decide to
        # output something then it's really important and we use logging.WARNING as a level
        log_level = logging.DEBUG if self.logger.isEnabledFor(logging.DEBUG) else logging.WARNING
        with stm32pio.core.log.LogPipe(self.logger, log_level) as log:
            completed_process = subprocess.run(command_arr, stdout=log.pipe, stderr=log.pipe)

        if completed_process.returncode == 0:
            self.logger.info("successful PlatformIO build")
        else:
            self.logger.error("PlatformIO build error")

        return completed_process.returncode
