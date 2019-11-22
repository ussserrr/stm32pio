#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__version__ = '0.9'

import argparse
import logging
import sys
import pathlib
import traceback
from typing import Optional


def parse_args(args: list) -> Optional[argparse.Namespace]:
    """

    """

    parser = argparse.ArgumentParser(description="Automation of creating and updating STM32CubeMX-PlatformIO projects. "
                                                 "Requirements: Python 3.6+, STM32CubeMX, Java, PlatformIO CLI. Edit "
                                                 "settings.py to set path to the STM32CubeMX (if default doesn't work)")
    # Global arguments (there is also an automatically added '-h, --help' option)
    parser.add_argument('--version', action='version', version=f"stm32pio v{__version__}")
    parser.add_argument('-v', '--verbose', help="enable verbose output (default: INFO)", action='count', required=False)

    subparsers = parser.add_subparsers(dest='subcommand', title='subcommands',
                                       description="valid subcommands", help="modes of operation")

    parser_new = subparsers.add_parser('new', help="generate CubeMX code, create PlatformIO project")
    parser_generate = subparsers.add_parser('generate', help="generate CubeMX code")
    parser_clean = subparsers.add_parser('clean', help="clean-up the project (WARNING: it deletes ALL content of "
                                                       "'path' except the .ioc file)")
    parser_init = subparsers.add_parser('init', help="create config .ini file so you can tweak parameters before "
                                                     "proceeding")

    # Common subparsers options
    for p in [parser_new, parser_generate, parser_clean, parser_init]:
        p.add_argument('-d', '--directory', dest='project_path', default=pathlib.Path.cwd(),
                       help="path to the project (current directory, if not given)")
    for p in [parser_new, parser_init]:
        p.add_argument('-b', '--board', dest='board', help="PlatformIO name of the board", required=False)
    for p in [parser_new, parser_generate]:
        p.add_argument('--start-editor', dest='editor', help="use specified editor to open PlatformIO project (e.g. "
                       "subl, code, atom, etc.)", required=False)
        p.add_argument('--with-build', action='store_true', help="build a project after generation", required=False)

    # Show help and exit if no arguments were given
    if len(args) == 0:
        parser.print_help()
        return None

    return parser.parse_args(args)


def main(sys_argv: list = sys.argv[1:]) -> int:
    """

    """

    args = parse_args(sys_argv)
    if args is None or args.subcommand is None:
        print("\nNo arguments were given, exiting...")
        return 0

    # Logger instance goes through the whole program.
    # Currently only 2 levels of verbosity through the '-v' option are counted (INFO and DEBUG)
    logger = logging.getLogger('stm32pio')
    if args.verbose:
        logging.basicConfig(format="%(levelname)-8s %(funcName)-26s %(message)s", level=logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("debug logging enabled")
    else:
        logging.basicConfig(format="%(levelname)-8s %(message)s", level=logging.INFO)
        logger.setLevel(logging.INFO)

    # Main routine
    import stm32pio.lib  # import the module after sys.path modification

    try:
        project = stm32pio.lib.Stm32pio(args.project_path)

        if args.subcommand == 'init' or args.subcommand == 'new' or args.subcommand == 'generate':
            project.init(board=args.board if 'board' in args else None)
            if (args.subcommand == 'init' or args.subcommand == 'new') and project.config.get('project', 'board') == '':
                logger.warning("STM32 board is not specified, it will be needed on PlatformIO project creation")
            if args.subcommand == 'init':
                logger.info('stm32pio project has been initialized. You can now edit parameters in stm32pio.ini file')
                project.save_config()

        if args.subcommand == 'new' or args.subcommand == 'generate':
            project.generate_code()
            if args.subcommand == 'new':
                project.pio_init()
                project.patch()
                project.save_config()

            if args.with_build:
                project.pio_build()
            if args.editor:
                project.start_editor(args.editor)

        if args.subcommand == 'clean':
            project.clean()

    # library is designed to throw the exception in bad cases so we catch here globally
    except Exception as e:
        logger.error(repr(e))
        if logger.level <= logging.DEBUG:  # verbose
            traceback.print_exception(*sys.exc_info())
        return -1

    logger.info("exiting...")
    return 0


if __name__ == '__main__':
    sys.path.insert(0, str(pathlib.Path(sys.path[0]).parent))  # hack to be able to run the app as 'python3 app.py'
    sys.exit(main())
