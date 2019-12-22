#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QListWidget, QListWidgetItem, \
    QStackedWidget, QLabel


class CentralWidget(QWidget):
    def __init__(self, parent=None):
        super(CentralWidget, self).__init__(parent)
        grid = QGridLayout()
        self.setLayout(grid)

        self.projects_list_widget = QListWidget()
        # first = QListWidgetItem('First', self.projects_list_widget)
        self.projects_list_widget.addItem('First')
        self.projects_list_widget.addItem('Second')
        self.projects_list_widget.addItem('Third')

        self.project_window = QStackedWidget()
        self.project_window.addWidget(QLabel('Hello, World!'))

        grid.addWidget(self.projects_list_widget, 0, 0)
        grid.addWidget(self.project_window, 0, 1)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.setWindowTitle(QCoreApplication.applicationName())
        self.central_widget = CentralWidget()
        self.setCentralWidget(self.central_widget)


if __name__ == '__main__':
    QCoreApplication.setOrganizationName('ussserrr')
    QCoreApplication.setApplicationName('stm32pio')

    app = QApplication(sys.argv)

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec_())
