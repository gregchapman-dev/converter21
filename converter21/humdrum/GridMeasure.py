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
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
from typing import List, Optional

from converter21.humdrum import HumdrumInternalError
from converter21.humdrum import HumNum
from converter21.humdrum import HumdrumToken
#from converter21.humdrum import HumdrumLine
from converter21.humdrum import HumdrumFile

from converter21.humdrum import MeasureStyle
from converter21.humdrum import FermataStyle
from converter21.humdrum import SliceType
from converter21.humdrum import GridVoice
#from converter21.humdrum import GridSide
from converter21.humdrum import GridStaff
#from converter21.humdrum import GridPart
from converter21.humdrum import GridSlice

# you can't import this here, because the recursive import causes very weird issues.
#from converter21.humdrum import HumGrid


### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

class GridMeasure:
    def __init__(self, ownerGrid):
        from converter21.humdrum import HumGrid
        ownerGrid: HumGrid
        self._ownerGrid: HumGrid = ownerGrid
        self.slices: [GridSlice] = []
        self.timestamp: HumNum = HumNum(-1)
        self.duration: HumNum = HumNum(-1)
        self.timeSigDur: HumNum = HumNum(-1)
        self.leftBarlineStyle: MeasureStyle = MeasureStyle.Regular
        self.rightBarlineStyle: MeasureStyle = MeasureStyle.Regular
        self.fermataStylePerStaff: List[FermataStyle] = []
        self.measureStyle: MeasureStyle = MeasureStyle.Regular
        self.measureNumberString: str = ''

        # only used on last measure in score
        self.rightBarlineFermataStylePerStaff: List[FermataStyle] = []

    def __str__(self) -> str:
        output: str = f'MEASURE({self.measureNumberString}):'
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
f'''STRANGE CASE 2 IN GRIDMEASURE::ADDGRACETOKEN
\tGRACE TIMESTAMP: {timestamp}
\tTEST  TIMESTAMP: {gridSlice.timestamp}''')

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
                      part: int, staff: int, voice: int,
                      maxPart: int) -> GridSlice:
        gs: GridSlice = None
        if not self.slices or self.slices[-1].timestamp < timestamp:
            # add a new GridSlice to an empty list or at end of list if timestamp
            # is after last entry in list.
            gs = GridSlice(self, timestamp, SliceType.Labels, maxPart)
            gs.addToken(tok, part, staff, voice)
            self.slices.append(gs)
            return gs

        # search for existing line with same timestamp and the same slice type
        for gridSlice in self.slices:
            if gridSlice.timestamp == timestamp and gridSlice.isLabelSlice:
                gridSlice.addToken(tok, part, staff, voice)
                gs = gridSlice
                return gs

        # Couldn't find a place for the label, so place at beginning of measure
        gs = GridSlice(self, timestamp, SliceType.Labels, maxPart)
        gs.addToken(tok, part, staff, voice)
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
                          part: int, staff: int, voice: int,
                          maxPart: int) -> GridSlice:
        gs: GridSlice = None
        if not self.slices or self.slices[-1].timestamp < timestamp:
            # add a new GridSlice to an empty list or at end of list if timestamp
            # is after last entry in list.
            gs = GridSlice(self, timestamp, SliceType.LabelAbbrs, maxPart)
            gs.addToken(tok, part, staff, voice)
            self.slices.append(gs)
            return gs

        # search for existing line with same timestamp and the same slice type
        for gridSlice in self.slices:
            if gridSlice.timestamp == timestamp and gridSlice.isLabelAbbrSlice:
                gridSlice.addToken(tok, part, staff, voice)
                gs = gridSlice
                return gs

        # Couldn't find a place for the label abbr, so place at beginning of measure
        gs = GridSlice(self, timestamp, SliceType.LabelAbbrs, maxPart)
        gs.addToken(tok, part, staff, voice)
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
    '''
    def transferTokens(self, outFile: HumdrumFile, recip: bool, firstBar: bool=False) -> bool:
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

        # in the first bar, we delay the initial barline until after all the clef, keysig, etc
        haveFirstBarline: bool = False
        doFirstBarlineNow: bool = False
        didFirstBarline: bool = False
        firstBarlineSlice: GridSlice = None

        if self.duration == 0:
            firstBar = False # don't reposition the first barline if the first bar has no notes

        for gridSlice in self.slices:
            if gridSlice.isInvalidSlice:
                # ignore slices to be removed from output (used for
                # e.g. removing redundant clef slices).
                continue

            if firstBar:
                if gridSlice.isDataSlice:
                    doFirstBarlineNow = True
                elif gridSlice.isLocalLayoutSlice:
                    doFirstBarlineNow = True
                elif gridSlice.isManipulatorSlice:
                    doFirstBarlineNow = True
                elif gridSlice.isVerseLabelSlice:
                    doFirstBarlineNow = True

                if doFirstBarlineNow and not didFirstBarline:
                    firstBarlineSlice.transferTokens(outFile, recip)
                    didFirstBarline = True
                    # and the slice that made us do the first barline now...
                    gridSlice.transferTokens(outFile, recip)
                    continue

                # assumption: we'll see the first barline well before we run into
                # something that will make us do it.
                if gridSlice.isMeasureSlice and not haveFirstBarline:
                    firstBarlineSlice = gridSlice
                    haveFirstBarline = True
                else:
                    gridSlice.transferTokens(outFile, recip)
            else:
                gridSlice.transferTokens(outFile, recip)

        return True

#     '''
#     //////////////////////////////
#     //
#     // GridMeasure::appendInitialBarline -- The barline will be
#     //    duplicated to all spines later.
#         Looks like it actually gets duplicated to all (current) spines here --gregc
#     '''
#     def appendInitialBarline(self, outFile: HumdrumFile, startBarline: int = 0):
#         if outFile.lineCount == 0:
#             # strange case which should never happen
#             return
#
#         startBarlineString = str(startBarline)
#         if self.measureNumberString:
#             startBarlineString = self.measureNumberString
#
#         fieldCount: int = outFile[-1].tokenCount
#         line: HumdrumLine = HumdrumLine()
#         tstring: str = '='
#         # TODO: humdrum writer needs to properly emit initial barline number
#         # TODO: ... for now just put in the barline.
#         tstring += startBarlineString
#
#         # probably best not to start with an invisible barline since
#         # a plain barline would not be shown before the first measure anyway.
#         # TODO: humdrum writer needs to properly emit hidden initial barline
#         # TODO: ... for now, make it invisible if measure number is 0
#         if startBarline == 0:
#             tstring += '-'
#
#         for _ in range(0, fieldCount):
#             token: HumdrumToken = HumdrumToken(tstring)
#             line.appendToken(token)
#
#         outFile.appendLine(line)

    '''
    //////////////////////////////
    //
    // GridMeasure::getOwner --
    '''
    @property
    def ownerGrid(self): # -> HumGrid:
        return self._ownerGrid

    '''
    //////////////////////////////
    //
    // GridMeasure::setOwner --
    '''
    @ownerGrid.setter
    def ownerGrid(self, newOwnerGrid):
        self._ownerGrid = newOwnerGrid

    # _getIndexedVoice_AppendingIfNecessary appends enough new voices to the list to
    # accommodate voiceIndex, then returns voices[voiceIndex]
    @staticmethod
    def _getIndexedVoice_AppendingIfNecessary(voices: List[GridVoice], voiceIndex: int) -> GridVoice:
        additionalVoicesNeeded: int = voiceIndex + 1 - len(voices)
        for _ in range(0, additionalVoicesNeeded):
            voices.append(GridVoice())
        return voices[voiceIndex]

    def addVerseLabels(self, associatedSlice: GridSlice,
                            partIndex: int, staffIndex: int,
                            verseLabels: List[HumdrumToken]):
        # add these verse labels just before this associatedSlice
        if len(self.slices) == 0:
		    # something strange happened: expecting at least one item in measure.
            return # associatedSlice is supposed to already be in the measure

        associatedSliceIdx: Optional[int] = None
        if associatedSlice is None:
            # place at end of measure (associate with imaginary slice just off the end)
            associatedSliceIdx = len(self.slices)
        else:
            # find owning line (associatedSlice)
            foundIt: bool = False
            for associatedSliceIdx in range(len(self.slices)-1, -1, -1): # loop in reverse index order
                gridSlice: GridSlice = self.slices[associatedSliceIdx]
                if gridSlice is associatedSlice:
                    foundIt = True
                    break
            if not foundIt:
                # cannot find owning line (a.k.a. associatedSlice is not in this GridMeasure)
                return

        # see if the previous slice is a VerseLabels slice we can use
        prevIdx: int = associatedSliceIdx-1
        prevSlice: GridSlice = self.slices[prevIdx]
        if prevSlice.isVerseLabelSlice:
            prevStaff: GridStaff = prevSlice.parts[partIndex].staves[staffIndex]
            if prevStaff.sides.verseCount == 0:
                for i, verseLabel in enumerate(verseLabels):
                    if verseLabel is not None:
                        prevStaff.sides.setVerse(i, verseLabel)
                return

        # if we get here, we couldn't use the previous slice, so we need to insert
        # a new Layout slice to use, just before the associated slice.
        insertPoint: int = associatedSliceIdx
        newSlice: GridSlice = None
        if associatedSlice is not None:
            newSlice: GridSlice = GridSlice(self, associatedSlice.timestamp, SliceType.VerseLabels)
            newSlice.initializeBySlice(associatedSlice)
            self.slices.insert(insertPoint, newSlice)
        else:
            newSlice = GridSlice(self, self.timestamp + self.duration, SliceType.VerseLabels)
            newSlice.initializeBySlice(self.slices[-1])
            self.slices.append(newSlice)

        newStaff: GridStaff = newSlice.parts[partIndex].staves[staffIndex]
        for i, verseLabel in enumerate(verseLabels):
            if verseLabel is not None:
                newStaff.sides.setVerse(i, verseLabel)

    '''
    //////////////////////////////
    //
    // GridMeasure::addLayoutParameter --
    '''
    def addLayoutParameter(self, associatedSlice: GridSlice,
                           partIndex: int, staffIndex: int, voiceIndex: int,
                           locomment: str):
        # add this '!LO:' string just before this associatedSlice
        if len(self.slices) == 0:
		    # something strange happened: expecting at least one item in measure.
            return # associatedSlice is supposed to already be in the measure

        associatedSliceIdx: Optional[int] = None
        if associatedSlice is None:
            # place at end of measure (associate with imaginary slice just off the end)
            associatedSliceIdx = len(self.slices)
        else:
            # find owning line (associatedSlice)
            foundIt: bool = False
            for associatedSliceIdx in range(len(self.slices)-1, -1, -1): # loop in reverse index order
                gridSlice: GridSlice = self.slices[associatedSliceIdx]
                if gridSlice is associatedSlice:
                    foundIt = True
                    break
            if not foundIt:
                # cannot find owning line (a.k.a. associatedSlice is not in this GridMeasure)
                return

        # see if the previous slice is a layout slice we can use
        prevIdx: int = associatedSliceIdx-1
        prevSlice: GridSlice = self.slices[prevIdx]
        if prevSlice.isLocalLayoutSlice:
            prevStaff: GridStaff = prevSlice.parts[partIndex].staves[staffIndex]
            prevVoice: GridVoice = self._getIndexedVoice_AppendingIfNecessary(prevStaff.voices,
                                                                              voiceIndex)
            if prevVoice.token is None or prevVoice.token.text == '!':
                prevVoice.token = HumdrumToken(locomment)
                return

        # if we get here, we couldn't use the previous slice, so we need to insert
        # a new Layout slice to use, just before the associated slice.
        insertPoint: int = associatedSliceIdx
        newSlice: GridSlice = None
        if associatedSlice is not None:
            newSlice = GridSlice(self, associatedSlice.timestamp, SliceType.Layouts)
            newSlice.initializeBySlice(associatedSlice)
            self.slices.insert(insertPoint, newSlice)
        else:
            newSlice = GridSlice(self, self.timestamp + self.duration, SliceType.Layouts)
            newSlice.initializeBySlice(self.slices[-1])
            self.slices.append(newSlice)

        newStaff: GridStaff = newSlice.parts[partIndex].staves[staffIndex]
        newVoice: GridVoice = self._getIndexedVoice_AppendingIfNecessary(newStaff.voices,
                                                                         voiceIndex)
        newVoice.token = HumdrumToken(locomment)

    '''
    //////////////////////////////
    //
    // GridMeasure::addDynamicsLayoutParameters --
    '''
    def addDynamicsLayoutParameters(self, associatedSlice: GridSlice,
                                    partIndex: int, staffIndex: int,
                                    locomment: str):
        if len(self.slices) == 0:
		    # something strange happened: expecting at least one item in measure.
            return # associatedSlice is supposed to already be in the measure

        associatedSliceIdx: Optional[int] = None
        if associatedSlice is None:
            # place at end of measure (associate with imaginary slice just off the end)
            associatedSliceIdx = len(self.slices)
        else:
            # find owning line (associatedSlice)
            foundIt: bool = False
            for associatedSliceIdx in range(len(self.slices)-1, -1, -1): # loop in reverse index order
                gridSlice: GridSlice = self.slices[associatedSliceIdx]
                if gridSlice is associatedSlice:
                    foundIt = True
                    break
            if not foundIt:
                # cannot find owning line (a.k.a. associatedSlice is not in this GridMeasure)
                return

        # see if the previous slice is a layout slice we can use
        prevIdx: int = associatedSliceIdx-1
        prevSlice: GridSlice = self.slices[prevIdx]
        if prevSlice.isLocalLayoutSlice:
            prevStaff: GridStaff = prevSlice.parts[partIndex].staves[staffIndex]
            if prevStaff.dynamics is None:
                prevStaff.dynamics = HumdrumToken(locomment)
                return

        # if we get here, we couldn't use the previous slice, so we need to insert
        # a new Layout slice to use, just before the associated slice.
        insertPoint: int = associatedSliceIdx
        newSlice: GridSlice = None
        if associatedSlice is not None:
            newSlice: GridSlice = GridSlice(self, associatedSlice.timestamp, SliceType.Layouts)
            newSlice.initializeBySlice(associatedSlice)
            self.slices.insert(insertPoint, newSlice)
        else:
            newSlice = GridSlice(self, self.timestamp + self.duration, SliceType.Layouts)
            newSlice.initializeBySlice(self.slices[-1])
            self.slices.append(newSlice)

        newStaff: GridStaff = newSlice.parts[partIndex].staves[staffIndex]
        newStaff.dynamics = HumdrumToken(locomment)

    '''
    //////////////////////////////
    //
    // GridMeasure::getFirstSpinedSlice --
    '''
    def firstSpinedSlice(self) -> GridSlice:
        for tslice in self.slices:
            if tslice is not None and tslice.hasSpines:
                return tslice
        return None

    '''
    //////////////////////////////
    //
    // GridMeasure::getLastSpinedSlice --
    '''
    def lastSpinedSlice(self):
        for tslice in reversed(self.slices):
            if tslice is not None and tslice.hasSpines:
                return tslice
        return None

    def fermataStyle(self, staffIndex: int) -> FermataStyle:
        output: FermataStyle = FermataStyle.NoFermata

        if 0 <= staffIndex < len(self.fermataStylePerStaff):
            output = self.fermataStylePerStaff[staffIndex]

#         if output != FermataStyle.NoFermata:
#             print(f'fermataStyle({staffIndex}): {output}')

#         print(f'fermataStyle({staffIndex}): {output}')

        return output

    def rightBarlineFermataStyle(self, staffIndex: int) -> FermataStyle:
        output: FermataStyle = FermataStyle.NoFermata

        if 0 <= staffIndex < len(self.rightBarlineFermataStylePerStaff):
            output = self.rightBarlineFermataStylePerStaff[staffIndex]

#         if output != FermataStyle.NoFermata:
#             print(f'rightBarlineFermataStyle({staffIndex}): {output}')

#         print(f'rightBarlineFermataStyle({staffIndex}): {output}')

        return output
