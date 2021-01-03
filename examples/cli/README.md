# Command line interface usage

1. Run the CubeMX, choose an MCU/board, make all desired tweaks
2. Select the `Project Manager -> Project` tab, specify a "Project Name", choose "Other Toolchains (GPDSC)". In the `Code Generator` tab check "Copy only the necessary library files" and "Generate periphery initialization as a pair of '.c/.h' files per peripheral" options

![Code Generator tab](/examples/cli/tab_CodeGenerator.png)

3. Back in the first tab (Project) copy the "Toolchain Folder Location" string. Save the project

![Project tab](/examples/cli/tab_Project.png)

4. Use the copied string (project folder) as a `-d` argument for the stm32pio (can be omitted if your current working directory is already a project directory).
5. Run `platformio boards` (`pio boards`) or go to [boards](https://docs.platformio.org/en/latest/boards) to list all supported devices. Pick one and use its ID as a `-b/--board` argument (for example, `nucleo_f031k6`)
6. All done! You can now run
   ```shell script
   $ stm32pio new -d path/to/project/ -b nucleo_f031k6 --start-editor=code --with-build
   ```
   to trigger the code generation, compile the project and start the VSCode editor with the folder opened (last 2 options are given as an example and they are not required). Make sure you have all the tools in PATH (`java` (or set its path in `stm32pio.ini`), `platformio`, `python`, editor). You can use a slightly shorter syntax if you are already located in the project directory:
   ```shell script
   path/to/project/ $   stm32pio new -b nucleo_f031k6
   ```
7. To get the information about the current state of the project use `status` command.
8. If you will be in need to update the hardware configuration in a future, make all the necessary stuff in CubeMX and run `generate` command in a similar way:
   ```shell script
   $ stm32pio generate -d /path/to/project
   ```
9. To clean-up the directory and keep only an `.ioc` file run the `clean` command.
10. If you're facing some errors complaining about some tool incorrectness, run `validate` command to check the current environment in terms of the tools' presence in your system.
