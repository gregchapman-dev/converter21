# ------------------------------------------------------------------------------
# Name:          HumdrumConverter.py
# Purpose:       A music21 subconverter for Humdrum files.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
from pathlib import Path

from music21 import common
from music21 import stream
from music21.converter.subConverters import SubConverter

from converter21.humdrum import HumdrumFile
from converter21.humdrum import HumdrumWriter

class HumdrumConverter(SubConverter):
    '''
    Simple class wrapper for parsing Humdrum data provided in a file or in a string.
    '''
    registerFormats = ('humdrum',)
    registerInputExtensions = ('krn', 'kern')
    registerOutputExtensions = ('krn', 'kern')

    def __init__(self, **keywords) -> None:
        super().__init__(**keywords)
        self.humdrumFile: HumdrumFile | None = None

    # --------------------------------------------------------------------------

    def parseData(
        self,
        dataString: str,
        number: int | None = None,
        acceptSyntaxErrors: bool = False,
        **_keywords
    ) -> stream.Score:
        '''
        Create HumdrumFile object from a string, and create a music21 Stream from it.
        '''
        # print("parsing krn string", file=sys.stderr)
        try:
            hf = HumdrumFile(acceptSyntaxErrors=acceptSyntaxErrors)
            hf.readString(dataString)
            self.stream = hf.createMusic21Stream()
            self.stream.c21_parse_err = hf.parseError  # type: ignore
            self.humdrumFile = hf
        except Exception as e:
            if not acceptSyntaxErrors:
                raise e
            # acceptSyntaxErrors means "do not raise exceptions on syntax errors".
            # if HumdrumFile raised an exception, it could not work around all the
            # syntax errors, so we must return an empty score.
            self.stream = stream.Score()
            self.stream.c21_parse_err = f'{e}'  # type: ignore

        return self.stream

    # pylint: disable=arguments-differ
    def parseFile(
        self,
        filePath: str | Path,
        number: int | None = None,
        acceptSyntaxErrors: bool = False,
        **_keywords
    ) -> stream.Score:
        '''
        Create HumdrumFile object from a file path, and create a music21 Stream from it.
        Note that normally, implementing parseData is sufficient, but Humdrum files
        may be utf-8 or latin-1, so we need to handle various text encodings ourselves.
        '''
        # print("parsing krn file", file=sys.stderr)
        try:
            hf = HumdrumFile(fileName=filePath, acceptSyntaxErrors=acceptSyntaxErrors)
            self.stream = hf.createMusic21Stream()
            self.stream.c21_parse_err = hf.parseError  # type: ignore
            self.humdrumFile = hf
        except Exception as e:
            if not acceptSyntaxErrors:
                raise e
            # acceptSyntaxErrors means "do not raise exceptions on syntax errors".
            # if HumdrumFile raised an exception, it could not work around all the
            # syntax errors, so we must return an empty score.
            self.stream = stream.Score()
            self.stream.c21_parse_err = f'{e}'  # type: ignore

        return self.stream

    # pylint: disable=arguments-differ
    def write(
        self,
        obj,
        fmt,
        fp=None,
        subformats=None,
        makeNotation=True,
        addRecipSpine=False,
        expandTremolos=True,
        **keywords
    ):
        if fp is None:
            fp = self.getTemporaryFile()
        else:
            fp = common.cleanpath(fp, returnPathlib=True)

        if not fp.suffix:
            fp = fp.with_suffix('.krn')

        hdw = HumdrumWriter(obj)
        hdw.makeNotation = makeNotation
        hdw.addRecipSpine = addRecipSpine
        hdw.expandTremolos = expandTremolos

        with open(fp, 'w', encoding='utf8') as f:
            hdw.write(f)

        return fp
