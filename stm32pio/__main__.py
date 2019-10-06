import sys
import pathlib

import stm32pio.stm32pio

if __name__ == '__main__':
    sys.path.insert(0, str(pathlib.Path(sys.path[0]).parent))  # hack to be able to run the app as 'python3 stm32pio.py'
    sys.exit(stm32pio.stm32pio.main())
