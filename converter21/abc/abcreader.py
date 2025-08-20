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
from xml.etree.ElementTree import Element

import music21 as m21

from converter21.shared import M21Utilities
from converter21.abc.abc2xml import getXmlDocs
from converter21.abc.abc2xml import fixDoctype
from converter21.abc.abc2xml import expand_abc_include

class ABCImportException(Exception):
    pass

class AbcReader:
    def __init__(self, dataString: str):
        self.abcString: str = dataString
        self.abcTuneByNumber: dict[str, str] = {}
        self.numberForAbcTune: dict[str, str] = {}
        self.abcTunesInDocumentOrder: list[str] = []

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
            # a bit of code stolen from getXmlDocs that finds the X:n number for
            # each tune (if there's more than one tune), and the associated tune.
            abctext: str = expand_abc_include(self.abcString)
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

        if number is None:
            # all the tunes in the ABC data (in doc order)
            xmlDocs: list[Element] = []
            abcNumbers = []
            for tune in self.abcTunesInDocumentOrder:
                numStr = self.numberForAbcTune[tune]
                xmlDocs.extend(getXmlDocs(self.abcTuneByNumber[numStr]))
                abcNumbers.append(numStr)

            for xmlDoc in xmlDocs:
                self.tweakXmlDoc(xmlDoc)
                xmlStr: str = fixDoctype(xmlDoc)
                xmlStrs.append(xmlStr)
        else:
            numStr = str(number)
            if numStr not in self.abcTuneByNumber:
                raise ABCImportException(
                    f'cannot find requested reference number in source file: {number}'
                )
            xmlDoc = getXmlDocs(self.abcTuneByNumber[numStr])[0]
            self.tweakXmlDoc(xmlDoc)
            xmlStrs = [fixDoctype(xmlDoc)]
            abcNumbers = [numStr]

        if len(xmlStrs) == 1:
            # return a Score
            score = m21.converter.parseData(xmlStrs[0], fmt='musicxml')
            if t.TYPE_CHECKING:
                assert isinstance(score, m21.stream.Score)
            score.metadata.number = abcNumbers[0]
            M21Utilities.fixupBadBeams(score, inPlace=True)
            return score

        # return an Opus of Scores, with each score.metadata.number set to the
        # abc tune reference number.
        opus = m21.stream.Opus()
        for xmlStr, numStr in zip(xmlStrs, abcNumbers):
            score = m21.converter.parseData(xmlStr)
            score.metadata.number = numStr
            opus.coreAppend(score)
        opus.coreElementsChanged()
        M21Utilities.fixupBadBeams(opus, inPlace=True)
        return opus

    @staticmethod
    def tweakXmlDoc(xmlDoc: Element):
        # munge any miscellaneous metadata names (e.g. 'notes') into music21-style
        # namespaced names (e.g. 'dcterms:description')
        miscfields = xmlDoc.findall('*/*/miscellaneous-field')
        for mf in miscfields:
            if 'name' in mf.attrib:
                name: str = mf.attrib['name']
                if name == 'notes':
                    mf.attrib['name'] = 'dcterms:description'
                    continue
                if name == 'history':
                    mf.attrib['name'] = 'dcterms:description'
                    continue
                if name in ('origin', 'area'):
                    if mf.text and (';' in mf.text or ',' in mf.text):
                        # locale (city, town, or village) of composition
                        mf.attrib['name'] = 'humdrum:OPC'
                    else:
                        # country of composition
                        mf.attrib['name'] = 'humdrum:OCY'
                    continue
                if name == 'book':
                    # parentTitle
                    mf.attrib['name'] = 'humdrum:OPR'
