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
from xml.etree.ElementTree import ElementTree
# import typing as t

import music21 as m21
# from music21.common import opFrac

# from converter21.mei import MeiExportError
# from converter21.mei import MeiInternalError
from converter21.mei import MeiMeasure
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
        self.staffNumbersForM21Parts: dict[m21.stream.Part, int] = (
            self._getStaffNumbersForM21Parts(m21Score)
        )
        self.staffGroupTrees: list[M21StaffGroupTree] = (
            M21Utilities.getStaffGroupTrees(
                list(m21Score[m21.layout.StaffGroup]),
                self.staffNumbersForM21Parts
            )
        )

        self.measures: list[MeiMeasure] = self._getMeiMeasures(m21Score)

    def makeElementTree(self) -> ElementTree:
        output: ElementTree = ElementTree()
        return output

    @staticmethod
    def _getStaffNumbersForM21Parts(score: m21.stream.Score) -> dict[m21.stream.Part, int]:
        output: dict[m21.stream.Part, int] = {}
        for staffIdx, part in enumerate(score.parts):
            output[part] = staffIdx + 1  # staff numbers are 1-based
        return output

    def _getMeiMeasures(self, m21Score: m21.stream.Score) -> list[MeiMeasure]:
        output: list[MeiMeasure] = []

        # OffsetIterator is not recursive, so we have to recursively pull all the measures
        # into one single stream, before we can use OffsetIterator to generate the "stacks"
        # of Measures that all occur at the same offset (moment) in the score.
        measuresStream: m21.stream.Stream[m21.stream.Measure] = (
            m21Score.recurse().getElementsByClass(m21.stream.Measure).stream()
        )
        offsetIterator: m21.stream.iterator.OffsetIterator[m21.stream.Measure] = (
            m21.stream.iterator.OffsetIterator(measuresStream)
        )
        for measureStack in offsetIterator:
            meiMeas = MeiMeasure(measureStack, self.staffNumbersForM21Parts)
            output.append(meiMeas)

        return output



