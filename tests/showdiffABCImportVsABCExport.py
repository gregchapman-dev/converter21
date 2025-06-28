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
    success = score1.write(fp=abcPath, fmt='abc', makeNotation=False)

    assert success

    # compare with bbdiff:
    subprocess.run(['bbdiff', str(inputPath), str(abcPath)], check=False)

    print(f'Parsing written ABC file: {abcPath}')
    score2 = m21.converter.parse(abcPath, format='abc', forceSource=True)
    assert score2 is not None
    assert score2.isWellFormedNotation()

    # compare the two music21 (ABC) scores
    # with music-score-diff:
    print('comparing the two m21/ABC scores')
    score_lin2 = AnnScore(
        score1, DetailLevel.AllObjects | DetailLevel.Style | DetailLevel.Metadata
    )
    print('loaded imported ABC score')
    score_lin3 = AnnScore(
        score2, DetailLevel.AllObjects | DetailLevel.Style | DetailLevel.Metadata
    )
    print('loaded exported ABC score')
    diffList, cost = Comparison.annotated_scores_diff(score_lin2, score_lin3)
    print('diffed the two scores:')
    numDiffs = len(diffList)
    print(f'\tnumber of differences = {numDiffs}')
    if numDiffs > 0:
        print('now we will mark and display the two scores')
        Visualization.mark_diffs(score1, score2, diffList)
        print('marked the scores to show differences')
        Visualization.show_diffs(score1, score2)
        print('displayed both annotated scores')

    omrnedOut: dict[str, str] = Visualization.get_omr_ned_output(cost, score_lin2, score_lin3)
    jsonStr: str = json.dumps(omrnedOut)
    print(jsonStr)
    textOut: str = Visualization.get_text_output(score1, score2, diffList)
    if textOut:
        print(textOut)

#     print('imported ABC score written to: ', score1.write('abc', makeNotation=False))
#     print('exported ABC score written to: ', score2.write('abc', makeNotation=False))
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
