# TODOs

## Business logic, business features
 - [ ] Issues guide for the GitHub (OS, content of the config, project tree, enable verbose)
 - [ ] GitHub CHANGELOG - separate New, Fixed, Changed into paragraphs
 - [ ] Middleware support (FreeRTOS, etc.)
 - [ ] Arduino framework support (needs research to check if it is possible)
 - [ ] Create VSCode plugin

## GUI version
 - [ ] Handle the initialization error (when boards are receiving)
 - [ ] Maybe `data()` `QAbstractListModel` method can be used instead of custom `get()`
 - [ ] Can probably detect Ctrl and Shift clicks without moving the mouse first
 - [ ] Notify the user that the 'board' parameter is empty
 - [ ] Mac: sometimes auto turned off shift highlighting after action (hide-restore helps)
 - [ ] Some visual flaws when the window have got resized (e.g. 'Add' button position doesn't change until the list gets focus, 'Log' area crawls onto the status bar)
 - [ ] Gray out "stage" line in all projects except current
 - [ ] Tests (research approaches and patterns)
 - [ ] Test performance with a large number of projects in the model. First test was made:
      1. Some projects occasionally change `initLoading` by itself (probably Loader unloads the content) (hence cannot click on them, busy indicator appearing)

         Note: Delegates are instantiated as needed and may be destroyed at any time. They are parented to ListView's contentItem, not to the view itself. State should never be stored in a delegate.

         Use `id()` in `setInitInfo()`. Or do not use ListView at all (replace by Repeater, for example) as it can reset our "notifications"
      2. Some projects show OK even after its deletion (only the app restart helps)
 - [ ] Test with different timings
 - [ ] Divide on multiple modules (both Python and QML)
 - [ ] Implement other methods for Qt abstract models
 - [ ] Warning on 'Clean' action (maybe the window with a checkbox "Do not ask in the future" (QSettings parameter))
 - [ ] 2 types of logging formatters for 2 verbosity levels
 - [ ] `TypeError: Cannot read property 'actionRunning' of null` (deconstruction order) (on project deletion only)
 - [ ] QML logging - pass to Python' `logging` and establish a similar format. Distinguish between `console.log()`, `console.error()` and so on
 - [ ] Lost log box autoscroll when manually scrolling between the actions
 - [ ] Crash on shutdown in Win and Linux (errors such as `[QML] CRITICAL QThread: Destroyed while thread is still running Process finished with exit code 1073741845`)
 - [ ] Start with a folder opened if it was provided on CLI (for example, `stm32pio_gui .`)
 - [ ] Linux:
      - Not a monospace font in the log area

## Core library
 - [ ] Add more checks, for example when updating the project (`generate` command), check for boards matching and so on...
 - [x] Remove casts to string where we can use path-like objects (related to Python version as new ones receive path-like objects arguments while old ones aren't)
 - [ ] We look for some snippets of strings in logs and output for the testing code but we hard-code them and this is not good, probably (e.g. 'DEBUG')
 - [ ] Store a folder initial content in .ini config and ignore it on clean-up process. Allow the user to modify such list (i.e. list of exclusion) in the config file. Mb some integration with `.gitignore`
 - [ ] at some point check for all tools (CubeMX, ...) to be present in the system (both CLI and GUI) (global `--check` command (as `--version`), also before execution of the full cycle (no sense to start if some tool doesn't exist))
 - [ ] generate code docs (help user to understand an internal mechanics, e.g. for embedding). Can be uploaded to the GitHub Wiki
 - [ ] colored logs, maybe (brakes zero-dependency principle)
 - [ ] check logging work when embed stm32pio lib in a third-party stuff (no logging setup at all)
 - [ ] merge subprocess pipes to one where suitable (i.e. `stdout` and `stderr`)
 - [ ] redirect subprocess pipes to `DEVNULL` where suitable to suppress output (tests)
 - [ ] Two words about a synchronous nature of the lib and user's responsibility of async wrapping (if needed). Also, maybe migrate to async/await approach in the future
 - [ ] `__init__`' `parameters` dict argument schema (Python 3.8 feature).
 - [ ] See https://docs.python.org/3/howto/logging-cookbook.html#context-info to maybe remade current logging schema (current is, perhaps, a cause of the strange error while testing (in the logging thread), also modifies global settings (log message factory))
 - [ ] UML diagrams (core, GUI back- and front-ends, thread flows, events, etc.)
 - [ ] CI is possible (Arch's AUR has the STM32CubeMX package, also there is a direct link). Deploy Docker one in Azure Pipelines, basic at Travis CI
 - [ ] Test preserving user files and folders on regeneration and mb other operations
 - [ ] Move special formatters inside the library. It is an implementation detail actually that we use subprocesses and so on
 - [ ] Mb store the last occurred exception traceback in .ini file and show on some CLI command (so we don't necessarily need to turn on the verbose mode). And, in general, we should show the error reason right off
 - [ ] 'verbose' and 'non-verbose' tests as `subTest` (also `should_log_error_...`)
 - [ ] the lib sometimes raising, sometimes returning the code and it is not consistent. While the reasons behind such behavior are clear, would be great to always return a result code and raise the exceptions in the outer scope, if there is need to
 - [ ] check board (no sense to go further on 'new' if the board in config.ini is not correct)
 - [ ] check if `platformio.ini` config will be successfully parsed when there are interpolation and/or empty parameters
 - [x] check if `.ioc` file is a text file on project initialization. Let `_find_ioc_file()` method to use explicitly provided file (useful for GUI). Maybe let user specify it via CLI
 - [ ] mb add CLI command for starting the GUI version (for example, `stm32pio --gui`)
 - [ ] test using virtualenv
