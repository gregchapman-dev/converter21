# ------------------------------------------------------------------------------
# Name:          setup.py
# Purpose:       install converter21 package
#
# Authors:       Greg Chapman
#
# Copyright:     (c) 2021-2025 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------

import setuptools

# must be kept up to date with converter21/shared/sharedconstants.py:_CONVERTER21_VERSION et al
converter21version = '3.3.0'

if __name__ == '__main__':
    setuptools.setup(
        name='converter21',
        version=converter21version,

        description='A music21-extending format converter package and command line tool (replaces music21\'s Humdrum and MEI parser, and adds a Humdrum writer and MEI writer)',
        long_description=open('README.md').read(),
        long_description_content_type='text/markdown',

        url='https://github.com/gregchapman-dev/converter21',

        author='Greg Chapman',
        author_email='gregc@mac.com',

        classifiers=[
            'Development Status :: 5 - Production/Stable',
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python :: 3 :: Only',
            'Operating System :: OS Independent',
            'Natural Language :: English',
        ],

        keywords=[
            'music',
            'score',
            'notation',
            'converter',
            'conversion',
            'format',
            'formats',
            'humdrum',
            'kern',
            'krn',
            'MEI',
            'writer',
            'parser',
            'reader',
            'music21',
            'OMR',
            'Optical Music Recognition',
        ],

        packages=setuptools.find_packages(),

        python_requires='>=3.10',

        install_requires=[
            'music21>=9.1',
        ],

        project_urls={
            'Source': 'https://github.com/gregchapman-dev/converter21',
            'Bug Reports': 'https://github.com/gregchapman-dev/converter21/issues',
        }
    )
