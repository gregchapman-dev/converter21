from pathlib import Path
import tempfile
import argparse
import sys
from typing import List, Tuple
import music21 as m21
from music21.base import VERSION_STR
from music21 import converter
from converter21 import MEIConverter

def runTheTest(filePath: Path, results) -> bool:
    print(f'{filePath}: ')
    print(f'{filePath}: ', file=results)
    results.flush()

    # import into music21
    try:
        score1: m21.stream.Score = converter.parse(filePath, forceSource=True)
    except KeyboardInterrupt:
        sys.exit(0)
    except:
        print('MEIConverter parse crash')
        print('MEIConverter parse crash', file=results)
        results.flush()
        return False

    if score1 is None:
        print('MEIConverter parse failure')
        print('MEIConverter parse failure', file=results)
        results.flush()
        return False

    if not score1.elements:
        print('score1 is empty')
        print('score1 is empty', file=results)
        results.flush()
        return True  # that's OK for mensural scores, etc

    if not score1.isWellFormedNotation():
        print('score1 not well formed')
        print('score1 not well formed', file=results)
        results.flush()
        return False

#     print('')
#     print('', file=results)
    return True

# ------------------------------------------------------------------------------

'''
    main entry point (parse arguments and do conversion)
'''
converter.unregisterSubconverter(converter.subConverters.ConverterMEI)
converter.registerSubconverter(MEIConverter)

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

                if runTheTest(Path(file), resultsf):
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
