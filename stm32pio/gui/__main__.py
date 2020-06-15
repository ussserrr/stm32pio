import sys

try:
    import stm32pio.gui.app
except ModuleNotFoundError:
    import pathlib
    sys.path.append(str(pathlib.Path(sys.path[0]).parent.parent))  # hack to run the app as 'python __main__.py'
    import stm32pio.gui.app


if __name__ == '__main__':
    sys.exit(stm32pio.gui.app.main())
