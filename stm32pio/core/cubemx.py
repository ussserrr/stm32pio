import difflib
import logging
import subprocess
import tempfile
from configparser import ConfigParser
from io import StringIO
from pathlib import Path
from string import Template
from typing import Tuple

import stm32pio.core.log
import stm32pio.core.settings
import stm32pio.core.util


# TODO: test case: text file given but not an .ioc (just some text)
class IocConfig(ConfigParser):
    """
    .ioc file structure is actually very similar to INI-style configs and can be managed by the ConfigParser with small
    tweaks
    """

    fake_section = 'me'
    header = ''

    def __init__(self, parent_path: Path, file_name: str, logger: stm32pio.core.log.Logger):
        self.logger = logger
        self.path = self._find_ioc_file(parent_path, file_name)
        super().__init__(interpolation=None)
        self.optionxform = lambda option: option  # do not modify the keys
        content = self.path.read_text()
        self.read_string(f'[{self.fake_section}]\n' + content)  # ConfigParser cannot handle headless configs
        self.header = stm32pio.core.util.extract_header_comment(content, comment_symbol='#')

    def _find_ioc_file(self, parent_path: Path, file_name: str) -> Path:
        """
        Find, check (that this is a non-empty text file) and return an .ioc file. If there are more than one - return
        first.

        Returns:
            absolute path to the .ioc file

        Raises:
            FileNotFoundError: no .ioc file is present
            ValueError: .ioc file is empty
        """

        # 2. Check the value from the config file
        if len(file_name) > 0:
            result_file = parent_path.joinpath(file_name).resolve(strict=True)
            self.logger.debug(f"using '{result_file.name}' file")

        # 3. Otherwise search for an appropriate file by yourself
        else:
            self.logger.debug("searching for any .ioc file...")
            candidates = list(parent_path.glob('*.ioc'))
            if len(candidates) == 0:  # TODO: Python 3.8: assignment expression feature
                raise FileNotFoundError("CubeMX project .ioc file")
            elif len(candidates) == 1:
                self.logger.debug(f"'{candidates[0].name}' is selected")
                result_file = candidates[0]
            else:
                self.logger.warning(f"there are multiple .ioc files, '{candidates[0].name}' is selected")
                result_file = candidates[0]

        # Check for the file correctness
        try:
            content = result_file.read_text()  # should be a text file
            if len(content) == 0:
                raise ValueError("the file is empty")
        except Exception as e:
            raise Exception(f"{result_file.name} is incorrect") from e

        return result_file

    def save(self):
        """
        Save the config back to its file (by overwriting it). This trying to introduce as little changes to the original
        content as possible, even prepending the initial "do not modify" line
        """
        fake_file = StringIO()
        self.write(fake_file, space_around_delimiters=False)
        config_text = fake_file.getvalue()
        self.path.write_text(
            (self.header if self.header else '') +
            config_text[config_text.index('\n') + 1:-1]  # remove fake section name (first line) and last \n
        )
        fake_file.close()

    def inspect(self, platformio_board: str = None, platformio_mcu: str = None):
        """
        Report some info about the current .ioc file state using given earlier logger instance. Note, that this method
        only looks for the options that should be *actively* tweaked, i.e. changed from the default values by a user.

        :param platformio_board: name to compare (i.e. nucleo_f031k6)
        :param platformio_mcu: name to compare (i.e. STM32F031K6T6)
        :return: None
        """

        s = self.fake_section

        if self.get(s, 'ProjectManager.TargetToolchain', fallback='') != 'Other Toolchains (GPDSC)':
            self.logger.warning('It is recommended to use value "Other Toolchains (GPDSC)" for parameter '
                                '"Project Manager –> Project -> Toolchain/IDE"')

        if self.getint(s, 'ProjectManager.LibraryCopy', fallback=None) != 1:
            self.logger.warning('It is recommended to set parameter '
                                '"Project Manager –> Code Generator –> Copy only the necessary library files"')

        if not self.getboolean(s, 'ProjectManager.CoupleFile', fallback=False):
            self.logger.warning('It is recommended to set parameter "Project Manager –> Code Generator –> '
                                'Generate peripheral initialization as a pair of \'.c/.h\' files per peripheral"')

        similarity_ratio_threshold = 0.8

        if self.get(s, 'board', fallback='') == 'custom' and platformio_mcu:
            device_id = self.get(s, 'ProjectManager.DeviceId', fallback='')
            if difflib.SequenceMatcher(
                a=device_id.lower(), b=platformio_mcu.lower()
            ).ratio() < similarity_ratio_threshold:
                self.logger.warning("Probably, there is a mismatch between CubeMX and PlatformIO MCUs:\n\t"
                                    f"{device_id} (CubeMX)   vs.   {platformio_mcu} (PlatformIO)")
        elif self.get(s, 'board', fallback='') != 'custom' and platformio_board:
            board = self.get(s, 'board', fallback='')
            if difflib.SequenceMatcher(
                a=board.lower(), b=platformio_board.lower()
            ).ratio() < similarity_ratio_threshold:
                self.logger.warning("Probably, there is a mismatch between CubeMX and PlatformIO boards:\n\t"
                                    f"{board} (CubeMX)   vs.   {platformio_board} (PlatformIO)")


class CubeMX:
    def __init__(self, work_dir: Path, ioc_file_name: str, exe_cmd: str, java_cmd: str,
                 logger: stm32pio.core.log.Logger):
        self.logger = logger
        self.work_dir = work_dir
        self.ioc = IocConfig(work_dir, ioc_file_name, logger)
        self.exe_cmd = exe_cmd
        self.java_cmd = java_cmd

    def execute_script(self, script_content: str) -> Tuple[subprocess.CompletedProcess, str]:
        """
        Call the STM32CubeMX app as 'java -jar' or directly to generate a code from the .ioc file. Pass the commands in
        a temp file.

        Returns:
            A tuple consisting of the subprocess.CompletedProcess and the full CubeMX output (both stdout and stderr
            combined)
        """

        # Use mkstemp() instead of higher-level API for compatibility with Windows (see tempfile docs for more details)
        cubemx_script_file, cubemx_script_name = tempfile.mkstemp()

        # We must remove the temp directory, so do not let any exception break our plans
        try:
            # buffering=0 leads to the immediate flushing on writing
            with open(cubemx_script_file, mode='w+b', buffering=0) as cubemx_script:
                cubemx_script.write(script_content.encode())  # should encode, since mode='w+b'

                command_arr = []
                # CubeMX can be invoked directly, without a need in Java command
                if self.java_cmd and (self.java_cmd.lower() not in stm32pio.core.settings.none_options):
                    command_arr += [self.java_cmd, '-jar']
                # -q: read the commands from the file, -s: silent performance
                command_arr += [self.exe_cmd, '-q', cubemx_script_name, '-s']
                # Redirect the output of the subprocess into the logging module (with DEBUG level)
                with stm32pio.core.log.LogPipe(self.logger, logging.DEBUG, accumulate=True) as log:
                    completed_process = subprocess.run(command_arr, stdout=log.pipe, stderr=log.pipe)
                    std_output = log.value

        except Exception as e:
            raise e  # re-raise an exception after the 'finally' block
        else:
            return completed_process, std_output
        finally:
            Path(cubemx_script_name).unlink()

    def generate_code(self, script_template: str) -> int:
        """
        Fill in the STM32CubeMX code generation script template from the project config and run it.

        Returns:
            completed process return code

        Raises:
            Exception: if the run failed (propagates from the inner call), if the return code is not 0, if any string
                indicating error was detected in the process output
        """

        self.logger.info("starting to generate a code from the CubeMX .ioc file...")

        cubemx_script_template = Template(script_template)
        # It's important to wrap paths into the quotation marks as they can contain whitespaces
        cubemx_script_content = cubemx_script_template.substitute(ioc_file_absolute_path=f'"{self.ioc.path}"',
                                                                  project_dir_absolute_path=f'"{self.work_dir}"')
        completed_process, std_output = self.execute_script(cubemx_script_content)

        error_msg = "code generation error"
        if completed_process.returncode == 0:
            if stm32pio.core.settings.cubemx_str_indicating_success in std_output:
                self.logger.info("successful code generation")
                return completed_process.returncode
            else:  # guessing
                error_lines = [line for line in std_output.splitlines(keepends=True)
                               if stm32pio.core.settings.cubemx_str_indicating_error in line]
                if len(error_lines):
                    self.logger.error(error_lines, from_subprocess=True)
                    raise Exception(error_msg)
                else:
                    self.logger.warning("Undefined result from the CubeMX (neither error or success symptoms were "
                                        "found in the logs). Keep going but there might be an error")
                    return completed_process.returncode
        else:
            # Most likely the 'java' error (e.g. no CubeMX is present)
            self.logger.error(f"Return code is {completed_process.returncode}", from_subprocess=True)
            if not self.logger.isEnabledFor(logging.DEBUG):
                # In DEBUG mode the output has already been printed
                self.logger.error(f"Output:\n{std_output}", from_subprocess=True)
            raise Exception(error_msg)
