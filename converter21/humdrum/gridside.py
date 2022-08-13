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
import typing as t

from converter21.humdrum import HumdrumToken

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class GridSide:
    def __init__(self) -> None:
        # there may be >1 verse of lyrics for a note
        self._verses: t.List[t.Optional[HumdrumToken]] = []
        self._harmony: t.Optional[HumdrumToken] = None
        self._xmlId: t.Optional[HumdrumToken] = None
        self._dynamics: t.Optional[HumdrumToken] = None
        self._figuredBass: t.Optional[HumdrumToken] = None

    def __str__(self) -> str:
        outstr: str = ' ['
        if self.xmlIdCount > 0:
            outstr += 'xmlid:' + str(self.xmlId)
        if self.verseCount > 0:
            outstr += 'verse:'
            for i, verse in enumerate(self._verses):
                if verse is not None:
                    outstr += verse.text
                if i < self.verseCount:
                    outstr += '; '
        if self.dynamicsCount > 0:
            outstr += 'dyn:' + str(self.dynamics)
        if self.harmonyCount > 0:
            outstr += 'harm:' + str(self.harmony)
        outstr += '] '
        return outstr

    @property
    def verseCount(self) -> int:
        return len(self._verses)

    def getVerse(self, index: int) -> t.Optional[HumdrumToken]:
        if 0 <= index < self.verseCount:
            return self._verses[index]
        return None

    def setVerse(self, index: int, token: t.Optional[t.Union[HumdrumToken, str]]) -> None:
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
            for _ in range(self.verseCount, index + 1):  # verseCount through index, inclusive
                self._verses.append(None)
            self._verses[index] = token

    @property
    def harmonyCount(self) -> int:
        if self._harmony is None:
            return 0
        return 1

    @property
    def harmony(self) -> t.Optional[HumdrumToken]:
        return self._harmony

    @harmony.setter
    def harmony(self, newHarmony: t.Optional[HumdrumToken]) -> None:
        self._harmony = newHarmony

    @property
    def xmlIdCount(self) -> int:
        if self._xmlId is None:
            return 0
        return 1

    @property
    def xmlId(self) -> t.Optional[HumdrumToken]:
        return self._xmlId

    @xmlId.setter
    def xmlId(self, newXmlId: t.Optional[HumdrumToken]) -> None:
        self._xmlId = newXmlId

    @property
    def dynamicsCount(self) -> int:
        if self._dynamics is None:
            return 0
        return 1

    @property
    def dynamics(self) -> t.Optional[HumdrumToken]:
        return self._dynamics

    @dynamics.setter
    def dynamics(self, newDynamics: t.Optional[HumdrumToken]) -> None:
        self._dynamics = newDynamics

    @property
    def figuredBassCount(self) -> int:
        if self._figuredBass is None:
            return 0
        return 1

    @property
    def figuredBass(self) -> t.Optional[HumdrumToken]:
        return self._figuredBass

    @figuredBass.setter
    def figuredBass(self, newFiguredBass: t.Optional[HumdrumToken]) -> None:
        self._figuredBass = newFiguredBass
