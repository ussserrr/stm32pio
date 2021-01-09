# INI-config description
Consider this file as a reference when editing the project parameters. 

The project's configuration file (by default, its name is `stm32pio.ini`) controls aspects of how the stm32pio treating your project. INI-format is convenient and familiar to PlatformIO users.

It has 2 main sections. As the stm32pio has no global config (keeping be simple and non-intrusive), the `[app]` section consists of some properties that could belong to the global app settings rather being set per-project. We're talking here about the CLI tools' (used by the stm32pio) paths/commands. The second section – `[project]` – is more related to the particular project.

By default, all available settings are explicitly placed inside an every INI config. It is recommended to not remove them from the file.

Some config properties can also be supplied by the CLI keys. So what is the resolution order in such case?
```
  defaults              <=  config file   <=  user-given
  (settings.py module)      stm32pio.ini      CLI keys
```
Right-hand values takes precedence over the left (arrows showing the merging order).

Note: this is not an only source of the program settings but more like a "public" subset of them. As you can see above, there is also the `settings.py` module controlling internal parameters.


## Table of contents
> - [`app` section](#app-section)
>   - [`java_cmd`](#java_cmd)
>   - [`platformio_cmd`](#platformio_cmd)
>   - [`cubemx_cmd`](#cubemx_cmd)
> - [`project` section](#project-section)
>   - [`cubemx_script_content`](#cubemx_script_content)
>   - [`platformio_ini_patch_content`](#platformio_ini_patch_content)
>   - [`board`](#board)
>   - [`ioc_file`](#ioc_file)
>   - [`cleanup_ignore`](#cleanup_ignore)
>   - [`cleanup_use_git`](#cleanup_use_git)
>   - [`last_error`](#last_error)


## `app` section
Specify commands of the corresponding tools if they are present in your PATH env variable (e.g. `java`, `platformio`). Alternatively, provide an absolute path (e.g. `C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX.exe`). If the path contains whitespaces, do not escape them manually, this will be done automatically.

### `java_cmd`
As you're probably already know, the CubeMX uses Java to run. So most likely it is already installed on your machine. By default, this command will be used to start the CubeMX as `java -jar` as it is the most universal and reliable approach. If omitted, there will be an attempt to run `cubemx_cmd` on its own, without preceding `java`. See `cubemx_cmd` below for more information.
#### Default
`java`

### `platformio_cmd`
`python -m platformio` method is not currently supported.
#### Default
`platformio`

### `cubemx_cmd`
As the CubeMX doesn't by default append itself to a PATH, this probably will be a path on your machine.
#### Default
 - macOS: `/Applications/STMicroelectronics/STM32CubeMX.app/Contents/Resources/STM32CubeMX`
 - Linux: `~/STM32CubeMX/STM32CubeMX`
 - Windows: `C:/Program Files/STMicroelectronics/STM32Cube/STM32CubeMX/STM32CubeMX.exe`


## `project` section

### `cubemx_script_content`
Template of the CubeMX script that will be filled, written to the temp file and fed to the CubeMX during the code generation process. In other words, they are instructions for the CubeMX to execute.
#### Default
```
config load ${ioc_file_absolute_path}
generate code ${project_dir_absolute_path}
exit
```

### `platformio_ini_patch_content`
Changes that should be applied to the `platformio.ini` file to conform the CubeMX and PlatformIO projects structures. For those who want to modify the patch: it has a general .INI-style syntax, so it is possible to specify several sections and apply composite patches. This works totally fine for the most cases except, perhaps, some really huge complex patches involving, say, the parameters' interpolation feature. It's turned off for both `platformio.ini` and user's patch parsing by default. If there are some problems you've encountered due to a such thing please modify the source code to match the parameters' interpolation behavior for the configs you need to. Seems like `platformio.ini` uses `ExtendedInterpolation` for its needs, by the way.
#### Default
```
[platformio]
include_dir = Inc
src_dir = Src
```

### `board`
Same as the corresponding CLI option – PlatformIO name (ID) of the board.
#### Default
None.

### `ioc_file`
`.ioc` file to work with (placed in the project root). This is not particularly useful when there is only a single one, but can be valuable when there are multiple.
#### Default
Name of the first `.ioc` file found, or an explicitly specified one.

### `cleanup_ignore`
List of paths relative to the project root that should be ignored (left) during the cleaning operation. Alternatively, each line specified can be a glob-style pattern. The list will be ignored if `cleanup_use_git` is set to True.
#### Default
Value of the `ioc_file`.

### `cleanup_use_git`
Boolean controlling the `clean` method: whether to utilize custom ignore list and remove the rest of the files or to delegate the task to git (`git clean`).
#### Default
`False`

### `last_error`
This isn't really a "parameter" and initially doesn't exist at all but appears in your config after some error occurs. This will contain an error string and its Python traceback so you can examine it later to solve the problem. This will be automatically cleared after the next successful operation on this project.
#### Default
None.
