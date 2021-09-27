import configparser
import gc

# Provides test constants and definitions
from tests.common import *

import stm32pio.core.settings
import stm32pio.core.project
import stm32pio.core.state


class TestIntegration(CustomTestCase):
    """
    Sequence of methods that should work seamlessly
    """

    def test_rebase_project(self):
        """
        Test the portability of projects: they should stay totally valid after moving to another path (same as renaming
        the parent part of the path). If we will not meet any exceptions, we should consider the test passed
        """
        project_before = stm32pio.core.project.Stm32pio(STAGE_PATH, parameters={'project': {'board': PROJECT_BOARD}})
        project_before.save_config()

        new_path = project_before.path.with_name(project_before.path.name + '-moved')
        shutil.move(project_before.path, new_path)

        project_after = stm32pio.core.project.Stm32pio(new_path, parameters={'project': {'board': PROJECT_BOARD}})
        self.assertEqual(project_after.generate_code(), 0)
        self.assertEqual(project_after.pio_init(), 0)
        self.assertEqual(project_after.patch(), None)
        self.assertEqual(project_after.build(), 0)

    def test_config_priorities(self):
        """
        Test the compliance with the priorities when reading the parameters
        """
        # Sample user's custom patch value
        config_parameter_user_value = inspect.cleandoc('''
            [test_section]
            key1 = value1
            key2 = 789
        ''')
        cli_parameter_user_value = 'nucleo_f429zi'

        # Create test config, ...
        config = configparser.ConfigParser(interpolation=None)
        config.read_dict({
            'project': {
                'platformio_ini_patch_content': config_parameter_user_value,
                'board': PROJECT_BOARD
            }
        })
        # ... save it
        with STAGE_PATH.joinpath(stm32pio.core.settings.config_file_name).open(mode='w') as config_file:
            config.write(config_file)

        # On project creation we should interpret the CLI-provided values as superseding to the saved ones and
        # saved ones, in turn, as superseding to the default ones (BUT only non-empty values)
        project = stm32pio.core.project.Stm32pio(STAGE_PATH, save_on_destruction=True, parameters={
            'app': {
                'cubemx_cmd': ''
            },
            'project': {
                'board': cli_parameter_user_value
            }
        })
        # Side-effect "test": the project should be destroyed immediately and its config should be saved during this
        del project
        gc.collect()

        # Parse the resulting stm32pio.ini via the configparser to see
        saved_config = configparser.ConfigParser(interpolation=None)
        saved_config.read(STAGE_PATH.joinpath(stm32pio.core.settings.config_file_name))

        with self.subTest(msg="User's .INI parameter has not been prioritized over the default one"):
            self.assertEqual(config_parameter_user_value,
                             saved_config.get('project', 'platformio_ini_patch_content'))
        with self.subTest(msg="User's CLI parameter has not been prioritized over the .INI one"):
            self.assertEqual(cli_parameter_user_value, saved_config.get('project', 'board'))
        with self.subTest(msg="Empty parameter has overwrite the non-empty one"):
            self.assertNotEqual('', saved_config.get('app', 'cubemx_cmd'))

    def test_build(self):
        """
        Initialize a new project and try to build it
        """
        project = stm32pio.core.project.Stm32pio(STAGE_PATH, parameters={'project': {'board': PROJECT_BOARD}})
        project.generate_code()
        project.pio_init()
        project.patch()

        self.assertEqual(project.build(), 0, msg="Build failed")

    def test_regenerate_code(self):
        """
        Simulate a new project creation, its changing and CubeMX code re-generation (for example, after adding new
        hardware features and some new files by a user)
        """
        project = stm32pio.core.project.Stm32pio(STAGE_PATH, parameters={'project': {'board': PROJECT_BOARD}})

        # Generate a new project ...
        project.generate_code()
        project.pio_init()
        project.patch()

        # ... change it:
        test_file_1 = STAGE_PATH.joinpath('Src', 'main.c')
        test_content_1 = "*** TEST STRING 1 ***\n"
        test_file_2 = STAGE_PATH.joinpath('Inc', 'my_header.h')
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

        project = stm32pio.core.project.Stm32pio(STAGE_PATH, parameters={'project': {'board': PROJECT_BOARD}})

        for method, expected_stage in [(None, stm32pio.core.state.ProjectStage.EMPTY),
                                       ('save_config', stm32pio.core.state.ProjectStage.INITIALIZED),
                                       ('generate_code', stm32pio.core.state.ProjectStage.GENERATED),
                                       ('pio_init', stm32pio.core.state.ProjectStage.PIO_INITIALIZED),
                                       ('patch', stm32pio.core.state.ProjectStage.PATCHED),
                                       ('build', stm32pio.core.state.ProjectStage.BUILT),
                                       ('clean', stm32pio.core.state.ProjectStage.EMPTY),
                                       ('pio_init', stm32pio.core.state.ProjectStage.UNDEFINED)]:
            if method is not None:
                getattr(project, method)()
            self.assertEqual(project.state.current_stage, expected_stage)
            if expected_stage != stm32pio.core.state.ProjectStage.UNDEFINED:
                self.assertTrue(project.state.is_consistent)
            else:
                # Should be UNDEFINED when the project is messed up (pio_init() after clean())
                self.assertFalse(project.state.is_consistent)

    def test_users_files_preservation(self):
        """
        Check that custom user's files and folders will remain untouched throughout all the steps of the project
        """

        users_file = STAGE_PATH.joinpath('some_users_file.txt')
        users_file_content = "Sample content that any human can put into a text file"
        users_file.write_text(users_file_content)
        users_dir = STAGE_PATH.joinpath('some_users_directory')
        users_dir.mkdir()

        def check_preservation():
            self.assertTrue(all(item in STAGE_PATH.iterdir() for item in [users_file, users_dir]))
            self.assertIn(users_file_content, users_file.read_text())

        project = stm32pio.core.project.Stm32pio(STAGE_PATH, parameters={'project': {'board': PROJECT_BOARD}})

        for method in ['save_config', 'generate_code', 'pio_init', 'patch', 'build']:
            getattr(project, method)()
            check_preservation()
