# ------------------------------------------------------------------------------
# Name:          MeasureData.py
# Purpose:       MeasureData is an object somewhere between an m21 Measure
#                and a GridMeasure.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021 Greg Chapman
# License:       BSD, see LICENSE
# ------------------------------------------------------------------------------
import sys
from typing import Union
import music21 as m21

from converter21.humdrum import HumNum
from converter21.humdrum import EventData

### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

class SimultaneousEvents:
    def __init__(self):
        self.startTime : HumNum = HumNum(-1) # start time of events
        self.duration  : HumNum = HumNum(-1) # max duration of events?
        self.zeroDur   : [EventData] = []    # zero-duration events at this time
        self.nonZeroDur: [EventData] = []    # non-zero-duration events at this time

class MeasureData:
    def __init__(self, measure: m21.stream.Measure,
                       ownerStaff,
                       measureIndex: int):
        from converter21.humdrum import StaffData
        ownerStaff: StaffData
        self.m21Measure: m21.stream.Measure = measure
        self.ownerStaff: StaffData = ownerStaff
        self._measureIndex: int = measureIndex
        self._startTime: HumNum = HumNum(-1)
        self._duration: HumNum = HumNum(-1)
        self._events: [EventData] = []
        self._sortedEvents: [SimultaneousEvents] = [] # list of startTime-binned events
        self._parseMeasure() # generates _events and then _sortedEvents

    @property
    def measureIndex(self) -> int:
        return self._measureIndex

    @property
    def staffIndex(self) -> int:
        return self.ownerStaff.staffIndex

    @property
    def partIndex(self) -> int:
        return self.ownerStaff.partIndex

    @property
    def previousMeasure(self): # -> MeasureData:
        prevIndex: int = self.measureIndex - 1
        if 0 <= prevIndex < self.ownerStaff.measureCount:
            return self.ownerStaff.measures[prevIndex]
        return None

    @property
    def nextMeasure(self): # -> MeasureData:
        nextIndex: int = self.measureIndex + 1
        if 0 <= nextIndex < self.ownerStaff.measureCount:
            return self.ownerStaff.measures[nextIndex]
        return None

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
    // MxmlMeasure::parseMeasure -- Reads music21 data for one staff's measure.
    '''
    def _parseMeasure(self):
        self._setStartTimeOfMeasure()
        self._duration = HumNum(self.m21Measure.duration)
        # m21 tracks timesigdur for us in barDuration, which is always the latest timeSig duration
        self._timeSigDur = self.m21Measure.barDuration

        if len(list(self.m21Measure.voices)) == 0:
            # treat the measure itself as voice 0
            self._parseEventsIn(self.m21Measure, 0)
        else:
            # parse the 0-offset non-streams first...
            self._parseEventsAtTopLevelOf(self.m21Measure)
            # ... then parse the voices
            for voiceIndex, voice in enumerate(self.m21Measure.voices):
                self._parseEventsIn(voice, voiceIndex)

        self._sortEvents()

    def _parseEventsIn(self, m21Stream: Union[m21.stream.Voice, m21.stream.Measure],
                             voiceIndex: int):
        m21FlatStream: Union[m21.stream.Voice, m21.stream.Measure] = m21Stream.flat
        for elementIndex, element in enumerate(m21FlatStream):
            event: EventData = EventData(element, elementIndex, voiceIndex, self)
            if event is not None:
                self._events.append(event)

    def _parseEventsAtTopLevelOf(self, m21Stream: m21.stream.Measure):
        for elementIndex, element in enumerate(m21Stream):
            if 'Stream' in element.classes:
                # skip substreams, just parse the top-level objects
                continue

            event: EventData = EventData(element, elementIndex, -1, self)
            if event is not None:
                self._events.append(event)

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
    def _sortEvents(self):
        times = set()
        for event in self._events:
            times.add(event.startTime)

        self._sortedEvents = []
        for val in times:
            self._sortedEvents.append(SimultaneousEvents())
            self._sortedEvents[-1].startTime = val

        # setup sorted access:
        mapping = dict()
        for sortedEvent in self._sortedEvents:
            mapping[sortedEvent.startTime] = sortedEvent

        for event in self._events:
            startTime: HumNum = event.startTime
            duration: HumNum = event.duration
            if event.isFloating:
                mapping[startTime].nonZeroDur.append(event)
            elif duration == 0:
                mapping[startTime].zeroDur.append(event)
            else:
                mapping[startTime].nonZeroDur.append(event)

        # debugging
        for e in self._sortedEvents:
            if len(e.zeroDur) > 0:
                print(e.startTime, 'z\t', end='', file=sys.stderr)
                for z in e.zeroDur:
                    print(' ', z.name, end='', file=sys.stderr)
                    print('(', z.partNumber, end='', file=sys.stderr)
                    print(',', z.staffNumber, end='', file=sys.stderr)
                    print(',', z.voiceNumber, end='', file=sys.stderr)
                    print(')', end='', file=sys.stderr)
                print('', file=sys.stderr)

            if len(e.nonZeroDur) > 0:
                print(e.startTime, 'n\t', end='', file=sys.stderr)
                for nz in e.nonZeroDur:
                    print(' ', nz.name, end='', file=sys.stderr)
                    print('(', nz.partNumber, end='', file=sys.stderr)
                    print(',', nz.staffNumber, end='', file=sys.stderr)
                    print(',', nz.voiceNumber, end='', file=sys.stderr)
                    print(')', end='', file=sys.stderr)
                print('', file=sys.stderr)

    '''
    //////////////////////////////
    //
    // MxmlMeasure::setStartTimeOfMeasure --
    '''
    def _setStartTimeOfMeasure(self):
        if self.ownerStaff is None:
            self._startTime = HumNum(0)
            return

        prev: MeasureData = self.previousMeasure
        if prev is None:
            self._startTime = HumNum(0)
            return

        self._startTime = prev.startTime + prev.duration

    '''
    //////////////////////////////
    //
    // MxmlMeasure::receiveEditorialAccidentalFromChild --
    '''
    def receiveEditorialAccidentalFromChild(self, editorialStyle: str):
        self.ownerStaff.recieveEditorialAccidental(editorialStyle)
