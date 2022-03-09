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
from typing import Union

from converter21.humdrum import HumdrumInternalError
from converter21.humdrum import HumNum
from converter21.humdrum import HumdrumToken

### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

class GridVoice:
    def __init__(self, token: Union[HumdrumToken,str] = None, duration: HumNum = HumNum(0)):
        self._token: HumdrumToken = None
        if isinstance(token, HumdrumToken) or token is None:
            self._token = token
        elif isinstance(token, str):
            self._token = HumdrumToken(token)
        else:
            raise HumdrumInternalError(f'invalid type of token: {token}')

        self._nextDur = duration
#         self._prevDur = HumNum(0) # appears to be unused (never set to anything but zero)
        self._isTransfered: bool = False

    def __str__(self) -> str:
        if self.token is None:
            return '{n}'
        return self.token.text

    '''
    //////////////////////////////
    //
    // GridVoice::isTransfered -- True if token was copied to a HumdrumFile
    //      object.
    '''
    @property
    def isTransfered(self) -> bool:
        return self._isTransfered

    '''
    //////////////////////////////
    //
    // GridVoice::setTransfered -- True if the object should not be
    //    deleted with the object is destroyed.  False if the token
    //    is not NULL and should be deleted when object is destroyed.
    '''
    @isTransfered.setter
    def isTransfered(self, newIsTransfered: bool):
        self._isTransfered = newIsTransfered

    '''
    //////////////////////////////
    //
    // GridVoice::getToken --
    '''
    @property
    def token(self) -> HumdrumToken:
        return self._token

    '''
    //////////////////////////////
    //
    // GridVoice::setToken --
    '''
    @token.setter
    def token(self, newToken: Union[HumdrumToken, str]):
        if isinstance(newToken, HumdrumToken) or newToken is None:
            self._token = newToken
        elif isinstance(newToken, str):
            self._token = HumdrumToken(newToken)
        else:
            raise HumdrumInternalError(f'invalid type of token: {newToken}')

        self._isTransfered = False

    '''
    //////////////////////////////
    //
    // GridVoice::isNull -- returns true if token is NULL or ".".
    '''
    @property
    def isNull(self) -> bool:
        if self.token is None:
            return True
        return self.token.isNull

    '''
    //////////////////////////////
    //
    // GridVoice::getDuration -- Return the total duration of the
    //   durational item, the sum of the nextdur and prevdur.
    //
    '''
    @property
    def duration(self) -> HumNum:
        return self._nextDur # + self._prevDur # prevDur is always zero, it seems

    @duration.setter
    def duration(self, newDuration: HumNum):
        self._nextDur = newDuration
#         self._prevDur = HumNum(0)

    '''
    //////////////////////////////
    //
    // GridVoice::forgetToken -- The HumdrumToken was passed off
    //      to some other object which is now responsible for
    //      deleting it.
    '''
    def forgetToken(self):
        self.isTransfered = True
        self.token = None
