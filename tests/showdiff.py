from pathlib import Path
import tempfile
import argparse
import sys
import subprocess

from music21.base import VERSION_STR
from musicdiff import Visualization
from musicdiff.annotation import AnnScore
from musicdiff import Comparison
from musicdiff import DetailLevel

# The things we're testing
from converter21.humdrum import HumdrumFile
from converter21.humdrum import HumdrumWriter

def runTheFullTest(krnPath: Path):
    print(f'krn file: {krnPath}')

    # resultsFileName = krnPath.stem + '.json'
    # resultsPath = krnPath.parent / resultsFileName

    # import into HumdrumFile
    hfb = HumdrumFile(str(krnPath))
    assert hfb.isValid

    # test against known good results
    # results = HumdrumFileTestResults.fromFiles(str(krnPath), str(resultsPath))
    # CheckHumdrumFile(hfb, results)

    # import HumdrumFile into music21 stream
    score1 = hfb.createMusic21Stream()
    assert score1 is not None
    assert score1.isWellFormedNotation() or not score1.elements

    # export score back to humdrum (without any makeNotation fixups)

    # if the score is empty, exporting from it will not produce anything interesting
    if not score1.elements:
        print('\tskipping export of empty score')
        return

#     score1.show('musicxml.pdf')
#     xmlFile = score1.write('musicxml')
#     print(f'MusicXML written to {xmlFile}')

    hdw: HumdrumWriter = HumdrumWriter(score1)
    hdw.makeNotation = False
    hdw.addRecipSpine = krnPath.name == 'test-rhythms.krn'
    # hdw.expandTremolos = False

    success: bool = True
    fp = Path(tempfile.gettempdir()) / krnPath.name
    with open(fp, 'w', encoding='utf-8') as f:
        success = hdw.write(f)

#     if not success:
#         score1.show('musicxml.pdf')
    assert success

    # and then try to parse the exported humdrum file

    hfb2 = HumdrumFile(str(fp))
#     if not hfb2.isValid:
#         score1.show('musicxml.pdf')
    assert hfb2.isValid

    score2 = hfb2.createMusic21Stream()
#     if score2 is None or not score2.isWellFormedNotation():
#         score1.show('musicxml.pdf')
    assert score2 is not None
    assert score2.isWellFormedNotation()

#     score2.show('musicxml.pdf')

    # compare the two music21 scores

    # first with bbdiff:
    subprocess.run(['bbdiff', str(krnPath), str(fp)], check=False)

    # next with music-score-diff:
    print('comparing the two m21 scores')
    score_lin1 = AnnScore(score1, DetailLevel.AllObjectsWithStyle)
    print('loaded first score')
    score_lin2 = AnnScore(score2, DetailLevel.AllObjectsWithStyle)
    print('loaded second score')
    diffList, _cost = Comparison.annotated_scores_diff(score_lin1, score_lin2)
    print('diffed the two scores:')
    numDiffs = len(diffList)
    print(f'\tnumber of differences = {numDiffs}')
    if numDiffs > 0:
        print('now we will mark and display the two scores')
        Visualization.mark_diffs(score1, score2, diffList)
        print('marked the scores to show differences')
        Visualization.show_diffs(score1, score2)
        print('displayed both annotated scores')
#     print('score1 written to: ', score1.write('musicxml', makeNotation=False))
#     print('score2 written to: ', score2.write('musicxml', makeNotation=False))

# ------------------------------------------------------------------------------

'''
    main entry point (parse arguments and do conversion)
'''
parser = argparse.ArgumentParser()
parser.add_argument('input_file')
print('music21 version:', VERSION_STR, file=sys.stderr)
args = parser.parse_args()

runTheFullTest(Path(args.input_file))
