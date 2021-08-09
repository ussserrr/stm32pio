# stm32pio

[![Build Status](https://dev.azure.com/andrei42008/stm32pio/_apis/build/status/ussserrr.stm32pio?branchName=master)](https://dev.azure.com/andrei42008/stm32pio/_build/latest?definitionId=1&branchName=master)

Small cross-platform Python app that can create and update [PlatformIO](https://platformio.org) projects from [STM32CubeMX](https://www.st.com/en/development-tools/stm32cubemx.html) `.ioc` files.

It uses the STM32CubeMX to generate a HAL-framework-based code and alongside creates the PlatformIO project with compatible parameters to bind them both together.

The [GUI version](/docs/GUI/README.md) is available, too (but read this main introduction first, please).

![Logo](/logo/logo.png)


## Table of contents
> - [Features](#features)
> - [Requirements](#requirements)
> - [Installation](#installation)
> - [Usage](#usage)
> - [Troubleshooting](#troubleshooting)
> - [Restrictions](#restrictions)


## Features
  - Originate the new full-fledged project in a single directory starting only from an `.ioc` file
  - Seamlessly update an existing project after the hardware changes by CubeMX
  - Quickly check the current state
  - Inspect tools (CubeMX, PlatformIO, etc.)
  - Clean-up the project
  - *[optional]* Automatically run your favorite editor or initiate a build in the end
  - *[optional]* GUI edition (see [the dedicated README](/docs/GUI/README.md) file) (please, read this main introduction first)


## Requirements:
**OS:** macOS, Linux, Windows 7-10

**Python:** 3.6+

The app introduces zero dependencies by itself. Of course, you need to have all the necessary tools installed in order to perform the operations:
  - STM32CubeMX with the desired downloaded frameworks (F0, F1, etc.). All recent versions are fine (5.x, 6.x)
  - Java (JRE, Java runtime environment) for the CubeMX. Starting from CubeMX v6.3.0 Java is included in the bundle (in form of a `jre` folder sitting alongside the executable) so you don't need to install it by yourself from now on. Hence, it can be omitted in the `stm32pio.ini` config file **except Windows** where it is still **highly recommended** to run CubeMX via `java.exe`. As mentioned, Java exists already, the only difference is that it is still will be listed in the default `stm32pio.ini` config. You can refer to STM32CubeMX own documentation to obtain more information on current situation if, suddenly, something will change in this regard
  - PlatformIO (4.2.0 and above) CLI (most likely is already present if you have installed it via some package manager (`pip`, `apt`, `brew`, etc.) or need to be installed as a "command line extension" from the PlatformIO IDE (see its [docs](https://docs.platformio.org/en/latest/core/installation.html#piocore-install-shell-commands) for more information))

If you, for some reasons, don't want to (or cannot) install (i.e. register in PATH) command line versions of these applications in your system, you can always specify the direct paths to them overriding the default values in the project configuration file `stm32pio.ini`. Check the [config reference](/docs/CONFIG.md) to see all possible ways of telling stm32pio where the tools are residing on your machine.


## Documentation
  - [CLI commands](/docs/CLI/COMMANDS.md)
  - [Config](/docs/CONFIG.md)
  - [Example (CLI)](/examples/cli)
  - [GUI](/docs/GUI/README.md)


## Installation
As a normal Python package the app can be run in a completely portable way by downloading (or cloning) the snapshot of this repository and invoking the main script:
```shell script
stm32pio-repo/ $   python3 stm32pio/cli/app.py
stm32pio-repo/ $   python3 -m stm32pio.cli  # or as the Python module
any-path/ $   python3 path/to/stm32pio-repo/stm32pio/cli/app.py
```
Note: we will assume `python3` and `pip3` hereinafter.

However, it's handier to install the utility to be able to run from anywhere. The PyPI distribution is available:
```shell script
$ pip install stm32pio
```

To uninstall run
```shell script
$ pip uninstall stm32pio
```


## Usage
You can always run
```shell script
$ stm32pio --help
```
to see help on available commands.

Basically, you need to follow such a workflow (refer to the [example](/examples/cli) which explains the same just illustrating it with some screenshots/command snippets):
  1. Create the CubeMX project (`.ioc` file) like you're used to, set up your hardware configuration, but after all save it with the compatible parameters
  2. Run stm32pio that automatically invokes CubeMX to generate a code, creates the PlatformIO project, patches the `platformio.ini` file.
  3. Work with your project normally as you wish, build/upload/debug etc.
  4. When necessary, come back to the hardware configuration in the CubeMX, then run stm32pio again to re-generate the code

See the [commands reference](/docs/CLI/COMMANDS.md) file listing the complete help about the available commands/options. On the first run, stm32pio will create a config file `stm32pio.ini`, syntax of which is similar to the `platformio.ini`. You can also create this config without any following operations by initializing the project:
```shell script
$ stm32pio init -d path/to/project
```
It may be useful to tweak some parameters before proceeding. See the [config reference](/docs/CONFIG.md) showing meanings for every key.


## Troubleshooting
If you're stuck and the basic logs doesn't clear the situation, try the following:
 - Run the same command in the verbose mode using the `-v` key:
   ```shell script
   $ stm32pio -v [command] [options]
   ```
   This will unlock additional logs which might help to clarify
 - Validate your environment, i.e. check whether the stm32pio can find all the essential tools on your machine:
   ```shell script
   $ stm32pio validate -d path/to/project
   ```
   This will print the report about the current set up according to your config `stm32pio.ini` file.
 - Use the dynamic help feature which outputs information specifically about the requested command, e.g.:
   ```shell script
   $ stm32pio new -h
   ```


## Restrictions
  - The tool doesn't check for different parameters' compatibility, e.g. CPU/IO/etc frequencies, allocated memory and so on. It simply eases your workflow with these 2 programs (PlatformIO and STM32CubeMX) a little bit.
  - In order to add CubeMX middlewares to your build the manual adjustments should be applied, the stm32pio doesn't handle them automatically. For example, FreeRTOS can be added via PlatformIO' `lib` feature or be directly compiled in its own directory using `lib_extra_dirs` option:
    ```ini
    lib_extra_dirs = Middlewares/Third_Party/FreeRTOS
    ```
    You also need to move all `.c`/`.h` files to the appropriate folders respectively. See PlatformIO documentation for more information.
