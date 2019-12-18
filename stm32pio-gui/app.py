#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# (c) EVILEG https://evileg.com/ru/post/242/

from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQml import QQmlApplicationEngine
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot


class Calculator(QObject):
    def __init__(self):
        QObject.__init__(self)

    # cигнал передающий сумму
    # обязательно даём название аргументу через arguments=['sum']
    # иначе нельзя будет его забрать в QML
    sumResult = pyqtSignal(int, arguments=['sum'])

    subResult = pyqtSignal(int, arguments=['sub'])

    # слот для суммирования двух чисел
    @pyqtSlot(int, int)
    def sum(self, arg1, arg2):
        # складываем два аргумента и испускаем сигнал
        self.sumResult.emit(arg1 + arg2)

    # слот для вычитания двух чисел
    @pyqtSlot(int, int)
    def sub(self, arg1, arg2):
        # вычитаем аргументы и испускаем сигнал
        self.subResult.emit(arg1 - arg2)


if __name__ == "__main__":
    import sys

    sys.argv += ['--style', 'material']

    # создаём экземпляр приложения
    app = QGuiApplication(sys.argv)
    # создаём QML движок
    engine = QQmlApplicationEngine()
    # создаём объект калькулятора
    calculator = Calculator()
    # и регистрируем его в контексте QML
    engine.rootContext().setContextProperty("calculator", calculator)
    # загружаем файл qml в движок
    engine.load("main.qml")

    engine.quit.connect(app.quit)
    sys.exit(app.exec_())
