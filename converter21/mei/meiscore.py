# ------------------------------------------------------------------------------
# Name:          meiscore.py
# Purpose:       MeiScore is an object that takes a music21 Score and
#                organizes its objects in an MEI-like structure.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
import typing as t
from xml.etree.ElementTree import Element  # , TreeBuilder

import music21 as m21
from music21.common import opFrac
from music21.common import OffsetQL

# from converter21.mei import MeiExportError
from converter21.mei import MeiInternalError
from converter21.mei import MeiMetadataItem
from converter21.mei import MeiMetadata
from converter21.mei import MeiMeasure
from converter21.mei import M21ObjectConvert
from converter21.shared import M21TemporarySpanner
from converter21.shared import M21BeamSpanner
from converter21.shared import M21TupletSpanner
from converter21.shared import M21TieSpanner
from converter21.shared import M21Utilities
from converter21.shared import M21StaffGroupTree
from converter21.shared import DebugTreeBuilder as TreeBuilder  # put this back before shipping

environLocal = m21.environment.Environment('converter21.mei.meiscore')

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class MeiScore:
    def __init__(self, m21Score: m21.stream.Score, meiVersion: str) -> None:
        def getUniqueVoiceIds(part: m21.stream.Part) -> list[int | str]:
            output: list[int | str] = ['']  # fake id for Measure
            for meas in part[m21.stream.Measure]:
                for voice in meas.voices:
                    if voice.id not in output:
                        output.append(voice.id)
            return output

        self.m21Score: m21.stream.Score = m21Score
        self.meiVersion: str = meiVersion

        self.customM21AttrsToDelete: dict[m21.base.Music21Object, list[str]] = {}

        self.currentTupletSpanners: dict[m21.stream.Part, list[M21TupletSpanner]] = {}
        self.currentTieSpanners: dict[m21.stream.Part, list[tuple[M21TieSpanner, int]]] = {}

        # we assume beams do not cross voice ids within the part. (This will still be true
        # when we eventually support cross-part beaming... the voice id will still match.)
        self.previousBeamedNoteOrChord: dict[
            tuple[m21.stream.Part, int | str],
            m21.note.NotRest | None
        ] = {}
        self.currentBeamSpanners: dict[
            tuple[m21.stream.Part, int | str],
            list[M21BeamSpanner]
        ] = {}

        for part in self.m21Score.parts:
            self.currentTupletSpanners[part] = []
            self.currentTieSpanners[part] = []
            voiceIds: list[int | str] = getUniqueVoiceIds(part)
            for voiceId in voiceIds:
                self.currentBeamSpanners[(part, voiceId)] = []
                self.previousBeamedNoteOrChord[(part, voiceId)] = None

        # pre-scan of m21Score to set up some things
        self.annotateScore()

        # annotateScore put a bunch of stuff in the spannerBundle, so we can't
        # copy it until now.  Which is just in time, since makeXmlIds/assureAllXmlIds needs it.
        self.spannerBundle = self.m21Score.spannerBundle

        # once annotated, check to see if any of these objects need xml:id.
        # self.makeXmlIds()

        # Actually, put an xml:id on every single Music21Object in the score.
        M21Utilities.assureAllXmlIds(self.m21Score)

        self.scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature] = (
            self.m21Score.getTimeSignatures(
                returnDefault=True,
                searchContext=False,
                sortByCreationTime=False
            )
        )

        self.staffNumbersForM21Parts: dict[m21.stream.Part, int] = (
            self._getStaffNumbersForM21Parts()
        )
        self.m21PartsForStaffNumbers: dict[int, m21.stream.Part] = {
            value: key for key, value in self.staffNumbersForM21Parts.items()
        }

        self.staffGroupTrees: list[M21StaffGroupTree] = (
            M21Utilities.getStaffGroupTrees(
                list(m21Score[m21.layout.StaffGroup]),
                self.staffNumbersForM21Parts,
            )
        )

        self.measures: list[MeiMeasure] = self._getMeiMeasures()
        self.metadata: MeiMetadata = MeiMetadata(m21Score.metadata)

    def _getStaffNumbersForM21Parts(self) -> dict[m21.stream.Part, int]:
        # If this routine ever changes the fact that staff numbers are in the same
        # monotonically increasing order as m21Score.parts, starting at 1, incrementing
        # by 1 for each Part, then makeStaffGrpOrStaffDefElementStartingAt() will need
        # to be updated to match (it counts on that fact).
        output: dict[m21.stream.Part, int] = {}
        for staffIdx, part in enumerate(self.m21Score.parts):
            output[part] = staffIdx + 1  # staff numbers are 1-based
        return output

    def _getMeiMeasures(self) -> list[MeiMeasure]:
        output: list[MeiMeasure] = []

        # OffsetIterator is not recursive, so we have to recursively pull all the measures
        # into one single stream, before we can use OffsetIterator to generate the "stacks"
        # of Measures that all occur at the same offset (moment) in the score.
        measuresStream: m21.stream.Stream[m21.stream.Measure] = (
            self.m21Score.recurse().getElementsByClass(m21.stream.Measure).stream()
        )
        offsetIterator: m21.stream.iterator.OffsetIterator[m21.stream.Measure] = (
            m21.stream.iterator.OffsetIterator(measuresStream)
        )
        meiMeas: MeiMeasure | None = None
        for measureStack in offsetIterator:
            prevMeiMeasure: MeiMeasure | None = meiMeas
            meiMeas = MeiMeasure(
                measureStack,
                prevMeiMeasure,
                self,
                self.customM21AttrsToDelete,
                self.spannerBundle)
            output.append(meiMeas)

        return output

    def makeRootElement(self) -> Element:
        tb: TreeBuilder = TreeBuilder(insert_comments=True, insert_pis=True)
        if self.meiVersion.startswith('4'):
            tb.start('mei', {
                'xmlns': 'http://www.music-encoding.org/ns/mei',
                'meiversion': '4.0.1'
            })
        elif self.meiVersion.startswith('5'):
            tb.start('mei', {
                'xmlns': 'http://www.music-encoding.org/ns/mei',
                'meiversion': '5.0+CMN'
            })

        # meiHead
        self.metadata.makeRootElement(tb)

        if self.metadata.mainWorkXmlId:
            tb.start('music', {'decls': '#' + self.metadata.mainWorkXmlId})
        else:
            tb.start('music', {})
        tb.start('body', {})
        tb.start('mdiv', {})

        tb.start('score', {})
        self.makeScoreDefElement(tb)

        tb.start('section', {})
        for meim in self.measures:
            meim.makeRootElement(tb)
        tb.end('section')

        tb.end('score')

        tb.end('mdiv')
        tb.end('body')

        # There's one bit of metadata that goes in music/back/div@type="textTranslation":
        # humdrum:HTX
        htxItems: list[MeiMetadataItem] = self.metadata.contents.get('HTX', [])
        if htxItems:
            allTheSameLanguage: bool
            theLanguage: str | None
            theLanguage, allTheSameLanguage = MeiMetadata.getTextListLanguage(htxItems)

            tb.start('back', {})
            tb.start('div', {'type': 'textTranslation'})
            if allTheSameLanguage and theLanguage:
                tb.start('lg', {'xml:lang': theLanguage})
            else:
                tb.start('lg', {})

            for htxItem in htxItems:
                # <l> can't take @analog, so use @type instead (says Perry)
                attrib: dict[str, str] = {'type': 'humdrum:HTX'}
                if isinstance(htxItem.value, m21.metadata.Text):
                    if htxItem.value.language and not allTheSameLanguage:
                        attrib['xml:lang'] = htxItem.value.language.lower()
                tb.start('l', attrib)
                tb.data(htxItem.meiValue)
                tb.end('l')
            tb.end('lg')
            tb.end('div')
            tb.end('back')

        tb.end('music')
        tb.end('mei')
        root: Element = tb.close()
        return root

    def makeStaffDefElement(
        self,
        part: m21.stream.Part,
        staffN: int,
        tb: TreeBuilder
    ):
        # staffLines (defaults to 5)
        staffLines: int = 5
        initialStaffLayout: m21.layout.StaffLayout | None = None
        initialStaffLayouts = list(
            part.recurse()
            .getElementsByClass(m21.layout.StaffLayout)
            .getElementsByOffsetInHierarchy(0.0)
        )
        if initialStaffLayouts:
            initialStaffLayout = initialStaffLayouts[0]
        if initialStaffLayout and initialStaffLayout.staffLines is not None:
            staffLines = initialStaffLayout.staffLines

        tb.start('staffDef', {
            'n': str(staffN),
            'lines': str(staffLines)
        })

        # clef
        clef: m21.clef.Clef | None = part.clef
        if clef is None:
            clefs: list[m21.clef.Clef] = list(
                part.recurse()
                .getElementsByClass(m21.clef.Clef)
                .getElementsByOffsetInHierarchy(0.0)
            )
            if clefs:
                clef = clefs[0]
        if clef is not None:
            M21ObjectConvert.m21ClefToMei(clef, self.spannerBundle, tb)
            clef.mei_handled_already = True  # type: ignore
            M21Utilities.extendCustomM21Attributes(
                self.customM21AttrsToDelete,
                clef,
                ['mei_handled_already']
            )
        else:
            environLocal.warn(f'No initial clef found in part {staffN}')

        # key signature
        keySig: m21.key.KeySignature | None = part.keySignature
        if keySig is None:
            keySigs: list[m21.key.KeySignature] = list(
                part.recurse()
                .getElementsByClass(m21.key.KeySignature)
                .getElementsByOffsetInHierarchy(0.0)
            )
            if keySigs:
                keySig = keySigs[0]
        if keySig is not None:
            M21ObjectConvert.m21KeySigToMei(keySig, self.spannerBundle, tb)
            keySig.mei_handled_already = True  # type: ignore
            M21Utilities.extendCustomM21Attributes(
                self.customM21AttrsToDelete,
                keySig,
                ['mei_handled_already']
            )
        else:
            environLocal.warn(f'No initial key signature found in part {staffN}')

        # time signature
        meterSig: m21.meter.TimeSignature | None = part.timeSignature
        if meterSig is None:
            meterSigs: list[m21.meter.TimeSignature] = list(
                part.recurse()
                .getElementsByClass(m21.meter.TimeSignature)
                .getElementsByOffsetInHierarchy(0.0)
            )
            if meterSigs:
                meterSig = meterSigs[0]
        if meterSig is not None:
            M21ObjectConvert.m21TimeSigToMei(meterSig, self.spannerBundle, tb)
            meterSig.mei_handled_already = True  # type: ignore
            M21Utilities.extendCustomM21Attributes(
                self.customM21AttrsToDelete,
                meterSig,
                ['mei_handled_already']
            )
        else:
            environLocal.warn(f'No initial time signature found in part {staffN}')

        tb.end('staffDef')

    _M21_STAFFGROUP_SYMBOL_TO_MEI: dict[str | None, str] = {
        # m21 symbol can be 'brace', 'bracket', 'square', 'line', None
        # mei symbol can be 'brace', 'bracket', 'bracketsq', 'line', 'none'
        'brace': 'brace',
        'bracket': 'bracket',
        'square': 'bracketsq',
        'line': 'line',
        None: 'none'
    }

    def makeStaffGrpElement(self, sgtree: M21StaffGroupTree, tb: TreeBuilder) -> list[int]:
        attr: dict[str, str] = {}
        if sgtree.staffGroup.name:
            attr['label'] = sgtree.staffGroup.name
        elif sgtree.staffGroup.abbreviation:
            attr['label'] = sgtree.staffGroup.abbreviation

        if sgtree.staffGroup.barTogether == 'Mensurstrich':
            attr['bar.method'] = 'mensur'
        elif sgtree.staffGroup.barTogether is False:
            attr['bar.thru'] = 'false'
        elif sgtree.staffGroup.barTogether is True:
            attr['bar.thru'] = 'true'

        attr['symbol'] = self._M21_STAFFGROUP_SYMBOL_TO_MEI[sgtree.staffGroup.symbol]

        tb.start('staffGrp', attr)

        part: m21.stream.Part
        staffNumsToProcess: set[int] = set(sgtree.staffNums)
        staffNums: list[int] = []
        for subgroup in sgtree.children:
            # 1. any staffNums before this subgroup
            for staffNum in sgtree.staffNums:
                if staffNum >= subgroup.lowestStaffNumber:
                    # we're done with staffNums before this subgroup
                    break

                if staffNum not in staffNumsToProcess:
                    # we already did this one
                    continue

                part = self.m21PartsForStaffNumbers[staffNum]
                self.makeStaffDefElement(part, staffNum, tb)
                staffNumsToProcess.remove(staffNum)
                staffNums.append(staffNum)

            # 2. now the subgroup
            newStaffNums: list[int] = self.makeStaffGrpElement(subgroup, tb)
            staffNumsProcessed: set[int] = set(newStaffNums)  # for speed of "in" checking
            staffNumsToProcess = set(num for num in staffNumsToProcess
                                            if num not in staffNumsProcessed)
            staffNums += newStaffNums

        # 3. any staffNums at the end after all the subgroups
        remainder: list[int] = sorted(list(staffNumsToProcess))
        for staffNum in remainder:
            part = self.m21PartsForStaffNumbers[staffNum]
            self.makeStaffDefElement(part, staffNum, tb)
            staffNumsToProcess.remove(staffNum)
            staffNums.append(staffNum)

        tb.end('staffGrp')
        staffNums.sort()
        return staffNums

    def _findTopStaffGroupTreeStartingWith(self, staffNum: int) -> M21StaffGroupTree | None:
        # self.staffGroupTrees is sorted by numStaves, so we need the last tree we saw
        # to get the topmost staffGroupTree that starts with staffNum.
        topTreeSoFar: M21StaffGroupTree | None = None
        for sgTree in self.staffGroupTrees:
            if sgTree.lowestStaffNumber == staffNum:
                topTreeSoFar = sgTree
        return topTreeSoFar

    def makeStaffGrpOrStaffDefElementStartingAt(self, staffNum: int, tb: TreeBuilder) -> int:
        # Assumption: staff numbers are in the same monotonically increasing order
        # as m21Score.parts, starting at 1, incrementing by 1 for each Part.  This
        # assumption can be seen to be true in _getStaffNumbersForM21Parts().
        sgTree: M21StaffGroupTree | None = self._findTopStaffGroupTreeStartingWith(staffNum)
        if sgTree is None:
            m21Part: m21.stream.Part = self.m21PartsForStaffNumbers[staffNum]
            self.makeStaffDefElement(m21Part, staffNum, tb)
            return staffNum + 1

        staffNums: list[int] = self.makeStaffGrpElement(sgTree, tb)
        return staffNums[-1] + 1

    def _nonGroupedStavesExist(self) -> bool:
        groupedStaffNums: set[int] = set()
        for sgTree in self.staffGroupTrees:
            groupedStaffNums.update(sgTree.staffNums)
        for sn in self.m21PartsForStaffNumbers:
            if sn not in groupedStaffNums:
                return True
        return False


    def makeScoreDefElement(self, tb: TreeBuilder) -> None:
        tb.start('scoreDef', {})
        madeFakeTopLevelStaffGrp: bool = False
        if len(self.staffGroupTrees) > 1 or self._nonGroupedStavesExist():
            # we'll need a top-level staffGrp to hold the multiple staffGroups/staffDefs
            # (just make it out of thin air)
            tb.start('staffGrp', {})
            madeFakeTopLevelStaffGrp = True

        nextStaffNum: int = 1
        while nextStaffNum in self.m21PartsForStaffNumbers:
            nextStaffNum = self.makeStaffGrpOrStaffDefElementStartingAt(nextStaffNum, tb)

        if madeFakeTopLevelStaffGrp:
            # close out the top-level staffGrp we made out of thin air
            tb.end('staffGrp')

        tb.end('scoreDef')

    def annotateScore(self) -> None:
        # self.spannerBundle has not yet been set, so make a copy of the spannerBundle
        # that was imported, for use during fillOttavas.
        spannerBundleForOttavas: m21.spanner.SpannerBundle = self.m21Score.spannerBundle

        for part in self.m21Score.parts:
            partTieSpanners: list[tuple[M21TieSpanner, int]] = self.currentTieSpanners[part]
            for measure in part:
                if not isinstance(measure, m21.stream.Measure):
                    continue

                # check/increment numMeasuresSearched in all part tie spanners
                defunctTieSpanners: list[tuple[M21TieSpanner, int]] = []
                for i, (sp, numMeasuresSearched) in enumerate(partTieSpanners):
                    if numMeasuresSearched >= 2:
                        defunctTieSpanners.append((sp, numMeasuresSearched))
                    else:
                        partTieSpanners[i] = (sp, numMeasuresSearched + 1)
                for sp, numMeasuresSearched in defunctTieSpanners:
                    partTieSpanners.remove((sp, numMeasuresSearched))

                voices: list[m21.stream.Voice | m21.stream.Measure] = (
                    list(measure[m21.stream.Voice])
                )
                if not voices:
                    voices = [measure]
                for voice in voices:
                    voiceId: int | str
                    if isinstance(voice, m21.stream.Measure):
                        voiceId = ''
                    else:
                        voiceId = voice.id

                    for obj in voice:
                        self.annotateBeams(obj, part, voiceId)
                        self.annotateTuplets(obj, part)
                        self.annotateTies(obj, part)
                        self.annotatePositionedRests(obj, part)
                        self.fillOttavas(obj, part, spannerBundleForOttavas)

                    if self.currentTupletSpanners[part]:
                        # assume tuplets end at end of each voice
                        self.currentTupletSpanners[part] = []

                if partTieSpanners:
                    # We must have encountered a stop in a voice before we encountered the
                    # start in a different voice.  Just run through the voices again,
                    # looking for tie stops only, to pick up any we missed.
                    for voice in voices:
                        for obj in voice:
                            self.annotateTies(obj, part, stopsOnly=True)

                if self.currentTupletSpanners[part]:
                    # We have at least one missing tuplet stop.  Assume all tuplets stop
                    # at end of measure. This isn't strictly true, but iohumdrum.cpp makes
                    # the same assumption (never producing a <tupletSpan>).
                    self.currentTupletSpanners[part] = []

        # print('done annotating score')

    def annotatePositionedRests(
        self,
        obj: m21.base.Music21Object,
        part: m21.stream.Part,
    ) -> None:
        if not isinstance(obj, m21.note.Rest):
            return
        if obj.stepShift == 0:
            return

        # obj is a positioned rest, compute and stash off MEI ploc/oloc strings
        currentClef: m21.clef.PitchClef | None = obj.getContextByClass(m21.clef.PitchClef)
        if currentClef is None or not hasattr(currentClef, 'lowestLine'):
            currentClef = m21.clef.TrebleClef()
            # this should not be common enough to
            # worry about the overhead
        if t.TYPE_CHECKING:
            assert isinstance(currentClef, m21.clef.PitchClef)
        midLineDNN = currentClef.lowestLine + 4
        restObjectPseudoDNN = midLineDNN + obj.stepShift
        tempPitch = m21.pitch.Pitch()
        tempPitch.diatonicNoteNum = restObjectPseudoDNN
        obj.mei_ploc = tempPitch.step.lower()  # type: ignore
        obj.mei_oloc = str(tempPitch.octave)  # type: ignore
        M21Utilities.extendCustomM21Attributes(
            self.customM21AttrsToDelete,
            obj,
            ['mei_ploc', 'mei_oloc']
        )

    def fillOttavas(
        self,
        obj: m21.base.Music21Object,
        part: m21.stream.Part,
        spannerBundle: m21.spanner.SpannerBundle
    ) -> None:
        for spanner in obj.getSpannerSites([m21.spanner.Ottava]):
            if not M21Utilities.isIn(spanner, spannerBundle):
                continue
            if spanner.isFirst(obj):
                spanner.fill(part)

    def deannotateScore(self) -> None:
        for sp in list(self.m21Score[M21TemporarySpanner]):
            self.m21Score.remove(sp)

        for obj in self.m21Score.recurse():
            # we don't put 'xml_id' in self.customM21AttrsToDelete, because
            # then every object would be in that dictionary.
            if hasattr(obj, 'xml_id'):
                delattr(obj, 'xml_id')

        for obj, customAttrs in self.customM21AttrsToDelete.items():
            for customAttr in customAttrs:
                if hasattr(obj, customAttr):
                    delattr(obj, customAttr)

        # all done, let go of these references to music21 objects.
        self.customM21AttrsToDelete = {}

#     def makeXmlIds(self) -> None:
#         for part in self.m21Score.parts:
#             for measure in part:
#                 if not isinstance(measure, m21.stream.Measure):
#                     continue
#                 self.makeMeasureXmlIds(measure, self.spannerBundle)

#     def makeMeasureXmlIds(
#         self,
#         measure: m21.stream.Measure,
#         spannerBundle: m21.spanner.SpannerBundle
#     ):
#         for obj in measure.recurse().getElementsByClass(m21.note.GeneralNote):
#             if isinstance(obj, m21.chord.Chord):
#                 # M21TieSpanner might contain notes that are inside chords (this
#                 # is not actually valid for real spanners, but it's ok for us).
#                 # Handle this as a special case.
#                 for note in obj.notes:
#                     for spanner in note.getSpannerSites():
#                         if not M21Utilities.isIn(spanner, spannerBundle):
#                             continue
#                         if isinstance(spanner, M21TieSpanner):
#                             M21Utilities.assureXmlId(spanner.getFirst())
#                             if spanner.getLast() is not spanner.getFirst():
#                                 M21Utilities.assureXmlId(spanner.getLast())
#
#             # check expressions for turn/trill/mordent; if any present, obj needs xmlId
#             for expr in obj.expressions:
#                 if isinstance(expr, (
#                     m21.expressions.Turn,
#                     m21.expressions.Trill,
#                     m21.expressions.GeneralMordent,
#                     m21.expressions.Fermata,
#                     m21.expressions.ArpeggioMark
#                 )):
#                     M21Utilities.assureXmlId(obj)
#                     break  # skip the rest of the expressions
#
#             # check for spanners (all spanners for now, might get too many xmlIds?)
#             for spanner in obj.getSpannerSites():
#                 if not M21Utilities.isIn(spanner, spannerBundle):
#                     continue
#                 if isinstance(spanner, (M21BeamSpanner, M21TupletSpanner)):
#                     # Beam spanners and tuplet spanners only need xmlIds if they
#                     # span multiple measures.  Note that we won't know this until
#                     # we encounter a later object in such a spanner, so when we
#                     # do, we reach back and assure xmlIds for everything in the
#                     # spanner.  Note that assureXmlId returns immediately if
#                     # the xml id is already in place.
#                     if not M21Utilities.allSpannedElementsAreInHierarchy(spanner, measure):
#                         for el in spanner.getSpannedElements():
#                             M21Utilities.assureXmlId(el)
#                     continue  # to next spanner
#
#                 if isinstance(spanner, M21TieSpanner):
#                     M21Utilities.assureXmlId(spanner.getFirst())
#                     if spanner.getLast() is not spanner.getFirst():
#                         M21Utilities.assureXmlId(spanner.getLast())
#                     continue  # to next spanner
#
#                 # Some spanners need xmlIds for all their elements:
#                 if isinstance(spanner, m21.expressions.ArpeggioMarkSpanner):
#                     M21Utilities.assureXmlId(obj)
#
#                 # All other spanners need xmlIds only for start and end elements
#                 if spanner.isFirst(obj) or spanner.isLast(obj):
#                     M21Utilities.assureXmlId(obj)

    def annotateBeams(
        self,
        noteOrChord: m21.base.Music21Object,
        part: m21.stream.Part,
        voiceId: int | str
    ) -> None:
        if not isinstance(noteOrChord, m21.note.NotRest):
            return

        if isinstance(noteOrChord, m21.harmony.ChordSymbol):
            # ChordSymbol is a NotRest, but should not have any beams.
            return

        def stopsBeam(beam: m21.beam.Beam) -> bool:
            if beam.type == 'stop':
                return True
            if beam.type == 'partial' and beam.direction == 'left':
                return True
            return False

        def startsBeam(beam: m21.beam.Beam) -> bool:
            if beam.type == 'start':
                return True
            if beam.type == 'partial' and beam.direction == 'right':
                return True
            return False

        def allStop(beams: m21.beam.Beams) -> bool:
            if len(beams.beamsList) == 0:
                return False
            for beamObj in beams:
                if not stopsBeam(beamObj):
                    return False
            return True

        def allStart(beams: m21.beam.Beams) -> bool:
            if len(beams.beamsList) == 0:
                return False
            for beamObj in beams:
                if not startsBeam(beamObj):
                    return False
            return True

        def computeBreakSec(prevBeams: m21.beam.Beams, currBeams: m21.beam.Beams) -> int:
            # returns the number of beams that should be seen during the break
            # returns 0 if no breaksec seen
            numBeams: int = len(currBeams)
            if len(prevBeams) != numBeams:
                return 0

            numStartStops: int = 0
            for prevBeam, currBeam in zip(prevBeams, currBeams):
                if stopsBeam(prevBeam) and startsBeam(currBeam):
                    numStartStops += 1

            if numStartStops == 0:
                return 0

            return numBeams - numStartStops

        if not noteOrChord.beams.beamsList:
            self.previousBeamedNoteOrChord[(part, voiceId)] = None
            return

        if allStart(noteOrChord.beams) or not self.currentBeamSpanners[(part, voiceId)]:
            newBeamSpanner = M21BeamSpanner()
            self.m21Score.append(newBeamSpanner)
            self.currentBeamSpanners[(part, voiceId)].append(newBeamSpanner)

        self.currentBeamSpanners[(part, voiceId)][-1].addSpannedElements(noteOrChord)

        if allStop(noteOrChord.beams):
            # done with this <beam> or <beamSpan>.  Put the spanner in the score,
            # and clear out any state variables.
            self.currentBeamSpanners[(part, voiceId)] = (
                self.currentBeamSpanners[(part, voiceId)][:-1]
            )
            self.previousBeamedNoteOrChord[(part, voiceId)] = None
            return

        # annotate any breaksec ending at this noteOrChord (set it on the previous noteOrChord)
        if self.previousBeamedNoteOrChord[(part, voiceId)] is not None:
            prevNC = self.previousBeamedNoteOrChord[(part, voiceId)]
            if t.TYPE_CHECKING:
                assert prevNC is not None
            breakSec: int = computeBreakSec(prevNC.beams, noteOrChord.beams)
            if breakSec > 0:
                prevNC.mei_breaksec = breakSec  # type: ignore
                M21Utilities.extendCustomM21Attributes(
                    self.customM21AttrsToDelete,
                    prevNC,
                    ['mei_breaksec']
                )
        self.previousBeamedNoteOrChord[(part, voiceId)] = noteOrChord

    def annotateTuplets(self, gnote: m21.base.Music21Object, part: m21.stream.Part) -> None:
        if not isinstance(gnote, m21.note.GeneralNote):
            return

        if isinstance(gnote, m21.harmony.ChordSymbol):
            # ChordSymbol is a GeneralNote, but will not have any duration (i.e. no tuplets)
            # in the MEI file.
            return

        def stopsTuplet(tuplet: m21.duration.Tuplet) -> bool:
            if tuplet.type in ('stop', 'startStop'):
                return True
            return False

        def startsTuplet(tuplet: m21.duration.Tuplet) -> bool:
            if tuplet.type in ('start', 'startStop'):
                return True
            return False

        if not gnote.duration.tuplets and self.currentTupletSpanners[part]:
            # if gnote is a grace note, keep the tuplet running but skip the grace note
            if gnote.duration.isGrace:
                return

            # if gnote is NOT a grace note, then stop the tuplet
            self.currentTupletSpanners[part] = self.currentTupletSpanners[part][:-1]
            return

        # start any new tuplet spanners
        for tuplet in gnote.duration.tuplets:
            if (startsTuplet(tuplet)
                    or (tuplet.type is None and not self.currentTupletSpanners[part])):
                newTupletSpanner = M21TupletSpanner(tuplet)
                self.m21Score.append(newTupletSpanner)
                self.currentTupletSpanners[part].append(newTupletSpanner)

        # put this note in all the tuplet spanners
        for spanner in self.currentTupletSpanners[part]:
            spanner.addSpannedElements(gnote)

        # stop any old tuplet spanners
        for tuplet in gnote.duration.tuplets:
            if stopsTuplet(tuplet):
                self.currentTupletSpanners[part] = self.currentTupletSpanners[part][:-1]

    def annotateTies(
        self,
        noteOrChord: m21.base.Music21Object,
        part: m21.stream.Part,
        stopsOnly: bool = False
    ) -> None:
        if not isinstance(noteOrChord, (m21.note.Note, m21.chord.Chord)):
            # Note that we reject Unpitched and PercussionChord here, since
            # they have no pitches, so they cannot be tied.
            return

        if isinstance(noteOrChord, m21.harmony.ChordSymbol):
            # ChordSymbol is a Chord, but will not have any ties.
            return

        def startsTie(noteOrChord: m21.note.Note | m21.chord.Chord) -> bool:
            if isinstance(noteOrChord, m21.chord.Chord):
                # chord.tie should always be ignored, in music21 it actually returns
                # the first tie it finds in the chord's notes. Which is not particularly
                # useful for us here.
                return False
            if noteOrChord.tie is None:
                return False
            if noteOrChord.tie.type in ('start', 'continue'):
                return True
            return False

        def stopsTieInWhichSpanner(
            note: m21.note.Note,
            part: m21.stream.Part,
            partTieSpanners: list[tuple[M21TieSpanner, int]],
            parentChord: m21.chord.Chord | None = None
        ) -> tuple[M21TieSpanner, int] | None:
            # look at all the partTieSpanners and see if this note has the
            # same (exact) pitches as the start note of that spanner.
            for sp, numMeasuresSearched in partTieSpanners:
                startNote: m21.note.Note = sp.getFirst()
                if note is startNote:
                    continue

                # comparison via nameWithOctave is working around the music21
                # bug where a pitch with accidental=None is different from
                # a pitch with accidental='natural'.  Ugh.
                if startNote.pitch.nameWithOctave != note.pitch.nameWithOctave:
                    continue

                # to stop a tie, you have to start at or beyond the end of the tie's start note.
                startParentChord: m21.chord.Chord | None = sp.startParentChord
                minPartOffset: OffsetQL
                actualPartOffset: OffsetQL
                if startParentChord is not None:
                    minPartOffset = opFrac(
                        startParentChord.getOffsetInHierarchy(part)
                        + startParentChord.quarterLength
                    )
                else:
                    minPartOffset = opFrac(
                        startNote.getOffsetInHierarchy(part)
                        + startNote.quarterLength
                    )

                if parentChord is not None:
                    actualPartOffset = parentChord.getOffsetInHierarchy(part)
                else:
                    actualPartOffset = note.getOffsetInHierarchy(part)

                if (actualPartOffset < minPartOffset):
                    continue

                # we found a spanner whose startNote has the same pitches as
                # note, so return that spanner.  note stops the tie
                # represented by that spanner.
                return (sp, numMeasuresSearched)

            return None

        partTieSpanners: list[tuple[M21TieSpanner, int]] = self.currentTieSpanners[part]

        if not stopsOnly:
            if isinstance(noteOrChord, m21.chord.Chord):
                # A chord itself never starts a tie; perhaps one or more of the chord's
                # individual notes does.
                for note in noteOrChord.notes:
                    if startsTie(note):
                        if t.TYPE_CHECKING:
                            assert note.tie is not None
                        newTieSpanner = M21TieSpanner(note.tie, startParentChord=noteOrChord)
                        newTieSpanner.addSpannedElements(note)
                        self.m21Score.append(newTieSpanner)
                        partTieSpanners.append((newTieSpanner, 1))
            elif startsTie(noteOrChord):
                if t.TYPE_CHECKING:
                    assert noteOrChord.tie is not None
                newTieSpanner = M21TieSpanner(noteOrChord.tie, startParentChord=None)
                newTieSpanner.addSpannedElements(noteOrChord)
                self.m21Score.append(newTieSpanner)
                partTieSpanners.append((newTieSpanner, 1))

        if not partTieSpanners:
            # no tie stops to search for...
            return

        spN: tuple[M21TieSpanner, int] | None = None
        if isinstance(noteOrChord, m21.chord.Chord):
            # The chord itself does not stop a tie (M21TieSpanners always span notes);
            # perhaps one or more of the chord's individual notes does.
            for note in noteOrChord.notes:
                spN = stopsTieInWhichSpanner(note, part, partTieSpanners, noteOrChord)
                if spN is not None:
                    spN[0].addSpannedElements(note)
                    partTieSpanners.remove(spN)
        elif isinstance(noteOrChord, m21.note.Note):
            spN = stopsTieInWhichSpanner(noteOrChord, part, partTieSpanners)
            if spN is not None:
                spN[0].addSpannedElements(noteOrChord)
                partTieSpanners.remove(spN)
        else:
            raise MeiInternalError('noteOrChord is not Note or Chord')
