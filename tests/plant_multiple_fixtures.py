import pathlib

FIXTURE = (pathlib.Path(__file__).parent / 'fixtures' / 'nucleo_f031k6' / 'nucleo_f031k6.ioc').resolve(strict=True)
LOCATION = (pathlib.Path.home() / 'stm32pio-gui-test-projects').resolve()
LOCATION.mkdir(exist_ok=True)
NAMES = ['Avocado',
         'Blackberry',
         'Orange',
         'Banana',
         'Watermelon',
         'Pear',
         'Strawberry',
         'Plum',
         'Apple',
         'Lemon',
         'Cherry',
         'Grape',
         'Lychee',
         'Peach',
         'Melon',
         'Mango']

for name in NAMES:
    (LOCATION / name).mkdir()
    content = FIXTURE.read_text().replace('nucleo_f031k6', name)
    (LOCATION / name / f'{name}.ioc').write_text(content)
