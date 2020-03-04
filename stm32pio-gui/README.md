# stm32pio-gui

The cross-platform GUI version of the application. It wraps the core library functionality in the Qt-QML skin using PySide2 (aka "Qt for Python" project) adding projects management feature so you can store and manipulate multiple stm32pio projects in one place.

Currently, it is in a beta stage though all implemented features work, with more or less (mostly visual and architectural) flaws.


## Installation

The app requires PySide2 5.12+ package. It is available in all major package managers including pip, apt, brew and so on. More convenient installation process is coming in next releases.


## Usage

Enter `python3 app.py` to start the app. Projects list (not the projects themself) and settings are stored by QSettings so refer to its docs if you bother about the actual location.
