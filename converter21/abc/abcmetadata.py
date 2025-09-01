# ------------------------------------------------------------------------------
# Name:          abcmetadata.py
# Purpose:       AbcMetadata performs conversion from/to music21 metadata to/from ABC info lines
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2025 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
# import typing as t
import copy

import music21 as m21

from converter21.shared import SharedConstants
from converter21.shared import M21Utilities

class AbcMetadata:

    @staticmethod
    def m21MetadataToAbcInfoLines(md: m21.metadata.Metadata, xNumber: int | None) -> list[str]:
        # infoDict is slightly different from mxm.header_fields_for_converter21
        # Here values per key are represented by a list, instead of a space-
        # delimited string.
        infoDict: dict[str, list[str]] = {}

        def addValue(k: str, v: str):
            if valList := infoDict.get(k, None):
                valList.append(v)
            else:
                infoDict[k] = [v]

        def addMultilineValue(k: str, v: str):
            lines: list[str] = v.split('\n')
            valList = infoDict.get(k, None)
            if valList is None:
                infoDict[k] = []
                valList = infoDict[k]
            for line in lines:
                valList.append(line)

        def addValueIfUnique(k: str, v: str):
            # doesn't add if value is already present
            if valList := infoDict.get(k, None):
                if v not in valList:
                    valList.append(v)
            else:
                infoDict[k] = [v]

        def addValueOnlyOnce(k: str, v: str):
            if infoDict.get(k, None):
                # already have one
                return
            infoDict[k] = [v]

        # grab the title(s) first, so they go before any alternateTitle(s)
        if titles := md['title']:
            for t in titles:
                addValueIfUnique('T', str(t))

        for key, value in md.all(returnSorted=False):
            if key == 'title':
                # we already did the titles above
                continue

            if key.startswith('abc:'):
                # chars after 'abc:' is the info key (e.g. 'N', 'H', 'W',
                # 'Z', 'Z:abc-transcription', etc)
                infoChars: str = key[4:]
                if infoChars in ('N', 'H', 'W', 'S', 'Z'):
                    # This value might be multiline, and needs to be split
                    # into multiple (e.g.) 'N:'-prefixed lines
                    addMultilineValue(infoChars, value)
                else:
                    addValueIfUnique(infoChars, value)
            elif key == 'number':
                addValueOnlyOnce('X', value)
            elif key == 'alternativeTitle':
                addValueIfUnique('T', value)
            elif key == 'composer':
                addValueIfUnique('C', value)
            elif key == 'parentTitle':
                addValueIfUnique('B', value)
            elif key == 'filePath':
                # nope, this is the filePath that was parsed to produce md, not
                # the filePath of the file we are writing.
                pass
            elif key == 'humdrum:RTL':
                addValueIfUnique('D', value)
            elif key in ('localeOfComposition', 'countryOfComposition'):
                addValueIfUnique('O', value)
            elif key == 'electronicEncoder':
                addValueIfUnique('Z:abc-transcription', value)
            elif key == 'electronicEditor':
                addValueIfUnique('Z:abc-edited-by', value)
            elif key == 'copyright':
                addValueIfUnique('Z:abc-copyright', value)

        # write our own I:abc-creator value (not from md)
        addValue('I:abc-creator', f'{SharedConstants._CONVERTER21_NAME_AND_VERSION}')

        # sort the lines into output in the preferred order
        output: list[str] = []

        def appendToOutput(key: str, vals: list[str]):
            xAlreadyWritten: bool = False
            delim: str = ':'
            if len(key) > 1:
                # e.g. key == 'Z:abc-transcription'
                delim = ' '
            for val in vals:
                if key == 'X' and not xAlreadyWritten:
                    # Don't write non-integer X: value to ABC files
                    # (some folks put random stuff in metadata['number']).
                    # Also, only write at most one 'X:n'.
                    if not val.isdigit():
                        continue

                output.append(f'{key}{delim}{val}')
                if key == 'X':
                    xAlreadyWritten = True

        # Order as: X, T, C, Z, O, all the rest
        # X is required, so if there is no X, make one up
        skipX: bool = False
        if xNumber is not None:
            appendToOutput('X', [str(xNumber)])
            skipX = True
        elif 'X' not in infoDict:
            appendToOutput('X', ['1'])

        theRestDict: dict[str, list[str]] = copy.copy(infoDict)
        for firstChar in 'XTCOZ':
            if firstChar == 'X' and skipX:
                continue
            for key, vals in infoDict.items():
                if key[0] == firstChar:
                    appendToOutput(key, vals)
                    del theRestDict[key]

        # now the rest (from theRestDict)
        for key, vals in theRestDict.items():
            appendToOutput(key, vals)

        return output

    @staticmethod
    def abcInfoDictToMetadata(infoFields: dict[str, str]) -> m21.metadata.Metadata:
        # takes info dict keyed by 'X', 'T', 'C', 'Z', 'I', etc

        def addValue(md: m21.metadata.Metadata, mdKey: str, hfValue: str):
            M21Utilities.addIfNotADuplicate(md, mdKey, hfValue)

        def addValues(md: m21.metadata.Metadata, mdKey: str, hfValue: str):
            hfValues: list[str] = splitValues(hfValue)
            if mdKey == 'title':
                for i, val in enumerate(hfValues):
                    if i == 0:
                        M21Utilities.addIfNotADuplicate(md, 'title', val)
                        continue
                    M21Utilities.addIfNotADuplicate(md, 'alternativeTitle', val)
            else:
                for val in hfValues:
                    M21Utilities.addIfNotADuplicate(md, mdKey, val)

        def splitValues(hfValue: str) -> list[str]:
            return hfValue.split('\n')

        # Start by splitting out 'Z' and 'I' into separate entries for
        # "no :abc" and all the different ":abc-whatever" names we see.
        newInfoFields: dict[str, str] = {}
        itemList = list(infoFields.items())
        for hfKey, hfValue in itemList:
            if hfKey in ('Z', 'I'):
                vals = splitValues(hfValue)
                for val in vals:
                    abcNameAndValue = val.split(' ', 1)
                    if len(abcNameAndValue) == 1:
                        if hfKey == 'Z':
                            # no space-delimited abcName, so just do 'Z'
                            if newVal := newInfoFields.get('Z'):
                                newInfoFields['Z'] = newVal + '\n' + val
                            else:
                                newInfoFields['Z'] = val
                            continue

                    abcName = abcNameAndValue[0]
                    if not abcName.startswith('abc'):
                        if hfKey == 'Z':
                            # no parseable abcName, so just do 'Z'
                            if newVal := newInfoFields.get('Z'):
                                newInfoFields['Z'] = newVal + '\n' + val
                            else:
                                newInfoFields['Z'] = val
                            continue
                        if hfKey == 'I':
                            # we ignore unparseable I: abcNames because there are a lot,
                            # and they are generally not metadata.
                            continue

                    abcValue = abcNameAndValue[1]
                    if hfKey == 'Z':
                        if abcName == 'abc-transcription':
                            if newVal := newInfoFields.get('Z:abc-transcription'):
                                newInfoFields['Z:abc-transcription'] = newVal + '\n' + abcValue
                            else:
                                newInfoFields['Z:abc-transcription'] = abcValue
                        elif abcName == 'abc-edited-by':
                            if newVal := newInfoFields.get('Z:abc-edited-by'):
                                newInfoFields['Z:abc-edited-by'] = newVal + '\n' + abcValue
                            else:
                                newInfoFields['Z:abc-edited-by'] = abcValue
                        elif abcName == 'abc-copyright':
                            if newVal := newInfoFields.get('Z:abc-copyright'):
                                newInfoFields['Z:abc-copyright'] = newVal + '\n' + abcValue
                            else:
                                newInfoFields['Z:abc-copyright'] = abcValue
                        else:
                            if newVal := newInfoFields.get('Z:' + abcName):
                                newInfoFields['Z:' + abcName] = newVal + '\n' + abcValue
                            else:
                                newInfoFields['Z:' + abcName] = abcValue
                    elif hfKey == 'I':
                        # ignore everything but 'abc-creator'; lots of non-metadata in I:
                        if abcName == 'abc-creator':
                            if newVal := newInfoFields.get('I:abc-creator'):
                                newInfoFields['I:abc-creator'] = newVal + '\n' + abcValue
                            else:
                                newInfoFields['I:abc-creator'] = abcValue

                # delete this entry from infoFields
                del infoFields[hfKey]

        # Add everything back in (split apart nicely)
        infoFields.update(newInfoFields)

        md = m21.metadata.Metadata()

        # music21 is already in the md.software list, add converter21, and then
        # we will add any I:abc-creator we happen to see as well.
        verStr: str = SharedConstants._CONVERTER21_NAME_AND_VERSION
        md.add('software', verStr)

        for hfKey, hfValue in infoFields.items():
            if not hfValue:
                # ignore metadata with no value(s)
                continue

            if hfKey in ('K', 'L', 'M', 'Q', 'U'):
                # header data that is not metadata
                continue

            mdAbcCustomKey: str = 'abc:' + hfKey
            if mdAbcCustomKey in M21Utilities.abcMetadataKeysThatWantMultilineValues:
                # There is no standard metadata key in music21 for these, so we
                # make up a custom namespace:name such as 'abc:N', etc.
                # These we treat as one metadata entry, with a multiline string.
                addValue(md, mdAbcCustomKey, hfValue)
            elif mdAbcCustomKey in M21Utilities.abcMetadataKeysThatWantMultipleSingleLineValues:
                # There is no standard metadata key in music21 for these, so we
                # make up a custom namespace:name such as 'abc:R', etc.
                # These we split into individual one-line metadata entries.
                addValues(md, mdAbcCustomKey, hfValue)
            elif hfKey == 'X':
                if hfValue.isdigit():
                    addValue(md, 'number', hfValue)
            elif hfKey == 'T':
                addValues(md, 'title', hfValue)
            elif hfKey == 'C':
                addValues(md, 'composer', hfValue)
            elif hfKey == 'B':  # 'book'
                addValues(md, 'parentTitle', hfValue)
            elif hfKey == 'D':  # discography
                # instead of abc:D, we use Humdrum's existing recording title item
                # Note that MEI import from verovio-translated ABC -> MEI will need
                # to read abc:D and set it as humdrum:RTL in the music21 metadata.
                addValues(md, 'humdrum:RTL', hfValue)  # 'album title'
            elif hfKey in ('O', 'A'):
                # 'A' is deprecated, we will read it, but write it as 'O'
                vals = splitValues(hfValue)
                for val in vals:
                    if ';' in val or ',' in val:
                        addValue(md, 'localeOfComposition', val)
                    else:
                        addValue(md, 'countryOfComposition', val)
            elif hfKey == 'I:abc-creator':
                addValues(md, 'software', hfValue)
            elif hfKey == 'Z:abc-transcription':
                addValues(md, 'electronicEncoder', hfValue)
            elif hfKey == 'Z:abc-edited-by':
                addValues(md, 'electronicEditor', hfValue)
            elif hfKey == 'Z:abc-copyright':
                addValues(md, 'copyright', hfValue)
            else:
                pass  # print(f'need to support {hfKey}')

        return md
