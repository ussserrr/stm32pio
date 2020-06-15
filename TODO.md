# TODOs

## Business logic, general features
 - [ ] GitHub CHANGELOG - separate New, Fixed, Changed into paragraphs
 - [ ] Middleware support (FreeRTOS, etc.)
 - [ ] Arduino framework support (needs research to check if it is possible)
 - [ ] Create VSCode plugin
 - [ ] UML diagrams (core, GUI back- and front-ends, thread flows, events, etc.)
 - [ ] CI is possible (Arch's AUR has the STM32CubeMX package, also there is a direct link). Deploy Docker one in Azure Pipelines, basic at Travis CI
 - [ ] In the future, probably use https://setuptools.readthedocs.io/en/latest/setuptools.html#accessing-data-files-at-runtime `importlib.resources` as a standard API to access non-Python files inside Python packages (such as `.qml`)
 - [ ] Use some features of newer Pythons after dropping the support for 3.6 (and so on)

## GUI version
 - [ ] Obtain boards on demand (not at the startup)
 - [ ] Can probably detect Ctrl and Shift clicks without moving the mouse first
 - [ ] Mac: sometimes auto turned off shift highlighting after action (hide-restore helps)
 - [ ] Some visual flaws when the window have got resized (e.g. 'Add' button position doesn't change until the list gets focus, 'Log' area crawls onto the status bar)
 - [ ] Tests (research approaches and patterns)
 - [ ] Remade the list item to use States, too. Probably, such properties need to be implemented:
       ```
       state: {
           loaded,

           visitedAfterInstantiating,

           actionRunning,
           [+] lastActionStatus,
           visitedAfterAction,
           ...
       }
       ```
 - [ ] Test with different timings
 - [ ] Divide on multiple modules (both Python and QML)
 - [ ] Implement other methods for Qt abstract models
 - [ ] Warning on 'Clean' action (maybe the window with a checkbox "Do not ask in the future" (QSettings parameter))
 - [ ] QML logging - pass to Python' `logging` and establish a similar format. Distinguish between `console.log()`, `console.error()` and so on
 - [ ] Lost log box autoscroll when manually scrolling between the actions
 - [ ] Crash on shutdown in Win and Linux (errors such as `[QML] CRITICAL QThread: Destroyed while thread is still running Process finished with exit code 1073741845`)
 - [ ] Linux: Not a monospaced font in the log area
 - [ ] Temporarily pin projects with currently running actions to the top (and stay there on scrolling). See QML Package type
 - [ ] "Pressed" effect for action buttons
 - [x] Fix: bold borders remains after an error
 - [ ] Maybe do not save the stm32pio.ini if there wasn't one (after starting from CLI)

## Core library
 - [ ] when updating the project (`generate` command), check for boards match
 - [ ] Remove casts to string where we can use path-like objects (related to a Python version as new ones receives path-like objects arguments while old ones aren't)
 - [ ] We look for some snippets of strings in logs and output for the testing code but we hard-code them and this is not good, probably (e.g. 'DEBUG')
 - [ ] Store an initial content of the folder in .ini config and ignore it on clean-up process. Allow the user to modify such list (i.e. list of exclusion) in the config file. Mb some integration with `.gitignore`
 - [ ] at some point check for all tools (CubeMX, ...) to be present in the system (both CLI and GUI) (global `--check` command (as `--version`), also before execution of the full cycle (no sense to start if some tool doesn't exist))
 - [ ] generate code docs (help user to understand an internal mechanics, e.g. for embedding). Can be uploaded to the GitHub Wiki
 - [ ] colored logs, maybe (breaks zero-dependency principle)
 - [ ] maybe migrate to async/await approach in the future (return some kind of a "remote controller" to control the running action)
 - [ ] `__init__`' `parameters` dict argument schema (Python 3.8 feature).
 - [ ] Mb store the last occurred exception traceback in .ini file and show on some CLI command (so we don't necessarily need to turn on the verbose mode and repeat this action). And, in general, we should show the error reason right off
 - [ ] the lib sometimes raising, sometimes returning the code and it is not consistent. While the reasons behind such behavior are clear, would be great to always return a result code and raise the exceptions in the outer scope, if there is need to
 - [ ] check board (no sense to go further on 'new' if the board in config.ini is not correct)
 - [ ] test using virtualenv
 - [ ] test for different `.ioc` files (i.e. F0, F1, F4 and so on) as it is not the same actually
 - [ ] mb allow to use an arbitrary strings (arrays of str) to specify tools commands in stm32pio.ini (shell=True or a list of args (split a string))
 - [x] cache boards for a small interval of time
 - [ ] count another '-v' as '-v' for PlatformIO calls (slider in GUI settings window)
 - [ ] Project' name (path) can be reused so cannot be used as a unique identifier but so is id(self)? Probably it is better to use a path (human-readable)
 - [x] Analyze `.ioc` file for the wrong framework/parameters
 - [x] Take out to settings "[ERROR]", "Successful code generation" etc.
 - [ ] Kill subprocesses if there is no output have appeared for some timeout (i.e. hung)
 - [x] Fix when '' board string overwrites existing
 - [x] Allow to not specify a board for `new` when it is already specified in the config
 - [ ] Maybe logging notifications about which parameters has superseded which
