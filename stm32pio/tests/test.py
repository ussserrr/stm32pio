import pathlib
import platform
import shutil
import subprocess
import time
import unittest

import stm32pio.settings
import stm32pio.util


# Test data
project_path = pathlib.Path('stm32pio/tests/stm32pio-test-project').resolve()
if not project_path.is_dir() and not project_path.joinpath('stm32pio-test-project.ioc').is_file():
    raise FileNotFoundError("No test project is present")
board = 'nucleo_f031k6'

def clean():
    """
    Clean-up the project folder and preserve only an '.ioc' file
    """
    for child in project_path.iterdir():
        if child.name != f"{project_path.name}.ioc":
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
        project = stm32pio.util.Stm32pio(project_path)
        project.generate_code()
        # Assuming that the presence of these files indicates a success
        files_should_be_present = [stm32pio.settings.cubemx_script_filename, 'Src/main.c', 'Inc/main.h']
        self.assertEqual([project_path.joinpath(file).is_file() for file in files_should_be_present],
                         [True] * len(files_should_be_present),
                         msg=f"At least one of {files_should_be_present} files haven't been created")


    def test_pio_init(self):
        """
        Consider that existence of 'platformio.ini' file is displaying successful PlatformIO project initialization
        """
        project = stm32pio.util.Stm32pio(project_path)
        project.pio_init(board)
        self.assertTrue(project_path.joinpath('platformio.ini').is_file(), msg="platformio.ini is not there")


    def test_patch_platformio_ini(self):
        """
        Compare contents of the patched string and the desired patch
        """
        project = stm32pio.util.Stm32pio(project_path)
        test_content = "*** TEST PLATFORMIO.INI FILE ***"
        project_path.joinpath('platformio.ini').write_text(test_content)

        project.patch_platformio_ini()

        after_patch_content = project_path.joinpath('platformio.ini').read_text()

        # Initial content wasn't corrupted
        self.assertEqual(after_patch_content[:len(test_content)], test_content,
                         msg="Initial content of platformio.ini is corrupted")
        # Patch content is as expected
        self.assertEqual(after_patch_content[len(test_content):], stm32pio.settings.platformio_ini_patch_content,
                         msg="patch content is not as expected")


    def test_build_should_raise(self):
        """
        Build an empty project so PlatformIO should return non-zero code and we, in turn, should throw the exception
        """
        project = stm32pio.util.Stm32pio(project_path)
        project.pio_init(board)
        with self.assertRaisesRegex(Exception, "PlatformIO build error",
                                    msg="Build error exception hadn't been raised"):
            project.pio_build()


    def test_run_editor(self):
        """
        Call the editors
        """
        project = stm32pio.util.Stm32pio(project_path)
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
        not_existing_path = project_path.joinpath('does_not_exist')
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
        project = stm32pio.util.Stm32pio(project_path)
        project.generate_code()
        project.pio_init(board)
        project.patch_platformio_ini()

        result = project.pio_build()

        self.assertEqual(result, 0, msg="Build failed")


    def test_regenerate_code(self):
        """
        Simulate new project creation, its changing and CubeMX code re-generation (for example, after adding new
        hardware features and some new files)
        """

        project = stm32pio.util.Stm32pio(project_path)

        # Generate a new project ...
        project.generate_code()
        project.pio_init(board)
        project.patch_platformio_ini()

        # ... change it:
        test_file_1 = project_path.joinpath('Src', 'main.c')
        test_content_1 = "*** TEST STRING 1 ***\n"
        test_file_2 = project_path.joinpath('Inc', 'my_header.h')
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
                      msg=f"{test_file_1} does not preserve user content after regeneration")
        self.assertIn(test_content_2, my_header_h_after_regenerate_content,
                      msg=f"{test_file_2} does not preserve user content after regeneration")



class TestCLI(unittest.TestCase):
    """

    """

    def setUp(self) -> None:
        clean()

    def test_new(self):
        pass

    def test_generate(self):
        pass

    def clean(self):
        pass



def tearDownModule():
    """
    Clean up after yourself
    """
    clean()



if __name__ == '__main__':
    unittest.main()
