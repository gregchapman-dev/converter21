# ------------------------------------------------------------------------------
# Name:          StaffData.py
# Purpose:       StaffData is an object somewhere between an m21 Part/PartStaff and a
#                staff column in a HumGrid. A ScoreData contains (among other things)
#                a list of parts (partDatas), each of which is a list of one or more
#                StaffDatas.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021 Greg Chapman
# License:       BSD, see LICENSE
# ------------------------------------------------------------------------------
import sys
from typing import Union
import music21 as m21

from converter21.humdrum import MeasureData

### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

class StaffData:
    def __init__(self, partStaff: Union[m21.stream.Part, m21.stream.PartStaff],
                       ownerPart,
                       staffIndex: int):
        from converter21.humdrum import PartData
        ownerPart: PartData
        self.ownerPart: PartData = ownerPart
        self.m21PartStaff: Union[m21.stream.Part, m21.stream.PartStaff] = partStaff
        self._staffIndex: int = staffIndex
        self.measures: [MeasureData] = []

        for m, measure in enumerate(partStaff.measures):
            measData: MeasureData = MeasureData(measure, self, m)
            self.measures.append(measData)

    @property
    def measureCount(self) -> int:
        return len(self.measures)

    @property
    def partIndex(self) -> int:
        return self.ownerPart.partIndex

    @property
    def staffIndex(self) -> int:
        return self._staffIndex

    def receiveEditorialAccidental(self, editorialStyle: str):
        self.ownerPart.receiveEditorialAccidental(editorialStyle)