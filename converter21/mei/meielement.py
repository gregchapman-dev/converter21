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
from xml.etree.ElementTree import TreeBuilder, tostring

import music21 as m21

from converter21.shared import M21Utilities

class MeiElement:
    def __init__(
        self,
        name: str,
        attrib: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.attrib: dict[str, str]
        self.subElements: list[MeiElement]

        if attrib:
            self.attrib = attrib
        else:
            self.attrib = {}
        self.subElements = []
        self.text = ''

    def appendSubElement(
        self,
        name: str,
        attrib: dict[str, str] | None = None
    ) -> 'MeiElement':
        subElement = MeiElement(name, attrib)
        self.subElements.append(subElement)
        return subElement

    def isEmpty(self) -> bool:
        if self.attrib:
            return False
        if self.text:
            return False
        if self.subElements:
            return False
        return True

    def fillInIsodate(
        self,
        m21Date: m21.metadata.DatePrimitive | m21.metadata.Text,
        attributeName: str = 'isodate'
    ):
        isodate: str = M21Utilities.isoDateFromM21DateObject(m21Date)
        if isodate:
            self.attrib[attributeName] = isodate

    def makeRootElement(self, tb: TreeBuilder):
        tb.start(self.name, self.attrib)
        if self.text:
            tb.data(self.text)
        for subEl in self.subElements:
            subEl.makeRootElement(tb)
        tb.end(self.name)

    def __repr__(self) -> str:
        # for debug view of MeiElement (displays XML)
        tb: TreeBuilder = TreeBuilder(insert_comments=True, insert_pis=True)
        self.makeRootElement(tb)
        return tostring(tb.close(), encoding='unicode')
