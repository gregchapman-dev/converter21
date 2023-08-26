# ------------------------------------------------------------------------------
# Name:          meimetadataitem.py
# Purpose:       MeiMetadataItem is an object that takes a music21 Metadata
#                item (key, value), and computes the MEI structure for it.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
from xml.etree.ElementTree import TreeBuilder  # , Element
import typing as t

import music21 as m21

# from converter21.mei import MeiExportError
# from converter21.mei import MeiInternalError
from converter21.mei import M21ObjectConvert
# from converter21.shared import M21Utilities

environLocal = m21.environment.Environment('converter21.mei.meimetadataitem')

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access


class MeiMetadataItem:
    def __init__(self, m21Item: tuple[str, t.Any]) -> None:
        self.key: str = m21Item[0]
        self.value: t.Any = m21Item[1]
        self.meiPath: str = M21ObjectConvert.getMeiPathForM21MetadataKeyOrRole(self.key)
        if not self.meiPath and isinstance(self.value, m21.metadata.Contributor):
            self.meiPath = M21ObjectConvert.getMeiPathForM21MetadataKeyOrRole(self.value.role)
        self.meiPathElements: tuple[str, ...] = (
            M21ObjectConvert.getMeiPathElementsForM21MetadataKey(self.key)
        )
        self.rootElementName: str = M21ObjectConvert.getElementNameForM21MetadataKey(self.key)
        self.rootElementAttribs: dict = M21ObjectConvert.getAttribDictForM21MetadataKey(self.key)
        self.meiValue: str = (
            M21ObjectConvert.getValueStringForM21MetadataItem(self.key, self.value)
        )

    def makeRootElement(self, tb: TreeBuilder) -> None:
        if not self.meiPath:
            return
        if not self.rootElementName:
            return
        tb.start(self.rootElementName, self.rootElementAttribs)
        tb.data(self.meiValue)
        tb.end(self.rootElementName)
