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
        meiHead.appendSubElement(fileDesc)

        if encodingDesc:
            meiHead.appendSubElement(encodingDesc)
        if workList:
            meiHead.appendSubElement(workList)
        if manifestationList:
            meiHead.appendSubElement(manifestationList)
        if extMeta:
            meiHead.appendSubElement(extMeta)

        meiHead.makeRootElement(tb)

    def makeFileDescElement(self, md: m21.metadata.Metadata) -> MeiElement:
        # meiHead/fileDesc is required, so we never return None here
        fileDesc: MeiElement = MeiElement('fileDesc')
        titleStmt: MeiElement = fileDesc.appendSubElement('titleStmt')
        mainTitleElement: MeiElement | None = self.makeMainTitleElement(md)
        if mainTitleElement is not None:
            self.mainTitleElement = titleStmt.appendSubElement(mainTitleElement)

        # TODO: finish fileDesc (pubStmt, sourceDesc)
        return fileDesc

    def makeMainTitleElement(self, md: m21.metadata.Metadata) -> MeiElement | None:
        mainTitleElement = MeiElement('title')
        # First all the main titles (OTL).  The untranslated one goes first,
        # with titlePart@type="main", and the others get titlePart@type=translated.
        mainTitleList: list[MeiMetadataItem] = self.contents.get('OTL', [])
        # Then any number (ONM).
        # Then any movement number (OMV).
        # Then any movement names (OMD). titlePart@type=movementName.  Untranslated first,
        # if there is one, but type is always movementName here.
        movementNameList: list[MeiMetadataItem] = self.contents.get('OMD', [])
        # Then any opus number (OPS).
        # Then any act number (OAC).
        # THen any scene number (OSC).
        if mainTitleElement.isEmpty():
            return None
        return mainTitleElement

    def makeEncodingDescElement(self, md: m21.metadata.Metadata) -> MeiElement | None:
        return None

    def makeWorkListElement(self, md: m21.metadata.Metadata) -> MeiElement | None:
        return None

    def makeManifestationListElement(self, md: m21.metadata.Metadata) -> MeiElement | None:
        return None

    def makeExtMetaElement(self, md: m21.metadata.Metadata) -> MeiElement | None:
        return None
