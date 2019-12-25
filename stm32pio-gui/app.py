#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

from PyQt5.QtCore import QCoreApplication, QUrl, QAbstractItemModel, pyqtProperty, QAbstractListModel, QModelIndex, \
    QObject, QVariant, Qt
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQml import qmlRegisterType, QQmlEngine, QQmlComponent, QQmlApplicationEngine
from PyQt5.QtQuick import QQuickView

import stm32pio.lib


class ProjectListItem(QObject):
    def __init__(self, project: stm32pio.lib.Stm32pio, parent=None):
        super().__init__(parent)
        self.project = project

    @pyqtProperty('QString')
    def name(self):
        return self.project.path.name

    @pyqtProperty('QString')
    def state(self):
        return str(self.project.state)


class ProjectsList(QAbstractListModel):
    def __init__(self, projects: list, parent=None):
        super().__init__(parent)
        self.projects = projects

    def rowCount(self, parent=None, *args, **kwargs):
        return len(self.projects)

    def data(self, index: QModelIndex, role=None):
        # print(index, role)
        if index.row() < 0 or index.row() >= len(self.projects):
            return QVariant()
        else:
            if role == Qt.DisplayRole:
                return self.projects[index.row()]
            else:
                return QVariant()

    def addProject(self, project):
        self.beginInsertRows(QModelIndex(), self.rowCount(), self.rowCount())
        self.projects.append(project)
        self.endInsertRows()



if __name__ == '__main__':
    app = QGuiApplication(sys.argv)

    projects = ProjectsList([])
    projects.addProject(ProjectListItem(stm32pio.lib.Stm32pio('../stm32pio-test-project', save_on_destruction=False)))
    projects.addProject(ProjectListItem(stm32pio.lib.Stm32pio('../stm32pio-test-project', save_on_destruction=False)))
    projects.addProject(ProjectListItem(stm32pio.lib.Stm32pio('../stm32pio-test-project', save_on_destruction=False)))

    view = QQuickView()
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.rootContext().setContextProperty('projectsModel', projects)
    view.setSource(QUrl('main.qml'))
    # view.show()

    sys.exit(app.exec_())
