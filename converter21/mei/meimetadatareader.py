# ------------------------------------------------------------------------------
# Name:          meimetadatareader.py
# Purpose:       MEI <meiHead> parser
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------

# import typing as t
from xml.etree.ElementTree import Element, tostring
# import re

import music21 as m21

from converter21.mei import MeiElementError
from converter21.mei import MeiShared
from converter21.mei import MeiElement
from converter21.shared import M21Utilities
from converter21.shared import SharedConstants

environLocal = m21.environment.Environment('converter21.mei.meimetadatareader')

_XMLID = '{http://www.w3.org/XML/1998/namespace}id'
_XMLLANG = '{http://www.w3.org/XML/1998/namespace}lang'
MEI_NS = '{http://www.music-encoding.org/ns/mei}'

_MISSED_DATE = 'Unable to decipher an MEI date "{}". Leaving as str.'


class MeiMetadataReader:
    def __init__(self, meiHead: Element) -> None:
        if meiHead.tag != f'{MEI_NS}meiHead':
            raise MeiElementError(
                'MeiMetadataReader must be initialized with an <meiHead> element.'
            )

        self.meiHead: Element = meiHead
        self.meiHeadElement: MeiElement = MeiElement(meiHead)
        self.madsAuthorityDataByID: dict[str, MeiElement] = {}
        self.m21Metadata: m21.metadata.Metadata = m21.metadata.Metadata()

    def processMetadata(self) -> None:
        self.madsAuthorityDataByID = self.gatherMADSAuthorityData()

        fileDescMD: m21.metadata.Metadata | None = None
        encodingDescMD: m21.metadata.Metadata | None = None
        workListMD: m21.metadata.Metadata | None = None

        # Gather up separate metadata from each subElement of meiHead, then combine
        # them (e.g. use title from workList if it's there, else from fileDesc).
        for subEl in self.meiHeadElement.subElements:
            if subEl.name.endswith('fileDesc'):
                fileDescMD = self.processFileDesc(subEl)
            elif subEl.name.endswith('encodingDesc'):
                encodingDescMD = self.processEncodingDesc(subEl)
            elif subEl.name.endswith('workList'):
                workListMD = self.processWorkList(subEl)

        self.m21Metadata = self.combineFileDescEncodingDescAndWorkListMetadata(
            fileDescMD,
            encodingDescMD,
            workListMD
        )

        # Add a single 'meiraw:meiHead' metadata element, that contains the raw XML of the
        # entire <meiHead> element (in case someone wants to parse out more info than we do).
        meiHeadXmlStr: str = tostring(self.meiHead, encoding='unicode')
#         meiHeadElementStr: str = self.meiHeadElement.__repr__()
        meiHeadXmlStr = meiHeadXmlStr.strip()  # strips off any trailing \n and spaces
        self.m21Metadata.addCustom('meiraw:meiHead', meiHeadXmlStr)

    def gatherMADSAuthorityData(self) -> dict[str, MeiElement]:
        output: dict[str, MeiElement] = {}
        # We recurse to find all <mads> elements anywhere in <meiHead>.  Our writer puts
        # them in the main <work> element's <extMeta><madsCollection>, but others might
        # put them in <meiHead><extMeta><madsCollection>.  We'll find them all here.
        madsElements: list[MeiElement] = self.meiHeadElement.findAll('mads', recurse=True)
        for mads in madsElements:
            madsID: str = mads.get('ID', '')
            if madsID:
                output[madsID] = mads
        return output

    def processFileDesc(self, fileDescElement: MeiElement) -> m21.metadata.Metadata:
        md = m21.metadata.Metadata()
        for subElement in fileDescElement.findAll('*', recurse=False):
            self.processFileDescSubElement(subElement, md)

        return md

    def processFileDescSubElement(self, element: MeiElement, md: m21.metadata.Metadata):
        if element.name == 'titleStmt':
            self.processTitleStmt(element, md)
        elif element.name == 'editionStmt':
            # Info about a different edition of this file.
            # Nothing interesting to music21 here?
            pass  # self.processEditionStmt(element, md)
        elif element.name == 'extent':
            # Size information about this file.
            # Nothing interesting to music21 here?
            pass  # self.processExtent(element, md)
        elif element.name == 'pubStmt':
            self.processPubStmt(element, md)
        elif element.name == 'seriesStmt':
            self.processSeriesStmt(element, md)
        elif element.name == 'notesStmt':
            self.processNotesStmt(element, 'humdrum:ONB', md)
        elif element.name == 'sourceDesc':
            self.processSourceDesc(element, md)

    def processTitleStmt(self, element: MeiElement, md: m21.metadata.Metadata):
        for subEl in element.findAll('*', recurse=False):
            if subEl.name == 'title':
                self.processTitleOrTitlePart(subEl, '', '', md)
            elif subEl.name == 'composer':
                self.processComposer(subEl, md)
            elif subEl.name == 'lyricist':
                self.processContributor(subEl, 'humdrum:LYR', '', md)
            elif subEl.name == 'librettist':
                self.processContributor(subEl, 'humdrum:LIB', '', md)
            elif subEl.name == 'funder':
                self.processContributor(subEl, 'humdrum:OCO', '', md)
            elif subEl.name == 'editor':
                self.processContributor(subEl, 'humdrum:EED', '', md)
            elif subEl.name == 'respStmt':
                self.processRespStmt(subEl, md, context='titleStmt')
            elif subEl.name in ('arranger', 'author', 'contributor', 'sponsor'):
                self.processContributor(subEl, '', '', md)

    def processPubStmt(self, element: MeiElement, md: m21.metadata.Metadata):
        for subEl in element.findAll('*', recurse=False):
            if subEl.name == 'date':
                m21DateObj: m21.metadata.DatePrimitive | str = (
                    self.m21DatePrimitiveOrStringFromDateElement(subEl, 'humdrum:YER', md)
                )
                if m21DateObj:
                    M21Utilities.addIfNotADuplicate(md, 'humdrum:YER', m21DateObj)
            elif subEl.name == 'availability':
                self.processAvailability(subEl, md, 'pubStmt')

    def processSeriesStmt(self, element: MeiElement, md: m21.metadata.Metadata):
        for subEl in element.findAll('*', recurse=False):
            if subEl.name == 'title':
                self.processTitleOrTitlePart(subEl, 'humdrum:GCO', '', md)

    def processSourceDesc(self, element: MeiElement, md: m21.metadata.Metadata):
        for sourceEl in element.findAll('source', recurse=False):
            self.processSource(sourceEl, md)

    def processSource(self, element: MeiElement, md: m21.metadata.Metadata):
        sourceType: str = element.get('type', '')
        for subEl in element.findAll('*', recurse=False):
            if subEl.name == 'bibl':
                self.processSourceBibl(subEl, sourceType, md)
            elif subEl.name == 'biblStruct':
                self.processSourceBiblStruct(subEl, sourceType, md)

    def processSourceBibl(
        self,
        element: MeiElement,
        sourceType: str,
        md: m21.metadata.Metadata
    ):
        context: str = 'source:' + sourceType
        subEls: list[MeiElement] = element.findAll('*', recurse=False)
        if not subEls:
            # just get the text, and call it an original document title
            text: str = element.text.strip()
            if text:
                M21Utilities.addIfNotADuplicate(md, 'humdrum:YOR', text)
            return

        for subEl in subEls:
            if subEl.name == 'identifier':
                self.processIdentifier(subEl, md)
            elif subEl.name == 'title':
                if sourceType in ('digital', 'printed', ''):
                    if not md['title']:
                        # There was no <title> in <fileDesc> or in any such <source>
                        # so far, so this will have to do.
                        self.processTitleOrTitlePart(subEl, 'humdrum:OTL', '', md)
                elif sourceType == 'recording':
                    self.processTitleOrTitlePart(subEl, 'humdrum:RTL', '', md)
                elif sourceType == 'unpub':
                    self.processTitleOrTitlePart(subEl, 'humdrum:SMS', '', md)
                else:
                    self.processTitleOrTitlePart(subEl, '', '', md)
            elif subEl.name == 'composer':
                self.processComposer(subEl, md)
            elif subEl.name == 'contributor':
                self.processContributor(subEl, '', '', md)
            elif subEl.name == 'dedicatee':
                self.processContributor(subEl, 'humdrum:ODE', '', md)
            elif subEl.name == 'distributor':
                self.processContributor(subEl, '', '', md)
            elif subEl.name == 'editor':
                if sourceType == 'digital':
                    self.processContributor(subEl, 'humdrum:EED', '', md)
                elif sourceType in ('printed', ''):
                    self.processContributor(subEl, 'humdrum:PED', '', md)
                elif sourceType == 'unpub':
                    self.processContributor(subEl, 'humdrum:YOE', '', md)
            elif subEl.name == 'funder':
                self.processContributor(subEl, 'humdrum:OCO', '', md)
            elif subEl.name == 'librettist':
                self.processContributor(subEl, 'humdrum:LIB', '', md)
            elif subEl.name == 'lyricist':
                self.processContributor(subEl, 'humdrum:LYR', '', md)
            elif subEl.name == 'publisher':
                if sourceType == 'digital':
                    self.processContributor(subEl, 'humdrum:YEP', '', md)
                elif sourceType in ('printed', ''):
                    self.processContributor(subEl, 'humdrum:PPR', '', md)
            elif subEl.name == 'sponsor':
                self.processContributor(subEl, '', '', md)
            elif subEl.name in ('name', 'persName', 'corpName'):
                self.processContributor(subEl, '', '', md)
            elif subEl.name == 'recipient':
                self.processContributor(subEl, '', '', md)
            elif subEl.name == 'repository':
                if sourceType == 'unpub':
                    self.processRepository(subEl, 'humdrum:SML', md)
            elif subEl.name == 'respStmt':
                self.processRespStmt(subEl, md, context=context)
            elif subEl.name == 'imprint':
                self.processImprint(subEl, md, sourceType)
            elif subEl.name == 'availability':
                self.processAvailability(subEl, md, sourceType)
            elif subEl.name == 'relatedItem':
                if sourceType in ('printed', '') and subEl.get('rel', '') == 'host':
                    bibl: MeiElement | None = subEl.findFirst('bibl', recurse=False)
                    if bibl is None:
                        continue
                    for titleEl in bibl.findAll('title', recurse=False):
                        self.processTitleOrTitlePart(titleEl, 'humdrum:PTL', '', md)

                    for biblScope in bibl.findAll('biblScope', recurse=False):
                        if (biblScope.get('type', '') == 'volumeNumber'
                                or biblScope.get('analog', '') == 'humdrum:OVM'):
                            text, _styleDict = MeiShared.textFromElem(biblScope)
                            text = text.strip()
                            if not text:
                                continue
                            M21Utilities.addIfNotADuplicate(md, 'humdrum:OVM', text)
            elif subEl.name == 'textLang':
                analog: str = subEl.get('analog', '')
                if not M21Utilities.isUsableMetadataKey(md, analog):
                    if sourceType == 'digital':
                        analog = 'humdrum:TXL'
                    else:
                        continue
                text = subEl.text.strip()
                if not text:
                    continue
                M21Utilities.addIfNotADuplicate(md, analog, text)
            elif subEl.name == 'creation':
                self.processCreation(subEl, md, context=context)
            elif subEl.name == 'date':
                analog = subEl.get('analog', '')
                if not M21Utilities.isUsableMetadataKey(md, analog):
                    typeStr: str = subEl.get('type', '')
                    if typeStr == 'copyrightDate':
                        analog = 'humdrum:YOY'
                    else:
                        continue

                m21DateObj: m21.metadata.DatePrimitive | str = (
                    self.m21DatePrimitiveOrStringFromDateElement(subEl, analog, md)
                )
                if m21DateObj:
                    M21Utilities.addIfNotADuplicate(md, analog, m21DateObj)
            elif subEl.name == 'edition':
                analog = subEl.get('analog', '')
                if not M21Utilities.isUsableMetadataKey(md, analog):
                    if sourceType != 'digital':
                        continue
                    typeStr = subEl.get('type', '')
                    if typeStr == 'version':
                        analog = 'humdrum:EEV'
                    else:
                        continue
                text = subEl.text.strip()
                M21Utilities.addIfNotADuplicate(md, analog, text)
            elif subEl.name == 'extent':
                analog = subEl.get('analog', '')
                if not M21Utilities.isUsableMetadataKey(md, analog):
                    # don't process unless analog is usable; the text format
                    # is very specific.
                    continue
                text = subEl.text.strip()
                M21Utilities.addIfNotADuplicate(md, analog, text)
            elif subEl.name == 'annot':
                defaultLang: str = subEl.get(_XMLLANG, '')
                defaultAnalog: str = ''
                if subEl.get('type', '') == 'manuscriptAccessAcknowledgment':
                    defaultAnalog = 'humdrum:SMA'
                else:
                    defaultAnalog = 'humdrum:ONB'

                self.processElementContainingParagraphsAndLineGroups(
                    subEl,
                    defaultLang,
                    defaultAnalog,
                    md
                )

    def processAvailability(self, element: MeiElement, md: m21.metadata.Metadata, sourceType: str):
        for useRestrict in element.findAll('useRestrict', recurse=False):
            text: str = useRestrict.text.strip()
            if not text:
                continue

            analog: str = useRestrict.get('analog', '')
            if not M21Utilities.isUsableMetadataKey(md, analog):
                # compute what analog should be
                typeStr: str = useRestrict.get('type', '')
                if typeStr == 'copyrightStatement':
                    analog = 'humdrum:YEM'
                elif typeStr == 'copyrightCountry':
                    analog = 'humdrum:YEN'
                elif typeStr == 'copyright':
                    if sourceType in ('printed', ''):
                        analog = 'mei:printedSourceCopyright'
                    elif sourceType == 'digital':
                        analog = 'humdrum:YEC'
                    else:
                        continue
                elif typeStr == '':
                    if sourceType in ('printed', ''):
                        analog = 'mei:printedSourceCopyright'
                    if sourceType == 'digital':
                        analog = 'humdrum:YEC'
                    elif sourceType == 'pubStmt':
                        analog = 'humdrum:YEM'
                    else:
                        continue
                else:
                    continue

            M21Utilities.addIfNotADuplicate(md, analog, text)

    def processSourceBiblStruct(
        self,
        element: MeiElement,
        sourceType: str,
        md: m21.metadata.Metadata
    ):
        analytics: list[MeiElement] = element.findAll('analytic', recurse=False)
        monographs: list[MeiElement] = element.findAll('monogr', recurse=False)

        for analytic in analytics:
            self.processAnalytic(analytic, sourceType, md)
        for monograph in monographs:
            self.processSourceBibl(monograph, sourceType, md)

    def processAnalytic(
        self,
        element: MeiElement,
        sourceType: str,
        md: m21.metadata.Metadata
    ):
        # We ignore it for all but recording sources
        if sourceType != 'recording':
            return

        for subEl in element.findAll('biblScope', recurse=False):
            text: str = subEl.text.strip()
            if not text:
                continue

            analog: str = subEl.get('analog', '')
            if not M21Utilities.isUsableMetadataKey(md, analog):
                # compute what analog should be
                if (subEl.get('type', '') == 'trackNumber'
                        or subEl.get('unit', '') == 'track'):
                    analog = 'humdrum:RC#'
                else:
                    continue

            M21Utilities.addIfNotADuplicate(md, analog, text)


    def processImprint(self, element: MeiElement, md: m21.metadata.Metadata, sourceType: str):
        for subEl in element.findAll('*', recurse=False):
            analog: str = subEl.get('analog', '')
            if subEl.name == 'publisher':
                if sourceType == 'digital':
                    self.processContributor(subEl, 'humdrum:YEP', '', md)
                elif sourceType == 'printed':
                    self.processContributor(subEl, 'humdrum:PPR', '', md)
                else:
                    self.processContributor(subEl, '', '', md)
            elif subEl.name in ('name', 'persName', 'corpName'):
                if sourceType == 'recorded':
                    if subEl.get('role', '') == 'production/distribution':
                        self.processContributor(subEl, 'humdrum:RRD', '', md)
                else:
                    self.processContributor(subEl, analog, '', md)
            elif subEl.name == 'geogName':
                if not M21Utilities.isUsableMetadataKey(md, analog):
                    if subEl.get('role', '') == 'recordingLocation':
                        analog = 'humdrum:RLC'
                    elif sourceType in ('printed', ''):
                        analog = 'humdrum:PPP'
                    else:
                        continue
                text: str = subEl.text.strip()
                if not text:
                    continue
                M21Utilities.addIfNotADuplicate(md, analog, text)

            elif subEl.name == 'date':
                analog = subEl.get('analog', '')
                if not M21Utilities.isUsableMetadataKey(md, analog):
                    typeStr: str = subEl.get('type', '')
                    if sourceType == 'digital':
                        if typeStr == 'releaseDate':
                            analog = 'humdrum:YER'
                        elif typeStr == 'encodingDate':
                            analog = 'humdrum:END'
                        else:
                            continue
                    elif sourceType == 'recording':
                        if typeStr == 'releaseDate':
                            analog = 'humdrum:RRD'
                        elif typeStr == 'recordingDate':
                            analog = 'humdrum:RDT'
                        else:
                            continue
                    elif sourceType in ('printed', ''):
                        if typeStr == 'copyright':
                            analog = 'mei:printedSourceCopyright'
                        else:
                            analog = 'humdrum:PDT'
                    else:
                        continue

                m21DateObj: m21.metadata.DatePrimitive | str = (
                    self.m21DatePrimitiveOrStringFromDateElement(subEl, analog, md)
                )
                if m21DateObj:
                    M21Utilities.addIfNotADuplicate(md, analog, m21DateObj)

    def processRepository(
        self,
        element: MeiElement,
        defaultAnalog: str,
        md: m21.metadata.Metadata
    ):
        text: str = element.text.strip()
        if not text:
            return

        analog: str = element.get('analog', '')
        if not M21Utilities.isUsableMetadataKey(md, analog):
            if defaultAnalog:
                analog = defaultAnalog
            else:
                return

        M21Utilities.addIfNotADuplicate(md, analog, text)

    def processRespStmt(self, element: MeiElement, md: m21.metadata.Metadata, context: str = ''):
        defaultRole: str = ''
        for subEl in element.findAll('*', recurse=False):
            if subEl.name == 'resp':
                defaultRole = subEl.text.strip()
            elif subEl.name in ('name', 'persName', 'corpName'):
                # defaultRole will be overridden by @role, if present
                # if name element has @analog, that will override everything.
                self.processContributor(subEl, '', defaultRole, md, context=context)

    def processEncodingDesc(self, encodingDescElement: MeiElement) -> m21.metadata.Metadata:
        md = m21.metadata.Metadata()

        # Here's a fine place to add the fact that it was converter21 that parsed the MEI
        # to create this music21 score.
        M21Utilities.addIfNotADuplicate(
            md,
            'software',
            SharedConstants._CONVERTER21_NAME,
            {
                'meiVersion': SharedConstants._CONVERTER21_VERSION
            }
        )

        for subEl in encodingDescElement.findAll('*', recurse=False):
            if subEl.name == 'editorialDecl':
                self.processElementContainingParagraphsAndLineGroups(subEl, '', '', md)
            elif subEl.name == 'appInfo':
                for application in subEl.findAll('application', recurse=False):
                    name: MeiElement | None = application.findFirst('name', recurse=False)
                    if name is None:
                        continue
                    appName: str = name.text.strip()
                    if not appName:
                        continue
                    other: dict[str, str] = {}
                    version: str = application.get('version', '')
                    if version:
                        other['meiVersion'] = version
                    M21Utilities.addIfNotADuplicate(
                        md,
                        'software',
                        appName,
                        other
                    )

        return md

    def processWorkList(self, workListElement: MeiElement) -> m21.metadata.Metadata:
        md = m21.metadata.Metadata()

        # Note that we only deal with top-level <work> elements in <workList>.
        # Nested <work>s are out-of-scope.
        works: list[MeiElement] = workListElement.findAll('work', recurse=False)
        mainWorks: set[MeiElement] = set()
        parentWorks: set[MeiElement] = set()
        groupWorks: set[MeiElement] = set()
        collectionWorks: set[MeiElement] = set()
        associatedWorks: set[MeiElement] = set()

        if not works:
            return md

        # annotate the works, with 'parent'/'child', 'group'/'member', or
        # 'collection'/'member' links.
        for work in works:
            relationList: MeiElement | None = work.findFirst('relationList', recurse=False)
            if relationList is None:
                continue

            relations: list[MeiElement] = relationList.findAll('relation', recurse=False)
            if not relations:
                continue

            for relation in relations:
                rel: str = relation.attrib.get('rel', '')
                target: str = relation.attrib.get('target', '')
                relType: str = relation.attrib.get('type', '')
                parentsTypeName: str = ''
                childrenTypeName: str = ''
                if rel == 'isPartOf' and target:
                    # our MEI exporter writes  @rel="isPartOf" @type= in order to make clear
                    # which Humdrum-style relationship we are describing.
                    if relType == 'isMemberOfCollection':
                        parentsTypeName = 'meiCollections'
                        childrenTypeName = 'meiMembers'
                    elif relType == 'isMemberOfGroup':
                        parentsTypeName = 'meiGroups'
                        childrenTypeName = 'meiMembers'
                    elif relType == 'isChildOfParent':
                        parentsTypeName = 'meiParents'
                        childrenTypeName = 'meiChildren'
                    else:
                        # default for 'isPartOf' is 'isMemberOfCollection'
                        parentsTypeName = 'meiCollections'
                        childrenTypeName = 'meiMembers'

                    if getattr(work, parentsTypeName, None) is None:
                        setattr(work, parentsTypeName, [])

                    for xmlId in target.split(' '):
                        xmlId = MeiShared.removeOctothorpe(xmlId)
                        group: MeiElement | None = (
                            workListElement.findFirstWithAttributeValue(
                                _XMLID,
                                xmlId,
                                recurse=False
                            )
                        )
                        if not group:
                            continue

                        getattr(work, parentsTypeName).append(group)
                        if getattr(group, childrenTypeName, None) is None:
                            setattr(group, childrenTypeName, [])
                        getattr(group, childrenTypeName).append(work)
                elif rel == 'hasPart' and target:
                    # same, but backward
                    # 'hasPart' is interpreted as 'hasCollectionMember' (our MEI writer
                    # doesn't write rel="hasPart", so we have no further info)
                    parentsTypeName = 'meiCollections'
                    childrenTypeName = 'meiMembers'

                    if getattr(work, childrenTypeName, None) is None:
                        setattr(work, childrenTypeName, [])

                    for xmlId in target.split(' '):
                        xmlId = MeiShared.removeOctothorpe(xmlId)
                        member: MeiElement | None = (
                            workListElement.findFirstWithAttributeValue(
                                _XMLID,
                                xmlId,
                                recurse=False
                            )
                        )
                        if not member:
                            continue

                        getattr(work, childrenTypeName).append(group)
                        if getattr(group, parentsTypeName, None) is None:
                            setattr(group, parentsTypeName, [])
                        getattr(group, parentsTypeName).append(work)
                elif rel == 'host' and target:
                    # handle this, even though it's not strictly allowed.
                    # It implies 'parent'/'child'
                    parentsTypeName = 'meiParents'
                    childrenTypeName = 'meiChildren'

                    if getattr(work, parentsTypeName, None) is None:
                        setattr(work, parentsTypeName, [])

                    for xmlId in target.split(' '):
                        xmlId = MeiShared.removeOctothorpe(xmlId)
                        parent: MeiElement | None = (
                            workListElement.findFirstWithAttributeValue(
                                _XMLID,
                                xmlId,
                                recurse=False
                            )
                        )
                        if not parent:
                            continue

                        getattr(work, parentsTypeName).append(group)
                        if getattr(group, childrenTypeName, None) is None:
                            setattr(group, childrenTypeName, [])
                        getattr(group, childrenTypeName).append(work)

        # First pass at categorizing works.  Use work@type (only values that could have
        # been set by our MEI writer).  But also rule out non-typed works with children
        # or members from being a main work (these could be from other MEI writers).
        for work in works:
            workType: str = work.attrib.get('type', '')
            if workType == 'associated':
                associatedWorks.add(work)
                continue
            if workType == 'parent':
                parentWorks.add(work)
                continue
            if workType == 'collection':
                collectionWorks.add(work)
                continue
            if workType == 'group':
                groupWorks.add(work)
                continue
            if getattr(work, 'meiChildren', []) or getattr(work, 'meiMembers', []):
                continue

            mainWorks.add(work)

        if not mainWorks:
            mainWorks.add(works[0])

        # Figure out if we have any parent/group/collection works (of the mainWorks).
        # This is redundant for MEI files we wrote, but non-redundant for MEI files
        # we didn't write.
        for mainWork in mainWorks:
            parentWorks.update(getattr(mainWork, 'meiParents', []))
            groupWorks.update(getattr(mainWork, 'meiGroups', []))
            collectionWorks.update(getattr(mainWork, 'meiCollections', []))

        # Pull only titles out of the parent/group/collection/associated works.  There's
        # no other metadata here that can map to music21 or Humdrum metadata.
        titleElements: list[MeiElement]
        for work in parentWorks:
            titleElements = work.findAll('title', recurse=False)
            for titleEl in titleElements:
                self.processTitleOrTitlePart(titleEl, 'humdrum:OPR', '', md)

        for work in groupWorks:
            titleElements = work.findAll('title', recurse=False)
            for titleEl in titleElements:
                self.processTitleOrTitlePart(titleEl, 'humdrum:GTL', '', md)

        for work in collectionWorks:
            titleElements = work.findAll('title', recurse=False)
            for titleEl in titleElements:
                self.processTitleOrTitlePart(titleEl, 'humdrum:GCO', '', md)

        for work in associatedWorks:
            titleElements = work.findAll('title', recurse=False)
            for titleEl in titleElements:
                self.processTitleOrTitlePart(titleEl, 'humdrum:GAW', '', md)

        # OK, now for the main works, we process everything we see (including any titles)
        for work in mainWorks:
            allElements = work.findAll('*', recurse=False)
            for elem in allElements:
                self.processMainWorkSubElement(elem, md)

        return md

    def processMainWorkSubElement(self, element: MeiElement, md: m21.metadata.Metadata):
        if element.name == 'identifier':
            self.processIdentifier(element, md)
        elif element.name == 'title':
            self.processTitleOrTitlePart(element, '', '', md)
        elif element.name == 'composer':
            self.processComposer(element, md)
        elif element.name == 'lyricist':
            self.processContributor(element, 'humdrum:LYR', '', md)
        elif element.name == 'librettist':
            self.processContributor(element, 'humdrum:LIB', '', md)
        elif element.name == 'funder':
            self.processContributor(element, 'humdrum:OCO', '', md)
        elif element.name == 'contributor':
            self.processContributor(element, '', '', md)
        elif element.name == 'sponsor':
            self.processContributor(element, '', '', md)
        elif element.name == 'creation':
            self.processCreation(element, md, context='mainWork')
        elif element.name == 'history':
            self.processElementContainingParagraphsAndLineGroups(element, '', 'humdrum:HAO', md)
        elif element.name == 'langUsage':
            self.processLangUsage(element, md)
        elif element.name == 'classification':
            self.processClassification(element, md)
        elif element.name == 'expressionList':
            self.processExpressionList(element, md)

    def processNotesStmt(
        self,
        element: MeiElement,
        defaultAnalog: str,
        md: m21.metadata.Metadata
    ):
        defaultLang: str = element.get(_XMLLANG, '')
        for elem in element.findAll('annot', recurse=False):
            self.processElementContainingParagraphsAndLineGroups(
                elem,
                defaultLang,
                defaultAnalog,
                md
            )

    def processIdentifier(self, element: MeiElement, md: m21.metadata.Metadata):
        text: str
        _styleDict: dict[str, str]
        text, _styleDict = MeiShared.textFromElem(element)
        text = text.strip()
        if not text:
            return

        typeStr: str = element.get('type', '')
        analog: str = element.get('analog', '')
        if not M21Utilities.isUsableMetadataKey(md, analog):
            # compute what analog should be
            if text.startswith('Koechel') or text.startswith('Köchel'):
                analog = 'humdrum:SCA'
            elif text.startswith('BWV'):
                analog = 'humdrum:SCT'
            elif typeStr == 'albumCatalogNumber':
                analog = 'humdrum:RC#'
            else:
                # we can't interpret this identifier
                return

        M21Utilities.addIfNotADuplicate(md, analog, text)

    def getMadsAuthorityDataForElement(self, element: Element | MeiElement) -> MeiElement | None:
        output: MeiElement | None = None
        authURI: str = element.get('auth.uri', '')
        if authURI:
            authURI = MeiShared.removeOctothorpe(authURI)
            if authURI in self.madsAuthorityDataByID:
                output = self.madsAuthorityDataByID[authURI]
        return output

    def processComposer(self, element: MeiElement, md: m21.metadata.Metadata):
        names: list[str] = []
        types: list[str] = []
        analogs: list[str] = []
        elementNames: list[str] = []
        madsElements: list[MeiElement | None] = []

        analog: str = element.get('analog', '')
        typeStr: str = element.get('type', '')
        cert: str = element.get('cert', '')
        mads: MeiElement | None = self.getMadsAuthorityDataForElement(element)

        name: str = element.text
        name = name.strip()
        if name:
            # <composer>name</composer>
            if not M21Utilities.isUsableMetadataKey(md, analog):
                # compute what analog should be
                if typeStr == 'alias':
                    analog = 'humdrum:COL'
                elif cert == 'medium':
                    analog = 'humdrum:COA'
                elif cert == 'low':
                    analog = 'humdrum:COS'
                else:
                    analog = 'humdrum:COM'
            M21Utilities.addIfNotADuplicate(md, analog, name)
            if mads is not None:
                self.processComposerMADSInfo(mads, md)

        # Whether or not <composer> held a name, check all persName/corpName/name
        # subElements as well.
        for elementName in ('persName', 'corpName', 'name'):
            nameEls: list[MeiElement] = element.findAll(elementName, recurse=False)
            for nameEl in nameEls:
                _styleDict: dict[str, str]
                name, _styleDict = MeiShared.textFromElem(nameEl)
                name = name.strip()
                if name:
                    analog = nameEl.get('analog', '')
                    typeStr = nameEl.get('type', '')
                    names.append(name)
                    types.append(typeStr)
                    analogs.append(analog)
                    elementNames.append(elementName)
                    madsElements.append(self.getMadsAuthorityDataForElement(nameEl))

        for name, typeStr, analog, elementName, mads in zip(
                names, types, analogs, elementNames, madsElements):
            if not M21Utilities.isUsableMetadataKey(md, analog):
                # compute what analog should be
                if elementName == 'corpName':
                    analog = 'humdrum:COC'
                elif typeStr == 'alias':
                    analog = 'humdrum:COL'
                elif cert == 'medium':
                    analog = 'humdrum:COA'
                elif cert == 'low':
                    analog = 'humdrum:COS'
                else:
                    analog = 'humdrum:COM'
            M21Utilities.addIfNotADuplicate(md, analog, name)
            if mads is not None:
                self.processComposerMADSInfo(mads, md)

    def processComposerMADSInfo(self, mads: MeiElement, md: m21.metadata.Metadata):
        # we currently only look at the first variant, for an alias
        variant: MeiElement | None = mads.findFirst('variant', recurse=False)
        if variant is not None:
            variantType: str = variant.get('type', '')
            otherType: str = variant.get('otherType', '')
            if (variantType == 'abbreviation'
                    or (variantType == 'other'
                        and otherType in ('humdrum:COL', 'alias', 'stageName'))):
                # this is a composerAlias
                nameEl: MeiElement | None = variant.findFirst('name', recurse=False)
                if nameEl is not None:
                    namePart: MeiElement | None = nameEl.findFirst('namePart', recurse=False)
                    if namePart is not None:
                        name: str = namePart.text
                        name = name.strip()
                        if name:
                            M21Utilities.addIfNotADuplicate(md, 'humdrum:COL', name)

        # look at personInfo for birthDate/deathDate/birthPlace/deathPlace/nationality
        personInfo: MeiElement | None = mads.findFirst('personInfo', recurse=False)
        if personInfo is not None:
            birthDateEl: MeiElement | None = personInfo.findFirst('birthDate', recurse=False)
            deathDateEl: MeiElement | None = personInfo.findFirst('deathDate', recurse=False)
            birthPlaceEl: MeiElement | None = personInfo.findFirst('birthPlace', recurse=False)
            deathPlaceEl: MeiElement | None = personInfo.findFirst('deathPlace', recurse=False)
            nationalityEl: MeiElement | None = personInfo.findFirst('nationality', recurse=False)
            if birthDateEl is not None and deathDateEl is not None:
                # add 'humdrum:CDT' metadata item
                birthIsoDate: str = birthDateEl.text.strip()
                deathIsoDate: str = deathDateEl.text.strip()
                if birthIsoDate and deathIsoDate:
                    m21BirthDatePrimitive: m21.metadata.DatePrimitive | None = (
                        M21Utilities.m21DatePrimitiveFromIsoDate(birthIsoDate)
                    )
                    m21DeathDatePrimitive: m21.metadata.DatePrimitive | None = (
                        M21Utilities.m21DatePrimitiveFromIsoDate(deathIsoDate)
                    )
                    if m21BirthDatePrimitive is not None and m21DeathDatePrimitive is not None:
                        # if ever 'humdrum:CDT' is officially added to music21, the value
                        # will have to be a DatePrimitive (which will have to be extended
                        # to support ranges of DatePrimitives).  For now it's always a
                        # Humdrum string, which can support them.
                        cdtDateBetween: str = M21Utilities.stringFromM21DatePrimitiveRange(
                            m21BirthDatePrimitive, m21DeathDatePrimitive
                        )

                        M21Utilities.addIfNotADuplicate(
                            md,
                            'humdrum:CDT',
                            cdtDateBetween
                        )

            if birthPlaceEl is not None:
                # add 'humdrum:CBL' metadata item
                name = birthPlaceEl.text.strip()
                if name:
                    M21Utilities.addIfNotADuplicate(md, 'humdrum:CBL', name)

            if deathPlaceEl is not None:
                # add 'humdrum:CDL' metadata item
                name = deathPlaceEl.text.strip()
                if name:
                    M21Utilities.addIfNotADuplicate(md, 'humdrum:CDL', name)

            if nationalityEl is not None:
                # add 'humdrum:CNT' metadata item
                name = nationalityEl.text.strip()
                if name:
                    M21Utilities.addIfNotADuplicate(md, 'humdrum:CNT', name)

    def processContributor(
        self,
        element: MeiElement,
        humdrumAnalog: str,
        defaultRole: str,
        md: m21.metadata.Metadata,
        context: str = ''
    ):
        names: list[str] = []
        analogs: list[str] = []
        analog: str = element.get('analog', '')
        contrib: m21.metadata.Contributor | None = None
        role: str = ''

        name: str = element.text
        name = name.strip()
        if name:
            # <element>name</element>
            if not M21Utilities.isUsableMetadataKey(md, analog):
                # compute what analog should be
                if humdrumAnalog:
                    analog = humdrumAnalog
                else:
                    # must be <contributor> or some other m21-unsupported contributor,
                    # so call it 'otherContributor' and set up a Contributor with
                    # role = @role (if <contributor>) else role = element.name.
                    analog = 'otherContributor'
                    if element.name == 'contributor':
                        role = M21Utilities.adjustRoleFromContext(
                            element.get('role', ''),
                            context
                        )
                        if not role:
                            role = defaultRole
                    else:
                        # defaultRole _overrides_ element.name, but not @role
                        # (used for <persName> et al)
                        role = M21Utilities.adjustRoleFromContext(
                            element.get('role', ''),
                            context
                        )
                        if not role:
                            if defaultRole:
                                role = defaultRole
                            else:
                                role = element.name

                    # check to see if role maps to an official music21 role (a.k.a. uniqueName)
                    # and if so, use that for role instead (and use it for analog, as well,
                    # instead of 'otherContributor').
                    uniqueNm = M21Utilities.meiRoleToUniqueName(md, role)
                    if uniqueNm:
                        role = uniqueNm
                        analog = uniqueNm

                    contrib = m21.metadata.Contributor(name=name, role=role)

            if contrib is None and analog.startswith('humdrum:'):
                # we might need to convert to 'otherContributor'
                hdKey: str = analog[8:]
                if hdKey in M21Utilities.humdrumReferenceKeyToM21OtherContributorRole:
                    role = M21Utilities.humdrumReferenceKeyToM21OtherContributorRole[hdKey]
                    analog = 'otherContributor'
                    contrib = m21.metadata.Contributor(name=name, role=role)

            if contrib is not None:
                M21Utilities.addIfNotADuplicate(md, analog, contrib)
                contrib = None
            else:
                M21Utilities.addIfNotADuplicate(md, analog, name)

        # Whether or not <element> held a name, check all persName/corpName/name
        # subElements as well.
        for elementName in ('persName', 'corpName', 'name'):
            nameEls: list[MeiElement] = element.findAll(elementName, recurse=False)
            for nameEl in nameEls:
                _styleDict: dict[str, str]
                name, _styleDict = MeiShared.textFromElem(nameEl)
                name = name.strip()
                if name:
                    analog = nameEl.get('analog', '')
                    names.append(name)
                    analogs.append(analog)

        for name, analog in zip(names, analogs):
            if not M21Utilities.isUsableMetadataKey(md, analog):
                # compute what analog should be
                if humdrumAnalog:
                    analog = humdrumAnalog
                else:
                    # must be <contributor> or some other m21-unsupported contributor,
                    # so call it 'otherContributor' and set up a Contributor with
                    # role = @role (if <contributor>) else role = element.name.
                    analog = 'otherContributor'
                    if element.name == 'contributor':
                        role = element.get('role', '')
                        if not role:
                            role = defaultRole
                    else:
                        # defaultRole _overrides_ element.name, but not @role
                        # (used for <persName> et al)
                        role = element.get('role', '')
                        if not role:
                            if defaultRole:
                                role = defaultRole
                            else:
                                role = element.name
                        # Check to see if role maps to an official music21 role (a.k.a. uniqueName)
                        # and if so, use that for role instead (and use it for analog, as well,
                        # instead of 'otherContributor').
                    uniqueNm = M21Utilities.meiRoleToUniqueName(md, role)
                    if uniqueNm:
                        role = uniqueNm
                        analog = uniqueNm
                    contrib = m21.metadata.Contributor(name=name, role=role)

            if contrib is None and analog.startswith('humdrum:'):
                # we might need to convert to 'otherContributor'
                hdKey = analog[8:]
                if hdKey in M21Utilities.humdrumReferenceKeyToM21OtherContributorRole:
                    role = M21Utilities.humdrumReferenceKeyToM21OtherContributorRole[hdKey]
                    analog = 'otherContributor'
                    contrib = m21.metadata.Contributor(name=name, role=role)

            if contrib is not None:
                M21Utilities.addIfNotADuplicate(md, analog, contrib)
                contrib = None
            else:
                M21Utilities.addIfNotADuplicate(md, analog, name)

    def processCreation(
        self,
        element: MeiElement,
        md: m21.metadata.Metadata,
        context: str
    ):
        # context == 'mainWork' means main (encoded) work, grab everything you see
        # context == 'mainWork/expression' means an expression of the work, grab
        #   date and geogName, but only if analog is usable, or date@type/geogName@role
        #   tell you it's a performance.
        # context == anything else, ignore
        if (context not in ('mainWork', 'mainWork/expression')
                and not context.startswith('source')):
            return

        dates: list[MeiElement] = element.findAll('date', recurse=False)
        countries: list[MeiElement] = element.findAll('country', recurse=False)
        settlements: list[MeiElement] = element.findAll('settlement', recurse=False)
        geogNames: list[MeiElement] = element.findAll('geogName', recurse=False)
        dedicatees: list[MeiElement] = element.findAll('dedicatee', recurse=False)

        for date in dates:
            analog: str = date.get('analog', '')
            if not M21Utilities.isUsableMetadataKey(md, analog):
                if context == 'mainWork/expression':
                    typeStr: str = date.get('type', '')
                    if typeStr == 'firstPerformance':
                        analog = 'humdrum:MPD'
                    elif typeStr == 'performance':
                        analog = 'humdrum:MDT'
                    else:
                        # skip this date; we don't know what it represents
                        continue
                elif context == 'mainWork' or context.startswith('source'):
                    analog = 'humdrum:ODT'
                else:
                    # Skip this date; we don't know what it represents.
                    continue

            m21DateObj: m21.metadata.DatePrimitive | str = (
                self.m21DatePrimitiveOrStringFromDateElement(date, analog, md)
            )
            if m21DateObj:
                M21Utilities.addIfNotADuplicate(md, analog, m21DateObj)

        if context == 'mainWork' or context.startswith('source'):
            for country in countries:
                text: str = country.text.strip()
                if not text:
                    continue
                analog = country.get('analog', '')
                if not M21Utilities.isUsableMetadataKey(md, analog):
                    analog = 'humdrum:OCY'
                M21Utilities.addIfNotADuplicate(md, analog, text)

            for settlement in settlements:
                text = settlement.text.strip()
                if not text:
                    continue
                analog = settlement.get('analog', '')
                if not M21Utilities.isUsableMetadataKey(md, analog):
                    analog = 'humdrum:OPC'
                M21Utilities.addIfNotADuplicate(md, analog, text)

        for geogName in geogNames:
            text = geogName.text.strip()
            if not text:
                continue
            analog = geogName.get('analog', '')
            if not M21Utilities.isUsableMetadataKey(md, analog):
                if context == 'mainWork/expression':
                    if geogName.get('role', '') == 'performanceLocation':
                        analog = 'humdrum:MLC'
                    else:
                        # skip this geogName; we don't know what it represents
                        continue
                elif context == 'mainWork' or context.startswith('source'):
                    if geogName.get('type', '') == 'coordinates':
                        analog = 'humdrum:ARL'
                    else:
                        analog = 'humdrum:ARE'
                else:
                    # Skip this geogName; we don't know what it represents.
                    continue

            M21Utilities.addIfNotADuplicate(md, analog, text)

        if context == 'mainWork' or context.startswith('source'):
            for dedicatee in dedicatees:
                text = dedicatee.text.strip()
                if not text:
                    continue
                analog = dedicatee.get('analog', '')
                if not M21Utilities.isUsableMetadataKey(md, analog):
                    analog = 'humdrum:ODE'
                M21Utilities.addIfNotADuplicate(md, analog, text)

    def processElementContainingParagraphsAndLineGroups(
        self,
        element: MeiElement,
        defaultLang: str,
        defaultAnalog: str,
        md: m21.metadata.Metadata
    ):
        # this can contain a list of <p> and/or <lg> elements, with the <lg>
        # elements each containing a list of <l> elements.  @xml:lang can be
        # found on <p>, <lg>, or <l> elements.  <l>'s @xml:lang overrides the
        # containing <lg>'s @xml:lang.
        localDefaultLang: str = element.get(_XMLLANG, '')
        if not localDefaultLang:
            localDefaultLang = defaultLang

        if element.text.strip():
            # This element might have straight text, and as such, is itself a
            # lineWithLanguage.
            self.processLineWithLanguage(element, localDefaultLang, defaultAnalog, md)

        for subElem in element.findAll('*', recurse=False):
            if subElem.name not in ('p', 'lg'):
                continue
            if subElem.name == 'p':
                # <p> can contain text.  It can also contain <lg>, so in that case,
                # <p> is an element containing lines...
                if subElem.text.strip():
                    self.processLineWithLanguage(subElem, localDefaultLang, defaultAnalog, md)
                self.processElementContainingParagraphsAndLineGroups(
                    subElem,
                    localDefaultLang,
                    defaultAnalog,
                    md
                )
            elif subElem.name == 'lg':
                lgLang: str = subElem.get(_XMLLANG, '')
                if not lgLang:
                    lgLang = localDefaultLang
                for lineEl in subElem.findAll('l', recurse=False):
                    self.processLineWithLanguage(lineEl, lgLang, defaultAnalog, md)

    def processLineWithLanguage(
        self,
        element: MeiElement,
        defaultLang: str,
        defaultAnalog: str,
        md: m21.metadata.Metadata,
    ):
        text: str = element.text.strip()
        if not text:
            return

        analog: str
        if element.name == 'l':
            analog = element.get('type', '')
        else:
            analog = element.get('analog', '')

        if not M21Utilities.isUsableMetadataKey(md, analog):
            if defaultAnalog:
                analog = defaultAnalog
            else:
                return

        lang: str = element.get(_XMLLANG, '')
        if not lang:
            lang = defaultLang

        if lang:
            mdText = m21.metadata.Text(text, language=lang)
        else:
            mdText = m21.metadata.Text(text)
        M21Utilities.addIfNotADuplicate(md, analog, mdText)

    def processLangUsage(self, element: MeiElement, md: m21.metadata.Metadata):
        for language in element.findAll('language', recurse=False):
            text: str = language.text.strip()
            if not text:
                continue

            analog: str = language.get('analog', '')
            if not analog:
                analog = 'humdrum:TXO'
            M21Utilities.addIfNotADuplicate(md, analog, text)

    def processClassification(self, element: MeiElement, md: m21.metadata.Metadata):
        for termList in element.findAll('termList', recurse=False):
            for term in termList.findAll('term', recurse=False):
                text: str = term.text.strip()
                if not text:
                    continue

                analog: str = term.get('analog', '')
                label: str = term.get('label', '')
                if not M21Utilities.isUsableMetadataKey(md, analog):
                    # Two of the possible classifications ('humdrum:AMD'
                    # aka 'mode' and 'humdrum:AMT' aka 'meter') have specific
                    # text formatting required.  So we will skip those if
                    # we don't see those two exact analogs.
                    if label == 'form':
                        analog = 'humdrum:AFR'
                    elif label == 'genre':
                        analog = 'humdrum:AGN'
                    elif label == 'style':
                        analog = 'humdrum:AST'
                    else:
                        continue

                M21Utilities.addIfNotADuplicate(md, analog, text)

    def processExpressionList(self, element: MeiElement, md: m21.metadata.Metadata):
        for expression in element.findAll('expression', recurse=False):
            self.processExpression(expression, md)

    def processExpression(self, element: MeiElement, md: m21.metadata.Metadata):
        for creation in element.findAll('creation', recurse=False):
            self.processCreation(creation, md, context='mainWork/expression')

    def processTitleOrTitlePart(
        self,
        elem: MeiElement,
        analogFromContext: str,
        originalLanguage: str,
        md: m21.metadata.Metadata
    ) -> None:
        # analogFromContext: if set, it means that we only produce that bit of metadata from this
        # title and/or titlePart(s).  Ignore other things like 'movementName', 'alternativeTitle',
        # etc.
        text: str
        if elem.name == 'title':
            # title might have embedded <titlePart>s, so only grab that first bit of text.
            # But _do_ parse any <lb> etc before that first <titlePart>.
            text, _ = MeiShared.textFromElem(elem, endAt='titlePart')
        else:
            text, _ = MeiShared.textFromElem(elem)

        text = text.strip()
        if text:
            skipIt: bool = False
            typeStr: str = elem.get('type', '')
            lang: str | None = elem.get(_XMLLANG)
            label: str = elem.get('label', '')
            analog: str = elem.get('analog', '')
            if analogFromContext:
                if analog == analogFromContext:
                    pass  # take analog and run with it
                elif M21Utilities.isUsableMetadataKey(md, analog):
                    skipIt = True
                elif typeStr in ('alternative', 'popular', 'movementName', 'number'
                            'movementNumber', 'opusNumber', 'actNumber', 'sceneNumber'):
                    skipIt = True
                else:
                    # e.g. typeStr is None, 'main', 'uniform', 'translated', 'somethingElse'
                    # Don't skip it; call it analogFromContext.
                    analog = analogFromContext
            else:
                if not M21Utilities.isUsableMetadataKey(md, analog):
                    # use typeStr to compute what analog should have been
                    if typeStr == 'alternative':
                        analog = 'humdrum:OTA'
                        if label == 'popular':
                            # verovio:iohumdrum.cpp writes @type="alternative" @label="popular"
                            # for 'humdrum:OTP' aka. 'popularTitle'
                            analog = 'humdrum:OTP'
                    elif typeStr == 'popular':
                        # This is what converter21's MEI exporter writes, and hopefully someday
                        # verovio will, too.
                        analog = 'humdrum:OTP'
                    elif typeStr in ('movementName', 'number',
                            'movementNumber', 'opusNumber',
                            'actNumber', 'sceneNumber'):
                        analog = (
                            'humdrum:'
                            + M21Utilities.m21MetadataPropertyUniqueNameToHumdrumReferenceKey[
                                typeStr
                            ]
                        )
                    else:
                        # e.g. typeStr is None, 'main', 'uniform', 'translated', 'somethingElse'
                        analog = 'humdrum:OTL'

            if not originalLanguage and lang and typeStr in ('', 'main', 'uniform'):
                # We trust the first title we see with @type=="main"/"uniform"/None
                # and @xml:lang="something" to tell us the original language (or
                # the caller might have passed it in, in which case we trust it,
                # and don't override it here).
                originalLanguage = lang

            isTranslated: bool = typeStr == 'translated'
            if originalLanguage and lang:
                # Override typeStr == 'translated' with more reliable info, because
                # typeStr == 'translated' can only happen with main/uniform titles,
                # the other ones like 'movementName', 'opusNumber' et al have no way
                # to say they are translated.
                isTranslated = lang != originalLanguage

            if not skipIt:
                value = m21.metadata.Text(data=text, language=lang, isTranslated=isTranslated)
                M21Utilities.addIfNotADuplicate(md, analog, value)

        # Process <titlePart> sub-elements (unless this elem is already a titlePart)
        if elem.name == 'titlePart':
            return

        titleParts: list[MeiElement] = elem.findAll('titlePart', recurse=False)
        for titlePart in titleParts:
            # recurse, passing in any originalLanguage we have computed
            self.processTitleOrTitlePart(titlePart, analogFromContext, originalLanguage, md)

    def combineFileDescEncodingDescAndWorkListMetadata(
        self,
        fileDescMD: m21.metadata.Metadata | None,
        encodingDescMD: m21.metadata.Metadata | None,
        workListMD: m21.metadata.Metadata | None
    ) -> m21.metadata.Metadata:
        # 1. Take everything from fileDescMD.
        # 2. Take everything from workListMD, replacing anything already there (i.e. overriding
        # anything from fileDescMD).
        # 3. Add everything from encodingDescMD (it shouldn't overlap).
        # 4. If 'title' and 'movementName' are identical singletons, get rid of 'title', it's
        # really the movementName.
        output = m21.metadata.Metadata()
        key: str
        values: list[m21.metadata.ValueType]
        if fileDescMD is not None:
            for key, values in fileDescMD._contents.items():
                output._contents[key] = values

        if workListMD is not None:
            for key, values in workListMD._contents.items():
                # Override anything from fileDescMD that has the same key as
                # something from workListMD.
                output._contents[key] = values

        if encodingDescMD is not None:
            # Add everything from encodingDescMD without throwing anything away
            for key, values in encodingDescMD._contents.items():
                # Check for duplicates
                existingValues: list[m21.metadata.ValueType] = output._contents.get(key, [])
                newValues: list[m21.metadata.ValueType] = []
                if not existingValues:
                    newValues = values
                else:
                    for value in values:
                        dupeFound: bool = False
                        for existingValue in existingValues:
                            if value == existingValue:
                                dupeFound = True
                                break
                        if not dupeFound:
                            newValues.append(value)
                output._contents[key] = existingValues + newValues

        # if there is a single title and a single movementName, and they are exactly the same,
        # get rid of the title (it's only there because Verovio and converter21 put a combination
        # title in the fileDesc, and really, it's only the movementName that was really there.)
        titles: list[m21.metadata.ValueType] = output._contents.get('title', [])
        movementNames: list[m21.metadata.ValueType] = output._contents.get('movementName', [])
        if len(titles) == 1 and len(movementNames) == 1:
            if titles[0] == movementNames[0]:
                del output._contents['title']

        return output

    def m21DatePrimitiveOrStringFromDateElement(
        self,
        dateEl: MeiElement,
        analog: str,
        md: m21.metadata.Metadata
    ) -> m21.metadata.DatePrimitive | str:
        mustBeString: bool = not M21Utilities.isUsableMetadataKey(
            md,
            analog,
            includeHumdrumCustomKeys=False
        )

        m21DateObj: m21.metadata.DatePrimitive | None
        isodate: str = dateEl.get('isodate', '')
        if isodate:
            m21DateObj = M21Utilities.m21DatePrimitiveFromIsoDate(isodate)
            if m21DateObj is None:
                # try it as humdrum date/zeit
                m21DateObj = M21Utilities.m21DatePrimitiveFromString(isodate)
            if m21DateObj is not None:
                if mustBeString:
                    return M21Utilities.stringFromM21DateObject(m21DateObj)
                return m21DateObj

        dateStart: str = dateEl.get('notbefore', '') or dateEl.get('startdate', '')
        dateEnd: str = dateEl.get('notafter', '') or dateEl.get('enddate', '')
        # These are isodates, but if they don't parse, we'll try them as humdrum date/zeit
        if dateStart and dateEnd:
            betweenDates: str = dateStart + '/' + dateEnd
            m21DateObj = M21Utilities.m21DatePrimitiveFromIsoDate(betweenDates)
            if m21DateObj is None:
                betweenDates = dateStart + '-' + dateEnd
                m21DateObj = M21Utilities.m21DatePrimitiveFromString(betweenDates)
            if m21DateObj is not None:
                if mustBeString:
                    return M21Utilities.stringFromM21DateObject(m21DateObj)
                return m21DateObj

        if dateStart:
            afterDate: str = dateStart + '/..'
            m21DateObj = M21Utilities.m21DatePrimitiveFromIsoDate(afterDate)
            if m21DateObj is None:
                afterDate = '>' + dateStart
                m21DateObj = M21Utilities.m21DatePrimitiveFromString(afterDate)
            if m21DateObj is not None:
                if mustBeString:
                    return M21Utilities.stringFromM21DateObject(m21DateObj)
                return m21DateObj

        if dateEnd:
            beforeDate: str = '../' + dateEnd
            m21DateObj = M21Utilities.m21DatePrimitiveFromIsoDate(beforeDate)
            if m21DateObj is None:
                beforeDate = '<' + dateEnd
                m21DateObj = M21Utilities.m21DatePrimitiveFromString(beforeDate)
            if m21DateObj is not None:
                if mustBeString:
                    return M21Utilities.stringFromM21DateObject(m21DateObj)
                return m21DateObj

        # If nothing else is present (and parseable), go for dateEl.text.
        # If _that_ is present, but not parseable, warn, and return it as a str.
        text: str = dateEl.text.strip()
        if text:
            m21DateObj = M21Utilities.m21DatePrimitiveFromString(text)
            if m21DateObj is None:
                # try it as isodate
                m21DateObj = M21Utilities.m21DatePrimitiveFromIsoDate(text)
            if m21DateObj is not None:
                if mustBeString:
                    return M21Utilities.stringFromM21DateObject(m21DateObj)
                return m21DateObj
            # not parseable as date, just return the text
            return text

        return ''

    def processMusicBackElement(self, back: Element | MeiElement):
        if isinstance(back, Element):
            back = MeiElement(back)
        backLang: str = back.get(_XMLLANG, '')
        for div in back.findAll('div', recurse=False):
            divLang: str = div.get(_XMLLANG, '')
            if not divLang:
                divLang = backLang
            defaultAnalog: str = ''
            typeStr: str = div.get('type', '')
            if typeStr == 'textTranslation':
                defaultAnalog = 'humdrum:HTX'
            self.processElementContainingParagraphsAndLineGroups(
                div,
                divLang,
                defaultAnalog,
                self.m21Metadata
            )
