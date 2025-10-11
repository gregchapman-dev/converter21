import typing as t
from pathlib import Path
import tempfile
import sys
import subprocess
import json
import random

from io import TextIOWrapper

from music21.base import VERSION_STR
import music21 as m21

from musicdiff import Visualization
from musicdiff.annotation import AnnScore, AnnMetadataItem, AnnExtra
from musicdiff import Comparison
from musicdiff import DetailLevel

import converter21
from converter21 import M21Utilities


# pylint: disable=useless-return
# pylint: disable=broad-exception-raised

DEFAULT_DETAIL_LEVEL: int = DetailLevel.AllObjects | DetailLevel.Style | DetailLevel.Metadata

class DiffUtilities:

    @staticmethod
    def runShowDiff(
        inputPath: Path,
        inFmt: str,
        outFmt: str,
        outExt: str,
        writeUsingVerovio: bool = False,
        convertInputToMeiUsingVerovioBeforeReading: bool = False,
        exportMeiMultiScoreHostTag: str = 'mei',  # default to match old results
        detail: DetailLevel | int = DEFAULT_DETAIL_LEVEL,
        scoreNum: int | None = None
    ):
        print('music21 version:', VERSION_STR, file=sys.stderr)
        converter21.register()

        if not inFmt:
            # figure it out from inputPath's file extension
            c = m21.converter.Converter()
            inFmt = c.getFormatFromFileExtension(inputPath)

        verovioCompatibleImport: bool = (
            writeUsingVerovio or convertInputToMeiUsingVerovioBeforeReading
        )

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
                ['verovio', '-a', '-f', inFmt, '-t', 'mei', '-o', str(meiPath), str(inputPath)],
                check=True,
                capture_output=True
            )

            print(f'Parsing Verovio-produced mei file: {meiPath}')
            # pretend we were passed this mei input file
            inputPath = meiPath
            inFmt = 'mei'
        elif inFmt:
            print(f'Parsing {inFmt} file: {inputPath}')

        if inFmt == 'pickled':
            scoreOrOpus1 = m21.converter.thaw(inputPath)
        else:
            scoreOrOpus1 = m21.converter.parse(
                inputPath,
                format=inFmt,
                # number=scoreNum,
                forceSource=True,
                verovioCompatibleImport=verovioCompatibleImport
            )

        assert isinstance(scoreOrOpus1, (m21.stream.Score, m21.stream.Opus))
        assert scoreOrOpus1.isWellFormedNotation()

        if inFmt in ('musicxml', 'mxl'):
            # We know that MusicXML files can only contain one score.
            if t.TYPE_CHECKING:
                assert isinstance(scoreOrOpus1, m21.stream.Score)

            # Some MusicXML files have abbreviations instead of chordKinds (e.g. 'min' instead of
            # the correct 'minor').  Fix that before the diff is performed.
            M21Utilities.fixupBadChordKinds(scoreOrOpus1, inPlace=True)

            # Some MusicXML files have beams that go 'start'/'continue' when they should be
            # 'start'/'stop'. fixupBadBeams notices that the next beam is a 'start', or is
            # not present at all, and therefore patches that 'continue' to be a 'stop'.
            M21Utilities.fixupBadBeams(scoreOrOpus1, inPlace=True)

        if writeUsingVerovio:
            if inFmt not in ('humdrum', 'abc') or outFmt != 'mei':
                raise Exception(
                    'bad args: writeUsingVerovio requires Humdrum or ABC input and MEI output'
                )
            # convert Humdrum input file to MEI using Verovio
            writePath = Path(tempfile.gettempdir())
            writePath /= inputPath.name
            writePath = writePath.with_suffix('.mei')
            print(f'Writing mei file with Verovio: {writePath}')
            subprocess.run(
                ['verovio', '-a', '-f', inFmt, '-t', 'mei', '-o', str(writePath), str(inputPath)],
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
            # success = scoreOrOpus1.write(fp=writePath, fmt=outFmt, makeNotation=False)
            if outFmt == 'mei':
                success = m21.stream.Stream.write(
                    scoreOrOpus1,
                    fp=writePath,
                    fmt=outFmt,
                    makeNotation=False,
                    multipleScoresHostTag=exportMeiMultiScoreHostTag
                )
            else:
                success = m21.stream.Stream.write(
                    scoreOrOpus1,
                    fp=writePath,
                    fmt=outFmt,
                    makeNotation=False
                )
            assert success

        if inFmt == outFmt and inFmt != 'mxl':
            # compare with bbdiff:
            subprocess.run(['bbdiff', str(inputPath), str(writePath)], check=False)

        print(f'Parsing written {outFmt} file: {writePath}')
        scoreOrOpus2 = m21.converter.parse(
            writePath,
            format=outFmt,
            forceSource=True,
            number=scoreNum,
            verovioCompatibleImport=verovioCompatibleImport
        )
        assert isinstance(scoreOrOpus2, m21.stream.Score | m21.stream.Opus)
        assert scoreOrOpus2.isWellFormedNotation()

        if scoreNum is not None and isinstance(scoreOrOpus1, m21.stream.Opus):
            # pull the appropriate score out of the input Opus
            theScore: m21.stream.Score | None = scoreOrOpus1.getScoreByNumber(str(scoreNum))
            assert isinstance(theScore, m21.stream.Score)
            scoreOrOpus1 = theScore

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
                sc1, detail
            )
            print(f'loaded imported {inFmt} score')
            score_lin2 = AnnScore(
                sc2, detail
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

    @staticmethod
    def runDiffAll(
        listPath: Path,
        inFmt: str,
        outFmt: str,
        outExt: str,
        writeUsingVerovio: bool = False,
        convertInputToMeiUsingVerovioBeforeReading: bool = False,
        exportMeiMultiScoreHostTag: str = 'mei',  # default to match old results
        detail: DetailLevel | int = DEFAULT_DETAIL_LEVEL
    ):
        # Generate a random integer between 1 and 1,000,000,000 (inclusive)
        # We put this in written file names, so different tests don't
        # overwrite each other's output files.
        uniqueInt: int = random.randint(1, 1000 * 1000 * 1000)

        goodPath: Path = Path(str(listPath.parent) + '/../results/' + str(listPath.stem)
                                + '.goodList.txt')
        badPath: Path = Path(str(listPath.parent) + '/../results/' + str(listPath.stem)
                                + '.badList.txt')
        resultsPath: Path = Path(str(listPath.parent) + '/../results/' + str(listPath.stem)
                                + '.resultsList.txt')

        fileList: list[str] = []
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

                        if DiffUtilities.runDiffOne(
                                Path(file),
                                resultsf,
                                inFmt,
                                outFmt,
                                outExt,
                                uniqueInt,
                                writeUsingVerovio,
                                convertInputToMeiUsingVerovioBeforeReading,
                                exportMeiMultiScoreHostTag,
                                detail):
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

    @staticmethod
    def runDiffOne(
        inputPath: Path,
        results: TextIOWrapper,
        inFmt: str,
        outFmt: str,
        outExt: str,
        uniqueInt: int,
        writeUsingVerovio: bool = False,
        convertInputToMeiUsingVerovioBeforeReading: bool = False,
        exportMeiMultiScoreHostTag: str = 'mei',  # default to match old results
        detail: DetailLevel | int = DEFAULT_DETAIL_LEVEL
    ) -> bool:
        # returns True if the test passed (no musicdiff differences found)
        if not inFmt:
            # figure it out from inputPath's file extension
            c = m21.converter.Converter()
            inFmt = c.getFormatFromFileExtension(inputPath)

        print(f'{inputPath}', end='')
        print(f'{inputPath}', end='', file=results)
        results.flush()

        origInputPath: Path = inputPath

        verovioCompatibleImport: bool = (
            writeUsingVerovio or convertInputToMeiUsingVerovioBeforeReading
        )

        if convertInputToMeiUsingVerovioBeforeReading:
            try:
                meiPath = Path(tempfile.gettempdir())
                meiPath /= inputPath.name
                meiPath = meiPath.with_suffix(f'.{uniqueInt}.mei')
                subprocess.run(
                    ['verovio', '-a', '-f', inFmt, '-t', 'mei', '-o', str(meiPath), str(inputPath)],
                    check=True,
                    capture_output=True
                )
            except KeyboardInterrupt:
                results.flush()
                sys.exit(0)
            except Exception:
                print(': conversion to mei with verovio failed')
                print(': conversion to mei with verovio failed', file=results)
                results.flush()
                return False

            inputPath = meiPath
            inFmt = 'mei'

        # import into music21
        try:
            scoreOrOpus1 = m21.converter.parse(
                inputPath,
                format=inFmt,
                forceSource=True,
                verovioCompatibleImport=verovioCompatibleImport
            )
            if scoreOrOpus1 is None:
                print(': scoreOrOpus1 creation failure')
                print(': scoreOrOpus1 creation failure', file=results)
                results.flush()
                return False
        except KeyboardInterrupt:
            results.flush()
            sys.exit(0)
        except Exception as e:
            print(f': scoreOrOpus1 creation crash: {e}')
            print(f': scoreOrOpus1 creation crash: {e}', file=results)
            results.flush()
            return False

        if not isinstance(scoreOrOpus1, (m21.stream.Score, m21.stream.Opus)):
            print(': scoreOrOpus1 is neither Score nor Opus')
            print(': scoreOrOpus1 is neither Score nor Opus', file=results)
            results.flush()
            return False

        if not scoreOrOpus1.elements:
            # empty score is valid result, but assume diff will be exact
            # (export of empty score fails miserably)
            print(': numDiffs = 0 (empty scoreOrOpus1)')
            print(': numDiffs = 0 (empty scoreOrOpus1)', file=results)
            results.flush()
            return True

        if not scoreOrOpus1.isWellFormedNotation():
            print(': scoreOrOpus1 not well formed')
            print(': scoreOrOpus1 not well formed', file=results)
            results.flush()
            return False

        if inFmt in ('musicxml', 'mxl'):
            # We know that MusicXML files can only contain one score.
            if t.TYPE_CHECKING:
                assert isinstance(scoreOrOpus1, m21.stream.Score)

            # Some MusicXML files have abbreviations instead of chordKinds (e.g. 'min' instead of
            # the correct 'minor').  Fix that before the diff is performed.
            M21Utilities.fixupBadChordKinds(scoreOrOpus1, inPlace=True)

            # Some MusicXML files have beams that go 'start'/'continue' when they should be
            # 'start'/'stop'. fixupBadBeams notices that the next beam is a 'start', or is
            # not present at all, and therefore patches that 'continue' to be a 'stop'.
            M21Utilities.fixupBadBeams(scoreOrOpus1, inPlace=True)

        if writeUsingVerovio:
            if inFmt not in ('humdrum', 'abc') or outFmt != 'mei':
                raise Exception(
                    'bad args: writeUsingVerovio requires Humdrum or ABC input and MEI output'
                )
            try:
                # convert Humdrum input file to MEI using Verovio
                writePath = Path(tempfile.gettempdir())
                writePath /= inputPath.name
                writePath = writePath.with_suffix(f'.{uniqueInt}.mei')
                # print(f'Writing mei file with Verovio: {writePath}')
                subprocess.run(
                    ['verovio', '-a', '-f', inFmt, '-t', 'mei', '-o',
                        str(writePath), str(inputPath)],
                    check=True,
                    capture_output=True
                )
            except KeyboardInterrupt:
                results.flush()
                sys.exit(0)
            except Exception as e:
                print(f': verovio crash: {e}')
                print(f': verovio crash: {e}', file=results)
                results.flush()
                return False

        else:
            # export score to outFmt (without any makeNotation fixups)
            try:
                success: bool = True
                writePath = Path(tempfile.gettempdir())
                writePath /= (inputPath.stem + '_Written')
                writePath = writePath.with_suffix(f'.{uniqueInt}.' + outExt)
                # Use Stream.write instead of Opus.write (which will incorrectly
                # split into multiple files, one per score)
                # success = scoreOrOpus1.write(fp=writePath, fmt=outFmt, makeNotation=False)
                if outFmt == 'mei':
                    success = m21.stream.Stream.write(
                        scoreOrOpus1,
                        fp=writePath,
                        fmt=outFmt,
                        makeNotation=False,
                        multipleScoresHostTag=exportMeiMultiScoreHostTag
                    )
                else:
                    success = m21.stream.Stream.write(
                        scoreOrOpus1,
                        fp=writePath,
                        fmt=outFmt,
                        makeNotation=False
                    )
                if not success:
                    print(': export failed')
                    print(': export failed', file=results)
                    results.flush()
                    return False
            except KeyboardInterrupt:
                results.flush()
                sys.exit(0)
            except Exception as e:
                print(f': export crash: {e}')
                print(f': export crash: {e}', file=results)
                results.flush()
                return False

        # and then try to parse the exported file

        try:
            # compare the two music21 scores with musicdiff APIs:
            scoreOrOpus2 = m21.converter.parse(
                writePath,
                format=outFmt,
                forceSource=True,
                verovioCompatibleImport=verovioCompatibleImport
            )
            if scoreOrOpus2 is None:
                print(': scoreOrOpus2 creation failure')
                print(': scoreOrOpus2 creation failure', file=results)
                results.flush()
                return False
        except KeyboardInterrupt:
            results.flush()
            sys.exit(0)
        except Exception as e:
            print(f': scoreOrOpus2 creation crash: {e}')
            print(f': scoreOrOpus2 creation crash: {e}', file=results)
            results.flush()
            return False

        if not isinstance(scoreOrOpus2, (m21.stream.Score, m21.stream.Opus)):
            print(': scoreOrOpus2 is neither Score nor Opus')
            print(': scoreOrOpus2 is neither Score nor Opus', file=results)
            results.flush()
            return False

        if not scoreOrOpus2.elements:
            print(': scoreOrOpus2 was empty')
            print(': scoreOrOpus2 was empty', file=results)
            results.flush()
            return False  # empty scoreOrOpus2 is bad, because scoreOrOpus1 was not empty

        if not scoreOrOpus2.isWellFormedNotation():
            print(': scoreOrOpus2 not well formed')
            print(': scoreOrOpus2 not well formed', file=results)
            results.flush()
            return False

        # Some converters can read/write Score or Opus (full of scores).
        # So we make lists 1 and 2 of scores, and loop over them, comparing.
        score1List: list[m21.stream.Score] = DiffUtilities.getScoreList(scoreOrOpus1)
        score2List: list[m21.stream.Score] = DiffUtilities.getScoreList(scoreOrOpus2)
        DiffUtilities.padWithEmptyScores(score1List, score2List)

        isMultiScore: bool = len(score1List) > 1

        totalNumDiffs: int = 0

        for i, (sc1, sc2) in enumerate(zip(score1List, score2List)):
            # use musicdiff to compare the two music21 scores,
            # and return whether or not they were identical
            try:
                if isMultiScore:
                    if i == 0:
                        # we already printed inputPath one time
                        print(f' (score {i}): ', end='')
                        print(f' (score {i}): ', end='', file=results)
                    else:
                        print(f'{origInputPath} (score {i}): ', end='')
                        print(f'{origInputPath} (score {i}): ', end='', file=results)
                else:
                    # we already printed inputPath one time
                    print(': ', end='')
                    print(': ', end='', file=results)

                results.flush()

                annotatedScore1 = AnnScore(sc1, detail)
                annotatedScore2 = AnnScore(sc2, detail)

                op_list, cost = Comparison.annotated_scores_diff(
                    annotatedScore1, annotatedScore2
                )
                numDiffs = len(op_list)
                totalNumDiffs += numDiffs
                print(f'numDiffs = {numDiffs}')
                print(f'numDiffs = {numDiffs}', file=results)
                results.flush()
                if numDiffs > 0:
                    summ: str = '\t' + DiffUtilities.oplistSummary(op_list)
                    print(summ)
                    print(summ, file=results)

                # print OMR-NED dict even if there are no diffs
                omrnedOut: dict = Visualization.get_omr_ned_output(
                    cost, annotatedScore1, annotatedScore2
                )
                jsonStr: str = json.dumps(omrnedOut)
                print(jsonStr)
                print(jsonStr, file=results)

                textOut: str = Visualization.get_text_output(sc1, sc2, op_list)
                if textOut:
                    print(textOut)
                    print(textOut, file=results)
                    results.flush()

            except KeyboardInterrupt:
                results.flush()
                sys.exit(0)
            except Exception as e:
                print(f'musicdiff crashed: {e}')
                print(f'musicdiff crashed: {e}', file=results)
                results.flush()
                return False

        if isMultiScore:
            print(f'{inputPath}: total numDiffs = {totalNumDiffs}')
            print(f'{inputPath}: total numDiffs = {totalNumDiffs}', file=results)
            results.flush()

        # one last flush() just to be sure...
        results.flush()

        if totalNumDiffs > 0:
            return False

        return True

    @staticmethod
    def oplistSummary(
        op_list: list[tuple[str, t.Any, t.Any]],
    ) -> str:
        output: str = ''
        counts: dict = {}

        # print(f'op_list = {op_list}', file=sys.stderr)

        counts['part'] = 0
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
            # part
            if op[0] in ('inspart', 'delpart'):
                counts['part'] += 1
            # measure
            elif op[0] in ('insbar', 'delbar'):
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
