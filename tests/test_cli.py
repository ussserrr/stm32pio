import configparser
import contextlib
import io
import pathlib
import re
import subprocess
import unittest.mock

import stm32pio.app
import stm32pio.lib
import stm32pio.settings

# Provides test constants
from tests.test import *


class TestCLI(CustomTestCase):
    """
    Some tests to mimic the behavior of end-user tasks (CLI commands such as 'new', 'clean', etc.). Run main function
    passing the arguments to it but sometimes even run as subprocess (to capture actual STDOUT/STDERR output)
    """

    def test_clean(self):
        for case in ['--quiet', 'yes', 'no']:
            with self.subTest(case=case):
                # Create files and folders
                test_file = FIXTURE_PATH.joinpath('test.file')
                test_dir = FIXTURE_PATH.joinpath('test.dir')
                test_file.touch(exist_ok=False)
                test_dir.mkdir(exist_ok=False)

                # Clean ...
                if case == '--quiet':
                    return_code = stm32pio.app.main(sys_argv=['clean', case, '-d', str(FIXTURE_PATH)])
                else:
                    with unittest.mock.patch('builtins.input', return_value=case):
                        return_code = stm32pio.app.main(sys_argv=['clean', '-d', str(FIXTURE_PATH)])

                self.assertEqual(return_code, 0, msg="Non-zero return code")

                # ... look for remaining items ...
                if case == 'no':
                    with self.subTest():
                        self.assertTrue(test_file.is_file(), msg=f"{test_file} has been deleted")
                    with self.subTest():
                        self.assertTrue(test_dir.is_dir(), msg=f"{test_dir}/ has been deleted")
                else:
                    with self.subTest():
                        self.assertFalse(test_file.is_file(), msg=f"{test_file} is still there")
                    with self.subTest():
                        self.assertFalse(test_dir.is_dir(), msg=f"{test_dir}/ is still there")

                # ... and .ioc file should be preserved in any case
                with self.subTest():
                    self.assertTrue(FIXTURE_PATH.joinpath(f"{FIXTURE_PATH.name}.ioc").is_file(),
                                    msg="Missing .ioc file")

    def test_new(self):
        """
        Successful build is the best indicator that all went right so we use '--with-build' option here
        """
        return_code = stm32pio.app.main(sys_argv=['new', '-d', str(FIXTURE_PATH), '-b', TEST_PROJECT_BOARD,
                                                  '--with-build'])
        self.assertEqual(return_code, 0, msg="Non-zero return code")

        # .ioc file should be preserved
        self.assertTrue(FIXTURE_PATH.joinpath(f"{FIXTURE_PATH.name}.ioc").is_file(), msg="Missing .ioc file")

    def test_generate(self):
        return_code = stm32pio.app.main(sys_argv=['generate', '-d', str(FIXTURE_PATH)])
        self.assertEqual(return_code, 0, msg="Non-zero return code")

        for directory in ['Inc', 'Src']:
            with self.subTest():
                self.assertTrue(FIXTURE_PATH.joinpath(directory).is_dir(), msg=f"Missing '{directory}'")
                self.assertNotEqual(len(list(FIXTURE_PATH.joinpath(directory).iterdir())), 0,
                                    msg=f"'{directory}' is empty")

        # .ioc file should be preserved
        self.assertTrue(FIXTURE_PATH.joinpath(f"{FIXTURE_PATH.name}.ioc").is_file(), msg="Missing .ioc file")

    def test_incorrect_path_should_log_error(self):
        """
        We should see an error log message and non-zero return code
        """
        path_not_exist = pathlib.Path('path_some_uniq_name/does/not/exist')

        with self.assertLogs(level='ERROR') as logs:
            return_code = stm32pio.app.main(sys_argv=['init', '-d', str(path_not_exist)])
            self.assertNotEqual(return_code, 0, msg="Return code should be non-zero")
            # Actual text may vary and depends on OS and system language so we check only for a part of path string
            self.assertTrue(next((True for message in logs.output if 'path_some_uniq_name' in message.lower()), False),
                            msg="'ERROR' logging message hasn't been printed")

    def test_no_ioc_file_should_log_error(self):
        """
        We should see an error log message and non-zero return code
        """
        dir_with_no_ioc_file = FIXTURE_PATH.joinpath('dir.with.no.ioc.file')
        dir_with_no_ioc_file.mkdir(exist_ok=False)

        with self.assertLogs(level='ERROR') as logs:
            return_code = stm32pio.app.main(sys_argv=['init', '-d', str(dir_with_no_ioc_file)])
            self.assertNotEqual(return_code, 0, msg="Return code should be non-zero")
            self.assertTrue(next((True for message in logs.output if FileNotFoundError.__name__ in message), False),
                            msg="'ERROR' logging message hasn't been printed")

    def test_verbose(self):
        """
        Capture the full output. Check for both 'DEBUG' logging messages and STM32CubeMX CLI output. Verbose logs format
        should match such a regex:

            ^(?=(DEBUG|INFO|WARNING|ERROR|CRITICAL) {0,4})(?=.{8} (?=(build|pio_init|...) {0,26})(?=.{26} [^ ]))
        """

        # inspect.getmembers() is great but it triggers class properties to execute leading to the unwanted code
        # execution
        methods = dir(stm32pio.lib.Stm32pio) + ['main']

        buffer_stdout, buffer_stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buffer_stdout), contextlib.redirect_stderr(buffer_stderr):
            return_code = stm32pio.app.main(sys_argv=['-v', 'new', '-d', str(FIXTURE_PATH), '-b', TEST_PROJECT_BOARD])

        self.assertEqual(return_code, 0, msg="Non-zero return code")
        # stderr and not stdout contains the actual output (by default for the logging module)
        self.assertEqual(len(buffer_stdout.getvalue()), 0,
                         msg="Process has printed something directly into STDOUT bypassing logging")
        self.assertIn('DEBUG', buffer_stderr.getvalue(), msg="Verbose logging output hasn't been enabled on STDERR")

        # Inject all methods' names in the regex. Inject the width of field in a log format string
        regex = re.compile("^(?=(DEBUG) {0,4})(?=.{8} (?=(" + '|'.join(methods) + ") {0," +
                           str(stm32pio.settings.log_fieldwidth_function) + "})(?=.{" +
                           str(stm32pio.settings.log_fieldwidth_function) + "} [^ ]))", flags=re.MULTILINE)
        self.assertGreaterEqual(len(re.findall(regex, buffer_stderr.getvalue())), 1,
                                msg="Logs messages doesn't match the format")

        # The snippet of the actual STM32CubeMX output
        self.assertIn("Starting STM32CubeMX", buffer_stderr.getvalue(), msg="STM32CubeMX has not printed its logs")

    def test_non_verbose(self):
        """
        Capture the full output. We should not see any 'DEBUG' logging messages or STM32CubeMX CLI output. Logs format
        should match such a regex:

            ^(?=(INFO) {0,4})(?=.{8} ((?!( |build|pio_init|...))))
        """

        # inspect.getmembers is great but it triggers class properties leading to the unacceptable code execution
        methods = dir(stm32pio.lib.Stm32pio) + ['main']

        buffer_stdout, buffer_stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buffer_stdout), contextlib.redirect_stderr(buffer_stderr):
            return_code = stm32pio.app.main(sys_argv=['generate', '-d', str(FIXTURE_PATH)])

        self.assertEqual(return_code, 0, msg="Non-zero return code")
        # stderr and not stdout contains the actual output (by default for the logging module)
        self.assertNotIn('DEBUG', buffer_stderr.getvalue(), msg="Verbose logging output has been enabled on stderr")
        self.assertEqual(len(buffer_stdout.getvalue()), 0, msg="All app output should flow through the logging module")

        regex = re.compile("^(?=(INFO) {0,4})(?=.{8} ((?!( |" + '|'.join(methods) + "))))", flags=re.MULTILINE)
        self.assertGreaterEqual(len(re.findall(regex, buffer_stderr.getvalue())), 1,
                                msg="Logs messages doesn't match the format")

        # The snippet of the actual STM32CubeMX output
        self.assertNotIn('Starting STM32CubeMX', buffer_stderr.getvalue(), msg="STM32CubeMX has printed its logs")

    def test_init(self):
        """
        Check for config creation and parameters presence
        """
        result = subprocess.run([PYTHON_EXEC, STM32PIO_MAIN_SCRIPT, 'init', '-d', str(FIXTURE_PATH),
                                 '-b', TEST_PROJECT_BOARD], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.assertEqual(result.returncode, 0, msg="Non-zero return code")

        self.assertTrue(FIXTURE_PATH.joinpath(stm32pio.settings.config_file_name).is_file(),
                        msg=f"{stm32pio.settings.config_file_name} file hasn't been created")

        config = configparser.ConfigParser(interpolation=None)
        config.read(str(FIXTURE_PATH.joinpath(stm32pio.settings.config_file_name)))
        for section, parameters in stm32pio.settings.config_default.items():
            for option, value in parameters.items():
                with self.subTest(section=section, option=option, msg="Section/key is not found in saved config file"):
                    self.assertIsNotNone(config.get(section, option, fallback=None))
        self.assertEqual(config.get('project', 'board', fallback="Not found"), TEST_PROJECT_BOARD,
                         msg="'board' has not been set")

    def test_status(self):
        """
        Test the output returning by the app on a request to the 'status' command
        """

        buffer_stdout = io.StringIO()
        with contextlib.redirect_stdout(buffer_stdout), contextlib.redirect_stderr(None):
            return_code = stm32pio.app.main(sys_argv=['status', '-d', str(FIXTURE_PATH)])

        self.assertEqual(return_code, 0, msg="Non-zero return code")

        matches_counter = 0
        last_stage_pos = -1
        for stage in stm32pio.lib.ProjectStage:
            if stage != stm32pio.lib.ProjectStage.UNDEFINED:
                match = re.search(r"^((\[ \])|(\[\*\])) {2}" + str(stage) + '$', buffer_stdout.getvalue(), re.MULTILINE)
                self.assertTrue(match, msg="Status information was not found on STDOUT")
                if match:
                    matches_counter += 1
                    self.assertGreater(match.start(), last_stage_pos, msg="The order of stages is messed up")
                    last_stage_pos = match.start()

        self.assertEqual(matches_counter, len(stm32pio.lib.ProjectStage) - 1)
