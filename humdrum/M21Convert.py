# ------------------------------------------------------------------------------
# Name:          M21Convert.py
# Purpose:       Conversion between HumdrumToken (etc) and music21 objects
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021 Greg Chapman
# License:       BSD, see LICENSE
# ------------------------------------------------------------------------------

#    All methods are static.  M21Convert is just a namespace for these conversion functions and
#    look-up tables.

from typing import Union
from fractions import Fraction
import music21 as m21

from humdrum import HumNum
from humdrum import HumdrumToken
from humdrum import Convert

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

class M21Convert:
    humdrumMensurationSymbolToM21TimeSignatureSymbol = {
        'c':    'common',   # modern common time (4/4)
        'c|':   'cut',      # modern cut time (2/2)
        'C':    'common',   # actually mensural-style common, but music21 doesn't know that one
        'C|':   'cut',      # actually mensural-style cut, but music21 doesn't know that one
#       'O':    '',        # mensural 'O' (not supported in music21)
#       'O|':   '',        # mensural 'cut O' (not supported in music21)
    }

    diatonicToM21PitchName = {
        0: 'C',
        1: 'D',
        2: 'E',
        3: 'F',
        4: 'G',
        5: 'A',
        6: 'B',
    }

    humdrumReferenceKeyToM21ContributorRole = {
        'COM': 'composer',
        'COA': 'attributed composer',
        'COS': 'suspected composer',
        'COL': 'composer alias',
        'COC': 'corporate composer',
        'LYR': 'lyricist',
        'LIB': 'librettist',
        'LAR': 'arranger',
        'LOR': 'orchestrator',
        'TRN': 'translator',
        'YOO': 'original document owner',
        'YOE': 'original editor',
        'EED': 'electronic editor',
        'ENC': 'electronic encoder'
    }

    humdrumDecoGroupStyleToM21GroupSymbol = {
        '{':    'brace',
        '[':    'bracket',
        '<':    'line',     # what is this one supposed to be, it's often ignored in iohumdrum.cpp
    }

    humdrumStandardKeyStringsToNumSharps = {
        '':                 0,
        'f#':               1,
        'f#c#':             2,
        'f#c#g#':           3,
        'f#c#g#d#':         4,
        'f#c#g#d#a#':       5,
        'f#c#g#d#a#e#':     6,
        'f#c#g#d#a#e#b#':   7,
        'b-':               -1,
        'b-e-':             -2,
        'b-e-a-':           -3,
        'b-e-a-d-':         -4,
        'b-e-a-d-g-':       -5,
        'b-e-a-d-g-c-':     -6,
        'b-e-a-d-g-c-f-':   -7,
    }

    humdrumModeToM21Mode = {
        'dor':  'dorian',
        'phr':  'phrygian',
        'lyd':  'lydian',
        'mix':  'mixolydian',
        'aeo':  'aeolian',
        'ion':  'ionian',
        'loc':  'locrian',
    }

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
    def m21Offset(humOffset: HumNum) -> Fraction:
        # music21 offsets can be Fraction, float, or str, specified in
        # quarter notes.  HumNum offsets are always a Fraction, and are
        # also specified in quarter notes.
        # We always produce a Fraction here, since that's what we have.
        return Fraction(humOffset)

    @staticmethod
    def m21PitchName(subTokenStr: str) -> str: # returns 'A#' for A sharp (ignores octave)
        diatonic: int = Convert.kernToDiatonicPC(subTokenStr) # PC == pitch class; ignores octave

        accidCount: int = 0
        for ch in subTokenStr:
            if ch == '#':
                accidCount += 1
            elif ch == '-':
                accidCount -= 1

        accidStr: str = ''
        if accidCount < 0:
            accidStr = '-' * (-accidCount)
        elif accidCount > 0:
            accidStr = '#' * accidCount

        return M21Convert.diatonicToM21PitchName[diatonic] + accidStr

    @staticmethod
    def m21PitchNameWithOctave(subTokenStr: str) -> str: # returns 'A#5' for A sharp in octave 5
        octaveNumber: int = Convert.kernToOctaveNumber(subTokenStr)
        octaveStr: str = ''

        if octaveNumber != -1000:
            octaveStr = str(octaveNumber)

        return M21Convert.m21PitchName(subTokenStr) + octaveStr

    @staticmethod
    def m21DurationWithTuplet(token: HumdrumToken, tuplet: m21.duration.Tuplet) -> m21.duration.Duration:
        durNoDots: HumNum = token.scaledDurationNoDots(token.rscale) / tuplet.tupletMultiplier()
        numDots: int = token.dotCount
        durType: str = m21.duration.convertQuarterLengthToType(Fraction(durNoDots))
        #print('m21DurationWithTuplet: type = "{}", dots={}'.format(durType, numDots))
        component: m21.duration.DurationTuple = m21.duration.durationTupleFromTypeDots(durType, numDots)
        output = m21.duration.Duration(components = (component,))
        output.tuplets = (tuplet,)
        return output

    @staticmethod
    def m21TimeSignature(timeSigToken: HumdrumToken, meterSigToken: HumdrumToken = None) -> m21.meter.TimeSignature:
        meterRatio: str = timeSigToken.timeSignatureRatioString
        timeSignature: m21.meter.TimeSignature = m21.meter.TimeSignature(meterRatio)

        # see if we can add symbol info (cut time, common time, whatever)
        if meterSigToken is not None:
            if meterSigToken.isMensurationSymbol or meterSigToken.isOriginalMensurationSymbol:
                meterSym: str = meterSigToken.mensurationSymbol
                if meterSym in M21Convert.humdrumMensurationSymbolToM21TimeSignatureSymbol:
                    timeSignature.symbol = \
                            M21Convert.humdrumMensurationSymbolToM21TimeSignatureSymbol[meterSym]

        return timeSignature

    @staticmethod
    def m21KeySignature(keySigToken: HumdrumToken, keyToken: HumdrumToken = None) -> Union[m21.key.KeySignature, m21.key.Key]:
        keySig = keySigToken.keySignature

        # ignore keySigToken if we have keyToken. keyToken has a lot more info.
        if keyToken:
            keyName, mode = keyToken.keyDesignation
            mode = M21Convert.humdrumModeToM21Mode.get(mode, None) # e.g. 'dor' -> 'dorian'
            return m21.key.Key(keyName, mode)

        # standard key signature in standard order (if numSharps is negative, it's -numFlats)
        if keySig in M21Convert.humdrumStandardKeyStringsToNumSharps:
            return m21.key.KeySignature(M21Convert.humdrumStandardKeyStringsToNumSharps[keySig])

        # non-standard key
        alteredPitches: [str] = [keySig[i:i+2].upper() for i in range(0, len(keySig), 2)]
        for pitch in alteredPitches:
            if pitch[0] not in 'ABCDEFG':
                # invalid accidentals in '*k[accidentals]'.
                # e.g. *k[X] as seen in rds-scores: R700_Cop-w2p64h38m3-10.krn
                return None

        output = m21.key.KeySignature()
        output.alteredPitches = alteredPitches
        return output

    @staticmethod
    def m21Clef(clefToken: HumdrumToken) -> m21.clef.Clef:
        clefStr: str = clefToken.clef # e.g. 'G2', 'Gv2', 'F4', 'C^^3', 'X', 'X2', etc
        if clefStr and clefStr[0] == '-':
            return m21.clef.NoClef()

        if clefStr and clefStr[0] == 'X':
            m21PercussionClef = m21.clef.clefFromString('percussion')
            if len(clefStr) > 1:
                m21PercussionClef.line = int(clefStr[1])
            return m21PercussionClef

        # not no clef, not a percussion clef, do the octave shift math
        clefStrNoShift: str = clefStr.replace('^', '').replace('v', '')
        octaveShift: int = clefStr.count('^')
        if octaveShift == 0:
            octaveShift = - clefStr.count('v')
        return m21.clef.clefFromString(clefStrNoShift, octaveShift)
