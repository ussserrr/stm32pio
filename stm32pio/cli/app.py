#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import inspect
import logging
import sys
from pathlib import Path
from typing import Optional, List

MODULE_PATH = Path(__file__).parent  # module path, e.g. root/stm32pio/cli/

# Package root, e.g. root/ (so if ran from sources, this is a repository folder;
# if the package is installed, it is a site-package entry
ROOT_PATH = MODULE_PATH.parent.parent

try:
    import stm32pio.core.log
except ModuleNotFoundError:
    sys.path.append(str(ROOT_PATH))  # hack to be able to run the app as 'python path/to/app.py'
finally:
    import stm32pio.core.log
    import stm32pio.core.project
    import stm32pio.core.settings
    import stm32pio.core.util


board_hint = "Type 'pio boards' or go to https://platformio.org to find an appropriate identifier"
no_board_message = f"PlatformIO board is not specified, it will be needed on PlatformIO project creation. {board_hint}"
init_message = f"project has been initialized. You can now edit {stm32pio.core.settings.config_file_name} config file"


def parse_args(args: List[str]) -> Optional[argparse.Namespace]:
    """
    Parse command line arguments.

    :param args: list of CLI arguments
    :return: argparse.Namespace or None if no arguments were given
    """

    root = argparse.ArgumentParser(description=inspect.cleandoc('''
        Small cross-platform Python app that can create and update PlatformIO projects from STM32CubeMX .ioc files. It
        uses STM32CubeMX to generate a HAL-framework-based code and alongside creates PlatformIO project with compatible
        parameters to stick them both together. Both CLI and GUI editions are available. Visit
        https://github.com/ussserrr/stm32pio for more information. Use 'stm32pio [command] -h' to see help on the
        particular command'''))

    # Global arguments (there is also an automatically added '-h, --help' option)
    root.add_argument('--version', action='version', version=f"stm32pio {stm32pio.core.util.get_version()}")
    root.add_argument('-v', '--verbose', help="enable verbose output (default level: INFO)", action='count', default=1)

    sub = root.add_subparsers(dest='command', title='commands', description="valid commands", help="available actions")

    # Primary operations
    init = sub.add_parser('init', help="create config .INI file to check and tweak parameters before proceeding")
    generate = sub.add_parser('generate', help="generate CubeMX code only")
    pio_init = sub.add_parser('pio_init', help="create new compatible PlatformIO project")
    patch = sub.add_parser('patch', help="tweak the project so both CubeMX and PlatformIO could work together")
    new = sub.add_parser('new', help="generate CubeMX code, create PlatformIO project and glue them together")
    status = sub.add_parser('status', help="inspect the project current state")
    validate = sub.add_parser('validate', help="verify current environment based on the config values")
    clean = sub.add_parser('clean', help="clean-up the project (by default, no files will be deleted immediately "
                                         "without your confirmation)")
    gui = sub.add_parser('gui', help="start the graphical version of the application. All arguments will "
                                     "be passed forward, see its own --help for more information")

    # Assign options to commands
    for command in [init, generate, pio_init, patch, new, status, validate, clean, gui]:
        command.add_argument('-d', '--directory', dest='path', default=Path.cwd(),
                             help="path to the project (current directory, if not given)")
    for command in [init, pio_init, new, gui]:
        command.add_argument('-b', '--board', dest='board', default='', help="PlatformIO board name. " + board_hint)
    for command in [init, generate, new]:
        command.add_argument('-e', '--start-editor', dest='editor',
                             help="start the specified editor after an action (e.g. subl, code, atom, etc.)")
    for command in [generate, new]:
        command.add_argument('-c', '--with-build', action='store_true', help="build the project after code generation")
    for command in [init, new]:
        command.add_argument('-s', '--store-content', action='store_true',
                             help="save folder initial contents as a cleanup ignore list")
    clean.add_argument('-s', '--store-content', action='store_true',
                       help="save project folder contents as a cleanup ignore list and exit")
    clean.add_argument('-q', '--quiet', action='store_true',
                       help="suppress the caution about the content removal (be sure of what you are doing!)")

    if len(args) == 0:
        root.print_help()
        return None

    return root.parse_args(args)


def setup_logging(verbose: int = 1, dummy: bool = False) -> logging.Logger:
    """
    Prepare a logging setup suitable for a CLI application. Keep in mind, though, that Python ``logging`` module, in
    general, mutates some internal global state, so be careful not to invoke this procedure twice in a single "session"
    to avoid any unwanted interfering and possible slowdowns.
    
    :param verbose: verbosity counter (currently only 2 levels are supported: NORMAL, VERBOSE (starts from 1))
    :param dummy: if True, the function will create a "/dev/null" logger instead (no operation)
    :return: configured and ready-to-use root logger instance. Corresponding logging adapters for every project will be
    dependent on this
    """
    if dummy:
        logger = logging.getLogger(__name__)
        logger.addHandler(logging.NullHandler())
    else:
        logger = logging.getLogger('stm32pio')
        logger.setLevel(logging.DEBUG if verbose == 2 else logging.INFO)
        handler = logging.StreamHandler()
        formatter = stm32pio.core.log.DispatchingFormatter(verbosity=stm32pio.core.log.Verbosity(verbose))
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.debug("debug logging enabled")  # will be printed only in verbose mode
    return logger


def main(sys_argv: List[str] = None, should_setup_logging: bool = True) -> int:
    """
    Entry point to the CLI edition of application. Since this is a highest-order wrapper, it can be used to
    programmatically the application (for testing, embedding, etc.). Example:

        ret_code = stm32pio.app.main(sys_argv=['new', '-d', '~/path/to/project', '-b', 'nucleo_f031k6', '--with-build'])

    :param sys_argv: list of CLI arguments
    :param should_setup_logging: if True, a reasonable default logging schema would be applied, otherwise it is on
    caller to resolve (or not) some logging configuration. The latter can be useful when an outer code makes sequential
    calls to this API so it is unwanted to append logging handlers every time (e.g. when unit-testing)
    :return: 0 on success, -1 otherwise
    """

    if sys_argv is None:
        sys_argv = sys.argv[1:]

    args = parse_args(sys_argv)

    if args is not None and args.command == 'gui':
        gui_args = [arg for arg in sys_argv if arg != 'gui']
        import stm32pio.gui.app as gui
        app = gui.create_app(sys_argv=gui_args)
        return app.exec_()
    elif args is not None and args.command is not None:
        logger = setup_logging(verbose=args.verbose, dummy=not should_setup_logging)
    else:
        print("\nNo arguments were given, exiting...")
        return 0

    project = None

    # Wrap the main routine into try...except to gently handle possible error (API is designed to throw in certain
    # situations when it doesn't make much sense to continue with the met conditions)
    try:
        if args.command == 'init':
            project = stm32pio.core.project.Stm32pio(args.path, parameters={'project': {'board': args.board}},
                                                     save_on_destruction=True)
            if args.store_content:
                project.config.set_content_as_ignore_list()
            if project.config.get('project', 'board') == '':
                logger.warning(no_board_message)
            project.inspect_ioc_config()
            logger.info(init_message)
            if args.editor:
                project.start_editor(args.editor)

        elif args.command == 'generate':
            project = stm32pio.core.project.Stm32pio(args.path)
            if project.config.get('project', 'inspect_ioc', fallback='0').lower() in stm32pio.core.settings.yes_options:
                project.inspect_ioc_config()
            project.generate_code()
            if args.with_build:
                project.build()
            if args.editor:
                project.start_editor(args.editor)

        elif args.command == 'pio_init':
            project = stm32pio.core.project.Stm32pio(args.path, parameters={'project': {'board': args.board}},
                                                     save_on_destruction=True)
            if project.config.get('project', 'inspect_ioc', fallback='0').lower() in stm32pio.core.settings.yes_options:
                project.inspect_ioc_config()
            project.pio_init()

        elif args.command == 'patch':
            project = stm32pio.core.project.Stm32pio(args.path)
            if project.config.get('project', 'inspect_ioc', fallback='0').lower() in stm32pio.core.settings.yes_options:
                project.inspect_ioc_config()
            project.patch()

        elif args.command == 'new':
            project = stm32pio.core.project.Stm32pio(args.path, parameters={'project': {'board': args.board}},
                                                     save_on_destruction=True)
            if args.store_content:
                project.config.set_content_as_ignore_list()
            if project.config.get('project', 'board') == '':
                logger.info(init_message)
                raise Exception(no_board_message)
            if project.config.get('project', 'inspect_ioc', fallback='0').lower() in stm32pio.core.settings.yes_options:
                project.inspect_ioc_config()
            project.generate_code()
            project.pio_init()
            project.patch()
            if args.with_build:
                project.build()
            if args.editor:
                project.start_editor(args.editor)

        elif args.command == 'status':
            project = stm32pio.core.project.Stm32pio(args.path)
            print(project.state)

        elif args.command == 'validate':
            project = stm32pio.core.project.Stm32pio(args.path)
            print(project.validate_environment())

        elif args.command == 'clean':
            project = stm32pio.core.project.Stm32pio(args.path)
            if args.store_content:
                project.config.set_content_as_ignore_list()
                project.config.save()
            else:
                project.clean(quiet=args.quiet)

    except (Exception,):
        stm32pio.core.log.log_current_exception(logger, config=project.config if project is not None else None)
        return -1

    return 0


if __name__ == '__main__':
    sys.exit(main())
