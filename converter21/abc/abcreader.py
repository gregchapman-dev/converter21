# ------------------------------------------------------------------------------
# Name:          abcreader.py
# Purpose:       AbcReader reads an ABC file, and converts it to a music21 stream.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2025 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
import typing as t
import re

import music21 as m21

from converter21.shared import M21Utilities
from converter21.abc import abc2xml
from converter21.abc import AbcMetadata

class AbcImportException(Exception):
    pass


LIMIT_NEEDED: int = 10000

class AbcReader:
    def __init__(self, dataString: str):
        limit: int = sys.getrecursionlimit()
        if limit < LIMIT_NEEDED:
            sys.setrecursionlimit(LIMIT_NEEDED)
        self.abcString: str = dataString
        self.abcTuneByNumber: dict[str, str] = {}
        self.abcTuneHeaderLinesByNumber: dict[str, list[str]] = {}
        self.numberForAbcTune: dict[str, str] = {}
        self.abcTunesInDocumentOrder: list[str] = []

    def run(
        self,
        number: int | None
    ) -> m21.stream.Score | m21.stream.Part | m21.stream.Opus:
        # convert abc data to musicxml data and then import
        # _that_ into music21.

        xmlStrs: list[str] = []
        numStr: str
        if not self.abcTuneByNumber:
            # a bit of code stolen from abc2xml.getXmlDocs that finds the X:n number for
            # each tune (if there's more than one tune), and the associated tune.
            abctext: str = abc2xml.expand_abc_include(self.abcString)
            fragments: list[str] = re.split(r'^\s*X:', abctext, flags=re.M)
            preamble: str = fragments[0]
            tunes: list[str] = fragments[1:]
            if not tunes and preamble:
                tunes, preamble = ['1\n' + preamble], ''  # tune without X:

            self.abcTunesInDocumentOrder = []

            for tune in tunes:
                numberAndTuneRemainder: list[str] = tune.split('\n', 1)
                numStr = numberAndTuneRemainder[0].strip()
                fullTuneText: str = preamble + 'X:' + tune
                self.abcTunesInDocumentOrder.append(fullTuneText)
                self.abcTuneByNumber[numStr] = fullTuneText
                self.numberForAbcTune[fullTuneText] = numStr
                self.abcTuneHeaderLinesByNumber[numStr] = fullTuneText.split('\n')

        abcNumbers: list[str] = []
        if number is None:
            # all the tunes in the ABC data (in doc order)
            abcNumbers = []
            for tune in self.abcTunesInDocumentOrder:
                numStr = self.numberForAbcTune[tune]
                abcNumbers.append(numStr)
                xmlDoc = abc2xml.getXmlDocs(
                    self.abcTuneByNumber[numStr],
                    rOpt=True
                )[0]
                xmlStr: str = abc2xml.fixDoctype(xmlDoc)
                xmlStrs.append(xmlStr)
        else:
            numStr = str(number)
            if numStr not in self.abcTuneByNumber:
                raise AbcImportException(
                    f'cannot find requested reference number in source file: {number}'
                )
            abcNumbers = [numStr]
            xmlDoc = abc2xml.getXmlDocs(
                self.abcTuneByNumber[numStr],
                rOpt=True
            )[0]
            xmlStrs = [abc2xml.fixDoctype(xmlDoc)]

        if len(xmlStrs) == 1:
            # return a Score
            score = m21.converter.parseData(xmlStrs[0], fmt='musicxml')
            if t.TYPE_CHECKING:
                assert isinstance(score, m21.stream.Score)
            score.metadata = AbcMetadata.abcHeaderLinesToM21Metadata(
                self.abcTuneHeaderLinesByNumber[abcNumbers[0]]
            )
            mdNumbers = score.metadata['number']
            if len(mdNumbers) == 1 and str(mdNumbers[0]) == '1':
                # There's only one tune (len(xmlStrs) == 1), and it contained X:1,
                # which is meaningless, so delete that metadata item.
                score.metadata['number'] = None
            M21Utilities.fixupBadBeams(score, inPlace=True)
            return score

        # return an Opus of Scores, with each score.metadata.number set to the
        # abc tune reference number.
        opus = m21.stream.Opus()
        for xmlStr, numStr in zip(xmlStrs, abcNumbers):
            score = m21.converter.parseData(xmlStr)
            if t.TYPE_CHECKING:
                assert isinstance(score, m21.stream.Score)
            score.metadata = AbcMetadata.abcHeaderLinesToM21Metadata(
                self.abcTuneHeaderLinesByNumber[numStr]
            )
            opus.coreAppend(score)
        opus.coreElementsChanged()
        M21Utilities.fixupBadBeams(opus, inPlace=True)
        # if self.preambleHeaderLines:
        #     opus.metadata = AbcMetadata.abcHeaderLinesToM21Metadata(
        #         opus, self.preambleHeaderLines
        #     )
        return opus
