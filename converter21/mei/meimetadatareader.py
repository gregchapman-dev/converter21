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
from xml.etree.ElementTree import Element, tostring

import music21 as m21

from converter21.shared import M21Utilities
from converter21.mei import MeiShared

environLocal = m21.environment.Environment('converter21.mei.meimetadatareader')

_XMLID = '{http://www.w3.org/XML/1998/namespace}id'
MEI_NS = '{http://www.music-encoding.org/ns/mei}'

_MISSED_DATE = 'Unable to decipher an MEI date "{}"'


class MeiMetadataReader:
    def __init__(self, meiHead: Element) -> None:
        self._initializeTagToFunctionTables()
        self.m21Metadata: m21.metadata.Metadata = m21.metadata.Metadata()
        if meiHead.tag != f'{MEI_NS}meiHead':
            environLocal.warn('MeiMetadataReader must be initialized with an <meiHead> element.')
            return

        # figure out if there is a <work> element.  If not, we should gather "work"-style metadata
        # from the <fileDesc> element instead.
        self.workExists = False
        work: Element | None = meiHead.find(f'.//{MEI_NS}work')
        if work is not None:
            self.workExists = True

        self._processEmbeddedMetadataElements(
            meiHead.iterfind('*'),
            self._meiHeadChildrenTagToFunction,
            '',
            self.m21Metadata
        )

        # Add a single 'meiraw:meiHead' metadata element, that contains the raw XML of the
        # entire <meiHead> element (in case someone wants to parse out more info than we do.
        meiHeadXmlStr: str = tostring(meiHead, encoding='unicode')
        meiHeadXmlStr = meiHeadXmlStr.strip()
        self.m21Metadata.addCustom('meiraw:meiHead', meiHeadXmlStr)

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
        if self.workExists and 'work' not in callerTagPath:
            # if <work> exists, insist on <work> title(s) only
            return

        if not self.workExists and 'fileDesc' not in callerTagPath:
            # if <work> doesn't exist, insist on <fileDesc> title(s) only
            return

        text: str
        _styleDict: dict[str, str]
        text, _styleDict = MeiShared.textFromElem(elem)
        text = text.strip()
        if not text:
            return

        uniqueName: str = 'title'
        typeStr: str = elem.get('type', '')
        label: str = elem.get('label', '')
        analog: str = elem.get('analog', '')
        if analog:
            if analog == 'humdrum:OTP':
                uniqueName = 'popularTitle'
            elif analog == 'humdrum:OTA':
                uniqueName = 'alternativeTitle'
        else:
            if typeStr == 'alternative':
                if label == 'popular':
                    uniqueName = 'popularTitle'
                else:
                    uniqueName = 'alternativeTitle'

        md.add(uniqueName, text)

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

#     def _seriesStmtFromElement(
#         self,
#         elem: Element,
#         callerTagPath: str,
#         md: m21.metadata.Metadata
#     ) -> None:
#         self._processEmbeddedMetadataElements(
#             elem.iterfind('*'),
#             self._seriesStmtChildrenTagToFunction,
#             self._getTagPath(callerTagPath, elem.tag),
#             md
#         )

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

    def _workFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        self._processEmbeddedMetadataElements(
            elem.iterfind('*'),
            self._workChildrenTagToFunction,
            self._getTagPath(callerTagPath, elem.tag),
            md
        )

    def m21DateFromDateElement(
        self,
        dateEl: Element
    ) -> m21.metadata.DatePrimitive | None:
        m21DateObj: m21.metadata.DatePrimitive | None = None
        isodate: str | None = dateEl.get('isodate')
        if isodate:
            m21DateObj = M21Utilities.m21DateObjectFromISODate(isodate)
            if m21DateObj is None:
                # try it as humdrum date/zeit
                m21DateObj = M21Utilities.m21DateObjectFromString(isodate)
            if m21DateObj is not None:
                # if m21DateObj is None, we'll fall through and
                # try to parse date.text, since @isodate was a fail.
                return m21DateObj

        if dateEl.text:
            m21DateObj = M21Utilities.m21DateObjectFromString(dateEl.text)
            if m21DateObj is None:
                # try it as isodate
                m21DateObj = M21Utilities.m21DateObjectFromISODate(dateEl.text)
        else:
            dateStart = dateEl.get('notbefore') or dateEl.get('startdate')
            dateEnd = dateEl.get('notafter') or dateEl.get('enddate')
            if dateStart and dateEnd:
                m21DateObj = M21Utilities.m21DateObjectFromString(dateStart + '-' + dateEnd)
            elif dateStart:
                m21DateObj = M21Utilities.m21DateObjectFromString('>' + dateStart)
            elif dateEnd:
                m21DateObj = M21Utilities.m21DateObjectFromString('<' + dateEnd)

        if m21DateObj is None:
            environLocal.warn(_MISSED_DATE.format(tostring(dateEl)))

        return m21DateObj

    def _creationFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        if 'work' not in callerTagPath:
            return

        date: Element | None = elem.find(f'{MEI_NS}date')
        geogNames: list[Element] = elem.findall(f'{MEI_NS}geogName')

        m21Date: m21.metadata.DatePrimitive | None = None
        if date is not None:
            m21Date = self.m21DateFromDateElement(date)
        if m21Date is not None:
            md.add('dateCreated', m21Date)

        for geogName in geogNames:
            name: str = geogName.text or ''
            if not name:
                continue
            analog: str = geogName.get('analog', '')
            uniqueName: str = 'countryOfComposition'
            if analog:
                # @analog="humdrum:OPC", for example, means 'localeOfComposition'
                # m21 metadata happens to use these names, otherwise we'd have to
                # declare our own lookup table.
                uniqueName = md.namespaceNameToUniqueName(analog) or ''
                if not uniqueName:
                    uniqueName = 'countryOfComposition'
            md.add(uniqueName, name)

    def _identifierFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _arrangerFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _authorFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _composerFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _contributorFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _editorFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _funderFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _librettistFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _lyricistFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

    def _sponsorFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        pass

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
            # f'{MEI_NS}seriesStmt': self._seriesStmtFromElement,
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

#         self._seriesStmtChildrenTagToFunction: dict[str, t.Callable[
#             [
#                 Element,                # element to process
#                 str,                    # tag of parent element
#                 m21.metadata.Metadata  # in/out (gets updated from contents of element)
#             ],
#             None]                   # no return value
#         ] = {
#             f'{MEI_NS}head': self._headFromElement,
#             f'{MEI_NS}respStmt': self._respStmtFromElement,
#             f'{MEI_NS}arranger': self._respLikePartFromElement,
#             f'{MEI_NS}author': self._respLikePartFromElement,
#             f'{MEI_NS}composer': self._respLikePartFromElement,
#             f'{MEI_NS}contributor': self._respLikePartFromElement,
#             f'{MEI_NS}editor': self._respLikePartFromElement,
#             f'{MEI_NS}funder': self._respLikePartFromElement,
#             f'{MEI_NS}librettist': self._respLikePartFromElement,
#             f'{MEI_NS}lyricist': self._respLikePartFromElement,
#             f'{MEI_NS}sponsor': self._respLikePartFromElement,
#             f'{MEI_NS}title': self._seriesTitleFromElement,
#         }

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
            # f'{MEI_NS}head': self._headFromElement,
            f'{MEI_NS}work': self._workFromElement,
        }

        self._workChildrenTagToFunction: dict[str, t.Callable[
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
            # f'{MEI_NS}head': self._headFromElement,
            f'{MEI_NS}creation': self._creationFromElement,
            f'{MEI_NS}notesStmt': self._notesStmtFromElement,
            f'{MEI_NS}identifier': self._identifierFromElement,
            f'{MEI_NS}arranger': self._arrangerFromElement,
            f'{MEI_NS}author': self._authorFromElement,
            f'{MEI_NS}composer': self._composerFromElement,
            f'{MEI_NS}contributor': self._contributorFromElement,
            f'{MEI_NS}editor': self._editorFromElement,
            f'{MEI_NS}funder': self._funderFromElement,
            f'{MEI_NS}librettist': self._librettistFromElement,
            f'{MEI_NS}lyricist': self._lyricistFromElement,
            f'{MEI_NS}sponsor': self._sponsorFromElement,
            f'{MEI_NS}title': self._titleFromElement,
        }

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


