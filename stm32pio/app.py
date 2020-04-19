#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__version__ = '1.21'

import argparse
import logging
import pathlib
import sys
import traceback
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
                                                 "Requirements: Python 3.6+, STM32CubeMX, Java, PlatformIO CLI. Visit "
                                                 "https://github.com/ussserrr/stm32pio for more information. Use "
                                                 "'help' command to take a glimpse on the available functionality")
    # Global arguments (there is also an automatically added '-h, --help' option)
    parser.add_argument('--version', action='version', version=f"stm32pio v{__version__}")
    parser.add_argument('-v', '--verbose', help="enable verbose output (default: INFO)", action='count')

    subparsers = parser.add_subparsers(dest='subcommand', title='subcommands', description="valid subcommands",
                                       help="modes of operation")

    parser_init = subparsers.add_parser('init', help="create config .ini file so you can tweak parameters before "
                                                     "proceeding")
    parser_new = subparsers.add_parser('new', help="generate CubeMX code, create PlatformIO project, glue them")
    parser_generate = subparsers.add_parser('generate', help="generate CubeMX code only")
    parser_status = subparsers.add_parser('status', help="get the description of the current project state")
    parser_clean = subparsers.add_parser('clean', help="clean-up the project (delete ALL content of 'path' "
                                                       "except the .ioc file)")

    # Common subparsers options
    for p in [parser_init, parser_new, parser_generate, parser_status, parser_clean]:
        p.add_argument('-d', '--directory', dest='project_path', default=pathlib.Path.cwd(),
                       help="path to the project (current directory, if not given)")
    for p in [parser_init, parser_new]:
        p.add_argument('-b', '--board', dest='board', default='', help="PlatformIO name of the board")
    for p in [parser_init, parser_new, parser_generate]:
        p.add_argument('--start-editor', dest='editor',
                       help="use specified editor to open the PlatformIO project (e.g. subl, code, atom, etc.)")
    for p in [parser_new, parser_generate]:
        p.add_argument('--with-build', action='store_true', help="build the project after generation")

    parser_clean.add_argument('-q', '--quiet', action='store_true',
                              help="suppress the caution about the content removal (be sure of what you are doing!)")

    if len(args) == 0:
        parser.print_help()
        return None

    return parser.parse_args(args)


def main(sys_argv: Optional[list] = None) -> int:
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

    # Import modules after sys.path modification
    import stm32pio.settings
    import stm32pio.lib
    import stm32pio.util

    args = parse_args(sys_argv)

    logger = logging.getLogger('stm32pio')  # the root (relatively to the possible outer scope) logger instance
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    # Currently only 2 levels of verbosity through the '-v' option are counted (INFO (default) and DEBUG (-v))
    if args is not None and args.subcommand is not None and args.verbose:
        logger.setLevel(logging.DEBUG)
        handler.setFormatter(stm32pio.util.DispatchingFormatter(
            f"%(levelname)-8s %(funcName)-{stm32pio.settings.log_fieldwidth_function}s %(message)s",
            special=stm32pio.util.special_formatters))
        logger.debug("debug logging enabled")
    elif args is not None and args.subcommand is not None:
        logger.setLevel(logging.INFO)
        handler.setFormatter(stm32pio.util.DispatchingFormatter("%(levelname)-8s %(message)s",
                                                                special=stm32pio.util.special_formatters))
    else:
        print("\nNo arguments were given, exiting...")
        return 0

    # Main routine
    try:
        if args.subcommand == 'init':
            project = stm32pio.lib.Stm32pio(args.project_path, parameters={'project': {'board': args.board}},
                                            instance_options={'save_on_destruction': True})
            if not args.board:
                logger.warning("STM32 PlatformIO board is not specified, it will be needed on PlatformIO project "
                               "creation")
            logger.info("project has been initialized. You can now edit stm32pio.ini config file")
            if args.editor:
                project.start_editor(args.editor)

        elif args.subcommand == 'new':
            project = stm32pio.lib.Stm32pio(args.project_path, parameters={'project': {'board': args.board}},
                                            instance_options={'save_on_destruction': True})
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
            project = stm32pio.lib.Stm32pio(args.project_path)
            project.generate_code()
            if args.with_build:
                project.build()
            if args.editor:
                project.start_editor(args.editor)

        elif args.subcommand == 'status':
            project = stm32pio.lib.Stm32pio(args.project_path)
            print(project.state)

        elif args.subcommand == 'clean':
            project = stm32pio.lib.Stm32pio(args.project_path)
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
        # Print format is: "ExceptionName: message"
        logger.exception(traceback.format_exception_only(*(sys.exc_info()[:2]))[-1],
                         exc_info=logger.isEnabledFor(logging.DEBUG))
        return -1

    return 0


if __name__ == '__main__':
    sys.path.append(str(pathlib.Path(sys.path[0]).parent))  # hack to be able to run the app as 'python app.py'
    sys.exit(main())
