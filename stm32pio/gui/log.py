import collections
import logging
import platform
import threading
from typing import MutableMapping

from PySide2.QtCore import QObject, Signal, QThread, QtInfoMsg, QtWarningMsg, QtCriticalMsg, QtFatalMsg, \
    qInstallMessageHandler

from stm32pio.core.log import Verbosity, DispatchingFormatter

from stm32pio.gui.util import ProjectID


def set_verbosity(value: bool):
    """Use this to toggle the verbosity of all loggers at once"""
    module_logger.setLevel(logging.DEBUG if value else logging.INFO)
    qml_logger.setLevel(logging.DEBUG if value else logging.INFO)
    projects_logger.setLevel(logging.DEBUG if value else logging.INFO)
    _projects_logger_formatter.verbosity = Verbosity.VERBOSE if value else Verbosity.NORMAL


def qt_message_handler(mode, context, message):
    """
    Register this logging handler for the Qt stuff if your platform doesn't provide a built-in one or if you want to
    customize it
    """
    if mode == QtInfoMsg:
        mode = logging.INFO
    elif mode == QtWarningMsg:
        mode = logging.WARNING
    elif mode == QtCriticalMsg:
        mode = logging.ERROR
    elif mode == QtFatalMsg:
        mode = logging.CRITICAL
    else:
        mode = logging.DEBUG
    qml_logger.log(mode, message)


def setup_logging(initial_verbosity):
    module_log_handler = logging.StreamHandler()
    module_log_handler.setFormatter(logging.Formatter("%(levelname)s %(module)s %(funcName)s %(message)s"))
    module_logger.addHandler(module_log_handler)
    module_logger.setLevel(logging.INFO)  # set this again later after getting QSettings

    # Apparently Windows version of PySide2 doesn't have QML logging feature turn on so we fill this gap
    if platform.system() == 'Windows':
        qml_log_handler = logging.StreamHandler()
        qml_log_handler.setFormatter(logging.Formatter("[QML] %(levelname)s %(message)s"))
        qml_logger.addHandler(qml_log_handler)
        qInstallMessageHandler(qt_message_handler)

    # Use "singleton" real logger for all projects just wrapping it into the LoggingAdapter for every project
    projects_logger.setLevel(logging.DEBUG if initial_verbosity else logging.INFO)
    projects_logger_handler.setFormatter(_projects_logger_formatter)
    projects_logger.addHandler(projects_logger_handler)

    set_verbosity(initial_verbosity)  # set initial verbosity settings based on the saved state


class BuffersDispatchingHandler(logging.Handler):
    """
    Every user's project using its own buffer (collections.deque) to store logs. This simple logging.Handler subclass
    finds and puts an incoming record into the corresponding buffer
    """

    buffers: MutableMapping[ProjectID, collections.deque] = {}  # the dictionary of projects' ids and theirs buffers

    def emit(self, record: logging.LogRecord) -> None:
        if hasattr(record, 'project_id'):
            # As we exist in the asynchronous environment there is always a risk of some "desynchronization" when the
            # project (and its buffer) has already been gone but some late message has arrived. Hence, we need to check
            buffer = self.buffers.get(record.project_id)
            if buffer is not None:
                buffer.append(record)
            else:
                module_logger.warning(f"Logging buffer for the project id {record.project_id} not found. The message "
                                      f"was:\n{record.msg}")
        else:
            module_logger.warning("LogRecord doesn't have a project_id attribute. Perhaps this is a result of the "
                                  f"logging setup misconfiguration. Anyway, the message was:\n{record.msg}")


class LoggingWorker(QObject):
    """
    QObject living in a separate QThread, logging everything it receiving. Intended to be an attached
    ProjectListItem property. Stringifies log records using global BuffersDispatchingHandler instance (its
    stm32pio.core.util.DispatchingFormatter, to be precise) and passes them via Qt Signal interface so they can be
    conveniently received by any Qt entity. Also, the level of the message is attaching so the reader can
    interpret them differently.

    Can be controlled by two threading.Event's:
        stopped - on activation, leads to thread termination
        can_flush_log - use this to temporarily save the logs in an internal buffer while waiting for some event to
            occurs (for example GUI widgets to load), and then flush them when the time has come
    """

    sendLog = Signal(str, int)

    def __init__(self, project_id: ProjectID, parent: QObject = None):
        super().__init__(parent=parent)

        self.project_id = project_id
        self.buffer = collections.deque()
        projects_logger_handler.buffers[project_id] = self.buffer  # register our buffer

        self.stopped = threading.Event()
        self.can_flush_log = threading.Event()

        self.thread = QThread(parent=self)
        self.moveToThread(self.thread)
        self.thread.started.connect(self.routine)
        self.thread.start()

    def routine(self) -> None:
        """
        The worker constantly querying the buffer on the new log messages availability
        """
        while not self.stopped.wait(timeout=0.050):
            if self.can_flush_log.is_set() and len(self.buffer):
                record = self.buffer.popleft()
                self.sendLog.emit(projects_logger_handler.format(record), record.levelno)
        # We do not flush all remaining logs before termination, it can be useful in some other applications though
        projects_logger_handler.buffers.pop(self.project_id)  # unregister our buffer
        module_logger.debug(f"exit LoggingWorker of project id {self.project_id}")
        self.thread.quit()


module_logger = logging.getLogger('stm32pio.gui.app')  # use it as a console logger for whatever you want to,
                                                       # typically not related to the concrete project
qml_logger = logging.getLogger('stm32pio.gui.qml')
projects_logger = logging.getLogger('stm32pio.gui.projects')

projects_logger_handler = BuffersDispatchingHandler()  # a storage of the buffers for the logging messages of all
                                                       # current projects (see its docs for more info)

_projects_logger_formatter = DispatchingFormatter()
