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
import typing as t

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
        self.annotations: dict[str, t.Any] = {}  # this is just for making external notes

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

    def findAll(
        self,
        name: str,
        recurse: bool = True
    ) -> list['MeiElement']:
        output: list[MeiElement] = []
        for subEl in self.subElements:
            if subEl.name.endswith(name):
                output.append(subEl)
            if recurse:
                output.extend(subEl.findAll(name, recurse=True))
        return output

    def findFirst(
        self,
        name: str,
        recurse: bool = True
    ) -> t.Union['MeiElement', None]:
        for subEl in self.subElements:
            if subEl.name.endswith(name):
                return subEl
            if recurse:
                foundEl: MeiElement | None = subEl.findFirst(name, recurse=True)
                if foundEl is not None:
                    return foundEl
        return None

    def findFirstWithAttributeValue(
        self,
        key: str,
        value: str,
        recurse: bool = True
    ) -> t.Union['MeiElement', None]:
        key = key.split(':')[-1]
        for subEl in self.subElements:
            for attribKey, attribValue in subEl.attrib.items():
                if attribKey.endswith(key):
                    if attribValue == value:
                        return subEl
            if recurse:
                foundEl: MeiElement | None = subEl.findFirstWithAttributeValue(
                    key, value, recurse=True
                )
                if foundEl is not None:
                    return foundEl
        return None

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
