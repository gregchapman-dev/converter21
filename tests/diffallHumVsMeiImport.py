from pathlib import Path
import tempfile
import argparse
import sys
import json
import subprocess
import typing as t
import music21 as m21
from music21.base import VERSION_STR

from musicdiff.annotation import AnnScore, AnnExtra, AnnMetadataItem
from musicdiff import Comparison
from musicdiff import Visualization
from musicdiff import DetailLevel

import converter21
from converter21.humdrum import HumdrumFile
from converter21.humdrum import HumdrumWriter

def getM21ObjectById(theID: int, score: m21.stream.Score) -> m21.base.Music21Object:
    obj = score.recurse().getElementById(theID)
    return obj

def oplistSummary(
    op_list: list[tuple[str, t.Any, t.Any]],
    _score1: m21.stream.Score,
    _score2: m21.stream.Score
) -> str:
    output: str = ''
    counts: dict = {}

    # print(f'op_list = {op_list}', file=sys.stderr)

    counts['measure'] = 0
    counts['voice'] = 0
    counts['note'] = 0
    counts['space'] = 0
    counts['gracenote'] = 0
    counts['beam'] = 0
    counts['lyric'] = 0
    counts['accidental'] = 0
    counts['tuplet'] = 0
    counts['tie'] = 0
    counts['expression'] = 0
    counts['articulation'] = 0
    counts['notestyle'] = 0
    counts['stemdirection'] = 0
    counts['staffgroup'] = 0

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
        elif op[0] in ('editspace',
                        'insspace',
                        'delspace'):
            counts['space'] += 1
        elif op[0] in ('graceedit', 'graceslashedit'):
            counts['gracenote'] += 1
        elif op[0] in ('lyricins',
                        'lyricdel',
                        'lyricsub',
                        'lyricedit',
                        'lyricnumedit',
                        'lyricidedit',
                        'lyricoffsetedit',
                        'lyricstyleedit'):
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
        # staffgroup
        elif op[0] in ('staffgrpins',
                        'staffgrpdel',
                        'staffgrpsub',
                        'staffgrpnameedit',
                        'staffgrpabbreviationedit',
                        'staffgrpsymboledit',
                        'staffgrpbartogetheredit',
                        'staffgrppartindicesedit'):
            counts['staffgroup'] += 1
        # metadata
        elif op[0] == 'mditemdel':
            assert isinstance(op[1], AnnMetadataItem)
            key = 'MD:' + op[1].key
            if counts.get(key, None) is None:
                counts[key] = 0
            counts[key] += 1
        elif op[0] == 'mditemins':
            assert isinstance(op[2], AnnMetadataItem)
            key = 'MD:' + op[2].key
            if counts.get(key, None) is None:
                counts[key] = 0
            counts[key] += 1
        elif op[0] == 'mditemsub':
            assert isinstance(op[1], AnnMetadataItem)
            assert isinstance(op[2], AnnMetadataItem)
            if op[1].key != op[2].key:
                key = 'MD:' + op[1].key + '!=' + op[2].key
            else:
                key = 'MD:' + op[1].key
            if counts.get(key, None) is None:
                counts[key] = 0
            counts[key] += 1
        elif op[0] == 'mditemkeyedit':
            assert isinstance(op[1], AnnMetadataItem)
            assert isinstance(op[2], AnnMetadataItem)
            key = 'MD:' + op[1].key + '!=' + op[2].key
            if counts.get(key, None) is None:
                counts[key] = 0
            counts[key] += 1
        elif op[0] == 'mditemvalueedit':
            assert isinstance(op[1], AnnMetadataItem)
            assert isinstance(op[2], AnnMetadataItem)
            key = 'MD:' + op[1].key
            if counts.get(key, None) is None:
                counts[key] = 0
            counts[key] += 1
        elif op[0] == 'extradel':
            # op[1] only
            assert isinstance(op[1], AnnExtra)
            key = op[1].kind
            if counts.get(key, None) is None:
                counts[key] = 0
            counts[key] += 1
        elif op[0] == 'extrains':
            # op[2] only
            assert isinstance(op[2], AnnExtra)
            key = op[2].kind
            if counts.get(key, None) is None:
                counts[key] = 0
            counts[key] += 1
        elif op[0] in ('extrasub',
                       'extracontentedit',
                       'extrasymboledit',
                       'extrainfoedit',
                       'extraoffsetedit',
                       'extradurationedit'):
            # op[1] and op[2]
            assert isinstance(op[1], AnnExtra)
            assert isinstance(op[2], AnnExtra)
            key = op[1].kind
            if counts.get(key, None) is None:
                counts[key] = 0
            counts[key] += 1
        elif op[0] == 'extrastyleedit':
            # op[1] and op[2]
            assert isinstance(op[1], AnnExtra)
            assert isinstance(op[2], AnnExtra)
            key = op[1].kind + ':style'
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
    except Exception as e:
        print(f'HumdrumFile1 parse crash: {e}')
        print(f'HumdrumFile1 parse crash: {e}', file=results)
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
    except Exception as e:
        print(f'score1 creation crash: {e}')
        print(f'score1 creation crash: {e}', file=results)
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

    # use verovio to convert humdrum file to mei file

    try:
        meiPath = Path(tempfile.gettempdir())
        meiPath /= krnPath.name
        meiPath = meiPath.with_suffix('.2.mei')
        subprocess.run(
            ['verovio', '-a', '-t', 'mei', '-o', f'{meiPath}', str(krnPath)],
            check=True,
            capture_output=True
        )
    except KeyboardInterrupt:
        sys.exit(0)
    except:
        print('conversion to mei with verovio failed')
        print('conversion to mei with verovio failed', file=results)
        results.flush()
        return False

    # import the mei file into music21
    try:
        score2 = m21.converter.parse(meiPath, format='mei', forceSource=True)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f'score2 creation crash: {e}')
        print(f'score2 creation crash: {e}', file=results)
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
    # and return whether or not they were identical. Disable
    # rest position comparison, since verovio makes them up.
    try:
        annotatedScore1 = AnnScore(
            score1,
            DetailLevel.AllObjects | DetailLevel.Style | DetailLevel.Metadata
        )
        annotatedScore2 = AnnScore(
            score2,
            DetailLevel.AllObjects | DetailLevel.Style | DetailLevel.Metadata
        )

        op_list, cost = Comparison.annotated_scores_diff(
                                        annotatedScore1, annotatedScore2)
        numDiffs = len(op_list)
        print(f'numDiffs = {numDiffs}')
        print(f'numDiffs = {numDiffs}', file=results)
        results.flush()
        if numDiffs > 0:
            summ: str = '\t' + oplistSummary(op_list, score1, score2)
            print(summ)
            print(summ, file=results)

        # print SER dict even if there are no diffs
        serOut: dict = Visualization.get_ser_output(cost, annotatedScore2)
        jsonStr: str = json.dumps(serOut)
        print(jsonStr)
        print(jsonStr, file=results)

        textOut: str = Visualization.get_text_output(score1, score2, op_list)
        if textOut:
            print(textOut)
            print(textOut, file=results)
            results.flush()

        if numDiffs > 0:
            return False
        return True
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f'musicdiff crashed: {e}')
        print(f'musicdiff crashed: {e}', file=results)
        results.flush()
        return False
    return True

# ------------------------------------------------------------------------------

'''
    main entry point (parse arguments and do conversion)
'''
converter21.M21Utilities.adjustMusic21Behavior()

parser = argparse.ArgumentParser(
            description='Loop over listfile (list of .krn files), importing and then exporting back to .krn, comparing original .krn with exported .krn.  Generate three output files (list_file.good.txt, list_file.bad.txt, list_file.results.txt) in the same folder as the list_file, where goodList.txt contains all the .krn file paths that had no music-score-diff differences with their exported version, badList.txt contains the ones that failed, or had differences, and resultsList.txt contains every file with a note about what happened.')
parser.add_argument(
        'list_file',
        help='file containing a list of the .krn files to compare (full paths)')

print('music21 version:', VERSION_STR, file=sys.stderr)
args = parser.parse_args()

converter21.register()

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
