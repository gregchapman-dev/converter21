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
import html
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
    humdrumMensurationSymbolToM21TimeSignatureSymbol: t.Dict[str, str] = {
        'c': 'common',  # modern common time (4/4)
        'c|': 'cut',    # modern cut time (2/2)
        # 'C': '',      # mensural common (not supported in music21)
        # 'C|': '',     # mensural cut (2/1) (not supported in music21)
        # 'O': '',      # mensural 'O' (not supported in music21)
        # 'O|': '',     # mensural 'cut O' (not supported in music21)
    }

    m21TimeSignatureSymbolToHumdrumMensurationSymbol: t.Dict[str, str] = {
        'common': 'c',  # modern common time (4/4)
        'cut': 'c|',    # modern cut time (2/2)
    }

    diatonicToM21PitchName: t.Dict[int, str] = {
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
        diatonicToM21StepName: t.Dict[int, m21.common.types.StepName] = {
            0: 'C',
            1: 'D',
            2: 'E',
            3: 'F',
            4: 'G',
            5: 'A',
            6: 'B',
        }

    humdrumReferenceKeyToEncodingScheme: t.Dict[str, str] = {
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

    humdrumReferenceKeyToM21MetadataPropertyUniqueName: t.Dict[str, str] = {
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
        'RMM': 'manufacturer',          # manufacturer or sponsoring company
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
        'OCO': 'commission',            # commissioned by
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
        'YOO': '',                      # original document owner
        'YOY': '',                      # original copyright year
        'YOE': '',                      # original editor
        'EED': '',                      # electronic editor
        'ENC': '',                      # electronic encoder (person)
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

    # This dict is private because we wrap a function around it.
    _m21MetadataPropertyUniqueNameToHumdrumReferenceKey: t.Dict[str, str] = {
        uniqueName: hdKey for (hdKey, uniqueName) in
        humdrumReferenceKeyToM21MetadataPropertyUniqueName.items() if uniqueName != ''
    }

    # Only used by old (pre-DublinCore) metadata code
    humdrumReferenceKeyToM21ContributorRole: t.Dict[str, str] = {
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

    # Only used by old (pre-DublinCore) metadata code
    m21ContributorRoleToHumdrumReferenceKey: t.Dict[str, str] = {
        'composer': 'COM',
        'attributed composer': 'COA',
        'suspected composer': 'COS',
        'composer alias': 'COL',
        'corporate composer': 'COC',
        'lyricist': 'LYR',
        'librettist': 'LIB',
        'arranger': 'LAR',
        'orchestrator': 'LOR',
        'translator': 'TRN',
        'original document owner': 'YOO',
        'original editor': 'YOE',
        'electronic editor': 'EED',
        'electronic encoder': 'ENC'
    }

    humdrumDecoGroupStyleToM21GroupSymbol: t.Dict[str, str] = {
        '{': 'brace',
        '[': 'bracket',
        '<': 'square',   # what is this one supposed to be, it's often ignored in iohumdrum.cpp
    }

    m21GroupSymbolToHumdrumDecoGroupStyleStart: t.Dict[str, str] = {
        'brace': '{',
        'bracket': '[',
        'square': '<',    # what is this one supposed to be, it's often ignored in iohumdrum.cpp
        'line': '',       # humdrum doesn't have line, but "no style" is close
    }

    m21GroupSymbolToHumdrumDecoGroupStyleStop: t.Dict[str, str] = {
        'brace': '}',
        'bracket': ']',
        'square': '>',    # what is this one supposed to be, it's often ignored in iohumdrum.cpp
        'line': '',       # humdrum doesn't have line, but "no style" is close
    }

    humdrumStandardKeyStringsToNumSharps: t.Dict[str, int] = {
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

    numSharpsToHumdrumStandardKeyStrings: t.Dict[int, str] = {
        0: '',
        1: 'f#',
        2: 'f#c#',
        3: 'f#c#g#',
        4: 'f#c#g#d#',
        5: 'f#c#g#d#a#',
        6: 'f#c#g#d#a#e#',
        7: 'f#c#g#d#a#e#b#',
        -1: 'b-',
        -2: 'b-e-',
        -3: 'b-e-a-',
        -4: 'b-e-a-d-',
        -5: 'b-e-a-d-g-',
        -6: 'b-e-a-d-g-c-',
        -7: 'b-e-a-d-g-c-f-',
    }

    humdrumModeToM21Mode: t.Dict[str, str] = {
        'dor': 'dorian',
        'phr': 'phrygian',
        'lyd': 'lydian',
        'mix': 'mixolydian',
        'aeo': 'aeolian',
        'ion': 'ionian',
        'loc': 'locrian',
    }

    m21ModeToHumdrumMode: t.Dict[str, str] = {
        'dorian': 'dor',
        'phrygian': 'phr',
        'lydian': 'lyd',
        'mixolydian': 'mix',
        'aeolian': 'aeo',
        'ionian': 'ion',
        'locrian': 'loc',
    }

    # place articulations in stacking order (nearest to furthest from note)
    humdrumArticulationStringToM21ArticulationClassName: t.Dict[str, str] = {
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

    m21ArticulationClassNameToHumdrumArticulationString: t.Dict[str, str] = {
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
        def m21StepNameV8(subTokenStr: str) -> t.Optional[m21.common.types.StepName]:
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
    def m21StepName(subTokenStr: str) -> t.Optional[str]:
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
    def m21Articulations(
            tokenStr: str,
            rdfAbove: str,
            rdfBelow: str
    ) -> t.List[m21.articulations.Articulation]:
        # music21 doesn't have different articulation lists per note in a chord, just a single
        # articulation list for the chord itself.  So we search the entire tokenStr for
        # articulations, and add them all to the chord.  This works for non-chord (note) tokens
        # as well.
        # store info about articulations in various dicts, keyed by humdrum articulation string
        # which is usually a single character, but can be two (e.g. '^^')
        articFound: t.Dict[str, bool] = {}
        articPlacement: t.Dict[str, str] = {}  # value is 'below', 'above', or ''
        # gestural means "not printed on the page, but it's what the performer did/should do"
        articIsGestural: t.Dict[str, bool] = {}

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

        artics: t.List[m21.articulations.Articulation] = []

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
        vdur: t.Optional[HumNum] = None
        vdurNoDots: t.Optional[HumNum] = None
        vdurNumDots: t.Optional[int] = None
        vdurType: t.Optional[str] = None
        if vdurStr:
            vdur = opFrac(Convert.recipToDuration(vdurStr) / tuplet.tupletMultiplier())
            if t.TYPE_CHECKING:
                assert vdur is not None
            vdurNoDots, vdurNumDots = Convert.computeDurationNoDotsAndNumDots(vdur)
            if vdurNumDots is None:
                print(f'Cannot figure out vDurNoDots + vDurNumDots from {vdurStr} (on '
                      + f'line number {token.lineNumber}), tuplet={tuplet}, ignoring'
                      'visual duration', file=sys.stderr)
            else:
                vdurType = m21.duration.convertQuarterLengthToType(vdurNoDots)

        dur: HumNum = opFrac(token.duration / tuplet.tupletMultiplier())
        durNoDots: HumNum
        numDots: t.Optional[int]
        durNoDots, numDots = Convert.computeDurationNoDotsAndNumDots(dur)
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
            meterSigToken: t.Optional[HumdrumToken] = None
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
            keyToken: t.Optional[HumdrumToken] = None
    ) -> t.Optional[t.Union[m21.key.KeySignature, m21.key.Key]]:
        keySig = keySigToken.keySignature

        m21Key: t.Optional[m21.key.Key] = None
        m21KeySig: t.Optional[m21.key.KeySignature] = None

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
            alteredPitches: t.List[str] = [
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
            keyName: t.Optional[str]
            mode: t.Optional[str]
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
    def m21IntervalFromTranspose(transpose: str) -> t.Optional[m21.interval.Interval]:
        dia: t.Optional[int]
        chroma: t.Optional[int]
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
    def humdrumTransposeStringFromM21Interval(interval: m21.interval.Interval) -> t.Optional[str]:
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
    ) -> t.Tuple[str, t.List[str]]:
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
    ) -> t.Tuple[str, str, str]:
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
    ) -> t.Tuple[str, t.List[str]]:
        prefix: str = ''
        recip: str = ''
        vdurRecip: str = ''
        graceType: str = ''
        recip, vdurRecip, graceType = M21Convert.kernRecipAndGraceTypeFromGeneralNote(m21Unpitched)
        pitch: str = M21Convert.kernPitchFromM21Unpitched(m21Unpitched, owner)
        postfix: str = ''
        layouts: t.List[str] = []
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
    ) -> t.Tuple[str, t.List[str]]:
        pitch: str = 'r'  # "pitch" of a rest is 'r'
        recip: str = ''
        vdurRecip: str = ''
        graceType: str = ''
        recip, vdurRecip, graceType = M21Convert.kernRecipAndGraceTypeFromGeneralNote(m21Rest)
        postfixAndLayouts: t.Tuple[str, t.List[str]] = (
            M21Convert.kernPostfixAndLayoutsFromM21Rest(
                m21Rest,
                recip,
                spannerBundle,
                owner)
        )
        postfix: str = postfixAndLayouts[0]
        layouts: t.List[str] = postfixAndLayouts[1]

        token: str = recip + graceType + pitch + postfix

        if vdurRecip:
            layouts.append('!LO:N:vis=' + vdurRecip)

        return (token, layouts)

    @staticmethod
    def kernPostfixAndLayoutsFromM21Rest(m21Rest: m21.note.Rest,
                                         recip: str,
                                         _spannerBundle: m21.spanner.SpannerBundle,
                                         owner=None,
                                         ) -> t.Tuple[str, t.List[str]]:
        postfix: str = ''
        layouts: t.List[str] = []

        # rest postfix possibility 0: fermata
        postfix += M21Convert._getHumdrumStringFromM21Expressions(
            m21Rest.expressions,
            m21Rest.duration,
            recip,
            owner=owner
        )

        # rest postfix possibility 1: pitch (for vertical positioning)
        if m21Rest.stepShift != 0:
            # postfix needs a pitch that matches the stepShift
            clef: t.Optional[m21.clef.Clef] = m21Rest.getContextByClass(m21.clef.Clef)
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

        return (postfix, layouts)

    @staticmethod
    def kernTokenStringAndLayoutsFromM21Note(m21Note: m21.note.Note,
                                             spannerBundle: m21.spanner.SpannerBundle,
                                             owner=None) -> t.Tuple[str, t.List[str]]:
        recip: str = ''
        vdurRecip: str = ''
        graceType: str = ''
        recip, vdurRecip, graceType = M21Convert.kernRecipAndGraceTypeFromGeneralNote(m21Note)
        pitch: str = M21Convert.kernPitchFromM21Pitch(m21Note.pitch, owner)
        prefix: str = ''
        postfix: str = ''
        layouts: t.List[str] = []
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
        isAppoggiatura: bool = isinstance(m21Duration, m21.duration.AppoggiaturaDuration)

        if isNonGrace:
            return ''

        if isAppoggiatura:
            return 'qq'

        # it's a grace, but not an appoggiatura
        return 'q'

    @staticmethod
    def _getSizeFromGeneralNote(m21GeneralNote: m21.note.GeneralNote) -> t.Optional[str]:
        if m21GeneralNote.hasStyleInformation:
            if t.TYPE_CHECKING:
                assert isinstance(m21GeneralNote.style, m21.style.NoteStyle)
            return m21GeneralNote.style.noteSize  # e.g. None, 'cue'
        return None

    @staticmethod
    def _getColorFromGeneralNote(m21GeneralNote: m21.note.GeneralNote) -> t.Optional[str]:
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
    ) -> t.Tuple[str, str, t.List[str]]:
        prefix: str = ''
        postfix: str = ''
        layouts: t.List[str] = []

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

            expressions: t.List[t.Union[m21.expressions.Expression, m21.spanner.Spanner]] = (
                M21Utilities.getAllExpressionsFromGeneralNote(m21GeneralNote, spannerBundle)
            )
            expressionStr = M21Convert._getHumdrumStringFromM21Expressions(
                expressions,
                m21GeneralNote.duration,
                recip,
                beamStr.count('L'),  # beamStarts
                owner
            )
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
        noteSize: t.Optional[str] = M21Convert._getSizeFromGeneralNote(m21GeneralNote)
        if noteSize is not None and noteSize == 'cue':
            cueSizeChar = owner.reportCueSizeToOwner()

        noteColor: t.Optional[str] = M21Convert._getColorFromGeneralNote(m21GeneralNote)
        if noteColor:
            noteColorChar = owner.reportNoteColorToOwner(noteColor)

        postfix = (
            sfOrSfzStr + expressionStr + articStr + cueSizeChar + noteColorChar
            + stemStr + beamStr + invisibleStr
        )

        noteLayouts: t.List[str] = M21Convert._getNoteHeadLayoutsFromM21GeneralNote(m21GeneralNote)
        layouts += noteLayouts

        if isStandaloneNote:
            dynLayouts: t.List[str] = (
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
    def _getNoteHeadLayoutsFromM21GeneralNote(m21GeneralNote: m21.note.GeneralNote) -> t.List[str]:
        if not isinstance(m21GeneralNote, m21.note.NotRest):
            # no notehead stuff, get out
            return []

        # noteheadFill is None, True, False
        # notehead is None, 'normal', 'cross', 'diamond', etc
        if m21GeneralNote.noteheadFill is None and (
                m21GeneralNote.notehead is None or m21GeneralNote.notehead == 'normal'):
            return []

        head: t.Optional[str] = None
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
    def _getKernSlurStartsAndStopsFromGeneralNote(
            m21GeneralNote: m21.note.GeneralNote,
            spannerBundle: m21.spanner.SpannerBundle
    ) -> t.Tuple[str, str]:
        # FUTURE: Handle crossing (non-nested) slurs during export to humdrum '&('
        outputStarts: str = ''
        outputStops: str = ''

        spanners: t.List[m21.spanner.Spanner] = m21GeneralNote.getSpannerSites()
        slurStarts: t.List[str] = []  # 'above', 'below', or None
        slurEndCount: int = 0

        for slur in spanners:
            if not isinstance(slur, m21.spanner.Slur):
                continue
            if slur not in spannerBundle:  # it's from the flat score, or something (ignore it)
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
    ) -> t.Tuple[str, t.List[str]]:
        pitchPerNote: t.List[str] = M21Convert.kernPitchesFromM21Chord(m21Chord, owner)
        recip: str = ''
        vdurRecip: str = ''
        graceType: str = ''
        recip, vdurRecip, graceType = M21Convert.kernRecipAndGraceTypeFromGeneralNote(m21Chord)
        prefixPerNote: t.List[str] = []
        postfixPerNote: t.List[str] = []
        layoutsForChord: t.List[str] = []

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
    def kernPitchesFromM21Chord(m21Chord: m21.chord.Chord, owner=None) -> t.List[str]:
        pitches: t.List[str] = []
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
    ) -> t.Tuple[t.List[str], t.List[str], t.List[str]]:
        prefixPerNote: t.List[str] = []    # one per note
        postfixPerNote: t.List[str] = []   # one per note
        layoutsForChord: t.List[str] = []  # 0 or more per note, maybe 1 for the whole chord

        # Here we get the chord signifiers, which might be applied to each note in the token,
        # or just the first, or just the last.
        beamStr: str = M21Convert._getHumdrumBeamStringFromM21GeneralNote(m21Chord)
        articStr: str = M21Convert._getHumdrumStringFromM21Articulations(
            m21Chord.articulations,
            owner
        )
        expressions: t.List[t.Union[m21.expressions.Expression, m21.spanner.Spanner]] = (
            M21Utilities.getAllExpressionsFromGeneralNote(m21Chord, spannerBundle)
        )
        exprStr: str = M21Convert._getHumdrumStringFromM21Expressions(
            expressions,
            m21Chord.duration,
            recip,
            beamStr.count('L'),  # beamStarts
            owner
        )
        stemStr: str = M21Convert._getHumdrumStemDirStringFromM21GeneralNote(m21Chord)
        slurStarts, slurStops = M21Convert._getKernSlurStartsAndStopsFromGeneralNote(
            m21Chord,
            spannerBundle
        )
        sfOrSfz: str = M21Convert._getSfOrSfzFromM21GeneralNote(m21Chord)
        dynLayouts: t.List[str] = M21Convert._getDynamicsLayoutsFromM21GeneralNote(m21Chord)
        layoutsForChord += dynLayouts

        # Here we get each note's signifiers
        for noteIdx, m21Note in enumerate(m21Chord):
            prefix: str = ''           # one for this note
            postfix: str = ''          # one for this note
            layouts: t.List[str] = []  # 0 or more for this note

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
        params: t.List[str] = layout.split(':')
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
    def kernRecipFromM21Duration(m21Duration: m21.duration.Duration) -> t.Tuple[str, str]:
        dur: HumNum
        vdur: t.Optional[HumNum] = None
        dots: t.Optional[str] = None
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
            # Real duration is quarterLength, visual duration is a bit more complex
            # (assuming only 1 component)
            dur = m21Duration.quarterLength
            vdur = m21.duration.convertTypeToQuarterLength(m21Duration.type)
            vdur *= m21Duration.tuplets[0].tupletMultiplier()
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

        if vdur:
            m21VDur: m21.duration.Duration
            if inTuplet:
                m21VDur = m21.duration.Duration(vdur / m21Duration.tuplets[0].tupletMultiplier())
                m21VDur.appendTuplet(m21Duration.tuplets[0])
            else:
                m21VDur = m21.duration.Duration(vdur)
            vdurRecip: str = M21Convert.kernRecipFromM21Duration(m21VDur)[0]
            return out, vdurRecip
        return out, ''

    @staticmethod
    def accidentalInfo(
            m21Accid: t.Optional[m21.pitch.Accidental]
    ) -> t.Tuple[int, bool, bool, str]:
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
        m21Accid: t.Optional[m21.pitch.Accidental] = m21Pitch.accidental
        m21Step: str = m21Pitch.step  # e.g. 'A' for an A-flat
        m21Octave: t.Optional[int] = m21Pitch.octave
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
            placement: t.Optional[str],
            style: t.Optional[m21.style.TextStyle]
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
        placement: t.Optional[str] = textExpression.placement
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
            if char in SharedConstants._SMUFL_METRONOME_MARK_NOTE_CHARS_TO_HUMDRUM_NOTE_NAME:
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

            if char in SharedConstants._SMUFL_METRONOME_MARK_NOTE_CHARS_TO_HUMDRUM_NOTE_NAME:
                output += (
                    '['
                    + SharedConstants._SMUFL_METRONOME_MARK_NOTE_CHARS_TO_HUMDRUM_NOTE_NAME[char]
                )
                j = i + 1
                while text[j] in (
                    SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR['metAugmentationDot'],
                    chr(0x2009),  # thin space, inserted around notes sometimes
                    chr(0x200A),  # thin space, inserted sometimes as well
                ):
                    if text[j] in (chr(0x2009), chr(0x200A)):
                        pass  # just skip the thin space
                    else:
                        output += '-dot'
                    j += 1
                output += ']'
                numCharsToSkip = j - (i + 1)
                continue

            if char in (chr(0x2009), chr(0x200A)):  # thin space, inserted sometimes
                continue  # just skip the thin space

            if char == chr(0x00A0):
                # convert nbsp to regular space (Humdrum doesn't want nbsp's in tempo text)
                output += ' '
                continue

            # all other chars
            output += char

        return output


    @staticmethod
    def _floatOrIntString(num: t.Union[float, int]) -> str:
        intNum: int = int(num)
        if num == intNum:
            return str(intNum)
        return str(num)

    # getMMTokenAndOMDFromM21TempoIndication returns (mmTokenStr, tempoTextLayout).
    @staticmethod
    def getMMTokenAndOMDFromM21TempoIndication(
            tempo: m21.tempo.TempoIndication
    ) -> t.Tuple[str, str]:
        mmTokenStr: str = ''
        tempoOMD: str = ''

        textExp: t.Optional[m21.expressions.TextExpression] = None

        # a TempoText has only text (no bpm info)
        if isinstance(tempo, m21.tempo.TempoText):
            textExp = tempo.getTextExpression()  # only returns explicit text
            if textExp is None:
                return ('', '')
            tempoOMD = '!!!OMD: ' + textExp.content
            return ('', tempoOMD)

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
            tempoOMD = '!!!OMD: ' + textExp.content

        if tempo.number is not None:
            # even if the number is implicit, go ahead and generate a *MM for it.
            # Note that we always round to integer to emit *MM (we round to integer
            # when we parse it, too).
            quarterBPM: float = tempo.getQuarterBPM()
            mmTokenStr = '*MM' + M21Convert._floatOrIntString(int(quarterBPM + 0.5))

        return (mmTokenStr, tempoOMD)

    # @staticmethod
    # def bpmTextLayoutParameterFromM21MetronomeMark(tempo: m21.tempo.MetronomeMark) -> str:
    #     if tempo is None:
    #         return ''
    #
    #     # '[eighth]=82', for example
    #     contentString: str = M21Convert.getHumdrumBPMTextFromM21MetronomeMark(tempo)
    #     placement: t.Optional[str] = tempo.placement
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
            noteName: t.Optional[str]
    ) -> t.Optional[m21.duration.Duration]:
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

    dynamicPatterns: t.List[str] = [
        # These have to be in a search order where you won't find a substring of the real
        # pattern first. For example, if you reverse the middle two, then 'fp' will match
        # as 'f' before it matches as 'fp'.
        'm(f|p)',      # 'mf', 'mp'
        's?f+z?p+',     # 'fp', 'sfzp', 'ffp' etc
        '[sr]?f+z?',    # 'sf, 'sfz', 'f', 'fff', etc
        'p+',           # 'p', 'ppp', etc
    ]
    dynamicBrackets: t.List[t.Tuple[str, str, str]] = [
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

        textStyle: t.Optional[m21.style.TextStyle] = None
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
        if textStyle is not None and textStyle.justify == 'right':
            output += ':rj'

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
    def getDynamicOnNoteParameters(dynamic: m21.dynamics.Dynamic) -> str:
        output: str = ''
        dynString: str = M21Convert.getDynamicString(dynamic)

        textStyle: t.Optional[m21.style.TextStyle] = None
        if dynamic.hasStyleInformation:
            assert isinstance(dynamic.style, m21.style.TextStyle)
            textStyle = dynamic.style

        # right justification
        if textStyle is not None and textStyle.justify == 'right':
            output += ':rj'

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
    def clefTokenFromM21Clef(clef: m21.clef.Clef) -> t.Optional[HumdrumToken]:
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
    ) -> t.Optional[HumdrumToken]:
        timeSigStr: str = '*M' + timeSig.ratioString
        return HumdrumToken(timeSigStr)

    @staticmethod
    def meterSigTokenFromM21TimeSignature(
            timeSig: m21.meter.TimeSignature
    ) -> t.Optional[HumdrumToken]:
        mensurationStr: t.Optional[str] = (
            M21Convert.m21TimeSignatureSymbolToHumdrumMensurationSymbol.get(timeSig.symbol)
        )
        if mensurationStr is None:
            return None

        meterSigStr: str = '*met(' + mensurationStr + ')'

        return HumdrumToken(meterSigStr)

    @staticmethod
    def instrumentTransposeTokenFromM21Instrument(
            inst: m21.instrument.Instrument
    ) -> t.Optional[HumdrumToken]:
        if inst.transposition is None:
            return None

        # Humdrum and music21 have reversed instrument transposition definitions
        transpose: m21.interval.Interval = inst.transposition.reverse()
        dNcM: t.Optional[str] = M21Convert.humdrumTransposeStringFromM21Interval(transpose)
        if dNcM is None:
            return None

        transposeStr: str = '*ITr'
        transposeStr += dNcM
        return HumdrumToken(transposeStr)

    @staticmethod
    def keySigTokenFromM21KeySignature(
            keySig: t.Union[m21.key.KeySignature, m21.key.Key]
    ) -> HumdrumToken:
        keySigStr: str = '*k['
        keySigStr += M21Convert.numSharpsToHumdrumStandardKeyStrings[keySig.sharps]
        keySigStr += ']'

        return HumdrumToken(keySigStr)

    @staticmethod
    def keyDesignationTokenFromM21KeySignature(
            keySig: t.Union[m21.key.KeySignature, m21.key.Key]
    ) -> t.Optional[HumdrumToken]:
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
            m21Artics: t.List[m21.articulations.Articulation],
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
                continue

            # check for caesura (isn't in the lookup because it's an RDF signifier)
            if isinstance(artic, m21.articulations.Caesura):
                caesuraChar: str = owner.reportCaesuraToOwner()
                output += caesuraChar

        return output

    @staticmethod
    def _getMeasureContaining(gnote: m21.note.GeneralNote) -> t.Optional[m21.stream.Measure]:
        measure: t.Optional[m21.stream.Measure] = gnote.getContextByClass(m21.stream.Measure)
        return measure

    @staticmethod
    def _allSpannedGeneralNotesInSameMeasure(spanner: m21.spanner.Spanner) -> bool:
        measureOfFirstSpanned: t.Optional[m21.stream.Measure] = None
        for i, gnote in enumerate(spanner):
            if i == 0:
                measureOfFirstSpanned = gnote.getContextByClass(m21.stream.Measure)
                continue
            if gnote.getContextByClass(m21.stream.Measure) is not measureOfFirstSpanned:
                return False
        return True

    @staticmethod
    def _getHumdrumStringFromM21Expressions(
            m21Expressions: t.Sequence[t.Union[m21.expressions.Expression, m21.spanner.Spanner]],
            duration: m21.duration.Duration,
            recip: str,
            beamStarts: t.Optional[int] = None,
            owner=None
    ) -> str:
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
                    expr, duration, recip, beamStarts, owner
                )
                continue
            if isinstance(expr, m21.expressions.TrillExtension):
                # TODO: print('export of TrillExtension not implemented')
                continue
            if isinstance(expr, m21.expressions.Fermata):
                output += ';'
                if expr.type == 'upright':
                    output += '<'
                continue
            if M21Utilities.m21SupportsArpeggioMarks():
                if isinstance(expr, m21.expressions.ArpeggioMark):  # type: ignore
                    output += ':'
                    continue
                if isinstance(expr, m21.expressions.ArpeggioMarkSpanner):  # type: ignore
                    if M21Convert._allSpannedGeneralNotesInSameMeasure(expr):
                        output += ':'
                    else:
                        output += '::'
                    continue
        return output

    numberOfFlagsToDurationReciprocal: t.Dict[int, int] = {
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
    def _getHumdrumStringFromTremolo(
            tremolo: t.Union[m21.expressions.Tremolo, m21.expressions.TremoloSpanner],
            duration: m21.duration.Duration,
            recip: str,
            beamStarts: t.Optional[int],
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
        tvInt: t.Optional[int] = (
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
    ) -> t.List[str]:
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
    ) -> t.Tuple[str, str, t.List[str]]:
        if m21GeneralNote.tie is None:
            return ('', '', [])

        tieStr: str = ''
        layouts: t.List[str] = []

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

                    # Regular and NoBarline don't add anything
                    if (vStyle1 is MeasureVisualStyle.Regular
                            or vStyle1 is MeasureVisualStyle.NoBarline):
                        theLookup[(vStyle1, vStyle2)] = vStyle2
                        continue
                    if (vStyle2 is MeasureVisualStyle.Regular
                            or vStyle2 is MeasureVisualStyle.NoBarline):
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

    measureVisualStyleFromM21BarlineType: t.Dict[str, MeasureVisualStyle] = {
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
            return MeasureStyle.NoBarline

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
    m21BarlineTypeFromHumdrumType: t.Dict[str, str] = {
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
        outputBarline: t.Optional[m21.bar.Barline] = None
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

    # Conversions from str to m21.metadata.DateBlah types, and back.
    # e.g. '1942///-1943///' -> DateBetween([Date(1942), Date(1943)])
    # m21.metadata.DateBlah have conversions to/from str, and the strings are really close
    # to humdrum format, but not quite, and they don't handle some humdrum cases at all
    # (like the one above).  So I need to replace them here.

    # str -> DateSingle | DateRelative | DateBetween | DateSelection

    # approximate (i.e. not exactly, but reasonably close)
    _dateApproximateSymbols: t.Tuple[str, ...] = ('~', 'x')

    # uncertain (i.e. maybe not correct at all)
    _dateUncertainSymbols: t.Tuple[str, ...] = ('?', 'z')

    # date1-date2 or date1^date2 (DateBetween)
    # date1|date2|date3|date4... (DateSelection)
    _dateDividerSymbols: t.Tuple[str, ...] = ('-', '^', '|')

    @staticmethod
    def m21DateObjectFromString(
            string: str
    ) -> t.Optional[t.Union[m21.metadata.DateSingle,
                            m21.metadata.DateRelative,
                            m21.metadata.DateBetween,
                            m21.metadata.DateSelection]]:
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

        dateStrings: t.List[str] = [string]  # if we don't split it, this is what we will parse
        for divider in M21Convert._dateDividerSymbols:
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
            # Other DataBlah types use their relevance for other things, so leaving
            # the '~'/'?' in place to cause yearError to be set is a better choice.
            if '~' in dateStrings[0][0:1]:  # avoids crash on empty dateStrings[0]
                dateStrings[0] = dateStrings[0][1:]
                singleRelevance = 'approximate'
            elif '?' in dateStrings[0][0:1]:  # avoids crash on empty dateStrings[0]
                dateStrings[0] = dateStrings[0][1:]
                singleRelevance = 'uncertain'

        dates: t.List[m21.metadata.Date] = []
        for dateString in dateStrings:
            date: t.Optional[m21.metadata.Date] = M21Convert._dateFromString(dateString)
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
    def _stripDateError(value: str) -> t.Tuple[str, t.Optional[str]]:
        '''
        Strip error symbols from a numerical value. Return cleaned source and
        error symbol. Only one error symbol is expected per string.
        '''
        sym: t.Tuple[str, ...] = (
            M21Convert._dateApproximateSymbols + M21Convert._dateUncertainSymbols
        )
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

        # found is in M21Convert._dateUncertainSymbols
        value = value.replace(found, '')
        return value, 'uncertain'

    _dateAttrNames: t.List[str] = [
        'year', 'month', 'day', 'hour', 'minute', 'second'
    ]
    _dateAttrStrFormat: t.List[str] = [
        '%i', '%02.i', '%02.i', '%02.i', '%02.i', '%02.i'
    ]

    _highestSecondString: str = '59'

    @staticmethod
    def _dateFromString(dateStr: str) -> t.Optional[m21.metadata.Date]:
        # year, month, day, hour, minute are int, second is float
        # (each can be None if not specified)
        values: t.List[t.Optional[t.Union[int, float]]] = []

        # yearError, monthError, dayError, hourError, minuteError, secondError
        valueErrors: t.List[t.Optional[str]] = []
        dateStr = dateStr.replace(':', '/')
        dateStr = dateStr.replace(' ', '')
        gotOne: bool = False
        try:
            for i, chunk in enumerate(dateStr.split('/')):
                value, error = M21Convert._stripDateError(chunk)
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
        for attr, attrValue, attrError in zip(M21Convert._dateAttrNames, values, valueErrors):
            if attrValue is not None:
                setattr(date, attr, attrValue)
                if attrError is not None:
                    setattr(date, attr + 'Error', attrError)

        return date

    @staticmethod
    def stringFromM21DateObject(
        m21Date: t.Union[
            m21.metadata.DateSingle,
            m21.metadata.DateRelative,
            m21.metadata.DateBetween,
            m21.metadata.DateSelection]
    ) -> str:
        # m21Date is DateSingle, DateRelative, DateBetween, or DateSelection
        # (all derive from DateSingle (v7) or DatePrimitive (v8))
        # pylint: disable=protected-access
        output: str = ''
        dateString: str
        if isinstance(m21Date, m21.metadata.DateSelection):
            # series of multiple dates, delimited by '|'
            for i, date in enumerate(m21Date._data):
                dateString = M21Convert._stringFromDate(date)
                if i > 0:
                    output += '|'
                output += dateString

        elif isinstance(m21Date, m21.metadata.DateBetween):
            # two dates, delimited by '-'
            for i, date in enumerate(m21Date._data):
                dateString = M21Convert._stringFromDate(date)
                if i > 0:
                    output += '-'
                output += dateString

        elif isinstance(m21Date, m21.metadata.DateRelative):
            # one date, prefixed by '<' or '>' for 'prior'/'onorbefore' or 'after'/'onorafter'
            output = '<'  # assume before
            if m21Date.relevance in ('after', 'onorafter'):
                output = '>'

            dateString = M21Convert._stringFromDate(m21Date._data[0])
            output += dateString

        elif isinstance(m21Date, m21.metadata.DateSingle):
            # one date, no prefixes
            output = M21Convert._stringFromDate(m21Date._data[0])
            if m21Date.relevance == 'uncertain':
                # [0] is the date error symbol
                output = M21Convert._dateUncertainSymbols[0] + output
            elif m21Date.relevance == 'approximate':
                # [0] is the date error symbol
                output = M21Convert._dateApproximateSymbols[0] + output

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
            if not value:
                msg.append('')
            else:
                fmt = M21Convert._dateAttrStrFormat[i]
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
            output = (
                msg[0] + '/' + msg[1] + '/' + msg[2] + '/' + msg[3] + ':' + msg[4] + ':' + msg[5]
            )

        return output

    @staticmethod
    def _dateErrorToSymbol(value: str) -> str:
        if value.lower() in M21Convert._dateApproximateSymbols + ('approximate',):
            return M21Convert._dateApproximateSymbols[1]  # [1] is the single value error symbol
        if value.lower() in M21Convert._dateUncertainSymbols + ('uncertain',):
            return M21Convert._dateUncertainSymbols[1]    # [1] is the single value error symbol
        return ''

    @staticmethod
    def humdrumMetadataValueToM21MetadataValue(humdrumValue: m21.metadata.Text) -> t.Any:
        m21Value: t.Optional[t.Union[
            m21.metadata.Text,
            m21.metadata.DateSingle,
            m21.metadata.DateRelative,
            m21.metadata.DateBetween,
            m21.metadata.DateSelection]] = None

        if humdrumValue.encodingScheme == 'humdrum:date':
            # convert to m21.metadata.DateXxxx
            m21Value = M21Convert.m21DateObjectFromString(str(humdrumValue))
            if m21Value is None:
                # wouldn't convert to DateXxxx, leave it as Text
                m21Value = humdrumValue
        else:
            # default is m21.metadata.Text (even for Contributors)
            m21Value = humdrumValue

        return m21Value

    @staticmethod
    def stringFromM21Contributor(c: m21.metadata.Contributor) -> str:
        # TODO: someday support export of multi-named Contributors
        if not c.names:
            return ''
        return c.names[0]

    @staticmethod
    def m21UniqueNameToHumdrumKeyWithoutIndexOrLanguage(uniqueName: str) -> t.Optional[str]:
        hdKey: t.Optional[str] = (
            M21Convert._m21MetadataPropertyUniqueNameToHumdrumReferenceKey.get(uniqueName, None)
        )

        if hdKey is None:
            # see if it was a 'humdrumraw:XXX' passthru
            if uniqueName.startswith('humdrumraw:'):
                hdKey = uniqueName[11:]

        return hdKey

    @staticmethod
    def m21MetadataItemToHumdrumKeyWithoutIndex(uniqueName: str,
                                                value: t.Any
                                                ) -> t.Optional[str]:
        hdKey: t.Optional[str] = (
            M21Convert._m21MetadataPropertyUniqueNameToHumdrumReferenceKey.get(uniqueName, None)
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
    def m21MetadataItemToHumdrumReferenceLineStr(
            idx: int,         # this is the index to insert into the hdKey
            uniqueName: str,
            value: t.Any
    ) -> t.Optional[str]:
        valueStr: str = ''
        refLineStr: str = ''

        hdKey: t.Optional[str] = (
            M21Convert.m21UniqueNameToHumdrumKeyWithoutIndexOrLanguage(uniqueName)
        )
        if hdKey is not None:
            if idx > 0:
                # we generate 'XXX', 'XXX1', 'XXX2', etc
                hdKey += str(idx)
        else:
            # must be free-form personal key... pass it thru as is (no indexing)
            hdKey = uniqueName

        if isinstance(value, m21.metadata.Text):
            if value.language:
                if value.isTranslated:
                    hdKey += '@' + value.language.upper()
                else:
                    hdKey += '@@' + value.language.upper()
            valueStr = str(value)
        elif isinstance(value,
                (m21.metadata.DateSingle,
                m21.metadata.DateRelative,
                m21.metadata.DateBetween,
                m21.metadata.DateSelection)
        ):
            # We don't like str(DateXxxx)'s results so we do our own.
            valueStr = M21Convert.stringFromM21DateObject(value)
        elif isinstance(value, m21.metadata.Contributor):
            valueStr = M21Convert.stringFromM21Contributor(value)
        else:
            # it's already a str, we hope, but if not, we convert here
            valueStr = str(value)

        # html escape-ify the string, and convert any actual linefeeds to r'\n'
        valueStr = html.escape(valueStr)
        valueStr = valueStr.replace('\n', r'\n')

        if t.TYPE_CHECKING:
            assert hdKey is not None

        if valueStr == '':
            refLineStr = '!!!' + hdKey + ':'
        else:
            refLineStr = '!!!' + hdKey + ': ' + valueStr

        return refLineStr
