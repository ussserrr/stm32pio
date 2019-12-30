import logging
import os
import threading


module_logger = logging.getLogger(__name__)

old_log_record_factory = logging.getLogRecordFactory()
def log_record_factory(*log_record_args, **log_record_kwargs):
    args_idx = 5
    if 'from_subprocess' in log_record_args[args_idx]:
        new_log_record_args = log_record_args[:args_idx] +\
                              (tuple(arg for arg in log_record_args[args_idx] if arg != 'from_subprocess'),) +\
                              log_record_args[args_idx + 1:]
        record = old_log_record_factory(*new_log_record_args, **log_record_kwargs)
        record.from_subprocess = True
    else:
        record = old_log_record_factory(*log_record_args, **log_record_kwargs)
    return record
logging.setLogRecordFactory(log_record_factory)

class DispatchingFormatter(logging.Formatter):
    def __init__(self, *args, special: dict = None, **kwargs):
        if isinstance(special, dict) and all(isinstance(formatter, logging.Formatter) for formatter in special.values()):
            self._formatters = special
        else:
            module_logger.warning(f"'special' argument is for providing custom formatters for special logging events "
                                  "and should be a dictionary with logging.Formatter values")
            self._formatters = {}
        super().__init__(*args, **kwargs)

    def format(self, record):
        if hasattr(record, 'from_subprocess') and record.from_subprocess:
            try:
                return self._formatters['subprocess'].format(record)
            except AttributeError:
                pass
        return super().format(record)


class LogPipe(threading.Thread):

    def __init__(self, logger: logging.Logger, level: int, *args, **kwargs):
        """Setup the object with a logger and a loglevel
        and start the thread
        """
        super().__init__(*args, **kwargs)

        self.logger = logger
        self.level = level

        self.fd_read, self.fd_write = os.pipe()
        self.pipe_reader = os.fdopen(self.fd_read)

    def __enter__(self):
        self.start()
        return self.fd_write

    def run(self):
        """Run the thread, logging everything.
        """
        for line in iter(self.pipe_reader.readline, ''):
            self.logger.log(self.level, line.strip('\n'), 'from_subprocess')

        self.pipe_reader.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        The exception will be passed forward, if present, so we don't need to do something with that. The tear-down
        process will be done anyway
        """
        os.close(self.fd_write)
