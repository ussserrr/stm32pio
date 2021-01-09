# Developing & contributing
Find actual tasks at [TODO.md list](/TODO.md) / [GitHub issues](https://github.com/ussserrr/stm32pio/issues). This file focuses on some relevant topics regarding build/test/CI processes. The code is well commented in-place and that can be considered as a developer documentation really. Some parts also can be found in the [docs](/docs) folder.


## Build
Staring from v2.0.0, the PEP517-compatible build process is supported. This process, yet described and standardized in several PEPs, is still a pretty early one and not fully adopted by official Python tools (such as pip, twine), though (at the time of publication at least). So the current way to pack is a little messy and relies on different instruments. Better use the latest Python and build packages versions.

For the dependencies list see [pyproject.toml](/pyproject.toml) file:
```shell script
$ pip install wheel setuptools setuptools_scm
```

To build a Python _wheel_ `setup.py` is not even required:
```shell script
$ pip wheel . --wheel-dir dist
```
but for the assembling of the source distribution tarball it is still necessary:
```shell script
$ python setup.py sdist
```


## Test
Testing (code is located at the [`tests`](/tests) directory) is done via the `unittest` module from the Python standard library. It's compatible with the `pytest` runner, too. Single test stage is a CubeMX project (`.ioc` file). Several such targets can be placed inside the `fixtures` folder to test against. Then start testing specifying concrete fixture as an environment variable:
```shell script
stm32pio-repo/ $   STM32PIO_TEST_CASE=nucleo_f031k6 python -m unittest -b -v
```
Every run automatically instantiates a temporary directory (using `tempfile` module) where all the actions are performed so no repository file will be "disturbed". To run the specific group of tests or a particular test function you can use:
```shell script
stm32pio-repo/ $   python -m unittest tests.test_integration.TestIntegration
stm32pio-repo/ $   python -m unittest tests.test_cli.TestCLI.test_verbosity
```
`.ioc` files and installed tools' versions should match otherwise the CubeMX will complain about their incompatibility.


## CI/CD
Azure Pipelines is used to automate test, build, and publish tasks (see [azure-pipelines.yml](/azure-pipelines.yml), [CI](/CI) for more information). The repo is tested against the matrix of all 3 major OSes and latest Python interpreters. Also, for the Linux runs the test percentage and coverage are calculated. Therefore, for these purposes some additional external dependencies are required:
  - pytest
  - coverage
  - yaml
  
There are some elements of the "reproducible builds" approach using several "lockfiles", isolated test fixtures and caching. Optional `platformio.ini.lockfile`, "freezing" the PlatformIO packages' versions needed for a successful build, can be placed inside an every fixture folder. This config is an ordinary .INI-style file which will be merged into the `platformio.ini` during testing.

Overall, due to a number of such a diverse tools in use, the full-fledged "canonical" CI seems challenging to implement, and the current set up is far from ideal in that regard.
