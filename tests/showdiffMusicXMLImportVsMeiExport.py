from pathlib import Path
import tempfile
import argparse
import sys
import subprocess

from music21.base import VERSION_STR
import music21 as m21

from musicdiff import Visualization
from musicdiff.annotation import AnnScore
from musicdiff import Comparison
from musicdiff import DetailLevel

# The things we're testing
from converter21.humdrum import HumdrumFile
from converter21.mei import MeiWriter
import converter21

def runTheFullTest(inputPath: Path):
    print(f'MusicXML file: {inputPath}')

    print(f'Parsing MusicXML file: {inputPath}')
    score1 = m21.converter.parse(inputPath, format='musicxml', forceSource=True)

    assert score1 is not None
    assert score1.isWellFormedNotation()

    meiw: MeiWriter = MeiWriter(score1)
    meiw.makeNotation = False

    success: bool = True
    meiwPath = Path(tempfile.gettempdir())
    meiwPath /= (inputPath.stem + '_Written')
    meiwPath = meiwPath.with_suffix('.mei')
    print(f'Writing MEI file: {meiwPath}')
    with open(meiwPath, 'wt') as f:
        success = meiw.write(f)

    assert success

    print(f'Parsing written MEI file: {meiwPath}')
    score2 = m21.converter.parse(meiwPath, format='mei', forceSource=True)
    assert score2 is not None
    assert score2.isWellFormedNotation()

    # compare the two music21 (MEI) scores
    # with music-score-diff:
    print('comparing the two m21/MEI scores')
    score_lin2 = AnnScore(score1, DetailLevel.AllObjectsWithStyleAndMetadata)
    print('loaded imported MEI score')
    score_lin3 = AnnScore(score2, DetailLevel.AllObjectsWithStyleAndMetadata)
    print('loaded exported MEI score')
    if score_lin2.n_of_parts != score_lin3.n_of_parts:
        print(f'numParts {score_lin2.n_of_parts} vs {score_lin3.n_of_parts}')
        return

    diffList, _cost = Comparison.annotated_scores_diff(score_lin2, score_lin3)
    print('diffed the two scores:')
    numDiffs = len(diffList)
    print(f'\tnumber of differences = {numDiffs}')
    if numDiffs > 0:
        print('now we will mark and display the two scores')
        Visualization.mark_diffs(score1, score2, diffList)
        print('marked the scores to show differences')
        Visualization.show_diffs(score1, score2)
        print('displayed both annotated scores')
#     print('imported MEI score written to: ', score1.write('musicxml', makeNotation=False))
#     print('exported MEI score written to: ', score2.write('musicxml', makeNotation=False))
    return

# ------------------------------------------------------------------------------

'''
    main entry point (parse arguments and do conversion)
'''
parser = argparse.ArgumentParser()
parser.add_argument('input_file')
print('music21 version:', VERSION_STR, file=sys.stderr)
args = parser.parse_args()

converter21.register()

runTheFullTest(Path(args.input_file))
