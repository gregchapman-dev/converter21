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
# from music21.common import OffsetQL, OffsetQLIn, opFrac

# from converter21.mei import MeiExportError
# from converter21.mei import MeiInternalError
from converter21.shared import M21Utilities
from converter21.mei import M21ObjectConvert
from converter21.mei import MeiBeamSpanner
from converter21.mei import MeiTupletSpanner

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

        for obj in self.m21Voice:
            if M21ObjectConvert.streamElementBelongsInLayer(obj):
                # check for beam, tuplet
                endBeamNeeded: bool = self.processBeamState(obj, tb)
                endTupletNeeded: bool = self.processTupletState(obj, tb)

                M21ObjectConvert.convertM21ObjectToMei(obj, tb)

                if endTupletNeeded:
                    tb.end('tuplet')
                if endBeamNeeded:
                    tb.end('beam')

        tb.end('layer')

    def processBeamState(self, obj: m21.base.Music21Object, tb: TreeBuilder) -> bool:
        # starts a beam if necessary before this obj.
        # returns whether or not the current beam should be ended after this obj.
        endTheBeam: bool = False
        for spanner in self.spannerBundle.getBySpannedElement(obj):
            if isinstance(spanner, MeiBeamSpanner):
                if spanner.isFirst(obj):
                    # start a <beam>, but only if all the spanned elements are in
                    # this m21Measure.
                    if M21Utilities.allSpannedElementsAreInHierarchy(
                        spanner, self.meiParent.m21Measure
                    ):
                        tb.start('beam', {})
                        # Mark this spanner as having been emitted as <beam>
                        # (so we don't also emit it as <beamSpan> later, in
                        # makePostStavesElements).
                        spanner.mei_beam = True  # type: ignore
                if spanner.isLast(obj):
                    if hasattr(spanner, 'mei_beam'):
                        endTheBeam = True

        return endTheBeam

    def processTupletState(self, obj: m21.base.Music21Object, tb: TreeBuilder) -> bool:
        # starts a tuplet if necessary before this obj.
        # returns whether or not the current tuplet should be ended after this obj.
        endTheTuplet: bool = False
        for spanner in self.spannerBundle.getBySpannedElement(obj):
            if isinstance(spanner, MeiTupletSpanner):
                if spanner.isFirst(obj):
                    # start a <beam>, but only if all the spanned elements are in
                    # this m21Measure.
                    if M21Utilities.allSpannedElementsAreInHierarchy(
                        spanner, self.meiParent.m21Measure
                    ):
                        attr: dict[str, str] = {}
                        M21ObjectConvert.fillInTupletAttributes(spanner.startTuplet, attr)
                        tb.start('tuplet', attr)
                        # Mark this spanner as having been emitted as <tuplet>
                        # (so we don't also emit it as <tupletSpan> later, in
                        # makePostStavesElements).
                        spanner.mei_tuplet = True  # type: ignore
                if spanner.isLast(obj):
                    if hasattr(spanner, 'mei_tuplet'):
                        endTheTuplet = True

        return endTheTuplet

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
            # element is in this voice.
            for spanner in self.spannerBundle.getBySpannedElement(obj):
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

            # 3. Turns/Trills/Mordents on notes/chords in this voice.
            #       We count on any TrillExtension being handled before
            #       now, in the spanner loop above. If that changes, all
            #       'mei_trill_already_handled' processing will need to
            #       change, too.
            if isinstance(obj, m21.note.GeneralNote):
                for expr in obj.expressions:  # type: ignore
                    if isinstance(expr, m21.expressions.Trill):
                        if (hasattr(expr, 'mei_trill_already_handled')
                                and expr.mei_trill_already_handled):
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

            # 4. Ties on notes (including notes within chords) in this voice.
