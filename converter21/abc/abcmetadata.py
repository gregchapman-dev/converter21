# ------------------------------------------------------------------------------
# Name:          abcmetadata.py
# Purpose:       AbcMetadata performs conversion from/to music21 metadata to/from ABC info lines
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2025 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import typing as t
import copy
import re

import music21 as m21

from converter21.shared import SharedConstants
from converter21.shared import M21Utilities

class AbcMetadata:

    complexAbcInfoKeys: list[str] = [
        # these are the M21Utilities.complexAbcMetadataKeyToM21MetadataPropertyName keys
        # with the leading 'abc:' stripped off.  e.g. 'abc:I:abc-creator' becomes
        # 'I:abc-creator'.
        key[4:] for key in M21Utilities.complexAbcMetadataKeyToM21MetadataPropertyName
    ]

    @staticmethod
    def m21MetadataToAbcHeaderLines(md: m21.metadata.Metadata, xNumber: int | None) -> list[str]:
        infoDict: dict[str, list[str | list[str]]] = {}

        def addValue(k: str, v: t.Any):
            v = str(v)
            if '\n' in v:
                addMultilineValue(k, v)
            else:
                addValueIfUnique(k, v)

        def addMultilineValue(k: str, v: str):
            lines: list[str] = v.split('\n')
            valList = infoDict.get(k, None)
            if valList is None:
                infoDict[k] = []
                valList = infoDict[k]
            valList.append(lines)

        def addValueIfUnique(k: str, v: str):
            # doesn't add if value is already present
            if valList := infoDict.get(k, None):
                if v not in valList:
                    valList.append(v)
            else:
                infoDict[k] = [v]

        def addValueOnlyOnce(k: str, v: t.Any):
            v = str(v)
            if infoDict.get(k, None):
                # already have one
                return
            infoDict[k] = [v]

        def spacesToUnderscores(s: str) -> str:
            output: str = re.sub(' ', '_', s)
            return output

        # grab the title(s) first, so they go before any alternateTitle(s)
        if titles := md['title']:
            for title in titles:
                addValue('T', title)

        for key, value in md.all(returnSorted=False, returnPrimitives=True):
            if key == 'title':
                # we already did the titles above
                continue

            if key.startswith('abc:'):
                # chars after 'abc:' is the info key (e.g. 'N', 'H', 'W',
                # 'Z', 'Z:abc-transcription', etc)
                if key not in M21Utilities.validAbcMetadataKeys:
                    continue

                infoChars: str = key[4:]
                addValue(infoChars, value)
            elif key == 'alternativeTitle':
                # special case, not in the lookup tables
                addValue('T', value)
            elif key == 'localeOfComposition':
                # special case, not in the lookup tables
                addValue('O', value)
            elif key == 'electronicEncoder':
                # special case, not in the lookup tables
                addValue('Z:abc-transcription', value)
            elif key == 'electronicEditor':
                # special case, not in the lookup tables
                addValue('Z:abc-edited-by', value)
            elif key == 'copyright':
                # special case, not in the lookup tables
                addValue('Z:abc-copyright', value)
            elif key in M21Utilities.m21MetadataPropertyNameToAbcMetadataKey:
                # use the lookup tables
                abcKey: str = M21Utilities.m21MetadataPropertyNameToAbcMetadataKey[key]
                infoChar: str = abcKey[4:]
                if infoChar == 'X':
                    addValueOnlyOnce(infoChar, value)
                else:
                    addValue(infoChar, value)
            else:
                # metadata that ABC has no official place to put.  We write it as:
                # %%metadata:key value (key is uniqueName or customName)
                if (key.startswith('raw:')
                        or key.startswith('meiraw:')
                        or key.startswith('humdrumraw:')):
                    # from original parsed file, no longer relevant (or we would have
                    # made up a better namespace name during parse)
                    continue
                if key in ('filePath', 'fileFormat', 'fileNumber', 'corpusFilePath'):
                    # only relevant to original parsed file, not to the file we are writing
                    continue
                if key == 'software':
                    # ABC doesn't care about all the software, just the abc-creator,
                    # which is handled separately.
                    continue

                if key == 'otherContributor':
                    key += f':{spacesToUnderscores(value.role)}'
                addValue('%%metadata:' + key, value)

        # write our own I:abc-creator and I:abc-version value (not from md)
        addValue('I:abc-creator', f'{SharedConstants._CONVERTER21_NAME_AND_VERSION}')
        addValue('I:abc-version', '2.1')

        # sort the lines into output in the preferred order
        output: list[str] = []

        def appendToOutput(key: str, vals: list[str | list[str]]):
            xAlreadyWritten: bool = False
            delim: str = ':'
            if len(key) > 1:
                # e.g. key == 'Z:abc-transcription' or '%%metadata:suspectedComposer'
                # or '%%metadata:mei:printedSourceCopyright'
                delim = ' '
            for valIdx, val in enumerate(vals):
                valLinesList: list[str]
                if isinstance(val, str):
                    valLinesList = [val]
                else:
                    valLinesList = val

                # if non-first value of key, add keyed blank line
                # to delimit the two values, so the reader can
                # tell the difference between (e.g.) two single
                # line values, and a two-line value.
                if valIdx > 0:
                    if delim == ' ':
                        output.append(f'{key}')
                    else:
                        output.append(f'{key}{delim}')

                for valLine in valLinesList:
                    if key == 'X' and not xAlreadyWritten:
                        # Don't write non-integer X: value to ABC files
                        # (some folks put random stuff in metadata['number']).
                        # Also, only write at most one 'X:n'.
                        if not valLine.isdigit():
                            continue

                    output.append(f'{key}{delim}{valLine}')
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

        theRestDict: dict[str, list[str | list[str]]] = copy.copy(infoDict)
        for firstChar in 'XTCOZN':
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
    def abcHeaderLinesToM21Metadata(headerLines: list[str]) -> m21.metadata.Metadata:
        # takes initial lines of tune, ending with first 'K:'
        def mergeContinuationLines(headerLines: list[str]) -> list[str]:
            output: list[str] = []
            for hLine in headerLines:
                if hLine.startswith('+:'):
                    # append the rest of the '+:' line to the previous line
                    if not output:
                        # file started with continuation line, weird...
                        continue
                    output[-1] += ' ' + hLine[2:]
                else:
                    output.append(hLine)
            return output

        def underscoresToSpaces(s: str) -> str:
            output: str = re.sub('_', ' ', s)
            return output

        def addMetadataItem(
            md: m21.metadata.Metadata,
            mdKey: str,
            mdValue: str | m21.metadata.Contributor,
            mdKeyOfCurrentMultilineValue: str
        ) -> str:
            # returns new value of mdKeyOfCurrentMultilineValue

            # some validation and key munging
            if mdKey == 'number':
                if t.TYPE_CHECKING:
                    assert isinstance(mdValue, str)
                if not mdValue.isdigit():
                    return mdKeyOfCurrentMultilineValue

            if mdKey in ('countryOfComposition', 'abc:A'):
                if t.TYPE_CHECKING:
                    assert isinstance(mdValue, str)
                if ';' in mdValue or ',' in mdValue:
                    mdKey = 'localeOfComposition'
                else:
                    mdKey = 'countryOfComposition'

            if mdKey == 'title':
                if md['title']:
                    # special case: first T is title, subsequent are alternativeTitle
                    mdKey = 'alternativeTitle'

            # handle multi-line continuations, etc
            if mdKey == mdKeyOfCurrentMultilineValue and mdValue:
                M21Utilities.appendToValue(md, mdKey, mdValue)
            elif mdKey == mdKeyOfCurrentMultilineValue and not mdValue:
                # break off current multiline value (but otherwise
                # ignore the empty value)
                mdKeyOfCurrentMultilineValue = ''
            else:  # mdKey != mdKeyOfCurrentMultilineValue
                # break off any current multiline value and create new
                # other-keyed item (that might be the start of a multiline value)
                mdKeyOfCurrentMultilineValue = ''
                M21Utilities.addIfNotADuplicate(md, mdKey, mdValue)
                mdKeyOfCurrentMultilineValue = mdKey

            return mdKeyOfCurrentMultilineValue

        headerLines = mergeContinuationLines(headerLines)

        md = m21.metadata.Metadata()
        mdKeyOfCurrentMultilineValue: str = ''

        mdKey: str
        mdValue: str | m21.metadata.Contributor

        for hLine in headerLines:
            if not hLine:
                mdKeyOfCurrentMultilineValue = ''
                continue

            if hLine.startswith('%%metadata:'):
                # TODO: handle custom metadata
                hLine = hLine[11:]
                keyAndValue = hLine.split(' ', 1)
                if len(keyAndValue) == 1:
                    # blank line, we need to see this as a delimiter between (possibly)
                    # multi-line items with the same key
                    keyAndValue = [keyAndValue[0], '']

                mdKey = keyAndValue[0]
                mdValue = keyAndValue[1]
                if mdKey.startswith('otherContributor:'):
                    # set up a ContributorValue with the appropriate role
                    role: str = mdKey.split(':', 1)[1]
                    role = underscoresToSpaces(role)
                    newValue = m21.metadata.Contributor(name=mdValue, role=role)
                    mdValue = newValue
                    mdKey = 'otherContributor'

                mdKeyOfCurrentMultilineValue = addMetadataItem(
                    md, mdKey, mdValue, mdKeyOfCurrentMultilineValue
                )

                continue

            if hLine[0] in ('%', 'K', 'L', 'M', 'Q', 'U'):
                # header line that is not metadata
                mdKeyOfCurrentMultilineValue = ''
                continue

            if hLine[0] in ('Z', 'I'):
                # check for complex name (e.g. 'Z:abc-edited-by' or 'I:abc-creator')
                complexNameProcessed: bool = False
                for complexName in AbcMetadata.complexAbcInfoKeys:
                    if hLine.startswith(complexName):
                        abcInfoKeyAndValue = hLine.split(' ', 1)
                        if len(abcInfoKeyAndValue) == 1:
                            # blank line, we need to see this as a delimiter between (possibly)
                            # multi-line items with the same key.  Set complexNameProcessed to
                            # True because that's all this line means.
                            mdKeyOfCurrentMultilineValue = ''
                            complexNameProcessed = True
                            break

                        # handle the complex info key case
                        mdKey = 'abc:' + abcInfoKeyAndValue[0]
                        mdValue = abcInfoKeyAndValue[1].strip()
                        mdKey = M21Utilities.complexAbcMetadataKeyToM21MetadataPropertyName.get(
                            mdKey, mdKey
                        )

                        mdKeyOfCurrentMultilineValue = addMetadataItem(
                            md, mdKey, mdValue, mdKeyOfCurrentMultilineValue
                        )
                        complexNameProcessed = True
                        break

                if complexNameProcessed:
                    continue

            if len(hLine) < 2:
                mdKeyOfCurrentMultilineValue = ''
                continue
            if hLine[1] != ':':
                mdKeyOfCurrentMultilineValue = ''
                continue
            if 'abc:' + hLine[0] not in M21Utilities.validAbcMetadataKeys:
                mdKeyOfCurrentMultilineValue = ''
                continue

            # normal (non-complex) case (e.g. Z:, C:, etc)
            abcInfoKeyAndValue = hLine.split(':', 1)
            if len(abcInfoKeyAndValue) == 1:
                # no colon?! skip this info line.
                mdKeyOfCurrentMultilineValue = ''
                continue

            mdKey = 'abc:' + abcInfoKeyAndValue[0]
            if mdKey not in M21Utilities.abcMetadataKeyToM21MetadataPropertyName:
                # non-metadata info line, skip it.
                mdKeyOfCurrentMultilineValue = ''
                continue
            newKey: str = M21Utilities.abcMetadataKeyToM21MetadataPropertyName[mdKey]
            if newKey:
                mdKey = newKey
            mdValue = abcInfoKeyAndValue[1].strip()
            mdKeyOfCurrentMultilineValue = addMetadataItem(
                md, mdKey, mdValue, mdKeyOfCurrentMultilineValue
            )

        return md
