"""
Entities helping the main class validate some command line tools.
"""

import logging
import subprocess
from typing import Optional, Callable, Tuple, List

import stm32pio.core.settings
from stm32pio.core.config import Config
from stm32pio.core.cubemx import CubeMX
from stm32pio.core.log import LogPipe


class ToolValidator:

    # Properties-results of validation. These will be set after run
    succeed: bool = None
    text: str = None  # some optional additional description of the tool state
    error: Exception = None  # optional exception in case some error happened

    def __init__(self, name: str, command: Optional[str],
                 runner: Callable[[Optional[str]], Tuple[subprocess.CompletedProcess, str]],
                 required: bool = True, logger: logging.Logger = None):
        """
        The constructor does nothing to check the tool. Invoke the validate() method to fill the meaningful fields.

        Args:
            name: what we're verifying?
            command: optional argument to pass to the runner
            runner: function to execute to determine the validated thing is correct
            required: is this parameter mandatory? If this is true the tool will be considered succeeded
                      even if it is not set
            logger: optional logging.Logger instance to indicate the progress
        """
        # TODO: dataclass can be used
        #  (https://stackoverflow.com/questions/1389180/automatically-initialize-instance-variables)
        self.name = name
        self.command = command
        self.runner = runner
        self.required = required
        self.logger = logger

    def _run(self, command):
        """_macro_ function to reduce a code repetition"""
        completed_process, std_output = self.runner(command)
        self.succeed = completed_process.returncode == 0
        if completed_process.returncode != 0:
            self.error = Exception(std_output)

    def validate(self):
        """Start the validation using collected information (properties). Return itself for further usage"""

        if self.logger is not None:
            self.logger.info(f"checking '{self.name}'...")

        try:
            if self.required:
                if self.command:
                    self._run(self.command)
                else:
                    self.succeed = False
                    self.error = Exception(f"'{self.name}' not set (should be a valid command)")
            else:
                if self.command and (self.command.lower() in stm32pio.core.settings.none_options):
                    self.succeed = True
                    self.text = f"'{self.name}' is set to None, ignoring"
                elif self.command:
                    self._run(self.command)
                else:
                    self.succeed = False
                    self.error = Exception(f"'{self.name}' not set (should be a valid command or None)")
        except Exception as e:
            self.succeed = False
            self.error = e

        return self


class ToolsValidationResults(List[ToolValidator]):
    """Conveniently store the validation results and use some useful additional features"""

    @property
    def succeed(self) -> bool:
        return all(tool.succeed for tool in self)

    def __str__(self):
        """Format the results of contained members (basic report and extended if present)"""

        basic_report = ''
        for tool in self:
            tool_str = f"[{'ok' if tool.succeed else 'error':>5}]  {tool.name:<10}"
            if tool.text:
                tool_str += f"  {tool.text}"
            basic_report += f"{tool_str}\n"

        verbose_report = ''
        faulty_tools = [tool for tool in self if tool.error is not None]
        if len(faulty_tools):
            verbose_report += '\n\nTools output:\n\n'
            for tool in faulty_tools:
                verbose_report += f"{tool.name}\n    {tool.error}\n\n"

        return basic_report + verbose_report


def validate_environment(config: Config, cubemx: CubeMX, logger: logging.Logger) -> ToolsValidationResults:
    """Verify tools specified in the 'app' section of the current configuration"""

    def java_runner(java_cmd):
        with LogPipe(logger, logging.DEBUG) as log:
            completed_process = subprocess.run([java_cmd, '-version'], stdout=log.pipe, stderr=log.pipe)
            std_output = log.value
        return completed_process, std_output

    def cubemx_runner(_):
        return cubemx.execute_script('exit\n')  # just start and exit

    def platformio_runner(platformio_cmd):
        with LogPipe(logger, logging.DEBUG) as log:
            completed_process = subprocess.run([platformio_cmd], stdout=log.pipe, stderr=log.pipe)
            std_output = log.value
        return completed_process, std_output

    if not config.path.exists():
        logger.warning("config file not found. Validation will be performed against the runtime configuration")

    return ToolsValidationResults(
        ToolValidator(
            name=param,
            command=config.get('app', param),
            runner=runner,
            required=required,
            logger=logger
        ).validate() for param, runner, required in [
            ('java_cmd', java_runner, False),
            ('cubemx_cmd', cubemx_runner, True),
            ('platformio_cmd', platformio_runner, True)
        ])
