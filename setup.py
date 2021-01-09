"""
To pack:
  $ pip3 install wheel
  $ python3 setup.py sdist bdist_wheel

To upload to PyPI:
  $ python3 -m twine upload dist/*
"""

import setuptools

setuptools.setup(use_scm_version=True)  # use_scm_version option can be placed only in an old-school setup.py atm...
