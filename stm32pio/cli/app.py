#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import inspect
import logging
import pathlib
import sys
from typing import Optional, List

MODULE_PATH = pathlib.Path(__file__).parent  # module path, e.g. root/stm32pio/cli/
ROOT_PATH = MODULE_PATH.parent.parent  # repo's or the site-package's entry root
try:
    import stm32pio.core.settings
    import stm32pio.core.log
    import stm32pio.core.project
    import stm32pio.core.util
except ModuleNotFoundError:
    sys.path.append(str(ROOT_PATH))  # hack to be able to run the app as 'python path/to/app.py'
    import stm32pio.core.settings
    import stm32pio.core.log
    import stm32pio.core.project
    import stm32pio.core.util


def parse_args(args: List[str]) -> Optional[argparse.Namespace]:
    """
    Dedicated function to parse the arguments given via CLI.

    Args:
        args: list of strings CLI arguments

    Returns:
        argparse.Namespace or None if no arguments were given
    """

    root_parser = argparse.ArgumentParser(description=inspect.cleandoc('''
        Automation of creating and updating STM32CubeMX-PlatformIO projects. Requirements: Python 3.6+, STM32CubeMX,
        Java, PlatformIO CLI. Visit https://github.com/ussserrr/stm32pio for more information. Use 'stm32pio [command]
        -h' to see help on the particular command'''))

    # Global arguments (there is also an automatically added '-h, --help' option)
    root_parser.add_argument('--version', action='version', version=f"stm32pio {stm32pio.core.util.get_version()}")
    root_parser.add_argument('-v', '--verbose', help="enable verbose output (default: INFO)", action='count', default=0)

    subparsers = root_parser.add_subparsers(dest='subcommand', title='subcommands', description="valid subcommands",
                                            help="available actions")

    parser_init = subparsers.add_parser('init',
                                        help="create config .ini file to check and tweak parameters before proceeding")
    parser_generate = subparsers.add_parser('generate', help="generate CubeMX code only")
    parser_pio_init = subparsers.add_parser('pio_init', help="create new compatible PlatformIO project")
    parser_patch = subparsers.add_parser('patch',
                                         help="tweak the project so the CubeMX and PlatformIO could work together")
    parser_new = subparsers.add_parser('new',
                                       help="generate CubeMX code, create PlatformIO project, glue them together")
    parser_status = subparsers.add_parser('status', help="get the description of the current project state")
    parser_clean = subparsers.add_parser('clean', help="clean-up the project (by default, it will ask you about the "
                                                       "files to delete)")
    parser_validate = subparsers.add_parser('validate', help="verify current environment based on the config values")
    parser_gui = subparsers.add_parser('gui', help="start the graphical version of the application. All arguments will "
                                                   "be passed forward, see its own --help for more information")

    # Common subparsers options
    for parser in [parser_init, parser_generate, parser_pio_init, parser_patch, parser_new, parser_status,
                   parser_validate, parser_clean, parser_gui]:
        parser.add_argument('-d', '--directory', dest='path', default=pathlib.Path.cwd(),
                            help="path to the project (current directory, if not given)")
    for parser in [parser_init, parser_pio_init, parser_new, parser_gui]:
        parser.add_argument('-b', '--board', dest='board', default='', help="PlatformIO identifier of the board")
    for parser in [parser_init, parser_generate, parser_new]:
        parser.add_argument('-e', '--start-editor', dest='editor',
                            help="use specified editor to open the PlatformIO project (e.g. subl, code, atom, etc.)")
    for parser in [parser_generate, parser_new]:
        parser.add_argument('-c', '--with-build', action='store_true', help="build the project after generation")
    for parser in [parser_init, parser_clean, parser_new]:
        parser.add_argument('-s', '--store-content', action='store_true',
                            help="save current folder contents as a cleanup ignore list and exit")
    parser_clean.add_argument('-q', '--quiet', action='store_true',
                              help="suppress the caution about the content removal (be sure of what you are doing!)")

    if len(args) == 0:
        root_parser.print_help()
        return None

    return root_parser.parse_args(args)


def setup_logging(verbose: int = 0, dummy: bool = False) -> logging.Logger:
    """
    Configure and return some root logger. The corresponding adapters for every project will be dependent on this.

    Args:
        verbose: verbosity counter (currently only 2 levels are supported: NORMAL, VERBOSE)
        dummy: create a NullHandler logger if true

    Returns:
        logging.Logger instance
    """
    if dummy:
        logger = logging.getLogger(__name__)
        logger.addHandler(logging.NullHandler())
    else:
        logger = logging.getLogger('stm32pio')
        logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        handler = logging.StreamHandler()
        formatter = stm32pio.core.log.DispatchingFormatter(
            verbosity=stm32pio.core.log.Verbosity.VERBOSE if verbose else stm32pio.core.log.Verbosity.NORMAL,
            general={
                stm32pio.core.log.Verbosity.NORMAL: logging.Formatter("%(levelname)-8s %(message)s"),
                stm32pio.core.log.Verbosity.VERBOSE: logging.Formatter(
                    f"%(levelname)-8s %(funcName)-{stm32pio.core.settings.log_fieldwidth_function}s %(message)s")
            })
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.debug("debug logging enabled")
    return logger


def main(sys_argv: List[str] = None, should_setup_logging: bool = True) -> int:
    """
    Can be used as a high-level wrapper to perform independent tasks.

    Example:
        ret_code = stm32pio.app.main(sys_argv=['new', '-d', '~/path/to/project', '-b', 'nucleo_f031k6', '--with-build'])

    Args:
        sys_argv: list of strings CLI arguments
        should_setup_logging: if this is true, the preferable default logging schema would be applied, otherwise it is a
            caller responsibility to provide (or do not) some logging configuration. The latter can be useful when the
            outer code makes sequential calls to this API so it is unwanted to append the logging handlers every time
            (e.g. when unit-testing)

    Returns:
        0 on success, -1 otherwise
    """

    if sys_argv is None:
        sys_argv = sys.argv[1:]

    args = parse_args(sys_argv)

    if args is not None and args.subcommand == 'gui':
        gui_args = [arg for arg in sys_argv if arg != 'gui']
        import stm32pio.gui.app as gui
        app = gui.create_app(sys_argv=gui_args)
        return app.exec_()
    elif args is not None and args.subcommand is not None:
        logger = setup_logging(verbose=args.verbose, dummy=not should_setup_logging)
    else:
        print("\nNo arguments were given, exiting...")
        return 0

    project = None

    # Main routine
    try:
        if args.subcommand == 'init':
            project = stm32pio.core.project.Stm32pio(args.path, parameters={'project': {'board': args.board}},
                                                     instance_options={'save_on_destruction': True})
            if args.store_content:
                project.config.save_content_as_ignore_list()
            if project.config.get('project', 'board') == '':
                logger.warning("PlatformIO board identifier is not specified, it will be needed on PlatformIO project "
                               "creation. Type 'pio boards' or go to https://platformio.org to find an appropriate "
                               "identifier")
            project.inspect_ioc_config()
            logger.info(f"project has been initialized. You can now edit {stm32pio.core.settings.config_file_name} "
                        "config file")
            if args.editor:
                project.start_editor(args.editor)

        elif args.subcommand == 'generate':
            project = stm32pio.core.project.Stm32pio(args.path)
            if project.config.get('project', 'inspect_ioc', fallback='0').lower() in stm32pio.core.settings.yes_options:
                project.inspect_ioc_config()
            project.generate_code()
            if args.with_build:
                project.build()
            if args.editor:
                project.start_editor(args.editor)

        elif args.subcommand == 'pio_init':
            project = stm32pio.core.project.Stm32pio(args.path, parameters={'project': {'board': args.board}},
                                                     instance_options={'save_on_destruction': True})
            if project.config.get('project', 'inspect_ioc', fallback='0').lower() in stm32pio.core.settings.yes_options:
                project.inspect_ioc_config()
            project.pio_init()

        elif args.subcommand == 'patch':
            project = stm32pio.core.project.Stm32pio(args.path)
            if project.config.get('project', 'inspect_ioc', fallback='0').lower() in stm32pio.core.settings.yes_options:
                project.inspect_ioc_config()
            project.patch()

        elif args.subcommand == 'new':
            project = stm32pio.core.project.Stm32pio(args.path, parameters={'project': {'board': args.board}},
                                                     instance_options={'save_on_destruction': True})
            if args.store_content:
                project.config.save_content_as_ignore_list()
            if project.config.get('project', 'board') == '':
                logger.info(f"project has been initialized. You can now edit {stm32pio.core.settings.config_file_name} "
                            "config file")
                raise Exception("PlatformIO board identifier is not specified, it is needed for PlatformIO project "
                                "creation. Type 'pio boards' or go to https://platformio.org to find an appropriate "
                                "identifier")
            if project.config.get('project', 'inspect_ioc', fallback='0').lower() in stm32pio.core.settings.yes_options:
                project.inspect_ioc_config()
            project.generate_code()
            project.pio_init()
            project.patch()
            if args.with_build:
                project.build()
            if args.editor:
                project.start_editor(args.editor)

        elif args.subcommand == 'status':
            project = stm32pio.core.project.Stm32pio(args.path)
            print(project.state)

        elif args.subcommand == 'validate':
            project = stm32pio.core.project.Stm32pio(args.path)
            print(project.validate_environment())

        elif args.subcommand == 'clean':
            project = stm32pio.core.project.Stm32pio(args.path)
            if args.store_content:
                project.config.save_content_as_ignore_list()
            else:
                project.clean(quiet_on_cli=args.quiet)

    # Global errors catching. Core library is designed to throw the exception in cases when there is no sense to
    # proceed. Of course this also suppose to handle any unexpected behavior, too
    except:
        stm32pio.core.log.log_current_exception(
            logger, config=project.config if (project is not None and hasattr(project, 'config')) else None)
        return -1

    return 0


if __name__ == '__main__':
    sys.exit(main())
