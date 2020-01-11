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


class RepetitiveTimer(threading.Thread):
    def __init__(self, stopped, callable, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stopped = stopped
        self.callable = callable

    def run(self) -> None:
        print('start')
        while not self.stopped.wait(timeout=0.005):
            self.callable()
        print('exitttt')


class InternalHandler(logging.Handler):
    def __init__(self, parent: QObject):
        super().__init__()
        self.parent = parent
        # self.temp_logs = []

        self.queued_buffer = collections.deque()

        self.stopped = threading.Event()
        self.timer = RepetitiveTimer(self.stopped, self.log)
        self.timer.start()

        self._finalizer = weakref.finalize(self, self.at_exit)

    def at_exit(self):
        print('exit')
        self.stopped.set()

    def log(self):
        if self.parent.is_bound:
            try:
                m = self.format(self.queued_buffer.popleft())
                # print('initialized', m)
                self.parent.logAdded.emit(m)
            except IndexError:
                pass

    def emit(self, record: logging.LogRecord) -> None:
        # msg = self.format(record)
        # print(msg)
        self.queued_buffer.append(record)
        # if not self.parent.is_bound:
        #     self.temp_logs.append(msg)
        # else:
        #     if len(self.temp_logs):
        #         self.temp_logs.reverse()
        #         for i in range(len(self.temp_logs)):
        #             m = self.temp_logs.pop()
        #             self.parent.logAdded.emit(m)
        #     self.parent.logAdded.emit(msg)


class HandlerWorker(QObject):
    addLog = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.temp_logs = []
        self.parent_ready = False

        this = self
        class H(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                msg = self.format(record)
                # print(msg)
                # self.queued_buffer.append(record)
                # if not this.parent_ready:
                #     this.temp_logs.append(msg)
                # else:
                #     if len(this.temp_logs):
                #         this.temp_logs.reverse()
                #         for i in range(len(this.temp_logs)):
                #             m = this.temp_logs.pop()
                #             this.addLog.emit(m)
                this.addLog.emit(msg)

        self.handler = H()

        # self.queued_buffer = collections.deque()

    # @Slot()
    # def cccompleted(self):
    #     self.parent_ready = True

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




class ProjectListItem(stm32pio.lib.Stm32pio, QObject):
    stateChanged = Signal()
    logAdded = Signal(str, arguments=['message'])
    # ccompleted = Signal()

    def __init__(self, dirty_path: str, parameters: dict = None, save_on_destruction: bool = True, parent=None):
        self.is_bound = False

        QObject.__init__(self, parent=parent)

        self.logThread = QThread()
        self.handler = HandlerWorker()
        self.handler.moveToThread(self.logThread)
        self.handler.addLog.connect(self.logAdded)
        # self.ccompleted.connect(self.handler.cccompleted)
        self.logThread.start()

        self.logger = logging.getLogger(f"{stm32pio.lib.__name__}.{id(self)}")
        self.logger.addHandler(self.handler.handler)
        self.logger.setLevel(logging.DEBUG)
        self.handler.handler.setFormatter(stm32pio.util.DispatchingFormatter(
            f"%(levelname)-8s %(funcName)-{stm32pio.settings.log_fieldwidth_function}s %(message)s",
            special=special_formatters))

        stm32pio.lib.Stm32pio.__init__(self, dirty_path, parameters=parameters, save_on_destruction=save_on_destruction)

        self._name = self.path.name

        # self.destroyed.connect(self.at_exit)
        self._finalizer = weakref.finalize(self, self.at_exit)

        # def update_value():
        #     # m = 'SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND SEND '
        #     # print(m, flush=True)
        #     self.config.save()
        #     self.stateChanged.emit()
        #     # self.logAdded.emit(m)
        # self.timer = threading.Timer(5, update_value)
        # self.timer.start()

    def at_exit(self):
        print('destroy', self)
        self.logThread.quit()
        self.logger.removeHandler(self.handler)

    @Property(str)
    def name(self):
        return self._name

    @Property(str, notify=stateChanged)
    def state(self):
        return str(super().state)

    @Slot()
    def completed(self):
        pass
        # self.handler.cccompleted()

    @Slot(str, 'QVariantList')
    def run(self, action, args):
        # print(action, args)
        # return
        this = self
        def job():
            getattr(this, action)(*args)
            this.stateChanged.emit()
        t = threading.Thread(target=job)
        t.start()

        # this = super()
        # class Worker(QThread):
        #     def run(self):
        #         this.generate_code()
        # self.w = Worker()
        # self.w.start()

        # return super().generate_code()


class ProjectsList(QAbstractListModel):

    def __init__(self, projects: list, parent=None):
        super().__init__(parent)
        self.projects = projects
        # self.destroyed.connect(functools.partial(ProjectsList.at_exit, self.__dict__))
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
        self.projects.append(ProjectListItem(path.toLocalFile(), save_on_destruction=False))
        self.endInsertRows()

    # @staticmethod
    def at_exit(self):
        print('destroy', self)
        # self.logger.removeHandler(self.handler)



if __name__ == '__main__':
    app = QGuiApplication(sys.argv)

    engine = QQmlApplicationEngine()

    qmlRegisterType(ProjectListItem, 'ProjectListItem', 1, 0, 'ProjectListItem')

    projects = ProjectsList([
        ProjectListItem('stm32pio-test-project', save_on_destruction=False),
        # ProjectListItem('../stm32pio-test-project', save_on_destruction=False),
        # ProjectListItem('../stm32pio-test-project', save_on_destruction=False)
    ])
    # projects.add(ProjectListItem('../stm32pio-test-project', save_on_destruction=False))

    engine.rootContext().setContextProperty("projectsModel", projects)
    engine.load(QUrl.fromLocalFile('stm32pio-gui/main.qml'))
    # engine.quit.connect(app.quit)

    sys.exit(app.exec_())
