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
from xml.etree.ElementTree import TreeBuilder  # , Element
import typing as t

import music21 as m21

# from converter21.mei import MeiExportError
# from converter21.mei import MeiInternalError
from converter21.mei import MeiElement
from converter21.shared import M21Utilities

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
        if md._isStandardUniqueName(self.key):
            self.uniqueName = self.key
            self.humdrumRefKey = (
                M21Utilities.m21MetadataPropertyUniqueNameToHumdrumReferenceKey.get(self.key, '')
            )
        elif self.key.startswith('humdrum:'):
            hdKey: str = self.key[8:]
            if hdKey in M21Utilities.validHumdrumReferenceKeys:
                self.humdrumRefKey = hdKey

        # self.isCustom is True if we don't have a uniqueName or humdrumRefKey
        self.isCustom: bool = not self.uniqueName and not self.humdrumRefKey

        self.isContributor: bool = md._isContributorUniqueName(self.uniqueName)

        # convert self.value to an appropriate string (no html escaping yet)
        self.meiValue: str = M21Utilities.m21MetadataValueToString(self.value)

class MeiMetadata:
    def __init__(self, m21Metadata: m21.metadata.Metadata) -> None:
        self.m21Metadata: m21.metadata.Metadata = m21Metadata
        # self.contents is structured just like m21Metadata._contents v8 and later,
        # except that the key is the humdrum ref key (if there is one), or the
        # uniqueName (if there is one), or the custom key if that's all there is.
        self.contents: dict[str, list[MeiMetadataItem]] = {}
        for m21Item in m21Metadata.all(returnPrimitives=True, returnSorted=False):
            meiItem = MeiMetadataItem(m21Item, m21Metadata)
            key: str = meiItem.humdrumRefKey or meiItem.uniqueName or meiItem.key
            currList: list[MeiMetadataItem] | None = self.contents.get(key, None)
            if currList is None:
                self.contents[key] = [meiItem]
            else:
                currList.append(meiItem)

        # Saved off state during makeRootElement (e.g. MeiElement trees that
        # may need to be re-used).

        # These are the simplified title and composers, that are used in
        # <fileDesc> and <source>.  The main <work> will have ALL the details.
        self.simpleTitleElement: MeiElement | None = None
        self.simpleComposerElements: list[MeiElement] = []

    def makeRootElement(self, tb: TreeBuilder):
        meiHead: MeiElement = MeiElement('meiHead')
        fileDesc: MeiElement = self.makeFileDescElement()
        encodingDesc: MeiElement | None = self.makeEncodingDescElement()
        workList: MeiElement | None = self.makeWorkListElement()
        manifestationList: MeiElement | None = self.makeManifestationListElement()
        extMeta: MeiElement | None = self.makeExtMetaElement()

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
        # metadata items we find.  One for the digital source, one for the published
        # printed source, one for a recorded source album (with maybe one for the
        # recorded source album track), and one for an unpublished manuscript source.
        # if sourceDesc ends up empty, we will not add it, so create separately and
        # only append if not empty.
        sourceDesc: MeiElement = MeiElement('sourceDesc')

        digitalSource: MeiElement | None = self.makeDigitalSource()
        if digitalSource is not None:
            sourceDesc.subElements.append(digitalSource)

        publishedSource: MeiElement | None = self.makePublishedSource()
        if publishedSource is not None:
            sourceDesc.subElements.append(publishedSource)

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
        if not self.anyExist('EED', 'ENC', 'EEV', 'EFL', 'YEP', 'YER', 'END', 'YEM', 'YEN'):
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
        copyrightStatements: list[MeiMetadataItem] = self.contents.get('YEM', [])
        copyrightCountries: list[MeiMetadataItem] = self.contents.get('YEN', [])
        textLanguages: list[MeiMetadataItem] = self.contents.get('TXL', [])

        for editor in editors:
            editorEl: MeiElement = bibl.appendSubElement(
                'editor',
                {
                    'analog': 'humdrum:EED'
                }
            )
            editorEl.text = editor.meiValue

        for encoder in encoders:
            encoderEl: MeiElement = bibl.appendSubElement(
                'editor',
                {
                    'type': 'encoder',
                    'analog': 'humdrum:ENC'
                }
            )
            encoderEl.text = encoder.meiValue

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

        if copyrightStatements or copyrightCountries:
            availability: MeiElement = bibl.appendSubElement('availability')
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

    def makePublishedSource(self) -> MeiElement | None:
        if not self.anyExist('LAR', 'PED', 'LOR', 'TRN', 'OCL', 'OVM', 'PTL',
                'PPR', 'PDT', 'PPP', 'PC#'):
            return None

        source: MeiElement = MeiElement('source', {'type': 'published'})
        bibl: MeiElement = source.appendSubElement('bibl')
        if self.simpleTitleElement is None:
            self.simpleTitleElement = self.makeSimpleTitleElement()
        bibl.subElements.append(self.simpleTitleElement)
        if not self.simpleComposerElements:
            self.simpleComposerElements = self.makeSimpleComposerElements()
        if self.simpleComposerElements:
            bibl.subElements.extend(self.simpleComposerElements)

        arrangers: list[MeiMetadataItem] = self.contents.get('LAR', [])
        editors: list[MeiMetadataItem] = self.contents.get('YOE', [])
        orchestrators: list[MeiMetadataItem] = self.contents.get('LOR', [])
        translators: list[MeiMetadataItem] = self.contents.get('TRN', [])
        collectors: list[MeiMetadataItem] = self.contents.get('OCL', [])
        volumeNumbers: list[MeiMetadataItem] = self.contents.get('OVM', [])
        volumeNames: list[MeiMetadataItem] = self.contents.get('PTL', [])

        for arranger in arrangers:
            arrangerEl: MeiElement = bibl.appendSubElement(
                'arranger',
                {
                    'analog': 'humdrum:LAR'
                }
            )
            arrangerEl.text = arranger.meiValue

        for editor in editors:
            editorEl: MeiElement = bibl.appendSubElement(
                'editor',
                {
                    'analog': 'humdrum:PED'
                }
            )
            editorEl.text = editor.meiValue

        if orchestrators or translators or collectors:
            respStmt: MeiElement = bibl.appendSubElement('respStmt')

            for orchestrator in orchestrators:
                respEl: MeiElement = respStmt.appendSubElement('resp')
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
                    'persName',
                    {
                        'analog': 'humdrum:OCL'
                    }
                )
                persNameEl.text = collector.meiValue

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
                'MCN', 'RMM', 'RRD', 'RLC', 'RDT', 'MLC'):
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

        for i, albumTitle in enumerate(albumTitles):
            if i < len(trackNumbers):
                analytic: MeiElement = biblStruct.appendSubElement('analytic')
                analytic.appendSubElement('title')
                biblScope = analytic.appendSubElement(
                    'biblScope',
                    {
                        'type': 'trackNumber',
                        'analog': 'humdrum:RT#'
                    }
                )
                biblScope.text = trackNumbers[i].meiValue

            monogr: MeiElement = biblStruct.appendSubElement('monogr')
            albumTitleEl: MeiElement = monogr.appendSubElement(
                'title',
                {
                    'analog': 'humdrum:RTL'
                }
            )
            albumTitleEl.text = albumTitle.meiValue

            if i < len(albumCatalogNumbers):
                albumCatalogNumberEl: MeiElement = monogr.appendSubElement(
                    'identifier',
                    {
                        'type': 'albumCatalogNumber',
                        'analog': 'humdrum:RC#'
                    }
                )
                albumCatalogNumberEl.text = albumCatalogNumbers[i].meiValue

            if (i < len(ensembleNames)
                    or i < len(performerNames)
                    or i < len(suspectedPerformerNames)
                    or i < len(producers)
                    or i < len(conductors)):
                respStmt: MeiElement = monogr.appendSubElement('respStmt')

                if i < len(ensembleNames):
                    ensembleName = ensembleNames[i]
                    respEl: MeiElement = respStmt.appendSubElement('resp')
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
                    performerName = performerNames[i]
                    respEl = respStmt.appendSubElement('resp')
                    respEl.text = 'performer'
                    performerNameEl: MeiElement = monogr.appendSubElement(
                        'persName',
                        {
                            'analog': 'humdrum:MPN'
                        }
                    )
                    performerNameEl.text = performerName.meiValue

                if i < len(suspectedPerformerNames):
                    suspectedPerformerName = suspectedPerformerNames[i]
                    respEl = respStmt.appendSubElement('resp')
                    respEl.text = 'performer'
                    suspectedPerformerNameEl: MeiElement = monogr.appendSubElement(
                        'persName',
                        {
                            'cert': 'medium',
                            'analog': 'humdrum:MPS'
                        }
                    )
                    suspectedPerformerNameEl.text = suspectedPerformerName.meiValue

                if i < len(producers):
                    producer = producers[i]
                    respEl = respStmt.appendSubElement('resp')
                    respEl.text = 'producer'
                    persNameEl: MeiElement = respStmt.appendSubElement(
                        'persName',
                        {
                            'analog': 'humdrum:RNP'
                        }
                    )
                    persNameEl.text = producer.meiValue

                for conductor in conductors:
                    conductor = conductors[i]
                    respEl = respStmt.appendSubElement('resp')
                    respEl.text = 'conductor'
                    persNameEl = respStmt.appendSubElement(
                        'persName',
                        {
                            'analog': 'humdrum:MCN'
                        }
                    )
                    persNameEl.text = conductor.meiValue

        if manufacturers or releaseDates or recordingLocations or recordingDates:
            imprint: MeiElement = monogr.appendSubElement('imprint')

            for manufacturer in manufacturers:
                manufacturerEl: MeiElement = imprint.appendSubElement(
                    'corpName',
                    {
                        'role': 'production/distribution',
                        'analog': 'humdrum:RMM'
                    }
                )
                manufacturerEl.text = manufacturer.meiValue

            for releaseDate in releaseDates:
                releaseDateEl: MeiElement = imprint.appendSubElement(
                    'date',
                    {
                        'type': 'releaseDate',
                        'analog': 'humdrum:RRD'
                    }
                )
                releaseDateEl.fillInIsodate(releaseDate.value)
                releaseDateEl.text = releaseDate.meiValue

            for recordingLocation in recordingLocations:
                recordingLocationEl: MeiElement = imprint.appendSubElement(
                    'geogName',
                    {
                        'role': 'recordingLocation',
                        'analog': 'humdrum:RLC'
                    }
                )
                recordingLocationEl.text = recordingLocation.meiValue

            for recordingDate in recordingDates:
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
                'persName',
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

        for acknowledgment in acknowledgments:
            acknowledgmentEl = bibl.appendSubElement(
                'annot',
                {
                    'type': 'manuscriptAccessAcknowledgment',
                    'analog': 'humdrum:SMA'
                }
            )
            acknowledgmentEl.text = acknowledgment.meiValue

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
        output: list[MeiElement] = []
        composers: list[MeiMetadataItem] = self.contents.get('COM', [])
        attributedComposers: list[MeiMetadataItem] = self.contents.get('COA', [])
        suspectedComposers: list[MeiMetadataItem] = self.contents.get('COS', [])
        composerCorporateNames: list[MeiMetadataItem] = self.contents.get('COC', [])
        composerAliases: list[MeiMetadataItem] = self.contents.get('COL', [])
#         composerDates: list[MeiMetadataItem] = self.contents.get('CDT', [])
#         composerBirthPlaces: list[MeiMetadataItem] = self.contents.get('CBL', [])
#         composerDeathPlaces: list[MeiMetadataItem] = self.contents.get('CDL', [])
#         composerNationalities: list[MeiMetadataItem] = self.contents.get('CNT', [])
        # TODO: Prefer composer birth/death dates from Contributor value.
        # TODO: But first make Humdrum importer put them there.

        for i, composer in enumerate(
                composers + attributedComposers + suspectedComposers):
            # Assume association is done by ordering of the metadata item arrays
            # Currently our Humdrum importer assumes this ordering should match
            # the ordering in the file.
            composerAlias: MeiMetadataItem | None = None
            composerCorporateName: MeiMetadataItem | None = None
#             composerBirthAndDeathDate: MeiMetadataItem | None = None
#             composerBirthPlace: MeiMetadataItem | None = None
#             composerDeathPlace: MeiMetadataItem | None = None
#             composerNationality: MeiMetadataItem | None = None
            if i < len(composerCorporateNames):
                composerCorporateName = composerCorporateNames[i]
            if i < len(composerAliases):
                composerAlias = composerAliases[i]
#             if i < len(composerDates):
#                 composerBirthAndDeathDate = composerDates[i]
#             if i < len(composerBirthPlaces):
#                 composerBirthPlace = composerBirthPlaces[i]
#             if i < len(composerDeathPlaces):
#                 composerDeathPlace = composerDeathPlaces[i]
#             if i < len(composerNationalities):
#                 composerNationality = composerNationalities[i]

            composerElement = MeiElement('composer')
            output.append(composerElement)

            # composer persName ('COM'/'COA'/'COS')
            composerAnalog: str = 'humdrum:COM'
            composerCert: str = ''
            if composer.value.role == 'attributedComposer':
                composerAnalog = 'humdrum:COA'
                composerCert = 'medium'
            elif composer.value.role == 'suspectedComposer':
                composerAnalog = 'humdrum:COS'
                composerCert = 'low'

            if composerCert:
                # We put @cert on <composer>, not on <persName>.
                # The uncertainty is about whether this composer was involved,
                # not about this composer's name.
                composerElement.attrib['cert'] = composerCert

            persNameAttr = {'analog': composerAnalog}
            persNameElement: MeiElement = composerElement.appendSubElement(
                'persName',
                persNameAttr
            )
            persNameElement.text = composer.meiValue

            # composer corporate name ('COC')
            if composerCorporateName is not None:
                persNameElement = composerElement.appendSubElement(
                    'corpName',
                    {
                        'analog': 'humdrum:COC'
                    }
                )
                persNameElement.text = composerCorporateName.meiValue

            # composer alias ('COL')
            if composerAlias is not None:
                persNameElement = composerElement.appendSubElement(
                    'persName',
                    {
                        'type': 'alias',
                        'analog': 'humdrum:COL'
                    }
                )
                persNameElement.text = composerAlias.meiValue

            # composer birth and death dates
#             if composerBirthAndDeathDate is not None:
#                 dateElement: MeiElement = composerElement.appendSubElement(
#                     'date',
#                     {
#                         'type': 'birth/death',
#                         'analog': 'humdrum:CDT',
#                     }
#                 )
#                 dateElement.fillInIsodate(composerBirthAndDeathDate.value)
#                 dateElement.text = composerBirthAndDeathDate.meiValue

            # composer birth place
#             if composerBirthPlace is not None:
#                 geogNameElement: MeiElement = composerElement.appendSubElement(
#                     'geogName',
#                     {
#                         'role': 'birthPlace',
#                         'analog': 'humdrum:CBL'
#                     }
#                 )
#                 geogNameElement.text = composerBirthPlace.meiValue

            # composer death place
#             if composerDeathPlace is not None:
#                 geogNameElement = composerElement.appendSubElement(
#                     'geogName',
#                     {
#                         'role': 'deathPlace',
#                         'analog': 'humdrum:CDL'
#                     }
#                 )
#                 geogNameElement.text = composerDeathPlace.meiValue

            # composer nationality
#             if composerNationality is not None:
#                 geogNameElement = composerElement.appendSubElement(
#                     'geogName',
#                     {
#                         'role': 'nationality',
#                         'analog': 'humdrum:CNT'
#                     }
#                 )
#                 geogNameElement.text = composerNationality.meiValue

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
                if mmItem.value.language.lower() == requiredLanguage.lower():
                    bestName = mmItem
                    break
            else:
                if mmItem.value.isTranslated is not True:
                    bestName = mmItem
                    break

        if bestName is None and mmItems:
            bestName = mmItems[0]
            firstLang = bestName.value.language.lower()
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
        bestTitle: MeiElement | None = self.getBestName(titles)
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

        if bestTitle and bestMovementName:
            titleElement.text = bestTitle.meiValue + ', ' + bestMovementName.meiValue
        elif bestTitle:
            titleElement.text = bestTitle.meiValue
        elif bestMovementName:
            titleElement.text = bestMovementName.meiValue
        return titleElement

    def makeTitleElements(self, firstTitleOnly: bool = False) -> list[MeiElement]:
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
        translatedTitleElement = MeiElement('title', {'type': 'translated'})

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

        # Then any alternative titles (OTA).
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

            if isTranslated:
                titlePart = translatedTitleElement.appendSubElement('titlePart', attrib)
            else:
                titlePart = untranslatedTitleElement.appendSubElement('titlePart', attrib)
            titlePart.text = alternativeTitle.meiValue

        # Then any popular titles (OTP).
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

            if isTranslated:
                titlePart = translatedTitleElement.appendSubElement('titlePart', attrib)
            else:
                titlePart = untranslatedTitleElement.appendSubElement('titlePart', attrib)
            titlePart.text = popularTitle.meiValue

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

        titleElements: list[MeiElement] = []
        if not untranslatedTitleElement.isEmpty():
            titleElements.append(untranslatedTitleElement)
        if not translatedTitleElement.isEmpty():
            titleElements.append(translatedTitleElement)
        return titleElements

    def makeEncodingDescElement(self) -> MeiElement | None:
        encodingNotes: list[MeiMetadataItem] = self.contents.get('RNB', [])
        encodingWarnings: list[MeiMetadataItem] = self.contents.get('RWB', [])
        if not encodingNotes and not encodingWarnings:
            return None

        encodingDesc: MeiElement = MeiElement('encodingDesc')
        editorialDecl: MeiElement = encodingDesc.appendSubElement('editorialDecl')

        if encodingNotes:
            language: str
            allTheSameLanguage: bool
            language, allTheSameLanguage = self.getTextListLanguage(encodingNotes)
            lg: MeiElement = editorialDecl.appendSubElement('lg')
            if allTheSameLanguage and language:
                lg.attrib['xml:lang'] = language
            for note in encodingNotes:
                # <l> does not take @analog, so use @type instead (says Perry)
                l: MeiElement = lg.appendSubElement('l', {'type': 'humdrum:RNB'})
                l.text = note.meiValue
                if note.value.language and not allTheSameLanguage:
                    l.attrib['xml:lang'] = note.text.language.lower()
        if encodingWarnings:
            language: str
            allTheSameLanguage: bool
            language, allTheSameLanguage = self.getTextListLanguage(encodingNotes)
            lg = editorialDecl.appendSubElement('lg')
            if allTheSameLanguage and language:
                lg.attrib['xml:lang'] = language
            for warning in encodingWarnings:
                # <l> does not take @analog, so use @type instead (says Perry)
                l = lg.appendSubElement('l', {'type': 'humdrum:RWB'})
                l.text = warning.meiValue
                if note.value.language and not allTheSameLanguage:
                    l.attrib['xml:lang'] = note.text.language.lower()

        return encodingDesc

    @staticmethod
    def getTextListLanguage(textItems: list[MeiMetadataItem]) -> tuple[str, bool]:
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
        notes: list[MeiMetadataItem] = self.contents.get('ONB', [])
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
        collectionWorkTitles: list[MeiMetadataItem] = self.contents.get('GCO', [])

        parentWorkXmlId: str = ''
        groupWorkXmlId: str = ''
        associatedWorkXmlId: str = ''
        collectionWorkXmlId: str = ''

        workList: MeiElement | None = None
        workNumber: int = 0

        # the parent work
        if parentWorkTitles:
            workList = workList or MeiElement('workList')

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
            workList = workList or MeiElement('workList')

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
            workList = workList or MeiElement('workList')

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
            workList = workList or MeiElement('workList')

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
                or notes
                or forms
                or genres
                or modes
                or meters
                or styles
                or firstPerformanceDates
                or performanceDates
                or performanceLocations):
            workList = workList or MeiElement('workList')

            theWork = workList.appendSubElement(
                'work',
                {
                    'xml:id': f'work{workNumber}_main',
                    'type': 'main'
                }
            )
            workNumber += 1

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
                funderElement: MeiElement = theWork.appendSubElement(
                    'funder',
                    {
                        'analog': 'humdrum:OCO'
                    }
                )
                funderElement.text = funder.meiValue

            # <langUsage>
            if languages:
                langUsageElement: MeiElement = theWork.appendSubElement('langUsage')
                for language in languages:
                    languageElement: MeiElement = langUsageElement.appendSubElement(
                        'language',
                        {
                            'analog': 'humdrum:TXO'
                        }
                    )
                    languageElement.text = language.meiValue

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
                        assert isintance(history.value, m21.metadata.Text)
                    attrib = {'type': 'humdrum:HAO'}
                    if history.value.language and not allTheSameLanguage:
                        attrib['xml:lang'] = history.value.language.lower()
                    # <l> can't take @analog, so use @type (says Perry)
                    lElement: MeiElement = lgElement.appendSubElement('l', attrib)
                    lElement.text = history.meiValue

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

            # <notesStmt>
            if notes:
                notesStmtElement: MeiElement = theWork.appendSubElement('notesStmt')
                for note in notes:
                    annotElement: MeiElement = notesStmtElement.appendSubElement(
                        'annot',
                        {
                            'analog': 'humdrum:ONB'
                        }
                    )
                    if note.value.language:
                        annotElement.attrib['xml:lang'] = note.value.language.lower()
                    annotElement.text = note.meiValue

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
                            'rel': 'host',
                            'plist': f'#{parentWorkXmlId}'
                        }
                    )
                if groupWorkXmlId:
                    relationList.appendSubElement(
                        'relation',
                        {
                            'rel': 'isPartOf',
                            'plist': f'#{groupWorkXmlId}'
                        }
                    )
                if associatedWorkXmlId:
                    relationList.appendSubElement(
                        'relation',
                        {
                            'rel': 'isVersionOf',
                            'plist': f'#{associatedWorkXmlId}'
                        }
                    )
                if collectionWorkXmlId:
                    relationList.appendSubElement(
                        'relation',
                        {
                            'rel': 'isPartOf',
                            'plist': f'#{collectionWorkXmlId}'
                        }
                    )

        return workList

    def makeManifestationListElement(self) -> MeiElement | None:
        return None

    def makeExtMetaElement(self) -> MeiElement | None:
        return None
