#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import collections
import functools
import logging
import pathlib
import queue
import sys
import threading
import time
import weakref

from PySide2.QtCore import QCoreApplication, QUrl, QAbstractItemModel, Property, QAbstractListModel, QModelIndex, \
    QObject, Qt, Slot, Signal, QTimer, QThread
from PySide2.QtGui import QGuiApplication
from PySide2.QtQml import qmlRegisterType, QQmlEngine, QQmlComponent, QQmlApplicationEngine
from PySide2.QtQuick import QQuickView

sys.path.insert(0, str(pathlib.Path(sys.path[0]).parent))

import stm32pio.settings
import stm32pio.lib
import stm32pio.util



special_formatters = {'subprocess': logging.Formatter('%(message)s')}


# class RepetitiveTimer(threading.Thread):
#     def __init__(self, stopped, callable, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.stopped = stopped
#         self.callable = callable
#
#     def run(self) -> None:
#         print('start')
#         while not self.stopped.wait(timeout=0.005):
#             self.callable()
#         print('exitttt')
#
#
# class InternalHandler(logging.Handler):
#     def __init__(self, parent: QObject):
#         super().__init__()
#         self.parent = parent
#         # self.temp_logs = []
#
#         self.queued_buffer = collections.deque()
#
#         self.stopped = threading.Event()
#         self.timer = RepetitiveTimer(self.stopped, self.log)
#         self.timer.start()
#
#         self._finalizer = weakref.finalize(self, self.at_exit)
#
#     def at_exit(self):
#         print('exit')
#         self.stopped.set()
#
#     def log(self):
#         if self.parent.is_bound:
#             try:
#                 m = self.format(self.queued_buffer.popleft())
#                 # print('initialized', m)
#                 self.parent.logAdded.emit(m)
#             except IndexError:
#                 pass
#
#     def emit(self, record: logging.LogRecord) -> None:
#         # msg = self.format(record)
#         # print(msg)
#         self.queued_buffer.append(record)
#         # if not self.parent.is_bound:
#         #     self.temp_logs.append(msg)
#         # else:
#         #     if len(self.temp_logs):
#         #         self.temp_logs.reverse()
#         #         for i in range(len(self.temp_logs)):
#         #             m = self.temp_logs.pop()
#         #             self.parent.logAdded.emit(m)
#         #     self.parent.logAdded.emit(msg)

class LoggingHandler(logging.Handler):
    def __init__(self, signal: Signal, parent_ready_event: threading.Event):
        super().__init__()
        self.temp_logs = []
        self.signal = signal
        self.parent_ready_event = parent_ready_event

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        print(msg)
        # self.queued_buffer.append(record)
        if not self.parent_ready_event.is_set():
            self.temp_logs.append(msg)
        else:
            if len(self.temp_logs):
                self.temp_logs.reverse()
                for i in range(len(self.temp_logs)):
                    m = self.temp_logs.pop()
                    self.signal.emit(m)
            self.signal.emit(msg)


class HandlerWorker(QObject):
    addLog = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.parent_ready = threading.Event()

        self.logging_handler = LoggingHandler(self.addLog, self.parent_ready)

        # self.queued_buffer = collections.deque()

    # @Slot()
    # def cccompleted(self):
    #     print('completed from ProjectListItem')
    #     self.parent_ready.set()

    #     self.stopped = threading.Event()
    #     self.timer = RepetitiveTimer(self.stopped, self.log)
    #     self.timer.start()
    #
    # def log(self):
    #     if self.parent_ready:
    #         try:
    #             m = self.format(self.queued_buffer.popleft())
    #             # print('initialized', m)
    #             self.addLog.emit(m)
    #         except IndexError:
    #             pass


class Stm32pio(stm32pio.lib.Stm32pio):
    def save_config(self):
        self.config.save()


class ProjectListItem(QObject):
    nameChanged = Signal()
    stateChanged = Signal()
    stageChanged = Signal()
    logAdded = Signal(str, arguments=['message'])
    actionResult = Signal(str, bool, arguments=['action', 'success'])
    # ccompleted = Signal()

    def __init__(self, project_args: list = None, project_kwargs: dict = None, parent: QObject = None):
        QObject.__init__(self, parent=parent)

        self.logThread = QThread()  # TODO: can be a 'daemon' type as it runs alongside the main for a long time
        self.handler = HandlerWorker()
        self.handler.moveToThread(self.logThread)
        self.handler.addLog.connect(self.logAdded)
        # self.ccompleted.connect(self.handler.cccompleted)

        self.logger = logging.getLogger(f"{stm32pio.lib.__name__}.{id(self)}")
        self.logger.addHandler(self.handler.logging_handler)
        self.logger.setLevel(logging.DEBUG)
        self.handler.logging_handler.setFormatter(stm32pio.util.DispatchingFormatter(
            f"%(levelname)-8s %(funcName)-{stm32pio.settings.log_fieldwidth_function}s %(message)s",
            special=special_formatters))

        self.logThread.start()

        self.worker = ProjectActionWorker(self.logger, lambda: None)

        self.project = None
        self._name = 'Loading...'
        self._state = { 'LOADING': True }
        self._current_stage = 'Loading...'

        self.qml_ready = threading.Event()

        # self.destroyed.connect(self.at_exit)
        self._finalizer2 = weakref.finalize(self, self.at_exit)

        if project_args is not None:
            if 'logger' not in project_kwargs:
                project_kwargs['logger'] = self.logger

            self.init_thread = threading.Thread(target=self.init_project, args=project_args, kwargs=project_kwargs)
            self.init_thread.start()
            # self.init_project(*project_args, **project_kwargs)

        # def update_value():
        #     # m = 'SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND '
        #     # print(m, flush=True)
        #     self.config.save()
        #     self.stateChanged.emit()
        #     # self.logAdded.emit(m)
        # self.timer = threading.Timer(5, update_value)
        # self.timer.start()

    def init_project(self, *args, **kwargs):
        try:
            # import time
            # time.sleep(1)
            if args[0] == '/Users/chufyrev/Documents/GitHub/stm32pio/Orange':
                raise Exception("Error during initialization")
            self.project = Stm32pio(*args, **kwargs)
        except Exception as e:
            self.logger.exception(e, exc_info=self.logger.isEnabledFor(logging.DEBUG))
            self._name = args[0]  # FIXME
            self._state = { 'INIT_ERROR': True }
            self._current_stage = 'Initializing error'
        self.qml_ready.wait()
        self.nameChanged.emit()
        self.stageChanged.emit()
        self.stateChanged.emit()
        # self.worker = ProjectActionWorker(self.logger, job)

    def at_exit(self):
        print('destroy', self)
        self.logger.removeHandler(self.handler)
        self.logThread.quit()

    @Property(str, notify=nameChanged)
    def name(self):
        if self.project is not None:
            return self.project.path.name
        else:
            return self._name

    @Property('QVariant', notify=stateChanged)
    def state(self):
        if self.project is not None:
            return { s.name: value for s, value in self.project.state.items() }
        else:
            return self._state

    @Property(str, notify=stageChanged)
    def current_stage(self):
        # print('wants current_stage')
        if self.project is not None:
            return str(self.project.state.current_stage)
        else:
            return self._current_stage

    # @Slot(result=bool)
    # def is_present(self):
    #     return self.state[stm32pio.lib.ProjectStage.EMPTY]

    @Slot()
    def completed(self):
        print('completed from QML')
        self.qml_ready.set()
        self.handler.parent_ready.set()
        # self.handler.cccompleted()

    @Slot(str, 'QVariantList')
    def run(self, action, args):
        self.worker = ProjectActionWorker(self.logger, getattr(self.project, action), args)

        self.worker.actionResult.connect(self.stateChanged)
        self.worker.actionResult.connect(self.stageChanged)
        self.worker.actionResult.connect(self.actionResult)


    # @Slot(str)
    # def stop(self, action):
    #     if self.worker.thread.isRunning() and self.worker.name == action:
    #         print('===============================', self.worker.thread.quit())


    # def save_config(self):
    #     return self.config.save()

        # this = super()
        # class Worker(QThread):
        #     def run(self):
        #         this.generate_code()
        # self.w = Worker()
        # self.w.start()

        # return super().generate_code()


class ProjectActionWorker(QObject):
    actionResult = Signal(str, bool, arguments=['action', 'success'])

    def __init__(self, logger, func, args=None):
        super().__init__(parent=None)  # QObject with a parent cannot be moved to any thread

        self.logger = logger
        self.func = func
        if args is None:
            self.args = []
        else:
            self.args = args
        self.name = func.__name__

        self.thread = QThread()
        self.moveToThread(self.thread)
        self.actionResult.connect(self.thread.quit)

        self.thread.started.connect(self.job)
        self.thread.start()


    def job(self):
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
        self.actionResult.emit(self.name, success)


class ProjectsList(QAbstractListModel):

    def __init__(self, projects: list, parent=None):
        super().__init__(parent)
        self.projects = projects
        self._finalizer = weakref.finalize(self, self.at_exit)

    @Slot(int, result=ProjectListItem)
    def getProject(self, index):
        return self.projects[index]

    def rowCount(self, parent=None, *args, **kwargs):
        return len(self.projects)

    def data(self, index: QModelIndex, role=None):
        if role == Qt.DisplayRole:
            return self.projects[index.row()]

    def add(self, project):
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self.projects.append(project)
        self.endInsertRows()

    @Slot(QUrl)
    def addProject(self, path):
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        project = ProjectListItem(project_args=[path.toLocalFile()],
                                  project_kwargs=dict(save_on_destruction=False, parameters={'board': 'nucleo_f031k6'}))
        # project = ProjectListItem()
        self.projects.append(project)
        self.endInsertRows()
        # project.init_project(path.toLocalFile(), save_on_destruction=False, parameters={ 'board': 'nucleo_f031k6' }, logger=project.logger)

        # self.adding_project = None
        # def job():
        #     self.adding_project = ProjectListItem(path.toLocalFile(), save_on_destruction=False, parameters={ 'board': 'nucleo_f031k6' })
        #     self.adding_project.moveToThread(app.thread())
        # self.worker = ProjectActionWorker(None, job)
        # self.worker.actionResult.connect(self.add)

    @Slot(int)
    def removeProject(self, index):
        self.beginRemoveRows(QModelIndex(), index, index)
        self.projects.pop(index)
        self.endRemoveRows()

    def at_exit(self):
        print('destroy', self)
        # self.logger.removeHandler(self.handler)



if __name__ == '__main__':
    app = QGuiApplication(sys.argv)

    engine = QQmlApplicationEngine()

    qmlRegisterType(ProjectListItem, 'ProjectListItem', 1, 0, 'ProjectListItem')

    apple = ProjectListItem(project_args=['Apple'], project_kwargs=dict(save_on_destruction=False, parameters={ 'board': 'nucleo_f031k6' }))
    # orange = ProjectListItem(project_args=['Orange'], project_kwargs=dict(save_on_destruction=False, parameters={ 'board': 'nucleo_f031k6' }))
    # peach = ProjectListItem(project_args=['Peach'], project_kwargs=dict(save_on_destruction=False, parameters={ 'board': 'nucleo_f031k6' }))
    # apple.init_project()

    projects = ProjectsList([
        apple,
        # orange,
        # peach
    ])
    # projects.addProject('Apple')
    # projects.add(ProjectListItem('../stm32pio-test-project', save_on_destruction=False))

    engine.rootContext().setContextProperty('projectsModel', projects)
    engine.load(QUrl.fromLocalFile('stm32pio-gui/main.qml'))
    # engine.quit.connect(app.quit)

    sys.exit(app.exec_())
