# ------------------------------------------------------------------------------
# Name:          MeasureData.py
# Purpose:       MeasureData is an object somewhere between an m21 Measure
#                and a GridMeasure.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
import typing as t

import music21 as m21
from music21.common import opFrac

# from converter21.humdrum import HumdrumExportError
from converter21.humdrum import HumNum, HumNumIn
from converter21.humdrum import MeasureStyle
from converter21.humdrum import FermataStyle
from converter21.humdrum import EventData
from converter21.humdrum import Convert
from converter21.humdrum import M21Convert
from converter21.shared import M21Utilities

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class SimultaneousEvents:
    def __init__(self) -> None:
        self.startTime: HumNum = opFrac(-1)      # start time of events
        self.duration: HumNum = opFrac(-1)       # max duration of events?
        self.zeroDur: t.List[EventData] = []     # zero-duration events at this time
        self.nonZeroDur: t.List[EventData] = []  # non-zero-duration events at this time

class MeasureData:
    def __init__(
            self,
            measure: m21.stream.Measure,
            ownerStaff,      # StaffData
            measureIndex: int,
            prevMeasData: t.Optional['MeasureData']
    ) -> None:
        from converter21.humdrum import StaffData
        self.m21Measure: m21.stream.Measure = measure
        self.ownerStaff: StaffData = ownerStaff

        # inherited from ownerScore, ultimately
        self.spannerBundle: m21.spanner.SpannerBundle = ownerStaff.spannerBundle

        self._prevMeasData: t.Optional[MeasureData] = prevMeasData
        self._measureIndex: int = measureIndex
        self._startTime: HumNum = opFrac(-1)
        self._duration: HumNum = opFrac(-1)
        self._timeSigDur: HumNum = opFrac(-1)
        # leftBarlineStyle describes the left barline of this measure
        self.leftBarlineStyle: MeasureStyle = MeasureStyle.NoBarline
        # rightBarlineStyle describes the right barline of this measure
        self.rightBarlineStyle: MeasureStyle = MeasureStyle.NoBarline
        # measureStyle is a combination of this measure's leftBarlineStyle and
        # the previous measure's rightBarlineStyle.  It's the style we use when
        # writing a barline ('=') token.
        self.measureStyle: MeasureStyle = MeasureStyle.NoBarline

        self.leftBarlineFermataStyle: FermataStyle = FermataStyle.NoFermata
        self.rightBarlineFermataStyle: FermataStyle = FermataStyle.NoFermata
        # fermataStyle is a combination of this measure's leftBarlineFermataStyle and
        # the previous measure's rightBarlineFermataStyle.  It's the fermata style we
        # use when writing a barline ('=') token.
        self.fermataStyle: FermataStyle = FermataStyle.NoFermata

        self.inRepeatBracket: bool = False
        self.startsRepeatBracket: bool = False
        self.stopsRepeatBracket: bool = False
        self.repeatBracketName: str = ''

        self._measureNumberString: str = ''
        self.events: t.List[EventData] = []
        self.sortedEvents: t.List[SimultaneousEvents] = []  # list of startTime-binned events

        self._parseMeasure()  # generates _events and then sortedEvents (also barlines)

    @property
    def measureIndex(self) -> int:
        return self._measureIndex

    @property
    def measureNumberString(self) -> str:
        return self._measureNumberString

    @property
    def staffIndex(self) -> int:
        return self.ownerStaff.staffIndex

    @property
    def staffNumber(self) -> int:
        return self.staffIndex + 1

    @property
    def partIndex(self) -> int:
        return self.ownerStaff.partIndex

    @property
    def partNumber(self) -> int:
        return self.partIndex + 1

    '''
    //////////////////////////////
    //
    // MxmlMeasure::getStartTime --
    '''
    @property
    def startTime(self) -> HumNum:
        return self._startTime

    '''
    //////////////////////////////
    //
    // MxmlMeasure::getDuration --
    '''
    @property
    def duration(self) -> HumNum:
        return self._duration

    '''
    //////////////////////////////
    //
    // MxmlMeasure::getTimeSigDur --
    '''
    @property
    def timeSigDur(self) -> HumNum:
        return self._timeSigDur

    '''
    //////////////////////////////
    //
    // MxmlMeasure::parseMeasure -- Reads music21 data for one staff's measure.
    '''
    def _parseMeasure(self) -> None:
        self._setStartTimeOfMeasure()
        self._duration = self.m21Measure.duration.quarterLength

        # m21 tracks timesigdur for us in barDuration, which is always the latest timeSig duration
        # But it can be ridiculously slow if it has to search back in the score for a timesignature,
        # so we only call it if the measure has a timesignature. If it doesn't have one, we
        # just use the _timeSigDur of the previous measure.
        if self.m21Measure.timeSignature is None and self._prevMeasData is not None:
            self._timeSigDur = self._prevMeasData.timeSigDur
        else:
            self._timeSigDur = self.m21Measure.barDuration.quarterLength

        self._measureNumberString = self.m21Measure.measureNumberWithSuffix()
        if self._measureNumberString == '0':
            self._measureNumberString = ''

        # In humdrum, measure style is a combination of this measure's left barline and the
        # previous measure's right barline.  (For example, ':|!|:' in a humdrum barline comes
        # from the previous right barline being an end-repeat (light-heavy) and the current
        # left barline being a start repeat (heavy-light)).
        # The very last humdrum barline (last measure's right barline) is handled as a special
        # case at a higher level, not here.

        # Compute our left and right barline style
        self.leftBarlineStyle = M21Convert.measureStyleFromM21Barline(self.m21Measure.leftBarline)
        self.rightBarlineStyle = M21Convert.measureStyleFromM21Barline(self.m21Measure.rightBarline)

        # measure index 0 only: pretend there is a left barline (hidden) if there is none
        # That first barline in Humdrum files is important for parse-ability.
        if self.measureIndex == 0:
            if self.leftBarlineStyle == MeasureStyle.NoBarline:
                self.leftBarlineStyle = MeasureStyle.Invisible

        # Grab the previous measure's right barline style (if there is one) and
        # combine it with our left barline style, giving our measureStyle.
        prevRightMeasureStyle: MeasureStyle = MeasureStyle.NoBarline
        if self._prevMeasData is not None:
            prevRightMeasureStyle = self._prevMeasData.rightBarlineStyle
        self.measureStyle = M21Convert.combineTwoMeasureStyles(self.leftBarlineStyle,
                                                               prevRightMeasureStyle)
        # Extract left and right barline Fermata
        self.leftBarlineFermataStyle = M21Convert.fermataStyleFromM21Barline(
            self.m21Measure.leftBarline
        )
        self.rightBarlineFermataStyle = M21Convert.fermataStyleFromM21Barline(
            self.m21Measure.rightBarline
        )

        # Grab the previous measure's right barline fermata style (if there is one) and
        # combine it with our left barline fermata style, giving our fermataStyle.
        prevRightBarlineFermataStyle: FermataStyle = FermataStyle.NoFermata
        if self._prevMeasData is not None:
            prevRightBarlineFermataStyle = self._prevMeasData.rightBarlineFermataStyle
        self.fermataStyle = M21Convert.combineTwoFermataStyles(
            self.leftBarlineFermataStyle,
            prevRightBarlineFermataStyle
        )

        # measure index 0 only: add events for any Instruments found in ownerStaff.m21PartStaff
        if self.measureIndex == 0:
            for elementIndex, inst in enumerate(
                    self.ownerStaff.m21PartStaff.getElementsByClass(m21.instrument.Instrument)):
                event: EventData = EventData(inst, elementIndex, -1, self)
                if event is not None:
                    self.events.append(event)

        # parse any RepeatBracket this measure is in.
        for rb in self.m21Measure.getSpannerSites([m21.spanner.RepeatBracket]):
            # measure is in this RepeatBracket
            if t.TYPE_CHECKING:
                assert isinstance(rb, m21.spanner.RepeatBracket)
            self.inRepeatBracket = True
            if rb.overrideDisplay:
                self.repeatBracketName = rb.overrideDisplay
            else:
                self.repeatBracketName = rb.number

            if rb.getFirst() == self.m21Measure:
                # this measure starts the RepeatBracket (it may also stop it)
                self.startsRepeatBracket = True

            if rb.getLast() == self.m21Measure:
                # this measure stops the RepeatBracket (it may also start it)
                self.stopsRepeatBracket = True

            # a measure can only be in one RepeatBracket, so stop looking
            break

        if len(list(self.m21Measure.voices)) == 0:
            # treat the measure itself as voice 0
            self._parseEventsIn(self.m21Measure, 0)
        else:
            # first parse any leading non-stream/non-notes elements (clefs, keysigs, timesigs)
            self._parseEventsAtTopLevelOf(self.m21Measure, firstBit=True)
            # ...then parse the voices...
            for voiceIndex, voice in enumerate(self.m21Measure.voices):
                emptyStartDuration: HumNum = voice.offset
                emptyEndDuration: HumNum = opFrac(
                    self.duration - (voice.offset + voice.duration.quarterLength)
                )
                self._parseEventsIn(voice, voiceIndex, emptyStartDuration, emptyEndDuration)

            # ... then parse the rest of the non-stream elements last, so that the ending barline
            # lands after any objects in the voices that are also at the last offset in the measure
            # (e.g. TextExpressions after the last note in the measure).
            self._parseEventsAtTopLevelOf(self.m21Measure, firstBit=False)

        self._sortEvents()

    def _parseEventsIn(
            self,
            m21Stream: t.Union[m21.stream.Voice, m21.stream.Measure],
            voiceIndex: int,
            emptyStartDuration: HumNumIn = 0,
            emptyEndDuration: HumNumIn = 0
    ) -> None:
        event: EventData
        durations: t.List[HumNum]
        startTime: HumNum
        if emptyStartDuration > 0:
            # make m21 hidden rests totalling this duration, and pretend they
            # were at the beginning of m21Stream
            durations = Convert.getPowerOfTwoDurationsWithDotsAddingTo(emptyStartDuration)
            startTime = self.startTime
            for duration in durations:
                m21StartRest: m21.note.Rest = m21.note.Rest(
                    duration=m21.duration.Duration(duration)
                )
                m21StartRest.style.hideObjectOnPrint = True
                event = EventData(m21StartRest, -1, voiceIndex, self, offsetInScore=startTime)
                if event is not None:
                    self.events.append(event)
                startTime = opFrac(startTime + duration)

        elementList: t.List[m21.base.Music21Object] = list(
            m21Stream.recurse().getElementsNotOfClass(m21.stream.Stream)
        )
        for elementIndex, element in enumerate(elementList):
            if (isinstance(element, m21.dynamics.Dynamic)
                    and M21Convert.getDynamicString(element) in ('sf', 'sfz')
                    and not M21Convert.isCentered(element)):
                # 'sf' and 'sfz' should be exported as 'z' or 'zz' on an associated note/chord
                # if possible, so look forward and backward for same-offset notes/chords to
                # do that with.  Note that we don't do this if the dynamic is centered between
                # two staves, since that is not really associated with a particular note.
                noteOrChord: t.Optional[m21.note.NotRest] = (
                    self._findAssociatedNoteOrChord(elementIndex, elementList)
                )
                if noteOrChord:
                    noteOrChord.humdrum_sf_or_sfz = element  # type: ignore
                    continue

            event = EventData(element, elementIndex, voiceIndex, self)
            if event is not None:
                self.events.append(event)
                # Make a separate event for any DynamicWedge (in score's
                #   spannerBundle) that starts with this element.
                #   Why?
                #       1. So we don't put the end of the wedge in the same slice as the
                #           endNote (wedges end at the end time of the endNote, not at
                #           the start time of the endNote).
                #       2. So wedge starts/ends will go in their own slice if necessary (e.g.
                #           if we choose not to export the voice-with-only-invisible-rests we
                #           may have made to position them correctly.
                extraEvents: t.List[EventData] = self._parseDynamicWedgesStartedOrStoppedAt(event)
                if extraEvents:
                    self.events += extraEvents

        if emptyEndDuration > 0:
            # make m21 hidden rests totalling this duration, and pretend they
            # were at the end of m21Stream
            durations = Convert.getPowerOfTwoDurationsWithDotsAddingTo(emptyEndDuration)
            startTime = opFrac(self.startTime + self.duration - opFrac(emptyEndDuration))
            for duration in durations:
                m21EndRest: m21.note.Rest = m21.note.Rest(duration=m21.duration.Duration(duration))
                m21EndRest.style.hideObjectOnPrint = True
                event = EventData(m21EndRest, -1, voiceIndex, self, offsetInScore=startTime)
                if event is not None:
                    self.events.append(event)
                startTime = opFrac(startTime + duration)

    @staticmethod
    def _findAssociatedNoteOrChord(
        elementIndex: int,
        elementList: t.List[m21.base.Music21Object]
    ) -> t.Optional[m21.note.NotRest]:
        # We're looking for a nearby note or chord with the same offset
        # (and not a grace note/chord).
        output: t.Optional[m21.note.NotRest] = None

        wantedOffset = elementList[elementIndex].offset
        proposed: m21.base.Music21Object

        # first look backward (but only until offset is different)
        index: int = elementIndex - 1
        while index in range(0, len(elementList)):
            proposed = elementList[index]
            if proposed.offset != wantedOffset:
                break
            if not isinstance(proposed, m21.note.NotRest):
                index -= 1
                continue
            if isinstance(proposed.duration,
                    (m21.duration.GraceDuration, m21.duration.AppoggiaturaDuration)):
                index -= 1
                continue
            output = proposed
            break

        if output is not None:
            return output

        # didn't find it backward, try forward
        index = elementIndex + 1
        while index in range(0, len(elementList)):
            proposed = elementList[index]
            if proposed.offset != wantedOffset:
                break
            if not isinstance(proposed, m21.note.NotRest):
                index += 1
                continue
            if isinstance(proposed.duration,
                    (m21.duration.GraceDuration, m21.duration.AppoggiaturaDuration)):
                index += 1
                continue
            output = proposed
            break

        return output

    def _parseDynamicWedgesStartedOrStoppedAt(self, event: EventData) -> t.List[EventData]:
        if t.TYPE_CHECKING:
            assert isinstance(event.m21Object, m21.note.GeneralNote)
        output: t.List[EventData] = []
        wedges: t.List[m21.dynamics.DynamicWedge] = (
            M21Utilities.getDynamicWedgesStartedOrStoppedWithGeneralNote(
                event.m21Object,
                self.spannerBundle)
        )
        wedge: m21.dynamics.DynamicWedge
        for wedge in wedges:
            ownerScore = self.ownerStaff.ownerPart.ownerScore
            score: m21.stream.Score = ownerScore.m21Score
            startNote: m21.note.GeneralNote = wedge.getFirst()
            endNote: m21.note.GeneralNote = wedge.getLast()
            thisEventIsStart: bool = startNote is event.m21Object
            thisEventIsEnd: bool = endNote is event.m21Object
            wedgeStartTime: t.Optional[HumNum] = None
            wedgeDuration: t.Optional[HumNum] = None
            wedgeEndTime: HumNum = opFrac(
                endNote.getOffsetInHierarchy(score) + endNote.duration.quarterLength
            )
            if thisEventIsStart:
                wedgeStartTime = startNote.getOffsetInHierarchy(score)
                wedgeDuration = opFrac(wedgeEndTime - wedgeStartTime)

            wedgeStartEvent: EventData
            wedgeEndEvent: EventData

            if thisEventIsStart and thisEventIsEnd:
                # We could make a combined event here, to try to get '>]', but
                # '>]' is evil because it requires the next token to the left
                # to be of the appropriate duration, and we have no (simple)
                # control over that.  So we always split up the start and end
                # so we only count on the start time of the appropriate token.

                # print(f'wedgeStartStopEvent: {event}', file=sys.stderr)
                wedgeStartEvent = EventData(
                    wedge, -1, event.voiceIndex, self,
                    offsetInScore=wedgeStartTime,
                    duration=wedgeDuration
                )
                output.append(wedgeStartEvent)

                wedgeEndEvent = EventData(
                    wedge, -1, event.voiceIndex, self,
                    offsetInScore=wedgeEndTime,
                    duration=0
                )
                output.append(wedgeEndEvent)
            elif thisEventIsStart:
                # add the start event, with duration
                # print(f'wedgeStartEvent: {event}', file=sys.stderr)
                wedgeStartEvent = EventData(
                    wedge, -1, event.voiceIndex, self,
                    offsetInScore=wedgeStartTime,
                    duration=wedgeDuration
                )
                output.append(wedgeStartEvent)
            elif thisEventIsEnd:
                # add the end event (duration == 0)
                # but add it to the same measure/voice as the wedge start event
                # print(f'wedgeStopEvent: {event}', file=sys.stderr)
                matchingStartEvent: t.Optional[EventData] = (
                    ownerScore.eventFromM21Object.get(id(wedge), None)
                )
                endVoiceIndex: int
                if matchingStartEvent is None:
                    # print('wedgeStop with no wedgeStart, putting it in its own measure/voice',
                    #           file=sys.stderr)
                    endVoiceIndex = event.voiceIndex
                    endSelf = self
                else:
                    endVoiceIndex = matchingStartEvent.voiceIndex
                    endSelf = matchingStartEvent.ownerMeasure
                wedgeEndEvent = EventData(
                    wedge, -1, endVoiceIndex, endSelf,
                    offsetInScore=wedgeEndTime,
                    duration=0
                )
                output.append(wedgeEndEvent)

        return output

    def _parseEventsAtTopLevelOf(
        self,
        m21Stream: m21.stream.Measure,
        firstBit: t.Optional[bool]  # None -> all of it, True -> first bit, False -> non-first-bit
    ) -> None:
        skipping: bool = False
        if firstBit is False:
            skipping = True

        for elementIndex, element in enumerate(m21Stream):
            if 'Stream' in element.classes:
                # skip substreams, just parse the top-level objects
                if firstBit is True:
                    # we hit a Voice, done with first bit
                    return
                elif firstBit is False:
                    # we hit a Voice, done with skipping
                    skipping = False
                continue

            if firstBit is True:
                if isinstance(element, (m21.note.GeneralNote, m21.stream.Stream)):
                    # done with first bit
                    return
            elif firstBit is False and skipping:
                if not isinstance(element, m21.note.GeneralNote):
                    # skip first bit
                    continue
                else:
                    # found a note, done with skipping
                    skipping = False

            event: EventData = EventData(element, elementIndex, -1, self)
            if event is not None:
                self.events.append(event)

                extraEvents: t.List[EventData] = self._parseDynamicWedgesStartedOrStoppedAt(event)
                if extraEvents:
                    self.events += extraEvents

    '''
    //////////////////////////////
    //
    // MxmlMeasure::sortEvents -- Sorts events for the measure into
    //   time order.  They are split into zero-duration events and
    //   non-zero events.  mevent_floating type are placed into the
    //   non-zero events even though they have zero duration (this is
    //   for harmony not attached to a note attack, and will be
    //   eventually including basso continuo figuration having the
    //   same situation).
    '''
    def _sortEvents(self) -> None:
        self.events.sort(key=lambda event: event.startTime)

        times: t.List[HumNum] = []  # will be sorted same as self.events (by startTime)
        for event in self.events:
            # don't add duplicated time entries (like a set)
            if not times or event.startTime != times[-1]:
                times.append(event.startTime)

        self.sortedEvents = []
        for val in times:
            self.sortedEvents.append(SimultaneousEvents())
            self.sortedEvents[-1].startTime = val

        # setup sorted access:
        mapping: t.Dict[HumNum, SimultaneousEvents] = {}
        for sortedEvent in self.sortedEvents:
            mapping[sortedEvent.startTime] = sortedEvent

        for event in self.events:
            startTime: HumNum = event.startTime
            duration: HumNum = event.duration
            if duration != 0 or event.isDynamicWedgeStartOrStop:
                # We treat dynamicWedge start/stop events as having duration even though
                # the stop events do not.  This is so that they can go in the same
                # slice with notes/rests, or on their own slice if they have a unique
                # timestamp.
                mapping[startTime].nonZeroDur.append(event)
            else:
                mapping[startTime].zeroDur.append(event)

        # debugging
        '''
        for e in self.sortedEvents:
            if len(e.zeroDur) > 0:
                print(e.startTime, 'z\t', end='', file=sys.stderr)
                for z in e.zeroDur:
                    print(' ', z.name, end='', file=sys.stderr)
                    print('(', z.partIndex, end='', file=sys.stderr)
                    print(',', z.staffIndex, end='', file=sys.stderr)
                    print(',', z.voiceIndex, end='', file=sys.stderr)
                    print(')', end='', file=sys.stderr)
                print('', file=sys.stderr)

            if len(e.nonZeroDur) > 0:
                print(e.startTime, 'n\t', end='', file=sys.stderr)
                for nz in e.nonZeroDur:
                    print(' ', nz.name, end='', file=sys.stderr)
                    print('(', nz.partIndex, end='', file=sys.stderr)
                    print(',', nz.staffIndex, end='', file=sys.stderr)
                    print(',', nz.voiceIndex, end='', file=sys.stderr)
                    print(')', end='', file=sys.stderr)
                print('', file=sys.stderr)
        '''
    '''
    //////////////////////////////
    //
    // MxmlMeasure::setStartTimeOfMeasure --
    '''
    def _setStartTimeOfMeasure(self) -> None:
        if self.ownerStaff is None:
            self._startTime = opFrac(0)
            return

        if self._prevMeasData is None:
            self._startTime = opFrac(0)
            return

        self._startTime = opFrac(self._prevMeasData.startTime + self._prevMeasData.duration)

    '''
    //////////////////////////////
    //
    // MxmlMeasure::reportEditorialAccidentalToOwner --
        The RDF signifier is returned, so we know what to put in the token
    //
    '''
    def reportEditorialAccidentalToOwner(self, editorialStyle: str) -> str:
        return self.ownerStaff.reportEditorialAccidentalToOwner(editorialStyle)

    '''
    //////////////////////////////
    //
    // MxmlMeasure::reportCaesuraToOwner --
        The RDF signifier is returned, so we know what to put in the token
    '''
    def reportCaesuraToOwner(self) -> str:
        return self.ownerStaff.reportCaesuraToOwner()

    def reportCueSizeToOwner(self) -> str:
        return self.ownerStaff.reportCueSizeToOwner()

    def reportNoteColorToOwner(self, color: str) -> str:
        return self.ownerStaff.reportNoteColorToOwner(color)

    def reportLinkedSlurToOwner(self) -> str:
        return self.ownerStaff.reportLinkedSlurToOwner()

    def reportVerseCountToOwner(self, verseCount: int) -> None:
        self.ownerStaff.receiveVerseCount(verseCount)

    '''
    //////////////////////////////
    //
    // MxmlMeasure::reportDynamicToOwner --
    '''
    def reportDynamicToOwner(self) -> None:
        self.ownerStaff.receiveDynamic()
