#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__version__ = '0.9'

import argparse
import logging
import sys
import pathlib


def parse_args(args):
    """

    """

    parser = argparse.ArgumentParser(description="Automation of creating and updating STM32CubeMX-PlatformIO projects. "
                                                 "Requirements: Python 3.6+, STM32CubeMX, Java, PlatformIO CLI. Edit "
                                                 "settings.py to set path to the STM32CubeMX (if default doesn't work)")
    # Global arguments (there is also an automatically added '-h, --help' option)
    parser.add_argument('--version', action='version', version=f"%(prog)s v{__version__}")
    parser.add_argument('-v', '--verbose', help="enable verbose output (default: INFO)", action='count', required=False)

    subparsers = parser.add_subparsers(dest='subcommand', title='subcommands',
                                       description="valid subcommands", help="modes of operation")

    parser_new = subparsers.add_parser('new', help="generate CubeMX code, create PlatformIO project")
    parser_generate = subparsers.add_parser('generate', help="generate CubeMX code")
    parser_clean = subparsers.add_parser('clean', help="clean-up the project (WARNING: it deletes ALL content of "
                                                       "'path' except the .ioc file)")

    # Common subparsers options
    for p in [parser_new, parser_generate, parser_clean]:
        p.add_argument('-d', '--directory', dest='project_path', help="path to the project (current directory, if not "
                       "given)", default=pathlib.Path.cwd())
    for p in [parser_new, parser_generate]:
        p.add_argument('--start-editor', dest='editor', help="use specified editor to open PlatformIO project (e.g. "
                       "subl, code, atom)", required=False)
        p.add_argument('--with-build', action='store_true', help="build a project after generation", required=False)

    parser_new.add_argument('-b', '--board', dest='board', help="PlatformIO name of the board", required=True)

    # Show help and exit if no arguments were given
    if len(args) <= 1:
        parser.print_help()
        return None

    return parser.parse_args(args)


def main(sys_argv=sys.argv[1:]):
    """

    """

    args = parse_args(sys_argv)
    if args is None:
        print("\nNo arguments were given, exiting...")
        return -1

    # Logger instance goes through the whole program.
    # Currently only 2 levels of verbosity through the '-v' option are counted (INFO and DEBUG)
    logger = logging.getLogger()
    if args.verbose:
        logging.basicConfig(format="%(levelname)-8s %(funcName)-16s %(message)s")
        logger.setLevel(logging.DEBUG)
        logger.debug("debug logging enabled")
    else:
        logging.basicConfig(format="%(levelname)-8s %(message)s")
        logger.setLevel(logging.INFO)

    # Main routine
    import stm32pio.util

    try:
        project = stm32pio.util.Stm32pio(args.project_path)

        if args.subcommand == 'new' or args.subcommand == 'generate':
            project.generate_code()
            if args.subcommand == 'new':
                project.pio_init(args.board)
                project.patch_platformio_ini()

            if args.with_build:
                project.pio_build()
            if args.editor:
                project.start_editor(args.editor)

        elif args.subcommand == 'clean':
            project.clean()

    except Exception as e:
        if logger.level <= logging.DEBUG:  # verbose
            raise e
        else:
            print(e.__repr__())
        return -1

    logger.info("exiting...")
    return 0


if __name__ == '__main__':
    sys.path.insert(0, str(pathlib.Path(sys.path[0]).parent))  # hack to be able to run the app as 'python3 stm32pio.py'
    sys.exit(main())
