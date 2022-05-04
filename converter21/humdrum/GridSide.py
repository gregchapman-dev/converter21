# ------------------------------------------------------------------------------
# Name:          GridSide.py
# Purpose:       HumGrid is an intermediate container for converting into Humdrum
#                syntax.  GridSide is a class which stores the "side" tokens for
#                a particular moment in time (GridSlice) of a staff (GridStaff) or
#                part (GridPart).
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

from converter21.humdrum import HumdrumToken

### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

class GridSide:
    def __init__(self):
        self._verses: [HumdrumToken] = [] # there may be more than one verse of lyrics for a note
        self._harmony: HumdrumToken = None
        self._xmlId: HumdrumToken = None
        self._dynamics: HumdrumToken = None
        self._figuredBass: HumdrumToken = None

    def __str__(self):
        outstr: str = ' ['
        if self.xmlIdCount > 0:
            outstr += 'xmlid:' + self.xmlId
        if self.verseCount > 0:
            outstr += 'verse:'
            for i, verse in enumerate(self._verses):
                outstr += verse.text
                if i < self.verseCount:
                    outstr += '; '
        if self.dynamicsCount > 0:
            outstr += 'dyn:' + self.dynamics.text
        if self.harmonyCount > 0:
            outstr += 'harm:' + self.harmony.text
        outstr += '] '
        return outstr

    @property
    def verseCount(self) -> int:
        return len(self._verses)

    def getVerse(self, index: int) -> HumdrumToken:
        if 0 <= index < self.verseCount:
            return self._verses[index]
        return None

    def setVerse(self, index: int, token: Union[HumdrumToken, str]):
        if isinstance(token, str):
            # make it into a proper token
            token = HumdrumToken(token)

        if index == self.verseCount:
            self._verses.append(token)
        elif index < self.verseCount:
            # Insert in a slot which might already have a verse token
            self._verses[index] = token
        else:
            # add more than one verse spot, and insert verse:
            for _ in range(self.verseCount, index+1): # verseCount through index, inclusive
                self._verses.append(None)
            self._verses[index] = token

    @property
    def harmonyCount(self) -> int:
        if self._harmony is None:
            return 0
        return 1

    @property
    def harmony(self) -> HumdrumToken:
        return self._harmony

    @harmony.setter
    def harmony(self, newHarmony: HumdrumToken):
        self._harmony = newHarmony

    @property
    def xmlIdCount(self) -> int:
        if self._xmlId is None:
            return 0
        return 1

    @property
    def xmlId(self) -> HumdrumToken:
        return self._xmlId

    @xmlId.setter
    def xmlId(self, newXmlId: HumdrumToken):
        self._xmlId = newXmlId

    @property
    def dynamicsCount(self) -> int:
        if self._dynamics is None:
            return 0
        return 1

    @property
    def dynamics(self) -> HumdrumToken:
        return self._dynamics

    @dynamics.setter
    def dynamics(self, newDynamics: HumdrumToken):
        self._dynamics = newDynamics

    @property
    def figuredBassCount(self) -> int:
        if self._figuredBass is None:
            return 0
        return 1

    @property
    def figuredBass(self) -> HumdrumToken:
        return self._figuredBass

    @figuredBass.setter
    def figuredBass(self, newFiguredBass: HumdrumToken):
        self._figuredBass = newFiguredBass
