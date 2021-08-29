# ------------------------------------------------------------------------------
# Name:          GridMeasure.py
# Purpose:       HumGrid is an intermediate container for converting into Humdrum
#                syntax.  HumGrid consists of a list of GridMeasures.  GridMeasure
#                contains the data for all parts (GridPart) in a particular
#                measure.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021 Greg Chapman
# License:       BSD, see LICENSE
# ------------------------------------------------------------------------------
import sys

from converter21.humdrum import HumdrumInternalError
from converter21.humdrum import HumNum
from converter21.humdrum import HumdrumToken
from converter21.humdrum import HumdrumLine
from converter21.humdrum import HumdrumFile

from converter21.humdrum import MeasureStyle
from converter21.humdrum import SliceType
#from converter21.humdrum import GridVoice
#from converter21.humdrum import GridSide
#from converter21.humdrum import GridStaff
#from converter21.humdrum import GridPart
from converter21.humdrum import GridSlice
from converter21.humdrum import HumGrid


### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

class GridMeasure:
    def __init__(self, ownerGrid: HumGrid):
        self._ownerGrid = ownerGrid
        self.slices: [GridSlice] = []
        self._timestamp: HumNum = HumNum(-1)
        self._duration: HumNum = HumNum(-1)
        self._timeSigDur: HumNum = HumNum(-1)
        self._measureStyle: MeasureStyle = MeasureStyle.Plain
        self._barNum: int = -1

    def __str__(self) -> str:
        output: str = ''
        for gridSlice in self.slices:
            output += str(gridSlice) + '\n'
        return output

    '''
    //////////////////////////////
    //
    // GridMeasure::appendGlobalLayout --
    '''
    def appendGlobalLayout(self, tok: str, timestamp: HumNum) -> GridSlice:
        gs: GridSlice = GridSlice(self, timestamp, SliceType.GlobalLayouts, 1)
        gs.addToken(tok, 0, 0, 0)
        gs.duration = HumNum(0)
        self.slices.append(gs)
        return gs

    '''
    //////////////////////////////
    //
    // GridSlice::addGraceToken -- Add a grace note token at the given
    //   gracenumber grace note line before the data line at the given
    //   timestamp.
    '''
    def addGraceToken(self, tok: str, timestamp: HumNum,
                      part: int, staff: int, voice: int,
                      maxStaff: int, graceNumber: int) -> GridSlice:
        if graceNumber < 1:
            raise HumdrumInternalError(
                'ERROR: graceNumber {} has to be larger than 0')

        gs: GridSlice = None
        if not self.slices:
            # add a new GridSlice to an empty list.
            gs = GridSlice(self, timestamp, SliceType.GraceNotes, maxStaff)
            gs.addToken(tok, part, staff, voice)
            self.slices.append(gs)
            return gs

        if timestamp > self.slices[-1].timestamp:
            # Grace note needs to be added at the end of a measure.
            idx: int = len(self.slices) - 1 # pointing at last slice
            counter: int = 0
            while idx >= 0:
                if self.slices[idx].isGraceSlice:
                    counter += 1
                    if counter == graceNumber:
                        # insert grace note into this slice
                        self.slices[idx].addToken(tok, part, staff, voice)
                        return self.slices[idx]
                elif self.slices[idx].isLocalLayoutSlice:
                    # skip over any layout parameter lines
                    idx -= 1
                    continue

                if self.slices[idx].isDataSlice:
                    # insert grace note after this note
                    gs = GridSlice(self, timestamp, SliceType.GraceNotes, maxStaff)
                    gs.addToken(tok, part, staff, voice)
                    self.slices.insert(idx+1, gs)
                    return gs

                idx -= 1

            return None # couldn't find anywhere to insert

        # search for existing line with same timestamp on a data slice:
        foundIndex: int = -1
        for idx, gridSlice in enumerate(self.slices):
            if timestamp < gridSlice.timestamp:
                raise HumdrumInternalError(
'''STRANGE CASE 2 IN GRIDMEASURE::ADDGRACETOKEN
\tGRACE TIMESTAMP: {}
\tTEST  TIMESTAMP: {}'''.format(timestamp, gridSlice.timestamp))

            if gridSlice.isDataSlice:
                if gridSlice.timestamp == timestamp:
                    foundIndex = idx
                    break

        idx: int = foundIndex - 1
        counter: int = 0
        while idx >= 0:
            if self.slices[idx].isGraceSlice:
                counter += 1
                if counter == graceNumber:
                    # insert grace note into this slice
                    self.slices[idx].addToken(tok, part, staff, voice)
                    return self.slices[idx]
            elif self.slices[idx].isLocalLayoutSlice:
                # skip over any layout parameter lines
                idx -= 1
                continue

            if self.slices[idx].isDataSlice:
                # insert grace note after this note
                gs = GridSlice(self, timestamp, SliceType.GraceNotes, maxStaff)
                gs.addToken(tok, part, staff, voice)
                self.slices.insert(idx+1, gs)
                return gs

            idx -= 1

        # grace note should be added at start of measure
        gs = GridSlice(self, timestamp, SliceType.GraceNotes, maxStaff)
        gs.addToken(tok, part, staff, voice)
        self.slices.insert(0, gs)
        return gs

    '''
    //////////////////////////////
    //
    // GridMeasure::addDataToken -- Add a data token in the data slice at the given
    //    timestamp (or create a new data slice at that timestamp), placing the
    //    token at the specified part, staff, and voice index.
    '''
    def addDataToken(self, tok: str, timestamp: HumNum,
                     part: int, staff: int, voice: int,
                     maxStaff: int) -> GridSlice:
        gs: GridSlice = None
        if not self.slices or self.slices[-1].timestamp < timestamp:
            # add a new GridSlice to an empty list or at end of list if timestamp
            # is after last entry in list.
            gs = GridSlice(self, timestamp, SliceType.Notes, maxStaff)
            gs.addToken(tok, part, staff, voice)
            self.slices.append(gs)
            return gs

        # search for existing line with same timestamp and the same slice type
        for idx, gridSlice in enumerate(self.slices):
            if timestamp == gridSlice.timestamp and gridSlice.isGraceSlice:
                # skip grace notes with the right timestamp
                continue

            if not gridSlice.isDataSlice:
                continue

            if gridSlice.timestamp == timestamp:
                gridSlice.addToken(tok, part, staff, voice)
                gs = gridSlice
                return gs

            if gridSlice.timestamp > timestamp:
                gs = GridSlice(self, timestamp, SliceType.Notes, maxStaff)
                gs.addToken(tok, part, staff, voice)
                self.slices.insert(idx, gs)
                return gs

        # Couldn't find a place for it, so place at end of measure.
        gs = GridSlice(self, timestamp, SliceType.Notes, maxStaff)
        gs.addToken(tok, part, staff, voice)
        self.slices.append(gs)
        return gs

    '''
        addTokenOfSliceType: common code used by several other add*Token
           functions (addTempoToken, addTimeSigToken, addMeterToken, etc).
    '''
    def addTokenOfSliceType(self, tok: str, timestamp: HumNum,
                            sliceType: SliceType,
                            part: int, staff: int, voice: int,
                            maxStaff: int) -> GridSlice:
        gs: GridSlice = None
        if not self.slices or self.slices[-1].timestamp < timestamp:
            # add a new GridSlice to an empty list or at end of list if timestamp
            # is after last entry in list.
            gs = GridSlice(self, timestamp, sliceType, maxStaff)
            gs.addToken(tok, part, staff, voice)
            self.slices.append(gs)
            return gs

        # search for existing line with same timestamp and the same slice type
        for idx, gridSlice in enumerate(self.slices):
            if gridSlice.timestamp == timestamp and gridSlice.sliceType == sliceType:
                gridSlice.addToken(tok, part, staff, voice)
                gs = gridSlice
                return gs

            if gridSlice.timestamp == timestamp and gridSlice.isDataSlice:
                # found the correct timestamp, but no slice of the right type at the
                # timestamp, so add the new slice before the data slice (eventually
                # keeping track of the order in which the other non-data slices should
                # be placed).
                gs = GridSlice(self, timestamp, sliceType, maxStaff)
                gs.addToken(tok, part, staff, voice)
                self.slices.insert(idx, gs)
                return gs

            if gridSlice.timestamp > timestamp:
                gs = GridSlice(self, timestamp, sliceType, maxStaff)
                gs.addToken(tok, part, staff, voice)
                self.slices.insert(idx, gs)
                return gs

        # Couldn't find a place for the token, so place at end of measure
        gs = GridSlice(self, timestamp, sliceType, maxStaff)
        gs.addToken(tok, part, staff, voice)
        self.slices.append(gs)
        return gs

    '''
    //////////////////////////////
    //
    // GridMeasure::addTempoToken -- Add a tempo token in the data slice at
    //    the given timestamp (or create a new tempo slice at that timestamp), placing the
    //    token at the specified part, staff, and voice index.
    '''
    def addTempoToken(self, tok: str, timestamp: HumNum,
                      part: int, staff: int, voice: int, maxStaff: int) -> GridSlice:
        return self.addTokenOfSliceType(tok, timestamp, SliceType.Tempos,
                                        part, staff, voice, maxStaff)

    '''
    //////////////////////////////
    //
    // GridMeasure::addTimeSigToken -- Add a time signature token in the data slice at
    //    the given timestamp (or create a new timesig slice at that timestamp), placing the
    //    token at the specified part, staff, and voice index.
    '''
    def addTimeSigToken(self, tok: str, timestamp: HumNum,
                      part: int, staff: int, voice: int, maxStaff: int) -> GridSlice:
        return self.addTokenOfSliceType(tok, timestamp, SliceType.TimeSigs,
                                        part, staff, voice, maxStaff)

    '''
    //////////////////////////////
    //
    // GridMeasure::addMeterSigToken -- Add a meter signature token in the data slice at
    //    the given timestamp (or create a new timesig slice at that timestamp), placing the
    //    token at the specified part, staff, and voice index.
    //
    //    To do:
    //      The meter signtature should occur immediately after a time signature line.
    '''
    def addMeterSigToken(self, tok: str, timestamp: HumNum,
                      part: int, staff: int, voice: int, maxStaff: int) -> GridSlice:
        return self.addTokenOfSliceType(tok, timestamp, SliceType.MeterSigs,
                                        part, staff, voice, maxStaff)

    '''
    //////////////////////////////
    //
    // GridMeasure::addKeySigToken -- Add a key signature  token in a key sig slice at
    //    the given timestamp (or create a new keysig slice at that timestamp), placing the
    //    token at the specified part, staff, and voice index.
    '''
    def addKeySigToken(self, tok: str, timestamp: HumNum,
                      part: int, staff: int, voice: int, maxStaff: int) -> GridSlice:
        return self.addTokenOfSliceType(tok, timestamp, SliceType.KeySigs,
                                        part, staff, voice, maxStaff)

    '''
    //////////////////////////////
    //
    // GridMeasure::addTransposeToken -- Add a transposition token in the data slice at
    //    the given timestamp (or create a new transposition slice at that timestamp), placing
    //    the token at the specified part, staff, and voice index.
    //
    //    Note: should placed after clef if present and no other transpose slice at
    //    same time.
    '''
    def addTransposeToken(self, tok: str, timestamp: HumNum,
                      part: int, staff: int, voice: int, maxStaff: int) -> GridSlice:
        return self.addTokenOfSliceType(tok, timestamp, SliceType.Transpositions,
                                        part, staff, voice, maxStaff)

    '''
    //////////////////////////////
    //
    // GridMeasure::addClefToken -- Add a clef token in the data slice at the given
    //    timestamp (or create a new clef slice at that timestamp), placing the
    //    token at the specified part, staff, and voice index.
    '''
    def addClefToken(self, tok: str, timestamp: HumNum,
                      part: int, staff: int, voice: int, maxStaff: int) -> GridSlice:
        return self.addTokenOfSliceType(tok, timestamp, SliceType.Clefs,
                                        part, staff, voice, maxStaff)

    '''
    //////////////////////////////
    //
    // GridMeasure::addBarlineToken -- Add a barline token in the data slice at the given
    //    timestamp (or create a new barline slice at that timestamp), placing the
    //    token at the specified part, staff, and voice index.
    '''
    def addBarlineToken(self, tok: str, timestamp: HumNum,
                      part: int, staff: int, voice: int, maxStaff: int) -> GridSlice:
        return self.addTokenOfSliceType(tok, timestamp, SliceType.Measures,
                                        part, staff, voice, maxStaff)

    '''
    //////////////////////////////
    //
    // GridMeasure::addLabelToken -- Add an instrument label token in a label slice at
    //    the given timestamp (or create a new label slice at that timestamp), placing the
    //    token at the specified part, staff, and voice index.
    '''
    def addLabelToken(self, tok: str, timestamp: HumNum,
                      part: int, _staff: int, voice: int, maxPart: int, maxStaff: int) -> GridSlice:
        gs: GridSlice = None
        if not self.slices or self.slices[-1].timestamp < timestamp:
            # add a new GridSlice to an empty list or at end of list if timestamp
            # is after last entry in list.
            gs = GridSlice(self, timestamp, SliceType.Labels, maxPart)
            gs.addToken(tok, part, maxStaff-1, voice)
            self.slices.append(gs)
            return gs

        # search for existing line with same timestamp and the same slice type
        for gridSlice in self.slices:
            if gridSlice.timestamp == timestamp and gridSlice.isLabelSlice:
                gridSlice.addToken(tok, part, maxStaff-1, voice)
                gs = gridSlice
                return gs

        # Couldn't find a place for the label, so place at beginning of measure
        gs = GridSlice(self, timestamp, SliceType.Labels, maxPart)
        gs.addToken(tok, part, maxStaff-1, voice)
        self.slices.insert(0, gs)
        return gs

    '''
    //////////////////////////////
    //
    // GridMeasure::addLabelAbbrToken -- Add an instrument label token in a label slice at
    //    the given timestamp (or create a new label slice at that timestamp), placing the
    //    token at the specified part, staff, and voice index.
    '''
    def addLabelAbbrToken(self, tok: str, timestamp: HumNum,
                      part: int, _staff: int, voice: int, maxPart: int, maxStaff: int) -> GridSlice:
        gs: GridSlice = None
        if not self.slices or self.slices[-1].timestamp < timestamp:
            # add a new GridSlice to an empty list or at end of list if timestamp
            # is after last entry in list.
            gs = GridSlice(self, timestamp, SliceType.LabelAbbrs, maxPart)
            gs.addToken(tok, part, maxStaff-1, voice)
            self.slices.append(gs)
            return gs

        # search for existing line with same timestamp and the same slice type
        for gridSlice in self.slices:
            if gridSlice.timestamp == timestamp and gridSlice.isLabelAbbrSlice:
                gridSlice.addToken(tok, part, maxStaff-1, voice)
                gs = gridSlice
                return gs

        # Couldn't find a place for the label abbr, so place at beginning of measure
        gs = GridSlice(self, timestamp, SliceType.LabelAbbrs, maxPart)
        gs.addToken(tok, part, maxStaff-1, voice)
        self.slices.insert(0, gs)
        return gs

    '''
    //////////////////////////////
    //
    // GridMeasure::addGlobalComment -- Add a global comment at the given
    //    timestamp (before any data line at the same timestamp).  Suppress
    //    adding the comment if it matches to another global comment at the
    //    same timestamp with the same text.
    '''
    def addGlobalComment(self, tok: str, timestamp: HumNum) -> GridSlice:
        gs: GridSlice = None
        if not self.slices or self.slices[-1].timestamp < timestamp:
            # add a new GridSlice to an empty list or at end of list if timestamp
            # is after last entry in list.
            gs = GridSlice(self, timestamp, SliceType.GlobalComments, 1)
            gs.addToken(tok, 0, 0, 0)
            self.slices.append(gs)
            return gs

        # search for existing data line (of any type) with the same timestamp
        for idx, gridSlice in enumerate(self.slices):
            # does it need to be before data slice or any slice?
            # if (((*iterator)->getTimestamp() == timestamp) && (*iterator)->isDataSlice())
            if gridSlice.timestamp == timestamp:
                # found the correct timestamp on a slice, so add the global comment
                # before the slice.  But don't add if the slice we found is a
                # global comment with the same text.
                if gridSlice.isGlobalComment:
                    if tok == gridSlice.parts[0].staves[0].voices[0].token.text:
                        # do not insert duplicate global comments
                        gs = gridSlice
                        return gs

                gs = GridSlice(self, timestamp, SliceType.GlobalComments, 1)
                gs.addToken(tok, 0, 0, 0)
                self.slices.insert(idx, gs)
                return gs

            if gridSlice.timestamp > timestamp:
                # insert before this slice
                gs = GridSlice(self, timestamp, SliceType.GlobalComments, 1)
                gs.addToken(tok, 0, 0, 0)
                self.slices.insert(idx, gs)
                return gs

        return None # I think we should put it at the beginning in this case --gregc

    '''
    //////////////////////////////
    //
    // GridMeasure::transferTokens --
    //    default value: startbarnum = 0
    '''
    def transferTokens(self, outFile: HumdrumFile, recip: bool, addBar: bool, startBarNum: int = 0) -> bool:
        # If the last data slice duration is zero, then calculate
        # the true duration from the duration of the measure.
        if self.slices:
            gridSlice: GridSlice = self.slices[-1]
            if gridSlice.isMeasureSlice and len(self.slices) >= 2:
                endingIdx = len(self.slices) - 2
                while endingIdx != 0 and not self.slices[endingIdx].isDataSlice:
                    endingIdx -= 1
                gridSlice = self.slices[endingIdx]
            else:
                gridSlice = None

            if gridSlice is not None and gridSlice.isDataSlice and gridSlice.duration == 0:
                mts: HumNum = self.timestamp
                mdur: HumNum = self.duration
                sts: HumNum = gridSlice.timestamp
                sliceDur: HumNum = (mts + mdur) - sts
                gridSlice.duration = sliceDur

        foundData: bool = False
        addedBar: bool = False

        for gridSlice in self.slices:
            if gridSlice.isInvalidSlice:
                # ignore slices to be removed from output (used for
                # e.g. removing redundant clef slices).
                continue

            if addBar and not addedBar:
                if gridSlice.isDataSlice:
                    foundData = True

                if gridSlice.isLayoutSlice:
                    # didn't actually find data, but barline should
                    # not cross this line.
                    foundData = True

                if gridSlice.isManipulatorSlice:
                    # didn't acutally find data, but the barline should
                    # be placed before any manipulator (a spine split), since
                    # that is more a property of the data than of the header
                    # interpretations.
                    foundData = True

                if foundData:
                    if self.duration == 0:
                        # do nothing
                        pass
                    else:
                        self.appendInitialBarline(outFile, startBarNum)
                        addedBar = True

            gridSlice.transferTokens(outFile, recip)

        return True

    '''
    //////////////////////////////
    //
    // GridMeasure::appendInitialBarline -- The barline will be
    //    duplicated to all spines later.
        Looks like it actually gets duplicated to all (current) spines here --gregc
    '''
    def appendInitialBarline(self, outFile: HumdrumFile, startBarline: int = 0):
        if outFile.lineCount == 0:
            # strange case which should never happen
            return

        if self.measureNumber > 0:
            startBarline = self.measureNumber

        fieldCount: int = outFile[-1].fieldCount
        line: HumdrumLine = HumdrumLine()
        tstring: str = '='
        # TODO: humdrum writer needs to properly emit initial barline number
        # TODO: ... for now just put in the barline.
        tstring += str(startBarline)

        # probably best not to start with an invisible barline since
        # a plain barline would not be shown before the first measure anyway.
        # TODO: humdrum writer needs to properly emit hidden initial barline
        # TODO: ... for now, make it invisible if measure number is 0
        if startBarline == 0:
            tstring += '-'

        for _ in range(0, fieldCount):
            token: HumdrumToken = HumdrumToken(tstring)
            line.appendToken(token)

        outFile.append(line)

    '''
    //////////////////////////////
    //
    // GridMeasure::getOwner --
    '''
    @property
    def ownerGrid(self) -> HumGrid:
        return self._ownerGrid

    '''
    //////////////////////////////
    //
    // GridMeasure::setOwner --
    '''
    @ownerGrid.setter
    def ownerGrid(self, newOwnerGrid: HumGrid):
        self._ownerGrid = newOwnerGrid

    '''
    //////////////////////////////
    //
    // GridMeasure::getDuration --
    '''
    @property
    def duration(self) -> HumNum:
        return self._duration

    '''
    //////////////////////////////
    //
    // GridMeasure::setDuration --
    '''
    @duration.setter
    def duration(self, newDuration: HumNum):
        self._duration = newDuration

    '''
    //////////////////////////////
    //
    // GridMeasure::getTimestamp --
    '''
    @property
    def timestamp(self) -> HumNum:
        return self._timestamp

    '''
    //////////////////////////////
    //
    // GridMeasure::setTimestamp --
    '''
    @timestamp.setter
    def timestamp(self, newTimestamp: HumNum):
        self._timestamp = newTimestamp

    '''
    //////////////////////////////
    //
    // GridMeasure::getTimeSigDur --
    '''
    @property
    def timeSigDur(self) -> HumNum:
        return self._timeSigDur

    '''
    //////////////////////////////
    //
    // GridMeasure::setTimeSigDur --
    '''
    @timeSigDur.setter
    def timeSigDur(self, newTimeSigDur: HumNum):
        self._timeSigDur = newTimeSigDur

    '''
    //////////////////////////////
    //
    // GridMeasure::getFirstSpinedSlice --
    '''
    def firstSpinedSlice(self):
        for tslice in self.slices:
            if not tslice.hasSpines:
                continue
            return tslice
        return None

    '''
    //////////////////////////////
    //
    // GridMeasure::getLastSpinedSlice --
    '''
    def lastSpinedSlice(self):
        for tslice in reversed(self.slices):
            if tslice is None:
                continue
            if tslice.isGlobalLayout:
                continue
            if tslice.isGlobalComment:
                continue
            if tslice.isReferenceRecord:
                continue
            return tslice
        return None

    '''
    //////////////////////////////
    //
    // GridMeasure::getMeasureNumber --
    '''
    @property
    def measureNumber(self) -> int:
        return self._barNum

    '''
    //////////////////////////////
    //
    // GridMeasure::setMeasureNumber --
    '''
    @measureNumber.setter
    def measureNumber(self, newMeasureNumber: int):
        self._barNum = newMeasureNumber
