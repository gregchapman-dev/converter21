# ------------------------------------------------------------------------------
# Name:          MEIConverter.py
# Purpose:       A music21 subconverter for MEI files.
#
# Authors:      Michael Scott Asato Cuthbert
#               Christopher Ariza
#
# Copyright:    Copyright © 2009-2015 Michael Scott Asato Cuthbert and the music21 Project
# License:      BSD, see license.txt
#
# Note:         This was copied verbatim from music21/converter/subConverters.py, and then modified
#               to live in converter21.  My hope is to eventually re-submit this as a PR to music21.
# ------------------------------------------------------------------------------
import typing as t
import pathlib

from music21 import stream
from music21.converter.subConverters import SubConverter

from converter21.mei import MeiToM21Converter

class MEIConverter(SubConverter):
    '''
    Converter for MEI. You must use an ".mei" file extension for MEI files because music21 will
    parse ".xml" files as MusicXML.
    '''
    registerFormats = ('mei',)
    registerInputExtensions = ('mei',)
    # NOTE: we're only working on import for now
    # registerShowFormats = ('mei',)
    # registerOutputExtensions = ('mei',)

    def parseData(
        self,
        dataString: str,
        number: t.Optional[int] = None
    ) -> t.Union[stream.Score, stream.Part, stream.Opus]:
        '''
        Convert a string with an MEI document into its corresponding music21 elements.

        * dataString: The string with XML to convert.

        * number: Unused in this class. Default is ``None``.

        Returns the music21 objects corresponding to the MEI file.
        '''
        if dataString.startswith('mei:'):
            dataString = dataString[4:]

        self.stream = MeiToM21Converter(dataString).run()

        output: stream.Stream = self.stream

        if t.TYPE_CHECKING:
            # self.stream is a property defined in SubConverter, and it's not
            # type-hinted properly.  But we know what this is.
            assert isinstance(output, (stream.Score, stream.Part, stream.Opus))

        return output


    def parseFile(
        self,
        filePath: t.Union[str, pathlib.Path],
        number: t.Optional[int] = None,
        **keywords,
    ) -> stream.Stream:
        '''
        Convert a file with an MEI document into its corresponding music21 elements.

        * filePath: Full pathname to the file containing MEI data as a string or Path.

        * number: Unused in this class. Default is ``None``.

        Returns the music21 objects corresponding to the MEI file.
        '''
        # In Python 3 we try the three most likely encodings to work. (UTF-16 is outputted from
        # "sibmei", the Sibelius-to-MEI exporter).  And sometimes latin-1 characters can work
        # their way in.
        dataStream: str
        try:
            with open(filePath, 'rt', encoding='utf-8') as f:
                dataStream = f.read()
        except UnicodeDecodeError:
            try:
                with open(filePath, 'rt', encoding='utf-16') as f:
                    dataStream = f.read()
            except UnicodeError:
                with open(filePath, 'rt', encoding='latin-1') as f:
                    dataStream = f.read()

        self.parseData(dataStream, number)

        return self.stream

    def checkShowAbility(self, **keywords):
        '''
        MEI export is not yet implemented.
        '''
        return False

    # def launch(self, filePath, fmt=None, options='', app=None, key=None):
    #     raise NotImplementedError('MEI export is not yet implemented.')

    def show(self, obj, fmt, app=None, subformats=None, **keywords):  # pragma: no cover
        raise NotImplementedError('MEI export is not yet implemented.')

    # def getTemporaryFile(self, subformats=None):
    #     raise NotImplementedError('MEI export is not yet implemented.')

    def write(self, obj, fmt, fp=None, subformats=None, **keywords):  # pragma: no cover
        raise NotImplementedError('MEI export is not yet implemented.')

    # def writeDataStream(self, fp, dataStr):
    #     raise NotImplementedError('MEI export is not yet implemented.')


