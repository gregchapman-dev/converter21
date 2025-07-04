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
# Copyright:     (c) 2021-2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
import typing as t

from music21.common import opFrac

from converter21.humdrum import HumdrumInternalError
from converter21.humdrum import HumNum, HumNumIn
from converter21.humdrum import HumdrumToken
# from converter21.humdrum import HumdrumLine
from converter21.humdrum import HumdrumFile

from converter21.humdrum import MeasureStyle
from converter21.humdrum import FermataStyle
from converter21.humdrum import SliceType
from converter21.humdrum import GridVoice
# from converter21.humdrum import GridSide
from converter21.humdrum import GridStaff
from converter21.humdrum import GridPart
from converter21.humdrum import GridSlice

# you can't import this here, because the recursive import causes very weird issues.
# from converter21.humdrum import HumGrid


# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class GridMeasure:
    def __init__(self, ownerGrid) -> None:
        from converter21.humdrum import HumGrid
        if not isinstance(ownerGrid, HumGrid):
            raise HumdrumInternalError('invalid ownerGrid')
        self._ownerGrid: HumGrid = ownerGrid
        self.slices: list[GridSlice] = []
        self._timestamp: HumNum = opFrac(-1)
        self._duration: HumNum = opFrac(-1)
        self._timeSigDur: HumNum = opFrac(-1)
        self.leftBarlineStylePerStaff: list[MeasureStyle] = []
        self.rightBarlineStylePerStaff: list[MeasureStyle] = []
        self.fermataStylePerStaff: list[FermataStyle] = []
        self.measureStylePerStaff: list[MeasureStyle] = []
        self.measureNumberString: str = ''

        self.inRepeatBracket: bool = False
        self.startsRepeatBracket: bool = False
        self.stopsRepeatBracket: bool = False
        self.repeatBracketName: str = ''

        # only used on last measure in score
        self.rightBarlineFermataStylePerStaff: list[FermataStyle] = []

    def __str__(self) -> str:
        output: str = f'MEASURE({self.measureNumberString}):'
        for gridSlice in self.slices:
            output += str(gridSlice) + '\n'
        return output

    @property
    def timestamp(self) -> HumNum:
        return self._timestamp

    @timestamp.setter
    def timestamp(self, newTimestamp: HumNumIn) -> None:
        self._timestamp = opFrac(newTimestamp)

    @property
    def duration(self) -> HumNum:
        return self._duration

    @duration.setter
    def duration(self, newDuration: HumNumIn) -> None:
        self._duration = opFrac(newDuration)

    @property
    def timeSigDur(self) -> HumNum:
        return self._timeSigDur

    @timeSigDur.setter
    def timeSigDur(self, newTimeSigDur: HumNumIn) -> None:
        self._timeSigDur = opFrac(newTimeSigDur)

    '''
    //////////////////////////////
    //
    // GridMeasure::appendGlobalLayout --
    '''
    def appendGlobalLayout(self, tok: str, timestamp: HumNumIn) -> GridSlice:
        gs: GridSlice = GridSlice(self, timestamp, SliceType.GlobalLayouts, [1])
        gs.addToken(tok, 0, 0, 0)
        gs.duration = opFrac(0)
        self.slices.append(gs)
        return gs

    '''
    //////////////////////////////
    //
    // GridSlice::addGraceToken -- Add a grace note token at the given
    //   gracenumber grace note line before the data line at the given
    //   timestamp.
    '''
    def addGraceToken(
        self,
        tok: str,
        timestamp: HumNumIn,
        part: int,
        staff: int,
        voice: int,
        staffCounts: list[int],
        graceNumber: int
    ) -> GridSlice | None:
        ts: HumNum = opFrac(timestamp)

        if graceNumber < 1:
            raise HumdrumInternalError(
                'ERROR: graceNumber {graceNumber} has to be larger than 0')

        gs: GridSlice
        idx: int
        counter: int

        if not self.slices:
            # add a new GridSlice to an empty list.
            gs = GridSlice(self, ts, SliceType.GraceNotes, staffCounts)
            gs.addToken(tok, part, staff, voice)
            self.slices.append(gs)
            return gs

        if ts > self.slices[-1].timestamp:
            # Grace note needs to be added at the end of a measure.
            idx = len(self.slices) - 1  # pointing at last slice
            counter = 0
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
                    gs = GridSlice(self, ts, SliceType.GraceNotes, staffCounts)
                    gs.addToken(tok, part, staff, voice)
                    self.slices.insert(idx + 1, gs)
                    return gs

                idx -= 1

            return None  # couldn't find anywhere to insert

        # search for existing line with same timestamp on a data slice:
        foundIndex: int = -1
        for slicei, gridSlice in enumerate(self.slices):
            if ts < gridSlice.timestamp:
                raise HumdrumInternalError(
                    'STRANGE CASE 2 IN GRIDMEASURE::ADDGRACETOKEN\n'
                    + f'\tGRACE TIMESTAMP: {ts}\n'
                    + f'\tTEST  TIMESTAMP: {gridSlice.timestamp}'
                )

            if gridSlice.isDataSlice:
                if gridSlice.timestamp == ts:
                    foundIndex = slicei
                    break

        idx = foundIndex - 1
        counter = 0
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
                gs = GridSlice(self, ts, SliceType.GraceNotes, staffCounts)
                gs.addToken(tok, part, staff, voice)
                self.slices.insert(idx + 1, gs)
                return gs

            idx -= 1

        # grace note should be added at start of measure
        gs = GridSlice(self, ts, SliceType.GraceNotes, staffCounts)
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
    def addDataToken(
        self,
        tok: str,
        timestamp: HumNumIn,
        part: int,
        staff: int,
        voice: int,
        staffCounts: list[int]
    ) -> GridSlice:
        ts: HumNum = opFrac(timestamp)
        gs: GridSlice

        if not self.slices or self.slices[-1].timestamp < ts:
            # add a new GridSlice to an empty list or at end of list if timestamp
            # is after last entry in list.
            gs = GridSlice(self, ts, SliceType.Notes, staffCounts)
            gs.addToken(tok, part, staff, voice)
            self.slices.append(gs)
            return gs

        # search for existing line with same timestamp and the same slice type
        for idx, gridSlice in enumerate(self.slices):
            if ts == gridSlice.timestamp and gridSlice.isGraceSlice:
                # skip grace notes with the right timestamp
                continue

            if not gridSlice.isDataSlice:
                continue

            if gridSlice.timestamp == ts:
                gridSlice.addToken(tok, part, staff, voice)
                gs = gridSlice
                return gs

            if gridSlice.timestamp > ts:
                gs = GridSlice(self, ts, SliceType.Notes, staffCounts)
                gs.addToken(tok, part, staff, voice)
                self.slices.insert(idx, gs)
                return gs

        # Couldn't find a place for it, so place at end of measure.
        gs = GridSlice(self, ts, SliceType.Notes, staffCounts)
        gs.addToken(tok, part, staff, voice)
        self.slices.append(gs)
        return gs

    '''
        addTokenOfSliceType: common code used by several other add*Token
           functions (addTempoToken, addTimeSigToken, addMeterToken, etc).
    '''
    def addTokenOfSliceType(
        self,
        tok: str,
        timestamp: HumNumIn,
        sliceType: SliceType,
        part: int,
        staff: int,
        voice: int,
        staffCounts: list[int],
        beforeAnyLayouts: bool = False
    ) -> GridSlice:
        # beforeAnyLayouts == True only works if the timestamp lands us exactly on a data slice
        ts: HumNum = opFrac(timestamp)
        gs: GridSlice

        if not self.slices or self.slices[-1].timestamp < ts:
            # add a new GridSlice to an empty list or at end of list if timestamp
            # is after last entry in list.
            gs = GridSlice(self, ts, sliceType, staffCounts)
            gs.addToken(tok, part, staff, voice)
            self.slices.append(gs)
            return gs

        # search for existing line with same timestamp and the same slice type
        for idx, gridSlice in enumerate(self.slices):
            if gridSlice.timestamp == ts and gridSlice.sliceType == sliceType:
                gridSlice.addToken(tok, part, staff, voice)
                gs = gridSlice
                return gs

            if gridSlice.timestamp == ts and gridSlice.isDataSlice:
                # found the correct timestamp, but no slice of the right type at the
                # timestamp, so add the new slice before the data slice (and, if
                # requested, before any layouts preceding this data slice).
                insertPoint: int = idx
                if beforeAnyLayouts:
                    insertPoint = self.startIdxOfLayoutGroupBefore(insertPoint)

                gs = GridSlice(self, ts, sliceType, staffCounts)
                gs.addToken(tok, part, staff, voice)
                self.slices.insert(insertPoint, gs)
                return gs

            if gridSlice.timestamp > ts:
                gs = GridSlice(self, ts, sliceType, staffCounts)
                gs.addToken(tok, part, staff, voice)
                self.slices.insert(idx, gs)
                return gs

        # Couldn't find a place for the token, so place at end of measure
        gs = GridSlice(self, ts, sliceType, staffCounts)
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
    def addTempoToken(
        self,
        tok: str,
        timestamp: HumNumIn,
        part: int,
        staff: int,
        voice: int,
        staffCounts: list[int]
    ) -> GridSlice:
        return self.addTokenOfSliceType(
            tok,
            timestamp,
            SliceType.Tempos,
            part,
            staff,
            voice,
            staffCounts,
            beforeAnyLayouts=True
        )

    '''
    //////////////////////////////
    //
    // GridMeasure::addTimeSigToken -- Add a time signature token in the data slice at
    //    the given timestamp (or create a new timesig slice at that timestamp), placing the
    //    token at the specified part, staff, and voice index.
    '''
    def addTimeSigToken(
        self,
        tok: str,
        timestamp: HumNumIn,
        part: int,
        staff: int,
        voice: int,
        staffCounts: list[int]
    ) -> GridSlice:
        return self.addTokenOfSliceType(tok, timestamp, SliceType.TimeSigs,
                                        part, staff, voice, staffCounts)

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
    def addMeterSigToken(
        self,
        tok: str,
        timestamp: HumNumIn,
        part: int,
        staff: int,
        voice: int,
        staffCounts: list[int]
    ) -> GridSlice:
        return self.addTokenOfSliceType(tok, timestamp, SliceType.MeterSigs,
                                        part, staff, voice, staffCounts)

    '''
    //////////////////////////////
    //
    // GridMeasure::addKeySigToken -- Add a key signature  token in a key sig slice at
    //    the given timestamp (or create a new keysig slice at that timestamp), placing the
    //    token at the specified part, staff, and voice index.
    '''
    def addKeySigToken(
        self,
        tok: str,
        timestamp: HumNumIn,
        part: int,
        staff: int,
        voice: int,
        staffCounts: list[int]
    ) -> GridSlice:
        return self.addTokenOfSliceType(tok, timestamp, SliceType.KeySigs,
                                        part, staff, voice, staffCounts)

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
    def addTransposeToken(
        self,
        tok: str,
        timestamp: HumNumIn,
        part: int,
        staff: int,
        voice: int,
        staffCounts: list[int]
    ) -> GridSlice:
        return self.addTokenOfSliceType(tok, timestamp, SliceType.Transpositions,
                                        part, staff, voice, staffCounts)

    '''
    //////////////////////////////
    //
    // GridMeasure::addClefToken -- Add a clef token in the data slice at the given
    //    timestamp (or create a new clef slice at that timestamp), placing the
    //    token at the specified part, staff, and voice index.
    '''
    def addClefToken(
        self,
        tok: str,
        timestamp: HumNumIn,
        part: int,
        staff: int,
        voice: int,
        staffCounts: list[int]
    ) -> GridSlice:
        return self.addTokenOfSliceType(tok, timestamp, SliceType.Clefs,
                                        part, staff, voice, staffCounts)

    '''
    //////////////////////////////
    //
    // GridMeasure::addBarlineToken -- Add a barline token in the data slice at the given
    //    timestamp (or create a new barline slice at that timestamp), placing the
    //    token at the specified part, staff, and voice index.
    '''
    def addBarlineToken(
        self,
        tok: str,
        timestamp: HumNumIn,
        part: int,
        staff: int,
        voice: int,
        staffCounts: list[int]
    ) -> GridSlice:
        return self.addTokenOfSliceType(tok, timestamp, SliceType.Measures,
                                        part, staff, voice, staffCounts)

    '''
    GridMeasure::addTupletDisplayTokenBefore -- Add a *tuplet/*Xtuplet/*brackettup/*Xbrackettup/etc
    token just before associatedSlice, placing the token at the specified part, staff, and voice index.
    '''
    def addTupletDisplayTokenBefore(
        self,
        tok: str,
        associatedSlice: GridSlice,
        partIndex: int,
        staffIndex: int,
        voiceIndex: int
    ) -> None:
        newSlice: GridSlice

        # add this display token just before the associatedSlice
        if associatedSlice is None:
            return

        if len(self.slices) == 0:
            # something strange happened: expecting at least one item in measure.
            # associatedSlice is supposed to already be in the measure.
            return

        associatedSliceIdx: int | None = None
        # find owning line (associatedSlice)
        foundIt: bool = False
        for associatedSliceIdx in range(len(self.slices) - 1, -1, -1):
            gridSlice: GridSlice = self.slices[associatedSliceIdx]
            if gridSlice is associatedSlice:
                foundIt = True
                break
        if not foundIt:
            # cannot find owning line (a.k.a. associatedSlice is not in this GridMeasure)
            return

        # see if the previous slice is a TupletDisplay slice we can use
        prevIdx: int = associatedSliceIdx - 1
        prevSlice: GridSlice = self.slices[prevIdx]
        if prevSlice.isTupletDisplaySlice:
            prevVoices: list[GridVoice | None] = (
                prevSlice.parts[partIndex].staves[staffIndex].voices
            )
            prevTok: HumdrumToken | None = None
            if voiceIndex < len(prevVoices):
                prevVoice: GridVoice | None = prevVoices[voiceIndex]
                if prevVoice is not None:
                    prevTok = prevVoice.token

            if prevTok is None or prevTok.text == '*':
                # go ahead and overwrite it (adding new voice if necessary)
                prevSlice.addToken(tok, partIndex, staffIndex, voiceIndex)
            else:
                # don't overwrite important token, instead insert a new slice
                newSlice = GridSlice(self, associatedSlice.timestamp, SliceType.TupletDisplay)
                newSlice.initializeBySlice(associatedSlice)
                newSlice.addToken(tok, partIndex, staffIndex, voiceIndex)
                self.slices.insert(associatedSliceIdx, newSlice)
            return

        # if we get here, we couldn't use the previous slice, so we need to insert
        # a new TupletDisplay slice to use, just before the associated slice.
        newSlice = GridSlice(self, associatedSlice.timestamp, SliceType.TupletDisplay)
        newSlice.initializeBySlice(associatedSlice)
        newSlice.addToken(tok, partIndex, staffIndex, voiceIndex)
        self.slices.insert(associatedSliceIdx, newSlice)

    def addOttavaOrPedalTokensBefore(
        self,
        toks: list[str],
        associatedSlice: GridSlice | None,
        partIndex: int,
        staffIndex: int
    ) -> None:
        def isPedal(tok: str) -> bool:
            return tok in ('*ped', '*Xped')

        if not toks:
            # nothing to add
            return

        # add this '*ped' or '*X8va' or... string just before this associatedSlice
        associatedSliceIdx: int | None = None
        if associatedSlice is None:
            # place at end of measure (associate with imaginary slice just off the end)
            associatedSliceIdx = len(self.slices)
        else:
            # find owning line (associatedSlice)
            foundIt: bool = False
            for associatedSliceIdx in range(len(self.slices) - 1, -1, -1):
                gridSlice: GridSlice = self.slices[associatedSliceIdx]
                if gridSlice is associatedSlice:
                    foundIt = True
                    break
            if not foundIt:
                # cannot find owning line (a.k.a. associatedSlice is not in this GridMeasure)
                return

        newSlice: GridSlice

        for tok in toks:
            if associatedSlice is not None:
                if isPedal(tok):
                    newSlice = GridSlice(self, associatedSlice.timestamp, SliceType.Pedals)
                else:
                    newSlice = GridSlice(self, associatedSlice.timestamp, SliceType.Ottavas)
                newSlice.initializeBySlice(associatedSlice)
                self.slices.insert(associatedSliceIdx, newSlice)
            else:
                if isPedal(tok):
                    newSlice = GridSlice(self, self.timestamp + self.duration, SliceType.Pedals)
                else:
                    newSlice = GridSlice(self, self.timestamp + self.duration, SliceType.Ottavas)
                newSlice.initializeBySlice(self.slices[-1])
                self.slices.append(newSlice)

            newStaff: GridStaff = newSlice.parts[partIndex].staves[staffIndex]
            # ottavas and pedals always go in voice 0 (so paired starts/stops can be found,
            # even when processing one voice at a time).
            newVoice: GridVoice = self._getIndexedVoice_AppendingIfNecessary(newStaff.voices, 0)
            newVoice.token = HumdrumToken(tok)

    '''
    //////////////////////////////
    //
    // GridMeasure::addLabelToken -- Add an instrument label token in a label slice at
    //    the given timestamp (or create a new label slice at that timestamp), placing the
    //    token at the specified part, staff, and voice index.
    '''
    def addLabelToken(
        self,
        tok: str,
        timestamp: HumNumIn,
        part: int,
        staff: int,
        voice: int,
        staffCounts: list[int]
    ) -> GridSlice:
        ts: HumNum = opFrac(timestamp)
        gs: GridSlice

        if not self.slices or self.slices[-1].timestamp < ts:
            # add a new GridSlice to an empty list or at end of list if timestamp
            # is after last entry in list.
            gs = GridSlice(self, ts, SliceType.Labels, staffCounts)
            gs.addToken(tok, part, staff, voice)
            self.slices.append(gs)
            return gs

        # search for existing line with same timestamp and the same slice type
        for gridSlice in self.slices:
            if gridSlice.timestamp == ts and gridSlice.isLabelSlice:
                gridSlice.addToken(tok, part, staff, voice)
                gs = gridSlice
                return gs

        # Couldn't find a place for the label, so place at beginning of measure
        gs = GridSlice(self, ts, SliceType.Labels, staffCounts)
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
    def addLabelAbbrToken(
        self,
        tok: str,
        timestamp: HumNumIn,
        part: int,
        staff: int,
        voice: int,
        staffCounts: list[int]
    ) -> GridSlice:
        ts: HumNum = opFrac(timestamp)
        gs: GridSlice

        if not self.slices or self.slices[-1].timestamp < ts:
            # add a new GridSlice to an empty list or at end of list if timestamp
            # is after last entry in list.
            gs = GridSlice(self, ts, SliceType.LabelAbbrs, staffCounts)
            gs.addToken(tok, part, staff, voice)
            self.slices.append(gs)
            return gs

        # search for existing line with same timestamp and the same slice type
        for gridSlice in self.slices:
            if gridSlice.timestamp == ts and gridSlice.isLabelAbbrSlice:
                gridSlice.addToken(tok, part, staff, voice)
                gs = gridSlice
                return gs

        # Couldn't find a place for the label abbr, so place at beginning of measure
        gs = GridSlice(self, ts, SliceType.LabelAbbrs, staffCounts)
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
    def addGlobalComment(self, tok: str, timestamp: HumNumIn) -> GridSlice | None:
        ts: HumNum = opFrac(timestamp)
        gs: GridSlice

        if not self.slices or self.slices[-1].timestamp < ts:
            # add a new GridSlice to an empty list or at end of list if timestamp
            # is after last entry in list.
            gs = GridSlice(self, ts, SliceType.GlobalComments, [1])
            gs.addToken(tok, 0, 0, 0)
            self.slices.append(gs)
            return gs

        # search for existing data line (of any type) with the same timestamp
        for idx, gridSlice in enumerate(self.slices):
            # does it need to be before data slice or any slice?
            # if (((*iterator)->getTimestamp() == ts) && (*iterator)->isDataSlice())
            if gridSlice.timestamp == ts:
                # found the correct timestamp on a slice, so add the global comment
                # before the slice.  But don't add if the slice we found is a
                # global comment with the same text.
                if gridSlice.isGlobalComment:
                    if len(gridSlice.parts[0].staves[0].voices) > 0:
                        voice0: GridVoice | None = gridSlice.parts[0].staves[0].voices[0]
                        if (voice0 is not None
                                and voice0.token is not None
                                and tok == voice0.token.text):
                            # do not insert duplicate global comments
                            gs = gridSlice
                            return gs

                gs = GridSlice(self, ts, SliceType.GlobalComments, [1])
                gs.addToken(tok, 0, 0, 0)
                self.slices.insert(idx, gs)
                return gs

            if gridSlice.timestamp > ts:
                # insert before this slice
                gs = GridSlice(self, ts, SliceType.GlobalComments, [1])
                gs.addToken(tok, 0, 0, 0)
                self.slices.insert(idx, gs)
                return gs

        return None

    def addGlobalReference(self, tok: str, timestamp: HumNumIn) -> GridSlice | None:
        ts: HumNum = opFrac(timestamp)
        gs: GridSlice

        if not self.slices or self.slices[-1].timestamp < ts:
            # add a new GridSlice to an empty list or at end of list if timestamp
            # is after last entry in list.
            gs = GridSlice(self, ts, SliceType.ReferenceRecords, [1])
            gs.addToken(tok, 0, 0, 0)
            self.slices.append(gs)
            return gs

        # search for existing data line (of any type) with the same timestamp
        for idx, gridSlice in enumerate(self.slices):
            if gridSlice.timestamp == ts:
                # found the correct timestamp on a slice, so add the global reference
                # before the slice.  But don't add if the slice we found is a
                # global reference with the same text.
                if gridSlice.isReferenceRecord:
                    if len(gridSlice.parts[0].staves[0].voices) > 0:
                        voice0: GridVoice | None = gridSlice.parts[0].staves[0].voices[0]
                        if (voice0 is not None
                                and voice0.token is not None
                                and tok == voice0.token.text):
                            # do not insert duplicate reference records
                            gs = gridSlice
                            return gs

                gs = GridSlice(self, ts, SliceType.ReferenceRecords, [1])
                gs.addToken(tok, 0, 0, 0)
                self.slices.insert(idx, gs)
                return gs

            if gridSlice.timestamp > ts:
                # insert before this slice
                gs = GridSlice(self, ts, SliceType.ReferenceRecords, [1])
                gs.addToken(tok, 0, 0, 0)
                self.slices.insert(idx, gs)
                return gs

        return None

    def addGlobalLayoutAtMeasureStart(self, tok: str) -> GridSlice:
        ts: HumNum = opFrac(self.timestamp)
        gs: GridSlice = GridSlice(self, ts, SliceType.GlobalLayouts, [1])
        gs.addToken(tok, 0, 0, 0)
        self.slices.insert(0, gs)
        return gs

    '''
    //////////////////////////////
    //
    // GridMeasure::transferTokens --
    '''
    def transferTokens(self, outFile: HumdrumFile, recip: bool, firstBar: bool = False) -> bool:
        # If the last data slice duration is zero, then calculate
        # the true duration from the duration of the measure.
        if self.slices:
            lastSlice: GridSlice | None = self.slices[-1]
            if lastSlice is not None and lastSlice.isMeasureSlice and len(self.slices) >= 2:
                endingIdx = len(self.slices) - 2
                while endingIdx != 0 and not self.slices[endingIdx].isDataSlice:
                    endingIdx -= 1
                lastSlice = self.slices[endingIdx]
            else:
                lastSlice = None

            if lastSlice is not None and lastSlice.isDataSlice and lastSlice.duration == 0:
                mts: HumNum = self.timestamp
                mdur: HumNum = self.duration
                sts: HumNum = lastSlice.timestamp
                sliceDur: HumNum = opFrac((mts + mdur) - sts)
                lastSlice.duration = sliceDur

        # in the first bar, we delay the initial barline (and any associated rehearsal mark)
        # until after all the clef, keysig, etc
        doFirstBarlineNow: bool = False
        didFirstBarline: bool = False
        firstBarlineSlice: GridSlice | None = None
        firstBarRehearsalMarkSlices: list[GridSlice] = []

        if self.duration == 0:
            # don't reposition the first barline if the first bar has no notes
            # (i.e. do not treat this as the first barline, even if the caller said to)
            firstBar = False

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
                    if firstBarlineSlice is not None:
                        for rehSlice in firstBarRehearsalMarkSlices:
                            rehSlice.transferTokens(outFile, recip)
                        firstBarlineSlice.transferTokens(outFile, recip)
                    didFirstBarline = True
                    # and the slice that made us do the first barline now...
                    gridSlice.transferTokens(outFile, recip)
                    continue

                if not didFirstBarline and gridSlice.isMeasureSlice and firstBarlineSlice is None:
                    firstBarlineSlice = gridSlice
                elif (not didFirstBarline and gridSlice.isGlobalLayout):
                    savedItForLater: bool = False
                    voice: GridVoice | None = gridSlice.parts[0].staves[0].voices[0]
                    if voice is not None:
                        token: HumdrumToken | None = voice.token
                        if token is not None:
                            if token.text.startswith('!!LO:REH'):
                                firstBarRehearsalMarkSlices.append(gridSlice)
                                savedItForLater = True
                    if not savedItForLater:
                        gridSlice.transferTokens(outFile, recip)
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
#     def appendInitialBarline(self, outFile: HumdrumFile, startBarline: int = 0) -> None:
#         if outFile.lineCount == 0:
#             # strange case which should never happen
#             return
#
#         startBarlineString = str(startBarline)
#         if self.measureNumberString:
#             startBarlineString = self.measureNumberString
#
#         tokenCount: int = outFile[-1].tokenCount
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
#         for _ in range(0, tokenCount):
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
    def ownerGrid(self):  # -> HumGrid:
        return self._ownerGrid

    @ownerGrid.setter
    def ownerGrid(self, newOwnerGrid) -> None:  # newOwnerGrid: HumGrid
        from converter21.humdrum import HumGrid
        if not isinstance(newOwnerGrid, HumGrid):
            raise HumdrumInternalError('invalid newOwnerGrid')
        self._ownerGrid = newOwnerGrid

    # _getIndexedVoice_AppendingIfNecessary appends enough new voices to the list to
    # accommodate voiceIndex, then returns voices[voiceIndex]
    @staticmethod
    def _getIndexedVoice_AppendingIfNecessary(
        voices: list[GridVoice | None],
        voiceIndex: int
    ) -> GridVoice:
        additionalVoicesNeeded: int = voiceIndex + 1 - len(voices)
        for _ in range(0, additionalVoicesNeeded):
            voices.append(GridVoice())

        output: GridVoice | None = voices[voiceIndex]
        if t.TYPE_CHECKING:
            # because we just filled it in
            assert isinstance(output, GridVoice)
        return output

    def addVerseLabels(
        self,
        associatedSlice: GridSlice,
        partIndex: int,
        staffIndex: int,
        verseLabels: list[HumdrumToken | None]
    ) -> None:
        # add these verse labels just before this associatedSlice
        if len(self.slices) == 0:
            # something strange happened: expecting at least one item in measure.
            # associatedSlice is supposed to already be in the measure.
            return

        associatedSliceIdx: int | None = None
        if associatedSlice is None:
            # place at end of measure (associate with imaginary slice just off the end)
            associatedSliceIdx = len(self.slices)
        else:
            # find owning line (associatedSlice)
            foundIt: bool = False
            for associatedSliceIdx in range(len(self.slices) - 1, -1, -1):
                gridSlice: GridSlice = self.slices[associatedSliceIdx]
                if gridSlice is associatedSlice:
                    foundIt = True
                    break
            if not foundIt:
                # cannot find owning line (a.k.a. associatedSlice is not in this GridMeasure)
                return

        # see if the previous slice is a VerseLabels slice we can use
        prevIdx: int = associatedSliceIdx - 1
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
        newSlice: GridSlice

        if associatedSlice is not None:
            newSlice = GridSlice(self, associatedSlice.timestamp, SliceType.VerseLabels)
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


    def addLayoutParameterAtTime(
        self,
        timestamp: HumNum,
        partIndex: int,
        locomment: str,
        beforeAnyNonTextLayouts: bool = False
    ) -> None:
        # find the associated data slice at the timestamp
        associatedSlice: GridSlice | None = None

        for theSlice in self.slices:
            if not theSlice.isDataSlice:
                continue
            if theSlice.timestamp >= timestamp:
                associatedSlice = theSlice
                break

        staffIndex: int = 0
        voiceIndex: int = 0
        self.addLayoutParameter(
            associatedSlice,
            partIndex,
            staffIndex,
            voiceIndex,
            locomment,
            beforeAnyNonTextLayouts=beforeAnyNonTextLayouts
        )

    '''
    //////////////////////////////
    //
    // GridMeasure::addLayoutParameter --
    '''
    def addLayoutParameter(
        self,
        associatedSlice: GridSlice | None,
        partIndex: int,
        staffIndex: int,
        voiceIndex: int,
        locomment: str,
        beforeAnyNonTextLayouts: bool = False
    ) -> None:
        # add this '!LO:' string just before this associatedSlice
        if len(self.slices) == 0:
            # something strange happened: expecting at least one item in measure.
            # associatedSlice is supposed to already be in the measure.
            return

        associatedSliceIdx: int | None = None
        if associatedSlice is None:
            # place at end of measure (associate with imaginary slice just off the end)
            associatedSliceIdx = len(self.slices)
        else:
            # find owning line (associatedSlice)
            foundIt: bool = False
            for associatedSliceIdx in range(len(self.slices) - 1, -1, -1):
                gridSlice: GridSlice = self.slices[associatedSliceIdx]
                if gridSlice is associatedSlice:
                    foundIt = True
                    break
            if not foundIt:
                # cannot find owning line (a.k.a. associatedSlice is not in this GridMeasure)
                return

        if not beforeAnyNonTextLayouts:
            # see if the previous slice is a layout slice we can use
            prevIdx: int = associatedSliceIdx - 1
            prevSlice: GridSlice = self.slices[prevIdx]
            if prevSlice.isLocalLayoutSlice:
                prevStaff: GridStaff = prevSlice.parts[partIndex].staves[staffIndex]
                prevVoice: GridVoice = self._getIndexedVoice_AppendingIfNecessary(prevStaff.voices,
                                                                                  voiceIndex)
                if prevVoice.token is None or prevVoice.token.text == '!':
                    prevVoice.token = HumdrumToken(locomment)
                    return

        insertPoint: int = associatedSliceIdx
        insertSlice: GridSlice | None = associatedSlice
        if beforeAnyNonTextLayouts:
            insertPoint = self.startIdxOfNonTextLayoutGroupBefore(
                associatedSliceIdx,
                partIndex,
                staffIndex,
                voiceIndex
            )
            if insertPoint < len(self.slices):
                insertSlice = self.slices[insertPoint]

        # if we get here, we couldn't use the previous slice, so we need to insert
        # a new Layout slice to use, just before the associated slice.
        newSlice: GridSlice

        if insertSlice is not None:
            newSlice = GridSlice(self, insertSlice.timestamp, SliceType.Layouts)
            newSlice.initializeBySlice(insertSlice)
            self.slices.insert(insertPoint, newSlice)
        else:
            newSlice = GridSlice(self, self.timestamp + self.duration, SliceType.Layouts)
            newSlice.initializeBySlice(self.slices[-1])
            self.slices.append(newSlice)

        newStaff: GridStaff = newSlice.parts[partIndex].staves[staffIndex]
        newVoice: GridVoice = self._getIndexedVoice_AppendingIfNecessary(newStaff.voices,
                                                                         voiceIndex)
        newVoice.token = HumdrumToken(locomment)

    def startIdxOfLayoutGroupBefore(self, sliceIdx: int) -> int:
        for testIdx in reversed(range(0, sliceIdx)):
            # loop backward from sliceIdx-1 to 0
            # We are counting on layout slices having zero duration,
            # since we need to not change timestamps as we walk them.
            if self.slices[testIdx].sliceType != SliceType.Layouts:
                return testIdx + 1
        return 0

    def startIdxOfNonTextLayoutGroupBefore(
        self,
        sliceIdx: int,
        partIdx: int,
        staffIdx: int,
        voiceIdx: int
    ) -> int:
        for testIdx in reversed(range(0, sliceIdx)):
            # loop backward from sliceIdx-1 to 0
            # We are counting on layout slices having zero duration,
            # since we need to not change timestamps as we walk them.
            if self.slices[testIdx].sliceType != SliceType.Layouts:
                # it is not a layout slice; we stop here
                return testIdx + 1

            # it is a layout slice.  Is this voice a non-text layout (i.e. not '!LO:TX')?
            if 0 <= partIdx < len(self.slices[testIdx].parts):
                part: GridPart = self.slices[testIdx].parts[partIdx]
                if 0 <= staffIdx < len(part.staves):
                    staff: GridStaff = part.staves[staffIdx]
                    if 0 <= voiceIdx < len(staff.voices):
                        voice: GridVoice | None = staff.voices[voiceIdx]
                        if voice is not None and voice.token is not None:
                            if voice.token.text.startswith('!LO:TX'):
                                # it is a text layout;
                                # we've passed any non-text layouts; we stop here
                                return testIdx + 1

        return 0


    '''
    //////////////////////////////
    //
    // GridMeasure::addDynamicsLayoutParameters --
    '''
    def addDynamicsLayoutParameters(
        self,
        associatedSlice: GridSlice,
        partIndex: int,
        locomment: str
    ) -> None:
        if len(self.slices) == 0:
            # something strange happened: expecting at least one item in measure.
            # associatedSlice is supposed to already be in the measure
            return

        associatedSliceIdx: int | None = None
        if associatedSlice is None:
            # place at end of measure (associate with imaginary slice just off the end)
            associatedSliceIdx = len(self.slices)
        else:
            # find owning line (associatedSlice)
            foundIt: bool = False
            for associatedSliceIdx in range(len(self.slices) - 1, -1, -1):
                gridSlice: GridSlice = self.slices[associatedSliceIdx]
                if gridSlice is associatedSlice:
                    foundIt = True
                    break
            if not foundIt:
                # cannot find owning line (a.k.a. associatedSlice is not in this GridMeasure)
                return

        # see if the previous slice is a layout slice we can use
        prevIdx: int = associatedSliceIdx - 1
        prevSlice: GridSlice = self.slices[prevIdx]
        if prevSlice.isLocalLayoutSlice:
            prevPart: GridPart = prevSlice.parts[partIndex]
            if prevPart.dynamics is None:
                prevPart.dynamics = HumdrumToken(locomment)
                return

        # if we get here, we couldn't use the previous slice, so we need to insert
        # a new Layout slice to use, just before the associated slice.
        insertPoint: int = associatedSliceIdx
        newSlice: GridSlice

        if associatedSlice is not None:
            newSlice = GridSlice(self, associatedSlice.timestamp, SliceType.Layouts)
            newSlice.initializeBySlice(associatedSlice)
            self.slices.insert(insertPoint, newSlice)
        else:
            newSlice = GridSlice(self, self.timestamp + self.duration, SliceType.Layouts)
            newSlice.initializeBySlice(self.slices[-1])
            self.slices.append(newSlice)

        newPart: GridPart = newSlice.parts[partIndex]
        newPart.dynamics = HumdrumToken(locomment)

    def addHarmonyLayoutParameters(
        self,
        associatedSlice: GridSlice,
        partIndex: int,
        locomment: str
    ) -> None:
        if len(self.slices) == 0:
            # something strange happened: expecting at least one item in measure.
            # associatedSlice is supposed to already be in the measure
            return

        associatedSliceIdx: int | None = None
        if associatedSlice is None:
            # place at end of measure (associate with imaginary slice just off the end)
            associatedSliceIdx = len(self.slices)
        else:
            # find owning line (associatedSlice)
            foundIt: bool = False
            for associatedSliceIdx in range(len(self.slices) - 1, -1, -1):
                gridSlice: GridSlice = self.slices[associatedSliceIdx]
                if gridSlice is associatedSlice:
                    foundIt = True
                    break
            if not foundIt:
                # cannot find owning line (a.k.a. associatedSlice is not in this GridMeasure)
                return

        # see if the previous slice is a layout slice we can use
        prevIdx: int = associatedSliceIdx - 1
        prevSlice: GridSlice = self.slices[prevIdx]
        if prevSlice.isLocalLayoutSlice:
            prevPart: GridPart = prevSlice.parts[partIndex]
            if prevPart.harmony is None:
                prevPart.harmony = HumdrumToken(locomment)
                return

        # if we get here, we couldn't use the previous slice, so we need to insert
        # a new Layout slice to use, just before the associated slice.
        insertPoint: int = associatedSliceIdx
        newSlice: GridSlice

        if associatedSlice is not None:
            newSlice = GridSlice(self, associatedSlice.timestamp, SliceType.Layouts)
            newSlice.initializeBySlice(associatedSlice)
            self.slices.insert(insertPoint, newSlice)
        else:
            newSlice = GridSlice(self, self.timestamp + self.duration, SliceType.Layouts)
            newSlice.initializeBySlice(self.slices[-1])
            self.slices.append(newSlice)

        newPart: GridPart = newSlice.parts[partIndex]
        newPart.harmony = HumdrumToken(locomment)

    '''
    //////////////////////////////
    //
    // GridMeasure::getFirstSpinedSlice --
    '''
    def firstSpinedSlice(self) -> GridSlice | None:
        for tslice in self.slices:
            if tslice is not None and tslice.hasSpines:
                return tslice
        return None

    '''
    //////////////////////////////
    //
    // GridMeasure::getLastSpinedSlice --
    '''
    def lastSpinedSlice(self) -> GridSlice | None:
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

    def measureStyle(self, staffIndex: int) -> MeasureStyle:
        output: MeasureStyle = MeasureStyle.Regular

        if 0 <= staffIndex < len(self.measureStylePerStaff):
            output = self.measureStylePerStaff[staffIndex]

        # print(f'measureStyle({staffIndex}): {output}', file=sys.stderr)

        return output

    def rightBarlineStyle(self, staffIndex: int) -> MeasureStyle:
        output: MeasureStyle = MeasureStyle.Regular

        if 0 <= staffIndex < len(self.measureStylePerStaff):
            output = self.rightBarlineStylePerStaff[staffIndex]

        # print(f'measureStyle({staffIndex}): {output}', file=sys.stderr)

        return output
