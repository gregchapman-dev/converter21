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

import sys
import re
from typing import Union
from fractions import Fraction
import music21 as m21

from humdrum import HumNum
from humdrum import HumdrumToken
from humdrum import Convert

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
    def m21FontStyleFromFontStyle(fontStyle: str) -> str:
        if fontStyle == 'bold-italic':
            return 'bolditalic'
        return fontStyle

    '''
        Everything below this line converts from M21 to humdrum

        kernTokenStringFromBlah APIs actually return two things: the kernTokenString and an
        optional list of layout strings (which will need to be inserted before the token).
        The kernPostfix, kernPrefix, and kernPostfixAndPrefix APIs also return an additional
        optional list of layout strings.
    '''

    @staticmethod
    def kernTokenStringFromM21GeneralNote(m21GeneralNote: m21.note.GeneralNote, owner=None) -> (str, [str]):
        if 'Unpitched' in m21GeneralNote.classes:
            return M21Convert.kernTokenStringFromM21Unpitched(m21GeneralNote, owner)

        if 'Rest' in m21GeneralNote.classes:
            return M21Convert.kernTokenStringFromM21Rest(m21GeneralNote)

        if 'Chord' in m21GeneralNote.classes:
            return M21Convert.kernTokenStringFromM21Chord(m21GeneralNote, owner)

        if 'Note' in m21GeneralNote.classes:
            # Work from the note's pitch
            return M21Convert.kernTokenStringFromM21Note(m21GeneralNote, owner)

        # Not a GeneralNote (Chord, Note, Rest, Unpitched).
        return ('', [])

    @staticmethod
    def kernTokenStringFromM21Unpitched(m21Unpitched: m21.note.Unpitched, owner=None) -> (str, [str]):
        # 888: kernTokenStringFromM21Unpitched needs implementation
        pass

    @staticmethod
    def kernTokenStringFromM21Rest(m21Rest: m21.note.Rest) -> (str, [str]):
        pitch: str = 'r' # "pitch" of a rest is 'r'
        postfix: str = M21Convert.kernPostfixFromM21Rest(m21Rest)
        layouts: [str] = []

        token: str = pitch + postfix

        return (token, layouts)

    @staticmethod
    def kernPostfixFromM21Rest(m21Rest: m21.note.Rest) -> (str, [str]):
        postfix: str = ''
        layouts: [str] = []

        # rest postfix possibility 1: pitch (for vertical positioning)
        if m21Rest.stepShift != 0:
            # postfix needs a pitch that matches the stepShift
            clef: m21.clef.Clef = m21Rest.getContextByClass('Clef')
            if clef is not None:
                baseline: int = clef.lowestLine
                midline: int = baseline + 4
                pitchNum: int = midline + m21Rest.stepShift
                kernPitch: str = Convert.base7ToKern(pitchNum)
                postfix += kernPitch

        # rest postfix possibility 2: invisibility
        postfix += M21Convert._getKernInvisibilityFromGeneralNote(m21Rest)

        return (postfix, layouts)

    @staticmethod
    def kernTokenStringFromM21Note(m21Note: m21.note.Note, owner=None) -> (str, [str]):
        prefix: str = ''
        recip: str = M21Convert.kernRecipFromM21Duration(m21Note.duration)
        pitch: str = M21Convert.kernPitchFromM21Pitch(m21Note.pitch, owner)
        postfix: str = ''
        layouts: [str] = []
        prefix, postfix, layouts = M21Convert.kernPrefixAndPostfixFromM21Note(m21Note)

        token: str = prefix + recip + pitch + postfix
        return (token, layouts)

    @staticmethod
    def kernPrefixAndPostfixFromM21Note(m21Note: m21.note.Note) -> (str, str, [str]):
        prefix: str = ''
        postfix: str = ''
        layouts: [str] = []

        # prefix/postfix possibility 1: ties
        if m21Note.tie:
            tieStyle: str = m21Note.tie.style
            tiePlacement: str = m21Note.tie.placement
            tieType: str = m21Note.tie.type
            if tieType == 'start':
                prefix += '['
            elif tieType == 'stop':
                postfix += ']'
            elif tieType == 'continue':
                prefix += '_'

            if tieType in ('start', 'continue'):
                if tieStyle == 'hidden':
                    prefix += 'y'
                elif tieStyle == 'dotted':
                    layouts.append('!LO:T:dot') # for a chord note, this will end up as '!LO:T:n=3:dot'
                elif tieStyle == 'dashed':
                    layouts.append('!LO:T:dash') # for a chord note, this will end up as '!LO:T:n=3:dash'

                if tieStyle != 'hidden':
                    if tiePlacement == 'above':
                        prefix += '>' # no need to report this up, since we always have '>' RDF signifier
                    elif tiePlacement == 'below':
                        prefix += '<' # no need to report this up, since we always have '<' RDF signifier

        # prefix/postfix possibility 2: slurs
        slurStarts: str = ''
        slurStops: str = ''
        slurStarts, slurStops = M21Convert._getKernSlurStartsAndStopsFromGeneralNote(m21Note)
        prefix += slurStarts
        postfix += slurStops

        # postfix possibility: invisible note
        postfix += M21Convert._getKernInvisibilityFromGeneralNote(m21Note)

        return (prefix, postfix, layouts)

    @staticmethod
    def _getKernSlurStartsAndStopsFromGeneralNote(m21GeneralNote: m21.note.GeneralNote) -> (str, str):
        # FUTURE: Handle crossing (non-nested) slurs during export to humdrum '&('
        outputStarts: str = ''
        outputStops: str = ''

        spanners: [m21.spanner.Spanner] = m21GeneralNote.getSpannerSites()
        slurStarts: [str] = [] # 'above', 'below', or None
        slurEndCount: int = 0

        for slur in spanners:
            if 'Slur' not in slur.classes:
                continue
            if slur.first == m21GeneralNote:
                slurStarts.append(slur.placement)
            elif slur.last == m21GeneralNote:
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
        if m21GeneralNote.style.hideObjectOnPrint:
            return 'yy'
        if 'SpacerRest' in m21GeneralNote.classes: # deprecated, but if we see it...
            return 'yy'
        return ''

    @staticmethod
    def kernTokenStringFromM21Chord(m21Chord: m21.chord.Chord, owner=None) -> (str, [str]):
        pitchPerNote: [str] = M21Convert.kernPitchesFromM21Chord(m21Chord, owner)
        recip: str = M21Convert.kernRecipFromM21Duration(m21Chord.duration) # same for each
        prefixPerNote: [str] = []
        postfixPerNote: [str] = []
        layoutsForChord: [str] = []

        prefixPerNote, postfixPerNote, layoutsForChord = \
            M21Convert.kernPrefixesAndPostfixesFromM21Chord(m21Chord)

        token: str = ''
        for i, (prefix, pitch, postfix) in enumerate(zip(prefixPerNote, pitchPerNote, postfixPerNote)):
            if i > 0:
                token += ' '
            token += prefix + recip + pitch + postfix

        return token, layoutsForChord

    @staticmethod
    def kernPitchesFromM21Chord(m21Chord: m21.chord.Chord, owner=None) -> [str]:
        pitches: [str] = []
        for m21Note in m21Chord:
            pitch: str = M21Convert.kernPitchFromM21Pitch(m21Note.pitch, owner)
            pitches.append(pitch)
        return pitches

    @staticmethod
    def kernPrefixesAndPostfixesFromM21Chord(m21Chord: m21.chord.Chord) -> (str, str, [str]):
        prefixPerNote:   [str] = [] # one per note
        postfixPerNote:  [str] = [] # one per note
        layoutsForChord: [str] = [] # 0 or more per note

        for noteIdx, m21Note in enumerate(m21Chord):
            prefix:  str   = '' # one for this note
            postfix: str   = '' # one for this note
            layouts: [str] = [] # 0 or more for this note

            prefix, postfix, layouts = M21Convert.kernPrefixAndPostfixFromM21Note(m21Note)

            # put them in prefixPerNote, postFixPerNote, and layoutsForChord
            prefixPerNote.append(prefix)
            postfixPerNote.append(postfix)
            if layouts:
                for layout in layouts:
                    # we have to add ':n=3' to each layout, where '3' is one-based (i.e. noteIdx+1)
                    numberedLayout: str = M21Convert._addNoteNumberToLayout(layout, noteIdx+1)
                    layoutsForChord.append(numberedLayout)

        return (prefixPerNote, postfixPerNote, layoutsForChord)

    @staticmethod
    def _addNoteNumberToLayout(layout: str, noteNum: int) -> str:
        # split at colons
        params: [str] = layout.split(':')
        insertAtIndex: int = len(params) - 2
        params.insert(insertAtIndex, 'n={}'.format(noteNum))
        output: str = ':'.join(params)
        return output

    '''
    //////////////////////////////
    //
    // MxmlEvent::getRecip -- return **recip value for note/rest.
    //   e.g. recip == '4' for a quarter note duration, recip == '2' for a half note duration.
        Code that converts to '00' etc came from Tool_musicxml2hum::addEvent. --gregc
    '''
    @staticmethod
    def kernRecipFromM21Duration(m21Duration: m21.duration.Duration) -> str:
        dur: HumNum = m21Duration.quarterLength / 4 # convert to whole-note units
        dots: str = ''
        percentExists = False

        # compute number of dots from dur
        if dur.numerator == 1:
            pass # no dots needed
        else:
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

        out: str = str(dur.denominator)
        if dur.numerator != 1:
            out += '%' + str(dur.numerator)
            percentExists = True
        out += dots

        # Check for a few specific 'n%m' recips that can be converted to '00' etc
        if percentExists:
            m = re.search(out, r'(\d+)%(\d+)(\.*)')
            if m:
                first: int = int(m.group(1))
                second: int = int(m.group(2))
                dots: str = m.group(3)
                if not dots:
                    if first == 1 and second == 2:
                        out.replace('1%2', '0')
                    elif first == 1 and second == 4:
                        out.replace('1%4', '00')
                    elif first == 1 and second == 3:
                        out.replace('1%3', '0.')
                else:
                    if first == 1 and second == 2:
                        original: str = '1%2' + dots
                        replacement: str = '0' + dots
                        out.replace(original, replacement)

        return out

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
        pitchName: str = ''
        pitchNameCount: int = 0

        if m21Accid is not None:
            alter = int(m21Accid.alter)
            if alter != m21Accid.alter:
                print('WARNING: Ignoring microtonal accidental: {}.'.format(m21Pitch), file=sys.stderr)
                # replace microtonal accidental with explicit natural sign
                alter = 0
                isExplicit = True

            if m21Accid.displayType != 'normal' and m21Accid.displayType != 'never':
                # must be 'always', 'unless-repeated', or 'even-tied'
                isExplicit = True
                editorialStyle: str = m21Accid.displayStyle
                if editorialStyle != 'normal':
                    # must be 'parentheses', 'bracket', or 'both'
                    isEditorial = True
                    M21Convert._reportEditorialAccidentalToOwner(owner, editorialStyle)

        pitchName = m21Step
        if m21Octave > 3:
            pitchName = m21Step.tolower()
            pitchNameCount = m21Octave - 3
        else:
            pitchName = m21Step.toupper()
            pitchNameCount = 4 - m21Octave

        for _ in range(0, pitchNameCount):
            output += pitchName

        if m21Accid is None:
            # no accidental suffix
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
                output += 'ni' # explicit natural + editorial suffix
            else:
                output += 'i'  # editorial suffix
        elif isExplicit:
            if alter == 0:
                output += 'n' # explicit natural
            else:
                output += 'X' # explicit suffix for other accidentals

    @staticmethod
    def _reportEditorialAccidentalToOwner(owner, editorialStyle: str):
        if owner:
            import EventData # owner is always an EventData
            ownerEvent: EventData = owner
            ownerEvent.reportEditorialAccidentalToOwner(editorialStyle)

    @staticmethod
    def textLayoutParameterFromM21TextExpression(textExpression: m21.expressions.TextExpression) -> str:
        if textExpression is None:
            return ''

        placementString: str = ''
        styleString: str = ''
        contentString: str = textExpression.content

        if textExpression.placement is not None:
            if textExpression.placement == 'above':
                placementString = ':a'
            elif textExpression.placement == 'below':
                placementString = ':b'

        # absoluteY overrides placement
        if textExpression.style.absoluteY is not None:
            if textExpression.style.absoluteY >= 0.0:
                placementString = ':a'
            else:
                placementString = ':b'

        if not contentString:
            return ''

        italic: bool = False
        bold: bool = False

        if textExpression.style.fontStyle is not None:
            if textExpression.style.fontStyle == 'italic':
                italic = True

        if textExpression.style.fontWeight is not None:
            if textExpression.style.fontWeight == 'bold':
                bold = True

        if italic and bold:
            styleString = ':Bi'
        elif italic:
            styleString = ':i'
        elif bold:
            styleString = ':B'

        contentString = M21Convert._cleanSpacesAndColons(contentString)

        if not contentString:
            # no text to display after cleaning
            return ''

        output: str = '!LO:TX' + placementString + styleString + ':t=' + contentString
        return output

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
        inStr: str = inStr.strip() # strips all leading and trailing whitespace
        newLinesAndTabs: str = '\t\n\r\v\f'
        output: str = ''
        for ch in inStr:
            if ch == ':': # convert all colons to '&colon;'
                output += '&colon;'
                continue

            if ch in newLinesAndTabs:
                output += ' ' # convert all newLinesAndTabs chars to a space
                continue

            output += ch

        return output

    # getMMTokenAndTempoTextLayoutFromM21TempoIndication returns (mmTokenStr, tempoTextLayout). Either can be None.
    @staticmethod
    def getMMTokenAndTempoTextLayoutFromM21TempoIndication(
                                tempo: m21.tempo.TempoIndication) -> (str, str):
        mmTokenStr: str = ''
        tempoTextLayout: str = ''

        textExp: m21.expressions.TextExpression = None

        # a TempoText has only text (no bpm info)
        if isinstance(tempo, m21.tempo.TempoText):
            textExp = tempo.getTextExpression() # only returns explicit text
            if textExp is None:
                return ('', '')
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
            tempoTextLayout = M21Convert.textLayoutParameterFromM21TextExpression(textExp)

        if tempo.number is not None and not tempo.numberImplicit:
            # we have an explicit bpm, so we can generate mmTokenStr and bpm text
            mmTokenStr = '*MM' + str(tempo.getQuarterBPM())
            if tempoTextLayout:
                tempoTextLayout += ' [' # space delimiter between text and bpm text
                tempoTextLayout += M21Convert.getHumdrumTempoNoteNameFromM21Duration(tempo.referent)
                tempoTextLayout += ']='
                tempoTextLayout += str(tempo.number)

        return (mmTokenStr, tempoTextLayout)

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

        # in case someone forgot to strip the brackets off '[quarter-dot]', for example.
        if noteName[0] == '[' and noteName[-1] == ']':
            noteName = noteName[1:-1]

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

    @staticmethod
    def getDynamicString(dynamic: m21.dynamics.Dynamic) -> str:
        if not isinstance(dynamic, m21.dynamics.Dynamic):
            return ''

        output: str = dynamic.value
        if output == 'rf':  # C++ code does this mapping, not sure why
            output = 'rfz'

        return output

    @staticmethod
    def getDynamicWedgeString(wedge: m21.dynamics.DynamicWedge, gnote: m21.note.GeneralNote) -> str:
        if not isinstance(wedge, m21.dynamics.DynamicWedge):
            return ''

        isCrescendo: bool = isinstance(wedge, m21.dynamics.Crescendo)
        isDiminuendo: bool = isinstance(wedge, m21.dynamics.Diminuendo)
        isStart: bool = wedge.isFirst(gnote)
        isEnd: bool = wedge.isLast(gnote)

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
    def getDynamicsParameters(dynamic: Union[m21.dynamics.Dynamic, m21.dynamics.DynamicWedge],
                               gnote: m21.note.GeneralNote) -> str:
        isSpanner: bool = None

        if isinstance(dynamic, m21.dynamics.Dynamic):
            isSpanner = False

        if isinstance(dynamic, m21.dynamics.DynamicWedge):
            isSpanner = True

        if isSpanner is None:
            # dynamic has invalid type
            return ''

        if isSpanner and not dynamic.isFirst(gnote):
            # don't apply parameters to ends of hairpins.
            return ''

        if dynamic.placement is None:
            return ''

        if dynamic.placement == 'above':
            return ':a'

        if dynamic.placement == 'below':
            return ':b'

        return ''
