# ------------------------------------------------------------------------------
# Name:          HumdrumFileBase.py
# Purpose:       Used to store Humdrum text lines from input stream
#                for further parsing.  This class analyzes the basic
#                spine structure after reading a Humdrum file.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
import typing as t
from pathlib import Path

from music21.common import opFrac

from converter21.humdrum import HumdrumInternalError
from converter21.humdrum import HumHash
from converter21.humdrum import HumNum, HumNumIn
from converter21.humdrum import HumSignifiers
from converter21.humdrum import HumdrumToken
from converter21.humdrum import HumdrumLine

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

# simple class to represent a pair of (first, last) related tokens
class TokenPair:
    def __init__(
            self,
            first: t.Optional[HumdrumToken],
            last: t.Optional[HumdrumToken]
    ) -> None:
        self._first: t.Optional[HumdrumToken] = first
        self._last: t.Optional[HumdrumToken] = last

    @property
    def first(self) -> t.Optional[HumdrumToken]:
        return self._first

    @first.setter
    def first(self, newFirst: HumdrumToken) -> None:
        self._first = newFirst

    @property
    def last(self) -> t.Optional[HumdrumToken]:
        return self._last

    @last.setter
    def last(self, newLast: HumdrumToken) -> None:
        self._last = newLast

    # the following two properties are used for sorting (sort by line index, then by field index)
    @property
    def firstLineIndex(self) -> int:
        if t.TYPE_CHECKING:
            assert isinstance(self._first, HumdrumToken)
        return self._first.lineIndex

    @property
    def firstFieldIndex(self) -> int:
        # Let mypy assume all is well... we'll crash appropriately if someone tries to
        # do this before populating _first.
        if t.TYPE_CHECKING:
            assert isinstance(self._first, HumdrumToken)
        return self._first.fieldIndex


class HumFileAnalysis:
    def __init__(self) -> None:
        self.clear()

    def clear(self) -> None:
        self.structureAnalyzed: bool = False
        self.rhythmAnalyzed: bool = False
        self.strandsAnalyzed: bool = False
        self.slursAnalyzed: bool = False
        self.phrasesAnalyzed: bool = False
        self.nullsAnalyzed: bool = False
        self.strophesAnalyzed: bool = False
        self.barlinesAnalyzed: bool = False
        self.barlinesDifferent: bool = False


class HumdrumFileBase(HumHash):
    '''
        Options bits for getTrackSequence() -> t.List[t.List[HumdrumToken]]
    '''
    OPT_PRIMARY: int = 0x001
    OPT_NOEMPTY: int = 0x002
    OPT_NONULL: int = 0x004
    OPT_NOINTERP: int = 0x008
    OPT_NOMANIP: int = 0x010
    OPT_NOCOMMENT: int = 0x020
    OPT_NOGLOBAL: int = 0x040
    OPT_NOREST: int = 0x080
    OPT_NOTIE: int = 0x100
    OPT_DATA: int = (OPT_NOMANIP
                            | OPT_NOCOMMENT
                            | OPT_NOGLOBAL)
    OPT_ATTACKS: int = (OPT_DATA
                            | OPT_NOREST
                            | OPT_NOTIE
                            | OPT_NONULL)

    def __init__(self, fileName: t.Optional[t.Union[str, Path]] = None) -> None:
        super().__init__()  # initialize the HumHash fields

        '''
        // m_lines: an array representing lines from the input file.
        // The contents of lines must be deallocated when deconstructing object.
        '''
        self._lines: t.List[HumdrumLine] = []

        '''
        // m_filename: name of the file which was loaded.
        '''
        # self._fileName: str = None # weirdly, appears not be set or used

        '''
        // m_segementlevel: segment level (e.g., work/movement)
        '''
        self._segmentLevel: int = 0

        '''
        // m_trackstarts: list of addresses of the exclusive interpreations
        // in the file.  The first element in the list is reserved, so the
        // number of tracks (primary spines) is equal to one less than the
        // size of this list.
        '''
        self._trackStarts: t.List[t.Optional[HumdrumToken]] = [None]

        '''
        // m_trackends: list of the addresses of the spine terminators in the
        // file. It is possible that spines can split and their subspines do not
        // merge before termination; therefore, the ends are stored in
        // a 2d array. The first dimension is the track number, and the second
        // dimension is the list of terminators.
            e.g. trackEnd2 = trackEnds[trackNum][2]
        '''
        self._trackEnds: t.List[t.List[HumdrumToken]] = [[]]

        '''
        // m_barlines: list of barlines in the data.  If the first measures is
        // a pickup measure, then the first entry will not point to the first
        // starting exclusive interpretation line rather than to a barline.
        // LATER: Maybe also add "measures" which are complete metrical cycles.
        '''
        self._barlines: t.List[HumdrumLine] = []

        '''
        // m_ticksperquarternote: this is the number of tick
        '''
        self._ticksPerQuarterNote: int = -1

        '''
        // m_idprefix: an XML id prefix used to avoid id collisions when
        // including multiple HumdrumFile XML in a single group.
        '''
        self._idPrefix: str = ''

        '''
        // m_strands1d: one-dimensional list of spine strands.
        '''
        self._strand1d: t.List[TokenPair] = []

        '''
        // m_strands2d: two-dimensional list of spine strands.
        '''
        self._strand2d: t.List[t.List[TokenPair]] = []

        '''
        // m_strophes1d: one-dimensional list of all *strophe/*Xstrophe pairs.
        '''
        self._strophes1d: t.List[TokenPair] = []

        '''
        // m_strophes2d: two-dimensional list of all *strophe/*Xstrophe pairs.
        '''
        self._strophes2d: t.List[t.List[TokenPair]] = []

        '''
        // m_quietParse: Set to true if error messages should not be
        // printed to the console when reading.
        '''
        self._quietParse: bool = False

        '''
        // m_parseError: Set to true if a read is successful.
        '''
        self._parseError: str = ''

        '''
        // m_displayError: Used to print error message only once.
        '''
        self._displayError: bool = False

        '''
        // m_signifiers: Used to keep track of !!!RDF records.
        '''
        self._signifiers: HumSignifiers = HumSignifiers()

        '''
            _hasInformalBreaks: True if there are '!!pagebreak:' or '!!linebreak:' breaks
                                in the file
            _hasFormalBreaks: True if there are '!LO:LB' or '!LO:PB' breaks in the file
        '''
        self._hasInformalBreaks: bool = False
        self._hasFormalBreaks: bool = False

        '''
        // m_analysis: Used to keep track of analysis states for the file.
        '''
        self._analyses: HumFileAnalysis = HumFileAnalysis()

        '''
            _spineColor: color, indexed by track and subtrack.  '' means use default color
            from iohumdrum.cpp, now computed in HumdrumFileContent.analyzeNotation()
        '''
        self._spineColor: t.List[t.List[str]] = []

        # only used by test infrastructure...
        # if we did this, then we skip the str(hf) == fileContents test
        self.fixedUpRecipOnlyToken: bool = False

        '''
            We are also a HumHash, and that was initialized via super() above.
            But we want our default HumHash prefix to be '!!', not ''
        '''
        self.prefix = '!!'

        if fileName is not None:
            self.read(fileName)

    '''
        Conversion to str.  All the lines, with '\n' between them.
    '''
    def __str__(self) -> str:
        contents: str = ''
        for i, line in enumerate(self._lines):
            if i > 0:
                contents += '\n'
            contents += line.text
        return contents

    '''
        Simple indexer, so you can do line5 = hdFile[5], without giving access to the whole array.
        Equivalent to C++: HumdrumLine& operator[](int index)
        Returns None if index is out of bounds.
    '''
    def __getitem__(self, index: int) -> t.Optional[HumdrumLine]:
        if not isinstance(index, int):
            # if its a slice, out-of-range start/stop won't crash
            return self._lines[index]

        if index < 0:
            index += len(self._lines)

        if index < 0:
            return None
        if index >= len(self._lines):
            return None

        return self._lines[index]

    '''
        A generator, so clients can do: for line in hdFile.lines(), without giving them access
        to the whole array
    '''
    def lines(self):
        for lineIdx in range(0, len(self._lines)):
            yield self._lines[lineIdx]

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::clear -- Reset the contents of a file to be empty.
    '''
    def clear(self) -> None:
        self._lines = []
        # self._fileName = ''
        self._trackStarts = [None]
        self._trackEnds = [[]]
        self._barlines = []
        self._segmentLevel = 0
        self._ticksPerQuarterNote = -1
        self._idPrefix = ''
        self._strand1d = []
        self._strand2d = []
        self._strophes1d = []
        self._strophes2d = []
        self._analyses.clear()

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::read -- Load file contents from an input stream or file.
    '''
    def read(self, fileName: t.Union[str, Path]) -> bool:
        # with open(fileName, errors='backslashreplace') as f: <- this always succeeds, but...
        try:
            with open(fileName, encoding='utf-8') as f:
                s = f.read()
                return self.readString(s)

        except UnicodeDecodeError:
            with open(fileName, encoding='latin-1') as f:
                s = f.read()
                return self.readString(s)

        return False

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::readString -- Read contents from a string rather than
    //    an istream or filename.
    '''
    def readString(self, contents: str) -> bool:
        if contents[-1] == '\n':
            contents = contents[0:-1]  # lose that last empty line (many editors add it)

        contentLines = contents.split('\n')
        # print(funcName(), 'len(contentLines) =', len(contentLines), file=sys.stderr)
        for contentLine in contentLines:
            line = HumdrumLine(contentLine)
            line.ownerFile = self
            self._lines.append(line)

        self.analyzeBaseFromLines()
        # print(funcName(), 'self.isValid =', self.isValid, file=sys.stderr)
        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getMergedSpineInfo -- Will only simplify a two-spine
    //   merge.  Should be expanded to larger spine mergers in the future.
    //   In other words, it is best to currently merge spines in the order
    //   in which they were split, so that the original spine label can
    //   be produced.
    '''
    @staticmethod
    def getMergedSpineInfo(
            info: t.List[str],
            startSpine: int,
            numExtraSpines: int
    ) -> str:
        # print(funcName(), 'startSpine =', startSpine, 'numExtraSpines =', numExtraSpines,
        #       file=sys.stderr)
        # print(funcName(), 'info =', info, file=sys.stderr)

        output: str = ''
        if numExtraSpines < 1:
            # Strange if get here. Nothing to merge.
            return info[startSpine]

        if numExtraSpines == 1:
            # two-spine merge
            # compare all but trailing 'a' or 'b'
            if info[startSpine][:-1] == info[startSpine + 1][:-1]:
                # print(funcName(), 'merged spineInfo =', info[startSpine][1:-2], file=sys.stderr)
                # strip off leading '(' and the trailing ')a' or ')b'
                return info[startSpine][1:-2]
            # print(funcName(), 'merged spineInfo =', info[startSpine] + ' ' + info[startSpine+1],
            #       file=sys.stderr)
            return info[startSpine] + ' ' + info[startSpine + 1]
        '''
        // Generalized code for simplifying up to N subspines at once
        // Not fully generalized so that the subspines will always be
        // simplified if not merged in a simple way, though.
        '''
        newInfo: t.List[str] = [
            info[i] for i in range(startSpine, startSpine + numExtraSpines + 1)
        ]
        while len(newInfo) > 1:
            simplifiedSomething = False
            for i in range(1, len(newInfo)):
                if newInfo[i - 1][:-1] == newInfo[i][:-1]:  # compare all but trailing a or b
                    simplifiedSomething = True
                    newInfo[i - 1] = ''             # we'll remove this later
                    newInfo[i] = newInfo[i][1:-2]   # strip off leading ( and trailing )a or )b

            newInfo2: t.List[str] = []
            for infoStr in newInfo:
                if infoStr != '':
                    newInfo2.append(infoStr)

            for i in range(1, len(newInfo2)):
                if newInfo2[i - 1][:-1] == newInfo2[i][:-1]:  # compare all but trailing a or b
                    simplifiedSomething = True
                    newInfo2[i - 1] = ''             # we'll remove this later
                    newInfo2[i] = newInfo2[i][1:-2]  # strip off leading ( and trailing )a or ')b'

            # do it again back into newInfo
            newInfo = []
            for infoStr in newInfo2:
                if infoStr != '':
                    newInfo.append(infoStr)

            if not simplifiedSomething:
                # we've simplified as much as we can, don't loop forever
                break

        output = newInfo[0]

        # Anything left beyond newInfo[0]? Just join with ' ' as delimiter.
        for i in range(1, len(newInfo)):
            output += ' ' + newInfo[i]

        # print(funcName(), 'merged spineInfo =', output, file=sys.stderr)
        return output


    '''
    //////////////////////////////
    //
    // HumdrumFileBase::addUniqueTokens -- Used for non-null token analysis.

        Adds all tokens from source to target, unless they are already in target.
    '''
    @staticmethod
    def addUniqueTokens(
            target: t.List[HumdrumToken],
            source: t.List[HumdrumToken]
    ) -> None:
        for srcToken in source:
            found = False
            for targToken in target:
                if srcToken == targToken:
                    found = True
                    break
            if not found:
                target.append(srcToken)

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::isStructureAnalyzed --
    '''
    @property
    def isStructureAnalyzed(self) -> bool:
        return self._analyses.structureAnalyzed

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::isRhythmAnalyzed --
    '''
    @property
    def isRhythmAnalyzed(self) -> bool:
        return self._analyses.rhythmAnalyzed

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::areStrandsAnalyzed --
    '''
    @property
    def areStrandsAnalyzed(self) -> bool:
        return self._analyses.strandsAnalyzed

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::areStrophesAnalyzed --
    '''
    @property
    def areStrophesAnalyzed(self) -> bool:
        return self._analyses.strophesAnalyzed

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getXmlIdPrefix -- Return the HumdrumXML ID attribute prefix.
    // HumdrumFileBase::setXmlIdPrefix -- Set the prefix for a HumdrumXML ID
    //     atrribute.  The prefix should not start with a digit, nor have
    //     spaces in it.
    '''
    @property
    def xmlIdPrefix(self) -> str:
        return self._idPrefix

    @xmlIdPrefix.setter
    def xmlIdPrefix(self, newXMLIdPrefix: str) -> None:
        self._idPrefix = newXMLIdPrefix

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getParseError -- Return parse fail reason.
    // HumdrumFileBase::setParseError -- Set an error message from parsing
    //     input data.  The size of the message will keep track of whether
    //     or not an error was generated.  If no error message is generated
    //     when reading data, then the parsing of the data is assumed to be
    //     good.
    '''
    @property
    def parseError(self) -> str:
        return self._parseError

    @parseError.setter
    def parseError(self, err: str) -> None:
        self._parseError = err

    def setParseError(self, err: str) -> bool:
        self.parseError = err
        return err == ''

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::isQuiet -- Returns true if parsing errors
    //    messages should be suppressed. By default the parsing
    //    is "noisy" and the error messages will be printed to
    //    standard error.
    // HumdrumFileBase::setQuietParsing -- Prevent error messages from
    //   being displayed when reading data.
    // @SEEALSO: setQuietParsing
    // @SEEALSO: setNoisyParsing
    '''
    @property
    def isQuiet(self) -> bool:
        return self._isQuiet

    @isQuiet.setter
    def isQuiet(self, newIsQuiet: bool) -> None:
        self._isQuiet = newIsQuiet

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::isValid -- Returns true if last read was
    //     successful.
    '''
    @property
    def isValid(self) -> bool:
        if self._displayError and self.parseError != '' and not self.isQuiet:
            print(self.parseError, file=sys.stderr)
            self._displayError = False

        return self.parseError == ''

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::analyzeBaseFromLines --
    '''
    def analyzeBaseFromLines(self) -> bool:
        if not self.analyzeTokens():
            return self.isValid
        if not self.analyzeLines():
            return self.isValid
        if not self.analyzeSpines():
            return self.isValid
        if not self.analyzeLinks():
            return self.isValid
        if not self.analyzeTracks():
            return self.isValid
        if not self.fixupKernRecipOnlyTokens():
            return self.isValid
        return self.isValid

    # for use by HumdrumWriter, for example, who has already created tokens and lines.
    def analyzeBase(self) -> bool:
        # this only happens in readString, so we need to do it here for exported HumdrumFiles.
        for line in self.lines():
            line.ownerFile = self
        # don't call analyzeTokens, we already have lines from the tokens

        if not self.analyzeLines():
            return self.isValid
        if not self.analyzeSpines():
            return self.isValid
        if not self.analyzeLinks():
            return self.isValid
        if not self.analyzeTracks():
            return self.isValid
        if not self.fixupKernRecipOnlyTokens():
            return self.isValid
        return self.isValid


    '''
        fixupKernRecipOnlyTokens: certain krn files (looking at you,
        rds-scores/R415_Web-w28p2-3m11-19.krn) have recip-only tokens
        in **kern spines.  These appear to be invisible duration markers
        that cover for the fact that some of the notes in this staff
        are actually annotated in other humdrum staffs.  iohumdrum.cpp
        just ignores these, but while that might work for MEI and/or
        verovio, music21 gets very confused if those "rests" are missing
        from a measure/voice.  Here, we fix this up by converting them to
        invisible rests.
    '''
    def fixupKernRecipOnlyTokens(self) -> bool:
        for line in self._lines:
            if line.isGlobal:
                continue

            fixedSomething: bool = False
            for token in line.tokens():
                if token.isKern and token.isRecipOnly:
                    token.text += 'ryy'
                    fixedSomething = True

            if fixedSomething:
                line.createLineFromTokens()
                self.fixedUpRecipOnlyToken = True

        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::analyzeTokens -- Generate token array from
    //    current contents of the lines.  If either tokens or the line
    //    is changed, then the other state becomes invalid.
    //    See createLinesFromTokens for regeneration of lines from tokens.
    '''
    def analyzeTokens(self) -> bool:
        for line in self._lines:
            line.createTokensFromLine()
        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::analyzeLines -- Store a line's index number in the
    //    HumdrumFile within the HumdrumLine object at that index.
    //    Returns false if there was an error.
    '''
    def analyzeLines(self) -> bool:
        for i, line in enumerate(self._lines):
            line.lineIndex = i
        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::analyzeTracks -- Analyze the track structure of the
    //     data.  Returns false if there was a parse error.
    '''
    def analyzeTracks(self) -> bool:
        for line in self._lines:
            success = line.analyzeTracks()
            if not success:
                return False

        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::analyzeLinks -- Generate forward and backwards spine links
    //    for each token.
    //
    '''
    def analyzeLinks(self) -> bool:
        nextLine: t.Optional[HumdrumLine] = None
        prevLine: t.Optional[HumdrumLine] = None
        for line in self._lines:
            if not line.hasSpines:
                continue
            prevLine = nextLine
            nextLine = line
            if prevLine is not None:
                if not self.stitchLinesTogether(prevLine, nextLine):
                    return self.isValid

        return self.isValid

    '''
        analyzeLinksForLines is for use after line insertion.  Make sure
            the range starts and ends on pre-existing (non-inserted) lines,
            and contains all inserted lines.
    '''
    def analyzeLinksForLineRange(self, rangeStart: int, rangeStop: int) -> bool:
        prevLine: t.Optional[HumdrumLine] = None
        nextLine: t.Optional[HumdrumLine] = None

        for lineIdx in range(rangeStart, rangeStop):
            line = self[lineIdx]
            if not line:
                continue
            if not line.hasSpines:
                continue
            prevLine = nextLine
            nextLine = line
            if prevLine is not None:
                if not self.stitchLinesTogether(prevLine, nextLine):
                    return self.isValid

        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::stitchLinesTogether -- Make forward/backward links for
    //    tokens on each line.
    '''
    def stitchLinesTogether(self, prevLine: HumdrumLine, nextLine: HumdrumLine) -> bool:
        # first handle simple cases where the spine assignments are one-to-one:
        if not prevLine.isInterpretation and not nextLine.isInterpretation:
            if prevLine.tokenCount != nextLine.tokenCount:
                return self.setParseError(
                    f'Error lines {prevLine.lineNumber} and {nextLine.lineNumber} '
                    + f'not same length.\nLine {prevLine.lineNumber}: {prevLine.text}\n'
                    + f'Line {nextLine.lineNumber}: {nextLine.text}\n'
                )

            for i, prevTok in enumerate(prevLine.tokens()):
                if nextLine[i] is not None:
                    prevTok.makeForwardLink(nextLine[i])
                else:
                    print('Strange error 1', file=sys.stderr)

            return True

        # Complicated case: spine manipulators have wreaked havoc
        nextTokenIdx: int = 0
        skipOneToken: bool = False
        mergeCount: int = 0
        for i, prevTok in enumerate(prevLine.tokens()):
            if skipOneToken:
                # print('skip one token', file=sys.stderr)
                skipOneToken = False
                continue

            if mergeCount != 0 and prevTok.isMergeInterpretation:
                # Still processing adjacent merge interpretations ('*v').
                # Connect this new adjacent *v spine manipulator to the
                # current next token.
                # print(funcName(), 'found another adjacent merge, i = {}'.format(i))
                if nextLine[nextTokenIdx] is not None:
                    prevTok.makeForwardLink(nextLine[nextTokenIdx])
                else:
                    print('Strange error 1.5', file=sys.stderr)

                mergeCount += 1

                if i != prevLine.tokenCount - 1:
                    continue

                # we're on the last token of the line, so fall through to finish up the merge group
                # print(funcName(), 'falling through because that last merge was at end of line')

            if mergeCount != 0 and (
                    (not prevTok.isMergeInterpretation) or (i == prevLine.tokenCount - 1)):
                # stop processing adjacent merge fields ('*v')
                # print(funcName(), 'last merge in adjacent group noticed at i = {}'.format(i))
                if mergeCount == 1:
                    # print(funcName(), 'bad *v count', file=sys.stderr)
                    return self.setParseError(
                        'Error: single spine merge indicator \'*v\' on line: '
                        + f'{prevLine.lineNumber}\n{prevLine.text}'
                    )
                nextTokenIdx += 1
                # stop counting merges, and fall through to process this non-merge token
                # if this was a merge token (i.e. it was last on the line), don't fall through
                mergeCount = 0
                if prevTok.isMergeInterpretation:
                    continue

            if not prevTok.isManipulator:
                if nextLine[nextTokenIdx] is not None:
                    prevTok.makeForwardLink(nextLine[nextTokenIdx])
                    nextTokenIdx += 1
                else:
                    print('Strange error 2', file=sys.stderr)

            elif prevTok.isSplitInterpretation:
                # Connect the previous token to the next two tokens.
                if nextLine[nextTokenIdx] is not None:
                    prevTok.makeForwardLink(nextLine[nextTokenIdx])
                    nextTokenIdx += 1
                else:
                    print('Strange error 3', file=sys.stderr)

                if nextLine[nextTokenIdx] is not None:
                    prevTok.makeForwardLink(nextLine[nextTokenIdx])
                    nextTokenIdx += 1
                else:
                    print('Strange error 4', file=sys.stderr)

            elif prevTok.isMergeInterpretation:
                # Start processing adjacent merge interpretations.
                # We will connect multiple previous tokens which are adjacent *v
                # spine manipulators to the current next token.
                # Here we do the first one, and the rest are done at the top of
                # the prevTok loop.
                # print(funcName(), 'prevLine {}: {}'.format(prevLine.lineNumber, prevLine.text),
                #       file=sys.stderr)
                # print(funcName(), 'nextLine {}: {}'.format(nextLine.lineNumber, nextLine.text),
                #       file=sys.stderr)
                # print(funcName(), 'found first adjacent merge at i={}'.format(i),
                #       file=sys.stderr)
                # print(funcName(), 'nextTokenIdx =', nextTokenIdx, file=sys.stderr)
                if nextLine[nextTokenIdx] is not None:
                    prevTok.makeForwardLink(nextLine[nextTokenIdx])
                else:
                    print('Strange error 5', file=sys.stderr)
                    raise HumdrumInternalError
                mergeCount = 1

            elif prevTok.isExchangeInterpretation:
                # swapping the order of two spines.
                prevTokPlus1: t.Optional[HumdrumToken] = prevLine[i + 1]
                if prevTokPlus1 is None or not prevTokPlus1.isExchangeInterpretation:
                    return self.setParseError(
                        'Error: single spine exchange indicator \'*x\' on line: '
                        + f'{prevLine.lineNumber}\n{prevLine.text}'
                    )

                nextNext: t.Optional[HumdrumToken] = nextLine[nextTokenIdx]
                if nextNext is not None:
                    prevTokPlus1.makeForwardLink(nextNext)
                else:
                    print('Strange error 6', file=sys.stderr)
                nextNextPlus1: t.Optional[HumdrumToken] = nextLine[nextTokenIdx + 1]
                if nextNextPlus1 is not None:
                    prevTok.makeForwardLink(nextNextPlus1)
                else:
                    print('Strange error 7', file=sys.stderr)
                nextTokenIdx += 2
                skipOneToken = True  # we already processed prevTok[i+1], so skip one prevTok

            elif prevTok.isTerminateInterpretation:
                # No link should be made.  There may be a problem if a
                # new segment is given (this should be handled by a
                # HumdrumSet class, not HumdrumFileBase.
                pass

            elif prevTok.isAddInterpretation:
                # A new data stream is being added, the next linked token
                # should be an exclusive interpretation.
                nextTok: t.Optional[HumdrumToken] = nextLine[nextTokenIdx]
                nextTokPlus1: t.Optional[HumdrumToken] = nextLine[nextTokenIdx + 1]
                if nextTokPlus1 is None or not nextTokPlus1.isExclusiveInterpretation:
                    return self.setParseError(
                        'Error: expecting exclusive interpretation on line '
                        + f'{nextLine.lineNumber} at token {i}, but got {nextTokPlus1}'
                    )
                if nextTok is not None:
                    prevTok.makeForwardLink(nextTok)
                    nextTokenIdx += 1
                else:
                    print('Strange error 8', file=sys.stderr)
                nextTokenIdx += 1

            elif prevTok.isExclusiveInterpretation:
                if nextLine[nextTokenIdx] is not None:
                    prevTok.makeForwardLink(nextLine[nextTokenIdx])
                    nextTokenIdx += 1
                else:
                    print('Strange error 9', file=sys.stderr)

            else:
                return self.setParseError('Error: should not get here')

        if nextTokenIdx != nextLine.tokenCount:
            return self.setParseError(
                f'''Error: cannot stitch lines together due to alignment problem.
Line {prevLine.lineNumber}: {prevLine.text}
Line {nextLine.lineNumber}: {nextLine.text}
nextTokenIdx = {nextTokenIdx}, nextLine.tokenCount = {nextLine.tokenCount}'''
            )

        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::analyzeSpines -- Analyze the spine structure of the
    //     data.  Returns false if there was a parse error.
    '''
    def analyzeSpines(self) -> bool:
        dataType: t.List[str] = []
        sinfo: t.List[str] = []
        lastSpine: t.List[t.List[HumdrumToken]] = []

        self._trackStarts = [None]
        self._trackEnds = [[]]

        seenFirstExInterp = False
        for i, line in enumerate(self._lines):
            if not line.hasSpines and line[0] is not None:
                line[0].fieldIndex = 0  # the only token on the line has fieldIndex 0
                continue

            if not seenFirstExInterp and not line.isExclusiveInterpretation:
                return self.setParseError(
                    f'Error on line: {i+1}:\n'
                    + 'Data found before exclusive interpretation\n'
                    + f'LINE: {line.text}'
                )

            if not seenFirstExInterp and line.isExclusiveInterpretation:
                # first line of data in file
                seenFirstExInterp = True
                dataType = []
                sinfo = []
                for j, token in enumerate(line.tokens()):
                    dataType.append(token.text)
                    self.addToTrackStarts(token)
                    sinfo.append(str(j + 1))
                    token.spineInfo = str(j + 1)
                    token.fieldIndex = j
                    lastSpine.append(token)
                continue

            if len(dataType) != line.tokenCount:
                err = (
                    f'Error on line {line.lineNumber}:\n'
                    + f'Expected {len(dataType)} fields, but found {line.tokenCount}\n'
                    + f'Line is: {line.text}'
                )
                if i > 0:
                    err += f'\nPrevious line is {self._lines[i-1].text}'
                return self.setParseError(err)

            for j, token in enumerate(line.tokens()):
                token.spineInfo = sinfo[j]
                token.fieldIndex = j

            if line.isManipulator:
                success, dataType, sinfo = self.adjustSpines(line, dataType, sinfo)
                if not success:
                    return self.isValid

        return self.isValid

    '''
        HumdrumFileBase::getSpineCount --
    '''
    @property
    def spineCount(self) -> int:
        return self.maxTrack

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::addToTrackStarts -- A starting exclusive interpretation was
    //    found, so store in the list of track starts.  The first index position
    //    in trackstarts is reserve for non-spine usage.
    '''
    def addToTrackStarts(self, token: t.Optional[HumdrumToken]) -> None:
        if token is None:
            self._trackStarts.append(None)
            self._trackEnds.append([])
        elif len(self._trackStarts) > 1 and self._trackStarts[-1] is None:
            self._trackStarts[-1] = token
        else:
            self._trackStarts.append(token)
            self._trackEnds.append([])

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::adjustSpines -- adjust dataType and spineInfo values based
    //   on manipulators found in the data.
    '''
    def adjustSpines(
            self,
            line: HumdrumLine,
            dataType: t.List[str],
            spineInfo: t.List[str]
    ) -> t.Tuple[bool, t.List[str], t.List[str]]:
        # returns success, as well as the newType array, and the newInfo array
        # if there is an error, it returns success=False, and both arrays empty
        newType: t.List[str] = []
        newInfo: t.List[str] = []
        mergeCount: int = 0
        skipOneToken: bool = False

        # print(funcName(), 'line {}: {}'.format(line.lineNumber, line.text), file=sys.stderr)
        # print(funcName(), 'starting dataType =', dataType, file=sys.stderr)
        # print(funcName(), 'starting spineInfo =', spineInfo, file=sys.stderr)

        for i, token in enumerate(line.tokens()):
            if skipOneToken:
                # print(funcName(), 'skipping one token', file=sys.stderr)
                skipOneToken = False
                continue

            if mergeCount > 0 and token.isMergeInterpretation:
                mergeCount += 1
                # print(funcName(), 'found merge token #{} on this line at i = {}'.format(
                #       mergeCount, i), file=sys.stderr)

                if i != line.tokenCount - 1:
                    continue

                # we're on the last token of the line, so fall through to finish up the merge group

            if mergeCount > 0 and (
                    (not token.isMergeInterpretation) or (i == line.tokenCount - 1)):
                # print(funcName(), 'end of merge token group on this line, count =', mergeCount,
                #       file=sys.stderr)
                if mergeCount == 1:
                    # print(funcName(), 'bad *v count', file=sys.stderr)
                    self.setParseError(
                        'Error: single spine merge indicator \'*v\' on line: '
                        + f'{line.lineNumber}\n{line.text}')
                    return (False, [], [])

                # print('spineInfo = ', spineInfo, 'i-mergeCount =', i-mergeCount,
                #       'mergeCount-1 =', mergeCount-1, file=sys.stderr)
                startSpine: int = i - mergeCount
                if token.isMergeInterpretation:
                    # we stopped at the end, so i is one less than usual
                    startSpine += 1
                newInfo.append(self.getMergedSpineInfo(spineInfo, startSpine, mergeCount - 1))
                # print('mergedSpineInfo =', newInfo[-1], file=sys.stderr)
                newType.append(dataType[startSpine])
                # print('new dataType =', newType[-1], file=sys.stderr)
                # stop counting merges, and fall through to process this non-merge token
                # if this was a merge token (i.e. it was last on the line), don't fall through
                mergeCount = 0
                if token.isMergeInterpretation:
                    continue

            if token.isSplitInterpretation:
                newType.append(dataType[i])
                newType.append(dataType[i])
                newInfo.append('(' + spineInfo[i] + ')a')
                newInfo.append('(' + spineInfo[i] + ')b')
            elif token.isMergeInterpretation:
                mergeCount = 1
                # print(funcName(), 'line with merge at i = {}: {}'.format(i, line.text),
                #       file=sys.stderr)
            elif token.isAddInterpretation:
                newType.append(dataType[i])
                newType.append('')
                newInfo.append(spineInfo[i])
                self.addToTrackStarts(None)
                newInfo.append(str(self.maxTrack))
            elif token.isExchangeInterpretation:
                if i >= line.tokenCount - 1:
                    self.setParseError("Error: *x is all alone at end of line")
                    return (False, [], [])
                nextTok: t.Optional[HumdrumToken] = line[i + 1]
                if t.TYPE_CHECKING:
                    # we know nextTok is not None because of i range check above
                    assert isinstance(nextTok, HumdrumToken)
                if not nextTok.isExchangeInterpretation:  # line[index] is index'th token
                    self.setParseError('Error: *x is all alone')
                    return (False, [], [])
                newType.append(dataType[i + 1])
                newType.append(dataType[i])
                newInfo.append(spineInfo[i + 1])
                newInfo.append(spineInfo[i])
                skipOneToken = True  # we already processed it here
            elif token.isTerminateInterpretation:
                # store pointer to terminate token in trackends
                # print(funcName(), 'trackStarts = {}, trackEnds = {}'.format(
                #       self._trackStarts, self._trackEnds), file=sys.stderr)
                self._trackEnds[len(self._trackStarts) - 1].append(token)
            elif token.isExclusiveInterpretation:
                newType.append(token.text)
                newInfo.append(spineInfo[i])
                if not (len(self._trackStarts) > 1 and self._trackStarts[-1] is None):
                    self.setParseError(
                        'Error: Exclusive interpretation with no preparation '
                        + f'on line {line.lineNumber} spine index {i}\n'
                        + f'Line: {line.text}'
                    )
                    return (False, [], [])
                if self._trackStarts[-1] is None:
                    self.addToTrackStarts(token)
            else:
                # should only be null interpretation
                newType.append(dataType[i])
                newInfo.append(spineInfo[i])

        # print(funcName(), 'ending dataType =', newType, file=sys.stderr)
        # print(funcName(), 'ending spineInfo =', newInfo, file=sys.stderr)
        return (True, newType, newInfo)

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::createLinesFromTokens -- Generate Humdrum lines strings
    //   from the stored list of tokens.
    '''
    def createLinesFromTokens(self) -> None:
        for line in self._lines:
            line.createLineFromTokens()

    '''
    ////////////////////////////
    //
    // HumdrumFileBase::appendLine -- Add a line to the file's contents.  The file's
    //    spine and rhythmic structure should be recalculated after an append.
    '''
    def appendLine(
            self,
            line: t.Union[HumdrumLine, str],
            asGlobalToken: bool = False,
            analyzeTokenLinks: bool = False
    ) -> None:
        if isinstance(line, str):
            line = HumdrumLine(line, asGlobalToken=asGlobalToken)
        if not isinstance(line, HumdrumLine):
            raise TypeError('appendLine must receive either line: str or line: HumdrumLine')
        self._lines.append(line)

        # if requested, re-analyze token links around the insertion
        if analyzeTokenLinks:
            startIdx: int = self.lineCount - 2  # previous last line
            endIdx: int = self.lineCount - 1    # new last line
            self.analyzeLinksForLineRange(startIdx, endIdx + 1)

    '''
    ////////////////////////////
    //
    // HumdrumFileBase::insertLine -- Add a line to the file's contents.  The file's
    //    spine and rhythmic structure should be recalculated after an append.
    '''
    def insertLine(
            self,
            index: int,
            aLine: t.Union[HumdrumLine, str],
            asGlobalToken: bool = False,
            analyzeTokenLinks: bool = False) -> None:
        if isinstance(aLine, str):
            aLine = HumdrumLine(aLine, asGlobalToken=asGlobalToken)
        if not isinstance(aLine, HumdrumLine):
            raise TypeError('insertLine must receive either line: str or line: HumdrumLine')
        self._lines.insert(index, aLine)

        # update line indexes for this line and the following ones
        for i, line in enumerate(self._lines):
            if i >= index:
                line.lineIndex = i

        # if requested, re-analyze token links around the insertion
        if analyzeTokenLinks:
            startIdx: int = max(0, index)
            endIdx: int = min(index + 1, self.lineCount - 1)
            self.analyzeLinksForLineRange(startIdx, endIdx + 1)

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::insertNullDataLine -- Add a null data line at
    //     the given absolute quarter-note timestamp in the file.  If there
    //     is already a data line at the given timestamp, then do not create
    //     a line and instead return a pointer to the existing line.  Returns
    //     NULL if there was a problem.
    '''
    def insertNullDataLine(self, timestamp: HumNumIn) -> t.Optional[HumdrumLine]:
        ts: HumNum = opFrac(timestamp)
        # for now do a linear search for the insertion point, but later
        # do something more efficient.
        beforet: t.Optional[HumNum] = None
        beforei: t.Optional[int] = None

        for i, line in enumerate(self.lines()):
            if not line.isData:
                continue

            current: HumNum = line.durationFromStart
            if current == ts:
                return line

            if current > ts:
                break

            beforet = current
            beforei = i

        if beforei is None:
            return None

        # This check is currently not necessary, since beforei and beforet are
        # both set at the same time, but will that always be true?
        # Also, mypy isn't smart enough to know, so this is a mypy hint.
        if beforet is None:
            return None

        beforeLine: t.Optional[HumdrumLine] = self[beforei]
        if t.TYPE_CHECKING:
            # we know beforeLine is not None because we found it above
            # in self.lines() which never returns None.
            assert isinstance(beforeLine, HumdrumLine)

        newLine: HumdrumLine = HumdrumLine()

        # copyStructure will add null tokens automatically
        newLine.copyStructure(beforeLine, '.')

        self.insertLine(beforei + 1, newLine)

        # Set the timestamp information for inserted line:
        delta: HumNum = opFrac(ts - beforet)

        newLine.durationFromStart = opFrac(beforeLine.durationFromStart + delta)
        newLine.durationFromBarline = opFrac(beforeLine.durationFromBarline + delta)
        newLine.durationToBarline = opFrac(beforeLine.durationToBarline - delta)
        newLine.duration = opFrac(beforeLine.duration - delta)
        beforeLine.duration = delta

        for beforeToken, newToken in zip(beforeLine.tokens(), newLine.tokens()):
            beforeToken.insertTokenAfter(newToken)

        return newLine

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::insertNullInterpretationLine -- Add a null interpretation
    //     line at the given absolute quarter-note timestamp in the file.  The line will
    //     be added after any other interpretation lines at that timestamp, but before any
    //     local comments that appear immediately before the data line(s) at that timestamp.
    //     Returns NULL if there was a problem.
    '''
    def insertNullInterpretationLine(self, timestamp: HumNumIn) -> t.Optional[HumdrumLine]:
        ts: HumNum = opFrac(timestamp)
        # for now do a linear search for the insertion point, but later
        # do something more efficient.
        beforei: t.Optional[int] = None

        for i, line in enumerate(self.lines()):
            if not line.isData:
                continue

            current: HumNum = line.durationFromStart
            if current == ts:
                beforei = i
                break

            if current > ts:
                break

            beforei = i

        if beforei is None:
            return None

        targetLine: t.Optional[HumdrumLine] = self.getLineForInterpretationInsertion(beforei)
        if t.TYPE_CHECKING:
            # we know that targetLine is not None, because beforei is a valid line.
            assert isinstance(targetLine, HumdrumLine)
        newLine: HumdrumLine = HumdrumLine()
        # copyStructure will add null tokens automatically
        newLine.copyStructure(targetLine, '*')

        targeti: int = targetLine.lineIndex
        self.insertLine(targeti, newLine)

        # inserted line will increment beforei by one:
        beforei += 1
        beforeLine: t.Optional[HumdrumLine] = self[beforei]
        if t.TYPE_CHECKING:
            # we know beforeLine is not None because we know that beforei
            # is in range.  We found it in range, then incremented it after
            # inserting a line before it (so it's still in range).
            assert isinstance(beforeLine, HumdrumLine)

        newLine.durationFromStart = beforeLine.durationFromStart
        newLine.durationFromBarline = beforeLine.durationFromBarline
        newLine.durationToBarline = beforeLine.durationToBarline
        newLine.duration = opFrac(0)

        # Problems here if targetLine is a manipulator
        for targetToken, newToken in zip(targetLine.tokens(), newLine.tokens()):
            targetToken.insertTokenAfter(newToken)

        return newLine

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::insertNullInterpretationLineAbove -- Add a null interpretation
    //     line at the given absolute quarter-note timestamp in the file.  The line will
    //     be added before any other lines at that timestamp.
    //     Returns NULL if there was a problem.
    '''
    def insertNullInterpretationLineAbove(self, timestamp: HumNumIn) -> t.Optional[HumdrumLine]:
        ts: HumNum = opFrac(timestamp)
        beforei: t.Optional[int] = None

        for i, line in enumerate(self.lines()):
            current: HumNum = line.durationFromStart
            if current == ts:
                beforei = i
                break
            if current > ts:
                break

            beforei = i

        if beforei is None:
            return None

        targetLine: t.Optional[HumdrumLine] = self.getLineForInterpretationInsertionAbove(beforei)
        if t.TYPE_CHECKING:
            # we know that targetLine is not None, because beforei is a valid line.
            assert isinstance(targetLine, HumdrumLine)

        newLine: HumdrumLine = HumdrumLine()
        newLine.copyStructure(targetLine, '*')

        targeti: int = targetLine.lineIndex

        self.insertLine(targeti, newLine)

        beforei += 1
        beforeLine: t.Optional[HumdrumLine] = self[beforei]
        if t.TYPE_CHECKING:
            # we know beforeLine is not None because we know that beforei
            # is in range.  We found it in range, then incremented it after
            # inserting a line well before it (so it's still in range).
            assert isinstance(beforeLine, HumdrumLine)

        newLine.durationFromStart = beforeLine.durationFromStart
        newLine.durationFromBarline = beforeLine.durationFromBarline
        newLine.durationToBarline = beforeLine.durationToBarline
        newLine.duration = opFrac(0)

        for targetToken, newToken in zip(targetLine.tokens(), newLine.tokens()):
            targetToken.insertTokenAfter(newToken)

        return newLine

    '''
        insertNullInterpretationLineAt(lineIndex) does exactly that, including
        hooking up the inter-line token links. The structure of the null interp
        line is determined by copying the line that is currently at lineIndex
        before the insertion.
        The newly created null interp line is returned.
    '''
    def insertNullInterpretationLineAt(self, lineIndex: int) -> HumdrumLine:
        newLine: HumdrumLine = HumdrumLine()

        if self.lineCount <= 0:
            raise HumdrumInternalError('Cannot insert a null interpretation line in an empty file')
        if lineIndex > self.lineCount:
            raise HumdrumInternalError('Cannot insert a null interpretion line beyond the EOF')

        if lineIndex < self.lineCount:
            # insert the new line
            nextLine: t.Optional[HumdrumLine] = self[lineIndex]
            if t.TYPE_CHECKING:
                # we know nextLine is not None because lineIndex < self.lineCount
                assert isinstance(nextLine, HumdrumLine)

            copyLine: t.Optional[HumdrumLine] = nextLine
            if not nextLine.hasSpines:
                copyLine = self[lineIndex - 1]  # problem if previous line is manipulator
            if copyLine is None or not copyLine.hasSpines:
                raise HumdrumInternalError(
                    'Cannot insert a null interpretation line between two unspined lines'
                )
            newLine.copyStructure(copyLine, '*')
            newLine.durationFromStart = nextLine.durationFromStart
            newLine.durationFromBarline = nextLine.durationFromBarline
            newLine.durationToBarline = nextLine.durationToBarline
            newLine.duration = opFrac(0)
            self.insertLine(lineIndex, newLine, analyzeTokenLinks=True)
        else:
            # append the new line
            prevLine: t.Optional[HumdrumLine] = self[lineIndex - 1]
            if t.TYPE_CHECKING:
                # we know prevLine is not None because we are appending, and if there
                # is no previous line, then we are appending to an empty file, and
                # we checked that first thing (if self.lineCount <= 0).
                assert isinstance(prevLine, HumdrumLine)

            newLine.copyStructure(prevLine, '*')  # problem if prevLine is manipulator
            newLine.durationFromStart = opFrac(prevLine.durationFromStart + prevLine.duration)
            newLine.durationFromBarline = opFrac(prevLine.durationFromBarline + prevLine.duration)
            newLine.durationToBarline = opFrac(prevLine.durationToBarline + prevLine.duration)
            newLine.duration = opFrac(0)
            self.appendLine(newLine, analyzeTokenLinks=True)

        return newLine

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getLineForInterpretationInsertion --  Search backwards
    //    in the file for the first local comment immediately before a data line
    //    index given as input.  If there are no local comments, then return the
    //    data line.  If there are local comment lines immediately before the data
    //    line, then keep searching for the first local comment.  Non-spined lines
    //    (global or empty lines) are ignored.  This function is used to insert
    //    an empty interpretation before a data line at a specific data line.
    '''
    def getLineForInterpretationInsertion(self, index: int) -> t.Optional[HumdrumLine]:
        if index not in range(0, self.lineCount):
            return None

        current: int = index - 1
        previous: int = index
        while current > 0:
            currentLine: t.Optional[HumdrumLine] = self[current]
            if t.TYPE_CHECKING:
                # we know currentLine is not None because current is in range
                assert isinstance(currentLine, HumdrumLine)

            if not currentLine.hasSpines:
                current -= 1
                continue
            if currentLine.isLocalComment:
                previous = current
                current -= 1
                continue

            return self[previous]

        return self[index]

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getLineForInterpretationInsertionAbove --  Search backwards
    //    in the file for the first line at the same timestamp as the starting line.
    '''
    def getLineForInterpretationInsertionAbove(self, index: int) -> t.Optional[HumdrumLine]:
        if index not in range(0, self.lineCount):
            return None

        timestamp: HumNum = self._lines[index].durationFromStart
        current: int = index - 1
        previous: int = index
        while current > 0:
            currentLine: t.Optional[HumdrumLine] = self[current]
            if t.TYPE_CHECKING:
                # we know currentLine is not None because current is in range
                assert isinstance(currentLine, HumdrumLine)

            if not currentLine.hasSpines:
                current -= 1
                continue
            teststamp: HumNum = currentLine.durationFromStart
            if teststamp == timestamp:
                previous = current
                current -= 1
                continue

            return self[previous]

        return self[index]

    '''
    ////////////////////////////
    //
    // HumdrumFileBase::getLineCount -- Returns the number of lines.
    '''
    @property
    def lineCount(self) -> int:
        return len(self._lines)

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getReferenceRecords --
    '''
    def referenceRecords(self) -> t.List[HumdrumLine]:
        refLines = []
        for line in self._lines:
            if line.isReference:
                refLines.append(line)

        return refLines

    def getReferenceValueForKey(self, key: str) -> str:
        for line in self.referenceRecords():
            if line.referenceKey == key:
                return line.referenceValue
        return ''

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getGlobalReferenceRecords --
    '''
    def globalReferenceRecords(self) -> t.List[HumdrumLine]:
        refLines = []
        for line in self._lines:
            if line.isGlobalReference:
                refLines.append(line)

        return refLines

    def getGlobalReferenceValueForKey(self, key: str) -> str:
        for line in self.globalReferenceRecords():
            if line.referenceKey == key:
                return line.referenceValue
        return ''

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getUniversalReferenceRecords --
    '''
    def universalReferenceRecords(self) -> t.List[HumdrumLine]:
        refLines = []
        for line in self._lines:
            if line.isUniversalReference:
                refLines.append(line)

        return refLines

    def getUniversalReferenceValueForKey(self, key: str) -> str:
        for line in self.universalReferenceRecords():
            if line.referenceKey == key:
                return line.referenceValue
        return ''

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::token -- Return the token at the given line/field index.
    //

        Clients can just do:
            tok = hdFile[lineindex][tokenindex]
    '''

    '''
    //
    // Special case that returns a subtoken string:
    //

        Clients can just do:
            subTok = hdFile[lineindex][tokenindex].subTokens[subTokenIndex]
    '''

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getMaxTrack -- Returns the number of primary
    //     spines in the data.
    '''
    @property
    def maxTrack(self) -> int:
        return len(self._trackStarts) - 1

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getExinterpCount -- return the number of spines in
    //    the file that are of the given exinterp type.  The input string
    //    may optionally include the ** exinterp prefix.
    '''
    def getExInterpCount(self, exInterp: str) -> int:
        return len(self.spineStartListOfType(exInterp))

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getSpineStopList -- Return a list of the ending
    //     points of spine strands.
    '''
    @property
    def spineStopList(self) -> t.List[HumdrumToken]:
        return [trackEnd for trackEndList in self._trackEnds for trackEnd in trackEndList]

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getSpineStartList -- Return a list of the exclustive
    //     interpretations starting spines in the data.  The single parameter
    //     version of the fuction returns all starting exclusive interpretations.
    //     The two-parameter version will result all exclusive interpretations
    //     of a given datatype, and the three-parameter version where the third
    //     parameter is a vector of string, will selectively include all starting
    //     tokens which match one of the data types in the input list.  The
    //     trackstarts class variable contains an empty slot at index 0;
    //     this is removed in the return vector.
    '''
    @property
    def spineStartList(self) -> t.List[t.Optional[HumdrumToken]]:
        return self._trackStarts[1:]

    def spineStartListOfType(self, exInterps: t.Union[str, t.List[str]]) -> t.List[HumdrumToken]:
        output: t.List[HumdrumToken] = []

        if isinstance(exInterps, str):
            exInterps = [exInterps]  # convert to t.List[str]

        newExInterps = [''] * len(exInterps)
        for i, exInterp in enumerate(exInterps):
            if exInterp.startswith('**'):
                newExInterps[i] = exInterp
            else:
                newExInterps[i] = '**' + exInterp

        for i, trackStart in enumerate(self._trackStarts):
            if i == 0:
                continue  # skip the first entry (there is no track 0)
            if trackStart is None:
                continue

            for exInterp in newExInterps:
                if exInterp == trackStart.text:
                    output.append(trackStart)
                    break

        return output

    def kernSpineStartList(self) -> t.List[HumdrumToken]:
        return self.spineStartListOfType('**kern')

    '''
    //////////////////////////////
    //
    // getPrimaryspineSequence -- Return a list of the HumdrumTokens in a spine,
    //    but not any secondary spine content if the spine splits.

        Note that spine numbers start at 0, and track numbers start at 1
    '''
    def getPrimarySpineSequence(self, spine: int, options: int) -> t.List[HumdrumToken]:
        track = spine + 1
        return self.getPrimaryTrackSequence(track, options)

    '''
    //////////////////////////////
    //
        getSpineSequence -- Return a list of the HumdrumTokens in a spine,
            including secondary spine content if the spine splits.

            Clients can specify spine, or startToken.  We will use spine if
            the client specifies both.
    '''
    def getSpineSequence(
            self,
            spine: int,
            startToken: t.Optional[HumdrumToken] = None,
            options: int = 0
    ) -> t.List[t.List[HumdrumToken]]:
        if startToken is not None:
            track = startToken.track  # get the track number from the token
        else:
            track = spine + 1  # get the track number from the spine number
        return self.getTrackSequence(track=track, options=options)

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getPrimaryTrackSequence -- Return a list of the
    //     given primary spine tokens for a given track (indexed starting at
    //     one and going through getMaxTrack().
    '''
    def getPrimaryTrackSequence(self, track: int, options: int) -> t.List[HumdrumToken]:
        tempSeq: t.List[t.List[HumdrumToken]] = self.getTrackSequence(
            track=track,
            options=(options | self.OPT_PRIMARY)
        )
        return [tokenList[0] for tokenList in tempSeq]

    '''
    /////////////////////////////
    //
    // HumdrumFileBase::getTrackSequence -- Extract a sequence of tokens
    //    for the given spine.  All subspine tokens will be included.
    //    See getPrimaryTrackSequence() if you only want the first subspine for
    //    a track on all lines.
    //
    // The following options are used for the getPrimaryTrackTokens:
    // * OPT_PRIMARY    => only extract primary subspine/subtrack.
    // * OPT_NOEMPTY    => don't include null tokens in extracted list if all
    //                        extracted subspines contains null tokens.
    //                        Includes null interpretations and comments as well.
    // * OPT_NONULL     => don't include any null tokens in extracted list.
    // * OPT_NOINTERP   => don't include interpretation tokens.
    // * OPT_NOMANIP    => don't include spine manipulators (*^, *v, *x, *+,
    //                        but still keep ** and *0).
    // * OPT_NOCOMMENT  => don't include comment tokens.
    // * OPT_NOGLOBAL   => don't include global records (global comments, reference
    //                        records, and empty lines). In other words, only return
    //                        a list of tokens from lines which hasSpines() it true.
    // * OPT_NOREST     => don't include **kern rests.
    // * OPT_NOTIE      => don't include **kern secondary tied notes.
    // Compound options:
    // * OPT_DATA      (OPT_NOMANIP | OPT_NOCOMMENT | OPT_NOGLOBAL)
    //     Only data tokens (including barlines)
    // * OPT_ATTACKS   (OPT_DATA | OPT_NOREST | OPT_NOTIE | OPT_NONULL)
    //     Only note-attack tokens (when etracting **kern data)
    '''
    def getTrackSequence(
            self,
            track: t.Optional[int] = None,
            startToken: t.Optional[HumdrumToken] = None,
            options: int = 0
    ) -> t.List[t.List[HumdrumToken]]:
        output: t.List[t.List[HumdrumToken]] = []

        if startToken is not None:
            track = startToken.track  # get the track number from the token

        optionPrimary: bool = (options & self.OPT_PRIMARY) == self.OPT_PRIMARY
        optionNoNull: bool = (options & self.OPT_NONULL) == self.OPT_NONULL
        optionNoEmpty: bool = (options & self.OPT_NOEMPTY) == self.OPT_NOEMPTY
        optionNoInterp: bool = (options & self.OPT_NOINTERP) == self.OPT_NOINTERP
        optionNoManip: bool = (options & self.OPT_NOMANIP) == self.OPT_NOMANIP
        optionNoComment: bool = (options & self.OPT_NOCOMMENT) == self.OPT_NOCOMMENT
        optionNoGlobal: bool = (options & self.OPT_NOGLOBAL) == self.OPT_NOGLOBAL
        optionNoRest: bool = (options & self.OPT_NOREST) == self.OPT_NOREST
        optionNoTie: bool = (options & self.OPT_NOTIE) == self.OPT_NOTIE

        for line in self._lines:
            if line.isEmpty:
                continue

            tempTokens = []
            if not optionNoGlobal and line.isGlobal:
                # append [the entire global line] to output
                token0: t.Optional[HumdrumToken] = line[0]
                if token0 is not None:
                    tempTokens.append(token0)
                    output.append(tempTokens)
                continue

            if optionNoEmpty:
                # if all tokens on line (in this track) are null, continue
                allNull: bool = True
                for token in line.tokens():
                    if token.track != track:
                        continue
                    if not token.isNull:
                        allNull = False
                        break
                if allNull:
                    continue

            foundTrack: bool = False
            for token in line.tokens():
                if token.track != track:
                    continue
                if optionPrimary and foundTrack:
                    continue

                foundTrack = True
                if optionNoInterp and token.isInterpretation:
                    continue
                if optionNoManip and token.isManipulator:
                    continue
                if optionNoNull and token.isNull:
                    continue
                if optionNoComment and token.isComment:
                    continue
                if optionNoRest and token.isRest:
                    continue
                if optionNoTie and token.isSecondaryTiedNote:
                    continue

                tempTokens.append(token)

            if tempTokens:
                output.append(tempTokens)

        return output

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getTrackStart -- Return the starting exclusive
    //     interpretation for the given track.  Returns NULL if the track
    //     number is out of range.
    '''
    def trackStart(self, track: t.Optional[int]) -> t.Optional[HumdrumToken]:
        if track is None:
            return None

        if track < 0:
            track += len(self._trackStarts)

        if track < 1 or track >= len(self._trackStarts):
            return None

        return self._trackStarts[track]

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getTrackEndCount -- Return the number of ending tokens
    //    for the given track.  Spines must start as a single exclusive
    //    interpretation token.  However, since spines may split and merge,
    //    it is possible that there are more than one termination points for a
    //    track.  This function returns the number of terminations which are
    //    present in a file for any given spine/track.
        Returns 0 if track number is out of range.
    '''
    def trackEndCount(self, track: int) -> int:
        if track < 0:
            track += len(self._trackEnds)
        if track < 1 or track >= len(self._trackEnds):
            return 0

        return len(self._trackEnds[track])

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::getTrackEnd -- Returns a pointer to the terminal manipulator
    //    token for the given track and subtrack.  Sub-tracks are indexed from 0 up
    //    to but not including getTrackEndCount.
    '''
    def trackEnd(self, track: int, subTrack: int) -> t.Optional[HumdrumToken]:
        if track < 0:
            track += len(self._trackEnds)

        if track < 0:
            return None

        if track > self.maxTrack:
            return None

        if subTrack < 0:
            subTrack += self.trackEndCount(track)

        if subTrack < 0 or subTrack >= len(self._trackEnds[track]):
            return None

        return self._trackEnds[track][subTrack]

    '''
    //////////////////////////////
    //
    // HumdrumFileBase::analyzeNonNullDataTokens -- For null data tokens, indicate
    //    the previous non-null token which the null token refers to.  After
    //    a spine merger, there may be multiple previous tokens, so you would
    //        have to decide on the actual source token on based on subtrack or
    //    sub-spine information.  The function also gives links to the previous/next
    //    non-null tokens, skipping over intervening null data tokens.

        Not called internally.  Called by HumdrumFileStructure.py
    '''
    def analyzeNonNullDataTokens(self) -> bool:
        ptokens: t.List[HumdrumToken] = []

        # analyze forward tokens:
        for i in range(1, self.maxTrack + 1):
            trackStart: t.Optional[HumdrumToken] = self._trackStarts[i]
            if trackStart is None:
                # I don't think this can happen, but I'm not sure.
                continue
            if not self.processNonNullDataTokensForTrackForward(trackStart, ptokens):
                return False

        ptokens = []  # starting another recursion

        # analyze backward tokens:
        for i in range(1, self.maxTrack + 1):
            for j in range(0, self.trackEndCount(i)):
                if not self.processNonNullDataTokensForTrackBackward(
                        self._trackEnds[i][j], ptokens):
                    return False

        '''
        // Eventually set the forward and backward non-null data token for
        // tokens in spines for all types of line types.  For now specify
        // the next non-null data token for the exclusive interpretation token.
        // Also this implementation does not consider that the first
        // non-null data tokens may be from multiple split tokens (fix later).

        // This algorithm is probably not right, but good enough for now.
        // There may be missing portions of the file for the analysis,
        // and/or the algorithm is probably retracking tokens in the case
        // of spine splits.
        '''
        stops: t.List[HumdrumToken] = self.spineStopList
        nexts: t.Optional[HumdrumToken] = None

        for stop in stops:
            if stop is None:
                continue

            # start at the track stop token and work backwards
            token: t.Optional[HumdrumToken] = stop
            if t.TYPE_CHECKING:
                # we know token is not None because stop/stops are not Optional
                assert isinstance(token, HumdrumToken)
            if token.isNonNullData:
                nexts = token

            token = token.previousToken0
            while token is not None:
                if nexts is not None:
                    token.addNextNonNullDataToken(nexts)
                if token.isNonNullData:
                    nexts = token
                token = token.previousToken0

        return True

    '''
    //////////////////////////////
    //
    // HumdrumFile::processNonNullDataTokensForTrackBackward -- Helper function
    //    for analyzeNonNullDataTokens.  Given any token, this function tells
    //    you what is the next non-null data token(s) in the spine after the given
    //    token.
    '''
    def processNonNullDataTokensForTrackBackward(self,
            endToken: HumdrumToken,
            ptokens: t.List[HumdrumToken]
    ) -> bool:
        token: HumdrumToken = endToken
        tcount: int = token.previousTokenCount

        while tcount > 0:
            for i in range(1, tcount):
                prevtok: t.Optional[HumdrumToken] = token.previousToken(i)
                if t.TYPE_CHECKING:
                    # we know prevtok is not None because i is in range
                    assert isinstance(prevtok, HumdrumToken)

                if not self.processNonNullDataTokensForTrackBackward(prevtok, ptokens):
                    return False

            prevToken: t.Optional[HumdrumToken] = token.previousToken0
            if t.TYPE_CHECKING:
                # we know prevToken is not None because 0 is in range (tcount > 0)
                assert isinstance(prevToken, HumdrumToken)

            if prevToken.isSplitInterpretation:
                self.addUniqueTokens(prevToken.nextNonNullDataTokens, ptokens)
                if token != prevToken.nextToken0:
                    # terminate if not most primary subspine
                    return True
            elif token.isData:
                self.addUniqueTokens(token.nextNonNullDataTokens, ptokens)
                if not token.isNull:
                    ptokens = [token]  # nukes the existing ptokens list

            # Follow previous data token 0 since 1 and higher are handled above.
            token = prevToken
            tcount = token.previousTokenCount

        return True

    '''
    //////////////////////////////
    //
    // HumdrumFile::processNonNullDataTokensForTrackForward -- Helper function
    //    for analyzeNonNullDataTokens.  Given any token, this function tells
    //    you what are the previous non-null data token(s) in the spine before
    //    the given token.
    '''
    def processNonNullDataTokensForTrackForward(self,
            startToken: HumdrumToken,
            ptokens: t.List[HumdrumToken]
    ) -> bool:
        token: HumdrumToken = startToken
        tcount: int = token.nextTokenCount

        while tcount > 0:
            nextToken: t.Optional[HumdrumToken] = None
            if token.isSplitInterpretation:
                for i in range(1, tcount):
                    nextTok: t.Optional[HumdrumToken] = token.nextToken(i)
                    if t.TYPE_CHECKING:
                        # we know nextTok is not None because i is in range
                        assert isinstance(nextTok, HumdrumToken)

                    if not self.processNonNullDataTokensForTrackForward(nextTok, ptokens):
                        return False
            elif token.isMergeInterpretation:
                nextToken = token.nextToken0
                if t.TYPE_CHECKING:
                    # we know nextToken is not None because 0 is in range (tcount > 0)
                    assert isinstance(nextToken, HumdrumToken)

                self.addUniqueTokens(nextToken.previousNonNullDataTokens, ptokens)
                if token != nextToken.previousToken0:
                    # terminate if not most primary subspine
                    return True
            else:
                self.addUniqueTokens(token.previousNonNullDataTokens, ptokens)
                if token.isNonNullData:
                    ptokens = [token]  # nukes the existing ptokens list

            # Data tokens can only be followed by up to one next token,
            # so no need to check for more than one next token.
            nextToken = token.nextToken0
            if t.TYPE_CHECKING:
                # we know nextToken is not None because 0 is in range (tcount > 0)
                assert isinstance(nextToken, HumdrumToken)

            token = nextToken
            tcount = token.nextTokenCount

        return True

    '''
    //////////////////////////////
    //
    // operator<< -- Default method of printing HumdrumFiles.  This printing method
    //    assumes that the HumdrumLine string is correct.  If a token is changed
    //    in the file, the HumdrumFileBase::createLinesFromTokens() before printing
    //    the contents of the line.
    '''
    def write(self, fp) -> None:
        for line in self._lines:
            line.write(fp)
