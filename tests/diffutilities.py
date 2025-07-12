from pathlib import Path
import tempfile
import sys
import subprocess
import json

from music21.base import VERSION_STR
import music21 as m21

from musicdiff import Visualization
from musicdiff.annotation import AnnScore
from musicdiff import Comparison
from musicdiff import DetailLevel

import converter21


# pylint: disable=useless-return

class DiffUtilities:
    @staticmethod
    def runShowDiff(
        inputPath: Path,
        inFmt: str,
        outFmt: str,
        outExt: str,
        writeUsingVerovio: bool = False,
        convertInputToMeiUsingVerovioBeforeReading: bool = False,
        scoreNum: int | None = None
    ):
        print('music21 version:', VERSION_STR, file=sys.stderr)
        converter21.register()

        if convertInputToMeiUsingVerovioBeforeReading:
            if inFmt != 'humdrum':
                raise Exception(
                    'convertInputToMeiUsingVerovioBeforeReading requires Humdrum input'
                )
            meiPath = Path(tempfile.gettempdir())
            meiPath /= inputPath.name
            meiPath = meiPath.with_suffix('.mei')
            print(f'Converting humdrum file: {inputPath} to mei using Verovio')
            subprocess.run(
                ['verovio', '-a', '-t', 'mei', '-o', str(meiPath), str(inputPath)],
                check=True,
                capture_output=True
            )

            print(f'Parsing Verovio-produced mei file: {meiPath}')
            # pretend we were passed this mei input file
            inputPath = meiPath
            inFmt = 'mei'
        else:
            print(f'Parsing {inFmt} file: {inputPath}')

        if inFmt == 'pickled':
            scoreOrOpus1 = m21.converter.thaw(inputPath)
        else:
            scoreOrOpus1 = m21.converter.parse(
                inputPath,
                format=inFmt,
                number=scoreNum,
                forceSource=True
            )

        assert isinstance(scoreOrOpus1, (m21.stream.Score, m21.stream.Opus))
        assert scoreOrOpus1.isWellFormedNotation()

        if inFmt in ('musicxml', 'mxl'):
            # Some MusicXML files have abbreviations instead of chordKinds (e.g. 'min' instead of
            # the correct 'minor').  Fix that before the diff is performed.
            M21Utilities.fixupBadChordKinds(scoreOrOpus1, inPlace=True)

            # Some MusicXML files have beams that go 'start'/'continue' when they should be
            # 'start'/'stop'. fixupBadBeams notices that the next beam is a 'start', or is
            # not present at all, and therefore patches that 'continue' to be a 'stop'.
            M21Utilities.fixupBadBeams(scoreOrOpus1, inPlace=True)

        if writeUsingVerovio:
            if inFmt != 'humdrum' or outFmt != 'mei':
                raise Exception(
                    'bad args: writeUsingVerovio requires Humdrum input and MEI output'
                )
            # convert Humdrum input file to MEI using Verovio
            writePath = Path(tempfile.gettempdir())
            writePath /= inputPath.name
            writePath = writePath.with_suffix('.mei')
            print(f'Writing mei file with Verovio: {writePath}')
            subprocess.run(
                ['verovio', '-a', '-t', 'mei', '-o', str(writePath), str(inputPath)],
                check=True,
                capture_output=True
            )
        else:
            success: bool = True
            writePath = Path(tempfile.gettempdir())
            writePath /= (inputPath.stem + '_Written')
            writePath = writePath.with_suffix(f'.{outExt}')
            print(f'Writing {outFmt} file: {writePath}')

            # Use Stream.write instead of Opus.write (which will incorrectly
            # split into multiple files, one per score)
            # success = score1.write(fp=writePath, fmt=outFmt, makeNotation=False)
            success = m21.stream.Stream.write(
                scoreOrOpus1, fp=writePath, fmt=outFmt, makeNotation=False
            )
            assert success

        if inFmt == outFmt and inFmt != 'mxl':
            # compare with bbdiff:
            subprocess.run(['bbdiff', str(inputPath), str(writePath)], check=False)

        print(f'Parsing written {outFmt} file: {writePath}')
        scoreOrOpus2 = m21.converter.parse(writePath, format=outFmt, forceSource=True)
        assert isinstance(scoreOrOpus2, m21.stream.Score | m21.stream.Opus)
        assert scoreOrOpus2.isWellFormedNotation()

        # Some converters can read/write Score or Opus (full of scores).
        # So we make lists 1 and 2 of scores, and loop over them, comparing.
        score1List: list[m21.stream.Score] = DiffUtilities.getScoreList(scoreOrOpus1)
        score2List: list[m21.stream.Score] = DiffUtilities.getScoreList(scoreOrOpus2)
        DiffUtilities.padWithEmptyScores(score1List, score2List)

        for i, (sc1, sc2) in enumerate(zip(score1List, score2List)):
            # compare the two music21 scores with musicdiff APIs:
            if len(score1List) == 1:
                print('comparing the two scores')
            else:
                print(f'comparing the two scores at index: {i}')
            score_lin1 = AnnScore(
                sc1, DetailLevel.AllObjects | DetailLevel.Style | DetailLevel.Metadata
            )
            print(f'loaded imported {inFmt} score')
            score_lin2 = AnnScore(
                sc2, DetailLevel.AllObjects | DetailLevel.Style | DetailLevel.Metadata
            )
            print(f'loaded exported {outFmt} score')

            diffList, cost = Comparison.annotated_scores_diff(score_lin1, score_lin2)
            print('diffed the two scores:')
            numDiffs = len(diffList)
            print(f'\tnumber of differences = {numDiffs}')
            if numDiffs > 0:
                # only render the first score diff to PDF
                if i == 0:
                    print('now we will mark and display the two scores')
                    Visualization.mark_diffs(sc1, sc2, diffList)
                    print('marked the scores to show differences')
                    Visualization.show_diffs(sc1, sc2)
                    print('displayed both annotated scores')

            omrnedOut: dict[str, str] = Visualization.get_omr_ned_output(
                cost, score_lin1, score_lin2
            )
            jsonStr: str = json.dumps(omrnedOut)
            print(jsonStr)

            textOut: str = Visualization.get_text_output(sc1, sc2, diffList)
            if textOut:
                print(textOut)

            # print(
            #     f'imported {inFmt} score written to: ',
            #     sc1.write('musicxml', makeNotation=False)
            # )
            # print(
            #     f'exported {outFmt} score written to: ',
            #     sc2.write('musicxml', makeNotation=False)
            # )

        return

    @staticmethod
    def getScoreList(scoreOrOpus: m21.stream.Score | m21.stream.Opus) -> list[m21.stream.Score]:
        if isinstance(scoreOrOpus, m21.stream.Score):
            return [scoreOrOpus]
        return list(scoreOrOpus.scores)

    @staticmethod
    def padWithEmptyScores(list1: list[m21.stream.Score], list2: list[m21.stream.Score]):
        if len(list1) == len(list2):
            return
        shortList: list[m21.stream.Score]
        longList: list[m21.stream.Score]
        if len(list1) > len(list2):
            shortList = list2
            longList = list1
        else:
            shortList = list1
            longList = list2
        numPad: int = len(longList) - len(shortList)
        for _ in range(0, numPad):
            shortList.append(m21.stream.Score())
