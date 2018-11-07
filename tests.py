#!/usr/bin/env python3


import os
import subprocess
import time
import unittest

import settings
import util


project_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stm32pio-test')
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
        self.assertEqual([os.path.isfile(os.path.join(project_path, settings.cubemx_script_filename)),
                          os.path.isdir(os.path.join(project_path, 'Src')),
                          os.path.isdir(os.path.join(project_path, 'Inc'))],
                         [True, True, True],
                         msg=f"{settings.cubemx_script_filename}, /Inc, /Src haven't been created")


    @clean_run
    def test_pio_init(self):
        """
        Consider that existence of 'platformio.ini' file is displaying successful PlatformIO project initialization
        """

        util.pio_init(project_path, board)
        self.assertTrue(os.path.isfile(os.path.join(project_path, 'platformio.ini')), msg="platformio.ini is not here")


    @clean_run
    def test_patch_platformio_ini(self):
        """
        Compare contents of the patched string and the desired patch
        """

        with open(os.path.join(project_path, 'platformio.ini'), mode='w') as platformio_ini:
            platformio_ini.write("*** TEST PLATFORMIO.INI FILE ***")

        util.patch_platformio_ini(project_path)

        with open(os.path.join(project_path, 'platformio.ini'), mode='rb') as platformio_ini:
            # '2' in seek() means that we count from the end of the file. This feature works only in binary file mode
            # In Windows additional '\r' is appended to every '\n' (newline differences) so we need to count them
            # for the correct calculation
            if settings.my_os == 'Windows':
                platformio_ini.seek(-(len(settings.platformio_ini_patch_text) +
                                      settings.platformio_ini_patch_text.count('\n')), 2)
                platformio_ini_patched_str = platformio_ini.read(len(settings.platformio_ini_patch_text) +
                                                                 settings.platformio_ini_patch_text.count('\n'))
                platformio_ini_patched_str = platformio_ini_patched_str.replace(b'\r', b'').decode('utf-8')
            else:
                platformio_ini.seek(-len(settings.platformio_ini_patch_text), 2)
                platformio_ini_patched_str = platformio_ini.read(
                    len(settings.platformio_ini_patch_text)).decode('utf-8')

        self.assertEqual(platformio_ini_patched_str, settings.platformio_ini_patch_text,
                         msg="'platformio.ini' patching error")


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
        util.start_editor(project_path, 'vscode')
        util.start_editor(project_path, 'sublime')
        util.start_editor(project_path, 'gedit')
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
                self.assertIn('gedit', result.stdout)



    @clean_run
    def test_regenerate_code(self):
        """
        Simulate new project creation, its changing and CubeMX regeneration (for example, after adding new hardware
        and some new files)
        """

        # Generate a new project
        util.generate_code(project_path)
        util.pio_init(project_path, board)
        util.patch_platformio_ini(project_path)

        # Change it:
        #   - add some sample string inside CubeMX' /* BEGIN - END */ block
        with open(os.path.join(project_path, 'Src', 'main.c'), mode='r+') as main_c:
            main_c_content = main_c.read()
            pos = main_c_content.index("while (1)")
            main_c_new_content = main_c_content[:pos] + "*** TEST STRING 1 ***\n" + main_c_content[pos:]
            main_c.seek(0)
            main_c.truncate()
            main_c.write(main_c_new_content)
        #  - add new file inside the project
        with open(os.path.join(project_path, 'Inc', 'my_header.h'), mode='w') as my_header_h:
            my_header_h.write("*** TEST STRING 2 ***\n")

        # Regenerate CubeMX project
        util.generate_code(project_path)

        # Check if added information is preserved
        with open(os.path.join(project_path, 'Src', 'main.c'), mode='r') as main_c:
            self.assertIn("*** TEST STRING 1 ***", main_c.read())
        with open(os.path.join(project_path, 'Inc', 'my_header.h'), mode='r') as my_header_h:
            self.assertIn("*** TEST STRING 2 ***", my_header_h.read())



if __name__ == '__main__':
    unittest.main(exit=False)
    util.clean(project_path)
