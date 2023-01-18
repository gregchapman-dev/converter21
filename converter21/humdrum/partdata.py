# ------------------------------------------------------------------------------
# Name:          PartData.py
# Purpose:       PartData is an object somewhere between an m21 Part (or a list of
#                m21 PartStaffs) and a part column (containing staff columns) in a
#                HumGrid.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
import typing as t

import music21 as m21

from converter21.humdrum import StaffData

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class PartData:
    def __init__(
            self,
            partStaves: t.List[m21.stream.Part],    # or PartStaff (derived from Part)
            ownerScore,                             # ScoreData
            partIndex: int
    ) -> None:
        from converter21.humdrum import ScoreData
        self.ownerScore: ScoreData = ownerScore
        self.spannerBundle: m21.spanner.SpannerBundle = ownerScore.spannerBundle
        self._partIndex: int = partIndex
        self._hasDynamics: bool = False

        # partStaves will be a list of one Part, or a list of multiple PartStaffs,
        # but we don't really care. We make a StaffData out of each one.
        self.staves: t.List[StaffData] = []
        for s, partStaff in enumerate(partStaves):
            staffData: StaffData = StaffData(partStaff, self, s)
            self.staves.append(staffData)

        self._partName: str = self._findPartName(partStaves)
        self._partAbbrev: str = self._findPartAbbrev(partStaves)

    @property
    def partIndex(self) -> int:
        return self._partIndex

    @property
    def partName(self) -> str:
        return self._partName

    @property
    def partAbbrev(self) -> str:
        return self._partAbbrev

    @property
    def staffCount(self) -> int:
        return len(self.staves)

    @property
    def hasDynamics(self) -> bool:
        return self._hasDynamics

    @staticmethod
    def _findPartName(
            partStaves: t.List[m21.stream.Part]  # or PartStaff (derived from Part)
    ) -> str:
        if len(partStaves) == 0:
            return ''

        if len(partStaves) == 1:
            return partStaves[0].partName

        possibleNames: t.List[str] = [partStaff.partName for partStaff in partStaves]
        for possibleName in possibleNames:
            if possibleName:  # skip any '' or None partNames
                return possibleName  # return the first real name you see

        return ''

    @staticmethod
    def _findPartAbbrev(
            partStaves: t.List[m21.stream.Part]  # or PartStaff (derived from Part)
    ) -> str:
        if len(partStaves) == 0:
            return ''

        if len(partStaves) == 1:
            return partStaves[0].partAbbreviation

        possibleAbbrevs: t.List[str] = [partStaff.partAbbreviation for partStaff in partStaves]
        for possibleAbbrev in possibleAbbrevs:
            if possibleAbbrev:  # skip any '' or None partAbbrevs
                return possibleAbbrev  # return the first real abbrev you see

        return ''

    def reportEditorialAccidentalToOwner(self, editorialStyle: str) -> str:
        return self.ownerScore.reportEditorialAccidentalToOwner(editorialStyle)

    def reportCaesuraToOwner(self) -> str:
        return self.ownerScore.reportCaesuraToOwner()

    def reportCueSizeToOwner(self) -> str:
        return self.ownerScore.reportCueSizeToOwner()

    def reportNoteColorToOwner(self, color: str) -> str:
        return self.ownerScore.reportNoteColorToOwner(color)

    def reportLinkedSlurToOwner(self) -> str:
        return self.ownerScore.reportLinkedSlurToOwner()

    def receiveDynamic(self):
        self._hasDynamics = True
