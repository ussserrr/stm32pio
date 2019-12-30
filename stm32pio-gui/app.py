#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import sys
import time

from PyQt5.QtCore import QCoreApplication, QUrl, QAbstractItemModel, pyqtProperty, QAbstractListModel, QModelIndex, \
    QObject, QVariant, Qt, pyqtSlot, pyqtSignal, QTimer
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQml import qmlRegisterType, QQmlEngine, QQmlComponent, QQmlApplicationEngine
from PyQt5.QtQuick import QQuickView

import stm32pio.lib
import stm32pio.settings


class ProjectListItem(QObject):
    nameChanged = pyqtSignal()

    def __init__(self, project: stm32pio.lib.Stm32pio, parent=None):
        super().__init__(parent)
        self.project = project
        self._name = 'abc'

    @pyqtProperty(str, notify=nameChanged)
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if self._name == value:
            return
        self._name = value
        self.nameChanged.emit()

    @pyqtProperty(str)
    def state(self):
        return str(self.project.state)


class ProjectsList(QAbstractListModel):
    def __init__(self, projects: list, parent=None):
        super().__init__(parent)
        self.projects = projects

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

    @pyqtSlot(int, str)
    def run(self, index, action):
        print('index:', index, action)
        time.sleep(10)
        getattr(self.projects[index].project, action)()



if __name__ == '__main__':
    logger = logging.getLogger('stm32pio')  # the root (relatively to the possible outer scope) logger instance
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(levelname)-8s "
                                           f"%(funcName)-{stm32pio.settings.log_function_fieldwidth}s "
                                           "%(message)s"))
    logger.debug("debug logging enabled")

    app = QGuiApplication(sys.argv)

    projects = ProjectsList([])
    projects.addProject(ProjectListItem(stm32pio.lib.Stm32pio('../stm32pio-test-project', save_on_destruction=False)))
    projects.addProject(ProjectListItem(stm32pio.lib.Stm32pio('../stm32pio-test-project', save_on_destruction=False)))
    projects.addProject(ProjectListItem(stm32pio.lib.Stm32pio('../stm32pio-test-project', save_on_destruction=False)))

    # qmlRegisterType(ProjectListItem, 'ProjectListItem', 1, 0, 'ProjectListItem')

    def update_value():
        projects.projects[1].name = 'def'
    timer = QTimer()
    timer.timeout.connect(update_value)
    timer.start(2000)

    view = QQuickView()
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.rootContext().setContextProperty('projectsModel', projects)
    view.setSource(QUrl('main.qml'))

    sys.exit(app.exec_())
