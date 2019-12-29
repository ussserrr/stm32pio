import logging
import threading
import os
import subprocess

# logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

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
        The exception will be passed forward, if present so we don't need to do something with that. The tear-down
        process will be done anyway
        """
        os.close(self.fd_write)


# For testing
# if __name__ == "__main__":
#     import sys
#
#     logpipe = LogPipe()
#     with subprocess.Popen(['curl', 'www.google.com'], stdout=logpipe, stderr=logpipe) as s:
#         logpipe.close()
#
#     sys.exit()



old_factory = logging.getLogRecordFactory()
def record_factory(*log_record_args, **kwargs):
    args_idx = 5
    if 'from_subprocess' in log_record_args[args_idx]:
        new_log_record_args = log_record_args[:args_idx] + (tuple(arg for arg in log_record_args[args_idx] if arg != 'from_subprocess'),) + log_record_args[args_idx+1:]
        record = old_factory(*new_log_record_args, **kwargs)
        record.from_subprocess = True
    else:
        record = old_factory(*log_record_args, **kwargs)
    return record
logging.setLogRecordFactory(record_factory)


class DispatchingFormatter(logging.Formatter):
    def __init__(self, *args, custom_formatters=None, **kwargs):
        self._formatters = custom_formatters
        super().__init__(*args, **kwargs)

    def format(self, record):
        if hasattr(record, 'from_subprocess') and record.from_subprocess:
            try:
                return self._formatters['subprocess'].format(record)
            except AttributeError:
                pass
        return super().format(record)


root_l = logging.getLogger('root')
root_f = DispatchingFormatter("%(levelname)-8s %(funcName)-26s %(message)s",
    custom_formatters={
        'subprocess': logging.Formatter('ONLY MESSAGE %(message)s')
    }
)
# root_f = logging.Formatter("USER HASN'T USED DispatchingFormatter %(message)s")
root_h = logging.StreamHandler()
root_h.setFormatter(root_f)
root_l.addHandler(root_h)
root_l.setLevel(logging.INFO)
# root_h.setLevel(logging.DEBUG)


child_l = logging.getLogger('root.child')
# child_f = DispatchingFormatter("%(levelname)-8s %(funcName)-26s %(message)s",
#                                custom_formatters={
#         'subprocess': logging.Formatter('ONLY MESSAGE %(message)s')
#     }
# )
# root_f = logging.Formatter("USER HASN'T USED DispatchingFormatter %(message)s")
# child_h = logging.StreamHandler()
# child_h.setFormatter(child_f)
# child_l.addHandler(child_h)
# child_l.setLevel(logging.DEBUG)
# child_h.setLevel(logging.DEBUG)

instance_l = logging.getLogger('root.child.instance')


root_l.info('Hello from root')
child_l.info('Hello from child')
instance_l.info('Hello from instance')
instance_l.info('Hello from instance but from subprocess', 'from_subprocess')


# logpipe = LogPipe(child_l)
# subprocess.run(['curl', 'www.google.com'], stdout=logpipe, stderr=logpipe)
# logpipe.close()

try:
    with LogPipe(instance_l, logging.DEBUG) as logpipe:
        subprocess.run(['curl', 'www.google.com'], stdout=logpipe, stderr=logpipe)
        # subprocess.run(['blabla'], stdout=logpipe, stderr=logpipe)
    print('not called cause the exception')
except FileNotFoundError:
    print('exception here')

# with subprocess.Popen(['curl', 'www.google.com'], stdout=logpipe, stderr=logpipe) as s:
#     logpipe.close()

# popen = subprocess.Popen(
#         ['curl', 'www.google.com'],
#         stdout=subprocess.PIPE,
#         stderr=subprocess.STDOUT,
#         universal_newlines=True
# )
# for stdout_line in iter(popen.stdout.readline, ""):
#     instance_l.debug(stdout_line.strip('\n'), 'from_subprocess')
# popen.stdout.close()
# return_code = popen.wait()
