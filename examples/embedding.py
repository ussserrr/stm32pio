#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Import the core library containing the main class - Stm32pio - representing the single project
import stm32pio.core.lib

# Instantiate the project. We can pass parameters at the creation stage ...
import stm32pio.core.state

project = stm32pio.core.lib.Stm32pio('./stm32pio-test-project',
                                     parameters={ 'project': { 'board': 'nucleo_f429zi' } })
# ... or later when there will be a need to do so
project.config.set('project', 'board', 'nucleo_f031k6')

# Now we can apply any actions by invoking the methods and properties
project.save_config()  # this will save the configuration file stm32pio.ini to the project folder

# The state can be tracked at any point
print(project.state)  # or ...
# Will output:
#     [*]  .ioc file is present
#     [*]  stm32pio initialized
#     [ ]  CubeMX code generated
#     [ ]  PlatformIO project initialized
#     [ ]  PlatformIO project patched
#     [ ]  PlatformIO project built
print(project.state[stm32pio.core.state.ProjectStage.INITIALIZED] is True)  # or ...
#     True
print(project.state.current_stage)
#     stm32pio initialized

# If we do not setup logging in our code the inner logging.Logger instance is not allowed
# to propagate its messages though
project.generate_code()  # we do not see any output here

# But we can help it by configuring some logging schema
import logging
logger = logging.getLogger('stm32pio')  # you can also provide a logger to the project instance itself
logger.setLevel(logging.INFO)  # use logging.DEBUG for the verbose output
handler = logging.StreamHandler()  # default STDERR stream
handler.setFormatter(logging.Formatter('%(levelname)s %(message)s'))
logger.addHandler(handler)

# Or you can just use built-in logging schema which is basically doing the same stuff for you. Note though, that only a
# single option should be either picked at a time, otherwise records duplication will occur
import stm32pio.cli.app
# logger = stm32pio.cli.app.setup_logging()

# Let's try again
project.pio_init()  # now there should be handful logging records!
#     INFO     starting PlatformIO project initialization...
#     INFO     successful PlatformIO project initialization

# Finally, you can use the high-level API - same as in the CLI version of the application - to perform complete tasks
project.clean()  # clean up the previous results first
# Again, disabling the default logging to prevent interference
return_code = stm32pio.cli.app.main(sys_argv=['new', '-d', './stm32pio-test-project', '-b', 'nucleo_f031k6'],
                                    should_setup_logging=False)
print(return_code)
#     0
project.clean()  # clean up after yourself
