# Second approach
# view = QQuickView()
# view.setResizeMode(QQuickView.SizeRootObjectToView)
# view.rootContext().setContextProperty('projectsModel', projects)
# view.setSource(QUrl('main.qml'))

import logging

import stm32pio.lib
import stm32pio.settings
import stm32pio.util

# s = stm32pio.lib.ProjectState([
#     (stm32pio.lib.ProjectStage.UNDEFINED, True),
#     (stm32pio.lib.ProjectStage.EMPTY, True),
#     (stm32pio.lib.ProjectStage.INITIALIZED, True),
#     (stm32pio.lib.ProjectStage.GENERATED, True),
#     (stm32pio.lib.ProjectStage.PIO_INITIALIZED, True),
#     (stm32pio.lib.ProjectStage.PATCHED, False),
#     (stm32pio.lib.ProjectStage.BUILT, True),
# ])

# logger = logging.getLogger('stm32pio')  # the root (relatively to the possible outer scope) logger instance
# handler = logging.StreamHandler()
# logger.addHandler(handler)
# special_formatters = {'subprocess': logging.Formatter('%(message)s')}
# logger.setLevel(logging.DEBUG)
# handler.setFormatter(stm32pio.util.DispatchingFormatter(
#     f"%(levelname)-8s %(funcName)-{stm32pio.settings.log_fieldwidth_function}s %(message)s",
#     special=special_formatters))

p = stm32pio.lib.Stm32pio('/Users/chufyrev/Documents/GitHub/stm32pio/stm32pio-test-project',
                          parameters={ 'board': 'nucleo_f031k6' }, save_on_destruction=False)
print(p.state)
print()
