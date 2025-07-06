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

class ABCImportException(Exception):
    pass

class AbcReader:
    def __init__(self, dataString: str):
        self.abcString: str = dataString
        self.abcTuneByNumber: dict[str, str] = {}

    def run(
        self,
        number: int | None
    ) -> m21.stream.Score | m21.stream.Part | m21.stream.Opus:
        # convert abc data to musicxml data and then import
        # _that_ into music21.
        xmlStrs: list[str] = []
        abcNumbers: list[str] = []
        numStr: str
        if not self.abcTuneByNumber:
            # a bit of code stolen from getXmlDocs that finds the X:n number
            # for each tune (if there's more than one tune)
            abctext: str = expand_abc_include(self.abcString)
            fragments: list[str] = re.split(r'^\s*X:', abctext, flags=re.M)
            preamble: str = fragments[0]
            tunes: list[str] = fragments[1:]
            if not tunes and preamble:
                tunes, preamble = ['1\n' + preamble], ''  # tune without X:

            self.abcTuneByNumber: dict[str, str] = {}
            for tune in tunes:
                numberAndTuneRemainder: list[str] = tune.split('\n', 1)
                numStr: str = numberAndTuneRemainder[0].strip()
                self.abcTuneByNumber[numStr] = preamble + 'X:' + tune

        if number is None:
            # all the tunes in the ABC data
            xmlStrs = [
                fixDoctype(xmlDoc) for xmlDoc in getXmlDocs(self.abcString, num=1000 * 1000)
            ]
            abcNumbers = [str(key) for key in self.abcTuneByNumber]
        else:
            numStr = str(number)
            if numStr not in self.abcTuneByNumber:
                raise ABCImportException(
                    f'cannot find requested reference number in source file: {number}'
                )
            xmlStrs = [fixDoctype(getXmlDocs(self.abcTuneByNumber[numStr])[0])]
            abcNumbers = [numStr]

        if len(xmlStrs) == 1:
            # return a Score
            score = m21.converter.parseData(xmlStrs[0], fmt='musicxml')
            score.metadata.fileNumber = abcNumbers[0]
            return score

        # return an Opus of Scores, with score.metadata.number set to the
        # abc tune reference number.
        opus = m21.stream.Opus()
        for xmlStr, numStr in zip(xmlStrs, abcNumbers):
            score = m21.converter.parseData(xmlStr)
            score.metadata.fileNumber = number
            opus.coreAppend(score)
        opus.coreElementsChanged()
        return opus
