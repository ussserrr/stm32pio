"""
Tweaked native ConfigParser entity attached to every stm32pio project.
"""

import collections.abc
import logging
from configparser import ConfigParser
from io import StringIO
from pathlib import Path
from typing import Mapping, Any, Union, List  # TODO: 3.9+: List is not needed anymore, just use standard list

import stm32pio.core.log
import stm32pio.core.settings
import stm32pio.core.util


ConfigMapping = Mapping[str, Mapping[str, Any]]  # in Python, *anything* can be converted to a string :)


class ProjectConfig(ConfigParser):
    """An ordinary ConfigParser with some additional functionality: getters, pretty printing, smart merging, ..."""

    def __init__(self, location: Path, logger: 'stm32pio.core.log.Logger',
                 name: str = stm32pio.core.settings.config_file_name,
                 defaults: ConfigMapping = stm32pio.core.settings.config_default,
                 runtime_parameters: ConfigMapping = None):
        """
        Setup a config for the project. Order of values masking (higher level non-empty values overwrites lower ones):

            default dict (settings.py)  =>  project file stm32pio.ini  =>  runtime provided values

        :param location: folder which contains (or should contain in the future) a config file (typically a project
        directory)
        :param logger: logging.Logger-compatible object
        :param name: config file name (typically with .INI extension)
        :param defaults: some mapping providing default values for the config
        :param runtime_parameters: another source of values with the highest priority
        """

        super().__init__(interpolation=None)

        self.logger = logger
        self.path = location / name

        # 1. Fill with default values ...
        self.read_dict(defaults)

        # 2. ... then merge with project's config file (if exist)...
        self.logger.debug(f"searching for {name} config...")
        self.merge_with(self.path, reason="compared to default")

        # 3. ... finally merge with some given runtime parameters (like from CLI or GUI)
        if runtime_parameters is not None:
            self.merge_with(runtime_parameters, reason="CLI keys")

    def get_ignore_list(self, section: str, option: str) -> List[Path]:
        """Custom getter similar to what built-in ones are providing (like ``getint()``/``getboolean()``...)"""
        ignore_list = []
        for entry in filter(lambda line: len(line) != 0,  # non-empty lines only
                            self.get(section, option, fallback='').splitlines()):
            ignore_list.extend(self.path.parent.glob(entry))
        return ignore_list

    def set_content_as_ignore_list(self):
        """
        When invoked, snapshotting the config directory' current content (relative, non-recursive) and sets it as the
        ``cleanup_ignore`` config option.
        """
        location = self.path.parent
        self.set('project', 'cleanup_ignore', '\n'.join(str(path.relative_to(location)) for path in location.iterdir()))
        self.logger.info("folder current contents has been set as cleanup_ignore list")

    def _log_whats_changed(self, compared_to: ConfigMapping,
                           log_string: str = "these config parameters will be overridden", reason: str = None) -> None:
        """
        Print a diff between the current state and given mapping (only in DEBUG mode).

        :param compared_to: some mapping (with same shape as ConfigParser) to compare
        :param log_string: prefix to put before the diff
        :param reason: optional comment about a cause of the requested merge
        """

        if self.logger.isEnabledFor(logging.DEBUG):
            whats_changed = []
            for section in compared_to.keys():
                for key, new_value in compared_to[section].items():
                    old_value = self.get(section, key, fallback=None)
                    if old_value != new_value:
                        old_value = old_value or "''"
                        if ('\n' in old_value) or ('\n' in new_value):
                            whats_changed.append(f"=== {section}.{key} ===\n{old_value}\n->\n{new_value}\n")
                        else:
                            whats_changed.append(f"=== {section}.{key} ===: {old_value} -> {new_value}")
            if len(whats_changed):
                overridden = '\n'.join(whats_changed)
                if reason is not None:
                    log_string += f" ({reason})"
                log_string += f":\n{overridden}"
                self.logger.debug(log_string)

    def merge_with(self, another: Union[Path, ConfigMapping], reason: str = None) -> None:
        """
        Merge itself with some external thing. Behavior is safe: empty values will not overwrite existing ones.

        :param another: path to config or a mapping
        :param reason: optional short description of a merge reason
        """
        if isinstance(another, Path):
            temp_config = ConfigParser(interpolation=None)
            temp_config.read(another)
            temp_config_dict_cleaned = stm32pio.core.util.cleanup_mapping(temp_config)
            self._log_whats_changed(temp_config_dict_cleaned, reason=reason,
                                    log_string=f"these config parameters will be overridden by {another}")
            self.read_dict(temp_config_dict_cleaned)
        elif isinstance(another, collections.abc.Mapping):
            self._log_whats_changed(another, reason=reason)
            self.read_dict(stm32pio.core.util.cleanup_mapping(another))
        else:
            raise TypeError(f"Cannot merge with value of type {type(another)}")

    def save(self, also_set_this: ConfigMapping = None) -> int:
        """
        Flush the config to file.

        :param also_set_this: optional mapping (with same shape as ConfigParser) to populate the config with
        :return: 0 on success, -1 otherwise
        """

        if also_set_this is not None and len(also_set_this):
            self.merge_with(also_set_this, reason="config file save was requested")

        try:
            with self.path.open(mode='w') as config_file:
                self.write(config_file)
            self.logger.debug(f"{self.path.name} config file has been saved")
            return 0
        except Exception as e:
            self.logger.warning(
                f"cannot save config: {e}",
                exc_info=self.logger.isEnabledFor(stm32pio.core.settings.show_traceback_threshold_level))
            return -1

    def __str__(self) -> str:
        """String representation (same as it will be stored in file)"""
        fake_file = StringIO()
        self.write(fake_file)
        printed = fake_file.getvalue()
        fake_file.close()
        return printed
