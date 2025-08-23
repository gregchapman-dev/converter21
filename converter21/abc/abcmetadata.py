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

class AbcMetadata:

    @staticmethod
    def m21MetadataToAbcInfoLines(md: m21.metadata.Metadata, xNumber: int | None) -> list[str]:
        # infoDict is slightly different from mxm.header_fields_for_converter21
        # Here values per key are represented by a list, instead of a space-
        # delimited string.
        infoDict: dict[str, list[str]] = {}

        def addValue(k: str, v: str):
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

        for key, value in md.all(returnSorted=False):
            if key.startswith('abc:'):
                # chars after 'abc:' is the info key (e.g. 'N', 'H', 'W',
                # 'Z', 'Z:abc-transcription', etc)
                infoChars: str = key[4:]
                addValue(infoChars, value)

            elif key == 'number':
                addValueOnlyOnce('X', value)
            elif key == 'title':
                addValue('T', value)
            elif key == 'composer':
                addValue('C', value)
            elif key == 'parentTitle':
                addValue('B', value)
            elif key == 'filePath':
                # nope, this is the filePath that was parsed to produce md, not
                # the filePath of the file we are writing.
                pass
            elif key == 'humdrum:RTL':
                addValue('D', value)
            elif key in ('localeOfComposition', 'countryOfComposition'):
                addValue('O', value)
            elif key == 'electronicEncoder':
                addValue('Z:abc-transcription', value)
            elif key == 'electronicEditor':
                addValue('Z:abc-edited-by', value)
            elif key == 'copyright':
                addValue('Z:abc-copyright', value)

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
            md.add(mdKey, hfValue)

        def addCustomValue(md: m21.metadata.Metadata, mdKey: str, hfValue: str):
            md.addCustom(mdKey, hfValue)

        def addValues(md: m21.metadata.Metadata, mdKey: str, hfValue: str):
            hfValues: list[str] = splitValues(hfValue)
            md.add(mdKey, hfValues)

        def addCustomValues(md: m21.metadata.Metadata, mdKey: str, hfValue: str):
            hfValues: list[str] = splitValues(hfValue)
            md.addCustom(mdKey, hfValues)

        def splitValues(hfValue: str) -> list[str]:
            return hfValue.split('\n')

        md = m21.metadata.Metadata()

        # music21 is already in the md.software list, add converter21, and then
        # we will add any I:abc-creator we happen to see as well.
        verStr: str = SharedConstants._CONVERTER21_NAME_AND_VERSION
        md.add('software', verStr)

        for hfKey, hfValue in infoFields.items():
            if hfKey in ('K', 'L', 'M', 'Q', 'P', 'U'):
                # header data that is not metadata
                continue

            if hfKey in ('N', 'H', 'W', 'R', 'G'):
                # There is no standard metadata key in music21 for these, so we
                # make up a custom namespace:name such as 'abc:N', etc.
                # N = notes: such as references to other tunes which are similar,
                #   details on how the original notation of the tune was converted
                #   to abc, etc
                # H = history: designed for multi-line notes, stories and anecdotes
                # W = untimed lyrics: to be printed after the music, for example
                # R = rhythm: an indication of the type of tune (e.g. hornpipe, double jig,
                #   single jig, 48-bar polka, etc).
                # G: grouping key (used for so many different things)
                addCustomValues(md, 'abc:' + hfKey, hfValue)
            elif hfKey == 'X':
                if hfValue.isdigit():
                    addValue(md, 'number', hfValue)
            elif hfKey == 'T':
                addValues(md, 'title', hfValue)
            elif hfKey == 'C':
                addValues(md, 'composer', hfValue)
            elif hfKey == 'B':  # 'book'
                addValues(md, 'parentTitle', hfValue)
            elif hfKey == 'F':  # file URL
                addValues(md, 'filePath', hfValue)
            elif hfKey == 'D':  # discography
                # instead of abc:D, we use Humdrum's existing recording title item
                # Note that MEI import from verovio-translated ABC -> MEI will need
                # to read abc:D and set it as humdrum:RTL in the music21 metadata.
                addCustomValues(md, 'humdrum:RTL', hfValue)  # 'album title'
            elif hfKey in ('O', 'A'):
                # 'A' is deprecated, we will read it, but write it as 'O'
                vals = splitValues(hfValue)
                for val in vals:
                    if ';' in val or ',' in val:
                        addValue(md, 'localeOfComposition', val)
                    else:
                        addValue(md, 'countryOfComposition', val)
            elif hfKey in ('I', 'Z'):
                # These are prefixed with 'abc-something '
                vals = splitValues(hfValue)
                for val in vals:
                    abcNameAndValue = val.split(' ', 1)
                    if len(abcNameAndValue) == 1:
                        if hfKey == 'Z':
                            # no space-delimited abcName, so val is the encoder
                            addValue(md, 'electronicEncoder', val)
                            continue

                    abcName = abcNameAndValue[0]
                    if not abcName.startswith('abc'):
                        if hfKey == 'Z':
                            # no parseable abcName, so val is the encoder
                            addValue(md, 'electronicEncoder', val)
                            continue
                        if hfKey == 'I':
                            # we ignore unparseable I: abcNames because there are a lot,
                            # and they are generally not metadata.
                            continue

                    abcValue = abcNameAndValue[1]
                    if hfKey == 'Z':
                        if abcName == 'abc-transcription':
                            addValue(md, 'electronicEncoder', abcValue)
                        elif abcName == 'abc-edited-by':
                            addValue(md, 'electronicEditor', abcValue)
                        elif abcName == 'abc-copyright':
                            addValue(md, 'copyright', abcValue)
                        else:
                            addCustomValue(md, 'abc:Z:' + abcName, abcValue)
                    elif hfKey == 'I':
                        # ignore everything but 'abc-creator'; lots of non-metadata in I:
                        if abcName == 'abc-creator':
                            addValue(md, 'software', abcValue)
            else:
                pass  # print(f'need to support {hfKey}')

        return md
