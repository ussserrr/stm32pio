#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import inspect
import logging
import pathlib
import platform
import sys
from typing import Optional, List

import stm32pio.core.pio

try:
    from PySide2.QtCore import Signal, QtInfoMsg, QtWarningMsg, QtCriticalMsg, QtFatalMsg, qInstallMessageHandler, \
        QStringListModel, QUrl, QThreadPool, QSettings, QByteArray
    # PySide environment is slightly different among OSes
    if platform.system() == 'Linux':
        from PySide2.QtWidgets import QApplication
        QApplicationClass = QApplication
    else:
        from PySide2.QtGui import QGuiApplication
        QApplicationClass = QGuiApplication
    from PySide2.QtGui import QIcon
    from PySide2.QtQml import QQmlApplicationEngine, qmlRegisterType
except ImportError as e:
    print(e)
    print("\nGUI version requires PySide2 to be installed. You can re-install stm32pio as 'pip install stm32pio[GUI]' "
          "or manually install its dependencies by yourself")
    sys.exit(-1)

MODULE_PATH = pathlib.Path(__file__).parent  # module path, e.g. root/stm32pio/gui/
ROOT_PATH = MODULE_PATH.parent.parent  # repo's or the site-package's entry root
try:
    import stm32pio.core.settings
    import stm32pio.core.log
    import stm32pio.core.util
    import stm32pio.core.state
except ModuleNotFoundError:
    sys.path.append(str(ROOT_PATH))  # hack to resolve imports if the app was launched as 'python path/to/app.py'
    import stm32pio.core.settings
    import stm32pio.core.log
    import stm32pio.core.util
    import stm32pio.core.state

from stm32pio.gui.settings import init_settings, Settings
from stm32pio.gui.util import Worker
from stm32pio.gui.log import setup_logging, module_logger
from stm32pio.gui.list import ProjectsList
from stm32pio.gui.project import ProjectListItem


def parse_args(args: list) -> Optional[argparse.Namespace]:
    parser = argparse.ArgumentParser(description=inspect.cleandoc('''stm32pio GUI version.
        Visit https://github.com/ussserrr/stm32pio for more information.'''))

    # Global arguments (there is also an automatically added '-h, --help' option)
    parser.add_argument('--version', action='version', version=f"stm32pio v{stm32pio.core.util.get_version()}")

    parser.add_argument('-d', '--directory', dest='path', default=str(pathlib.Path.cwd()),
        help="path to the project (current directory, if not given, but any other option should be specified then)")
    parser.add_argument('-b', '--board', dest='board', default='', help="PlatformIO name of the board")

    return parser.parse_args(args) if len(args) else None


def create_app(sys_argv: List[str] = None) -> QApplicationClass:
    if sys_argv is None:
        sys_argv = sys.argv[1:]

    args = parse_args(sys_argv)

    app = QApplicationClass(sys.argv)

    # These are used as an identifier for QSettings, too
    app.setOrganizationName('ussserrr')
    app.setApplicationName('stm32pio')
    app.setWindowIcon(QIcon(str(MODULE_PATH.joinpath('icons/icon.svg'))))

    settings = init_settings(app)

    setup_logging(initial_verbosity=settings.get('verbose'))

    # Restore projects list
    # TODO: Qt pollutes a system leaving its files across several folders, right? We should probably inform a user
    settings.beginGroup('app')
    restored_projects_paths: List[str] = []
    for index in range(settings.beginReadArray('projects')):
        settings.setArrayIndex(index)
        restored_projects_paths.append(settings.value('path'))
    settings.endArray()
    settings.endGroup()

    engine = QQmlApplicationEngine(parent=app)

    qmlRegisterType(ProjectListItem, 'ProjectListItem', 1, 0, 'ProjectListItem')
    qmlRegisterType(Settings, 'Settings', 1, 0, 'Settings')

    projects_model = ProjectsList(parent=engine)
    boards_model = QStringListModel(parent=engine)

    # Convert to QML-compatible format
    project_stages = { stage.name: str(stage) for stage in stm32pio.core.state.ProjectStage }

    # Fake stages: these are not present in the original enum of possible states
    project_stages['LOADING'] = 'Loading...'
    project_stages['INIT_ERROR'] = 'Initialization error'

    root_path = ('/' + str(ROOT_PATH).replace('\\', '/')) if platform.system() == 'Windows' else str(ROOT_PATH)

    # TODO: use setContextProperties() (see in Qt6, not present in Qt5...)
    engine.rootContext().setContextProperty('appVersion', stm32pio.core.util.get_version())
    engine.rootContext().setContextProperty('rootPath', root_path)
    engine.rootContext().setContextProperty('Logging', stm32pio.core.log.logging_levels)
    engine.rootContext().setContextProperty(stm32pio.core.state.ProjectStage.__name__, project_stages)
    engine.rootContext().setContextProperty('projectsModel', projects_model)
    engine.rootContext().setContextProperty('boardsModel', boards_model)
    engine.rootContext().setContextProperty('settings', settings)

    engine.load(QUrl.fromLocalFile(str(MODULE_PATH/'qml'/'App.qml')))

    main_window = engine.rootObjects()[0]  # only child
    app.aboutToQuit.connect(main_window.close)  # Qt.quit() can now be successfully used

    def onClose():
        print('Closing...')
        for project in projects_model.projects:
            project.should_be_destroyed.set()
    main_window.closing.connect(onClose)

    # Getting PlatformIO boards can take a long time when the PlatformIO cache is outdated but it is important to have
    # them before the projects list is restored, so we start a dedicated loading thread. We actually can add other
    # start-up operations here if there will be a need to. Use the same Worker class to spawn the thread at the pool
    # TODO: this uses default platformio command but it might be unavailable.
    #  Also, it unnecessarily slows down the startup
    def loading():
        boards = ['None'] + stm32pio.core.pio.get_boards()
        boards_model.setStringList(boards)

    def loaded(action_name: str, success: bool):
        try:
            # Qt objects cannot be parented from the different thread so we restore the projects list in the main thread
            for path in restored_projects_paths:
                projects_model.addListItem(path, list_item_kwargs={ 'from_startup': True })

            # At the end, append (or jump to) a CLI-provided project, if there is one
            if args is not None and 'path' in args:
                list_item_kwargs = { 'from_startup': True }
                if args.board:  # TODO: test this
                    list_item_kwargs['project_kwargs'] = { 'parameters': { 'project': { 'board': args.board } } }  # pizdec konechno...
                projects_model.addListItem(str(pathlib.Path(args.path)), list_item_kwargs=list_item_kwargs)
                # Append always happens to the end of list and we want to jump to the last added project (CLI one). The
                # resulting length of the list is (len(restored_projects_paths) + 1) so the last index is that minus 1
                projects_model.goToProject.emit((len(restored_projects_paths) + 1) - 1)
                projects_model.saveInSettings()
        except:
            stm32pio.core.log.log_current_exception(logging.getLogger('stm32pio.gui.app'))
            success = False

        main_window.backendLoaded.emit(success)  # inform the GUI
        print('stm32pio GUI started')

    loader = Worker(loading, logger=module_logger, parent=app)
    loader.finished.connect(loaded)
    QThreadPool.globalInstance().start(loader)

    return app


def main():
    print('Starting stm32pio GUI...')
    app = create_app()
    return app.exec_()




if __name__ == '__main__':
    sys.exit(main())
