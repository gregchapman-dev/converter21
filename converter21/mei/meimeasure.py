# ------------------------------------------------------------------------------
# Name:          meimeasure.py
# Purpose:       MeiMeasure is an object that represents a number of simultaneous
#                music21 measures, one per staff.
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

from converter21.mei import MeiStaff
from converter21.mei import M21ObjectConvert
# from converter21.mei import MeiExportError
from converter21.mei import MeiInternalError
# from converter21.shared import M21Utilities

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class MeiMeasure:
    Debug: bool = False  # can be set to True for more debugging

    def __init__(
        self,
        m21Measures: list[m21.stream.Measure],
        prevMeiMeasure,  # MeiMeasure | None
        staffNumbersForM21Parts: dict[m21.stream.Part, int],
        spannerBundle: m21.spanner.SpannerBundle,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature]
    ) -> None:
        '''
            m21Measures: a list of simultaneous measures, one per staff
            staffNumbersForM21Parts: a dictionary of staff numbers, keyed by Part/PartStaff
        '''
        self.nextMeiMeasure: MeiMeasure | None = None
        self.prevMeiMeasure: MeiMeasure | None = prevMeiMeasure
        if prevMeiMeasure is not None:
            prevMeiMeasure.nextMeiMeasure = self

        # self.staffNumbersForM21Parts = staffNumbersForM21Parts
        self.spannerBundle = spannerBundle
        self.scoreMeterStream = scoreMeterStream
        self.staves: list[MeiStaff] = []
        self.measureNumStr: str = ''
        for m in m21Measures:
            if not self.measureNumStr:
                # m.measureNumberWithSuffix() always returns a non-empty string.
                # At the very least, it will return '0'.
                self.measureNumStr = m.measureNumberWithSuffix()
            part: m21.stream.Part | None = self._getPartFor(m, list(staffNumbersForM21Parts.keys()))
            if part is None:
                raise MeiInternalError('Found a Measure that\'s not in a Part.')
            nStr: str = str(staffNumbersForM21Parts[part])
            staff = MeiStaff(nStr, m, part, spannerBundle, scoreMeterStream)
            self.staves.append(staff)

    @staticmethod
    def _getPartFor(
        measure: m21.stream.Measure,
        parts: list[m21.stream.Part]
    ) -> m21.stream.Part | None:
        for p in parts:
            if p in measure.sites:
                return p
        return None

    def makeRootElement(self, tb: TreeBuilder):
        attr: dict[str, str] = {}
        self._fillInMeasureAttributes(attr)

        tb.start('measure', attr)
        for staff in self.staves:
            staff.makeRootElement(tb)
        for staff in self.staves:
            staff.makePostStavesElements(tb)
        tb.end('measure')

    def _fillInMeasureAttributes(self, attr: dict[str, str]):
        attr['n'] = self.measureNumStr

        if len(self.staves) == 0:
            return

        meiStaff = self.staves[0]
        if self.prevMeiMeasure is None:
            # This is the very first measure.  We need to emit 'left' attribute
            # instead of assuming the previous measure combined it into their
            # 'right' attribute.
            myLeftBarline: m21.bar.Barline | None = meiStaff.m21Measure.leftBarline
            left: str = M21ObjectConvert.m21BarlineToMeiMeasureBarlineAttr(myLeftBarline)
            if left:
                attr['left'] = left

        # Our left is already handled, either in the code above or in the previous measure.
        # Now we have to handle our right + next measure's left (if there is a next measure).

        myRightBarline: m21.bar.Barline | None = meiStaff.m21Measure.rightBarline
        nextLeftBarline: m21.bar.Barline | None = None
        if self.nextMeiMeasure is not None and len(self.nextMeiMeasure.staves) > 0:
            nextLeftBarline = self.nextMeiMeasure.staves[0].m21Measure.leftBarline

        right: str = M21ObjectConvert.m21BarlinesToMeiMeasureBarlineAttr(
            myRightBarline,
            nextLeftBarline
        )
        if right:
            attr['right'] = right
