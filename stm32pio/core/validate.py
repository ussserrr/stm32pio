import logging
import subprocess
from typing import Optional, Callable, Tuple, List

import stm32pio.core.settings


class ToolValidator:
    """Verify some command line tool"""

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
            required: is this parameter mandatory?
            logger: optional logging.Logger instance to indicate the progress
        """
        # TODO: dataclass can be used (https://stackoverflow.com/questions/1389180/automatically-initialize-instance-variables)
        self.name = name
        self.command = command
        self.runner = runner
        self.required = required
        self.logger = logger

    def _run(self, command):
        """More like a _macro_ function to reduce a code repeating instead of a _real_ standalone method"""
        process, process_output = self.runner(command)
        self.succeed = process.returncode == 0
        if process.returncode != 0:
            self.error = Exception(process_output)

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
        """Format the results of contained members (basic report and extended if needed)"""

        basic_report = ''
        for tool in self:
            tool_str = f"[{'ok' if tool.succeed else 'error':>5}]  {tool.name:<10}"
            if tool.text:
                tool_str += f"  {tool.text}"
            basic_report += f"{tool_str}\n"

        verbose_report = ''
        errored_tools = [tool for tool in self if tool.error is not None]
        if len(errored_tools):
            verbose_report += '\n\nTools output:\n\n'
            for tool in errored_tools:
                verbose_report += f"{tool.name}\n    {tool.error}\n\n"

        return basic_report + verbose_report
