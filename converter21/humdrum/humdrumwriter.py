# ------------------------------------------------------------------------------
# Name:          humdrumwriter.py
# Purpose:       HumdrumWriter is an object that takes a music21 stream and
#                writes it to a file as Humdrum data.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
from enum import IntEnum, auto
from copy import deepcopy
import typing as t

import music21 as m21
from music21.common import opFrac

from converter21.humdrum import HumdrumExportError, HumdrumInternalError
from converter21.humdrum import HumNum, HumNumIn
from converter21.humdrum import M21Convert

from converter21.humdrum import EventData
from converter21.humdrum import MeasureData, SimultaneousEvents
from converter21.humdrum import ScoreData

from converter21.humdrum import SliceType
# from converter21.humdrum import MeasureStyle
from converter21.humdrum import GridVoice
# from converter21.humdrum import GridSide
from converter21.humdrum import GridStaff
from converter21.humdrum import GridPart
from converter21.humdrum import GridSlice
from converter21.humdrum import GridMeasure
from converter21.humdrum import HumGrid

from converter21.humdrum import HumdrumToken
from converter21.humdrum import HumdrumFile
from converter21.humdrum import ToolTremolo

from converter21.shared import M21Utilities
from converter21.shared import M21StaffGroupTree

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class RepeatBracketState(IntEnum):
    NoEndings = 0
    InBracket = auto()
    FinishedBracket = auto()

class PendingOttavaStop:
    def __init__(self, tokenString: str, timestamp: HumNumIn) -> None:
        self.tokenString: str = tokenString
        self.timestamp: HumNum = opFrac(timestamp)

class HumdrumWriter:
    Debug: bool = False  # can be set to True for more debugging

    # '<>' are not considered reservable, they are hard-coded to below/above, and
    # used as such without coordination here.
    # '@' is not considered reservable (damn) because we use it in tremolos
    # (e.g. '@16@' and '@@32@@')
    _reservableRDFKernSignifiers: str = 'ijZVNl!+|'

    _m21EditorialStyleToHumdrumEditorialStyle: dict[str, str] = {
        # m21 editorial style: RDF definition string we will write
        'parentheses': 'paren',
        'bracket': 'bracket',
    }
    _humdrumEditorialStyleToFavoriteSignifier: dict[str, str] = {
        'paren': 'i',
        'bracket': 'j',
    }
    _humdrumEditorialStyleToRDFDefinitionString: dict[str, str] = {
        'paren': 'editorial accidental (paren)',
        'bracket': 'editorial accidental (bracket)',
    }

    def __init__(self, obj: m21.prebase.ProtoM21Object) -> None:
        self._m21Object: m21.prebase.ProtoM21Object = obj
        self._m21Score: m21.stream.Score | None = None
        self.spannerBundle: m21.spanner.SpannerBundle | None = None
        self._scoreData: ScoreData | None = None
        self.staffCounts: list[int] = []  # indexed by partIndex

        # default options (these can be set to non-default values by clients,
        # as long as they do it before they call write())
        # client can set to False if obj is a Score
        self.makeNotation: bool = True
        # client can set to True to add a recip spine
        self.addRecipSpine: bool = False
        # client can set to False if they want to keep the '@32@'-style
        # bowed tremolos, and the '@@16@@'-style fingered tremolos
        self.expandTremolos: bool = True
        # can be set to True for debugging output
        self.VoiceDebug: bool = False

        self._reservedRDFKernSignifiers: str = ''  # set by property, so we can vet it
        self._assignedRDFKernSignifiers: str = ''  # set internally

        # _rdfKernSignifierLookup will be computed from what is needed in the score,
        # taking into account any reservedRDFKernSignifiers set by the user
        # key: definition, value: signifier
        # definition might be a str, but can get pretty complicated...
        self._rdfKernSignifierLookup: dict[
            str | tuple[tuple[str, str | None], ...],
            str
        ] = {}

        # private data, computed along the way...
        self._forceRecipSpine: bool = False  # set to true sometimes in figured bass, harmony code
        self._hasTremolo: bool = False       # has fingered or bowed tremolo(s) that need expanding
        # current state of *tuplet/*Xtuplet (partIndex, staffIndex)
        self._tupletsSuppressed: dict[int, dict[int, bool]] = {}
        # current state of *brackettup/*Xbrackettup
        self._tupletBracketsSuppressed: dict[int, dict[int, bool]] = {}

        # temporary data (to be emitted with next durational object)
        # First elements of text tuple are part index, staff index, voice index
        self._currentTexts: list[tuple[int, int, int, m21.expressions.TextExpression]] = []
        # Dynamics are at part level in Humdrum files. But... dynamics also can be placed
        # above/below/between any of the staves in the part via things like !LO:DY:b=2, so
        # we also need a mechanism for specifying which staff it came from.
        self._currentDynamics: list[tuple[int, int, m21.dynamics.Dynamic]] = []
        # First element of tempo tuple is part index (tempo is at the part level)
        self._currentTempos: list[tuple[int, m21.tempo.TempoIndication]] = []

        # we stash any ottava stops here, to be emitted at the appropriate timestamp
        self.pendingOttavaStopsForPartAndStaff: dict[int, dict[int, list[PendingOttavaStop]]] = {}

        # whether or not we should avoid output of the first MetronomeMark (as !LO:TX or !!!OMD)
        # that matches the OMD (movementName) that was chosen to represent the temop in the
        # initial Humdrum header.
        self._waitingToMaybeSkipFirstTempoText: bool = True
        self._tempoMovementNames: list[str] = []

        # The initial OMD token that was not emitted inline, but instead will be used
        # to put the metadata.movementName back the way it was (if appropriate).
        self.initialOMDToken: str | None = None

    def tupletsSuppressed(
        self,
        partIndex: int,
        staffIndex: int,
    ) -> bool:
        if not self._tupletsSuppressed:
            return False

        partTupletsSuppressed: dict[int, bool] = (
            self._tupletsSuppressed.get(partIndex, {})
        )
        if not partTupletsSuppressed:
            return False

        staffTupletsSuppressed: bool = (
            partTupletsSuppressed.get(staffIndex, False)
        )
        return staffTupletsSuppressed

    def setTupletsSuppressed(
        self,
        partIndex: int,
        staffIndex: int,
        value: bool
    ):
        partTupletsSuppressed: dict[int, bool] = (
            self._tupletsSuppressed.get(partIndex, {})
        )
        if not partTupletsSuppressed:
            self._tupletsSuppressed[partIndex] = partTupletsSuppressed

        partTupletsSuppressed[staffIndex] = value

    def tupletBracketsSuppressed(
        self,
        partIndex: int,
        staffIndex: int,
    ) -> bool:
        if not self._tupletBracketsSuppressed:
            return False

        partTupletBracketsSuppressed: dict[int, bool] = (
            self._tupletBracketsSuppressed.get(partIndex, {})
        )
        if not partTupletBracketsSuppressed:
            return False

        staffTupletBracketsSuppressed: bool = (
            partTupletBracketsSuppressed.get(staffIndex, False)
        )
        return staffTupletBracketsSuppressed

    def setTupletBracketsSuppressed(
        self,
        partIndex: int,
        staffIndex: int,
        value: bool
    ):
        partTupletBracketsSuppressed: dict[int, bool] = (
            self._tupletBracketsSuppressed.get(partIndex, {})
        )
        if not partTupletBracketsSuppressed:
            self._tupletBracketsSuppressed[partIndex] = partTupletBracketsSuppressed

        partTupletBracketsSuppressed[staffIndex] = value

    def _chosenSignifierForRDFDefinition(
        self,
        rdfDefinition: str | tuple[tuple[str, str | None], ...],
        favoriteSignifier: str
    ) -> str:
        chosenSignifier: str | None = None
        # if we've already chosen a signifier, just return that
        chosenSignifier = self._rdfKernSignifierLookup.get(rdfDefinition, None)
        if chosenSignifier is not None:
            return chosenSignifier

        # if we can get the favorite, choose it
        if (favoriteSignifier not in self.reservedRDFKernSignifiers
                and favoriteSignifier not in self._assignedRDFKernSignifiers):
            chosenSignifier = favoriteSignifier
            self._rdfKernSignifierLookup[rdfDefinition] = chosenSignifier
            self._assignedRDFKernSignifiers += chosenSignifier
        else:
            # choose an unreserved, unassigned signifier
            for ch in self._reservableRDFKernSignifiers:
                if ch in self.reservedRDFKernSignifiers:
                    continue
                if ch in self._assignedRDFKernSignifiers:
                    continue
                chosenSignifier = ch
                self._rdfKernSignifierLookup[rdfDefinition] = chosenSignifier
                self._assignedRDFKernSignifiers += chosenSignifier
                break
            else:
                # if we couldn't find an unreserved, unassigned signifier, go ahead
                # and choose a reserved one (but print out a warning).
                for ch in self._reservableRDFKernSignifiers:
                    if ch in self._assignedRDFKernSignifiers:
                        continue
                    chosenSignifier = ch
                    self._rdfKernSignifierLookup[rdfDefinition] = chosenSignifier
                    self._assignedRDFKernSignifiers += chosenSignifier
                    print('Too many reserved RDF signifiers for this score, '
                            f'using reserved signifier \'{chosenSignifier}\' '
                            f'for \'{rdfDefinition}\'', file=sys.stderr)
                    break

        if not chosenSignifier:
            # shouldn't ever happen
            raise HumdrumInternalError('Ran out of RDF signifier chars')

        return chosenSignifier

    def reportEditorialAccidentalToOwner(self, editorialStyle: str) -> str:
        humdrumStyle: str = self._m21EditorialStyleToHumdrumEditorialStyle.get(editorialStyle, '')
        if not humdrumStyle:
            print(f'Unrecognized music21 editorial accidental style \'{editorialStyle}\': '
                    'treating as parentheses.',
                    file=sys.stderr)
            humdrumStyle = 'paren'

        rdfDefinition: str = self._humdrumEditorialStyleToRDFDefinitionString[humdrumStyle]
        favoriteSignifier: str = self._humdrumEditorialStyleToFavoriteSignifier[humdrumStyle]
        return self._chosenSignifierForRDFDefinition(rdfDefinition, favoriteSignifier)

    def reportCaesuraToOwner(self) -> str:
        rdfDefinition: str = 'caesura'
        favoriteSignifier: str = 'Z'
        return self._chosenSignifierForRDFDefinition(rdfDefinition, favoriteSignifier)

    def reportCueSizeToOwner(self) -> str:
        rdfDefinition: str = 'cue size'
        favoriteSignifier: str = '!'
        return self._chosenSignifierForRDFDefinition(rdfDefinition, favoriteSignifier)

    def reportNoteColorToOwner(self, color: str) -> str:
        # 'marked note, color=hotpink'
        rdfDefinition: tuple[tuple[str, str | None], ...] = (
            ('marked note', None),
            ('color', color),
        )
        favoriteSignifier: str = 'i'
        return self._chosenSignifierForRDFDefinition(rdfDefinition, favoriteSignifier)

    def reportLinkedSlurToOwner(self) -> str:
        rdfDefinition: str = 'linked'
        favoriteSignifier: str = 'N'
        return self._chosenSignifierForRDFDefinition(rdfDefinition, favoriteSignifier)

    @property
    def reservedRDFKernSignifiers(self) -> str:
        return self._reservedRDFKernSignifiers

    @reservedRDFKernSignifiers.setter
    def reservedRDFKernSignifiers(self, newReservedRDFKernSignifiers: str) -> None:
        if newReservedRDFKernSignifiers is None:
            self._reservedRDFKernSignifiers = ''
            return

        if not isinstance(newReservedRDFKernSignifiers, str):
            raise TypeError('reservedRDFKernSignifiers must be of type str')

        badSignifiers: str = ''
        for ch in newReservedRDFKernSignifiers:
            if ch not in self._reservableRDFKernSignifiers:
                badSignifiers += ch

        if badSignifiers:
            raise ValueError(
                f'The following signifier chars are not reservable: \'{badSignifiers}\'.\n'
                + f'Reservable signifier chars are \'{self._reservableRDFKernSignifiers}\''
            )

        self._reservedRDFKernSignifiers = newReservedRDFKernSignifiers

    def write(self, fp) -> bool:
        # First: HumdrumWriter.write likes to modify the input stream (e.g. transposing to
        # concert pitch, etc), so we need to make a copy of the input stream before we start.
        # TODO: do the transposition in Humdrum-land, following C++ code 'transpose -c'
        # (use transpose's code from humlib).  For now, go ahead and modify the input;
        # copying the whole score takes WAY too long.
        # if isinstance(self._m21Object, m21.stream.Stream):
        #     self._m21Object = self._m21Object.coreCopyAsDerivation('HumdrumWriter.write')

        # Second: turn the object into a well-formed Score (someone might have passed in a single
        # note, for example).  This code is swiped from music21 v7's musicxml exporter.  The hope
        # is that someday it will become an API in music21 that every exporter can call.
        if self.makeNotation:
            self._m21Score = M21Utilities.makeScoreFromObject(self._m21Object)
        else:
            if not isinstance(self._m21Object, m21.stream.Score):
                raise HumdrumExportError(
                    'Since makeNotation=False, source obj must be a music21 Score, and it is not.'
                )
            if not self._m21Object.isWellFormedNotation():
                print('Source obj is not well-formed; see isWellFormedNotation()', file=sys.stderr)
            self._m21Score = self._m21Object
        del self._m21Object  # everything after this uses self._m21Score

        self.spannerBundle = self._m21Score.spannerBundle

        # set up _tempoMovementNames for use when emitting the first measure (to
        # maybe skip producing '!LO:TX' from a MetronomeMark that is described
        # perfectly already by the tempo movementName/!!!OMD.
        if self._m21Score.metadata:
            movementNames: list[str] = self._m21Score.metadata['movementName']
            if movementNames:
                self._tempoMovementNames = [str(movementName) for movementName in movementNames]

        # The rest is based on Tool_musicxml2hum::convert(ostream& out, xml_document& doc)
        # 1. convert self._m21Score to HumGrid
        # 2. convert HumGrid to HumdrumFile
        # 3. write HumdrumFile to fp

        # Tool_musicxml2hum::convert loops over the parts, doing prepareVoiceMapping
        # on each one, then calls reindexVoices.

        status: bool = True
        outgrid: HumGrid = HumGrid()

        status = status and self._stitchParts(outgrid, self._m21Score)
        if not status:
            return status

        if self._scoreData is None:
            raise HumdrumInternalError('stitchParts failed, but returned True')

#         outgrid.removeRedundantClefChanges() # don't do this; not our business
#         outgrid.removeSibeliusIncipit()

        # transfer verse counts from staves to HumGrid:
        for p, partData in enumerate(self._scoreData.parts):
            for s, staffData in enumerate(partData.staves):
                verseCount: int = staffData.verseCount
                outgrid.setVerseCount(p, s, verseCount)

        # transfer harmony counts from parts to HumGrid:
        # for p, partData in enumerate(self._scoreData.parts):
        #     harmonyCount: int = partData.harmonyCount
        #     outgrid.setHarmonyCount(p, harmonyCount)

        # transfer dynamics boolean for part to HumGrid
        for p, partData in enumerate(self._scoreData.parts):
            if partData.hasDynamics:
                outgrid.setDynamicsPresent(p)

        # transfer figured bass boolean for part to HumGrid
#       for (int p=0; p<(int)partdata.size(); p++) {
#           bool fbstate = partdata[p].hasFiguredBass();
#           if (fbstate) {
#           outdata.setFiguredBassPresent(p);
#           break;
#           }
#       }

        if self.addRecipSpine or self._forceRecipSpine:
            outgrid.enableRecipSpine()

        # print(f'outgrid={outgrid}', file=sys.stderr)

        outfile: HumdrumFile = HumdrumFile()
        outgrid.transferTokens(outfile)

        self._addHeaderRecords(outfile)
        self._addFooterRecords(outfile)
        # self._addMeasureOneNumber(outfile)

        for hline in outfile.lines():
            hline.createLineFromTokens()

#         chord.run(outfile) # makes sure each note in the chord has the right stuff on it?

        # client can disable tremolo expansion by setting self.expandTremolos to False
        if self._hasTremolo and self.expandTremolos:
            # tremolos have been inserted as single tokens (or token pairs) that describe
            # the tremolo (e.g. with '@@16@@' or '@32@').  This needs to be expanded into
            # all the actual notes in the tremolo, surrounded by *tremolo/*Xtremolo to tell
            # parsers to look for spelled-out tremolos here.
            tremolo = ToolTremolo(outfile)
            tremolo.processFile()

        # TODO: Here's where we would do the Humdrum-land transpositions (if necessary)
        # TODO: ... the trick is that we need to know exactly which parts/staves to
        # TODO: ... translate, and only the music21 Score knows that. So this can't be
        # TODO: ... a HumdrumFile or HumdrumFileUtilities function, it has to be here.
        # TODO: ... Or it can be in HumdrumFile{Utilities}, but it needs to take instructions
        # TODO: ... about which parts/staves to translate (which we would compute here).
        # if self._hasTranspositions:
        #     self.transposeToConcertPitch(outfile)

        self._printResult(fp, outfile)

        return status

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::printResult -- filter out
    //      some item if not necessary:
    //
    // MuseScore calls everything "Piano" by default, so suppress
    // this instrument name if there is only one **kern spine in
    // the file.
    '''
    @staticmethod
    def _printResult(fp, outfile: HumdrumFile) -> None:
        outfile.write(fp)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addFooterRecords --
    '''
    def _addFooterRecords(self, outfile: HumdrumFile) -> None:
        for definition, signifier in self._rdfKernSignifierLookup.items():
            rdfLine = f'!!!RDF**kern: {signifier} = '
            if isinstance(definition, tuple):  # it's a tuple of k/v pairs (tuples)
                # multiple definitions: key1, key2 = value2, key3, etc...
                for i, (k, v) in enumerate(definition):
                    if i > 0:
                        rdfLine += ', '
                    if v is None:
                        rdfLine += f'{k}'
                    elif v == '':
                        rdfLine += f'{k}='
                    else:
                        rdfLine += f'{k}="{v}"'  # double quotes are required
            else:
                rdfLine += f'{definition}'
            outfile.appendLine(rdfLine, asGlobalToken=True)

        # we always export these, even if we didn't use them, since we almost always use them
        outfile.appendLine('!!!RDF**kern: > = above', asGlobalToken=True)
        outfile.appendLine('!!!RDF**kern: < = below', asGlobalToken=True)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addHeaderRecords -- Inserted in reverse order
    //      (last record inserted first).
    '''

    otherWorkIdLookupDict: dict[str, str] = {
        # 'composer': 'COM', # we do contributors NOT by workId
        'copyright': 'YEC',
        'date': 'ODT'
    }

    def _addHeaderRecords(self, outfile: HumdrumFile) -> None:
        systemDecoration: str = self._getSystemDecoration()
        if systemDecoration and systemDecoration != 's1':
            outfile.appendLine('!!!system-decoration: ' + systemDecoration, asGlobalToken=True)

        if t.TYPE_CHECKING:
            assert isinstance(self._m21Score, m21.stream.Score)

        m21Metadata: m21.metadata.Metadata = self._m21Score.metadata
#        print('metadata = \n', m21Metadata.all(), file=sys.stderr)
        if m21Metadata is None:
            return

        # get all metadata tuples (uniqueName, singleValue)
        # m21Metadata.all() returns a large tuple instead of a list, so we have to convert
        # to a list, since we want to remove things from it as we process them.
        allItems: list[tuple[str, m21.metadata.ValueType]] = list(
            m21Metadata.all(returnPrimitives=True, returnSorted=False)
        )

        # Top of Humdrum file is (in order):
        # 1. Composer name(s)
        # 2. Title(s), including alternate titles, popular titles, etc
        # 3. Movement name (should only be one, but we'll take 'em all)
        # 4. Copyright(s) including original and electronic

        def returnAndRemoveAllItemsWithUniqueName(
            allItems: list[tuple[str, m21.metadata.ValueType]],
            uniqueName: str
        ) -> list[tuple[str, m21.metadata.ValueType]]:
            # uniqueName is 0th element of tuple
            output: list[tuple[str, m21.metadata.ValueType]] = []
            for item in allItems:
                if item[0] == uniqueName:
                    output.append(item)

            for itemToRemove in output:
                allItems.remove(itemToRemove)

            return output

        mdComposerItems: list[
            tuple[str, m21.metadata.ValueType]
        ] = returnAndRemoveAllItemsWithUniqueName(allItems, 'composer')

        mdTitleItems: list[
            tuple[str, m21.metadata.ValueType]
        ] = returnAndRemoveAllItemsWithUniqueName(allItems, 'title')
        mdAlternateTitleItems: list[
            tuple[str, m21.metadata.ValueType]
        ] = returnAndRemoveAllItemsWithUniqueName(allItems, 'alternativeTitle')
        mdPopularTitleItems: list[
            tuple[str, m21.metadata.ValueType]
        ] = returnAndRemoveAllItemsWithUniqueName(allItems, 'popularTitle')
        mdParentTitleItems: list[
            tuple[str, m21.metadata.ValueType]
        ] = returnAndRemoveAllItemsWithUniqueName(allItems, 'parentTitle')
        mdGroupTitleItems: list[
            tuple[str, m21.metadata.ValueType]
        ] = returnAndRemoveAllItemsWithUniqueName(allItems, 'groupTitle')
        mdMovementNameItems: list[
            tuple[str, m21.metadata.ValueType]
        ] = returnAndRemoveAllItemsWithUniqueName(allItems, 'movementName')
        mdMovementNumberItems: list[
            tuple[str, m21.metadata.ValueType]
        ] = returnAndRemoveAllItemsWithUniqueName(allItems, 'movementNumber')

        mdCopyrightItems: list[
            tuple[str, m21.metadata.ValueType]
        ] = returnAndRemoveAllItemsWithUniqueName(allItems, 'copyright')

        # extra step: see if mdMovementNameItems[-1] matches self.initialOMDToken,
        # and if so, put any '[half-dot] = 63'-style suffix back on the
        # movementName before we emit it as the initial OMD.
        if mdMovementNameItems:
            if self.initialOMDToken is not None:
                # initialOMDToken is a str of the form '!!!OMD: blah'
                initialOMDValue: str = self.initialOMDToken[8:]
                # mdMovementNameItems[-1][1] is a Text value
                lastMovementNameStr: str = str(mdMovementNameItems[-1][1])
                if initialOMDValue.startswith(lastMovementNameStr):
                    # replace in mdMovementNameItems with a deepcopy (don't change
                    # the original metadata item!)
                    newValue = deepcopy(mdMovementNameItems[-1][1])
                    if t.TYPE_CHECKING:
                        assert isinstance(newValue, m21.metadata.Text)
                    initialOMDValue = M21Convert.translateSMUFLNotesToNoteNames(initialOMDValue)
                    newValue._data = initialOMDValue  # pylint: disable=protected-access
                    mdMovementNameItems[-1] = (mdMovementNameItems[-1][0], newValue)

        hdKeyWithoutIndexToCurrentIndex: dict = {}
        atLine: int = 0

        hdKeyWithoutIndex: str | None
        refLineStr: str | None
        idx: int

        for uniqueName, value in mdComposerItems:
            hdKeyWithoutIndex = (
                M21Convert.m21MetadataItemToHumdrumKeyWithoutIndex(uniqueName, value)
            )
            if t.TYPE_CHECKING:
                # because 'composer' has a humdrum key
                assert hdKeyWithoutIndex is not None
            idx = hdKeyWithoutIndexToCurrentIndex.get(hdKeyWithoutIndex, 0)
            hdKeyWithoutIndexToCurrentIndex[hdKeyWithoutIndex] = idx + 1  # for next time
            refLineStr = M21Convert.m21MetadataItemToHumdrumReferenceLineStr(
                idx, uniqueName, value
            )
            if refLineStr is not None:
                outfile.insertLine(atLine, refLineStr, asGlobalToken=True)
            atLine += 1

        for uniqueName, value in mdTitleItems:
            hdKeyWithoutIndex = (
                M21Convert.m21MetadataItemToHumdrumKeyWithoutIndex(uniqueName, value)
            )
            if t.TYPE_CHECKING:
                # because 'title' has a humdrum key
                assert hdKeyWithoutIndex is not None
            idx = hdKeyWithoutIndexToCurrentIndex.get(hdKeyWithoutIndex, 0)
            hdKeyWithoutIndexToCurrentIndex[hdKeyWithoutIndex] = idx + 1  # for next time
            refLineStr = M21Convert.m21MetadataItemToHumdrumReferenceLineStr(
                idx, uniqueName, value
            )
            if refLineStr is not None:
                outfile.insertLine(atLine, refLineStr, asGlobalToken=True)
            atLine += 1

        for uniqueName, value in mdAlternateTitleItems:
            hdKeyWithoutIndex = (
                M21Convert.m21MetadataItemToHumdrumKeyWithoutIndex(uniqueName, value)
            )
            if t.TYPE_CHECKING:
                # because 'alternateTitle' has a humdrum key
                assert hdKeyWithoutIndex is not None
            idx = hdKeyWithoutIndexToCurrentIndex.get(hdKeyWithoutIndex, 0)
            hdKeyWithoutIndexToCurrentIndex[hdKeyWithoutIndex] = idx + 1  # for next time
            refLineStr = M21Convert.m21MetadataItemToHumdrumReferenceLineStr(
                idx, uniqueName, value
            )
            if refLineStr is not None:
                outfile.insertLine(atLine, refLineStr, asGlobalToken=True)
            atLine += 1

        for uniqueName, value in mdPopularTitleItems:
            hdKeyWithoutIndex = (
                M21Convert.m21MetadataItemToHumdrumKeyWithoutIndex(uniqueName, value)
            )
            if t.TYPE_CHECKING:
                # because 'popularTitle' has a humdrum key
                assert hdKeyWithoutIndex is not None
            idx = hdKeyWithoutIndexToCurrentIndex.get(hdKeyWithoutIndex, 0)
            hdKeyWithoutIndexToCurrentIndex[hdKeyWithoutIndex] = idx + 1  # for next time
            refLineStr = M21Convert.m21MetadataItemToHumdrumReferenceLineStr(
                idx, uniqueName, value
            )
            if refLineStr is not None:
                outfile.insertLine(atLine, refLineStr, asGlobalToken=True)
            atLine += 1

        for uniqueName, value in mdParentTitleItems:
            hdKeyWithoutIndex = (
                M21Convert.m21MetadataItemToHumdrumKeyWithoutIndex(uniqueName, value)
            )
            if t.TYPE_CHECKING:
                # because 'parentTitle' has a humdrum key
                assert hdKeyWithoutIndex is not None
            idx = hdKeyWithoutIndexToCurrentIndex.get(hdKeyWithoutIndex, 0)
            hdKeyWithoutIndexToCurrentIndex[hdKeyWithoutIndex] = idx + 1  # for next time
            refLineStr = M21Convert.m21MetadataItemToHumdrumReferenceLineStr(
                idx, uniqueName, value
            )
            if refLineStr is not None:
                outfile.insertLine(atLine, refLineStr, asGlobalToken=True)
            atLine += 1

        for uniqueName, value in mdGroupTitleItems:
            hdKeyWithoutIndex = (
                M21Convert.m21MetadataItemToHumdrumKeyWithoutIndex(uniqueName, value)
            )
            if t.TYPE_CHECKING:
                # because 'groupTitle' has a humdrum key
                assert hdKeyWithoutIndex is not None
            idx = hdKeyWithoutIndexToCurrentIndex.get(hdKeyWithoutIndex, 0)
            hdKeyWithoutIndexToCurrentIndex[hdKeyWithoutIndex] = idx + 1  # for next time
            refLineStr = M21Convert.m21MetadataItemToHumdrumReferenceLineStr(
                idx, uniqueName, value
            )
            if refLineStr is not None:
                outfile.insertLine(atLine, refLineStr, asGlobalToken=True)
            atLine += 1

        for uniqueName, value in mdMovementNameItems:
            hdKeyWithoutIndex = (
                M21Convert.m21MetadataItemToHumdrumKeyWithoutIndex(uniqueName, value)
            )
            if t.TYPE_CHECKING:
                # because 'movementName' has a humdrum key
                assert hdKeyWithoutIndex is not None
            idx = 0
#             idx = hdKeyWithoutIndexToCurrentIndex.get(hdKeyWithoutIndex, 0)
#             hdKeyWithoutIndexToCurrentIndex[hdKeyWithoutIndex] = idx + 1  # for next time
            refLineStr = M21Convert.m21MetadataItemToHumdrumReferenceLineStr(
                idx, uniqueName, value
            )
            if refLineStr is not None:
                outfile.insertLine(atLine, refLineStr, asGlobalToken=True)
            atLine += 1

        for uniqueName, value in mdMovementNumberItems:
            hdKeyWithoutIndex = (
                M21Convert.m21MetadataItemToHumdrumKeyWithoutIndex(uniqueName, value)
            )
            if t.TYPE_CHECKING:
                # because 'movementNumber' has a humdrum key
                assert hdKeyWithoutIndex is not None
            idx = hdKeyWithoutIndexToCurrentIndex.get(hdKeyWithoutIndex, 0)
            hdKeyWithoutIndexToCurrentIndex[hdKeyWithoutIndex] = idx + 1  # for next time
            refLineStr = M21Convert.m21MetadataItemToHumdrumReferenceLineStr(
                idx, uniqueName, value
            )
            if refLineStr is not None:
                outfile.insertLine(atLine, refLineStr, asGlobalToken=True)
            atLine += 1

        for uniqueName, value in mdCopyrightItems:
            hdKeyWithoutIndex = (
                M21Convert.m21MetadataItemToHumdrumKeyWithoutIndex(uniqueName, value)
            )
            if t.TYPE_CHECKING:
                # because 'copyright' has a humdrum key
                assert hdKeyWithoutIndex is not None
            idx = hdKeyWithoutIndexToCurrentIndex.get(hdKeyWithoutIndex, 0)
            hdKeyWithoutIndexToCurrentIndex[hdKeyWithoutIndex] = idx + 1  # for next time
            refLineStr = M21Convert.m21MetadataItemToHumdrumReferenceLineStr(
                idx, uniqueName, value
            )
            if refLineStr is not None:
                outfile.insertLine(atLine, refLineStr, asGlobalToken=True)
            atLine += 1

        # what's left in allItems goes at the bottom of the file
        for uniqueName, value in allItems:
            if (uniqueName.startswith('humdrumraw:')
                    or uniqueName.startswith('humdrum:')
                    or uniqueName.startswith('raw:')):
                refLineStr = M21Convert.m21MetadataItemToHumdrumReferenceLineStr(
                    0, uniqueName, value
                )
            else:
                nsName: str | None = m21Metadata.uniqueNameToNamespaceName(uniqueName)
                if nsName and nsName.startswith('m21FileInfo:'):
                    # We don't write fileInfo (which is about the original file, not the one we're
                    # writing) to the output Humdrum file.
                    continue
                refLineStr = None
                hdKeyWithoutIndex = None

                if uniqueName == 'otherContributor':
                    # See if we can make a valid humdrum key out of the contributor role.
                    if t.TYPE_CHECKING:
                        assert isinstance(value, m21.metadata.Contributor)
                    hdKeyWithoutIndex = (
                        M21Utilities.contributorRoleToHumdrumReferenceKey(value.role)
                    )
                    if hdKeyWithoutIndex is not None:
                        idx = hdKeyWithoutIndexToCurrentIndex.get(hdKeyWithoutIndex, 0)
                        hdKeyWithoutIndexToCurrentIndex[
                            hdKeyWithoutIndex] = idx + 1  # for next time
                        refLineStr = M21Convert.humdrumMetadataItemToHumdrumReferenceLineStr(
                            idx, hdKeyWithoutIndex, value
                        )
                    if refLineStr is not None:
                        outfile.appendLine(refLineStr, asGlobalToken=True)
                        continue

                hdKeyWithoutIndex = (
                    M21Convert.m21MetadataItemToHumdrumKeyWithoutIndex(uniqueName, value)
                )

                if hdKeyWithoutIndex is not None:
                    idx = hdKeyWithoutIndexToCurrentIndex.get(hdKeyWithoutIndex, 0)
                    hdKeyWithoutIndexToCurrentIndex[hdKeyWithoutIndex] = idx + 1  # for next time
                    refLineStr = M21Convert.m21MetadataItemToHumdrumReferenceLineStr(
                        idx, uniqueName, value
                    )
                else:
                    refLineStr = M21Convert.m21MetadataItemToHumdrumReferenceLineStr(
                        0, uniqueName, value
                    )
            if refLineStr is not None:
                outfile.appendLine(refLineStr, asGlobalToken=True)

    def _getSystemDecoration(self) -> str:
        output: str = ''

        # Find all the StaffGroups in the score, and use sg.spannerStorage.elements (the parts)
        # as well as sg.symbol and sg.barTogether from each one to generate a 'sN'-based
        # system-decoration string.
        if t.TYPE_CHECKING:
            assert isinstance(self._scoreData, ScoreData)
            assert isinstance(self.spannerBundle, m21.spanner.SpannerBundle)
        staffNumbersByM21Part: dict[m21.stream.Part, int] = (
            self._getGlobalStaffNumbersForM21Parts(self._scoreData)
        )
        staffGroups: list[m21.layout.StaffGroup] = (
            list(self.spannerBundle.getByClass(m21.layout.StaffGroup))
        )
        staffGroupTrees: list[M21StaffGroupTree] = (
            M21Utilities.getStaffGroupTrees(staffGroups, staffNumbersByM21Part)
        )

        for sgtree in staffGroupTrees:
            output, _ = self._appendRecursiveDecoString(output, sgtree)

        return output

    @staticmethod
    def _appendRecursiveDecoString(
        output: str,
        sgtree: M21StaffGroupTree
    ) -> tuple[str, list[int]]:
        if sgtree is None:
            return (output, [])
        if sgtree.numStaves == 0:
            return (output, [])

        preString: str = ''
        postString: str = ''
        symbol: str = sgtree.staffGroup.symbol
        barTogether: bool | str = sgtree.staffGroup.barTogether  # might be 'mensurstrich'

        if symbol in M21Convert.m21GroupSymbolToHumdrumDecoGroupStyleStart:
            preString += M21Convert.m21GroupSymbolToHumdrumDecoGroupStyleStart[symbol]
            postString = M21Convert.m21GroupSymbolToHumdrumDecoGroupStyleStop[symbol] + postString

        if barTogether:  # 'mensurstrich' will evaluate to True, which is OK...
            preString += '('
            postString = ')' + postString

        output += preString

        sortedStaffNums: list[int] = sorted(list(sgtree.staffNums))
        staffNumsToProcess: set[int] = set(sortedStaffNums)
        staffNums: list[int] = []

        for subgroup in sgtree.children:
            lowestStaffNumInSubgroup: int = min(subgroup.staffNums)

            # 1. any staffNums before this subgroup
            for i, staffNum in enumerate(sortedStaffNums):
                if staffNum >= lowestStaffNumInSubgroup:
                    # we're done with staffNums before this subgroup
                    break

                if staffNum not in staffNumsToProcess:
                    # we already did this one
                    continue

                if i > 0:
                    output += ','
                output += 's' + str(staffNum)
                staffNumsToProcess.remove(staffNum)
                staffNums.append(staffNum)

            # 2. now the subgroup (adds more text to output)
            output, newStaffNums = HumdrumWriter._appendRecursiveDecoString(output, subgroup)
            staffNumsProcessed: set[int] = set(newStaffNums)  # for speed of "in" checking
            staffNumsToProcess = set(num for num in staffNumsToProcess
                                            if num not in staffNumsProcessed)
            staffNums += newStaffNums


        # 3. any staffNums at the end after all the subgroups
        for i, staffNum in enumerate(sorted(list(staffNumsToProcess))):
            if i > 0:
                output += ','
            output += 's' + str(staffNum)
            staffNumsToProcess.remove(staffNum)
            staffNums.append(staffNum)

        output += postString

        return (output, staffNums)

    @staticmethod
    def _getGlobalStaffNumbersForM21Parts(scoreData: ScoreData) -> dict[m21.stream.Part, int]:
        output: dict[m21.stream.Part, int] = {}
        staffNumber: int = 0  # global staff numbers are 1-based
        for partData in scoreData.parts:
            for staffData in partData.staves:
                staffNumber += 1  # global staff numbers are 1-based
                output[staffData.m21PartStaff] = staffNumber
        return output

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::stitchParts -- Merge individual parts into a
    //     single score sequence.
    '''
    def _stitchParts(self, outgrid: HumGrid, score: m21.stream.Score) -> bool:
        # First, count parts (and each part's measures)
        partCount: int = 0
        measureCount: list[int] = []
        for part in score.parts:  # includes PartStaffs, too
            partCount += 1
            measureCount.append(0)
            for _ in part.getElementsByClass('Measure'):
                measureCount[-1] += 1

        if partCount == 0:
            return False

        mCount0 = measureCount[0]
        for mCount in measureCount:
            if mCount != mCount0:
                raise HumdrumExportError(
                    'ERROR: cannot handle parts with different measure counts'
                )

        self._scoreData = ScoreData(score, self)

        self.staffCounts = self._scoreData.getStaffCounts()

        # Now insert each measure into the HumGrid across those parts/staves
        status: bool = True
        for m in range(0, mCount0):
            status = status and self._insertMeasure(outgrid, m)

        self._moveBreaksToEndOfPreviousMeasure(outgrid)
        self._insertRepeatBracketSlices(outgrid)
        self._insertPartNames(outgrid)

        return status

    @staticmethod
    def _fillAllVoicesInSlice(gridSlice: GridSlice, string: str) -> None:
        durationZero: HumNum = opFrac(0)

        for part in gridSlice.parts:
            for staff in part.staves:
                if staff is None:
                    raise HumdrumInternalError(
                        'staff is None in HumdrumWriter._fillAllVoicesInSlice'
                    )

                voiceCount: int = len(staff.voices)
                if voiceCount == 0:
                    staff.voices.append(GridVoice(string, durationZero))
                    continue

                for v, gv in enumerate(staff.voices):
                    if gv is None:
                        gv = GridVoice(string, durationZero)
                        staff.voices[v] = gv
                    elif gv.token is None:
                        gv.token = HumdrumToken(string)
                    else:
                        raise HumdrumInternalError(
                            'gv.token is not None in HumdrumWriter._fillAllVoicesInSlice'
                        )

    @staticmethod
    def _insertSectionNameSlice(outgm: GridMeasure, string: str):
        firstDataIdx: int = 0  # if we find no data, we'll just insert before idx 0
        for i, gridSlice in enumerate(outgm.slices):
            if gridSlice.isDataSlice:
                firstDataIdx = i
                break

        firstDataSlice: GridSlice = outgm.slices[firstDataIdx]
        sectionNameSlice: GridSlice = GridSlice(
            outgm, firstDataSlice.timestamp, SliceType.SectionNames
        )

        sectionNameSlice.initializeBySlice(firstDataSlice)
        HumdrumWriter._fillAllVoicesInSlice(sectionNameSlice, string)
        outgm.slices.insert(firstDataIdx, sectionNameSlice)

    @staticmethod
    def _insertRepeatBracketSlices(outgrid: HumGrid) -> None:
        if not outgrid.hasRepeatBrackets:
            return

        def incrementName(sectionName: str) -> str:
            # 'A' ... 'Z', 'AA' ... 'ZZ', 'AAA' .. 'ZZZ', etc
            if not sectionName or sectionName[0] not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                raise HumdrumInternalError('invalid section name generated')

            oldFirstChar: str = sectionName[0]
            for c in sectionName[1:]:
                if c != oldFirstChar:
                    raise HumdrumInternalError('invalid section name generated')

            # wraparound case
            if oldFirstChar == 'Z':
                # 'Z' -> 'AA', 'ZZ' -> 'AAA', etc
                return 'A' * (len(sectionName) + 1)

            # regular case
            newFirstChar: str = chr(ord(oldFirstChar) + 1)
            return newFirstChar * len(sectionName)

        def startBracket(
            sectionName: str,
            bracketName: str,
            fallbackNumber: int,  # use then increment if bracketName is not str(int)
            gm: GridMeasure,
        ) -> int:
            bracketNumber: int
            try:
                bracketNumber = int(bracketName)
            except ValueError:
                bracketNumber = fallbackNumber

            HumdrumWriter._insertSectionNameSlice(gm, f'*>{sectionName}{bracketNumber}')
            return bracketNumber + 1

        def startSection(
            sectionName: str,
            gm: GridMeasure
        ) -> None:
            HumdrumWriter._insertSectionNameSlice(gm, f'*>{sectionName}')

        # the suffix of a bracket's section name in a Humdrum file must be numeric
        # if the bracket name is not numeric, just use 1, 2, 3 instead (it ain't
        # right, but it's better than no bracket at all).
        fallbackNumber: int = 1
        currSectionName: str = 'A'
        state: RepeatBracketState = RepeatBracketState.NoEndings

        for m, gm in enumerate(outgrid.measures):
            if m == 0:
                # Since we know there are repeat brackets, we must start section A
                # before anything, or *>A1 will not be recognized as an ending
                # emit '*>A' (where A is currSectionName)
                startSection(currSectionName, gm)

            if state == RepeatBracketState.NoEndings and not gm.inRepeatBracket:
                # this is almost always true: we're not currently within repeat
                # brackets and this measure isn't in one either.  Get out quick
                # to avoid the state machine gauntlet.
                continue

            # state machine
            if state == RepeatBracketState.NoEndings:
                if gm.startsRepeatBracket and gm.stopsRepeatBracket:
                    # start the first bracket and say it's finished
                    fallbackNumber = startBracket(
                        currSectionName, gm.repeatBracketName, 1, gm
                    )
                    state = RepeatBracketState.FinishedBracket
                elif gm.startsRepeatBracket:
                    # start the first bracket and say it's not finished
                    fallbackNumber = startBracket(
                        currSectionName, gm.repeatBracketName, 1, gm
                    )
                    state = RepeatBracketState.InBracket
                elif gm.stopsRepeatBracket:
                    # illegal, but we will treat it like a start/stop,
                    # even though there was no start.
                    # start the first bracket and say it's finished
                    fallbackNumber = startBracket(
                        currSectionName, gm.repeatBracketName, 1, gm
                    )
                    state = RepeatBracketState.FinishedBracket
                elif gm.inRepeatBracket:
                    # illegal, but we will treat it like a start,
                    # even though there was no start.
                    # start the first bracket and say it's not finished
                    fallbackNumber = startBracket(
                        currSectionName, gm.repeatBracketName, 1, gm
                    )
                    state = RepeatBracketState.InBracket
#               else:  # not gm.inRepeatBracket
#                   # This won't happen, we already handled it before the state machine code.
#                   state = RepeatBracketState.NoEndings

            elif state == RepeatBracketState.InBracket:
                if gm.startsRepeatBracket and gm.stopsRepeatBracket:
                    # illegal, but we will treat it like a stopsRepeatBracket
                    # say it's finished
                    state = RepeatBracketState.FinishedBracket
                elif gm.startsRepeatBracket:
                    # illegal, but we will fake a stop to make it legal.
                    # InBracket + stopsRepeatBracket -> FinishedBracket
                    # FinishedBracket + startsRepeatBracket does:
                    # start a bracket, and say it's not finished
                    fallbackNumber = startBracket(
                        currSectionName, gm.repeatBracketName, fallbackNumber, gm
                    )
                    state = RepeatBracketState.InBracket
                elif gm.stopsRepeatBracket:
                    # say it's finished
                    state = RepeatBracketState.FinishedBracket
                elif gm.inRepeatBracket:
                    # say it's still not finished
                    state = RepeatBracketState.InBracket
                else:  # not gm.inRepeatBracket:
                    # illegal, but we will fake a stop to make it legal.
                    # InBracket + stopsRepeatBracket -> FinishedBracket
                    # FinishedBracket + not inRepeatBracket does:
                    # start the next section, these endings are done
                    currSectionName = incrementName(currSectionName)
                    startSection(currSectionName, gm)
                    state = RepeatBracketState.NoEndings

            elif state == RepeatBracketState.FinishedBracket:
                if gm.startsRepeatBracket and gm.stopsRepeatBracket:
                    # start a non-first bracket and say it's finished
                    fallbackNumber = startBracket(
                        currSectionName, gm.repeatBracketName, fallbackNumber, gm
                    )
                    state = RepeatBracketState.FinishedBracket
                elif gm.startsRepeatBracket:
                    # start a non-first bracket and say it's not finished
                    fallbackNumber = startBracket(
                        currSectionName, gm.repeatBracketName, fallbackNumber, gm
                    )
                    state = RepeatBracketState.InBracket
                elif gm.stopsRepeatBracket:
                    # illegal, but we will treat it like a start/stop,
                    # even though there was no start.
                    # start a non-first bracket and say it's finished
                    fallbackNumber = startBracket(
                        currSectionName, gm.repeatBracketName, fallbackNumber, gm
                    )
                    state = RepeatBracketState.FinishedBracket
                elif gm.inRepeatBracket:
                    # illegal, but we will treat it like a start,
                    # even though there was no start.
                    # start a non-first bracket and say it's not finished
                    fallbackNumber = startBracket(
                        currSectionName, gm.repeatBracketName, fallbackNumber, gm
                    )
                    state = RepeatBracketState.InBracket
                else:  # not gm.inRepeatBracket:
                    # start the next section, these endings are done
                    currSectionName = incrementName(currSectionName)
                    startSection(currSectionName, gm)
                    state = RepeatBracketState.NoEndings

    '''
    //////////////////////////////
    //
    // moveBreaksToEndOfPreviousMeasure --
    '''
    @staticmethod
    def _moveBreaksToEndOfPreviousMeasure(outgrid: HumGrid) -> None:
        for m in range(1, len(outgrid.measures)):
            gm: GridMeasure = outgrid.measures[m]
            gmlast: GridMeasure = outgrid.measures[m - 1]
            if gm is None or gmlast is None:
                continue

            if not gm.slices:
                # empty measure
                return

            startTime: HumNum = gm.slices[0].timestamp
            for sliceIdx, gridSlice in enumerate(gm.slices):
                time2: HumNum = gridSlice.timestamp
                if time2 > startTime:
                    break

                if not gridSlice.isGlobalComment:
                    continue

                voice0: GridVoice | None = gridSlice.parts[0].staves[0].voices[0]
                if voice0 is None:
                    continue
                token: HumdrumToken | None = voice0.token
                if token is None:
                    continue

                if token.text in ('!!LO:LB:g=z', '!!LO:PB:g=z'):
                    gmlast.slices.append(gridSlice)
                    gm.slices.pop(sliceIdx)
                    # there can be only one break, so quit the slice loop now.
                    break

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::insertPartNames --
    '''
    def _insertPartNames(self, outgrid: HumGrid) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(self._scoreData, ScoreData)

        hasAbbr: bool = False
        hasName: bool = False

        for partData in self._scoreData.parts:
            if partData.partName:
                hasName = True
                break

        for partData in self._scoreData.parts:
            if partData.partAbbrev:
                hasAbbr = True
                break

        if not hasAbbr and not hasName:
            return

        gm: GridMeasure
        if not outgrid.measures:
            gm = GridMeasure(outgrid)
            outgrid.measures.append(gm)
        else:
            gm = outgrid.measures[0]

        # We do abbreviation first, since addLabelAbbrToken and addLabelToken put the
        # token as early in the measure as possible, so the order will be reversed.
        maxStaff: int
        s: int
        v: int
        if hasAbbr:
            for p, partData in enumerate(self._scoreData.parts):
                partAbbr: str = partData.partAbbrev
                if not partAbbr:
                    continue
                abbr: str = "*I'" + partAbbr
                maxStaff = outgrid.staffCount(p)
                s = maxStaff - 1  # put it in last staff (which is first on the Humdrum line)
                v = 0  # voice 0
                gm.addLabelAbbrToken(abbr, 0, p, s, v, self.staffCounts)

        if hasName:
            for p, partData in enumerate(self._scoreData.parts):
                partName: str = partData.partName
                if not partName:
                    continue
                if 'MusicXML' in partName:
                    # ignore Finale dummy part names
                    continue
                if 'Part_' in partName:
                    # ignore SharpEye dummy part names
                    continue
                if 'Unnamed' in partName:
                    # ignore Sibelius dummy part names
                    continue
                iname: str = '*I"' + partName
                maxStaff = outgrid.staffCount(p)
                s = maxStaff - 1  # put it in last staff (which is first on the Humdrum line)
                v = 0  # voice 0
                gm.addLabelToken(iname, 0, p, s, v, self.staffCounts)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::insertMeasure --
    '''
    def _insertMeasure(self, outgrid: HumGrid, mIndex: int) -> bool:
        if t.TYPE_CHECKING:
            assert isinstance(self._scoreData, ScoreData)

        gm: GridMeasure = outgrid.appendMeasure()

        measureDatas: list[MeasureData] = []
        sevents: list[list[SimultaneousEvents]] = []

        for p, part in enumerate(self._scoreData.parts):
            for s, staff in enumerate(part.staves):
                xmeasure: MeasureData = staff.measures[mIndex]
                measureDatas.append(xmeasure)
                if p == 0 and s == 0:
                    gm.duration = xmeasure.duration
                    gm.timestamp = xmeasure.startTime
                    gm.timeSigDur = xmeasure.timeSigDur
                # self._checkForDummyRests(xmeasure) # handled in MeasureData
                sevents.append(xmeasure.sortedEvents)
                if p == 0 and s == 0:
                    # only checking number of first barline
                    gm.measureNumberString = xmeasure.measureNumberString  # might be '124a'

                # styles, on the other hand, need to be checked in every staff
                gm.leftBarlineStylePerStaff.append(xmeasure.leftBarlineStyle)
                gm.rightBarlineStylePerStaff.append(xmeasure.rightBarlineStyle)
                gm.measureStylePerStaff.append(xmeasure.measureStyle)
                gm.fermataStylePerStaff.append(xmeasure.fermataStyle)
                gm.rightBarlineFermataStylePerStaff.append(xmeasure.rightBarlineFermataStyle)

                # repeat brackets
                gm.inRepeatBracket = xmeasure.inRepeatBracket
                gm.startsRepeatBracket = xmeasure.startsRepeatBracket
                gm.stopsRepeatBracket = xmeasure.stopsRepeatBracket
                gm.repeatBracketName = xmeasure.repeatBracketName
                if gm.inRepeatBracket:
                    outgrid.hasRepeatBrackets = True

        curTime: list[HumNum] = [opFrac(-1)] * len(measureDatas)
        measureDurs: list[HumNum | None] = [None] * len(measureDatas)
        curIndex: list[int] = [0] * len(measureDatas)
        nextTime: HumNum = opFrac(-1)

        tsDur: HumNum = opFrac(-1)
        for ps, mdata in enumerate(measureDatas):
            events: list[EventData] = mdata.events
            # Keep track of hairpin endings that should be attached
            # the the previous note (and doubling the ending marker
            # to indicate that the timestamp of the ending is at the
            # end rather than the start of the note.
            #   I think this is a no-op for music21 input. --gregc

            if self.VoiceDebug:
                for event in events:
                    print('!!ELEMENT: ', end='', file=sys.stderr)
                    print(f'\tTIME:  {event.startTime}', end='', file=sys.stderr)
                    print(f'\tSTi:   {event.staffIndex}', end='', file=sys.stderr)
                    print(f'\tVi:    {event.voiceIndex}', end='', file=sys.stderr)
                    print(f'\tDUR:   {event.duration}', end='', file=sys.stderr)
                    print(f'\tTOKEN: {event.kernTokenString()}',
                                end='', file=sys.stderr)
                    print(f'\tNAME:  {event.name}', end='', file=sys.stderr)
                    print('', file=sys.stderr)  # line feed (one line per event)
                print('======================================', file=sys.stderr)

            if sevents[ps]:
                curTime[ps] = sevents[ps][curIndex[ps]].startTime
            else:
                curTime[ps] = tsDur
            if nextTime < 0:
                nextTime = curTime[ps]
            elif curTime[ps] < nextTime:
                nextTime = curTime[ps]

            measureDurs[ps] = mdata.duration
        # end of loop over parts' staves' measures at measure # mIndex

        allEnd: bool = False
        nowEvents: list[SimultaneousEvents] = []
#         nowPartStaves: list[int] = []
        status: bool = True

        # Q: I believe the following loop is trying to process nowEvents for each "now" in
        # Q: ... time order.  But it doesn't actually get time order right, so instead I
        # Q: ... made sure that any MeasureData's sortedEvents are actually sorted by time
        # Q: ... instead of just binned by time (with the bins not necessarily in order).
        # Q: ... I did this by using a sorted list (with no duplicates) instead of a set
        # Q: ... in MeasureData._sortEvents().
        # Q: ... Things come out here in time order now, but I'm still confused by this loop,
        # Q: ... so I don't dare simplify it yet (by assuming that sortedEvents are in order).
        processTime: HumNum = nextTime
        while not allEnd:
            nowEvents = []
#             nowPartStaves = []
            allEnd = True
            processTime = nextTime
            nextTime = opFrac(-1)
            for ps in reversed(range(0, len(measureDatas))):
                if curIndex[ps] >= len(sevents[ps]):
                    continue

                if sevents[ps][curIndex[ps]].startTime == processTime:
                    thing: SimultaneousEvents = sevents[ps][curIndex[ps]]
                    nowEvents.append(thing)
#                     nowPartStaves.append(ps)
                    curIndex[ps] += 1

                if curIndex[ps] < len(sevents[ps]):
                    allEnd = False
                    if nextTime < 0 or sevents[ps][curIndex[ps]].startTime < nextTime:
                        nextTime = sevents[ps][curIndex[ps]].startTime
            # end reversed loop over parts
            status = status and self._convertNowEvents(gm, nowEvents, processTime)
        # end loop over slices (i.e. events in the measure across all partstaves)

        if self._currentTexts or self._currentDynamics or self._currentTempos:
            # one more _addEvent (no slice, no event) to flush out these
            # things that have to be exported as a side-effect of the next
            # durational event (but we've hit end of measure, so there is
            # no such event to process, unless we're willing to let them
            # move to the next measure... which we are NOT).
            self._addEvent(None, gm, None, processTime)

        # if self._offsetHarmony:
            # self._insertOffsetHarmonyIntoMeasure(gm)
        # if self._offsetFiguredBass:
            # self._insertOffsetFiguredBassIntoMeasure(gm)

        return status

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::convertNowEvents --
    '''
    def _convertNowEvents(
        self,
        outgm: GridMeasure,
        nowEvents: list[SimultaneousEvents],
        nowTime: HumNumIn
    ) -> bool:
        if not nowEvents:
            # print('NOW EVENTS ARE EMPTY', file=sys.stderr)
            return True

        self._appendZeroDurationEvents(outgm, nowEvents, nowTime)

        # I have run into cases where nowEvents[0] hasn't any duration events,
        # but nowEvents[1] has them.  We need to check all of them, not just
        # nowEvents[0]
        weHaveDurationEvents: bool = False
        for ne in nowEvents:
            if ne.nonZeroDur:
                weHaveDurationEvents = True
                break

        if not weHaveDurationEvents:
            # no duration events (should be a terminal barline)
            # ignore and deal with in calling function
            return True

        self._appendNonZeroDurationEvents(outgm, nowEvents, nowTime)
        return True

    '''
    /////////////////////////////
    //
    // Tool_musicxml2hum::appendZeroEvents --
    '''
    def _appendZeroDurationEvents(
        self,
        outgm: GridMeasure,
        nowEvents: list[SimultaneousEvents],
        nowTime: HumNumIn
    ) -> None:

        if t.TYPE_CHECKING:
            assert isinstance(self._scoreData, ScoreData)

        hasClef: bool = False
        hasKeySig: bool = False
        hasKeyDesignation: bool = False
        hasTransposition: bool = False
        hasTimeSig: bool = False
#        hasOttava: bool = False
        hasStaffLines: bool = False

        # These are all indexed by part, and include a staff index with each element
        # Some have further indexes for voice, and maybe note
        clefs: list[list[tuple[int, m21.clef.Clef]]] = []
        keySigs: list[list[tuple[int, m21.key.KeySignature]]] = []
        timeSigs: list[list[tuple[int, m21.meter.TimeSignature]]] = []
        staffLines: list[list[tuple[int, int]]] = []  # number of staff lines (if specified)
        transposingInstruments: list[list[tuple[int, m21.instrument.Instrument]]] = []
#        hairPins: list[list[m21.dynamics.DynamicWedge]] = []
#        ottavas: list[list[list[m21.spanner.Ottava]]] = []

        graceBefore: list[list[list[list[EventData]]]] = []
        graceAfter: list[list[list[list[EventData]]]] = []
        foundNonGrace: bool = False

        # pre-populate the top level list with an empty list for each part
        for _ in range(0, len(self._scoreData.parts)):
            clefs.append([])
            keySigs.append([])
            timeSigs.append([])
            staffLines.append([])
            transposingInstruments.append([])
#            hairPins.append([])
#            ottavas.append([])
            graceBefore.append([])
            graceAfter.append([])

        for simultaneousEventList in nowEvents:
            for zeroDurEvent in simultaneousEventList.zeroDur:
                m21Obj: m21.base.Music21Object = zeroDurEvent.m21Object  # getNode
                pindex: int = zeroDurEvent.partIndex
                sindex: int = zeroDurEvent.staffIndex
                vindex: int = zeroDurEvent.voiceIndex

                if isinstance(m21Obj, m21.clef.Clef):
                    clefs[pindex].append((sindex, m21Obj))
                    hasClef = True
                    foundNonGrace = True
                elif isinstance(m21Obj, (m21.key.Key, m21.key.KeySignature)):
                    keySigs[pindex].append((sindex, m21Obj))
                    hasKeySig = True
                    hasKeyDesignation = 'Key' in m21Obj.classes
                    foundNonGrace = True
                elif isinstance(m21Obj, m21.instrument.Instrument):
                    if M21Utilities.isTransposingInstrument(m21Obj):
                        transposingInstruments[pindex].append((sindex, m21Obj))
                        hasTransposition = True
                        foundNonGrace = True
                elif isinstance(m21Obj, m21.layout.StaffLayout):
                    if m21Obj.staffLines is not None:
                        staffLines[pindex].append((sindex, m21Obj.staffLines))
                        hasStaffLines = True
                        foundNonGrace = True
                elif isinstance(m21Obj, m21.meter.TimeSignature):
                    timeSigs[pindex].append((sindex, m21Obj))
                    hasTimeSig = True
                    hasMeterSig = M21Utilities.hasMeterSymbol(m21Obj)
                    foundNonGrace = True
                elif isinstance(m21Obj, m21.expressions.TextExpression):
                    # put in self._currentTexts, so it can be emitted
                    # during the immediately following call to
                    # appendNonZeroEvents() -> addEvent()
                    self._currentTexts.append((pindex, sindex, vindex, m21Obj))
                elif isinstance(m21Obj, m21.tempo.MetronomeMark):
                    # if we haven't done this yet, check if mm text matches the first movement
                    # name (OMD) and if so, make a note to skip the tempo text output (!LO:TX) as
                    # redundant with first OMD.
                    # We will still output the *MM as appropriate.
                    if self._waitingToMaybeSkipFirstTempoText:
                        self._waitingToMaybeSkipFirstTempoText = False
                        for movementName in self._tempoMovementNames:
                            if m21Obj.text is not None and movementName in m21Obj.text:
                                m21Obj.humdrumTempoIsFromInitialOMD = True  # type: ignore
                                break
                    self._currentTempos.append((pindex, m21Obj))
                elif isinstance(m21Obj, m21.dynamics.Dynamic):
                    self._currentDynamics.append((pindex, sindex, m21Obj))
                    zeroDurEvent.reportDynamicToOwner()
#                 elif 'FiguredBass' in m21Obj.classes:
#                     self._currentFiguredBass.append(m21Obj)
                elif isinstance(m21Obj, m21.note.GeneralNote):
                    if isinstance(m21Obj.duration,
                            (m21.duration.GraceDuration, m21.duration.AppoggiaturaDuration)):
                        if foundNonGrace:
                            self._addEventToList(graceAfter, zeroDurEvent)
                        else:
                            self._addEventToList(graceBefore, zeroDurEvent)
                    else:
                        # this is a zero-duration GeneralNote, but not a gracenote.
                        # Just ignore it; it's only here to be in a Spanner (like
                        # DynamicWedge), and we've already handled that.
                        pass
                elif isinstance(m21Obj, (m21.layout.PageLayout, m21.layout.SystemLayout)):
                    self._processPrintElement(outgm, m21Obj, nowTime)
                # elif isinstance(m21Obj, m21.spanner.SpannerAnchor):
                #     # Just ignore it; it's only here to be in a Spanner (like DynamicWedge),
                #     # and we've already handled that.
                #    pass

        self._addGraceLines(outgm, graceBefore, nowTime)

        if hasStaffLines:
            self._addStriaLine(outgm, staffLines, nowTime)

        if hasClef:
            self._addClefLine(outgm, clefs, nowTime)

        if hasTransposition:
            self._addTranspositionLine(outgm, transposingInstruments, nowTime)

        if hasKeySig:
            self._addKeySigLine(outgm, keySigs, nowTime, hasKeyDesignation)

        if hasTimeSig:
            self._addTimeSigLine(outgm, timeSigs, nowTime, hasMeterSig)

#         if hasOttava:
#             self._addOttavaLine(outgm, ottavas, nowTime)

        self._addGraceLines(outgm, graceAfter, nowTime)

    '''
    ///////////////////////////////
    //
    // Tool_musicxml2hum::addEventToList --
    '''
    @staticmethod
    def _addEventToList(
        eventList: list[list[list[list[EventData]]]],
        event: EventData
    ) -> None:
        p: int = event.partIndex
        s: int = event.staffIndex
        v: int = event.voiceIndex

        # make sure we have enough part lists in the list
        if p >= len(eventList):
            additionalPartsNeeded: int = p + 1 - len(eventList)
            for _ in range(0, additionalPartsNeeded):
                eventList.append([])

        # make sure we have enough staff lists in the part list
        if s >= len(eventList[p]):
            additionalStavesNeeded: int = s + 1 - len(eventList[p])
            for _ in range(0, additionalStavesNeeded):
                eventList[p].append([])

        # make sure we have enough voice lists in the staff list
        if v >= len(eventList[p][s]):
            additionalVoicesNeeded: int = v + 1 - len(eventList[p][s])
            for _ in range(0, additionalVoicesNeeded):
                eventList[p][s].append([])

        # append event to the voice list
        eventList[p][s][v].append(event)

    '''
    ///////////////////////////////
    //
    // Tool_musicxml2hum::addGraceLines -- Add grace note lines.  The number of
    //     lines is equal to the maximum number of successive grace notes in
    //     any part.  Grace notes are filled in reverse sequence.
    '''
    def _addGraceLines(
        self,
        outgm: GridMeasure,
        notes: list[list[list[list[EventData]]]],
        nowTime: HumNumIn
    ) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(self._scoreData, ScoreData)

        maxGraceNoteCount: int = 0
        for staffList in notes:  # notes is a list of staffLists, one staffList per part
            for voiceList in staffList:
                for noteList in voiceList:
                    if maxGraceNoteCount < len(noteList):
                        maxGraceNoteCount = len(noteList)

        if maxGraceNoteCount == 0:
            return

        slices: list[GridSlice] = []
        for _ in range(0, maxGraceNoteCount):
            slices.append(GridSlice(outgm, nowTime, SliceType.GraceNotes, self.staffCounts))
            outgm.slices.append(slices[-1])

        for staffList in notes:  # notes is a list of staffLists, one staffList per part
            for voiceList in staffList:
                for noteList in voiceList:
                    startn: int = maxGraceNoteCount - len(noteList)
                    for n, note in enumerate(noteList):
                        self._addEvent(slices[startn + n], outgm, note, nowTime)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addClefLine --
    '''
    def _addClefLine(
        self,
        outgm: GridMeasure,
        clefs: list[list[tuple[int, m21.clef.Clef]]],
        nowTime: HumNumIn
    ) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(self._scoreData, ScoreData)

        gridSlice: GridSlice = GridSlice(outgm, nowTime, SliceType.Clefs, self.staffCounts)
        outgm.slices.append(gridSlice)

        if len(clefs) != len(gridSlice.parts):
            raise HumdrumExportError(
                'Number of clef lists does not match number of parts'
            )

        for p, partClefs in enumerate(clefs):
            if partClefs:
                self._insertPartClefs(partClefs, gridSlice.parts[p])

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addStriaLine --
    '''
    def _addStriaLine(
        self,
        outgm: GridMeasure,
        staffLines: list[list[tuple[int, int]]],
        nowTime: HumNumIn
    ) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(self._scoreData, ScoreData)
        gridSlice: GridSlice = GridSlice(outgm, nowTime, SliceType.Stria, self.staffCounts)
        outgm.slices.append(gridSlice)

        if len(staffLines) != len(gridSlice.parts):
            raise HumdrumExportError(
                'number of staffLine lists does not match number of parts'
            )

        for p, partStaffLines in enumerate(staffLines):
            if partStaffLines is not None:
                self._insertPartStria(partStaffLines, gridSlice.parts[p])

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addTimeSigLine --
    '''
    def _addTimeSigLine(
        self,
        outgm: GridMeasure,
        timeSigs: list[list[tuple[int, m21.meter.TimeSignature]]],
        nowTime: HumNumIn,
        hasMeterSig: bool
    ) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(self._scoreData, ScoreData)

        gridSlice: GridSlice = GridSlice(outgm, nowTime, SliceType.TimeSigs, self.staffCounts)
        outgm.slices.append(gridSlice)

        for partTimeSigs, part in zip(timeSigs, gridSlice.parts):
            if partTimeSigs:
                self._insertPartTimeSigs(partTimeSigs, part)

        if not hasMeterSig:
            return

        # Add meter sigs related to time signatures (e.g. common time, cut time)
        gridSlice = GridSlice(outgm, nowTime, SliceType.MeterSigs, self.staffCounts)
        outgm.slices.append(gridSlice)

        # now add meter sigs associated with time signatures
        # The m21 timesig object contains this (optional) info as well
        for partTimeSigs, part in zip(timeSigs, gridSlice.parts):
            if partTimeSigs:
                self._insertPartMeterSigs(partTimeSigs, part)

    def _insertPartTimeSigs(
        self,
        timeSigs: list[tuple[int, m21.meter.TimeSignature]],
        part: GridPart
    ) -> None:
        if part is None:
            return

        durationZero: HumNum = opFrac(0)
        voice0: int = 0
        for staffIdx, timeSig in timeSigs:
            token: HumdrumToken | None = M21Convert.timeSigTokenFromM21TimeSignature(timeSig)
            if token:
                staff = part.staves[staffIdx]
                staff.setTokenLayer(voice0, token, durationZero)

        # go back and fill in all None tokens with null interpretations
        self._fillEmpties(part, '*')

    def _insertPartMeterSigs(
        self,
        timeSigs: list[tuple[int, m21.meter.TimeSignature]],
        part: GridPart
    ) -> None:
        if part is None:
            return

        durationZero: HumNum = opFrac(0)
        voice0: int = 0
        for staffIdx, timeSig in timeSigs:
            token: HumdrumToken | None = M21Convert.meterSigTokenFromM21TimeSignature(timeSig)
            if token is not None:
                staff = part.staves[staffIdx]
                staff.setTokenLayer(voice0, token, durationZero)

        # go back and fill in all None tokens with null interpretations
        self._fillEmpties(part, '*')

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addKeySigLine -- Only adding one key signature
    //   for each part for now.
    '''
    def _addKeySigLine(
        self,
        outgm: GridMeasure,
        keySigs: list[list[tuple[int, m21.key.KeySignature | m21.key.Key]]],
        nowTime: HumNumIn,
        hasKeyDesignation: bool
    ) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(self._scoreData, ScoreData)

        gridSlice: GridSlice = GridSlice(outgm, nowTime, SliceType.KeySigs, self.staffCounts)
        outgm.slices.append(gridSlice)

        for partKeySigs, part in zip(keySigs, gridSlice.parts):
            if partKeySigs:
                self._insertPartKeySigs(partKeySigs, part)

        # Add any key designations as well
        if not hasKeyDesignation:
            return

        gridSlice = GridSlice(outgm, nowTime, SliceType.KeyDesignations, self.staffCounts)
        outgm.slices.append(gridSlice)

        for partKeySigs, part in zip(keySigs, gridSlice.parts):
            if partKeySigs:
                self._insertPartKeyDesignations(partKeySigs, part)

    def _insertPartKeySigs(
        self,
        keySigs: list[tuple[int, m21.key.KeySignature | m21.key.Key]],
        part: GridPart
    ) -> None:
        if part is None:
            return

        durationZero: HumNum = opFrac(0)
        voice0: int = 0
        for staffIdx, keySig in keySigs:
            token: HumdrumToken = M21Convert.keySigTokenFromM21KeySignature(keySig)
            if token:
                staff = part.staves[staffIdx]
                staff.setTokenLayer(voice0, token, durationZero)

        # go back and fill in all None tokens with null interpretations
        self._fillEmpties(part, '*')

    def _insertPartKeyDesignations(
        self,
        keySigs: list[tuple[int, m21.key.KeySignature | m21.key.Key]],
        part: GridPart
    ) -> None:

        if part is None:
            return

        durationZero: HumNum = opFrac(0)
        voice0: int = 0
        for staffIdx, keySig in keySigs:
            if isinstance(keySig, m21.key.Key):  # we can only generate KeyDesignation from Key
                token: HumdrumToken | None = (
                    M21Convert.keyDesignationTokenFromM21KeySignature(keySig)
                )
                if token:
                    staff = part.staves[staffIdx]
                    staff.setTokenLayer(voice0, token, durationZero)

        # go back and fill in all None tokens with null interpretations
        self._fillEmpties(part, '*')

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addTranspositionLine -- Transposition codes to
    //   produce written parts.
    '''
    def _addTranspositionLine(
        self,
        outgm: GridMeasure,
        transposingInstruments: list[list[tuple[int, m21.instrument.Instrument]]],
        nowTime: HumNumIn
    ) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(self._scoreData, ScoreData)

        gridSlice: GridSlice = GridSlice(outgm, nowTime, SliceType.KeySigs, self.staffCounts)
        outgm.slices.append(gridSlice)

        for partTransposingInstruments, part in zip(transposingInstruments, gridSlice.parts):
            if partTransposingInstruments:
                self._insertPartTranspositions(partTransposingInstruments, part)

    def _insertPartTranspositions(
        self,
        transposingInstruments: list[tuple[int, m21.instrument.Instrument]],
        part: GridPart
    ) -> None:
        if part is None:
            return

        durationZero: HumNum = opFrac(0)
        voice0: int = 0
        for staffIdx, inst in transposingInstruments:
            token: HumdrumToken | None = (
                M21Convert.instrumentTransposeTokenFromM21Instrument(inst)
            )
            if token:
                staff = part.staves[staffIdx]
                staff.setTokenLayer(voice0, token, durationZero)

        # go back and fill in all None tokens with null interpretations
        self._fillEmpties(part, '*')

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::insertPartClefs --
    '''
    def _insertPartClefs(self, clefs: list[tuple[int, m21.clef.Clef]], part: GridPart) -> None:
        if part is None:
            return

        durationZero: HumNum = opFrac(0)
        voice0: int = 0
        for staffIdx, clef in clefs:
            token: HumdrumToken | None = M21Convert.clefTokenFromM21Clef(clef)
            if token:
                staff = part.staves[staffIdx]
                staff.setTokenLayer(voice0, token, durationZero)

        # go back and fill in all None tokens with null interpretations
        self._fillEmpties(part, '*')

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::insertPartStria --
    '''
    def _insertPartStria(self, staffLineCounts: list[tuple[int, int]], part: GridPart) -> None:
        if part is None:
            return

        durationZero: HumNum = opFrac(0)
        voice0: int = 0
        for staffIdx, lineCount in staffLineCounts:
            token: HumdrumToken = HumdrumToken('*stria' + str(lineCount))
            staff = part.staves[staffIdx]
            staff.setTokenLayer(voice0, token, durationZero)

        # go back and fill in all None tokens with null interpretations
        self._fillEmpties(part, '*')

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::fillEmpties --
    '''
    @staticmethod
    def _fillEmpties(part: GridPart, string: str) -> None:
        durationZero: HumNum = opFrac(0)

        for staff in part.staves:
            if staff is None:
                print('staff is None in _fillEmpties', file=sys.stderr)
                continue

            voiceCount: int = len(staff.voices)
            if voiceCount == 0:
                staff.voices.append(GridVoice(string, durationZero))
            else:
                for v, gv in enumerate(staff.voices):
                    if gv is None:
                        gv = GridVoice(string, durationZero)
                        staff.voices[v] = gv
                    elif gv.token is None:
                        gv.token = HumdrumToken(string)

    @staticmethod
    def _processPrintElement(
        outgm: GridMeasure,
        m21Obj: m21.layout.PageLayout | m21.layout.SystemLayout,
        nowTime: HumNumIn
    ) -> None:
        isPageBreak: bool = isinstance(m21Obj, m21.layout.PageLayout) and m21Obj.isNew is True
        isSystemBreak: bool = isinstance(m21Obj, m21.layout.SystemLayout) and m21Obj.isNew is True

        if not isPageBreak and not isSystemBreak:
            return

        # C++ code (musicxml2hum) checks the last slice to see if it's already a page/system break
        # and does nothing if it is.  Maybe that's MusicXML-specific?  If music21 Score has
        # multiple page or system breaks in a row, it seems like I should honor that.
#         gs: GridSlice = outgm.slices[-1]
#
#         token: HumdrumToken = None
#         if gs is not None and gs.parts:
#             part: GridPart = gs.parts[0]
#             if part.staves:
#                 staff: GridStaff = part.staves[0]
#                 if staff.voices:
#                     voice: GridVoice = staff.voices[0]
#                     token = voice.token

        if isPageBreak:
            outgm.addGlobalComment('!!LO:PB:g=z', nowTime)
        elif isSystemBreak:
            outgm.addGlobalComment('!!LO:LB:g=z', nowTime)


    '''
    /////////////////////////////
    //
    // Tool_musicxml2hum::appendNonZeroEvents --
    '''
    def _appendNonZeroDurationEvents(
        self,
        outgm: GridMeasure,
        nowEvents: list[SimultaneousEvents],
        nowTime: HumNumIn
    ) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(self._scoreData, ScoreData)

        outSlice: GridSlice = GridSlice(outgm, nowTime, SliceType.Notes, self.staffCounts)

        if len(outgm.slices) == 0:
            outgm.slices.append(outSlice)
        else:
            # insert into correct time position in measure
            lastTime: HumNum = outgm.slices[-1].timestamp
            if nowTime >= lastTime:
                outgm.slices.append(outSlice)
            else:
                # travel backwards in the measure until the correct
                # time position is found.
                for i, walkSlice in enumerate(reversed(outgm.slices)):
                    if walkSlice.timestamp <= nowTime:
                        outgm.slices.insert(i, outSlice)
                        break

        for ne in nowEvents:
            events: list[EventData] = ne.nonZeroDur
            for event in events:
                self._addEvent(outSlice, outgm, event, nowTime)

    def storePendingOttavaStops(
        self,
        stops: list[str],
        timestamp: HumNum,
        partIndex: int,
        staffIndex: int,
        voiceIndex: int
    ):
        if self.pendingOttavaStopsForPartAndStaff.get(partIndex, None) is None:
            self.pendingOttavaStopsForPartAndStaff[partIndex] = {}
        if self.pendingOttavaStopsForPartAndStaff[partIndex].get(staffIndex, None) is None:
            self.pendingOttavaStopsForPartAndStaff[partIndex][staffIndex] = []

        for stop in stops:
            pendingOttavaStop = PendingOttavaStop(stop, timestamp)
            self.pendingOttavaStopsForPartAndStaff[partIndex][staffIndex].append(pendingOttavaStop)

    def popPendingOttavaStopsAtTime(
        self,
        partIndex: int,
        staffIndex: int,
        timestamp: HumNum
    ) -> list[str]:
        output: list[str] = []
        stopsForPart: dict[int, list[PendingOttavaStop]] | None = (
            self.pendingOttavaStopsForPartAndStaff.get(partIndex, None)
        )
        if not stopsForPart:
            return output

        stopsForStaff: list[PendingOttavaStop] | None = stopsForPart.get(staffIndex, None)
        if not stopsForStaff:
            return output

        removeList: list[PendingOttavaStop] = []
        for stop in stopsForStaff:
            if stop.timestamp == timestamp:
                output.append(stop.tokenString)
                removeList.append(stop)

        for removeThis in removeList:
            stopsForStaff.remove(removeThis)

        return output

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addEvent -- Add a note or rest to a grid slice
    '''
    def _addEvent(
        self,
        outSlice: GridSlice | None,
        outgm: GridMeasure,
        event: EventData | None,
        nowTime: HumNumIn
    ) -> None:
        partIndex: int   # event.partIndex
        staffIndex: int  # event.staffIndex
        voiceIndex: int  # event.voiceIndex

        if event is not None:
            partIndex = event.partIndex
            staffIndex = event.staffIndex
            voiceIndex = event.voiceIndex

        if outSlice is not None:
            # Insert any pending Ottava stops
            ottavaStopTokenStrings: list[str] = (
                self.popPendingOttavaStopsAtTime(partIndex, staffIndex, nowTime)
            )

            outgm.addOttavaTokensBefore(
                ottavaStopTokenStrings,
                outSlice,
                partIndex,
                staffIndex,
                voiceIndex
            )

        tokenString: str = ''
        layouts: list[str] = []
        if event is None or not event.isDynamicWedgeStartOrStop:
            if event is not None:
                if t.TYPE_CHECKING:
                    assert isinstance(outSlice, GridSlice)

                tokenString, layouts = event.getNoteKernTokenStringAndLayouts()
                if '@' in tokenString:
                    self._hasTremolo = True

                if self.Debug:
                    print(f'!!TOKEN: {tokenString}', end='\t', file=sys.stderr)
                    print(f'TS: {event.startTime}', end='\t', file=sys.stderr)
                    print(f'DUR: {event.duration}', end='\t', file=sys.stderr)
                    print(f'STn: {event.staffNumber}', end='\t', file=sys.stderr)
                    print(f'Vn: {event.voiceNumber}', end='\t', file=sys.stderr)
                    print(f'STi: {event.staffIndex}', end='\t', file=sys.stderr)
                    print(f'Vi: {event.voiceIndex}', end='\t', file=sys.stderr)
                    print(f'eName: {event.name}', file=sys.stderr)

                token = HumdrumToken(tokenString)
                outSlice.parts[partIndex].staves[staffIndex].setTokenLayer(
                    voiceIndex, token, event.duration
                )

                # check for ottava starts/stops and emit *8va or *X8va aut cetera
                if event.isOttavaStartOrStop:
                    starts: list[str]
                    stops: list[str]
                    starts, stops = event.getOttavaTokenStrings()
                    if starts:
                        # any starts go before this slice
                        outgm.addOttavaTokensBefore(
                            starts,
                            outSlice,
                            partIndex,
                            staffIndex,
                            voiceIndex
                        )
                    if stops:
                        # any stops go after the full duration of this event,
                        # which might be many slices from now (maybe even in
                        # a different measure) so we have to stash them off
                        # and insert them later.
                        self.storePendingOttavaStops(
                            stops,
                            opFrac(event.startTime + event.duration),
                            partIndex,
                            staffIndex,
                            voiceIndex
                        )

                # implement tuplet number/bracket visibility
                # *tuplet means display tuplets (default)
                # *Xtuplet means suppress tuplets (both num and bracket are suppressed)
                # *brackettup means display tuplet brackets (default, but only makes a
                # difference if tuplet is displayed)
                # *Xbrackettup means suppress tuplet brackets (only makes a difference if tuplet
                # is displayed)
                if event.isTupletStart:
                    if self.tupletsSuppressed(partIndex, staffIndex):
                        if not event.suppressTupletNum:
                            outgm.addTupletDisplayTokenBefore(
                                '*tuplet',
                                outSlice,
                                partIndex,
                                staffIndex,
                                voiceIndex
                            )
                            self.setTupletsSuppressed(partIndex, staffIndex, False)

                            # Also check to make sure *brackettup is in the right state,
                            # since Humdrum is about to start paying attention to it.
                            if (self.tupletBracketsSuppressed(partIndex, staffIndex)
                                    != event.suppressTupletBracket):
                                s1: str = '*brackettup'
                                if event.suppressTupletBracket:
                                    s1 = '*Xbrackettup'
                                outgm.addTupletDisplayTokenBefore(
                                    s1,
                                    outSlice,
                                    partIndex,
                                    staffIndex,
                                    voiceIndex
                                )
                                self.setTupletBracketsSuppressed(
                                    partIndex,
                                    staffIndex,
                                    event.suppressTupletBracket
                                )
                    else:
                        # Tuplets are not currently suppressed (*tuplet is current in force)
                        if event.suppressTupletNum:
                            outgm.addTupletDisplayTokenBefore(
                                '*Xtuplet',
                                outSlice,
                                partIndex,
                                staffIndex,
                                voiceIndex
                            )
                            self.setTupletsSuppressed(partIndex, staffIndex, True)

                            # We don't check state of *brackettup here, since it doesn't matter.
                            # We'll update it next time we emit *tuplet to turn tuplets back on.
                        else:
                            # Tuplets are on, and we're leaving them on.  Better check that
                            # *brackettup state doesn't need to change.
                            if (self.tupletBracketsSuppressed(partIndex, staffIndex)
                                    != event.suppressTupletBracket):
                                s2: str = '*brackettup'
                                if event.suppressTupletBracket:
                                    s2 = '*Xbrackettup'
                                outgm.addTupletDisplayTokenBefore(
                                    s2,
                                    outSlice,
                                    partIndex,
                                    staffIndex,
                                    voiceIndex
                                )
                                self.setTupletBracketsSuppressed(
                                    partIndex,
                                    staffIndex,
                                    event.suppressTupletBracket
                                )

                # layouts go last because they need to be closest to the note.
                for layoutString in layouts:
                    outgm.addLayoutParameter(
                        outSlice, partIndex, staffIndex, voiceIndex, layoutString
                    )

                vcount: int = self._addLyrics(outgm, outSlice, partIndex, staffIndex, event)
                if vcount > 0:
                    event.reportVerseCountToOwner(vcount)

                hcount: int = self._addHarmony(
                    outSlice.parts[partIndex], event, nowTime, partIndex
                )
                if hcount > 0:
                    pass
                    # event.reportHarmonyCountToOwner(hcount)

        # LATER: implement figured bass
        #         fcount: int = self._addFiguredBass(outSlice.parts[partIndex],
        #                                               event, nowTime, partIndex)
        #         if fcount > 0:
        #             event.reportFiguredBassToOwner()

        # LATER: implement brackets for *lig/*Xlig and *col/*Xcol
        #         if self._currentBrackets[partIndex]:
        #             for bracket in self._currentBrackets[partIndex]:
        #                 event.bracket = bracket
        #             self._currentBrackets[partIndex] = []
        #             self._addBrackets(outSlice, outgm, event, nowTime, partIndex)

            if (event is not None and event.texts) or self._currentTexts:
                # self._currentTexts contains any zero-duration (unassociated) TextExpressions,
                # that could be in any part/staff/voice.  We'll take the opportunity to add them
                # now.
                # event.texts contains any TextExpressions associated with this note (in this
                # part/staff/voice).
                if t.TYPE_CHECKING:
                    assert isinstance(outSlice, GridSlice)
                    assert isinstance(event, EventData)
                self._addTexts(outSlice, outgm, event, self._currentTexts)
                self._currentTexts = []  # they've all been added

            if self._currentTempos:
                # self._currentTempos contains all the TempoIndications that could be in any part.
                # There is no event.tempos (music21 tempos are always unassociated).  But we take
                # the opportunity to add them now.
                if t.TYPE_CHECKING:
                    assert isinstance(outSlice, GridSlice)
                self._addTempos(outSlice, outgm, self._currentTempos)
                self._currentTempos = []  # they've all been added

        if (event is not None and event.isDynamicWedgeStartOrStop) or self._currentDynamics:
            # self._currentDynamics contains any zero-duration (unassociated) dynamics ('pp' et al)
            # that could be in any part/staff.
            # event has a single dynamic wedge start or stop, that is in this part/staff.
            if t.TYPE_CHECKING:
                assert isinstance(outSlice, GridSlice)
                assert isinstance(event, EventData)
            self._addDynamics(outSlice, outgm, event, self._currentDynamics)
            self._currentDynamics = []
            if event is not None and event.isDynamicWedgeStartOrStop:
                event.reportDynamicToOwner()  # reports that dynamics exist in this part/staff

        # might need special hairpin ending processing here (or might be musicXML-specific).

        # might need postNoteText processing, but it looks like that's only for a case
        # ... where '**blah' (a humdrum exInterp) occurs in a musicXML direction node. (Why?!?)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addDynamic -- extract any dynamics for the event
    '''
    @staticmethod
    def _addDynamics(
        outSlice: GridSlice,
        outgm: GridMeasure,
        event: EventData,
        extraDynamics: list[tuple[int, int, m21.dynamics.Dynamic]]
    ) -> None:
        dynamics: list[tuple[int, int, str]] = []

        eventIsDynamicWedge: bool = event is not None and event.isDynamicWedgeStartOrStop
        eventIsDynamicWedgeStart: bool = event is not None and event.isDynamicWedgeStart

        if eventIsDynamicWedge:
            dynamics.append((event.partIndex, event.staffIndex, event.getDynamicWedgeString()))

        for partIndex, staffIndex, dynamic in extraDynamics:
            dstring = M21Convert.getDynamicString(dynamic)
            dynamics.append((partIndex, staffIndex, dstring))

        if not dynamics:
            # we shouldn't have been called
            return

        # The following dictionaries are keyed by partIndex (no staffIndex here)
        dynTokens: dict[int, HumdrumToken] = {}
        moreThanOneDynamic: dict[int, bool] = {}
        currentDynamicIndex: dict[int, int] = {}

        for partIndex, staffIndex, dstring in dynamics:
            if not dstring:
                continue

            if dynTokens.get(partIndex, None) is None:
                dynTokens[partIndex] = HumdrumToken(dstring)
                moreThanOneDynamic[partIndex] = False
            else:
                dynTokens[partIndex].text += ' ' + dstring
                moreThanOneDynamic[partIndex] = True
                currentDynamicIndex[partIndex] = 1  # ':n=' is 1-based

        # dynTokens key is tuple[int, int], value is token
        for partIndex, token in dynTokens.items():
            if outSlice is None:
                # we better make one, timestamped at end of measure, type Notes (even though it
                # will only have '.' in the **kern spines, and a 'p' (or whatever) in the
                # **dynam spine)
                outSlice = GridSlice(outgm, outgm.timestamp + outgm.duration, SliceType.Notes)
                outSlice.initializeBySlice(outgm.slices[-1])

            existingDynamicsToken: HumdrumToken | None = (
                outSlice.parts[partIndex].dynamics
            )
            if existingDynamicsToken is None:
                outSlice.parts[partIndex].dynamics = token
            else:
                existingDynamicsToken.text += ' ' + token.text
                moreThanOneDynamic[partIndex] = True
                currentDynamicIndex[partIndex] = 1  # ':n=' is 1-based

        # add any necessary layout params
        dparam: str | None
        fullParam: str

        # first the one DynamicWedge start or stop that is this event (but only if it's a start)
        if eventIsDynamicWedgeStart:
            if t.TYPE_CHECKING:
                assert isinstance(event.m21Object, m21.dynamics.DynamicWedge)

            dparam = M21Convert.getDynamicWedgeStartParameters(event.m21Object, event.staffIndex)
            if dparam:
                fullParam = '!LO:HP'
                if moreThanOneDynamic[partIndex]:
                    fullParam += ':n=' + str(currentDynamicIndex[partIndex])
                    currentDynamicIndex[partIndex] += 1
                fullParam += dparam
                outgm.addDynamicsLayoutParameters(outSlice, partIndex, fullParam)

        # next the Dynamic objects ('pp', etc) in extraDynamics
        for partIndex, staffIndex, dynamic in extraDynamics:
            dparam = M21Convert.getDynamicParameters(dynamic, staffIndex)
            if dparam:
                fullParam = '!LO:DY'

                if moreThanOneDynamic[partIndex]:
                    fullParam += ':n=' + str(currentDynamicIndex[partIndex])
                    currentDynamicIndex[partIndex] += 1

                fullParam += dparam
                outgm.addDynamicsLayoutParameters(outSlice, partIndex, fullParam)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addTexts -- Add all text direction for a note.
    '''
    def _addTexts(
        self,
        outSlice: GridSlice,
        outgm: GridMeasure,
        event: EventData,
        extraTexts: list[tuple[int, int, int, m21.expressions.TextExpression]]
    ) -> None:
        if event is not None:
            partIndex: int = event.partIndex
            staffIndex: int = event.staffIndex
            voiceIndex: int = event.voiceIndex
            for textExpression in event.texts:
                self._addText(outSlice, outgm,
                              partIndex, staffIndex, voiceIndex,
                              textExpression)

        # extraTexts come each with their own partIndex, staffIndex, voiceIndex
        for partIndex, staffIndex, voiceIndex, textExpression in extraTexts:
            self._addText(outSlice, outgm,
                          partIndex, staffIndex, voiceIndex,
                          textExpression)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addText -- Add a text direction to the grid.
    '''
    @staticmethod
    def _addText(
        outSlice: GridSlice,
        outgm: GridMeasure,
        partIndex: int,
        staffIndex: int,
        voiceIndex: int,
        textExpression: m21.expressions.TextExpression
    ) -> None:
        textString: str = M21Convert.textLayoutParameterFromM21TextExpression(textExpression)
        outgm.addLayoutParameter(outSlice, partIndex, staffIndex, voiceIndex, textString)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addTempos -- Add tempo indication for a note.
    '''
    def _addTempos(
        self,
        outSlice: GridSlice,
        outgm: GridMeasure,
        tempos: list[tuple[int, m21.tempo.TempoIndication]]
    ) -> None:
        # we have to deduplicate because sometimes MusicXML export from music21 adds
        # extra metronome marks when exporting from PartStaffs.
        # We only want one metronome mark in this slice, preferably in the top-most part
        # We'll be content with the highest partIndex seen.
        # Note: The original routine over-deleted if there were multiple _different_
        # metronome marks.
        # This is now rewritten to only delete actual duplicates. --gregc
        # And now de-duplication is disabled; it was causing more problems than it was worth.
        emittedTempos: list[m21.tempo.TempoIndication] = []

        # First, sort by partIndex (highest first)
        # Then loop over all the tempos, adding only the first one you see of each unique mark
        def partIndexOf(tempo: tuple[int, m21.tempo.TempoIndication]) -> int:
            return tempo[0]

        def isAlreadyEmitted(_tempo: m21.tempo.TempoIndication) -> bool:
            # disable de-duplication to see if it causes any problems (helps with a few scores)
            return False
#             tempoMM: m21.tempo.MetronomeMark = tempo.getSoundingMetronomeMark()
#             for e in emittedTempos:
#                 if type(tempo) is not type(e): # original type, not MM
#                     continue
#                 eMM: m21.tempo.MetronomeMark = e.getSoundingMetronomeMark()
#                 if eMM.numberImplicit != tempoMM.numberImplicit:
#                     continue
#                 if not eMM.numberImplicit and eMM.number != tempoMM.number:
#                     continue
#                 if eMM.textImplicit != tempoMM.textImplicit:
#                     continue
#                 if not eMM.textImplicit and eMM.text != tempoMM.text:
#                     continue
#                 if eMM.referent != tempoMM.referent:
#                     continue
#                 return True
#             return False

        sortedTempos = sorted(tempos, key=partIndexOf, reverse=True)
        for partIndex, tempoIndication in sortedTempos:
            if not isAlreadyEmitted(tempoIndication):
                self._addTempo(outSlice, outgm, partIndex, tempoIndication)
                emittedTempos.append(tempoIndication)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addTempo -- Add a tempo direction to the grid.
    '''
    def _addTempo(
        self,
        outSlice: GridSlice,
        outgm: GridMeasure,
        partIndex: int,
        tempoIndication: m21.tempo.TempoIndication
    ) -> None:
        wasInitialOMD: bool = False
        if hasattr(tempoIndication, 'humdrumTempoIsFromInitialOMD'):
            wasInitialOMD = tempoIndication.humdrumTempoIsFromInitialOMD  # type: ignore
            delattr(tempoIndication, 'humdrumTempoIsFromInitialOMD')

        mmTokenStr: str = ''  # e.g. '*MM128'
        tempoOMD: str = ''  # e.g. '!!!OMD: [eighth]=82','!!!OMD: Andantino [eighth]=82'
        mmTokenStr, tempoOMD = (
            M21Convert.getMMTokenAndOMDFromM21TempoIndication(tempoIndication)
        )

        staffIndex: int = 0
        voiceIndex: int = 0
        if mmTokenStr:
            outgm.addTempoToken(mmTokenStr, outSlice.timestamp,
                                partIndex, staffIndex, voiceIndex,
                                self.staffCounts)

        if tempoOMD:
            if wasInitialOMD:
                # Stash tempoOMD off because it might have extra '[half-dot]=63'-style
                # text in it that was stripped from the movementName in the metadata
                # (no-one wants that in a title), and we should restore it when writing
                # the initial OMD to the output Humdrum file.
                self.initialOMDToken = tempoOMD
            else:
                # emit it now instead (it's a tempo change partway through the score)
                outgm.addGlobalReference(tempoOMD, outSlice.timestamp)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addLyrics --
    '''
    def _addLyrics(
        self,
        outgm: GridMeasure,
        outSlice: GridSlice,
        partIndex: int,
        staffIndex: int,
        event: EventData
    ) -> int:
        if t.TYPE_CHECKING:
            assert isinstance(event.m21Object, m21.note.GeneralNote)

        staff: GridStaff = outSlice.parts[partIndex].staves[staffIndex]
        gnote: m21.note.GeneralNote = event.m21Object
        verses: list[m21.note.Lyric | None] = []
        if not hasattr(gnote, 'lyrics'):
            return 0
        if not gnote.lyrics:
            return 0

        # order the verses by number
        for lyric in gnote.lyrics:
            number: int = lyric.number
            if number > 100:
                print(f'Error: verse number is too large: {number}', file=sys.stderr)
                return 0

            if number == len(verses) + 1:
                verses.append(lyric)
            elif 0 < number < len(verses):
                # replace a verse for some reason
                verses[number - 1] = lyric
            elif number > 0:
                # more than one off the end, fill in with empty slots
                oldLen: int = len(verses)
                newLen: int = number
                for _ in range(oldLen, newLen):
                    verses.append(None)
                verses[number - 1] = lyric

        # now, in number order (with maybe some empty slots)
        vLabelTokens: list[HumdrumToken | None] = [None] * len(verses)
        thereAreVerseLabels: bool = False

        for i, verse in enumerate(verses):
            verseText: str = ''
            verseLabel: str = ''
            if verse is not None:
                # rawText handles elisions as well as syllabic-based hyphens
                verseText = self._cleanSpaces(verse.rawText)

                # escape text which would otherwise be reinterpreated
                # as Humdrum syntax.
                if verseText and verseText[0] in ('!', '*'):
                    verseText = '\\' + verseText

                # if verse.identifier has not been set, verse.identifier will return verse.number
                # (which is always set to an integer for ordering), and we're uninterested
                # in that for verse labeling purposes.  We're already ordering by number.
                if verse.identifier != verse.number:
                    # verse.identifier can return an int, but if set explicitly
                    # we expect it to be set to str.  We cast to str, just in case.
                    verseLabel = str(verse.identifier)

            if verseLabel:
                vLabelTokens[i] = HumdrumToken('*v:' + verseLabel)
                thereAreVerseLabels = True

            verseToken: HumdrumToken
            if verseText:
                verseToken = HumdrumToken(verseText)
            else:
                verseToken = HumdrumToken('.')

            staff.sides.setVerse(i, verseToken)

        # if there are any verse labels, add them in a new slice just before this one
        if thereAreVerseLabels:
            outgm.addVerseLabels(outSlice, partIndex, staffIndex, vLabelTokens)

        return staff.sides.verseCount

    '''
    //////////////////////////////
    //
    // cleanSpaces -- remove trailing and leading spaces from text.
    //    Also removed doubled spaces, and converts tabs and newlines
    //    into spaces.
    '''
    @staticmethod
    def _cleanSpaces(text: str) -> str:
        # Non-obvious, but it does the job exactly...
        # split() returns a list of words that were delimited by chunks of
        # whitespace (space, tab, newline, etc).  The words will have NO
        # whitespace in them (i.e. trailing and leading whitespace is also
        # removed).  join() will rejoin those words with a single space
        # (specified here as ' ') between them.
        return ' '.join(text.split())


    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addHarmony --
    '''
    def _addHarmony(
        self,
        part: GridPart,  # LATER: needs implementation
        event: EventData,
        nowTime: HumNumIn,
        partIndex: int
    ) -> int:
        if self or part or event or nowTime or partIndex:
            return 0
        return 0
