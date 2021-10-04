"""
Various ways to remove artifacts from the project folder
"""

import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

import stm32pio.core.settings
from stm32pio.core.log import Logger, LogPipe
from stm32pio.core.util import get_folder_contents


# TODO: Python 3.8: also see typing.Protocol (https://stackoverflow.com/a/66056490/7782943)
class ICleanStrategy(ABC):
    """Common interface for different cleaners"""

    def __init__(self, path: Path, logger: Logger, ask_confirmation: bool):
        """
        :param path: working directory
        :param logger: logging.Logger-compatible object
        :param ask_confirmation: if True, the full removal list will be shown and the user will be asked (on CLI)
        to proceed
        """
        self.path = path
        self.logger = logger
        self.ask_confirmation = ask_confirmation

    @abstractmethod
    def clean(self):
        """Concrete implementation"""
        raise NotImplementedError


class DefaultStrategyI(ICleanStrategy):
    """Custom algorithm to perform a cleanup. Can be supplied with an optional ignore list"""

    def __init__(self, path: Path, logger: Logger, ask_confirmation: bool = True, ignore_list: List[Path] = None):
        """
        :param ignore_list: list of *concrete paths* to not remove
        """
        super().__init__(path, logger, ask_confirmation)
        self.ignore_list = ignore_list

    def clean(self):
        """Deletes everything except the ignore list entries"""

        removal_list = get_folder_contents(self.path, ignore_list=self.ignore_list)
        if len(removal_list):
            if self.ask_confirmation:
                removal_str = '\n'.join(f'  {path.relative_to(self.path)}' for path in removal_list)
                while True:
                    reply = input(f"These files/folders will be deleted:\n{removal_str}\nAre you sure? (y/n) ")
                    if reply.lower() in stm32pio.core.settings.yes_options:
                        break
                    elif reply.lower() in stm32pio.core.settings.no_options:
                        return

            for entry in removal_list:
                if entry.is_dir():
                    shutil.rmtree(entry)  # this can delete non-empty directories
                    self.logger.debug(f'del "{entry.relative_to(self.path)}"/')
                elif entry.is_file():
                    entry.unlink()
                    self.logger.debug(f'del "{entry.relative_to(self.path)}"')
            self.logger.info("project has been cleaned")
        else:
            self.logger.info("no files/folders to remove")


class GitStrategyI(ICleanStrategy):
    """Delegate the entire task to the Git. See its docs for ``git clean`` command for more information"""

    def __init__(self, path: Path, logger: Logger, ask_confirmation: bool = True, exe_cmd: str = 'git',
                 clean_args: List[str] = None):
        """
        :param exe_cmd: command or a path to executable
        :param clean_args: ``git clean`` command arguments
        """
        super().__init__(path, logger, ask_confirmation)
        self.exe_cmd = exe_cmd
        self.clean_args = clean_args if clean_args is not None else [
            '-d', '--force',  # recurse into untracked directories
            '-X'              # remove only files ignored by Git
        ]

    def clean(self):
        """Run subprocess with appropriate arguments"""
        # Remove files listed in .gitignore (see git clean --help for more information)
        command = [self.exe_cmd, 'clean'] + self.clean_args
        if self.ask_confirmation:
            command.append('--interactive')
        if not self.logger.isEnabledFor(logging.DEBUG):
            command.append('--quiet')
        with LogPipe(self.logger, logging.INFO) as log:
            # TODO: Python 3.6 compatibility: str(self.path)
            subprocess.run(command, check=True, cwd=str(self.path), stdout=log.pipe, stderr=log.pipe)
        self.logger.info("Done", from_subprocess=True)  # fake
