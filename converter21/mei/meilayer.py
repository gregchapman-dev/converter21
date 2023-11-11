# ------------------------------------------------------------------------------
# Name:          meilayer.py
# Purpose:       MeiLayer is an object that represents a single music21
#                Voice (i.e. within a Measure). If there are no voices
#                within a given Measure, a single MeiLayer will be created
#                from the Measure itself.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
from xml.etree.ElementTree import TreeBuilder
# import typing as t

import music21 as m21
from music21.common import OffsetQL

# from converter21.mei import MeiExportError
# from converter21.mei import MeiInternalError
from converter21.shared import M21Utilities
from converter21.mei import M21ObjectConvert
from converter21.mei import MeiBeamSpanner
from converter21.mei import MeiTupletSpanner

environLocal = m21.environment.Environment('converter21.mei.meilayer')

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

nextFreeVoiceNumber: int = 0

class MeiLayer:
    Debug: bool = False  # can be set to True for more debugging

    def __init__(
        self,
        m21Voice: m21.stream.Voice | m21.stream.Measure,
        meiParent,  # MeiStaff
        spannerBundle: m21.spanner.SpannerBundle,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature]
    ) -> None:
        from converter21.mei import MeiStaff
        self.m21Voice: m21.stream.Voice | m21.stream.Measure = m21Voice
        self.meiParent: MeiStaff = meiParent
        self.spannerBundle: m21.spanner.SpannerBundle = spannerBundle
        self.scoreMeterStream = scoreMeterStream

    def makeRootElement(self, tb: TreeBuilder):
        # The following voice id fix-up code is patterned after similar code
        # in music21's MusicXML writer.  The idea is to handle three cases
        # (any or all of which may be in play within any given measure):
        #
        # 1. Someone has assigned integer voice.id values with great care (for
        #       cross-staff voices, for example).  Leave them alone, and dance
        #       around them.
        #
        # 2. voice.id values have been left as default (mem address of voice).
        #       We need to fix them up to be reasonable low integers, unique
        #       within the parent MeiStaff (dancing around assigned low integer
        #       voice.id values, as stated above).
        #
        # 3. Someone has assigned string voice.id values with great care for
        #       some other reason, and we should simply use them.
        layerNStr: str = ''
        if isinstance(self.m21Voice, m21.stream.Voice):
            if (isinstance(self.m21Voice.id, int)
                    and self.m21Voice.id < m21.defaults.minIdNumberToConsiderMemoryLocation):
                # Someone assigned this voice id on purpose (tracking voice ids across
                # measures, for instance).  Use it, and set nextFreeVoiceNumber to use
                # the next higher integer (so we will dance around this id).
                layerNStr = str(self.m21Voice.id)
                self.meiParent.nextFreeVoiceNumber = self.m21Voice.id + 1
            elif isinstance(self.m21Voice.id, int):
                # This voice id is actually a memory location, so we need to change it
                # to a low number so it can be used in MEI.  Dance around any previously
                # assigned low int voice ids by using nextFreeVoiceNumber.
                layerNStr = str(self.meiParent.nextFreeVoiceNumber)
                self.meiParent.nextFreeVoiceNumber += 1
            elif isinstance(self.m21Voice.id, str):
                layerNStr = self.m21Voice.id
            else:
                layerNStr = ''

        layerAttr: dict[str, str] = {}
        if layerNStr:
            layerAttr['n'] = layerNStr
        tb.start('layer', {'n': layerNStr})

        voiceBeams: set[m21.spanner.Spanner] = self.getAllBeamsInVoice(self.m21Voice)
        for obj in self.m21Voice:
            if M21ObjectConvert.streamElementBelongsInLayer(obj):
                # Gather a list of beam, tuplet, fTrem spanners that start
                # with this obj.  Sort them by duration (longest first),
                # so they will nest properly as elements.
                beamTupletFTremStarts: list[
                    MeiBeamSpanner | MeiTupletSpanner | m21.expressions.TremoloSpanner
                ] = self.getOrderedBeamTupletFTremStarts(obj, voiceBeams)
                beamTupletFTremEnds: list[
                    MeiBeamSpanner | MeiTupletSpanner | m21.expressions.TremoloSpanner
                ] = self.getOrderedBeamTupletFTremEnds(obj)

                # process any nested element starts
                for btfs in beamTupletFTremStarts:
                    self.processBeamTupletFTremStart(btfs, tb)
                endBTremNeeded: bool = self.processBTremState(obj, tb)

                # emit the object itself
                M21ObjectConvert.convertM21ObjectToMei(obj, tb)

                # process any nested element ends
                if endBTremNeeded:
                    tb.end('bTrem')
                for btfe in beamTupletFTremEnds:
                    self.processBeamTupletFTremEnd(btfe, tb)

        tb.end('layer')

    @staticmethod
    def getAllBeamsInVoice(
        voice: m21.stream.Voice | m21.stream.Measure
    ) -> set[m21.spanner.Spanner]:
        output: set[m21.spanner.Spanner] = set()
        for obj in voice:
            if M21ObjectConvert.streamElementBelongsInLayer(obj):
                beams: list[m21.spanner.Spanner] = obj.getSpannerSites([MeiBeamSpanner])
                output.update(beams)
        return output

    _NUM_MARKS_TO_UNIT_DUR: dict[int, str] = {
        1: '8',
        2: '16',
        3: '32',
        4: '64',
        5: '128',
        6: '256',
        7: '512',
        8: '1024',
        9: '2048'
    }

    _UNIT_DUR_TO_BEAMS: dict[str, str] = {
        '8': '1',
        '16': '2',
        '32': '3',
        '64': '4',
        '128': '5',
        '256': '6',
        '512': '7',
        '1024': '8',
        '2048': '9'
    }

    _QL_NO_DOTS_TO_NUM_FLAGS: dict[float, int] = {
        # not present implies zero beams
        0.5: 1,  # 0.5ql is an eighth note -> one beam
        0.25: 2,
        0.125: 3,
        0.0625: 4,
        0.03125: 5,
        0.015625: 6,
        0.0078125: 7,
        0.00390625: 8,
        0.001953125: 9
    }

    def processBTremState(self, obj: m21.base.Music21Object, tb: TreeBuilder) -> bool:
        # starts a bTrem if necessary before this obj.
        # returns whether or not the current bTrem should be ended after this obj.
        endTheTremolo: bool = False
        if not isinstance(obj, m21.note.GeneralNote):
            return endTheTremolo

        for expr in obj.expressions:
            if isinstance(expr, m21.expressions.Tremolo):
                durQLNoDots: float = m21.duration.typeToDuration.get(obj.duration.type, 0.0)
                numNoteBeams: int = self._QL_NO_DOTS_TO_NUM_FLAGS.get(durQLNoDots, 0)
                totalNumBeams: int = expr.numberOfMarks + numNoteBeams
                unitDur: str = self._NUM_MARKS_TO_UNIT_DUR.get(totalNumBeams, '')
                if not unitDur:
                    environLocal.warn(f'invalid totalNumBeams ({totalNumBeams}), skipping bTrem.')
                    break

                # start a <bTrem>
                attr: dict[str, str] = {}
                attr['unitdur'] = unitDur
                tb.start('bTrem', attr)

                # <bTrem> contains only one note/chord, so end it now.
                endTheTremolo = True
                break

        return endTheTremolo

    def processBeamTupletFTremStart(
        self,
        btfs: MeiBeamSpanner | MeiTupletSpanner | m21.expressions.TremoloSpanner,
        tb: TreeBuilder
    ):
        attr: dict[str, str] = {}
        if isinstance(btfs, MeiBeamSpanner):
            # start a <beam>
            tb.start('beam', attr)
        elif isinstance(btfs, MeiTupletSpanner):
            # start a <tuplet>
            M21ObjectConvert.fillInTupletAttributes(btfs.startTuplet, attr)
            tb.start('tuplet', attr)
        elif isinstance(btfs, m21.expressions.TremoloSpanner):
            durQLNoDots: float = m21.duration.typeToDuration.get(
                btfs.getFirst().duration.type, 0.0
            )
            numNoteBeams: int = self._QL_NO_DOTS_TO_NUM_FLAGS.get(durQLNoDots, 0)
            totalNumBeams: int = btfs.numberOfMarks + numNoteBeams
            unitDur: str = self._NUM_MARKS_TO_UNIT_DUR.get(totalNumBeams, '')
            if not unitDur:
                environLocal.warn(
                    f'invalid totalNumBeams ({totalNumBeams}), skipping fTrem.'
                )
                btfs.mei_skip = True  # type: ignore
                return
            beams: str = self._UNIT_DUR_TO_BEAMS.get(unitDur, '')
            if not beams:
                environLocal.warn(
                    f'invalid unitDur ({unitDur}), skipping fTrem.'
                )
                btfs.mei_skip = True  # type: ignore
                return

            # start an <fTrem>
            attr['beams'] = beams
            attr['unitdur'] = unitDur
            tb.start('fTrem', attr)

    def processBeamTupletFTremEnd(
        self,
        btfe: MeiBeamSpanner | MeiTupletSpanner | m21.expressions.TremoloSpanner,
        tb: TreeBuilder
    ):
        if hasattr(btfe, 'mei_skip'):
            return

        if isinstance(btfe, MeiBeamSpanner):
            tb.end('beam')
        elif isinstance(btfe, MeiTupletSpanner):
            tb.end('tuplet')
        elif isinstance(btfe, m21.expressions.TremoloSpanner):
            tb.end('fTrem')

    def getOrderedBeamTupletFTremStarts(
        self,
        obj: m21.base.Music21Object,
        voiceBeams: set[m21.spanner.Spanner]
    ) -> list[MeiBeamSpanner | MeiTupletSpanner | m21.expressions.TremoloSpanner]:

        def spannerQL(spanner: m21.spanner.Spanner) -> OffsetQL:
            return M21Utilities.getSpannerQuarterLength(spanner, self.meiParent.m21Measure)

        def nestsReasonably(
            tuplet: m21.spanner.Spanner,
            voiceBeams: set[m21.spanner.Spanner]
        ) -> bool:
            # check each beam spanner in voiceBeams.
            tupletSet: set[m21.note.GeneralNote] = set(tuplet.getSpannedElements())
            for beam in voiceBeams:
                beamSet: set[m21.note.GeneralNote] = set(beam.getSpannedElements())
                if tupletSet.isdisjoint(beamSet):
                    # tuplet is unrelated to this beam, move onto the next beam.
                    continue

                # tuplet overlaps with beam at least a little.
                if tupletSet.issubset(beamSet):
                    # tuplet contains a subset (or all) of beam's notes, and no other notes.
                    # beam is nested inside tuplet: we're OK with this beam, move onto the
                    # next beam.
                    continue

                # tuplet overlaps with beam, but also contains other notes.
                if not beamSet.issubset(tupletSet):
                    # tuplet overlaps partially with beam, plus other notes.  This CANNOT work.
                    # beam cannot nest inside tuplet, and tuplet cannot nest inside beam.
                    return False

                # tuplet contains all notes in beam plus other notes. This can only work if
                # the other notes are either _entire_ beams' worth of notes, or non-beamed
                # notes.
                for beam1 in voiceBeams:
                    if beam1 is beam:
                        continue
                    beam1Set: set[m21.note.GeneralNote] = set(beam1.getSpannedElements())
                    if beam1Set.isdisjoint(tupletSet):
                        # no worries with this beam
                        continue
                    if not beam1Set.issubset(tupletSet):
                        # beam1 is partially contained by tuplet.  Big problem.
                        return False

            return True

        output: list[MeiBeamSpanner | MeiTupletSpanner | m21.expressions.TremoloSpanner] = []
        for spanner in obj.getSpannerSites([
            MeiBeamSpanner,
            MeiTupletSpanner,
            m21.expressions.TremoloSpanner
        ]):
            # we're only interested in starts
            if not spanner.isFirst(obj):
                continue

            # Beam and tuplet are special, they can span across measure boundaries.
            # If they do span across a measure boundary, skip them here, we'll
            # emit a <beamSpan> or <tupletSpan> instead, later.
            if isinstance(spanner, (MeiBeamSpanner, MeiTupletSpanner)):
                if not M21Utilities.allSpannedElementsAreInHierarchy(
                    spanner, self.meiParent.m21Measure
                ):
                    M21ObjectConvert.assureXmlIds(spanner)
                    continue

                # Tuplet is even more special.  It can interleave with beams in a way
                # that cannot be nested.  If so, we can't emit <tuplet>, since it can't
                # be properly nested with the <beam>s in the voice/layer, so we have to
                # skip the tuplet here, and emit later as <tupletSpan>.
                if isinstance(spanner, MeiTupletSpanner):
                    if not nestsReasonably(spanner, voiceBeams):
                        M21ObjectConvert.assureXmlIds(spanner)
                        continue

                # mark as having been emitted as <beam> or <tuplet> so we don't emit
                # as <beamSpan> or <tupletSpan> later, in makePostStavesElements.
                if isinstance(spanner, MeiBeamSpanner):
                    spanner.mei_beam = True  # type: ignore
                else:
                    spanner.mei_tuplet = True  # type: ignore

            elif isinstance(spanner, m21.expressions.TremoloSpanner):
                if len(spanner) != 2:
                    environLocal.warn('len(TremoloSpanner) != 2, skipping fTrem.')
                    continue

                obj.mei_in_ftrem = True  # type: ignore

            output.append(spanner)  # type: ignore

        output.sort(reverse=True, key=spannerQL)
        return output

    def getOrderedBeamTupletFTremEnds(
        self,
        obj: m21.base.Music21Object,
    ) -> list[MeiBeamSpanner | MeiTupletSpanner | m21.expressions.TremoloSpanner]:

        def spannerQL(spanner: m21.spanner.Spanner) -> OffsetQL:
            return M21Utilities.getSpannerQuarterLength(spanner, self.meiParent.m21Measure)

        output: list[MeiBeamSpanner | MeiTupletSpanner | m21.expressions.TremoloSpanner] = []
        for spanner in obj.getSpannerSites([
            MeiBeamSpanner,
            MeiTupletSpanner,
            m21.expressions.TremoloSpanner
        ]):
            # we're only interested in starts
            if not spanner.isLast(obj):
                continue

            if isinstance(spanner, MeiBeamSpanner) and not hasattr(spanner, 'mei_beam'):
                # Skip if we're emitting as <beamSpan>
                continue

            if isinstance(spanner, MeiTupletSpanner) and not hasattr(spanner, 'mei_tuplet'):
                # Skip if we're emitting as <tupletSpan>
                continue

            if isinstance(spanner, m21.expressions.TremoloSpanner):
                if len(spanner) != 2:
                    environLocal.warn('len(TremoloSpanner) != 2, skipping fTrem.')
                    continue

                obj.mei_in_ftrem = True  # type: ignore

            output.append(spanner)  # type: ignore

        output.sort(key=spannerQL)  # type: ignore
        return output

    def makePostStavesElements(self, tb: TreeBuilder):
        m21Part: m21.stream.Part = self.meiParent.m21Part
        m21Measure: m21.stream.Measure = self.meiParent.m21Measure
        staffNStr: str = self.meiParent.staffNStr
        for obj in self.m21Voice:
            # Lots of stuff from a MeiLayer goes in the post-staves elements:
            # 1. Some elements in this voice (e.g. Dynamic, TextExpression, TempoIndication)
            if M21ObjectConvert.streamElementBelongsInPostStaves(obj):
                M21ObjectConvert.convertPostStaveStreamElement(
                    obj,
                    staffNStr,
                    m21Part,
                    m21Measure,
                    self.scoreMeterStream,
                    tb
                )

            # 2. Spanners (Slurs, DynamicWedges, TrillExtensions, etc) whose first
            # element is in this voice. Includes <beamSpan>, <tupletSpan>, <tie>
            for spanner in obj.getSpannerSites():
                if spanner.isFirst(obj):
                    # print(f'spanner seen: {spanner.classes[0]}', file=sys.stderr)
                    M21ObjectConvert.postStavesSpannerToMei(
                        spanner,
                        staffNStr,
                        m21Part,
                        m21Measure,
                        self.scoreMeterStream,
                        tb
                    )
            if isinstance(obj, m21.chord.Chord):
                # check every note in the chord
                for note in obj.notes:
                    for spanner in note.getSpannerSites():  # type: ignore
                        if spanner.isFirst(note):
                            M21ObjectConvert.postStavesSpannerToMei(
                                spanner,
                                staffNStr,
                                m21Part,
                                m21Measure,
                                self.scoreMeterStream,
                                tb
                            )

            # 3. Turns/Trills/Mordents/Fermatas/ArpeggioMarks on notes/chords in this voice.
            #       We count on any TrillExtension being handled before
            #       now, in the spanner loop above. If that changes, all
            #       'mei_trill_already_handled' processing will need to
            #       change, too.
            if isinstance(obj, m21.note.GeneralNote):
                for expr in obj.expressions:  # type: ignore
                    if isinstance(expr, m21.expressions.Trill):
                        if (hasattr(expr, 'mei_trill_already_handled')):
                            continue

                        M21ObjectConvert.trillToMei(
                            obj,
                            expr,
                            staffNStr,
                            m21Part,
                            m21Measure,
                            self.scoreMeterStream,
                            tb
                        )
                        continue

                    if isinstance(expr, m21.expressions.Turn):
                        M21ObjectConvert.turnToMei(
                            obj,
                            expr,
                            staffNStr,
                            m21Part,
                            m21Measure,
                            self.scoreMeterStream,
                            tb
                        )
                        continue

                    if isinstance(expr, m21.expressions.GeneralMordent):
                        M21ObjectConvert.mordentToMei(
                            obj,
                            expr,
                            staffNStr,
                            m21Part,
                            m21Measure,
                            self.scoreMeterStream,
                            tb
                        )
                        continue

                    if isinstance(expr, m21.expressions.Fermata):
                        M21ObjectConvert.fermataToMei(
                            obj,
                            expr,
                            staffNStr,
                            m21Part,
                            m21Measure,
                            self.scoreMeterStream,
                            tb
                        )
                        continue

                    if isinstance(expr, m21.expressions.ArpeggioMark):
                        M21ObjectConvert.arpeggioMarkToMei(
                            obj,
                            expr,
                            staffNStr,
                            m21Part,
                            m21Measure,
                            self.scoreMeterStream,
                            tb
                        )
                        continue
