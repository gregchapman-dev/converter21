# ------------------------------------------------------------------------------
# Name:          GridSlice.py
# Purpose:       HumGrid is an intermediate container for converting into Humdrum
#                syntax.  GridSlice is a class which stores a timestamp, a slice type
#                and data for all parts in the given slice (moment in time).
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

from converter21.humdrum import HumdrumInternalError
from converter21.humdrum import HumNum
from converter21.humdrum import HumdrumToken
from converter21.humdrum import HumdrumLine
from converter21.humdrum import HumdrumFile

from converter21.humdrum import SliceType
from converter21.humdrum import GridSide
from converter21.humdrum import GridVoice
from converter21.humdrum import GridStaff
from converter21.humdrum import GridPart
from converter21.humdrum import GridMeasure
from converter21.humdrum import HumGrid

from converter21.humdrum import ScoreData

### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

class GridSlice:
    def __init__(self, measure: GridMeasure, timestamp: HumNum, sliceType: SliceType,
                       partCount: int = 0, oldSlice = None):
        self._timestamp: HumNum = timestamp
        self._type: SliceType = sliceType
        self._ownerGrid: HumGrid = None
        self._measure: GridMeasure = None # enclosing measure
        if measure:
            self._ownerGrid = measure.ownerGrid   # measure's enclosing grid
            self._measure = measure

        self.parts: [GridPart] = []
        if oldSlice is None:
            # GridSlice::GridSlice -- Constructor.  If partcount is positive, then
            #    allocate the desired number of parts (still have to allocate staves
            #    in part before using).
            for _ in range(0, partCount):
                part: GridPart = GridPart()
                staff: GridStaff = GridStaff()
                voice: GridVoice = GridVoice()
                self.parts.append(part)
                part.staves.append(staff)
                staff.voices.append(voice)
        else:
            # This constructor allocates the matching part and staff count of the
            # input oldSlice parameter.  There will be no GridVoices allocated inside
            # the GridStaffs (they will be required to have at least one).
            for oldPart in oldSlice.parts:
                part = GridPart()
                self.parts.append(part)
                for _ in oldPart.staves:
                    staff = GridStaff()
                    part.staves.append(staff)
                    # don't create voices here

    def __str__(self) -> str:
        output: str = 'TS=' + self.timestamp + ' '

        for p, part in enumerate(self.parts):
            output += '(p' + str(p) + ':)'
            if part is None:
                output += '{n}'
                continue

            # part staves
            for s, staff in enumerate(part.staves):
                output += '(s' + str(s) + ':)'
                if staff is None:
                    output += '{n}'
                    continue

                # staff voices
                for v, voice in enumerate(staff.voices):
                    output += '(v' + str(v) + ':)'
                    if voice is None:
                        output += '{n}'
                        continue
                    if voice.token is None:
                        output += '{n}'
                    else:
                        output += voice.token.text

                # staff side
                output += ' sside:' + str(staff.side)

            # part side
            output += ' pside:' + str(part.side)

        return output

    '''
    //////////////////////////////
    //
    // GridSlice::addToken -- Will not allocate part array, but will
    //     grow staff or voice array if needed.
    '''
    def addToken(self, tok: Union[HumdrumToken, str], parti: int, staffi: int, voicei: int):
        if isinstance(tok, str):
            tok = HumdrumToken(tok)

        if not 0 <= parti < len(self.parts):
            raise HumdrumInternalError(
                'Error: part index {} is out of range(0, {})'.format(
                            parti, len(self.parts)))

        if staffi < 0:
            raise HumdrumInternalError('Error: staff index {} < 0'.format(staffi))

        part: GridPart = self.parts[parti]

        # fill in enough staves to get you to staffi
        if staffi >= len(part.staves):
            for _ in range(len(part.staves), staffi+1):
                part.staves.append(GridStaff())

        staff: GridStaff = part.staves[staffi]

        # fill in enough voices to get you to voicei
        if voicei >= len(staff.voices):
            for _ in range(len(staff.voices), voicei+1):
                staff.voices.append(GridVoice())

        voice: GridVoice = staff.voices[voicei]

        # Ok, finally do what you came to do...
        voice.token = tok

    '''
    //////////////////////////////
    //
    // GridSlice::createRecipTokenFromDuration --  Will not be able to
    //   distinguish between triplet notes and dotted normal equivalents,
    //   this can be changed later by checking neighboring durations in the
    //   list for the presence of triplets.
    '''
    @staticmethod
    def _createRecipTokenFromDuration(duration: HumNum) -> HumdrumToken:
        duration /= 4 # convert to quarter note units

        if duration.numerator == 0:
            # if the GridSlice is at the end of a measure, the
            # time between the starttime/endtime of the GridSlice should
            # be subtracted from the endtime of the current GridMeasure.
            return HumdrumToken('g')

        if duration.numerator == 1:
            return HumdrumToken(str(duration.denominator))

        if duration.numerator % 3 == 0:
            dotdur: HumNum = (duration * 2) / 3
            if dotdur.numerator == 1:
                return HumdrumToken(str(dotdur.denominator) + '.')

        # try to fit to two dots here

        # try to fit to three dots here

        return HumdrumToken(str(duration.denominator) + '%' + str(duration.numerator))

    @property
    def sliceType(self) -> SliceType:
        return self._type

    @sliceType.setter
    def sliceType(self, newSliceType: SliceType):
        self._type = newSliceType

    @property
    def isInterpretationSlice(self) -> bool:
        if self.sliceType < SliceType.Measure_:
            return False
        if self.sliceType > SliceType.Interpretation_:
            return False
        return True

    @property
    def isDataSlice(self) -> bool:
        if self.sliceType <= SliceType.Data_:
            return True
        return False

    @property
    def isNoteSlice(self) -> bool:
        return self.sliceType == SliceType.Notes

    @property
    def isGraceSlice(self) -> bool:
        return self.sliceType == SliceType.GraceNotes

    @property
    def isMeasureSlice(self) -> bool:
        return self.sliceType == SliceType.Measures

    @property
    def isClefSlice(self) -> bool:
        return self.sliceType == SliceType.Clefs

    @property
    def isLabelSlice(self) -> bool:
        return self.sliceType == SliceType.Labels

    @property
    def isLabelAbbrSlice(self) -> bool:
        return self.sliceType == SliceType.LabelAbbrs

    @property
    def isTransposeSlice(self) -> bool:
        return self.sliceType == SliceType.Transpositions

    @property
    def isKeySigSlice(self) -> bool:
        return self.sliceType == SliceType.KeySigs

    @property
    def isKeyDesignationSlice(self) -> bool:
        return self.sliceType == SliceType.KeyDesignations

    @property
    def isTimeSigSlice(self) -> bool:
        return self.sliceType == SliceType.TimeSigs

    @property
    def isTempoSlice(self) -> bool:
        return self.sliceType == SliceType.Tempos

    @property
    def isMeterSigSlice(self) -> bool:
        return self.sliceType == SliceType.MeterSigs

    @property
    def isManipulatorSlice(self) -> bool:
        return self.sliceType == SliceType.Manipulators

    @property
    def isLocalLayoutSlice(self) -> bool:
        return self.sliceType == SliceType.Layouts

    @property
    def isInvalidSlice(self) -> bool:
        return self.sliceType == SliceType.Invalid

    @property
    def isGlobalComment(self) -> bool:
        return self.sliceType == SliceType.GlobalComments

    @property
    def isGlobalLayout(self) -> bool:
        return self.sliceType == SliceType.GlobalLayouts

    @property
    def isReferenceRecord(self) -> bool:
        return self.sliceType == SliceType.ReferenceRecords

    @property
    def isOttavaRecord(self) -> bool:
        return self.sliceType == SliceType.Ottavas

    @property
    def hasSpines(self) -> bool:
        if self.sliceType < SliceType.Spined_:
            return True
        return False

    '''
    //////////////////////////////
    //
    // GridSlice::transferTokens -- Create a HumdrumLine and append it to
    //    the data.
    '''
    def transferTokens(self, outFile: HumdrumFile, recip: bool):
        line: HumdrumLine = HumdrumLine()
        voice: GridVoice = None
        emptyStr: str = '.'

        if self.isMeasureSlice:
            if len(self.parts) > 0:
                if len(self.parts[0].staves[0].voices) > 0:
                    voice = self.parts[0].staves[0].voices[0]
                    if voice.token is not None:
                        emptyStr = voice.token.text
                    else:
                        emptyStr = '=YYYYYY'
                else:
                    emptyStr = '=YYYYYY'
        elif self.isInterpretationSlice:
            emptyStr = '*'
        elif self.isLocalLayoutSlice:
            emptyStr = '!'
        elif not self.hasSpines:
            emptyStr = '???'

        if recip:
            token: HumdrumToken = None

            if self.isNoteSlice:
                token = self._createRecipTokenFromDuration(self.duration)
            elif self.isClefSlice:
                token = HumdrumToken('*')
                emptyStr = '*'
            elif self.isMeasureSlice:
                if len(self.parts[0].staves[0]) > 0:
                    voice = self.parts[0].staves[0].voices[0]
                    token = HumdrumToken(voice.token.text)
                else:
                    token = HumdrumToken('=XXXXX')
                emptyStr = token.text
            elif self.isInterpretationSlice:
                token = HumdrumToken('*')
                emptyStr = '*'
            elif self.isGraceSlice:
                token = HumdrumToken('q')
                emptyStr = '.'
            elif self.hasSpines:
                token = HumdrumToken('55')
                emptyStr = '!'

            if token is not None:
                if self.hasSpines:
                    line.appendToken(token)
                else:
                    token = None

        # extract the Tokens from each part/staff
        for p, part in enumerate(reversed(self.parts)):
            if not self.hasSpines and p != 0:
                continue
            for s, staff in enumerate(reversed(part.staves)):
                if not self.hasSpines and s != 0:
                    continue
                if len(staff.voices) == 0:
                    # LATER: fix this later.  For now if there are no notes
                    # LATER: ... on the staff, add a null token.  Fix so that
                    # LATER: ... all open voices are given null tokens.
                    line.appendToken(HumdrumToken(emptyStr))
                else:
                    for voice in reversed(staff.voices):
                        if voice is not None and voice.token is not None:
                            line.appendToken(voice.token)
                            voice.forgetToken()
                        else:
                            line.appendToken(HumdrumToken(emptyStr))

                if not self.hasSpines:
                    # Don't add sides to non-spined lines
                    continue

                maxxcount: int = self.getXmlIdCount(p, s)
                maxvcount: int = self.getVerseCount(p, s)
                maxhcount: int = self.getHarmonyCount(p, s)
                maxfcount: int = self.getFiguredBassCount(p, s)
                self.transferSidesFromStaff(line, staff, emptyStr,
                                   maxxcount, maxvcount, maxhcount, maxfcount)

            if not self.hasSpines:
                # Don't add sides to non-spined lines
                continue

            maxxcount: int = self.getXmlIdCount(p)
            maxvcount: int = self.getVerseCount(p)
            maxhcount: int = self.getHarmonyCount(p, -1)
            maxdcount: int = self.getDynamicsCount(p)
            maxfcount: int = self.getFiguredBassCount(p)
            self.transferSidesFromPart(line, part, p, emptyStr,
                               maxxcount, maxvcount, maxhcount,
                               maxdcount, maxfcount)

        outFile.appendLine(line)

    @property
    def measureDuration(self) -> HumNum:
        if not self.measure:
            return HumNum(-1)
        return self.measure.duration

    @property
    def measureTimestamp(self) -> HumNum:
        if not self.measure:
            return HumNum(-1)
        return self.measure.timestamp

    '''
    //////////////////////////////
    //
    // GridSlice::getVerseCount --
    '''
    def getVerseCount(self, partIndex: int, staffIndex: int = -1) -> int:
        grid: HumGrid = self.ownerGrid
        if grid is None:
            return 0

        return grid.getVerseCount(partIndex, staffIndex)

    '''
    //////////////////////////////
    //
    // GridSlice::getHarmonyCount --
    //    default value: staffindex = -1; (currently not looking for
    //        harmony data attached directly to staff (only to part.)
    '''
    def getHarmonyCount(self, partIndex: int, staffIndex: int = -1) -> int:
        grid: HumGrid = self.ownerGrid
        if grid is None:
            return 0

        if staffIndex >= 0:
            # ignoring staff-level harmony
            return 0

        return grid.getHarmonyCount(partIndex)

    '''
    //////////////////////////////
    //
    // GridSlice::getXmlidCount --
    //    default value: staffindex = -1; (currently not looking for
    //        harmony data attached directly to staff (only to part.)
    '''
    def getXmlIdCount(self, partIndex: int, _unusedstaffIndex: int = -1) -> int:
        grid: HumGrid = self.ownerGrid
        if grid is None:
            return 0
        # should probably adjust to staffindex later:
        return grid.getXmlIdCount(partIndex)

    '''
    //////////////////////////////
    //
    // GridSlice::getDynamicsCount -- Return 0 if no dynamics, otherwise typically returns 1.
    '''
    def getDynamicsCount(self, partIndex: int, staffIndex: int = -1) -> int:
        grid: HumGrid = self.ownerGrid
        if grid is None:
            return 0

        if staffIndex >= 0:
            # ignoring staff-level dynamics
            return 0

        return grid.getDynamicsCount(partIndex)

    '''
    //////////////////////////////
    //
    // GridSlice::getFiguredBassCount -- Return 0 if no figured bass; otherwise,
    //     typically returns 1.
    '''
    def getFiguredBassCount(self, partIndex: int, staffIndex: int = -1) -> int:
        grid: HumGrid = self.ownerGrid
        if grid is None:
            return 0

        if staffIndex >= 0:
            # ignoring staff-level figured bass
            return 0

        return grid.getFiguredBassCount(partIndex)

    '''
    //////////////////////////////
    //
    // GridSlice::transferSides --
    '''

    # this version is used to transfer Sides from the Part
    @staticmethod
    def transferSidesFromPart(line: HumdrumLine, part: GridPart, _unusedpartIndex: int,
                              emptyStr: str, _unusedmaxxcount: int, maxvcount: int,
                              maxhcount: int, maxdcount: int, maxfcount: int):
        sides: GridSide = part.sides
        xcount: int = sides.xmlIdCount
        hcount: int = sides.harmonyCount
        vcount: int = sides.verseCount

        # XMLID
        if xcount > 0:
            xmlId: HumdrumToken = sides.xmlId
            if xmlId is not None:
                line.appendToken(xmlId)
                sides.xmlId = None
            else:
                line.appendToken(HumdrumToken(emptyStr))

        # VERSES
        for i in range(0, vcount):
            verse: HumdrumToken = sides.getVerse(i)
            if verse is not None:
                line.appendToken(verse)
                sides.setVerse(i, None) # BUG: was sides.detachHarmony
            else:
                line.appendToken(HumdrumToken(emptyStr))

        for i in range(vcount, maxvcount):
            line.appendToken(HumdrumToken(emptyStr))

        # DYNAMICS
        if maxdcount > 0:
            dynamics: HumdrumToken = sides.dynamics
            if dynamics is not None:
                line.appendToken(dynamics)
                sides.dynamics = None
            else:
                line.appendToken(HumdrumToken(emptyStr))

        # FIGURED BASS
        if maxfcount > 0:
            figuredBass: HumdrumToken = sides.figuredBass
            if figuredBass is not None:
                line.appendToken(figuredBass)
                sides.figuredBass = None
            else:
                line.appendToken(HumdrumToken(emptyStr))

        # HARMONY
        for i in range(0, hcount):
            harmony: HumdrumToken = sides.harmony
            if harmony is not None:
                line.appendToken(harmony)
                sides.harmony = None
            else:
                line.appendToken(HumdrumToken(emptyStr))

        for i in range(hcount, maxhcount):
            line.appendToken(HumdrumToken(emptyStr))

    # this version is used to transfer Sides from the Staff
    @staticmethod
    def transferSidesFromStaff(line: HumdrumLine, staff: GridStaff, emptyStr: str,
                               maxxcount: int, maxvcount: int,
                               _unusedmaxhcount: int, maxfcount: int):
        sides: GridSide = staff.sides

        # existing verses:
        vcount: int = sides.verseCount

        # xcount: int = sides.xmlIdCount
        fcount: int = sides.figuredBassCount

        # there should not be any harmony attached to staves
        # (only to parts, so hcount should only be zero):
        hcount: int = sides.harmonyCount

        # XMLID
        if maxxcount > 0:
            xmlId: HumdrumToken = sides.xmlId
            if xmlId is not None:
                line.appendToken(xmlId)
                sides.xmlId = None
            else:
                line.appendToken(HumdrumToken(emptyStr))

        # VERSES
        for i in range(0, vcount):
            verse: HumdrumToken = sides.getVerse(i)
            if verse is not None:
                line.appendToken(verse)
                sides.setVerse(i, None)
            else:
                line.appendToken(HumdrumToken(emptyStr))

        for i in range(vcount, maxvcount):
            line.appendToken(HumdrumToken(emptyStr))

        # HARMONY
        for i in range(0, hcount):
            harmony: HumdrumToken = sides.harmony
            if harmony is not None:
                line.appendToken(harmony)
                sides.harmony = None
            else:
                line.appendToken(HumdrumToken(emptyStr))

        # FIGURED BASS
        for i in range(0, fcount):
            figuredBass: HumdrumToken = sides.figuredBass
            if figuredBass is not None:
                line.appendToken(figuredBass)
                sides.figuredBass = None
            else:
                line.appendToken(HumdrumToken(emptyStr))

        for i in range(fcount, maxfcount):
            line.appendToken(HumdrumToken(emptyStr))

    '''
    //////////////////////////////
    //
    // GridSlice::initializePartStaves -- Also initialize sides
        No voices in staves though, apparently. --gregc
    '''
    def initializePartStaves(self, scoreData: ScoreData):
        self.parts = []
        for partData in scoreData.parts:
            newPart: GridPart = GridPart()
            self.parts.append(newPart)
            for _staffData in partData.staves:
                newStaff: GridStaff = GridStaff()
                newPart.staves.append(newStaff)

    '''
    //////////////////////////////
    //
    // GridSlice::initializeByStaffCount -- Initialize with parts containing a single staff.
            ... and put a single voice in that staff, apparently. --gregc
    '''
    def initializeByStaffCount(self, staffCount: int):
        self.parts = []
        for _ in range(0, staffCount):
            newPart: GridPart = GridPart()
            self.parts.append(newPart)

            newStaff: GridStaff = GridStaff()
            newPart.staves.append(newStaff)

            newVoice: GridVoice = GridVoice()
            newStaff.voices.append(newVoice)

    '''
    //////////////////////////////
    //
    // GridSlice::initializeBySlice -- Allocate parts/staves/voices counts by an existing slice.
    //   Presuming that the slice is not already initialized with content.
    '''
    def initializeBySlice(self, oldSlice):
        self.parts = []
        for oldPart in oldSlice.parts:
            newPart = GridPart()
            self.parts.append(newPart)
            for oldStaff in oldPart.staves:
                newStaff = GridStaff()
                newPart.staves.append(newStaff)
                for _oldVoice in oldStaff.voices:
                    newVoice = GridVoice()
                    newStaff.voices.append(newVoice)

    '''
    //////////////////////////////
    //
    // GridSlice::getDuration -- Return the duration of the slice in
    //      quarter notes.
    '''
    @property
    def duration(self) -> HumNum:
        return self._duration

    '''
    //////////////////////////////
    //
    // GridSlice::setDuration --
    '''
    @duration.setter
    def duration(self, newDuration: HumNum):
        self._duration = newDuration

    '''
    //////////////////////////////
    //
    // GridSlice::getTimestamp --
    '''
    @property
    def timestamp(self) -> HumNum:
        return self._timestamp

    '''
    //////////////////////////////
    //
    // GridSlice::setTimestamp --
    '''
    @timestamp.setter
    def timestamp(self, newTimestamp: HumNum):
        self._timestamp = newTimestamp

    '''
    //////////////////////////////
    //
    // GridSlice::setOwner --
    '''
    @property
    def ownerGrid(self) -> HumGrid:
        return self._ownerGrid

    '''
    //////////////////////////////
    //
    // GridSlice::getOwner --
    '''
    @ownerGrid.setter
    def ownerGrid(self, newOwnerGrid: HumGrid):
        self._ownerGrid = newOwnerGrid

    '''
    //////////////////////////////
    //
    // GridSlice::getMeasure --
    '''
    @property
    def measure(self) -> GridMeasure:
        return self._measure

    '''
    //////////////////////////////
    //
    // GridSlice::invalidate -- Mark the slice as invalid, which means that
    //    it should not be transferred to the output Humdrum file in HumGrid.
    //    Tokens stored in the GridSlice will be deleted by GridSlice when it
    //    is destroyed.
    '''
    def invalidate(self):
        self.sliceType = SliceType.Invalid
        # should only do with 0 duration slices, but force to 0 if not already.
        self.duration = HumNum(0)

    '''
    //////////////////////////////
    //
    // GridSlice::reportVerseCount --
    '''
    def reportVerseCount(self, partIndex: int, staffIndex: int, count: int):
        if not self.ownerGrid:
            return

        self.ownerGrid.reportVerseCount(partIndex, staffIndex, count)

    '''
    //////////////////////////////
    //
    // GridSlice::getNullTokenForSlice --
    '''
    def nullTokenStringForSlice(self) -> str:
        if self.isDataSlice:
            return '.'
        if self.isInterpretationSlice:
            return '*'
        if self.isMeasureSlice:
            return '='
        if not self.hasSpines:
            return '!!'
        return '!'