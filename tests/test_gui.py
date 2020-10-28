import platform

# Provides test constants and definitions
from tests.common import *


class TestGUI(CustomTestCase):
    def test_imports(self):
        import stm32pio.gui.app

    @unittest.skipIf(platform.system() == 'Linux', "works unstable under Linux")
    def test_starts(self):
        import stm32pio.gui.app

        successful_loading_flag = False

        def on_loaded(_: str, success: bool):
            nonlocal successful_loading_flag
            successful_loading_flag = success
            projects_list = app.findChildren(stm32pio.gui.app.ProjectsList)[0]
            projects_list.removeProject(0)
            app.quit()

        # TODO: this will create and use QSettings, probably should use local storage (not OS-level one)
        app = stm32pio.gui.app.main(sys_argv=['--directory', str(PROJECT_PATH)])
        app.loaded.connect(on_loaded)
        app.exec_()

        self.assertTrue(successful_loading_flag)
