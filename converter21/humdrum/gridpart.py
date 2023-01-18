# ------------------------------------------------------------------------------
# Name:          GridPart.py
# Purpose:       HumGrid is an intermediate container for converting into Humdrum
#                syntax.  GridPart is a class which stores all information (notes,
#                dynamics, lyrics, etc) for a particular part (which may have more
#                than one staff), for a particular moment in time (GridSlice).
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
from converter21.humdrum import GridStaff
from converter21.humdrum import GridSide

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class GridPart:
    def __init__(self) -> None:
        self.staves: t.List[GridStaff] = []
        self.sides: GridSide = GridSide()
        self._partName: str = ''

    def __str__(self) -> str:
        output: str = ''
        for s, staff in enumerate(self.staves):
            output += '(s' + str(s) + ':)'
            if staff is None:
                output += '{n}'
                continue
            for v, voice in enumerate(staff.voices):
                output += '(v' + str(v) + ':)'
                if voice is None:
                    output += '{nv}'
                    continue
                if voice.token is None:
                    output += '{n}'
                    continue
                output += voice.token.text
        output += ' ppp ' + str(self.sides)
        return output

    # side property pass-thrus
    @property
    def dynamicsCount(self) -> int:
        if self.sides.dynamics is None:
            return 0
        return 1

    @property
    def dynamics(self) -> t.Optional[HumdrumToken]:
        return self.sides.dynamics

    @dynamics.setter
    def dynamics(self, newDynamics: t.Optional[HumdrumToken]) -> None:
        self.sides.dynamics = newDynamics
