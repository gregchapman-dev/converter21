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

        # saved off state during makeRootElement (e.g. MeiElement trees that
        # may need to be re-used)
        self.mainTitleElement: MeiElement | None = None
        self.mainComposerElements: list[MeiElement] = []

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

        # We stash off the main title element because we will reuse it in
        # the workList/work that describes the work we have encoded here.
        self.mainTitleElement = self.makeMainTitleElement()
        if self.mainTitleElement is not None:
            titleStmt.subElements.append(self.mainTitleElement)

        self.mainComposerElements = self.makeMainComposerElements()
        if self.mainComposerElements:
            titleStmt.subElements.extend(self.mainComposerElements)

        # pubStmt describes the MEI file we are writing.  It is, of course,
        # unpublished, so we use <unpub> to say that.  This pubStmt will
        # always be non-empty, so create/append in one step
        pubStmt: MeiElement = fileDesc.appendSubElement('pubStmt')
        unpub: MeiElement = pubStmt.appendSubElement('unpub')
        unpub.text = (
            '''This MEI file was created by converter21's MEI writer, from a music21 score.
                   If it is published, this unpub element should be removed, and the enclosing
                   pubStmt element should be properly filled out.'''
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
            recordedTrackSource: MeiElement | None = self.makeRecordedTrackSource()
            if recordedTrackSource is not None:
                sourceDesc.subElements.append(recordedTrackSource)

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
        if self.mainTitleElement:
            bibl.subElements.append(self.mainTitleElement)
        if self.mainComposerElements:
            bibl.subElements.extend(self.mainComposerElements)

        editors: list[MeiMetadataItem] = self.contents.get('EED', [])
        encoders: list[MeiMetadataItem] = self.contents.get('ENC', [])
        versions: list[MeiMetadataItem] = self.contents.get('EEV', [])
        fileNumbers: list[MeiMetadataItem] = self.contents.get('EFL', [])
        publishers: list[MeiMetadataItem] = self.contents.get('YEP', [])
        releaseDates: list[MeiMetadataItem] = self.contents.get('YER', [])
        encodingDates: list[MeiMetadataItem] = self.contents.get('END', [])
        copyrightStatements: list[MeiMetadataItem] = self.contents.get('YEM', [])
        copyrightCountries: list[MeiMetadataItem] = self.contents.get('YEN', [])

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
                'edition',
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
                releaseDateEl.text = releaseDate.meiValue

            for encodingDate in encodingDates:
                encodingDateEl: MeiElement = imprint.appendSubElement(
                    'date',
                    {
                        'type': 'encodingDate',
                        'analog': 'humdrum:END'
                    }
                )
                encodingDateEl.text = encodingDate.meiValue

        for copyrightStatement in copyrightStatements:
            copyrightStatementEl: MeiElement = bibl.appendSubElement(
                'annot',
                {
                    'type': 'copyrightStatement',
                    'analog': 'humdrum:YEM'
                }
            )
            copyrightStatementEl.text = copyrightStatement.meiValue

        for copyrightCountry in copyrightCountries:
            copyrightCountryEl: MeiElement = bibl.appendSubElement(
                'annot',
                {
                    'type': 'copyrightCountry',
                    'analog': 'humdrum:YEN'
                }
            )
            copyrightCountryEl.text = copyrightCountry.meiValue

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
        if self.mainTitleElement:
            bibl.subElements.append(self.mainTitleElement)
        if self.mainComposerElements:
            bibl.subElements.extend(self.mainComposerElements)

        arrangers: list[MeiMetadataItem] = self.contents.get('LAR', [])
        editors: list[MeiMetadataItem] = self.contents.get('YOE', [])
        orchestrators: list[MeiMetadataItem] = self.contents.get('LOR', [])
        translators: list[MeiMetadataItem] = self.contents.get('TRN', [])
        collectors: list[MeiMetadataItem] = self.contents.get('OCL', [])
        textLanguages: list[MeiMetadataItem] = self.contents.get('TXL', [])
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
                respEl: MeiElement = respStmt.appendSubElement(
                    'resp',
                    {
                        'analog': 'humdrum:LOR'
                    }
                )
                respEl.text = 'orchestrator'
                persNameEl: MeiElement = respStmt.appendSubElement(
                    'persName',
                    {
                        'analog': 'humdrum:LOR'
                    }
                )
                persNameEl.text = orchestrator.meiValue

            for translator in translators:
                respEl = respStmt.appendSubElement(
                    'resp',
                    {
                        'analog': 'humdrum:TRN'
                    }
                )
                respEl.text = 'translator'
                persNameEl = respStmt.appendSubElement(
                    'persName',
                    {
                        'analog': 'humdrum:TRN'
                    }
                )
                persNameEl.text = translator.meiValue

            for collector in collectors:
                respEl = respStmt.appendSubElement(
                    'resp',
                    {
                        'analog': 'humdrum:OCL'
                    }
                )
                respEl.text = 'collector/transcriber'
                persNameEl = respStmt.appendSubElement(
                    'persName',
                    {
                        'analog': 'humdrum:OCL'
                    }
                )
                persNameEl.text = collector.meiValue

        for textLanguage in textLanguages:
            textLanguageEl: MeiElement = bibl.appendSubElement(
                'textLang',
                {
                    'analog': 'humdrum:TXL'
                }
            )
            textLanguageEl.text = textLanguage.meiValue

        for volumeName in volumeNames:
            relatedItem: MeiElement = bibl.appendSubElement(
                'relatedItem',
                {
                    'rel': 'host'
                }
            )
            relBibl: MeiElement = relatedItem.appendSubElement('bibl')
            relBibl.appendSubElement('title')
            biblScope: MeiElement = relBibl.appendSubElement(
                'biblScope',
                {
                    'analog': 'humdrum:PTL'
                }
            )
            biblScope.text = volumeName.meiValue

        for volumeNumber in volumeNumbers:
            relatedItem = bibl.appendSubElement(
                'relatedItem',
                {
                    'rel': 'host'
                }
            )
            relBibl = relatedItem.appendSubElement('bibl')
            relBibl.appendSubElement('title')
            biblScope = relBibl.appendSubElement(
                'biblScope',
                {
                    'analog': 'humdrum:OVM'
                }
            )
            biblScope.text = volumeNumber.meiValue

        if bibl.isEmpty():
            return None
        return source

    def makeRecordedSource(self) -> MeiElement | None:
        if not self.anyExist('RTL', 'RC#', 'MGN', 'MPN', 'MPS', 'RNP',
                'MCN', 'RMM', 'RRD', 'RLC', 'RDT', 'MLC'):
            return None

        source: MeiElement = MeiElement('source', {'type': 'recordedAlbum'})
        bibl: MeiElement = source.appendSubElement('bibl', {'xml:id': 'album1'})

        albumTitles: list[MeiMetadataItem] = self.contents.get('RTL', [])
        albumCatalogNumbers: list[MeiMetadataItem] = self.contents.get('RC#', [])
        ensembleNames: list[MeiMetadataItem] = self.contents.get('MGN', [])
        performerNames: list[MeiMetadataItem] = self.contents.get('MPN', [])
        suspectedPerformerNames: list[MeiMetadataItem] = self.contents.get('MPS', [])
        producers: list[MeiMetadataItem] = self.contents.get('RNP', [])
        conductors: list[MeiMetadataItem] = self.contents.get('MCN', [])
        manufacturers: list[MeiMetadataItem] = self.contents.get('RMM', [])
        releaseDates: list[MeiMetadataItem] = self.contents.get('RRD', [])
        recordingPlaces: list[MeiMetadataItem] = self.contents.get('RLC', [])
        recordingDates: list[MeiMetadataItem] = self.contents.get('RDT', [])
        performanceLocations: list[MeiMetadataItem] = self.contents.get('MLC', [])

        for albumTitle in albumTitles:
            albumTitleEl: MeiElement = bibl.appendSubElement(
                'title',
                {
                    'analog': 'humdrum:RTL'
                }
            )
            albumTitleEl.text = albumTitle.meiValue

        for albumCatalogNumber in albumCatalogNumbers:
            albumCatalogNumberEl: MeiElement = bibl.appendSubElement(
                'identifier',
                {
                    'type': 'albumCatalogNumber',
                    'analog': 'humdrum:RC#'
                }
            )
            albumCatalogNumberEl.text = albumCatalogNumber.meiValue

        for ensembleName in ensembleNames:
            ensembleNameEl: MeiElement = bibl.appendSubElement(
                'corpName',
                {
                    'type': 'ensembleName',
                    'role': 'performer',
                    'analog': 'humdrum:MGN'
                }
            )
            ensembleNameEl.text = ensembleName.meiValue

        for performerName in performerNames:
            performerNameEl: MeiElement = bibl.appendSubElement(
                'persName',
                {
                    'role': 'performer',
                    'analog': 'humdrum:MPN'
                }
            )
            performerNameEl.text = performerName.meiValue

        for suspectedPerformerName in suspectedPerformerNames:
            suspectedPerformerNameEl: MeiElement = bibl.appendSubElement(
                'persName',
                {
                    'role': 'performer',
                    'cert': 'medium',
                    'analog': 'humdrum:MPS'
                }
            )
            suspectedPerformerNameEl.text = suspectedPerformerName.meiValue

        if producers or conductors:
            respStmt: MeiElement = bibl.appendSubElement('respStmt')

            for producer in producers:
                respEl: MeiElement = respStmt.appendSubElement(
                    'resp',
                    {
                        'analog': 'humdrum:RNP'
                    }
                )
                respEl.text = 'producer'
                persNameEl: MeiElement = respStmt.appendSubElement(
                    'persName',
                    {
                        'analog': 'humdrum:RNP'
                    }
                )
                persNameEl.text = producer.meiValue

            for conductor in conductors:
                respEl = respStmt.appendSubElement(
                    'resp',
                    {
                        'analog': 'humdrum:MCN'
                    }
                )
                respEl.text = 'conductor'
                persNameEl = respStmt.appendSubElement(
                    'persName',
                    {
                        'analog': 'humdrum:MCN'
                    }
                )
                persNameEl.text = conductor.meiValue

        if manufacturers or releaseDates or recordingPlaces or recordingDates:
            imprint: MeiElement = bibl.appendSubElement('imprint')

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
                        'isodate': M21Utilities.isoDateFromM21DateObject(
                            releaseDate.value
                        ),
                        'analog': 'humdrum:RRD'
                    }
                )
                releaseDateEl.text = releaseDate.meiValue

            for recordingPlace in recordingPlaces:
                recordingPlaceEl: MeiElement = imprint.appendSubElement(
                    'geogName',
                    {
                        'role': 'recordingPlace',
                        'analog': 'humdrum:RLC'
                    }
                )
                recordingPlaceEl.text = recordingPlace.meiValue

            for recordingDate in recordingDates:
                recordingDateEl: MeiElement = imprint.appendSubElement(
                    'date',
                    {
                        'type': 'recordingDate',
                        'isodate': M21Utilities.isoDateFromM21DateObject(
                            recordingDate.value
                        ),
                        'analog': 'humdrum:RDT'
                    }
                )
                recordingDateEl.text = recordingDate.meiValue

        for performanceLocation in performanceLocations:
            performanceLocationEl: MeiElement = bibl.appendSubElement(
                'geogName',
                {
                    'role': 'performanceLocation',
                    'analog': 'humdrum:MLC'
                }
            )
            performanceLocationEl.text = performanceLocation.meiValue

        if bibl.isEmpty():
            return None
        return source

    def makeRecordedTrackSource(self) -> MeiElement | None:
        if not self.anyExist('RT#'):
            return None

        source: MeiElement = MeiElement('source', {'type': 'recordedTrack'})
        bibl: MeiElement = source.appendSubElement('bibl')

        trackNumbers: list[MeiMetadataItem] = self.contents.get('RT#', [])

        bibl.appendSubElement('title')
        for trackNumber in trackNumbers:
            trackNumberEl: MeiElement = bibl.appendSubElement(
                'identifier',
                {
                    'analog': 'humdrum:RT#'
                }
            )
            trackNumberEl.text = trackNumber.meiValue

        bibl.appendSubElement(
            'relatedItem',
            {
                'rel': 'host',
                'data': '#album1'
            }
        )

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
                    'isodate': M21Utilities.isoDateFromM21DateObject(
                        copyrightDate.value
                    ),
                    'analog': 'humdrum:YOY'
                }
            )
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

    def makeMainComposerElements(self) -> list[MeiElement]:
        output: list[MeiElement] = []
        composers: list[MeiMetadataItem] = self.contents.get('COM', [])
        composerAliases: list[MeiMetadataItem] = self.contents.get('COL', [])
        composerDates: list[MeiMetadataItem] = self.contents.get('CDT', [])
        composerBirthPlaces: list[MeiMetadataItem] = self.contents.get('CBL', [])
        composerDeathPlaces: list[MeiMetadataItem] = self.contents.get('CDL', [])
        # TODO: Prefer composer birth/death dates from Contributor value.
        # TODO: But first make Humdrum importer put them there.


        for i, composer in enumerate(composers):
            # Assume association is done by ordering of the metadata item arrays
            # Currently our Humdrum importer assumes this ordering should match
            # the ordering in the file.
            composerAlias: MeiMetadataItem | None = None
            composerBirthAndDeathDate: MeiMetadataItem | None = None
            composerBirthPlace: MeiMetadataItem | None = None
            composerDeathPlace: MeiMetadataItem | None = None
            if i < len(composerAliases):
                composerAlias = composerAliases[i]
            if i < len(composerDates):
                composerBirthAndDeathDate = composerDates[i]
            if i < len(composerBirthPlaces):
                composerBirthPlace = composerBirthPlaces[i]
            if i < len(composerDeathPlaces):
                composerDeathPlace = composerDeathPlaces[i]

            composerElement = MeiElement('composer')
            output.append(composerElement)

            # composer name ('COM')
            persNameElement: MeiElement = composerElement.appendSubElement(
                'persName',
                {
                    'analog': 'humdrum:COM'
                }
            )
            persNameElement.text = composer.meiValue

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
            if composerBirthAndDeathDate is not None:
                isodate: str = M21Utilities.isoDateFromM21DateObject(
                    composerBirthAndDeathDate.value
                )

                attrib: dict[str, str] = {
                    'type': 'birth/death',
                    'analog': 'humdrum:CDT',
                }

                if isodate:
                    attrib['isodate'] = isodate

                dateElement: MeiElement = composerElement.appendSubElement(
                    'date',
                    attrib
                )
                dateElement.text = composerBirthAndDeathDate.meiValue

            # composer birth place
            if composerBirthPlace is not None:
                geogNameElement: MeiElement = composerElement.appendSubElement(
                    'geogName',
                    {
                        'role': 'birthPlace',
                        'analog': 'humdrum:CBL'
                    }
                )
                geogNameElement.text = composerBirthPlace.meiValue

            # composer death place
            if composerDeathPlace is not None:
                geogNameElement = composerElement.appendSubElement(
                    'geogName',
                    {
                        'role': 'deathPlace',
                        'analog': 'humdrum:CDL'
                    }
                )
                geogNameElement.text = composerDeathPlace.meiValue

        return output

    def makeMainTitleElement(self) -> MeiElement | None:
        mainTitles: list[MeiMetadataItem] = self.contents.get('OTL', [])
        plainNumbers: list[MeiMetadataItem] = self.contents.get('ONM', [])
        movementNumbers: list[MeiMetadataItem] = self.contents.get('OMV', [])
        movementNames: list[MeiMetadataItem] = self.contents.get('OMD', [])
        opusNumbers: list[MeiMetadataItem] = self.contents.get('OPS', [])
        actNumbers: list[MeiMetadataItem] = self.contents.get('OAC', [])
        sceneNumbers: list[MeiMetadataItem] = self.contents.get('OSC', [])

        titleElement = MeiElement('title')

        # First all the main titles (OTL).  The untranslated one goes first,
        # with titlePart@type="main", and the others get titlePart@type=translated.
        titlePart: MeiElement
        firstTitle: MeiMetadataItem | None = None
        firstLang: str = ''
        for mainTitle in mainTitles:
            if (isinstance(mainTitle.value, m21.metadata.Text)
                    and mainTitle.value.isTranslated is not True):
                firstTitle = mainTitle
                if firstTitle.value.language:
                    firstLang = firstTitle.value.language.lower()
                break

        if firstTitle is not None:
            attrib: dict[str, str] = {'type': 'main', 'analog': 'humdrum:OTL'}
            if firstLang:
                attrib['xml:lang'] = firstLang
            titlePart = titleElement.appendSubElement('titlePart', attrib)
            titlePart.text = firstTitle.meiValue

        for mainTitle in mainTitles:
            if mainTitle is firstTitle:
                continue

            isTranslated: bool = False
            lang: str = ''
            if isinstance(mainTitle.value, m21.metadata.Text):
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

            titlePart = titleElement.appendSubElement('titlePart', attrib)
            titlePart.text = mainTitle.meiValue

        # Then any number(s) (ONM).
        for plainNumber in plainNumbers:
            lang = ''
            if isinstance(plainNumber.value, m21.metadata.Text):
                if plainNumber.value.language:
                    lang = plainNumber.value.language.lower()

            attrib = {'type': 'number', 'analog': 'humdrum:ONM'}
            if lang:
                attrib['xml:lang'] = lang

            titlePart = titleElement.appendSubElement('titlePart', attrib)
            titlePart.text = plainNumber.meiValue

        # Then any movement number(s) (OMV).
        for movementNumber in movementNumbers:
            lang = ''
            if isinstance(movementNumber.value, m21.metadata.Text):
                if movementNumber.value.language:
                    lang = movementNumber.value.language.lower()

            attrib = {'type': 'movementNumber', 'analog': 'humdrum:OMV'}
            if lang:
                attrib['xml:lang'] = lang

            titlePart = titleElement.appendSubElement('titlePart', attrib)
            titlePart.text = movementNumber.meiValue

        # Then any movement name(s) (OMD). titlePart@type=movementName.  Untranslated first,
        # if there is one, but type is always movementName here.
        firstMovementName: MeiMetadataItem | None = None
        firstLang = ''
        for movementName in movementNames:
            if (isinstance(movementName.value, m21.metadata.Text)
                    and movementName.value.isTranslated is not True):
                firstMovementName = movementName
                if movementName.value.language:
                    firstLang = movementName.value.language.lower()
                break

        if firstMovementName is not None:
            attrib = {'type': 'movementName', 'analog': 'humdrum:OMD'}
            if firstLang:
                attrib['xml:lang'] = firstLang
            titlePart = titleElement.appendSubElement('titlePart', attrib)
            titlePart.text = firstMovementName.meiValue

        for movementName in movementNames:
            if movementName is firstMovementName:
                continue

            lang = ''
            if isinstance(movementName.value, m21.metadata.Text):
                if movementName.value.language:
                    lang = movementName.value.language.lower()

            attrib = {'type': 'movementName', 'analog': 'humdrum:OMD'}
            if lang:
                attrib['xml:lang'] = lang

            titlePart = titleElement.appendSubElement('titlePart', attrib)
            titlePart.text = movementName.meiValue

        # Then any opus number(s) (OPS).
        for opusNumber in opusNumbers:
            lang = ''
            if isinstance(opusNumber.value, m21.metadata.Text):
                if opusNumber.value.language:
                    lang = opusNumber.value.language.lower()

            attrib = {'type': 'opusNumber', 'analog': 'humdrum:OPS'}
            if lang:
                attrib['xml:lang'] = lang

            titlePart = titleElement.appendSubElement('titlePart', attrib)
            titlePart.text = opusNumber.meiValue

        # Then any act number(s) (OAC).
        for actNumber in actNumbers:
            lang = ''
            if isinstance(actNumber.value, m21.metadata.Text):
                if actNumber.value.language:
                    lang = actNumber.value.language.lower()

            attrib = {'type': 'actNumber', 'analog': 'humdrum:OAC'}
            if lang:
                attrib['xml:lang'] = lang

            titlePart = titleElement.appendSubElement('titlePart', attrib)
            titlePart.text = actNumber.meiValue

        # Then any scene number(s) (OSC).
        for sceneNumber in sceneNumbers:
            lang = ''
            if isinstance(sceneNumber.value, m21.metadata.Text):
                if sceneNumber.value.language:
                    lang = sceneNumber.value.language.lower()

            attrib = {'type': 'sceneNumber', 'analog': 'humdrum:OSC'}
            if lang:
                attrib['xml:lang'] = lang

            titlePart = titleElement.appendSubElement('titlePart', attrib)
            titlePart.text = sceneNumber.meiValue

        if titleElement.isEmpty():
            return None
        return titleElement

    def makeEncodingDescElement(self) -> MeiElement | None:
        return None

    def makeWorkListElement(self) -> MeiElement | None:
        return None

    def makeManifestationListElement(self) -> MeiElement | None:
        return None

    def makeExtMetaElement(self) -> MeiElement | None:
        return None
