"""
Logging is an important part of the application since almost all of its output is flowing through the Python ``logging``
library in some way or another providing a feedback to users. It is an intended behavior allowing us not just quickly
customize the output format but also redirect it to different "sinks" in any possible combinations. It has been
developed and taken such a form mostly during the GUI milestone to provide some sleek asynchronous way of piping all
text-based application output to GUI components while preserving a backwards compatibility with the CLI API.

This module consists of several handy utilities for various uses throughout the app.
"""

import enum
import logging
import os
from contextlib import AbstractContextManager
from copy import copy
from threading import Thread
from traceback import format_exc as format_exception
from typing import Any, MutableMapping, Tuple, Mapping, Optional, List, Union

import stm32pio.core.config
import stm32pio.core.settings


_module_logger = logging.getLogger(__name__)  # this module logger

logging_levels = {  # GUI is using this map to adjust its representation
    logging.getLevelName(logging.CRITICAL):  logging.CRITICAL,
    logging.getLevelName(logging.ERROR):     logging.ERROR,
    logging.getLevelName(logging.WARNING):   logging.WARNING,
    logging.getLevelName(logging.INFO):      logging.INFO,
    logging.getLevelName(logging.DEBUG):     logging.DEBUG,
    logging.getLevelName(logging.NOTSET):    logging.NOTSET
}

# Do not add or remove any information from the message and simply pass it "as-is"
as_is_formatter = logging.Formatter('%(message)s')


@enum.unique
class Verbosity(enum.IntEnum):
    """
    Global logging verbosity levels available for the application. Each one determines how every LogRecord will be
    formatted (independent from its level)
    """
    NORMAL = enum.auto()  # note: starts from 1
    VERBOSE = enum.auto()


@enum.unique
class SpecialLogEvent(enum.Enum):
    """
    Identifiers for the special logging cases when a log request should be treated differently compared to a normal
    situations
    """
    FROM_SUBPROCESS = 'from_subprocess'


class ProjectLogger(logging.LoggerAdapter):
    """
    Wrapper around the actual Logger to supply some contextual information to every LogRecord. Usage example:

        self.logger = ProjectLogger(logging.getLogger('some_singleton_logger_for_all_projects'), project_id=id(self))
    """

    def __init__(self, underlying_logger: logging.Logger, project_id: int):
        super().__init__(logger=underlying_logger, extra=dict(project_id=project_id))

    # TODO: kwargs can utilize Python 3.8+ TypedDict, doesn't it?..
    def process(self, msg: Any, kwargs: MutableMapping[str, Any]) -> Tuple[Any, MutableMapping[str, Any]]:
        """Inject a context data (both from the adapter and the log call)"""

        # 1. Attach the common, per-project-scoped context
        if 'extra' in kwargs:
            kwargs['extra'].update(self.extra)
        else:
            kwargs['extra'] = copy(self.extra)  # be careful! Only works for plain objects

        # 2. Inject a logging-call-scoped context
        flags = [case for case in SpecialLogEvent if case.value in kwargs and bool(kwargs[case.value])]
        if len(flags) > 1:
            _module_logger.warning(f"More than 1 special logging event flag is set for a single record \"{msg}\". "
                                   "A first one will be chosen")
        if len(flags) > 0:
            # We should use *something* as a key anyway, so why not a SpecialLogEvent name?
            kwargs['extra'][SpecialLogEvent.__name__] = flags[0]
        for case in flags:  # clear our "custom" keys since the kwargs argument cannot contain any unwanted values
            del kwargs[case.value]

        return msg, kwargs


Logger = Union[logging.Logger, logging.LoggerAdapter]  # used as a type hint for all loggers throughout the app


class DispatchingFormatter(logging.Formatter):
    """
    Wrapper around the ordinary logging.Formatter allowing to have multiple formatters for different purposes. General
    arguments schema:

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

    # General-purpose logging formatters
    GENERAL_FORMATTERS_DEFAULT = {
        Verbosity.NORMAL: logging.Formatter("%(levelname)-8s %(message)s"),
        Verbosity.VERBOSE: logging.Formatter(
            f"%(levelname)-8s %(module)s %(funcName)-{stm32pio.core.settings.log_fieldwidth_function}s %(message)s")
    }

    # Logging formatters for some "special" cases. Currently, only "from_subprocess" is defined
    SPECIAL_FORMATTERS_DEFAULT = {
        SpecialLogEvent.FROM_SUBPROCESS: {
            level: as_is_formatter for level in Verbosity
        }
    }

    def __init__(self, verbosity: Verbosity = Verbosity.NORMAL,
                 general: Mapping[Verbosity, logging.Formatter] = None,
                 special: Mapping[SpecialLogEvent, Mapping[Verbosity, logging.Formatter]] = None):
        super().__init__()  # will be '%(message)s'
        self.verbosity = verbosity
        self.general = DispatchingFormatter.GENERAL_FORMATTERS_DEFAULT if general is None else general
        self.special = DispatchingFormatter.SPECIAL_FORMATTERS_DEFAULT if special is None else special

    def find_formatter_for(self, record: logging.LogRecord) ->\
            Tuple[Optional[SpecialLogEvent], Optional[logging.Formatter]]:
        """Find and return an appropriate formatter"""
        special_case = getattr(record, SpecialLogEvent.__name__) if hasattr(record, SpecialLogEvent.__name__) else None
        if special_case is not None:
            return special_case, self.special.get(special_case, {}).get(self.verbosity)
        return None, self.general.get(self.verbosity)

    def format(self, record: logging.LogRecord) -> str:
        """Dispatch a request to a suitable formatter"""
        case, formatter = self.find_formatter_for(record)
        if formatter is not None:
            return formatter.format(record)
        else:
            _module_logger.warning(f"No formatter found for logging event {case}, verbosity {self.verbosity}. "
                                   "Falling back to default one")
            return super().format(record)


class LogPipeRC:
    """Small class suitable for passing to a caller on the LogPipe context manager enter"""

    accumulator: List[str] = []  # accumulating all incoming messages

    def __init__(self, fd: int):
        """
        :param fd: writable end of os.pipe
        """
        self.pipe = fd

    @property
    def value(self):
        return ''.join(self.accumulator)


class LogPipe(Thread, AbstractContextManager):
    """
    Thread combined with the context manager providing a nice way to temporarily redirect some stream output into the
    ``logging`` module. One straightforward application is to suppress a given subprocess' STDOUT/STDERR and wrap them
    into a conventional logging mechanism of your app. It can also accumulate such output to an internal variable for
    further usage
    """

    def __init__(self, logger: Logger = None, level: int = logging.INFO, accumulate: bool = False):
        """
        :param logger: logger to flow a streaming lines to
        :param level: logging level to log a messages with
        :param accumulate: whether to store a copy of incoming information
        """

        super().__init__()  # initialize both ancestors (refer to MRO)

        self.logger = logger
        self.level = level
        self.accumulate = accumulate

        self.fd_read, self.fd_write = os.pipe()  # create 2 ends of the pipe and setup the reading one
        self.pipe_reader = os.fdopen(self.fd_read)

        self.rc = LogPipeRC(self.fd_write)  # RC stands for "remote control"

    def __enter__(self) -> LogPipeRC:
        """Start the thread and return the consuming end of pipe. The caller should feed its data to that input now"""
        self.start()
        return self.rc

    def run(self):
        """Routine of the thread: absorb everything"""
        for line in iter(self.pipe_reader.readline, ''):  # stop iteration when the empty string will occur
            if self.accumulate:
                self.rc.accumulator.append(line)  # accumulate the string
            if self.logger:
                self.logger.log(self.level, line.strip('\n'), from_subprocess=True)  # mark the message origin
        self.pipe_reader.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Any exception will be passed forward. The following tear-down process will be done anyway"""
        os.close(self.fd_write)


def log_current_exception(logger: Logger, show_traceback: bool = None,
                          config: stm32pio.core.config.ProjectConfig = None) -> None:
    """
    When called from inside a ``try...except`` block, will smartly report error details depending on a context. In
    verbose mode (as determined based on the given logger) additionally prints the traceback, otherwise only a message
    will be shown. This can be overridden by ``show_traceback`` flag. If project config is given, traceback always will
    be put in it instead of printing.

    :param logger: instance to output the message
    :param show_traceback: reset default behavior (ignored if ``config`` given)
    :param config: ``ProjectConfig`` instance
    """

    if show_traceback is None:
        show_traceback = logger.isEnabledFor(stm32pio.core.settings.show_traceback_threshold_level)

    # We do not explicitly retrieve an exception info via sys.exc_info() as it immediately stores a reference to the
    # current Python frame/variables possibly causing some weird errors and memory leaks (objects are not garbage
    # collected). See https://cosmicpercolator.com/2016/01/13/exception-leaks-in-python-2-and-3/ for more information.
    lines = format_exception().splitlines()
    message = lines[-1]
    if message.startswith('Exception: ') and not show_traceback:
        message = message[len('Exception: '):]
    traceback = '\n'.join(lines[:-1])

    if config is not None:
        logger.error(message)
        config_saved = config.save({'project': {'last_error': f"{message}\n{traceback}"}}) == 0
        if config_saved:
            logger.info(f"Traceback has been saved to {config.path.name}. It will be cleared on next successful run")
        else:
            logger.warning(f"Traceback has not been saved to {config.path.name}")
    else:
        logger.error(f"{message}\n{traceback}" if show_traceback else message)
