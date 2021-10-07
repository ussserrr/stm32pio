import logging
import time
from typing import Callable, List, Any, Optional

from PySide2.QtCore import QObject, QRunnable, Signal

import stm32pio.core.log


ProjectID = type(id(object))  # Int


class Worker(QObject, QRunnable):
    """
    Generic worker for asynchronous processes: QObject + QRunnable combination. First allows to attach Qt signals,
    second is compatible with the QThreadPool
    """

    started = Signal(str, arguments=['action'])
    finished = Signal(str, bool, arguments=['action', 'success'])


    def __init__(self, func: Callable[[List[Any]], Optional[int]], args: List[Any] = None,
                 logger: logging.Logger = None, parent: QObject = None):
        """
        Args:
            func: function to run. It should return 0 or None for the call to be considered successful
            args: the list of positional arguments. They will be unpacked and passed to the function
            logger: optional logger to report about the occurred exception
            parent: Qt object
        """
        QObject.__init__(self, parent=parent)
        QRunnable.__init__(self)

        self.func = func
        self.args = args if args is not None else []
        self.logger = logger
        self.name = func.__name__


    def run(self):
        self.started.emit(self.name)  # notify the caller

        try:
            result = self.func(*self.args)
        except Exception:
            if self.logger is not None:
                # We cannot pass the project config here to preserve the error because we don't have the reference
                stm32pio.core.log.log_current_exception(self.logger)
            result = -1

        if result is None or (type(result) == int and result == 0):
            success = True
        else:
            success = False

        self.finished.emit(self.name, success)  # notify the caller

        if not success:
            # Pause the thread and, therefore, the parent QThreadPool queue so the caller can decide whether we should
            # proceed or stop. This should not cause any problems as we've already perform all necessary tasks and this
            # just delaying the QRunnable removal from the pool
            # TODO: looks like a hack...
            time.sleep(1.0)
