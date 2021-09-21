"""
State of the project in terms of business logic. It defines the sequence of some typical life-cycle stages a project can
sit in.
"""

import collections
import contextlib
import enum

import stm32pio.core.project

_stages_string_representations = {
    'UNDEFINED': 'The project is messed up',
    'EMPTY': '.ioc file is present',
    'INITIALIZED': 'stm32pio initialized',
    'GENERATED': 'CubeMX code generated',
    'PIO_INITIALIZED': 'PlatformIO project initialized',
    'PATCHED': 'PlatformIO project patched',
    'BUILT': 'PlatformIO project built'
}


@enum.unique
class ProjectStage(enum.IntEnum):
    """
    Codes indicating a project state at the moment. Should be the sequence of incrementing integers to be suited for
    state determining algorithm. Starts from 1.

    Hint: Files/folders to be present on every project state (more or less, just for reference):
        UNDEFINED: use this state to indicate none of the states below. Also, when we do not have any .ioc file the
                   Stm32pio class instance cannot be created (constructor raises an exception)
        EMPTY: ['project.ioc']
        INITIALIZED: ['project.ioc', 'stm32pio.ini']
        GENERATED: ['Inc', 'Src', 'project.ioc', 'stm32pio.ini']
        PIO_INITIALIZED (on case-sensitive FS): ['test', 'include', 'Inc', 'platformio.ini', '.gitignore', 'Src', 'lib',
                                                 'project.ioc', '.travis.yml', 'src']
        PATCHED: ['test', 'Inc', 'platformio.ini', '.gitignore', 'Src', 'lib', 'project.ioc', '.travis.yml']
        BUILT: same as above + '.pio' folder with build artifacts (such as .pio/build/nucleo_f031k6/firmware.bin,
                                                                           .pio/build/nucleo_f031k6/firmware.elf)
    """
    UNDEFINED = enum.auto()  # note: starts from 1
    EMPTY = enum.auto()
    INITIALIZED = enum.auto()
    GENERATED = enum.auto()
    PIO_INITIALIZED = enum.auto()
    PATCHED = enum.auto()
    BUILT = enum.auto()

    def __str__(self):
        return _stages_string_representations[self.name]


class ProjectState(collections.OrderedDict):
    """
    The ordered dictionary subclass suitable for storing the Stm32pio instances state. For example:
      {
        ProjectStage.UNDEFINED:         True,  # doesn't necessarily means that the project is messed up, see below
        ProjectStage.EMPTY:             True,
        ProjectStage.INITIALIZED:       True,
        ProjectStage.GENERATED:         False,
        ProjectStage.PIO_INITIALIZED:   False,
        ProjectStage.PATCHED:           False,
        ProjectStage.BUILT:             False
      }
    It is also extended with additional properties providing useful information such as obtaining the project current
    stage.

    The class has no special constructor so its filling - both stages and their order - is a responsibility of the
    external code. It also has no protection nor checks for its internal correctness. Anyway, it is intended to be used
    (i.e. creating) only by the internal code of this library so there shouldn't be any worries.
    """

    def __init__(self, project: 'stm32pio.core.project.Stm32pio'):
        """Constructing and returning the current state of the project (tweaked dict, see ProjectState docs)"""
        super().__init__()

        try:
            pio_is_initialized = project.platformio.ini.is_initialized
        except:  # we just want to know the status and don't care about the details
            pio_is_initialized = False

        platformio_ini_is_patched = False
        if pio_is_initialized:  # make no sense to proceed if there is something happened in the first place
            with contextlib.suppress(Exception):  # we just want to know the status and don't care about the details
                platformio_ini_is_patched = project.platformio.ini.is_patched

        inc_dir = project.path / 'Inc'
        src_dir = project.path / 'Src'
        include_dir = project.path / 'include'
        pio_dir = project.path / '.pio'

        # Create the temporary ordered dictionary and fill it with the conditions results arrays
        # TODO: dicts are insertion ordered (3.6+ CPython, 3.7+ language-wise)
        self[ProjectStage.UNDEFINED] = [True]
        self[ProjectStage.EMPTY] = [project.cubemx.ioc.path.is_file()]
        self[ProjectStage.INITIALIZED] = [project.config.path.is_file()]
        self[ProjectStage.GENERATED] = [inc_dir.is_dir() and len(list(inc_dir.iterdir())) > 0,
                                        src_dir.is_dir() and len(list(src_dir.iterdir())) > 0]
        self[ProjectStage.PIO_INITIALIZED] = [pio_is_initialized]
        self[ProjectStage.PATCHED] = [platformio_ini_is_patched, not include_dir.is_dir()]
        # Hidden folder. Can be not visible in your file manager and cause a confusion
        self[ProjectStage.BUILT] = [pio_dir.is_dir() and any(item.is_file() for item in pio_dir.rglob('*firmware*'))]

        # Fold arrays and save results in ProjectState instance
        for stage, conditions in self.items():
            self[stage] = all(conditions)

    def __str__(self):
        """
        Pretty human-readable complete representation of the project state (not including the service one UNDEFINED to
        not confuse the end-user)
        """
        # Need 2 spaces between the icon and the text to look fine
        return '\n'.join(f"{'[*]' if stage_value else '[ ]'}  {stage_name}"
                         for stage_name, stage_value in self.items() if stage_name != ProjectStage.UNDEFINED)

    @property
    def current_stage(self) -> ProjectStage:
        last_consistent_stage = ProjectStage.UNDEFINED
        not_fulfilled_stage_found = False

        # Search for a consecutive sequence of True's and find the last of them. For example, if the array is
        #   [1,1,1,0,0,0,0]
        #        ^
        # we should consider 2 as the last index
        for stage_name, stage_fulfilled in self.items():
            if stage_fulfilled:
                if not_fulfilled_stage_found:
                    # Fall back to the UNDEFINED stage if we have breaks in conditions results array. E.g., for
                    #   [1,1,1,0,1,0,0]
                    # we should return UNDEFINED as it doesn't look like a correct set of files actually
                    last_consistent_stage = ProjectStage.UNDEFINED
                    break
                else:
                    last_consistent_stage = stage_name
            else:
                not_fulfilled_stage_found = True

        return last_consistent_stage

    @property
    def is_consistent(self) -> bool:
        """Whether the state has been went through the stages consequentially or not"""
        return self.current_stage != ProjectStage.UNDEFINED
