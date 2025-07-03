from pathlib import Path
import tempfile
import argparse
import sys
import subprocess
import json

from music21.base import VERSION_STR
import music21 as m21

from musicdiff import Visualization
from musicdiff.annotation import AnnScore
from musicdiff import Comparison
from musicdiff import DetailLevel

# The things we're testing
from converter21.shared import M21Utilities
import converter21

def getScoreList(scoreOrOpus: m21.stream.Score | m21.stream.Opus) -> list[m21.stream.Score]:
    if isinstance(scoreOrOpus, m21.stream.Score):
        return [scoreOrOpus]
    return list(scoreOrOpus.scores)

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

def runTheFullTest(inputPath: Path):
    print(f'Parsing ABC file: {inputPath}')
    score1 = m21.converter.parse(inputPath, format='abc', forceSource=True)

    assert score1 is not None
    assert score1.isWellFormedNotation()

    success: bool = True
    abcPath = Path(tempfile.gettempdir())
    abcPath /= (inputPath.stem + '_Written')
    abcPath = abcPath.with_suffix('.abc')
    print(f'Writing ABC file: {abcPath}')
    # Use Stream.write instead of Opus.write (which will incorrectly
    # split into multiple abc files, one per score)
    # success = score1.write(fp=abcPath, fmt='abc', makeNotation=False)
    success = m21.stream.Stream.write(score1, fp=abcPath, fmt='abc', makeNotation=False)
    assert success

    # compare with bbdiff:
    subprocess.run(['bbdiff', str(inputPath), str(abcPath)], check=False)

    print(f'Parsing written ABC file: {abcPath}')
    score2 = m21.converter.parse(abcPath, format='abc', forceSource=True)
    assert score2 is not None
    assert score2.isWellFormedNotation()

    # ABC importer/exporter can produce Score or Opus (full of scores).
    # So we make lists 1 and 2 of scores, and loop over them, comparing.
    score1List: list[m21.stream.Score] = getScoreList(score1)
    score2List: list[m21.stream.Score] = getScoreList(score2)
    padWithEmptyScores(score1List, score2List)

    for sc1, sc2 in zip(score1List, score2List):
        # compare the two music21 (ABC) scores
        # with music-score-diff:
        print('comparing the two m21/ABC scores')
        score_lin1 = AnnScore(
            sc1, DetailLevel.AllObjects | DetailLevel.Style | DetailLevel.Metadata
        )
        print('loaded imported ABC score')
        score_lin2 = AnnScore(
            sc2, DetailLevel.AllObjects | DetailLevel.Style | DetailLevel.Metadata
        )
        print('loaded exported ABC score')
        diffList, cost = Comparison.annotated_scores_diff(score_lin1, score_lin2)
        print('diffed the two scores:')
        numDiffs = len(diffList)
        print(f'\tnumber of differences = {numDiffs}')
        if numDiffs > 0:
            print('now we will mark and display the two scores')
            Visualization.mark_diffs(sc1, sc2, diffList)
            print('marked the scores to show differences')
            # Visualization.show_diffs(sc1, sc2)
            print('displayed both annotated scores')

        omrnedOut: dict[str, str] = Visualization.get_omr_ned_output(cost, score_lin1, score_lin2)
        jsonStr: str = json.dumps(omrnedOut)
        print(jsonStr)
        textOut: str = Visualization.get_text_output(sc1, sc2, diffList)
        if textOut:
            print(textOut)

        # print('imported ABC score written to: ', sc1.write('abc', makeNotation=False))
        # print('exported ABC score written to: ', sc2.write('abc', makeNotation=False))

    return

# ------------------------------------------------------------------------------

'''
    main entry point (parse arguments and do conversion)
'''
converter21.register()
converter21.M21Utilities.adjustMusic21Behavior()

parser = argparse.ArgumentParser()
parser.add_argument('input_file')
print('music21 version:', VERSION_STR, file=sys.stderr)
args = parser.parse_args()

runTheFullTest(Path(args.input_file))
