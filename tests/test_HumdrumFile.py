import pytest
from pathlib import Path
import tempfile

# The things we're testing
from converter21.humdrum import HumdrumFileBase
from converter21.humdrum import HumdrumFile
from converter21.humdrum import HumdrumWriter


# The check routine that every test calls at least once
from tests.Utilities import CheckHumdrumFile, HumdrumFileTestResults

# def test_ParticularFile():
#     f = HumdrumFile('/Users/gregc/Documents/test/rds-scores/kern/R408_Web-w13p1-2m1-12.krn') # put particular file to test's full pathstr there
#     assert (f.isValid)
#
#     results = HumdrumFileTestResults.fromFiles('/Users/gregc/Documents/test/rds-scores/kern/R408_Web-w13p1-2m1-12.krn',
#                                                '/Users/gregc/Documents/test/rds-scores/kern/R408_Web-w13p1-2m1-12.json')
#     CheckHumdrumFile(f, results)

def test_getMergedSpineInfo():
    assert HumdrumFile.getMergedSpineInfo(['1'], 0, 0) == '1'
    #assert getMergedSpineInfo(['1', '2'], 0, 1) == '1 2'
    assert HumdrumFile.getMergedSpineInfo(['(1)a', '((1)b)a', '((1)b)b', '(2)a', '(2)b', '3'], 1, 1) == '(1)b'
    assert HumdrumFile.getMergedSpineInfo(['(1)a', '((1)b)a', '((1)b)b', '(2)a', '(2)b', '3'], 0, 2) == '1'
    assert HumdrumFile.getMergedSpineInfo(['(1)a', '(((1)b)a)a', '(((1)b)a)b', '(((1)b)b)a', '(((1)b)b)b', '(2)a', '(2)b', '3'], 0, 4) == '1'
    assert HumdrumFile.getMergedSpineInfo(['(1)a', '(((1)b)a)a', '(((1)b)a)b', '(((1)b)b)a', '(((1)b)b)b', '(2)a', '(2)b', '3'], 5, 1) == '2'
    assert HumdrumFile.getMergedSpineInfo(['(1)a', '((((1)b)a)a)a', '((((1)b)a)a)b', '((((1)b)a)b)a', '((((1)b)a)b)b', '((((1)b)b)a)a', '((((1)b)b)a)b', '((((1)b)b)b)a', '((((1)b)b)b)b', '(2)a', '(2)b', '3'], 0, 8) == '1'

def test_HumdrumFile_default_init():
    f = HumdrumFile()
    results = HumdrumFileTestResults()
    CheckHumdrumFile(f, results)

def ReadAllTestFilesInFolder(folder: str):
    krnPaths: [Path] = sorted(list(Path(folder).glob('**/*.krn')), key=str)
    print('numTestFiles in', folder, ' =', len(krnPaths))
    assert len(krnPaths) > 0

    numCrashes = 0
    crashIdxes = []
    for i, krnPath in enumerate(krnPaths):
        print('krn file {}: {}'.format(i, krnPath))

        # use this to skip files in folder (i.e. start with n, which is 0-based)
        # n = 78
        # if i < n:
        #     print(f'\tskipping any files before {n}th file in folder')
        #     continue
#
#         if krnPath.name == 'sonata07-1.krn':
#             print('hi')

        resultsFileName = krnPath.stem + '.json'
        resultsPath = krnPath.parent / resultsFileName
#         try:

        if 'tasso-scores' in str(krnPath) and krnPath.name in (
                'Tam2031034a-Vorro_veder_cio_che_Tirsi_avra_fatto--Balsamino_1594.krn',
                                                            ):
            print('skipping test because krnFile contains more than one score (not yet supported)')
            continue

        hfb = HumdrumFile(str(krnPath))
        assert(hfb.isValid)

        results = HumdrumFileTestResults.fromFiles(str(krnPath), str(resultsPath))
        CheckHumdrumFile(hfb, results)

        # import humdrum into music21 stream

        score = hfb.createMusic21Stream()
        assert(score is not None)
        assert(score.isWellFormedNotation() or not score.elements)

        # export score back to humdrum (without any makeNotation fixups)

        # if the score is empty, exporting from it will not produce anything interesting
        if not score.elements:
            print('\tskipping export of empty score')
            continue

        # The following are worth working on, but I am skipping for now so I can run
        # all the tests to see where we are.

        # these are cases that cause extendTokenDuration to fail because it ran out
        # of room before the next note (music21 has overlapping notes, most likely)
        if krnPath.name in (
                'test-manipulators.krn',
                'test-spine-float.krn'
                            ):
            print('\tskipping export due to overlapping note durations (caused perhaps by *+)')
            continue

        hdw: HumdrumWriter = HumdrumWriter(score)
        hdw.makeNotation = False
        hdw.addRecipSpine = krnPath.name == 'test-rhythms.krn'

        success: bool = True
        fp = Path(tempfile.gettempdir()) / krnPath.name
        with open(fp, 'w') as f:
            success = hdw.write(f)

        assert(success)

        # and then try to parse the exported humdrum file

        # These are cases where export produced an unparseable humdrum file.

        # this is a weird one...
        if 'rds-scores' in str(krnPath) and krnPath.name in (
                'R262x_Ive-w33b4p26.krn',
                'R443_Ber-w10p321m593-595.krn',
                ): # rds-scores
            print('\tskipping parse of export due to missing fields')
            continue

        if 'rds-scores' in str(krnPath) and krnPath.name in (
                'R258_Ive-w30p9m55-57.krn',
                                                            ):
            print('\tskipping parse of export due to unparseable manipulators (original is even weirder, but parseable)')
            continue

        hfb = HumdrumFile(str(fp))
        assert(hfb.isValid)

        score2 = hfb.createMusic21Stream()
        assert(score2 is not None)
        assert(score2.isWellFormedNotation())

        # here we could check against results, or even compare the two music21 scores

#         except:
#             numCrashes += 1
#             crashIdxes += [i]
#
#     if numCrashes > 0:
#         print("crashed {} times {} out of {} files".format(numCrashes, crashIdxes, len(krnPaths)))
#         assert False

@pytest.mark.slow
def test_HumdrumFile_read_all_test_files_from_humdrum_beethoven_piano_sonatas_FromFile():
    '''Test HumdrumFile('blah.krn') for every krn file
        in ~/Documents/test/humdrum_beethoven_piano_sonatas'''
    ReadAllTestFilesInFolder('/Users/gregc/Documents/test/humdrum_beethoven_piano_sonatas')

@pytest.mark.slow
def test_HumdrumFile_read_all_test_files_from_humdrum_chopin_mazurkas_FromFile():
    '''Test HumdrumFile('blah.krn') for every krn file
        in ~/Documents/test/humdrum_chopin_mazurkas'''
    ReadAllTestFilesInFolder('/Users/gregc/Documents/test/humdrum_chopin_mazurkas')

@pytest.mark.slow
def test_HumdrumFile_read_all_test_files_from_humdrum_joplin_FromFile():
    '''Test HumdrumFile('blah.krn') for every krn file
        in ~/Documents/test/humdrum_joplin'''
    ReadAllTestFilesInFolder('/Users/gregc/Documents/test/humdrum_joplin')

@pytest.mark.slow
def test_HumdrumFile_read_all_test_files_from_humdrum_mozart_piano_sonatas_FromFile():
    '''Test HumdrumFile('blah.krn') for every krn file
        in ~/Documents/test/humdrum_mozart_piano_sonatas'''
    ReadAllTestFilesInFolder('/Users/gregc/Documents/test/humdrum_mozart_piano_sonatas')

def test_HumdrumFile_read_all_test_files_from_humlib_FromFile():
    '''Test HumdrumFile('blah.krn') for every krn file
        in ~/Documents/test/humdrum_test_files_from_humlib'''
    ReadAllTestFilesInFolder('/Users/gregc/Documents/test/humdrum_test_files_from_humlib')

@pytest.mark.slow
def test_HumdrumFile_read_all_humdrum_files_in_music21_corpus_FromFile():
    '''Test HumdrumFile('blah.krn') against 'blah.json' for every krn file
    in ~/Documents/test/humdrum_test_files_from_music21_corpus'''
    ReadAllTestFilesInFolder('/Users/gregc/Documents/test/humdrum_test_files_from_music21_corpus')

# @pytest.mark.slow
# def test_HumdrumFile_read_all_test_files_from_humdrum_chopin_first_editions_FromFile():
#     '''Test HumdrumFile('blah.krn') for every krn file
#         in ~/Documents/test/humdrum-chopin-first-editions'''
#     ReadAllTestFilesInFolder('/Users/gregc/Documents/test/humdrum-chopin-first-editions')

#@pytest.mark.slow
# def test_HumdrumFile_read_all_humdrum_files_in_jrp_scores_FromFile():
#     '''Test HumdrumFile('blah.krn') against 'blah.json' for every krn file
#     in ~/Documents/test/jrp-scores'''
#     ReadAllTestFilesInFolder('/Users/gregc/Documents/test/jrp-scores')

@pytest.mark.slow
def test_HumdrumFile_read_all_humdrum_files_in_rds_scores_FromFile():
    '''Test HumdrumFile('blah.krn') against 'blah.json' for every krn file
    in ~/Documents/test/rds-scores'''
    ReadAllTestFilesInFolder('/Users/gregc/Documents/test/rds-scores')

@pytest.mark.slow
def test_HumdrumFile_read_all_humdrum_files_in_tasso_scores_FromFile():
    '''Test HumdrumFile('blah.krn') against 'blah.json' for every krn file
    in ~/Documents/test/tasso-scores'''
    ReadAllTestFilesInFolder('/Users/gregc/Documents/test/tasso-scores')

# add more tests for coverage...
