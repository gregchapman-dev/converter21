# ------------------------------------------------------------------------------
# Name:          HumAddress.py
# Purpose:       Used to store the location of a token in a HumdrumFile.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import typing as t

from converter21.humdrum import HumdrumSyntaxError

class HumAddress:
    def __init__(self) -> None:
        from converter21.humdrum import HumdrumToken
        from converter21.humdrum import HumdrumLine
        self.trackNum: t.Optional[int] = None
        self._subTrack: int = -1
        self._subTrackCount: int = 0
        self._fieldIndex: int = -1
        self._ownerLine: t.Optional[HumdrumLine] = None
        self._spining: str = ''

        # cache of self.ownerLine.trackStart(self.trackNum)
        self._dataTypeTokenCached: t.Optional[HumdrumToken] = None

    '''
    //////////////////////////////
    //
    // HumAddress::getLineIndex -- Returns the line index in the owning HumdrumFile
    //    for the token associated with the address.  Returns -1 if not owned by a
    //    HumdrumLine (or line assignments have not been made for tokens in the
    //    file).
    '''
    @property
    def lineIndex(self) -> int:
        if self._ownerLine is None:
            return -1
        return self._ownerLine.lineIndex

    '''
    //////////////////////////////
    //
    // HumAddress::getLineNumber --  Similar to getLineIndex() but adds one.
    '''
    @property
    def lineNumber(self) -> int:
        return self.lineIndex + 1

    '''
    //////////////////////////////
    //
    // HumAddress::getTrack -- The track number of the given spine.  This is the
    //   first number in the spine info string.  The track number is the same
    //   as a spine number.
    // HumAddress::setTrack -- Set the track number of the associated token.
    //   This should always be the first number in the spine information string,
    //   or -1 if the spine info is empty.  Tracks are limited to an arbitrary
    //   count of 1000 (could be increased in the future if needed).  This function
    //   is used by the HumdrumFileStructure class.
    '''
    @property
    def track(self) -> t.Optional[int]:
        return self.trackNum

    @track.setter
    def track(self, newTrack: t.Optional[int]) -> None:
        if newTrack is None or newTrack < 0:
            newTrack = None
        elif newTrack > 1000:
            raise HumdrumSyntaxError("too many tracks (limit is 1000)")
        self.trackNum = newTrack
        # blow away self._dataTypeTokenCached since it depends on self.trackNum
        self._dataTypeTokenCached = None

    '''
    //////////////////////////////
    //
    // HumAddress::getSubtrack -- The subtrack number of the given spine.  This
    //   functions in a similar manner to layer numbers in MEI data.  The first
    //   sub-spine of a spine is always subtrack 1, regardless of whether or not
    //   an exchange manipulator (*x) was used to switch the left-to-right ordering
    //   of the spines in the file.  All sub-spines regardless of their splitting
    //   origin are given sequential subtrack numbers.  For example if the spine
    //   info is "(1)a"/"((1)b)a"/"((1)b)b" -- the spine is split, then the second
    //   sub-spine only is split--then the sub-spines are labeled as sub-tracks "1",
    //   "2", "3" respectively.  When a track has only one sub-spine (i.e., it has
    //   been split), the subtrack value will be "0".
    // HumAddress::setSubtrack -- Set the subtrack of the spine.
    //   If the token is the only one active for a spine, the subtrack should
    //   be set to zero.  If there are more than one sub-tracks for the spine, this
    //   is the one-offset index of the spine (be careful if a sub-spine column
    //   is exchanged with another spine other than the one from which it was
    //   created.  In this case the subtrack number is not useful to calculate
    //   the field index of other sub-tracks for the given track.
    //   This function is used by the HumdrumFileStructure class.
    '''
    @property
    def subTrack(self) -> int:
        if self.subTrackCount == 1:
            return 0
        return self._subTrack

    @subTrack.setter
    def subTrack(self, newSubTrack: int) -> None:
        # no negative subtracks
        newSubTrack = max(newSubTrack, 0)
        if newSubTrack > 1000:
            raise HumdrumSyntaxError("too many subTracks (limit is 1000)")
        self._subTrack = newSubTrack
    '''
    //////////////////////////////
    //
    // HumAddress::getSubtrackCount -- The number of subtrack spines for a
    //   given spine on the owning HumdurmLine.  Returns 0 if spine analysis
    //   has not been done, or if the line does not have spines (i.e., reference
    //   records, global comments and empty lines).
    '''
    @property
    def subTrackCount(self) -> int:
        return self._subTrackCount

    @subTrackCount.setter
    def subTrackCount(self, newSubTrackCount: int) -> None:
        self._subTrackCount = newSubTrackCount

    '''
    //////////////////////////////
    //
    // HumAddress::getFieldIndex -- Returns the field index on the line of the
    //     token associated with the address.
    // HumAddress::setFieldIndex -- Set the field index of associated token
    //   in the HumdrumLine owner.  If the token is now owned by a HumdrumLine,
    //   then the input parameter should be -1.
    '''
    @property
    def fieldIndex(self) -> int:
        return self._fieldIndex

    @fieldIndex.setter
    def fieldIndex(self, newFieldIndex: int) -> None:
        self._fieldIndex = newFieldIndex

    @property
    def fieldNumber(self) -> int:
        return self.fieldIndex + 1

    '''
    //////////////////////////////
    //
    // HumAddress::getSpineInfo -- Return the spine information for the token
    //     associated with the address.  Examples: "1" the token is in the first
    //     (left-most) spine, and there are no active sub-spines for the spine.
    //     "(1)a"/"(1)b" are the spine descriptions of the two sub-spines after
    //     a split manipulator (*^).  "((1)a)b" is the second sub-spines of the
    //     first sub-spine for spine 1.
    // HumAddress::setSpineInfo -- Set the spine description of the associated
    //     token.  For example "2" for the second spine (from the left), or
    //     "((2)a)b" for a sub-spine created as the left sub-spine of the main
    //     spine and then as the right sub-spine of that sub-spine.  This function
    //     is used by the HumdrumFileStructure class.
    '''
    @property
    def spineInfo(self) -> str:
        return self._spining

    @spineInfo.setter
    def spineInfo(self, newSpineInfo: str) -> None:
        self._spining = newSpineInfo

    '''
    //////////////////////////////
    //
    // HumAddress::getLine -- return the HumdrumLine which owns the token
    //    associated with this address.  Returns NULL if it does not belong
    //    to a HumdrumLine object.
    // HumAddress::setOwner -- Stores a pointer to the HumdrumLine on which
    //   the token associated with this address belongs.  When not owned by
    //   a HumdrumLine, the parameter's value should be NULL.
    '''
    @property
    def ownerLine(self):  # returns t.Optional[HumdrumLine]
        return self._ownerLine

    @ownerLine.setter
    def ownerLine(self, newOwnerLine) -> None:  # newOwnerLine: t.Optional[HumdrumLine]
        self._ownerLine = newOwnerLine
        # blow away cache of dataType, because it depends on ownerLine
        self._dataTypeTokenCached = None

    '''
    //////////////////////////////
    //
    // HumAddress::hasOwner -- Returns true if a HumdrumLine owns the token
    //    associated with the address.
    '''
    @property
    def hasOwnerLine(self) -> bool:
        return self.ownerLine is not None

    '''
    //////////////////////////////
    //
    // HumAddress::getDataType -- Return the exclusive interpretation string of the
    //    token associated with the address.
    //
    '''
    @property
    def dataType(self):  # -> HumdrumToken
        if self._dataTypeTokenCached is not None:
            return self._dataTypeTokenCached

        from converter21.humdrum import HumdrumToken
        if self.ownerLine is None:
            return HumdrumToken('')

        tok = self.ownerLine.trackStart(self.track)
        if tok is None:
            return HumdrumToken('')

        # cache it
        self._dataTypeTokenCached = tok

        return tok

    '''
    //////////////////////////////
    //
    // HumAddress::getTrackString --  Return the track and subtrack as a string.
    //      The returned string will have the track number if the sub-spine value
    //      is zero.  The optional separator parameter is used to separate the
    //      track number from the subtrack number.
    // default value: separator = "."

        I'll add the non-property getter (with separator) if someone calls it.
        For now this is a property. --gregc
    '''
    @property
    def trackString(self) -> str:
        if self.subTrack > 0:
            return str(self.track) + '.' + str(self.subTrack)

        return str(self.track)
