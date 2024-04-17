# ------------------------------------------------------------------------------
# Name:          meielement.py
# Purpose:       MeiElement is an object that represents an element (tree) in
#                an MEI file. Very much like Element, but with a few enhancements
#                (name == tag with no namespace, direct access to subElement list,
#                explicit recursion, find elements with a particular attribute),
#                but no iterators yet, just lists.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
from xml.etree.ElementTree import Element, tostring  # ,TreeBuilder
import typing as t

import music21 as m21

from converter21.shared import M21Utilities
from converter21.shared import DebugTreeBuilder as TreeBuilder

class MeiElement:
    def __init__(
        self,
        elem: str | Element,
        attrib: dict[str, str] | None = None,  # ignored if elem is an Element
    ) -> None:
        self.tag: str = ''
        self.name: str = ''  # no namespace
        self.attrib: dict[str, str] = {}
        self.text: str = ''
        self.tail: str = ''
        self.subElements: list[MeiElement] = []

        if isinstance(elem, Element):
            self.tag = elem.tag
            if self.tag.startswith('{') and '}' in self.tag:
                self.name = self.tag.split('}')[-1]
            else:
                self.name = self.tag
            self.attrib = elem.attrib
            self.text = elem.text or ''
            self.tail = elem.tail or ''

            for i in range(0, len(elem)):
                self.subElements.append(MeiElement(elem[i]))

            return

        # isinstance(elem, str)
        self.tag = elem
        if self.tag.startswith('{') and '}' in self.tag:
            self.name = self.tag.split('}')[-1]
        else:
            self.name = self.tag
        if attrib:
            self.attrib = attrib

    def appendSubElement(
        self,
        tag: str,
        attrib: dict[str, str] | None = None
    ) -> 'MeiElement':
        subElement = MeiElement(tag, attrib)
        self.subElements.append(subElement)
        return subElement

    def get(self, attribName, default=None):
        return self.attrib.get(attribName, default)

    def findAll(
        self,
        tagOrName: str,
        recurse: bool = True
    ) -> list['MeiElement']:
        output: list[MeiElement] = []
        for subEl in self.subElements:
            if tagOrName in ('*', subEl.tag, subEl.name):
                output.append(subEl)
            if recurse:
                output.extend(subEl.findAll(tagOrName, recurse=True))
        return output

    def findFirst(
        self,
        tagOrName: str,
        recurse: bool = True
    ) -> t.Union['MeiElement', None]:
        for subEl in self.subElements:
            if tagOrName in ('*', subEl.tag, subEl.name):
                return subEl
            if recurse:
                foundEl: MeiElement | None = subEl.findFirst(tagOrName, recurse=True)
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
        newAttribs: dict[str, str] = M21Utilities.isoDateFromM21DatePrimitive(m21Date)
        if newAttribs:
            self.attrib.update(newAttribs)

    def makeRootElement(self, tb: TreeBuilder):
        tb.start(self.tag, self.attrib)
        if self.text:
            tb.data(self.text)
        for subEl in self.subElements:
            subEl.makeRootElement(tb)
        tb.end(self.tag)
        if self.tail:
            tb.data(self.tail)

    def __repr__(self) -> str:
        # for debug view of MeiElement (displays XML)
        tb: TreeBuilder = TreeBuilder(insert_comments=True, insert_pis=True)
        self.makeRootElement(tb)
        return tostring(tb.close(), encoding='unicode')
