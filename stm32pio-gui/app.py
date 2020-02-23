#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import collections
import logging
import pathlib
import sys
import threading
import time
import weakref

from PySide2.QtCore import QCoreApplication, QUrl, Property, QAbstractListModel, QModelIndex, \
    QObject, Qt, Slot, Signal, QTimer, QThread, qInstallMessageHandler, QtInfoMsg, QtWarningMsg, QtCriticalMsg, \
    QtFatalMsg, QThreadPool, QRunnable, QStringListModel, QSettings
# for Manjaro
# from PySide2.QtWidgets import QApplication
from PySide2.QtGui import QGuiApplication
from PySide2.QtQml import qmlRegisterType, QQmlApplicationEngine


sys.path.insert(0, str(pathlib.Path(sys.path[0]).parent))

import stm32pio.settings
import stm32pio.lib
import stm32pio.util



special_formatters = {'subprocess': logging.Formatter('%(message)s')}


class LoggingHandler(logging.Handler):
    def __init__(self, buffer):
        super().__init__()
        self.buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        self.buffer.append(record)


class LoggingWorker(QObject):
    addLog = Signal(str, int)

    def __init__(self, logger):
        super().__init__(parent=None)

        self.buffer = collections.deque()
        self.stopped = threading.Event()
        self.can_flush_log = threading.Event()
        self.logging_handler = LoggingHandler(self.buffer)

        logger.addHandler(self.logging_handler)
        self.logging_handler.setFormatter(stm32pio.util.DispatchingFormatter(
            f"%(levelname)-8s %(funcName)-{stm32pio.settings.log_fieldwidth_function}s %(message)s",
            special=special_formatters))

        self.thread = QThread()
        self.moveToThread(self.thread)

        self.thread.started.connect(self.routine)
        self.thread.start()

    def routine(self):
        while not self.stopped.wait(timeout=0.050):
            if self.can_flush_log.is_set():
                try:
                    record = self.buffer.popleft()
                    m = self.logging_handler.format(record)
                    self.addLog.emit(m, record.levelno)
                except IndexError:
                    pass
        print('quit logging thread')
        self.thread.quit()



class Stm32pio(stm32pio.lib.Stm32pio):
    def save_config(self, parameters: dict = None):
        # raise Exception('test')
        if parameters is not None:
            for section_name, section_value in parameters.items():
                for key, value in section_value.items():
                    self.config.set(section_name, key, value)
        self.config.save()


class ProjectListItem(QObject):
    nameChanged = Signal()
    stateChanged = Signal()
    stageChanged = Signal()
    logAdded = Signal(str, int, arguments=['message', 'level'])
    actionResult = Signal(str, bool, arguments=['action', 'success'])

    def __init__(self, project_args: list = None, project_kwargs: dict = None, parent: QObject = None):
        super().__init__(parent=parent)

        self.logger = logging.getLogger(f"{stm32pio.lib.__name__}.{id(self)}")
        self.logger.setLevel(logging.DEBUG if settings.get('verbose') else logging.INFO)
        self.logging_worker = LoggingWorker(self.logger)
        self.logging_worker.addLog.connect(self.logAdded)

        self.workers_pool = QThreadPool()
        self.workers_pool.setMaxThreadCount(1)
        self.workers_pool.setExpiryTimeout(-1)

        self.project = None
        self._name = 'Loading...'
        self._state = { 'LOADING': True }
        self._current_stage = 'Loading...'

        self.qml_ready = threading.Event()

        self._finalizer2 = weakref.finalize(self, self.at_exit)

        if project_args is not None:
            if 'logger' not in project_kwargs:
                project_kwargs['logger'] = self.logger

            self.init_thread = threading.Thread(target=self.init_project, args=project_args, kwargs=project_kwargs)
            self.init_thread.start()


    def init_project(self, *args, **kwargs):
        try:
            # print('start to init in python')
            # time.sleep(3)
            # if args[0] == '/Users/chufyrev/Documents/GitHub/stm32pio/Orange':
            # raise Exception("Error during initialization")
            self.project = Stm32pio(*args, **kwargs)
        except Exception as e:
            self.logger.exception(e, exc_info=self.logger.isEnabledFor(logging.DEBUG))
            self._name = args[0]  # FIXME check if available
            self._state = { 'INIT_ERROR': True }
            self._current_stage = 'Initializing error'
        else:
            # TODO: maybe remove _-values
            pass
        finally:
            self.qml_ready.wait()
            # print('end to init in python')
            self.nameChanged.emit()
            self.stageChanged.emit()
            self.stateChanged.emit()

    def at_exit(self):
        print('destroy', self)
        self.workers_pool.waitForDone(msecs=-1)
        self.logging_worker.stopped.set()
        # self.logThread.quit()

    @Property(str, notify=nameChanged)
    def name(self):
        if self.project is not None:
            return self.project.path.name
        else:
            return self._name

    @Property('QVariant', notify=stateChanged)
    def state(self):
        if self.project is not None:
            return { s.name: value for s, value in self.project.state.items() if s != stm32pio.lib.ProjectStage.UNDEFINED }
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
    def completed(self):
        print('completed from QML')
        self.qml_ready.set()
        self.logging_worker.can_flush_log.set()

    @Slot(str, 'QVariantList')
    def run(self, action, args):
        # TODO: queue or smth of jobs
        worker = NewProjectActionWorker(getattr(self.project, action), args, self.logger)
        worker.actionResult.connect(self.stateChanged)
        worker.actionResult.connect(self.stageChanged)
        worker.actionResult.connect(self.actionResult)

        self.workers_pool.start(worker)

    @Slot()
    def test(self):
        print('test')


class NewProjectActionWorker(QObject, QRunnable):
    actionResult = Signal(str, bool, arguments=['action', 'success'])

    def __init__(self, func, args=None, logger=None):
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
        self.actionResult.emit(self.name, success)




class ProjectsList(QAbstractListModel):

    def __init__(self, projects: list = None, parent=None):
        super().__init__(parent=parent)
        self.projects = projects if projects is not None else []
        self._finalizer = weakref.finalize(self, self.at_exit)

    @Slot(int, result=ProjectListItem)
    def getProject(self, index):
        if index in range(len(self.projects)):
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
            for index in range(len(self.projects)):
                settings.setArrayIndex(index)
                settings.setValue('path', str(self.projects[index].project.path))
            settings.endArray()
            settings.endGroup()

            self.endRemoveRows()
            # print('removed')

    def at_exit(self):
        print('destroy', self)
        # self.logger.removeHandler(self.handler)



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
    if stm32pio.settings.my_os == 'Windows':
        qInstallMessageHandler(qt_message_handler)

    app = QGuiApplication(sys.argv)
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

    def on_loading():
        boards_model.setStringList(boards)
        projects = [ProjectListItem(project_args=[path], project_kwargs=dict(save_on_destruction=False)) for path in projects_paths]
        # projects = [
        #     ProjectListItem(project_args=['Apple'], project_kwargs=dict(save_on_destruction=False)),
        #     ProjectListItem(project_args=['Orange'], project_kwargs=dict(save_on_destruction=False)),
        #     ProjectListItem(project_args=['Peach'], project_kwargs=dict(save_on_destruction=False))
        # ]
        for p in projects:
            projects_model.add(p)
        main_window.backendLoaded.emit()

    loader = NewProjectActionWorker(loading)
    loader.actionResult.connect(on_loading)
    QThreadPool.globalInstance().start(loader)

    sys.exit(app.exec_())
