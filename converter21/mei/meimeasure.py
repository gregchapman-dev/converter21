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
# from xml.etree.ElementTree import TreeBuilder
import typing as t

import music21 as m21
# from music21.common import opFrac

from converter21.mei import MeiStaff
from converter21.mei import M21ObjectConvert
# from converter21.mei import MeiExportError
from converter21.mei import MeiInternalError
from converter21.shared import M21Utilities
from converter21.shared import DebugTreeBuilder as TreeBuilder

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
        parentScore,  # MeiScore
        # custom m21 attrs to delete later (children will extend this)
        customAttrs: dict[m21.base.Music21Object, list[str]],
        spannerBundle: m21.spanner.SpannerBundle,
    ) -> None:
        '''
            parentScore: the parent MeiScore
            m21Measures: a list of simultaneous measures, one per Part/PartStaff
            prevMeiMeasure: the immediately previous MeiMeasure
            spannerBundle: the spanner bundle containing all spanners in the score
        '''
        if t.TYPE_CHECKING:
            from converter21.mei import MeiScore
            assert isinstance(parentScore, MeiScore)
            assert isinstance(prevMeiMeasure, MeiMeasure) or prevMeiMeasure is None

        self.m21Measures: list[m21.stream.Measure] = m21Measures
        self.nextMeiMeasure: MeiMeasure | None = None
        self.prevMeiMeasure: MeiMeasure | None = prevMeiMeasure
        if prevMeiMeasure is not None:
            prevMeiMeasure.nextMeiMeasure = self

        self.customAttrs: dict[m21.base.Music21Object, list[str]] = customAttrs
        self.spannerBundle = spannerBundle

        self.staves: list[MeiStaff] = []
        self.measureNumStr: str = ''
        for m in m21Measures:
            if not self.measureNumStr:
                # m.measureNumberWithSuffix() always returns a non-empty string.
                # At the very least, it will return '0'.
                self.measureNumStr = m.measureNumberWithSuffix()
            part: m21.stream.Part | None = (
                self._getPartFor(m, list(parentScore.staffNumbersForM21Parts.keys()))
            )
            if part is None:
                raise MeiInternalError('Found a Measure that\'s not in a Part.')
            nStr: str = str(parentScore.staffNumbersForM21Parts[part])
            staff = MeiStaff(nStr, m, parentScore, customAttrs, spannerBundle)
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

    def startsWithPageBreak(self) -> tuple[bool, int | None]:
        for m in self.m21Measures:
            pageLayouts: list[m21.base.Music21Object] = (
                list(m[m21.layout.PageLayout])
            )
            if not pageLayouts:
                continue
            pageLayout: m21.base.Music21Object = pageLayouts[0]
            if t.TYPE_CHECKING:
                assert isinstance(pageLayout, m21.layout.PageLayout)
            if pageLayout.offset != 0:
                continue
            if not pageLayout.isNew:
                continue
            return True, pageLayout.pageNumber
        return False, 0

    def startsWithSystemBreak(self) -> bool:
        for m in self.m21Measures:
            systemLayouts: list[m21.base.Music21Object] = (
                list(m[m21.layout.SystemLayout])
            )
            if not systemLayouts:
                continue
            systemLayout: m21.base.Music21Object = systemLayouts[0]
            if t.TYPE_CHECKING:
                assert isinstance(systemLayout, m21.layout.SystemLayout)
            if systemLayout.offset != 0:
                continue
            if not systemLayout.isNew:
                continue
            return True
        return False

    def makeRootElement(self, tb: TreeBuilder):
        startsWithPageBreak: bool = False
        pageNum: int | None = None
        startsWithPageBreak, pageNum = self.startsWithPageBreak()
        if startsWithPageBreak:
            pbAttr: dict[str, str] = {}
            if pageNum is not None:
                pbAttr['n'] = str(pageNum)
            tb.start('pb', pbAttr)
            tb.end('pb')
        elif self.startsWithSystemBreak():
            tb.start('sb', {})
            tb.end('sb')

        self._checkForEndingStart(tb)

        attr: dict[str, str] = {}
        self._fillInMeasureAttributes(attr)

        tb.start('measure', attr)
        for staff in self.staves:
            staff.makeRootElement(tb)
        for staff in self.staves:
            staff.makePostStavesElements(tb)
        tb.end('measure')

        self._checkForEndingEnd(tb)

    def _checkForEndingStart(self, tb: TreeBuilder):
        rb: m21.spanner.RepeatBracket | None = None

        for m21m in self.m21Measures:
            # Any one of them being first in a RepeatBracket is sufficient
            # (they should all be, or none be).
            for spanner in m21m.getSpannerSites():
                if not M21Utilities.isIn(spanner, self.spannerBundle):
                    continue
                if isinstance(spanner, m21.spanner.RepeatBracket):
                    if spanner.isFirst(m21m):
                        rb = spanner
                        break
            if rb is not None:
                break

        if rb is None:
            return

        attr: dict[str, str] = {}

        if rb.overrideDisplay:
            # technically we should strip spaces, but... that messes with a
            # multi-word override, and verovio is happy to display ending@n
            # with spaces.  Most overrides will be just one word anyway.
            attr['n'] = rb.overrideDisplay
        else:
            # rb.number is a single number e.g. '1', or '2', or a list of numbers
            # e.g. '1, 5' or '1-3'.  We must strip out any spaces, though, to meet
            # MEI spec for ending@n
            nStr: str = rb.number
            nStr = nStr.strip()
            attr['n'] = nStr

        tb.start('ending', attr)

    def _checkForEndingEnd(self, tb: TreeBuilder):
        rb: m21.spanner.RepeatBracket | None = None

        for m21m in self.m21Measures:
            # Any one of them being last in a RepeatBracket is sufficient
            # (they should all be, or none be).
            for spanner in m21m.getSpannerSites():
                if not M21Utilities.isIn(spanner, self.spannerBundle):
                    continue
                if isinstance(spanner, m21.spanner.RepeatBracket):
                    if spanner.isLast(m21m):
                        rb = spanner
                        break
            if rb is not None:
                break

        if rb is None:
            return

        tb.end('ending')

    def _fillInMeasureAttributes(self, attr: dict[str, str]):
        nStr: str = self.measureNumStr
        if nStr and nStr != '0':
            attr['n'] = self.measureNumStr

        if len(self.staves) == 0:
            return

        meiStaff = self.staves[0]
        if self.prevMeiMeasure is None:
            # This is the very first measure.  We need to emit 'left' attribute
            # instead of assuming the previous measure combined it into their
            # 'right' attribute.
            myLeftBarline: m21.bar.Barline | None = meiStaff.m21Measure.leftBarline
            left: str = M21ObjectConvert.m21BarlineToMeiMeasureBarlineAttr(
                myLeftBarline,
                self.customAttrs
            )
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
            nextLeftBarline,
            self.customAttrs
        )
        if right:
            attr['right'] = right
