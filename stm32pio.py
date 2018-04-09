#!/usr/bin/env python3


__version__ = 0.5

import sys, argparse, logging


parser = argparse.ArgumentParser(description='Automation of creating and updating STM32CubeMX-PlatformIO projects. '\
											 'Requirements: Python 3.5+, STM32CubeMX, Platformio CLI or PlatformIO '\
											 'Shell Commands (Menubar -> PlatformIO -> Install Shell Commands). '\
											 "Edit settings.py to set path to the STM32CubeMX (if it can't find).")
# global arguments (there is also automatically added -h, --help option)
parser.add_argument('--version', action='version', version='%(prog)s v{version}'.format(version=__version__))
parser.add_argument('-v', '--verbose', help='enable verbose output (default: INFO)', action='count', required=False)

subparsers = parser.add_subparsers(dest='subcommand', title='subcommands',
								   description='valid subcommands', help='modes of operation')

parser_new = subparsers.add_parser('new', help='generate cubemx-code, create pio-project [and start editor]')
parser_new.add_argument('-d', '--directory', dest='path', help='path to project', required=True)
parser_new.add_argument('-b', '--board', dest='board', help='pio name of the board', required=True)
parser_new.add_argument('--start-editor', dest='editor', help="use specidied editor to open pio project",
						choices=['atom', 'vscode'], required=False)

parser_generate = subparsers.add_parser('generate', help='generate cubemx-code')
parser_generate.add_argument('-d', '--directory', dest='path', help='path to project', required=True)

parser_clean = subparsers.add_parser('clean', help="clean-up the project (delete all content of 'path'"\
												   "except the .ioc file)")
parser_clean.add_argument('-d', '--directory', dest='path', help='path to project', required=True)

args = parser.parse_args()


# Logger instance goes through the whole program.
# Currently only 2 levels of verbosity though -v option is counted
logging.basicConfig(format='%(levelname)-8s %(message)s')
logger = logging.getLogger('')
if args.verbose:
	logger.setLevel(logging.DEBUG)
	logger.debug('debug logging enabled')
else:
	logger.setLevel(logging.INFO)


# print help if no arguments were given
if not len(sys.argv) > 1:
	parser.print_help()
	sys.exit()

# main routine
else:
	import os, subprocess
	from miscs import generate_code, pio_init, patch_platformio_ini, start_editor, clean


	path = os.path.normpath(args.path)  # handle /path/to/proj and /path/to/proj/ cases
	if not os.path.exists(path):
		logger.error('incorrect path')
		sys.exit()


	if args.subcommand == 'new':
		generate_code(path)
		pio_init(path, args.board)
		patch_platformio_ini(path)

		if args.editor:
			start_editor(path, args.editor)


	elif args.subcommand == 'generate':
		generate_code(path)


	elif args.subcommand == 'clean':
		clean(path)


logger.info('normal exit')
