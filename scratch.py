import stm32pio.lib
import io

project = stm32pio.lib.Stm32pio('/stm32pio-test-project',
                                parameters={'board': 'nucleo_f031k6'},
                                save_on_destruction=False)

# project.generate_code()
project.pio_init()
platformio_ini_patched = project.patch()
str_stream = io.StringIO()
platformio_ini_patched.write(str_stream)
# with project.project_path.joinpath('platformio2.ini').open(mode='w') as config_file:
#     platformio_ini_patched.write(config_file)

import difflib

with open(str(project.project_path.joinpath('platformio.ini'))) as platformio_ini_file:
    a = platformio_ini_file.read()
    # with open(str(project.project_path.joinpath('platformio2.ini'))) as platformio_ini_patched:
    b = str_stream.getvalue()
    s = difflib.SequenceMatcher(a=a, b=b)
    for tag, i1, i2, j1, j2 in s.get_opcodes():
        print('{:7}   a[{}:{}] --> b[{}:{}] {!r:>8} --> {!r}'.format(
            tag, i1, i2, j1, j2, a[i1:i2], b[j1:j2]))
