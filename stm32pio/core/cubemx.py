"""
Module outsourcing most of the STM32CubeMX-related logic.
"""

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


class IocConfig(ConfigParser):
    """
    .ioc file structure is actually very similar to traditional INI-style configs and can be managed by the
    ``ConfigParser`` with small tweaks
    """

    fake_section_name = 'ioc'
    header = ''

    def __init__(self, parent_path: Path, file_name: str, logger: stm32pio.core.log.Logger):
        """
        Concentrate a CubeMX .ioc-file-related logic. As such file is a fundamental piece of every stm32pio project,
        this constructor throws in case of an absent or incorrect one.

        :param parent_path: project folder
        :param file_name: expected file name
        :param logger: logging.Logger-compatible object
        """
        super().__init__(interpolation=None)
        self.logger = logger
        self.path, content = self._find_ioc_file(parent_path, file_name)
        self.optionxform = lambda option: option  # do not modify keys
        self.read_string(f'[{IocConfig.fake_section_name}]\n' + content)  # ConfigParser cannot handle headless configs
        self.header = stm32pio.core.util.extract_header_comment(content, comment_symbol='#')

    def _find_ioc_file(self, parent_path: Path, file_name: str) -> Tuple[Path, str]:
        """
        Find and perform a basic correctness check of a CubeMX project .ioc file. Different scenarios are considered.
        Read and return raw string content for further usage.

        :param parent_path: project folder
        :param file_name: expected file name
        :return: absolute path and the file content
        """

        if file_name:  # if file is given, check its existence...
            result_file = parent_path.joinpath(file_name).resolve(strict=True)
            self.logger.debug(f"using '{result_file.name}' file")
        else:  # ...otherwise search for a file in the containing directory
            self.logger.debug("searching for .ioc file...")
            candidates = list(parent_path.glob('*.ioc'))
            if len(candidates) == 0:  # TODO: Python 3.8: assignment expression feature
                raise FileNotFoundError("CubeMX project .ioc file")
            elif len(candidates) == 1:
                self.logger.debug(f"'{candidates[0].name}' is selected")
            else:
                self.logger.warning(f"there are multiple .ioc files, '{candidates[0].name}' is selected")
            result_file = candidates[0]

        try:
            content = result_file.read_text()  # should be a non-empty text file
            if len(content) == 0:
                raise ValueError("file is empty")
        except Exception as e:
            raise Exception("file is incorrect") from e
        else:
            return result_file, content

    def save(self):
        """
        Save the config back to its file (by overwriting it). This trying to introduce as little changes to the original
        content as possible, even prepending the initial "do not modify" notice
        """
        fake_file = StringIO()
        self.write(fake_file, space_around_delimiters=False)
        config_text = fake_file.getvalue()
        self.path.write_text(
            (self.header if self.header else '') +  # restore a header
            config_text[config_text.index('\n') + 1:-1])  # remove fake section (first line) and last \n
        fake_file.close()

    def inspect(self, platformio_board: str = None, platformio_mcu: str = None):
        """
        Report some info about the .ioc file current state. This method looks only for options that should be *actively*
        tweaked (i.e. changed from the default values by a user) in order for project to be compatible with PlatformIO
        (see README and CLI usage example).

        :param platformio_board: name to compare (i.e. nucleo_f031k6)
        :param platformio_mcu: name to compare (i.e. STM32F031K6T6)
        """

        s = IocConfig.fake_section_name  # just for a short variable name

        def w(message: str):
            self.logger.warning(self.path.name + ': ' + message)

        if self.get(s, 'ProjectManager.TargetToolchain', fallback='') != 'Other Toolchains (GPDSC)':
            w('It is recommended to use value "Other Toolchains (GPDSC)" for parameter '
              '"Project Manager –> Project -> Toolchain/IDE"')

        if self.getint(s, 'ProjectManager.LibraryCopy', fallback=None) != 1:
            w('It is recommended to set parameter '
              '"Project Manager –> Code Generator –> Copy only the necessary library files"')

        if not self.getboolean(s, 'ProjectManager.CoupleFile', fallback=False):
            w('It is recommended to set parameter "Project Manager –> '
              'Code Generator –> Generate peripheral initialization as a pair of \'.c/.h\' files per peripheral"')

        similarity_threshold = 0.8

        if self.get(s, 'board', fallback='') == 'custom' and platformio_mcu:
            device_id = self.get(s, 'ProjectManager.DeviceId', fallback='')
            if difflib.SequenceMatcher(a=device_id.lower(), b=platformio_mcu.lower()).ratio() < similarity_threshold:
                self.logger.warning("Probably, there is a mismatch between CubeMX and PlatformIO MCUs:\n\t"
                                    f"{device_id} (CubeMX)   vs.   {platformio_mcu} (PlatformIO)")
        elif self.get(s, 'board', fallback='') != 'custom' and platformio_board:
            board = self.get(s, 'board', fallback='')
            if difflib.SequenceMatcher(a=board.lower(), b=platformio_board.lower()).ratio() < similarity_threshold:
                self.logger.warning("Probably, there is a mismatch between CubeMX and PlatformIO boards:\n\t"
                                    f"{board} (CubeMX)   vs.   {platformio_board} (PlatformIO)")


class CubeMX:
    """Interface to interact with the STM32CubeMX program"""

    def __init__(self, work_dir: Path, ioc_file_name: str, exe_cmd: str, logger: stm32pio.core.log.Logger,
                 java_cmd: str = None):
        """
        :param work_dir: project folder
        :param ioc_file_name: expected .ioc file name (can be found automatically if not given)
        :param exe_cmd: path to the CubeMX executable binary
        :param logger: logging.Logger-compatible object
        :param java_cmd: optional JRE executable (newer CubeMX versions doesn't need that)
        """
        self.logger = logger
        self.work_dir = work_dir
        self.ioc = IocConfig(work_dir, ioc_file_name, logger)  # represents project .ioc file config
        self.exe_cmd = exe_cmd
        self.java_cmd = java_cmd

    def execute_script(self, script_content: str) -> Tuple[subprocess.CompletedProcess, str]:
        """
        CubeMX can be fed with the script file to read commands from (see PDF manual). This method manages a temp file
        for such script.

        :param script_content: multi-line string
        :return: tuple of subprocess.CompletedProcess instance and recorded STDOUT output
        """

        # TODO: This, probably, needs to be investigated in the future
        # Use mkstemp() instead of higher-level API for compatibility with Windows (see tempfile docs for more details)
        cubemx_script_file, cubemx_script_name = tempfile.mkstemp()

        # We should remove a temp directory yourself, so do not let any exception break our plans
        try:
            # buffering=0 leads to the immediate flushing on writing
            with open(cubemx_script_file, mode='w+b', buffering=0) as cubemx_script:
                cubemx_script.write(script_content.encode())  # should encode since mode='w+b'

                command_arr = []
                # CubeMX can be invoked directly or through the JRE
                if self.java_cmd and (self.java_cmd.lower() not in stm32pio.core.settings.none_options):
                    command_arr += [self.java_cmd, '-jar']
                command_arr += [self.exe_cmd, '-q',  # read commands from file
                                cubemx_script_name, '-s']  # no splash screen
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
        Initiate a code generation process using CubeMX CLI. As of yet, results of this action differs when invoked from
        CLI and GUI (folders structure).

        :param script_template: string.Template compatible string to fill with necessary paths
        :return: completed process return code
        """

        self.logger.info("starting to generate a code from the CubeMX .ioc file...")

        cubemx_script_template = Template(script_template)
        # It's important to wrap paths into quotation marks as they can contain whitespaces
        cubemx_script_content = cubemx_script_template.substitute(ioc_file_absolute_path=f'"{self.ioc.path}"',
                                                                  project_dir_absolute_path=f'"{self.work_dir}"')
        completed_process, std_output = self.execute_script(cubemx_script_content)

        error_msg = "code generation error"
        if completed_process.returncode == 0:
            if stm32pio.core.settings.cubemx_str_indicating_success in std_output:
                self.logger.info("successful code generation")
                return completed_process.returncode
            else:  # strictly speaking, here we're just guessing
                error_lines = [line for line in std_output.splitlines(keepends=True)
                               if stm32pio.core.settings.cubemx_str_indicating_error in line]
                if len(error_lines):
                    self.logger.error(''.join(error_lines), from_subprocess=True)
                    raise Exception(error_msg)
                else:
                    self.logger.warning("Unclear CubeMX code generation results (neither error or success symptoms "
                                        "were found in logs). Keep going but there might be errors...")
                    return completed_process.returncode
        else:
            # Most likely, Java error (e.g. no CubeMX is present)
            self.logger.error(f"Return code is {completed_process.returncode}", from_subprocess=True)
            if not self.logger.isEnabledFor(logging.DEBUG):
                # In DEBUG mode the output has already been printed
                self.logger.error(f"Output:\n{std_output}", from_subprocess=True)
            raise Exception(error_msg)
