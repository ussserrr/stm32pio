import unittest, os, shutil
import settings
from miscs import generate_code, pio_init, patch_platformio_ini, start_editor, clean

if settings.myOS == 'Darwin':
    path = settings.homeDir + '/Documents/STM32/stm32pio-test'
elif settings.myOS == 'Linux':
    path = settings.homeDir + '/Documents/CubeMX/stm32pio-test'
elif settings.myOS == 'Windows':
    path = '?'

board = 'nucleo_f031k6'



class Test(unittest.TestCase):

    def test_generate_code(self):
        generate_code(path)
        self.assertEqual( [os.path.isfile(path+'/'+settings.cubemxScriptFilename),
                           os.path.isdir(path+'/Src'),
                           os.path.isdir(path+'/Inc')],
                          [True, True, True],
                          msg="{cubemxScriptFilename}, /Inc, /Src weren't created"\
                          .format(cubemxScriptFilename=settings.cubemxScriptFilename) )


    def test_pio_init(self):
        pio_init(path, board)
        self.assertTrue( os.path.isfile(path+'/platformio.ini'),
                         msg='platformio.ini is not here' )


    def test_patch_platformio_ini(self):
        platformio_ini = open(path+'/platformio.ini', mode='w')
        platformio_ini.write('*** TEST PLATFORMIO.INI FILE ***')
        platformio_ini.close()

        patch_platformio_ini(path)

        platformio_ini = open(path+'/platformio.ini', mode='rb')
        platformio_ini.seek(-len(settings.platformio_ini_patch), 2)
        platformio_ini_patched_str = platformio_ini.read(len(settings.platformio_ini_patch))\
                                                   .decode('utf-8')
        platformio_ini.close()
        os.remove(path + '/platformio.ini')

        self.assertEqual(platformio_ini_patched_str, settings.platformio_ini_patch,
                         msg="'platformio.ini' patching error")



if __name__ == '__main__':
    clean(path)
    unittest.main(exit=False)
    clean(path)
