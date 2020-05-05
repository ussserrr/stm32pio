#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__version__ = '1.30'

import argparse
import inspect
import logging
import pathlib
import sys
from typing import Optional, List

try:
    import stm32pio.settings
    import stm32pio.lib
    import stm32pio.util
except ModuleNotFoundError:
    sys.path.append(str(pathlib.Path(sys.path[0]).parent))  # hack to be able to run the app as 'python app.py'
    import stm32pio.settings
    import stm32pio.lib
    import stm32pio.util


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
        Java, PlatformIO CLI. Visit https://github.com/ussserrr/stm32pio for more information. Use 'help' command to
        take a glimpse on the available functionality'''))

    # Global arguments (there is also an automatically added '-h, --help' option)
    root_parser.add_argument('--version', action='version', version=f"stm32pio v{__version__}")
    root_parser.add_argument('-v', '--verbose', help="enable verbose output (default: INFO)", action='count', default=0)

    subparsers = root_parser.add_subparsers(dest='subcommand', title='subcommands', description="valid subcommands",
                                            help="available actions")

    parser_init = subparsers.add_parser('init',
                                        help="create config .ini file to check and tweak parameters before proceeding")
    parser_new = subparsers.add_parser('new',
                                       help="generate CubeMX code, create PlatformIO project, glue them together")
    parser_gui = subparsers.add_parser('gui', help="start the graphical version of the application. All arguments will "
                                                   "be passed forward, see its --help for more information")
    parser_generate = subparsers.add_parser('generate', help="generate CubeMX code only")
    parser_status = subparsers.add_parser('status', help="get the description of the current project state")
    parser_clean = subparsers.add_parser('clean',
                                         help="clean-up the project (delete ALL content of 'path' except an .ioc file)")

    # Common subparsers options
    for parser in [parser_init, parser_new, parser_gui, parser_generate, parser_status, parser_clean]:
        parser.add_argument('-d', '--directory', dest='path', default=pathlib.Path.cwd(),
                            help="path to the project (current directory, if not given)")
    for parser in [parser_init, parser_new, parser_gui]:
        parser.add_argument('-b', '--board', dest='board', default='', help="PlatformIO name of the board")
    for parser in [parser_init, parser_new, parser_generate]:
        parser.add_argument('--start-editor', dest='editor',
                            help="use specified editor to open the PlatformIO project (e.g. subl, code, atom, etc.)")
    for parser in [parser_new, parser_generate]:
        parser.add_argument('--with-build', action='store_true', help="build the project after generation")

    parser_clean.add_argument('-q', '--quiet', action='store_true',
                              help="suppress the caution about the content removal (be sure of what you are doing!)")

    if len(args) == 0:
        root_parser.print_help()
        return None

    return root_parser.parse_args(args)


def setup_logging(args_verbose_counter: int = 0, dummy: bool = False) -> logging.Logger:
    """
    Configure some root logger. The corresponding adapters for every project will be dependent on this.

    Args:
        args_verbose_counter: verbosity level (currently only 2 levels are supported: NORMAL, VERBOSE)
        dummy: create a NullHandler logger if true

    Returns:
        logging.Logger instance
    """
    if dummy:
        logger = logging.getLogger(__name__)
        logger.addHandler(logging.NullHandler())
    else:
        logger = logging.getLogger('stm32pio')
        logger.setLevel(logging.DEBUG if args_verbose_counter else logging.INFO)
        handler = logging.StreamHandler()
        formatter = stm32pio.util.DispatchingFormatter(
            verbosity=stm32pio.util.Verbosity.VERBOSE if args_verbose_counter else stm32pio.util.Verbosity.NORMAL,
            general={
                stm32pio.util.Verbosity.NORMAL: logging.Formatter("%(levelname)-8s %(message)s"),
                stm32pio.util.Verbosity.VERBOSE: logging.Formatter(
                    f"%(levelname)-8s %(funcName)-{stm32pio.settings.log_fieldwidth_function}s %(message)s")
            })
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.debug("debug logging enabled")
    return logger


def main(sys_argv: List[str] = None, should_setup_logging: bool = True) -> int:
    """
    Can be used as a high-level wrapper to do complete tasks.

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
        import stm32pio_gui.app
        gui_args = [arg for arg in sys_argv if arg != 'gui']
        return stm32pio_gui.app.main(sys_argv=gui_args)
    elif args is not None and args.subcommand is not None:
        logger = setup_logging(args_verbose_counter=args.verbose, dummy=not should_setup_logging)
    else:
        print("\nNo arguments were given, exiting...")
        return 0

    # Main routine
    try:
        if args.subcommand == 'init':
            project = stm32pio.lib.Stm32pio(args.path, parameters={'project': {'board': args.board}},
                                            instance_options={'save_on_destruction': True})
            if not args.board:
                logger.warning("PlatformIO board identifier is not specified, it will be needed on PlatformIO project "
                               "creation. Type 'pio boards' or go to https://platformio.org to find an appropriate "
                               "identifier")
            logger.info("project has been initialized. You can now edit stm32pio.ini config file")
            if args.editor:
                project.start_editor(args.editor)

        elif args.subcommand == 'new':
            project = stm32pio.lib.Stm32pio(args.path, parameters={'project': {'board': args.board}},
                                            instance_options={'save_on_destruction': True})
            if project.config.get('project', 'board') == '':
                raise Exception("PlatformIO board identifier is not specified, it is needed for PlatformIO project "
                                "creation. Type 'pio boards' or go to https://platformio.org to find an appropriate "
                                "identifier")
            project.generate_code()
            project.pio_init()
            project.patch()
            if args.with_build:
                project.build()
            if args.editor:
                project.start_editor(args.editor)

        elif args.subcommand == 'generate':
            project = stm32pio.lib.Stm32pio(args.path)
            project.generate_code()
            if args.with_build:
                project.build()
            if args.editor:
                project.start_editor(args.editor)

        elif args.subcommand == 'status':
            project = stm32pio.lib.Stm32pio(args.path)
            print(project.state)

        elif args.subcommand == 'clean':
            project = stm32pio.lib.Stm32pio(args.path)
            if args.quiet:
                project.clean()
            else:
                while True:
                    reply = input(f'WARNING: this operation will delete ALL content of the directory "{project.path}" '
                                  f'except the "{pathlib.Path(project.config.get("project", "ioc_file")).name}" file. '
                                  'Are you sure? (y/n) ')
                    if reply.lower() in ['y', 'yes', 'true', '1']:
                        project.clean()
                        break
                    elif reply.lower() in ['n', 'no', 'false', '0']:
                        break

    # Library is designed to throw the exception in bad cases so we catch here globally
    except Exception:
        stm32pio.util.log_current_exception(logger)
        return -1

    return 0


if __name__ == '__main__':
    sys.exit(main())
