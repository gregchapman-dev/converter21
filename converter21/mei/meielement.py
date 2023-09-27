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
from xml.etree.ElementTree import TreeBuilder, Element, tostring

import music21 as m21

from converter21.shared import M21Utilities

class MeiElement:
    def __init__(
        self,
        elem: str | Element,
        attrib: dict[str, str] | None = None,  # ignored if elem is an Element
    ) -> None:
        self.name: str = ''
        self.attrib: dict[str, str] = {}
        self.text: str = ''
        self.tail: str = ''
        self.subElements: list[MeiElement] = []

        if isinstance(elem, Element):
            self.name = elem.tag
            self.attrib = elem.attrib
            self.text = elem.text or ''
            self.tail = elem.tail or ''

            for i in range(0, len(elem)):
                self.subElements.append(MeiElement(elem[i]))

            return

        # isinstance(elem, str)
        self.name = elem
        if attrib:
            self.attrib = attrib

    def appendSubElement(
        self,
        name: str,
        attrib: dict[str, str] | None = None
    ) -> 'MeiElement':
        subElement = MeiElement(name, attrib)
        self.subElements.append(subElement)
        return subElement

    def getSubElements(
        self,
        name: str
    ) -> list['MeiElement']:
        output: list[MeiElement] = []
        for subEl in self.subElements:
            if subEl.name == name:
                output.append(subEl)
        return output

    def isEmpty(self) -> bool:
        if self.attrib:
            return False
        if self.text:
            return False
        if self.subElements:
            return False
        if self.tail.strip():
            # tail is considered empty if it just has \n and spaces/tabs
            return False
        return True

    def fillInIsodate(
        self,
        m21Date: m21.metadata.DatePrimitive | m21.metadata.Text,
        attributeName: str = 'isodate'
    ):
        isodate: str = M21Utilities.isoDateFromM21DatePrimitive(m21Date)
        if isodate:
            self.attrib[attributeName] = isodate

    def makeRootElement(self, tb: TreeBuilder):
        tb.start(self.name, self.attrib)
        if self.text:
            tb.data(self.text)
        for subEl in self.subElements:
            subEl.makeRootElement(tb)
        tb.end(self.name)
        if self.tail:
            tb.data(self.tail)

    def __repr__(self) -> str:
        # for debug view of MeiElement (displays XML)
        tb: TreeBuilder = TreeBuilder(insert_comments=True, insert_pis=True)
        self.makeRootElement(tb)
        return tostring(tb.close(), encoding='unicode')
