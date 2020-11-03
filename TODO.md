# TODO list

## Business logic, general features
 - [ ] GitHub CHANGELOG - separate New, Fixed, Changed into paragraphs
 - [ ] Middleware support (FreeRTOS, etc.)
 - [ ] Arduino framework support (needs research to check if it is possible)
 - [ ] Create VSCode plugin
 - [ ] UML diagrams (core, GUI back- and front-ends, thread flows, events, etc.)
 - [ ] In the future, probably use https://setuptools.readthedocs.io/en/latest/setuptools.html#accessing-data-files-at-runtime `importlib.resources` as a standard API to access non-Python files inside Python packages (such as `.qml`)
 - [ ] Use some features of newer Pythons after dropping the support for 3.6 (and so on)
 - [ ] Generate code docs (help user to understand an internal mechanics, e.g. for embedding). Say, just for public API (main project, `cli.app.main()`, logging). Can be uploaded to the GitHub Wiki. Currently we struggle to even track the API changes (e.g. for semver). API is some code endpoints and entire CLI set, I suppose...
 - [ ] Build, install and only then test the app
 - [ ] Templates for CI?
 - [ ] Remade this TODOs list as a GitHub issues/project/milestones? Use labels to mimic DISCUSSION ones and so on
 - [ ] Write in README about why we use an INI config format (because it should be familiar to the PlatformIO user). Also consider to migrate to some other (more feature-rich) format (JSON, etc.)


## GUI version
 - [ ] Obtain boards on demand (not at the startup)
 - [ ] Can probably detect Ctrl and Shift clicks without moving the mouse first
 - [ ] Mac: sometimes auto turned off shift highlighting after action (hide-restore helps)
 - [ ] Some visual flaws when the window have got resized (e.g. 'Add' button position doesn't change until the list gets focus, 'Log' area crawls onto the status bar)
 - [ ] Tests (research approaches and patterns)
 - [ ] Remade the list item to use States, too. Probably, such properties need to be implemented:
    ```
    state: {
        - loading (show spinner)
        - new (green highlighting)
        - cannot be initialized (red highlighting)
        - action has finished successfully (green dot)
        - action has finished with error (red dot)

        - selected
        - not selected

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
 - [ ] Maybe do not save the stm32pio.ini if there wasn't one (after starting from CLI)
 - [ ] Specify board without reloading the app. Warn that board is not specified after cleanup
 - [ ] Add multiple folders on "Add" button
 - [ ] Do not store the state in the list delegate. Save it in the model, also widgets will be using it so the code will be cleaner
 - [ ] Setup QML logging proxy (QML's `console.log()` functions family to the Python `logging`) for all platforms (not only Windows)
 - [ ] Interface for the validation feature


## Core library and CLI

### PlatformIO board
 - [ ] When updating the project (`generate` command), check for boards match
 - [ ] Check board (no sense to go further on 'new' if the board in config.ini is not correct)
 - [ ] If `--board` has not been supplied try to get it from the `platformio.ini` (if present)

### Control spawn subprocesses
 - [ ] maybe migrate to async/await approach in the future (return some kind of a "remote controller" to control the running action)
 - [ ] Kill subprocesses if there is no output have appeared for some timeout (i.e. hung)
 
### CubeMX
 - [ ] Use CubeMX options such as `project couplefilesbyip <0|1>` and `project toolchain <toolchain>` or ...
 - [ ] ... parse an `.ioc` file and edit the parameters in-place if necessary
 - [ ] Analyze `.ioc` file for the wrong framework/parameters (validation continue...)
 - [ ] Deal with CubeMX requests about software package and CubeMX versions migrations (seems like the only way is to set them first in `.ioc` file, no appropriate CLI keys)
 
### Config
 - [x] Mb store the last occurred exception traceback in .ini file and show on some CLI command (so we don't necessarily need to turn on the verbose mode and repeat this action). And, in general, we should show the error reason right off
 - [ ] mb allow to use an arbitrary strings (arrays of str) to specify tools commands in stm32pio.ini (`shell=True` or a list of args (split a string))
 - [x] Maybe log about which parameters has superseded which
 - [x] Pretty printer for the config
 - [ ] Store editor in the config?

### Other
 - [x] Remove casts to string where we can use path-like objects (related to a Python version as new ones receives path-like objects arguments while old ones aren't)
 - [x] We look for some snippets of strings in logs and output in a testing code but we hard-code them and this is not good, probably (e.g. 'DEBUG')
 - [ ] Store an initial content of the folder in .ini config and ignore it on clean-up process. Allow the user to modify such list (i.e. list of exclusion) in the config file. Mb some integration with `.gitignore` if present
 - [x] at some point check for all tools (CubeMX, ...) to be present in the system (both CLI and GUI) (global `--check` command (as `--version`), also before execution of the full cycle (no sense to start if some tool doesn't exist))
 - [ ] DISCUSSION. Colored CLI logs, maybe (breaks zero-dependency principle though...)
 - [ ] `__init__`' `parameters` dict argument schema (Python 3.8 feature).
 - [ ] DISCUSSION. The lib sometimes raising, sometimes returning the code and it is not consistent. Current decision making agent: common sense and the essence of the action. Would be great to always return a result code and raise the exceptions in the outer scope, if there is need to
 - [ ] count another `-v` as `-v` for the PlatformIO calls (also do it as a slider in the GUI settings window)
 - [ ] Project name (path) can be reused so cannot be used as a unique identifier but so is `id(self)`? Probably it is better to use a path (human-readable) (but it also can be reused...)
 - [ ] DISCUSSION. Use `--start-editor` as a generic action to perform after the main operation (rename, of course)?
 - [ ] Search for `str(...)` calls to eliminate them where possible (i.e. unnecessary)
