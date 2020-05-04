"""
Some auxiliary entities not falling into other categories
"""

import contextlib
import enum
import json
import logging
import os
import subprocess
import threading
import traceback
import warnings
from typing import Any, List, Mapping, MutableMapping, Tuple, Optional

module_logger = logging.getLogger(__name__)  # this file logger


logging_levels = {  # for exposing the levels to the GUI
    logging.getLevelName(logging.CRITICAL): logging.CRITICAL,
    logging.getLevelName(logging.ERROR): logging.ERROR,
    logging.getLevelName(logging.WARNING): logging.WARNING,
    logging.getLevelName(logging.INFO): logging.INFO,
    logging.getLevelName(logging.DEBUG): logging.DEBUG,
    logging.getLevelName(logging.NOTSET): logging.NOTSET
}


def log_current_exception(logger: logging.Logger, show_traceback_threshold_level: int = logging.DEBUG):
    """
    Print format is:

        ExceptionName: message
        [optional] traceback

    We do not explicitly retrieve an exception info via sys.exc_info() as it immediately stores a reference to the
    current Python frame and/or variables causing some possible weird errors (objects are not GC'ed) and memory leaks.
    See https://cosmicpercolator.com/2016/01/13/exception-leaks-in-python-2-and-3/ for more information
    """
    exc_full_str = traceback.format_exc()
    exc_str = exc_full_str.splitlines()[-1]
    exc_tb = ''.join(exc_full_str.splitlines(keepends=True)[:-1])
    logger.error(f'{exc_str}\n{exc_tb}' if logger.isEnabledFor(show_traceback_threshold_level) else exc_str)


class ProjectLoggerAdapter(logging.LoggerAdapter):
    """
    Use this as a logger for every project:

        self.logger = stm32pio.util.ProjectLoggerAdapter(logging.getLogger('some_singleton_projects_logger'),
                                                         { 'project_id': id(self) })

    It will automatically mix in 'project_id' (and any other property) to every LogRecord (whether you supply 'extra' in
    your log call or not)
    """
    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> Tuple[Any, MutableMapping[str, Any]]:
        """Inject context data (both from the adapter and the log call)"""
        if 'extra' in kwargs:
            kwargs['extra'].update(self.extra)
        else:
            kwargs['extra'] = self.extra
        return msg, kwargs


# Currently available verbosity levels. Verbosity determines how every LogRecord will be formatted (regardless its
# logging level)
@enum.unique
class Verbosity(enum.IntEnum):
    NORMAL = enum.auto()
    VERBOSE = enum.auto()


# Do not add or remove any information from the message and simply pass it "as-is"
as_is_formatter = logging.Formatter('%(message)s')


class DispatchingFormatter(logging.Formatter):
    """
    The wrapper around the ordinary logging.Formatter allowing to have multiple formatters for different purposes.
    General arguments schema:

        {
            verbosity=Verbosity.NORMAL,
            general={
                Verbosity.NORMAL: logging.Formatter(...)
                Verbosity.VERBOSE: logging.Formatter(...)
                ...
            },
            special={
                'case_1': {
                    Verbosity.NORMAL: logging.Formatter(...)
                    ...
                },
                ...
            }
        }
    """

    # Mapping of logging formatters for "special". Currently, only "from_subprocess" is defined. It's good to hide such
    # implementation details as much as possible though they are still tweakable from the outer code
    special_formatters = {
        'from_subprocess': {  # TODO: maybe remade as enum, too? To have an IDE hints and more safety in general
            level: as_is_formatter for level in Verbosity
        }
    }

    def __init__(self, *args, general: Mapping[Verbosity, logging.Formatter] = None,
                 special: Mapping[str, Mapping[Verbosity, logging.Formatter]] = None,
                 verbosity: Verbosity = Verbosity.NORMAL, **kwargs):

        super().__init__(*args, **kwargs)  # will be '%(message)s' if no arguments were given

        self.verbosity = verbosity
        self._warn_was_shown = False

        if general is not None:
            self.general = general
        else:
            warnings.warn("'general' argument for DispatchingFormatter was not provided. It contains formatters for "
                          "all the logging events except special ones and should be a dict with verbosity levels keys "
                          "and logging.Formatter values")
            self.general = {}

        if special is not None:
            self.special = special
        else:
            self.special = DispatchingFormatter.special_formatters  # use defaults


    def find_formatter_for(self, record: logging.LogRecord, verbosity: Verbosity) -> Optional[logging.Formatter]:
        """Determine and return the appropriate formatter"""
        special_formatter = next((self.special[case] for case in self.special.keys() if hasattr(record, case)), None)
        if special_formatter is not None:
            return special_formatter.get(verbosity)
        else:
            return self.general.get(verbosity)


    def format(self, record: logging.LogRecord) -> str:
        """Overridden method"""
        # Allows to specify a verbosity level on the per-record basis, not only globally
        formatter = self.find_formatter_for(record,
                                            record.verbosity if hasattr(record, 'verbosity') else self.verbosity)
        if formatter is not None:
            return formatter.format(record)
        else:
            if not self._warn_was_shown:
                self._warn_was_shown = True
                module_logger.warning("No formatter found, use default one hereinafter")
            return super().format(record)



class LogPipeRC:
    """Small class suitable for passing to the caller when the LogPipe context manager is invoked"""
    value = ''  # string accumulating all incoming messages

    def __init__(self, fd: int):
        self.pipe = fd  # writable half of os.pipe


class LogPipe(threading.Thread, contextlib.AbstractContextManager):
    """
    The thread combined with a context manager to provide a nice way to temporarily redirect something's stream output
    into the logging module. One straightforward application is to suppress subprocess STDOUT and/or STDERR streams and
    wrap them into the logging mechanism as it is now for any other message in your app. Also, store the incoming
    messages in the string for using it after an execution
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

    IMPORTANT NOTE: PlatformIO can go to the Internet from time to time when it decides that its cache is out of date.
    So it can take a long time to execute.
    """

    # Windows 7, as usual, correctly works only with shell=True...
    result = subprocess.run(f"{platformio_cmd} boards --json-output stm32cube",
                            encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, check=True)

    boards = json.loads(result.stdout)
    return [board['id'] for board in boards]
