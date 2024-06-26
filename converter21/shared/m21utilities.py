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
import typing as t
from fractions import Fraction
from copy import copy, deepcopy

import music21 as m21
from music21.common.types import OffsetQL, OffsetQLIn, StepName
from music21.common.numberTools import opFrac
from music21.figuredBass import realizerScale

from converter21.shared import SharedConstants

class CannotMakeScoreFromObjectError(Exception):
    pass


class NoMusic21VersionError(Exception):
    pass


class Converter21InternalError(Exception):
    pass


MAX_INT: int = 9223372036854775807
MAX_OFFSETQL: OffsetQL = opFrac(MAX_INT)

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
        s.metadata = deepcopy(M21Utilities._getMetadataFromContext(p))
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
        p.metadata = deepcopy(M21Utilities._getMetadataFromContext(m))
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
            part.elements = deepcopy(st)  # type: ignore
            if not st.getElementsByClass('Clef').getElementsByOffset(0.0):
                part.clef = m21.clef.bestClef(part)
            part.makeNotation(inPlace=True)
            part.metadata = deepcopy(M21Utilities._getMetadataFromContext(st))
            return M21Utilities._fromPart(part)

        if st.hasPartLikeStreams():
            # if it has part-like streams, treat it like a Score
            score = m21.stream.Score()
            score.mergeAttributes(st)
            score.elements = deepcopy(st)  # type: ignore
            score.makeNotation(inPlace=True)
            score.metadata = deepcopy(M21Utilities._getMetadataFromContext(st))
            return M21Utilities._fromScore(score)

        firstSubStream = st.getElementsByClass('Stream').first()
        if firstSubStream is not None and firstSubStream.isFlat:
            # like a part w/ measures...
            part = m21.stream.Part()
            part.mergeAttributes(st)
            part.elements = deepcopy(st)  # type: ignore
            bestClef = not st.getElementsByClass('Clef').getElementsByOffset(0.0)
            part.makeNotation(inPlace=True, bestClef=bestClef)
            part.metadata = deepcopy(M21Utilities._getMetadataFromContext(st))
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
        nCopy = deepcopy(n)

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
        n.pitch = deepcopy(p)
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
        dCopy = deepcopy(d)
        n = m21.note.Note()
        n.duration = dCopy
        return M21Utilities._fromGeneralNote(n)

    @staticmethod
    def _fromDynamic(dynamicObject: m21.dynamics.Dynamic) -> m21.stream.Score:
        '''
        Rarely rarely used.  Only if you call .show() on a dynamic object
        '''
        dCopy = deepcopy(dynamicObject)
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
        objCopy = deepcopy(obj)
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
    def adjustSpannerOrder(sp: m21.spanner.Spanner, s: m21.stream.Stream):
        # the adjustment is that we move the element with the smallest offsetInHierarchy(s)
        # to the beginning of the list, and the element with the largest highestTime
        # (offsetInHierarchy(s) + el.quarterLength) to the end of the list.
        firstEl: m21.Music21Object | None = sp.getFirst()
        lastEl: m21.Music21Object | None = sp.getLast()
        lowestEl: m21.Music21Object | None = firstEl
        highestEl: m21.Music21Object | None = lastEl
        if lowestEl is None and highestEl is None:
            # zero elements, no adjustment necessary
            return
        if lowestEl is highestEl:
            # one element, no adjustment necessary
            return

        highestEndTime: OffsetQL = -1.
        lowestStartTime: OffsetQL = MAX_OFFSETQL
        for el in sp:
            endTime: OffsetQL = -1.  # not 0., since grace notes might have endTime == 0.
            startTime: OffsetQL = MAX_OFFSETQL
            try:
                startTime = el.getOffsetInHierarchy(s)
                endTime = startTime + el.quarterLength
            except Exception:
                # el not in s, we'll have to ignore it; keep going
                continue

            if endTime >= highestEndTime:
                # >= so we get the last element that has that highestEndTime
                highestEndTime = endTime
                highestEl = el
            if startTime < lowestStartTime:
                # < (not <=) so we get the first element that has that lowestStartTime
                lowestStartTime = startTime
                lowestEl = el

        if lowestEl is not None and lowestEl is not firstEl:
            # get them all
            elements: list[m21.Music21Object] = sp.getSpannedElements()
            # remove them all
            for el in elements:
                sp.spannerStorage.remove(el)

            # add them back, lowestEl first
            sp.addSpannedElements(lowestEl)
            sp.addSpannedElements(elements)  # lowestEl will be skipped because already there

        if highestEl is not None:
            # make sure it is last
            sp.spannerStorage.remove(highestEl)
            sp.addSpannedElements(highestEl)

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
        if not output.dots:
            # ignore dots if base ql was already requiring some dots
            output.dots = dots
        return output

    @staticmethod
    def isPowerOfTwo(num: OffsetQLIn) -> bool:
        numFraction: Fraction = Fraction(num)
        if numFraction.numerator == 0:
            return False
        absNumer: int = abs(numFraction.numerator)
        if numFraction.denominator == 1:
            return (absNumer & (absNumer - 1)) == 0
        if absNumer == 1:
            return (numFraction.denominator & (numFraction.denominator - 1)) == 0
        return False

    @staticmethod
    def isPowerOfTwoWithDots(quarterLength: OffsetQLIn) -> bool:
        ql: OffsetQL = opFrac(quarterLength)
        if M21Utilities.isPowerOfTwo(ql):
            # power of two + no dots
            return True
        if M21Utilities.isPowerOfTwo(ql * opFrac(Fraction(2, 3))):
            # power of two + 1 dot
            return True
        if M21Utilities.isPowerOfTwo(ql * opFrac(Fraction(4, 7))):
            # power of two + 2 dots
            return True
        if M21Utilities.isPowerOfTwo(ql * opFrac(Fraction(8, 15))):
            # power of two + 3 dots
            return True
        return False

    @staticmethod
    def computeDurationNoDotsAndNumDots(durWithDots: OffsetQLIn) -> tuple[OffsetQL, int | None]:
        dd: OffsetQL = opFrac(durWithDots)
        attemptedPowerOfTwo: OffsetQL = dd
        if M21Utilities.isPowerOfTwo(attemptedPowerOfTwo):
            # power of two + no dots
            return (attemptedPowerOfTwo, 0)

        attemptedPowerOfTwo = dd * opFrac(Fraction(2, 3))
        if M21Utilities.isPowerOfTwo(attemptedPowerOfTwo):
            # power of two + 1 dot
            return (attemptedPowerOfTwo, 1)

        attemptedPowerOfTwo = dd * opFrac(Fraction(4, 7))
        if M21Utilities.isPowerOfTwo(attemptedPowerOfTwo):
            # power of two + 2 dots
            return (attemptedPowerOfTwo, 2)

        attemptedPowerOfTwo = dd * opFrac(Fraction(8, 15))
        if M21Utilities.isPowerOfTwo(attemptedPowerOfTwo):
            # power of two + 3 dots
            return (attemptedPowerOfTwo, 3)

        # None signals that we couldn't actually find a power-of-two duration
        return (dd, None)

    @staticmethod
    def getPowerOfTwoQuarterLengthsWithDotsAddingTo(
        quarterLength: OffsetQLIn,
    ) -> list[OffsetQL]:
        output: list[OffsetQL] = []
        ql: OffsetQL = opFrac(quarterLength)

        if M21Utilities.isPowerOfTwoWithDots(ql):
            # power of two + maybe some dots
            output.append(ql)
            return output

        powerOfTwoQLAttempt: OffsetQL = opFrac(4)  # start with whole note
        smallest: OffsetQL = opFrac(Fraction(1, 2048))
        while powerOfTwoQLAttempt >= smallest:
            if ql >= powerOfTwoQLAttempt:
                output.append(powerOfTwoQLAttempt)
                ql = opFrac(ql - powerOfTwoQLAttempt)
            else:
                powerOfTwoQLAttempt = opFrac(powerOfTwoQLAttempt / 2)

            if M21Utilities.isPowerOfTwoWithDots(ql):
                # power of two + maybe some dots
                output.append(ql)
                return output

        # we couldn't compute a full list so just return the original param
        return [opFrac(quarterLength)]

    @staticmethod
    def getPowerOfTwoDurationsWithDotsAddingTo(
        quarterLength: OffsetQLIn,
    ) -> list[m21.duration.Duration]:
        # Unlike getPowerOfTwoQuarterLengthsWithDotsAddingTo, this one returns
        # an empty list when it cannot do the job.
        qlList: list[OffsetQL] = (
            M21Utilities.getPowerOfTwoQuarterLengthsWithDotsAddingTo(quarterLength)
        )
        if len(qlList) == 1 and not M21Utilities.isPowerOfTwoWithDots(qlList[0]):
            return []
        return [m21.duration.Duration(ql) for ql in qlList]

    @staticmethod
    def getPowerOfTwoDurationsWithDotsAddingToAndCrossing(
        totalDuration: OffsetQLIn,
        crossing: OffsetQLIn,
    ) -> tuple[list[m21.duration.Duration], list[m21.duration.Duration]]:
        output1: list[m21.duration.Duration] = []
        output2: list[m21.duration.Duration] = []
        totalDuration = opFrac(totalDuration)
        crossing = opFrac(crossing)
        secondDur: OffsetQL = opFrac(totalDuration - crossing)
        needTuplet: bool = False

        if crossing == 0:
            output1 = []
        elif M21Utilities.isPowerOfTwoWithDots(crossing):
            output1 = [m21.duration.Duration(crossing)]
        else:
            output1 = M21Utilities.getPowerOfTwoDurationsWithDotsAddingTo(crossing)
            if not output1:
                # problem: we'll need a tuplet to get to crossing
                needTuplet = True

        if not needTuplet:
            if secondDur == 0:
                output2 = []
            elif M21Utilities.isPowerOfTwoWithDots(secondDur):
                output2 = [m21.duration.Duration(secondDur)]
            else:
                output2 = M21Utilities.getPowerOfTwoDurationsWithDotsAddingTo(secondDur)
                if not output2:
                    # problem: we'll need a tuplet to get from crossing to totalDuration
                    output1 = []
                    needTuplet = True

        if not needTuplet:
            return (output1, output2)

        # we need a tuplet for some reason

        # Easiest case: totalDuration is powerOfTwoWithDots (only crossing is tuplet-y)
        if M21Utilities.isPowerOfTwoWithDots(totalDuration):
            crossingFrac: Fraction = Fraction(crossing)
            qLen: OffsetQL = opFrac(Fraction(1, crossingFrac.denominator))
            tuplets: list[m21.duration.Tuplet] = m21.duration.quarterLengthToTuplet(
                qLen,
                maxToReturn=1)
            if not tuplets:
                raise Converter21InternalError('Cannot compute crossing tuplet')

            # Figure out similar tuplet that covers all of totalDuration
            tupletElementQL: OffsetQL = totalDuration
            while M21Utilities.isPowerOfTwoWithDots(tupletElementQL):
                tupletElementQL = tupletElementQL / float(tuplets[0].numberNotesActual)

            tuplets = m21.duration.quarterLengthToTuplet(
                tupletElementQL
            )
            if not tuplets:
                raise Converter21InternalError('Cannot compute totalDuration tuplet')

            tuplet: m21.duration.Tuplet = deepcopy(tuplets[0])
            tuplet.numberNotesActual = int(totalDuration / tupletElementQL)
            tuplet.numberNotesNormal = int(
                tuplet.numberNotesActual * tuplets[0].tupletMultiplier()
            )
            tupletStart: m21.duration.Tuplet = deepcopy(tuplet)
            tupletStart.type = 'start'
            tupletStop: m21.duration.Tuplet = deepcopy(tuplet)
            tupletStop.type = 'stop'


            tupletMultiplier: OffsetQL = tuplets[0].tupletMultiplier()
            output1, output2 = M21Utilities.getPowerOfTwoDurationsWithDotsAddingToAndCrossing(
                opFrac(totalDuration / tupletMultiplier),
                opFrac(crossing / tupletMultiplier)
            )

            for i, dur in enumerate(output1 + output2):
                if i == 0:
                    dur.tuplets = (tupletStart,)
                elif i == len(output1 + output2) - 1:
                    dur.tuplets = (tupletStop,)
                else:
                    dur.tuplets = (tuplet,)

            return output1, output2

        # case 2: totalDuration is representable by a list of powerOfTwoWithDots durations
        # (only crossing is tuplet-y).
        totalDurs: list[m21.duration.Duration] = (
            M21Utilities.getPowerOfTwoDurationsWithDotsAddingTo(totalDuration)
        )
        if totalDurs:
            # Figure out which element of totalDurs contains the crossing point,
            # recurse on that element (as totalDuration), and then construct
            # the output lists from all of the computed lists.
            newTotalQL: OffsetQL = 0.
            newCrossing: OffsetQL = 0.
            foundIdx: int = -1
            curOffset: OffsetQL = 0.
            for i, partialDur in enumerate(totalDurs):
                partialQL: OffsetQL = partialDur.quarterLength
                nextOffset: OffsetQL = opFrac(curOffset + partialQL)
                if curOffset <= crossing < nextOffset:
                    newTotalQL = partialQL
                    newCrossing = opFrac(crossing - curOffset)
                    foundIdx = i
                    break
                curOffset = nextOffset

            if foundIdx == -1:
                raise Converter21InternalError('Could not find crossing in totalDuration')

            beforeCrossing: list[m21.duration.Duration]
            afterCrossing: list[m21.duration.Duration]
            beforeCrossing, afterCrossing = (
                M21Utilities.getPowerOfTwoDurationsWithDotsAddingToAndCrossing(
                    newTotalQL,
                    newCrossing
                )
            )

            # Construct new lists:
            # 1. pre-foundIdx durations
            # 2. foundIdx became beforeCrossing and afterCrossing
            # 3. post-foundIdx durations
            # So...
            # output1 = pre-foundIdx durations + beforeCrossing
            # output2 = afterCrossing + post-foundIdx durations
            if foundIdx == 0:
                output1 = beforeCrossing
            else:
                output1 = totalDurs[:foundIdx - 1] + beforeCrossing
            if foundIdx == len(totalDurs) - 1:
                output2 = afterCrossing
            else:
                output2 = afterCrossing + totalDurs[foundIdx + 1:]
            return output1, output2

        # case 3: totalDuration is itself tuplet-y (e.g. 10/3).
        raise Converter21InternalError(
            'totalDuration must representable by a list of powerOfTwoWithDots durations.'
        )

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
    def getSpannerQuarterLength(
        spanner: m21.spanner.Spanner,
        hierarchy: m21.stream.Stream
    ) -> OffsetQL:
        first = spanner.getFirst()
        last = spanner.getLast()
        start: OffsetQL = first.getOffsetInHierarchy(hierarchy)
        end: OffsetQL = last.getOffsetInHierarchy(hierarchy)
        end += last.duration.quarterLength
        return opFrac(end - start)

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
        for i, child in enumerate(staffGroupTrees):
            smallestParent: M21StaffGroupTree | None = None
            for parent in staffGroupTrees:
                if parent is child or parent in child.children:
                    continue

                if i < len(staffGroupTrees) - 1:
                    if child.staffNums.issubset(parent.staffNums):
                        smallestParent = parent
                        # we know it's smallest because they're sorted by size
                        break
                else:
                    # last child; if there are no top-level parents yet, this guy is it, so
                    # don't bother looking for smallest parent (this fixes a bug where there
                    # are multiple possible top-level parents, all with the same staves in
                    # them, and none of them end up at the top, because they are all subsets
                    # of eachother).
                    if topLevelParents:
                        if child.staffNums.issubset(parent.staffNums):
                            smallestParent = parent
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

    @staticmethod
    def m21DatePrimitiveFromIsoDate(
        isodate: str
    ) -> m21.metadata.DatePrimitive | None:
        def removeSplitChars(isodate: str) -> str:
            for ch in ['{', '}', '[', ']']:
                isodate = isodate.strip(ch)
            return isodate

        def splitIsoDateList(isodate: str) -> list[str]:
            isodate = removeSplitChars(isodate)
            return isodate.split(',')

        def splitIsoDateRangeSelection(isodate: str) -> list[str]:
            isodate = removeSplitChars(isodate)
            return isodate.split('..')

        if not isodate:
            return None

        # if it looks like a non-iso-date (contains more than one '/') give up
        if isodate.count('/') > 1:
            return None

        if isodate[0] in ('{', '['):
            if isodate[0] == '[' and '..' in isodate:
                # it's a selection that is a range.  We can represent this as a DateBetween.
                m21Dates: list[m21.metadata.Date] = (
                    M21Utilities.m21DateListFromIsoDateList(splitIsoDateRangeSelection(isodate))
                )
                return m21.metadata.DateBetween(m21Dates)

            # list (DateSelection)
            relevance: str = 'and' if isodate[0] == '{' else 'or'
            m21Dates = M21Utilities.m21DateListFromIsoDateList(splitIsoDateList(isodate))
            return m21.metadata.DateSelection(m21Dates, relevance=relevance)

        if '/' in isodate:
            if '..' not in isodate:
                # regular range (DateBetween)
                m21Dates = M21Utilities.m21DateListFromIsoDateList(isodate.split('/'))
                return m21.metadata.DateBetween(m21Dates[:2])

            # open ended range (DateRelative)
            if isodate.startswith('../'):
                isodate = isodate[3:]
                relevance = 'prior'
            elif isodate.endswith('/..'):
                isodate = isodate[:-3]
                relevance = 'after'
            else:
                return None

            if '/' in isodate:
                # should not be any '/' once we remove '../' or '/..'
                return None

            m21Date: m21.metadata.Date | None = M21Utilities.m21DateFromIsoDate(isodate)
            if m21Date is None:
                return None

            return m21.metadata.DateRelative(m21Date, relevance=relevance)

        # single date (DateSingle)
        singleError: str = ''
        if isodate[-1] == '~':
            isodate = isodate[:-1]
            singleError = 'approximate'
        elif isodate[-1] == '?':
            isodate = isodate[:-1]
            singleError = 'uncertain'

        m21Date = M21Utilities.m21DateFromIsoDate(isodate)
        if m21Date is None:
            return None

        output: m21.metadata.DateSingle = m21.metadata.DateSingle(m21Date)
        if singleError:
            output.relevance = singleError

        return output

    @staticmethod
    def m21DateListFromIsoDateList(
        isodates: list[str]
    ) -> list[m21.metadata.Date]:
        m21Dates: list[m21.metadata.Date] = []
        for isodate in isodates:
            m21Date: m21.metadata.Date | None = M21Utilities.m21DateFromIsoDate(isodate)
            if m21Date is not None:
                m21Dates.append(m21Date)
        return m21Dates

    @staticmethod
    def m21DateFromIsoDate(
        isodate: str
    ) -> m21.metadata.Date | None:
        # Requires the isodate to contain a single date and/or time, no ranges
        # or lists of dates/times.
        if not isodate:
            return None
        if '/' in isodate:
            return None
        if isodate[0] in ('{', '['):
            return None

        # parse the single isodate into a Date
        date: str = ''
        time: str = ''

        if 'T' in isodate:
            pieces: list[str] = isodate.split('T')
            if len(pieces) != 2:
                return None
            date = pieces[0]
            time = pieces[1]
        else:
            if '-' not in isodate and ':' not in isodate:
                date = isodate
            elif '-' in isodate and ':' not in isodate:
                date = isodate
            elif '-' not in isodate and ':' in isodate:
                time = isodate
            else:
                return None

        # we have date and/or time
        year: str | None = None
        month: str | None = None
        day: str | None = None
        hour: str | None = None
        minute: str | None = None
        second: str | None = None
        if date:
            datePieces: list[str] = date.split('-')
            year = datePieces[0]
            if len(datePieces) > 1:
                month = datePieces[1]
            if len(datePieces) > 2:
                day = datePieces[2]

        if time:
            timePieces: list[str] = time.split(':')
            if len(timePieces) >= 3:
                hour = timePieces[0]
                minute = timePieces[1]
                second = timePieces[2]

        try:
            return m21.metadata.Date(
                year=year,
                month=month,
                day=day,
                hour=hour,
                minute=minute,
                second=second
            )
        except Exception:
            pass

        return None

    @staticmethod
    def edtfNestedDateRangeFromString(string: str) -> dict[str, str]:
        dateStrings: list[str] = string.split('-')
        if len(dateStrings) != 2:
            return {}

        startDateStr: str = dateStrings[0]
        endDateStr: str = dateStrings[1]
        doStart: m21.metadata.DatePrimitive | None = (
            M21Utilities.m21DatePrimitiveFromString(startDateStr)
        )
        doEnd: m21.metadata.DatePrimitive | None = (
            M21Utilities.m21DatePrimitiveFromString(endDateStr)
        )
        if doStart is None or doEnd is None:
            return {}

        singleError: str = (
            doStart.relevance if isinstance(doStart, m21.metadata.DateSingle) else ''
        )
        output: dict[str, str] = {}
        startIsoDates: list[str] = []
        for date in doStart._data:
            iso: str = M21Utilities.isoDateFromM21Date(date, edtf=True)
            if not iso:
                return {}

            if singleError == 'approximate':
                iso = iso + '~'
            elif singleError == 'uncertain':
                iso = iso + '?'

            startIsoDates.append(iso)

        if isinstance(doStart, m21.metadata.DateSingle):
            output['startedtf'] = startIsoDates[0]
        elif isinstance(doStart, m21.metadata.DateRelative):
            if doStart.relevance in ('prior', 'onorbefore'):
                output['startedtf'] = '../' + startIsoDates[0]
            elif doStart.relevance in ('after', 'onorafter'):
                output['startedtf'] = startIsoDates[0] + '/..'
        elif isinstance(doStart, m21.metadata.DateBetween):
            # DateBetween for the beginning of a DatePrimitive range is actually a
            # selection within a range: [date1..date2], not a full range: date1/date2.
            output['startedtf'] = '[' + startIsoDates[0] + '..' + startIsoDates[1] + ']'
        elif isinstance(doStart, m21.metadata.DateSelection):
            if doStart.relevance == 'and':
                output['startedtf'] = '{' + ','.join(startIsoDates) + '}'
            else:
                output['startedtf'] = '[' + ','.join(startIsoDates) + ']'

        singleError = doEnd.relevance if isinstance(doEnd, m21.metadata.DateSingle) else ''
        endIsoDates: list[str] = []
        for date in doEnd._data:
            iso = M21Utilities.isoDateFromM21Date(date, edtf=True)
            if not iso:
                return {}

            if singleError == 'approximate':
                iso = iso + '~'
            elif singleError == 'uncertain':
                iso = iso + '?'

            endIsoDates.append(iso)

        if isinstance(doEnd, m21.metadata.DateSingle):
            output['endedtf'] = endIsoDates[0]
        elif isinstance(doEnd, m21.metadata.DateRelative):
            if doEnd.relevance in ('prior', 'onorbefore'):
                output['endedtf'] = '../' + endIsoDates[0]
            elif doEnd.relevance in ('after', 'onorafter'):
                output['endedtf'] = endIsoDates[0] + '/..'
        elif isinstance(doEnd, m21.metadata.DateBetween):
            # DateBetween for the ending of a DatePrimitive range is actually a
            # selection within a range: [date1..date2], not a full range: date1/date2.
            output['endedtf'] = '[' + endIsoDates[0] + '..' + endIsoDates[1] + ']'
        elif isinstance(doEnd, m21.metadata.DateSelection):
            if doEnd.relevance == 'and':
                output['endedtf'] = '{' + ','.join(endIsoDates) + '}'
            else:
                output['endedtf'] = '[' + ','.join(endIsoDates) + ']'

        return output

    @staticmethod
    def isoDateFromM21DatePrimitive(
        dateObj: m21.metadata.DatePrimitive | m21.metadata.Text,
        edtf: bool = False
    ) -> dict[str, str]:
        if isinstance(dateObj, m21.metadata.Text):
            # convert to DatePrimitive
            do: m21.metadata.DatePrimitive | None = (
                M21Utilities.m21DatePrimitiveFromString(str(dateObj))
            )
            if do is None:
                if edtf:
                    # take one final shot: it might be a "nested" humdrum date range,
                    # e.g. 1525^1526-1594 (which means a range from (1525 or 1526) to 1594)
                    # This is not representable in music21 (except as Text), but can be
                    # represented in two edtf dates (birth and death, for example,
                    # where birth is '1525/1526' and death is '1594').
                    # So, here we try to return two edtf dates: 'startedtf': '1525/1526'
                    # and 'endedtf': '1594'.  If this is a composer birth/death date
                    # date going into MADS <birthDate> and <deathDate> elements, that
                    # code will need to tease this apart and make those two elements
                    # of it.
                    return M21Utilities.edtfNestedDateRangeFromString(str(dateObj))
                return {}

            dateObj = do

        if dateObj.relevance in ('uncertain', 'approximate'):
            if not edtf:
                # pre-EDTF isodates can't represent uncertain/approximate dates,
                # so don't return one.  The plain text will still describe it,
                # and should be parseable by most folks.
                return {}

        isodates: list[str] = []
        for date in dateObj._data:
            iso: str = M21Utilities.isoDateFromM21Date(date, edtf)
            if not iso:
                return {}
            isodates.append(iso)

        if isinstance(dateObj, m21.metadata.DateSingle):
            if edtf:
                return {'edtf': isodates[0]}
            return {'isodate': isodates[0]}
        elif isinstance(dateObj, m21.metadata.DateRelative):
            if dateObj.relevance in ('prior', 'onorbefore'):
                if edtf:
                    return {'edtf': '../' + isodates[0]}
                return {'notafter': isodates[0]}
            elif dateObj.relevance in ('after', 'onorafter'):
                if edtf:
                    return {'edtf': isodates[0] + '/..'}
                return {'notbefore': isodates[0]}
        elif isinstance(dateObj, m21.metadata.DateBetween):
            if edtf:
                return {'edtf': isodates[0] + '/' + isodates[1]}
            return {
                'startdate': isodates[0],
                'enddate': isodates[1]
            }
        elif isinstance(dateObj, m21.metadata.DateSelection):
            if edtf:
                if dateObj.relevance == 'and':
                    return {'edtf': '{' + ','.join(isodates) + '}'}
                else:
                    return {'edtf': '[' + ','.join(isodates) + ']'}
            else:
                return {}

        return {}

    @staticmethod
    def isoDateFromM21Date(date: m21.metadata.Date, edtf: bool = False) -> str:
        msg: list[str] = []
        for attr in date.attrNames:
            value: int = t.cast(int, getattr(date, attr))
            if value is None:
                break  # ignore anything after this
            suffix: str = ''
            error: str | None = getattr(date, attr + 'Error')
            if error:
                if not edtf:
                    return ''  # pre-EDTF ISO dates can't describe approximate/uncertain values.
                if error == 'uncertain':
                    suffix = '?'
                elif error == 'approximate':
                    suffix = '~'

            sub: str
            if attr == 'year':
                sub = '%04d' % value
            else:
                sub = '%02d' % value
            sub = sub + suffix
            msg.append(sub)

        out = '-'.join(msg[:4])
        if len(msg) >= 4:
            out += 'T' + ':'.join(msg[4:])
        return out

    # Conversions from str to m21.metadata.DatePrimitive types, and back.
    # e.g. '1942///-1943///' -> DateBetween([Date(1942), Date(1943)])
    # m21.metadata.DateBlah have conversions to/from str, and the strings are really close
    # to Humdrum/MEI format, but not quite, and they don't handle some Humdrum cases at all
    # (like the one above).  So I need to replace them here.

    # str -> DateSingle | DateRelative | DateBetween | DateSelection

    # approximate (i.e. not exactly, but reasonably close)
    _dateApproximateSymbols: tuple[str, ...] = ('~', 'x')

    # uncertain (i.e. maybe not correct at all)
    _dateUncertainSymbols: tuple[str, ...] = ('?', 'z')

    # date1-date2 or date1^date2 (DateBetween)
    # date1|date2|date3|date4... (DateSelection)
    _dateDividerSymbols: tuple[str, ...] = ('-', '^', '|')

    @staticmethod
    def m21DatePrimitiveFromString(
        string: str
    ) -> m21.metadata.DatePrimitive | None:
        if not string:
            return None

        # if it looks like an isodate (contains too many '-'s) give up
        if string.count('-') > 1:
            return None

        # check for a zeit date range that is too complicated for DateBetween (needs
        # a range of DatePrimitives, not a range of Dates).
        if string.count('-') == 1:
            for dateStr in string.split('-'):
                if ('~' in dateStr[0:1]
                        or '?' in dateStr[0:1]
                        or '>' in dateStr[0:1]
                        or '<' in dateStr[0:1]):
                    # fail, so we can try a range of DatePrimitives
                    return None

        typeNeeded: t.Type = m21.metadata.DateSingle
        relativeType: str = ''
        if '<' in string[0:1]:  # this avoids string[0] crash on empty string
            typeNeeded = m21.metadata.DateRelative
            string = string.replace('<', '')
            relativeType = 'before'
        elif '>' in string[0:1]:  # this avoids string[0] crash on empty string
            typeNeeded = m21.metadata.DateRelative
            string = string.replace('>', '')
            relativeType = 'after'

        dateStrings: list[str] = [string]  # if we don't split it, this is what we will parse
        for divider in M21Utilities._dateDividerSymbols:
            if divider in string:
                if divider == '|':
                    typeNeeded = m21.metadata.DateSelection
                    # split on all '|'s
                    dateStrings = string.split(divider)
                else:
                    typeNeeded = m21.metadata.DateBetween
                    # split only at first divider
                    dateStrings = string.split(divider, 1)
                # we assume there is only one type of divider present
                break

        del string  # to make sure we never look at it again in this method

        singleRelevance: str = ''
        if typeNeeded == m21.metadata.DateSingle:
            # special case where a leading '~' or '?' should be removed and cause
            # the DateSingle's relevance to be set to 'approximate' or 'uncertain'.
            if '~' in dateStrings[0][0:1]:  # avoids crash on empty dateStrings[0]
                dateStrings[0] = dateStrings[0][1:]
                singleRelevance = 'approximate'
            elif '?' in dateStrings[0][0:1]:  # avoids crash on empty dateStrings[0]
                dateStrings[0] = dateStrings[0][1:]
                singleRelevance = 'uncertain'
        else:
            # This is a bit redundant with the initial check above, but it rejects
            # a few more cases, like an approximate DateRelative.
            for dateString in dateStrings:
                if '~' in dateString[0:1] or '?' in dateString[0:1]:
                    # fail, so we can try a range of m21DatePrimitives
                    return None

        dates: list[m21.metadata.Date] = []
        for dateString in dateStrings:
            date: m21.metadata.Date | None = M21Utilities._dateFromString(dateString)
            if date is None:
                # if dateString is unparseable, give up on date parsing of this whole metadata item
                return None
            dates.append(date)

        if typeNeeded == m21.metadata.DateSingle:
            if singleRelevance:
                return m21.metadata.DateSingle(dates[0], relevance=singleRelevance)
            return m21.metadata.DateSingle(dates[0])

        # the "type ignore" comments below are because DateRelative, DateBetween, and
        # DateSelection are not declared to take a list of Dates, even though they do
        # (DateSingle does as well, but it is declared so).
        if typeNeeded == m21.metadata.DateRelative:
            return m21.metadata.DateRelative(dates[0], relevance=relativeType)  # type: ignore

        if typeNeeded == m21.metadata.DateBetween:
            return m21.metadata.DateBetween(dates)  # type: ignore

        if typeNeeded == m21.metadata.DateSelection:
            return m21.metadata.DateSelection(dates)  # type: ignore

        return None

    @staticmethod
    def _stripDateError(value: str) -> tuple[str, str | None]:
        '''
        Strip error symbols from a numerical value. Return cleaned source and
        error symbol. Only one error symbol is expected per string.
        '''
        sym: tuple[str, ...] = (
            M21Utilities._dateApproximateSymbols + M21Utilities._dateUncertainSymbols
        )
        found = None
        for char in value:
            if char in sym:
                found = char
                break
        if found is None:
            return value, None
        if found in M21Utilities._dateApproximateSymbols:
            value = value.replace(found, '')
            return value, 'approximate'

        # found is in M21Utilities._dateUncertainSymbols
        value = value.replace(found, '')
        return value, 'uncertain'

    _dateAttrNames: list[str] = [
        'year', 'month', 'day', 'hour', 'minute', 'second'
    ]
    _dateAttrStrFormat: list[str] = [
        '%i', '%02.i', '%02.i', '%02.i', '%02.i', '%02.i'
    ]

    _highestSecondString: str = '59'

    @staticmethod
    def _dateFromString(dateStr: str) -> m21.metadata.Date | None:
        # year, month, day, hour, minute are int, second is float
        # (each can be None if not specified)
        values: list[int | float | None] = []

        # yearError, monthError, dayError, hourError, minuteError, secondError
        valueErrors: list[str | None] = []
        dateStr = dateStr.replace(':', '/')
        dateStr = dateStr.replace(' ', '')
        gotOne: bool = False
        try:
            for i, chunk in enumerate(dateStr.split('/')):
                value, error = M21Utilities._stripDateError(chunk)
                if i == 0 and len(value) >= 2:
                    if value[0] == '@':
                        # year with prepended '@' is B.C.E. so replace with '-'
                        value = '-' + value[1:]

                if value == '':
                    values.append(None)
                elif i == 5:
                    # second is a float, but music21 has started ignoring milliseconds recently
                    # so we convert from str to float and then to int (truncating).
                    values.append(int(float(value)))
                    gotOne = True
                else:
                    values.append(int(value))
                    gotOne = True
                valueErrors.append(error)
        except ValueError:
            # if anything failed to convert to integer, this string is unparseable
            gotOne = False

        if not gotOne:
            # There were no parseable values in the string, so no meaningful date to return
            return None

        date: m21.metadata.Date = m21.metadata.Date()
        for attr, attrValue, attrError in zip(M21Utilities._dateAttrNames, values, valueErrors):
            if attrValue is not None:
                setattr(date, attr, attrValue)
                if attrError is not None:
                    setattr(date, attr + 'Error', attrError)

        return date

    @staticmethod
    def stringFromM21DateObject(m21Date: m21.metadata.DatePrimitive) -> str:
        # m21Date is DateSingle, DateRelative, DateBetween, or DateSelection
        # (all derive from DatePrimitive)
        # pylint: disable=protected-access
        output: str = ''
        dateString: str
        if isinstance(m21Date, m21.metadata.DateSelection):
            # series of multiple dates, delimited by '|'
            for i, date in enumerate(m21Date._data):
                dateString = M21Utilities._stringFromDate(date)
                if i > 0:
                    output += '|'
                output += dateString

        elif isinstance(m21Date, m21.metadata.DateBetween):
            # two dates, delimited by '-'
            for i, date in enumerate(m21Date._data):
                dateString = M21Utilities._stringFromDate(date)
                if i > 0:
                    output += '-'
                output += dateString

        elif isinstance(m21Date, m21.metadata.DateRelative):
            # one date, prefixed by '<' or '>' for 'prior'/'onorbefore' or 'after'/'onorafter'
            output = '<'  # assume before
            if m21Date.relevance in ('after', 'onorafter'):
                output = '>'

            dateString = M21Utilities._stringFromDate(m21Date._data[0])
            output += dateString

        elif isinstance(m21Date, m21.metadata.DateSingle):
            # one date, no prefixes
            output = M21Utilities._stringFromDate(m21Date._data[0])
            if m21Date.relevance == 'uncertain':
                # [0] is the date error symbol
                output = M21Utilities._dateUncertainSymbols[0] + output
            elif m21Date.relevance == 'approximate':
                # [0] is the date error symbol
                output = M21Utilities._dateApproximateSymbols[0] + output

        # pylint: enable=protected-access
        return output

    @staticmethod
    def _stringFromDate(date: m21.metadata.Date) -> str:
        msg = []
        if date.hour is None and date.minute is None and date.second is None:
            breakIndex = 3  # index
        else:
            breakIndex = 99999

        for i in range(len(M21Utilities._dateAttrNames)):
            if i >= breakIndex:
                break
            attr = M21Utilities._dateAttrNames[i]
            value = getattr(date, attr)
            error = getattr(date, attr + 'Error')
            if not value:
                msg.append('')
            else:
                fmt = M21Utilities._dateAttrStrFormat[i]
                sub = fmt % int(value)
                if i == 0:  # year
                    # check for negative year, and replace '-' with '@'
                    if len(sub) >= 2 and sub[0] == '-':
                        sub = '@' + sub[1:]
                elif i == 5:  # seconds
                    # Check for formatted seconds starting with '60' (due to rounding) and
                    # truncate to '59'. That's easier than doing rounding correctly
                    # (carrying into minutes, hours, days, etc).
                    if sub.startswith('60'):
                        sub = M21Utilities._highestSecondString
                if error is not None:
                    sub += M21Utilities._dateErrorToSymbol(error)
                msg.append(sub)

        output: str = ''
        if breakIndex == 3:
            # just a date, so leave off any trailing '/'s
            output = msg[0]
            if msg[1] or msg[2]:
                output += '/' + msg[1]
            if msg[2]:
                output += '/' + msg[2]
        else:
            # has a time, so we have to do the whole thing
            output = (
                msg[0] + '/' + msg[1] + '/' + msg[2] + '/' + msg[3] + ':' + msg[4] + ':' + msg[5]
            )

        return output

    @staticmethod
    def _dateErrorToSymbol(value: str) -> str:
        if value.lower() in M21Utilities._dateApproximateSymbols + ('approximate',):
            return M21Utilities._dateApproximateSymbols[1]  # [1] is the single value error symbol
        if value.lower() in M21Utilities._dateUncertainSymbols + ('uncertain',):
            return M21Utilities._dateUncertainSymbols[1]    # [1] is the single value error symbol
        return ''

    @staticmethod
    def stringFromM21DatePrimitiveRange(
        m21StartDatePrimitive: m21.metadata.DatePrimitive,
        m21EndDatePrimitive: m21.metadata.DatePrimitive
    ) -> str:
        # The usual case: both elements of range are DateSingle, with no overall error.
        # We make a DateBetween, and then return the Humdrum string for that.
        if (isinstance(m21StartDatePrimitive, m21.metadata.DateSingle)
                and not m21StartDatePrimitive.relevance
                and isinstance(m21EndDatePrimitive, m21.metadata.DateSingle)
                and not m21EndDatePrimitive.relevance):
            return M21Utilities.stringFromM21DateObject(
                m21.metadata.DateBetween([
                    m21StartDatePrimitive._data[0],
                    m21EndDatePrimitive._data[0]
                ])
            )

        # Funky case: either or both of the elements is NOT a DateSingle.
        # We get a Humdrum string for each of them (using '^' as the range separator)
        # and then combine them with a '-' between them.
        startString: str = M21Utilities.stringFromM21DateObject(m21StartDatePrimitive)
        endString: str = M21Utilities.stringFromM21DateObject(m21EndDatePrimitive)

        startString = startString.replace('-', '^')
        endString = endString.replace('-', '^')

        return startString + '-' + endString

    @staticmethod
    def m21DatePrimitiveRangeFromString(
        string: str
    ) -> tuple[m21.metadata.DatePrimitive | None, m21.metadata.DatePrimitive | None]:
        startDatePrimitive: m21.metadata.DatePrimitive | None = None
        endDatePrimitive: m21.metadata.DatePrimitive | None = None
        dateStrings: list[str] = string.split('-')
        if len(dateStrings) != 2:
            return None, None

        startDatePrimitive = M21Utilities.m21DatePrimitiveFromString(dateStrings[0])
        endDatePrimitive = M21Utilities.m21DatePrimitiveFromString(dateStrings[1])
        return startDatePrimitive, endDatePrimitive


    humdrumReferenceKeyToM21MetadataPropertyUniqueName: dict[str, str] = {
        # dict value is music21's unique name or '' (if there is no m21Metadata equivalent)
        # Authorship information:
        'COM': 'composer',              # composer's name
        'COA': 'attributedComposer',    # attributed composer
        'COS': 'suspectedComposer',     # suspected composer
        'COL': 'composerAlias',         # composer's abbreviated, alias, or stage name
        'COC': 'composerCorporate',     # composer's corporate name
        'CDT': '',                      # composer's birth and death dates (**zeit format)
        'CBL': '',                      # composer's birth location
        'CDL': '',                      # composer's death location
        'CNT': '',                      # composer's nationality
        'LYR': 'lyricist',              # lyricist's name
        'LIB': 'librettist',            # librettist's name
        'LAR': 'arranger',              # music arranger's name
        'LOR': 'orchestrator',          # orchestrator's name
        'TXO': 'textOriginalLanguage',  # original language of vocal/choral text
        'TXL': 'textLanguage',          # language of the encoded vocal/choral text
        # Recording information (if the Humdrum encodes information pertaining to an
        # audio recording)
        'TRN': 'translator',            # translator of the text
        'RTL': '',                      # album title
        'RMM': '',                      # manufacturer or sponsoring company
        'RC#': '',                      # recording company's catalog number of album
        'RRD': 'dateIssued',            # release date (**date format)
        'RLC': '',                      # place of recording
        'RNP': 'producer',              # producer's name
        'RDT': '',                      # date of recording (**date format)
        'RT#': '',                      # track number
        # Performance information (if the Humdrum encodes, say, a MIDI performance)
        'MGN': '',                      # ensemble's name
        'MPN': '',                      # performer's name
        'MPS': '',                      # suspected performer
        'MRD': '',                      # date of performance (**date format)
        'MLC': '',                      # place of performance
        'MCN': 'conductor',             # conductor's name
        'MPD': '',                      # date of first performance (**date format)
        'MDT': '',                      # I've seen 'em (another way to say date of performance?)
        # Work identification information
        'OTL': 'title',                 # title
        'OTP': 'popularTitle',          # popular title
        'OTA': 'alternativeTitle',      # alternative title
        'OPR': 'parentTitle',           # title of parent work
        'OAC': 'actNumber',             # act number (e.g. '2' or 'Act 2')
        'OSC': 'sceneNumber',           # scene number (e.g. '3' or 'Scene 3')
        'OMV': 'movementNumber',        # movement number (e.g. '4', or 'mov. 4', or...)
        'OMD': 'movementName',          # movement name
        'OPS': 'opusNumber',            # opus number (e.g. '23', or 'Opus 23')
        'ONM': 'number',                # number (e.g. number of song within ABC multi-song file)
        'OVM': 'volumeNumber',          # volume number (e.g. '6' or 'Vol. 6')
        'ODE': 'dedicatedTo',           # dedicated to
        'OCO': 'commissionedBy',        # commissioned by
        'OCL': 'transcriber',           # collected/transcribed by
        'ONB': '',                      # free form note related to title or identity of work
        'ODT': 'dateCreated',           # date or period of composition (**date or **zeit format)
        'OCY': 'countryOfComposition',  # country of composition
        'OPC': 'localeOfComposition',   # city, town, or village of composition
        # Group information
        'GTL': 'groupTitle',            # group title (e.g. 'The Seasons')
        'GAW': 'associatedWork',        # associated work, such as a play or film
        'GCO': 'collectionDesignation',  # collection designation (e.g. 'Norton Scores')
        # Imprint information
        'PUB': '',                      # publication status 'published'/'unpublished'
        'PED': '',                      # publication editor
        'PPR': 'firstPublisher',        # first publisher
        'PDT': 'dateFirstPublished',    # date first published (**date format)
        'PTL': 'publicationTitle',      # publication (volume) title
        'PPP': 'placeFirstPublished',   # place first published
        'PC#': 'publishersCatalogNumber',  # publisher's catalog number (NOT scholarly catalog)
        'SCT': 'scholarlyCatalogAbbreviation',  # scholarly catalog abbrev/number (e.g. 'BWV 551')
        'SCA': 'scholarlyCatalogName',  # scholarly catalog (unabbreviated) (e.g. 'Koechel 117')
        'SMS': 'manuscriptSourceName',  # unpublished manuscript source name
        'SML': 'manuscriptLocation',    # unpublished manuscript location
        'SMA': 'manuscriptAccessAcknowledgement',  # acknowledgment of manuscript access
        'YEP': 'electronicPublisher',   # publisher of electronic edition
        'YEC': 'copyright',             # date and owner of electronic copyright
        'YER': 'electronicReleaseDate',  # date electronic edition released
        'YEM': '',                      # copyright message (e.g. 'All rights reserved')
        'YEN': '',                      # country of copyright
        'YOR': '',                      # original document from which encoded doc was prepared
        'YOO': 'originalDocumentOwner',  # original document owner
        'YOY': '',                      # original copyright year
        'YOE': 'originalEditor',        # original editor
        'EED': 'electronicEditor',      # electronic editor
        'ENC': 'electronicEncoder',     # electronic encoder (person)
        'END': '',                      # encoding date
        'EMD': '',                      # electronic document modification description (one/mod)
        'EEV': '',                      # electronic edition version
        'EFL': '',                      # file number e.g. '1/4' for one of four
        'EST': '',                      # encoding status (usually deleted before distribution)
        'VTS': '',                      # checksum (excluding the VTS line itself)
        # Analytic information
        'ACO': '',  # collection designation
        'AFR': '',  # form designation
        'AGN': '',  # genre designation
        'AST': '',  # style, period, or type of work designation
        'AMD': '',  # mode classification e.g. '5; Lydian'
        'AMT': '',  # metric classification, must be one of eight names, e.g. 'simple quadruple'
        'AIN': '',  # instrumentation, must be alphabetical list of *I abbrevs, space-delimited
        'ARE': '',  # geographical region of origin (list of 'narrowing down' names of regions)
        'ARL': '',  # geographical location of origin (lat/long)
        # Historical and background information
        'HAO': '',  # aural history (lots of text, stories about the work)
        'HTX': '',  # freeform translation of vocal text
        # Representation information
        'RLN': '',  # Extended ASCII language code
        'RNB': '',  # a note about the representation
        'RWB': ''   # a warning about the representation
    }

    m21MetadataPropertyUniqueNameToHumdrumReferenceKey: dict[str, str] = {
        uniqueName: hdKey for (hdKey, uniqueName) in
        humdrumReferenceKeyToM21MetadataPropertyUniqueName.items() if uniqueName != ''
    }

    validHumdrumReferenceKeys: tuple[str, ...] = tuple(hdKey for hdKey in
        humdrumReferenceKeyToM21MetadataPropertyUniqueName.keys())

    customHumdrumReferenceKeysThatAreDates: tuple[str, ...] = (
        'CDT',
        'RDT',
        'MRD',
        'MPD',
        'MDT',
        'YOY',
        'END'
    )

    humdrumReferenceKeyToM21OtherContributorRole: dict[str, str] = {
        'MPN': 'performer',
        'MPS': 'suspected performer',
        'PED': 'publication editor',  # a.k.a. 'source editor'
    }

    m21OtherContributorRoleToHumdrumReferenceKey: dict[str, str] = {
        'performer': 'MPN',
        'suspected performer': 'MPS',
        'suspectedPerformer': 'MPS',
        'source editor': 'PED',
        'sourceEditor': 'PED',
        'publication editor': 'PED',
        'publicationEditor': 'PED',
    }

    validMeiMetadataKeys: tuple[str, ...] = (
        'mei:printedSourceCopyright',
    )

    @staticmethod
    def adjustRoleFromContext(role: str, context: str) -> str:
        if role == 'editor':
            if context in ('titleStmt', 'source:digital'):
                return 'electronicEditor'
            if context in ('source:printed', 'source:'):
                return 'publicationEditor'
            if context == 'source:unpub':
                return 'originalEditor'
            return 'editor'
        return role

    @staticmethod
    def meiRoleToUniqueName(md: m21.metadata.Metadata, role: str) -> str:
        if md._isStandardUniqueName(role):
            return role
        if role == 'encoder':
            return 'electronicEncoder'
        if role == 'dedicatee':
            return 'dedicatedTo'
        return ''

    @staticmethod
    def contributorRoleToHumdrumReferenceKey(role: str) -> str:
        output: str = (
            M21Utilities.m21MetadataPropertyUniqueNameToHumdrumReferenceKey.get(
                role, ''
            )
        )
        if output:
            return output

        output = M21Utilities.m21OtherContributorRoleToHumdrumReferenceKey.get(
            role, ''
        )
        if output:
            return output

        altRole: str
        if ' ' in role:
            # try converting to camelCase.
            altRole = M21Utilities.spaceDelimitedToCamelCase(role)
        else:
            # try converting to space-delimited.
            altRole = M21Utilities.camelCaseToSpaceDelimited(role)

        output = (
            M21Utilities.m21MetadataPropertyUniqueNameToHumdrumReferenceKey.get(
                altRole, ''
            )
        )
        if output:
            return output

        output = M21Utilities.m21OtherContributorRoleToHumdrumReferenceKey.get(
            altRole, ''
        )
        if output:
            return output

        return ''

    @staticmethod
    def spaceDelimitedToCamelCase(text: str) -> str:
        output: str = ''
        capitalizeNext: bool = False
        for ch in text:
            if ch == ' ':
                capitalizeNext = True
                continue

            if capitalizeNext:
                output += ch.upper()
                capitalizeNext = False
            else:
                output += ch.lower()
        return output

    @staticmethod
    def camelCaseToSpaceDelimited(text: str) -> str:
        output: str = ''
        for ch in text:
            if ch.isupper():
                output += ' '
                output += ch.lower()
            else:
                output += ch
        return output

    @staticmethod
    def stringFromM21Contributor(c: m21.metadata.Contributor) -> str:
        # TODO: someday support export of multi-named Contributors
        if not c.names:
            return ''
        return c.names[0]

    @staticmethod
    def m21MetadataValueToString(
        value: t.Any,
        isRaw: bool = False,
        lineFeedOK: bool = False
    ) -> str:
        valueStr: str
        if isRaw or isinstance(value, m21.metadata.Text):
            valueStr = str(value)
        elif isinstance(value, m21.metadata.DatePrimitive):
            # We don't like str(DateXxxx)'s results so we do our own.
            valueStr = M21Utilities.stringFromM21DateObject(value)
        elif isinstance(value, m21.metadata.Contributor):
            valueStr = M21Utilities.stringFromM21Contributor(value)
        else:
            # it's already a str, we hope, but if not, we convert here
            valueStr = str(value)

        if not lineFeedOK:
            # escape any \n
            valueStr = valueStr.replace('\n', r'\n')
        return valueStr

    @staticmethod
    def isUsableMetadataKey(
        md: m21.metadata.Metadata,
        key: str,
        includeHumdrumCustomKeys: bool = True
    ) -> bool:
        # returns true if key is a standard uniqueName, a standard namespaceName,
        # a non-standard namespaceName that we can convert into a standard
        # uniqueName/namespaceName (e.g. 'dcterm:title' can be converted to
        # 'dcterms:title'), or a 'humdrum:XXX' name that we are willing to
        # use as if it were a standard namespaceName (but is actually a custom
        # key).
        if md._isStandardUniqueName(key):
            return True
        if md._isStandardNamespaceName(key):
            return True
        if key.startswith('humdrum:'):
            if includeHumdrumCustomKeys:
                return True
            else:
                # is it standard?  Yes, if it maps to a uniqueName
                uniqueName: str = (
                    M21Utilities.humdrumReferenceKeyToM21MetadataPropertyUniqueName.get(
                        key[8:],
                        ''
                    )
                )
                if uniqueName:
                    # humdrum key that maps to uniqueName; always welcome
                    return True
                # custom humdrum key, and we've been asked not to include them
                return False

        # Let's see if we can make a standard namespaceName from it.
        if key.startswith('dcterm:'):
            key = key.replace('dcterm:', 'dcterms:')
            if md._isStandardNamespaceName(key):
                return True
            return False

        if key.startswith('dc:'):
            key = key.replace('dc:', 'dcterms:')
            if md._isStandardNamespaceName(key):
                return True
            return False

        if key.startswith('marc:'):
            key = key.replace('marc:', 'marcrel:')
            if md._isStandardNamespaceName(key):
                return True
            return False

        return False

    @staticmethod
    def addIfNotADuplicate(
        md: m21.metadata.Metadata,
        key: str,
        value: t.Any,
        other: dict[str, str] | None = None
    ):
        # Note that we specifically support 'humdrum:XXX' keys that do not map
        # to uniqueNames and 'mei:blahblah' keys (using them as custom keys).
        # We also support a few alternative namespaces ('dc:' and 'dcterm:' for
        # 'dcterms:' and 'marc:' for 'marcrel:').
        uniqueName: str | None = None
        if md._isStandardUniqueName(key):
            uniqueName = key
        elif md._isStandardNamespaceName(key):
            uniqueName = md.namespaceNameToUniqueName(key)
        elif key.startswith('humdrum:'):
            uniqueName = M21Utilities.humdrumReferenceKeyToM21MetadataPropertyUniqueName.get(
                key[8:],
                ''
            )
            if not uniqueName:
                M21Utilities.addCustomIfNotADuplicate(md, key, value, other)
                return
        elif key.startswith('mei:'):
            if key in M21Utilities.validMeiMetadataKeys:
                M21Utilities.addCustomIfNotADuplicate(md, key, value, other)
                return
        elif key.startswith('dcterm:'):
            key = key.replace('dcterm:', 'dcterms:')
            if md._isStandardNamespaceName(key):
                uniqueName = md.namespaceNameToUniqueName(key)
        elif key.startswith('dc:'):
            key = key.replace('dc:', 'dcterms:')
            if md._isStandardNamespaceName(key):
                uniqueName = md.namespaceNameToUniqueName(key)
        elif key.startswith('marc:'):
            key = key.replace('marc:', 'marcrel:')
            if md._isStandardNamespaceName(key):
                uniqueName = md.namespaceNameToUniqueName(key)

        if isinstance(value, str):
            value = m21.metadata.Text(value)

        if uniqueName:
            value = md._convertValue(uniqueName, value)

        if other:
            for k, v in other.items():
                M21Utilities.addOtherMetadataAttrib(value, k, v)
                c21OtherAttribs: set[str] = set()
                if hasattr(value, 'c21OtherAttribs'):
                    c21OtherAttribs = getattr(value, 'c21OtherAttribs')
                c21OtherAttribs.add(k)
                setattr(value, 'c21OtherAttribs', c21OtherAttribs)
                setattr(value, k, v)

        if uniqueName is None:
            uniqueName = ''

        for val in md[uniqueName]:
            if M21Utilities.mdValueEqual(val, value):
                return
        md.add(uniqueName, value)

    @staticmethod
    def addOtherMetadataAttrib(value: m21.metadata.ValueType, k: str, v: str):
        c21OtherAttribs: set[str] = set()
        if hasattr(value, 'c21OtherAttribs'):
            c21OtherAttribs = getattr(value, 'c21OtherAttribs')
        c21OtherAttribs.add(k)
        setattr(value, 'c21OtherAttribs', c21OtherAttribs)
        setattr(value, k, v)

    @staticmethod
    def mdValueEqual(v1: m21.metadata.ValueType, v2: m21.metadata.ValueType) -> bool:
        if isinstance(v1, m21.metadata.Text) and isinstance(v2, m21.metadata.Text):
            # don't compare .isTranslated, it's often lost in various file formats.
            if v1._data != v2._data:
                return False
            if v1.language != v2.language:
                return False
        else:
            if v1 != v2:
                return False

        # check other attributes set by converter21 importers
        # (e.g. MEI importer adds 'meiVersion')
        c21OtherAttribs1: set[str] = set()
        c21OtherAttribs2: set[str] = set()
        if hasattr(v1, 'c21OtherAttribs'):
            c21OtherAttribs1 = getattr(v1, 'c21OtherAttribs')
        if hasattr(v2, 'c21OtherAttribs'):
            c21OtherAttribs2 = getattr(v2, 'c21OtherAttribs')
        if len(c21OtherAttribs1) != len(c21OtherAttribs2):
            return False
        for v1Attr, v2Attr in zip(c21OtherAttribs1, c21OtherAttribs2):
            if getattr(v1, v1Attr) != getattr(v2, v2Attr):
                return False
        return True

    @staticmethod
    def addCustomIfNotADuplicate(
        md: m21.metadata.Metadata,
        key: str,
        value: str | m21.metadata.Text,
        other: dict[str, str] | None = None
    ):
        if isinstance(value, str):
            value = m21.metadata.Text(value, isTranslated=False)
        for val in md.getCustom(key):
            if M21Utilities.mdValueEqual(val, value):
                return
        md.addCustom(key, value)

    ACCIDENTAL_CHAR_TO_ASCII: dict[str, str] = {
        # Unicode
        SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR['musicFlatSign']: 'b',
        SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR['musicSharpSign']: '#',
        # SMUFL
        SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR['accidentalFlat']: 'b',
        SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR['accidentalSharp']: '#',
        SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR['accidentalDoubleSharp']: '##',
        SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR['accidentalDoubleFlat']: 'bb',
        SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR['accidentalTripleSharp']: '###',
        SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR['accidentalTripleFlat']: 'bbb',
        SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR['accidentalNaturalFlat']: 'b',
        SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR['accidentalNaturalSharp']: '#',
        SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR['accidentalSharpSharp']: '##',
    }

    # ============================
    # ChordSymbol support routines
    # ============================

    @staticmethod
    def convertChordSymbolFigureToPrintableText(text: str, removeNoteNames: bool = False) -> str:
        # For use when writing an MEI file.
        # removeRootName = True?  Good for computing cs.chordKindStr

        # In a cs figure, just after first char (root), any flats are '-'; any trailing '-'s
        # (after bass)', but everywhere between, 'b' means flat (unless it's in the word
        # 'subtract').
        # Turn all '-' to 'b' and all 'subtract' to 'omit' (which works better in a printable
        # string anyway).
        text = re.sub('subtract', 'omit', text)
        text = re.sub('-', 'b', text)

        output: str = ''
        unicodeFlat: str = SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR['accidentalFlat']
        unicodeSharp: str = SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR['accidentalSharp']
        for ch in text:
            if ch == 'b':
                output += unicodeFlat
            elif ch == '#':
                output += unicodeSharp
            elif ch == ' ':
                pass  # we are removing the spaces around ' add ', ' omit ', ' alter '
            else:
                output += ch

        if removeNoteNames:
            # remove leading chord letter name (and accidentals)
            output = output[1:]
            while output and output[0] in (unicodeFlat, unicodeSharp):
                output = output[1:]

            if '/' in output:
                # remove trailing '/blah'
                slashIdx: int = output.index('/')
                output = output[:slashIdx]

        # some final tweaks of things music21 does, that I don't like
        output = output.replace('dim', '\u00B0')  # degree symbol instead of 'dim'
        if 'o' in output:
            output = output.replace('o7', '\u00B0' + '7')
            output = output.replace('o9', '\u00B0' + '9')
            output = output.replace('o' + unicodeFlat + '9', '\u00B0' + unicodeFlat + '9')
            output = output.replace('o11', '\u00B0' + '11')

        return output

    @staticmethod
    def convertPrintableTextToChordSymbolFigure(text: str) -> str:
        output: str = ''

        # First, put the spaces back in around 'add', 'omit', 'subtract', and 'alter'
        # (music21 will accept both omit and subtract in a figure as meaning the same
        # thing, so we go for omit everywhere to avoid the confusion of extra 'b's).
        text = re.sub('add', ' add ', text)
        text = re.sub('omit', ' omit ', text)
        text = re.sub('subtract', ' omit ', text)  # Yes, switch to ' omit '
        text = re.sub('alter', ' alter ', text)

        # Note how we choose between 'b' and '-' for output ('-' for any root/bass accidentals
        # 'b' for other notes).
        useHyphen: bool = False  # for root

        i = 0
        while i < len(text):
            ch = text[i]
            if i == 0:
                # grab root plus any accidental(s)
                output += ch
                i += 1
                while ch in M21Utilities.ACCIDENTAL_CHAR_TO_ASCII:
                    output += M21Utilities.ACCIDENTAL_CHAR_TO_ASCII[ch]
                    i += 1

                # from now until we see a '/' (just before bass note, if present),
                # we will change any 'b' ASCII accidental to '-'.
                useHyphen = True
                continue

            if ch == '/':
                useHyphen = False  # for bass

            if ch in M21Utilities.ACCIDENTAL_CHAR_TO_ASCII:
                newStr: str = M21Utilities.ACCIDENTAL_CHAR_TO_ASCII[ch]
                if useHyphen and newStr in ('b', 'bb', 'bbb'):
                    newStr = '-' * len(newStr)
                output += newStr
            else:
                output += ch

            i += 1

        return output

    @staticmethod
    def chordSymbolHasAlters(cs: m21.harmony.ChordSymbol) -> bool:
        for csMod in cs.chordStepModifications:
            if csMod.modType == 'alter':
                return True
        return False

    @staticmethod
    def makeM21RegFromChordSymbol(cs: m21.harmony.ChordSymbol) -> str:
        return cs.figure

    @staticmethod
    def makeChordSymbolFromM21Reg(figure: str) -> m21.harmony.ChordSymbol | None:
        cs: m21.harmony.ChordSymbol | None = None

        try:
            cs = m21.harmony.ChordSymbol(figure)
            if not cs.pitches or (len(cs.pitches) == 1 and 'pedal' not in figure):
                cs = None
        except Exception:
            cs = None

        return cs

    M21_CHORD_KIND_TO_HARTE_SHORTHAND_AND_DEGREES: dict[str, tuple[str, str]] = {
        # triads
        'major': ('maj', ''),
        'minor': ('min', ''),
        'augmented': ('aug', ''),
        'diminished': ('dim', ''),

        # sevenths
        'dominant-seventh': ('7', ''),
        'major-seventh': ('maj7', ''),
        'minor-major-seventh': ('minmaj7', ''),
        'minor-seventh': ('min7', ''),
        'augmented-major-seventh': ('aug', '7'),
        'augmented-seventh': ('aug', 'b7'),
        'half-diminished-seventh': ('hdim7', ''),
        'diminished-seventh': ('dim7', ''),
        'seventh-flat-five': ('', '3,b5,b7'),

        # sixths
        'major-sixth': ('maj6', ''),
        'minor-sixth': ('min6', ''),

        # ninths
        'major-ninth': ('maj9', ''),
        'dominant-ninth': ('9', ''),
        'minor-major-ninth': ('minmaj7', '9'),
        'minor-ninth': ('min9', ''),
        'augmented-major-ninth': ('aug', '7,9'),
        'augmented-dominant-ninth': ('aug', 'b7,9'),
        'half-diminished-ninth': ('hdim7', '9'),
        'half-diminished-minor-ninth': ('hdim7', 'b9'),
        'diminished-ninth': ('dim7', '9'),
        'diminished-minor-ninth': ('dim7', 'b9'),

        # elevenths
        'dominant-11th': ('9', '11'),
        'major-11th': ('maj9', '11'),
        'minor-major-11th': ('minmaj7', '9,11'),
        'minor-11th': ('min9', '11'),
        'augmented-major-11th': ('aug', '7,9,11'),
        'augmented-11th': ('aug', 'b7,9,11'),
        'half-diminished-11th': ('hdim7', '9,11'),
        'diminished-11th': ('dim7', '9,11'),

        # thirteenths
        'major-13th': ('maj9', '11,13'),
        'dominant-13th': ('9', '11,13'),
        'minor-major-13th': ('minmaj7', '9,11,13'),
        'minor-13th': ('min9', '11,13'),
        'augmented-major-13th': ('aug', '7,9,11,13'),
        'augmented-dominant-13th': ('aug', 'b7,9,11,13'),
        'half-diminished-13th': ('hdim7', '9,11,13'),

        # other
        'suspended-second': ('', '1,2,5'),
        'suspended-fourth': ('sus4', ''),
        'suspended-fourth-seventh': ('sus4', 'b7'),
        'Neapolitan': ('', '1,b2,3,b5'),
        'neapolitan': ('', '1,b2,3,b5'),
        'Italian': ('', '1,#4,b6'),
        'italian': ('', '1,#4,b6'),
        'French': ('', '1,2,#4,b6'),
        'french': ('', '1,2,#4,b6'),
        'German': ('', '1,b3,#4,b6'),
        'german': ('', '1,b3,#4,b6'),
        'pedal': ('', '1'),
        'power': ('', '1,5'),
        'Tristan': ('', '1,#4,#6,#9'),
        'tristan': ('', '1,#4,#6,#9'),
    }

    M21_CHORD_KIND_TO_HARTE_DEGREES: dict[str, str] = {
        # triads
        'major': '3,5',
        'minor': 'b3,5',
        'augmented': '3,#5',
        'diminished': 'b3,b5',

        # sevenths
        'dominant-seventh': '3,5,b7',
        'major-seventh': '3,5,7',
        'minor-major-seventh': 'b3,5,7',
        'minor-seventh': 'b3,5,b7',
        'augmented-major-seventh': '3,#5,7',
        'augmented-seventh': '3,#5,b7',
        'half-diminished-seventh': 'b3,b5,b7',
        'diminished-seventh': 'b3,b5,bb7',
        'seventh-flat-five': '3,b5,b7',

        # sixths
        'major-sixth': '3,5,6',
        'minor-sixth': 'b3,5,6',

        # ninths
        'major-ninth': '3,5,7,9',
        'dominant-ninth': '3,5,b7,9',
        'minor-major-ninth': 'b3,5,7,9',
        'minor-ninth': 'b3,5,b7,9',
        'augmented-major-ninth': '3,#5,7,9',
        'augmented-dominant-ninth': '3,#5,b7,9',
        'half-diminished-ninth': 'b3,b5,b7,9',
        'half-diminished-minor-ninth': 'b3,b5,b7,b9',
        'diminished-ninth': 'b3,b5,bb7,9',
        'diminished-minor-ninth': 'b3,b5,bb7,b9',

        # elevenths
        'dominant-11th': '3,5,b7,9,11',
        'major-11th': '3,5,7,9,11',
        'minor-major-11th': 'b3,5,7,9,11',
        'minor-11th': 'b3,5,b7,9,11',
        'augmented-major-11th': '3,#5,7,9,11',
        'augmented-11th': '3,#5,b7,9,11',
        'half-diminished-11th': 'b3,b5,b7,9,11',
        'diminished-11th': 'b3,b5,bb7,9,11',

        # thirteenths
        'major-13th': '3,5,7,9,11,13',
        'dominant-13th': '3,5,b7,9,11,13',
        'minor-major-13th': 'b3,5,7,9,11,13',
        'minor-13th': 'b3,5,b7,9,11,13',
        'augmented-major-13th': '3,#5,7,9,11,13',
        'augmented-dominant-13th': '3,#5,b7,9,11,13',
        'half-diminished-13th': 'b3,b5,b7,9,11,13',

        # other
        'suspended-second': '1,2,5',
        'suspended-fourth': '1,4,5',
        'suspended-fourth-seventh': '1,4,5,b7',
        'Neapolitan': '1,b2,3,b5',
        'neapolitan': '1,b2,3,b5',
        'Italian': '1,#4,b6',
        'italian': '1,#4,b6',
        'French': '1,2,#4,b6',
        'french': '1,2,#4,b6',
        'German': '1,b3,#4,b6',
        'german': '1,b3,#4,b6',
        'pedal': '1',
        'power': '1,5',
        'Tristan': '1,#4,#6,#9',
        'tristan': '1,#4,#6,#9',
    }

    HARTE_SHORTHAND_TO_DEGREE_TUPLE: dict[str, tuple[str, ...]] = {
        'maj': ('3', '5'),
        'min': ('b3', '5'),
        'dim': ('b3', 'b5'),
        'aug': ('3', '#5'),
        'maj7': ('3', '5', '7'),
        'min7': ('b3', '5', 'b7'),
        '7': ('3', '5', 'b7'),
        'dim7': ('b3', 'b5', 'bb7'),
        'hdim7': ('b3', 'b5', 'b7'),
        'minmaj7': ('b3', '5', '7'),
        'maj6': ('3', '5', '6'),
        'min6': ('b3', '5', '6'),
        '9': ('3', '5', 'b7', '9'),
        'maj9': ('3', '5', '7', '9'),
        'min9': ('b3', '5', 'b7', '9'),
        'sus4': ('4', '5'),
    }

    @staticmethod
    def _degreeInt(degree: str) -> int:
        m = re.match(r'[b#-*]*(\d+)', degree)
        if not m:
            raise Converter21InternalError('unparseable (Harte, music21) degree string')
        return int(m.group(1))

    @staticmethod
    def makeHarteFromChordSymbol(cs: m21.harmony.ChordSymbol, noResult: str = '') -> str:
        def hartifyRoot(root: m21.pitch.Pitch) -> str:
            return re.sub('-', 'b', root.name)

        def hartifyBass(bass: m21.pitch.Pitch, root: m21.pitch.Pitch) -> str:
            # returns the degree of the bass note, relative to the root.
            # For example, if bass=C-flat and root=D, returns 'bb7'
            # First, these are in the wrong octaves.  We need the bass to
            # be less than an octave above the root so we can get an interval
            # going up.  That way we know m21Name[-1] works to get the degree
            # number, because we know bass is above root, by less than 8 degrees
            # so it will be the last character of 'M3' or whatever.
            if bass.name == root.name:
                return ''

            newBass: m21.pitch.Pitch = deepcopy(bass)
            newBass.octave = root.octave
            if newBass < root:
                # we know newBass.octave and root.octave are not None
                newBass.octave += 1  # type: ignore

            intv = m21.interval.Interval(root, newBass)
            m21Name: str = intv.name
            degreeNumStr: str = m21Name[-1]
            if degreeNumStr in ('1', '4', '5'):  # won't be '8'
                if m21Name.startswith('P'):
                    return degreeNumStr
                if m21Name.startswith('A'):
                    return ('#' * m21Name.count('A')) + str(degreeNumStr)
                if m21Name.startswith('d'):
                    return ('b' * m21Name.count('d')) + str(degreeNumStr)

            # '2', '3', '6', '7' use 'M' instead of 'P', and 'm' for the first decrement.
            if m21Name.startswith('M'):
                return degreeNumStr
            if m21Name.startswith('A'):
                return ('#' * m21Name.count('A')) + str(degreeNumStr)
            if m21Name.startswith('m'):
                return 'b' + degreeNumStr
            if m21Name.startswith('d'):
                numFlats: int = m21Name.count('d') + 1
                return ('b' * numFlats) + degreeNumStr

            # shouldn't get here
            return degreeNumStr

        def modifyDegrees(
            degrees: str,
            addList: list[str],
            omitList: list[str],
            alterList: list[str]
        ) -> str:
            degreeList: list[str] = []
            newDegreeList: list[str] = []
            if degrees:
                degreeList = degrees.split(',')
                newDegreeList = copy(degreeList)
            # first do the omitList
            for omit in omitList:
                removedIt: bool = False
                for deg in degreeList:
                    if omit == deg:
                        # we only remove it from current degree list if it has
                        # the same number of #'s or b's
                        newDegreeList.remove(deg)
                        removedIt = True
                if not removedIt:
                    # put it in the list with a '*' replacing the #'s or b's,
                    # to omit it from the degree list implied by the shorthand
                    newDegreeList.append('*' + str(M21Utilities._degreeInt(omit)))

            # then the alters (if there are alters, there is no shorthand;
            # all the notes are represented in degreeList)
            for alter in alterList:
                for i, deg in enumerate(degreeList):
                    if M21Utilities._degreeInt(alter) == M21Utilities._degreeInt(deg):
                        # we alter anything with the right degree number
                        newDegreeList[i] = alter

            # then the adds
            newDegreeList.extend(addList)

            # sort by degree (lowest degree first)
            newDegreeList = sorted(newDegreeList, key=M21Utilities._degreeInt)
            return ','.join(newDegreeList)

        # --------- start of makeHarteFromChordSymbol ---------
        cs = deepcopy(cs)  # because we want to try to simplify it
        M21Utilities.simplifyChordSymbol(cs)

        if isinstance(cs, m21.harmony.NoChord):
            return 'N'

        if not cs.pitches:
            return 'N'

        root: m21.pitch.Pitch | None = cs.root()
        if root is None:
            # could do something smart if there are pitches but no root (but would that happen?)
            return 'N'

        bass: m21.pitch.Pitch | None = cs.bass()

        harteRoot: str = hartifyRoot(root)
        harteBass: str = ''
        if bass is not None:
            harteBass = hartifyBass(bass, root)
        shorthand: str = ''
        degrees: str = ''

        if M21Utilities.chordSymbolHasAlters(cs):
            # we can't use shorthand, just a list of degrees (which we will alter)
            if cs.chordKind in M21Utilities.M21_CHORD_KIND_TO_HARTE_DEGREES:
                degrees = (
                    M21Utilities.M21_CHORD_KIND_TO_HARTE_DEGREES[cs.chordKind]
                )
            else:
                return noResult
        else:
            if cs.chordKind in M21Utilities.M21_CHORD_KIND_TO_HARTE_SHORTHAND_AND_DEGREES:
                shorthand, degrees = (
                    M21Utilities.M21_CHORD_KIND_TO_HARTE_SHORTHAND_AND_DEGREES[cs.chordKind]
                )
            else:
                return noResult

        # Now figure out ChordSymbol alters/adds/subtracts
        if cs.chordStepModifications:
            omitList: list[str] = []
            addList: list[str] = []
            alterList: list[str] = []

            for csMod in cs.chordStepModifications:
                degree: str = str(csMod.degree)
                if csMod.interval is not None:
                    numAlter = csMod.interval.semitones
                    if numAlter > 0:
                        s = '#'
                    else:
                        s = 'b'
                    prefix: str = s * abs(numAlter)
                    degree = prefix + degree

                if csMod.modType == 'subtract':
                    omitList.append(degree)
                elif csMod.modType == 'add':
                    addList.append(degree)
                else:
                    alterList.append(degree)

            degrees = modifyDegrees(degrees, addList, omitList, alterList)

        harte: str = harteRoot
        if shorthand or degrees:
            harte += ':'
            if shorthand:
                harte += shorthand
            if degrees:
                harte += '(' + degrees + ')'
        if harteBass:
            harte += '/' + harteBass
        return harte

    @staticmethod
    def makeChordSymbolFromHarte(harte: str) -> m21.harmony.ChordSymbol | None:
        def parseHarte(harte: str) -> tuple[str, str, str, str]:
            # returns root, shorthand, degrees (without parens), bass
            if harte == 'N':
                return 'N', '', '', ''

            root: str = ''
            shorthand: str = ''
            degrees: str = ''
            bass: str = ''
            # This pattern allows some malformed harte, but does a good job of splitting
            # up the 4 parts (some optional) of the string.
            m = re.match(
                r'^([A-G#b]+)(?::([a-z0-9]*)(\([*#b,\d]+\))?)?(?:\/([#b]*\d+))?$',
                harte
            )
            if m:
                root = m.group(1) or ''
                shorthand = m.group(2) or ''
                degrees = m.group(3) or ''
                bass = m.group(4) or ''

            if degrees:
                # the regex left the parens on; strip them off
                degrees = degrees[1:-1]

            return root, shorthand, degrees, bass

        def deHartifyBass(bass: str, rootPitch: m21.pitch.Pitch) -> m21.pitch.Pitch | None:
            if bass == '1':
                # exactly the same note as root
                return None

            bassNum: str = ''
            accid: str = ''
            for ch in bass:
                if ch in '#b':
                    accid += ch
                elif ch in '1234567':
                    bassNum = ch
                    break

            bassAlter: int = accid.count('#')
            bassAlter -= accid.count('b')

            bassIntvName: str
            if bassNum in ('1', '4', '5'):
                if bassAlter < 0:
                    bassIntvName = ('d' * -bassAlter) + bassNum
                elif bassAlter > 0:
                    bassIntvName = ('A' * bassAlter) + bassNum
                else:
                    bassIntvName = 'P' + bassNum
            else:
                # '2', '3', '6', '7' use 'M' instead of 'P', and 'm' for the first decrement.
                if bassAlter == -1:
                    bassIntvName = 'm' + bassNum
                elif bassAlter < -1:
                    bassIntvName = ('d' * (bassAlter - 1)) + bassNum
                elif bassAlter > 0:
                    bassIntvName = ('A' * bassAlter) + bassNum
                else:
                    bassIntvName = 'M' + bassNum

            bassPitch = m21.interval.Interval(bassIntvName).transposePitch(
                rootPitch,
                inPlace=False
            )

            # make sure bass is (just) below root
            bassPitch.octave = rootPitch.octave
            if bassPitch > rootPitch:
                bassPitch.octave -= 1  # type: ignore

            return bassPitch

        # ---------- makeChordSymbolFromHarte starts here ----------

        root: str = ''
        shorthand: str = ''
        degrees: str = ''
        bass: str = ''
        root, shorthand, degrees, bass = parseHarte(harte)
        if root == 'N':
            return m21.harmony.NoChord()
        if not root:
            return None  # Harte without a root is to be ignored (not even a NoChord)

        # root looks like 'Fb', which needs to turn into 'F-' ('#' can be left as is)
        rootPitch = m21.pitch.Pitch(re.sub('b', '-', root), octave=3)

        # bass looks like '-3', which means the major third of the chord, less one semitone
        # (without changing the letter name of the note), so we might end up with who
        # knows what accidental.  Degree numbers are always the major/perfect degree,
        # (or, if you like, the degree of the major scale starting at the root).  The
        # degree accidental(s) adjust that pitch's accidental.)
        bassPitch: m21.pitch.Pitch | None = None
        if bass:
            bassPitch = deHartifyBass(bass, rootPitch)

        degreeList: list[str] = degrees.split(',') if degrees else []
        if shorthand:
            # add the implied degrees to degreeList
            impliedDegList: list[str] = []
            if shorthand in M21Utilities.HARTE_SHORTHAND_TO_DEGREE_TUPLE:
                impliedDegList = list(M21Utilities.HARTE_SHORTHAND_TO_DEGREE_TUPLE[shorthand])
            # check original degreeList for removals (that we then remove from impliedDegList)
            removeList: list[str] = []
            if impliedDegList:
                for deg in degreeList:
                    if deg.startswith('*'):
                        removeList.append(deg[1:])
                for remDeg in removeList:
                    if remDeg in impliedDegList:
                        impliedDegList.remove(remDeg)
                    if '*' + remDeg in degreeList:
                        degreeList.remove('*' + remDeg)

            if impliedDegList:
                degreeList.extend(impliedDegList)

        # there's always the implied degree '1'
        if '1' not in degreeList:
            degreeList.insert(0, '1')

        # sort the list (by degree)
        degreeList = sorted(degreeList, key=M21Utilities._degreeInt)
        leftoverDegrees: set[str] = set()

        m21ChordKind: str = ''

        # we need to find the CHORD_TYPE that has the most common notes (and no extra notes)
        mostCommonNotes: int = 0
        for kind in m21.harmony.CHORD_TYPES:
            kindDegrees: str = m21.harmony.getNotationStringGivenChordType(kind)
            kindDegrees = re.sub('-', 'b', kindDegrees)
            kindDegreeList: list[str] = kindDegrees.split(',')

            degreeSet: set[str] = set(degreeList)
            kindDegreeSet: set[str] = set(kindDegreeList)

            # kindDegreeList must have no extra notes (beyond those in degreeSet)
            if kindDegreeSet - degreeSet != set():
                continue

            # We're looking for biggest intersection
            inter: set[str] = kindDegreeSet & degreeSet
            if len(inter) > mostCommonNotes:
                m21ChordKind = kind
                mostCommonNotes = len(inter)
                leftoverDegrees = degreeSet - kindDegreeSet
            elif len(inter) == mostCommonNotes:
                # break the tie with len(leftoverDegrees)
                newLeftovers: set[str] = degreeSet - kindDegreeSet
                if len(newLeftovers) < len(leftoverDegrees):
                    m21ChordKind = kind
                    mostCommonNotes = len(inter)
                    leftoverDegrees = newLeftovers

        if not m21ChordKind:
            raise Converter21InternalError('Could not find matching kind; not even pedal!')

        cs: m21.harmony.ChordSymbol | None = None
        try:
            cs = m21.harmony.ChordSymbol(root=rootPitch, bass=bassPitch, kind=m21ChordKind)
            if cs is not None and not cs.pitches:
                cs = None
        except Exception:
            cs = None

        if cs is not None and leftoverDegrees:
            # add the extra degrees not implied by m21ChordKind (in order, lowest first)
            leftoverDegreesList = sorted(list(leftoverDegrees), key=M21Utilities._degreeInt)
            for deg in leftoverDegreesList:
                degInt: int = M21Utilities._degreeInt(deg)
                if degInt == 1:
                    # we don't need to add it because it's the root
                    continue

                alter: int = deg.count('#')
                alter -= deg.count('b')  # 'b', not '-', because these are Harte degrees
                csMod = m21.harmony.ChordStepModification('add', degInt, alter)
                cs.addChordStepModification(csMod, updatePitches=True)

        if cs is not None:
            # see if we can find a better chordKind with fewer chordStepModifications
            M21Utilities.simplifyChordSymbol(cs)

        return cs

    @staticmethod
    def simplifyChordSymbol(cs: m21.harmony.ChordSymbol):
        csms: list[m21.harmony.ChordStepModification] = cs.getChordStepModifications()
        if not csms:
            return

        csWasModified: bool = False
        if len(csms) == 1 and cs.chordKind in (
                'major', 'minor', 'augmented', 'diminished',
                'augmented-seventh', 'augmented-major-seventh',
                'minor-seventh'):
            csm: m21.harmony.ChordStepModification = csms[0]
            if csm.modType == 'add' and csm.degree == 7:
                if cs.chordKind == 'major':
                    if csm.interval.semitones == 0:
                        cs.chordKind = 'major-seventh'
                        csWasModified = True
                    elif csm.interval.semitones == -1:
                        cs.chordKind = 'dominant-seventh'
                        csWasModified = True
                elif cs.chordKind == 'minor':
                    if csm.interval.semitones == 0:
                        cs.chordKind = 'minor-major-seventh'
                        csWasModified = True
                    elif csm.interval.semitones == -1:
                        cs.chordKind = 'minor-seventh'
                        csWasModified = True
                elif cs.chordKind == 'augmented':
                    if csm.interval.semitones == 0:
                        cs.chordKind = 'augmented-major-seventh'
                        csWasModified = True
                    elif csm.interval.semitones == -1:
                        cs.chordKind = 'augmented-seventh'
                        csWasModified = True
                elif cs.chordKind == 'diminished':
                    if csm.interval.semitones == -1:
                        cs.chordKind = 'half-diminished-seventh'
                        csWasModified = True
                    elif csm.interval.semitones == -2:
                        cs.chordKind = 'diminished-seventh'
                        csWasModified = True
            elif csm.modType == 'add' and csm.degree == 9 and csm.interval.semitones == 0:
                if cs.chordKind == 'augmented-seventh':
                    cs.chordKind = 'augmented-dominant-ninth'
                    csWasModified = True
                elif cs.chordKind == 'augmented-major-seventh':
                    cs.chordKind = 'augmented-major-ninth'
                    csWasModified = True
            elif csm.modType == 'alter' and csm.degree == 5 and csm.interval.semitones == -1:
                if cs.chordKind == 'minor-seventh':
                    cs.chordKind = 'half-diminished-seventh'
                    csWasModified = True

        if csWasModified:
            cs.chordStepModifications = []
            cs.figure = None  # next get will update it

    @staticmethod
    def _updatePitches(cs: m21.harmony.ChordSymbol):
        # fix bug in cs._updatePitches (it doesn't know about 'augmented' ninths)
        def adjustOctaves(cs, pitches):
            from music21 import pitch, chord
            self = cs  # because this is an edited copy of ChordSymbol._adjustOctaves
            if not isinstance(pitches, list):
                pitches = list(pitches)

            # do this for all ninth, thirteenth, and eleventh chords...
            # this must be done to get octave spacing right
            # possibly rewrite figured bass function with this integrated?
            # ninths = ['dominant-ninth', 'major-ninth', 'minor-ninth']
            # elevenths = ['dominant-11th', 'major-11th', 'minor-11th']
            # thirteenths = ['dominant-13th', 'major-13th', 'minor-13th']

            if self.chordKind.endswith('-ninth'):
                pitches[1] = pitch.Pitch(pitches[1].name + str(pitches[1].octave + 1))
            elif self.chordKind.endswith('-11th'):
                pitches[1] = pitch.Pitch(pitches[1].name + str(pitches[1].octave + 1))
                pitches[3] = pitch.Pitch(pitches[3].name + str(pitches[3].octave + 1))

            elif self.chordKind.endswith('-13th'):
                pitches[1] = pitch.Pitch(pitches[1].name + str(pitches[1].octave + 1))
                pitches[3] = pitch.Pitch(pitches[3].name + str(pitches[3].octave + 1))
                pitches[5] = pitch.Pitch(pitches[5].name + str(pitches[5].octave + 1))
            else:
                return pitches

            c = chord.Chord(pitches)
            c = c.sortDiatonicAscending()

            return list(c.pitches)

        self = cs  # because this is a copy of ChordSymbol._updatePitches
        if 'root' not in self._overrides or 'bass' not in self._overrides or self.chordKind is None:
            return

        # create figured bass scale with root as scale
        fbScale = realizerScale.FiguredBassScale(self._overrides['root'], 'major')

        # render in the 3rd octave by default
        self._overrides['root'].octave = 3
        self._overrides['bass'].octave = 3

        if self._notationString():
            pitches = fbScale.getSamplePitches(self._overrides['root'], self._notationString())
            # remove duplicated bass note due to figured bass method.
            pitches.pop(0)
        else:
            pitches = []
            pitches.append(self._overrides['root'])
            if self._overrides['bass'] not in pitches:
                pitches.append(self._overrides['bass'])

        pitches = adjustOctaves(self, pitches)

        if self._overrides['root'].name != self._overrides['bass'].name:
            inversionNum: int | None = self.inversion()
            if not self.inversionIsValid(inversionNum):
                # there is a bass, yet no normal inversion was found: must be added note
                inversionNum = None

                # arbitrary octave, must be below root,
                # which was arbitrarily chosen as 3 above
                self._overrides['bass'].octave = 2
                pitches.append(self._overrides['bass'])
        else:
            self.inversion(None, transposeOnSet=False)
            inversionNum = None

        pitches = self._adjustPitchesForChordStepModifications(pitches)

        if inversionNum not in (0, None):
            if t.TYPE_CHECKING:
                assert inversionNum is not None
            for p in pitches[0:inversionNum]:
                p.octave = p.octave + 1
                # Repeat if 9th/11th/13th chord in 4th inversion or greater
                if inversionNum > 3:
                    p.octave = p.octave + 1

            # if after bumping up the octaves, there are still pitches below bass pitch
            # bump up their octaves
            # bassPitch = pitches[inversionNum]

            # self.bass(bassPitch)
            for p in pitches:
                if p.diatonicNoteNum < self._overrides['bass'].diatonicNoteNum:
                    p.octave = p.octave + 1

        while self._hasPitchAboveC4(pitches):
            for thisPitch in pitches:
                thisPitch.octave -= 1

        # but if this has created pitches below lowest note (the A 3 octaves below middle C)
        # on a standard piano, we're going to have to bump all the octaves back up
        while self._hasPitchBelowA1(pitches):
            for thisPitch in pitches:
                thisPitch.octave += 1

        self.pitches = tuple(pitches)
        self.sortDiatonicAscending(inPlace=True)

        # set overrides to be pitches in the harmony
        # self._overrides = {}  # JTW: was wiping legit overrides such as root=C from 'C6'
        self.bass(self.bass(), allow_add=True)
        self.root(self.root())

    EXTRA_CHORD_KINDS: dict[str, str] = {
        'maj9': 'major-ninth',
        'sus47': 'suspended-fourth-seventh',
        'minMaj7': 'minor-major-seventh',
        '°': 'diminished',
        'augmented-ninth': 'augmented-dominant-ninth'
    }

    @staticmethod
    def fixupBadChordKinds(s: m21.stream.Stream, inPlace=False) -> m21.stream.Stream:
        fixme: m21.stream.Stream = s
        if not inPlace:
            fixme = deepcopy(s)

        for cs in fixme[m21.harmony.ChordSymbol]:
            if cs.chordKind in m21.harmony.CHORD_TYPES:
                # all good, check the next cs
                continue

            fixedIt: bool = False
            for k in m21.harmony.CHORD_TYPES:
                # maybe cs.chordKind is a known abbreviation?
                if cs.chordKind in m21.harmony.getAbbreviationListGivenChordType(k):
                    cs.chordKind = k
                    M21Utilities._updatePitches(cs)
                    fixedIt = True
                    break

            if fixedIt:
                # done with this bad cs, move on to the next one
                continue

            # we can also use our own lookup (on chordKind)
            if cs.chordKind in M21Utilities.EXTRA_CHORD_KINDS:
                cs.chordKind = M21Utilities.EXTRA_CHORD_KINDS[cs.chordKind]
                M21Utilities._updatePitches(cs)
                fixedIt = True

            if fixedIt:
                # done with this bad cs, move on to the next one
                continue

            for k in m21.harmony.CHORD_TYPES:
                # maybe cs.chordKindStr is a known abbreviation?
                if cs.chordKindStr in m21.harmony.getAbbreviationListGivenChordType(k):
                    cs.chordKind = k
                    M21Utilities._updatePitches(cs)
                    fixedIt = True
                    break

            if fixedIt:
                # done with this bad cs, move on to the next one
                continue

            # we can also use our own lookup (on chordKindStr)
            if cs.chordKindStr in M21Utilities.EXTRA_CHORD_KINDS:
                cs.chordKind = M21Utilities.EXTRA_CHORD_KINDS[cs.chordKindStr]
                M21Utilities._updatePitches(cs)
                fixedIt = True

            if fixedIt:
                # done with this bad cs, move on to the next one
                continue

            # Well-known chords that require (in music21) chord modifications
            # So far, cs.chordKind == 'maj69' is the only one.
            # It is ['1','3','5','6','9'], which is 'major-sixth' with add 9
            if cs.chordKind == 'maj69':
                cs.chordKind = 'major-sixth'
                cs.addChordStepModification(
                    m21.harmony.ChordStepModification(modType='add', degree=9)
                )
                M21Utilities._updatePitches(cs)
                fixedIt = True

            if fixedIt:
                continue

            # I have seen chords with chordKind == '/A' and chordKindStr == '/A',
            # meaning 'root' major chord with bass = 'A'.  I have also seen
            # 'min/A', meaning minor chord with bass = 'A'.  It will print as
            # {root}{chordKindStr}, so construct that and set it as cs.figure.
            # If parseable, cs.chordKind and cs.bass() will be set, and the
            # pitches reconstructed.  Then we trim the '/A' off the chordKindStr,
            # since that is added automatically, now that cs.bass() is set
            # correctly.
            # See "Stuart and Laughhelm - Mixed Emotions.mxl" for an example in
            # measure 2: root == 'A-', chordKindStr (and chordKind) == 'min/G'.
            if '/' in cs.chordKindStr:
                # figure it out
                if cs.root():
                    newFigure: str = cs.root().name + cs.chordKindStr
                    cs.figure = newFigure
                    # remove trailing '/blah' from cs.chordKindStr
                    slashIdx: int = cs.chordKindStr.index('/')
                    cs.chordKindStr = cs.chordKindStr[:slashIdx]
                    fixedIt = True

            if fixedIt:
                continue

        return fixme

    @staticmethod
    def fixupBadBeams(score: m21.stream.Score, inPlace=False) -> m21.stream.Score:
        # must be a score; we will look for parts/measures/etc

        # 1. Looks for continues that should be stops (given the Note
        # immediately following).  These are often seen in MusicXML, and while Finale
        # handles them, Musescore and converter21's converters (and musicdiff) do not.
        # 2. Looks (in 1-part scores only) for multiple stops in a row.  These are
        # fixed by converting all but the last to a continue.  1-part scores only
        # because cross-part beams can do this legitimately.  To detect that properly
        # is possible, but would require looking at all voices in a measure stack
        # simultaneously.

        fixme: m21.stream.Score = score
        if not inPlace:
            fixme = deepcopy(score)

        parts: list[m21.stream.Part] = list(fixme[m21.stream.Part])
        for part in parts:
            # key is previous voice.id (or 'measure' if it's the measure)
            lastNCInPrevVoice: dict[int | str, m21.note.NotRest] = {}
            measures: list[m21.stream.Measure] = list(part[m21.stream.Measure])
            for meas in measures:
                # we can only fix up beams within a Voice (or within the Measure
                # itself, if there are no Voices)
                voices: list[m21.stream.Voice | m21.stream.Measure] = list(
                    meas[m21.stream.Voice]
                )
                if not voices:
                    voices = [meas]

                for voice in voices:
                    voiceKey: int | str
                    if isinstance(voice, m21.stream.Measure):
                        voiceKey = 'measure'
                    else:
                        voiceKey = voice.id

                    notesAndChords: list[m21.note.NotRest] = list(voice[m21.note.NotRest])

                    # Remove any ChordSymbols (they are Chords that don't count)
                    # and any grace notes (they don't participate in the non-grace-note
                    # beaming).
                    removeList: list[m21.note.NotRest] = []
                    for nc in notesAndChords:
                        if isinstance(nc, m21.harmony.ChordSymbol):
                            removeList.append(nc)
                        elif nc.duration.isGrace:
                            removeList.append(nc)

                    for cs in removeList:
                        notesAndChords.remove(cs)

                    for i in range(0, len(notesAndChords)):
                        thisNC: m21.note.NotRest = notesAndChords[i]
                        prevNC: m21.note.NotRest | None
                        if i == 0:
                            prevNC = lastNCInPrevVoice.get(voiceKey) or None
                        else:
                            prevNC = notesAndChords[i - 1]

                        # prevNC is the one we are fixing (based on beams in thisNC)
                        if prevNC is None or not prevNC.beams:
                            # nothing to fix
                            continue

                        prevBeam: m21.beam.Beam
                        if not thisNC.beams:
                            # thisNC has no beams. Any continues in prevNC.beams should be stops.
                            for prevBeam in prevNC.beams:
                                if prevBeam.type == 'continue':
                                    prevBeam.type = 'stop'
                        else:
                            # thisNC has beams.  Check any/all of prevNC's beams.
                            for prevBeam in prevNC.beams:
                                num: int = prevBeam.number
                                if num not in thisNC.beams.getNumbers():
                                    # no matching beam in thisNC, prevBeam must stop,
                                    # not continue
                                    if prevBeam.type == 'continue':
                                        prevBeam.type = 'stop'
                                else:
                                    # matching beam in thisNC; if it starts, prevBeam
                                    # must stop, not continue.  If it stops, prevBeam
                                    # must continue, not stop (two stops in a row
                                    # is silly.)
                                    thisBeam = thisNC.beams.getByNumber(num)
                                    if thisBeam.type == 'start':
                                        if prevBeam.type == 'continue':
                                            prevBeam.type = 'stop'
                                    elif thisBeam.type == 'stop' and len(parts) == 1:
                                        # WE CAN ONLY DO THIS IF THERE IS ONLY ONE PART.
                                        # In cross-staff beaming, this code gets very
                                        # confused and makes things worse.
                                        if prevBeam.type == 'stop':
                                            prevBeam.type = 'continue'

                    if meas is measures[-1]:
                        # fix last note in score (in this voice)
                        # (if its a continue it should be a stop)
                        if notesAndChords:
                            lastNCInScore: m21.note.NotRest = notesAndChords[-1]
                            for beam in lastNCInScore.beams:
                                if beam.type == 'continue':
                                    beam.type = 'stop'
                    else:
                        # stash last voice note off to be fixed during processing of
                        # next measure (for this voice)
                        if notesAndChords:
                            lastNCInPrevVoice[voiceKey] = notesAndChords[-1]
                        else:
                            lastNCInPrevVoice.pop(voiceKey, None)

        return fixme

    @staticmethod
    def adjustMusic21Behavior() -> None:
        if 'augmented-ninth' not in m21.harmony.CHORD_ALIASES:
            m21.harmony.CHORD_ALIASES['augmented-ninth'] = 'augmented-dominant-ninth'
        if 'minor-major' not in m21.harmony.CHORD_ALIASES:
            m21.harmony.CHORD_ALIASES['minor-major'] = 'minor-major-seventh'
