# stm32pio

[![Build Status](https://dev.azure.com/andrei42008/stm32pio/_apis/build/status/ussserrr.stm32pio?branchName=master)](https://dev.azure.com/andrei42008/stm32pio/_build/latest?definitionId=1&branchName=master)

Small cross-platform Python app that can create and update [PlatformIO](https://platformio.org) projects from [STM32CubeMX](https://www.st.com/en/development-tools/stm32cubemx.html) `.ioc` files.

It uses the STM32CubeMX to generate a HAL-framework-based code and alongside creates the PlatformIO project with compatible parameters to glue them both together.

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
  - Originate new full-fledged project in a single directory starting only from an `.ioc` file
  - Seamlessly update an existing project after making hardware changes from CubeMX
  - Quickly check the project current state
  - Inspect tools (CubeMX, PlatformIO, etc.)
  - Easily clean-up the project
  - *[optional]* Automatically run your favorite editor or initiate a build in the end
  - *[optional]* GUI edition (see [the dedicated README](/docs/GUI/README.md) file) (please, read this main introduction first)


## Requirements:
**OS:** Linux, macOS, Windows (few latest versions of 7, and above)

**Python:** 3.6+

The app introduces zero dependencies by itself. Of course, you need to have all necessary tools installed on your machine in order to perform the operations:
  - STM32CubeMX. All recent versions are fine (5.x, 6.x).
    
    - CubeMX is written in Java, so Java Runtime Environment (JRE) is required. For CubeMX versions starting from 6.3.0 it is included in the installation bundle (of CubeMX). If you are using older versions of CubeMX, either upgrade or install JRE manually.
    
    - STM32CubeMX CLI (which is used by stm32pio) can be invoked directly (by calling the executable file) or through the Java. First case is obviously simpler, and it is a default way of operating for UNIX and macOS. On Windows, however, the latter case is the only working one (for some reason), so Java executable (whether command or path) should be specified. As mentioned above, a method of its obtaining differs depending on CubeMX version, but default settings doing their best to figure out an appropriate setup and most likely all will just work out of the box.

    - CubeMX embedded software packages of your choice (F0, F1, etc.) should be added into CubeMX. In case of their absence or versions mismatches you will probably be prompted by CubeMX during the code generation stage.

    For more information on how STM32CubeMX functions please refer to its manual (that is shipped with the installation bundle) or community forum.

  - PlatformIO CLI. Its presence in your system depends on how you're using it:
    - If you have obtained it via some package manager like `pip`, `conda`, `apt`, `brew`, `choco`, etc. most likely the `platformio` command is already in your `PATH` environment variable, and you're able to start it through a command line. In this case you're good to go.
    - If you're using PlatformIO IDE, the CLI extension should be installed in addition to your existing setup. See [PlatformIO docs](https://docs.platformio.org/en/latest/core/installation.html#piocore-install-shell-commands) for more information on how to do that.

Either way, for every tool listed above, a simple direct path to the according executable can be specified just in case you cannot or don't want to register them in your `PATH`. Check the [config reference](/docs/CONFIG.md) to see all possible ways of telling stm32pio where the tools are residing on your machine.


## Documentation
  - [CLI commands](/docs/CLI/COMMANDS.md)
  - [Config](/docs/CONFIG.md)
  - [Example (CLI)](/examples/cli)
  - [GUI](/docs/GUI/README.md)


## Installation
The most straightforward way is to get the PyPI distribution:
```shell script
$ pip install stm32pio
```

To uninstall run
```shell script
$ pip uninstall stm32pio
```

As a normal Python package, the app can be run completely portable. Simply download or clone this repository and launch the main script:
```shell script
stm32pio-repo/ $   python stm32pio/cli/app.py  # call the file...
stm32pio-repo/ $   python -m stm32pio.cli  # ...or run as Python module
stm32pio-repo/ $   python -m stm32pio.cli.app
any-path/ $   python path/to/stm32pio-repo/stm32pio/cli/app.py  # the script can be invoked from anywhere
```


## Usage
You can always run
```shell script
$ stm32pio
```
to see help on available commands.

Essentially, you need to follow such a workflow:
  1. Create new CubeMX project, set up your hardware configuration, and save with compatible parameters. You'll end up with the `.ioc` file.
  2. Run stm32pio that automatically invokes CubeMX to generate a code, establishes new PlatformIO project with specific parameters and applies the patch.
  3. Work with your PlatformIO project normally as you like, build/upload/debug etc.
  4. When necessary, come back to hardware configuration in CubeMX, then run stm32pio again to re-generate the code.

Refer to the [example](/examples/cli) guide which basically explains same concepts just in more details and illustrates with some screenshots/command snippets.

See the [commands reference](/docs/CLI/COMMANDS.md) providing the complete help about available commands/options. On the first run in your project, stm32pio will create a config file `stm32pio.ini`, syntax of which is similar to `platformio.ini`. You can also create such config without any following operations by initializing the project:
```shell script
path/to/project $ stm32pio init
```
Might be useful to tweak some parameters before proceeding. See the [config reference](/docs/CONFIG.md) showing meanings for every key.


## Troubleshooting
If you've encountered a problem and basic logs doesn't clear the situation, try the following:
 - Run the same command in verbose mode adding `-v` key:
   ```shell script
   $ stm32pio -v ...
   ```
   This will unlock extra logs helping to clarify what's wrong
 - Validate your environment, i.e. check whether stm32pio can find all required tools on your machine:
   ```shell script
   $ stm32pio validate
   ```
   This will print a small report about the current setup according to your config `stm32pio.ini` file.
 - Use the dynamic help feature that outputs information exactly about the requested command, for example:
   ```shell script
   $ stm32pio new -h  # "new" command manual
   ```


## Restrictions
  - The tool doesn't check for compatibility of various parameters like clocks/pinout/periphery/memory and so on. It just eases your workflow with those 2 programs (PlatformIO and STM32CubeMX) a little bit.
  - In order to introduce some CubeMX middleware into target build the manual adjustments should be applied – stm32pio will not handle them automatically. Tell PlatformIO what to link, set necessary build flags, etc. For example, FreeRTOS can be added via PlatformIO `lib` feature or be directly compiled in its own directory using `lib_extra_dirs` option:
    ```ini
    lib_extra_dirs = Middlewares/Third_Party/FreeRTOS
    ```
    You also need to move all `.c`/`.h` sources into according directories. See PlatformIO documentation for more information.
