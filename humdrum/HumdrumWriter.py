# ------------------------------------------------------------------------------
# Name:          HumdrumWriter.py
# Purpose:       HumdrumWriter is an object that takes a music21 stream and
#                writes it to a file as Humdrum data.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021 Greg Chapman
# License:       BSD, see LICENSE
# ------------------------------------------------------------------------------
import sys
import copy
from collections import OrderedDict
from typing import List, Tuple
import music21 as m21

from humdrum import HumdrumExportError
from humdrum import HumNum
from humdrum import M21Convert

from humdrum import EventData
from humdrum import MeasureData, SimultaneousEvents
from humdrum import ScoreData

from humdrum import GridStaff
from humdrum import GridPart
from humdrum import SliceType
from humdrum import GridSlice
from humdrum import GridMeasure
from humdrum import HumGrid

from humdrum import HumdrumToken
from humdrum import HumdrumFile

### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

class HumdrumWriter:
    Debug: bool = True

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

    def __init__(self, obj: m21.prebase.ProtoM21Object):
        self._m21Object: m21.prebase.ProtoM21Object = obj
        self._m21Score: m21.stream.Score = None
        self._scoreData: ScoreData = None

        # default options (these can be set to non-default values by clients,
        # as long as they do it before they call write())
        self.makeNotation : bool = True  # client can set to False if obj is a Score
        self.addRecipSpine: bool = False # client can set to True to add a recip spine to the output
        self.VoiceDebug: bool = False # can be set to True for debugging output

        # private data, computed along the way...
        self._forceRecipSpine: bool = False # set to true sometimes in figured bass, harmony code
        self._hasTremolo: bool = False

        # temporary data (to be emitted with next durational object)
        # First element of tuple is the part index
        self._currentTexts:  List[Tuple[int, m21.expressions.TextExpression]] = []
        self._currentTempos: List[Tuple[int, m21.tempo.TempoIndication]] = []
        self._currentDynamics: List[m21.dynamics.Dynamic] = [] # no tuple here

    def write(self, fp):
        # First, turn the object into a well-formed Score (someone might have passed in a single
        # note, for example).  This code is swiped from music21 v7's musicxml exporter.  The hope
        # is that someday it will become an API in music21 that every exporter can call.
        if self.makeNotation:
            self._m21Score = self._makeScoreFromObject(self._m21Object) # always creates a new Score
        else:
            if 'Score' not in self._m21Object.classes:
                raise HumdrumExportError('Can only export Scores with makeNotation=False')
            self._m21Score = self._m21Object
        self._m21Object = None # everything after this uses self._m21Score

        # The rest is based on Tool_musicxml2hum::convert(ostream& out, xml_document& doc)
        # 1. convert self._m21Score to HumGrid
        # 2. convert HumGrid to HumdrumFile
        # 3. write HumdrumFile to fp

        status: bool = True
        outgrid: HumGrid = HumGrid()

        status = status and self._stitchParts(outgrid, self._m21Score)

        outgrid.removeRedundantClefChanges()
#         outgrid.removeSibeliusIncipit()

        if self.addRecipSpine or self._forceRecipSpine:
            outgrid.enableRecipSpine()

        outfile: HumdrumFile = HumdrumFile()
        outgrid.transferTokens(outfile)

        self._addHeaderRecords(outfile)
        #888 self._addFooterRecords(outfile, _scoreData)
        #888 self._addMeasureOneNumber(outfile)

#         chord.run(outfile) # makes sure each note in the chord has the right stuff on it?

#         if self._hasOrnaments: # maybe outgrid.hasOrnaments? or m21Score.hasOrnaments?
#             trillspell.run(outfile) # figures out actual trill, mordent, turn type
                                      # based on current key and accidentals

#         if self._hasTremolo:
#             tremolo.run(outfile) # spells out the tremolo, which was inserted (apparently)
                                   # as a single token? Adds *tremolo/*Xtremolo, so we know.

#         if self._hasTransposition: # *Tr? *ITr?
#             transpose.run('-C', outfile) # to concert pitch
#             if transpose.hasHumdrumText:
#                 outfile.readString(transpose.getHumdrumText)
#         else:
        for hline in outfile.lines():
            hline.createLineFromTokens()

        self._printResult(fp, outfile)

        # This should go in _addFooterRecords(outfile), so _printResult will print it
        #888 self._prepareRdfs(outgrid, self._m21Score)
        #888 self._printRdfs(fp) # this will go away if we do that ^

        return status

    def _printResult(self, fp, outfile: HumdrumFile):
        pass # 888 implement _printResult

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addHeaderRecords -- Inserted in reverse order
    //      (last record inserted first).
    '''
    def _addHeaderRecords(self, outfile: HumdrumFile):
        # This should go inside _addHeaderRecords, and not exist as member data
        systemDecoration: str = self._getSystemDecoration(self._m21Score, outfile)
        if systemDecoration and systemDecoration != 's1':
            outfile.appendLine('!!!system-decoration: ' + systemDecoration)

        #metadata: m21.metadata.Metadata = score.metadata
        # 888 implement m21.metadata.Metadata -> !!!AAA: blah

    @staticmethod
    def _getSystemDecoration(m21Score: m21.stream.Score, outfile: HumdrumFile) -> str:
        return (m21Score, outfile) # 888 implement _getSystemDecoration


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
            for _ in part.measures:
                measureCount[-1] += 1

        if partCount == 0:
            return False

        mCount0 = measureCount[0]
        for mCount in measureCount:
            if mCount != mCount0:
                raise HumdrumExportError('ERROR: cannot handle parts with different measure counts')

        self._scoreData = ScoreData(score)

        # Now insert each measure into the HumGrid across those parts/staves
        status: bool = True
        for m in range(0, mCount0):
            status = status and self._insertMeasure(outgrid, m)

        #888 self._moveBreaksToEndOfPreviousMeasure(outgrid)
        #888 self._insertPartNames(outgrid, parts)

        return status

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::insertMeasure --
    '''
    def _insertMeasure(self, outgrid: HumGrid, mIndex: int):
        gm: GridMeasure = outgrid.appendMeasure()

        xmeasure: MeasureData = None
        measureData: [MeasureData] = []
        sevents: [[SimultaneousEvents]] = []

        for p, part in enumerate(self._scoreData.parts):
            for s, staff in enumerate(part.staves):
                xmeasure = staff.measures[mIndex]
                measureData.append(xmeasure)
                if p == 0 and s == 0:
                    gm.duration = xmeasure.duration
                    gm.timestamp = xmeasure.timestamp
                    gm.timeSigDur = xmeasure.timeSigDur
                #888 self._checkForDummyRests(xmeasure)
                sevents.append(xmeasure.sortedEvents())
                if p == 0 and s == 0:
                    gm.barStyle = xmeasure.barStyle

        curTime: [HumNum] = [None] * len(measureData)
        measureDurs: [HumNum] = [None] * len(measureData)
        curIndex: [int] = [0] * len(measureData)
        nextTime: HumNum = HumNum(-1)

        tsDur: HumNum = HumNum(-1)
        for ps, mdata in enumerate(measureData):
            events: [EventData] = mdata.eventList()
            # Keep track of hairpin endings that should be attached
            # the the previous note (and doubling the ending marker
            # to indicate that the timestamp of the ending is at the
            # end rather than the start of the note.
            #   I think this is a no-op for music21 input. --gregc

            if self.VoiceDebug:
                for event in events:
                    print('!!ELEMENT: ', end='', file=sys.stderr)
                    print('\tTIME:  {}'.format(event.startTime), end='', file=sys.stderr)
                    print('\tSTi:   {}'.format(event.staffIndex), end='', file=sys.stderr)
                    print('\tVi:    {}'.format(event.voiceIndex), end='', file=sys.stderr)
                    print('\tDUR:   {}'.format(event.duration), end='', file=sys.stderr)
                    print('\tPITCH: {}'.format(event.kernPitch), end='', file=sys.stderr)
                    print('\tNAME:  {}'.format(event.elementName), end='', file=sys.stderr)
                    print('', file=sys.stderr) # line feed (one line per event)
                print('======================================', file=sys.stderr)

            if sevents[ps]:
                # TODO: I think curIndex[ps] could be replaced with 0 here --gregc
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

        processTime: HumNum = nextTime
        while not allEnd:
            nowEvents = []
#             nowPartStaves = []
            allEnd = True
            processTime = nextTime
            nextTime = HumNum(-1)
            for ps in reversed(range(0, len(measureData))):
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

        if not nowEvents[0].nonZeroDur:
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
#        hasTransposition:   bool = False
        hasTimeSig:         bool = False
        hasOttava:          bool = False
        hasStaffLines:      bool = False

        # These are all indexed by part, staff
        # Some have further indexes for voice, and maybe note
        clefs: [[m21.clef.Clef]] = []
        keySigs: [[m21.key.KeySignature]] = []
        transpositions: [[m21.interval.Interval]] = []
        timeSigs: [[m21.meter.TimeSignature]] = []
        hairPins: [[m21.dynamics.DynamicWedge]] = []
        staffLines: [[int]] = [] # number of staff lines (if specified)
        ottavas: [[[m21.spanner.Ottava]]] = []

        graceBefore: [[[[EventData]]]] = []
        graceAfter: [[[[EventData]]]] = []
        foundNonGrace: bool = False

        # pre-populate the top level list with an empty list for each part
        for _ in range(0, len(self._scoreData.parts)):
            clefs.append([])
            keySigs.append([])
            transpositions.append([])
            timeSigs.append([])
            hairPins.append([])
            staffLines.append([])
            ottavas.append([])
            graceBefore.append([])
            graceAfter.append([])

        for simultaneousEventList in nowEvents:
            for zeroDurEvent in simultaneousEventList.zerodur:
                m21Obj: m21.base.Music21Object = zeroDurEvent.m21Object # getNode
                pindex: int = zeroDurEvent.partIndex

                if 'Clef' in m21Obj.classes:
                    clefs[pindex].append(m21Obj)
                    hasClef = True
                    foundNonGrace = True
                elif 'Key' in m21Obj.classes or 'KeySignature' in m21Obj.classes:
                    keySigs[pindex].append(m21Obj)
                    hasKeySig = True
                    hasKeyDesignation = 'Key' in m21Obj.classes
                    foundNonGrace = True
                elif 'StaffLayout' in m21Obj.classes:
                    staffLines[pindex].append(m21Obj.staffLines)
                    hasStaffLines = True
                    foundNonGrace = True
                elif 'TimeSignature' in m21Obj.classes:
                    timeSigs[pindex].append(m21Obj)
                    hasTimeSig = True
                    foundNonGrace = True
                elif 'TextExpression' in m21Obj.classes:
                    # put in self._currentTexts, so it can be emitted
                    # during the immediately following call to
                    # appendNonZeroEvents() -> addEvent()
                    self._currentTexts.append((pindex, m21Obj))
                elif 'MetronomeMark' in m21Obj.classes:
                    self._currentTempos.append((pindex, m21Obj))
                elif 'Dynamic' in m21Obj.classes:
                    self._currentDynamics.append(m21Obj) # no tuple here
#                 elif 'FiguredBass' in m21Obj.classes:
#                     self._currentFiguredBass.append(m21Obj)
                elif 'GeneralNote' in m21Obj.classes:
                    if foundNonGrace:
                        self._addEventToList(graceAfter, zeroDurEvent)
                    else:
                        self._addEventToList(graceBefore, zeroDurEvent)
                elif 'PageLayout' in m21Obj.classes or 'SystemLayout' in m21Obj.classes:
                    self._processPrintElement(outgm, m21Obj, nowTime)

        # 888 do the rest of these addBlahLine(s) (Grace, Stria, Clef, KeySig, etc)
#         self._addGraceLines(outgm, graceBefore, nowTime)
#
#         if hasStaffLines:
#             self._addStriaLine(outgm, staffLines, nowTime)
#
#         if hasClef:
#             self._addClefLine(outgm, clefs, nowTime)
#
#         if hasKeySig:
#             self._addKeySigLine(outgm, keySigs, nowTime)
#
#         if hasKeyDesignation:
#             self._addKeyDesignationLine(outgm, keySigs, nowTime)
#
#         if hasTimeSig:
#             self._addTimeSigLine(outgm, keySigs, nowTime)
#
#         if hasOttava:
#             self._addOttavaLine(outgm, ottavas, nowTime)
#
#         self._addGraceLines(outgm, graceAfter, nowTime)
        return (hasStaffLines, hasClef, hasKeySig, hasKeyDesignation, hasTimeSig, hasOttava) # remove

    def _addEventToList(self, eventList: [EventData], event: EventData):
        return (self, eventList, event) # 888 implement _addEventToList

    def _processPrintElement(self, outgm: GridMeasure, m21Obj: m21.base.Music21Object, nowTime: HumNum):
        return (self, outgm, m21Obj, nowTime) # 888 implement _processPrintElement

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
            lastTime: HumNum = outgm.slices[-1].timeStamp
            if nowTime >= lastTime:
                outgm.slices.append(outSlice)
            else:
                # travel backwards in the measure until the correct
                # time position is found.
                for i, walkSlice in enumerate(reversed(outgm.slices)):
                    if walkSlice.timeStamp <= nowTime:
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
        partIndex: int = event.partIndex
        staffIndex: int = event.staffIndex
        voiceIndex: int = event.voiceIndex

        tokenString: str = event.getNoteKernTokenString()
        if '@' in tokenString:
            self._hasTremolo = True

        if self.Debug:
            print('!!TOKEN: {tokenString}', end='\t', file=sys.stderr)
            print('TS: {event.startTime}', end='\t', file=sys.stderr)
            print('DUR: {event.duration}', end='\t', file=sys.stderr)
            print('STn: {event.staffNumber}', end='\t', file=sys.stderr)
            print('Vn: {event.voiceNumber}', end='\t', file=sys.stderr)
            print('STi: {event.staffIndex}', end='\t', file=sys.stderr)
            print('Vi: {event.voiceIndex}', end='\t', file=sys.stderr)
            print('eName: {event.elementName}', file=sys.stderr)

        token = HumdrumToken(tokenString)
        outSlice.parts[partIndex].staves[staffIndex].setTokenLayer(voiceIndex, token, event.duration)

        vcount: int = self._addLyrics(outSlice.parts[partIndex].staves[staffIndex], event)
        if vcount > 0:
            event.reportVerseCountToOwner(staffIndex, vcount)

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

        if self._currentTexts:
            # self._currentTexts contains any zero-duration (unassociated) TextExpressions.
            # event.texts already contains any TextExpressions associated with this note.
            event.texts += self._currentTexts
            self._currentTexts = []

            self._addTexts(outSlice, outgm, partIndex, staffIndex, voiceIndex, event)

        if self._currentTempos:
            # self._currentTempos contains all the TempoIndications.  event.tempos is
            # empty, but for consistency (and future extensibility) we append here.
            event.tempos += self._currentTempos
            self._currentTempos = []

            self._addTempos(outSlice, outgm, partIndex, staffIndex, voiceIndex, event)

        if self._currentDynamics[partIndex]:
            # self._currentDynamics contains any zero-duration (unassociated) dynamics ('pp' et al).
            # event.dynamics already contains any "durational" dynamics (multi-note wedges starts or
            # stops) associated with this note.
            event.dynamics += self._currentDynamics[partIndex]
            self._currentDynamics[partIndex] = []
            event.reportDynamicsToOwner()
            self._addDynamics(outSlice, outgm, partIndex, staffIndex, event)

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
                     partIndex: int, staffIndex: int, event: EventData):
        if not event.dynamics:
            return # no dynamics

        tok: HumdrumToken = None
        for dynamic in event.dynamics: # dynamic can be Dynamic ('pp') or DynamicWedge (dim/cresc)
            dstring: str = ''
            if isinstance(dynamic, m21.dynamics.Dynamic):
                dstring = M21Convert.getDynamicString(dynamic)
                if tok is None:
                    tok = HumdrumToken(dstring)
                else:
                    tok.text += ' ' + dstring

            elif isinstance(dynamic, m21.dynamics.DynamicWedge):
                dstring = M21Convert.getDynamicWedgeString(dynamic, event.m21Object)
                if tok is None:
                    tok = HumdrumToken(dstring)
                else:
                    tok.text += ' ' + dstring

        if tok is not None:
            outSlice.parts[partIndex].staves[staffIndex].dynamics = tok

        # add any necessary layout params
        moreThanOneDynamic: bool = (len(event.dynamics) > 1)
        for i, dynamic in enumerate(event.dynamics):
            dparam: str = M21Convert.getDynamicsParameters(dynamic, event.m21Object)
            if dparam:
                fullParam: str = ''
                if isinstance(dynamic, m21.dynamics.Dynamic):
                    fullParam += '!LO:DY'
                elif isinstance(dynamic, m21.dynamics.DynamicWedge):
                    fullParam += '!LO:HP'
                else:
                    continue

                if moreThanOneDynamic:
                    fullParam += ':n=' + str(i+1) # :n= is 1-based

                fullParam += dparam
                outgm.addDynamicsLayoutParameters(outSlice, partIndex, staffIndex, fullParam)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addTexts -- Add all text direction for a note.
    '''
    def _addTexts(self, outSlice: GridSlice,
                        outgm: GridMeasure,
                        _partIndex: int,
                        staffIndex: int,
                        _voiceIndex: int,
                        event: EventData):
        for newPartIndex, textExpression in event.texts:
            newVoiceIndex: int = 0 # Not allowing addressing text by layer (could be changed)
            self._addText(outSlice, outgm,
                          newPartIndex, staffIndex, newVoiceIndex,
                          textExpression)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addText -- Add a text direction to the grid.
    '''
    @staticmethod
    def _addText(outSlice: GridSlice, outgm: GridMeasure,
                 partIndex: int, staffIndex: int, _voiceIndex: int,
                 textExpression: m21.expressions.TextExpression):
        textString: str = M21Convert.textLayoutParameterFromM21TextExpression(textExpression)
        outgm.addLayoutParameter(outSlice, partIndex, staffIndex, textString)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addTempos -- Add tempo indication for a note.
    '''
    def _addTempos(self, outSlice: GridSlice,
                         outgm: GridMeasure,
                         _partIndex: int,
                         staffIndex: int,
                         _voiceIndex: int,
                         event: EventData):
        for newPartIndex, tempoIndication in event.tempos:
            newVoiceIndex: int = 0 # Not allowing addressing tempo by layer (could be changed)
            self._addTempo(outSlice, outgm,
                           newPartIndex, staffIndex, newVoiceIndex,
                           tempoIndication)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addTempo -- Add a tempo direction to the grid.
    '''
    @staticmethod
    def _addTempo(outSlice: GridSlice, outgm: GridMeasure,
                  partIndex: int, staffIndex: int, _voiceIndex: int,
                  tempoIndication: m21.tempo.TempoIndication):
        mmTokenStr: str = ''      # '*MM128' for example
        tempoTextLayout: str = '' # '!LO:TX:a:t=[eighth]=256' for example
        mmTokenStr, tempoTextLayout = M21Convert.getMMTokenAndTempoTextLayoutFromM21TempoIndication(
                                            tempoIndication)
        if mmTokenStr:
            outgm.addTempoToken(mmTokenStr, outSlice.timestamp,
                                partIndex, staffIndex, 0, 10) #self._maxStaff)

        if tempoTextLayout:
            # The text direction needs to be added before the last line in the measure object.
            # If there is already an empty layout slice before the current one (with no spine
            # manipulators in between), then insert onto the existing layout slice; otherwise
            # create a new layout slice.
            outgm.addTempoLayout(outSlice, partIndex, staffIndex, tempoTextLayout)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::addLyrics --
    '''
    def _addLyrics(self, staff: GridStaff, event: EventData) -> int: #LATER: needs implementation
        if self or staff or event:
            return 0
        return 0

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
