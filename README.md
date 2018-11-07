# stm32pio
Small cross-platform Python app that can create and update [PlatformIO](https://platformio.org) projects from [STM32CubeMX](http://www.st.com/en/development-tools/stm32cubemx.html) `.ioc` files.

## Features
  - Start the new project in a single directory using only `.ioc` file
  - Update existing project after adding/changing hardware options from CubeMX
  - Clean-up the project
  - *[optional]* Automatically run your favorite editor in the end

## Requirements:
  - For this app:
    - Python 3.6+
  - For usage:
    - macOS, Linux, Windows
    - STM32CubeMX (all recent versions) with downloaded necessary frameworks (F0, F1, etc.). Try to generate code in ordinary way (through the GUI) at least once before running stm32pio
    - Java CLI (JRE) (likely is already installed if STM32CubeMX works)
    - PlatformIO CLI.

## Usage
Check `settings.py` to make sure that all user-specific parameters are valid. Run
```bash
$ python3 stm32pio.py --help
```
to see help.

## Example
1. Run CubeMX, choose MCU/board, do all necessary stuff
2. Open `Project -> Settings` menu, specify Project Name, choose Other Toolchains (GPDSC). In Code Generator tab check "Copy only the necessary library files" and "Generate periphery initialization as a pair of '.c/.h' files per peripheral" options

![Code Generator tab](/screenshots/tab_CodeGenerator.png)

3. Back in the first tab (Project) copy the "Toolchain Folder Location" string. Click OK, close CubeMX

![Project tab](/screenshots/tab_Project.png)

4. Use copied string as a `-d` argument for stm32pio. So it is assumed that the name of the project folder matches the name of `.ioc` file
5. Run `platformio boards` (`pio boards`) to list all supported devices. Pick one and use its ID as a `-b` argument (for example, `nucleo_f031k6`)
6. All done. You can now run
```bash
$ python3 stm32pio.py new -d /path/to/cubemx/project -b nucleo_f031k6 --start-editor=vscode
```
to complete generation and start the Visual Studio Code editor with opened folder (as example, not required). Make sure you have all tools in PATH (`java` (or set in `settings.py`), editor, Python)
7. If you will be in need to update hardware configuration in the future, make all necessary stuff in CubeMX and run `generate` command in a similar way:
```bash
$ python3 stm32pio.py generate -d /path/to/cubemx/project
```
8. To clean-up the folder and keep only `.ioc` file run `clean` command

## Testing
Since ver. 0.45 there are some unit-tests in file `tests.py` (based on the unittest module). Run
```bash
$ python3 tests.py -v
```
to test the app. It uses STM32F0 framework to generate code from `./stm32pio-test/stm32pio-test.ioc` file.
