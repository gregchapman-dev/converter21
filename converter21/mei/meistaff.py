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
        m21Part: m21.stream.Part
    ) -> None:
        self.staffNStr: str = staffNStr
        self.m21Measure = m21Measure
        self.m21Part = m21Part

    def makeRootElement(self, tb: TreeBuilder):
        tb.start('staff', {'n': self.staffNStr})
        # notes etc go here
        tb.end('staffs')
