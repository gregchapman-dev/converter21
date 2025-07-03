# ------------------------------------------------------------------------------
# Name:          abcreader.py
# Purpose:       AbcReader reads an ABC file, and converts it to a music21 stream.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2025 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
# import typing as t
import re
import music21 as m21
from converter21.abc.abc2xml import getXmlDocs
from converter21.abc.abc2xml import fixDoctype
from converter21.abc.abc2xml import expand_abc_include

class AbcReader:
    def __init__(self, dataString: str):
        self.abcString: str = dataString

        # a bit of code stolen from getXmlDocs that finds the X:n number
        # for each tune (if there's more than one tune)
        abctext: str = expand_abc_include(self.abcString)
        fragments: list[str] = re.split(r'^\s*X:', abctext, flags=re.M)
        tunes: list[str] = fragments[1:]
        self.abcNumberList: list[str] = []
        if len(tunes) > 1:
            for tune in tunes:
                numberAndTune: list[str] = tune.split('\n', 1)
                number: str = numberAndTune[0].strip()
                self.abcNumberList.append(number)

    def run(self) -> m21.stream.Score | m21.stream.Part | m21.stream.Opus:
        # convert self.abcString (abc data) to musicxml data and then
        # import _that_ into music21.
        xmlStrs: list[str] = [fixDoctype(xmlDoc)
            for xmlDoc in getXmlDocs(self.abcString, num=1000 * 1000)]
        if len(xmlStrs) == 1:
            # return a Score
            return m21.converter.parseData(xmlStrs[0], fmt='musicxml')

        if len(xmlStrs) != len(self.abcNumberList):
            # should never happen?
            # Make up the numbers
            self.abcNumberList = [str(i) for i in range(1, len(xmlStrs) + 1)]

        # return an Opus of Scores, with score.metadata.number set to the
        # abc tune reference number.
        opus = m21.stream.Opus()
        for xmlStr, number in zip(xmlStrs, self.abcNumberList):
            score = m21.converter.parseData(xmlStr)
            score.metadata.number = number
            opus.coreAppend(score)
        opus.coreElementsChanged()
        return opus
