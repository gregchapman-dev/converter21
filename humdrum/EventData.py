# ------------------------------------------------------------------------------
# Name:          EventData.py
# Purpose:       EventData is an object somewhere between an m21 note/dynamic/etc
#                and a GridVoice (HumdrumToken) or GridSide (HumdrumToken).
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

from humdrum import HumNum
from humdrum import M21Convert
from humdrum import M21Utilities

### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

class EventData:
    def __init__(self, element: m21.base.Music21Object,
                       elementIndex: int,
                       voiceIndex: int,
                       ownerMeasure):
        from Humdrum import MeasureData
        ownerMeasure: MeasureData
        self.ownerMeasure: MeasureData = ownerMeasure
        self._startTime: HumNum = HumNum(-1)
        self._duration: HumNum = HumNum(-1)
        self._voiceIndex: int = voiceIndex
        self._elementIndex: int = elementIndex
        self._element: m21.base.Music21Object = element
        self._name: str = ''
        self._texts: [m21.expressions.TextExpression] = []
        self._tempos: [m21.tempo.TempoIndication] = []
        self._dynamics: [Union[m21.dynamics.Dynamic, m21.dynamics.DynamicWedge]] = []
        self._myTextsComputed: bool = False
        self._myDynamicsComputed: bool = False

        self._parseEvent(element)

    def _parseEvent(self, element: m21.base.Music21Object):
        ownerScore = self.ownerMeasure.ownerStaff.ownerPart.ownerScore
        self._startTime = ownerScore.getSemiFlatScore().elementOffset(element)
        self._duration = HumNum(element.duration.quarterLength)
        # element.classes is a tuple containing the names (strings, not objects) of classes
        # that this object belongs to -- starting with the object's class name and going up
        # the mro() for the object.
        # So element.classes[0] is the name of the element's class.
        # e.g. 'Note' for m21.note.Note
        self._name = element.classes[0]

    @property
    def elementIndex(self) -> int:
        return self._elementIndex

    @property
    def voiceIndex(self) -> int:
        return self._voiceIndex

    @property
    def measureIndex(self) -> int:
        return self.ownerMeasure.measureIndex

    @property
    def staffIndex(self) -> int:
        return self.ownerMeasure.staffIndex

    @property
    def partIndex(self) -> int:
        return self.ownerMeasure.partIndex

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
    def texts(self) -> [m21.expressions.TextExpression]:
        if not self._myTextsComputed:
            self._texts = M21Utilities.getTextExpressionsFromGeneralNote(self.m21Object)
            self._myTextsComputed = True
        return self._texts

    @property
    def dynamics(self) -> [Union[m21.dynamics.Dynamic, m21.dynamics.DynamicWedge]]:
        if not self._myDynamicsComputed:
            self._dynamics = M21Utilities.getDynamicWedgesFromGeneralNote(self.m21Object)
            self._myDynamicsComputed = True
        return self._dynamics

    @property
    def tempos(self) -> [m21.tempo.TempoIndication]:
        return self._tempos

    '''
        getNoteKernTokenString -- get a **kern token string and a list of layout strings
        for an event that is a GeneralNote.
        If the event is not a GeneralNote (Chord, Note, Rest, Unpitched), we return ('', []).
        If event is a Chord, we return a space-delimited token string containing all the
        appropriate subtokens, and a list of all the layouts for the chord.
    '''
    def getNoteKernTokenString(self) -> (str, [str]):
        # We pass in self to get reports of the existence of editorial accidentals, ornaments,
        # etc. These reports get passed up the EventData.py/MeasureData.py reporting chain up
        # to PartData.py, where they are stored and/or acted upon.
        return M21Convert.kernTokenStringFromM21GeneralNote(self.m21Object, self)

    '''
    //////////////////////////////
    //
    // MxmlEvent::reportEditorialAccidentalToOwner --
    '''
    def reportEditorialAccidentalToOwner(self, editorialStyle: str):
        self.ownerMeasure.receiveEditorialAccidentalFromChild(editorialStyle)
