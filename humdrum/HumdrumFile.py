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
# Copyright:     (c) 2021 Greg Chapman
# License:       BSD, see LICENSE
# ------------------------------------------------------------------------------
import re
import sys
import math
from fractions import Fraction
from typing import Union
import copy

import music21 as m21

from humdrum import HumdrumSyntaxError
from humdrum import HumdrumInternalError
from humdrum import HumdrumFileContent
from humdrum import HumdrumLine
from humdrum import HumdrumToken
from humdrum import HumNum
from humdrum import HumHash
from humdrum import HumParamSet
from humdrum import Convert
from humdrum import M21Convert

### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

'''
    HumdrumFile class is HumdrumFileContent plus conversion to music21.stream.Score
'''

# Note that these durations are expressed in quarter notes,
# so HumNum(1,2), a.k.a "a half" actually means an eighth note,
# which has one beam.
durationNoDotsToNumBeams = {
    HumNum(1,   2):    1, # eighth note has 1 beam
    HumNum(1,   4):    2, # 16th note has 2 beams
    HumNum(1,   8):    3, # 32nd note has 3 beams
    HumNum(1,  16):    4, # 64th note has 4 beams
    HumNum(1,  32):    5, # 128th note has 5 beams
    HumNum(1,  64):    6, # 256th note has 6 beams
    HumNum(1, 128):    7, # 512th note has 7 beams
    HumNum(1, 256):    8, # 1024th note has 8 beams
    HumNum(1, 512):    9, # 2048th note has 9 beams
}

humdrumInstrumentClassCodeToInstrumentName = {
    'vox':  'Vocalist',
    'str':  'StringInstrument',
    'ww':   'WoodwindInstrument',
    'bras': 'BrassInstrument',
    'klav': 'KeyboardInstrument',
    'perc': 'Percussion',
}

humdrumInstrumentCodeToInstrumentName = {
    'soprn':    'Soprano',
    'cant':     'Soprano',  # Found in many sources, but not a predefined humdrum instrument
    'mezzo':    'MezzoSoprano',
    'calto':    'Contralto',
    'tenor':    'Tenor',
    'barit':    'Baritone',
    'bass':     'Bass',
    'vox':      'Vocalist',
    'feme':     'FemaleVoice',
    'male':     'MaleVoice',
    'nfant':    "ChildVoice",
    'recit':    'Recitativo',
    'lyrsp':    'LyricSoprano',
    'drmsp':    'DramaticSoprano',
    'colsp':    'ColoraturaSoprano',
    'alto':     'Alto',
    'ctenor':   'CounterTenor',
    'heltn':    'TenoreRobusto',
    'lyrtn':    'LyricTenor',
    'bspro':    'BassoProfondo',
    'bscan':    'BassoCantante',
    'false':    'Falsetto',
    'castr':    'Castrato',

    # String Instruments
    'archl':    'Archlute', # archiluth (Fr.); liuto attiorbato/arcileuto/arciliuto (It.)
    'arpa':     'Harp',     # arpa (It.), arpa (Span.)
    'banjo':    'Banjo',
    'biwa':     'Biwa',
    'bguit':    'ElectricBass',
    'cbass':    'Contrabass',
    'cello':    'Violoncello',
    'cemba':    'Harpsichord',  # clavecin (Fr.); Cembalo (Ger.); cembalo (It.)
    'cetra':    'Cittern',      # cistre/sistre (Fr.); Cither/Zitter (Ger.); cetra/cetera (It.)
    'clavi':    'Clavichord',   # clavicordium (Lat.); clavicorde (Fr.)
    'dulc':     'Dulcimer',     # or cimbalom; Cimbal or Hackbrett (Ger.)
    'eguit':    'ElectricGuitar',
    'forte':    'FortePiano',
    'guitr':    'Guitar',       # guitarra (Span.); guitare (Fr.); Gitarre (Ger.); chitarra (It.)
    'hurdy':    'HurdyGurdy',   # variously named in other languages
    'liuto':    'Lute',         # lauto, liuto leuto (It.); luth (Fr.); Laute (Ger.)
    'kit':      'Kit',          # variously named in other languages
    'kokyu':    'Kokyu',        # (Japanese spike fiddle)
    'komun':    'KomunGo',      # (Korean long zither)
    'koto':     'Koto',         # (Japanese long zither)
    'mando':    'Mandolin',     # mandolino (It.); mandoline (Fr.); Mandoline (Ger.)
    'piano':    'Piano',
    'pipa':     'ChineseLute',
    'psalt':    'Psaltery',     # (box zither)
    'qin':      'Qin',          #ch'in (Chinese zither)
    'quitr':    'Gittern',      # (short-necked lute); quitarre (Fr.); Quinterne (Ger.)
    'rebec':    'Rebec',        # rebeca (Lat.); rebec (Fr.); Rebec (Ger.)
    'bansu':    'Bansuri',
    'sarod':    'Sarod',
    'shami':    'Shamisen',     # (Japanese fretless lute)
    'sitar':    'Sitar',
    'tambu':    'Tambura',      # tanpura
    'tanbr':    'Tanbur',
    'tiorb':    'Theorbo',      # tiorba (It.); tèorbe (Fr.); Theorb (Ger.)
    'ud':       'Ud',
    'ukule':    'Ukulele',
    'vina':     'Vina',
    'viola':    'Viola',        # alto (Fr.); Bratsche (Ger.)
    'violb':    'BassViolaDaGamba', # viole (Fr.); Gambe (Ger.)
    'viold':    'ViolaDamore',  # viole d'amour (Fr.); Liebesgeige (Ger.)
    'violn':    'Violin',       # violon (Fr.); Violine or Geige (Ger.); violino (It.)
    'violp':    'PiccoloViolin',# violino piccolo (It.)
    'viols':    'TrebleViolaDaGamba',# viole (Fr.); Gambe (Ger.)
    'violt':    'TenorViolaDaGamba', # viole (Fr.); Gambe (Ger.)
    'zithr':    'Zither', #; Zither (Ger.); cithare (Fr.); cetra da tavola (It.)

    # Wind Instruments
    'accor':    'Accordion',    # ; accordéon (Fr.); Akkordeon (Ger.)
    'armon':    'Harmonica',    # ; armonica (It.)
    'bagpS':    'Bagpipes',     # (Scottish)
    'bagpI':    'Bagpipes',     # (Irish)
    'baset':    'BassettHorn',
    'calam':    'Chalumeau',    # calamus (Lat.); kalamos (Gk.)
    'calpe':    'Calliope',
    'cangl':    'EnglishHorn',  # cor anglais (Fr.)
    'chlms':    'SopranoShawm', # chalmeye, shalme, etc.; chalemie (Fr.); ciaramella (It.)
    'chlma':    'AltoShawm',    # chalmeye, shalme, etc.
    'chlmt':    'TenorShawm',   # chalmeye, shalme, etc.
    'clars':    'SopranoClarinet',  # (in either B-flat or A); clarinetto (It.)
    'clarp':    'PiccoloClarinet',
    'clara':    'AltoClarinet', # (in E-flat)
    'clarb':    'BassClarinet', # (in B-flat)
    'cor':      'Horn',         # cor (Fr.); corno (It.); Horn (Ger.)
    'cornm':    'Cornemuse',    # French bagpipe
    'corno':    'Cornett',      # (woodwind instr.); cornetto (It.); cornaboux (Fr.); Zink (Ger.)
    'cornt':    'Cornet',       # (brass instr.); cornetta (It.); cornet à pistons (Fr.); Cornett (Ger.)
    'ctina':    'Concertina',   # concertina (Fr.); Konzertina (Ger.)
    'fagot':    'Bassoon',      # fagotto (It.)
    'fag_c':    'Contrabassoon',# contrafagotto (It.)
    'fife':     'Fife',
    'flt':      'Flute',        # flauto (It.); Flöte (Ger.); flûte (Fr.)
    'flt_a':    'AltoFlute',
    'flt_b':    'BassFlute',
    'fltds':    'SopranoRecorder', # flûte à bec, flûte douce (Fr.);
    #            Blockflöte (Ger.); flauto dolce (It.)
    'fltdn':    'SopraninoRecorder',
    'fltda':    'AltoRecorder',
    'fltdt':    'TenorRecorder',
    'fltdb':    'BassRecorder',
    'flugh':    'Flugelhorn',
    'hichi':    'Hichiriki',    # (Japanese double reed used in gagaku)
    'krums':    'SopranoCrumhorn',  # Krummhorn/Krumbhorn (Ger.); tournebout (Fr.)
    'kruma':    'AltoCrumhorn',
    'krumt':    'TenorCrumhorn',
    'krumb':    'BassCrumhorn',
    'nokan':    'Nokan',        # (Japanese flute for the no theatre)
    'oboe':     'Oboe',         # hautbois (Fr.); Hoboe, Oboe (Ger.): oboe (It.)
    'oboeD':    'OboeDamore',
    'ocari':    'Ocarina',
    'organ':    'PipeOrgan',    # organum (Lat.); organo (It.); orgue (Fr.); Orgel (Ger.)
    'panpi':    'PanFlute',     # panpipe
    'picco':    'Piccolo',      # flute
    'piri':     'KoreanPiri',
    'porta':    'PortativeOrgan',
    'rackt':    'Racket',       # Rackett (Ger.); cervelas (Fr.)
    'reedo':    'ReedOrgan',
    'sarus':    'Sarrusophone',
    'saxN':     'SopraninoSaxophone',   # (in E-flat)
    'saxS':     'SopranoSaxophone',     # (in B-flat)
    'saxA':     'AltoSaxophone',        # (in E-flat)
    'saxT':     'TenorSaxophone',       # (in B-flat)
    'saxR':     'BaritoneSaxophone',    # (in E-flat)
    'saxB':     'BassSaxophone',        # (in B-flat)
    'saxC':     'ContrabassSaxophone',  # (in E-flat)
    'shaku':    'Shakuhachi',
    'sheng':    'MouthOrgan',           # (Chinese)
    'sho':      'MouthOrgan',           # (Japanese)
    'sxhS':     'SopranoSaxhorn',       # (in B-flat)
    'sxhA':     'AltoSaxhorn',          # (in E-flat)
    'sxhT':     'TenorSaxhorn',         # (in B-flat)
    'sxhR':     'BaritoneSaxhorn',      # (in E-flat)
    'sxhB':     'BassSaxhorn',          # (in B-flat)
    'sxhC':     'ContrabassSaxhorn',    # (in E-flat)
    'tromt':    'Trombone',             # tenor; trombone (It.); trombone (Fr.); Posaune (Ger.)
    'tromb':    'BassTrombone',
    'tromp':    'Trumpet',              # ; tromba (It.); trompette (Fr.); Trompete (Ger.)
    'tuba':     'Tuba',
    'zurna':    'Zurna',

    # Percussion Instruments
    'bdrum':    'BassDrum',         # (kit)
    'campn':    'ChurchBells',      # bell; campana (It.); cloche (Fr.); campana (Span.)
    'caril':    'ChurchBells',      # carillon
    'casts':    'Castanets',        # castañetas (Span.); castagnette (It.)
    'chime':    'TubularBells',     # chimes
    'clest':    'Celesta',          # céleste (Fr.)
    'crshc':    'CrashCymbals',     # (kit)
    'fingc':    'FingerCymbal',
    'glock':    'Glockenspiel',
    'gong':     'Gong',
    'marac':    'Maracas',
    'marim':    'Marimba',
    'piatt':    'Cymbals',          # piatti (It.); cymbales (Fr.); Becken (Ger.); kymbos (Gk.)
    'ridec':    'RideCymbals',      # (kit)
    'sdrum':    'SnareDrum',        # (kit)
    'spshc':    'SplashCymbals',    # (kit)
    'steel':    'SteelDrum',        # tinpanny
    'tabla':    'Tabla',
    'tambn':    'Tambourine',       # timbrel; tamburino (It.); Tamburin (Ger.)
    'timpa':    'Timpani',          # timpani (It.); timbales (Fr.); Pauken (Ger.)
    'tom':      'TomTom',           # drum
    'trngl':    'Triangle',         # triangle (Fr.); Triangel (Ger.); triangolo (It.)
    'vibra':    'Vibraphone',
    'xylo':     'Xylophone',        # xylophone (Fr.); silofono (It.)

    # Keyboard Instruments
    # dup *Iaccor    accordion; accordéon (Fr.); Akkordeon (Ger.)
    # dup *Icaril    carillon
    # dup *Icemba    harpsichord; clavecin (Fr.); Cembalo (Ger.); cembalo (It.)
    # dup *Iclavi    clavichord; clavicordium (Lat.); clavicorde (Fr.)
    # dup *Iclest    'Celesta',          # céleste (Fr.)
    # dup *Iforte    fortepiano
    'hammd':    'ElectricOrgan',    # Hammond electronic organ
    # dup *Iorgan    pipe organ; orgue (Fr.); Orgel (Ger.);
    # organo (It.); organo (Span.); organum (Lat.)
    # dup *Ipiano    pianoforte
    # dup *Iporta    portative organ
    # dup *Ireedo    reed organ
    'rhode':    'ElectricPiano',    # Fender-Rhodes electric piano
    'synth':    'Synthesizer',      # keyboard synthesizer
}

def getInstrumentNameFromCode(instrumentCode: str, iTrans: str) -> str:
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
        return iName + ' in B-flat' # sounds B-flat below C
    if iTrans == '*ITrd2c3':
        return iName + ' in A'      # sounds A below C
    if iTrans == '*ITrd5c9':
        return iName + ' in E-flat' # sounds E-flat below C
    if iTrans == '*ITrd-2c-3':
        return iName + ' in E-flat' # sounds E-flat above C

    return iName

def getInstrumentNameFromClassCode(instrumentClassCode: str) -> str:
    if instrumentClassCode in humdrumInstrumentClassCodeToInstrumentName:
        return humdrumInstrumentClassCodeToInstrumentName[instrumentClassCode]

    return instrumentClassCode

class Phrase(m21.spanner.Slur):
    '''
    A Slur that represents a Phrase.  Code that doesn't know about Phrases will
    (hopefully) just see that it is a Slur.  Code that does know about Phrases
    can do Phrase-specific things.
    '''

class HumdrumTie:
    def __init__(self):
        self.startNote: m21.note.Note = None
        self.startLayerIndex: int = None
        self.startToken: HumdrumToken = None
        self.startSubTokenStr: str = None
        self.startSubTokenIdx: int = None

        self.pitch: int = None
        self.startTime: HumNum = None
        self.endTime: HumNum = None

        self.wasInserted: bool = False

    def setStart(self,
                 startLayerIndex: int,
                 startNote: m21.note.Note,
                 startToken: HumdrumToken,
                 startSubTokenStr: str,
                 startSubTokenIdx: int):
        self.startLayerIndex = startLayerIndex
        self.startNote = startNote
        self.startToken = startToken
        self.startSubTokenStr = startSubTokenStr
        self.startSubTokenIdx = startSubTokenIdx

        # pitch computation is a little sloppy (on purpose?).
        # This will (e.g.) allow a C-flat to be tied to a B-natural.
        # base40 would be more stringent, but wouldn't work for triple
        # flats and triple sharps.
        self.pitch = Convert.kernToMidiNoteNumber(startSubTokenStr)
        self.startTime = startToken.durationFromStart
        self.endTime = self.startTime + startToken.duration

    def setEndAndInsert(self, endNote: m21.note.Note, endSubTokenStr: str) -> m21.tie.Tie:
        startTieType: str = 'start'
        if '_' in self.startSubTokenStr:
            startTieType = 'continue'

        startTie: m21.tie.Tie = m21.tie.Tie(startTieType)
        self.startNote.tie = startTie

        # also add an end tie to endNote (but not if the end tie is a continue,
        # which will be handled shortly since it's in the list as a start)
        if ']' in endSubTokenStr: # not '_'
            endNote.tie = m21.tie.Tie('stop') # that's it, no style or placement

        self.wasInserted = True
        return startTie

class HumdrumBeamAndTuplet:
    # A struct (per note/chord/rest) describing a beam and/or tuplet group.
    # Tuplets can contain rests, but beams cannot. --gregc
    def __init__(self):
        # for tuplets
        self.group: int = 0      # tuplet group number (within layer)

        # numNotesActual and numNotesNormal are a ratio of sorts, but tupletRatio holds
        # the lowest-common-denominator ratio.  For example, for a tuplet that has 15 16th notes
        # in the space of 10 16th notes, numNotesActual is 15, and numNotesNormal is 10, but
        # tupletMultiplier is still 2/3 (i.e. all note durations are 2/3 of normal duration)
        self.numNotesActual: int = 1
        self.numNotesNormal: int = 1
        self.tupletMultiplier: HumNum = HumNum(1, 1)
        self.numScale: int = 1

        self.tupletStart: int = 0 # set to tuplet group number (on starting note/rest)
        self.tupletEnd: int = 0   # set to tuplet group number (on ending note/rest)
        self.forceStartStop: bool = False # True if Humdrum data made us start or end
                                 # this tuplet at a specific location (i.e. we should
                                 # encode that in music21).  If False, we leave tuplet.type
                                 # unspecified in music21 (neither 'start' nor 'stop'), and
                                 # let the starts/stops fall where they may.

        # for beamed normal notes
        self.beamStart: int = 0  # set to beam number on starting note
        self.beamEnd: int = 0    # set to beam number on ending note

        # for beamed grace notes
        self.gbeamStart: int = 0 # set to beam number on starting grace note
        self.gbeamEnd: int = 0   # set to beam number on ending grace note

        # for all
        self.token: HumdrumToken = None # the token for this note/rest


class BeamAndTupletGroupState:
    # A struct containing the current state of beams and tuplets as we walk the tokens in a layer
    def __init__(self):
        # for beams
        self.inBeam: bool = False                # set to True when a beam starts, False when it ends
        self.previousBeamTokenIdx: int = -1      # index (in layer) of the previous token in a beam
        # for grace note beams
        self.inGBeam: bool = False               # set to True when a gbeam starts, False when it ends
        self.previousGBeamTokenIdx: int = -1     # index (in layer) of the previous token in a gbeam
        # for tuplets
        self.inTuplet: bool = False                # set to True when a tuplet starts, False when it ends
        self.m21Tuplet: m21.duration.Tuplet = None # tuplet template for every note in the current tuplet

MAXLAYERSFORCUESIZE = 100

class StaffStateVariables:
    def __init__(self):
        '''
            First we have permanent info we have figured out about this staff
        '''
        # the m21 Part for the staff
        self.m21Part: m21.stream.Part = None

        # the m21 Instrument for the staff
# in the part at offset 0        self.instrument: m21.instrument.Instrument = None

        # verse == keeps track of whether or not staff contains associated
        # **text/**silbe spines which will be converted into lyrics.
        # Also **vdata and **vvdata spines --gregc
        self.hasLyrics: bool = False

        # verse_labels == List of verse labels that need to be added to the
        # current staff.
        self.lyricLabels: [HumdrumToken] = []

        # figured bass
        self.figuredBassState: int = None
        self.isStaffWithFiguredBass: bool = False # true if staff has figured bass (in associated spine)

        # instrument info
        self.instrumentClass: str = None # e.g. 'bras' is BrassInstrument

        # hand-transposition info (we have to undo it as we translate to music21, since
        # there is no way in music21 to mark a staff has having been transposed from the
        # original).
        # This is completely orthogonal to transposing instruments, which are handled
        # entirely separately.
#         self.wasTransposedBy = 0 # base40

        # staff info
        self.staffScaleFactor: float = 1.0
        self.numStaffLines: int = 5

        self.dynamPosDefined: bool = False
        self.dynamPos: int = 0
        self.dynamStaffAdj: int = 0

        # first info in part (we hang on to these here, waiting for a Measure to put them in)
        self.firstM21Clef: m21.clef.Clef = None
        self.firstM21KeySig: m21.key.KeySignature = None # will be m21.key.Key if we can
        self.firstM21TimeSig: m21.meter.TimeSignature = None

        # ties (list of starts that we search when we see an end)
        self.ties: [HumdrumTie] = []

        # tremolo is active on this staff (*tremolo and *Xtremolo)
        self.tremolo: bool = False

        # noteHead style for this staff, according to *head interpretation
        self.noteHead: str = ''

        # are notes in specific layer cue-sized? (according to *cue and *Xcue interps)
        self.cueSize: [bool] = [False] * MAXLAYERSFORCUESIZE

        # are tuplets suppressed in this staff?
        # (according to *beamtup/*Xbeamtup, *brackettup/*Xbrackettup, *tuplet/*Xtuplet)
        self.suppressTupletNumber: bool = False
        self.suppressTupletBracket: bool = False

        '''
            Next we have temporary (processing) state about this staff (current measure, etc)
        '''
        self.mostRecentlySeenClefTok: HumdrumToken = None

    def printState(self, prefix: str):
        print('{}hasLyrics: {}'.format(prefix, self.hasLyrics))
        print('{}lyricLabels: {}', self.lyricLabels)


class HumdrumFile(HumdrumFileContent):
    # add XML print routines?

    def __init__(self, fileName: str = None):
        super().__init__(fileName) # initialize the HumdrumFileBase fields

        self.m21Stream: m21.stream.Score = None

        self._staffStarts: [HumdrumToken] = None    # len = staffCount
        self._staffStartsIndexByTrack: [int] = None # len = staffCount + 1 a.k.a. rkern, or "ReverseKernIndex"

        # all sorts of info about each staff, and some temporary state as well
        self._staffStates: [StaffStateVariables] = None # len = staffCount

        # top-level info
        self._hasHarmonySpine: bool = False
        self._hasFingeringSpine: bool = False
        self._hasKernSpine: bool = False
        self._hasStringSpine: bool = False
        self._hasMensSpine: bool = False
        self._hasFiguredBassSpine: bool = False
        self._hasColorSpine: bool = False
        self._hasTremolo: bool = False # *tremolo interpretation has been seen somewhere

        # initial state (after parsing the leading comments and interps)
        self._initialTempoName: str = ''
        self._initialTempoBPM: float = 0.0

        # time signature info
        self._timeSigDurationsByLine: [HumNum] = None
        self._timeSignaturesWithLineIdx: [tuple] = []  # each tuple is (top: int, bot: int, lineIndex: int)

        # oclef, omet, okey (mens-only stuff)
        self._oclefs: [tuple] = []          # each tuple is (partNum, oclef token)
        self._omets: [tuple] = []           # each tuple is (partNum, omet token)
        self._okeys: [tuple] = []           # each tuple is (partNum, okey token)


        # section labels and non-numbered labels (len = lineCount)
        self._sectionLabels: [HumdrumToken] = None
        self._numberlessLabels: [HumdrumToken] = None

        # staff group names and abbreviations
        self._groupNames: dict = dict()         # {int, str}
        self._groupNameTokens: dict = dict()    # {int, HumdrumToken}
        self._groupAbbrevs: dict = dict()       # {int, str}
        self._groupAbbrevTokens: dict = dict()  # {int, HumdrumToken}

        # metadata (from biblio records)
        self._biblio: {(str, str)} = {}

        # conversion processing state

        # _layerTokens: current system measure represented as a 3d list of tokens.
        # It contains a list of staves, each of which is a list of layers, each of which
        # is a list of tokens. This is produced by _generateStaffLayerTokensForMeasure()
        self._layerTokens: [[[HumdrumToken]]] = []

        # _oneMeasurePerStaff: current measure (i.e. a list of Measures) across all staves.  Indexed by staffIndex.
        self._oneMeasurePerStaff: [m21.stream.Measure] = []

        # _allMeasuresPerStaff: list of all measures per staff. Indexed by measureIndex (0:numMeasures), then by staffIndex (0:numStaves)
        self._allMeasuresPerStaff: [[m21.stream.Measure]] = []

        # _m21BreakAtStartOfNextMeasure: a SystemLayout or PageLayout object to be inserted
        # at start of the next measure
        self._m21BreakAtStartOfNextMeasure: [m21.Music21Object] = None # SystemLayout or PageLayout

        # _nextLeftBarlineStartsRepeat: a note to the next measure from the previous
        # measure, saying "please have your left barline start a repeat section"
        self._nextLeftBarlineStartsRepeat: bool = False

    def createMusic21Stream(self) -> m21.stream.Stream:
        # First, analyze notation: this is extra analysis, not done by default,
        # which lives in HumdrumFileContent
        self.analyzeNotation()

        # Create a list of the parts, and which spine represents them
        self._staffStarts = self.spineStartListOfType(['**kern', '**mens'])

        if not self._staffStarts: # if empty list or None
            # No parts in file, give up.  Return an empty score.
            self.m21Stream = m21.stream.Score()
            return self.m21Stream

        # init some lists of staff info
        self._initializeStaffStates()

        # figure out what we have
        self._analyzeSpineDataTypes()

        # reverse staff start order, since top part is last spine
        self._staffStarts.reverse()
        self._calculateStaffStartsIndexByTrack()

        # prepare more stuff
        self._prepareLyrics() # which staffs have associated lyrics?
        self._prepareSections() # associate numbered and unnumbered section names with lines
        self._prepareMetadata() # pull standard biblio keys/values out of reference records
        self._prepareTimeSignatures() # gather time signature info

        # set up m21Stream high-level structure (Score:Parts, StaffGroups layout, Metadata, Tempo, etc)
        self._createInitialScore()

        # all the measures
        lineIdx: int = self._staffStarts[0].lineIndex # assumes no staff starts earlier than the first
        while lineIdx < self.lineCount - 1:
            lineIdx = self._convertSystemMeasure(lineIdx) # returns the line number of the next measure
            self._checkForInformalBreak(lineIdx)

        self._processHangingTieStarts()

        # Do something so (e.g.) 'Piano'/'Pno.' ends up in the right place
        # between the two staves that are the piano grand staff, say, in a piece
        # for piano and orchestra...
        # For MEI it is promoteInstrumentNames/AbbreviationsToGroup, but in music21
        # there's no higher object for the piano grand staff, just the two PartStaffs.
        # In the m21.layout.StaffGroup object there's a place for group name/abbrev.
        # So, for a group without a name/abbrev, and with every staff in the group
        # having the same instrument name/abbrev (or none at all), we could promote
        # that staff instrument name/abbrev to the StaffGroup group name/abbrev.
        # TODO: Promote instrument name/abbrev (Organ) to m21.layout.StaffGroup object (grand staff)

        return self.m21Stream

    '''
    //////////////////////////////
    //
    // HumdrumInput::processHangingTieStarts -- Deal with tie starts that were
    //    never matched with tie ends.
    '''
    def _processHangingTieStarts(self):
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
    def _processHangingTieStart(self, tieInfo: HumdrumTie):
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
    def _processHangingTieEnd(note: m21.note.Note, tstring: str):
        if '_' in tstring:
            return # 'continue' will be handled in the ss.ties list as a tieStart

        note.tie = m21.tie.Tie('stop') # that's it, no style or placement

    @property
    def staffCount(self) -> int:
        return len(self._staffStarts)

    def _initializeStaffStates(self):
        self._staffStates = []
        for _ in range(0, self.staffCount):
            self._staffStates.append(StaffStateVariables())

    def _prepareMetadata(self):
        for bibLine in self.referenceRecords():
            key = bibLine.referenceKey
            value = bibLine.referenceValue
            self._biblio[key] = value

    '''
    //////////////////////////////
    //
    // HumdrumInput::prepareTimeSigDur -- create a list of the durations of time
    //      signatures in the file, indexed by hum::HumdrumFile line number.  Only
    //      the first spine in the file is considered.
    '''
    def _prepareTimeSignatures(self):
        top: int = -1
        bot: int = -1

        self._timeSigDurationsByLine = [HumNum(-1)] * self.lineCount
        self._timeSignaturesWithLineIdx = []

        starts = self.spineStartListOfType('**kern')
        if not starts: # None or empty list
            starts = self.spineStartListOfType('**recip')
            if not starts: # None or empty list
                # no **kern or **recip so give up
                return

        startTok = starts[0]
        if startTok is None:
            return

        curDur: HumNum = HumNum(-1)

        token = startTok.nextToken(0) # stay left if there's a split
        while token is not None:
            lineIdx: int = token.lineIndex
            if not token.isTimeSignature:
                self._timeSigDurationsByLine[lineIdx] = curDur
                token = token.nextToken(0) # stay left if there's a split
                continue
            top, bot = token.timeSignature
            self._timeSignaturesWithLineIdx.append((top, bot, lineIdx))
            curDur = HumNum(top, bot)
            curDur *= 4 # convert to duration in quarter notes

            self._timeSigDurationsByLine[lineIdx] = curDur
            token = token.nextToken(0) # stay left if there's a split

        self._timeSigDurationsByLine[-1] = curDur

        for i in reversed(range(0, self.lineCount-1)):
            if self._timeSigDurationsByLine[i] == 0:
                self._timeSigDurationsByLine[i] = self._timeSigDurationsByLine[i + 1]


    '''
    //////////////////////////////
    //
    // HumdrumInput::prepareStaffGroups --  Add information about each part and
    //    group by brackets/bar groupings

        Set up m21Stream high-level structure (Score: Parts, StaffGroups layout, Metadata, Tempo, etc).
        _createInitialScore is not called unless there is at least one staff.

    '''
    def _createInitialScore(self):
        self.m21Stream = m21.stream.Score()

        # Initial tempo
        self._createInitialTempo() # Q: why is initial tempo treated differently from other tempos?

        # Info for each part (fillPartInfo)
        for i, startTok in enumerate(self._staffStarts):
            self._createPart(startTok, i+1, self.staffCount)

        # m21.layout.StaffGroup for each group of staves, using !!system-decoration, if present
        self._createStaffGroups()

        # m21.metadata.Metadata for the score
        self._createScoreMetadata()

    '''
    //////////////////////////////
    //
    // HumdrumInput::convertSystemMeasure -- Convert one measure of
    //     a Humdrum score into an MEI measure element.

        Convert one measure of a Humdrum score into a Music21 Measure
    '''
    def _convertSystemMeasure(self, lineIdx: int) -> int:
        # We return the line number of the next measure
        startIdx: int = lineIdx
        endIdx: int = self._measureEndLineIndex(startIdx)

        if endIdx < 0:
            # empty measure, skip it.  This can happen at the start of
            # a score if there is an invisible measure before the start of the
            # data, or if there is an ending bar before the ending of the data.
            return -endIdx # make it positive again

        # if self._ignore[startIdx]:
        #     # don't convert this measure (!!ignore/!!Xignore toggles)
        #     return endIdx

        # if self._multirest[startIdx] < 0:
        #     # this is a whole-measure rest, but it is part of a multi-measure rest sequence
        #     return endIdx

        foundDataBefore: bool = False
        for i in reversed(range(0, startIdx + 1)): # start at startIdx, work back through 0
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

        self._setupSystemMeasures(startIdx, endIdx)
        self._generateStaffLayerTokensForMeasure(startIdx, endIdx)
        self._convertMeasureStaves(startIdx, endIdx)
        #self._checkForRehearsal(startIdx)

        # self._addFTremSlurs() This clearly does nothing in iohumdrum.cpp; I bet it has been replaced

        self._checkForFormalBreak(endIdx)

        return endIdx

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
    def _setupSystemMeasures(self, startLineIdx: int, endLineIdx: int):
        measureNumber: Union[int, str] = self._getMeasureNumber(startLineIdx)

        self._oneMeasurePerStaff = []
        for i in range(0, self.staffCount):
            ss: StaffStateVariables = self._staffStates[i]
            measure: m21.stream.Measure = m21.stream.Measure(measureNumber)
            self._oneMeasurePerStaff.append(measure)
            ss.m21Part.append(measure)

            if self._lines[startLineIdx].durationFromStart <= 0:
                # first measure... we already have the clef, keysig, and timesig
                # for this measure waiting for us in _staffState[i]
                if ss.firstM21Clef:
                    measure.insert(0, ss.firstM21Clef)
                if ss.firstM21KeySig:
                    measure.insert(0, ss.firstM21KeySig)
                if ss.firstM21TimeSig:
                    measure.insert(0, ss.firstM21TimeSig)

            # in verovio _nextLeftBarlineStartsRepeat is m_leftbarstyle (only ever set
            # to BARRENDITION_rptstart or BARRENDITION_NONE, so for me it's a bool)
            if self._nextLeftBarlineStartsRepeat:
                # The previous measure ended with a "start repeat" or "end/start repeat"
                # barline, which can only be achieved in music21 with some help from
                # the next measure. The previous measure has requested that this measure's
                # left barline style be set to 'startrpt'
                measure.leftBarline = m21.bar.Repeat(direction='start')

        self._allMeasuresPerStaff.append(self._oneMeasurePerStaff)

        # We've handled it and should set it to False
        self._nextLeftBarlineStartsRepeat = False

        if self._lines[startLineIdx].durationFromStart > 0:
            # not first measure, check for keysig, timesig changes
            # Q: what about clef changes?  Might happen in _fillContentsOfLayer,
            # Q: along with notes and rests?
            self._addKeyTimeChangesToSystemMeasures(startLineIdx, endLineIdx)


            # LATER: mensural support
#             if self._oclefs or self._omets or self._okeys:
#                 self._storeOriginalClefMensurationKeyApp()

        # TODO: sections (A, B) and repeat endings (1, 2)

        self._setSystemMeasureStyle(endLineIdx)

    '''
    //////////////////////////////
    //
    // HumdrumInput::setSystemMeasureStyle -- Set the style of the left and/or
    //    right barline for the measure.

        Sets the style of the right barline of this measure, and (maybe) tells
        the next measure what to do with it's left barline (usually nothing).
    '''
    def _setSystemMeasureStyle(self, endLineIdx: int):
        endToken = self._lines[endLineIdx][0]
        endBar = endToken.text


        if not endToken.isBarline: # no barline at all, put a hidden one in
            for measure in self._oneMeasurePerStaff:
                measure.rightBarline = m21.bar.Barline('none')
                measure.rightBarline.style.hideObjectOnPrint = True
            return

        if endBar.startswith('=='): # final barline (light-heavy)
            for measure in self._oneMeasurePerStaff:
                measure.rightBarline = m21.bar.Barline('final')
            return

        if ':|!|:' in endBar or \
            ':!!:' in endBar or \
            ':||:' in endBar or \
            ':!:' in endBar or \
            ':|:' in endBar: # repeat both directions
            for measure in self._oneMeasurePerStaff:
                measure.rightBarline = m21.bar.Repeat(direction='end')
            self._nextLeftBarlineStartsRepeat = True
            return

        if ':|' in endBar or \
            ':!' in endBar: # end repeat
            for measure in self._oneMeasurePerStaff:
                measure.rightBarline = m21.bar.Repeat(direction='end')
            return

        if '!:' in endBar or \
            '|:' in endBar: # start repeat
            self._nextLeftBarlineStartsRepeat = True
            return

        if '||' in endBar: # double light
            for measure in self._oneMeasurePerStaff:
                measure.rightBarline = m21.bar.Barline('light-light')
            return

        if '!!' in endBar: # double heavy
            for measure in self._oneMeasurePerStaff:
                measure.rightBarline = m21.bar.Barline('heavy-heavy')
            return

        if '!|' in endBar: # heavy light
            for measure in self._oneMeasurePerStaff:
                measure.rightBarline = m21.bar.Barline('heavy-light')
            return

        if '|!' in endBar: # light heavy
            for measure in self._oneMeasurePerStaff:
                measure.rightBarline = m21.bar.Barline('light-heavy')
            return

        if "'" in endBar: # partial (mid)
            for measure in self._oneMeasurePerStaff:
                measure.rightBarline = m21.bar.Barline('short')
            return

        if '`' in endBar: # partial (top)
            for measure in self._oneMeasurePerStaff:
                measure.rightBarline = m21.bar.Barline('tick')
            return

        if '-' in endBar: # hidden
            for measure in self._oneMeasurePerStaff:
                measure.rightBarline = m21.bar.Barline('none')
                measure.rightBarline.style.hideObjectOnPrint = True
            return

        for measure in self._oneMeasurePerStaff:
            measure.rightBarline = m21.bar.Barline('regular')
        return

    '''
    //////////////////////////////
    //
    // HumdrumInput::getMeasureNumber -- Return the current barline's measure
    //     number, or return -1 if no measure number.  Returns 0 if a
    //     pickup measure.
        If there is a suffix (e.g. 23b), returns a string instead of an int
    '''
    def _getMeasureNumber(self, startLineIdx: int) -> Union[int, str]:
        name: str = ''
        number: int = -1

        if self._lines[startLineIdx].isBarline:
            number = self._lines[startLineIdx].barlineNumber # returns -1 if no number present
            name = self._lines[startLineIdx].barlineName # returns '' if name is just a number with no suffix
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
            number = self._lines[barlineIdx].barlineNumber # returns -1 if no number present
            name = self._lines[barlineIdx].barlineName # returns '' if name is just a number with no suffix
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
        one Measure per staff/Part). We also do something Verovio does not: we
        handle signature changes mid-Measure, and insert them at the appropriate
        time offset.
    '''
    def _addKeyTimeChangesToSystemMeasures(self, startLineIdx: int, endLineIdx: int):
        # Keep track of any key and time signature changes for each staff (token).
        # The token's time offset within the Measure is token.durationFromBarline.
        keyToks:        [HumdrumToken] = [None] * self.staffCount
        keySigToks:     [HumdrumToken] = [None] * self.staffCount
        timeSigToks:    [HumdrumToken] = [None] * self.staffCount
        meterSigToks:   [HumdrumToken] = [None] * self.staffCount
#         iTransposeToks: [HumdrumToken] = [None] * self.staffCount

        empty:          bool = True
        hasKeySig:      bool = False
        hasTimeSig:     bool = False
#         hasITranspose:  bool = False

        for i in range(startLineIdx, endLineIdx + 1): # inclusive of end
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
#                 elif token.isInstrumentTranspose: # *ITr seems confused with *Tr in iohumdrum.cpp
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

        if hasTimeSig:
            for i, timeSigTok in enumerate(timeSigToks):
                if timeSigTok is None:
                    continue
                m21OffsetInMeasure: Fraction = \
                    M21Convert.m21Offset(timeSigTok.durationFromBarline)
                m21TimeSig = M21Convert.m21TimeSignature(timeSigTok, meterSigToks[i])
                self._oneMeasurePerStaff[i].insert(m21OffsetInMeasure, m21TimeSig)

        if hasKeySig:
            for i, keySigTok in enumerate(keySigToks):
                if keySigTok is None:
                    continue
                m21KeySig = M21Convert.m21KeySignature(keySigTok, keyToks[i])
                if m21KeySig:
                    m21OffsetInMeasure: Fraction = M21Convert.m21Offset(keySigTok.durationFromBarline)
                    self._oneMeasurePerStaff[i].insert(m21OffsetInMeasure, m21KeySig)

    '''
    //////////////////////////////
    //
    // HumdrumInput::storeStaffLayerTokensForMeasure -- Store lists of notation
    //   data by staff and layer.
    '''
    def _generateStaffLayerTokensForMeasure(self, startLineIdx: int, endLineIdx: int):
        self._layerTokens = []
        for i in range(0, self.staffCount):
            self._layerTokens.append([])

        lastTrack: int = -1
        staffIndex: int = -1
        layerIndex: int = 0

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
                continue # no layers to see here

            # check for the maximum size of each spine (check staff
            # for maximum layer count):
            lastTrack = -1
            for token in line.tokens():
                if not token.isStaffDataType:
                    continue

                if token.track != lastTrack:
                    lastTrack = token.track
                    layerIndex = 0
                    continue

                layerIndex += 1
                staffIndex = self._staffStartsIndexByTrack[token.track]
                if len(self._layerTokens[staffIndex]) < layerIndex + 1:
                    self._layerTokens[staffIndex].append([])

        # Now we can do the job:
        for i in range(startLineIdx, endLineIdx + 1):
            line = self._lines[i]

            if not line.hasSpines:
                continue

            lastTrack = -1
            for token in line.tokens():
                if token.track < 1:
                    continue

                staffIndex = self._staffStartsIndexByTrack[token.track]
                if staffIndex < 0:
                    continue

                if token.track != lastTrack:
                    layerIndex = 0
                # elif not token.isPrimaryStrophe:
                #     # Do not increment layer index for secondary strophes
                #     # Also ignore non-primary strophes for now.
                #     continue
                else:
                    layerIndex += 1

                lastTrack = token.track
                if token.isNullData:
                    # keeping null interpretations to search for clef
                    # in primary layer for secondary layer duplication.
                    if token.linkedParameterSetCount == 0:
                        continue

                if token.isLocalComment and token.isNull:
                    # don't store empty comments as well. (maybe ignore all
                    # comments anyway).
                    continue

                if len(self._layerTokens[staffIndex]) < layerIndex + 1:
                    self._layerTokens[staffIndex].append([])

# music21 doesn't do system-wide measures (they only have measure per part), so all
# of this limitation of what can be represented as a system-wide barline doesn't apply.
# That's apparently an MEI limitation?  If so, the MEI exporter can deal with it.
#                 if token.isBarline and not token.allSameBarlineStyle:
#                     if '-' in token.text:
#                         # do not store partial invisible barlines
#                         continue

                self._layerTokens[staffIndex][layerIndex].append(token)

                if layerIndex == 0 and token.isClef:
                    layerCount = self._getCurrentLayerCount(token)
                    # Duplicate clef in all layers (needed for cases when
                    # a secondary layer ends before the end of a measure.
                    for k in range(layerCount, len(self._layerTokens[staffIndex])):
                        self._layerTokens[staffIndex][k].append(token)

        #self._printMeasureTokens()

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
        ttrack: int = token.track

        currTok: HumdrumToken = token.nextFieldToken
        while currTok:
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
    def _printMeasureTokens(self):
        print('self._layerTokens:')
        for i, staff in enumerate(self._layerTokens):
            print('STAFF {}\t'.format(i + 1), end = '', flush=True)
            for j, layer in enumerate(staff):
                print('LAYER {}:\t'.format(j + 1), end = '', flush=True)
                for token in layer:
                    print(' ', token.text, end = '', flush=True)
                print('', flush=True)

    '''
    //////////////////////////////
    //
    // HumdrumInput::convertMeasureStaves -- fill in a measure with the
    //    individual staff elements for each part.

        We actually create and fill in a Measure per staff and append to each Part
        (that's how music21 likes it). --gregc
    '''
    def _convertMeasureStaves(self, startLineIdx: int, endLineIdx: int):
        layerCounts: [int] = self.staffLayerCounts

        # TODO: Figured Bass
#         if self._hasFiguredBassSpine:
#             self._addFiguredBassForMeasureStaves(startLineIdx, endLineIdx)

        # TODO: Metronome changes
#         self._handleMetronomeChange()

        for i, startTok in enumerate(self._staffStarts):
            self._convertMeasureStaff(startTok.track, startLineIdx, endLineIdx, layerCounts[i])

        # TODO: Harmony, fingering, string numbers
#         if self._hasHarmonySpine:
#             self._addHarmFloatsForMeasure() # this guy should use setSpineColorFromColorInterpToken(token)
#         if self._hasFingeringSpine:
#             self._addFingeringsForMeasure()
#         if self._hasStringSpine:
#             self._addStringNumbersForMeasure()

    '''
    //////////////////////////////
    //
    // HumdrumInput::convertMeasureStaff -- print a particular staff in a
    //     particular measure.

        Convert a particular Measure in a particular staff/Part.
    '''
    def _convertMeasureStaff(self, track: int, startLineIdx: int, endLineIdx: int, layerCount: int):
        for layerIndex in range(0, layerCount):
            self._convertStaffLayer(track, startLineIdx, endLineIdx, layerIndex)

        # Q: what about checkClefBufferForSameAs... sounds like it is (mostly?) undoing
        # Q: the extra clef copies we added in _generateStaffLayerTokensForMeasure()

    '''
    //////////////////////////////
    //
    // HumdrumInput::convertStaffLayer -- Prepare a layer element in the current
    //   staff and then fill it with data.
    '''
    def _convertStaffLayer(self, track: int, startLineIdx: int, endLineIdx: int, layerIndex: int):
        staffIndex: int = self._staffStartsIndexByTrack[track]
        if staffIndex < 0:
            # not a kern/mens spine
            return

        layerData: [HumdrumToken] = self._layerTokens[staffIndex][layerIndex]
        if not layerData: # empty layer?!
            return

        self._fillContentsOfLayer(track, startLineIdx, endLineIdx, layerIndex)

    '''
    //////////////////////////////
    //
    // HumdrumInput::printGroupInfo --
    '''
    @staticmethod
    def _printGroupInfo(tgs: [HumdrumBeamAndTuplet]):
        for tg in tgs:
            print(tg.token.text, end='\t')
            if tg.token.text and len(tg.token.text) < 8:
                print('', end='\t')
            print('BS:{}'.format(tg.beamStart), end='\t')
            print('BE:{}'.format(tg.beamEnd), end='\t')
            print('GS:{}'.format(tg.gbeamStart), end='\t')
            print('GE:{}'.format(tg.gbeamEnd), end='\t')
            print('TS:{}'.format(tg.tupletStart), end='\t')
            print('TE:{}'.format(tg.tupletEnd), end='\t')
            print('TG:{}'.format(tg.group), end='\t')
            print('TA/TN:{}/{}'.format(tg.numNotesActual, tg.numNotesNormal), end='\t')
            print('TF:{}'.format(tg.forceStartStop))

    '''
    //////////////////////////////
    //
    // HumdrumInput::fillContentsOfLayer -- Fill the layer with musical data.
    '''
    def _fillContentsOfLayer(self,
                             track: int,
                             startLineIndex: int,
                             endLineIndex: int,
                             layerIndex: int):
        staffIndex: int = self._staffStartsIndexByTrack[track]
        if staffIndex < 0:
            # not a kern/mens spine
            return

        layerData: [HumdrumToken] = self._layerTokens[staffIndex][layerIndex]
        if not layerData: # empty layer?!
            return

        #self._prepareInitialOttavas(layerData[0])

        measureStartTime: HumNum = self._lines[startLineIndex].durationFromStart
        measureEndTime: HumNum = self._lines[endLineIndex].durationFromStart \
                                    + self._lines[endLineIndex].duration
        measureDuration: HumNum = measureEndTime - measureStartTime

        if measureDuration == 0:
            return # empty layer, no need for it, not even for space (see comment below)

        # Note that using offsetInMeasure means we can bypass all Verovio's prespace stuff.
        # MEI (and maybe others) might need it, but that's for the various exporters to
        # deal with if necessary.  We have positioned this Voice correctly in the Measure.
        voice: m21.stream.Voice = m21.stream.Voice()
        voiceOffsetInMeasure: Fraction = M21Convert.m21Offset(layerData[0].durationFromBarline)
        if layerData[0].isBarline:
            voiceOffsetInMeasure = 0 # durationFromBarline returns duration of previous bar in this case
        self._oneMeasurePerStaff[staffIndex].insert(voiceOffsetInMeasure, voice)

        # Note: no special case for whole measure rests.
        # music21 can detect and deal with these without our help.

        # beams and tuplets
        tgs: [HumdrumBeamAndTuplet] = self._prepareBeamAndTupletGroups(layerData)
#        self._printGroupInfo(tgs) # for debug only

        groupState: BeamAndTupletGroupState = BeamAndTupletGroupState()

#        lastDataTok: HumdrumToken = None # ignore for now, it's for sameas clef analysis
        for tokenIdx, layerTok in enumerate(layerData):
#             if layerTok.isData:
#                 lastDataTok = layerTok

            if layerTok.isNullData:
                # print any global text directions attached to the null token
                # and then skip to next token.
                self._processDirections(voice, layerTok, staffIndex)
                continue

            if layerTok.isInterpretation:
                self._processInterpretationLayerToken(voice, layerTok, layerIndex, staffIndex)
                continue

            if layerTok.isBarline:
                # TODO: barline formatting (partially implemented)
#                self._processBarlineLayerToken(voice, layerTok, staffIndex)
                continue

            if not layerTok.isData:
                continue

            # layerTok.isData...

#             if layerTok.isMens:
#                 self._convertMensuralToken(...)
#                 continue

            # iohumdrum.cpp does tgs processing in a different order,
            # because it is generating MEI.  We are generating music21,
            # so instead of handleGroupStarts before processing the note,
            # and then handleGroupEnds after, we have to do all group
            # handling after processing the note, in _handleGroupState.

            if layerTok.getValueBool('auto', 'tremoloBeam'):
                if 'L' not in layerTok.text:
                    # ignore the ending note of a beamed group
                    # of tremolos (a previous note in the tremolo
                    # replaces display of this note).
                    groupState = self._handleGroupState(groupState, tgs, layerData, tokenIdx, staffIndex)
                    continue

            if layerTok.getValueBool('auto', 'suppress'):
                # This element is not supposed to be printed,
                # probably due to being in a tremolo.
                # But there are some things we have to do anyway...
                self._processSuppressedLayerToken(voice, layerTok, staffIndex)
                continue

            # conversion of **kern data to music21
            if layerTok.isChord:
                self._processChordLayerToken(voice, layerTok, staffIndex, layerIndex)
            elif layerTok.isRest:
                self._processRestLayerToken(voice, layerTok, staffIndex)
            elif layerTok.isNote:
                self._processNoteLayerToken(voice, layerTok, staffIndex, layerIndex)
            else:
                # this is probably a **recip value without note or rest information
                # so print it as a space (invisible rest).
                self._processOtherLayerToken(voice, layerTok, staffIndex)

            groupState = self._handleGroupState(groupState, tgs, layerData, tokenIdx, staffIndex)

        # end loop over layer tokens

        self._processBarlinesInLayerData(voice, track, layerIndex)

    '''
        _processInterpretationLayerToken
    '''
    def _processInterpretationLayerToken(self, voice: m21.stream.Voice,
                                         layerTok: HumdrumToken,
                                         layerIndex: int,
                                         staffIndex: int):
        ss: StaffStateVariables = self._staffStates[staffIndex]
        if ss.hasLyrics:
            self._checkForVerseLabels(voice, layerTok)
        # TODO: ottava marks
        # self._handleOttavaMark(voice, layerTok, staffIndex)
        # self._handleLigature(layerTok) # just for **mens
        # self._handleColoration(layerTok) # just for **mens
        self._handleTempoChange(voice, layerTok) # needs replacement implementation
        self._handlePedalMark(voice, layerTok)
        self._handleStaffStateVariables(layerTok, layerIndex, staffIndex)
        self._handleStaffDynamicsStateVariables(layerTok, staffIndex)
        self._handleCustos(voice, layerTok)
        self._handleRepInterp(voice, layerTok) # new
        self._handleColorInterp(layerTok) # new
        self._handleClefChange(voice, layerTok, staffIndex)
        self._handleTimeSigChange(voice, layerTok, staffIndex) # new

    '''
    //////////////////////////////
    //
    // HumdrumInput::checkForVerseLabels --
    '''
    def _checkForVerseLabels(self, voice: m21.stream.Voice, token: HumdrumToken):
        # TODO: verse labels
        pass

    def _handlePedalMark(self, voice: m21.stream.Voice, token: HumdrumToken):
        # TODO: pedal marks
        pass

    def _handleCustos(self, voice: m21.stream.Voice, token: HumdrumToken):
        # TODO: *custos
        pass

    def _handleRepInterp(self, voice: m21.stream.Voice, token: HumdrumToken):
        # TODO: *rep (repetition element)
        pass

    def _handleColorInterp(self, token: HumdrumToken):
        # TODO: *color (spine color)
        # if '*color:' not in token.text:
        #     return
        # self.setSpineColorFromColorInterpToken(token)
        pass

    def _handleClefChange(self, voice: m21.stream.Voice, token: HumdrumToken, staffIndex: int):
        forceClefChange: bool = False
        if token.isClef:
            if token.getValueBool('auto', 'clefChange'):
                forceClefChange = True

        if token.isMens:
            return # LATER: support **mens (handleClefChange)

        if forceClefChange or token.durationFromStart != 0:
            if token.isClef:
                clefOffsetInMeasure: Fraction = M21Convert.m21Offset(token.durationFromBarline)
                voiceOffsetInMeasure: Union[Fraction, float] = \
                    self._oneMeasurePerStaff[staffIndex].elementOffset(voice)
                clefOffsetInVoice: Union[Fraction, float] = clefOffsetInMeasure - voiceOffsetInMeasure
                m21Clef: m21.clef.Clef = M21Convert.m21Clef(token)
                voice.insert(clefOffsetInVoice, m21Clef)
            elif token.isNull:
                # Q: under certain circumstances, clefs are duplicated to secondary layers. Why?
                pass



    def _handleTimeSigChange(self, voice: m21.stream.Voice, token: HumdrumToken, staffIndex: int):
        if token.isTimeSignature:
            # Now done at the measure level.  This location might
            # be good for time signatures which change in the
            # middle of measures.
            self._processDirections(voice, token, staffIndex)

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
    def _handleStaffDynamicsStateVariables(self, token: HumdrumToken, staffIndex: int):
        ss: StaffStateVariables = self._staffStates[staffIndex]

        tok: HumdrumToken = token.nextFieldToken
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
                ss.dynamPos = 0         # centered between a staff and the staff below
                ss.dynamPosDefined = True # so we know that dynamPos=0 means something
                ss.dynamStaffAdj = 0    # centered between _this_ staff and the staff below
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
    //    *Xtremolo    = terminal *tremelo contraction
    //    *tremolo     = merge possible beam groups into tremolos
    //    *Xbeamtup    = suppress beam tuplet numbers
    //    *beamtup     = display beam tuplet numbers
    //    *Xbrackettup = suppress tuplet brackets
    //    *brackettup  = display tuplet brackets
    //    *Xcue        = notes back to regular size (operates at layer level rather than staff level).
    //    *cue         = display notes in cue size (operates at layer level rather than staff level).
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
    def _handleStaffStateVariables(self, token: HumdrumToken, layerIndex: int, staffIndex: int):
        ss: StaffStateVariables = self._staffStates[staffIndex]
        if token.text == '*Xbeamtup' or token.text == '*Xtuplet':
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

        if 'acclev' in token.text:
            self._storeAcclev(token.text, staffIndex)
            return

        if token.text == r'*2\left':
            ss.rightHalfStem = False
            return
        if token.text == r'*2\right':
            ss.rightHalfStem = True
            return

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
    def _handleTempoChange(self, voice: m21.stream.Voice, token: HumdrumToken):
        # tempo changes
        pass
#         if not token.isTempo:
#             return

#         if token.durationFromStart == 0:
#             # ignore starting tempo setting since it is handled
#             # by scoreDef.
#             return

#         tempoName: str = token.tempoName
#         tempoBPM: float = token.tempoBPM
        # Q: During tempo handling in iohumdrum.cpp, things like
        # Q: allegro [quarter] = 128 or allegro [quarter=128] are never
        # Q: actually parsed and turned into reality, just added to
        # Q: the MEI as text (with "quarter" turned nicely into a SMUFL
        # Q: quarter note symbol).  I want to do better, and generate
        # Q: a real m21.MetronomeMark for this.


    '''
        _handleGroupState adds beams and tuplets to a note/rest in the layer, as appropriate.

        In music21, every note/chord/rest has a Tuplet (in its Duration), that both describes
        the timing of that note, and the bracketing of the tuplet in the score.  In music21,
        every note/chord has a Beams object that contains 0 or more Beam objects (e.g. beamed
        16th notes have two Beam objects each).
    '''
    def _handleGroupState(self,
                          currState: BeamAndTupletGroupState,
                          tgs: [HumdrumBeamAndTuplet],
                          layerData: [HumdrumToken],
                          tokenIdx: int,
                          staffIndex: int) -> BeamAndTupletGroupState:
        ss: StaffStateVariables = self._staffStates[staffIndex]
        token: HumdrumToken = layerData[tokenIdx]
        tg: HumdrumBeamAndTuplet = tgs[tokenIdx]
        newState: BeamAndTupletGroupState = copy.copy(currState)

        if ss.tremolo:
            if 'L' in token.text:
                success: bool = self._checkForTremolo(layerData, tgs, tokenIdx, staffIndex)
                if success:
                    # beamed group converted into tremolo
                    return newState

        if tg.beamStart or tg.gbeamStart:
            direction: int = 0
            if self._signifiers.above:
                pattern: str = '[LJKk]+' + self._signifiers.above
                if re.search(pattern, token.text):
                    direction = 1
            if self._signifiers.below:
                pattern: str = '[LJKk]+' + self._signifiers.below
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
                                            tg.durationTupleNormal,
                                            tg.numScale)
            # start the tuplet
            self._startTuplet(layerData, tokenIdx, newState.m21Tuplet, staffIndex)
            newState.inTuplet = True
        elif newState.inTuplet and tg.tupletEnd:
            # end the tuplet
            self._endTuplet(layerData, tokenIdx, newState.m21Tuplet)
            newState.inTuplet = False
            newState.m21Tuplet = None
        elif newState.inTuplet:
            # continue the tuplet
            self._continueTuplet(layerData, tokenIdx, newState.m21Tuplet)

        # handle beam state
        if tg.beamStart:
            # start the beam
            self._startBeam(layerData, tokenIdx)
            newState.inBeam = True
            newState.previousBeamTokenIdx = tokenIdx
        elif newState.inBeam and tg.beamEnd:
            # end the beam
            self._endBeam(layerData, tokenIdx, newState.previousBeamTokenIdx)
            newState.inBeam = False
            newState.previousBeamTokenIdx = -1
        elif newState.inBeam and not layerData[tokenIdx].isRest:
            # continue the beam (but not if it's a rest, they can be within
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
    def _makeTuplet(numberNotesActual: int,
                    numberNotesNormal: int,
                    durationNormal: m21.duration.DurationTuple,
                    numScale: int = None) -> m21.duration.Tuplet:

        numActual: int = numberNotesActual
        numNormal: int = numberNotesNormal
        durNormal: m21.duration.DurationTuple = durationNormal
        if numScale is not None:
            # multiply numActual and numNormal by numScale
            # dived durNormal by numScale
            numActual *= numScale
            numNormal *= numScale
            durNormal = m21.duration.durationTupleFromQuarterLength(durNormal.quarterLength / Fraction(numScale))

        tuplet: m21.duration.Tuplet = m21.duration.Tuplet(
                                        numberNotesActual=numActual,
                                        numberNotesNormal=numNormal,
                                        durationNormal=durNormal,
                                        durationActual=durNormal)
        # apply our own defaults

        # m21 default tuplet placement is 'above', but it should be None.  The only client I
        # can see is m21ToXML.py, which handles placement == None by not specifying placement
        # in the output XML.  That is exactly what we want as default behavior, so we will
        # always set tuplet.placement to None as a default.
        tuplet.placement = None # our better default

        # I have the same issue with music21's default tuplet bracket, which is True.
        # I want to default to unspecified, which is None.  Unfortunately, m21ToXML.py
        # doesn't check for tuplet.bracket == None, like it does for tuplet.placement,
        # so I'll need to update that at some point.  For now, m21ToXML.py will treat
        # None as False, which seems wrong, but not fatally so. --gregc
        tuplet.bracket = None

        # print('_makeTuplet: tuplet =', tuplet)
        return tuplet

    '''
        _getNumBeamsForNoteOrChord --
    '''
    @staticmethod
    def _getNumBeamsForNoteOrChord(token: HumdrumToken, noteOrChord: m21.Music21Object) -> int:
        if noteOrChord is None:
            return 0

        if 'Note' not in noteOrChord.classes and 'Chord' not in noteOrChord.classes:
            return 0

        noteDurationNoDots: HumNum = token.durationNoDots # unless we're in a tuplet

        if len(noteOrChord.duration.tuplets) > 1:
            # LATER: support nested tuplets (music21 needs to support this first)
            return 0

        if len(noteOrChord.duration.tuplets) == 1:
            # actual notes vs normal notes:  In an eighth-note triplet, actual notes is 3,
            # normal notes is 2.  i.e. 3 actual notes are played in the duration of 2 normal notes
            numberActualNotesInTuplet: int = noteOrChord.duration.tuplets[0].numberNotesActual
            numberNormalNotesInTuplet: int = noteOrChord.duration.tuplets[0].numberNotesNormal
            noteDurationNoDots *= HumNum(numberActualNotesInTuplet, numberNormalNotesInTuplet)

        # normalize the fraction
        dur = HumNum(noteDurationNoDots.numerator, noteDurationNoDots.denominator)
        if dur not in durationNoDotsToNumBeams:
            return 0
        return durationNoDotsToNumBeams[dur]

    def _startBeam(self, layerData: [HumdrumToken], startTokenIdx: int):
        token: HumdrumToken = layerData[startTokenIdx]
        obj: m21.note.GeneralNote = token.getValueM21Object('music21', 'generalNote')

        # We append explicitly (instead of with a single call to beams.fill(numBeams))
        # because we may need more than 6 (dur == 1/256), and 6 is beams.fill's hard-
        # coded limit.
        numBeams: int = self._getNumBeamsForNoteOrChord(token, obj)
        for _ in range(0, numBeams):
            obj.beams.append('start')

    def _continueBeam(self, layerData: [HumdrumToken], tokenIdx: int, prevBeamTokenIdx: int, beamType: str = 'continue'):
        token: HumdrumToken = layerData[tokenIdx]
        obj: m21.note.GeneralNote = token.getValueM21Object('music21', 'generalNote')

        if obj is None or 'Rest' in obj.classes:
            return

        prevToken: HumdrumToken = layerData[prevBeamTokenIdx]
        prevObj: m21.note.GeneralNote = prevToken.getValueM21Object('music21',
                                                                 'generalNote')

        numBeams: int = self._getNumBeamsForNoteOrChord(token, obj)
        prevNumBeams: int = self._getNumBeamsForNoteOrChord(prevToken, prevObj)

        if 0 < numBeams < prevNumBeams:
            # we're not dealing with secondary breaks here (that happens below), just
            # beam counts that are derived from the note durations.  So this means the
            # previous note needs to be modified to have his extra beams turn into
            # 'partial-right' beams.
            for beamNum in range(numBeams+1, prevNumBeams+1): # beam numbers are 1-based
                prevObj.beams.setByNumber(beamNum, 'partial', direction='right')

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
                for i in range(breakBeamCount+1, numBeams+1): # beam numbers are 1-based
                    prevObj.beams.setByNumber(i, 'stop')
                    obj.beams.setByNumber(i, 'start')

    def _endBeam(self, layerData: [HumdrumToken], tokenIdx: int, prevBeamTokenIdx: int):
        # the implementation here is exactly the same as _continueBeam, so just call him.
        self._continueBeam(layerData, tokenIdx, prevBeamTokenIdx, beamType='stop')

    def _startGBeam(self, layerData: [HumdrumToken], startTokenIdx: int):
        self._startBeam(layerData, startTokenIdx)

    def _continueGBeam(self, layerData: [HumdrumToken], tokenIdx: int, prevGBeamTokenIdx: int):
        self._continueBeam(layerData, tokenIdx, prevGBeamTokenIdx)

    def _endGBeam(self, layerData: [HumdrumToken], tokenIdx: int, prevGBeamTokenIdx: int):
        self._endBeam(layerData, tokenIdx, prevGBeamTokenIdx)

    def _startTuplet(self, layerData: [HumdrumToken], startTokenIdx: int, tupletTemplate: m21.duration.Tuplet, staffIndex: int):
        ss: StaffStateVariables = self._staffStates[staffIndex]
        startTok: HumdrumToken = layerData[startTokenIdx]
        startNote: m21.note.GeneralNote = startTok.getValueM21Object('music21', 'generalNote')
        if not startNote:
            raise HumdrumInternalError('no note/chord/rest at start of tuplet')

        # remember the original duration value, so we can do a debug check at the end
        # to make sure it didn't change (things like changing actual number from 6 to 3
        # are tricky, so we need to check our work).
        originalQuarterLength: HumNum = HumNum(startNote.duration.quarterLength)
        duration: m21.duration.Duration = copy.deepcopy(startNote.duration)
        tuplet: m21.duration.Tuplet = copy.deepcopy(tupletTemplate)

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
        if duration.tuplets in (None, ()):
            recomputeDuration = True
        elif len(duration.tuplets) > 1:
            recomputeDuration = True
        elif duration.tuplets[0].durationNormal != tuplet.durationNormal:
            recomputeDuration = True
        elif duration.tuplets[0].tupletMultiplier() != tuplet.tupletMultiplier():
            recomputeDuration = True

        if recomputeDuration:
            duration = M21Convert.m21DurationWithTuplet(startTok, tuplet)

        # Now figure out the rest of the tuplet fields (type, placement, bracket, etc)

        tuplet.type = 'start' # has to be set, or no-one cares about the placement, bracket, etc

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
        newQuarterLength: HumNum = HumNum(startNote.duration.quarterLength)
        if newQuarterLength != originalQuarterLength:
            raise HumdrumInternalError('_startTuplet modified duration.quarterLength')

    @staticmethod
    def _continueTuplet(layerData: [HumdrumToken], tokenIdx: int, tupletTemplate: m21.duration.Tuplet):
        token: HumdrumToken = layerData[tokenIdx]
        note: m21.note.GeneralNote = token.getValueM21Object('music21', 'generalNote')
        if not note:
            # This could be a *something interp token; just skip it.
            return
        if token.isGrace: # grace note in the middle of a tuplet, but it's not _in_ the tuplet
            return

        # remember the original duration value, so we can do a debug check at the end
        # to make sure it didn't change (things like changing actual number from 6 to 3
        # are tricky, so we need to check our work).
        originalQuarterLength: HumNum = HumNum(note.duration.quarterLength)

        duration: m21.duration.Duration = copy.deepcopy(note.duration)
        tuplet: m21.duration.Tuplet = copy.deepcopy(tupletTemplate)

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
        if duration.tuplets in (None, ()):
            recomputeDuration = True
        elif len(duration.tuplets) > 1:
            recomputeDuration = True
        elif duration.tuplets[0].durationNormal != tuplet.durationNormal:
            recomputeDuration = True
        elif duration.tuplets[0].tupletMultiplier() != tuplet.tupletMultiplier():
            recomputeDuration = True

        if recomputeDuration:
            duration = M21Convert.m21DurationWithTuplet(token, tuplet)

        # set the tuplet on the note duration.
        # If we recomputed the duration above, this has already been done
        if not recomputeDuration:
            duration.tuplets = (tuplet,)

        # And set this new duration on the note.
        note.duration = duration

        newQuarterLength: HumNum = HumNum(note.duration.quarterLength)
        if newQuarterLength != originalQuarterLength:
            raise HumdrumInternalError('_continueTuplet modified duration.quarterLength')

    @staticmethod
    def _endTuplet(layerData: [HumdrumToken], tokenIdx: int, tupletTemplate: m21.duration.Tuplet):
        endToken: HumdrumToken = layerData[tokenIdx]
        endNote: m21.note.GeneralNote = endToken.getValueM21Object('music21', 'generalNote')
        if not endNote:
            raise HumdrumInternalError('no note/chord/rest at end of tuplet')

        # remember the original duration value, so we can do a debug check at the end
        # to make sure it didn't change (things like changing actual number from 6 to 3
        # are tricky, so we need to check our work).
        originalQuarterLength: HumNum = HumNum(endNote.duration.quarterLength)

        duration: m21.duration.Duration = copy.deepcopy(endNote.duration)
        tuplet: m21.duration.Tuplet = copy.deepcopy(tupletTemplate)

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
        if duration.tuplets in (None, ()):
            recomputeDuration = True
        elif len(duration.tuplets) > 1:
            recomputeDuration = True
        elif duration.tuplets[0].durationNormal != tuplet.durationNormal:
            recomputeDuration = True
        elif duration.tuplets[0].tupletMultiplier() != tuplet.tupletMultiplier():
            recomputeDuration = True

        if recomputeDuration:
            duration = M21Convert.m21DurationWithTuplet(endToken, tuplet)

        tuplet.type = 'stop'

        # Now set the tuplet in the duration to this one
        duration.tuplets = (tuplet,)

        # And set this new duration on the endNote.
        endNote.duration = duration

        newQuarterLength: HumNum = HumNum(endNote.duration.quarterLength)
        if newQuarterLength != originalQuarterLength:
            raise HumdrumInternalError('_endTuplet modified duration.quarterLength')

    '''
    //////////////////////////////
    //
    // HumdrumInput::setBeamDirection -- Set a beam up or down.
    '''
    @staticmethod
    def _setBeamDirection(direction: int, tgs: [HumdrumBeamAndTuplet], layerData: [HumdrumToken], tokenIdx: int, isGrace: bool):
        upOrDown: str = None
        if direction == 1:
            upOrDown = 'up'
        elif direction == -1:
            upOrDown = 'down'

        tg: HumdrumBeamAndTuplet = tgs[tokenIdx]
        beamStart: int = tg.beamStart
        if isGrace:
            beamStart = tg.gbeamStart

        for i in range(tokenIdx, len(layerData)):
            beamEnd: int = tgs[i].beamEnd
            if isGrace:
                beamEnd = tgs[i].gbeamEnd

            token: HumdrumToken = layerData[i]
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
            # (too late to set stem.dir, the note/chord has already been created)
            # token.setValue('auto', 'stem.dir', str(direction))
            obj: m21.note.GeneralNote = token.getValueM21Object('music21', 'generalNote')
            if not obj:
                continue # no durational object

            if 'Chord' not in obj.classes and 'Note' not in obj.classes:
                continue # it's not a note/chord, no stem direction needed

            if upOrDown:
                if 'Chord' in obj.classes:
                    obj.stemDirection = upOrDown
#                     Hmmm... seems like setting stemDirection up or down on each
#                     note might be a good idea, but iohumdrum.cpp doesn't do that. --gregc
                    # clear the stemDirection of all the notes in the chord, at least.
                    for note in obj.notes:
                        note.stemDirection = None # means 'unspecified'
                elif 'Note' in obj.classes:
                    obj.stemDirection = upOrDown

            if beamEnd == beamStart:
                # last note of beam so exit
                break

    '''
    //////////////////////////////
    //
    // HumdrumInput::storeBreaksec -- Look for cases where sub-beams are broken.
    '''
    @staticmethod
    def _storeSecondaryBreakBeamCount(beamState: [int], beamNums: [int], layerData: [HumdrumToken], isGrace: bool = False):
        # a list of "beams", each of which is actually a list of the note indices in that beam
        beamedNotes: [[int]] = []

        # the beam number of the "beam" list we are currently filling in
        bnum: int = 0

        for i, layerTok in enumerate(layerData):
            if beamNums[i] == 0:
                # not in a beam
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
    def _analyzeLayerBeams(self, beamNums: [int], gbeamNums: [int], layerData: [HumdrumToken]):
        beamState: [int] = [0] * len(layerData)
        gbeamState: [int] = [0] * len(layerData) # for grace notes
        didBeamStateGoNegative: bool = False
        didGBeamStateGoNegative: bool = False
        lastBeamState: int = 0
        lastGBeamState: int = 0

        for i, layerTok in enumerate(layerData):
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
                didGBeamStateGoNegative = True # BUGFIX: didBeam -> didGBeam

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
            beamState = [0] * len(beamState) # local, so we can replace
            for i in range(0, len(beamNums)): # non-local, we must modify in place
                beamNums[i] = 0

        if didGBeamStateGoNegative or gbeamState[-1] != 0:
            # something wrong with the gracenote beaming, either incorrect or
            # the beaming crosses a barline or layer.  Don't try to
            # beam anything.
            gbeamState = [0] * len(gbeamState) # local, so we can replace
            for i in range(0, len(gbeamNums)): # non-local, we must modify in place
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
    def _prepareBeamAndTupletGroups(self, layerData: [HumdrumToken]) -> [HumdrumBeamAndTuplet]:
        beamNums: [int] = []
        gbeamNums: [int] = []
        self._analyzeLayerBeams(beamNums, gbeamNums, layerData)

        tgs: [HumdrumBeamAndTuplet] = []

        # duritems == a list of items in the layer which have duration.
        # Grace notes, barlines, interpretations, local comments, global comments,
        # etc. are filtered out for the analysis.
        durItems: [HumdrumToken] = []

        # indexmapping == maping from a duritem index to a layerdata index.
        indexMapping: [int] = []

        # indexmapping2 == mapping from a layerdata index to a duritem index,
        # with -1 meaning no mapping.
        indexMapping2: [int] = []

        # durbeamnum == beam numbers for durational items only.
        durBeamNums: [int] = []

        # Extract a list of the layer items that have duration:
        for i, layerTok in enumerate(layerData):
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
        powerOfTwoWithoutDots: [bool] = [None] * len(durItems)
        hasTuplet: bool = False
        dotlessDur: [HumNum] = [None] * len(durItems)

        # durationwithdots == full duration of the note/rest including augmentation dots.
        durationWithDots: [HumNum] = [None] * len(durItems)

        # dursum = a cumulative sum of the full durs, starting at 0 for
        # the first index.
        durSum: [HumNum] = [None] * len(durItems)

        sumSoFar: HumNum = HumNum(0)
        for i, durItem in enumerate(durItems):
            durNoDots: HumNum = durItem.scaledDurationNoDots(durItem.rscale)
            dotlessDur[i] = durNoDots / 4
            powerOfTwoWithoutDots[i] = Convert.isPowerOfTwo(durNoDots)
            hasTuplet = hasTuplet or not powerOfTwoWithoutDots[i]
            durationWithDots[i] = durItem.scaledDuration(durItem.rscale)
            durSum[i] = sumSoFar
            sumSoFar += durationWithDots[i]

        # Count the number of beams.  The durbeamnum std::vector contains a list
        # of beam numbers starting from 1 (or 0 if a note/rest has no beam).
        beamCount: int = 0
        for durBeamNum in durBeamNums:
            if durBeamNum > beamCount:
                beamCount = durBeamNum

        # beamstarts and beamends are lists of the starting and ending
        # index for beams of duration items in the layer.  The index is
        # into the durlist std::vector (list of items which posses duration).
        beamStarts: [int] = [-1] * beamCount
        beamEnds: [int] = [0] * beamCount
        for i, durBeamNum in enumerate(durBeamNums):
            if durBeamNum > 0:
                if beamStarts[durBeamNum - 1] < 0:
                    beamStarts[durBeamNum - 1] = i
                beamEnds[durBeamNum - 1] = i

        # beamstartboolean == starting of a beam on a particular note
        # beamendboolean == ending of a beam on a particular note
        beamStartBoolean: [int] = [0] * len(durBeamNums)
        beamEndBoolean: [int] = [0] * len(durBeamNums)
        for i in range(0, len(beamStarts)):
            beamStartBoolean[beamStarts[i]] = i + 1
            beamEndBoolean[beamEnds[i]] = i + 1

        # Calculate grace note beam starts and ends.
        # Presuming no clef changes, etc. found between notes in
        # a gracenote beam.  Generalize further if so.
        # gbeamstart == boolean for starting of a grace note beam
        # gbeamend == boolean ending of a grace note beam
        gbeamStarts: [int] = [0] * len(layerData)
        gbeamEnds: [int] = [0] * len(layerData)
        gState: [int] = [0] * len(layerData)

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
                tgs.append(HumdrumBeamAndTuplet())
                tgs[-1].token = layerData[i]
                tgs[-1].gbeamStart = gbeamStarts[i]
                tgs[-1].gbeamEnd = gbeamEnds[i]
                if indexMapping2[i] < 0:
                    continue
                tgs[-1].beamStart = beamStartBoolean[indexMapping2[i]]
                tgs[-1].beamEnd = beamEndBoolean[indexMapping2[i]]
            return tgs

        # hasTuplet == True

        # beamdur = a list of the durations for each beam
        beamDurs: [HumNum] = [None] * len(beamStarts)
        for i in range(0, len(beamDurs)):
            beamDurs[i] = (durSum[beamEnds[i]] - durSum[beamStarts[i]]) \
                            + durationWithDots[beamEnds[i]]

        # beampowdot == the number of augmentation dots on a power of two for
        # the duration of the beam.  -1 means could not be made power of two with
        # dots.
        beamPowDots: [int] = [-1] * len(beamStarts)
        for i, beamDur in enumerate(beamDurs):
            beamPowDots[i] = self._getNumDotsForPowerOfTwo(beamDur)

        binaryBeams: [bool] = [False] * len(beamStarts)
        for i, beamStart in enumerate(beamStarts):
            if powerOfTwoWithoutDots[beamStart]:
                binaryBeams[i] = True

        # Assume that tuplet beams that can fit into a power of two will form
        # a tuplet group.  Perhaps bias towards beampowdot being 0, and try to
        # beam groups to include non-beamed tuplets into lower powdots.
        # Should check that the factors of notes in the beam group all match...
        tupletGroups: [int] = [0] * len(durItems)

        # durforce: boolean for if a tuplet has been forced to be started or
        # stopped on the current note.
        durForce: [bool] = [False] * len(durItems)

        # tupletDurs: actual duration of tuplet that starts on this note
        tupletDurs: [HumNum] = [None] * len(durItems)

        # actual DurationTuple of the tuplet (type='eighth', dots=0, qL=0.5)
        durationTupleNormal: [m21.duration.DurationTuple] = [None] * len(durItems)

        tupletNum: int = 1
        skipToI: int = -1
        for i in range(0, len(durItems)):
            if i < skipToI:
                continue

            if powerOfTwoWithoutDots[i]:
                # not a tuplet
                continue

            # At a tuplet start.
            starting = i

            # Search for the end.
            ending: int = len(durItems) - 1
            groupDur: HumNum = HumNum(0)

            forcedTupletDuration: HumNum = None
            rparam: str = durItems[starting].layoutParameter('TUP', 'r')
            if rparam:
                forcedTupletDuration = Convert.recipToDuration(rparam)

            if forcedTupletDuration is None:
                # Recommendation: if you use LO:TUP:num, also specify LO:TUP:r, to be explicit.
                endIndex: int = self._findTupletEndByBeamWithDottedPow2Duration(
                                        starting, beamStarts, beamEnds,
                                        beamPowDots, powerOfTwoWithoutDots)
                if endIndex:
                    ending = endIndex

                    # create a new tuplet group
                    groupDur = HumNum(0)
                    for j in range(starting, ending+1): # starting through ending
                        tupletGroups[j] = tupletNum
                        groupDur += durationWithDots[j]
                    tupletDurs[starting] = groupDur
                    tupletNum += 1
                    skipToI = ending + 1
                    continue

            groupDur = durationWithDots[starting]
            for j in range(starting + 1, len(durItems)):
                if powerOfTwoWithoutDots[j]: # if note j is not a tuplet note, we have to stop at j-1
                    ending = j - 1
                    break

                if self._checkForTupletForcedBreak(durItems, j):
                    # force a tuplet break
                    ending = j - 1
                    durForce[starting] = True
                    durForce[ending] = True
                    break

                # The rest of these are based on group duration so far.
                groupDur += durationWithDots[j]

                if forcedTupletDuration is not None and groupDur >= forcedTupletDuration:
                    ending = j
                    durForce[starting] = True
                    durForce[ending] = True
                    break

                if forcedTupletDuration is None:
                    if Convert.isPowerOfTwo(groupDur):
                        ending = j
                        break

            # create a new tuplet group
            for j in range(starting, ending+1): # starting through ending
                tupletGroups[j] = tupletNum
            tupletDurs[starting] = groupDur
            tupletNum += 1
            skipToI = ending + 1

        # tupletstartboolean == starting of a tuplet group
        # tupletendboolean == ending of a tuplet group
        tupletStartBoolean: [int] = [0] * len(tupletGroups)
        tupletEndBoolean: [int] = [0] * len(tupletGroups)
        tstart: [bool] = [False] * len(tupletGroups)
        tend: [bool] = [False] * len(tupletGroups)

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
        numNotesActual: [int] = [-1] * len(tupletGroups)
        numNotesNormal: [int] = [-1] * len(tupletGroups)
        tupletMultiplier: [HumNum] = [HumNum(1)] * len(tupletGroups)
        for i, tupletGroup in enumerate(tupletGroups):
            if tupletGroup == 0:
                continue

            nextPowOfTwo: HumNum = None
            if dotlessDur[i] < 1:
                nextPowOfTwo = self._nextHigherPowerOfTwo(dotlessDur[i])
            else:
                quotient: float = float(numNotesActual[i]) / float(numNotesNormal[i])
                iQuotient: int = int(quotient)
                nextPowOfTwo = HumNum(self._nextLowerPowerOfTwo(iQuotient))

            if dotlessDur[i].numerator == 3:
                # correction for duplets
                nextPowOfTwo /= HumNum(2)

            tupletMultiplier[i] = dotlessDur[i] / nextPowOfTwo
            numNotesActual[i] = tupletMultiplier[i].denominator
            numNotesNormal[i] = tupletMultiplier[i].numerator

            # Reference tuplet breve to breve rather than whole.
            if dotlessDur[i].numerator == 4 and dotlessDur[i].denominator == 3:
                numNotesNormal[i] = 2
                tupletMultiplier[i] = HumNum(2, tupletMultiplier[i].denominator)

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

            if numNotesActual[i] != numNotesActual[i - 1] or numNotesNormal[i] != numNotesNormal[i - 1]:
                if tupletGroups[i] == tupletGroups[i - 1]:
                    correction += 1
                    tupletStartBoolean[i] = tupletGroups[i] + correction
                    tupletEndBoolean[i - 1] = tupletGroups[i]
            tupletGroups[i] += correction

        # Change those -1s to 1s, I'm guessing. --gregc
        for i in range(0, len(numNotesActual)):
            if numNotesActual[i] < 0:
                numNotesActual[i] = -numNotesActual[i]

        for i in range(0, len(durItems)):
            if tupletDurs[i] is None:
                durationTupleNormal[i] = None
                continue
            durationTupleNormal[i] = m21.duration.durationTupleFromQuarterLength(
                                        tupletDurs[i] / HumNum(numNotesNormal[i]))
            if durationTupleNormal[i].type == 'inexpressible':
                # It must be a partial tuplet: tupletDurs[i] is only part of the full tuplet duration.
                # This seems like a mal-notation to me: see Palestrina/Benedictus_66_b_002.krn measure
                # 56 (tenor part), for an example.  The piece is in 4/2, and there are half-note
                # triplets (tuplet duration is a whole note) everywhere.  In this measure (tenor part)
                # we see two triplet half notes followed by a whole note, followed by one triplet
                # half note.  To fix the mal-notation, I would have replaced the whole note with
                # three triplet half notes, all tied together.  Then the first of those would be the
                # third note of the first triplet, and the last two of those would be the first two
                # notes of the second triplet.  Alternatively, this piece really seems to be better
                # notated as one triplet of whole notes per measure (duration of triplet == breve).
                # I would note that verovio renders this measure weirdly, by putting a triplet
                # bracket around the first two notes, and another "around" the last note. But we need
                # to work around it, since the partial duration causes an inexpressible durationNormal
                # and music21 really hates that. The workaround below seems OK, but the end result
                # from export to MusicXML (or perhaps from the render by Musescore) adds rests to
                # the tuplets to get them to be full duration. And that's even more wrong than what
                # verovio does, since it makes the measure too long.
                # Workaround:
                # Let's see if the partial duration is 1/N or 2/N or 3/N... of a reasonable tuplet
                # duration, where N is numNotesActual.  For example, for a triplet (numNotesActual
                # is 3), see if the partial duration is 1/3 or 2/3 of a reasonable tuplet duration.
                # A reasonable tuplet duration is (first) a power-of-two duration, and (next) a
                # dotted power-of-two duration.
                haveGoodDurationNormal: bool = False

                # try (first) for power of two full tuplet duration
                for numNotes in reversed(range(1, numNotesActual[i])):
                    proposedTupletDur: HumNum = tupletDurs[i] / HumNum(numNotes, numNotesActual[i])
                    if Convert.isPowerOfTwo(proposedTupletDur):
                        durationTupleNormal[i] = m21.duration.durationTupleFromQuarterLength(
                                                    proposedTupletDur)
                        haveGoodDurationNormal = True
                        break

                if haveGoodDurationNormal:
                    continue

                # try (next) for single-dotted power of two full tuplet duration
                for numNotes in reversed(range(1, numNotesActual[i])):
                    proposedTupletDur: HumNum = tupletDurs[i] / HumNum(numNotes, numNotesActual[i])
                    tupletDurWithoutSingleDot: HumNum = proposedTupletDur * HumNum(2, 3)
                    if Convert.isPowerOfTwo(tupletDurWithoutSingleDot):
                        durationTupleNormal[i] = m21.duration.durationTupleFromQuarterLength(
                                                    proposedTupletDur)
                        haveGoodDurationNormal = True
                        break

                if not haveGoodDurationNormal:
                    print('Cannot figure out a reasonable tuplet duration')

        tgs = []
        for i, layerTok in enumerate(layerData):
            tgs.append(HumdrumBeamAndTuplet())
            tgs[-1].token = layerTok
            if indexMapping2[i] < 0:
                # this is a non-durational layer item or a non-tuplet note
                tgs[-1].duration = HumNum(0)
                tgs[-1].durationNoDots = HumNum(0)
                tgs[-1].beamStart = 0
                tgs[-1].beamEnd = 0
                tgs[-1].gbeamStart = gbeamStarts[i]
                tgs[-1].gbeamend = gbeamEnds[i]
                tgs[-1].tupletStart = 0
                tgs[-1].tupletEnd = 0
                tgs[-1].group = -1
                tgs[-1].numNotesActual = -1
                tgs[-1].numNotesNormal = -1
                tgs[-1].tupletMultiplier = HumNum(1)
                tgs[-1].durationTupleNormal = None
                tgs[-1].forceStartStop = False
            else:
                # this is a tuplet note (with duration)
                tgs[-1].duration = layerTok.duration
                tgs[-1].durationNoDots = layerTok.durationNoDots
                tgs[-1].beamStart = beamStartBoolean[indexMapping2[i]]
                tgs[-1].beamEnd = beamEndBoolean[indexMapping2[i]]
                tgs[-1].gbeamStart = gbeamStarts[i]
                tgs[-1].gbeamend = gbeamEnds[i]
                tgs[-1].tupletStart = tupletStartBoolean[indexMapping2[i]]
                tgs[-1].tupletEnd = tupletEndBoolean[indexMapping2[i]]
                tgs[-1].group = tupletGroups[indexMapping2[i]]
                tgs[-1].numNotesActual = numNotesActual[indexMapping2[i]]
                tgs[-1].numNotesNormal = numNotesNormal[indexMapping2[i]]
                tgs[-1].tupletMultiplier = tupletMultiplier[indexMapping2[i]]
                tgs[-1].durationTupleNormal = durationTupleNormal[indexMapping2[i]]
                tgs[-1].forceStartStop = durForce[indexMapping2[i]]

        # Renumber tuplet groups in sequence (otherwise the mergeTupletsCuttingBeam()
        # function will delete the 1st group if it is not the first tuplet.
        tcounter: int = 0
        for tg in tgs:
            if tg.tupletStart:
                tcounter += 1
                tg.tupletStart = tcounter
            elif tg.tupletEnd:
                tg.tupletEnd = tcounter

        self._mergeTupletsCuttingBeam(tgs)
#        self._resolveTupletBeamTie(tgs) # this is MEI-specific; music21 doesn't care
        self._assignTupletScalings(tgs)

        # in iohumdrum.cpp this is called after return from prepareBeamAndTupletGroups()
        self._fixLargeTuplets(tgs)

        return tgs

    '''
    //////////////////////////////
    //
    // HumdrumInput::fixLargeTuplets -- fix triple-breve/triplet-wholenote cases.
    '''
    @staticmethod
    def _fixLargeTuplets(tgs: [HumdrumBeamAndTuplet]):
        # triplet-whole + triplet-breve cases
        for i in range(1, len(tgs)):
            if not (tgs[i].tupletStart == 2 and tgs[i].tupletEnd == 1):
                continue
            if tgs[i-1].tupletStart == 1 and tgs[i-1].tupletEnd == 1:
                print('two triplet-halfs + triplet-breve case')

        # two triplet-halfs + triplet-breve case
        for i in range(2, len(tgs)):
            if not (tgs[i].tupletStart == 2 and tgs[i].tupletEnd == 1):
                continue
            if not (tgs[i-1].tupletStart == 0 and tgs[i-1].tupletEnd == 1):
                continue
            if tgs[i-2].tupletStart == 1 and tgs[i-1].tupletEnd == 0:
                print('two triplet-halfs + triplet-breve case')

        # two triplet-halfs + triplet-breve case + two triplet-halfs
        for i in range(2, len(tgs)):
            if not (tgs[i].tupletStart == 0 and tgs[i].tupletEnd == 2):
                continue
            if not (tgs[i-1].tupletStart == 2 and tgs[i-1] == 0):
                continue
            if tgs[i-2].tupletStart == 1 and tgs[i-2].tupletEnd == 1:
                print('two triplet-halfs + triplet-breve case + two triplet-halfs')

    '''
    //////////////////////////////
    //
    // HumdrumInput::assignTupletScalings --
    '''
    def _assignTupletScalings(self, tgs: [HumdrumBeamAndTuplet]):
        maxGroup: int = 0
        for tg in tgs:
            if maxGroup < tg.group:
                maxGroup = tg.group

        if maxGroup <= 0:
            # no tuplets
            return

        # tggroups contains lists of tuplet-y items (i.e. with group > 0), by group number
        tggroups: [[HumdrumBeamAndTuplet]] = []
        for _ in range(0, maxGroup+1):
            tggroups.append([])

        for tg in tgs:
            group: int = tg.group
            if group <= 0:
                continue
            tggroups[group].append(tg)

        for tggroup in tggroups:
            self._assignScalingToTupletGroup(tggroup) # tggroups[0] is empty, but that's OK

    '''
    //////////////////////////////
    //
    // HumdrumInput::assignScalingToTupletGroup --
    '''
    @staticmethod
    def _assignScalingToTupletGroup(tggroup: [HumdrumBeamAndTuplet]):
        if not tggroup: # tggroup is None or [], so bail out
            return

        # Set the Humdrum-specified numNotesActual for the tuplet (if it makes sense).
        num: str = tggroup[0].token.layoutParameter('TUP', 'num')
        if num:
            numValue: int = int(num)
            if numValue > 0:
                scale: HumNum = HumNum(num) / tggroup[0].numNotesActual
                if scale.denominator == 1 and scale >= 1:
                    for tg in tggroup:
                        tg.numScale = scale.numerator
                    return

        # There was no Humdrum-specified numNotesActual, or it didn't make sense.
        # Initialize all scalings to 1
        for tg in tggroup:
            tg.numScale = 1

        durCounts: dict = dict() # key: HumNum, value: int
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
            count: int = list(durCounts.values())[0] # how many of that duration are present
            scale: HumNum = HumNum(count) / tggroup[0].numNotesActual
            if scale.denominator == 1 and scale > 1:
                for tg in tggroup:
                    tg.numScale = scale.numerator

            return

        # check for two durations with the same count
        # Try units = (dur1+dur2) * count
        if len(durCounts) == 2:
            counts: [int] = list(durCounts.values())
            if counts[0] == counts[1]:
                scale: HumNum = HumNum(counts[0]) / tggroup[0].numNotesActual
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
        maxDur: HumNum = HumNum(0)
        for dur in durCounts:
            if dur > maxDur:
                maxDur = dur

        totalDur: HumNum = HumNum(0)
        for tg in tggroup:
            totalDur += tg.duration

        units: HumNum = totalDur / maxDur
        if units.denominator == 1 and units > 1:
            scale: HumNum = units / tggroup[0].numNotesActual
            if scale.denominator == 1 and scale > 1:
                for tg in tggroup:
                    tg.numScale = scale.numerator
                return

    '''
    //////////////////////////////
    //
    // HumdrumInput::mergeTupletsCuttingBeam -- When a tuplet ends on a beamed note,
    //     but it can be continued with another tuplet of the same type, then merge the
    //     two tuplets.  These cases are caused by groupings needed at a higher level
    //     than the beat according to the time signature.
    '''
    @staticmethod
    def _mergeTupletsCuttingBeam(tgs: [HumdrumBeamAndTuplet]):

        # newtgs is a list of only durational items, removing things like clefs and barlines.
        # Actually it looks like it only has the tuplet-y items in it. --gregc
        newtgs: [HumdrumBeamAndTuplet] = []
        for tg in tgs:
            if tg.group >= 0:
                newtgs.append(tg)

        inBeam: [int] = [0] * len(newtgs)
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
                inBeam[i] = inBeam[i-1]
                continue

            # i == 0 and it's not a beamStart
            inBeam[i] = 0

        for i, tg in enumerate(newtgs):
            if not (inBeam[i] and tg.tupletEnd):
                continue
            # this is a tupletEnd that is within a beam (and not right at the end of the beam)

            if i >= len(newtgs) - 1:
                continue
            if not newtgs[i+1].tupletStart:
                continue
            if tg.tupletMultiplier != newtgs[i+1].tupletMultiplier:
                continue
            # and the next note is a tuplet start that qualifies to be in the same tuplet

            # Need to merge adjacent tuplets.
            newNotesActual: int = tg.numNotesActual + newtgs[i+1].numNotesActual
            newNotesNormal: int = tg.numNotesNormal + newtgs[i+1].numNotesNormal
            target = tg.tupletEnd
            for j in reversed(range(0, i+1)): # i..0 including i
                newtgs[j].numNotesActual = newNotesActual
                newtgs[j].numNotesNormal = newNotesNormal
                if newtgs[j].tupletStart == target:
                    break

            target = newtgs[i+1].tupletStart
            for j in range(i+1, len(newtgs)):
                if newtgs[j].group < 0: # not in the tuplet, why would this happen?
                    continue

                newtgs[j].numNotesActual = newNotesActual
                newtgs[j].numNotesNormal = newNotesNormal
                if not newtgs[j].tupletEnd:
                    continue
                if newtgs[j].tupletEnd == target:
                    break

            tg.tupletEnd = 0
            newtgs[i+1].tupletStart = 0

            for j in range(i+2, len(newtgs)):
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
    def _findTupletEndByBeamWithDottedPow2Duration(tupletStartIdx: int,
            beamStarts: [int], beamEnds: [int],
            beamPowDots: [int], powerOfTwoWithoutDots: [bool]) -> int:
        # i is an index into the beams, beamStartIdx/beamEndIdx are indices into durItems
        for i, beamStartIdx in enumerate(beamStarts):
            if beamStartIdx != tupletStartIdx:
                continue

            # we found a beam that starts where the tuplet starts

            if beamPowDots[i] < 0: # beamPowDot is the number of dots required to make the
                                   # beam duration into a power of two.
                                   # If -1, it can't be done.
                # beam starting at tuplet start doesn't have a (dotted) power-of-two
                # duration, so bail out
                return None

            beamEndIdx: int = beamEnds[i] # we will return this if all goes well

            for j in range(beamStartIdx, beamEndIdx+1): # includes beamEndIdx
                if powerOfTwoWithoutDots[j]:
                    # we ran out of tuplet notes before the end of the beam,
                    # so bail out
                    return None

            return beamEndIdx

        return None


    def _checkForTremolo(self, layerData: [HumdrumToken], tgs: [HumdrumBeamAndTuplet], tokenIdx: int, staffIndex: int):
        # test with Beethoven sonata20-2.krn
        pass

    '''
    //////////////////////////////
    //
    // HumdrumInput::checkForTupletForcedBreak --
    '''
    @staticmethod
    def _checkForTupletForcedBreak(durItems: [HumdrumToken], index: int) -> bool:
        if index == 0:
            return False

        if index > len(durItems):
            return False

        startTok: HumdrumToken = durItems[index]
        endTok: HumdrumToken = durItems[index - 1]
        stopLine: int = endTok.lineIndex
        curLine: int = startTok.lineIndex
        cur: HumdrumToken = startTok.previousToken(0)

        while cur and curLine > stopLine:
            if cur.isInterpretation and cur.text == '*tupbreak':
                return True
            cur = cur.previousToken(0)
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
    def _nextHigherPowerOfTwo(num: HumNum) -> HumNum:
        value: float = math.log(float(num)) / math.log(2.0)
        denom: int = int(-value)
        return HumNum(1, int(pow(2.0, denom)))

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
    def _getNumDotsForPowerOfTwo(value: HumNum) -> int:
        if Convert.isPowerOfTwo(value):
            return 0

        # check for one dot
        tval: HumNum = value * HumNum(2, 3)
        if Convert.isPowerOfTwo(tval):
            return 1

        # check for two dots
        tval = value * HumNum(4, 7)
        if Convert.isPowerOfTwo(tval):
            return 2

        # check for three dots
        tval = value * HumNum(8, 15)
        if Convert.isPowerOfTwo(tval):
            return 3

        # check for four dots
        tval = value * HumNum(16, 31)
        if Convert.isPowerOfTwo(tval):
            return 4

        return -1

    '''
        _processBarlinesInLayerData
    '''
    def _processBarlinesInLayerData(self, voice: m21.stream.Voice, track: int, layerIndex: int):
        staffIndex: int = self._staffStartsIndexByTrack[track]
        if staffIndex < 0:
            # not a kern/mens spine
            return

        layerData: [HumdrumToken] = self._layerTokens[staffIndex][layerIndex]
        if not layerData: # empty layer?!
            return

        if layerIndex == 0 and layerData and layerData[-1].isBarline:
            endBarline = layerData[-1]
#             if ';' in endBarline.text:
#                 self._addFermata(endBarline, None)
#             if ',' in endBarline.text:
#                 self._addBreath(endBarline, None)

            # check for rptend here, since the one for the last measure in
            # the music is missed by the inline processing.  But maybe limit
            # this one to only checking for the last measure.  Or move barline
            # styling here...
            if ':|' in endBarline.text or ':!' in endBarline.text:
                if self._oneMeasurePerStaff[staffIndex]:
                    self._oneMeasurePerStaff[staffIndex].rightBarline = m21.bar.Repeat(direction='end')

        # Check for repeat start at beginning of music.  The data for the very
        # first measure starts at the exclusive interpretation so that clefs
        # and time signatures and such are included.  If the first element
        # in the layer is an exclusive interpretation, then search for any
        # starting barline that should be checked for a repeat start:
        if layerData and layerData[0].isExclusiveInterpretation:
            for layerTok in layerData:
                if layerTok.isData:
                    break

                if not layerTok.isBarline:
                    continue

                if '|:' in layerTok.text or '!:' in layerTok.text:
                    if self._oneMeasurePerStaff[staffIndex]:
                        self._oneMeasurePerStaff[staffIndex].leftBarline = m21.bar.Repeat(direction='start')
                break

        # Check for repeat start at other places besides beginning of music:
        if layerIndex == 0 and layerData and layerData[0].isBarline:
            if '|:' in layerData[0].text or '!:' in layerData[0].text:
                if self._oneMeasurePerStaff[staffIndex]:
                    self._oneMeasurePerStaff[staffIndex].leftBarline = m21.bar.Repeat(direction='start')

        if layerData and layerData[-1].isBarline:
            self._processDirections(voice, layerData[-1], staffIndex)

    @staticmethod
    def _createNote(infoHash: HumHash = None) -> m21.note.Note:
        # infoHash is generally the token for which the note is being created,
        # but we declare it as a HumHash, since the only thing we read is
        # 'spannerHolder', and the only thing we write is 'generalNote'
        # The actual construction of the note contents from the token is done elsewhere.
        spannerHolder: m21.note.GeneralNote = None
        if infoHash:
            spannerHolder = infoHash.getValueM21Object('music21', 'spannerHolder')

        note: m21.note.Note = M21Convert.createNote(spannerHolder)
        if infoHash is not None and note is not None:
            infoHash.setValue('music21', 'generalNote', note)

        return note

    @staticmethod
    def _createUnpitched(infoHash: HumHash = None) -> m21.note.Note:
        # infoHash is generally the token for which the note is being created,
        # but we declare it as a HumHash, since the only thing we read is
        # 'spannerHolder', and the only thing we write is 'generalNote'
        # The actual construction of the note contents from the token is done elsewhere.
        spannerHolder: m21.note.GeneralNote = None
        if infoHash:
            spannerHolder = infoHash.getValueM21Object('music21', 'spannerHolder')

        unpitched: m21.note.Unpitched = M21Convert.createUnpitched(spannerHolder)
        if infoHash is not None and unpitched is not None:
            infoHash.setValue('music21', 'generalNote', unpitched)

        return unpitched

    @staticmethod
    def _createChord(infoHash: HumHash = None) -> m21.chord.Chord:
        # infoHash is generally the token for which the chord is being created,
        # but we declare it as a HumHash, since the only thing we read is
        # 'spannerHolder', and the only thing we write is 'generalNote'
        # The actual construction of the chord contents from the token is done elsewhere.
        spannerHolder: m21.note.GeneralNote = None
        if infoHash:
            spannerHolder = infoHash.getValueM21Object('music21', 'spannerHolder')

        chord: m21.chord.Chord = M21Convert.createChord(spannerHolder)
        if infoHash is not None and chord is not None:
            infoHash.setValue('music21', 'generalNote', chord)

        return chord

    @staticmethod
    def _createRest(infoHash: HumHash = None) -> m21.note.Rest:
        # infoHash is generally the token for which the rest is being created,
        # but we declare it as a HumHash, since the only thing we read is
        # 'spannerHolder', and the only thing we write is 'generalNote'
        # The actual construction of the rest contents from the token is done elsewhere.
        spannerHolder: m21.note.GeneralNote = None
        if infoHash:
            spannerHolder = infoHash.getValueM21Object('music21', 'spannerHolder')

        rest: m21.note.Rest = M21Convert.createRest(spannerHolder)
        if infoHash is not None and rest is not None:
            infoHash.setValue('music21', 'generalNote', rest)

        return rest

    '''
        _processChordLayerToken
    '''
    def _processChordLayerToken(self, voice: m21.stream.Voice, layerTok: HumdrumToken, staffIndex: int, layerIndex: int):
        chordOffsetInMeasure: Fraction = M21Convert.m21Offset(layerTok.durationFromBarline)
        voiceOffsetInMeasure: Union[Fraction, float] = \
            self._oneMeasurePerStaff[staffIndex].elementOffset(voice)
        chordOffsetInVoice: Union[Fraction, float] = chordOffsetInMeasure - voiceOffsetInMeasure
        chord: m21.chord.Chord = self._createChord(layerTok)

        # if (m_hasTremolo && layerdata[i]->getValueBool("auto", "tremolo")) {
        # else if (m_hasTremolo && layerdata[i]->getValueBool("auto", "tremolo2")) {

        # TODO: chord signifiers
        #self._processChordSignifiers(chord, layerTok, staffIndex)

        chord = self._convertChord(chord, layerTok, staffIndex, layerIndex)

        self._processSlurs(chord, layerTok)
        self._processPhrases(chord, layerTok)
        self._processDynamics(voice, layerTok, staffIndex)

        # TODO: chord stem directions, articulations, ornaments, arpeggios
#         self._assignAutomaticStem(chord, layerTok, staffIndex)
        self._addArticulations(chord, layerTok)
#         self._addOrnaments(chord, layerTok)
#         self._addArpeggio(chord, layerTok)
        self._processDirections(voice, layerTok, staffIndex)

        voice.insert(chordOffsetInVoice, chord)

    '''
        _convertChord
    '''
    def _convertChord(self, chord: m21.chord.Chord, layerTok: HumdrumToken, staffIndex: int, layerIndex: int) -> m21.chord.Chord:
#         int staffadj = getStaffAdjustment(token);
#         if (staffadj != 0) {
#             int staffnum = staffindex + 1 + staffadj;
#             setStaff(chord, staffnum);
#         }
        tstrings: [str] = layerTok.subtokens

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
            # Verovio doesn't properly suppress the stem that goes with the invisible note.
            # I'm not going to do that, since I want to describe exactly what is there, for
            # music21, and the exporters will each need to handle it correctly (or not!).
#             if ((!allinvis) && (tstrings[j].find("yy") != std::string::npos)) {
#                 continue;
#             }

            note = self._createNote() # pass in no infoHash, since this is only part of the chord
            note = self._convertNote(note, layerTok, 0, staffIndex, layerIndex, subTokenIdx)
            chord.add(note)

        if allInvisible:
            chord.style.hideObjectOnPrint = True

        # grace notes need to be done before rhythm since default
        # duration is set to an eighth note here.
        chord = self._processGrace(chord, layerTok.text)

        # chord tremolos
#         if (m_hasTremolo && token->getValueBool("auto", "tremolo")) {
#             hum::HumdrumToken newtok(token->getValue("auto", "recip"));
#             dur = convertRhythm(chord, &newtok, 0);
#         }
#         else if (m_hasTremolo && token->getValueBool("auto", "tremolo2")) {
#             hum::HumdrumToken newtok(token->getValue("auto", "recip"));
#             dur = convertRhythm(chord, &newtok, 0);
#         }
#         else if (m_hasTremolo && token->getValueBool("auto", "tremoloAux")) {
#             hum::HumdrumToken newtok(token->getValue("auto", "recip"));
#             dur = convertRhythm(chord, &newtok, 0);
#         }
#         else {
        self._convertRhythm(chord, layerTok)

        # LATER: Support *2\right for scores where half-notes' stems are on the right
        # I don't think music21 can do it, so...

        # Overwrite cross-stem direction if there is an explicit stem direction.
        # BUGFIX: We are doing this processing in _convertNote for notes that are in
        # BUGFIX: a chord, and for the chord here, so we might end up with notes in a chord
        # BUGFIX: whose stem direction is the opposite of the stem direction of the chord...
        if '/' in tstring:
            chord.stemDirection = 'up'
        elif '\\' in tstring:
            chord.stemDirection = 'down'

        # Stem direction of the chord.  If both up and down, then show up.
        # stem.dir is actually gone.  See _setBeamDirection, where we used to
        # set it, but now we just set chord.stemDirection directly there instead.
#         beamStemDir: int = layerTok.getValueInt('auto', 'stem.dir')
#         if beamStemDir == 1:
#             chord.stemDirection = 'up'
#         elif beamStemDir == -1:
#             chord.stemDirection = 'down'

        # We do not need to adjustChordNoteDurations, since _convertNote carefully did not
        # set note durations at all (in a chord). --gregc
        #    adjustChordNoteDurations(chord, notes, tstrings);

        index: int = len(self._allMeasuresPerStaff) - 1
        layerTok.setValue('music21', 'measureIndex', index)

        self._convertLyrics(chord, layerTok)
        return chord

    '''
        _processRestLayerToken
    '''
    def _processRestLayerToken(self, voice: m21.stream.Voice, layerTok: HumdrumToken, staffIndex: int):
        restOffsetInMeasure: Fraction = M21Convert.m21Offset(layerTok.durationFromBarline)
        voiceOffsetInMeasure: Union[Fraction, float] = \
            self._oneMeasurePerStaff[staffIndex].elementOffset(voice)
        restOffsetInVoice: Union[Fraction, float] = restOffsetInMeasure - voiceOffsetInMeasure
        rest: m21.note.Rest = self._createRest(layerTok)

        rest = self._convertRest(rest, layerTok, staffIndex)
        # TODO: rest colors
        #self._colorRest(rest, layerTok)
        self._processSlurs(rest, layerTok)
        self._processPhrases(rest, layerTok)
        self._processDynamics(voice, layerTok, staffIndex)
        self._processDirections(voice, layerTok, staffIndex)

        if 'yy' in layerTok.text and not self._signifiers.irestColor and not self._signifiers.spaceColor:
            # Invisible rest
            rest.style.hideObjectOnPrint = True

        voice.insert(restOffsetInVoice, rest)

    '''
    /////////////////////////////
    //
    // HumdrumInput::convertRest --
    '''
    def _convertRest(self, rest: m21.note.Rest, token: HumdrumToken, staffIndex: int) -> m21.note.Rest:
        self._convertRhythm(rest, token)
        self._positionRestVertically(rest, token)

        self._adjustStaff(rest, token, staffIndex)

#         if ';' in token.text:
#             self._addFermata(rest, token)

        index: int = len(self._allMeasuresPerStaff) - 1
        token.setValue('music21', 'measureIndex', index)

        return rest

    '''
        _adjustStaff: moves a note/rest/whatever to the staff above or
            below if necessary.
    '''
    def _adjustStaff(self, rest: m21.note.Rest, token: HumdrumToken, staffIndex: int):
        pass

    '''
        _positionRestVertically: uses the style.absoluteY value which was
            computed by HumdrumFileContent.analyzeRestPositions
    '''
    @staticmethod
    def _positionRestVertically(rest: m21.note.Rest, token: HumdrumToken):
        # I don't use getValueInt here because the default is 0, and I
        # need the default to be "don't set rest.style.absoluteY at all" --gregc
        absoluteYStr: str = token.getValue('auto', 'absoluteY')
        if absoluteYStr:
            rest.style.absoluteY = int(absoluteYStr)

    '''
        _processNoteLayerToken
    '''
    def _processNoteLayerToken(self, voice: m21.stream.Voice, layerTok: HumdrumToken, staffIndex: int, layerIndex: int):
        noteOffsetInMeasure: Fraction = M21Convert.m21Offset(layerTok.durationFromBarline)
        voiceOffsetInMeasure: Union[Fraction, float] = \
            self._oneMeasurePerStaff[staffIndex].elementOffset(voice)
        noteOffsetInVoice: Union[Fraction, float] = noteOffsetInMeasure - voiceOffsetInMeasure
        note: m21.note.Note = self._createNote(layerTok)

        # TODO: tremolos
        # if self._hasTremolo and layerTok.getValueBool('auto', 'tremolo'):
        #     note = self._processTremolo(note, layerTok, 0, staffIndex)
        # elif self._hasTremolo and layerTok.getValueBool('auto', 'tremolo2'):
        #     note = self._processTremolo2(note, layerTok, 0, staffIndex)
        # else:
        note = self._convertNote(note, layerTok, 0, staffIndex, layerIndex)

        self._processSlurs(note, layerTok)
        self._processPhrases(note, layerTok)
        self._processDynamics(voice, layerTok, staffIndex)
        # TODO: note stem directions, no stem, hairpin accent, cue size
        # TODO: note articulations, ornaments, arpeggio
#             assignAutomaticStem(note, layerdata[i], staffindex);
#             if (m_signifiers.nostem && layerdata[i]->find(m_signifiers.nostem) != std::string::npos) {
#                 note->SetStemVisible(BOOLEAN_false);
#             }
#hairpinAccent should be part of processArticulations.  It's separate because MEI doesn't do hairpin accents, so verovio fakes it.
#             if (m_signifiers.hairpinAccent && layerdata[i]->find(m_signifiers.hairpinAccent) != std::string::npos) {
#                 addHairpinAccent(layerdata[i]);
#             }
# this cuesize stuff is done in convertNote.  Put it in a new processCueSize function
# and call it from convertNote only (covers more cases than here).
#             if (m_signifiers.cuesize && layerdata[i]->find(m_signifiers.cuesize) != std::string::npos) {
#                 note->SetCue(BOOLEAN_true);
#             }
#             else if (m_staffstates.at(staffindex).cue_size.at(m_currentlayer)) {
#                 note->SetCue(BOOLEAN_true);
#             }
        self._addArticulations(note, layerTok)
#             addOrnaments(note, layerdata[i]);
#             addArpeggio(note, layerdata[i]);
#             processDirections(layerdata[i], staffindex); # m21.expressions.TextExpression
        voice.insert(noteOffsetInVoice, note)

    def _addArticulations(self, note: m21.note.GeneralNote, token: HumdrumToken):
        # store info about articulations in various dicts, keyed by humdrum articulation string
        # which is usually a single character, but can be two (e.g. '^^')
        articFound: dict = dict() # value is bool
        articPlacement: dict = dict() # value is 'below', 'above', or ''
        articIsGestural: dict = dict() # value is bool (gestural means "not printed on the page, but it's what the performer did")

        tsize: int = len(token.text)
        ch: str = ''
        ch1: str = ''
        ch2: str = ''
        ch3: str = ''
        skipNChars: int = 0

        for i in range(0, tsize):
            if skipNChars:
                skipNChars -= 1
                continue

            ch = token.text[i]
            if ch.isdigit():
                continue

            ch1 = ''
            if i+1 < tsize:
                ch1 = token.text[i+1]
            if ch == '^' and ch1 == '^':
                ch = '^^'
                ch1 = ''
                skipNChars = 1
                if i+skipNChars+1 < tsize:
                    ch1 = token.text[i+skipNChars+1]
            elif ch == "'" and ch1 == "'":
                # staccatissimo alternate (eventually remove)
                ch = '`'
                ch1 = ''
                skipNChars = 1
                if i+skipNChars+1 < tsize:
                    ch1 = token.text[i+skipNChars+1]
            # this will include a bunch of non-articulation characters as well, but we
            # will only look for the ones we know, below.
            articFound[ch] = True
            articIsGestural[ch] = False
            articPlacement[ch] = ''

            if ch1:
                # check for gestural (hidden) articulations
                ch2 = ''
                if i+skipNChars+2 < tsize:
                    ch2 = token.text[i+skipNChars+2]
                ch3 = ''
                if i+skipNChars+3 < tsize:
                    ch3 = token.text[i+skipNChars+3]

                if ch1 == 'y' and ch2 != 'y':
                    articIsGestural[ch] = True
                elif self._signifiers.above and ch1 == self._signifiers.above \
                        and ch2 == 'y' and ch3 != 'y':
                    articIsGestural[ch] = True
                elif self._signifiers.below and ch1 == self._signifiers.below \
                        and ch2 == 'y' and ch3 != 'y':
                    articIsGestural[ch] = True

            if self._signifiers.above and ch1 == self._signifiers.above:
                articPlacement[ch] = 'above'
            elif self._signifiers.below and ch1 == self._signifiers.below:
                articPlacement[ch] = 'below'


        artics: [m21.articulations.Articulation] = []

        # place articulations in stacking order (nearest to furthest from note)
        # (not sure if that does anything for music21, but whatever --gregc)
        if articFound.get("'", None):
            staccato = m21.articulations.Staccato()
            placement: str = articPlacement["'"]
            if placement:
                staccato.placement = placement
            if articIsGestural["'"]:
                staccato.style.hideObjectOnPrint = True
            artics.append(staccato)

        if articFound.get('`', None):
            staccatissimo = m21.articulations.Staccatissimo()
            placement: str = articPlacement['`']
            if placement:
                staccatissimo.placement = placement
            if articIsGestural['`']:
                staccatissimo.style.hideObjectOnPrint = True
            artics.append(staccatissimo)

        if articFound.get('~', None):
            tenuto = m21.articulations.Tenuto()
            placement: str = articPlacement['~']
            if placement:
                tenuto.placement = placement
            if articIsGestural['~']:
                tenuto.style.hideObjectOnPrint = True
            artics.append(tenuto)

        if articFound.get('^^', None):
            strongAccent = m21.articulations.StrongAccent()
            placement: str = articPlacement['^^']
            if placement:
                strongAccent.placement = placement
            if articIsGestural['^^']:
                strongAccent.style.hideObjectOnPrint = True
            artics.append(strongAccent)

        if articFound.get('^', None):
            accent = m21.articulations.Accent()
            placement: str = articPlacement['^']
            if placement:
                accent.placement = placement
            if articIsGestural['^']:
                accent.style.hideObjectOnPrint = True
            artics.append(accent)

        if articFound.get('o', None):
            harmonic = m21.articulations.Harmonic()
            placement: str = articPlacement['o']
            if placement:
                harmonic.placement = placement
            if articIsGestural['o']:
                harmonic.style.hideObjectOnPrint = True
            artics.append(harmonic)

        if articFound.get('v', None):
            upBow = m21.articulations.UpBow()
            placement: str = articPlacement['v']
            if placement:
                upBow.placement = placement
            if articIsGestural['v']:
                upBow.style.hideObjectOnPrint = True
            artics.append(upBow)

        if articFound.get('u', None):
            downBow = m21.articulations.DownBow()
            placement: str = articPlacement['u']
            if placement:
                downBow.placement = placement
            if articIsGestural['u']:
                downBow.style.hideObjectOnPrint = True
            artics.append(downBow)

        if artics:
            note.articulations = artics

    def _processSlurs(self, endNote: m21.note.GeneralNote, token: HumdrumToken):
        slurEndCount: int = token.getValueInt('auto', 'slurEndCount')
        if slurEndCount <= 0:
            return # not a slur end

        # slurstarts: indexed by slur end number (NB: 0 position not used).
        # tuple contains the slur start enumeration (tuple[0]) and the start token (tuple[1])
        slurStartList: [tuple] = [(-1, None)] * (slurEndCount + 1)
        for i in range(1, slurEndCount+1):
            slurStartList[i] = (token.getSlurStartNumber(i), token.getSlurStartToken(i))

        for i in range(1, slurEndCount+1):
            slurStartTok: HumdrumToken = slurStartList[i][1]
            if not slurStartTok:
                continue

            slurStartNumber: int = slurStartList[i][0]
            isInvisible: bool = self._checkIfSlurIsInvisible(slurStartTok, slurStartNumber)
            if isInvisible:
                continue

            startNote: m21.note.GeneralNote = slurStartTok.getValueM21Object(
                                                'music21', 'generalNote')
            if not startNote:
                # startNote can sometimes not be there yet, due to cross layer slurs.
                # Here we make a placeholder GeneralNote, from which createNote will
                # transfer the spanners, when creating the actual note.
                startNote = m21.note.GeneralNote()
                slurStartTok.setValue('music21', 'spannerHolder', startNote)

            slur: m21.spanner.Slur = m21.spanner.Slur(startNote, endNote)
            self._addSlurLineStyle(slur, slurStartTok, slurStartNumber)

            # set above/below from current layout parameter (if there is one)
            self._setLayoutSlurDirection(slur, slurStartTok)

            # Calculate if the slur should be forced above or below
            # this is the case for doubly slured chords.  Only the first
            # two slurs between a pair of notes/chords will be oriented
            # (other slurs will need to be manually adjusted and probably
            # linked to individual notes to avoid overstriking the first
            # two slurs.
            if slurEndCount > 1:
                found: int = -1
                for j in range(1, slurEndCount):
                    if i == j:
                        continue
                    if slurStartList[i][1] == slurStartList[j][1]:
                        found = j
                        break
                if found > 0:
                    if found > i:
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
                        if slurStartTok.text[k+1] == self._signifiers.above:
                            slur.placement = 'above'
                        elif slurStartTok.text[k+1] == self._signifiers.below:
                            slur.placement = 'below'
                        break

            # Put spanner in top-level stream, because it might contain notes
            # that are in different Parts.
            self.m21Stream.insert(0, slur)

    def _setLayoutSlurDirection(self, slur: m21.spanner.Slur, token: HumdrumToken):
        if self._hasAboveParameter(token, 'S'):
            slur.placement = 'above'
        elif self._hasBelowParameter(token, 'S'):
            slur.placement = 'below'

    @staticmethod
    def _addSlurLineStyle(slur: m21.spanner.Slur, token: HumdrumToken, slurNumber: int):
        if slurNumber < 1:
            slurNumber = 1
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
        for i in range(0, tsize-1):
            if token.text[i] == '(':
                counter += 1
            if counter == number:
                if token.text[i+1] == 'y':
                    return True
                return False
        return False

    def _processPhrases(self, note: m21.note.GeneralNote, token: HumdrumToken):
        # TODO: phrases
        pass

    @staticmethod
    def _processGrace(noteOrChord: Union[m21.note.Note, m21.chord.Chord], tstring: str) -> Union[m21.note.Note, m21.chord.Chord]:
        myNC: Union[m21.note.Note, m21.chord.Chord] = noteOrChord
        if 'qq' in tstring:
            myNC = myNC.getGrace(appoggiatura=True)
            myNC.duration.slash = False
            myNC.duration.type = 'eighth' # for now, recomputed later
        elif 'q' in tstring:
            myNC = myNC.getGrace(appoggiatura=False)
            myNC.duration.type = 'eighth' # for now, recomputed later
        return myNC

    def _convertNote(self, note: m21.note.Note, token: HumdrumToken, staffAdjust: int, staffIndex: int, layerIndex: int, subTokenIdx: int = -1) -> m21.note.Note:
        # note is empty.  Fill it in.
        ss: StaffStateVariables = self._staffStates[staffIndex]
        tstring: str = token.text
        if subTokenIdx >= 0:
            tstring = token.subtokens[subTokenIdx]

        # TODO: scordatura

        isChord: bool = token.isChord # we might be converting one note (subtoken) of a chord (token)
        isUnpitched: bool = token.isUnpitched
        isBadPitched: bool = False

        # Q: Should pitched note in staff with *clefX be colored (because it's an error)?
        # if not isUnpitched and ss.lastClef.text.startswith('*clefX'):
        #     isBadPitched = True # it's wrong
        #     isUnpitched = True  # fix it

        self._processTerminalLong(token)

        # TODO: overfilling notes (might be a no-op for music21)
        #self._processOverfillingNotes(token)

        # TODO: support colored notes
        # (e.g. use note.style.color = 'red')
        self._colorNote(note, token, tstring)

        # handleOttavaMark doesn't perhaps match music21's model
        # (m21.Ottava is a Spanner containing the notes involved)
        # so handleOttavaMark may need to be rewritten so we can
        # do the right thing in the inline code here
        # self._processOttava(note, token, staffIndex) # new factored routine

        # check for accacciatura ('q') and appoggiatura ('qq')
        if not isChord:
            note = self._processGrace(note, tstring)

        # Add the pitch information
        # This here is the point where Verovio transposes "transposing instruments"
        # back to the written key, but we don't do that (music21 understands transposing
        # instruments just fine).
        m21PitchName: str = M21Convert.m21PitchName(tstring)
        octave: int = Convert.kernToOctaveNumber(tstring)

        if isUnpitched:
            note = self._createUnpitched(token)
            note.displayOctave = octave
            note.displayStep = m21PitchName
        else:
            # Q: might need to jump octaves backward to the ottava?  Maybe that's just MEI.
            # Q: music21 has transposing and non-transposing ottavas, so we probably just
            # Q: need to use the right one, so we can leave the note alone.
            note.octave = octave
            note.name = m21PitchName

        if isBadPitched:
            note.style.color = '#c41414'

        # TODO: editorial and cautionary accidentals (partially implemented)
        # needs some work (and a revisiting of the iohumdrum.cpp code)

        if token.getBooleanLayoutParameter('N', 'xstem'):
            note.stemDirection = 'nostem'

        if token.getBooleanLayoutParameter('N', 'cue'):
            note.style.noteSize = 'cue'

        self._setNoteHead(note, token, subTokenIdx, staffIndex) # new

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

        # editorial and cautionary needs some work (and a revisiting of the iohumdrum.cpp code)
        # check for editorial or cautionary accidental
        hasCautionary: bool = token.hasCautionaryAccidental(subTokenIdx)
        # cautionaryOverride: str = None # e.g. 'n#', where the note just has '#'
        hasEditorial: bool = token.hasEditorialAccidental(subTokenIdx)
        editorialStyle: str = ''
        if hasCautionary or hasEditorial:
            # cautionaryOverride: str = token.cautionaryAccidental(subTokenIdx)
            editorialStyle: str = token.editorialAccidentalStyle(subTokenIdx)


        if not mensit and not isUnpitched:
            if hasEditorial or hasCautionary:
                if not note.pitch.accidental:
                    note.pitch.accidental = m21.pitch.Accidental('natural')

                if hasEditorial:
                    note.pitch.accidental.displayStatus = True # forces it to be displayed
                    if editorialStyle.startswith('brac'):
                        note.pitch.accidental.displayStyle = 'bracket'
                    elif editorialStyle.startswith('paren'):
                        note.pitch.accidental.displayStyle = 'parentheses'
                    elif editorialStyle in ('a', 'above'):
                        note.pitch.accidental.displayLocation = 'above'
                elif hasCautionary: # cautionary is ignored if we have editorial.
                    # music21 can't deal with overrides unless I actually change
                    # the value of the note (that ain't right)
                    # music21 can't deal with the combo overrides ('n#') or the
                    # alternate spelling overrides ('##' vs. 'x') at all.
                    # See todo.txt for a possible music21 cautionary override method.
                    note.pitch.accidental.displayStatus = True # forces it to be displayed

        # we don't set the duration of notes in a chord.  The chord gets a duration
        # instead.
        if not isChord:
            if self._hasTremolo and token.getValueBool('auto', 'tremolo'):
                newtok: HumdrumToken = token.getValueToken('auto', 'recip')
                self._convertRhythm(note, newtok, 0)
            elif self._hasTremolo and token.getValueBool('auto', 'tremolo2'):
                newtok: HumdrumToken = token.getValueToken('auto', 'recip')
                self._convertRhythm(note, newtok, 0)
            elif self._hasTremolo and token.getValueBool('auto', 'tremoloAux'):
                newtok: HumdrumToken = token.getValueToken('auto', 'recip')
                self._convertRhythm(note, newtok, 0)
            else:
                self._convertRhythm(note, token, subTokenIdx)

        # LATER: Support *2\right for scores where half-notes' stems are on the right
        # I don't think music21 can do it, so...

        # Q: Figure out why a note with duration zero is being displayed by
        # Q: Verovio as a stemless quarter note.
        # Q: I'm just going to put it in the music21 stream as a zero-duration note,
        # Q: and see what happens.
#         if dur == 0:
#             note.duration.quarterLength = 1
#             note.stemDirection = 'nostem'
#             # if you want a stemless grace note, then set the
#             # stemlength to zero explicitly.
        else:
            # TODO: note visual duration that is different from chord visual duration
            pass
#             std::string chordvis = token->getVisualDurationChord();
#             if (chordvis.empty()) {
#                 std::string notevis = token->getVisualDuration(subtoken);
#                 if (!notevis.empty()) {
#                     convertRhythm(note, token, subtoken);
#                 }
#             }

        self._setStemDirection(note, tstring)

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
            self._convertLyrics(note, token)

        # measure index (for later m21.spanner stuff: slurs, ties, phrases, etc)
        if not isChord:
            index: int = len(self._allMeasuresPerStaff) - 1
            token.setValue('music21', 'measureIndex', index)

        # cue sized notes
        if self._signifiers.cueSize \
                and self._signifiers.cueSize in tstring:
            # note is marked as cue-sized
            note.style.noteSize = 'cue'
        elif ss.cueSize[layerIndex]:
            # layer is marked as containing all cue-sized notes
            note.style.noteSize = 'cue'

        return note

    '''
    //////////////////////////////
    //
    // processTerminalLong -- Not set up for chords yet.
    '''
    def _processTerminalLong(self, token: HumdrumToken):
        if not self._signifiers.terminalLong:
            return
        if self._signifiers.terminalLong not in token.text:
            return

        token.setValue('LO', 'N', 'vis', '00') # set visual duration to "long" (i.e. 4 whole notes)

        # TODO: terminal longs (partially implemented)
        # 1. make following barlines invisible
        # 2. if token is tied, follow ties to attached notes and make them invisible

    '''
    //////////////////////////////
    //
    // HumdrumInput::colorNote --
    '''
    def _colorNote(self, note: m21.note.Note, token: HumdrumToken, tstring: str):
        spineColor: str = self._getSpineColor(token)
        if spineColor:
            note.style.color = spineColor

        # also check for marked notes (the marked color will override spine color)
        for i, mark in enumerate(self._signifiers.noteMarks):
            if mark in tstring:
                note.style.color = self._signifiers.noteColors[i]
                # TODO: note-associated text
                # (e.g. rds-scores: R129_Jan-w30p11m124-127.krn)
                if self._signifiers.noteDirs[i]:
                    pass
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
        output: str = ''
        track: int = token.track
        strack: int = token.subTrack
        output: str = self._spineColor[track][strack]

        if not self._hasColorSpine:
            return output

        lineIdx = token.lineIndex
        fieldIdx = token.fieldIndex
        for i in range(fieldIdx + 1, self[lineIdx].fieldCount):
            tok: HumdrumToken = self[lineIdx][i]
            if not tok.isDataType('**color'):
                continue

            output = tok.nullResolution
            if output == '.':
                output = ''
            break

        return output

    '''
        _setNoteHead
    '''
    def _setNoteHead(self, note: m21.note.Note, token: HumdrumToken, subTokenIdx: int, staffIndex: int):
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
                except m21.note.NotRestException: # if unrecognized
                    pass # use default notehead

    @staticmethod
    def _setStemDirection(note: m21.note.Note, tstring: str):
        # stem direction (if any)
        if '/' in tstring:
            note.stemDirection = 'up'
        elif '\\' in tstring:
            note.stemDirection = 'down'

        # ('auto', 'stem.dir') is gone, due to the rework of beam and tuplet processing.
        # In _setBeamDirection, where we figure out beam stems (and where we used to set
        # 'stem.dir', we've already called _setStemDirection, so it's too late. We just
        # override note.stemDirection explicitly there, instead.
#         beamStemDir: int = token.getValueInt('auto', 'stem.dir')
#         if beamStemDir == 1:
#             note.stemDirection = 'up'
#         elif beamStemDir == -1:
#             note.stemDirection = 'down'

    '''
    //////////////////////////////
    //
    // HumdrumInput::convertVerses --
    '''
    def _convertLyrics(self, obj: m21.Music21Object, token: HumdrumToken):
        pass
        # TODO: lyrics

    '''
    //////////////////////////////
    //
    // HumdrumInput::processTieStart -- linked slurs not allowed in chords yet.
    '''
    def _processTieStart(self, note: m21.note.Note, token: HumdrumToken, tstring: str, subTokenIdx: int, layerIndex: int):
        if token.isMens:
            return

        isContinue: bool = '_' in tstring

        endTag: str = 'tieEnd'
        if subTokenIdx >= 0:
            endTag += str(subTokenIdx + 1) # tieEndN tags are 1-based

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


        tie = HumdrumTie()
        tie.setStart(layerIndex,
                     note,
                     token,
                     tstring,
                     subTokenIdx)

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
    def _processTieEnd(self, note: m21.note.Note, token: HumdrumToken, tstring: str, subTokenIdx: int, layerIndex: int):
        if token.isMens:
            return

        startTag = 'tieStart'
        if token.isChord:
            startTag += str(subTokenIdx + 1) # tieStartN tags are 1-based

        tieStartTok = token.getValueToken('auto', startTag)
        if tieStartTok:
            # linked ties are handled in processTieStart()
            # (but we might need to simply put a tie end on this note)
            if ']' in tstring: # not '_'
                note.tie = m21.tie.Tie('stop') # that's it, no style or placement
            return

        timeStamp: HumNum = token.durationFromStart
        track: int = token.track
        staffIndex: int = self._staffStartsIndexByTrack[track]
        ss: StaffStateVariables = self._staffStates[staffIndex]
        disjunct: bool = ']]' in tstring or '__' in tstring
        pitch: int = Convert.kernToMidiNoteNumber(tstring)
        found: HumdrumTie = None

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
                if disjunct and '__' in tie.startSubTokenStr: # BUGFIX: This "if" was missing.
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
    def _addTieStyle(self, tie: m21.tie.Tie, token: HumdrumToken, tstring: str, subTokenIdx: int):
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
    @staticmethod
    def _convertRhythm(obj: m21.Music21Object, token: HumdrumToken, subTokenIdx: int = -1) -> HumNum:
#         if token.isMens:
#             return self._convertMensuralRhythm(obj, token, subTokenIdx)

        # instead of just doing dur = token.duration, we need to recompute
        # it, because we need to get a real duration from grace notes (token.duration
        # always returns 0 for grace notes)
        tstring: str = token.text.lstrip(' ')
        if subTokenIdx >= 0:
            tstring = token.subTokens[subTokenIdx]

        # Remove grace note information (for generating printed duration)
        if 'q' in tstring:
            tstring = re.sub('q', '', tstring)

        # music21 does not support visual duration different from actual
        # (gestural) duration.  Humdrum can do it via layout parameters,
        # and MEI can do it, but music21 cannot.  So, if there is a visual
        # duration, that's the one we encode (because that will cause it
        # to be visible on the printed page).
        vstring: str = token.getVisualDuration(subTokenIdx)

        if vstring:
            dur = Convert.recipToDuration(vstring)
        else:
            dur = Convert.recipToDuration(tstring)

        obj.duration.quarterLength = Fraction(dur)

        return dur

    '''
        _processOtherLayerToken
    '''
    def _processOtherLayerToken(self, voice: m21.stream.Voice, layerTok: HumdrumToken, staffIndex: int):
        pass

    '''
        _processSuppressedLayerToken
    '''
    def _processSuppressedLayerToken(self, voice: m21.stream.Voice, layerTok: HumdrumToken, staffIndex: int):
        # This element is not supposed to be printed,
        # probably due to being in a tremolo.
        # But first check for dynamics and text, which
        # should not be suppressed:
        self._processDynamics(voice, layerTok, staffIndex)
        self._processDirections(voice, layerTok, staffIndex)

    def _processDynamics(self, voice: m21.stream.Voice, token: HumdrumToken, staffIndex: int):
        dynamic: str = ''
        isGrace: bool = token.isGrace
        line: HumdrumLine = token.ownerLine
        ss: StaffStateVariables = self._staffStates[staffIndex]

        if not line:
            return

        dynamicOffsetInMeasure: Fraction = M21Convert.m21Offset(token.durationFromBarline)
        voiceOffsetInMeasure: Union[Fraction, float] = \
            self._oneMeasurePerStaff[staffIndex].elementOffset(voice)
        dynamicOffsetInVoice: Union[Fraction, float] = dynamicOffsetInMeasure - voiceOffsetInMeasure


        track: int = token.track
        lastTrack: int = track
        ttrack: int = -1
        startField: int = token.fieldIndex + 1

#         forceAbove: bool = False
#         forceBelow: bool = False
#         forceCenter: bool = False
        trackDiff: int = 0
#         staffAdjust: int = ss.dynamStaffAdj
#         force: bool = False

#         if ss.dynamPos > 0:
#             #force = True
#             forceAbove = True
#         elif ss.dynamPos < 0:
#             #force = True
#             forceBelow = True
#         elif ss.dynamPos == 0 and ss.dynamPosDefined:
#             forceCenter = True
#         elif ss.hasLyrics:
#             forceAbove = True # Q: is this something we shouldn't do (rendering decisions)?

#         justification: bool = False
#         if token.layoutParameter('DY', 'rj') == 'true':
#             justification = True

        dcolor: str = token.layoutParameter('DY', 'color')
#         needsRend: bool = justification or dcolor

        # Handle "z" for sforzando (sf), or "zz" for sfz
        #   This seems to be at the wrong level, shouldn't it be inside the loop below? --gregc
        if 'z' in token.text:
            print('_processDynamics: "z" found in token.text at top level')

        active: bool = True
        for i in range(startField, line.tokenCount):
            staffAdj = ss.dynamStaffAdj
            dynTok: HumdrumToken = line[i]
            exInterp: str = dynTok.dataType.text
            if exInterp != '**kern' and 'kern' in exInterp:
                active = False # will this ever be true? --gregc
            if dynTok.isKern:
                active = True
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
            if not (dynTok.isDataType('**dynam') or dynTok.isDataType('**dyn')):
                continue

            # Don't skip NULL tokens, because this algorithm only prints dynamics
            # after the last layer, and there could be notes in earlier layer
            # that need the dynamic.
            # if dynTok.isNull:
            #     continue

            dynTokStr: str = dynTok.text
            if dynTok.getValueBool('auto', 'DY', 'processed'):
                return
            dynTok.setValue('auto', 'DY', 'processed', 'true')

            # int pcount = dyntok->getLinkedParameterSetCount();

            hairpins: str = ''
            letters: str = ''
            for ch in dynTokStr:
                if ch.isalpha():
                    letters += ch
                else:
                    hairpins += ch

            if re.search('^[sr]?f+z?$', letters): # 'sf', 'sfz', 'f', 'fff', etc ('rfz'? really?)
                dynamic = letters
            elif re.search('^p+$', letters): # 'p', 'ppp', etc
                dynamic = letters
            elif re.search('^m?(f|p)$', letters): # 'mf', 'mp'
                dynamic = letters
            elif re.search('^s?f+z?p+$', letters): # 'fp', 'sfzp', 'ffp' etc
                dynamic = letters

            if dynamic:
                staffAdj = ss.dynamStaffAdj

                dynText: str = self._getLayoutParameterWithDefaults(dynTok, 'DY', 't', '', '')
                if dynText:
                    dynText = re.sub('%s', dynamic, dynText)
                    dynamic = dynText

                above: bool = self._hasAboveParameter(dynTok, 'DY') #, staffAdj)
                below: bool = False
                center: bool = False
#                 showPlace: bool = above
                if not above:
                    below = self._hasBelowParameter(dynTok, 'DY') #, staffAdj)
#                     showPlace = below
                if not above and not below:
                    hasCenter, staffAdj = self._hasCenterParameter(token, 'DY', staffAdj)
                    if hasCenter:
                        above = False
                        below = False
                        center = True
#                         showPlace = center

                # if pcount > 0, then search for prefix and postfix text
                # to add to the dynamic.
                # std::string prefix = "aaa ";
                # std::string postfix = " bbb";
                # See https://github.com/music-encoding/music-encoding/issues/540

                rightJustified: bool = False
                if dynTok.layoutParameter('DY', 'rj') == 'true':
                    rightJustified = True

                #editorial: bool = False
                editStr: str = self._getLayoutParameterWithDefaults(dynTok, 'DY', 'ed', 'true', '')
                if editStr:
                    #editorial = True
                    if 'brack' in editStr:
                        dynamic = '[ ' + dynamic + ' ]'
                    elif 'paren' in editStr:
                        dynamic = '( ' + dynamic + ' )'
                    elif 'curly' in editStr:
                        dynamic = '{ ' + dynamic + ' }'
                    elif 'angle' in editStr:
                        dynamic = '< ' + dynamic + ' >'

                dcolor: str = dynTok.layoutParameter('DY', 'color')
                #needsRend: bool = justification or dcolor

                # Here is where we create the music21 object for the dynamic
                m21Dynamic: m21.dynamics.Dynamic = m21.dynamics.Dynamic(dynamic)
                m21Dynamic.fontStyle = 'bold' # this is what verovio does
                if dcolor:
                    m21Dynamic.style.color = dcolor
                if rightJustified:
                    m21Dynamic.style.justify = 'right'

                # verticalgroup: str = dyntok.layoutParameter('DY', 'vg')
                # Q: is there a music21 equivalent to MEI's verticalgroup?
                if above:
                    m21Dynamic.style.absoluteY = 'above'
                elif below:
                    m21Dynamic.style.absoluteY = 'below'
                elif center:
                    m21Dynamic.style.absoluteY = -20
#                 elif forceAbove:
#                     m21Dynamic.style.absoluteY = 'above'
#                 elif forceBelow:
#                     m21Dynamic.style.absoluteY = 'below'
#                 elif forceCenter:
#                     m21Dynamic.style.absoluteY = -20

                voice.insert(dynamicOffsetInVoice, m21Dynamic)

            if hairpins:
                self._processHairpin(voice, dynamicOffsetInVoice, hairpins, token, dynTok, staffIndex)

        token = token.nextToken(0)
        if not token:
            return

        while token and not token.isData:
            token = token.nextToken(0)

        if not token:
            return
        if not token.isNull:
            return

        # re-run this function on null tokens after the main note since
        # there may be dynamics unattached to a note (for various often
        # legitimate reasons).  Maybe make this more efficient later, such as
        # do a separate parse of dynamics data in a different loop.
        self._processDynamics(voice, token, staffIndex)


    def _processHairpin(self, voice: m21.stream.Voice, dynamicOffsetInVoice: Union[Fraction, float],
                        hairpins: str, token: HumdrumToken, dynTok: HumdrumToken, staffIndex: int):
        if '<' in hairpins:
            startHairpin = '<'
            stopHairpin = '['
        elif '>' in hairpins:
            startHairpin = '>'
            stopHairpin = ']'
        else:
            return

        startStopHairpin1 = startHairpin + stopHairpin
        startStopHairpin2 = startHairpin + ' ' + stopHairpin

        ss: StaffStateVariables = self._staffStates[staffIndex]

#         endLine: bool = False
        endTok: HumdrumToken = None
#         duration: HumNum = HumNum(0)
        if startStopHairpin1 in hairpins or startStopHairpin2 in hairpins:
#             duration = self._getLeftNoteDuration(token)
            endTok = token
#             endLine = True
        else:
            endTok = self._getHairpinEnd(dynTok, stopHairpin)

        staffAdj = ss.dynamStaffAdj
        above: bool = self._hasAboveParameter(dynTok, 'HP') #, staffAdj)
        below: bool = False
        center: bool = False
#         showPlace: bool = above
        if not above:
            below = self._hasBelowParameter(dynTok, 'HP') #, staffAdj)
#             showPlace = below
        if not above and not below:
            hasCenter, staffAdj = self._hasCenterParameter(dynTok, 'HP', staffAdj)
            if hasCenter:
                above = False
                below = False
                center = True
#                 showPlace = center

        if endTok:
            # Here is where we create the music21 object for the crescendo/decrescendo
            m21Hairpin: m21.dynamics.DynamicWedge
            if startHairpin == '<':
                m21Hairpin = m21.dynamics.Crescendo()
            else:
                m21Hairpin = m21.dynamics.Diminuendo()

            # LATER: staff adjustments for dynamics and forcing position
            if center and not above and not below:
                m21Hairpin.style.absoluteY = -20
            else:
                if above:
                    m21Hairpin.style.absoluteY = 'above'
                elif below:
                    m21Hairpin.style.absoluteY = 'below'
#                 elif forceAbove:
#                     m21Hairpin.style.absoluteY = 'above'
#                 elif forceBelow:
#                     m21Hairpin.style.absoluteY = 'below'

            # Now I need to put the start and end "notes" into the Crescendo spanner.
            # This is instead of all the timestamp stuff verovio does.
            startNoteToken: HumdrumToken = self._getAppropriateNearbyNoteToken(token, start=True)
            endNoteToken: HumdrumToken = self._getAppropriateNearbyNoteToken(endTok, start=False)

            if not startNoteToken and not endNoteToken:
                # should never happen
                raise HumdrumSyntaxError('no start or end note token for hairpin')

            if not startNoteToken:
                startNoteToken = endNoteToken
            if not endNoteToken:
                endNoteToken = startNoteToken

            startNote: m21.note.GeneralNote = startNoteToken.getValueM21Object(
                                                'music21', 'generalNote')
            endNote: m21.note.GeneralNote = endNoteToken.getValueM21Object(
                                                'music21', 'generalNote')
            if not startNote:
                # startNote can sometimes not be there yet, due to cross layer slurs.
                # Here we make a placeholder GeneralNote, from which createNote will
                # transfer the spanners, when creating the actual note.
                startNote = m21.note.GeneralNote()
                startNoteToken.setValue('music21', 'spannerHolder', startNote)
            if not endNote:
                # endNote can sometimes not be there yet, due to cross layer slurs.
                # Here we make a placeholder GeneralNote, from which createNote will
                # transfer the spanners, when creating the actual note.
                endNote = m21.note.GeneralNote()
                endNoteToken.setValue('music21', 'spannerHolder', endNote)

            m21Hairpin.addSpannedElements(startNote, endNote)
            self.m21Stream.insert(0, m21Hairpin)
        else:
            # no endpoint so print as the word "cresc."/"decresc." (modified by _signifiers and layout)
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

            pinText = self._getLayoutParameterWithDefaults(dynTok, 'HP', 't', '', '')
            if pinText:
                pinText = re.sub('%s', content, pinText)
                content = pinText

            m21TextExp: m21.expressions.TextExpression = m21.expressions.TextExpression(content)
            if fontStyle:
                m21TextExp.style.fontStyle = fontStyle

            if center and not above and not below:
                m21TextExp.style.absoluteY = -20
            else:
                if above:
                    m21TextExp.style.absoluteY = 'above'
                elif below:
                    m21TextExp.style.absoluteY = 'below'
#                 elif forceAbove:
#                     m21TextExp.style.absoluteY = 'above'
#                 elif forceBelow:
#                     m21TextExp.style.absoluteY = 'below'
            voice.insert(dynamicOffsetInVoice, m21TextExp)

    '''
    //////////////////////////////
    //
    // HumdrumInput::getLeftNoteDuration --
    '''
    def _getLeftNoteDuration(self, token: HumdrumToken) -> HumNum:
        output: HumNum = HumNum(0)
        leftNote: HumdrumToken = self._getLeftNoteToken(token)
        if leftNote:
            output = Convert.recipToDuration(leftNote.text)
        return output

    @staticmethod
    def _getLeftNoteToken(token: HumdrumToken) -> HumdrumToken:
        output: HumdrumToken = None
        current: HumdrumToken = token
        while current:
            if not current.isKern:
                current = current.previousFieldToken
                continue
            if not current.isNonNullData:
                current = current.previousFieldToken
                continue
            output = current
            break
        return output

    @staticmethod
    def _getRightNoteToken(token: HumdrumToken) -> HumdrumToken:
        output: HumdrumToken = None
        current: HumdrumToken = token
        while current:
            if not current.isKern:
                current = current.nextFieldToken
                continue
            if current.isNonNullData:
                current = current.nextFieldToken
                continue
            output = current
            break
        return output

    def _getAppropriateNearbyNoteToken(self, token: HumdrumToken, start: bool) -> HumdrumToken:
        # look left, then right
        # if start, look up (left and right) until you hit a barline, then down
        # if not start, look down (left and right) first, then up
        # a good token isKern and isNonNullData
        output: HumdrumToken = self._getLeftNoteToken(token)
        if output:
            return output

        output = self._getRightNoteToken(token)
        if output:
            return output

        if start:
            # start walking up the file until we hit a barline, looking left and right
            current = token.previousToken(0)
            while not current.isBarline:
                if current.isInterpretation or current.isComment:
                    current = current.previousToken(0)
                    continue

                output = self._getLeftNoteToken(current)
                if output:
                    return output

                output = self._getRightNoteToken(current)
                if output:
                    return output

                current = current.previousToken(0)

            # didn't find anything earlier in the measure, try later in the measure
            current = token.nextToken(0)
            while not current.isBarline:
                if current.isInterpretation or current.isComment:
                    current = current.nextToken(0)
                    continue

                output = self._getLeftNoteToken(current)
                if output:
                    return output

                output = self._getRightNoteToken(current)
                if output:
                    return output

                current = current.nextToken(0)
        else:
            # start walking down the file until we hit a barline, looking left and right
            current = token.nextToken(0)
            while not current.isBarline:
                if current.isInterpretation or current.isComment:
                    current = current.nextToken(0)
                    continue

                output = self._getLeftNoteToken(current)
                if output:
                    return output

                output = self._getRightNoteToken(current)
                if output:
                    return output

                current = current.nextToken(0)

            # didn't find anything later in the measure, try earlier in the measure
            current = token.previousToken(0)
            while not current.isBarline:
                if current.isInterpretation or current.isComment:
                    current = current.previousToken(0)
                    continue

                output = self._getLeftNoteToken(current)
                if output:
                    return output

                output = self._getRightNoteToken(current)
                if output:
                    return output

                current = current.previousToken(0)

        return None


    '''
    //////////////////////////////
    //
    // HumdrumInput::getHairpinEnd --
    '''
    @staticmethod
    def _getHairpinEnd(token: HumdrumToken, endChar: str) -> HumdrumToken:
        if not token:
            return None

        token = token.getNextNonNullDataToken(0)

        while token:
            isBadToken: bool = False
            if endChar in token.text:
                return token

            for ch in token.text:
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

            token = token.getNextNonNullDataToken(0)

        return None

    def _processDirections(self, voice: m21.stream.Voice, token: HumdrumToken, staffIndex: int):
        # TODO: text directions
        pass

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
    def _getLayoutParameterWithDefaults(token: HumdrumToken, ns2: str, catKey: str,
                                        existsButEmptyValue: str,
                                        doesntExistValue: str = '') -> str:
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
    def staffLayerCounts(self) -> [int]:
        return [len(listOfLayersForStaff) for listOfLayersForStaff in self._layerTokens]

#         for i, listOfLayersForStaff in enumerate(self._layerTokens):
#             output[i] = len(listOfLayersForStaff)


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
    def _checkForInformalBreak(self, lineIdx: int):
        if lineIdx >= self.lineCount - 1:
            return

        firstTS: HumNum = self._lines[lineIdx].durationFromStart
        lineBreakIdx: int = -1
        pageBreakIdx: int = -1

        # look forward for informal breaks, up to first data, or first line where ts changes
        for i in range(lineIdx, self.lineCount):
            line = self._lines[i]
            if line.isData or line.durationFromStart != firstTS:
                break

            if not line.isGlobalComment:
                continue

            if line[0].text.startswith('!!linebreak:'):
                lineBreakIdx = i
                break

            if line[0].text.startswith('!!pagebreak:'):
                pageBreakIdx = i
                break

        if lineBreakIdx == -1 and pageBreakIdx == -1:
            # look backward for informal breaks, back to first data, or first line where ts changes
            for i in reversed(range(1, lineIdx)): # don't bother with line 0
                line = self._lines[i]
                if line.isData or line.durationFromStart != firstTS:
                    break

                if not line.isGlobalComment:
                    continue

                if line[0].text.startswith('!!linebreak:'):
                    lineBreakIdx = i
                    break

                if line[0].text.startswith('!!pagebreak:'):
                    pageBreakIdx = i
                    break

        if lineBreakIdx == -1 and pageBreakIdx == -1:
            return

        if lineBreakIdx > 0:
            self._m21BreakAtStartOfNextMeasure = m21.layout.SystemLayout(isNew = True)
        elif pageBreakIdx > 0:
            self._m21BreakAtStartOfNextMeasure = m21.layout.PageLayout(isNew = True)

    '''
    //////////////////////////////
    //
    // HumdrumInput::checkForLayoutBreak --
    '''
    def _checkForFormalBreak(self, lineIdx: int):
        if lineIdx >= self.lineCount - 1:
            return

        line: HumdrumLine = self._lines[lineIdx]

        if not line.isBarline:
            return

        token: HumdrumToken = line[0]
        group: str = token.layoutParameter('LB', 'g')
        if group:
            self._m21BreakAtStartOfNextMeasure = m21.layout.SystemLayout(isNew = True)
            return

        group: str = token.layoutParameter('PB', 'g')
        if group:
            self._m21BreakAtStartOfNextMeasure = m21.layout.PageLayout(isNew = True)
            return

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
                continue # start looking at startIdx + 1

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

    def _createScoreMetadata(self):
        # TODO: handle Humdrum vs. music21 metadata mismatches
        if not self._biblio:
            return # there is no metadata to be had

        m21Metadata = m21.metadata.Metadata()
        self.m21Stream.metadata = m21Metadata
        for k in self._biblio:
            v = self._biblio[k]
            if k in M21Convert.humdrumReferenceKeyToM21ContributorRole:
                contrib = m21.metadata.Contributor()
                contrib.role = M21Convert.humdrumReferenceKeyToM21ContributorRole[k]
                contrib.name = v
                print('key: {} -> {}, value: {}'.format(k, contrib.role, contrib.name))
                m21Metadata.addContributor(contrib)
            elif k.lower() in m21Metadata.workIdAbbreviationDict:
                print('key: {} -> {}, value: {}'.format(k, m21Metadata.workIdAbbreviationDict[k.lower()], v))
                m21Metadata.setWorkId(k, v)
            elif k == 'YEC': # electronic edition copyright
                print('key: {} -> {}, value: {}'.format(k, 'metadata.Copyright', v))
                m21Metadata.copyright = m21.metadata.Copyright(v)
            else:
                # We could add it to the m21Stream in some non-standard way (perhaps with a
                # Music21Object that is what we wish m21.metadata.Metadata was, with language
                # codes, all keys allowed, etc)
                pass
#                 print('unrecognized referenceKey: {}, value: {}'.format(k, v))
#                 print('unrecognized referenceKey: {}, value: {}'.format(k, v), file=sys.stderr)

    def _createStaffGroups(self):
        decoration: str = self.getReferenceValueForKey('system-decoration')
        success: bool = False
        if decoration:
            success: bool = self._processSystemDecoration(decoration)

        if not success: # no decoration, or decoration processing failed
            # Set a default decoration style depending on the staff count.
            if self.staffCount == 2:
                # If there are two staves, presume that it is for a grand staff
                # and a brace should be displayed, with all barlines crossing.
                self._processSystemDecoration('{(*)}')
            elif self.staffCount > 2:
                # If there are more than two staves then
                # add a bracket around the staves (barlines do not cross)
                self._processSystemDecoration('[*]')
            elif  self.staffCount == 1:
                # If there is one staff, then no extra decoration.
                pass
            else:
                pass # we can't get here because this method is never called with 0 staves

    '''
    //////////////////////////////
    //
    // HumdrumInput::getStaffNumberLabel -- Return number 13 in pattern *staff13.

        Searches tokens starting at spineStart, until a data token is found
    '''
    @staticmethod
    def _getStaffNumberLabel(spineStart: HumdrumToken) -> int:
        tok: HumdrumToken = spineStart
        while tok and not tok.isData:
            if not tok.isStaffInterpretation:
                tok = tok.nextToken(0) # stay left if there's a split
                continue

            staffNums = tok.staffNums
            if len(staffNums) > 0:
                return staffNums[0]

        return 0

    '''
    //////////////////////////////
    //
    // HumdrumInput::getPartNumberLabel -- Return number 2 in pattern *part2.

        Searches tokens starting at spineStart, until a data token is found
    '''
    @staticmethod
    def _getPartNumberLabel(spineStart: HumdrumToken) -> int:
        tok: HumdrumToken = spineStart
        while tok and not tok.isData:
            if not tok.isPart:
                tok = tok.nextToken(0) # stay left if there's a split
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
    def _getGroupNumberLabel(spineStart: HumdrumToken) -> int:
        tok: HumdrumToken = spineStart
        while tok and not tok.isData:
            if not tok.isGroup:
                tok = tok.nextToken(0) # stay left if there's a split
                continue
            return tok.groupNum
        return 0

    '''
    //////////////////////////////
    //
    // HumdrumInput::processStaffDecoration -- Currently only one level
    //    of bracing is allowed.  Probably allow remapping of staff order
    //    with the system decoration, and possible merge two kern spines
    //    onto a single staff (such as two similar instruments sharing
    //    a common staff).

        I factored this a little. It needs a lot more. --gregc
    '''
    def _processSystemDecoration(self, decoration: str) -> bool:
        if not decoration:
            return False

        trackList: [int] = []
        startTok: HumdrumToken
        for startTok in self._staffStarts:
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

        staffList = []          # just a list of staff numbers found in *staff interps
        trackToStaff = dict()   # key is track num, value is staff num
        trackToStaffStartIndex = dict() # key is track num, value is index into self._staffStarts

        classToStaves = dict()  # key is instrument class name, value is list of staff nums
        groupToStaves = dict()  # key is group num, value is list of staff nums
        partToStaves = dict()   # key is part num, value is list of staff nums

        staffToClass = dict()   # key is staff num, value is instrument class name
        staffToGroup = dict()   # key is staff num, value is group num
        staffStartIndexToGroup = dict() # key is index into self._staffStarts, value is group num
        staffToPart = dict()    # key is staff num, value is part num
        staffToStaffStartIndex = dict() # key is staff num, value is index into self._staffStarts

        for staffStartIndex, startTok in enumerate(self._staffStarts):
            staffNum: int = self._getStaffNumberLabel(startTok)
            groupNum: int = self._getGroupNumberLabel(startTok)
            partNum: int = self._getPartNumberLabel(startTok)
            trackNum: int = startTok.track
            instrumentClass: str = self._staffStates[staffStartIndex].instrumentClass

            # we require *staffN numbers to be present, or system-decoration can't work --gregc
            # (not strictly true, you could do tN (trackNum) style decoration, and we should
            # allow that)
            if staffNum <= 0:
                return False

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

        # Expand groupings into staves.  The d variable contains the expansions
        # and the decoration variable contains the original decoration string.
        d: str = decoration

        # Instrument class expansion to staves:
        # e.g. '{(bras)}' might expand to '{(s3,s4,s5)}'
        if classToStaves:
            for iClassPattern in classToStaves:
                replacement: str = ''
                for i, sNum in enumerate(classToStaves[iClassPattern]):
                    replacement += 's' + str(sNum)
                    if i < len(classToStaves[iClassPattern]) - 1:
                        replacement += ','
                d = re.sub(iClassPattern, replacement, d)

        # Group number expansion to staves:
        if groupToStaves:
            # example:   {(g1}} will be expanded to {(s1,s2,s3)} if
            # group1 is given to staff1, staff2, and staff3.
            for gNum in groupToStaves:
                gNumStr: str = 'g' + str(gNum)
                replacement: str = ''
                for i, sNum in enumerate(groupToStaves[gNum]):
                    replacement += 's' + str(sNum)
                    if i < len(groupToStaves[gNum]) - 1:
                        replacement += ','
                d = re.sub(gNumStr, replacement, d)

        # Part number expansion to staves:
        if partToStaves:
            # example:   {(p1}} will be expanded to {(s1,s2)} if
            # part1 is given to staff1 and staff2.
            for pNum in partToStaves:
                pNumStr: str = 'p' + str(pNum)
                replacement: str = ''
                for i, sNum in enumerate(partToStaves[pNum]):
                    replacement += 's' + str(sNum)
                    if i < len(partToStaves[pNum]) - 1:
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
            replacement: str = ''
            for i, trackNum in enumerate(trackList):
                replacement += 't' + str(trackNum)
                if i < len(trackList) - 1:
                    replacement += ','
            d = re.sub(r'\*', replacement, d)
            hasStar = True

        d = re.sub(r'\*', '', d) # gets rid of any remaining '*' characters
        if not d:
            return False
        '''
        print('INPUT DECORATION: {}'.format(decoration), file=sys.stderr)
        print('       PROCESSED: {}'.format(d), file=sys.stderr)
        '''

        decoStaffNums: [int] = []
        for m in re.finditer(r's(\d+)', d):
            if m:
                decoStaffNums.append(int(m.group(1)))

        for decoStaffNum in decoStaffNums:
            if decoStaffNum not in staffList:
                # The staff number in the decoration string
                # is not present in the list so remove it.
                staffNumPattern = 's' + str(decoStaffNum)
                # assert that if there is a next char, it is not a digit (don't match 's1' to 's10')
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
        OPENS  = ['(', '{', '[', '<']
        CLOSES = [')', '}', ']', '>']
        stack: [tuple] = []             # list of (d string index, paren char)
        pairing: [int] = [-1] * len(d)

        for i, ch in enumerate(d):
            if ch in OPENS:
                stack.append((i, ch))
            elif ch in CLOSES:
                if not stack: # if stack is empty
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
                stack.pop() # removes last element of stack, which we just consumed

        if stack: # is not empty
            isValid = False

        '''
        # print analysis:
        for i, ch in enumerate(d):
            print("d[{}] =\t{} pairing: {}".format(i, ch, pairing[i]))
        '''

        if not isValid:
            return False

        if not pairing: # if pairing is empty
            return False

        # start setting up the entire system via one or more m21.layout.StaffGroup objects
        staffGroups: [m21.layout.StaffGroup] = [None] * len(d) # sparse, only at '{[<', and index 0 and len-1
        barGroups: [[int]] = [[]] # starts out containing one empty list
        groupStyle: [str] = [' '] # starts with a single string (a space)
        isStaffIndicator: bool = False
        isTrackIndicator: bool = False
        value: int = 0
        grouper: bool = False
        gLevel: int = 0

        skipNext: bool = False
        for i, dCharI in enumerate(d):
            if skipNext:
                skipNext = False
                continue

            if dCharI in '{[<':
                if not grouper:
                    if not barGroups[-1]: # is empty
                        groupStyle[-1] = dCharI
                    else:
                        groupStyle.append(dCharI)
                        barGroups.append([])
                groupStyle[-1] = dCharI
                if i < len(d) - 1:
                    if d[i + 1] == '(':
                        groupStyle[-1] += '('
                        skipNext = True # we've already handled it
                grouper = True
                gLevel += 1
            elif dCharI == '(':
                # a bit simpler than '{[<' above...
                groupStyle[-1] = '('
                grouper = True
            elif dCharI in '}]>':
                groupStyle.append(' ')
                barGroups.append([])
                gLevel -= 1
                if gLevel == 0:
                    grouper = False
            elif dCharI == ')':
                if len(groupStyle[-1]) > 1 and groupStyle[-1][1] == '(':
                    # ignore since it does not indicate a group (double open-paren?)
                    pass
                else:
                    barGroups.append([])
                    groupStyle.append(' ')
                gLevel -= 1
                if gLevel == 0:
                    grouper = False
            elif dCharI == 's':
                isStaffIndicator = True
                isTrackIndicator = False
            elif dCharI == 't':
                isStaffIndicator = False
                isTrackIndicator = True
            elif dCharI.isdigit():
                if value < 0:
                    value = 0
                value = (value * 10) + int(dCharI)
                if i == len(d) - 1 or not d[i + 1].isdigit(): # if end of digit chars
                    if isStaffIndicator:
                        value = staffToStaffStartIndex.get(value, -1)
                    elif isTrackIndicator:
                        value = trackToStaffStartIndex.get(value, -1)

                    isStaffIndicator = False
                    isTrackIndicator = False
                    if value < 0:
                        # spine does not exist in self._staffStarts (thus it isn't in the score): skip
                        value = 0
                        continue
                    barGroups[-1].append(value)
                    value = 0

        if barGroups and not barGroups[-1]: #if barGroups is not empty, but last barGroup is empty
            barGroups.pop() # remove that last empty barGroup

        '''
        print('BAR GROUPS')
        for i, barGroup in enumerate(barGroups):
            print('\tgroupStyle[]={}\tgroup={}:\t'.format(groupStyle[i], i), end='')
            for val in barGroup:
                print(' {}'.format(val), end='')
            print('') # endLine
        '''

        # Pull out all non-zero staff groups:
        newGroups: [[int]] = []
        newStyles: [str] = []
        for i, barGroup in enumerate(barGroups):
            if not barGroup: # if barGroup is empty
                continue
            newGroups.append(barGroup)
            newStyles.append(groupStyle[i])

        '''
        print('NEW GROUPS')
        for i, newGroup in enumerate(newGroups):
            print('\tgroupStyle[]={}\tgroup={}:\t'.format(newStyles[i], i), end='')
            for val in newGroup:
                print(' {}'.format(val), end='')
            print('') # endLine
        '''

        # Check to see that all staffstarts are represented in system decoration;
        # otherwise, declare that it is invalid and print a simple decoration.
        found: [int] = [0] * self.staffCount
        if hasStar:
            found = [1] * len(found)
        else:
            for newGroup in newGroups:
                for val in newGroup:
                    found[val] += 1

            for i, foundCount in enumerate(found):
                if foundCount != 1:
                    print('I:{}\t=\t{}'.format(i, foundCount), file=sys.stderr)
                    isValid = False
                    break

        if not isValid:
            print("DECORATION IS INVALID:", decoration, file=sys.stderr)
            if d != decoration:
                print("\tSTAFF VERSION:", d)

            # iohumdrum.cpp unconditionally adds a full-score brace here, but I'm going
            # to fail instead, and let the failure handling put some default bracing
            # in place.
            return False

        # Build system groups based on system decoration instructions (FINALLY!)
        for i, newGroup in enumerate(newGroups):
            if not newGroup: # it's empty? weird, skip it.
                continue

            groupNum = staffStartIndexToGroup.get(newGroup[0], 0)
            staffGroups[i] = self._processStaffGroupDecoration(
                                        groupNum, newGroup, newStyles[i])

        for staffGroup in staffGroups:
            if staffGroup is None: # we've reached the end (the array is longer than it needs to be)
                break
            self.m21Stream.insert(0, staffGroup)

        return True

    '''
        _processStaffGroupDecoration
    '''
    def _processStaffGroupDecoration(self, groupNum: int, group: [int], style: str) -> m21.layout.StaffGroup:
        groupName: str = None
        groupNameTok: HumdrumToken = None
        groupAbbrev: str = None
        groupAbbrevTok: HumdrumToken = None

        groupParts: [m21.stream.Part] = []
        for i, ss in enumerate(self._staffStates): # these are ordered by staffStartIndex
            if i in group:
                groupParts.append(ss.m21Part)

        sg: m21.layout.StaffGroup =  m21.layout.StaffGroup(groupParts)

        if style and style[0] in '[{<':
            if len(group) >= 1:
                sg.symbol = M21Convert.humdrumDecoGroupStyleToM21GroupSymbol[style[0]]
            sg.barTogether = '(' in style
        elif style and style[0] == '(':
            sg.barTogether = True

        if groupNum > 0:
            groupName = self._groupNames.get(groupNum)
            #groupNameTok = self._groupNameTokens.get(groupNum)
            groupAbbrev = self._groupAbbrevs.get(groupNum)
            #groupAbbrevTok = self._groupAbbrevTokens.get(groupNum)
            if groupAbbrev and groupAbbrevTok:
                sg.abbreviation = groupAbbrev
                # sg.abbreviation.humdrumLocation = groupAbbrevTok # for debugging...
            if groupName and groupNameTok:
                sg.name = groupName
                #sg.name.humdrumLocation = groupNameTok # for debugging...

        return sg

    '''
    //////////////////////////////
    //
    // HumdrumInput::fillPartInfo --
    '''
    def _createPart(self, partStartTok: HumdrumToken, partNum: int, partCount: int): # partNum is 1-based
        ss: StaffStateVariables = self._staffStates[partNum - 1]
        ss.m21Part = m21.stream.Part()
        self.m21Stream.insert(0, ss.m21Part)

        group: int = self._getGroupNumberLabel(partStartTok)

        clefTok: HumdrumToken = None
        partTok: HumdrumToken = None
        staffTok: HumdrumToken = None
        staffScaleTok: HumdrumToken = None
        striaTok: HumdrumToken = None
        keySigTok: HumdrumToken = None
        keyTok: HumdrumToken = None
        timeSigTok: HumdrumToken = None
        meterSigTok: HumdrumToken = None
#         primaryMensuration: str = ''

        iName: str = None
        iCode: str = None
        iClassCode: str = None
        iAbbrev: str = None
        iTranspose: str = None
        iTrans40: int = None

        token: HumdrumToken = partStartTok
        while token and not token.ownerLine.isData: # just scan the interp/comments before first data
            if token.isClef:
                if clefTok:
                    if clefTok.clef == token.clef:
                        # there is already a clef found, and it is the same
                        # as this one, so ignore the second one.
                        pass
                    else:
                        # mark clef as a clef change to print in the layer
                        token.setValue('auto', 'clefChange', True)
#Q:                        self._markOtherClefsAsChange(token) might be a no-op for music21

                    token = token.nextToken(0) # stay left if there's a split
                    continue

                # first clef (not a clef change)
                if token.clef[-1].isdigit() or token.clef[0] == 'X':
                    # allow percussion clef '*clefX' to not have a line number, since it is unpitched.
                    clefTok = token
            elif token.isOriginalClef:
                if token.originalClef[0].isdigit():
                    self._oclefs.append((partNum, token))
            elif token.isPart:
                partTok = token
            elif token.isStaffInterpretation:
                staffTok = token
            elif token.isStria: # num lines per staff (usually 5)
                striaTok = token
            elif token.isOriginalMensurationSymbol:
                self._omets.append((partNum, token))
            elif token.isKeySignature:
                keySigTok = token
            elif token.isOriginalKeySignature:
                self._okeys.append((partNum, token))
            elif token.isKeyDesignation:  # e.g. *A-: or *d:dor
                keyTok = token
            elif token.isScale:
                staffScaleTok = token
            elif token.isSize:
                staffScaleTok = token
#             elif token.isTranspose:
#                 ss.wasTransposedBy = Convert.transToBase40(token.transpose)

            elif token.isInstrumentTranspose:
                iTranspose = token.instrumentTranspose
            elif token.isInstrumentGroupAbbreviation: # e.g. *I''bras is Brass
                if partCount > 1:
                    # Avoid encoding the part group abbreviation when there is only one
                    # part in order to suppress the display of the abbreviation.
                    groupAbbrev: str = token.instrumentGroupAbbreviation
                    if group >= 0 and groupAbbrev != '':
                        self._groupAbbrevs[group] = groupAbbrev
                        self._groupAbbrevTokens[group] = token
            elif token.isInstrumentAbbreviation: # part (instrument) abbreviation, e.g. *I'Vln.
                if partCount > 1:
                    # Avoid encoding the part abbreviation when there is only one
                    # part in order to suppress the display of the abbreviation.
                    iAbbrev = token.instrumentAbbreviation
            elif token.isInstrumentGroupName: # group label, e.g. *I""Strings
                groupName: str = token.instrumentGroupName
                if group > 0 and groupName != '':
                    self._groupNames[group] = groupName
                    self._groupNameTokens[group] = token
            elif token.isInstrumentName: # part (instrument) label
                iName = token.instrumentName
            elif token.isInstrumentCode: # instrument code, e.g. *Iclars is Clarinet
                iCode = token.instrumentCode
            elif token.isInstrumentClassCode: # instrument class code, e.g. *ICbras is BrassInstrument
                iClassCode = token.instrumentClassCode
                ss.instrumentClass = iClassCode
            elif token.isMensurationSymbol:
                meterSigTok = token
            elif token.isTimeSignature:
                timeSigTok = token
            elif 'acclev' in token.text: # '*acclev', '*acclev:', '*Xacclev', etc
                self._storeAcclev(token, partNum - 1) # for **mens accidental processing
            elif token.text.startswith('*stem'):
                self._storeStemInterpretation(token, partNum - 1, 1) # layerNum == 1

# When different parts have different mensurations at the same time, a global comment can be added at that point in the score to indicate the primary mensuration for performance tempo determination. For example, if three out of for parts are in Cut-C and one is in C, then the global record starting with "!!primary-mensuration:" and followed by the main mensuration used to determine the tempo of the following music. For example:
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

            token = token.nextToken(0) # stay left if there's a split

        # now process the stuff you gathered, putting important info in ss
        # and in ss.m21Part (created above)

        # Make an instrument name if we need to...
        if iName is None:
            if iCode is not None:
                iName = getInstrumentNameFromCode(iCode, iTranspose)
            elif iClassCode is not None:
                iName = getInstrumentNameFromClassCode(iClassCode)
            elif iAbbrev is not None:
                iName = iAbbrev
            elif iTrans40 is not None:
                iName = 'UnknownTransposingInstrument'

        # create m21Instrument, and insert it into ss.m21Part
        if iName:
            m21Inst: m21.instrument.Instrument = None
            try:
                m21Inst = m21.instrument.fromString(iName) # parses recognized names, sets extra fields
            except m21.instrument.InstrumentException:
                pass

            m21Inst = m21.instrument.Instrument(iName)
            if iAbbrev and iAbbrev != iName:
                m21Inst.instrumentAbbreviation = iAbbrev
            if iTrans40:
                m21Inst.transposition = m21.musedata.base40.base40DeltaToInterval(iTrans40)
            ss.m21Part.insert(0, m21Inst)

        # short-circuit *clef with *oclef for **mens data
        if partStartTok.isMens:
            if self._oclefs and partNum == self._oclefs[-1][0]:
                clefTok = self._oclefs[-1][1]

        # short-circuit *met with *omet for **mens data
        if partStartTok.isMens:
            if self._omets and partNum == self._omets[-1][0]:
                meterSigTok = self._omets[-1][1]

        if staffTok:
            # search for a **dynam before the next **kern spine, and set the
            # dynamics position to centered if there is a slash in the *staff1/2 string.
            # In the future also check *part# to see if there are two staves for a part
            # with no **dynam for the lower staff (infer to be a grand staff).
            dynamSpine: HumdrumToken = self.associatedDynamSpine(staffTok)
            if dynamSpine \
                    and dynamSpine.isStaffInterpretation \
                    and '/' in dynamSpine.text:
                # the dynamics should be placed between
                # staves: the current one and the one below it.
                ss.dynamPos = 0
                ss.dynamStaffAdj = 0
                ss.dynamPosDefined = True

        if partTok:
            pPartNum: int = 0   # from *part token
            dPartNum: int = 0   # from *part token in associated dynam spine
            lPartNum: int = 0   # from *part token in next left staff spine
            dynamSpine: HumdrumToken = self.associatedDynamSpine(partTok)
            if dynamSpine:
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
            ss.firstM21Clef = m21Clef # hang on to this until we have a first measure to put it in
            ss.mostRecentlySeenClefTok = clefTok
        # else:
        #     We won't do any getAutoClef stuff, music21 does that for you.

        #if transpose: Already handled above where we set wasTransposedBy...
        #if iTranspose, iAbbrev, hasLabel: Already handled in instrument prep above.

        if keySigTok:
            m21KeySig = M21Convert.m21KeySignature(keySigTok, keyTok)
            ss.firstM21KeySig = m21KeySig # hang on to this until we have a first measure to put it in

        m21TimeSig = None
        if timeSigTok:
            m21TimeSig = M21Convert.m21TimeSignature(timeSigTok, meterSigTok)

        ss.firstM21TimeSig = m21TimeSig # hang on to this until we have a first measure to put it in
#         if partStartTok.isMens:
#             if self._isBlackNotation(partStartTok):
#                 # music21 doesn't (yet) really support black mensural notation
#             else:
#                 # music21 doesn't (yet) really support white mensural notation, either
    '''
    //////////////////////////////
    //
    // HumdrumInput::storeStemInterpretation --
    '''
    def _storeStemInterpretation(self, value: str, staffIndex: int, layerIndex: int):
        if 'stem' not in value:
            return

        ss: StaffStateVariables = self._staffStates[staffIndex]
        ending: str = value[6:] # everything after '*stem:'

        if ending in 'x/\\':
            ss.stemType[layerIndex] = ending
        else:
            ss.stemType[layerIndex] = 'X'

    '''
    //////////////////////////////
    //
    // HumdrumInput::storeAcclev -- Used for **mens accidental conversion to @accid+@edit or @accid.ges.
    '''
    def _storeAcclev(self,  value: str, staffIndex: int):
        if 'acclev' not in value:
            return

        ss: StaffStateVariables = self._staffStates[staffIndex]

        if len(value) > len('*acclev:') and value.startswith('*acclev:'):
            state: str = value[8:] # everything after the colon
            if state:
                if state[0].isdigit:
                    ss.acclev = int(state[0])
                elif state == 'YY':
                    ss.acclev = 1
                elif state == 'Y':
                    ss.acclev = 2
                elif state == 'yy':
                    ss.acclev = 3
                elif state == 'y':
                    ss.acclev = 4
        elif value == '*acclev:':
            ss.acclev = 0
        elif value == '*acclev':
            ss.acclev = 0
        elif value == '*Xacclev':
            ss.acclev = 0

    '''
    //////////////////////////////
    //
    // HumdrumInput::getAssociatedDynamSpine -- Return the first **dynam
    //     spine before another staff spine is found; or return NULL token
    //     first;

        We are searching to the right...
    '''
    @staticmethod
    def associatedDynamSpine(token: HumdrumToken) -> HumdrumToken:
        if token is None:
            return None

        current: HumdrumToken = token.nextFieldToken
        while current:
            if current.isStaffDataType: # if current has reached a **kern or **mens spine
                break                   # we're done looking
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
    def previousStaffToken(token: HumdrumToken) -> HumdrumToken:
        if token is None:
            return None

        track: int = token.track
        ttrack: int = -1
        current: HumdrumToken = token.previousFieldToken
        while current:
            if not current.isStaffDataType: # step over non-staff spines
                current = current.previousFieldToken
                continue

            ttrack = current.track
            if ttrack == track: # step over anything in the same track as the starting token
                current = current.previousFieldToken
                continue

            break # current is the first token (in a staff spine) to the left that isn't in our track

        if current is None:
            return None

        # keep going to find the first subspine of that track (ttrack)
        firstSubspine: HumdrumToken = current
        current = current.previousFieldToken
        while current:
            if current.track == ttrack:
                firstSubspine = current
                current = current.previousFieldToken
                continue # BUGFIX: This "continue" was missing
            break

        return firstSubspine

    '''
    //////////////////////////////
    //
    // HumdrumInput::addMidiTempo --
    '''
    def _createInitialTempo(self):
        foundTempo: bool = False
        token = self._staffStarts[0]
        while token is not None and not token.isData: # just looking at the first interps and comments
            if not token.isTempo:
                token = token.nextToken(0)
                continue

            # It's a tempo indication (*MM), so we're done
            self._initialTempoName = token.tempoName
            self._initialTempoBPM = token.tempoBPM
            foundTempo = self._initialTempoName != '' or self._initialTempoBPM > 0.0
            break

        # if we didn't find a *MM, look  again for !!!OMD (tempo name)
        if not foundTempo:
            omdValue: str = None
            for line in self._lines:
                if line.isData:
                    break
                if line[0].text.startswith('!!!OMD:'):
                    omdValue = line.referenceValue
                    break

            if omdValue:
                # some !!!OMD values are not tempos, so convert to BPM to see if we get > 0
                if Convert.tempoNameToBPM(omdValue, self._timeSignaturesWithLineIdx[0]) > 0:
                    foundTempo = True
                    self._initialTempoName = omdValue
                    # don't imply the BPM number was specified, let others default as they will
                    self._initialTempoBPM = 0.0

        # set up music21 stuff
        m21Tempo = None
        if foundTempo:
            if self._initialTempoBPM > 0 and self._initialTempoName:
                m21Tempo = m21.tempo.MetronomeMark(
                                text = self._initialTempoName,
                                number = self._initialTempoBPM)
            elif self._initialTempoBPM > 0:
                m21Tempo = m21.tempo.MetronomeMark(number = self._initialTempoBPM)
            elif self._initialTempoName:
                m21Tempo = m21.tempo.TempoText(self._initialTempoName)

        if m21Tempo:
            self.m21Stream.insert(0, m21Tempo)

    '''
    //////////////////////////////
    //
    // HumdrumInput::prepareSections --
    '''
    def _prepareSections(self):
        self._sectionLabels = [None] * self.lineCount
        self._numberlessLabels = [None] * self.lineCount

        secName: HumdrumToken = None
        noNumName: HumdrumToken = None

        for i, line in enumerate(self._lines):
            self._sectionLabels[i] = secName
            self._numberlessLabels[i] = noNumName

            if not line.isInterpretation:
                continue

            if not line[0].text.startswith('*>'):
                continue

            if '[' in line[0].text:
                # ignore expansion lists
                continue

            secName = line[0]
            self._sectionLabels[i] = secName

            # work backward until you hit a line of data, copying
            # this sectionLabel onto those previous comment and
            # interp lines --gregc
            for j in reversed(range(0, i)):
                if self._lines[j].isData:
                    break
                self._sectionLabels[j] = self._sectionLabels[i]

            if not secName.text[-1].isdigit():
                noNumName = secName
                self._numberlessLabels[i] = noNumName # BUGFIX:
                # work backward until you hit a line of data, copying
                # this numberlessLabel onto those previous comment and
                # interp lines --gregc
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


    '''
    //////////////////////////////
    //
    // HumdrumInput::prepareVerses -- Assumes that m_staffstarts has been
    //      filled already.
    '''
    def _prepareLyrics(self):
        if self.staffCount == 0:
            return

        for i, startTok in enumerate(self._staffStarts):
            line: HumdrumLine = startTok.ownerLine
            fieldIdx = startTok.fieldIndex
            for j in range(fieldIdx+1, line.tokenCount):
                if line[j].isStaffDataType:
                    break # we're done looking for associated lyrics spines

                if line[j].isDataType('**text') \
                        or line[j].isDataType('**silbe') \
                        or line[j].dataType.text.startswith('**vdata') \
                        or line[j].dataType.text.startswith('**vvdata'):
                    self._staffStates[i].hasLyrics = True

    def _calculateStaffStartsIndexByTrack(self):
        self._staffStartsIndexByTrack = [-1] * (self.maxTrack + 1)
        for i, startTok in enumerate(self._staffStarts):
            self._staffStartsIndexByTrack[startTok.track] = i

    def _analyzeSpineDataTypes(self):
        staffIndex: int = -1
        for startTok in self.spineStartList:
            if startTok.isDataType('**kern'):
                staffIndex += 1
            elif startTok.isDataType('**mxhm'):
                self._hasHarmonySpine = True
            elif startTok.isDataType('**fing'):
                self._hasFingeringSpine = True
            elif startTok.isDataType('**string'):
                self._hasStringSpine = True
            elif startTok.isDataType('**mens'):
                staffIndex += 1
                self._hasMensSpine = True
            elif startTok.isDataType('**harm'):
                self._hasHarmonySpine = True
            elif startTok.isDataType('**rhrm'): # **recip + **harm
                self._hasHarmonySpine = True
            elif startTok.dataType.text.startswith('**cdata'):
                self._hasHarmonySpine = True
            elif startTok.isDataType('**color'):
                self._hasColorSpine = True
            elif startTok.isDataType('**fb') \
                    or startTok.isDataType('**Bnum'): # older name
                self._hasFiguredBassSpine = True
                if staffIndex >= 0:
                    self._staffStates[staffIndex].figuredBassState = -1
                    self._staffStates[staffIndex].isStaffWithFiguredBass = True
            elif startTok.isDataType('**fba'):
                self._hasFiguredBassSpine = True
                if staffIndex >= 0:
                    self._staffStates[staffIndex].figuredBassState = +1
                    self._staffStates[staffIndex].isStaffWithFiguredBass = True

    '''
    //////////////////////////////
    //
    // HumdrumInput::hasAboveParameter -- true if has an "a" parameter or has a "Z" parameter set to anything.
    '''
    @staticmethod
    def _hasAboveParameter(token: HumdrumToken, ns2: str) -> bool:
        lcount: int = token.linkedParameterSetCount
        if lcount == 0:
            return False

        for p in range(0, lcount):
            hps: HumParamSet = token.getLinkedParameterSet(p)
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

    '''
    //////////////////////////////
    //
    // HumdrumInput::hasBelowParameter -- true if has an "b" parameter or has a "Y" parameter set to anything.
    '''
    @staticmethod
    def _hasBelowParameter(token: HumdrumToken, ns2: str) -> bool:
        lcount: int = token.linkedParameterSetCount
        if lcount == 0:
            return False

        for p in range(0, lcount):
            hps: HumParamSet = token.getLinkedParameterSet(p)
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

    '''
    //////////////////////////////
    //
    // HumdrumInput::hasCenterParameter -- true if has a "c" parameter is present with optional staff adjustment.
    '''
    @staticmethod
    def _hasCenterParameter(token: HumdrumToken, ns2: str, staffAdj: int) -> tuple: # (hasCenter, newStaffAdj))
        lcount: int = token.linkedParameterSetCount
        if lcount == 0:
            return (False, staffAdj)

        for p in range(0, lcount):
            hps: HumParamSet = token.getLinkedParameterSet(p)
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
                        staffAdj = int(paramVal)
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
            hps: HumParamSet = token.getLinkedParameterSet(p)
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
