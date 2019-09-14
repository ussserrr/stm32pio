#!/usr/bin/env python3


import os
import pathlib
import subprocess
import time
import unittest

import settings
import util


project_path = pathlib.Path('stm32pio/tests/stm32pio-test-project').resolve()
board = 'nucleo_f031k6'



def clean_run(test):
    def wrapper(self):
        util.clean(project_path)
        return test(self)
    return wrapper



class Test(unittest.TestCase):

    @clean_run
    def test_generate_code(self):
        """
        Check whether files and folders have been created
        """

        util.generate_code(project_path)
        # Assuming that the presence of these files indicates a success
        files_should_be_present = [settings.cubemx_script_filename, 'Src/main.c', 'Inc/main.h']
        self.assertEqual([project_path.joinpath(file).is_file() for file in files_should_be_present],
                         [True] * len(files_should_be_present),
                         msg=f"At least one of {files_should_be_present} files haven't been created")


    @clean_run
    def test_pio_init(self):
        """
        Consider that existence of 'platformio.ini' file is displaying successful PlatformIO project initialization
        """

        util.pio_init(project_path, board)
        self.assertTrue(project_path.joinpath('platformio.ini').is_file(), msg="platformio.ini is not there")
        with self.assertRaisesRegex(Exception, "PlatformIO build error",
                                    msg='Exception("PlatformIO build error") was not raised'):
            util.pio_build(project_path)


    @clean_run
    def test_patch_platformio_ini(self):
        """
        Compare contents of the patched string and the desired patch
        """

        test_content = "*** TEST PLATFORMIO.INI FILE ***"
        project_path.joinpath('platformio.ini').write_text(test_content)

        util.patch_platformio_ini(project_path)

        after_patch_content = project_path.joinpath('platformio.ini').read_text()

        # Initial content wasn't corrupted
        self.assertEqual(after_patch_content[:len(test_content)], test_content,
                         msg="Initial content of platformio.ini is corrupted")
        # Patch content is as expected
        self.assertEqual(after_patch_content[len(test_content):], settings.platformio_ini_patch_content,
                         msg="patch content is not as expected")


    @clean_run
    def test_build(self):
        """
        Initialize a new project and try to build it
        """

        util.generate_code(project_path)
        util.pio_init(project_path, board)
        util.patch_platformio_ini(project_path)

        result = subprocess.run(['platformio', 'run'],
                                cwd=project_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Or, for Python 3.7 and above:
        # result = subprocess.run(['platformio', 'run'], cwd=project_path, capture_output=True)

        self.assertEqual(result.returncode, 0, msg="build failed")


    def test_run_editor(self):
        """
        Call editors
        """

        util.start_editor(project_path, 'atom')
        util.start_editor(project_path, 'code')
        util.start_editor(project_path, 'subl')
        time.sleep(1)  # wait a little bit for apps to start

        if settings.my_os == 'Windows':
            result = subprocess.run(['wmic', 'process', 'get', 'description'],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            self.assertIn('atom.exe', result.stdout)
            self.assertIn('Code.exe', result.stdout)
            self.assertIn('sublime_text.exe', result.stdout)
        else:
            result = subprocess.run(['ps', '-A'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')
            # Or, for Python 3.7 and above:
            # result = subprocess.run(['ps', '-A'], capture_output=True, encoding='utf-8')
            if settings.my_os == 'Darwin':
                self.assertIn('Atom', result.stdout)
                self.assertIn('Visual Studio Code', result.stdout)
                self.assertIn('Sublime', result.stdout)
            if settings.my_os == 'Linux':
                self.assertIn('atom', result.stdout)
                self.assertIn('code', result.stdout)
                self.assertIn('sublime', result.stdout)


    @clean_run
    def test_regenerate_code(self):
        """
        Simulate new project creation, its changing and CubeMX regeneration (for example, after adding new hardware
        and some new files)
        """

        # Generate a new project ...
        util.generate_code(project_path)
        util.pio_init(project_path, board)
        util.patch_platformio_ini(project_path)

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

        # Regenerate CubeMX project
        util.generate_code(project_path)

        # Check if added information is preserved
        main_c_after_regenerate_content = test_file_1.read_text()
        my_header_h_after_regenerate_content = test_file_2.read_text()
        self.assertIn(test_content_1, main_c_after_regenerate_content,
                      msg=f"{test_file_1} does not preserve user content after regeneration")
        self.assertIn(test_content_2, my_header_h_after_regenerate_content,
                      msg=f"{test_file_2} does not preserve user content after regeneration")


    def test_file_not_found(self):
        """

        """
        not_existing_path = project_path.joinpath('does_not_exist')
        with self.assertRaises(FileNotFoundError, msg="FileNotFoundError was not raised"):
            util._get_project_path(not_existing_path)


def tearDownModule():
    util.clean(project_path)


if __name__ == '__main__':
    unittest.main(exit=False)
    util.clean(project_path)
