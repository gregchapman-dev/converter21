# ------------------------------------------------------------------------------
# Name:          m21objectconvert.py
# Purpose:       M21ObjectConvert is a static class full of utility routines
#                that convert between m21 objects and a series of calls to
#                an MEI tree builder.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
from xml.etree.ElementTree import TreeBuilder
import typing as t

import music21 as m21
# from music21.common import opFrac

# from converter21.mei import MeiExportError
# from converter21.mei import MeiInternalError
# from converter21.shared import M21Utilities

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

nextFreeVoiceNumber: int = 0

class M21ObjectConvert:

    @staticmethod
    def convertM21ObjectToMei(obj: m21.base.Music21Object, tb: TreeBuilder):
        convert: t.Callable[[m21.base.Music21Object, TreeBuilder], None] | None = (
            M21ObjectConvert._getM21ObjectConverter(obj)
        )
        if convert is not None:
            convert(obj, tb)

    @staticmethod
    def m21NoteToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        noteAttr: dict[str, str] = {}
        tb.start('note', noteAttr)
        tb.end('note')

    @staticmethod
    def _getM21ObjectConverter(
        obj: m21.base.Music21Object
    ) -> t.Callable[[m21.base.Music21Object, TreeBuilder], None] | None:
        if isinstance(obj, m21.stream.Stream):
            print(f'skipping unexpected stream object: {obj.classes[0]}')
            return None

        # obj.classes[0] is the most specific class name; we look for that first
        for className in obj.classes:
            if className in _M21_OBJECT_CONVERTER:
                return _M21_OBJECT_CONVERTER[className]

        return None

_M21_OBJECT_CONVERTER: dict[str, t.Callable[
    [m21.base.Music21Object, TreeBuilder],
    None]
] = {
    'Note': M21ObjectConvert.m21NoteToMei,

}
