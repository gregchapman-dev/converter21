from pathlib import Path
import tempfile
import argparse
import sys
from typing import List, Tuple
import music21 as m21
from music21.base import VERSION_STR

from musicdiff.annotation import AnnScore, AnnExtra
from musicdiff import Comparison
from musicdiff import DetailLevel

# The things we're testing
from converter21.humdrum import HumdrumFile
from converter21.humdrum import HumdrumWriter

def getM21ObjectById(theID: int, score: m21.stream.Score) -> m21.base.Music21Object:
    obj = score.recurse().getElementById(theID)
    return obj

def oplistSummary(op_list: List[Tuple[str]], _score1: m21.stream.Score, _score2: m21.stream.Score) -> str:
    output: str = ''
    counts: dict = {}

    # print(f'op_list = {op_list}', file=sys.stderr)

    counts['measure'] = 0
    counts['voice'] = 0
    counts['note'] = 0
    counts['beam'] = 0
    counts['lyric'] = 0
    counts['accidental'] = 0
    counts['tuplet'] = 0
    counts['tie'] = 0
    counts['expression'] = 0
    counts['articulation'] = 0
    counts['notestyle'] = 0
    counts['stemdirection'] = 0

    for op in op_list:
        # measure
        if op[0] in ('insbar', 'delbar'):
            counts['measure'] += 1
        # voice
        elif op[0] in ('voiceins', 'voicedel'):
            counts['voice'] += 1
        # note
        elif op[0] in ('noteins',
                        'notedel',
                        'pitchnameedit',
                        'inspitch',
                        'delpitch',
                        'headedit',
                        'dotins',
                        'dotdel'):
            counts['note'] += 1
        elif op[0] in ('inslyric',
                        'dellyric',
                        'editlyric'):
            counts['lyric'] += 1
        elif op[0] in ('editstyle',
                       'editnoteshape',
                       'editnoteheadfill',
                       'editnoteheadparenthesis'):
            counts['notestyle'] += 1
        elif op[0] in ('editstemdirection'):
            counts['stemdirection'] += 1
        # beam
        elif op[0] in ('insbeam',
                        'delbeam',
                        'editbeam'):
            counts['beam'] += 1
        # accidental
        elif op[0] in ('accidentins',
                        'accidentdel',
                        'accidentedit'):
            counts['accidental'] += 1
        # tuplet
        elif op[0] in ('instuplet',
                        'deltuplet',
                        'edittuplet'):
            counts['tuplet'] += 1
        # tie
        elif op[0] in ('tieins',
                        'tiedel'):
            counts['tie'] += 1
        # expression
        elif op[0] in ('insexpression',
                        'delexpression',
                        'editexpression'):
            counts['expression'] += 1
        # articulation
        elif op[0] in ('insarticulation',
                        'delarticulation',
                        'editarticulation'):
            counts['articulation'] += 1

        elif op[0] == 'extradel':
            # op[1] only
            assert isinstance(op[1], AnnExtra)
            key = op[1].content
            if counts.get(key, None) is None:
                counts[key] = 0
            counts[key] += 1
        elif op[0] == 'extrains':
            # op[2] only
            assert isinstance(op[2], AnnExtra)
            key = op[2].content
            if counts.get(key, None) is None:
                counts[key] = 0
            counts[key] += 1
        elif op[0] in ('extrasub',
                       'extracontentedit',
                       'extraoffsetedit',
                       'extradurationedit'):
            # op[1] and op[2]
            assert isinstance(op[1], AnnExtra)
            assert isinstance(op[2], AnnExtra)
            key = op[1].content # a little weird for "extracontentedit", but that's pretty rare
            if counts.get(key, None) is None:
                counts[key] = 0
            counts[key] += 1
        elif op[0] == 'extrastyleedit':
            # op[1] and op[2]
            assert isinstance(op[1], AnnExtra)
            assert isinstance(op[2], AnnExtra)
            key = op[1].content + ':style'
            if counts.get(key, None) is None:
                counts[key] = 0
            counts[key] += 1


    firstDone: bool = False
    for k, v in counts.items():
        if v == 0:
            continue

        if firstDone:
            output += f', {k}:{v}'
        else:
            output += f'{k}:{v}'
            firstDone = True

    return output

# returns True if the test passed (no music-score-diff differences found)
def runTheDiff(krnPath: Path, results) -> bool:
    print(f'{krnPath}: ', end='')
    print(f'{krnPath}: ', end='', file=results)
    results.flush()

    # import into HumdrumFile
    try:
        hfb = HumdrumFile(str(krnPath))
        if not hfb.isValid:
            print('HumdrumFile1 parse failure')
            print('HumdrumFile1 parse failure', file=results)
            results.flush()
            return False
    except KeyboardInterrupt:
        sys.exit(0)
    except:
        print('HumdrumFile1 parse crash')
        print('HumdrumFile1 parse crash', file=results)
        results.flush()
        return False

    # import HumdrumFile into music21 stream
    try:
        score1 = hfb.createMusic21Stream()
        if score1 is None:
            print('score1 creation failure')
            print('score1 creation failure', file=results)
            results.flush()
            return False
    except KeyboardInterrupt:
        sys.exit(0)
    except:
        print('score1 creation crash')
        print('score1 creation crash', file=results)
        results.flush()
        return False

    if not score1.elements:
        # empty score is valid result, but assume diff will be exact
        # (export of empty score fails miserably)
        print('numDiffs = 0 (empty score1)')
        print('numDiffs = 0 (empty score1)', file=results)
        results.flush()
        return True

    if not score1.isWellFormedNotation():
        print('score1 not well formed')
        print('score1 not well formed', file=results)
        results.flush()
        return False

    # export score back to humdrum (without any makeNotation fixups)

    hdw: HumdrumWriter = HumdrumWriter(score1)
    hdw.makeNotation = False
    hdw.addRecipSpine = krnPath.name == 'test-rhythms.krn'
    # hdw.expandTremolos = False

    try:
        success: bool = True
        fp = Path(tempfile.gettempdir()) / krnPath.name
        with open(fp, 'w', encoding='utf-8') as f:
            success = hdw.write(f)
        if not success:
            print('export failed')
            print('export failed', file=results)
            results.flush()
            return False
    except KeyboardInterrupt:
        sys.exit(0)
    except:
        print('export crash')
        print('export crash', file=results)
        results.flush()
        return False

    # and then try to parse the exported humdrum file
    try:
        hfb2 = HumdrumFile(str(fp))
        if not hfb2.isValid:
            print('HumdrumFile2 parse failure')
            print('HumdrumFile2 parse failure', file=results)
            results.flush()
            return False
    except KeyboardInterrupt:
        sys.exit(0)
    except:
        print('HumdrumFile2 parse crash')
        print('HumdrumFile2 parse crash', file=results)
        results.flush()
        return False

    try:
        score2 = hfb2.createMusic21Stream()
        if score2 is None:
            print('score2 creation failure')
            print('score2 creation failure', file=results)
            results.flush()
            return False
    except KeyboardInterrupt:
        sys.exit(0)
    except:
        print('score2 creation crash')
        print('score2 creation crash', file=results)
        results.flush()
        return False

    if not score2.elements:
        print('score2 was empty')
        print('score2 was empty', file=results)
        results.flush()
        return False # empty score2 is bad, because score1 was not empty

    if not score2.isWellFormedNotation():
        print('score2 not well formed')
        print('score2 not well formed', file=results)
        results.flush()
        return False

    # use music-score-diff to compare the two music21 scores,
    # and return whether or not they were identical
    try:
        annotatedScore1 = AnnScore(score1, DetailLevel.AllObjectsWithStyle)
        annotatedScore2 = AnnScore(score2, DetailLevel.AllObjectsWithStyle)
        op_list, _cost = Comparison.annotated_scores_diff(
                                        annotatedScore1, annotatedScore2)
        numDiffs = len(op_list)
        print(f'numDiffs = {numDiffs}')
        print(f'numDiffs = {numDiffs}', file=results)
        results.flush()
        if numDiffs > 0:
            summ: str = '\t' + oplistSummary(op_list, score1, score2)
            print(summ)
            print(summ, file=results)
            results.flush()
            return False
        return True
    except KeyboardInterrupt:
        sys.exit(0)
    except:
        print('musicdiff crashed')
        print('musicdiff crashed', file=results)
        results.flush()
        return False
    return True

# ------------------------------------------------------------------------------

'''
    main entry point (parse arguments and do conversion)
'''
parser = argparse.ArgumentParser(
            description='Loop over listfile (list of .krn files), importing and then exporting back to .krn, comparing original .krn with exported .krn.  Generate three output files (list_file.good.txt, list_file.bad.txt, list_file.results.txt) in the same folder as the list_file, where goodList.txt contains all the .krn file paths that had no music-score-diff differences with their exported version, badList.txt contains the ones that failed, or had differences, and resultsList.txt contains every file with a note about what happened.')
parser.add_argument(
        'list_file',
        help='file containing a list of the .krn files to compare (full paths)')

print('music21 version:', VERSION_STR, file=sys.stderr)
args = parser.parse_args()

listPath: Path = Path(args.list_file)
goodPath: Path = Path(str(listPath.parent) + '/' + str(listPath.stem)
                        + '.goodList.txt')
badPath: Path = Path(str(listPath.parent) + '/' + str(listPath.stem)
                        + '.badList.txt')
resultsPath: Path = Path(str(listPath.parent) + '/' + str(listPath.stem)
                        + '.resultsList.txt')

fileList: [str] = []
with open(listPath, encoding='utf-8') as listf:
    s: str = listf.read()
    fileList = s.split('\n')

with open(goodPath, 'w', encoding='utf-8') as goodf:
    with open(badPath, 'w', encoding='utf-8') as badf:
        with open(resultsPath, 'w', encoding='utf-8') as resultsf:
            for i, file in enumerate(fileList):
                if not file or file[0] == '#':
                    # blank line, or commented out
                    print(file)
                    print(file, file=resultsf)
                    resultsf.flush()
                    continue

#                 if file != '/Users/gregc/Documents/test/humdrum_beethoven_piano_sonatas/kern/sonata02-3.krn':
#                     continue

                if runTheDiff(Path(file), resultsf):
                    resultsf.flush()
                    print(file, file=goodf)
                    goodf.flush()
                else:
                    resultsf.flush()
                    print(file, file=badf)
                    badf.flush()
            resultsf.flush()
        badf.flush()
    goodf.flush()

print('done.')
