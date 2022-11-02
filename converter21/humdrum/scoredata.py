# ------------------------------------------------------------------------------
# Name:          ScoreData.py
# Purpose:       ScoreData is an object somewhere between an m21 Score
#                and a HumGrid. It contains a list of PartDatas, each
#                of which contains a list of StaffDatas, derived from
#                all the Parts/PartStaffs in the Score.
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
from music21.common.misc import flattenList

from converter21.humdrum import HumdrumInternalError
from converter21.humdrum import EventData
from converter21.humdrum import PartData

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

# TODO: pass StaffGroup into PartData() so we have another source of partName/partAbbrev

class ScoreData:
    def __init__(self, score: m21.stream.Score, ownerWriter) -> None:
        from converter21.humdrum import HumdrumWriter
        self.ownerWriter: HumdrumWriter = ownerWriter

        if not isinstance(score, m21.stream.Score):
            raise HumdrumInternalError('ScoreData must be initialized with a music21 Score object')

        self.m21Score: m21.stream.Score = score
        self.spannerBundle: m21.spanner.SpannerBundle = ownerWriter.spannerBundle

        self.parts: t.List[PartData] = []

        # key is id(m21Object): a large integer that is actually the mem address of m21Object
        self.eventFromM21Object: t.Dict[int, EventData] = {}

        # Following staff group code stolen from musicxml exporter in music21.
        # Keep it up-to-date!

        staffGroups = self.m21Score.getElementsByClass('StaffGroup')
        joinableGroups: t.List[m21.layout.StaffGroup] = []

        # Joinable groups must consist of only PartStaffs with Measures
        # that exist in self.m21Score
        for sg in staffGroups:
            if len(sg) <= 1:
                continue
            if not all('PartStaff' in p.classes for p in sg):
                continue
            if not all(p.getElementsByClass('Measure') for p in sg):
                continue
            if not all(p in self.m21Score.parts for p in sg):
                continue
            joinableGroups.append(sg)

        # Deduplicate joinable groups (ex: bracket and brace enclose same PartStaffs)
        permutations = set()
        deduplicatedGroups: t.List[m21.layout.StaffGroup] = []
        for jg in joinableGroups:
            containedParts = tuple(jg)
            if containedParts not in permutations:
                deduplicatedGroups.append(jg)
            permutations.add(containedParts)
        joinableGroups = deduplicatedGroups

        # But forbid overlapping, spaghetti staffGroups
        joinable_components_list = flattenList(deduplicatedGroups)
        if len(set(joinable_components_list)) != len(joinable_components_list):
            joinableGroups = []

        partsWithMoreThanOneStaff: t.List[t.List[m21.stream.Part]] = []
        groupedParts: t.List[m21.stream.PartStaff] = []
        for jg in joinableGroups:
            partsWithMoreThanOneStaff.append([])
            for partStaff in jg:
                partsWithMoreThanOneStaff[-1].append(partStaff)
                groupedParts.append(partStaff)

        scorePartsStillToProcess = list(score.parts)
        for part in score.parts:  # includes PartStaffs, too
            if part not in scorePartsStillToProcess:
                # we already processed this due to a staff group
                continue

            if 'PartStaff' in part.classes and part in groupedParts:
                # make a new partData entry for these PartStaffs and fill it
                for partStaffList in partsWithMoreThanOneStaff:
                    if part in partStaffList:
                        partOfStavesData: PartData = PartData(partStaffList, self, len(self.parts))
                        self.parts.append(partOfStavesData)
                        for ps in partStaffList:
                            scorePartsStillToProcess.remove(ps)  # so we don't double process
                        break
            else:
                # make a new partData entry for the Part (one staff which is the part)
                partData: PartData = PartData([part], self, len(self.parts))
                self.parts.append(partData)
                scorePartsStillToProcess.remove(part)

    @property
    def partCount(self) -> int:
        return len(self.parts)

    def getStaffCounts(self) -> t.List[int]:
        output: t.List[int] = []
        for part in self.parts:
            output.append(part.staffCount)
        return output

    def reportEditorialAccidentalToOwner(self, editorialStyle: str) -> str:
        return self.ownerWriter.reportEditorialAccidentalToOwner(editorialStyle)

    def reportCaesuraToOwner(self) -> str:
        return self.ownerWriter.reportCaesuraToOwner()

    def reportCueSizeToOwner(self) -> str:
        return self.ownerWriter.reportCueSizeToOwner()

    def reportNoteColorToOwner(self, color: str) -> str:
        return self.ownerWriter.reportNoteColorToOwner(color)

    def reportLinkedSlurToOwner(self) -> str:
        return self.ownerWriter.reportLinkedSlurToOwner()
