# ------------------------------------------------------------------------------
# Name:          HumdrumWriter.py
# Purpose:       HumdrumWriter is an object that takes a music21 stream and
#                writes it to a file as Humdrum data.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
import copy
from collections import OrderedDict
from typing import List, Tuple, Dict, Set, Union, Optional
import music21 as m21

from converter21.humdrum import HumdrumExportError, HumdrumInternalError
from converter21.humdrum import HumNum
from converter21.humdrum import M21Convert
from converter21.humdrum import M21Utilities
from converter21.humdrum import M21StaffGroupTree

from converter21.humdrum import EventData
from converter21.humdrum import MeasureData, SimultaneousEvents
from converter21.humdrum import ScoreData

from converter21.humdrum import SliceType
#from converter21.humdrum import MeasureStyle
from converter21.humdrum import GridVoice
#from converter21.humdrum import GridSide
from converter21.humdrum import GridStaff
from converter21.humdrum import GridPart
from converter21.humdrum import GridSlice
from converter21.humdrum import GridMeasure
from converter21.humdrum import HumGrid

from converter21.humdrum import HumdrumToken
from converter21.humdrum import HumdrumFile
from converter21.humdrum import ToolTremolo

### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

class HumdrumWriter:
    Debug: bool = False # can be set to True for more debugging

    _classMapping = OrderedDict([
        ('Score', '_fromScore'),
        ('Part', '_fromPart'),
        ('Measure', '_fromMeasure'),
        ('Voice', '_fromVoice'),
        ('Stream', '_fromStream'),
        # ## individual parts
        ('GeneralNote', '_fromGeneralNote'),
        ('Pitch', '_fromPitch'),
        ('Duration', '_fromDuration'),  # not an m21 object
        ('Dynamic', '_fromDynamic'),
        ('DiatonicScale', '_fromDiatonicScale'),
        ('Scale', '_fromScale'),
        ('Music21Object', '_fromMusic21Object'),
    ])

    # '<>' are not considered reservable, they are hard-coded to below/above, and
    # used as such without coordination here.
    # '@' is not considered reservable (damn) because we use it in tremolos (e.g. '@16@' and '@@32@@')
    _reservableRDFKernSignifiers: str = 'ijZVNl!+|'

    _m21EditorialStyleToHumdrumEditorialStyle: dict = {
        # m21 editorial style: RDF definition string we will write
        'parentheses': 'paren',
        'bracket': 'bracket',
    }
    _humdrumEditorialStyleToFavoriteSignifier: dict = {
        'paren': 'i',
        'bracket': 'j',
    }
    _humdrumEditorialStyleToRDFDefinitionString: dict = {
        'paren': 'editorial accidental (paren)',
        'bracket': 'editorial accidental (bracket)',
    }

    def __init__(self, obj: m21.prebase.ProtoM21Object):
        self._m21Object: m21.prebase.ProtoM21Object = obj
        self._m21Score: m21.stream.Score = None
        self.spannerBundle = None
        self._scoreData: ScoreData = None
        self._maxStaff: int = 0

        # default options (these can be set to non-default values by clients,
        # as long as they do it before they call write())
        self.makeNotation : bool = True  # client can set to False if obj is a Score
        self.addRecipSpine: bool = False # client can set to True to add a recip spine to the output
        self.expandTremolos: bool = True # can be set to False if you want to keep the '@32@'-style
                                         # bowed tremolos, and the '@@16@@'-style fingered tremolos

        self.VoiceDebug: bool = False # can be set to True for debugging output
        self._reservedRDFKernSignifiers: str = '' # set by property, so we can vet it
        self._assignedRDFKernSignifiers: str = '' # set internally, as we use them for various things

        # _rdfKernSignifierLookup will be computed from what is needed in the score,
        # taking into account any reservedRDFKernSignifiers set by the user
        self._rdfKernSignifierLookup: dict = {} # key: definition (str or tuple), value: signifier

        # private data, computed along the way...
        self._forceRecipSpine: bool = False # set to true sometimes in figured bass, harmony code
        self._hasTremolo: bool = False      # has fingered or bowed tremolo(s) that need expanding
        self._hasOrnaments: bool = False    # has trills, mordents, or turns that need refinement

        # temporary data (to be emitted with next durational object)
        # First elements of text tuple are part index, staff index, voice index
        self._currentTexts:  List[Tuple[int, int, int, m21.expressions.TextExpression]] = []
        # First elements of dynamic tuple are part index, staff index (dynamics are at staff level)
        self._currentDynamics: List[Tuple[int, int, m21.dynamics.Dynamic]] = []
        # First element of tempo tuple is part index (tempo is at the part level)
        self._currentTempos: List[Tuple[int, m21.tempo.TempoIndication]] = []

    def _chosenSignifierForRDFDefinition(self,
                                         rdfDefinition: Union[str, Tuple[str, Optional[str]]],
                                         favoriteSignifier: str) -> str:
        chosenSignifier: Optional[str] = None
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
        else: # choose an unreserved, unassigned signifier
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
                    print(f'Too many reserved RDF signifiers for this score, using reserved signifier \'{chosenSignifier}\' for \'{rdfDefinition}\'', file=sys.stderr)
                    break

        if not chosenSignifier:
            raise HumdrumInternalError('Ran out of RDF signifier chars') # shouldn't ever happen

        return chosenSignifier

    def reportEditorialAccidentalToOwner(self, editorialStyle: str) -> str:
        humdrumStyle: str = self._m21EditorialStyleToHumdrumEditorialStyle.get(editorialStyle, '')
        if not humdrumStyle:
            print(f'Unrecognized music21 editorial accidental style \'{editorialStyle}\': treating as parentheses.',
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
        rdfDefinition: Tuple[str, Optional[str]] = (
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
    def reservedRDFKernSignifiers(self, newReservedRDFKernSignifiers: str):
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
            raise ValueError(f'''
The following signifier chars are not reservable: \'{badSignifiers}\'.
Reservable signifier chars are \'{self._reservableRDFKernSignifiers}\''''
                            )

        self._reservedRDFKernSignifiers = newReservedRDFKernSignifiers

    def write(self, fp):
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
            self._m21Score = self._makeScoreFromObject(self._m21Object) # always creates a new Score
        else:
            if not isinstance(self._m21Object, m21.stream.Score):
                raise HumdrumExportError('Since makeNotation=False, source obj must be a music21 Score, and it is not.')
            self._m21Score = self._m21Object
        del self._m21Object # everything after this uses self._m21Score

        self.spannerBundle = self._m21Score.spannerBundle

        # The rest is based on Tool_musicxml2hum::convert(ostream& out, xml_document& doc)
        # 1. convert self._m21Score to HumGrid
        # 2. convert HumGrid to HumdrumFile
        # 3. write HumdrumFile to fp

        # 888: Tool_musicxml2hum::convert loops over the parts, doing prepareVoiceMapping
        # 888: ...on each one, then calls reindexVoices.  m_maxstaff is computed as well.
        self._maxStaff = len(self._m21Score.parts)

        status: bool = True
        outgrid: HumGrid = HumGrid()

        status = status and self._stitchParts(outgrid, self._m21Score)
        if not status:
            return status

#         outgrid.removeRedundantClefChanges() # don't do this; we're not in the business of prettying things
#         outgrid.removeSibeliusIncipit()

        # transfer verse counts and dynamics boolean from staves to HumGrid:
        for p, partData in enumerate(self._scoreData.parts):
            for s, staffData in enumerate(partData.staves):
                if staffData.hasDynamics:
                    outgrid.setDynamicsPresent(p, s)
                verseCount: int = staffData.verseCount
                outgrid.setVerseCount(p, s, verseCount)

	    # transfer harmony counts from parts to HumGrid:
        # for p, partData in enumerate(self._scoreData.parts):
        #     harmonyCount: int = partData.harmonyCount
        #     outgrid.setHarmonyCount(p, harmonyCount)

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

        outfile: HumdrumFile = HumdrumFile()
        outgrid.transferTokens(outfile)

        self._addHeaderRecords(outfile)
        self._addFooterRecords(outfile)
        #888 self._addMeasureOneNumber(outfile)

        for hline in outfile.lines():
            hline.createLineFromTokens()

#         chord.run(outfile) # makes sure each note in the chord has the right stuff on it?

#         if self._hasOrnaments: # maybe outgrid.hasOrnaments? or m21Score.hasOrnaments?
#             trillspell.run(outfile) # figures out actual trill, mordent, turn type
                                      # based on current key and accidentals

        if self._hasTremolo and self.expandTremolos: # client can disable tremolo expansion
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
    def _printResult(fp, outfile: HumdrumFile):
        outfile.write(fp)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addFooterRecords --
    '''
    def _addFooterRecords(self, outfile: HumdrumFile):
        for definition, signifier in self._rdfKernSignifierLookup.items():
            rdfLine = f'!!!RDF**kern: {signifier} = '
            if isinstance(definition, tuple): # it's a tuple of k/v pairs
                # multiple definitions: key1, key2 = value2, key3, etc...
                for i, (k, v) in enumerate(definition):
                    if i > 0:
                        rdfLine += ', '
                    if v is None:
                        rdfLine += f'{k}'
                    elif v == '':
                        rdfLine += f'{k}='
                    else:
                        rdfLine += f'{k}="{v}"' # double quotes, or parse will include any following ','
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

    otherWorkIdLookupDict: dict = {
#        'composer': 'COM', # we do contributors NOT by workId
        'copyright': 'YEC',
        'date': 'ODT'
    }

    @staticmethod
    def _allMetadataAsTextObjects(m21Metadata: m21.metadata.Metadata) -> List[Tuple[str, m21.prebase.ProtoM21Object]]: # value can be m21.metadata.Text or m21.metadata.Date et al
        # this is straightup equivalent to Metadata.all(), but it (1) returns the full value
        # objects, so I can see the language codes for text, (2) doesn't delete title if
        # movementName is the same (dammit), and (3) I never want contributors.
        # To get the full objects I have to access _workIds directly instead of calling getattr,
        # which means I have to handle copyright and date separately.

        # pylint: disable=protected-access
        allOut = {}

        # first the real workIds
        for thisAttribute in sorted(set(m21Metadata.workIdAbbreviationDict.values())):
            val = m21Metadata._workIds.get(thisAttribute, None)

            if val == 'None' or not val:
                continue
            allOut[str(thisAttribute)] = val # NOT str(val), I want Text (or whatever), not str

        # then copyright and date (which are not stored in workIds)
        val = m21Metadata.copyright
        if val is not None and val != 'None':
            allOut['copyright'] = val

        val = m21Metadata._date # internal object for real Date object
        if val is not None and val != 'None':
            allOut['date'] = val

        # pylint: enable=protected-access
        return list(sorted(allOut.items()))

    @staticmethod
    def _emitContributorNameList(outfile: HumdrumFile, c: m21.metadata.Contributor, skipName: m21.metadata.Text=None):
        k: str = M21Convert.m21ContributorRoleToHumdrumReferenceKey.get(c.role, None)
        if k is None:
            print(f'music21 contributor role {c.role} maps to no Humdrum ref key', file=sys.stderr)
            return

        # pylint: disable=protected-access
        needToSkipOne: bool = skipName is not None
        skippedIt: bool = False
        for idx, v in enumerate(c._names):
            if needToSkipOne and v is skipName: # is, instead of ==.  Same object, not equal object
                skippedIt = True
                continue

            # We need to carefully manage the number suffix, since if there is a skipped name,
            # it has already been emitted with num=0 (no number suffix), so we can't use that
            # here.
            # if there is no skipped name, we can just use 0..n
            # if there is a skipped name (at index s), then the numbers we use must be:
            # indices: 0..s-1, s,    s+1..n
            # nums:    1..s,   skip, s+1..n
            # so the only tricky bit is if we have a skipName, and we haven't skipped it yet.
            # in that case, num must be idx + 1. In all other cases, num should be idx.
            num: int = idx
            if needToSkipOne and not skippedIt:
                num = idx+1

            vStr: str = '' # no name is cool if v is None
            langCode: str = ''
            if v is not None:
                vStr = str(v)
                langCode = v.language

            hdKey: str = k
            if num > 0:
                hdKey += str(num)

            if langCode:
                hdKey += '@' + langCode.upper()
            outfile.appendLine('!!!' + hdKey + ': ' + vStr, asGlobalToken=True)
        # pylint: enable=protected-access

    def _addHeaderRecords(self, outfile: HumdrumFile):
        systemDecoration: str = self._getSystemDecoration()
        if systemDecoration and systemDecoration != 's1':
            outfile.appendLine('!!!system-decoration: ' + systemDecoration, asGlobalToken=True)

        # pylint: disable=protected-access
        m21Metadata: m21.metadata.Metadata = self._m21Score.metadata
#        print('metadata = \n', m21Metadata.all(), file=sys.stderr)
        if m21Metadata is None:
            return

        # Top of Humdrum file is (in order):
        # 1. Composer(s): COM = m21Metadata.getContributorsByRole('composer')[0].name
        # 2. Title: OTL = metadata._workIds['title']
        # 3. Movement name: OMD = metadata._workIDs['movementName']
        # 4. Copyright: YEC = metadata.copyright
        firstComposerEmitted: m21.metadata.Contributor = None
        titleEmitted: bool = False
        movementNameEmitted: bool = False
        copyrightEmitted: bool = False

        atLine: int = 0
        composers: List[m21.metadata.Text] = m21Metadata.getContributorsByRole('composer')
        mdTitle: m21.metadata.Text = m21Metadata._workIds['title']
        mdMovementName: m21.metadata.Text = m21Metadata._workIds['movementName']
        mdCopyright: m21.metadata.Copyright = m21Metadata.copyright


        if composers:
            composer: m21.metadata.Contributor = composers[0]
            nameText: m21.metadata.Text = composer.names[0]

            # default to names[0], but if you can find a name
            # without a language, use that one instead (it's
            # probably the composer's name in their own language)
            for ntext in composer._names:
                if ntext.language is None:
                    nameText = ntext
                    break

            langCode: str = nameText.language
            hdKey: str = 'COM'
            if langCode:
                hdKey += '@' + langCode.upper()
            outfile.insertLine(atLine, '!!!' + hdKey + ': ' + str(nameText), asGlobalToken=True)
            atLine += 1
            firstComposerEmitted = nameText

        if mdTitle:
            langCode: str = mdTitle.language
            hdKey: str = 'OTL'
            if langCode:
                hdKey += '@' + langCode.upper()
            outfile.insertLine(atLine, '!!!' + hdKey + ': ' + str(mdTitle), asGlobalToken=True)
            atLine += 1
            titleEmitted = True

        if mdMovementName:
            langCode: str = mdMovementName.language
            hdKey: str = 'OMD'
            if langCode:
                hdKey += '@' + langCode.upper()
            outfile.insertLine(atLine, '!!!' + hdKey + ': ' + str(mdMovementName), asGlobalToken=True)
            atLine += 1
            movementNameEmitted = True

        if mdCopyright:
            langCode: str = mdCopyright.language
            hdKey: str = 'YEC'
            if langCode:
                hdKey += '@' + langCode.upper()
            outfile.insertLine(atLine, '!!!' + hdKey + ': ' + str(mdCopyright), asGlobalToken=True)
            atLine += 1
            copyrightEmitted = True

        # the rest of the workIds go at the bottom of the file
        titleSkipped: bool = False
        movementNameSkipped: bool = False
        copyrightSkipped: bool = False
        for workId, metaValue in self._allMetadataAsTextObjects(m21Metadata):
            if titleEmitted and not titleSkipped and workId == 'title':
                titleSkipped = True
                continue

            if movementNameEmitted and not movementNameSkipped and workId == 'movementName':
                movementNameSkipped = True
                continue

            if copyrightEmitted and not copyrightSkipped and workId == 'copyright':
                copyrightSkipped = True
                continue

            workIdKey: str = workId.lower()
            if workIdKey in m21.metadata.Metadata.workIdLookupDict:
                abbrev = m21.metadata.Metadata.workIdToAbbreviation(workIdKey)
                abbrev = abbrev.upper()
            elif workIdKey in HumdrumWriter.otherWorkIdLookupDict:
                abbrev = HumdrumWriter.otherWorkIdLookupDict[workIdKey]
            else:
                abbrev = workId

            hdKey: str = abbrev
            valueStr: str = ''
            if metaValue is not None:
                valueStr = str(metaValue)
            else:
                valueStr = '' # no string is cool

            if isinstance(metaValue, m21.metadata.DateSingle):
                # all metadata DateBlah types derive from DateSingle
                # We don't like str(DateBlah)'s results so we do our own.
                valueStr = M21Convert.stringFromM21DateObject(metaValue)
            elif isinstance(metaValue, m21.metadata.Text):
                langCode: str = metaValue.language
                if langCode:
                    hdKey += '@' + langCode.upper()

            outfile.appendLine('!!!' + hdKey + ': ' + valueStr, asGlobalToken=True)

        # contributors after the workIds, at the bottom of the file
        firstComposerSkipped: bool = False
        for c in m21Metadata.contributors:
            if (firstComposerEmitted is not None
                    and not firstComposerSkipped
                    and c.role == 'composer'
                    and firstComposerEmitted in c._names):
                # emit all but firstComposerEmitted from c.names
                self._emitContributorNameList(outfile, c, skipName=firstComposerEmitted)
                firstComposerSkipped = True
                continue

            # emit all contributor names from c.names
            self._emitContributorNameList(outfile, c)

        # metadata.editorial stuff (things that aren't supported by m21 metadata).
        # Put them at the bottom of the file, after all the other metadata
        if m21Metadata.hasEditorialInformation:
            for k, v in m21Metadata.editorial.items():
                if ' ' not in k and '\t' not in k: # can't do keys with space or tab in them!
                    hdKey: str = k
                    hdValue: str = str(v)
                    if hdKey.startswith('humdrum:'):
                        hdKey = hdKey[8:] # lose that 'humdrum:' prefix
                    colonBeforeValue: str = ': '
                    if hdValue == '':
                        colonBeforeValue = ':'
                    outfile.appendLine('!!!' + hdKey + colonBeforeValue + hdValue, asGlobalToken=True)
        # pylint: enable=protected-access

    def _getSystemDecoration(self) -> str:
        output: str = ''

        # Find all the StaffGroups in the score, and use sg.spannerStorage.elements (the parts)
        # as well as sg.symbol and sg.barTogether from each one to generate a 'sN'-based
        # system-decoration string.
        staffNumbersByM21Part: Dict[m21.stream.Part, int] = self._getGlobalStaffNumbersForM21Parts(
                                                                    self._scoreData)
        staffGroups: List[m21.layout.StaffGroup] = list(self.spannerBundle.getByClass('StaffGroup'))
        staffGroupTrees: List[M21StaffGroupTree] = self._getStaffGroupTrees(
                                                                staffGroups, staffNumbersByM21Part)

        for sgtree in staffGroupTrees:
            output, _ = self._appendRecursiveDecoString(output, sgtree)

        return output

    @staticmethod
    def _appendRecursiveDecoString(output: str, sgtree: M21StaffGroupTree) -> Tuple[str, List[int]]:
        if sgtree is None:
            return (output, [])
        if sgtree.numStaves == 0:
            return (output, [])

        preString: str = ''
        postString: str = ''
        symbol: str = sgtree.staffGroup.symbol
        barTogether: bool = sgtree.staffGroup.barTogether # might be 'mensurstrich'

        if symbol in M21Convert.m21GroupSymbolToHumdrumDecoGroupStyleStart:
            preString += M21Convert.m21GroupSymbolToHumdrumDecoGroupStyleStart[symbol]
            postString = M21Convert.m21GroupSymbolToHumdrumDecoGroupStyleStop[symbol] + postString

        if barTogether: # 'mensurstrich' will evaluate to True, which is OK...
            preString += '('
            postString = ')' + postString

        output += preString

        sortedStaffNums: List[int] = sorted(list(sgtree.staffNums))
        staffNumsToProcess: Set[int] = set(sortedStaffNums)
        staffNums: List[int] = []

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
            staffNumsProcessed: Set[int] = set(newStaffNums) # for speed of "in" checking
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
    def _getStaffGroupTrees(staffGroups: List[m21.layout.StaffGroup],
                            staffNumbersByM21Part: Dict[m21.stream.Part, int]
                           ) -> List[M21StaffGroupTree]:
        topLevelParents: List[M21StaffGroupTree] = []

        # Start with the tree being completely flat. Sort it by number of staves, so
        # we can bail early when searching for smallest parent, since the first one
        # we find will be the smallest.
        staffGroupTrees: List[M21StaffGroupTree] = (
                [M21StaffGroupTree(sg, staffNumbersByM21Part) for sg in staffGroups]
        )
        staffGroupTrees.sort(key=lambda tree: tree.numStaves)

        # Hook up each child node to the parent with the smallest superset of the child's staves.
        # If there is no parent with a superset of the child's staves at all, the child is actually
        # a top level parent.
        for child in staffGroupTrees:
            smallestParent: M21StaffGroupTree = None
            for parent in staffGroupTrees:
                if parent is child or parent in child.children:
                    continue

                if child.staffNums.issubset(parent.staffNums):
                    smallestParent = parent
                    break # we know it's smallest because they're sorted by size

            if smallestParent is None:
                topLevelParents.append(child)
            else:
                smallestParent.children.append(child)

        # Sort every list of siblings in the tree (including the
        # topLevelParents themselves) by lowest staff number, so
        # the staff numbers are in order.
        HumdrumWriter._sortStaffGroupTrees(topLevelParents)

        return topLevelParents

    @staticmethod
    def _sortStaffGroupTrees(trees: List[M21StaffGroupTree]):
        # Sort every list of siblings in the tree (including the
        # passed-in trees list itself) by lowest staff number.
        if not trees:
            return

        trees.sort(key=lambda tree: tree.lowestStaffNumber)
        for tree in trees:
            HumdrumWriter._sortStaffGroupTrees(tree.children)

    @staticmethod
    def _getGlobalStaffNumbersForM21Parts(scoreData: ScoreData) -> Dict[m21.stream.Part, int]:
        output: Dict[m21.stream.Part, int] = {}
        staffNumber: int = 0 # global staff numbers are 1-based
        for partData in scoreData.parts:
            for staffData in partData.staves:
                staffNumber += 1 # global staff numbers are 1-based
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
        measureCount: [int] = []
        for part in score.parts: # includes PartStaffs, too
            partCount += 1
            measureCount.append(0)
            for _ in part.getElementsByClass('Measure'):
                measureCount[-1] += 1

        if partCount == 0:
            return False

        mCount0 = measureCount[0]
        for mCount in measureCount:
            if mCount != mCount0:
                raise HumdrumExportError('ERROR: cannot handle parts with different measure counts')

        self._scoreData = ScoreData(score, self)

        # Now insert each measure into the HumGrid across those parts/staves
        status: bool = True
        for m in range(0, mCount0):
            status = status and self._insertMeasure(outgrid, m)

        self._moveBreaksToEndOfPreviousMeasure(outgrid)
        self._insertPartNames(outgrid)

        return status

    '''
    //////////////////////////////
    //
    // moveBreaksToEndOfPreviousMeasure --
    '''
    @staticmethod
    def _moveBreaksToEndOfPreviousMeasure(outgrid: HumGrid):
        for m in range(1, len(outgrid.measures)):
            gm: GridMeasure = outgrid.measures[m]
            gmlast: GridMeasure = outgrid.measures[m-1]
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

                token = gridSlice.parts[0].staves[0].voices[0].token
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
    def _insertPartNames(self, outgrid: HumGrid):
        hasName: bool = False
        hasAbbr: bool = False

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

        gm: GridMeasure = None
        if not outgrid.measures:
            gm = GridMeasure(outgrid)
            outgrid.measures.append(gm)
        else:
            gm = outgrid.measures[0]

        # We do abbreviation first, since addLabelAbbrToken and addLabelToken put the
        # token as early in the measure as possible, so the order will be reversed.
        if hasAbbr:
            for p, partData in enumerate(self._scoreData.parts):
                partAbbr: str = partData.partAbbrev
                if not partAbbr:
                    continue
                abbr: str = "*I'" + partAbbr
                maxStaff: int = outgrid.staffCount(p)
                s: int = maxStaff - 1 # put it in last staff (which is first on the Humdrum line)
                v: int = 0 # voice 0
                gm.addLabelAbbrToken(abbr, HumNum(0), p, s, v, self._scoreData.partCount)

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
                maxStaff: int = outgrid.staffCount(p)
                s: int = maxStaff - 1 # put it in last staff (which is first on the Humdrum line)
                v: int = 0 # voice 0
                gm.addLabelToken(iname, HumNum(0), p, s, v, self._scoreData.partCount)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::insertMeasure --
    '''
    def _insertMeasure(self, outgrid: HumGrid, mIndex: int):
        gm: GridMeasure = outgrid.appendMeasure()

        xmeasure: MeasureData = None
        measureDatas: [MeasureData] = []
        sevents: [[SimultaneousEvents]] = []

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
                    # only checking measure styles and number of first barline
                    gm.leftBarlineStyle = xmeasure.leftBarlineStyle
                    gm.rightBarlineStyle = xmeasure.rightBarlineStyle
                    gm.measureStyle = xmeasure.measureStyle
                    gm.measureNumberString = xmeasure.measureNumberString # might be '124a'

                # barline fermatas, on the other hand, need to be checked in every staff
                gm.fermataStylePerStaff.append(xmeasure.fermataStyle)
                gm.rightBarlineFermataStylePerStaff.append(xmeasure.rightBarlineFermataStyle)

        curTime: [HumNum] = [None] * len(measureDatas)
        measureDurs: [HumNum] = [None] * len(measureDatas)
        curIndex: [int] = [0] * len(measureDatas)
        nextTime: HumNum = HumNum(-1)

        tsDur: HumNum = HumNum(-1)
        for ps, mdata in enumerate(measureDatas):
            events: [EventData] = mdata.events
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
                    print(f'\tTOKEN: {event.kernTokenString(self.spannerBundle)}',
                                end='', file=sys.stderr)
                    print(f'\tNAME:  {event.name}', end='', file=sys.stderr)
                    print('', file=sys.stderr) # line feed (one line per event)
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
        nowEvents: [SimultaneousEvents] = []
#         nowPartStaves: [int] = []
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
            nextTime = HumNum(-1)
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
        #end loop over slices (i.e. events in the measure across all partstaves)

        if self._currentTexts or self._currentDynamics or self._currentTempos:
            # one more _addEvent (no slice, no event) to flush out these
            # things that have to be exported as a side-effect of the next
            # durational event (but we've hit end of measure, so there is
            # no such event to process, unless we're willing to let them
            # move to the next measure... which we are NOT).
            self._addEvent(None, gm, None, processTime)

        #888 if self._offsetHarmony:
            #888 self._insertOffsetHarmonyIntoMeasure(gm)
        #888 if self._offsetFiguredBass:
            #888 self._insertOffsetFiguredBassIntoMeasure(gm)

        return status

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::convertNowEvents --
    '''
    def _convertNowEvents(self, outgm: GridMeasure,
                          nowEvents: [SimultaneousEvents],
                          nowTime: HumNum) -> bool:
        if not nowEvents:
#             print('NOW EVENTS ARE EMPTY', file=sys.stderr)
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

        #if not nowEvents[0].nonZeroDur:
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
    def _appendZeroDurationEvents(self, outgm: GridMeasure,
                                  nowEvents: [SimultaneousEvents],
                                  nowTime: HumNum):
        hasClef:            bool = False
        hasKeySig:          bool = False
        hasKeyDesignation:  bool = False
        hasTransposition:   bool = False
        hasTimeSig:         bool = False
#        hasOttava:          bool = False
        hasStaffLines:      bool = False

        # These are all indexed by part, and include a staff index with each element
        # Some have further indexes for voice, and maybe note
        clefs: [[Tuple[int, m21.clef.Clef]]] = []
        keySigs: [[Tuple[int, m21.key.KeySignature]]] = []
        timeSigs: [[Tuple[m21.meter.TimeSignature]]] = []
        staffLines: [[Tuple[int, int]]] = [] # number of staff lines (if specified)
        transposingInstruments: [[Tuple[int, m21.instrument.Instrument]]] = []
#        hairPins: [[m21.dynamics.DynamicWedge]] = []
#        ottavas: [[[m21.spanner.Ottava]]] = []

        graceBefore: [[[[EventData]]]] = []
        graceAfter: [[[[EventData]]]] = []
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
                m21Obj: m21.base.Music21Object = zeroDurEvent.m21Object # getNode
                pindex: int = zeroDurEvent.partIndex
                sindex: int = zeroDurEvent.staffIndex
                vindex: int = zeroDurEvent.voiceIndex

                if 'Clef' in m21Obj.classes:
                    clefs[pindex].append((sindex, m21Obj))
                    hasClef = True
                    foundNonGrace = True
                elif 'Key' in m21Obj.classes or 'KeySignature' in m21Obj.classes:
                    keySigs[pindex].append((sindex, m21Obj))
                    hasKeySig = True
                    hasKeyDesignation = 'Key' in m21Obj.classes
                    foundNonGrace = True
                elif 'Instrument' in m21Obj.classes:
                    if M21Utilities.isTransposingInstrument(m21Obj):
                        transposingInstruments[pindex].append((sindex, m21Obj))
                        hasTransposition = True
                        foundNonGrace = True
                elif 'StaffLayout' in m21Obj.classes:
                    staffLines[pindex].append((sindex, m21Obj.staffLines))
                    hasStaffLines = True
                    foundNonGrace = True
                elif 'TimeSignature' in m21Obj.classes:
                    timeSigs[pindex].append((sindex, m21Obj))
                    hasTimeSig = True
                    hasMeterSig = M21Utilities.hasMeterSymbol(m21Obj)
                    foundNonGrace = True
                elif 'TextExpression' in m21Obj.classes:
                    # put in self._currentTexts, so it can be emitted
                    # during the immediately following call to
                    # appendNonZeroEvents() -> addEvent()
                    self._currentTexts.append((pindex, sindex, vindex, m21Obj))
                elif 'MetronomeMark' in m21Obj.classes:
                    self._currentTempos.append((pindex, m21Obj))
                elif 'Dynamic' in m21Obj.classes:
                    self._currentDynamics.append((pindex, sindex, m21Obj))
                    zeroDurEvent.reportDynamicToOwner()
#                 elif 'FiguredBass' in m21Obj.classes:
#                     self._currentFiguredBass.append(m21Obj)
                elif 'GeneralNote' in m21Obj.classes:
                    if foundNonGrace:
                        self._addEventToList(graceAfter, zeroDurEvent)
                    else:
                        self._addEventToList(graceBefore, zeroDurEvent)
                elif 'PageLayout' in m21Obj.classes or 'SystemLayout' in m21Obj.classes:
                    self._processPrintElement(outgm, m21Obj, nowTime)

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
    def _addEventToList(eventList: [[[[EventData]]]], event: EventData):
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
    def _addGraceLines(self, outgm: GridMeasure,
                             notes: List[List[List[List[EventData]]]],
                             nowTime: HumNum):
        maxGraceNoteCount: int = 0
        for staffList in notes: # notes is a list of staffLists, one staffList per part
            for voiceList in staffList:
                for noteList in voiceList:
                    if maxGraceNoteCount < len(noteList):
                        maxGraceNoteCount = len(noteList)

        if maxGraceNoteCount == 0:
            return

        slices: List[GridSlice] = []
        for _ in range(0, maxGraceNoteCount):
            slices.append(GridSlice(outgm, nowTime, SliceType.GraceNotes))
            outgm.slices.append(slices[-1])
            slices[-1].initializePartStaves(self._scoreData)

        for staffList in notes: # notes is a list of staffLists, one staffList per part
            for voiceList in staffList:
                for noteList in voiceList:
                    startn: int = maxGraceNoteCount - len(noteList)
                    for n, note in enumerate(noteList):
                        self._addEvent(slices[startn+n], outgm, note, nowTime)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addClefLine --
    '''
    def _addClefLine(self, outgm: GridMeasure, clefs: List[List[Tuple[int, m21.clef.Clef]]], nowTime: HumNum):
        gridSlice: GridSlice = GridSlice(outgm, nowTime, SliceType.Clefs)
        outgm.slices.append(gridSlice)
        gridSlice.initializePartStaves(self._scoreData)

        assert len(clefs) == len(gridSlice.parts), 'number of clef lists does not match number of parts'

        for p, partClefs in enumerate(clefs):
            if partClefs:
                self._insertPartClefs(partClefs, gridSlice.parts[p])

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addStriaLine --
    '''
    def _addStriaLine(self, outgm: GridMeasure, staffLines: List[List[Tuple[int, int]]], nowTime: HumNum):
        gridSlice: GridSlice = GridSlice(outgm, nowTime, SliceType.Stria)
        outgm.slices.append(gridSlice)
        gridSlice.initializePartStaves(self._scoreData)

        assert len(staffLines) == len(gridSlice.parts), 'number of staffLine lists does not match number of parts'

        for p, partStaffLines in enumerate(staffLines):
            if partStaffLines is not None:
                self._insertPartStria(partStaffLines, gridSlice.parts[p])

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addTimeSigLine --
    '''
    def _addTimeSigLine(self, outgm: GridMeasure,
                              timeSigs: List[List[Tuple[int, m21.meter.TimeSignature]]],
                              nowTime: HumNum,
                              hasMeterSig: bool):
        gridSlice: GridSlice = GridSlice(outgm, nowTime, SliceType.TimeSigs)
        outgm.slices.append(gridSlice)
        gridSlice.initializePartStaves(self._scoreData)

        for partTimeSigs, part in zip(timeSigs, gridSlice.parts):
            if partTimeSigs:
                self._insertPartTimeSigs(partTimeSigs, part)

        if not hasMeterSig:
            return

        # Add meter sigs related to time signatures (e.g. common time, cut time)
        gridSlice: GridSlice = GridSlice(outgm, nowTime, SliceType.MeterSigs)
        outgm.slices.append(gridSlice)
        gridSlice.initializePartStaves(self._scoreData)

        # now add meter sigs associated with time signatures
        # The m21 timesig object contains this (optional) info as well
        for partTimeSigs, part in zip(timeSigs, gridSlice.parts):
            if partTimeSigs:
                self._insertPartMeterSigs(partTimeSigs, part)

    def _insertPartTimeSigs(self, timeSigs: List[Tuple[int, m21.meter.TimeSignature]],
                                  part: GridPart):
        if part is None:
            return

        durationZero: HumNum = HumNum(0)
        voice0: int = 0
        for staffIdx, timeSig in timeSigs:
            token: HumdrumToken = M21Convert.timeSigTokenFromM21TimeSignature(timeSig)
            if token:
                staff = part.staves[staffIdx]
                staff.setTokenLayer(voice0, token, durationZero)

        # go back and fill in all None tokens with null interpretations
        self._fillEmpties(part, '*')

    def _insertPartMeterSigs(self, timeSigs: List[m21.meter.TimeSignature],
                                  part: GridPart):
        if part is None:
            return

        durationZero: HumNum = HumNum(0)
        voice0: int = 0
        for staffIdx, timeSig in timeSigs:
            token: HumdrumToken = M21Convert.meterSigTokenFromM21TimeSignature(timeSig)
            if token: # returns None if meterSig info doesn't exist
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
    def _addKeySigLine(self, outgm: GridMeasure,
                             keySigs: List[List[Tuple[int, Union[m21.key.KeySignature, m21.key.Key]]]],
                             nowTime: HumNum,
                             hasKeyDesignation: bool):
        gridSlice: GridSlice = GridSlice(outgm, nowTime, SliceType.KeySigs)
        outgm.slices.append(gridSlice)
        gridSlice.initializePartStaves(self._scoreData)

        for partKeySigs, part in zip(keySigs, gridSlice.parts):
            if partKeySigs:
                self._insertPartKeySigs(partKeySigs, part)

        # Add any key designations as well
        if not hasKeyDesignation:
            return

        gridSlice: GridSlice = GridSlice(outgm, nowTime, SliceType.KeyDesignations)
        outgm.slices.append(gridSlice)
        gridSlice.initializePartStaves(self._scoreData)

        for partKeySigs, part in zip(keySigs, gridSlice.parts):
            if partKeySigs:
                self._insertPartKeyDesignations(partKeySigs, part)

    def _insertPartKeySigs(self, keySigs: List[Tuple[int, Union[m21.key.KeySignature, m21.key.Key]]],
                                         part: GridPart):
        if part is None:
            return

        durationZero: HumNum = HumNum(0)
        voice0: int = 0
        for staffIdx, keySig in keySigs:
            token: HumdrumToken = M21Convert.keySigTokenFromM21KeySignature(keySig)
            if token:
                staff = part.staves[staffIdx]
                staff.setTokenLayer(voice0, token, durationZero)

        # go back and fill in all None tokens with null interpretations
        self._fillEmpties(part, '*')

    def _insertPartKeyDesignations(self, keySigs: List[Union[m21.key.KeySignature, m21.key.Key]],
                                         part: GridPart):
        if part is None:
            return

        durationZero: HumNum = HumNum(0)
        voice0: int = 0
        for staffIdx, keySig in keySigs:
            if isinstance(keySig, m21.key.Key): # we can only generate KeyDesignation from Key
                token: HumdrumToken = M21Convert.keyDesignationTokenFromM21KeySignature(keySig)
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
    def _addTranspositionLine(self, outgm: GridMeasure, transposingInstruments: List[List[Tuple[int, m21.instrument.Instrument]]], nowTime: HumNum):
        gridSlice: GridSlice = GridSlice(outgm, nowTime, SliceType.KeySigs)
        outgm.slices.append(gridSlice)
        gridSlice.initializePartStaves(self._scoreData)

        for partTransposingInstruments, part in zip(transposingInstruments, gridSlice.parts):
            if partTransposingInstruments:
                self._insertPartTranspositions(partTransposingInstruments, part)

    def _insertPartTranspositions(self,
                                  transposingInstruments: List[Tuple[int, m21.instrument.Instrument]],
                                  part: GridPart):
        if part is None:
            return

        durationZero: HumNum = HumNum(0)
        voice0: int = 0
        for staffIdx, inst in transposingInstruments:
            token: HumdrumToken = M21Convert.instrumentTransposeTokenFromM21Instrument(inst)
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
    def _insertPartClefs(self, clefs: List[Tuple[int, m21.clef.Clef]], part: GridPart):
        if part is None:
            return

        durationZero: HumNum = HumNum(0)
        voice0: int = 0
        for staffIdx, clef in clefs:
            token: HumdrumToken = M21Convert.clefTokenFromM21Clef(clef)
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
    def _insertPartStria(self, staffLineCounts: List[Tuple[int, int]], part: GridPart):
        if part is None:
            return

        durationZero: HumNum = HumNum(0)
        voice0: int = 0
        for staffIdx, lineCount in staffLineCounts:
            tokenStr: str = '*stria' + str(lineCount)
            staff = part.staves[staffIdx]
            staff.setTokenLayer(voice0, tokenStr, durationZero)

        # go back and fill in all None tokens with null interpretations
        self._fillEmpties(part, '*')

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::fillEmpties --
    '''
    @staticmethod
    def _fillEmpties(part: GridPart, string: str):
        durationZero: HumNum = HumNum(0)

        for staff in part.staves:
            if staff is None:
                print('staff is None in _fillEmpties', file=sys.stderr)
                continue

            voiceCount: int = len(staff.voices)
            if voiceCount == 0:
                gv: GridVoice = GridVoice(string, durationZero)
                staff.voices.append(gv)
            else:
                for v, gv in enumerate(staff.voices):
                    if gv is None:
                        gv = GridVoice(string, durationZero)
                        staff.voices[v] = gv
                    elif gv.token is None:
                        gv.token = HumdrumToken(string)

    @staticmethod
    def _processPrintElement(outgm: GridMeasure,
                             m21Obj: Union[m21.layout.PageLayout, m21.layout.SystemLayout],
                             nowTime: HumNum):
        isPageBreak: bool = isinstance(m21Obj, m21.layout.PageLayout) and m21Obj.isNew
        isSystemBreak: bool = isinstance(m21Obj, m21.layout.SystemLayout) and m21Obj.isNew

        if not isPageBreak and not isSystemBreak:
            return

        # C++ code (musicxml2hum) checks the last slice to see if it's already a page/system break
        # and does nothing if it is.  Maybe that's MusicXML-specific?  If music21 Score has multiple
        # page or system breaks in a row, it seems like I should honor that.
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
#             if token is None or token.text != '!!pagebreak:original':
            outgm.addGlobalComment('!!LO:PB:g=z', nowTime)
        elif isSystemBreak:
#             if token is None or token.text != '!!linebreak:original':
            outgm.addGlobalComment('!!LO:LB:g=z', nowTime)


    '''
    /////////////////////////////
    //
    // Tool_musicxml2hum::appendNonZeroEvents --
    '''
    def _appendNonZeroDurationEvents(self, outgm: GridMeasure,
                                           nowEvents: [SimultaneousEvents],
                                           nowTime: HumNum):
        outSlice: GridSlice = GridSlice(outgm, nowTime, SliceType.Notes)

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
        outSlice.initializePartStaves(self._scoreData)

        for ne in nowEvents:
            events: [EventData] = ne.nonZeroDur
            for event in events:
                self._addEvent(outSlice, outgm, event, nowTime)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addEvent -- Add a note or rest to a grid slice
    '''
    def _addEvent(self, outSlice: GridSlice, outgm: MeasureData, event: EventData, nowTime: HumNum):
        partIndex: int = None # event.partIndex
        staffIndex: int = None # event.staffIndex
        voiceIndex: int = None # event.voiceIndex

        if event is not None:
            partIndex = event.partIndex
            staffIndex = event.staffIndex
            voiceIndex = event.voiceIndex

        tokenString: str = ''
        layouts: [str] = []
        if event is None or not event.isDynamicWedgeStartOrStop:
            if event is not None:
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
                outSlice.parts[partIndex].staves[staffIndex].setTokenLayer(voiceIndex, token, event.duration)
                for layoutString in layouts:
                    outgm.addLayoutParameter(outSlice, partIndex, staffIndex, voiceIndex, layoutString)

                vcount: int = self._addLyrics(outgm, outSlice, partIndex, staffIndex, event)
                if vcount > 0:
                    event.reportVerseCountToOwner(vcount)

                hcount: int = self._addHarmony(outSlice.parts[partIndex], event, nowTime, partIndex)
                if hcount > 0:
                    event.reportHarmonyCountToOwner(hcount)

        # LATER: implement figured bass
        #         fcount: int = self._addFiguredBass(outSlice.parts[partIndex], event, nowTime, partIndex)
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
                self._addTexts(outSlice, outgm, event, self._currentTexts)
                self._currentTexts = [] # they've all been added

            if self._currentTempos:
                # self._currentTempos contains all the TempoIndications that could be in any part.
                # There is no event.tempos (music21 tempos are always unassociated).  But we take
                # the opportunity to add them now.
                self._addTempos(outSlice, outgm, self._currentTempos)
                self._currentTempos = [] # they've all been added

        if (event is not None and event.isDynamicWedgeStartOrStop) or self._currentDynamics:
            # self._currentDynamics contains any zero-duration (unassociated) dynamics ('pp' et al)
            # that could be in any part/staff.
            # event has a single dynamic wedge start or stop, that is in this part/staff.
            self._addDynamics(outSlice, outgm, event, self._currentDynamics)
            self._currentDynamics = []
            if event is not None and event.isDynamicWedgeStartOrStop:
                event.reportDynamicToOwner() # reports that dynamics exist in this part/staff

        # 888 might need special hairpin ending processing here (or might be musicXML-specific).

        # 888 might need postNoteText processing, but it looks like that's only for a case
        # 888 ... where '**blah' (a humdrum exInterp) occurs in a musicXML direction node. (Why?!?)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addDynamic -- extract any dynamics for the event
    '''
    @staticmethod
    def _addDynamics(outSlice: GridSlice, outgm: GridMeasure,
                     event: EventData, extraDynamics: List[Tuple[int, int, m21.dynamics.Dynamic]]):

        dynamics: List[Tuple[int, int, str]] = []

        eventIsDynamicWedge: bool = event is not None and event.isDynamicWedgeStartOrStop
        eventIsDynamicWedgeStart: bool = event is not None and event.isDynamicWedgeStart

        if eventIsDynamicWedge:
            dynamics.append((event.partIndex, event.staffIndex, event.getDynamicWedgeString()))

        for partIndex, staffIndex, dynamic in extraDynamics:
            dstring = M21Convert.getDynamicString(dynamic)
            dynamics.append((partIndex, staffIndex, dstring))

        if not dynamics:
            return # we shouldn't have been called

        dynTokens: Dict[Tuple[int, int], HumdrumToken] = {}
        moreThanOneDynamic: Dict[Tuple[int, int], bool] = {}
        currentDynamicIndex: Dict[Tuple[int, int], int] = {}

        for partIndex, staffIndex, dstring in dynamics:
            if not dstring:
                continue

            if dynTokens.get((partIndex, staffIndex), None) is None:
                dynTokens[(partIndex, staffIndex)] = HumdrumToken(dstring)
                moreThanOneDynamic[(partIndex, staffIndex)] = False
            else:
                dynTokens[(partIndex, staffIndex)].text += ' ' + dstring
                moreThanOneDynamic[(partIndex, staffIndex)] = True
                currentDynamicIndex[(partIndex, staffIndex)] = 1 # ':n=' is 1-based

        for (partIndex, staffIndex), token in dynTokens.items(): # key is Tuple[int, int], value is token
            if outSlice is None:
                # we better make one, timestamped at end of measure, type Notes (even though it
                # will only have '.' in the **kern spines, and a 'p' (or whatever) in the **dynam spine)
                outSlice = GridSlice(outgm, outgm.timestamp+outgm.duration, SliceType.Notes)
                outSlice.initializeBySlice(outgm.slices[-1])

            if outSlice.parts[partIndex].staves[staffIndex].dynamics is None:
                outSlice.parts[partIndex].staves[staffIndex].dynamics = token
            else:
                outSlice.parts[partIndex].staves[staffIndex].dynamics.text += ' ' + token.text
                moreThanOneDynamic[(partIndex, staffIndex)] = True
                currentDynamicIndex[(partIndex, staffIndex)] = 1 # ':n=' is 1-based

        # add any necessary layout params

        # first the one DynamicWedge start or stop that is this event (but only if it's a start)
        if eventIsDynamicWedgeStart:
            dparam: str = M21Convert.getDynamicWedgeStartParameters(event.m21Object)
            if dparam:
                fullParam: str = '!LO:HP'
                if moreThanOneDynamic[(partIndex, staffIndex)]:
                    fullParam += ':n=' + str(currentDynamicIndex[(partIndex, staffIndex)])
                    currentDynamicIndex[(partIndex, staffIndex)] += 1
                fullParam += dparam
                outgm.addDynamicsLayoutParameters(outSlice, partIndex, staffIndex, fullParam)

        # next the Dynamic objects ('pp', etc) in extraDynamics
        for partIndex, staffIndex, dynamic in extraDynamics:
            dparam: str = M21Convert.getDynamicParameters(dynamic)
            if dparam:
                fullParam: str = '!LO:DY'

                if moreThanOneDynamic[(partIndex, staffIndex)]:
                    fullParam += ':n=' + str(currentDynamicIndex[(partIndex, staffIndex)])
                    currentDynamicIndex[(partIndex, staffIndex)] += 1

                fullParam += dparam
                outgm.addDynamicsLayoutParameters(outSlice, partIndex, staffIndex, fullParam)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addTexts -- Add all text direction for a note.
    '''
    def _addTexts(self, outSlice: GridSlice,
                        outgm: GridMeasure,
                        event: EventData,
                        extraTexts: List[Tuple[int, int, int, m21.expressions.TextExpression]]):
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
    def _addText(outSlice: GridSlice, outgm: GridMeasure,
                 partIndex: int, staffIndex: int, voiceIndex: int,
                 textExpression: m21.expressions.TextExpression):
        textString: str = M21Convert.textLayoutParameterFromM21TextExpression(textExpression)
        outgm.addLayoutParameter(outSlice, partIndex, staffIndex, voiceIndex, textString)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addTempos -- Add tempo indication for a note.
    '''
    def _addTempos(self, outSlice: GridSlice,
                         outgm: GridMeasure,
                         tempos: List[Tuple[int, m21.tempo.TempoIndication]]):
        # we have to deduplicate because sometimes MusicXML export from music21 adds
        # extra metronome marks when exporting from PartStaffs.
        # We only want one metronome mark in this slice, preferably in the top-most part
        # We'll be content with the highest partIndex seen.
        # Note: The original routine over-deleted if there were multiple _different_ metronome marks.
        # This is now rewritten to only delete actual duplicates. --gregc
        # And now de-duplication is disabled; it was causing more problems than it was worth.
        emittedTempos: List[m21.tempo.TempoIndication] = []

        # First, sort by partIndex (highest first)
        # Then loop over all the tempos, adding only the first one you see of each unique mark
        def partIndexOf(tempo: Tuple[int, m21.tempo.TempoIndication]) -> int:
            return tempo[0]

        def isAlreadyEmitted(_tempo: m21.tempo.TempoIndication) -> bool:
            return False # disable de-duplication to see if it causes any problems (helps with a few scores)
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
    def _addTempo(self, outSlice: GridSlice, outgm: GridMeasure, partIndex: int,
                  tempoIndication: m21.tempo.TempoIndication):
        mmTokenStr: str = ''      # '*MM128' for example
        tempoTextLayout: str = '' # '!LO:TX:a:t=[eighth]=82', or '!LO:TX:t=Andantino [eighth]=82', for example
        mmTokenStr, tempoTextLayout = M21Convert.getMMTokenAndTempoTextLayoutFromM21TempoIndication(
                                            tempoIndication)
        staffIndex: int = 0
        voiceIndex: int = 0
        if mmTokenStr:
            outgm.addTempoToken(mmTokenStr, outSlice.timestamp,
                                partIndex, staffIndex, voiceIndex,
                                self._maxStaff)

        if tempoTextLayout:
            outgm.addLayoutParameter(outSlice, partIndex, staffIndex, voiceIndex, tempoTextLayout)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addLyrics --
    '''
    def _addLyrics(self,
                   outgm: GridMeasure,
                   outSlice: GridSlice,
                   partIndex: int,
                   staffIndex: int,
                   event: EventData) -> int:
        staff: GridStaff = outSlice.parts[partIndex].staves[staffIndex]
        gnote: m21.note.GeneralNote = event.m21Object
        verses: List[m21.note.Lyric] = []
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
                verses[number-1] = lyric
            elif number > 0:
                # more than one off the end, fill in with empty slots
                oldLen: int = len(verses)
                newLen: int = number
                for _ in range(oldLen, newLen):
                    verses.append(None)
                verses[number-1] = lyric

        # now, in number order (with maybe some empty slots)
        vLabelTokens: List[HumdrumToken] = [None] * len(verses)
        thereAreVerseLabels: bool = False

        for i, verse in enumerate(verses):
            verseText: str = None
            verseLabel: str = None
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
                    verseLabel = verse.identifier

            if verseLabel:
                vLabelTokens[i] = HumdrumToken('*v:' + verseLabel)
                thereAreVerseLabels = True

            verseToken: HumdrumToken = None
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
    def _addHarmony(self, part: GridPart,  #LATER: needs implementation
                          event: EventData,
                          nowTime: HumNum,
                          partIndex: int) -> int:
        if self or part or event or nowTime or partIndex:
            return 0
        return 0

    '''
        _makeScoreFromObject (et al) are here to turn any ProtoM21Object into a well-formed Score/Part/Measure/whatever stream.  stream.makeNotation will also be called.  Clients can avoid
        this if they init with a Score, and set self.makeNotation to False before calling write().
    '''
    def _makeScoreFromObject(self, obj: m21.base.Music21Object) -> m21.stream.Score:
        classes = obj.classes
        outScore: m21.stream.Score = None
        for cM, methName in self._classMapping.items():
            if cM in classes:
                meth = getattr(self, methName)
                outScore = meth(obj)
                break
        if outScore is None:
            raise HumdrumExportError(
                f'Cannot translate {obj} to a well-formed Score; put it in a Stream first!')

        return outScore

    @staticmethod
    def _fromScore(sc: m21.stream.Score) -> m21.stream.Score:
        '''
            From a score, make a new, perhaps better notated score
        '''
        scOut = sc.makeNotation(inPlace=False)
        if not scOut.isWellFormedNotation():
            print(f'{scOut} is not well-formed; see isWellFormedNotation()', file=sys.stderr)
        return scOut

    def _fromPart(self, p: m21.stream.Part) -> m21.stream.Score:
        '''
        From a part, put it in a new, better notated score.
        '''
        if p.isFlat:
            p = p.makeMeasures()
        s = m21.stream.Score()
        s.insert(0, p)
        s.metadata = copy.deepcopy(self._getMetadataFromContext(p))
        return self._fromScore(s)

    def _fromMeasure(self, m: m21.stream.Measure) -> m21.stream.Score:
        '''
        From a measure, put it in a part, then in a new, better notated score
        '''
        mCopy = m.makeNotation()
        if not m.recurse().getElementsByClass('Clef').getElementsByOffset(0.0):
            mCopy.clef = m21.clef.bestClef(mCopy, recurse=True)
        p = m21.stream.Part()
        p.append(mCopy)
        p.metadata = copy.deepcopy(self._getMetadataFromContext(m))
        return self._fromPart(p)

    def _fromVoice(self, v: m21.stream.Voice) -> m21.stream.Score:
        '''
        From a voice, put it in a measure, then a part, then a score
        '''
        m = m21.stream.Measure(number=1)
        m.insert(0, v)
        return self._fromMeasure(m)

    def _fromStream(self, st: m21.stream.Stream) -> m21.stream.Score:
        '''
        From a stream (that is not a voice, measure, part, or score), make an educated guess
        at it's structure, and do the appropriate thing to wrap it in a score.
        '''
        if st.isFlat:
            # if it's flat, treat it like a Part (which will make measures)
            st2 = m21.stream.Part()
            st2.mergeAttributes(st)
            st2.elements = copy.deepcopy(st)
            if not st.getElementsByClass('Clef').getElementsByOffset(0.0):
                st2.clef = m21.clef.bestClef(st2)
            st2.makeNotation(inPlace=True)
            st2.metadata = copy.deepcopy(self._getMetadataFromContext(st))
            return self._fromPart(st2)

        if st.hasPartLikeStreams():
            # if it has part-like streams, treat it like a Score
            st2 = m21.stream.Score()
            st2.mergeAttributes(st)
            st2.elements = copy.deepcopy(st)
            st2.makeNotation(inPlace=True)
            st2.metadata = copy.deepcopy(self._getMetadataFromContext(st))
            return self._fromScore(st2)

        if st.getElementsByClass('Stream').first().isFlat:
            # like a part w/ measures...
            st2 = m21.stream.Part()
            st2.mergeAttributes(st)
            st2.elements = copy.deepcopy(st)
            bestClef = not st.getElementsByClass('Clef').getElementsByOffset(0.0)
            st2.makeNotation(inPlace=True, bestClef=bestClef)
            st2.metadata = copy.deepcopy(self._getMetadataFromContext(st))
            return self._fromPart(st2)

        # probably a problem? or a voice...
        bestClef = not st.getElementsByClass('Clef').getElementsByOffset(0.0)
        st2 = st.makeNotation(inPlace=False, bestClef=bestClef)
        return self._fromScore(st2)

    def _fromGeneralNote(self, n: m21.note.GeneralNote) -> m21.stream.Score:
        '''
        From a note/chord/rest, put it in a measure/part/score
        '''
        # make a copy, as this process will change tuple types
        # this method is called infrequently, and only for display of a single
        # note
        nCopy = copy.deepcopy(n)

        # modifies in place
        m21.stream.makeNotation.makeTupletBrackets([nCopy.duration], inPlace=True)
        out = m21.stream.Measure(number=1)
        out.append(nCopy)
        return self._fromMeasure(out)

    def _fromPitch(self, p: m21.pitch.Pitch) -> m21.stream.Score:
        '''
        From a pitch, put it in a note, then put that in a measure/part/score
        '''
        n = m21.note.Note()
        n.pitch = copy.deepcopy(p)
        out = m21.stream.Measure(number=1)
        out.append(n)
        # call the musicxml property on Stream
        return self._fromMeasure(out)

    def _fromDuration(self, d: m21.duration.Duration) -> m21.stream.Score:
        '''
        Rarely rarely used.  Only if you call .show() on a duration object
        '''
        # make a copy, as we this process will change tuple types
        # not needed, since fromGeneralNote does it too.  but so
        # rarely used, it doesn't matter, and the extra safety is nice.
        dCopy = copy.deepcopy(d)
        n = m21.note.Note()
        n.duration = dCopy
        # call the musicxml property on Stream
        return self._fromGeneralNote(n)

    def _fromDynamic(self, dynamicObject: m21.dynamics.Dynamic) -> m21.stream.Score:
        '''
        Rarely rarely used.  Only if you call .show() on a dynamic object
        '''
        dCopy = copy.deepcopy(dynamicObject)
        out = m21.stream.Stream()
        out.append(dCopy)
        return self._fromStream(out)

    def _fromDiatonicScale(self, diatonicScaleObject: m21.scale.DiatonicScale) -> m21.stream.Score:
        '''
        Generate the pitches from this scale
        and put it into a stream.Measure, then call
        fromMeasure on it.
        '''
        m = m21.stream.Measure(number=1)
        for i in range(1, diatonicScaleObject.abstract.getDegreeMaxUnique() + 1):
            p = diatonicScaleObject.pitchFromDegree(i)
            n = m21.note.Note()
            n.pitch = p
            if i == 1:
                n.addLyric(diatonicScaleObject.name)

            if p.name == diatonicScaleObject.getTonic().name:
                n.quarterLength = 4  # set longer
            elif p.name == diatonicScaleObject.getDominant().name:
                n.quarterLength = 2  # set longer
            else:
                n.quarterLength = 1
            m.append(n)
        m.timeSignature = m.bestTimeSignature()
        return self._fromMeasure(m)

    def _fromScale(self, scaleObject: m21.scale.Scale) -> m21.stream.Score:
        '''
        Generate the pitches from this scale
        and put it into a stream.Measure, then call
        fromMeasure on it.
        '''
        m = m21.stream.Measure(number=1)
        for i in range(1, scaleObject.abstract.getDegreeMaxUnique() + 1):
            p = scaleObject.pitchFromDegree(i)
            n = m21.note.Note()
            n.pitch = p
            if i == 1:
                n.addLyric(scaleObject.name)

            if p.name == scaleObject.getTonic().name:
                n.quarterLength = 4  # set longer
            else:
                n.quarterLength = 1
            m.append(n)
        m.timeSignature = m.bestTimeSignature()
        return self._fromMeasure(m)

    def _fromMusic21Object(self, obj):
        '''
        return things such as a single TimeSignature as a score
        '''
        objCopy = copy.deepcopy(obj)
        out = m21.stream.Measure(number=1)
        out.append(objCopy)
        return self._fromMeasure(out)

    @staticmethod
    def _getMetadataFromContext(s: m21.stream.Stream):
        '''
        Get metadata from site or context, so that a Part
        can be shown and have the rich metadata of its Score
        '''
        # get metadata from context.
        md = s.metadata
        if md is not None:
            return md

        for contextSite in s.contextSites():
            if contextSite.site.metadata is not None:
                return contextSite.site.metadata
        return None
