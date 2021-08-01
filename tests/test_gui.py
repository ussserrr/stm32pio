import platform

# Provides test constants and definitions
from tests.common import *


try:
    import PySide2
    pyside_is_present = True
except ImportError:
    pyside_is_present = False


@unittest.skipIf(not pyside_is_present, "no PySide2 found")
class TestGUI(CustomTestCase):
    def test_imports(self):
        import stm32pio.gui.app
