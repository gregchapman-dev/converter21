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
                if key not in M21Utilities.validAbcMetadataKeys:
                    continue

                infoChars: str = key[4:]
                if key in M21Utilities.abcMetadataKeysThatWantMultilineValues:
                    # This value might be multiline, and needs to be split
                    # into multiple (e.g.) 'N:'-prefixed lines
                    addMultilineValue(infoChars, value)
                else:
                    addValueIfUnique(infoChars, value)
            elif key == 'alternativeTitle':
                # special case, not in the lookup tables
                addValueIfUnique('T', value)
            elif key == 'localeOfComposition':
                # special case, not in the lookup tables
                addValueIfUnique('O', value)
            elif key == 'electronicEncoder':
                # special case, not in the lookup tables
                addValueIfUnique('Z:abc-transcription', value)
            elif key == 'electronicEditor':
                # special case, not in the lookup tables
                addValueIfUnique('Z:abc-edited-by', value)
            elif key == 'copyright':
                # special case, not in the lookup tables
                addValueIfUnique('Z:abc-copyright', value)
            elif key in M21Utilities.m21MetadataPropertyNameToAbcMetadataKey:
                # use the lookup tables
                abcKey: str = M21Utilities.m21MetadataPropertyNameToAbcMetadataKey[key]
                infoChar: str = abcKey[4:]
                if infoChar == 'X':
                    addValueOnlyOnce(infoChar, value)
                else:
                    addValueIfUnique(infoChar, value)

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

            mdKey: str = 'abc:' + hfKey
            if (mdKey not in M21Utilities.validAbcMetadataKeys
                    and mdKey not in M21Utilities.complexAbcMetadataKeyToM21MetadataPropertyName):
                # it wasn't in our 'abc:*' lookup tables.  Skip it.
                continue

            if mdKey in M21Utilities.abcMetadataKeyToM21MetadataPropertyName:
                newMdKey: str = M21Utilities.abcMetadataKeyToM21MetadataPropertyName[mdKey]
                if newMdKey:
                    # abc:x maps directly to a uniqueName (or non-standard but useful humdrum
                    # or mei name), so we should use that instead.
                    mdKey = newMdKey

            # special 'abc:x:abc-something' keys (with their own lookup table)
            if mdKey in M21Utilities.complexAbcMetadataKeyToM21MetadataPropertyName:
                mdKey = M21Utilities.complexAbcMetadataKeyToM21MetadataPropertyName[mdKey]

            if mdKey in M21Utilities.abcMetadataKeysThatWantMultilineValues:
                # These we treat as one metadata entry, with a multiline string.
                addValue(md, mdKey, hfValue)
            elif mdKey == 'number':
                # special case, must check for malformed 'X:non-numeric'
                if hfValue.isdigit():
                    addValue(md, mdKey, hfValue)
            elif mdKey in ('countryOfComposition', 'abc:A'):
                # abc:O (origin) maps to 'countryOfComposition'.
                # abc:A (area) is deprecated, but we can read it.
                # special case: we try to detect if locale or country
                vals = splitValues(hfValue)
                for val in vals:
                    if ';' in val or ',' in val:
                        addValue(md, 'localeOfComposition', val)
                    else:
                        addValue(md, 'countryOfComposition', val)
            elif mdKey == 'title':
                # special case: first T is title, subsequent are alternativeTitle
                vals = splitValues(hfValue)
                for i, val in enumerate(vals):
                    if i == 0:
                        addValue(md, 'title', val)
                    else:
                        addValue(md, 'alternativeTitle', val)
            else:
                # everybody else
                addValues(md, mdKey, hfValue)

        return md
