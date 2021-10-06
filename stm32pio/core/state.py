"""
stm32pio project state in terms of business logic. It defines the sequence of some typical life-cycle stages a project
can sit in and the logic to inspect them.
"""

import collections
import contextlib
import enum

import stm32pio.core.project


@enum.unique
class ProjectStage(enum.IntEnum):
    """
    Each code represents some attribute of the project. Their combination summarizes a state the project is being in
    right now. Enum should be an integer numbers sequence so different comparing algorithms can be applied to it. Rough
    list of different files/folders characterizing every stage (follow down to trace the project evolution):

        UNDEFINED: special pseudo-stage. It is always fulfilled but when this is a *only* satisfied stage, it means the
        project is messed up and some stages were skipped on the way up to the last one
        EMPTY: project.ioc
        INITIALIZED: project.ioc, stm32pio.ini
        GENERATED: Inc/, Src/, project.ioc, stm32pio.ini
        PIO_INITIALIZED (for case-sensitive systems): include/, Inc/, lib/, src/, Src/, test/, .gitignore,
                                                      platformio.ini, project.ioc, stm32pio.ini
        PATCHED: Inc/, lib/, Src/, test/, .gitignore, platformio.ini *(modified)*, project.ioc, stm32pio.ini
        BUILT: *same as above* + .pio/ folder carrying build artifacts (such as .pio/build/nucleo_f031k6/firmware.bin)
    """

    UNDEFINED = enum.auto()  # note: starts from 1
    EMPTY = enum.auto()
    INITIALIZED = enum.auto()
    GENERATED = enum.auto()
    PIO_INITIALIZED = enum.auto()
    PATCHED = enum.auto()
    BUILT = enum.auto()

    def __str__(self):
        return _stages_string_representations[self]


_stages_string_representations = {
    ProjectStage.UNDEFINED: 'The project is messed up',
    ProjectStage.EMPTY: '.ioc file is present',
    ProjectStage.INITIALIZED: 'stm32pio initialized',
    ProjectStage.GENERATED: 'CubeMX code generated',
    ProjectStage.PIO_INITIALIZED: 'PlatformIO project initialized',
    ProjectStage.PATCHED: 'PlatformIO project patched',
    ProjectStage.BUILT: 'PlatformIO project built'
}


# TODO: 3.6+ CPython, 3.7+ language-wise: dicts are insertion ordered already
class ProjectState(collections.OrderedDict):

    def __init__(self, project: 'stm32pio.core.project.Stm32pio'):
        """
        Defines criteria for every ``ProjectStage`` and evaluate all of them for the given ``Stm32pio`` project.
        Resulting dictionary will be a state object with ``ProjectStage`` keys and boolean values denoting whether a
        particular stage has been fulfilled. Items order is always the same declaring a typical project life-cycle with
        ``EMPTY`` stage at the start and ``BUILT`` one in the end.
        **Important**: the class doesn't track a project and acts as a snapshot of its current state. Use
        ``Stm32pio.state`` to obtain the actual information whenever you need to.

        :param project: stm32pio project to calculate the state for
        """

        super().__init__()

        #
        # 1. Gather and prepare some data
        #
        try:  # there might be no platformio.ini file yet
            pio_is_initialized = project.platformio.ini.is_initialized
        except (Exception,):
            pio_is_initialized = False

        platformio_ini_is_patched = False
        if pio_is_initialized:  # there might be no platformio.ini file yet
            # The getter below is designed to throw in certain circumstances but we don't care about the details here
            with contextlib.suppress(Exception):
                platformio_ini_is_patched = project.platformio.ini.is_patched

        inc_dir = project.path / 'Inc'
        src_dir = project.path / 'Src'
        include_dir = project.path / 'include'
        pio_dir = project.path / '.pio'  # hidden PlatformIO per-project-based service folder

        #
        # 2. For each ProjectStage define the criteria a project should met to be considered fulfilling this particular
        # stage
        #
        self[ProjectStage.UNDEFINED] = [True]  # always satisfied, see ProjectStage.UNDEFINED description
        self[ProjectStage.EMPTY] = [project.cubemx.ioc.path.is_file()]  # IOC file is present
        self[ProjectStage.INITIALIZED] = [project.config.path.is_file()]  # stm32pio.ini config file has been saved
        self[ProjectStage.GENERATED] = [inc_dir.is_dir() and len(list(inc_dir.iterdir())),
                                        src_dir.is_dir() and len(list(src_dir.iterdir()))]  # code has been generated
        self[ProjectStage.PIO_INITIALIZED] = [pio_is_initialized]  # platformio.ini file is present
        # Analyze platformio.ini file and look for junk folders
        self[ProjectStage.PATCHED] = [platformio_ini_is_patched, not include_dir.exists()]
        # Search for a build artifacts
        self[ProjectStage.BUILT] = [pio_dir.is_dir() and any(item.is_file() for item in pio_dir.rglob('*firmware*'))]

        #
        # 3. Evaluate and fold all conditions above to take the final form
        #
        for stage, conditions in self.items():
            self[stage] = all(conditions)

    def __str__(self):
        """Pretty human-readable representation (doesn't include the UNDEFINED service stage)"""
        return '\n'.join(f"{'[*]' if stage_value else '[ ]'}  {stage_name}"
                         for stage_name, stage_value in self.items() if stage_name != ProjectStage.UNDEFINED)

    @property
    def current_stage(self) -> ProjectStage:
        """
        Normally, the project goes through life-cycle phases consequentially fulfilling the stages one by one. The last
        satisfied stage in this case we call a *consistent* one. But if there are breaks happening along the regular
        trip we consider such state as inconsistent and saying the project is "messed up" (e.g. when some files were
        manually moved). This scenario is reflected by the special UNDEFINED stage.

        :return: the last consistent stage or ``ProjectStage.UNDEFINED`` if there is no such
        """
        # The algorithm below is probably the most time and memory efficient. It definitely can be shorter with a
        # drawback of being slower/more consuming

        last_consistent_stage = ProjectStage.UNDEFINED  # this one is always satisfied
        not_fulfilled_stage_found = False

        # Look for a consecutive sequence of True's and find the last of them. For example, if the array is
        #   [1,1,1,0,0,0,0]
        #        ^
        # we should consider 2 as the last index
        for stage_name, stage_is_fulfilled in self.items():
            if stage_is_fulfilled:
                if not_fulfilled_stage_found:
                    # Fallback to the UNDEFINED stage if we have breaks in conditions results array. E.g., for
                    #   [1,1,1,0,0,1,0]
                    # we should return UNDEFINED as it doesn't look like a correct set
                    last_consistent_stage = ProjectStage.UNDEFINED
                    break
                else:
                    last_consistent_stage = stage_name
            else:
                not_fulfilled_stage_found = True

        return last_consistent_stage

    @property
    def is_consistent(self) -> bool:
        """See ``current_stage`` for the *"consistency"* definition"""
        return self.current_stage != ProjectStage.UNDEFINED
