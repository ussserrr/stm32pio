import sys

try:
    import stm32pio.cli.app
except ModuleNotFoundError:
    import pathlib
    sys.path.append(str(pathlib.Path(__file__).parent.parent))  # hack to run the app as 'python __main__.py'
    import stm32pio.cli.app


if __name__ == '__main__':
    sys.exit(stm32pio.cli.app.main())
