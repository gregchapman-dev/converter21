# ------------------------------------------------------------------------------
# Name:          HumGrid.py
# Purpose:       HumGrid is an intermediate container for converting into Humdrum
#                syntax.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021 Greg Chapman
# License:       BSD, see LICENSE
# ------------------------------------------------------------------------------
import sys
import re

from converter21.humdrum import HumdrumInternalError
from converter21.humdrum import HumNum
from converter21.humdrum import Convert
from converter21.humdrum import HumdrumToken
from converter21.humdrum import HumdrumLine
from converter21.humdrum import HumdrumFile

#from converter21.humdrum import MeasureStyle
from converter21.humdrum import SliceType
from converter21.humdrum import GridVoice
#from converter21.humdrum import GridSide
from converter21.humdrum import GridStaff
from converter21.humdrum import GridPart
from converter21.humdrum import GridSlice
from converter21.humdrum import GridMeasure


### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

class HumGrid:
    def __init__(self):
        self.measures: [GridMeasure] = []
        self._allSlices: [GridSlice] = []

        # indexed by part (max = 100 parts)
        self._verseCount: [[int]] = []
        for _ in range(0, 100):
            self._verseCount.append([])
        self._harmonyCount: [int] = [0] * 100
        self._dynamics: [bool] = [False] * 100
        self._xmlIds: [bool] = [False] * 100
        self._figuredBass: [bool] = [False] * 100
        self._harmony: [bool] = [False] * 100
        self._partNames: [str] = [] # grows as necessary

        # options:
        self._pickup: bool = False
        self._recip: bool = False # include **recip spine in output
        self._music21Barlines: bool = False # use measure numbers from music21 Measures

    def __str__(self):
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
    def deleteMeasure(self, measureIndex: int):
        self.measures.pop(measureIndex)

    '''
    //////////////////////////////
    //
    // HumGrid::enableRecipSpine --
    '''
    def enableRecipSpine(self):
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
    def hasPickup(self):
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
    // HumGrid::hasDynamics -- Return true if there are any dyanmics for the part.
    '''
    def hasDynamics(self, partIndex: int) -> bool:
        if 0 <= partIndex < len(self._dynamics):
            return self._dynamics[partIndex]
        return False

    '''
    //////////////////////////////
    //
    // HumGrid::hasFiguredBass -- Return true if there is any figured bass for the part.
    '''
    def hasFiguredBass(self, partIndex: int) -> bool:
        if 0 <= partIndex < len(self._figuredBass):
            return self._figuredBass[partIndex]
        return False

    def hasHarmony(self, partIndex: int) -> bool:
        if 0 <= partIndex < len(self._harmony):
            return self._harmony[partIndex]
        return False

    '''
    //////////////////////////////
    //
    // HumGrid::setDynamicsPresent -- Indicate that part needs a **dynam spine.
    '''
    def setDynamicsPresent(self, partIndex: int):
        if 0 <= partIndex < len(self._dynamics):
            self._dynamics[partIndex] = True

    '''
    //////////////////////////////
    //
    // HumGrid::setXmlidsPresent -- Indicate that part needs an **xmlid spine.
    '''
    def setXmlIdsPresent(self, partIndex: int):
        if 0 <= partIndex < len(self._xmlIds):
            self._xmlIds[partIndex] = True

    '''
    //////////////////////////////
    //
    // HumGrid::setFiguredBassPresent -- Indicate that part needs a **fb spine.
    '''
    def setFiguredBassPresent(self, partIndex: int):
        if 0 <= partIndex < len(self._figuredBass):
            self._figuredBass[partIndex] = True

    '''
    //////////////////////////////
    //
    // HumGrid::setHarmonyPresent -- Indicate that part needs a **harm spine.
    '''
    def setHarmonyPresent(self, partIndex: int):
        if 0 <= partIndex < len(self._harmony):
            self._harmony[partIndex] = True

    '''
    //////////////////////////////
    //
    // HumGrid::setHarmonyCount -- part size hardwired to 100 for now.
    '''
    def setHarmonyCount(self, partIndex: int, newCount: int):
        if 0 <= partIndex < len(self._harmonyCount):
            self._harmonyCount[partIndex] = newCount

    '''
    //////////////////////////////
    //
    // HumGrid::reportVerseCount --
        What is actually stored is max verseCount for part/staff seen so far
    '''
    def reportVerseCount(self, partIndex: int, staffIndex: int, newCount: int):
        if newCount <= 0:
            return # won't be bigger than max so far

        staffNumber: int = staffIndex + 1
        partSize = len(self._verseCount)
        if partIndex >= partSize:
            for _ in range(partSize, partIndex+1):
                self._verseCount.append([])

        staffCount = len(self._verseCount[partIndex])
        if staffNumber >= staffCount:
            for _ in range(staffCount, staffNumber+1):
                self._verseCount[partIndex].append(0)

        if newCount > self._verseCount[partIndex][staffNumber]:
            self._verseCount[partIndex][staffNumber] = newCount

    '''
    //////////////////////////////
    //
    // HumGrid::setVerseCount --
        Overwrites any existing verse count for this part/staff
    '''
    def setVerseCount(self, partIndex: int, staffIndex: int, newCount: int):
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
    def transferTokens(self, outFile: HumdrumFile, startBarNum: int = 0, interp: str = '**kern') -> bool:
        status: bool = self.buildSingleList()
        if not status:
            return False
        self.expandLocalCommentLayers()
        self.calculateGridDurations()
        self.addNullTokens()
        self.addInvisibleRestsInFirstTrack()
        self.addMeasureLines()
        self.buildSingleList() # is this needed a second time?
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
        addStartBar: bool = not self.hasPickup and not self._music21Barlines
        for m, measure in enumerate(self.measures):
            if m == 0 and addStartBar:
                status &= measure.transferTokens(outFile, self._recip, addStartBar, startBarNum)
            else:
                status &= measure.transferTokens(outFile, self._recip, False)
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
            for gridSlice in measure:
                self._allSlices.append(gridSlice)

        for sliceIdx in range(0, len(self._allSlices) - 1):
            ts1: HumNum = self._allSlices[sliceIdx].timestamp
            ts2: HumNum = self._allSlices[sliceIdx + 1].timestamp
            dur: HumNum = ts2 - ts1 # whole note units
            self._allSlices[sliceIdx].duration = dur

        return len(self._allSlices) > 0

    '''
    //////////////////////////////
    //
    // HumGrid::calculateGridDurations --
    '''
    def calculateGridDurations(self):

        # the last line has to be calculated from the shortest or
        # longest duration on the line.  Acutally all durations
        # starting on this line must be the same, so just search for
        # the first duration.

        lastSlice = self._allSlices[-1]

        # set to zero in case not a duration type of line:
        lastSlice.duration = HumNum(0)

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
    def addNullTokens(self):
        for i, gridSlice in enumerate(self._allSlices):
            if not gridSlice.isNoteSlice:
                # probably need to deal with grace note slices here
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
                        # duration that needs to be extended to the next
                        # duration in the
                        self.extendDurationToken(i, p, s, v)

        self.addNullTokensForGraceNotes()
        self.adjustClefChanges()
        self.addNullTokensForClefChanges()
        self.addNullTokensForLayoutComments()
        self.checkForNullDataHoles()

    '''
    //////////////////////////////
    //
    // HumGrid::extendDurationToken --
    '''
    def extendDurationToken(self, slicei: int, parti: int, staffi: int, voicei: int):
        if 0 <= slicei < len(self._allSlices) - 1:
            # nothing after this line, so can extend further
            return

        thisSlice: GridSlice = self._allSlices[slicei]
        nextSlice: GridSlice = self._allSlices[slicei + 1]
        if not thisSlice.hasSpines:
            # no extensions needed in non-spines slices.
            return

        if thisSlice.isGraceSlice:
            # grace slices are of zero duration; do not extend
            return

        gv: GridVoice = thisSlice.parts[parti].staves[staffi].voices[voicei]
        token: HumdrumToken = gv.token
        if token is None:
            # STRANGE: token should not be None
            return

        if token.text == '.':
            # null data token so ignore;
            # change this later to add a duration for the null token below
            return

        tokenDur: HumNum = Convert.recipToDuration(token.text)
        currTs: HumNum   = thisSlice.timestamp
        nextTs: HumNum   = nextSlice.timestamp
        sliceDur: HumNum = nextTs - currTs
        timeLeft: HumNum = tokenDur - sliceDur

        if tokenDur == 0:
            # Do not try to extend tokens with zero duration
            # These are most likely **mens notes.
            return

        print('===================')
        print('EXTENDING TOKEN    ', token)
        print('\tTOKEN DUR:       ', tokenDur)
        print('\tTOKEN START:     ', currTs)
        print('\tSLICE DUR:       ', sliceDur)
        print('\tNEXT SLICE START:', nextTs)
        print('\tTIME LEFT:       ', timeLeft)
        print('\t-----------------')

        if timeLeft != 0:
            # fill in null tokens for the required duration.
            if timeLeft < 0:
                return

            sliceType: SliceType = None
            gs: GridStaff = None
            s: int = slicei + 1

            while s < len(self._allSlices) and timeLeft > 0:
                sSlice: GridSlice = self._allSlices[s]
                if not sSlice.hasSpines:
                    s += 1
                    continue

                currTs = nextTs
                nexts: int = 1
                nextsSlice: GridSlice = None
                while s < len(self._allSlices) - nexts:
                    nextsSlice = self._allSlices[s + nexts]
                    if not nextsSlice.hasSpines:
                        nexts += 1
                        nextsSlice = None
                        continue
                    break

                if nextsSlice:
                    nextTs = nextsSlice.timestamp
                else:
                    nextTs = currTs + sSlice.duration

                sliceDur = nextTs - currTs
                sliceType = sSlice.sliceType
                gs = sSlice.parts[parti].staves[staffi]
                if gs is None:
                    raise HumdrumInternalError('Strange error6 in extendDurationToken()')

                if sSlice.isGraceSlice:
                    sSlice.duration = HumNum(0)
                elif sSlice.isDataSlice:
                    gs.setNullTokenLayer(voicei, sliceType, sliceDur)
                    timeLeft =- sliceDur
                elif sSlice.isInvalidSlice:
                    print('THIS IS AN INVALID SLICE({}) {}'.format(s, sSlice))
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
        addNullTokensForSliceType is common code used by addNullTokensForBlah,
            where Blah is GraceNotes, Clefs, LayoutComments
    '''
    def addNullTokensForSliceType(self, sliceType: SliceType):
        # add null tokens in other voices in slices of this type
        lastNote: GridSlice = None
        nextNote: GridSlice = None
        for i, theSlice in enumerate(self._allSlices):
            if theSlice.sliceType != sliceType:
                continue

            # theSlice is of the sliceType we are looking for
            for j in range(i+1, len(self._allSlices)):
                if self._allSlices[j].isNoteSlice:
                    nextNote = self._allSlices[j]
                    break

            if nextNote is None:
                continue

            for j in reversed(range(0, i)): # starts at i-1, ends at 0
                if self._allSlices[j].isNoteSlice:
                    lastNote = self._allSlices[j]
                    break

            if lastNote is None:
                continue

            self._fillInNullTokensForSlice(theSlice, lastNote, nextNote)

    '''
        _fillInNullTokensForSliceType fills in null tokens in a slice to avoid
            contracting to a single spine
    '''
    @staticmethod
    def _fillInNullTokensForSlice(theSlice: GridSlice,
                                  lastNote: GridSlice, nextNote: GridSlice):
        if theSlice is None:
            return
        if lastNote is None:
            return
        if nextNote is None:
            return

        nullChar: str = theSlice.nullTokenStringForSlice()

        for p, part in enumerate(theSlice.parts):
            for s, staff in enumerate(part.staves):
                v1count:  int = len(lastNote.parts[p].staves[s])
                v2count:  int = len(nextNote.parts[p].staves[s])
                theCount: int = len(theSlice.parts[p].staves[s])

                if v1count < 1:
                    v1count = 1
                if v2count < 1:
                    v2count = 1

                if v1count != v2count:
                    # Note slices are expanding or contracting so do
                    # not try to adjust the slice between them.
                    continue

                for _ in range(0, v1count - theCount):
                    gv: GridVoice = GridVoice(nullChar, 0)
                    staff.voices.append(gv)

    '''
    //////////////////////////////
    //
    // HumGrid::addNullTokensForGraceNotes -- Avoid grace notes at
    //     starts of measures from contracting the subspine count.
    '''
    def addNullTokensForGraceNotes(self):
        self.addNullTokensForSliceType(SliceType.GraceNotes)

    '''
    //////////////////////////////
    //
    // HumGrid::addNullTokensForLayoutComments -- Avoid layout in multi-subspine
    //     regions from contracting to a single spine.
    '''
    def addNullTokensForLayoutComments(self):
        self.addNullTokensForSliceType(SliceType.Layouts)

    '''
    //////////////////////////////
    //
    // HumGrid::addNullTokensForClefChanges -- Avoid clef in multi-subspine
    //     regions from contracting to a single spine.
    '''
    def addNullTokensForClefChanges(self):
        self.addNullTokensForSliceType(SliceType.Clefs)

    '''
    //////////////////////////////
    //
    // HumGrid::adjustClefChanges -- If a clef change starts at the
    //     beginning of a measure, move it to before the measure (unless
    //     the measure has zero duration).
    '''
    def adjustClefChanges(self):
        for i in range(1, len(self.measures)):
            thisMeasure: GridMeasure = self.measures[i]
            prevMeasure: GridMeasure = self.measures[i-1]

            firstSliceOfThisMeasure: GridSlice = None
            if thisMeasure.slices:
                firstSliceOfThisMeasure = thisMeasure.slices[0]

            if firstSliceOfThisMeasure is None:
                print('Warning: GridSlice is None in GridMeasure[{}]'.format(i), file=sys.stderr)
                continue
            if not firstSliceOfThisMeasure.parts:
                print('Warning: GridSlice is empty in GridMeasure[{}]'.format(i), file=sys.stderr)
                continue
            if not firstSliceOfThisMeasure.isClefSlice:
                continue

            # move clef to end of previous measure
            thisMeasure.slices.pop(0)
            prevMeasure.append(firstSliceOfThisMeasure)

    '''
    //////////////////////////////
    //
    // HumGrid::checkForNullDataHoles -- identify any spots in the grid which are NULL
    //     pointers and allocate invisible rests for them by finding the next
    //     durational item in the particular staff/layer.
    '''
    def checkForNullDataHoles(self):
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

                        for q in range(i+1, len(self._allSlices)):
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
                                duration += slicep.duration
                                continue
                            vp: GridVoice = sp.voices[v]
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
                        voice.token = recip

    '''
    //////////////////////////////
    //
    // HumGrid::addInvisibleRestsInFirstTrack --  If there are any
    //    timing gaps in the first track of a **kern spine, then
    //    fill in with invisible rests.
    // ggg
    '''
    def addInvisibleRestsInFirstTrack(self):
        nextEvent: [[GridSlice]] = []
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
    def setPartStaffDimensions(self, nextEvent: [[GridSlice]], startSlice: GridSlice):
        nextEvent.clear()
        for gridSlice in self._allSlices:
            if not gridSlice.isNoteSlice:
                continue

            for _ in range(0, len(gridSlice.parts)):
                nextEvent.append([])

            for p, part in enumerate(gridSlice.parts):
                for _ in range(0, len(part.staves)):
                    nextEvent[p].append([])

                for s in range(0, len(part.staves)):
                    nextEvent[p][s] = startSlice

            break

    '''
    //////////////////////////////
    //
    // HumGrid::addInvisibleRest --
    '''
    def addInvisibleRest(self, nextEvent: [[GridSlice]], sliceIndex: int, p: int, s: int):
        ending: GridSlice = nextEvent[p][s]
        if ending is None:
            print('Not handling this case yet at end of data.', file=sys.stderr)
            return

        endTime: HumNum = ending.timestamp
        starting: GridSlice = self._allSlices[sliceIndex]
        startTime: HumNum = starting.timestamp
        token: HumdrumToken = starting.parts[p].staves[s].voices[0].token
        duration: HumNum = Convert.recipToDuration(token.text)
        if duration == 0:
            # Do not deal with zero duration items (maybe **mens data)
            return

        difference: HumNum = endTime - startTime
        gap: HumNum = difference - duration
        if gap == 0:
            # nothing to do
            nextEvent[p][s] = starting
            return

        target: HumNum = startTime + duration

        kern: str = Convert.durationToRecip(gap)
        kern += 'ryy'

        for i in range(sliceIndex+1, len(self._allSlices)):
            gridSlice: GridSlice = self._allSlices[i]
            if not gridSlice.isNoteSlice:
                continue

            timestamp: HumNum = gridSlice.timestamp
            if timestamp < target:
                continue

            if timestamp > target:
                print('Cannot deal with this slice addition case yet for invisible rests...', file=sys.stderr)
                print('\tTIMESTAMP = {}\t>\t{}'.format(timestamp, target), file=sys.stderr)
                nextEvent[p][s] = starting
                return

            # At timestamp for adding new token.
            staff: GridStaff = self._allSlices[i].parts[p].staves[s]
            if len(staff.voices) > 0 and staff.voices[0] is None:
                # Element is null where an invisible rest should be
                # so allocate space for it.
                staff.voices[0] = GridVoice()
            if len(staff.voices) > 0:
                staff.voices[0].token = kern

            break

        # Store the current event in the buffer
        nextEvent[p][s] = starting

    '''
    //////////////////////////////
    //
    // HumGrid::addMeasureLines --
    '''
    def addMeasureLines(self):
        barNums: [int] = []
        if not self._music21Barlines:
            barNums = self.getMetricBarNumbers()

        for m in range(0, len(self.measures) - 1):
            measure = self.measures[m]
            nextMeasure = self.measures[m+1]
            if len(nextMeasure.slices) == 0:
                # next measure is empty for some reason, so give up
                continue

            firstSpined: GridSlice = nextMeasure.firstSpinedSlice()
            timestamp: HumNum = firstSpined.timestamp

            if len(measure.slices) == 0:
                continue

            if measure.duration == 0:
                continue

            mslice: GridSlice = GridSlice(measure, timestamp, SliceType.Measures)
            # what to do when endSlice is None?
            endSlice: GridSlice = measure.lastSpinedSlice() # this has to come before next line
            measure.slices.append(mslice) # this has to come after the previous line
            partCount: int = len(firstSpined.parts)
            for p in range(0, partCount):
                part = GridPart()
                mslice.parts.append(part)
                staffCount: int = len(firstSpined.parts[p].staves)
                for s in range(0, staffCount):
                    staff = GridStaff()
                    part.staves.append(staff)

                    # insert the minimum number of barlines based on the
                    # voices in the current and next measure
                    vcount = len(endSlice.parts[p].staves[s])
                    if firstSpined:
                        nextvcount = len(firstSpined.parts[p].staves[s])
                    else:
                        # perhaps an empty measure?  This will cause problems.
                        nextvcount = 0

                    lcount = vcount
                    if lcount > nextvcount:
                        lcount = nextvcount
                    if lcount == 0:
                        lcount = 1

                    for _ in range(0, lcount):
                        num: int = measure.measureNumber
                        if m < len(barNums) - 1:
                            num = barNums[m+1]
                        token = self.createBarToken(m, num, measure)
                        gv: GridVoice = GridVoice(token, 0)
                        staff.voices.append(gv)

    '''
    //////////////////////////////
    //
    // HumGrid::addLastMeasure --
    '''
    def addLastBarline(self):
        # add the last barline, which will be only one voice
        # for each part/staff
        if not self.measures:
            return

        modelSlice: GridSlice = self.measures[-1].slices[-1]
        if modelSlice is None:
            return

        # probably not the correct timestamp, but probably not important
        # to get correct:
        timestamp: HumNum = modelSlice.timestamp

        measure: GridMeasure = self.measures[-1]
        barStyle: self.getBarStyle(measure)
        mslice: GridSlice = GridSlice(measure, timestamp, SliceType.Measures)
        measure.append(mslice)

        for modelPart in modelSlice.parts:
            part = GridPart()
            mslice.parts.append(part)
            for _ in range(0, len(modelPart.staves)):
                staff = GridStaff()
                part.staves.append(staff)
                token: HumdrumToken = HumdrumToken('=' + barStyle)
                voice: GridVoice = GridVoice(token, 0)
                staff.voices.append(voice)

    '''
    //////////////////////////////
    //
    // HumGrid::createBarToken --
    '''
    def createBarToken(self, _m: int, barNum: int, measure: GridMeasure) -> str:
        token: str = ''
        barStyle: str = self.getBarStyle(measure)
        num: str = ''

        if barNum > 0:
            num = str(barNum)

        if self._music21Barlines:
            # barNum+1 because of the measure number
            # comes from the previous measure.
            if barStyle == '=':
                token = '=='
                token += str(barNum+1) # was str(m+1)
            else:
                token = '='
                token += str(barNum+1) # was str(m+1)
                token += barStyle
        else:
            if barNum > 0:
                if barStyle == '=':
                    token = '=='
                    token += num
                else:
                    token = '='
                    token += num
                    token += barStyle
            else:
                if barStyle == '=':
                    token = '=='
                else:
                    token = '='
                    token += barStyle

        return token

    '''
    //////////////////////////////
    //
    // HumGrid::getMetricBarNumbers --
    '''
    def getMetricBarNumbers(self) -> [int]:
        mcount: int = len(self.measures)
        if mcount == 0:
            return []

        output: [int] = [None] * mcount
        mdur: [HumNum] = [None] * mcount  # actual measure duration
        tsdur: [HumNum] = [None] * mcount # time signature duration

        for m, measure in enumerate(self.measures):
            mdur[m]  = measure.duration
            tsdur[m] = measure.timeSigDur
            if tsdur[m] <= 0: # i.e. was never set
                tsdur[m] = mdur[m]

        start: int = 0
        if mdur[0] == 0:
            start = 1

        counter: int = 0
        if mdur[start] == tsdur[start]:
            self._pickup = False
            counter += 1
            # add the initial barline later when creating HumdrumFile
        else:
            self._pickup = True

        for m in range(start, len(self.measures)):
            if m == start and mdur[m] == 0:
                output[m] = HumNum(counter-1)
                continue

            if mdur[m] == 0:
                output[m] = HumNum(-1)
                continue

            if m < mcount - 1 and tsdur[m] == tsdur[m+1]:
                if mdur[m] + mdur[m+1] == tsdur[m]:
                    output[m] = HumNum(-1)
                else:
                    output[m] = HumNum(counter)
                    counter += 1
            else:
                output[m] = HumNum(counter)
                counter += 1

        return output

    '''
    //////////////////////////////
    //
    // HumGrid::getBarStyle --
    '''
    @staticmethod
    def getBarStyle(measure: GridMeasure) -> str:
        output: str = ''
        if measure.isDouble:
            output = '||'
        elif measure.isFinal:
            output = '='
        elif measure.isInvisibleBarline:
            output = '-'
        elif measure.isRepeatBoth:
            output = ':|!|:'
        elif measure.isRepeatBackward:
            output = ':|!'
        elif measure.isRepeatForward:
            output = '!|:'
        return output

    '''
    //////////////////////////////
    //
    // HumGrid::cleanTempos --
    '''
    def cleanTempos(self):
        for gridSlice in self._allSlices:
            if gridSlice.isTempoSlice:
                self._cleanTempoSlice(gridSlice)

    @staticmethod
    def _cleanTempoSlice(tempoSlice: GridSlice):
        token: HumdrumToken = None

        # find first real tempo token
        for part in tempoSlice.parts:
            for staff in part.staves:
                for voice in staff.voices:
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
                    if voice.token is None:
                        voice.token = token

    '''
    //////////////////////////////
    //
    // HumGrid::manipulatorCheck --
        returns True if any manipulators were added
    '''
    def manipulatorCheck(self) -> bool:
        output: bool = False
        for m, measure in enumerate(self.measures):
            if not measure.slices:
                continue

            skipNextSlice: bool = False
            for i, slice1 in enumerate(measure.slices):
                if skipNextSlice:
                    skipNextSlice = False
                    continue

                if not slice1.hasSpines:
                    # Don't monitor manipulators on no-spined lines.
                    continue

                slice2: GridSlice = self.getNextSpinedLine(i, m)
                manipulator: GridSlice = self.manipulatorCheckTwoSlices(slice1, slice2)
                if manipulator is None:
                    continue

                output = True
                measure.slices.insert(i+1, manipulator)
                skipNextSlice = True # skip over the new manipulator line (expand it later)

        return output

    '''
    //////////////////////////////
    //
    // HumGrid::getNextSpinedLine -- Find next spined GridSlice.
    '''
    def getNextSpinedLine(self, slicei: int, measurei: int) -> GridSlice:
        measure: GridMeasure = self.measures[measurei]
        nextOne: int = slicei+1

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
    def manipulatorCheckTwoSlices(self, ice1: GridSlice, ice2: GridSlice) -> GridSlice:
        if ice1 is None:
            return None

        if ice2 is None:
            return None

        if not ice1.hasSpines:
            return None

        if not ice2.hasSpines:
            return None

        p1Count: int = len(ice1.parts)
        p2Count: int = len(ice2.parts)
        if p1Count != p2Count:
            print('Warning: Something weird happened here', file=sys.stderr)
            print('p1Count = {}'.format(p1Count), file=sys.stderr)
            print('p2Count = {}'.format(p2Count), file=sys.stderr)
            print('ICE1 = {}'.format(ice1), file=sys.stderr)
            print('ICE2 = {}'.format(ice2), file=sys.stderr)
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
                if v1Count < 1:
                    v1Count = 1

                v2Count: int = len(staff2.voices)
                if v2Count < 1:
                    v2Count = 1

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

        p1Count = len(ice1.parts)
        mslice.parts = [None] * p1Count
        for p, (part1, part2) in enumerate(zip(ice1.parts, ice2.parts)):
            mpart = GridPart()
            mslice.parts[p] = mpart
            s1Count = len(part1.staves)
            mpart.staves = [None] * s1Count
            for s, (staff1, staff2) in enumerate(zip(part1, part2)):
                mstaff = GridStaff()
                mpart.staves[s] = mstaff
                v1Count = len(staff1.voices)
                v2Count = len(staff2.voices)
                if v2Count < 1:
                    # empty spines will be filled in with at least one null token.
                    v2Count = 1
                if v1Count < 1:
                    # empty spines will be filled in with at least one null token.
                    v1Count = 1

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
                        for _ in range(0, v1Count-1):
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
                            token = self.createHumdrumToken('*^' + str(doubled+1), p, s)
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
    def cleanupManipulators(self):
        currSlice: GridSlice = None
        lastSlice: GridSlice = None
        for measure in self.measures:
            for i, gridSlice in enumerate(measure.slices):
                lastSlice = currSlice
                currSlice = gridSlice
                if currSlice.sliceType != SliceType.Manipulators:
                    if lastSlice is not None and lastSlice.sliceType != SliceType.Manipulators:
                        self.matchVoices(currSlice, lastSlice)
                    continue

                if lastSlice is not None and lastSlice.sliceType != SliceType.Manipulators:
                    self.matchVoices(currSlice, lastSlice)

                # check to see if manipulator needs to be split into
                # multiple lines.
                newSlices: [GridSlice] = self.cleanManipulator(currSlice)
                if newSlices:
                    for newSlice in newSlices:
                        measure.slices.insert(i, newSlice)

    '''
    //////////////////////////////
    //
    // HumGrid::matchVoices --
    '''
    def matchVoices(self, currSlice: GridSlice, lastSlice: GridSlice):
        if currSlice is None:
            return
        if lastSlice is None:
            return

        pcount1: int = len(currSlice.parts)
        pcount2: int = len(lastSlice.parts)
        if pcount1 != pcount2:
            return

        for i, (part1, part2) in enumerate(zip(currSlice.parts, lastSlice.parts)):
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
                    gv: GridVoice = self.createVoice('*', 'A', 0, i, j)
                    staff2.voices.append(gv)

    '''
    //////////////////////////////
    //
    // HumGrid::createVoice -- create voice with given token contents.
    '''
    @staticmethod
    def createVoice(tok: str, _post: str, _duration: HumNum, _partIndex: int, _staffIndex: int) -> GridVoice:
        token: str = tok
        #token += ':' + _post + ':' + str(_partIndex) + ',' + str(_staffIndex)
        gv: GridVoice = GridVoice(token, 0)
        return gv

    '''
    //////////////////////////////
    //
    // HumGrid::cleanManipulator --
    '''
    def cleanManipulator(self, currSlice: GridSlice):
        newSlices: [GridSlice] = []
        output: GridSlice = None

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
    def checkManipulatorExpand(self, currSlice: GridSlice) -> GridSlice:
        needNew: bool = False
        for part in currSlice.parts:
            for staff in part.staves:
                for voice in staff.voices:
                    token: HumdrumToken = voice.token
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
                                        currSlice.sliceType, currSlice)

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
                                p: int, s: int):
        newStaff: GridStaff = newManip.parts[p].staves[s]
        curStaff: GridStaff = currSlice.parts[p].staves[s]

        for cv, curVoice in enumerate(curStaff.voices):
            token: HumdrumToken = curVoice.token
            if token.text.startswith('*^'):
                if len(token.text) > 2 and token.text[2].isdigit():
                    # transfer *^ to newmanip and replace with * and *^(n-1) in curr
                    # Convert *^3 to *^ and add ^* to next line, for example
                    # Convert *^4 to *^ and add ^*3 to next line, for example
                    count: int = 0
                    m = re.match(r'^\*\^([\d]+)', token.text)
                    if m:
                        count = int(m.group(1))
                    else:
                        print('Error finding expansion number', file=sys.stderr)
                    newStaff.voices.append(curVoice)
                    curVoice.token.text = '*^'
                    newVoice: GridVoice = self.createVoice('*', 'B', 0, p, s)
                    curStaff.voices[cv] = newVoice # replace curVoice with newVoice
                    if count <= 3: # why 3? --gregc
                        newVoice = GridVoice('*^', 0)
                    else:
                        newVoice = GridVoice('*^' + str(count-1), 0)
                    curStaff.voices.insert(cv+1, newVoice)
                else:
                    # transfer *^ to newmanip and replace with two * in curr
                    newStaff.voices.append(curVoice)
                    newVoice = self.createVoice('*', 'C', 0, p, s)
                    curStaff.voices[cv] = newVoice
                    newVoice = self.createVoice('*', 'D', 0, p, s)
                    curStaff.voices.insert(cv, newVoice)
            else:
                # insert * in newmanip
                newVoice = self.createVoice('*', 'E', 0, p, s)
                newStaff.voices.append(newVoice)

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
    def checkManipulatorContract(self, currSlice: GridSlice) -> GridSlice:
        needNew: bool = False
        init: bool = False
        lastVoice: GridVoice = None

        for part in reversed(currSlice.parts):
            for staff in part.staves:
                if not staff.voices:
                    continue
                voice: GridVoice = staff.voices[-1]
                if not init:
                    lastVoice = staff.voices[-1]
                    init = True
                    continue
                if lastVoice is not None:
                    if voice.token.text == '*v' and lastVoice.token.text == '*v':
                        needNew = True
                        break
                lastVoice = staff.voices[-1]

            if needNew:
                break

        if not needNew:
            return None

        # need to split *v's from different adjacent staves onto separate lines.
        newManip: GridSlice = GridSlice(currSlice.measure, currSlice.timestamp,
                                        currSlice.sliceType, currSlice)
        lastVoice = None
        lastStaff: GridStaff = None
        foundNew: bool = False
        lastp: int = 0
        lasts: int = 0
        partSplit: int = -1

        for p, part in enumerate(reversed(currSlice.parts)):
            for s, staff in enumerate(reversed(part.staves)):
                voice: GridVoice = staff.voices[-1]
                newStaff: GridStaff = newManip.parts[p].staves[s]
                if lastVoice is not None:
                    if voice.token.text == '*v' and lastVoice.token.text == '*v':
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
    def transferMerges(self, oldStaff: GridStaff, oldLastStaff: GridStaff,
                             newStaff: GridStaff, newLastStaff: GridStaff,
                             pindex: int, sindex: int):
        if oldStaff is None or oldLastStaff is None:
            print('Weird error in HumGrid.transferMerges()', file=sys.stderr)
            return

        # New staves are presumed to be totally empty

        # First create '*' tokens for newStaff slice where there are
        # '*v' in old staff.  All other tokens should be set to '*'.
        for voice in oldStaff.voices:
            if voice.token.text == '*v':
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
            if voice.token.text == '*v':
                newLastStaff.voices.append(voice)
                if not addedNull:
                    oldLastStaff.voices[v] = self.createVoice('*', 'J', 0, pindex, sindex)
                    addedNull = True
                else:
                    oldLastStaff.voices[v] = None
            else:
                newLastStaff.append(self.createVoice('*', 'K', 0, pindex, sindex))

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
    def transferOtherParts(self, oldLine: GridSlice, newLine: GridSlice, maxPart: int):
        if maxPart >= len(oldLine.voices):
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
                    if voice is None:
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
    def adjustVoices(self, currSlice: GridSlice, newManip: GridSlice, _partSplit: int):
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
    def createMatchedVoiceCount(self, snew: GridStaff, sold: GridStaff, p: int, s: int):
        if len(snew.voices) != 0:
            raise HumdrumInternalError('createMatchedVoiceCount is only for creating a totally new voice list')

        for _ in range(0, len(sold.voices)):
            snew.voices.append(self.createVoice('*', 'N', 0, p, s))

    '''
    //////////////////////////////
    //
    // HumGrid::insertPartNames --
    '''
    def insertPartNames(self, outFile: HumdrumFile):
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
                text += 'I"' + pname # *I" is humdrum's instrument name interp
            for s in range(0, len(part.staves)):
                line.appendToken(HumdrumToken(text))
                self.insertSideNullInterpretations(line, p, s) # insert staff sides
            self.insertSideNullInterpretations(line, p, -1) # insert part sides
        outFile.insertLine(0, line) # insert at line 0

    '''
    //////////////////////////////
    //
    // HumGrid::insertSideNullInterpretations --
    '''
    def insertSideNullInterpretations(self, line: HumdrumLine, p: int, s: int):
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
            for _ in range(0, self.xmlIdCount(p)): # xmlIdCount is always 0 or 1, but...
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
    def insertStaffIndications(self, outFile: HumdrumFile):
        if not self.measures:
            return
        if not self.measures[0].slices:
            return

        line: HumdrumLine = HumdrumLine()

        if self._recip:
            line.appendToken(HumdrumToken('*'))

        gridSlice: GridSlice = self.measures[0].slices[0]
        staffCount: int = 0
        for part in gridSlice.parts:
            staffCount += len(part.staves)

        for p, part in enumerate(gridSlice.parts):
            for s in range(0, len(part.staves)):
                text:str = '*staff' + str(staffCount)
                line.appendToken(HumdrumToken(text))
                self.insertSideStaffInfo(line, p, s, staffCount) # insert staff sides
                staffCount -= 1
            self.insertSideStaffInfo(line, p, -1, -1) # insert part sides
        outFile.insertLine(0, line) # insert at line 0

    '''
    //////////////////////////////
    //
    // HumGrid::insertSideStaffInfo --
    '''
    def insertSideStaffInfo(self, line: HumdrumLine, p: int, s: int, staffNum: int):
        if staffNum < 0:
            # part side info (no staff markers)
            if self.hasDynamics(p):
                line.appendToken(HumdrumToken('*'))
            if self.hasFiguredBass(p):
                line.appendToken(HumdrumToken('*'))
            for _ in range(0, self.harmonyCount(p)):
                line.appendToken(HumdrumToken('*'))
        else:
            # staff side info (staff markers)
            text: str = '*'
            if staffNum > 0:
                text = '*staff' + str(staffNum)
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
    def insertPartIndications(self, outFile: HumdrumFile):
        if not self.measures:
            return
        if not self.measures[0].slices:
            return

        line: HumdrumLine = HumdrumLine()

        if self._recip:
            line.appendToken(HumdrumToken('*'))

        gridSlice: GridSlice = self.measures[0].slices[0]
        for p, part in enumerate(gridSlice.parts):
            text: str = '*part' + str(p+1)
            for s in range(0, len(part.staves)):
                line.appendToken(HumdrumToken(text))
                self.insertSidePartInfo(line, p, s) # insert staff sides
            self.insertSidePartInfo(line, p, -1) # insert part sides
        outFile.insertLine(0, line) # insert at line 0

    '''
    //////////////////////////////
    //
    // HumGrid::insertSidePartInfo --
    '''
    def insertSidePartInfo(self, line: HumdrumLine, p: int, s: int):
        text: str = '*part' + str(p+1)
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
    def insertExclusiveInterpretationLine(self, outFile: HumdrumFile, interp: str):
        if not self.measures:
            return
        if not self.measures[0].slices:
            return

        line: HumdrumLine = HumdrumLine()

        if self._recip:
            line.appendToken(HumdrumToken('**recip'))

        gridSlice: GridSlice = self.measures[0].slices[0]
        for p, part in enumerate(gridSlice.parts):
            for s in range(0, len(part.staves)):
                line.appendToken(HumdrumToken(interp))
                self.insertExInterpSides(line, p, s) # insert staff sides
            self.insertExInterpSides(line, p, -1) # insert part sides
        outFile.insertLine(0, line) # insert at line 0

    '''
    //////////////////////////////
    //
    // HumGrid::insertExInterpSides --
    '''
    def insertExInterpSides(self, line: HumdrumLine, p: int, s: int):
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
    def insertDataTerminationLine(self, outFile: HumdrumFile):
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
                self.insertSideTerminals(line, p, s) # insert staff sides
            self.insertSideTerminals(line, p, -1) # insert part sides
        outFile.appendLine(line)

    '''
    //////////////////////////////
    //
    // HumGrid::insertSideTerminals --
    '''
    def insertSideTerminals(self, line: HumdrumLine, p: int, s: int):
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
    '''
    def removeRedundantClefChanges(self):
        # curClef is a list of the current staff on the part:staff.
        curClef: [[str]] = []
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
    def expandLocalCommentLayers(self):
        dataSlice: GridSlice = None
        localSlice: GridSlice = None
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
    def matchLocalCommentLayers(self, oslice: GridSlice, islice: GridSlice):
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
    def matchLocalCommentStaffLayers(ostaff: GridStaff, istaff: GridStaff):
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
            ostaff.append(GridVoice('!', 0))

    '''
    //////////////////////////////
    //
    // HumGrid::setPartName --
    '''
    def setPartName(self, partIndex: int, partName: str):
        if partIndex < 0:
            return

        if partIndex < len(self._partNames):
            self._partNames[partIndex] = partName
            return

        if partIndex < 100:
            # grow the array and then store name
            for _ in range(len(self._partNames), partIndex+1):
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