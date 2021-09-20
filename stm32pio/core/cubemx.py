import configparser
import difflib
import io
import logging
import pathlib
import warnings


class IocConfig(configparser.ConfigParser):
    """
    .ioc file structure is actually very similar to INI-style configs and can be managed by the ConfigParser with small
    tweaks
    """

    fake_section = 'me'

    def __init__(self, path: pathlib.Path, logger: logging.Logger = None):
        self.path = path
        self.logger = logger
        super().__init__(interpolation=None)
        self.optionxform = lambda option: option  # do not modify the keys
        content = f'[{self.fake_section}]\n' + path.read_text()  # ConfigParser cannot handle headless configs
        self.read_string(content)

    def save(self):
        """
        Save the config back to its file (by overwriting it). This trying to introduce as little changes to the original
        content as possible, even prepending the initial "do not modify" line
        """
        fake_file = io.StringIO()
        self.write(fake_file, space_around_delimiters=False)
        config_text = fake_file.getvalue()
        self.path.write_text(
            "#MicroXplorer Configuration settings - do not modify\n" +
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

        if self.logger is None:
            warnings.warn(f".ioc file {self.path} inspection was requested "
                          "but no logger instance was provided during the construction phase")
            return

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
