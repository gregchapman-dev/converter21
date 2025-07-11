# ------------------------------------------------------------------------------
# Name:          MEIConverter.py
# Purpose:       A music21 subconverter for MEI files.
#
# Note:          This was copied verbatim from music21/converter/subConverters.py (by
#                Michael Scott Asato Cuthbert and Christopher Ariza), and then modified
#                to live in converter21.
#
# Copyright:     (c) 2021-2023 Greg Chapman
# License:       MIT, see LICENSE
#
# ------------------------------------------------------------------------------
import typing as t
import pathlib
from xml.etree.ElementTree import fromstring, Element, ElementTree, ParseError

from music21 import stream
from music21 import common
from music21 import environment

from music21.converter.subConverters import SubConverter

from converter21.mei import MeiReader, MEI_NS, INVALID_XML_DOC, WRONG_ROOT_ELEMENT
from converter21.mei import MeiValidityError
from converter21.mei import MeiElementError
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

        * number: One-based score number within `<meiCorpus>`. Default is `None`.

        Returns the music21 objects corresponding to the MEI file.
        :raises: :exc:`MeiValidityError` when the MEI file is not valid XML.
        '''
        if dataString.startswith('mei:'):
            dataString = dataString[4:]

        try:
            documentRoot = fromstring(dataString)
            if isinstance(documentRoot, ElementTree):
                documentRoot = documentRoot.getroot()
        except ParseError as parseErr:
            environLocal.warn(
                '\n\nERROR: Parsing the MEI document with ElementTree failed.')
            environLocal.warn(f'We got the following error:\n{parseErr}')
            raise MeiValidityError(INVALID_XML_DOC)

        # Check for <meiCorpus>, and if present, make an Opus, read
        # <meiCorpus><meiHead> into opus.metadata, and make an MeiReader
        # for each enclosed <mei> element, putting the resulting score(s)
        # into the Opus.
        if documentRoot.tag == f'{MEI_NS}meiCorpus':
            meiVersion: str = documentRoot.attrib.get('meiversion', '')
            if not meiVersion:
                raise MeiAttributeError('No @meiversion on root element.')

            if number is None:
                self.stream = stream.Opus()
            meiRoots: list[Element] = documentRoot.findall(f'./{MEI_NS}mei')
            for scoreIdx, meiRoot in enumerate(meiRoots):
                if number is None:
                    score = MeiReader(meiRoot, meiVersion).run()
                    self.stream.append(score)
                else:
                    # we only want a particular score
                    scoreNum: int = scoreIdx + 1
                    if number == scoreNum:
                        self.stream = MeiReader(meiRoot).run()
                        break
        elif documentRoot.tag == f'{MEI_NS}mei':
            self.stream = MeiReader(documentRoot).run()
        else:
            # bad root tag
            raise MeiElementError(WRONG_ROOT_ELEMENT.format(documentRoot.tag))

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
        **keywords
    ):
        if fp is None:
            fp = self.getTemporaryFile()
        else:
            fp = common.cleanpath(fp, returnPathlib=True)

        if not fp.suffix:
            fp = fp.with_suffix('.mei')

        meiw = MeiWriter(obj)
        meiw.makeNotation = makeNotation
        meiw.meiVersion = meiVersion

        with open(fp, 'wt', encoding='utf-8') as f:
            meiw.write(f)

        return fp
