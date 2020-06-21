"""
To pack:
  $ pip3 install wheel
  $ python3 setup.py sdist bdist_wheel

To upload to PyPI:
  $ python3 -m twine upload dist/*
"""

import setuptools

setuptools.setup()
