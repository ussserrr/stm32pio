# stm32pio

[![Build Status](https://dev.azure.com/andrei42008/stm32pio/_apis/build/status/ussserrr.stm32pio?branchName=dev)](https://dev.azure.com/andrei42008/stm32pio/_build/latest?definitionId=1&branchName=dev)

Small cross-platform Python app that can create and update [PlatformIO](https://platformio.org) projects from the [STM32CubeMX](https://www.st.com/en/development-tools/stm32cubemx.html) `.ioc` files.

It uses STM32CubeMX to generate a HAL-framework-based code and alongside creates PlatformIO project with the compatible parameters to stick them both together.

The [GUI version](/docs/gui/README.md) is available, too.

![Logo](/screenshots/logo.png)


## Table of contents
> - [Features](#features)
> - [Requirements](#requirements)
> - [Installation](#installation)
> - [Usage](#usage)
>   - [Project patching](#project-patching)
>   - [Embedding](#embedding)
> - [Example](#example)
> - [Build](#build)
> - [Test](#test)
> - [CI](#ci)
> - [Restrictions](#restrictions)


## Features
  - Start the new complete project in a single directory using only an `.ioc` file
  - Update an existing project after changing a hardware options in CubeMX
  - Clean-up the project
  - Get the status information
  - *[optional]* Automatically run your favorite editor in the end
  - *[optional]* Automatically make an initial build of the project
  - *[optional]* GUI version (see [the dedicated README](/docs/gui/README.md) file)


## Requirements:
The app presents zero dependencies by itself and requires only this to run:
  - macOS, Linux, Windows
  - Python 3.6 and above

Of course, you need to have all the necessary tools to be installed in order to work with them:
  - STM32CubeMX with the desired downloaded frameworks (F0, F1, etc.). All recent versions are fine, probably something like 5.0+
  - Java CLI (JRE, Java runtime environment) for the CubeMX (likely is already installed if the CubeMX is working). In other words, you should be able to launch the Java from your terminal using `java` command. Which version is appropriate for the CubeMX you can find in its docs
  - PlatformIO (4.2.0 and above) CLI (already present if you have installed PlatformIO via some package manager (`pip`, `apt`, `brew`, etc.) or need to be installed as the "command line extension" from IDE (see [docs](https://docs.platformio.org/en/latest/core/installation.html) for more information))

If you for some reasons don't want to or cannot install command line versions of these applications in your system you can always specify the direct paths to them using the project configuration file `stm32pio.ini` or even override the default values in the source code file `core/settings.py`.

Also, some external dependencies may be required to build, test and pack the app. See the corresponding sections for more information.

A general recommendation there would be to test both CubeMX (code generation) and PlatformIO (project creation, building) at least once before using the stm32pio to make sure all the tools work properly even without any "glue".

**2020 Update**: in my tests, recent versions of CubeMX had been shipping with no installer of some sort. So I just unpack the distribution archive and place it in `~/cubemx` directory so it can be started simply as `java -jar ~/cubemx/STM32CubeMX.exe`. That's why the default path is as mentioned above. Tell me if your default path is rather another. Also, the default structure of the generated code is significantly different when you invoke the generation from the GUI version of CubeMX or the CLI one. As stm32pio uses the latter, currently the PlatformIO project structure cannot be properly patched to use a code from the GUI version of CubeMX (at least with the default patch config, you can always tweak it in a configuration file `stm32pio.ini`).


## Installation
As a normal Python package the app can be run in a completely portable way by downloading or cloning the snapshot of this repository and invoking the main script (or the Python module):
```shell script
stm32pio-repo/ $   python3 stm32pio/cli/app.py  # or
stm32pio-repo/ $   python3 -m stm32pio.cli  # or
any-path/ $   python3 path/to/stm32pio-repo/stm32pio/cli/app.py
```
(we assume `python3` and `pip3` hereinafter).

However, it's handier to install the utility to be able to run stm32pio from anywhere. The PyPI distribution (starting from v0.95) is available:
```shell script
$ pip install stm32pio
```

To uninstall run
```shell script
$ pip uninstall stm32pio
```


## Usage
Basically, you need to follow such a pattern:
  1. Create CubeMX project (`.ioc` file), set-up your hardware configuration, save with the compatible parameters
  2. Run the stm32pio that automatically invokes CubeMX to generate the code, creates PlatformIO project, patches a `platformio.ini` file and so on
  3. Work with your project normally as you wish, compile/upload/debug etc.
  4. Come back to the hardware configuration in CubeMX when necessary, then run stm32pio to re-generate the code

Refer to Example section on more detailed steps. If you face off with some error try to enable a verbose output to get more information about a problem:
```shell script
$ stm32pio -v [command] [options]
```

On the first run stm32pio will create a config file `stm32pio.ini`, syntax of which is similar to the `platformio.ini`. You can also create this config without any following operations by initializing the project:
```shell script
$ stm32pio init -d path/to/project
```
It may be useful to tweak some parameters before proceeding. The structure of the config is separated into two sections: `app` and `project`. Options of the first one is related to the global settings (such as commands to invoke different instruments) though they can be adjusted on the per-project base while the second section contains of project-related parameters. See comments in the [`settings.py`](/stm32pio/core/settings.py) file for parameters description.

You can always run
```shell script
$ stm32pio --help
```
to see help on available commands. Find the copy of its output on the [project wiki](https://github.com/ussserrr/stm32pio/wiki/stm32pio-help) page, also.

### Project patching

Note, that the patch operation (which takes the CubeMX code and PlatformIO project to the compliance) erases all the comments (lines starting with `;`) inside the `platformio.ini` file. They are not required anyway, in general, but if you need them for some reason please consider saving the information somewhere else.

For those who wants to modify the patch (default one is at [`settings.py`](/stm32pio/core/settings.py), project one in a config file `stm32pio.ini`): it has a general-form .INI-style content so it's possible to specify several sections and apply composite patches. This works totally fine for the most cases except, perhaps, some really big complex patches involving, say, the parameters interpolation feature. It is turned off for both `platformio.ini` and user's patch parsing by default. If there are some problems you've met due to a such behavior please modify the source code to match the parameters interpolation kind for the configs you need to. Seems like `platformio.ini` uses `ExtendedInterpolation` for its needs, by the way.

### Embedding

You can also use stm32pio as an ordinary Python package and embed it in your own application. Find the minimal example at the [examples](/examples) to see some possible ways of implementing this. Basically, you need to import `stm32pio.core.lib` module (where the main `Stm32pio` class resides), _optionally_ set up a logger and you are good to go. If you prefer higher-level API similar to the CLI version, use `main()` function in `cli/app.py` passing the same CLI arguments to it. Also, take a look at the CLI ([`app.py`](/stm32pio/cli/app.py)) or GUI versions.


## Example
1. Run CubeMX, choose MCU/board, do all necessary tweaking
2. Select `Project Manager -> Project` tab, specify "Project Name", choose "Other Toolchains (GPDSC)". In `Code Generator` tab check "Copy only the necessary library files" and "Generate periphery initialization as a pair of '.c/.h' files per peripheral" options

![Code Generator tab](/docs/cubemx_project_settings/tab_CodeGenerator.png)

3. Back in the first tab (Project) copy the "Toolchain Folder Location" string (you may not be able to copy it in modern CubeMX versions so use a terminal or a file manager to do this). Save the project

![Project tab](/docs/cubemx_project_settings/tab_Project.png)

4. Use a copied string (project folder) as a `-d` argument for stm32pio (can be omitted if your current working directory is already a project directory).
5. Run `platformio boards` (`pio boards`) or go to [boards](https://docs.platformio.org/en/latest/boards) to list all supported devices. Pick one and use its ID as a `-b` argument (for example, `nucleo_f031k6`)
6. All done! You can now run
   ```shell script
   $ stm32pio new -d path/to/cubemx/project/ -b nucleo_f031k6 --start-editor=code --with-build
   ```
   to trigger the code generation, compile the project and start the VSCode editor with opened folder (last 2 options are given as an example and they are not required). Make sure you have all the tools in PATH (`java` (or set its path in `stm32pio.ini`), `platformio`, `python`, editor). You can use a slightly shorter form if you are already located in the project directory:
   ```shell script
   path/to/cubemx/project/ $   stm32pio new -b nucleo_f031k6
   ```
7. To get the information about the current state of the project use `status` command.
8. If you will be in need to update the hardware configuration in a future, make all the necessary stuff in CubeMX and run `generate` command in a similar way:
   ```shell script
   $ stm32pio generate -d /path/to/cubemx/project
   ```
9. To clean-up the folder and keep only the `.ioc` file run `clean` command.


## Build
Staring from v2.0.0 PEP517-compatible build process is supported. For the build dependencies list see [pyproject.toml](/pyproject.toml) file:
```shell script
$ pip install wheel
$ pip install setuptools setuptools_scm
```
This process yet described and standardized in PEPs is still early and not fully implemented by the different tools (such as pip, twine) though (at the time of this version at least). So the current way is a little bit messy and depends on different instruments. Use the latest Python and build packages versions. To build a _wheel_ `setup.py` is not even required:
```shell script
$ pip wheel . --wheel-dir dist
```
but for the source distribution tarball it is still necessary:
```shell script
$ python setup.py sdist
```


## Test
There are some tests in [`tests`](/tests) directory (based on the unittest module). The test stage is a CubeMX project (`.ioc` file) with an optional `platformio.ini.lockfile` config specifying the versions of the used ("locked") PlatformIO libraries (see "CI" chapter) (this config is an ordinary .INI-style file which will be merged with the `platformio.ini` test file). Several such targets can be placed to the `fixtures` folder to test against. Finally, run this command setting the current case as an environment variable
```shell script
stm32pio-repo/ $   STM32PIO_TEST_CASE=nucleo_f031k6 python -m unittest -b -v
```
to test the stm32pio. Tests code automatically create temporary directory (using `tempfile` Python standard module) where all actions are performed.

To run the specific group of tests or a single test function you can use:
```shell script
stm32pio-repo/ $   python -m unittest tests.test_integration.TestIntegration
stm32pio-repo/ $   python -m unittest tests.test_cli.TestCLI.test_verbosity
```

Automated tests against old `.ioc` files seems not possible because of CubeMX interactive GUI prompts about migrations. I don't find any CLI key or option to disable them (and in general, documentation for the CubeMX CLI doesn't look complete...).


## CI
Azure Pipelines is used to automate test, build, and publish tasks. The repo is tested against all 3 major OSes and for the Linux the test coverage is also calculated. For this purposes some additional external dependencies are necessary, such as
  - pytest
  - coverage
  - yaml
  
There are some elements of the "reproducible builds" approach using several "lockfiles", isolated test fixtures and caching. Actually, due to a number of different tools in use and their nature the truly and fully "canonical" CI seems challenging to implement so the current system is far from ideal. It probably will be improved in the future, see [azure-pipelines.yml](/azure-pipelines.yml), [CI](/CI) for more information for now.


## Restrictions
  - The tool doesn't check for different parameters compatibility, e.g. CPU frequency, memory sizes and so on. It simply eases your workflow with these 2 programs (PlatformIO and STM32CubeMX) a little bit.
  - CubeMX middlewares are not supported yet because it's hard to be prepared for every possible configuration. You need to manually adjust them to build appropriately. For example, FreeRTOS can be added via PlatformIO' `lib` feature or be directly compiled in its own directory using `lib_extra_dirs` option:
    ```ini
    lib_extra_dirs = Middlewares/Third_Party/FreeRTOS
    ```
    You also need to move all `.c`/`.h` files to the appropriate folders respectively. See PlatformIO documentation for more information.
