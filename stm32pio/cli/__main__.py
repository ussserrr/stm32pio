import pathlib
import sys

MODULE_PATH = pathlib.Path(__file__).parent  # module path, e.g. root/stm32pio/cli/
ROOT_PATH = MODULE_PATH.parent.parent  # repo's or the site-package's entry root
try:
    import stm32pio.cli.app
except ModuleNotFoundError:
    sys.path.append(str(ROOT_PATH))  # hack to run the app as 'python path/to/__main__.py'
    import stm32pio.cli.app


if __name__ == '__main__':
    sys.exit(stm32pio.cli.app.main())
