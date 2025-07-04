# ------------------------------------------------------------------------------
# Name:          HumdrumFile.py
# Purpose:       Top-level HumdrumFile object, which contains all the
#                conversion-to-music21-stream code, as well as notation
#                analysis, which is necessary to that conversion.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import re
import sys
import math
import html
import copy
import typing as t
from fractions import Fraction
from pathlib import Path

import music21 as m21
from music21.common import OffsetQL, opFrac

from music21.common.enums import OrnamentDelay
from converter21.humdrum import HumdrumInternalError, HumdrumSyntaxError
from converter21.humdrum import HumdrumFileContent
from converter21.humdrum import HumdrumLine
from converter21.humdrum import HumdrumToken
from converter21.humdrum import FakeRestToken
from converter21.humdrum import HumNum, HumNumIn
from converter21.humdrum import HumHash
from converter21.humdrum import HumParamSet
from converter21.humdrum import Convert
from converter21.humdrum import M21Convert
from converter21.shared import M21StaffGroupDescriptionTree
from converter21.shared import M21Utilities
from converter21.shared import SharedConstants

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

'''
    HumdrumFile class is HumdrumFileContent plus conversion to music21.stream.Score
'''

# Note that these durations are expressed in quarter notes, so
# Fraction(1,2), a.k.a "a half" actually means an eighth note,
# which has one beam.
durationNoDotsToNumBeams: dict[HumNum, int] = {
    opFrac(Fraction(1, 2)): 1,    # eighth note has 1 beam
    opFrac(Fraction(1, 4)): 2,    # 16th note has 2 beams
    opFrac(Fraction(1, 8)): 3,    # 32nd note has 3 beams
    opFrac(Fraction(1, 16)): 4,   # 64th note has 4 beams
    opFrac(Fraction(1, 32)): 5,   # 128th note has 5 beams
    opFrac(Fraction(1, 64)): 6,   # 256th note has 6 beams
    opFrac(Fraction(1, 128)): 7,  # 512th note has 7 beams
    opFrac(Fraction(1, 256)): 8,  # 1024th note has 8 beams
    opFrac(Fraction(1, 512)): 9,  # 2048th note has 9 beams
}

humdrumInstrumentClassCodeToInstrumentName: dict[str, str] = {
    'vox': 'Vocalist',
    'str': 'StringInstrument',
    'ww': 'WoodwindInstrument',
    'bras': 'BrassInstrument',
    'klav': 'KeyboardInstrument',
    'perc': 'Percussion',
}

humdrumInstrumentCodeToInstrumentName: dict[str, str] = {
    'soprn': 'Soprano',
    'cant': 'Soprano',  # Found in many sources, but not a predefined humdrum instrument
    'mezzo': 'MezzoSoprano',
    'calto': 'Contralto',
    'tenor': 'Tenor',
    'barit': 'Baritone',
    'bass': 'Bass',
    'vox': 'Vocalist',
    'feme': 'FemaleVoice',
    'male': 'MaleVoice',
    'nfant': 'ChildVoice',
    'recit': 'Recitativo',
    'lyrsp': 'LyricSoprano',
    'drmsp': 'DramaticSoprano',
    'colsp': 'ColoraturaSoprano',
    'alto': 'Alto',
    'ctenor': 'CounterTenor',
    'heltn': 'TenoreRobusto',
    'lyrtn': 'LyricTenor',
    'bspro': 'BassoProfondo',
    'bscan': 'BassoCantante',
    'false': 'Falsetto',
    'castr': 'Castrato',

    # String Instruments
    'archl': 'Archlute',  # archiluth (Fr.); liuto attiorbato/arcileuto/arciliuto (It.)
    'arpa': 'Harp',       # arpa (It.), arpa (Span.)
    'banjo': 'Banjo',
    'biwa': 'Biwa',
    'bguit': 'ElectricBass',
    'cbass': 'Contrabass',
    'cello': 'Violoncello',
    'cemba': 'Harpsichord',  # clavecin (Fr.); Cembalo (Ger.); cembalo (It.)
    'cetra': 'Cittern',      # cistre/sistre (Fr.); Cither/Zitter (Ger.); cetra/cetera (It.)
    'clavi': 'Clavichord',   # clavicordium (Lat.); clavicorde (Fr.)
    'dulc': 'Dulcimer',      # or cimbalom; Cimbal or Hackbrett (Ger.)
    'eguit': 'ElectricGuitar',
    'forte': 'FortePiano',
    'guitr': 'Guitar',       # guitarra (Span.); guitare (Fr.); Gitarre (Ger.); chitarra (It.)
    'hurdy': 'HurdyGurdy',   # variously named in other languages
    'liuto': 'Lute',         # lauto, liuto leuto (It.); luth (Fr.); Laute (Ger.)
    'kit': 'Kit',            # variously named in other languages
    'kokyu': 'Kokyu',        # (Japanese spike fiddle)
    'komun': 'KomunGo',      # (Korean long zither)
    'koto': 'Koto',          # (Japanese long zither)
    'mando': 'Mandolin',     # mandolino (It.); mandoline (Fr.); Mandoline (Ger.)
    'piano': 'Piano',
    'pipa': 'ChineseLute',
    'psalt': 'Psaltery',     # (box zither)
    'qin': 'Qin',            # ch'in (Chinese zither)
    'quitr': 'Gittern',      # (short-necked lute); quitarre (Fr.); Quinterne (Ger.)
    'rebec': 'Rebec',        # rebeca (Lat.); rebec (Fr.); Rebec (Ger.)
    'bansu': 'Bansuri',
    'sarod': 'Sarod',
    'shami': 'Shamisen',     # (Japanese fretless lute)
    'sitar': 'Sitar',
    'tambu': 'Tambura',      # tanpura
    'tanbr': 'Tanbur',
    'tiorb': 'Theorbo',      # tiorba (It.); tèorbe (Fr.); Theorb (Ger.)
    'ud': 'Ud',
    'ukule': 'Ukulele',
    'vina': 'Vina',
    'viola': 'Viola',               # alto (Fr.); Bratsche (Ger.)
    'violb': 'BassViolaDaGamba',    # viole (Fr.); Gambe (Ger.)
    'viold': 'ViolaDamore',         # viole d'amour (Fr.); Liebesgeige (Ger.)
    'violn': 'Violin',              # violon (Fr.); Violine or Geige (Ger.); violino (It.)
    'violp': 'PiccoloViolin',       # violino piccolo (It.)
    'viols': 'TrebleViolaDaGamba',  # viole (Fr.); Gambe (Ger.)
    'violt': 'TenorViolaDaGamba',   # viole (Fr.); Gambe (Ger.)
    'zithr': 'Zither',              # Zither (Ger.); cithare (Fr.); cetra da tavola (It.)

    # Wind Instruments
    'accor': 'Accordion',        # accordéon (Fr.); Akkordeon (Ger.)
    'armon': 'Harmonica',        # armonica (It.)
    'bagpS': 'Bagpipes',         # (Scottish)
    'bagpI': 'Bagpipes',         # (Irish)
    'baset': 'BassettHorn',
    'calam': 'Chalumeau',        # calamus (Lat.); kalamos (Gk.)
    'calpe': 'Calliope',
    'cangl': 'EnglishHorn',      # cor anglais (Fr.)
    'chlms': 'SopranoShawm',     # chalmeye, shalme, etc.; chalemie (Fr.); ciaramella (It.)
    'chlma': 'AltoShawm',        # chalmeye, shalme, etc.
    'chlmt': 'TenorShawm',       # chalmeye, shalme, etc.
    'clars': 'SopranoClarinet',  # (in either B-flat or A); clarinetto (It.)
    'clarp': 'PiccoloClarinet',
    'clara': 'AltoClarinet',     # (in E-flat)
    'clarb': 'BassClarinet',     # (in B-flat)
    'cor': 'Horn',               # cor (Fr.); corno (It.); Horn (Ger.)
    'cornm': 'Cornemuse',        # French bagpipe
    'corno': 'Cornett',          # (woodwind instr.); cornetto (It.); cornaboux (Fr.); Zink (Ger.)
    'cornt': 'Cornet',           # (brass instr.); cornetta (It.); cornet à pistons (Fr.);
                                 #   Cornett (Ger.)
    'ctina': 'Concertina',       # concertina (Fr.); Konzertina (Ger.)
    'fagot': 'Bassoon',          # fagotto (It.)
    'fag_c': 'Contrabassoon',    # contrafagotto (It.)
    'fife': 'Fife',
    'flt': 'Flute',              # flauto (It.); Flöte (Ger.); flûte (Fr.)
    'flt_a': 'AltoFlute',
    'flt_b': 'BassFlute',
    'fltds': 'SopranoRecorder',  # flûte à bec, flûte douce (Fr.);
    #                              Blockflöte (Ger.); flauto dolce (It.)
    'fltdn': 'SopraninoRecorder',
    'fltda': 'AltoRecorder',
    'fltdt': 'TenorRecorder',
    'fltdb': 'BassRecorder',
    'flugh': 'Flugelhorn',
    'hichi': 'Hichiriki',        # (Japanese double reed used in gagaku)
    'krums': 'SopranoCrumhorn',  # Krummhorn/Krumbhorn (Ger.); tournebout (Fr.)
    'kruma': 'AltoCrumhorn',
    'krumt': 'TenorCrumhorn',
    'krumb': 'BassCrumhorn',
    'nokan': 'Nokan',        # (Japanese flute for the no theatre)
    'oboe': 'Oboe',          # hautbois (Fr.); Hoboe, Oboe (Ger.): oboe (It.)
    'oboeD': 'OboeDamore',
    'ocari': 'Ocarina',
    'organ': 'PipeOrgan',    # organum (Lat.); organo (It.); orgue (Fr.); Orgel (Ger.)
    'panpi': 'PanFlute',     # panpipe
    'picco': 'Piccolo',      # flute
    'piri': 'KoreanPiri',
    'porta': 'PortativeOrgan',
    'rackt': 'Racket',       # Rackett (Ger.); cervelas (Fr.)
    'reedo': 'ReedOrgan',
    'sarus': 'Sarrusophone',
    'saxN': 'SopraninoSaxophone',   # (in E-flat)
    'saxS': 'SopranoSaxophone',     # (in B-flat)
    'saxA': 'AltoSaxophone',        # (in E-flat)
    'saxT': 'TenorSaxophone',       # (in B-flat)
    'saxR': 'BaritoneSaxophone',    # (in E-flat)
    'saxB': 'BassSaxophone',        # (in B-flat)
    'saxC': 'ContrabassSaxophone',  # (in E-flat)
    'shaku': 'Shakuhachi',
    'sheng': 'MouthOrgan',          # (Chinese)
    'sho': 'MouthOrgan',            # (Japanese)
    'sxhS': 'SopranoSaxhorn',       # (in B-flat)
    'sxhA': 'AltoSaxhorn',          # (in E-flat)
    'sxhT': 'TenorSaxhorn',         # (in B-flat)
    'sxhR': 'BaritoneSaxhorn',      # (in E-flat)
    'sxhB': 'BassSaxhorn',          # (in B-flat)
    'sxhC': 'ContrabassSaxhorn',    # (in E-flat)
    'tromt': 'Trombone',            # tenor; trombone (It.); trombone (Fr.); Posaune (Ger.)
    'tromb': 'BassTrombone',
    'tromp': 'Trumpet',             # tromba (It.); trompette (Fr.); Trompete (Ger.)
    'tuba': 'Tuba',
    'zurna': 'Zurna',

    # Percussion Instruments
    'bdrum': 'BassDrum',         # (kit)
    'campn': 'ChurchBells',      # bell; campana (It.); cloche (Fr.); campana (Span.)
    'caril': 'ChurchBells',      # carillon
    'casts': 'Castanets',        # castañetas (Span.); castagnette (It.)
    'chime': 'TubularBells',     # chimes
    'clest': 'Celesta',          # céleste (Fr.)
    'crshc': 'CrashCymbals',     # (kit)
    'fingc': 'FingerCymbal',
    'glock': 'Glockenspiel',
    'gong': 'Gong',
    'marac': 'Maracas',
    'marim': 'Marimba',
    'piatt': 'Cymbals',          # piatti (It.); cymbales (Fr.); Becken (Ger.); kymbos (Gk.)
    'ridec': 'RideCymbals',      # (kit)
    'sdrum': 'SnareDrum',        # (kit)
    'spshc': 'SplashCymbals',    # (kit)
    'steel': 'SteelDrum',        # tinpanny
    'tabla': 'Tabla',
    'tambn': 'Tambourine',       # timbrel; tamburino (It.); Tamburin (Ger.)
    'timpa': 'Timpani',          # timpani (It.); timbales (Fr.); Pauken (Ger.)
    'tom': 'TomTom',             # drum
    'trngl': 'Triangle',         # triangle (Fr.); Triangel (Ger.); triangolo (It.)
    'vibra': 'Vibraphone',
    'xylo': 'Xylophone',         # xylophone (Fr.); silofono (It.)

    # Keyboard Instruments
    # dup *Iaccor    accordion; accordéon (Fr.); Akkordeon (Ger.)
    # dup *Icaril    carillon
    # dup *Icemba    harpsichord; clavecin (Fr.); Cembalo (Ger.); cembalo (It.)
    # dup *Iclavi    clavichord; clavicordium (Lat.); clavicorde (Fr.)
    # dup *Iclest    'Celesta',          # céleste (Fr.)
    # dup *Iforte    fortepiano
    'hammd': 'ElectricOrgan',    # Hammond electronic organ
    # dup *Iorgan    pipe organ; orgue (Fr.); Orgel (Ger.);
    # organo (It.); organo (Span.); organum (Lat.)
    # dup *Ipiano    pianoforte
    # dup *Iporta    portative organ
    # dup *Ireedo    reed organ
    'rhode': 'ElectricPiano',    # Fender-Rhodes electric piano
    'synth': 'Synthesizer',      # keyboard synthesizer
}

class Phrase(m21.spanner.Slur):
    '''
    A Slur that represents a Phrase.  Code that doesn't know about Phrases will
    (hopefully) just see that it is a Slur.  Code that does know about Phrases
    can do Phrase-specific things.
    '''

class HumdrumTie:
    def __init__(
        self,
        startLayerIndex: int,
        startNote: m21.note.Note | m21.note.Unpitched,
        startToken: HumdrumToken,
        startSubTokenStr: str,
        startSubTokenIdx: int
    ) -> None:
        self.startLayerIndex: int = startLayerIndex
        self.startNote: m21.note.Note | m21.note.Unpitched = startNote
        self.startToken: HumdrumToken = startToken
        self.startSubTokenStr: str = startSubTokenStr
        self.startSubTokenIdx: int = startSubTokenIdx

        # pitch computation is a little sloppy (on purpose?).
        # This will (e.g.) allow a C-flat to be tied to a B-natural.
        # base40 would be more stringent, but wouldn't work for triple
        # flats and triple sharps.
        self.pitch: int = Convert.kernToMidiNoteNumber(startSubTokenStr)
        self.startTime: HumNum = opFrac(startToken.durationFromStart)
        self.endTime: HumNum = opFrac(self.startTime + opFrac(startToken.duration))

        self.wasInserted: bool = False

    def setEndAndInsert(
        self,
        endNote: m21.note.Note | m21.note.Unpitched,
        endSubTokenStr: str
    ) -> m21.tie.Tie:
        startTieType: str = 'start'
        if '_' in self.startSubTokenStr:
            startTieType = 'continue'

        startTie: m21.tie.Tie = m21.tie.Tie(startTieType)
        self.startNote.tie = startTie

        # also add an end tie to endNote (but not if the end tie is a continue,
        # which will be handled shortly since it's in the list as a start)
        if ']' in endSubTokenStr:  # not '_'
            endNote.tie = m21.tie.Tie('stop')  # that's it, no style or placement

        self.wasInserted = True
        return startTie

class HumdrumBeamAndTuplet:
    # A struct (per note/chord/rest) describing a beam and/or tuplet group.
    # Tuplets can contain rests, but beams cannot.
    def __init__(self) -> None:
        # for tuplets

        # tuplet group number (within layer)
        self.group: int = 0

        self.duration: HumNum = opFrac(0)
        self.durationNoDots: HumNum = opFrac(0)

        # numNotesActual and numNotesNormal are a ratio of sorts, but tupletRatio holds
        # the lowest-common-denominator ratio.  For example, for a tuplet that has 15 16th notes
        # in the space of 10 16th notes, numNotesActual is 15, and numNotesNormal is 10, but
        # tupletMultiplier is still 2/3 (i.e. all note durations are 2/3 of normal duration)
        self.numNotesActual: int = 1
        self.numNotesNormal: int = 1
        self.tupletMultiplier: HumNum = opFrac(1)
        self.numScale: int = 1
        self.durationTupleNormal: m21.duration.DurationTuple | None = None

        self.tupletStart: int = 0  # set to tuplet group number (on starting note/rest)
        self.tupletEnd: int = 0    # set to tuplet group number (on ending note/rest)

        # True if Humdrum data made us start or end this tuplet at a specific location.
        self.forceStartStop: bool = False

        # for beamed normal notes
        self.beamStart: int = 0  # set to beam number on starting note
        self.beamEnd: int = 0    # set to beam number on ending note

        # for beamed grace notes
        self.gbeamStart: int = 0  # set to beam number on starting grace note
        self.gbeamEnd: int = 0    # set to beam number on ending grace note

        # for all

        # the token for this note/rest
        self.token: HumdrumToken | FakeRestToken | None = None


class BeamAndTupletGroupState:
    # A struct containing the current state of beams and tuplets as we walk the tokens in a layer
    def __init__(self) -> None:
        # for beams
        self.inBeam: bool = False             # set True when a beam starts, False when it ends
        self.previousBeamTokenIdx: int = -1   # index (in layer) of the previous token in a beam

        # for grace note beams
        self.inGBeam: bool = False            # set True when a gbeam starts, False when it ends
        self.previousGBeamTokenIdx: int = -1  # index (in layer) of the previous token in a gbeam

        # for tuplets
        self.inTuplet: bool = False           # set True when a tuplet starts, False when it ends
        # tuplet template for every note in the current tuplet
        self.m21Tuplet: m21.duration.Tuplet | None = None


MAX_LAYERS_FOR_STAFF_STATE_LISTS: int = 100

class StaffStateVariables:
    def __init__(self) -> None:
        '''
            First we have permanent info we have figured out about this staff
        '''
        # the m21 Part for the staff
        self.m21Part: m21.stream.Part | None = None

        # Whether the Part is actually a PartStaff (or should be when created)
        # Set when perusing *part and *staff exInterps.  If a particular *part
        # number has multiple *staff numbers then we should create a PartStaff
        # for each different *staff in the *part.  If there is only one *staff
        # in a *part, then we should create a Part for that *staff/*part.
        self.isPartStaff: bool = False

        # verse == keeps track of whether or not staff contains associated
        # **text/**silbe spines which will be converted into lyrics.
        # Also **vdata and **vvdata spines --gregc
        self.hasLyrics: bool = False

        # verse_labels == List of verse labels that need to be added to the
        # current staff.
        self.verseLabels: list[HumdrumToken] = []

        # figured bass
        self.figuredBassState: int | None = None
        self.isStaffWithFiguredBass: bool = False  # true if staff has figured bass

        # instrument info
        self.instrumentClass: str = ''   # e.g. 'bras' is BrassInstrument
        self.instrumentCode: str = ''    # e.g. 'clars' is Soprano Clarinet
        self.instrumentName: str = ''    # e.g. 'Piano'
        self.instrumentAbbrev: str = ''  # e.g. 'Pno.'

        # hand-transposition info (we have to undo it as we translate to music21, since
        # there is no way in music21 to mark a staff has having been transposed from the
        # original).
        # This is completely orthogonal to transposing instruments, which are handled
        # entirely separately.
#         self.wasTransposedBy = 0  # base40

        # staff info
        self.staffScaleFactor: float = 1.0
        self.numStaffLines: int = 5

        self.dynamPosDefined: bool = False
        self.dynamPos: int = 0
        self.dynamStaffAdj: int = 0

        self.tgs: dict[
            tuple[int | None, int],  # MeasureKey
            list[list[HumdrumBeamAndTuplet | None]]  # top list is per layer
        ] = {}

        # first info in part (we hang on to these here, waiting for a Measure to put them in)
        self.firstM21Clef: m21.clef.Clef | None = None
        self.firstM21KeySig: m21.key.KeySignature | m21.key.Key | None = None
        self.firstM21TimeSig: m21.meter.TimeSignature | None = None

        # ties (list of starts that we search when we see an end)
        self.ties: list[HumdrumTie] = []

        # tremolo is active on this staff (*tremolo and *Xtremolo)
        self.tremolo: bool = False

        # noteHead style for this staff, according to *head interpretation
        self.noteHead: str = ''

        # stemType for each layer in this staff
        self.stemType: list[str] = [''] * MAX_LAYERS_FOR_STAFF_STATE_LISTS

        # are notes in specific layer cue-sized? (according to *cue and *Xcue interps)
        self.cueSize: list[bool] = [False] * MAX_LAYERS_FOR_STAFF_STATE_LISTS

        # are tuplets suppressed in this staff?
        # (according to *beamtup/*Xbeamtup, *brackettup/*Xbrackettup, *tuplet/*Xtuplet)
        self.suppressTupletNumber: bool = False
        self.suppressTupletBracket: bool = False

        # ottava stuff (each current ottava is not None if we're currently
        # accumulating notes into that ottava).
        self.currentOttava1Up: m21.spanner.Ottava | None = None
        self.currentOttava1Down: m21.spanner.Ottava | None = None
        self.currentOttava2Up: m21.spanner.Ottava | None = None
        self.currentOttava2Down: m21.spanner.Ottava | None = None
        self.hasOttavas: bool = False

        '''
            Next we have temporary (processing) state about this staff (current keysig, etc)
        '''
        self.mostRecentlySeenClefTok: HumdrumToken | None = None
        self.currentM21KeySig: m21.key.KeySignature | m21.key.Key | None = None
        # pylint: disable=no-member
        self.currentPedalMark: m21.expressions.PedalMark | None = None  # type: ignore
        # pylint: enable=no-member

    def printState(self, prefix: str) -> None:
        print(f'{prefix}hasLyrics: {self.hasLyrics}', file=sys.stderr)
        print(f'{prefix}verseLabels: {self.verseLabels}', file=sys.stderr)


class HumdrumFile(HumdrumFileContent):
    # add XML print routines?

    def __init__(
        self,
        fileName: str | Path | None = None,
        acceptSyntaxErrors: bool = False
    ) -> None:
        M21Utilities.adjustMusic21Behavior()

        super().__init__(fileName, acceptSyntaxErrors)  # initialize the HumdrumFileBase fields


        # The m21Score attribute will not exist until it is set up (in createMusic21Stream)
        # and it will not be None at that point.
        # self.m21Score: m21.stream.Score

        # all sorts of info about each staff, and some temporary state as well
        self._staffStates: list[StaffStateVariables] = []  # len = staffCount

        # ignore the following lines.
        # Note that we only pay attention to this at barlines (and if the barline is commented
        # out, we ignore the entire following measure).
        self.ignoreLine: list[bool] = []  # will contain one bool per line in the file

        # top-level info
        self._hasHarmonySpine: bool = False
        self._chosenHarmonyDataType: str = ''
        self._hasFingeringSpine: bool = False
        self._hasKernSpine: bool = False
        self._hasStringSpine: bool = False
        self._hasMensSpine: bool = False
        self._hasFiguredBassSpine: bool = False
        self._hasColorSpine: bool = False
        self._hasTremolo: bool = False  # *tremolo interpretation has been seen in first pass

        # initial state (after parsing the leading comments and interps)

        # time signature info
        self._timeSigDurationsByLine: list[HumNum] = []

        # each tuple is (top: int, bot: int, lineIndex: int)
        self._timeSignaturesWithLineIdx: list[tuple[int, int, int]] = []

        # oclef, omet, okey (mens-only stuff)
        #   each tuple is (partNum, token)
        self._oclefs: list[tuple[int, HumdrumToken]] = []
        self._omets: list[tuple[int, HumdrumToken]] = []
        self._okeys: list[tuple[int, HumdrumToken]] = []


        # section support (for repeat endings a.k.a. RepeatBracket spanners)
        self._sectionLabels: list[HumdrumToken | None] = []
        self._numberlessLabels: list[HumdrumToken | None] = []
        self._lastSection: str = ''
        self._endingNum: int = 0
        self._currentEndingPerStaff: list[m21.spanner.RepeatBracket] = []

        # staff group names and abbreviations
        self._groupNames: dict[int, str] = {}
        self._groupNameTokens: dict[int, HumdrumToken] = {}
        self._groupAbbrevs: dict[int, str] = {}
        self._groupAbbrevTokens: dict[int, HumdrumToken] = {}

        # metadata (from biblio records)
        # We use a list of key/value pairs instead of a dictionary
        # because keys aren't necessarily unique.
        self._biblio: list[tuple[str, str]] = []

        # parsed from things like !!!LO-style:REH:enc=dbox:color=limegreen:fs=200%
        self._layoutDefaultStyles: dict[str, dict[str, str]] = {}

        # conversion processing state

        # _currentMeasureLayerTokens: current system measure represented as a 3d list of tokens.
        # It contains a list of staves, each of which is a list of layers, each of which
        # is a list of tokens. This is produced by _generateStaffLayerTokensForMeasure()
        self._currentMeasureLayerTokens: list[
            list[list[HumdrumToken | FakeRestToken]]
        ] = []

        # _scoreLayerTokens: contains the 3d list of tokens for all the system measures,
        # held in a dictionary, one element per system measure, where the key is a tuple
        # holding the start and end line index for the measure (startIdx -> '=N', endIdx -> '=N+1')
        self._scoreLayerTokens: dict[
            tuple[int | None, int],  # MeasureKey
            list[list[list[HumdrumToken | FakeRestToken]]]
        ] = {}

        # measureKey is tuple[startLineIdx, endLineIdx], where both lines are barlines
        #   (or 0 for first bar)
        # We need to be able to get a measureIndex from measureKey, or from startIdx or endIdx.
        # Here is where we build up that picture.
        self._measureIndexFromKey: dict[
            tuple[int | None, int],  # measureKey
            int                             # measureIndex
        ] = {}

        # We need to be able to get a measureIndex from a lineIndex as well.
        # This array of measure indices has an element for every line in the file.
        # Note that this is a little different from the definition of measureKey,
        # where both the startLineIdx and endLineIdx point at barlines.  Here,
        # the measureIndex of a barline is the index of the measure that _starts_
        # with that barline.
        self._measureIndexFromLineIndex: list[int] = []

        # _allMeasuresPerStaff: list of all measures per staff.
        # Indexed by measureIndex (0:numMeasures), then by staffIndex (0:numStaves).
        self._allMeasuresPerStaff: list[list[m21.stream.Measure]] = []

        # _m21BreakAtStartOfNextMeasure: a SystemLayout or PageLayout object to be inserted
        # at start of the next measure
        self._m21BreakAtStartOfNextMeasure: m21.Music21Object | None = None

        self._currentOMDDurationFromStart: HumNum = opFrac(0)

    @staticmethod
    def getInstrumentNameFromCode(instrumentCode: str, iTrans: str | None) -> str:
        iName: str = ''
        if instrumentCode not in humdrumInstrumentCodeToInstrumentName:
            return instrumentCode

        iName = humdrumInstrumentCodeToInstrumentName[instrumentCode]

        if iTrans is None or iTrans == '':
            return iName

        # Some instruments always have a specific key, such as
        # alto flute, which is in G, but the transposition is
        # often not given in the name.  These are the transpositions
        # that need to be given in the name...
        if iTrans == '*ITrd1c2':
            return iName + ' in B-flat'  # sounds B-flat below C
        if iTrans == '*ITrd2c3':
            return iName + ' in A'       # sounds A below C
        if iTrans == '*ITrd5c9':
            return iName + ' in E-flat'  # sounds E-flat below C
        if iTrans == '*ITrd-2c-3':
            return iName + ' in E-flat'  # sounds E-flat above C

        return iName

    @staticmethod
    def getInstrumentNameFromClassCode(instrumentClassCode: str) -> str:
        if instrumentClassCode in humdrumInstrumentClassCodeToInstrumentName:
            return humdrumInstrumentClassCodeToInstrumentName[instrumentClassCode]

        return instrumentClassCode

    def createMusic21Stream(self) -> m21.stream.Score:
        # First, analyze notation: this is extra analysis, not done by default,
        # which lives in HumdrumFileContent

        # pylint: disable=attribute-defined-outside-init
        self.m21Score: m21.stream.Score = m21.stream.Score()
        if self.numSyntaxErrorsFixed > 0:
            self.m21Score.c21_syntax_errors_fixed = self.numSyntaxErrorsFixed  # type: ignore

        if not self.isValid:
            # input file did not parse successfully, give up.  Return an empty score.
            return self.m21Score

        # You can comment out sections of a Humdrum file using the following global comments:
        # !!ignore
        # !!Xignore
        # Note that we only pay attention to this at barlines (and if the barline is commented
        # out, we ignore the entire following measure).
        self._initializeIgnoreLineVector()

        # Create a list of the parts, and which spine represents them
        self._staffStarts = self.spineStartListOfType(['**kern', '**mens'])

        if not self._staffStarts:  # if empty list or None
            # No parts in file, give up.  Return an empty score.
            return self.m21Score

        self.analyzeDefaultLayoutStyles()
        self.analyzeNotation()

        # init some lists of staff info
        self._initializeStaffStates()

        # figure out what we have
        self._analyzeSpineDataTypes()

        # reverse staff start order, since top part is last spine
        self._staffStarts.reverse()
        self._calculateStaffStartsIndexByTrack()

        # prepare more stuff
        self._prepareVerses()          # which staffs have associated lyrics?
        self._prepareSections()        # associate numbered/unnumbered section names with lines
        self._prepareMetadata()        # pull standard biblio keys/values out of reference records
        self._prepareTimeSignatures()  # gather time signature info

        # Creates Parts, PartStaffs, and StaffGroups, as appropriate,
        # using !!system-decoration, if present.
        self._createStaffGroupsAndParts()

        # m21.metadata.Metadata for the score
        self._createScoreMetadata()

        # prepare layer token lists for the whole score, in anticipation of two passes:
        # first pass, and then conversion (second pass)
        self._prepareScoreLayerTokens()

        # first pass over the layer tokens (e.g. mark all the tremolos)

        # Assume no staff starts earlier than the first
        lineIdx: int = self._staffStarts[0].lineIndex
        while lineIdx < self.lineCount - 1:
            # self._firstPassSystemMeasure returns the line idx of the next measure to process
            lineIdx = self._firstPassSystemMeasure(lineIdx)

        # clear any staff state we modified (in first pass) back to initial state for second pass
        self._prepareForSecondPass()

        # prepare all the system measures
        self._prepareSystemMeasures()

        # conversion (second) pass over all the measures' layer tokens
        lineIdx = self._staffStarts[0].lineIndex  # assumes no staff starts earlier than the first
        while lineIdx < self.lineCount - 1:
            # self._convertSystemMeasure returns the line idx of the next measure
            lineIdx = self._convertSystemMeasure(lineIdx)
#            self._checkForInformalBreak(lineIdx)

        self._processHangingTieStarts()

        # Fill intermediate elements in Ottavas.  This needs to happen before any
        # transposition because Ottavas must be filled to be transposed correctly.
        for sp in self.m21Score.spannerBundle:
            if not isinstance(sp, m21.spanner.Ottava):
                continue
            spStaffIndex: int = -1
            if hasattr(sp, 'humdrum_staff_index'):
                spStaffIndex = sp.humdrum_staff_index  # type: ignore
            if spStaffIndex >= 0:
                ss: StaffStateVariables = self._staffStates[spStaffIndex]
                ss.hasOttavas = True
                if ss.m21Part is not None:
                    # depending on voicing, the last element in the ottava may not be the
                    # element with the highest end time.  That's unfortunate, because that
                    # is what spanner.fill assumes.  So find that element, remove and
                    # re-add it, so that it is the last element in the ottava.
                    M21Utilities.adjustSpannerOrder(sp, ss.m21Part)
                    sp.fill(ss.m21Part)

        # Transpose any transposing instrument parts (or parts with ottavas) to "written pitch".
        # For performance, check the instruments/ottavas here, since stream.toWrittenPitch can
        # be expensive, even if there is no transposing instrument or ottavas.
        for ss in self._staffStates:
            if ss.m21Part is not None:
                hasTransposingInstrument: bool = False
                for inst in ss.m21Part.getElementsByClass(m21.instrument.Instrument):
                    if M21Utilities.isTransposingInstrument(inst):
                        hasTransposingInstrument = True
                        break
                if hasTransposingInstrument or ss.hasOttavas:
                    ss.m21Part.toWrittenPitch(inPlace=True, preserveAccidentalDisplay=True)

        # set c21_syntax_errors_fixed again, because actually generating the score might
        # have caused us to fix more syntax errors.
        if self.numSyntaxErrorsFixed > 0:
            self.m21Score.c21_syntax_errors_fixed = self.numSyntaxErrorsFixed  # type: ignore
        return self.m21Score

    def _prepareForSecondPass(self) -> None:
        for ss in self._staffStates:
            # ss.tremolo is set to True and False as we run across *tremolo and *Xtremolo
            # while traversing the layers during first pass. At start of second pass, it
            # should be False, just like it was for the first pass.
            ss.tremolo = False

    def measureIndexFromKey(self, measureKey: tuple[int | None, int]) -> int:
        return self._measureIndexFromKey[measureKey]

    def measureIndexFromLineIndex(self, lineIndex: int) -> int:
        return self._measureIndexFromLineIndex[lineIndex]

    def _prepareSystemMeasures(self) -> None:
        # create measureIndexFromLineIndex list
        self._measureIndexFromLineIndex = [-1] * self.lineCount

        # assume no staff starts earlier than the first
        lineIdx: int = self._staffStarts[0].lineIndex
        while lineIdx < self.lineCount - 1:
            measureKey: tuple[int | None, int] = self._measureKey(lineIdx)
            startIdx, endIdx = measureKey
            if startIdx is None:
                lineIdx = endIdx
                continue

            if self.ignoreLine[startIdx]:
                # don't prepare this measure (!!ignore/!!Xignore toggles)
                lineIdx = endIdx
                continue

            offsetInScore: HumNum = self._lines[startIdx].durationFromStart
            if offsetInScore < 0:
                print(f'offsetInScore(startIdx={startIdx}) is negative: {offsetInScore}',
                        file=sys.stderr)
                offsetInScore = opFrac(0)

            self._setupSystemMeasures(measureKey, offsetInScore)

            # set up measureIndexFromLineIndex for this range of lines
            measureIndex = self.measureIndexFromKey(measureKey)
            for li in range(startIdx, endIdx):  # leave endIdx for the next measure
                self._measureIndexFromLineIndex[li] = measureIndex

            lineIdx = endIdx

        # loop over everything again, setting measure styles
        # This is a second loop so we can see the next measure as well as this one.
        lineIdx = self._staffStarts[0].lineIndex
        while lineIdx < self.lineCount - 1:
            measureKey = self._measureKey(lineIdx)
            startIdx, endIdx = measureKey
            if startIdx is None:
                lineIdx = endIdx
                continue

            if self.ignoreLine[startIdx]:
                # don't prepare this measure (!!ignore/!!Xignore toggles)
                lineIdx = endIdx
                continue

            self._setSystemMeasureStyle(measureKey)

            lineIdx = endIdx

    '''
    //////////////////////////////
    //
    // HumdrumInput::initializeIgnoreVector -- Mark areas of the input file that
    //     should not be converted into
        ... the music21 score.
        Note that we only pay attention to this at barlines (and if the barline is commented
        out, we ignore the entire following measure).
    '''
    def _initializeIgnoreLineVector(self) -> None:
        self.ignoreLine = [False] * self.lineCount
        state: bool = False
        for i, line in enumerate(self._lines):
            self.ignoreLine[i] = state
            if not line.isGlobalComment:
                continue
            if line.text == '!!ignore':
                state = True
            elif line.text == '!!Xignore':
                state = False

    '''
    //////////////////////////////
    //
    // HumdrumInput::processHangingTieStarts -- Deal with tie starts that were
    //    never matched with tie ends.
    '''
    def _processHangingTieStarts(self) -> None:
        for ss in self._staffStates:
            for tie in ss.ties:
                self._processHangingTieStart(tie)

    '''
    //////////////////////////////
    //
    // HumdrumInput::processHangingTieStart --

        For music21 output we handle this a little differently than iohumdrum.cpp does
        for MEI output.  In music21, describing a tie with only a start note is easy,
        and we can leave the problem of what to do in this case to the individual
        exporters.
    '''
    def _processHangingTieStart(self, tieInfo: HumdrumTie) -> None:
        tieType: str = 'start'
        if '_' in tieInfo.startSubTokenStr:
            tieType = 'continue'

        tieInfo.startNote.tie = m21.tie.Tie(tieType)
        self._addTieStyle(tieInfo.startNote.tie, tieInfo.startToken,
                          tieInfo.startSubTokenStr, tieInfo.startSubTokenIdx)

    '''
    //////////////////////////////
    //
    // HumdrumInput::processHangingTieEnd --

        For music21 output we handle this a little differently than iohumdrum.cpp does
        for MEI output.  In music21, describing a tie with only an end note is easy,
        and we can leave the problem of what to do in this case to the individual
        exporters.
    '''
    @staticmethod
    def _processHangingTieEnd(note: m21.note.Note | m21.note.Unpitched, tstring: str) -> None:
        if '_' in tstring:
            return  # 'continue' will be handled in the ss.ties list as a tieStart

        note.tie = m21.tie.Tie('stop')  # that's it, no style or placement

    @property
    def staffCount(self) -> int:
        return len(self._staffStarts)

    def _initializeStaffStates(self) -> None:
        self._staffStates = []
        for _ in range(0, self.staffCount):
            self._staffStates.append(StaffStateVariables())

    def _prepareMetadata(self) -> None:
        # We take every instance of each key, but... I make an exception for OMD,
        # because it is also used as a tempo change at start of any measure, so
        # you only want the OMDs before the first note for the "movement names".
        # I give you beethoven piano sonata21-3.krn as an example.  First OMD is
        # 'Rondo: Allegretto moderato', and last OMD (in a measure in the middle
        # of the movement) is 'Prestissimo'.  The movement name is 'Rondo: Allegretto'. --gregc
        # Note: if we end up with an OMD ('movementName') metadata item and
        # an OTL ('title') metadata item, and they are exactly the same, then we
        # ignore the title, and retain the movementName.
        firstDataLineIdx: int = self.lineCount  # one off the end
        for line in self._lines:
            if line.isData:
                firstDataLineIdx = line.lineIndex
                break

        for bibLine in self.referenceRecords():
            if bibLine.text.startswith('!!!!'):
                # skip the universal records for now, we don't handle multi-score Humdrum files
                continue

            key = bibLine.referenceKey
            value = bibLine.referenceValue

            # system-decoration and RDF** are referenceRecords, but should not
            # go in self._biblio, since they are not metadata.
            if key == 'system-decoration':
                continue
            if key.startswith('RDF**'):
                continue

            if value:
                value = html.unescape(value)
                value = value.replace(r'\n', '\n')
            if not value:
                continue

            if key == 'OMD':
                # only take OMDs before the firstDataLineIdx as movementName in metadata,
                # because after the first data line, they're not movementNames, just
                # tempo changes.  But only take them as movementName if they actually have
                # a tempoName (or are just a name with no mm info).
                if bibLine.lineIndex < firstDataLineIdx:
                    # strip off any [quarter = 128] suffix, and any 'M.M.' or 'M. M.' or etc.
                    tempoName, mmStr, noteName, bpmText = (
                        Convert.getMetronomeMarkInfo(value)
                    )
                    if not tempoName and not mmStr and not noteName and not bpmText:
                        self._biblio.append((key, value))
                    elif tempoName:
                        tempoName.strip()
                        if tempoName:
                            value = tempoName
                            self._biblio.append((key, value))
            else:
                self._biblio.append((key, value))

        titles: list[str] = []
        movementNames: list[str] = []
        for k, v in self._biblio:
            if k == 'OMD':
                movementNames.append(v)
                continue
            if k == 'OTL':
                titles.append(v)
                continue

        if len(titles) == 1 and len(movementNames) == 1:
            if titles[0] == movementNames[0]:
                self._biblio.remove(('OTL', titles[0]))

    '''
    //////////////////////////////
    //
    // HumdrumInput::prepareTimeSigDur -- create a list of the durations of time
    //      signatures in the file, indexed by hum::HumdrumFile line number.  Only
    //      the first spine in the file is considered.
    '''
    def _prepareTimeSignatures(self) -> None:
        top: int | None = None
        bot: int | None = None

        self._timeSigDurationsByLine = [opFrac(-1)] * self.lineCount
        self._timeSignaturesWithLineIdx = []

        starts = self.spineStartListOfType('**kern')
        if not starts:  # None or empty list
            starts = self.spineStartListOfType('**recip')
            if not starts:  # None or empty list
                # no **kern or **recip so give up
                return

        startTok = starts[0]
        if startTok is None:
            return

        curDur: HumNum = opFrac(-1)

        token = startTok.nextToken0  # stay left if there's a split
        while token is not None:
            lineIdx: int = token.lineIndex
            if not token.isTimeSignature:
                self._timeSigDurationsByLine[lineIdx] = curDur
                token = token.nextToken0  # stay left if there's a split
                continue
            top, bot = token.timeSignature
            if top is None or bot is None:
                # token is a timeSig, but it's malformed, so don't use it
                self._timeSigDurationsByLine[lineIdx] = curDur
                token = token.nextToken0  # stay left if there's a split
                continue
            self._timeSignaturesWithLineIdx.append((top, bot, lineIdx))
            curDur = opFrac(Fraction(top, bot))
            curDur = opFrac(curDur * 4)  # convert to duration in quarter notes

            self._timeSigDurationsByLine[lineIdx] = curDur
            token = token.nextToken0  # stay left if there's a split

        self._timeSigDurationsByLine[-1] = curDur

        for i in reversed(range(0, self.lineCount - 1)):
            if self._timeSigDurationsByLine[i] == 0:
                self._timeSigDurationsByLine[i] = self._timeSigDurationsByLine[i + 1]


    '''
    //////////////////////////////
    //
    // HumdrumInput::convertSystemMeasure -- Convert one measure of
    //     a Humdrum score into an MEI measure element.

        Convert one measure of a Humdrum score into a Music21 Measure
    '''
    def _convertSystemMeasure(self, lineIdx: int) -> int:
        # We return the line number of the next measure
        measureKey: tuple[int | None, int] = self._measureKey(lineIdx)
        startIdx, endIdx = measureKey
        if startIdx is None:
            # skip it (but return the endIdx so the client can keep walking measures)
            return endIdx

        if self.ignoreLine[startIdx]:
            # don't convert this measure (!!ignore/!!Xignore toggles)
            return endIdx

        # if self._multirest[startIdx] < 0:
        #     # this is a whole-measure rest, but it is part of a multi-measure rest sequence
        #     return endIdx

        self._currentMeasureLayerTokens = self._scoreLayerTokens[measureKey]
        self._convertMeasureStaves(measureKey)
        self._checkForGlobalRehearsal(measureKey)

        # self._addFTremSlurs() This appears to do nothing in iohumdrum.cpp

        return endIdx

    def _repositionStartIndex(self, startIdx: int) -> int:
        foundDataBefore: bool = False
        for i in reversed(range(0, startIdx + 1)):  # start at startIdx, work back through 0
            if self._lines[i].isData:
                foundDataBefore = True
                break
        if not foundDataBefore:
            startIdx = 0

        if self._lines[startIdx].isEmpty:
            for i in range(startIdx + 1, self.lineCount):
                if self._lines[i].hasSpines:
                    startIdx = i
                    break
                startIdx += 1
        return startIdx

    '''
    //////////////////////////////
    //
    // HumdrumInput::setupSystemMeasure -- prepare a new system measure.
    //   Also checks if the key or time signatures change at the start
    //   of the measures (other than the first measure of a score).

        Since music21 Measures are within a Part (instead of one Measure containing
        a single measures-worth of all Parts), we actually set up "SystemMeasures",
        a list of Measures, one per staff/Part.
    '''
    def _setupSystemMeasures(
        self,
        measureKey: tuple[int | None, int],
        measureOffset: HumNumIn
    ) -> int:
        startLineIdx, endLineIdx = measureKey
        if startLineIdx is None:
            # this method should not be called without a startLineIdx in measureKey
            raise HumdrumInternalError('Invalid measureKey')
        mOffset: HumNum = opFrac(measureOffset)

        measureNumber: int | str = self._getMeasureNumber(startLineIdx)
        if measureNumber == -1:
            measureNumber = 0  # in music21, measureNumber = 0 means undefined

        # section analysis (only used for repeat endings, the ABA stuff is uninteresting
        # notation-wise, and music21 has no way to store it in any case)
        currentSection: str = ''
        sectionLabel: HumdrumToken | None = self._sectionLabels[startLineIdx]
        if sectionLabel is not None:
            currentSection = sectionLabel.text
            if currentSection.startswith('*>'):
                currentSection = currentSection[2:]

        endNum: int = 0
        ending: bool = False
        newSection: bool = False
        if currentSection and currentSection[-1].isdigit():
            withNumStr: str = ''
            noNumStr: str = ''
            if sectionLabel is not None:
                withNumStr = sectionLabel.text
            numberlessLabel: HumdrumToken | None = self._numberlessLabels[startLineIdx]
            if numberlessLabel is not None:
                noNumStr = numberlessLabel.text

            # Humdrum section names are technically free-form.  Repeat endings
            # are marked by a section name that is the current section name
            # with a number at the end. --gregc
            if noNumStr and withNumStr and withNumStr[0:len(noNumStr)] == noNumStr:
                ending = True
            if ending:
                m = re.search(r'(\d+)$', currentSection)
                if m is not None:
                    endNum = int(m.group(1))
                else:
                    # suffix is not a number, so not an ending
                    ending = False
        elif currentSection != self._lastSection:
            newSection = True
            if sectionLabel is not None:
                self._lastSection = currentSection
            else:
                self._lastSection = ''

        if ending and self._endingNum != endNum:
            # create a new ending (one per staff)
            # we'll add the measures to this spanner in the "per staff" loop
            self._currentEndingPerStaff = []
            for i in range(0, self.staffCount):
                rb: m21.spanner.RepeatBracket = m21.spanner.RepeatBracket(number=endNum)
                rb.humdrum_staff_index = i  # type: ignore
                self._currentEndingPerStaff.append(rb)
                self.m21Score.coreInsert(0, rb)
            self.m21Score.coreElementsChanged()
            self._endingNum = endNum
        elif ending:
            # inside a current ending (one per staff), which is already
            # set up, just add to it below in the "per staff" loop
            pass
        elif newSection:
            # a new section has started (which ends the current ending)
            self._currentEndingPerStaff = []
            self._endingNum = 0
        else:
            # outside of an ending
            self._currentEndingPerStaff = []
            self._endingNum = 0

        currentMeasurePerStaff: list[m21.stream.Measure] = []
        for i in range(0, self.staffCount):
            ss: StaffStateVariables = self._staffStates[i]
            measure: m21.stream.Measure = m21.stream.Measure(number=measureNumber)
            currentMeasurePerStaff.append(measure)
            if t.TYPE_CHECKING:
                # By the time we get here, all the m21Parts are set up.
                assert ss.m21Part is not None
            ss.m21Part.coreInsert(mOffset, measure)
            ss.m21Part.coreElementsChanged()

            if ending:
                # assume self._currentEndingPerStaff is fully populated
                self._currentEndingPerStaff[i].addSpannedElements(measure)

            # start coreInserting into measure
            insertedIntoMeasure: bool = False
            if self._lines[startLineIdx].durationFromStart <= 0:
                # first measure... we already have the clef, keysig, and timesig
                # for this measure waiting for us in _staffState[i]
                if ss.firstM21Clef:
                    measure.coreInsert(0, ss.firstM21Clef)
                    insertedIntoMeasure = True
                if ss.firstM21KeySig:
                    measure.coreInsert(0, ss.firstM21KeySig)
                    insertedIntoMeasure = True
                if ss.firstM21TimeSig:
                    measure.coreInsert(0, ss.firstM21TimeSig)
                    insertedIntoMeasure = True

            # we insert page/line breaks at offset 0 in part 0's measure
            if self._m21BreakAtStartOfNextMeasure and i == 0:
                measure.coreInsert(0, self._m21BreakAtStartOfNextMeasure)
                insertedIntoMeasure = True
                self._m21BreakAtStartOfNextMeasure = None

            # if we insertedIntoMeasure at all, we must call coreElementsChanged()
            if insertedIntoMeasure:
                measure.coreElementsChanged()

        self._allMeasuresPerStaff.append(currentMeasurePerStaff)
        measureIndex: int = len(self._allMeasuresPerStaff) - 1
        self._measureIndexFromKey[measureKey] = measureIndex

        if self._lines[startLineIdx].durationFromStart > 0:
            # not first measure, check for keysig, timesig changes
            # Q: what about clef changes?  Might happen in _fillContentsOfLayer,
            # Q: along with notes and rests?
            self._addKeyTimeChangesToSystemMeasures(measureKey)

        # set up self._m21BreakAtStartOfNextMeasure for the next measure
        self._checkForFormalBreak(endLineIdx)

#             LATER: mensural support
#             if self._oclefs or self._omets or self._okeys:
#                 self._storeOriginalClefMensurationKeyApp()

        # TODO: sections (A, B)

        return endLineIdx

    '''
    //////////////////////////////
    //
    // HumdrumInput::setSystemMeasureStyle -- Set the style of the left and/or
    //    right barline for the measure.

        Sets the style of the right barline of the measures in this system measure,
        and (maybe) tells the next system measure's measures what to do with their
        left barline (usually nothing).
    '''
    def _setSystemMeasureStyle(self, measureKey: tuple[int | None, int]) -> None:
        _, endLineIdx = measureKey
        measureIndex: int = self.measureIndexFromKey(measureKey)
        nextMeasureIndex: int | None = None
        if measureIndex + 1 < len(self._allMeasuresPerStaff):
            nextMeasureIndex = measureIndex + 1

        currentMeasurePerStaff: list[m21.stream.Measure] = (
            self._allMeasuresPerStaff[measureIndex]
        )

        line: HumdrumLine = self._lines[endLineIdx]
        firstToken: HumdrumToken | None = line[0]
        if firstToken is None:
            return

        if not firstToken.isBarline:
            # This is the last measure and it ends without a final barline.
            # Put an invisible right barline in every currentMeasurePerPart.
            for m in currentMeasurePerStaff:
                m.rightBarline = m21.bar.Barline('none')
            return

        lastStaffIndex: int = -1
        for endToken in line.tokens():
            if endToken is None:
                # can this even happen?
                continue

            if endToken.track is None:
                # happens in some tests
                continue

            staffIndex: int = self._staffStartsIndexByTrack[endToken.track]
            if staffIndex < 0:
                # not a notational spine for a staff
                continue
            if staffIndex == lastStaffIndex:
                # we already handled this staff/measure
                continue
            lastStaffIndex = staffIndex

            if not endToken.isBarline:
                # shouldn't ever happen because we checked this before looping over endToken
                continue

            endBar: str = endToken.text

            if endBar.startswith('=='):  # final barline (light-heavy)
                currentMeasurePerStaff[staffIndex].rightBarline = m21.bar.Barline('final')
                continue

            endingBarline: m21.bar.Barline = M21Convert.m21BarlineFromHumdrumString(
                endBar, side='right'
            )
            if endingBarline is not None:
                currentMeasurePerStaff[staffIndex].rightBarline = endingBarline

            if nextMeasureIndex is not None:
                if ('!:' in endBar or '|:' in endBar):  # start repeat
                    nextMeasurePerStaff: list[m21.stream.Measure] = (
                        self._allMeasuresPerStaff[nextMeasureIndex]
                    )
                    nextMeasurePerStaff[staffIndex].leftBarline = (
                        M21Convert.m21BarlineFromHumdrumString(endBar, side='left')
                    )

    '''
    //////////////////////////////
    //
    // HumdrumInput::getMeasureNumber -- Return the current barline's measure
    //     number, or return -1 if no measure number.  Returns 0 if a
    //     pickup measure.
        If there is a suffix (e.g. 23b), returns a string instead of an int
    '''
    def _getMeasureNumber(self, startLineIdx: int) -> int | str:
        name: str = ''
        number: int = -1

        if self._lines[startLineIdx].isBarline:
            # barlineNumber returns -1 if no number present
            number = self._lines[startLineIdx].barlineNumber
            # barlineName returns '' if name is just a number with no suffix
            name = self._lines[startLineIdx].barlineName
            if name:
                return name
            return number

        # at the start of the score (most likely).  Search through the first
        # spine for the first barline, provided that it starts before the first
        # data line.
        found: bool = False
        barlineIdx: int = -1
        for i, line in enumerate(self._lines):
            if line.isBarline:
                found = True
                barlineIdx = i
                break

            if line.isData:
                found = False
                barlineIdx = -1
#                 if self.hasPickup:
#                     # set the first implicit measure to 0
#                     return 0
                break

        if found:
            # barlineNumber returns -1 if no number present
            number = self._lines[barlineIdx].barlineNumber
            # barlineName returns '' if name is just a number with no suffix
            name = self._lines[barlineIdx].barlineName
            if name:
                return name
            return number

        return -1

    '''
    /////////////////////////////
    //
    // HumdrumInput::addSystemKeyTimeChange -- Add key or time signature changes
    //    for a measure.  The scoreDef element is inserted before the measure in
    //    which the change occurs.

        For music21, we add any changes to the appropriate systemMeasure (there is
        one Measure per staff/Part). We also do something C++ code does not: we
        handle signature changes mid-Measure, and insert them at the appropriate
        time offset.
    '''
    def _addKeyTimeChangesToSystemMeasures(
        self,
        measureKey: tuple[int | None, int]
    ) -> None:
        startLineIdx, endLineIdx = measureKey
        if startLineIdx is None:
            # this method should not be called without a startLineIdx in measureKey
            raise HumdrumInternalError('Invalid measureKey')

        # Keep track of any key and time signature changes for each staff (token).
        # The token's time offset within the Measure is token.durationFromBarline.
        keyToks: list[HumdrumToken | None] = [None] * self.staffCount
        keySigToks: list[HumdrumToken | None] = [None] * self.staffCount
        timeSigToks: list[HumdrumToken | None] = [None] * self.staffCount
        meterSigToks: list[HumdrumToken | None] = [None] * self.staffCount
        # iTransposeToks: list[HumdrumToken | None] = [None] * self.staffCount

        empty: bool = True
        hasKeySig: bool = False
        hasTimeSig: bool = False
        # hasITranspose: bool = False

        for i in range(startLineIdx, endLineIdx + 1):  # inclusive of end
            line = self._lines[i]
            if not line.isInterpretation:
                continue

            for token in line.tokens():
                staffIndex: int = self._staffStartsIndexByTrack[token.track]
                if staffIndex < 0:
                    # not a notational spine for a staff
                    continue

                if token.isTimeSignature:
                    timeSigToks[staffIndex] = token
                    empty = False
                    hasTimeSig = True
                elif token.isKeySignature:
                    keySigToks[staffIndex] = token
                    empty = False
                    hasKeySig = True
                elif token.isKeyDesignation:
                    keyToks[staffIndex] = token
                    empty = False
# TODO: transposing instrument change (e.g. Bb Clarinet to A Clarinet)
#                 elif token.isInstrumentTranspose:
#                     iTransposeToks[staffIndex] = token
#                     empty = False
#                     hasITranspose = True

                # Meter signature will only be used if immediately following
                # a time signature, so do not set to nonempty by itself.
                if timeSigToks[staffIndex] and token.isMensurationSymbol:
                    meterSigToks[staffIndex] = token

        if empty:
            # No transposition, key or time signature changes.
            return

        if hasTimeSig or hasKeySig:
            currentMeasurePerStaff: list[m21.stream.Measure] = (
                self._allMeasuresPerStaff[self.measureIndexFromKey(measureKey)]
            )
            for measure, timeSigTok, meterSigTok, keySigTok, keyTok in zip(
                    currentMeasurePerStaff, timeSigToks, meterSigToks, keySigToks, keyToks):

                insertedIntoMeasure: bool = False

                if timeSigTok is not None:
                    m21TimeSig = M21Convert.m21TimeSignature(timeSigTok, meterSigTok)
                    if m21TimeSig is not None:
                        m21OffsetInMeasure = timeSigTok.durationFromBarline
                        measure.coreInsert(m21OffsetInMeasure, m21TimeSig)
                        insertedIntoMeasure = True

                if keySigTok is not None:
                    m21KeySig = M21Convert.m21KeySignature(keySigTok, keyTok)
                    if m21KeySig is not None:
                        m21OffsetInMeasure = keySigTok.durationFromBarline
                        measure.coreInsert(m21OffsetInMeasure, m21KeySig)
                        # always track current keysig per staff
                        self._staffStates[staffIndex].currentM21KeySig = m21KeySig
                        insertedIntoMeasure = True

                if insertedIntoMeasure:
                    measure.coreElementsChanged()

        if hasKeySig:
            for i, keySigTok in enumerate(keySigToks):
                if keySigTok is None:
                    continue


    '''
    //////////////////////////////
    //
    // HumdrumInput::storeStaffLayerTokensForMeasure -- Store lists of notation
    //   data by staff and layer.
    '''
    def _generateStaffLayerTokensForMeasure(
        self,
        startLineIdx: int,
        endLineIdx: int
    ) -> list[list[list[HumdrumToken | FakeRestToken]]]:
        output: list[list[list[HumdrumToken | FakeRestToken]]] = []
        for i in range(0, self.staffCount):
            output.append([])

        lastTrack: int = -1
        staffIndex: int = -1
        layerIndex: int = 0
        tokenTrack: int

        # First need to pre-allocate layer information so that clefs can
        # be inserted into partial layers (which otherwise may not have
        # been created before the clef needs to be inserted).
        for i in range(startLineIdx, endLineIdx + 1):
            line = self._lines[i]

            if i > startLineIdx:
                if line.isData and self._lines[i - 1].isData:
                    # spining (layers) cannot change between data lines
                    # so do not bother to check
                    continue

            if not line.hasSpines:
                continue  # no layers to see here

            # check for the maximum size of each spine (check staff
            # for maximum layer count):
            lastTrack = -1
            for token in line.tokens():
                if not token.isStaffDataType:
                    continue

                tokenTrack = token.track
                if tokenTrack != lastTrack:
                    lastTrack = tokenTrack
                    layerIndex = 0
                    continue

                layerIndex += 1
                staffIndex = self._staffStartsIndexByTrack[tokenTrack]
                if len(output[staffIndex]) < layerIndex + 1:
                    output[staffIndex].append([])

        # Now we can do the job:
        for i in range(startLineIdx, endLineIdx + 1):
            line = self._lines[i]

            if not line.hasSpines:
                continue

            lastTrack = -1
            for token in line.tokens():
                tokenTrack = token.track
                if tokenTrack < 1:
                    continue

                staffIndex = self._staffStartsIndexByTrack[tokenTrack]
                if staffIndex < 0:
                    continue

                if tokenTrack != lastTrack:
                    layerIndex = 0
                # elif not token.isPrimaryStrophe:
                #     # Do not increment layer index for secondary strophes
                #     # Also ignore non-primary strophes for now.
                #     continue
                else:
                    layerIndex += 1

                lastTrack = tokenTrack

                if token.isLocalComment and token.isNull:
                    # don't store empty comments as well. (maybe ignore all
                    # comments anyway).
                    continue

                if len(output[staffIndex]) < layerIndex + 1:
                    output[staffIndex].append([])

# music21 doesn't do system-wide measures (they only have measure per part), so all
# of this limitation of what can be represented as a system-wide barline doesn't apply.
# That's apparently an MEI limitation?  If so, the MEI exporter can deal with it.
#                 if token.isBarline and not token.allSameBarlineStyle:
#                     if '-' in token.text:
#                         # do not store partial invisible barlines
#                         continue

                # if there is a time gap between end of previous data token and this one,
                # insert an invisible rest to fill it.
                if token.durationFromStart > 0:
                    prevDataToken: HumdrumToken | None = (
                        self._findLastNonNullDataToken(output[staffIndex][layerIndex])
                    )
                    if prevDataToken is not None:
                        prevDuration: HumNum = prevDataToken.duration
                        # e.g. barlines have duration == -1, use 0 instead
                        prevDuration = max(prevDuration, opFrac(0))
                        prevEndTime: HumNum = opFrac(
                            prevDataToken.durationFromStart + prevDuration
                        )
                        gapDuration: HumNum = opFrac(token.durationFromStart - prevEndTime)
                        if gapDuration > 0:
                            fakeRestDurationFromBarline: HumNum = opFrac(
                                token.durationFromBarline - gapDuration
                            )
                            fakeRests: list[FakeRestToken] = self.makeFakeRestTokens(
                                gapDuration, fakeRestDurationFromBarline
                            )
                            output[staffIndex][layerIndex] += fakeRests

                output[staffIndex][layerIndex].append(token)

#                 if layerIndex == 0 and token.isClef:
#                     layerCount = self._getCurrentLayerCount(token)
#                     # Duplicate clef in all layers (needed for cases when
#                     # a secondary layer ends before the end of a measure.
#                     for k in range(layerCount, len(output[staffIndex])):
#                         output[staffIndex][k].append(token)

        return output

    @staticmethod
    def makeFakeRestTokens(
        gapDuration: HumNumIn,
        durationFromBarline: HumNumIn
    ) -> list[FakeRestToken]:
        output: list[FakeRestToken] = []
        durFromBarline: HumNum = opFrac(durationFromBarline)
        restDurations: list[HumNum] = (
            M21Utilities.getPowerOfTwoQuarterLengthsWithDotsAddingTo(gapDuration)
        )
        for restDuration in restDurations:
            output.append(FakeRestToken(restDuration, durFromBarline))
            durFromBarline = opFrac(durFromBarline + restDuration)

        return output

    @staticmethod
    def _findLastNonNullDataToken(
        tokenList: list[HumdrumToken | FakeRestToken]
    ) -> HumdrumToken | None:
        if not tokenList:
            return None

        for token in reversed(tokenList):
            if isinstance(token, FakeRestToken):
                continue
            if token.isNonNullData:
                return token

        return None

    '''
    //////////////////////////////
    //
    // HumdrumInput::getCurrentLayerCount -- Given a token in layer 1
    //    of a staff, count how many active layers there are at the
    //    same time.
    '''
    @staticmethod
    def _getCurrentLayerCount(token: HumdrumToken) -> int:
        output: int = 1
        ttrack: int | None = token.track

        if ttrack is None:
            return output

        currTok: HumdrumToken | None = token.nextFieldToken
        while currTok is not None:
            if currTok.track != ttrack:
                break
            output += 1
            currTok = currTok.nextFieldToken

        return output

    '''
    /////////////////////////////
    //
    // HumdrumInput::printMeasureTokens -- For debugging.
    '''
    def _printCurrentMeasureLayerTokens(self) -> None:
        print('self._currentMeasureLayerTokens:', file=sys.stderr)
        for i, staff in enumerate(self._currentMeasureLayerTokens):
            print(f'STAFF {i + 1}\t', end='', flush=True, file=sys.stderr)
            for j, layer in enumerate(staff):
                print(f'LAYER {j + 1}:\t', end='', flush=True, file=sys.stderr)
                for token in layer:
                    if token.isFakeRest:
                        print(' FAKE REST', end='', flush=True, file=sys.stderr)
                    else:
                        if t.TYPE_CHECKING:
                            # it's not a fake rest
                            assert isinstance(token, HumdrumToken)
                        print(' ', token.text, end='', flush=True, file=sys.stderr)
                print('', flush=True, file=sys.stderr)

    '''
    //////////////////////////////
    //
    // HumdrumInput::convertMeasureStaves -- fill in a measure with the
    //    individual staff elements for each part.

        We actually create and fill in a Measure per staff and append to each Part
        (that's how music21 likes it). --gregc
    '''
    def _convertMeasureStaves(self, measureKey: tuple[int | None, int]) -> None:
        layerCounts: list[int] = self.staffLayerCounts

        # TODO: Figured Bass
#         if self._hasFiguredBassSpine:
#             self._addFiguredBassForMeasureStaves(measureKey)

        # Tempo changes via !!!OMD
        self._checkForOmd(measureKey)

        for i, startTok in enumerate(self._staffStarts):
            if t.TYPE_CHECKING:
                # assume that at least all the _staffStarts have track numbers
                assert startTok.track is not None
            self._convertMeasureStaff(startTok.track, measureKey, layerCounts[i])

        if self._hasHarmonySpine:
            self._addHarmFloatsForMeasure(measureKey)
        # TODO: fingering, string numbers
#         if self._hasFingeringSpine:
#             self._addFingeringsForMeasure(measureKey)
#         if self._hasStringSpine:
#             self._addStringNumbersForMeasure(measureKey)


    '''
    //////////////////////////////
    //
    // HumdrumInput::addHarmFloatsForMeasure --  Insert <harm> type data.
    //   Exclusive interpretations processed by this function:
    //     **mxhm      == pitch-class based chord labels
    //     **harte     == Harte-style regularized chord labels
    '''
    def _addHarmFloatsForMeasure(self, measureKey: tuple[int | None, int]):
        startLineIdx, endLineIdx = measureKey
        if startLineIdx is None:
            # this method should not be called without a startLineIdx in measureKey
            raise HumdrumInternalError('Invalid measureKey')

        # Search the measure for mxhm data to process
        for i in range(startLineIdx, endLineIdx):
            line: HumdrumLine = self._lines[i]
            if not line.isData:
                continue

            active: bool = True
            track: int = 0

            for j, token in enumerate(line.tokens()):
                if token.isMens:
                    active = False
                    continue

                if token.isKern:
                    active = True
                    track = token.track
                    continue

                if not active:
                    continue
                if token.isNull:
                    continue

                dataType: str = str(token.dataType)
                if not dataType:
                    continue

                if self._chosenHarmonyDataType != dataType:
                    continue

                if token.getValueBool('auto', 'hidden'):
                    # Don't process invisible harmony data
                    continue

                if 'yy' in token.text:
                    # 'yy' means hidden, too
                    continue

                harmonyTexts: list[str] = [token.text]
                if dataType == '**harte':
                    # we support multiple space-delimited harmonies per token
                    harmonyTexts = token.text.split(' ')
                hasMultipleHarmonies: bool = len(harmonyTexts) > 1

                n: int | None = None
                if hasMultipleHarmonies:
                    n = 0  # will be incremented before first harmony (!LO:n= is 1-based)

                for htext in harmonyTexts:
                    chordSym: m21.harmony.ChordSymbol | None = (
                        M21Convert.getM21ChordSymFromHarmonyText(htext, dataType)
                    )
                    if chordSym is None:
                        continue

                    if hasMultipleHarmonies:
                        if t.TYPE_CHECKING:
                            assert n is not None
                        n += 1

                    nStr: str = ''
                    if n is not None:
                        nStr = str(n)

                    kindStr: str = ''
                    fullText: str = self._getLayoutParameterWithDefaults(
                        token, 'H', 't', '', '', n=nStr
                    )
                    if fullText:
                        chordSym.c21_full_text = fullText  # type: ignore
                    else:
                        kindStr = self._getLayoutParameterWithDefaults(
                            token, 'H', 'kt', '', '', n=nStr
                        )
                        if kindStr:
                            chordSym.chordKindStr = kindStr

                    staffIndex: int = self._staffStartsIndexByTrack[track]
                    csOffset: OffsetQL = token.durationFromBarline
                    currentMeasurePerStaff: list[m21.stream.Measure] = (
                        self._allMeasuresPerStaff[self.measureIndexFromKey(measureKey)]
                    )
                    currentMeasurePerStaff[staffIndex].coreInsert(csOffset, chordSym)
                    currentMeasurePerStaff[staffIndex].coreElementsChanged()

    '''
    //////////////////////////////
    //
    // HumdrumInput::convertMeasureStaff -- print a particular staff in a
    //     particular measure.

        Convert a particular Measure in a particular staff/Part.
    '''
    def _convertMeasureStaff(
        self,
        track: int,
        measureKey: tuple[int | None, int],
        layerCount: int
    ) -> None:
        # layers go forward, even though staves/parts go backward.  We might want an
        # option (for import here, and export elsewhere) to allow the user to specify
        # their layer order preference.  (There are tools to flip them around.)

        # for layerIndex in range(layerCount-1, -1, -1):
        for layerIndex in range(0, layerCount):
            self._convertStaffLayer(track, measureKey, layerIndex)

        # converter21's Humdrum exporter adds invisible rest voices to position
        # things like Dynamics/etc at an appropriate score offset.  If we can
        # place those Dynamics/etc in the enclosing Measure (at the right offset),
        # we can remove the voice.
        staffIndex: int = self._staffStartsIndexByTrack[track]
        if staffIndex < 0:
            # not a kern/mens spine
            return

        measureIndex: int = self.measureIndexFromKey(measureKey)
        measure: m21.stream.Measure = (
            self._allMeasuresPerStaff[measureIndex][staffIndex]
        )

        # Don't remove the only voice in the measure
        if len(tuple(measure.voices)) <= 1:
            return

        voicesToRemove: list[m21.stream.Voice] = []

        for voice in measure.voices:
            if self._isInvisibleRestVoice(voice):
                voicesToRemove.append(voice)

        # Removal loop is separate, so we don't delete from the measure while iterating
        # over the measure.
        for voice in voicesToRemove:
            self._removeVoiceFromMeasure(measure, voice)

        # Q: what about checkClefBufferForSameAs... sounds like it is (mostly?) undoing
        # Q: the extra clef copies we added in _generateStaffLayerTokensForMeasure()

    '''
    //////////////////////////////
    //
    // HumdrumInput::convertStaffLayer -- Prepare a layer element in the current
    //   staff and then fill it with data.
    '''
    def _convertStaffLayer(
        self,
        track: int,
        measureKey: tuple[int | None, int],
        layerIndex: int
    ) -> None:
        staffIndex: int = self._staffStartsIndexByTrack[track]
        if staffIndex < 0:
            # not a kern/mens spine
            return

        layerData: list[HumdrumToken | FakeRestToken] = (
            self._currentMeasureLayerTokens[staffIndex][layerIndex]
        )
        if not layerData:  # empty layer?!
            return

        self._fillContentsOfLayer(track, measureKey, layerIndex)

    '''
    //////////////////////////////
    //
    // HumdrumInput::printGroupInfo --
    '''
    @staticmethod
    def _printGroupInfo(tgs: list[HumdrumBeamAndTuplet | None]) -> None:
        for tg in tgs:
            if t.TYPE_CHECKING:
                # tgs has been filled in completely
                assert isinstance(tg, HumdrumBeamAndTuplet)
            token = tg.token
            if token is None:
                print('None', end='\t', file=sys.stderr)
            elif isinstance(token, FakeRestToken):
                print('FakeRest', end='\t', file=sys.stderr)
            else:
                print(token.text, end='\t', file=sys.stderr)
                if token.text and len(token.text) < 8:
                    print('', end='\t', file=sys.stderr)
            print(f'BS:{tg.beamStart}', end='\t', file=sys.stderr)
            print(f'BE:{tg.beamEnd}', end='\t', file=sys.stderr)
            print(f'GS:{tg.gbeamStart}', end='\t', file=sys.stderr)
            print(f'GE:{tg.gbeamEnd}', end='\t', file=sys.stderr)
            print(f'TS:{tg.tupletStart}', end='\t', file=sys.stderr)
            print(f'TE:{tg.tupletEnd}', end='\t', file=sys.stderr)
            print(f'TG:{tg.group}', end='\t', file=sys.stderr)
            print(f'TA/TN:{tg.numNotesActual}/{tg.numNotesNormal}', end='\t', file=sys.stderr)
            print(f'TF:{tg.forceStartStop}', file=sys.stderr)

    def getMeasureForStaff(
        self,
        measureIndex: int,
        staffIndex: int
    ) -> m21.stream.Measure:
        if measureIndex not in range(0, len(self._allMeasuresPerStaff)):
            raise HumdrumInternalError('measureIndex out of range')

        currentMeasurePerStaff: list[m21.stream.Measure] = (
            self._allMeasuresPerStaff[measureIndex]
        )

        if staffIndex not in range(0, len(currentMeasurePerStaff)):
            raise HumdrumInternalError('staffIndex out of range')

        return currentMeasurePerStaff[staffIndex]

    '''
    //////////////////////////////
    //
    // HumdrumInput::fillContentsOfLayer -- Fill the layer with musical data.
    '''
    def _fillContentsOfLayer(
        self,
        track: int,
        measureKey: tuple[int | None, int],
        layerIndex: int
    ) -> None:
        staffIndex: int = self._staffStartsIndexByTrack[track]
        if staffIndex < 0:
            # not a kern/mens spine
            return

        layerData: list[HumdrumToken | FakeRestToken] = (
            self._currentMeasureLayerTokens[staffIndex][layerIndex]
        )
        if not layerData:  # empty layer?!
            return

        ss: StaffStateVariables = self._staffStates[staffIndex]
        measureIndex: int = self.measureIndexFromKey(measureKey)

        # check for ottava start at or before start of measure
        self._prepareInitialOttavas(layerData[0], staffIndex, measureIndex)

        # cadenzas can have measure entirely made up of grace notes...
        # don't bail on measureDuration == 0!

        # beams and tuplets
        tgs: list[HumdrumBeamAndTuplet | None] = (
            ss.tgs[measureKey][layerIndex]  # computed by first pass
        )
        #        self._printGroupInfo(tgs)  # for debug only

        voice: m21.stream.Voice = m21.stream.Voice()
        voiceOffsetInMeasure: HumNum = layerData[0].durationFromBarline
        if layerData[0].isBarline:
            # durationFromBarline returns duration of previous bar in this case
            voiceOffsetInMeasure = opFrac(0)
        if voiceOffsetInMeasure > 0:
            # Start the voice at the beginning of the measure, by inserting
            # a fake rest of appropriate duration at the beginning of the voice,
            # and setting voiceOffsetInMeasure to 0.  We do this because there
            # is a lot of software out there (including music21's musicxml writer)
            # that doesn't handle voices that start in the middle of a measure
            # very well.
            fakeRests: list[FakeRestToken] = self.makeFakeRestTokens(
                voiceOffsetInMeasure, 0
            )

            for rest in reversed(fakeRests):
                layerData.insert(0, rest)
                tgs.insert(0, None)
            voiceOffsetInMeasure = opFrac(0)

        assert len(tgs) == len(layerData)

        currentMeasurePerStaff: list[m21.stream.Measure] = (
            self._allMeasuresPerStaff[measureIndex]
        )
        currentMeasurePerStaff[staffIndex].coreInsert(voiceOffsetInMeasure, voice)
        currentMeasurePerStaff[staffIndex].coreElementsChanged()

# TODO: merge new iohumdrum.cpp changes --gregc 01July2021
#     // Check for cases where there are only null interpretations in the measure
#     // and insert a space in the measure (related to tied notes across barlines).
#     if (layerOnlyContainsNullStuff(layerdata)) {
#         fillEmptyLayer(staffindex, layerindex, elements, pointers);
#         return true;
#     }

        # Note: no special case for whole measure rests.
        # music21 can detect and deal with these without our help.

        groupState: BeamAndTupletGroupState = BeamAndTupletGroupState()

#        lastDataTok: HumdrumToken = None # ignore for now, it's for sameas clef analysis
        inTremolo: bool = False
        insertedIntoVoice: bool = False
        for tokenIdx, layerTok in enumerate(layerData):
            # Check for fake inserted token representing an invisible rest (due to
            # time gap between layer tokens).
            if isinstance(layerTok, FakeRestToken):
                if self._processFakeRestLayerToken(
                        measureIndex, voice, voiceOffsetInMeasure, layerTok):
                    insertedIntoVoice = True
                continue

            # After this point, we can assume that layerTok is a real HumdrumToken
            if t.TYPE_CHECKING:
                assert isinstance(layerTok, HumdrumToken)

#             if layerTok.isData:
#                 lastDataTok = layerTok

            if layerTok.isNullData:
                # print any global text directions (or dynamics) attached to the null token
                # and then skip to next token.
                if self._processDynamics(
                        measureIndex, voice, voiceOffsetInMeasure, layerTok, staffIndex):
                    insertedIntoVoice = True
                if self._processDirections(
                        measureIndex, voice, voiceOffsetInMeasure, layerTok, staffIndex):
                    insertedIntoVoice = True
                continue

            if layerTok.isInterpretation:
                if self._processInterpretationLayerToken(
                        measureIndex, voice, voiceOffsetInMeasure,
                        layerData, tokenIdx, layerIndex, staffIndex):
                    insertedIntoVoice = True
                continue

            if layerTok.isBarline:
                # should be already handled in self._setSystemMeasureStyle
                continue

            if not layerTok.isData:
                continue

            # layerTok.isData...

#             if layerTok.isMens:
#                 if self._convertMensuralToken(...):
#                     insertedIntoVoice = True
#                 continue

            # iohumdrum.cpp does tgs processing in a different order,
            # because it is generating MEI.  We are generating music21,
            # so instead of handleGroupStarts before processing the note,
            # and then handleGroupEnds after, we have to do all group
            # handling after processing the note, in _handleGroupState.
            # This means we had to pull out the _checkForTremolo call, since
            # that definitely has to happen before processing the note (it
            # may completely replace a beamed group of notes with a tremolo).
            # (Note that we subsequently pulled checking for tremolos out to
            # a full score scan before any conversions, to handle the fact that
            # conversion of dynamic wedges to music21 requires that all tremolos
            # be marked first, so we don't use a suppressed note as the start/end
            # of a crescendo/diminuendo).
            # It also means that we have to call _handleGroupState before
            # any continue below, since they won't reach the call at bottom
            # of the loop.
            if ss.tremolo:
                inTremolo = layerTok.getValueBool('auto', 'inTremolo')  # set by first pass
            else:
                inTremolo = False

            if layerTok.getValueBool('auto', 'tremoloBeam'):  # set by first pass
                if 'J' in layerTok.text:
                    # handle the ending note of a beamed group
                    # of tremolos (reach back to the first note in this
                    # last tremolo in the beamed group, to add the 'stop' beam).
                    groupState = self._handleGroupState(
                        groupState, tgs, layerData, tokenIdx,
                        staffIndex, tremoloBeam=True, tremolo=inTremolo
                    )
                    continue

            if layerTok.getValueBool('auto', 'suppress'):  # set by _checkForTremolo (first pass)
                # This element is not supposed to be printed,
                # probably due to being in a tremolo.
                # But there are some things we have to do anyway...
                if self._processSuppressedLayerToken(
                        measureIndex, voice, voiceOffsetInMeasure, layerTok, staffIndex):
                    insertedIntoVoice = True
                groupState = self._handleGroupState(
                    groupState, tgs, layerData, tokenIdx, staffIndex, tremolo=inTremolo
                )
                continue

            # conversion of **kern data to music21

            # The order of these checks is important, because the checks assume things.
            # isChord looks for spaces, isRest looks for 'r', isNote looks for any 'a-gA-g',
            # so if you call isNote first, chords will look like notes, and positioned rests
            # will look like notes.
            if layerTok.isChord:
                if self._processChordLayerToken(
                        measureIndex, voice, voiceOffsetInMeasure,
                        layerData, tokenIdx, staffIndex, layerIndex):
                    insertedIntoVoice = True
            elif layerTok.isRest:
                if self._processRestLayerToken(
                        measureIndex, voice, voiceOffsetInMeasure, layerTok, staffIndex):
                    insertedIntoVoice = True
            elif layerTok.isNote or layerTok.isUnpitched:
                # unpitched notes are handled the same as pitched notes here
                if self._processNoteLayerToken(
                        measureIndex, voice, voiceOffsetInMeasure,
                        layerData, tokenIdx, staffIndex, layerIndex):
                    insertedIntoVoice = True
            else:
                # this is probably a **recip value without note or rest information
                # so print it as a space (invisible rest).
                if self._processOtherLayerToken(
                        measureIndex, voice, voiceOffsetInMeasure, layerTok, staffIndex):
                    insertedIntoVoice = True

            groupState = self._handleGroupState(
                groupState, tgs, layerData, tokenIdx, staffIndex, tremolo=inTremolo
            )

        # end loop over layer tokens

        if self._processBarlinesInLayerData(
                measureIndex, voice, voiceOffsetInMeasure, track, layerIndex):
            insertedIntoVoice = True

        if insertedIntoVoice:
            voice.coreElementsChanged()

        # Some of those things that were insertedIntoVoice might
        # have actually been insertedIntoMeasure.
        currentMeasurePerStaff[staffIndex].coreElementsChanged()

    @staticmethod
    def _isInvisibleRestVoice(voice: m21.stream.Voice) -> bool:
        for element in voice:
            if isinstance(
                element,
                (
                    m21.dynamics.Dynamic,
                    m21.expressions.TextExpression,
                    m21.tempo.TempoIndication,
                    m21.spanner.SpannerAnchor,
                    m21.bar.Barline
                )
            ):
                continue
            if not isinstance(element, m21.note.Rest):
                return False
            if not element.hasStyleInformation:
                return False
            if not element.style.hideObjectOnPrint:
                return False
        return True

    @staticmethod
    def _removeVoiceFromMeasure(measure: m21.stream.Measure, voice: m21.stream.Voice):
        for element in voice:
            offsetInMeasure: HumNum

            if isinstance(
                element,
                (
                    m21.dynamics.Dynamic,
                    m21.expressions.TextExpression,
                    m21.tempo.TempoIndication,
                    m21.spanner.SpannerAnchor
                )
            ):
                offsetInMeasure = element.getOffsetInHierarchy(measure)
                measure.insert(offsetInMeasure, element)
                continue

            spanners: list[m21.spanner.Spanner] = list(element.getSpannerSites())
            if spanners:
                # must be an invisible rest being used as a SpannerAnchor.
                # Make a SpannerAnchor to replace it (and insert into measure).
                # Replace all spanner references to element with references to
                # the new anchor.
                anchor = m21.spanner.SpannerAnchor()
                for spanner in spanners:
                    spanner.replaceSpannedElement(element, anchor)
                offsetInMeasure = element.getOffsetInHierarchy(measure)
                measure.insert(offsetInMeasure, anchor)

        measure.remove(voice)


    '''
        _processInterpretationLayerToken
            returns whether or not anything was inserted into the voice
    '''
    def _processInterpretationLayerToken(
        self,
        measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int,
        layerIndex: int,
        staffIndex: int
    ) -> bool:
        vOffsetInMeasure: HumNum = opFrac(voiceOffsetInMeasure)
        ss: StaffStateVariables = self._staffStates[staffIndex]
        layerTok: HumdrumToken | FakeRestToken = layerData[tokenIdx]
        if layerTok.isFakeRest:
            return False

        if t.TYPE_CHECKING:
            # We know because layerTok.isFakeRest == False
            assert isinstance(layerTok, HumdrumToken)

        insertedIntoVoice: bool = False

        if ss.hasLyrics:
            self._checkForVerseLabels(layerTok)

        if not layerTok.isNull and not layerTok.isManipulator:
            # non-null, non-manip interp tokens can have linked params that are directions
            if self._processDirections(
                    measureIndex, voice, vOffsetInMeasure, layerTok, staffIndex):
                insertedIntoVoice = True

        self._handleOttavaMark(measureIndex, layerTok, staffIndex)
        # self._handleLigature(layerTok) # just for **mens
        # self._handleColoration(layerTok) # just for **mens
        self._handleTempoChange(measureIndex, layerTok, staffIndex)
        if self._handlePedalMark(measureIndex, voice, vOffsetInMeasure, layerTok):
            insertedIntoVoice = True
        self._handleStaffStateVariables(measureIndex, layerTok, layerIndex, staffIndex)
        self._handleStaffDynamicsStateVariables(measureIndex, layerTok, staffIndex)
        if self._handleCustos(measureIndex, voice, vOffsetInMeasure, layerTok):
            insertedIntoVoice = True
        if self._handleRepInterp(measureIndex, voice, vOffsetInMeasure, layerTok):
            insertedIntoVoice = True
        self._handleColorInterp(measureIndex, layerTok)
        if self._handleClefChange(
            measureIndex, voice, vOffsetInMeasure, layerData, tokenIdx, staffIndex
        ):
            insertedIntoVoice = True
#         if self._handleTimeSigChange(
#                   measureIndex, voice, vOffsetInMeasure, layerTok, staffIndex):
#             insertedIntoVoice = True

        return insertedIntoVoice

    def _prepareInitialOttavas(
        self,
        token: HumdrumToken | FakeRestToken,
        staffIndex: int,
        measureIndex: int
    ) -> None:
        if token is None:
            return

        if token.isFakeRest:
            return

        if t.TYPE_CHECKING:
            assert isinstance(token, HumdrumToken)

        if token.durationFromStart > 0:
            # not "initial"
            return

        if token.subTrack > 1:
            # only check for initial ottavas in the first layer
            return

        tok: HumdrumToken | None = token.previousToken0
        while tok is not None:
            if not tok.isInterpretation:
                tok = tok.previousToken0
                continue

            if self._handleOttavaMark(measureIndex, tok, staffIndex):
                break

            tok = tok.previousToken0

    def _handleOttavaMark(
        self,
        measureIndex: int,
        token: HumdrumToken | FakeRestToken,
        staffIndex: int
    ) -> bool:
        ss: StaffStateVariables
        measure: m21.stream.Measure

        if token.isFakeRest:
            return False
        if t.TYPE_CHECKING:
            assert isinstance(token, HumdrumToken)

        startNote: m21.note.GeneralNote | None = None
        ottavaText = self.getUnhandledOttavaMarkInStaff(token)
        if ottavaText == '*8va':
            # turn on "up one octave" ottava
            ss = self._staffStates[staffIndex]
            # create it (if it isn't already there; might be in a different voice in the staff)
            if ss.currentOttava1Up is None:
                ss.currentOttava1Up = m21.spanner.Ottava(type='8va', transposing=False)
                ss.currentOttava1Up.humdrum_staff_index = staffIndex  # type: ignore
                ss.currentOttava1Up.humdrum_start_measure_index = measureIndex  # type: ignore
                ss.currentOttava1Up.humdrum_start_duration_from_barline = (  # type: ignore
                    token.durationFromBarline
                )
                # put it in the measure
                measure = self._allMeasuresPerStaff[measureIndex][staffIndex]
                measure.insert(0, ss.currentOttava1Up)

                # work around other voices being "hidden from ottava" due to manipulators
                startNote = self.getStartNoteForOttava(token)
                if startNote is not None:
                    ss.currentOttava1Up.addSpannedElements(startNote)

            return True

        if ottavaText == '*8ba':
            # turn on "down one octave" ottava
            ss = self._staffStates[staffIndex]
            # create it (if it isn't already there; might be in a different voice in the staff)
            if ss.currentOttava1Down is None:
                ss.currentOttava1Down = m21.spanner.Ottava(type='8vb', transposing=False)
                ss.currentOttava1Down.humdrum_staff_index = staffIndex  # type: ignore
                ss.currentOttava1Down.humdrum_start_measure_index = measureIndex  # type: ignore
                ss.currentOttava1Down.humdrum_start_duration_from_barline = (  # type: ignore
                    token.durationFromBarline
                )
                # put it in the measure
                measure = self._allMeasuresPerStaff[measureIndex][staffIndex]
                measure.insert(0, ss.currentOttava1Down)

                # work around other voices being "hidden from ottava" due to manipulators
                startNote = self.getStartNoteForOttava(token)
                if startNote is not None:
                    ss.currentOttava1Down.addSpannedElements(startNote)

            return True

        if ottavaText == '*15ma':
            # turn on "up two octaves" ottava
            ss = self._staffStates[staffIndex]
            # create it (if it isn't already there; might be in a different voice in the staff)
            if ss.currentOttava2Up is None:
                ss.currentOttava2Up = m21.spanner.Ottava(type='15ma', transposing=False)
                ss.currentOttava2Up.humdrum_staff_index = staffIndex  # type: ignore
                ss.currentOttava2Up.humdrum_start_measure_index = measureIndex  # type: ignore
                ss.currentOttava2Up.humdrum_start_duration_from_barline = (  # type: ignore
                    token.durationFromBarline
                )
                # put it in the measure
                measure = self._allMeasuresPerStaff[measureIndex][staffIndex]
                measure.insert(0, ss.currentOttava2Up)

                # work around other voices being "hidden from ottava" due to manipulators
                startNote = self.getStartNoteForOttava(token)
                if startNote is not None:
                    ss.currentOttava2Up.addSpannedElements(startNote)

            return True

        if ottavaText == '*15ba':
            # turn on "down two octaves" ottava
            ss = self._staffStates[staffIndex]
            # create it (if it isn't already there; might be in a different voice in the staff)
            if ss.currentOttava2Down is None:
                ss.currentOttava2Down = m21.spanner.Ottava(type='15mb', transposing=False)
                ss.currentOttava2Down.humdrum_staff_index = staffIndex  # type: ignore
                ss.currentOttava2Down.humdrum_start_measure_index = measureIndex  # type: ignore
                ss.currentOttava2Down.humdrum_start_duration_from_barline = (  # type: ignore
                    token.durationFromBarline
                )
                # put it in the measure
                measure = self._allMeasuresPerStaff[measureIndex][staffIndex]
                measure.insert(0, ss.currentOttava2Down)

                # work around other voices being "hidden from ottava" due to manipulators
                startNote = self.getStartNoteForOttava(token)
                if startNote is not None:
                    ss.currentOttava2Down.addSpannedElements(startNote)

            return True

        endNote: m21.note.GeneralNote | None = None
        if ottavaText == '*X8va':
            ss = self._staffStates[staffIndex]
            if ss.currentOttava1Up is None:
                # unexpected ottava stop
                return True

            if self._isLastEndOttavaLikeThisInStaff(token, ottavaText):
                # get "last chance" end token and turn off "up one octave" ottava
                endNote = self.getEndNoteForOttava(token)
                if endNote is not None:
                    ss.currentOttava1Up.addSpannedElements(endNote)
                ss.currentOttava1Up = None
            elif not hasattr(ss.currentOttava1Up, 'humdrum_end_measure_index'):
                ss.currentOttava1Up.humdrum_end_measure_index = measureIndex  # type: ignore
                ss.currentOttava1Up.humdrum_end_duration_from_barline = (  # type: ignore
                    token.durationFromBarline
                )
            return True

        if ottavaText == '*X8ba':
            ss = self._staffStates[staffIndex]
            if ss.currentOttava1Down is None:
                # unexpected ottava stop
                return True

            if self._isLastEndOttavaLikeThisInStaff(token, ottavaText):
                # get "last chance" end token and turn off "down one octave" ottava
                endNote = self.getEndNoteForOttava(token)
                if endNote is not None:
                    ss.currentOttava1Down.addSpannedElements(endNote)
                ss.currentOttava1Down = None
            elif not hasattr(ss.currentOttava1Down, 'humdrum_end_measure_index'):
                ss.currentOttava1Down.humdrum_end_measure_index = measureIndex  # type: ignore
                ss.currentOttava1Down.humdrum_end_duration_from_barline = (  # type: ignore
                    token.durationFromBarline
                )
            return True

        if ottavaText == '*X15ma':
            ss = self._staffStates[staffIndex]
            if ss.currentOttava2Up is None:
                # unexpected ottava stop
                return True

            if self._isLastEndOttavaLikeThisInStaff(token, ottavaText):
                # get "last chance" end token and turn off "up two octaves" ottava
                endNote = self.getEndNoteForOttava(token)
                if endNote is not None:
                    ss.currentOttava2Up.addSpannedElements(endNote)
                ss.currentOttava2Up = None
            elif not hasattr(ss.currentOttava2Up, 'humdrum_end_measure_index'):
                ss.currentOttava2Up.humdrum_end_measure_index = measureIndex  # type: ignore
                ss.currentOttava2Up.humdrum_end_duration_from_barline = (  # type: ignore
                    token.durationFromBarline
                )
            return True

        if ottavaText == '*X15ba':
            ss = self._staffStates[staffIndex]
            if ss.currentOttava2Down is None:
                # unexpected ottava stop
                return True

            if self._isLastEndOttavaLikeThisInStaff(token, ottavaText):
                # get "last chance" end token and turn off "down two octaves" ottava
                endNote = self.getEndNoteForOttava(token)
                if endNote is not None:
                    ss.currentOttava2Down.addSpannedElements(endNote)
                ss.currentOttava2Down = None
            elif not hasattr(ss.currentOttava2Down, 'humdrum_end_measure_index'):
                ss.currentOttava2Down.humdrum_end_measure_index = measureIndex  # type: ignore
                ss.currentOttava2Down.humdrum_end_duration_from_barline = (  # type: ignore
                    token.durationFromBarline
                )
            return True

        return False

    def getStartNoteForOttava(self, token: HumdrumToken) -> m21.note.GeneralNote | None:
        startTok: HumdrumToken | None = self.getStartNoteTokenForOttava(token)
        if startTok is None:
            return None

        startNote: m21.note.GeneralNote = self._getGeneralNoteOrPlaceHolder(startTok)
        return startNote

    @staticmethod
    def getStartNoteTokenForOttava(token: HumdrumToken) -> HumdrumToken | None:
        tok: HumdrumToken | None = token.nextToken0
        while tok is not None and not tok.isData:
            tok = tok.nextToken0

        if tok is None:
            # couldn't find a next data line
            return None

        track: int | None = tok.track
        ttrack: int | None = track
        notes: list[HumdrumToken] = []
        timestamps: list[HumNum] = []

        while ttrack == track:
            xtok: HumdrumToken = tok
            if xtok.isNull:
                tok = tok.nextFieldToken
                if tok is None:
                    break
                ttrack = tok.track
                continue

            timestamp: HumNum = xtok.durationFromStart
            notes.append(xtok)
            timestamps.append(timestamp)

            tok = tok.nextFieldToken
            if tok is None:
                break
            ttrack = tok.track

        if not notes:
            return None

        bestIndex: int = 0
        for i in range(1, len(notes)):
            if timestamps[i] < timestamps[bestIndex]:
                bestIndex = i

        return notes[bestIndex]

    def getEndNoteForOttava(self, token: HumdrumToken) -> m21.note.GeneralNote | None:
        endTok: HumdrumToken | None = self.getEndNoteTokenForOttava(token)
        if endTok is None:
            return None

        endNote: m21.note.GeneralNote = self._getGeneralNoteOrPlaceHolder(endTok)
        return endNote

    @staticmethod
    def getEndNoteTokenForOttava(token: HumdrumToken) -> HumdrumToken | None:
        tok: HumdrumToken | None = token.previousToken0
        while tok is not None and not tok.isData:
            tok = tok.previousToken0

        if tok is None:
            # couldn't find a previous data line
            return None

        track: int | None = tok.track
        ttrack: int | None = track
        notes: list[HumdrumToken] = []
        timestamps: list[HumNum] = []

        while ttrack == track:
            xtok: HumdrumToken = tok
            if xtok.isNull:
                xtok = xtok.nullResolution
            if xtok is None:
                tok = tok.nextFieldToken
                if tok is None:
                    break
                ttrack = tok.track
                continue

            timestamp: HumNum = xtok.durationFromStart
            notes.append(xtok)
            timestamps.append(timestamp)

            tok = tok.nextFieldToken
            if tok is None:
                break
            ttrack = tok.track

        if not notes:
            return None

        bestIndex: int = 0
        for i in range(1, len(notes)):
            if timestamps[i] > timestamps[bestIndex]:
                bestIndex = i

        return notes[bestIndex]

    def getUnhandledOttavaMarkInStaff(self, token: HumdrumToken) -> str:
        if token.text in ('*8va', '*X8va', '*8ba', '*X8ba', '*15ma', '*X15ma', '*15ba', '*X15ba'):
            return token.text

        # token might be '*', so we need to look at the rest of the voices in the staff
        # (fields in the track).
        ourTrack: int | None = token.track
        tok: HumdrumToken | None = token.nextFieldToken
        if tok is None:
            # no more tokens on line (and no such unhandled ottava found)
            return ''

        ttrack: int | None = tok.track
        while ttrack == ourTrack:
            if tok.text in ('*8va', '*X8va', '*8ba', '*X8ba', '*15ma', '*X15ma', '*15ba', '*X15ba'):
                # found an unhandled ottava mark
                return tok.text

            tok = tok.nextFieldToken
            if tok is None:
                # no more tokens on line (and no unhandled ottava mark found)
                return ''
            ttrack = tok.track

        # no more tokens in other voices in our track/staff (and no unhandled ottava mark found)
        return ''

    def _isLastEndOttavaLikeThisInStaff(self, token: HumdrumToken, endOttavaText: str) -> bool:
        # Search the rest of this track (on this HumdrumLine) for other ottava ends
        # like this. If there are none, then this is the last of the ottava ends in
        # this track/staff, so we return True.
        ourTrack: int | None = token.track
        tok: HumdrumToken | None = token.nextFieldToken
        if tok is None:
            # no more tokens on line (and no such end ottava found)
            return True

        ttrack: int | None = tok.track
        while ttrack == ourTrack:
            if tok.text == endOttavaText:
                # found an end ottava like token in our staff (token is not the last one)
                return False

            tok = tok.nextFieldToken
            if tok is None:
                # no more tokens on line (and no such end ottava found)
                return True
            ttrack = tok.track

        # no more tokens in other voices in our track/staff (and no such end ottava found)
        return True

    '''
    //////////////////////////////
    //
    // HumdrumInput::handlePedalMark --  *ped turns on and *Xped turns off.
        If you see *Xped followed by *ped (i.e. at same timestamp), that's
        a bounce.  *ped without a *Xped just before it can also be a bounce
        if the pedal is already down, but in that case it's an 'altsymbol'
        bounce ('Ped.' bounce, not '*Ped.' bounce)
    '''
    # pylint: disable=no-member
    def _handlePedalMark(
        self,
        measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        token: HumdrumToken
    ) -> bool:
        insertedIntoVoice: bool = False

        if not M21Utilities.m21PedalMarksSupported():
            return insertedIntoVoice

        if token.text not in ('*ped', '*Xped'):
            return insertedIntoVoice

        track: int | None = token.track
        if track is None:
            # not a kern/mens spine
            return insertedIntoVoice

        staffIndex: int = self._staffStartsIndexByTrack[track]
        if staffIndex < 0:
            # not a kern/mens spine
            return insertedIntoVoice

        # we insert pedal stuff in the measure, not down here in the voice
        pedalOffsetInMeasure: HumNum = token.durationFromBarline
        measure: m21.stream.Measure = self._allMeasuresPerStaff[measureIndex][staffIndex]
        ss: StaffStateVariables = self._staffStates[staffIndex]
        if token.text == '*ped':
            bounceBefore: bool = self._hasBounceBefore(token)

            # pedal down
            if ss.currentPedalMark is not None:
                # pedal is already down, just insert a bounce here
                pedalBounce = m21.expressions.PedalBounce()  # type: ignore
                if not bounceBefore:
                    # bounce is just 'Ped.', not '*Ped.'
                    pedalBounce.overrideBounceUp = m21.expressions.PedalForm.NoMark  # type: ignore
                measure.coreInsert(pedalOffsetInMeasure, pedalBounce)
                ss.currentPedalMark.addSpannedElements(pedalBounce)
            else:
                # pedal is not down, start a new PedalMark spanner with a SpannerAnchor
                anchor = m21.spanner.SpannerAnchor()
                measure.coreInsert(pedalOffsetInMeasure, anchor)
                ss.currentPedalMark = m21.expressions.PedalMark()  # type: ignore
                ss.currentPedalMark.addSpannedElements(anchor)
                measure.coreInsert(pedalOffsetInMeasure, ss.currentPedalMark)
            insertedIntoVoice = True
        elif token.text == '*Xped':
            bounceAfter: bool = self._hasBounceAfter(token)
            if bounceAfter:
                # this will be handled later, when we reach that pedal down
                return insertedIntoVoice

            # pedal up (not a bounce).
            if ss.currentPedalMark is None:
                # weird, the pedal is not down.  Just ignore this pedal up, I guess...
                return insertedIntoVoice

            # End the current PedalMark spanner with an anchor
            anchor = m21.spanner.SpannerAnchor()
            measure.coreInsert(pedalOffsetInMeasure, anchor)
            ss.currentPedalMark.addSpannedElements(anchor)
            ss.currentPedalMark = None
            insertedIntoVoice = True

        return insertedIntoVoice
    # pylint: enable=no-member

    '''
    //////////////////////////////
    //
    // HumdrumInput::hasBounceAfter -- If an *Xped has a *ped after it
    //    at the same timestamp, then the *Xped should be ignored
    //    as the following *ped will be turned into a bounce.
    '''
    def _hasBounceAfter(self, token: HumdrumToken) -> bool:
        if token.text != '*Xped':
            return False

        timestamp: HumNum = token.durationFromStart
        current: HumdrumToken | None = token.nextToken0
        while current is not None and current.durationFromStart == timestamp:
            if current.text == '*ped':
                return True
            current = current.nextToken0

        return False

    '''
    //////////////////////////////
    //
    // HumdrumInput::hasBounceBefore -- If a *ped has an *Xped before it
    //    at the same timestamp, then it should be converted to a bounce.
    '''
    def _hasBounceBefore(self, token: HumdrumToken) -> bool:
        if token.text != '*ped':
            return False

        timestamp: HumNum = token.durationFromStart
        current: HumdrumToken | None = token.previousToken0
        while current is not None and current.durationFromStart == timestamp:
            if current.text == '*Xped':
                return True
            current = current.previousToken0

        return False

    def _handleCustos(
        self,
        measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        token: HumdrumToken
    ) -> bool:
        # TODO: *custos
        return False

    def _handleRepInterp(
        self,
        measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        token: HumdrumToken
    ) -> bool:
        # TODO: *rep (repetition element)
        return False

    def _handleColorInterp(self, measureIndex: int, token: HumdrumToken) -> None:
        # TODO: *color (spine color)
        # if '*color:' not in token.text:
        #     return
        # self.setSpineColorFromColorInterpToken(token)
        return  # _handleColorInterp needs implementation

    def _handleClefChange(
        self,
        measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int,
        staffIndex: int
    ) -> bool:
        # vOffsetInMeasure: HumNum = opFrac(voiceOffsetInMeasure)
        token: HumdrumToken | FakeRestToken = layerData[tokenIdx]
        if token.isFakeRest:
            return False

        if t.TYPE_CHECKING:
            # We know because token.isFakeRest is False
            assert isinstance(token, HumdrumToken)

        forceClefChange: bool = False
        if token.isClef:
            if token.getValueBool('auto', 'clefChange'):
                forceClefChange = True

        if token.isMens:
            return False  # LATER: support **mens (handleClefChange)

        if forceClefChange or token.durationFromStart != 0:
            if token.isClef:
                if self.acceptSyntaxErrors:
                    # truncate at first ' ' seen
                    subtokens: list[str] = token.text.split(' ')
                    if len(subtokens) > 1:
                        token.text = subtokens[0]
                        token.ownerLine.createLineFromTokens()
                        self.numSyntaxErrorsFixed += len(subtokens) - 1

                # we do clef changes up in the measure, not in the voices
                clefOffsetInMeasure: HumNum = token.durationFromBarline
                m21Clef: m21.clef.Clef = M21Convert.m21Clef(token)
                measure: m21.stream.Measure = self._allMeasuresPerStaff[measureIndex][staffIndex]
                measure.coreInsert(clefOffsetInMeasure, m21Clef)
                return True

#             elif token.isNull:
#                 if tokenIdx > 0 and token.lineIndex == layerData[tokenIdx-1].lineIndex:
#                     pass # do nothing: duplicate layer clefs are handled elsewhere
#                 else:
#                     # duplicate clef changes in secondary layers
#                     xtrack: int = token.track
#                     tok: HumdrumToken = token.previousFieldToken
#                     while tok is not None:
#                         ttrack: int = tok.track
#                         if ttrack == xtrack:
#                             if tok.isClef:
#                                 clefOffsetInMeasure: Fraction = token.durationFromBarline
#                                 clefOffsetInVoice: HumNum = opFrac(
#                                     clefOffsetInMeasure - vOffsetInMeasure
#                                 )
#                                 m21Clef: m21.clef.Clef = M21Convert.m21Clef(tok)
#                                 voice.coreInsert(clefOffsetInVoice, m21Clef)
#                                 insertedIntoVoice = True
#                                 break
#                         tok = tok.previousFieldToken
        return False

#     def _handleTimeSigChange(self,
#                              _measureIndex: int,
#                              _voice: m21.stream.Voice,
#                              _voiceOffsetInMeasure: HumNumIn,
#                              _token: HumdrumToken,
#                              _staffIndex: int) -> bool:
#         if token.isTimeSignature:
#             # Now done at the measure level.  This location might
#             # be good for time signatures which change in the
#             # middle of measures.
#             # _processDirections is now done, more generally, in
#             # _processInterpretationLayerToken.
#             # return self._processDirections(
#             #     measureIndex, voice, voiceOffsetInMeasure, token, staffIndex)
#             pass
#
#         return False

    '''
    //////////////////////////////
    //
    // HumdrumInput::handleStaffDynamStateVariables -- Deal with simple boolean switches
    //     that are turned on/off by interpretation tokens in **dynam spines.
    //
    // NB: need to set to part level rather than staff level?
    //
    // Controls that this function deals with:
    //    *above   = Force all dynamics above staff.
    //    *above:2 = Force all dynamics above staff below top one
    //    *below   = Force all dynamics below the staff.
    //    *below:2 = Force all dynamics below staff below top one
    //    *center  = Force all dynamics to be centered between this staff and the one below.
    '''
    def _handleStaffDynamicsStateVariables(
        self,
        _measureIndex: int,
        token: HumdrumToken,
        staffIndex: int
    ) -> None:
        ss: StaffStateVariables = self._staffStates[staffIndex]

        tok: HumdrumToken | None = token.nextFieldToken
        while tok and not tok.isKern:
            if not tok.isDataType('**dynam'):
                tok = tok.nextFieldToken
                continue

            if tok.text == '*above':
                ss.dynamPos = +1        # above a staff
                ss.dynamStaffAdj = 0    # above _this_ staff
                tok = tok.nextFieldToken
                continue

            if tok.text == '*above:2':
                ss.dynamPos = +1        # above a staff
                ss.dynamStaffAdj = -1   # above the staff below _this_ staff
                tok = tok.nextFieldToken
                continue

            if tok.text == '*below:2':
                ss.dynamPos = -1        # below a staff
                ss.dynamStaffAdj = -1   # below the staff below _this_ staff
                tok = tok.nextFieldToken
                continue

            if tok.text == '*below':
                ss.dynamPos = -1        # below a staff
                ss.dynamStaffAdj = 0    # below _this_ staff
                tok = tok.nextFieldToken
                continue

            if tok.text == '*center':
                ss.dynamPos = 0            # centered between a staff and the staff below
                ss.dynamPosDefined = True  # so we know that dynamPos=0 means something
                ss.dynamStaffAdj = 0       # centered between _this_ staff and the staff below
                tok = tok.nextFieldToken
                continue

            if tok.text == '*center:2':
                # for centering on organ staff between pedal
                # and bottom of grand staff.
                ss.dynamPos = 0
                ss.dynamPosDefined = True
                ss.dynamStaffAdj = -1
                tok = tok.nextFieldToken
                continue

            tok = tok.nextFieldToken


    r'''
    //////////////////////////////
    //
    // HumdrumInput::handleStaffStateVariables -- Deal with simple boolean switches
    //     that are turned on/off by interpretation tokens.
    //
    // Controls that this function deals with:
    //    *Xtuplet     = suppress beam and bracket tuplet numbers
    //    *tuplet      = display beam and bracket tuplet numbers
    //    *Xtremolo    = terminal *tremolo contraction
    //    *tremolo     = merge possible beam groups into tremolos
    //    *Xbeamtup    = suppress beam tuplet numbers
    //    *beamtup     = display beam tuplet numbers
    //    *Xbrackettup = suppress tuplet brackets
    //    *brackettup  = display tuplet brackets
    //    *Xcue        = notes back to regular size (operates at layer rather than staff level).
    //    *cue         = display notes in cue size (operates at layer rather than staff level).
    //    *kcancel     = display cancellation key signatures
    //    *Xkcancel    = do not display cancellation key signatures (default)
    //    *2\right     = place stems on right side of half notes when stem is down.
    //    *2\left      = place stems on left side of half notes when stem is down.
    //    *stem:       = automatic assignment of stems if there are no stems on the note already.
    //       *stem:X   = no automatic assignment
    //       *stem:x   = no stem
    //       *stem:/   = no stem up
    //       *stem:\   = no stem down
    //    *head:       = notehead shape
    '''
    def _handleStaffStateVariables(
        self,
        _measureIndex: int,
        token: HumdrumToken,
        layerIndex: int,
        staffIndex: int
    ) -> None:
        ss: StaffStateVariables = self._staffStates[staffIndex]
        if token.text in ('*Xbeamtup', '*Xtuplet'):
            ss.suppressTupletNumber = True
            return
        if token.text == '*beamtup' or token.text.startswith('*tuplet'):
            ss.suppressTupletNumber = False
            return

        if token.text == '*Xbrackettup':
            ss.suppressTupletBracket = True
            return
        if token.text == '*brackettup':
            ss.suppressTupletBracket = False
            return

        if token.text == '*Xtremolo':
            ss.tremolo = False
            return
        if token.text == '*tremolo':
            ss.tremolo = True
            self._hasTremolo = True
            return

        if token.text == '*Xcue':
            ss.cueSize[layerIndex] = False
            return
        if token.text == '*cue':
            ss.cueSize[layerIndex] = True
            return

        if token.text.startswith('*stem'):
            self._storeStemInterpretation(token.text, staffIndex, layerIndex)
            return

#         if 'acclev' in token.text:
#             self._storeAcclev(token.text, staffIndex)
#             return

#         if token.text == r'*2\left':
#             ss.rightHalfStem = False
#             return
#         if token.text == r'*2\right':
#             ss.rightHalfStem = True
#             return

        # Note that music21 does not have a way to annotate key signature cancellation.
        # I would add that MusicXML also has a "cancel the previous key sig" mechanism
        # that is not translated to music21 for the same reason.  Sounds like a good
        # thing to add to music21 and these two parsers. --gregc
        # TODO: cancel previous key signature

#         # Key cancellation option is currently global to all staves:
#         if token.text == '*Xkcancel':
#             self._show_cautionary_keysig = False
#             return
#         if token.text == '*kcancel':
#             self._show_cautionary_keysig = True
#             return

        m = re.search(r'^\*head:([^:]*):?', token.text)
        # There may be a pitch parameter after the shape,
        # but this is ignored for now.
        if m:
            ss.noteHead = m.group(1)

    '''
    //////////////////////////////
    //
    // HumdrumInput::handleTempoChange -- Generate <tempo> from *MM# interpretation as
    //    long as there is no <tempo> text that will use the tempo *MM# as @midi.bpm.
    //    *MM at the start of the music is ignored (placed separately into scoreDef).
    '''
    def _handleTempoChange(self, measureIndex: int, token: HumdrumToken, staffIndex: int) -> None:
        if not token.isTempo:
            return

        isAlreadyHandled: bool = token.getValueBool('auto', 'MM handled')
        if isAlreadyHandled:
            # this *MM has already been incorporated into a MetronomeMark (via
            # processing an OMD or a !!LO:TX:omd:t=whatever)
            return

        # bail if you see a nearby OMD just before this token, since the processing
        # of that non-initial OMD (see _checkForOmd) has handled this *MM for us.
        # If the nearby OMD is partway through a measure, though, it will not have
        # been handled by _checkForOmd (which prepends a measure with a starting
        # tempo change), and we will need to handle it here (and get the tempo name
        # from the OMD if necessary, see below).
        if self._isNearHandledOmd(token):
            # we've handled this *MM in _checkForOmd()
            return

        tempoName: str = token.tempoName  # *MM[Adagio] => tempoName == 'Adagio', tempoBPM == 0
        tempoBPM: int = token.tempoBPM    # *MM127.5 => tempoBPM == 128, tempoName == ''

        if not tempoName and tempoBPM <= 0:
            return

        if self._hasTempoTextAfterMM(token):
            # we'll handle this *MM during text direction processing
            return

        # Only insert the tempo if there is no higher kern/mens spine
        # that has a tempo marking at the same time.
        if not self._isLastStaffTempo(token):
            return

        nearbyUnhandledOMD: HumdrumLine | None = None
        if not tempoName:
            # if there's a nearby unhandled OMD, get the tempoName from there.
            nearbyUnhandledOMD = self._getNearbyUnhandledOmdLine(token)
            if nearbyUnhandledOMD is not None:
                firstTok: HumdrumToken | None = nearbyUnhandledOMD[0]
                if firstTok is not None and self._isTempoish(firstTok.text):
                    firstTok.setValue('auto', 'OMD handled', True)
                    tempoName = nearbyUnhandledOMD.referenceValue

        if tempoName:
            tempoName = html.unescape(tempoName)
            tempoName = tempoName.replace(r'\n', '\n')
            tempoName = tempoName.strip()

        mmText: str | None = tempoName
        if mmText == '':
            mmText = None
        mmNumber: int | None = tempoBPM
        if mmNumber is not None and mmNumber <= 0:
            mmNumber = None

        if mmText is not None or mmNumber is not None:
            # We insert this tempo at the beginning of the measure
            # OMD and *MM have no way of specifying placement or fontStyle,
            # so we default to the usual: 'above' and 'bold'.
            if mmText is not None and self._isTempoish(mmText):
                # convert [quarter] (etc) to actual SMUFL quarter note
                mmText = Convert.getTempoText(mmText)
            tempo: m21.tempo.MetronomeMark = self._myMetronomeMarkInit(
                number=mmNumber, text=mmText
            )
            if t.TYPE_CHECKING:
                assert isinstance(tempo.style, m21.style.TextStyle)
            tempo.style.fontStyle = 'bold'
            if hasattr(tempo, 'placement'):
                tempo.placement = 'above'  # type: ignore
            else:
                tempo.style.absoluteY = 'above'

            # TODO: If nearbyUnhandledOMD is actually '!!LO:TX:omd:t=', then we should
            # TODO: override that default 'bold'/'above' with anything specified there.

            tempoOffsetInMeasure: HumNum = token.durationFromBarline

            currentMeasurePerStaff: list[m21.stream.Measure] = (
                self._allMeasuresPerStaff[measureIndex]
            )
            currentMeasurePerStaff[staffIndex].coreInsert(
                tempoOffsetInMeasure, tempo
            )
            currentMeasurePerStaff[staffIndex].coreElementsChanged()

    '''
    //////////////////////////////
    //
    // HumdrumInput::isLastStaffTempo --
        I have changed the definition of this to not care about track numbers,
        just look to see if there's a higher kern/mens spine with a tempo. --gregc
    '''
    @staticmethod
    def _isLastStaffTempo(token: HumdrumToken) -> bool:
        field: int = token.fieldIndex + 1
        line: HumdrumLine = token.ownerLine
        for i in range(field, line.tokenCount):
            newTok: HumdrumToken | None = line[i]
            if newTok is None or not newTok.isStaffDataType:  # kern or mens
                continue
            if newTok.isTempo:
                return False
        return True

    '''
    //////////////////////////////
    //
    // HumdrumInput::hasTempoTextAfter -- Used to check of *MM# tempo change has potential <tempo>
    //    text after it, but before any data.  Will not cross a measure boundary.
    //    Input token is assumed to be a *MM interpertation (MIDI-like tempo change)
    //    Algorithm: Find the first note after the input token and then check for a local
    //    or global LO:TX parameter that applies to that note (for local LO:TX).
    '''
    def _hasTempoTextAfterMM(self, token: HumdrumToken) -> bool:
        inFile: HumdrumFile = token.ownerLine.ownerFile
        startLineIdx: int = token.lineIndex
        current: HumdrumToken | None = token.nextToken0
        if not current:
            return False

        # search for local LO:TX:
        while current and not current.isData:
            current = current.nextToken0
        if not current:
            # No more data: at the end of the music.
            return False

        data: HumdrumToken = current
        dataLineIdx: int = data.lineIndex
        # now work backwards through all null local comments and !LO: parameters searching
        # for potential tempo text
        texts: list[str] = []

        current = data.previousToken0
        if not current:
            return False

        line: int = current.lineIndex
        while current and line > startLineIdx:
            if current.isManipulator:
                # skip over it and keep looking
                current = current.previousToken0
                if current is not None:
                    line = current.lineIndex
                continue

            if not current.isLocalComment:
                break

            if current.text.startswith('!LO:TX:'):
                texts.append(current.text)

            current = current.previousToken0
            if current is not None:
                line = current.lineIndex

        for text in texts:
            if self._isTempoishLayout(text):
                return True

        # now check for global tempo text
        texts = []
        for i in reversed(range(startLineIdx + 1, dataLineIdx)):
            linei: HumdrumLine | None = inFile[i]
            if linei is None:
                continue
            gtok: HumdrumToken | None = linei[0]  # token 0 of line i
            if gtok is None:
                continue
            if gtok.text.startswith('!!LO:TX:'):
                texts.append(gtok.text)

        for text in texts:
            if self._isTempoishLayout(text):
                return True

        return False

    def _hasTempoTextAfterOMD(self, token: HumdrumToken) -> bool:
        inFile: HumdrumFile = token.ownerLine.ownerFile
        startLineIdx: int = token.lineIndex

        # search for first spined line and start at that line's first token
        current: HumdrumToken | None = token
        i: int = startLineIdx
        linei: HumdrumLine | None = inFile[i]
        while current is not None and linei is not None and not linei.isData:
            i += 1
            linei = inFile[i]
            if linei is None:
                continue
            current = linei[0]

        if not current:
            return False

        # current points at first data line after OMD.
        data: HumdrumToken = current
        dataLineIdx: int = data.lineIndex
        # now work backwards (to the OMD) searching for potential tempo text
        texts: list[str] = []

        for i in reversed(range(startLineIdx + 1, dataLineIdx)):
            linei = inFile[i]
            if linei is None:
                continue
            for tok in linei.tokens():
                if tok is None:
                    continue
                if tok.text.startswith('!LO:TX:') or tok.text.startswith('!!LO:TX:'):
                    texts.append(tok.text)

        for text in texts:
            if self._isTempoishLayout(text):
                return True

        return False

    '''
    //////////////////////////////
    //
    // HumdrumInput::isTempoishText -- Return true if the text is probably tempo indication.
    '''
    def _isTempoishLayout(self, text: str) -> bool:
        if re.search(':tempo:', text):
            return True
        if re.search(':temp$', text):
            return True
        m = re.search(':t=([^:]+)', text)
        if not m:
            return False

        textStr: str = m.group(1)
        if self._isTempoish(textStr):
            return True

        return False

    @staticmethod
    def _isTempoish(text: str) -> bool:
        if not text:
            return False

        if Convert.hasMetronomeMarkInfo(text):
            return True

        return False
    '''
    //////////////////////////////
    //
    // HumdrumInput::isNearOmd -- Returns true of the line of the token is adjacent to
    //    An OMD line, with the boundary being a data line (measures are included).
    '''
    @staticmethod
    def _isNearHandledOmd(token: HumdrumToken) -> bool:
        tline: int = token.lineIndex
        inFile: HumdrumFile = token.ownerLine.ownerFile
        linei: HumdrumLine | None
        ltok: HumdrumToken | None
        for i in reversed(range(0, tline)):
            linei = inFile[i]
            if linei is None:
                continue
            ltok = linei[0]  # token 0 of line i
            if ltok is None:
                continue
            if ltok.isData:
                break
            if not linei.isReference:
                continue
            if ltok.text.startswith('!!!OMD') and ltok.getValueBool('auto', 'OMD handled'):
                return True

        for i in range(tline + 1, inFile.lineCount):
            linei = inFile[i]
            if linei is None:
                continue
            ltok = linei[0]  # token 0 of line i
            if ltok is None:
                continue
            if ltok.isData:
                break
            if not linei.isReference:
                continue
            if ltok.text.startswith('!!!OMD') and ltok.getValueBool('auto', 'OMD handled'):
                return True

        return False

    @staticmethod
    def _getNearbyUnhandledOmdLine(token: HumdrumToken) -> HumdrumLine | None:
        tline: int = token.lineIndex
        inFile: HumdrumFile = token.ownerLine.ownerFile
        linei: HumdrumLine | None
        ltok: HumdrumToken | None

        for i in reversed(range(0, tline)):
            linei = inFile[i]
            if linei is None:
                continue
            ltok = linei[0]  # token 0 of line i
            if ltok is None:
                continue
            if ltok.isData:
                break
            if not linei.isReference:
                continue
            if ltok.text.startswith('!!!OMD') and not ltok.getValueBool('auto', 'OMD handled'):
                return linei

        for i in range(tline + 1, inFile.lineCount):
            linei = inFile[i]
            if linei is None:
                continue
            ltok = linei[0]  # token 0 of line i
            if ltok is None:
                continue
            if ltok.isData:
                break
            if not linei.isReference:
                continue
            if ltok.text.startswith('!!!OMD') and not ltok.getValueBool('auto', 'OMD handled'):
                return linei

        return None


    '''
        _handleGroupState adds beams and tuplets to a note/rest in the layer, as appropriate.

        In music21, every note/chord/rest has a Tuplet (in its Duration), that both describes
        the timing of that note, and the bracketing of the tuplet in the score.  In music21,
        every note/chord has a Beams object that contains 0 or more Beam objects (e.g. beamed
        16th notes have two Beam objects each).
    '''
    def _handleGroupState(
        self,
        currState: BeamAndTupletGroupState,
        tgs: list[HumdrumBeamAndTuplet | None],
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int,
        staffIndex: int,
        tremoloBeam: bool = False,
        tremolo: bool = False
    ) -> BeamAndTupletGroupState:
        token: HumdrumToken | FakeRestToken = layerData[tokenIdx]
        tg: HumdrumBeamAndTuplet | None = tgs[tokenIdx]
        if t.TYPE_CHECKING:
            # we have completely filled in tgs by now
            assert isinstance(tg, HumdrumBeamAndTuplet)
        newState: BeamAndTupletGroupState = copy.copy(currState)

        if token.isFakeRest:
            return newState

        if t.TYPE_CHECKING:
            assert isinstance(token, HumdrumToken)

        if tg.beamStart or tg.gbeamStart:
            pattern: str
            direction: int = 0
            if self._signifiers.above:
                pattern = '[LJKk]+' + self._signifiers.above
                if re.search(pattern, token.text):
                    direction = 1
            if self._signifiers.below:
                pattern = '[LJKk]+' + self._signifiers.below
                if re.search(pattern, token.text):
                    direction = -1
            if direction != 0:
                self._setBeamDirection(direction, tgs, layerData,
                                       tokenIdx, isGrace=tg.gbeamStart != 0)

        # tuplets first, because this can (temporarily) change the duration of a note,
        # which could remove any beams we set up, as no longer appropriate.  Note that
        # unlike iohumdrum.cpp, we don't need to nest tuplets and beams (that start or
        # end together) carefully, since music21, unlike MEI, doesn't require that.

        # handle tuplet state
        if tg.tupletStart:
            # start a tuplet
            # we have our own Tuplet constructor to set defaults
            newState.m21Tuplet = self._makeTuplet(
                tg.numNotesActual,
                tg.numNotesNormal,
                None,  # tg.durationTupleNormal,
                tg.numScale
            )
            # start the tuplet
            self._startTuplet(layerData, tokenIdx, newState.m21Tuplet, staffIndex, tremolo)
            newState.inTuplet = True
        elif newState.inTuplet and tg.tupletEnd:
            # end the tuplet
            assert newState.m21Tuplet is not None
            self._endTuplet(layerData, tokenIdx, newState.m21Tuplet, tremolo)
            newState.inTuplet = False
            newState.m21Tuplet = None
        elif newState.inTuplet:
            # continue the tuplet
            assert newState.m21Tuplet is not None
            self._continueTuplet(layerData, tokenIdx, newState.m21Tuplet, tremolo)

        # handle beam state
        if tg.beamStart:
            # start the beam
            self._startBeam(layerData, tokenIdx)
            newState.inBeam = True
            newState.previousBeamTokenIdx = tokenIdx
        elif newState.inBeam and tg.beamEnd:
            # end the beam
            self._endBeam(
                layerData, tokenIdx, newState.previousBeamTokenIdx, tremoloBeam=tremoloBeam
            )
            newState.inBeam = False
            newState.previousBeamTokenIdx = -1
        elif newState.inBeam and not token.isRest and not token.isGrace:
            # continue the beam (but not if it's a rest or grace note, they can be within
            # the beam duration, but they won't have beams, obviously)
            self._continueBeam(layerData, tokenIdx, newState.previousBeamTokenIdx)
            newState.previousBeamTokenIdx = tokenIdx

        # handle gbeam state
        if tg.gbeamStart:
            # start the grace note beam
            self._startGBeam(layerData, tokenIdx)
            newState.inGBeam = True
            newState.previousGBeamTokenIdx = tokenIdx
        elif newState.inGBeam and tg.gbeamEnd:
            # end the grace note beam
            self._endGBeam(layerData, tokenIdx, newState.previousGBeamTokenIdx)
            newState.inGBeam = False
            newState.previousGBeamTokenIdx = -1
        elif newState.inGBeam:
            # continue the grace note beam
            self._continueGBeam(layerData, tokenIdx, newState.previousGBeamTokenIdx)
            newState.previousGBeamTokenIdx = tokenIdx

        return newState

    @staticmethod
    def _makeTuplet(
        numberNotesActual: int,
        numberNotesNormal: int,
        durationNormal: m21.duration.DurationTuple | None,
        numScale: int | None = None
    ) -> m21.duration.Tuplet:

        numActual: int = numberNotesActual
        numNormal: int = numberNotesNormal
        durNormal: m21.duration.DurationTuple | None = durationNormal
        if numScale is not None and numScale != 1:
            # multiply numActual and numNormal by numScale
            # dived durNormal by numScale
            numActual *= numScale
            numNormal *= numScale
            if durNormal is not None:
                durNormal = m21.duration.durationTupleFromQuarterLength(
                    opFrac(durNormal.quarterLength / numScale)
                )

        tuplet: m21.duration.Tuplet = m21.duration.Tuplet(
            numberNotesActual=numActual,
            numberNotesNormal=numNormal,
            durationNormal=durNormal,
            durationActual=durNormal
        )
        # apply our own defaults

        # m21 default tuplet placement is 'above', but it should be None.  The only client I
        # can see is m21ToXML.py, which handles placement == None by not specifying placement
        # in the output XML.  That is exactly what we want as default behavior, so we will
        # always set tuplet.placement to None as a default.

        # our better default
        tuplet.placement = None  # type: ignore

        # I have the same issue with music21's default tuplet bracket, which is True.
        # I want to default to unspecified, which is None.  Unfortunately, m21ToXML.py
        # doesn't check for tuplet.bracket == None, like it does for tuplet.placement,
        # so I'll need to update that at some point.  For now, m21ToXML.py will treat
        # None as False, which seems wrong, but not fatally so. --gregc
        tuplet.bracket = None  # type: ignore

        # print('_makeTuplet: tuplet =', tuplet, file=sys.stderr)
        return tuplet

    '''
        _getNumBeamsForNoteOrChord --
    '''
    @staticmethod
    def _getNumBeamsForNoteOrChord(
        token: HumdrumToken | FakeRestToken,
        noteOrChord: m21.note.NotRest
    ) -> int:
        if noteOrChord is None:
            return 0
        if token.isFakeRest:
            return 0

        if t.TYPE_CHECKING:
            # we know because token.isFakeRest is False
            assert isinstance(token, HumdrumToken)

        # adjust if this note is in a fingered tremolo (currently all beams are marks
        # in that case, so return zero beams).
        if noteOrChord.getSpannerSites('TremoloSpanner'):
            return 0

        noteDurationNoDots: HumNum
        if token.isGrace:
            noteDurationNoDots = token.graceVisualDuration
        else:
            noteDurationNoDots = token.durationNoDots  # unless we're in a tuplet
            # override with visual duration if present
            durVis: str = token.getVisualDuration()
            if durVis:
                noteDurationNoDots = Convert.recipToDurationNoDots(durVis)

            if len(noteOrChord.duration.tuplets) > 1:
                # LATER: support nested tuplets (music21 needs to support this first)
                return 0

            if len(noteOrChord.duration.tuplets) == 1:
                # actual notes vs normal notes:  In an eighth-note triplet, actual notes is 3,
                # and normal notes is 2.  i.e. 3 actual notes are played in the duration of 2
                # normal notes
                # We do this tuplet adjustment if there is no visual duration or if there
                # is a visual duration and it looks tuplet-y (not a power of two).
                if not durVis or not M21Utilities.isPowerOfTwo(noteDurationNoDots):
                    multiplier: Fraction = Fraction(
                        noteOrChord.duration.tuplets[0].numberNotesActual,
                        noteOrChord.duration.tuplets[0].numberNotesNormal
                    )
                    noteDurationNoDots = opFrac(noteDurationNoDots * opFrac(multiplier))

        if isinstance(noteDurationNoDots, Fraction):
            # normalize the Fraction (not sure this is actually necessary now that we are
            # using opFrac, but let's try not to make any assumptions about the implementation
            # of opFrac and Fraction)
            noteDurationNoDots = opFrac(
                Fraction(noteDurationNoDots.numerator, noteDurationNoDots.denominator)
            )

        if noteDurationNoDots not in durationNoDotsToNumBeams:
            return 0

        numBeams: int = durationNoDotsToNumBeams[noteDurationNoDots]

        # adjust if this note is a bowed tremolo (numberOfMarks replaces some beams)
        for expression in noteOrChord.expressions:
            if isinstance(expression, m21.expressions.Tremolo):
                numBeams -= expression.numberOfMarks
                break

        return numBeams

    def _startBeam(
        self,
        layerData: list[HumdrumToken | FakeRestToken],
        startTokenIdx: int
    ) -> None:
        token: HumdrumToken | FakeRestToken = layerData[startTokenIdx]
        if token.isFakeRest:
            return

        if t.TYPE_CHECKING:
            # We know because token.isFakeRest is False
            assert isinstance(token, HumdrumToken)

        obj: m21.Music21Object | None = token.getValueM21Object('music21', 'generalNote')
        if not isinstance(obj, m21.note.NotRest):
            print(f'startBeam failed: no m21 NotRest found in token ({token})')
            return

        # We append explicitly (instead of with a single call to beams.fill(numBeams))
        # because we may need more than 6 (dur == 1/256), and 6 is beams.fill's hard-
        # coded limit.
        numBeams: int = self._getNumBeamsForNoteOrChord(token, obj)
        for _ in range(0, numBeams):
            obj.beams.append('start')

    @staticmethod
    def _findStartOfTremolo(
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int
    ) -> int:
        for i in range(tokenIdx, -1, -1):
            # all tremolo starts are marked with 'startTremolo'
            if layerData[i].getValue('auto', 'startTremolo') is not None:
                return i
        raise HumdrumInternalError('cannot find start of tremolo')

    def _continueBeam(
        self,
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int,
        prevBeamTokenIdx: int,
        beamType: str = 'continue',
        tremoloBeam: bool = False
    ) -> None:
        if tremoloBeam and beamType == 'stop':  # last note in a beamed group of tremolos
            # search back for first note in the first tremolo of a beamed group of tremolos
            tokenIdx = self._findStartOfTremolo(layerData, tokenIdx)

        token: HumdrumToken | FakeRestToken = layerData[tokenIdx]
        if token.isFakeRest:
            return

        obj: m21.Music21Object | None = token.getValueM21Object('music21', 'generalNote')
        if not isinstance(obj, m21.note.NotRest):
            return

        if tremoloBeam and beamType == 'stop':
            # replace the last beam in obj (probably a 'continue') with a 'stop'.
            # Note that setByNumber is 1-based, so len(beamsList) is the last beam.
            beamNum: int = len(obj.beams.beamsList)
            if beamNum > 0:
                obj.beams.setByNumber(beamNum, beamType)
            else:
                # there are no existing beams, create a 'stop' beam
                obj.beams.append(beamType)
            return

        prevToken: HumdrumToken | FakeRestToken = layerData[prevBeamTokenIdx]
        prevObj: m21.Music21Object | None = prevToken.getValueM21Object(
            'music21',
            'generalNote'
        )
        if not isinstance(prevObj, m21.note.NotRest):
            return

        numBeams: int = self._getNumBeamsForNoteOrChord(token, obj)
        prevNumBeams: int = self._getNumBeamsForNoteOrChord(prevToken, prevObj)
        if 0 < numBeams < prevNumBeams:
            # we're not dealing with secondary breaks here (that happens below), just
            # beam counts that are derived from the note durations.  So this means the
            # previous note needs to be modified to have his extra beams turn into
            # 'stop'ped beams (or 'partial' beams)
            for beamNum in range(numBeams + 1, prevNumBeams + 1):  # beam numbers are 1-based
                prevObjBeam = prevObj.beams.getByNumber(beamNum)
                if prevObjBeam.type == 'start':
                    prevObj.beams.setByNumber(beamNum, 'partial', direction='right')
                else:
                    prevObj.beams.setByNumber(beamNum, 'stop')

            # now do our beams
            for _ in range(0, numBeams):
                obj.beams.append(beamType)

        elif 0 < prevNumBeams < numBeams:
            for i in range(0, numBeams):
                if beamType == 'stop':
                    if i in range(prevNumBeams, numBeams):
                        obj.beams.append('partial', direction='left')
                    else:
                        obj.beams.append('stop')
                else:
                    if i in range(prevNumBeams, numBeams):
                        obj.beams.append('start')
                    else:
                        obj.beams.append('continue')
        else:
            # normal case (prevNumBeams == numBeams)
            for _ in range(0, numBeams):
                obj.beams.append(beamType)

        # now handle any requested secondary beam breaks
        # we actually get the request on prevToken, and
        # make changes to both prevToken ('continue' becomes 'stop')
        # and token ('continue' becomes 'start')
        breakBeamCount = prevToken.getValueInt('auto', 'breakBeamCount')
        if breakBeamCount > 0:
            if prevNumBeams == numBeams and numBeams > breakBeamCount:
                for i in range(breakBeamCount + 1, numBeams + 1):  # beam numbers are 1-based
                    prevObj.beams.setByNumber(i, 'stop')
                    obj.beams.setByNumber(i, 'start')

    def _endBeam(
        self,
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int,
        prevBeamTokenIdx: int,
        tremoloBeam: bool = False
    ) -> None:
        # the implementation here is exactly the same as _continueBeam, so just call him.
        self._continueBeam(
            layerData, tokenIdx, prevBeamTokenIdx, beamType='stop', tremoloBeam=tremoloBeam
        )

    def _startGBeam(
        self,
        layerData: list[HumdrumToken | FakeRestToken],
        startTokenIdx: int
    ) -> None:
        self._startBeam(layerData, startTokenIdx)

    def _continueGBeam(
        self,
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int,
        prevGBeamTokenIdx: int
    ) -> None:
        self._continueBeam(layerData, tokenIdx, prevGBeamTokenIdx)

    def _endGBeam(
        self,
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int,
        prevGBeamTokenIdx: int
    ) -> None:
        self._endBeam(layerData, tokenIdx, prevGBeamTokenIdx)

    def _startTuplet(
        self,
        layerData: list[HumdrumToken | FakeRestToken],
        startTokenIdx: int,
        tupletTemplate: m21.duration.Tuplet,
        staffIndex: int,
        tremolo: bool
    ) -> None:
        ss: StaffStateVariables = self._staffStates[staffIndex]
        startTok: HumdrumToken | FakeRestToken = layerData[startTokenIdx]
        if startTok.isFakeRest:
            raise HumdrumInternalError('FakeRestToken at start of tuplet')

        if t.TYPE_CHECKING:
            # We know because startTok.isFakeRest is False
            assert isinstance(startTok, HumdrumToken)

        startNote: m21.Music21Object | None = startTok.getValueM21Object(
            'music21',
            'generalNote'
        )
        if not isinstance(startNote, m21.note.GeneralNote):
            raise HumdrumInternalError(
                f'no note/chord/rest at start of tuplet (startTok: {startTok})'
            )

        # remember the original duration value, so we can do a debug check at the end
        # to make sure it didn't change (things like changing actual number from 6 to 3
        # are tricky, so we need to check our work).
#         originalQuarterLength: HumNum = opFrac(startNote.duration.quarterLength)

        if tremolo:
            newNoteDuration: m21.duration.Duration | None = None
            tremoloNoteVisualDuration: HumNum | None = None
            tremoloNoteGesturalDuration: HumNum | None = None
            recipStr: str | None = None

            # TODO: this code is very like the tremolo code in _convertRhythm/_endTuplet.
            # TODO: have one copy of this code.
            if startTok.getValueBool('auto', 'startTremolo'):
                recipStr = startTok.getValueString('auto', 'recip')
                if recipStr:
                    tremoloNoteVisualDuration = Convert.recipToDuration(recipStr)
            elif startTok.getValueBool('auto', 'startTremolo2') or \
                    startTok.getValueBool('auto', 'tremoloAux'):
                # In two note tremolos, the two notes each look like they have the full duration
                # of the tremolo sequence, but they actually each need to have half that duration
                # internally, for the measure duration to make sense.
                recipStr = startTok.getValueString('auto', 'recip')
                if recipStr:
                    tremoloNoteVisualDuration = Convert.recipToDuration(recipStr)
                    tremoloNoteGesturalDuration = opFrac(tremoloNoteVisualDuration / opFrac(2))

            if tremoloNoteVisualDuration is not None:
                newNoteDuration = m21.duration.Duration()
                newNoteDuration.quarterLength = tremoloNoteVisualDuration
                if tremoloNoteGesturalDuration is not None:
                    newNoteDuration.linked = False  # leave the note looking like visual duration
                    newNoteDuration.quarterLength = tremoloNoteGesturalDuration
                startNote.duration = newNoteDuration

        duration: m21.duration.Duration = copy.deepcopy(startNote.duration)
        tuplet: m21.duration.Tuplet | None = None

        if tremolo:
            if duration.tuplets:
                tuplet = copy.deepcopy(duration.tuplets[0])  # it's already computed from recip
        else:
            tuplet = copy.deepcopy(tupletTemplate)

        # We may need to compute a new duration from scratch, now that we have the tuplet
        # details.  This is because sometimes music21 doesn't give us a duration we like.
        # For example, Humdrum data might describe a 5-in-the-place-of-6-sixteenth-note-tuplet,
        # and music21 (given only the duration: 3/40 of a whole note) will call that a
        # 5-in-the-place-of-4-dotted-sixteenth-note-tuplet.  Humdrum knows different, because
        # the recip data is very clear: '40%3' == no dots.  music21 will also describe what
        # Humdrum says is a dotted eighth note in a triplet, as a straight eighth note, with no
        # tuplet at all.  Same deal, we know better, so we compute a new duration from scratch,
        # with our tuplet template as a guide.

        # Note that "if tremolo", we've already recomputed the duration, so don't bother here.
        recomputeDuration: bool = False
        if tuplet and not tremolo:
            if duration.tuplets in (None, ()):
                recomputeDuration = True
            elif len(duration.tuplets) > 1:
                recomputeDuration = True
            elif duration.tuplets[0].durationNormal != tuplet.durationNormal:
                recomputeDuration = True
            elif duration.tuplets[0].tupletMultiplier() != tuplet.tupletMultiplier():
                recomputeDuration = True

            if recomputeDuration:
                duration = M21Convert.m21DurationWithTuplet(
                    startTok, tuplet, self.acceptSyntaxErrors
                )
                tuplet = duration.tuplets[0]

        # Now figure out the rest of the tuplet fields (type, placement, bracket, etc)

        if tuplet:
            # type has to be set to 'start', or no-one cares about the placement, bracket, etc
            tuplet.type = 'start'

            if self._hasAboveParameter(startTok, 'TUP'):
                tuplet.placement = 'above'
            elif self._hasBelowParameter(startTok, 'TUP'):
                tuplet.placement = 'below'

            # The staff might have suppressed tuplet brackets
            if ss.suppressTupletBracket or ss.suppressTupletNumber:
                # if we're suppressing tuplet numbers, suppress the bracket
                tuplet.bracket = False

            # Here iohumdrum.cpp decides that if there is a beam that covers exactly this tuplet,
            # then we should suppress the tuplet's bracket.  This seems like an engraving decision,
            # so I'm not going to do it here in the parser.
    #         if self._shouldHideBeamBracket(tgs, layerData, startTokenIdx):
    #             tuplet.bracket = False

            # local control of brackets (overrides staff-level tuplet bracket suppression)
            xbr: bool = self._hasTrueLayoutParameter(startTok, 'TUP', 'xbr')
            br: bool = self._hasTrueLayoutParameter(startTok, 'TUP', 'br')
            if xbr:
                tuplet.bracket = False
            if br:
                tuplet.bracket = True

            # The staff might have suppressed tuplet numbers (e.g. after a measure or two)
            if ss.suppressTupletNumber:
                tuplet.tupletActualShow = None

            # Now set the tuplets in the duration to just this one
            # If we recomputed the duration above, this has already been done.
            if not recomputeDuration:
                duration.tuplets = (tuplet,)

        # And set this new duration on the startNote.
        startNote.duration = duration

        # Check to make sure we didn't change the actual duration of the note
        # (and generate the new quarterLength _now_ so the cache doesn't clear
        # at an inopportune time).
#         newQuarterLength: HumNum = opFrac(startNote.duration.quarterLength)
#         if newQuarterLength != originalQuarterLength:
#             raise HumdrumInternalError('_startTuplet modified duration.quarterLength')

    def _continueTuplet(
        self,
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int,
        tupletTemplate: m21.duration.Tuplet,
        tremolo: bool
    ) -> None:
        token: HumdrumToken | FakeRestToken = layerData[tokenIdx]
        if token.isFakeRest:
            return

        if t.TYPE_CHECKING:
            # We know because token.isFakeRest is False
            assert isinstance(token, HumdrumToken)

        note: m21.Music21Object | None = token.getValueM21Object('music21', 'generalNote')
        if not isinstance(note, m21.note.GeneralNote):
            # This could be a *something interp token (or a suppressed note); just skip it.
            return

        if token.isGrace:  # grace note in the middle of a tuplet, but it's not _in_ the tuplet
            return

        # remember the original duration value, so we can do a debug check at the end
        # to make sure it didn't change (things like changing actual number from 6 to 3
        # are tricky, so we need to check our work).
#         originalQuarterLength: HumNum = opFrac(note.duration.quarterLength)

        if tremolo:
            newNoteDuration: m21.duration.Duration | None = None
            tremoloNoteVisualDuration: HumNum | None = None
            tremoloNoteGesturalDuration: HumNum | None = None

            # TODO: this code is very like the tremolo code in _convertRhythm/_endTuplet.
            # TODO: have one copy of this code.
            recipStr: str | None = None
            if token.getValueBool('auto', 'startTremolo'):
                recipStr = token.getValueString('auto', 'recip')
                if recipStr:
                    tremoloNoteVisualDuration = Convert.recipToDuration(recipStr)
            elif token.getValueBool('auto', 'startTremolo2') or \
                    token.getValueBool('auto', 'tremoloAux'):
                # In two note tremolos, the two notes each look like they have the full duration
                # of the tremolo sequence, but they actually each need to have half that duration
                # internally, for the measure duration to make sense.
                recipStr = token.getValueString('auto', 'recip')
                if recipStr:
                    tremoloNoteVisualDuration = Convert.recipToDuration(recipStr)
                    tremoloNoteGesturalDuration = opFrac(tremoloNoteVisualDuration / opFrac(2))

            if tremoloNoteVisualDuration is not None:
                newNoteDuration = m21.duration.Duration()
                newNoteDuration.quarterLength = tremoloNoteVisualDuration
                if tremoloNoteGesturalDuration is not None:
                    newNoteDuration.linked = False  # leave the note looking like visual duration
                    newNoteDuration.quarterLength = tremoloNoteGesturalDuration
                note.duration = newNoteDuration

        duration: m21.duration.Duration = copy.deepcopy(note.duration)
        tuplet: m21.duration.Tuplet | None = None

        if tremolo:
            if duration.tuplets:
                tuplet = copy.deepcopy(duration.tuplets[0])  # it's already computed from recip
        else:
            tuplet = copy.deepcopy(tupletTemplate)

        # We may need to compute a new duration from scratch, now that we have the tuplet
        # details.  This is because sometimes music21 doesn't give us a duration we like.
        # For example, Humdrum data might describe a 5-in-the-place-of-6-sixteenth-note-tuplet,
        # and music21 (given only the duration: 3/40 of a whole note) will call that a
        # 5-in-the-place-of-4-dotted-sixteenth-note-tuplet.  Humdrum knows different, because
        # the recip data is very clear: '40%3' == no dots.  music21 will also describe what
        # Humdrum says is a dotted eighth note in a triplet, as a straight eighth note, with no
        # tuplet at all.  Same deal, we know better, so we compute a new duration from scratch,
        # with our tuplet template as a guide.

        recomputeDuration: bool = False
        if tuplet and not tremolo:
            if duration.tuplets in (None, ()):
                recomputeDuration = True
            elif len(duration.tuplets) > 1:
                recomputeDuration = True
            elif duration.tuplets[0].durationNormal != tuplet.durationNormal:
                recomputeDuration = True
            elif duration.tuplets[0].tupletMultiplier() != tuplet.tupletMultiplier():
                recomputeDuration = True

            if recomputeDuration:
                duration = M21Convert.m21DurationWithTuplet(
                    token, tuplet, self.acceptSyntaxErrors
                )
                tuplet = duration.tuplets[0]

        # set the tuplet on the note duration.
        # If we recomputed the duration above, this has already been done
        if tuplet and not recomputeDuration:
            duration.tuplets = (tuplet,)

        # And set this new duration on the note.
        note.duration = duration

#         newQuarterLength: HumNum = opFrac(note.duration.quarterLength)
#         if newQuarterLength != originalQuarterLength:
#             raise HumdrumInternalError('_continueTuplet modified duration.quarterLength')

    def _endTuplet(
        self,
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int,
        tupletTemplate: m21.duration.Tuplet,
        tremolo: bool
    ) -> None:
        if tremolo:
            tokenIdx = HumdrumFile._findStartOfTremolo(layerData, tokenIdx)
        endToken: HumdrumToken | FakeRestToken = layerData[tokenIdx]
        if endToken.isFakeRest:
            return

        if t.TYPE_CHECKING:
            # We know because endToken.isFakeRest is False
            assert isinstance(endToken, HumdrumToken)

        endNote: m21.Music21Object | None = endToken.getValueM21Object(
            'music21',
            'generalNote'
        )
        if not isinstance(endNote, m21.note.GeneralNote):
            raise HumdrumInternalError(
                f'no note/chord/rest at end of tuplet (endToken = {endToken})'
            )

        # remember the original duration value, so we can do a debug check at the end
        # to make sure it didn't change (things like changing actual number from 6 to 3
        # are tricky, so we need to check our work).
#         originalQuarterLength: HumNum = opFrac(endNote.duration.quarterLength)

        if tremolo:
            newNoteDuration: m21.duration.Duration | None = None
            tremoloNoteVisualDuration: HumNum | None = None
            tremoloNoteGesturalDuration: HumNum | None = None

            # TODO: this code is very like the tremolo code in _convertRhythm/_startTuplet.
            # TODO: have one copy of this code.
            recipStr: str | None = None
            if endToken.getValueBool('auto', 'startTremolo'):
                recipStr = endToken.getValue('auto', 'recip')
                if recipStr:
                    tremoloNoteVisualDuration = Convert.recipToDuration(recipStr)
            elif endToken.getValueBool('auto', 'startTremolo2') or \
                    endToken.getValueBool('auto', 'tremoloAux'):
                # In two note tremolos, the two notes each look like they have the full duration
                # of the tremolo sequence, but they actually each need to have half that duration
                # internally, for the measure duration to make sense.
                recipStr = endToken.getValue('auto', 'recip')
                if recipStr:
                    tremoloNoteVisualDuration = Convert.recipToDuration(recipStr)
                    tremoloNoteGesturalDuration = opFrac(tremoloNoteVisualDuration / opFrac(2))

            if tremoloNoteVisualDuration is not None:
                newNoteDuration = m21.duration.Duration()
                newNoteDuration.quarterLength = tremoloNoteVisualDuration
                if tremoloNoteGesturalDuration is not None:
                    newNoteDuration.linked = False  # leave the note looking like visual duration
                    newNoteDuration.quarterLength = tremoloNoteGesturalDuration
                endNote.duration = newNoteDuration

        duration: m21.duration.Duration = copy.deepcopy(endNote.duration)
        tuplet: m21.duration.Tuplet | None = None

        if tremolo:
            if duration.tuplets:
                tuplet = copy.deepcopy(duration.tuplets[0])  # it's already computed from recip
        else:
            tuplet = copy.deepcopy(tupletTemplate)

        # We may need to compute a new duration from scratch, now that we have the tuplet
        # details.  This is because sometimes music21 doesn't give us a duration we like.
        # For example, Humdrum data might describe a 5-in-the-place-of-6-sixteenth-note-tuplet,
        # and music21 (given only the duration: 3/40 of a whole note) will call that a
        # 5-in-the-place-of-4-dotted-sixteenth-note-tuplet.  Humdrum knows different, because
        # the recip data is very clear: '40%3' == no dots.  music21 will also describe what
        # Humdrum says is a dotted eighth note in a triplet, as a straight eighth note, with no
        # tuplet at all.  Same deal, we know better, so we compute a new duration from scratch,
        # with our tuplet template as a guide.

        # Note that "if tremolo", we've already recomputed the duration, so don't bother here.
        recomputeDuration: bool = False
        if tuplet and not tremolo:
            if duration.tuplets in (None, ()):
                recomputeDuration = True
            elif len(duration.tuplets) > 1:
                recomputeDuration = True
            elif duration.tuplets[0].durationNormal != tuplet.durationNormal:
                recomputeDuration = True
            elif duration.tuplets[0].tupletMultiplier() != tuplet.tupletMultiplier():
                recomputeDuration = True

            if recomputeDuration:
                duration = M21Convert.m21DurationWithTuplet(
                    endToken, tuplet, self.acceptSyntaxErrors
                )
                tuplet = duration.tuplets[0]

        if tuplet:
            # Now set the tuplet in the duration to this one
            tuplet.type = 'stop'
            if not recomputeDuration:
                duration.tuplets = (tuplet,)

        # And set this new duration on the endNote.
        endNote.duration = duration

#         newQuarterLength: HumNum = opFrac(endNote.duration.quarterLength)
#         if newQuarterLength != originalQuarterLength:
#             raise HumdrumInternalError('_endTuplet modified duration.quarterLength')

    '''
    //////////////////////////////
    //
    // HumdrumInput::setBeamDirection -- Set a beam up or down.
    '''
    @staticmethod
    def _setBeamDirection(
        direction: int,
        tgs: list[HumdrumBeamAndTuplet | None],
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int,
        isGrace: bool
    ) -> None:
        upOrDown: str = ''
        if direction == 1:
            upOrDown = 'up'
        elif direction == -1:
            upOrDown = 'down'

        tg: HumdrumBeamAndTuplet | None = tgs[tokenIdx]
        if t.TYPE_CHECKING:
            # we have completely filled in tgs by now
            assert isinstance(tg, HumdrumBeamAndTuplet)

        beamStart: int = tg.beamStart
        if isGrace:
            beamStart = tg.gbeamStart

        for i in range(tokenIdx, len(layerData)):
            tgi: HumdrumBeamAndTuplet | None = tgs[i]
            if t.TYPE_CHECKING:
                # we have completely filled in tgs by now
                assert isinstance(tgi, HumdrumBeamAndTuplet)

            beamEnd: int = tgi.beamEnd
            if isGrace:
                beamEnd = tgi.gbeamEnd

            token: HumdrumToken | FakeRestToken = layerData[i]
            if token.isFakeRest:
                continue

            if t.TYPE_CHECKING:
                # because token.isFakeRest is False
                assert isinstance(token, HumdrumToken)

            if not token.isData:
                continue
            if token.isNull:
                continue
            if token.isRest:
                # not adding stem direction to rests
                continue
            if token.duration == 0 and not isGrace:
                # ignore grace note beams (if not a grace note)
                continue
            if token.duration != 0 and isGrace:
                # ignore non-grace note beams (if a grace note)
                continue

            # do it (directly to the music21 note or chord)
            # set stem.dir on the token if the note/chord has not yet been created)
            obj: m21.Music21Object | None = token.getValueM21Object('music21', 'generalNote')
            if not obj:
                # no durational object; set it on the token
                token.setValue('auto', 'stem.dir', str(direction))
            else:
                if not isinstance(obj, (m21.note.Note, m21.chord.ChordBase, m21.note.Unpitched)):
                    continue  # it's not a note/chord, no stem direction needed

                if upOrDown:
                    obj.stemDirection = upOrDown
                    if isinstance(obj, m21.chord.ChordBase):
                        for note in obj.notes:
                            note.stemDirection = upOrDown

            if beamEnd == beamStart:
                # last note of beam so exit
                break

    '''
    //////////////////////////////
    //
    // HumdrumInput::storeBreaksec -- Look for cases where sub-beams are broken.
    '''
    @staticmethod
    def _storeSecondaryBreakBeamCount(
        beamState: list[int],
        beamNums: list[int],
        layerData: list[HumdrumToken | FakeRestToken],
        isGrace: bool = False
    ) -> None:
        # a list of "beams", each of which is actually a list of the note indices in that beam
        beamedNotes: list[list[int]] = []

        # the beam number of the "beam" list we are currently filling in
        bnum: int = 0

        for i, layerTok in enumerate(layerData):
            if beamNums[i] == 0:
                # not in a beam
                continue
            if isinstance(layerTok, FakeRestToken):
                # a fake invisible rest we inserted to fill a gap (not from the original file)
                continue
            if not layerTok.isData:
                # not a note or rest in the beam
                continue
            if layerTok.isNull:
                # shouldn't happen, but just in case.
                continue
            if not isGrace and layerTok.isGrace:
                # layerTok is a grace note but we're analyzing non-grace-note beams
                continue
            if isGrace and not layerTok.isGrace:
                # layerTok is not a grace note, but we're analyzing grace note beams
                continue

            if bnum != beamNums[i]:
                # create a new list of notes (indices)
                beamedNotes.append([])
                bnum = beamNums[i]

            beamedNotes[-1].append(i)

        for beamNotes in beamedNotes:
            for j in range(1, len(beamNotes) - 1):
                index1: int = beamNotes[j - 1]
                index2: int = beamNotes[j]
                index3: int = beamNotes[j + 1]
                bcount1: int = beamState[index1]
                bcount2: int = beamState[index2]
                bcount3: int = beamState[index3]

                # Is our beam count less than both the previous and next beam count?
                # Then we need to note in the token that a secondary break has occurred.
                # The value stored should be the (smaller) beam count of this token.
                if bcount2 < bcount1 and bcount2 < bcount3:
                    # mark a secondary break for the given note/chord/rest.
                    layerData[index2].setValue('auto', 'breakBeamCount', str(bcount2))

    '''
    //////////////////////////////
    //
    // HumdrumInput::analyzeLayerBeams --
    '''
    def _analyzeLayerBeams(
        self,
        beamNums: list[int],
        gbeamNums: list[int],
        layerData: list[HumdrumToken | FakeRestToken]
    ) -> None:
        beamState: list[int] = [0] * len(layerData)
        gbeamState: list[int] = [0] * len(layerData)  # for grace notes
        didBeamStateGoNegative: bool = False
        didGBeamStateGoNegative: bool = False
        lastBeamState: int = 0
        lastGBeamState: int = 0

        for i, layerTok in enumerate(layerData):
            if isinstance(layerTok, FakeRestToken):
                beamState[i] = lastBeamState
                gbeamState[i] = lastGBeamState
                continue

            if not layerTok.isData:
                beamState[i] = lastBeamState
                gbeamState[i] = lastGBeamState
                continue

            if layerTok.isNull:
                # shouldn't get to this state
                beamState[i] = lastBeamState
                gbeamState[i] = lastGBeamState
                continue

            # layerTok is non-null data

            # why count 'L' and 'J'?  We're supporting lazy beaming after all,
            # so this is not a reliable source of "number of beams" (duration is).
            # Well, the only thing we can see here is if the Humdrum author wants
            # a secondary break in the beams, by lowering the number of beams
            # briefly, to _not_ match the duration.  We also check here that
            # 'L's and 'J's are matched within the measure (lazy or not, you gotta
            # make them match).
            if layerTok.isGrace:
                gbeamState[i] = layerTok.text.count('L')
                gbeamState[i] -= layerTok.text.count('J')
                lastGBeamState = gbeamState[i]
            else:
                beamState[i] = layerTok.text.count('L')
                beamState[i] -= layerTok.text.count('J')
                lastBeamState = beamState[i]

            if i > 0:
                beamState[i] += beamState[i - 1]
                gbeamState[i] += gbeamState[i - 1]
                lastBeamState = beamState[i]
                lastGBeamState = gbeamState[i]

            if beamState[i] < 0:
                didBeamStateGoNegative = True
            if gbeamState[i] < 0:
                didGBeamStateGoNegative = True  # BUGFIX: didBeam -> didGBeam

        # Convert to beam enumerations.  Beamstates are nonzero for the
        # notes in a beam, but the last one is zero.

        # don't replace the caller's list with an empty list; empty the caller's list
        beamNums.clear()
        bcounter: int = 1
        for i, bstate in enumerate(beamState):
            if bstate != 0:
                beamNums.append(bcounter)
            elif i > 0 and beamState[i - 1] != 0:
                beamNums.append(bcounter)
                bcounter += 1
            else:
                beamNums.append(0)

        # don't replace the caller's list with an empty list; empty the caller's list
        gbeamNums.clear()
        bcounter = 1
        for i, gbstate in enumerate(gbeamState):
            if gbstate != 0:
                gbeamNums.append(bcounter)
            elif i > 0 and gbeamState[i - 1] != 0:
                gbeamNums.append(bcounter)
                bcounter += 1
            else:
                gbeamNums.append(0)

        if didBeamStateGoNegative or beamState[-1] != 0:
            # something wrong with the beaming, either incorrect or
            # the beaming crosses a barline or layer.  Don't try to
            # beam anything.
            beamState = [0] * len(beamState)   # local, so we can replace
            for i in range(0, len(beamNums)):  # non-local, we must modify in place
                beamNums[i] = 0

        if didGBeamStateGoNegative or gbeamState[-1] != 0:
            # something wrong with the gracenote beaming, either incorrect or
            # the beaming crosses a barline or layer.  Don't try to
            # beam anything.
            gbeamState = [0] * len(gbeamState)  # local, so we can replace
            for i in range(0, len(gbeamNums)):  # non-local, we must modify in place
                gbeamNums[i] = 0

        # Do any of the beams or gbeams have secondary breaks?  If so,
        # store the number of beams that remain during that break in the
        # token for use later, when adding beams to the notes.
        self._storeSecondaryBreakBeamCount(beamState, beamNums, layerData)
        self._storeSecondaryBreakBeamCount(gbeamState, gbeamNums, layerData, True)

    '''
    //////////////////////////////
    //
    // HumdrumInput::prepareBeamAndTupletGroups -- Calculate beam and tuplet
    //     groupings for a layer.
    '''
    def _prepareBeamAndTupletGroups(self,
        layerData: list[HumdrumToken | FakeRestToken]
    ) -> list[HumdrumBeamAndTuplet]:
        beamNums: list[int] = []
        gbeamNums: list[int] = []
        self._analyzeLayerBeams(beamNums, gbeamNums, layerData)

        tgs: list[HumdrumBeamAndTuplet] = []

        # duritems == a list of items in the layer which have duration.
        # Grace notes, barlines, interpretations, local comments, global comments,
        # FakeRestTokens, etc. are filtered out for the analysis.
        durItems: list[HumdrumToken] = []

        # indexmapping == mapping from a duritem index to a layerdata index.
        indexMapping: list[int] = []

        # indexmapping2 == mapping from a layerdata index to a duritem index,
        # with -1 meaning no mapping.
        indexMapping2: list[int] = []

        # durbeamnum == beam numbers for durational items only.
        durBeamNums: list[int] = []

        # Extract a list of the layer items that have duration:
        for i, layerTok in enumerate(layerData):
            if layerTok.isFakeRest:
                indexMapping2.append(-1)
                continue

            if t.TYPE_CHECKING:
                assert isinstance(layerTok, HumdrumToken)

            if not layerTok.isData:
                indexMapping2.append(-1)
                continue
            if layerTok.isNull or layerTok.isGrace:
                indexMapping2.append(-1)
                continue

            # don't consider notes without durations
            dur: HumNum = Convert.recipToDuration(layerTok.text)
            if dur == 0:
                indexMapping2.append(-1)
                continue

            indexMapping.append(i)
            indexMapping2.append(len(indexMapping) - 1)
            durItems.append(layerTok)
            durBeamNums.append(beamNums[i])

        # poweroftwo == keeps track whether durations are based on a power
        # (non-tuplet) or not (tuplet).  Notes/rests with false poweroftwo
        # will be grouped into tuplets.
        isPowerOfTwoWithoutDots: list[bool] = [True] * len(durItems)
        hasTuplet: bool = False
        dotlessDur: list[HumNum] = [-1.0] * len(durItems)

        # durationwithdots == full duration of the note/rest including augmentation dots.
        durationWithDots: list[HumNum] = [-1.0] * len(durItems)

        # dursum = a cumulative sum of the full durs, starting at 0 for
        # the first index.
        durSum: list[HumNum] = [0.0] * len(durItems)

        sumSoFar: HumNum = opFrac(0)
        for i, durItem in enumerate(durItems):
            durNoDots: HumNum = durItem.durationNoDots
            dotlessDur[i] = opFrac(durNoDots / opFrac(4))
            isPowerOfTwoWithoutDots[i] = M21Utilities.isPowerOfTwo(durNoDots)
            hasTuplet = hasTuplet or not isPowerOfTwoWithoutDots[i]
            durationWithDots[i] = durItem.duration
            durSum[i] = sumSoFar
            sumSoFar = opFrac(sumSoFar + durItem.duration)

        # Count the number of beams.  The durbeamnum std::vector contains a list
        # of beam numbers starting from 1 (or 0 if a note/rest has no beam).
        beamCount: int = 0
        for durBeamNum in durBeamNums:
            beamCount = max(beamCount, durBeamNum)

        # beamstarts and beamends are lists of the starting and ending
        # index for beams of duration items in the layer.  The index is
        # into the durlist std::vector (list of items which posses duration).
        beamStarts: list[int] = [-1] * beamCount
        beamEnds: list[int] = [0] * beamCount
        for i, durBeamNum in enumerate(durBeamNums):
            if durBeamNum > 0:
                if beamStarts[durBeamNum - 1] < 0:
                    beamStarts[durBeamNum - 1] = i
                beamEnds[durBeamNum - 1] = i

        # beamstartboolean == starting of a beam on a particular note
        # beamendboolean == ending of a beam on a particular note
        beamStartBoolean: list[int] = [0] * len(durBeamNums)
        beamEndBoolean: list[int] = [0] * len(durBeamNums)
        for i in range(0, len(beamStarts)):
            beamStartBoolean[beamStarts[i]] = i + 1
            beamEndBoolean[beamEnds[i]] = i + 1

        # Calculate grace note beam starts and ends.
        # Presuming no clef changes, etc. found between notes in
        # a gracenote beam.  Generalize further if so.
        # gbeamstart == boolean for starting of a grace note beam
        # gbeamend == boolean ending of a grace note beam
        gbeamStarts: list[int] = [0] * len(layerData)
        gbeamEnds: list[int] = [0] * len(layerData)
        gState: list[int] = [0] * len(layerData)

        for i, gbeamNum in enumerate(gbeamNums):
            if gbeamNum == 0:
                continue
            if gState[gbeamNum] != 0:
                continue
            gState[gbeamNum] = 1
            gbeamStarts[i] = gbeamNum

        gState = [0] * len(layerData)
        for i, gbeamNum in reversed(list(enumerate(gbeamNums))):
            if gbeamNum == 0:
                continue
            if gState[gbeamNum] != 0:
                continue
            gState[gbeamNum] = 1
            gbeamEnds[i] = gbeamNum

        if not hasTuplet:
            # we're done, close up and call it a day
            for i in range(0, len(layerData)):
                newtg: HumdrumBeamAndTuplet = HumdrumBeamAndTuplet()
                tgs.append(newtg)
                newtg.token = layerData[i]
                newtg.gbeamStart = gbeamStarts[i]
                newtg.gbeamEnd = gbeamEnds[i]
                if indexMapping2[i] < 0:
                    continue

                newtg.beamStart = beamStartBoolean[indexMapping2[i]]
                newtg.beamEnd = beamEndBoolean[indexMapping2[i]]
            return tgs

        # hasTuplet == True

        # beamdur = a list of the durations for each beam
        beamDurs: list[HumNum] = [-1.0] * len(beamStarts)
        for i in range(0, len(beamDurs)):
            beamDurs[i] = opFrac((durSum[beamEnds[i]] - durSum[beamStarts[i]])
                            + durationWithDots[beamEnds[i]])

        # beampowdot == the number of augmentation dots on a power of two for
        # the duration of the beam.  -1 means could not be made power of two with
        # dots.
        beamPowDots: list[int] = [-1] * len(beamStarts)
        for i, beamDur in enumerate(beamDurs):
            beamPowDots[i] = self._getNumDotsForPowerOfTwo(beamDur)

        binaryBeams: list[bool] = [False] * len(beamStarts)
        for i, beamStart in enumerate(beamStarts):
            if isPowerOfTwoWithoutDots[beamStart]:
                binaryBeams[i] = True

        # Assume that tuplet beams that can fit into a power of two will form
        # a tuplet group.  Perhaps bias towards beampowdot being 0, and try to
        # beam groups to include non-beamed tuplets into lower powdots.
        # Should check that the factors of notes in the beam group all match...
        tupletGroups: list[int] = [0] * len(durItems)

        # durforce: boolean for if a tuplet has been forced to be started or
        # stopped on the current note.
        durForce: list[bool] = [False] * len(durItems)

        # tupletDurs: actual duration of tuplet that starts on this note
        tupletDurs: list[HumNum | None] = [None] * len(durItems)

        # actual DurationTuple of the tuplet (type='eighth', dots=0, qL=0.5)
        durationTupleNormal: list[m21.duration.DurationTuple | None] = (
            [None] * len(durItems)
        )

        tupletNum: int = 1
        skipToI: int = -1
        for i in range(0, len(durItems)):
            if i < skipToI:
                continue

            if isPowerOfTwoWithoutDots[i]:
                # not a tuplet
                continue

            # At a tuplet start.
            starting = i

            # Search for the end.
            ending: int = len(durItems) - 1
            groupDur: HumNum = opFrac(0)

            forcedTupletDuration: HumNum | None = None
            rparam: str = durItems[starting].layoutParameter('TUP', 'r')
            if rparam:
                forcedTupletDuration = Convert.recipToDuration(rparam)

            if forcedTupletDuration is None:
                # Recommendation: if you use LO:TUP:num, also specify LO:TUP:r, to be explicit.
                endIndex: int | None = self._findTupletEndByBeamWithDottedPow2Duration(
                    starting, beamStarts, beamEnds,
                    beamPowDots, isPowerOfTwoWithoutDots
                )
                if endIndex is not None:
                    ending = endIndex

                    # create a new tuplet group
                    groupDur = opFrac(0)
                    for j in range(starting, ending + 1):  # starting through ending
                        tupletGroups[j] = tupletNum
                        groupDur = opFrac(groupDur + durationWithDots[j])
                    tupletDurs[starting] = groupDur
                    tupletNum += 1
                    skipToI = ending + 1
                    continue

            groupDur = durationWithDots[starting]
            for j in range(starting + 1, len(durItems)):
                if isPowerOfTwoWithoutDots[j]:
                    # if note j is not a tuplet note, we have to stop at j - 1
                    ending = j - 1
                    break

                if self._checkForTupletForcedBreak(durItems, j):
                    # force a tuplet break
                    ending = j - 1
                    durForce[starting] = True
                    durForce[ending] = True
                    break

                # The rest of these are based on group duration so far.
                groupDur = opFrac(groupDur + durationWithDots[j])

                if forcedTupletDuration is not None and groupDur >= forcedTupletDuration:
                    ending = j
                    durForce[starting] = True
                    durForce[ending] = True
                    break

                if forcedTupletDuration is None:
                    if M21Utilities.isPowerOfTwo(groupDur):
                        ending = j
                        break

            # create a new tuplet group
            for j in range(starting, ending + 1):  # starting through ending
                tupletGroups[j] = tupletNum
            tupletDurs[starting] = groupDur
            tupletNum += 1
            skipToI = ending + 1

        # tupletstartboolean == starting of a tuplet group
        # tupletendboolean == ending of a tuplet group
        tupletStartBoolean: list[int] = [0] * len(tupletGroups)
        tupletEndBoolean: list[int] = [0] * len(tupletGroups)
        tstart: list[bool] = [False] * len(tupletGroups)
        tend: list[bool] = [False] * len(tupletGroups)

        # forward loop over tupletGroups
        for i, tupletGroup in enumerate(tupletGroups):
            if tupletGroup == 0:
                continue
            if not tstart[tupletGroup - 1]:
                tupletStartBoolean[i] = tupletGroup
                tstart[tupletGroup - 1] = True

        # backward loop over tupletGroups
        for i, tupletGroup in reversed(list(enumerate(tupletGroups))):
            if tupletGroup == 0:
                continue
            if not tend[tupletGroup - 1]:
                tupletEndBoolean[i] = tupletGroup
                tend[tupletGroup - 1] = True

        # figure out tuplet ratio (numNotesActual and numNotesNormal, e.g. 3 and 2)
        # for each note in the tuplet.  Since we are not looking at actual note duration
        # here (just the ratio of dotless note duration to next power of two), this is
        # a really good way of triggering the final splits of tuplet groups if they have
        # different ratios in different portions of the group.
        numNotesActual: list[int] = [-1] * len(tupletGroups)
        numNotesNormal: list[int] = [-1] * len(tupletGroups)
        tupletMultiplier: list[HumNum] = [opFrac(1)] * len(tupletGroups)
        for i, tupletGroup in enumerate(tupletGroups):
            if tupletGroup == 0:
                continue

            nextPowOfTwo: HumNum
            if dotlessDur[i] < 1:
                nextPowOfTwo = self._nextHigherPowerOfTwo(dotlessDur[i])
            else:
                quotient: float = float(numNotesActual[i]) / float(numNotesNormal[i])
                iQuotient: int = int(quotient)
                nextPowOfTwo = opFrac(self._nextLowerPowerOfTwo(iQuotient))

            dotlessDurFraction: Fraction = Fraction(dotlessDur[i])
            if (dotlessDurFraction.numerator == 3
                    and M21Utilities.isPowerOfTwo(dotlessDurFraction.denominator)):
                # correction for duplets
                nextPowOfTwo = opFrac(nextPowOfTwo / opFrac(2))

            tupletMultiplier[i] = opFrac(dotlessDur[i] / nextPowOfTwo)

            tupletMultiplierFraction: Fraction = Fraction(tupletMultiplier[i])

            numNotesActual[i] = tupletMultiplierFraction.denominator
            numNotesNormal[i] = tupletMultiplierFraction.numerator

            # Reference tuplet breve to breve rather than whole.
            if dotlessDurFraction.numerator == 4 and dotlessDurFraction.denominator == 3:
                numNotesNormal[i] = 2
                tupletMultiplier[i] = opFrac(Fraction(2, tupletMultiplierFraction.denominator))

        # adjust tupletgroups based on tuplet ratio changes
        correction: int = 0
        for i in range(1, len(tupletGroups)):
            if numNotesActual[i] == 1 and numNotesNormal[i] == 1:
                continue
            if numNotesActual[i] == -1 and numNotesNormal[i] == -1:
                continue
            if numNotesActual[i - 1] == 1 and numNotesNormal[i - 1] == 1:
                continue
            if numNotesActual[i - 1] == -1 and numNotesNormal[i - 1] == -1:
                continue

            if (numNotesActual[i] != numNotesActual[i - 1]
                    or numNotesNormal[i] != numNotesNormal[i - 1]):
                if tupletGroups[i] == tupletGroups[i - 1]:
                    correction += 1
                    tupletStartBoolean[i] = tupletGroups[i] + correction
                    tupletEndBoolean[i - 1] = tupletGroups[i]
            tupletGroups[i] += correction

        # Change those -1s to 1s, I'm guessing. --gregc
        for i in range(0, len(numNotesActual)):
            if numNotesActual[i] < 0:
                numNotesActual[i] = -numNotesActual[i]

        haveGoodDurationNormal: bool = False
        for i in range(0, len(durItems)):
            if tupletDurs[i] is None:
                durationTupleNormal[i] = None
                continue
            tupletDursI = tupletDurs[i]
            if t.TYPE_CHECKING:
                assert tupletDursI is not None
            durTuple: m21.duration.DurationTuple = (
                m21.duration.durationTupleFromQuarterLength(
                    tupletDursI / opFrac(numNotesNormal[i]))
            )
            durationTupleNormal[i] = durTuple
            if durTuple.type == 'inexpressible':
                # It must be a partial tuplet: tupletDurs[i] is only part of the full tuplet
                # duration. This seems like a mal-notation to me:
                # see Palestrina/Benedictus_66_b_002.krn measure 56 (tenor part), for an example.
                # The piece is in 4/2, and there are half-note triplets (tuplet duration is a
                # whole note) everywhere.  In this measure (tenor part) we see two triplet half
                # notes followed by a whole note, followed by one triplet half note.  To fix the
                # mal-notation, I would have replaced the whole note with three triplet half
                # notes, all tied together.  Then the first of those would be the third note of
                # the first triplet, and the last two of those would be the first two notes of
                # the second triplet.  Alternatively, this piece really seems to be better notated
                # as one triplet of whole notes per measure (duration of triplet == breve). I would
                # note that C++ code renders this measure weirdly, by putting a triplet bracket
                # around the first two notes, and another "around" the last note. But we need to
                # work around it, since the partial duration causes an inexpressible duration
                # and music21 really hates that. The workaround below seems OK, but the end result
                # from export to MusicXML (or perhaps from the render by Musescore) adds rests to
                # the tuplets to get them to be full duration. And that's even more wrong than what
                # C++ code does, since it makes the measure too long.
                # Workaround:
                # Let's see if the partial duration is 1/N or 2/N or 3/N... of a reasonable tuplet
                # duration, where N is numNotesActual.  For example, for a triplet (numNotesActual
                # is 3), see if the partial duration is 1/3 or 2/3 of a reasonable tuplet duration.
                # A reasonable tuplet duration is (first) a power-of-two duration, and (next) a
                # dotted power-of-two duration.

                # try (first) for power of two full tuplet duration
                proposedTupletDur: HumNum
                for numNotes in reversed(range(1, numNotesActual[i])):
                    proposedTupletDur = opFrac(
                        tupletDursI / opFrac(Fraction(numNotes, numNotesActual[i]))
                    )
                    if M21Utilities.isPowerOfTwo(proposedTupletDur):
                        durationTupleNormal[i] = m21.duration.durationTupleFromQuarterLength(
                            proposedTupletDur
                        )
                        haveGoodDurationNormal = True
                        break

                if haveGoodDurationNormal:
                    continue

                # try (next) for single-dotted power of two full tuplet duration
                for numNotes in reversed(range(1, numNotesActual[i])):
                    proposedTupletDur = opFrac(
                        tupletDursI / opFrac(Fraction(numNotes, numNotesActual[i]))
                    )
                    tupletDurWithoutSingleDot: HumNum = opFrac(
                        proposedTupletDur / opFrac(Fraction(3, 2))
                    )
                    if M21Utilities.isPowerOfTwo(tupletDurWithoutSingleDot):
                        durationTupleNormal[i] = m21.duration.durationTupleFromQuarterLength(
                            proposedTupletDur
                        )
                        haveGoodDurationNormal = True
                        break

                if haveGoodDurationNormal:
                    continue

                # try (next) for double-dotted power of two full tuplet duration
                for numNotes in reversed(range(1, numNotesActual[i])):
                    proposedTupletDur = opFrac(
                        tupletDursI / opFrac(Fraction(numNotes, numNotesActual[i]))
                    )
                    tupletDurWithoutDoubleDot: HumNum = opFrac(
                        proposedTupletDur / opFrac(Fraction(7, 4))
                    )
                    if M21Utilities.isPowerOfTwo(tupletDurWithoutDoubleDot):
                        durationTupleNormal[i] = m21.duration.durationTupleFromQuarterLength(
                            proposedTupletDur
                        )
                        haveGoodDurationNormal = True
                        break

                if haveGoodDurationNormal:
                    continue

                # try (next) for triple-dotted power of two full tuplet duration
                for numNotes in reversed(range(1, numNotesActual[i])):
                    proposedTupletDur = opFrac(
                        tupletDursI / opFrac(Fraction(numNotes, numNotesActual[i]))
                    )
                    tupletDurWithoutTripleDot: HumNum = opFrac(
                        proposedTupletDur / opFrac(Fraction(15, 8))
                    )
                    if M21Utilities.isPowerOfTwo(tupletDurWithoutTripleDot):
                        durationTupleNormal[i] = m21.duration.durationTupleFromQuarterLength(
                            proposedTupletDur
                        )
                        haveGoodDurationNormal = True
                        break

        # At this point, if we see a durationTuple.type='inexpressible', we will
        # simply split that tuplet apart into it's constituent notes, making
        # each of those notes a tuplet in its own right, recomputing its durationTuple
        # on the fly (but using the tuplet's tupletMultiplier for all the new one-note
        # tuplets).

        tgs = []
        for i, layerTok in enumerate(layerData):
            new_tg: HumdrumBeamAndTuplet = HumdrumBeamAndTuplet()
            tgs.append(new_tg)
            new_tg.token = layerTok
            if indexMapping2[i] < 0:
                # this is a non-durational layer item or a non-tuplet note
                new_tg.duration = opFrac(0)
                new_tg.durationNoDots = opFrac(0)
                new_tg.beamStart = 0
                new_tg.beamEnd = 0
                new_tg.gbeamStart = gbeamStarts[i]
                new_tg.gbeamEnd = gbeamEnds[i]
                new_tg.tupletStart = 0
                new_tg.tupletEnd = 0
                new_tg.group = -1
                new_tg.numNotesActual = -1
                new_tg.numNotesNormal = -1
                new_tg.tupletMultiplier = opFrac(1)
                new_tg.durationTupleNormal = None
                new_tg.forceStartStop = False
            else:
                if t.TYPE_CHECKING:
                    # because FakeRestTokens end up with indexMapping2[i] < 0
                    assert isinstance(layerTok, HumdrumToken)
                # this is a tuplet note (with duration)
                new_tg.duration = layerTok.duration
                new_tg.durationNoDots = layerTok.durationNoDots
                new_tg.beamStart = beamStartBoolean[indexMapping2[i]]
                new_tg.beamEnd = beamEndBoolean[indexMapping2[i]]
                new_tg.gbeamStart = gbeamStarts[i]
                new_tg.gbeamEnd = gbeamEnds[i]
                new_tg.tupletStart = tupletStartBoolean[indexMapping2[i]]
                new_tg.tupletEnd = tupletEndBoolean[indexMapping2[i]]
                new_tg.group = tupletGroups[indexMapping2[i]]
                new_tg.numNotesActual = numNotesActual[indexMapping2[i]]
                new_tg.numNotesNormal = numNotesNormal[indexMapping2[i]]
                new_tg.tupletMultiplier = tupletMultiplier[indexMapping2[i]]
                new_tg.durationTupleNormal = durationTupleNormal[indexMapping2[i]]
                new_tg.forceStartStop = durForce[indexMapping2[i]]

        # Renumber tuplet groups in sequence (otherwise the mergeTupletsCuttingBeam()
        # function will delete the 1st group if it is not the first tuplet.
        tcounter: int = 0
        for tg in tgs:
            if t.TYPE_CHECKING:
                # tgs has been filled in completely
                assert isinstance(tg, HumdrumBeamAndTuplet)
            if tg.tupletStart:
                tcounter += 1
                tg.tupletStart = tcounter
            elif tg.tupletEnd:
                tg.tupletEnd = tcounter

        self._mergeTupletsCuttingBeam(tgs)
#        self._resolveTupletBeamTie(tgs) # this is MEI-specific; music21 doesn't care

        # music21-specific: tuplet duration must be expressible with powerOfTwo + dots.
        # If it isn't, we have to split it up until it does (worst case, every single
        # note becomes its own tuplet).
        # self._fixTupletsWithInexpressibleDuration(tgs)

        self._assignTupletScalings(tgs)

        # in iohumdrum.cpp this is called after return from prepareBeamAndTupletGroups()
        # self._fixLargeTuplets(tgs)

        return tgs

    '''
    //////////////////////////////
    //
    // HumdrumInput::fixLargeTuplets -- fix triple-breve/triplet-wholenote cases.
    '''
    @staticmethod
    def _fixLargeTuplets(tgs: list[HumdrumBeamAndTuplet]) -> None:
        tgi: HumdrumBeamAndTuplet | None
        tgiPrev1: HumdrumBeamAndTuplet | None
        tgiPrev2: HumdrumBeamAndTuplet | None

        # triplet-whole + triplet-breve cases
        for i in range(1, len(tgs)):
            tgi = tgs[i]
            tgiPrev1 = tgs[i - 1]
            if not (tgi.tupletStart == 2 and tgi.tupletEnd == 1):
                continue
            if tgiPrev1.tupletStart == 1 and tgiPrev1.tupletEnd == 1:
                print('triplet-whole + triplet-breve case', file=sys.stderr)

        # two triplet-halfs + triplet-breve case
        for i in range(2, len(tgs)):
            tgi = tgs[i]
            tgiPrev1 = tgs[i - 1]
            tgiPrev2 = tgs[i - 2]
            if not (tgi.tupletStart == 2 and tgi.tupletEnd == 1):
                continue
            if not (tgiPrev1.tupletStart == 0 and tgiPrev1.tupletEnd == 1):
                continue
            if tgiPrev2.tupletStart == 1 and tgiPrev1.tupletEnd == 0:
                print('two triplet-halfs + triplet-breve case', file=sys.stderr)

        # two triplet-halfs + triplet-breve case + two triplet-halfs
        for i in range(2, len(tgs)):
            tgi = tgs[i]
            tgiPrev1 = tgs[i - 1]
            tgiPrev2 = tgs[i - 2]
            if not (tgi.tupletStart == 0 and tgi.tupletEnd == 2):
                continue
            if not (tgiPrev1.tupletStart == 2 and tgiPrev1 == 0):
                continue
            if tgiPrev2.tupletStart == 1 and tgiPrev2.tupletEnd == 1:
                print('two triplet-halfs + triplet-breve case + two triplet-halfs',
                        file=sys.stderr)

    '''
    //////////////////////////////
    //
    // HumdrumInput::assignTupletScalings --
    '''
    def _assignTupletScalings(self, tgs: list[HumdrumBeamAndTuplet]) -> None:
        maxGroup: int = 0
        for tg in tgs:
            maxGroup = max(maxGroup, tg.group)

        if maxGroup <= 0:
            # no tuplets
            return

        # tggroups contains lists of tuplet-y items (i.e. with group > 0), by group number
        tggroups: list[list[HumdrumBeamAndTuplet]] = []
        for _ in range(0, maxGroup + 1):
            tggroups.append([])

        for tg in tgs:
            if t.TYPE_CHECKING:
                # tgs has been filled in completely
                assert isinstance(tg, HumdrumBeamAndTuplet)
            group: int = tg.group
            if group <= 0:
                continue
            tggroups[group].append(tg)

        for tggroup in tggroups:
            self._assignScalingToTupletGroup(tggroup)  # tggroups[0] is empty, but that's OK

    '''
    //////////////////////////////
    //
    // HumdrumInput::assignScalingToTupletGroup --
    '''
    @staticmethod
    def _assignScalingToTupletGroup(tggroup: list[HumdrumBeamAndTuplet]) -> None:
        if not tggroup:  # tggroup is None or [], so bail out
            return

        firstTokenInGroup: HumdrumToken | FakeRestToken | None = tggroup[0].token
        if t.TYPE_CHECKING:
            # FakeRestTokens/Nones are never in a tggroup
            assert isinstance(firstTokenInGroup, HumdrumToken)

        # Set the Humdrum-specified numNotesActual for the tuplet (if it makes sense).
        scale: Fraction
        num: str = firstTokenInGroup.layoutParameter('TUP', 'num')
        if num:
            numValue: int = int(num)
            if numValue > 0:
                scale = Fraction(num)
                scale /= tggroup[0].numNotesActual
                # if scale is an integer >= 1...
                if scale.denominator == 1 and scale >= 1:
                    for tg in tggroup:
                        tg.numScale = scale.numerator
                    return

        # There was no Humdrum-specified numNotesActual, or it didn't make sense.
        # Initialize all scalings to 1
        for tg in tggroup:
            tg.numScale = 1

        durCounts: dict[HumNum, int] = {}
        for tg in tggroup:
            durNoDots: HumNum = tg.durationNoDots
            if durNoDots in durCounts:
                durCounts[durNoDots] += 1
            else:
                durCounts[durNoDots] = 1

        # check for all notes same duration
        if len(durCounts) == 1:
            # All durations are the same, so set the scale to the multiple of how
            # many of that duration are present. (or to 1, if that doesn't work)
            count: int = list(durCounts.values())[0]  # how many of that duration are present
            scale = Fraction(count) / tggroup[0].numNotesActual
            # if scale is an integer > 1
            if scale.denominator == 1 and scale > 1:
                for tg in tggroup:
                    tg.numScale = scale.numerator

            return

        # check for two durations with the same count
        # Try units = (dur1+dur2) * count
        if len(durCounts) == 2:
            counts: list[int] = list(durCounts.values())
            if counts[0] == counts[1]:
                scale = Fraction(counts[0]) / tggroup[0].numNotesActual
                if scale.denominator == 1 and scale > 1:
                    for tg in tggroup:
                        tg.numScale = scale.numerator
                return

        '''
            This is commented out in iohumdrum.cpp... --gregc

        // Use the most common duration for the tuplet scaling:
        // (this could be refined for dotted durations)
        hum::HumNum maxcountdur = 0;
        int maxcount = 0;
        for (auto it : durcounts) {
            if (it.second > maxcount) {
                maxcount = it.second;
                maxcountdur = it.first;
            }
        }
        '''

        # Try units = totalDur / maxDur
        maxDur: HumNum = opFrac(0)
        for dur in durCounts:
            maxDur = max(maxDur, dur)

        totalDur: HumNum = opFrac(0)
        for tg in tggroup:
            totalDur = opFrac(totalDur + tg.duration)

        # TODO: transformation below should probably happen above as well, but needs testing
        # units: HumNum = totalDur / maxDur
        # if units.denominator == 1 and units > 1:
            # scale: HumNum = units / tggroup[0].numNotesActual
            # if scale.denominator == 1 and scale > 1:
            #     for tg in tggroup:
            #         tg.numScale = scale.numerator
            #     return
        numNotesActual: Fraction = Fraction(totalDur / maxDur)
        numNotesNormal: Fraction = Fraction(numNotesActual * tggroup[0].tupletMultiplier)
        if (numNotesActual.denominator == 1 and numNotesActual > 1
                and numNotesNormal.denominator == 1 and numNotesNormal > 1):
            for tg in tggroup:
                tg.numScale = 1
                tg.numNotesActual = numNotesActual.numerator
                tg.numNotesNormal = numNotesNormal.numerator

    '''
    //////////////////////////////
    //
    // HumdrumInput::mergeTupletsCuttingBeam -- When a tuplet ends on a beamed note,
    //     but it can be continued with another tuplet of the same type, then merge the
    //     two tuplets.  These cases are caused by groupings needed at a higher level
    //     than the beat according to the time signature.
    '''
    @staticmethod
    def _mergeTupletsCuttingBeam(tgs: list[HumdrumBeamAndTuplet]) -> None:
        # newtgs is a list of only durational items, removing things like clefs and barlines.
        # Actually it looks like it only has the tuplet-y items in it. --gregc
        newtgs: list[HumdrumBeamAndTuplet] = []
        for tg in tgs:
            if tg.group >= 0:
                newtgs.append(tg)

        inBeam: list[int] = [0] * len(newtgs)
        for i, tg in enumerate(newtgs):
            if tg.forceStartStop:
                # Don't merge anything
                inBeam[i] = 0
                continue

            if tg.beamStart:
                inBeam[i] = tg.beamStart
                continue

            if tg.beamEnd:
                inBeam[i] = 0   # if you're at the beamEnd, you're not "within" a beam group
                continue

            if i > 0:
                inBeam[i] = inBeam[i - 1]
                continue

            # i == 0 and it's not a beamStart
            inBeam[i] = 0

        for i, tg in enumerate(newtgs):
            if not (inBeam[i] and tg.tupletEnd):
                continue
            # this is a tupletEnd that is within a beam (and not right at the end of the beam)

            if i >= len(newtgs) - 1:
                continue
            if not newtgs[i + 1].tupletStart:
                continue
            if tg.tupletMultiplier != newtgs[i + 1].tupletMultiplier:
                continue
            # and the next note is a tuplet start that qualifies to be in the same tuplet

            # Need to merge adjacent tuplets.
            newNotesActual: int = tg.numNotesActual + newtgs[i + 1].numNotesActual
            newNotesNormal: int = tg.numNotesNormal + newtgs[i + 1].numNotesNormal
            target = tg.tupletEnd
            for j in reversed(range(0, i + 1)):  # i..0 including i
                newtgs[j].numNotesActual = newNotesActual
                newtgs[j].numNotesNormal = newNotesNormal
                if newtgs[j].tupletStart == target:
                    break

            target = newtgs[i + 1].tupletStart
            for j in range(i + 1, len(newtgs)):
                if newtgs[j].group < 0:  # not in the tuplet, why would this happen?
                    continue

                newtgs[j].numNotesActual = newNotesActual
                newtgs[j].numNotesNormal = newNotesNormal
                if not newtgs[j].tupletEnd:
                    continue
                if newtgs[j].tupletEnd == target:
                    break

            tg.tupletEnd = 0
            newtgs[i + 1].tupletStart = 0

            for j in range(i + 2, len(newtgs)):
                if newtgs[j].tupletStart:
                    newtgs[j].tupletStart -= 1
                if newtgs[j].tupletEnd:
                    newtgs[j].tupletEnd -= 1

        # recalculate tuplet groups from new tupletStart and tupletEnd group nums
        currGroup: int = 0
        for tg in newtgs:
            if tg.tupletStart:
                currGroup = tg.tupletStart
            tg.group = currGroup
            if tg.tupletEnd:
                currGroup = 0

        # rather than apply a scaleAdjust (like iohumdrum.cpp does), we make music21
        # happy by realizing that we haven't change the scale at all here, we've just
        # changed the numNotesActual and numNotesNormal (above)

    @staticmethod
    def _fixTupletsWithInexpressibleDuration(tgs: list[HumdrumBeamAndTuplet]) -> None:
        # newtgs is a list of items in tuplets. We need all the tuplets, not just the bad ones,
        # so we can renumber them all.
        newtgs: list[HumdrumBeamAndTuplet] = []
        for tg in tgs:
            if tg.group >= 0:
                newtgs.append(tg)

        inBadTuplet: list[bool] = [False] * len(newtgs)
        currTupletIsBad: bool = False
        badExists: bool = False
        for i, tg in enumerate(newtgs):
            if tg.tupletStart:
                # this is first note in tuplet
                currTupletIsBad = False
                if (tg.durationTupleNormal is not None
                        and tg.durationTupleNormal.type == 'inexpressible'):
                    currTupletIsBad = True
                    badExists = True

            inBadTuplet[i] = currTupletIsBad

        if not badExists:
            return

        for i, tg in enumerate(newtgs):
            # for now, don't try to be too smart, just split the bad tuplets into
            # single-note tuplets
            if not inBadTuplet[i]:
                continue

            # This is a member of a bad tuplet: split it out into its own tuplet.
            tg.durationTupleNormal = m21.duration.durationTupleFromQuarterLength(
                tg.duration * tg.numNotesActual
            )

            tg.tupletStart = 0
            tg.tupletEnd = 0

            for j in range(i + 1, len(newtgs)):
                if newtgs[j].tupletStart:
                    newtgs[j].tupletStart += 1
                if newtgs[j].tupletEnd:
                    newtgs[j].tupletEnd += 1

        # recalculate tuplet groups from new tupletStart and tupletEnd group nums
        currGroup: int = 0
        for tg in newtgs:
            if tg.tupletStart:
                currGroup = tg.tupletStart
            tg.group = currGroup
            if tg.tupletEnd:
                currGroup = 0

    @staticmethod
    def _findTupletEndByBeamWithDottedPow2Duration(
        tupletStartIdx: int,
        beamStarts: list[int],
        beamEnds: list[int],
        beamPowDots: list[int],
        isPowerOfTwoWithoutDots: list[bool]
    ) -> int | None:
        # i is an index into the beams, beamStartIdx/beamEndIdx are indices into durItems
        for i, beamStartIdx in enumerate(beamStarts):
            if beamStartIdx != tupletStartIdx:
                continue

            # we found a beam that starts where the tuplet starts

            # beamPowDot is the number of dots required to make the beam duration into
            # a power of two. If -1, it can't be done.
            if beamPowDots[i] < 0:
                # beam starting at tuplet start doesn't have a (dotted) power-of-two
                # duration, so bail out
                return None

            beamEndIdx: int = beamEnds[i]  # we will return this if all goes well

            for j in range(beamStartIdx, beamEndIdx + 1):  # includes beamEndIdx
                if isPowerOfTwoWithoutDots[j]:
                    # we ran out of tuplet notes before the end of the beam,
                    # so bail out
                    return None

            return beamEndIdx

        return None

    '''
    //////////////////////////////
    //
    // HumdrumInput::checkForTremolo --  Check to see if a beamed group of notes
    //    can be converted into a tremolo. (Decision to convert to tremolo is done
    //    outside of this function and is activated by the *tremolo tandem interpretation).
    '''
    @staticmethod
    def _checkForTremolo(
        layerData: list[HumdrumToken | FakeRestToken],
        tgs: list[HumdrumBeamAndTuplet | None],
        startIdx: int
    ) -> bool:
        tgStart: HumdrumBeamAndTuplet | None = tgs[startIdx]
        if t.TYPE_CHECKING:
            # tgs has been completely filled in
            assert isinstance(tgStart, HumdrumBeamAndTuplet)

        beamNumber: int = tgStart.beamStart
        notes: list[HumdrumToken] = []
        for i in range(startIdx, len(layerData)):
            tgi: HumdrumBeamAndTuplet | None = tgs[i]
            if t.TYPE_CHECKING:
                # tgs has been completely filled in
                assert isinstance(tgi, HumdrumBeamAndTuplet)
            layerTok: HumdrumToken | FakeRestToken = layerData[i]
            if layerTok.isFakeRest:
                continue
            if t.TYPE_CHECKING:
                # We know because layerTok.isFakeRest is False
                assert isinstance(layerTok, HumdrumToken)
            if layerTok.isNote:
                notes.append(layerTok)
            if tgi.beamEnd == beamNumber:
                break

        if not notes:
            return False

        duration: HumNum = notes[0].duration
        if duration == 0:
            return False  # we don't tremolo-ize grace notes

        pitches: list[list[int]] = []
        for _ in range(0, len(notes)):
            pitches.append([])

        for i, note in enumerate(notes):
            # Disallow any tremolo with a tie anywhere except the start token (and disable
            # continue there)
            if '_' in note.text:
                # tie continuation on any note: disallow tremolo
                return False
            if i != 0:
                # start/end tie allowed on first note, but not on any other
                if '[' in note.text or ']' in note.text:
                    return False

            if i > 0:
                if note.duration != duration:
                    # All durations in beam must be the same for a tremolo.
                    # (at least for now).
                    return False

            # Store all notes in chord for comparing in next loop
            for subtok in note.subtokens:
                pitches[i].append(Convert.kernToBase40(subtok))

        # Check for single note tremolo (bowed tremolo)
        nextSame: list[bool] = [True] * len(notes)
        allPitchesEqual: bool = True

        for i in range(1, len(pitches)):
            if len(pitches[i]) != len(pitches[i - 1]):
                allPitchesEqual = False
                nextSame[i - 1] = False
                continue

            # Check if each note in the successive chords is the same.
            # The ordering of notes in each chord is assumed to be the same
            # (i.e., this function is not going to waste time sorting
            # the pitches to check if the chords are equivalent).
            for j in range(0, len(pitches[i])):
                if pitches[i][j] != pitches[i - 1][j]:
                    allPitchesEqual = False
                    nextSame[i - 1] = False

        tdur: HumNum
        recip: str
        slashes: int

        if allPitchesEqual:
            # beam group should be converted into a single note (bowed) tremolo
            tdur = opFrac(duration * len(notes))
            recip = Convert.durationToRecip(tdur)

            slashes = int(math.log(float(duration)) / math.log(2.0))
            noteBeams: int = int(math.log(float(tdur)) / math.log(2.0))
            if noteBeams < 0:
                slashes = slashes - noteBeams
            slashes = -slashes
            if slashes <= 0:
                # something went wrong calculating durations
                return False

            notes[0].setValue('auto', 'startTremolo', '1')
            notes[0].setValue('auto', 'inTremolo', '1')
            notes[0].setValue('auto', 'recip', recip)
            notes[0].setValue('auto', 'slashes', slashes)
            for i in range(1, len(notes)):
                notes[i].setValue('auto', 'inTremolo', '1')
                notes[i].setValue('auto', 'suppress', '1')

            return True

        # Check for multiple bTrem embedded in single beam group.
        # The current requirement is that all subgroups must have the
        # same duration (this requirement can be loosened in the future
        # if necessary).
        hasInternalTrem: bool = True
        for i in range(1, len(nextSame) - 1):
            if nextSame[i]:
                continue
            if not nextSame[i - 1]:
                hasInternalTrem = False
                break
            if not nextSame[i + 1]:
                hasInternalTrem = False
                break
        if len(nextSame) == 2:
            if not nextSame[0] and nextSame[1]:
                hasInternalTrem = False

        # Group separate tremolo groups within a single beam
        groupings: list[list[HumdrumToken | FakeRestToken]] = []
        if hasInternalTrem:
            groupings.append([])
            groupings[-1].append(notes[0])
            for i in range(0, len(notes) - 1):
                if nextSame[i]:
                    groupings[-1].append(notes[i + 1])
                else:
                    groupings.append([])
                    groupings[-1].append(notes[i + 1])

        # Current requirement is that the internal tremolos are power-of-two
        # (deal with dotted internal tremolos as needed in the future).
        allPow2: bool = True
        if hasInternalTrem:
            for grouping in groupings:
                if not M21Utilities.isPowerOfTwo(len(grouping)):
                    allPow2 = False
                    break

        if hasInternalTrem and allPow2:
            # Ready to mark internal single note (bowed) tremolo

            # First suppress printing of all non-primary tremolo notes:
            for grouping in groupings:
                for j in range(1, len(grouping)):
                    grouping[j].setValue('auto', 'inTremolo', '1')
                    grouping[j].setValue('auto', 'suppress', '1')

            # Now add tremolo slash(es) on the first notes.

            for grouping in groupings:
                tdur = opFrac(duration * len(grouping))
                recip = Convert.durationToRecip(tdur)
                slashes = -int(math.log2(float(duration) / float(tdur)))
                grouping[0].setValue('auto', 'startTremolo', '1')
                grouping[0].setValue('auto', 'inTremolo', '1')
                grouping[0].setValue('auto', 'slashes', slashes)
                grouping[0].setValue('auto', 'recip', recip)

            # Preserve the beam on the group of tremolos.  The beam can
            # only be an eighth-note beam for now (this should be the
            # general rule for beamed tremolos).
            groupings[0][0].setValue('auto', 'tremoloBeam', '8')
            groupings[-1][-1].setValue('auto', 'tremoloBeam', '8')

            # returning false in order to keep the beam.
            return False

        # Check for two-note tremolo case.
        # Allowing odd-length sequences (3, 5, 7, etc) which can in theory
        # be represented, but I have not seen such cases.

        if len(pitches) < 3:
            # a two-note tremolo that only lasts one or two notes doesn't make sense.
            return False

        # check to see that all even notes/chords are the same
        for i in range(2, len(pitches)):
            if len(pitches[i]) != len(pitches[i - 2]):
                return False
            # Check if each note in the successive chords is the same.
            # The ordering of notes in each chord is assumed to be the same
            # (i.e., this function is not going to waste time sorting
            # the pitches to check if the chords are equivalent).
            for j in range(0, len(pitches[i])):
                if pitches[i][j] != pitches[i - 2][j]:
                    return False

        # If got to this point, create a two-note/chord tremolo
        tdur = opFrac(duration * len(notes))
        recip = Convert.durationToRecip(tdur)
        unitRecip: str = Convert.durationToRecip(duration)

        # Eventually also allow calculating of beam.float
        # (mostly for styling half note tremolos).
        beams: int = -int(math.log(float(duration)) / math.log(2.0))
        if beams <= 0:
            # something went wrong calculating durations.
            raise HumdrumInternalError(f'Problem with tremolo2 beams calculation: {beams}')

        notes[0].setValue('auto', 'startTremolo2', '1')
        notes[0].setValue('auto', 'inTremolo', '1')
        notes[0].setValue('auto', 'recip', recip)
        notes[0].setValue('auto', 'unit', unitRecip)  # problem if dotted...
        notes[0].setValue('auto', 'beams', beams)

        notes[-1].setValue('auto', 'tremoloAux', '1')
        notes[-1].setValue('auto', 'recip', recip)

        for i in range(1, len(notes)):
            notes[i].setValue('auto', 'inTremolo')
            notes[i].setValue('auto', 'suppress', '1')

        return True

    '''
    //////////////////////////////
    //
    // HumdrumInput::checkForTupletForcedBreak --
    '''
    @staticmethod
    def _checkForTupletForcedBreak(durItems: list[HumdrumToken], index: int) -> bool:
        if index == 0:
            return False

        if index > len(durItems):
            return False

        startTok: HumdrumToken = durItems[index]
        endTok: HumdrumToken = durItems[index - 1]
        stopLine: int = endTok.lineIndex
        curLine: int = startTok.lineIndex
        cur: HumdrumToken | None = startTok.previousToken0

        while cur and curLine > stopLine:
            if cur.isInterpretation and cur.text == '*tupbreak':
                return True
            cur = cur.previousToken0
            if cur is None:
                break
            curLine = cur.lineIndex
            if cur == endTok:
                break

        return False

    '''
    //////////////////////////////
    //
    // HumdrumInput::nextHigherPowerOfTwo -- Use with values between 0 and 1.
    '''
    @staticmethod
    def _nextHigherPowerOfTwo(num: HumNumIn) -> HumNum:
        if num == 0:
            return opFrac(Fraction(1, 1024))
        value: float = math.log(float(num)) / math.log(2.0)
        denom: int = int(-value)
        return opFrac(Fraction(1, int(pow(2.0, denom))))

    '''
    //////////////////////////////
    //
    // HumdrumInput::nextLowerPowerOfTwo -- For integers above 1.
    '''
    @staticmethod
    def _nextLowerPowerOfTwo(num: int) -> int:
        if num < 1:
            return 1

        doOneMore: bool = False
        if num.bit_length() > 32:
            doOneMore = True

        num = num | (num >> 1)
        num = num | (num >> 2)
        num = num | (num >> 4)
        num = num | (num >> 8)
        num = num | (num >> 16)
        if doOneMore:
            num = num | (num >> 32)

        return num - (num >> 1)

    '''
    //////////////////////////////
    //
    // HumdrumInput::getDotPowerOfTwo -- Checks up to 3 augmentation dots.
        What the heck, check for 4 augmentation dots, too.
    '''
    @staticmethod
    def _getNumDotsForPowerOfTwo(value: HumNumIn) -> int:
        val: HumNum = opFrac(value)
        if M21Utilities.isPowerOfTwo(val):
            return 0

        # check for one dot
        tval: HumNum = opFrac(val / opFrac(Fraction(3, 2)))
        if M21Utilities.isPowerOfTwo(tval):
            return 1

        # check for two dots
        tval = opFrac(val / opFrac(Fraction(7, 4)))
        if M21Utilities.isPowerOfTwo(tval):
            return 2

        # check for three dots
        tval = opFrac(val / opFrac(Fraction(15, 8)))
        if M21Utilities.isPowerOfTwo(tval):
            return 3

        # check for four dots
        tval = opFrac(val / opFrac(Fraction(31, 16)))
        if M21Utilities.isPowerOfTwo(tval):
            return 4

        return -1

    '''
        _processBarlinesInLayerData
    '''
    def _processBarlinesInLayerData(
        self,
        measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        track: int,
        layerIndex: int
    ) -> bool:
        insertedIntoVoice: bool = False
        staffIndex: int = self._staffStartsIndexByTrack[track]
        if staffIndex < 0:
            # not a kern/mens spine
            return insertedIntoVoice

        layerData: list[HumdrumToken | FakeRestToken] = (
            self._currentMeasureLayerTokens[staffIndex][layerIndex]
        )
        if not layerData:  # empty layer?!
            return insertedIntoVoice

        currentMeasurePerStaff: list[m21.stream.Measure] = (
            self._allMeasuresPerStaff[measureIndex]
        )

        if layerIndex == 0 and layerData[-1].isBarline:
            endBarline = layerData[-1]
            if t.TYPE_CHECKING:
                # because FakeRestToken.isBarline is always False
                assert isinstance(endBarline, HumdrumToken)

            # check for rptend here, since the one for the last measure in
            # the music is missed by the inline processing.  But maybe limit
            # this one to only checking for the last measure.  Or move barline
            # styling here...
            if ':|' in endBarline.text or ':!' in endBarline.text:
                if currentMeasurePerStaff[staffIndex]:
                    currentMeasurePerStaff[staffIndex].rightBarline = (
                        m21.bar.Repeat(direction='end')
                    )

            if ';' in endBarline.text:  # or ',' in endBarline.text:
                if currentMeasurePerStaff[staffIndex]:
                    if not currentMeasurePerStaff[staffIndex].rightBarline:
                        currentMeasurePerStaff[staffIndex].rightBarline = m21.bar.Barline('normal')
                    if ';' in endBarline.text:
                        self._addFermata(
                            currentMeasurePerStaff[staffIndex].rightBarline, endBarline
                        )
#                     if ',' in endBarline.text:
#                         self._addBreath(
#                             currentMeasurePerStaff[staffIndex].rightBarline, endBarline
#                         )

        # Check for repeat start at beginning of music.  The data for the very
        # first measure starts at the exclusive interpretation so that clefs
        # and time signatures and such are included.  If the first element
        # in the layer is an exclusive interpretation, then search for any
        # starting barline that should be checked for a repeat start.
        # While we're here, also check for any directions associated with
        # that initial barline of the very first measure.  In other measures,
        # that text would be in the previous measure, but there is no previous
        # measure here.
        if layerData[0].isExclusiveInterpretation:
            for layerTok in layerData:
                if layerTok.isFakeRest:
                    # treat layerTok.isFakeRest like layerTok.isData
                    break

                if t.TYPE_CHECKING:
                    # because layerTok.isFakeRest is False
                    assert isinstance(layerTok, HumdrumToken)

                if layerTok.isData:
                    break

                if not layerTok.isBarline:
                    continue

                insertedIntoVoice = (
                    insertedIntoVoice
                    or self._processDirections(
                        measureIndex,
                        voice,
                        voiceOffsetInMeasure,
                        layerTok,
                        staffIndex)
                )

                if '|:' in layerTok.text or '!:' in layerTok.text:
                    if currentMeasurePerStaff[staffIndex]:
                        currentMeasurePerStaff[staffIndex].leftBarline = (
                            m21.bar.Repeat(direction='start')
                        )
                break

        # Check for repeat start at other places besides beginning of music:
        firstTok: HumdrumToken | FakeRestToken = layerData[0]
        if layerIndex == 0 and firstTok.isBarline:
            if t.TYPE_CHECKING:
                # because FakeRestToken.isBarline is always False
                assert isinstance(firstTok, HumdrumToken)

            if '|:' in firstTok.text or '!:' in firstTok.text:
                if currentMeasurePerStaff[staffIndex]:
                    currentMeasurePerStaff[staffIndex].leftBarline = (
                        m21.bar.Repeat(direction='start')
                    )

        lastTok: HumdrumToken | FakeRestToken = layerData[-1]
        if lastTok.isBarline:
            if t.TYPE_CHECKING:
                # because FakeRestToken.isBarline is always False
                assert isinstance(lastTok, HumdrumToken)
            insertedIntoVoice = (
                insertedIntoVoice
                or self._processDirections(
                    measureIndex,
                    voice,
                    voiceOffsetInMeasure,
                    lastTok,
                    staffIndex)
            )

        return insertedIntoVoice

    @staticmethod
    def _getGeneralNoteOrPlaceHolder(token: HumdrumToken) -> m21.note.GeneralNote:
        gnote: m21.Music21Object | None = token.getValueM21Object('music21', 'generalNote')
        if not gnote:
            # gnote may not have been created yet. If so, we will use a
            # placeHolder GeneralNote instead, from which createNote will
            # transfer the spanners, when creating the actual note.  If there
            # isn't already a placeHolder GeneralNote, we will make one here.
            gnote = token.getValueM21Object('music21', 'placeHolder')
            if gnote is None:
                gnote = m21.note.GeneralNote()
                token.setValue('music21', 'placeHolder', gnote)
        if t.TYPE_CHECKING:
            assert isinstance(gnote, m21.note.GeneralNote)
        return gnote

    @staticmethod
    def _createNote(infoHash: HumHash | None = None) -> m21.note.Note:
        # infoHash is generally the token for which the note is being created,
        # but we declare it as a HumHash, since the only thing we read is
        # 'placeHolder'.
        # The actual construction of the note contents from the token is done elsewhere.
        placeHolder: m21.Music21Object | None = None
        if infoHash is not None:
            placeHolder = infoHash.getValueM21Object('music21', 'placeHolder')

        note: m21.note.Note = M21Utilities.createNote(placeHolder)

        if placeHolder is not None and infoHash is not None:
            infoHash.setValue('music21', 'placeHolder', None)

        return note

    @staticmethod
    def _createUnpitched(infoHash: HumHash | None = None) -> m21.note.Unpitched:
        # infoHash is generally the token for which the note is being created,
        # but we declare it as a HumHash, since the only thing we read is
        # 'placeHolder'.
        # The actual construction of the unpitched contents from the token is done elsewhere.
        placeHolder: m21.Music21Object | None = None
        if infoHash is not None:
            placeHolder = infoHash.getValueM21Object('music21', 'placeHolder')

        unpitched: m21.note.Unpitched = M21Utilities.createUnpitched(placeHolder)

        if placeHolder is not None and infoHash is not None:
            infoHash.setValue('music21', 'placeHolder', None)

        return unpitched

    def _createAndConvertNote(
        self,
        token: HumdrumToken,
        staffAdjust: int,
        measureIndex: int,
        staffIndex: int,
        layerIndex: int,
        subTokenIdx: int = -1
    ) -> m21.note.Note | m21.note.Unpitched | None:
        note: m21.note.Note | m21.note.Unpitched
        if token.isUnpitched:
            note = self._createUnpitched(token)
        else:
            note = self._createNote(token)

        convertedNote: m21.note.Note | m21.note.Unpitched | None = self._convertNote(
            note,
            token,
            staffAdjust,
            measureIndex,
            staffIndex,
            layerIndex,
            subTokenIdx
        )
        if token is not None and convertedNote is not None:
            token.setValue('music21', 'generalNote', convertedNote)

        return convertedNote

    @staticmethod
    def _replaceGeneralNoteWithUnpitched(placeHolder: m21.note.GeneralNote) -> m21.note.Unpitched:
        unpitched: m21.note.Unpitched = M21Utilities.createUnpitched(placeHolder)
        return unpitched

    @staticmethod
    def _createChord(infoHash: HumHash | None = None) -> m21.chord.Chord:
        # infoHash is generally the token for which the chord is being created,
        # but we declare it as a HumHash, since the only thing we read is
        # 'placeHolder'.
        # The actual construction of the chord contents from the token is done elsewhere.
        placeHolder: m21.Music21Object | None = None
        if infoHash:
            placeHolder = infoHash.getValueM21Object('music21', 'placeHolder')

        chord: m21.chord.Chord = M21Utilities.createChord(placeHolder)

        if placeHolder is not None and infoHash is not None:
            infoHash.setValue('music21', 'placeHolder', None)

        return chord

    def _createAndConvertChord(
        self,
        token: HumdrumToken,
        measureIndex: int,
        staffIndex: int,
        layerIndex: int
    ) -> m21.chord.Chord:
        chord: m21.chord.Chord = self._createChord(token)
        chord = self._convertChord(chord, token, measureIndex, staffIndex, layerIndex)
        if token is not None and chord is not None:
            token.setValue('music21', 'generalNote', chord)
        return chord

    @staticmethod
    def _createRest(infoHash: HumHash | None = None) -> m21.note.Rest:
        # infoHash is generally the token for which the rest is being created,
        # but we declare it as a HumHash, since the only thing we read is
        # 'placeHolder'.
        # The actual construction of the rest contents from the token is done elsewhere.
        placeHolder: m21.Music21Object | None = None
        if infoHash:
            placeHolder = infoHash.getValueM21Object('music21', 'placeHolder')

        rest: m21.note.Rest = M21Utilities.createRest(placeHolder)

        if placeHolder is not None and infoHash is not None:
            infoHash.setValue('music21', 'placeHolder', None)

        return rest

    def _createAndConvertRest(
        self,
        token: HumdrumToken,
        measureIndex: int,
        staffIndex: int
    ) -> m21.note.Rest:
        rest: m21.note.Rest = self._createRest(token)
        rest = self._convertRest(rest, token, measureIndex, staffIndex)
        if token is not None and rest is not None:
            token.setValue('music21', 'generalNote', rest)
        return rest

    def _createAndConvertFakeRest(self, fakeRest: FakeRestToken) -> m21.note.Rest:
        rest: m21.note.Rest = self._createRest(None)
        rest.duration.quarterLength = fakeRest.duration
        rest.style.hideObjectOnPrint = True
        return rest

    @staticmethod
    def _processUnexpandedTremolo(noteOrChord: m21.note.NotRest, layerTok: HumdrumToken) -> None:
        m = re.search(r'@(\d+)@', layerTok.text)
        if not m:
            # it wasn't an unexpanded tremolo after all
            return

        tremoloTotalDuration: HumNum = Convert.recipToDuration(layerTok.text)
        tremoloSingleNoteDuration: HumNum = Convert.recipToDuration(m.group(1))
        slashes: int = int(math.log(float(tremoloSingleNoteDuration)) / math.log(2.0))
        noteBeams: int = int(math.log(float(tremoloTotalDuration)) / math.log(2.0))
        if noteBeams < 0:
            slashes = slashes - noteBeams
        slashes = -slashes
        if slashes <= 0:
            # something went wrong calculating durations
            return

        tremolo: m21.expressions.Tremolo = m21.expressions.Tremolo()
        try:
            tremolo.numberOfMarks = slashes
            noteOrChord.expressions.append(tremolo)
        except m21.expressions.TremoloException:
            # numberOfMarks out of range (1..8)
            return

    @staticmethod
    def _processTremolo(noteOrChord: m21.note.NotRest, layerTok: HumdrumToken) -> None:
        tremolo: m21.expressions.Tremolo = m21.expressions.Tremolo()
        slashes: int = layerTok.getValueInt('auto', 'slashes')
        try:
            tremolo.numberOfMarks = slashes
            noteOrChord.expressions.append(tremolo)
        except m21.expressions.TremoloException:
            # numberOfMarks out of range (1..8)
            pass

    def _processUnexpandedTremolo2(
        self,
        noteOrChord: m21.note.NotRest,
        measureIndex: int,
        voice: m21.stream.Voice,
        noteOrChordOffsetInVoice: HumNumIn,
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int,
        staffIndex: int,
        layerIndex: int
    ) -> bool:
        skippedEndOfTremolo2: bool = False
        layerTok: HumdrumToken | FakeRestToken = layerData[tokenIdx]
        if layerTok.isFakeRest:
            # fake rests aren't unexpanded tremolo2s
            return skippedEndOfTremolo2

        if t.TYPE_CHECKING:
            # because layerTok.isFakeRest is False
            assert isinstance(layerTok, HumdrumToken)

        m = re.search(r'@@(\d+)@@', layerTok.text)
        if not m:
            # it wasn't an unexpanded tremolo2 after all
            return skippedEndOfTremolo2

        if layerTok.getValueBool('auto', 'unexpandedTremolo2AlreadyProcessed'):
            # it's an endTremolo2 token, and we've already processed it
            skippedEndOfTremolo2 = True
            return skippedEndOfTremolo2

        singleTremoloNoteDuration: HumNum = Convert.recipToDuration(m.group(1))
        beams: int = -int(math.log(float(singleTremoloNoteDuration)) / math.log(2.0))
        second: HumdrumToken | None = None

        tremolo2: m21.expressions.TremoloSpanner = m21.expressions.TremoloSpanner()
        try:
            tremolo2.numberOfMarks = beams
            for z in range(tokenIdx + 1, len(layerData)):
                tokz: HumdrumToken | FakeRestToken = layerData[z]
                if tokz.isFakeRest:
                    continue
                if t.TYPE_CHECKING:
                    # because tokz.isFakeRest is False
                    assert isinstance(tokz, HumdrumToken)
                if re.search(r'@@(\d+)@@', tokz.text):
                    second = tokz
                    second.setValue('auto', 'unexpandedTremolo2AlreadyProcessed', '1')
                    break
        except m21.expressions.TremoloException:
            # numberOfMarks out of range (1..8)
            return skippedEndOfTremolo2

        if not second:
            return skippedEndOfTremolo2

        # First we need to double the visual duration of noteOrChord (leaving the
        # gestural duration as it was)
        self._fixupUnexpandedTremolo2Duration(noteOrChord)

        self.m21Score.coreInsert(0, tremolo2)
        self.m21Score.coreElementsChanged()

        ncOffsetInVoice: HumNum = opFrac(noteOrChordOffsetInVoice)
        # ignoring slurs, ties, ornaments, articulations
        if second.isChord:
            chord2: m21.chord.Chord = self._createAndConvertChord(
                second, measureIndex, staffIndex, layerIndex
            )
            self._fixupUnexpandedTremolo2Duration(chord2)
            chord2OffsetInVoice: HumNum = opFrac(
                ncOffsetInVoice + noteOrChord.duration.quarterLength)
            voice.coreInsert(chord2OffsetInVoice, chord2)
            tremolo2.addSpannedElements(noteOrChord, chord2)
        else:
            note2: m21.note.Note | m21.note.Unpitched | None = self._createAndConvertNote(
                second, 0, measureIndex, staffIndex, layerIndex
            )
            if note2 is None:
                return skippedEndOfTremolo2
            note2OffsetInVoice: HumNum = opFrac(
                ncOffsetInVoice + noteOrChord.duration.quarterLength
            )
            self._fixupUnexpandedTremolo2Duration(note2)
            voice.coreInsert(note2OffsetInVoice, note2)
            tremolo2.addSpannedElements(noteOrChord, note2)

        self._addSlurToTremoloSpanner(tremolo2, layerTok, second)
        self._addExplicitStemDirectionToTremoloSpanner(tremolo2, layerTok)

        return skippedEndOfTremolo2

    @staticmethod
    def _fixupUnexpandedTremolo2Duration(noteOrChord: m21.note.NotRest) -> None:
        # double the duration
        originalDuration: HumNum = opFrac(noteOrChord.duration.quarterLength)
        noteOrChord.duration.quarterLength = opFrac(originalDuration * opFrac(2))

        # halve the gestural duration (back to what it was)
        # so visual duration will stay doubled
        noteOrChord.duration.linked = False
        noteOrChord.duration.quarterLength = originalDuration

    def _processTremolo2(
        self,
        noteOrChord: m21.note.NotRest,
        measureIndex: int,
        voice: m21.stream.Voice,
        noteOrChordOffsetInVoice: HumNumIn,
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int,
        staffIndex: int,
        layerIndex: int
    ) -> None:
        layerTok: HumdrumToken | FakeRestToken = layerData[tokenIdx]
        if layerTok.isFakeRest:
            return

        if t.TYPE_CHECKING:
            # because layerTok.isFakeRest is False
            assert isinstance(layerTok, HumdrumToken)

        tremolo2: m21.expressions.TremoloSpanner = m21.expressions.TremoloSpanner()
        beams: int = layerTok.getValueInt('auto', 'beams')
        # unit: int = layerTok.getValueInt('auto', 'unit')
        second: HumdrumToken | None = None
        try:
            tremolo2.numberOfMarks = beams
            for z in range(tokenIdx + 1, len(layerData)):
                tokz: HumdrumToken | FakeRestToken = layerData[z]
                if tokz.isFakeRest:
                    continue
                if t.TYPE_CHECKING:
                    # because tokz.isFakeRest is False
                    assert isinstance(tokz, HumdrumToken)
                if tokz.getValueInt('auto', 'tremoloAux'):
                    second = tokz
                    break
        except m21.expressions.TremoloException:
            # numberOfMarks out of range (1..8)
            return

        if second is None:
            return

        self.m21Score.coreInsert(0, tremolo2)
        self.m21Score.coreElementsChanged()

        ncOffsetInVoice: HumNum = opFrac(noteOrChordOffsetInVoice)

        # ignoring slurs, ties, ornaments, articulations
        if second.isChord:
            chord2: m21.chord.Chord = self._createAndConvertChord(
                second, measureIndex, staffIndex, layerIndex
            )
            chord2OffsetInVoice: HumNum = opFrac(
                ncOffsetInVoice + noteOrChord.duration.quarterLength
            )
            voice.coreInsert(chord2OffsetInVoice, chord2)
            tremolo2.addSpannedElements(noteOrChord, chord2)
        else:
            note2: m21.note.Note | m21.note.Unpitched | None = self._createAndConvertNote(
                second, 0, measureIndex, staffIndex, layerIndex
            )
            if note2 is None:
                return
            note2OffsetInVoice: HumNum = opFrac(
                ncOffsetInVoice + noteOrChord.duration.quarterLength
            )
            voice.coreInsert(note2OffsetInVoice, note2)
            tremolo2.addSpannedElements(noteOrChord, note2)

        self._addSlurToTremoloSpanner(tremolo2, layerTok, second)
        self._addExplicitStemDirectionToTremoloSpanner(tremolo2, layerTok)

    '''
    //////////////////////////////
    //
    // HumdrumInput::addSlur -- Check if there is a slur start and
    //   end at the start/end of the tremolo group.
    '''
    def _addSlurToTremoloSpanner(
        self,
        tremoloSpanner: m21.expressions.TremoloSpanner,
        start: HumdrumToken,
        ending: HumdrumToken
    ) -> None:
        if ')' not in ending.text:
            # no slur ending
            return
        if 'J' not in ending.text:
            # no beam end (there could be weird unbeamed cases perhaps)
            return

        if '(' not in start.text:
            # no slur start on tremoloSpanner, but there is a slur end from somewhere
            self._processSlurs(tremoloSpanner.getLast(), ending)
            return
        if 'L' not in start.text:
            # no beam start (there could be weird unbeamed cases perhaps)
            return

        # maybe a problem if not all of the slurs on ending token
        # are ftrem (may result in multiple slurs for non-tremolo slurs.
        self._processSlurs(tremoloSpanner.getLast(), ending)

    '''
    //////////////////////////////
    //
    // addExplicitStemDirection -- Check if there is an explicit direction for
    //   the FTrem element.  This can be either an above/below signifier
    //   after the beam on the first token of the ftrem group, or it can be
    //   the stem direction on the first note of the tremolo group.
    '''
    def _addExplicitStemDirectionToTremoloSpanner(
        self,
        tremoloSpanner: m21.expressions.TremoloSpanner,
        start: HumdrumToken
    ) -> None:
        direction: int = 0
        if '/' in start.text:
            direction = +1
        elif '\\' in start.text:
            direction = -1
        else:
            if self._signifiers.above:
                if re.search('[LJkK]+' + self._signifiers.above, start.text):
                    direction = +1
            elif self._signifiers.below:
                if re.search('[LJkK]+' + self._signifiers.below, start.text):
                    direction = -1

        if direction == 0:
            return

        for obj in tremoloSpanner.getSpannedElementsByClass(['NotRest']):
            # Note, Chord, Unpitched
            if direction > 0:
                obj.stemDirection = 'up'
                if isinstance(obj, m21.chord.ChordBase):
                    for n in obj.notes:
                        n.stemDirection = 'up'
            elif direction < 0:
                obj.stemDirection = 'down'
                if isinstance(obj, m21.chord.ChordBase):
                    for n in obj.notes:
                        n.stemDirection = 'down'

    '''
        _processTremolos: does any processing necessary to generate Tremolo or TremoloSpanner
    '''
    def _processTremolos(
        self,
        noteOrChord: m21.note.NotRest,
        measureIndex: int,
        voice: m21.stream.Voice,
        offsetInVoice: HumNumIn,
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int,
        staffIndex: int,
        layerIndex: int
    ) -> bool:
        skippedEndOfTremolo2: bool = False
        layerTok: HumdrumToken | FakeRestToken = layerData[tokenIdx]
        if layerTok.isFakeRest:
            return skippedEndOfTremolo2

        if t.TYPE_CHECKING:
            # because layerTok.isFakeRest is False
            assert isinstance(layerTok, HumdrumToken)

        ncOffsetInVoice: HumNum = opFrac(offsetInVoice)
        if '@@' in layerTok.text:
            skippedEndOfTremolo2 = self._processUnexpandedTremolo2(
                noteOrChord, measureIndex, voice, ncOffsetInVoice,
                layerData, tokenIdx, staffIndex, layerIndex
            )
        elif '@' in layerTok.text:
            self._processUnexpandedTremolo(noteOrChord, layerTok)
        elif self._hasTremolo and layerTok.getValueBool('auto', 'startTremolo'):
            self._processTremolo(noteOrChord, layerTok)
        elif self._hasTremolo and layerTok.getValueBool('auto', 'startTremolo2'):
            self._processTremolo2(noteOrChord, measureIndex, voice, ncOffsetInVoice,
                                  layerData, tokenIdx,
                                  staffIndex, layerIndex)
        return skippedEndOfTremolo2

    '''
        _processChordLayerToken
    '''
    def _processChordLayerToken(
        self,
        measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int,
        staffIndex: int,
        layerIndex: int
    ) -> bool:
        insertedIntoVoice: bool = False
        layerTok: HumdrumToken | FakeRestToken = layerData[tokenIdx]
        if layerTok.isFakeRest:
            return insertedIntoVoice

        if t.TYPE_CHECKING:
            # because layerTok.isFakeRest is False
            assert isinstance(layerTok, HumdrumToken)

        vOffsetInMeasure: HumNum = opFrac(voiceOffsetInMeasure)
        chordOffsetInMeasure: HumNum = layerTok.durationFromBarline
        chordOffsetInVoice: HumNum = opFrac(chordOffsetInMeasure - vOffsetInMeasure)
        chord: m21.chord.Chord = self._createAndConvertChord(
            layerTok, measureIndex, staffIndex, layerIndex
        )

        skipThisChord: bool = self._processTremolos(
            chord, measureIndex, voice, chordOffsetInVoice,
            layerData, tokenIdx, staffIndex, layerIndex
        )
        if skipThisChord:
            # it was the end of a Tremolo2, and had already been inserted earlier
            return insertedIntoVoice

        # TODO: chord signifiers
        # self._processChordSignifiers(chord, layerTok, staffIndex)

        self._processSlurs(chord, layerTok)
        self._processPhrases(chord, layerTok)
        self._processDynamics(measureIndex, voice, vOffsetInMeasure, layerTok, staffIndex)

        # TODO: chord stem directions
#         self._assignAutomaticStem(chord, layerTok, staffIndex)
        self._addArticulations(chord, layerTok)
        self._addOrnaments(chord, layerTok, staffIndex)
        self._addArpeggio(chord, layerTok)
        self._processDirections(measureIndex, voice, vOffsetInMeasure, layerTok, staffIndex)

        voice.coreInsert(chordOffsetInVoice, chord)
        insertedIntoVoice = True

        return insertedIntoVoice

    '''
        _convertChord
    '''
    def _convertChord(
        self,
        chord: m21.chord.Chord,
        layerTok: HumdrumToken,
        measureIndex: int,
        staffIndex: int,
        layerIndex: int
    ) -> m21.chord.Chord:
        # int staffadj = getStaffAdjustment(token);
        # if (staffadj != 0) {
        #     int staffnum = staffindex + 1 + staffadj;
        #     setStaff(chord, staffnum);
        # }
        tstrings: list[str] = layerTok.subtokens

        allInvisible: bool = True
        for tstring in tstrings:
            if 'yy' not in tstring:
                allInvisible = False
                break

        for subTokenIdx, tstring in enumerate(tstrings):
            isRest: bool = False
            hasNoteValue: bool = False
            hasDuration: bool = False
            if not tstring:
                continue

            for ch in tstring:
                if ch == 'r':
                    isRest = True
                elif ch in 'abcdefgABCDEFG':
                    # I would note that rests _can_ have note values (for positioning),
                    # but we don't actually care here, because we skip all rests below. --gregc
                    hasNoteValue = True
                elif ch in '0123456789':
                    hasDuration = True

            if isRest:
                # no rests in chords
                continue

            if hasDuration and not hasNoteValue:
                # no spaces in chords
                continue

            # iohumdrum.cpp suppressed conversion of invisible notes in a chord, since
            # C++ code doesn't properly suppress the stem that goes with the invisible note.
            # I'm not going to do that, since I want to describe exactly what is there, for
            # music21, and the exporters will each need to handle it correctly (or not!).
#             if ((!allinvis) && (tstrings[j].find("yy") != std::string::npos)) {
#                 continue;
#             }

            note: m21.note.Note | m21.note.Unpitched | None = self._createAndConvertNote(
                layerTok,
                0,
                measureIndex,
                staffIndex,
                layerIndex,
                subTokenIdx
            )
            if note is not None:
                chord.add(note)

        if allInvisible:
            chord.style.hideObjectOnPrint = True

        # grace notes need to be done before rhythm since default
        # duration is set to an eighth note here.
        chord = self._replaceChordWithGrace(chord, layerTok.text)

        # chord tremolos are handled inside _convertRhythm
        self._convertRhythm(chord, layerTok)

        # LATER: Support *2\right for scores where half-notes' stems are on the right
        # I don't think music21 can do it, so...

        # Overwrite cross-stem direction if there is an explicit stem direction.  This
        # has already been done for each note in the chord (in the createAndConvertNote
        # calls above).  Here we are believing the first '/' or '\\' we see in the chord
        # token, which may well be on one of the note subtokens.
        didSetChordStemDirection: bool = False
        if '/' in ' '.join(tstrings):
            chord.stemDirection = 'up'
            didSetChordStemDirection = True
        elif '\\' in ' '.join(tstrings):
            chord.stemDirection = 'down'
            didSetChordStemDirection = True

        # Stem direction of the chord beam.  If both up and down, then show up.
        beamStemDir: int = layerTok.getValueInt('auto', 'stem.dir')
        if beamStemDir == 1:
            chord.stemDirection = 'up'
            didSetChordStemDirection = True
        elif beamStemDir == -1:
            chord.stemDirection = 'down'
            didSetChordStemDirection = True

        if didSetChordStemDirection:
            for note in chord.notes:
                note.stemDirection = chord.stemDirection

        # We do not need to adjustChordNoteDurations, since _convertNote carefully did not
        # set note durations at all (in a chord). --gregc
        #    adjustChordNoteDurations(chord, notes, tstrings);

        layerTok.setValue('music21', 'measureIndex', measureIndex)

        self._processOttava(chord, layerTok, measureIndex, staffIndex)

        self._convertVerses(chord, layerTok)
        return chord

    '''
        _processRestLayerToken
    '''
    def _processRestLayerToken(
        self,
        measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        layerTok: HumdrumToken,
        staffIndex: int
    ) -> bool:
        vOffsetInMeasure: HumNum = opFrac(voiceOffsetInMeasure)
        restOffsetInMeasure: HumNum = layerTok.durationFromBarline
        restOffsetInVoice: HumNum = opFrac(restOffsetInMeasure - vOffsetInMeasure)
        rest: m21.note.Rest = self._createAndConvertRest(layerTok, measureIndex, staffIndex)

        # TODO: rest colors
        # self._colorRest(rest, layerTok)
        self._processSlurs(rest, layerTok)
        self._processPhrases(rest, layerTok)
        self._processDynamics(measureIndex, voice, vOffsetInMeasure, layerTok, staffIndex)
        self._processDirections(measureIndex, voice, vOffsetInMeasure, layerTok, staffIndex)

        if ('yy' in layerTok.text
                and not self._signifiers.irestColor
                and not self._signifiers.spaceColor):
            # Invisible rest
            rest.style.hideObjectOnPrint = True

        voice.coreInsert(restOffsetInVoice, rest)
        return True  # we did insert into the voice

    def _processFakeRestLayerToken(
        self,
        _measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        fakeRest: FakeRestToken
    ) -> bool:
        vOffsetInMeasure: HumNum = opFrac(voiceOffsetInMeasure)
        restOffsetInMeasure: HumNum = fakeRest.durationFromBarline
        restOffsetInVoice: HumNum = opFrac(restOffsetInMeasure - vOffsetInMeasure)
        rest: m21.note.Rest = self._createAndConvertFakeRest(fakeRest)
        voice.coreInsert(restOffsetInVoice, rest)
        return True  # we did insert into the voice

    '''
    /////////////////////////////
    //
    // HumdrumInput::convertRest --
    '''
    def _convertRest(
        self,
        rest: m21.note.Rest,
        token: HumdrumToken,
        measureIndex: int,
        staffIndex: int
    ) -> m21.note.Rest:
        if 'q' in token.text:
            # It's an accacciatura ('q') or appoggiatura ('qq')
            rest = self._replaceRestWithGrace(rest, token.text)

        self._convertRhythm(rest, token)
        self._positionRestVertically(rest, token)

        self._adjustStaff(rest, token, staffIndex)

        if ';' in token.text:
            self._addFermata(rest, token)

        token.setValue('music21', 'measureIndex', measureIndex)

        return rest

    '''
        _adjustStaff: moves a note/rest/whatever to the staff above or
            below if necessary.
    '''
    def _adjustStaff(self, rest: m21.note.Rest, token: HumdrumToken, staffIndex: int) -> None:
        pass  # LATER: _adjustStaff

    '''
        _positionRestVertically: uses the stepShift value which was
            computed by HumdrumFileContent.analyzeRestPositions
    '''
    @staticmethod
    def _positionRestVertically(rest: m21.note.Rest, token: HumdrumToken) -> None:
        # I don't use getValueInt here because the default is 0, and I
        # need the default to be "don't set rest.stepShift at all" --gregc
        stepShiftStr: str | None = token.getValue('auto', 'stepShift')
        if stepShiftStr is None:
            return
        rest.stepShift = int(stepShiftStr)

    '''
        _processNoteLayerToken
    '''
    def _processNoteLayerToken(
        self,
        measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        layerData: list[HumdrumToken | FakeRestToken],
        tokenIdx: int,
        staffIndex: int,
        layerIndex: int
    ) -> bool:
        layerTok: HumdrumToken | FakeRestToken = layerData[tokenIdx]
        if layerTok.isFakeRest:
            return False

        if t.TYPE_CHECKING:
            # because layerTok.isFakeRest is False
            assert isinstance(layerTok, HumdrumToken)

        vOffsetInMeasure: HumNum = opFrac(voiceOffsetInMeasure)
        noteOffsetInMeasure: HumNum = layerTok.durationFromBarline
        noteOffsetInVoice: HumNum = opFrac(noteOffsetInMeasure - vOffsetInMeasure)
        note: m21.note.Note | m21.note.Unpitched | None = self._createAndConvertNote(
            layerTok,
            0,
            measureIndex,
            staffIndex,
            layerIndex
        )

        if note is None:
            return False

        skipThisNote: bool = self._processTremolos(note, measureIndex,
                                                   voice, noteOffsetInVoice,
                                                   layerData, tokenIdx,
                                                   staffIndex, layerIndex)
        if skipThisNote:
            # it was an endTremolo2, and had been inserted earlier
            return False

        self._processSlurs(note, layerTok)
        self._processPhrases(note, layerTok)
        self._processDynamics(measureIndex, voice, vOffsetInMeasure, layerTok, staffIndex)
        # TODO: note stem directions, no stem, hairpin accent, cue size
#       assignAutomaticStem(note, layerdata[i], staffindex);
#       if (m_signifiers.nostem
#               && layerdata[i]->find(m_signifiers.nostem) != std::string::npos) {
#           note->SetStemVisible(BOOLEAN_false);
#       if (m_signifiers.hairpinAccent
#               && layerdata[i]->find(m_signifiers.hairpinAccent) != std::string::npos) {
#           addHairpinAccent(layerdata[i]);
        self._addArticulations(note, layerTok)
        self._addOrnaments(note, layerTok, staffIndex)
        self._addArpeggio(note, layerTok)
        self._processDirections(measureIndex, voice, vOffsetInMeasure, layerTok, staffIndex)
        voice.coreInsert(noteOffsetInVoice, note)
        return True  # we did insert into the voice

    '''
    //////////////////////////////
    //
    // HumdrumInput::addArpeggio --
    //   : = arpeggio which may cross between layers on a staff.
    //   :: = arpeggio which crosses staves on a single system.

        Music21 has two types of arpeggio marks: a single chord mark (ArpeggioMark, placed in
        chord.expressions), and a multi-chord/note mark (ArpeggioMarkSpanner, which contains
        all the notes/chords that are arpeggiated together).

        Note that a Humdrum staff arpeggio may be translated to an ArpeggioMark on a single
        chord, or may have multiple chords/notes (in multiple layers on a staff) so it must
        be translated to an ArpeggioMarkSpanner. A system arpeggio always has multiple
        chords/notes, so it is always translated to an ArpeggioMarkSpanner.
    '''
    def _addArpeggio(self, gnote: m21.note.GeneralNote, layerTok: HumdrumToken):
        arpeggiatedTokens: list[HumdrumToken] = []

        if '::' in layerTok.text:
            # it's a cross-staff arpeggio (a.k.a. system arpeggio)
            if not self._isLeftmostSystemArpeggioToken(layerTok):
                return
            arpeggiatedTokens = self._getSystemArpeggioTokens(layerTok)
            if not arpeggiatedTokens:
                # no system arpeggio actually found
                return
        elif ':' in layerTok.text:
            # it's a single-layer or cross-layer arpeggio (a.k.a. staff arpeggio)
            if not self._isLeftmostStaffArpeggioToken(layerTok):
                return
            arpeggiatedTokens = self._getStaffArpeggioTokens(layerTok)
            if not arpeggiatedTokens:
                # no staff arpeggio actually found
                return
        else:
            # no arpeggio on this note/chord
            return

        if len(arpeggiatedTokens) == 1:
            gnote.expressions.append(m21.expressions.ArpeggioMark())  # type: ignore
        elif len(arpeggiatedTokens) > 1:
            arpeggioSpanner = m21.expressions.ArpeggioMarkSpanner()  # type: ignore
            for arpTok in arpeggiatedTokens:
                gn: m21.note.GeneralNote = self._getGeneralNoteOrPlaceHolder(arpTok)
                arpeggioSpanner.addSpannedElements(gn)
            self.m21Score.coreInsert(0, arpeggioSpanner)
            self.m21Score.coreElementsChanged()

    @staticmethod
    def _isLeftmostSystemArpeggioToken(token: HumdrumToken) -> bool:
        tok: HumdrumToken | None = token.previousFieldToken

        # loop over tokens to our left, to see if there are any arpeggiated chords/notes
        while tok is not None:
            if not tok.isKern:
                # skip spines that don't contain notes/chords/etc
                tok = tok.previousFieldToken
                continue

            if tok.isRest and tok.isInvisible:
                # skip invisible rests
                tok = tok.previousFieldToken
                continue

            if ':' in tok.text:
                # we found an arpeggiated chord/note to our left, so...
                return False

            tok = tok.previousFieldToken

        return True

    @staticmethod
    def _getSystemArpeggioTokens(leftmostToken: HumdrumToken) -> list[HumdrumToken]:
        output: list[HumdrumToken] = [leftmostToken]
        tok: HumdrumToken | None = leftmostToken.nextFieldToken

        # loop over tokens to our right, adding them to the output list until we see
        # a token without ':'.
        while tok is not None:
            if not tok.isKern:
                # skip spines that don't contain notes/chords/etc
                tok = tok.nextFieldToken
                continue

            if tok.isRest and tok.isInvisible:
                # skip invisible rests
                tok = tok.nextFieldToken
                continue

            if '::' not in tok.text:
                # it's not an arpeggiated token, we're done
                break

            output.append(tok)
            tok = tok.nextFieldToken

        return output

    @staticmethod
    def _isLeftmostStaffArpeggioToken(token: HumdrumToken) -> bool:
        staffTrack: int | None = token.track
        if t.TYPE_CHECKING:
            # at this point, tokens must have track numbers
            assert staffTrack is not None

        tok: HumdrumToken | None = token.previousFieldToken

        # loop over tokens to our left, to see if there are any arpeggiated chords/notes
        while tok is not None:
            if tok.track != staffTrack:
                # all done (we've moved into a different staff)
                break

            if not tok.isKern:
                # skip spines that don't contain notes/chords/etc
                tok = tok.previousFieldToken
                continue

            if tok.isRest and tok.isInvisible:
                # skip invisible rests
                tok = tok.previousFieldToken
                continue

            if ':' in tok.text:
                # we found an arpeggiated chord/note to our left, so...
                return False

            tok = tok.previousFieldToken

        return True

    @staticmethod
    def _getStaffArpeggioTokens(leftmostToken: HumdrumToken) -> list[HumdrumToken]:
        output: list[HumdrumToken] = [leftmostToken]
        staffTrack: int | None = leftmostToken.track
        if t.TYPE_CHECKING:
            # at this point, tokens must have track numbers
            assert staffTrack is not None

        tok: HumdrumToken | None = leftmostToken.nextFieldToken

        # loop over tokens to our right, adding them to the output list until we see
        # a token without ':'.
        while tok is not None:
            if tok.track != staffTrack:
                # all done (we've moved into a different staff)
                break

            if not tok.isKern:
                # skip spines that don't contain notes/chords/etc
                tok = tok.nextFieldToken
                continue

            if tok.isRest and tok.isInvisible:
                # skip invisible rests
                tok = tok.nextFieldToken
                continue

            if ':' not in tok.text:
                # it's not an arpeggiated token, we're done
                break

            output.append(tok)
            tok = tok.nextFieldToken

        return output

    def _addArticulations(self, note: m21.note.GeneralNote, token: HumdrumToken) -> None:
        note.articulations += M21Convert.m21Articulations(
            token.text,
            self._signifiers.above,
            self._signifiers.below
        )

    def _addOrnaments(
        self,
        gnote: m21.note.GeneralNote,
        token: HumdrumToken,
        staffIndex: int
    ) -> None:
        lowerText = token.text.lower()
        if 't' in lowerText:
            self._addTrill(gnote, token, staffIndex)
        if ';' in lowerText:
            self._addFermata(gnote, token)
# handled in articulations code
#         if ',' in lowerText:
#             self._addBreath(gnote, token)
        if 'w' in lowerText or 'm' in lowerText:
            self._addMordent(gnote, token, staffIndex)
        if 's' in lowerText or '$' in lowerText:
            self._addTurn(gnote, token, staffIndex)

    _LAYOUT_ACCIDENTAL_TO_ACCIDENTAL_NUM_STR: dict[str, str] = {
        '#': '1',
        '-': '-1',
        'n': '0',
        'n-': '-1',
        'n#': '1',
        '--': '-2',
        '##': '2',
        'x': '2',
        '#x': '3',
        'x#': '3',
        '###': '3',
        '---': '-3',
    }

    '''
    //////////////////////////////
    //
    // HumdrumInput::addTrill -- Add trill for note.
    '''
    def _addTrill(
        self,
        startNote: m21.note.GeneralNote,
        token: HumdrumToken,
        staffIndex: int
    ) -> None:
        ss: StaffStateVariables = self._staffStates[staffIndex]

        subTokenIdx: int = 0
        tpos: int = -1
        for i, ch in enumerate(token.text):
            if ch == ' ':
                subTokenIdx += 1
                continue
            if ch in ('t', 'T'):
                tpos = i
                if i < len(token.text) - 1:
                    # deal with TT or tt for trills with wavy lines
                    if token.text[i + 1] in ('t', 'T'):
                        tpos += 1
                break
        if tpos == -1:
            # no trill on a note
            return

        if 'TTT' in token.text or 'ttt' in token.text:
            # continuation trill, so don't start a new one
            return

        # music21 now supports Trill accidentals. That is handled by accidental analysis
        # in HumdrumFileContent, and then here we adjust that based on any '!LO:TR:acc='
        # accidental.

        trillAccid: m21.pitch.Accidental | None = self._computeM21Accidental(
            token.getValueString('auto', str(subTokenIdx), 'trillAccidental.vis')
        )
        if trillAccid is not None:
            # we have a visual accidental
            trillAccid.displayStatus = True
        else:
            trillAccid = self._computeM21Accidental(
                token.getValueString('auto', str(subTokenIdx), 'trillAccidental.ges')
            )
            if trillAccid is not None:
                # we have a gestural accidental
                trillAccid.displayStatus = False

        # replace the trill accidental if different in layout parameters, such as:
        #    !LO:TR:acc=##
        # for a double sharp, or
        #    !LO:TR:acc=none
        # for no visible accidental
        accText: str = token.layoutParameter('TR', 'acc')
        if accText:
            if accText in ('none', 'false'):
                if trillAccid is not None:
                    trillAccid.displayStatus = False
            else:
                trillAccid = self._computeM21Accidental(
                    self._LAYOUT_ACCIDENTAL_TO_ACCIDENTAL_NUM_STR.get(accText, '')
                )
                if trillAccid is not None:
                    trillAccid.displayStatus = True

        trill: m21.expressions.Trill = m21.expressions.Trill(accidental=trillAccid)

        # Now, resolve the Trill's "other" pitch based on startNote
        if startNote.pitches:
            trill.resolveOrnamentalPitches(startNote, keySig=ss.currentM21KeySig)

        startNote.expressions.append(trill)

        # here the C++ code sets placement to 'below' if layer == 2
        # if m_currentlayer == 2:
        #     trill.placement = 'below'

        # our better default
        trill.placement = None  # type: ignore

        if self._signifiers.above:
            if tpos < len(token.text) - 1:
                if token.text[tpos + 1] == self._signifiers.above:
                    trill.placement = 'above'
        if self._signifiers.below:
            if tpos < len(token.text) - 1:
                if token.text[tpos + 1] == self._signifiers.below:
                    trill.placement = 'below'

        if 'TT' not in token.text and 'tt' not in token.text:
            # no TrillExtension
            return

        # Done with Trill, now on to TrillExtension

        # Find the ending note after the trill line.  Multiple trill line extensions for chord
        # notes are not handled by this algorithm, but these should be rare in notation.
        # The music21 way to notate this is with a TrillExtension (a Spanner) that contains the
        # startNote and the last trilled note (i.e. the note before the "ending note" which we
        # are about to find).
        endTok: HumdrumToken | None = token.nextToken0
        lastNoteOrBar: HumdrumToken = token
        nextToLastNote: HumdrumToken = token

        while endTok:
            if endTok.isBarline:
                if lastNoteOrBar.isData:
                    nextToLastNote = lastNoteOrBar
                lastNoteOrBar = endTok

            if not endTok.isData:
                endTok = endTok.nextToken0
                continue

            if endTok.isNull:
                endTok = endTok.nextToken0
                continue

            # it's a note/chord/rest
            if endTok.isGrace:
                # check to see if the next non-grace note/rest has a TTT or ttt on it.
                # if so, then do not terminate the trill extension line at this
                # grace notes.
                ntok: HumdrumToken | None = endTok.nextToken0
                while ntok:
                    if ntok.isBarline:
                        lastNoteOrBar = ntok

                    if not ntok.isData:
                        ntok = ntok.nextToken0
                        continue

                    if ntok.isGrace:
                        ntok = ntok.nextToken0
                        continue

                    lastNoteOrBar = ntok

                    # at this point ntok is a durational note/chord/rest
                    if 'TTT' not in ntok.text and 'ttt' not in ntok.text:
                        endTok = ntok
                        break
                    ntok = ntok.nextToken0

            if lastNoteOrBar.isData:
                nextToLastNote = lastNoteOrBar
            lastNoteOrBar = endTok
            if 'TTT' not in endTok.text and 'ttt' not in endTok.text:
                break

            endTok = endTok.nextToken0

        # This code is now quite different from C++ code, as we are creating a spanner, not
        # MEI stuff (where there are more cases to consider).
        if endTok and nextToLastNote:
            # endTok (first note after trill extension) was found, use nextToLastNote in spanner
            endTok = nextToLastNote
        elif not endTok and lastNoteOrBar and lastNoteOrBar.isData:
            # reached the end of the music without finding a note after trill extension, so
            # use the lastNoteOrBar in spanner
            endTok = lastNoteOrBar
        else:
            # it must start and end on the same note
            endTok = None

        trillExtension: m21.expressions.TrillExtension
        if endTok is None:
            trillExtension = m21.expressions.TrillExtension(startNote)
        else:
            endNote: m21.note.GeneralNote = self._getGeneralNoteOrPlaceHolder(endTok)
            trillExtension = m21.expressions.TrillExtension(startNote, endNote)

        self.m21Score.coreInsert(0, trillExtension)
        self.m21Score.coreElementsChanged()

    def _addFermata(
        self,
        obj: m21.note.GeneralNote | m21.bar.Barline,
        token: HumdrumToken
    ) -> None:
        if ';' not in token.text:
            return
        if 'yy' in token.text:
            return

#         staffAdj: int = self._getStaffAdjustment(token)
        fermata: m21.expressions.Fermata = m21.expressions.Fermata()
        fermata.type = 'upright'

        fermata2: m21.expressions.Fermata | None = None
        if ';;' in token.text:
            fermata2 = m21.expressions.Fermata()
            fermata2.type = 'inverted'
            fermata2.style.absoluteY = 'below'

        if fermata2 is not None:
            if isinstance(obj, m21.bar.Barline):
                # music21 only allows one fermata on a barline
                obj.pause = fermata
            else:
                obj.expressions.append(fermata)
                obj.expressions.append(fermata2)
            return

        direction: int = self._getDirection(token, ';')
        if direction < 0:
            fermata.type = 'inverted'
            fermata.style.absoluteY = 'below'
        elif direction > 0:
            fermata.type = 'upright'
            fermata.style.absoluteY = 'above'
        # C++ code also has special cases for m_currentlayer 1 and 2 (i.e. layerIndex 0 and 1)
        # where layer 1 goes 'above', and layer 2 goes 'below', and others get no direction.

        if isinstance(obj, m21.bar.Barline):
            # music21 barlines can only have one fermata; stick with the first one
            if obj.pause is None:
                obj.pause = fermata
        else:
            obj.expressions.append(fermata)

#     '''
#     //////////////////////////////
#     //
#     // HumdrumInput::addBreath -- Add floating breath for note/chord.
#         Only used for barlines now, and that doesn't work yet.
#     '''
#     def _addBreath(self, gnote: m21.note.GeneralNote, token: HumdrumToken) -> None:
#         if ',' not in token.text:
#             return
#
#         if 'yy' in token.text or ',y' in token.text:
#             return # the entire note is hidden, or the breath mark is hidden
#
#         breathMark = m21.articulations.BreathMark()
#         direction = self._getDirection(token, ',')
#         if direction < 0:
#             breathMark.placement = 'below'
#         elif direction > 0:
#             breathMark.placement = 'above'
#         # C++ code also has special cases for m_currentlayer 1 and 2 (i.e. layerIndex 0 and 1)
#         # where layer 1 goes 'above', and layer 2 goes 'below', and others get no direction.
#
#         # TODO: _addBreath might be passed a barline instead of a note.  BreathMark gets printed
#         # TODO: ... just after the note in question, so we could attach it to the previous note
#         # TODO: ... (if there is one)
#         gnote.articulations.append(breathMark)

    def _computeM21Accidental(
        self,
        valueStr: str | None
    ) -> m21.pitch.Accidental | None:
        if not valueStr:
            return None

        try:
            accidNum: int = int(valueStr)
        except Exception:
            return None

        accid: m21.pitch.Accidental = m21.pitch.Accidental(accidNum)
        return accid

    '''
    //////////////////////////////
    //
    // HumdrumInput::addMordent -- Add mordent for note.
    //      M  = upper mordent, major second interval
    //      MM = double upper mordent, major second interval
    //      m  = upper mordent, minor second interval
    //      mm = double upper mordent, minor second interval
    //      W  = lower mordent, major second interval
    //      WW = double lower mordent, major second interval
    //      w  = lower mordent, minor second interval
    //      ww = double lower mordent, minor second interval
    //  also:
    //      Mm  = upper mordent with unknown interval
    //      MMm = double upper mordent with unknown interval
    //      Ww  = lower mordent with unknown interval
    //      WWw = double lower mordent with unknown interval

        There is much discussion about which mordent is normal, and which mordent is inverted.
        Yay standards! The bottom line is that there is an 'upper' mordent and a 'lower' mordent,
        and which one of these is considered to be inverted has changed over time.  music21 says
        very clearly that their InvertedMordent type is the upper mordent, so the only question
        then is whether 'W' or 'M' is Humdrum's upper mordent.  Verovio thinks 'M' is upper.
        music21's humdrum/spineParser.py thinks the opposite (although it doesn't actually mention
        upper and lower, it just maps 'W' to m21.expressions.InvertedMordent, which we know to be
        upper).  I will be sticking to verovio's definition, since verovio's humdrum parser is
        written by Craig Sapp, the author of humlib, and his code seems to be the closest thing to
        thorough humdrum documentation that we have. Also, 'M' looks like it is pointing up,
        so... --gregc

    '''
    def _addMordent(
        self,
        gnote: m21.note.GeneralNote,
        token: HumdrumToken,
        staffIndex: int
    ) -> None:
        ss: StaffStateVariables = self._staffStates[staffIndex]

        subtoks: list[str] = token.subtokens
        if not subtoks:
            return

        subtrack: int = token.subTrack

        mindices: list[int] = []   # indices of subtokens with mordent
        mstrings: list[str] = []   # list of mordent strings (including '<', '>', 'y')
        mpitches: list[int] = []   # pitches of notes with mordents

        query: str = '('
        query += '[wWmM]+'
        query += '[y'
        if self._signifiers.above:
            query += self._signifiers.above
        if self._signifiers.below:
            query += self._signifiers.below
        query += ']*'
        query += ')'

        for i, subtok in enumerate(subtoks):
            if 'r' in subtok:
                continue

            m = re.search(query, subtok)
            if not m:
                continue

            match: str = m.group(1)
            if 'y' in match:
                # Hidden mordent, so suppress from conversion
                continue

            mindices.append(i)
            mstrings.append(match)
            mpitches.append(Convert.kernToBase40(subtok))

        if not mindices:
            # no mordents found
            return

        # find highest and lowest pitch
        highest: int = mpitches[0]
        lowest: int = mpitches[0]
        for mpitch in mpitches:
            highest = max(highest, mpitch)
            lowest = min(lowest, mpitch)

        mplaces: list[int] = [0] * len(mindices)
        if subtrack:
            if subtrack % 2 != 0:
                # force above for first/third/fifth/etc. layers:
                mplaces = [+1] * len(mplaces)
            else:
                # force below for second/fourth/etc. layers:
                mplaces = [-1] * len(mplaces)

        else:
            # Single voice so put above if a single mordent,
            # but place a second mordent below if a dyad.
            if len(mindices) == 1:
                mplaces[0] = +1
            elif len(mindices) == 2:
                if highest == mpitches[0]:
                    mplaces[0] = +1
                    mplaces[1] = -1
                else:
                    mplaces[0] = -1
                    mplaces[1] = +1
            else:
                # If there are three or more mordents in a chord, place them
                # all above the staff, and if any should be placed below, then
                # it will have to be manually specified.
                mplaces = [+1] * len(mplaces)

        for i, (mstring, mplace, subTokenIdx) in enumerate(zip(mstrings, mplaces, mindices)):
            if not mstring:
                continue

            isLower: bool = mstring[0] in 'wW'

            mordentAccid: m21.pitch.Accidental | None = self._computeM21Accidental(
                token.getValueString('auto', str(subTokenIdx), 'mordentAccidental.vis')
            )
            if mordentAccid is not None:
                # we have a visual accidental
                mordentAccid.displayStatus = True
            else:
                mordentAccid = self._computeM21Accidental(
                    token.getValueString('auto', str(subTokenIdx), 'mordentAccidental.ges')
                )
                if mordentAccid is not None:
                    # we have a gestural accidental
                    mordentAccid.displayStatus = False


            # Set any explicit visual accidental for the mordent.
            # Maybe in the future allow for lacc and uacc to place the accidental.
            # Also deal multiple mordents in a chord later.
            accText: str = token.layoutParameter('MOR', 'acc')
            if accText and accText != 'true':
                if accText in ('none', 'false'):
                    if mordentAccid is not None:
                        mordentAccid.displayStatus = False
                else:
                    mordentAccid = self._computeM21Accidental(
                        self._LAYOUT_ACCIDENTAL_TO_ACCIDENTAL_NUM_STR.get(accText, '')
                    )
                    if mordentAccid is not None:
                        mordentAccid.displayStatus = True

            mordent: m21.expressions.GeneralMordent
            if isLower:
                mordent = m21.expressions.Mordent(accidental=mordentAccid)
            else:
                mordent = m21.expressions.InvertedMordent(accidental=mordentAccid)

            # Default placement has been set up in mplaces.
            direction: int = mplace

            # Override default with any explicit placement of the mordent
            if self._signifiers.above:
                if self._signifiers.above in mstring:
                    direction = +1

            if self._signifiers.below:
                if self._signifiers.below in mstring:
                    direction = -1

            mordent.placement = None  # type: ignore
            if direction < 0:
                mordent.placement = 'below'
            elif direction > 0:
                mordent.placement = 'above'

            # LATER: long mordents ('MM', 'mm', 'WW', 'ww') are not supported by music21, so we
            # LATER: ... can't really support them here.
#           if 'MM' in mstrings[i] or 'WW' in mstrings[i]:   # 'mm'? 'ww'?
#               mordent.isLong = True

            # Now, resolve the mordent's "other" pitch based on gnote
            if gnote.pitches:
                mordent.resolveOrnamentalPitches(gnote, keySig=ss.currentM21KeySig)

            gnote.expressions.append(mordent)

    '''
    //////////////////////////////
    //
    // HumdrumInput::addTurn -- Add turn for note.
    //  only one of these four possibilities:
    //      S([Ss][Ss])?  = delayed turn
    //      sS([Ss][Ss])? = undelayed turn
    //      $([Ss][Ss])?  = delayed inverted turn
    //      s$([Ss][Ss])? = undelayed inverted turn
    //
    //  Not used anymore:
    //      SS = turn, centered between two notes
    //      $$ = inverted turn, centered between two notes
    //
    //  Layout parameters:
    //      LO:TURN:facc[=true] = flip upper and lower accidentals
    //      LO:TURN:uacc=[acc]  = upper [visible] accidental (or lower one if flip is active)
    //      LO:TURN:lacc=[acc]  = lower [visible] accidental (or upper one if flip is active)
    // 			[ul]acc = "none" = force the accidental not to show
    // 			[ul]acc = "true" = force the accidental not to show
    //                                  ("LO:TURN:[ul]acc" hide an accidental)
    //
    // Deal with cases where the accidental should be hidden but different from sounding
    // accidental.  This can be done when MEI allows @accidlower.ges and @accidupper.ges.
    //
    // Assuming not in chord for now.
    '''
    def _addTurn(
        self,
        gnote: m21.note.GeneralNote,
        token: HumdrumToken,
        staffIndex: int
    ) -> None:
        ss: StaffStateVariables = self._staffStates[staffIndex]
        tok: str = token.text
        turnStart: int = -1
        turnEnd: int = -1

        # assume not in chord for now
        subTokenIdx: int = 0

        for i, ch in enumerate(tok):
            if ch in ('s', 'S', '$'):
                turnStart = i
                turnEnd = i
                for j in range(i + 1, len(tok)):
                    if tok[j] not in ('s', 'S', '$'):
                        turnEnd = j - 1
                        break
                    turnEnd = j
                break

        turnStr: str = tok[turnStart:turnEnd + 1]
        if turnStr == 's':
            # invalid turn indication; leading 's' (not delayed) must be followed by 'S' or '$'
            return

        isDelayed: bool = turnStr[0] != 's'
        isInverted: bool = False
        if not isDelayed and turnStr[1] == '$':
            isInverted = True
        elif turnStr[0] == '$':
            isInverted = True


        # check for automatic upper and lower accidental on turn:
        turnLowerAccid: m21.pitch.Accidental | None = self._computeM21Accidental(
            token.getValueString('auto', str(subTokenIdx), 'turnLowerAccidental.vis')
        )
        if turnLowerAccid is not None:
            # we have a visual lower accidental
            turnLowerAccid.displayStatus = True
        else:
            turnLowerAccid = self._computeM21Accidental(
                token.getValueString('auto', str(subTokenIdx), 'turnLowerAccidental.ges')
            )
            if turnLowerAccid is not None:
                # we have a gestural lower accidental
                turnLowerAccid.displayStatus = False

        turnUpperAccid: m21.pitch.Accidental | None = self._computeM21Accidental(
            token.getValueString('auto', str(subTokenIdx), 'turnUpperAccidental.vis')
        )
        if turnUpperAccid is not None:
            # we have a visual upper accidental
            turnUpperAccid.displayStatus = True
        else:
            turnUpperAccid = self._computeM21Accidental(
                token.getValueString('auto', str(subTokenIdx), 'turnUpperAccidental.ges')
            )
            if turnUpperAccid is not None:
                # we have a gestural upper accidental
                turnUpperAccid.displayStatus = False

        # Check for LO:TURN forced visual accidentals
        lacctext: str = token.layoutParameter('TURN', 'lacc')
        uacctext: str = token.layoutParameter('TURN', 'uacc')
        if lacctext and lacctext != 'true':
            if lacctext in ('none', 'false'):
                if turnLowerAccid is not None:
                    turnLowerAccid.displayStatus = False
            else:
                turnLowerAccid = self._computeM21Accidental(
                    self._LAYOUT_ACCIDENTAL_TO_ACCIDENTAL_NUM_STR.get(lacctext, '')
                )
                if turnLowerAccid is not None:
                    turnLowerAccid.displayStatus = True

        if uacctext and uacctext != 'true':
            if uacctext in ('none', 'false'):
                if turnUpperAccid is not None:
                    turnUpperAccid.displayStatus = False
            else:
                turnUpperAccid = self._computeM21Accidental(
                    self._LAYOUT_ACCIDENTAL_TO_ACCIDENTAL_NUM_STR.get(uacctext, '')
                )
                if turnUpperAccid is not None:
                    turnUpperAccid.displayStatus = True

        # Check to see if accidentals need to be flipped:
        facctext: str = token.layoutParameter('TURN', 'facc')
        if facctext == 'true':
            turnLowerAccid, turnUpperAccid = turnUpperAccid, turnLowerAccid

        # Create Turn/InvertedTurn object, using upper and lower accids
        turn: m21.expressions.Turn
        delay: OrnamentDelay = OrnamentDelay.NO_DELAY
        if isDelayed:
            delay = OrnamentDelay.DEFAULT_DELAY

        if isInverted:
            turn = m21.expressions.InvertedTurn(
                delay=delay,
                upperAccidental=turnUpperAccid,
                lowerAccidental=turnLowerAccid
            )
        else:
            turn = m21.expressions.Turn(
                delay=delay,
                upperAccidental=turnUpperAccid,
                lowerAccidental=turnLowerAccid
            )

        # our better default
        turn.placement = None  # type: ignore

        if self._signifiers.above:
            if turnEnd < len(tok) - 1:
                if tok[turnEnd + 1] == self._signifiers.above:
                    turn.placement = 'above'

        if self._signifiers.below:
            if turnEnd < len(tok) - 1:
                if tok[turnEnd + 1] == self._signifiers.below:
                    turn.placement = 'below'

        # Now, resolve the Turn "other" pitches based on gnote
        if gnote.pitches:
            turn.resolveOrnamentalPitches(gnote, keySig=ss.currentM21KeySig)

        gnote.expressions.append(turn)


    '''
    //////////////////////////////
    //
    // HumdrumInput::getDirection --
    //    0  = no direction specified
    //    1  = place above
    //    -1 = place below
    '''
    def _getDirection(self, token: HumdrumToken, target: str) -> int:
        if self._signifiers.above:
            if target + self._signifiers.above in token.text:
                return +1

        if self._signifiers.below:
            if target + self._signifiers.below in token.text:
                return -1

        return 0

    def _processSlurs(self, endNote: m21.note.GeneralNote, token: HumdrumToken) -> None:
        slurEndCount: int = token.getValueInt('auto', 'slurEndCount')
        if slurEndCount <= 0:
            # not a slur end
            return

        # slurstarts: indexed by slur end number (NB: 0 position not used).
        # tuple contains the slur start enumeration (tuple[0]) and the start token (tuple[1])
        slurStartList: list[tuple[int, HumdrumToken | None]] = (
            [(-1, None)] * (slurEndCount + 1)
        )
        for i in range(1, slurEndCount + 1):
            slurStartList[i] = (token.getSlurStartNumber(i), token.getSlurStartToken(i))

        for i in range(1, slurEndCount + 1):
            slurStartTok: HumdrumToken | None = slurStartList[i][1]
            if not slurStartTok:
                continue

            slurStartNumber: int = slurStartList[i][0]
            isInvisible: bool = self._checkIfSlurIsInvisible(slurStartTok, slurStartNumber)
            if isInvisible:
                continue

            startNote: m21.note.GeneralNote = self._getGeneralNoteOrPlaceHolder(slurStartTok)
            slur: m21.spanner.Slur = m21.spanner.Slur(startNote, endNote)
            self._addSlurLineStyle(slur, slurStartTok, slurStartNumber)

            # set above/below from current layout parameter (if there is one)
            self._setLayoutSlurDirection(slur, slurStartTok)

            # Calculate if the slur should be forced above or below
            # this is the case for doubly slurred chords.  Only the first
            # two slurs between a pair of notes/chords will be oriented
            # (other slurs will need to be manually adjusted and probably
            # linked to individual notes to avoid overstriking the first
            # two slurs.
            if slurEndCount > 1:
                found: int = -1
                for j in range(1, slurEndCount + 1):
                    if i == j:
                        continue
                    if slurStartList[i][1] == slurStartList[j][1]:
                        found = j
                        break
                if found > 0:
                    if found < i:
                        slur.placement = 'above'
                    else:
                        slur.placement = 'below'

            # If the token itself says above or below, that overrides everything
            if self._signifiers.above or self._signifiers.below:
                count: int = 0
                for k in range(0, len(slurStartTok.text) - 1):
                    if slurStartTok.text[k] == '(':
                        count += 1
                    if count == slurStartNumber:
                        if slurStartTok.text[k + 1] == self._signifiers.above:
                            slur.placement = 'above'
                        elif slurStartTok.text[k + 1] == self._signifiers.below:
                            slur.placement = 'below'
                        break

            # Put spanner in top-level stream, because it might contain notes
            # that are in different Parts.
            self.m21Score.coreInsert(0, slur)
            self.m21Score.coreElementsChanged()

    def _setLayoutSlurDirection(self, slur: m21.spanner.Slur, token: HumdrumToken) -> None:
        if self._hasAboveParameter(token, 'S'):
            slur.placement = 'above'
        elif self._hasBelowParameter(token, 'S'):
            slur.placement = 'below'

    @staticmethod
    def _addSlurLineStyle(slur: m21.spanner.Slur, token: HumdrumToken, slurNumber: int) -> None:
        slurNumber = max(slurNumber, 1)  # never let it be < 1
        slurIndex: int = slurNumber - 1
        dashed: str = token.layoutParameter('S', 'dash', slurIndex)
        dotted: str = token.layoutParameter('S', 'dot', slurIndex)
        if dotted:
            slur.lineType = 'dotted'
        elif dashed:
            slur.lineType = 'dashed'

        color: str = token.layoutParameter('S', 'color', slurIndex)
        if color:
            slur.style.color = color

    @staticmethod
    def _checkIfSlurIsInvisible(token: HumdrumToken, number: int) -> bool:
        tsize: int = len(token.text)
        counter: int = 0
        for i in range(0, tsize - 1):
            if token.text[i] == '(':
                counter += 1
            if counter == number:
                if token.text[i + 1] == 'y':
                    return True
                return False
        return False

    def _processPhrases(self, note: m21.note.GeneralNote, token: HumdrumToken) -> None:
        pass  # LATER: phrases (_processPhrases)

    @staticmethod
    def _replaceGeneralNoteWithGrace(
        generalNote: m21.note.GeneralNote,
        tstring: str
    ) -> m21.note.GeneralNote:
        myGN: m21.note.GeneralNote = generalNote
        if 'qq' in tstring:
            myGN = myGN.getGrace(appoggiatura=True)
            if t.TYPE_CHECKING:
                assert isinstance(myGN.duration, m21.duration.GraceDuration)
            myGN.duration.slash = False
            myGN.duration.type = 'eighth'  # for now, recomputed later
        elif 'q' in tstring:
            myGN = myGN.getGrace(appoggiatura=False)
            myGN.duration.type = 'eighth'  # for now, recomputed later

        if myGN is not generalNote:
            # transfer any spanners from generalNote to myGN
            for spanner in generalNote.getSpannerSites():
                spanner.replaceSpannedElement(generalNote, myGN)

        return myGN

    @staticmethod
    def _replaceNoteWithGrace(
        note: m21.note.Note | m21.note.Unpitched,
        tstring: str
    ) -> m21.note.Note | m21.note.Unpitched:
        gn: m21.note.GeneralNote = HumdrumFile._replaceGeneralNoteWithGrace(note, tstring)
        if t.TYPE_CHECKING:
            # because _replaceGeneralNoteWithGrace always returns the same type you pass in
            assert isinstance(gn, (m21.note.Note, m21.note.Unpitched))
        return gn

    @staticmethod
    def _replaceChordWithGrace(chord: m21.chord.Chord, tstring: str) -> m21.chord.Chord:
        gn: m21.note.GeneralNote = HumdrumFile._replaceGeneralNoteWithGrace(chord, tstring)
        if t.TYPE_CHECKING:
            # because of the nature of _replaceGeneralNoteWithGrace (see above)
            assert isinstance(gn, m21.chord.Chord)
        return gn

    @staticmethod
    def _replaceRestWithGrace(rest: m21.note.Rest, tstring: str) -> m21.note.Rest:
        gn: m21.note.GeneralNote = HumdrumFile._replaceGeneralNoteWithGrace(rest, tstring)
        if t.TYPE_CHECKING:
            # because _replaceGeneralNoteWithGrace always returns the same type you pass in
            assert isinstance(gn, m21.note.Rest)
        return gn

    def _convertNote(
        self,
        note: m21.note.Note | m21.note.Unpitched,
        token: HumdrumToken,
        staffAdjust: int,
        measureIndex: int,
        staffIndex: int,
        layerIndex: int,
        subTokenIdx: int = -1
    ) -> m21.note.Note | m21.note.Unpitched | None:
        # note is empty.  Fill it in.
        ss: StaffStateVariables = self._staffStates[staffIndex]
        tstring: str = ''
        stindex: int = 0
        if subTokenIdx < 0:
            tstring = token.text
        else:
            tstring = token.subtokens[subTokenIdx]
            stindex = subTokenIdx

        # TODO: scordatura

        # we might be converting one note (subtoken) of a chord (token)
        isChord: bool = token.isChord
        isUnpitched: bool = token.isUnpitched
        isBadPitched: bool = False

        # Q: Should pitched note in staff with *clefX be colored (because it's an error)?
        # if not isUnpitched and ss.lastClef.text.startswith('*clefX'):
        #     isBadPitched = True # it's wrong
        #     isUnpitched = True  # fix it

        self._processTerminalLong(token)

        # TODO: overfilling notes (might be a no-op for music21)
        # self._processOverfillingNotes(token)

        # TODO: support colored notes
        # (e.g. use note.style.color = 'red')
        self._colorNote(note, token, tstring)

        if not isChord:
            self._processOttava(note, token, measureIndex, staffIndex)

        # check for accacciatura ('q') and appoggiatura ('qq')
        if not isChord and 'q' in tstring:
            note = self._replaceNoteWithGrace(note, tstring)

        # Add the pitch information
        # This here is the point where C++ code transposes "transposing instruments"
        # back to the written key, but we don't do that (music21 understands transposing
        # instruments just fine).
        m21PitchName: str = M21Convert.m21PitchName(tstring)
        octave: int = Convert.kernToOctaveNumber(tstring)

        if isUnpitched:
            if t.TYPE_CHECKING:
                assert isinstance(note, m21.note.Unpitched)
            if hasattr(m21.common.types, 'StepName'):
                displayStepV8: m21.common.types.StepName | None = (
                    M21Convert.m21StepNameV8(tstring)
                )
                if octave >= 0 and displayStepV8 is not None:
                    note.displayOctave = octave
                    note.displayStep = displayStepV8
            else:
                # we can remove this code in favor of StepName once we no longer
                # support music21 v7
                displayStep: str | None = M21Convert.m21StepName(tstring)
                if octave >= 0 and displayStep is not None:
                    note.displayOctave = octave
                    note.displayStep = displayStep  # type: ignore
        else:
            if t.TYPE_CHECKING:
                assert isinstance(note, m21.note.Note)
            # Q: might need to jump octaves backward to the ottava?  Maybe that's just MEI.
            # Q: music21 has transposing and non-transposing ottavas, so we probably just
            # Q: need to use the right one, so we can leave the note alone.
            if octave < 0 or m21PitchName is None:
                # tstring is bogus, it didn't parse as a note.
                return None
            note.octave = octave
            note.name = m21PitchName

        if isBadPitched:
            note.style.color = '#c41414'

        # TODO: editorial and cautionary accidentals (partially implemented)
        # needs some work (and a revisiting of the iohumdrum.cpp code)

        if token.getBooleanLayoutParameter('N', 'xstem'):
            note.stemDirection = 'noStem'

        self._setNoteHead(note, token, subTokenIdx, staffIndex)

        mensit: bool = False
#         isGestural: bool = False
#         hasMensAccidental: bool = False
#         accidlevel: int = 0
#         if self._hasMensSpine and token.isMens:
#             # mensural notes are indicated differently, so check here for their method.
#             if 'n' in tstring or '-' in tstring or '#' in tstring:
#                 hasMensAccidental = True
#
#             mensit = True
#             if 'YY' in tstring:
#                 accidlevel = 1
#             elif 'Y' in tstring:
#                 accidlevel = 2
#             elif 'yy' in tstring:
#                 accidlevel = 3
#             elif 'y' in tstring:
#                 accidlevel = 4
#
#             isGestural = (accidlevel > ss.acclev)
#
#         accidCount: int = Convert.base40ToAccidental(base40)
#         if testaccid > 2 or testaccid < -2:
#             # note couldn't be expressed in base40 above
#             accidCount = testaccid

        # check for editorial or cautionary accidental
        hasCautionary: bool | None = token.hasCautionaryAccidental(stindex)
#        cautionaryOverride: str = '' # e.g. 'n#', where the note just has '#'
        hasVisible: bool | None = token.hasVisibleAccidental(stindex)
        hasEditorial: bool | None = token.hasEditorialAccidental(stindex)
        editorialStyle: str = ''
        if hasCautionary:
            # cautionaryOverride = token.cautionaryAccidental(stindex)
            pass
        if hasEditorial:
            optionalEdStyle: str | None = token.editorialAccidentalStyle(stindex)
            if optionalEdStyle is not None:
                editorialStyle = optionalEdStyle

        if not mensit and not isUnpitched:
            if t.TYPE_CHECKING:
                assert isinstance(note, m21.note.Note)
            if note.pitch.accidental:
                # by default we do not display accidentals (only cautionary/editorial/visible)
                note.pitch.accidental.displayStatus = False

            if hasEditorial or hasCautionary or hasVisible:
                if not note.pitch.accidental:
                    note.pitch.accidental = m21.pitch.Accidental('natural')

                if hasEditorial:
                    note.pitch.accidental.displayStatus = True
                    if editorialStyle.startswith('brac'):
                        note.pitch.accidental.displayStyle = 'bracket'
                    elif editorialStyle.startswith('paren'):
                        note.pitch.accidental.displayStyle = 'parentheses'
                    elif editorialStyle in ('a', 'above'):
                        note.pitch.accidental.displayLocation = 'above'
                elif hasCautionary or hasVisible:  # cautionary is ignored if we have editorial.
                    # music21 doesn't really know how to deal with non-standard accidentals
                    # here, but music21's MusicXML importer does, so we set them like it does,
                    # with allowNonStandardValue=True, and spell them like MusicXML does, as well.
                    # music21's 'standard' accidentals are:
                    # 'natural': '',
                    # 'sharp': '#',
                    # 'double-sharp': '##',
                    # 'triple-sharp': '###',
                    # 'quadruple-sharp': '####',
                    # 'flat': '-',
                    # 'double-flat': '--',
                    # 'triple-flat': '---',
                    # 'quadruple-flat': '----',
                    # 'half-sharp': '~',
                    # 'one-and-a-half-sharp': '#~',
                    # 'half-flat': '`',
                    # 'one-and-a-half-flat': '-`',

                    note.pitch.accidental.displayStatus = True

                    # We can't actually do this, since none of the exporters understand, so
                    # they fail to print the cautionary accidental entirely...
                    # Once MusicXML export handles these, we can put it back in.
                    # if cautionaryOverride and cautionaryOverride != 'true':
                    #     if cautionaryOverride == 'n':
                    #         note.pitch.accidental.set('natural')
                    #     elif cautionaryOverride == '-':
                    #         note.pitch.accidental.set('flat')
                    #     elif cautionaryOverride == '#':
                    #         note.pitch.accidental.set('sharp')
                    #     elif cautionaryOverride == '--':
                    #         note.pitch.accidental.set('double-flat')
                    #     elif cautionaryOverride == 'x':
                    #         note.pitch.accidental.set('double-sharp')
                    #     elif cautionaryOverride == '##':
                    #         note.pitch.accidental.set('sharp-sharp', allowNonStandardValue=True)
                    #     elif cautionaryOverride == '---':
                    #         note.pitch.accidental.set('triple-flat')
                    #     elif cautionaryOverride == 'xs':
                    #         note.pitch.accidental.set('double-sharp-sharp',
                    #           allowNonStandardValue=True)
                    #     elif cautionaryOverride == 'sx':
                    #         note.pitch.accidental.set('sharp-double-sharp',
                    #           allowNonStandardValue=True)
                    #     elif cautionaryOverride == '###':
                    #         note.pitch.accidental.set('sharp-sharp-sharp',
                    #           allowNonStandardValue=True)
                    #     elif cautionaryOverride == 'n-':
                    #         note.pitch.accidental.set('natural-flat', allowNonStandardValue=True)
                    #     elif cautionaryOverride == 'n#':
                    #         note.pitch.accidental.set('natural-sharp',
                    #           allowNonStandardValue=True)

        self._setStemDirection(note, token, tstring)

        # we don't set the duration of notes in a chord.  The chord gets a duration
        # instead.
        if not isChord:
            # note tremolos are handled inside _convertRhythm
            dur: HumNum = self._convertRhythm(note, token, subTokenIdx)
            if dur == 0:
                note.duration.type = 'quarter'
                note.stemDirection = 'noStem'

        if not token.isMens:
            # yy means make invisible in **kern, but is used for accidental
            # levels in **mens
            if 'yy' in tstring:
                note.style.hideObjectOnPrint = True

        # TODO: **kern 'P' and 'p' for start/stop appoggiatura (might be no-op for music21)

        # handle ties ('_' is both a start and an end)
        if not token.isMens:
            if '[' in tstring or '_' in tstring:
                self._processTieStart(note, token, tstring, subTokenIdx, layerIndex)
            if ']' in tstring or '_' in tstring:
                self._processTieEnd(note, token, tstring, subTokenIdx, layerIndex)

        # TODO: staffAdjust: move note to staff above or below if above/below signifier present
        if staffAdjust:
            print('moving notes to staff above or below not yet supported', file=sys.stderr)

        # lyrics
        if not isChord:
            self._convertVerses(note, token)

        # measure index (for later m21.spanner stuff: slurs, ties, phrases, etc)
        if not isChord:
            token.setValue('music21', 'measureIndex', measureIndex)

        # cue sized notes
        if t.TYPE_CHECKING:
            assert isinstance(note.style, m21.style.NoteStyle)

        if self._signifiers.cueSize and self._signifiers.cueSize in tstring:
            # note is marked as cue-sized
            note.style.noteSize = 'cue'
        elif ss.cueSize[layerIndex]:
            # layer is marked as containing all cue-sized notes
            note.style.noteSize = 'cue'
        elif token.getBooleanLayoutParameter('N', 'cue'):
            note.style.noteSize = 'cue'

        return note

    def _addToOttava(
            self,
            noteOrChord: m21.note.NotRest,
            token: HumdrumToken,
            ottava: m21.spanner.Ottava,
            measureIndex: int,
            staffIndex: int
    ):
        if measureIndex == ottava.humdrum_start_measure_index:  # type: ignore
            # check to see if noteOrChord/token is before the ottava starts
            if (token.durationFromBarline
                    < ottava.humdrum_start_duration_from_barline):  # type: ignore
                # it is before ottava start, don't add it
                return

        if hasattr(ottava, 'humdrum_end_measure_index'):
            if measureIndex == ottava.humdrum_end_measure_index:  # type: ignore
                if (token.durationFromBarline
                        >= ottava.humdrum_end_duration_from_barline):  # type: ignore
                    # it starts at or after ottava end, don't add it.
                    # Note that we are not checking token's end time, because
                    # (1) no note _should_ be overlapping the ottava end time,
                    # and (2) if such a note existed, it should probably be
                    # interpreted as being in the ottava.
                    return

        ottava.addSpannedElements(noteOrChord)

    def _processOttava(
        self,
        noteOrChord: m21.note.NotRest,
        token: HumdrumToken,
        measureIndex: int,
        staffIndex: int
    ):
        ss: StaffStateVariables = self._staffStates[staffIndex]
        if ss.currentOttava1Up is not None:
            self._addToOttava(noteOrChord, token, ss.currentOttava1Up, measureIndex, staffIndex)
        if ss.currentOttava1Down is not None:
            self._addToOttava(noteOrChord, token, ss.currentOttava1Down, measureIndex, staffIndex)
        if ss.currentOttava2Up is not None:
            self._addToOttava(noteOrChord, token, ss.currentOttava2Up, measureIndex, staffIndex)
        if ss.currentOttava2Down is not None:
            self._addToOttava(noteOrChord, token, ss.currentOttava2Down, measureIndex, staffIndex)

    '''
    //////////////////////////////
    //
    // processTerminalLong -- Not set up for chords yet.
    '''
    def _processTerminalLong(self, token: HumdrumToken) -> None:
        if not self._signifiers.terminalLong:
            return
        if self._signifiers.terminalLong not in token.text:
            return


        # TODO: terminal longs (partially implemented)
        # token.setValue('LO', 'N', 'vis', '00')
        # sets visual duration to "long" (i.e. 4 whole notes)
        # 1. make following barlines invisible
        # 2. if token is tied, follow ties to attached notes and make them invisible

    '''
    //////////////////////////////
    //
    // HumdrumInput::colorNote --
    '''
    def _colorNote(
        self,
        note: m21.note.Note | m21.note.Unpitched,
        token: HumdrumToken,
        tstring: str
    ) -> None:
        spineColor: str = self._getSpineColor(token)
        if spineColor:
            note.style.color = spineColor

        # also check for marked notes (the marked color will override spine color)
        for i, mark in enumerate(self._signifiers.noteMarks):
            if mark in tstring:
                note.style.color = self._signifiers.noteColors[i]
                if self._signifiers.noteDirs[i]:
                    # (e.g. rds-scores: R129_Jan-w30p11m124-127.krn)
                    pass  # TODO: note-associated text
                break

    '''
    //////////////////////////////
    //
    // HumdrumInput::getSpineColor --  But suppress black colors which are
    //     the default color of notes.
        Knowing the default color of notes is not the business of a parser, but
        rather the business of a renderer.  If the Humdrum data says "black", we
        will explicitly set "black", and only use default color if the Humdrum
        data doesn't say anything. --gregc
    '''
    def _getSpineColor(self, token: HumdrumToken) -> str:
        track: int | None = token.track
        strack: int = token.subTrack
        if track is None:
            return ''

        output: str = self._spineColor[track][strack]

        if not self._hasColorSpine:
            return output

        lineIdx = token.lineIndex
        fieldIdx = token.fieldIndex
        lineWithToken: HumdrumLine | None = self[lineIdx]
        if t.TYPE_CHECKING:
            # lineWithToken is not None because token is on that lineWithToken
            assert isinstance(lineWithToken, HumdrumLine)
        for i in range(fieldIdx + 1, lineWithToken.tokenCount):
            tok: HumdrumToken | None = lineWithToken[i]
            if t.TYPE_CHECKING:
                # tok is not None because i is in range
                assert isinstance(tok, HumdrumToken)
            if not tok.isDataType('**color'):
                continue

            tokRes: HumdrumToken | None = tok.nullResolution
            if tokRes is not None:
                output = tokRes.text
                if output == '.':
                    output = ''
            break

        return output

    '''
        _setNoteHead
    '''
    def _setNoteHead(
        self,
        note: m21.note.Note | m21.note.Unpitched,
        token: HumdrumToken,
        subTokenIdx: int,
        staffIndex: int
    ) -> None:
        head: str = token.layoutParameter('N', 'head', subTokenIdx)
        if not head:
            head = self._staffStates[staffIndex].noteHead

        if head:
            if head == 'solid':
                note.noteheadFill = True
            elif head == 'open':
                note.noteheadFill = False
            elif head == 'rhombus':
                note.notehead = 'diamond'
            elif head.startswith('dia'):
                note.notehead = 'diamond'
            elif head == 'plus':
                note.notehead = 'cross'
            else:
                try:
                    note.notehead = head
                except m21.note.NotRestException:
                    # use default notehead if unrecognized (NotRestException)
                    pass

    @staticmethod
    def _setStemDirection(
        note: m21.note.Note | m21.note.Unpitched,
        token: HumdrumToken,
        tstring: str
    ) -> None:
        # stem direction (if any)
        if '/' in tstring:
            note.stemDirection = 'up'
        elif '\\' in tstring:
            note.stemDirection = 'down'

        beamStemDir: int = token.getValueInt('auto', 'stem.dir')
        if beamStemDir == 1:
            note.stemDirection = 'up'
        elif beamStemDir == -1:
            note.stemDirection = 'down'

    '''
    //////////////////////////////
    //
    // HumdrumInput::convertVerses --
    '''
    def _convertVerses(self, obj: m21.note.NotRest, token: HumdrumToken) -> None:
        if token.track is None:
            return
        staffIndex: int = self._staffStartsIndexByTrack[token.track]
        ss: StaffStateVariables = self._staffStates[staffIndex]
        if not ss.hasLyrics:
            return

        subTrack: int = token.subTrack
        if subTrack > 1 and token.noteInLowerSubtrack():
            # don't print a lyric for secondary layers unless
            # all of the lower layers do not have a note attacking
            # or tied at the same time.  That way we don't duplicate
            # lyrics in multiple voices when one voice will do.
            return

        line: HumdrumLine = token.ownerLine
        track: int = token.track
        startField: int = token.fieldIndex + 1
        verseNum: int = 0

        for i, fieldTok in enumerate(line.tokens()):
            if i < startField:
                continue
            exinterp: str = fieldTok.dataType.text
            if fieldTok.isKern or 'kern' in exinterp:
                if fieldTok.track != track:
                    break

            if fieldTok.isMens or 'mens' in exinterp:
                if fieldTok.track != track:
                    break

            isLyric: bool = False
            isSilbe: bool = False
            isVdata: bool = False
            isVVdata: bool = False
            if fieldTok.isDataType('**text'):
                isLyric = True
            elif fieldTok.isDataType('**silbe'):
                isSilbe = True
                isLyric = True
            elif exinterp.startswith('**vdata'):
                isVdata = True
                isLyric = True
            elif exinterp.startswith('**vvdata'):
                isVVdata = True
                isLyric = True

            if not isLyric:
                continue

            if fieldTok.isNull:
                verseNum += 1
                continue

            if isSilbe:
                if fieldTok.text == '|':
                    verseNum += 1
                    continue

            verseLabel: str | None = None
            if ss.verseLabels:
                labels: list[HumdrumToken]
                labels = self._getVerseLabels(fieldTok, staffIndex)
                if labels:
                    verseLabel = self._getVerseLabelText(labels[0])

            vtexts: list[str] = []
            vtoks: list[HumdrumToken] = []
            vcolor: str = ''
            ftrack: int = fieldTok.track
            fstrack: int = fieldTok.subTrack

            if isSilbe:
                value: str = fieldTok.text
                value = value.replace('|', '')
                value = value.replace('u2', 'ü')
                value = value.replace('a2', 'ä')
                value = value.replace('o2', 'ö')
                value = value.replace(r'\u3', 'ü')
                value = value.replace(r'\a3', 'ä')
                value = value.replace(r'\o3', 'ö')
                vtexts.append(value)
                vtoks.append(fieldTok)
                vcolor = self._spineColor[ftrack][fstrack]
            else:
                # not silbe
                vtexts.append(fieldTok.text)
                vtoks.append(fieldTok)
                vcolor = self._spineColor[ftrack][fstrack]

            if isVVdata:
                self._splitSyllableBySpaces(vtexts)

            for content, vtoken in zip(vtexts, vtoks):
                # emit music21 lyrics and attach to obj
                verseNum += 1
                if not content:
                    continue

                # parent Lyric (will contain multiple component Lyrics if elisions present)
                verse: m21.note.Lyric = m21.note.Lyric()
                if vcolor:
                    verse.style.color = vcolor

                verse.number = verseNum
                if verseLabel:
                    verse.identifier = verseLabel


                if isVdata or isVVdata:
                    # do not parse text content as lyrics
                    # applyRaw=True means do not do any hyphen parsing
                    verse.setTextAndSyllabic(content, applyRaw=True)
                    obj.lyrics.append(verse)
                    continue

                content = self._colorVerse(verse, content)

                # verse can have multiple syllables if elisions present

                contents: list[str] = []

                # split syllable by elisions:
                contents.append(content[0])
                for z in range(1, len(content) - 1):
                    if content[z] in (' ', '\xa0') and content[z + 1] != "'":
                        # create an elision by separating into next piece of syllable
                        # \xa0 is a non-breaking space, and several humdrum files in
                        # jrp-scores use it as an elision character.
                        # The latter condition is to not elide "ma 'l"
                        contents.append('')
                    else:
                        contents[-1] += content[z]

                if len(content) > 1:
                    contents[-1] += content[-1]

                # we're all split apart, so we can translate any &nbsp; et al
                for idx, c in enumerate(contents):
                    contents[idx] = html.unescape(c)
                    contents[idx] = contents[idx].replace(r'\n', '\n')

                ij: str | None = vtoken.getValueString('auto', 'ij')

                # add elements for sub-syllables due to elisions:
                if len(contents) > 1:
                    verse.components = []
                    for syllableContent in contents:
                        syl: m21.note.Lyric = m21.note.Lyric()
                        # applyRaw=False means do all the parsing of hyphens to figure out syllabic
                        syl.setTextAndSyllabic(syllableContent, applyRaw=False)
                        verse.components.append(syl)
                else:
                    # applyRaw=False means do all the parsing of hyphens to figure out syllabic
                    verse.setTextAndSyllabic(contents[0], applyRaw=False)

                if ij:
                    verse.style.fontStyle = 'italic'  # type: ignore

                obj.lyrics.append(verse)

    '''
    //////////////////////////////
    //
    // HumdrumInput::getVerseLabelText --
    '''
    @staticmethod
    def _getVerseLabelText(token: HumdrumToken) -> str:
        if token is None:
            return ''
        if not token.isInterpretation:
            return ''
        if not token.text.startswith('*v:'):
            return ''

        contents: str = token.text[3:]
        output: str = ''
        if re.search(contents, r'^\d+$'):
            output = contents + '.'
        else:
            output = contents

        return output

    '''
    //////////////////////////////
    //
    // HumdrumInput::splitSyllableBySpaces -- Split a string into pieces
    //    according to spaces.  Default value spacer = ' ');
    '''
    @staticmethod
    def _splitSyllableBySpaces(vtext: list[str], spacer: str = ' ') -> None:
        if len(vtext) != 1:
            return

        if spacer not in vtext[0]:
            return

        original: str = vtext[0]
        vtext[0] = ''

        for origCh in original:
            if origCh != spacer:
                vtext[-1] += origCh
                continue
            # new string needs to be made
            vtext.append('')

    '''
    //////////////////////////////
    //
    // HumdrumInput::checkForVerseLabels --
    '''
    def _checkForVerseLabels(self, token: HumdrumToken) -> None:
        if token is None:
            return
        if not token.isInterpretation:
            return
        if token.track is None:
            return

        track: int = token.track
        staffIndex: int = self._staffStartsIndexByTrack[token.track]
        ss: StaffStateVariables = self._staffStates[staffIndex]

        current: HumdrumToken | None = token.nextFieldToken
        while current is not None and track == current.track:
            current = current.nextFieldToken

        while current and not current.isStaffDataType:
            if current.isDataType('**text') and current.text.startswith('*v:'):
                ss.verseLabels.append(current)
            current = current.nextFieldToken

    '''
    //////////////////////////////
    //
    // HumdrumInput::getVerseLabels --
    '''
    def _getVerseLabels(self, token: HumdrumToken, staffIndex: int) -> list[HumdrumToken]:
        output: list[HumdrumToken] = []
        ss: StaffStateVariables = self._staffStates[staffIndex]
        if not ss.verseLabels:
            return output

        remainder: list[HumdrumToken] = []
        spineInfo = token.spineInfo
        for label in ss.verseLabels:
            if label.spineInfo == spineInfo:
                output.append(label)
            else:
                remainder.append(label)

        if not output:
            return output

        ss.verseLabels = remainder
        return output

    '''
    //////////////////////////////
    //
    // HumdrumInput::colorVerse --
    '''
    def _colorVerse(self, verse: m21.note.Lyric, tokenStr: str) -> str:
        output: str = tokenStr
        for textMark, textColor in zip(self._signifiers.textMarks, self._signifiers.textColors):
            if textMark in tokenStr:
                verse.style.color = textColor

                # remove mark character from text (so that it does not display)
                output = re.sub(textMark, '', output)
                return output

        return output

    '''
    //////////////////////////////
    //
    // HumdrumInput::processTieStart -- linked slurs not allowed in chords yet.
    '''
    def _processTieStart(
        self,
        note: m21.note.Note | m21.note.Unpitched,
        token: HumdrumToken,
        tstring: str,
        subTokenIdx: int,
        layerIndex: int
    ) -> None:
        if token.isMens:
            return
        if token.track is None:
            return

        isContinue: bool = '_' in tstring

        endTag: str = 'tieEnd'
        if subTokenIdx >= 0:
            endTag += str(subTokenIdx + 1)  # tieEndN tags are 1-based

        tieEndTok: HumdrumToken = token.getValueToken('auto', endTag)
        if tieEndTok:
            # A linked tie which can be inserted immediately (and
            # not stored in the list of tie starts for later processing).
            endNumTag: str = 'tieEndSubtokenNumber'
            endN: int = subTokenIdx + 1
            if token.isChord:
                if endN > 0:
                    endNumTag += str(endN)
            endNumber: int = token.getValueInt('auto', endNumTag)
            if endNumber <= 0:
                endNumber = 1

            if isContinue:
                note.tie = m21.tie.Tie('continue')
            else:
                note.tie = m21.tie.Tie('start')

            self._addTieStyle(note.tie, token, tstring, subTokenIdx)

        # this tie was not linked directly in the Humdrum source, so we
        # need to figure out which note it is tied to.
        # So we push all the necessary info about this tie-start onto our
        # stack of tie-starts, and carry on.


        tie = HumdrumTie(
            layerIndex,
            note,
            token,
            tstring,
            subTokenIdx
        )

        # above and below placement is handled with a call to _setTieStyle
        # after tie.setEndAndInsert, not here, as it is in iohumdrum.cpp

        staffIndex: int = self._staffStartsIndexByTrack[token.track]
        ss: StaffStateVariables = self._staffStates[staffIndex]

        ss.ties.append(tie)

    '''
    //////////////////////////////
    //
    // processTieEnd --
    '''
    def _processTieEnd(
        self,
        note: m21.note.Note | m21.note.Unpitched,
        token: HumdrumToken,
        tstring: str,
        subTokenIdx: int,
        layerIndex: int
    ) -> None:
        if token.isMens:
            return
        if token.track is None:
            return

        startTag = 'tieStart'
        if token.isChord:
            startTag += str(subTokenIdx + 1)  # tieStartN tags are 1-based

        tieStartTok = token.getValueToken('auto', startTag)
        if tieStartTok:
            # linked ties are handled in processTieStart()
            # (but we might need to simply put a tie end on this note)
            if ']' in tstring:  # not '_'
                note.tie = m21.tie.Tie('stop')  # that's it, no style or placement
            return

        timeStamp: HumNum = token.durationFromStart
        track: int = token.track
        staffIndex: int = self._staffStartsIndexByTrack[track]
        ss: StaffStateVariables = self._staffStates[staffIndex]
        disjunct: bool = ']]' in tstring or '__' in tstring
        pitch: int = Convert.kernToMidiNoteNumber(tstring)
        found: HumdrumTie | None = None

        # search for open tie in current layer
        for tie in ss.ties:
            if tie.startLayerIndex != layerIndex:
                continue
            if tie.pitch != pitch:
                continue
            if disjunct and '[[' in tie.startSubTokenStr:
                found = tie
                break
            if disjunct and '__' in tie.startSubTokenStr:
                found = tie
                break
            if tie.endTime == timeStamp:
                found = tie
                break

        if not found:
            # search for open tie in current staff outside of current layer.
            for tie in ss.ties:
                if tie.pitch != pitch:
                    continue
                if disjunct and '[[' in tie.startSubTokenStr:
                    found = tie
                    break
                if disjunct and '__' in tie.startSubTokenStr:  # BUGFIX: This "if" was missing.
                    found = tie
                    break
                if tie.endTime == timeStamp:
                    found = tie
                    break

        if not found:
            self._processHangingTieEnd(note, tstring)
            return

        # TODO: hanging tie end in different endings
        # needToBreak = self._inDifferentEndings(found.startToken, token)
        # if needToBreak:
        #     self._processHangingTieEnd(note, tstring)
        #     return

        # invisible ties (handled here in iohumdrum.cpp) are handled via style
        # (since that's how music21 describes them)

        m21TieStart: m21.tie.Tie = found.setEndAndInsert(note, tstring)
        self._addTieStyle(m21TieStart, token, tstring, subTokenIdx)

        if found.wasInserted:
            # Only deleting the finished tie if it was successful.  Undeleted
            # ones can be checked later.  They are either encoding errors, or
            # hanging ties, or arpeggiation/disjunct ties (the latter are ties
            # where there is technically a time gap between the tied notes,
            # which we will ignore if the tie is encoded with [[, ]] rather
            # than [, ]).
            # See https://github.com/humdrum-tools/verovio-humdrum-viewer/issues/164
            # for a discussion of disjunct ties, and why they are needed.
            ss.ties.remove(found)

    '''
    //////////////////////////////
    //
    // HumdrumInput::addTieLineStyle -- Add dotted or dashed line information to a
    //    tie from layout parameters.
    //        Default parameter: index = 0.

        I have enhanced this a bit to include looking at signifiers (for above and
        below), and most significantly, to decide if the tie is hidden.
        Sadly, music21 doesn't support tie coloring.  tie.style is a string, not
        a music21.style.Style...
    '''
    def _addTieStyle(
        self,
        tie: m21.tie.Tie,
        token: HumdrumToken,
        tstring: str,
        subTokenIdx: int
    ) -> None:
        if '[y' in tstring or '_y' in tstring:
            tie.style = 'hidden'
        elif token.layoutParameter('T', 'dot', subTokenIdx):
            tie.style = 'dotted'
        elif token.layoutParameter('T', 'dash', subTokenIdx):
            tie.style = 'dashed'

        # LATER: tie coloring
        # Q: why doesn't music21's Tie have a real style attr?  Propose music21 fix.

        # above or below, based on layout parameters
        if token.layoutParameter('T', 'a', subTokenIdx):
            tie.placement = 'above'
        elif token.layoutParameter('T', 'b', subTokenIdx):
            tie.placement = 'below'

        # above or below, based on signifiers (this overrides layout parameters)
        if self._signifiers.above:
            startAbove: str = '[' + self._signifiers.above
            continueAbove: str = '_' + self._signifiers.above
            if startAbove in tstring or continueAbove in tstring:
                tie.placement = 'above'

        if self._signifiers.below:
            startBelow: str = '[' + self._signifiers.below
            continueBelow: str = '_' + self._signifiers.below
            if startBelow in tstring or continueBelow in tstring:
                tie.placement = 'below'

    '''
        _convertRhythm: computes token/subtoken duration and sets it on obj
                        (note, rest, chord).  Returns the computed duration.
    '''
    def _convertRhythm(
        self,
        obj: m21.Music21Object,
        token: HumdrumToken,
        subTokenIdx: int = -1
    ) -> HumNum:
        # if token.isMens:
        #     return self._convertMensuralRhythm(obj, token, subTokenIdx)
        isGrace: bool = False
        tremoloNoteVisualDuration: HumNum | None = None
        tremoloNoteGesturalDuration: HumNum | None = None
        if self._hasTremolo and (token.isNote or token.isChord):
            recipStr: str | None = None
            if token.getValueBool('auto', 'startTremolo'):
                recipStr = token.getValueString('auto', 'recip')
                if recipStr:
                    tremoloNoteVisualDuration = Convert.recipToDuration(recipStr)
            elif (token.getValueBool('auto', 'startTremolo2')
                    or token.getValueBool('auto', 'tremoloAux')):
                # In two note tremolos, the two notes each look like they have the full duration
                # of the tremolo sequence, but they actually each need to have half that duration
                # internally, for the measure duration to make sense.
                recipStr = token.getValueString('auto', 'recip')
                if recipStr:
                    tremoloNoteVisualDuration = Convert.recipToDuration(recipStr)
                    tremoloNoteGesturalDuration = opFrac(tremoloNoteVisualDuration / opFrac(2))

            if tremoloNoteVisualDuration is not None:
                obj.duration.quarterLength = tremoloNoteVisualDuration
                if tremoloNoteGesturalDuration is not None:
                    obj.duration.linked = False  # leave the note looking like visual duration
                    obj.duration.quarterLength = tremoloNoteGesturalDuration
                    return tremoloNoteGesturalDuration
                return tremoloNoteVisualDuration

        tstring: str = token.text.lstrip(' ')
        if subTokenIdx >= 0:
            tstring = token.subtokens[subTokenIdx]

        # Remove grace note information (for generating printed duration)
        if 'q' in tstring:
            isGrace = True
            tstring = re.sub('q', '', tstring)

        vstring: str = token.getVisualDuration(subTokenIdx)
        vdur: HumNum | None = None
        if vstring:
            vdur = Convert.recipToDuration(vstring)

        dur: HumNum = Convert.recipToDuration(tstring)

        if vdur is not None and vdur != dur:
            # set obj duration to vdur, and then unlink the duration, so the subsequent
            # setting of gestural/actual duration doesn't change how the note looks.
            obj.duration.quarterLength = vdur
            obj.duration.linked = False

        if isGrace:
            # set duration.type, not duration.quarterLength
            # if dur == 0 (e.g. token.text == 'aaq' with no recip data),
            # we'll just leave the default type of 'eighth' as we set it earlier.
            if dur != 0:
                # There are humdrum scores with grace notes that have tuplet-y durations,
                # but all we care about is how many flags.  So "closest type" is better
                # than crashing because there is no matching type.
                obj.duration.type = m21.duration.quarterLengthToClosestType(dur)[0]
        else:
            obj.duration.quarterLength = dur

        return dur

    '''
        _processOtherLayerToken
    '''
    def _processOtherLayerToken(
        self,
        measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        layerTok: HumdrumToken,
        staffIndex: int
    ) -> bool:
        return False

    '''
        _processSuppressedLayerToken
    '''
    def _processSuppressedLayerToken(
        self,
        measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        layerTok: HumdrumToken,
        staffIndex: int
    ) -> bool:
        # This element is not supposed to be printed,
        # probably due to being in a tremolo.
        # But first check for dynamics and text, which
        # should not be suppressed:
        vOffsetInMeasure: HumNum = opFrac(voiceOffsetInMeasure)
        insertedIntoVoice: bool = False
        if self._processDynamics(measureIndex, voice, vOffsetInMeasure, layerTok, staffIndex):
            insertedIntoVoice = True
        if self._processDirections(measureIndex, voice, vOffsetInMeasure, layerTok, staffIndex):
            insertedIntoVoice = True

        return insertedIntoVoice

    def _processDynamics(
        self,
        measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        token: HumdrumToken,
        staffIndex: int
    ) -> bool:
        insertedIntoVoice: bool = False
        dynamic: str = ''
        isGrace: bool = token.isGrace
        line: HumdrumLine = token.ownerLine
        ss: StaffStateVariables = self._staffStates[staffIndex]

        if not line:
            return insertedIntoVoice
        if token.track is None:
            return insertedIntoVoice

        vOffsetInMeasure: HumNum = opFrac(voiceOffsetInMeasure)
        dynamicOffsetInMeasure: HumNum = token.durationFromBarline
        dynamicOffsetInVoice: HumNum = opFrac(dynamicOffsetInMeasure - vOffsetInMeasure)

        measure: m21.stream.Measure | None
        newStaffIndex: int

        track: int = token.track
        lastTrack: int = track
        ttrack: int = -1
        startField: int = token.fieldIndex + 1

        forceAbove: bool = False
        forceBelow: bool = False
        forceCenter: bool = False
        trackDiff: int = 0
        staffAdj: int = ss.dynamStaffAdj
        force: bool = False  # actually force, not just prefer if unspecified

        if ss.dynamPos > 0:
            force = True
            forceAbove = True
        elif ss.dynamPos < 0:
            force = True
            forceBelow = True
        elif ss.dynamPos == 0 and ss.dynamPosDefined:
            forceCenter = True
        elif ss.hasLyrics:
            forceAbove = True

        justification: int = 0
        if token.layoutParameter('DY', 'rj') == 'true':
            justification = 1
        if token.layoutParameter('DY', 'cj') == 'true':
            justification = 2

        dcolor: str = token.layoutParameter('DY', 'color')

        needsRend: bool = bool(justification) or bool(dcolor)

        above: bool = False
        below: bool = False
        center: bool = False
#         showpos: bool = False

        # Handle 'z' in (**kern) token for subito forte (sf), or 'zz' for sforzando (sfz)
        # 'zy' or 'zzy' means it is hidden.
        if 'z' in token.text and 'zy' not in token.text:
            loc: int = token.text.index('z')
            subtrack: int = token.subTrack
            if subtrack == 1:
                above = True
                below = False
                center = False
            elif subtrack == 2:
                above = False
                below = True
                center = False

            # Now figure out if placement was specified
            hasAbove: bool
            hasBelow: bool
            hasCenter: bool
            hasAbove, staffAdj = self._hasAboveParameterStaffAdj(token, 'DY', staffAdj)
            if hasAbove:
                above = True
                below = False
                center = False
            if not above:
                hasBelow, staffAdj = self._hasBelowParameterStaffAdj(token, 'DY', staffAdj)
                if hasBelow:
                    above = False
                    below = True
                    center = False
                    if staffAdj:
                        staffAdj -= 1
                    elif force and forceBelow:
                        staffAdj = -ss.dynamStaffAdj
            if not above and not below:
                hasCenter, staffAdj = self._hasCenterParameterStaffAdj(token, 'DY', staffAdj)
                if hasCenter:
                    above = False
                    below = False
                    center = True

            # This code block should probably be deleted.
            if (self._signifiers.below
                    and loc < len(token.text) - 1
                    and token.text[loc + 1] == self._signifiers.below):
                above = False
                below = True
            if (self._signifiers.above
                    and loc < len(token.text) - 1
                    and token.text[loc + 1] == self._signifiers.above):
                above = True
                below = False

            newStaffIndex = staffIndex + staffAdj
            newStaffIndex = max(newStaffIndex, 0)
            newStaffIndex = min(newStaffIndex, self.staffCount - 1)

            measure = None
            if newStaffIndex != staffIndex:
                measure = self.getMeasureForStaff(measureIndex, newStaffIndex)

            # Here is where we create the music21 object for the sf/sfz
            dynstr: str = 'sf'
            if 'zz' in token.text:
                dynstr = 'sfz'
            m21sf: m21.dynamics.Dynamic = m21.dynamics.Dynamic(dynstr)
            if t.TYPE_CHECKING:
                assert isinstance(m21sf.style, m21.style.TextStyle)

            # Undo music21's default Dynamic absolute positioning
            m21sf.style.absoluteX = None
            m21sf.style.absoluteY = None

            if dcolor:
                m21sf.style.color = dcolor

            if justification == 1:
                m21sf.style.justify = 'right'
            elif justification == 2:
                m21sf.style.justify = 'center'

            if needsRend:
                # dynamics are set to bold (like verovio, only if other style stuff set)
                m21sf.style.fontStyle = M21Convert.m21FontStyleFromFontStyle('bold')

            if above or (force and forceAbove) or (forceAbove and not below and not center):
                if hasattr(m21sf, 'placement'):
                    m21sf.placement = 'above'
                else:
                    m21sf.style.absoluteY = 'above'
            elif below or (force and forceBelow) or (forceBelow and not above and not center):
                if hasattr(m21sf, 'placement'):
                    m21sf.placement = 'below'
                else:
                    m21sf.style.absoluteY = 'below'
            elif center or (force and forceCenter) or (forceCenter and not above and not below):
                # center means below, and vertically centered between this staff and the one below
                m21sf.style.alignVertical = 'middle'
                if hasattr(m21sf, 'placement'):
                    m21sf.placement = 'below'
                else:
                    m21sf.style.absoluteY = 'below'

            if measure is not None:
                measure.insert(dynamicOffsetInMeasure, m21sf)
            else:
                voice.coreInsert(dynamicOffsetInVoice, m21sf)
                insertedIntoVoice = True

        # now look for any **dynam tokens to the right
        active: bool = True
        for i in range(startField, line.tokenCount):
            staffAdj = ss.dynamStaffAdj
            dynTok: HumdrumToken | None = line[i]
            if t.TYPE_CHECKING:
                # dynTok is not None because i is in range
                assert isinstance(dynTok, HumdrumToken)

            exInterp: str = dynTok.dataType.text
            if exInterp != '**kern' and 'kern' in exInterp:
                active = False
            if dynTok.isKern:
                active = True
                if dynTok.track is not None:
                    ttrack = dynTok.track
                    if ttrack != track:
                        if ttrack != lastTrack:
                            trackDiff += 1
                            lastTrack = ttrack
                    if isGrace:
                        continue
                    break
                # Break if this is not the last layer for the current spine
                if not dynTok.isNull:
                    break
            if not active:
                continue
            if not dynTok.isDataType('**dynam') and not dynTok.isDataType('**dyn'):
                continue

            # Don't skip NULL tokens, because this algorithm only prints dynamics
            # after the last layer, and there could be notes in earlier layer
            # that need the dynamic.
            # if dynTok.isNull:
            #     continue

            dynTokStr: str = dynTok.text
            if dynTok.getValueBool('auto', 'DY', 'processed'):
                return insertedIntoVoice
            dynTok.setValue('auto', 'DY', 'processed', 'true')

            # int pcount = dyntok->getLinkedParameterSetCount();

            hairpins: str = ''
            letters: str = ''
            for ch in dynTokStr:
                if ch.isalpha():
                    letters += ch
                else:
                    hairpins += ch

            if re.search('^[sr]?f+z?$', letters):
                # 'sf', 'sfz', 'f', 'fff', etc
                dynamic = letters
            elif re.search('^p+$', letters):
                # 'p', 'ppp', etc
                dynamic = letters
            elif re.search('^m?(f|p)$', letters):
                # 'mf', 'mp'
                dynamic = letters
            elif re.search('^s?f+z?p+$', letters):
                # 'fp', 'sfzp', 'ffp' etc
                dynamic = letters

            if dynamic:
                staffAdj = ss.dynamStaffAdj

                dynText: str = self._getLayoutParameterWithDefaults(dynTok, 'DY', 't', '', '')
                if dynText:
                    dynText = re.sub('%s', dynamic + ' ', dynText)
                    dynamic = dynText.strip()

                above = False
                below = False
                above, staffAdj = self._hasAboveParameterStaffAdj(dynTok, 'DY', staffAdj)
                if not above:
                    below, staffAdj = self._hasBelowParameterStaffAdj(dynTok, 'DY', staffAdj)
                if not above and not below:
                    hasCenter, staffAdj = self._hasCenterParameterStaffAdj(token, 'DY', staffAdj)
                    if hasCenter:
                        above = False
                        below = False
                        center = True

                # if pcount > 0, then search for prefix and postfix text
                # to add to the dynamic.
                # std::string prefix = "aaa ";
                # std::string postfix = " bbb";
                # See https://github.com/music-encoding/music-encoding/issues/540

                justification = 0
                dcolor = ''
                needsRend = False
                if dynTok.layoutParameter('DY', 'rj') == 'true':
                    justification = 1
                elif dynTok.layoutParameter('DY', 'cj') == 'true':
                    justification = 2

                # editorial: bool = False
                editStr: str = self._getLayoutParameterWithDefaults(dynTok, 'DY', 'ed', 'true', '')
                gotOne: bool = False
                if editStr:
                    if 'brack' in editStr:
                        gotOne = True
                        dynamic = '[ ' + dynamic + ' ]'
                    elif 'paren' in editStr:
                        gotOne = True
                        dynamic = '( ' + dynamic + ' )'
                    elif 'curly' in editStr:
                        gotOne = True
                        dynamic = '{ ' + dynamic + ' }'
                    elif 'angle' in editStr:
                        gotOne = True
                        dynamic = '< ' + dynamic + ' >'

                if not gotOne:
                    parenP: str = self._getLayoutParameterWithDefaults(
                        dynTok, 'DY', 'paren', 'true', ''
                    )
                    brackP: str = self._getLayoutParameterWithDefaults(
                        dynTok, 'DY', 'brack', 'true', ''
                    )
                    curlyP: str = self._getLayoutParameterWithDefaults(
                        dynTok, 'DY', 'curly', 'true', ''
                    )
                    angleP: str = self._getLayoutParameterWithDefaults(
                        dynTok, 'DY', 'angle', 'true', ''
                    )
                    if parenP:
                        dynamic = '( ' + dynamic + ' )'
                    elif brackP:
                        dynamic = '[ ' + dynamic + ' ]'
                    elif curlyP:
                        dynamic = '{ ' + dynamic + ' }'
                    elif angleP:
                        dynamic = '< ' + dynamic + ' >'

                dcolor = dynTok.layoutParameter('DY', 'color')
                needsRend = bool(justification) or bool(dcolor)

                # Here is where we create the music21 object for the dynamic
                m21Dynamic: m21.dynamics.Dynamic = m21.dynamics.Dynamic(dynamic)
                if t.TYPE_CHECKING:
                    assert isinstance(m21Dynamic.style, m21.style.TextStyle)

                # Undo music21's default Dynamic absolute positioning
                m21Dynamic.style.absoluteX = None
                m21Dynamic.style.absoluteY = None

                if dcolor:
                    m21Dynamic.style.color = dcolor
                if justification == 1:
                    m21Dynamic.style.justify = 'right'
                elif justification == 2:
                    m21Dynamic.style.justify = 'center'

                if needsRend:
                    # dynamics are set to bold (like verovio, only if other style stuff set)
                    m21Dynamic.style.fontStyle = M21Convert.m21FontStyleFromFontStyle('bold')

                newStaffIndex = staffIndex - staffAdj
                newStaffIndex = max(newStaffIndex, 0)
                newStaffIndex = min(newStaffIndex, self.staffCount - 1)

                measure = None
                if newStaffIndex != staffIndex:
                    measure = self.getMeasureForStaff(measureIndex, newStaffIndex)

                # verticalgroup: str = dyntok.layoutParameter('DY', 'vg')
                # Q: is there a music21 equivalent to MEI's verticalgroup?
                if above or (force and forceAbove) or (forceAbove and not below and not center):
                    if hasattr(m21Dynamic, 'placement'):
                        m21Dynamic.placement = 'above'
                    else:
                        m21Dynamic.style.absoluteY = 'above'
                elif below or (force and forceBelow) or (forceBelow and not above and not center):
                    if hasattr(m21Dynamic, 'placement'):
                        m21Dynamic.placement = 'below'
                    else:
                        m21Dynamic.style.absoluteY = 'below'
                elif center or (force and forceCenter) or (
                        forceCenter and not above and not below):
                    # center means below, and vertically centered between
                    # this staff and the one below
                    m21Dynamic.style.alignVertical = 'middle'
                    if hasattr(m21Dynamic, 'placement'):
                        m21Dynamic.placement = 'below'
                    else:
                        m21Dynamic.style.absoluteY = 'below'

                if measure is not None:
                    measure.insert(dynamicOffsetInMeasure, m21Dynamic)
                else:
                    voice.coreInsert(dynamicOffsetInVoice, m21Dynamic)
                    insertedIntoVoice = True

            if hairpins:
                if self._processHairpin(
                        measureIndex,
                        voice,
                        voiceOffsetInMeasure,
                        dynamicOffsetInVoice,
                        hairpins,
                        token,
                        dynTok,
                        staffIndex):
                    insertedIntoVoice = True

        # No more need for the following recursive call to _processDynamics:
        # // re-run this function on null tokens after the main note since
        # // there may be dynamics unattached to a note (for various often
        # // legitimate reasons).  Maybe make this more efficient later, such as
        # // do a separate parse of dynamics data in a different loop.

        # Instead I now leave null data tokens in the layerData, and process
        # them just like suppressed tokens: directions/dynamics only. --gregc
        return insertedIntoVoice

    def _processHairpin(
        self,
        measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        dynamicOffsetInVoice: HumNumIn,
        hairpins: str,
        token: HumdrumToken,
        dynTok: HumdrumToken,
        staffIndex: int
    ) -> bool:
        insertedIntoVoice: bool = False

        if '<' in hairpins:
            startHairpin = '<'
            stopHairpin = '['
            stopAtEndHairpin = '[['
        elif '>' in hairpins:
            startHairpin = '>'
            stopHairpin = ']'
            stopAtEndHairpin = ']]'
        else:
            return insertedIntoVoice

        startStopHairpin1 = startHairpin + stopHairpin
        startStopHairpin2 = startHairpin + ' ' + stopHairpin

        ss: StaffStateVariables = self._staffStates[staffIndex]
        forceAbove: bool = False
        forceBelow: bool = False
        forceCenter: bool = False
        force: bool = False  # actually force, not just prefer if unspecified
        if ss.dynamPos > 0:
            forceAbove = True
            force = True
        elif ss.dynamPos < 0:
            forceBelow = True
            force = True
        elif ss.dynamPos == 0 and ss.dynamPosDefined:
            forceCenter = True
        elif ss.hasLyrics:
            forceAbove = True

        endAtEndOfEndToken: bool = False
        endTok: HumdrumToken | None = None
        leftNoteDuration: HumNum = 0.
        if startStopHairpin1 in hairpins or startStopHairpin2 in hairpins:
            leftNoteDuration = self._getLeftNoteDuration(token)
            endTok = token
            endAtEndOfEndToken = True
        else:
            endTok = self._getHairpinEnd(dynTok, stopHairpin)

        staffAdj = ss.dynamStaffAdj
        above: bool = False
        below: bool = False
        center: bool = False
        above, staffAdj = self._hasAboveParameterStaffAdj(dynTok, 'HP', staffAdj)
        if not above:
            below, staffAdj = self._hasBelowParameterStaffAdj(dynTok, 'HP', staffAdj)
        if not above and not below:
            hasCenter, staffAdj = self._hasCenterParameterStaffAdj(dynTok, 'HP', staffAdj)
            if hasCenter:
                above = False
                below = False
                center = True

        if endTok:
            # Here is where we create the music21 object for the crescendo/decrescendo
            m21Hairpin: m21.dynamics.DynamicWedge
            if startHairpin == '<':
                m21Hairpin = m21.dynamics.Crescendo()
            else:
                m21Hairpin = m21.dynamics.Diminuendo()

            newStaffIndex = staffIndex - staffAdj
            newStaffIndex = max(newStaffIndex, 0)
            newStaffIndex = min(newStaffIndex, self.staffCount - 1)

            m21Hairpin.humdrum_staff_index = newStaffIndex  # type: ignore

            # here we always want measure, even if newStaffIndex == staffIndex,
            # because we like putting fake spanned objects up in the measure.
            measure = self.getMeasureForStaff(measureIndex, newStaffIndex)

            if center or (force and forceCenter) or (forceCenter and not above and not below):
                # center means below, and vertically centered between this staff and the one below
                if t.TYPE_CHECKING:
                    assert isinstance(m21Hairpin.style, m21.style.TextStyle)
                m21Hairpin.style.alignVertical = 'middle'
                if hasattr(m21Hairpin, 'placement'):
                    m21Hairpin.placement = 'below'
                else:
                    m21Hairpin.style.absoluteY = 'below'
            elif above or (force and forceAbove) or (forceAbove and not below and not center):
                if hasattr(m21Hairpin, 'placement'):
                    m21Hairpin.placement = 'above'
                else:
                    m21Hairpin.style.absoluteY = 'above'
            elif below or (force and forceBelow) or (forceBelow and not above and not center):
                if hasattr(m21Hairpin, 'placement'):
                    m21Hairpin.placement = 'below'
                else:
                    m21Hairpin.style.absoluteY = 'below'

            color = self._getLoColor(dynTok, 'HP')
            if color:
                m21Hairpin.style.color = color

            # Now I need to put the start and end "notes" into the Crescendo spanner.
            # This is instead of all the timestamp stuff C++ code does.
            startTime: HumNum = token.durationFromStart
            endTime: HumNum
            if leftNoteDuration > 0:
                endTime = endTok.durationFromStart + leftNoteDuration
            else:
                endTime = endTok.durationFromStart

            if (leftNoteDuration == 0
                    and (endAtEndOfEndToken or stopAtEndHairpin in endTok.text)):
                endTime += endTok.ownerLine.duration

            startNoteToken: HumdrumToken | None = (
                self._getNearbyNoteTokenWithAppropriateTimestamp(
                    token,
                    startTime,
                    start=True
                )
            )
            endNoteToken: HumdrumToken | None = (
                self._getNearbyNoteTokenWithAppropriateTimestamp(
                    endTok,
                    endTime,
                    start=False
                )
            )

            startNote: m21.Music21Object | None = None
            if startNoteToken:
                startNote = self._getGeneralNoteOrPlaceHolder(startNoteToken)
            else:
                # couldn't find a startNote, so use a spannerAnchor instead
                startNote = m21.spanner.SpannerAnchor()
                measure.insert(
                    opFrac(voiceOffsetInMeasure + dynamicOffsetInVoice),
                    startNote
                )

            endNote: m21.Music21Object | None = None
            if endNoteToken:
                endNote = self._getGeneralNoteOrPlaceHolder(endNoteToken)
            else:
                # couldn't find a endNote, so use a spannerAnchor instead
                endNote = m21.spanner.SpannerAnchor()

                # compute measures to skip and offset2 (in that final measure)
                offset2: HumNum
                if leftNoteDuration > 0:
                    offset2 = self._getMeasureOffset(dynTok, leftNoteDuration)
                else:
                    offset2 = self._getMeasureOffset(endTok, 0)
                if (leftNoteDuration == 0
                        and (endAtEndOfEndToken or stopAtEndHairpin in endTok.text)):
                    offset2 += endTok.ownerLine.duration
                measuresFromNow: int = self._getMeasureDifference(dynTok, endTok)
                endMeasureIndex: int = measureIndex + measuresFromNow
                endMeasure: m21.stream.Measure = self.getMeasureForStaff(
                    endMeasureIndex, newStaffIndex
                )
                endMeasure.insert(offset2, endNote)

            if startNote is not None and endNote is not None:
                # should always be True, but hard to prove statically
                m21Hairpin.addSpannedElements(startNote, endNote)
                self.m21Score.coreInsert(0, m21Hairpin)
                self.m21Score.coreElementsChanged()
            else:
                print('Warning: Failed to find/create start or end of DynamicWedge',
                        file=sys.stderr)
        else:
            # no endpoint so print as the word "cresc."/"decresc."
            # (modified by _signifiers and layout)
            content: str = ''
            fontStyle: str = ''

            # default
            if startHairpin == '<':
                content = 'cresc.'
            else:
                content = 'decresc.'

            # override with RDF signifiers
            if startHairpin == '<' and self._signifiers.crescText:
                content = self._signifiers.crescText
                fontStyle = self._signifiers.crescFontStyle
            elif startHairpin == '>' and self._signifiers.decrescText:
                content = self._signifiers.decrescText
                fontStyle = self._signifiers.decrescFontStyle

#             # This is a weird thing that I am doing only to avoid some diff warnings.
#             # Once I can remove my MEI parser's "default is italic" code (which I can
#             # do when Verovio stops writing "unspecified italics" when italics was
#             # actually specified; see https://github.com/rism-digital/verovio/issues/3074),
#             # then I can also remove this...
#             if not fontStyle:
#                 fontStyle = 'italic'

            pinText = self._getLayoutParameterWithDefaults(dynTok, 'HP', 't', '', '')
            if pinText:
                html.unescape(pinText)
                if pinText:
                    pinText = re.sub('%s', content, pinText)
                    pinText = pinText.replace(r'\n', '\n')
                    content = pinText

            m21TextExp: m21.expressions.TextExpression = m21.expressions.TextExpression(content)
            if t.TYPE_CHECKING:
                assert isinstance(m21TextExp.style, m21.style.TextStyle)

            if fontStyle:
                m21TextExp.style.fontStyle = M21Convert.m21FontStyleFromFontStyle(fontStyle)

            newStaffIndex = staffIndex - staffAdj
            newStaffIndex = max(newStaffIndex, 0)
            newStaffIndex = min(newStaffIndex, self.staffCount - 1)

            measure = None
            if newStaffIndex != staffIndex:
                measure = self.getMeasureForStaff(measureIndex, newStaffIndex)

            if center or (force and forceCenter) or (forceCenter and not above and not below):
                # center means below, and vertically centered between this staff and the one below
                m21TextExp.style.alignVertical = 'middle'
                if hasattr(m21TextExp, 'placement'):
                    m21TextExp.placement = 'below'
                else:
                    m21TextExp.style.absoluteY = 'below'
            elif above or (force and forceAbove) or (forceAbove and not below and not center):
                if hasattr(m21TextExp, 'placement'):
                    m21TextExp.placement = 'above'
                else:
                    m21TextExp.style.absoluteY = 'above'
            elif below or (force and forceBelow) or (forceBelow and not above and not center):
                if hasattr(m21TextExp, 'placement'):
                    m21TextExp.placement = 'below'
                else:
                    m21TextExp.style.absoluteY = 'below'

            if measure is not None:
                measure.insert(dynamicOffsetInVoice, m21TextExp)
            else:
                voice.coreInsert(dynamicOffsetInVoice, m21TextExp)
                insertedIntoVoice = True

        return insertedIntoVoice

    @staticmethod
    def _getMeasureDifference(startTok: HumdrumToken, endTok: HumdrumToken) -> int:
        if startTok.ownerLine is None:
            return 0

        file: HumdrumFile | None = startTok.ownerLine.ownerFile
        if file is None:
            return 0

        startLine: int = startTok.lineIndex
        endLine: int = endTok.lineIndex
        counter: int = 0
        for i in range(startLine, endLine + 1):
            line: HumdrumLine | None = file[i]
            if line is not None and line.isBarline:
                counter += 1

        return counter

    @staticmethod
    def _getMeasureOffset(token: HumdrumToken, extraOffset: HumNum) -> HumNum:
        offset: HumNum = token.durationFromBarline + extraOffset
        return offset

    '''
    //////////////////////////////
    //
    // HumdrumInput::getLeftNoteDuration --
    '''
    def _getLeftNoteDuration(self, token: HumdrumToken) -> HumNum:
        output: HumNum = opFrac(0)
        current: HumdrumToken | None = token
        while current is not None:
            if not current.isKern:
                current = current.previousFieldToken
                continue
            if current.isNull:
                current = current.previousFieldToken
                continue

            output = Convert.recipToDuration(current.text)
            break

        return output

    @staticmethod
    def _getLeftNoteToken(token: HumdrumToken, _isStart: bool) -> HumdrumToken | None:
        # Look left for a non-null data token within the track's kern fields
        output: HumdrumToken | None = None
        current: HumdrumToken | None = None
        if token.isDataType('**dynam'):
            # we must first find the first kern token to the left before scanning
            current = token
            while current and not current.isKern:
                current = current.previousFieldToken

        if current is None:
            return None
        if current.track is None:
            return None

        ttrack: int = current.track
#         tStartTok: HumdrumToken = self._staffStarts[self._staffStartsIndexByTrack[ttrack]]
#         tpart: int = self._getPartNumberLabel(tStartTok)

        while current is not None:
            # startTok: HumdrumToken = (
            #     self._staffStarts[self._staffStartsIndexByTrack[current.track]]
            # )
            # part: int = self._getPartNumberLabel(startTok)
            # if part != tpart:
            if current.track != ttrack:
                break
            if not current.isKern:
                break
            if current.isNonNullData and not current.getValueBool('auto', 'suppress'):
                # don't use a suppressed token, no note will be generated from it
                # (it's probably a note in the middle of a tremolo)
                output = current
                break
            current = current.previousFieldToken

        return output

    @staticmethod
    def _getRightNoteToken(token: HumdrumToken, _isStart: bool) -> HumdrumToken | None:
        # Look right for a non-null data token within the track's kern fields
        output: HumdrumToken | None = None
        if not token.isKern:
            # there are no interesting kern tokens to the right (only to the left)
            return None
        if token.track is None:
            return None

        ttrack: int = token.track
#         tStartTok: HumdrumToken = self._staffStarts[self._staffStartsIndexByTrack[ttrack]]
#         tpart: int = self._getPartNumberLabel(tStartTok)

        current: HumdrumToken | None = token
        while current is not None:
            # startTok: HumdrumToken = (
            #     self._staffStarts[self._staffStartsIndexByTrack[current.track]]
            # )
            # part: int = self._getPartNumberLabel(startTok)
            # if part != tpart:
            if current.track != ttrack:
                break
            if not current.isKern:
                break
            if current.isNonNullData and not current.getValueBool('auto', 'suppress'):
                # don't use a suppressed token, no note will be generated from it
                # (it's probably a note in the middle of a tremolo)
                output = current
                break
            current = current.nextFieldToken

        return output

    def _hasAppropriateTimestamp(
        self,
        token: HumdrumToken,
        timestamp: HumNumIn,
        start: bool
    ) -> bool:
        ts: HumNum = opFrac(timestamp)
        return self._getAppropriateTimestamp(token, start) == ts

    @staticmethod
    def _getAppropriateTimestamp(token: HumdrumToken, start: bool) -> HumNum:
        if start:
            return token.durationFromStart
        return opFrac(token.durationFromStart + token.duration)

    def _getNearbyNoteTokenWithAppropriateTimestamp(
        self,
        token: HumdrumToken,
        timestamp: HumNumIn,
        start: bool
    ) -> HumdrumToken | None:
        # look left, then right (within the track)
        # Then, look up (left and right within the track) until you've passed the
        # timestamp
        # Then, look down (left and right within the track) until you've passed the
        # timestamp
        ts: HumNum = opFrac(timestamp)
        output: HumdrumToken | None = self._getLeftNoteToken(token, start)
        if output is not None and self._hasAppropriateTimestamp(output, ts, start):
            return output

        output = self._getRightNoteToken(token, start)
        if output is not None and self._hasAppropriateTimestamp(output, ts, start):
            return output

        # start walking up the file until we pass the timestamp, looking left and right
        leftIsDone: bool = False
        rightIsDone: bool = False

        leftTimestamp: HumNum
        rightTimestamp: HumNum

        current = token.previousToken0
        while current is not None:
            if current.isInterpretation or current.isComment or current.isBarline:
                current = current.previousToken0
                continue

            if not leftIsDone:
                output = self._getLeftNoteToken(current, start)
                if output:
                    leftTimestamp = self._getAppropriateTimestamp(output, start)
                    if leftTimestamp == ts:
                        return output
                    if leftTimestamp < ts:
                        # we've passed the left timestamp we were looking for
                        leftIsDone = True

            if not rightIsDone:
                output = self._getRightNoteToken(current, start)
                if output:
                    rightTimestamp = self._getAppropriateTimestamp(output, start)
                    if rightTimestamp == ts:
                        return output
                    if rightTimestamp < ts:
                        # we've passed the right timestamp we were looking for
                        rightIsDone = True

            if rightIsDone and leftIsDone:
                break

            current = current.previousToken0

        # didn't find anything earlier, try later
        leftIsDone = False
        rightIsDone = False

        current = token.nextToken0
        while current is not None:
            if current.isInterpretation or current.isComment or current.isBarline:
                current = current.nextToken0
                continue

            if not leftIsDone:
                output = self._getLeftNoteToken(current, start)
                if output:
                    leftTimestamp = self._getAppropriateTimestamp(output, start)
                    if leftTimestamp == ts:
                        return output
                    if leftTimestamp < ts:
                        # we've passed the left timestamp we were looking for
                        leftIsDone = True

            if not rightIsDone:
                output = self._getRightNoteToken(current, start)
                if output:
                    rightTimestamp = self._getAppropriateTimestamp(output, start)
                    if rightTimestamp == ts:
                        return output
                    if rightTimestamp > ts:
                        # we've passed the right timestamp we were looking for
                        rightIsDone = True

            if rightIsDone and leftIsDone:
                break

            current = current.nextToken0

        return None


    '''
    //////////////////////////////
    //
    // HumdrumInput::getHairpinEnd --
    '''
    @staticmethod
    def _getHairpinEnd(token: HumdrumToken, endChar: str) -> HumdrumToken | None:
        if not token:
            return None

        endToken: HumdrumToken | None = token.getNextNonNullDataToken(0)

        while endToken:
            isBadToken: bool = False
            if endChar in endToken.text:
                return endToken

            for ch in endToken.text:
                if ch.isalpha():
                    isBadToken = True
                elif ch == '<':
                    isBadToken = True
                elif ch == '>':
                    isBadToken = True

                if isBadToken:
                    # maybe return the bad token for a weak ending
                    # to a hairpin...
                    return None

            endToken = endToken.getNextNonNullDataToken(0)

        return None

    '''
    //////////////////////////////
    //
    // HumdrumInput::processDirections --
        returns whether or not it inserted something in the voice
    '''
    def _processDirections(
        self,
        measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        token: HumdrumToken,
        staffIndex: int
    ) -> bool:
        insertedIntoVoice: bool = False

        vOffsetInMeasure: HumNum = opFrac(voiceOffsetInMeasure)
        lcount = token.linkedParameterSetCount
        for i in range(0, lcount):
            if self._processLinkedDirection(
                    i, measureIndex, voice, vOffsetInMeasure, token, staffIndex):
                insertedIntoVoice = True

        text: str | None = token.getValueString('LO', 'TX', 't')
        if not text:
            return insertedIntoVoice

        text = html.unescape(text)
        text = text.replace(r'\n', '\n')
        if not text:
            return insertedIntoVoice

        # justification == 0 means no explicit justification (mostly left justified)
        # justification == 1 means right justified
        # justification == 2 means center justified
        justification: int = 0
        if token.isDefined('LO', 'TX', 'rj'):
            justification = 1
        if token.isDefined('LO', 'TX', 'cj'):
            justification = 2

        zparam: bool = token.isDefined('LO', 'TX', 'Z')
        yparam: bool = token.isDefined('LO', 'TX', 'Y')

        aparam: bool = token.isDefined('LO', 'TX', 'a')  # place above staff
        bparam: bool = False
        cparam: bool = False
        if not aparam:
            bparam = token.isDefined('LO', 'TX', 'b')  # place below staff
        if not aparam and not bparam:
            cparam = token.isDefined('LO', 'TX', 'c')  # place below staff, centered with next one

        # default font for text string (later check for embedded fonts)
        italic: bool = False
        bold: bool = False

        vgroup: int = -1
        if token.isDefined('LO', 'TX', 'vgrp'):
            vgroup = token.getValueInt('LO', 'TX', 'vgrp')

        if token.isDefined('LO', 'TX', 'i'):  # italic
            italic = True
        if token.isDefined('LO', 'TX', 'B'):  # bold
            bold = True
        if token.isDefined('LO', 'TX', 'bi'):  # bold-italic
            bold = True
            italic = True
        if token.isDefined('LO', 'TX', 'ib'):  # bold-italic
            bold = True
            italic = True
        if token.isDefined('LO', 'TX', 'Bi'):  # bold-italic
            bold = True
            italic = True
        if token.isDefined('LO', 'TX', 'iB'):  # bold-italic
            bold = True
            italic = True

        color: str | None = token.getValueString('LO', 'TX', 'color')

        placement: str = ''
        if aparam:
            placement = 'above'
        elif bparam:
            placement = 'below'
        elif cparam:
            placement = 'between'
        elif zparam:
            Z: int = token.getValueInt('LO', 'TX', 'Z')
            if Z >= 0:
                placement = 'above'
            else:
                placement = 'below'
        elif yparam:
            Y: int = token.getValueInt('LO', 'TX', 'Y')
            if Y >= 0:
                placement = 'below'
            else:
                placement = 'above'

        if self._addDirection(text, placement, bold, italic, measureIndex, voice, vOffsetInMeasure,
                              token, justification, color, vgroup):
            insertedIntoVoice = True

        return insertedIntoVoice

    '''
    //////////////////////////////
    //
    // HumdrumInput::processLinkedDirection --
    '''
    def _processLinkedDirection(
        self,
        index: int,
        _measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        token: HumdrumToken,
        staffIndex: int
    ) -> bool:
        insertedIntoVoice: bool = False

        vOffsetInMeasure: HumNum = opFrac(voiceOffsetInMeasure)
        direction: m21.expressions.TextExpression | None = None
        tempo: m21.tempo.MetronomeMark | None = None

        isGlobal: bool = token.linkedParameterIsGlobal(index)
        isFirst: bool = True
        if isGlobal:
            isFirst = self._isFirstTokenOnStaff(token)

        if not isFirst:
            # Don't insert multiple global directions per staff (see below where we
            # additionally only put a global direction in one particular staff).
            return insertedIntoVoice

        hps: HumParamSet | None = token.getLinkedParameterSet(index)
        if hps is None:
            return insertedIntoVoice

        if hps.namespace1 != 'LO':
            return insertedIntoVoice

        namespace2: str = hps.namespace2
        isText: bool = namespace2 == 'TX'
        isSic: bool = namespace2 == 'SIC'
        _vgroup: int = -1

        if not isText and not isSic:
            # not a text direction so ignore
            return insertedIntoVoice

        # default font for text string (later check for embedded fonts)
        italic: bool = False
        bold: bool = False
        zparam: bool = False
        yparam: bool = False
        aparam: bool = False
        bparam: bool = False
        cparam: bool = False

        # maybe add center justification as an option later
        # justification == 0 means no explicit justification (mostly left justified)
        # justification == 1 means right justified
        # justification == 2 means center justified
        justification: int = 0

# NOPE: merge new iohumdrum.cpp changes --gregc 01July2021
# Actually, I don't want to change to right justification just because of where the text is.
# Accuracy over prettiness during export. -- gregc
#     if (token->isBarline()) {
#         hum::HumNum startdur = token->getDurationFromStart();
#         hum::HumdrumFile *hfile = token->getOwner()->getOwner();
#         hum::HumNum totaldur = (*hfile)[hfile->getLineCount() - 1].getDurationFromStart();
#         if (startdur == totaldur) {
#             justification = 1;
#         }
#     }

        color: str = ''
        if isSic:
            # default color for sic text directions (set to black if not wanted)
            color = 'limegreen'

        isProblem: bool = False
        isVerbose: bool = False
        isTempo: bool = False
        text: str = ''
        key: str = ''
        value: str = ''
        _typeValue: str = ''
        verboseType: str = ''
        ovalue: str = ''
        svalue: str = ''
        placement: str = ''

        for i in range(0, hps.count):
            key = hps.getParameterName(i)
            value = hps.getParameterValue(i)
            if key == 'a':
                aparam = True
            elif key == 'b':
                bparam = True
            elif key == 'c':
                cparam = True
            elif key == 't':
                text = value
                if not text:
                    # nothing to display
                    return insertedIntoVoice
            elif key == 'Y':
                yparam = True
            elif key == 'Z':
                zparam = True
            elif key == 'i':
                italic = True
            elif key == 'B':
                bold = True
            elif key in ('Bi', 'bi', 'iB', 'ib'):
                italic = True
                bold = True
            elif key == 'rj':
                justification = 1
            elif key == 'cj':
                justification = 2
            elif key == 'color':
                color = value
            elif key == 'v':
                isVerbose = True
                verboseType = value
            elif key == 'o':
                ovalue = value
            elif key == 's':
                svalue = value
            elif key == 'problem':
                isProblem = True
            elif key == 'type':
                _typeValue = value
            elif key == 'tempo':
                isTempo = True
            elif key == 'vgrp':
                if value and value[0].isdigit():
                    _vgroup = int(value)

        if namespace2 == 'SIC' and not isVerbose:
            return insertedIntoVoice

        if aparam:
            placement = 'above'
        elif bparam:
            placement = 'below'
        elif cparam:
            placement = 'between'
        elif zparam:
            Z: int = token.getValueInt('LO', 'TX', 'Z')
            if Z >= 0:
                placement = 'above'
            else:
                placement = 'below'
        elif yparam:
            Y: int = token.getValueInt('LO', 'TX', 'Y')
            if Y >= 0:
                placement = 'below'
            else:
                placement = 'above'
        else:
            # default to 'above' to match Verovio
            placement = 'above'

        if isSic:
            if verboseType == 'text':
                if ovalue:
                    text = ovalue
                elif svalue:
                    text = svalue
                else:
                    text = 'S'
            else:
                text = 'S'

        text = html.unescape(text)
        text = text.replace(r'\n', '\n')
        text = text.strip()

        maxStaff: int = len(self._staffStarts) - 1

        if token.linkedParameterIsGlobal(index):
            if placement == 'below' and staffIndex != maxStaff:
                # For system-text, do not place on any staff except the bottom staff.
                # This will probably change in the future to place at the bottom
                # of each staff group only.
                return insertedIntoVoice
            if placement == 'above' and staffIndex != 0:
                # For system-text, do not place on any staff except the top staff.
                # This will probably change in the future to place at the top
                # of each staff group only.
                return insertedIntoVoice

        tempoOrDirection: m21.tempo.MetronomeMark | m21.expressions.TextExpression | None = None

        if self._isTempoish(text):
            tempo = self._createMetronomeMark(text, token)
            tempoOrDirection = tempo

        if tempoOrDirection is None:
            if token.isTimeSignature:
                # Special case for !!LO:TX just before time sig (always considered a tempo)
                tempo = self._createMetronomeMark(text, token)
                tempoOrDirection = tempo

        if tempoOrDirection is None:
            if isTempo:
                midiBPM: int = self._getMmTempo(token)
                if midiBPM == 0:
                    # this is a redundant tempo message, so ignore (even as text dir)
                    return insertedIntoVoice

                tempo = self._myMetronomeMarkInit(number=midiBPM)
                tempoOrDirection = tempo

        if tempoOrDirection is None:
            direction = m21.expressions.TextExpression(text)
            tempoOrDirection = direction

        if t.TYPE_CHECKING:
            assert isinstance(tempoOrDirection.style, m21.style.TextStyle)

        if placement:
            if placement == 'between':
                placement = 'below'
                tempoOrDirection.style.alignVertical = 'middle'

            if direction:
                direction.placement = placement
            elif tempo:
                if placement in ('above', 'below'):
                    tempo.placement = placement  # type: ignore

        if color:
            tempoOrDirection.style.color = color
        elif isProblem:
            tempoOrDirection.style.color = 'red'
        elif isSic:
            tempoOrDirection.style.color = 'limegreen'

        if bold and italic:
            tempoOrDirection.style.fontStyle = M21Convert.m21FontStyleFromFontStyle('bold-italic')
        elif italic:
            tempoOrDirection.style.fontStyle = M21Convert.m21FontStyleFromFontStyle('italic')
        elif bold:
            tempoOrDirection.style.fontStyle = M21Convert.m21FontStyleFromFontStyle('bold')
        elif tempo:
            # default tempo to bold
            tempoOrDirection.style.fontStyle = M21Convert.m21FontStyleFromFontStyle('bold')

        if justification == 1:
            tempoOrDirection.style.justify = 'right'
        elif justification == 2:
            tempoOrDirection.style.justify = 'center'

        tempoOrDirectionOffsetInMeasure: HumNum = token.durationFromBarline
        tempoOrDirectionOffsetInVoice: HumNum = opFrac(
            tempoOrDirectionOffsetInMeasure - vOffsetInMeasure
        )
        voice.coreInsert(tempoOrDirectionOffsetInVoice, tempoOrDirection)
        insertedIntoVoice = True

        return insertedIntoVoice

    '''
    //////////////////////////////
    //
    // HumdrumInput::isFirstTokenOnStaff -- Used to control global
    //     directions: only one token will be used to generate a direction.
    '''
    @staticmethod
    def _isFirstTokenOnStaff(token: HumdrumToken) -> bool:
        if token.track is None:
            return False
        target: int = token.track
        track: int | None
        tok: HumdrumToken | None = token.previousFieldToken
        while tok is not None:
            track = tok.track
            if track != target:
                return True
            if not tok.isNull:  # if tok.isNull, we need to check further
                return False
            tok = tok.previousFieldToken
        return True

    '''
    //////////////////////////////
    //
    // HumdrumInput::addDirection --
    //     default value: color = "";
    //
    //     TODO: token.layoutParameter() should not be used in this function.  Instead
    //     paste the parameter set that generate a text direction (there could be multiple
    //     text directions attached to the note, and using getPayoutParameter() will merge
    //     all of their parameters incorrectly.
    '''
    def _addDirection(
        self,
        text: str,
        placement: str,
        bold: bool,
        italic: bool,
        _measureIndex: int,
        voice: m21.stream.Voice,
        voiceOffsetInMeasure: HumNumIn,
        token: HumdrumToken,
        justification: int,
        color: str | None,
        _vgroup: int
    ) -> bool:
        vOffsetInMeasure: HumNum = opFrac(voiceOffsetInMeasure)
        tempo: m21.tempo.MetronomeMark | None = None
        direction: m21.expressions.TextExpression | None = None
        tempoOrDirection: m21.tempo.MetronomeMark | m21.expressions.TextExpression | None = None

        text = html.unescape(text)
        text = text.replace(r'\n', '\n')

        if self._isTempoish(text):
            tempo = self._createMetronomeMark(text, token)
            tempoOrDirection = tempo

        if tempoOrDirection is None:
            direction = m21.expressions.TextExpression(text)
            tempoOrDirection = direction

        if t.TYPE_CHECKING:
            assert isinstance(tempoOrDirection.style, m21.style.TextStyle)

        isProblem: bool = False
        problem: str = token.layoutParameter('TX', 'problem')
        if problem == 'true':
            isProblem = True

        isSic: bool = False
        sic: str = token.layoutParameter('SIC', 'sic')
        if sic == 'true':
            isSic = True

        # convert to HPS input value in the future:
        _typeValue: str = token.layoutParameter('TX', 'type')
        if _typeValue:
            pass  # appendType(direction, typeValue)

        if placement:  # we do nothing with placement None or ''
            if placement == 'between':
                placement = 'below'
                tempoOrDirection.style.alignVertical = 'middle'

            if direction:
                # TextExpression got .placement in music21 v7
                direction.placement = placement
            elif tempo:
                if placement in ('above', 'below'):
                    tempo.placement = placement  # type: ignore

        if color:
            tempoOrDirection.style.color = color
        elif isProblem:
            tempoOrDirection.style.color = 'red'
        elif isSic:
            tempoOrDirection.style.color = 'limegreen'

        if bold and italic:
            tempoOrDirection.style.fontStyle = M21Convert.m21FontStyleFromFontStyle('bold-italic')
        elif italic:
            tempoOrDirection.style.fontStyle = M21Convert.m21FontStyleFromFontStyle('italic')
        elif bold:
            tempoOrDirection.style.fontStyle = M21Convert.m21FontStyleFromFontStyle('bold')

        if justification == 1:
            tempoOrDirection.style.justify = 'right'
        elif justification == 2:
            tempoOrDirection.style.justify = 'center'

        tempoOrDirectionOffsetInMeasure: HumNum = token.durationFromBarline
        tempoOrDirectionOffsetInVoice: HumNum = opFrac(
            tempoOrDirectionOffsetInMeasure - vOffsetInMeasure
        )
        voice.coreInsert(tempoOrDirectionOffsetInVoice, tempoOrDirection)
        return True

    def prevTokenIncludingGlobalToken(self, token: HumdrumToken) -> HumdrumToken | None:
        # try for previous token, else first token on previous line (even if global)
        prevTok: HumdrumToken | None = token.previousToken0
        if prevTok is not None:
            return prevTok

        prevLineIdx: int = token.ownerLine.lineIndex - 1
        if prevLineIdx < 0:
            return None

        prevLine: HumdrumLine | None = self[prevLineIdx]
        if not prevLine:
            return None

        return prevLine[0]

    def nextTokenIncludingGlobalToken(self, token: HumdrumToken) -> HumdrumToken | None:
        # try for next token, else first token on next line (even if global)
        nextTok: HumdrumToken | None = token.nextToken0
        if nextTok is not None:
            return nextTok

        nextLineIdx: int = token.ownerLine.lineIndex + 1
        if nextLineIdx >= self.lineCount:
            return None

        nextLine: HumdrumLine | None = self[nextLineIdx]
        if not nextLine:
            return None

        return nextLine[0]

    '''
    //////////////////////////////
    //
    // HumdrumInput::getMmTempo -- return any *MM# tempo value before or at the input token,
    //     but before any data.
    //     Returns 0 if no tempo is found.
    '''
    def _getMmTempo(self, token: HumdrumToken | None) -> int:
        current: HumdrumToken | None = token

        if current and current.isData:
            current = current.previousToken0

        while current and not current.isData:
            if current.isInterpretation:
                m = re.search(r'^\*MM(\d+\.?\d*)', current.text)
                if m:
                    isLast: bool = self._isLastStaffTempo(current)
                    if not isLast:
                        return 0
                    tempo: float = float(m.group(1))
                    return int(tempo + 0.5)
            current = current.previousToken0

        return 0

    def _getMmTempoBeforeOMD(self, token: HumdrumToken | None) -> int:
        current: HumdrumToken | None = token

        if current and current.isData:
            current = self.prevTokenIncludingGlobalToken(current)

        while current and not current.isData:
            if current.isTempo:
                return current.tempoBPM
            current = self.prevTokenIncludingGlobalToken(current)

        return 0

    '''
    //////////////////////////////
    //
    // HumdrumInput::getMmTempoForward -- return any *MM# tempo value before or at the input token,
    //     but before any data.
    //     Returns 0.0 if no tempo is found.
        Actually returns any *MM# tempo value at or after the input token,
        and returns 0 if nothing found.
    '''
    def _getMmTempoForward(self, token: HumdrumToken | None) -> tuple[int, HumdrumToken | None]:
        current: HumdrumToken | None = token
        if current and current.isData:
            current = self.nextTokenIncludingGlobalToken(current)

        while current and not current.isData:
            if current.isTempo:
                return current.tempoBPM, current
            current = self.nextTokenIncludingGlobalToken(current)

        return 0, None

    '''
        _myMetronomeMarkInit: calls m21.tempo.MetronomeMark() and then puts the style back to
        regular TextStyle defaults.
    '''
    @staticmethod
    def _myMetronomeMarkInit(
        text=None,
        number=None,
        referent=None,
        parentheses=False
    ) -> m21.tempo.MetronomeMark:
        mm = m21.tempo.MetronomeMark(text=text,
                                     number=number,
                                     referent=referent,
                                     parentheses=parentheses)

        mm.numberImplicit = True  # even though it might be explicit, we don't want it shown

        if mm.hasStyleInformation:
            # undo music21's weird TempoText style defaults
            # and just go with music21's normal TextStyle defaults
            if t.TYPE_CHECKING:
                assert isinstance(mm.style, m21.style.TextStyle)

            defaultStyle = m21.style.TextStyle()

            # fields from class Style

            # pylint: disable=protected-access
            mm.style.size = defaultStyle.size
            mm.style.relativeX = defaultStyle.relativeX
            mm.style.relativeY = defaultStyle.relativeY
            mm.style.absoluteX = defaultStyle.absoluteX
            mm.style._absoluteY = defaultStyle._absoluteY
            mm.style._enclosure = defaultStyle._enclosure
            mm.style.fontRepresentation = defaultStyle.fontRepresentation
            mm.style.color = defaultStyle.color
            mm.style.units = defaultStyle.units
            mm.style.hideObjectOnPrint = defaultStyle.hideObjectOnPrint

            # fields from class TextStyle

            mm.style._fontFamily = defaultStyle._fontFamily
            mm.style._fontSize = defaultStyle._fontSize
            mm.style._fontStyle = defaultStyle._fontStyle
            mm.style._fontWeight = defaultStyle._fontWeight
            mm.style._letterSpacing = defaultStyle._letterSpacing
            mm.style.lineHeight = defaultStyle.lineHeight
            mm.style.textDirection = defaultStyle.textDirection
            mm.style.textRotation = defaultStyle.textRotation
            mm.style.language = defaultStyle.language
            mm.style.textDecoration = defaultStyle.textDecoration
            mm.style._justify = defaultStyle._justify
            mm.style._alignHorizontal = defaultStyle._alignHorizontal
            mm.style._alignVertical = defaultStyle._alignVertical
            # pylint: enable=protected-access

        return mm

    def _createMetronomeMark(
        self,
        text: str,
        tokenOrBPM: HumdrumToken | int
    ) -> m21.tempo.MetronomeMark | None:
        token: HumdrumToken | None = None
        midiBPM: int = 0
        if isinstance(tokenOrBPM, HumdrumToken):
            token = tokenOrBPM
        elif isinstance(tokenOrBPM, int):
            midiBPM = tokenOrBPM

        metronomeMark: m21.tempo.MetronomeMark | None = None

        tempoName: str | None = None  # e.g. 'andante'
        mmStr: str | None = None      # e.g. 'M. M.' or 'M.M.' or 'M M' or M:M:
        noteName: str | None = None   # e.g. 'quarter'
        bpmText: str | None = None    # e.g. '88'

        mmText: str | None
        mmNumber: int | None
        mmReferent: m21.duration.Duration | None

        mmNumberToken: HumdrumToken | None = None

        text = html.unescape(text)
        text = text.replace(r'\n', '\n')

        tempoName, mmStr, noteName, bpmText = Convert.getMetronomeMarkInfo(text)
        if mmStr is None:
            mmStr = ''

        if not tempoName and not noteName and not bpmText:
            # raw text
            mmNumber = None
            if midiBPM > 0:
                mmNumber = midiBPM
            else:
                mmNumber = self._getMmTempo(token)  # nearby (previous) *MM
                if mmNumber <= 0:
                    mmNumber, mmNumberToken = self._getMmTempoForward(token)
                if mmNumber <= 0:
                    mmNumber = None
                if mmNumber is not None and mmNumberToken is not None:
                    mmNumberToken.setValue('auto', 'MM handled', True)

            mmText = text.strip()  # strip leading and trailing whitespace
            if mmText == '':
                mmText = None

            if mmNumber is not None or mmText is not None:
                metronomeMark = self._myMetronomeMarkInit(number=mmNumber, text=mmText)
            return metronomeMark

        # at least one of tempoName, noteName, and bpmText are present
        mmReferent = M21Convert.durationFromHumdrumTempoNoteName(noteName)
        mmText = tempoName
        if mmText and (mmText[-1] == '(' or mmText[-1] == '['):
            mmText = mmText[0:-1]
        if mmText:
            mmText = mmText.strip()  # strip leading and trailing whitespace

        if mmText and mmStr:
            mmText += ' ' + mmStr
        elif not mmText and mmStr:
            mmText = mmStr

        if mmText == '':
            mmText = None

        mmNumber = midiBPM
        if mmNumber <= 0:
            mmNumber = self._getMmTempo(token)  # nearby (previous) *MM
        if mmNumber <= 0:
            mmNumber, mmNumberToken = self._getMmTempoForward(token)
        if mmNumber <= 0:
            mmNumber = None
        if mmNumber is not None and mmNumberToken is not None:
            mmNumberToken.setValue('auto', 'MM handled', True)

        if bpmText and (bpmText[-1] == ')' or bpmText[-1] == ']'):
            bpmText = bpmText[0:-1]
        if bpmText:
            # bpmText overrides nearby *MM and passed in midiBPM
            mmNumber = int(float(bpmText) + 0.5)
        if mmNumber is not None and mmNumber <= 0:
            mmNumber = None

        if mmNumber is not None or mmText is not None or mmReferent is not None:
            if bpmText:
                # We parsed the BPM out of a lovely well-formed string, so use the whole string.
                # But replace the [quarter-dot] (or whatever) with the appropriate SMUFL string.
                mmText = Convert.getTempoText(text)

            metronomeMark = self._myMetronomeMarkInit(
                number=mmNumber, text=mmText, referent=mmReferent
            )
        return metronomeMark

    '''
    //////////////////////////////
    //
    // HumdrumInput::getLayoutParameter -- Get an attached layout parameter
    //   for a token.  Move this variant into HumdrumToken class at some point.
    //
    //     trueString = value to return if there is a parameter but the
    //                  value is empty.
    //     falseString = value to return if there is no parameter.
    //                   default value = ""
    '''
    @staticmethod
    def _getLayoutParameterWithDefaults(
        token: HumdrumToken,
        ns2: str,
        catKey: str,
        existsButEmptyValue: str,
        doesntExistValue: str = '',
        n: str = ''
    ) -> str:
        lcount = token.linkedParameterSetCount
        if lcount == 0:
            return doesntExistValue

        for p in range(0, lcount):
            hps = token.getLinkedParameterSet(p)
            if not hps:
                continue
            if hps.namespace1 != 'LO':
                continue
            if hps.namespace2 != ns2:
                continue

            if n:
                foundN: bool = False
                for q in range(0, hps.count):
                    k: str = hps.getParameterName(q)
                    if k == 'n':
                        v: str = hps.getParameterValue(q)
                        if v == n:
                            foundN = True
                            break

                if not foundN:
                    continue

            # we found n, or there's no n
            for q in range(0, hps.count):
                key: str = hps.getParameterName(q)
                if key == catKey:
                    value: str = hps.getParameterValue(q)
                    if value:
                        return value
                    return existsButEmptyValue

        return doesntExistValue

    '''
    //////////////////////////////
    //
    // HumdrumInput::getStaffLayerCounts -- Return the maximum layer count for each
    //    part within the measure.
    '''
    @property
    def staffLayerCounts(self) -> list[int]:
        return [
            len(listOfLayersForStaff) for listOfLayersForStaff in self._currentMeasureLayerTokens
        ]

#         for i, listOfLayersForStaff in enumerate(self._currentMeasureLayerTokens):
#             output[i] = len(listOfLayersForStaff)

    def _checkForOmd(self, measureKey: tuple[int | None, int]) -> None:
        startLineIdx, endLineIdx = measureKey
        if startLineIdx is None:
            # this method should not be called without a startLineIdx in measureKey
            raise HumdrumInternalError('Invalid measureKey')

        if self._currentOMDDurationFromStart > self._lines[startLineIdx].durationFromStart:
            return

        if len(self._staffStarts) == 0:
            return

        key: str = ''
        value: str = ''
        index: int = -1
        for i in range(startLineIdx, endLineIdx):
            line: HumdrumLine = self._lines[i]
            if line.isData:
                break

            if line.isBarline:
                token: HumdrumToken | None = line[0]
                if t.TYPE_CHECKING:
                    # because 0 is in range
                    assert isinstance(token, HumdrumToken)
                num: int = token.barlineNumber
                if value and num > 1:
                    # Don't print initial OMD if a musical excerpt.
                    # Feels like data-loss, but it isn't.  The OMD
                    # is still in the metadata, just not turned into
                    # a metronome mark as well.
                    return
            if not line.isReference:
                continue
            key = line.referenceKey
            if key == 'OMD':
                index = i
                value = line.referenceValue
                # break # Don't break: search for the last OMD in a non-data region

        if index == -1:
            return
        if not value:
            return

        value = html.unescape(value)
        if not value:
            return
        value = value.replace(r'\n', '\n')

        hasOmdText: bool = self._hasOmdText(measureKey)
        if hasOmdText:
            # Do not print the !!!OMD: reference record since there is an
            # alternate !!LO:TX:omd: entry that will be printed instead.
            return

        omdToken: HumdrumToken | None = self._lines[index][0]
        if t.TYPE_CHECKING:
            # omdToken contains the OMD we found (or we would have returned by now)
            assert isinstance(omdToken, HumdrumToken)

        self._currentOMDDurationFromStart = omdToken.durationFromStart

        if self._hasTempoTextAfterOMD(omdToken):
            # any tempo text after an OMD will have everything we need
            return

        # check for nearby *MM marker before OMD
        midibpm: int = self._getMmTempoBeforeOMD(omdToken)
        if midibpm <= 0:
            # check for nearby *MM marker after OMD
            midibpm, _ = self._getMmTempoForward(omdToken)


        omdToken.setValue('auto', 'OMD handled', True)
        # put the metronome mark in this measure of staff 0 (highest staff on the page)
        # Since OMD has no way of specifying placement or fontStyle, we set these
        # to the usual: 'above' and 'bold'
        staffIndex: int = 0
        tempo: m21.tempo.MetronomeMark | None = self._createMetronomeMark(value, midibpm)
        if tempo is not None:
            if t.TYPE_CHECKING:
                assert isinstance(tempo.style, m21.style.TextStyle)
            tempo.style.fontStyle = 'bold'
            if hasattr(tempo, 'placement'):
                tempo.placement = 'above'  # type: ignore
            else:
                tempo.style.absoluteY = 'above'

            currentMeasurePerStaff: list[m21.stream.Measure] = (
                self._allMeasuresPerStaff[self.measureIndexFromKey(measureKey)]
            )
            currentMeasurePerStaff[staffIndex].coreInsert(0, tempo)
            currentMeasurePerStaff[staffIndex].coreElementsChanged()

    def _hasOmdText(self, measureKey: tuple[int | None, int]) -> bool:
        startLineIdx, endLineIdx = measureKey
        if startLineIdx is None:
            # this method should not be called without a startLineIdx in measureKey
            raise HumdrumInternalError('Invalid measureKey')

        for i in range(startLineIdx, endLineIdx):
            line: HumdrumLine = self._lines[i]
            if line.hasSpines:
                continue

            token: HumdrumToken | None = line[0]
            if token is not None and token.text:
                m = re.match(r'^!!LO:TX.*:omd(:|$)', token.text)
                if m:
                    return True

        return False


    '''
    //////////////////////////////
    //
    // HumdrumInput::checkForBreak -- Search for a linebreak or a pagebreak marker,
    //     such as:
    //          !!linebreak:
    //          !!pagebreak:
    // There are also layout parameters for barlines that function as line breaks.
    // This one is primarily from MusicXML conversion, and can be removed or converted
    // to the layout system as need.  Search for a break message anywhere
    // around the barline but before any data is found.
    '''
#     def _checkForInformalBreak(self, lineIdx: int) -> None:
#         if lineIdx >= self.lineCount - 1:
#             return
#
#         firstTS: HumNum = self._lines[lineIdx].durationFromStart
#         lineBreakIdx: int = -1
#         pageBreakIdx: int = -1
#
#         # look forward for informal breaks, up to first data, or first line where ts changes
#         for i in range(lineIdx, self.lineCount):
#             line = self._lines[i]
#             if line.isData or line.durationFromStart != firstTS:
#                 break
#
#             if not line.isGlobalComment:
#                 continue
#
#             if line[0].text.startswith('!!linebreak:'):
#                 lineBreakIdx = i
#                 break
#
#             if line[0].text.startswith('!!pagebreak:'):
#                 pageBreakIdx = i
#                 break
#
#         if lineBreakIdx == -1 and pageBreakIdx == -1:
#             # look backward for informal breaks, back to first data,
#             # or first line where ts changes
#             for i in reversed(range(1, lineIdx)): # don't bother with line 0
#                 line = self._lines[i]
#                 if line.isData or line.durationFromStart != firstTS:
#                     break
#
#                 if not line.isGlobalComment:
#                     continue
#
#                 if line[0].text.startswith('!!linebreak:'):
#                     lineBreakIdx = i
#                     break
#
#                 if line[0].text.startswith('!!pagebreak:'):
#                     pageBreakIdx = i
#                     break
#
#         if lineBreakIdx == -1 and pageBreakIdx == -1:
#             return
#
#         if lineBreakIdx > 0:
#             self._m21BreakAtStartOfNextMeasure = m21.layout.SystemLayout(isNew = True)
#         elif pageBreakIdx > 0:
#             self._m21BreakAtStartOfNextMeasure = m21.layout.PageLayout(isNew = True)

    '''
    //////////////////////////////
    //
    // HumdrumInput::checkForLayoutBreak --
    '''
    def _checkForFormalBreak(self, lineIdx: int) -> None:
        if lineIdx >= self.lineCount - 1:
            return

        line: HumdrumLine = self._lines[lineIdx]

        if not line.isBarline:
            return

        token: HumdrumToken | None = line[0]
        if t.TYPE_CHECKING:
            # it's a barline, there has to be a first token
            assert isinstance(token, HumdrumToken)

        group: str = token.layoutParameter('LB', 'g')
        if group and not group.startswith('original'):
            self._m21BreakAtStartOfNextMeasure = m21.layout.SystemLayout(isNew=True)
            return

        group = token.layoutParameter('PB', 'g')
        if group and not group.startswith('original'):
            self._m21BreakAtStartOfNextMeasure = m21.layout.PageLayout(isNew=True)
            return

    '''
    // HumdrumInput::checkForGlobalRehearsal -- Only attached to barlines for now.
    '''
    def _checkForGlobalRehearsal(self, measureKey: tuple[int | None, int]):
        startLineIdx: int | None
        endLineIdx: int
        startLineIdx, endLineIdx = measureKey
        if startLineIdx is None:
            # skip this measure
            return

        checkLine: int = self._getNextBarlineIndex(startLineIdx, endLineIdx)
        line: HumdrumLine = self._lines[checkLine]
        if not line.isBarline:
            return

        token: HumdrumToken | None = line[0]
        if token is None:
            return

        absysDefault: str = self._getDefaultLayoutParameter('REH', 'absys')
        fontSizeDefault: str = self._getDefaultLayoutParameter('REH', 'fs')
        tvalueDefault: str = self._getDefaultLayoutParameter('REH', 't')
        qlOffsetDefault: str = self._getDefaultLayoutParameter('REH', 'qo')
        enclosureDefault: str = self._getDefaultLayoutParameter('REH', 'enc')
        colorDefault: str = self._getDefaultLayoutParameter('REH', 'color')
        enclosureColorDefault: str = self._getDefaultLayoutParameter('REH', 'encc')

        lcount: int = token.linkedParameterSetCount
        for i in range(0, lcount):
            hps: HumParamSet | None = token.getLinkedParameterSet(i)
            if not hps:
                continue
            if hps.namespace1 != 'LO':
                continue
            ns2: str = hps.namespace2
            if ns2 != 'REH':
                continue

            isGlobal: bool = token.linkedParameterIsGlobal(i)
            if not isGlobal:
                continue

            staffIndices: list[int] = [0]  # by default just put in staff 0 (top staff)

            absys: bool = absysDefault not in ('', '0', 'false')  # above and below system
            qlOffset: OffsetQL = M21Utilities.getQLFromString(qlOffsetDefault)
            aparam: bool = False
            bparam: bool = False
            bold: bool = False
            italic: bool = False
            justification: int = 0
            fontSize: str = fontSizeDefault
            encl: str = enclosureDefault
            enclColor: str = enclosureColorDefault
            color: str = colorDefault
            staffNumStrs: list[str] = []
            tvalue: str = tvalueDefault
            for j in range(0, hps.count):
                paramKey: str = hps.getParameterName(j)
                paramVal: str = hps.getParameterValue(j)
                if paramKey == 't':
                    tvalue = paramVal
                    continue
                if paramKey == 'enc':
                    encl = paramVal
                    continue
                if paramKey == 'a':
                    aparam = True
                    continue
                if paramKey == 'b':
                    bparam = True
                    continue
                if paramKey == 'absys':
                    absys = paramVal not in ('0', 'false')
                    continue
                if paramKey == 'qo':
                    qlOffset = M21Utilities.getQLFromString(paramVal)
                    continue
                if paramKey == 'fs':
                    fontSize = paramVal
                    continue
                if paramKey == 'rj':
                    justification = 1
                    continue
                if paramKey == 'cj':
                    justification = 2
                    continue
                if paramKey == 'i':
                    italic = True
                    continue
                if paramKey == 'B':
                    bold = True
                    continue
                if paramKey in ('ib', 'iB', 'bi', 'Bi'):
                    bold = True
                    italic = True
                    continue
                if paramKey == 'color':
                    color = paramVal
                    continue
                if paramKey == 'encc':
                    enclColor = paramVal
                    continue
                if paramKey == 'place':
                    # we currently only parse strings like 's1,s4', not 'p1,p2' or 'g1,g3'
                    placeStrs = paramVal.split(',')
                    for placeStr in placeStrs:
                        if not placeStr.startswith('s'):
                            # bad format, give up on :place=
                            staffNumStrs = []
                            break
                        if not placeStr[1:].isdigit():
                            # bad format, give up on :place=
                            staffNumStrs = []
                            break
                        staffNumStrs.append(placeStr[1:])
                    continue

            # We allow rehearsal marks with no text (so does music21's
            # MusicXML importer).

            if absys and self.staffCount < 2:
                # Above and below system only applies if 2 or more staves in system
                absys = False

            if staffNumStrs:
                staffIndices = []  # remove default 0
                for staffNumStr in staffNumStrs:
                    staffIndices.append(int(staffNumStr) - 1)

            if absys:
                if 0 not in staffIndices:
                    staffIndices.insert(0, 0)
                if self.staffCount - 1 not in staffIndices:
                    staffIndices.append(self.staffCount - 1)

            numRehearsalMarks: int = len(staffIndices)
            rehearsalMarks: list[m21.expressions.RehearsalMark] = []
            for i in range(0, numRehearsalMarks):
                reh = m21.expressions.RehearsalMark(tvalue)
                if t.TYPE_CHECKING:
                    assert isinstance(reh.style, m21.style.TextStylePlacement)
                rehearsalMarks.append(reh)

                if absys and staffIndices[i] == 0:
                    reh.style.placement = 'above'
                elif absys and staffIndices[i] == self.staffCount - 1:
                    reh.style.placement = 'below'
                elif aparam:  # above staff
                    reh.style.placement = 'above'
                elif bparam:  # below staff
                    reh.style.placement = 'below'

                if fontSize:
                    reh.style.fontSize = fontSize
                if bold and italic:
                    reh.style.fontStyle = M21Convert.m21FontStyleFromFontStyle('bold-italic')
                elif italic:
                    reh.style.fontStyle = M21Convert.m21FontStyleFromFontStyle('italic')
                elif bold:
                    reh.style.fontStyle = M21Convert.m21FontStyleFromFontStyle('bold')

                if justification == 1:
                    reh.style.justify = 'right'
                elif justification == 2:
                    reh.style.justify = 'center'

                # music21 has no way to have separate color for reh text and enclosure,
                # so while we have the same style if/elif here as Verovio, we just grab
                # whatever color we can find.
                if color and not enclColor:
                    reh.style.color = color
                elif not color and enclColor:
                    reh.style.color = enclColor
                elif color and enclColor:
                    reh.style.color = color

                if encl == 'box':
                    reh.style.enclosure = m21.style.Enclosure.SQUARE
                elif encl == 'circle':
                    reh.style.enclosure = m21.style.Enclosure.CIRCLE
                elif encl == 'dbox':
                    reh.style.enclosure = m21.style.Enclosure.DIAMOND
                elif encl == 'tbox':
                    reh.style.enclosure = m21.style.Enclosure.TRIANGLE
                elif encl == 'none':
                    if hasattr(m21.style.Enclosure, 'NO_ENCLOSURE'):
                        reh.style.enclosure = m21.style.Enclosure.NO_ENCLOSURE  # type: ignore

            currentMeasurePerStaff: list[m21.stream.Measure] = (
                self._allMeasuresPerStaff[self.measureIndexFromKey(measureKey)]
            )
            for reh, staffIndex in zip(rehearsalMarks, staffIndices):
                currentMeasurePerStaff[staffIndex].coreInsert(qlOffset, reh)
            for staffIndex in set(staffIndices):
                currentMeasurePerStaff[staffIndex].coreElementsChanged()

    '''
    //////////////////////////////
    //
    // HumdrumInput::getNextBarlineIndex -- Return the next barline row on or after
    //     the current index into the file.  If there is none before the first
    //     encountered data line, then return the input value.
    '''
    def _getNextBarlineIndex(self, startLine: int, endLine: int) -> int:
        line: HumdrumLine = self._lines[startLine]
        token: HumdrumToken | None = line[0]
        if token is not None:
            if token.isBarline:
                return startLine
            if token.text == '*-':
                return startLine

        # check the rest of the lines (including endLine)
        for lineIdx in range(startLine + 1, endLine + 1):
            line = self._lines[lineIdx]
            token = line[0]
            if token is None:
                continue
            if token.isBarline:
                return lineIdx
            if token.isData:
                return startLine
            if token.text == '*-':
                return lineIdx

        return startLine

    '''
    //////////////////////////////
    //
    // HumdrumInput::getMeasureEndLine -- Return the line index of the
    //   ending of a given measure.  This is usually a barline, but can be
    //   the end of a file if there is no terminal barline in the **kern
    //   data.  Returns a negative line number if there is no data in the
    //   measure.
    '''
    def _measureEndLineIndex(self, startIdx: int) -> int:
        endIdx: int = self.lineCount - 1
        foundData: bool = False
        for i, line in enumerate(self._lines):
            if i < startIdx + 1:
                # start looking at startIdx + 1
                continue

            if line.isData:
                foundData = True
            elif line.isBarline:
                # only create a new measure if all staves have identical barline
                if line.allSameBarlineStyle:
                    endIdx = i
                    break
        else:
            # We get here only if the loop exits normally... if we break out, we'll skip this
            # This handles the case where there is no ending barline
            endIdx = self.lineCount - 1

        if not foundData:
            return -endIdx

        return endIdx

    # _parseReferenceItem: takes key/value pair, and parses the key to derive
    # actual key and language code (skipping over any number), and then also
    # sets up a Text object for the value, including the language there, if
    # appropriate.
    # If the key doesn't have a parseable form, original key and Text(value)
    # are returned.
    # Parseable key forms:
    # 'COM' where 'COM' can be any string that doesn't have 0-9 or '@' or ' ' or '\t' in it
    # 'COM3'
    # 'COM@FR'  (one '@' means this is a translated language)
    # 'COM@@FR' (two '@'s means this is the original language)
    # 'COM72@RU'
    # 'COM5@@RU'
    @staticmethod
    def _parseReferenceItem(k: str, v: str) -> tuple[str, m21.metadata.Text, bool]:
        parsedKey: str | None = None
        parsedValue: m21.metadata.Text | None = None
        isParseable: bool = False

        # parse the key with regex:
        # 'COM5@@RU' -> 1:'COM', 2:'5', 3:'@@RU', 4:'@@', 5:'RU'
        # TODO: parse reference keys that have a number in the middle of the key:
        # TODO: ... e.g. 'OTL3-sub@@HAW' (The third subtitle in the original language of Hawaiian.)
        m = re.match(r'^([^0-9@ \t]*)([0-9]*)?((@{1,2})([a-zA-Z]*))?$', k)
        if not m:
            isParseable = False
            parsedKey = k
            parsedValue = m21.metadata.Text(v)
        else:
            isParseable = True
            parsedKey = m.group(1)
            langCode: str = m.group(5)
            isTranslated: bool = bool(langCode) and m.group(4) != '@@'
            encodingScheme: str | None = (
                M21Convert.humdrumReferenceKeyToEncodingScheme.get(parsedKey[0:3], None)
            )
            parsedValue = m21.metadata.Text(
                v,
                language=langCode.lower() if langCode else None,
                isTranslated=isTranslated,
                encodingScheme=encodingScheme
            )

        # we consider any key a humdrum standard key if it is parseable, and starts with 3 chars
        # that are in the list of humdrum reference keys ('COM', 'OTL', etc)
        # This includes parsed keys such as: 'COM-viaf-url' because it starts with COM.
        isHumdrumStandardKey: bool = (
            isParseable
            and parsedKey in M21Utilities.validHumdrumReferenceKeys
        )
        return (parsedKey, parsedValue, isHumdrumStandardKey)

    @staticmethod
    def _incrementOrInsertNumberInReferenceKey(key: str, insertNum: int = 1) -> str:
        # Find integer (if any) starting at newk[3] (just after humdrum key)
        # and increment it. If none found, insert a '1' there.
        newk: str = key

        m = re.match(r'^.{3}([0-9]+)', newk)
        if m:
            # increment that integer
            numStr = m.group(1)
            newNumStr: str = str(int(numStr) + 1)
            newk = newk[:3] + newNumStr + newk[3 + len(numStr):]
        else:
            # insert '1' after the 3-char humdrum key
            newk = newk[:3] + str(insertNum) + newk[3:]

        return newk

    @staticmethod
    def _replaceOrInsertNumberInReferenceKey(key: str, insertNum: int = 1) -> str:
        # Find integer (if any) starting at newk[3] (just after humdrum key)
        # and increment it. If none found, insert a '1' there.
        newk: str = key

        m = re.match(r'^.{3}([0-9]+)', newk)
        if m:
            # replace that integer
            oldNumStr = m.group(1)
            newNumStr: str = str(insertNum)
            newk = newk[:3] + newNumStr + newk[3 + len(oldNumStr):]
        else:
            # insert str(insertNum) after the 3-char humdrum key
            newk = newk[:3] + str(insertNum) + newk[3:]

        return newk

    def _createScoreMetadata(self) -> None:
        m21Metadata = m21.metadata.Metadata()
        self.m21Score.metadata = m21Metadata

        # first add a 'software' entry for this importer
        m21Metadata.add(
            'software',
            SharedConstants._CONVERTER21_NAME
        )

        addedValue: m21.metadata.ValueType = m21Metadata['software'][-1]
        M21Utilities.addOtherMetadataAttrib(
            addedValue,
            'humdrumVersion',
            SharedConstants._CONVERTER21_VERSION
        )

        for k, v in self._biblio:
            parsedKey: str
            parsedValue: m21.metadata.Text
            isStandardHumdrumKey: bool
            parsedKey, parsedValue, isStandardHumdrumKey = self._parseReferenceItem(k, v)

            if parsedKey == 'MRD':
                # 'MRD' and 'MDT' mean exactly the same thing.  I prefer the MDT spelling.
                parsedKey = 'MDT'

            m21UniqueName: str | None = (
                M21Utilities.humdrumReferenceKeyToM21MetadataPropertyUniqueName.get(
                    parsedKey, None)
            )

            if not m21UniqueName:
                # check for ACO, which like GCO, maps to 'collectionDesignation' (so can't be
                # filled in with a value in humdrumReferenceKeyToM21MetadataPropertyUniqueName)
                if parsedKey == 'ACO':
                    m21UniqueName = 'collectionDesignation'

            if m21UniqueName:
                m21Value: t.Any = M21Convert.humdrumMetadataValueToM21MetadataValue(parsedValue)
                M21Utilities.addIfNotADuplicate(m21Metadata, m21UniqueName, m21Value)
                continue

            if isStandardHumdrumKey:
                # Check if it's a contributor (that music21 doesn't apparently support),
                # and if so, make a Contributor with role set appropriately, and add it
                # with music21-supported 'otherContributor'.
                if parsedKey in M21Utilities.humdrumReferenceKeyToM21OtherContributorRole:
                    role: str = (
                        M21Utilities.humdrumReferenceKeyToM21OtherContributorRole[parsedKey]
                    )
                    contrib = m21.metadata.Contributor(name=parsedValue, role=role)
                    M21Utilities.addIfNotADuplicate(m21Metadata, 'otherContributor', contrib)
                    continue

                if parsedKey in M21Utilities.customHumdrumReferenceKeysThatAreDates:
                    # Fix up the date Text we have, by converting to DatePrimitive or
                    # DatePrimitive range, and back to string.
                    try:
                        dateObj: m21.metadata.DatePrimitive | None = (
                            M21Utilities.m21DatePrimitiveFromString(str(parsedValue))
                        )
                        # pylint: disable=protected-access
                        if dateObj is not None:
                            text: str = M21Utilities.stringFromM21DateObject(dateObj)
                            parsedValue._data = text
                        else:
                            # Try a DatePrimitive range instead
                            startDateObj: m21.metadata.DatePrimitive | None
                            endDateObj: m21.metadata.DatePrimitive | None
                            startDateObj, endDateObj = (
                                M21Utilities.m21DatePrimitiveRangeFromString(str(parsedValue))
                            )
                            if startDateObj is not None and endDateObj is not None:
                                parsedValue._data = M21Utilities.stringFromM21DatePrimitiveRange(
                                    startDateObj, endDateObj
                                )
                        # pylint: enable=protected-access
                    except Exception:
                        # badly formatted date; just ignore this metadata item
                        continue

                # Treat any other standard Humdrum keys as if they are true music21 keys.
                # Use 'humdrum:???' because there is no uniqueName (yet; I'll try to get
                # them all into music21 at some point).
                M21Utilities.addCustomIfNotADuplicate(
                    m21Metadata,
                    'humdrum:' + parsedKey,
                    parsedValue
                )
                continue

            # freeform key/value, put it in as custom (but with key prepended with
            # 'raw:' to prevent possible overlap with music21 metadata uniqueName key).
            m21Metadata.addCustom('raw:' + k, v)

    def _prepartPartInstrumentInfo(self, partStartTok: HumdrumToken, staffNum: int) -> None:
        # staffNum is 1-based, but _staffStates is 0-based
        ss: StaffStateVariables = self._staffStates[staffNum - 1]

        token: HumdrumToken | None = partStartTok
        while token is not None and not token.ownerLine.isData:
            # just scan the interp/comments before first data
            if token.isInstrumentAbbreviation:
                # part (instrument) abbreviation, e.g. *I'Vln.
                ss.instrumentAbbrev = token.instrumentAbbreviation
            elif token.isInstrumentName:
                # part (instrument) label
                ss.instrumentName = token.instrumentName
            elif token.isInstrumentCode:
                # instrument code, e.g. *Iclars is Clarinet
                ss.instrumentCode = token.instrumentCode
            elif token.isInstrumentClassCode:
                # instrument class code, e.g. *ICbras is BrassInstrument
                ss.instrumentClass = token.instrumentClassCode

            token = token.nextToken0  # stay left if there's a split

    def _createStaffGroupsAndParts(self) -> None:
        for i, startTok in enumerate(self._staffStarts):
            self._prepartPartInstrumentInfo(startTok, i + 1)

        decoration: str = self.getReferenceValueForKey('system-decoration')
        # Don't optimize by not calling _processSystemDecoration for empty/None decoration.
        # _processSystemDecoration also figures out ss.isPartStaff, even if there is
        # no decoration.
        status: bool = self._processSystemDecoration(decoration)

        # If there are no parts, either we didn't call _processSystemDecoration, or it failed.
        # We must have parts, so create them here.
        weHaveParts: bool = status  # if status is False, we do not have any parts, for sure
        if weHaveParts:
            # we _should_ have parts, better check to be sure
            for ss in self._staffStates:
                if ss.m21Part is None:
                    weHaveParts = False
                    break

        if weHaveParts:
            return

        # we don't have parts, so create them
        for i, startTok in enumerate(self._staffStarts):
            self._createPart(startTok, i + 1, self.staffCount)

    '''
    //////////////////////////////
    //
    // HumdrumInput::getStaffNumberLabel -- Return number 13 in pattern *staff13.

        Searches tokens starting at spineStart, until a data token is found
    '''
    @staticmethod
    def _getStaffNumberLabel(spineStart: HumdrumToken | None) -> int:
        tok: HumdrumToken | None = spineStart
        while tok and not tok.isData:
            if not tok.isStaffInterpretation:
                tok = tok.nextToken0  # stay left if there's a split
                continue

            staffNums = tok.staffNums
            if len(staffNums) > 0:
                return staffNums[0]

            tok = tok.nextToken0  # stay left if there's a split

        return 0

    '''
    //////////////////////////////
    //
    // HumdrumInput::getPartNumberLabel -- Return number 2 in pattern *part2.

        Searches tokens starting at spineStart, until a data token is found
    '''
    @staticmethod
    def _getPartNumberLabel(spineStart: HumdrumToken | None) -> int:
        tok: HumdrumToken | None = spineStart
        while tok and not tok.isData:
            if not tok.isPart:
                tok = tok.nextToken0  # stay left if there's a split
                continue
            return tok.partNum
        return 0

    '''
    //////////////////////////////
    //
    // HumdrumInput::getGroupNumberLabel -- Return number 7 in pattern *group7.

        Searches tokens starting at spineStart, until a data token is found
    '''
    @staticmethod
    def _getGroupNumberLabel(spineStart: HumdrumToken | None) -> int:
        tok: HumdrumToken | None = spineStart
        while tok and not tok.isData:
            if not tok.isGroup:
                tok = tok.nextToken0  # stay left if there's a split
                continue
            return tok.groupNum
        return 0

    def _shouldFakeOnePartAndOrAllStaves(self) -> tuple[bool, bool]:
        # returns (fakeOnePart, fakeAllStaves)
        # Returns fakeOnePart=True if (1) there are any missing *partN interps and
        #                             (2) there are <= 3 staffStarts.
        # (if there are more than 3 staffStarts, we will fake as many parts as there are staves)
        # Returns fakeAllStaves=True if there are any missing *staffN interps.
        partInterpsUsable: bool = True
        staffInterpsUsable: bool = True
        for startTok in self._staffStarts:
            partNum: int = self._getPartNumberLabel(startTok)
            staffNum: int = self._getStaffNumberLabel(startTok)

            if partNum <= 0:
                partInterpsUsable = False
            if staffNum <= 0:
                staffInterpsUsable = False

            if not partInterpsUsable and not staffInterpsUsable:
                # we're not going to get any new information, get out
                break

        fakeOnePart: bool = (
            not partInterpsUsable
            and self.staffCount in (2, 3)
            and self.staffIndicesHaveSameMultiStaffInstrument(list(range(0, self.staffCount)))
        )
        fakeAllStaves: bool = not staffInterpsUsable
        return fakeOnePart, fakeAllStaves

    def _isMultiStaffInstrumentCode(self, iCode: str) -> bool | None:
        iName: str = self.getInstrumentNameFromCode(iCode, None)
        return self._isMultiStaffInstrumentName(iName)

    def _isMultiStaffInstrumentAbbrev(self, iAbbrev: str) -> bool | None:
        return self._isMultiStaffInstrumentName(iAbbrev)

    def _isMultiStaffInstrumentName(self, iName: str) -> bool | None:
        m21Inst: m21.instrument.Instrument | None = None
        try:
            m21Inst = m21.instrument.fromString(iName)
        except m21.instrument.InstrumentException:
            pass  # ignore InstrumentException

        if m21Inst is None:
            return None  # just ignore names that don't mean anything

        return isinstance(m21Inst, (m21.instrument.KeyboardInstrument, m21.instrument.Organ))

    def staffIndicesHaveSameMultiStaffInstrument(self, staffIndices: list[int]) -> bool:
        # Note that each staff has to match the first or have no instrument (code, name, abbrev).
        firstInstrumentCode: str = ''
        firstInstrumentName: str = ''
        firstInstrumentAbbrev: str = ''
        isMultiStaff: bool | None
        for staffIdx in staffIndices:
            ss: StaffStateVariables = self._staffStates[staffIdx]
            if not firstInstrumentCode and ss.instrumentCode:
                firstInstrumentCode = ss.instrumentCode
                isMultiStaff = self._isMultiStaffInstrumentCode(firstInstrumentCode)
                if isMultiStaff is None:
                    firstInstrumentCode = ''
                elif isMultiStaff is False:
                    return False
            if not firstInstrumentName and ss.instrumentName:
                firstInstrumentName = ss.instrumentName
                isMultiStaff = self._isMultiStaffInstrumentName(firstInstrumentName)
                if isMultiStaff is None:
                    firstInstrumentName = ''
                elif isMultiStaff is False:
                    return False
            if not firstInstrumentAbbrev and ss.instrumentAbbrev:
                firstInstrumentAbbrev = ss.instrumentAbbrev
                isMultiStaff = self._isMultiStaffInstrumentAbbrev(firstInstrumentAbbrev)
                if isMultiStaff is None:
                    firstInstrumentAbbrev = ''
                elif isMultiStaff is False:
                    return False

            if firstInstrumentCode and ss.instrumentCode:
                if firstInstrumentCode != ss.instrumentCode:
                    return False
            if firstInstrumentName and ss.instrumentName:
                if firstInstrumentName != ss.instrumentName:
                    return False
            if firstInstrumentAbbrev and ss.instrumentAbbrev:
                if firstInstrumentAbbrev != ss.instrumentAbbrev:
                    return False

        if not firstInstrumentCode and not firstInstrumentName and not firstInstrumentAbbrev:
            if len(staffIndices) == 2:
                # assume completely unmarked two staff scores are piano scores
                return True
            # other completely unmarked scores are _not_ assumed to be multi-staff instruments
            return False

        # we actually matched multi-staff instruments
        return True

    '''
    //////////////////////////////
    //
    // HumdrumInput::processStaffDecoration -- Currently only one level
    //    of bracing is allowed.  Probably allow remapping of staff order
    //    with the system decoration, and possible merge two kern spines
    //    onto a single staff (such as two similar instruments sharing
    //    a common staff).

        Full recursive nesting is allowed now. --gregc 02oct2021
    '''
    def _processSystemDecoration(self, decoration: str) -> bool:
        trackList: list[int] = []
        startTok: HumdrumToken
        for startTok in self._staffStarts:
            if t.TYPE_CHECKING:
                # assume at least the _staffStarts all have track numbers
                assert startTok.track is not None
            trackList.append(startTok.track)

        isValid: bool = True

        # If decoration prefixes number with "s", then match to a kern
        # start which contains *staff# before any data content.  If the
        # number is not prefixed by "s", then assume that it is a kern
        # spine enumeration.  Staff enumerations can be utilized if a smaller
        # group of parts are extracted, but kern enumerations can become
        # invalid if extracting sub-scores.  In both cases the enumeration
        # goes from the top of the staff to the bottom, which means from right
        # to left on the Humdrum line.  If the order of the staff or kern
        # enumeration in the decoration is not monotonic covering every staff
        # in the score, then the results may have problems.

        # gregc -- I do not attempt to support bare spine numbers, since they are not
        # reliable.  I might be able to make them reliable by using the original spine
        # number for each staff, not simply using the index into _staffStarts.  I suspect
        # that no-one uses bare spine numbers in decorations, since they do not work well.

        # just a list of staff numbers found in *staff interps
        staffList: list[int] = []

        # key: tracknum, value: staffnum
        trackToStaff: dict[int, int] = {}

        # key: tracknum, value: staffstartindex
        trackToStaffStartIndex: dict[int, int] = {}

        # key is instrument class name, value is list of staff nums
        classToStaves: dict[str, list[int]] = {}

        # key is group num, value is list of staff nums
        groupToStaves: dict[int, list[int]] = {}

        # key is part num, value is list of staff nums
        partToStaves: dict[int, list[int]] = {}

        # key is staff num, value is instrument class name
        staffToClass: dict[int, str] = {}

        # key is staff num, value is group num
        staffToGroup: dict[int, int] = {}

        # key is index into self._staffStarts, value is group num (but we have to
        # declare key as int | str, because that's how it is declared in
        # M21StaffGroupDescriptionTree).
        staffStartIndexToGroup: dict[int | str, int] = {}

        # key is staff num, value is part num
        staffToPart: dict[int, int] = {}

        # key is staff num, value is index into self._staffStarts
        staffToStaffStartIndex: dict[int, int] = {}

        fakeOnePart: bool = False
        fakeAllStaves: bool = False
        fakeOnePart, fakeAllStaves = self._shouldFakeOnePartAndOrAllStaves()

        for staffStartIndex, (ss, startTok) in enumerate(
                zip(self._staffStates, self._staffStarts)):
            if t.TYPE_CHECKING:
                # assume at least the _staffStarts all have track numbers
                assert startTok.track is not None

            staffNum: int = self._getStaffNumberLabel(startTok)
            groupNum: int = self._getGroupNumberLabel(startTok)
            partNum: int = self._getPartNumberLabel(startTok)
            trackNum: int = startTok.track
            instrumentClass: str = ss.instrumentClass

            if fakeAllStaves:
                staffNum = staffStartIndex + 1

            if fakeOnePart:
                partNum = 1

            if staffNum in staffList:
                raise HumdrumSyntaxError('*staffN interpretations have duplicated staff numbers')

            staffList.append(staffNum)
            staffToStaffStartIndex[staffNum] = staffStartIndex

            trackToStaff[trackNum] = staffNum
            trackToStaffStartIndex[trackNum] = staffStartIndex

            if instrumentClass:
                if instrumentClass not in classToStaves:
                    classToStaves[instrumentClass] = [staffNum]
                else:
                    classToStaves[instrumentClass].append(staffNum)
                staffToClass[staffNum] = instrumentClass

            if groupNum > 0:
                if groupNum not in groupToStaves:
                    groupToStaves[groupNum] = [staffNum]
                else:
                    groupToStaves[groupNum].append(staffNum)
                staffToGroup[staffNum] = groupNum
                staffStartIndexToGroup[staffStartIndex] = groupNum

            if partNum > 0:
                if partNum not in partToStaves:
                    partToStaves[partNum] = [staffNum]
                else:
                    partToStaves[partNum].append(staffNum)
                staffToPart[staffNum] = partNum

        if not partToStaves:
            # all partNums were 0, which means every stave is its own part
            for staffNum in staffList:
                partToStaves[staffNum] = [staffNum]

        # Check each part's staves to see if they should be PartStaffs.
        # They should, if there is more than one staff in the part, either
        # because the Humdrum file was authored that way, or because we
        # noticed a set of staves that should be a multi-staff part above.
        for staffNs in partToStaves.values():
            if len(staffNs) > 1:
                for staffN in staffNs:
                    self._staffStates[staffToStaffStartIndex[staffN]].isPartStaff = True

        # Compute the StaffGroupDescriptionTree, either from the decoration string,
        # or if there is no such string, create a default tree from partToStaves et al.
        topLevelParent: M21StaffGroupDescriptionTree | None = None
        groupDescs: list[M21StaffGroupDescriptionTree | None]

        # rootGroupDesc is only there if there is no outer group in d (i.e. pretend there is a '()'
        # around the whole thing if there is no '[]', '{}', '()', or '<>' around the whole thing).
        rootGroupDesc: M21StaffGroupDescriptionTree | None = None

        if decoration:
            # Expand groupings into staves.  The d variable contains the expansions
            # and the decoration variable contains the original decoration string.
            d: str = decoration
            replacement: str

            # Instrument class expansion to staves:
            # e.g. '{(bras)}' might expand to '{(s3,s4,s5)}'
            if classToStaves:
                for iClassPattern, staves in classToStaves.items():
                    replacement = ''
                    for i, sNum in enumerate(staves):
                        replacement += 's' + str(sNum)
                        if i < len(staves) - 1:
                            replacement += ','
                    d = re.sub(iClassPattern, replacement, d)

            # Group number expansion to staves:
            if groupToStaves:
                # example:   {(g1}} will be expanded to {(s1,s2,s3)} if
                # group1 is given to staff1, staff2, and staff3.
                for gNum, staves in groupToStaves.items():
                    gNumStr: str = 'g' + str(gNum)
                    replacement = ''
                    for i, sNum in enumerate(staves):
                        replacement += 's' + str(sNum)
                        if i < len(staves) - 1:
                            replacement += ','
                    d = re.sub(gNumStr, replacement, d)

            # Part number expansion to staves:
            if partToStaves:
                # example:   {(p1}} will be expanded to {(s1,s2)} if
                # part1 is given to staff1 and staff2.
                for pNum, staves in partToStaves.items():
                    pNumStr: str = 'p' + str(pNum)
                    replacement = ''
                    for i, sNum in enumerate(staves):
                        replacement += 's' + str(sNum)
                        if i < len(staves) - 1:
                            replacement += ','
                    d = re.sub(pNumStr, replacement, d)

            # remove unexpanded groups and parts
            d = re.sub(r'p\d+', '', d)
            d = re.sub(r'g\d+', '', d)

            # remove any invalid characters
            d = re.sub(r'[^0-9s()<>{}*\[\]]', '', d)

            # Expand * to mean all tracks present in the score
            hasStar: bool = False
            if re.search(r'\*', d):
                replacement = ''
                for i, trackNum in enumerate(trackList):
                    replacement += 't' + str(trackNum)
                    if i < len(trackList) - 1:
                        replacement += ','
                d = re.sub(r'\*', replacement, d)
                hasStar = True

            d = re.sub(r'\*', '', d)  # gets rid of any remaining '*' characters
            if not d:
                return False
            '''
            print('INPUT DECORATION: {}'.format(decoration), file=sys.stderr)
            print('       PROCESSED: {}'.format(d), file=sys.stderr)
            '''

            decoStaffNums: list[int] = []
            for m in re.finditer(r's(\d+)', d):
                if m:
                    decoStaffNums.append(int(m.group(1)))

            for decoStaffNum in decoStaffNums:
                if decoStaffNum not in staffList:
                    # The staff number in the decoration string
                    # is not present in the list so remove it.
                    staffNumPattern = 's' + str(decoStaffNum)
                    # assert that if there is a next char, it is not a
                    # digit (don't match 's1' to 's10')
                    staffNumPattern += r'(?!\d)'
                    d = re.sub(staffNumPattern, '', d)

            # remove any empty groups
            d = re.sub(r'\(\)', '', d)
            d = re.sub(r'\[\]', '', d)
            d = re.sub(r'\{\}', '', d)
            d = re.sub(r'<>', '', d)
            # do it again to be safe (for one recursion)
            d = re.sub(r'\(\)', '', d)
            d = re.sub(r'\[\]', '', d)
            d = re.sub(r'\{\}', '', d)
            d = re.sub(r'<>', '', d)

            # How many staves ('sN' or 'tN') in d?
            decoStaffCount = d.count('s') + d.count('t')
            if decoStaffCount == 0:
                return False

            if decoStaffCount == 1:
                # remove decoration when a single staff on system.
                # This leaves only 'sN' or 'tN', with no braces of any sort.
                d = re.sub(r'[^ts\d]', '', d)

            # Now pair (), <> {}, and [] parentheses in the d string.
            # This is mostly for validation purposes (are things properly nested?)
            # but we also use pairing when walking the string to keep track of
            # where the current '}' was opened, for example.
            OPENS: list[str] = ['(', '{', '[', '<']
            CLOSES: list[str] = [')', '}', ']', '>']
            stack: list[tuple[int, str]] = []  # list of (d string index, paren char)
            pairing: list[int] = [-1] * len(d)

            for i, ch in enumerate(d):
                if ch in OPENS:
                    stack.append((i, ch))
                elif ch in CLOSES:
                    if not stack:
                        # close with no open
                        isValid = False
                        break
                    positionInList: int = CLOSES.index(ch)
                    if stack[-1][1] != OPENS[positionInList]:
                        # mismatched open and close
                        isValid = False
                        break
                    pairing[stack[-1][0]] = i
                    pairing[i] = stack[-1][0]
                    stack.pop()  # removes last element of stack, which we just consumed

            if stack:  # is not empty
                isValid = False

            '''
            # print analysis:
            for i, ch in enumerate(d):
                print("d[{}] =\t{} pairing: {}".format(i, ch, pairing[i]), file=sys.stderr)
            '''

            if not isValid:
                return False

            if not pairing:
                return False

            # figure out which staffIds etc are grouped.  If groups are nested,
            # higher level groups contain all the staves of their contained (lower
            # level) groups.

            # groupDescs has an element for every character in d.  We will replace some of
            # these Nones (the ones where a '{[(<' starts a group) with an actual group
            # description below.
            groupDescs = [None] * len(d)

            # loop over d, creating/pushing, popping through nested M21StaffGroupDescriptionTrees
            # as you hit various delimiters, adding each staffIndex seen to all currently pushed
            # M21StaffGroupDescriptionTrees (you, and those above you) as you walk over the 'sN's.
            staffStartIndicesSeen: list[int] = []
            isStaffIndicator: bool = False
            isTrackIndicator: bool = False
            value: int = 0

            currentGroup: M21StaffGroupDescriptionTree | None = None
            if pairing[-1] != 0:
                # There is no outer group, so make a fake one.
                rootGroupDesc = M21StaffGroupDescriptionTree()
                rootGroupDesc.symbol = 'none'  # no visible bracing
                rootGroupDesc.barTogether = False  # no barline across the staves
                currentGroup = rootGroupDesc

            skipNext: bool = False
            pairedGroup: M21StaffGroupDescriptionTree | None
            newGroup: M21StaffGroupDescriptionTree
            for i, dCharI in enumerate(d):
                if skipNext:
                    skipNext = False
                    continue

                if dCharI in '{[<':
                    newGroup = M21StaffGroupDescriptionTree()
                    newGroup.symbol = M21Convert.humdrumDecoGroupStyleToM21GroupSymbol[dCharI]
                    if i < len(d) - 1:
                        if d[i + 1] == '(' and pairing[i + 1] == pairing[i] - 1:
                            # the '(' and ')' are both one character inside the enclosing braces
                            newGroup.barTogether = True
                            skipNext = True  # we've already handled the '('
                    newGroup.parent = currentGroup
                    if currentGroup is not None:
                        currentGroup.children.append(newGroup)
                    currentGroup = newGroup
                    groupDescs[i] = newGroup
                elif dCharI == '(':
                    # standalone '(' gets its own StaffGroup with no symbol,
                    # just barTogether = True
                    newGroup = M21StaffGroupDescriptionTree()
                    newGroup.barTogether = True
                    newGroup.parent = currentGroup
                    if currentGroup is not None:
                        currentGroup.children.append(newGroup)
                    currentGroup = newGroup
                    groupDescs[i] = newGroup
                elif dCharI in '}]>':
                    # pairing[i] is the index in d of the matching '{[<'
                    pairedGroup = groupDescs[pairing[i]]
                    if t.TYPE_CHECKING:
                        # because we set up pairing[i] to point to non-None earlier
                        assert isinstance(pairedGroup, M21StaffGroupDescriptionTree)
                    currentGroup = pairedGroup.parent
                elif dCharI == ')':
                    # pairing[i] is the index in d of the matching '{[<('
                    if i < len(d) - 1:
                        if d[i + 1] in '}]>' and pairing[i + 1] == pairing[i] - 1:
                            # this is NOT a standalone ')', so skip it.
                            # We already set barTogether when we saw the matching '('.
                            continue
                    pairedGroup = groupDescs[pairing[i]]
                    if t.TYPE_CHECKING:
                        # because we set up pairing[i] to point to non-None earlier
                        assert isinstance(pairedGroup, M21StaffGroupDescriptionTree)
                    currentGroup = pairedGroup.parent

                elif dCharI == 's':
                    isStaffIndicator = True
                    isTrackIndicator = False

                elif dCharI == 't':
                    isStaffIndicator = False
                    isTrackIndicator = True

                elif dCharI.isdigit():
                    value = max(value, 0)  # never leave it < 0
                    value = (value * 10) + int(dCharI)
                    if i == len(d) - 1 or not d[i + 1].isdigit():
                        # end of digit chars
                        sstartIndex: int = -1
                        if isStaffIndicator:
                            sstartIndex = staffToStaffStartIndex.get(value, -1)
                        elif isTrackIndicator:
                            sstartIndex = trackToStaffStartIndex.get(value, -1)

                        value = 0

                        isStaffIndicator = False
                        isTrackIndicator = False
                        if sstartIndex not in range(0, self.staffCount):
                            # Spine does not exist in the score: skip it.
                            continue

                        # we put this sstartIndex in the current group (noted as 'owned')
                        # and as 'referenced' in current group and all its ancestors.
                        ancestor: M21StaffGroupDescriptionTree | None = currentGroup
                        while ancestor is not None:
                            if ancestor is currentGroup:
                                currentGroup.ownedStaffIds.append(sstartIndex)
                            ancestor.staffIds.append(sstartIndex)
                            ancestor = ancestor.parent

                        staffStartIndicesSeen.append(sstartIndex)

            # Check to see that all staffstarts are represented in system decoration exactly once.
            # Otherwise, declare that it is invalid.
            found: list[int] = [0] * self.staffCount
            if not hasStar:
                # we're good by definition
                for val in staffStartIndicesSeen:
                    found[val] += 1

                for i, foundCount in enumerate(found):
                    if foundCount != 1:
                        isValid = False
                        break

            if not isValid:
                print("DECORATION IS INVALID:", decoration, file=sys.stderr)
                if d != decoration:
                    print("\tSTAFF VERSION:", d, file=sys.stderr)

                # iohumdrum.cpp unconditionally adds a full-score brace here, but I'm going
                # to fail instead, and let the failure handling put some default bracing
                # in place.
                return False

            for groupDesc in groupDescs:
                if groupDesc is not None and groupDesc.staffIds:
                    # we skip None groupDescs and empty groupDescs (no staves)
                    groupDesc.groupNum = staffStartIndexToGroup.get(groupDesc.staffIds[0], 0)

            topLevelParent = rootGroupDesc
            if topLevelParent is None:
                topLevelParent = groupDescs[0]

        else:
            # There is no decoration, but we know partToStaves, so if we have multi-staff
            # parts, let's make staff groups for them, so we don't end up (on export)
            # with multiple parts instead of multiple staves within one part. We walk
            # the parts/staves and create a StaffGroupDescriptionTree here, similar to
            # how we do it above while walking the decoration string.

            # groupDescs has an element for every part in partToStaves.  We will replace
            # some of these Nones (the ones where a part has multiple staves) with an
            # actual group description below.
            groupDescs = [None] * len(partToStaves)
            rootGroupDesc = M21StaffGroupDescriptionTree()
            rootGroupDesc.symbol = 'none'  # no visible bracing
            rootGroupDesc.barTogether = False  # no barline across the staves

            numStaffGroups: int = 0
            if partToStaves:
                for i, staves in enumerate(partToStaves.values()):
                    if len(staves) > 1:
                        # make a StaffGroupDescriptionTree for these staves,
                        # and put it under rootGroupDesc
                        newGroup = M21StaffGroupDescriptionTree()
                        if len(staves) == 2:
                            # If there are two staves, presume that it is for a grand staff
                            # and a brace should be displayed.  Barlines should go thru everything.
                            newGroup.symbol = 'brace'
                            newGroup.barTogether = True
                        else:
                            # If there are more than two staves then
                            # add a bracket around the staves.  Barlines go thru staves only.
                            newGroup.symbol = 'bracket'
                            newGroup.barTogether = False
                        newGroup.ownedStaffIds = [
                            staffToStaffStartIndex[staffNum] for staffNum in staves
                        ]
                        newGroup.staffIds = newGroup.ownedStaffIds
                        newGroup.parent = rootGroupDesc
                        rootGroupDesc.children.append(newGroup)
                        rootGroupDesc.staffIds += newGroup.staffIds
                        groupDescs[i] = newGroup
                        numStaffGroups += 1
                    elif len(staves) == 1:
                        # no StaffGroupDescriptionTree for this staff, it's
                        # owned by the top-level staff group
                        sidx: int = staffToStaffStartIndex[staves[0]]
                        rootGroupDesc.ownedStaffIds.append(sidx)
                        rootGroupDesc.staffIds.append(sidx)
            else:
                # no partToStaves, just a staffList, all of which should go in the top-level
                # staff group
                for staffNum in staffList:
                    staffIdx: int = staffNum - 1
                    rootGroupDesc.ownedStaffIds.append(staffIdx)
                    rootGroupDesc.staffIds.append(staffIdx)

            if rootGroupDesc.symbol == 'none' and len(rootGroupDesc.ownedStaffIds) != 1:
                rootGroupDesc.symbol = 'bracket'  # not sure why verovio does this

            for groupDesc in groupDescs:
                if groupDesc is not None and groupDesc.staffIds:
                    # we skip None groupDescs and empty groupDescs (no staves)
                    groupDesc.groupNum = staffStartIndexToGroup.get(groupDesc.staffIds[0], 0)

            if (numStaffGroups == 1
                    and rootGroupDesc.staffIds == rootGroupDesc.children[0].staffIds):
                topLevelParent = rootGroupDesc.children[0]  # just that one, please
            else:
                topLevelParent = rootGroupDesc

        staffGroups: list[m21.layout.StaffGroup] = []
        if topLevelParent is not None:
            # Recursively sort every list of siblings in the tree by
            # lowest staff number, so the staff numbers are in order.
            self._sortGroupDescriptionTrees([topLevelParent])

            newStaffGroups, _, _ = self._processStaffGroupDescriptionTree(topLevelParent)
            staffGroups += newStaffGroups

        # Insert the StaffGroups into the score in reverse order.
        # TODO: Figure out if inserting StaffGroups into the score in reverse order is correct.
        # This sets up the staffGroups so that the HumdrumWriter can get the order of nesting of
        # things like {[s1,s2]} correct.  I can't tell if this is actually the right place to do
        # this, since I can't get anyone to obey both the brace and the bracket.  If it turns out
        # that I find someone who does, and they get it backward because of my reversal here, then
        # I should NOT reverse here, and reverse in the HumdrumWriter instead.
        # Note well, that reversal makes no difference at all in HumdrumWriter, unless there are
        # two brackets/braces nested around the same list of staves.  It's about figuring out who
        # is the parent (since music21 doesn't explicitly nest StaffGroups).  It's easy if one
        # group has a true superset of the staves in another, but if they have the exact same
        # list of staves, who is the parent?
        # I've asked on the music21 list...
        insertedIntoScore: bool = False
        for staffGroup in reversed(staffGroups):
            self.m21Score.coreInsert(0, staffGroup)
            insertedIntoScore = True
        if insertedIntoScore:
            self.m21Score.coreElementsChanged()

        return True

    @staticmethod
    def _sortGroupDescriptionTrees(trees: list[M21StaffGroupDescriptionTree]) -> None:
        # Sort the staffIds and ownedStaffIds in every node in the tree.
        # Sort every list of children in the tree (including the
        # passed-in trees list itself) by lowest staff index.
        if not trees:
            return

        for tree in trees:
            tree.staffIds.sort()
            tree.ownedStaffIds.sort()

        trees.sort(key=lambda tree: tree.staffIds[0] if tree.staffIds else -1)

        for tree in trees:
            HumdrumFile._sortGroupDescriptionTrees(tree.children)

    '''
        _processStaffGroupDescriptionTree returns three lists: the StaffGroups generated,
        the Parts/PartStaffs contained by those StaffGroups, and the staff indices for those
        Parts/PartStaffs.  The StaffGroup list length will be <= the Part/PartStaff list length,
        and the staff indices list length will be == the Part/PartStaff list length.
    '''
    def _processStaffGroupDescriptionTree(
        self,
        groupDescTree: M21StaffGroupDescriptionTree
    ) -> tuple[list[m21.layout.StaffGroup], list[m21.stream.Part], list[int]]:
        if groupDescTree is None:
            return ([], [], [])
        if not groupDescTree.staffIds:
            return ([], [], [])

        staffGroups: list[m21.layout.StaffGroup] = []
        staves: list[m21.stream.Part] = []
        staffIds: list[int] = []

        # top-level staffGroup for this groupDescTree
        staffGroups.append(m21.layout.StaffGroup())

        # Iterate over each sub-group (check for owned groups of staves between subgroups)
        # Process owned groups here, recurse to process sub-groups
        staffIdsToProcess: set[int | str] = set(groupDescTree.staffIds)

        for subgroup in groupDescTree.children:
            firstStaffIdxInSubgroup: int | str = subgroup.staffIds[0]
            if t.TYPE_CHECKING:
                assert isinstance(firstStaffIdxInSubgroup, int)

            # 1. any owned group just before this subgroup
            # (while loop will not execute if there is no owned group before this subgroup)
            for ownedStaffIdx in groupDescTree.ownedStaffIds:
                if t.TYPE_CHECKING:
                    assert isinstance(ownedStaffIdx, int)

                if ownedStaffIdx >= firstStaffIdxInSubgroup:
                    # we're done with this owned group (there may be another one later)
                    break

                if ownedStaffIdx not in staffIdsToProcess:
                    # we already did this one
                    continue

                ss = self._staffStates[ownedStaffIdx]
                startTok = self._staffStarts[ownedStaffIdx]
                self._createPart(startTok, ownedStaffIdx + 1, self.staffCount)
                if t.TYPE_CHECKING:
                    assert ss.m21Part is not None
                staffGroups[0].addSpannedElements(ss.m21Part)
                staves.append(ss.m21Part)
                staffIds.append(ownedStaffIdx)

                staffIdsToProcess.remove(ownedStaffIdx)

            # 2. now the subgroup (returns a list of StaffGroups for the subtree)
            newStaffGroups: list[m21.layout.StaffGroup]
            newStaves: list[m21.stream.Part]
            newIds: list[int]

            newStaffGroups, newStaves, newIds = (
                self._processStaffGroupDescriptionTree(subgroup)
            )

            # add newStaffGroups to staffGroups
            staffGroups += newStaffGroups

            # add newStaves to staves and to our top-level staffGroup (staffGroups[0])
            staves += newStaves
            staffGroups[0].addSpannedElements(newStaves)

            # add newIds to staffIds
            staffIds += newIds

            # remove newIds from staffIdsToProcess
            staffIdsProcessed: set[int] = set(newIds)  # for speed of "in" checking
            staffIdsToProcess = {
                idx for idx in staffIdsToProcess if idx not in staffIdsProcessed
            }

        # done with everything but the very last owned group (if present)
        if staffIdsToProcess:
            # 3. any unprocessed owned group just after the last subgroup
            for ownedStaffIdx in groupDescTree.ownedStaffIds:
                if ownedStaffIdx not in staffIdsToProcess:
                    # we already did this one
                    continue

                if t.TYPE_CHECKING:
                    assert isinstance(ownedStaffIdx, int)

                ss = self._staffStates[ownedStaffIdx]
                startTok = self._staffStarts[ownedStaffIdx]
                self._createPart(startTok, ownedStaffIdx + 1, self.staffCount)
                if t.TYPE_CHECKING:
                    assert ss.m21Part is not None
                staffGroups[0].addSpannedElements(ss.m21Part)
                staves.append(ss.m21Part)
                staffIds.append(ownedStaffIdx)

                staffIdsToProcess.remove(ownedStaffIdx)

        # assert that we are done
        assert not staffIdsToProcess

        # configure our top-level staffGroup
        sg: m21.layout.StaffGroup = staffGroups[0]
        sg.symbol = groupDescTree.symbol
        sg.barTogether = groupDescTree.barTogether

        groupName = self._groupNames.get(groupDescTree.groupNum)
        groupAbbrev = self._groupAbbrevs.get(groupDescTree.groupNum)
        if groupAbbrev:
            sg.abbreviation = groupAbbrev
        if groupName:
            sg.name = groupName

        # Look in the group's Parts to see if they all have the same
        # instrument e.g. 'Organ' or 'Piano' (it still counts if some
        # parts have no instrument at all, and the rest have the same
        # common instrument).
        # If so,
        #   (1) set that instrument in the StaffGroup
        #   (2) mark that instrument in the Part(s) as not-to-be-printed
        #
        # This overrides any groupName or groupAbbrev that has been set on the sg.
        self._promoteCommonInstrumentToStaffGroup(sg)

        return (staffGroups, staves, staffIds)

    @staticmethod
    def _promoteCommonInstrumentToStaffGroup(staffGroup: m21.layout.StaffGroup) -> None:
        # Note: MuseScore doesn't support StaffGroup.name/abbrev, but Finale does.
        partsAndInstruments: list[tuple[int, m21.instrument.Instrument]] = []
        commonInstrument: m21.instrument.Instrument | None = None
        for part in staffGroup.getSpannedElements():
            inst = part.getInstrument(returnDefault=False)
            if inst is None:
                continue
            if commonInstrument is None:
                commonInstrument = inst
                partsAndInstruments.append((part, inst))
                continue
            if (inst.instrumentName == commonInstrument.instrumentName
                    and inst.instrumentAbbreviation == commonInstrument.instrumentAbbreviation):
                partsAndInstruments.append((part, inst))
                continue
            # found a non-common instrument in the staffGroup, get the heck out
            commonInstrument = None
            partsAndInstruments = []
            break

        if commonInstrument:
            staffGroup.name = commonInstrument.instrumentName
            staffGroup.abbreviation = commonInstrument.instrumentAbbreviation

            # Hide the instruments when printing, or they'll print on each staff
            # of the group, too.
            for part, instrument in partsAndInstruments:
                instrument.style.hideObjectOnPrint = True

    '''
    //////////////////////////////
    //
    // HumdrumInput::fillStaffInfo --
    '''
    def _createPart(self, partStartTok: HumdrumToken, staffNum: int, partCount: int) -> None:
        # staffNum is 1-based, but _staffStates is 0-based
        ss: StaffStateVariables = self._staffStates[staffNum - 1]
        if ss.isPartStaff:
            ss.m21Part = m21.stream.PartStaff()
        else:
            ss.m21Part = m21.stream.Part()

        # we will insert notes at sounding pitch, and then convert them at the end to written pitch
        ss.m21Part.atSoundingPitch = True
        self.m21Score.coreInsert(0, ss.m21Part)
        self.m21Score.coreElementsChanged()

        group: int = self._getGroupNumberLabel(partStartTok)

        clefTok: HumdrumToken | None = None
        partTok: HumdrumToken | None = None
        staffTok: HumdrumToken | None = None
        staffScaleTok: HumdrumToken | None = None
        striaTok: HumdrumToken | None = None
        keySigTok: HumdrumToken | None = None
        keyTok: HumdrumToken | None = None
        timeSigTok: HumdrumToken | None = None
        meterSigTok: HumdrumToken | None = None
#         primaryMensuration: str = ''

        iName: str | None = None
        iCode: str | None = None
        iClassCode: str | None = None
        iAbbrev: str | None = None
        iTranspose: str | None = None

        token: HumdrumToken | None = partStartTok
        while token is not None and not token.ownerLine.isData:
            # just scan the interp/comments before first data
            if token.isClef:
                if clefTok:
                    if clefTok.clef == token.clef:
                        # there is already a clef found, and it is the same as this one,
                        # so ignore the second one.
                        pass
                    else:
                        # mark clef as a clef change to print in the measure
                        token.setValue('auto', 'clefChange', True)
#                         self._markOtherClefsAsChange(token)

                    token = token.nextToken0  # stay left if there's a split
                    continue

                # first clef (not a clef change)
                if token.clef[-1].isdigit() or token.clef[0] == 'X':
                    # allow percussion clef '*clefX' to not have a line number,
                    # since it is unpitched.
                    clefTok = token
            elif token.isOriginalClef:
                if token.originalClef[0].isdigit():
                    self._oclefs.append((staffNum, token))
            elif token.isPart:
                partTok = token
            elif token.isStaffInterpretation:
                staffTok = token
            elif token.isStria:
                # num lines per staff (usually 5)
                striaTok = token
            elif token.isOriginalMensurationSymbol:
                self._omets.append((staffNum, token))
            elif token.isKeySignature:
                keySigTok = token
            elif token.isOriginalKeySignature:
                self._okeys.append((staffNum, token))
            elif token.isKeyDesignation:
                # e.g. *A-: or *d:dor
                keyTok = token
            elif token.isScale:
                staffScaleTok = token
            elif token.isSize:
                staffScaleTok = token
#             elif token.isTranspose:
#                 ss.wasTransposedBy = Convert.transToBase40(token.transpose)

            elif token.isInstrumentTranspose:
                iTranspose = token.instrumentTranspose
            elif token.isInstrumentGroupAbbreviation:
                # e.g. *I''bras is Brass
                if partCount > 1:
                    # Avoid encoding the part group abbreviation when there is only one
                    # part in order to suppress the display of the abbreviation.
                    groupAbbrev: str = token.instrumentGroupAbbreviation
                    if group >= 0 and groupAbbrev != '':
                        self._groupAbbrevs[group] = groupAbbrev
                        self._groupAbbrevTokens[group] = token
            elif token.isInstrumentAbbreviation:
                # part (instrument) abbreviation, e.g. *I'Vln.
                if partCount > 1:
                    # Avoid encoding the part abbreviation when there is only one
                    # part in order to suppress the display of the abbreviation.
                    iAbbrev = token.instrumentAbbreviation
            elif token.isInstrumentGroupName:
                # group label, e.g. *I""Strings
                groupName: str = token.instrumentGroupName
                if group > 0 and groupName != '':
                    self._groupNames[group] = groupName
                    self._groupNameTokens[group] = token
            elif token.isInstrumentName:
                # part (instrument) label
                iName = token.instrumentName
            elif token.isInstrumentCode:
                # instrument code, e.g. *Iclars is Clarinet
                iCode = token.instrumentCode
            elif token.isInstrumentClassCode:
                # instrument class code, e.g. *ICbras is BrassInstrument
                iClassCode = token.instrumentClassCode
            elif token.isMensurationSymbol:
                meterSigTok = token
            elif token.isTimeSignature:
                timeSigTok = token
#             elif 'acclev' in token.text: # '*acclev', '*acclev:', '*Xacclev', etc
#                 self._storeAcclev(token.text, staffNum - 1) # for **mens accidental processing
            elif token.text.startswith('*stem'):
                # layerNum == 1
                self._storeStemInterpretation(token.text, staffNum - 1, 1)

# When different parts have different mensurations at the same time, a global comment can be
# added at that point in the score to indicate the primary mensuration for performance tempo
# determination. For example, if three out of for parts are in Cut-C and one is in C, then the
# global record starting with "!!primary-mensuration:" and followed by the main mensuration
# used to determine the tempo of the following music. For example:
#
#   *M2/1      *M2/1     *M2/1      *M2/1
#   *met(C|)   *met(C)   *met(C|)   *met(C|)
#   !!primary-mensuration: met(C|)

#             startLine = token.lineIndex + 1
#             for i, line in enumerate(self._lines):
#                 if i < startLine: # we start at token.lineIndex + 1
#                     continue
#                 if not line.isGlobalComment:
#                     break
#
#                 m = re.search(r'^!!primary-mensuration:met\((.+)\)', line.text)
#                 if m is not None:
#                     primaryMensuration = m.group(1)

            token = token.nextToken0  # stay left if there's a split

        # now process the stuff you gathered, putting important info in ss
        # and in ss.m21Part (created above)

        # Make an instrument name if we need to...
        if iName is None:
            if iCode is not None:
                iName = self.getInstrumentNameFromCode(iCode, iTranspose)
            elif iClassCode is not None:
                iName = self.getInstrumentNameFromClassCode(iClassCode)
            elif iAbbrev is not None:
                iName = iAbbrev
            elif iTranspose is not None:
                iName = 'UnknownTransposingInstrument'

        # create m21Instrument, and insert it into ss.m21Part
        if iName:
            m21Inst: m21.instrument.Instrument | None = None
            try:
                # instrument.fromString parses recognized names, sets extra fields
                m21Inst = m21.instrument.fromString(iName)
            except m21.instrument.InstrumentException:
                pass  # ignore InstrumentException (it's OK)

            if m21Inst is None:
                m21Inst = m21.instrument.Instrument(iName)

            # clear out any transposition that iName implied to music21, since we need to
            # only trust the Humdrum transposition information (iTranspose).
            if m21Inst is not None:
                m21Inst.transposition = None

            if iAbbrev and iAbbrev != iName:
                m21Inst.instrumentAbbreviation = iAbbrev
            if iTranspose:
                # Here's where we pick up the exact instrument transposition
                # from iTranspose, and put it in the instrument we've created.
                transposeFromWrittenToSounding: m21.interval.Interval | None = (
                    M21Convert.m21IntervalFromTranspose(iTranspose)
                )
                # m21 Instrument transposition is from sounding to written
                # (reverse of what we have)
                if transposeFromWrittenToSounding is not None:
                    m21Inst.transposition = transposeFromWrittenToSounding.reverse()
            ss.m21Part.coreInsert(0, m21Inst)
            ss.m21Part.coreElementsChanged()

        # short-circuit *clef with *oclef for **mens data
        if partStartTok.isMens:
            if self._oclefs and staffNum == self._oclefs[-1][0]:
                clefTok = self._oclefs[-1][1]

        # short-circuit *met with *omet for **mens data
        if partStartTok.isMens:
            if self._omets and staffNum == self._omets[-1][0]:
                meterSigTok = self._omets[-1][1]

        dynamSpine: HumdrumToken | None
        if staffTok:
            # search for a **dynam before the next **kern spine, and set the
            # dynamics position to centered if there is a slash in the *staff1/2 string.
            # In the future also check *part# to see if there are two staves for a part
            # with no **dynam for the lower staff (infer to be a grand staff).
            dynamSpine = self.associatedDynamSpine(staffTok)
            if (dynamSpine is not None
                    and dynamSpine.isStaffInterpretation
                    and '/' in dynamSpine.text):
                # the dynamics should be placed between
                # staves: the current one and the one below it.
                ss.dynamPos = 0
                ss.dynamStaffAdj = 0
                ss.dynamPosDefined = True

        if partTok:
            pPartNum: int = 0   # from *part token
            dPartNum: int = 0   # from *part token in associated dynam spine
            lPartNum: int = 0   # from *part token in next left staff spine
            dynamSpine = self.associatedDynamSpine(partTok)
            if dynamSpine is not None:
                dPartNum = dynamSpine.partNum

            if dPartNum > 0:
                pPartNum = partTok.partNum

            if pPartNum > 0:
                nextLeftStaffTok = self.previousStaffToken(partTok)
                if nextLeftStaffTok:
                    lPartNum = nextLeftStaffTok.partNum

            if lPartNum > 0:
                if lPartNum == pPartNum and dPartNum == pPartNum:
                    ss.dynamPos = 0
                    ss.dynamStaffAdj = 0
                    ss.dynamPosDefined = True

        if staffScaleTok:
            ss.staffScaleFactor = staffScaleTok.scale

        if striaTok:
            ss.numStaffLines = striaTok.stria

        if clefTok:
            m21Clef: m21.clef.Clef = M21Convert.m21Clef(clefTok)
            # hang on to this until we have a first measure to put it in
            ss.firstM21Clef = m21Clef
            ss.mostRecentlySeenClefTok = clefTok
        # else:
        #     We won't do any getAutoClef stuff, music21 does that for you.

        # if transpose: Already handled above where we set wasTransposedBy...
        # if iTranspose, iAbbrev, hasLabel: Already handled in instrument prep above.

        if keySigTok:
            # hang on to this until we have a first measure to put it in
            m21KeySig = M21Convert.m21KeySignature(keySigTok, keyTok)
            ss.firstM21KeySig = m21KeySig
            # also always track current keysig per staff
            ss.currentM21KeySig = m21KeySig

        m21TimeSig = None
        if timeSigTok:
            # hang on to this until we have a first measure to put it in
            m21TimeSig = M21Convert.m21TimeSignature(timeSigTok, meterSigTok)
            ss.firstM21TimeSig = m21TimeSig

#         if partStartTok.isMens:
#             if self._isBlackNotation(partStartTok):
#                 # music21 doesn't really support black mensural notation
#             else:
#                 # music21 doesn't really support white mensural notation, either

    '''
    //////////////////////////////
    //
    // HumdrumInput::markOtherClefsAsChange -- There is a case
    //     where spine splits at the start of the music miss a clef
    //     change that needs to be added to a secondary layer.  This
    //     function will mark the secondary clefs so that they will
    //     be converted as clef changes.
    '''
#     @staticmethod
#     def _markOtherClefsAsChange(clef: HumdrumToken) -> None:
#         if clef.track is None:
#             return
#         ctrack: int = clef.track
#
#         current: HumdrumToken | None = clef.nextFieldToken
#         while current is not None:
#             if current.track != ctrack:
#                 break
#             current.setValue('auto', 'clefChange', 1)
#             current = current.nextFieldToken
#
#         current = clef.previousFieldToken
#         while current is not None:
#             if current.track != ctrack:
#                 break
#             current.setValue('auto', 'clefChange', 1)
#             current = current.previousFieldToken

    '''
    //////////////////////////////
    //
    // HumdrumInput::storeStemInterpretation --
    '''
    def _storeStemInterpretation(self, value: str, staffIndex: int, layerIndex: int) -> None:
        if 'stem' not in value:
            return

        ss: StaffStateVariables = self._staffStates[staffIndex]
        ending: str = value[6:]  # everything after '*stem:'

        if ending in 'x/\\':
            ss.stemType[layerIndex] = ending
        else:
            ss.stemType[layerIndex] = 'X'

#     '''
#     //////////////////////////////
#     //
#     // HumdrumInput::storeAcclev --
#     // Used for **mens accidental conversion to @accid+@edit or @accid.ges.
#     '''
#     def _storeAcclev(self,  value: str, staffIndex: int) -> None:
#         if 'acclev' not in value:
#             return
#
#         ss: StaffStateVariables = self._staffStates[staffIndex]
#
#         if len(value) > len('*acclev:') and value.startswith('*acclev:'):
#             state: str = value[8:] # everything after the colon
#             if state:
#                 if state[0].isdigit:
#                     ss.acclev = int(state[0])
#                 elif state == 'YY':
#                     ss.acclev = 1
#                 elif state == 'Y':
#                     ss.acclev = 2
#                 elif state == 'yy':
#                     ss.acclev = 3
#                 elif state == 'y':
#                     ss.acclev = 4
#         elif value == '*acclev:':
#             ss.acclev = 0
#         elif value == '*acclev':
#             ss.acclev = 0
#         elif value == '*Xacclev':
#             ss.acclev = 0

    '''
    //////////////////////////////
    //
    // HumdrumInput::getAssociatedDynamSpine -- Return the first **dynam
    //     spine before another staff spine is found; or return NULL token
    //     first;

        We are searching to the right...
    '''
    @staticmethod
    def associatedDynamSpine(token: HumdrumToken | None) -> HumdrumToken | None:
        if token is None:
            return None

        current: HumdrumToken | None = token.nextFieldToken
        while current is not None:
            if current.isStaffDataType:
                # current has reached a **kern or **mens spine
                # so we're done looking
                break
            if current.isDataType('**dynam'):
                return current
            current = current.nextFieldToken

        return None

    '''
    //////////////////////////////
    //
    // HumdrumInput::getPreviousStaffToken -- return the first staff token
    //    to the left which is not the same track as the current token, and
    //    also is the first subspine of that track.  Return NULL if no previous
    //    staff token.

        "staff token" in this context means "token in a **kern or **mens spine"
    '''
    @staticmethod
    def previousStaffToken(token: HumdrumToken | None) -> HumdrumToken | None:
        if token is None:
            return None
        if token.track is None:
            return None

        track: int = token.track
        current: HumdrumToken | None = token.previousFieldToken
        while current is not None:
            if not current.isStaffDataType:
                # step over non-staff spines
                current = current.previousFieldToken
                continue

            if current.track == track:
                # step over anything in the same track as the starting token
                current = current.previousFieldToken
                continue

            # current is the first token (in a staff spine) to the left that isn't in our track
            break

        if current is None:
            return None
        if current.track is None:
            return None

        ttrack: int = current.track

        # keep going to find the first subspine of that track (ttrack)
        firstSubspine: HumdrumToken = current
        current = current.previousFieldToken
        while current is not None:
            if current.track == ttrack:
                firstSubspine = current
                current = current.previousFieldToken
                continue  # BUGFIX: This "continue" was missing
            break

        return firstSubspine

    '''
    //////////////////////////////
    //
    // HumdrumInput::prepareSections --
    '''
    def _prepareSections(self) -> None:
        self._sectionLabels = [None] * self.lineCount
        self._numberlessLabels = [None] * self.lineCount

        secName: HumdrumToken | None = None
        noNumName: HumdrumToken | None = None

        for i, line in enumerate(self._lines):
            self._sectionLabels[i] = secName
            self._numberlessLabels[i] = noNumName

            if not line.isInterpretation:
                continue

            if line[0] is None:
                continue

            if not line[0].text.startswith('*>'):
                continue

            if '[' in line[0].text:
                # ignore expansion lists
                continue

            secName = line[0]
            self._sectionLabels[i] = secName

            # work backward until you hit a line of data, copying this
            # sectionLabel onto those previous comment and interp lines
            for j in reversed(range(0, i)):
                if self._lines[j].isData:
                    break
                self._sectionLabels[j] = self._sectionLabels[i]

            if not secName.text[-1].isdigit():
                noNumName = secName
                self._numberlessLabels[i] = noNumName  # BUGFIX: was self._sectionLabels[i]

                # work backward until you hit a line of data, copying this
                # numberlessLabel onto those previous comment and interp lines
                for j in reversed(range(0, i)):
                    if self._lines[j].isData:
                        break
                    self._numberlessLabels[j] = self._numberlessLabels[i]

        # smear the numberless labels backward across all previous lines without
        # numberless labels (until you hit a labeled line, then pick that one up
        # to keep smearing backward).
        for i in reversed(range(0, self.lineCount - 1)):
            if self._numberlessLabels[i] is None:
                if self._numberlessLabels[i + 1] is not None:
                    self._numberlessLabels[i] = self._numberlessLabels[i + 1]

    def _measureKey(self, lineIdx: int) -> tuple[int | None, int]:
        startIdx: int = lineIdx
        endIdx: int = self._measureEndLineIndex(startIdx)
        if endIdx < 0:
            # None means skip this measure, endIdx is made positive to get to next measure
            return None, -endIdx
        startIdx = self._repositionStartIndex(startIdx)
        return startIdx, endIdx

    def _firstPassSystemMeasure(self, lineIdx: int) -> int:
        measureKey: tuple[int | None, int] = self._measureKey(lineIdx)
        startIdx: int | None
        endIdx: int
        startIdx, endIdx = measureKey
        if startIdx is None:
            # skip it (but return the positive version so the client can keep walking measures)
            return endIdx

        if self.ignoreLine[startIdx]:
            # don't perform first pass on this measure (!!ignore/!!Xignore toggles)
            return endIdx

        self._firstPassMeasureStaves(measureKey)

        return endIdx

    def _firstPassMeasureStaves(self, measureKey: tuple[int | None, int]) -> None:
        measureStavesLayerDatas: list[list[list[HumdrumToken | FakeRestToken]]] = (
            self._scoreLayerTokens[measureKey]
        )

        for staffIndex, (startTok, measureStaffLayerDatas) in enumerate(
                zip(self._staffStarts, measureStavesLayerDatas)):
            if t.TYPE_CHECKING:
                # assume at least the _staffStarts all have track numbers
                assert startTok.track is not None
            self._firstPassMeasureStaff(staffIndex,
                                        startTok.track,
                                        measureStaffLayerDatas,
                                        measureKey)

    def _firstPassMeasureStaff(
        self,
        staffIndex: int,
        track: int,
        measureStaffLayerDatas: list[list[HumdrumToken | FakeRestToken]],
        measureKey: tuple[int | None, int]
    ) -> None:
        if self._staffStartsIndexByTrack[track] < 0:
            # not a kern/mens spine
            return

        ss: StaffStateVariables = self._staffStates[staffIndex]

        # create ss.tgs list for this measure == [[], [], ...] of the correct length,
        # to be filled in by the staff's first pass
        ss.tgs[measureKey] = []
        layerCount = len(measureStaffLayerDatas)
        for _ in range(0, layerCount):
            # append an empty list (i.e. containing zero BeamAndTupletGroups) for each layer
            # _firstPassContentsOfLayer will be called once for each layer, and will fill
            # in one of these lists per call.
            ss.tgs[measureKey].append([])
        for layerIndex, layerData in enumerate(measureStaffLayerDatas):
            self._firstPassContentsOfLayer(staffIndex, layerData, layerIndex, measureKey)

    def _firstPassContentsOfLayer(
        self,
        staffIndex: int,
        layerData: list[HumdrumToken | FakeRestToken],
        layerIndex: int,
        measureKey: tuple[int | None, int]
    ) -> None:
        if not layerData:
            # empty layer?!
            return

        ss: StaffStateVariables = self._staffStates[staffIndex]

        tgs: list[HumdrumBeamAndTuplet] = self._prepareBeamAndTupletGroups(layerData)
        ss.tgs[measureKey][layerIndex] = t.cast(list[HumdrumBeamAndTuplet | None], tgs)

        for tokenIdx, layerTok in enumerate(layerData):
            if isinstance(layerTok, FakeRestToken):
                continue

            # After this point, we can assume that layerTok is a real HumdrumToken
            if layerTok.isNullData:
                continue

            if layerTok.isInterpretation:
                if layerTok.text == '*Xtremolo':
                    ss.tremolo = False
                elif layerTok.text == '*tremolo':
                    ss.tremolo = True
                    self._hasTremolo = True
                continue

            if not layerTok.isData:
                continue

            # it's a data token, mark up the tokens that should turn into tremolos
            if ss.tremolo:
                # We are in a *tremolo section of the staff.
                # All tokens that start tremolos have a start beam ('L')
                if 'L' in layerTok.text:
                    self._checkForTremolo(layerData, ss.tgs[measureKey][layerIndex], tokenIdx)

    '''
    //////////////////////////////
    //
    // HumdrumInput::prepareVerses -- Assumes that m_staffstarts has been
    //      filled already.
    '''
    def _prepareVerses(self) -> None:
        if self.staffCount == 0:
            return

        line: HumdrumLine = self._staffStarts[0].ownerLine
        for i, startTok in enumerate(self._staffStarts):
            fieldIdx: int = startTok.fieldIndex
            for j in range(fieldIdx + 1, line.tokenCount):
                token: HumdrumToken | None = line[j]
                if t.TYPE_CHECKING:
                    # because j is in range
                    assert token is not None
                if token.isStaffDataType:
                    # we're done looking for associated lyrics spines
                    break

                if token.isDataType('**text') \
                        or token.isDataType('**silbe') \
                        or token.dataType.text.startswith('**vdata') \
                        or token.dataType.text.startswith('**vvdata'):
                    self._staffStates[i].hasLyrics = True

    def _prepareScoreLayerTokens(self) -> None:
        # assume no staff starts earlier than the first staff
        lineIdx: int = self._staffStarts[0].lineIndex
        while lineIdx < self.lineCount - 1:
            startIdx: int = lineIdx
            endIdx: int = self._measureEndLineIndex(startIdx)
            if endIdx < 0:
                # skip it (but return the positive version so the client can keep walking measures)
                lineIdx = -endIdx
                continue

            startIdx = self._repositionStartIndex(startIdx)

            self._scoreLayerTokens[(startIdx, endIdx)] = (
                self._generateStaffLayerTokensForMeasure(startIdx, endIdx)
            )
            lineIdx = endIdx

    def _calculateStaffStartsIndexByTrack(self) -> None:
        self._staffStartsIndexByTrack = [-1] * (self.maxTrack + 1)
        for i, startTok in enumerate(self._staffStarts):
            if t.TYPE_CHECKING:
                # assume at least the _staffStarts all have track numbers
                assert startTok.track is not None
            self._staffStartsIndexByTrack[startTok.track] = i

    def _analyzeSpineDataTypes(self) -> None:
        staffIndex: int = -1
        for startTok in self.spineStartList:
            if startTok is None:
                print('startTok is None in hf.spineStartList', file=sys.stderr)
                continue

            if startTok.isDataType('**kern'):
                staffIndex += 1
            elif startTok.isDataType('**mxhm'):
                self._hasHarmonySpine = True
                # we'll take **mxhm if there isn't anything else
                if not self._chosenHarmonyDataType:
                    self._chosenHarmonyDataType = '**mxhm'
            elif startTok.isDataType('**harte'):
                self._hasHarmonySpine = True
                # Harte is our favorite, if there's more than one
                self._chosenHarmonyDataType = '**harte'
            elif startTok.isDataType('**fing'):
                self._hasFingeringSpine = True
            elif startTok.isDataType('**string'):
                self._hasStringSpine = True
            elif startTok.isDataType('**mens'):
                staffIndex += 1
                self._hasMensSpine = True
            # Only mxhm/harte-style harmony for now
#             elif startTok.isDataType('**harm'):
#                 self._hasHarmonySpine = True
#             elif startTok.isDataType('**rhrm'):  # **recip + **harm
#                 self._hasHarmonySpine = True
#             elif startTok.dataType.text.startswith('**cdata'):
#                 self._hasHarmonySpine = True
            elif startTok.isDataType('**color'):
                self._hasColorSpine = True
            elif (startTok.isDataType('**fb')
                    or startTok.isDataType('**Bnum')):  # older name
                self._hasFiguredBassSpine = True
                if staffIndex >= 0:
                    self._staffStates[staffIndex].figuredBassState = -1
                    self._staffStates[staffIndex].isStaffWithFiguredBass = True
            elif startTok.isDataType('**fba'):
                self._hasFiguredBassSpine = True
                if staffIndex >= 0:
                    self._staffStates[staffIndex].figuredBassState = +1
                    self._staffStates[staffIndex].isStaffWithFiguredBass = True


    @staticmethod
    def _getLoColor(token: HumdrumToken, ns2: str) -> str:
        lcount: int = token.linkedParameterSetCount
        if lcount == 0:
            return ''

        for p in range(0, lcount):
            hps: HumParamSet | None = token.getLinkedParameterSet(p)
            if not hps:
                continue
            if hps.namespace1 != 'LO':
                continue
            if hps.namespace2 != ns2:
                continue

            for q in range(0, hps.count):
                paramKey: str = hps.getParameterName(q)
                paramVal: str = hps.getParameterValue(q)
                if paramKey == 'color':
                    return paramVal

        return ''

    '''
    //////////////////////////////
    //
    // HumdrumInput::hasAboveParameter -- true if has an "a" parameter
    // or has a "Z" parameter set to anything.
    '''
    @staticmethod
    def _hasAboveParameter(token: HumdrumToken, ns2: str) -> bool:
        lcount: int = token.linkedParameterSetCount
        if lcount == 0:
            return False

        for p in range(0, lcount):
            hps: HumParamSet | None = token.getLinkedParameterSet(p)
            if not hps:
                continue
            if hps.namespace1 != 'LO':
                continue
            if hps.namespace2 != ns2:
                continue

            for q in range(0, hps.count):
                paramKey: str = hps.getParameterName(q)
                if paramKey == 'a':
                    return True
                if paramKey == 'Z':
                    return True

        return False

    @staticmethod
    def _hasAboveParameterStaffAdj(
        token: HumdrumToken,
        ns2: str,
        staffAdj: int
    ) -> tuple[bool, int]:
        lcount: int = token.linkedParameterSetCount
        if lcount == 0:
            return (False, staffAdj)

        for p in range(0, lcount):
            hps: HumParamSet | None = token.getLinkedParameterSet(p)
            if not hps:
                continue
            if hps.namespace1 != 'LO':
                continue
            if hps.namespace2 != ns2:
                continue

            for q in range(0, hps.count):
                paramKey: str = hps.getParameterName(q)
                paramVal: str = hps.getParameterValue(q)
                if paramKey == 'a':
                    if paramVal == 'true':
                        # above the attached staff
                        staffAdj = 0
                    elif paramVal:
                        if paramVal[0].isdigit():
                            try:
                                staffAdj = int(paramVal)
                            except Exception:
                                return (True, staffAdj)
                            if staffAdj:
                                staffAdj = -(staffAdj - 1)
                    return (True, staffAdj)
                if paramKey == 'Z':
                    return (True, staffAdj)

        return (False, staffAdj)

    '''
    //////////////////////////////
    //
    // HumdrumInput::hasBelowParameter -- true if has an "b" parameter
    // or has a "Y" parameter set to anything.
    '''
    @staticmethod
    def _hasBelowParameter(token: HumdrumToken, ns2: str) -> bool:
        lcount: int = token.linkedParameterSetCount
        if lcount == 0:
            return False

        for p in range(0, lcount):
            hps: HumParamSet | None = token.getLinkedParameterSet(p)
            if not hps:
                continue
            if hps.namespace1 != 'LO':
                continue
            if hps.namespace2 != ns2:
                continue

            for q in range(0, hps.count):
                paramKey: str = hps.getParameterName(q)
                if paramKey == 'b':
                    return True
                if paramKey == 'Y':
                    return True

        return False

    @staticmethod
    def _hasBelowParameterStaffAdj(
        token: HumdrumToken,
        ns2: str,
        staffAdj: int
    ) -> tuple[bool, int]:
        lcount: int = token.linkedParameterSetCount
        if lcount == 0:
            return (False, staffAdj)

        for p in range(0, lcount):
            hps: HumParamSet | None = token.getLinkedParameterSet(p)
            if not hps:
                continue
            if hps.namespace1 != 'LO':
                continue
            if hps.namespace2 != ns2:
                continue

            for q in range(0, hps.count):
                paramKey: str = hps.getParameterName(q)
                paramVal: str = hps.getParameterValue(q)
                if paramKey == 'b':
                    if paramVal == 'true':
                        # below the attached staff
                        staffAdj = 0
                    elif paramVal:
                        if paramVal[0].isdigit():
                            try:
                                staffAdj = int(paramVal)
                            except Exception:
                                return (True, staffAdj)
                            if staffAdj:
                                staffAdj = -(staffAdj - 1)
                    return (True, staffAdj)
                if paramKey == 'Y':
                    return (True, staffAdj)

        return (False, staffAdj)

    '''
    //////////////////////////////
    //
    // HumdrumInput::hasCenterParameter -- true if has a "c" parameter is present
    // with optional staff adjustment.
    '''
    @staticmethod
    def _hasCenterParameterStaffAdj(
        token: HumdrumToken,
        ns2: str,
        staffAdj: int
    ) -> tuple[bool, int]:
        # returns (hasCenter, newStaffAdj))
        lcount: int = token.linkedParameterSetCount
        if lcount == 0:
            return (False, staffAdj)

        for p in range(0, lcount):
            hps: HumParamSet | None = token.getLinkedParameterSet(p)
            if not hps:
                continue
            if hps.namespace1 != 'LO':
                continue
            if hps.namespace2 != ns2:
                continue

            for q in range(0, hps.count):
                paramKey: str = hps.getParameterName(q)
                paramVal: str = hps.getParameterValue(q)
                if paramKey == 'c':
                    if paramVal == 'true':
                        # below the attached staff
                        staffAdj = 0
                    elif paramVal:
                        if paramVal[0].isdigit():
                            try:
                                staffAdj = int(paramVal)
                            except Exception:
                                return (True, staffAdj)
                            if staffAdj:
                                staffAdj = -(staffAdj - 1)
                    return (True, staffAdj)
                if paramKey == 'Y':
                    return (True, staffAdj)

        return (False, staffAdj)

    '''
    //////////////////////////////
    //
    // HumdrumInput::hasLayoutParameter -- True if there is a layout parameter
            with this ns2 and key, whose value is not "0" or "False".
    '''
    @staticmethod
    def _hasTrueLayoutParameter(token: HumdrumToken, ns2: str, key: str) -> bool:
        lcount: int = token.linkedParameterSetCount
        if lcount == 0:
            return False

        for p in range(0, lcount):
            hps: HumParamSet | None = token.getLinkedParameterSet(p)
            if not hps:
                continue
            if hps.namespace1 != 'LO':
                continue
            if hps.namespace2 != ns2:
                continue

            for q in range(0, hps.count):
                paramKey = hps.getParameterName(q)
                if paramKey != key:
                    continue
                value = hps.getParameterValue(q)
                if value in ('0', 'false'):
                    return False
                return True

        return False

    '''
    //////////////////////////////
    //
    // HumdrumInput::analyzeDefaultLayoutStyles -- search for lines starting with:
    //   !!LO-style: and set the default parameters for the given LO category.
    // Example:
    //   !!!LO-style:REH:enc=dbox:encc=crimson:color=limegreen:absys:fs=200%
    //
    //   These values will be inserted into the m_layoutDefaultStyles variable.
    //   In this case:
    //       m_layoutDefaultStyle["REH"]["enc"]   = "dbox";
    //       m_layoutDefaultStyle["REH"]["encc"]  = "crimson";
    //       m_layoutDefaultStyle["REH"]["color"] = "limegreen";
    //       m_layoutDefaultStyle["REH"]["absys"] = "1";
    //       m_layoutDefaultStyle["REH"]["fs"]    = "200%";
    //  These defaults will be loaded before processing a !!LO:REH layout parameter set.
    //  The defaults can be placed anywhere in the file, and later defaults for the
    //  same category will replace ones earllier in the file.
    '''
    def analyzeDefaultLayoutStyles(self) -> None:
        self._layoutDefaultStyles = {}
        prefix: str = '!!!LO-style:'
        for line in self._lines:
            if line.hasSpines:
                continue
            if not line.text.startswith(prefix):
                continue

            rest: str = line.text[len(prefix):]
            pieces: list[str] = rest.split(':')
            if not pieces:
                continue

            category: str = pieces[0]
            self._layoutDefaultStyles[category] = {}

            for piece in pieces[1:]:
                if piece == '':
                    continue
                if piece and piece[0] == '=':
                    continue
                m = re.search(r'^([^=]+)=(.*)$', piece)
                if m:
                    key: str = m.group(1)
                    value: str = m.group(2)
                    value = html.unescape(value)
                    self._layoutDefaultStyles[category][key] = value
                else:
                    key = piece
                    value = '1'
                    self._layoutDefaultStyles[category][key] = value

    '''
    //////////////////////////////
    //
    // HumdrumInput::getDefaultLayoutParameter -- Return the default layout
    //   parameter for a given cateogry and category parameter.  If there is
    //   no given parameter, returns "".
    '''
    def _getDefaultLayoutParameter(self, category: str, parameter: str) -> str:
        if not self._layoutDefaultStyles:
            return ''

        catDict: dict[str, str] = self._layoutDefaultStyles.get(category, {})
        paramVal: str = catDict.get(parameter, '')
        return paramVal
