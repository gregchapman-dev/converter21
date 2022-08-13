# ------------------------------------------------------------------------------
# Name:          HumdrumTools.py
# Purpose:       HumdrumTools contains various tools that modify Humdrum data.
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

from converter21.humdrum import HumdrumFile
from converter21.humdrum import HumdrumLine
from converter21.humdrum import HumdrumToken
from converter21.humdrum import HumNum
from converter21.humdrum import Convert

class ToolTremolo:
    # Tremolo expansion tool.
    def __init__(self, infile: HumdrumFile) -> None:
        self.infile: HumdrumFile = infile
        self.markupTokens: t.List[HumdrumToken] = []
        self.firstTremoloLinesInTrack: t.List[t.List[t.Optional[HumdrumLine]]] = []
        self.lastTremoloLinesInTrack: t.List[t.List[t.Optional[HumdrumLine]]] = []

    '''
    //////////////////////////////
    //
    // Tool_tremolo::processFile --
    '''
    def processFile(self) -> None:
        if self.infileNeedsToBeParsed():
            self.infile.analyzeBase()
            self.infile.analyzeStructure()
            if not self.infile.isValid:
                return

        for _ in range(0, self.infile.maxTrack + 1):
            self.firstTremoloLinesInTrack.append([])
            self.lastTremoloLinesInTrack.append([])

        for line in reversed(list(self.infile.lines())):
            if not line.isData:
                continue
            if line.duration == 0:
                # don't deal with grace notes
                continue

            for token in line.tokens():
                if not token.isKern:
                    continue
                if token.isNull:
                    continue

                m = re.search(r'@(\d+)@', token.text)
                if not m:
                    continue

                self.markupTokens.insert(0, token)  # markupTokens is in forward order

                value: int = int(m.group(1))
                duration: HumNum = Convert.recipToDuration(token.text)
                four: HumNum = opFrac(4)
                count: HumNum = opFrac((duration * value) / four)
                increment: HumNum = opFrac(four / value)

                if '@@' in token.text:
                    count = opFrac(count * 2)

                countFraction: Fraction = Fraction(count)
                if countFraction.denominator != 1:
                    print(f'Error: tremolo time value cannot be used: {value}', file=sys.stderr)
                    continue

                kcount: int = countFraction.numerator
                startTime: HumNum = token.durationFromStart
                for k in range(1, kcount):
                    timestamp: HumNum = opFrac(startTime + (increment * opFrac(k)))
                    self.infile.insertNullDataLine(timestamp)

        self.expandTremolos()
        self.addTremoloInterpretations()

        # is this necessary?  We do createLineFromTokens() whenever we modify a token already.
#         if self.modified:
#             self.infile.createLinesFromTokens()

    def infileNeedsToBeParsed(self) -> bool:
        if not self.infile.isStructureAnalyzed:
            return True
        if not self.infile.isRhythmAnalyzed:
            return True

        return False


    def notesFoundInTrackBetweenLineIndices(self, track: int, startIdx: int, endIdx: int) -> bool:
        # Check every line between startIdx and endIdx, NOT inclusive at either end
        for i in range(startIdx + 1, endIdx):
            line: t.Optional[HumdrumLine] = self.infile[i]
            if line is None:
                continue
            for token in line.tokens():
                if token.track == track:
                    if token.isNote:
                        return True
        return False

    '''
    //////////////////////////////
    //
    // Tool_tremolo::addTremoloInterpretations --
    '''
    def addTremoloInterpretations(self) -> None:
        # These starts/stops are exactly what music21 has, which is per beam-group.
        # We would like to avoid a stop immediately followed by a start (as redundant).
        # Or even a stop and then a start with no actual notes between them.
        # So we first "optimize" this.
        for track, (firstLines, lastLines) in enumerate(zip(
                self.firstTremoloLinesInTrack,
                self.lastTremoloLinesInTrack)):
            lastLineRemovalIndices: t.List[int] = []
            firstLineRemovalIndices: t.List[int] = []
            currLastLineIndex: t.Optional[int] = None
            prevLastLineIndex: t.Optional[int] = None
            currFirstLineIndex: t.Optional[int] = None
            for idx, (firstLine, lastLine) in enumerate(zip(firstLines, lastLines)):
                if t.TYPE_CHECKING:
                    # self.{first,last}TremoloLinesInTrack should be filled in by now
                    assert firstLine is not None
                    assert lastLine is not None

                prevLastLineIndex = currLastLineIndex
                currFirstLineIndex = firstLine.lineIndex
                currLastLineIndex = lastLine.lineIndex

                if prevLastLineIndex is not None:
                    if not self.notesFoundInTrackBetweenLineIndices(
                            track, prevLastLineIndex, currFirstLineIndex):
                        lastLineRemovalIndices.append(idx - 1)
                        firstLineRemovalIndices.append(idx)

            for lineIndexToRemove in reversed(lastLineRemovalIndices):
                lastLines.pop(lineIndexToRemove)
            for lineIndexToRemove in reversed(firstLineRemovalIndices):
                firstLines.pop(lineIndexToRemove)


        line: HumdrumLine

        # Insert starting *tremolo(s)
        for track, firstLines in enumerate(self.firstTremoloLinesInTrack):
            if not firstLines:
                # no first times in this track
                continue

            for firstLine in firstLines:
                if firstLine is None:
                    continue

                line = self.infile.insertNullInterpretationLineAt(
                    firstLine.lineIndex
                )
                if line is None:
                    continue

                for token in line.tokens():
                    if token.subTrack > 1:
                        # Currently *tremolo affects all subTracks, but this
                        # will probably change in the future.
                        continue
                    if token.track == track:
                        token.text = '*tremolo'
                        line.createLineFromTokens()

        # Insert ending *Xtremolo(s)
        for track, lastLines in enumerate(self.lastTremoloLinesInTrack):
            if not lastLines:
                continue

            for lastLine in lastLines:
                if lastLine is None:
                    continue

                line = self.infile.insertNullInterpretationLineAt(
                    lastLine.lineIndex + 1
                )
                if line is None:
                    continue

                for token in line.tokens():
                    if token.subTrack is not None and token.subTrack > 1:
                        # Currently *tremolo affects all subTracks, but this
                        # will probably change in the future.
                        continue
                    if token.track == track:
                        token.text = '*Xtremolo'
                        line.createLineFromTokens()

    '''
    //////////////////////////////
    //
    // Tool_tremolo::expandTremolos --
    '''
    def expandTremolos(self) -> None:
        for token in self.markupTokens:
            # if we have already replaced the '@' or '@@' token with an expansion note,
            # we just skip it here.
            if '@' not in token.text:
                continue

            if '@@' in token.text:
                self.expandFingerTremolo(token)
            else:
                self.expandTremolo(token)

    '''
    //////////////////////////////
    //
    // Tool_tremolo::expandTremolo --
    '''
    def expandTremolo(self, token: HumdrumToken) -> None:
        addBeam: bool = False
        tnotes: int = -1

        m = re.search(r'@(\d+)@', token.text)
        if not m:
            return

        value: int = int(m.group(1))
        valueHumNum: HumNum = opFrac(value)
        valueFraction: Fraction = Fraction(value)

        duration: HumNum = Convert.recipToDuration(token.text)

        four: HumNum = opFrac(4)
        count: HumNum = opFrac(duration * valueHumNum / four)
        countFraction: Fraction = Fraction(count)
        if countFraction.denominator != 1:
            print(f'Error: non-integer number of tremolo notes: {token}', file=sys.stderr)
            return
        if value < 8:
            print(f'Error: tremolo notes can only be eighth-notes or shorter: {token}',
                    file=sys.stderr)
            return
        if duration > 0.5:
            # needs to be less than one for tuplet quarter note tremolos
            addBeam = True

        # There are cases where duration < 1 need added beams
        # when the note is not already in a beam.  Such as
        # a plain 8th note with a slash.  This needs to be
        # converted into two 16th notes with a beam so that
        # *tremolo can reduce it back into a tremolo, since
        # it will only reduce beam groups.

        repeat: HumNum = opFrac((duration * valueHumNum) / four)
        increment: HumNum = opFrac(four / valueHumNum)
        repeatFraction: Fraction = Fraction(repeat)
        if repeatFraction.denominator != 1:
            print(f'Error: tremolo repetition count must be an integer: {token}',
                    file=sys.stderr)
            return
        tnotes = repeatFraction.numerator

        self.storeFirstTremoloNoteInfo(token)

        beams: int = int(math.log(float(value), 2)) - 2
        markup: str = f'@{valueFraction.numerator}@'
        base: str = re.sub(markup, '', token.text)

        # complicated beamings are not allowed yet (no internal L/J markers in tremolo beam)
        hasBeamStart: bool = 'L' in base
        hasBeamStop: bool = 'J' in base

        if addBeam:
            hasBeamStart = True
            hasBeamStop = True

        # Currently not allowed to add tremolo to beamed notes, so remove all beaming:
        base = re.sub(r'[LJKk]+', '', base)
        startBeam: str = 'L' * beams
        endBeam: str = 'J' * beams

        # Set the rhythm of the tremolo notes.
        # Augmentation dot is expected adjacent to regular rhythm value.
        # Maybe allow anywhere?
        base = re.sub(r'\d+%?\d*\.*', str(valueFraction.numerator), base)
        initial: str = base
        if hasBeamStart:
            initial += startBeam
        terminal: str = base
        if hasBeamStop:
            terminal += endBeam

        # remove tie continue from start of tremolo (leave tie start/end in place)
        initial = re.sub(r'_+[<>]?', '', initial)
        # remove tie information from middle of tremolo
        base = re.sub(r'[\[_\]]+[<>]?', '', base)
        # remove tie information from end of tremolo
        terminal = re.sub(r'[\[_\]]+[<>]?', '', terminal)

        # remove slur start from end of tremolo:
        terminal = re.sub(r'[(]+[<>]', '', terminal)

        token.text = initial
        token.ownerLine.createLineFromTokens()

        # Now fill in the rest of the tremolos.
        startTime: HumNum = token.durationFromStart
        timestamp: HumNum = opFrac(startTime + increment)
        currTok: t.Optional[HumdrumToken] = token.nextToken(0)
        counter: int = 1

        while currTok is not None:
            if not currTok.isData:
                currTok = currTok.nextToken(0)
                continue

            duration = currTok.ownerLine.duration
            if duration == 0:
                # grace note line, so skip
                currTok = currTok.nextToken(0)
                continue

            cstamp: HumNum = currTok.durationFromStart
            if cstamp < timestamp:
                currTok = currTok.nextToken(0)
                continue

            if cstamp > timestamp:
                print('\tWarning: terminating tremolo insertion early', file=sys.stderr)
                print(f'\tCSTAMP : {cstamp} TSTAMP : {timestamp}', file=sys.stderr)
                break

            counter += 1
            if counter == tnotes:
                currTok.text = terminal
                self.storeLastTremoloNoteInfo(currTok)
            else:
                currTok.text = base

            currTok.ownerLine.createLineFromTokens()
            if counter >= tnotes:
                # done with inserting of tremolo notes.
                break

            timestamp = opFrac(timestamp + increment)
            currTok = currTok.nextToken(0)

    '''
    //////////////////////////////
    //
    // Tool_tremolo::getNextNote --
    '''
    def getNextNote(self, token: HumdrumToken) -> t.Optional[HumdrumToken]:
        output: t.Optional[HumdrumToken] = None
        current: t.Optional[HumdrumToken] = token.nextToken0

        while current is not None:
            if not current.isData:
                current = current.nextToken0
                continue
            if current.duration == 0:
                # ignore grace notes
                current = current.nextToken0
                continue
            if current.isNull or current.isRest:
                current = current.nextToken0
                continue

            output = current
            break

        return output

    '''
    //////////////////////////////
    //
    // Tool_tremolo::expandFingerTremolos --
    '''
    def expandFingerTremolo(self, token1: HumdrumToken) -> None:
        token2: t.Optional[HumdrumToken] = self.getNextNote(token1)
        if token2 is None:
            return

        m = re.search(r'@@(\d+)@@', token1.text)
        if m is None:
            return

        value: int = int(m.group(1))
        valueHumNum: HumNum = opFrac(value)
        if not Convert.isPowerOfTwo(valueHumNum):
            print(f'Error: not a power of two: {token1}', file=sys.stderr)
            return
        if value < 8:
            print(f'Error: tremolo can only be eighth-notes or shorter: {token1}', file=sys.stderr)
            return

        duration: HumNum = Convert.recipToDuration(token1.text)
        four: HumNum = opFrac(4)
        count: HumNum = opFrac((duration * valueHumNum) / four)
        countFraction: Fraction = Fraction(count)

        if countFraction.denominator != 1:
            print(f'Error: tremolo repetition count must be an integer: {token1}', file=sys.stderr)
            return
        increment: HumNum = opFrac(four / valueHumNum)

        tnotes: int = countFraction.numerator * 2

        self.storeFirstTremoloNoteInfo(token1)

        beams: int = int(math.log(float(value), 2)) - 2
        markup: str = f'@@{value}@@'
        base1: str = token1.text
        base1 = re.sub(markup, '', base1)
        # Currently not allowed to add tremolo to beamed notes, so remove all beaming:
        base1 = re.sub(r'[LJKk]+', '', base1)
        startBeam: str = 'L' * beams
        endBeam: str = 'J' * beams

        # Set the rhythm of the tremolo notes.
        # Augmentation dot is expected adjacent to regular rhythm value.
        # Maybe allow anywhere?
        base1 = re.sub(r'\d+%?\d*\.*', str(value), base1)
        initial: str = base1 + startBeam
        # remove slur end from start of tremolo
        initial = re.sub(r'[)]+[<>]?', '', initial)
        # remove tie continue from start of tremolo (leave tie start/end in place)
        initial = re.sub(r'_+[<>]?', '', initial)

        # remove slur information from middle of tremolo
        base1 = re.sub(r'[()]+[<>]?', '', base1)
        # remove tie information from middle of tremolo
        base1 = re.sub(r'[\[_\]]+[<>]?', '', base1)

        token1.text = initial
        token1.ownerLine.createLineFromTokens()

        base2: str = token2.text
        base2 = re.sub(markup, '', base2)
        base2 = re.sub(r'[LJKk]+', '', base2)
        base2 = re.sub(r'\d+%?\d*\.*', str(value), base2)

        terminal: str = base2 + endBeam
        # remove slur start information from end of tremolo:
        terminal = re.sub(r'[(]+[<>]?', '', terminal)
        # remove tie information from end of tremolo
        terminal = re.sub(r'[\[_\]]+[<>]?', '', terminal)

        state: bool = False

        # Now fill in the rest of the tremolos.
        startTime: HumNum = token1.durationFromStart
        timestamp: HumNum = opFrac(startTime + increment)
        currTok: t.Optional[HumdrumToken] = token1.nextToken(0)
        counter: int = 1
        while currTok is not None:
            if not currTok.isData:
                currTok = currTok.nextToken(0)
                continue

            # We also skip zero-duration lines (grace notes)
            if currTok.ownerLine.duration == 0:
                currTok = currTok.nextToken(0)
                continue

            cstamp: HumNum = currTok.durationFromStart
            if cstamp < timestamp:
                currTok = currTok.nextToken(0)
                continue

            if cstamp > timestamp:
                print('\tWarning: terminating tremolo insertion early', file=sys.stderr)
                print(f'\tCSTAMP : {cstamp} TSTAMP : {timestamp}', file=sys.stderr)
                break

            counter += 1
            if counter == tnotes:
                currTok.text = terminal
                self.storeLastTremoloNoteInfo(currTok)
            else:
                if state:
                    currTok.text = base1
                else:
                    currTok.text = base2
                state = not state

            currTok.ownerLine.createLineFromTokens()

            if counter >= tnotes:
                # done with inserting of tremolo notes
                break

            timestamp = opFrac(timestamp + increment)
            currTok = currTok.nextToken(0)

    '''
    //////////////////////////////
    //
    // Tool_tremolo::storeFirstTremoloNote --
    '''
    def storeFirstTremoloNoteInfo(self, token: HumdrumToken) -> None:
        if token is None:
            return

        track: t.Optional[int] = token.track
        if track is None:
            print(f'Track is not set for token: {token}', file=sys.stderr)
            return

        self.firstTremoloLinesInTrack[track].append(token.ownerLine)

    '''
    //////////////////////////////
    //
    // Tool_tremolo::storeLastTremoloNote --
    '''
    def storeLastTremoloNoteInfo(self, token: HumdrumToken) -> None:
        if token is None:
            return

        track: t.Optional[int] = token.track
        if track is None:
            print(f'Track is not set for token: {token}', file=sys.stderr)
            return

        self.lastTremoloLinesInTrack[track].append(token.ownerLine)
