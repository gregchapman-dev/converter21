# ------------------------------------------------------------------------------
# Name:          HumdrumLine.py
# Purpose:       Used to store Humdrum text lines and analytic markup
#                of the line.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021 Greg Chapman
# License:       BSD, see LICENSE
# ------------------------------------------------------------------------------
import sys
import re

from converter21.humdrum import HumNum
from converter21.humdrum import HumHash
from converter21.humdrum import Convert
from converter21.humdrum import HumdrumToken

### For debug or unit test print, a simple way to get a string which is the current function name
### with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  #pragma no cover
# pylint: enable=protected-access

'''
    getKeyAndValue(string, delimiter) is a utility function that
    extracts ('keystr', 'valuestr') from strings like '  keystr   :valuestr '.
    It splits at the delimiter, and strips all leading and trailing whitespace
    from the resulting strings.
'''
def _getKeyAndValue(keyValueStr: str, delimiter: str = ':') -> (str, str):
    keyAndValueStrList = keyValueStr.split(delimiter)
    if len(keyAndValueStrList) == 1:
        return (keyAndValueStrList.strip(), None)

    return (keyAndValueStrList[0].strip(), keyAndValueStrList[1].strip())


class HumdrumLine(HumHash):
    def __init__(self, line: str = '', ownerFile = None): # ownerFile: HumdrumFile
        from converter21.humdrum import HumdrumFile
        super().__init__() # initialize the HumHash fields

        '''
            _text: the line's text string
        '''
        if line is None:
            line = ''
        elif len(line) > 0 and line[-1] == '\n':
            line = line[:-1] # strip off any trailing LF

        self._text: str = line

        '''
        // owner: This is the HumdrumFile which manages the given line.
        '''
        self._ownerFile: HumdrumFile = ownerFile

        '''
        // m_lineindex: Used to store the index number of the HumdrumLine in
        // the owning HumdrumFile object.
        // This variable is filled by HumdrumFileStructure::analyzeLines().
        '''
        self._lineIndex: int = None

        '''
        // m_tokens: Used to store the individual tab-separated token fields
        // on a line.  These are prepared automatically after reading in
        // a full line of text (which is accessed throught the string parent
        // class).  If the full line is changed, the tokens are not updated
        // automatically -- use createTokensFromLine().  Likewise the full
        // text line is not updated if any tokens are changed -- use
        // createLineFromTokens() in that case.  The second case is more
        // useful: you can read in a HumdrumFile, tweak the tokens, then
        // reconstruct the full line and print out again.
        // This variable is filled by HumdrumFile::read().
        // The contents of this vector should be deleted when deconstructing
        // a HumdrumLine object.
        '''
        self._tokens: [str] = []

        '''
        // m_tabs: Used to store a count of the number of tabs between
        // each token on a line.  This is the number of tabs after the
        // token at the given index (so no tabs before the first token).
        '''
        self._numTabsAfterToken: [int] = []

        '''
        // m_duration: This is the "duration" of a line.  The duration is
        // equal to the minimum time unit of all durational tokens on the
        // line.  This also includes null tokens when the duration of a
        // previous note in a previous spine is ending on the line, so it is
        // not just the minimum duration on the line.
        // This variable is filled by HumdrumFileStructure::analyzeRhythm().
        '''
        self._duration: HumNum = None

        '''
        // m_durationFromStart: This is the cumulative duration of all lines
        // prior to this one in the owning HumdrumFile object.  For example,
        // the first notes in a score start at time 0, If the duration of the
        // first data line is 1 quarter note, then the durationFromStart for
        // the second line will be 1 quarter note.
        // This variable is filled by HumdrumFileStructure::analyzeRhythm().
        '''
        self._durationFromStart: HumNum = None

        '''
        // m_durationFromBarline: This is the cumulative duration from the
        // last barline to the current data line.
        // This variable is filled by HumdrumFileStructure::analyzeMeter().
        '''
        self._durationFromBarline: HumNum = None

        '''
        // m_durationToBarline: This is the duration from the start of the
        // current line to the next barline in the owning HumdrumFile object.
        // This variable is filled by HumdrumFileStructure::analyzeMeter().
        '''
        self._durationToBarline: HumNum = None

        '''
        // m_linkedParameters: List of Humdrum tokens which are parameters
        // (mostly only layout parameters at the moment)
        '''
        self._linkedParameters: [HumdrumToken] = []

        '''
        // m_rhythm_analyzed: True if duration information from HumdrumFile
        // has been added to line.
        '''
        self._rhythmAnalyzed: bool = False

        '''
            We are also a HumHash, and that was initialized via super() above.
            But we want our default HumHash prefix to be '!!', not ''
        '''
        self.prefix = '!!'

    # In C++ a HumdrumLine is also a string().  Deriving a mutable class from an immutable
    # base class in Python is trickier than I can manage. So we have a standard "conversion"
    # to string instead.  print("hdLine =", hdLine) will call this automatically, for example.
    # But most clients will need to call str(hdLine), or hdLine.text to "cast" to string.
    def __str__(self) -> str:
        return self.text

    '''
    //////////////////////////////
    //
    // HumdrumLine::token -- Returns a reference to the given token on the line.
    //    An invalid token index would be bad to give to this function as it
    //    returns a reference rather than a pointer (which could be set to
    //    NULL if invalid).  Perhaps this function will eventually throw an
    //    error if the index is out of bounds.

            Returns None if index is out of bounds.
    '''
    def __getitem__(self, index: int) -> HumdrumToken:
        if not isinstance(index, int):
            raise Exception("only simple indexing (no slicing) allowed in HumdrumLine")

        if index < 0:
            index += len(self._tokens)

        if index < 0:
            return None
        if index >= len(self._tokens):
            return None

        return self._tokens[index]

    # generator, so you can do: for token in line.tokens()
    def tokens(self):
        for tokenIdx in range(0, len(self._tokens)):
            yield self._tokens[tokenIdx]

    # Now the actual HumdrumLine APIs/properties
    '''
    //////////////////////////////
    //
    // HumdrumLine::getText --
    '''
    @property
    def text(self) -> str:
        return self._text

    '''
    //////////////////////////////
    //
    // HumdrumLine::setText -- Get the textual content of the line.  Note that
    //    you may need to run HumdrumLine::createLineFromTokens() if the tokens
    //    of the line have changed.
    '''
    @text.setter
    def text(self, newText: str):
        self._text = newText

    '''
        rhythmAnalyzed property (r/w): set to True at beginning of
        HumdrumFileStructure::analyzeRhythmStructure, which we call from here in HumdrumLine,
        if we need that info, and self.rhythmAnalyzed is False.
    '''
    @property
    def rhythmAnalyzed(self) -> bool:
        return self._rhythmAnalyzed

    @rhythmAnalyzed.setter
    def rhythmAnalyzed(self, newRhythmAnalyzed: bool):
        self._rhythmAnalyzed = newRhythmAnalyzed


    '''
    //////////////////////////////
    //
    // HumdrumLine::isKernBoundaryStart -- Return true if the
    //    line does not have any null tokens in **kern data which
    //    refer to data tokens above the line.
    '''
    @property
    def isKernBoundaryStart(self) -> bool:
        if not self.isData:
            return False

        for token in self._tokens:
            if not token.isKern:
                continue
            if token.isNull:
                return False

        return True

    '''
    //////////////////////////////
    //
    // HumdrumLine::isKernBoundaryEnd -- Return true if the next
    //    data line contains no null tokens in the **kern spines.
    //    Assuming that a **kern spine split always starts with
    //    a non-null token.
    '''
    @property
    def isKernBoundaryEnd(self) -> bool:
        if not self.isData:
            return False

        for token in self._tokens:
            if not token.isKern:
                continue

            ntok = token.nextToken0
            while ntok is not None and not ntok.isData:
                ntok = ntok.nextToken0

            if ntok is None:
                continue

            if ntok.isNull:
                return False

        return True

    '''
    //////////////////////////////
    //
    // HumdrumLine::isComment -- Returns true if the first character
    //   in the string is '!'. Could be local, global, or a reference record.
    '''
    @property
    def isComment(self) -> bool:
        return self.text.startswith('!')

    '''
    //////////////////////////////
    //
    // HumdrumLine::isLocalComment -- Returns true if a local comment.
    '''
    @property
    def isLocalComment(self) -> bool:
        return self.isComment and not self.isGlobalComment

    '''
    //////////////////////////////
    //
    // HumdrumLine::isGlobalComment -- Returns true if a global comment.
    '''
    @property
    def isGlobalComment(self) -> bool:
        return self.text.startswith('!!')

    '''
    //////////////////////////////
    //
    // HumdrumLine::isUniversalComment -- Returns true if a universal comment.
    '''
    @property
    def isUniversalComment(self) -> bool:
        return self.text.startswith('!!!!')

    '''
    //////////////////////////////
    //
    // HumdrumLine::isReference -- Returns true if a reference record.
    '''
    @property
    def isReference(self) -> bool:
        return self.isGlobalReference or self.isUniversalReference

    '''
    //////////////////////////////
    //
    // HumdrumLine::isGlobalReference -- Returns true if a global reference record.
    //   Meaning that it is in the form:
    //     !!!KEY: VALUE
    '''
    @property
    def isGlobalReference(self) -> bool:
        if len(self.text) < 5:
            return False
        if not self.text.startswith('!!!'):
            return False
        if self.text.startswith('!!!!'):
            return False
        if ':' not in self.text:
            return False
        preAndPostColon = ':'.split(self.text)
        if ' ' in preAndPostColon[0]: # there was a space pre-colon
            return False
        if '\t' in preAndPostColon[0]: # there was a tab pre-colon
            return False

        return True

    '''
    //////////////////////////////
    //
    // HumdrumLine::isUniversalReference -- Returns true if
    //     a universal reference record.
    '''
    @property
    def isUniversalReference(self) -> bool:
        if len(self.text) < 5:
            return False
        if not self.text.startswith('!!!!'):
            return False
        if self.text.startswith('!!!!!'):
            return False
        if ':' not in self.text:
            return False
        preAndPostColon = ':'.split(self.text)
        if ' ' in preAndPostColon[0]: # there was a space pre-colon
            return False
        if '\t' in preAndPostColon[0]: # there was a tab pre-colon
            return False

        return True

    '''
    //////////////////////////////
    //
    // HumdrumLine::isSignifier -- Returns true if a !!!RDF reference record.
    '''
    @property
    def isSignifier(self) -> bool:
        if len(self.text) < 9:
            return False
        return self.text.startswith('!!!RDF**')

    '''
    //////////////////////////////
    //
    // HumdrumLine::getReferenceKey -- Return reference key if a reference
    //     record.  Otherwise returns an empty string.
    '''
    @property
    def referenceKey(self) -> str:
        if self.isGlobalReference:
            return self.globalReferenceKey

        if self.isUniversalReference:
            return self.universalReferenceKey

        return ''

    '''
    //////////////////////////////
    //
    // HumdrumLine::getReferenceValue -- Return reference value if a reference
    //     record.  Otherwise returns an empty string.
    '''
    @property
    def referenceValue(self) -> str:
        if self.isGlobalReference:
            return self.globalReferenceValue

        if self.isUniversalReference:
            return self.universalReferenceValue

        return ''

    '''
    //////////////////////////////
    //
    // HumdrumLine::getGlobalReferenceKey -- Return reference key if a global
    //     reference record.  Otherwise returns an empty string.
    '''
    @property
    def globalReferenceKey(self) -> str:
        if not self.isGlobalReference:
            return ''

        return _getKeyAndValue(self.text[3:])[0]

    '''
    //////////////////////////////
    //
    // HumdrumLine::getGlobalReferenceValue -- Return reference value if a
    //     global reference record.  Otherwise returns an empty string.
    '''
    @property
    def globalReferenceValue(self) -> str:
        if not self.isGlobalReference:
            return ''

        return _getKeyAndValue(self.text[3:])[1]

    '''
    //////////////////////////////
    //
    // HumdrumLine::getUniversalReferenceKey -- Return reference key if a universal
    //     reference record.  Otherwise returns an empty string.
    '''
    @property
    def universalReferenceKey(self) -> str:
        if not self.isUniversalReference:
            return ''

        return _getKeyAndValue(self.text[4:])[0]

    '''
    //////////////////////////////
    //
    // HumdrumLine::getUniversalReferenceValue -- Return reference value if a
    //     universal reference record.  Otherwise returns an empty string.
    '''
    @property
    def universalReferenceValue(self) -> str:
        if not self.isUniversalReference:
            return ''

        return _getKeyAndValue(self.text[4:])[0]

    '''
    //////////////////////////////
    //
    // HumdrumLine::isExclusiveInterpretation -- Returns true if the first two characters
    //     are "**".
        Modifying this to return True if any token on the line has first two characters '**' -- gregc
        This is to pick up things like:
        **kern <-- this line is (and was) exclusive interpretation
        *+
        *   **data <-- this line is (but was not) exclusive interpretation

    '''
    @property
    def isExclusiveInterpretation(self) -> bool:
        for token in self._tokens:
            if token.isExclusiveInterpretation:
                return True
        return False

    '''
    //////////////////////////////
    //
    // HumdrumLine::isTerminator -- Returns true if all tokens on the line
    //    are terminators.
    '''
    @property
    def isTerminateInterpretation(self) -> bool:
        if self.tokenCount == 0:
            # if tokens have not been parsed, check line text
            return self.text.startswith('*-') # BUGFIX: *! -> *-

        for token in self._tokens:
            if not token.isTerminateInterpretation:
                return False

        return True

    '''
    //////////////////////////////
    //
    // HumdrumLine::isInterpretation -- Returns true if starts with '*' character.
    '''
    @property
    def isInterpretation(self) -> bool:
        return self.text.startswith('*')

    '''
    //////////////////////////////
    //
    // HumdrumLine::isBarline -- Returns true if starts with '=' character.

        Returns whether or not the first token is a barline.
    '''
    @property
    def isBarline(self) -> bool:
        return self._tokens[0].isBarline

    '''
        barlineNumber returns barline number of first token.
    '''
    @property
    def barlineNumber(self) -> int:
        return self._tokens[0].barlineNumber

    '''
        barlineName returns the barline name of the first token
    '''
    @property
    def barlineName(self) -> str:
        return self._tokens[0].barlineName

    '''
    //////////////////////////////
    //
    // HumdrumLine::isData -- Returns true if data (but not measure).
    '''
    @property
    def isData(self) -> bool:
        if self.isComment or self.isInterpretation or self.isBarline or self.isEmpty:
            return False
        return True

    '''
    //////////////////////////////
    //
    // HumdrumLine::isAllNull -- Returns true if all tokens on the line
    //    are null ("." if a data line, "*" if an interpretation line, "!"
    //    if a local comment line).
    '''
    @property
    def isAllNull(self) -> bool:
        if not self.hasSpines:
            return False

        for token in self._tokens:
            if not token.isNull:
                return False

        return True

    '''
    //////////////////////////////
    //
    // HumdrumLine::isAllRhythmicNull -- Returns true if all rhythmic
    //    data-type tokens on the line are null ("." if a data line,
    //    "*" if an interpretation line, "!" if a local comment line).
    '''
    @property
    def isAllRhythmicNull(self) -> bool:
        if not self.hasSpines:
            return False

        for token in self._tokens:
            if not token.hasRhythm:
                continue
            if not token.isNull:
                return False

        return True

    '''
    //////////////////////////////
    //
    // HumdrumLine::getLineIndex -- Returns the index number of the line in the
    //    HumdrumFileBase storage for the lines.
    '''
    @property
    def lineIndex(self) -> int:
        return self._lineIndex

    '''
    //////////////////////////////
    //
    // HumdrumLine::setLineIndex -- Used by the HumdrumFileBase class to set the
    //   index number of the line in the data storage for the file.
    '''
    @lineIndex.setter
    def lineIndex(self, newLineIndex: int):
        self._lineIndex = newLineIndex

    '''
    //////////////////////////////
    //
    // HumdrumLine::getLineNumber -- Returns the line index plus one.
        '''
    @property
    def lineNumber(self) -> int:
        if self.lineIndex is None:
            return None
        return self.lineIndex + 1

    '''
    //////////////////////////////
    //
    // HumdrumLine::getDuration -- Get the duration of the line.  The duration will
    //    be None if rhythmic analysis in HumdrumFileStructure has not been
    //    done on the owning HumdrumFile object.  Otherwise this is the duration of
    //    the current line in the file.
    '''
    @property
    def duration(self) -> HumNum:
        if not self._rhythmAnalyzed:
            if self._ownerFile:
                self._ownerFile.analyzeRhythmStructure()
        return self._duration

    def scaledDuration(self, scale: HumNum) -> HumNum:
        return self.duration * scale # remember, accessing duration property can trigger rhythm analysis

    '''
    //////////////////////////////
    //
    // HumdrumLine::setDuration -- Sets the duration of the line.  This is done
    //   in the rhythmic analysis for the HumdurmFileStructure class.
    '''
    @duration.setter
    def duration(self, newDuration: HumNum):
        if newDuration >= HumNum(0):
            self._duration = newDuration
        else:
            self._duration = HumNum(0)

    '''
    //////////////////////////////
    //
    // HumdrumLine::getBarlineDuration -- Return the duration following a barline,
    //    or the duration of the previous barline in the data.
    '''
    @property
    def barlineDuration(self) -> HumNum:
        # If necessary (and possible), analyze rhythm structure of the whole file,
        # so we can answer the question
        if not self._rhythmAnalyzed:
            if self._ownerFile:
                self._ownerFile.analyzeRhythmStructure()

        if self.isBarline:
            return self.durationToBarline

        return self.durationFromBarline + self.durationToBarline

    def scaledBarlineDuration(self, scale: HumNum) -> HumNum:
        return self.barlineDuration * scale

    '''
    //////////////////////////////
    //
    // HumdrumLine::getDurationFromStart -- Get the duration from the start of the
    //    file to the start of the current line.  This will be -1 if rhythmic
    //    analysis has not been done in the HumdrumFileStructure class.
    '''
    @property
    def durationFromStart(self) -> HumNum:
        if not self._rhythmAnalyzed:
            if self._ownerFile:
                self._ownerFile.analyzeRhythmStructure()

        return self._durationFromStart

    def scaledDurationFromStart(self, scale: HumNum) -> HumNum:
        return self.durationFromStart * scale

    '''
    //////////////////////////////
    //
    // HumdrumLine::setDurationFromStart -- Sets the duration from the start of the
    //    file to the start of the current line.  This is used in rhythmic
    //    analysis done in the HumdrumFileStructure class.
    '''
    @durationFromStart.setter
    def durationFromStart(self, newDurationFromStart: HumNum):
        self._durationFromStart = newDurationFromStart

    '''
    //////////////////////////////
    //
    // HumdrumLine::getDurationToEnd -- Get the duration from the start of the
    //    file to the start of the current line.  This will be -1 if rhythmic
    //    analysis has not been done in the HumdrumFileStructure class.
    '''
    @property
    def durationToEnd(self) -> HumNum:
        if not self._rhythmAnalyzed:
            if self._ownerFile:
                self._ownerFile.analyzeRhythmStructure()
            else:
                return HumNum(0) # there's no owner, so we can't get the score duration

        return self._ownerFile.scoreDuration -  self.durationFromStart

    def scaledDurationToEnd(self, scale: HumNum) -> HumNum:
        return self.durationToEnd * scale

    '''
    //////////////////////////////
    //
    // HumdrumLine::getDurationFromBarline -- Returns the duration from the start
    //    of the given line to the first barline occurring before the given line.
    //    Analysis of this data is found in HumdrumFileStructure::metricAnalysis.
    '''
    @property
    def durationFromBarline(self) -> HumNum:
        if not self._rhythmAnalyzed:
            if self._ownerFile:
                self._ownerFile.analyzeRhythmStructure()

        return self._durationFromBarline

    def scaledDurationFromBarline(self, scale: HumNum) -> HumNum:
        return self.durationFromBarline * scale

    '''
    //////////////////////////////
    //
    // HumdrumLine::setDurationFromBarline -- Time from the previous
    //    barline to the current line.  This function is used in analyzeMeter in
    //    the HumdrumFileStructure class.
    '''
    @durationFromBarline.setter
    def durationFromBarline(self, newDurationFromBarline: HumNum):
        self._durationFromBarline = newDurationFromBarline

    '''
    //////////////////////////////
    //
    // HumdrumLine::getDurationToBarline -- Time from the starting of the
    //   current note to the next barline.
    '''
    @property
    def durationToBarline(self) -> HumNum:
        if not self._rhythmAnalyzed:
            if self._ownerFile:
                self._ownerFile.analyzeRhythmStructure()

        return self._durationToBarline

    def scaledDurationToBarline(self, scale: HumNum) -> HumNum:
        return self.durationToBarline * scale

    '''
    //////////////////////////////
    //
    // HumdrumLine::setDurationToBarline -- Sets the duration from the current
    //     line to the next barline in the score.  This function is used by
    //     analyzeMeter in the HumdrumFileStructure class.
    '''
    @durationToBarline.setter
    def durationToBarline(self, newDurationToBarline: HumNum):
        self._durationToBarline = newDurationToBarline

    '''
    //////////////////////////////
    //
    // HumdrumLine::getTrackStart --  Returns the starting exclusive interpretation
    //    for the given spine/track.
    '''
    def trackStart(self, track: int) -> HumdrumToken:
        if self._ownerFile is None:
            return None

        return self._ownerFile.trackStart(track)

    '''
    //////////////////////////////
    //
    // HumdrumLine::getTrackEnd --  Returns the ending exclusive interpretation
    //    for the given spine/track.
    '''
    def trackEnd(self, track: int, subSpine: int) -> HumdrumToken:
        if self._ownerFile is None:
            return None

        return self._ownerFile.trackEnd(track, subSpine)

    '''
    //////////////////////////////
    //
    // HumdrumLine::getBeat -- Returns the beat number for the data on the
    //     current line given the input **recip representation for the duration
    //     of a beat.  The beat in a measure is offset from 1 (first beat is
    //     1 rather than 0).
    //  Default value: beatrecip = "4".
    //  Default value: beatdur   = 1.

        Instead of two routines for HumNum beatDur and str beatRecip, I'm writing one
        that takes either.  I'll make the default beat a quarter note (beatRecip = "4",
        beatDur = HumNum(1, 4)).  Note that if the type of beatDuration is not HumNum
        or str, we'll try directly converting to HumNum, so we actually support float,
        int, Decimal, etc here.  But we always return HumNum.
    '''
    def beat(self, beatDuration = HumNum(1,4)) -> HumNum:
        if isinstance(beatDuration, HumNum):
            pass
        elif isinstance(beatDuration, str): # recip format string, e.g. '4' means 1/4
            beatDuration = Convert.recipToDuration(beatDuration)
        else:
            beatDuration = HumNum(beatDuration)

        if beatDuration == HumNum(0):
            return HumNum(0)
        beatInMeasure = (self.durationFromBarline / beatDuration) + 1
        return beatInMeasure

    '''
    //////////////////////////////
    //
    // HumdrumLine::hasSpines -- Returns true if the line contains spines.  This
    //   means the the line is not empty or a global comment (which can include
    //   reference records.
    '''
    @property
    def hasSpines(self) -> bool:
        return not self.isGlobal

    '''
    //////////////////////////////
    //
    // HumdrumLine::isGlobal -- Returns true if the line is a global record: either
    //   and empty record, a global comment or a reference record.
    '''
    @property
    def isGlobal(self) -> bool:
        return self.isEmpty or self.isGlobalComment

    '''
    //////////////////////////////
    //
    // HumdrumLine::isManipulator -- Returns true if any tokens on the line are
    //   manipulator interpretations.  Only null interpretations are allowed on
    //   lines which contain manipulators, but the parser currently does not
    //   enforce this rule.
    '''
    @property
    def isManipulator(self) -> bool:
        for token in self._tokens:
            if token.isManipulator:
                return True
        return False

    '''
    //////////////////////////////
    //
    // HumdrumLine::isEmpty -- Returns true if no characters on line.  A blank line
    //   is technically disallowed in the classic Humdrum Toolkit programs, but it
    //   is usually tolerated.  In humlib (and HumdrumExtras) empty lines with
    //   no content (not even space characters) are allowed and treated as a
    //   special class of line.
    '''
    @property
    def isEmpty(self) -> bool:
        return self.text == ''

    '''
    //////////////////////////////
    //
    // HumdrumLine::getTokenCount --  Returns the number of tokens on the line.
    //     This value is set by HumdrumFileBase in analyzeTokens.
    '''
    @property
    def tokenCount(self) -> int:
        return len(self._tokens)

    '''
    //////////////////////////////
    //
    // HumdrumLine::createTokensFromLine -- Chop up a HumdrumLine string into
    //     individual tokens.
    '''
    def createTokensFromLine(self) -> int: # returns number of tokens created
        '''
        // delete previous tokens (will need to re-analyze structure
        // of file after this).
        '''
        self._tokens = []
        self._numTabsAfterToken = []

        if self.text == '':
            # one empty token
            token = HumdrumToken()
            token.ownerLine = self
            self._tokens = [token]
            self._numTabsAfterToken = [0]
            return 1

        if self.text.startswith('!!'):
            # global, so just one token for the whole line
            token = HumdrumToken(self.text)
            token.ownerLine = self
            self._tokens = [token]
            self._numTabsAfterToken = [0]
            return 1

        tokenStrList: [str] = self.text.split('\t')
        for tokenStr in tokenStrList:
            token = HumdrumToken(tokenStr)
            token.ownerLine = self
            self._tokens.append(token)
            self._numTabsAfterToken.append(1)

#         for m in re.finditer(r'([^\t]+)(\t*)', self.text):
#             # m is a match object containing two groups: first the token, then any trailing tabs
#             tokenStr = m.group(1)
#             if tokenStr is None:
#                 break
#
#             tabsStr = m.group(2)
#             if tabsStr is None:
#                 numTabsAfterThisToken = 0
#             else:
#                 numTabsAfterThisToken = len(tabsStr)
#
#             token = HumdrumToken(tokenStr)
#             token.ownerLine = self
#             self._tokens.append(token)
#             self._numTabsAfterToken.append(numTabsAfterThisToken)

        return len(self._tokens)


    '''
    //////////////////////////////
    //
    // HumdrumLine::createLineFromTokens --  Re-generate a HumdrumLine string from
    //    individual tokens on the line.  This function will be necessary to
    //    run before printing a HumdrumFile if you have changed any tokens on the
    //    line.  Otherwise, changes in the tokens will not be passed on to the
    ///   printing of the line.
    '''
    def createLineFromTokens(self):
        # 1. make sure that _numTabsAfterToken is full by appending hard-coded values (mostly 1s)
        numEntriesNeeded = len(self._tokens) - len(self._numTabsAfterToken)
        if numEntriesNeeded > 0:
            self._numTabsAfterToken += [1] * (numEntriesNeeded - 1)
            self._numTabsAfterToken += [0] # zero tabs after the last token, please

        # 2. repair any zeroes in _numTabsAfterToken to be ones (except the last one)
        for i in range(0, len(self._numTabsAfterToken)-1):
            if self._numTabsAfterToken[i] == 0:
                self._numTabsAfterToken[i] = 1

        # 3. construct self.text by concatenating all tokens, separated by the
        #       appropriate number of tabs
        self.text = ''
        for i, token in enumerate(self._tokens):
            self.text += token.text
            self.text += '\t' * self._numTabsAfterToken[i]

    '''
    //////////////////////////////
    //
    // HumdrumLine::addExtraTabs -- Adds extra tabs between primary spines so that the
    //    first token of a spine is vertically aligned.  The input array to this
    //    function is a list of maximum widths.  This is typically caluclated by
    //    HumdrumFileBase::getTrackWidths().  The first indexed value is unused,
    //    since there is no track 0.
    '''
    def addExtraTabs(self, trackWidths: [int]):
        if not self.hasSpines:
            return

        localWidths = [0] * len(trackWidths)

        # start with 1 tab after every token
        self._numTabsAfterToken = [1] * len(self._numTabsAfterToken)

        lastTrack: int = 0
        thisTrack: int = 0
        for j, token in enumerate(self._tokens):
            lastTrack = thisTrack
            thisTrack = token.track
            if thisTrack != lastTrack and lastTrack > 0:
                diff = trackWidths[lastTrack] - localWidths[lastTrack]
                if diff > 0 and j > 0:
                    self._numTabsAfterToken[j-1] += diff

            localWidths[thisTrack] += 1

    '''
    //////////////////////////////
    //
    // HumdrumLine::analyzeTokenDurations -- Calculate the duration of
    //    all tokens on a line.
    '''
    def analyzeTokenDurations(self) -> bool:
        if not self.hasSpines:
            return True

        for token in self._tokens:
            token.analyzeDuration()

        return True

    '''
    //////////////////////////////
    //
    // HumdrumLine::analyzeTracks -- Calculate the subtrack info for subspines.
    //   Subtracks index subspines strictly from left to right on the line.
    //   Subspines can be exchanged and be represented left to right out of
    //   original order.
    '''
    def analyzeTracks(self) -> bool:
        if not self.hasSpines:
            return True

        maxTrack = 0
        for token in self._tokens:
            track = 0
            # use re to get the integer track number from e.g. '(((3)b)a)b'
            m = re.match(r'\(*(\d+)', token.spineInfo)
            if m is not None:
                trackStr = m.group(1)
                if trackStr is not None:
                    track = int(trackStr)

            if maxTrack < track:
                maxTrack = track

            token.track = track

        subTracks = [0] * (maxTrack+1)
        currSubTrack = [0] * (maxTrack+1)

        for token in self._tokens:
            subTracks[token.track] += 1

        for token in self._tokens:
            tokenTrack: int = token.track
            if subTracks[tokenTrack] > 1:
                currSubTrack[tokenTrack] += 1
                token.subTrack = currSubTrack[tokenTrack]
            else:
                token.subTrack = 0

        return True

    '''
    //////////////////////////////
    //
    // HumdrumLine::printTrackInfo -- Print the analyzed track information.
    //     The first (left-most) spine in a Humdrum file is track 1, the
    //     next is track 2, etc.  The track value is shared by all subspines,
    //     so there may be duplicate track numbers on a line if the spine
    //     has split.  When the spine splits, a subtrack number is given
    //     after a "." character in the printed output from this function.
    //     Subtrack==0 means that there is only one subtrack.
    //     Examples:
    //         "1"  == Track 1, subtrack 1 (and there are no more subtracks)
    //          "1.1" == Track 1, subtrack 1 (and there are more subtracks)
    //          "1.2" == Track 1, subtrack 2 (and there may be more subtracks)
    //          "1.10" == Track 1, subtrack 10 (and there may be subtracks)
    //     Each starting exclusive interpretation is assigned to a unique
    //     track number.  When a *+ manipulator is given, the new exclusive
    //     interpretation on the next line is give the next higher track
    //     number.
    //
    // default value: out = cout
    '''
    def printTrackInfo(self):
        if self.isManipulator:
            print(self.text, file=sys.stderr)
            return

        for i, token in enumerate(self._tokens):
            print(token.trackString, end='', file=sys.stderr)
            if i < len(self._tokens) - 1:
                print('\t', end='', file=sys.stderr)


    '''
    //////////////////////////////
    //
    // HumdrumLine::getOwner -- Return the HumdrumFile which manages
    //   (owns) this line.
    '''
    @property
    def ownerFile(self): # -> HumdrumFile
        return self._ownerFile

    '''
    //////////////////////////////
    //
    // HumdrumLine::setOwner -- store a pointer to the HumdrumFile which
    //    manages (owns) this object.
    '''
    @ownerFile.setter
    def ownerFile(self, newOwnerFile): # newOwnerFile: HumdrumFile
        self._ownerFile = newOwnerFile

    '''
    //////////////////////////////
    //
    // HumdrumLine::addLinkedParameter --
    '''
    def addLinkedParameter(self, token: HumdrumToken) -> int:
        for i, paramToken in enumerate(self._linkedParameters):
            if paramToken == token:
                return i

        self._linkedParameters.append(token)
        return len(self._linkedParameters) - 1

    '''
    //////////////////////////////
    //
    // HumdrumLine::setLayoutParameters -- Takes a global comment with
    //     the structure:
    //        !!LO:NS2:key1=value1:key2=value2:key3=value3
    //     and stores it in the HumHash parent class of the line.
    '''
    def setLayoutParameters(self):
        if not self.text.startswith('!!LO:'):
            return
        self.setParameters(self.text[2:]) # strip off the leading '!!'

    '''
    //////////////////////////////
    //
    // HumdrumLine::setParameters -- Store global parameters in the first token
    //    of the line.  Also add a marker at ("","","global","true") to indicate
    //    that the parameters are global rather than local.  (Global text directions
    //    will behave differently from local text directions, for example).
    '''
    def setParameters(self, pdata: str): # pdata is 'LO:blah:bleah=value' (no leading '!' or '!!')
        pieces: [str] = pdata.split(':')
        if len(pieces) < 3:
            return

        ns1: str = pieces[0]
        ns2: str = pieces[1]
        key: str = ''
        value: str = ''

        for i in range(2, len(pieces)):
            piece = re.sub('&colon', ':', pieces[i])
            keyAndValue: [str] = piece.split('=')

            key = keyAndValue[0]
            if len(keyAndValue) == 1:
                value = 'true'
            else:
                value = keyAndValue[1]
            self._tokens[0].setValue(ns1, ns2, key, value)

        self._tokens[0].setValue('global', 'true')

    '''
    // HumdrumLine::appendToken -- add a token at the end of the current
    //      list of tokens in the line.

        Q: shouldn't this also set ownerLine on the token? especially if it was a string
    '''
    def appendToken(self, token, tabCount: int = 0): # token can be HumdrumToken or str
        if isinstance(token, str):
            token = HumdrumToken(token)
        self._tokens.append(token)
        self._numTabsAfterToken.append(tabCount)

    '''
    //////////////////////////////
    //
    // HumdrumLine::insertToken -- Add a token before the given token position.
    '''
    def insertToken(self, index: int, token, tabCount: int): # token can be HumdrumToken or str
        if isinstance(token, HumdrumToken):
            self._tokens.insert(index, token)
            self._numTabsAfterToken.insert(index, tabCount)
            return
        if isinstance(token, str):
            self._tokens.insert(index, HumdrumToken(token))
            self._numTabsAfterToken.insert(index, tabCount)

    '''
    //////////////////////////////
    //
    // HumdrumLine::getKernNoteAttacks -- Return the number of kern notes
    //    that attack on a line.
    '''
    @property
    def numKernNoteAttacks(self) -> int:
        output: int = 0
        for token in self._tokens:
            if not token.isKern:
                continue
            if token.isNoteAttack:
                output += 1
        return output

    '''
    //////////////////////////////
    //
    // HumdrumLine::storeGlobalLinkedParameters --
    '''
    def storeGlobalLinkedParameters(self):
        if self._tokens:
            self._tokens[0].storeParameterSet()

    '''
    //////////////////////////////
    //
    // HumdrumLine::getBarNumber -- return the bar number on the line.
    //    If the line is not a bar line, then return -1.  If there is
    //    no number at any token position on the line then return -1.
    '''
    @property
    def barNumber(self) -> int:
        if not self.isBarline:
            return -1

        for token in self._tokens:
            barnum = -1
            # use re to get the integer bar number from e.g. '=5-'
            m = re.match(r'=(\d+)', token.text)
            if m is not None:
                barnumStr = m.group(1)
                if barnumStr is not None:
                    barnum = int(barnumStr)
                    return barnum

        return -1

    '''
    //////////////////////////////
    //
    // HumdrumLine::allSameStyle -- return true if barlines through all
    //     staves are the same. Requires HumdrumFile::analyzeBarlines() to be
    //     run first.
    '''
    @property
    def allSameBarlineStyle(self) -> bool:
        return not self.getValueBool('auto', 'barlinesDifferent')