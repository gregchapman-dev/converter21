# ------------------------------------------------------------------------------
# Name:          HumGrid.py
# Purpose:       HumGrid is an intermediate container for converting into Humdrum
#                syntax.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
import re
import typing as t

from music21.common import opFrac

from converter21.humdrum import HumdrumInternalError
from converter21.humdrum import HumNum, HumNumIn
from converter21.humdrum import Convert

from converter21.humdrum import SliceType
from converter21.humdrum import MeasureStyle
from converter21.humdrum import GridVoice
from converter21.humdrum import GridStaff
from converter21.humdrum import GridPart
from converter21.humdrum import GridSlice
from converter21.humdrum import GridMeasure

from converter21.humdrum import HumdrumToken
from converter21.humdrum import HumdrumLine
from converter21.humdrum import HumdrumFile

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class HumGrid:
    def __init__(self) -> None:
        self.measures: t.List[GridMeasure] = []
        self._allSlices: t.List[GridSlice] = []

        self.hasRepeatBrackets: bool = False

        # indexed by part (max = 100 parts)
        self._verseCount: t.List[t.List[int]] = []
        for _ in range(0, 100):
            self._verseCount.append([])
        self._harmonyCount: t.List[int] = [0] * 100
        self._xmlIds: t.List[bool] = [False] * 100
        self._figuredBass: t.List[bool] = [False] * 100
        self._harmony: t.List[bool] = [False] * 100
        self._partNames: t.List[str] = []  # grows as necessary
        self._dynamics: t.List[bool] = [False] * 100

        # options:
        self._pickup: bool = False
        self._recip: bool = False  # include **recip spine in output

    def __str__(self) -> str:
        output = 'GRID:'
        for i, measure in enumerate(self.measures):
            output += '\nMEASURE ' + str(i) + ' =========================\n' + str(measure)
        return output

    '''
    //////////////////////////////
    //
    // HumGrid::addMeasureToBack -- Allocate a GridMeasure at the end of the
    //     measure list.
    '''
    def appendMeasure(self) -> GridMeasure:
        gm: GridMeasure = GridMeasure(self)
        self.measures.append(gm)
        return gm

    '''
    //////////////////////////////
    //
    // HumGrid::deleteMeasure --
    '''
    def deleteMeasure(self, measureIndex: int) -> None:
        self.measures.pop(measureIndex)

    '''
    //////////////////////////////
    //
    // HumGrid::enableRecipSpine --
    '''
    def enableRecipSpine(self) -> None:
        self._recip = True

    '''
    //////////////////////////////
    //
    // HumGrid::getPartCount -- Return the number of parts in the Grid
    //   by looking at the number of parts in the first spined GridSlice.
    '''
    @property
    def partCount(self) -> int:
        if self._allSlices:
            return len(self._allSlices[0].parts)

        if not self.measures:
            return 0

        if not self.measures[0].slices:
            return 0

        # if there is at least one measure (with at least one slice)
        # return the number of parts in the last slice of the first measure
        return len(self.measures[0].slices[-1].parts)

    '''
    //////////////////////////////
    //
    // HumGrid::hasPickup --
    '''
    @property
    def hasPickup(self) -> bool:
        return self._pickup

    '''
    //////////////////////////////
    //
    // HumGrid::getStaffCount --
    '''
    def staffCount(self, partIndex: int) -> int:
        if not self.measures:
            return 0

        if not self.measures[0].slices:
            return 0

        # if there is at least one measure (with at least one slice)
        # return the number of staves in the specified part in the last slice
        # of the first measure.
        return len(self.measures[0].slices[-1].parts[partIndex].staves)

    '''
    //////////////////////////////
    //
    // HumGrid::getHarmonyCount --
    '''
    def harmonyCount(self, partIndex: int) -> int:
        if 0 <= partIndex < len(self._harmonyCount):
            return self._harmonyCount[partIndex]
        return 0

    '''
    //////////////////////////////
    //
    // HumGrid::getVerseCount --
    '''
    def verseCount(self, partIndex: int, staffIndex: int) -> int:
        if 0 <= partIndex < len(self._verseCount):
            staffNumber: int = staffIndex + 1
            if 1 <= staffNumber < len(self._verseCount[partIndex]):
                return self._verseCount[partIndex][staffNumber]
        return 0

    '''
    //////////////////////////////
    //
    // HumGrid::hasXmlids -- Return true if there are any xmlids for the part.
    '''
    def hasXmlIds(self, partIndex: int) -> bool:
        if 0 <= partIndex < len(self._xmlIds):
            return self._xmlIds[partIndex]
        return False

    '''
    //////////////////////////////
    //
    // HumGrid::getXmlidCount --
    '''
    def xmlIdCount(self, partIndex: int) -> int:
        # yeah this is weird, but if we ever have more than one xmlID per part,
        # everyone should already be calling the right function, and we just
        # have to change the code here (and in hasXmlIds above).
        return int(self.hasXmlIds(partIndex))


    '''
    //////////////////////////////
    //
    // HumGrid::hasDynamics -- Return true if there are any dynamics for the part/staff.
    '''
    def hasDynamics(self, partIndex: int) -> bool:
        if 0 <= partIndex < len(self._dynamics):
            return self._dynamics[partIndex]
        return False

    '''
    //////////////////////////////
    //
    // HumGrid::getDynamicsCount --
    '''
    def dynamicsCount(self, partIndex: int) -> int:
        if 0 <= partIndex < len(self._dynamics):
            return int(self._dynamics[partIndex])  # cast bool to int (0 or 1)
        return 0


    '''
    //////////////////////////////
    //
    // HumGrid::hasFiguredBass -- Return true if there is any figured bass for the part.
    '''
    def hasFiguredBass(self, partIndex: int) -> bool:
        if 0 <= partIndex < len(self._figuredBass):
            return self._figuredBass[partIndex]
        return False

    '''
    //////////////////////////////
    //
    // HumGrid::getFiguredBassCount --
    '''
    def figuredBassCount(self, partIndex: int) -> int:
        if 0 <= partIndex < len(self._figuredBass):
            return int(self._figuredBass[partIndex])  # cast bool to int (0 or 1)
        return 0

    def hasHarmony(self, partIndex: int) -> bool:
        if 0 <= partIndex < len(self._harmony):
            return self._harmony[partIndex]
        return False

    '''
    //////////////////////////////
    //
    // HumGrid::setDynamicsPresent -- Indicate that part needs a **dynam spine.
        Actually, indicate that part,staff needs a **dynam spine.  Dynamics are on the staff.
    '''
    def setDynamicsPresent(self, partIndex: int) -> None:
        if 0 <= partIndex < len(self._dynamics):
            self._dynamics[partIndex] = True

    '''
    //////////////////////////////
    //
    // HumGrid::setXmlidsPresent -- Indicate that part needs an **xmlid spine.
    '''
    def setXmlIdsPresent(self, partIndex: int) -> None:
        if 0 <= partIndex < len(self._xmlIds):
            self._xmlIds[partIndex] = True

    '''
    //////////////////////////////
    //
    // HumGrid::setFiguredBassPresent -- Indicate that part needs a **fb spine.
    '''
    def setFiguredBassPresent(self, partIndex: int) -> None:
        if 0 <= partIndex < len(self._figuredBass):
            self._figuredBass[partIndex] = True

    '''
    //////////////////////////////
    //
    // HumGrid::setHarmonyPresent -- Indicate that part needs a **harm spine.
    '''
    def setHarmonyPresent(self, partIndex: int) -> None:
        if 0 <= partIndex < len(self._harmony):
            self._harmony[partIndex] = True

    '''
    //////////////////////////////
    //
    // HumGrid::setHarmonyCount -- part size hardwired to 100 for now.
    '''
    def setHarmonyCount(self, partIndex: int, newCount: int) -> None:
        if 0 <= partIndex < len(self._harmonyCount):
            self._harmonyCount[partIndex] = newCount

    '''
    //////////////////////////////
    //
    // HumGrid::reportVerseCount --
        What is actually stored is max verseCount for part/staff seen so far
    '''
    def reportVerseCount(self, partIndex: int, staffIndex: int, newCount: int) -> None:
        if newCount <= 0:
            return  # won't be bigger than max so far

        staffNumber: int = staffIndex + 1
        partSize: int = len(self._verseCount)
        if partIndex >= partSize:
            for _ in range(partSize, partIndex + 1):
                self._verseCount.append([])

        staffCount: int = len(self._verseCount[partIndex])
        if staffNumber >= staffCount:
            for _ in range(staffCount, staffNumber + 1):
                self._verseCount[partIndex].append(0)

        if newCount > self._verseCount[partIndex][staffNumber]:
            self._verseCount[partIndex][staffNumber] = newCount

    '''
    //////////////////////////////
    //
    // HumGrid::setVerseCount --
        Overwrites any existing verse count for this part/staff
    '''
    def setVerseCount(self, partIndex: int, staffIndex: int, newCount: int) -> None:
        if 0 <= partIndex < len(self._verseCount):
            staffNumber: int = staffIndex + 1
            if staffNumber <= 0:
                return
            if staffNumber < len(self._verseCount[partIndex]):
                self._verseCount[partIndex][staffNumber] = newCount
            else:
                for _ in range(len(self._verseCount[partIndex]), staffNumber + 1):
                    self._verseCount[partIndex].append(0)
                self._verseCount[partIndex][staffNumber] = newCount

    '''
    //////////////////////////////
    //
    // HumGrid::transferTokens --
    //   default value: startbarnum = 0.
    '''
    def transferTokens(self, outFile: HumdrumFile, interp: str = '**kern') -> bool:
        status: bool = self.buildSingleList()
        if not status:
            return False
        self.expandLocalCommentLayers()
        self.calculateGridDurations()
        # move clefs from start of measure to end of prev measure (skip the first measure)
#         self.adjustClefChanges() # Don't do that. Humdrum don't care.
        self.addNullTokens()
#         self.addInvisibleRestsInFirstTrack() what the heck is this for? It's doing bad stuff.
        self.addMeasureLines()
        self.buildSingleList()  # is this needed a second time?
        self.cleanTempos()
        self.addLastBarline()
        if self.manipulatorCheck():
            self.cleanupManipulators()

        # the following are carefully ordered backward because each one
        # inserts their work at line 0 of outFile
        self.insertPartNames(outFile)
        self.insertStaffIndications(outFile)
        self.insertPartIndications(outFile)
        self.insertExclusiveInterpretationLine(outFile, interp)

        # from here we insert at the end of outFile
        for m, measure in enumerate(self.measures):
            if m == 0:
                status &= measure.transferTokens(outFile, self._recip, firstBar=True)
            else:
                status &= measure.transferTokens(outFile, self._recip)
            if not status:
                break

        self.insertDataTerminationLine(outFile)
        return True

    '''
    //////////////////////////////
    //
    // HumGrid::buildSingleList --
    '''
    def buildSingleList(self) -> bool:
        self._allSlices = []

        for measure in self.measures:
            for gridSlice in measure.slices:
                self._allSlices.append(gridSlice)

        for sliceIdx in range(0, len(self._allSlices) - 1):
            ts1: HumNum = self._allSlices[sliceIdx].timestamp
            ts2: HumNum = self._allSlices[sliceIdx + 1].timestamp
            dur: HumNum = opFrac(ts2 - ts1)
            self._allSlices[sliceIdx].duration = dur

        return len(self._allSlices) > 0

    '''
    //////////////////////////////
    //
    // HumGrid::calculateGridDurations --
    '''
    def calculateGridDurations(self) -> None:

        # the last line has to be calculated from the shortest or
        # longest duration on the line.  Acutally all durations
        # starting on this line must be the same, so just search for
        # the first duration.

        lastSlice: GridSlice = self._allSlices[-1]

        # set to zero in case not a duration type of line:
        lastSlice.duration = opFrac(0)

        if not lastSlice.isNoteSlice:
            return

        for part in lastSlice.parts:
            for staff in part.staves:
                for voice in staff.voices:
                    if voice is None:
                        continue
                    if voice.duration > 0:
                        lastSlice.duration = voice.duration
                        return

    '''
    //////////////////////////////
    //
    // HumGrid::addNullTokens --
    '''
    def addNullTokens(self) -> None:
        # make sure every note has enough '.'s to cover duration
        self.addNullTokensForNoteDurations()

        self.addNullTokensForGraceNotes()
        self.addNullTokensForClefChanges()
        self.addNullTokensForLayoutComments()

        # for debugging only, raises exception if expected voice or token is None
#        self.checkForMissingNullTokens()

        self.checkForNullDataHoles()

    '''
    //////////////////////////////
    //
    // HumGrid::extendDurationToken --
    '''
    def extendDurationToken(self, slicei: int, parti: int, staffi: int, voicei: int) -> None:
        if not 0 <= slicei < len(self._allSlices) - 1:
            return

        thisSlice: GridSlice = self._allSlices[slicei]
        nextSlice: GridSlice = self._allSlices[slicei + 1]
        if not thisSlice.hasSpines:
            # no extensions needed in non-spines slices.
            return

        if thisSlice.isGraceSlice:
            # grace slices are of zero duration; do not extend
            return

        gv: t.Optional[GridVoice] = thisSlice.parts[parti].staves[staffi].voices[voicei]
        if gv is None:
            # STRANGE: voice should not be None
            return

        token: t.Optional[HumdrumToken] = gv.token
        if token is None:
            # STRANGE: token should not be None
            return

        if token.text == '.':
            # null data token so ignore;
            # change this later to add a duration for the null token below
            return

        tokenDur: HumNum = Convert.recipToDuration(token.text)
        currTs: HumNum = thisSlice.timestamp
        nextTs: HumNum = nextSlice.timestamp
        sliceDur: HumNum = opFrac(nextTs - currTs)
        timeLeft: HumNum = opFrac(tokenDur - sliceDur)

        if tokenDur == 0:
            # Do not try to extend tokens with zero duration
            # These are most likely **mens notes.
            return

        ''' debugging
        print('===================', file=sys.stderr)
        print('EXTENDING TOKEN    ', token, file=sys.stderr)
        print('\tTOKEN DUR:       ', tokenDur, file=sys.stderr)
        print('\tTOKEN START:     ', currTs, file=sys.stderr)
        print('\tSLICE DUR:       ', sliceDur, file=sys.stderr)
        print('\tNEXT SLICE START:', nextTs, file=sys.stderr)
        print('\tTIME LEFT:       ', timeLeft, file=sys.stderr)
        print('\t-----------------', file=sys.stderr)
        '''

        if timeLeft != 0:
            # fill in null tokens for the required duration.
            if timeLeft < 0:
                return

            sliceType: t.Optional[SliceType] = None
            gs: t.Optional[GridStaff] = None
            s: int = slicei + 1

            while s < len(self._allSlices) and timeLeft > 0:
                sSlice: GridSlice = self._allSlices[s]
                if not sSlice.hasSpines:
                    s += 1
                    continue

                currTs = nextTs
                nexts: int = 1
                nextsSlice: t.Optional[GridSlice] = None
                while s < len(self._allSlices) - nexts:
                    nextsSlice = self._allSlices[s + nexts]
                    if t.TYPE_CHECKING:
                        assert isinstance(nextsSlice, GridSlice)
                    if not nextsSlice.hasSpines:
                        nexts += 1
                        nextsSlice = None
                        continue
                    break

                if nextsSlice is not None:
                    nextTs = nextsSlice.timestamp
                else:
                    nextTs = opFrac(currTs + sSlice.duration)

                sliceDur = opFrac(nextTs - currTs)
                sliceType = sSlice.sliceType
                gs = sSlice.parts[parti].staves[staffi]
                if gs is None:
                    raise HumdrumInternalError('Strange error6 in extendDurationToken()')

                if sSlice.isGraceSlice:
                    sSlice.duration = opFrac(0)
                elif sSlice.isDataSlice:
                    # if there is already a non-null token here, don't overwrite it,
                    # raise an exception instead.  This should not happen.
                    if voicei < len(gs.voices):
                        vi: t.Optional[GridVoice] = gs.voices[voicei]
                        if vi is not None:
                            vitok: t.Optional[HumdrumToken] = vi.token
                            if vitok is not None:
                                if vitok.text != '.':
                                    raise HumdrumInternalError(
                                        f'Note ({token.text}) duration overlaps next note '
                                        + f'in voice ({vitok.text})'
                                    )
                    gs.setNullTokenLayer(voicei, sliceType, sliceDur)
                    timeLeft = opFrac(timeLeft - sliceDur)
                elif sSlice.isInvalidSlice:
                    print(f'THIS IS AN INVALID SLICE({s}) {sSlice}', file=sys.stderr)
                else:
                    # store a null token for the non-data slice, but probably skip
                    # if there is a token already there (such as a clef-change).
                    if voicei < len(gs.voices) and gs.voices[voicei] is not None:
                        # there is already a token here, so do not replace it.
                        pass
                    else:
                        gs.setNullTokenLayer(voicei, sliceType, sliceDur)

                s += 1
                if s == len(self._allSlices) - 1:
                    self._allSlices[s].duration = timeLeft

        # walk through zero-dur items and fill them in, but stop at
        # a token (likely a grace note which should not be erased)

    '''
    //////////////////////////////
    //
    // HumGrid::addNullTokensForGraceNotes -- Avoid grace notes at
    //     starts of measures from contracting the subspine count.
    '''
    def addNullTokensForGraceNotes(self) -> None:
        # add null tokens for grace notes in other voices
        self._addNullTokensForSliceType(SliceType.GraceNotes)

    '''
    //////////////////////////////
    //
    // HumGrid::addNullTokensForLayoutComments -- Avoid layout in multi-subspine
    //     regions from contracting to a single spine.
    '''
    def addNullTokensForLayoutComments(self) -> None:
        # add null tokens for layout comments in other voices
        self._addNullTokensForSliceType(SliceType.Layouts)

    '''
    //////////////////////////////
    //
    // HumGrid::addNullTokensForClefChanges -- Avoid clef in multi-subspine
    //     regions from contracting to a single spine.
    '''
    def addNullTokensForClefChanges(self) -> None:
        # add null tokens for clef changes in other voices
        self._addNullTokensForSliceType(SliceType.Clefs)

    '''
        _addNullTokensForSliceType
    '''
    def _addNullTokensForSliceType(self, sliceType: SliceType) -> None:
        # add null tokens in other voices in slices of this type
        for i, theSlice in enumerate(self._allSlices):
            if theSlice.sliceType != sliceType:
                continue

            # theSlice is of the sliceType we are looking for.
            # Find the last note and next note.
            lastNote: t.Optional[GridSlice] = None
            nextNote: t.Optional[GridSlice] = None

            for j in range(i + 1, len(self._allSlices)):
                if self._allSlices[j].isNoteSlice:
                    nextNote = self._allSlices[j]
                    break

            if nextNote is None:
                continue

            for j in reversed(range(0, i)):  # starts at i-1, ends at 0
                if self._allSlices[j].isNoteSlice:
                    lastNote = self._allSlices[j]
                    break

            if lastNote is None:
                continue

            self._fillInNullTokensForSlice(theSlice, lastNote, nextNote)

    '''
        _fillInNullTokensForSlice fills in null tokens in a slice to avoid
            contracting to a single spine
    '''
    @staticmethod
    def _fillInNullTokensForSlice(theSlice: GridSlice,
                                  lastSpined: GridSlice,
                                  nextSpined: GridSlice) -> None:
        nullChar: str = theSlice.nullTokenStringForSlice()

        for p, part in enumerate(theSlice.parts):
            for s, staff in enumerate(part.staves):
                lastCount: int = len(lastSpined.parts[p].staves[s].voices)
                nextCount: int = len(nextSpined.parts[p].staves[s].voices)
                thisCount: int = len(theSlice.parts[p].staves[s].voices)

                lastCount = max(lastCount, 1)
                nextCount = max(nextCount, 1)

                # If spined slices are expanding or contracting, do
                # not try to adjust the slice between them.
                # These will get filled in properly during manipulator
                # processing.
                if lastCount == nextCount:
                    # Extend the array of voices to match the surrounding voice count.
                    for _ in range(0, lastCount - thisCount):
                        staff.voices.append(None)

                # But no matter what, fill in any missing voices and/or tokens
                # with nullChar.
                for v, voice in enumerate(staff.voices):
                    if voice is None:
                        staff.voices[v] = GridVoice(nullChar, 0)
                    elif voice.token is None:
                        voice.token = HumdrumToken(nullChar)

    def addNullTokensForNoteDurations(self) -> None:
        # make sure every note has enough null tokens after it to cover
        # its entire duration.  This is critical to do before manipulator
        # checking, so that spines don't get merged in the middle of a
        # note's duration.
        for i, gridSlice in enumerate(self._allSlices):
            if not gridSlice.isNoteSlice:
                continue

            for p, part in enumerate(gridSlice.parts):
                for s, staff in enumerate(part.staves):
                    for v, voice in enumerate(staff.voices):
                        if voice is None:
                            # in theory should not happen
                            continue
                        if voice.isNull:
                            continue

                        # found a note/rest which should have a non-zero
                        # duration that needs to be extended through the
                        # an appropriate number of slices to cover the
                        # note's duration (by adding '.' tokens).
                        self.extendDurationToken(i, p, s, v)

    '''
    //////////////////////////////
    //
    // HumGrid::adjustClefChanges -- If a clef change starts at the
    //     beginning of a measure, move it to before the measure (unless
    //     the measure has zero duration).
    def adjustClefChanges(self) -> None:
        for i in range(1, len(self.measures)):
            thisMeasure: GridMeasure = self.measures[i]
            prevMeasure: GridMeasure = self.measures[i-1]

            firstSliceOfThisMeasure: GridSlice = None
            if thisMeasure.slices:
                firstSliceOfThisMeasure = thisMeasure.slices[0]

            if firstSliceOfThisMeasure is None:
                print(f'Warning: GridSlice is None in GridMeasure[{i}]', file=sys.stderr)
                continue
            if not firstSliceOfThisMeasure.parts:
                print(f'Warning: GridSlice is empty in GridMeasure[{i}]', file=sys.stderr)
                continue
            if not firstSliceOfThisMeasure.isClefSlice:
                continue

            # move clef to end of previous measure
            thisMeasure.slices.pop(0)
            prevMeasure.slices.append(firstSliceOfThisMeasure)
    '''

    def checkForMissingNullTokens(self, sliceType: t.Optional[SliceType] = None) -> None:
        for i, gridSlice in enumerate(self._allSlices):
            if sliceType is not None:
                if not gridSlice.isSliceOfType(sliceType):
                    continue
            for p, part in enumerate(gridSlice.parts):
                for s, staff in enumerate(part.staves):
                    for v, voice in enumerate(staff.voices):
                        if voice is None:
                            raise HumdrumInternalError(
                                f'voice is None: i,p,s,v = {i},{p},{s},{v}'
                            )
                        if voice.token is None:
                            raise HumdrumInternalError(
                                f'voice.token is None: i,p,s,v = {i},{p},{s},{v}'
                            )

    '''
    //////////////////////////////
    //
    // HumGrid::checkForNullDataHoles -- identify any spots in the grid which are NULL
    //     pointers and allocate invisible rests for them by finding the next
    //     durational item in the particular staff/layer.
    '''
    def checkForNullDataHoles(self) -> None:
        for i, gridSlice in enumerate(self._allSlices):
            if not gridSlice.isNoteSlice:
                continue

            for p, part in enumerate(gridSlice.parts):
                for s, staff in enumerate(part.staves):
                    for v, voice in enumerate(staff.voices):
                        if voice is not None:
                            continue

                        voice = GridVoice()
                        staff.voices[v] = voice

                        # Calculate duration of void by searching
                        # for the next non-null voice in the current part/staff/voice
                        duration: HumNum = gridSlice.duration

                        for q in range(i + 1, len(self._allSlices)):
                            slicep: GridSlice = self._allSlices[q]
                            if not slicep.isNoteSlice:
                                # or isDataSlice?
                                continue
                            if p >= len(slicep.parts) - 1:
                                continue
                            pp: GridPart = slicep.parts[p]
                            if s >= len(pp.staves) - 1:
                                continue
                            sp: GridStaff = pp.staves[s]
                            if v >= len(sp.voices) - 1:
                                # Found a data line with no data at given voice, so
                                # add slice duration to cumulative duration.
                                duration = opFrac(duration + slicep.duration)
                                continue
                            vp: t.Optional[GridVoice] = sp.voices[v]
                            if vp is None:
                                # found another void spot which should be dealt with later
                                break

                            # There is a token at the same part/staff/voice position.
                            # Maybe check if a null token, but if not a null token,
                            # then break here also.
                            break

                        recip: str = Convert.durationToRecip(duration)
                        # ggg @ marker is added to keep track of them for more debugging
                        recip += 'ryy@'
                        voice.token = HumdrumToken(recip)

    '''
    //////////////////////////////
    //
    // HumGrid::addInvisibleRestsInFirstTrack --  If there are any
    //    timing gaps in the first track of a **kern spine, then
    //    fill in with invisible rests.
    '''
    def addInvisibleRestsInFirstTrack(self) -> None:
        nextEvent: t.List[t.List[GridSlice]] = []
        lastSlice: GridSlice = self._allSlices[-1]
        self.setPartStaffDimensions(nextEvent, lastSlice)

        # loop backward over all the slices
        for i, gridSlice in enumerate(reversed(self._allSlices)):
            if not gridSlice.isNoteSlice:
                continue

            for p, part in enumerate(gridSlice.parts):
                for s, staff in enumerate(part.staves):
                    if not staff.voices:
                        # cerr << "EMPTY STAFF VOICE WILL BE FILLED IN LATER!!!!" << endl;
                        continue

                    if staff.voices[0] is None:
                        # in theory should not happen
                        continue

                    # no loop over voices... we're only interested in voice[0] ("first track")
                    gv0: GridVoice = staff.voices[0]
                    if gv0.isNull:
                        continue

                    # Found a note/rest.  Check if its duration matches
                    # the next non-null data token.  If not, then add
                    # an invisible rest somewhere between the two

                    # first check to see if the previous item is a
                    # NULL.  If so, then store and continue.
                    if nextEvent[p][s] is None:
                        nextEvent[p][s] = gridSlice
                        continue

                    self.addInvisibleRest(nextEvent, i, p, s)

    '''
    //////////////////////////////
    //
    // HumGrid::setPartStaffDimensions --
    '''
    def setPartStaffDimensions(self,
            nextEvent: t.List[t.List[GridSlice]],
            startSlice: GridSlice) -> None:
        nextEvent.clear()
        for gridSlice in self._allSlices:
            if not gridSlice.isNoteSlice:
                continue

            for _ in range(0, len(gridSlice.parts)):
                nextEvent.append([])

            for p, part in enumerate(gridSlice.parts):
                for _ in range(0, len(part.staves)):
                    nextEvent[p].append([])  # type: ignore

                for s in range(0, len(part.staves)):
                    nextEvent[p][s] = startSlice

            break

    '''
    //////////////////////////////
    //
    // HumGrid::addInvisibleRest --
    '''
    def addInvisibleRest(self,
            nextEvent: t.List[t.List[GridSlice]],
            sliceIndex: int,
            p: int,
            s: int) -> None:
        ending: t.Optional[GridSlice] = nextEvent[p][s]
        if ending is None:
            print('Not handling this case yet at end of data.', file=sys.stderr)
            return

        endTime: HumNum = ending.timestamp
        starting: GridSlice = self._allSlices[sliceIndex]
        startTime: HumNum = starting.timestamp
        if len(starting.parts[p].staves[s].voices) == 0:
            print('missing voice in addInvisibleRest', file=sys.stderr)
            return

        voice0: t.Optional[GridVoice] = starting.parts[p].staves[s].voices[0]
        if voice0 is None:
            print('voice0 is None in addInvisibleRest', file=sys.stderr)
            return
        token: t.Optional[HumdrumToken] = voice0.token
        if token is None:
            print('voice0.token is None in addInvisibleRest', file=sys.stderr)
            return

        duration: HumNum = Convert.recipToDuration(token.text)
        if duration == 0:
            # Do not deal with zero duration items (maybe **mens data)
            return

        difference: HumNum = opFrac(endTime - startTime)
        gap: HumNum = opFrac(difference - duration)
        if gap == 0:
            # nothing to do
            nextEvent[p][s] = starting
            return

        target: HumNum = opFrac(startTime + duration)

        kern: str = Convert.durationToRecip(gap)
        kern += 'ryy'

        for i in range(sliceIndex + 1, len(self._allSlices)):
            gridSlice: GridSlice = self._allSlices[i]
            if not gridSlice.isNoteSlice:
                continue

            timestamp: HumNum = gridSlice.timestamp
            if timestamp < target:
                continue

            if timestamp > target:
                print('Cannot deal with this slice addition case yet for invisible rests...',
                        file=sys.stderr)
                print(f'\tTIMESTAMP = {timestamp}\t>\t{target}', file=sys.stderr)
                nextEvent[p][s] = starting
                return

            # At timestamp for adding new token.
            staff: GridStaff = self._allSlices[i].parts[p].staves[s]
            if len(staff.voices) > 0 and staff.voices[0] is None:
                # Element is null where an invisible rest should be
                # so allocate space for it.
                staff.voices[0] = GridVoice()
            if len(staff.voices) > 0:
                if t.TYPE_CHECKING:
                    assert staff.voices[0] is not None
                staff.voices[0].token = HumdrumToken(kern)

            break

        # Store the current event in the buffer
        nextEvent[p][s] = starting

    '''
    //////////////////////////////
    //
    // HumGrid::addMeasureLines --

        C++ code puts the barline at the end of the measure, with the next measure's number,
        and does a bunch of extra work to figure out the initial barline (if necessary).
        We will count on music21 getting the initial barline right, so we just put the
        barline at the beginning of the measure.  This also means we don't have to add 1
        to the measure number, which is good, because in music21 it's a string (might have
        an alphabetic suffix, like '124a').
    '''
    def addMeasureLines(self) -> None:
        for m, measure in enumerate(self.measures):
            firstSpined: t.Optional[GridSlice] = measure.firstSpinedSlice()
            if firstSpined is None:
                # no spined slices in this measure?!? no barline for you.
                continue

            timestamp: HumNum = firstSpined.timestamp
            prevMeasure: t.Optional[GridMeasure] = None
            prevLastSpined: t.Optional[GridSlice] = None
            if m > 0:
                prevMeasure = self.measures[m - 1]
                if len(prevMeasure.slices) > 0:
                    prevLastSpined = prevMeasure.lastSpinedSlice()

            if len(measure.slices) == 0:
                continue

            if measure.duration == 0:
                continue

            hasBarline: bool = False
            for mStyle in measure.measureStylePerStaff:
                if mStyle != MeasureStyle.NoBarline:
                    hasBarline = True
                    break

            if not hasBarline:
                continue

            mslice: GridSlice = GridSlice(measure, timestamp, SliceType.Measures)
            measure.slices.insert(0, mslice)  # barline is first slice in measure

            partCount: int = len(firstSpined.parts)
            staffIndex: int = 0
            for p in range(0, partCount):
                part = GridPart()
                mslice.parts.append(part)
                staffCount: int = len(firstSpined.parts[p].staves)
                for s in range(0, staffCount):
                    staff = GridStaff()
                    part.staves.append(staff)

                    # Insert the minimum number of barlines based on the
                    # voices in the current and previous measure.
                    # The idea here is that if there is a transition at the
                    # barline from more spines to less, or less spines to more,
                    # the manipulator(s) should be inserted on the "more" side
                    # of the barline.
                    voiceCount: int = len(firstSpined.parts[p].staves[s].voices)
                    prevVoiceCount: int = 1  # default, if there is no previous measure
                    if prevLastSpined is not None:
                        prevVoiceCount = len(prevLastSpined.parts[p].staves[s].voices)

                    voiceCount = min(voiceCount, prevVoiceCount)

                    if voiceCount == 0:
                        voiceCount = 1

                    for _ in range(0, voiceCount):
                        token: t.Optional[str] = self.createBarToken(measure, staffIndex)
                        if token is None:
                            # Humdrum can't have a mixture of barlines and "no barline", so
                            # instead of "no barline", create an invisible barline.
                            token = self.createInvisibleBarToken(measure, staffIndex)
                        if token is not None:
                            gv: GridVoice = GridVoice(token, 0)
                            staff.voices.append(gv)

                    staffIndex += 1


    '''
    //////////////////////////////
    //
    // HumGrid::addLastMeasure --
    '''
    def addLastBarline(self) -> None:
        # add the last barline, which will be only one voice
        # for each part/staff
        if not self.measures:
            return

        measure: GridMeasure = self.measures[-1]

        hasBarline: bool = False
        for mStyle in measure.rightBarlineStylePerStaff:
            if mStyle != MeasureStyle.NoBarline:
                hasBarline = True
                break

        if not hasBarline:
            return

        modelSlice: GridSlice = self.measures[-1].slices[-1]
        if modelSlice is None:
            return

        # probably not the correct timestamp, but probably not important
        # to get correct:
        timestamp: HumNum = modelSlice.timestamp

        mslice: GridSlice = GridSlice(measure, timestamp, SliceType.Measures)
        measure.slices.append(mslice)

        staffIndex: int = 0
        for modelPart in modelSlice.parts:
            part = GridPart()
            mslice.parts.append(part)
            for _ in range(0, len(modelPart.staves)):
                measureStyle: t.Optional[str] = self.getLastBarlineStyle(measure, staffIndex)
                if measureStyle is None:
                    # we can't mix barlines with "no barline", so make an invisible barline
                    measureStyle = '-'
                staff = GridStaff()
                part.staves.append(staff)
                token: HumdrumToken = HumdrumToken('=' + measureStyle)
                voice: GridVoice = GridVoice(token, 0)
                staff.voices.append(voice)
                staffIndex += 1

    '''
    //////////////////////////////
    //
    // HumGrid::createBarToken --
    '''
    def createBarToken(self, measure: GridMeasure, staffIndex: int) -> t.Optional[str]:
        measureStyle: t.Optional[str] = self.getMeasureStyle(measure, staffIndex)
        if measureStyle is None:  # a.k.a. measureStyle == MeasureStyle.NoBarline
            return None

        token: str
        measureNumStr: str = measure.measureNumberString

        if measureNumStr:
            if measureStyle == '=':
                token = '=='
                token += measureNumStr
            elif measureStyle.startswith('=;'):
                token = '=='
                token += measureNumStr
                token += measureStyle[1:]
            else:
                token = '='
                token += measureNumStr
                token += measureStyle
        else:
            token = '='
            token += measureStyle

        return token

    def createInvisibleBarToken(self, measure: GridMeasure, staffIndex: int) -> str:
        measureNumStr: str = measure.measureNumberString
        if measureNumStr:
            return '=' + measureNumStr + '-'
        return '=-'

#     '''
#     //////////////////////////////
#     //
#     // HumGrid::getMetricBarNumbers --
#     '''
#     def getMetricBarNumbers(self) -> [int]:
#         mcount: int = len(self.measures)
#         if mcount == 0:
#             return []
#
#         output: t.List[int] = [None] * mcount
#         mdur: t.List[HumNum] = [None] * mcount  # actual measure duration
#         tsdur: t.List[HumNum] = [None] * mcount # time signature duration
#
#         for m, measure in enumerate(self.measures):
#             mdur[m]  = measure.duration
#             tsdur[m] = measure.timeSigDur
#             if tsdur[m] <= 0: # i.e. was never set
#                 tsdur[m] = mdur[m]
#
#         start: int = 0
#         if mdur[0] == 0:
#             start = 1
#
#         counter: int = 0
#         if mdur[start] == tsdur[start]:
#             self._pickup = False
#             counter += 1
#             # add the initial barline later when creating HumdrumFile
#         else:
#             self._pickup = True
#
#         for m in range(start, len(self.measures)):
#             if m == start and mdur[m] == 0:
#                 output[m] = opFrac(counter-1)
#                 continue
#
#             if mdur[m] == 0:
#                 output[m] = opFrac(-1)
#                 continue
#
#             if m < mcount - 1 and tsdur[m] == tsdur[m+1]:
#                 if mdur[m] + mdur[m+1] == tsdur[m]:
#                     output[m] = opFrac(-1)
#                 else:
#                     output[m] = opFrac(counter)
#                     counter += 1
#             else:
#                 output[m] = opFrac(counter)
#                 counter += 1
#
#         return output

    '''
    //////////////////////////////
    //
    // HumGrid::getBarStyle --
    '''
    @staticmethod
    def getMeasureStyle(measure: GridMeasure, staffIndex: int) -> t.Optional[str]:
        output: t.Optional[str] = Convert.measureStyleToHumdrumBarlineStyleStr(
            measure.measureStyle(staffIndex)
        )
        if output is None:
            return None

        output += Convert.fermataStyleToHumdrumFermataStyleStr(
            measure.fermataStyle(staffIndex)
        )
        return output

    @staticmethod
    def getLastBarlineStyle(measure: GridMeasure, staffIndex: int) -> t.Optional[str]:
        output: t.Optional[str] = Convert.measureStyleToHumdrumBarlineStyleStr(
            measure.rightBarlineStyle(staffIndex)
        )
        if output is None:
            return None

        output += Convert.fermataStyleToHumdrumFermataStyleStr(
            measure.rightBarlineFermataStyle(staffIndex)
        )
        return output

    '''
    //////////////////////////////
    //
    // HumGrid::cleanTempos --
    '''
    def cleanTempos(self) -> None:
        for gridSlice in self._allSlices:
            if gridSlice.isTempoSlice:
                self._cleanTempoSlice(gridSlice)

    @staticmethod
    def _cleanTempoSlice(tempoSlice: GridSlice) -> None:
        token: t.Optional[HumdrumToken] = None

        # find first real tempo token
        for part in tempoSlice.parts:
            for staff in part.staves:
                for voice in staff.voices:
                    if voice is None:
                        continue
                    token = voice.token
                    if token is not None:
                        break
                if token is not None:
                    break
            if token is not None:
                break

        if token is None:
            return

        # if there are any missing tokens, fill them in with the one we found
        for part in tempoSlice.parts:
            for staff in part.staves:
                for voice in staff.voices:
                    if voice is None:
                        continue
                    if voice.token is None:
                        voice.token = token

    def makeFakeBarlineSlice(
        self,
        measure: GridMeasure,
        timestamp: HumNumIn,
        voicesPerStaff: int = 1,
        matchVoicesToSlice: t.Optional[GridSlice] = None
    ) -> GridSlice:
        fakeSlice: GridSlice = GridSlice(measure, timestamp, SliceType.Measures)

        staffIndex: int = 0
        for p in range(0, self.partCount):
            part = GridPart()
            fakeSlice.parts.append(part)
            for s in range(0, self.staffCount(p)):
                staff = GridStaff()
                part.staves.append(staff)

                if matchVoicesToSlice is not None:
                    thisVoiceCount = len(matchVoicesToSlice.parts[p].staves[s].voices)
                else:
                    thisVoiceCount = voicesPerStaff

                if thisVoiceCount == 0:
                    thisVoiceCount = 1

                for _ in range(0, thisVoiceCount):
                    token: str = self.createInvisibleBarToken(measure, staffIndex)
                    gv: GridVoice = GridVoice(token, 0)
                    staff.voices.append(gv)

                staffIndex += 1

        return fakeSlice

    '''
    //////////////////////////////
    //
    // HumGrid::manipulatorCheck --
        returns True if any manipulators were added
    '''
    def manipulatorCheck(self) -> bool:
        # We may need to make a fake starting barline for the first measure, and/or a fake
        # ending barline for the last measure. This is so that if we start without a barline
        # (or end without a barline), we'll still split and merge appropriately before the
        # first line of the first measure/after the last line of the last measure.
        fakeFirstSlice: t.Optional[GridSlice] = None
        fakeLastSlice: t.Optional[GridSlice] = None

        # check if we need fakeFirstSlice
        for measure in self.measures:
            if not measure.slices:
                continue

            if not measure.slices[0].isMeasureSlice:
                # we need a fake first slice
                fakeFirstSlice = self.makeFakeBarlineSlice(
                    measure, measure.slices[0].timestamp, voicesPerStaff=1
                )

            # all done, either way
            break

        # check if we need fakeLastSlice
        for m in reversed(range(0, len(self.measures))):
            measure = self.measures[m]
            if not measure.slices:
                continue

            if not measure.slices[-1].isMeasureSlice:
                # we need a fake last slice
                fakeLastSlice = self.makeFakeBarlineSlice(
                    measure, measure.slices[-1].timestamp, voicesPerStaff=1
                )

            # all done, either way
            break

        manipulator: t.Optional[GridSlice]
        lastSpinedLine: t.Optional[GridSlice] = None
        output: bool = False

        startNextMeasureAtSlice1: bool = False
        if fakeFirstSlice is not None:
            firstSpinedLine: t.Optional[GridSlice] = self.getNextSpinedLine(slicei=-1, measurei=0)
            manipulator = self.manipulatorCheckTwoSlices(fakeFirstSlice, firstSpinedLine)
            if manipulator is not None:
                output = True
                measure.slices.insert(0, manipulator)
                startNextMeasureAtSlice1 = True

        for m, measure in enumerate(self.measures):
            if not measure.slices:
                continue

            # This is a while loop instead of a for loop because we're
            # carefully inserting into the list we are iterating over,
            # and we have to do the iteration by hand to have that kind
            # of control.
            i: int = 0
            if startNextMeasureAtSlice1:
                # step over the manipulator we inserted at the start
                i = 1
                startNextMeasureAtSlice1 = False

            while True:
                if i >= len(measure.slices):  # not in while; len(measure.slices) may have changed
                    break

                slice1: GridSlice = measure.slices[i]
                if not slice1.hasSpines:
                    # Don't monitor manipulators on no-spined lines.
                    i += 1
                    continue

                lastSpinedLine = slice1

                slice2: t.Optional[GridSlice] = self.getNextSpinedLine(slicei=i, measurei=m)
                if slice2 is not None:
                    lastSpinedLine = slice2

                manipulator = self.manipulatorCheckTwoSlices(slice1, slice2)
                if manipulator is None:
                    i += 1
                    continue

                output = True
                measure.slices.insert(i + 1, manipulator)
                i += 2  # skip over the new manipulator line (expand it later)

            # one last check, if there's a fakeLastSlice
            if fakeLastSlice is not None:
                manipulator = self.manipulatorCheckTwoSlices(lastSpinedLine, fakeLastSlice)
                if manipulator is not None:
                    output = True
                    measure.slices.append(manipulator)

        return output

    '''
    //////////////////////////////
    //
    // HumGrid::getNextSpinedLine -- Find next spined GridSlice.
    '''
    def getNextSpinedLine(self, slicei: int, measurei: int) -> t.Optional[GridSlice]:
        measure: GridMeasure = self.measures[measurei]
        nextOne: int = slicei + 1

        while nextOne != len(measure.slices):
            if measure.slices[nextOne].hasSpines:
                break
            nextOne += 1

        if nextOne != len(measure.slices):
            return measure.slices[nextOne]

        # Check against all the slices in the next measure as well
        measurei += 1
        if measurei >= len(self.measures):
            # end of data, so nothing to adjust with
            # but this should never happen in general
            return None

        measure = self.measures[measurei]
        nextOne = 0
        while nextOne != len(measure.slices):
            if measure.slices[nextOne].hasSpines:
                return measure.slices[nextOne]
            nextOne += 1

        return None

    '''
    // HumGrid::manipulatorCheck -- Look for differences in voice/layer count
    //   for each part/staff pairing between adjacent lines.  If they do not match,
    //   then add spine manipulator line to Grid between the two lines.
    '''
    def manipulatorCheckTwoSlices(self,
            ice1: t.Optional[GridSlice],
            ice2: t.Optional[GridSlice]
    ) -> t.Optional[GridSlice]:
        if ice1 is None:
            return None

        if ice2 is None:
            return None

        if not ice1.hasSpines:
            return None

        if not ice2.hasSpines:
            return None

        needManip: bool = False
        p1Count: int = len(ice1.parts)
        p2Count: int = len(ice2.parts)
        if p1Count != p2Count:
            print('Warning: Something weird happened here', file=sys.stderr)
            print(f'p1Count = {p1Count}', file=sys.stderr)
            print(f'p2Count = {p2Count}', file=sys.stderr)
            print(f'ICE1 = {ice1}', file=sys.stderr)
            print(f'ICE2 = {ice2}', file=sys.stderr)
            print('p1Count and p2Count should be the same', file=sys.stderr)
            return None

        for part1, part2 in zip(ice1.parts, ice2.parts):
            s1Count: int = len(part1.staves)
            s2Count: int = len(part2.staves)
            if s1Count != s2Count:
                print('Warning: Something weird happened here with staff counts', file=sys.stderr)
                return None

            for staff1, staff2 in zip(part1.staves, part2.staves):
                v1Count: int = len(staff1.voices)
                # the voice count always must be at least 1.  This case
                # is related to inserting clefs in other parts.
                v1Count = max(v1Count, 1)

                v2Count: int = len(staff2.voices)
                v2Count = max(v2Count, 1)

                if v1Count == v2Count:
                    continue

                needManip = True
                break

            if needManip:
                break

        if not needManip:
            return None

        # build manipulator line (which will be expanded further if adjacent
        # staves have *v manipulators.

        mslice: GridSlice = GridSlice(ice1.measure, ice2.timestamp, SliceType.Manipulators)

        mslice.parts = []
        for p, (part1, part2) in enumerate(zip(ice1.parts, ice2.parts)):
            mpart = GridPart()
            mslice.parts.append(mpart)
            mpart.staves = []
            for s, (staff1, staff2) in enumerate(zip(part1.staves, part2.staves)):
                mstaff = GridStaff()
                mpart.staves.append(mstaff)
                v1Count = len(staff1.voices)
                v2Count = len(staff2.voices)
                # empty spines will be filled in with at least one null token.
                v2Count = max(v2Count, 1)
                v1Count = max(v1Count, 1)

                if v1Count == v2Count:
                    # no manipulation here: null token
                    token = self.createHumdrumToken('*', p, s)
                    voice = GridVoice(token, 0)
                    mstaff.voices.append(voice)
                elif v1Count < v2Count:
                    # need to grow
                    grow: int = v2Count - v1Count
                    if v2Count == 2 * v1Count:
                        # all subspines split
                        for _ in range(0, v1Count):
                            token = self.createHumdrumToken('*^', p, s)
                            voice = GridVoice(token, 0)
                            mstaff.voices.append(voice)
                    elif v1Count > 0 and grow > 2 * v1Count:
                        # too large to split all at the same time, deal with later
                        for _ in range(0, v1Count - 1):
                            token = self.createHumdrumToken('*^', p, s)
                            voice = GridVoice(token, 0)
                            mstaff.voices.append(voice)
                        extra: int = v2Count - (v1Count - 1) * 2
                        if extra > 2:
                            token = self.createHumdrumToken('*^' + str(extra), p, s)
                        else:
                            token = self.createHumdrumToken('*^', p, s)
                        voice = GridVoice(token, 0)
                        mstaff.voices.append(voice)
                    else:
                        # only split spines at end of list
                        doubled: int = v2Count - v1Count
                        notDoubled: int = v1Count - doubled
                        for _ in range(0, notDoubled):
                            token = self.createHumdrumToken('*', p, s)
                            voice = GridVoice(token, 0)
                            mstaff.voices.append(voice)

                        if doubled > 1:
                            token = self.createHumdrumToken('*^' + str(doubled + 1), p, s)
                        else:
                            token = self.createHumdrumToken('*^', p, s)
                        voice = GridVoice(token, 0)
                        mstaff.voices.append(voice)
                elif v1Count > v2Count:
                    # need to shrink
                    shrink: int = v1Count - v2Count + 1
                    notShrink: int = v1Count - shrink
                    for _ in range(0, notShrink):
                        token = self.createHumdrumToken('*', p, s)
                        voice = GridVoice(token, 0)
                        mstaff.voices.append(voice)
                    for _ in range(0, shrink):
                        token = self.createHumdrumToken('*v', p, s)
                        voice = GridVoice(token, 0)
                        mstaff.voices.append(voice)

        return mslice

    '''
    //////////////////////////////
    //
    // HumGrid::createHumdrumToken --
    '''
    @staticmethod
    def createHumdrumToken(tok: str, _pindex: int, _sindex: int) -> HumdrumToken:
        token: str = tok
        # token += ':' + str(_pindex) + ',' + str(_sindex)
        output: HumdrumToken = HumdrumToken(token)
        return output

    '''
    //////////////////////////////
    //
    // HumGrid::cleanupManipulators --
    '''
    def cleanupManipulators(self) -> None:
        currSlice: t.Optional[GridSlice] = None
        lastSlice: t.Optional[GridSlice] = None
        for measure in self.measures:
            # This is a while loop instead of a for loop because we're
            # carefully inserting into the list we are iterating over,
            # and we have to do the iteration by hand to have that kind
            # of control.
            i: int = 0
            while i < len(measure.slices):
                lastSlice = currSlice
                currSlice = measure.slices[i]
                if currSlice.sliceType != SliceType.Manipulators:
                    if lastSlice is not None and lastSlice.sliceType != SliceType.Manipulators:
                        self.matchVoices(currSlice, lastSlice)
                    i += 1
                    continue

                if lastSlice is not None and lastSlice.sliceType != SliceType.Manipulators:
                    self.matchVoices(currSlice, lastSlice)

                # check to see if manipulator needs to be split into
                # multiple lines.
                newSlices: t.List[GridSlice] = self.cleanManipulator(currSlice)
                if newSlices:
                    # BUGFIX: reversed loop because insert(i) reverses
                    for newSlice in reversed(newSlices):
                        measure.slices.insert(i, newSlice)
                i += 1

    '''
    //////////////////////////////
    //
    // HumGrid::matchVoices --
    '''
    def matchVoices(self, currSlice: GridSlice, lastSlice: GridSlice) -> None:
        if currSlice is None:
            return
        if lastSlice is None:
            return

        # We need to be more general, so figure out the correct nullTokenString
        nullStr: str = currSlice.nullTokenStringForSlice()

        pcount1: int = len(lastSlice.parts)
        pcount2: int = len(currSlice.parts)
        if pcount1 != pcount2:
            return

        for i, (part1, part2) in enumerate(zip(lastSlice.parts, currSlice.parts)):
            scount1: int = len(part1.staves)
            scount2: int = len(part2.staves)
            if scount1 != scount2:
                continue

            for j, (staff1, staff2) in enumerate(zip(part1.staves, part2.staves)):
                vcount1 = len(staff1.voices)
                vcount2 = len(staff2.voices)
                if vcount1 == vcount2:
                    continue

                if vcount2 > vcount1:
                    # strange if it happens
                    continue

                difference: int = vcount1 - vcount2
                for _ in range(0, difference):
                    gv: GridVoice = self.createVoice(nullStr, 'A', 0, i, j)
                    staff2.voices.append(gv)

    '''
    //////////////////////////////
    //
    // HumGrid::createVoice -- create voice with given token contents.
    '''
    @staticmethod
    def createVoice(
            tok: str,
            _post: str,
            _duration: HumNumIn,
            _partIndex: int,
            _staffIndex: int
    ) -> GridVoice:
        token: str = tok
        # token += ':' + _post + ':' + str(_partIndex) + ',' + str(_staffIndex)
        gv: GridVoice = GridVoice(token, 0)
        return gv

    '''
    //////////////////////////////
    //
    // HumGrid::cleanManipulator --
    '''
    def cleanManipulator(self, currSlice: GridSlice) -> t.List[GridSlice]:
        newSlices: t.List[GridSlice] = []
        output: t.Optional[GridSlice] = None

        # deal with *^ manipulators
        output = self.checkManipulatorExpand(currSlice)
        while output is not None:
            newSlices.append(output)
            output = self.checkManipulatorExpand(currSlice)

        # deal with *v manipulators
        output = self.checkManipulatorContract(currSlice)
        while output is not None:
            newSlices.append(output)
            output = self.checkManipulatorContract(currSlice)

        return newSlices

    '''
    //////////////////////////////
    //
    // HumGrid::checkManipulatorExpand -- Check for cases where a spine expands
    //    into sub-spines.
    '''
    def checkManipulatorExpand(self, currSlice: GridSlice) -> t.Optional[GridSlice]:
        needNew: bool = False
        for part in currSlice.parts:
            for staff in part.staves:
                for voice in staff.voices:
                    if voice is None:
                        continue
                    token: t.Optional[HumdrumToken] = voice.token
                    if token is None:
                        continue
                    if token.text.startswith('*^'):
                        if len(token.text) > 2 and token.text[2].isdigit():
                            needNew = True
                            break
                if needNew:
                    break
            if needNew:
                break

        if not needNew:
            return None

        # need to split *^#'s into separate *^

        newManip: GridSlice = GridSlice(currSlice.measure, currSlice.timestamp,
                                        currSlice.sliceType, fromSlice=currSlice)

        for p, part in enumerate(currSlice.parts):
            for s, staff in enumerate(part.staves):
                self.adjustExpansionsInStaff(newManip, currSlice, p, s)

        return newManip

    '''
    //////////////////////////////
    //
    // HumGrid::adjustExpansionsInStaff -- duplicate null
    //   manipulators, and expand large-expansions, such as *^3 into
    //   *^ and *^ on the next line, or *^4 into *^ and *^3 on the
    //   next line.  The "newmanip" will be placed before curr, so
    '''
    def adjustExpansionsInStaff(self, newManip: GridSlice, currSlice: GridSlice,
                                p: int, s: int) -> None:
        newStaff: GridStaff = newManip.parts[p].staves[s]
        curStaff: GridStaff = currSlice.parts[p].staves[s]

        # This is a while loop instead of a for loop because we're
        # carefully inserting into the list we are iterating over,
        # and we have to do the iteration by hand to have that kind
        # of control.
        cv: int = 0
        for _ in range(0, len(curStaff.voices)):  # loops over original range
            curVoice: t.Optional[GridVoice] = curStaff.voices[cv]
            if curVoice is None:
                raise HumdrumInternalError('curVoice is None in adjustExpansionsInStaff')

            if curVoice.token is not None and curVoice.token.text.startswith('*^'):
                if len(curVoice.token.text) > 2 and curVoice.token.text[2].isdigit():
                    # transfer *^ to newmanip and replace with * and *^(n-1) in curr
                    # Convert *^3 to *^ and add ^* to next line, for example
                    # Convert *^4 to *^ and add ^*3 to next line, for example
                    count: int = 0
                    m = re.match(r'^\*\^([\d]+)', curVoice.token.text)
                    if m:
                        count = int(m.group(1))
                    else:
                        print('Error finding expansion number', file=sys.stderr)
                    newStaff.voices.append(curVoice)
                    curVoice.token.text = '*^'
                    newVoice: GridVoice = self.createVoice('*', 'B', 0, p, s)
                    curStaff.voices[cv] = newVoice  # replace curVoice with newVoice
                    if count <= 3:
                        newVoice = GridVoice('*^', 0)
                    else:
                        newVoice = GridVoice('*^' + str(count - 1), 0)
                    curStaff.voices.insert(cv + 1, newVoice)
                    cv += 1
                else:
                    # transfer *^ to newmanip and replace with two * in curr
                    newStaff.voices.append(curVoice)
                    newVoice = self.createVoice('*', 'C', 0, p, s)
                    curStaff.voices[cv] = newVoice
                    newVoice = self.createVoice('*', 'D', 0, p, s)
                    curStaff.voices.insert(cv, newVoice)
                    cv += 1
            else:
                # insert * in newmanip
                newVoice = self.createVoice('*', 'E', 0, p, s)
                newStaff.voices.append(newVoice)
                cv += 1

    '''
    //////////////////////////////
    //
    // HumGrid::checkManipulatorContract -- Will only check for adjacent
    //    *v records across adjacent staves, which should be good enough.
    //    Will not check within a staff, but this should not occur within
    //    MusicXML input data due to the way it is being processed.
    //    The return value is a newly created GridSlice pointer which contains
    //    a new manipulator to add to the file (and the current manipultor
    //    slice will also be modified if the return value is not NULL).
    '''
    def checkManipulatorContract(self, currSlice: GridSlice) -> t.Optional[GridSlice]:
        needNew: bool = False
        init: bool = False
        lastVoice: t.Optional[GridVoice] = None
        staff: GridStaff
        voice: t.Optional[GridVoice]

        for part in reversed(currSlice.parts):
            for staff in reversed(part.staves):
                if not staff.voices:
                    continue
                voice = staff.voices[-1]
                if not init:
                    lastVoice = staff.voices[-1]
                    init = True
                    continue
                if lastVoice is not None and voice is not None:
                    if str(voice.token) == '*v' and str(lastVoice.token) == '*v':
                        needNew = True
                        break
                lastVoice = staff.voices[-1]

            if needNew:
                break

        if not needNew:
            return None

        # need to split *v's from different adjacent staves onto separate lines.
        newManip: GridSlice = GridSlice(currSlice.measure, currSlice.timestamp,
                                        currSlice.sliceType, fromSlice=currSlice)
        lastVoice = None
        lastStaff: t.Optional[GridStaff] = None
        foundNew: bool = False
        lastp: int = 0
        lasts: int = 0
        partSplit: int = -1

        for p in range(len(currSlice.parts) - 1, -1, -1):
            part = currSlice.parts[p]
            for s in range(len(part.staves) - 1, -1, -1):
                staff = part.staves[s]
                voice = staff.voices[-1]
                newStaff: GridStaff = newManip.parts[p].staves[s]
                if lastVoice is not None and voice is not None:
                    if str(voice.token) == '*v' and str(lastVoice.token) == '*v':
                        # splitting the slices at this staff boundary
                        newLastStaff: GridStaff = newManip.parts[lastp].staves[lasts]
                        self.transferMerges(staff, lastStaff, newStaff, newLastStaff, p, s)
                        foundNew = True
                        partSplit = p
                        break
#               else:
#                   if len(staff.voices) > 1:
#                       for j in range(len(newStaff.voices), len(staff.voices)):
#                           vdata: GridVoice = self.createVoice('*', 'F', 0, p, s)
#                           newStaff.voices.append(vdata)
                lastStaff = staff
                lastVoice = lastStaff.voices[-1]
                lastp = p
                lasts = s

            if foundNew:
                # transfer all of the subsequent manipulators forward
                # after the staff/newstaff point in the slice
                if partSplit > 0:
                    self.transferOtherParts(currSlice, newManip, partSplit)
                break

        # fill in any missing voice null interpretation tokens
        self.adjustVoices(currSlice, newManip, partSplit)

        return newManip

    '''
    //////////////////////////////
    //
    // HumGrid::transferMerges -- Move *v spines from one staff to last staff,
    //   and re-adjust staff "*v" tokens to a single "*" token.
    // Example:
    //                 laststaff      staff
    // old:            *v   *v        *v   *v
    // converts to:
    // new:            *v   *v        *    *
    // old:            *              *v   *v
    '''
    def transferMerges(self,
            oldStaff: t.Optional[GridStaff],
            oldLastStaff: t.Optional[GridStaff],
            newStaff: GridStaff,
            newLastStaff: GridStaff,
            pindex: int,
            sindex: int) -> None:

        if oldStaff is None or oldLastStaff is None:
            print('Weird error in HumGrid.transferMerges()', file=sys.stderr)
            return

        # New staves are presumed to be totally empty

        # First create '*' tokens for newStaff slice where there are
        # '*v' in old staff.  All other tokens should be set to '*'.
        for voice in oldStaff.voices:
            if voice is not None and voice.token is not None and voice.token.text == '*v':
                newStaff.voices.append(self.createVoice('*', 'H', 0, pindex, sindex))
            else:
                newStaff.voices.append(self.createVoice('*', 'I', 0, pindex, sindex))

        # Next, all '*v' tokens at end of old previous staff should be
        # transferred to the new previous staff and replaced with
        # a single '*' token.  Non '*v' tokens in the old last staff should
        # be converted to '*' tokens in the new last staff.

        # It may be possible for '*v' tokens to not be only at the end of
        # the list of oldLastStaff tokens, but does not seem possible.

        addedNull: bool = False
        for v, voice in enumerate(oldLastStaff.voices):
            if voice is not None and voice.token is not None and voice.token.text == '*v':
                newLastStaff.voices.append(voice)
                if not addedNull:
                    oldLastStaff.voices[v] = self.createVoice('*', 'J', 0, pindex, sindex)
                    addedNull = True
                else:
                    oldLastStaff.voices[v] = None
            else:
                newLastStaff.voices.append(self.createVoice('*', 'K', 0, pindex, sindex))

        # Go back to the oldLastStaff and chop off all ending Nones
        # * it should never get to zero (there should be at least one '*' left.
        # In theory intermediate Nones should be checked for, and if the
        # exist, then something bad will happen.  But it does not seem
        # possible to have intermediate Nones.
        for voice in reversed(oldLastStaff.voices):
            if voice is None:
                oldLastStaff.voices = oldLastStaff.voices[:-1]

    '''
    //////////////////////////////
    //
    // HumGrid::transferOtherParts -- after a line split due to merges
    //    occurring at the same time.
    '''
    def transferOtherParts(self, oldLine: GridSlice, newLine: GridSlice, maxPart: int) -> None:
        if maxPart >= len(oldLine.parts):
            return

        for i in range(0, maxPart):
            oldLine.parts[i], newLine.parts[i] = newLine.parts[i], oldLine.parts[i]

            # duplicate the voice counts on the old line (needed if there is more
            # than one voice in a staff when splitting a line due to '*v' merging).
            oldPart = oldLine.parts[i]
            newPart = newLine.parts[i]
            for j in range(0, len(oldPart.staves)):
                oldStaff = oldPart.staves[j]
                newStaff = newPart.staves[j]
                adjustment: int = 0
                voices: int = len(newStaff.voices)
                for voice in newStaff.voices:
                    if voice is None or voice.token is None:
                        continue
                    if voice.token.text == '*v':
                        adjustment += 1

                if adjustment > 0:
                    adjustment -= 1
                voices -= adjustment
                oldStaff.voices = []
                for _ in range(0, voices):
                    oldStaff.voices.append(self.createVoice('*', 'Z', 0, i, j))

        for p, (newPart, oldPart) in enumerate(zip(newLine.parts, oldLine.parts)):
            for s, (newStaff, oldStaff) in enumerate(zip(newPart.staves, oldPart.staves)):
                if len(newStaff.voices) >= len(oldStaff.voices):
                    continue

                diff: int = len(oldStaff.voices) - len(newStaff.voices)
                for _ in range(0, diff):
                    newStaff.voices.append(self.createVoice('*', 'G', 0, p, s))

    '''
    //////////////////////////////
    //
    // HumGrid::adjustVoices --
    '''
    def adjustVoices(self, currSlice: GridSlice, newManip: GridSlice, _partSplit: int) -> None:
        for p, (part1, part2) in enumerate(zip(currSlice.parts, newManip.parts)):
            for s, (staff1, staff2) in enumerate(zip(part1.staves, part2.staves)):
                if len(staff1.voices) == 0 and len(staff2.voices) > 0:
                    self.createMatchedVoiceCount(staff1, staff2, p, s)
                elif len(staff2.voices) == 0 and len(staff1.voices) > 0:
                    self.createMatchedVoiceCount(staff2, staff1, p, s)

    '''
    //////////////////////////////
    //
    // HumGrid::createMatchedVoiceCount --
    '''
    def createMatchedVoiceCount(self, snew: GridStaff, sold: GridStaff, p: int, s: int) -> None:
        if len(snew.voices) != 0:
            raise HumdrumInternalError(
                'createMatchedVoiceCount is only for creating a totally new voice list'
            )

        for _ in range(0, len(sold.voices)):
            snew.voices.append(self.createVoice('*', 'N', 0, p, s))

    '''
    //////////////////////////////
    //
    // HumGrid::insertPartNames --
    '''
    def insertPartNames(self, outFile: HumdrumFile) -> None:
        if not self._partNames:
            return

        if not self.measures:
            return
        if not self.measures[0].slices:
            return

        line: HumdrumLine = HumdrumLine()

        if self._recip:
            line.appendToken(HumdrumToken('*'))

        gridSlice: GridSlice = self.measures[0].slices[0]
        for p, part in enumerate(gridSlice.parts):
            text: str = '*'
            pname: str = self._partNames[p]
            if pname:
                text += 'I"' + pname  # *I" is humdrum's instrument name interp
            for s in range(0, len(part.staves)):
                line.appendToken(HumdrumToken(text))
                self.insertSideNullInterpretations(line, p, s)  # insert staff sides
            self.insertSideNullInterpretations(line, p, -1)  # insert part sides
        outFile.insertLine(0, line)  # insert at line 0

    '''
    //////////////////////////////
    //
    // HumGrid::insertSideNullInterpretations --
    '''
    def insertSideNullInterpretations(self, line: HumdrumLine, p: int, s: int) -> None:
        if s < 0:
            # part side info
            if self.hasDynamics(p):
                line.appendToken(HumdrumToken('*'))
            if self.hasFiguredBass(p):
                line.appendToken(HumdrumToken('*'))
            for _ in range(0, self.harmonyCount(p)):
                line.appendToken(HumdrumToken('*'))
        else:
            # staff side info
            for _ in range(0, self.xmlIdCount(p)):  # xmlIdCount is always 0 or 1, but...
                line.appendToken(HumdrumToken('*'))
            for _ in range(0, self.verseCount(p, s)):
                line.appendToken(HumdrumToken('*'))

    '''
    //////////////////////////////
    //
    // HumGrid::insertStaffIndications -- Currently presumes
    //    that the first entry contains spines.  And the first measure
    //    in the HumGrid object must contain a slice.  This is the
    //    MusicXML Part number. (Some parts will contain more than one
    //    staff).
    '''
    def insertStaffIndications(self, outFile: HumdrumFile) -> None:
        if not self.measures:
            return
        if not self.measures[0].slices:
            return

        line: HumdrumLine = HumdrumLine()

        if self._recip:
            line.appendToken(HumdrumToken('*'))

        gridSlice: GridSlice = self.measures[0].slices[0]
        staffCount: int = 0
        part: GridPart
        for part in gridSlice.parts:
            staffCount += len(part.staves)

        for p in reversed(range(0, len(gridSlice.parts))):
            part = gridSlice.parts[p]
            staffNums: t.List[int] = []
            for s in reversed(range(0, len(part.staves))):
                staffNums.append(staffCount)
                text: str = '*staff' + str(staffCount)
                line.appendToken(HumdrumToken(text))
                self.insertSideStaffInfo(line, p, s, [staffCount])  # insert staff sides
                staffCount -= 1
            self.insertSideStaffInfo(line, p, -1, staffNums)  # insert part sides
        outFile.insertLine(0, line)  # insert at line 0

    '''
    //////////////////////////////
    //
    // HumGrid::insertSideStaffInfo --
    '''
    def insertSideStaffInfo(
        self,
        line: HumdrumLine,
        p: int,
        s: int,
        staffNums: t.List[int]  # >1 element if s is negative (i.e. part sides)
    ) -> None:
        text: str
        if s < 0:
            # part side info (no staff markers, except dynamics, which might have *staff1/2)
            if self.hasDynamics(p):
                text = '*staff'
                for i, staffNum in enumerate(reversed(staffNums)):
                    if i > 0:
                        text += '/'
                    text += str(staffNum)
                line.appendToken(HumdrumToken(text))
            if self.hasFiguredBass(p):
                line.appendToken(HumdrumToken('*'))
            for _ in range(0, self.harmonyCount(p)):
                line.appendToken(HumdrumToken('*'))
        else:
            # staff side info (staff markers)
            text = '*'
            if staffNums[0] > 0:
                text = '*staff' + str(staffNums[0])
            for _ in range(0, self.xmlIdCount(p)):
                line.appendToken(HumdrumToken(text))
            for _ in range(0, self.verseCount(p, s)):
                line.appendToken(HumdrumToken(text))

    '''
    //////////////////////////////
    //
    // HumGrid::insertPartIndications -- Currently presumes
    //    that the first entry contains spines.  And the first measure
    //    in the HumGrid object must contain a slice.  This is the
    //    MusicXML Part number. (Some parts will contain more than one
    //    staff).
    '''
    def insertPartIndications(self, outFile: HumdrumFile) -> None:
        if not self.measures:
            return
        if not self.measures[0].slices:
            return

        line: HumdrumLine = HumdrumLine()

        if self._recip:
            line.appendToken(HumdrumToken('*'))

        gridSlice: GridSlice = self.measures[0].slices[0]
        for p in reversed(range(0, len(gridSlice.parts))):
            part: GridPart = gridSlice.parts[p]
            text: str = '*part' + str(p + 1)
            for s in reversed(range(0, len(part.staves))):
                line.appendToken(HumdrumToken(text))
                self.insertSidePartInfo(line, p, s)  # insert staff sides
            self.insertSidePartInfo(line, p, -1)  # insert part sides
        outFile.insertLine(0, line)  # insert at line 0

    '''
    //////////////////////////////
    //
    // HumGrid::insertSidePartInfo --
    '''
    def insertSidePartInfo(self, line: HumdrumLine, p: int, s: int) -> None:
        text: str = '*part' + str(p + 1)
        if s < 0:
            # part side info
            if self.hasDynamics(p):
                line.appendToken(HumdrumToken(text))
            if self.hasFiguredBass(p):
                line.appendToken(HumdrumToken(text))
            for _ in range(0, self.harmonyCount(p)):
                line.appendToken(HumdrumToken(text))
        else:
            # staff side info
            for _ in range(0, self.xmlIdCount(p)):
                line.appendToken(HumdrumToken(text))
            for _ in range(0, self.verseCount(p, s)):
                line.appendToken(HumdrumToken(text))

    '''
    //////////////////////////////
    //
    // HumGrid::insertExclusiveInterpretationLine -- Currently presumes
    //    that the first entry contains spines.  And the first measure
    //    in the HumGrid object must contain a slice.
    '''
    def insertExclusiveInterpretationLine(self, outFile: HumdrumFile, interp: str) -> None:
        if not self.measures:
            return
        if not self.measures[0].slices:
            return

        line: HumdrumLine = HumdrumLine()

        if self._recip:
            line.appendToken(HumdrumToken('**recip'))

        gridSlice: GridSlice = self.measures[0].slices[0]
        for p in reversed(range(0, len(gridSlice.parts))):
            part: GridPart = gridSlice.parts[p]
            for s in reversed(range(0, len(part.staves))):
                line.appendToken(HumdrumToken(interp))
                self.insertExInterpSides(line, p, s)  # insert staff sides
            self.insertExInterpSides(line, p, -1)  # insert part sides
        outFile.insertLine(0, line)  # insert at line 0

    '''
    //////////////////////////////
    //
    // HumGrid::insertExInterpSides --
    '''
    def insertExInterpSides(self, line: HumdrumLine, p: int, s: int) -> None:
        if s < 0:
            # part side info
            if self.hasDynamics(p):
                line.appendToken(HumdrumToken('**dynam'))
            if self.hasFiguredBass(p):
                line.appendToken(HumdrumToken('**fb'))
            for _ in range(0, self.harmonyCount(p)):
                line.appendToken(HumdrumToken('**mxhm'))
        else:
            # staff side info
            for _ in range(0, self.xmlIdCount(p)):
                line.appendToken(HumdrumToken('**xmlid'))
            for _ in range(0, self.verseCount(p, s)):
                line.appendToken(HumdrumToken('**text'))

    '''
    //////////////////////////////
    //
    // HumGrid::insertDataTerminationLine -- Currently presumes
    //    that the last entry contains spines.  And the first
    //    measure in the HumGrid object must contain a slice.
    //    Also need to compensate for *v on previous line.
    '''
    def insertDataTerminationLine(self, outFile: HumdrumFile) -> None:
        if not self.measures:
            return
        if not self.measures[0].slices:
            return

        line: HumdrumLine = HumdrumLine()

        if self._recip:
            line.appendToken(HumdrumToken('*-'))

        gridSlice: GridSlice = self.measures[0].slices[0]
        for p, part in enumerate(gridSlice.parts):
            for s in range(0, len(part.staves)):
                line.appendToken(HumdrumToken('*-'))
                self.insertSideTerminals(line, p, s)  # insert staff sides
            self.insertSideTerminals(line, p, -1)  # insert part sides
        outFile.appendLine(line)

    '''
    //////////////////////////////
    //
    // HumGrid::insertSideTerminals --
    '''
    def insertSideTerminals(self, line: HumdrumLine, p: int, s: int) -> None:
        text: str = '*-'
        if s < 0:
            # part side info
            if self.hasDynamics(p):
                line.appendToken(HumdrumToken(text))
            if self.hasFiguredBass(p):
                line.appendToken(HumdrumToken(text))
            for _ in range(0, self.harmonyCount(p)):
                line.appendToken(HumdrumToken(text))
        else:
            # staff side info
            for _ in range(0, self.xmlIdCount(p)):
                line.appendToken(HumdrumToken(text))
            for _ in range(0, self.verseCount(p, s)):
                line.appendToken(HumdrumToken(text))

    '''
    //////////////////////////////
    //
    // HumGrid::removeRedundantClefChanges -- Will also have to consider
    //		the meter signature.
    def removeRedundantClefChanges(self) -> None:
        # curClef is a list of the current staff on the part:staff.
        curClef: t.List[t.List[str]] = []
        hasDuplicate: bool = False
        for measure in self.measures:
            for clefSlice in measure.slices:
                if not clefSlice.isClefSlice:
                    continue
                allEmpty: bool = True
                for p, part in enumerate(clefSlice.parts):
                    for s, staff in enumerate(part.staves):
                        if len(staff.voices) < 1:
                            continue
                        voice: GridVoice = staff.voices[0]
                        token: HumdrumToken = voice.token
                        if token is None:
                            continue
                        if token.text == '*':
                            continue
                        if 'clef' not in token.text:
                            # something (probably invalid) which is not a clef
                            allEmpty = False
                            continue
                        if p >= len(curClef):
                            for _ in range(len(curClef), p+1):
                                curClef.append([])
                        if s >= len(curClef[p]):
                            # first clef on the staff, so can't be a duplicate
                            for _ in range(len(curClef[p]), s+1):
                                curClef[p].append('')
                            curClef[p][s] = token.text
                            allEmpty = False
                            continue

                        if curClef[p][s] == token.text:
                            # clef is already active, so remove this one
                            hasDuplicate = True
                            voice.token = '*'
                        else:
                            curClef[p][s] = token.text
                            allEmpty = False

                if not hasDuplicate:
                    continue

                # Check the slice to see if it is empty, and delete if so.
                # This algorithm does not consider the GridSide content in
                # the clefSlice.
                if allEmpty:
                    clefSlice.invalidate()
    '''

    '''
    //////////////////////////////
    //
    // HumGrid::expandLocalCommentLayers -- Walk backwards in the
    //   data list, and match the layer count for local comments
    //   to have them match to the next data line.  This is needed
    //   to attach layout parameters properly to data tokens.  Layout
    //   parameters cannot pass through spine manipulator lines, so
    //   this function is necessary to prevent spine manipulators
    //   from orphaning local layout parameter lines.
    //
    //   For now just adjust local layout parameter slices, but maybe
    //   later do all types of local comments.
    '''
    def expandLocalCommentLayers(self) -> None:
        dataSlice: t.Optional[GridSlice] = None
        localSlice: t.Optional[GridSlice] = None
        for gridSlice in self._allSlices:
            if gridSlice.isDataSlice:
                dataSlice = gridSlice
            if gridSlice.isMeasureSlice:
                dataSlice = gridSlice
            # other slice types should be considered as well,
            # but definitely not manipulator slices:
            if gridSlice.isManipulatorSlice:
                dataSlice = gridSlice

            if not gridSlice.isLocalLayoutSlice:
                continue

            localSlice = gridSlice
            if dataSlice is None:
                continue

            self.matchLocalCommentLayers(localSlice, dataSlice)

    '''
    //////////////////////////////
    //
    // HumGrid::matchLayers -- Make sure every staff in both inputs
    //   have the same number of voices.
    '''
    def matchLocalCommentLayers(self, oslice: GridSlice, islice: GridSlice) -> None:
        if len(oslice.parts) != len(islice.parts):
            # something wrong or one of the slices
            # could be a non-spined line
            return

        for opart, ipart in zip(oslice.parts, islice.parts):
            if len(opart.staves) != len(ipart.staves):
                # something that should never happen
                continue

            for ostaff, istaff in zip(opart.staves, ipart.staves):
                self.matchLocalCommentStaffLayers(ostaff, istaff)

    # matchLocalCommentStaffLayers (also originally called HumGrid::matchLayers)
    @staticmethod
    def matchLocalCommentStaffLayers(ostaff: GridStaff, istaff: GridStaff) -> None:
        iVoiceCount: int = len(istaff.voices)
        oVoiceCount: int = len(ostaff.voices)
        if iVoiceCount == oVoiceCount:
            # the voice counts match, so nothing to do.
            return
        if iVoiceCount < oVoiceCount:
            # Ignore potentially strange case
            return

        diff: int = iVoiceCount - oVoiceCount
        for _ in range(0, diff):
            ostaff.voices.append(GridVoice('!', 0))

    '''
    //////////////////////////////
    //
    // HumGrid::setPartName --
    '''
    def setPartName(self, partIndex: int, partName: str) -> None:
        if partIndex < 0:
            return

        if partIndex < len(self._partNames):
            self._partNames[partIndex] = partName
            return

        if partIndex < 100:
            # grow the array and then store name
            for _ in range(len(self._partNames), partIndex + 1):
                self._partNames.append('')
            self._partNames[partIndex] = partName

    '''
    //////////////////////////////
    //
    // HumGrid::getPartName --
    '''
    def getPartName(self, partIndex: int) -> str:
        if partIndex < 0:
            return ''
        if partIndex < len(self._partNames):
            return self._partNames[partIndex]
        return ''
