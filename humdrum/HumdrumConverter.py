# ------------------------------------------------------------------------------
# Name:          HumdrumConverter.py
# Purpose:       A music21 subconverter for Humdrum files.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021 Greg Chapman
# License:       BSD, see LICENSE
# ------------------------------------------------------------------------------
import sys
from music21 import converter
from music21 import environment

from humdrum import HumdrumFile

_MOD = 'converter21.HumdrumConverter'
environLocal = environment.Environment(_MOD)

class HumdrumConverter(converter.subConverters.SubConverter):
    '''
    Simple class wrapper for parsing Humdrum data provided in a file or in a string.
    '''
    registerFormats = ('humdrum',)
    registerInputExtensions = ('krn',)
    registerOutputExtensions = ('krn',)

    def __init__(self, **keywords):
        super().__init__(**keywords)
        self.humdrumFile = None

    # --------------------------------------------------------------------------

    def parseData(self, dataString, number=None):
        '''Create HumdrumFile object from a string, and create a music21 Stream from it.

        >>> humData = ('**kern\\n*M2/4\\n=1\\n24r\\n24g#\\n24f#\\n24e\\n24c#\\n' +
        ...     '24f\\n24r\\n24dn\\n24e-\\n24gn\\n24e-\\n24dn\\n*-')
        >>> c = converter.subConverters.HumdrumConverter()
        >>> s = c.parseData(humData)
        >>> c.stream.show('text')
        {0.0} <music21.metadata.Metadata object at 0x7f33545027b8>
        {0.0} <music21.stream.Part spine_0>
            {0.0} <music21.stream.Measure 1 offset=0.0>
                {0.0} <music21.meter.TimeSignature 2/4>
                {0.0} <music21.note.Rest rest>
                {0.1667} <music21.note.Note G#>
                {0.3333} <music21.note.Note F#>
                {0.5} <music21.note.Note E>
                {0.6667} <music21.note.Note C#>
                {0.8333} <music21.note.Note F>
                {1.0} <music21.note.Rest rest>
                {1.1667} <music21.note.Note D>
                {1.3333} <music21.note.Note E->
                {1.5} <music21.note.Note G>
                {1.6667} <music21.note.Note E->
                {1.8333} <music21.note.Note D>
        '''
        print("parsing krn string", file=sys.stderr)
        hf = HumdrumFile()
        hf.readString(dataString)
        self.stream = hf.createMusic21Stream()
        self.humdrumFile = hf
        return self.stream

    def parseFile(self, filePath, number=None):
        '''
        Create HumdrumFile object from a file path, and create a music21 Stream from it.
        Note that normally, implementing parseData is sufficient, but Humdrum files
        may be utf-8 or latin-1, so we need to handle various text encodings ourselves.
        '''
        print("parsing krn file", file=sys.stderr)
        hf = HumdrumFile(filePath)
        self.stream = hf.createMusic21Stream()
        self.humdrumFile = hf
        return self.stream

    def write(self, obj, fmt, fp=None, subformats=None, **keywords):
        print("writing to krn file", file=sys.stderr)

        if fp is None:
            fp = environLocal.getTempFile('.krn')

#         hdw = HumdrumWriter(obj)
#         hdw.write(fp)

        return fp
