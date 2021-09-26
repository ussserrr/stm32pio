"""
This module encapsulates logic needed by stm32pio to interact with PlatformIO CLI. It is called ``pio.py`` to prevent
possible import confusions with the real ``platformio.py`` package.
"""

import copy
import json
import logging
import subprocess
import time
import configparser
from io import StringIO
from pathlib import Path
from typing import List

import stm32pio.core.settings
from stm32pio.core.log import LogPipe


class PlatformioINI(configparser.ConfigParser):
    """
    ``platformio.ini`` file is a generic INI-style config and can be parsed using builtin ``configparser`` module. The
    real capabilities of this file implemented by PlatformIO is very sophisticated but for our purposes it is enough to
    use just a basic ``ConfigParser``. This class is intended to be used as a part of ``PlatformIO`` class.
    """

    header = ''
    patch_config_exception = None

    def __init__(self, path: Path, patch_content: str, logger: logging.Logger):
        """
        Majority of properties might become invalid if will be changed after construction so they are intended to be set
        "once and for all" at the construction stage. In case they should be dynamic, one should reimplement them as
        "@property" with proper getters/setters/etc.

        :param path: path to the platformio.ini file. It will NOT be read on initialization but lazy evaluated during
        requested operations
        :param patch_content: INI-style string that should be merged with the platformio.ini file
        :param logger: logging.Logger-compatible object
        """
        self.logger = logger
        self.path = path
        try:
            self.patch_config = configparser.ConfigParser(interpolation=None)
            self.patch_config.read_string(patch_content)
        except Exception as e:
            self.patch_config = None
            self.patch_config_exception = e
        super().__init__(interpolation=None)

    def sync(self) -> None:
        """
        Clean itself and re-read the config from self.path. Store first N consecutive lines starting with ; as a header
        """
        for section in self.sections():
            self.remove_section(section)
        content = self.path.read_text()
        self.read_string(content)
        if not self.header and content.startswith(';'):
            for line in content.splitlines(keepends=True):
                if line.startswith(';'):
                    self.header += line
                else:
                    break

    @property
    def is_initialized(self) -> bool:
        """Config considered to be initialized when the file is present, correct and not empty"""
        self.sync()
        return len(self.sections()) > 0

    @property
    def is_patched(self) -> bool:
        """The config is patched when it contains all pairs from a given earlier patch"""

        if self.patch_config_exception is not None:
            raise Exception("Cannot determine is project patched: desired patch content is invalid (should satisfy "
                            "INI-format requirements)") from self.patch_config_exception

        try:
            if not self.is_initialized:
                self.logger.warning(f"{self.path.name} file is empty")
                return False
        except FileNotFoundError as e:
            raise Exception(f"Cannot determine is project patched: {self.path.name} file not found") from e
        except Exception as e:
            raise Exception(f"Cannot determine is project patched: {self.path.name} file is incorrect") from e

        for patch_section in self.patch_config.sections():
            if self.has_section(patch_section):
                for patch_key, patch_value in self.patch_config.items(patch_section):
                    platformio_ini_value = self.get(patch_section, patch_key, fallback=None)
                    # TODO: #58: strict equality is an unreliable characteristic
                    if platformio_ini_value != patch_value:
                        self.logger.debug(f"[{patch_section}]{patch_key}: patch value is\n  {patch_value}\nbut "
                                          f"{self.path.name} contains\n  {platformio_ini_value}")
                        return False
            else:
                self.logger.debug(f"{self.path.name} has no '{patch_section}' section")
                return False
        return True

    def patch(self) -> None:
        """
        Apply a given earlier patch. This will try to restore the initial platformio.ini header but all other comments
        throughout the file will be lost
        """

        if self.is_patched:
            self.logger.info(f"{self.path.name} has been already patched")
        else:
            self.logger.debug(f"patching {self.path.name} file...")

            # Merge 2 configs
            for patch_section in self.patch_config.sections():
                if not self.has_section(patch_section):
                    self.logger.debug(f"[{patch_section}] section was added")
                    self.add_section(patch_section)
                for patch_key, patch_value in self.patch_config.items(patch_section):
                    self.logger.debug(f"set [{patch_section}]{patch_key} = {patch_value}")
                    self.set(patch_section, patch_key, patch_value)

            fake_file = StringIO()
            self.write(fake_file)
            config_text = fake_file.getvalue()
            restored_header = (self.header + '\n') if self.header else ''
            self.path.write_text(restored_header + config_text[:-1])
            fake_file.close()
            self.logger.debug(f"{self.path.name} has been patched")


class PlatformIO:
    """
    Interface to execute some [related to application] PlatformIO CLI commands. It also creates a PlatformioINI instance
    so the hierarchy is nice-looking and reflects real objects relations.
    """

    def __init__(self, exe_cmd: str, project_path: Path, patch_content: str, logger: logging.Logger):
        """
        :param exe_cmd: PlatformIO CLI command or a path to the executable. This shouldn't be an arbitrary shell command
        :param project_path: Project folder. Typically, same as the stm32pio project directory
        :param patch_content: INI-style string that should be merged with the platformio.ini file
        :param logger: logging.Logger-compatible object
        """
        self.exe_cmd = exe_cmd
        self.project_path = project_path
        self.logger = logger
        self.ini = PlatformioINI(project_path / 'platformio.ini', patch_content, logger)

    def init(self, board: str) -> int:
        """
        Initialize a new project (can also be safely run on an existing project, too). Actual command: ``platformio
        project init``.

        :param board: PlatformIO name of the board (e.g. nucleo_f031k6)
        :return: Return code of the executed command
        """

        self.logger.info("starting PlatformIO project initialization...")

        try:
            if len(self.ini.sections()):
                self.logger.warning(f"{self.ini.path.name} file already exist")
            # else: file is empty – PlatformIO should overwrite it
        except FileNotFoundError:
            pass  # no file – PlatformIO will create it
        except configparser.Error:
            self.logger.warning(f"{self.ini.path.name} file is incorrect, trying to proceed now...")

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
            self.logger.error(f"return code is {completed_process.returncode}. Output:\n\n{completed_process.stdout}",
                              extra={'from_subprocess': True})
            raise Exception(error_msg)

    def build(self) -> int:
        """
        Initiate a build (``platformio run`` command)

        :return: Return code of the executed command
        """

        self.logger.info("starting PlatformIO project build...")

        command_arr = [self.exe_cmd, 'run', '--project-dir', str(self.project_path)]
        if not self.logger.isEnabledFor(logging.DEBUG):
            command_arr.append('--silent')

        # In the non-verbose mode (logging.INFO) there would be a '--silent' option so if the PlatformIO will decide to
        # output something then it's really important and we use logging.WARNING as a level
        log_level = logging.DEBUG if self.logger.isEnabledFor(logging.DEBUG) else logging.WARNING
        with LogPipe(self.logger, log_level) as log:
            completed_process = subprocess.run(command_arr, stdout=log.pipe, stderr=log.pipe)

        if completed_process.returncode == 0:
            self.logger.info("successful PlatformIO build")
        else:
            self.logger.error("PlatformIO build error")

        return completed_process.returncode


_pio_boards_cache: List[str] = []
_pio_boards_cache_fetched_at: float = 0


# TODO: is there some std lib implementation of temp cache?
#  (no, look at 3rd-party alternative: https://github.com/tkem/cachetools, just like lru_cache)
def get_boards(platformio_cmd: str = stm32pio.core.settings.config_default['app']['platformio_cmd']) -> List[str]:
    """
    Obtain the PlatformIO boards list (string identifiers only). As we interested only in STM32 ones, cut off all of the
    others. Additionally, establish a short-time "cache" to prevent the over-flooding with requests to subprocess.

    IMPORTANT NOTE: PlatformIO can go to the Internet from time to time when it decides that its own cache is out of
    date. So it may take a long time to execute.
    """

    global _pio_boards_cache_fetched_at, _pio_boards_cache

    cache_is_empty = len(_pio_boards_cache) == 0
    current_time = time.time()
    cache_is_outdated = current_time - _pio_boards_cache_fetched_at >= stm32pio.core.settings.pio_boards_cache_lifetime

    if cache_is_empty or cache_is_outdated:
        # Windows 7, as usual, correctly works only with shell=True...
        completed_process = subprocess.run(
            f"{platformio_cmd} boards --json-output stm32cube",
            encoding='utf-8', shell=True, stdout=subprocess.PIPE, check=True)
        _pio_boards_cache = [board['id'] for board in json.loads(completed_process.stdout)]
        _pio_boards_cache_fetched_at = current_time

    # Caller can mutate the array and damage our cache so we give it a copy (as the values are strings it is equivalent
    # to the deep copy of this list)
    return copy.copy(_pio_boards_cache)
