import configparser
import inspect
import shutil

import stm32pio.lib
import stm32pio.settings

# Provides test constants
from tests.test import *


class TestIntegration(CustomTestCase):
    """
    Sequence of methods that should work seamlessly
    """

    def test_rebase_project(self):
        """
        Test the portability of projects: they should stay totally valid after moving to another path (same as renaming
        the parent part of the path). If we will not meet any exceptions, we should consider the test passed.
        """
        project_before = stm32pio.lib.Stm32pio(FIXTURE_PATH, parameters={'project': {'board': TEST_PROJECT_BOARD}})
        project_before.save_config()

        new_path = f'{project_before.path}-moved'
        shutil.move(str(project_before.path), new_path)

        project_after = stm32pio.lib.Stm32pio(new_path, parameters={'project': {'board': TEST_PROJECT_BOARD}})
        project_after.generate_code()
        project_after.pio_init()
        project_after.patch()
        project_after.build()

    def test_config_priorities(self):
        """
        Test the compliance with priorities when reading the parameters
        """
        # Sample user's custom patch value
        config_parameter_user_value = inspect.cleandoc('''
            [test_section]
            key1 = value1
            key2 = 789
        ''')
        cli_parameter_user_value = 'nucleo_f429zi'

        # Create test config
        config = configparser.ConfigParser(interpolation=None)
        config.read_dict({
            'project': {
                'platformio_ini_patch_content': config_parameter_user_value,
                'board': TEST_PROJECT_BOARD
            }
        })
        # ... save it
        with FIXTURE_PATH.joinpath(stm32pio.settings.config_file_name).open(mode='w') as config_file:
            config.write(config_file)

        # On project creation we should interpret the CLI-provided values as superseding to the saved ones and
        # saved ones, in turn, as superseding to the default ones
        project = stm32pio.lib.Stm32pio(FIXTURE_PATH, parameters={'project': {'board': cli_parameter_user_value}})
        project.pio_init()
        project.patch()

        # Actually, we can parse platformio.ini via configparser but this is simpler in our case
        after_patch_content = FIXTURE_PATH.joinpath('platformio.ini').read_text()
        self.assertIn(config_parameter_user_value, after_patch_content,
                      msg="User config parameter has not been prioritized over the default one")
        self.assertIn(cli_parameter_user_value, after_patch_content,
                      msg="User CLI parameter has not been prioritized over the saved one")

    def test_build(self):
        """
        Initialize a new project and try to build it
        """
        project = stm32pio.lib.Stm32pio(FIXTURE_PATH, parameters={'project': {'board': TEST_PROJECT_BOARD}})
        project.generate_code()
        project.pio_init()
        project.patch()

        result = project.build()

        self.assertEqual(result, 0, msg="Build failed")

    def test_regenerate_code(self):
        """
        Simulate a new project creation, its changing and CubeMX code re-generation (for example, after adding new
        hardware features and some new files by a user)
        """
        project = stm32pio.lib.Stm32pio(FIXTURE_PATH, parameters={'project': {'board': TEST_PROJECT_BOARD}})

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

        # Check if added information has been preserved
        for test_content, after_regenerate_content in [(test_content_1, test_file_1.read_text()),
                                                       (test_content_2, test_file_2.read_text())]:
            with self.subTest(msg=f"User content hasn't been preserved in {after_regenerate_content}"):
                self.assertIn(test_content, after_regenerate_content)

    def test_current_stage(self):
        """
        Go through the sequence of states emulating the real-life project lifecycle
        """
        project = stm32pio.lib.Stm32pio(FIXTURE_PATH, parameters={'project': {'board': TEST_PROJECT_BOARD}})
        self.assertEqual(project.state.current_stage, stm32pio.lib.ProjectStage.EMPTY)

        project.save_config()
        self.assertEqual(project.state.current_stage, stm32pio.lib.ProjectStage.INITIALIZED)

        project.generate_code()
        self.assertEqual(project.state.current_stage, stm32pio.lib.ProjectStage.GENERATED)

        project.pio_init()
        self.assertEqual(project.state.current_stage, stm32pio.lib.ProjectStage.PIO_INITIALIZED)

        project.patch()
        self.assertEqual(project.state.current_stage, stm32pio.lib.ProjectStage.PATCHED)

        project.build()
        self.assertEqual(project.state.current_stage, stm32pio.lib.ProjectStage.BUILT)

        project.clean()
        self.assertEqual(project.state.current_stage, stm32pio.lib.ProjectStage.EMPTY)

        # Should be UNDEFINED when the project is messed up
        project.pio_init()
        self.assertEqual(project.state.current_stage, stm32pio.lib.ProjectStage.UNDEFINED)
        self.assertFalse(project.state.is_consistent)
