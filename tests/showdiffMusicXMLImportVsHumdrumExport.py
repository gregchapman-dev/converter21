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
from converter21.humdrum import HumdrumWriter
import converter21

def runTheFullTest(inputPath: Path):
    print(f'MusicXML file: {inputPath}')

    print(f'Parsing MusicXML file: {inputPath}')
    score1 = m21.converter.parse(inputPath, format='musicxml', forceSource=True)

    assert score1 is not None
    assert score1.isWellFormedNotation()

    humdrumw: HumdrumWriter = HumdrumWriter(score1)
    humdrumw.makeNotation = False

    success: bool = True
    humdrumwPath = Path(tempfile.gettempdir())
    humdrumwPath /= (inputPath.stem + '_Written')
    humdrumwPath = humdrumwPath.with_suffix('.krn')
    print(f'Writing Humdrum file: {humdrumwPath}')
    with open(humdrumwPath, 'wt') as f:
        success = humdrumw.write(f)

    assert success

    print(f'Parsing written Humdrum file: {humdrumwPath}')
    score2 = m21.converter.parse(humdrumwPath, format='humdrum', forceSource=True)
    assert score2 is not None
    assert score2.isWellFormedNotation()

    # compare the two music21 (Humdrum) scores
    # with music-score-diff:
    print('comparing the two music21 scores')
    score_lin2 = AnnScore(score1, DetailLevel.AllObjectsWithStyleAndMetadata)
    print('loaded imported MusicXML score')
    score_lin3 = AnnScore(score2, DetailLevel.AllObjectsWithStyleAndMetadata)
    print('loaded exported Humdrum score')
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
#     print('imported MusicXML score written to: ', score1.write('musicxml', makeNotation=False))
#     print('exported Humdrum score written to: ', score2.write('musicxml', makeNotation=False))
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