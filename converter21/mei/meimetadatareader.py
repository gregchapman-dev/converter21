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
from converter21.mei import MeiElement

environLocal = m21.environment.Environment('converter21.mei.meimetadatareader')

_XMLID = '{http://www.w3.org/XML/1998/namespace}id'
MEI_NS = '{http://www.music-encoding.org/ns/mei}'

_MISSED_DATE = 'Unable to decipher an MEI date "{}". Leaving as str.'


class MeiMetadataReader:
    def __init__(self, meiHead: Element) -> None:
        self.m21Metadata: m21.metadata.Metadata = m21.metadata.Metadata()
        if meiHead.tag != f'{MEI_NS}meiHead':
            environLocal.warn('MeiMetadataReader must be initialized with an <meiHead> element.')
            return

        self.meiHeadElement: MeiElement = MeiElement(meiHead)
        self.madsAuthorityDataByID: dict[str, MeiElement] = self.gatherMADSAuthorityData()

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
        meiHeadXmlStr: str = tostring(meiHead, encoding='unicode')
#         meiHeadElementStr: str = self.meiHeadElement.__repr__()
        meiHeadXmlStr = meiHeadXmlStr.strip()  # strips off any trailing \n and spaces
        self.m21Metadata.addCustom('meiraw:meiHead', meiHeadXmlStr)

    def gatherMADSAuthorityData(self) -> dict[str, MeiElement]:
        output: dict[str, MeiElement] = {}
        madsElements: list[MeiElement] = self.meiHeadElement.findAll('mads')
        for mads in madsElements:
            madsID: str = mads.get('ID', '')
            if madsID:
                output[madsID] = mads
        return output

    def processFileDesc(self, fileDescElement: MeiElement) -> m21.metadata.Metadata:
        output = m21.metadata.Metadata()
        return output

    def processEncodingDesc(self, encodingDescElement: MeiElement) -> m21.metadata.Metadata:
        output = m21.metadata.Metadata()
        return output

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
            relationList: MeiElement | None = work.findFirst('relationList')
            if relationList is None:
                continue

            relations: list[MeiElement] = relationList.findAll('relation')
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
                                'xml:id',
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
                                'xml:id',
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
                                'xml:id',
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
            self.processLyricist(element, md)
        elif element.name == 'librettist':
            self.processLibrettist(element, md)
        elif element.name == 'funder':
            self.processFunder(element, md)
        elif element.name == 'contributor':
            self.processContributor(element, '', md)
        elif element.name == 'creation':
            self.processCreation(element, md)
        elif element.name == 'history':
            self.processHistory(element, md)
        elif element.name == 'langUsage':
            self.processLangUsage(element, md)
        elif element.name == 'notesStmt':
            self.processNotesStmt(element, md)
        elif element.name == 'classification':
            self.processClassification(element, md)
        elif element.name == 'expressionList':
            self.processExpressionList(element, md)

    def processIdentifier(self, element: MeiElement, md: m21.metadata.Metadata):
        text: str
        _styleDict: dict[str, str]
        text, _styleDict = MeiShared.textFromElem(element)
        text = text.strip()
        if not text:
            return

        analog: str = element.get('analog', '')
        if not analog.startswith('humdrum:'):
            # compute what analog should be (make it start with 'humdrum:')
            if text.startswith('Koechel') or text.startswith('Köchel'):
                analog = 'humdrum:SCA'
            if text.startswith('BWV'):
                analog = 'humdrum:SCT'
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
            if not analog.startswith('humdrum:'):
                # compute what analog should be (make it start with 'humdrum:')
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
            if not analog.startswith('humdrum:'):
                # compute what analog should be (make it start with 'humdrum:')
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
        variant: MeiElement | None = mads.findFirst('variant')
        if variant is not None:
            variantType: str = variant.get('type', '')
            otherType: str = variant.get('otherType', '')
            if (variantType == 'abbreviation'
                    or (variantType == 'other'
                        and otherType in ('humdrum:COL', 'alias', 'stageName'))):
                # this is a composerAlias
                nameEl: MeiElement | None = variant.findFirst('name')
                if nameEl is not None:
                    namePart: MeiElement | None = nameEl.findFirst('namePart')
                    if namePart is not None:
                        name: str = namePart.text
                        name = name.strip()
                        if name:
                            M21Utilities.addIfNotADuplicate(md, 'humdrum:COL', name)

        # look at personInfo for birthDate/deathDate/birthPlace/deathPlace/nationality
        personInfo: MeiElement | None = mads.findFirst('personInfo')
        if personInfo is not None:
            birthDateEl: MeiElement | None = personInfo.findFirst('birthDate')
            deathDateEl: MeiElement | None = personInfo.findFirst('deathDate')
            birthPlaceEl: MeiElement | None = personInfo.findFirst('birthPlace')
            deathPlaceEl: MeiElement | None = personInfo.findFirst('deathPlace')
            nationalityEl: MeiElement | None = personInfo.findFirst('nationality')
            if birthDateEl is not None and deathDateEl is not None:
                # add 'humdrum:CDT' metadata item
                birthIsoDate: str = birthDateEl.text.strip()
                deathIsoDate: str = deathDateEl.text.strip()
                if birthIsoDate and deathIsoDate:
                    m21Dates = M21Utilities.m21DateListFromIsoDateList([birthIsoDate, deathIsoDate])
                    cdtDateBetween = m21.metadata.DateBetween(m21Dates)
                    if md._isStandardNamespaceName('humdrum:CDT'):
                        M21Utilities.addIfNotADuplicate(md, 'humdrum:CDT', cdtDateBetween)
                    else:
                        # can't use a Date, have to use a string, and it has to be a Humdrum string
                        M21Utilities.addIfNotADuplicate(
                            md,
                            'humdrum:CDT',
                            M21Utilities.stringFromM21DateObject(cdtDateBetween)
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
        md: m21.metadata.Metadata
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
            if not analog.startswith('humdrum:'):
                # compute what analog should be (make it start with 'humdrum:')
                if humdrumAnalog:
                    analog = humdrumAnalog
                else:
                    # must be <contributor>, so call it 'otherContributor' and
                    # set up a Contributor with role = @role
                    analog = 'otherContributor'
                    role = element.get('role', '')
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
            if not analog.startswith('humdrum:'):
                # compute what analog should be (make it start with 'humdrum:')
                if humdrumAnalog:
                    analog = humdrumAnalog
                else:
                    # must be <contributor>, so call it 'otherContributor' and
                    # set up a Contributor with role = @role
                    analog = 'otherContributor'
                    role = element.get('role', '')
                    contrib = m21.metadata.Contributor(name=name, role=role)
            if contrib is not None:
                M21Utilities.addIfNotADuplicate(md, analog, contrib)
                contrib = None
            else:
                M21Utilities.addIfNotADuplicate(md, analog, name)

    def processLyricist(self, element: MeiElement, md: m21.metadata.Metadata):
        self.processContributor(element, 'humdrum:LYR', md)

    def processLibrettist(self, element: MeiElement, md: m21.metadata.Metadata):
        self.processContributor(element, 'humdrum:LIB', md)

    def processFunder(self, element: MeiElement, md: m21.metadata.Metadata):
        self.processContributor(element, 'humdrum:OCO', md)

    def processCreation(self, element: MeiElement, md: m21.metadata.Metadata):
        pass

    def processHistory(self, element: MeiElement, md: m21.metadata.Metadata):
        pass

    def processLangUsage(self, element: MeiElement, md: m21.metadata.Metadata):
        pass

    def processNotesStmt(self, element: MeiElement, md: m21.metadata.Metadata):
        pass

    def processClassification(self, element: MeiElement, md: m21.metadata.Metadata):
        pass

    def processExpressionList(self, element: MeiElement, md: m21.metadata.Metadata):
        pass

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
        # title might have embedded <titlePart>s, so only grab that first bit of text
        text = elem.text
        text = text.strip()
        if text:
            skipIt: bool = False
            typeStr: str = elem.get('type', '')
            lang: str | None = elem.get('xml:lang')
            label: str = elem.get('label', '')
            analog: str = elem.get('analog', '')
            if analogFromContext:
                if analog == analogFromContext:
                    pass  # take analog and run with it
                elif analog.startswith('humdrum:'):
                    skipIt = True
                elif typeStr in ('alternative', 'popular', 'movementName', 'number'
                            'movementNumber', 'opusNumber', 'actNumber', 'sceneNumber'):
                    skipIt = True
                else:
                    # e.g. typeStr is None, 'main', 'uniform', 'translated', 'somethingElse'
                    # Don't skip it; call it analogFromContext.
                    analog = analogFromContext
            else:
                if not analog.startswith('humdrum:'):
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
        if workListMD is not None:
            output = workListMD
        else:
            output = m21.metadata.Metadata()
        return output

    def updateWithBackMatter(self, back: Element, md: m21.metadata.Metadata):
        # back/div@type="textTranslation"/lg@lang=""/l@type="humdrum:HTX"@lang=""
        return

class MeiMetadataReaderOLD:
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

        # TODO: handle <titlePart> sub-elements

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
            elif typeStr == 'popular':
                uniqueName = 'popularTitle'

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
            m21DateObj = M21Utilities.m21DatePrimitiveFromIsoDate(isodate)
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
                m21DateObj = M21Utilities.m21DatePrimitiveFromIsoDate(dateEl.text)
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


