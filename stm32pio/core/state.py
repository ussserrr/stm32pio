"""
State of the project in terms of business logic. It defines the sequence of some typical life-cycle stages a project can
sit in.
"""

import collections
import enum

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

    def __str__(self):
        """
        Pretty human-readable complete representation of the project state (not including the service one UNDEFINED to
        not confuse the end-user)
        """
        # Need 2 spaces between the icon and the text to look fine
        return '\n'.join(f"{'[*]' if stage_value else '[ ]'}  {str(stage_name)}"
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
