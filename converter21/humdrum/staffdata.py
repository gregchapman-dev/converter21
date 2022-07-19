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
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
#from typing import Union
import music21 as m21

from converter21.humdrum import MeasureData
from converter21.humdrum import M21Utilities

### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

class StaffData:
    def __init__(self, partStaff: m21.stream.Part, # could be PartStaff, which is derived from Part
                       ownerPart,
                       staffIndex: int):
        from converter21.humdrum import PartData
        ownerPart: PartData
        self.ownerPart: PartData = ownerPart
        self.m21PartStaff: m21.stream.Part = partStaff
        self.spannerBundle = ownerPart.spannerBundle # inherited from ownerScore, ultimately
        self._transposeWrittenToSounding(partStaff)
        self._staffIndex: int = staffIndex
        self._hasDynamics: bool = False
        self._verseCount: int = 0
        self.measures: [MeasureData] = []

        prevMeasData: MeasureData = None
        for m, measure in enumerate(partStaff.getElementsByClass('Measure')):
            measData: MeasureData = MeasureData(measure, self, m, prevMeasData)
            self.measures.append(measData)
            prevMeasData = measData

    @staticmethod
    def _transposeWrittenToSounding(partStaff: m21.stream.Part):
        # Transpose any transposing instrument parts to "sounding pitch" (a.k.a. concert pitch).
        # For performance, check the instruments here, since stream.toSoundingPitch
        # can be expensive, even if there is no transposing instrument.
        if partStaff and partStaff.atSoundingPitch is False: # might be 'unknown' or True
            for inst in partStaff.getElementsByClass(m21.instrument.Instrument):
                if M21Utilities.isTransposingInstrument(inst):
                    partStaff.toSoundingPitch(inPlace=True)
                    break # you only need to transpose the part once

    @property
    def measureCount(self) -> int:
        return len(self.measures)

    @property
    def partIndex(self) -> int:
        return self.ownerPart.partIndex

    @property
    def staffIndex(self) -> int:
        return self._staffIndex

    @property
    def hasDynamics(self) -> bool:
        return self._hasDynamics

    @property
    def verseCount(self) -> int:
        return self._verseCount

    def reportEditorialAccidentalToOwner(self, editorialStyle: str) -> str:
        return self.ownerPart.reportEditorialAccidentalToOwner(editorialStyle)

    def reportCaesuraToOwner(self) -> str:
        return self.ownerPart.reportCaesuraToOwner()

    def reportCueSizeToOwner(self) -> str:
        return self.ownerPart.reportCueSizeToOwner()

    def reportNoteColorToOwner(self, color: str) -> str:
        return self.ownerPart.reportNoteColorToOwner(color)

    def reportLinkedSlurToOwner(self) -> str:
        return self.ownerPart.reportLinkedSlurToOwner()

    def receiveVerseCount(self, verseCount: int):
        # don't propagate up to PartData, verses are per staff
        # accumulate the maximum verseCount seen
        if verseCount > self._verseCount:
            self._verseCount = verseCount

    def receiveDynamic(self):
        # don't propagate up to PartData, we do per-staff dynamics
        self._hasDynamics = True
