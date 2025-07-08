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
from converter21.shared import M21Utilities
from converter21.abc.xml2abc import vertaal as convertMusicXMLToABC

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
            xmlFp = self._m21ScoreOrOpus.write(
                fmt='musicxml', fp=None, makeNotation=self.makeNotation
            )
            if xmlFp is None:
                raise AbcExportError(
                    'Export to temporary MusicXML file failed.'
                )
            with open(xmlFp, 'r', encoding='utf8') as xmlFpOut:
                xmlStr = xmlFpOut.read()

            # Now run that MusicXML through xml2abc.vertaal (MusicXML str -> ABC str)
            abcStr, _ = convertMusicXMLToABC(xmlStr)
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

            nextNumber: int = 0
            for score in self._m21ScoreOrOpus.scores:
                if useExistingNums:
                    nextNumber = score.metadata.number
                else:
                    nextNumber += 1

                # TODO: performance improvement - write to string
                xmlFp = score.write(fmt='musicxml', fp=None, makeNotation=self.makeNotation)
                if xmlFp is None:
                    raise AbcExportError(
                        'Export to temporary MusicXML file failed.'
                    )
                with open(xmlFp, 'r', encoding='utf8') as xmlFpOut:
                    xmlStr = xmlFpOut.read()

                scoreAbcStr: str
                scoreAbcStr, _ = convertMusicXMLToABC(xmlStr)

                if abcStr:
                    abcStr += '\n\n'

                # remove the bad 'X:1' and replace with f'X:{number}'
                if scoreAbcStr[:4] == 'X:1\n':
                    abcStr += f'X:{nextNumber}\n'
                abcStr += scoreAbcStr[4:]

        fp.write(abcStr)
        return True
