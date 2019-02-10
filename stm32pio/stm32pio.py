#!/usr/bin/env python3


if __name__ == '__main__':

    import argparse
    import logging
    import sys
    import os

    import __init__

    parser = argparse.ArgumentParser(description="Automation of creating and updating STM32CubeMX-PlatformIO projects. "
                                                 "Requirements: Python 3.6+, STM32CubeMX, Java, PlatformIO CLI. Edit "
                                                 "settings.py to set project path to the STM32CubeMX (if default "
                                                 "doesn't work)")
    # global arguments (there is also automatically added '-h, --help' option)
    parser.add_argument('--version', action='version', version=f"%(prog)s v{__init__.__version__}")
    parser.add_argument('-v', '--verbose', help="enable verbose output (default: INFO)", action='count', required=False)

    subparsers = parser.add_subparsers(dest='subcommand', title='subcommands',
                                       description="valid subcommands", help="modes of operation")

    parser_new = subparsers.add_parser('new',
                                       help="generate CubeMX code, create PlatformIO project [and start the editor]")
    parser_new.add_argument('-d', '--directory', dest='project_path',
                            help="path to the project (current directory, if not given)", default=os.getcwd())
    parser_new.add_argument('-b', '--board', dest='board', help="PlatformIO name of the board", required=True)
    parser_new.add_argument('--start-editor', dest='editor', help="use specified editor to open PlatformIO project",
                            choices=['atom', 'vscode', 'sublime'], required=False)

    parser_generate = subparsers.add_parser('generate', help="generate CubeMX code")
    parser_generate.add_argument('-d', '--directory', dest='project_path',
                                 help="path to the project (current directory, if not given)", default=os.getcwd())

    parser_clean = subparsers.add_parser('clean', help="clean-up the project (WARNING: it deletes ALL content of "
                                                       "'path' except the .ioc file)")
    parser_clean.add_argument('-d', '--directory', dest='project_path',
                              help="path to the project (current directory, if not given)", default=os.getcwd())

    args = parser.parse_args()


    # Logger instance goes through the whole program.
    # Currently only 2 levels of verbosity through the '-v' option are counted
    logging.basicConfig(format="%(levelname)-8s %(message)s")
    logger = logging.getLogger('')
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("debug logging enabled")
    else:
        logger.setLevel(logging.INFO)


    # Show help and exit if no arguments were given
    if not len(sys.argv) > 1:
        parser.print_help()
        sys.exit()

    # Main routine
    else:
        import util

        # Handle '/path/to/proj' and '/path/to/proj/', 'dot' (current directory) cases
        project_path = os.path.abspath(os.path.normpath(args.project_path))
        if not os.path.exists(project_path):
            logger.error("incorrect project path")
            sys.exit()


        if args.subcommand == 'new':
            util.generate_code(project_path)
            util.pio_init(project_path, args.board)
            util.patch_platformio_ini(project_path)

            if args.editor:
                util.start_editor(project_path, args.editor)


        elif args.subcommand == 'generate':
            util.generate_code(project_path)


        elif args.subcommand == 'clean':
            util.clean(project_path)


    logger.info("exiting...")
