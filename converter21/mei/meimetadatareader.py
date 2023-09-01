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
import re

import music21 as m21

from converter21.shared import M21Utilities
from converter21.mei import MeiShared

environLocal = m21.environment.Environment('converter21.mei.meimetadatareader')

_XMLID = '{http://www.w3.org/XML/1998/namespace}id'
MEI_NS = '{http://www.music-encoding.org/ns/mei}'

_MISSED_DATE = 'Unable to decipher an MEI date "{}". Leaving as str.'


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

        # only process the first <work> element.
        self.firstWorkProcessed = False

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
        # instead of choosing between work and fileDesc, do both, but check md to make
        # sure you're not exactly duplicating something that's already there.
        if 'work' not in callerTagPath and 'fileDesc' not in callerTagPath:
            return

        text: str
        _styleDict: dict[str, str]
        text, _styleDict = MeiShared.textFromElem(elem)
        text = text.strip()
        if not text:
            return

        uniqueName: str = 'title'
        typeStr: str = elem.get('type', '')
        lang: str | None = elem.get('xml:lang')
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

        isTranslated: bool = typeStr == 'translated'

        value = m21.metadata.Text(data=text, language=lang, isTranslated=isTranslated)
        M21Utilities.addIfNotADuplicate(md, uniqueName, value)

    def _respStmtFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        self._processEmbeddedMetadataElements(
            elem.iterfind('*'),
            self._respStmtChildrenTagToFunction,
            self._getTagPath(callerTagPath, elem.tag),
            md
        )

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
        if 'fileDesc' not in callerTagPath:
            # might also be in <manifestation>, which is less interesting
            return

        for el in elem.iterfind('*'):
            tagPath: str = self._getTagPath(callerTagPath, el.tag)
            if el.tag == f'{MEI_NS}availability':
                self._availabilityFromElement(el, tagPath, md)
            elif el.tag == f'{MEI_NS}pubPlace':
                if el.text:
                    M21Utilities.addCustomIfNotADuplicate(md, 'humdrum:YEN', el.text)
            elif el.tag == f'{MEI_NS}publisher':
                self._contributorFromElement(el, tagPath, md)
            elif el.tag == f'{MEI_NS}date':
                m21DateObj: m21.metadata.DatePrimitive | str = self.m21DateFromDateElement(el)
                M21Utilities.addIfNotADuplicate(md, 'electronicReleaseDate', m21DateObj)
            elif el.tag == f'{MEI_NS}respStmt':
                self._respStmtFromElement(el, tagPath, md)
            else:
                environLocal.warn(f'Unprocessed <{el.tag}> in {callerTagPath}')

    @staticmethod
    def _isCopyright(text: str) -> bool:
        # we say True if we can find a 4-digit number in a reasonable range, and some other text.
        pattFourDigitsWithinString: str = r'(.*)(\d{4})(.*)'
        m = re.match(pattFourDigitsWithinString, text)
        if not m:
            return False

        prefix: str = m.group(1)
        year: str = m.group(2)
        suffix: str = m.group(3)

        # first we require that there be _some_ other text (there's supposed to be at least
        # a name, maybe the word "Copyright" or something, too)
        if not prefix and not suffix:
            return False

        yearInt: int = int(year)
        # First copyright ever was in 1710.
        if yearInt < 1710:
            return False

        # I'm assuming this code will not be running after the year 2200.
        if yearInt > 2200:
            return False

        return True

    def _availabilityFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        if 'fileDesc' not in callerTagPath:
            # uninterested in <manifestation>
            return

        callerTag: str = self._getTagPath(callerTagPath, elem.tag)
        for el in elem.iterfind('*'):
            if el.tag == f'{MEI_NS}useRestrict':
                if not el.text:
                    continue
                analog: str = el.get('analog', '')
                if analog == 'humdrum:YEC' or self._isCopyright(el.text):
                    M21Utilities.addIfNotADuplicate(md, 'copyright', el.text)
                else:
                    # copyrightMessage (not yet supported in music21)
                    M21Utilities.addCustomIfNotADuplicate(md, 'humdrum:YEM', el.text)
            else:
                environLocal.warn(f'Unprocessed <{el.tag}> in {callerTag}')

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
        # only parse the first work
        if self.firstWorkProcessed:
            return

        self._processEmbeddedMetadataElements(
            elem.iterfind('*'),
            self._workChildrenTagToFunction,
            self._getTagPath(callerTagPath, elem.tag),
            md
        )

        self.firstWorkProcessed = True

    def m21DateFromDateElement(
        self,
        dateEl: Element
    ) -> m21.metadata.DatePrimitive | str:
        m21DateObj: m21.metadata.DatePrimitive | str | None
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
            if m21DateObj is None:
                environLocal.warn(_MISSED_DATE.format(dateEl.text))
                return dateEl.text
            return m21DateObj

        dateStart = dateEl.get('notbefore') or dateEl.get('startdate')
        dateEnd = dateEl.get('notafter') or dateEl.get('enddate')
        if dateStart and dateEnd:
            betweenDates: str = dateStart + '-' + dateEnd
            m21DateObj = M21Utilities.m21DateObjectFromString(betweenDates)
            if m21DateObj is None:
                environLocal.warn(_MISSED_DATE.format(betweenDates))
                return betweenDates
            return m21DateObj

        if dateStart:
            afterDate: str = '>' + dateStart
            m21DateObj = M21Utilities.m21DateObjectFromString(afterDate)
            if m21DateObj is None:
                environLocal.warn(_MISSED_DATE.format(afterDate))
                return afterDate
            return m21DateObj

        if dateEnd:
            beforeDate: str = '<' + dateEnd
            m21DateObj = M21Utilities.m21DateObjectFromString(beforeDate)
            if m21DateObj is None:
                environLocal.warn(_MISSED_DATE.format(beforeDate))
                return beforeDate
            return m21DateObj

        return ''

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

        if date is not None:
            m21Date: m21.metadata.DatePrimitive | str = self.m21DateFromDateElement(date)
            if m21Date:
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
            M21Utilities.addIfNotADuplicate(md, uniqueName, name)

    def _identifierFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        if not elem.text:
            return

        analog: str = elem.get('analog', '')
        if analog:
            if analog == 'humdrum:SCT':
                M21Utilities.addIfNotADuplicate(md, 'scholarlyCatalogAbbreviation', elem.text)
                return
            if analog == 'humdrum:SCA':
                M21Utilities.addIfNotADuplicate(md, 'scholarlyCatalogName', elem.text)
                return
            if analog == 'humdrum:PC#':
                M21Utilities.addIfNotADuplicate(md, 'publishersCatalogNumber', elem.text)
                return

        typeStr: str = elem.get('type', '')
        if typeStr:
            if typeStr == 'scholarlyCatalogAbbreviation':
                M21Utilities.addIfNotADuplicate(md, 'scholarlyCatalogAbbreviation', elem.text)
                return
            if typeStr == 'scholarlyCatalogName':
                M21Utilities.addIfNotADuplicate(md, 'scholarlyCatalogName', elem.text)
                return
            if typeStr == 'publishersCatalogNumber':
                M21Utilities.addIfNotADuplicate(md, 'publishersCatalogNumber', elem.text)
                return

        # We'll guess that this could be considered a scholarly catalog abbreviation
        M21Utilities.addIfNotADuplicate(md, 'scholarlyCatalogAbbreviation', elem.text)

    @staticmethod
    def _meiAnalogToM21UniqueName(analog: str, md: m21.metadata.Metadata) -> str:
        if analog.startswith('dcterm:'):
            # convert to 'dcterms:whatever' and then process normally
            substrings: list[str] = analog.split(':')
            result: str = ''
            for i, substring in enumerate(substrings):
                if i == 0:
                    result = 'dcterms'
                else:
                    result += ':' + substring
            analog = result

        if md._isStandardUniqueName(analog):
            return analog
        if md._isStandardNamespaceName(analog):
            s: str | None = md.namespaceNameToUniqueName(analog)
            if t.TYPE_CHECKING:
                assert s is not None
            return s

        # Hmmm... perhaps it's 'humdrum:???', but in m21 metadata it's 'dcterms:*' or 'marcrel:*'
        if analog.startswith('humdrum:') and len(analog) == len('humdrum:') + 3:
            humdrumKey: str = analog[8:]
            uniqueName: str = (
                M21Utilities.humdrumReferenceKeyToM21MetadataPropertyUniqueName.get(
                    humdrumKey, ''
                )
            )
            if uniqueName:
                return uniqueName

        # give up
        return ''

    def _meiRoleToM21UniqueName(self, role: str, md: m21.metadata.Metadata) -> str:
        if md._isStandardUniqueName(role):
            return role
        if md._isStandardNamespaceName(role):
            s: str | None = md.namespaceNameToUniqueName(role)
            if t.TYPE_CHECKING:
                assert s is not None
            return s

        # Let's try combining space-delimited words into uniqueNames.
        # This will, for example, turn 'ComPoser aliaS' into 'composerAlias'.
        if ' ' in role:
            possibleUniqueName: str = M21Utilities.spaceDelimitedToCamelCase(role)
            if md._isStandardUniqueName(possibleUniqueName):
                return possibleUniqueName

        return ''

    _NAME_KEY_TO_CORP_NAME_KEY: dict[str, str] = {
        'composer': 'composerCorporate'
    }

    def _contributorFromElement(
        self,
        elem: Element,
        callerTagPath: str,
        md: m21.metadata.Metadata
    ) -> None:
        # instead of choosing between work and fileDesc, do both, but check md to make
        # sure you're not exactly duplicating something that's already there.
        if 'work' not in callerTagPath and 'fileDesc' not in callerTagPath:
            return

        if not elem.text:
            return

        analog: str = elem.get('analog', '')
        role: str = elem.get('role', '')
        key: str = ''
        if elem.tag in (
                f'{MEI_NS}name',
                f'{MEI_NS}persName',
                f'{MEI_NS}corpName',
                f'{MEI_NS}contributor'
        ):
            # prefer @analog (if it works), because it isn't free-form, like @role
            if analog:
                key = self._meiAnalogToM21UniqueName(analog, md)
            if role and not key:
                key = self._meiRoleToM21UniqueName(role, md)
                if not key:
                    key = role
            if not key:
                key = analog
        else:
            # the elem.tag ends with 'composer', or 'arranger', or...
            # and those are (hopefully) all valid m21 metadata uniqueNames.
            key = elem.tag.split('}')[-1]

        if not key:
            return

        if md._isStandardUniqueName(key):
            if key == 'composer':
                # Check analog (and cert, if necessary) to see if composer is suspected
                # or attributed.
                if analog == 'humdrum:COA':
                    key = 'attributedComposer'
                elif analog == 'humdrum:COS':
                    key = 'suspectedComposer'
                else:
                    cert: str = elem.get('cert', '')
                    if cert == 'unknown':
                        # iohumdrum.cpp (verovio) used to write this for both suspect and attrib
                        key = 'suspectedComposer'
                    elif cert == 'medium':
                        key = 'attributedComposer'
                    elif cert == 'low':
                        key = 'suspectedComposer'
            elif elem.tag == f'{MEI_NS}corpName':
                key = self._NAME_KEY_TO_CORP_NAME_KEY.get(key, key)
            M21Utilities.addIfNotADuplicate(md, key, elem.text)
        else:
            nameText = m21.metadata.Text(data=elem.text, isTranslated=False)
            M21Utilities.addIfNotADuplicate(
                md,
                'otherContributor',
                m21.metadata.Contributor(role=key, name=nameText)
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
            # f'{MEI_NS}manifestationList': self._manifestationListFromElement,
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
            # f'{MEI_NS}head': self._headFromElement,
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

        self._respStmtChildrenTagToFunction: dict[str, t.Callable[
            [
                Element,                # element to process
                str,                    # tag of parent element
                m21.metadata.Metadata  # in/out (gets updated from contents of element)
            ],
            None]                   # no return value
        ] = {
            f'{MEI_NS}name': self._contributorFromElement,
            f'{MEI_NS}persName': self._contributorFromElement,
            f'{MEI_NS}corpName': self._contributorFromElement,
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
            f'{MEI_NS}arranger': self._contributorFromElement,
            f'{MEI_NS}author': self._contributorFromElement,
            f'{MEI_NS}composer': self._contributorFromElement,
            f'{MEI_NS}contributor': self._contributorFromElement,
            f'{MEI_NS}editor': self._contributorFromElement,
            f'{MEI_NS}funder': self._contributorFromElement,
            f'{MEI_NS}librettist': self._contributorFromElement,
            f'{MEI_NS}lyricist': self._contributorFromElement,
            f'{MEI_NS}sponsor': self._contributorFromElement,
            f'{MEI_NS}title': self._titleFromElement,
        }

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


