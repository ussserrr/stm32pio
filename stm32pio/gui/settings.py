import logging
from typing import Mapping, Any, List, Callable
import warnings

from PySide2.QtCore import QSettings, Slot

import stm32pio.gui.log


class Settings(QSettings):
    """
    Extend the class by useful get/set methods allowing to avoid redundant code lines and also are callable from the
    QML side
    """

    DEFAULTS = {
        'editor': '',
        'verbose': False,
        'notifications': True  # TODO: rename to use_notifications?
    }

    def __init__(self, prefix: str, defaults: Mapping[str, Any] = None, qs_args: List[Any] = None,
                 qs_kwargs: Mapping[str, Any] = None, external_triggers: Mapping[str, Callable[[Any], Any]] = None):
        """
        Args:
            prefix: this prefix will always be added when get/set methods will be called so use it to group some most
                important preferences under a single name. For example, prefix='app/params' while the list of users is
                located in 'app/users'
            defaults: mapping of fallback values (under the prefix mentioned above) that will be used if there is no
                matching key in the storage
            qs_args: positional arguments that will be passed to the QSettings constructor
            qs_kwargs: keyword arguments that will be passed to the QSettings constructor
            external_triggers: mapping where the keys are parameters names (under the prefix) and the values are
                functions that will be called with the corresponding parameter value as the argument when the parameter
                is going to be set. It's useful to setup the additional actions needed to be performed right after
                a certain parameter gets an update
        """

        qs_args = qs_args if qs_args is not None else []
        qs_kwargs = qs_kwargs if qs_kwargs is not None else {}

        super().__init__(*qs_args, **qs_kwargs)

        self.prefix = prefix
        defaults = defaults if defaults is not None else Settings.DEFAULTS
        self.external_triggers = external_triggers if external_triggers is not None else {}

        for key, value in defaults.items():
            if not self.contains(self.prefix + key):
                self.setValue(self.prefix + key, value)

    @Slot()
    def clear(self):
        super().clear()

    @Slot(str, result='QVariant')
    def get(self, key):
        value = self.value(self.prefix + key)
        # On case insensitive backends 'False' is saved as 'false' so we need to workaround this
        if value == 'false':
            value = False
        elif value == 'true':
            value = True
        return value

    @Slot(str, 'QVariant')
    def set(self, key, value):
        self.setValue(self.prefix + key, value)

        if key in self.external_triggers.keys():
            self.external_triggers[key](value)


_settings = None


def init_settings(app):
    global _settings

    if isinstance(_settings, Settings) and hasattr(_settings, 'prefix'):
        warnings.warn("QSettings is already initialized. Use global_instance() to retrieve the instance",
                      category=ResourceWarning)
        return _settings

    if not app.organizationName or not app.applicationName:
        warnings.warn("app.organizationName or app.applicationName should be specified before using QSettings",
                      category=ResourceWarning)

    _settings = Settings(prefix='app/settings/', qs_kwargs={ 'parent': app },
                         external_triggers={ 'verbose': stm32pio.gui.log.set_verbosity })

    return _settings


def global_instance():
    if _settings is None:
        warnings.warn("QSettings is not initialized. Call init_settings() first", category=ResourceWarning)
    return _settings
