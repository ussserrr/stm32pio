"""
Some auxiliary entities not falling into other categories
"""

import collections
import json
import logging
import os
import subprocess
import sys
import threading
import traceback
import warnings
from typing import Any, List, Mapping, MutableMapping, Tuple, Optional

module_logger = logging.getLogger(__name__)


def log_current_exception(logger: logging.Logger, show_traceback_threshold_level=logging.DEBUG):
    """Print format is: ExceptionName: message"""
    logger.exception(traceback.format_exception_only(*(sys.exc_info()[:2]))[-1],
                     exc_info=logger.isEnabledFor(show_traceback_threshold_level))


class ProjectLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> Tuple[Any, MutableMapping[str, Any]]:
        if 'extra' in kwargs:
            kwargs['extra'].update(self.extra)
        else:
            kwargs['extra'] = self.extra
        return msg, kwargs


logging_levels = {
    logging.getLevelName(logging.CRITICAL): logging.CRITICAL,
    logging.getLevelName(logging.ERROR): logging.ERROR,
    logging.getLevelName(logging.WARNING): logging.WARNING,
    logging.getLevelName(logging.INFO): logging.INFO,
    logging.getLevelName(logging.DEBUG): logging.DEBUG,
    logging.getLevelName(logging.NOTSET): logging.NOTSET
}

verbosity_levels = collections.OrderedDict(
    normal=0,
    verbose=1
)

# Do not add or remove any information from the message and simply pass it "as-is"
as_is_formatter = logging.Formatter('%(message)s')
special_formatters = {
    'from_subprocess': {
        level: as_is_formatter for level in verbosity_levels.values()
    }
}


class DispatchingFormatter(logging.Formatter):
    """
    The wrapper around the ordinary logging.Formatter allowing to have multiple formatters for different purposes.
    'extra' argument of the log() function has a similar intention but different mechanics
    """

    def __init__(self, *args, general: Mapping[int, logging.Formatter] = None,
                 special: Mapping[str, Mapping[int, logging.Formatter]] = None, verbosity: int = 0, **kwargs):

        super().__init__(*args, **kwargs)  # will be '%(message)s' if no arguments were given

        self.verbosity = verbosity

        if general is not None:
            self.general = general
        else:
            warnings.warn("'general' argument is for providing the custom formatters for all the logging events except "
                          "special ones and should be a dict with verbosity levels keys and logging.Formatter values")
            self.general = {}

        if special is not None:
            self.special = special
        else:
            # warnings.warn("'special' argument is for providing the custom formatters for the special logging events "
            #               "and should be a dict with cases names keys and described above dict values")
            self.special = special_formatters

        self._warn_was_shown = False

    @property
    def verbosity(self):
        return self._verbosity

    @verbosity.setter
    def verbosity(self, value):
        verbosity_levels_values = list(verbosity_levels.values())
        if value < verbosity_levels_values[0]:
            self._verbosity = verbosity_levels_values[0]
        elif value > verbosity_levels_values[-1]:
            self._verbosity = verbosity_levels_values[-1]
        else:
            self._verbosity = value


    def find_formatter_for(self, record: logging.LogRecord, verbosity: int) -> Optional[logging.Formatter]:
        special_formatter = next((self.special[case] for case in self.special.keys() if hasattr(record, case)), None)
        if special_formatter is not None:
            return special_formatter.get(verbosity)
        else:
            return self.general.get(verbosity)


    def format(self, record: logging.LogRecord) -> str:
        """
        Use suitable formatter based on the LogRecord attributes
        """

        formatter = self.find_formatter_for(record, record.verbosity if hasattr(record, 'verbosity') else self.verbosity)

        if formatter is not None:
            return formatter.format(record)
        else:
            if not self._warn_was_shown:
                self._warn_was_shown = True
                module_logger.warning("No formatter found, use default one hereinafter")
            return super().format(record)


class LogPipeRC:
    """
    Small class suitable for passing to the caller when the LogPipe context manager is invoked
    """

    value = ''  # string accumulating all incoming messages

    def __init__(self, fd: int):
        self.pipe = fd  # writable half of os.pipe


class LogPipe(threading.Thread):
    """
    The thread combined with a context manager to provide a nice way to temporarily redirect something's stream output
    into logging module. The most straightforward application is to suppress subprocess STDOUT and/or STDERR streams and
    wrap them in the logging mechanism as it is now for any other message in your app. Also, store the incoming messages
    in the string
    """

    def __init__(self, logger: logging.Logger, level: int, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger = logger
        self.level = level

        self.fd_read, self.fd_write = os.pipe()  # create 2 ends of the pipe and setup the reading one
        self.pipe_reader = os.fdopen(self.fd_read)

        self.rc = LogPipeRC(self.fd_write)  # "remote control"

    def __enter__(self) -> LogPipeRC:
        """
        Activate the thread and return the consuming end of the pipe so the invoking code can use it to feed its
        messages from now on
        """
        self.start()
        return self.rc

    def run(self):
        """
        Routine of the thread, logging everything
        """
        for line in iter(self.pipe_reader.readline, ''):  # stops the iterator when empty string will occur
            self.rc.value += line  # accumulate the string
            self.logger.log(self.level, line.strip('\n'), extra={ 'from_subprocess': True })  # mark the message origin
        self.pipe_reader.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        The exception will be passed forward, if present, so we don't need to do something with that. The following
        tear-down process will be done anyway
        """
        os.close(self.fd_write)


def get_platformio_boards(platformio_cmd) -> List[str]:
    """
    Obtain the PlatformIO boards list. As we interested only in STM32 ones, cut off all the others.

    IMPORTANT NOTE: The inner implementation can go to the Internet from time to time when it decides that its cache is
    out of date. So it can take a long time to execute.
    """

    # Windows 7, as usual, correctly works only with shell=True...
    result = subprocess.run(f"{platformio_cmd} boards --json-output stm32cube",
                            encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, check=True)

    boards = json.loads(result.stdout)
    return [board['id'] for board in boards]
