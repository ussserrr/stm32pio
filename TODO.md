# TODO list

## Business logic, general features
 - [ ] Middleware support (FreeRTOS, etc.)
 - [ ] Arduino framework support (needs research to check if it is possible)
 - [ ] Create VSCode plugin
 - [ ] UML diagrams (core, GUI back- and front-ends, thread flows, events, etc.). Maybe automated
 - [ ] In the future, probably use `importlib.resources` as a standard API to access non-Python files inside Python packages (such as `.qml`)
 - [ ] Use some features of newer Pythons after dropping the support for 3.6 (and so on)
 - [ ] Generate code docs (help user to understand an internal mechanics, e.g. for embedding). Say, just for public API (main project, `cli.app.main()`, logging). Can be uploaded to the GitHub Wiki. Currently, we struggle to even track the API changes (e.g. for semver). API is some code endpoints and entire CLI set, I suppose...
 - [ ] Build, install and only then test the app
 - [ ] Remade this TODO list as a GitHub issues/project/milestones. Use labels to mimic DISCUSSION ones and so on (UPD: GitHub now has its own "discussions" feature, actually)
 - [ ] Write in the README about why we use an INI config format (because it should be familiar to the PlatformIO user). Also consider migrating to some other (more feature-rich) format (JSON, etc.)
 - [ ] See on GitHub what people looking for the most (what files) and adjust those parts of the repo
 - [ ] Collect all Python 3.7+ TODOs, notes, etc. to form some kind of resume of what can be done to take advantages of new language/lib features while dropping the 3.6 support
 - [ ] Check do we actually need `wheel` package to be installed prior `pip install stm32pio`. Can we add it to dependencies and be sure it will be retrieved before any other?
 - [ ] Adopt Google style guides (https://google.github.io/styleguide/pyguide.html), or some another one (mainly for comments, docstrings, etc.)...
 - [ ] Rewrite GitHub issue templates to modern [config.yml](https://docs.github.com/en/github/building-a-strong-community/configuring-issue-templates-for-your-repository#configuring-the-template-chooser) and note the `validate` feature in it
 - [ ] Use as little string literals as possible (e.g. a config better be typed, Qt signal/slot names, and so on)
 - [ ] Can we detect unused code structures? E.g. methods, functions... (probably some static tool/linter)
 - [ ] Check with some static analyzer (mypy) (actually, PyCharm is already doing it)
 - [ ] Migrate CHANGELOG to GitHub releases?


## CI
 - [ ] Lock ALL tools' versions per a commit! CubeMX F0 framework, PlatformIO and its build tools & libraries versions (use templates, variables and cache). Every build is dependent on:
    - PlatformIO
    - PlatformIO packages
    - CubeMX
    - CubeMX packages
    - PySide2
    - Python
    - Win/Mac/UNIX
 - [ ] CI/test-related code in the `settings.py` is probably not good, should find the workaround
 - [ ] Fail if not all tests have been passed
 - [ ] Templates for CI?
 - [ ] Migrate to GitHub actions?
 - [ ] Specify CI dependencies (pyyaml, pytest, etc.) is some way (for example, `setup.cfg` `extras` option)


## GUI version
 - [ ] Live-reloading of the config file
 - [ ] Obtain boards only on demand (not at a startup)
 - [ ] Detect Ctrl and Shift clicks without moving the mouse first
 - [ ] Mac: sometimes auto turned off shift highlighting after action (hide-restore helps)
 - [ ] Some visual flaws when the window have got resized (e.g. 'Add' button position doesn't change until the list gets focus, 'Log' area crawls onto the status bar)
 - [ ] Tests (research possibilities and patterns)
   - [ ] Test with different timings
   - [ ] Prolonged tests: measure performance/memory consumption (profiling)
 - [ ] QML modules are not isolated – we still use global IDs and so on
 - [ ] Warning on 'Clean' action (maybe the window with a checkbox "Do not ask in the future" (QSettings parameter))
 - [ ] QML logging – pass to Python' `logging` and establish a similar format. Distinguish between `console.log()`, `console.error()` and so on. For all platforms (not only Windows)
 - [ ] Bug: losing LogArea autoscroll after manual scrolling (even between actions)
 - [ ] Linux: Not a monospaced font in the log area
 - [ ] Remember last viewed project (index)
 - [ ] Temporarily pin projects with currently running actions to the top (and stay there on scrolling). See QML "Package" type
 - [ ] "Pressed" effect for the action button
 - [ ] Maybe do not save the stm32pio.ini if there wasn't one (after starting from CLI) (i.e. no implicit intervention)
 - [ ] Specify board without app reloading. Warn that board is not specified after cleanup
 - [ ] Add multiple projects on "Add" button (from a dialog)
 - [ ] Do not store a state in a list delegate. Save it in the model, also widgets will be using it so the \[QML\] code will be cleaner
 - [ ] Explain why we \[partially\] store a project state in the QML delegate (because these properties are so specific and related to the GUI stuff)
 - [ ] Interface for the validation feature (and other that have been implemented in CLI yet GUI lacks)
 - [ ] Add some sort of desktop shortcut to start the app cause why the GUI users should bother with a CLI stuff? (Seems like impossible atm)
 - [ ] Add dark mode
 - [ ] Maybe completely pack the app (single-executable distribution) (https://doc.qt.io/qtforpython/deployment.html)
 - [ ] Migrate to Qt6 (PySide6) (check packages availability)
 - [ ] Switch between input fields on Tab (and different elements, in general)
 - [ ] Jump to project on system notification click
 - [ ] OS integration:
   - [ ] Blink the toolbar icon after an action
   - [ ] Show progress (just for steps, at least)
 - [ ] `Must construct a QGuiApplication first` is still sometimes present on shutdown...


## Core library and CLI

### PlatformIO board
 - [ ] When updating the project (`generate` command), check if boards matches
 - [ ] Check board (no sense to go further on 'new' if the board in the config.ini is not correct)
 - [ ] If `--board` has not been supplied, try to get it from the `platformio.ini` (if present)

### Control spawn subprocesses
 - [ ] Maybe migrate to async/await approach in the future (return some kind of "remote controller" to control the running action) (we have a PoC in iCloud)
 - [ ] Kill subprocesses if there is no output have appeared for some timeout (i.e. hung)

### CubeMX
 - [ ] Use CubeMX options such as `project couplefilesbyip <0|1>` and `project toolchain <toolchain>` or ...
 - [ ] ... parse an `.ioc` file and edit the parameters in-place if necessary
 - [ ] Analyze `.ioc` file for the wrong framework/parameters (validation continues...)
 - [ ] Deal with CubeMX requests about software package and CubeMX versions migrations (seems like the only way is to set them first in `.ioc` file, no appropriate CLI keys)

### Config
 - [ ] mb allow to use an arbitrary strings (arrays of str) to specify tools commands in stm32pio.ini (`shell=True` or a list of args (split a string))
 - [ ] Be able to set the `platformio_cmd` in config to `python -m platformio` (convert to list and concat where used)
 - [ ] Mark some parameters as unnecessary and do not save them to config unless explicitly stated (it can now be implemented more easily thanks to the `Config` subclass, I guess) (some DB-like schema)
 - [ ] Set `git` command in settings (config). There are a little too many options now, should consider hide them unless explicitly set (like in the platformio.ini)
 - [ ] Store an editor in the config?
 - [ ] Implement some _optional_ global config (e.g. `~/.stm32pio`) where the users can specify their paths/commands of tools. Uniform GUI and CLI configs in this case. Maybe if one uses the GUI version they would be fine with the `QSettings` config (add option to choose) (provide fallback mechanics)

### Tests
 - [ ] Closely audit the test suite (e.g. CLI tests doesn't verify ALL available commands because some of them will be considered redundant in the presence of unit tests and so on)
 - [ ] Public API backward compatibility testing (core lib + CLI, I guess)
 - [ ] What if some parameters missing in the config file? Check the behavior

### Other
 - [ ] Use %(module)s in log format string (see GUI)
 - [ ] Remove casts to string where we can use path-like objects (seems like Python 3.6 on Windows is delaying this)
 - [ ] DISCUSSION. Colored CLI logs, maybe (3rd-party) (breaks zero-dependency principle though...)
 - [ ] If we output config "diffs" (in debug mode) we should print them more beautiful (some tables or so). Probably should consider external dependency or optional CLI tool (if present then ...)
 - [ ] `__init__`' `parameters` dict argument schema (Python 3.8 feature)
 - [ ] DISCUSSION. The lib sometimes raising, sometimes returning the code and it is not consistent. Current decision-making agent: common sense and the essence of the action. Would be great to always return a result code and raise the exceptions in the outer scope, if there is need to
 - [ ] Count another `-v` as `-v` for the PlatformIO calls (also we can implement it as a (vertical) slider in the GUI settings window (remember Windows UAC panel?))
 - [ ] DISCUSSION. Project name (path) can be reused, so it shouldn't be considered as a unique identifier but so is `id(self)`? Probably it is better to use a path (human-readable) (but it also can be reused...)
 - [ ] DISCUSSION. Support equality comparison for `Project` (`__eq__()`) and get rid of `p1.path.samefile(p2.path)`. It's actually a more complicated topic than it seems, e.g. what are _equal_ projects? Path is not the only component of the project despite being the primary one, what about the config content though? It can be different for the same path at different points of time (when config were read after some period). Not needed at the moment
 - [ ] DISCUSSION. Use `--start-editor` as a generic action to perform after the main operation (rename, of course)?
 - [ ] Take a look to the `dataclass` feature and find where we can apply it (3.7+)
 - [ ] Project' `instance_options` is kind of ugly...
 - [ ] `platformio_ini_is_patched` is actually not so reliable. For example, some property can contain both our and user-defined values and still technically be considered as "patched". Maybe should use `in` for checking instead of the strict equality
 - [ ] Automatically add the `stm32pio.ini` and artifacts to git
 - [ ] DISCUSSION. Convert the embedding example to an IPython notebook (or smth like this)
 - [ ] Support a CubeMX project structure generated by the GUI version of CubeMX. Add a flag or detect automatically which one is existing at the moment
 - [ ] Core project class is still too big and will be even larger in the future. Maybe establish some FP-style library and call those functions from the class methods
