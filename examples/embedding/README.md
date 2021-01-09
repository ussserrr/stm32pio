# Embedding

You can also use the stm32pio as an ordinary Python package and embed it in your own application. It is a minimal example. Long story short, you need to import the core module' project class, _optionally_ set up a logging and you are good to go. If you prefer a higher-level API similar to the CLI version, use the `main()` function from the `stm32pio.cli.app` passing same CLI arguments to it.
