import logging
import threading
import weakref
from typing import List, Mapping, Any, Optional

from PySide2.QtCore import QObject, Signal, QThreadPool, Property, Slot

import stm32pio.core.log
import stm32pio.core.project
import stm32pio.core.state
import stm32pio.core.settings

from stm32pio.gui.log import LoggingWorker, module_logger
from stm32pio.gui.util import Worker


class ProjectListItem(QObject):
    """
    The core functionality class - the wrapper around the Stm32pio class suitable for the project GUI representation
    """

    logAdded = Signal(str, int, arguments=['message', 'level'])  # send the log message to the front-end
    initialized = Signal()
    destructed = Signal()

    def __init__(self, project_args: List[Any] = None, project_kwargs: Mapping[str, Any] = None,
                 from_startup: bool = False, parent: QObject = None):
        """
        Instance construction is split into 2 phases: the wrapper setup and inner Stm32pio class initialization. The
        latter one is taken out to the separated thread as it is, potentially, a time-consuming operation. This thread
        starts right after the main constructor so the wrapper is already built at that moment and therefore can be used
        from GUI, be referenced and so on.

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

        underlying_logger = logging.getLogger('stm32pio.gui.projects')
        self.logger = stm32pio.core.log.ProjectLogger(underlying_logger, project_id=id(self))
        self.logging_worker = LoggingWorker(project_id=id(self))
        self.logging_worker.sendLog.connect(self.logAdded)

        # QThreadPool can automatically queue new incoming tasks if a number of them are larger than maxThreadCount
        self.workers_pool = QThreadPool(parent=self)
        self.workers_pool.setMaxThreadCount(1)
        self.workers_pool.setExpiryTimeout(-1)  # tasks wait forever for the available spot

        self._current_action: str = 'loading'
        self._last_action_succeed: bool = True

        # These values are valid only until the Stm32pio project initialize itself (or failed to) (see init_project)
        self.project: Optional[stm32pio.core.project.Stm32pio] = None
        # Use a project path string (as it should be a first argument) as a name
        self._name = str(project_args[0]) if len(project_args) else 'Undefined'
        self._state = { 'LOADING': True }  # pseudo-stage (not present in the ProjectStage enum but is used from QML)
        self._current_stage = 'LOADING'

        self.qml_ready = threading.Event()  # the front and the back both should know when each other is initialized
        self.should_be_destroyed = threading.Event()  # currently, is used just to "cancel" the initialization thread

        # Register some kind of the deconstruction handler (later, after the project initialization, see init_project)
        self._finalizer = None

        if 'logger' not in project_kwargs:
            project_kwargs['logger'] = self.logger

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
            self.project = stm32pio.core.project.Stm32pio(*args, **kwargs)
        except:
            stm32pio.core.log.log_current_exception(self.logger)
            self._state = { 'INIT_ERROR': True }  # pseudo-stage
            self._current_stage = 'INIT_ERROR'
        else:
            if self.project.config.get('project', 'inspect_ioc').lower() in stm32pio.core.settings.yes_options and \
               self.project.state.current_stage > stm32pio.core.state.ProjectStage.EMPTY:
                self.project.inspect_ioc_config()
        finally:
            # Register some kind of the deconstruction handler
            self._finalizer = weakref.finalize(self, self.at_exit, self.workers_pool, self.logging_worker,
                                               self.name if self.project is None else str(self.project))
            self._current_action = ''

            # Wait for the GUI to initialize (which one is earlier, actually, back or front)
            while not self.qml_ready.wait(timeout=0.050):
                # When item is located out of visible scope then QML doesn't load its visual representation so this
                # initialization thread is kept hanging. This is OK except when the app shutting down, it prevents
                # Python GC of calling weakref for finalization process. So we introduce additional flag to be able
                # to quit the thread
                if self.should_be_destroyed.is_set():
                    break

            if not self.should_be_destroyed.is_set():
                self.updateState()
                self.initialized.emit()
                self.nameChanged.emit()  # in any case we should notify the GUI part about the initialization ending


    @staticmethod
    def at_exit(workers_pool: QThreadPool, logging_worker: LoggingWorker, name: str):
        """
        The instance deconstruction handler is meant to be used with weakref.finalize() conforming with the requirement
        to have no reference to the target object (so it doesn't contain any instance reference and also is decorated as
        'staticmethod')
        """
        # Wait forever for all the jobs to complete. Currently, we cannot abort them gracefully
        workers_pool.waitForDone(msecs=-1)
        logging_worker.stopped.set()  # post the event in the logging worker to inform it...
        logging_worker.thread.wait()  # ...and wait for it to exit, too
        module_logger.debug(f"destroyed {name}")

    def deleteLater(self) -> None:
        self.destructed.emit()
        return super().deleteLater()

    @Slot()
    def qmlLoaded(self):
        """Event signaling the complete loading of the needed frontend components"""
        self.qml_ready.set()
        self.logging_worker.can_flush_log.set()

    @Property(bool)
    def fromStartup(self) -> bool:
        """Is this project is here from the beginning of the app life?"""
        return self._from_startup

    @Property('QVariant')
    def config(self) -> dict:
        """Inner project's ConfigParser config converted to the dictionary (QML JS object)"""
        # TODO: cache this? (related to live-reloaded settings...)
        return {
            section: {
                key: value for key, value in self.project.config.items(section)
            } if self.project is not None else {} for section in ['app', 'project']
        }

    nameChanged = Signal()
    @Property(str, notify=nameChanged)
    def name(self) -> str:
        """Human-readable name of the project. Will evaluate to the absolute path if it cannot be instantiated"""
        if self.project is not None:
            return self.project.path.name
        else:
            return self._name

    stateChanged = Signal()
    @Property('QVariant', notify=stateChanged)
    def state(self) -> dict:
        """
        Get the current project state in the appropriate Qt form. Update the cached 'current stage' value as a side
        effect
        """
        if type(self._state) == stm32pio.core.state.ProjectState:
            return { stage.name: value for stage, value in self._state.items() }
        else:
            return self._state

    @Slot()
    def updateState(self):
        if self.project is not None:
            self._state = self.project.state
        self.stateChanged.emit()
        self.currentStageChanged.emit()

    currentStageChanged = Signal()
    @Property(str, notify=currentStageChanged)
    def currentStage(self) -> str:
        """
        Get the current stage the project resides in.
        Note: this returns a cached value. Cache updates every time the state property got requested
        """
        if type(self._state) == stm32pio.core.state.ProjectState:
            return self._state.current_stage.name
        else:
            return self._current_stage

    @Property(str)
    def currentAction(self) -> str:
        """
        Stm32pio action (i.e. function name) that is currently executing or an empty string if there is none. It is set
        on actionStarted signal and reset on actionFinished
        """
        return self._current_action

    @Property(bool)
    def lastActionSucceed(self) -> bool:
        """Have the last action ended with a success?"""
        return self._last_action_succeed

    actionStarted = Signal(str, arguments=['action'])
    @Slot(str)
    def actionStartedSlot(self, action: str):
        """Pass the corresponding signal from the worker, perform related tasks"""
        # Currently, this property should be set BEFORE emitting the 'actionStarted' signal (because QML will query it
        # when the signal will be handled in StateMachine) (probably, should be resolved later as it is bad to be bound
        # to such a specific logic)
        self._current_action = action
        self.actionStarted.emit(action)

    actionFinished = Signal(str, bool, arguments=['action', 'success'])
    @Slot(str, bool)
    def actionFinishedSlot(self, action: str, success: bool):
        """Pass the corresponding signal from the worker, perform related tasks"""
        self._last_action_succeed = success
        if not success:
            # Clear the queue - stop further execution (cancel planned tasks if an error had happened)
            self.workers_pool.clear()
        self.actionFinished.emit(action, success)
        # Currently, this property should be reset AFTER emitting the 'actionFinished' signal (because QML will query it
        # when the signal will be handled in StateMachine) (probably, should be resolved later as it is bad to be bound
        # to such a specific logic)
        self._current_action = ''


    @Slot(str, 'QVariantList')
    def run(self, action: str, args: List[Any]):
        """
        Asynchronously perform Stm32pio actions (generate, build, etc.) (dispatch all business logic).

        Args:
            action: method name of the corresponding Stm32pio action
            args: list of positional arguments for this action
        """

        worker = Worker(getattr(self.project, action), args, self.logger, parent=self)
        worker.started.connect(self.actionStartedSlot)
        worker.finished.connect(self.actionFinishedSlot)
        worker.finished.connect(self.updateState)
        worker.finished.connect(self.currentStageChanged)

        self.workers_pool.start(worker)  # will automatically place to the queue
