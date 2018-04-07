import unittest, os, shutil
import settings
from miscs import generate_code, pio_init, patch_platformio_ini, start_editor, clean

if settings.myOS in ['Darwin', 'Linux']:
    path = os.path.dirname(os.path.abspath(__file__)) + '/stm32pio-test'
# Windows not implemented yet
elif settings.myOS == 'Windows':
    path = '?'

board = 'nucleo_f031k6'



class Test(unittest.TestCase):

    def test_generate_code(self):
        """
        Check whether files and folders were created
        """

        generate_code(path)
        self.assertEqual( [os.path.isfile(path+'/'+settings.cubemxScriptFilename),
                           os.path.isdir(path+'/Src'),
                           os.path.isdir(path+'/Inc')],
                          [True, True, True],
                          msg="{cubemxScriptFilename}, /Inc, /Src weren't created"\
                          .format(cubemxScriptFilename=settings.cubemxScriptFilename) )


    def test_pio_init(self):
        """
        Consider that existence of 'platformio.ini' file is displaying successful
        PlatformIO project initialization
        """

        pio_init(path, board)
        self.assertTrue( os.path.isfile(path+'/platformio.ini'),
                         msg='platformio.ini is not here' )


    def test_patch_platformio_ini(self):
        """
        Compare contents of the patched string and the desired patch
        """

        platformioIni = open(path+'/platformio.ini', mode='w')
        platformioIni.write('*** TEST PLATFORMIO.INI FILE ***')
        platformioIni.close()

        patch_platformio_ini(path)

        platformioIni = open(path+'/platformio.ini', mode='rb')
        platformioIni.seek(-len(settings.platformioIniPatch), 2)
        platformioIniPatchedStr = platformioIni.read(len(settings.platformioIniPatch))\
                                                   .decode('utf-8')
        platformioIni.close()
        os.remove(path + '/platformio.ini')

        self.assertEqual(platformioIniPatchedStr, settings.platformioIniPatch,
                         msg="'platformio.ini' patching error")



if __name__ == '__main__':
    clean(path)
    unittest.main(exit=False)
    clean(path)
