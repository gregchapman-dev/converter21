import pytest
from pathlib import Path

# The things we're testing
from converter21.humdrum import HumdrumFileBase
from converter21.humdrum import HumdrumFile
from converter21.humdrum.HumdrumFileBase import getMergedSpineInfo


# The check routine that every test calls at least once
from tests.Utilities import CheckHumdrumFile, HumdrumFileTestResults

def test_HumdrumFile_default_init():
    f = HumdrumFile()
    results = HumdrumFileTestResults()
    CheckHumdrumFile(f, results)

# def test_ParticularFile():
#     f = HumdrumFile('/Users/gregc/Documents/test/humdrum_test_files_from_humlib/test-manipulators.krn') # put particular file to test's full pathstr there
#     results = HumdrumFileTestResults('') # put particular file to test's results file there
#     CheckHumdrumFile(f, results)

def test_getMergedSpineInfo():
    assert getMergedSpineInfo(['1'], 0, 0) == '1'
    #assert getMergedSpineInfo(['1', '2'], 0, 1) == '1 2'
    assert getMergedSpineInfo(['(1)a', '((1)b)a', '((1)b)b', '(2)a', '(2)b', '3'], 1, 1) == '(1)b'
    assert getMergedSpineInfo(['(1)a', '((1)b)a', '((1)b)b', '(2)a', '(2)b', '3'], 0, 2) == '1'
    assert getMergedSpineInfo(['(1)a', '(((1)b)a)a', '(((1)b)a)b', '(((1)b)b)a', '(((1)b)b)b', '(2)a', '(2)b', '3'], 0, 4) == '1'
    assert getMergedSpineInfo(['(1)a', '(((1)b)a)a', '(((1)b)a)b', '(((1)b)b)a', '(((1)b)b)b', '(2)a', '(2)b', '3'], 5, 1) == '2'
    assert getMergedSpineInfo(['(1)a', '((((1)b)a)a)a', '((((1)b)a)a)b', '((((1)b)a)b)a', '((((1)b)a)b)b', '((((1)b)b)a)a', '((((1)b)b)a)b', '((((1)b)b)b)a', '((((1)b)b)b)b', '(2)a', '(2)b', '3'], 0, 8) == '1'

def ReadAllTestFilesInFolder(folder: str):
    krnPaths: [Path] = list(Path(folder).glob('**/*.krn'))
    print('numTestFiles in', folder, ' =', len(krnPaths))
    assert len(krnPaths) > 0

    numCrashes = 0
    crashIdxes = []
    for i, krnPath in enumerate(krnPaths):
        print('krn file {}: {}'.format(i, krnPath))
        resultsFileName = krnPath.stem + '.json'
        resultsPath = krnPath.parent / resultsFileName
#         try:
        hfb = HumdrumFile(str(krnPath))
        score = hfb.createMusic21Stream() # calls analyzeNotation, and does conversion (not tested, just run)
        results = HumdrumFileTestResults.fromFiles(str(krnPath), str(resultsPath))
        CheckHumdrumFile(hfb, results)
#         except:
#             numCrashes += 1
#             crashIdxes += [i]
#
#     if numCrashes > 0:
#         print("crashed {} times {} out of {} files".format(numCrashes, crashIdxes, len(krnPaths)))
#         assert False

def test_HumdrumFile_read_all_test_files_from_humlib_FromFile():
    '''Test HumdrumFile('blah.krn') for every krn file
        in ~/Documents/test/humdrum_test_files_from_humlib'''
    ReadAllTestFilesInFolder('/Users/gregc/Documents/test/humdrum_test_files_from_humlib')

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

# @pytest.mark.slow
# def test_HumdrumFile_read_all_test_files_from_humdrum_chopin_first_editions_FromFile():
#     '''Test HumdrumFile('blah.krn') for every krn file
#         in ~/Documents/test/humdrum-chopin-first-editions'''
#     ReadAllTestFilesInFolder('/Users/gregc/Documents/test/humdrum-chopin-first-editions')

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

@pytest.mark.slow
def test_HumdrumFile_read_all_humdrum_files_in_music21_corpus_FromFile():
    '''Test HumdrumFile('blah.krn') against 'blah.json' for every krn file
    in ~/Documents/test/humdrum_test_files_from_music21_corpus'''
    ReadAllTestFilesInFolder('/Users/gregc/Documents/test/humdrum_test_files_from_music21_corpus')

@pytest.mark.slow
def test_HumdrumFile_read_all_humdrum_files_in_tasso_scores_FromFile():
    '''Test HumdrumFile('blah.krn') against 'blah.json' for every krn file
    in ~/Documents/test/tasso-scores'''
    ReadAllTestFilesInFolder('/Users/gregc/Documents/test/tasso-scores')

@pytest.mark.slow
def test_HumdrumFile_read_all_humdrum_files_in_rds_scores_FromFile():
    '''Test HumdrumFile('blah.krn') against 'blah.json' for every krn file
    in ~/Documents/test/rds-scores'''
    ReadAllTestFilesInFolder('/Users/gregc/Documents/test/rds-scores')

# add more tests for coverage...
