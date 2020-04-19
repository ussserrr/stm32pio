#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import collections
import logging
import pathlib
import platform
import sys
import threading
import time
import traceback
import weakref
from typing import List, Callable, Optional, Dict, Any

try:
    from PySide2.QtCore import QUrl, Property, QAbstractListModel, QModelIndex, QObject, Qt, Slot, Signal, QThread,\
        qInstallMessageHandler, QtInfoMsg, QtWarningMsg, QtCriticalMsg, QtFatalMsg, QThreadPool, QRunnable,\
        QStringListModel, QSettings
    if platform.system() == 'Linux':
        # Most UNIX systems does not provide QtDialogs implementation so the program should be 'linked' against
        # the QApplication...
        from PySide2.QtWidgets import QApplication
    else:
        from PySide2.QtGui import QGuiApplication
    from PySide2.QtGui import QIcon
    from PySide2.QtQml import qmlRegisterType, QQmlApplicationEngine, QJSValue
except ImportError as e:
    print(e)
    print("\nGUI version requires PySide2 to be installed. You can re-install stm32pio as 'pip install stm32pio[GUI]' "
          "or manually install its dependencies by yourself")
    sys.exit(-1)

ROOT_PATH = pathlib.Path(sys.path[0]).parent
MODULE_PATH = pathlib.Path(__file__).parent
try:
    import stm32pio.settings
    import stm32pio.lib
    import stm32pio.util
except ModuleNotFoundError:
    sys.path.insert(0, str(ROOT_PATH))
    import stm32pio.settings
    import stm32pio.lib
    import stm32pio.util



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
    QObject living in a separate QThread, logging everything it receiving. Intended to be an attached ProjectListItem
    property. Stringifies log records using DispatchingFormatter and passes them via Signal interface so they can be
    conveniently received by any Qt entity. Also, the level of the message is attaching so the reader can interpret them
    differently.

    Can be controlled by two threading.Event's:
        stopped - on activation, leads to thread termination
        can_flush_log - use this to temporarily save the logs in an internal buffer while waiting for some event to
            occurs (for example GUI widgets to load), and then flush them when the time has come
    """

    sendLog = Signal(str, int)

    def __init__(self, logger: logging.Logger, parent: QObject = None):
        super().__init__(parent=parent)

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
            if self.can_flush_log.is_set() and len(self.buffer):
                record = self.buffer.popleft()
                self.sendLog.emit(self.logging_handler.format(record), record.levelno)
        module_logger.debug('exit logging worker')
        self.thread.quit()



class ProjectListItem(QObject):
    """
    The core functionality class - wrapper around Stm32pio class suitable for the project GUI representation
    """

    nameChanged = Signal()  # properties notifiers
    stateChanged = Signal()
    stageChanged = Signal()

    logAdded = Signal(str, int, arguments=['message', 'level'])  # send the log message to the front-end

    actionStarted = Signal(str, arguments=['action'])
    actionFinished = Signal(str, bool, arguments=['action', 'success'])


    def __init__(self, project_args: list = None, project_kwargs: dict = None, from_startup: bool = False,
                 parent: QObject = None):
        """
        Args:
            project_args: list of positional arguments that will be passed to the Stm32pio constructor
            project_kwargs: dictionary of keyword arguments that will be passed to the Stm32pio constructor
            from_startup: mark that this project comes from the beginning of the app life (e.g. from the NV-storage) so
                it can be treated differently on the GUI side
            parent: Qt parent
        """

        super().__init__(parent=parent)

        if project_args is None:
            project_args = []
        if project_kwargs is None:
            project_kwargs = {}

        self._from_startup = from_startup

        self.logger = logging.getLogger(f"{stm32pio.lib.__name__}.{id(self)}")
        self.logger.setLevel(logging.DEBUG if settings.get('verbose') else logging.INFO)
        self.logging_worker = LoggingWorker(self.logger)
        self.logging_worker.sendLog.connect(self.logAdded)

        # QThreadPool can automatically queue new incoming tasks if a number of them are larger than maxThreadCount
        self.workers_pool = QThreadPool(parent=self)
        self.workers_pool.setMaxThreadCount(1)
        self.workers_pool.setExpiryTimeout(-1)  # tasks forever wait for the available spot
        self._current_action = ''

        # These values are valid till the Stm32pio project does not initialize itself (or failed to)
        self.project = None
        self._name = 'Loading...'
        self._state = { 'LOADING': True }  # pseudo-stage (isn't present in ProjectStage enum)
        self._current_stage = 'Loading...'

        self.qml_ready = threading.Event()  # the front and the back both should know when each other is initialized

        # Register some kind of the deconstruction handler (later, after the project initialization)
        self._finalizer = None

        if 'instance_options' not in project_kwargs:
            project_kwargs['instance_options'] = { 'logger': self.logger }
        elif 'logger' not in project_kwargs['instance_options']:
            project_kwargs['instance_options']['logger'] = self.logger

        # Start the Stm32pio part initialization right after. It can take some time so we schedule it in a dedicated
        # thread
        init_thread = threading.Thread(target=self.init_project, args=project_args, kwargs=project_kwargs)
        init_thread.start()


    def init_project(self, *args, **kwargs) -> None:
        """
        Initialize the underlying Stm32pio project.

        Args:
            *args: positional arguments of the Stm32pio constructor
            **kwargs: keyword arguments of the Stm32pio constructor
        """
        try:
            self.project = stm32pio.lib.Stm32pio(*args, **kwargs)
        except Exception:
            # Error during the initialization. Print format is: "ExceptionName: message"
            self.logger.exception(traceback.format_exception_only(*(sys.exc_info()[:2]))[-1],
                                  exc_info=self.logger.isEnabledFor(logging.DEBUG))
            if len(args):
                self._name = args[0]  # use a project path string (as it should be a first argument) as a name
            else:
                self._name = 'Undefined'
            self._state = { 'INIT_ERROR': True }  # pseudo-stage (isn't present in ProjectStage enum)
            self._current_stage = 'Initializing error'
        else:
            # Successful initialization. These values should not be used anymore but we "reset" them anyway
            self._name = 'Project'
            self._state = {}
            self._current_stage = 'Initialized'
        finally:
            # Register some kind of the deconstruction handler
            self._finalizer = weakref.finalize(self, self.at_exit, self.workers_pool, self.logging_worker,
                                               self.name if self.project is None else str(self.project))
            self.qml_ready.wait()  # wait for the GUI to initialize (which one is earlier, actually, back or front)
            self.nameChanged.emit()  # in any case we should notify the GUI part about the initialization ending
            self.stageChanged.emit()
            self.stateChanged.emit()


    @staticmethod
    def at_exit(workers_pool: QThreadPool, logging_worker: LoggingWorker, name: str):
        """
        Instance deconstruction handler meant to be used with weakref.finalize() conforming with the requirement to have
        no reference to the target object (so it is decorated as 'staticmethod')
        """
        module_logger.info(f"destroy {name}")
        # Wait forever for all the jobs to complete. Currently, we cannot abort them gracefully
        workers_pool.waitForDone(msecs=-1)
        logging_worker.stopped.set()  # post the event in the logging worker to inform it...
        logging_worker.thread.wait()  # ...and wait for it to exit, too


    @Property(bool)
    def fromStartup(self) -> bool:
        """Is this project is here from the beginning of the app life?"""
        return self._from_startup

    @Property(str, notify=nameChanged)
    def name(self) -> str:
        """Human-readable name of the project. Will evaluate to the absolute path if it cannot be instantiated"""
        if self.project is not None:
            return self.project.path.name
        else:
            return self._name

    @Property('QVariant', notify=stateChanged)
    def state(self) -> dict:
        """
        Get the current project state in the appropriate Qt form. Update the cached 'current stage' value as a side
        effect
        """
        if self.project is not None:
            state = self.project.state

            # Side-effect: caching the current stage at the same time to avoid the flooding of calls to the 'state'
            # getter (many IO operations). Requests to 'state' and 'stage' are usually goes together so there is no need
            # to necessarily keeps them separated
            self._current_stage = str(state.current_stage)

            state.pop(stm32pio.lib.ProjectStage.UNDEFINED)  # exclude UNDEFINED key
            # Convert to {string: boolean} dict (will be translated into the JavaScript object)
            return { stage.name: value for stage, value in state.items() }
        else:
            return self._state

    @Property(str, notify=stageChanged)
    def currentStage(self) -> str:
        """
        Get the current stage the project resides in.
        Note: this returns a cached value. Cache updates every time the state property got requested
        """
        return self._current_stage

    @Property(str)
    def currentAction(self) -> str:
        """
        Stm32pio action (i.e. function name) that is currently executing or an empty string if there is none. It is set
        on actionStarted signal and reset on actionFinished
        """
        return self._current_action

    @Slot(str)
    def actionStartedSlot(self, action: str):
        """Pass the corresponding signal from the worker, perform related tasks"""
        # Currently, this property should be set BEFORE emitting the 'actionStarted' signal (because QML will query it
        # when the signal will be handled in StateMachine) (probably, should be resolved later as it is bad to be bound
        # to such a specific logic)
        self._current_action = action
        self.actionStarted.emit(action)

    @Slot(str, bool)
    def actionFinishedSlot(self, action: str, success: bool):
        """Pass the corresponding signal from the worker, perform related tasks"""
        if not success:
            self.workers_pool.clear()  # clear the queue - stop further execution
        self.actionFinished.emit(action, success)
        # Currently, this property should be reset AFTER emitting the 'actionFinished' signal (because QML will query it
        # when the signal will be handled in StateMachine) (probably, should be resolved later as it is bad to be bound
        # to such a specific logic)
        self._current_action = ''

    @Slot()
    def qmlLoaded(self):
        """Event signaling the complete loading of the needed frontend components"""
        self.qml_ready.set()
        self.logging_worker.can_flush_log.set()


    @Slot(str, 'QVariantList')
    def run(self, action: str, args: list):
        """
        Asynchronously perform Stm32pio actions (generate, build, etc.) (dispatch all business logic).

        Args:
            action: method name of the corresponding Stm32pio action
            args: list of positional arguments for this action
        """

        worker = Worker(getattr(self.project, action), args, self.logger)
        worker.started.connect(self.actionStartedSlot)
        worker.finished.connect(self.actionFinishedSlot)
        worker.finished.connect(self.stateChanged)
        worker.finished.connect(self.stageChanged)

        self.workers_pool.start(worker)  # will automatically place to the queue



class Worker(QObject, QRunnable):
    """
    Generic worker for asynchronous processes: QObject + QRunnable combination. First allows to attach Qt signals,
    second is compatible with QThreadPool.
    """

    started = Signal(str, arguments=['action'])
    finished = Signal(str, bool, arguments=['action', 'success'])


    def __init__(self, func: Callable[[list], Optional[int]], args: list = None, logger: logging.Logger = None,
                 parent: QObject = None):
        """
        Args:
            func: function to run. It should return 0 or None to call to be considered successful
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
                # Print format is: "ExceptionName: message"
                self.logger.exception(traceback.format_exception_only(*(sys.exc_info()[:2]))[-1],
                                      exc_info=self.logger.isEnabledFor(logging.DEBUG))
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
            time.sleep(1.0)




class ProjectsList(QAbstractListModel):
    """
    QAbstractListModel implementation - describe basic operations and delegate all main functionality to the
    ProjectListItem.
    """

    duplicateFound = Signal(int, arguments=['duplicateIndex'])

    def __init__(self, projects: List[ProjectListItem] = None, parent: QObject = None):
        """
        Args:
            projects: initial list of projects
            parent: QObject to be parented to
        """
        super().__init__(parent=parent)
        self.projects = projects if projects is not None else []

    @Slot(int, result=ProjectListItem)
    def get(self, index: int):
        """
        Expose the ProjectListItem to the GUI QML side. You should firstly register the returning type using
        qmlRegisterType or similar.
        """
        if index in range(len(self.projects)):
            return self.projects[index]

    def rowCount(self, parent=None, *args, **kwargs):
        return len(self.projects)

    def data(self, index: QModelIndex, role=None):
        if role == Qt.DisplayRole or role is None:
            return self.projects[index.row()]

    def addProject(self, project: ProjectListItem):
        """
        Append already formed ProjectListItem to the projects list
        """
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self.projects.append(project)
        self.endInsertRows()

    @Slot('QStringList')
    def addProjectByPath(self, str_list: list):
        """
        Create, append to the end and save in QSettings a new ProjectListItem instance with a given QUrl path (typically
        is sent from the QML GUI).
        """

        if len(str_list) > 1:
            for path_str in str_list:
                self.addProjectByPath([path_str])
            return
        elif len(str_list) == 0:
            module_logger.warning("No path were given")
            return

        path_qurl = QUrl(str_list[0])
        if path_qurl.isLocalFile():
            path = path_qurl.toLocalFile()
        elif path_qurl.isRelative():  # this means that the path string is not starting with 'file://' prefix
            path = str_list[0]  # just use a source string
        else:
            module_logger.error(f"Incorrect path: {str_list[0]}")
            return

        # When we add a bunch of projects (or in the general case, too) recently added ones can be not instantiated yet
        # so we need to check
        duplicate_index = next((idx for idx, list_item in enumerate(self.projects) if list_item.project is not None and
                                list_item.project.path.samefile(pathlib.Path(path))), -1)
        if duplicate_index > -1:
            module_logger.warning(f"This project is already in the list: {path}")
            self.duplicateFound.emit(duplicate_index)  # notify the GUI
            return

        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())

        project = ProjectListItem(project_args=[path], parent=self)
        self.projects.append(project)

        self.endInsertRows()

        settings.beginGroup('app')
        settings.beginWriteArray('projects')
        settings.setArrayIndex(len(self.projects) - 1)
        settings.setValue('path', path)
        settings.endArray()
        settings.endGroup()

    @Slot(int)
    def removeProject(self, index: int):
        """
        Remove the project residing on the index both from the runtime list and QSettings
        """
        if index in range(len(self.projects)):
            self.beginRemoveRows(QModelIndex(), index, index)

            project = self.projects.pop(index)
            # It allows the project to be deconstructed (i.e. GC'ed) very soon, not at the app shutdown time
            project.deleteLater()

            self.endRemoveRows()

            settings.beginGroup('app')

            # Get current settings ...
            settings_projects_list = []
            for idx in range(settings.beginReadArray('projects')):
                settings.setArrayIndex(idx)
                settings_projects_list.append(settings.value('path'))
            settings.endArray()

            # ... drop the index ...
            settings_projects_list.pop(index)

            # ... and overwrite the list. We don't use self.projects[i].project.path as there is a chance that 'path'
            # doesn't exist (e.g. not initialized for some reason project) but reuse the current values
            settings.remove('projects')
            settings.beginWriteArray('projects')
            for idx, path in enumerate(settings_projects_list):
                settings.setArrayIndex(idx)
                settings.setValue('path', path)
            settings.endArray()

            settings.endGroup()




class Settings(QSettings):
    """
    Extend the class by useful get/set methods allowing to avoid redundant code lines and also are callable from the
    QML side
    """

    DEFAULTS = {
        'editor': '',
        'verbose': False,
        'notifications': True
    }

    def __init__(self, prefix: str, defaults: dict = None, qs_args: list = None, qs_kwargs: dict = None,
                 external_triggers: Dict[str, Callable[[str], Any]] = None):
        """
        Args:
            prefix: this prefix will always be added when get/set methods will be called so use it to group some most
                needed preferences under a single name. For example, prefix='app/params' while the list of users is
                located in 'app/users'
            defaults: dictionary of fallback values (under the prefix mentioned above) that will be used if there is no
                matching key in the storage
            qs_args: positional arguments that will be passed to the QSettings constructor
            qs_kwargs: keyword arguments that will be passed to the QSettings constructor
            external_triggers: dictionary where the keys are parameters names (under the prefix) and the values are
                functions that will be called with the corresponding parameter value as the argument when the parameter
                is going to be set. Itis useful for a setup of the additional actions needed to be performed right after
                a certain parameter gets an update
        """

        qs_args = qs_args if qs_args is not None else []
        qs_kwargs = qs_kwargs if qs_kwargs is not None else {}

        super().__init__(*qs_args, **qs_kwargs)

        self.prefix = prefix
        defaults = defaults if defaults is not None else self.DEFAULTS
        self.external_triggers = external_triggers if external_triggers is not None else {}

        for key, value in defaults.items():
            if not self.contains(self.prefix + key):
                self.setValue(self.prefix + key, value)

    @Slot()
    def clear(self):
        super().clear()


    @Slot(str, result='QVariant')
    def get(self, key):
        value = self.value(self.prefix + key)
        # Windows registry storage is case insensitive so 'False' is saved as 'false' and we need to handle this
        if value == 'false':
            value = False
        elif value == 'true':
            value = True
        return value


    @Slot(str, 'QVariant')
    def set(self, key, value):
        self.setValue(self.prefix + key, value)

        if key in self.external_triggers.keys():
            self.external_triggers[key](value)


def main():
    global module_logger
    module_log_handler = logging.StreamHandler()
    module_log_handler.setFormatter(logging.Formatter("%(levelname)s %(funcName)s %(message)s"))
    module_logger.addHandler(module_log_handler)
    module_logger.setLevel(logging.INFO)
    module_logger.info('Starting stm32pio_gui...')

    def qt_message_handler(mode, context, message):
        """
        Register this logging handler for the Qt stuff if your plarform doesn't provide the built-in one or if you want to
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

    # Apparently Windows version of PySide2 doesn't have QML logging feature turn on so we fill this gap
    # TODO: set up for other platforms too (separate console.debug, console.warn, etc.)
    qml_logger = logging.getLogger('qml')
    if platform.system() == 'Windows':
        qml_log_handler = logging.StreamHandler()
        qml_log_handler.setFormatter(logging.Formatter("[QML] %(levelname)s %(message)s"))
        qml_logger.addHandler(qml_log_handler)
        qInstallMessageHandler(qt_message_handler)


    # Most Linux distros should be linked with the QWidgets' QApplication instead of the QGuiApplication to enable
    # QtDialogs
    if platform.system() == 'Linux':
        app = QApplication(sys.argv)
    else:
        app = QGuiApplication(sys.argv)

    # Used as a settings identifier too
    app.setOrganizationName('ussserrr')
    app.setApplicationName('stm32pio')
    app.setWindowIcon(QIcon(str(MODULE_PATH.joinpath('icons/icon.svg'))))


    global settings

    def verbose_setter(value):
        module_logger.setLevel(logging.DEBUG if value else logging.INFO)
        for project in projects_model.projects:
            project.logger.setLevel(logging.DEBUG if value else logging.INFO)

    settings = Settings(prefix='app/settings/',
                        qs_kwargs={
                            'parent': app
                        },
                        external_triggers={
                            'verbose': verbose_setter
                        })
    # settings.clear()  # clear all
    # settings.remove('app/settings')
    # settings.remove('app/projects')

    module_logger.setLevel(logging.DEBUG if settings.get('verbose') else logging.INFO)
    qml_logger.setLevel(logging.DEBUG if settings.get('verbose') else logging.INFO)
    # if module_logger.isEnabledFor(logging.DEBUG):
    #     module_logger.debug("App QSettings:")
    #     for key in settings.allKeys():
    #         module_logger.debug(f"{key}: {settings.value(key)} (type: {type(settings.value(key))})")

    settings.beginGroup('app')
    projects_paths = []
    for index in range(settings.beginReadArray('projects')):
        settings.setArrayIndex(index)
        projects_paths.append(settings.value('path'))
    settings.endArray()
    settings.endGroup()


    engine = QQmlApplicationEngine(parent=app)

    qmlRegisterType(ProjectListItem, 'ProjectListItem', 1, 0, 'ProjectListItem')
    qmlRegisterType(Settings, 'Settings', 1, 0, 'Settings')

    projects_model = ProjectsList(parent=engine)
    boards = []
    boards_model = QStringListModel(parent=engine)

    engine.rootContext().setContextProperty('Logging', {
        logging.getLevelName(logging.CRITICAL): logging.CRITICAL,
        logging.getLevelName(logging.ERROR): logging.ERROR,
        logging.getLevelName(logging.WARNING): logging.WARNING,
        logging.getLevelName(logging.INFO): logging.INFO,
        logging.getLevelName(logging.DEBUG): logging.DEBUG,
        logging.getLevelName(logging.NOTSET): logging.NOTSET
    })
    engine.rootContext().setContextProperty('projectsModel', projects_model)
    engine.rootContext().setContextProperty('boardsModel', boards_model)
    engine.rootContext().setContextProperty('appSettings', settings)

    engine.load(QUrl.fromLocalFile(str(MODULE_PATH.joinpath('main.qml'))))

    main_window = engine.rootObjects()[0]


    # Getting PlatformIO boards can take long time when the PlatformIO cache is outdated but it is important to have
    # them before the projects list restoring, so we start a dedicated loading thread. We actually can add other
    # start-up operations here if there will be need to. Use the same Worker to spawn the thread at pool.

    def loading():
        nonlocal boards
        boards = ['None'] + stm32pio.util.get_platformio_boards('platformio')

    def loaded(_, success):
        boards_model.setStringList(boards)
        projects = [ProjectListItem(project_args=[path], from_startup=True, parent=projects_model) for path in projects_paths]
        for p in projects:
            projects_model.addProject(p)
        main_window.backendLoaded.emit()  # inform the GUI

    loader = Worker(loading, logger=module_logger)
    loader.finished.connect(loaded)
    QThreadPool.globalInstance().start(loader)


    return app.exec_()



# Globals
module_logger = logging.getLogger(__name__)  # use it as a console logger for whatever you want to, typically not
                                             # related to the concrete project
settings = QSettings()  # placeholder, will be replaced in main()



if __name__ == '__main__':
    sys.exit(main())
