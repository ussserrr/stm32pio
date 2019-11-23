import unittest
import configparser
import pathlib
import platform
import shutil
import subprocess
import tempfile
import time
import inspect
import sys

import stm32pio.app
import stm32pio.settings
import stm32pio.lib


# Test data
TEST_PROJECT_PATH = pathlib.Path('stm32pio-test-project').resolve()
if not TEST_PROJECT_PATH.is_dir() or not TEST_PROJECT_PATH.joinpath('stm32pio-test-project.ioc').is_file():
    raise FileNotFoundError("No test project is present")
TEST_PROJECT_BOARD = 'nucleo_f031k6'


temp_dir = tempfile.TemporaryDirectory()
FIXTURE_PATH = pathlib.Path(temp_dir.name).joinpath(TEST_PROJECT_PATH.name)

STM32PIO_MAIN_SCRIPT = inspect.getfile(stm32pio.app)
PYTHON_EXEC = sys.executable


class TestUnit(unittest.TestCase):
    """

    """

    def setUp(self) -> None:
        self.tearDown()
        shutil.copytree(TEST_PROJECT_PATH, FIXTURE_PATH)

    def tearDown(self) -> None:
        shutil.rmtree(FIXTURE_PATH, ignore_errors=True)

    def test_generate_code(self):
        """
        Check whether files and folders have been created
        """
        project = stm32pio.lib.Stm32pio(FIXTURE_PATH, parameters={'board': TEST_PROJECT_BOARD})
        project.generate_code()

        # Assuming that the presence of these files indicates a success
        files_should_be_present = ['Src/main.c', 'Inc/main.h']
        for file in files_should_be_present:
            with self.subTest(file_should_be_present=file, msg=f"{file} hasn't been created"):
                self.assertEqual(FIXTURE_PATH.joinpath(file).is_file(), True)

    def test_pio_init(self):
        """
        Consider that existence of 'platformio.ini' file is displaying successful PlatformIO project initialization
        """
        project = stm32pio.lib.Stm32pio(FIXTURE_PATH, parameters={'board': TEST_PROJECT_BOARD})
        result = project.pio_init()

        self.assertEqual(result, 0, msg="Non-zero return code")
        self.assertTrue(FIXTURE_PATH.joinpath('platformio.ini').is_file(), msg="platformio.ini is not there")

    def test_patch(self):
        """
        Compare contents of the patched string and the desired patch
        """
        project = stm32pio.lib.Stm32pio(FIXTURE_PATH)
        test_content = "*** TEST PLATFORMIO.INI FILE ***"
        FIXTURE_PATH.joinpath('platformio.ini').write_text(test_content)

        project.patch()

        self.assertFalse(FIXTURE_PATH.joinpath('include').is_dir(), msg="'include' has not been deleted")

        after_patch_content = FIXTURE_PATH.joinpath('platformio.ini').read_text()

        self.assertEqual(after_patch_content[:len(test_content)], test_content,
                         msg="Initial content of platformio.ini is corrupted")
        self.assertEqual(after_patch_content[len(test_content):],
                         stm32pio.settings.config_default['project']['platformio_ini_patch_content'],
                         msg="Patch content is not as expected")

    def test_build_should_raise(self):
        """
        Build an empty project so PlatformIO should return non-zero code and we, in turn, should throw the exception
        """
        project = stm32pio.lib.Stm32pio(FIXTURE_PATH, parameters={'board': TEST_PROJECT_BOARD})
        project.pio_init()

        with self.assertRaisesRegex(Exception, "PlatformIO build error",
                                    msg="Build error exception hadn't been raised"):
            project.pio_build()

    def test_run_editor(self):
        """
        Call the editors
        """
        project = stm32pio.lib.Stm32pio(FIXTURE_PATH)

        editors = {
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

        for command, name in editors.items():
            if platform.system() == 'Windows':
                command_str = f"where {command} /q"
            else:
                command_str = f"command -v {command}"
            editor_exists = True if subprocess.run(command_str, shell=True, stdout=subprocess.PIPE,
                                                   stderr=subprocess.PIPE).returncode == 0\
                            else False
            if editor_exists:
                with self.subTest(command=command, name=name[platform.system()]):
                    project.start_editor(command)
                    time.sleep(1)  # wait a little bit for app to start
                    if platform.system() == 'Windows':
                        # "encoding='utf-8'" is for "a bytes-like object is required, not 'str'" in "assertIn"
                        result = subprocess.run(['wmic', 'process', 'get', 'description'],
                                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
                    else:
                        result = subprocess.run(['ps', '-A'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                encoding='utf-8')
                        # Or, for Python 3.7 and above:
                        # result = subprocess.run(['ps', '-A'], capture_output=True, encoding='utf-8')
                    self.assertIn(name[platform.system()], result.stdout)

    def test_init_path_not_found_should_raise(self):
        """
        Pass non-existing path and expect the error
        """
        path_does_not_exist = 'does_not_exist'

        not_existing_path = FIXTURE_PATH.joinpath(path_does_not_exist)
        with self.assertRaises(FileNotFoundError, msg="FileNotFoundError was not raised") as cm:
            stm32pio.lib.Stm32pio(not_existing_path)
            self.assertIn(path_does_not_exist, str(cm.exception), msg="Exception doesn't contain a description")

    def test_save_config(self):
        project = stm32pio.lib.Stm32pio(FIXTURE_PATH, parameters={'board': TEST_PROJECT_BOARD})
        project.save_config()

        self.assertTrue(FIXTURE_PATH.joinpath('stm32pio.ini').is_file(), msg="'stm32pio.ini' file hasn't been created")

        config = configparser.ConfigParser()
        config.read(str(FIXTURE_PATH.joinpath('stm32pio.ini')))
        for section, parameters in stm32pio.settings.config_default.items():
            for option, value in parameters.items():
                with self.subTest(section=section, option=option, msg="Section/key is not found in saved config file"):
                    self.assertNotEqual(config.get(section, option, fallback="Not found"), "Not found")
        self.assertEqual(config.get('project', 'board', fallback="Not found"), TEST_PROJECT_BOARD,
                         msg="'board' has not been set")


class TestIntegration(unittest.TestCase):
    """

    """

    def setUp(self) -> None:
        self.tearDown()
        shutil.copytree(TEST_PROJECT_PATH, FIXTURE_PATH)

    def tearDown(self) -> None:
        shutil.rmtree(FIXTURE_PATH, ignore_errors=True)

    def test_config_prioritites(self):
        custom_content = "SOME CUSTOM CONTENT"

        config = configparser.ConfigParser()
        config.read_dict({
            'project': {
                'platformio_ini_patch_content': custom_content
            }
        })
        with FIXTURE_PATH.joinpath('stm32pio.ini').open(mode='w') as config_file:
            config.write(config_file)

        project = stm32pio.lib.Stm32pio(FIXTURE_PATH, parameters={'board': TEST_PROJECT_BOARD})
        project.pio_init()
        project.patch()

        after_patch_content = FIXTURE_PATH.joinpath('platformio.ini').read_text()
        self.assertIn(custom_content, after_patch_content, msg="Patch content is not from user config")

    def test_build(self):
        """
        Initialize a new project and try to build it
        """
        project = stm32pio.lib.Stm32pio(FIXTURE_PATH, parameters={'board': TEST_PROJECT_BOARD})
        project.generate_code()
        project.pio_init()
        project.patch()

        result = project.pio_build()

        self.assertEqual(result, 0, msg="Build failed")

    def test_regenerate_code(self):
        """
        Simulate new project creation, its changing and CubeMX code re-generation (for example, after adding new
        hardware features and some new files)
        """

        project = stm32pio.lib.Stm32pio(FIXTURE_PATH, parameters={'board': TEST_PROJECT_BOARD})

        # Generate a new project ...
        project.generate_code()
        project.pio_init()
        project.patch()

        # ... change it:
        test_file_1 = FIXTURE_PATH.joinpath('Src', 'main.c')
        test_content_1 = "*** TEST STRING 1 ***\n"
        test_file_2 = FIXTURE_PATH.joinpath('Inc', 'my_header.h')
        test_content_2 = "*** TEST STRING 2 ***\n"
        #   - add some sample string inside CubeMX' /* BEGIN - END */ block
        main_c_content = test_file_1.read_text()
        pos = main_c_content.index("while (1)")
        main_c_new_content = main_c_content[:pos] + test_content_1 + main_c_content[pos:]
        test_file_1.write_text(main_c_new_content)
        #  - add new file inside the project
        test_file_2.write_text(test_content_2)

        # Re-generate CubeMX project
        project.generate_code()

        # Check if added information is preserved
        main_c_after_regenerate_content = test_file_1.read_text()
        my_header_h_after_regenerate_content = test_file_2.read_text()
        self.assertIn(test_content_1, main_c_after_regenerate_content,
                      msg=f"User content hasn't been preserved after regeneration in {test_file_1}")
        self.assertIn(test_content_2, my_header_h_after_regenerate_content,
                      msg=f"User content hasn't been preserved after regeneration in {test_file_2}")


class TestCLI(unittest.TestCase):
    """

    """

    def setUp(self) -> None:
        self.tearDown()
        shutil.copytree(TEST_PROJECT_PATH, FIXTURE_PATH)

    def tearDown(self) -> None:
        shutil.rmtree(FIXTURE_PATH, ignore_errors=True)

    def test_clean(self):
        """
        Dangerous test actually...
        """

        # Create files and folders
        file_should_be_deleted = FIXTURE_PATH.joinpath('file.should.be.deleted')
        dir_should_be_deleted = FIXTURE_PATH.joinpath('dir.should.be.deleted')
        file_should_be_deleted.touch(exist_ok=False)
        dir_should_be_deleted.mkdir(exist_ok=False)

        # Clean
        return_code = stm32pio.app.main(sys_argv=['clean', '-d', str(FIXTURE_PATH)])
        self.assertEqual(return_code, 0, msg="Non-zero return code")

        # Look for remaining items
        self.assertFalse(file_should_be_deleted.is_file(), msg=f"{file_should_be_deleted} is still there")
        self.assertFalse(dir_should_be_deleted.is_dir(), msg=f"{dir_should_be_deleted} is still there")

        # And .ioc file should be preserved
        self.assertTrue(FIXTURE_PATH.joinpath(f"{FIXTURE_PATH.name}.ioc").is_file(), msg="Missing .ioc file")

    def test_new(self):
        """
        Successful build is the best indicator that all went right so we use '--with-build' option
        """
        return_code = stm32pio.app.main(sys_argv=['new', '-d', str(FIXTURE_PATH), '-b', TEST_PROJECT_BOARD,
                                                  '--with-build'])

        self.assertEqual(return_code, 0, msg="Non-zero return code")
        # .ioc file should be preserved
        self.assertTrue(FIXTURE_PATH.joinpath(f"{FIXTURE_PATH.name}.ioc").is_file(), msg="Missing .ioc file")

    def test_generate(self):
        """
        """
        return_code = stm32pio.app.main(sys_argv=['generate', '-d', str(FIXTURE_PATH)])
        self.assertEqual(return_code, 0, msg="Non-zero return code")

        inc_dir = 'Inc'
        src_dir = 'Src'

        self.assertTrue(FIXTURE_PATH.joinpath(inc_dir).is_dir(), msg=f"Missing '{inc_dir}'")
        self.assertTrue(FIXTURE_PATH.joinpath(src_dir).is_dir(), msg=f"Missing '{src_dir}'")
        self.assertFalse(len(list(FIXTURE_PATH.joinpath(inc_dir).iterdir())) == 0, msg=f"'{inc_dir}' is empty")
        self.assertFalse(len(list(FIXTURE_PATH.joinpath(src_dir).iterdir())) == 0, msg=f"'{src_dir}' is empty")

        # .ioc file should be preserved
        self.assertTrue(FIXTURE_PATH.joinpath(f"{FIXTURE_PATH.name}.ioc").is_file(), msg="Missing .ioc file")

    def test_incorrect_path(self):
        """
        """
        with self.assertLogs(level='ERROR') as logs:
            return_code = stm32pio.app.main(sys_argv=['init', '-d', '~/path/does/not/exist'])
            self.assertNotEqual(return_code, 0, msg='Return code should be non-zero')
            self.assertTrue(next(True for item in logs.output if 'path/does/not/exist' in item),
                            msg="ERROR logging message hasn't been printed")

    def test_no_ioc_file(self):
        """
        """

        dir_with_no_ioc_file = FIXTURE_PATH.joinpath('dir.with.no.ioc.file')
        dir_with_no_ioc_file.mkdir(exist_ok=False)

        with self.assertLogs(level='ERROR') as logs:
            return_code = stm32pio.app.main(sys_argv=['init', '-d', str(dir_with_no_ioc_file)])
            self.assertNotEqual(return_code, 0, msg='Return code should be non-zero')
            self.assertTrue(next(True for item in logs.output if "CubeMX project .ioc file" in item),
                            msg="ERROR logging message hasn't been printed")

    def test_verbose(self):
        """
        Run as subprocess (can be done as assertLogs(), see above)
        """

        stm32pio_exec = inspect.getfile(stm32pio.app)  # get the path to the main stm32pio script
        # get the current python executable (no need to guess whether it's python or python3 and so on)
        python_exec = sys.executable

        result = subprocess.run([python_exec, stm32pio_exec, '-v', 'generate', '-d', FIXTURE_PATH], encoding='utf-8',
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        self.assertEqual(result.returncode, 0, msg="Non-zero return code")
        # Somehow stderr and not stdout contains the actual output
        self.assertIn('DEBUG', result.stderr, msg="Verbose logging output hasn't been enabled on stderr")
        self.assertIn('Starting STM32CubeMX', result.stdout, msg="STM32CubeMX didn't print its logs")

    def test_non_verbose(self):
        """
        """

        result = subprocess.run([PYTHON_EXEC, STM32PIO_MAIN_SCRIPT, 'generate', '-d', FIXTURE_PATH], encoding='utf-8',
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        self.assertEqual(result.returncode, 0, msg="Non-zero return code")
        self.assertNotIn('DEBUG', result.stderr, msg="Verbose logging output has been enabled on stderr")
        self.assertNotIn('DEBUG', result.stdout, msg="Verbose logging output has been enabled on stdout")
        self.assertNotIn('Starting STM32CubeMX', result.stdout, msg="STM32CubeMX printed its logs")

    def test_init(self):
        subprocess.run([PYTHON_EXEC, STM32PIO_MAIN_SCRIPT, 'init', '-d', FIXTURE_PATH, '-b', TEST_PROJECT_BOARD])

        self.assertTrue(FIXTURE_PATH.joinpath('stm32pio.ini').is_file(), msg="'stm32pio.ini' file hasn't been created")

        config = configparser.ConfigParser()
        config.read(str(FIXTURE_PATH.joinpath('stm32pio.ini')))
        for section, parameters in stm32pio.settings.config_default.items():
            for option, value in parameters.items():
                with self.subTest(section=section, option=option, msg="Section/key is not found in saved config file"):
                    self.assertIsNotNone(config.get(section, option, fallback=None))
        self.assertEqual(config.get('project', 'board', fallback="Not found"), TEST_PROJECT_BOARD,
                         msg="'board' has not been set")


def tearDownModule():
    """
    Clean up after yourself
    """
    temp_dir.cleanup()


if __name__ == '__main__':
    unittest.main()
