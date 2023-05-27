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

# from converter21.mei import MeiExportError
# from converter21.mei import MeiInternalError
from converter21.mei import MeiMeasure
from converter21.mei import M21ObjectConvert
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
        for measureStack in offsetIterator:
            meiMeas = MeiMeasure(
                measureStack,
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
                part.getElementsByClass(m21.layout.StaffLayout).getElementsByOffset(0.0)
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
