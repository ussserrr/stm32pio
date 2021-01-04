# CLI API
This file is describing all operations available from the command line interface version of the application. You can also use an applicable to any command `-h/--help` key to refer to its short description at any time. All the commands below can be run in the verbose mode with the `-v/--verbose` key given and will print some additional debug information. It is useful for errors tracking. Please supply the verbose output when submitting an issue/question about the stm32pio.

## Table of contents
> - [Project life-cycle](#project-life-cycle)
>   - [`init`](#init)
>   - [`generate`](#generate)
>   - [`pio_init`](#pio_init)
>   - [`patch`](#patch)
>   - [`new`](#new)
> - [Utils](#utils)
>   - [`clean`](#clean)
>   - [`status`](#status)
>   - [`validate`](#validate)
>   - [`gui`](#gui)
> - [Options](#options)


## Project life-cycle
These commands summarize the stm32pio goal – managing of the project combining STM32CubeMX and PlatformIO. The real-life example can be found [here](/examples/cli), it shows a typical use case (with screenshots).

### `init`
This will initialize a fresh new project creating `stm32pio.ini` config where you can review and tweak any parameters if necessary. Normally, the latter shouldn't be a case, it is only needed, for example, if tools are installed somewhat different on your machine (e.g. `platformio` is not in the PATH environment variable).
#### Prerequisites
`.ioc` file should be present at the specified path (in fact, this determines what is a project and what isn't).
#### Expected output
✅ `stm32pio.ini`

### `generate`
This will start the CubeMX for you and tell it to run the code generation against your `.ioc` file. CubeMX has its own CLI mode which is used for this feature. However, it still can prompt or warn you about some things, e.g. incompatible CubeMX versions, missing software packages and so on. If this is a case, please read and fix them, then try to re-run the generation action. Also, the output of the code generation feature in CubeMX is pretty different when running from the CLI or GUI mode of the CubeMX, so doesn't let this to confuse you. The CLI one is always a correct one if you plan to use the stm32pio, while the GUI one isn't compatible with the patching algorithm (see below). Also, the default structure of the generated code is significantly different when you invoke the generation from the GUI version of CubeMX or the CLI one. As stm32pio uses the latter, currently the PlatformIO project structure cannot be properly patched to use a code from the GUI version of CubeMX (at least with the default patch, you can always tweak it in a configuration file `stm32pio.ini`).
#### Prerequisites
`.ioc` file with the compatible parameters:
 - "Copy only the necessary library files" should be set to `True` (`ProjectManager.LibraryCopy=1` in the `.ioc` file)
 - "Generate periphery initialization as a pair of '.c/.h' files per peripheral" should be set to `True` (`ProjectManager.CoupleFile=true` in the `.ioc` file)
 - "Other Toolchains (GPDSC)" for the toolchain (`ProjectManager.TargetToolchain=Other Toolchains (GPDSC)` in the `.ioc` file)

Look at the [example](/examples/cli) to see how they can be set.
#### Expected output
✅ `Inc/`
✅ `Src/`

### `pio_init`
Starts the PlatformIO to create the new project passing the compatible parameters (e.g. framework to use during the compilation). Running this command is basically the same as running the `platformio project init ...` manually. Typically, you shouldn't be in the situation when you need to execute this command by yourself, instead `new` or `generate` will be more practical most of the time.
#### Prerequisites
PlatformIO board identifier supplied (whether set in the config or passed as a CLI argument).
#### Expected output
✅ `lib/`
✅ `include/`
✅ `src/`
✅ `test/`
✅ `platformio.ini`
✅ `.gitignore`

### `patch`
This is a "glue" actually coupling the CubeMX output and the expected by PlatformIO project structure. Note: this operation erases all the comments (lines starting with `;`) inside the `platformio.ini` file. They are not required anyway, in general, but if you need them for some reasons please consider saving the information somewhere else.
#### Prerequisites
 - generated CubeMX code
 - initialized PlatformIO project
#### Expected output
❌ `src/`
❌ `include/`
✏️ `platformio.ini`

### `new`
Fulfill the complete run for the project passing it through all of the stages above. Additionally, optional build via PlatformIO can be initiated with the corresponding CLI key (basically `pio run` command).
#### Prerequisites
`.ioc` file.
#### Expected output
All of the above (+ optional build artifacts, if the corresponding option was given).

There is no dedicated "build" command because this task can be done through the `--with-build` option (see below) or completely by PlatformIO itself (`pio run`).


## Utils

### `clean`
Can be used to return the project to its original state while experimenting or to quickly remove some temporary files. By default, this will retain only the `.ioc` file, but you can specify the ignore-list (in the config) – files/folders to preserve. Alternatively, this task can be entirely entrusted to the git and its own rules. For example, a role of the ignore-list in this case can be played by the `.gitignore` list. Note: by default, you will be prompted about files/folders for removal. There is an option to suppress it but in this case you are on your own.
#### Prerequisites
`.ioc` file.
#### Expected output
Depends on configuration.

### `status`
Inspect the project state and show the obtained information. All possible project stages will be printed while the fulfilled ones will be marked.
#### Prerequisites
None
#### Expected output
Terminal output.

### `validate`
Inspect the current environment – tools listed under the "app" section of the config (i.e. CubeMX, PlatformIO). Allows to quickly check whether all these programs are correctly set and/or installed in your system.
#### Prerequisites
Config file. In case it doesn't exist, the default config will be tested although this, probably, is not very useful.
#### Expected output
Terminal output.

### `gui`
Start the GUI version of the application. All arguments given will be passed forward. See [its own docs](/docs/GUI) for more information.
#### Prerequisites
GUI dependencies installed (PySide2).
#### Expected output
None (GUI window appears).


## Options
Although every main command listed above has its own set of available options, some of them are common across multiple ones. Remember you can always run `-h/--help` option to see topical info.

### `-d/--directory PATH`
Pass the project folder. Alternatively, the `.ioc` file itself can be specified. Despite this being the fundamental identifier, you can omit it entirely in your commands calls. In this case the current working directory will be assumed as the project's one. Basically like for git, PlatformIO and many other CLI tools.
#### Default
Current working directory.

### `-b/--board`
PlatformIO identifier of the board. In other words, pick the "ID" column of the `platformio boards` command output.
#### Default
None.

### `-e/--start-editor`
Many of the code/text editors (both CLI and GUI ones) can be started from the terminal, e.g. VSCode – by the `code` command, Sublime – `subl` and so on. The second CLI argument is often the desired folder path to open so using the formula `[EDITOR] [PATH]` we can satisfy most of the conforming editors. Furthermore, it can actually be used as a generic post-action hook as long the arguments' formula is suitable.
#### Default
None.

### `-c/--with-build`
Build the project in the end. See `new` command description.
#### Default
False.

### `clean` options
`-s/--store-content` – get the current content of the project folder, save it to the `cleanup_ignore` config option and exit.

**Default**: False.

`-q/--quiet` – suppress the prompt about the files/folders to delete. Be careful, it is recommended to use this option only after the first successful removal.

**Default**: True.
