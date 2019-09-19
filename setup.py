import setuptools

from stm32pio import __version__

with open("README.md", 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name="stm32pio",
    version=__version__,
    author="ussserrr",
    author_email="andrei4.2008@gmail.com",
    description="Small cross-platform Python app that can create and update PlatformIO projects from STM32CubeMX .ioc "
                "files.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ussserrr/stm32pio",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'stm32pio = stm32pio.stm32pio:main'
        ]
    }
)
