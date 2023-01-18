# ------------------------------------------------------------------------------
# Name:          HumdrumFileStructure.py
# Purpose:       Responsible for rhythm analysis, parameter analysis (including
#                RDF signifier analysis), null token resolution, strand analysis,
#                and strophe analysis.
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
from operator import attrgetter
from fractions import Fraction
from pathlib import Path

from music21.common import opFrac

from converter21.humdrum import HumdrumInternalError
from converter21.humdrum import HumNum, HumNumIn
from converter21.humdrum import Convert
from converter21.humdrum import HumdrumToken
from converter21.humdrum import HumdrumLine
from converter21.humdrum import HumdrumFileBase
from converter21.humdrum import TokenPair

class HumdrumFileStructure(HumdrumFileBase):
    # HumdrumFileStructure has no private data to initialize, just a bunch more functions
    # So... no __init__
    # Except... pylint is unhappy about some data it thinks is uninitialized (because it's
    # initialized in HumdrumFileBase), so let's initialize it here, too.
    def __init__(self, fileName: t.Optional[t.Union[str, Path]] = None) -> None:
        super().__init__(fileName)
        self._ticksPerQuarterNote: int = -1
        self._barlines: t.List[HumdrumLine] = []
        self._strand1d: t.List[TokenPair] = []
        self._strand2d: t.List[t.List[TokenPair]] = []

    def readString(self, contents: str) -> bool:
        if not super().readString(contents):
            return self.isValid
        return self.analyzeStructure()

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::analyzeStructure -- Analyze global/local
    //    parameters and rhythmic structure.
    '''
    def analyzeStructure(self) -> bool:
        # unconditionally re-analyzes everything (except strands, for some reason)
        # called from various tools, not just from self.readString()
        success = self.analyzeStructureNoRhythm()
        if not success:
            return self.isValid

        success = self.analyzeRhythmStructure()
        if not success:
            return self.isValid

        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::analyzeStructureNoRhythm -- Analyze global/local
    //    parameters but not rhythmic structure.
    '''
    def analyzeStructureNoRhythm(self) -> bool:
        # called from analyzeStructure unconditionally, and from analyzeRhythmStructure if necessary
        self._analyses.structureAnalyzed = True

        if not self.areStrandsAnalyzed:
            success = self.analyzeStrands()
            if not success:
                return self.isValid

        success = self.analyzeGlobalParameters()
        if not success:
            return self.isValid

        success = self.analyzeLocalParameters()
        if not success:
            return self.isValid

        success = self.analyzeTokenDurations()
        if not success:
            return self.isValid

        self.analyzeSignifiers()

        return self.isValid

    '''
    /////////////////////////////
    //
    // HumdrumFileStructure::analyzeRhythmStructure --
    '''
    def analyzeRhythmStructure(self) -> bool:
        # called from HumdrumLine, not just from self.analyzeStructure(),
        # thus the need to analyzeStructureNoRhythm, if necessary
        self._analyses.rhythmAnalyzed = True
        self.setLinesRhythmAnalyzed()

        if not self.isStructureAnalyzed:
            success = self.analyzeStructureNoRhythm()
            if not success:
                return self.isValid

        firstSpine: t.Optional[HumdrumToken] = self.spineStartList[0]
        if firstSpine is not None and firstSpine.isDataType('**recip'):
            self.assignRhythmFromRecip(firstSpine)
        else:
            success = self.analyzeRhythm()
            if not success:
                return self.isValid
            success = self.analyzeDurationsOfNonRhythmicSpines()
            if not success:
                return self.isValid
        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::getScoreDuration -- Return the total duration
    //    of the score in quarter note units.  Returns zero if no lines in the
    //    file, or -1 if there are lines, but no rhythmic analysis has been done.
    '''
    @property
    def scoreDuration(self) -> HumNum:
        if self.lineCount == 0:
            return 0
        return opFrac(
            # BUGFIX: Added last line duration
            self._lines[-1].durationFromStart + self._lines[-1].duration
        )

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::tpq -- "Ticks per Quarter-note".  Returns the minimal
    //    number of integral time units that divide a quarter note into equal
    //    subdivisions.  This value is needed to convert Humdrum data into
    //    MIDI file data, MuseData, and MusicXML data.  Also useful for timebase
    //    type of operations on the data and describing the durations in terms
    //    of integers rather than with fractions.  This function will also
    //    consider the implicit durations of non-rhythmic spine data.
    '''
    def tpq(self) -> int:
        if self._ticksPerQuarterNote > 0:
            return self._ticksPerQuarterNote

        durationSet: t.Set[Fraction] = self.getPositiveLineDurationFractions()
        denoms: t.List[int] = []
        for dur in durationSet:
            if dur.denominator > 1:
                denoms.append(dur.denominator)

        lcm: int = 1
        if len(denoms) > 0:
            lcm = Convert.getLcm(denoms)
        self._ticksPerQuarterNote = lcm
        return self._ticksPerQuarterNote

    def getPositiveLineDurationFractions(self) -> t.Set[Fraction]:
        output: t.Set[Fraction] = set()
        for line in self._lines:
            if line.duration > 0:
                output.add(Fraction(line.duration))
        return output

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::assignRhythmFromRecip --
    '''
    def assignRhythmFromRecip(self, spineStart: HumdrumToken) -> bool:
        currTok: t.Optional[HumdrumToken] = spineStart
        while currTok is not None:
            if not currTok.isData:
                currTok = currTok.nextToken0
                continue

            if currTok.isNull:
                # This should not occur in a well-formed **recip spine, but
                # treat as a zero duration.
                currTok = currTok.nextToken0
                continue

            currTok.ownerLine.duration = Convert.recipToDuration(currTok.text)
            currTok = currTok.nextToken0

        # now go back and set the absolute position from the start of the file.
        totalDurSoFar: HumNum = opFrac(0)
        for line in self._lines:
            line.durationFromStart = totalDurSoFar
            if line.duration is None or line.duration < 0:
                line.duration = opFrac(0)
            totalDurSoFar = opFrac(totalDurSoFar + line.duration)

        # Analyze durations to/from barlines:
        success = self.analyzeMeter()
        if not success:
            return False
        success = self.analyzeNonNullDataTokens()
        if not success:
            return False

        return True


    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::setLineRhythmAnalyzed --
    '''
    def setLinesRhythmAnalyzed(self) -> None:
        for line in self._lines:
            line.rhythmAnalyzed = True

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::analyzeRhythm -- Analyze the rhythmic structure
    //     of the data.  Returns false if there was a parse error.
    '''
    def analyzeRhythm(self) -> bool:
        # self.setLinesRhythmAnalyzed() # already happened in analyzeRhythmStructure
        if self.maxTrack == 0:
            return True


        trackStartTok: t.Optional[HumdrumToken] = self.trackStart(1)
        if trackStartTok is None:
            return False

        startLine: int = trackStartTok.lineIndex
        success: bool

        for i in range(1, self.maxTrack + 1):
            trackStartTok = self.trackStart(i)
            if trackStartTok is None:
                continue
            if not trackStartTok.hasRhythm:
                # Can't analyze rhythm of spines that do not have rhythm
                continue
            if trackStartTok.lineIndex == startLine:
                success = self.assignDurationsToTrack(trackStartTok, 0)
                if not success:
                    return False
            else:
                # Spine does not start at beginning of data, so
                # the starting position of the spine has to be
                # determined before continuing.  Search for a token
                # which is on a line with assigned duration, then work
                # outwards from that position.
                continue

        # Go back and analyze spines that do not start at the
        # beginning of the data stream.
        for i in range(1, self.maxTrack + 1):
            trackStartTok = self.trackStart(i)
            if trackStartTok is None:
                continue
            if not trackStartTok.hasRhythm:
                # Can't analyze rhythm of spines that do not have rhythm
                continue
            if trackStartTok.lineIndex > startLine:
                success = self.analyzeRhythmOfFloatingSpine(trackStartTok)
                if not success:
                    return False

        success = self.analyzeNullLineRhythms()
        if not success:
            return False
        self.fillInMissingStartTimes()
        self.assignLineDurations()
        success = self.analyzeMeter()
        if not success:
            return False
        success = self.analyzeNonNullDataTokens()
        return success

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::analyzeMeter -- Store the times from the last barline
    //     to the current line, as well as the time to the next barline.
    //     the sum of these two will be the duration of the barline, except
    //     for barlines, where the getDurationToBarline() will store the
    //     duration of the measure staring at that barline.  To get the
    //     beat, you will have to figure out the current time signature.
    '''
    def analyzeMeter(self) -> bool:
        self._barlines = []

        durationSum: HumNum = opFrac(0)
        foundFirstBarline: bool = False

        for line in self._lines:
            line.durationFromBarline = durationSum
            durationSum = opFrac(durationSum + line.duration)
            if line.isBarline:
                foundFirstBarline = True
                self._barlines.append(line)
                durationSum = opFrac(0)
            elif line.isData and not foundFirstBarline:
                # pickup measure, so set the first barline to the start of the file
                self._barlines.append(self._lines[0])
                foundFirstBarline = True

        durationSum = opFrac(0)
        for line in reversed(self._lines):
            durationSum = opFrac(durationSum + line.duration)
            line.durationToBarline = durationSum
            if line.isBarline:
                durationSum = opFrac(0)

        return True

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::analyzeTokenDurations -- Calculate the duration of
    //   all tokens in spines which posses duration in a file.
    '''
    def analyzeTokenDurations(self) -> bool:
        for line in self._lines:
            success = line.analyzeTokenDurations()
            if not success:
                return self.isValid
        return self.isValid

    '''
    ///////////////////////////////
    //
    // HumdrumFileStructure::analyzeGlobalParameters -- only allowing layout
    //    parameters at the moment.  Global parameters affect the next
    //    line which is either a barline, dataline or an interpretation
    //    other than a spine manipulator.  Null lines are also not
    //    considered.
    '''
    def analyzeGlobalParameters(self) -> bool:
        globalParamLines: t.List[HumdrumLine] = []

        for line in self._lines:
            if line.isGlobalComment and line.text.startswith('!!LO:'):
                line.storeGlobalLinkedParameters()  # stores those params in zeroth token of line
                globalParamLines.append(line)
                continue

            if not line.hasSpines:
                continue
            if line.isAllNull:
                continue
            if line.isLocalComment:
                continue
            if not globalParamLines:
                continue

            # Filter manipulators or not?  At the moment allow
            # global parameters to pass through manipulators.
            # if (m_lines[i]->isManipulator()) {
            # 	continue;
            # }

            for token in line.tokens():
                for gLine in globalParamLines:
                    # this token is affected by this global param
                    token.addLinkedParameterSet(gLine[0])

            globalParamLines = []

        return self.isValid

    '''
    ///////////////////////////////
    //
    // HumdrumFileStructure::analyzeLocalParameters -- Parses any
    //    local comments before a non-null token.
    '''
    def analyzeLocalParameters(self) -> bool:
        for i in range(0, self.strandCount()):
            self.processLocalParametersForStrand(i)

        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::analyzeDurationsOfNonRhythmicSpines -- Calculate the
    //    duration of non-null data token in non-rhythmic spines.
    '''
    def analyzeDurationsOfNonRhythmicSpines(self) -> bool:
        for track in range(1, self.maxTrack + 1):  # tracks are 1-based
            for endIdx in range(0, self.trackEndCount(track)):
                trackEnd: t.Optional[HumdrumToken] = self.trackEnd(track, endIdx)
                if trackEnd is None or trackEnd.hasRhythm:
                    continue
                success = self.assignDurationsToNonRhythmicTrack(trackEnd, trackEnd)
                if not success:
                    return self.isValid

        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::assignDurationsToTrack -- Assign duration from starts
    //    for each rhythmic spine in the file.  Analysis is done recursively, one
    //    sub-spine at a time.  Duplicate analyses are prevented by the state
    //    variable in the HumdrumToken (currently called rhycheck because it is only
    //    used in this function).  After the durationFromStarts have been assigned
    //    for the rhythmic analysis of non-data tokens and non-rhythmic spines is
    //    done elsewhere.
    '''
    def assignDurationsToTrack(self, startToken: HumdrumToken, startDur: HumNumIn) -> bool:
        sDur: HumNum = opFrac(startDur)
        if not startToken.hasRhythm:
            return self.isValid

        success: bool = self.prepareDurations(startToken, startToken.rhythmAnalysisState, sDur)
        if not success:
            return self.isValid
        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::prepareDurations -- Helper function for
    //     HumdrumFileStructure::assignDurationsToTrack() which does all of the
    //     work for assigning durationFromStart values.
    '''
    def prepareDurations(self, token: HumdrumToken, state: int, startDur: HumNumIn) -> bool:
        if state != token.rhythmAnalysisState:
            return self.isValid

        token.incrementRhythmAnalysisState()

        durSum: HumNum = opFrac(startDur)

        success = self.setLineDurationFromStart(token, durSum)
        if not success:
            return self.isValid

        if token.duration > 0:
            durSum = opFrac(durSum + token.duration)

        reservoir: t.List[HumdrumToken] = []
        startDurs: t.List[HumNum] = []

        # Assign line durationFromStarts for primary track first
        tcount: int = token.nextTokenCount
        while tcount > 0:
            for i, tok in enumerate(token.nextTokens):
                if i == 0:
                    # we'll deal with token 0 ourselves below
                    continue
                reservoir.append(tok)
                startDurs.append(durSum)

            if t.TYPE_CHECKING:
                # we know here that token.nextTokenCount > 0, so
                # token.nextToken0 is not None
                assert isinstance(token.nextToken0, HumdrumToken)

            token = token.nextToken0
            if state != token.rhythmAnalysisState:
                break

            token.incrementRhythmAnalysisState()
            success = self.setLineDurationFromStart(token, durSum)
            if not success:
                return self.isValid

            if token.duration > 0:
                durSum = opFrac(durSum + token.duration)

            tcount = token.nextTokenCount

        if tcount == 0 and token.isTerminateInterpretation:
            success = self.setLineDurationFromStart(token, durSum)
            if not success:
                return self.isValid

        # Process secondary tracks next:
        newState: int = state
        for i in reversed(range(0, len(reservoir))):
            self.prepareDurations(reservoir[i], newState, startDurs[i])

        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::setLineDurationFromStart -- Set the duration of
    //      a line based on the analysis of tokens in the spine.
    '''
    def setLineDurationFromStart(self, token: HumdrumToken, durSum: HumNumIn) -> bool:
        dSum: HumNum = opFrac(durSum)
        if not token.isTerminateInterpretation and token.duration < 0:
            # undefined rhythm, so don't assign line duration information
            return self.isValid

        line: HumdrumLine = token.ownerLine
        if line.durationFromStart == -1:
            line.durationFromStart = dSum
        elif line.durationFromStart != dSum:
            if not token.isTerminateInterpretation:
                return self.setParseError(
                    f'''Error: Inconsistent rhythm analysis occurring near line {token.lineNumber}
Expected durationFromStart to be: {dSum} but found it to be {line.durationFromStart}
Line: {line.text}'''
                )
            line.durationFromStart = max(line.durationFromStart, dSum)

        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::analyzeRhythmOfFloatingSpine --  This analysis
    //    function is used to analyze the rhythm of spines which do not start at
    //    the beginning of the data.  The function searches for the first line
    //    which has an assigned durationFromStart value, and then uses that
    //    as the basis for assigning the initial durationFromStart position
    //    for the spine.
    '''
    def analyzeRhythmOfFloatingSpine(self, spineStart: HumdrumToken) -> bool:
        durSum: HumNum = opFrac(0)
        foundDur: HumNum = opFrac(0)

        # Find a known durationFromStart for a line in the Humdrum file, then
        # use that to calculate the starting duration of the floating spine.
        if spineStart.durationFromStart >= 0:
            foundDur = spineStart.durationFromStart
        else:
            token: t.Optional[HumdrumToken] = spineStart
            while token is not None:
                if token.durationFromStart >= 0:
                    foundDur = token.durationFromStart
                    break
                if token.duration > 0:
                    durSum = opFrac(durSum + token.duration)
                token = token.nextToken0

        if foundDur == 0:
            return self.setParseError('Error: cannot link floating spine to score.')

        success: bool = self.assignDurationsToTrack(spineStart, foundDur - durSum)
        if not success:
            return self.isValid

        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::analyzeNullLineRhythms -- When a series of null-token
    //    data line occur between two data lines possessing a start duration,
    //    then split the duration between those two lines amongst the null-token
    //    lines.  For example if a data line starts at time 15, and there is one
    //    null-token line before another data line at time 16, then the null-token
    //    line will be assigned to the position 15.5 in the score.
    '''
    def analyzeNullLineRhythms(self) -> bool:
        nullLines: t.List[HumdrumLine] = []
        previousLine: t.Optional[HumdrumLine] = None
        nextLine: t.Optional[HumdrumLine] = None

        for line in self._lines:
            if t.TYPE_CHECKING:
                # we know that every element of self._lines is not None
                assert isinstance(line, HumdrumLine)

            if not line.hasSpines:
                continue

            if line.isBarline:
                # We start from scratch in each measure.  This is because, if there is a null data
                # line as the first line in a measure, we don't want it to start halfway from last
                # real note in previous measure to first real note in this measure.  Any such
                # unprocessed null lines will end up inheriting their start time from the first
                # non-null note in this measure, during fillInMissingStartTimes' first loop
                # (backwards) over the lines.
                previousLine = None
                nullLines = []

            if line.isAllRhythmicNull:
                if line.isData:
                    nullLines.append(line)
                continue

            if line.durationFromStart < 0:
                if line.isData:
                    return self.setParseError(
                        'Error: found an unexpectedly missing durationFromStart on '
                        + f'data line {line.durationFromStart}\n'
                        + f'Line: {line.text}'
                    )
                continue

            nextLine = line
            if previousLine is None:
                previousLine = nextLine
                nullLines = []
                continue

            if t.TYPE_CHECKING:
                # we know previousLine is not None if we get here
                assert isinstance(previousLine, HumdrumLine)

            startDur: HumNum = previousLine.durationFromStart
            endDur: HumNum = nextLine.durationFromStart
            gapDur: HumNum = opFrac(endDur - startDur)
            nullDur: HumNum = opFrac(gapDur / (len(nullLines) + 1))
            for j, nullLine in enumerate(nullLines):
                nullLine.durationFromStart = opFrac(startDur + opFrac(nullDur * (j + 1)))

            previousLine = nextLine
            nullLines = []

        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::fillInNegativeStartTimes -- Negative line durations
    //    after the initial rhythmAnalysis mean that the lines are not data line.
    //    Duplicate the duration of the next non-negative duration for all negative
    //    durations.
        "negative" is now "None" -- gregc
    '''
    def fillInMissingStartTimes(self) -> None:
        lastDur: HumNum = opFrac(-1)

        for line in reversed(self._lines):
            if line.durationFromStart < 0 and lastDur >= 0:
                line.durationFromStart = lastDur
            if line.durationFromStart >= 0:
                lastDur = line.durationFromStart

        # fill in start times for ending comments
        for line in self._lines:
            if line.durationFromStart >= 0:
                lastDur = line.durationFromStart
            else:
                line.durationFromStart = lastDur

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::assignLineDurations --  Calculate the duration of lines
    //   based on the durationFromStart of the current line and the next line.
    '''
    def assignLineDurations(self) -> None:
        for i in range(0, len(self._lines)):
            if i == len(self._lines) - 1:
                self._lines[i].duration = opFrac(0)
            else:
                startDur: HumNum = self._lines[i].durationFromStart
                endDur: HumNum = self._lines[i + 1].durationFromStart
                self._lines[i].duration = opFrac(endDur - startDur)

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::assignDurationsToNonRhythmicTrack --  After the basic
    //   rhythmAnalysis has been done, go back and assign durations to non-rhythmic
    //   spine tokens based on the lineFromStart values of the lines that they
    //   occur on as well as the distance in the file to the next non-null token for
    //   that spine.
    '''
    def assignDurationsToNonRhythmicTrack(
            self,
            endToken: HumdrumToken,
            current: HumdrumToken
    ) -> bool:
        spineInfo: str = endToken.spineInfo
        token: t.Optional[HumdrumToken] = endToken

        while token is not None:
            if token.spineInfo != spineInfo:
                if 'b' in token.spineInfo:
                    break
                if 'b' in spineInfo:
                    break

            tcount: int = token.previousTokenCount
            if tcount == 0:
                break

            if tcount > 1:
                for i in range(1, tcount):
                    ptok: t.Optional[HumdrumToken] = token.previousToken(i)
                    if t.TYPE_CHECKING:
                        # we know that ptok is not None
                        assert isinstance(ptok, HumdrumToken)

                    success = self.assignDurationsToNonRhythmicTrack(ptok, current)
                    if not success:
                        return self.isValid

            if token.isNonNullData:
                token.duration = opFrac(current.durationFromStart - token.durationFromStart)
                current = token

            token = token.previousToken0

        return self.isValid

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::processLocalParametersForStrand --
    '''
    def processLocalParametersForStrand(self, index: int) -> None:
        sStart: t.Optional[HumdrumToken] = self.strandStart1d(index)
        sEnd: t.Optional[HumdrumToken] = self.strandEnd1d(index)
        tok: t.Optional[HumdrumToken] = sEnd  # start at the end and work backward
        dtok: t.Optional[HumdrumToken] = None

        while tok is not None:
            if tok.isData:
                dtok = tok
            elif tok.isBarline:
                # layout parameters allowed for barlines
                dtok = tok
            elif tok.isInterpretation and tok.text != '*' and not tok.isManipulator:
                # layout parameters allowed for non-null, non-manip interpretations
                dtok = tok
            elif tok.isLocalComment and tok.text.startswith('!LO:'):
                tok.storeParameterSet()
                if dtok is not None:
                    dtok.addLinkedParameterSet(tok)

            if tok == sStart:
                break

            tok = tok.previousToken0

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::analyzeStrands -- Analyze spine strands.
    '''
    def analyzeStrands(self) -> bool:
        self._analyses.strandsAnalyzed = True

        self._strand1d = []
        self._strand2d = []

        for i in range(0, self.spineCount):
            tok: t.Optional[HumdrumToken] = self.spineStartList[i]
            self._strand2d.append([])
            self.analyzeSpineStrands(self._strand2d[-1], tok)

        for i in range(0, len(self._strand2d)):
            self._strand2d[i].sort(key=attrgetter('firstLineIndex', 'firstFieldIndex'))
            for j in range(0, len(self._strand2d[i])):
                self._strand1d.append(self._strand2d[i][j])

        self.assignStrandsToTokens()
        self.resolveNullTokens()
        self.analyzeLocalParameters()
#        self.analyzeStrophes()

        return self.isValid

    '''
    ///////////////////////////////
    //
    // HumdrumFileStructure::resolveNullTokens --
    '''
    def resolveNullTokens(self) -> None:
        if self._analyses.nullsAnalyzed:
            return

        self._analyses.nullsAnalyzed = True
        if not self.areStrandsAnalyzed:
            self.analyzeStrands()

        data: t.Optional[HumdrumToken] = None
        strandPair: TokenPair
        for strandPair in self._strand1d:
            token: t.Optional[HumdrumToken] = strandPair.first
            strandEnd: t.Optional[HumdrumToken] = strandPair.last
            if t.TYPE_CHECKING:
                # after analyzeStrands, no pair in self._strand1d will have Nones in it.
                assert token is not None
                assert strandEnd is not None

            while token != strandEnd:
                if token is None:
                    # we never reached strandEnd, but we're done
                    raise HumdrumInternalError(f'never found strandEnd ({strandEnd})')

                if not token.isData:
                    token = token.nextToken0
                    continue

                if data is None:
                    data = token
                    token.nullResolution = data
                    token = token.nextToken0
                    continue

                if token.isNull:
                    token.nullResolution = data
                else:
                    data = token

                token = token.nextToken0

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::assignStrandsToTokens -- Store the 1D strand
    //    index number for each token in the file.  Global tokens will have
    //    strand index set to -1.
    '''
    def assignStrandsToTokens(self) -> None:
        strandPair: TokenPair
        for i, strandPair in enumerate(self._strand1d):
            tok: t.Optional[HumdrumToken] = strandPair.first
            while tok is not None:
                tok.strandIndex = i
                tok = tok.nextToken0

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::analyzeSpineStrands -- Fill in the list of
    //   strands in a single spine.
    '''
    def analyzeSpineStrands(
            self,
            ends: t.List[TokenPair],
            startToken: t.Optional[HumdrumToken]
    ) -> None:
        newStrand: TokenPair = TokenPair(startToken, None)
        ends.append(newStrand)

        tok: t.Optional[HumdrumToken] = startToken
        while tok is not None:
            if tok.isMergeInterpretation and tok.subTrack > 1:
                # check to the left: if the left primary/sub spine also has
                # a *v, then this is the end of this strand; otherwise, the
                # strand continues.
                if tok.previousFieldToken is not None:
                    if tok.previousFieldToken.isMergeInterpretation:
                        newStrand.last = tok
                        return

                tok = tok.nextToken0
                continue

            if tok.isTerminateInterpretation:
                newStrand.last = tok
                return

            if tok.nextTokenCount > 1:
                # should only be 2, but allow for generalizing in the future.
                for j in range(1, tok.nextTokenCount):
                    self.analyzeSpineStrands(ends, tok.nextToken(j))

            tok = tok.nextToken0

        print('Should not get here in analyzeSpineStrands()', file=sys.stderr)

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::getStrandCount --
    '''
    def strandCount(self, spineIndex: t.Optional[int] = None) -> int:
        if not self.areStrandsAnalyzed:
            self.analyzeStrands()

        if spineIndex is None:
            # caller is asking for strand count of entire file
            return len(self._strand1d)

        # caller is asking for strand count of a particular spine
        if spineIndex < 0 or spineIndex >= len(self._strand2d):
            return 0

        return len(self._strand2d[spineIndex])

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::getStrandStart -- Return the first token
    //    in the a strand.
    '''
    def strandStart2d(self, spineIndex: int, strandIndex: int) -> t.Optional[HumdrumToken]:
        if not self.areStrandsAnalyzed:
            self.analyzeStrands()

        return self._strand2d[spineIndex][strandIndex].first

    def strandStart1d(self, strandIndex: int) -> t.Optional[HumdrumToken]:
        if not self.areStrandsAnalyzed:
            self.analyzeStrands()

        return self._strand1d[strandIndex].first

    def strandEnd2d(self, spineIndex: int, strandIndex: int) -> t.Optional[HumdrumToken]:
        if not self.areStrandsAnalyzed:
            self.analyzeStrands()

        return self._strand2d[spineIndex][strandIndex].last

    def strandEnd1d(self, strandIndex: int) -> t.Optional[HumdrumToken]:
        if not self.areStrandsAnalyzed:
            self.analyzeStrands()

        return self._strand1d[strandIndex].last

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::hasFilters -- Returns true if has any
    //    reference records starting with "!!!filter:" or "!!!!filter:".
    '''
    def hasFilters(self) -> bool:
        refs: t.List[HumdrumLine] = self.globalReferenceRecords()
        for ref in refs:
            if ref.globalReferenceKey == 'filter':
                return True
        return False

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::hasGlobalFilters -- Returns true if has any
    //    reference records starting with "!!!filter:".
    '''
    def hasGlobalFilters(self) -> bool:
        for line in self._lines:
            if not line.isComment:
                continue

            token0: t.Optional[HumdrumToken] = line[0]
            if token0 is not None and token0.text.startswith('!!!filter'):
                return True

        return False

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::hasUniversalFilters -- Returns true if has any
    //    reference records starting with "!!!!filter:".
    '''
    def hasUniversalFilters(self) -> bool:
        refs: t.List[HumdrumLine] = self.universalReferenceRecords()
        for ref in refs:
            if ref.universalReferenceKey == 'filter':
                return True
        return False

    '''
    //////////////////////////////
    //
    // HumdrumFileStructure::analyzeSignifiers --
        Analyzes all the RDF lines
    '''
    def analyzeSignifiers(self) -> None:
        for line in self._lines:
            if line.isSignifier:
                self._signifiers.addSignifier(line.text)
        self._signifiers.generateKnownInfo()
