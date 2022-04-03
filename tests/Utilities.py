from converter21.humdrum import HumHash
from converter21.humdrum import HumNum
from converter21.humdrum import HumAddress
from converter21.humdrum import *
from converter21.humdrum import HumdrumToken
from converter21.humdrum import HumdrumLine
from converter21.humdrum import HumdrumFile
from converter21.humdrum import HumSignifier
from converter21.humdrum import HumSignifiers

import music21 as m21

from typing import Tuple
from fractions import Fraction
import random
import json
import re

TOKENTYPE_DATA                  = 'data'
TOKENTYPE_BARLINE               = 'barline'
TOKENTYPE_INTERPRETATION        = 'interpretation'
TOKENTYPE_LOCALCOMMENT          = 'localComment'
TOKENTYPE_GLOBALCOMMENT         = 'globalComment'
TOKENTYPE_GLOBALREFERENCE       = 'globalReference'
TOKENTYPE_UNIVERSALCOMMENT      = 'universalComment'
TOKENTYPE_UNIVERSALREFERENCE    = 'universalReference'

SPECIFICTYPE_NOTHINGSPECIFIC    = 'nothing'
SPECIFICTYPE_NULLDATA           = 'nullData'
SPECIFICTYPE_NULLINTERPRETATION = 'nullInterpretation'
SPECIFICTYPE_NULLCOMMENT        = 'nullComment'
SPECIFICTYPE_NOTE               = 'note'
SPECIFICTYPE_REST               = 'rest'
SPECIFICTYPE_KEYSIGNATURE       = 'keysig'
SPECIFICTYPE_TIMESIGNATURE      = 'timesig'
SPECIFICTYPE_CLEF               = 'clef'
SPECIFICTYPE_SPLIT              = 'split'
SPECIFICTYPE_MERGE              = 'merge'
SPECIFICTYPE_EXCHANGE           = 'exchange'
SPECIFICTYPE_ADD                = 'add'
SPECIFICTYPE_TERMINATE          = 'terminate'
SPECIFICTYPE_EXINTERP           = 'exinterp'

LINETYPE_EMPTY              = 'empty'               # empty string:                     '' or None
LINETYPE_GLOBALCOMMENT      = 'globalComment'       # starts with two or more bangs:    '!!'
LINETYPE_GLOBALREFERENCE    = 'globalReference'     # of the form:                      '!!!KEY: VALUE'
LINETYPE_UNIVERSALCOMMENT   = 'universalComment'    # starts with exactly four bangs:   '!!!!'
LINETYPE_UNIVERSALREFERENCE = 'universalReference'  # of the form:                      '!!!!KEY: VALUE'
LINETYPE_LOCALCOMMENT       = 'localComment'        # starts with exactly one bang:     '!'
LINETYPE_BARLINE            = 'barline'             # starts with equal sign:           '='
LINETYPE_INTERPRETATION     = 'interpretation'      # starts with asterisk:             '*'
LINETYPE_DATA               = 'data'                # anything else


# some line types are comments
commentTypeTuple = (LINETYPE_LOCALCOMMENT,
                    LINETYPE_GLOBALCOMMENT,
                    LINETYPE_UNIVERSALCOMMENT,
                    LINETYPE_GLOBALREFERENCE,
                    LINETYPE_UNIVERSALREFERENCE)

# some line types are local (i.e. they have spines)
hasSpinesTypeTuple = (LINETYPE_LOCALCOMMENT,
                      LINETYPE_DATA,
                      LINETYPE_BARLINE,
                      LINETYPE_INTERPRETATION)

# some line types are global (including EMPTY, apparently!)
isGlobalTypeTuple = (LINETYPE_EMPTY,
                     LINETYPE_GLOBALCOMMENT,
                     LINETYPE_GLOBALREFERENCE,
                     LINETYPE_UNIVERSALCOMMENT,
                     LINETYPE_UNIVERSALREFERENCE)


class HumdrumFileTestResults:
    ''' HumdrumFileTestResults holds the original Humdrum test file contents, the original results file contents,
        and the extra results derived from those two things.
        self.fileContents: [str] = the original Humdrum test file contents
        self.results: dict = the original results file contents, as follows:
            self.results["exclusiveInterpretationlineNumbers"]: [int] = list of line nums of the '**' lines
            self.results["manipulatorLineNumbers"]: [int] = list of line nums of '*^', '*v', etc lines
            self.results["tokenDataTypeChanges"]: {} = dict(lineNumberOfChange: str(int), newTokenDataTypes: [str])
        self.extraResults: dict = the results derived from Humdrum test file contents and results file contents
            self.extraResults["lines"]
            self.extraResults["lineCount"]
            self.extraResults["lineNumbers"]
            self.extraResults["tokens"]
            self.extraResults["tokenDataTypes"]
            self.extraResults["maxTrack"]
            self.extraResults["lineTypes"]
            self.extraResults["isExclusiveInterpretation"]
            self.extraResults["isManipulator"]

        All results (and extraResults) are accessible as read-only properties of the obvious name,
        to avoid needing to key into the appropriate dictionary.
        '''

    def __init__(self, fileContents: str = None, results: dict = None):
        # fileContents is the entire Humdrum test file contents in a string
        # results is a dict parsed from the resultsFile's JSON contents
        if results is None:
            results = dict(
                tpq = 1,
                exclusiveInterpretationLineNumbers = [],
                manipulatorLineNumbers = [],
                tokenDataTypeChanges = {},
                spineInfoChanges = {},
                fileContentsUnmodified = True)

        if fileContents and fileContents[-1] == '\n':
            self.fileContents = fileContents[:-1]
        else:
            self.fileContents: str = fileContents

        self.results: dict = results

        # Take fileContent and results, and generate a bunch more results that don't
        # need to be specified in the resultsFile
        self.extraResults: dict = self.generateExtraResults()

    @classmethod
    def fromFiles(cls, testFileName: str, resultsFileName: str):
        #                                                        -> HumdrumFileTestResults:
        # Alternate __init__-like function that takes the files, reads them in,
        # and ends up calling the __init__ above by calling cls(str, dict),
        # which is HumdrumFileTestResults(str, dict)
        fileContents: str = None
        results: dict = None

        # Read Humdrum file.
        # Note that utf-8 works fine on basic ASCII (utf-8 is a superset of ASCII), but may fail on certain latin-1 chars
        try:
            with open(testFileName, encoding='utf-8') as testFile:
                fileContents = testFile.read()
        except UnicodeDecodeError:
            # Unicode decode failed, so try again as latin-1.
            with open(testFileName, encoding='latin-1') as testFile:
                fileContents = testFile.read()

        with open(resultsFileName) as resultsFile:
            results = json.load(resultsFile)
        return cls(fileContents, results)

    # results properties
    @property
    def tpq(self):
        return self.results["tpq"]

    @property
    def fileContentsUnmodified(self):
        return self.results["fileContentsUnmodified"]

    @property
    def exclusiveInterpretationLineNumbers(self):
        return self.results["exclusiveInterpretationLineNumbers"]

    @property
    def manipulatorLineNumbers(self):
        return self.results["manipulatorLineNumbers"]

    @property
    def tokenDataTypeChanges(self):
        return self.results["tokenDataTypeChanges"]

    @property
    def spineInfoChanges(self):
        return self.results["spineInfoChanges"]

    # extraResults properties
    @property
    def lines(self):
        return self.extraResults["lines"]

    @property
    def lineCount(self):
        return self.extraResults["lineCount"]

    @property
    def lineNumbers(self):
        return self.extraResults["lineNumbers"]

    @property
    def tokens(self):
        return self.extraResults["tokens"]

    @property
    def tokenDataTypes(self):
        return self.extraResults["tokenDataTypes"]

    @property
    def maxTrack(self):
        return self.extraResults["maxTrack"]

    @property
    def lineTypes(self):
        return self.extraResults["lineTypes"]

    @property
    def isExclusiveInterpretation(self):
        return self.extraResults["isExclusiveInterpretation"]

    @property
    def isManipulator(self):
        return self.extraResults["isManipulator"]

#     def writeToFile(self, outTestFileName: str, outResultsFileName: str):
#         # Convenient for constructing test/results files from HumdrumFileTestResults
#         # objects that didn't originally come from a file, but rather from
#         # a hand-constructed Humdrum string and results dict.
#         with open(outTestFileName, 'w') as outTestFile:
#             outTestFile.write(self.fileContents)
#         with open(outResultsFileName, 'w') as outResultsFile:
#             outResultsFile.write(json.dumps(self.results, indent=4))

    def generateExtraResults(self) -> dict:
        # default extra results
        lines = []
        lineCount = 0
        tokens = []
        tokenDataTypes = []
        initialTrackCount = 0

        if self.fileContents is not None:
            lines = self.generateExpectedLines(self.fileContents)
            lineCount = len(lines)
            tokens = self.generateExpectedTokens(lines)
            if self.exclusiveInterpretationLineNumbers:
                firstExInterpLineIdx = self.exclusiveInterpretationLineNumbers[0] - 1
                initialTrackCount = len(tokens[firstExInterpLineIdx])

        return dict(
            lines = lines,
            lineCount = lineCount,
            lineNumbers = [i for i in range(1, lineCount+1)],
            tokens = tokens,
            tokenDataTypes = self.generateExpectedTokenStrings(self.tokenDataTypeChanges, lineCount),

            # starts at initialTrackCount, adds one for every '*+', subtracts one for every '*-',
            # and returns the maximum seen
            maxTrack = self.generateExpectedMaxTrack(tokens, initialTrackCount),
            lineTypes = self.generateExpectedLineTypes(lines),
            isExclusiveInterpretation = self.generateExpectedIs__FromTrueLineNumbers(
                                                        self.exclusiveInterpretationLineNumbers,
                                                        lineCount),
            isManipulator = self.generateExpectedIs__FromTrueLineNumbers(
                                                self.manipulatorLineNumbers,
                                                lineCount),
            )

    def generateExpectedMaxTrack(self, tokens: [[str]], initialTrackCount: int) -> int:
        currentTrackCount = initialTrackCount
        expectedMaxTrack = currentTrackCount

        for lineTokens in tokens:
            for token in lineTokens:
                if token == '*+':
                    currentTrackCount += 1
                    if currentTrackCount > expectedMaxTrack:
                        expectedMaxTrack = currentTrackCount
                elif token == '*-':
                    currentTrackCount -= 1

        return expectedMaxTrack

    def generateExpectedLines(self, entireHumdrumFileString: str) -> [str]:
        return entireHumdrumFileString.split('\n')

    def generateExpectedTokens(self, allLines: [str]) -> [[str]]:
        tokens: [[str]] = []
        for line in allLines:
            if line.startswith('!!'): # because (e.g. beethoven.../sonata04-1.krn) someone might have commented out a
                tokens.append([line])   # line with '!!', so we can't use the presence of tabs to mean there are spines
            elif line == '': # blank line
                tokens.append(['']) # single empty token
            else:
                tokens.append(self.splitIntoTokens(line))
        return tokens

    def splitIntoTokens(self, line: str) -> [str]:
        output: [str] = []
        for m in re.finditer(r'([^\t]+)(\t*)', line):
            # m is a match object containing two groups: first the token, then any trailing tabs
            tokenStr = m.group(1)
            if tokenStr is None:
                break
            output.append(tokenStr)
        return output

    def getExpectedLineType(self, line: str) -> str:
        if line is None or line == '':
            return LINETYPE_EMPTY
        elif line[0] == '=':
            return LINETYPE_BARLINE
        elif line[0] == '*':
            return LINETYPE_INTERPRETATION
        elif line[0] == '!':
            if len(line) >= 2 and line[1] == '!':
                if len(line) >= 3 and line[2] == '!':
                    if len(line) >= 4 and line[3] == '!':
                        if ':' in line:
                            return LINETYPE_UNIVERSALREFERENCE
                        else:
                            return LINETYPE_UNIVERSALCOMMENT
                    else:
                        return LINETYPE_GLOBALREFERENCE
                else:
                    return LINETYPE_GLOBALCOMMENT
            else:
                return LINETYPE_LOCALCOMMENT
        else:
            return LINETYPE_DATA

    def generateExpectedLineTypes(self, allLines: [str]) -> [str]:
        lineTypes = []
        for line in allLines:
            lineTypes.append(self.getExpectedLineType(line))
        return lineTypes

    def generateExpectedLineStrings(self, stringChanges: dict, lineCount: int) -> list:
        result = [''] * lineCount
        changeLineNumbers = []
        # We want integers for sorting and comparison with lineNumbers, but the keys are strings representing integers.
        # Note that python allows integer keys, but we store these in JSON files, and JSON does not allow that.
        for key in list(stringChanges.keys()):
            changeLineNumbers.append(int(key))
        changeLineNumbers.sort()
        changeLineNumbers_Idx: int = 0
        currValue: str = ''
        for lineIdx in range(0, lineCount):
            lineNumber = lineIdx+1  # lineNumber is 1-based, lineIdx is 0-based
            if changeLineNumbers_Idx < len(changeLineNumbers) and lineNumber == changeLineNumbers[changeLineNumbers_Idx]:
                currValue = stringChanges[str(lineNumber)] # back to str for a key
                changeLineNumbers_Idx += 1
            result[lineIdx] = currValue
        return result

    def generateExpectedTokenStrings(self, stringListChanges: dict, lineCount: int) -> [list]:
        result = [['']] * lineCount # a single empty token on every line
        changeLineNumbers = []
        # We want integers for sorting and comparison with lineNumbers, but the keys are strings representing integers.
        # Note that python allows integer keys, but we store these in JSON files, and JSON does not allow that.
        for key in list(stringListChanges.keys()):
            changeLineNumbers.append(int(key))
        changeLineNumbers.sort()
        changeLineNumbers_Idx: int = 0
        currValue: [str] = ['']
        for lineIdx in range(0, lineCount):
            lineNumber = lineIdx+1  # lineNumber is 1-based, lineIdx is 0-based
            if changeLineNumbers_Idx < len(changeLineNumbers) and lineNumber == changeLineNumbers[changeLineNumbers_Idx]:
                currValue = stringListChanges[str(lineNumber)] # back to str for a key
                changeLineNumbers_Idx += 1
            result[lineIdx] = currValue
        return result

    def generateExpectedIs__FromTrueLineNumbers(self, trueLineNumbers: [int], numValues: int) -> [bool]:
        expectedIs__: [bool] = [False] * numValues
        for trueLineNumber in trueLineNumbers: # 1-based
            expectedIs__[trueLineNumber - 1] = True # 0-based
        return expectedIs__


def CheckHumdrumToken( token: HumdrumToken,
                        expectedText: str = '',
                        expectedDataType: str = '',
                        expectedTokenType: str = TOKENTYPE_DATA,
                        expectedSpecificType: str = SPECIFICTYPE_NOTHINGSPECIFIC,
                        expectedDuration: str = HumNum(-1)
                        ):

    #print('CheckHumdrumToken: token = "{}"'.format(token))

    # set up some derived expectations
    expectedIsData = expectedTokenType == TOKENTYPE_DATA
    expectedIsBarline = expectedTokenType == TOKENTYPE_BARLINE
    expectedIsInterpretation = expectedTokenType == TOKENTYPE_INTERPRETATION
    expectedIsLocalComment = expectedTokenType == TOKENTYPE_LOCALCOMMENT
    expectedIsGlobalComment = expectedTokenType == TOKENTYPE_GLOBALCOMMENT
#     expectedIsGlobalReference = expectedTokenType == TOKENTYPE_GLOBALREFERENCE
#     expectedIsUniversalComment = expectedTokenType == TOKENTYPE_UNIVERSALCOMMENT
#     expectedIsUniversalReference = expectedTokenType == TOKENTYPE_UNIVERSALREFERENCE

    expectedIsNote = expectedSpecificType == SPECIFICTYPE_NOTE
    expectedIsRest = expectedSpecificType == SPECIFICTYPE_REST
    expectedIsNullData = expectedSpecificType == SPECIFICTYPE_NULLDATA
    expectedIsNullInterpretation = expectedSpecificType == SPECIFICTYPE_NULLINTERPRETATION
    expectedIsNullComment = expectedSpecificType == SPECIFICTYPE_NULLCOMMENT
    expectedIsNull = expectedIsNullData or expectedIsNullInterpretation or expectedIsNullComment

    expectedIsKeySignature = expectedSpecificType == SPECIFICTYPE_KEYSIGNATURE
    expectedIsTimeSignature = expectedSpecificType == SPECIFICTYPE_TIMESIGNATURE
    expectedIsClef = expectedSpecificType == SPECIFICTYPE_CLEF
    expectedIsSplitInterpretation = expectedSpecificType == SPECIFICTYPE_SPLIT
    expectedIsMergeInterpretation = expectedSpecificType == SPECIFICTYPE_MERGE
    expectedIsExchangeInterpretation = expectedSpecificType == SPECIFICTYPE_EXCHANGE
    expectedIsAddInterpretation = expectedSpecificType == SPECIFICTYPE_ADD
    expectedIsTerminateInterpretation = expectedSpecificType == SPECIFICTYPE_TERMINATE
    expectedIsExclusiveInterpretation = expectedSpecificType == SPECIFICTYPE_EXINTERP
    expectedIsManipulator = expectedIsSplitInterpretation \
                                or expectedIsMergeInterpretation \
                                or expectedIsExchangeInterpretation \
                                or expectedIsAddInterpretation \
                                or expectedIsTerminateInterpretation \
                                or expectedIsExclusiveInterpretation

    expectedIsKern = expectedDataType == '**kern'
    expectedIsMens = expectedDataType == '**mens'
    expectedIsRecip = expectedDataType == '**recip'
    expectedIsStaffDataType = expectedIsKern or expectedIsMens

    # text
    assert token.text == expectedText
    assert str(token) == expectedText

    # duration
    assert token.duration == expectedDuration
    assert token.scaledDuration(HumNum(1,5)) == expectedDuration * HumNum(1,5)

    # Token Type
    assert token.isData == expectedIsData
    assert token.isBarline == expectedIsBarline
    assert token.isInterpretation == expectedIsInterpretation
    assert token.isLocalComment == expectedIsLocalComment
    assert token.isGlobalComment == expectedIsGlobalComment
#     assert token.isGlobalReference == expectedIsGlobalReference
#     assert token.isUniversalComment == expectedIsUniversalComment
#     assert token.isUniversalReference == expectedIsUniversalReference

    # Specific Type
    assert token.isNullData == expectedIsNullData
    assert token.isNull == expectedIsNull
    assert token.isNote == expectedIsNote
    assert token.isRest == expectedIsRest
    assert token.isKeySignature == expectedIsKeySignature
    assert token.isTimeSignature == expectedIsTimeSignature
    assert token.isClef == expectedIsClef
    assert token.isSplitInterpretation == expectedIsSplitInterpretation
    assert token.isMergeInterpretation == expectedIsMergeInterpretation
    assert token.isExchangeInterpretation == expectedIsExchangeInterpretation
    assert token.isAddInterpretation == expectedIsAddInterpretation
    assert token.isTerminateInterpretation == expectedIsTerminateInterpretation
    assert token.isExclusiveInterpretation == expectedIsExclusiveInterpretation
    assert token.isManipulator == expectedIsManipulator

    # Data Type
    assert token.dataType.text == expectedDataType
    assert token.isDataType(expectedDataType) == True
    if expectedDataType[:2] == '**':
        assert token.isDataType(expectedDataType[1:]) == False
        assert token.isDataType(expectedDataType[2:]) == True
    assert token.isKern == expectedIsKern
    assert token.isMens == expectedIsMens
    assert token.isStaffDataType == expectedIsStaffDataType

def CheckHumdrumLine( line: HumdrumLine,
                        expectedLine: str = '',
                        expectedLineNumber: int = None,
                        expectedType: str = LINETYPE_EMPTY,
                        expectedTokenCount: int = 1,
                        expectedIsExclusiveInterpretation: bool = False,
                        expectedIsManipulator: bool = False,
                        expectedTokens: [str] = None ):
    # set up some derived expectations
    expectedIsData = expectedType == LINETYPE_DATA
    expectedIsBarline = expectedType == LINETYPE_BARLINE
    expectedIsInterpretation = expectedType == LINETYPE_INTERPRETATION
    expectedIsLocalComment = expectedType == LINETYPE_LOCALCOMMENT
    expectedIsGlobalComment = expectedType == LINETYPE_GLOBALCOMMENT
    expectedIsGlobalReference = expectedType == LINETYPE_GLOBALREFERENCE
    expectedIsUniversalComment = expectedType == LINETYPE_UNIVERSALCOMMENT
    expectedIsUniversalReference = expectedType == LINETYPE_UNIVERSALREFERENCE
    expectedIsComment = expectedType in commentTypeTuple
    expectedHasSpines = expectedType in hasSpinesTypeTuple
    expectedIsGlobal = expectedType in isGlobalTypeTuple

    expectedIsAllNull = False # if no spines
    if expectedHasSpines:
        # default to True if hasSpines, then if we see a non-null token, we set to False and get out
        expectedIsAllNull = True
        for tokenText in expectedTokens:
            if expectedIsInterpretation and tokenText != '*':
                expectedIsAllNull = False
                break
            if expectedIsLocalComment and tokenText != '!':
                expectedIsAllNull = False
                break
            if (expectedIsData or expectedIsBarline) and tokenText != '.':
                expectedIsAllNull = False
                break

    assert line.lineNumber == expectedLineNumber
    assert line.text == expectedLine
    assert str(line) == expectedLine

    # interrogate the line various ways
    assert line.isAllNull == expectedIsAllNull
    assert line.isData == expectedIsData
    assert line.isBarline == expectedIsBarline
    assert line.isInterpretation == expectedIsInterpretation
    assert line.isLocalComment == expectedIsLocalComment
    assert line.isGlobalComment == expectedIsGlobalComment
    assert line.isGlobalReference == expectedIsGlobalReference
    assert line.isUniversalComment == expectedIsUniversalComment
    assert line.isUniversalReference == expectedIsUniversalReference
    assert line.isComment == expectedIsComment
    assert line.hasSpines == expectedHasSpines # isLocal, in other words
    assert line.isGlobal == expectedIsGlobal
    assert line.isExclusiveInterpretation == expectedIsExclusiveInterpretation
    assert line.isManipulator == expectedIsManipulator

    # check that tokenCount and the length of all the arrays are expectedTokenCount
    assert line.tokenCount == expectedTokenCount
    assert len(list(line.tokens())) == expectedTokenCount

    # check the line tokens themselves
    if expectedTokens is not None: # is None if we have no way of expecting a particular list of tokens
        assert [str(token) for token in line.tokens()] == expectedTokens
        assert [line[tokIdx].text for tokIdx in range(0, line.tokenCount)] == expectedTokens

def CheckHumAddress(addr: HumAddress,
                            expectedSegment: int = 0,
                            expectedLine: int = 0,
                            expectedToken: int = 0,
                            expectedSubToken: int = 0,
                            expectedStr: str = '{line = 0, token = 0}'):
    assert addr.segment == expectedSegment
    assert addr.line == expectedLine
    assert addr.token == expectedToken
    assert addr.subToken == expectedSubToken
    assert str(addr) == expectedStr

def getTokenDataTypes(hf: HumdrumFile) -> [[str]]:
    #returns a '**blah' string for every token in every line in the file
    return [[token.dataType.text for token in line.tokens()] for line in hf.lines()]

def CheckHumdrumFile(hf: HumdrumFile, results: HumdrumFileTestResults):
    assert hf.lineCount == results.lineCount
    assert hf.maxTrack == results.maxTrack
    assert getTokenDataTypes(hf) == results.tokenDataTypes
    assert hf.tpq() == results.tpq
    assert hf.tpq() == results.tpq # check it twice, for code coverage of "I already computed that" path

    if results.fileContentsUnmodified:
        if results.fileContents is None:
            assert str(hf) == ''
        else:
            assert str(hf) == results.fileContents

    for lineIdx, line in enumerate(hf.lines()):
        if results.fileContentsUnmodified: # LATER: keep track of which lines not to check
            assert line.text == results.lines[lineIdx]
            assert str(line) == results.lines[lineIdx]          # test HumdrumLine.__str__
            assert hf[lineIdx].text == results.lines[lineIdx]   # test HumdrumFile.__getitem__
            assert [tok.text for tok in line.tokens()] == results.tokens[lineIdx]

        assert line.lineNumber == results.lineNumbers[lineIdx]
        assert line.isExclusiveInterpretation == results.isExclusiveInterpretation[lineIdx]
        assert line.isManipulator == results.isManipulator[lineIdx]
        assert line.tokenCount == len(results.tokens[lineIdx])

def CheckHumSignifier(sig: HumSignifier,
                        expectedExInterp: str,
                        expectedSignifier: str,
                        expectedDefinition: str):
    assert sig.exInterp == expectedExInterp
    assert sig.signifier == expectedSignifier
    assert sig.definition == expectedDefinition

def CheckHumSignifiers(hss: HumSignifiers, **kw):
    for key, value in kw.items():
        if key == 'above':
            assert hss.above == value
        elif key == 'below':
            assert hss.below == value
        elif key == 'linked':
            assert hss.linked == value
        elif key == 'noteMarks':
            assert hss.noteMarks == value
        elif key == 'noteColors':
            assert hss.noteColors == value
        elif key == 'noteDirs':
            assert hss.noteDirs == value
        elif key == 'noStem':
            assert hss.noStem == value
        elif key == 'cueSize':
            assert hss.cueSize == value
        elif key == 'hairpinAccent':
            assert hss.hairpinAccent == value
        elif key == 'terminalLong':
            assert hss.terminalLong == value
        elif key == 'crescText':
            assert hss.crescText == value
        elif key == 'decrescText':
            assert hss.decrescText == value
        elif key == 'crescFontStyle':
            assert hss.crescFontStyle == value
        elif key == 'decrescFontStyle':
            assert hss.decrescFontStyle == value
        elif key == 'spaceColor':
            assert hss.spaceColor == value
        elif key == 'ispaceColor':
            assert hss.ispaceColor == value
        elif key == 'rspaceColor':
            assert hss.rspaceColor == value
        elif key == 'irestColor':
            assert hss.irestColor == value
        elif key == 'textMarks':
            assert hss.textMarks == value
        elif key == 'textColors':
            assert hss.textColors == value
        elif key == 'editorialAccidentals':
            assert hss.editorialAccidentals == value
        elif key == 'editorialAccidentalTypes':
            assert hss.editorialAccidentalTypes == value
        else:
            print('CheckHumSignifiers does not support "{}" yet. Add test support!'.format(key))
            assert False

def CheckM21DateSingle(dateSingle, expectedYear=None, expectedMonth=None, expectedDay=None,
                                   expectedHour=None, expectedMinute=None, expectedSecond=None,
                                   expectedYearError=None, expectedMonthError=None,
                                   expectedDayError=None, expectedHourError=None,
                                   expectedMinuteError=None, expectedSecondError=None,
                                   expectedRelevance='certain'):
    assert isinstance(dateSingle, m21.metadata.DateSingle)
    assert dateSingle.relevance == expectedRelevance
    assert dateSingle._data[0].year == expectedYear
    assert dateSingle._data[0].yearError == expectedYearError
    assert dateSingle._data[0].month == expectedMonth
    assert dateSingle._data[0].monthError == expectedMonthError
    assert dateSingle._data[0].day == expectedDay
    assert dateSingle._data[0].dayError == expectedDayError
    assert dateSingle._data[0].hour == expectedHour
    assert dateSingle._data[0].hourError == expectedHourError
    assert dateSingle._data[0].minute == expectedMinute
    assert dateSingle._data[0].minuteError == expectedMinuteError
    assert dateSingle._data[0].second == expectedSecond
    assert dateSingle._data[0].secondError == expectedSecondError

def CheckM21DateRelative(dateRelative, expectedYear=None, expectedMonth=None, expectedDay=None,
                                   expectedHour=None, expectedMinute=None, expectedSecond=None,
                                   expectedYearError=None, expectedMonthError=None,
                                   expectedDayError=None, expectedHourError=None,
                                   expectedMinuteError=None, expectedSecondError=None,
                                   expectedRelevance=None): # expectedRelevance=None is never right
    assert isinstance(dateRelative, m21.metadata.DateRelative)
    assert dateRelative.relevance == expectedRelevance
    assert dateRelative._data[0].year == expectedYear
    assert dateRelative._data[0].yearError == expectedYearError
    assert dateRelative._data[0].month == expectedMonth
    assert dateRelative._data[0].monthError == expectedMonthError
    assert dateRelative._data[0].day == expectedDay
    assert dateRelative._data[0].dayError == expectedDayError
    assert dateRelative._data[0].hour == expectedHour
    assert dateRelative._data[0].hourError == expectedHourError
    assert dateRelative._data[0].minute == expectedMinute
    assert dateRelative._data[0].minuteError == expectedMinuteError
    assert dateRelative._data[0].second == expectedSecond
    assert dateRelative._data[0].secondError == expectedSecondError

def _checkM21DateBetweenOrSelection(dateBetweenOrSelection,
                                    expectedNumDates,
                                    expectedYear, expectedMonth, expectedDay,
                                    expectedHour, expectedMinute, expectedSecond,
                                    expectedYearError, expectedMonthError,
                                    expectedDayError, expectedHourError,
                                    expectedMinuteError, expectedSecondError):
    assert len(dateBetweenOrSelection._data) == expectedNumDates
    if not isinstance(expectedYear, Tuple):
        expectedYear = (expectedYear,) * expectedNumDates
    if not isinstance(expectedMonth, Tuple):
        expectedMonth = (expectedMonth,) * expectedNumDates
    if not isinstance(expectedDay, Tuple):
        expectedDay = (expectedDay,) * expectedNumDates
    if not isinstance(expectedHour, Tuple):
        expectedHour = (expectedHour,) * expectedNumDates
    if not isinstance(expectedMinute, Tuple):
        expectedMinute = (expectedMinute,) * expectedNumDates
    if not isinstance(expectedSecond, Tuple):
        expectedSecond = (expectedSecond,) * expectedNumDates
    if not isinstance(expectedYearError, Tuple):
        expectedYearError = (expectedYearError,) * expectedNumDates
    if not isinstance(expectedMonthError, Tuple):
        expectedMonthError = (expectedMonthError,) * expectedNumDates
    if not isinstance(expectedDayError, Tuple):
        expectedDayError = (expectedDayError,) * expectedNumDates
    if not isinstance(expectedHourError, Tuple):
        expectedHourError = (expectedHourError,) * expectedNumDates
    if not isinstance(expectedMinuteError, Tuple):
        expectedMinuteError = (expectedMinuteError,) * expectedNumDates
    if not isinstance(expectedSecondError, Tuple):
        expectedSecondError = (expectedSecondError,) * expectedNumDates

    for i in range(0, expectedNumDates):
        assert dateBetweenOrSelection._data[i].year == expectedYear[i]
        assert dateBetweenOrSelection._data[i].yearError == expectedYearError[i]
        assert dateBetweenOrSelection._data[i].month == expectedMonth[i]
        assert dateBetweenOrSelection._data[i].monthError == expectedMonthError[i]
        assert dateBetweenOrSelection._data[i].day == expectedDay[i]
        assert dateBetweenOrSelection._data[i].dayError == expectedDayError[i]
        assert dateBetweenOrSelection._data[i].hour == expectedHour[i]
        assert dateBetweenOrSelection._data[i].hourError == expectedHourError[i]
        assert dateBetweenOrSelection._data[i].minute == expectedMinute[i]
        assert dateBetweenOrSelection._data[i].minuteError == expectedMinuteError[i]
        assert dateBetweenOrSelection._data[i].second == expectedSecond[i]
        assert dateBetweenOrSelection._data[i].secondError == expectedSecondError[i]

def CheckM21DateBetween(dateBetween,
                                    expectedNumDates=2,
                                    expectedYear=None, expectedMonth=None, expectedDay=None,
                                    expectedHour=None, expectedMinute=None, expectedSecond=None,
                                    expectedYearError=None, expectedMonthError=None,
                                    expectedDayError=None, expectedHourError=None,
                                    expectedMinuteError=None, expectedSecondError=None,
                                    expectedRelevance='between'):
    assert isinstance(dateBetween, m21.metadata.DateBetween)
    assert dateBetween.relevance == expectedRelevance
    _checkM21DateBetweenOrSelection(dateBetween,
                                    expectedNumDates,
                                    expectedYear, expectedMonth, expectedDay,
                                    expectedHour, expectedMinute, expectedSecond,
                                    expectedYearError, expectedMonthError,
                                    expectedDayError, expectedHourError,
                                    expectedMinuteError, expectedSecondError)

def CheckM21DateSelection(dateSelection,
                                    expectedNumDates,
                                    expectedYear=None, expectedMonth=None, expectedDay=None,
                                    expectedHour=None, expectedMinute=None, expectedSecond=None,
                                    expectedYearError=None, expectedMonthError=None,
                                    expectedDayError=None, expectedHourError=None,
                                    expectedMinuteError=None, expectedSecondError=None,
                                    expectedRelevance='or'):
    assert isinstance(dateSelection, m21.metadata.DateSelection)
    assert dateSelection.relevance == expectedRelevance
    _checkM21DateBetweenOrSelection(dateSelection,
                                    expectedNumDates,
                                    expectedYear, expectedMonth, expectedDay,
                                    expectedHour, expectedMinute, expectedSecond,
                                    expectedYearError, expectedMonthError,
                                    expectedDayError, expectedHourError,
                                    expectedMinuteError, expectedSecondError)

def CheckString(string, expectedString):
    assert isinstance(string, str)
    assert string == expectedString

def CheckIsNone(obj):
    assert obj is None
