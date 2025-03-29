from pathlib import Path
import tempfile
import argparse
import sys
import json
import typing as t
import music21 as m21
from music21.base import VERSION_STR

from musicdiff.annotation import AnnScore, AnnExtra, AnnMetadataItem
from musicdiff import Comparison
from musicdiff import Visualization
from musicdiff import DetailLevel

# The things we're testing
import converter21
from converter21.mei import MeiWriter

from converter21.shared import M21Utilities

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

# returns True if the test passed (no musicdiff differences found)
def runTheDiff(inputPath: Path, results) -> bool:
    print(f'{inputPath}: ', end='')
    print(f'{inputPath}: ', end='', file=results)
    results.flush()

    # import into music21
    try:
        score1 = m21.converter.parse(inputPath, format='musicxml', forceSource=True)
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

    # Some MusicXML files have abbreviations instead of chordKinds (e.g. 'min' instead of
    # the correct 'minor').  Fix that before the diff is performed.
    M21Utilities.fixupBadChordKinds(score1, inPlace=True)

    # Some MusicXML files have beams that go 'start'/'continue' when they should be
    # 'start'/'stop'. fixupBadBeams notices that the next beam is a 'start', or is
    # not present at all, and therefore patches that 'continue' to be a 'stop'.
    M21Utilities.fixupBadBeams(score1, inPlace=True)

    # export score back to MEI (without any makeNotation fixups)

    meiw: MeiWriter = MeiWriter(score1)
    meiw.makeNotation = False

    try:
        success: bool = True
        meiwPath = Path(tempfile.gettempdir())
        meiwPath /= (inputPath.stem + '_Written')
        meiwPath = meiwPath.with_suffix('.mei')
        with open(meiwPath, 'wt') as f:
            success = meiw.write(f)
        if not success:
            print('export failed')
            print('export failed', file=results)
            results.flush()
            return False
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f'export crash: {e}')
        print(f'export crash: {e}', file=results)
        results.flush()
        return False

    # and then try to parse the exported MEI file
    try:
        score2 = m21.converter.parse(meiwPath, format='mei', forceSource=True)
        if score2 is None:
            print('score2 creation failure')
            print('score2 creation failure', file=results)
            results.flush()
            return False
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

    # use musicdiff to compare the two music21 scores,
    # and return whether or not they were identical
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

        # print OMR-NED dict even if there are no diffs
        omrnedOut: dict = Visualization.get_omr_ned_output(cost, annotatedScore1, annotatedScore2)
        jsonStr: str = json.dumps(omrnedOut)
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
            description='Loop over listfile (list of .musicxml files), importing and then exporting back to .mei, comparing original .musicxml with exported .mei.  Generate three output files (list_file.good.txt, list_file.bad.txt, list_file.results.txt) in the same folder as the list_file, where goodList.txt contains all the .musicxml file paths that had no musicdiff differences with their exported version, badList.txt contains the ones that failed, or had differences, and resultsList.txt contains every file with a note about what happened.')
parser.add_argument(
        'list_file',
        help='file containing a list of the .musicxml/.mxl files to compare (full paths)')

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
