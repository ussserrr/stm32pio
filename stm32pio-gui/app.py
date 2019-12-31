#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys
import time

from PySide2.QtCore import QCoreApplication, QUrl, QAbstractItemModel, Property, QAbstractListModel, QModelIndex, \
    QObject, Qt, Slot, Signal, QTimer
from PySide2.QtGui import QGuiApplication
from PySide2.QtQml import qmlRegisterType, QQmlEngine, QQmlComponent, QQmlApplicationEngine
from PySide2.QtQuick import QQuickView

import stm32pio.settings
import stm32pio.lib
import stm32pio.util



special_formatters = {'subprocess': logging.Formatter('%(message)s')}


class ProjectListItem(stm32pio.lib.Stm32pio, QObject):
    # nameChanged = Signal()

    def __init__(self, dirty_path: str, parameters: dict = None, save_on_destruction: bool = True, qt_parent=None):
        QObject.__init__(self, parent=qt_parent)

        this = self
        class InternalHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                print(record)
                this.log(self.format(record))
        self.handler = InternalHandler()
        logger = logging.getLogger(f"{stm32pio.lib.__name__}.{id(self)}")
        logger.addHandler(self.handler)
        logger.setLevel(logging.DEBUG)
        self.handler.setFormatter(stm32pio.util.DispatchingFormatter(
            f"%(levelname)-8s %(funcName)-{stm32pio.settings.log_fieldwidth_function}s %(message)s",
            special=special_formatters))

        stm32pio.lib.Stm32pio.__init__(self, dirty_path, parameters=parameters, save_on_destruction=save_on_destruction)
        self._name = self.path.name

    logAdded = Signal(str, arguments=['message'])
    def log(self, message):
        self.logAdded.emit(message)

    @Property(str)
    def name(self):
        return self._name

    # @name.setter
    # def name(self, value):
    #     if self._name == value:
    #         return
    #     self._name = value
    #     self.nameChanged.emit()

    @Property(str)
    def state(self):
        return str(super().state)

    @Slot()
    def clean(self) -> None:
        print('clean was called')
        super().clean()


class ProjectsList(QAbstractListModel):
    def __init__(self, projects: list, parent=None):
        super().__init__(parent)
        self.projects = projects

    @Slot(int, result=ProjectListItem)
    def getProject(self, index):
        print('getProject', index)
        return self.projects[index]

    def rowCount(self, parent=None, *args, **kwargs):
        return len(self.projects)

    def data(self, index: QModelIndex, role=None):
        # print(index.row(), role)
        if role == Qt.DisplayRole:
            return self.projects[index.row()]

    def addProject(self, project):
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self.projects.append(project)
        self.endInsertRows()

    @Slot(int, str)
    def run(self, index, action):
        print('index:', index, action)
        # time.sleep(10)
        getattr(self.projects[index], action)()



if __name__ == '__main__':
    # logger = logging.getLogger('stm32pio')  # the root (relatively to the possible outer scope) logger instance
    # handler = InternalHandler()
    # logger.addHandler(handler)
    # special_formatters = {'subprocess': logging.Formatter('%(message)s')}
    # logger.setLevel(logging.DEBUG)
    # handler.setFormatter(stm32pio.util.DispatchingFormatter(
    #     f"%(levelname)-8s %(funcName)-{stm32pio.settings.log_fieldwidth_function}s %(message)s",
    #     special=special_formatters))
    # logger.debug("debug logging enabled")

    app = QGuiApplication(sys.argv)

    engine = QQmlApplicationEngine()

    print('AAAAAAAAAAA', qmlRegisterType(ProjectListItem, 'ProjectListItem', 1, 0, 'ProjectListItem'))

    projects = ProjectsList([])
    projects.addProject(ProjectListItem('../stm32pio-test-project', save_on_destruction=False))
    projects.addProject(ProjectListItem('../stm32pio-test-project', save_on_destruction=False))
    projects.addProject(ProjectListItem('../stm32pio-test-project', save_on_destruction=False))

    # def update_value():
    #     projects.projects[1].name = 'def'
    # timer = QTimer()
    # timer.timeout.connect(update_value)
    # timer.start(2000)

    # First approach
    engine.rootContext().setContextProperty("projectsModel", projects)
    engine.load(QUrl('main.qml'))

    # Second approach
    # view = QQuickView()
    # view.setResizeMode(QQuickView.SizeRootObjectToView)
    # view.rootContext().setContextProperty('projectsModel', projects)
    # view.setSource(QUrl('main.qml'))

    engine.rootObjects()[0].findChildren(QObject)

    engine.quit.connect(app.quit)
    sys.exit(app.exec_())
