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
from copy import deepcopy
import typing as t

import music21 as m21
from music21.common import opFrac
from music21.common import OffsetQL

from converter21.mei import MeiExportError
from converter21.mei import MeiInternalError
from converter21.mei import MeiMeasure
from converter21.mei import M21ObjectConvert
from converter21.mei import MeiTemporarySpanner
from converter21.mei import MeiBeamSpanner
from converter21.mei import MeiTupletSpanner
from converter21.mei import MeiTieSpanner
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

        self.previousBeamedNoteOrChord: m21.note.NotRest | None = None
        self.currentBeamSpanner: MeiBeamSpanner | None = None
        self.currentTupletSpanners: list[MeiTupletSpanner] = []
        self.currentTieSpanners: dict[m21.stream.Part, list[tuple[MeiTieSpanner, int]]] = {}
        for part in self.m21Score.parts:
            self.currentTieSpanners[part] = []

        # pre-scan of m21Score to set up some things
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
            'meiversion': '4.0.0'
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
        for part in self.m21Score.parts:
            partTieSpanners: list[tuple[MeiTieSpanner, int]] = self.currentTieSpanners[part]
            for measure in part:
                if not isinstance(measure, m21.stream.Measure):
                    continue

                # check/increment numMeasuresSearched in all part tie spanners
                defunctTieSpanners: list[tuple[MeiTieSpanner, int]] = []
                for i, (sp, numMeasuresSearched) in enumerate(partTieSpanners):
                    if numMeasuresSearched >= 2:
                        defunctTieSpanners.append((sp, numMeasuresSearched))
                    else:
                        partTieSpanners[i] = (sp, numMeasuresSearched + 1)
                for sp, numMeasuresSearched in defunctTieSpanners:
                    partTieSpanners.remove((sp, numMeasuresSearched))

                voices: list[m21.stream.Voice | m21.stream.Measure] = (
                    list(measure[m21.stream.Voice])
                )
                if not voices:
                    voices = [measure]
                for voice in voices:
                    for obj in voice:
                        self.annotateBeams(obj)
                        self.annotateTuplets(obj)
                        self.annotateTies(obj, part)

                # once annotated, check to see if any of these objects
                # need xml:id.
                self.makeXmlIds(measure)

        # print('done annotating score')

    def deannotateScore(self) -> None:
        for sp in self.m21Score.getElementsByClass(MeiTemporarySpanner):
            if isinstance(sp, MeiBeamSpanner):
                for el in sp.getSpannedElements():
                    if hasattr(el, 'mei_breaksec'):
                        delattr(el, 'mei_breaksec')
            self.m21Score.remove(sp)

        for obj in self.m21Score[m21.note.GeneralNote]:
            if hasattr(obj, 'mei_xml_id'):
                delattr(obj, 'mei_xml_id')

    def makeXmlIds(self, measure: m21.stream.Measure):
        for obj in measure.recurse().getElementsByClass(m21.note.GeneralNote):
            if isinstance(obj, m21.chord.Chord):
                # MeiTieSpanner might contain notes that are inside chords (this
                # is not actually valid for real spanners, but it's ok for us).
                # Handle this as a special case.
                for note in obj.notes:
                    for spanner in note.getSpannerSites():
                        if isinstance(spanner, MeiTieSpanner):
                            M21ObjectConvert.assureXmlId(spanner.getFirst())
                            if spanner.getLast() is not spanner.getFirst():
                                M21ObjectConvert.assureXmlId(spanner.getLast())

            # check expressions for turn/trill/mordent; if any present, obj needs xmlId
            for expr in obj.expressions:
                if isinstance(expr, (
                    m21.expressions.Turn,
                    m21.expressions.Trill,
                    m21.expressions.GeneralMordent,
                    m21.expressions.Fermata
                )):
                    M21ObjectConvert.assureXmlId(obj)
                    break  # skip the rest of the expressions

            # check for spanners (all spanners for now, might get too many xmlIds?)
            for spanner in obj.getSpannerSites():
                if isinstance(spanner, (MeiBeamSpanner, MeiTupletSpanner)):
                    # Beam spanners and tuplet spanners only need xmlIds if they
                    # span multiple measures.  Note that we won't know this until
                    # we encounter a later object in such a spanner, so when we
                    # do, we reach back and assure xmlIds for everything in the
                    # spanner.  Note that assureXmlId returns immediately if
                    # the xml id is already in place.
                    if not M21Utilities.allSpannedElementsAreInHierarchy(spanner, measure):
                        for el in spanner.getSpannedElements():
                            M21ObjectConvert.assureXmlId(el)
                    continue  # to next spanner

                if isinstance(spanner, MeiTieSpanner):
                    M21ObjectConvert.assureXmlId(spanner.getFirst())
                    if spanner.getLast() is not spanner.getFirst():
                        M21ObjectConvert.assureXmlId(spanner.getLast())
                    continue  # to next spanner

                # Some spanners need xmlIds for all their elements:
                if isinstance(spanner, m21.expressions.ArpeggioMarkSpanner):
                    M21ObjectConvert.assureXmlId(obj)

                # All other spanners need xmlIds only for start and end elements
                if spanner.isFirst(obj) or spanner.isLast(obj):
                    M21ObjectConvert.assureXmlId(obj)

    def annotateBeams(self, noteOrChord: m21.base.Music21Object) -> None:
        if not isinstance(noteOrChord, m21.note.NotRest):
            return

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
            if len(beams.beamsList) == 0:
                return False
            for beamObj in beams:
                if not stopsBeam(beamObj):
                    return False
            return True

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

        if not noteOrChord.beams.beamsList:
            self.previousBeamedNoteOrChord = None
            return

        if self.currentBeamSpanner is None:
            self.currentBeamSpanner = MeiBeamSpanner()
            self.m21Score.append(self.currentBeamSpanner)

        self.currentBeamSpanner.addSpannedElements(noteOrChord)

        if allStop(noteOrChord.beams):
            # done with this <beam> or <beamSpan>.  Put the spanner in the score,
            # and clear out any state variables.
            self.currentBeamSpanner = None
            self.previousBeamedNoteOrChord = None
            return

        # annotate any breaksec ending at this noteOrChord (set it on the previous noteOrChord)
        if self.previousBeamedNoteOrChord is not None:
            breakSec: int = computeBreakSec(self.previousBeamedNoteOrChord.beams, noteOrChord.beams)
            if breakSec > 0:
                self.previousBeamedNoteOrChord.mei_breaksec = breakSec  # type: ignore

        self.previousBeamedNoteOrChord = noteOrChord

    def annotateTuplets(self, gnote: m21.base.Music21Object) -> None:
        if not isinstance(gnote, m21.note.GeneralNote):
            return

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

        starts: int = numStarts(gnote.duration.tuplets)
        if len(gnote.duration.tuplets) - starts != len(self.currentTupletSpanners):
            raise MeiExportError('malformed music21 nested tuplets')
            # I guess we could try to figure it out

        # start any new tuplet spanners
        for tuplet in gnote.duration.tuplets:
            if startsTuplet(tuplet):
                newTupletSpanner = MeiTupletSpanner(tuplet)
                self.m21Score.append(newTupletSpanner)
                self.currentTupletSpanners.append(newTupletSpanner)

        # put this note in all the tuplet spanners
        for spanner in self.currentTupletSpanners:
            spanner.addSpannedElements(gnote)

        # stop any old tuplet spanners
        for tuplet in gnote.duration.tuplets:
            if stopsTuplet(tuplet):
                self.currentTupletSpanners = self.currentTupletSpanners[:-1]

    def annotateTies(
        self,
        noteOrChord: m21.base.Music21Object,
        part: m21.stream.Part
    ) -> None:
        if not isinstance(noteOrChord, (m21.note.Note, m21.chord.Chord)):
            # Note that we reject Unpitched and PercussionChord here, since
            # they have no pitches.
            return

        def startsTie(noteOrChord: m21.note.Note | m21.chord.Chord) -> bool:
            if noteOrChord.tie is None:
                return False
            if noteOrChord.tie.type in ('start', 'continue'):
                return True
            return False

        def stopsTieInWhichSpanner(
            note: m21.note.Note,
            part: m21.stream.Part,
            partTieSpanners: list[tuple[MeiTieSpanner, int]],
            parentChord: m21.chord.Chord | None = None
        ) -> tuple[MeiTieSpanner, int] | None:
            # look at all the partTieSpanners and see if this note has the
            # same (exact) pitches as the start note of that spanner.
            for sp, numMeasuresSearched in partTieSpanners:
                startNote: m21.note.Note = sp.getFirst()
                if note is startNote:
                    continue

                if startNote.pitch != note.pitch:
                    continue

                # to stop a tie, you have to start at or beyond the end of the tie's start note.
                startParentChord: m21.chord.Chord | None = sp.startParentChord
                minPartOffset: OffsetQL
                actualPartOffset: OffsetQL
                if startParentChord is not None:
                    minPartOffset = opFrac(
                        startParentChord.getOffsetInHierarchy(part)
                        + startParentChord.quarterLength
                    )
                else:
                    minPartOffset = opFrac(
                        startNote.getOffsetInHierarchy(part)
                        + startNote.quarterLength
                    )

                if parentChord is not None:
                    actualPartOffset = parentChord.getOffsetInHierarchy(part)
                else:
                    actualPartOffset = note.getOffsetInHierarchy(part)

                if (actualPartOffset < minPartOffset):
                    continue

                # we found a spanner whose startNote has the same pitches as
                # note, so return that spanner.  note stops the tie
                # represented by that spanner.
                return (sp, numMeasuresSearched)

            return None

        partTieSpanners: list[tuple[MeiTieSpanner, int]] = self.currentTieSpanners[part]

        if startsTie(noteOrChord):
            if t.TYPE_CHECKING:
                assert noteOrChord.tie is not None
            if isinstance(noteOrChord, m21.chord.Chord):
                # Pretend there was a tie on every note.
                for note in noteOrChord.notes:
                    noteTie: m21.tie.Tie = deepcopy(noteOrChord.tie)
                    newTieSpanner = MeiTieSpanner(noteTie, startParentChord=noteOrChord)
                    newTieSpanner.addSpannedElements(note)
                    self.m21Score.append(newTieSpanner)
                    partTieSpanners.append((newTieSpanner, 1))
            else:
                newTieSpanner = MeiTieSpanner(noteOrChord.tie, startParentChord=None)
                newTieSpanner.addSpannedElements(noteOrChord)
                self.m21Score.append(newTieSpanner)
                partTieSpanners.append((newTieSpanner, 1))
        elif isinstance(noteOrChord, m21.chord.Chord):
            # The chord itself does not start a tie; perhaps one or more of the chord's
            # individual notes does.
            for note in noteOrChord.notes:
                if startsTie(note):
                    if t.TYPE_CHECKING:
                        assert note.tie is not None
                    newTieSpanner = MeiTieSpanner(note.tie, startParentChord=noteOrChord)
                    newTieSpanner.addSpannedElements(note)
                    self.m21Score.append(newTieSpanner)
                    partTieSpanners.append((newTieSpanner, 1))

        spN: tuple[MeiTieSpanner, int] | None = None
        if isinstance(noteOrChord, m21.chord.Chord):
            # The chord itself does not stop a tie (MeiTieSpanners always span notes);
            # perhaps one or more of the chord's individual notes does.
            for note in noteOrChord.notes:
                spN = stopsTieInWhichSpanner(note, part, partTieSpanners, noteOrChord)
                if spN is not None:
                    spN[0].addSpannedElements(note)
                    partTieSpanners.remove(spN)
        elif isinstance(noteOrChord, m21.note.Note):
            spN = stopsTieInWhichSpanner(noteOrChord, part, partTieSpanners)
            if spN is not None:
                spN[0].addSpannedElements(noteOrChord)
                partTieSpanners.remove(spN)
        else:
            raise MeiInternalError('noteOrChord is not Note or Chord')
