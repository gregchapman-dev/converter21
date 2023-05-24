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
        staffNumbersForM21Parts: dict[m21.stream.Part, int]
    ) -> None:
        '''
            m21Measures: a list of simultaneous measures, one per staff
            staffNumbersForM21Parts: a dictionary of staff numbers, keyed by Part/PartStaff
        '''
        # self.staffNumbersForM21Parts = staffNumbersForM21Parts
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
            staff = MeiStaff(nStr, m, part)
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
        tb.start('measure', {'n': self.measureNumStr})
        for staff in self.staves:
            staff.makeRootElement(tb)
        for staff in self.staves:
            staff.makePostStavesElements(tb)
        tb.end('measure')

