# ------------------------------------------------------------------------------
# Name:          abcreader.py
# Purpose:       AbcReader reads an ABC file, and converts it to a music21 stream.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2025 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import typing as t
import re
import copy
# from xml.etree.ElementTree import Element

import music21 as m21

from converter21.shared import M21Utilities
from converter21.shared import SharedConstants
from converter21.abc import abc2xml

class ABCImportException(Exception):
    pass

class AbcReader:
    def __init__(self, dataString: str):
        self.abcString: str = dataString
        self.abcTuneByNumber: dict[str, str] = {}
        self.numberForAbcTune: dict[str, str] = {}
        self.abcTunesInDocumentOrder: list[str] = []
        self.headerFieldsByTuneNumber: dict[str, dict[str, str]] = {}

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

        abcNumbers: list[str] = []
        if number is None:
            # all the tunes in the ABC data (in doc order)
            abcNumbers = []
            for tune in self.abcTunesInDocumentOrder:
                numStr = self.numberForAbcTune[tune]
                abcNumbers.append(numStr)
                xmlDoc = abc2xml.getXmlDocs(self.abcTuneByNumber[numStr])[0]
                self.headerFieldsByTuneNumber[numStr] = copy.copy(
                    abc2xml.mxm.header_fields_for_converter21
                )
                xmlStr: str = abc2xml.fixDoctype(xmlDoc)
                xmlStrs.append(xmlStr)
        else:
            numStr = str(number)
            if numStr not in self.abcTuneByNumber:
                raise ABCImportException(
                    f'cannot find requested reference number in source file: {number}'
                )
            abcNumbers = [numStr]
            xmlDoc = abc2xml.getXmlDocs(self.abcTuneByNumber[numStr])[0]
            self.headerFieldsByTuneNumber[numStr] = copy.copy(
                abc2xml.mxm.header_fields_for_converter21
            )
            xmlStrs = [abc2xml.fixDoctype(xmlDoc)]

        if len(xmlStrs) == 1:
            # return a Score
            score = m21.converter.parseData(xmlStrs[0], fmt='musicxml')
            if t.TYPE_CHECKING:
                assert isinstance(score, m21.stream.Score)
            score.metadata = self.computeAbcMetadata(self.headerFieldsByTuneNumber[abcNumbers[0]])
            M21Utilities.fixupBadBeams(score, inPlace=True)
            return score

        # return an Opus of Scores, with each score.metadata.number set to the
        # abc tune reference number.
        opus = m21.stream.Opus()
        for xmlStr, numStr in zip(xmlStrs, abcNumbers):
            score = m21.converter.parseData(xmlStr)
            if t.TYPE_CHECKING:
                assert isinstance(score, m21.stream.Score)
            score.metadata = self.computeAbcMetadata(self.headerFieldsByTuneNumber[numStr])
            opus.coreAppend(score)
        opus.coreElementsChanged()
        M21Utilities.fixupBadBeams(opus, inPlace=True)
        # if self.preambleHeaderFields:
        #     self.computeAbcMetadata(opus, self.preambleHeaderFields)
        return opus

    @staticmethod
    def computeAbcMetadata(headerFields: dict[str, str]) -> m21.metadata.Metadata:
        def addValue(md: m21.metadata.Metadata, mdKey: str, hfValue: str):
            md.add(mdKey, hfValue)

        def addCustomValue(md: m21.metadata.Metadata, mdKey: str, hfValue: str):
            md.addCustom(mdKey, hfValue)

        def addValues(md: m21.metadata.Metadata, mdKey: str, hfValue: str):
            hfValues: list[str] = splitValues(hfValue)
            md.add(mdKey, hfValues)

        def addCustomValues(md: m21.metadata.Metadata, mdKey: str, hfValue: str):
            hfValues: list[str] = splitValues(hfValue)
            md.addCustom(mdKey, hfValues)

        def splitValues(hfValue: str) -> list[str]:
            return hfValue.split('\n')

        md = m21.metadata.Metadata()

        # music21 is already in the md.software list, add converter21, and then
        # we will add any I:abc-creator we happen to see as well.
        verStr: str = SharedConstants._CONVERTER21_NAME_AND_VERSION
        md.add('software', verStr)

        for hfKey, hfValue in headerFields.items():
            if hfKey in ('K', 'L', 'M', 'Q', 'P', 'U'):
                # header data that is not metadata
                continue

            if hfKey in ('N', 'H', 'W', 'R', 'G'):
                # There is no standard metadata key in music21 for these, so we
                # make up a custom namespace:name such as 'abc:N', etc.
                # N = notes: such as references to other tunes which are similar,
                #   details on how the original notation of the tune was converted
                #   to abc, etc
                # H = history: designed for multi-line notes, stories and anecdotes
                # W = untimed lyrics: to be printed after the music, for example
                # R = rhythm: an indication of the type of tune (e.g. hornpipe, double jig,
                #   single jig, 48-bar polka, etc).
                # G: grouping key (used for so many different things)
                addCustomValues(md, 'abc:' + hfKey, hfValue)
            elif hfKey == 'X':
                addValue(md, 'number', hfValue)
            elif hfKey == 'T':
                addValues(md, 'title', hfValue)
            elif hfKey == 'C':
                addValues(md, 'composer', hfValue)
            elif hfKey == 'B':  # 'book'
                addValues(md, 'parentTitle', hfValue)
            elif hfKey == 'F':  # file URL
                addValues(md, 'filePath', hfValue)
            elif hfKey == 'D':  # discography
                # instead of abc:D, we use Humdrum's existing recording title item
                # Note that MEI import from verovio-translated ABC -> MEI will need
                # to read abc:D and set it as humdrum:RTL in the music21 metadata.
                addCustomValues(md, 'humdrum:RTL', hfValue)  # 'album title'
            elif hfKey in ('O', 'A'):
                # 'A' is deprecated, we will read it, but write it as 'O'
                vals = splitValues(hfValue)
                for val in vals:
                    if ';' in val or ',' in val:
                        addValue(md, 'localeOfComposition', val)
                    else:
                        addValue(md, 'countryOfComposition', val)
            elif hfKey in ('I', 'Z'):
                # These are prefixed with 'abc-something '
                vals = splitValues(hfValue)
                for val in vals:
                    abcNameAndValue = val.split(' ', 1)
                    if len(abcNameAndValue) == 1:
                        if hfKey == 'Z':
                            # no space-delimited abcName, so val is the encoder
                            addValue(md, 'electronicEncoder', val)
                            continue

                    abcName = abcNameAndValue[0]
                    if not abcName.startswith('abc'):
                        if hfKey == 'Z':
                            # no parseable abcName, so val is the encoder
                            addValue(md, 'electronicEncoder', val)
                            continue
                        if hfKey == 'I':
                            # we ignore unparseable I: abcNames because there are a lot,
                            # and they are generally not metadata.
                            continue

                    abcValue = abcNameAndValue[1]
                    if hfKey == 'Z':
                        if abcName == 'abc-transcription':
                            addValue(md, 'electronicEncoder', abcValue)
                        elif abcName == 'abc-edited-by':
                            addValue(md, 'electronicEditor', abcValue)
                        elif abcName == 'abc-copyright':
                            addValue(md, 'copyright', abcValue)
                        else:
                            addCustomValue(md, 'abc:Z:' + abcName, abcValue)
                    elif hfKey == 'I':
                        # ignore everything but 'abc-creator'
                        if abcName == 'abc-creator':
                            addValue(md, 'software', abcValue)
                        else:
                            addCustomValue(md, 'abc:I:' + abcName, abcValue)
            else:
                pass  # print(f'need to support {hfKey}')

        return md
