#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# from __future__ import annotations

import collections
import logging
import pathlib
import sys
import threading
import time
import weakref

sys.path.insert(0, str(pathlib.Path(sys.path[0]).parent))
import stm32pio.settings
import stm32pio.lib
import stm32pio.util

from PySide2.QtCore import QUrl, Property, QAbstractListModel, QModelIndex, QObject, Qt, Slot, Signal, QThread, qInstallMessageHandler, QtInfoMsg, QtWarningMsg, QtCriticalMsg, QtFatalMsg, QThreadPool, QRunnable, QStringListModel, QSettings
if stm32pio.settings.my_os == 'Linux':
    # Most UNIX systems does not provide QtDialogs implementation...
    from PySide2.QtWidgets import QApplication
else:
    from PySide2.QtGui import QGuiApplication, QIcon
from PySide2.QtQml import qmlRegisterType, QQmlApplicationEngine





class BufferedLoggingHandler(logging.Handler):
    """
    Simple logging.Handler subclass putting all incoming records into the given buffer
    """
    def __init__(self, buffer: collections.deque):
        super().__init__()
        self.buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        self.buffer.append(record)


class LoggingWorker(QObject):
    """
    QObject living in a separate QThread, logging everything it receiving. Intended to be an attached Stm32pio project
    class property. Stringifies log records using DispatchingFormatter and passes them via Signal interface so they can
    be conveniently received by any Qt entity. Also, the level of the message is attaching so the reader can interpret
    them differently.

    Can be controlled by two threading.Event's:
      stopped - on activation, leads to thread termination
      can_flush_log - use this to temporarily save the logs in an internal buffer while waiting for some event to occurs
        (for example GUI widgets to load), and then flush them when time has come
    """

    sendLog = Signal(str, int)

    def __init__(self, logger: logging.Logger):
        super().__init__(parent=None)

        self.buffer = collections.deque()
        self.stopped = threading.Event()
        self.can_flush_log = threading.Event()
        self.logging_handler = BufferedLoggingHandler(self.buffer)

        logger.addHandler(self.logging_handler)
        self.logging_handler.setFormatter(stm32pio.util.DispatchingFormatter(
            f"%(levelname)-8s %(funcName)-{stm32pio.settings.log_fieldwidth_function}s %(message)s",
            special=stm32pio.util.special_formatters))

        self.thread = QThread()
        self.moveToThread(self.thread)

        self.thread.started.connect(self.routine)
        self.thread.start()

    def routine(self) -> None:
        """
        The worker constantly querying the buffer on the new log messages availability.
        """
        while not self.stopped.wait(timeout=0.050):
            if self.can_flush_log.is_set():
                if len(self.buffer):
                    record = self.buffer.popleft()
                    self.sendLog.emit(self.logging_handler.format(record), record.levelno)
        self.thread.quit()



class ProjectListItem(QObject):
    """
    The core functionality class - GUI representation of the Stm32pio project
    """

    nameChanged = Signal()  # properties notifiers
    stateChanged = Signal()
    stageChanged = Signal()

    logAdded = Signal(str, int, arguments=['message', 'level'])  # send the log message to the front-end
    actionDone = Signal(str, bool, arguments=['action', 'success'])  # emit when the action has executed


    def __init__(self, project_args: list = None, project_kwargs: dict = None, parent: QObject = None):
        super().__init__(parent=parent)

        self.logger = logging.getLogger(f"{stm32pio.lib.__name__}.{id(self)}")
        self.logger.setLevel(logging.DEBUG if settings.get('verbose') else logging.INFO)
        self.logging_worker = LoggingWorker(self.logger)
        self.logging_worker.sendLog.connect(self.logAdded)

        # QThreadPool can automatically queue new incoming tasks if a number of them are larger than maxThreadCount
        self.workers_pool = QThreadPool()
        self.workers_pool.setMaxThreadCount(1)
        self.workers_pool.setExpiryTimeout(-1)  # tasks forever wait for the available spot

        # These values are valid till the Stm32pio project does not initialize itself (or failed to)
        self.project = None
        self._name = 'Loading...'
        self._state = { 'LOADING': True }
        self._current_stage = 'Loading...'

        self.qml_ready = threading.Event()  # the front and the back both should know when each other is initialized

        self._finalizer = weakref.finalize(self, self.at_exit)  # register some kind of deconstruction handler

        if project_args is not None:
            if 'logger' not in project_kwargs:
                project_kwargs['logger'] = self.logger

            # Start the Stm32pio part initialization right after. It can take some time so we schedule it in a dedicated
            # thread
            self.init_thread = threading.Thread(target=self.init_project, args=project_args, kwargs=project_kwargs)
            self.init_thread.start()


    def init_project(self, *args, **kwargs) -> None:
        """
        Initialize the underlying Stm32pio project.

        Args:
            *args: positional arguments of the Stm32pio constructor
            **kwargs: keyword arguments of the Stm32pio constructor
        """
        try:
            # print('start to init in python')
            # time.sleep(3)
            # if args[0] == '/Users/chufyrev/Documents/GitHub/stm32pio/Orange':
            # raise Exception("Error during initialization")
            self.project = stm32pio.lib.Stm32pio(*args, **kwargs)  # our slightly tweaked subclass
        except Exception as e:
            # Error during the initialization
            self.logger.exception(e, exc_info=self.logger.isEnabledFor(logging.DEBUG))
            if len(args):
                self._name = args[0]  # use project path string (probably) as a name
            else:
                self._name = 'No name'
            self._state = { 'INIT_ERROR': True }
            self._current_stage = 'Initializing error'
        else:
            self._name = 'Project'  # successful initialization. These values should not be used anymore
            self._state = {}
            self._current_stage = 'Initialized'
        finally:
            self.qml_ready.wait()  # wait for the GUI to initialized
            # print('end to init in python')
            self.nameChanged.emit()  # in any case we should notify the GUI part about the initialization ending
            self.stageChanged.emit()
            self.stateChanged.emit()

    def at_exit(self):
        print('destroy', self.project)
        self.workers_pool.waitForDone(msecs=-1)  # wait for all jobs to complete. Currently, we cannot abort them...
        self.logging_worker.stopped.set()  # stop the logging worker in the end

    @Property(str, notify=nameChanged)
    def name(self):
        if self.project is not None:
            return self.project.path.name
        else:
            return self._name

    @Property('QVariant', notify=stateChanged)
    def state(self):
        if self.project is not None:
            # Convert to normal dict (JavaScript object) and exclude UNDEFINED key
            return { stage.name: value for stage, value in self.project.state.items()
                     if stage != stm32pio.lib.ProjectStage.UNDEFINED }
        else:
            return self._state

    @Property(str, notify=stageChanged)
    def current_stage(self):
        # print('wants current_stage')
        if self.project is not None:
            return str(self.project.state.current_stage)
        else:
            return self._current_stage


    @Slot()
    def qmlLoaded(self):
        """
        Event signaling the complete loading of needed frontend components.
        """
        # print('completed from QML')
        self.qml_ready.set()
        self.logging_worker.can_flush_log.set()


    @Slot(str, 'QVariantList')
    def run(self, action: str, args: list):
        """
        Asynchronously perform Stm32pio actions (generate, build, etc.) (dispatch all business logic).

        Args:
            action: method name of the corresponding Stm32pio action
            args: list of positional arguments for the action
        """

        worker = ProjectActionWorker(getattr(self.project, action), args, self.logger)
        worker.actionDone.connect(self.stateChanged)
        worker.actionDone.connect(self.stageChanged)
        worker.actionDone.connect(self.actionDone)

        self.workers_pool.start(worker)  # will automatically place to the queue



class ProjectActionWorker(QObject, QRunnable):
    """
    QObject + QRunnable combination. First allows to attach Qt signals, second is compatible with QThreadPool
    """

    actionDone = Signal(str, bool, arguments=['action', 'success'])

    def __init__(self, func, args: list = None, logger: logging.Logger = None):
        QObject.__init__(self, parent=None)
        QRunnable.__init__(self)

        self.logger = logger
        self.func = func
        if args is None:
            self.args = []
        else:
            self.args = args
        self.name = func.__name__

    def run(self):
        try:
            result = self.func(*self.args)
        except Exception as e:
            if self.logger is not None:
                self.logger.exception(e, exc_info=self.logger.isEnabledFor(logging.DEBUG))
            result = -1
        if result is None or (type(result) == int and result == 0):
            success = True
        else:
            success = False
        self.actionDone.emit(self.name, success)  # notify the caller




class ProjectsList(QAbstractListModel):
    """
    QAbstractListModel implementation - describe basic operations and delegate all main functionality to the
    ProjectListItem.
    """

    def __init__(self, projects: list = None, parent: QObject = None):
        """
        Args:
            projects: initial list of projects
            parent: QObject to be parented to
        """
        super().__init__(parent=parent)
        self.projects = projects if projects is not None else []
        # self._finalizer = weakref.finalize(self, self.at_exit)

    @Slot(int, result=ProjectListItem)
    def getProject(self, index: int):
        if index in range(len(self.projects)):
            return self.projects[index]

    def rowCount(self, parent=None, *args, **kwargs):
        return len(self.projects)

    def data(self, index: QModelIndex, role=None):
        if role == Qt.DisplayRole or role is None:
            return self.projects[index.row()]

    def addProject(self, project: ProjectListItem):
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self.projects.append(project)
        self.endInsertRows()

    @Slot(QUrl)
    def addProjectByPath(self, path: QUrl):
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        project = ProjectListItem(project_args=[path.toLocalFile()],
                                  project_kwargs=dict(save_on_destruction=False))
        self.projects.append(project)

        settings.beginGroup('app')
        settings.beginWriteArray('projects')
        settings.setArrayIndex(len(self.projects) - 1)
        settings.setValue('path', path.toLocalFile())
        settings.endArray()
        settings.endGroup()

        self.endInsertRows()

    @Slot(int)
    def removeProject(self, index):
        # print('pop index', index)
        try:
            self.projects[index]
        except Exception as e:
            print(e)
        else:
            self.beginRemoveRows(QModelIndex(), index, index)
            self.projects.pop(index)

            settings.beginGroup('app')
            settings.remove('projects')
            settings.beginWriteArray('projects')
            for idx in range(len(self.projects)):
                settings.setArrayIndex(idx)
                settings.setValue('path', str(self.projects[idx].project.path))
            settings.endArray()
            settings.endGroup()

            self.endRemoveRows()
            # print('removed')




def loading():
    # time.sleep(3)
    global boards
    boards = ['None'] + stm32pio.util.get_platformio_boards()


def qt_message_handler(mode, context, message):
    if mode == QtInfoMsg:
        mode = 'Info'
    elif mode == QtWarningMsg:
        mode = 'Warning'
    elif mode == QtCriticalMsg:
        mode = 'critical'
    elif mode == QtFatalMsg:
        mode = 'fatal'
    else:
        mode = 'Debug'
    print("%s: %s" % (mode, message))


DEFAULT_SETTINGS = {
    'editor': '',
    'verbose': False
}

class Settings(QSettings):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key, value in DEFAULT_SETTINGS.items():
            if not self.contains('app/settings/' + key):
                self.setValue('app/settings/' + key, value)

    @Slot(str, result='QVariant')
    def get(self, key):
        return self.value('app/settings/' + key)

    @Slot(str, 'QVariant')
    def set(self, key, value):
        self.setValue('app/settings/' + key, value)

        if key == 'verbose':
            for project in projects_model.projects:
                project.logger.setLevel(logging.DEBUG if value else logging.INFO)


if __name__ == '__main__':
    # Use it as a console logger for whatever you want to
    module_logger = logging.getLogger(__name__)
    module_handler = logging.StreamHandler()
    module_logger.addHandler(module_handler)
    module_logger.setLevel(logging.DEBUG)

    # Apparently Windows version of PySide2 doesn't have QML logging feature turn on so we fill this gap
    if stm32pio.settings.my_os == 'Windows':
        qInstallMessageHandler(qt_message_handler)

    # Most Linux distros should be linked with the QWidgets' QApplication instead of the QGuiApplication to enable
    # QtDialogs
    if stm32pio.settings.my_os == 'Linux':
        app = QApplication(sys.argv)
    else:
        app = QGuiApplication(sys.argv)

    # Used as a settings identifier too
    app.setOrganizationName('ussserrr')
    app.setApplicationName('stm32pio')

    settings = Settings()
    # settings.remove('app/settings')
    # settings.remove('app/projects')
    settings.beginGroup('app')
    projects_paths = []
    for index in range(settings.beginReadArray('projects')):
        settings.setArrayIndex(index)
        projects_paths.append(settings.value('path'))
    settings.endArray()
    settings.endGroup()

    engine = QQmlApplicationEngine()

    qmlRegisterType(ProjectListItem, 'ProjectListItem', 1, 0, 'ProjectListItem')
    qmlRegisterType(Settings, 'Settings', 1, 0, 'Settings')

    projects_model = ProjectsList()
    boards = []
    boards_model = QStringListModel()

    engine.rootContext().setContextProperty('Logging', {
        'CRITICAL': logging.CRITICAL,
        'ERROR': logging.ERROR,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
        'NOTSET': logging.NOTSET
    })
    engine.rootContext().setContextProperty('projectsModel', projects_model)
    engine.rootContext().setContextProperty('boardsModel', boards_model)
    engine.rootContext().setContextProperty('appSettings', settings)

    engine.load(QUrl.fromLocalFile('stm32pio-gui/main.qml'))

    main_window = engine.rootObjects()[0]
    app.setWindowIcon(QIcon('stm32pio-gui/icons/icon.svg'))

    def on_loading():
        boards_model.setStringList(boards)
        projects = [ProjectListItem(project_args=[path], project_kwargs=dict(save_on_destruction=False)) for path in projects_paths]
        # projects = [
        #     ProjectListItem(project_args=['Apple'], project_kwargs=dict(save_on_destruction=False)),
        #     ProjectListItem(project_args=['Orange'], project_kwargs=dict(save_on_destruction=False)),
        #     ProjectListItem(project_args=['Peach'], project_kwargs=dict(save_on_destruction=False))
        # ]
        for p in projects:
            projects_model.addProject(p)
        main_window.backendLoaded.emit()

    loader = ProjectActionWorker(loading)
    loader.actionDone.connect(on_loading)
    QThreadPool.globalInstance().start(loader)

    sys.exit(app.exec_())
