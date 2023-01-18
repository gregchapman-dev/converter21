# ------------------------------------------------------------------------------
# Name:          HumdrumToken.py
# Purpose:       Represents a single field in a line of a Humdrum file
#                The intersection of line and spine, if you will...
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
import copy
import typing as t
from fractions import Fraction

from music21.common import opFrac

from converter21.humdrum import HumAddress
from converter21.humdrum import HumNum, HumNumIn
from converter21.humdrum import HumHash
from converter21.humdrum import HumParamSet
from converter21.humdrum import Convert

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

# spine manipulators:
SPLIT_TOKEN: str = '*^'
MERGE_TOKEN: str = '*v'
EXCHANGE_TOKEN: str = '*x'
TERMINATE_TOKEN: str = '*-'
ADD_TOKEN: str = '*+'
# Also exclusive interpretations which start with '**' followed by the data type.

# other special tokens:
NULL_DATA: str = '.'
NULL_INTERPRETATION: str = '*'
NULL_COMMENT_LOCAL: str = '!'
NULL_COMMENT_GLOBAL: str = '!!'

# regex patterns
KEY_DESIGNATION_PATTERN: str = r'^\*([a-gA-G][#-]*):([a-z]{3})?'

# stria stuff
DEFAULT_LINES_PER_STAFF: int = 5
MAX_LINES_PER_STAFF: int = 32

def makeTag(string: str, num: int) -> str:
    if num > 1:
        return string + str(num)
    return string

# used to generate invisible rests to fill gaps.  Not a real HumdrumToken, but can be put
# in arrays of layerTokens, and will be specially treated.
class FakeRestToken(HumHash):
    # some attributes so we can be treated (a bit) like a real HumdrumToken
    isFakeRest: bool = True  # HumdrumToken.isFakeRest == False
    isBarline: bool = False
    isExclusiveInterpretation: bool = False

    def __init__(self, duration: HumNumIn, durationFromBarline: HumNumIn = 0) -> None:
        super().__init__()  # initialize the HumHash fields
        self.duration: HumNum = opFrac(duration)
        self.durationFromBarline: HumNum = opFrac(durationFromBarline)

# We use conditionally defined attributes to implement property caching, so make pylint shut up
# about it
# pylint: disable=attribute-defined-outside-init

class HumdrumToken(HumHash):
    isFakeRest: bool = False  # FakeRestToken.isFakeRest == True

    # phrase vs. slur
    PHRASE: str = '{'
    SLUR: str = '('

    def __init__(self, token: t.Optional[str] = '') -> None:
        super().__init__()  # initialize the HumHash fields

        '''
            _text: the token's text string
        '''
        self._text: str = token if token is not None else ''

        self._subtokens: t.List[str] = []
        self._subtokensGenerated: bool = False

        '''
        // address: The address contains information about the location of
        // the token on a HumdrumLine and in a HumdrumFile.
        '''
        self._address: HumAddress = HumAddress()


        '''
        // duration: The duration of the token.  Non-rhythmic data types
        // will have a negative duration (which should be interpreted
        // as a zero duration--See HumdrumToken::hasRhythm()).
        // Grace note will have a zero duration, even if they have a duration
        // list in the token for a graphical display duration.
        '''
        self._duration: HumNum = opFrac(-1)

        # graceVisualDuration: only set for grace notes that have recip in their token
        # e.g. '16qqcc'.  self._duration is 0 (because it's a grace note), but the grace
        # note will have two flags because of the '16'.
        self._graceVisualDuration: HumNum = opFrac(-1)

        '''
        // nextTokens: This is a list of all previous tokens in the spine which
        // immediately follow this token. Typically there will be one
        // following token, but there can be two tokens if the current
        // token is *^, and there will be zero following tokens after a
        // spine terminating token (*-).
        '''
        self._nextTokens: t.List[HumdrumToken] = []

        # contains nextToken(0), for speed
        self._nextToken0: t.Optional[HumdrumToken] = None

        '''
        // previousTokens: Simiar to nextTokens, but for the immediately
        // preceding token(s) in the data.  Typically there will be one
        // preceding token, but there can be multiple tokens when the previous
        // line has *v merge tokens for the spine.  Exclusive interpretations
        // have no tokens preceding them.
        '''
        self._previousTokens: t.List[HumdrumToken] = []

        # contains previousToken(0), for speed
        self._previousToken0: t.Optional[HumdrumToken] = None

        '''
        // nextNonNullDataTokens: This is a list of non-null tokens in the spine
        // that follow this one.
        '''
        self._nextNonNullDataTokens: t.List[HumdrumToken] = []

        '''
        // previousNonNullDataTokens: This is a list of non-null tokens in the spine
        // that precede this one.
        '''
        self._previousNonNullDataTokens: t.List[HumdrumToken] = []

        '''
        // rhycheck: Used to perform HumdrumFileStructure::analyzeRhythm
        // recursively.
        '''
        self._rhythmAnalysisState: int = 0

        '''
        // strand: Used to keep track of contiguous voice connections between
        // secondary spines/tracks.  This is the 1-D strand index number
        // (not the 2-d one).
        '''
        self._strandIndex: int = -1

        '''
        // m_nullresolve: used to point to the token that a null token
        // refers to.
        '''
        self._nullResolution: t.Optional[HumdrumToken] = None

        '''
        // m_linkedParameterTokens: List of Humdrum tokens which are parameters
        // (mostly only layout parameters at the moment).
        '''
        self._linkedParameterTokens: t.List[HumdrumToken] = []

        '''
        // m_parameterSet: A single parameter encoded in the text of the
        // token.  Was previously called m_linkedParameter.
        '''
        self._parameterSet: t.Optional[HumParamSet] = None

        '''
        // m_rhythm_analyzed: Set to true when HumdrumFile assigned duration
        '''
        self._rhythmAnalyzed: bool = False

        '''
        // m_strophe: Starting point of a strophe that the token belongs to.
        // NULL means that it is not in a strophe.
        '''
        self._strophe: t.Optional[HumdrumToken] = None

        '''
            rscale: the rscale that applies to this token
        '''
        self._rscale: HumNum = opFrac(1)

        '''
            We are also a HumHash, and that was initialized via super() above.
            But we want our default HumHash prefix to be '!', not ''
        '''
        self.prefix: str = '!'

        self._atLeastOneCachedTokenTextPropertyExists: bool = False
        self._atLeastOneCachedDataTypePropertyExists: bool = False

    # In C++ a HumdrumToken is also a string().  Deriving a mutable class from an immutable
    # base class in Python is trickier than I can manage. So we have a standard "conversion"
    # to string instead.  print("hdToken =", hdToken) will call this automatically, for example.
    # But most clients will need to call str(hdToken), or hdToken.text to "cast" to string.
    def __str__(self) -> str:
        return self.text

    # Now the actual HumdrumToken APIs/properties

    cachedTokenTextProperties: t.Set[str] = {
        '_isDataCached',
        '_isInterpretationCached',
        '_isNonNullDataCached',
        '_isNullDataCached',
        '_isNullCached',
        '_isBarlineCached',
        '_isCommentCached',
        '_isLocalCommentCached',
        '_isGlobalCommentCached',
        '_isLabelCached',
        '_isChordCached',
        '_isExclusiveInterpretationCached',
        '_isSplitInterpretationCached',
        '_isMergeInterpretationCached',
        '_isExchangeInterpretationCached',
        '_isTerminateInterpretationCached',
        '_isAddInterpretationCached',
        '_isManipulatorCached',
        '_isRecipOnlyCached',
        '_hasBeamCached',
        '_hasFermataCached',
        '_isStaffInterpretationCached',
        '_isPartCached',
        '_isGroupCached',
        '_isRestCached',
        '_isNoteCached'
    }

    cachedDataTypeProperties: t.Set[str] = {
        '_isKernCached',
        '_isRecipCached',
        '_isMensCached',
        '_hasRhythmCached',
        '_isStaffDataTypeCached',
        '_isRestCached',
        '_isNoteCached'
    }

    # Note that _isRestCached/_isNoteCached is in both lists, since it is a TokenText property,
    # but it also is parsed differently for different dataTypes.
    def _clearCachedTokenTextProperties(self) -> None:
        # we delete these attributes instead of setting them to None, to
        # avoid the cost of clearing cached properties during __init__
        # (the attributes do not exist, by default)
        if self._atLeastOneCachedTokenTextPropertyExists:
            for attrib in self.cachedTokenTextProperties:
                self.__dict__.pop(attrib, None)
            self._atLeastOneCachedTokenTextPropertyExists = False

    def _clearCachedDataTypeProperties(self) -> None:
        # we delete these attributes instead of setting them to None, to
        # avoid the cost of clearing cached properties during __init__
        # (the attributes do not exist, by default)
        if self._atLeastOneCachedDataTypePropertyExists:
            for attrib in self.cachedDataTypeProperties:
                self.__dict__.pop(attrib, None)
            self._atLeastOneCachedDataTypePropertyExists = False

    '''
    //////////////////////////////
    //
    // HumdrumToken::getText --
    '''
    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, newText: str) -> None:
        self._text = newText
        self._subtokensGenerated = False
        if self._atLeastOneCachedTokenTextPropertyExists:
            self._clearCachedTokenTextProperties()

    '''
    //////////////////////////////
    //
    // HumdrumToken::getPreviousNonNullDataTokenCount -- Returns the number of
    //   previous tokens in the spine which is not a null token.  For null
    //   tokens, this will be a count of the number of non-null tokens which
    //   the null represents.
    // @SEEALSO: getPreviousNonNullDataToken
    '''
    @property
    def previousNonNullDataTokenCount(self) -> int:
        return len(self._previousNonNullDataTokens)

    @property
    def previousNonNullDataTokens(self) -> t.List['HumdrumToken']:
        return self._previousNonNullDataTokens

    '''
    //////////////////////////////
    //
    // HumdrumToken::insertTokenAfter -- Insert the given token after this token.
    //    This will sever the link from this token to its next token.  There is only
    //    presumed to be one next token, at least for the moment.
    '''
    def insertTokenAfter(self, newToken: 'HumdrumToken') -> None:
        if self._nextTokens == []:
            self._nextTokens.append(newToken)
            self.updateNextToken0()
        else:
            oldNextToken: HumdrumToken = self.nextTokens[0]
            self.nextTokens[0] = newToken
            self.updateNextToken0()

            newToken.previousTokens = [self]
            newToken.updatePreviousToken0()
            newToken.nextTokens = [oldNextToken]
            newToken.updateNextToken0()

            if oldNextToken.previousTokens == []:
                oldNextToken.previousTokens.append(newToken)
            else:
                oldNextToken.previousTokens[0] = newToken
            oldNextToken.updatePreviousToken0()

    '''
    //////////////////////////////
    //
    // HumdrumToken::getPreviousNonNullDataToken -- Returns the non-null
    //    data token which occurs before this token in the data in the same
    //    spine.  The default value is index 0, since mostly there will only
    //    be one previous token.
    '''
    def getPreviousNonNullDataToken(self, index: int = 0) -> t.Optional['HumdrumToken']:
        # handle Python-style negative indexing
        if index < 0:
            index += self.previousNonNullDataTokenCount

        if index < 0:
            return None

        if index >= self.previousNonNullDataTokenCount:
            return None

        return self._previousNonNullDataTokens[index]

    '''
    //////////////////////////////
    //
    // HumdrumToken::getNextNonNullDataTokenCount -- Returns the number of non-null
    //     data tokens which follow this token in the spine.
    '''
    @property
    def nextNonNullDataTokenCount(self) -> int:
        return len(self._nextNonNullDataTokens)

    @property
    def nextNonNullDataTokens(self) -> t.List['HumdrumToken']:
        return self._nextNonNullDataTokens

    '''
    //////////////////////////////
    //
    // HumdrumToken::getNextNonNullDataToken -- Returns the given next non-null token
    //    following this one in the spine.  The default value for index is 0 since
    //    the next non-null data token count will typically be 1.
    '''
    def getNextNonNullDataToken(self, index: int = 0) -> t.Optional['HumdrumToken']:
        # handle Python-style negative indexing
        if index < 0:
            index += self.nextNonNullDataTokenCount

        if index < 0:
            return None

        if index >= self.nextNonNullDataTokenCount:
            return None

        return self._nextNonNullDataTokens[index]

    '''
    //////////////////////////////
    //
    // HumdrumToken::getSlurDuration -- If the note has a slur start, then
    //    returns the duration until the endpoint; otherwise, returns 0;
    //    Expand later to handle slur ends and elided slurs.  The function
    //    HumdrumFileContent::analyzeSlurs() should be called before accessing
    //    this function.  If the slur duration was already calculated, return
    //    that value; otherwise, calculate from the location of a matching
    //    slur end.
    '''
    def getSlurDuration(self, scale: HumNumIn) -> HumNum:
        if not self.isKern:
            return opFrac(0)

        if self.isDefined('auto', 'slurDuration'):
            return self.getValueHumNum('auto', 'slurDuration')

        if self.isDefined('auto', 'slurEnd'):
            slurEndToken = self.getValueToken('auto', 'slurEnd')
            if slurEndToken is not None:
                return opFrac(
                    slurEndToken.getScaledDurationFromStart(scale)
                    - self.getScaledDurationFromStart(scale)
                )

        return opFrac(0)

    '''
    //////////////////////////////
    //
    // HumdrumToken::getDataType -- Get the exclusive interpretation type for
    //     the token.
    // @SEEALSO: isDataType
    '''
    @property
    def dataType(self) -> 'HumdrumToken':
        return self._address.dataType

    '''
    //////////////////////////////
    //
    // HumdrumToken::isDataType -- Returns true if the data type of the token
    //   matches the test data type.
    // @SEEALSO: getDataType getKern
    '''
    def isDataType(self, dtype: str) -> bool:
        if dtype.startswith('**'):
            return dtype == self.dataType.text

        return dtype == self.dataType.text[2:]

    '''
    //////////////////////////////
    //
    // HumdrumToken::isKern -- Returns true if the data type of the token
    //    is **kern.
    // @SEEALSO: isDataType
    '''
    @property
    def isKern(self) -> bool:
        # cache the result for performance
        try:
            return self._isKernCached
        except AttributeError:
            self._isKernCached: bool = self.isDataType('**kern')
            self._atLeastOneCachedDataTypePropertyExists = True
        return self._isKernCached

    '''
        isRecip -- Returns true if the data type of the token is **recip
    '''
    @property
    def isRecip(self) -> bool:
        # cache the result for performance
        try:
            return self._isRecipCached
        except AttributeError:
            self._isRecipCached: bool = self.isDataType('**recip')
            self._atLeastOneCachedDataTypePropertyExists = True
        return self._isRecipCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isMens -- Returns true if the data type of the token
    //    is **mens.
    // @SEEALSO: isDataType
    '''
    @property
    def isMens(self) -> bool:
        # cache the result for performance
        try:
            return self._isMensCached
        except AttributeError:
            self._isMensCached: bool = self.isDataType('**mens')
            self._atLeastOneCachedDataTypePropertyExists = True
        return self._isMensCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::getSpineInfo -- Returns the spine split/merge history
    //    for the token.
    // @SEEALTO: setSpineInfo
    '''
    @property
    def spineInfo(self) -> str:
        return self._address.spineInfo

    @spineInfo.setter
    def spineInfo(self, newSpineInfo: str) -> None:
        self._address.spineInfo = newSpineInfo

    '''
    //////////////////////////////
    //
    // HumdrumToken::getLineIndex -- Returns the line index of the owning
    //    HumdrumLine for this token.
    // @SEEALTO: getLineNumber
    '''
    @property
    def lineIndex(self) -> int:
        return self._address.lineIndex

    '''
    //////////////////////////////
    //
    // HumdrumToken::getLineNumber -- Returns the line index plus 1.
    // @SEEALTO: getLineIndex
    '''
    @property
    def lineNumber(self) -> int:
        return self._address.lineNumber

    '''
    //////////////////////////////
    //
    // HumdrumToken::getFieldIndex -- Returns the index of the token the line.
    // @SEEALSO: getFieldIndex
    '''
    @property
    def fieldIndex(self) -> int:
        return self._address.fieldIndex

    @fieldIndex.setter
    def fieldIndex(self, newFieldIndex: int) -> None:
        self._address.fieldIndex = newFieldIndex

    '''
    //////////////////////////////
    //
    // HumdrumToken::getFieldNumber -- Returns the index +1 of the token the line
    // @SEEALSO: getFieldNumber
    '''
    @property
    def fieldNumber(self) -> int:
        return self._address.fieldNumber

    '''
    //////////////////////////////
    //
    // HumdrumToken::getTrack -- Get the track (similar to a staff in MEI).
    '''
    @property
    def track(self) -> t.Optional[int]:
        # trackNum is a data member; cheaper than using the track property
        return self._address.trackNum

    @track.setter
    def track(self, track: t.Optional[int]) -> None:
        # here we set track via address property for the checks
        self._address.track = track
        if self._atLeastOneCachedDataTypePropertyExists:
            # some cached properties depend on dataType,
            # which depends on ownerLine and track
            self._clearCachedDataTypeProperties()
    '''
    //////////////////////////////
    //
    // HumdrumToken::getSubtrack -- Get the subtrack (similar to a layer
    //    in MEI).
    '''
    @property
    def subTrack(self) -> int:
        return self._address.subTrack

    @subTrack.setter
    def subTrack(self, newSubTrack: int) -> None:
        self._address.subTrack = newSubTrack

    @property
    def subTrackCount(self) -> int:
        return self._address.subTrackCount

    @subTrackCount.setter
    def subTrackCount(self, newSubTrackCount: int) -> None:
        self._address.subTrackCount = newSubTrackCount

    @property
    def rscale(self) -> HumNum:
        return self._rscale

    @rscale.setter
    def rscale(self, newRscale: HumNumIn) -> None:
        self._rscale = opFrac(newRscale)

    '''
    //////////////////////////////
    //
    // HumdrumToken::getNextTokens -- Returns a list of the next
    //   tokens in the spine after this token.
    // @SEEALSO: getNextToken
    '''
    @property
    def nextTokens(self) -> t.List['HumdrumToken']:
        return self._nextTokens

    @nextTokens.setter
    def nextTokens(self, newNextTokens: t.List['HumdrumToken']) -> None:
        self._nextTokens = newNextTokens
        self.updateNextToken0()

    '''
    //////////////////////////////
    //
    // HumdrumToken::getNextToken -- Returns the next token in the
    //    spine.  Since the next token count is usually one, the default
    //    index value is zero.  When there is no next token (when the current
    //    token is a spine terminaor), then NULL will be returned.
    // default value: index = 0
    // @SEEALSO: getNextTokens, getPreviousToken
    '''
    def nextToken(self, index: int) -> t.Optional['HumdrumToken']:
        if 0 <= index < len(self._nextTokens):
            return self._nextTokens[index]
        return None

    @property
    def nextToken0(self) -> t.Optional['HumdrumToken']:
        return self._nextToken0

    def updateNextToken0(self) -> None:
        self._nextToken0 = self.nextToken(0)

    '''
    //////////////////////////////
    //
    // HumdrumToken::addNextNonNullToken --
    '''
    def addNextNonNullDataToken(self, token: 'HumdrumToken') -> None:
        if token is None:
            return

        if token in self._nextNonNullDataTokens:
            return

        self._nextNonNullDataTokens.append(token)

    '''
    //////////////////////////////
    //
    // HumdrumToken::getPreviousToken -- Returns the previous token in the
    //    spine.  Since the previous token count is usually one, the default
    //    index value is zero.
    // default value: index = 0
    '''
    def previousToken(self, index: int) -> t.Optional['HumdrumToken']:
        if 0 <= index < len(self._previousTokens):
            return self._previousTokens[index]
        return None

    @property
    def previousToken0(self) -> t.Optional['HumdrumToken']:
        return self._previousToken0

    @property
    def previousTokenN(self) -> t.Optional['HumdrumToken']:
        if self._previousTokens:
            return self._previousTokens[-1]
        return None

    def updatePreviousToken0(self) -> None:
        self._previousToken0 = self.previousToken(0)

    '''
    //////////////////////////////
    //
    // HumdrumToken::getPreviousTokens -- Returns a list of the previous
    //    tokens in the spine before this token.
    '''
    @property
    def previousTokens(self) -> t.List['HumdrumToken']:
        return self._previousTokens

    @previousTokens.setter
    def previousTokens(self, newPreviousTokens: t.List['HumdrumToken']) -> None:
        self._previousTokens = newPreviousTokens
        self.updatePreviousToken0()

    '''
    //////////////////////////////
    //
    // HumdrumToken::getNextFieldToken --
        This returns the token representing the next field in the ownerLine of this token --gregc
    '''
    @property
    def nextFieldToken(self) -> t.Optional['HumdrumToken']:
        from converter21.humdrum import HumdrumLine
        self.ownerLine: HumdrumLine
        if self.ownerLine is None:
            return None
        if self.fieldIndex >= self.ownerLine.tokenCount - 1:
            return None
        return self.ownerLine[self.fieldIndex + 1]

    '''
    //////////////////////////////
    //
    // HumdrumToken::getPreviousFieldToken --
        This returns the token representing the previous field in the ownerLine of this token
    '''
    @property
    def previousFieldToken(self) -> t.Optional['HumdrumToken']:
        if self.ownerLine is None:
            return None
        if self.fieldIndex < 1:
            return None
        return self.ownerLine[self.fieldIndex - 1]

    '''
    //////////////////////////////
    //
    // HumdrumToken::analyzeDuration -- Currently reads the duration of
    //   **kern and **recip data.  Add more data types here such as **koto.
    '''
    def analyzeDuration(self) -> None:
        self._rhythmAnalyzed = True

        if self.text == NULL_DATA:
            self._duration = opFrac(-1)
            return

        if self.isComment:
            self._duration = opFrac(-1)
            return

        if self.isInterpretation:
            self._duration = opFrac(-1)
            return

        if self.isBarline:
            self._duration = opFrac(-1)
            return

        if self.hasRhythm:
            if self.isNonNullData:
                if self.isKern:
                    self._duration = Convert.recipToDuration(self.text)
                    if self.isGrace:
                        recipWithoutQsOrDots: str = self.text.replace('q', '').replace('.', '')
                        self._graceVisualDuration = Convert.recipToDuration(recipWithoutQsOrDots)
                elif self.isRecip:
                    self._duration = Convert.recipToDuration(self.text)
                elif self.isMens:
                    self._duration = Convert.mensToDuration(self.text)
                else:
                    # LATER: **koto not supported...
                    self._duration = opFrac(-1)
            else:
                self._duration = opFrac(-1)
        else:
            self._duration = opFrac(-1)

    '''
    ///////////////////////////////
    //
    // HumdrumToken::isManipulator -- Returns true if token is one of:
    //    SPLIT_TOKEN     = "*^"  == spine splitter
    //    MERGE_TOKEN     = "*v"  == spine merger
    //    EXCHANGE_TOKEN  = "*x"  == spine exchanger
    //    ADD_TOKEN       = "*+"  == spine adder
    //    TERMINATE_TOKEN = "*-"  == spine terminator
    //    **...  == exclusive interpretation
    '''
    @property
    def isManipulator(self) -> bool:
        # cache the result for performance
        try:
            return self._isManipulatorCached
        except AttributeError:
            self._isManipulatorCached: bool = (
                self.isSplitInterpretation
                or self.isMergeInterpretation
                or self.isExchangeInterpretation
                or self.isAddInterpretation
                or self.isTerminateInterpretation
                or self.isExclusiveInterpretation
            )
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isManipulatorCached

    '''
        isRecipOnly returns True if the token is just a recip 'value', like you would normally
        see in a **recip spine.  This is in support of such tokens in **kern, where they are
        (apparently) intended to be invisible rests.  See rds-scores/R415_Web-s28p2-3m11-19.krn,
        measure 19, where the right hand Piano staff has a triplet-eighth set of 3 such tokens
        ('12').  Without making these into invisible rests, music21 ends up thinking it's a
        short measure.
    '''
    @property
    def isRecipOnly(self) -> bool:
        # cache the result for performance
        try:
            return self._isRecipOnlyCached
        except AttributeError:
            self._isRecipOnlyCached: bool = (
                re.match(r'^[\d]+(%[\d]+)?[.]*$', self.text) is not None
            )
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isRecipOnlyCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::getDuration -- Returns the duration of the token.  The token
    //    does not necessarily need to have any explicit duration, as the returned
    //    value will also include implicit duration calculated in analyzeRhythm
    //    in the HumdrumFileStructure class.
    '''
    def scaledDuration(self, scale: HumNumIn) -> HumNum:
        # self.duration will trigger rhythm analysis if necessary
        return opFrac(self.duration * opFrac(scale))

    @property
    def duration(self) -> HumNum:
        if not self._rhythmAnalyzed:
            self.analyzeDuration()

        return self._duration

    @duration.setter
    def duration(self, newDuration: HumNumIn) -> None:
        self._rhythmAnalyzed = True
        self._duration = opFrac(newDuration)

    @property
    def graceVisualDuration(self) -> HumNum:
        if not self._rhythmAnalyzed:
            self.analyzeDuration()

        return self._graceVisualDuration

    '''
    //////////////////////////////
    //
    // HumdrumToken::getDots -- Count the number of '.' characters in token string.
    //    Terminating the count at the first occurrence of the separator character,
    //    which is by default a space character.
    '''
    @property
    def dotCount(self) -> int:
        count: int = 0

        for ch in self.text:
            if ch == '.':
                count += 1
            if ch == ' ':
                break

        return count

    '''
    //////////////////////////////
    //
    // HumdrumToken::getDurationNoDots -- Return the duration of the
    //   note excluding any dots.
    '''
    @property
    def durationNoDots(self) -> HumNum:
        dotCount: int = self.dotCount
        if dotCount == 0:
            return self.duration

        bot: int = int(pow(2.0, dotCount + 1)) - 1
        top: int = int(pow(2.0, dotCount))
        dotMultiplier: HumNum = opFrac(Fraction(top, bot))
        return opFrac(self.duration * dotMultiplier)

    def scaledDurationNoDots(self, scale: HumNumIn) -> HumNum:
        return opFrac(self.durationNoDots * opFrac(scale))

    '''
    //////////////////////////////
    //
    // HumdrumToken::getDurationFromStart -- Returns the duration from the
    //   start of the owning HumdrumFile to the starting time of the
    //   owning HumdrumLine for the token.  The durationFromStart is
    //   in reference to the start of the token, not the end of the token,
    //   which may be on another HumdrumLine.
    '''
    def getScaledDurationFromStart(self, scale: HumNumIn) -> HumNum:
        lineDur = self.ownerLine.durationFromStart
        return opFrac(lineDur * opFrac(scale))

    ''' durationFromStart property for unscaled getDurationFromStart --gregc '''
    @property
    def durationFromStart(self) -> HumNum:
        return self.ownerLine.durationFromStart

    '''
    //////////////////////////////
    //
    // HumdrumToken::getDurationToEnd -- Returns the duration from the
    //   start of the current line to the start of the last line
    //   (the duration of the last line is always zero, so the duration
    //   to end is always the duration to the end of the last non-zero
    //   duration line.
    '''
    def getScaledDurationToEnd(self, scale: HumNumIn) -> HumNum:
        if self.ownerLine is None:  # bugfix, but current clients probably don't care --gregc
            return opFrac(0)
        return opFrac(self.ownerLine.durationToEnd * opFrac(scale))

    ''' durationToEnd property for unscaled getDurationToEnd --gregc '''
    @property
    def durationToEnd(self) -> HumNum:
        if self.ownerLine is None:  # bugfix, but current clients probably don't care --gregc
            return opFrac(0)
        return self.ownerLine.durationToEnd

    '''
    //////////////////////////////
    //
    // HumdrumToken::getBarlineDuration -- Returns the duration between
    //   the next and previous barline.  If the token is a barline token,
    //   then return the duration to the next barline.  The barline duration data
    //   is filled in automatically when reading a file with the
    //   HumdrumFileStructure::analyzeMeter() function.  The duration
    //   will always be non-positive if the file is read with HumdrumFileBase and
    //   analyzeMeter() is not run to analyze the data.
    '''
    def getScaledBarlineDuration(self, scale: HumNumIn) -> HumNum:
        if self.ownerLine is None:
            return opFrac(0)
        return opFrac(self.ownerLine.barlineDuration * opFrac(scale))

    @property
    def barlineDuration(self) -> HumNum:
        if self.ownerLine is None:
            return opFrac(0)
        return self.ownerLine.barlineDuration

    '''
    //////////////////////////////
    //
    // HumdrumToken::getDurationToBarline -- Get duration from start of token to
    //      the start of the next barline. Units are quarter notes, unless scale
    //      is set to a value other than 1.
    '''
    def getScaledDurationToBarline(self, scale: HumNumIn) -> HumNum:
        if self.ownerLine is None:
            return opFrac(0)
        return opFrac(self.ownerLine.durationToBarline * opFrac(scale))

    @property
    def durationToBarline(self) -> HumNum:
        if self.ownerLine is None:
            return opFrac(0)
        return self.ownerLine.durationToBarline

    '''
    //////////////////////////////
    //
    // HumdrumToken::getDurationFromBarline -- Get duration from start of token to
    //      the previous barline. Units are quarter notes, unless scale
    //      is set to a value other than 1.
    '''
    def getScaledDurationFromBarline(self, scale: HumNumIn) -> HumNum:
        if self.ownerLine is None:
            return opFrac(0)
        return opFrac(self.ownerLine.durationFromBarline * opFrac(scale))

    @property
    def durationFromBarline(self) -> HumNum:
        if self.ownerLine is None:
            return opFrac(0)
        return self.ownerLine.durationFromBarline

    '''
    //////////////////////////////
    //
    // HumdrumToken::hasRhythm -- Returns true if the exclusive interpretation
    //    contains rhythmic data which will be used for analyzing the
    //    duration of a HumdrumFile, for example.
        Weird that this supports **recip, but analyzeDuration does not. --gregc
        Both need to add *koto support. --gregc
    '''
    @property
    def hasRhythm(self) -> bool:
        # cache the result for performance
        try:
            return self._hasRhythmCached
        except AttributeError:
            self._hasRhythmCached: bool = self.dataType.text in ('**kern', '**recip', '**mens')
            self._atLeastOneCachedDataTypePropertyExists = True
        return self._hasRhythmCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::hasBeam -- True if **kern has L, J, K, or k.
    '''
    @property
    def hasBeam(self) -> bool:
        # cache the result for performance
        try:
            return self._hasBeamCached
        except AttributeError:
            self._hasBeamCached: bool = (
                'L' in self.text
                or 'J' in self.text
                or 'K' in self.text
                or 'k' in self.text
            )
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._hasBeamCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::hasFermata --
    '''
    @property
    def hasFermata(self) -> bool:
        # cache the result for performance
        try:
            return self._hasFermataCached
        except AttributeError:
            self._hasFermataCached: bool = ';' in self.text
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._hasFermataCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isStaff -- Returns true if the spine type represents
    //   a notated staff.
    '''
    @property
    def isStaffDataType(self) -> bool:
        # cache the result for performance
        try:
            return self._isStaffDataTypeCached
        except AttributeError:
            self._isStaffDataTypeCached: bool = self.isKern or self.isMens
            self._atLeastOneCachedDataTypePropertyExists = True
        return self._isStaffDataTypeCached

    @property
    def isStaffInterpretation(self) -> bool:
        # cache the result for performance
        try:
            return self._isStaffInterpretationCached
        except AttributeError:
            self._isStaffInterpretationCached: bool = self.text.startswith('*staff')
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isStaffInterpretationCached

    @property
    def staff(self) -> str:
        # can be '1', '2', etc, or even '1/2' e.g. if this **dynam spine applies to two staves
        if not self.isStaffInterpretation:
            return ''
        return self.text[6:]

    @property
    def staffNums(self) -> t.List[int]:
        staffStr: str = self.staff
        staffNumList: t.List[int] = []
        for m in re.finditer(r'(\d+)/?', staffStr):
            if m.group(1) is None:
                break
            staffNumList.append(int(m.group(1)))
        return staffNumList

    @property
    def isPart(self) -> bool:
        # cache the result for performance
        try:
            return self._isPartCached
        except AttributeError:
            self._isPartCached: bool = self.text.startswith('*part')
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isPartCached

    @property
    def partNum(self) -> int:
        if not self.isPart:
            return -1

        # ignore characters after the number
        m = re.match(r'^\*part(\d+).*$', self.text)
        if m is None:
            return -1

        return int(m.group(1))

    @property
    def isGroup(self) -> bool:
        # cache the result for performance
        try:
            return self._isGroupCached
        except AttributeError:
            self._isGroupCached: bool = self.text.startswith('*group')
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isGroupCached

    @property
    def groupNum(self) -> int:
        if not self.isGroup:
            return -1

        # ignore characters after the number
        m = re.match(r'^\*group(\d+).*$', self.text)
        if m is None:
            return -1

        return int(m.group(1))

    @property
    def isStria(self) -> bool:
        return self.text.startswith('*stria')

    @property
    def stria(self) -> int:
        if not self.isStria:
            return DEFAULT_LINES_PER_STAFF
        m = re.match(r'^\*stria(\d+)', self.text)
        if m is None:
            return DEFAULT_LINES_PER_STAFF
        numLines: int = int(m.group(1))
        if numLines > MAX_LINES_PER_STAFF:
            return DEFAULT_LINES_PER_STAFF
        return numLines

    @property
    def isScale(self) -> bool:
        return self.text.startswith('*scale:')

    @property
    def isSize(self) -> bool:
        return self.text.startswith('*size:')

    @property
    def scale(self) -> float:
        if not self.isScale and not self.isSize:
            return 1.0
        m = re.search(r':(\d+(\.?\d*)?)%', self.text)
        if m:
            return float(m.group(1))
        return 1.0

    '''
    //////////////////////////////
    //
    // HumdrumToken::isRest -- Returns true if the token is a rest.
        Q: Only a few of these (e.g. isRest) bother to resolve null tokens.  Why? --gregc
    '''
    @property
    def isRest(self) -> bool:
        # assumption: isRest will only be called after self._nullResolution has been
        # set once and for all
        try:
            return self._isRestCached
        except AttributeError:
            tokenText: str = self.text
            if self.isNull:
                tokenText = self.nullResolution.text

            self._isRestCached: bool = False

            # BUGFIX: Without this "if self.isData", isRest('**kern') will return True
            # BUGFIX: (there's an 'r')
            if self.isData:
                if self.isKern:
                    self._isRestCached = Convert.isKernRest(tokenText)
                elif self.isMens:
                    self._isRestCached = Convert.isMensRest(tokenText)

            # isRest changes if tokenText changes, and also if dataType changes
            self._atLeastOneCachedTokenTextPropertyExists = True
            self._atLeastOneCachedDataTypePropertyExists = True

        return self._isRestCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isNote -- Returns true if the token is a (kern) note
    //     (possessing a pitch).
        Q: isNote is an example that doesn't bother to resolve null tokens. Why? --gregc
    '''
    @property
    def isNote(self) -> bool:
        try:
            return self._isNoteCached
        except AttributeError:
            self._isNoteCached: bool = False
            if not self.isData or self.isNull:
                pass
            elif self.isKern:
                self._isNoteCached = Convert.isKernNote(self.text)
            elif self.isMens:
                self._isNoteCached = Convert.isMensNote(self.text)

        return self._isNoteCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isPitched -- True if not a rest or an unpitched note.
    '''
    @property
    def isPitched(self) -> bool:
        if self.isKern:
            return 'r' not in self.text and 'R' not in self.text

        # Don't know data type so return false for now:
        return False

    '''
    //////////////////////////////
    //
    // HumdrumToken::isUnpitched -- True if has an unpitched marker
        This is checking for an unpitched note (e.g. in a percussion part), not a rest.
    '''
    @property
    def isUnpitched(self) -> bool:
        if self.isKern:
            return 'R' in self.text

        # Don't know data type so return false for now:
        return False

    '''
    //////////////////////////////
    //
    // HumdrumToken::isSustainedNote -- Returns true if the token represents
    //     a sounding note, but not the attack portion.  Should only be
    //     applied to **kern data.
    '''
    @property
    def isSustainedNote(self) -> bool:
        token: HumdrumToken = self
        if self.isNull:
            token = self.nullResolution
        return token.isSecondaryTiedNote

    '''
    //////////////////////////////
    //
    // HumdrumToken::isNoteAttack -- Returns true if the token represents
    //     the attack of a note.  Should only be applied to **kern data, but
    //     this function does not check for that for efficiency reasons.
    '''
    @property
    def isNoteAttack(self) -> bool:
        token: HumdrumToken = self
        if self.isNull:
            token = self.nullResolution

        if token.isRest:
            return False

        return not token.isSecondaryTiedNote

    '''
    //////////////////////////////
    //
    // HumdrumToken::isInvisible -- True if a barline and is invisible (contains
    //     a "-" styling), or a note/rest contains the string "yy" which is
    //     interpreted as meaning make it invisible.
    '''
    @property
    def isInvisible(self) -> bool:
        if not self.isKern:
            return False

        if self.isBarline:
            return '-' in self.text
        if self.isData:
            return 'yy' in self.text

        return False

    '''
    //////////////////////////////
    //
    // HumdrumToken::isGrace -- True if a **kern note has no duration.
        Should isGrace handle grace notes with duration differently? --gregc
    '''
    @property
    def isGrace(self) -> bool:
        if not self.isKern:
            return False
        if not self.isData:
            return False
        # return True if 'q' or 'qq' is in self.text
        return 'q' in self.text

    '''
    //////////////////////////////
    //
    // HumdrumToken::isClef -- True if a clef.
    '''
    @property
    def isClef(self) -> bool:
        if not (self.isKern or self.isMens):
            return False
        if not self.isInterpretation:
            return False

        if self.text.startswith('*clef'):
            return True

        # check for 'auto', 'clef' (added by HumdrumFile.py)
        autoClef: t.Optional[str] = self.getValueString('auto', 'clef')
        if autoClef and autoClef.startswith('*clef'):
            return True

        return False


    @property
    def clef(self) -> str:
        if not (self.isKern or self.isMens):
            return ''
        if not self.isInterpretation:
            return ''

        if self.text.startswith('*clef'):
            return self.text[5:]

        # check for 'auto', 'clef' (added by HumdrumFile.py)
        autoClef: t.Optional[str] = self.getValueString('auto', 'clef')
        if autoClef:
            return autoClef[5:]

        return ''

    '''
    //////////////////////////////
    //
    // HumdrumToken::isModernClef -- True if a modern clef.
    '''
    @property
    def isModernClef(self) -> bool:
        if not (self.isKern or self.isMens):
            return False
        if not self.isInterpretation:
            return False

        return self.text.startswith('*mclef')

    @property
    def modernClef(self) -> str:
        if not self.isModernClef:
            return ''
        return self.text[6:]

    '''
    //////////////////////////////
    //
    // HumdrumToken::isOriginalClef -- True if an original clef.
    '''
    @property
    def isOriginalClef(self) -> bool:
        if not (self.isKern or self.isMens):
            return False
        if not self.isInterpretation:
            return False

        return self.text.startswith('*oclef')

    @property
    def originalClef(self) -> str:
        if not self.isOriginalClef:
            return ''
        return self.text[6:]

    '''
    //////////////////////////////
    //
    // HumdrumToken::isKeySignature -- True if a key signature.
    '''
    @property
    def isKeySignature(self) -> bool:
        return self.text.startswith('*k[') and self.text.endswith(']')

    @property
    def keySignature(self) -> str:
        if not self.isKeySignature:
            return ''
        return self.text[3:-1]

    '''
    //////////////////////////////
    //
    // HumdrumToken::isOriginalKeySignature -- True if an original key signature.
    '''
    @property
    def isOriginalKeySignature(self) -> bool:
        return self.text.startswith('*ok[') and self.text.endswith(']')

    @property
    def originalKeySignature(self) -> str:
        if not self.isOriginalKeySignature:
            return ''
        return self.text[4:-1]

    '''
    //////////////////////////////
    //
    // HumdrumToken::isModernKeySignature -- True if a modern key signature.
    '''
    @property
    def isModernKeySignature(self) -> bool:
        return self.text.startswith('*mk[') and self.text.endswith(']')

    @property
    def modernKeySignature(self) -> str:
        if not self.isModernKeySignature:
            return ''
        return self.text[4:-1]

    '''
    //////////////////////////////
    //
    // HumdrumToken::isKeyDesignation -- True if a **kern key designation.
    //   *C:
    //   *A-:
    //   *c#:
    //   *d:dor
    '''
    @property
    def isKeyDesignation(self) -> bool:
        # we have to do an re.match because *grp:3 passed our simple check
        return re.match(KEY_DESIGNATION_PATTERN, self.text) is not None

    @property
    def keyDesignation(self) -> t.Tuple[t.Optional[str], t.Optional[str]]:
        # *d:dor returns ('d', 'dor'), *A-: returns ('A-', None)
        m = re.match(KEY_DESIGNATION_PATTERN, self.text)
        if m:
            return (m.group(1), m.group(2))
        return (None, None)

    '''
    //////////////////////////////
    //
    // HumdrumToken::isTimeSignature -- True if a **kern time signature.
    '''
    @property
    def isTimeSignature(self) -> bool:
        if len(self.text) < 3:
            return False
        if not self.text.startswith('*M'):
            return False
        if not self.text[2].isdigit():
            return False
        if '/' not in self.text:
            return False
        return True

    @property
    def timeSignature(self) -> t.Tuple[t.Optional[int], t.Optional[int]]:
        # returns (top: int, bot: int) or (None, None)
        if not self.isTimeSignature:
            return (None, None)

        # deal with triplet-whole note beats later: r'*M(\d+)/(\d+)%(\d+)'
        m = re.match(r'^\*M([\d]+)/([\d]+)', self.text)
        if m:
            top: int = int(m.group(1))
            bot: int = int(m.group(2))
            botStr: str = m.group(2)
            if botStr == '0':       # breve (2 whole notes)
                top *= 2
                bot = 1
            elif botStr == '00':    # longa (4 whole notes)
                top *= 4
                bot = 1
            elif botStr == '000':   # maxima (8 whole notes)
                top *= 8
                bot = 1
            elif botStr == '0000':  # double maxima (16 whole notes)
                top *= 16
                bot = 1
            return (top, bot)

        return (None, None)

    @property
    def timeSignatureRatioString(self) -> str:  # returns '{top}/{bot}'
        top, bot = self.timeSignature
        if top is None or bot is None:
            return ''

        return str(top) + '/' + str(bot)

    '''
    //////////////////////////////
    //
    // HumdrumToken::isTempo -- True if a **kern tempo.

        e.g. *MM124 or **MM124.67
        e.g. *MM[Adagio]
    '''
    @property
    def isTempo(self) -> bool:
        if len(self.text) < 4:
            return False
        if not self.text.startswith('*MM'):
            return False
        if not self.text[3].isdigit() and not self.text[3] == '[':
            return False
        return True

    @property
    def tempoBPM(self) -> int:
        if not self.isTempo:
            return 0
        m = re.match(r'^\*MM(\d+\.?\d*)', self.text)
        if m:
            tempo: float = float(m.group(1))
            return int(tempo + 0.5)
        return 0

    @property
    def tempoName(self) -> str:
        if not self.isTempo:
            return ''
        m = re.match(r'^\*MM[(.+)]', self.text)
        if m:
            return m.group(1)
        return ''

    '''
    //////////////////////////////
    //
    // HumdrumToken::isMensurationSymbol -- True if a **kern mensuration Symbol.
    '''
    @property
    def isMensurationSymbol(self) -> bool:
        return self.text.startswith('*met(') and self.text.endswith(')')

    '''
    //////////////////////////////
    //
    // HumdrumToken::isOriginalMensurationSymbol -- True if a **kern original mensuration Symbol.
    '''
    @property
    def isOriginalMensurationSymbol(self) -> bool:
        return self.text.startswith('*omet(') and self.text.endswith(')')

    @property
    def mensurationSymbol(self) -> str:
        m = None
        if self.isMensurationSymbol:
            m = re.match(r'^\*met\((.+)\)', self.text)
        elif self.isOriginalMensurationSymbol:
            m = re.match(r'^\*omet\((.+)\)', self.text)

        if m:
            return m.group(1)
        return ''


    '''
    //////////////////////////////
    //
    // HumdrumToken::isInstrumentDesignation -- Such as *Iclars for B-flat clarinet.
    '''
    @property
    def isInstrumentCode(self) -> bool:
        if len(self.text) < 3:
            # has to be '*I' and at least one lower-case letter
            return False
        if not self.text.startswith('*I'):
            return False
        if not self.text[2:].isalpha():
            # return False for '*I""blah', "*I'Blah", etc
            return False
        if not self.text[2:].islower():
            return False
        return True

    '''
        isInstrumentClassCode -- such as *ICbras for BrassInstrument
    '''
    @property
    def isInstrumentClassCode(self) -> bool:
        if len(self.text) < 4:
            # has to be '*IC' and at least one lower-case letter
            return False
        if not self.text.startswith('*IC'):
            return False
        if not self.text[3:].isalpha():
            return False
        if not self.text[3:].islower():
            return False
        return True

    '''
    //////////////////////////////
    //
    // HumdrumToken::isInstrumentName -- True if an instrument name token.
    '''
    @property
    def isInstrumentName(self) -> bool:
        if len(self.text) < 4:
            # has to be *I" plus at least one character
            return False
        if self.text[3] == '"':
            # avoid *I""Blah, which is InstrumentGroupName
            return False
        return self.text.startswith('*I"')

    '''
        isInstrumentGroupName
    '''
    @property
    def isInstrumentGroupName(self) -> bool:
        if len(self.text) < 5:
            # has to be *I"" plus at least one character
            return False
        return self.text.startswith('*I""')

    '''
    //////////////////////////////
    //
    // HumdrumToken::isInstrumentAbbreviation -- True if an instrument abbreviation token.
    '''
    @property
    def isInstrumentAbbreviation(self) -> bool:
        if len(self.text) < 4:
            # has to be *I' plus at least one character
            return False
        if self.text[3] == "'":
            # avoid *I''Blah, which is InstrumentGroupAbbreviation
            return False
        return self.text.startswith("*I'")

    '''
        isInstrumentGroupAbbreviation
    '''
    @property
    def isInstrumentGroupAbbreviation(self) -> bool:
        if len(self.text) < 5:
            # has to be *I'' plus at least one character
            return False
        return self.text.startswith("*I''")

    '''
        instrumentCode -- return 'clars' from '*Iclars', for example
    '''
    @property
    def instrumentCode(self) -> str:
        if not self.isInstrumentCode:
            return ''
        # everything after *I
        return self.text[2:]

    '''
        instrumentClassCode -- return 'bras' from '*ICbras', for example
    '''
    @property
    def instrumentClassCode(self) -> str:
        if not self.isInstrumentClassCode:
            return ''
        # everything after *IC
        return self.text[3:]

    '''
    //////////////////////////////
    //
    // HumdrumToken::getInstrumentName --
    '''
    @property
    def instrumentName(self) -> str:
        if not self.isInstrumentName:
            return ''
        # everything after *I"
        return self.text[3:]

    '''
        instrumentGroupName
    '''
    @property
    def instrumentGroupName(self) -> str:
        if not self.isInstrumentGroupName:
            return ''
        # everything after *I""
        return self.text[4:]

    '''
    //////////////////////////////
    //
    // HumdrumToken::getInstrumentAbbreviation --
    '''
    @property
    def instrumentAbbreviation(self) -> str:
        if not self.isInstrumentAbbreviation:
            return ''
        # everything after *I'
        return self.text[3:]

    '''
        instrumentGroupAbbreviation
    '''
    @property
    def instrumentGroupAbbreviation(self) -> str:
        if not self.isInstrumentGroupAbbreviation:
            return ''
        # everything after *I''
        return self.text[4:]

    '''
        isInstrumentTranspose
    '''
    @property
    def isInstrumentTranspose(self) -> bool:
        if self.text.startswith('*ITrd'):
            return True
        return False

    '''
        instrumentTranspose
    '''
    @property
    def instrumentTranspose(self) -> str:
        if not self.isInstrumentTranspose:
            return ''
        # everything after '*ITr' -> 'dNcM'
        return self.text[4:]

    '''
        isTranspose
    '''
    @property
    def isTranspose(self) -> bool:
        if self.text.startswith('*Trd'):
            return True
        return False

    '''
        instrumentTranspose
    '''
    @property
    def transpose(self) -> str:
        if not self.isTranspose:
            return ''
        # everything after '*Tr' -> 'dNcM'
        return self.text[3:]

    '''
    //////////////////////////////
    //
    // HumdrumToken::hasSlurStart -- Returns true if the **kern token has
    //     a '(' character.
    '''
    @property
    def hasSlurStart(self) -> bool:
        if not self.isKern:
            return False
        return Convert.hasKernSlurStart(self.text)

    '''
    //////////////////////////////
    //
    // HumdrumToken::hasSlurEnd -- Returns true if the **kern token has
    //     a ')' character.
    '''
    @property
    def hasSlurEnd(self) -> bool:
        if not self.isKern:
            return False
        return Convert.hasKernSlurEnd(self.text)

    '''
    //////////////////////////////
    //
    // HumdrumToken::hasVisibleAccidental -- Returns true if the accidental
    //    of a **kern note is viewable if rendered to graphical notation.
    //     return values:
    //      false
    //      true
    //      None = undefined;
    '''
    def hasVisibleAccidental(self, subtokenIndex: int) -> t.Optional[bool]:
        humLine = self.ownerLine
        if humLine is None:
            return None
        humFile = humLine.ownerFile
        if humFile is None:
            return None

        # make sure we've done the full accidental analysis on the whole file
        if not humFile.getValueBool('auto', 'accidentalAnalysis'):
            successful = humFile.analyzeKernAccidentals()
            if not successful:
                return None

        return self.getValueBool('auto', str(subtokenIndex), 'visualAccidental')

    '''
    //////////////////////////////
    //
    // HumdrumToken::hasCautionaryAccidental -- Returns true if the accidental
    //    of a **kern note is viewable if rendered to graphical notation.
    //     return values:
    //      false
    //      true
    //      None = undefined;
    '''
    def hasCautionaryAccidental(self, subtokenIndex: int) -> t.Optional[bool]:
        humLine = self.ownerLine
        if humLine is None:
            return None
        humFile = humLine.ownerFile
        if humFile is None:
            return None

        # make sure we've done the full accidental analysis on the whole file
        if not humFile.getValueBool('auto', 'accidentalAnalysis'):
            successful = humFile.analyzeKernAccidentals()
            if not successful:
                return None

        return self.getValueBool('auto', str(subtokenIndex), 'cautionaryAccidental')

    def cautionaryAccidental(self, subtokenIndex: int) -> t.Optional[str]:
        humLine = self.ownerLine
        if humLine is None:
            return None
        humFile = humLine.ownerFile
        if humFile is None:
            return None

        # make sure we've done the full accidental analysis on the whole file
        if not humFile.getValueBool('auto', 'accidentalAnalysis'):
            successful = humFile.analyzeKernAccidentals()
            if not successful:
                return None

        return self.getValueString('auto', str(subtokenIndex), 'cautionaryAccidental')

    def hasEditorialAccidental(self, subtokenIndex: int) -> t.Optional[bool]:
        humLine = self.ownerLine
        if humLine is None:
            return None
        humFile = humLine.ownerFile
        if humFile is None:
            return None

        # make sure we've done the full accidental analysis on the whole file
        if not humFile.getValueBool('auto', 'accidentalAnalysis'):
            successful = humFile.analyzeKernAccidentals()
            if not successful:
                return None

        return self.getValueBool('auto', str(subtokenIndex), 'editorialAccidental')

    def editorialAccidentalStyle(self, subtokenIndex: int) -> t.Optional[str]:
        humLine = self.ownerLine
        if humLine is None:
            return None
        humFile = humLine.ownerFile
        if humFile is None:
            return None

        # make sure we've done the full accidental analysis on the whole file
        if not humFile.getValueBool('auto', 'accidentalAnalysis'):
            successful = humFile.analyzeKernAccidentals()
            if not successful:
                return None

        editStyle: t.Optional[str] = self.getValueString(
            'auto', str(subtokenIndex), 'editorialAccidentalStyle'
        )
        if editStyle is None:
            return ''
        return editStyle

    '''
    //////////////////////////////
    //
    // HumdrumToken::hasLigatureBegin --
    '''
    @property
    def hasLigatureBegin(self) -> bool:
        if not self.isMens:
            return False
        return Convert.hasLigatureBegin(self.text)

    '''
    //////////////////////////////
    //
    // HumdrumToken::hasRectaLigatureBegin --
    '''
    @property
    def hasRectaLigatureBegin(self) -> bool:
        if not self.isMens:
            return False
        return Convert.hasRectaLigatureBegin(self.text)

    '''
    //////////////////////////////
    //
    // HumdrumToken::hasObliquaLigatureBegin --
    '''
    @property
    def hasObliquaLigatureBegin(self) -> bool:
        if not self.isMens:
            return False
        return Convert.hasObliquaLigatureBegin(self.text)

    '''
    //////////////////////////////
    //
    // HumdrumToken::hasStemDirection --
    '''
    @property
    def getStemDirection(self) -> t.Optional[str]:
        if not self.isKern:
            return None
        return Convert.getKernStemDirection(self.text)

    '''
    //////////////////////////////
    //
    // HumdrumToken::allSameBarlineStyle --
    '''
    @property
    def allSameBarlineStyle(self) -> bool:
        if self.ownerLine is None:
            return True
        return self.ownerLine.allSameBarlineStyle

    '''
    //////////////////////////////
    //
    // HumdrumToken::hasLigatureEnd --
    '''
    @property
    def hasLigatureEnd(self) -> bool:
        if not self.isMens:
            return False
        return Convert.hasLigatureEnd(self.text)

    '''
    //////////////////////////////
    //
    // HumdrumToken::hasRectaLigatureEnd --
    '''
    @property
    def hasRectaLigatureEnd(self) -> bool:
        if not self.isMens:
            return False
        return Convert.hasRectaLigatureEnd(self.text)

    '''
    //////////////////////////////
    //
    // HumdrumToken::hasObliquaLigatureEnd --
    '''
    @property
    def hasObliquaLigatureEnd(self) -> bool:
        if not self.isMens:
            return False
        return Convert.hasObliquaLigatureEnd(self.text)

    '''
    //////////////////////////////
    //
    // HumdrumToken::isSecondaryTiedNote -- Returns true if the token
    //     is a (kern) note (possessing a pitch) and has '_' or ']' characters.
    '''
    @property
    def isSecondaryTiedNote(self) -> bool:
        if not self.isKern:
            return False

        return Convert.isKernSecondaryTiedNote(self.text)

    '''
    //////////////////////////////
    //
    // HumdrumToken::isBarline -- Returns true if the first character is an
    //   equals sign.
    '''
    @property
    def isBarline(self) -> bool:
        # cache the result for performance
        try:
            return self._isBarlineCached
        except AttributeError:
            self._isBarlineCached: bool = self.text.startswith('=')
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isBarlineCached

    '''
        barlineNumber returns the first number found.
        e.g. it returns 23 for both '=!|23' and '=23a:|', etc
    '''
    @property
    def barlineNumber(self) -> int:
        if not self.isBarline:
            return -1

        m = re.search(r'([\d]+)', self.text)
        if m:
            return int(m.group(1))
        return -1

    '''
        barlineName returns the full name of the barline, which is of the form 'Nc',
        where N is an integer (see barlineNumber) and c is a single lower-case
        character, used for alternate endings of a repeated section.
        If there is no suffix character, we return '' (and you should use barlineNumber)
        e.g. it returns '' for '=!|23' and '23a' for '=23a:|', etc
    '''
    @property
    def barlineName(self) -> str:
        if not self.isBarline:
            return ''

        m = re.search(r'([\d]+([a-z]{1}))', self.text)
        if m and m.group(2):
            # we have a barlineNumber with a single lower-case character suffix
            return m.group(1)
        return ''

    '''
    //////////////////////////////
    //
    // HumdrumToken::isCommentGlobal -- Returns true of the token starts with "!!".
    //    Currently confused with reference records.
    '''
    @property
    def isGlobalComment(self) -> bool:
        # cache the result for performance
        try:
            return self._isGlobalCommentCached
        except AttributeError:
            self._isGlobalCommentCached: bool = self.text.startswith('!!')
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isGlobalCommentCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isCommentLocal -- Returns true of the token start with "!",
    //   but not "!!" which is for global comments.
    '''
    @property
    def isLocalComment(self) -> bool:
        # cache the result for performance
        try:
            return self._isLocalCommentCached
        except AttributeError:
            self._isLocalCommentCached: bool = self.isComment and not self.isGlobalComment
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isLocalCommentCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isComment -- Returns true of the token start with "!".
    '''
    @property
    def isComment(self) -> bool:
        # cache the result for performance
        try:
            return self._isCommentCached
        except AttributeError:
            self._isCommentCached: bool = self.text.startswith('!')
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isCommentCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isData -- Returns true if not an interpretation, barline
    //      or local comment.  This will not work on synthetic tokens generated
    //      from an empty line.  So this function should be called only on tokens
    //      in lines which pass the HumdrumLine::hasSpines() test.
    '''
    @property
    def isData(self) -> bool:
        # cache the result for performance
        try:
            return self._isDataCached
        except AttributeError:
            self._isDataCached: bool = (
                not self.isInterpretation
                and not self.isComment
                and not self.isBarline
            )
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isDataCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isInterpretation -- Returns true if an interpretation.
    '''
    @property
    def isInterpretation(self) -> bool:
        # cache the result for performance
        try:
            return self._isInterpretationCached
        except AttributeError:
            self._isInterpretationCached: bool = self.text.startswith('*')
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isInterpretationCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isNonNullData -- Returns true if the token is a data token
    //    that is not a null token.
    '''
    @property
    def isNonNullData(self) -> bool:
        # cache the result for performance
        try:
            return self._isNonNullDataCached
        except AttributeError:
            self._isNonNullDataCached: bool = self.isData and not self.isNull
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isNonNullDataCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isNullData -- Returns true if the token is a null
    //     data token.
    '''
    @property
    def isNullData(self) -> bool:
        # cache the result for performance
        try:
            return self._isNullDataCached
        except AttributeError:
            self._isNullDataCached: bool = self.isData and self.isNull
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isNullDataCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isLabel -- Returns true if a thru label (such as *>A).
    '''
    @property
    def isLabel(self) -> bool:
        # cache the result for performance
        try:
            return self._isLabelCached
        except AttributeError:
            self._isLabelCached: bool = self.text.startswith('*>') and '[' not in self.text
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isLabelCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isChord -- True if is a chord.  Presuming you know what
    //     data type you are accessing.
    //     Default value:
    //          separate = " "   (**kern note separator)
    '''
    @property
    def isChord(self) -> bool:
        # cache the result for performance
        try:
            return self._isChordCached
        except AttributeError:
            self._isChordCached: bool = ' ' in self.text
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isChordCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isExclusiveInterpretation -- Returns true if first two
    //     characters are "**".
    '''
    @property
    def isExclusiveInterpretation(self) -> bool:
        # cache the result for performance
        try:
            return self._isExclusiveInterpretationCached
        except AttributeError:
            self._isExclusiveInterpretationCached: bool = self.text.startswith('**')
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isExclusiveInterpretationCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isSplitInterpretation -- True if the token is "*^".
    '''
    @property
    def isSplitInterpretation(self) -> bool:
        # cache the result for performance
        try:
            return self._isSplitInterpretationCached
        except AttributeError:
            self._isSplitInterpretationCached: bool = self.text == SPLIT_TOKEN
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isSplitInterpretationCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isMergeInterpretation -- True if the token is "*v".
    '''
    @property
    def isMergeInterpretation(self) -> bool:
        # cache the result for performance
        try:
            return self._isMergeInterpretationCached
        except AttributeError:
            self._isMergeInterpretationCached: bool = self.text == MERGE_TOKEN
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isMergeInterpretationCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isExchangeInterpretation -- True if the token is "*x".
    '''
    @property
    def isExchangeInterpretation(self) -> bool:
        # cache the result for performance
        try:
            return self._isExchangeInterpretationCached
        except AttributeError:
            self._isExchangeInterpretationCached: bool = self.text == EXCHANGE_TOKEN
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isExchangeInterpretationCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isTerminateInterpretation -- True if the token is "*-".
    '''
    @property
    def isTerminateInterpretation(self) -> bool:
        # cache the result for performance
        try:
            return self._isTerminateInterpretationCached
        except AttributeError:
            self._isTerminateInterpretationCached: bool = self.text == TERMINATE_TOKEN
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isTerminateInterpretationCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isAddInterpretation -- True if the token is "*+".
    '''
    @property
    def isAddInterpretation(self) -> bool:
        # cache the result for performance
        try:
            return self._isAddInterpretationCached
        except AttributeError:
            self._isAddInterpretationCached: bool = self.text == ADD_TOKEN
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isAddInterpretationCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::isNull -- Returns true if the token is a null token,
    //   either for data, comments, or interpretations.  Does not consider
    //   null global comments since they are not part of the spine structure.
    '''
    @property
    def isNull(self) -> bool:
        # cache the result for performance
        try:
            return self._isNullCached
        except AttributeError:
            self._isNullCached: bool = (
                self.text in (NULL_DATA, NULL_INTERPRETATION, NULL_COMMENT_LOCAL)
            )
            self._atLeastOneCachedTokenTextPropertyExists = True
        return self._isNullCached

    '''
    //////////////////////////////
    //
    // HumdrumToken::noteInLowerSubtrack -- Return true if the note
    //     is attacked or sustained with another note in a lower layer.
    //     This is for using in hum2mei conversion to avoid a bug in
    //     verovio related to lyrics in layers where the notes are a
    //     second apart.
        iohumdrum.cpp in Verovio is the only client --gregc
    '''
    @property
    def noteInLowerSubtrack(self) -> bool:
        if self.subTrack <= 1:
            return False
        if self.ownerLine is None:
            return False

        track: t.Optional[int] = self.track
        if track is None:
            return False

        # loops from field-1 to 0 (end index -1 is exclusive), incrementing by -1
        for i in range(self.fieldIndex - 1, -1, -1):
            xtoken = self.ownerLine.token[i]
            if xtoken.track != track:
                return False
            if xtoken.isNull:
                continue
            if 'r' in xtoken.text:
                continue
            return True

        return False


    '''
    //////////////////////////////
    //
    // HumdrumToken::getTrackString -- Gets "track.subtrack" as a string.  The
    //     track and subtrack are integers.  The getTrackString function will
    //     return a string with the track and subtrack separated by an dot.  The
    //     Dot is not a decimal point, but if the subtrack count does not exceed
    //     9, then the returned string can be treated as a floating-point number
    //     where the subtrack is the fractional part.
    // @SEEALSO: getTrack, getSubtrack
    '''
    @property
    def trackString(self) -> str:
        return self._address.trackString

    '''
    //////////////////////////////
    //
    // HumdrumToken::getSubtokenCount -- Returns the number of sub-tokens in
    //     a token.  The input parameter is the sub-token separator.  If the
    //     separator comes at the start or end of the token, then there will
    //     be empty sub-token(s) included in the count.
    // default value: separator = " "
    // @SEEALSO: getSubtoken

        Separator is always ' ' here, so subtokenCount can be a property. --gregc
    '''
    @property
    def subtokenCount(self) -> int:
        return len(self.subtokens)

    '''
    /////////////////////////////
    //
    // HumdrumToken::getSubtoken -- Extract the specified sub-token from the token.
    //    Tokens usually are separated by spaces in Humdrum files, but this will
    //    depened on the data type (so therefore, the tokens are not presplit into
    //    sub-tokens when reading in the file).
    // default value: separator = " "
    // @SEEALSO: getSubtokenCount, getTrackString

        Instead of getSubtoken(index), we have (below) a subtokens property which
        generates a list of subtoken strings for the client to index into.  We
        cache it for performance. --gregc
    '''

    '''
    //////////////////////////////
    //
    // HumdrumToken::getSubtokens -- Return the list of subtokens as an array
    //     of strings.
    //     default value: separator = " "
    '''
    @property
    def subtokens(self) -> t.List[str]:
        if not self._subtokensGenerated:
            self._subtokens = self.text.split(' ')
            self._subtokensGenerated = True

        return self._subtokens
    '''
    //////////////////////////////
    //
    // HumdrumToken::replaceSubtoken --
    //     default value: separator = " "
    '''
    def replaceSubtoken(self, index: int, newSubtoken: str) -> None:
        if index < 0 or index >= self.subtokenCount:
            return
        self.subtokens[index] = newSubtoken
        self.text = ' '.join(self.subtokens)
        # Set _subtokensGenerated to True, because setting self.text clears it,
        # but we know the subtokens are there.
        self._subtokensGenerated = True

    '''
    //////////////////////////////
    //
    // HumdrumToken::addLinkedParameterSet --
    '''
    def addLinkedParameterSet(self, token: 'HumdrumToken') -> int:
        if ':ignore' in token.text:
            '''
            // Ignore layout command (store layout command but
            // do not use it).  This is particularly for adding
            // layout parameters for notation, but the parameters
            // currently cause problems in verovio (so they should
            // be unignored at a future date when the layout
            // parameter is handled better).  Note that any
            // parameter starting with "ignore" such as "ignored"
            // will also be suppressed by this if statement.
            '''
            return -1

        for i, linkedToken in enumerate(self._linkedParameterTokens):
            if linkedToken == token:
                return i

        if not self._linkedParameterTokens:
            self._linkedParameterTokens.append(token)
            return 0

        # Insert token into the list, keeping it sorted by line index
        if token.lineIndex >= self._linkedParameterTokens[-1].lineIndex:
            self._linkedParameterTokens.append(token)
            return self.linkedParameterSetCount - 1

        for i, linkedToken in enumerate(self._linkedParameterTokens):
            if token.lineIndex < linkedToken.lineIndex:
                self._linkedParameterTokens.insert(i, token)
                return i  # bugfix: C++ version returns len-1

        # I don't think you can get here, but if you do, you failed.
        # Treat it as 'ignored' (store layout command but do not use it).
        return -1

    '''
    //////////////////////////////
    //
    // HumdrumToken::linkedParameterIsGlobal --
    '''
    def linkedParameterIsGlobal(self, index: int) -> bool:
        if index not in range(0, self.linkedParameterSetCount):
            return False
        return self._linkedParameterTokens[index].isGlobalComment

    '''
    //////////////////////////////
    //
    // HumdrumToken::getLinkedParameterSetCount --
    '''
    @property
    def linkedParameterSetCount(self) -> int:
        return len(self._linkedParameterTokens)

    '''
    //////////////////////////////
    //
    // HumdrumToken::getParameterSet --
    '''
    @property
    def parameterSet(self) -> t.Optional[HumParamSet]:
        return self._parameterSet

    '''
    //////////////////////////////
    //
    // HumdrumToken::getLinkedParameterSet --
    '''
    def getLinkedParameterSet(self, index: int) -> t.Optional[HumParamSet]:
        if index not in range(0, self.linkedParameterSetCount):
            return None
        return self._linkedParameterTokens[index].parameterSet

    '''
    //////////////////////////////
    //
    // HumdrumToken::storeParameterSet -- Store the contents of the token
    //    in the parameter storage.  Used for layout parameters.
    '''
    def storeParameterSet(self) -> None:
        if (self.isLocalComment or self.isGlobalComment) and ':' in self.text:
            self._parameterSet = HumParamSet(self.text)

    '''
    //////////////////////////////
    //
    // HumdrumToken::makeForwardLink -- Link a following spine token to this one.
    //    Used by the HumdrumFileBase::analyzeLinks function.
    '''
    def makeForwardLink(self, nextToken: 'HumdrumToken') -> None:
        self.nextTokens.append(nextToken)
        self.updateNextToken0()
        nextToken.previousTokens.append(self)
        nextToken.updatePreviousToken0()

    '''
    //////////////////////////////
    //
    // HumdrumToken::makeBackwardLink -- Link a previous spine token to this one.
    //    Used by the HumdrumFileBase::analyzeLinks function.
    '''
    def makeBackwardLink(self, previousToken: 'HumdrumToken') -> None:
        self.previousTokens.append(previousToken)
        self.updatePreviousToken0()
        previousToken.nextTokens.append(self)
        previousToken.updateNextToken0()

    '''
    //////////////////////////////
    //
    // HumdrumToken::getOwner -- Returns a pointer to the HumdrumLine that
    //    owns this token.
    '''
    @property
    def ownerLine(self):  # returns t.Optional[HumdrumLine]
        return self._address.ownerLine

    @ownerLine.setter
    def ownerLine(self, newOwnerLine) -> None:  # newOwnerLine: t.Optional[HumdrumLine]
        self._address.ownerLine = newOwnerLine
        if self._atLeastOneCachedDataTypePropertyExists:
            # some cached properties depend on dataType,
            # which depends on ownerLine and track
            self._clearCachedDataTypeProperties()

    '''
    //////////////////////////////
    //
    // HumdrumToken::getState -- Returns the rhythm state variable.
    '''
    @property
    def rhythmAnalysisState(self) -> int:
        return self._rhythmAnalysisState

    '''
    //////////////////////////////
    //
    // HumdrumToken::incrementState -- update the rhythm analysis state variable.
    //    This will prevent redundant recursive analysis in analyzeRhythm of
    //    the HumdrumFileStructure class.
    '''
    def incrementRhythmAnalysisState(self) -> None:
        self._rhythmAnalysisState += 1

    '''
    //////////////////////////////
    //
    // HumdrumToken::getStrandIndex -- Returns the 1-D strand index
    //    that the token belongs to in the owning HumdrumFile.
    //    Returns -1 if there is no strand assignment.
    '''
    @property
    def strandIndex(self) -> int:
        return self._strandIndex

    @strandIndex.setter
    def strandIndex(self, newStrandIndex: int) -> None:
        self._strandIndex = newStrandIndex

    '''
    //////////////////////////////
    //
    // HumdrumToken::getSlurStartElisionLevel -- Returns the count of
    //   elision marks ('&') preceding a slur start character '('.
    //   Returns -1 if there is no slur start character.
    //   Default value: index = 0
    '''
    def startElisionLevel(self, slurOrPhrase: str, index: int = 0) -> int:
        if self.isKern or self.isMens:
            if slurOrPhrase == HumdrumToken.SLUR:
                return Convert.getKernSlurStartElisionLevel(self.text, index)
            if slurOrPhrase == HumdrumToken.PHRASE:
                return Convert.getKernPhraseStartElisionLevel(self.text, index)

        return -1

    '''
    //////////////////////////////
    //
    // HumdrumToken::getSlurEndElisionLevel -- Returns the count of
    //   elision marks ('&') preceding a slur end character ')'.
    //   Returns -1 if there is no slur end character.
    //   Default value: index = 0
    '''
    def endElisionLevel(self, slurOrPhrase: str, index: int = 0) -> int:
        if self.isKern or self.isMens:
            if slurOrPhrase == HumdrumToken.SLUR:
                return Convert.getKernSlurEndElisionLevel(self.text, index)
            if slurOrPhrase == HumdrumToken.PHRASE:
                return Convert.getKernPhraseEndElisionLevel(self.text, index)

        return -1

    '''
    //////////////////////////////
    //
    // HumdrumToken::getNextTokenCount -- Returns the number of tokens in the
    //   spine/sub spine which follow this token.  Typically this will be 1,
    //   but will be zero for a terminator interpretation (*-), and will be
    //   2 for a split interpretation (*^).
    '''
    @property
    def nextTokenCount(self) -> int:
        return len(self.nextTokens)

    '''
    //////////////////////////////
    //
    // HumdrumToken::getPreviousTokenCount -- Returns the number of tokens
    //   in the spine/sub-spine which precede this token.  Typically this will
    //   be 1, but will be zero for an exclusive interpretation (starting with
    //   "**"), and will be greater than one for a token which follows a
    //   spine merger (using *v interpretations).
    '''
    @property
    def previousTokenCount(self) -> int:
        return len(self.previousTokens)

    '''
    //////////////////////////////
    //
    // HumdrumToken::getSlurStartToken -- Return a pointer to the token
    //     which starts the given slur.  Returns NULL if no start.  Assumes that
    //     HumdrumFileContent::analyzeKernSlurs() has already been run.
    //                <parameter key="slurEnd" value="HT_140366146702320" idref=""/>
        Storing a pointer in a string is not something Python (or I) can deal with.
        We simply set/get a reference to the token itself in the HumHash instead. --gregc
    '''
    def getSlurStartToken(self, number: int) -> 'HumdrumToken':
        return self.getValueToken('auto', makeTag('slurStartId', number))

    '''
    //////////////////////////////
    //
    // HumdrumToken::getSlurStartNumber -- Given a slur ending number,
    //    return the slur start number that it pairs with.
    '''
    def getSlurStartNumber(self, number: int) -> int:
        return self.getValueInt('auto', makeTag('slurStartNumber', number))

    '''
    //////////////////////////////
    //
    // HumdrumToken::getSlurEndToken -- Return a pointer to the token
    //     which ends the given slur.  Returns NULL if no end.  Assumes that
    //     HumdrumFileContent::analyzeKernSlurs() has already been run.
    //                <parameter key="slurStart" value="HT_140366146702320" idref=""/>
        Storing a pointer in a string is not something Python (or I) can deal with.
        We simply set/get a reference to the token itself in the HumHash instead. --gregc
    '''
    def getSlurEndToken(self, number: int) -> 'HumdrumToken':
        return self.getValueToken('auto', makeTag('slurEnd', number))

    '''
    //////////////////////////////
    //
    // HumdrumToken::getPhraseStartToken -- Return a pointer to the token
    //     which starts the given phrase.  Returns NULL if no start.  Assumes that
    //     HumdrumFileContent::analyzeKernPhrasings() has already been run.
    //                <parameter key="phraseEnd" value="HT_140366146702320" idref=""/>
        Storing a pointer in a string is not something Python (or I) can deal with.
        We simply set/get a reference to the token itself in the HumHash instead. --gregc
    '''
    def getPhraseStartToken(self, number: int) -> 'HumdrumToken':
        return self.getValueToken('auto', makeTag('phraseStart', number))

    '''
    //////////////////////////////
    //
    // HumdrumToken::getPhraseEndToken -- Return a pointer to the token
    //     which ends the given phrase.  Returns NULL if no end.  Assumes that
    //     HumdrumFileContent::analyzeKernPhrasings() has already been run.
    //                <parameter key="phraseStart" value="HT_140366146702320" idref=""/>
        Storing a pointer in a string is not something Python (or I) can deal with.
        We simply set/get a reference to the token itself in the HumHash instead. --gregc
    '''
    def getPhraseEndToken(self, number: int) -> 'HumdrumToken':
        return self.getValueToken('auto', makeTag('phraseEnd', number))

    '''
    //////////////////////////////
    //
    // HumdrumToken::resolveNull --
    '''
    @property
    def nullResolution(self) -> 'HumdrumToken':
        if self._nullResolution is not None:
            return self._nullResolution

        if self.ownerLine is not None and self.ownerLine.ownerFile is not None:
            self.ownerLine.ownerFile.resolveNullTokens()

        if self._nullResolution is not None:
            return self._nullResolution

        return self

    @nullResolution.setter
    def nullResolution(self, newNullResolution: 'HumdrumToken') -> None:
        self._nullResolution = newNullResolution

    '''
    //////////////////////////////
    //
    // HumdrumToken::copyStucture --
    '''
    def copyStructure(self, fromToken: 'HumdrumToken') -> None:
        # pylint: disable=protected-access
        from converter21.humdrum import HumdrumLine
        self._strandIndex = fromToken._strandIndex

        # pick up original ownerLine before you overwrite _address
        originalOwnerLine: t.Optional[HumdrumLine] = self._address.ownerLine
        self._address = copy.copy(fromToken._address)

        # preserve the original ownerLine
        self._address.ownerLine = originalOwnerLine
        # pylint: enable=protected-access

    '''
    //////////////////////////////
    //
    // HumdrumToken::getStrophe -- return the strophe that the token belongs to,
    //    or NULL if it is not in a strophe.
    '''
    @property
    def strophe(self) -> t.Optional['HumdrumToken']:
        return self._strophe

    @strophe.setter
    def strophe(self, strophe: t.Optional['HumdrumToken']) -> None:
        if strophe is None:
            self._strophe = None
            return

        if not strophe.text.startswith('*S/'):
            # invalid strophe marker.
            self._strophe = None
            return

        self._strophe = strophe

    '''
    //////////////////////////////
    //
    // HumdrumToken::hasStrophe -- return true if the token is in a strophe; otherwise,
    //    return false.
    '''
    @property
    def hasStrophe(self) -> bool:
        return self.strophe is not None


    '''
    //////////////////////////////
    //
    // HumdrumToken::isFirstStrophe -- Returns true if the token is in the first
    //    strophe variant.  Returns true if not in a strophe.
    '''
    @property
    def isFirstStrophe(self) -> bool:
        if self.strophe is None:
            return True

        toleft = self.strophe.previousFieldToken
        if toleft is None:
            return True

        return self.strophe.track != toleft.track

    '''
    //////////////////////////////
    //
    // HumdrumToken::isStrophe -- Return true if the token has the given strophe
    //   label.
    '''
    def isStrophe(self, label: str) -> bool:
        if self.strophe is None:
            return False

        if label is None or label == '':
            return self.strophe.text == '*S/'

        if label.startswith('*'):
            return self.strophe.text == label

        return self.strophe.text[3:] == label

    '''
    //////////////////////////////
    //
    // HumdrumToken::getStropheLabel -- Return the strophe label after *S/ in the
    //    strophe token.  Returns the empty string when not in a strophe.
    '''
    @property
    def stropheLabel(self) -> str:
        if self.strophe is None:
            return ''

        if len(self.strophe.text) <= 3:
            return ''

        if self.strophe.text == '*S/':
            return ''

        return self.strophe.text[3:]

    '''
        LayoutParameter stuff
    '''

    '''
    //////////////////////////////
    //
    // HumdrumToken::getLayoutParameter -- Returns requested layout parameter
    //     if it is attached to a token directly or indirectly through a linked
    //     parameter.  Returns empty string if no explicit visual durtation (so
    //     the visual duration is same as the logical duration).  If subtokenindex
    //     is less than -1 (the default value for the paramter), then ignore the
    //     @n parameter control for indexing the layout parameter to chord notes.
    //     The subtokenindex (0 indexed) is converted to note number (1 indexed)
    //     for checking @n.  @n is currently only allowed to be a single integer
    //     (eventually allow ranges and multiple values).
    '''
    def layoutParameter(self, category: str, keyName: str, subtokenIndex: int = -1) -> str:
        # First check for any local layout parameter:
        testOutput: t.Optional[str] = self.getValueString('LO', category, keyName)
        if testOutput:
            if subtokenIndex >= 0:
                n: int = self.getValueInt('LO', category, 'n')
                if n == subtokenIndex + 1:
                    return testOutput
            else:
                return testOutput

        output: str = ''
        lcount: int = self.linkedParameterSetCount
        if lcount == 0:
            return output

        nparam: str = ''
        for p in range(0, lcount):
            hps: t.Optional[HumParamSet] = self.getLinkedParameterSet(p)
            if hps is None:
                continue
            if hps.namespace1 != 'LO':
                continue
            if hps.namespace2 != category:
                continue

            output = ''
            for q in range(0, hps.count):
                key: str = hps.getParameterName(q)
                if key == keyName:
                    output = hps.getParameterValue(q)
                    if subtokenIndex < 0:
                        return output
                if key == 'n':
                    nparam = hps.getParameterValue(q)

            if not nparam:
                # no subtoken selection for this parameter,
                # so return if not empty
                if output:
                    return output
            elif subtokenIndex < 0:
                # no subtoken selection so return output if not empty
                if output:
                    return output
            else:
                # There is a subtoken selection number, so
                # return output if n matches it (minus one)

                # currently @n requires a single value
                # (should allow a range or multiple values
                # later).  Also not checking validity of
                # string first (needs to start with a digit);
                np: int = int(nparam)
                if np == subtokenIndex + 1:
                    return output

                # not the output that is required,
                # so suppress for end of loop
                output = ''

        return output

    def getBooleanLayoutParameter(self, category: str, key: str) -> bool:
        lcount: int = self.linkedParameterSetCount
        for i in range(0, lcount):
            hps: t.Optional[HumParamSet] = self.getLinkedParameterSet(i)
            if not hps:
                continue
            if hps.namespace1 != 'LO':
                continue
            if hps.namespace2 != category:
                continue
            pkey: str = ''
            for j in range(0, hps.count):
                pkey = hps.getParameterName(j)
                if pkey == key:
                    return True
        return False

    def getStringLayoutParameter(self, category: str, key: str) -> str:
        lcount: int = self.linkedParameterSetCount
        for i in range(0, lcount):
            hps: t.Optional[HumParamSet] = self.getLinkedParameterSet(i)
            if not hps:
                continue
            if hps.namespace1 != 'LO':
                continue
            if hps.namespace2 != category:
                continue
            pkey: str = ''
            for j in range(0, hps.count):
                pkey = hps.getParameterName(j)
                if pkey == key:
                    return hps.getParameterValue(j)
        return ''

    '''
    //////////////////////////////
    //
    // HumdrumToken::getVisualDuration -- Returns LO:N:vis parameter if it is attached
    //    to a token directly or indirectly through a linked parameter.  Returns empty string
    //    if no explicit visual duration (so the visual duration is same as the logical duration).
    '''
    def getVisualDuration(self, subtokenIdx: int = -1) -> str:
        visDurStr = self.layoutParameter('N', 'vis', subtokenIdx)
        # if visDurStr:
        #     print('visualDuration(recip) = {}, origDur(quarterLength) = {}'.format(
        #               visDurStr, self.duration), file=sys.stderr)
        return visDurStr

    '''
        XML and other print stuff
    '''
