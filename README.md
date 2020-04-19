# stm32pio
Small cross-platform Python app that can create and update [PlatformIO](https://platformio.org) projects from [STM32CubeMX](https://www.st.com/en/development-tools/stm32cubemx.html) `.ioc` files.

It uses STM32CubeMX to generate a HAL-framework-based code and alongside creates PlatformIO project with compatible parameters to stick them both together.

The [GUI version](/stm32pio_gui) is available, too.

![Logo](/screenshots/logo.png)


## Table of contents
> - [Features](#features)
> - [Requirements](#requirements)
> - [Installation](#installation)
> - [Usage](#usage)
>   - [Project patching](#project-patching)
>   - [Embedding](#embedding)
> - [Example](#example)
> - [Testing](#testing)
> - [Restrictions](#restrictions)


## Features
  - Start the new complete project in a single directory using only an `.ioc` file
  - Update an existing project after changing hardware options in CubeMX
  - Clean-up the project
  - Get the status information
  - *[optional]* Automatically run your favorite editor in the end
  - *[optional]* Automatically make an initial build of the project
  - *[optional]* GUI version (beta) (see stm32pio-gui sub-folder for the dedicated README)


## Requirements:
  - For this app:
    - Python 3.6 and above
  - For usage:
    - macOS, Linux, Windows
    - STM32CubeMX with desired downloaded frameworks (F0, F1, etc.)
    - Java CLI (JRE) (likely is already installed if the STM32CubeMX is working)
    - PlatformIO CLI (already presented if you have installed PlatformIO via some package manager or need to be installed as the "command line extension" from IDE)

A general recommendation there would be to test both CubeMX (code generation) and PlatformIO (project creation, building) at least once before using stm32pio to make sure that all tools work properly even without any "glue".


## Installation
You can run the app in a portable way by downloading or cloning the snapshot of the repository and invoking the main script or Python module:
```shell script
stm32pio-repo/ $   python3 stm32pio/app.py  # or
stm32pio-repo/ $   python3 -m stm32pio  # or
any-path/ $   python3 path/to/stm32pio-repo/stm32pio/app.py
```
(we assume python3 and pip3 hereinafter). It is possible to run the app like this from anywhere.

However, it's handier to install the utility to be able to run stm32pio from anywhere. Use
```shell script
stm32pio-repo/ $   pip install wheel
stm32pio-repo/ $   python setup.py sdist bdist_wheel
stm32pio-repo/ $   pip install dist/stm32pio-X.XX-py3-none-any.whl
```
commands to launch the setup process. Now you can simply type `stm32pio` in the terminal to run the utility in any directory.

Finally, the PyPI distribution (starting from v0.95) is available:
```shell script
$ pip install stm32pio
```

To uninstall in both cases run
```shell script
$ pip uninstall stm32pio
```


## Usage
Basically, you need to follow such a pattern:
  1. Create CubeMX project (.ioc file), set-up your hardware configuration, save with the compatible parameters
  2. Run the stm32pio that automatically invokes CubeMX to generate the code, creates PlatformIO project, patches a `platformio.ini` file and so on
  3. Work on the project in your editor as usual, compile/upload/debug etc.
  4. Edit the configuration in CubeMX when necessary, then run stm32pio to re-generate the code

Refer to Example section on more detailed steps. If you face off with some error try to enable a verbose output to get more information about a problem:
```shell script
$ stm32pio -v [command] [options]
```

On the first run stm32pio will create a config file `stm32pio.ini`, syntax of which is similar to the `platformio.ini`. You can also create this config without any following operations by initializing the project:
```shell script
$ stm32pio init -d path/to/project
```
It may be useful to tweak some parameters before proceeding. The structure of the config is separated in two sections: `app` and `project`. Options of the first one is related to the global settings such as commands to invoke different instruments though they can be adjusted on the per-project base while the second section contains of project-related parameters. See comments in the [`settings.py`](/stm32pio/settings.py) file for parameters description.

You can always run
```shell script
$ python app.py --help
```
to see help on available commands. Find the copy of its output on the [project wiki](https://github.com/ussserrr/stm32pio/wiki/stm32pio-help) page, also.

### Project patching

Note, that the patch operation (which takes the CubeMX code and PlatformIO project to the compliance) erases all the comments (lines starting with `;`) inside the `platformio.ini` file. They are not required anyway, in general, but if you need them for some reason please consider to save the information somewhere else.

For those who want to modify the patch (default one is at [`settings.py`](/stm32pio/settings.py), project one in a config file `stm32pio.ini`): it can has a general-form .INI content so it is possible to specify several sections and apply composite patches. This works totally fine for the most cases except, perhaps, some really big complex patches involving, say, the parameters interpolation feature. It is turned off for both `platformio.ini` and user's patch parsing by default. If there are some problems you've met due to a such behavior please modify the source code to match the parameters interpolation kind for the configs you need to. Seems like `platformio.ini` uses `ExtendedInterpolation` for its needs, by the way.

### Embedding

You can also use stm32pio as an ordinary Python package and embed it in your own application. Find the minimal example at the [project wiki](https://github.com/ussserrr/stm32pio/wiki/Embedding-example) page to see some possible ways of implementing this. Basically, you need to import `stm32pio.lib` module (where the main `Stm32pio` class resides), (optionally) set up a logger and you are good to go. If you prefer higher-level API similar to the CLI version, use `main()` function in `app.py` passing the same CLI arguments to it (except the actual script name). Also, take a look at the CLI ([`app.py`](/stm32pio/app.py)) or GUI versions.


## Example
1. Run CubeMX, choose MCU/board, do all necessary tweaking
2. Select `Project Manager -> Project` tab, specify "Project Name", choose "Other Toolchains (GPDSC)". In `Code Generator` tab check "Copy only the necessary library files" and "Generate periphery initialization as a pair of '.c/.h' files per peripheral" options

![Code Generator tab](/screenshots/tab_CodeGenerator.png)

3. Back in the first tab (Project) copy the "Toolchain Folder Location" string (you maybe not be able to copy it in modern CubeMX versions so use terminal or file manager to do this). Save the project, close CubeMX

![Project tab](/screenshots/tab_Project.png)

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
8. If you will be in need to update hardware configuration in the future, make all the necessary stuff in CubeMX and run `generate` command in a similar way:
   ```shell script
   $ stm32pio generate -d /path/to/cubemx/project
   ```
9. To clean-up the folder and keep only the `.ioc` file run `clean` command.


## Testing
There are some tests in file [`test.py`](/stm32pio/tests/test.py) (based on the unittest module). Run
```shell script
stm32pio-repo/ $   python -m unittest -b -v
```
or
```shell script
stm32pio-repo/ $   python -m stm32pio.tests.test -b -v
```
to test the app. It uses STM32F0 framework to generate and build a code from the test [`stm32pio-test-project.ioc`](/stm32pio-test-project/stm32pio-test-project.ioc) project file. Please make sure that the test project folder is clean (i.e. contains only an .ioc file) before running the test otherwise it can lead to some cases failing. Tests automatically create temporary directory (using `tempfile` Python standard module) where all actions are performed.

For the specific test suite or case you can use
```shell script
stm32pio-repo/ $   python -m unittest stm32pio.tests.test.TestIntegration -b -v
stm32pio-repo/ $   python -m unittest stm32pio.tests.test.TestCLI.test_verbose -b -v
```


## Restrictions
  - The tool doesn't check for different parameters compatibility, e.g. CPU frequency, memory sizes and so on. It simply eases your workflow with these 2 programs (PlatformIO and STM32CubeMX) a little bit.
  - CubeMX middlewares are not supported yet because it's hard to be prepared for every possible configuration. You need to manually adjust them to build appropriately. For example, FreeRTOS can be added via PlatformIO' `lib` feature or be directly compiled in its own directory using `lib_extra_dirs` option:
    ```ini
    lib_extra_dirs = Middlewares/Third_Party/FreeRTOS
    ```
    You also need to move all `.c`/`.h` files to the appropriate folders respectively. See PlatformIO documentation for more information.
