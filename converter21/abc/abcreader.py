# ------------------------------------------------------------------------------
# Name:          abcreader.py
# Purpose:       AbcReader reads an ABC file, and converts it to a music21 stream.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2025 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import music21 as m21
from converter21.abc.abc2xml import getXmlDocs
from converter21.abc.abc2xml import fixDoctype

class AbcReader:
    def __init__(self, dataString: str):
        self.abcString: str = dataString

    def run(self) -> m21.stream.Score | m21.stream.Part | m21.stream.Opus:
        # convert self.abcString (abc data) to musicxml data and then
        # import _that_ into music21.
        xmlDocs = getXmlDocs(self.abcString, num=1)
        xmlStr: str = fixDoctype(xmlDocs[0])
        return m21.converter.parseData(xmlStr, fmt='musicxml')

