import collections.abc
import configparser
import contextlib
import io
import logging
import platform
import string
import subprocess
import time
import unittest.mock

from functools import reduce
from typing import Mapping, Union

# Provides test constants and definitions
import stm32pio.core.pio
from tests.common import *

import stm32pio.core.settings
import stm32pio.core.project
import stm32pio.core.cubemx
import stm32pio.core.util


class TestUnit(CustomTestCase):
    """
    Test the single method. As we at some point decided to use a class instead of the set of scattered functions we need
    to do some preparations for almost every test (e.g. instantiate the class, create the PlatformIO project, etc.),
    though, so the architecture now is way less modular
    """

    def test_generate_code(self):
        """
        Check whether files and folders have been created (by STM32CubeMX)
        """
        project = stm32pio.core.project.Stm32pio(STAGE_PATH, parameters={'project': {'board': PROJECT_BOARD}})
        project.generate_code()

        # Assuming that the presence of these files indicating a success
        files_should_be_present = ['Src/main.c', 'Inc/main.h']
        for file in files_should_be_present:
            with self.subTest(msg=f"{file} hasn't been created"):
                self.assertEqual(STAGE_PATH.joinpath(file).is_file(), True)

    def test_pio_init(self):
        """
        Consider that the existence of a 'platformio.ini' file showing a successful PlatformIO project initialization.
        There are other artifacts that can be checked too but we are interested only in a 'platformio.ini' anyway. Also,
        check that it is a correct configparser.ConfigParser file and is not empty
        """
        project = stm32pio.core.project.Stm32pio(STAGE_PATH, parameters={'project': {'board': PROJECT_BOARD}})
        result = project.pio_init()

        self.assertEqual(result, 0, msg="Non-zero return code")
        self.assertTrue(STAGE_PATH.joinpath('platformio.ini').is_file(), msg="platformio.ini is not there")

        platformio_ini = configparser.ConfigParser(interpolation=None)
        self.assertGreater(len(platformio_ini.read(STAGE_PATH.joinpath('platformio.ini'))), 0,
                           msg='platformio.ini is empty')

    def test_patch(self):
        """
        Check that the new parameters have been added, modified ones have been updated and existing parameters didn't
        gone. Also, check for unnecessary folders deletion
        """
        project = stm32pio.core.project.Stm32pio(STAGE_PATH)

        header = inspect.cleandoc('''
            ; This is a test config .ini file
            ; with a comment. It emulates a real
            ; platformio.ini file
        ''') + '\n'
        test_content = header + inspect.cleandoc('''
            [platformio]
            include_dir = this s;789hould be replaced
                let's add some tricky content
            ; there should appear a new parameter
            test_key3 = this should be preserved
                alright?

            [test_section]
            test_key1 = test_value1
            test_key2 = 123
        ''') + '\n'
        STAGE_PATH.joinpath('platformio.ini').write_text(test_content)
        STAGE_PATH.joinpath('include').mkdir()

        project.patch()

        with self.subTest():
            self.assertFalse(STAGE_PATH.joinpath('include').is_dir(), msg="'include' has not been deleted")

        original_test_config = configparser.ConfigParser(interpolation=None)
        original_test_config.read_string(test_content)

        patched_config = configparser.ConfigParser(interpolation=None)
        patch_config = configparser.ConfigParser(interpolation=None)
        patch_config.read_string(project.config.get('project', 'platformio_ini_patch_content'))

        patched_content = STAGE_PATH.joinpath('platformio.ini').read_text()
        patched_config.read_string(patched_content)
        self.assertGreater(len(patched_content), 0)

        for patch_section in patch_config.sections():
            self.assertTrue(patched_config.has_section(patch_section), msg=f"{patch_section} is missing")
            for patch_key, patch_value in patch_config.items(patch_section):
                self.assertEqual(patched_config.get(patch_section, patch_key, fallback=None), patch_value,
                                 msg=f"{patch_section}: {patch_key}={patch_value} is missing or incorrect in the "
                                     "patched config")

        for original_section in original_test_config.sections():
            self.assertTrue(patched_config.has_section(original_section),
                            msg=f"{original_section} from the original config is missing")
            for original_key, original_value in original_test_config.items(original_section):
                # We've already checked patch parameters so skip them
                if not patch_config.has_option(original_section, original_key):
                    self.assertEqual(patched_config.get(original_section, original_key), original_value,
                                     msg=f"{original_section}: {original_key}={original_value} is corrupted")

        self.assertIn(header, patched_content, msg='Header should be preserved')

    def test_build_should_handle_error(self):
        """
        Build an empty project so PlatformIO should return an error
        """
        project = stm32pio.core.project.Stm32pio(STAGE_PATH, parameters={'project': {'board': PROJECT_BOARD}})
        project.pio_init()

        with self.assertLogs(level='ERROR') as logs:
            self.assertNotEqual(project.build(), 0, msg="Build error was not indicated")
            # next() - Technique to find something in array, string, etc. (or to indicate that there is no of such)
            self.assertTrue(next((True for item in logs.output if "PlatformIO build error" in item), False),
                            msg="Error message does not match")

    def test_start_editor(self):
        """
        Call the editors. Use subprocess shell=True as it works on all OSes
        """
        project = stm32pio.core.project.Stm32pio(STAGE_PATH)

        editors = {  # some editors to check
            'atom': {
                'Windows': 'atom.exe',
                'Darwin': 'Atom',
                'Linux': 'atom'
            },
            'code': {
                'Windows': 'Code.exe',
                'Darwin': 'Visual Studio Code',
                'Linux': 'code'
            },
            'subl': {
                'Windows': 'sublime_text.exe',
                'Darwin': 'Sublime',
                'Linux': 'sublime'
            }
        }

        # Look for the command presence in the system so we test only installed editors
        if platform.system() == 'Windows':
            command_template = string.Template("where $editor /q")
        else:
            command_template = string.Template("command -v $editor")

        for editor, editor_process_names in editors.items():
            if subprocess.run(command_template.substitute(editor=editor), shell=True).returncode == 0:
                editor_exists = True
            else:
                editor_exists = False

            if editor_exists:
                with self.subTest(command=editor, name=editor_process_names[platform.system()]):
                    project.start_editor(editor)

                    time.sleep(1)  # wait a little bit for app to start

                    if platform.system() == 'Windows':
                        command_arr = ['wmic', 'process', 'get', 'description']
                    else:
                        command_arr = ['ps', '-A']
                    # "encoding='utf-8'" is for "a bytes-like object is required, not 'str'" in "assertIn"
                    result = subprocess.run(command_arr, stdout=subprocess.PIPE, encoding='utf-8')
                    # TODO: or, for Python 3.7 and above:
                    # result = subprocess.run(command_arr, capture_output=True, encoding='utf-8')
                    self.assertIn(editor_process_names[platform.system()], result.stdout)

    def test_init_path_not_found_should_raise(self):
        """
        Pass a non-existing path and expect the error
        """
        path_does_not_exist_name = 'does_not_exist'

        path_does_not_exist = STAGE_PATH.joinpath(path_does_not_exist_name)
        with self.assertRaisesRegex(FileNotFoundError, path_does_not_exist_name,
                                    msg="FileNotFoundError has not been raised or doesn't contain a description"):
            stm32pio.core.project.Stm32pio(path_does_not_exist)

    def test_save_config(self):
        """
        Explicitly save the config to a file and look did that actually happen and whether all the information was
        preserved
        """
        # 'board' is non-default, 'project'-section parameter
        project = stm32pio.core.project.Stm32pio(STAGE_PATH, parameters={'project': {'board': PROJECT_BOARD}})

        # Merge additional parameters
        retcode = project.save_config({
            'project': {
                'additional_test_key': 'test_value'
            }
        })

        self.assertEqual(retcode, 0, msg="Return code of the method is non-zero")
        self.assertTrue(STAGE_PATH.joinpath(stm32pio.core.settings.config_file_name).is_file(),
                        msg=f"{stm32pio.core.settings.config_file_name} file hasn't been created")

        config = configparser.ConfigParser(interpolation=None)
        self.assertGreater(len(config.read(STAGE_PATH.joinpath(stm32pio.core.settings.config_file_name))), 0,
                           msg="Config is empty")
        for section, parameters in stm32pio.core.settings.config_default.items():
            for option, value in parameters.items():
                with self.subTest(section=section, option=option,
                                  msg="Section/key is not found in the saved config file"):
                    self.assertNotEqual(config.get(section, option, fallback="Not found"), "Not found")

        self.assertEqual(config.get('project', 'board', fallback="Not found"), PROJECT_BOARD,
                         msg="'board' has not been set")
        self.assertEqual(config.get('project', 'additional_test_key', fallback="Not found"), 'test_value',
                         msg="Merged config is not present in the saved file")

    def test_get_platformio_boards(self):
        """
        PlatformIO identifiers of boards are requested using PlatformIO CLI in JSON format
        """
        boards = stm32pio.core.pio.get_boards()

        self.assertIsInstance(boards, collections.abc.MutableSequence)
        self.assertGreater(len(boards), 0, msg="boards list is empty")
        self.assertTrue(all(isinstance(item, str) for item in boards), msg="some list items are not strings")

    def test_ioc_file_provided(self):
        """
        Test a correct handling of a case when the .ioc file was specified instead of the containing directory
        """

        # Create multiple .ioc files
        shutil.copy(STAGE_PATH.joinpath(PROJECT_IOC_FILENAME), STAGE_PATH.joinpath('42.ioc'))
        shutil.copy(STAGE_PATH.joinpath(PROJECT_IOC_FILENAME), STAGE_PATH.joinpath('Abracadabra.ioc'))

        project = stm32pio.core.project.Stm32pio(STAGE_PATH.joinpath('42.ioc'))  # pick just one
        self.assertTrue(project.cubemx.ioc.path.samefile(STAGE_PATH.joinpath('42.ioc')),
                        msg="Provided .ioc file hasn't been chosen")
        self.assertEqual(project.config.get('project', 'ioc_file'), '42.ioc',
                         msg="Provided .ioc file is not in the config")

    def test_validate_environment(self):
        project = stm32pio.core.project.Stm32pio(STAGE_PATH)

        with self.subTest(msg="Valid config"):
            result_should_be_ok = project.validate_environment()
            self.assertTrue(result_should_be_ok.succeed, msg="All the tools are correct but the validation says "
                                                             "otherwise")

        with self.subTest(msg="Invalid config"):
            project.config.set('app', 'platformio_cmd', 'this_command_doesnt_exist')
            result_should_fail = project.validate_environment()
            self.assertFalse(result_should_fail.succeed, msg="One tool is incorrect and the results should reflect "
                                                             "this")
            platformio_result = next((result for result in result_should_fail if result.name == 'platformio_cmd'), None)
            self.assertIsNotNone(platformio_result, msg="PlatformIO validation results not found")
            self.assertFalse(platformio_result.succeed, msg="PlatformIO validation results should be False")

    def test_inspect_ioc(self):
        with self.subTest(msg="Parsing an .ioc file"):
            config = stm32pio.core.cubemx.IocConfig(STAGE_PATH, PROJECT_IOC_FILENAME, logger=logging.getLogger('any'))
            self.assertSequenceEqual(config.sections(), [stm32pio.core.cubemx.IocConfig.fake_section_name],
                                     msg="Incorrect set of config sections", seq_type=list)
            self.assertGreater(len(config[config.fake_section_name].keys()), 10, msg="There should be a lot of keys")

        with self.subTest(msg="Inspecting a proper config"):
            config = stm32pio.core.cubemx.IocConfig(STAGE_PATH, PROJECT_IOC_FILENAME, logger=logging.getLogger('any'))
            with contextlib.redirect_stderr(io.StringIO()) as logs:
                config.inspect(PROJECT_BOARD)
            self.assertEqual(logs.getvalue(), '', msg="Correctly set config shouldn't produce any warnings")

        with self.subTest(msg="Inspecting an invalid config"):
            invalid_content = inspect.cleandoc('''
                board=SOME-BOARD-123
                # board is wrong and no other parameters at all
            ''') + '\n'
            invalid_ioc = STAGE_PATH / 'invalid.ioc'
            invalid_ioc.write_text(invalid_content)
            config = stm32pio.core.cubemx.IocConfig(STAGE_PATH, 'invalid.ioc', logger=logging.getLogger('any'))
            with self.assertLogs(logger='any', level=logging.WARNING) as logs:
                config.inspect(PROJECT_BOARD)
            self.assertEqual(len(logs.records), 4, msg="There should be 4 warning log messages")

        with self.subTest(msg="Custom board with unmatched MCUs"):
            ioc_content = inspect.cleandoc('''
                board=custom
                ProjectManager.DeviceId=some_wrong_mcu
            ''') + '\n'
            invalid_ioc = STAGE_PATH / 'invalid.ioc'
            invalid_ioc.write_text(ioc_content)
            config = stm32pio.core.cubemx.IocConfig(STAGE_PATH, 'invalid.ioc', logger=logging.getLogger('any'))
            with self.assertLogs(logger='any', level=logging.WARNING) as logs:
                config.inspect(PROJECT_BOARD, 'STM32F031K6T6')
            self.assertTrue(any('MCU' in line for line in logs.output), msg="No mention of mismatched MCUs")

        with self.subTest(msg="Saving the config back"):
            ioc_file = STAGE_PATH / PROJECT_IOC_FILENAME
            initial_content = ioc_file.read_text()
            config = stm32pio.core.cubemx.IocConfig(STAGE_PATH, PROJECT_IOC_FILENAME, logger=logging.getLogger('any'))

            config.save()
            self.assertEqual(ioc_file.read_text(), initial_content, msg="Configs should be identical")

            changed_board = "INTEL-8086"
            config[config.fake_section_name]['board'] = changed_board
            config.save()
            self.assertIn(f'board={changed_board}', ioc_file.read_text(), msg="Edited parameters weren't preserved")

    def test_clean(self):
        def plant_fs_tree(path: Path, tree: Mapping[str, Union[str, Mapping]], exist_ok: bool = True):
            for endpoint, content in tree.items():
                if isinstance(content, collections.abc.Mapping):
                    (path / endpoint).mkdir(exist_ok=exist_ok)
                    plant_fs_tree(path / endpoint, content, exist_ok=exist_ok)
                elif type(content) == str and len(content):
                    (path / endpoint).write_text(content)
                else:
                    (path / endpoint).touch()

        def flatten_tree(tree, root: Path = None):
            tree_paths = []
            for endpoint, content in tree.items():
                tree_paths.append(Path(endpoint) if root is None else (root / endpoint))
                if isinstance(content, collections.abc.Mapping):
                    tree_paths.extend(flatten_tree(content, root=Path(endpoint) if root is None else (root / endpoint)))
            return tree_paths

        def tree_exists_fully(path: Path, tree: Mapping[str, Union[str, Mapping]]):
            tree_paths = flatten_tree(tree, root=path)
            actual_paths = list(path.rglob('*'))
            return all(endpoint in actual_paths for endpoint in tree_paths)

        def tree_not_exists_fully(path: Path, tree: Mapping[str, Union[str, Mapping]]):
            tree_paths = flatten_tree(tree, root=path)
            actual_paths = list(path.rglob('*'))
            return all(endpoint not in actual_paths for endpoint in tree_paths)

        test_tree = {
            'root_file.txt': '',
            'root empty folder': {},
            'root_folder': {
                'nested_file.mp3': '',
                'nested_folder': {
                    'file_in_nested_folder_1.jpg': '',
                    'file in nested folder 2.png': ''
                }
            }
        }
        test_tree_endpoints = flatten_tree(test_tree)

        plant_fs_tree(STAGE_PATH, test_tree)
        with self.subTest(msg="quiet"):
            project = stm32pio.core.project.Stm32pio(STAGE_PATH)
            project.clean()
            self.assertTrue(tree_not_exists_fully(STAGE_PATH, test_tree), msg="Test tree hasn't been removed")
            self.assertTrue(project.cubemx.ioc.path.exists(), msg=".ios file wasn't preserved")

        self.setUp()  # same actions we perform between test cases (external cleaning)
        plant_fs_tree(STAGE_PATH, test_tree)
        with self.subTest(msg="not quiet, respond yes"):
            project = stm32pio.core.project.Stm32pio(STAGE_PATH)
            with unittest.mock.patch('builtins.input', return_value=stm32pio.core.settings.yes_options[0]):
                project.clean(quiet=False)
                input_args, input_kwargs = input.call_args  # input() function was called with these arguments
                input_prompt = input_args[0]
                # Check only for a name as the path separator is different for UNIX/Win
                self.assertTrue(all(endpoint.name in input_prompt for endpoint in test_tree_endpoints),
                                msg="Paths for removal should be reported to the user")
            self.assertTrue(tree_not_exists_fully(STAGE_PATH, test_tree), msg="Test tree hasn't been removed")
            self.assertTrue(project.cubemx.ioc.path.exists(), msg=".ios file wasn't preserved")

        self.setUp()
        plant_fs_tree(STAGE_PATH, test_tree)
        with self.subTest(msg="not quiet, respond no"):
            project = stm32pio.core.project.Stm32pio(STAGE_PATH)
            with unittest.mock.patch('builtins.input', return_value=stm32pio.core.settings.no_options[0]):
                project.clean(quiet=False)
            self.assertTrue(tree_exists_fully(STAGE_PATH, test_tree), msg="Test tree wasn't preserved")
            self.assertTrue(project.cubemx.ioc.path.exists(), msg=".ios file wasn't preserved")

        self.setUp()
        plant_fs_tree(STAGE_PATH, test_tree)
        with self.subTest(msg="user's ignore list"):
            ignore_list = [
                f'{STAGE_PATH.name}.ioc',
                'root_file.txt',
                'this_path_doesnt_exist_yet',
                'root_folder/nested_folder/file_in_nested_folder_1.jpg'
            ]
            ignore_list_unfolded = reduce(
                lambda array, entry:
                    array +  # accumulator
                    [Path(entry)] +  # include the entry itself cause it isn't among parents
                    [parent for parent in Path(entry).parents if parent != Path()],  # remove the '.' path
                ignore_list, [])
            project = stm32pio.core.project.Stm32pio(STAGE_PATH)
            project.config.set('project', 'cleanup_ignore', '\n'.join(ignore_list))
            project.clean()
            for endpoint in [STAGE_PATH / entry for entry in test_tree_endpoints]:
                if endpoint.relative_to(STAGE_PATH) in ignore_list_unfolded:
                    self.assertTrue(endpoint.exists(), msg="Files/folders from the ignore list should be preserved")
                else:
                    self.assertFalse(endpoint.exists(), msg="Unnecessary files/folders hasn't been removed")

        self.setUp()
        subprocess.run(['git', 'init'], cwd=str(STAGE_PATH), check=True)  # TODO: str() - 3.6 compatibility
        plant_fs_tree(STAGE_PATH, test_tree)
        STAGE_PATH.joinpath('.gitignore').write_text(inspect.cleandoc('''
            # sample .gitignore
            *.mp3
        '''))
        with self.subTest(msg="use .gitignore"):
            project = stm32pio.core.project.Stm32pio(STAGE_PATH)
            # This is important, otherwise git won't clean anything
            subprocess.run(['git', 'add', '--all'], cwd=str(STAGE_PATH), check=True)  # TODO: str() - 3.6 compatibility
            project.config.set('project', 'cleanup_use_git', 'yes')
            project.clean()
            for endpoint in [STAGE_PATH / entry for entry in test_tree_endpoints]:
                if endpoint.relative_to(STAGE_PATH) == Path('root_folder').joinpath('nested_file.mp3'):
                    self.assertFalse(endpoint.exists(), msg="Files/folders from the .gitignore should be removed")
                else:
                    self.assertTrue(endpoint.exists(), msg="Files/folders tracked by git should be preserved")

        # Nasty hack for Windows, otherwise it may not delete all the temp files
        # (https://github.com/ussserrr/stm32pio/issues/23)
        if platform.system() == 'Windows':
            subprocess.run(f'rd /s /q "{STAGE_PATH}"', shell=True, check=True)

        self.setUp()
        plant_fs_tree(STAGE_PATH, test_tree)
        with self.subTest(msg="save current content in ignore list"):
            project = stm32pio.core.project.Stm32pio(STAGE_PATH)
            project.config.set_content_as_ignore_list()
            STAGE_PATH.joinpath('this_file_should_be_removed').touch()
            project.clean()
            self.assertTrue(tree_exists_fully(STAGE_PATH, test_tree), msg="Test tree should be preserved")
            self.assertFalse(STAGE_PATH.joinpath('this_file_should_be_removed').exists(),
                             msg="File added later should be removed")
