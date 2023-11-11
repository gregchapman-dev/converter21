# ------------------------------------------------------------------------------
# Name:          meistaff.py
# Purpose:       MeiStaff is an object that represents a single music21
#                Part/PartStaff's contributions to a particular MeiMeasure.
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
# from music21.common import opFrac

# from converter21.mei import MeiExportError
# from converter21.mei import MeiInternalError
# from converter21.shared import M21Utilities
from converter21.mei import M21ObjectConvert
from converter21.mei import MeiLayer

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class MeiStaff:
    Debug: bool = False  # can be set to True for more debugging

    def __init__(
        self,
        staffNStr: str,
        m21Measure: m21.stream.Measure,
        m21Part: m21.stream.Part,
        spannerBundle: m21.spanner.SpannerBundle,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature]
    ) -> None:
        self.staffNStr: str = staffNStr
        self.m21Measure = m21Measure
        self.m21Part = m21Part
        self.spannerBundle = spannerBundle
        self.scoreMeterStream = scoreMeterStream
        self.nextFreeVoiceNumber = 1
        self.layers: list[MeiLayer] = []
        self.theOneLayerIsTheMeasureItself = False

        voices: list[m21.stream.Voice | m21.stream.Measure]
        if m21Measure.voices:
            voices = list(m21Measure.voices)
        else:
            voices = [m21Measure]
            self.theOneLayerIsTheMeasureItself = True

        for voice in voices:
            self.layers.append(MeiLayer(voice, self, spannerBundle, scoreMeterStream))

    def makeRootElement(self, tb: TreeBuilder):
        self.nextFreeVoiceNumber = 1
        if not self.theOneLayerIsTheMeasureItself:
            # Process any clef/timesig/keysig at offset 0 in enclosing measure (but
            # if the m21Measure itself is the first measure in the m21Part, skip
            # the very first clef, timesig and keysig, since those initial ones are
            # handled in the original <scoredef>).
            # We assume that any clef/timesig/keysig at non-zero measure offset will
            # be sitting alongside the notes (e.g. in a Voice), and can just be emitted
            # like a note, without this <staffdef> wrapper.
            firstSeen: list[str] = []
            staffDefEmitted: bool = False
            for el in self.m21Measure:
                if el.offset == 0:
                    if isinstance(
                        el,
                        (m21.clef.Clef, m21.meter.TimeSignature, m21.key.KeySignature)
                    ):
                        if self.m21Measure.offset == 0:
                            # very first measure in part:
                            # skip the first clef, the first timesig, and first keysig
                            if isinstance(el, m21.clef.Clef):
                                if 'clef' not in firstSeen:
                                    firstSeen.append('clef')
                                    continue
                            if isinstance(el, m21.meter.TimeSignature):
                                if 'timesig' not in firstSeen:
                                    firstSeen.append('timesig')
                                    continue
                            if isinstance(el, m21.key.KeySignature):
                                if 'keysig' not in firstSeen:
                                    firstSeen.append('keysig')
                                    continue

                        if not staffDefEmitted:
                            tb.start('staffDef', {'n': self.staffNStr})
                            staffDefEmitted = True
                        M21ObjectConvert.convertM21ObjectToMei(el, tb)
            if staffDefEmitted:
                tb.end('staffDef')

        tb.start('staff', {'n': self.staffNStr})
        for layer in self.layers:
            layer.makeRootElement(tb)
        # 888 process any final barline in the Measure (MeiStaff)
        tb.end('staff')



    def makePostStavesElements(self, tb: TreeBuilder):
        for layer in self.layers:
            layer.makePostStavesElements(tb)

        # The top-level measure (if not treated as the one layer) might have some
        # post-staves elements, too (e.g. Dynamic, TextExpression, TempoIndication).
        # This is a small subset of what can be emitted in layer.makePostStavesElements.
        # Also, there may be SpannerAnchors that exist at the Measure level.
        if not self.theOneLayerIsTheMeasureItself:
            for obj in self.m21Measure:
                if M21ObjectConvert.streamElementBelongsInPostStaves(obj):
                    M21ObjectConvert.convertPostStaveStreamElement(
                        obj,
                        self.staffNStr,
                        self.m21Part,
                        self.m21Measure,
                        self.scoreMeterStream,
                        tb
                    )
                if isinstance(obj, m21.spanner.SpannerAnchor):
                    for spanner in obj.getSpannerSites():
                        if hasattr(spanner, 'mei_trill_already_handled'):
                            continue
                        if spanner.isFirst(obj):
                            # print(f'spanner seen: {spanner.classes[0]}', file=sys.stderr)
                            M21ObjectConvert.postStavesSpannerToMei(
                                spanner,
                                self.staffNStr,
                                self.m21Part,
                                self.m21Measure,
                                self.scoreMeterStream,
                                tb
                            )

        # lastly, any fermata on the right barline is a post-staves element.
        if self.m21Measure.rightBarline is not None:
            if self.m21Measure.rightBarline.pause is not None:
                M21ObjectConvert.fermataToMei(
                    self.m21Measure.rightBarline,
                    self.m21Measure.rightBarline.pause,
                    self.staffNStr,
                    self.m21Part,
                    self.m21Measure,
                    self.scoreMeterStream,
                    tb
                )

