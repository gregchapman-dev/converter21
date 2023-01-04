# ------------------------------------------------------------------------------
# Name:          HumdrumFileContent.py
# Purpose:       Used to add content analysis to HumdrumFileStructure class,
#                and do other higher-level processing of Humdrum data.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import re
import typing as t
from fractions import Fraction
from pathlib import Path

from music21.common import opFrac

from converter21.humdrum import HumdrumInternalError
from converter21.humdrum import HumNum
from converter21.humdrum import Convert
from converter21.humdrum import M21Convert
from converter21.humdrum import HumdrumToken
from converter21.humdrum import HumdrumFileStructure
from converter21.humdrum import TokenPair

# spineColors array will contains slots for this many subtracks
MAXCOLORSUBTRACK: int = 30

class HumdrumFileContent(HumdrumFileStructure):
    # HumdrumFileContent has no private data to initialize, just a bunch more functions
    # So... no __init__.  Well, OK, to keep pylint happy about attribute-defined-outside-init,
    # a quick __init__ that sets a few attributes that are already set in HumdrumFileBase.py
    def __init__(self, fileName: t.Optional[t.Union[str, Path]] = None) -> None:
        super().__init__(fileName)  # initialize the HumdrumFileBase fields
        self._hasInformalBreaks: bool = False
        self._hasFormalBreaks: bool = False

        # spinecolor = self._spineColor[track][subtrack]
        self._spineColor: t.List[t.List[str]] = []

        self._staffStarts: t.List[HumdrumToken] = []     # len = staffCount
        self._staffStartsIndexByTrack: t.List[int] = []  # len = staffCount + 1

    def readString(self, contents: str) -> bool:
        if not super().readString(contents):
            return self.isValid
        return self.isValid

    def analyzeNotation(self) -> None:
        # This code originally was in verovio/iohumdrum.cpp (by Craig Sapp)
        # Here I am consolidating this into one HumdrumFileContent method which
        # can be called from any client that wants notation support (e.g.
        # HumdrumFile.createM21Stream)

        # Might be worth adding to HumdrumFileContent at some point
        # m_multirest = analyzeMultiRest(infile);

        self.analyzeBreaks()
        self.analyzeSlurs()
        self.analyzePhrasings()
        self.analyzeKernTies()
        # self.analyzeKernStemLengths()  # Don't know why this is commented out in iohumdrum.cpp
        self.analyzeRestPositions()
        self.analyzeKernAccidentals()
        self.analyzeTextRepetition()

#         if (m_signifiers.terminallong) {
#             hideTerminalBarlines(infile);
#         }
#         checkForColorSpine(infile); # interesting to move here
        self.analyzeRScale()

        # If there are any cross-staff notes/chords, set their stems to be out of the way
        # of any other notes in that other staff (i.e. stems down if the note moved into
        # the staff above, and vice versa), and if there is only one layer in that
        # other staff, move the stems of any notes that might overlap in the opposite
        # direction (i.e. stems up if the cross-staff note has its stem down).
        self.analyzeCrossStaffStemDirections()

#         # iohumdrum calls this to deal with measure vs barline in MEI.
#         self.analyzeBarlines();

        self.analyzeClefNulls()

#         if (infile.hasDifferentBarlines()) {
#             adjustMeasureTimings(infile); # Interesting to move here, but confuses me (why?)
#         }

        self.initializeSpineColor()
#         initializeIgnoreVector(infile); # interesting to move here

#         extractNullInformation(m_nulls, infile); # might be interesting?
#         Perhaps very MEI-specific. (actually needed, but replaced by FakeRestToken stuff)


    def analyzeCrossStaffStemDirections(self) -> None:
        above: str = self._signifiers.above
        below: str = self._signifiers.below
        if not above and not below:
            # no cross-staff notes present in data
            return

        for staffStart in self._staffStarts:
            self.analyzeStaffCrossStaffStemDirections(staffStart)

    def analyzeStaffCrossStaffStemDirections(self, startToken: t.Optional[HumdrumToken]) -> None:
        if startToken is None:
            return
        if not startToken.isKern:
            return
        above: str = self._signifiers.above
        below: str = self._signifiers.below
        if not above and not below:
            # no cross-staff notes present in data
            return

        current: t.Optional[HumdrumToken] = startToken
        while current is not None:
            if current.isData:
                self.checkCrossStaffStems(current, above, below)
            current = current.nextToken0

    def checkCrossStaffStems(self, token: HumdrumToken, above: str, below: str) -> None:
        track: t.Optional[int] = token.track
        current: t.Optional[HumdrumToken] = token
        while current is not None:
            if current.track != track:
                break
            self.checkDataForCrossStaffStems(current, above, below)
            current = current.nextFieldToken

    def checkDataForCrossStaffStems(self, token: HumdrumToken, above: str, below: str) -> None:
        if token.isNull:
            return
        if token.isRest:
            return
        if '/' in token.text:
            # has a stem-up marker, so do not try to adjust stems
            return
        if '\\' in token.text:
            # has a stem-down marker, so do not try to adjust stems
            return

        hasAbove: bool = False
        hasBelow: bool = False
        notePattern: str = r'[A-Ga-g]+[#n-]*'
        if above:
            if re.search(notePattern + above, token.text):
                # note/chord has staff-above signifier
                hasAbove = True
        if below:
            if re.search(notePattern + below, token.text):
                # note/chord has staff-below signifier
                hasBelow = True

        if not (hasAbove or hasBelow):
            # no above/below signifier, so nothing to do
            return
        if hasAbove and hasBelow:
            # strange complication of above and below, so ignore
            return
        if hasAbove:
            self.prepareStaffAboveNoteStems(token)
        elif hasBelow:
            self.prepareStaffBelowNoteStems(token)

    def prepareStaffAboveNoteStems(self, token: HumdrumToken) -> None:
        token.setValue('auto', 'stem.dir', '-1')
        track: t.Optional[int] = token.track
        curr: t.Optional[HumdrumToken] = token.nextFieldToken
        ttrack: t.Optional[int]

        # Find the next higher **kern spine (if any)
        while curr is not None:
            ttrack = curr.track
            if not curr.isKern:
                curr = curr.nextFieldToken
                continue
            if ttrack == track:
                curr = curr.nextFieldToken
                continue
            # is kern data and in a different spine
            break

        if curr is None:
            # no higher staff of **kern data
            return

        if not curr.isKern:
            # something strange happened
            return

        endTime: HumNum = opFrac(token.durationFromStart + token.duration)
        curr2: t.Optional[HumdrumToken] = curr
        while curr2 is not None:
            if curr2.durationFromStart >= endTime:
                # exceeded the duration of the cross-staff note, so stop looking
                break

            if not curr2.isData:
                # ignore non-data tokens
                curr2 = curr2.nextToken0
                continue
            if curr2.isNull:
                curr2 = curr2.nextToken0
                continue
            if curr2.isRest:
                # ignore rests
                curr2 = curr2.nextToken0
                continue
            if not curr2.isNote:
                curr2 = curr2.nextToken0
                continue
            if '/' in curr2.text or '\\' in curr2.text:
                # the note/chord has a stem direction, so ignore it
                curr2 = curr2.nextToken0
                continue
            if curr2.subTrack != 0:
                # layer != 0 means there is more than one active layer at this point in the
                # above staff.  If so, then do not assign any stem directions.
                curr2 = curr2.nextToken0
                continue

            # set the stem to up for the current note/chord
            curr2.setValue('auto', 'stem.dir', '1')
            curr2 = curr2.nextToken0

    def prepareStaffBelowNoteStems(self, token: HumdrumToken) -> None:
        token.setValue('auto', 'stem.dir', '1')
        track: t.Optional[int] = token.track
        curr: t.Optional[HumdrumToken] = token.previousFieldToken
        ttrack: t.Optional[int]

        # Find the next lower **kern spine (if any):
        while curr is not None:
            ttrack = curr.track
            if not curr.isKern:
                curr = curr.previousFieldToken
                continue
            if ttrack == track:
                curr = curr.previousFieldToken
                continue
            # is kern data and in a different spine
            break

        if curr is None:
            return

        if not curr.isKern:
            # something strange happened
            return

        # Find the first subtrack of the identified spine
        targetTrack: t.Optional[int] = curr.track
        while curr is not None:
            ptok: t.Optional[HumdrumToken] = curr.previousFieldToken
            if ptok is None:
                break
            ttrack = ptok.track
            if targetTrack != ttrack:
                break
            curr = ptok
            # ptok = curr.previousToken  # this is wrong, and ignored, I think

        # Should now be at the first subtrack of the target staff.

        endTime: HumNum = opFrac(token.durationFromStart + token.duration)
        curr2: t.Optional[HumdrumToken] = curr
        while curr2 is not None:
            if curr2.durationFromStart >= endTime:
                # exceeded the duration of the cross-staff note, so stop looking
                break

            if not curr2.isData:
                # ignore non-data tokens
                curr2 = curr2.nextToken0
                continue
            if curr2.isNull:
                curr2 = curr2.nextToken0
                continue
            if curr2.isRest:
                # ignore rests
                curr2 = curr2.nextToken0
                continue
            if not curr2.isNote:
                curr2 = curr2.nextToken0
                continue
            if '/' in curr2.text or '\\' in curr2.text:
                # the note/chord has a stem direction, so ignore it
                curr2 = curr2.nextToken0
                continue
            if curr2.subTrack != 0:
                # layer != 0 means there is more than one active layer at this point in the
                # below staff.  If so, then do not assign any stem directions.
                curr2 = curr2.nextToken0
                continue

            # set the step to down for the current note/chord
            curr2.setValue('auto', 'stem.dir', '-1')
            curr2 = curr2.nextToken0

    '''
    //////////////////////////////
    //
    // HumdrumInput::analyzeClefNulls -- Mark all null interpretations
    //    that are in the same track as a clef interpretation.
    '''
    def analyzeClefNulls(self) -> None:
        for line in self.lines():
            if not line.isInterpretation:
                continue

            for token in line.tokens():
                if not token.isKern:
                    continue
                if not token.isClef:
                    continue
                self.markAdjacentNullsWithClef(token)

    '''
    //////////////////////////////
    //
    // HumdrumInput::markAdjacentNullsWithClef -- Input is a clef token,
    //     and all null interpretations in the same track will be marked
    //     as being the same clef, since verovio/MEI requires clef changes
    //     to be present in all layers.
        ... and music21 likes this (in all voices) too. --gregc
    '''
    @staticmethod
    def markAdjacentNullsWithClef(clef: HumdrumToken) -> None:
        ctrack: t.Optional[int] = clef.track
        if ctrack is None:
            return

        track: t.Optional[int] = 0

        current: t.Optional[HumdrumToken] = clef.nextFieldToken
        while current is not None:
            track = current.track
            if track != ctrack:
                break
            if current.text == '*':
                current.setValue('auto', 'clef', clef.text)
            current = current.nextFieldToken

        current = clef.previousFieldToken
        while current is not None:
            track = current.track
            if track != ctrack:
                break
            if current.text == '*':
                current.setValue('auto', 'clef', clef.text)
            current = current.previousFieldToken

    '''
    //////////////////////////////
    //
    // HumdrumInput::analyzeBreaks -- Returns true if there are page or
    //   system breaks in the data.

        Actually sets self._hasFormalBreaks and self._hasInformalBreaks
    '''
    def analyzeBreaks(self) -> None:
        # check for informal breaking markers such as:
        # !!pagebreak:original
        # !!linebreak:original
        # we don't pay attention to informal breaks (these are the breaks that happened
        # to be in the original score, not breaks that were specified as part of that score)
        #   for line in self._lines:
        #       if not line.isGlobalComment:
        #           continue
        #
        #       if line[0].text.startswith('!!pagebreak:'):
        #           self._hasInformalBreaks = True
        #           break
        #
        #       if line[0].text.startswith('!!linebreak:'):
        #           self._hasInformalBreaks = True
        #           break

        # check for formal breaking markers such as:
        # !!LO:PB:g=z
        # !!LO:LB:g=z
        for line in self._lines:
            if not line.isComment:
                continue

            if line[0] is None:
                # shouldn't happen, but...
                continue

            if '!LO:LB' in line[0].text:
                self._hasFormalBreaks = True
                break

            if '!LO:PB' in line[0].text:
                self._hasFormalBreaks = True
                break

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::analyzeSlurs -- Link start and ends of
    //    slurs to each other.
    '''
    def analyzeSlurs(self) -> bool:
        if self._analyses.slursAnalyzed:
            return False

        self._analyses.slursAnalyzed = True

        output: bool = True
        output = output and self.analyzeSlursOrPhrases(HumdrumToken.SLUR, '**kern')
        output = output and self.analyzeSlursOrPhrases(HumdrumToken.SLUR, '**mens')
        return output

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::analyzePhrasings -- Link start and ends of
    //    phrases to each other.
    '''
    def analyzePhrasings(self) -> bool:
        if self._analyses.phrasesAnalyzed:
            return False

        self._analyses.phrasesAnalyzed = True

        output: bool = True
        output = output and self.analyzeSlursOrPhrases(HumdrumToken.PHRASE, '**kern')
        return output

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::analyzeMensSlurs -- Link start and ends of
    //    slurs to each other.  They are the same as **kern, so borrowing
    //    analyzeKernSlurs to do the analysis.

        analyzeKernSlurs, analyzeMensSlurs, and analyzeKernPhrases (and their
        support functions) are almost completely identical, so I am combining
        them all into one parameterized set of functions. --gregc 17feb2021

        analyzeSlursOrPhrases takes two params:
            slurOrPhrase - HumdrumToken.SLUR or HumdrumToken.PHRASE
            spineDataType - '**kern' or '**mens'

            SLUR and PHRASE are defined (and used) in HumdrumToken.py, where I have
            combined the {slur,phrase}{Start,End}ElisionLevel functions into the
            startElisionLevel(slurOrPhrase, index) and
            endElisionLevel(slurOrPhrase, index)
    '''
    def analyzeSlursOrPhrases(self, slurOrPhrase: str, spineDataType: str) -> bool:
        spineStarts: t.List[HumdrumToken] = self.spineStartListOfType(spineDataType)
        if not spineStarts:
            return True

        # labels: first is previous label, last is next label
        labels: t.List[TokenPair] = [TokenPair(None, None)] * self.lineCount
        l: t.List[t.Optional[HumdrumToken]] = [None] * self.lineCount

        for i, line in enumerate(self._lines):
            if not line.isInterpretation:
                continue
            token = line[0]
            if token is not None and token.text.startswith('*>') and '[' not in token.text:
                l[i] = token

        current: t.Optional[HumdrumToken] = None
        for i, label in enumerate(l):
            if label is not None:
                current = label
            labels[i].first = current

        current = None
        for i, label in enumerate(reversed(l)):
            if label is not None:
                current = label
            labels[i].last = current

        endings: t.List[int] = [0] * self.lineCount
        ending: int = 0
        for i, label in enumerate(l):
            if label is not None:
                ending = 0
                lastChar = label.text[-1]
                if lastChar.isdigit():
                    ending = int(lastChar)
            endings[i] = ending

        output: bool = True
        slurStarts: t.List[HumdrumToken] = []
        slurEnds: t.List[HumdrumToken] = []
        linkSignifier: str = self._signifiers.linked
        for spineStart in spineStarts:
            output = (
                output and self.analyzeSpineSlursOrPhrases(
                    slurOrPhrase,
                    spineStart,
                    slurStarts,
                    slurEnds,
                    labels,
                    endings,
                    linkSignifier)
            )

        self.createLinkedSlursOrPhrases(slurOrPhrase, slurStarts, slurEnds)
        return output

    def analyzeSpineSlursOrPhrases(
            self,
            slurOrPhrase: str,
            spineStart: HumdrumToken,
            linkStarts: t.List[HumdrumToken],
            linkEnds: t.List[HumdrumToken],
            labels: t.List[TokenPair],
            endings: t.List[int],
            linkSig: str
    ) -> bool:
        beginStr: str = ''
        endStr: str = ''
        endingBackTag: str = ''
        sideTag: str = ''
        durationTag: str = ''
        hangingTag: str = ''
        openIndexTag: str = ''

        if slurOrPhrase == HumdrumToken.SLUR:
            beginStr = '('
            endStr = ')'
            endingBackTag = 'endingSlurBack'
            sideTag = 'slurSide'
            durationTag = 'slurDuration'
            hangingTag = 'hangingSlur'
            openIndexTag = 'slurOpenIndex'
        elif slurOrPhrase == HumdrumToken.PHRASE:
            beginStr = '{'
            endStr = '}'
            endingBackTag = 'endingPhraseBack'
            sideTag = 'phraseSide'
            durationTag = 'phraseDuration'
            hangingTag = 'hangingPhrase'
            openIndexTag = 'phraseOpenIndex'
        else:
            return False

        # linked phrases/slurs handled separately, so generate an ignore sequence:
        ignoreBegin: str = linkSig + beginStr
        ignoreEnd: str = linkSig + endStr

        # tracktokens == the 2-D data list for the track,
        # arranged in layers with the second dimension.
        trackTokens: t.List[t.List[HumdrumToken]] = self.getTrackSequence(
            startToken=spineStart, options=self.OPT_DATA | self.OPT_NOEMPTY
        )

        # opens == list of phrase/slur openings for each track and elision level
        # first dimension: elision level (max: 4)
        # second dimension: layer number (max: 8)
        opens: t.List[t.List[t.List[HumdrumToken]]] = []
        for _el in range(0, 4):
            opens.append([])
            for _tr in range(0, 8):
                opens[-1].append([])

        openCount: int = 0
        closeCount: int = 0
        elision: int = 0

        for rowOfTokens in trackTokens:
            for track, token in enumerate(rowOfTokens):
                if not token.isData:
                    continue
                if token.isNull:
                    continue
                openCount = token.text.count('(')
                closeCount = token.text.count(')')

                for i in range(0, closeCount):
                    if self._isLinkedSlurOrPhraseEnd(slurOrPhrase, token, i, ignoreEnd):
                        linkEnds.append(token)
                        continue

                    elision = token.endElisionLevel(slurOrPhrase, i)
                    if elision < 0:
                        continue

                    if opens[elision][track]:
                        # list of slur/phrase opens is not empty
                        self._linkSlurOrPhraseEndpoints(
                            slurOrPhrase, opens[elision][track][-1], token
                        )
                        # remove that last slur/phrase opening from buffer
                        opens[elision][track] = opens[elision][track][:-1]
                    else:
                        # No starting slur/phrase marker to match to this slur/phrase end in the
                        # given track.
                        # Search for an open slur/phrase in another track:
                        found: bool = False
                        for iTrack in range(0, len(opens[elision])):
                            if opens[elision][iTrack]:
                                # list of slur/phrase opens is not empty
                                self._linkSlurOrPhraseEndpoints(slurOrPhrase,
                                                               opens[elision][iTrack][-1],
                                                               token)
                                # remove slur/phrase opening from buffer
                                opens[elision][iTrack] = opens[elision][iTrack][:-1]
                                found = True
                                break
                        if not found:
                            lineIndex: int = token.lineIndex
                            endNum: int = endings[lineIndex]
                            pIndex: int = -1
                            first: t.Optional[HumdrumToken] = labels[lineIndex].first
                            if first is not None:
                                pIndex = first.lineIndex - 1

                            endNumPre: int = -1
                            if pIndex >= 0:
                                endNumPre = endings[pIndex]

                            if endNumPre > 0 and endNum > 0 and endNumPre != endNum:
                                # This is a slur/phrase in an ending that starts at the
                                # start of an ending.
                                duration: HumNum = token.durationFromStart
                                first = labels[token.lineIndex].first
                                if first is not None:
                                    duration = opFrac(duration - first.durationFromStart)
                                token.setValue('auto', endingBackTag, 'true')
                                token.setValue('auto', sideTag, 'stop')
                                token.setValue('auto', durationTag, token.durationToEnd)
                            else:
                                # This is a slur/phrase closing that does not have a
                                # matching opening.
                                token.setValue('auto', hangingTag, 'true')
                                token.setValue('auto', sideTag, 'stop')
                                token.setValue('auto', openIndexTag, str(i))
                                token.setValue('auto', durationTag, token.durationToEnd)

                for i in range(0, openCount):
                    if self._isLinkedSlurOrPhraseBegin(slurOrPhrase, token, i, ignoreBegin):
                        linkStarts.append(token)
                        continue
                    elision = token.startElisionLevel(slurOrPhrase, i)
                    if elision < 0:
                        continue
                    opens[elision][track].append(token)

        # Mark unclosed slur/phrase starts:
        for elisionOpens in opens:
            for trackOpens in elisionOpens:
                for openToken in trackOpens:
                    openToken.setValue('', 'auto', hangingTag, 'true')
                    openToken.setValue('', 'auto', sideTag, 'start')
                    openToken.setValue('', 'auto', durationTag, openToken.durationFromStart)

        return True

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::createLinkedSlurs --  Currently assume that
    //    start and ends are matched.
    '''
    def createLinkedSlursOrPhrases(self,
            slurOrPhrase: str,
            linkStarts: t.List[HumdrumToken],
            linkEnds: t.List[HumdrumToken]) -> None:
        shortest: int = len(linkStarts)
        if shortest > len(linkEnds):
            shortest = len(linkEnds)
        if shortest == 0:
            # nothing to do
            return

        for i in range(0, shortest):
            self._linkSlurOrPhraseEndpoints(slurOrPhrase, linkStarts[i], linkEnds[i])

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::isLinkedSlurEnd --
    '''
    @staticmethod
    def _isLinkedSlurOrPhraseEnd(
            slurOrPhrase: str,
            token: HumdrumToken,
            index: int,
            pattern: str
    ) -> bool:
        endStr: str = ''
        if slurOrPhrase == HumdrumToken.SLUR:
            endStr = ')'
        elif slurOrPhrase == HumdrumToken.PHRASE:
            endStr = '}'
        else:
            return False

        if pattern is None or len(pattern) <= 1:
            return False

        counter: int = -1
        for i in range(0, len(token.text)):
            if token.text[i] == endStr:
                counter += 1

            if i == 0:
                # Can't have linked slur at starting index in string.
                continue

            if counter != index:
                continue

            startIndex: int = 1 - len(pattern) + 1
            if token.text[startIndex:].startswith(pattern):
                return True
            return False

        return False

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::isLinkedSlurBegin --
    '''
    @staticmethod
    def _isLinkedSlurOrPhraseBegin(
            slurOrPhrase: str,
            token: HumdrumToken,
            index: int,
            pattern: str
    ) -> bool:
        startStr: str = slurOrPhrase

        if pattern is None or len(pattern) <= 1:
            return False

        counter: int = -1
        for i in range(0, len(token.text)):
            if token.text[i] == startStr:
                counter += 1

            if i == 0:
                continue

            if counter != index:
                continue

            startIndex = i - len(pattern) + 1
            if pattern in token.text[startIndex:]:
                return True
            return False
        return False

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::linkSlurEndpoints --  Allow up to two slur starts/ends
    //      on a note.
    '''
    @staticmethod
    def _linkSlurOrPhraseEndpoints(
            slurOrPhrase: str,
            startTok: HumdrumToken,
            endTok: HumdrumToken
    ) -> None:
        if slurOrPhrase == HumdrumToken.SLUR:
            prefix = 'slur'
        else:
            prefix = 'phrase'

        durTag: str = prefix + 'Duration'
        endTag: str = prefix + 'EndId'
        startTag: str = prefix + 'StartId'
        startNumberTag: str = prefix + 'StartNumber'
        endNumberTag: str = prefix + 'EndNumber'
        startCountTag: str = prefix + 'StartCount'
        endCountTag: str = prefix + 'EndCount'



        startCount: int = startTok.getValueInt('auto', startCountTag) + 1
        openCount: int = startTok.text.count(slurOrPhrase)
        openEnumeration = openCount - startCount + 1

        if openEnumeration > 1:
            openSuffix: str = str(openEnumeration)
            endTag += openSuffix
            durTag += openSuffix

        endCount: int = endTok.getValueInt('auto', endCountTag) + 1
        closeEnumeration: int = endCount
        if closeEnumeration > 1:
            closeSuffix: str = str(closeEnumeration)
            startTag += closeSuffix
            startNumberTag += closeSuffix

        duration: HumNum = opFrac(endTok.durationFromStart - startTok.durationFromStart)

        startTok.setValue('auto', endTag, endTok)
        startTok.setValue('auto', 'id', startTok)
        startTok.setValue('auto', endNumberTag, closeEnumeration)
        startTok.setValue('auto', durTag, duration)
        startTok.setValue('auto', startCountTag, startCount)

        endTok.setValue('auto', startTag, startTok)
        endTok.setValue('auto', 'id', endTok)
        endTok.setValue('auto', startNumberTag, openEnumeration)
        endTok.setValue('auto', endCountTag, endCount)

#         print('SLUR: starts at {} (lineNum:{}, fieldNum:{}), ends at {} (lineNum:{},
#               fieldNum:{})'.format(startTok.text, startTok.lineNumber, startTok.fieldNumber,
#               endTok.text, endTok.lineNumber, endTok.fieldNumber), file=sys.stderr)

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::analyzeKernTies -- Link start and ends of
    //    ties to each other.
    '''
    def analyzeKernTies(self) -> bool:
        output: bool = True
        linkedTieStarts: t.List[t.Tuple[HumdrumToken, int]] = []
        linkedTieEnds: t.List[t.Tuple[HumdrumToken, int]] = []
        linkSignifier: str = self._signifiers.linked

        output = self.generateLinkedTieStartsAndEnds(linkedTieStarts, linkedTieEnds, linkSignifier)
        self.createLinkedTies(linkedTieStarts, linkedTieEnds)
        return output

    '''
    // Could be generalized to allow multiple grand-staff pairs by limiting
    // the search spines for linking (probably with *part indications).
    // Currently all spines are checked for linked ties.
    '''

    def generateLinkedTieStartsAndEnds(
            self,
            linkedTieStarts: t.List[t.Tuple[HumdrumToken, int]],
            linkedTieEnds: t.List[t.Tuple[HumdrumToken, int]],
            linkSignifier: str
    ) -> bool:
        # Use this in the future to limit to grand-staff search (or 3 staves for organ):
        # vector<vector<HTp> > tracktokens;
        # this->getTrackSeq(tracktokens, spinestart, OPT_DATA | OPT_NOEMPTY);

        # Only analyzing linked ties for now (others ties are handled without analysis in
        # HumdrumFile.createMusic21Stream, for example).
        if linkSignifier is None or linkSignifier == '':
            return True

        lstart: str = linkSignifier + '['
        lmiddle: str = linkSignifier + '_'
        lend: str = linkSignifier + ']'

        startDatabase: t.List[t.Tuple[t.Optional[HumdrumToken], int]] = [(None, -1)] * 400

        for line in self._lines:
            if not line.isData:
                continue

            for tok in line.tokens():
                if not tok.isKern:
                    continue
                if not tok.isData:
                    continue
                if tok.isNull:
                    continue
                if tok.isRest:
                    continue

                for subtokenIdx, subtokenStr in enumerate(tok.subtokens):
                    if lstart in subtokenStr:
                        startb40: int = Convert.kernToBase40(subtokenStr)
                        startDatabase[startb40] = (tok, subtokenIdx)

                    if lend in subtokenStr:
                        endb40: int = Convert.kernToBase40(subtokenStr)
                        endEntry: t.Tuple[t.Optional[HumdrumToken], int] = startDatabase[endb40]
                        if endEntry[0] is not None:
                            if t.TYPE_CHECKING:
                                assert isinstance(endEntry[0], HumdrumToken)
                            linkedTieStarts.append((endEntry[0], endEntry[1]))
                            linkedTieEnds.append((tok, subtokenIdx))
                            startDatabase[endb40] = (None, -1)

                    if lmiddle in subtokenStr:
                        middleb40: int = Convert.kernToBase40(subtokenStr)
                        middleEntry: t.Tuple[t.Optional[HumdrumToken], int] = (
                            startDatabase[middleb40]
                        )
                        if middleEntry[0] is not None:
                            if t.TYPE_CHECKING:
                                assert isinstance(middleEntry[0], HumdrumToken)
                            linkedTieStarts.append((middleEntry[0], middleEntry[1]))
                            linkedTieEnds.append((tok, subtokenIdx))
                        startDatabase[middleb40] = (tok, subtokenIdx)

        return True

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::createLinkedTies --
    '''
    def createLinkedTies(
            self,
            linkStarts: t.List[t.Tuple[HumdrumToken, int]],
            linkEnds: t.List[t.Tuple[HumdrumToken, int]]
    ) -> None:
        shortest = len(linkStarts)
        if shortest > len(linkEnds):
            shortest = len(linkEnds)
        if shortest == 0:
            # nothing to do
            return

        for i in range(0, shortest):
            self._linkTieEndpoints(
                linkStarts[i][0], linkStarts[i][1], linkEnds[i][0], linkEnds[i][1]
            )

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::linkTieEndpoints --
    '''
    @staticmethod
    def _linkTieEndpoints(
            tieStart: HumdrumToken,
            startSubtokenIdx: int,
            tieEnd: HumdrumToken,
            endSubtokenIdx: int
    ) -> None:
        durTag: str = 'tieDuration'
        startTag: str = 'tieStart'
        endTag: str = 'tieEnd'
        startNumTag: str = 'tieStartSubtokenNumber'
        endNumTag: str = 'tieEndSubtokenNumber'

        startSubtokenNumber: int = startSubtokenIdx + 1
        endSubtokenNumber: int = endSubtokenIdx + 1

        if tieStart.isChord:
            if startSubtokenNumber > 0:
                startSuffix: str = str(startSubtokenNumber)
                durTag += startSuffix
                endNumTag += startSuffix
                endTag += startSuffix

        if tieEnd.isChord:
            if endSubtokenNumber > 0:
                endSuffix: str = str(endSubtokenNumber)
                startTag += endSuffix
                startNumTag += endSuffix

        tieStart.setValue('auto', endTag, tieEnd)
        tieStart.setValue('auto', 'id', tieStart)
        if endSubtokenNumber > 0:
            tieStart.setValue('auto', endNumTag, str(endSubtokenNumber))

        tieEnd.setValue('auto', startTag, tieStart)
        tieEnd.setValue('auto', 'id', tieEnd)
        if startSubtokenNumber > 0:
            tieEnd.setValue('auto', startNumTag, str(startSubtokenNumber))

        duration: HumNum = opFrac(tieEnd.durationFromStart - tieStart.durationFromStart)
        tieStart.setValue('auto', durTag, duration)

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::analyzeRestPositions -- Calculate the vertical position
    //    of rests on staves with two layers.
    '''
    def analyzeRestPositions(self) -> None:
        # I will not be assigning implicit vertical rest positions to workaround
        # verovio's subsequent adjustments.  I will just be noting explicit vertical
        # rest positions.  --gregc
        self.checkForExplicitVerticalRestPositions()

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::checkForExplicitVerticalRestPositions -- Starting at the
    //     current layer, check all rests in the same track for vertical positioning.
    '''
    def checkForExplicitVerticalRestPositions(self) -> None:
        # default to treble clef
        defaultBaseline: int = Convert.kernClefToBaseline('*clefG2')
        baselines: t.List[int] = [defaultBaseline] * (self.maxTrack + 1)

        for line in self._lines:
            if line.isInterpretation:
                for tok in line.tokens():
                    if not tok.isKern:
                        continue
                    if not tok.isClef:
                        continue

                    baselines[tok.track] = Convert.kernClefToBaseline(tok.text)

            if not line.isData:
                continue

            for tok in line.tokens():
                if not tok.isKern:
                    continue
                if not tok.isRest:
                    continue

                self._checkRestForVerticalPositioning(tok, baselines[tok.track])

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::checkRestForVerticalPositioning -- Read any pitch information attached
    //     to a rest and convert to ploc/oloc values.

        Instead of ploc and oloc for MEI (which humlib does), compute and save what the
        stepShift for a music21 rest should be.
    '''
    @staticmethod
    def _checkRestForVerticalPositioning(rest: HumdrumToken, baseline: int) -> bool:
        m = re.search(r'([A-Ga-g]+)', rest.text)
        if m is None:
            return False

        pitch: str = m.group(1)
        b7: int = Convert.kernToBase7(pitch)
        if b7 < 0:
            # that wasn't really a pitch, no vertical positioning for you
            return False

        diff: int = (b7 - baseline) + 100
        if diff % 2 != 0:
            # force to every other diatonic step (staff lines)
            if rest.duration > 1:
                b7 -= 1
            else:
                b7 += 1

        # Instead of ploc and oloc for MEI (which humlib does), compute and save what the
        # stepShift for a music21 rest should be.
        # stepShift = 0 means "on the middle line", -1 means "in the first space below the
        # midline", +2 means "on the line above the midline", etc.
        # baseline is the base7 pitch of the lowest line in the staff -> stepShift = -4
        # b7 is the base7 pitch (including octave) of where the rest should go, so:

        # midline is 2 spaces + 2 lines (4 diatonic steps) above baseline
        midline: int = baseline + 4
        stepShift: int = b7 - midline
        rest.setValue('auto', 'stepShift', str(stepShift))

        return True

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::analyzeKernAccidentals -- Identify accidentals that
    //    should be printed (only in **kern spines) as well as cautionary
    //    accidentals (accidentals which are forced to be displayed but otherwise
    //    would not be printed.  Algorithm assumes that all secondary tied notes
    //    will not display their accidental across a system break.  Consideration
    //    about grace-note accidental display still needs to be done.
    '''
    def analyzeKernAccidentals(self) -> bool:
        # ottava marks must be analyzed first:
        self.analyzeOttavas()

        # We will mark a "visible accidental" in four (Humdrum) situations:
        #
        # 1. there is an 'n' specified with no "hidden" mark (a 'y' immediately
        #    following the 'n', or a 'yy' anywhere in the token)
        # 2. there is a single 'X' immediately following the '#', '-', or 'n'
        # 3. There is an editorial accidental signifier character immediately following
        #    the '#', '-', or 'n'.  We will also obey the edittype in the signifier.
        # 4. There is a linked layout param (('N', 'acc') and ('A', 'vis')) to specify
        #    display of a specific accidental (or combination, such as 'n#')
        #
        # We will also mark a visible accidental if it is necessary because the
        # accidental is not already in the key signature, and hasn't already occurred
        # in this measure (in this staff and in this octave).

        spineStartCount: int = len(self.spineStartList)

        spineStartIdxFromTrackNum: t.List[int] = [-1] * (self.maxTrack + 1)
        for i, startTok in enumerate(self.spineStartList):
            if startTok is not None and startTok.track is not None:
                spineStartIdxFromTrackNum[startTok.track] = i

        # keysigs == key signature spellings of diatonic pitch classes.  This array
        # is duplicated into dstates after each barline.
        keysigs: t.List[t.List[int]] = []
        for _ in range(0, spineStartCount):
            keysigs.append([0] * 7)

        # dstates == diatonic states for every pitch in a spine.
        # sub-spines are considered as a single unit, although there are
        # score conventions which would keep a separate voices on a staff
        # with different accidental states (i.e., two parts superimposed
        # on the same staff, but treated as if on separate staves).
        # Eventually this algorithm should be adjusted for dealing with
        # cross-staff notes, where the cross-staff notes should be following
        # the accidentals of a different spine...
        dstates: t.List[t.List[int]] = []
        for _ in range(0, spineStartCount):
            dstates.append([0] * 70)  # 10 octave limit may cause problems; fix later

        # gdstates == grace note diatonic states for every pitch in a spine.
        gdstates: t.List[t.List[int]] = []
        for _ in range(0, spineStartCount):
            gdstates.append([0] * 70)

        # firstInBar == keep track of first beat in measure.
        firstInBar: t.List[bool] = [False] * spineStartCount

        lastTrack: int = -1
        concurrentState: t.List[int] = [0] * 70

        spineStartIdx: int
        for line in self._lines:
            if not line.hasSpines:
                continue

            if line.isInterpretation:
                for token in line.tokens():
                    if not token.isKern:
                        continue

                    if token.text.startswith('*k['):
                        spineStartIdx = spineStartIdxFromTrackNum[token.track]
                        self.fillKeySignature(keysigs[spineStartIdx], token.text)

                        # resetting key states of current measure.  What to do if this
                        # key signature is in the middle of a measure?
                        self.resetDiatonicStatesWithKeySignature(
                            dstates[spineStartIdx],
                            keysigs[spineStartIdx]
                        )
                        self.resetDiatonicStatesWithKeySignature(
                            gdstates[spineStartIdx],
                            keysigs[spineStartIdx]
                        )

            elif line.isBarline:
                for token in line.tokens():
                    if not token.isKern:
                        continue

                    if token.isInvisible:
                        continue

                    firstInBar = [True] * spineStartCount
                    spineStartIdx = spineStartIdxFromTrackNum[token.track]

                    # reset the accidental states in dstates to match keysigs.
                    self.resetDiatonicStatesWithKeySignature(
                        dstates[spineStartIdx],
                        keysigs[spineStartIdx]
                    )
                    self.resetDiatonicStatesWithKeySignature(
                        gdstates[spineStartIdx],
                        keysigs[spineStartIdx]
                    )

            if not line.isData:
                continue

            concurrentState = [0] * 70
            lastTrack = -1

            for token in line.tokens():
                if not token.isKern:
                    continue

                if token.isNull:
                    continue

                if token.isRest:
                    continue

                if token.track != lastTrack:
                    concurrentState = [0] * 70

                lastTrack = token.track
                spineStartIdx = spineStartIdxFromTrackNum[token.track]

                for k, subtok in enumerate(token.subtokens):
                    if len(token.subtokens) > 1:
                        # it's a chord
                        # Rests in chords represent unsounding notes.
                        # Rests can have pitch, but this is treated as
                        # Diatonic pitch which does not involve accidentals,
                        # so convert to pitch-like so that accidentals are
                        # processed on these notes.
                        subtok = subtok.replace('r', 'R')

                    b40: int = Convert.kernToBase40(subtok)
                    diatonic: int = Convert.kernToBase7(subtok)
                    octaveAdjust: int = 0  # no ottavas yet...   token.getValueInt('auto', 'ottava')
                    diatonic -= octaveAdjust * 7
                    if diatonic < 0:
                        # Deal with extra-low notes later.
                        continue

                    isGrace: bool = token.isGrace
                    accid: int = Convert.kernToAccidentalCount(subtok)
                    isHidden: bool = False
                    if 'yy' not in subtok:  # if note is hidden accidental hiding isn't necessary
                        # if ('ny' in subtok or '#y' in subtok or '-y' in subtok):
                        #     isHidden = True
                        # We can't support hiding of accidentals (because music21
                        # doesn't really support beyond saying "this isn't necessary").
                        # We need to edit out the 'y' so that the accidental will only be
                        # visible if necessary, and further remove the 'n' as well
                        # (since an 'n' implies forced visibility).
                        if 'ny' in subtok:
                            subtok = subtok.replace('ny', '')

                    loc: int
                    if '_' in subtok or ']' in subtok:
                        # tied notes do not need accidentals, so skip them
                        if (accid != keysigs[spineStartIdx][diatonic % 7]
                                and firstInBar[spineStartIdx]):
                            # But first, prepare to force an accidental to be shown on
                            # the note immediately following the end of a tied group
                            # if the tied group crosses a barline.
                            dstates[spineStartIdx][diatonic] = -1000 + accid
                            gdstates[spineStartIdx][diatonic] = -1000 + accid

                        if '#X' not in subtok and '-X' not in subtok and 'n' not in subtok:
                            continue
                        # else an accidental should be forced at end of tie (fall through)

                    # check for accidentals on trills, mordents and turns.
                    exprNote: int
                    exprDiatonic: int
                    exprAccid: int
                    lowerInt: int
                    lowerb40: int
                    lowerDiatonic: int
                    lowerAccid: int
                    upperInt: int
                    upperb40: int
                    upperDiatonic: int
                    upperAccid: int
                    uacc: int
                    bacc: int
                    mainPitch: str
                    otherPitch: str
                    if 't' in subtok:
                        # minor second trill
                        exprNote = b40 + 5
                        exprDiatonic = Convert.base40ToDiatonic(exprNote)
                        exprAccid = Convert.base40ToAccidental(exprNote)
                        mainPitch = M21Convert.base40ToM21PitchName(b40)
                        otherPitch = M21Convert.base40ToM21PitchName(exprNote)
                        token.setValue('auto', str(k), 'trillNoteM21Pitch', mainPitch)
                        token.setValue('auto', str(k), 'trillOtherNoteM21Pitch', otherPitch)
                        if dstates[spineStartIdx][exprDiatonic] != exprAccid:
                            token.setValue(
                                'auto', str(k), 'trillAccidental', str(exprAccid))
                            # if we ever get ornament accidentals displaying, put this next
                            # line back in.
                            # dstates[spineStartIdx][exprDiatonic] = -1000 + exprAccid
                    elif 'T' in subtok:
                        # major second trill
                        exprNote = b40 + 6
                        exprDiatonic = Convert.base40ToDiatonic(exprNote)
                        exprAccid = Convert.base40ToAccidental(exprNote)
                        mainPitch = M21Convert.base40ToM21PitchName(b40)
                        otherPitch = M21Convert.base40ToM21PitchName(exprNote)
                        token.setValue('auto', str(k), 'trillNoteM21Pitch', mainPitch)
                        token.setValue('auto', str(k), 'trillOtherNoteM21Pitch', otherPitch)
                        if dstates[spineStartIdx][exprDiatonic] != exprAccid:
                            token.setValue(
                                'auto', str(k), 'trillAccidental', str(exprAccid))
                            # if we ever get ornament accidentals displaying, put this next
                            # line back in.
                            # dstates[spineStartIdx][exprDiatonic] = -1000 + exprAccid
                    elif 'M' in subtok:
                        # major second upper mordent
                        exprNote = b40 + 6
                        exprDiatonic = Convert.base40ToDiatonic(exprNote)
                        exprAccid = Convert.base40ToAccidental(exprNote)
                        if dstates[spineStartIdx][exprDiatonic] != exprAccid:
                            token.setValue(
                                'auto', str(k), 'mordentUpperAccidental', str(exprAccid))
                            # if we ever get ornament accidentals displaying, put this next
                            # line back in.
                            # dstates[spineStartIdx][exprDiatonic] = -1000 + exprAccid
                    elif 'm' in subtok:
                        # minor second upper mordent
                        exprNote = b40 + 5
                        exprDiatonic = Convert.base40ToDiatonic(exprNote)
                        exprAccid = Convert.base40ToAccidental(exprNote)
                        if dstates[spineStartIdx][exprDiatonic] != exprAccid:
                            token.setValue(
                                'auto', str(k), 'mordentUpperAccidental', str(exprAccid))
                            # if we ever get ornament accidentals displaying, put this next
                            # line back in.
                            # dstates[spineStartIdx][exprDiatonic] = -1000 + exprAccid
                    elif 'W' in subtok:
                        # major second lower mordent
                        exprNote = b40 - 6
                        exprDiatonic = Convert.base40ToDiatonic(exprNote)
                        exprAccid = Convert.base40ToAccidental(exprNote)
                        if dstates[spineStartIdx][exprDiatonic] != exprAccid:
                            token.setValue(
                                'auto', str(k), 'mordentLowerAccidental', str(exprAccid))
                            # if we ever get ornament accidentals displaying, put this next
                            # line back in.
                            # dstates[spineStartIdx][exprDiatonic] = -1000 + exprAccid
                    elif 'w' in subtok:
                        # minor second lower mordent
                        exprNote = b40 - 5
                        exprDiatonic = Convert.base40ToDiatonic(exprNote)
                        exprAccid = Convert.base40ToAccidental(exprNote)
                        if dstates[spineStartIdx][exprDiatonic] != exprAccid:
                            token.setValue(
                                'auto', str(k), 'mordentLowerAccidental', str(exprAccid))
                            # if we ever get ornament accidentals displaying, put this next
                            # line back in.
                            # dstates[spineStartIdx][exprDiatonic] = -1000 + exprAccid
                    elif '$' in subtok:
                        # inverted turn
                        loc = subtok.find('$')
                        exprDiatonic = Convert.base40ToDiatonic(b40)
                        lowerInt = 0
                        upperInt = 0
                        if loc < len(subtok) - 1:
                            if subtok[loc + 1] == 's':
                                lowerInt = -5
                            elif subtok[loc + 1] == 'S':
                                lowerInt = -6

                        if loc < len(subtok) - 2:
                            if subtok[loc + 2] == 's':
                                upperInt = 5
                            elif subtok[loc + 2] == 'S':
                                upperInt = 6

                        lowerDiatonic = exprDiatonic - 1
                        # Maybe also need to check for forced accidental state...
                        lowerAccid = dstates[spineStartIdx][lowerDiatonic]
                        lowerb40 = Convert.base7ToBase40(lowerDiatonic) + lowerAccid
                        upperDiatonic = exprDiatonic + 1
                        # Maybe also need to check for forced accidental state...
                        upperAccid = dstates[spineStartIdx][upperDiatonic]
                        upperb40 = Convert.base7ToBase40(upperDiatonic) + upperAccid

                        if lowerInt == 0:
                            # need to calculate lower interval (but it will not appear
                            # below the inverted turn, just calculating for performance
                            # rendering.
                            lowerInt = lowerb40 + b40
                            lowerb40 = b40 + lowerInt

                        if upperInt == 0:
                            # need to calculate upper interval (but it will not appear
                            # above the inverted turn, just calculating for performance
                            # rendering.
                            upperInt = upperb40 - b40
                            upperb40 = b40 + upperInt

                        uacc = Convert.base40ToAccidental(b40 + upperInt)
                        bacc = Convert.base40ToAccidental(b40 + lowerInt)
                        if uacc != upperAccid:
                            token.setValue(
                                'auto', str(k), 'turnUpperAccidental', str(uacc))
                            # if we ever get ornament accidentals displaying, put this next
                            # line back in.
                            # dstates[spineStartIdx][exprDiatonic] = -1000 + uacc

                        if bacc != lowerAccid:
                            token.setValue(
                                'auto', str(k), 'turnUpperAccidental', str(bacc))
                            # if we ever get ornament accidentals displaying, put this next
                            # line back in.
                            # dstates[spineStartIdx][exprDiatonic] = -1000 + bacc
                    elif 'S' in subtok:
                        # regular turn
                        loc = subtok.find('S')
                        exprDiatonic = Convert.base40ToDiatonic(b40)
                        lowerInt = 0
                        upperInt = 0
                        if loc < len(subtok) - 1:
                            if subtok[loc + 1] == 's':
                                upperInt = 5
                            elif subtok[loc + 1] == 'S':
                                upperInt = 6

                        if loc < len(subtok) - 2:
                            if subtok[loc + 2] == 's':
                                lowerInt = -5
                            elif subtok[loc + 2] == 'S':
                                lowerInt = -6

                        lowerDiatonic = exprDiatonic - 1
                        # Maybe also need to check for forced accidental state...
                        lowerAccid = dstates[spineStartIdx][lowerDiatonic]
                        lowerb40 = Convert.base7ToBase40(lowerDiatonic) + lowerAccid
                        upperDiatonic = exprDiatonic + 1
                        # Maybe also need to check for forced accidental state...
                        upperAccid = dstates[spineStartIdx][upperDiatonic]
                        upperb40 = Convert.base7ToBase40(upperDiatonic) + upperAccid

                        if lowerInt == 0:
                            # need to calculate lower interval (but it will not appear
                            # below the inverted turn, just calculating for performance
                            # rendering.
                            lowerInt = lowerb40 + b40
                            lowerb40 = b40 + lowerInt

                        if upperInt == 0:
                            # need to calculate upper interval (but it will not appear
                            # above the inverted turn, just calculating for performance
                            # rendering.
                            upperInt = upperb40 - b40
                            upperb40 = b40 + upperInt

                        uacc = Convert.base40ToAccidental(b40 + upperInt)
                        bacc = Convert.base40ToAccidental(b40 + lowerInt)
                        if uacc != upperAccid:
                            token.setValue(
                                'auto', str(k), 'turnUpperAccidental', str(uacc))
                            # if we ever get ornament accidentals displaying, put this next
                            # line back in.
                            # dstates[spineStartIdx][exprDiatonic] = -1000 + uacc

                        if bacc != lowerAccid:
                            token.setValue(
                                'auto', str(k), 'turnUpperAccidental', str(bacc))
                            # if we ever get ornament accidentals displaying, put this next
                            # line back in.
                            # dstates[spineStartIdx][exprDiatonic] = -1000 + bacc

                    if isGrace and accid != gdstates[spineStartIdx][diatonic]:
                        # accidental is different from the previous state so should be
                        # printed
                        if not isHidden:
                            token.setValue('auto', str(k), 'visualAccidental', 'true')
                            if gdstates[spineStartIdx][diatonic] < -900:
                                # this is an obligatory cautionary accidental
                                token.setValue('auto', str(k), 'cautionaryAccidental', 'true')
                        gdstates[spineStartIdx][diatonic] = accid
                        # regular notes are note affected by grace notes accidental
                        # changes, but should have an obligatory cautionary accidental,
                        # displayed for clarification.
                        dstates[spineStartIdx][diatonic] = -1000 + accid

                    elif (not isGrace and (
                            (concurrentState[diatonic]
                                and concurrentState[diatonic] == accid)
                            or accid != dstates[spineStartIdx][diatonic])):
                        if not isHidden:
                            token.setValue('auto', str(k), 'visualAccidental', 'true')
                            concurrentState[diatonic] = accid
                            if dstates[spineStartIdx][diatonic] < -900:
                                # this is an obligatory cautionary accidental
                                token.setValue('auto', str(k), 'cautionaryAccidental', 'true')
                        dstates[spineStartIdx][diatonic] = accid
                        gdstates[spineStartIdx][diatonic] = accid

                    elif accid == 0 and 'n' in subtok and not isHidden:
                        # if humdrum data specifies 'n', we'll put in a cautionary accidental
                        token.setValue('auto', str(k), 'cautionaryAccidental', 'true')
                        token.setValue('auto', str(k), 'visualAccidental', 'true')

                    elif 'XX' not in subtok:
                        # The accidental is not necessary. See if there is a single "X"
                        # immediately after the accidental which means to force it to
                        # display.
                        if '#X' in subtok or '-X' in subtok or 'nX' in subtok:
                            token.setValue('auto', str(k), 'cautionaryAccidental', 'true')
                            token.setValue('auto', str(k), 'visualAccidental', 'true')

                    # editorialAccidental analysis
                    isEditorial: bool = False
                    editType: str = ''
                    for x, signifier in enumerate(self._signifiers.editorialAccidentals):
                        if signifier in subtok:
                            isEditorial = True
                            editType = self._signifiers.editorialAccidentalTypes[x]
                            break

                    subTokenIdx: int = k
                    if len(token.subtokens) == 1:
                        subTokenIdx = -1
                    editType2: str = token.layoutParameter('A', 'edit', subTokenIdx)
                    if editType2 and not editType:
                        isEditorial = True
                        if editType2 == 'true':
                            # default editorial accidental type
                            editType = ''
                            # use the first editorial accidental RDF style in file if present
                            if self._signifiers.editorialAccidentalTypes:
                                editType = self._signifiers.editorialAccidentalTypes[0]
                        else:
                            editType = editType2

                    if isEditorial:
                        token.setValue('auto', str(k), 'editorialAccidental', 'true')
                        token.setValue('auto', str(k), 'visualAccidental', 'true')
                        if editType:
                            token.setValue('auto', str(k), 'editorialAccidentalStyle', editType)

                    # layout parameters (('N', 'acc') and ('A', 'vis')) can also be used
                    # to specify a specific accidental or combination to be made visible.
                    # 'A', 'vis' takes priority over 'N', 'acc', if both are present
                    layoutAccidental: str = token.layoutParameter('A', 'vis', subTokenIdx)
                    if not layoutAccidental:
                        layoutAccidental = token.layoutParameter('N', 'acc', subTokenIdx)
                    if layoutAccidental:
                        token.setValue('auto', str(k), 'cautionaryAccidental', layoutAccidental)
                        token.setValue('auto', str(k), 'visualAccidental', layoutAccidental)

            firstInBar = [False] * spineStartCount

        # Indicate that the accidental analysis has been done:
        self.setValue('auto', 'accidentalAnalysis', 'true')

        return True

    @staticmethod
    def fillKeySignature(keysig: t.List[int], ks_tstring: str):
        for i in range(0, len(keysig)):
            keysig[i] = 0

        if 'f#' in ks_tstring:
            keysig[3] = 1
        if 'c#' in ks_tstring:
            keysig[0] = 1
        if 'g#' in ks_tstring:
            keysig[4] = 1
        if 'd#' in ks_tstring:
            keysig[1] = 1
        if 'a#' in ks_tstring:
            keysig[5] = 1
        if 'e#' in ks_tstring:
            keysig[2] = 1
        if 'b#' in ks_tstring:
            keysig[6] = 1
        if 'b-' in ks_tstring:
            keysig[6] = -1
        if 'e-' in ks_tstring:
            keysig[2] = -1
        if 'a-' in ks_tstring:
            keysig[5] = -1
        if 'd-' in ks_tstring:
            keysig[1] = -1
        if 'g-' in ks_tstring:
            keysig[4] = -1
        if 'c-' in ks_tstring:
            keysig[0] = -1
        if 'f-' in ks_tstring:
            keysig[3] = -1

    @staticmethod
    def resetDiatonicStatesWithKeySignature(states: t.List[int], keysig: t.List[int]):
        for i in range(0, len(states)):
            states[i] = keysig[i % 7]

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::analyzeOttavas --

        analyzeOttavas reads any 8va-type data, and makes a note of it in each affected token.
    '''
    def analyzeOttavas(self) -> None:
        trackCount: int = self.maxTrack
        activeOttava: t.List[int] = [0] * (trackCount + 1)  # 0th element goes unused
        octaveState: t.List[int] = [0] * (trackCount + 1)   # 0th element goes unused

        ttrack: int

        for line in self._lines:
            if line.isInterpretation:
                for token in line.tokens():
                    if not token.isKern:
                        continue
                    ttrack = token.track
                    if token.text == '*8va':
                        octaveState[ttrack] = +1
                        activeOttava[ttrack] += 1
                    elif token.text == '*X8va':
                        octaveState[ttrack] = 0
                        activeOttava[ttrack] -= 1
                    elif token.text == '*8ba':
                        octaveState[ttrack] = -1
                        activeOttava[ttrack] += 1
                    elif token.text == '*X8ba':
                        octaveState[ttrack] = 0
                        activeOttava[ttrack] -= 1
                    elif token.text == '*15ma':
                        octaveState[ttrack] = +2
                        activeOttava[ttrack] += 1
                    elif token.text == '*X15ma':
                        octaveState[ttrack] = 0
                        activeOttava[ttrack] -= 1
                    elif token.text == '*15ba':
                        octaveState[ttrack] = -2
                        activeOttava[ttrack] += 1
                    elif token.text == '*X15ba':
                        octaveState[ttrack] = 0
                        activeOttava[ttrack] -= 1
            elif line.isData:
                for token in line.tokens():
                    if not token.isKern:
                        continue
                    ttrack = token.track
                    if activeOttava[ttrack] == 0:  # if nesting level is 0
                        continue
                    if octaveState[ttrack] == 0:  # if octave adjustment is 0
                        continue
                    if token.isNull:
                        continue
                    # do not exclude rests, since the vertical placement of the rest
                    # on the staff may need to be updated by the ottava mark.
                    # if token.isRest:
                    #     continue

                    token.setValue('auto', 'ottava', str(octaveState[ttrack]))

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::analyzeTextRepetition -- Look for *ij and *Xij markers
    //     that indicate repetition marks.  values added to text:
    //          auto/ij=true: the syllable is in an ij region.
    //          auto/ij-begin=true: the syllable is the first in an ij region.
    //          auto/ij-end=true: the syllable is the last in an ij region.
    //
    // Returns true if there are any *ij/*Xij markers in the data.
    '''
    def analyzeTextRepetition(self) -> None:
        spineStarts: t.List[t.Optional[HumdrumToken]] = self.spineStartList

        for start in spineStarts:
            ijstate: bool = False
            startij: bool = False
            lastIJToken: t.Optional[HumdrumToken] = None  # last token seen in ij range

            if start is None:
                raise HumdrumInternalError('start that is None found in spineStarts')

            # BUGFIX: **sylb -> **silbe
            if not start.isDataType('**text') and not start.isDataType('**silbe'):
                continue

            current: t.Optional[HumdrumToken] = start
            while current is not None:
                if current.isNull:
                    current = current.nextToken0
                    continue

                if current.isInterpretation:
                    if current.text == '*ij':
                        startij = True
                        ijstate = True
                    elif current.text == '*Xij':
                        startij = False
                        ijstate = False
                        if lastIJToken is not None:
                            lastIJToken.setValue('auto', 'ij-end', 'true')
                            lastIJToken = None
                    current = current.nextToken0
                    continue

                if current.isData:
                    if ijstate:
                        current.setValue('auto', 'ij', 'true')
                        if startij:
                            current.setValue('auto', 'ij-begin', 'true')
                            startij = False
                        lastIJToken = current

                current = current.nextToken0

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::analyzeRScale --
    '''
    def analyzeRScale(self) -> bool:
        numActiveTracks: int = 0  # number of tracks currently having an active rscale parameter
        rscales: t.List[HumNum] = [opFrac(1)] * (self.maxTrack + 1)
        ttrack: int

        for line in self._lines:
            if line.isInterpretation:
                for token in line.tokens():
                    if not token.isKern:
                        continue

                    if not token.text.startswith('*rscale:'):
                        continue

                    value: HumNum = opFrac(1)
                    m = re.search(r'\*rscale:(\d+)/(\d+)', token.text)
                    if m is not None:
                        top: int = int(m.group(1))
                        bot: int = int(m.group(2))
                        value = opFrac(Fraction(top, bot))
                    else:
                        m = re.search(r'\*rscale:(\d+)', token.text)
                        if m is not None:
                            top = int(m.group(1))
                            value = opFrac(top)

                    ttrack = token.track
                    if value == 1:
                        if rscales[ttrack] != 1:
                            rscales[ttrack] = opFrac(1)
                            numActiveTracks -= 1
                    else:
                        if rscales[ttrack] == 1:
                            numActiveTracks += 1
                        rscales[ttrack] = value
                continue

            if numActiveTracks == 0:
                continue

            if not line.isData:
                continue

            for token in line.tokens():
                ttrack = token.track
                if rscales[ttrack] == 1:
                    continue
                if not token.isKern:
                    continue
                if token.isNull:
                    continue
                if token.duration < 0:
                    continue

                dur: HumNum = opFrac(token.durationNoDots * rscales[ttrack])
                vis: str = Convert.durationToRecip(dur)
                vis += '.' * token.dotCount
                token.setValue('LO', 'N', 'vis', vis)

        return True

    '''
    //////////////////////////////
    //
    // HumdrumInput::initializeSpineColor -- Look for *color: interpretations before data.

        This only looks at the beginning of the file, before any data tokens.
        Later, we will update self._spineColor when necessary as we process the file.

    '''
    def initializeSpineColor(self) -> None:
        self._spineColor = [[''] * MAXCOLORSUBTRACK] * (self.maxTrack + 1)
        for line in self.lines():
            if line.isData:
                break

            if not line.isInterpretation:
                continue

            if '*color:' not in line.text:
                continue

            for token in line.tokens():
                self.setSpineColorFromColorInterpToken(token)

    '''
        setSpineColorFromColorInterpToken - factored from several places in HumdrumFileContent.py
        and HumdrumFile.py
    '''
    def setSpineColorFromColorInterpToken(self, token: HumdrumToken) -> None:
        m = re.search(r'^\*color:(.*)', token.text)
        if m:
            ctrack: t.Optional[int] = token.track
            strack: t.Optional[int] = token.subTrack
            if ctrack is None or strack is None:
                return
            if strack < MAXCOLORSUBTRACK:
                self._spineColor[ctrack][strack] = m.group(1)
                if strack == 1:
                    # copy it to subtrack 0 as well
                    self._spineColor[ctrack][0] = m.group(1)
                elif strack == 0:
                    # copy it to all subtracks
                    for z in range(1, MAXCOLORSUBTRACK):
                        self._spineColor[ctrack][z] = m.group(1)

    '''
    //////////////////////////////
    //
    // HumdrumFileContent::hasPickup -- Return false if there is no pickup measure.
    //   Return the barline index number if there is a pickup measure.  A pickup measure
    //   is identified when the duration from the start of the file to the first
    //   barline is not zero or equal to the duration of the starting time signature.
    //   if there is not starting time signature, then there cannot be an identified
    //   pickup measure.
    '''
    def hasPickup(self) -> int:
        barlineIdx: int = -1
        tsig: t.Optional[HumdrumToken] = None

        for i, line in enumerate(self._lines):
            if line.isBarline:
                if barlineIdx > 0:
                    # second barline found, so stop looking for time signature
                    break
                barlineIdx = i
                continue

            if not line.isInterpretation:
                continue

            if tsig is not None:
                continue

            for token in line.tokens():
                if token.isTimeSignature:
                    tsig = token
                    break

        if tsig is None:
            # no time signature so return 0
            return 0

        if barlineIdx < 0:
            # no barlines in music
            return 0

        mdur: HumNum = self._lines[barlineIdx].durationFromStart
        tdur: HumNum = Convert.timeSigToDuration(tsig)
        if mdur == tdur:
            # first measure is exactly as long as the time signature says: no pickup measure
            return 0

        return barlineIdx
