# ------------------------------------------------------------------------------
# Name:          M21Utilities.py
# Purpose:       Utility functions for music21 objects
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------

#    All methods are static.  M21Utilities is just a namespace for these conversion functions and
#    look-up tables.

import re
import sys
import copy
import typing as t

import music21 as m21
from music21.common.types import OffsetQL, OffsetQLIn, StepName
from music21.common.numberTools import opFrac

class CannotMakeScoreFromObjectError(Exception):
    pass


class NoMusic21VersionError(Exception):
    pass


# pylint: disable=protected-access

DEBUG: bool = False
TUPLETDEBUG: bool = True
BEAMDEBUG: bool = True

def durationWithTupletDebugReprInternal(dur: m21.duration.Duration) -> str:
    output: str = f'dur.qL={dur.quarterLength}'
    if len(dur.tuplets) >= 1:
        tuplet: m21.duration.Tuplet = dur.tuplets[0]
        output += ' tuplets[0]: ' + tuplet._reprInternal()
        output += ' bracket=' + str(tuplet.bracket)
        output += ' type=' + str(tuplet.type)
    return output

def noteDebugReprInternal(n: m21.note.Note) -> str:
    output = n.name
    if BEAMDEBUG and hasattr(n, 'beams') and n.beams:
        output += ' beams: ' + n.beams._reprInternal()
    if TUPLETDEBUG:
        output += ' ' + durationWithTupletDebugReprInternal(n.duration)
    return output

def unpitchedDebugReprInternal(u: m21.note.Unpitched) -> str:
    output = m21.note.GeneralNote._reprInternal(u)
    if BEAMDEBUG and hasattr(u, 'beams') and u.beams:
        output += ' beams: ' + u.beams._reprInternal()
    if TUPLETDEBUG:
        output += ' ' + durationWithTupletDebugReprInternal(u.duration)
    return output

def chordDebugReprInternal(c: m21.chord.Chord) -> str:
    if not c.pitches:
        return m21.note.GeneralNote._reprInternal(c)

    allPitches = []
    for thisPitch in c.pitches:
        allPitches.append(thisPitch.nameWithOctave)

    output = ' '.join(allPitches)
    if BEAMDEBUG and hasattr(c, 'beams') and c.beams:
        output += ' beams: ' + c.beams._reprInternal()
    if TUPLETDEBUG:
        output += ' ' + durationWithTupletDebugReprInternal(c.duration)
    return output

def setDebugReprInternal(self, method) -> None:
    if DEBUG:
        import types
        self._reprInternal = types.MethodType(method, self)

# pylint: disable=protected-access


class M21StaffGroupTree:
    # Used during export
    def __init__(
            self,
            sg: m21.layout.StaffGroup,
            staffNumbersByM21Part: dict[m21.stream.Part, int]
    ) -> None:
        # about this staff group
        self.staffGroup: m21.layout.StaffGroup = sg
        self.staffNums: set[int] = set(staffNumbersByM21Part[m21Part]
                                            for m21Part in
                                                sg.spannerStorage.elements)
        self.numStaves: int = len(self.staffNums)
        self.lowestStaffNumber: int = min(self.staffNums)

        # tree links
        self.children: list[M21StaffGroupTree] = []


class M21StaffGroupDescriptionTree:
    # Used during import
    def __init__(self) -> None:
        # about this group description
        self.symbol: str = 'none'       # see m21.layout.StaffGroup.symbol
        self.barTogether: bool | str = False  # see m21.layout.StaffGroup.barTogether

        # instrument should be set if there is an instrument for the staff group.
        # The Humdrum importer doesn't use this field, as it has other ways of
        # tracking this.
        self.instrument: m21.instrument.Instrument | None = None

        # Humdrum importer sets groupNum instead, and then gathers names later
        # using that groupNum.
        self.groupNum: int = 0

        # staves referenced by this group (includes staves in subgroups).
        # staffIds should be in staff order (on the page, from top to bottom).
        self.staffIds: list[int | str] = []  # Humdrum likes int, MEI likes str

        # staves actually in this group (i.e. not in a subgroup).
        # ownedStaffIds should be in staff order (on the page, from top to bottom).
        self.ownedStaffIds: list[int | str] = []

        # staffInstruments should contain the instrument for each staff (if there
        # is one). The Humdrum importer doesn't use this field, as it has other
        # ways of tracking this.
        self.staffInstruments: list[m21.instrument.Instrument | None] = []

        # ownedStaffInstruments should contain the instrument for each owned staff
        # (if there is one). The Humdrum importer doesn't use this field, as it has
        # other ways of tracking this.
        self.ownedStaffInstruments: list[m21.instrument.Instrument | None] = []

        # tree links:
        # children == subgroups, parent = enclosing group (None for top)
        self.children: list[M21StaffGroupDescriptionTree] = []
        self.parent: M21StaffGroupDescriptionTree | None = None


class M21Utilities:

    @staticmethod
    def createNote(
        placeHolder: m21.Music21Object | None = None
    ) -> m21.note.Note:
        note = m21.note.Note()

        # for debugging, override this note's _reprInternal so we can see any Beams.
        setDebugReprInternal(note, noteDebugReprInternal)

        # Now replace placeHolder with note in every spanner that references it.
        # (This is for, e.g., slurs that were created before this note was there.)
        if placeHolder is not None:
            spanners = placeHolder.getSpannerSites()
            for spanner in spanners:
                spanner.replaceSpannedElement(placeHolder, note)

        return note

    @staticmethod
    def createUnpitched(
        placeHolder: m21.Music21Object | None = None
    ) -> m21.note.Unpitched:
        unpitched = m21.note.Unpitched()

        # for debugging, override this unpitched's _reprInternal so we can see any Beams.
        setDebugReprInternal(unpitched, unpitchedDebugReprInternal)

        # Now replace placeHolder with unpitched in every spanner that references it.
        # (This is for, e.g., slurs that were created before this unpitched was there.)
        if placeHolder is not None:
            spanners = placeHolder.getSpannerSites()
            for spanner in spanners:
                spanner.replaceSpannedElement(placeHolder, unpitched)

        return unpitched

    @staticmethod
    def createChord(
        placeHolder: m21.Music21Object | None = None
    ) -> m21.chord.Chord:
        chord = m21.chord.Chord()

        # for debugging, override this chord's _reprInternal so we can see any Beams.
        setDebugReprInternal(chord, chordDebugReprInternal)

        # Now replace placeHolder with chord in every spanner that references it.
        # (This is for, e.g., slurs that were created before this chord was there.)
        if placeHolder:
            spanners = placeHolder.getSpannerSites()
            for spanner in spanners:
                spanner.replaceSpannedElement(placeHolder, chord)

        return chord

    @staticmethod
    def createRest(
        placeHolder: m21.Music21Object | None = None
    ) -> m21.note.Rest:
        rest = m21.note.Rest()

        # for debugging, override this rest's _reprInternal so we can see any Beams.
        setDebugReprInternal(rest, noteDebugReprInternal)

        # Now replace placeHolder with rest in every spanner that references it.
        # (This is for, e.g., slurs that were created before this rest was there.)
        if placeHolder:
            spanners = placeHolder.getSpannerSites()
            for spanner in spanners:
                spanner.replaceSpannedElement(placeHolder, rest)

        return rest

    @staticmethod
    def makeScoreFromObject(obj: m21.prebase.ProtoM21Object) -> m21.stream.Score:
        '''
        makeScoreFromObject (et al) are here to turn any ProtoM21Object into a well-formed
        Score/Part/Measure/whatever stream.  stream.makeNotation will also be called.  Clients
        can avoid this if they init with a Score, and set self.makeNotation to False before
        calling write().
        '''
        _classMapping: dict[str, str] = {
            'Score': '_fromScore',
            'Part': '_fromPart',
            'Measure': '_fromMeasure',
            'Voice': '_fromVoice',
            'Stream': '_fromStream',
            'GeneralNote': '_fromGeneralNote',
            'Pitch': '_fromPitch',
            'Duration': '_fromDuration',
            'Dynamic': '_fromDynamic',
            'DiatonicScale': '_fromDiatonicScale',
            'Scale': '_fromScale',
            'Music21Object': '_fromMusic21Object',
        }

        classes = obj.classes
        outScore: m21.stream.Score | None = None
        for cM, methName in _classMapping.items():
            if cM in classes:
                meth = getattr(M21Utilities, methName)
                outScore = meth(obj)
                break
        if outScore is None:
            raise CannotMakeScoreFromObjectError(
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

    @staticmethod
    def _fromPart(p: m21.stream.Part) -> m21.stream.Score:
        '''
        From a part, put it in a new, better notated score.
        '''
        if p.isFlat:
            p = p.makeMeasures()
        s = m21.stream.Score()
        s.insert(0, p)
        s.metadata = copy.deepcopy(M21Utilities._getMetadataFromContext(p))
        return M21Utilities._fromScore(s)

    @staticmethod
    def _getMetadataFromContext(s: m21.stream.Stream) -> m21.metadata.Metadata | None:
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

    @staticmethod
    def _fromMeasure(m: m21.stream.Measure) -> m21.stream.Score:
        '''
        From a measure, put it in a part, then in a new, better notated score
        '''
        mCopy = m.makeNotation()
        if not m.recurse().getElementsByClass('Clef').getElementsByOffset(0.0):
            mCopy.clef = m21.clef.bestClef(mCopy, recurse=True)
        p = m21.stream.Part()
        p.append(mCopy)
        p.metadata = copy.deepcopy(M21Utilities._getMetadataFromContext(m))
        return M21Utilities._fromPart(p)

    @staticmethod
    def _fromVoice(v: m21.stream.Voice) -> m21.stream.Score:
        '''
        From a voice, put it in a measure, then a part, then a score
        '''
        m = m21.stream.Measure(number=1)
        m.insert(0, v)
        return M21Utilities._fromMeasure(m)

    @staticmethod
    def _fromStream(st: m21.stream.Stream) -> m21.stream.Score:
        '''
        From a stream (that is not a voice, measure, part, or score), make an educated guess
        at it's structure, and do the appropriate thing to wrap it in a score.
        '''
        if st.isFlat:
            # if it's flat, treat it like a Part (which will make measures)
            part = m21.stream.Part()
            part.mergeAttributes(st)
            part.elements = copy.deepcopy(st)  # type: ignore
            if not st.getElementsByClass('Clef').getElementsByOffset(0.0):
                part.clef = m21.clef.bestClef(part)
            part.makeNotation(inPlace=True)
            part.metadata = copy.deepcopy(M21Utilities._getMetadataFromContext(st))
            return M21Utilities._fromPart(part)

        if st.hasPartLikeStreams():
            # if it has part-like streams, treat it like a Score
            score = m21.stream.Score()
            score.mergeAttributes(st)
            score.elements = copy.deepcopy(st)  # type: ignore
            score.makeNotation(inPlace=True)
            score.metadata = copy.deepcopy(M21Utilities._getMetadataFromContext(st))
            return M21Utilities._fromScore(score)

        firstSubStream = st.getElementsByClass('Stream').first()
        if firstSubStream is not None and firstSubStream.isFlat:
            # like a part w/ measures...
            part = m21.stream.Part()
            part.mergeAttributes(st)
            part.elements = copy.deepcopy(st)  # type: ignore
            bestClef = not st.getElementsByClass('Clef').getElementsByOffset(0.0)
            part.makeNotation(inPlace=True, bestClef=bestClef)
            part.metadata = copy.deepcopy(M21Utilities._getMetadataFromContext(st))
            return M21Utilities._fromPart(part)

        # probably a problem? or a voice...
        bestClef = not st.getElementsByClass('Clef').getElementsByOffset(0.0)
        st2 = st.makeNotation(inPlace=False, bestClef=bestClef)
        return M21Utilities._fromScore(st2)

    @staticmethod
    def _fromGeneralNote(n: m21.note.GeneralNote) -> m21.stream.Score:
        '''
        From a note/chord/rest, put it in a measure/part/score
        '''
        # Make a copy, as this process will change tuplet types.
        # This method is called infrequently, and only for display of a single
        # note
        nCopy = copy.deepcopy(n)

        out = m21.stream.Measure(number=1)
        out.append(nCopy)
        m21.stream.makeNotation.makeTupletBrackets(out, inPlace=True)
        return M21Utilities._fromMeasure(out)

    @staticmethod
    def _fromPitch(p: m21.pitch.Pitch) -> m21.stream.Score:
        '''
        From a pitch, put it in a note, then put that in a measure/part/score
        '''
        n = m21.note.Note()
        n.pitch = copy.deepcopy(p)
        out = m21.stream.Measure(number=1)
        out.append(n)
        return M21Utilities._fromMeasure(out)

    @staticmethod
    def _fromDuration(d: m21.duration.Duration) -> m21.stream.Score:
        '''
        Rarely rarely used.  Only if you call .show() on a duration object
        '''
        # Make a copy, as this process will change tuplet types.
        # Not needed, since fromGeneralNote does it too.  But so
        # rarely used, it doesn't matter, and the extra safety is nice.
        dCopy = copy.deepcopy(d)
        n = m21.note.Note()
        n.duration = dCopy
        return M21Utilities._fromGeneralNote(n)

    @staticmethod
    def _fromDynamic(dynamicObject: m21.dynamics.Dynamic) -> m21.stream.Score:
        '''
        Rarely rarely used.  Only if you call .show() on a dynamic object
        '''
        dCopy = copy.deepcopy(dynamicObject)
        out: m21.stream.Stream = m21.stream.Stream()
        out.append(dCopy)
        return M21Utilities._fromStream(out)

    @staticmethod
    def _fromDiatonicScale(diatonicScaleObject: m21.scale.DiatonicScale) -> m21.stream.Score:
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
        return M21Utilities._fromMeasure(m)

    @staticmethod
    def _fromScale(scaleObject: m21.scale.Scale) -> m21.stream.Score:
        '''
        Generate the pitches from this scale
        and put it into a stream.Measure, then call
        fromMeasure on it.
        '''
        if t.TYPE_CHECKING:
            assert isinstance(scaleObject, m21.scale.ConcreteScale)

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
        return M21Utilities._fromMeasure(m)

    @staticmethod
    def _fromMusic21Object(obj) -> m21.stream.Score:
        '''
        return things such as a single TimeSignature as a score
        '''
        objCopy = copy.deepcopy(obj)
        out = m21.stream.Measure(number=1)
        out.append(objCopy)
        return M21Utilities._fromMeasure(out)

    @staticmethod
    def getTextExpressionsFromGeneralNote(
            gnote: m21.note.GeneralNote
    ) -> list[m21.expressions.TextExpression]:
        output: list[m21.expressions.TextExpression] = []
        for exp in gnote.expressions:
            if isinstance(exp, m21.expressions.TextExpression):
                output.append(exp)

        return output

    # getAllExpressionsFromGeneralNote returns a list of expression gleaned from
    # both gnote.expressions as well as a few expression spanners the note might
    # be in.
    @staticmethod
    def getAllExpressionsFromGeneralNote(
            gnote: m21.note.GeneralNote,
            spannerBundle: m21.spanner.SpannerBundle
    ) -> list[m21.expressions.Expression | m21.spanner.Spanner]:
        expressions: list[m21.expressions.Expression | m21.spanner.Spanner] = []

        # start with the expression spanners (TrillExtension and TremoloSpanner)
        spanners: list[m21.spanner.Spanner] = gnote.getSpannerSites()
        for spanner in spanners:
            if spanner not in spannerBundle:
                continue
            if isinstance(spanner, m21.expressions.TrillExtension):
                expressions.append(spanner)
                continue
            if isinstance(spanner, m21.expressions.TremoloSpanner):
                expressions.append(spanner)
                continue
            if isinstance(spanner, m21.expressions.ArpeggioMarkSpanner):
                expressions.append(spanner)

        # finish up with gnote.expressions
        expressions += gnote.expressions
        return expressions

    @staticmethod
    def getDynamicWedgesStartedOrStoppedWithGeneralNote(
            gnote: m21.note.GeneralNote,
            spannerBundle: m21.spanner.SpannerBundle
    ) -> list[m21.dynamics.DynamicWedge]:
        output: list[m21.dynamics.DynamicWedge] = []
        spanners: list[m21.spanner.Spanner] = gnote.getSpannerSites('DynamicWedge')
        for spanner in spanners:
            if spanner not in spannerBundle:
                continue
            if not spanner.isFirst(gnote) and not spanner.isLast(gnote):
                # not started/stopped with general note, forget it
                continue
            if isinstance(spanner, m21.dynamics.DynamicWedge):
                output.append(spanner)
        return output

    @staticmethod
    def getDynamicWedgesStartedWithGeneralNote(
            gnote: m21.note.GeneralNote,
            spannerBundle: m21.spanner.SpannerBundle
    ) -> list[m21.dynamics.DynamicWedge]:
        output: list[m21.dynamics.DynamicWedge] = []
        spanners: list[m21.spanner.Spanner] = gnote.getSpannerSites('DynamicWedge')
        for spanner in spanners:
            if spanner not in spannerBundle:
                continue
            if not spanner.isFirst(gnote):  # not started with general note, forget it
                continue
            if isinstance(spanner, m21.dynamics.DynamicWedge):
                output.append(spanner)
        return output

    @staticmethod
    def hasMeterSymbol(timeSig: m21.meter.TimeSignature) -> bool:
        if timeSig.symbol in ('common', 'cut'):
            return True
        return False

    @staticmethod
    def isTransposingInstrument(inst: m21.instrument.Instrument) -> bool:
        trans: m21.interval.Interval | None = inst.transposition
        if trans is None:
            return False  # not a transposing instrument

        if (trans.semitones == 0 and trans.specifier == m21.interval.Specifier.PERFECT):
            return False  # instrument transposition is a no-op

        return True

    @staticmethod
    def isMultiStaffInstrument(inst: m21.instrument.Instrument | None) -> bool:
        if inst is None:
            return False

        # Weirdly, music21 doesn't derive Organ from KeyboardInstrument, go figure.  Check both.
        return isinstance(inst, (m21.instrument.KeyboardInstrument, m21.instrument.Organ))

    @staticmethod
    def makeDuration(
        base: OffsetQLIn = 0.0,
        dots: int = 0
    ) -> m21.duration.Duration:
        '''
        Given a base duration and a number of dots, create a :class:`~music21.duration.Duration`
        instance with the appropriate ``quarterLength`` value.

        Returns a :class:`Duration` corresponding to the fully-augmented value.

        **Examples**

        >>> from converter21 import M21Utilities
        >>> from fractions import Fraction
        >>> M21Utilities.makeDuration(base=2.0, dots=0).quarterLength  # half note, no dots
        2.0
        >>> M21Utilities.makeDuration(base=2.0, dots=1).quarterLength  # half note, one dot
        3.0
        >>> M21Utilities.makeDuration(base=2, dots=2).quarterLength  # 'base' can be an int or float
        3.5
        >>> M21Utilities.makeDuration(2.0, 10).quarterLength  # crazy dots
        3.998046875
        >>> M21Utilities.makeDuration(0.33333333333333333333, 0).quarterLength  # fractions too
        Fraction(1, 3)
        >>> M21Utilities.makeDuration(Fraction(1, 3), 1).quarterLength
        0.5
        '''
        output: m21.duration.Duration = m21.duration.Duration(base)
        output.dots = dots
        return output

    @staticmethod
    def splitComplexRestDurations(s: m21.stream.Stream) -> None:
        # only handles rests that are in s directly (does not recurse)
        # always in-place, never adds ties (because they're rests)
        # loses all beams, so we can only do this on rests!
        rest: m21.note.Rest
        for rest in s.getElementsByClass('Rest'):
            if rest.duration.type != 'complex':
                continue
            insertPoint = rest.offset
            restList: tuple[m21.note.Rest, ...] = M21Utilities.splitComplexRestDuration(rest)
            s.replace(rest, restList[0])
            insertPoint += restList[0].quarterLength
            for subsequent in restList[1:]:
                s.insert(insertPoint, subsequent)
                insertPoint += subsequent.quarterLength

            # Replace elements in spanners
            for sp in rest.getSpannerSites():
                if sp.getFirst() is rest:
                    sp.replaceSpannedElement(rest, restList[0])
                if sp.getLast() is rest:
                    sp.replaceSpannedElement(rest, restList[-1])

    @staticmethod
    def splitComplexRestDuration(rest: m21.note.Rest) -> tuple[m21.note.Rest, ...]:
        atm: OffsetQL = rest.duration.aggregateTupletMultiplier()
        quarterLengthList: list[OffsetQLIn] = [
            float(c.quarterLength * atm) for c in rest.duration.components
        ]
        splits: tuple[m21.note.Rest, ...] = (
            rest.splitByQuarterLengths(quarterLengthList, addTies=False)  # type: ignore
        )

        return splits

    @staticmethod
    def splitM21PitchNameIntoNameAccidOctave(m21PitchName: str) -> tuple[str, str, str]:
        patt: str = r'([ABCDEFG])([-#]*)([\d]+)'
        m = re.match(patt, m21PitchName)
        if m:
            g2: str = m.group(2)
            if g2 == '':
                g2 = 'n'
            return m.group(1), g2, m.group(3)
        return m21PitchName, 'n', ''

    _STEP_TO_PITCH_CLASS: dict[str, int] = {
        'C': 0,
        'D': 1,
        'E': 2,
        'F': 3,
        'G': 4,
        'A': 5,
        'B': 6
    }

    _PITCH_CLASS_TO_STEP: dict[int, str] = {
        0: 'C',
        1: 'D',
        2: 'E',
        3: 'F',
        4: 'G',
        5: 'A',
        6: 'B'
    }

    @staticmethod
    def pitchToBase7(m21Pitch: m21.pitch.Pitch) -> int:
        pc: int = M21Utilities._STEP_TO_PITCH_CLASS[m21Pitch.step]
        octave: int = m21Pitch.implicitOctave  # implicit means return default (4) if None
        return pc + (7 * octave)

    @staticmethod
    def base7ToDisplayName(base7: int) -> str:
        pc: int = base7 % 7
        octave: int = base7 // 7
        name: str = M21Utilities._PITCH_CLASS_TO_STEP[pc]
        name += str(octave)
        return name

    @staticmethod
    def safePitch(
        name: str,
        accidental: m21.pitch.Accidental | str | None = None,
        octave: str | int = ''
    ) -> m21.pitch.Pitch:
        '''
        Safely build a :class:`~music21.pitch.Pitch` from a string.

        When :meth:`~music21.pitch.Pitch.__init__` is given an empty string,
        it raises a :exc:`~music21.pitch.PitchException`. This
        function instead returns a default :class:`~music21.pitch.Pitch` instance.

        name: Desired name of the :class:`~music21.pitch.Pitch`.

        accidental: (Optional) Symbol for the accidental.

        octave: (Optional) Octave number.

        Returns A :class:`~music21.pitch.Pitch` with the appropriate properties.

        >>> from converter21.shared import M21Utilities
        >>> M21Utilities.safePitch('D#6')
        <music21.pitch.Pitch D#6>
        >>> M21Utilities.safePitch('D', '#', '6')
        <music21.pitch.Pitch D#6>
        >>> M21Utilities.safePitch('D', '#', 6)
        <music21.pitch.Pitch D#6>
        >>> M21Utilities.safePitch('D', '#')
        <music21.pitch.Pitch D#>
        '''
        if not name:
            return m21.pitch.Pitch()
        if (octave or octave == 0) and accidental is not None:
            return m21.pitch.Pitch(name, octave=int(octave), accidental=accidental)
        if octave or octave == 0:
            return m21.pitch.Pitch(name, octave=int(octave))
        if accidental is not None:
            return m21.pitch.Pitch(name, accidental=accidental)
        return m21.pitch.Pitch(name)

    @staticmethod
    def getAltersForKey(
        m21Key: m21.key.Key | m21.key.KeySignature | None
    ) -> list[int]:
        # returns a list of pitch alterations (number of semitones up or down),
        # indexed by pitch (base7), where index 0 is C0, and index 69 is B9.
        alters: list[int] = [0] * 70
        if m21Key is None:
            return alters

        STEPNAMES: tuple[StepName, ...] = ('C', 'D', 'E', 'F', 'G', 'A', 'B')
        for pitchClass, pitchName in enumerate(STEPNAMES):
            accid: m21.pitch.Accidental | None = m21Key.accidentalByStep(pitchName)
            if accid is None:
                continue
            alter: int = int(accid.alter)
            for octave in range(0, 10):  # 0 through 9, inclusive
                alters[pitchClass + (octave * 7)] = alter

        return alters

    @staticmethod
    def safeGetOffsetInHierarchy(
        obj: m21.base.Music21Object,
        stream: m21.stream.Stream
    ) -> OffsetQL | None:
        try:
            return obj.getOffsetInHierarchy(stream)
        except m21.sites.SitesException:
            return None

    @staticmethod
    def objectIsInHierarchy(
        obj: m21.base.Music21Object,
        stream: m21.stream.Stream
    ) -> bool:
        offset = M21Utilities.safeGetOffsetInHierarchy(obj, stream)
        if offset is None:
            return False
        return True

    @staticmethod
    def allSpannedElementsAreInHierarchy(
        spanner: m21.spanner.Spanner,
        stream: m21.stream.Stream
    ) -> bool:
        for obj in spanner.getSpannedElements():
            if not M21Utilities.objectIsInHierarchy(obj, stream):
                return False
        return True

    @staticmethod
    def getActiveTimeSigFromMeterStream(
        offset: OffsetQL,
        meterStream: m21.stream.Stream[m21.meter.TimeSignature]
    ) -> m21.meter.TimeSignature | None:
        timeSig: m21.base.Music21Object | None = (
            meterStream.getElementAtOrBefore(opFrac(offset))
        )
        if t.TYPE_CHECKING:
            assert timeSig is None or isinstance(timeSig, (m21.meter.TimeSignature))
        return timeSig

    @staticmethod
    def m21VersionIsAtLeast(neededVersion: tuple[int, int, int, str]) -> bool:
        if len(m21.VERSION) == 0:
            raise NoMusic21VersionError('music21 version must be set!')

        try:
            # compare element 0
            if int(m21.VERSION[0]) < neededVersion[0]:
                return False
            if int(m21.VERSION[0]) > neededVersion[0]:
                return True

            # element 0 is equal... go on to next element
            if len(m21.VERSION) == 1 or len(neededVersion) == 1:
                # there is no next element to compare, so we are done.
                # result is True only if m21 version has >= elements of needed version.
                # if neededVersion has more elements, then result is False
                return len(m21.VERSION) >= len(neededVersion)

            # compare element 1
            if int(m21.VERSION[1]) < neededVersion[1]:
                return False
            if int(m21.VERSION[1]) > neededVersion[1]:
                return True

            # element 1 is equal... go on to next element
            if len(m21.VERSION) == 2 or len(neededVersion) == 2:
                # there is no next element to compare, so we are done.
                # result is True only if m21 version has >= elements of needed version.
                # if neededVersion has more elements, then result is False
                return len(m21.VERSION) >= len(neededVersion)

            # compare element 2
            if int(m21.VERSION[2]) < neededVersion[2]:
                return False
            if int(m21.VERSION[2]) > neededVersion[2]:
                return True

            # element 2 is equal... go on to next element
            if len(m21.VERSION) == 3 or len(neededVersion) == 3:
                # there is no next element to compare, so we are done.
                # result is True only if m21 version has >= elements of needed version.
                # if neededVersion has more elements, then result is False
                return len(m21.VERSION) >= len(neededVersion)

            # compare element 3 (probably a string)
            if m21.VERSION[3] < neededVersion[3]:
                return False
            if m21.VERSION[3] > neededVersion[3]:
                return True

            return True  # four elements equal, that's all we care about
        except Exception:
            return False

        return False

    @staticmethod
    def getStaffGroupTrees(
        staffGroups: list[m21.layout.StaffGroup],
        staffNumbersByM21Part: dict[m21.stream.Part, int]
    ) -> list[M21StaffGroupTree]:
        topLevelParents: list[M21StaffGroupTree] = []

        # Start with the tree being completely flat. Sort it by number of staves, so
        # we can bail early when searching for smallest parent, since the first one
        # we find will be the smallest.
        staffGroupTrees: list[M21StaffGroupTree] = [
            M21StaffGroupTree(sg, staffNumbersByM21Part) for sg in staffGroups
        ]
        staffGroupTrees.sort(key=lambda tree: tree.numStaves)

        # Hook up each child node to the parent with the smallest superset of the child's staves.
        # If there is no parent with a superset of the child's staves at all, the child is actually
        # a top level parent.
        for child in staffGroupTrees:
            smallestParent: M21StaffGroupTree | None = None
            for parent in staffGroupTrees:
                if parent is child or parent in child.children:
                    continue

                if child.staffNums.issubset(parent.staffNums):
                    smallestParent = parent
                    # we know it's smallest because they're sorted by size
                    break

            if smallestParent is None:
                topLevelParents.append(child)
            else:
                smallestParent.children.append(child)

        # Sort every list of siblings in the tree (including the
        # topLevelParents themselves) by lowest staff number, so
        # the staff numbers are in order.
        M21Utilities._sortStaffGroupTrees(topLevelParents)

        return topLevelParents

    @staticmethod
    def _sortStaffGroupTrees(trees: list[M21StaffGroupTree]) -> None:
        # Sort every list of siblings in the tree (including the
        # passed-in trees list itself) by lowest staff number.
        if not trees:
            return

        trees.sort(key=lambda tree: tree.lowestStaffNumber)
        for tree in trees:
            M21Utilities._sortStaffGroupTrees(tree.children)
