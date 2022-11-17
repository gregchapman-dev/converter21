# ------------------------------------------------------------------------------
# Name:          EventData.py
# Purpose:       EventData is an object somewhere between an m21 note/dynamic/etc
#                and a GridVoice (HumdrumToken) or GridSide (HumdrumToken).
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
            offsetInScore: t.Optional[HumNumIn] = None,
            duration: t.Optional[HumNumIn] = None
    ) -> None:
        from converter21.humdrum import MeasureData
        from converter21.humdrum import ScoreData
        self.ownerMeasure: MeasureData = ownerMeasure
        self.spannerBundle: m21.spanner.SpannerBundle = (
            self.ownerMeasure.spannerBundle  # from ownerScore, ultimately
        )
        self._startTime: HumNum = opFrac(-1)
        self._duration: HumNum = opFrac(-1)
        self._voiceIndex: int = voiceIndex
        self._elementIndex: int = elementIndex
        self._element: m21.base.Music21Object = element
        self._elementType: t.Type = type(element)
        self._name: str = ''
        self._texts: t.List[m21.expressions.TextExpression] = []
        self._tempos: t.List[m21.tempo.TempoIndication] = []
        self._dynamics: t.List[t.Union[m21.dynamics.Dynamic, m21.dynamics.DynamicWedge]] = []
        self._myTextsComputed: bool = False
        self._myDynamicsComputed: bool = False

        self._parseEvent(element, offsetInScore, duration)

        ownerScore: ScoreData = ownerMeasure.ownerStaff.ownerPart.ownerScore
        ownerScore.eventFromM21Object[id(element)] = self

    def __str__(self) -> str:
        output: str = self.kernTokenString()
        if output:
            return output
        return self.m21Object.classes[0]  # at least say what type of m21Object it was

    def _parseEvent(
            self,
            element: m21.base.Music21Object,
            offsetInScore: t.Optional[HumNumIn],
            duration: t.Optional[HumNumIn]
    ) -> None:
        if offsetInScore is not None:
            self._startTime = opFrac(offsetInScore)
        else:
            ownerScore = self.ownerMeasure.ownerStaff.ownerPart.ownerScore
            self._startTime = opFrac(element.getOffsetInHierarchy(ownerScore.m21Score))

        if duration is not None:
            self._duration = opFrac(duration)
        else:
            self._duration = opFrac(element.duration.quarterLength)

        # element.classes is a tuple containing the names (strings, not objects) of classes
        # that this object belongs to -- starting with the object's class name and going up
        # the mro() for the object.
        # So element.classes[0] is the name of the element's class.
        # e.g. 'Note' for m21.note.Note
        self._name = element.classes[0]

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
    def name(self) -> str:
        return self._name

    @property
    def m21Object(self) -> m21.base.Music21Object:
        return self._element

    @property
    def texts(self) -> t.List[m21.expressions.TextExpression]:
        if not self._myTextsComputed:
            if isinstance(self.m21Object, m21.note.GeneralNote):
                self._texts = M21Utilities.getTextExpressionsFromGeneralNote(self.m21Object)
            self._myTextsComputed = True
        return self._texts

    @property
    def tempos(self) -> t.List[m21.tempo.TempoIndication]:
        return self._tempos

    '''
        getNoteKernTokenString -- get a **kern token string and a list of layout strings
        for an event that is a GeneralNote.
        If the event is not a GeneralNote (Chord, Note, Rest, Unpitched), we return ('', []).
        If event is a Chord, we return a space-delimited token string containing all the
        appropriate subtokens, and a list of all the layouts for the chord.
    '''
    def getNoteKernTokenStringAndLayouts(self) -> t.Tuple[str, t.List[str]]:
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

    def reportVerseCountToOwner(self, verseCount: int) -> None:
        self.ownerMeasure.reportVerseCountToOwner(verseCount)
