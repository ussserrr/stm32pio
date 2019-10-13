import pathlib
import platform
import shutil
import subprocess
import time
import inspect
import sys
import unittest

import stm32pio.app
import stm32pio.settings
import stm32pio.util


# Test data
PROJECT_PATH = pathlib.Path('stm32pio/tests/stm32pio-test-project').resolve()
if not PROJECT_PATH.is_dir() and not PROJECT_PATH.joinpath('stm32pio-test-project.ioc').is_file():
    raise FileNotFoundError("No test project is present")
PROJECT_BOARD = 'nucleo_f031k6'

def clean():
    """
    Clean-up the project folder and preserve only an '.ioc' file
    """
    for child in PROJECT_PATH.iterdir():
        if child.name != f"{PROJECT_PATH.name}.ioc":
            if child.is_dir():
                shutil.rmtree(str(child), ignore_errors=True)
            elif child.is_file():
                child.unlink()


class TestUnit(unittest.TestCase):
    """

    """

    def setUp(self) -> None:
        clean()

    def test_generate_code(self):
        """
        Check whether files and folders have been created
        """
        project = stm32pio.util.Stm32pio(PROJECT_PATH)
        project.generate_code()
        # Assuming that the presence of these files indicates a success
        files_should_be_present = [stm32pio.settings.cubemx_script_filename, 'Src/main.c', 'Inc/main.h']
        self.assertEqual([PROJECT_PATH.joinpath(file).is_file() for file in files_should_be_present],
                         [True] * len(files_should_be_present),
                         msg=f"At least one of {files_should_be_present} files haven't been created")

    def test_pio_init(self):
        """
        Consider that existence of 'platformio.ini' file is displaying successful PlatformIO project initialization
        """
        project = stm32pio.util.Stm32pio(PROJECT_PATH)
        project.pio_init(PROJECT_BOARD)
        self.assertTrue(PROJECT_PATH.joinpath('platformio.ini').is_file(), msg="platformio.ini is not there")

    def test_patch_platformio_ini(self):
        """
        Compare contents of the patched string and the desired patch
        """
        project = stm32pio.util.Stm32pio(PROJECT_PATH)
        test_content = "*** TEST PLATFORMIO.INI FILE ***"
        PROJECT_PATH.joinpath('platformio.ini').write_text(test_content)

        project.patch_platformio_ini()

        after_patch_content = PROJECT_PATH.joinpath('platformio.ini').read_text()

        # Initial content wasn't corrupted
        self.assertEqual(after_patch_content[:len(test_content)], test_content,
                         msg="Initial content of platformio.ini is corrupted")
        # Patch content is as expected
        self.assertEqual(after_patch_content[len(test_content):], stm32pio.settings.platformio_ini_patch_content,
                         msg="Patch content is not as expected")

    def test_build_should_raise(self):
        """
        Build an empty project so PlatformIO should return non-zero code and we, in turn, should throw the exception
        """
        project = stm32pio.util.Stm32pio(PROJECT_PATH)
        project.pio_init(PROJECT_BOARD)
        with self.assertRaisesRegex(Exception, "PlatformIO build error",
                                    msg="Build error exception hadn't been raised"):
            project.pio_build()

    def test_run_editor(self):
        """
        Call the editors
        """
        project = stm32pio.util.Stm32pio(PROJECT_PATH)
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
            with self.subTest(command=command, name=name):
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

    def test_file_not_found(self):
        """
        Pass non-existing path and expect the error
        """
        not_existing_path = PROJECT_PATH.joinpath('does_not_exist')
        with self.assertRaises(FileNotFoundError, msg="FileNotFoundError was not raised"):
            stm32pio.util.Stm32pio(not_existing_path)


class TestIntegration(unittest.TestCase):
    """

    """

    def setUp(self) -> None:
        clean()

    def test_build(self):
        """
        Initialize a new project and try to build it
        """
        project = stm32pio.util.Stm32pio(PROJECT_PATH)
        project.generate_code()
        project.pio_init(PROJECT_BOARD)
        project.patch_platformio_ini()

        result = project.pio_build()

        self.assertEqual(result, 0, msg="Build failed")

    def test_regenerate_code(self):
        """
        Simulate new project creation, its changing and CubeMX code re-generation (for example, after adding new
        hardware features and some new files)
        """

        project = stm32pio.util.Stm32pio(PROJECT_PATH)

        # Generate a new project ...
        project.generate_code()
        project.pio_init(PROJECT_BOARD)
        project.patch_platformio_ini()

        # ... change it:
        test_file_1 = PROJECT_PATH.joinpath('Src', 'main.c')
        test_content_1 = "*** TEST STRING 1 ***\n"
        test_file_2 = PROJECT_PATH.joinpath('Inc', 'my_header.h')
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
        clean()

    def test_clean(self):
        """
        Dangerous test actually...
        """

        # Create files and folders
        file_should_be_deleted = PROJECT_PATH.joinpath('file.should.be.deleted')
        dir_should_be_deleted = PROJECT_PATH.joinpath('dir.should.be.deleted')
        file_should_be_deleted.touch(exist_ok=False)
        dir_should_be_deleted.mkdir(exist_ok=False)

        # Clean
        return_code = stm32pio.app.main(sys_argv=['clean', '-d', str(PROJECT_PATH)])
        self.assertEqual(return_code, 0, msg="Non-zero return code")

        # Look for remaining items
        self.assertFalse(file_should_be_deleted.is_file(), msg=f"{file_should_be_deleted} is still there")
        self.assertFalse(dir_should_be_deleted.is_dir(), msg=f"{dir_should_be_deleted} is still there")

        # And .ioc file should be preserved
        self.assertTrue(PROJECT_PATH.joinpath(f"{PROJECT_PATH.name}.ioc").is_file(), msg="Missing .ioc file")

    def test_new(self):
        """
        Successful build is the best indicator that all went right so we use '--with-build' option
        """
        return_code = stm32pio.app.main(sys_argv=['new', '-d', str(PROJECT_PATH), '-b', str(PROJECT_BOARD),
                                                       '--with-build'])
        self.assertEqual(return_code, 0, msg="Non-zero return code")

        # .ioc file should be preserved
        self.assertTrue(PROJECT_PATH.joinpath(f"{PROJECT_PATH.name}.ioc").is_file(), msg="Missing .ioc file")

    def test_generate(self):
        """
        """
        return_code = stm32pio.app.main(sys_argv=['generate', '-d', str(PROJECT_PATH)])
        self.assertEqual(return_code, 0, msg="Non-zero return code")

        inc_dir = 'Inc'
        src_dir = 'Src'

        self.assertTrue(PROJECT_PATH.joinpath(inc_dir).is_dir(), msg=f"Missing '{inc_dir}'")
        self.assertTrue(PROJECT_PATH.joinpath(src_dir).is_dir(), msg=f"Missing '{src_dir}'")
        self.assertFalse(len([child for child in PROJECT_PATH.joinpath(inc_dir).iterdir()]) == 0,
                         msg=f"'{inc_dir}' is empty")
        self.assertFalse(len([child for child in PROJECT_PATH.joinpath(src_dir).iterdir()]) == 0,
                         msg=f"'{src_dir}' is empty")

        # .ioc file should be preserved
        self.assertTrue(PROJECT_PATH.joinpath(f"{PROJECT_PATH.name}.ioc").is_file(), msg="Missing .ioc file")

    def test_incorrect_path(self):
        """
        """
        return_code = stm32pio.app.main(sys_argv=['generate', '-d', '~/path/does/not/exist'])
        self.assertNotEqual(return_code, 0, msg='Return code should be non-zero')

    def test_no_ioc_file(self):
        """
        """

        dir_with_no_ioc_file = PROJECT_PATH.joinpath('dir.with.no.ioc.file')
        dir_with_no_ioc_file.mkdir(exist_ok=False)

        return_code = stm32pio.app.main(sys_argv=['generate', '-d', str(dir_with_no_ioc_file)])
        self.assertNotEqual(return_code, 0, msg='Return code should be non-zero')

    def test_verbose(self):
        """
        Run as subprocess
        """

        stm32pio_exec = inspect.getfile(stm32pio.app)  # get the path to the main stm32pio script
        # Get the path of the current python executable (no need to guess python or python3) (can probably use another
        # approach to retrieve the executable)
        python_exec = sys.executable
        result = subprocess.run([python_exec, stm32pio_exec, '-v', 'clean', '-d', str(PROJECT_PATH)], encoding='utf-8',
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, msg="Non-zero return code")
        # Somehow stderr contains actual output
        self.assertIn('DEBUG', result.stderr.split(), msg="Verbose logging output has not been enabled")


def tearDownModule():
    """
    Clean up after yourself
    """
    clean()


if __name__ == '__main__':
    unittest.main()
