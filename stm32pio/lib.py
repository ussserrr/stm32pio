import collections
import logging
import pathlib
import shutil
import subprocess
import enum
import configparser
import string
import sys
import tempfile
import traceback
import weakref

import stm32pio.settings

logger = logging.getLogger('stm32pio.util')


@enum.unique
class ProjectState(enum.IntEnum):
    """
    """
    UNDEFINED = enum.auto()
    INITIALIZED = enum.auto()
    GENERATED = enum.auto()
    PIO_INITIALIZED = enum.auto()
    PIO_INI_PATCHED = enum.auto()
    BUILT = enum.auto()


class Stm32pio:
    """
    Main class
    """

    def __init__(self, dirty_path: str, parameters=None, save_on_destruction=True):
        if parameters is None:
            parameters = {}

        self.project_path = self._resolve_project_path(dirty_path)
        self.config = self._load_settings_file()

        ioc_file = self._find_ioc_file()
        self.config.set('project', 'ioc_file', str(ioc_file))

        cubemx_script_template = string.Template(self.config.get('project', 'cubemx_script_content'))
        cubemx_script_content = cubemx_script_template.substitute(project_path=self.project_path,
            cubemx_ioc_full_filename=self.config.get('project', 'ioc_file'))
        self.config.set('project', 'cubemx_script_content', cubemx_script_content)

        board = ''
        if 'board' in parameters and parameters['board'] is not None:
            try:
                board = self._resolve_board(parameters['board'])
            except Exception as e:
                logger.warning(e)
            self.config.set('project', 'board', board)
        elif self.config.get('project', 'board', fallback=None) is None:
            self.config.set('project', 'board', board)

        if save_on_destruction:
            self._finalizer = weakref.finalize(self, self.save_config)


    def save_config(self):
        try:
            with self.project_path.joinpath('stm32pio.ini').open(mode='w') as config_file:
                self.config.write(config_file)
        except Exception as e:
            logger.warning(f"Cannot save config: {e}")
            if logger.getEffectiveLevel() <= logging.DEBUG:
                traceback.print_exception(*sys.exc_info())


    def get_state(self) -> ProjectState:
        """
        Hint: Files/folders to be present on every project state:
            generated:   ['Inc', 'Src', 'cubemx-script', 'stm32pio-test-project.ioc']
            pio initted: ['test', 'include', 'Inc', 'platformio.ini', '.gitignore', 'Src', 'cubemx-script', 'lib', 'stm32pio-test-project.ioc', '.travis.yml', 'src']
            patched:     ['test', 'Inc', 'platformio.ini', '.gitignore', 'Src', 'cubemx-script', 'lib', 'stm32pio-test-project.ioc', '.travis.yml']
            built:       ['.pio', 'test', 'Inc', 'platformio.ini', '.gitignore', 'Src', 'cubemx-script', 'lib', 'stm32pio-test-project.ioc', '.travis.yml'] +
                          .pio/build/nucleo_f031k6/firmware.bin, .pio/build/nucleo_f031k6/firmware.elf
        """

        logger.debug("Calculating project state...")
        logger.debug(f"Project content: {[item.name for item in self.project_path.iterdir()]}")

        states_conditions = collections.OrderedDict()
        states_conditions[ProjectState.UNDEFINED] = [True]
        states_conditions[ProjectState.INITIALIZED] = [self.project_path.joinpath('stm32pio.ini').is_file()]
        states_conditions[ProjectState.GENERATED] = [self.project_path.joinpath('Inc').is_dir() and
                                                     len(list(self.project_path.joinpath('Inc').iterdir())) > 0,
                                                     self.project_path.joinpath('Src').is_dir() and
                                                     len(list(self.project_path.joinpath('Src').iterdir())) > 0]
        states_conditions[ProjectState.PIO_INITIALIZED] = [
            self.project_path.joinpath('platformio.ini').is_file() and
            len(self.project_path.joinpath('platformio.ini').read_text()) > 0]
        states_conditions[ProjectState.PIO_INI_PATCHED] = [
            self.project_path.joinpath('platformio.ini').is_file() and
            self.config.get('project', 'platformio_ini_patch_content') in
            self.project_path.joinpath('platformio.ini').read_text(),
            not self.project_path.joinpath('include').is_dir()]
        states_conditions[ProjectState.BUILT] = [
            self.project_path.joinpath('.pio').is_dir() and
            any([item.is_file() for item in self.project_path.joinpath('.pio').rglob('*firmware*')])]

        # Use (1,0) instead of (True,False) because on debug printing it looks better
        conditions_results = []
        for state, conditions in states_conditions.items():
            conditions_results.append(1 if all(condition is True for condition in conditions) else 0)

        # Put away unnecessary processing as the string still will be formed even if the logging level doesn't allow
        # propagation of this message
        if logger.getEffectiveLevel() <= logging.DEBUG:
            states_info_str = '\n'.join(f"{state.name:20}{conditions_results[state.value-1]}" for state in ProjectState)
            logger.debug(f"Determined states:\n{states_info_str}")

        last_true_index = 0  # UNDEFINED is always True
        for index, value in enumerate(conditions_results):
            if value == 1:
                last_true_index = index
            else:
                break

        project_state = ProjectState.UNDEFINED
        if 1 not in conditions_results[last_true_index + 1:]:
            project_state = ProjectState(last_true_index + 1)

        return project_state


    def _find_ioc_file(self) -> pathlib.Path:
        """
        """

        ioc_file = self.config.get('project', 'ioc_file', fallback=None)
        if ioc_file:
            return pathlib.Path(ioc_file).resolve()
        else:
            logger.debug("Searching for any .ioc file...")
            candidates = list(self.project_path.glob('*.ioc'))
            if len(candidates) == 0:
                raise FileNotFoundError("Not found: CubeMX project .ioc file")
            elif len(candidates) == 1:
                logger.debug(f"{candidates[0].name} is selected")
                return candidates[0]
            else:
                logger.warning(f"There are multiple .ioc files, {candidates[0].name} is selected")
                return candidates[0]


    def _load_settings_file(self) -> configparser.ConfigParser:
        """
        """
        # logger.debug("Searching for any .ioc file...")
        stm32pio_ini = self.project_path.joinpath('stm32pio.ini')
        # if stm32pio_ini.is_file():
        config = configparser.ConfigParser()

        # Fill with default values
        config.read_dict(stm32pio.settings.config_default)
        # Then override by user values (if exist)
        config.read(str(stm32pio_ini))

        # for section in config.sections():
        #     print('=========== ' + section + ' ===========')
        #     for item in config.items(section):
        #         print(item)

        return config


    @staticmethod
    def _resolve_project_path(dirty_path: str) -> pathlib.Path:
        """
        Handle 'path/to/proj' and 'path/to/proj/', '.' (current directory) and other cases

        Args:
            dirty_path: some directory in the filesystem
        """
        resolved_path = pathlib.Path(dirty_path).expanduser().resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"Not found: {resolved_path}")
        else:
            return resolved_path


    def _resolve_board(self, board: str) -> str:
        """

        """
        logger.debug("searching for PlatformIO board...")
        result = subprocess.run([self.config.get('app', 'platformio_cmd'), 'boards'], encoding='utf-8',
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Or, for Python 3.7 and above:
        # result = subprocess.run(['platformio', 'boards'], encoding='utf-8', capture_output=True)
        if result.returncode == 0:
            if board not in result.stdout.split():
                raise Exception("wrong PlatformIO STM32 board. Run 'platformio boards' for possible names")
            else:
                return board
        else:
            raise Exception("failed to search for PlatformIO boards")


    def generate_code(self) -> None:
        """
        Call STM32CubeMX app as a 'java -jar' file with the automatically prearranged 'cubemx-script' file
        """

        # buffering=0 leads to the immediate flushing on writing
        with tempfile.NamedTemporaryFile(buffering=0) as cubemx_script:
            cubemx_script.write(self.config.get('project', 'cubemx_script_content').encode())

            logger.info("starting to generate a code from the CubeMX .ioc file...")
            command_arr = [self.config.get('app', 'java_cmd'), '-jar', self.config.get('app', 'cubemx_cmd'), '-q',
                           cubemx_script.name, '-s']
            if logger.getEffectiveLevel() <= logging.DEBUG:
                result = subprocess.run(command_arr)
            else:
                result = subprocess.run(command_arr, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # Or, for Python 3.7 and above:
                # result = subprocess.run(command_arr, capture_output=True)
            if result.returncode == 0:
                logger.info("successful code generation")
            else:
                logger.error(f"code generation error (CubeMX return code is {result.returncode}).\n"
                             "Try to enable a verbose output or generate a code from the CubeMX itself.")
                raise Exception("code generation error")


    def pio_init(self) -> int:
        """
        Call PlatformIO CLI to initialize a new project

        Args:
            board: string displaying PlatformIO name of MCU/board (from 'pio boards' command)
        """

        logger.info("starting PlatformIO project initialization...")

        command_arr = [self.config.get('app', 'platformio_cmd'), 'init', '-d', str(self.project_path), '-b', self.config.get('project', 'board'),
                       '-O', 'framework=stm32cube']
        if logger.getEffectiveLevel() > logging.DEBUG:
            command_arr.append('--silent')

        error_msg = "PlatformIO project initialization error"

        result = subprocess.run(command_arr, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            # PlatformIO returns 0 even on some errors ('platformio.ini' wasn't created, e.g. no '--board' argument)
            if 'ERROR' in result.stdout.upper():
                print(result.stdout)
                raise Exception(error_msg)
            if 'ERROR' in result.stderr.upper():
                print(result.stderr)
                raise Exception(error_msg)
            logger.info("successful PlatformIO project initialization")
            return result.returncode
        else:
            raise Exception(error_msg)


    def patch(self) -> None:
        """
        Patch platformio.ini file to use created earlier by CubeMX 'Src' and 'Inc' folders as sources
        """

        logger.debug("patching 'platformio.ini' file...")

        platformio_ini_file = self.project_path.joinpath('platformio.ini')
        if platformio_ini_file.is_file():
            with platformio_ini_file.open(mode='a') as f:
                f.write(self.config.get('project', 'platformio_ini_patch_content'))
            logger.info("'platformio.ini' has been patched")
        else:
            logger.warning("'platformio.ini' file not found")

        shutil.rmtree(self.project_path.joinpath('include'), ignore_errors=True)
        if not self.project_path.joinpath('SRC').is_dir():  # check for case sensitive file system
            shutil.rmtree(self.project_path.joinpath('src'), ignore_errors=True)


    def start_editor(self, editor_command: str) -> None:
        """
        Start the editor specified by 'editor_command' with the project opened

        Args:
            editor_command: editor command (as we start in the terminal)
        """

        logger.info(f"starting an editor '{editor_command}'...")

        try:
            subprocess.run([editor_command, self.project_path], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start the editor {editor_command}: {e.stderr}")


    def pio_build(self) -> int:
        """
        Initiate a build of the PlatformIO project by the PlatformIO ('run' command)

        Returns:
            0 if success, raise an exception otherwise
        """

        if self.project_path.joinpath('platformio.ini').is_file():
            logger.info("starting PlatformIO build...")
        else:
            logger.error("no 'platformio.ini' file, build is impossible")
            return -1

        command_arr = [self.config.get('app', 'platformio_cmd'), 'run', '-d', self.project_path]
        if logger.getEffectiveLevel() > logging.DEBUG:
            command_arr.append('--silent')
        result = subprocess.run(command_arr)
        if result.returncode == 0:
            logger.info("successful PlatformIO build")
            return result.returncode
        else:
            logger.error("PlatformIO build error")
            raise Exception("PlatformIO build error")


    def clean(self) -> None:
        """
        Clean-up the project folder and preserve only an '.ioc' file
        """

        for child in self.project_path.iterdir():
            if child.name != f"{self.project_path.name}.ioc":
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                    logger.debug(f"del {child}/")
                elif child.is_file():
                    child.unlink()
                    logger.debug(f"del {child}")

        logger.info("project has been cleaned")
