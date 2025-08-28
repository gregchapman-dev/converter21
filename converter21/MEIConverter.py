# ------------------------------------------------------------------------------
# Name:          MEIConverter.py
# Purpose:       A music21 subconverter for MEI files.
#
# Note:          This file was copied verbatim from music21/converter/subConverters.py (by
#                Michael Scott Asato Cuthbert and Christopher Ariza), and then modified
#                to live in converter21.
#
# Copyright:     (c) 2021-2025 Greg Chapman
# License:       MIT, see LICENSE
#
# ------------------------------------------------------------------------------
import typing as t
import pathlib

from music21 import stream
from music21 import common
from music21 import environment

from music21.converter.subConverters import SubConverter

from converter21.mei import MeiReader
from converter21.mei import MeiWriter

environLocal = environment.Environment('converter21.mei.meireader')

class MEIConverter(SubConverter):
    '''
    Converter for MEI. You must use an ".mei" file extension for MEI files because music21 will
    parse ".xml" files as MusicXML.
    '''
    registerFormats = ('mei',)
    registerInputExtensions = ('mei',)
    # registerShowFormats = ('mei',)
    registerOutputExtensions = ('mei',)

    def parseData(
        self,
        dataString: str,
        number: int | None = None
    ) -> stream.Score | stream.Part | stream.Opus:
        '''
        Convert a string with an MEI document into its corresponding music21 elements.

        * dataString: The string with XML to convert.

        * number: Score number. Default is `None`.  If there are any missing numbers
            in the document to match against, number is interpreted as a 1-based
            index into the scores found in document order.

        Returns the music21 objects corresponding to the MEI file.
        :raises: :exc:`MeiValidityError` when the MEI file is not valid XML.
        '''
        self.stream = MeiReader(dataString).run(number)
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
        Convert a file with an MEI document into its corresponding music21 elements.

        * filePath: Full pathname to the file containing MEI data as a string or Path.

        * number: One-based score number within `<meiCorpus>`. Default is `None`.

        Returns the music21 objects corresponding to the MEI file.
        :raises: :exc:`MeiValidityError` when the MEI file is not valid XML.
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
        meiVersion='5',
        multipleScoresHostTag='mdiv',
        **keywords
    ):
        if fp is None:
            fp = self.getTemporaryFile()
        else:
            fp = common.cleanpath(fp, returnPathlib=True)

        if not fp.suffix:
            fp = fp.with_suffix('.mei')

        meiw = MeiWriter(obj, makeNotation, meiVersion, multipleScoresHostTag)

        with open(fp, 'wt', encoding='utf-8') as f:
            meiw.write(f)

        return fp
