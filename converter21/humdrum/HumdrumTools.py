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
from typing import List, Optional

from converter21.humdrum import HumdrumFile
from converter21.humdrum import HumdrumLine
from converter21.humdrum import HumdrumToken
from converter21.humdrum import HumNum
from converter21.humdrum import Convert

class ToolTremolo:
    # Tremolo expansion tool.
    def __init__(self, infile: HumdrumFile):
        self.infile: HumdrumFile = infile
        self.markupTokens: List[HumdrumToken] = []
        self.firstTremoloLinesInTrack: List[List[Optional[HumNum]]] = []
        self.lastTremoloLinesInTrack: List[List[Optional[HumdrumLine]]] = []

    '''
    //////////////////////////////
    //
    // Tool_tremolo::processFile --
    '''
    def processFile(self):
        if self.infileNeedsToBeParsed():
            self.infile.analyzeBase()
            self.infile.analyzeStructure()
            if not self.infile.isValid:
                return

        for _ in range(0, self.infile.maxTrack+1):
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

                self.markupTokens.insert(0, token) # markupTokens is in forward order

                value: int = int(m.group(1))
                duration: HumNum = Convert.recipToDuration(token.text)
                count: HumNum = duration
                count *= value
                count /= 4
                increment: HumNum = HumNum(4)
                increment /= value

                if '@@' in token.text:
                    count *= 2

                if count.denominator != 1:
                    print(f'Error: tremolo time value cannot be used: {value}', file=sys.stderr)
                    continue

                kcount: int = count.numerator
                startTime: HumNum = token.durationFromStart
                for k in range(1, kcount):
                    timestamp: HumNum = startTime + (increment * k)
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
        for i in range(startIdx+1, endIdx):
            line: HumdrumLine = self.infile[i]
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
    def addTremoloInterpretations(self):
        # These starts/stops are exactly what music21 has, which is per beam-group.
        # We would like to avoid a stop immediately followed by a start (as redundant).
        # Or even a stop and then a start with no actual notes between them.
        # So we first "optimize" this.
        for track, (firstLines, lastLines) in enumerate(zip(
                                                self.firstTremoloLinesInTrack,
                                                self.lastTremoloLinesInTrack)):
            lastLineRemovalIndices: List[int] = []
            firstLineRemovalIndices: List[int] = []
            currLastLineIndex: int = None
            prevLastLineIndex: int = None
            currFirstLineIndex: int = None
            for idx, (firstLine, lastLine) in enumerate(zip(firstLines, lastLines)):
                prevLastLineIndex = currLastLineIndex
                currFirstLineIndex = firstLine.lineIndex
                currLastLineIndex = lastLine.lineIndex

                if prevLastLineIndex is not None:
                    if not self.notesFoundInTrackBetweenLineIndices(track, prevLastLineIndex, currFirstLineIndex):
                        lastLineRemovalIndices.append(idx-1)
                        firstLineRemovalIndices.append(idx)

            for lineIndexToRemove in reversed(lastLineRemovalIndices):
                lastLines.pop(lineIndexToRemove)
            for lineIndexToRemove in reversed(firstLineRemovalIndices):
                firstLines.pop(lineIndexToRemove)


        # Insert starting *tremolo(s)
        for track, firstLines in enumerate(self.firstTremoloLinesInTrack):
            if not firstLines: # no first times in this track
                continue

            for firstLine in firstLines:
                if firstLine is None:
                    continue

                line: HumdrumLine = self.infile.insertNullInterpretationLineAt(
                                                            firstLine.lineIndex)
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

                line: HumdrumLine = self.infile.insertNullInterpretationLineAt(
                                                            lastLine.lineIndex+1)
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
    def expandTremolos(self):
        i = 0
        while i < len(self.markupTokens):
            token: HumdrumToken = self.markupTokens[i]
            if '@@' in token.text:
                token2: Optional[HumdrumToken] = None
                if i+1 < len(self.markupTokens):
                    token2 = self.markupTokens[i+1]
                self.expandFingerTremolo(token, token2)
                i += 2
            else:
                self.expandTremolo(self.markupTokens[i])
                i += 1

    '''
    //////////////////////////////
    //
    // Tool_tremolo::expandTremolo --
    '''
    def expandTremolo(self, token: HumdrumToken):
        value: int = 0
        addBeam: bool = False
        tnotes: int = -1

        m = re.search(r'@(\d+)@', token.text)
        if not m:
            return

        value = int(m.group(1))
        duration: HumNum = Convert.recipToDuration(token.text)
        count: HumNum = HumNum(duration * value / 4)
        if count.denominator != 1:
            print(f'Error: non-integer number of tremolo notes: {token}', file=sys.stderr)
            return
        if value < 8:
            print(f'Error: tremolo notes can only be eighth-notes or shorter: {token}',
                    file=sys.stderr)
            return
        if float(duration) > 0.5:
            # needs to be less than one for tuplet quarter note tremolos
            addBeam = True

        # There are cases where duration < 1 need added beams
        # when the note is not already in a beam.  Such as
        # a plain 8th note with a slash.  This needs to be
        # converted into two 16th notes with a beam so that
        # *tremolo can reduce it back into a tremolo, since
        # it will only reduce beam groups.

        repeat: HumNum = duration
        repeat *= value
        repeat /= 4
        increment: HumNum = HumNum(4)
        increment /= value
        if repeat.denominator != 1:
            print(f'Error: tremolo repetition count must be an integer: {token}',
                    file=sys.stderr)
            return
        tnotes = repeat.numerator

        self.storeFirstTremoloNoteInfo(token)

        beams: int = int(math.log(float(value), 2)) - 2
        markup: str = f'@{value.numerator}@'
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
        base = re.sub(r'\d+%?\d*\.*', str(value.numerator), base)
        initial: str = base
        if hasBeamStart:
            initial += startBeam
        terminal: str = base
        if hasBeamStop:
            terminal += endBeam

        # remove slur end from start of tremolo:
        terminal = re.sub(r'[(]+[<>]', '', terminal)

        token.text = initial
        token.ownerLine.createLineFromTokens()

        # Now fill in the rest of the tremolos.
        startTime: HumNum = token.durationFromStart
        timestamp: HumNum = startTime + increment
        currTok: HumdrumToken = token.nextToken(0)
        counter: int = 1

        while currTok is not None:
            if not currTok.isData:
                currTok = currTok.nextToken(0)
                continue

            duration: HumNum = currTok.ownerLine.duration
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

            timestamp += increment
            currTok = currTok.nextToken(0)

    '''
    //////////////////////////////
    //
    // Tool_tremolo::expandFingerTremolos --
    '''
    def expandFingerTremolo(self, token1: HumdrumToken, token2: HumdrumToken):
        if token2 is None:
            return

        m = re.search(r'@@(\d+)@@', token1.text)
        if not m:
            return

        value: int = int(m.group(1))
        if not Convert.isPowerOfTwo(HumNum(value)):
            print(f'Error: not a power of two: {token1}', file=sys.stderr)
            return
        if value < 8:
            print(f'Error: tremolo can only be eighth-notes or shorter: {token1}', file=sys.stderr)
            return

        duration: HumNum = Convert.recipToDuration(token1.text)
        count: HumNum = duration

        count *= value
        count /= 4
        if count.denominator != 1:
            print(f'Error: tremolo repetition count must be an integer: {token1}', file=sys.stderr)
            return
        increment: HumNum = HumNum(4)
        increment /= value

        tnotes: int = count.numerator * 2

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

        # remove slur information from middle of tremolo
        base1 = re.sub(r'[()]+[<>]?', '', base1)

        token1.text = initial
        token1.ownerLine.createLineFromTokens()

        base2: str = token2.text
        base2 = re.sub(markup, '', base2)
        base2 = re.sub(r'[LJKk]+', '', base2)
        base2 = re.sub(r'\d+%?\d*\.*', str(value), base2)

        terminal: str = base2 + endBeam
        # remove slur start information from end of tremolo:
        terminal = re.sub(r'[(]+[<>]?', '', terminal)

        state: bool = False

        # Now fill in the rest of the tremolos.
        startTime: HumNum = token1.durationFromStart
        timestamp: HumNum = startTime + increment
        currTok: HumdrumToken = token1.nextToken(0)
        counter: int = 1
        while currTok is not None:
            if not currTok.isData:
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

            timestamp += increment
            currTok = currTok.nextToken(0)

    '''
    //////////////////////////////
    //
    // Tool_tremolo::storeFirstTremoloNote --
    '''
    def storeFirstTremoloNoteInfo(self, token: HumdrumToken):
        if token is None:
            return

        track: int = token.track
        if track < 1:
            print(f'Track is not set for token: {token}', file=sys.stderr)
            return

        self.firstTremoloLinesInTrack[track].append(token.ownerLine)

    '''
    //////////////////////////////
    //
    // Tool_tremolo::storeLastTremoloNote --
    '''
    def storeLastTremoloNoteInfo(self, token: HumdrumToken):
        if token is None:
            return

        track: int = token.track
        if track < 1:
            print(f'Track is not set for token: {token}', file=sys.stderr)
            return

        self.lastTremoloLinesInTrack[track].append(token.ownerLine)
