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
import typing as t

import music21 as m21
from music21.common.types import OffsetQL, OffsetQLIn, StepName

from converter21.humdrum import HumdrumInternalError

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
            if M21Utilities.m21SupportsArpeggioMarks():
                if isinstance(spanner, m21.expressions.ArpeggioMarkSpanner):  # type: ignore
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

    @staticmethod
    def pitchToBase7(m21Pitch: m21.pitch.Pitch) -> int:
        pc: int = M21Utilities._STEP_TO_PITCH_CLASS[m21Pitch.step]
        octave: int = m21Pitch.implicitOctave  # implicit means return default (4) if None
        return pc + (7 * octave)

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

    # to be used if music21 doesn't support spanner fill.
    @staticmethod
    def fillOttava(
        ottava: m21.spanner.Ottava,
        searchStream: m21.stream.Stream,
        *,
        includeEndBoundary: bool = False,
        mustFinishInSpan: bool = False,
        mustBeginInSpan: bool = True,
        includeElementsThatEndAtStart: bool = False
    ):
        if hasattr(ottava, 'filledStatus') and ottava.filledStatus is True:  # type: ignore
            # Don't fill twice.
            return

        if ottava.getFirst() is None:
            # no spanned elements?  Nothing to fill.
            return

        endElement: m21.base.Music21Object | None = None
        if len(ottava) > 1:
            # Start and end elements are different, we can't just append everything, we need
            # to save off the end element, remove it, add everything, then add the end element
            # again.  Note that if there are actually more than 2 elements before we start
            # filling, the new intermediate elements will come after the existing ones,
            # regardless of offset.  But first and last will still be the same two elements
            # as before, which is the most important thing.
            endElement = ottava.getLast()
            if t.TYPE_CHECKING:
                assert endElement is not None
            ottava.spannerStorage.remove(endElement)

        try:
            startOffsetInHierarchy: OffsetQL = ottava.getFirst().getOffsetInHierarchy(searchStream)
        except m21.sites.SitesException:
            # print('start element not in searchStream')
            if endElement is not None:
                ottava.addSpannedElements(endElement)
            return

        endOffsetInHierarchy: OffsetQL
        if endElement is not None:
            try:
                endOffsetInHierarchy = (
                    endElement.getOffsetInHierarchy(searchStream) + endElement.quarterLength
                )
            except m21.sites.SitesException:
                # print('end element not in searchStream')
                ottava.addSpannedElements(endElement)
                return
        else:
            endOffsetInHierarchy = (
                ottava.getLast().getOffsetInHierarchy(searchStream) + ottava.getLast().quarterLength
            )

        for foundElement in (searchStream
                .recurse()
                .getElementsByOffsetInHierarchy(
                    startOffsetInHierarchy,
                    endOffsetInHierarchy,
                    includeEndBoundary=includeEndBoundary,
                    mustFinishInSpan=mustFinishInSpan,
                    mustBeginInSpan=mustBeginInSpan,
                    includeElementsThatEndAtStart=includeElementsThatEndAtStart)
                .getElementsByClass(m21.note.NotRest)):
            if endElement is None or foundElement is not endElement:
                ottava.addSpannedElements(foundElement)

        if endElement is not None:
            # add it back in as the end element
            ottava.addSpannedElements(endElement)

        ottava.filledStatus = True  # type: ignore

    @staticmethod
    def m21VersionIsAtLeast(neededVersion: tuple[int, int, int, str]) -> bool:
        # m21.VERSION[0] * 10000 + m21.VERSION[1] * 100 + m21.VERSION[2]
        if len(m21.VERSION) == 0:
            raise HumdrumInternalError('music21 version must be set!')

        # compare element 0
        if m21.VERSION[0] < neededVersion[0]:
            return False
        if m21.VERSION[0] > neededVersion[0]:
            return True

        # element 0 is equal... go on to next element
        if len(m21.VERSION) == 1 or len(neededVersion) == 1:
            # there is no next element to compare, so we are done.
            # result is True only if m21 version has >= elements of needed version.
            # if neededVersion has more elements, then result is False
            return len(m21.VERSION) >= len(neededVersion)

        # compare element 1
        if m21.VERSION[1] < neededVersion[1]:
            return False
        if m21.VERSION[1] > neededVersion[1]:
            return True

        # element 1 is equal... go on to next element
        if len(m21.VERSION) == 2 or len(neededVersion) == 2:
            # there is no next element to compare, so we are done.
            # result is True only if m21 version has >= elements of needed version.
            # if neededVersion has more elements, then result is False
            return len(m21.VERSION) >= len(neededVersion)

        # compare element 2
        if m21.VERSION[2] < neededVersion[2]:
            return False
        if m21.VERSION[2] > neededVersion[2]:
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

    _cachedM21SupportsDublinCoreMetadata: bool | None = None
    @staticmethod
    def m21SupportsDublinCoreMetadata() -> bool:
        if M21Utilities._cachedM21SupportsDublinCoreMetadata is not None:
            return M21Utilities._cachedM21SupportsDublinCoreMetadata

        if hasattr(m21.metadata.Metadata, 'bestTitle'):
            M21Utilities._cachedM21SupportsDublinCoreMetadata = True
            return True

        M21Utilities._cachedM21SupportsDublinCoreMetadata = False
        return False

    _cachedM21SupportsArpeggioMarks: bool | None = None
    @staticmethod
    def m21SupportsArpeggioMarks() -> bool:
        if M21Utilities._cachedM21SupportsArpeggioMarks is not None:
            return M21Utilities._cachedM21SupportsArpeggioMarks

        if hasattr(m21.expressions, 'ArpeggioMark'):
            M21Utilities._cachedM21SupportsArpeggioMarks = True
            return True

        M21Utilities._cachedM21SupportsArpeggioMarks = False
        return False

    _cachedM21SupportsSpannerAnchor: bool | None = None
    @staticmethod
    def m21SupportsSpannerAnchor() -> bool:
        if M21Utilities._cachedM21SupportsSpannerAnchor is not None:
            return M21Utilities._cachedM21SupportsSpannerAnchor

        if hasattr(m21.spanner, 'SpannerAnchor'):
            M21Utilities._cachedM21SupportsSpannerAnchor = True
            return True

        M21Utilities._cachedM21SupportsSpannerAnchor = False
        return False

    _cachedM21SupportsSpannerFill: bool | None = None
    @staticmethod
    def m21SupportsSpannerFill() -> bool:
        if M21Utilities._cachedM21SupportsSpannerFill is not None:
            return M21Utilities._cachedM21SupportsSpannerFill

        if hasattr(m21.spanner.Spanner, 'fill'):
            M21Utilities._cachedM21SupportsSpannerFill = True
            return True

        M21Utilities._cachedM21SupportsSpannerFill = False
        return False

    _cachedM21SupportsDelayedTurns: bool | None = None
    @staticmethod
    def m21SupportsDelayedTurns() -> bool:
        if M21Utilities._cachedM21SupportsDelayedTurns is not None:
            return M21Utilities._cachedM21SupportsDelayedTurns

        if hasattr(m21.expressions.Turn, 'isDelayed'):
            M21Utilities._cachedM21SupportsDelayedTurns = True
            return True

        M21Utilities._cachedM21SupportsDelayedTurns = False
        return False


class M21StaffGroupTree:
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
    def __init__(self) -> None:
        # about this group description
        self.groupNum: int = 0
        self.symbol: str = 'none'       # see m21.layout.StaffGroup.symbol
        self.barTogether: bool = False  # see m21.layout.StaffGroup.barTogether
        # staves referenced by this group (includes staves in subgroups).
        # staffIndices is in staff order.
        self.staffIndices: list[int] = []
        # staves actually in this group (i.e. not in a subgroup).
        # ownedStaffIndices is in staff order.
        self.ownedStaffIndices: list[int] = []

        # tree links:
        # children == subgroups, parent = enclosing group (None for top)
        self.children: list[M21StaffGroupDescriptionTree] = []
        self.parent: M21StaffGroupDescriptionTree | None = None
