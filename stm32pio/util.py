import logging
import pathlib
import shutil
import subprocess
import enum
import configparser
import string
import tempfile

import stm32pio.settings

logger = logging.getLogger('stm32pio.util')


# TODO: add states and check the current state for every operation (so we can't, for example, go to build stage without
#  a pio_init performed before). Also, it naturally helps us to construct the GUI in which we manage the list of
#  multiple projects. (use enum for this)
#  Also, we would probably need some method to detect a current project state on program start (or store it explicitly
#  in the dotted system file)
@enum.unique
class ProjectState(enum.IntEnum):
    """
    """
    UNDEFINED = enum.auto()
    GENERATED = enum.auto()
    PIO_INITIALIZED = enum.auto()
    PIO_INI_PATCHED = enum.auto()
    BUILT = enum.auto()


# NUM_OF_STATES = len(list(ProjectState))


class Stm32pio:
    """
    Main class
    """

    def __init__(self, dirty_path: str):
        self.project_path = self._resolve_project_path(dirty_path)
        self.config = self._load_settings_file()

        ioc_file = self._find_ioc_file()
        self.config.set('project', 'ioc_file', str(ioc_file))

        # self.config.set('project', 'state', str(self.get_state().value))

        cubemx_script_template = string.Template(self.config.get('project', 'cubemx_script_content'))
        cubemx_script_content = cubemx_script_template.substitute(project_path=self.project_path,
                                                                  cubemx_ioc_full_filename=str(ioc_file))
        self.config.set('project', 'cubemx_script_content', cubemx_script_content)

        self._save_config()


    def _save_config(self):
        with self.project_path.joinpath('stm32pio.ini').open(mode='w') as config_file:
            self.config.write(config_file)


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

        states_conditions = {
            ProjectState.UNDEFINED: [True],
            ProjectState.GENERATED: [self.project_path.joinpath('Inc').is_dir(),
                                     self.project_path.joinpath('Src').is_dir()],
            ProjectState.PIO_INITIALIZED: [self.project_path.joinpath('platformio.ini').is_file()],
            ProjectState.PIO_INI_PATCHED: [not self.project_path.joinpath('include').is_dir(),
                                           self.project_path.joinpath('platformio.ini').is_file() and
                                           self.config.get('project', 'platformio_ini_patch_content') in self.project_path.joinpath('platformio.ini').read_text()],
            ProjectState.BUILT: [self.project_path.joinpath('.pio').is_dir(),
                                 any([path.is_file() for path in self.project_path.joinpath('.pio').rglob('*firmware*')])]
        }

        # Use (1,0) instead of (True,False) because on debug printing it looks cleaner
        conditions_results = [1 if all(conditions is True for conditions in states_conditions[state]) else 0
                              for state in ProjectState]
        # Put away unnecessary processing as the string still will be formed even if the logging level doesn't allow
        # propagation of this message
        if logger.level <= logging.DEBUG:
            states_info_str = '\n'.join(f"{state.name:20}{conditions_results[state.value-1]}" for state in ProjectState)
            logger.debug(f"Determined states: {states_info_str}")

        last_true_index = 0
        for index, value in enumerate(conditions_results):
            if value == 1:
                last_true_index = index
            else:
                break

        project_state = ProjectState(last_true_index + 1) if 1 not in conditions_results[last_true_index + 1:] \
            else ProjectState.UNDEFINED  # edit there to get first approach from second

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
                raise FileNotFoundError("CubeMX project .ioc file")
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
        correct_path = pathlib.Path(dirty_path).expanduser().resolve()
        if not correct_path.exists():
            logger.error("incorrect project path")
            raise FileNotFoundError(correct_path)
        else:
            return correct_path


    def generate_code(self) -> None:
        """
        Call STM32CubeMX app as a 'java -jar' file with the automatically prearranged 'cubemx-script' file
        """

        # buffering=0 leads to the immediate flushing on writing
        with tempfile.NamedTemporaryFile(buffering=0) as cubemx_script:
            cubemx_script.write(self.config.get('project', 'cubemx_script_content').encode())

            logger.info("starting to generate a code from the CubeMX .ioc file...")
            command_arr = [self.config.get('app', 'java_cmd'), '-jar', self.config.get('app', 'cubemx_cmd'), '-q',
                           cubemx_script.name]
            if logger.level <= logging.DEBUG:
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


    def pio_init(self, board: str) -> None:
        """
        Call PlatformIO CLI to initialize a new project

        Args:
            board: string displaying PlatformIO name of MCU/board (from 'pio boards' command)
        """

        # Check board name
        logger.debug("searching for PlatformIO board...")
        result = subprocess.run([self.config.get('app', 'platformio_cmd'), 'boards'], encoding='utf-8',
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Or, for Python 3.7 and above:
        # result = subprocess.run(['platformio', 'boards'], encoding='utf-8', capture_output=True)
        if result.returncode == 0:
            if board not in result.stdout.split():
                logger.error("wrong STM32 board. Run 'platformio boards' for possible names")
                raise Exception("wrong STM32 board")
        else:
            logger.error("failed to start PlatformIO")
            raise Exception("failed to start PlatformIO")

        logger.info("starting PlatformIO project initialization...")
        command_arr = [self.config.get('app', 'platformio_cmd'), 'init', '-d', self.project_path, '-b', board,
                       '-O', 'framework=stm32cube']
        if logger.level > logging.DEBUG:
            command_arr.append('--silent')
        result = subprocess.run(command_arr)
        if result.returncode == 0:
            logger.info("successful PlatformIO project initialization")
        else:
            logger.error("PlatformIO project initialization error")
            raise Exception("PlatformIO error")


    def patch(self) -> None:
        """
        Patch platformio.ini file to use created earlier by CubeMX 'Src' and 'Inc' folders as sources
        """

        logger.debug("patching 'platformio.ini' file...")

        platformio_ini_file = self.project_path.joinpath('platformio.ini')
        if platformio_ini_file.is_file():
            with platformio_ini_file.open(mode='a') as f:
                f.write(self.config.get('project', 'platformio_ini_patch_content'))
            logger.info("'platformio.ini' patched")
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

        logger.info("starting an editor...")

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
        if logger.level > logging.DEBUG:
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
