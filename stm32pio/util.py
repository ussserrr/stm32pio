"""
Some auxiliary entities not falling into other categories
"""

import logging
import os
import threading
from typing import List

from platformio.managers.platform import PlatformManager


module_logger = logging.getLogger(__name__)



# Do not add or remove any information from the message and simply pass it "as-is"
special_formatters = { 'subprocess': logging.Formatter('%(message)s') }

default_log_record_factory = logging.getLogRecordFactory()

def log_record_factory(*log_record_args, **log_record_kwargs):
    """
    Replace the default factory of logging.LogRecord's instances so we can handle our special logging flags
    """
    args_idx = 5  # index of 'args' argument in the positional arguments list

    if 'from_subprocess' in log_record_args[args_idx]:
        # Remove our custom flag from the tuple (it is inside a tuple that is inside a list)
        new_log_record_args = log_record_args[:args_idx] + \
                              (tuple(arg for arg in log_record_args[args_idx] if arg != 'from_subprocess'),) + \
                              log_record_args[args_idx + 1:]
        # Construct an ordinary LogRecord and append our flag as an attribute
        record = default_log_record_factory(*new_log_record_args, **log_record_kwargs)
        record.from_subprocess = True
    else:
        record = default_log_record_factory(*log_record_args, **log_record_kwargs)

    return record

logging.setLogRecordFactory(log_record_factory)


class DispatchingFormatter(logging.Formatter):
    """
    The wrapper around the ordinary logging.Formatter allowing to have multiple formatters for different purposes.
    'extra' argument of the log() function has a similar intention but different mechanics
    """

    def __init__(self, *args, special: dict = None, **kwargs):
        super().__init__(*args, **kwargs)

        # Store all provided formatters in an internal variable
        if isinstance(special, dict) and all(isinstance(value, logging.Formatter) for value in special.values()):
            self._formatters = special
        else:
            module_logger.warning(f"'special' argument is for providing custom formatters for special logging events "
                                  "and should be a dictionary with logging.Formatter values")
            self._formatters = {}

        self.warn_was_shown = False

    def format(self, record: logging.LogRecord) -> str:
        """
        Use suitable formatter based on the LogRecord attributes
        """
        if hasattr(record, 'from_subprocess') and record.from_subprocess:
            if 'subprocess' in self._formatters:
                return self._formatters['subprocess'].format(record)
            elif not self.warn_was_shown:
                module_logger.warning("No formatter found for the 'subprocess' case, use default hereinafter")
        return super().format(record)


class LogPipe(threading.Thread):
    """
    The thread combined with a context manager to provide a nice way to temporarily redirect something's stream output
    into logging module. The most straightforward application is to suppress subprocess STDOUT and/or STDERR streams and
    wrap them in the logging mechanism as it is for now for any other message in your app.
    """

    def __init__(self, logger: logging.Logger, level: int, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger = logger
        self.level = level

        self.fd_read, self.fd_write = os.pipe()  # create 2 ends of the pipe and setup the reading one
        self.pipe_reader = os.fdopen(self.fd_read)

    def __enter__(self) -> int:
        """
        Activate the thread and return the consuming end of the pipe so the invoking code can use it to feed its
        messages from now on
        """
        self.start()
        return self.fd_write

    def run(self):
        """
        Routine of the thread, logging everything
        """
        for line in iter(self.pipe_reader.readline, ''):
            self.logger.log(self.level, line.strip('\n'), 'from_subprocess')  # mark the message origin

        self.pipe_reader.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        The exception will be passed forward, if present, so we don't need to do something with that. The following
        tear-down process will be done anyway
        """
        os.close(self.fd_write)



def get_platformio_boards() -> List[str]:
    """
    Use PlatformIO Python sources to obtain the boards list. As we interested only in STM32 ones, cut off all the
    others.

    IMPORTANT NOTE: The inner implementation can go to the Internet from time to time when it decides that its cache is
    out of date. So it can take a long time to execute.
    """

    pm = PlatformManager()
    return [board['id'] for board in pm.get_all_boards() if 'stm32cube' in board['frameworks']]
