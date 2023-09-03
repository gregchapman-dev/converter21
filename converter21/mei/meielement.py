# ------------------------------------------------------------------------------
# Name:          meielement.py
# Purpose:       MeiElement is an object that represents an element (tree) in
#                an MEI file.  This is generally only used for export of metadata,
#                where <meiHead> sub-trees need to be constructed in a way that
#                TreeBuilder can't easily support.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
from xml.etree.ElementTree import TreeBuilder

class MeiElement:
    def __init__(
        self,
        name: str,
        attrib: dict[str, str] | None = None,
        subElements: list['MeiElement'] | None = None
    ) -> None:
        self.name = name
        self.attrib: dict[str, str]
        self.subElements: list[MeiElement]

        if attrib:
            self.attrib = attrib
        else:
            self.attrib = {}
        if subElements:
            self.subElements = subElements
        else:
            self.subElements = []

    def appendSubElement(
        self,
        subElement: str | MeiElement,
        attrib: dict[str, str] | None = None
    ) -> MeiElement:
        if isinstance(subElement, str):
            subElement = MeiElement(subElement, attrib)
        self.subElements.append(subElement)
        return subElement

    def isEmpty(self) -> bool:
        if self.attrib:
            return False
        if self.subElements:
            return False
        return True

    def makeRootElement(self, tb: TreeBuilder):
        tb.start(self.name, self.attrib)
        for subEl in self.subElements:
            subEl.makeRootElement(tb)
        tb.end(self.name)
