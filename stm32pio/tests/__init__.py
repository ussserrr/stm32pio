"""
Some unit-tests for stm32pio. Should be as a package or module to be able to be running by 'unittest discover' so that
is why we have this __init__.py. Uses sample project to generate and build it. It's OK to get errors on
`test_run_editor` one because you don't necessarily should have all of the editors. Run as

python3 -m unittest discover -v -s stm32pio/tests/ -t stm32pio/

(from repo's root)
"""
