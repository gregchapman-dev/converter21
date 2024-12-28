# ------------------------------------------------------------------------------
# Name:          meimetadata.py
# Purpose:       MeiMetadata is an object that takes a music21 Metadata
#                object, and computes the MEI structure for it.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
# from xml.etree.ElementTree import TreeBuilder
import typing as t

import music21 as m21

# from converter21.mei import MeiExportError
# from converter21.mei import MeiInternalError
from converter21.mei import MeiElement
from converter21.shared import M21Utilities
from converter21.shared import SharedConstants
from converter21.shared import DebugTreeBuilder as TreeBuilder

environLocal = m21.environment.Environment('converter21.mei.meimetadata')

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class MeiMetadataItem:
    def __init__(self, m21Item: tuple[str, t.Any], md: m21.metadata.Metadata) -> None:
        self.key: str = m21Item[0]
        self.value: t.Any = m21Item[1]

        # self.uniqueName is only set if self.key is a standard music21 metadata
        #   unique name.
        # self.humdrumRefKey is set in two cases:
        #   1. self.key is 'humdrum:XXX' and 'XXX' is something we understand
        #       (we share this knowledge with our humdrum converter).
        #   2. self.key is a standard music21 uniqueName, and it maps to a
        #       particular humdrum key (this is knowledge shared with our
        #       humdrum converter).

        self.uniqueName: str = ''
        self.humdrumRefKey: str = ''
        self.meiMetadataKey: str = ''
        if md._isStandardUniqueName(self.key):
            self.uniqueName = self.key
            self.humdrumRefKey = (
                M21Utilities.m21MetadataPropertyUniqueNameToHumdrumReferenceKey.get(self.key, '')
            )
            if self.uniqueName == 'otherContributor' and not self.humdrumRefKey:
                if t.TYPE_CHECKING:
                    assert isinstance(self.value, m21.metadata.Contributor)
                role: str = self.value.role
                self.humdrumRefKey = (
                    M21Utilities.m21OtherContributorRoleToHumdrumReferenceKey.get(role, '')
                )

        elif self.key.startswith('humdrum:'):
            hdKey: str = self.key[8:]
            if hdKey in M21Utilities.validHumdrumReferenceKeys:
                self.humdrumRefKey = hdKey
        elif self.key.startswith('mei:'):
            if self.key in M21Utilities.validMeiMetadataKeys:
                self.meiMetadataKey = self.key

        # self.isCustom is True if we don't have a uniqueName or humdrumRefKey or meiMetadataKey
        self.isCustom: bool = (
            not self.uniqueName and not self.humdrumRefKey and not self.meiMetadataKey
        )

        self.isContributor: bool = md._isContributorUniqueName(self.uniqueName)

        # convert self.value to an appropriate string (no html escaping yet)
        self.meiValue: str = M21Utilities.m21MetadataValueToString(self.value, lineFeedOK=True)

        # Add any other attributes set by converter21 importers (e.g. MEI importer
        # will have set value.meiVersion to 'version', which we will translate to
        # @version="version")
        self.meiOtherAttribs: dict[str, str] = {}
        otherAttribs: set[str] = getattr(self.value, 'c21OtherAttribs', set())
        for attrib in otherAttribs:
            version: str = ''
            if attrib in ('meiVersion', 'humdrumVersion'):
                version = getattr(self.value, attrib, '')
            if version:
                self.meiOtherAttribs['version'] = version

class MeiMetadata:
    def __init__(self, m21Metadata: m21.metadata.Metadata | None) -> None:
        self.m21Metadata: m21.metadata.Metadata | None = m21Metadata
        # self.contents is structured just like m21Metadata._contents v8 and later,
        # except that the key is the humdrum ref key (if there is one), or the
        # uniqueName (if there is one), or the custom key if that's all there is.
        self.contents: dict[str, list[MeiMetadataItem]] = {}
        if m21Metadata is not None:
            for m21Item in m21Metadata.all(returnPrimitives=True, returnSorted=False):
                meiItem = MeiMetadataItem(m21Item, m21Metadata)
                key: str = (
                    meiItem.humdrumRefKey
                    or meiItem.uniqueName
                    or meiItem.meiMetadataKey
                    or meiItem.key
                )
                currList: list[MeiMetadataItem] | None = self.contents.get(key, None)
                if currList is None:
                    self.contents[key] = [meiItem]
                else:
                    currList.append(meiItem)

        # The xml:id of the main work (the work that is actually encoded).
        # This will be referenced in mdiv@decls (or maybe music@decls).
        self.mainWorkXmlId: str = ''

        # Saved off state during makeRootElement (e.g. MeiElement trees that
        # may need to be re-used).

        # These are the simplified title and composers, that are used in
        # <fileDesc> and <source>.  The main <work> will have ALL the details.
        self.simpleTitleElement: MeiElement | None = None
        self.simpleComposerElements: list[MeiElement] = []

        # This element contains any <mads> elements that will end up in <work>/<extMeta>.
        self.madsCollection: MeiElement | None = None

    def makeRootElement(self, tb: TreeBuilder):
        meiHead: MeiElement = MeiElement('meiHead')
        fileDesc: MeiElement = self.makeFileDescElement()
        encodingDesc: MeiElement | None = self.makeEncodingDescElement()
        workList: MeiElement | None = self.makeWorkListElement()
        manifestationList: MeiElement | None = self.makeManifestationListElement()
        extMeta: MeiElement | None = self.makeExtMetaElementForMeiHead()

        # fileDesc is required
        meiHead.subElements.append(fileDesc)

        if encodingDesc:
            meiHead.subElements.append(encodingDesc)
        if workList:
            meiHead.subElements.append(workList)
        if manifestationList:
            meiHead.subElements.append(manifestationList)
        if extMeta:
            meiHead.subElements.append(extMeta)

        meiHead.makeRootElement(tb)

    def anyExist(self, *args: str) -> bool:
        for arg in args:
            if self.contents.get(arg, []):
                return True
        return False

    def makeFileDescElement(self) -> MeiElement:
        # meiHead/fileDesc is required, so we never return None here
        fileDesc: MeiElement = MeiElement('fileDesc')

        # titleStmt is required, so we create/append in one step
        titleStmt: MeiElement = fileDesc.appendSubElement('titleStmt')

        if self.simpleTitleElement is None:
            self.simpleTitleElement = self.makeSimpleTitleElement()
        titleStmt.subElements.append(self.simpleTitleElement)

        # pubStmt describes the MEI file we are writing.  It is, of course,
        # unpublished, so we use <unpub> to say that.  This pubStmt will
        # always be non-empty, so create/append in one step
        pubStmt: MeiElement = fileDesc.appendSubElement('pubStmt')
        unpub: MeiElement = pubStmt.appendSubElement('unpub')
        unpub.text = (
            '''This MEI file was created by converter21's MEI writer. When
                   published, this unpub element should be removed, and the
                   enclosing pubStmt element should be properly filled out.'''
        )

        # sourceDesc: There are potentially multiple sources here, depending on what
        # metadata items we find.  One for the digital source, one for the printed
        # source, one for a recorded source, and one for an unpublished manuscript
        # source.
        # if sourceDesc ends up empty, we will not add it, so create separately and
        # only append if not empty.
        sourceDesc: MeiElement = MeiElement('sourceDesc')

        digitalSource: MeiElement | None = self.makeDigitalSource()
        if digitalSource is not None:
            sourceDesc.subElements.append(digitalSource)

        printedSource: MeiElement | None = self.makePrintedSource()
        if printedSource is not None:
            sourceDesc.subElements.append(printedSource)

        if digitalSource is not None and printedSource is not None:
            digitalSourceBibl: MeiElement | None = (
                digitalSource.findFirst('bibl', recurse=False)
            )
            printedSourceBibl: MeiElement | None = (
                printedSource.findFirst('bibl', recurse=False)
            )
            # relate them to eachother with 'otherFormat'.  They are the same,
            # just in different formats (printed vs digital).
            if digitalSourceBibl is not None and printedSourceBibl is not None:
                digitalSourceBibl.attrib['xml:id'] = 'source0_digital'
                printedSourceBibl.attrib['xml:id'] = 'source1_printed'
                digitalSourceBibl.appendSubElement(
                    'relatedItem',
                    {
                        'rel': 'otherFormat',
                        'target': '#source1_printed'
                    }
                )
                printedSourceBibl.appendSubElement(
                    'relatedItem',
                    {
                        'rel': 'otherFormat',
                        'target': '#source0_digital'
                    }
                )

        recordedSource: MeiElement | None = self.makeRecordedSource()
        if recordedSource is not None:
            sourceDesc.subElements.append(recordedSource)

        unpublishedSource: MeiElement | None = self.makeUnpublishedSource()
        if unpublishedSource is not None:
            sourceDesc.subElements.append(unpublishedSource)

        if not sourceDesc.isEmpty():
            fileDesc.subElements.append(sourceDesc)

        return fileDesc

    def makeDigitalSource(self) -> MeiElement | None:
        if not self.anyExist(
                'EED', 'ENC', 'EEV', 'EFL', 'YEP', 'YER',
                'END', 'YEC', 'YEM', 'YEN', 'TXL', 'ONB'):
            return None

        source: MeiElement = MeiElement('source', {'type': 'digital'})
        bibl: MeiElement = source.appendSubElement('bibl')
        if self.simpleTitleElement is None:
            self.simpleTitleElement = self.makeSimpleTitleElement()
        bibl.subElements.append(self.simpleTitleElement)
        if not self.simpleComposerElements:
            self.simpleComposerElements = self.makeSimpleComposerElements()
        if self.simpleComposerElements:
            bibl.subElements.extend(self.simpleComposerElements)

        editors: list[MeiMetadataItem] = self.contents.get('EED', [])
        encoders: list[MeiMetadataItem] = self.contents.get('ENC', [])
        versions: list[MeiMetadataItem] = self.contents.get('EEV', [])
        fileNumbers: list[MeiMetadataItem] = self.contents.get('EFL', [])
        publishers: list[MeiMetadataItem] = self.contents.get('YEP', [])
        releaseDates: list[MeiMetadataItem] = self.contents.get('YER', [])
        encodingDates: list[MeiMetadataItem] = self.contents.get('END', [])
        copyrights: list[MeiMetadataItem] = self.contents.get('YEC', [])
        copyrightStatements: list[MeiMetadataItem] = self.contents.get('YEM', [])
        copyrightCountries: list[MeiMetadataItem] = self.contents.get('YEN', [])
        textLanguages: list[MeiMetadataItem] = self.contents.get('TXL', [])
        notes: list[MeiMetadataItem] = self.contents.get('ONB', [])

        for editor in editors:
            editorEl: MeiElement = bibl.appendSubElement(
                'editor',
                {
                    'analog': 'humdrum:EED'
                }
            )
            editorEl.text = editor.meiValue

        if encoders:
            respStmt: MeiElement = bibl.appendSubElement('respStmt')

            for encoder in encoders:
                respEl: MeiElement = respStmt.appendSubElement('resp')
                respEl.text = 'encoder'
                persNameEl: MeiElement = respStmt.appendSubElement(
                    'persName',
                    {
                        'analog': 'humdrum:ENC'
                    }
                )
                persNameEl.text = encoder.meiValue

        for version in versions:
            versionEl: MeiElement = bibl.appendSubElement(
                'edition',
                {
                    'type': 'version',
                    'analog': 'humdrum:EEV'
                }
            )
            versionEl.text = version.meiValue

        for fileNumber in fileNumbers:
            fileNumberEl: MeiElement = bibl.appendSubElement(
                'extent',
                {
                    'type': 'fileNumber',
                    'unit': 'file',
                    'analog': 'humdrum:EFL'
                }
            )
            fileNumberEl.text = fileNumber.meiValue

        if publishers or releaseDates or encodingDates:
            imprint: MeiElement = bibl.appendSubElement('imprint')
            for publisher in publishers:
                publisherEl: MeiElement = imprint.appendSubElement(
                    'publisher',
                    {
                        'analog': 'humdrum:YEP'
                    }
                )
                publisherEl.text = publisher.meiValue

            for releaseDate in releaseDates:
                releaseDateEl: MeiElement = imprint.appendSubElement(
                    'date',
                    {
                        'type': 'releaseDate',
                        'analog': 'humdrum:YER'
                    }
                )
                releaseDateEl.fillInIsodate(releaseDate.value)
                releaseDateEl.text = releaseDate.meiValue

            for encodingDate in encodingDates:
                encodingDateEl: MeiElement = imprint.appendSubElement(
                    'date',
                    {
                        'type': 'encodingDate',
                        'analog': 'humdrum:END'
                    }
                )
                encodingDateEl.fillInIsodate(encodingDate.value)
                encodingDateEl.text = encodingDate.meiValue

        if copyrights or copyrightStatements or copyrightCountries:
            availability: MeiElement = bibl.appendSubElement('availability')
            for cpyright in copyrights:
                copyrightEl: MeiElement = availability.appendSubElement(
                    'useRestrict',
                    {
                        'type': 'copyright',
                        'analog': 'humdrum:YEC'
                    }
                )
                copyrightEl.text = cpyright.meiValue

            for copyrightStatement in copyrightStatements:
                copyrightStatementEl: MeiElement = availability.appendSubElement(
                    'useRestrict',
                    {
                        'type': 'copyrightStatement',
                        'analog': 'humdrum:YEM'
                    }
                )
                copyrightStatementEl.text = copyrightStatement.meiValue

            for copyrightCountry in copyrightCountries:
                copyrightCountryEl: MeiElement = availability.appendSubElement(
                    'useRestrict',
                    {
                        'type': 'copyrightCountry',
                        'analog': 'humdrum:YEN'
                    }
                )
                copyrightCountryEl.text = copyrightCountry.meiValue

        if notes:
            annot: MeiElement = bibl.appendSubElement('annot')
            language, allTheSameLanguage = self.getTextListLanguage(notes)
            lineGroup: MeiElement = annot.appendSubElement('lg')
            if allTheSameLanguage and language:
                lineGroup.attrib['xml:lang'] = language

            for note in notes:
                # <l> does not take @analog, so use @type instead (says Perry)
                line = lineGroup.appendSubElement('l', {'type': 'humdrum:ONB'})
                line.text = note.meiValue
                if note.value.language and not allTheSameLanguage:
                    line.attrib['xml:lang'] = note.value.language.lower()

        for textLanguage in textLanguages:
            textLanguageEl: MeiElement = bibl.appendSubElement(
                'textLang',
                {
                    'analog': 'humdrum:TXL'
                }
            )
            textLanguageEl.text = textLanguage.meiValue

        if bibl.isEmpty():
            # we check bibl because source is not empty: it contains bibl.
            return None
        return source

    def makePrintedSource(self) -> MeiElement | None:
        if not self.anyExist('LAR', 'PED', 'LOR', 'TRN', 'OCL', 'OVM', 'PTL',
                'PPR', 'PDT', 'PPP', 'PC#', 'mei:printedSourceCopyright'):
            return None

        arrangers: list[MeiMetadataItem] = self.contents.get('LAR', [])
        editors: list[MeiMetadataItem] = self.contents.get('PED', [])
        orchestrators: list[MeiMetadataItem] = self.contents.get('LOR', [])
        translators: list[MeiMetadataItem] = self.contents.get('TRN', [])
        collectors: list[MeiMetadataItem] = self.contents.get('OCL', [])
        volumeNumbers: list[MeiMetadataItem] = self.contents.get('OVM', [])
        volumeNames: list[MeiMetadataItem] = self.contents.get('PTL', [])
        publishers: list[MeiMetadataItem] = self.contents.get('PPR', [])
        datesPublished: list[MeiMetadataItem] = self.contents.get('PDT', [])
        locationsPublished: list[MeiMetadataItem] = self.contents.get('PPP', [])
        publisherCatalogNumbers: list[MeiMetadataItem] = self.contents.get('PC#', [])
        printedSourceCopyrights: list[MeiMetadataItem] = (
            self.contents.get('mei:printedSourceCopyright', [])
        )

        source: MeiElement = MeiElement('source', {'type': 'printed'})
        bibl: MeiElement = source.appendSubElement('bibl')

        for publisherCatalogNumber in publisherCatalogNumbers:
            identifierEl: MeiElement = bibl.appendSubElement(
                'identifier',
                {
                    'type': 'catalogNumber',
                    'analog': 'humdrum:PC#'
                }
            )
            identifierEl.text = publisherCatalogNumber.meiValue

        if self.simpleTitleElement is None:
            self.simpleTitleElement = self.makeSimpleTitleElement()
        bibl.subElements.append(self.simpleTitleElement)
        if not self.simpleComposerElements:
            self.simpleComposerElements = self.makeSimpleComposerElements()
        if self.simpleComposerElements:
            bibl.subElements.extend(self.simpleComposerElements)

        for editor in editors:
            editorEl: MeiElement = bibl.appendSubElement(
                'editor',
                {
                    'analog': 'humdrum:PED'
                }
            )
            editorEl.text = editor.meiValue

        if arrangers or orchestrators or translators or collectors:
            # arrangers could technically go outside <respStmt>, but
            # Perry requests that they go inside <respStmt> for ease
            # of conversion to his proposed v. 6.
            respStmt: MeiElement = bibl.appendSubElement('respStmt')

            for arranger in arrangers:
                respEl: MeiElement = respStmt.appendSubElement('resp')
                respEl.text = 'arranger'
                arrangerEl: MeiElement = respStmt.appendSubElement(
                    'persName',
                    {
                        'analog': 'humdrum:LAR'
                    }
                )
                arrangerEl.text = arranger.meiValue

            for orchestrator in orchestrators:
                respEl = respStmt.appendSubElement('resp')
                respEl.text = 'orchestrator'
                persNameEl: MeiElement = respStmt.appendSubElement(
                    'persName',
                    {
                        'analog': 'humdrum:LOR'
                    }
                )
                persNameEl.text = orchestrator.meiValue

            for translator in translators:
                respEl = respStmt.appendSubElement('resp')
                respEl.text = 'translator'
                persNameEl = respStmt.appendSubElement(
                    'persName',
                    {
                        'analog': 'humdrum:TRN'
                    }
                )
                persNameEl.text = translator.meiValue

            for collector in collectors:
                respEl = respStmt.appendSubElement('resp')
                respEl.text = 'collector/transcriber'
                persNameEl = respStmt.appendSubElement(
                    'name',
                    {
                        'analog': 'humdrum:OCL'
                    }
                )
                persNameEl.text = collector.meiValue

        if publishers or datesPublished or locationsPublished:
            imprint: MeiElement = bibl.appendSubElement('imprint')
            for publisher in publishers:
                publisherEl: MeiElement = imprint.appendSubElement(
                    'publisher',
                    {
                        'analog': 'humdrum:PPR'
                    }
                )
                publisherEl.text = publisher.meiValue
            for datePublished in datesPublished:
                dateEl: MeiElement = imprint.appendSubElement(
                    'date',
                    {
                        'type': 'datePublished',
                        'analog': 'humdrum:PDT'
                    }
                )
                dateEl.fillInIsodate(datePublished.value)
                dateEl.text = datePublished.meiValue

            for locationPublished in locationsPublished:
                geogNameEl: MeiElement = imprint.appendSubElement(
                    'geogName',
                    {
                        'role': 'locationPublished',
                        'analog': 'humdrum:PPP'
                    }
                )
                geogNameEl.text = locationPublished.meiValue

        if printedSourceCopyrights:
            availability: MeiElement = bibl.appendSubElement('availability')
            for printedSourceCopyright in printedSourceCopyrights:
                useRestrict: MeiElement = availability.appendSubElement(
                    'useRestrict',
                    {
                        'type': 'copyright'
                    }
                )
                useRestrict.text = printedSourceCopyright.meiValue

        for volumeName, volumeNumber in zip(volumeNames, volumeNumbers):
            relatedItem: MeiElement = bibl.appendSubElement(
                'relatedItem',
                {
                    'rel': 'host'
                }
            )
            relBibl: MeiElement = relatedItem.appendSubElement('bibl')
            titleElement = relBibl.appendSubElement(
                'title',
                {
                    'analog': 'humdrum:PTL'
                }
            )
            titleElement.text = volumeName.meiValue

            biblScope: MeiElement = relBibl.appendSubElement(
                'biblScope',
                {
                    'analog': 'humdrum:OVM'
                }
            )
            biblScope.text = volumeNumber.meiValue

        if len(volumeNames) - len(volumeNumbers) > 0:
            # we ignore any extra volume numbers, since a number without a name
            # isn't interesting.
            for volumeName in volumeNames[len(volumeNumbers):]:
                relatedItem = bibl.appendSubElement(
                    'relatedItem',
                    {
                        'rel': 'host'
                    }
                )
                relBibl = relatedItem.appendSubElement('bibl')
                titleElement = relBibl.appendSubElement(
                    'title',
                    {
                        'analog': 'humdrum:PTL'
                    }
                )
                titleElement.text = volumeName.meiValue

        if bibl.isEmpty():
            return None
        return source

    def makeRecordedSource(self) -> MeiElement | None:
        if not self.anyExist('RTL', 'RC#', 'MGN', 'MPN', 'MPS', 'RNP',
                'MCN', 'RMM', 'RRD', 'RLC', 'RDT', 'RT#'):
            return None

        source: MeiElement = MeiElement('source', {'type': 'recording'})
        biblStruct: MeiElement = source.appendSubElement('biblStruct')

        albumTitles: list[MeiMetadataItem] = self.contents.get('RTL', [])
        albumCatalogNumbers: list[MeiMetadataItem] = self.contents.get('RC#', [])
        ensembleNames: list[MeiMetadataItem] = self.contents.get('MGN', [])
        performerNames: list[MeiMetadataItem] = self.contents.get('MPN', [])
        suspectedPerformerNames: list[MeiMetadataItem] = self.contents.get('MPS', [])
        producers: list[MeiMetadataItem] = self.contents.get('RNP', [])
        conductors: list[MeiMetadataItem] = self.contents.get('MCN', [])
        manufacturers: list[MeiMetadataItem] = self.contents.get('RMM', [])
        releaseDates: list[MeiMetadataItem] = self.contents.get('RRD', [])
        recordingLocations: list[MeiMetadataItem] = self.contents.get('RLC', [])
        recordingDates: list[MeiMetadataItem] = self.contents.get('RDT', [])
        trackNumbers: list[MeiMetadataItem] = self.contents.get('RT#', [])
        longestLen: int = 0
        longestLen = max(
            longestLen,
            len(albumTitles),
            len(albumCatalogNumbers),
            len(ensembleNames),
            len(performerNames),
            len(suspectedPerformerNames),
            len(producers),
            len(conductors),
            len(manufacturers),
            len(releaseDates),
            len(recordingLocations),
            len(recordingDates),
            len(trackNumbers),
        )

        for i in range(0, longestLen):
            if i < len(trackNumbers):
                analytic: MeiElement = biblStruct.appendSubElement('analytic')
                if self.simpleTitleElement is None:
                    self.simpleTitleElement = self.makeSimpleTitleElement()
                analytic.subElements.append(self.simpleTitleElement)
                biblScope = analytic.appendSubElement(
                    'biblScope',
                    {
                        'type': 'trackNumber',
                        'unit': 'track',
                        'analog': 'humdrum:RT#'
                    }
                )
                biblScope.text = trackNumbers[i].meiValue

            if (i < len(albumTitles)
                    or i < len(albumCatalogNumbers)
                    or i < len(ensembleNames)
                    or i < len(performerNames)
                    or i < len(suspectedPerformerNames)
                    or i < len(producers)
                    or i < len(conductors)
                    or i < len(manufacturers)
                    or i < len(releaseDates)
                    or i < len(recordingLocations)
                    or i < len(recordingDates)):
                monogr: MeiElement = biblStruct.appendSubElement('monogr')

                if i < len(albumTitles):
                    albumTitle: MeiMetadataItem = albumTitles[i]

                    albumTitleEl: MeiElement = monogr.appendSubElement(
                        'title',
                        {
                            'analog': 'humdrum:RTL'
                        }
                    )
                    albumTitleEl.text = albumTitle.meiValue

                if i < len(albumCatalogNumbers):
                    albumCatalogNumber: MeiMetadataItem = albumCatalogNumbers[i]
                    albumCatalogNumberEl: MeiElement = monogr.appendSubElement(
                        'identifier',
                        {
                            'type': 'albumCatalogNumber',
                            'analog': 'humdrum:RC#'
                        }
                    )
                    albumCatalogNumberEl.text = albumCatalogNumber.meiValue

                if (i < len(ensembleNames)
                        or i < len(performerNames)
                        or i < len(suspectedPerformerNames)
                        or i < len(producers)
                        or i < len(conductors)):
                    respStmt: MeiElement = monogr.appendSubElement('respStmt')

                    if i < len(ensembleNames):
                        ensembleName: MeiMetadataItem = ensembleNames[i]
                        respEl = respStmt.appendSubElement('resp')
                        respEl.text = 'performer'
                        ensembleNameEl: MeiElement = respStmt.appendSubElement(
                            'corpName',
                            {
                                'type': 'ensembleName',
                                'analog': 'humdrum:MGN'
                            }
                        )
                        ensembleNameEl.text = ensembleName.meiValue

                    if i < len(performerNames):
                        performerName: MeiMetadataItem = performerNames[i]
                        respEl = respStmt.appendSubElement('resp')
                        respEl.text = 'performer'
                        performerNameEl: MeiElement = respStmt.appendSubElement(
                            'persName',
                            {
                                'analog': 'humdrum:MPN'
                            }
                        )
                        performerNameEl.text = performerName.meiValue

                    if i < len(suspectedPerformerNames):
                        suspectedPerformerName: MeiMetadataItem = suspectedPerformerNames[i]
                        respEl = respStmt.appendSubElement('resp')
                        respEl.text = 'performer'
                        suspectedPerformerNameEl: MeiElement = respStmt.appendSubElement(
                            'persName',
                            {
                                'cert': 'medium',
                                'analog': 'humdrum:MPS'
                            }
                        )
                        suspectedPerformerNameEl.text = suspectedPerformerName.meiValue

                    if i < len(producers):
                        producer: MeiMetadataItem = producers[i]
                        respEl = respStmt.appendSubElement('resp')
                        respEl.text = 'producer'
                        persNameEl: MeiElement = respStmt.appendSubElement(
                            'name',
                            {
                                'analog': 'humdrum:RNP'
                            }
                        )
                        persNameEl.text = producer.meiValue

                    if i < len(conductors):
                        conductor: MeiMetadataItem = conductors[i]
                        respEl = respStmt.appendSubElement('resp')
                        respEl.text = 'conductor'
                        persNameEl = respStmt.appendSubElement(
                            'persName',
                            {
                                'analog': 'humdrum:MCN'
                            }
                        )
                        persNameEl.text = conductor.meiValue

                if (i < len(manufacturers)
                        or i < len(releaseDates)
                        or i < len(recordingLocations)
                        or i < len(recordingDates)):
                    imprint: MeiElement = monogr.appendSubElement('imprint')

                    if i < len(manufacturers):
                        manufacturer: MeiMetadataItem = manufacturers[i]
                        manufacturerEl: MeiElement = imprint.appendSubElement(
                            'corpName',
                            {
                                'role': 'production/distribution',
                                'analog': 'humdrum:RMM'
                            }
                        )
                        manufacturerEl.text = manufacturer.meiValue

                    if i < len(releaseDates):
                        releaseDate: MeiMetadataItem = releaseDates[i]
                        releaseDateEl: MeiElement = imprint.appendSubElement(
                            'date',
                            {
                                'type': 'releaseDate',
                                'analog': 'humdrum:RRD'
                            }
                        )
                        releaseDateEl.fillInIsodate(releaseDate.value)
                        releaseDateEl.text = releaseDate.meiValue

                    if i < len(recordingLocations):
                        recordingLocation: MeiMetadataItem = recordingLocations[i]
                        recordingLocationEl: MeiElement = imprint.appendSubElement(
                            'geogName',
                            {
                                'role': 'recordingLocation',
                                'analog': 'humdrum:RLC'
                            }
                        )
                        recordingLocationEl.text = recordingLocation.meiValue

                    if i < len(recordingDates):
                        recordingDate: MeiMetadataItem = recordingDates[i]
                        recordingDateEl: MeiElement = imprint.appendSubElement(
                            'date',
                            {
                                'type': 'recordingDate',
                                'analog': 'humdrum:RDT'
                            }
                        )
                        recordingDateEl.fillInIsodate(recordingDate.value)
                        recordingDateEl.text = recordingDate.meiValue

        if biblStruct.isEmpty():
            return None
        return source

    def makeUnpublishedSource(self) -> MeiElement | None:
        if not self.anyExist('SMS', 'YOR', 'SML', 'YOO', 'YOE', 'YOY', 'SMA'):
            return None

        source: MeiElement = MeiElement('source', {'type': 'unpub'})
        bibl: MeiElement = source.appendSubElement('bibl')

        manuscriptNames: list[MeiMetadataItem] = self.contents.get('SMS', [])
        moreManuscriptNames: list[MeiMetadataItem] = self.contents.get('YOR', [])
        manuscriptLocations: list[MeiMetadataItem] = self.contents.get('SML', [])
        manuscriptOwners: list[MeiMetadataItem] = self.contents.get('YOO', [])
        editors: list[MeiMetadataItem] = self.contents.get('YOE', [])
        copyrightDates: list[MeiMetadataItem] = self.contents.get('YOY', [])
        acknowledgments: list[MeiMetadataItem] = self.contents.get('SMA', [])

        for manuscriptName in manuscriptNames:
            manuscriptNameEl: MeiElement = bibl.appendSubElement(
                'identifier',
                {
                    'analog': 'humdrum:SMS'
                }
            )
            manuscriptNameEl.text = manuscriptName.meiValue

        for manuscriptName in moreManuscriptNames:
            manuscriptNameEl = bibl.appendSubElement(
                'identifier',
                {
                    'analog': 'humdrum:YOR'
                }
            )
            manuscriptNameEl.text = manuscriptName.meiValue

        # do both again as <title>
        for manuscriptName in manuscriptNames:
            manuscriptNameEl = bibl.appendSubElement(
                'title',
                {
                    'analog': 'humdrum:SMS'
                }
            )
            manuscriptNameEl.text = manuscriptName.meiValue

        for manuscriptName in moreManuscriptNames:
            manuscriptNameEl = bibl.appendSubElement(
                'title',
                {
                    'analog': 'humdrum:YOR'
                }
            )
            manuscriptNameEl.text = manuscriptName.meiValue

        for manuscriptLocation in manuscriptLocations:
            manuscriptLocationEl = bibl.appendSubElement(
                'repository',
                {
                    'analog': 'humdrum:SML'
                }
            )
            manuscriptLocationEl.text = manuscriptLocation.meiValue

        for manuscriptOwner in manuscriptOwners:
            manuscriptOwnerEl = bibl.appendSubElement(
                'name',
                {
                    'role': 'manuscriptOwner',
                    'analog': 'humdrum:YOO'
                }
            )
            manuscriptOwnerEl.text = manuscriptOwner.meiValue

        for editor in editors:
            editorEl = bibl.appendSubElement(
                'editor',
                {
                    'analog': 'humdrum:YOE'
                }
            )
            editorEl.text = editor.meiValue

        for copyrightDate in copyrightDates:
            copyrightDateEl = bibl.appendSubElement(
                'date',
                {
                    'type': 'copyrightDate',
                    'analog': 'humdrum:YOY'
                }
            )
            copyrightDateEl.fillInIsodate(copyrightDate.value)
            copyrightDateEl.text = copyrightDate.meiValue

        if acknowledgments:
            annot: MeiElement = bibl.appendSubElement(
                'annot',
                {
                    'type': 'manuscriptAccessAcknowledgment',
                }
            )
            language, allTheSameLanguage = self.getTextListLanguage(acknowledgments)
            lineGroup: MeiElement = annot.appendSubElement('lg')
            if allTheSameLanguage and language:
                lineGroup.attrib['xml:lang'] = language

            for acknowledgment in acknowledgments:
                # <l> does not take @analog, so use @type instead (says Perry)
                line = lineGroup.appendSubElement('l', {'type': 'humdrum:SMA'})
                line.text = acknowledgment.meiValue
                if acknowledgment.value.language and not allTheSameLanguage:
                    line.attrib['xml:lang'] = acknowledgment.value.language.lower()

        if bibl.isEmpty():
            return None
        return source

    def makeSimpleComposerElements(self) -> list[MeiElement]:
        # Just all the COMs.  If no COMs, then do the COCs (corporate), the COAs (attributed),
        # the COSs (suspected), or the COLs (aliases), in that order of preference.
        output: list[MeiElement] = []
        composers: list[MeiMetadataItem] = self.contents.get('COM', [])
        if not composers:
            composers = self.contents.get('COC', [])
        if not composers:
            composers = self.contents.get('COA', [])
        if not composers:
            composers = self.contents.get('COS', [])
        if not composers:
            composers = self.contents.get('COL', [])
        if not composers:
            return output

        for composer in composers:
            composerElement = MeiElement('composer')
            output.append(composerElement)

            # composer cert
            composerCert: str = ''
            if composer.value.role == 'attributedComposer':
                composerCert = 'medium'
            elif composer.value.role == 'suspectedComposer':
                composerCert = 'low'
            if composerCert:
                # We put @cert on <composer>, not on <persName>.
                # The uncertainty is about whether this composer was involved,
                # not about what this composer's name was.
                composerElement.attrib['cert'] = composerCert

            nameElement: MeiElement = composerElement.appendSubElement('persName')
            nameElement.text = composer.meiValue

            # adjust nameElement.name and nameElement.attrib as necessary
            if composer.value.role == 'composerCorporate':
                nameElement.name = 'corpName'
            elif composer.value.role == 'composerAlias':
                nameElement.attrib['type'] = 'alias'

        return output

    def makeComposerElements(self) -> list[MeiElement]:
        # returns a list of <composer> elements
        # As a side effect, generates any <mads> XML for composer personal info
        # (e.g. birth and death dates/places, nationality), stashing them in
        # self.madsElements to emit later.

        output: list[MeiElement] = []
        composers: list[MeiMetadataItem] = self.contents.get('COM', [])
        attributedComposers: list[MeiMetadataItem] = self.contents.get('COA', [])
        suspectedComposers: list[MeiMetadataItem] = self.contents.get('COS', [])
        corporateComposers: list[MeiMetadataItem] = self.contents.get('COC', [])
        composerAliases: list[MeiMetadataItem] = self.contents.get('COL', [])
        composerDates: list[MeiMetadataItem] = self.contents.get('CDT', [])
        composerBirthPlaces: list[MeiMetadataItem] = self.contents.get('CBL', [])
        composerDeathPlaces: list[MeiMetadataItem] = self.contents.get('CDL', [])
        composerNationalities: list[MeiMetadataItem] = self.contents.get('CNT', [])
        # TODO: Prefer composer birth/death dates from Contributor value.
        # TODO: But first make Humdrum importer put them there.
        allComposers: list[MeiMetadataItem] = (
            composers + attributedComposers + suspectedComposers + corporateComposers
        )

        madsXmlIdIndex: int = 0
        for i, composer in enumerate(allComposers):
            # Assume association is done by ordering of the metadata item arrays
            # Currently our Humdrum importer assumes this ordering should match
            # the ordering in the file.
            composerAlias: MeiMetadataItem | None = None
            composerBirthAndDeathDate: MeiMetadataItem | None = None
            composerBirthPlace: MeiMetadataItem | None = None
            composerDeathPlace: MeiMetadataItem | None = None
            composerNationality: MeiMetadataItem | None = None
            if i < len(composerAliases):
                composerAlias = composerAliases[i]
            if i < len(composerDates):
                composerBirthAndDeathDate = composerDates[i]
            if i < len(composerBirthPlaces):
                composerBirthPlace = composerBirthPlaces[i]
            if i < len(composerDeathPlaces):
                composerDeathPlace = composerDeathPlaces[i]
            if i < len(composerNationalities):
                composerNationality = composerNationalities[i]

            composerElement = MeiElement('composer')
            output.append(composerElement)

            # composer persName ('COM'/'COA'/'COS')
            composerAnalog: str = 'humdrum:COM'
            composerCert: str = ''
            composerNameElementName: str = 'persName'
            if composer.value.role == 'attributedComposer':
                composerAnalog = 'humdrum:COA'
                composerCert = 'medium'
            elif composer.value.role == 'suspectedComposer':
                composerAnalog = 'humdrum:COS'
                composerCert = 'low'
            elif composer.value.role == 'composerCorporate':
                composerAnalog = 'humdrum:COC'
                composerNameElementName = 'corpName'

            if composerCert:
                # We put @cert on <composer>, not on <persName>.
                # The uncertainty is about whether this composer was involved,
                # not about this composer's name.
                composerElement.attrib['cert'] = composerCert

            nameElement: MeiElement = composerElement.appendSubElement(
                composerNameElementName,
                {
                    'analog': composerAnalog
                }
            )
            nameElement.text = composer.meiValue

            # MADS-style authority records (personal info about a composer)
            if (composerBirthAndDeathDate is None
                    and composerBirthPlace is None
                    and composerDeathPlace is None
                    and composerNationality is None):
                # nothing for MADS
                continue

            madsXmlId: str = f'mads{madsXmlIdIndex}'
            madsXmlIdIndex += 1

            # reference <mads> element from composer's nameElement
            nameElement.attrib['auth.uri'] = '#' + madsXmlId

            # There is extra info about the composer, that will need to go
            # in <work><extMeta><madsCollection><mads>
            if self.madsCollection is None:
                schemaLoc: str = (
                    'http://www.loc.gov/mads/v2 https://www.loc.gov/standards/mads/mads-2-1.xsd'
                )
                self.madsCollection = MeiElement(
                    'madsCollection',
                    {
                        'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                        'xsi:schemaLocation': schemaLoc,
                        'xmlns': 'http://www.loc.gov/mads/v2'
                    }
                )

            mads = self.madsCollection.appendSubElement('mads', {'ID': madsXmlId})

            authority: MeiElement = mads.appendSubElement('authority')
            name: MeiElement = authority.appendSubElement('name')
            if composerNameElementName == 'corpName':
                name.attrib['type'] = 'corporate'
            namePart: MeiElement = name.appendSubElement('namePart')
            namePart.text = composer.meiValue

            # composerAlias ('humdrum:COL') goes in <mads><variant>
            if composerAlias:
                variant: MeiElement = mads.appendSubElement(
                    'variant',
                    {
                        'type': 'other',
                        'otherType': 'humdrum:COL'
                    }
                )
                name = variant.appendSubElement('name')
                namePart = name.appendSubElement('namePart')
                namePart.text = composerAlias.meiValue

            # extra info goes in <mads><personInfo>
            if (composerBirthAndDeathDate is not None
                    or composerBirthPlace is not None
                    or composerDeathPlace is not None
                    or composerNationality is not None):
                personInfo: MeiElement = mads.appendSubElement('personInfo')
                if composerBirthAndDeathDate is not None:
                    isodateAttrs: dict[str, str] = (
                        M21Utilities.isoDateFromM21DatePrimitive(
                            composerBirthAndDeathDate.value,
                            edtf=True
                        )
                    )

                    # isodateAttrs will either contain 'edtf', or it will
                    # contain one or both of 'startedtf' and 'endedtf',
                    # or it will be empty.
                    isodate: str = isodateAttrs.get('edtf', '')
                    isodateBirth: str = isodateAttrs.get('startedtf', '')
                    isodateDeath: str = isodateAttrs.get('endedtf', '')
                    if isodate or isodateBirth or isodateDeath:
                        if not isodateBirth and not isodateDeath:
                            # all we have is isodate
                            isodateBirthDeath: list[str] = isodate.split('/')
                            if len(isodateBirthDeath) > 0:
                                isodateBirth = isodateBirthDeath[0]
                            if len(isodateBirthDeath) > 1:
                                isodateDeath = isodateBirthDeath[1]

                        if isodateBirth:
                            birthDate: MeiElement = personInfo.appendSubElement(
                                'birthDate',
                                {
                                    'encoding': 'edtf'
                                }
                            )
                            birthDate.text = isodateBirth

                        if isodateDeath:
                            deathDate: MeiElement = personInfo.appendSubElement(
                                'deathDate',
                                {
                                    'encoding': 'edtf'
                                }
                            )
                            deathDate.text = isodateDeath

                if composerBirthPlace is not None:
                    birthPlace: MeiElement = personInfo.appendSubElement('birthPlace')
                    birthPlace.text = composerBirthPlace.meiValue

                if composerDeathPlace is not None:
                    deathPlace: MeiElement = personInfo.appendSubElement('deathPlace')
                    deathPlace.text = composerDeathPlace.meiValue

                if composerNationality is not None:
                    nationality: MeiElement = personInfo.appendSubElement('nationality')
                    nationality.text = composerNationality.meiValue

        return output

    @staticmethod
    def getBestName(
        mmItems: list[MeiMetadataItem],
        requiredLanguage: str = ''
    ) -> MeiMetadataItem | None:
        # If requiredLanguage is set, return the first item with that language,
        # otherwise return the first item that is untranslated.
        # If nothing is found that has the right language/is untranslated,
        # just return the first item (or None, if mmItems is empty).
        bestName: MeiMetadataItem | None = None
        for mmItem in mmItems:
            if not isinstance(mmItem.value, m21.metadata.Text):
                continue

            if requiredLanguage:
                if (mmItem.value.language
                        and mmItem.value.language.lower() == requiredLanguage.lower()):
                    bestName = mmItem
                    break
            else:
                if mmItem.value.isTranslated is not True:
                    bestName = mmItem
                    break

        if bestName is None and mmItems:
            bestName = mmItems[0]
        return bestName

    def makeSimpleTitleElement(self) -> MeiElement:
        # first untranslated OTL (or just first OTL, if all are translated)
        # plus first OMD in that same language goes in the <title> element
        # (no titlePart).
        # If there are no OTLs/OMDs, empty <title/> is returned
        # Note: no @analog, the individual titles will have @analog elsewhere.
        titles: list[MeiMetadataItem] = self.contents.get('OTL', [])
        movementNames: list[MeiMetadataItem] = self.contents.get('OMD', [])
        titleElement = MeiElement('title')
        firstLang: str = ''
        bestTitle: MeiMetadataItem | None = self.getBestName(titles)
        if bestTitle is not None and bestTitle.value.language:
            firstLang = bestTitle.value.language
        bestMovementName: MeiMetadataItem | None = self.getBestName(movementNames, firstLang)
        if (bestTitle is None
                and bestMovementName is not None
                and bestMovementName.value.language):
            firstLang = bestMovementName.value.language.lower()

        if bestTitle is None and bestMovementName is None:
            return titleElement

        if firstLang:
            titleElement.attrib['xml:lang'] = firstLang

        if bestTitle and bestMovementName and bestTitle.meiValue != bestMovementName.meiValue:
            titleElement.text = bestTitle.meiValue + ', ' + bestMovementName.meiValue
        elif bestTitle:
            titleElement.text = bestTitle.meiValue
        elif bestMovementName:
            titleElement.text = bestMovementName.meiValue
        return titleElement

    def makeTitleElements(self) -> list[MeiElement]:
        mainTitles: list[MeiMetadataItem] = self.contents.get('OTL', [])
        alternativeTitles: list[MeiMetadataItem] = self.contents.get('OTA', [])
        popularTitles: list[MeiMetadataItem] = self.contents.get('OTP', [])
        plainNumbers: list[MeiMetadataItem] = self.contents.get('ONM', [])
        movementNumbers: list[MeiMetadataItem] = self.contents.get('OMV', [])
        movementNames: list[MeiMetadataItem] = self.contents.get('OMD', [])
        opusNumbers: list[MeiMetadataItem] = self.contents.get('OPS', [])
        actNumbers: list[MeiMetadataItem] = self.contents.get('OAC', [])
        sceneNumbers: list[MeiMetadataItem] = self.contents.get('OSC', [])

        untranslatedTitleElement = MeiElement('title')
        translatedTitleElement = MeiElement('title')
        alternativeTitleElements: list[MeiElement] = []
        popularTitleElements: list[MeiElement] = []

        # First all the main titles (OTL).
        titlePart: MeiElement
        for mainTitle in mainTitles:
            lang: str = ''
            if t.TYPE_CHECKING:
                assert isinstance(mainTitle.value, m21.metadata.Text)
            isTranslated = mainTitle.value.isTranslated is True
            if mainTitle.value.language:
                lang = mainTitle.value.language.lower()

            attrib = {}
            if isTranslated:
                attrib['type'] = 'translated'
            else:
                attrib['type'] = 'main'
            attrib['analog'] = 'humdrum:OTL'
            if lang:
                attrib['xml:lang'] = lang

            if isTranslated:
                titlePart = translatedTitleElement.appendSubElement('titlePart', attrib)
            else:
                titlePart = untranslatedTitleElement.appendSubElement('titlePart', attrib)
            titlePart.text = mainTitle.meiValue

        # Then any movement name(s) (OMD).
        for movementName in movementNames:
            lang = ''
            if t.TYPE_CHECKING:
                assert isinstance(movementName.value, m21.metadata.Text)
            isTranslated = movementName.value.isTranslated is True
            if movementName.value.language:
                lang = movementName.value.language.lower()

            attrib = {'type': 'movementName', 'analog': 'humdrum:OMD'}
            if lang:
                attrib['xml:lang'] = lang

            if isTranslated:
                titlePart = translatedTitleElement.appendSubElement('titlePart', attrib)
            else:
                titlePart = untranslatedTitleElement.appendSubElement('titlePart', attrib)
            titlePart.text = movementName.meiValue

        # Then any number(s) (ONM).
        for plainNumber in plainNumbers:
            lang = ''
            if t.TYPE_CHECKING:
                assert isinstance(plainNumber.value, m21.metadata.Text)
            isTranslated = plainNumber.value.isTranslated is True
            if plainNumber.value.language:
                lang = plainNumber.value.language.lower()

            attrib = {'type': 'number', 'analog': 'humdrum:ONM'}
            if lang:
                attrib['xml:lang'] = lang

            if isTranslated:
                titlePart = translatedTitleElement.appendSubElement('titlePart', attrib)
            else:
                titlePart = untranslatedTitleElement.appendSubElement('titlePart', attrib)
            titlePart.text = plainNumber.meiValue

        # Then any movement number(s) (OMV).
        for movementNumber in movementNumbers:
            lang = ''
            if t.TYPE_CHECKING:
                assert isinstance(movementNumber.value, m21.metadata.Text)
            isTranslated = movementNumber.value.isTranslated is True
            if movementNumber.value.language:
                lang = movementNumber.value.language.lower()

            attrib = {'type': 'movementNumber', 'analog': 'humdrum:OMV'}
            if lang:
                attrib['xml:lang'] = lang

            if isTranslated:
                titlePart = translatedTitleElement.appendSubElement('titlePart', attrib)
            else:
                titlePart = untranslatedTitleElement.appendSubElement('titlePart', attrib)
            titlePart.text = movementNumber.meiValue

        # Then any opus number(s) (OPS).
        for opusNumber in opusNumbers:
            lang = ''
            if t.TYPE_CHECKING:
                assert isinstance(opusNumber.value, m21.metadata.Text)
            isTranslated = opusNumber.value.isTranslated is True
            if opusNumber.value.language:
                lang = opusNumber.value.language.lower()

            attrib = {'type': 'opusNumber', 'analog': 'humdrum:OPS'}
            if lang:
                attrib['xml:lang'] = lang

            if isTranslated:
                titlePart = translatedTitleElement.appendSubElement('titlePart', attrib)
            else:
                titlePart = untranslatedTitleElement.appendSubElement('titlePart', attrib)
            titlePart.text = opusNumber.meiValue

        # Then any act number(s) (OAC).
        for actNumber in actNumbers:
            lang = ''
            if t.TYPE_CHECKING:
                assert isinstance(actNumber.value, m21.metadata.Text)
            isTranslated = actNumber.value.isTranslated is True
            if actNumber.value.language:
                lang = actNumber.value.language.lower()

            attrib = {'type': 'actNumber', 'analog': 'humdrum:OAC'}
            if lang:
                attrib['xml:lang'] = lang

            if isTranslated:
                titlePart = translatedTitleElement.appendSubElement('titlePart', attrib)
            else:
                titlePart = untranslatedTitleElement.appendSubElement('titlePart', attrib)
            titlePart.text = actNumber.meiValue

        # Then any scene number(s) (OSC).
        for sceneNumber in sceneNumbers:
            lang = ''
            if t.TYPE_CHECKING:
                assert isinstance(sceneNumber.value, m21.metadata.Text)
            isTranslated = sceneNumber.value.isTranslated is True
            if sceneNumber.value.language:
                lang = sceneNumber.value.language.lower()

            attrib = {'type': 'sceneNumber', 'analog': 'humdrum:OSC'}
            if lang:
                attrib['xml:lang'] = lang

            if isTranslated:
                titlePart = translatedTitleElement.appendSubElement('titlePart', attrib)
            else:
                titlePart = untranslatedTitleElement.appendSubElement('titlePart', attrib)
            titlePart.text = sceneNumber.meiValue

        # Separately, any alternative titles (OTA) (no titleParts)
        for alternativeTitle in alternativeTitles:
            lang = ''
            if t.TYPE_CHECKING:
                assert isinstance(alternativeTitle.value, m21.metadata.Text)
            isTranslated = alternativeTitle.value.isTranslated is True
            if alternativeTitle.value.language:
                lang = alternativeTitle.value.language.lower()

            attrib = {'type': 'alternative', 'analog': 'humdrum:OTA'}
            if lang:
                attrib['xml:lang'] = lang

            alternativeTitleEl = MeiElement('title', attrib)
            alternativeTitleEl.text = alternativeTitle.meiValue
            alternativeTitleElements.append(alternativeTitleEl)

        # Separately, any popular titles (OTP) (no titleParts)
        for popularTitle in popularTitles:
            lang = ''
            if t.TYPE_CHECKING:
                assert isinstance(popularTitle.value, m21.metadata.Text)
            isTranslated = popularTitle.value.isTranslated is True
            if popularTitle.value.language:
                lang = popularTitle.value.language.lower()

            attrib = {'type': 'popular', 'analog': 'humdrum:OTP'}
            if lang:
                attrib['xml:lang'] = lang

            popularTitleEl = MeiElement('title', attrib)
            popularTitleEl.text = popularTitle.meiValue
            popularTitleElements.append(popularTitleEl)

        # roll them all up into a list
        titleElements: list[MeiElement] = []
        if not untranslatedTitleElement.isEmpty():
            untranslatedTitleElement.attrib['type'] = 'uniform'
            titleElements.append(untranslatedTitleElement)
        if not translatedTitleElement.isEmpty():
            translatedTitleElement.attrib['type'] = 'translated'
            titleElements.append(translatedTitleElement)

        if alternativeTitleElements:
            titleElements.extend(alternativeTitleElements)
        if popularTitleElements:
            titleElements.extend(popularTitleElements)

        return titleElements

    def makeEncodingDescElement(self) -> MeiElement | None:
        encodingNotes: list[MeiMetadataItem] = self.contents.get('RNB', [])
        encodingWarnings: list[MeiMetadataItem] = self.contents.get('RWB', [])
        softwares: list[MeiMetadataItem] = self.contents.get('software', [])

        converter21AlreadyThere: bool = False
        for software in softwares:
            if software.meiValue == SharedConstants._CONVERTER21_NAME:
                version = software.meiOtherAttribs.get('version', '')
                if version == SharedConstants._CONVERTER21_VERSION:
                    converter21AlreadyThere = True

        if (not encodingNotes
                and not encodingWarnings
                and not softwares
                and converter21AlreadyThere):
            return None

        encodingDesc: MeiElement = MeiElement('encodingDesc')

        if softwares or not converter21AlreadyThere:
            appInfo: MeiElement = encodingDesc.appendSubElement('appInfo')

            # add converter21 if it wasn't already there
            if not converter21AlreadyThere:
                application: MeiElement = appInfo.appendSubElement(
                    'application',
                    {
                        'version': SharedConstants._CONVERTER21_VERSION
                    }
                )
                name: MeiElement = application.appendSubElement('name')
                name.text = SharedConstants._CONVERTER21_NAME

            for software in softwares:
                application = appInfo.appendSubElement(
                    'application',
                    software.meiOtherAttribs
                )
                name = application.appendSubElement('name')
                name.text = software.meiValue

        if encodingNotes or encodingWarnings:
            editorialDecl: MeiElement = encodingDesc.appendSubElement('editorialDecl')
            p: MeiElement = editorialDecl.appendSubElement('p')

            language: str | None
            allTheSameLanguage: bool
            line: MeiElement
            if encodingNotes:
                language, allTheSameLanguage = self.getTextListLanguage(encodingNotes)
                lineGroup: MeiElement = p.appendSubElement('lg')
                if allTheSameLanguage and language:
                    lineGroup.attrib['xml:lang'] = language
                for note in encodingNotes:
                    # <l> does not take @analog, so use @type instead (says Perry)
                    line = lineGroup.appendSubElement('l', {'type': 'humdrum:RNB'})
                    line.text = note.meiValue
                    if note.value.language and not allTheSameLanguage:
                        line.attrib['xml:lang'] = note.value.language.lower()

            if encodingWarnings:
                language, allTheSameLanguage = self.getTextListLanguage(encodingWarnings)
                lineGroup = p.appendSubElement('lg')
                if allTheSameLanguage and language:
                    lineGroup.attrib['xml:lang'] = language
                for warning in encodingWarnings:
                    # <l> does not take @analog, so use @type instead (says Perry)
                    line = lineGroup.appendSubElement('l', {'type': 'humdrum:RWB'})
                    line.text = warning.meiValue
                    if warning.value.language and not allTheSameLanguage:
                        line.attrib['xml:lang'] = warning.value.language.lower()

        return encodingDesc

    @staticmethod
    def getTextListLanguage(textItems: list[MeiMetadataItem]) -> tuple[str | None, bool]:
        # returns tuple(theLanguage: str | None, allTheSameLanguage: bool)
        theLanguage: str | None = None
        allTheSameLanguage: bool = True
        for textItem in textItems:
            if t.TYPE_CHECKING:
                assert isinstance(textItem.value, m21.metadata.Text)
            if theLanguage is None and textItem.value.language is not None:
                theLanguage = textItem.value.language.lower()
                continue
            if theLanguage is not None and textItem.value.language is not None:
                if theLanguage != textItem.value.language.lower():
                    allTheSameLanguage = False
                    break

        return theLanguage, allTheSameLanguage

    def makeWorkListElement(self) -> MeiElement | None:
        # the main (encoded) work
        catalogNumbers: list[MeiMetadataItem] = self.contents.get('SCA', [])
        catalogAbbrevNumbers: list[MeiMetadataItem] = self.contents.get('SCT', [])
        opusNumbers: list[MeiMetadataItem] = self.contents.get('OPS', [])
        creationDates: list[MeiMetadataItem] = self.contents.get('ODT', [])
        creationCountries: list[MeiMetadataItem] = self.contents.get('OCY', [])
        creationSettlements: list[MeiMetadataItem] = self.contents.get('OPC', [])
        creationRegions: list[MeiMetadataItem] = self.contents.get('ARE', [])
        creationLatLongs: list[MeiMetadataItem] = self.contents.get('ARL', [])
        lyricists: list[MeiMetadataItem] = self.contents.get('LYR', [])
        librettists: list[MeiMetadataItem] = self.contents.get('LIB', [])
        dedicatees: list[MeiMetadataItem] = self.contents.get('ODE', [])
        funders: list[MeiMetadataItem] = self.contents.get('OCO', [])
        languages: list[MeiMetadataItem] = self.contents.get('TXO', [])
        histories: list[MeiMetadataItem] = self.contents.get('HAO', [])
        instrumentLists: list[MeiMetadataItem] = self.contents.get('AIN', [])
        forms: list[MeiMetadataItem] = self.contents.get('AFR', [])
        genres: list[MeiMetadataItem] = self.contents.get('AGN', [])
        modes: list[MeiMetadataItem] = self.contents.get('AMD', [])
        meters: list[MeiMetadataItem] = self.contents.get('AMT', [])
        styles: list[MeiMetadataItem] = self.contents.get('AST', [])
        firstPerformanceDates: list[MeiMetadataItem] = self.contents.get('MPD', [])
        performanceDates: list[MeiMetadataItem] = self.contents.get('MDT', [])
        performanceDates.extend(self.contents.get('MRD', []))
        performanceLocations: list[MeiMetadataItem] = self.contents.get('MLC', [])

        # related works
        parentWorkTitles: list[MeiMetadataItem] = self.contents.get('OPR', [])
        groupWorkTitles: list[MeiMetadataItem] = self.contents.get('GTL', [])
        associatedWorkTitles: list[MeiMetadataItem] = self.contents.get('GAW', [])
        # GCO and ACO have the same definition: "Collection designation, such
        # as Norton Scores, Smithsonian Collection, etc."
        collectionWorkTitles: list[MeiMetadataItem] = self.contents.get('GCO', [])
        collectionWorkTitles.extend(self.contents.get('ACO', []))

        parentWorkXmlId: str = ''
        groupWorkXmlId: str = ''
        associatedWorkXmlId: str = ''
        collectionWorkXmlId: str = ''

        workList: MeiElement | None = None
        workNumber: int = 0

        # the parent work
        if parentWorkTitles:
            if workList is None:
                workList = MeiElement('workList')

            parentWorkXmlId = f'work{workNumber}_parent'
            parentWork = workList.appendSubElement(
                'work',
                {
                    'xml:id': parentWorkXmlId,
                    'type': 'parent'
                }
            )
            workNumber += 1

            for parentWorkTitle in parentWorkTitles:
                titleElement = parentWork.appendSubElement(
                    'title',
                    {
                        'analog': 'humdrum:OPR'
                    }
                )
                titleElement.text = parentWorkTitle.meiValue

        # the group work
        if groupWorkTitles:
            if workList is None:
                workList = MeiElement('workList')

            groupWorkXmlId = f'work{workNumber}_group'
            groupWork = workList.appendSubElement(
                'work',
                {
                    'xml:id': groupWorkXmlId,
                    'type': 'group'
                }
            )
            workNumber += 1

            for groupWorkTitle in groupWorkTitles:
                titleElement = groupWork.appendSubElement(
                    'title',
                    {
                        'analog': 'humdrum:GTL'
                    }
                )
                titleElement.text = groupWorkTitle.meiValue

        # the associated work
        if associatedWorkTitles:
            if workList is None:
                workList = MeiElement('workList')

            associatedWorkXmlId = f'work{workNumber}_associated'
            associatedWork = workList.appendSubElement(
                'work',
                {
                    'xml:id': associatedWorkXmlId,
                    'type': 'associated'
                }
            )
            workNumber += 1

            for associatedWorkTitle in associatedWorkTitles:
                titleElement = associatedWork.appendSubElement(
                    'title',
                    {
                        'analog': 'humdrum:GAW'
                    }
                )
                titleElement.text = associatedWorkTitle.meiValue

        # the collection work
        if collectionWorkTitles:
            if workList is None:
                workList = MeiElement('workList')

            collectionWorkXmlId = f'work{workNumber}_collection'
            collectionWork = workList.appendSubElement(
                'work',
                {
                    'xml:id': collectionWorkXmlId,
                    'type': 'collection'
                }
            )
            workNumber += 1

            for collectionWorkTitle in collectionWorkTitles:
                titleElement = collectionWork.appendSubElement(
                    'title',
                    {
                        'analog': 'humdrum:GCO'
                    }
                )
                titleElement.text = collectionWorkTitle.meiValue

        titleElements: list[MeiElement] = self.makeTitleElements()
        composerElements: list[MeiElement] = self.makeComposerElements()

        # the main (encoded) work
        if (catalogNumbers
                or catalogAbbrevNumbers
                or opusNumbers
                or titleElements
                or creationDates
                or creationCountries
                or creationSettlements
                or creationRegions
                or creationLatLongs
                or composerElements
                or lyricists
                or librettists
                or dedicatees
                or funders
                or languages
                or histories
                or instrumentLists
                or forms
                or genres
                or modes
                or meters
                or styles
                or firstPerformanceDates
                or performanceDates
                or performanceLocations):
            if workList is None:
                workList = MeiElement('workList')

            self.mainWorkXmlId = f'work{workNumber}_encoded'
            workNumber += 1

            theWork = workList.appendSubElement(
                'work',
                {
                    'xml:id': self.mainWorkXmlId,
                    'type': 'encoded'
                }
            )

            # <identifier>
            for catalogNumber in catalogNumbers:
                identifierElement = theWork.appendSubElement(
                    'identifier',
                    {
                        'analog': 'humdrum:SCA'
                    }
                )
                identifierElement.text = catalogNumber.meiValue

            for catalogAbbrevNumber in catalogAbbrevNumbers:
                identifierElement = theWork.appendSubElement(
                    'identifier',
                    {
                        'analog': 'humdrum:SCT'
                    }
                )
                identifierElement.text = catalogAbbrevNumber.meiValue

            for opusNumber in opusNumbers:
                identifierElement = theWork.appendSubElement(
                    'identifier',
                    {
                        'analog': 'humdrum:OPS'
                    }
                )
                identifierElement.text = opusNumber.meiValue

            # all <title>s
            theWork.subElements.extend(titleElements)

            # all <composer>s
            theWork.subElements.extend(composerElements)

            # <lyricist>
            for lyricist in lyricists:
                lyricistElement: MeiElement = theWork.appendSubElement('lyricist')
                persName = lyricistElement.appendSubElement(
                    'persName',
                    {
                        'analog': 'humdrum:LYR'
                    }
                )
                persName.text = lyricist.meiValue

            # <librettist>
            for librettist in librettists:
                librettistElement: MeiElement = theWork.appendSubElement('librettist')
                persName = librettistElement.appendSubElement(
                    'persName',
                    {
                        'analog': 'humdrum:LIB'
                    }
                )
                persName.text = librettist.meiValue

            # <funder>
            for funder in funders:
                funderElement: MeiElement = theWork.appendSubElement('funder')
                persName = funderElement.appendSubElement(
                    'name',
                    {
                        'analog': 'humdrum:OCO'
                    }
                )
                persName.text = funder.meiValue

            # <creation>
            if (creationDates
                    or creationCountries
                    or creationSettlements
                    or creationRegions
                    or creationLatLongs
                    or dedicatees):
                creationElement: MeiElement = theWork.appendSubElement('creation')

                for creationDate in creationDates:
                    dateElement: MeiElement = creationElement.appendSubElement(
                        'date',
                        {
                            'analog': 'humdrum:ODT',
                        }
                    )
                    dateElement.fillInIsodate(creationDate.value)
                    dateElement.text = creationDate.meiValue

                for creationCountry in creationCountries:
                    countryElement: MeiElement = creationElement.appendSubElement(
                        'country',
                        {
                            'analog': 'humdrum:OCY'
                        }
                    )
                    countryElement.text = creationCountry.meiValue

                for creationSettlement in creationSettlements:
                    settlementElement: MeiElement = creationElement.appendSubElement(
                        'settlement',
                        {
                            'analog': 'humdrum:OPC'
                        }
                    )
                    settlementElement.text = creationSettlement.meiValue

                for creationRegion in creationRegions:
                    regionElement: MeiElement = creationElement.appendSubElement(
                        'geogName',
                        {
                            'analog': 'humdrum:ARE'
                        }
                    )
                    regionElement.text = creationRegion.meiValue

                for creationLatLong in creationLatLongs:
                    regionElement = creationElement.appendSubElement(
                        'geogName',
                        {
                            'type': 'coordinates',
                            'analog': 'humdrum:ARL'
                        }
                    )
                    regionElement.text = creationLatLong.meiValue

                for dedicatee in dedicatees:
                    contributorElement = creationElement.appendSubElement(
                        'dedicatee',
                        {
                            'analog': 'humdrum:ODE'
                        }
                    )
                    contributorElement.text = dedicatee.meiValue

            # <history>
            if histories:
                allTheSameLanguage: bool
                theLanguage: str | None
                theLanguage, allTheSameLanguage = MeiMetadata.getTextListLanguage(histories)
                historyElement: MeiElement = theWork.appendSubElement('history')
                attrib: dict[str, str] = {}
                if allTheSameLanguage and theLanguage:
                    attrib['xml:lang'] = theLanguage
                lgElement: MeiElement = historyElement.appendSubElement('lg', attrib)

                for history in histories:
                    if t.TYPE_CHECKING:
                        assert isinstance(history.value, m21.metadata.Text)
                    attrib = {'type': 'humdrum:HAO'}
                    if history.value.language and not allTheSameLanguage:
                        attrib['xml:lang'] = history.value.language.lower()
                    # <l> can't take @analog, so use @type (says Perry)
                    lElement: MeiElement = lgElement.appendSubElement('l', attrib)
                    lElement.text = history.meiValue

            # <langUsage>
            if languages:
                langUsageElement: MeiElement = theWork.appendSubElement('langUsage')
                for lang in languages:
                    languageElement: MeiElement = langUsageElement.appendSubElement(
                        'language',
                        {
                            'analog': 'humdrum:TXO'
                        }
                    )
                    languageElement.text = lang.meiValue

            # TODO: <perfMedium><perfResList>
#             if instrumentLists:
#                 perfMediumElement: MeiElement = theWork.appendSubElement('perfMedium')
#                 if len(instrumentLists) == 1:
#                     perfResListElement: MeiElement = perfMediumElement.appendSubElement(
#                         'perfResList'
#                     )
#                     for instrument in instrumentLists[0].split(' '):
#                         perfResElement: MeiElement = perfResListElement.appendSubElement(
#                             'perfRes'
#                         )
#                         perfResElement.text = oh boy, what about counts
#                     outerPerfResListElement: MeiElement = perfMediumElement.appendSubElement(
#                         'perfResList'
#                     )

            # <classification>
            if forms or genres or modes or meters or styles:
                classificationElement: MeiElement = theWork.appendSubElement('classification')
                termListElement: MeiElement = classificationElement.appendSubElement('termList')
                for form in forms:
                    termElement: MeiElement = termListElement.appendSubElement(
                        'term',
                        {
                            'label': 'form',
                            'analog': 'humdrum:AFR'
                        }
                    )
                    termElement.text = form.meiValue

                for genre in genres:
                    termElement = termListElement.appendSubElement(
                        'term',
                        {
                            'label': 'genre',
                            'analog': 'humdrum:AGN'
                        }
                    )
                    termElement.text = genre.meiValue

                for mode in modes:
                    termElement = termListElement.appendSubElement(
                        'term',
                        {
                            'label': 'mode',
                            'analog': 'humdrum:AMD'
                        }
                    )
                    termElement.text = mode.meiValue

                for meter in meters:
                    termElement = termListElement.appendSubElement(
                        'term',
                        {
                            'label': 'meter',
                            'analog': 'humdrum:AMT'
                        }
                    )
                    termElement.text = meter.meiValue

                for style in styles:
                    termElement = termListElement.appendSubElement(
                        'term',
                        {
                            'label': 'style',
                            'analog': 'humdrum:AST'
                        }
                    )
                    termElement.text = style.meiValue

            # <expressionList>
            expressionListElement: MeiElement | None = None
            if firstPerformanceDates:
                expressionListElement = theWork.appendSubElement('expressionList')

                expressionElement: MeiElement = expressionListElement.appendSubElement(
                    'expression'
                )
                titleElement = expressionElement.appendSubElement('title')
                titleElement.text = "First performance"
                creationElement = expressionElement.appendSubElement('creation')
                for firstPerformanceDate in firstPerformanceDates:
                    dateElement = creationElement.appendSubElement(
                        'date',
                        {
                            'type': 'firstPerformance',
                            'analog': 'humdrum:MPD'
                        }
                    )
                    dateElement.fillInIsodate(firstPerformanceDate.value)
                    dateElement.text = firstPerformanceDate.meiValue

            if performanceDates:
                if expressionListElement is None:
                    expressionListElement = theWork.appendSubElement('expressionList')

                for i, performanceDate in enumerate(performanceDates):
                    expressionElement = expressionListElement.appendSubElement(
                        'expression'
                    )
                    titleElement = expressionElement.appendSubElement('title')
                    titleElement.text = 'Performance'
                    creationElement = expressionElement.appendSubElement('creation')

                    dateElement = creationElement.appendSubElement(
                        'date',
                        {
                            'type': 'performance',
                            'analog': 'humdrum:MDT'
                        }
                    )
                    dateElement.fillInIsodate(performanceDate.value)
                    dateElement.text = performanceDate.meiValue

                    if i < len(performanceLocations):
                        performanceLocation = performanceLocations[i]
                        geogNameElement = creationElement.appendSubElement(
                            'geogName',
                            {
                                'role': 'performanceLocation',
                                'analog': 'humdrum:MLC'
                            }
                        )
                        geogNameElement.text = performanceLocation.meiValue

            # <relationList> (relations to the other works)
            if parentWorkXmlId or groupWorkXmlId or associatedWorkXmlId or collectionWorkXmlId:
                relationList = theWork.appendSubElement('relationList')
                if parentWorkXmlId:
                    relationList.appendSubElement(
                        'relation',
                        {
                            'rel': 'isPartOf',
                            'type': 'isChildOfParent',
                            'target': f'#{parentWorkXmlId}'
                        }
                    )
                if groupWorkXmlId:
                    relationList.appendSubElement(
                        'relation',
                        {
                            'rel': 'isPartOf',
                            'type': 'isMemberOfGroup',
                            'target': f'#{groupWorkXmlId}'
                        }
                    )
                if associatedWorkXmlId:
                    relationList.appendSubElement(
                        'relation',
                        {
                            'rel': 'isVersionOf',
                            'type': 'isAssociatedWith',
                            'target': f'#{associatedWorkXmlId}'
                        }
                    )
                if collectionWorkXmlId:
                    relationList.appendSubElement(
                        'relation',
                        {
                            'rel': 'isPartOf',
                            'type': 'isMemberOfCollection',
                            'target': f'#{collectionWorkXmlId}'
                        }
                    )

            extMeta: MeiElement | None = self.makeExtMetaElementForWork()
            if extMeta is not None:
                theWork.subElements.append(extMeta)

        return workList

    def makeManifestationListElement(self) -> MeiElement | None:
        return None

    def makeExtMetaElementForMeiHead(self) -> MeiElement | None:
        return None

    def makeExtMetaElementForWork(self) -> MeiElement | None:
        if not self.madsCollection:
            return None

        extMeta: MeiElement = MeiElement('extMeta')
        extMeta.subElements.append(self.madsCollection)
        self.madsCollection = None

        return extMeta
