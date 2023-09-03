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
        #   2. self.key is a standard music21 uniqueName, in which case we know
        #       which humdrum key it maps to (this is knowledge shared with our
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
        self.mainComposerElement: MeiElement | None = None

    def makeRootElement(self, tb: TreeBuilder):
        meiHead: MeiElement = MeiElement('meiHead')
        fileDesc: MeiElement = self.makeFileDescElement(self.m21Metadata)
        encodingDesc: MeiElement | None = self.makeEncodingDescElement(self.m21Metadata)
        workList: MeiElement | None = self.makeWorkListElement(self.m21Metadata)
        manifestationList: MeiElement | None = self.makeManifestationListElement(self.m21Metadata)
        extMeta: MeiElement | None = self.makeExtMetaElement(self.m21Metadata)

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

    def makeFileDescElement(self, md: m21.metadata.Metadata) -> MeiElement:
        # meiHead/fileDesc is required, so we never return None here
        fileDesc: MeiElement = MeiElement('fileDesc')
        titleStmt: MeiElement = fileDesc.appendSubElement('titleStmt')
        self.mainTitleElement = self.makeMainTitleElement(md)
        if self.mainTitleElement is not None:
            titleStmt.subElements.append(self.mainTitleElement)

        # TODO: finish fileDesc (pubStmt, sourceDesc)
        return fileDesc

    def makeMainTitleElement(self, md: m21.metadata.Metadata) -> MeiElement | None:
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

    def makeEncodingDescElement(self, md: m21.metadata.Metadata) -> MeiElement | None:
        return None

    def makeWorkListElement(self, md: m21.metadata.Metadata) -> MeiElement | None:
        return None

    def makeManifestationListElement(self, md: m21.metadata.Metadata) -> MeiElement | None:
        return None

    def makeExtMetaElement(self, md: m21.metadata.Metadata) -> MeiElement | None:
        return None
