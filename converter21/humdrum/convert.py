# ------------------------------------------------------------------------------
# Name:          Convert.py
# Purpose:       Conversions
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------

import sys
import re
import math
import typing as t
from fractions import Fraction

from music21.common import opFrac

from converter21.shared import SharedConstants
from converter21.humdrum import MeasureStyle
from converter21.humdrum import FermataStyle
from converter21.humdrum import HumNum, HumNumIn
from converter21.humdrum import HumdrumInternalError

class Convert:

    '''
        *** Rhythm ***
    '''

    '''
    //////////////////////////////
    //
    // Convert::recipToDuration -- Convert **recip rhythmic values into
    //     rational number durations in terms of quarter notes.  For example "4"
    //     will be converted to 1, "4." to 3/2 (1+1/2).  The second parameter
    //     is a scaling factor which can change the rhythmic value's base duration.
    //     Giving a scale of 1 will return the duration in whole note units, so
    //     "4" will return a value of 1/4 (one quarter of a whole note).  Using
    //     3/2 will give the duration in terms of dotted-quarter note units.
    //     The third parameter is the sub-token separate.  For example if the input
    //     string contains a space, anything after the first space will be ignored
    //     when extracting the string.  **kern data which also includes the pitch
    //     along with the rhythm can also be given and will be ignored.
    // default value: scale = 4 (duration in terms of quarter notes)
    // default value: separator = " " (sub-token separator)
    '''
    # key is recip, value is duration
    _knownRecipDurationCache: t.Dict[str, HumNum] = {}

    @staticmethod
    def recipToDuration(recip: str, scale: HumNumIn = opFrac(4)) -> HumNum:
        if recip in Convert._knownRecipDurationCache:
            return Convert._knownRecipDurationCache[recip]

        output: HumNum = opFrac(0)
        if 'q' in recip:
            # grace note, ignore printed rhythm
            Convert._knownRecipDurationCache[recip] = output
            return output  # 0

        subToken = recip.split(' ')[0]  # we're only interested in the first subtoken
        dotCount = subToken.count('.')

        m = re.search(r'([\d]+)%([\d]+)', subToken)
        if m is not None:
            # reciprocal rhythm 'denom%numer'
            output = opFrac(Fraction(int(m.group(2)), int(m.group(1))))
        else:
            m = re.search(r'([\d]+)', subToken)
            if m is None:
                # no rhythm found
                # don't fill cache with bad strings
                # Convert._knownRecipDurationCache[recip] = output
                return output  # 0

            if m.group(1).startswith('0'):
                # 0-symbol (e.g. '0' is 2/1, '00' is 4/1, '000' is 8/1, etc)
                zeroCount = m.group(1).count('0')
                output = opFrac(Fraction(pow(2, zeroCount), 1))
            else:
                # plain rhythm (denominator is in subToken, numerator is 1)
                output = opFrac(Fraction(1, int(m.group(1))))

        scale = opFrac(scale)
        dotFactor: HumNum = opFrac(1)
        if dotCount > 0:
            # if dotCount=1: dotFactor should be  3/2 (1.5, or one and a half)
            # if dotCount=2: dotFactor should be  7/4 (1.75, or one and three quarters)
            # if dotCount=3: dotFactor should be 15/8 (1.875, or one and seven eighths)
            # etc...
            #
            # dotFactor =   2^(dotCount+1) - 1
            #               ------------------
            #                   2^dotCount
            dotFactor = Fraction(pow(2, dotCount + 1) - 1, pow(2, dotCount))
            dotFactor = opFrac(dotFactor)

        output = opFrac(output * dotFactor * scale)
        Convert._knownRecipDurationCache[recip] = output
        return output

    '''
    //////////////////////////////
    //
    // Convert::recipToDurationNoDots -- Same as recipToDuration(), but ignore
    //   any augmentation dots.
    '''
    @staticmethod
    def recipToDurationNoDots(recip: str, scale: HumNumIn = opFrac(4)) -> HumNum:
        recipNoDots: str = re.sub(r'\.', 'Z', recip)
        return Convert.recipToDuration(recipNoDots, scale)

    '''
    //////////////////////////////
    //
    // Convert::timeSigToDurationInQuarters -- Convert a **kern time signature
    //   into the duration of the measure for that time signature.
    //   output units are in quarter notes.
    //   Example: 6/8 => 3 quarters
    //   Example: 3/4 => 3 quarters
    //   Example: 3/8 => 3/2 quarters
    '''
    @staticmethod
    def timeSigToDuration(token, scale: HumNumIn = opFrac(4)) -> HumNum:
        from converter21.humdrum import HumdrumToken
        tok: HumdrumToken = token
        if not tok.isTimeSignature:
            return opFrac(0)

        # LATER: Handle extended **recip for time signature denominator
        m = re.search(r'^\*M(\d+)/(\d+)', tok.text)
        if m is None:
            return opFrac(0)

        scale = opFrac(scale)

        top: int = int(m.group(1))
        bot: int = int(m.group(2))
        output = opFrac(Fraction(top, bot)) * scale
        return opFrac(output)

    '''
    //////////////////////////////
    //
    // Convert::durationToRecip -- Duration input is in units of quarter notes
    '''
    @staticmethod
    def durationToRecip(duration: HumNumIn) -> str:
        # convert from quarter notes to whole notes
        dur: HumNum = opFrac(opFrac(duration) / opFrac(4))
        # we need numerator and denominator sometimes
        durFraction: Fraction = Fraction(dur)

        if durFraction.numerator == 1:
            # simple rhythm (integer divisions of the whole note)
            return str(durFraction.denominator)

        if dur == 2:
            return '0'     # breve
        if dur == 3:
            return '0.'    # dotted breve
        if dur == 4:
            return '00'    # long
        if dur == 6:
            return '00.'   # dotted long
        if dur == 8:
            return '000'   # maxima
        if dur == 12:
            return '000.'  # dotted maxima

        if durFraction.numerator == 0:
            # grace note
            return 'q'

        # now decide if the rhythm can be represented simply with one dot.
        test1dot: Fraction = Fraction(dur * opFrac(Fraction(2, 3)))
        if test1dot.numerator == 1:
            # single dot works
            return str(test1dot.denominator) + '.'

        # now decide if the rhythm can be represented simply with two dots.
        test2dot: Fraction = Fraction(dur * opFrac(Fraction(4, 7)))
        if test2dot.numerator == 1:
            # double dot works
            return str(test2dot.denominator) + '..'

        # now decide if the rhythm can be represented simply with three dots.
        test3dot: Fraction = Fraction(dur * opFrac(Fraction(8, 15)))
        if test3dot.numerator == 1:
            # triple dot works
            return str(test3dot.denominator) + '...'

        # duration required more than three dots or is not simple,
        # so assume that it is not simple:
        return str(durFraction.denominator) + '%' + str(durFraction.numerator)

    '''
        *** Mensural notation ***
    '''

    '''
    //////////////////////////////
    //
    // Convert::mensToDuration --
    //   X = maxima (octuple whole note)
    //   L = long  (quadruple whole note)
    //   S = breve (double whole note)
    //   s = semi-breve (whole note)
    //   M = minim (half note)
    //   m = semi-minim (quarter note)
    //   U = fusa (eighth note)
    //   u = semifusa (sixteenth note)
    //
    //   p = perfect (dotted)
    //   i = imperfect (not-dotted)
    //
    // Still have to deal with coloration (triplets)
    //
    // Default value: scale = 4 (convert to quarter note units)
    //                separator = " " (space between chord notes)
    '''
    @staticmethod
    def mensToDuration(text: str) -> HumNum:
        output: HumNum = opFrac(0)
        perfect: bool = False
        for ch in text:
            if ch == 'p':
                perfect = True
            if ch == 'i':
                perfect = False

            # units are in whole notes, but we will convert to quarter notes before returning result
            if ch == 'X':
                output = opFrac(8)
                break
            if ch == 'L':
                output = opFrac(4)
                break
            if ch == 'S':
                output = opFrac(2)
                break
            if ch == 's':
                output = opFrac(1)
                break
            if ch == 'M':
                output = opFrac(Fraction(1, 2))
                break
            if ch == 'm':
                output = opFrac(Fraction(1, 4))
                break
            if ch == 'U':
                output = opFrac(Fraction(1, 8))
                break
            if ch == 'u':
                output = opFrac(Fraction(1, 16))
                break
            if ch == ' ':  # token separator, we're done
                # only get duration of first note in chord
                break

        if perfect:
            output *= opFrac(3)
            output /= opFrac(2)

        # convert to quarter notes
        output *= opFrac(4)
        return opFrac(output)

    '''
    //////////////////////////////
    //
    // Convert::mensToDurationNoDots -- The imperfect duration of the **mens rhythm.
    '''
    @staticmethod
    def mensToDurationNoDots(text: str) -> HumNum:
        output: HumNum = opFrac(0)
        for ch in text:
            # units are in whole notes, but we will convert to quarter notes before returning result
            if ch == 'X':
                output = opFrac(8)
                break
            if ch == 'L':
                output = opFrac(4)
                break
            if ch == 'S':
                output = opFrac(2)
                break
            if ch == 's':
                output = opFrac(1)
                break
            if ch == 'M':
                output = opFrac(Fraction(1, 2))
                break
            if ch == 'm':
                output = opFrac(Fraction(1, 4))
                break
            if ch == 'U':
                output = opFrac(Fraction(1, 8))
                break
            if ch == 'u':
                output = opFrac(Fraction(1, 16))
                break
            if ch == ' ':  # token separator, we're done
                # only get duration of first note in chord
                break

        # convert to quarter notes
        output *= opFrac(4)
        return opFrac(output)

    '''
    //////////////////////////////
    //
    // Convert::isMensRest -- Returns true if the input string represents
    //   a **mens rest.
    '''
    @staticmethod
    def isMensRest(text: str) -> bool:
        return 'r' in text

    '''
    //////////////////////////////
    //
    // Convert::isMensNote -- Returns true if the input string represents
    //   a **mens note (i.e., token with a pitch, not a null token or a rest).
    '''
    @staticmethod
    def isMensNote(text: str) -> bool:
        for ch in text:
            if ch.lower() in 'abcdefg':
                return True
        return False

    '''
    //////////////////////////////
    //
    // Convert::hasLigatureBegin -- Returns true if the input string
    //   has a '<' or '[' character.
    '''
    @staticmethod
    def hasLigatureBegin(text: str) -> bool:
        return Convert.hasRectaLigatureBegin(text) or Convert.hasObliquaLigatureBegin(text)

    '''
    //////////////////////////////
    //
    // Convert::hasLigatureEnd --
    '''
    @staticmethod
    def hasLigatureEnd(text: str) -> bool:
        return Convert.hasRectaLigatureEnd(text) or Convert.hasObliquaLigatureEnd(text)

    '''
    //////////////////////////////
    //
    // Convert::hasRectaLigatureBegin --
    '''
    @staticmethod
    def hasRectaLigatureBegin(text: str) -> bool:
        return '[' in text

    '''
    //////////////////////////////
    //
    // Convert::hasRectaLigatureEnd -- Returns true if the input string
    //   has a ']'.
    '''
    @staticmethod
    def hasRectaLigatureEnd(text: str) -> bool:
        return ']' in text

    '''
    //////////////////////////////
    //
    // Convert::hasObliquaLigatureBegin --
    '''
    @staticmethod
    def hasObliquaLigatureBegin(text: str) -> bool:
        return '<' in text

    '''
    //////////////////////////////
    //
    // Convert::hasObliquaLigatureEnd -- Returns true if the input string
    //   has a '>'.
    '''
    @staticmethod
    def hasObliquaLigatureEnd(text: str) -> bool:
        return '>' in text


    '''
        *** Tempo ***
    '''

    namedTempoPatterns: t.Dict[str, int] = {
        # some of these are actually regular expression patterns
        'larghissimo': 24,
        'adagissimo': 35,
        'all.*molto': 146,
        'all.*vivace': 144,
        'all.*moderato': 116,
        'all.*fuoco': 138,
        'all.*presto': 160,
        'grave': 40,
        'largo': 45,
        'lento?': 50,
        'larghetto': 63,
        'adagio': 70,
        'adagietto': 74,
        'andantino': 90,
        'marcia moderato': 85,
        'andante moderato': 92,
        'allegretto': 116,
        'rasch': 128,
        'vivo': 152,
        'vif': 152,
        'vivace': 164,
        'vivacissimo': 172,
        'allegrissimo': 176,
        'moderato': 108,
        'andante': 88,
        'presto': 180,
        'allegro': 128,
        'prestissimo': 208,
        'bewegt': 144,
        'all(?!a)': 128,
    }

    '''
    //////////////////////////////
    //
    // Convert::tempoNameToMm -- Guess what the MM tempo should be given
    //    a tempo name.  Returns 0 if no guess is made.
    //
    // LATER: Also add cases where there is a tempo marking, such as [quarter] = 132
    // in the input text.
    '''
    @staticmethod
    def tempoNameToBPM(name: str, timeSig: t.Tuple[int, int]) -> float:
        # timeSig tuple is (top: int, bot: int, ... other stuff)
        top: int = timeSig[0]
        bot: int = timeSig[1]
        lowerName = name.lower()

        output: float = 0.0

        for namePatt, nameValue in Convert.namedTempoPatterns.items():
            if re.match(namePatt, lowerName):
                output = float(nameValue)
                break

        if output <= 0:
            return 0

        if 'ma non troppo' in lowerName or 'non tanto' in lowerName:
            if output > 100:
                output *= 0.93
            else:
                output /= 0.93

        if bot == 2:
            output *= 1.75
        elif bot == 1:
            output *= 3.0
        elif bot == 8 and top % 3 == 0:
            output *= 1.5
        elif bot == 8:
            output *= 0.75
        elif bot == 16 and top % 3 == 0:
            output *= 1.5 / 2.0
        elif bot == 16:
            output /= 2.0
        elif bot == 32 and top % 3 == 0:
            output *= 1.5 / 4.0
        elif bot == 32:
            output /= 4.0

        if bot == 2 and top % 3 == 0:
            output *= 1.5

        return output

    _METRONOME_MARK_PATTERNS: t.List[str] = [
        # the one with parens needs to come first or a string with parens will match the wrong
        # pattern, and instead of 'Allegro', you'll get 'Allegro ('.
        # With parens, e.g. 'Allegro M.M. ([quarter] = 128.0)'
        r'(.*?)\s*(M\.M\.|M\. M\.|M\:M\:|M M)?\s*\(\[([^=\]]*)\]\s*=\s*(\d+\.?\d*)',
        # Without parens, e.g. 'Allegro M.M. [quarter] = 128.0'
        r'(.*?)\s*(M\.M\.|M\. M\.|M\:M\:|M M)?\s*\[([^=\]]*)\]\s*=\s*(\d+\.?\d*)',
    ]

    @staticmethod
    def getMetronomeMarkInfo(
        text: str
    ) -> t.Tuple[t.Optional[str], t.Optional[str], t.Optional[str], t.Optional[str]]:
        # takes strings like
        # "Andante M.M. [quarter] = 88.1"  # PATTERNS[0]
        # or
        # "Andante M.M. ([quarter] = 88.1" # PATTERNS[1]
        # and returns
        # (tempoName, mmStr, refNoteName, bpmText) -> ('Andante', 'M.M.', 'quarter', '88.1')

        for markPatt in Convert._METRONOME_MARK_PATTERNS:
            m = re.search(markPatt, text)
            if m:
                return (m.group(1), m.group(2), m.group(3), m.group(4))

        return (None, None, None, None)

    @staticmethod
    def hasMetronomeMarkInfo(text: str) -> bool:
        for markPatt in Convert._METRONOME_MARK_PATTERNS:
            m = re.search(markPatt, text)
            if m:
                return True

        return False


    @staticmethod
    def getTempoText(text: str) -> str:
        output: str = ''

        pattern: str = r'(.*)\[([^=\]]*)\]\s*=\s*(\d+.*)'
        m = re.search(pattern, text)
        if m is None:
            return ''

        first: str = m.group(1)
        second: str = m.group(2)
        third: str = m.group(3)

        second = Convert.humdrumTempoNoteNameToSmuflText(second)

        if first:
            if first[-1] == '(':
                # Add _very_ thin spacer (HAIR SPACE) after opening parenthesis
                # to separate parenthesis and notehead:
                first += chr(0x200A)

        output += first

        # Add the musical symbols (notes and dots), adding a space between them
        dotChar: str = SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get('metAugmentationDot', '')
        counter: int = 0
        for i, char in enumerate(second):
            if i > 0:
                # Add a space element between music symbols.
                if char == dotChar:
                    # use a THIN SPACE before dot
                    output += chr(0x2009)
                else:
                    # use a "non-breaking space" otherwise
                    output += chr(0x00A0)

            output += char

        output += chr(0x00A0) + '=' + chr(0x00A0) + third

        return output

    @staticmethod
    def humdrumTempoNoteNameToSmuflText(text: str) -> str:
        output: str = ''
        if not text:
            return output

        finaltext: str
        if text[0] == '[' and text[-1] == ']':
            finaltext = text[1:-1]
        else:
            finaltext = text

        # Remove styling qualifiers
        finaltext = re.sub('[|@].*', '', finaltext)

        # https://www.smufl.org/version/1.2/range/metronomeMarks

        # Count the number of augmentation dots on the note, and then remove them:
        dots: int = 0
        if re.search('-dot$', finaltext):
            dots = 1
            if re.search('-dot-dot$', finaltext):
                dots = 2
                if re.search('-dot-dot-dot$', finaltext):
                    dots = 3
                # Only allowing three augmentation dots.
        finaltext = re.sub('(-dot)+', '', finaltext)

        # Check for "." used as an augmentation dot (typically used with numbers):
        m = re.search(r'(\.+)$', finaltext)
        if m:
            dotstring: str = m.group(1)
            dots += len(dotstring)
            finaltext = re.sub(r'\.+$', '', finaltext)

        if finaltext in ('quarter', '4'):
            output = SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get('metNoteQuarterUp', '')
        elif finaltext in ('half', '2'):
            output = SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get('metNoteHalfUp', '')
        elif finaltext in ('whole', '1'):
            output = SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get('metNoteWhole', '')
        elif finaltext in ('breve', 'double-whole', '0'):
            output = SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get('metNoteDoubleWhole', '')
        elif finaltext in ('eighth', '8', '8th'):
            output = SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get('metNote8thUp', '')
        elif finaltext in ('sixteenth', '16', '16th'):
            output = SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get('metNote16thUp', '')
        elif finaltext in ('32', '32nd'):
            output = SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get('metNote32ndUp', '')
        elif finaltext in ('64', '64th'):
            output = SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get('metNote64thUp', '')
        elif finaltext in ('128', '128th'):
            output = SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get('metNote128thUp', '')
        elif finaltext in ('256', '256th'):
            output = SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get('metNote256thUp', '')
        elif finaltext in ('512', '512th'):
            output = SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get('metNote512thUp', '')
        elif finaltext in ('1024', '1024th'):
            output = SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get('metNote1024thUp', '')

        if dots > 0:
            output += (
                SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get('metAugmentationDot', '')
                * dots
            )

        return output

    '''
        *** Math ***
    '''

    '''
    //////////////////////////////
    //
    // Convert::getLcm -- Return the Least Common Multiple of a list of numbers.
    '''
    @staticmethod
    def getLcm(nums: t.List[int]) -> int:
        if len(nums) == 0:
            return 1

        output: int = nums[0]
        for i in range(1, len(nums)):
            output = (output * nums[i]) // math.gcd(output, nums[i])

        return output


    '''
        *** kern ***
    '''

    '''
    //////////////////////////////
    //
    // Convert::isKernRest -- Returns true if the input string represents
    //   a **kern rest.
    '''
    @staticmethod
    def isKernRest(text: str) -> bool:
        return 'r' in text

    '''
    //////////////////////////////
    //
    // Convert::isKernNote -- Returns true if the input string represents
    //   a **kern note (i.e., token with a pitch, not a null token or a rest).
    '''
    @staticmethod
    def isKernNote(text: str) -> bool:
        # rests can have note values (for positioning) without being a note,
        # so check if it's a rest before looking for note values.
        if Convert.isKernRest(text):
            return False

        for ch in text:
            if ch in 'abcdefgABCDEFG':
                return True
        return False

    '''
    //////////////////////////////
    //
    // Convert::hasKernSlurStart -- Returns true if the input string
    //   has a '('.
    '''
    @staticmethod
    def hasKernSlurStart(text: str) -> bool:
        return '(' in text

    '''
    //////////////////////////////
    //
    // Convert::hasKernSlurEnd -- Returns true if the input string
    //   has a ')'.
    '''
    @staticmethod
    def hasKernSlurEnd(text: str) -> bool:
        return ')' in text

    '''
    //////////////////////////////
    //
    // Convert::hasKernPhraseStart -- Returns true if the input string
    //   has a '{'.
    '''
    @staticmethod
    def hasKernPhraseStart(text: str) -> bool:
        return '{' in text

    '''
    //////////////////////////////
    //
    // Convert::hasKernPhraseEnd -- Returns true if the input string
    //   has a '}'.
    '''
    @staticmethod
    def hasKernPhraseEnd(text: str) -> bool:
        return '}' in text

    '''
    //////////////////////////////
    //
    // Convert::getKernSlurStartElisionLevel -- Returns the number of
    //   '&' characters before the given '(' character in a kern token.
    //   Returns -1 if no '(' character in string.
    '''
    @staticmethod
    def getKernSlurStartElisionLevel(text: str, index: int) -> int:
        return Convert._getElisionLevelWorker('(', text, index)

    '''
    //////////////////////////////
    //
    // Convert::getKernSlurEndElisionLevel -- Returns the number of
    //   '&' characters before the last ')' character in a kern token.
    //   Returns -1 if no ')' character in string.
    '''
    @staticmethod
    def getKernSlurEndElisionLevel(text: str, index: int) -> int:
        return Convert._getElisionLevelWorker(')', text, index)

    '''
    //////////////////////////////
    //
    // Convert::getKernPhraseStartElisionLevel -- Returns the number of
    //   '&' characters before the given '{' character in a kern token.
    //   Returns -1 if no '{' character in string.
    '''
    @staticmethod
    def getKernPhraseStartElisionLevel(text: str, index: int) -> int:
        return Convert._getElisionLevelWorker('{', text, index)

    '''
    //////////////////////////////
    //
    // Convert::getKernPhraseEndElisionLevel -- Returns the number of
    //   '&' characters before the last '}' character in a kern token.
    //   Returns -1 if no '}' character in string.
    '''
    @staticmethod
    def getKernPhraseEndElisionLevel(text: str, index: int) -> int:
        return Convert._getElisionLevelWorker('}', text, index)

    @staticmethod
    def _getElisionLevelWorker(searchChar: str, text: str, index: int) -> int:
        output: int = 0
        foundSearchChar: bool = False
        count: int = 0
        target: int = index + 1

        for i, ch in enumerate(text):
            if ch == searchChar:
                count += 1
            if count == target:
                foundSearchChar = True
                # walk backward from i-1 counting contiguous '&'s
                for ch1 in reversed(text[:i]):
                    if ch1 == '&':
                        output += 1
                    else:
                        break
                break

        if not foundSearchChar:
            return -1

        return output

    '''
    //////////////////////////////
    //
    // Convert::isKernSecondaryTiedNote -- Returns true if the input string
    //   represents a **kern note (i.e., token with a pitch,
    //   not a null token or a rest) and has a '_' or ']' character.
    '''
    @staticmethod
    def isKernSecondaryTiedNote(text: str) -> bool:
        if not Convert.isKernNote(text):
            return False

        for ch in text:
            if ch in '_]':
                return True

        return False

    '''
    //////////////////////////////
    //
    // Convert::hasKernStemDirection -- Returns true if a stem direction in data; otherwise,
    //    return false.  If true, then '/' means stem up, and '\\' means stem down.
        renamed to getKernStemDirection, returns '/' or '\' or None
    '''
    @staticmethod
    def getKernStemDirection(text: str) -> t.Optional[str]:
        for ch in text:
            if ch == '/':
                return '/'
            if ch == '\\':
                return '\\'
        return None

    '''
        *** pitch ***
    '''

    '''
    //////////////////////////////
    //
    // Convert::kernToBase40 -- Convert **kern pitch to a base-40 integer.
    //    Will ignore subsequent pitches in a chord.
    '''
    @staticmethod
    def kernToBase40(text: str) -> int:
        pc: int = Convert.kernToBase40PC(text)
        if pc < 0:
            return pc

        octave: int = Convert.kernToOctaveNumber(text)
        return pc + (40 * octave)

    '''
    //////////////////////////////
    //
    // Convert::kernToBase40PC -- Convert **kern pitch to a base-40 pitch class.
    //    Will ignore subsequent pitches in a chord.
    '''
    @staticmethod
    def kernToBase40PC(text: str) -> int:
        diatonic = Convert.kernToDiatonicPC(text)
        if diatonic < 0:
            return diatonic

        accID = Convert.kernToAccidentalCount(text)
        output: int = -1000
        if diatonic == 0:
            output = 0
        elif diatonic == 1:
            output = 6
        elif diatonic == 2:
            output = 12
        elif diatonic == 3:
            output = 17
        elif diatonic == 4:
            output = 23
        elif diatonic == 5:
            output = 29
        elif diatonic == 6:
            output = 35

        output += accID
        return output + 2   # +2 to make C-flat-flat == 0 (bottom of octave)

    '''
    //////////////////////////////
    //
    // Convert::kernToOctaveNumber -- Convert a kern token into an octave number.
    //    Middle C is the start of the 4th octave. -1000 is returned if there
    //    is not pitch in the string.  Only the first subtoken in the string is
    //    considered.
    '''
    @staticmethod
    def kernToOctaveNumber(text: str) -> int:
        ucCount: int = 0
        lcCount: int = 0

        if text == '.':
            return -1000

        for ch in text:
            if ch == ' ':
                break
            if ch == 'r':
                return -1000

            if ch in 'ABCDEFG':
                ucCount += 1
            if ch in 'abcdefg':
                lcCount += 1

        if ucCount > 0 and lcCount > 0:
            # invalid pitch description
            return -1000

        if ucCount > 0:
            return 4 - ucCount

        if lcCount > 0:
            return 3 + lcCount

        return -1000

    '''
    //////////////////////////////
    //
    // Convert::kernToBase12PC -- Convert **kern pitch to a base-12 pitch-class.
    //   C=0, C#/D-flat=1, D=2, etc.  Will return -1 instead of 11 for C-, and
    //   will return 12 instead of 0 for B#.
    '''
    @staticmethod
    def kernToBase12PC(text: str) -> int:
        diatonic: int = Convert.kernToDiatonicPC(text)
        if diatonic < 0:
            return diatonic

        accid: int = Convert.kernToAccidentalCount(text)
        output: int = -1000
        if diatonic == 0:
            output = 0
        elif diatonic == 1:
            output = 2
        elif diatonic == 2:
            output = 4
        elif diatonic == 3:
            output = 5
        elif diatonic == 4:
            output = 7
        elif diatonic == 5:
            output = 9
        elif diatonic == 6:
            output = 11

        return output + accid
    '''
    ///////////////////////////////
    //
    // Convert::kernToMidiNoteNumber -- Convert **kern to MIDI note number
    //    (middle C = 60).  Middle C is assigned to octave 5 rather than
    //    octave 4 for the kernToBase12() function.
    '''
    @staticmethod
    def kernToMidiNoteNumber(text: str) -> int:
        pc: int = Convert.kernToBase12PC(text)
        octave: int = Convert.kernToOctaveNumber(text)
        return pc + (12 * (octave + 1))

    '''
    //////////////////////////////
    //
    // Convert::kernToAccidentalCount -- Convert a kern token into a count
    //    of accidentals in the first subtoken.  Sharps are assigned to the
    //    value +1 and flats to -1.  So a double sharp is +2 and a double
    //    flat is -2.  Only the first subtoken in the string is considered.
    //    Cases such as "#-" should not exist, but in this case the return
    //    value will be 0.
    '''
    @staticmethod
    def kernToAccidentalCount(text: str) -> int:
        output: int = 0
        for ch in text:
            if ch == ' ':
                break

            if ch == '-':
                output -= 1
            elif ch == '#':
                output += 1

        return output

    '''
    //////////////////////////////
    //
    // Convert::kernToDiatonicPC -- Convert a kern token into a diatonic
    //    note pitch-class where 0="C", 1="D", ..., 6="B".  -1000 is returned
    //    if the note is rest, and -2000 if there is no pitch information in the
    //    input string. Only the first subtoken in the string is considered.
    '''
    @staticmethod
    def kernToDiatonicPC(text: str) -> int:
        for ch in text:
            if ch == ' ':
                break
            if ch == 'r':
                return -1000

            if ch in 'cC':
                return 0
            if ch in 'dD':
                return 1
            if ch in 'eE':
                return 2
            if ch in 'fF':
                return 3
            if ch in 'gG':
                return 4
            if ch in 'aA':
                return 5
            if ch in 'bB':
                return 6

        return -2000

    '''
    //////////////////////////////
    //
    // Convert::kernClefToBaseline -- returns the diatonic pitch
    //    of the bottom line on the staff.
    '''
    CLEF_TO_BASELINE_PITCH: t.Dict[str, str] = {
        'G2': 'e',      # treble clef
        'F4': 'GG',     # bass clef
        'C3': 'F',      # alto clef
        'C4': 'D',      # tenor clef
        'Gv2': 'E',     # vocal tenor clef

        # rest of C clef possibilities:
        'C1': 'c',      # soprano clef
        'C2': 'A',      # mezzo-soprano clef
        'C5': 'BB',     # baritone clef

        # rest of G clef possibilities:
        'G1': 'g',      # French-violin clef
        'G3': 'c',
        'G4': 'A',
        'G5': 'F',

        # rest of F clef possibilities:
        'F1': 'F',
        'F2': 'D',
        'F3': 'BB',
        'F5': 'EE',

        # rest of G clef down an octave possibilities:
        'Gv1': 'G',
        'Gv3': 'C',
        'Gv4': 'AA',
        'Gv5': 'FF',

        # F clef down an octave possibilities:
        'Fv1': 'FF',
        'Fv2': 'DD',
        'Fv3': 'BBB',
        'Fv4': 'GGG',
        'Fv5': 'EEE',

        # C clef down an octave possibilities:
        'Cv1': 'C',
        'Cv2': 'AA',
        'Cv3': 'FF',
        'Cv4': 'DD',
        'Cv5': 'BBB',

        # G clef up an octave possibilities:
        'G^1': 'gg',
        'G^2': 'ee',
        'G^3': 'cc',
        'G^4': 'a',
        'G^5': 'f',

        # F clef up an octave possibilities:
        'F^1': 'f',
        'F^2': 'd',
        'F^3': 'B',
        'F^4': 'G',
        'F^5': 'E',

        # C clef up an octave possibilities:
        'C^1': 'cc',
        'C^2': 'a',
        'C^3': 'f',
        'C^4': 'd',
        'C^5': 'B',

        # G clef down two octaves possibilities:
        'Gvv1': 'GG',
        'Gvv2': 'EE',
        'Gvv3': 'CC',
        'Gvv4': 'AAA',
        'Gvv5': 'FFF',

        # F clef down two octaves possibilities:
        'Fvv1': 'FFF',
        'Fvv2': 'DDD',
        'Fvv3': 'BBBB',
        'Fvv4': 'GGGG',
        'Fvv5': 'EEEE',

        # C clef down two octaves possibilities:
        'Cvv1': 'CC',
        'Cvv2': 'AAA',
        'Cvv3': 'FFF',
        'Cvv4': 'DDD',
        'Cvv5': 'BBBB',

        # G clef up two octaves possibilities:
        'G^^1': 'ggg',
        'G^^2': 'eee',
        'G^^3': 'ccc',
        'G^^4': 'aa',
        'G^^5': 'ff',

        # F clef up two octaves possibilities:
        'F^^1': 'ff',
        'F^^2': 'dd',
        'F^^3': 'b',
        'F^^4': 'g',
        'F^^5': 'e',

        # C clef up two octaves possibilities:
        'C^^1': 'ccc',
        'C^^2': 'aa',
        'C^^3': 'ff',
        'C^^4': 'dd',
        'C^^5': 'b',
    }

    @staticmethod
    def kernClefToBaseline(text: str) -> int:
        clefName: str = ''
        if text.startswith('*clef'):
            clefName = text[5:]
        elif text.startswith('clef'):
            clefName = text[4:]
        else:
            print('Error in Convert.kernClefToBaseline:', text, file=sys.stderr)
            return -1000

        if clefName in Convert.CLEF_TO_BASELINE_PITCH:
            return Convert.kernToBase7(Convert.CLEF_TO_BASELINE_PITCH[clefName])

        # just use treble clef if we don't know what the clef is
        return Convert.kernToBase7(Convert.CLEF_TO_BASELINE_PITCH['G2'])

    '''
    //////////////////////////////
    //
    // Convert::kernToBase7 -- Convert **kern pitch to a base-7 integer.
    //    This is a diatonic pitch class with C=0, D=1, ..., B=6.
    '''
    @staticmethod
    def kernToBase7(text: str) -> int:
        diatonic: int = Convert.kernToDiatonicPC(text)
        if diatonic < 0:
            return diatonic

        octave: int = Convert.kernToOctaveNumber(text)
        return diatonic + (7 * octave)

    '''
    //////////////////////////////
    //
    // Convert::base7ToBase40 -- Convert a base7 value to a base-40 value
    //   (without accidentals).  Negative values are not allowed, but not
    //   checked for.
    '''
    @staticmethod
    def base7ToBase40(base7: int) -> int:
        octave: int = base7 // 7
        b7pc: int = base7 % 7
        b40pc: int = 0

        if b7pc == 0:
            b40pc = 0   # C
        elif b7pc == 1:
            b40pc = 6   # D
        elif b7pc == 2:
            b40pc = 12  # E
        elif b7pc == 3:
            b40pc = 17  # F
        elif b7pc == 4:
            b40pc = 23  # G
        elif b7pc == 5:
            b40pc = 29  # A
        elif b7pc == 6:
            b40pc = 35  # B

        return (octave * 40) + 2 + b40pc  # +2, I assume, because 0 is C-double-flat --gregc

    '''
    //////////////////////////////
    //
    // Convert::base40ToKern -- Convert Base-40 integer pitches into
    //   **kern pitch representation.
    '''
    @staticmethod
    def base40ToKern(b40: int) -> str:
        octave: int = b40 // 40
        accidental: int = Convert.base40ToAccidental(b40)
        diatonic: int = Convert.base40ToDiatonic(b40) % 7
        base: str = 'a'
        if diatonic == 0:
            base = 'c'
        elif diatonic == 1:
            base = 'd'
        elif diatonic == 2:
            base = 'e'
        elif diatonic == 3:
            base = 'f'
        elif diatonic == 4:
            base = 'g'
        elif diatonic == 5:
            base = 'a'
        elif diatonic == 6:
            base = 'b'

        if octave < 4:
            base = base.upper()

        repeat: int = 0
        if octave > 4:
            repeat = octave - 4
        elif octave < 3:
            repeat = 3 - octave

        if repeat > 12:
            raise HumdrumInternalError(f'Error: unreasonable octave value: {octave} for {b40}')

        output: str = base * (1 + repeat)
        if accidental > 0:
            output += '#' * accidental
        elif accidental < 0:
            output += '-' * -accidental

        return output

    '''
        base7ToKern -- Convert a base-7 integer to a **kern pitch
    '''
    @staticmethod
    def base7ToKern(base7: int) -> str:
        base40: int = Convert.base7ToBase40(base7)
        output: str = Convert.base40ToKern(base40)
        return output

    '''
    //////////////////////////////
    //
    // Convert::base40ToDiatonic -- find the diatonic pitch of the
    //   given base-40 pitch.  Output pitch classes: 0=C, 1=D, 2=E,
    //   3=F, 4=G, 5=A, 6=B.  To this the diatonic octave is added.
    //   To get only the diatonic pitch class, mod by 7: (% 7).
    //   Base-40 pitches are not allowed, and the algorithm will have
    //   to be adjusted to allow them.  Currently any negative base-40
    //   value is presumed to be a rest and not processed.
    '''
    @staticmethod
    def base40ToDiatonic(b40: int) -> int:
        if b40 < 0:
            return -1  # rest

        chroma: int = b40 % 40
        octaveOffset: int = (b40 // 40) * 7

        if chroma in (0, 1, 2, 3, 4):       # C-- to C##
            return 0 + octaveOffset
        if chroma in (6, 7, 8, 9, 10):      # D-- to D##
            return 1 + octaveOffset
        if chroma in (12, 13, 14, 15, 16):  # E-- to E##
            return 2 + octaveOffset
        if chroma in (17, 18, 19, 20, 21):  # F-- to F##
            return 3 + octaveOffset
        if chroma in (23, 24, 25, 26, 27):  # G-- to G##
            return 4 + octaveOffset
        if chroma in (29, 30, 31, 32, 33):  # A-- to A##
            return 5 + octaveOffset
        if chroma in (35, 36, 37, 38, 39):  # B-- to B##
            return 6 + octaveOffset

        # found an empty slot, so return rest:
        return -1

    '''
    //////////////////////////////
    //
    // Convert::base40ToAccidental -- +1 = 1 sharp, +2 = double sharp, 0 = natural
    //	-1 = 1 flat, -2 = double flat
    '''
    @staticmethod
    def base40ToAccidental(b40: int) -> int:
        if b40 < 0:
            # not considering low pitches.  If so then the mod operator
            # below would need fixing.
            return 0

        b40pc: int = b40 % 40  # get rid of octave
        if b40pc == 0:
            return -2       # C-double-flat
        if b40pc == 1:
            return -1       # C-flat
        if b40pc == 2:
            return 0        # C
        if b40pc == 3:
            return 1        # C-sharp
        if b40pc == 4:
            return 2        # C-double-sharp
        if b40pc == 5:
            return 1000     # no note for this b40pc
        if b40pc == 6:
            return -2
        if b40pc == 7:
            return -1
        if b40pc == 8:
            return 0        # D
        if b40pc == 9:
            return 1
        if b40pc == 10:
            return 2
        if b40pc == 11:
            return 1000     # no note for this b40pc
        if b40pc == 12:
            return -2
        if b40pc == 13:
            return -1
        if b40pc == 14:
            return 0        # E
        if b40pc == 15:
            return 1
        if b40pc == 16:
            return 2
        if b40pc == 17:
            return -2
        if b40pc == 18:
            return -1
        if b40pc == 19:
            return 0        # F
        if b40pc == 20:
            return 1
        if b40pc == 21:
            return 2
        if b40pc == 22:
            return 1000     # no note for this b40pc
        if b40pc == 23:
            return -2
        if b40pc == 24:
            return -1
        if b40pc == 25:
            return 0        # G
        if b40pc == 26:
            return 1
        if b40pc == 27:
            return 2
        if b40pc == 28:
            return 1000     # no note for this b40pc
        if b40pc == 29:
            return -2
        if b40pc == 30:
            return -1
        if b40pc == 31:
            return 0        # A
        if b40pc == 32:
            return 1
        if b40pc == 33:
            return 2
        if b40pc == 34:
            return 1000     # no note for this b40pc
        if b40pc == 35:
            return -2
        if b40pc == 36:
            return -1
        if b40pc == 37:
            return 0        # B
        if b40pc == 38:
            return 1
        if b40pc == 39:
            return 2

        return 0

    '''
        Math stuff
    '''

    '''
    //////////////////////////////
    //
    // HumNum::isPowerOfTwo -- Returns true if a power of two.
    '''
    @staticmethod
    def isPowerOfTwo(num: HumNumIn) -> bool:
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
    def isPowerOfTwoWithDots(quarterLength: HumNumIn) -> bool:
        ql: HumNum = opFrac(quarterLength)
        if Convert.isPowerOfTwo(ql):
            # power of two + no dots
            return True
        if Convert.isPowerOfTwo(ql * opFrac(Fraction(2, 3))):
            # power of two + 1 dot
            return True
        if Convert.isPowerOfTwo(ql * opFrac(Fraction(4, 7))):
            # power of two + 2 dots
            return True
        if Convert.isPowerOfTwo(ql * opFrac(Fraction(8, 15))):
            # power of two + 3 dots
            return True
        return False

    @staticmethod
    def computeDurationNoDotsAndNumDots(durWithDots: HumNumIn) -> t.Tuple[HumNum, t.Optional[int]]:
        dd: HumNum = opFrac(durWithDots)
        attemptedPowerOfTwo: HumNum = dd
        if Convert.isPowerOfTwo(attemptedPowerOfTwo):
            # power of two + no dots
            return (attemptedPowerOfTwo, 0)

        attemptedPowerOfTwo = dd * opFrac(Fraction(2, 3))
        if Convert.isPowerOfTwo(attemptedPowerOfTwo):
            # power of two + 1 dot
            return (attemptedPowerOfTwo, 1)

        attemptedPowerOfTwo = dd * opFrac(Fraction(4, 7))
        if Convert.isPowerOfTwo(attemptedPowerOfTwo):
            # power of two + 2 dots
            return (attemptedPowerOfTwo, 2)

        attemptedPowerOfTwo = dd * opFrac(Fraction(8, 15))
        if Convert.isPowerOfTwo(attemptedPowerOfTwo):
            # power of two + 3 dots
            return (attemptedPowerOfTwo, 3)

        # None signals that we couldn't actually find a power-of-two duration
        return (dd, None)

    @staticmethod
    def getPowerOfTwoDurationsWithDotsAddingTo(quarterLength: HumNumIn) -> t.List[HumNum]:
        output: t.List[HumNum] = []
        ql: HumNum = opFrac(quarterLength)

        if Convert.isPowerOfTwoWithDots(ql):
            # power of two + maybe some dots
            output.append(ql)
            return output

        powerOfTwoQLAttempt: HumNum = opFrac(4)  # start with whole note
        smallest: HumNum = opFrac(Fraction(1, 2048))
        while powerOfTwoQLAttempt >= smallest:
            if ql >= powerOfTwoQLAttempt:
                output.append(powerOfTwoQLAttempt)
                ql = opFrac(ql - powerOfTwoQLAttempt)
            else:
                powerOfTwoQLAttempt = opFrac(powerOfTwoQLAttempt / 2)

            if Convert.isPowerOfTwoWithDots(ql):
                # power of two + maybe some dots
                output.append(ql)
                return output

        # we couldn't compute a full list so just return the original param
        return [opFrac(quarterLength)]

    @staticmethod
    def transToDiatonicChromatic(trans: str) -> t.Tuple[t.Optional[int], t.Optional[int]]:
        # This pattern will match *ITrdNcM and *TrdNcM and dNcM
        m = re.search(r'd([+-]?\d+)c([+-]?\d+)', trans)
        if not m:
            return (None, None)
        return (int(m.group(1)), int(m.group(2)))

    @staticmethod
    def diatonicChromaticToTrans(d: int, c: int) -> str:
        return 'd' + str(d) + 'c' + str(c)

    _humdrumBarlineStyleFromMeasureStyle: t.Dict[MeasureStyle, t.Optional[str]] = {
        MeasureStyle.Double: '||',
        MeasureStyle.HeavyHeavy: '!!',
        MeasureStyle.HeavyLight: '!|',
        MeasureStyle.Final: '=',                    # first '=' of '==' is already there
        MeasureStyle.Short: "'",
        MeasureStyle.Tick: '`',
        MeasureStyle.Dotted: '.',
        MeasureStyle.Dashed: ':',
        MeasureStyle.Invisible: '-',
        MeasureStyle.Regular: '',
        MeasureStyle.Heavy: '!',
        MeasureStyle.NoBarline: None,
        MeasureStyle.RepeatBackwardRegular: ':|',
        MeasureStyle.RepeatBackwardHeavy: ':!',
        MeasureStyle.RepeatBackwardHeavyLight: ':!|',
        MeasureStyle.RepeatBackwardFinal: ':|!',
        MeasureStyle.RepeatBackwardHeavyHeavy: ':!!',
        MeasureStyle.RepeatBackwardDouble: ':||',
        MeasureStyle.RepeatForwardRegular: '|:',
        MeasureStyle.RepeatForwardHeavy: '!:',
        MeasureStyle.RepeatForwardHeavyLight: '!|:',
        MeasureStyle.RepeatForwardFinal: '|!:',
        MeasureStyle.RepeatForwardHeavyHeavy: '!!:',
        MeasureStyle.RepeatForwardDouble: '||:',
        MeasureStyle.RepeatBothRegular: ':|:',
        MeasureStyle.RepeatBothHeavy: ':!:',
        MeasureStyle.RepeatBothHeavyLight: ':!|:',  # unexpected asymmetry
        MeasureStyle.RepeatBothFinal: ':|!:',       # unexpected asymmetry
        MeasureStyle.RepeatBothHeavyHeavy: ':!!:',
        MeasureStyle.RepeatBothDouble: ':||:',
        MeasureStyle.RepeatBothHeavyLightHeavy: ':!|!:',
        MeasureStyle.RepeatBothLightHeavyLight: ':|!|:'
    }

    @staticmethod
    def measureStyleToHumdrumBarlineStyleStr(measureStyle: MeasureStyle) -> t.Optional[str]:
        output: t.Optional[str] = Convert._humdrumBarlineStyleFromMeasureStyle[measureStyle]
        return output

    _humdrumFermataStyleFromFermataStyle: t.Dict[FermataStyle, str] = {
        FermataStyle.NoFermata: '',
        FermataStyle.Fermata: ';',
        FermataStyle.FermataAbove: ';>',
        FermataStyle.FermataBelow: ';<',
    }

    @staticmethod
    def fermataStyleToHumdrumFermataStyleStr(fermataStyle: FermataStyle) -> str:
        output: str = Convert._humdrumFermataStyleFromFermataStyle[fermataStyle]
        return output
