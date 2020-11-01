import collections
import configparser
import copy
import io
import logging
import pathlib
from typing import Mapping, Any, Union

import stm32pio.core.util
import stm32pio.core.settings


class Config(configparser.ConfigParser):
    def __init__(self, location: pathlib.Path, name: str = stm32pio.core.settings.config_file_name,
                 defaults: Mapping[str, Mapping[str, Any]] = stm32pio.core.settings.config_default,
                 runtime_parameters: Mapping[str, Mapping[str, Any]] = None, logger: logging.Logger = None):
        """
        Prepare ConfigParser config for the project. Order (priorities) of getting values (masking) (i.e. higher levels
        overwrites lower but only if a value is non-empty):

            default dict (settings module)  =>  config file stm32pio.ini  =>  user-given (runtime) values
                                                                              (via CLI or another way)

        Args:
            location: path to folder which contain (or should contain) the config file
            name: file name of the config
            defaults: mapping with the default values for the config (see schema above)
            runtime_parameters: another mapping to write (see schema above)
            logger: optional logging.Logger instance
        """
        super().__init__(interpolation=None)

        self.logger = logger
        self.path = location / name

        # Fill with default values ...
        self.read_dict(copy.deepcopy(defaults))

        # ... then merge with user's config file (if exist) values ...
        if self.logger:
            self.logger.debug(f"searching for {name}...")
        self.merge_with(self.path)

        # ... finally merge with the given in this session CLI parameters
        if runtime_parameters is not None and len(runtime_parameters):
            self.merge_with(runtime_parameters)

    def merge_with(self, another: Union[pathlib.Path, Mapping[str, Mapping[str, Any]]]) -> None:
        """
        Merge itself with some external thing. It is safe because the empty given values will not overwrite existing
        ones
        """
        if isinstance(another, pathlib.Path):
            temp_config = configparser.ConfigParser(interpolation=None)
            temp_config.read(another)
            temp_config_dict = stm32pio.core.util.configparser_to_dict(temp_config)
            temp_config_dict_cleaned = stm32pio.core.util.cleanup_dict(temp_config_dict)
            self.read_dict(temp_config_dict_cleaned)
        elif isinstance(another, collections.abc.Mapping):
            self.read_dict(stm32pio.core.util.cleanup_dict(another))
        else:
            raise TypeError(f"Cannot merge the given value of type {type(another)} to the config {self.path}. This "
                            "type isn't supported")

    def save(self, parameters: Mapping[str, Mapping[str, Any]] = None) -> int:
        """
        Preliminarily, updates the config with the given 'parameters' dictionary. It should has the following format:

            {
                'project': {
                    'board': 'nucleo_f031k6',
                    'ioc_file': 'fan_controller.ioc'
                },
                ...
            }

        Then writes itself to the file 'path' and logs using the logger.

        Returns:
            0 on success, -1 otherwise
        """

        if parameters is not None and len(parameters):
            self.merge_with(parameters)

        try:
            with self.path.open(mode='w') as config_file:
                self.write(config_file)
            if self.logger:
                self.logger.debug(f"{self.path.name} config file has been saved")
            return 0
        except Exception as e:
            if self.logger:
                self.logger.warning(f"cannot save the config: {e}", exc_info=self.logger.isEnabledFor(logging.DEBUG))
            return -1

    def __str__(self) -> str:
        """String representation"""
        fake_file = io.StringIO()
        self.write(fake_file)
        printed = fake_file.getvalue()
        fake_file.close()
        return printed
