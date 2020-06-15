# stm32pio GUI

![Main](screenshots/main.png)

The cross-platform GUI version of the stm32pio. It wraps the core library functionality into the Qt5-QML skin using the PySide2 (aka "Qt for Python" project) and adding the projects management feature allowing you to store and manipulate on multiple stm32pio projects at one place.


## Table of contents
> - [Install and run](#install-and-run)
> - [Usage](#usage)
> - [Architecture notes](#architecture-notes)


## Install and run

The app requires PySide2 5.12+ package (Qt 5.12 respectively). It is available in all major package managers including pip, apt, brew and so on.

The convenient way to install is via `pip` specifying `extras` option:
```shell script
$ pip install stm32pio[GUI]
```

Then it can be started as
```shell script
$ stm32pio_gui
```
or
```shell script
$ stm32pio gui
```
from anywhere. If you have already installed the latest basic CLI version, this script and sources are already on your machine so you can reinstall it using the command above or just supplement the setup installing the PySide2 manually.

If you rather want to launch completely from sources, it is possible like this:
```shell script
$ python path/to/stm32pio_gui/app.py
```
or
```shell script
stm32pio-repo/ $   python -m stm32pio_gui
```

Either way, you can additionally specify the project (and board ID) to open with:
```shell script
$ stm32pio_gui -d ./sample-project -b discovery_f4
```


## Usage

Add a folder with the `.ioc` file to begin with. You can either use an "Add" button or drag-and-drop it into the main window, in the latter case you also have an ability to add multiple projects simultaneously. If the project is empty the initialization screen will be shown to help in setup:

![Init](screenshots/init_screen.png)

Skip it or enter one of the available PlatformIO STM32 boards identifier. Select "Run" to apply all actions to the project (analog of the `new` CLI command).

In the main screen the buttons row allows you to run specific actions while, at the same time, represents the state of the project. Green color means that this stage is fulfilled. The active project is monitored automatically while all the others refreshes only when you click on them so the "stage" line at the projects list item can be outdated.

Let's assume you've worked on the project for some time and need to re-generate and rebuild the configuration. To schedule all the necessary actions to run one after another navigate to the last desired action pressing the Shift key. All the actions prior this one should be colored light-green now:

![Highlighting](screenshots/highlighting.png)

Shift-click on it to execute the series. The picked actions will be framed with the border around each of them:

![Group](screenshots/group.png)

Add Ctrl to the mouse click to start the editor specified in the settings after the action. It can be combined with Shift as well. **Hint:** specify a `start` as an "Editor" command to open the folder in the new Explorer window under the Windows, `open` for the Finder on the macOS.

Currently, the project config (stm32pio.ini) is not live-reloaded so any changes you do to it will not be reflected until the next start.


## Architecture notes

Projects list (not the projects themself) and settings are stored by `QSettings` so refer to its docs if you bother about the actual location.

See `docs` directory to see state machine diagram of the project action button.
