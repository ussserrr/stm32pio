# stm32pio
Small cross-platform Python app that can create and update [PlatformIO](https://platformio.org) projects from [STM32CubeMX](https://www.st.com/en/development-tools/stm32cubemx.html) `.ioc` files.

It uses STM32CubeMX to generate a HAL-framework based code and alongside creates PlatformIO project with the compatible `stm32cube` framework specified.

![Logo](/screenshots/logo.png)


## Features
  - Start the new project in a single directory using only an `.ioc` file
  - Update existing project after changing hardware options from CubeMX
  - Clean-up the project (WARNING: it deletes ALL content of project path except the `.ioc` file!)
  - *[optional]* Automatically run your favorite editor in the end
  - *[optional]* Automatically make an initial build of the project


## Requirements:
  - For this app:
    - Python 3.6 and above
  - For usage:
    - macOS, Linux, Windows
    - STM32CubeMX (all recent versions) with desired downloaded frameworks (F0, F1, etc.)
    - Java CLI (JRE) (likely is already installed if the STM32CubeMX is working)
    - PlatformIO CLI (already presented if you have installed PlatformIO via some package manager or need to be installed as the command line extension from IDE)

A general recommendation there would be to try to generate and build a code manually (via the CubeMX GUI and PlatformIO CLI or IDE) at least once before using stm32pio to make sure that all tools are working properly without any "glue".


## Installation
Starting from v0.8 it is possible to install the utility to be able to run stm32pio from anywhere. Use
```shell script
stm32pio-repo/ $   pip3 install .
```
command to launch the setup process. Now you can simply type 'stm32pio' in the terminal to run the utility in any directory.

PyPI distribution (starting from v0.95):
```shell script
$ pip install stm32pio
```

To uninstall run
```shell script
$ pip3 uninstall stm32pio
```


## Usage
Basically, you need to follow such a pattern:
  1. Create CubeMX project, set-up your hardware configuration
  2. Run stm32pio that automatically invoke CubeMX to generate the code, create PlatformIO project, patch a 'platformio.ini' file and so on
  3. Work on the project in your editor, compile/upload/debug etc.
  4. Edit the configuration in CubeMX when necessary, then run stm32pio to regenerate the code.

Refer to Example section on more detailed steps. If you face off with some error try to enable a verbose output to get more information about a problem:
```shell script
$ stm32pio -v [command] [options]
```

Note, that the patch operation (which takes the CubeMX code and PlatformIO project to the compliance) erases all the comments (lines starting with `;`) inside the `platformio.ini` file. They are not required anyway, in general, but if you need them please consider to save the information somewhere else.

Starting from v0.95, the patch can has a general-form .INI content so it is possible to modify several sections and apply composite patches. This works totally fine for almost every cases except some big complex patches involving the parameters interpolation feature. It is turned off for both `platformio.ini` and user's patch parsing by default. If there are some problems you've met due to a such behavior please modify the source code to match the parameters interpolation kind for the configs you need to. Seems like `platformio.ini` uses `ExtendedInterpolation` for its needs, by the way.

On the first run stm32pio will create a config file `stm32pio.ini`, syntax of which is similar to the `platformio.ini`. You can also create this config without any following operations by initializing the project:
```shell script
$ stm32pio init -d path/to/project
```
It may be useful to tweak some parameters before proceeding. The structure of the config is separated in two sections: `app` and `project`. Options of the first one is related to the global settings such as commands to invoke different instruments though they can be adjusted on the per-project base while the second section contains of project-related parameters. See the comments in the [`settings.py`](/stm32pio/settings.py) file for parameters description.

You can always run
```shell script
$ python3 app.py --help
```
to see help on available commands.

You can also use stm32pio as a package and embed it in your own application. See [`app.py`](/stm32pio/app.py) to see how to implement this. Basically you need to import `stm32pio.lib` module (where the main `Stm32pio` class resides), set up a logger and you are good to go. If you need higher-level API similar to the CLI version, use `main()` function in `app.py` passing the same CLI arguments to it (except the actual script name).


## Example
1. Run CubeMX, choose MCU/board, do all necessary stuff
2. Select `Project Manager -> Project` tab, specify "Project Name", choose "Other Toolchains (GPDSC)". In `Code Generator` tab check "Copy only the necessary library files" and "Generate periphery initialization as a pair of '.c/.h' files per peripheral" options

![Code Generator tab](/screenshots/tab_CodeGenerator.png)

3. Back in the first tab (Project) copy the "Toolchain Folder Location" string (you maybe not be able to copy it in modern CubeMX versions so use terminal or file manager to do this). Save the project, close CubeMX

![Project tab](/screenshots/tab_Project.png)

4. Use a copied string as a `-d` argument for stm32pio. So it is assumed that the name of the project folder matches the name of `.ioc` file. (`-d` argument can be omitted if your current working directory is already a project directory)
5. Run `platformio boards` (`pio boards`) or go to [boards](https://docs.platformio.org/en/latest/boards) to list all supported devices. Pick one and use its ID as a `-b` argument (for example, `nucleo_f031k6`)
6. All done! You can now run
   ```shell script
   $ python3 app.py new -d path/to/cubemx/project/ -b nucleo_f031k6 --start-editor=code --with-build
   ```
   to complete generation, start the Visual Studio Code editor with opened folder and compile the project (as an example, not required). Make sure you have all tools in PATH (`java` (or set its path in `stm32pio.ini`), `platformio`, `python`, editor). You can use shorter form if you are already located in the project directory (also using shebang alias):
   ```shell script
   path/to/cubemx/project/ $   stm32pio new -b nucleo_f031k6
   ```
7. If you will be in need to update hardware configuration in the future, make all necessary stuff in CubeMX and run `generate` command in a similar way:
   ```shell script
   $ python3 app.py generate -d /path/to/cubemx/project
   ```
8. To clean-up the folder and keep only the `.ioc` file run `clean` command


## Testing
Since ver. 0.45 there are some tests in file [`test.py`](/stm32pio/tests/test.py) (based on the unittest module). Run
```shell script
stm32pio-repo/ $   python3 -m unittest -b -v
```
or
```shell script
stm32pio-repo/ $   python3 -m stm32pio.tests.test -b -v
```
to test the app. It uses STM32F0 framework to generate and build a code from the test [`stm32pio-test-project.ioc`](/stm32pio-test-project/stm32pio-test-project.ioc) project file. Please make sure that the test project folder is clean (i.e. contains only an .ioc file) before running the test.

For specific test suite or case you can use
```shell script
stm32pio-repo/ $   python3 -m unittest stm32pio.tests.test.TestIntegration -b -v
stm32pio-repo/ $   python3 -m unittest stm32pio.tests.test.TestCLI.test_verbose -b -v
```

While testing was performed on different Python and OS versions, some older Windows versions had shown some 'glitches' and instability. [WinError 5] and others had appeared on such tests like `test_run_edtor` and on `tempfile` clean-up processes. So be ready to face off with them.

CI is hard to implement for all target OSes during the requirement to have all the tools (PlatformIO, Java, CubeMX, etc.) installed during the test. For example, ST doesn't even provide a direct link to the CubeMX for downloading.


## Restrictions
  - The tool doesn't check for different parameters compatibility, e.g. CPU frequency, memory sizes and so on. It simply eases your workflow with these 2 programs (PlatformIO and STM32CubeMX) a little bit.
  - CubeMX middlewares are not supported yet because it's hard to be prepared for every possible configuration. You need to manually adjust them to build appropriately. For example, FreeRTOS can be added via PlatformIO' `lib` feature or be directly compiled in its own directory using `lib_extra_dirs` option:
    ```ini
    lib_extra_dirs = Middlewares/Third_Party/FreeRTOS
    ```
    You also need to move all `.c`/`.h` files to the appropriate folders respectively. See PlatformIO documentation for more information.
