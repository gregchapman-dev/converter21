# ------------------------------------------------------------------------------
# Name:          ABCConverter.py
# Purpose:       A music21 subconverter for MEI files.
#
# Note:          This was copied verbatim from music21/converter/subConverters.py (by
#                Michael Scott Asato Cuthbert and Christopher Ariza), and then modified
#                to live in converter21.
#
# Copyright:     (c) 2025 Greg Chapman
# License:       MIT, see LICENSE
#
# ------------------------------------------------------------------------------
import typing as t
import pathlib

from music21 import stream
from music21 import common

from music21.converter.subConverters import SubConverter

from converter21.abc import AbcReader
from converter21.abc import AbcWriter

class ABCConverter(SubConverter):
    '''
    Converter for ABC.
    '''
    registerFormats = ('abc',)
    registerInputExtensions = ('abc',)
    # registerShowFormats = ('abc',)
    registerOutputExtensions = ('abc',)

    def parseData(
        self,
        dataString: str,
        number: int | None = None
    ) -> stream.Score | stream.Part | stream.Opus:
        '''
        Convert a string with an ABC document into its corresponding music21
        elements.

        * dataString: The string with ABC to convert.

        * number: X:n reference number of ABC tune to parse. Default is ``None`` (parse them all).

        Returns the music21 objects corresponding to the ABC file (or numbered ABC tune).
        '''
        # if dataString.startswith('mei:'):
        #     dataString = dataString[4:]

        self.stream = AbcReader(dataString).run(number)

        output: stream.Stream = self.stream

        if t.TYPE_CHECKING:
            # self.stream is a property defined in SubConverter, and it's not
            # type-hinted properly.  But we know what this is.
            assert isinstance(output, (stream.Score, stream.Opus))

        return output


    def parseFile(
        self,
        filePath: str | pathlib.Path,
        number: int | None = None,
        **keywords,
    ) -> stream.Score | stream.Part | stream.Opus:
        '''
        Convert a file with an ABC document into its corresponding music21 elements.

        * filePath: Full pathname to the file containing ABC data as a string or Path.

        * number: X:n reference number of ABC tune to parse. Default is ``None`` (parse them all).

        Returns the music21 objects corresponding to the ABC file.
        '''
        # In Python 3 we try the three most likely encodings to work.
        dataStream: str
        try:
            with open(filePath, 'rt', encoding='utf-8') as f:
                dataStream = f.read()
        except UnicodeDecodeError:
            try:
                with open(filePath, 'rt', encoding='latin-1') as f:
                    dataStream = f.read()
            except UnicodeError:
                with open(filePath, 'rt', encoding='utf-16') as f:
                    dataStream = f.read()

        self.parseData(dataStream, number)

        if t.TYPE_CHECKING:
            # self.stream is a property defined in SubConverter, and it's not
            # type-hinted properly.  But we know what this is.
            assert isinstance(self.stream, (stream.Score, stream.Opus))

        return self.stream

    # pylint: disable=arguments-differ
    def write(
        self,
        obj,
        fmt,
        fp=None,
        subformats=None,
        makeNotation=True,
        abcVersion='2.1',
        **keywords
    ):
        if fp is None:
            fp = self.getTemporaryFile()
        else:
            fp = common.cleanpath(fp, returnPathlib=True)

        if not fp.suffix:
            fp = fp.with_suffix('.abc')

        abcw = AbcWriter(obj)
        abcw.makeNotation = makeNotation
        abcw.meiVersion = abcVersion

        with open(fp, 'wt', encoding='utf-8') as f:
            abcw.write(f)

        return fp
