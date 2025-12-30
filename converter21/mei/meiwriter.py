# ------------------------------------------------------------------------------
# Name:          meiwriter.py
# Purpose:       MeiWriter is an object that takes a music21 stream and
#                writes it to a file as MEI data.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023-2025 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
import typing as t
from xml.etree.ElementTree import Element, ElementTree, indent

import music21 as m21
# from music21.common import opFrac

from converter21.mei import MeiExportError
# from converter21.mei import MeiInternalError
from converter21.mei import MeiScore
from converter21.mei import MeiShared

from converter21.shared import M21Utilities
from converter21.shared import SharedConstants

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class MeiWriter:
    Debug: bool = False  # can be set to True for more debugging

    def __init__(
        self,
        obj: m21.prebase.ProtoM21Object,
        makeNotation: bool,
        meiVersion: str,
        multipleScoresHostTag: str
    ) -> None:
        M21Utilities.adjustMusic21Behavior()

        self._m21Object: m21.prebase.ProtoM21Object = obj
        self._m21ScoreOrOpus: m21.stream.Score | m21.stream.Opus | None = None

        self.makeNotation = makeNotation

        if meiVersion[0] not in ('4', '5'):
            raise MeiExportError(
                f'invalid meiVersion: {meiVersion}. Must start with "4" or "5".'
            )
        self.meiVersion = meiVersion

        if multipleScoresHostTag not in ('mei', 'mdiv', 'music'):
            raise MeiExportError(
                'multipleScoresHostTag must be "mei", "mdiv", or "music".'
            )
        self.multipleScoresHostTag = multipleScoresHostTag

    def write(self, fp) -> bool:
        # First: We like to modify the input stream (e.g. fixing durations, etc), so we need to
        # make a copy of the input stream before we start.
        if isinstance(self._m21Object, m21.stream.Stream):
            # before deepcopying, fix up any complex hidden rests (so the input score can be
            # visualized).  This should have been done by whoever created the input score,
            # but let's at least fix it up now.
            M21Utilities.fixupComplexHiddenRests(self._m21Object, inPlace=True)
            self._m21Object = self._m21Object.coreCopyAsDerivation('MEIWriter.write')

        # Second: turn the object into a well-formed Score/Opus (someone might have passed in a
        # single note, for example).  This code is swiped from music21 v7's musicxml exporter.
        # The hope is that someday it will become an API in music21 that every exporter can call.
        if self.makeNotation:
            if isinstance(self._m21Object, m21.stream.Opus):
                self._m21ScoreOrOpus = M21Utilities.makeWellFormedOpus(self._m21Object)
            else:
                self._m21ScoreOrOpus = M21Utilities.makeScoreFromObject(self._m21Object)
        else:
            if not isinstance(self._m21Object, (m21.stream.Score, m21.stream.Opus)):
                raise MeiExportError(
                    'Since makeNotation=False, source obj must be a music21'
                    ' Score/Opus, and it is not.'
                )
            if not self._m21Object.isWellFormedNotation():
                print(
                    'Score/Opus is not well-formed; see Stream.isWellFormedNotation()',
                    file=sys.stderr
                )

            self._m21ScoreOrOpus = self._m21Object
        del self._m21Object  # everything after this uses self._m21ScoreOrOpus

        # Third: deal with various duration problems (we see this e.g. after import of a
        # Photoscore-generated MusicXML file)
        M21Utilities.fixupBadDurations(self._m21ScoreOrOpus, inPlace=True)

        # Check that all parts (in all scores) have the same number of measures.
        err: str = M21Utilities.reportUnwritableScore(
            self._m21ScoreOrOpus,
            checkMeasureCounts=True,
            checkMeasureOffsets=False
        )
        if err:
            raise MeiExportError(err)

        scores: list[m21.stream.Score]
        if isinstance(self._m21ScoreOrOpus, m21.stream.Score):
            scores = [self._m21ScoreOrOpus]
        else:
            scores = list(self._m21ScoreOrOpus.scores)

        # pylint: disable=line-too-long
        prefix: str
        if self.meiVersion.startswith('4'):
            prefix = (
                '''<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="https://music-encoding.org/schema/4.0.1/mei-CMN.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>
<?xml-model href="https://music-encoding.org/schema/4.0.1/mei-CMN.rng" type="application/xml" schematypens="http://purl.oclc.org/dsdl/schematron"?>
'''
            )
        elif self.meiVersion.startswith('5'):
            prefix = (
                '''<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="https://music-encoding.org/schema/5.1/mei-CMN.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>
<?xml-model href="https://music-encoding.org/schema/5.1/mei-CMN.rng" type="application/xml" schematypens="http://purl.oclc.org/dsdl/schematron"?>
'''
            )

        # pylint: enable=line-too-long
        fp.write(prefix)

        indentLevel: int = 0
        indentSpace: str = '   '  # 3 spaces

        # where should we write xmlns/meiversion?
        meiVersion: str = self.meiVersion
        multipleScores: bool = len(scores) > 1

        if not multipleScores:
            # single Score hosted in mei element (no matter what self.multipleScoresHostTag says)
            meiScore: MeiScore = MeiScore(scores[0], meiVersion)
            meiElement: Element = meiScore.makeMeiElement()
            fp.write(indentSpace * indentLevel)
            indent(meiElement, space=indentSpace, level=indentLevel)
            ElementTree(meiElement).write(fp, encoding='unicode')
            fp.write('\n')
            # clean up all the notes-to-self MeiScore wrote in the score.
            meiScore.deannotateScore()
            return True

        # Multiple scores!
        if t.TYPE_CHECKING:
            assert isinstance(self._m21ScoreOrOpus, m21.stream.Opus)

        # There are three MEI file possibilities:
        #   (1) multiple 'mei'   (within top-level 'meiCorpus')
        #   (2) multiple 'mdiv'  (within top-level 'mei'/'music')
        #   (3) multiple 'music' (within top-level 'mei'/'music'/'group')
        if self.multipleScoresHostTag == 'mei':
            if meiVersion.startswith('5'):
                fp.write(
                    '<meiCorpus xmlns="http://www.music-encoding.org/ns/mei"'
                    ' meiversion="5.1+CMN">'
                )
            else:
                fp.write(
                    '<meiCorpus xmlns="http://www.music-encoding.org/ns/mei"'
                    ' meiversion="4.0.1">'
                )
            fp.write('\n')

            # Here is where we might put any opus.metadata items in <meiCorpus><meiHead>.
            # Nothing for now, though.

            meiVersion = ''  # disable the xmlns/meiversion attributes in <mei> elements
            indentLevel = 1
            meiScores: list[MeiScore] = [MeiScore(score, meiVersion) for score in scores]
            for meiScore in meiScores:
                meiElement = meiScore.makeMeiElement()
                fp.write(indentSpace * indentLevel)
                indent(meiElement, space=indentSpace, level=indentLevel)
                ElementTree(meiElement).write(fp, encoding='unicode')
                fp.write('\n')

            fp.write('</meiCorpus>\n')
            fp.flush()

            # Don't clean up until score elements completely generated, so
            # memory (and thus xml:ids) don't get re-used in multiple
            # scores in the MEI file.
            for meiScore in meiScores:
                # clean up all the notes-to-self MeiScore wrote in the score.
                meiScore.deannotateScore()
            return True

        # 'music' or 'mdiv'
        # Big difference from 'mei' (that is common to 'music' and 'mdiv') is that
        # we're rooted in 'mei', not 'meiCorpus', and the Opus metadata goes in
        # mei/meiHead proper, and the score metadatas all go in their own 'work'
        # element within mei/meiHead/workList.

        # First we gather all the work-level metadata and the 'score'-level score data.
        # Then we will write the MEI file appropriately using those pieces.
        workElements: list[Element] = []
        scoreElements: list[Element] = []

        useExistingNums: bool = True
        existingNums: list[str | None] = self._m21ScoreOrOpus.getNumbers()
        existingNumInts: list[int] = []
        # to use the existing numbers, there must be no Nones
        for num in existingNums:
            if num is None:
                useExistingNums = False
                break

        # to use the existing numbers there must be no duplicates
        if useExistingNums:
            uniqueNums: list[str | None] = list(set(existingNums))
            if len(uniqueNums) != len(existingNums):
                useExistingNums = False

        # to use the existing numbers, they must all be convertable to int
        if useExistingNums:
            try:
                existingNumInts = [int(num) for num in existingNums]  # type: ignore
            except Exception:
                useExistingNums = False

        nextNumber: int | None = None
        if not useExistingNums:
            nextNumber = 0

        meiScores = [MeiScore(score, meiVersion) for score in scores]
        for scoreIdx, meiScore in enumerate(meiScores):
            if useExistingNums:
                nextNumber = existingNumInts[scoreIdx]
                if t.TYPE_CHECKING:
                    assert nextNumber is not None
            else:
                if t.TYPE_CHECKING:
                    assert nextNumber is not None
                nextNumber += 1

            # Here we convert a music21 Score to an MeiScore. It's still all m21 objects, but
            # the object structure is MEI-like. For example:
            #   music21 scores are {Staff1(Measure1 .. MeasureN), Staff2(Measure1 .. MeasureN)}
            #   but MEI scores are {Measure1{Staff1, Staff2} .. MeasureN{Staff1, Staff2}}.
            scoreEl: Element
            workEl: Element
            scoreEl, workEl = meiScore.makeScoreAndWorkElement(nextNumber)
            dataId: str = M21Utilities.makeXmlIdFrom(id(scoreEl), self.multipleScoresHostTag)
            workEl.attrib['data'] = '#' + dataId

            workElements.append(workEl)
            scoreElements.append(scoreEl)

        # Don't clean up until score elements completely generated, so
        # memory (and thus xml:ids) don't get re-used in multiple
        # scores in the MEI file.
        for meiScore in meiScores:
            # clean up all the notes-to-self MeiScore wrote in the score.
            meiScore.deannotateScore()

        if meiVersion.startswith('5'):
            fp.write(
                '<mei xmlns="http://www.music-encoding.org/ns/mei"'
                ' meiversion="5.1+CMN">'
            )
        else:
            fp.write(
                '<mei xmlns="http://www.music-encoding.org/ns/mei"'
                ' meiversion="4.0.1">'
            )
        fp.write('\n')

        # no Opus metadata for now, just get meiHead ready to receive a work per score.
        fp.write(f'{indentSpace}<meiHead>\n')
        fp.write(f'{indentSpace * 2}<fileDesc>\n')
        fp.write(f'{indentSpace * 3}<titleStmt>\n')
        fp.write(f'{indentSpace * 4}<title></title>\n')
        fp.write(f'{indentSpace * 3}</titleStmt>\n')
        fp.write(f'{indentSpace * 3}<pubStmt></pubStmt>\n')
        fp.write(f'{indentSpace * 2}</fileDesc>\n')
        fp.write(f'{indentSpace * 2}<encodingDesc>\n')
        fp.write(f'{indentSpace * 3}<appInfo>\n')
        fp.write(f'{indentSpace * 4}<application>\n')
        fp.write(f'{indentSpace * 5}<name>{SharedConstants._CONVERTER21_NAME_AND_VERSION}</name>\n')
        fp.write(f'{indentSpace * 4}</application>\n')
        fp.write(f'{indentSpace * 3}</appInfo>\n')
        fp.write(f'{indentSpace * 2}</encodingDesc>\n')
        fp.write(f'{indentSpace * 2}<workList>\n')
        indentLevel = 3
        for workEl in workElements:
            fp.write(indentSpace * indentLevel)
            indent(workEl, space=indentSpace, level=indentLevel)
            ElementTree(workEl).write(fp, encoding='unicode')
            fp.write('\n')
        fp.write(f'{indentSpace * 2}</workList>\n')
        fp.write(f'{indentSpace}</meiHead>\n')
        fp.write(f'{indentSpace}<music>\n')
        if self.multipleScoresHostTag == 'mdiv':
            fp.write(f'{indentSpace * 2}<body>\n')
            # every score will follow: <mdiv><score> ... <mdiv><score ... <mdiv><score> etc
        else:  # 'music'
            fp.write(f'{indentSpace * 2}<group>\n')
            # every score will follow: <music><mdiv><score> ... <music><mdiv><score> etc

        for workEl, scoreEl in zip(workElements, scoreElements):
            nStr: str = workEl.attrib['n']
            dataStr: str = MeiShared.removeOctothorpe(workEl.attrib['data'])
            if self.multipleScoresHostTag == 'mdiv':
                fp.write(f'{indentSpace * 3}<mdiv xml:id="{dataStr}" n="{nStr}">\n')
                indentLevel = 4
            else:  # 'music'
                fp.write(f'{indentSpace * 3}<music xml:id="{dataStr}" n="{nStr}">\n')
                fp.write(f'{indentSpace * 4}<body>\n')
                fp.write(f'{indentSpace * 5}<mdiv>\n')
                indentLevel = 6

            fp.write(indentSpace * indentLevel)
            indent(scoreEl, space=indentSpace, level=indentLevel)
            ElementTree(scoreEl).write(fp, encoding='unicode')
            fp.write('\n')

            if self.multipleScoresHostTag == 'mdiv':
                fp.write(f'{indentSpace * 3}</mdiv>\n')
            else:  # 'music'
                fp.write(f'{indentSpace * 5}</mdiv>\n')
                fp.write(f'{indentSpace * 4}</body>\n')
                fp.write(f'{indentSpace * 3}</music>\n')

        if self.multipleScoresHostTag == 'mdiv':
            fp.write(f'{indentSpace * 2}</body>\n')
        else:  # 'music'
            fp.write(f'{indentSpace * 2}</group>\n')
        fp.write(f'{indentSpace}</music>\n')
        fp.write('</mei>\n')

        fp.flush()

        return True
