# ------------------------------------------------------------------------------
# Name:          M21Utilities.py
# Purpose:       Utility functions for music21 objects
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021 Greg Chapman
# License:       BSD, see LICENSE
# ------------------------------------------------------------------------------

#    All methods are static.  M21Utilities is just a namespace for these conversion functions and
#    look-up tables.

# import sys
# import re
# from typing import Union
# from fractions import Fraction
import music21 as m21

# pylint: disable=protected-access

DEBUG = 0
TUPLETDEBUG = 1
BEAMDEBUG = 1

def durationWithTupletDebugReprInternal(self: m21.duration.Duration) -> str:
    output: str = 'dur.qL={}'.format(self.quarterLength)
    if len(self.tuplets) >= 1:
        tuplet: m21.duration.Tuplet = self.tuplets[0]
        output += ' tuplets[0]: ' + tuplet._reprInternal()
        output += ' bracket=' + str(tuplet.bracket)
        output += ' type=' + str(tuplet.type)
    return output

def noteDebugReprInternal(self: m21.note.Note) -> str:
    output = self.name
    if BEAMDEBUG and hasattr(self, 'beams') and self.beams:
        output += ' beams: ' + self.beams._reprInternal()
    if TUPLETDEBUG:
        output += ' ' + durationWithTupletDebugReprInternal(self.duration)
    return output

def unpitchedDebugReprInternal(self: m21.note.Unpitched) -> str:
    output = super()._reprInternal
    if BEAMDEBUG and hasattr(self, 'beams') and self.beams:
        output += ' beams: ' + self.beams._reprInternal()
    if TUPLETDEBUG:
        output += ' ' + durationWithTupletDebugReprInternal(self.duration)
    return output

def chordDebugReprInternal(self: m21.chord.Chord) -> str:
    if not self.pitches:
        return super()._reprInternal()

    allPitches = []
    for thisPitch in self.pitches:
        allPitches.append(thisPitch.nameWithOctave)

    output = ' '.join(allPitches)
    if BEAMDEBUG and hasattr(self, 'beams') and self.beams:
        output += ' beams: ' + self.beams._reprInternal()
    if TUPLETDEBUG:
        output += ' ' + durationWithTupletDebugReprInternal(self.duration)
    return output

def setDebugReprInternal(self, method):
    if DEBUG != 0:
        import types
        self._reprInternal = types.MethodType(method, self)

# pylint: disable=protected-access

class M21Utilities:

    @staticmethod
    def createNote(spannerHolder: m21.note.GeneralNote = None) -> m21.note.Note:
        note = m21.note.Note()

        # for debugging, override this note's _reprInternal so we can see any Beams.
        setDebugReprInternal(note, noteDebugReprInternal)

        # Now replace spannerHolder with note in every spanner that references it.
        # (This is for, e.g., slurs that were created before this note was there.)
        if spannerHolder:
            spanners = spannerHolder.getSpannerSites()
            for spanner in spanners:
                spanner.replaceSpannedElement(spannerHolder, note)

        return note

    @staticmethod
    def createUnpitched(spannerHolder: m21.note.GeneralNote = None) -> m21.note.Unpitched:
        unpitched = m21.note.Unpitched()

        # for debugging, override this unpitched's _reprInternal so we can see any Beams.
        setDebugReprInternal(unpitched, unpitchedDebugReprInternal)

        # Now replace spannerHolder with unpitched in every spanner that references it.
        # (This is for, e.g., slurs that were created before this unpitched was there.)
        if spannerHolder:
            spanners = spannerHolder.getSpannerSites()
            for spanner in spanners:
                spanner.replaceSpannedElement(spannerHolder, unpitched)

        return unpitched

    @staticmethod
    def createChord(spannerHolder: m21.note.GeneralNote = None) -> m21.chord.Chord:
        chord = m21.chord.Chord()

        # for debugging, override this chord's _reprInternal so we can see any Beams.
        setDebugReprInternal(chord, chordDebugReprInternal)

        # Now replace spannerHolder with chord in every spanner that references it.
        # (This is for, e.g., slurs that were created before this chord was there.)
        if spannerHolder:
            spanners = spannerHolder.getSpannerSites()
            for spanner in spanners:
                spanner.replaceSpannedElement(spannerHolder, chord)

        return chord

    @staticmethod
    def createRest(spannerHolder: m21.note.GeneralNote = None) -> m21.note.Rest:
        rest = m21.note.Rest()

        # for debugging, override this rest's _reprInternal so we can see any Beams.
        setDebugReprInternal(rest, noteDebugReprInternal)

        # Now replace spannerHolder with rest in every spanner that references it.
        # (This is for, e.g., slurs that were created before this rest was there.)
        if spannerHolder:
            spanners = spannerHolder.getSpannerSites()
            for spanner in spanners:
                spanner.replaceSpannedElement(spannerHolder, rest)

        return rest

    @staticmethod
    def getTextExpressionsFromGeneralNote(gnote: m21.note.GeneralNote) -> [m21.expressions.TextExpression]:
        pass

    @staticmethod
    def getDynamicWedgesFromGeneralNote(gnote: m21.note.GeneralNote) -> [m21.dynamics.DynamicWedge]:
        pass
