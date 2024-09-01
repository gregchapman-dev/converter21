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
# from xml.etree.ElementTree import TreeBuilder
import typing as t

import music21 as m21
from music21.common import OffsetQL
# from music21.common import opFrac

# from converter21.mei import MeiExportError
# from converter21.mei import MeiInternalError
from converter21.shared import M21Utilities
from converter21.mei import M21ObjectConvert
from converter21.mei import MeiLayer
from converter21.shared import DebugTreeBuilder as TreeBuilder

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
        parentScore,  # MeiScore
        # custom m21 attrs to delete later (children will extend this)
        customAttrs: dict[m21.base.Music21Object, list[str]],
        spannerBundle: m21.spanner.SpannerBundle,
    ) -> None:
        if t.TYPE_CHECKING:
            from converter21.mei import MeiScore
            assert isinstance(parentScore, MeiScore)

        self.staffNStr: str = staffNStr
        self.m21Measure = m21Measure
        self.m21Score = parentScore.m21Score
        self.customAttrs: dict[m21.base.Music21Object, list[str]] = customAttrs
        self.spannerBundle = spannerBundle
        self.scoreMeterStream = parentScore.scoreMeterStream
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
            self.layers.append(MeiLayer(voice, self, parentScore, customAttrs, spannerBundle))

    def makeRootElement(self, tb: TreeBuilder):
        self.nextFreeVoiceNumber = 1
        extraStaffChanges: list[
            tuple[
                m21.clef.Clef | m21.meter.TimeSignature | m21.key.KeySignature,
                OffsetQL
            ]
        ] = []

        if not self.theOneLayerIsTheMeasureItself:
            # Process any clef/timesig/keysig at offset 0 in enclosing measure (but
            # if the m21Measure itself is the first measure in the part, skip the
            # very first clef, timesig and keysig, since those initial ones are
            # handled in the original <scoredef>).

            # The clefs/timesigs/keysigs at non-zero measure offset will either be
            # sitting alongside the notes (e.g. in a Voice), or they will not be at
            # the Voice level (i.e. they will be at the Measure level).

            # The clefs/timesigs/keysigs at Voice level can just be emitted in that
            # MeiLayer like a note, without this <staffDef> wrapper.

            # The clefs/timesigs/keysigs at Measure level will need to be emitted
            # in all the MeiLayers (again without the <staffDef> wrapper), with the
            # clef/timesig/keysig in the first layer being fully specified, and the
            # other clefs/timesigs/keysigs simply being marked as being @sameas the
            # clef/timesig/keysig in the first layer.

            firstSeen: list[str] = []
            staffDefEmitted: bool = False
            for el in self.m21Measure:
                if isinstance(
                    el,
                    (m21.clef.Clef, m21.meter.TimeSignature, m21.key.KeySignature)
                ):
                    elOffsetInMeasure: OffsetQL = el.getOffsetInHierarchy(self.m21Measure)
                    if elOffsetInMeasure == 0:
                        if self.m21Measure.getOffsetInHierarchy(self.m21Score) == 0:
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
                        M21ObjectConvert.convertM21ObjectToMei(el, self.spannerBundle, tb)
                    else:
                        # gather up non-zero offset clefs/timesigs/keysigs to emit in MeiLayer
                        if len(self.layers) > 1:
                            # we'll need an xmlId for any sameas references from extra layers.
                            M21Utilities.assureXmlId(el)
                        extraStaffChanges.append((el, elOffsetInMeasure))

            if staffDefEmitted:
                tb.end('staffDef')

        tb.start('staff', {'n': self.staffNStr})
        for layer in self.layers:
            layer.makeRootElement(tb, extraStaffChanges=extraStaffChanges)
        tb.end('staff')

    def makePostStavesElements(self, tb: TreeBuilder):
        for layer in self.layers:
            layer.makePostStavesElements(tb)

        # The top-level measure (if not treated as the one layer) might have some
        # post-staves elements, too (e.g. Dynamic, TextExpression, TempoIndication,
        # ChordSymbol).
        # This is a small subset of what can be emitted in layer.makePostStavesElements.
        # Also, there may be SpannerAnchors that exist at the Measure level.
        if not self.theOneLayerIsTheMeasureItself:
            for obj in self.m21Measure:
                if M21ObjectConvert.streamElementBelongsInPostStaves(obj):
                    M21ObjectConvert.convertPostStaveStreamElement(
                        obj,
                        self.staffNStr,
                        self.m21Score,
                        self.m21Measure,
                        self.scoreMeterStream,
                        tb
                    )
                if isinstance(obj, m21.spanner.SpannerAnchor):
                    for spanner in obj.getSpannerSites():
                        if not M21Utilities.isIn(spanner, self.spannerBundle):
                            continue
                        if hasattr(spanner, 'mei_trill_already_handled'):
                            continue
                        if spanner.isFirst(obj):
                            # print(f'spanner seen: {spanner.classes[0]}', file=sys.stderr)
                            M21ObjectConvert.postStavesSpannerToMei(
                                spanner,
                                self.staffNStr,
                                self.m21Score,
                                self.m21Measure,
                                self.scoreMeterStream,
                                self.customAttrs,
                                self.spannerBundle,
                                tb
                            )

        # lastly, any fermata on the right barline is a post-staves element.
        if self.m21Measure.rightBarline is not None:
            if self.m21Measure.rightBarline.pause is not None:
                M21ObjectConvert.fermataToMei(
                    self.m21Measure.rightBarline,
                    self.m21Measure.rightBarline.pause,
                    self.staffNStr,
                    self.m21Score,
                    self.m21Measure,
                    self.scoreMeterStream,
                    tb
                )

