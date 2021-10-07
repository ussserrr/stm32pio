"""
This module encapsulates logic needed by stm32pio to interact with PlatformIO CLI. It is called ``pio.py`` to prevent
possible import confusions with the real ``platformio.py`` package.
"""

import json
import logging
import subprocess
import configparser
from copy import copy
from io import StringIO
from pathlib import Path
from time import time
from typing import List

import stm32pio.core.log
import stm32pio.core.settings
import stm32pio.core.util


class PlatformioINI(configparser.ConfigParser):
    """
    ``platformio.ini`` file is a generic INI-style config and can be parsed using builtin ``configparser`` module. The
    real capabilities of this file implemented by PlatformIO is very sophisticated but for our purposes it is enough to
    use just a basic ``ConfigParser``. This class is intended to be used as a part of ``PlatformIO`` class.
    """

    header = ''
    patch_config_exception = None

    def __init__(self, path: Path, patch_content: str, logger: stm32pio.core.log.Logger):
        """
        Majority of properties might become invalid if will be changed after construction so they are intended to be set
        "once and for all" at the construction stage. In case they should be dynamic, one should reimplement them as
        ``@property`` with proper getters/setters/etc.

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

    def sync(self) -> int:
        """
        Clean itself and re-read the config from self.path. Store first N consecutive lines starting with ; as a header

        :return: number of sections after readout (excluding DEFAULT)
        """
        for section in self.sections():
            self.remove_section(section)
        content = self.path.read_text()
        self.read_string(content)
        if not self.header:
            self.header = stm32pio.core.util.extract_header_comment(content, comment_symbol=';')
        return len(self.sections())

    @property
    def is_initialized(self) -> bool:
        """Config considered to be initialized when the file is present, correct and not empty"""
        return self.sync() > 0

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

            for patch_section in self.patch_config.sections():  # merge 2 configs
                if not self.has_section(patch_section):
                    self.logger.debug(f"[{patch_section}] section was added")
                    self.add_section(patch_section)
                for patch_key, patch_value in self.patch_config.items(patch_section):
                    self.logger.debug(f"set [{patch_section}]{patch_key} = {patch_value}")
                    self.set(patch_section, patch_key, patch_value)

            fake_file = StringIO()
            self.write(fake_file)
            config_text = fake_file.getvalue()
            self.path.write_text(
                ((self.header + '\n') if self.header else '') +  # restore a header
                config_text[:-1])  # omit trailing \n
            fake_file.close()
            self.logger.debug(f"{self.path.name} has been patched")


class PlatformIO:
    """
    Interface to execute some [related to application] PlatformIO CLI commands. It also creates a PlatformioINI instance
    so the hierarchy is nice-looking and reflects real objects relations.
    """

    def __init__(self, project_path: Path, exe_cmd: str, patch_content: str, logger: stm32pio.core.log.Logger):
        """
        :param exe_cmd: PlatformIO CLI command or a path to the executable. This shouldn't be an arbitrary shell command
        :param project_path: Project folder. Typically, same as the stm32pio project directory
        :param patch_content: INI-style string that should be merged with the platformio.ini file
        :param logger: logging.Logger-compatible object
        """
        self.project_path = project_path
        self.exe_cmd = exe_cmd
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
            if self.ini.sync():
                self.logger.warning(f"{self.ini.path.name} file already exist")
            # else: file is empty – PlatformIO should overwrite it
        except FileNotFoundError:
            pass  # no file – PlatformIO will create it
        except configparser.Error:
            self.logger.warning(f"{self.ini.path.name} file is incorrect, trying to proceed...")

        command_arr = [self.exe_cmd, 'project', 'init',
                       '--project-dir', str(self.project_path),
                       '--board', board,
                       '--project-option', 'framework=stm32cube',
                       '--project-option', 'board_build.stm32cube.custom_config_header=yes']  # see #26
        if not self.logger.isEnabledFor(logging.DEBUG):
            command_arr.append('--silent')

        process = subprocess.run(command_arr, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        error_msg = "PlatformIO project initialization error"
        if process.returncode == 0:  # PlatformIO returns 0 even on some errors (e.g. no '--board' argument)
            if 'error' in process.stdout.lower():  # strictly speaking, here we're just guessing
                self.logger.error(process.stdout, from_subprocess=True)
                raise Exception(error_msg)
            self.logger.debug(process.stdout, from_subprocess=True)
            self.logger.info("successful PlatformIO project initialization")
            return process.returncode
        else:
            self.logger.error(f"return code: {process.returncode}. Output:\n\n{process.stdout}",  from_subprocess=True)
            raise Exception(error_msg)

    def build(self) -> int:
        """
        Initiate a build (``platformio run`` command).

        :return: Return code of the executed command
        """

        self.logger.info("starting PlatformIO project build...")

        command_arr = [self.exe_cmd, 'run', '--project-dir', str(self.project_path)]

        log_level = logging.DEBUG
        if not self.logger.isEnabledFor(logging.DEBUG):
            command_arr.append('--silent')
            log_level = logging.WARNING  # in silent mode PlatformIO producing only warnings, if any

        with stm32pio.core.log.LogPipe(self.logger, log_level) as log:
            process = subprocess.run(command_arr, stdout=log.pipe, stderr=log.pipe)

        if process.returncode == 0:
            self.logger.info("successful PlatformIO build")
        else:
            self.logger.error("PlatformIO build error")

        return process.returncode


_pio_boards_cache: List[str] = []
_pio_boards_cache_fetched_at: float = 0


# TODO: probably some lock should be acquired preventing of more than 1 execution at a time (e.g. from threads)
# Is there some std lib implementation of temp cache? No, look at 3rd-party alternative, just like lru_cache:
# https://github.com/tkem/cachetools
def get_boards(platformio_cmd: str = stm32pio.core.settings.config_default['app']['platformio_cmd']) -> List[str]:
    """
    Obtain PlatformIO boards list (string identifiers only). As we interested only in STM32 ones, cut off all of the
    others. Additionally, establish a short-time "cache" for quick serving of sequential calls.

    IMPORTANT NOTE: PlatformIO can go online from time to time when decided that its own cache is out of
    date. So it may take some time to execute on the first run after a long break.

    :param platformio_cmd: path or command of PlatformIO executable
    :return: list of STM32 PlatformIO boards codes
    """

    global _pio_boards_cache_fetched_at, _pio_boards_cache

    cache_is_empty = len(_pio_boards_cache) == 0
    current_time = time()
    cache_is_outdated = current_time - _pio_boards_cache_fetched_at >= stm32pio.core.settings.pio_boards_cache_lifetime

    if cache_is_empty or cache_is_outdated:
        process = subprocess.run([platformio_cmd, 'boards', '--json-output', 'stm32cube'],
                                 stdout=subprocess.PIPE, check=True)
        _pio_boards_cache = [board['id'] for board in json.loads(process.stdout)]
        _pio_boards_cache_fetched_at = current_time

    # We don't know what a caller will ended up doing with that list. Simple copy is a sufficient solution for us since
    # copy(list[string]) basically equals deepcopy(list[string]) as strings are immutable in Python
    return copy(_pio_boards_cache)
