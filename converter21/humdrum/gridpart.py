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

from converter21.humdrum import GridStaff
from converter21.humdrum import GridSide

### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

class GridPart:
    def __init__(self):
        self.staves: [GridStaff] = []
        self.sides: GridSide = GridSide()
        self._partName: str = ''

    def __str__(self):
        output:str = ''
        for s, staff in enumerate(self.staves):
            output += '(s' + str(s) + ':)'
            if staff is None:
                output += '{n}'
                continue
            for v, voice in enumerate(staff.voices):
                output += '(v' + str(v) + ':)'
                if voice is None:
                    output += '{n}'
                    continue
                if voice.token is None:
                    output += '{n}'
                else:
                    output += voice.token.text
        output += ' ppp ' + str(self.sides)
        return output
