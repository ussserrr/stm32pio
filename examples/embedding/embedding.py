#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Import the core library containing the main class - Stm32pio - representing a single project
import stm32pio.core.project

# Instantiate the project. We can pass parameters at the creation stage ...
project = stm32pio.core.project.Stm32pio('./stm32pio-test-project',
                                         parameters={ 'project': { 'board': 'nucleo_f429zi' } })
# ... or later when there will be a need to do so
project.config.set('project', 'board', 'nucleo_f031k6')

# Now we can execute any action by invoking methods and properties
project.config.save()  # this will save the configuration file stm32pio.ini to the project folder

# The state can be inspected at any point
print(project.state)
# Will output:
#     [*]  .ioc file is present
#     [*]  stm32pio initialized
#     [ ]  CubeMX code generated
#     [ ]  PlatformIO project initialized
#     [ ]  PlatformIO project patched
#     [ ]  PlatformIO project built
# or ...
from stm32pio.core.state import ProjectStage
print(project.state[ProjectStage.INITIALIZED] is True)
#     True
# or ...
print(project.state.current_stage)
#     stm32pio initialized

# If we haven't set up logging, messages from the inner logging.Logger instance are not allowed to propagate by default
project.generate_code()  # we do not see any output here

# But we can help it by configuring some logging schema
import logging
logger = logging.getLogger('stm32pio')  # you can also provide a logger to the project instance itself
logger.setLevel(logging.INFO)  # use logging.DEBUG for the verbose output
handler = logging.StreamHandler()  # default STDERR stream
handler.setFormatter(logging.Formatter('%(levelname)s %(message)s'))  # some pretty simple output format
logger.addHandler(handler)

# Or you can just use a built-in logging schema which is basically doing the same stuff for you. Note though, that only
# a single option should be either picked at a time, otherwise records duplication will occur
import stm32pio.cli.app
# logger = stm32pio.cli.app.setup_logging()  # comment section above and uncomment me

# There are multiple ways of logging configuration, it as an essential feature opening doors to many possible library
# applications

# Let's try again
project.pio_init()  # now there should be some handful logging records!
#     INFO     starting PlatformIO project initialization...
#     INFO     successful PlatformIO project initialization

# Finally, you can use the high-level API - same as for the CLI version of the application - to perform complex tasks
project.clean()  # clean up the previous results first
return_code = stm32pio.cli.app.main(
    sys_argv=['new', '--directory', './stm32pio-test-project', '--board', 'nucleo_f031k6'],
    should_setup_logging=False)  # again, disabling the default logging to prevent an interference
print(return_code)  # main() is designed to never throw any exception so we monitor the response via the return code
#     0
project.clean()  # clean up after yourself

# In the end, let's check our environment - programs used by the stm32pio. This can be done through the 'validate'
# command. Like for the state, its output is ready for printing right away:
print(project.validate_environment())
#     [   ok]  java_cmd
#     [   ok]  cubemx_cmd
#     [   ok]  platformio_cmd
