# ------------------------------------------------------------------------------
# Name:          meimetadatareader.py
# Purpose:       MEI <meiHead> parser
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------

import typing as t
from xml.etree.ElementTree import Element, ParseError, tostring, ElementTree
import re
import html

import music21 as m21

from converter21.mei import MeiShared

environLocal = m21.environment.Environment('converter21.mei.meimetadatareader')

_XMLID = '{http://www.w3.org/XML/1998/namespace}id'
MEI_NS = '{http://www.music-encoding.org/ns/mei}'

class MeiMetadataReader:
    def __init__(self, meiHead: Element) -> None:
        self._initializeTagToFunctionTables()
        self.m21Metadata: m21.metadata.Metadata = m21.metadata.Metadata()
        if meiHead.tag != f'{MEI_NS}meiHead':
            environLocal.warn('MeiMetadataReader must be initialized with an <meiHead> element.')
            return

        self._processEmbeddedMetadataElements(
            meiHead.iterfind('*'),
            self._meiHeadChildrenTagToFunction,
            '',
            self.m21Metadata
        )

    def _processEmbeddedMetadataElements(
        self,
        elements: t.Iterable[Element],
        mapping: dict[str, t.Callable[
            [
                Element,                # element to process
                str,                    # tag of parent element
                m21.metadata.Metadata  # in/out (gets updated from contents of element)
            ],
            None]                   # no return value
        ],
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        for eachElem in elements:
            if eachElem.tag in mapping:
                mapping[eachElem.tag](eachElem, callerTagPath, md)
            else:
                environLocal.warn(f'Unprocessed <{eachElem.tag}> in {callerTagPath}')

    @staticmethod
    def _chooseSubElement(appOrChoice: Element) -> Element | None:
        # self will eventually be used if we have a specified choice mechanism there...
        chosen: Element | None = None
        if appOrChoice.tag == f'{MEI_NS}app':
            # choose 'lem' (lemma) if present, else first 'rdg' (reading)
            chosen = appOrChoice.find(f'{MEI_NS}lem')
            if chosen is None:
                chosen = appOrChoice.find(f'{MEI_NS}rdg')
            return chosen

        if appOrChoice.tag == f'{MEI_NS}choice':
            # choose 'corr' (correction) if present,
            # else 'reg' (regularization) if present,
            # else first sub-element.
            chosen = appOrChoice.find(f'{MEI_NS}corr')
            if chosen is None:
                chosen = appOrChoice.find(f'{MEI_NS}reg')
            if chosen is None:
                chosen = appOrChoice.find('*')
            return chosen

        environLocal.warn('Internal error: chooseSubElement expects <app> or <choice>')
        return chosen  # None, if we get here

    @staticmethod
    def _getTagPath(tagPath: str, addTag: str) -> str:
        return tagPath + '/' + addTag.split('}')[-1]  # lose leading '{http:.../name/space}'

    @staticmethod
    def _elementToString(element: Element) -> str:
        # returns everything between <element> and </element>
        s: str = element.text or ''
        for subEl in element:
            s += tostring(subEl, encoding='unicode')
        return s

    def _appChoiceMeiHeadChildrenFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        chosen: Element | None = self._chooseSubElement(elem)
        if chosen is None:
            return

        # iterate all immediate children
        self._processEmbeddedMetadataElements(
            chosen.iterfind('*'),
            self._meiHeadChildrenTagToFunction,
            self._getTagPath(callerTagPath, chosen.tag),
            md
        )

    def _passThruEditorialMeiHeadChildrenFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        # iterate all immediate children
        self._processEmbeddedMetadataElements(
            elem.iterfind('*'),
            self._meiHeadChildrenTagToFunction,
            self._getTagPath(callerTagPath, elem.tag),
            md
        )

    def _fileDescFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        self._processEmbeddedMetadataElements(
            elem.iterfind('*'),
            self._fileDescChildrenTagToFunction,
            self._getTagPath(callerTagPath, elem.tag),
            md
        )

    def _appChoiceFileDescChildrenFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        chosen: Element | None = self._chooseSubElement(elem)
        if chosen is None:
            return

        # iterate all immediate children
        self._processEmbeddedMetadataElements(
            chosen.iterfind('*'),
            self._fileDescChildrenTagToFunction,
            self._getTagPath(callerTagPath, chosen.tag),
            md
        )

    def _passThruEditorialFileDescChildrenFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        # iterate all immediate children
        self._processEmbeddedMetadataElements(
            elem.iterfind('*'),
            self._fileDescChildrenTagToFunction,
            self._getTagPath(callerTagPath, elem.tag),
            md
        )

    def _titleStmtFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        self._processEmbeddedMetadataElements(
            elem.iterfind('*'),
            self._titleStmtChildrenTagToFunction,
            self._getTagPath(callerTagPath, elem.tag),
            md
        )

    def _titleFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        # first, add a custom mei-specific item (because there are
        # several places in meiHead that might have a title or two).
        fullMeiTitleElementContents: str = tostring(elem, encoding='unicode')
        fullMeiTitleElementContents = fullMeiTitleElementContents.strip()
        tagPath: str = self._getTagPath(callerTagPath, elem.tag)
        md.addCustom('meiHead:' + tagPath, fullMeiTitleElementContents)

        # Assume for now that every title belongs in md['title'] (that's not right, we need to
        # pick the right one, maybe as a post-processing pass over the mei-specific metadata)
        text: str
        styleDict: dict[str, str]
        text, styleDict = MeiShared.textFromElem(elem)
        text = text.strip()
        md.add('title', text)

    def _headFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _respStmtFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _respLikePartFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _editionStmtFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _extentFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _pubStmtFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _seriesStmtFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        self._processEmbeddedMetadataElements(
            elem.iterfind('*'),
            self._seriesStmtChildrenTagToFunction,
            self._getTagPath(callerTagPath, elem.tag),
            md
        )

    def _notesStmtFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _sourceDescFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _encodingDescFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        self._processEmbeddedMetadataElements(
            elem.iterfind('*'),
            self._encodingDescChildrenTagToFunction,
            self._getTagPath(callerTagPath, elem.tag),
            md
        )

    def _workListFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        self._processEmbeddedMetadataElements(
            elem.iterfind('*'),
            self._workListChildrenTagToFunction,
            self._getTagPath(callerTagPath, elem.tag),
            md
        )

    def _manifestationListFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        self._processEmbeddedMetadataElements(
            elem.iterfind('*'),
            self._manifestationListChildrenTagToFunction,
            self._getTagPath(callerTagPath, elem.tag),
            md
        )

    def _revisionDescFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        self._processEmbeddedMetadataElements(
            elem.iterfind('*'),
            self._revisionDescChildrenTagToFunction,
            self._getTagPath(callerTagPath, elem.tag),
            md
        )

    def _extMetaFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        self._processEmbeddedMetadataElements(
            elem.iterfind('*'),
            self._extMetaChildrenTagToFunction,
            self._getTagPath(callerTagPath, elem.tag),
            md
        )

    def _initializeTagToFunctionTables(self) -> None:
        self._meiHeadChildrenTagToFunction: dict[str, t.Callable[
            [
                Element,                # element to process
                str,                    # tag of parent element
                m21.metadata.Metadata  # in/out (gets updated from contents of element)
            ],
            None]                   # no return value
        ] = {
            f'{MEI_NS}app': self._appChoiceMeiHeadChildrenFromElement,
            f'{MEI_NS}choice': self._appChoiceMeiHeadChildrenFromElement,
            f'{MEI_NS}add': self._passThruEditorialMeiHeadChildrenFromElement,
            f'{MEI_NS}corr': self._passThruEditorialMeiHeadChildrenFromElement,
            f'{MEI_NS}damage': self._passThruEditorialMeiHeadChildrenFromElement,
            f'{MEI_NS}expan': self._passThruEditorialMeiHeadChildrenFromElement,
            f'{MEI_NS}orig': self._passThruEditorialMeiHeadChildrenFromElement,
            f'{MEI_NS}reg': self._passThruEditorialMeiHeadChildrenFromElement,
            f'{MEI_NS}sic': self._passThruEditorialMeiHeadChildrenFromElement,
            f'{MEI_NS}subst': self._passThruEditorialMeiHeadChildrenFromElement,
            f'{MEI_NS}supplied': self._passThruEditorialMeiHeadChildrenFromElement,
            f'{MEI_NS}unclear': self._passThruEditorialMeiHeadChildrenFromElement,
            f'{MEI_NS}fileDesc': self._fileDescFromElement,
            f'{MEI_NS}encodingDesc': self._encodingDescFromElement,
            f'{MEI_NS}workList': self._workListFromElement,
            f'{MEI_NS}manifestationList': self._manifestationListFromElement,
            f'{MEI_NS}revisionDesc': self._revisionDescFromElement,
            f'{MEI_NS}extMeta': self._extMetaFromElement,
        }

        self._fileDescChildrenTagToFunction: dict[str, t.Callable[
            [
                Element,                # element to process
                str,                    # tag of parent element
                m21.metadata.Metadata  # in/out (gets updated from contents of element)
            ],
            None]                   # no return value
        ] = {
            f'{MEI_NS}app': self._appChoiceFileDescChildrenFromElement,
            f'{MEI_NS}choice': self._appChoiceFileDescChildrenFromElement,
            f'{MEI_NS}add': self._passThruEditorialFileDescChildrenFromElement,
            f'{MEI_NS}corr': self._passThruEditorialFileDescChildrenFromElement,
            f'{MEI_NS}damage': self._passThruEditorialFileDescChildrenFromElement,
            f'{MEI_NS}expan': self._passThruEditorialFileDescChildrenFromElement,
            f'{MEI_NS}orig': self._passThruEditorialFileDescChildrenFromElement,
            f'{MEI_NS}reg': self._passThruEditorialFileDescChildrenFromElement,
            f'{MEI_NS}sic': self._passThruEditorialFileDescChildrenFromElement,
            f'{MEI_NS}subst': self._passThruEditorialFileDescChildrenFromElement,
            f'{MEI_NS}supplied': self._passThruEditorialFileDescChildrenFromElement,
            f'{MEI_NS}unclear': self._passThruEditorialFileDescChildrenFromElement,
            f'{MEI_NS}editionStmt': self._editionStmtFromElement,
            f'{MEI_NS}extent': self._extentFromElement,
            f'{MEI_NS}notesStmt': self._notesStmtFromElement,
            f'{MEI_NS}pubStmt': self._pubStmtFromElement,
            f'{MEI_NS}seriesStmt': self._seriesStmtFromElement,
            f'{MEI_NS}sourceDesc': self._sourceDescFromElement,
            f'{MEI_NS}titleStmt': self._titleStmtFromElement,
        }

        self._titleStmtChildrenTagToFunction: dict[str, t.Callable[
            [
                Element,                # element to process
                str,                    # tag of parent element
                m21.metadata.Metadata  # in/out (gets updated from contents of element)
            ],
            None]                   # no return value
        ] = {
            f'{MEI_NS}head': self._headFromElement,
            f'{MEI_NS}respStmt': self._respStmtFromElement,
            f'{MEI_NS}arranger': self._respLikePartFromElement,
            f'{MEI_NS}author': self._respLikePartFromElement,
            f'{MEI_NS}composer': self._respLikePartFromElement,
            f'{MEI_NS}contributor': self._respLikePartFromElement,
            f'{MEI_NS}editor': self._respLikePartFromElement,
            f'{MEI_NS}funder': self._respLikePartFromElement,
            f'{MEI_NS}librettist': self._respLikePartFromElement,
            f'{MEI_NS}lyricist': self._respLikePartFromElement,
            f'{MEI_NS}sponsor': self._respLikePartFromElement,
            f'{MEI_NS}title': self._titleFromElement,
        }

        self._seriesStmtChildrenTagToFunction: dict[str, t.Callable[
            [
                Element,                # element to process
                str,                    # tag of parent element
                m21.metadata.Metadata  # in/out (gets updated from contents of element)
            ],
            None]                   # no return value
        ] = {
            f'{MEI_NS}head': self._headFromElement,
            f'{MEI_NS}respStmt': self._respStmtFromElement,
            f'{MEI_NS}arranger': self._respLikePartFromElement,
            f'{MEI_NS}author': self._respLikePartFromElement,
            f'{MEI_NS}composer': self._respLikePartFromElement,
            f'{MEI_NS}contributor': self._respLikePartFromElement,
            f'{MEI_NS}editor': self._respLikePartFromElement,
            f'{MEI_NS}funder': self._respLikePartFromElement,
            f'{MEI_NS}librettist': self._respLikePartFromElement,
            f'{MEI_NS}lyricist': self._respLikePartFromElement,
            f'{MEI_NS}sponsor': self._respLikePartFromElement,
            f'{MEI_NS}title': self._titleFromElement,
        }

        self._encodingDescChildrenTagToFunction: dict[str, t.Callable[
            [
                Element,                # element to process
                str,                    # tag of parent element
                m21.metadata.Metadata  # in/out (gets updated from contents of element)
            ],
            None]                   # no return value
        ] = {}

        self._workListChildrenTagToFunction: dict[str, t.Callable[
            [
                Element,                # element to process
                str,                    # tag of parent element
                m21.metadata.Metadata  # in/out (gets updated from contents of element)
            ],
            None]                   # no return value
        ] = {}

        self._manifestationListChildrenTagToFunction: dict[str, t.Callable[
            [
                Element,                # element to process
                str,                    # tag of parent element
                m21.metadata.Metadata  # in/out (gets updated from contents of element)
            ],
            None]                   # no return value
        ] = {}

        self._revisionDescChildrenTagToFunction: dict[str, t.Callable[
            [
                Element,                # element to process
                str,                    # tag of parent element
                m21.metadata.Metadata  # in/out (gets updated from contents of element)
            ],
            None]                   # no return value
        ] = {}

        self._extMetaChildrenTagToFunction: dict[str, t.Callable[
            [
                Element,                # element to process
                str,                    # tag of parent element
                m21.metadata.Metadata  # in/out (gets updated from contents of element)
            ],
            None]                   # no return value
        ] = {}


