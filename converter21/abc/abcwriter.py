# ------------------------------------------------------------------------------
# Name:          abcwriter.py
# Purpose:       AbcWriter is an object that takes a music21 stream and
#                writes it to a file as ABC data.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2025 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
import typing as t

import music21 as m21
from music21.musicxml import helpers
from music21.musicxml.m21ToXml import ScoreExporter

from converter21.shared import M21Utilities
from converter21.abc.xml2abc import vertaal as convertMusicXMLToABC
from converter21.abc import AbcMetadata

class AbcExportError(Exception):
    pass

class AbcWriter:
    def __init__(self, obj: m21.prebase.ProtoM21Object) -> None:
        M21Utilities.adjustMusic21Behavior()

        self._m21Object: m21.prebase.ProtoM21Object = obj
        self._m21ScoreOrOpus: m21.stream.Score | m21.stream.Opus | None = None

        # default options (these can be set to non-default values by clients,
        # as long as they do it before they call write())

        # client can set to False if obj is a Score
        self.makeNotation: bool = True

        # In future, client may be able to set self.abcVersion to '2.1' or '2.2'.
        # Always assume 2.1 for now.
        # self.abcVersion: str = '2.1'

    @staticmethod
    def scoreToMusicXmlString(score: m21.stream.Score, makeNotation: bool) -> str:
        scoreExporter = ScoreExporter(score, makeNotation=makeNotation)
        scoreExporter.parse()
        output: str = scoreExporter.xmlHeader().decode('utf-8')  # very small encode/decode
        output += helpers.dumpString(scoreExporter.xmlRoot, noCopy=True)
        return output

    def write(self, fp) -> bool:
        if self.makeNotation:
            if isinstance(self._m21Object, m21.stream.Opus):
                self._m21ScoreOrOpus = M21Utilities.makeWellFormedOpus(self._m21Object)
            else:
                self._m21ScoreOrOpus = M21Utilities.makeScoreFromObject(self._m21Object)
        else:
            if not isinstance(self._m21Object, (m21.stream.Score, m21.stream.Opus)):
                raise AbcExportError(
                    'Since makeNotation=False, source obj must be a music21'
                    ' Score/Opus, and it is not.'
                )
            if not self._m21Object.isWellFormedNotation():
                print('Source obj is not well-formed; see isWellFormedNotation()', file=sys.stderr)

            self._m21ScoreOrOpus = self._m21Object
        del self._m21Object  # everything after this uses self._m21ScoreOrOpus

        abcStr: str = ''
        xmlStr: str = ''

        # Now convert to MusicXML
        if isinstance(self._m21ScoreOrOpus, m21.stream.Score):
            xmlStr = self.scoreToMusicXmlString(self._m21ScoreOrOpus, self.makeNotation)

            # Now run that MusicXML through xml2abc.vertaal (MusicXML str -> ABC str)
            abcStr, _ = convertMusicXMLToABC(xmlStr, wev=1)
            abcStr = self.fixupAbcHeaderFields(
                abcStr,
                self._m21ScoreOrOpus.metadata,
                None)

        else:  # it's an Opus
            if t.TYPE_CHECKING:
                assert isinstance(self._m21ScoreOrOpus, m21.stream.Opus)
            # if the scores in the Opus have unique numbers in their metadata,
            # then write out those numbers as X:n, else make up the X:n numbers.
            useExistingNums: bool = True
            existingNums: list[str | None] = self._m21ScoreOrOpus.getNumbers()
            for num in existingNums:
                if num is None:
                    useExistingNums = False
                    break
            if useExistingNums:
                uniqueNums: list[str | None] = list(set(existingNums))
                if len(uniqueNums) != len(existingNums):
                    useExistingNums = False

            nextNumber: int | None = None
            if not useExistingNums:
                nextNumber = 0

            for score in self._m21ScoreOrOpus.scores:
                if not useExistingNums:
                    if t.TYPE_CHECKING:
                        assert nextNumber is not None
                    nextNumber += 1

                xmlStr = self.scoreToMusicXmlString(score, self.makeNotation)

                scoreAbcStr: str
                scoreAbcStr, _ = convertMusicXMLToABC(xmlStr, wev=1)
                scoreAbcStr = self.fixupAbcHeaderFields(
                    scoreAbcStr,
                    score.metadata,
                    nextNumber)

                if abcStr:
                    abcStr += '\n'

                abcStr += scoreAbcStr

        fp.write(abcStr)
        return True

    _INFO_LINE_STARTS_TO_DELETE: tuple[str, ...] = (
        'A',  # area (deprecated; we read 'A' but write 'O')
        'B',  # book
        'C',  # composer
        'D',  # discography
        'F',  # file URL
        'G',  # group by
        'H',  # history
        'I:abc-creator',  # we will set this to 'converter21 vm.n'
        'N',  # notes
        'O',  # origin (location)
        'R',  # rhythm
        'S',  # source
        'T',  # title
        'W',  # words (untimed lyrics)
        'X',  # reference number (tune number)
        'Z',  # transcription
    )

    def fixupAbcHeaderFields(
        self,
        abcStr: str,
        md: m21.metadata.Metadata,
        xNumber: int | None
    ) -> str:
        # Strip out all the header fields that are metadata, and reconstruct
        # them from md.

        def shouldDelete(abcLine: str) -> bool:
            for s in self._INFO_LINE_STARTS_TO_DELETE:
                if abcLine.startswith(s):
                    return True
            return False

        abcLines: list[str] = abcStr.split('\n')
        _headerLines: list[str] = []  # debugging only

        currIdx: int = 0
        while True:
            # inc or shrink loop
            abcLine = abcLines[currIdx].strip()

            if shouldDelete(abcLine):
                _headerLines.append(abcLine)  # debugging only
                # shrink (currIdx will point at next line)
                del abcLines[currIdx]
            else:
                # inc (currIdx will point at next line)
                currIdx += 1

            if abcLine[0] == 'K':
                break

        newInfoLines: list[str] = AbcMetadata.m21MetadataToAbcHeaderLines(md, xNumber)
        allLines: list[str] = newInfoLines + abcLines
        return '\n'.join(allLines)
