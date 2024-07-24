# ------------------------------------------------------------------------------
# Name:          M21Convert.py
# Purpose:       Conversion between HumdrumToken (etc) and music21 objects
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------

#    All methods are static.  M21Convert is just a namespace for these conversion functions and
#    look-up tables.

import sys
import re
import math
import typing as t
from fractions import Fraction

import music21 as m21
from music21.common import opFrac

from converter21.shared import SharedConstants
from converter21.humdrum import MeasureStyle, MeasureVisualStyle, MeasureType
from converter21.humdrum import FermataStyle
from converter21.humdrum import HumdrumInternalError
# from converter21.humdrum import HumdrumExportError
from converter21.humdrum import HumNum
from converter21.humdrum import HumdrumToken
from converter21.humdrum import Convert
from converter21.shared import M21Utilities


class M21Convert:
    humdrumMensurationSymbolToM21TimeSignatureSymbol: dict[str, str] = {
        'c': 'common',  # modern common time (4/4)
        'c|': 'cut',    # modern cut time (2/2)
        # 'C': '',      # mensural common (not supported in music21)
        # 'C|': '',     # mensural cut (2/1) (not supported in music21)
        # 'O': '',      # mensural 'O' (not supported in music21)
        # 'O|': '',     # mensural 'cut O' (not supported in music21)
    }

    m21TimeSignatureSymbolToHumdrumMensurationSymbol: dict[str, str] = {
        'common': 'c',  # modern common time (4/4)
        'cut': 'c|',    # modern cut time (2/2)
    }

    diatonicToM21PitchName: dict[int, str] = {
        0: 'C',
        1: 'D',
        2: 'E',
        3: 'F',
        4: 'G',
        5: 'A',
        6: 'B',
    }

    if hasattr(m21.common.types, 'StepName'):
        # same as diatonicToM21PitchName, but the values are typed as StepName
        diatonicToM21StepName: dict[int, m21.common.types.StepName] = {
            0: 'C',
            1: 'D',
            2: 'E',
            3: 'F',
            4: 'G',
            5: 'A',
            6: 'B',
        }

    humdrumReferenceKeyToEncodingScheme: dict[str, str] = {
        # Note that we only enter things in this dict that aren't free-form text (that's the
        # default). Note also that 'humdrum:date' covers all the ways humdrum encodes dates in
        # a string. The string might represent a single date, a pair of dates, or even a list
        # of dates.
        'CDT': 'humdrum:date',  # composer's birth and death dates (**zeit format)
        'RRD': 'humdrum:date',  # release date (**date format)
        'RDT': 'humdrum:date',  # date of recording (**date format)
        'MRD': 'humdrum:date',  # date of performance (**date format)
        'MPD': 'humdrum:date',  # date of first performance (**date format)
        'MDT': 'humdrum:date',  # unknown/I've seen 'em (another way to say date of performance?)
        'ODT': 'humdrum:date',  # date or period of composition (**date or **zeit format)
        'PDT': 'humdrum:date',  # date first published (**date format)
        'YER': 'humdrum:date',  # date electronic edition released
        'END': 'humdrum:date',  # encoding date
    }

    humdrumDecoGroupStyleToM21GroupSymbol: dict[str, str] = {
        '{': 'brace',
        '[': 'bracket',
        '<': 'square',   # what is this one supposed to be, it's often ignored in iohumdrum.cpp
    }

    m21GroupSymbolToHumdrumDecoGroupStyleStart: dict[str, str] = {
        'brace': '{',
        'bracket': '[',
        'square': '<',    # what is this one supposed to be, it's often ignored in iohumdrum.cpp
        'line': '',       # humdrum doesn't have line, but "no style" is close
    }

    m21GroupSymbolToHumdrumDecoGroupStyleStop: dict[str, str] = {
        'brace': '}',
        'bracket': ']',
        'square': '>',    # what is this one supposed to be, it's often ignored in iohumdrum.cpp
        'line': '',       # humdrum doesn't have line, but "no style" is close
    }

    humdrumStandardKeyStringsToNumSharps: dict[str, int] = {
        '': 0,
        'f#': 1,
        'f#c#': 2,
        'f#c#g#': 3,
        'f#c#g#d#': 4,
        'f#c#g#d#a#': 5,
        'f#c#g#d#a#e#': 6,
        'f#c#g#d#a#e#b#': 7,
        'b-': -1,
        'b-e-': -2,
        'b-e-a-': -3,
        'b-e-a-d-': -4,
        'b-e-a-d-g-': -5,
        'b-e-a-d-g-c-': -6,
        'b-e-a-d-g-c-f-': -7,
    }

    numSharpsToHumdrumStandardKeyStrings: dict[int, str] = {
        0: '',
        1: 'f#',
        2: 'f#c#',
        3: 'f#c#g#',
        4: 'f#c#g#d#',
        5: 'f#c#g#d#a#',
        6: 'f#c#g#d#a#e#',
        7: 'f#c#g#d#a#e#b#',
        8: 'f##c#g#d#a#e#b#',
        9: 'f##c##g#d#a#e#b#',
        10: 'f##c##g##d#a#e#b#',
        11: 'f##c##g##d##a#e#b#',
        12: 'f##c##g##d##a##e#b#',
        13: 'f##c##g##d##a##e##b#',
        14: 'f##c##g##d##a##e##b##',
        -1: 'b-',
        -2: 'b-e-',
        -3: 'b-e-a-',
        -4: 'b-e-a-d-',
        -5: 'b-e-a-d-g-',
        -6: 'b-e-a-d-g-c-',
        -7: 'b-e-a-d-g-c-f-',
        -8: 'b--e-a-d-g-c-f-',
        -9: 'b--e--a-d-g-c-f-',
        -10: 'b--e--a--d-g-c-f-',
        -11: 'b--e--a--d--g-c-f-',
        -12: 'b--e--a--d--g--c-f-',
        -13: 'b--e--a--d--g--c--f-',
        -14: 'b--e--a--d--g--c--f--',
    }

    humdrumModeToM21Mode: dict[str, str] = {
        'dor': 'dorian',
        'phr': 'phrygian',
        'lyd': 'lydian',
        'mix': 'mixolydian',
        'aeo': 'aeolian',
        'ion': 'ionian',
        'loc': 'locrian',
    }

    m21ModeToHumdrumMode: dict[str, str] = {
        'dorian': 'dor',
        'phrygian': 'phr',
        'lydian': 'lyd',
        'mixolydian': 'mix',
        'aeolian': 'aeo',
        'ionian': 'ion',
        'locrian': 'loc',
    }

    # place articulations in stacking order (nearest to furthest from note)
    humdrumArticulationStringToM21ArticulationClassName: dict[str, str] = {
        "'": 'Staccato',
        '`': 'Staccatissimo',
        '~': 'Tenuto',
        '^^': 'StrongAccent',
        '^': 'Accent',
        ',': 'BreathMark',
        'o': 'Harmonic',
        'v': 'UpBow',
        'u': 'DownBow',
        '"': 'Pizzicato'
    }

    m21ArticulationClassNameToHumdrumArticulationString: dict[str, str] = {
        'Staccato': "'",
        'Staccatissimo': '`',
        'Tenuto': '~',
        'StrongAccent': '^^',
        'Accent': '^',
        'BreathMark': ',',
        'Harmonic': 'o',
        'UpBow': 'v',
        'DownBow': 'u',
        'Pizzicato': '"',
    }

    @staticmethod
    def base40ToM21PitchName(b40: int) -> str:
        octave: int = b40 // 40
        diatonic: int = Convert.base40ToDiatonic(b40) % 7
        accidCount: int = Convert.base40ToAccidental(b40)
        accidStr: str = ''
        if accidCount < 0:
            accidStr = '-' * (-accidCount)
        elif accidCount > 0:
            accidStr = '#' * accidCount

        name = M21Convert.diatonicToM21PitchName[diatonic] + accidStr + str(octave)
        return name

    @staticmethod
    def base40ToM21Pitch(b40: int) -> m21.pitch.Pitch:
        name = M21Convert.base40ToM21PitchName(b40)
        return m21.pitch.Pitch(name)

    @staticmethod
    def m21PitchName(subTokenStr: str) -> str:
        # e.g. returns 'A#' for A sharp (ignores octave)
        diatonic: int = Convert.kernToDiatonicPC(subTokenStr)  # PC == pitch class; ignores octave
        if diatonic < 0:
            # no pitch here, it's an unpitched note without a note position
            return ''

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

    # pylint: disable=no-member
    if hasattr(m21.common.types, 'StepName'):
        @staticmethod
        def m21StepNameV8(subTokenStr: str) -> m21.common.types.StepName | None:
            # PC == pitch class; ignores octave
            diatonic: int = Convert.kernToDiatonicPC(subTokenStr)
            if diatonic < 0:
                # no pitch here, it's an unpitched note without a note position
                return None

            return M21Convert.diatonicToM21StepName[diatonic]
    # pylint: enable=no-member

    # We can remove the following (and unconditionalize and rename m21StepNameV8)
    # once we no longer need to support music21 v7
    @staticmethod
    def m21StepName(subTokenStr: str) -> str | None:
        # e.g. returns 'A' for A sharp (ignores octave and accidental)
        diatonic: int = Convert.kernToDiatonicPC(subTokenStr)  # PC == pitch class; ignores octave
        if diatonic < 0:
            # no pitch here, it's an unpitched note without a note position
            return None

        return M21Convert.diatonicToM21PitchName[diatonic]

    @staticmethod
    def m21PitchNameWithOctave(subTokenStr: str) -> str:
        # e.g. returns 'A#5' for A sharp in octave 5
        octaveNumber: int = Convert.kernToOctaveNumber(subTokenStr)
        octaveStr: str = ''

        if octaveNumber != -1000:
            octaveStr = str(octaveNumber)

        return M21Convert.m21PitchName(subTokenStr) + octaveStr

    @staticmethod
    def getM21ChordSymFromHarmonyText(
        tokenStr: str,
        dataType: str = '**mxhm'
    ) -> m21.harmony.ChordSymbol | None:
        if dataType not in ('**mxhm', '**harte'):
            print('Harmony type "{dataType}" not supported, skipping.', file=sys.stderr)
            return None

        if dataType == '**harte':
            return M21Utilities.makeChordSymbolFromHarte(tokenStr)

        # ----- **mxhm -----
#         def replace(text: str, oldPatt: str, new: str) -> tuple[str, bool]:
#             # returns new text and whether or not any change was made
#             newText: str = re.sub(oldPatt, new, text)
#             return newText, newText != text

        if tokenStr == 'none':
            return m21.harmony.NoChord()

        # mxhm data is of the form '<root> <chord-type>', where root is '<A..G><#|-> and
        # kind is things like 'major', 'minor-seventh', etc.
        strings: list[str] = tokenStr.split()
        root: str = strings[0]
        kind: str = ''
        if len(strings) > 1:
            kind = strings[1]
        bass: str = ''

        if not root:
            print(f'malformed **mxhm harmony: skipping "{tokenStr}"', file=sys.stderr)
            return None

        if '/' in kind:
            # there's a specified bass note (e.g. 'C major/D')
            kindAndBass: list[str] = kind.split('/')
            if len(kindAndBass) != 2:
                print(f'malformed **mxhm harmony: skipping "{tokenStr}"', file=sys.stderr)
                return None
            kind = kindAndBass[0]
            bass = kindAndBass[1]

        # convert from MusicXML/Humdrum kind to music21 kind ('dominant' -> 'dominant-seventh')
#         kindStr: str = kind  # stash off original kind to make a kindStr (printed) string from
        if kind in m21.harmony.CHORD_ALIASES:
            kind = m21.harmony.CHORD_ALIASES[kind]
        if kind not in m21.harmony.CHORD_TYPES:
            print(f'malformed **mxhm harmony: skipping "{tokenStr}"', file=sys.stderr)
            return None

        # We need to make up a kindStr (e.g. 'm7'), similar to what verovio's
        # Humdrum importer does.
#         if kindStr == 'major-minor':
#             kindStr = 'Mm7'
#         elif kindStr == 'minor-major':
#             kindStr = 'mM7'
#
#         changed: bool
#         kindStr, changed = replace(kindStr, 'major-', 'maj')
#         if not changed:
#             kindStr, changed = replace(kindStr, 'minor-', 'm')
#         if not changed:
#             kindStr, changed = replace(kindStr, 'dominant-', 'dom')
#         if not changed:
#             kindStr, changed = replace(kindStr, 'augmented-', '+')
#         if not changed:
#             kindStr, changed = replace(kindStr, 'suspended-', 'sus')
#         if not changed:
#             kindStr, changed = replace(kindStr, 'diminished-', '\u00B0')  # degree sign
#
#         kindStr, changed = replace(kindStr, 'seventh', '7')
#         if not changed:
#             kindStr, changed = replace(kindStr, 'ninth', '9')
#         if not changed:
#             kindStr, changed = replace(kindStr, '11th', '11')
#         if not changed:
#             kindStr, changed = replace(kindStr, '13th', '13')
#         if not changed:
#             kindStr, changed = replace(kindStr, 'second', '2')
#         if not changed:
#             kindStr, changed = replace(kindStr, 'fourth', '4')
#         if not changed:
#             kindStr, changed = replace(kindStr, 'sixth', '6')
#
#         if kindStr in ('major', 'maj', 'ma'):
#             kindStr = ''
#         elif kindStr in ('minor', 'min'):
#             kindStr = 'm'
#         elif kindStr == 'augmented':
#             kindStr = '+'
#         elif kindStr == 'minor-seventh':
#             # I suspect this has already been accomplished above
#             kindStr = 'm7'
#         elif kindStr == 'major-seventh':
#             # I suspect this has already been accomplished above
#             kindStr = 'maj7'
#         elif kindStr == 'dom11':
#             kindStr = '11'
#         elif kindStr == 'dom13':
#             kindStr = '13'
#         elif kindStr == 'dom9':
#             kindStr = '9'
#         elif kindStr == 'half-diminished':
#             kindStr = '\u00F8'  # o-slash
#         elif kindStr == 'diminished':
#             kindStr = '\u00B0'  # degree sign
#         elif kindStr == 'dominant':
#             kindStr = '7'
#         elif kindStr == 'power':
#             kindStr = '5'
#         elif kindStr == 'm7b5':
#             kindStr = 'm7' + '\u266d' + '5'  # unicode flat

#         output = m21.harmony.ChordSymbol(bass=bass, root=root, kind=kind, kindStr=kindStr)
        output = m21.harmony.ChordSymbol(bass=bass, root=root, kind=kind)
        M21Utilities.simplifyChordSymbol(output)
        text: str = output.findFigure()
        text = M21Utilities.convertChordSymbolFigureToPrintableText(
            text, removeNoteNames=True
        )
        if text:
            output.chordKindStr = text

        return output

    @staticmethod
    def m21ChordSymToHarmonyText(
        cs: m21.harmony.ChordSymbol,
        dataType: str = '**mxhm',
        noResult: str = ''
    ) -> str:
        if dataType not in ('**mxhm', '**harte'):
            raise HumdrumInternalError('Harmony type "{dataType}" not supported')

        if dataType == '**harte':
            return M21Utilities.makeHarteFromChordSymbol(cs, noResult=noResult)

        root: str = ''
        csRoot: m21.pitch.Pitch | None = cs.root()
        if csRoot is not None:
            root = csRoot.name

        kind: str = cs.chordKind or ''
        # reverse alias kind back into MusicXML/Humdrum-land ('dominant-seventh' -> 'dominant')
        for alias in m21.harmony.CHORD_ALIASES:
            if m21.harmony.CHORD_ALIASES[alias] == kind:
                kind = alias

        bass: str = ''
        csBass: m21.pitch.Pitch | None = cs.bass()
        if csBass is not None and csBass.name != root:
            bass = csBass.name

        output: str = root
        if root and kind:
            output += ' '
        output += kind

        if bass:
            output += '/' + bass

        if not output:
            return noResult

        return output


    @staticmethod
    def m21Articulations(
        tokenStr: str,
        rdfAbove: str,
        rdfBelow: str
    ) -> list[m21.articulations.Articulation]:
        # music21 doesn't have different articulation lists per note in a chord, just a single
        # articulation list for the chord itself.  So we search the entire tokenStr for
        # articulations, and add them all to the chord.  This works for non-chord (note) tokens
        # as well.
        # store info about articulations in various dicts, keyed by humdrum articulation string
        # which is usually a single character, but can be two (e.g. '^^')
        articFound: dict[str, bool] = {}
        articPlacement: dict[str, str] = {}  # value is 'below', 'above', or ''
        # gestural means "not printed on the page, but it's what the performer did/should do"
        articIsGestural: dict[str, bool] = {}

        tsize: int = len(tokenStr)
        ch: str = ''
        ch1: str = ''
        ch2: str = ''
        ch3: str = ''
        skipNChars: int = 0

        for i in range(0, tsize):
            if skipNChars:
                skipNChars -= 1
                continue

            ch = tokenStr[i]
            if ch.isdigit():
                continue

            ch1 = ''
            if i + 1 < tsize:
                ch1 = tokenStr[i + 1]
            if ch == '^' and ch1 == '^':
                ch = '^^'
                ch1 = ''
                skipNChars = 1
                if i + skipNChars + 1 < tsize:
                    ch1 = tokenStr[i + skipNChars + 1]
            elif ch == "'" and ch1 == "'":
                # staccatissimo alternate (eventually remove)
                ch = '`'
                ch1 = ''
                skipNChars = 1
                if i + skipNChars + 1 < tsize:
                    ch1 = tokenStr[i + skipNChars + 1]

# TODO: merge new iohumdrum.cpp changes --gregc 01July2021
#         else if ((ch == '~') && (posch == '~')) {
#             // textual tenuto
#             textTenuto = true;
#             ++i;
#             posch = i < tsize - 1 ? token->at(i + 1) : 0;
#             if (m_signifiers.below && (posch == m_signifiers.below)) {
#                 textTenutoBelow = true;
#             }
#             continue;
#         }
#         if (m_signifiers.verticalStroke == ch) {
#             // use 7 slot in array for vertical strokes
#             ch = 7;
#         }

            # this will include a bunch of non-articulation characters as well, but we
            # will only look for the ones we know, below.
            articFound[ch] = True
            articIsGestural[ch] = False
            articPlacement[ch] = ''

            if ch1:
                # check for gestural (hidden) articulations
                ch2 = ''
                if i + skipNChars + 2 < tsize:
                    ch2 = tokenStr[i + skipNChars + 2]
                ch3 = ''
                if i + skipNChars + 3 < tsize:
                    ch3 = tokenStr[i + skipNChars + 3]

                if ch1 == 'y' and ch2 != 'y':
                    articIsGestural[ch] = True
                elif rdfAbove and ch1 == rdfAbove \
                        and ch2 == 'y' and ch3 != 'y':
                    articIsGestural[ch] = True
                elif rdfBelow and ch1 == rdfBelow \
                        and ch2 == 'y' and ch3 != 'y':
                    articIsGestural[ch] = True

            if rdfAbove and ch1 == rdfAbove:
                articPlacement[ch] = 'above'
            elif rdfBelow and ch1 == rdfBelow:
                articPlacement[ch] = 'below'

# TODO: merge new iohumdrum.cpp changes --gregc 01July2021
#     if (textTenuto) {
#         std::string text = "ten.";
#         std::string placement = "above";
#         if (textTenutoBelow) {
#             placement = "below";
#         }
#         bool bold = false;
#         bool italic = true;
#         int justification = 0;
#         std::string color = "";
#         int vgroup = 0;
#         int staffindex = m_rkern[token->getTrack()];
#         addDirection(text, placement, bold, italic, token,
#             staffindex, justification, color, vgroup);
#     }

        artics: list[m21.articulations.Articulation] = []

        for humdrumArticString in M21Convert.humdrumArticulationStringToM21ArticulationClassName:
            if articFound.get(humdrumArticString, False):
                m21ArticClassName: str = (
                    M21Convert.humdrumArticulationStringToM21ArticulationClassName[
                        humdrumArticString
                    ]
                )
                m21ArticClass = getattr(m21.articulations, m21ArticClassName)
                if m21ArticClass is None:
                    continue
                m21Artic = m21ArticClass()
                if m21Artic is None:
                    continue
                placement: str = articPlacement[humdrumArticString]
                if placement:
                    m21Artic.placement = placement

                # Rather than making gestural articulations invisible, just leave them out.
                # This sucks a bit, but matches verovio.  I'll fix this when they do.
                if not articIsGestural[humdrumArticString]:
                    artics.append(m21Artic)

                # Here's how it should be done
                # if articIsGestural[humdrumArticString]:
                #     m21Artic.style.hideObjectOnPrint = True
                # artics.append(m21Artic)

        return artics

    @staticmethod
    def m21DurationWithTuplet(
        token: HumdrumToken,
        tuplet: m21.duration.Tuplet
    ) -> m21.duration.Duration:
        vdurStr: str = token.getVisualDuration()
        vdur: HumNum | None = None
        vdurNoDots: HumNum | None = None
        vdurNumDots: int | None = None
        vdurType: str | None = None
        if vdurStr:
            # New policy: visual durations in Humdrum files do not follow the tupletiness
            # of the gestural duration.  Rather, they are either non-tuplety, or they have
            # their own tupletiness (which then has to match the tupletiness of the gestural
            # duration).  So we only use tupletMultipler on them if they are not already
            # a power of two with dots.
            vdur = Convert.recipToDuration(vdurStr)
            if t.TYPE_CHECKING:
                assert vdur is not None
            if not M21Utilities.isPowerOfTwoWithDots(vdur):
                vdur = opFrac(vdur / tuplet.tupletMultiplier())
            vdurNoDots, vdurNumDots = M21Utilities.computeDurationNoDotsAndNumDots(vdur)
            if vdurNumDots is None:
                print(f'Cannot figure out vDurNoDots + vDurNumDots from {vdurStr} (on '
                      + f'line number {token.lineNumber}), ignoring'
                      'visual duration', file=sys.stderr)
            else:
                vdurType = m21.duration.convertQuarterLengthToType(vdurNoDots)

        dur: HumNum = opFrac(token.duration / tuplet.tupletMultiplier())
        durNoDots: HumNum
        numDots: int | None
        durNoDots, numDots = M21Utilities.computeDurationNoDotsAndNumDots(dur)
        if numDots is None:
            print(f'Cannot figure out durNoDots + numDots from {token.text} (on '
                    + f'line number {token.lineNumber}), tuplet={tuplet}, about to '
                    + 'crash in convertQuarterLengthToType()...', file=sys.stderr)

        component: m21.duration.DurationTuple
        if vdurType:
            component = m21.duration.durationTupleFromTypeDots(vdurType, vdurNumDots)
        else:
            durType: str = m21.duration.convertQuarterLengthToType(durNoDots)
            component = m21.duration.durationTupleFromTypeDots(durType, numDots)

        output = m21.duration.Duration(components=(component,))
        output.tuplets = (tuplet,)

        if vdurType:
            output.linked = False
            output.quarterLength = opFrac(token.duration)

        return output

    @staticmethod
    def m21TimeSignature(
        timeSigToken: HumdrumToken,
        meterSigToken: HumdrumToken | None = None
    ) -> m21.meter.TimeSignature:
        meterRatio: str = timeSigToken.timeSignatureRatioString
        timeSignature: m21.meter.TimeSignature = m21.meter.TimeSignature(meterRatio)

        # see if we can add symbol info (cut time, common time, whatever)
        if meterSigToken is not None:
            if meterSigToken.isMensurationSymbol or meterSigToken.isOriginalMensurationSymbol:
                meterSym: str = meterSigToken.mensurationSymbol
                if meterSym in M21Convert.humdrumMensurationSymbolToM21TimeSignatureSymbol:
                    timeSignature.symbol = (
                        M21Convert.humdrumMensurationSymbolToM21TimeSignatureSymbol[meterSym]
                    )

        return timeSignature

    @staticmethod
    def m21KeySignature(
        keySigToken: HumdrumToken,
        keyToken: HumdrumToken | None = None
    ) -> m21.key.KeySignature | m21.key.Key | None:
        keySig = keySigToken.keySignature

        m21Key: m21.key.Key | None = None
        m21KeySig: m21.key.KeySignature | None = None

        # pre-process keysigs like '*k[bnenf#c#]'
        # (weird, but the chopin scores sometimes have these)
        if 'n' in keySig:
            keySig = keySig.replace('an', '')
            keySig = keySig.replace('bn', '')
            keySig = keySig.replace('cn', '')
            keySig = keySig.replace('dn', '')
            keySig = keySig.replace('en', '')
            keySig = keySig.replace('fn', '')
            keySig = keySig.replace('gn', '')

        # standard key signature in standard order (if numSharps is negative, it's -numFlats)
        if keySig in M21Convert.humdrumStandardKeyStringsToNumSharps:
            m21KeySig = m21.key.KeySignature(
                M21Convert.humdrumStandardKeyStringsToNumSharps[keySig]
            )

        if m21KeySig is None:
            # try non-standard key sig
            badKeySig: bool = False
            alteredPitches: list[str] = [
                keySig[i:i + 2].upper() for i in range(0, len(keySig), 2)
            ]
            for pitch in alteredPitches:
                if pitch[0] not in 'abcdefg':
                    # invalid accidentals in '*k[accidentals]'.
                    # e.g. *k[X] as seen in rds-scores: R700_Cop-w2p64h38m3-10.krn
                    badKeySig = True
                    break

            if not badKeySig:
                m21KeySig = m21.key.KeySignature()
                m21KeySig.alteredPitches = alteredPitches
                return m21KeySig  # there's no m21Key that will match a non-standard key sig


        # m21KeySig is most reliable, but m21Key will have a lot more info if we can trust it.
        # We will trust it if we have no m21KeySig (of course), or it has the same number of
        # sharps/flats as m21KeySig.
        if keyToken is not None:
            keyName: str | None
            mode: str | None
            keyName, mode = keyToken.keyDesignation
            if keyName:
                if mode is not None:
                    # e.g. 'dor' -> 'dorian'
                    mode = M21Convert.humdrumModeToM21Mode.get(mode, None)
                m21Key = m21.key.Key(keyName, mode)
                if m21KeySig is not None and m21Key.sharps != m21KeySig.sharps:
                    # nope, can't trust it
                    m21Key = None

        # return m21Key if we trust it, else return m21KeySig (always trusted)
        if m21Key is not None:
            return m21Key
        return m21KeySig

    @staticmethod
    def m21Clef(clefToken: HumdrumToken) -> m21.clef.Clef:
        clefStr: str = clefToken.clef  # e.g. 'G2', 'Gv2', 'F4', 'C^^3', 'X', 'X2', etc
        if clefStr and clefStr[0] == '-':
            return m21.clef.NoClef()

        if clefStr and clefStr[0] == 'X':
            m21PercussionClef = m21.clef.clefFromString('percussion')
            if len(clefStr) > 1:
                m21PercussionClef.line = int(clefStr[1])
            return m21PercussionClef

        # not no clef, not a percussion clef, do the octave shift math
        # but first remove any weird characters (not in 'GFC^v12345')
        # because that's what iohumdrum.cpp:insertClefElement ends up doing
        # (it just ignores them by searching for whatever it is looking for).
        # This is particularly for supporting things like '*clefF-4' as an
        # alternate spelling for '*clefF4'.

        # For now, I'm just going to delete any '-'s I see. --gregc
        clefStr = clefStr.replace('-', '')
        clefStrNoShift: str = clefStr.replace('^', '').replace('v', '')
        octaveShift: int = clefStr.count('^')
        if octaveShift == 0:
            octaveShift = - clefStr.count('v')
        return m21.clef.clefFromString(clefStrNoShift, octaveShift)

    @staticmethod
    def m21IntervalFromTranspose(transpose: str) -> m21.interval.Interval | None:
        dia: int | None
        chroma: int | None
        dia, chroma = Convert.transToDiatonicChromatic(transpose)
        if dia is None or chroma is None:
            return None  # we couldn't parse transpose string
        if dia == 0 and chroma == 0:
            return None  # this is a no-op transposition, so ignore it

        # diatonic step count can be used as a generic interval type here if
        # shifted 1 away from zero (because a diatonic step count of 1 is a
        # generic 2nd, for example).
        if dia < 0:
            dia -= 1
        else:
            dia += 1

        return m21.interval.intervalFromGenericAndChromatic(dia, chroma)

    @staticmethod
    def humdrumTransposeStringFromM21Interval(interval: m21.interval.Interval) -> str | None:
        if interval.generic is None:
            return None

        chroma: int = int(interval.semitones)
        dia: int = interval.generic.value

        # diatonic step count is generic interval type shifted 1 closer to 0
        if dia < 0:
            dia += 1
        else:
            dia -= 1
        return Convert.diatonicChromaticToTrans(dia, chroma)

    @staticmethod
    def m21FontStyleFromFontStyle(fontStyle: str) -> str:
        if fontStyle == 'bold-italic':
            return 'bolditalic'
        if fontStyle == 'normal-italic':
            return 'italic'
        return fontStyle

    '''
        Everything below this line converts from M21 to humdrum

        kernTokenStringFromBlah APIs actually return two things: the kernTokenString and an
        optional list of layout strings (which will need to be inserted before the token).
        The kernPostfix, kernPrefix, and kernPostfixAndPrefix APIs also return an additional
        optional list of layout strings.
    '''

    @staticmethod
    def kernTokenStringAndLayoutsFromM21GeneralNote(
        m21GeneralNote: m21.Music21Object,
        spannerBundle: m21.spanner.SpannerBundle,
        owner=None
    ) -> tuple[str, list[str]]:
        # this method can take any Music21Object, but only GeneralNotes return
        # anything interesting.
        if isinstance(m21GeneralNote, m21.note.Note):
            return M21Convert.kernTokenStringAndLayoutsFromM21Note(
                m21GeneralNote, spannerBundle, owner
            )

        if isinstance(m21GeneralNote, m21.note.Rest):
            return M21Convert.kernTokenStringAndLayoutsFromM21Rest(
                m21GeneralNote, spannerBundle, owner
            )

        if isinstance(m21GeneralNote, m21.chord.Chord):
            return M21Convert.kernTokenStringAndLayoutsFromM21Chord(
                m21GeneralNote, spannerBundle, owner
            )

        if isinstance(m21GeneralNote, m21.note.Unpitched):
            return M21Convert.kernTokenStringAndLayoutsFromM21Unpitched(
                m21GeneralNote, spannerBundle, owner
            )

        # Not a GeneralNote (Chord, Note, Rest, Unpitched).
        return ('', [])

    @staticmethod
    def kernPitchFromM21Unpitched(m21Unpitched: m21.note.Unpitched, owner=None) -> str:
        output: str = 'R'

        if m21Unpitched.displayOctave == 4 and m21Unpitched.displayStep == 'B':
            # these are default positions (mid-line treble clef), and should not
            # be treated as explicit in the resulting kern token
            return output

        output += M21Convert.kernPitchFromM21OctaveAndStep(m21Unpitched.displayOctave,
                                                            m21Unpitched.displayStep,
                                                            owner)
        return output

    @staticmethod
    def kernPitchFromM21OctaveAndStep(m21Octave: int, m21Step: str, _owner) -> str:
        output: str = ''
        pitchName: str = m21Step
        pitchNameCount: int
        if m21Octave > 3:
            pitchName = m21Step.lower()
            pitchNameCount = m21Octave - 3
        else:
            pitchName = m21Step.upper()
            pitchNameCount = 4 - m21Octave

        for _ in range(0, pitchNameCount):
            output += pitchName

        return output

    @staticmethod
    def kernRecipAndGraceTypeFromGeneralNote(
        m21GeneralNote: m21.note.GeneralNote
    ) -> tuple[str, str, str]:
        # returns (recip, vdurRecip, graceType)
        recip: str = ''
        vdurRecip: str = ''
        graceType: str = ''
        recip, vdurRecip = M21Convert.kernRecipFromM21Duration(m21GeneralNote.duration)
        graceType = M21Convert.kernGraceTypeFromM21Duration(m21GeneralNote.duration)
        if (graceType
                and hasattr(m21GeneralNote, 'stemDirection')
                and m21GeneralNote.stemDirection == 'noStem'):  # type: ignore
            # grace notes with no stem are encoded in Humdrum as grace notes with no recip
            recip = ''
        return recip, vdurRecip, graceType

    @staticmethod
    def kernTokenStringAndLayoutsFromM21Unpitched(
        m21Unpitched: m21.note.Unpitched,
        spannerBundle: m21.spanner.SpannerBundle,
        owner=None
    ) -> tuple[str, list[str]]:
        prefix: str = ''
        recip: str = ''
        vdurRecip: str = ''
        graceType: str = ''
        recip, vdurRecip, graceType = M21Convert.kernRecipAndGraceTypeFromGeneralNote(m21Unpitched)
        pitch: str = M21Convert.kernPitchFromM21Unpitched(m21Unpitched, owner)
        postfix: str = ''
        layouts: list[str] = []
        prefix, postfix, layouts = M21Convert.kernPrefixPostfixAndLayoutsFromM21GeneralNote(
            m21Unpitched,
            recip,
            spannerBundle,
            isFirstNoteInChord=False,
            isStandaloneNote=True,
            owner=owner
        )

        if vdurRecip and postfix.count('@@') == 2:
            # we have a fingered tremolo, so a portion of visual duration doubles the actual
            # duration to make music21 do the right thing visually with a fingered tremolo.
            # We must undo this factor of 2.
            vdur: HumNum = opFrac(Convert.recipToDuration(vdurRecip) / 2)
            m21VDur: m21.duration.Duration = m21.duration.Duration(vdur)
            vdurRecip = M21Convert.kernRecipFromM21Duration(m21VDur)[0]
            if vdurRecip == recip:
                vdurRecip = ''

        token: str = prefix + recip + graceType + pitch + postfix

        if vdurRecip:
            layouts.append('!LO:N:vis=' + vdurRecip)

        return (token, layouts)

    @staticmethod
    def kernTokenStringAndLayoutsFromM21Rest(
        m21Rest: m21.note.Rest,
        spannerBundle: m21.spanner.SpannerBundle,
        owner=None
    ) -> tuple[str, list[str]]:
        pitch: str = 'r'  # "pitch" of a rest is 'r'
        recip: str = ''
        vdurRecip: str = ''
        graceType: str = ''
        recip, vdurRecip, graceType = M21Convert.kernRecipAndGraceTypeFromGeneralNote(m21Rest)
        prefixPostfixAndLayouts: tuple[str, str, list[str]] = (
            M21Convert.kernPrefixPostfixAndLayoutsFromM21Rest(
                m21Rest,
                recip,
                spannerBundle,
                owner)
        )
        prefix: str = prefixPostfixAndLayouts[0]
        postfix: str = prefixPostfixAndLayouts[1]
        layouts: list[str] = prefixPostfixAndLayouts[2]

        token: str = prefix + recip + graceType + pitch + postfix

        if vdurRecip:
            layouts.append('!LO:N:vis=' + vdurRecip)

        return (token, layouts)

    @staticmethod
    def kernPrefixPostfixAndLayoutsFromM21Rest(
        m21Rest: m21.note.Rest,
        recip: str,
        spannerBundle: m21.spanner.SpannerBundle,
        owner=None
    ) -> tuple[str, str, list[str]]:
        prefix: str = ''
        postfix: str = ''
        layouts: list[str] = []

        # rest postfix possibility 0: fermata
        exprStr: str
        expressionLayouts: list[str]
        exprStr, expressionLayouts = M21Convert._getHumdrumStringAndLayoutsFromM21Expressions(
            m21Rest.expressions,
            m21Rest,
            recip,
            owner=owner
        )
        postfix += exprStr
        layouts += expressionLayouts

        # rest postfix possibility 1: pitch (for vertical positioning)
        if m21Rest.stepShift != 0:
            # postfix needs a pitch that matches the stepShift
            clef: m21.clef.Clef | None = m21Rest.getContextByClass(m21.clef.Clef)
            if t.TYPE_CHECKING:
                # This is just a mypy-visible assertion that clef has a lowestLine
                # attribute. We check at runtime for lowestLine existence, but mypy
                # doesn't notice that, so we do this here to get mypy to shut up.
                # Note that PitchClef is not the only type of clef that has lowestLine,
                # but it's sufficient for this check (because we check at runtime below).
                assert isinstance(clef, m21.clef.PitchClef)
            if clef is not None and hasattr(clef, 'lowestLine'):
                baseline: int = clef.lowestLine
                midline: int = baseline + 4  # TODO: handle other than 5-line staves
                pitchNum: int = midline + m21Rest.stepShift
                # m21 pitch numbers (e.g. clef.lowestLine) are base7 + 1 for some reason
                # (despite documentation saying that C0 == 0) so subtract 1 before passing
                # to base7 APIs
                kernPitch: str = Convert.base7ToKern(pitchNum - 1)
                postfix += kernPitch

        # rest postfix possibility 2: invisibility
        postfix += M21Convert._getKernInvisibilityFromGeneralNote(m21Rest)

        # prefix/postfix possibility: slurs
        slurStarts: str = ''
        slurStops: str = ''
        slurStarts, slurStops = (
            M21Convert._getKernSlurStartsAndStopsFromGeneralNote(m21Rest, spannerBundle)
        )
        prefix = slurStarts + prefix  # prepend to prefix for readability
        postfix += slurStops

        return (prefix, postfix, layouts)

    @staticmethod
    def kernTokenStringAndLayoutsFromM21Note(
        m21Note: m21.note.Note,
        spannerBundle: m21.spanner.SpannerBundle,
        owner=None
    ) -> tuple[str, list[str]]:
        recip: str = ''
        vdurRecip: str = ''
        graceType: str = ''
        recip, vdurRecip, graceType = M21Convert.kernRecipAndGraceTypeFromGeneralNote(m21Note)
        pitch: str = M21Convert.kernPitchFromM21Pitch(m21Note.pitch, owner)
        prefix: str = ''
        postfix: str = ''
        layouts: list[str] = []
        prefix, postfix, layouts = M21Convert.kernPrefixPostfixAndLayoutsFromM21GeneralNote(
            m21Note,
            recip,
            spannerBundle,
            isFirstNoteInChord=False,
            isStandaloneNote=True,
            owner=owner
        )

        if vdurRecip and postfix.count('@@') == 2:
            # we have a fingered tremolo, so a portion of visual duration doubles the actual
            # duration to make music21 do the right thing visually with a fingered tremolo.
            # We must undo this factor of 2.
            vdur: HumNum = opFrac(Convert.recipToDuration(vdurRecip) / 2)
            m21VDur: m21.duration.Duration = m21.duration.Duration(vdur)
            vdurRecip = M21Convert.kernRecipFromM21Duration(m21VDur)[0]
            if vdurRecip == recip:
                vdurRecip = ''

        token: str = prefix + recip + graceType + pitch + postfix

        if vdurRecip:
            layouts.append('!LO:N:vis=' + vdurRecip)

        return (token, layouts)

    @staticmethod
    def kernGraceTypeFromM21Duration(m21Duration: m21.duration.Duration) -> str:
        isNonGrace: bool = not m21Duration.isGrace

        if isNonGrace:
            return ''

        if isinstance(m21Duration, m21.duration.AppoggiaturaDuration):
            # AppoggiaturaDurations are always accented
            return 'qq'

        if t.TYPE_CHECKING:
            # because non-grace and AppoggiaturaDuration have already returned
            assert isinstance(m21Duration, m21.duration.GraceDuration)

        # GraceDurations might be accented or unaccented.
        # duration.slash isn't always reliable (historically), but we can use it
        # as a fallback.
        # Check duration.stealTimePrevious and duration.stealTimeFollowing first.
        if m21Duration.stealTimePrevious is not None:
            return 'q'
        if m21Duration.stealTimeFollowing is not None:
            return 'qq'
        if m21Duration.slash is True:
            return 'q'
        if m21Duration.slash is False:
            return 'qq'

        # by default GraceDuration with no other indications means unaccented grace note.
        return 'q'

    @staticmethod
    def _getSizeFromGeneralNote(m21GeneralNote: m21.note.GeneralNote) -> str | None:
        if m21GeneralNote.hasStyleInformation:
            if t.TYPE_CHECKING:
                assert isinstance(m21GeneralNote.style, m21.style.NoteStyle)
            return m21GeneralNote.style.noteSize  # e.g. None, 'cue'
        return None

    @staticmethod
    def _getColorFromGeneralNote(m21GeneralNote: m21.note.GeneralNote) -> str | None:
        if m21GeneralNote.hasStyleInformation:
            return m21GeneralNote.style.color  # e.g. None, 'hotpink', '#00FF00', etc
        return None

    @staticmethod
    def kernPrefixPostfixAndLayoutsFromM21GeneralNote(
        m21GeneralNote: m21.note.GeneralNote,
        recip: str,
        spannerBundle: m21.spanner.SpannerBundle,
        isFirstNoteInChord: bool = False,
        isStandaloneNote: bool = True,
        owner=None
    ) -> tuple[str, str, list[str]]:
        prefix: str = ''
        postfix: str = ''
        layouts: list[str] = []

        # postfix possibility: invisible note
        invisibleStr: str = M21Convert._getKernInvisibilityFromGeneralNote(m21GeneralNote)

        # postfix possibility: articulations
        articStr: str = ''  # includes breathmark, caesura
        # other notations (fermata, trills, tremolos, mordents)
        expressionStr: str = ''
        stemStr: str = ''
        beamStr: str = ''
        cueSizeChar: str = ''
        noteColorChar: str = ''
        sfOrSfzStr: str = ''

        if isStandaloneNote:
            # if this note is in a chord, we will get this info from the chord itself,
            # not from this note
            beamStr = M21Convert._getHumdrumBeamStringFromM21GeneralNote(m21GeneralNote)

            expressions: list[m21.expressions.Expression | m21.spanner.Spanner] = (
                M21Utilities.getAllExpressionsFromGeneralNote(m21GeneralNote, spannerBundle)
            )
            expressionLayouts: list[str]
            expressionStr, expressionLayouts = (
                M21Convert._getHumdrumStringAndLayoutsFromM21Expressions(
                    expressions,
                    m21GeneralNote,
                    recip,
                    beamStr.count('L'),  # beamStarts
                    owner=owner
                )
            )
            layouts += expressionLayouts

            articStr = M21Convert._getHumdrumStringFromM21Articulations(
                m21GeneralNote.articulations,
                owner
            )
            stemStr = M21Convert._getHumdrumStemDirStringFromM21GeneralNote(m21GeneralNote)
            sfOrSfzStr = M21Convert._getSfOrSfzFromM21GeneralNote(m21GeneralNote)

        # isFirstNoteInChord is currently unused, but I suspect we'll need it at some point.
        # Make pylint happy (I can't just rename it with a '_' because callers use the param name.)
        if isFirstNoteInChord:
            pass

        # cue size is assumed to always be set on individual notes in a chord,
        # never just on the chord itself.
        noteSize: str | None = M21Convert._getSizeFromGeneralNote(m21GeneralNote)
        if noteSize is not None and noteSize == 'cue':
            cueSizeChar = owner.reportCueSizeToOwner()

        noteColor: str | None = M21Convert._getColorFromGeneralNote(m21GeneralNote)
        if noteColor:
            noteColorChar = owner.reportNoteColorToOwner(noteColor)

        postfix = (
            sfOrSfzStr + expressionStr + articStr + cueSizeChar + noteColorChar
            + stemStr + beamStr + invisibleStr
        )

        noteLayouts: list[str] = M21Convert._getNoteHeadLayoutsFromM21GeneralNote(m21GeneralNote)
        layouts += noteLayouts

        if isStandaloneNote:
            dynLayouts: list[str] = (
                M21Convert._getDynamicsLayoutsFromM21GeneralNote(m21GeneralNote)
            )
            layouts += dynLayouts

        # prefix/postfix possibility: ties
        tieStart, tieStop, tieLayouts = (
            M21Convert._getTieStartStopAndLayoutsFromM21GeneralNote(m21GeneralNote)
        )
        prefix = tieStart + prefix  # prepend to prefix for readability
        postfix += tieStop  # includes tie continues, since they should also be in the postfix
        layouts += tieLayouts

        # prefix/postfix possibility: slurs
        slurStarts: str = ''
        slurStops: str = ''
        slurStarts, slurStops = (
            M21Convert._getKernSlurStartsAndStopsFromGeneralNote(m21GeneralNote, spannerBundle)
        )
        prefix = slurStarts + prefix  # prepend to prefix for readability
        postfix += slurStops

        return (prefix, postfix, layouts)

    @staticmethod
    def _getNoteHeadLayoutsFromM21GeneralNote(m21GeneralNote: m21.note.GeneralNote) -> list[str]:
        if not isinstance(m21GeneralNote, m21.note.NotRest):
            # no notehead stuff, get out
            return []

        # noteheadFill is None, True, False
        # notehead is None, 'normal', 'cross', 'diamond', etc
        if m21GeneralNote.noteheadFill is None and (
                m21GeneralNote.notehead is None or m21GeneralNote.notehead == 'normal'):
            return []

        head: str | None = None
        if m21GeneralNote.noteheadFill is True:
            head = 'solid'
        elif m21GeneralNote.noteheadFill is False:
            head = 'open'
        elif m21GeneralNote.notehead == 'diamond':
            head = 'diamond'
        elif m21GeneralNote.notehead == 'cross':
            head = 'plus'

        if head:
            return [f'!LO:N:head={head}']

        return []

    _M21_OTTAVA_TYPES_TO_HUMDRUM = {
        '8va': '8va',
        '8vb': '8ba',
        '15ma': '15ma',
        '15mb': '15ba'
    }

    @staticmethod
    def _getKernTokenStringFromM21Ottava(ottava: m21.spanner.Ottava, start: bool) -> str:
        output: str = ''
        humdrumOttavaType: str = M21Convert._M21_OTTAVA_TYPES_TO_HUMDRUM.get(ottava.type, '')
        if not humdrumOttavaType:
            print(
                'Ottava type not supported in Humdrum: {ottava.type}; assuming 8va',
                file=sys.stderr
            )
            humdrumOttavaType = '8va'

        output = '*'
        if not start:
            output += 'X'
        output += humdrumOttavaType
        return output

    @staticmethod
    def getKernTokenStringFromM21OttavaStart(ottava: m21.spanner.Ottava) -> str:
        return M21Convert._getKernTokenStringFromM21Ottava(ottava, start=True)

    @staticmethod
    def getKernTokenStringFromM21OttavaStop(ottava: m21.spanner.Ottava) -> str:
        return M21Convert._getKernTokenStringFromM21Ottava(ottava, start=False)

    @staticmethod
    def _getKernSlurStartsAndStopsFromGeneralNote(
        m21GeneralNote: m21.note.GeneralNote,
        spannerBundle: m21.spanner.SpannerBundle
    ) -> tuple[str, str]:
        # FUTURE: Handle crossing (non-nested) slurs during export to humdrum '&('
        outputStarts: str = ''
        outputStops: str = ''

        spanners: list[m21.spanner.Spanner] = m21GeneralNote.getSpannerSites()
        slurStarts: list[str] = []  # 'above', 'below', or None
        slurEndCount: int = 0

        for slur in spanners:
            if not isinstance(slur, m21.spanner.Slur):
                continue
            if not M21Utilities.isIn(slur, spannerBundle):
                # it's from the flat score, or something (ignore it)
                continue
            if slur.isFirst(m21GeneralNote):
                slurStarts.append(slur.placement)
            elif slur.isLast(m21GeneralNote):
                slurEndCount += 1

        # slur starts (and optional placements of each)
        for placement in slurStarts:
            if placement is None:
                outputStarts += '('
            elif placement == 'above':
                outputStarts += '(>'
            elif placement == 'below':
                outputStarts += '(<'
            else:
                # shouldn't happen, but handle it
                outputStarts += '('

        # slur stops
        outputStops += ')' * slurEndCount

        return (outputStarts, outputStops)

    @staticmethod
    def _getKernInvisibilityFromGeneralNote(m21GeneralNote: m21.note.GeneralNote) -> str:
        if m21GeneralNote.hasStyleInformation and m21GeneralNote.style.hideObjectOnPrint:
            return 'yy'
        if 'SpacerRest' in m21GeneralNote.classes:
            # deprecated, but if we see it...
            return 'yy'
        return ''

    @staticmethod
    def kernTokenStringAndLayoutsFromM21Chord(
        m21Chord: m21.chord.Chord,
        spannerBundle: m21.spanner.SpannerBundle,
        owner=None
    ) -> tuple[str, list[str]]:
        pitchPerNote: list[str] = M21Convert.kernPitchesFromM21Chord(m21Chord, owner)
        recip: str = ''
        vdurRecip: str = ''
        graceType: str = ''
        recip, vdurRecip, graceType = M21Convert.kernRecipAndGraceTypeFromGeneralNote(m21Chord)
        prefixPerNote: list[str] = []
        postfixPerNote: list[str] = []
        layoutsForChord: list[str] = []

        prefixPerNote, postfixPerNote, layoutsForChord = (
            M21Convert.kernPrefixesPostfixesAndLayoutsFromM21Chord(
                m21Chord,
                recip,
                spannerBundle,
                owner)
        )

        token: str = ''
        for i, (prefix, pitch, postfix) in enumerate(
                zip(prefixPerNote, pitchPerNote, postfixPerNote)):
            if i > 0:
                token += ' '
            token += prefix + recip + graceType + pitch + postfix
            if vdurRecip and postfix.count('@@') == 2:
                # we have a fingered tremolo, so a portion of visual duration doubles the actual
                # duration to make music21 do the right thing visually with a fingered tremolo.
                # We must undo this factor of 2.
                vdur: HumNum = opFrac(Convert.recipToDuration(vdurRecip) / 2)
                m21VDur: m21.duration.Duration = m21.duration.Duration(vdur)
                vdurRecip = M21Convert.kernRecipFromM21Duration(m21VDur)[0]
                if vdurRecip == recip:
                    vdurRecip = ''

        if vdurRecip:
            layoutsForChord.append('!LO:N:vis=' + vdurRecip)

        return token, layoutsForChord

    @staticmethod
    def kernPitchesFromM21Chord(m21Chord: m21.chord.Chord, owner=None) -> list[str]:
        pitches: list[str] = []
        for m21Note in m21Chord:
            pitch: str = M21Convert.kernPitchFromM21Pitch(m21Note.pitch, owner)
            pitches.append(pitch)
        return pitches

    @staticmethod
    def kernPrefixesPostfixesAndLayoutsFromM21Chord(
        m21Chord: m21.chord.Chord,
        recip: str,
        spannerBundle: m21.spanner.SpannerBundle,
        owner=None
    ) -> tuple[list[str], list[str], list[str]]:
        prefixPerNote: list[str] = []    # one per note
        postfixPerNote: list[str] = []   # one per note
        layoutsForChord: list[str] = []  # 0 or more per note, maybe 1 for the whole chord

        # Here we get the chord signifiers, which might be applied to each note in the token,
        # or just the first, or just the last.
        beamStr: str = M21Convert._getHumdrumBeamStringFromM21GeneralNote(m21Chord)
        articStr: str = M21Convert._getHumdrumStringFromM21Articulations(
            m21Chord.articulations,
            owner
        )
        expressions: list[m21.expressions.Expression | m21.spanner.Spanner] = (
            M21Utilities.getAllExpressionsFromGeneralNote(m21Chord, spannerBundle)
        )
        expressionLayouts: list[str]
        exprStr: str
        exprStr, expressionLayouts = M21Convert._getHumdrumStringAndLayoutsFromM21Expressions(
            expressions,
            m21Chord,
            recip,
            beamStr.count('L'),  # beamStarts
            owner=owner
        )
        layoutsForChord += expressionLayouts

        stemStr: str = M21Convert._getHumdrumStemDirStringFromM21GeneralNote(m21Chord)
        slurStarts, slurStops = M21Convert._getKernSlurStartsAndStopsFromGeneralNote(
            m21Chord,
            spannerBundle
        )
        sfOrSfz: str = M21Convert._getSfOrSfzFromM21GeneralNote(m21Chord)
        dynLayouts: list[str] = M21Convert._getDynamicsLayoutsFromM21GeneralNote(m21Chord)
        layoutsForChord += dynLayouts

        # Here we get each note's signifiers
        for noteIdx, m21Note in enumerate(m21Chord):
            prefix: str = ''           # one for this note
            postfix: str = ''          # one for this note
            layouts: list[str] = []  # 0 or more for this note

            prefix, postfix, layouts = M21Convert.kernPrefixPostfixAndLayoutsFromM21GeneralNote(
                m21Note,
                recip,
                spannerBundle,
                isFirstNoteInChord=(noteIdx == 0),
                isStandaloneNote=False,
                owner=owner
            )

            # Add the chord signifiers as appropriate
            if noteIdx == 0:
                # first note gets the slur starts
                #   (plus 'z' or 'zz', expressions, articulations, stem directions)
                prefix = slurStarts + prefix
                postfix = postfix + sfOrSfz + exprStr + articStr + stemStr
            elif noteIdx == len(m21Chord) - 1:
                # last note gets the beams, and the slur stops
                #   (plus 'z' or 'zz', expressions, articulations, stem directions)
                postfix = postfix + sfOrSfz + exprStr + articStr + stemStr + beamStr + slurStops
            else:
                # the other notes in the chord just get 'z', 'zz', expressions, articulations,
                # stem directions
                postfix = postfix + sfOrSfz + exprStr + articStr + stemStr


            # put them in prefixPerNote, postFixPerNote, and layoutsForNotes
            prefixPerNote.append(prefix)
            postfixPerNote.append(postfix)
            for layout in layouts:
                # we have to add ':n=3' to each layout, where '3' is one-based (i.e. noteIdx+1)
                numberedLayout: str = M21Convert._addNoteNumberToLayout(layout, noteIdx + 1)
                layoutsForChord.append(numberedLayout)

        return (prefixPerNote, postfixPerNote, layoutsForChord)

    @staticmethod
    def _addNoteNumberToLayout(layout: str, noteNum: int) -> str:
        # split at colons
        params: list[str] = layout.split(':')
        insertAtIndex: int = 2
        params.insert(insertAtIndex, f'n={noteNum}')

        output: str = ':'.join(params)
        return output

    '''
    //////////////////////////////
    //
    // MxmlEvent::getRecip -- return **recip value for note/rest.
    //   e.g. recip == '4' for a quarter note duration, recip == '2' for a half note duration.
        Code that converts to '00' etc came from Tool_musicxml2hum::addEvent. --gregc
        Also returns any visual duration recip as a second string.
    '''
    @staticmethod
    def kernRecipFromM21Duration(m21Duration: m21.duration.Duration) -> tuple[str, str]:
        dur: HumNum
        vdur: HumNum | None = None
        dots: str | None = None
        inTuplet: bool = False

        if m21Duration.isGrace:
            # It's a grace note, so we want to generate real recip (printed duration)
            # even though quarterLength is (correctly) zero. m21Duration.type is 'eighth'
            # or '16th' or whatever, so use that.  This way the grace notes will keep
            # the correct number of flags/beams.
            dur = m21.duration.convertTypeToQuarterLength(m21Duration.type)
            dots = ''
        elif m21Duration.linked is False and m21Duration.tuplets and len(m21Duration.tuplets) == 1:
            # There's a real (gestural) duration and a visual duration AND they are tuplet-y.
            # Real duration is quarterLength, visual duration ignores the tuplet and just uses
            # type and dots.
            dur = m21Duration.quarterLength
            vdur = m21.duration.convertTypeToQuarterLength(m21Duration.type)
            if m21Duration.dots > 0:
                vdur *= (1.5 * float(m21Duration.dots))
            vdur = opFrac(vdur)
            inTuplet = True
        elif m21Duration.linked is False:
            # There's a real (gestural) duration and a visual duration
            # Real duration is quarterLength, visual duration is components[0].quarterLength
            # (assuming only 1 component)
            dur = m21Duration.quarterLength
            if len(m21Duration.components) == 1:
                vdur = m21Duration.components[0].quarterLength
            else:
                print('visual duration unusable, ignoring it', file=sys.stderr)
        elif m21Duration.tuplets and len(m21Duration.tuplets) == 1:
            dur = m21.duration.convertTypeToQuarterLength(m21Duration.type)
            dur *= m21Duration.tuplets[0].tupletMultiplier()
            dur = opFrac(dur)
            dots = '.' * m21Duration.dots
            inTuplet = True
        else:
            # no tuplet, or nested tuplets (which we will ignore, since music21 doesn't really
            # support nested tuplets, and neither do we)
            dur = m21Duration.quarterLength

        dur = opFrac(dur / 4)  # convert to whole-note units
        durFraction: Fraction = Fraction(dur)

        if dots is None and not inTuplet:
            # compute number of dots from dur (and shrink dur to match)
            # if it's 1 we don't need any dots
            if durFraction.numerator != 1:
                # otherwise check up to three dots
                oneDotDur: Fraction = Fraction(dur * 2 / 3)
                if oneDotDur.numerator == 1:
                    durFraction = oneDotDur
                    dots = '.'
                else:
                    twoDotDur: Fraction = Fraction(dur * 4 / 7)
                    if twoDotDur.numerator == 1:
                        durFraction = twoDotDur
                        dots = '..'
                    else:
                        threeDotDur: Fraction = Fraction(dur * 8 / 15)
                        if threeDotDur.numerator == 1:
                            durFraction = threeDotDur
                            dots = '...'

        percentExists: bool = False
        out: str = str(durFraction.denominator)
        if durFraction.numerator != 1:
            out += '%' + str(durFraction.numerator)
            percentExists = True
        if dots:
            out += dots

        # Check for a few specific 'n%m' recips that can be converted to '00' etc
        if percentExists:
            m = re.search(r'(\d+)%(\d+)(\.*)', out)
            if m:
                first: int = int(m.group(1))
                second: int = int(m.group(2))
                someDots: str = m.group(3)
                if not someDots:
                    if first == 1 and second == 2:
                        out = out.replace('1%2', '0')
                    elif first == 1 and second == 4:
                        out = out.replace('1%4', '00')
                    elif first == 1 and second == 8:
                        out = out.replace('1%8', '000')
                    elif first == 1 and second == 16:
                        out = out.replace('1%16', '0000')
                    elif first == 1 and second == 3 and not inTuplet:
                        # don't add a dot if we're in a tuplet, we have the exact dot count we want
                        out = out.replace('1%3', '0.')
                    elif first == 1 and second == 6 and not inTuplet:
                        # don't add a dot if we're in a tuplet, we have the exact dot count we want
                        out = out.replace('1%6', '00.')
                    elif first == 1 and second == 12 and not inTuplet:
                        # don't add a dot if we're in a tuplet, we have the exact dot count we want
                        out = out.replace('1%12', '000.')
                    elif first == 1 and second == 24 and not inTuplet:
                        # don't add a dot if we're in a tuplet, we have the exact dot count we want
                        out = out.replace('1%24', '0000.')
                else:
                    if first == 1 and second == 2:
                        out = out.replace('1%2' + someDots, '0' + someDots)
                    elif first == 1 and second == 4:
                        out = out.replace('1%4' + someDots, '00' + someDots)
                    elif first == 1 and second == 8:
                        out = out.replace('1%8' + someDots, '000' + someDots)
                    elif first == 1 and second == 16:
                        out = out.replace('1%16' + someDots, '0000' + someDots)

        # now make sure that if we're in a tuplet, that the recip we produce, once we remove
        # the dots, is not a power of two.  If it is, come up with a recip that has the exact
        # same duration, but has more dots, so it is not a power of two with no dots.
        if inTuplet:
            recipNoDots: str = out.split('.', 1)[0]
            durNoDots: HumNum = Convert.recipToDuration(recipNoDots)
            if M21Utilities.isPowerOfTwo(durNoDots):
                # we have a problem, try to fix by making a recip with one more dot
                numDots: int = out.count('.')
                desiredDurNoDots: HumNum = durNoDots / 1.5
                newRecip: str = Convert.durationToRecip(desiredDurNoDots)
                newNumDots: int = numDots + 1
                newRecip += '.' * newNumDots
                out = newRecip

        if vdur:
            m21VDur = m21.duration.Duration(vdur)
            vdurRecip: str = M21Convert.kernRecipFromM21Duration(m21VDur)[0]
            return out, vdurRecip
        return out, ''

    @staticmethod
    def accidentalInfo(
        m21Accid: m21.pitch.Accidental | None
    ) -> tuple[int, bool, bool, str]:
        # returns alter, isExplicit, isEditorial, and editorialStyle
        alter: int = 0
        isExplicit: bool = False   # forced to display
        isEditorial: bool = False  # forced to display (with parentheses or bracket)
        editorialStyle: str = 'normal'
        if m21Accid is not None:
            alter = int(m21Accid.alter)
            if alter != m21Accid.alter:
                print(f'WARNING: Ignoring microtonal accidental: {m21Accid}.', file=sys.stderr)
                # replace microtonal accidental with explicit natural sign
                alter = 0
                isExplicit = True

            if m21Accid.displayStatus:  # must be displayed
                isExplicit = True
                editorialStyle = m21Accid.displayStyle
                if editorialStyle != 'normal':
                    # must be 'parentheses', 'bracket', or 'both'
                    isEditorial = True
        return (alter, isExplicit, isEditorial, editorialStyle)

    @staticmethod
    def kernPitchFromM21Pitch(m21Pitch: m21.pitch.Pitch, owner) -> str:
        output: str = ''
        m21Accid: m21.pitch.Accidental | None = m21Pitch.accidental
        m21Step: str = m21Pitch.step  # e.g. 'A' for an A-flat
        m21Octave: int | None = m21Pitch.octave
        if m21Octave is None:
            m21Octave = m21Pitch.implicitOctave  # 4, most likely

        isEditorial: bool = False  # forced to display (with parentheses or bracket)
        isExplicit: bool = False   # forced to display
        alter: int = 0
        editorialStyle: str = ''

        alter, isExplicit, isEditorial, editorialStyle = M21Convert.accidentalInfo(m21Accid)
        if isEditorial:
            editorialSuffix = M21Convert._reportEditorialAccidentalToOwner(owner, editorialStyle)

        output = M21Convert.kernPitchFromM21OctaveAndStep(m21Octave, m21Step, owner)

        if m21Accid is None:
            # no accidental suffix (it's ok)
            pass
        elif alter > 0:
            # sharps suffix
            for _ in range(0, alter):
                output += '#'
        elif alter < 0:
            # flats suffix
            for _ in range(0, -alter):
                output += '-'

        if isEditorial:
            if alter == 0:
                # explicit natural + editorial suffix
                output += 'n' + editorialSuffix
            else:
                output += editorialSuffix
        elif isExplicit:
            if alter == 0:
                # explicit natural
                output += 'n'
            else:
                # explicit suffix for other accidentals
                output += 'X'

        return output

    @staticmethod
    def _reportEditorialAccidentalToOwner(owner, editorialStyle: str) -> str:
        if owner:
            from converter21.humdrum import EventData
            ownerEvent: EventData = owner
            return ownerEvent.reportEditorialAccidentalToOwner(editorialStyle)
        return ''

    @staticmethod
    def textLayoutParameterFromM21Pieces(
        content: str,
        placement: str | None,
        style: m21.style.TextStyle | None
    ) -> str:
        placementString: str = ''
        styleString: str = ''
        justString: str = ''
        colorString: str = ''
        contentString: str = M21Convert.translateSMUFLNotesToNoteNames(content)
        contentString = M21Convert._cleanSpacesAndColons(contentString)

        # We are perfectly happy to deal with empty contentString.  The result will be:
        # '!LO:TX:i:t=' or something like that.
        # The bottom line is that we can't return an invalid token string (e.g. '') or
        # that will go into the exported file, and a '' will show up on parse as a missing
        # spine. --gregc
        if placement is not None:
            if placement == 'above':
                placementString = ':a'
            elif placement == 'below':
                if style and style.alignVertical == 'middle':
                    placementString = ':c'
                else:
                    placementString = ':b'

        if style:
            # absoluteY overrides placement
            if style.absoluteY is not None:
                if style.absoluteY > 0.0:
                    placementString = ':a'
                else:
                    placementString = ':b'

            italic: bool = False
            bold: bool = False

            if style.fontStyle is not None:
                if style.fontStyle == 'italic':
                    italic = True
                elif style.fontStyle == 'bold':
                    bold = True
                elif style.fontStyle == 'bolditalic':
                    bold = True
                    italic = True

            if style.fontWeight is not None and style.fontWeight == 'bold':
                bold = True

            if italic and bold:
                styleString = ':Bi'
            elif italic:
                styleString = ':i'
            elif bold:
                styleString = ':B'

            if style.justify == 'right':
                justString = ':rj'
            elif style.justify == 'center':
                justString = ':cj'

            if style.color:
                colorString = f':color={style.color}'

        output: str = (
            '!LO:TX' + placementString + styleString + justString + colorString
            + ':t=' + contentString
        )
        return output

    @staticmethod
    def textLayoutParameterFromM21TextExpression(
        textExpression: m21.expressions.TextExpression
    ) -> str:
        if textExpression is None:
            return ''

        contentString: str = textExpression.content
        placement: str | None = textExpression.placement
        if textExpression.hasStyleInformation:
            if t.TYPE_CHECKING:
                assert isinstance(textExpression.style, m21.style.TextStyle)
            return M21Convert.textLayoutParameterFromM21Pieces(
                contentString,
                placement,
                textExpression.style
            )
        return M21Convert.textLayoutParameterFromM21Pieces(contentString, placement, None)

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::cleanSpacesAndColons -- Converts newlines and
    //     tabs to spaces, and removes leading and trailing spaces from the
    //     string.  Another variation would be to use \n to encode newlines
    //     if they need to be preserved, but for now converting them to spaces.
    //     Colons (:) are also converted to &colon;.
    '''
    @staticmethod
    def _cleanSpacesAndColons(inStr: str) -> str:
        otherNewLinesAndTabs: str = '\t\r\v\f'
        output: str = ''
        for ch in inStr:
            if ch == '\u00A0':
                # convert all non-breaking spaces to '&nbsp;'
                output += '&nbsp;'
                continue

            if ch == ':':
                # convert all colons to '&colon;'
                output += '&colon;'
                continue

            if ch == '\n':
                output += r'\n'
                continue

            if ch in otherNewLinesAndTabs:
                # convert all otherNewLinesAndTabs chars to a space
                output += ' '
                continue

            output += ch

        # Strip all leading and trailing whitespace
        # We do this last after we've already saved the non-breaking spaces from stripping.
        output = output.strip()
        return output

    @staticmethod
    def translateSMUFLNotesToNoteNames(text: str) -> str:
        # translates SMUFL note strings to Humdrum note names (and drops thin spaces)
        # e.g. ' ' -> [half-dot]

        # We get pretty aggressive here about making the resulting tempo text parseable
        # (removing thin spaces, translating nbsp to space, etc), so we really don't
        # want to do that if there are no SMUFL notes in the text.
        # Check first, and if no SMUFL note found, return the text untouched.
        smuflNoteFound: bool = False
        for char in text:
            if char in SharedConstants.SMUFL_METRONOME_MARK_NOTE_CHARS_TO_HUMDRUM_NOTE_NAME:
                smuflNoteFound = True
                break
        if not smuflNoteFound:
            return text

        output: str = ''
        numCharsToSkip: int = 0
        for i, char in enumerate(text):
            if numCharsToSkip > 0:
                numCharsToSkip -= 1
                continue

            if char in SharedConstants.SMUFL_METRONOME_MARK_NOTE_CHARS_TO_HUMDRUM_NOTE_NAME:
                output += (
                    '['
                    + SharedConstants.SMUFL_METRONOME_MARK_NOTE_CHARS_TO_HUMDRUM_NOTE_NAME[char]
                )
                j = i + 1
                while text[j] in (
                    SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR['metAugmentationDot'],
                    chr(0x2009),  # thin space, inserted around notes sometimes
                    chr(0x200A),  # hair (very thin) space, inserted sometimes as well
                ):
                    if text[j] in (chr(0x2009), chr(0x200A)):
                        pass  # just skip the thin/hair space
                    else:
                        output += '-dot'
                    j += 1
                output += ']'
                numCharsToSkip = j - (i + 1)
                continue

            if char in (chr(0x2009), chr(0x200A)):  # thin space, inserted sometimes
                continue  # just skip the thin/hair space

            if char == chr(0x00A0):
                # convert nbsp to regular space (Humdrum doesn't want nbsp's in tempo text)
                output += ' '
                continue

            # all other chars
            output += char

        return output


    @staticmethod
    def _floatOrIntString(num: float | int) -> str:
        intNum: int = int(num)
        if num == intNum:
            return str(intNum)
        return str(num)

    # getMMTokenAndTempoTextFromM21TempoIndication returns (mmTokenStr, tempoTextLayout).
    @staticmethod
    def getMMTokenAndTempoTextFromM21TempoIndication(
        tempo: m21.tempo.TempoIndication
    ) -> tuple[str, str]:
        mmTokenStr: str = ''
        tempoText: str = ''

        textExp: m21.expressions.TextExpression | None = None
        contentString: str = ''

        # a TempoText has only text (no bpm info)
        if isinstance(tempo, m21.tempo.TempoText):
            textExp = tempo.getTextExpression()  # only returns explicit text
            if textExp is None:
                return ('', '')
            contentString = M21Convert.translateSMUFLNotesToNoteNames(textExp.content)
            contentString = M21Convert._cleanSpacesAndColons(contentString)
            tempoText = contentString
            return ('', tempoText)

        # a MetricModulation describes a change from one MetronomeMark to another
        # (it carries extra info for analysis purposes).  We just get the new
        # MetronomeMark and carry on.
        if isinstance(tempo, m21.tempo.MetricModulation):
            tempo = tempo.newMetronome

        # a MetronomeMark has (optional) text (e.g. 'Andante') and (optional) bpm info.
        if not isinstance(tempo, m21.tempo.MetronomeMark):
            return ('', '')

        # if the MetronomeMark has non-implicit text, we construct some layout text (with style).
        # if the MetronomeMark has bpm info (implicit or not), we construct a *MM.
        textExp = tempo.getTextExpression()  # only returns explicit text
        if textExp is not None:
            # We have some text (like 'Andante') to display
            contentString = M21Convert.translateSMUFLNotesToNoteNames(textExp.content)
            contentString = M21Convert._cleanSpacesAndColons(contentString)
            tempoText = contentString

        if tempo.number is not None:
            # Produce *MM even for implicit numbers.
            # Note that we always round to integer to emit *MM (we round to integer
            # when we parse it, too).
            quarterBPM: float | None = tempo.getQuarterBPM()
            if quarterBPM is not None:
                mmTokenStr = '*MM' + M21Convert._floatOrIntString(int(quarterBPM + 0.5))

        return (mmTokenStr, tempoText)

    # @staticmethod
    # def bpmTextLayoutParameterFromM21MetronomeMark(tempo: m21.tempo.MetronomeMark) -> str:
    #     if tempo is None:
    #         return ''
    #
    #     # '[eighth]=82', for example
    #     contentString: str = M21Convert.getHumdrumBPMTextFromM21MetronomeMark(tempo)
    #     placement: str | None = tempo.placement
    #
    #     if tempo.hasStyleInformation:
    #         if t.TYPE_CHECKING:
    #             assert isinstance(tempo.style, m21.style.TextStyle)
    #         return M21Convert.textLayoutParameterFromM21Pieces(
    #             contentString, placement, tempo.style
    #         )
    #     return M21Convert.textLayoutParameterFromM21Pieces(contentString, placement, None)

    # @staticmethod
    # def getHumdrumBPMTextFromM21MetronomeMark(tempo: m21.tempo.MetronomeMark) -> str:
    #     output: str = '['
    #     output += M21Convert.getHumdrumTempoNoteNameFromM21Duration(tempo.referent)
    #     output += ']='
    #     output += M21Convert._floatOrIntString(tempo.number)
    #     return output

    @staticmethod
    def getHumdrumTempoNoteNameFromM21Duration(referent: m21.duration.Duration) -> str:
        # m21 Duration types are all names that are acceptable as humdrum tempo note names,
        # so no type->name mapping is required.  (See m21.duration.typeToDuration's dict keys.)
        noteName: str = referent.type
        if referent.dots > 0:
            noteName += '-dot' * referent.dots
        return noteName

    @staticmethod
    def durationFromHumdrumTempoNoteName(
        noteName: str | None
    ) -> m21.duration.Duration | None:
        if not noteName:
            return None

        # In case someone forgot to strip the brackets off '[quarter-dot]', for example.
        if noteName[0] == '[':
            noteName = noteName[1:]

        if noteName[-1] == ']':
            noteName = noteName[:-1]

        # remove styling qualifiers (everything after '|' or '@')
        noteName = re.sub('[|@].*', '', noteName)

        # generating rhythmic note with (up to three) optional "-dot"s after it.
        dots: int = 0
        if re.search('-dot$', noteName):
            dots = 1
            if re.search('-dot-dot$', noteName):
                dots = 2
                if re.search('-dot-dot-dot$', noteName):
                    dots = 3
                # Only allowing three augmentation dots.
        noteName = re.sub('(-dot)+', '', noteName)

        # Check for "." used as an augmentation dot (typically used with numbers):
        m = re.search(r'(\.+)$', noteName)
        if m:
            dotstring: str = m.group(1)
            dots += len(dotstring)
            noteName = re.sub(r'\.+$', '', noteName)

        if noteName in ('quarter', '4'):
            return m21.duration.Duration(type='quarter', dots=dots)
        if noteName in ('half', '2'):
            return m21.duration.Duration(type='half', dots=dots)
        if noteName in ('whole', '1'):
            return m21.duration.Duration(type='whole', dots=dots)
        if noteName in ('breve', 'double-whole', '0'):
            return m21.duration.Duration(type='breve', dots=dots)
        if noteName in ('eighth', '8', '8th'):
            return m21.duration.Duration(type='eighth', dots=dots)
        if noteName in ('sixteenth', '16', '16th'):
            return m21.duration.Duration(type='16th', dots=dots)
        if noteName in ('32', '32nd'):
            return m21.duration.Duration(type='32nd', dots=dots)
        if noteName in ('64', '64th'):
            return m21.duration.Duration(type='64th', dots=dots)
        if noteName in ('128', '128th'):
            return m21.duration.Duration(type='128th', dots=dots)
        if noteName in ('256', '256th'):
            return m21.duration.Duration(type='256th', dots=dots)
        if noteName in ('512', '512th'):
            return m21.duration.Duration(type='512th', dots=dots)
        if noteName in ('1024', '1024th'):
            return m21.duration.Duration(type='1024th', dots=dots)

        return None

    dynamicPatterns: list[str] = [
        # These have to be in a search order where you won't find a substring of the real
        # pattern first. For example, if you reverse the middle two, then 'fp' will match
        # as 'f' before it matches as 'fp'.
        'm(f|p)',      # 'mf', 'mp'
        's?f+z?p+',     # 'fp', 'sfzp', 'ffp' etc
        '[sr]?f+z?',    # 'sf, 'sfz', 'f', 'fff', etc
        'p+',           # 'p', 'ppp', etc
    ]
    dynamicBrackets: list[tuple[str, str, str]] = [
        ('brack', r'\[ ', r' \]'),
        ('paren', r'\( ', r' \)'),
        ('curly', r'\{ ', r' \}'),
        ('angle', '< ', ' >'),
    ]

    @staticmethod
    def getDynamicString(dynamic: m21.dynamics.Dynamic) -> str:
        output: str
        for patt in M21Convert.dynamicPatterns:
            # look for perfect match of entire value
            m = re.match('^' + patt + '$', dynamic.value)
            if m:
                output = m.group(0)
                return output

        # didn't find a perfect match, check for surrounding brackets, parens, curlies or angles.
        for patt in M21Convert.dynamicPatterns:
            for _name, start, end in M21Convert.dynamicBrackets:
                matchPatt: str = '^' + start + patt + end + '$'
                m = re.match(matchPatt, dynamic.value)
                if m:
                    output = m.group(0)
                    # strip off the start and end
                    output = output[2:-2]
                    return output

        # didn't find anything yet, perhaps it's something like 'p sempre legato', where
        # we need to find 'p', and not 'mp'.
        for patt in M21Convert.dynamicPatterns:
            for startDelim in ('^', r'\s'):
                for endDelim in (r'\s', '$'):
                    m = re.search(startDelim + patt + endDelim, dynamic.value)
                    if m:
                        output = m.group(0)
                        if startDelim == r'\s':
                            output = output[1:]
                        if endDelim == r'\s':
                            output = output[:-1]
                        return output

        # give up and return whatever that string is (that isn't, and doesn't contain, a dynamic)
        return dynamic.value

    @staticmethod
    def getDynamicWedgeString(wedge: m21.Music21Object, isStart: bool, isEnd: bool) -> str:
        # This method can take any Music21Object, but only DynamicWedges return anything
        # interesting.
        if not isinstance(wedge, m21.dynamics.DynamicWedge):
            return ''

        isCrescendo: bool = isinstance(wedge, m21.dynamics.Crescendo)
        isDiminuendo: bool = isinstance(wedge, m21.dynamics.Diminuendo)

        if isStart and isEnd:
            # start and end in same string
            if isCrescendo:
                return '<['
            if isDiminuendo:
                return '>]'
        else:
            if isStart and isCrescendo:
                return '<'
            if isStart and isDiminuendo:
                return '>'
            if isEnd and isCrescendo:
                return '['
            if isEnd and isDiminuendo:
                return ']'

        return ''

    '''
    //////////////////////////////
    //
    // Tool_musicxml2hum::getDynamicsParameters --
    '''
    @staticmethod
    def getDynamicParameters(dynamic: m21.dynamics.Dynamic, staffIndex: int) -> str:
        output: str = ''
        dynString: str = M21Convert.getDynamicString(dynamic)

        textStyle: m21.style.TextStyle | None = None
        if dynamic.hasStyleInformation:
            assert isinstance(dynamic.style, m21.style.TextStyle)
            textStyle = dynamic.style

        staffStr: str = ''
        if staffIndex > 0:
            staffStr = '=' + str(staffIndex + 1)

        if dynamic.placement == 'above':
            output += ':a' + staffStr

        if dynamic.placement == 'below':
            if textStyle is not None and textStyle.alignVertical == 'middle':
                if staffIndex == 0:
                    # already in top staff, humdrum default is centered below, so leave it out
                    pass
                else:
                    output += ':c' + staffStr
            else:
                output += ':b' + staffStr

        # right justification
        if textStyle is not None:
            if textStyle.justify == 'right':
                output += ':rj'
            elif textStyle.justify == 'center':
                output += ':cj'

        if dynString != dynamic.value:
            # check first for surrounding brackets, parens, curlies or angles.
            for patt in M21Convert.dynamicPatterns:
                for name, start, end in M21Convert.dynamicBrackets:
                    matchPatt: str = '^' + start + patt + end + '$'
                    m = re.match(matchPatt, dynamic.value)
                    if m:
                        output += ':ed=' + name
                        return output

            # t='%s sempre legato' (if dynamic.value is 'ff sempre legato', for example)
            # be careful not to match 'mp' in 'ff sempre legato'!
            for patt in M21Convert.dynamicPatterns:
                for startDelim in ('^', r'\s'):
                    for endDelim in (r'\s', '$'):
                        m = re.search(startDelim + patt + endDelim, dynamic.value)
                        if m:
                            dynstr: str = m.group(0)
                            substitution: str = '%s'
                            if startDelim == r'\s':
                                substitution = dynstr[0] + substitution
                            if endDelim == r'\s':
                                substitution = substitution + dynstr[-1]
                            fmt: str = re.sub(dynstr, substitution, dynamic.value, count=1)
                            # See if there is a double space after the %s we just put in.
                            # If there is, assume verovio's humdrum reader put the extra space,
                            # and delete it.
                            fmt = re.sub('%s  ', '%s ', fmt, count=1)
                            output += ':t=' + fmt
                            return output

        return output

    @staticmethod
    def getHarmonyParameters(cs: m21.harmony.ChordSymbol, staffIndex: int) -> str:
        output: str = ''
        #   textStyle: m21.style.TextStyle | None = None
        #   if dynamic.hasStyleInformation:
        #       assert isinstance(dynamic.style, m21.style.TextStyle)
        #       textStyle = dynamic.style
        #
        #   staffStr: str = ''
        #   if staffIndex > 0:
        #       staffStr = '=' + str(staffIndex + 1)
        #
        #   if cs.placement == 'above':
        #       output += ':a' + staffStr
        #
        #   if dynamic.placement == 'below':
        #       if textStyle is not None and textStyle.alignVertical == 'middle':
        #           if staffIndex == 0:
        #               # already in top staff, humdrum default is centered below, so leave it out
        #               pass
        #           else:
        #               output += ':c' + staffStr
        #           else:
        #               output += ':b' + staffStr
        #
        #       if textStyle is not None:
        #           if textStyle.justify == 'right':
        #               output += ':rj'
        #           elif textStyle.justify == 'center':
        #               output += ':cj'
        if hasattr(cs, 'c21_full_text'):
            output += f':t={cs.c21_full_text}'  # type: ignore
        if cs.chordKindStr:
            output += f':kt={cs.chordKindStr}'

        return output

    @staticmethod
    def getDynamicOnNoteParameters(dynamic: m21.dynamics.Dynamic) -> str:
        output: str = ''
        dynString: str = M21Convert.getDynamicString(dynamic)

        textStyle: m21.style.TextStyle | None = None
        if dynamic.hasStyleInformation:
            assert isinstance(dynamic.style, m21.style.TextStyle)
            textStyle = dynamic.style

        # right justification
        if textStyle is not None:
            if textStyle.justify == 'right':
                output += ':rj'
            elif textStyle.justify == 'center':
                output += ':cj'

        if dynString != dynamic.value:
            # check first for surrounding brackets, parens, curlies or angles.
            for patt in M21Convert.dynamicPatterns:
                for name, start, end in M21Convert.dynamicBrackets:
                    matchPatt: str = '^' + start + patt + end + '$'
                    m = re.match(matchPatt, dynamic.value)
                    if m:
                        output += ':ed=' + name
                        return output

            # t='%s sempre legato' (if dynamic.value is 'ff sempre legato', for example)
            # be careful not to match 'mp' in 'ff sempre legato'!
            for patt in M21Convert.dynamicPatterns:
                for startDelim in ('^', r'\s'):
                    for endDelim in (r'\s', '$'):
                        m = re.search(startDelim + patt + endDelim, dynamic.value)
                        if m:
                            dynstr: str = m.group(0)
                            substitution: str = '%s'
                            if startDelim == r'\s':
                                substitution = dynstr[0] + substitution
                            if endDelim == r'\s':
                                substitution = substitution + dynstr[-1]
                            fmt: str = re.sub(dynstr, substitution, dynamic.value, count=1)
                            output += ':t=' + fmt
                            return output

        return output

    @staticmethod
    def getDynamicWedgeStartParameters(dynamic: m21.dynamics.DynamicWedge, staffIndex: int) -> str:
        if not isinstance(dynamic, m21.dynamics.DynamicWedge):
            return ''

        staffStr: str = ''
        if staffIndex > 0:
            staffStr = '=' + str(staffIndex + 1)

        # Dynamic.placement showed up in music21 v7
        if dynamic.placement == 'above':
            return ':a' + staffStr

        if dynamic.placement == 'below':
            # dynamicWedge.style doesn't generally have alignVertical
            # (it's not a TextStyle), but...
            # some importers set it anyway, so if it's there, obey it.
            if (dynamic.hasStyleInformation
                    and hasattr(dynamic.style, 'alignVertical')
                    and dynamic.style.alignVertical == 'middle'):  # type: ignore
                if staffIndex == 0:
                    # already in top staff, humdrum default is centered below, so leave it out
                    return ''
                else:
                    return ':c' + staffStr
            return ':b' + staffStr

        return ''

    @staticmethod
    def clefTokenFromM21Clef(clef: m21.clef.Clef) -> HumdrumToken | None:
        if clef is None:
            return None

        string: str = '*clef'
        if clef.sign in ('G', 'F', 'C'):
            string += clef.sign

            octaveChange: int = clef.octaveChange
            if octaveChange is not None:
                if octaveChange < 0:
                    string += 'v' * -octaveChange
                elif octaveChange > 0:
                    string += '^' * octaveChange

            if isinstance(clef.line, int):  # can be None
                string += str(clef.line)

        elif clef.sign == 'percussion':
            string += 'X'  # '*clefX'
            if isinstance(clef.line, int):  # it's usually None (centered), but you can position it
                string += str(clef.line)

        else:
            # humdrum doesn't support other clefs (like 'TAB', 'jianpu')
            return None

        return HumdrumToken(string)

    @staticmethod
    def timeSigTokenFromM21TimeSignature(
        timeSig: m21.meter.TimeSignature
    ) -> HumdrumToken | None:
        timeSigStr: str = '*M' + timeSig.ratioString
        return HumdrumToken(timeSigStr)

    @staticmethod
    def meterSigTokenFromM21TimeSignature(
        timeSig: m21.meter.TimeSignature
    ) -> HumdrumToken | None:
        mensurationStr: str | None = (
            M21Convert.m21TimeSignatureSymbolToHumdrumMensurationSymbol.get(timeSig.symbol)
        )
        if mensurationStr is None:
            return None

        meterSigStr: str = '*met(' + mensurationStr + ')'

        return HumdrumToken(meterSigStr)

    @staticmethod
    def instrumentTransposeTokenFromM21Instrument(
        inst: m21.instrument.Instrument
    ) -> HumdrumToken | None:
        if inst.transposition is None:
            return None

        # Humdrum and music21 have reversed instrument transposition definitions
        transpose: m21.interval.Interval = inst.transposition.reverse()
        dNcM: str | None = M21Convert.humdrumTransposeStringFromM21Interval(transpose)
        if dNcM is None:
            return None

        transposeStr: str = '*ITr'
        transposeStr += dNcM
        return HumdrumToken(transposeStr)

    @staticmethod
    def keySigTokenFromM21KeySignature(
        keySig: m21.key.KeySignature | m21.key.Key
    ) -> HumdrumToken:
        keySigStr: str = '*k['
        keySigStr += M21Convert.numSharpsToHumdrumStandardKeyStrings[keySig.sharps]
        keySigStr += ']'

        return HumdrumToken(keySigStr)

    @staticmethod
    def keyDesignationTokenFromM21KeySignature(
        keySig: m21.key.KeySignature | m21.key.Key
    ) -> HumdrumToken | None:
        if not isinstance(keySig, m21.key.Key):
            return None

        keyStr: str = '*' + keySig.tonicPitchNameWithCase + ':'
        if keySig.mode in ('major', 'minor'):
            # already indicated via uppercase (major) or lowercase (minor)
            return HumdrumToken(keyStr)

        keyStr += M21Convert.m21ModeToHumdrumMode.get(keySig.mode, '')
        return HumdrumToken(keyStr)

    @staticmethod
    def _getHumdrumStringFromM21Articulations(
        m21Artics: list[m21.articulations.Articulation],
        owner=None
    ) -> str:
        output: str = ''
        for artic in m21Artics:
            humdrumChar: str = M21Convert.m21ArticulationClassNameToHumdrumArticulationString.get(
                artic.classes[0],
                ''
            )
            if humdrumChar:
                output += humdrumChar
            elif isinstance(artic, m21.articulations.Caesura):
                # check for caesura (isn't in the lookup because it's an RDF signifier)
                caesuraChar: str = owner.reportCaesuraToOwner()
                output += caesuraChar

            # add any placement
            if artic.placement == 'below':
                output += '<'
            elif artic.placement == 'above':
                output += '>'

        return output

    @staticmethod
    def _getMeasureContaining(gnote: m21.note.GeneralNote) -> m21.stream.Measure | None:
        measure: m21.stream.Measure | None = gnote.getContextByClass(m21.stream.Measure)
        return measure

    @staticmethod
    def _allSpannedGeneralNotesInSameMeasure(spanner: m21.spanner.Spanner) -> bool:
        measureOfFirstSpanned: m21.stream.Measure | None = None
        for i, gnote in enumerate(spanner):
            if i == 0:
                measureOfFirstSpanned = M21Convert._getMeasureContaining(gnote)
                continue
            if M21Convert._getMeasureContaining(gnote) is not measureOfFirstSpanned:
                return False
        return True

    @staticmethod
    def _getHumdrumStringAndLayoutsFromM21Expressions(
        m21Expressions: t.Sequence[m21.expressions.Expression | m21.spanner.Spanner],
        m21GeneralNote: m21.note.GeneralNote,
        recip: str,
        beamStarts: int | None = None,
        owner=None
    ) -> tuple[str, list[str]]:
        # expressions are Fermata, Trill, Mordent, Turn, Tremolo (one note)
        # also the following two Spanners: TrillExtension and TremoloSpanner (multiple notes)
        output: str = ''
        layouts: list[str] = []

        trillSeen: str = ''
        trillExtStartSeen: bool = False
        for expr in m21Expressions:
            if isinstance(
                expr,
                (m21.expressions.Trill, m21.expressions.GeneralMordent, m21.expressions.Turn)
            ):
                ornStr, ornLayouts = (
                    M21Convert._getHumdrumStringAndLayoutsFromM21TrillMordentTurn(
                        expr, m21GeneralNote
                    )
                )
                output += ornStr
                layouts += ornLayouts
                if isinstance(expr, m21.expressions.Trill):
                    trillSeen = ornStr
                continue

            if isinstance(expr, (m21.expressions.Tremolo, m21.expressions.TremoloSpanner)):
                output += M21Convert._getHumdrumStringFromTremolo(
                    expr, m21GeneralNote.duration, recip, beamStarts, owner
                )
                continue

            if isinstance(expr, m21.expressions.TrillExtension):
                if m21GeneralNote and expr.isFirst(m21GeneralNote):
                    # turn any trill start into trill with wavy-line later
                    trillExtStartSeen = True
                else:
                    # continue the trill extension
                    # This should technically be 'ttt' or 'TTT', depending on
                    # whether the trill is a half or whole step trill, but it
                    # actually doesn't matter to any of the parsers I've seen,
                    # so just use 'TTT' instead of tracking trill intervals
                    # from previous notes.
                    output += 'TTT'
                continue

            if isinstance(expr, m21.expressions.Fermata):
                output += ';'
                if expr.type == 'upright':
                    output += '<'
                continue

            if isinstance(expr, m21.expressions.ArpeggioMark):
                output += ':'
                continue
            if isinstance(expr, m21.expressions.ArpeggioMarkSpanner):
                if M21Convert._allSpannedGeneralNotesInSameMeasure(expr):
                    output += ':'
                else:
                    output += '::'
                continue

        if trillSeen and trillExtStartSeen:
            # replace a 't' or 'T' (trill sign) with a 'tt' or 'TT' (trill sign + wavy line)
            re.sub(trillSeen, trillSeen + trillSeen, output, count=1)

        return output, layouts

    numberOfFlagsToDurationReciprocal: dict[int, int] = {
        0: 4,
        1: 8,
        2: 16,
        3: 32,
        4: 64,
        5: 128,
        6: 256,
        7: 512,
        8: 1024,
        9: 2048,
    }

    @staticmethod
    def _getHumdrumStringAndLayoutsFromM21TrillMordentTurn(
        orn: m21.expressions.Trill | m21.expressions.GeneralMordent | m21.expressions.Turn,
        gNote: m21.note.GeneralNote,
        _owner=None
    ) -> tuple[str, list[str]]:
        output: str = ''
        layouts: list[str] = []

        # don't re-resolve them if they're already there, you'll lose their displayStatus
        if not orn.ornamentalPitches:
            orn.resolveOrnamentalPitches(gNote)

        accid: str
        if isinstance(orn, m21.expressions.Trill):
            # one ornamental pitch, either above (Trill) or below (InvertedTrill)
            # Humdrum doesn't really support InvertedTrill, so we just do the best
            # we can by putting it below the note.
            if orn.ornamentalPitch is not None:
                if (orn.ornamentalPitch.accidental
                        and orn.ornamentalPitch.accidental.displayStatus):
                    accid = m21.pitch.accidentalNameToModifier.get(
                        orn.ornamentalPitch.accidental.name, ''
                    )
                    if accid:
                        layouts.append(f'!LO:TR:acc={accid}')

            semitones: float = 0.0
            if gNote.pitches:
                intv = m21.interval.Interval(gNote.pitches[0], orn.ornamentalPitch)
                semitones = float(intv.chromatic.semitones)

            if semitones == 0:
                # trill on Unpitched.  Call it 't'
                output = 't'
            elif abs(semitones) <= 1:
                if semitones > 0:
                    output = 't'
                else:
                    output = 't<'
            else:
                if semitones > 0:
                    output = 'T'
                else:
                    output = 'T<'

            return output, layouts

        if isinstance(orn, m21.expressions.GeneralMordent):
            # one ornamental pitch, either above (InvertedMordent) or below (Mordent)
            # 'M' and 'm' are above, 'W' and 'w' are below.
            if orn.ornamentalPitch is not None:
                if (orn.ornamentalPitch.accidental
                        and orn.ornamentalPitch.accidental.displayStatus):
                    accid = m21.pitch.accidentalNameToModifier.get(
                        orn.ornamentalPitch.accidental.name, ''
                    )
                    if accid:
                        layouts.append(f'!LO:MOR:acc={accid}')

            semitones = 0.0
            if gNote.pitches:
                intv = m21.interval.Interval(gNote.pitches[0], orn.ornamentalPitch)
                semitones = float(intv.chromatic.semitones)

            if semitones == 0:
                # mordent on Unpitched.  Call it 'm'
                output = 't'
            elif abs(semitones) <= 1:
                if semitones > 0:
                    output = 'm'
                else:
                    output = 'w'
            else:
                if semitones > 0:
                    output = 'M'
                else:
                    output = 'W'

            return output, layouts

        if isinstance(orn, m21.expressions.Turn):
            # two ornamental pitches, one above and one below
            if orn.upperOrnamentalPitch is not None:
                if (orn.upperOrnamentalPitch.accidental
                        and orn.upperOrnamentalPitch.accidental.displayStatus):
                    accid = m21.pitch.accidentalNameToModifier.get(
                        orn.upperOrnamentalPitch.accidental.name, ''
                    )
                    if accid:
                        layouts.append(f'!LO:TURN:uacc={accid}')

            if orn.lowerOrnamentalPitch is not None:
                if (orn.lowerOrnamentalPitch.accidental
                        and orn.lowerOrnamentalPitch.accidental.displayStatus):
                    accid = m21.pitch.accidentalNameToModifier.get(
                        orn.lowerOrnamentalPitch.accidental.name, ''
                    )
                    if accid:
                        layouts.append(f'!LO:TURN:lacc={accid}')

            # '$..' is inverted
            # 'S..' is not inverted
            # 's' at the start before '$..' or 'S..' means not delayed
            # The values of the '..' characters describe how many semitones the upper and
            # lower notes are above and below the main note.
            prefix: str
            if isinstance(orn, m21.expressions.InvertedTurn):
                if orn.isDelayed:
                    # delayed, inverted
                    prefix = '$'
                else:
                    # not delayed, inverted
                    prefix = 's$'
            else:
                if orn.isDelayed:
                    # delayed, not inverted
                    prefix = 'S'
                else:
                    # not delayed, not inverted
                    prefix = 'sS'

            upperCh: str
            lowerCh: str
            semitones = 0.0
            if gNote.pitches:
                intv = m21.interval.Interval(gNote.pitches[0], orn.upperOrnamentalPitch)
                semitones = float(intv.chromatic.semitones)

            if semitones == 0:
                # turn on Unpitched, call it 's'
                upperCh = 's'
            elif abs(semitones) <= 1:
                upperCh = 's'
            else:
                upperCh = 'S'

            if gNote.pitches:
                intv = m21.interval.Interval(gNote.pitches[0], orn.lowerOrnamentalPitch)
                semitones = float(intv.chromatic.semitones)

            if semitones == 0:
                # turn on Unpitched, call it 's'
                lowerCh = 's'
            elif abs(semitones) <= 1:
                lowerCh = 's'
            else:
                lowerCh = 'S'

            output = prefix + upperCh + lowerCh

            return output, layouts

        return '', []  # we should never get here


    @staticmethod
    def _getHumdrumStringFromTremolo(
        tremolo: m21.expressions.Tremolo | m21.expressions.TremoloSpanner,
        duration: m21.duration.Duration,
        recip: str,
        beamStarts: int | None,
        _owner=None
    ) -> str:
        output: str = ''
        fingered: bool
        if isinstance(tremolo, m21.expressions.Tremolo):
            fingered = False
        elif isinstance(tremolo, m21.expressions.TremoloSpanner):
            fingered = True
        else:
            raise HumdrumInternalError('tremolo is not of an appropriate type')

        tvalue: HumNum
        tvFraction: Fraction
        tvInt: int | None = (
            M21Convert.numberOfFlagsToDurationReciprocal.get(tremolo.numberOfMarks, None)
        )
        if tvInt is not None:
            tvalue = opFrac(tvInt)
            if fingered:
                # fingered tremolo (2 notes)
                if beamStarts and duration.quarterLength < 1:
                    # ignore beamStarts for quarter-notes and above
                    tvalue *= beamStarts
                if duration.tuplets and len(duration.tuplets) == 1:
                    tvalue /= duration.tuplets[0].tupletMultiplier()
                tvFraction = Fraction(tvalue)
                if tvFraction.denominator == 1:
                    output = f'@@{tvFraction.numerator}@@'
                else:
                    output = f'@@{tvFraction.numerator}%{tvFraction.denominator}@@'
            else:
                # bowed tremolo (one note)
                durNoDots: HumNum = Convert.recipToDurationNoDots(recip)
                if 0 < durNoDots < 1:
                    dval: float = - math.log2(float(durNoDots))
                    twopow: int = int(dval)
                    tvalue *= (1 << twopow)
                if duration.tuplets and len(duration.tuplets) == 1:
                    tvalue /= duration.tuplets[0].tupletMultiplier()
                tvFraction = Fraction(tvalue)
                if tvFraction.denominator == 1:
                    output = f'@{tvFraction.numerator}@'
                else:
                    output = f'@{tvFraction.numerator}%{tvFraction.denominator}@'

        return output

    @staticmethod
    def _getHumdrumBeamStringFromM21Beams(m21Beams: m21.beam.Beams) -> str:
        output: str = ''

        beamStarts: int = 0
        beamEnds: int = 0
        hookForwards: int = 0
        hookBacks: int = 0

        for beam in m21Beams:
            if beam.type == 'start':
                beamStarts += 1
            elif beam.type == 'stop':
                beamEnds += 1
            elif beam.type == 'continue':
                pass
            elif beam.type == 'partial':
                if beam.direction == 'left':
                    hookBacks += 1
                elif beam.direction == 'right':
                    hookForwards += 1

        output += 'J' * beamEnds
        output += 'k' * hookBacks
        output += 'K' * hookForwards
        output += 'L' * beamStarts

        return output

    @staticmethod
    def _getHumdrumBeamStringFromM21GeneralNote(m21GeneralNote: m21.note.GeneralNote) -> str:
        if not isinstance(m21GeneralNote, m21.note.NotRest):
            # Rests don't have beams, NotRest is where they live
            return ''

        return M21Convert._getHumdrumBeamStringFromM21Beams(m21GeneralNote.beams)

    @staticmethod
    def _getHumdrumStemDirStringFromM21GeneralNote(m21GeneralNote: m21.note.GeneralNote) -> str:
        if not isinstance(m21GeneralNote, m21.note.NotRest):
            # Rests don't have stemdirection, NotRest is where they live
            return ''

        if m21GeneralNote.stemDirection == 'down':
            return '\\'
        if m21GeneralNote.stemDirection == 'up':
            return '/'

        return ''

    @staticmethod
    def isCentered(m21Obj: m21.base.Music21Object) -> bool:
        if not m21Obj.hasStyleInformation:
            return False

        placement: str = ''
        if hasattr(m21Obj, 'placement'):
            placement = m21Obj.placement  # type: ignore
        elif hasattr(m21Obj.style, 'placement'):
            placement = m21Obj.style.placement  # type: ignore

        if placement != 'below':
            return False

        if not hasattr(m21Obj.style, 'alignVertical'):
            return False

        return m21Obj.style.alignVertical == 'middle'  # type: ignore

    @staticmethod
    def _getSfOrSfzFromM21GeneralNote(
        m21GeneralNote: m21.note.GeneralNote
    ) -> str:
        if not hasattr(m21GeneralNote, 'humdrum_sf_or_sfz'):
            return ''

        dynam = m21GeneralNote.humdrum_sf_or_sfz  # type: ignore
        if t.TYPE_CHECKING:
            assert isinstance(dynam, m21.dynamics.Dynamic)

        dynString: str = M21Convert.getDynamicString(dynam)

        suffix: str = ''
        if dynam.placement == 'above':
            suffix = '>'
        elif dynam.placement == 'below':
            suffix = '<'

        if dynString == 'sf':
            return 'z' + suffix
        if dynString == 'sfz':
            return 'zz' + suffix

        return ''

    @staticmethod
    def _getDynamicsLayoutsFromM21GeneralNote(
        m21GeneralNote: m21.note.GeneralNote
    ) -> list[str]:
        if not hasattr(m21GeneralNote, 'humdrum_sf_or_sfz'):
            return []

        dynam = m21GeneralNote.humdrum_sf_or_sfz  # type: ignore
        if t.TYPE_CHECKING:
            assert isinstance(dynam, m21.dynamics.Dynamic)

        dparam: str = M21Convert.getDynamicOnNoteParameters(dynam)
        if dparam:
            return ['!LO:DY' + dparam]
        return []

    @staticmethod
    def _getTieStartStopAndLayoutsFromM21GeneralNote(
        m21GeneralNote: m21.note.GeneralNote
    ) -> tuple[str, str, list[str]]:
        if m21GeneralNote.tie is None:
            return ('', '', [])

        tieStr: str = ''
        layouts: list[str] = []

        tieStyle: str = m21GeneralNote.tie.style
        tiePlacement: str = m21GeneralNote.tie.placement
        tieType: str = m21GeneralNote.tie.type
        if tieType == 'start':
            tieStr += '['
        elif tieType == 'stop':
            tieStr += ']'
        elif tieType == 'continue':
            tieStr += '_'

        # style and placement are ignored/never set on tie stop
        if tieType in ('start', 'continue'):
            if tieStyle == 'hidden':
                # ignore placement if hidden
                tieStr += 'y'
            else:
                if tiePlacement == 'above':
                    # we don't report this up, since we always have '>' RDF signifier
                    tieStr += '>'
                elif tiePlacement == 'below':
                    # we don't report this up, since we always have '<' RDF signifier
                    tieStr += '<'

                if tieStyle == 'dotted':
                    layouts.append('!LO:T:dot')
                elif tieStyle == 'dashed':
                    layouts.append('!LO:T:dash')

        if tieType == 'start':
            return (tieStr, '', layouts)
        if tieType in ('stop', 'continue'):
            return ('', tieStr, layouts)

        return ('', '', [])

    _repeatBothStyleCombos: dict = {}

    @staticmethod
    def _setupRepeatBothStyleComboLookup() -> None:
        theLookup: dict = {}

        # both the same = same (don't add them together)
        # Example: if you want heavy-heavy, don't put heavy on both, put heavy-heavy on both.
        for vStyle in MeasureVisualStyle:
            theLookup[(vStyle, vStyle)] = vStyle

        # the special triple styles (heavy-light-heavy and light-heavy-light)
        # should never be looked up, so put something reasonable there, like
        # "use the first triple in the tuple"
        for vStyle in MeasureVisualStyle:
            theLookup[(MeasureVisualStyle.HeavyLightHeavy, vStyle)] = (
                MeasureVisualStyle.HeavyLightHeavy
            )
            theLookup[(MeasureVisualStyle.LightHeavyLight, vStyle)] = (
                MeasureVisualStyle.LightHeavyLight
            )

        # standard "both" combos first:
        # heavy-light + light-heavy (final) = heavy-light-heavy
        # light-heavy (final) + heavy-light = light-heavy-light
        theLookup[(MeasureVisualStyle.HeavyLight, MeasureVisualStyle.Final)] = (
            MeasureVisualStyle.HeavyLightHeavy
        )
        theLookup[(MeasureVisualStyle.Final, MeasureVisualStyle.HeavyLight)] = (
            MeasureVisualStyle.LightHeavyLight
        )

        # different (and our humdrum parser wouldn't produce this),
        # but obviously add up to another that makes sense:
        #   heavy + light-heavy (final)   = heavy-light-heavy
        #   heavy-light + heavy           = heavy-light-heavy
        #   regular + heavy-light         = light-heavy-light
        #   light-heavy (final) + regular = light-heavy-light
        theLookup[(MeasureVisualStyle.Heavy, MeasureVisualStyle.Final)] = (
            MeasureVisualStyle.HeavyLightHeavy
        )
        theLookup[(MeasureVisualStyle.HeavyLight, MeasureVisualStyle.Heavy)] = (
            MeasureVisualStyle.HeavyLightHeavy
        )
        theLookup[(MeasureVisualStyle.Regular, MeasureVisualStyle.HeavyLight)] = (
            MeasureVisualStyle.LightHeavyLight
        )
        theLookup[(MeasureVisualStyle.Final, MeasureVisualStyle.Regular)] = (
            MeasureVisualStyle.LightHeavyLight
        )

        # weird cases humdrum doesn't support (and don't make sense):
        #   heavy + light = heavy-light -> ':!|:' which is just weird
        #   light + heavy = light-heavy -> ':|!:' which is just weird
        theLookup[(MeasureVisualStyle.Heavy, MeasureVisualStyle.Regular)] = (
            MeasureVisualStyle.HeavyLight
        )
        theLookup[(MeasureVisualStyle.Regular, MeasureVisualStyle.Heavy)] = (
            MeasureVisualStyle.Final
        )

        M21Convert._repeatBothStyleCombos = theLookup

        # fill in the rest:
        for vStyle1 in MeasureVisualStyle:
            for vStyle2 in MeasureVisualStyle:
                combo = theLookup.get((vStyle1, vStyle2), None)
                if combo is None:
                    # different styles, and it's not one of the triple-style cases above

                    # Invisible trumps everything
                    if (vStyle1 is MeasureVisualStyle.Invisible
                            or vStyle2 is MeasureVisualStyle.Invisible):
                        theLookup[(vStyle1, vStyle2)] = MeasureVisualStyle.Invisible
                        continue

                    # Regular doesn't add anything
                    if (vStyle1 is MeasureVisualStyle.Regular):
                        theLookup[(vStyle1, vStyle2)] = vStyle2
                        continue
                    if (vStyle2 is MeasureVisualStyle.Regular):
                        theLookup[(vStyle1, vStyle2)] = vStyle1
                        continue

                    # Anything else (different styles, neither is Regular or Invisible
                    # or NoBarline, and it's not one of the triple-style cases above),
                    # vStyle1 wins
                    theLookup[(vStyle1, vStyle2)] = vStyle1

    @staticmethod
    def _combineVisualRepeatBothStyles(
        style1: MeasureVisualStyle,
        style2: MeasureVisualStyle
    ) -> MeasureVisualStyle:
        if not M21Convert._repeatBothStyleCombos:
            M21Convert._setupRepeatBothStyleComboLookup()

        return M21Convert._repeatBothStyleCombos[(style1, style2)]

    @staticmethod
    def combineTwoMeasureStyles(
        currMeasureBeginStyle: MeasureStyle,
        prevMeasureEndStyle: MeasureStyle
    ) -> MeasureStyle:
        outputMType: MeasureType = currMeasureBeginStyle.mType
        outputVStyle: MeasureVisualStyle = currMeasureBeginStyle.vStyle
        if prevMeasureEndStyle.mType == MeasureType.RepeatBackward:
            if currMeasureBeginStyle.mType == MeasureType.RepeatForward:
                outputMType = MeasureType.RepeatBoth
                outputVStyle = M21Convert._combineVisualRepeatBothStyles(
                    prevMeasureEndStyle.vStyle,
                    outputVStyle
                )
            else:
                outputMType = MeasureType.RepeatBackward
                outputVStyle = prevMeasureEndStyle.vStyle
        else:
            # just take the "more complex" of the two
            outputMType = max(outputMType, prevMeasureEndStyle.mType)
            outputVStyle = max(outputVStyle, prevMeasureEndStyle.vStyle)

        return M21Convert.getMeasureStyle(outputVStyle, outputMType)

    _measureStyleLookup: dict = {}

    @staticmethod
    def _computeMeasureStyleLookup() -> None:
        theLookup: dict = {}

        for style in MeasureStyle:
            theLookup[(style.vStyle, style.mType)] = style

        M21Convert._measureStyleLookup = theLookup

    @staticmethod
    def getMeasureStyle(vStyle: MeasureVisualStyle, mType: MeasureType) -> MeasureStyle:
        if not M21Convert._measureStyleLookup:
            M21Convert._computeMeasureStyleLookup()
        return M21Convert._measureStyleLookup[(vStyle, mType)]

    measureVisualStyleFromM21BarlineType: dict[str, MeasureVisualStyle] = {
        'regular': MeasureVisualStyle.Regular,
        'dotted': MeasureVisualStyle.Dotted,
        'dashed': MeasureVisualStyle.Regular,  # no dashed in humdrum
        'heavy': MeasureVisualStyle.Heavy,
        'double': MeasureVisualStyle.Double,   # a.k.a. light-light
        'final': MeasureVisualStyle.Final,     # a.k.a. light-heavy
        'heavy-light': MeasureVisualStyle.HeavyLight,
        'heavy-heavy': MeasureVisualStyle.HeavyHeavy,
        'tick': MeasureVisualStyle.Tick,
        'short': MeasureVisualStyle.Short,
        'none': MeasureVisualStyle.Invisible
    }

    @staticmethod
    def measureStyleFromM21Barline(m21Barline: m21.bar.Barline) -> MeasureStyle:
        vStyle: MeasureVisualStyle = MeasureVisualStyle.Regular
        mType: MeasureType = MeasureType.NotRepeat
        if m21Barline is None:
            return MeasureStyle.Regular

        if isinstance(m21Barline, m21.bar.Repeat):
            if m21Barline.direction == 'start':
                mType = MeasureType.RepeatForward
            else:
                # direction == 'end'
                mType = MeasureType.RepeatBackward
        vStyle = M21Convert.measureVisualStyleFromM21BarlineType[m21Barline.type]
        return M21Convert.getMeasureStyle(vStyle, mType)

    @staticmethod
    def fermataStyleFromM21Barline(barline: m21.bar.Barline) -> FermataStyle:
        if not isinstance(barline, m21.bar.Barline):
            return FermataStyle.NoFermata
        return M21Convert.fermataStyleFromM21Fermata(barline.pause)


    # m21Barline is ordered, because we want to iterate over the keys,
    # and find '||' before '|', for example
    m21BarlineTypeFromHumdrumType: dict[str, str] = {
        '||': 'double',      # a.k.a. 'light-light' in MusicXML
        '!!': 'heavy-heavy',
        '!|': 'heavy-light',
        '|!': 'final',       # a.k.a. 'light-heavy' in MusicXML
        '==': 'final',       # a.k.a. 'light-heavy' in MusicXML
        '\'': 'short',
        '`': 'tick',
        '-': 'none',
        '|': 'regular',      # barlines are 'regular' by default (e.g. '=3' is 'regular')
        '!': 'heavy',
        '.': 'dotted',
        ':': 'dashed'
    }

    @staticmethod
    def _m21BarlineTypeFromHumdrumString(measureString: str) -> str:
        for humdrumType in M21Convert.m21BarlineTypeFromHumdrumType:
            if humdrumType in measureString:
                return M21Convert.m21BarlineTypeFromHumdrumType[humdrumType]
        return 'regular'  # default m21BarlineType

    @staticmethod
    def _m21BarlineTypeFromHumdrumRepeatString(measureString: str, side: str) -> str:
        # side is 'left' or 'right', describing which end of a measure this repeat string
        # should be interpreted for
        if side == 'left':
            # left barline is created from the rightmost portion of the measureString
            if ':!|!:' in measureString:
                return M21Convert._m21BarlineTypeFromHumdrumString('|!:')
            if ':|!|:' in measureString:
                return M21Convert._m21BarlineTypeFromHumdrumString('!|:')
            if ':||:' in measureString:
                return M21Convert._m21BarlineTypeFromHumdrumString('||:')
            if ':!:' in measureString:
                return M21Convert._m21BarlineTypeFromHumdrumString('!:')
            if ':|:' in measureString:
                return M21Convert._m21BarlineTypeFromHumdrumString('|:')
            if '|:' in measureString or '!:' in measureString:
                return M21Convert._m21BarlineTypeFromHumdrumString(measureString)

            # this is not a left barline repeat, so we should not have been called
            raise HumdrumInternalError(
                f'measureString does not contain left barline repeat: {measureString}'
            )

        if side == 'right':
            # right barline is created from the leftmost portion of the humdrumRepeatType
            if ':!|!:' in measureString:
                return M21Convert._m21BarlineTypeFromHumdrumString(':!|')
            if ':|!|:' in measureString:
                return M21Convert._m21BarlineTypeFromHumdrumString(':|!')
            if ':||:' in measureString:
                return M21Convert._m21BarlineTypeFromHumdrumString(':||')
            if ':!:' in measureString:
                return M21Convert._m21BarlineTypeFromHumdrumString(':!')
            if ':|:' in measureString:
                return M21Convert._m21BarlineTypeFromHumdrumString(':|')
            if ':|' in measureString or ':!' in measureString:
                return M21Convert._m21BarlineTypeFromHumdrumString(measureString)

            # this is not a right barline repeat, so we should not have been called
            raise HumdrumInternalError(
                f'measureString does not contain right barline repeat: {measureString}'
            )

        # should not ever get here
        raise HumdrumInternalError(f'side should be "left" or "right", not "{side}"')

    @staticmethod
    def m21BarlineFromHumdrumString(
        measureString: str,
        side: str
    ) -> m21.bar.Barline:  # can return m21.bar.Repeat (which is a Barline)
        # side is 'left' or 'right', describing which end of a measure this measureString
        # should be interpreted for
        outputBarline: m21.bar.Barline | None = None
        if side == 'right':
            # handle various repeats
            if (':|' in measureString
                    or ':!' in measureString):
                # right barline is an end repeat
                outputBarline = m21.bar.Repeat(direction='end')
                outputBarline.type = (
                    M21Convert._m21BarlineTypeFromHumdrumRepeatString(measureString, side)
                )
            elif ('|:' in measureString
                    or '!:' in measureString):
                # right barline is NOT an end repeat, but next measure's left barline
                # is a start repeat; our right barline (which lands at the same spot)
                # should just be regular, to blend in silently
                outputBarline = m21.bar.Barline('regular')
        elif side == 'left':
            # handle various repeats
            if ('|:' in measureString
                    or '!:' in measureString):
                # left barline is a start repeat
                outputBarline = m21.bar.Repeat(direction='start')
                outputBarline.type = (
                    M21Convert._m21BarlineTypeFromHumdrumRepeatString(measureString, side)
                )
            elif (':|' in measureString
                    or ':!' in measureString):
                # left barline is NOT a start repeat, but previous measure's right barline
                # is an end repeat; our left barline (which lands at the same spot) should
                # just be regular, to blend in silently
                outputBarline = m21.bar.Barline('regular')

        if outputBarline is None:
            barlineType: str = M21Convert._m21BarlineTypeFromHumdrumString(measureString)
            outputBarline = m21.bar.Barline(barlineType)

        return outputBarline

    @staticmethod
    def fermataStyleFromM21Fermata(m21Fermata: m21.expressions.Fermata) -> FermataStyle:
        if not isinstance(m21Fermata, m21.expressions.Fermata):
            return FermataStyle.NoFermata

        output: FermataStyle = FermataStyle.Fermata
        if m21Fermata.hasStyleInformation and m21Fermata.style == 'upright':
            output = FermataStyle.FermataBelow
#         elif m21Fermata.hasStyleInformation and m21Fermata.style == 'inverted':
#             # leave it as a normal Fermata, this is m21's default
#             output = FermataStyle.FermataAbove

        return output

    @staticmethod
    def combineTwoFermataStyles(
        currMeasureBeginFermata: FermataStyle,
        prevMeasureEndFermata: FermataStyle
    ) -> FermataStyle:
        # simple combination for now: if either is a fermata, use it as the combination
        # if both are a fermata, use the current measure's begin fermata
        # if neither is a fermata, return FermataStyle.NoFermata
        if currMeasureBeginFermata != FermataStyle.NoFermata:
            return currMeasureBeginFermata
        if prevMeasureEndFermata != FermataStyle.NoFermata:
            return prevMeasureEndFermata
        return FermataStyle.NoFermata

    @staticmethod
    def humdrumMetadataValueToM21MetadataValue(humdrumValue: m21.metadata.Text) -> t.Any:
        m21Value: m21.metadata.Text | m21.metadata.DatePrimitive | None = None

        if humdrumValue.encodingScheme == 'humdrum:date':
            # convert to m21.metadata.DateXxxx
            m21Value = M21Utilities.m21DatePrimitiveFromString(str(humdrumValue))
            if m21Value is None:
                # wouldn't convert to DateXxxx, leave it as Text
                m21Value = humdrumValue
        else:
            # default is m21.metadata.Text (even for Contributors)
            m21Value = humdrumValue

        return m21Value

    @staticmethod
    def m21UniqueNameToHumdrumKeyWithoutIndexOrLanguage(uniqueName: str) -> str | None:
        hdKey: str | None = (
            M21Utilities.m21MetadataPropertyUniqueNameToHumdrumReferenceKey.get(uniqueName, None)
        )

        if hdKey is None:
            # see if it was a 'humdrumraw:XXX' passthru
            if uniqueName.startswith('humdrumraw:'):
                hdKey = uniqueName[11:]

        return hdKey

    @staticmethod
    def m21MetadataItemToHumdrumKeyWithoutIndex(
        uniqueName: str,
        value: t.Any
    ) -> str | None:
        hdKey: str | None = (
            M21Utilities.m21MetadataPropertyUniqueNameToHumdrumReferenceKey.get(uniqueName, None)
        )

        if hdKey is None:
            # see if it was a 'humdrumraw:XXX' passthru
            if uniqueName.startswith('humdrumraw:'):
                hdKey = uniqueName[11:]

        if isinstance(value, m21.metadata.Text):
            if value.language:
                if value.isTranslated:
                    hdKey += '@' + value.language.upper()
                else:
                    hdKey += '@@' + value.language.upper()
        return hdKey

    @staticmethod
    def humdrumMetadataItemToHumdrumReferenceLineStr(
        idx: int,
        hdKey: str,
        value: t.Any
    ) -> str | None:
        valueStr: str = M21Utilities.m21MetadataValueToString(value)
        refLineStr: str = ''

        if idx > 0:
            # we generate 'XXX', 'XXX1', 'XXX2', etc
            hdKey += str(idx)

        if isinstance(value, m21.metadata.Text):
            if value.language:
                if value.isTranslated:
                    hdKey += '@' + value.language.upper()
                else:
                    hdKey += '@@' + value.language.upper()

        if valueStr == '':
            refLineStr = '!!!' + hdKey + ':'
        else:
            refLineStr = '!!!' + hdKey + ': ' + valueStr

        return refLineStr

    @staticmethod
    def m21MetadataItemToHumdrumReferenceLineStr(
        idx: int,         # this is the index to insert into the hdKey
        uniqueName: str,
        value: t.Any
    ) -> str | None:
        valueStr: str = ''
        refLineStr: str = ''
        isRaw: bool = False
        isNonRawHumdrum: bool = False

        if uniqueName.startswith('raw:'):
            uniqueName = uniqueName[4:]
            isRaw = True
        elif uniqueName.startswith('humdrumraw:'):
            uniqueName = uniqueName[11:]
            isRaw = True
        elif uniqueName.startswith('humdrum:'):
            uniqueName = uniqueName[8:]
            isNonRawHumdrum = True

        hdKey: str | None = None
        valueStr = M21Utilities.m21MetadataValueToString(value, isRaw)
        if isRaw:
            hdKey = uniqueName
        else:
            if isNonRawHumdrum:
                hdKey = uniqueName
            else:
                hdKey = M21Convert.m21UniqueNameToHumdrumKeyWithoutIndexOrLanguage(uniqueName)
            if hdKey is not None:
                if idx > 0:
                    # we generate 'XXX', 'XXX1', 'XXX2', etc
                    hdKey += str(idx)
            else:
                # must be free-form custom key... pass it thru as is (no indexing)
                hdKey = uniqueName

            if isinstance(value, m21.metadata.Contributor):
                if value._names[0].language:
                    if value._names[0].isTranslated:
                        hdKey += '@' + value._names[0].language.upper()
                    else:
                        hdKey += '@@' + value._names[0].language.upper()
            elif isinstance(value, m21.metadata.Text):
                if value.language:
                    if value.isTranslated:
                        hdKey += '@' + value.language.upper()
                    else:
                        hdKey += '@@' + value.language.upper()

        if t.TYPE_CHECKING:
            assert hdKey is not None

        if valueStr == '':
            refLineStr = '!!!' + hdKey + ':'
        else:
            refLineStr = '!!!' + hdKey + ': ' + valueStr

        return refLineStr
