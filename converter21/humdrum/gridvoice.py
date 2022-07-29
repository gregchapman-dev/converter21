# ------------------------------------------------------------------------------
# Name:          GridVoice.py
# Purpose:       HumGrid is an intermediate container for converting into Humdrum
#                syntax.  GridVoice is a class which stores a HumdrumToken in that
#                grid.  It's what's in the voice/spine (GridVoice), within a
#                particular staff/group-of-spines (GridStaff), within a particular
#                (possibly multi-staff) part (GridPart), at a particular moment
#                in time, i.e. on a particular HumdrumLine (GridSlice).
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

from music21.common import opFrac

from converter21.humdrum import HumNum, HumNumIn
from converter21.humdrum import HumdrumToken

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class GridVoice:
    def __init__(
            self,
            token: t.Optional[t.Union[HumdrumToken, str]] = None,
            duration: HumNumIn = opFrac(0)
    ) -> None:
        if isinstance(token, str):
            token = HumdrumToken(token)
        self._token: t.Optional[HumdrumToken] = token

        self._nextDur = opFrac(duration)
#         self._prevDur = opFrac(0) # appears to be unused (never set to anything but zero)
        self._isTransfered: bool = False

    def __str__(self) -> str:
        if self._token is None:
            return '{n}'
        return self._token.text

    '''
    //////////////////////////////
    //
    // GridVoice::isTransfered -- True if token was copied to a HumdrumFile
    //      object.
    // GridVoice::setTransfered -- True if the object should not be
    //    deleted with the object is destroyed.  False if the token
    //    is not NULL and should be deleted when object is destroyed.
    '''
    @property
    def isTransfered(self) -> bool:
        return self._isTransfered

    @isTransfered.setter
    def isTransfered(self, newIsTransfered: bool) -> None:
        self._isTransfered = newIsTransfered

    '''
    //////////////////////////////
    //
    // GridVoice::getToken --
    '''
    @property
    def token(self) -> t.Optional[HumdrumToken]:
        return self._token

    @token.setter
    def token(self, newToken: t.Optional[t.Union[HumdrumToken, str]]) -> None:
        if isinstance(newToken, str):
            newToken = HumdrumToken(newToken)
        self._token = newToken

        self._isTransfered = False

    '''
    //////////////////////////////
    //
    // GridVoice::isNull -- returns true if token is NULL or ".".
    '''
    @property
    def isNull(self) -> bool:
        if self._token is None:
            return True
        return self._token.isNull

    '''
    //////////////////////////////
    //
    // GridVoice::getDuration -- Return the total duration of the
    //   durational item, the sum of the nextdur and prevdur.
    //
    '''
    @property
    def duration(self) -> HumNum:
        return self._nextDur  # + self._prevDur # prevDur is always zero, it seems

    @duration.setter
    def duration(self, newDuration: HumNumIn) -> None:
        self._nextDur = opFrac(newDuration)
#         self._prevDur = opFrac(0)

    '''
    //////////////////////////////
    //
    // GridVoice::forgetToken -- The HumdrumToken was passed off
    //      to some other object which is now responsible for
    //      deleting it.
    '''
    def forgetToken(self) -> None:
        self.isTransfered = True
        self.token = None
