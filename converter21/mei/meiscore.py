# ------------------------------------------------------------------------------
# Name:          meiscore.py
# Purpose:       MeiScore is an object that takes a music21 Score and
#                organizes its objects in an MEI-like structure.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
from xml.etree.ElementTree import Element, TreeBuilder
# import typing as t

import music21 as m21
# from music21.common import opFrac

from converter21.mei import MeiExportError
# from converter21.mei import MeiInternalError
from converter21.mei import MeiMeasure
from converter21.mei import M21ObjectConvert
from converter21.mei import MeiBeamSpanner
from converter21.mei import MeiTupletSpanner
from converter21.shared import M21Utilities
from converter21.shared import M21StaffGroupTree

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class MeiScore:
    Debug: bool = False  # can be set to True for more debugging

    def __init__(self, m21Score: m21.stream.Score) -> None:
        self.m21Score: m21.stream.Score = m21Score

        # Scan the m21Score, and put in some annotations for our own use (making things that
        # look MEI-ish to represent music21 things that are very not MEI-ish; for example,
        # translate all noteOrChord.beams into our own MeiBeamSpanner objects and some sort
        # of noteOrChord.mei_breaksec attribute).  These annotations will disappear as we
        # finish exporting from each one in makeRootElement().
        self.previousBeamedNoteOrChord: m21.note.NotRest | None = None
        self.currentBeamSpanner: MeiBeamSpanner | None = None
        self.currentTupletSpanners: list[MeiTupletSpanner] = []
        self.annotateScore()

        self.spannerBundle: m21.spanner.SpannerBundle = self.m21Score.spannerBundle
        self.scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature] = (
            self.m21Score.getTimeSignatures(
                returnDefault=True,
                searchContext=False,
                sortByCreationTime=False
            )
        )

        self.staffNumbersForM21Parts: dict[m21.stream.Part, int] = (
            self._getStaffNumbersForM21Parts()
        )
        self.staffGroupTrees: list[M21StaffGroupTree] = (
            M21Utilities.getStaffGroupTrees(
                list(m21Score[m21.layout.StaffGroup]),
                self.staffNumbersForM21Parts
            )
        )

        self.measures: list[MeiMeasure] = self._getMeiMeasures()

    def _getStaffNumbersForM21Parts(self) -> dict[m21.stream.Part, int]:
        output: dict[m21.stream.Part, int] = {}
        for staffIdx, part in enumerate(self.m21Score.parts):
            output[part] = staffIdx + 1  # staff numbers are 1-based
        return output

    def _getMeiMeasures(self) -> list[MeiMeasure]:
        output: list[MeiMeasure] = []

        # OffsetIterator is not recursive, so we have to recursively pull all the measures
        # into one single stream, before we can use OffsetIterator to generate the "stacks"
        # of Measures that all occur at the same offset (moment) in the score.
        measuresStream: m21.stream.Stream[m21.stream.Measure] = (
            self.m21Score.recurse().getElementsByClass(m21.stream.Measure).stream()
        )
        offsetIterator: m21.stream.iterator.OffsetIterator[m21.stream.Measure] = (
            m21.stream.iterator.OffsetIterator(measuresStream)
        )
        meiMeas: MeiMeasure | None = None
        for measureStack in offsetIterator:
            prevMeiMeasure: MeiMeasure | None = meiMeas
            meiMeas = MeiMeasure(
                measureStack,
                prevMeiMeasure,
                self.staffNumbersForM21Parts,
                self.spannerBundle,
                self.scoreMeterStream)
            output.append(meiMeas)

        return output

    def makeRootElement(self) -> Element:
        tb: TreeBuilder = TreeBuilder(insert_comments=True, insert_pis=True)
        tb.start('mei', {
            'xmlns': 'http://www.music-encoding.org/ns/mei',
            'meiversion': '4.0.1'
        })

        self.makeMeiHead(tb)

        tb.start('music', {})
        tb.start('body', {})
        tb.start('mdiv', {})

        tb.start('score', {})
        self.makeScoreDefElement(tb)
        tb.start('section', {})
        for meim in self.measures:
            meim.makeRootElement(tb)
        tb.end('section')
        tb.end('score')

        tb.end('mdiv')
        tb.end('body')
        tb.end('music')

        tb.end('mei')
        root: Element = tb.close()
        return root

    def makeMeiHead(self, tb: TreeBuilder) -> None:
        # Here lies metadata, in <fileDesc>, <encodingDesc>, <workList>, etc
        tb.start('meiHead', {})
        tb.start('fileDesc', {})
        tb.end('fileDesc')
        tb.start('encodingDesc', {})
        tb.end('encodingDesc')
        tb.start('workList', {})
        tb.end('workList')
        tb.end('meiHead')

    def makeScoreDefElement(self, tb: TreeBuilder) -> None:
        tb.start('scoreDef', {})
        tb.start('staffGrp', {})
        for part, staffN in self.staffNumbersForM21Parts.items():
            # staffLines (defaults to 5)
            staffLines: int = 5
            initialStaffLayout: m21.layout.StaffLayout | None = None
            initialStaffLayouts = list(
                part.recurse().getElementsByClass(m21.layout.StaffLayout).getElementsByOffset(0.0)
            )
            if initialStaffLayouts:
                initialStaffLayout = initialStaffLayouts[0]
            if initialStaffLayout and initialStaffLayout.staffLines is not None:
                staffLines = initialStaffLayout.staffLines

            tb.start('staffDef', {
                'n': str(staffN),
                'lines': str(staffLines)
            })

            # clef
            clef: m21.clef.Clef | None = part.clef
            if clef is None:
                clefs: list[m21.clef.Clef] = list(
                    part.recurse().getElementsByClass(m21.clef.Clef).getElementsByOffset(0.0)
                )
                if clefs:
                    clef = clefs[0]
            if clef is not None:
                M21ObjectConvert.m21ClefToMei(clef, tb)


            # key signature
            keySig: m21.key.KeySignature | None = part.keySignature
            if keySig is None:
                keySigs: list[m21.key.KeySignature] = list(
                    part.recurse()
                    .getElementsByClass(m21.key.KeySignature)
                    .getElementsByOffset(0.0)
                )
                if keySigs:
                    keySig = keySigs[0]
            if keySig is not None:
                M21ObjectConvert.m21KeySigToMei(keySig, tb)

            # time signature
            meterSig: m21.meter.TimeSignature | None = part.timeSignature
            if meterSig is None:
                meterSigs: list[m21.meter.TimeSignature] = list(
                    part.recurse()
                    .getElementsByClass(m21.meter.TimeSignature)
                    .getElementsByOffset(0.0)
                )
                if meterSigs:
                    meterSig = meterSigs[0]
            if meterSig is not None:
                M21ObjectConvert.m21TimeSigToMei(meterSig, tb)

            tb.end('staffDef')
        tb.end('staffGrp')
        tb.end('scoreDef')

    def annotateScore(self) -> None:
        for part in self.m21Score[m21.stream.Part]:
            for measure in part[m21.stream.Measure]:
                voices: list[m21.stream.Voice | m21.stream.Measure] = (
                    list(measure[m21.stream.Voice])
                )
                if not voices:
                    voices = [measure]
                for voice in voices:
                    for obj in voice:
                        self.annotateBeams(obj)
                        self.annotateTuplets(obj)

    def annotateBeams(self, noteOrChord: m21.base.Music21Object) -> None:
        def stopsBeam(beam: m21.beam.Beam) -> bool:
            if beam.type == 'stop':
                return True
            if beam.type == 'partial' and beam.direction == 'left':
                return True
            return False

        def startsBeam(beam: m21.beam.Beam) -> bool:
            if beam.type == 'start':
                return True
            if beam.type == 'partial' and beam.direction == 'right':
                return True
            return False

        def allStop(beams: m21.beam.Beams) -> bool:
            for beamObj in beams:
                if stopsBeam(beamObj):
                    return True
            return False

        def computeBreakSec(prevBeams: m21.beam.Beams, currBeams: m21.beam.Beams) -> int:
            # returns the number of beams that should be seen during the break
            # returns 0 if no breaksec seen
            numBeams: int = len(currBeams)
            if len(prevBeams) != numBeams:
                return 0

            numStartStops: int = 0
            for prevBeam, currBeam in zip(prevBeams, currBeams):
                if stopsBeam(prevBeam) and startsBeam(currBeam):
                    numStartStops += 1

            if numStartStops == 0:
                return 0

            return numBeams - numStartStops

        if not isinstance(noteOrChord, m21.note.NotRest):
            return

        if not noteOrChord.beams.beamsList:
            self.previousBeamedNoteOrChord = None
            return

        if self.currentBeamSpanner is None:
            self.currentBeamSpanner = MeiBeamSpanner()

        self.currentBeamSpanner.addSpannedElements(noteOrChord)

        if allStop(noteOrChord.beams):
            # done with this <beam> or <beamSpan>.  Put the spanner in the score,
            # and clear out any state variables.
            self.m21Score.append(self.currentBeamSpanner)
            self.currentBeamSpanner = None
            self.previousBeamedNoteOrChord = None
            return

        # annotate any breaksec ending at this noteOrChord (set it on the previous noteOrChord)
        if self.previousBeamedNoteOrChord is not None:
            breakSec: int = computeBreakSec(self.previousBeamedNoteOrChord.beams, noteOrChord.beams)
            if breakSec > 0:
                self.previousBeamedNoteOrChord.mei_breaksec = breakSec  # type: ignore

        self.previousBeamedNoteOrChord = noteOrChord

    def annotateTuplets(self, noteOrChord: m21.base.Music21Object) -> None:
        def stopsTuplet(tuplet: m21.duration.Tuplet) -> bool:
            if tuplet.type in ('stop', 'startStop'):
                return True
            return False

        def startsTuplet(tuplet: m21.duration.Tuplet) -> bool:
            if tuplet.type in ('start', 'startStop'):
                return True
            return False

        def numStarts(tuplets: tuple[m21.duration.Tuplet, ...]) -> int:
            output: int = 0
            for tupletObj in tuplets:
                if startsTuplet(tupletObj):
                    output += 1
            return output

        if not isinstance(noteOrChord, m21.note.GeneralNote):
            return

        starts: int = numStarts(noteOrChord.duration.tuplets)
        if len(noteOrChord.duration.tuplets) - starts != len(self.currentTupletSpanners):
            raise MeiExportError('malformed music21 nested tuplets')
            # I guess we could try to figure it out

        # start any new tuplet spanners
        for tuplet in noteOrChord.duration.tuplets:
            if startsTuplet(tuplet):
                newTupletSpanner = MeiTupletSpanner(tuplet)
                self.currentTupletSpanners.append(newTupletSpanner)

        # put this note in all the tuplet spanners
        for spanner in self.currentTupletSpanners:
            spanner.addSpannedElements(noteOrChord)

        # stop any old tuplet spanners
        for tuplet in noteOrChord.duration.tuplets:
            if stopsTuplet(tuplet):
                self.m21Score.append(self.currentTupletSpanners[-1])
                self.currentTupletSpanners = self.currentTupletSpanners[:-1]
