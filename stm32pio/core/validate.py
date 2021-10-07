"""
Helpers for command line tools presence validation.
"""

import logging
import subprocess
from typing import Optional, Callable, Tuple, List

import stm32pio.core.config
import stm32pio.core.cubemx
import stm32pio.core.log
import stm32pio.core.settings


Runner = Callable[[Optional[str]], Tuple[subprocess.CompletedProcess, str]]


class Tool:
    """Class representing a tool – some CLI command to execute and validate (i.e. check its presence)"""

    # Properties-results of validation. These will be set after a run. Initially set to None to explicitly indicate
    # there were been no validations yet
    succeed: bool = None
    remarks: str = None  # some optional additional description of the tool state
    error: Exception = None  # exception will be set in case of unsuccessful run

    def __init__(self, logger: stm32pio.core.log.Logger, name: str, runner: Runner, command: str = None,
                 required: bool = True):
        """
        :param logger: logging.Logger-compatible object
        :param name: what we're verifying?
        :param runner: function to execute in order to validate the tool
        :param command: if given, this will be passed to runner as an argument
        :param required: if False, the tool will be considered succeed even if it is not set
        """
        self.logger = logger
        self.name = name
        self.runner = runner
        self.command = command
        self.required = required

    def _run(self, command: str):
        """Execute a runner"""
        completed_process, std_output = self.runner(command)
        self.succeed = completed_process.returncode == 0
        if completed_process.returncode != 0:
            self.error = Exception(std_output or 'Unknown error')

    def validate(self) -> 'Tool':
        """Run the validation. Chainable method"""
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
                    self.remarks = f"'{self.name}' is set to None, ignoring"
                elif self.command:
                    self._run(self.command)
                else:
                    self.succeed = False
                    self.error = Exception(f"'{self.name}' not set (should be a valid command or None)")
        except Exception as e:
            self.succeed = False
            self.error = e
        return self


class ToolsValidationResults(List[Tool]):
    """
    Convenient container of validation results allowing external code to easily interpret them. See
    ``validate_environment`` to get an idea.
    """

    @property
    def succeed(self) -> bool:
        return all(tool.succeed for tool in self)

    def __str__(self):
        """Format basic and extended reports"""

        basic_report = ''
        for tool in self:
            tool_str = f"[{'ok' if tool.succeed else 'error':>5}]  {tool.name:<10}"
            if tool.remarks:
                tool_str += f"  {tool.remarks}"
            basic_report += f"{tool_str}\n"

        verbose_report = ''
        faulty_tools = [tool for tool in self if tool.error is not None]
        if len(faulty_tools):
            verbose_report += '\n\nTools output:\n\n'
            for tool in faulty_tools:
                verbose_report += f"{tool.name}\n    {tool.error}\n\n"

        return basic_report + verbose_report


def validate_environment(logger: stm32pio.core.log.Logger, config: stm32pio.core.config.ProjectConfig,
                         cubemx: stm32pio.core.cubemx.CubeMX) -> ToolsValidationResults:
    """
    Defines minimal runners enough to ensure that a tool works and execute them in the given project context gathering
    the results.

    :param logger: project' logger instance
    :param config: project config containing tools commands in its "app" section
    :param cubemx: project' CubeMX instance
    :return: validation results suitable for immediate printing
    """

    def java_runner(java_cmd):
        with stm32pio.core.log.LogPipe(logger, logging.DEBUG, accumulate=True) as log:
            completed_process = subprocess.run([java_cmd, '-version'], stdout=log.pipe, stderr=log.pipe)
        return completed_process, log.value

    def cubemx_runner(_):
        return cubemx.execute_script('exit\n')  # just start and exit

    def platformio_runner(platformio_cmd):
        with stm32pio.core.log.LogPipe(logger, logging.DEBUG, accumulate=True) as log:
            completed_process = subprocess.run([platformio_cmd], stdout=log.pipe, stderr=log.pipe)
        return completed_process, log.value

    if not config.path.exists():
        logger.warning("config file not found. Validation will be performed against the runtime configuration")

    return ToolsValidationResults(
        Tool(name=param,
             command=config.get('app', param),
             runner=runner,
             required=required,
             logger=logger).validate()
        for param, runner, required in [
            ('platformio_cmd', platformio_runner, True),
            ('cubemx_cmd', cubemx_runner, True),
            ('java_cmd', java_runner, False)
        ])
