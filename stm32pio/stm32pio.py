#!/usr/bin/env python3

import argparse
import logging
import sys
import pathlib

import __init__


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Automation of creating and updating STM32CubeMX-PlatformIO projects. "
                                                 "Requirements: Python 3.6+, STM32CubeMX, Java, PlatformIO CLI. Edit "
                                                 "settings.py to set path to the STM32CubeMX (if default doesn't work)")
    # Global arguments (there is also an automatically added '-h, --help' option)
    parser.add_argument('--version', action='version', version=f"%(prog)s v{__init__.__version__}")
    parser.add_argument('-v', '--verbose', help="enable verbose output (default: INFO)", action='count', required=False)

    subparsers = parser.add_subparsers(dest='subcommand', title='subcommands',
                                       description="valid subcommands", help="modes of operation")

    parser_new = subparsers.add_parser('new',
                                       help="generate CubeMX code, create PlatformIO project [and start the editor]")
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

    args = parser.parse_args()


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


    # Show help and exit if no arguments were given
    if not len(sys.argv) > 1:
        parser.print_help()
        sys.exit()

    # Main routine
    else:
        import util

        try:
            if args.subcommand == 'new' or args.subcommand == 'generate':
                util.generate_code(args.project_path)
                if args.subcommand == 'new':
                    util.pio_init(args.project_path, args.board)
                    util.patch_platformio_ini(args.project_path)

                if args.editor:
                    util.start_editor(args.project_path, args.editor)
                if args.with_build:
                    util.pio_build(args.project_path)

            elif args.subcommand == 'clean':
                util.clean(args.project_path)

        except Exception as e:
            print(e.__repr__())


    logger.info("exiting...")
