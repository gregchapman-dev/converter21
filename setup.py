# ------------------------------------------------------------------------------
# Name:          setup.py
# Purpose:       install
#
# Authors:       Greg Chapman
#
# Copyright:     (c) 2021 Greg Chapman
# License:       BSD, see LICENSE
# ------------------------------------------------------------------------------

import setuptools

converter21version = '0.9.0'

if __name__ == '__main__':
    setuptools.setup(
        name='converter21',
        version=converter21version,
        author='Greg Chapman',
        author_email='gregc@mac.com',
        url='https://github.com/gregchapman-dev/converter21',
        license='BSD',
        python_requires='>=3.7',
        description='music21-based score converter tool with a new Humdrum converter',
        long_description=open('README.md').read(),
        packages=setuptools.find_packages(),
        install_requires=[
            'music21',
        ],
    )
