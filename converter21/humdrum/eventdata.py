# ------------------------------------------------------------------------------
# Name:          EventData.py
# Purpose:       EventData is an object somewhere between an m21 note/dynamic/etc
#                and a GridVoice (HumdrumToken) or GridSide (HumdrumToken).
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys

import music21 as m21
from music21.common import opFrac

from converter21.humdrum import HumNum, HumNumIn
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

class EventData:
    def __init__(
        self,
        element: m21.base.Music21Object,
        elementIndex: int,
        voiceIndex: int,
        ownerMeasure,
        offsetInScore: HumNumIn | None = None,
        duration: HumNumIn | None = None
    ) -> None:
        from converter21.humdrum import MeasureData
        from converter21.humdrum import ScoreData
        self.ownerMeasure: MeasureData = ownerMeasure
        self.ownerScore: ScoreData = ownerMeasure.ownerStaff.ownerPart.ownerScore
        self.spannerBundle: m21.spanner.SpannerBundle = (
            self.ownerMeasure.spannerBundle  # from ownerScore, ultimately
        )
        self._startTime: HumNum = opFrac(-1)
        self._duration: HumNum = opFrac(-1)
        self._durationTuplets: tuple[m21.duration.Tuplet, ...] = ()
        self._voiceIndex: int = voiceIndex
        self._elementIndex: int = elementIndex
        self._element: m21.base.Music21Object = element
        self._name: str = ''
        self._texts: list[m21.expressions.TextExpression] = []
        self._tempos: list[m21.tempo.TempoIndication] = []
        self._dynamics: list[m21.dynamics.Dynamic | m21.dynamics.DynamicWedge] = []
        self._myTextsComputed: bool = False
        self._myDynamicsComputed: bool = False

        self._parseEvent(element, offsetInScore, duration)
        self.ownerScore.eventFromM21Object[id(element)] = self

    def __str__(self) -> str:
        output: str = self.kernTokenString()
        if output:
            return output
        return self.m21Object.classes[0]  # at least say what type of m21Object it was

    def _parseEvent(
        self,
        element: m21.base.Music21Object,
        offsetInScore: HumNumIn | None,
        duration: HumNumIn | None
    ) -> None:
        if offsetInScore is not None:
            self._startTime = opFrac(offsetInScore)
        else:
            ownerScore = self.ownerMeasure.ownerStaff.ownerPart.ownerScore
            self._startTime = opFrac(element.getOffsetInHierarchy(ownerScore.m21Score))

        if duration is not None:
            self._duration = opFrac(duration)
        else:
            if isinstance(element, m21.harmony.ChordSymbol):
                # We pretend all ChordSymbols have duration == 0.
                # They generally do, but some analysis algorithms like to figure
                # out a duration for each ChordSym, and we should ignore that.
                self._duration = 0.
            else:
                self._duration = opFrac(element.duration.quarterLength)
                if element.duration.tuplets:
                    self._durationTuplets = element.duration.tuplets

        ottavas: list[m21.spanner.Ottava] = self.getOttavasStartedHere()
        for ottava in ottavas:
            if ottava.transposing:
                # Convert the Ottava to a non-transposing Ottava by transposing all pitches
                # to their sounding octave.  This makes the Humdrum notes export correctly.
                ottava.fill(self.ownerMeasure.ownerStaff.m21PartStaff)
                ottava.performTransposition()

        # element.classes is a tuple containing the names (strings, not objects) of classes
        # that this object belongs to -- starting with the object's class name and going up
        # the mro() for the object.
        # So element.classes[0] is the name of the element's class.
        # e.g. 'Note' for m21.note.Note
        self._name = element.classes[0]

    @property
    def isChordSymbol(self) -> bool:
        return isinstance(self.m21Object, m21.harmony.ChordSymbol)

    @property
    def isDynamicWedgeStartOrStop(self) -> bool:
        return isinstance(self.m21Object, m21.dynamics.DynamicWedge)

    @property
    def isDynamicWedgeStop(self) -> bool:
        if not isinstance(self.m21Object, m21.dynamics.DynamicWedge):
            return False
        if self.duration == 0:
            return True  # starts always have non-zero duration
        return False

    @property
    def isDynamicWedgeStart(self) -> bool:
        if not isinstance(self.m21Object, m21.dynamics.DynamicWedge):
            return False
        if self.duration == 0:
            return False  # starts always have non-zero duration
        return True

    @property
    def elementIndex(self) -> int:
        return self._elementIndex

    @property
    def elementNumber(self) -> int:
        return self.elementIndex + 1

    @property
    def voiceIndex(self) -> int:
        return self._voiceIndex

    @property
    def voiceNumber(self) -> int:
        return self.voiceIndex + 1

    @property
    def measureIndex(self) -> int:
        return self.ownerMeasure.measureIndex

    @property
    def measureNumber(self) -> int:
        return self.measureIndex + 1

    @property
    def staffIndex(self) -> int:
        return self.ownerMeasure.staffIndex

    @property
    def staffNumber(self) -> int:
        return self.staffIndex + 1

    @property
    def partIndex(self) -> int:
        return self.ownerMeasure.partIndex

    @property
    def partNumber(self) -> int:
        return self.partIndex + 1

    @property
    def startTime(self) -> HumNum:
        return self._startTime

    @property
    def duration(self) -> HumNum:
        return self._duration

    @property
    def isTupletStart(self) -> bool:
        if self._durationTuplets is not None and len(self._durationTuplets) > 0:
            return self._durationTuplets[0].type == 'start'
        return False

    @property
    def suppressTupletNum(self) -> bool:
        if not self._durationTuplets:
            return False
        return self._durationTuplets[0].tupletActualShow is None

    @property
    def suppressTupletBracket(self) -> bool:
        if not self._durationTuplets:
            return False
        return self._durationTuplets[0].bracket is False

    @property
    def name(self) -> str:
        return self._name

    @property
    def m21Object(self) -> m21.base.Music21Object:
        return self._element

    @property
    def texts(self) -> list[m21.expressions.TextExpression]:
        if not self._myTextsComputed:
            if isinstance(self.m21Object, m21.note.GeneralNote):
                self._texts = M21Utilities.getTextExpressionsFromGeneralNote(self.m21Object)
            self._myTextsComputed = True
        return self._texts

    @property
    def tempos(self) -> list[m21.tempo.TempoIndication]:
        return self._tempos

    def getOttavasStartedHere(self) -> list[m21.spanner.Ottava]:
        output: list[m21.spanner.Ottava] = []
        for sp in self.m21Object.getSpannerSites():
            if not isinstance(sp, m21.spanner.Ottava):
                continue
            if not M21Utilities.isIn(sp, self.spannerBundle):
                continue
            if sp.isFirst(self.m21Object):
                output.append(sp)
        return output

    @property
    def isOttavaStartOrStop(self) -> bool:
        for sp in self.m21Object.getSpannerSites():
            if not isinstance(sp, m21.spanner.Ottava):
                continue
            if not M21Utilities.isIn(sp, self.spannerBundle):
                continue
            if sp.isFirst(self.m21Object):
                return True
            if sp.isLast(self.m21Object):
                return True
        return False

    def getOttavaTokenStrings(self) -> tuple[list[str], list[str]]:
        # returns an ottava starts list and an ottava ends list (both sorted to nest properly)

        def spannerQL(spanner: m21.spanner.Spanner) -> HumNum:
            return M21Utilities.getSpannerQuarterLength(spanner, self.ownerScore.m21Score)

        ottavaStarts: list[m21.spanner.Ottava] = []
        ottavaStops: list[m21.spanner.Ottava] = []

        for sp in self.m21Object.getSpannerSites():
            if not isinstance(sp, m21.spanner.Ottava):
                continue
            if not M21Utilities.isIn(sp, self.spannerBundle):
                continue
            if sp.isFirst(self.m21Object):
                ottavaStarts.append(sp)
            if sp.isLast(self.m21Object):
                ottavaStops.append(sp)

        # Sort the starts by longest ottava first, and the stops by shortest ottava first
        # so they nest properly.  (I wonder if ottavas ever actually overlap; they certainly
        # can, in music21. If they do overlap, this will be important.)
        ottavaStarts.sort(key=spannerQL, reverse=True)
        ottavaStops.sort(key=spannerQL)

        outputStarts: list[str] = []
        outputStops: list[str] = []

        for sp in ottavaStarts:
            outputStarts.append(M21Convert.getKernTokenStringFromM21OttavaStart(sp))

        for sp in ottavaStops:
            outputStops.append(M21Convert.getKernTokenStringFromM21OttavaStop(sp))

        return outputStarts, outputStops

    '''
        getNoteKernTokenString -- get a **kern token string and a list of layout strings
        for an event that is a GeneralNote.
        If the event is not a GeneralNote (Chord, Note, Rest, Unpitched), we return ('', []).
        If event is a Chord, we return a space-delimited token string containing all the
        appropriate subtokens, and a list of all the layouts for the chord.
    '''
    def getNoteKernTokenStringAndLayouts(self) -> tuple[str, list[str]]:
        # We pass in self to get reports of the existence of editorial accidentals, ornaments,
        # etc. These reports get passed up the EventData.py/MeasureData.py reporting chain up
        # to PartData.py, where they are stored and/or acted upon.
        return M21Convert.kernTokenStringAndLayoutsFromM21GeneralNote(
            self.m21Object, self.spannerBundle, self
        )

    def kernTokenString(self) -> str:
        # for debugging output; real code uses getNoteKernTokenStringAndLayouts() or
        # getDynamicWedgeString.
        tokenString: str = ''
        tokenString, _ignore = self.getNoteKernTokenStringAndLayouts()
        if not tokenString:
            tokenString = self.getDynamicWedgeString()
        return tokenString

    def getDynamicWedgeString(self) -> str:
        if not self.isDynamicWedgeStartOrStop:
            return ''

        return M21Convert.getDynamicWedgeString(
            self.m21Object, self.isDynamicWedgeStart, self.isDynamicWedgeStop
        )

    '''
    //////////////////////////////
    //
    // MxmlEvent::reportEditorialAccidentalToOwner --
        The RDF signifier (chosen well above us) is returned, so we know what to put in the token
    '''
    def reportEditorialAccidentalToOwner(self, editorialStyle: str) -> str:
        return self.ownerMeasure.reportEditorialAccidentalToOwner(editorialStyle)

    '''
    //////////////////////////////
    //
    // MxmlEvent::reportCaesuraToOwner -- inform the owner that there is a caesura
    //    that needs an RDF marker.
        The RDF signifier (chosen well above us) is returned, so we know what to put in the token
    '''
    def reportCaesuraToOwner(self) -> str:
        return self.ownerMeasure.reportCaesuraToOwner()

    def reportCueSizeToOwner(self) -> str:
        return self.ownerMeasure.reportCueSizeToOwner()

    def reportNoteColorToOwner(self, color: str) -> str:
        return self.ownerMeasure.reportNoteColorToOwner(color)

    def reportLinkedSlurToOwner(self) -> str:
        return self.ownerMeasure.reportLinkedSlurToOwner()

    def reportDynamicToOwner(self) -> None:
        self.ownerMeasure.reportDynamicToOwner()

    def reportHarmonyToOwner(self) -> None:
        self.ownerMeasure.reportHarmonyToOwner()

    def reportVerseCountToOwner(self, verseCount: int) -> None:
        self.ownerMeasure.reportVerseCountToOwner(verseCount)
