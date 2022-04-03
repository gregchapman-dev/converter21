# ------------------------------------------------------------------------------
# Name:          M21Convert.py
# Purpose:       Conversion between HumdrumToken (etc) and music21 objects
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------

#    All methods are static.  M21Convert is just a namespace for these conversion functions and
#    look-up tables.

import sys
import re
import math
from typing import Union, List, Tuple, OrderedDict, Optional, Type
from fractions import Fraction
import music21 as m21

from converter21.humdrum import MeasureStyle, MeasureVisualStyle, MeasureType
from converter21.humdrum import FermataStyle
from converter21.humdrum import HumdrumInternalError
from converter21.humdrum import HumdrumExportError
from converter21.humdrum import HumNum
from converter21.humdrum import HumdrumToken
from converter21.humdrum import Convert
from converter21.humdrum import M21Utilities

class M21Convert:
    humdrumMensurationSymbolToM21TimeSignatureSymbol = {
        'c':    'common',   # modern common time (4/4)
        'c|':   'cut',      # modern cut time (2/2)
#       'C':    '',        # mensural common (not supported in music21)
#       'C|':    '',       # mensural cut (2/1) (not supported in music21)
#       'O':    '',        # mensural 'O' (not supported in music21)
#       'O|':   '',        # mensural 'cut O' (not supported in music21)
    }

    m21TimeSignatureSymbolToHumdrumMensurationSymbol = {
        'common': 'c',   # modern common time (4/4)
        'cut': 'c|',    # modern cut time (2/2)
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

    m21ContributorRoleToHumdrumReferenceKey = {
        'composer'                  : 'COM',
        'attributed composer'       : 'COA',
        'suspected composer'        : 'COS',
        'composer alias'            : 'COL',
        'corporate composer'        : 'COC',
        'lyricist'                  : 'LYR',
        'librettist'                : 'LIB',
        'arranger'                  : 'LAR',
        'orchestrator'              : 'LOR',
        'translator'                : 'TRN',
        'original document owner'   : 'YOO',
        'original editor'           : 'YOE',
        'electronic editor'         : 'EED',
        'electronic encoder'        : 'ENC'
    }

    humdrumReferenceKeys: Tuple[str] = (
        # Authorship information:
        'COM', # composer's name
        'COA', # attributed composer
        'COS', # suspected composer
        'COL', # composer's abbreviated, alias, or stage name
        'COC', # composer's corporate name
        'CDT', # composer's birth and death dates (**zeit format)
        'CBL', # composer's birth location
        'CDL', # composer's death location
        'CNT', # composer's nationality
        'LYR', # lyricist's name
        'LIB', # librettist's name
        'LAR', # music arranger's name
        'LOR', # orchestrator's name
        'TXO', # original language of vocal/choral text
        'TXL', # language of the encoded vocal/choral text
        # Recording information (if the Humdrum encodes information pertaining to an audio recording)
        'TRN', # translator of the text
        'RTL', # album title
        'RMM', # manufacturer or sponsoring company
        'RC#', # recording company's catalog number of album
        'RRD', # release date (**date format)
        'RLC', # place of recording
        'RNP', # producer's name
        'RDT', # date of recording (**date format)
        'RT#', # track number
        # Performance information (if the Humdrum encodes, say, a MIDI performance)
        'MGN', # ensemble's name
        'MPN', # performer's name
        'MPS', # suspected performer
        'MRD', # date of performance (**date format)
        'MLC', # place of performance
        'MCN', # conductor's name
        'MPD', # date of first performance (**date format)
        'MDT', # unknown, but I've seen 'em (another way to say date of performance?)
        # Work identification information
        'OTL', # title
        'OTP', # popular title
        'OTA', # alternative title
        'OPR', # title of parent work
        'OAC', # act number (e.g. '2' or 'Act 2')
        'OSC', # scene number (e.g. '3' or 'Scene 3')
        'OMV', # movement number (e.g. '4', or 'mov. 4', or...)
        'OMD', # movement name
        'OPS', # opus number (e.g. '23', or 'Opus 23')
        'ONM', # number (e.g. '5', or 'No. 5')
        'OVM', # volume number (e.g. '6' or 'Vol. 6')
        'ODE', # dedicated to
        'OCO', # commissioned by
        'OCL', # collected/transcribed by
        'ONB', # free form note (nota bene) related to title or identity of work
        'ODT', # date or period of composition (**date or **zeit format)
        'OCY', # country of composition
        'OPC', # city, town, or village of composition
        # Group information
        'GTL', # group title (e.g. 'The Seasons')
        'GAW', # associated work, such as a play or film
        'GCO', # collection designation (e.g. 'Norton Scores')
        # Imprint information
        'PUB', # publication status 'published'/'unpublished'
        'PED', # publication editor
        'PPR', # first publisher
        'PDT', # date first published (**date format)
        'PTL', # publication (volume) title
        'PPP', # place first published
        'PC#', # publisher's catalog number (NOT scholarly catalog, see below)
        'SCT', # scholarly catalog abbreviation and number (e.g. 'BWV 551')
        'SCA', # scholarly catalog (unabbreviated) (e.g. 'Koechel 117')
        'SMS', # unpublished manuscript source name
        'SML', # unpublished manuscript location
        'SMA', # acknowledgment of manuscript access
        # Copyright information
        'YEP', # publisher of electronic edition
        'YEC', # date and owner of electronic copyright
        'YER', # date electronic edition released
        'YEM', # copyright message (e.g. 'All rights reserved')
        'YEN', # country of copyright
        'YOR', # original document from which encoded document was prepared
        'YOO', # original document owner
        'YOY', # original copyright year
        'YOE', # original editor
        'EED', # electronic editor
        'ENC', # electronic encoder (person)
        'END', # encoding date
        'EMD', # electronic document modification description (one per modificiation)
        'EEV', # electronic edition version
        'EFL', # file number e.g. '1/4' for one of four
        'EST', # encoding status (free form, normally eliminated prior to distribution)
        'VTS', # checksum (excluding the VTS line itself)
        # Analytic information
        'ACO', # collection designation
        'AFR', # form designation
        'AGN', # genre designation
        'AST', # style, period, or type of work designation
        'AMD', # mode classification e.g. '5; Lydian'
        'AMT', # metric classification, must be one of eight specific names, e.g. 'simple quadruple'
        'AIN', # instrumentation, must be alphabetically ordered list of *I abbrevs, space-delimited
        'ARE', # geographical region of origin (list of 'narrowing down' names of regions)
        'ARL', # geographical location of origin (lat/long)
        # Historical and background information
        'HAO', # aural history (lots of text, stories about the work)
        'HTX', # freeform translation of vocal text
        # Representation information
        'RLN', # Extended ASCII language code
        'RDT', # date encoded (**date format)
        'RNB', # a note about the representation
        'RWB', # a warning about the representation
    )

    humdrumDecoGroupStyleToM21GroupSymbol = {
        '{':    'brace',
        '[':    'bracket',
        '<':    'square',   # what is this one supposed to be, it's often ignored in iohumdrum.cpp
    }

    m21GroupSymbolToHumdrumDecoGroupStyleStart = {
        'brace':    '{',
        'bracket':  '[',
        'square':   '<',    # what is this one supposed to be, it's often ignored in iohumdrum.cpp
        'line':     '',     # humdrum doesn't have line, but "no style" is close
    }

    m21GroupSymbolToHumdrumDecoGroupStyleStop = {
        'brace':    '}',
        'bracket':  ']',
        'square':   '>',    # what is this one supposed to be, it's often ignored in iohumdrum.cpp
        'line':     '',     # humdrum doesn't have line, but "no style" is close
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

    numSharpsToHumdrumStandardKeyStrings = {
        0:  '',
        1:  'f#',
        2:  'f#c#',
        3:  'f#c#g#',
        4:  'f#c#g#d#',
        5:  'f#c#g#d#a#',
        6:  'f#c#g#d#a#e#',
        7:  'f#c#g#d#a#e#b#',
        -1: 'b-',
        -2: 'b-e-',
        -3: 'b-e-a-',
        -4: 'b-e-a-d-',
        -5: 'b-e-a-d-g-',
        -6: 'b-e-a-d-g-c-',
        -7: 'b-e-a-d-g-c-f-',
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

    m21ModeToHumdrumMode = {
        'dorian': 'dor',
        'phrygian': 'phr',
        'lydian': 'lyd',
        'mixolydian': 'mix',
        'aeolian': 'aeo',
        'ionian': 'ion',
        'locrian': 'loc',
    }

    # place articulations in stacking order (nearest to furthest from note)
    humdrumArticulationStringToM21ArticulationClassName: OrderedDict = OrderedDict([
        ("'",   'Staccato'),
        ('`',   'Staccatissimo'),
        ('~',   'Tenuto'),
        ('^^',  'StrongAccent'),
        ('^',   'Accent'),
        (',',   'BreathMark'),
        ('o',   'Harmonic'),
        ('v',   'UpBow'),
        ('u',   'DownBow'),
        ('"',   'Pizzicato')
    ])

    m21ArticulationClassNameToHumdrumArticulationString: OrderedDict = OrderedDict([
        ('Staccato',        "'"),
        ('Staccatissimo',   '`'),
        ('Tenuto',          '~'),
        ('StrongAccent',    '^^'),
        ('Accent',          '^'),
        ('BreathMark',      ','),
        ('Harmonic',        'o'),
        ('UpBow',           'v'),
        ('DownBow',         'u'),
        ('Pizzicato',       '"'),
    ])

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
        if diatonic < 0:
            # no pitch here, it's an unpitched note without a note position
            return None

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
    def m21Articulations(tokenStr: str, rdfAbove: str, rdfBelow: str) -> List[m21.articulations.Articulation]:
        # music21 doesn't have different articulation lists per note in a chord, just a single
        # articulation list for the chord itself.  So we search the entire tokenStr for
        # articulations, and add them all to the chord.  This works for non-chord (note) tokens
        # as well.
        # store info about articulations in various dicts, keyed by humdrum articulation string
        # which is usually a single character, but can be two (e.g. '^^')
        articFound: dict = {} # value is bool
        articPlacement: dict = {} # value is 'below', 'above', or ''
        articIsGestural: dict = {} # value is bool (gestural means "not printed on the page, but it's what the performer did")

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
            if i+1 < tsize:
                ch1 = tokenStr[i+1]
            if ch == '^' and ch1 == '^':
                ch = '^^'
                ch1 = ''
                skipNChars = 1
                if i+skipNChars+1 < tsize:
                    ch1 = tokenStr[i+skipNChars+1]
            elif ch == "'" and ch1 == "'":
                # staccatissimo alternate (eventually remove)
                ch = '`'
                ch1 = ''
                skipNChars = 1
                if i+skipNChars+1 < tsize:
                    ch1 = tokenStr[i+skipNChars+1]

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
                if i+skipNChars+2 < tsize:
                    ch2 = tokenStr[i+skipNChars+2]
                ch3 = ''
                if i+skipNChars+3 < tsize:
                    ch3 = tokenStr[i+skipNChars+3]

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
#         addDirection(text, placement, bold, italic, token, staffindex, justification, color, vgroup);
#     }

        artics: [m21.articulations.Articulation] = []

        for humdrumArticString in M21Convert.humdrumArticulationStringToM21ArticulationClassName:
            if articFound.get(humdrumArticString, None):
                m21ArticClassName: str = M21Convert.humdrumArticulationStringToM21ArticulationClassName[humdrumArticString]
                m21ArticClass = getattr(m21.articulations, m21ArticClassName)
                if m21ArticClass is None:
                    continue
                m21Artic = m21ArticClass()
                if m21Artic is None:
                    continue
                placement: str = articPlacement[humdrumArticString]
                if placement:
                    m21Artic.placement = placement
                if articIsGestural[humdrumArticString]:
                    m21Artic.style.hideObjectOnPrint = True
                artics.append(m21Artic)

        return artics

    @staticmethod
    def m21DurationWithTuplet(token: HumdrumToken, tuplet: m21.duration.Tuplet) -> m21.duration.Duration:
        dur: HumNum = token.duration / HumNum(tuplet.tupletMultiplier())
        durNoDots: HumNum = None
        numDots: int = None
        durNoDots, numDots = Convert.computeDurationNoDotsAndNumDots(dur)
        if numDots is None:
            print(f'Cannot figure out durNoDots + numDots from {token.text} (on line number {token.lineNumber}), tuplet={tuplet}, about to crash in convertQuarterLengthToType()...', file=sys.stderr)
        durType: str = m21.duration.convertQuarterLengthToType(Fraction(durNoDots))
        #print('m21DurationWithTuplet: type = "{}", dots={}'.format(durType, numDots), file=sys.stderr)
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
    def m21IntervalFromTranspose(transpose: str) -> m21.interval.Interval:
        dia: int = None
        chroma: int = None
        dia, chroma = Convert.transToDiatonicChromatic(transpose)
        if dia is None or chroma is None:
            return None # we couldn't parse transpose string
        if dia == 0 and chroma == 0:
            return None # this is a no-op transposition, so ignore it

        # diatonic step count can be used as a generic interval type here if
        # shifted 1 away from zero (because a diatonic step count of 1 is a
        # generic 2nd, for example).
        if dia < 0:
            dia -= 1
        else:
            dia += 1

        return m21.interval.intervalFromGenericAndChromatic(dia, chroma)

    @staticmethod
    def humdrumTransposeStringFromM21Interval(interval: m21.interval.Interval) -> str:
        chroma: int = interval.semitones
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
    def kernTokenStringAndLayoutsFromM21GeneralNote(m21GeneralNote: m21.note.GeneralNote, spannerBundle: m21.spanner.SpannerBundle, owner=None) -> Tuple[str, List[str]]:
        if 'Note' in m21GeneralNote.classes:
            return M21Convert.kernTokenStringAndLayoutsFromM21Note(
                                        m21GeneralNote, spannerBundle, owner)

        if 'Rest' in m21GeneralNote.classes:
            return M21Convert.kernTokenStringAndLayoutsFromM21Rest(
                                        m21GeneralNote, spannerBundle, owner)

        if 'Chord' in m21GeneralNote.classes:
            return M21Convert.kernTokenStringAndLayoutsFromM21Chord(
                                        m21GeneralNote, spannerBundle, owner)

        if 'Unpitched' in m21GeneralNote.classes:
            return M21Convert.kernTokenStringAndLayoutsFromM21Unpitched(m21GeneralNote, spannerBundle, owner)

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
    def kernTokenStringAndLayoutsFromM21Unpitched(m21Unpitched: m21.note.Unpitched,
                                                  spannerBundle: m21.spanner.SpannerBundle,
                                                  owner=None) -> Tuple[str, List[str]]:
        prefix: str = ''
        recip: str = ''
        vdurRecip: str = ''
        recip, vdurRecip = M21Convert.kernRecipFromM21Duration(m21Unpitched.duration)
        graceType: str = M21Convert.kernGraceTypeFromM21Duration(m21Unpitched.duration)
        pitch: str = M21Convert.kernPitchFromM21Unpitched(m21Unpitched, owner)
        postfix: str = ''
        layouts: [str] = []
        prefix, postfix, layouts = M21Convert.kernPrefixPostfixAndLayoutsFromM21GeneralNote(
                                                m21Unpitched,
                                                recip,
                                                spannerBundle,
                                                isFirstNoteInChord = False,
                                                isStandaloneNote = True,
                                                owner=owner)

        if vdurRecip and postfix.count('@@') == 2:
            # we have a fingered tremolo, so a portion of visual duration doubles the actual
            # duration to make music21 do the right thing visually with a fingered tremolo.
            # We must undo this factor of 2.
            vdur: HumNum = Convert.recipToDuration(vdurRecip)
            vdur /= 2
            m21VDur: m21.duration.Duration = m21.duration.Duration(Fraction(vdur))
            vdurRecip = M21Convert.kernRecipFromM21Duration(m21VDur)[0]
            if vdurRecip == recip:
                vdurRecip = ''

        token: str = prefix + recip + graceType + pitch + postfix

        if vdurRecip:
            layouts.append('!LO:N:vis=' + vdurRecip)

        return (token, layouts)

    @staticmethod
    def kernTokenStringAndLayoutsFromM21Rest(m21Rest: m21.note.Rest, spannerBundle: m21.spanner.SpannerBundle, owner=None) -> Tuple[str, List[str]]:
        pitch: str = 'r' # "pitch" of a rest is 'r'
        recip: str = ''
        vdurRecip: str = ''
        recip, vdurRecip = M21Convert.kernRecipFromM21Duration(m21Rest.duration)
        graceType: str = M21Convert.kernGraceTypeFromM21Duration(m21Rest.duration)
        postfixAndLayouts: Tuple[str, List[str]] = M21Convert.kernPostfixAndLayoutsFromM21Rest(
                                                                m21Rest,
                                                                recip,
                                                                spannerBundle,
                                                                owner)
        postfix: str = postfixAndLayouts[0]
        layouts: [str] = postfixAndLayouts[1]

        token: str = recip + graceType + pitch + postfix

        if vdurRecip:
            layouts.append('!LO:N:vis=' + vdurRecip)

        return (token, layouts)

    @staticmethod
    def kernPostfixAndLayoutsFromM21Rest(m21Rest: m21.note.Rest,
                                         recip: str,
                                         _spannerBundle: m21.spanner.SpannerBundle,
                                         owner=None,
                                         ) -> Tuple[str, List[str]]:
        postfix: str = ''
        layouts: [str] = []

        # rest postfix possibility 0: fermata
        postfix += M21Convert._getHumdrumStringFromM21Expressions(
                                    m21Rest.expressions,
                                    m21Rest.duration,
                                    recip,
                                    owner=owner)

        # rest postfix possibility 1: pitch (for vertical positioning)
        if m21Rest.stepShift != 0:
            # postfix needs a pitch that matches the stepShift
            clef: m21.clef.Clef = m21Rest.getContextByClass('Clef')
            if clef is not None:
                baseline: int = clef.lowestLine
                midline: int = baseline + 4 # TODO: handle other than 5-line staves
                pitchNum: int = midline + m21Rest.stepShift
                # m21 pitch numbers (e.g. clef.lowestLine) are base7+1 for some reason
                # (despite documentation saying that C0 == 0) so subtract 1 before passing
                # to base7 APIs
                kernPitch: str = Convert.base7ToKern(pitchNum - 1)
                postfix += kernPitch

        # rest postfix possibility 2: invisibility
        postfix += M21Convert._getKernInvisibilityFromGeneralNote(m21Rest)

        return (postfix, layouts)

    @staticmethod
    def kernTokenStringAndLayoutsFromM21Note(m21Note: m21.note.Note,
                                             spannerBundle: m21.spanner.SpannerBundle,
                                             owner=None) -> Tuple[str, List[str]]:
        prefix: str = ''
        recip: str = ''
        vdurRecip: str = ''
        recip, vdurRecip = M21Convert.kernRecipFromM21Duration(m21Note.duration)
        graceType: str = M21Convert.kernGraceTypeFromM21Duration(m21Note.duration)
        pitch: str = M21Convert.kernPitchFromM21Pitch(m21Note.pitch, owner)
        postfix: str = ''
        layouts: [str] = []
        prefix, postfix, layouts = M21Convert.kernPrefixPostfixAndLayoutsFromM21GeneralNote(
                                                m21Note,
                                                recip,
                                                spannerBundle,
                                                isFirstNoteInChord = False,
                                                isStandaloneNote = True,
                                                owner=owner)

        if vdurRecip and postfix.count('@@') == 2:
            # we have a fingered tremolo, so a portion of visual duration doubles the actual
            # duration to make music21 do the right thing visually with a fingered tremolo.
            # We must undo this factor of 2.
            vdur: HumNum = Convert.recipToDuration(vdurRecip)
            vdur /= 2
            m21VDur: m21.duration.Duration = m21.duration.Duration(Fraction(vdur))
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
        isAppoggiatura: bool = isinstance(m21Duration, m21.duration.AppoggiaturaDuration)

        if isNonGrace:
            return ''

        if isAppoggiatura:
            return 'qq'

        # it's a grace, but not an appoggiatura
        return 'q'

    @staticmethod
    def _getSizeFromGeneralNote(m21GeneralNote: m21.note.GeneralNote) -> str:
        if m21GeneralNote.hasStyleInformation:
            return m21GeneralNote.style.noteSize # e.g. None, 'cue'
        return None

    @staticmethod
    def _getColorFromGeneralNote(m21GeneralNote: m21.note.GeneralNote) -> str:
        if m21GeneralNote.hasStyleInformation:
            return m21GeneralNote.style.color # e.g. None, 'hotpink', '#00FF00', etc
        return None

    @staticmethod
    def kernPrefixPostfixAndLayoutsFromM21GeneralNote(m21GeneralNote: m21.note.GeneralNote,
                                               recip: str,
                                               spannerBundle: m21.spanner.SpannerBundle,
                                               isFirstNoteInChord: bool = False,
                                               isStandaloneNote: bool = True,
                                               owner=None) -> Tuple[str, str, List[str]]:
        prefix: str = ''
        postfix: str = ''
        layouts: [str] = []

        # postfix possibility: invisible note
        invisibleStr: str = M21Convert._getKernInvisibilityFromGeneralNote(m21GeneralNote)

        # postfix possibility: articulations
        articStr: str = '' # includes breathmark, caesura
        # other notations (fermata, trills, tremolos, mordents)
        expressionStr: str = ''
        stemStr: str = ''
        beamStr: str = ''
        cueSizeChar: str = ''
        noteColorChar: str = ''
        if isStandaloneNote:
            # if this note is in a chord, we will get this info from the chord itself, not from here
            beamStr = M21Convert._getHumdrumBeamStringFromM21GeneralNote(m21GeneralNote)

            expressions: m21.expressions.Expression = \
                M21Utilities.getAllExpressionsFromGeneralNote(m21GeneralNote, spannerBundle)
            expressionStr = M21Convert._getHumdrumStringFromM21Expressions(
                                            expressions,
                                            m21GeneralNote.duration,
                                            recip,
                                            beamStr.count('L'), # beamStarts
                                            owner)
            articStr = M21Convert._getHumdrumStringFromM21Articulations(m21GeneralNote.articulations,
                                                                            owner)
            stemStr = M21Convert._getHumdrumStemDirStringFromM21GeneralNote(m21GeneralNote)

        # isFirstNoteInChord is currently unused, but I suspect we'll need it at some point.
        # Make pylint happy (I can't just rename it with a '_' because callers use the param name.)
        if isFirstNoteInChord:
            pass

        # cue size is assumed to always be set on individual notes in a chord,
        # never just on the chord itself.
        noteSize: str = M21Convert._getSizeFromGeneralNote(m21GeneralNote)
        if noteSize is not None and noteSize == 'cue':
            cueSizeChar = owner.reportCueSizeToOwner()

        noteColor: str = M21Convert._getColorFromGeneralNote(m21GeneralNote)
        if noteColor:
            noteColorChar = owner.reportNoteColorToOwner(noteColor)

        postfix = expressionStr + articStr + cueSizeChar + noteColorChar + stemStr + beamStr + invisibleStr

        noteLayouts: [str] = M21Convert._getNoteHeadLayoutsFromM21GeneralNote(m21GeneralNote)
        layouts += noteLayouts

        # prefix/postfix possibility: ties
        tieStart, tieStop, tieLayouts = M21Convert._getTieStartStopAndLayoutsFromM21GeneralNote(m21GeneralNote)
        prefix = tieStart + prefix # prepend to prefix for readability
        postfix += tieStop # includes tie continues, since they should also be in the postfix
        layouts += tieLayouts

        # prefix/postfix possibility: slurs
        slurStarts: str = ''
        slurStops: str = ''
        slurStarts, slurStops = M21Convert._getKernSlurStartsAndStopsFromGeneralNote(m21GeneralNote, spannerBundle)
        prefix = slurStarts + prefix # prepend to prefix for readability
        postfix += slurStops

        return (prefix, postfix, layouts)

    @staticmethod
    def _getNoteHeadLayoutsFromM21GeneralNote(m21GeneralNote: m21.note.GeneralNote) -> List[str]:
        if not isinstance(m21GeneralNote, m21.note.NotRest):
            # no notehead stuff, get out
            return []

        # noteheadFill is None, True, False
        # notehead is None, 'normal', 'cross', 'diamond', etc
        if m21GeneralNote.noteheadFill is None and (
                m21GeneralNote.notehead is None or m21GeneralNote.notehead == 'normal'
                                                   ):
            return []

        head: Optional[str] = None
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

    @staticmethod
    def _getKernSlurStartsAndStopsFromGeneralNote(m21GeneralNote: m21.note.GeneralNote, spannerBundle: m21.spanner.SpannerBundle) -> Tuple[str, str]:
        # FUTURE: Handle crossing (non-nested) slurs during export to humdrum '&('
        outputStarts: str = ''
        outputStops: str = ''

        spanners: [m21.spanner.Spanner] = m21GeneralNote.getSpannerSites()
        slurStarts: [str] = [] # 'above', 'below', or None
        slurEndCount: int = 0

        for slur in spanners:
            if 'Slur' not in slur.classes:
                continue
            if slur not in spannerBundle: # it's from the flat score, or something (ignore it)
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
            else: # shouldn't happen, but handle it
                outputStarts += '('

        # slur stops
        outputStops += ')' * slurEndCount

        return (outputStarts, outputStops)

    @staticmethod
    def _getKernInvisibilityFromGeneralNote(m21GeneralNote: m21.note.GeneralNote) -> str:
        if m21GeneralNote.hasStyleInformation and m21GeneralNote.style.hideObjectOnPrint:
            return 'yy'
        if 'SpacerRest' in m21GeneralNote.classes: # deprecated, but if we see it...
            return 'yy'
        return ''

    @staticmethod
    def kernTokenStringAndLayoutsFromM21Chord(m21Chord: m21.chord.Chord, spannerBundle: m21.spanner.SpannerBundle, owner=None) -> Tuple[str, List[str]]:
        pitchPerNote: [str] = M21Convert.kernPitchesFromM21Chord(m21Chord, owner)
        recip: str = ''
        vdurRecip: str = ''
        recip, vdurRecip = M21Convert.kernRecipFromM21Duration(m21Chord.duration) # same for each
        graceType: str = M21Convert.kernGraceTypeFromM21Duration(m21Chord.duration)
        prefixPerNote: [str] = []
        postfixPerNote: [str] = []
        layoutsForChord: [str] = []

        prefixPerNote, postfixPerNote, layoutsForChord = \
            M21Convert.kernPrefixesPostfixesAndLayoutsFromM21Chord(
                                m21Chord,
                                recip,
                                spannerBundle,
                                owner)

        token: str = ''
        for i, (prefix, pitch, postfix) in enumerate(zip(prefixPerNote, pitchPerNote, postfixPerNote)):
            if i > 0:
                token += ' '
            token += prefix + recip + graceType + pitch + postfix
            if vdurRecip and postfix.count('@@') == 2:
                # we have a fingered tremolo, so a portion of visual duration doubles the actual
                # duration to make music21 do the right thing visually with a fingered tremolo.
                # We must undo this factor of 2.
                vdur: HumNum = Convert.recipToDuration(vdurRecip)
                vdur /= 2
                m21VDur: m21.duration.Duration = m21.duration.Duration(Fraction(vdur))
                vdurRecip = M21Convert.kernRecipFromM21Duration(m21VDur)[0]
                if vdurRecip == recip:
                    vdurRecip = ''

        if vdurRecip:
            layoutsForChord.append('!LO:N:vis=' + vdurRecip)

        return token, layoutsForChord

    @staticmethod
    def kernPitchesFromM21Chord(m21Chord: m21.chord.Chord, owner=None) -> List[str]:
        pitches: [str] = []
        for m21Note in m21Chord:
            pitch: str = M21Convert.kernPitchFromM21Pitch(m21Note.pitch, owner)
            pitches.append(pitch)
        return pitches

    @staticmethod
    def kernPrefixesPostfixesAndLayoutsFromM21Chord(m21Chord: m21.chord.Chord, recip: str, spannerBundle: m21.spanner.SpannerBundle, owner=None) -> Tuple[List[str], List[str], List[str]]:
        prefixPerNote:   [str] = [] # one per note
        postfixPerNote:  [str] = [] # one per note
        layoutsForNotes: [str] = [] # 0 or more per note

        # Here we get the chord signifiers, which might be applied to each note in the token,
        # or just the first, or just the last.
        beamStr: str = M21Convert._getHumdrumBeamStringFromM21GeneralNote(m21Chord)
        articStr:str = M21Convert._getHumdrumStringFromM21Articulations(
                                        m21Chord.articulations,
                                        owner)
        exprStr: str = M21Convert._getHumdrumStringFromM21Expressions(
                                        m21Chord.expressions,
                                        m21Chord.duration,
                                        recip,
                                        beamStr.count('L'), # beamStarts
                                        owner)
        stemStr: str = M21Convert._getHumdrumStemDirStringFromM21GeneralNote(m21Chord)
        slurStarts, slurStops = M21Convert._getKernSlurStartsAndStopsFromGeneralNote(
                                                            m21Chord, spannerBundle)

        # Here we get each note's signifiers
        for noteIdx, m21Note in enumerate(m21Chord):
            prefix:  str   = '' # one for this note
            postfix: str   = '' # one for this note
            layouts: [str] = [] # 0 or more for this note

            prefix, postfix, layouts = M21Convert.kernPrefixPostfixAndLayoutsFromM21GeneralNote(
                                            m21Note,
                                            recip,
                                            spannerBundle,
                                            isFirstNoteInChord = noteIdx == 0,
                                            isStandaloneNote = False,
                                            owner=owner)

            # Add the chord signifiers as appropriate
            if noteIdx == 0:
                # first note gets the slur starts
                #   (plus expressions, articulations, stem directions)
                prefix = slurStarts + prefix
                postfix = postfix + exprStr + articStr + stemStr
            elif noteIdx == len(m21Chord) - 1:
                # last note gets the beams, and the slur stops
                #   (plus expressions, articulations, stem directions)
                postfix = postfix + exprStr + articStr + stemStr + beamStr + slurStops
            else:
                # the other notes in the chord just get expressions, articulations, stem directions
                postfix = postfix + exprStr + articStr + stemStr


            # put them in prefixPerNote, postFixPerNote, and layoutsForNotes
            prefixPerNote.append(prefix)
            postfixPerNote.append(postfix)
            for layout in layouts:
                # we have to add ':n=3' to each layout, where '3' is one-based (i.e. noteIdx+1)
                numberedLayout: str = M21Convert._addNoteNumberToLayout(layout, noteIdx+1)
                layoutsForNotes.append(numberedLayout)

        return (prefixPerNote, postfixPerNote, layoutsForNotes)

    @staticmethod
    def _addNoteNumberToLayout(layout: str, noteNum: int) -> str:
        # split at colons
        params: [str] = layout.split(':')
        insertAtIndex: int = len(params) - 2
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
    def kernRecipFromM21Duration(m21Duration: m21.duration.Duration) -> (str, str):
        dur: HumNum = None
        vdur: HumNum = None
        dots: Optional[str] = None
        inTuplet: bool = False

        if m21Duration.isGrace:
            # It's a grace note, so we want to generate real recip (printed duration)
            # even though quarterLength is (correctly) zero. m21Duration.type is 'eighth'
            # or '16th' or whatever, so use that.  This way the grace notes will keep
            # the correct number of flags/beams.
            dur = HumNum(m21.duration.convertTypeToQuarterLength(m21Duration.type))
            dots = ''
        elif m21Duration.linked is False:
            # There's a real duration and a visual duration
            # Real duration is quarterLength, visual duration is components[0].quarterLength (assuming only 1 component)
            dur = HumNum(m21Duration.quarterLength)
            if len(m21Duration.components) == 1:
                vdur = HumNum(m21Duration.components[0].quarterLength)
            else:
                print('visual duration unusable, ignoring it', file=sys.stderr)
        elif m21Duration.tuplets and len(m21Duration.tuplets) == 1:
            dur = HumNum(m21.duration.convertTypeToQuarterLength(m21Duration.type))
            dur *= HumNum(m21Duration.tuplets[0].tupletMultiplier())
            dots = '.' * m21Duration.dots
            inTuplet = True
        else:
            # no tuplet, or nested tuplets (which we will ignore, since music21 doesn't really
            # support nested tuplets, and neither do we)
            dur = HumNum(m21Duration.quarterLength)

        dur /= 4 # convert to whole-note units

        if dots is None:
            # compute number of dots from dur (and shrink dur to match)
            if dur.numerator != 1: # if it's 1 we don't need any dots
                # otherwise check up to three dots
                oneDotDur: HumNum = dur * 2 / 3
                if oneDotDur.numerator == 1:
                    dur = oneDotDur
                    dots = '.'
                else:
                    twoDotDur: HumNum = dur * 4 / 7
                    if twoDotDur.numerator == 1:
                        dur = twoDotDur
                        dots = '..'
                    else:
                        threeDotDur: HumNum = dur * 8 / 15
                        if threeDotDur.numerator == 1:
                            dur = threeDotDur
                            dots = '...'

        percentExists: bool = False
        out: str = str(dur.denominator)
        if dur.numerator != 1:
            out += '%' + str(dur.numerator)
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
                        # don't add a dot if you're in a tuplet, we have the exact dot count we want
                        out = out.replace('1%3', '0.')
                    elif first == 1 and second == 6 and not inTuplet:
                        # don't add a dot if you're in a tuplet, we have the exact dot count we want
                        out = out.replace('1%6', '00.')
                    elif first == 1 and second == 12 and not inTuplet:
                        # don't add a dot if you're in a tuplet, we have the exact dot count we want
                        out = out.replace('1%12', '000.')
                    elif first == 1 and second == 24 and not inTuplet:
                        # don't add a dot if you're in a tuplet, we have the exact dot count we want
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

        if vdur:
            m21VDur: m21.duration.Duration = m21.duration.Duration(Fraction(vdur))
            vdurRecip: str = M21Convert.kernRecipFromM21Duration(m21VDur)[0]
            return out, vdurRecip
        return out, None

    @staticmethod
    def accidentalInfo(m21Accid: m21.pitch.Accidental) -> (int, bool, bool, str):
        # returns alter, isExplicit, isEditorial, and editorialStyle
        alter: int = 0
        isExplicit: bool = False # forced to display
        isEditorial: bool = False # forced to display (with parentheses or bracket)
        editorialStyle: str = 'normal'
        if m21Accid is not None:
            alter = int(m21Accid.alter)
            if alter != m21Accid.alter:
                print(f'WARNING: Ignoring microtonal accidental: {m21Accid}.', file=sys.stderr)
                # replace microtonal accidental with explicit natural sign
                alter = 0
                isExplicit = True

            if m21Accid.displayStatus: # must be displayed
                isExplicit = True
                editorialStyle = m21Accid.displayStyle
                if editorialStyle != 'normal':
                    # must be 'parentheses', 'bracket', or 'both'
                    isEditorial = True
        return (alter, isExplicit, isEditorial, editorialStyle)

    @staticmethod
    def kernPitchFromM21Pitch(m21Pitch: m21.pitch.Pitch, owner) -> str:
        output: str = ''
        m21Accid: m21.pitch.Accidental = m21Pitch.accidental
        m21Step: str = m21Pitch.step # e.g. 'A' for an A-flat
        m21Octave: int = m21Pitch.octave
        if m21Octave is None:
            m21Octave = m21Pitch.implicitOctave # 4, most likely

        isEditorial: bool = False # forced to display (with parentheses or bracket)
        isExplicit: bool = False # forced to display
        alter: int = 0
        editorialStyle: str = ''

        alter, isExplicit, isEditorial, editorialStyle = M21Convert.accidentalInfo(m21Accid)
        if isEditorial:
            editorialSuffix = M21Convert._reportEditorialAccidentalToOwner(owner, editorialStyle)

        output = M21Convert.kernPitchFromM21OctaveAndStep(m21Octave, m21Step, owner)

        if m21Accid is None:
            pass # no accidental suffix (it's ok)
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
                output += 'n' + editorialSuffix # explicit natural + editorial suffix
            else:
                output += editorialSuffix
        elif isExplicit:
            if alter == 0:
                output += 'n' # explicit natural
            else:
                output += 'X' # explicit suffix for other accidentals

        return output

    @staticmethod
    def _reportEditorialAccidentalToOwner(owner, editorialStyle: str) -> str:
        if owner:
            from converter21.humdrum import EventData # owner is always an EventData
            ownerEvent: EventData = owner
            return ownerEvent.reportEditorialAccidentalToOwner(editorialStyle)
        return ''

    @staticmethod
    def textLayoutParameterFromM21Pieces(content    : str,
                                         placement  : str,
                                         style      : Optional[m21.style.Style]) -> str:
        placementString: str = ''
        styleString: str = ''
        justString: str = ''
        colorString: str = ''
        contentString: str = M21Convert._cleanSpacesAndColons(content)

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
                if style.absoluteY >= 0.0:
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

            if style.color: # not None and != ''
                colorString = f':color={style.color}'

        output: str = '!LO:TX' + placementString + styleString + justString + colorString + ':t=' + contentString
        return output

    @staticmethod
    def textLayoutParameterFromM21TextExpression(textExpression: m21.expressions.TextExpression) -> str:
        if textExpression is None:
            return ''

        contentString: str = textExpression.content
        placement: Optional[str] = None

        if hasattr(textExpression, 'placement'):
            # TextExpression.placement showed up in music21 v7
            placement = textExpression.placement
        else:
            # old music21 v6 name is TextExpression.positionPlacement
            placement = textExpression.positionPlacement

        if textExpression.hasStyleInformation:
            return M21Convert.textLayoutParameterFromM21Pieces(contentString, placement,
                                                               textExpression.style)
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
        newLinesAndTabs: str = '\t\n\r\v\f'
        output: str = ''
        for ch in inStr:
            if ch == '\u00A0': # convert all non-breaking spaces to '&nbsp;'
                output += '&nbsp;'
                continue

            if ch == ':': # convert all colons to '&colon;'
                output += '&colon;'
                continue

            if ch in newLinesAndTabs:
                output += ' ' # convert all newLinesAndTabs chars to a space
                continue

            output += ch

        # Strip all leading and trailing whitespace
        # We do this last after we've already saved the non-breaking spaces from stripping.
        output = output.strip()
        return output

    @staticmethod
    def _floatOrIntString(num: Union[float, int]) -> str:
        intNum: int = int(num)
        if num == intNum:
            return str(intNum)
        return str(num)

    # getMMTokenAndTempoTextLayoutFromM21TempoIndication returns (mmTokenStr, tempoTextLayout). Either can be None.
    @staticmethod
    def getMMTokenAndTempoTextLayoutFromM21TempoIndication(
                                tempo: m21.tempo.TempoIndication) -> Tuple[str, str]:
        mmTokenStr: str = ''
        tempoTextLayout: str = ''

        textExp: m21.expressions.TextExpression = None

        # a TempoText has only text (no bpm info)
        if isinstance(tempo, m21.tempo.TempoText):
            textExp = tempo.getTextExpression() # only returns explicit text
            if textExp is None:
                return ('', '')
            textExp.placement = tempo.placement
            tempoTextLayout = M21Convert.textLayoutParameterFromM21TextExpression(textExp)
            return ('', tempoTextLayout)

        # a MetricModulation describes a change from one MetronomeMark to another
        # (it carries extra info for analysis purposes).  We just get the new
        # MetronomeMark and carry on.
        if isinstance(tempo, m21.tempo.MetricModulation):
            tempo = tempo.newMetronome

        # a MetronomeMark has (optional) text (e.g. 'Andante') and (optional) bpm info.
        if not isinstance(tempo, m21.tempo.MetronomeMark):
            return ('', '')

        # if the MetronomeMark has non-implicit text, we construct some layout text (with style).
        # if the MetronomeMark has non-implicit bpm info, we construct a *MM, and if we also had
        # constructed layout text, we append some humdrum-type bpm text to our layout text.
        textExp = tempo.getTextExpression() # only returns explicit text
        if textExp is not None:
            # We have some text (like 'Andante') to display (and some textStyle)
            textExp.placement = tempo.placement
            tempoTextLayout = M21Convert.textLayoutParameterFromM21TextExpression(textExp)

        if tempo.number is not None and not tempo.numberImplicit:
            # we have an explicit bpm, so we can generate mmTokenStr and bpm text
            # For now, don't ever bother with *MM.  HumdrumBPMText is so much better.
            # mmTokenStr = '*MM' + M21Convert._floatOrIntString(tempo.getQuarterBPM())
            if not tempoTextLayout:
                tempoTextLayout = M21Convert.bpmTextLayoutParameterFromM21MetronomeMark(tempo)
            else: # we have explicit text in a layout already, just add the bpm info
                tempoTextLayout += ' ' # space delimiter between explicit text and bpm text
                tempoTextLayout += M21Convert.getHumdrumBPMTextFromM21MetronomeMark(tempo)

        return (mmTokenStr, tempoTextLayout)

    @staticmethod
    def bpmTextLayoutParameterFromM21MetronomeMark(tempo: m21.tempo.MetronomeMark) -> str:
        if tempo is None:
            return ''

        # '[eighth]=82', for example
        contentString: str = M21Convert.getHumdrumBPMTextFromM21MetronomeMark(tempo)
        placement: Optional[str] = None

        if hasattr(tempo, 'placement'):
            # MetronomeMark.placement showed up in music21 v7
            placement = tempo.placement
        else:
            # (nothing at all, not even 'positionPlacement' in v6)
            placement = 'above' # assume tempos are above for v6

        if tempo.hasStyleInformation:
            return M21Convert.textLayoutParameterFromM21Pieces(contentString, placement, tempo.style)
        return M21Convert.textLayoutParameterFromM21Pieces(contentString, placement, None)



    @staticmethod
    def getHumdrumBPMTextFromM21MetronomeMark(tempo: m21.tempo.MetronomeMark) -> str:
        output: str = '['
        output += M21Convert.getHumdrumTempoNoteNameFromM21Duration(tempo.referent)
        output += ']='
        output += M21Convert._floatOrIntString(tempo.number)
        return output

    @staticmethod
    def getHumdrumTempoNoteNameFromM21Duration(referent: m21.duration.Duration) -> str:
        # m21 Duration types are all names that are acceptable as humdrum tempo note names,
        # so no type->name mapping is required.  (See m21.duration.typeToDuration's dict keys.)
        noteName: str = referent.type
        if referent.dots > 0:
            # we only place one dot here (following the C++ code)
            noteName += '-dot'
        return noteName

    @staticmethod
    def durationFromHumdrumTempoNoteName(noteName: str) -> m21.duration.Duration:
        if not noteName:
            return None

        # In case someone forgot to strip the brackets off '[quarter-dot]', for example.
        if noteName[0] == '[':
            noteName = noteName[1:]

        if noteName[-1] == ']':
            noteName = noteName[:-1]

        # remove styling qualifiers
        noteName = noteName.split('|', 1)[0] # splits at first '|' only, or not at all

        # generating rhythmic note with optional "-dot" after it. (Only one '-dot' is noticed.)
        dots: bool = 0
        if re.search('-dot$', noteName):
            dots = 1
            noteName = noteName[0:-4]

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

        # the following are not supported by the C++ code, but seem reasonable, given music21's support
        if noteName in ('2048', '2048th'):
            return m21.duration.Duration(type='2048th', dots=dots)
        if noteName in ('longa', '00'):
            return m21.duration.Duration(type='longa', dots=dots)
        if noteName in ('maxima', '000'):
            return m21.duration.Duration(type='maxima', dots=dots)
        if noteName in ('duplex-maxima', '0000'):
            return m21.duration.Duration(type='duplex-maxima', dots=dots)

        return None

    dynamicPatterns = [
        # These have to be in a search order where you won't find a substring of the real pattern first.
        # For example, if you reverse the middle two, then 'fp' will match as 'f' before it matches as 'fp'.
        'm(f|p)',      # 'mf', 'mp'
        's?f+z?p+',     # 'fp', 'sfzp', 'ffp' etc
        '[sr]?f+z?',    # 'sf, 'sfz', 'f', 'fff', etc
        'p+',           # 'p', 'ppp', etc
    ]
    dynamicBrackets = [
        ('brack', r'\[ ', r' \]'),
        ('paren', r'\( ', r' \)'),
        ('curly', r'\{ ', r' \}'),
        ('angle', '< ', ' >'),
    ]
    @staticmethod
    def getDynamicString(dynamic: m21.dynamics.Dynamic) -> str:
        if not isinstance(dynamic, m21.dynamics.Dynamic):
            return ''

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
                        output: str = m.group(0)
                        if startDelim == r'\s':
                            output = output[1:]
                        if endDelim == r'\s':
                            output = output[:-1]
                        return output

        # give up and return whatever that string is (that isn't, and doesn't contain, a dynamic)
        return dynamic.value

    @staticmethod
    def getDynamicWedgeString(wedge: m21.dynamics.DynamicWedge, isStart: bool, isEnd: bool) -> str:
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
    def getDynamicParameters(dynamic: m21.dynamics.Dynamic) -> str:
        if not isinstance(dynamic, m21.dynamics.Dynamic):
            return ''

        output: str = ''
        if hasattr(dynamic, 'placement'):
            # Dynamic.placement showed up in music21 v7
            if dynamic.placement == 'above':
                output += ':a'

            if dynamic.placement == 'below':
                if dynamic.style.alignVertical == 'middle':
                    output += ':c'
                else:
                    output += ':b'
        else:
            # in music21 v6 it's called Dynamic.positionPlacement
            if dynamic.positionPlacement == 'above':
                output += ':a'

            if dynamic.positionPlacement == 'below':
                if dynamic.style.alignVertical == 'middle':
                    output += ':c'
                else:
                    output += ':b'

        # right justification
        if dynamic.hasStyleInformation and dynamic.style.justify == 'right':
            output += ':rj'

        if M21Convert.getDynamicString(dynamic) != dynamic.value:
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
    def getDynamicWedgeStartParameters(dynamic: m21.dynamics.DynamicWedge) -> str:
        if not isinstance(dynamic, m21.dynamics.DynamicWedge):
            return ''

        if hasattr(dynamic, 'placement'):
            # Dynamic.placement showed up in music21 v7
            if dynamic.placement == 'above':
                return ':a'

            if dynamic.placement == 'below':
                # don't check alignVertical, it isn't there (only in TextStyle)
                return '' # music21 never sets to None, always 'below', and humdrum default is below
        else:
            # in music21 v6 it's called Dynamic.positionPlacement
            if dynamic.positionPlacement == 'above':
                return ':a'

            if dynamic.positionPlacement == 'below':
                # don't check alignVertical, it isn't there (only in TextStyle)
                return '' # music21 never sets to None, always 'below', and humdrum default is below

        return ''

    @staticmethod
    def clefTokenFromM21Clef(clef: m21.clef.Clef) -> HumdrumToken:
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

            if isinstance(clef.line, int): # can be None
                string += str(clef.line)

        elif clef.sign == 'percussion':
            string += 'X' # '*clefX'
            if isinstance(clef.line, int): # it's usually None (centered), but you can position it
                string += str(clef.line)

        else: # humdrum doesn't support other clefs (like 'TAB', 'jianpu')
            return None

        return HumdrumToken(string)

    @staticmethod
    def timeSigTokenFromM21TimeSignature(timeSig: m21.meter.TimeSignature) -> HumdrumToken:
        timeSigStr: str = '*M' + timeSig.ratioString
        return HumdrumToken(timeSigStr)

    @staticmethod
    def meterSigTokenFromM21TimeSignature(timeSig: m21.meter.TimeSignature) -> HumdrumToken:
        mensurationStr: str = M21Convert.m21TimeSignatureSymbolToHumdrumMensurationSymbol.get(timeSig.symbol, None)
        if mensurationStr is None:
            return None

        meterSigStr: str = '*met(' + mensurationStr + ')'

        return HumdrumToken(meterSigStr)

    @staticmethod
    def instrumentTransposeTokenFromM21Instrument(inst: m21.instrument.Instrument) -> HumdrumToken:
        # Humdrum and music21 have reversed instrument transposition definitions
        transpose: m21.interval.Interval = inst.transposition.reverse()
        transposeStr: str = '*ITr'
        transposeStr += M21Convert.humdrumTransposeStringFromM21Interval(transpose)
        return HumdrumToken(transposeStr)

    @staticmethod
    def keySigTokenFromM21KeySignature(keySig: Union[m21.key.KeySignature, m21.key.Key]) -> HumdrumToken:
        keySigStr: str = '*k['
        keySigStr += M21Convert.numSharpsToHumdrumStandardKeyStrings[keySig.sharps]
        keySigStr += ']'

        return HumdrumToken(keySigStr)

    @staticmethod
    def keyDesignationTokenFromM21KeySignature(keySig: Union[m21.key.KeySignature, m21.key.Key]) -> HumdrumToken:
        if not isinstance(keySig, m21.key.Key):
            return None

        keyStr: str = '*' + keySig.tonicPitchNameWithCase + ':'
        if keySig.mode in ('major', 'minor'):
            # already indicated via uppercase (major) or lowercase (minor)
            return HumdrumToken(keyStr)

        keyStr += M21Convert.m21ModeToHumdrumMode.get(keySig.mode, '')
        return HumdrumToken(keyStr)

    @staticmethod
    def _getHumdrumStringFromM21Articulations(m21Artics: List[m21.articulations.Articulation], owner=None) -> str:
        output: str = ''
        for artic in m21Artics:
            humdrumChar = M21Convert.m21ArticulationClassNameToHumdrumArticulationString.get(
                            artic.classes[0],
                            '')
            if humdrumChar:
                output += humdrumChar
                continue

            # check for caesura (isn't in the lookup because it's an RDF signifier)
            if isinstance(artic, m21.articulations.Caesura):
                caesuraChar: str = owner.reportCaesuraToOwner()
                output += caesuraChar

        return output

    @staticmethod
    def _getHumdrumStringFromM21Expressions(m21Expressions: List[m21.expressions.Expression],
                                            duration: m21.duration.Duration,
                                            recip: str,
                                            beamStarts: int=None,
                                            owner=None) -> str:
        # expressions are Fermata, Trill, Mordent, Turn, Tremolo (one note)
        # also the following two Spanners: TrillExtension and TremoloSpanner (multiple notes)
        output: str = ''
        for expr in m21Expressions:
            if isinstance(expr, m21.expressions.Trill):
                # TODO: print('export of Trill not implemented')
                continue
            if isinstance(expr, m21.expressions.Mordent):
                # TODO: print('export of Mordent not implemented')
                continue
            if isinstance(expr, m21.expressions.Turn):
                # TODO: print('export of Turn not implemented')
                continue
            if isinstance(expr, (m21.expressions.Tremolo, m21.expressions.TremoloSpanner)):
                output += M21Convert._getHumdrumStringFromTremolo(
                                        expr, duration, recip, beamStarts, owner)
                continue
            if isinstance(expr, m21.expressions.TrillExtension):
                # TODO: print('export of TrillExtension not implemented')
                continue
            if isinstance(expr, m21.expressions.Fermata):
                output += ';'
                if expr.type == 'upright':
                    output += '<'
                continue

        return output

    numberOfFlagsToDurationReciprocal: dict = {
        0 : 4,
        1 : 8,
        2 : 16,
        3 : 32,
        4 : 64,
        5 : 128,
        6 : 256,
        7 : 512,
        8 : 1024,
        9 : 2048,
    }

    @staticmethod
    def _getHumdrumStringFromTremolo(tremolo: Union[m21.expressions.Tremolo,
                                                    m21.expressions.TremoloSpanner],
                                     duration: m21.duration.Duration,
                                     recip: str,
                                     beamStarts: int,
                                     _owner=None) -> str:
        output: str = ''
        fingered: bool = None
        if isinstance(tremolo, m21.expressions.Tremolo):
            fingered = False
        elif isinstance(tremolo, m21.expressions.TremoloSpanner):
            fingered = True
        else:
            raise HumdrumInternalError('tremolo is not of an appropriate type') # shouldn't happen

        tremolo: int = M21Convert.numberOfFlagsToDurationReciprocal.get(tremolo.numberOfMarks, None)
        if tremolo is not None:
            tvalue: HumNum = HumNum(tremolo)
            if fingered:
                if beamStarts and duration.quarterLength < 1:
                    # ignore beamStarts for quarter-notes and above
                    tvalue *= beamStarts
                if duration.tuplets and len(duration.tuplets) == 1:
                    tvalue /= HumNum(duration.tuplets[0].tupletMultiplier())
                if tvalue.denominator == 1:
                    output = f'@@{tvalue}@@'
                else:
                    output = f'@@{tvalue.numerator}%{tvalue.denominator}@@'
            else: # not fingered (bowed)
                durNoDots: HumNum = Convert.recipToDurationNoDots(recip)
                if 0 < durNoDots < 1:
                    dval: float = - math.log2(float(durNoDots))
                    twopow: int = int(dval)
                    tvalue *= (1<<twopow)
                if duration.tuplets and len(duration.tuplets) == 1:
                    tvalue /= HumNum(duration.tuplets[0].tupletMultiplier())
                if tvalue.denominator == 1:
                    output = f'@{tvalue}@'
                else:
                    output = f'@{tvalue.numerator}%{tvalue.denominator}@'

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
            elif beam.type ==  'stop':
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
    def _getTieStartStopAndLayoutsFromM21GeneralNote(m21GeneralNote: m21.note.GeneralNote) -> (str, str, List[str]):
        if m21GeneralNote.tie is None:
            return ('', '', [])

        tieStr: str = ''
        layouts: [str] = []

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
                tieStr += 'y'
            else: # ignore placement if hidden (duh)
                if tiePlacement == 'above':
                    tieStr += '>' # no need to report this up, since we always have '>' RDF signifier
                elif tiePlacement == 'below':
                    tieStr += '<' # no need to report this up, since we always have '<' RDF signifier

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
    def _setupRepeatBothStyleComboLookup():
        theLookup: dict = {}

        # both the same = same (don't add them together)
        # Example: if you want heavy-heavy, don't put heavy on both, put heavy-heavy on both.
        for vStyle in MeasureVisualStyle:
            theLookup[(vStyle, vStyle)] = vStyle

        # the special triple styles (heavy-light-heavy and light-heavy-light)
        # should never be looked up, so put something reasonable there, like
        # "use the first triple in the tuple"
        for vStyle in MeasureVisualStyle:
            theLookup[(MeasureVisualStyle.HeavyLightHeavy, vStyle)] = MeasureVisualStyle.HeavyLightHeavy
            theLookup[(MeasureVisualStyle.LightHeavyLight, vStyle)] = MeasureVisualStyle.LightHeavyLight

        # standard "both" combos first:
        # heavy-light + light-heavy (final) = heavy-light-heavy
        # light-heavy (final) + heavy-light = light-heavy-light
        theLookup[(MeasureVisualStyle.HeavyLight, MeasureVisualStyle.Final)] = MeasureVisualStyle.HeavyLightHeavy
        theLookup[(MeasureVisualStyle.Final, MeasureVisualStyle.HeavyLight)] = MeasureVisualStyle.LightHeavyLight

        # different (and our humdrum parser wouldn't produce this),
        # but obviously add up to another that makes sense:
        #   heavy + light-heavy (final)   = heavy-light-heavy
        #   heavy-light + heavy           = heavy-light-heavy
        #   regular + heavy-light         = light-heavy-light
        #   light-heavy (final) + regular = light-heavy-light
        theLookup[(MeasureVisualStyle.Heavy, MeasureVisualStyle.Final)] = MeasureVisualStyle.HeavyLightHeavy
        theLookup[(MeasureVisualStyle.HeavyLight, MeasureVisualStyle.Heavy)] = MeasureVisualStyle.HeavyLightHeavy
        theLookup[(MeasureVisualStyle.Regular, MeasureVisualStyle.HeavyLight)] = MeasureVisualStyle.LightHeavyLight
        theLookup[(MeasureVisualStyle.Final, MeasureVisualStyle.Regular)] = MeasureVisualStyle.LightHeavyLight

        # weird cases humdrum doesn't support (and don't make sense):
            # heavy + light = heavy-light -> ':!|:' which is just weird
            # light + heavy = light-heavy -> ':|!:' which is just weird
        theLookup[(MeasureVisualStyle.Heavy, MeasureVisualStyle.Regular)] = MeasureVisualStyle.HeavyLight
        theLookup[(MeasureVisualStyle.Regular, MeasureVisualStyle.Heavy)] = MeasureVisualStyle.Final

        M21Convert._repeatBothStyleCombos = theLookup

        # fill in the rest:
        for vStyle1 in MeasureVisualStyle:
            for vStyle2 in MeasureVisualStyle:
                combo = theLookup.get((vStyle1, vStyle2), None)
                if combo is None:
                    # different styles, and it's not one of the triple-style cases above

                    # Invisible trumps everything
                    if vStyle1 is MeasureVisualStyle.Invisible or vStyle2 is MeasureVisualStyle.Invisible:
                        theLookup[(vStyle1, vStyle2)] = MeasureVisualStyle.Invisible
                        continue

                    # Regular doesn't add anything
                    if vStyle1 is MeasureVisualStyle.Regular:
                        theLookup[(vStyle1, vStyle2)] = vStyle2
                        continue
                    if vStyle2 is MeasureVisualStyle.Regular:
                        theLookup[(vStyle1, vStyle2)] = vStyle1
                        continue

                    # Anything else (different styles, neither is Regular or Invisible, and
                    # it's not one of the triple-style cases above), vStyle1 wins
                    theLookup[(vStyle1, vStyle2)] = vStyle1

    @staticmethod
    def _combineVisualRepeatBothStyles(style1: MeasureVisualStyle,
                                       style2: MeasureVisualStyle) -> MeasureVisualStyle:
        if not M21Convert._repeatBothStyleCombos:
            M21Convert._setupRepeatBothStyleComboLookup()

        return M21Convert._repeatBothStyleCombos[(style1, style2)]

    @staticmethod
    def combineTwoMeasureStyles(currMeasureBeginStyle: MeasureStyle, prevMeasureEndStyle: MeasureStyle) -> MeasureStyle:
        outputMType: MeasureType = currMeasureBeginStyle.mType
        outputVStyle: MeasureVisualStyle = currMeasureBeginStyle.vStyle
        if prevMeasureEndStyle.mType == MeasureType.RepeatBackward:
            if currMeasureBeginStyle.mType == MeasureType.RepeatForward:
                outputMType = MeasureType.RepeatBoth
                outputVStyle = M21Convert._combineVisualRepeatBothStyles(
                                                prevMeasureEndStyle.vStyle,
                                                outputVStyle)
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
    def _computeMeasureStyleLookup():
        theLookup: dict = {}

        for style in MeasureStyle:
            theLookup[(style.vStyle, style.mType)] = style

        M21Convert._measureStyleLookup = theLookup

    @staticmethod
    def getMeasureStyle(vStyle: MeasureVisualStyle, mType: MeasureType) -> MeasureStyle:
        if not M21Convert._measureStyleLookup:
            M21Convert._computeMeasureStyleLookup()
        return M21Convert._measureStyleLookup[(vStyle, mType)]

    measureVisualStyleFromM21BarlineType: dict = {
        'regular'       : MeasureVisualStyle.Regular,
        'dotted'        : MeasureVisualStyle.Regular, # no dotted in humdrum
        'dashed'        : MeasureVisualStyle.Regular, # no dashed in humdrum
        'heavy'         : MeasureVisualStyle.Heavy,
        'double'        : MeasureVisualStyle.Double, # light-light
        'final'         : MeasureVisualStyle.Final,  # light-heavy
        'heavy-light'   : MeasureVisualStyle.HeavyLight,
        'heavy-heavy'   : MeasureVisualStyle.HeavyHeavy,
        'tick'          : MeasureVisualStyle.Tick,
        'short'         : MeasureVisualStyle.Short,
        'none'          : MeasureVisualStyle.Invisible
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
            else: # direction == 'end'
                mType = MeasureType.RepeatBackward
        vStyle = M21Convert.measureVisualStyleFromM21BarlineType[m21Barline.type]
        return M21Convert.getMeasureStyle(vStyle, mType)

    @staticmethod
    def fermataStyleFromM21Barline(barline: m21.bar.Barline) -> FermataStyle:
        if not isinstance(barline, m21.bar.Barline):
            return FermataStyle.NoFermata
        return M21Convert.fermataStyleFromM21Fermata(barline.pause)


    # m21Barline is ordered, because we want to iterate over the keys, and find '||' before '|', for example
    m21BarlineTypeFromHumdrumType: OrderedDict = OrderedDict(
    [
        ('||', 'double'),      # a.k.a. 'light-light' in MusicXML
        ('!!', 'heavy-heavy'),
        ('!|', 'heavy-light'),
        ('|!', 'final'),       # a.k.a. 'light-heavy' in MusicXML
        ('==', 'final'),       # a.k.a. 'light-heavy' in MusicXML
        ('\'', 'short'),
        ('`' , 'tick'),
        ('-' , 'none'),
        ('|' , 'regular'),     # barlines are 'regular' by default (e.g. '=3' is 'regular')
        ('!' , 'heavy')
    ])

    @staticmethod
    def _m21BarlineTypeFromHumdrumString(measureString: str) -> str:
        for humdrumType in M21Convert.m21BarlineTypeFromHumdrumType:
            if humdrumType in measureString:
                return M21Convert.m21BarlineTypeFromHumdrumType[humdrumType]
        return 'regular' # default m21BarlineType

    @staticmethod
    def _m21BarlineTypeFromHumdrumRepeatString(measureString: str, side: str) -> str:
        # side is 'left' or 'right', describing which end of a measure this repeat string should be interpreted for
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
            raise HumdrumInternalError(f'measureString does not contain left barline repeat: {measureString}')

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
            raise HumdrumInternalError(f'measureString does not contain right barline repeat: {measureString}')

        # should not ever get here
        raise HumdrumInternalError(f'side should be "left" or "right", not "{side}"')

    @staticmethod
    def m21BarlineFromHumdrumString(measureString: str, side: str) -> m21.bar.Barline: # could be m21.bar.Repeat
        # side is 'left' or 'right', describing which end of a measure this measureString should be interpreted for
        outputBarline: m21.bar.Barline = None
        if side == 'right':
            if (':|' in measureString or
                ':!' in measureString):
                # right barline is an end repeat
                outputBarline = m21.bar.Repeat(direction='end')
                outputBarline.type = M21Convert._m21BarlineTypeFromHumdrumRepeatString(measureString, side)
        elif side == 'left':
            if ('|:' in measureString or
                '!:' in measureString):
                # left barline is a start repeat
                outputBarline = m21.bar.Repeat(direction='start')
                outputBarline.type = M21Convert._m21BarlineTypeFromHumdrumRepeatString(measureString, side)
            else:
                # 'left' is only passed in for repeat marks; normal barlines always go on the right.
                raise HumdrumExportError(f'Left barline is not a repeat mark: {measureString}')

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
#         elif m21Fermata.hasStyleInformation and m21Fermata.style == 'inverted': # leave it as a normal Fermata, this is m21's default
#             output = FermataStyle.FermataAbove

        return output

    @staticmethod
    def combineTwoFermataStyles(currMeasureBeginFermata: FermataStyle, prevMeasureEndFermata: FermataStyle) -> FermataStyle:
        # simple combination for now: if either is a fermata, use it as the combination
        # if both are a fermata, use the current measure's begin fermata
        # if neither is a fermata, return FermataStyle.NoFermata
        if currMeasureBeginFermata != FermataStyle.NoFermata:
            return currMeasureBeginFermata
        if prevMeasureEndFermata != FermataStyle.NoFermata:
            return prevMeasureEndFermata
        return FermataStyle.NoFermata

    # Conversions from str to m21.metadata.DateBlah types, and back.
    # e.g. '1942///-1943///' -> DateBetween([Date(1942), Date(1943)])
    # m21.metadata.DateBlah have conversions to/from str, and the strings are really close to humdrum format,
    # but not quite, and they don't handle some humdrum cases at all (like the one above).  So I need to
    # replace them here.

    # str -> DateSingle | DateRelative | DateBetween | DateSelection

    _dateApproximateSymbols = ('~', 'x')    # approximate (i.e. not exactly, but reasonably close)
    _dateUncertainSymbols = ('?', 'z')      # uncertain (i.e. maybe not correct at all)
    _dateDividerSymbols = ('-', '^', '|')   # date1-date2 or date1^date2 (DateBetween: between these two dates)
                                            # date1|date2|date3|date4... (DateSelection: one of these dates)

    @staticmethod
    def m21DateObjectFromString(string: str) -> Union[m21.metadata.DateSingle,
                                                      m21.metadata.DateRelative,
                                                      m21.metadata.DateBetween,
                                                      m21.metadata.DateSelection]:
        typeNeeded: Type = m21.metadata.DateSingle
        relativeType: str = ''
        if '<' in string[0:1]: # this avoids crash on empty string
            typeNeeded = m21.metadata.DateRelative
            string = string.replace('<', '')
            relativeType = 'before'
        elif '>' in string[0:1]: # this avoids crash on empty string
            typeNeeded = m21.metadata.DateRelative
            string = string.replace('>', '')
            relativeType = 'after'

        dateStrings: List[str] = [string] # if we don't split it, this is what we will parse
        for divider in M21Convert._dateDividerSymbols:
            if divider in string:
                if divider == '|':
                    typeNeeded = m21.metadata.DateSelection
                    dateStrings = string.split(divider)    # split on all '|'s
                else:
                    typeNeeded = m21.metadata.DateBetween
                    dateStrings = string.split(divider, 1) # split only at first instance of divider
                break # we assume there is only one type of divider present

        del string # to make sure we never look at it again

        singleRelevance: str = ''
        if typeNeeded == m21.metadata.DateSingle:
            # special case where a leading '~' or '?' should be removed and cause
            # the DateSingle's relevance to be set to 'approximate' or 'uncertain'.
            # Other DataBlah types use their relevance for other things, so leaving
            # the '~'/'?' in place to cause yearError to be set is a better choice.
            if '~' in dateStrings[0][0:1]: # avoids crash on empty dateStrings[0]
                dateStrings[0] = dateStrings[0][1:]
                singleRelevance = 'approximate'
            elif '?' in dateStrings[0][0:1]: # avoids crash on empty dateStrings[0]
                dateStrings[0] = dateStrings[0][1:]
                singleRelevance = 'uncertain'

        dates: List[m21.metadata.Date] = []
        for dateString in dateStrings:
            date: m21.metadata.Date = M21Convert._dateFromString(dateString)
            if date is None:
                # if dateString is unparseable, give up on date parsing of this whole metadata item
                return None
            dates.append(date)

        if typeNeeded == m21.metadata.DateSingle:
            if singleRelevance:
                return m21.metadata.DateSingle(dates[0], relevance=singleRelevance)
            return m21.metadata.DateSingle(dates[0])

        if typeNeeded == m21.metadata.DateRelative:
            return m21.metadata.DateRelative(dates[0], relevance=relativeType)

        if typeNeeded == m21.metadata.DateBetween:
            return m21.metadata.DateBetween(dates)

        if typeNeeded == m21.metadata.DateSelection:
            return m21.metadata.DateSelection(dates)

        return None

    @staticmethod
    def _stripDateError(value: str) -> Tuple[str, str]:
        '''
        Strip error symbols from a numerical value. Return cleaned source and
        error symbol. Only one error symbol is expected per string.
        '''
        sym = M21Convert._dateApproximateSymbols + M21Convert._dateUncertainSymbols
        found = None
        for char in value:
            if char in sym:
                found = char
                break
        if found is None:
            return value, None
        if found in M21Convert._dateApproximateSymbols:
            value = value.replace(found, '')
            return value, 'approximate'
        #if found in M21Convert._dateUncertainSymbols: # always True
        value = value.replace(found, '')
        return value, 'uncertain'

    _dateAttrNames     = [ 'year', 'month',   'day',  'hour', 'minute', 'second']
    _dateAttrStrFormat = [   '%i', '%02.i', '%02.i', '%02.i',  '%02.i', '%05.2f']
    _highestSecondString = '59.99' # two digits past decimal point because of '%05.2f' above

    @staticmethod
    def _dateFromString(dateStr: str) -> m21.metadata.Date:
        values: List[Optional[Union[int, float]]] = []  # year, month, day, hour, minute as ints, second as float
                                                        # (each can be None if not specified)
        valueErrors: List[str] = []                     # yearError, monthError, dayError,
                                                        #   hourError, minuteError, secondError
        dateStr = dateStr.replace(':', '/')
        dateStr = dateStr.replace(' ', '')
        gotOne: bool = False
        try:
            for i, chunk in enumerate(dateStr.split('/')):
                value, error = M21Convert._stripDateError(chunk)
                if i == 0 and len(value) >= 2: # year with prepended '@' is B.C.E. so replace with '-'
                    if value[0] == '@':
                        value = '-' + value[1:]

                if value == '':
                    values.append(None)
                elif i == 5: # second is a float
                    values.append(float(value))
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
        for attr, attrValue, attrError in zip(M21Convert._dateAttrNames, values, valueErrors):
            if attrValue is not None:
                setattr(date, attr, attrValue)
                if attrError is not None:
                    setattr(date, attr + 'Error', attrError)

        return date

    @staticmethod
    def stringFromM21DateObject(m21Date: m21.metadata.DateSingle) -> str:
        # m21Date is DateSingle, DateRelative, DateBetween, or DateSelection (all derive from DateSingle)
        # pylint: disable=protected-access
        output: str = ''
        if isinstance(m21Date, m21.metadata.DateSelection):
            # series of multiple dates, delimited by '|'
            for i, date in enumerate(m21Date._data):
                dateString: str = M21Convert._stringFromDate(date)
                if i > 0:
                    output += '|'
                output += dateString

        elif isinstance(m21Date, m21.metadata.DateBetween):
            # two dates, delimited by '-'
            for i, date in enumerate(m21Date._data):
                dateString: str = M21Convert._stringFromDate(date)
                if i > 0:
                    output += '-'
                output += dateString

        elif isinstance(m21Date, m21.metadata.DateRelative):
            # one date, prefixed by '<' or '>' for 'prior'/'onorbefore' or 'after'/'onorafter'
            output = '<' # assume before
            if m21Date.relevance in ('after', 'onorafter'):
                output = '>'

            dateString: str = M21Convert._stringFromDate(m21Date._data[0])
            output += dateString

        elif isinstance(m21Date, m21.metadata.DateSingle):
            # one date, no prefixes
            output = M21Convert._stringFromDate(m21Date._data[0])
            if m21Date.relevance == 'uncertain':
                output = M21Convert._dateUncertainSymbols[0] + output   # [0] is the date error symbol
            elif m21Date.relevance == 'approximate':
                output = M21Convert._dateApproximateSymbols[0] + output # [0] is the date error symbol

        # pylint: enable=protected-access
        return output

    @staticmethod
    def _stringFromDate(date: m21.metadata.Date) -> str:
        msg = []
        if date.hour is None and date.minute is None and date.second is None:
            breakIndex = 3  # index
        else:
            breakIndex = 99999

        for i in range(len(M21Convert._dateAttrNames)):
            if i >= breakIndex:
                break
            attr = M21Convert._dateAttrNames[i]
            value = getattr(date, attr)
            error = getattr(date, attr + 'Error')
            if value is None:
                msg.append('')
            else:
                fmt = M21Convert._dateAttrStrFormat[i]
                sub = fmt % value
                if i == 0: # year
                    # check for negative year, and replace '-' with '@'
                    if len(sub) >= 2 and sub[0] == '-':
                        sub = '@' + sub[1:]
                elif i == 5: # seconds
                    # Check for formatted seconds starting with '60' (due to rounding) and truncate to '59.99'
                    # That's easier than doing rounding correctly (carrying into minutes, hours, days, etc).
                    if sub.startswith('60'):
                        sub = M21Convert._highestSecondString
                if error is not None:
                    sub += M21Convert._dateErrorToSymbol(error)
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
            output = msg[0] + '/' + msg[1] + '/' + msg[2] + '/' + msg[3] + ':' + msg[4] + ':' + msg[5]

        return output

    @staticmethod
    def _dateErrorToSymbol(value):
        if value.lower() in M21Convert._dateApproximateSymbols + ('approximate',):
            return M21Convert._dateApproximateSymbols[1] # [1] is the single value error symbol
        if value.lower() in M21Convert._dateUncertainSymbols + ('uncertain',):
            return M21Convert._dateUncertainSymbols[1]   # [1] is the single value error symbol
        return ''
