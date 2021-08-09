# Developing & contributing
Find actual tasks at [Projects](https://github.com/ussserrr/stm32pio/projects) and [Discussions](https://github.com/ussserrr/stm32pio/discussions). This file, on the other hand, focuses on some relevant topics regarding build/test/CI processes. The code is well commented in-place and that can be considered as a developer documentation really. Some parts also can be found in the [docs](/docs) folder.


## Build
Staring from v2.0.0, the PEP517-compatible build process is supported. For the dependencies list see [pyproject.toml](/pyproject.toml) file. It is recommended to use the latest stable Python and modules versions. [build](https://pypa-build.readthedocs.io) package is used to build both wheel and source distributions. To start a process run:
```shell
$ pip install build
$ python -m build
```


## Test
Testing (code is located at the [`tests`](/tests) directory) is done via the `unittest` module from the Python standard library. It's compatible with the `pytest` runner, too. Single test stage is a CubeMX project (`.ioc` file). Several such targets can be placed inside the `fixtures` folder to test against. Then start testing specifying concrete fixture as an environment variable:
```shell
stm32pio-repo/ $   STM32PIO_TEST_CASE=nucleo_f031k6 python -m unittest -b -v
```
Every run automatically instantiates a temporary directory (using `tempfile` module) where all the actions are performed so no repository file will be "disturbed". To run the specific group of tests or a particular test function you can use:
```shell
stm32pio-repo/ $   python -m unittest tests.test_integration.TestIntegration
stm32pio-repo/ $   python -m unittest tests.test_cli.TestCLI.test_verbosity
```
`.ioc` files and installed tools' versions should match otherwise the CubeMX will complain about their incompatibility.


## CI/CD

**WARNING:** CI/CD is currently turned off due to the unavailability of the STM32CubeMX (no direct link provided)

Azure Pipelines is used to automate test, build, and publish tasks (see [azure-pipelines.yml](/azure-pipelines.yml), [CI](/CI) for more information). The repo is tested against the matrix of all 3 major OSes and latest Python interpreters. Also, for the Linux runs the test percentage and coverage are calculated. Therefore, for these purposes some additional external dependencies are required:
  - pytest
  - coverage
  - yaml
  
There are some elements of the "reproducible builds" approach using several "lockfiles", isolated test fixtures and caching. Optional `platformio.ini.lockfile`, "freezing" the PlatformIO packages' versions needed for a successful build, can be placed inside an every fixture folder. This config is an ordinary .INI-style file which will be merged into the `platformio.ini` during testing.

Overall, due to a number of such a diverse tools in use, the full-fledged "canonical" CI seems challenging to implement, and the current set up is far from ideal in that regard.

Finally, in the end of a pipeline, resulting bundles are published to PyPA via twine module. This stage is enabled only for the master branch.
