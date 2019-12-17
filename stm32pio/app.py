#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__version__ = '0.96'

import argparse
import logging
import pathlib
import sys
from typing import Optional


def parse_args(args: list) -> Optional[argparse.Namespace]:
    """
    Dedicated function to parse the arguments given via the CLI

    Args:
        args: list of strings CLI arguments

    Returns:
        argparse.Namespace or None if no arguments were given
    """

    parser = argparse.ArgumentParser(description="Automation of creating and updating STM32CubeMX-PlatformIO projects. "
                                                 "Requirements: Python 3.6+, STM32CubeMX, Java, PlatformIO CLI. Run "
                                                 "'init' command to create config file and set the path to STM32CubeMX "
                                                 "and other tools (if defaults doesn't work for you)")
    # Global arguments (there is also an automatically added '-h, --help' option)
    parser.add_argument('--version', action='version', version=f"stm32pio v{__version__}")
    parser.add_argument('-v', '--verbose', help="enable verbose output (default: INFO)", action='count', required=False)

    subparsers = parser.add_subparsers(dest='subcommand', title='subcommands', description="valid subcommands",
                                       help="modes of operation")

    parser_init = subparsers.add_parser('init', help="create config .ini file so you can tweak parameters before "
                                                     "proceeding")
    parser_new = subparsers.add_parser('new', help="generate CubeMX code, create PlatformIO project")
    parser_generate = subparsers.add_parser('generate', help="generate CubeMX code only")
    parser_clean = subparsers.add_parser('clean', help="clean-up the project (WARNING: it deletes ALL content of "
                                                       "'path' except the .ioc file)")

    # Common subparsers options
    for p in [parser_init, parser_new, parser_generate, parser_clean]:
        p.add_argument('-d', '--directory', dest='project_path', default=pathlib.Path.cwd(), required=False,
                       help="path to the project (current directory, if not given)")
    for p in [parser_init, parser_new]:
        p.add_argument('-b', '--board', dest='board', required=False, help="PlatformIO name of the board")
    for p in [parser_init, parser_new, parser_generate]:
        p.add_argument('--start-editor', dest='editor', required=False,
                       help="use specified editor to open PlatformIO project (e.g. subl, code, atom, etc.)")
    for p in [parser_new, parser_generate]:
        p.add_argument('--with-build', action='store_true', required=False, help="build a project after generation")

    if len(args) == 0:
        parser.print_help()
        return None

    return parser.parse_args(args)


def main(sys_argv=None) -> int:
    """
    Can be used as a high-level wrapper to do complete tasks

    Example:
        ret_code = stm32pio.app.main(sys_argv=['new', '-d', '~/path/to/project', '-b', 'nucleo_f031k6', '--with-build'])

    Args:
        sys_argv: list of strings CLI arguments

    Returns:
        0 on success, -1 otherwise
    """

    if sys_argv is None:
        sys_argv = sys.argv[1:]

    import stm32pio.settings

    args = parse_args(sys_argv)

    logger = logging.getLogger('stm32pio')  # the root (relatively to the possible outer scope) logger instance
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    # Currently only 2 levels of verbosity through the '-v' option are counted (INFO (default) and DEBUG (-v))
    if args is not None and args.subcommand is not None and args.verbose:
        logger.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(levelname)-8s "
                                               f"%(funcName)-{stm32pio.settings.log_function_fieldwidth}s "
                                               "%(message)s"))
        logger.debug("debug logging enabled")
    elif args is not None and args.subcommand is not None:
        logger.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
    else:
        logger.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.info("\nNo arguments were given, exiting...")
        return 0

    import stm32pio.lib  # import the module after sys.path modification and logger configuration

    # Main routine
    try:
        if args.subcommand == 'init':
            project = stm32pio.lib.Stm32pio(args.project_path, parameters={'board': args.board})
            if not args.board:
                logger.warning("STM32 PlatformIO board is not specified, it will be needed on PlatformIO project "
                               "creation")
            logger.info('project has been initialized. You can now edit stm32pio.ini config file')
            if args.editor:
                project.start_editor(args.editor)

        elif args.subcommand == 'new':
            project = stm32pio.lib.Stm32pio(args.project_path, parameters={'board': args.board})
            if project.config.get('project', 'board') == '':
                raise Exception("STM32 PlatformIO board is not specified, it is needed for PlatformIO project creation")
            project.generate_code()
            project.pio_init()
            project.patch()
            if args.with_build:
                project.build()
            if args.editor:
                project.start_editor(args.editor)

        elif args.subcommand == 'generate':
            project = stm32pio.lib.Stm32pio(args.project_path, save_on_destruction=False)
            project.generate_code()
            if args.with_build:
                project.build()
            if args.editor:
                project.start_editor(args.editor)

        elif args.subcommand == 'clean':
            project = stm32pio.lib.Stm32pio(args.project_path, save_on_destruction=False)
            project.clean()

    # library is designed to throw the exception in bad cases so we catch here globally
    except Exception as e:
        logger.exception(e, exc_info=logger.getEffectiveLevel() <= logging.DEBUG)
        return -1

    logger.info("exiting...")
    return 0


if __name__ == '__main__':
    sys.path.insert(0, str(pathlib.Path(sys.path[0]).parent))  # hack to be able to run the app as 'python3 app.py'
    sys.exit(main())
