# ------------------------------------------------------------------------------
# Name:          GridStaff.py
# Purpose:       HumGrid is an intermediate container for converting into Humdrum
#                syntax.  GridStaff is a class which stores all voice/layer tokens
#                ([GridVoice]) and side tokens (GridSide) for a particular staff
#                in a particular part (GridPart), at a particular moment in time
#                (GridSlice).
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys

from converter21.humdrum import HumdrumInternalError
from converter21.humdrum import HumdrumExportError
from converter21.humdrum import HumNum
from converter21.humdrum import HumdrumToken
from converter21.humdrum import SliceType
from converter21.humdrum import GridVoice
from converter21.humdrum import GridSide


### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

class GridStaff():
    def __init__(self):
        self.voices: [GridVoice] = []
        self.sides: GridSide = GridSide()

    def __str__(self):
        output: str = ''

        for i, gv in enumerate(self.voices):
            if gv is None:
                output += '{nv}'
            else:
                if gv.token is None:
                    output += '{n}'
                else:
                    output += gv.token.text

            if i < len(self.voices) - 1:
                output += '\t'

        if self.sides is not None:
            output += '\t' + str(self.sides)

        return output

    # side property pass-thrus
    @property
    def dynamicsCount(self) -> int:
        if self.sides.dynamics is None:
            return 0
        return 1

    @property
    def dynamics(self) -> HumdrumToken:
        return self.sides.dynamics

    @dynamics.setter
    def dynamics(self, newDynamics: HumdrumToken):
        self.sides.dynamics = newDynamics


    '''
    //////////////////////////////
    //
    // GridStaff::setTokenLayer -- Insert a token at the given voice/layer index.
    //    If there is another token already there, then delete it.  If there
    //    is no slot for the given voice, then create one and fill in all of the
    //    other new ones with NULLs.
    '''
    def setTokenLayer(self, layerIndex: int, token: HumdrumToken, duration: HumNum) -> GridVoice:
        if layerIndex < 0:
            raise HumdrumInternalError(f'Error: layer index is {layerIndex} for {token}')

        if layerIndex > len(self.voices) - 1:
            for _ in range(len(self.voices), layerIndex + 1): # range includes layerIndex
                self.voices.append(None)

        gv: GridVoice = GridVoice(token, duration)
        self.voices[layerIndex] = gv
        return gv

    def setNullTokenLayer(self, layerIndex: int, sliceType: SliceType, nextDur: HumNum):
        if sliceType == SliceType.Invalid:
            return
        if sliceType == SliceType.GlobalLayouts:
            return
        if sliceType == SliceType.GlobalComments:
            return
        if sliceType == SliceType.ReferenceRecords:
            return

        nullStr: str = ''
        if sliceType < SliceType.Data_:
            nullStr = '.'
        elif sliceType <= SliceType.Measure_:
            nullStr = '='
        elif sliceType <= SliceType.Interpretation_:
            nullStr = '*'
        elif sliceType <= SliceType.Spined_:
            nullStr = '!'
        else:
            raise HumdrumInternalError(f'!!STRANGE ERROR: {self}, SLICE TYPE: {sliceType}')

        if layerIndex < len(self.voices):
            if (self.voices[layerIndex] is not None
                    and self.voices[layerIndex].token is not None):
                if self.voices[layerIndex].token.text == nullStr:
				    # there is already a null data token here, so don't
				    # replace it.
                    return
                raise HumdrumExportError('Warning, existing token: \'{self.voices[layerIndex].token.text}\' where a null token should be.')

        token: HumdrumToken = HumdrumToken(nullStr)
        self.setTokenLayer(layerIndex, token, nextDur)

# appendTokenLayer goes here, but no-one calls it

    @property
    def maxVerseCount(self) -> int:
        return 5
