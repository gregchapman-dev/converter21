import pytest
from pathlib import Path
import tempfile
import argparse
import sys
import subprocess
from music21.base import VERSION_STR

# The things we're testing
from converter21.humdrum import HumdrumFileBase
from converter21.humdrum import HumdrumFile
from converter21.humdrum import HumdrumWriter
from converter21.humdrum.HumdrumFileBase import getMergedSpineInfo

# music-score-diff lib
import lib.score_visualization as sv
import lib.NotationLinear as nlin
import lib.score_comparison_lib as scl


# The check routine that every test calls at least once
from tests.Utilities import CheckHumdrumFile, HumdrumFileTestResults

def runTheFullTest(krnPath: Path):
    print(f'krn file: {krnPath}')

    resultsFileName = krnPath.stem + '.json'
    resultsPath = krnPath.parent / resultsFileName

    # import into HumdrumFile
    hfb = HumdrumFile(str(krnPath))
    assert(hfb.isValid)

    # test against known good results
    results = HumdrumFileTestResults.fromFiles(str(krnPath), str(resultsPath))
    CheckHumdrumFile(hfb, results)

    # import HumdrumFile into music21 stream
    score1 = hfb.createMusic21Stream()
    assert(score1 is not None)
    assert(score1.isWellFormedNotation() or not score1.elements)

    # export score back to humdrum (without any makeNotation fixups)

    # if the score is empty, exporting from it will not produce anything interesting
    if not score1.elements:
        print('\tskipping export of empty score')
        return

    hdw: HumdrumWriter = HumdrumWriter(score1)
    hdw.makeNotation = False
    hdw.addRecipSpine = krnPath.name == 'test-rhythms.krn'

    success: bool = True
    fp = Path(tempfile.gettempdir()) / krnPath.name
    with open(fp, 'w') as f:
        success = hdw.write(f)

    assert(success)

    # and then try to parse the exported humdrum file

    hfb = HumdrumFile(str(fp))
    assert(hfb.isValid)

    score2 = hfb.createMusic21Stream()
    assert(score2 is not None)
    assert(score2.isWellFormedNotation())

    # compare the two music21 scores

    # first with bbdiff:
#    subprocess.run(['bbdiff', str(krnPath), str(fp)])

    # next with music-score-diff:
    print('comparing the two m21 scores')
    score_lin1 = nlin.Score(score1)
    print('loaded first score')
    score_lin2 = nlin.Score(score2)
    print('loaded second score')
    op_list, cost = scl.complete_scorelin_diff(score_lin1, score_lin2)
    print('diffed the two scores:')
    numDiffs = len(op_list)
    print(f'\tnumber of differences = {numDiffs}')
    if numDiffs > 0:
        print('now we will annotate and display the two scores')
        sv.annotate_differences(score1, score2, op_list)
        print('annotated the scores to show differences')
        sv.show_differences(score1, score2)
        print('displayed both annotated scores')

# ------------------------------------------------------------------------------

'''
    main entry point (parse arguments and do conversion)
'''
parser = argparse.ArgumentParser()
parser.add_argument('input_file')
print('music21 version:', VERSION_STR, file=sys.stderr)
args = parser.parse_args()

runTheFullTest(Path(args.input_file))
