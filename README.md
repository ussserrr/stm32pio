# stm32pio
Small Python app that can create and update [PlatformIO](https://platformio.org) project from [STM32CubeMX](http://www.st.com/en/development-tools/stm32cubemx.html) `.ioc` file.

## Features
  - Start new project in a single directory using only `.ioc` file
  - Update existing project to add/change hardware options from CubeMX
  - *[optional]* Automatically run your favorite editor in the end

## Requirements:
  - For this app:
    - Python 3.5+
  - For usage:
    - macOS or Linux OS
    - STM32CubeMX (all recent versions)
    - Java CLI (probably already installed for STM32CubeMX)
    - PlatformIO CLI (if using from IDE (for example, Atom), run (macOS and Linux) `Menubar -> PlatformIO -> Install Shell Commands`). Therefore, currently stm32pio doesn't support Windows due to the lack of PlatformIO CLI.

## Usage
Run
```sh
$ python3 stm32pio.py --help
```
to see help.

## Example
1. Run CubeMX, choose MCU/board, do all necessary stuff
2. Open `Project -> Settings` menu, set Project Name, choose Other Toolchains (GPDSC). In Code Generator tab check "Copy only the necessary library files" and "Generate periphery initialization as a pair of '.c/.h' files per peripheral"
3. Back in the first tab (Project) copy the "Toolchain Folder Location" string. Click OK
4. Use copied string as a `-d` argument for stm32pio
5. Run `pio boards` to list all supported devices. Pick one and use its ID as a `-b` argument (for example, `nucleo_f031k6`)
6. All done. You can now run
```sh
$ python3 stm32pio.py new -d /path/to/cubemx/project -b nucleo_f031k6 --start-editor=vscode
```
to complete generation.
