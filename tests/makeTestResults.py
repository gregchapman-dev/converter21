import argparse
from pathlib import Path
import json
import os, sys

# do the following to temporarily add parent dir to $path, so this python file in
# converter21/tests can import from converter21/humdrum.
currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)

from converter21.humdrum import HumdrumFile

def generateExclusiveInterpretationLineNumbers(hf: HumdrumFile) -> list:
    result = []
    for line in hf.lines():
        if line.isExclusiveInterpretation:
            result.append(line.lineNumber)
    return result

def generateManipulatorLineNumbers(hf: HumdrumFile) -> list:
    result = []
    for line in hf.lines():
        if line.isManipulator:
            result.append(line.lineNumber)
    return result

def generateTokenDataTypeChanges(hf: HumdrumFile) -> dict:
    result = {}
    currTokenDataTypes: [str] = []
    for line in hf.lines():
        newTokenDataTypes = [token.dataType.text for token in line.tokens()]
        if newTokenDataTypes != currTokenDataTypes:
            result[str(line.lineNumber)] = newTokenDataTypes
            currTokenDataTypes = newTokenDataTypes
    return result

def generateSpineInfoChanges(hf: HumdrumFile) -> dict:
    result = {}
    currSpineInfos: [str] = []
    for line in hf.lines():
        newSpineInfos = [token.spineInfo for token in line.tokens()]
        if newSpineInfos != currSpineInfos:
            result[str(line.lineNumber)] = newSpineInfos
            currSpineInfos = newSpineInfos
    return result

parser = argparse.ArgumentParser(
            description='Make test results for all .krn files in a folder. The test results for /tests/SomeMusic.krn will be written to /tests/SomeMusic.json.')
parser.add_argument('folder',
                    help='folder where the .krn files to process can be found')
parser.add_argument('-r', '--recurse', action='store_true',
                    help='recurse through subfolders')

args = parser.parse_args()

folder = args.folder.rstrip('/') # to be pretty

if args.recurse:
    patt = '**/*.krn'
else:
    patt = '*.krn'

krnPaths: [Path] = list(Path(folder).glob(patt))
print('numTestFiles =', len(krnPaths))
for krnPath in krnPaths:
    print("krnPath     =", krnPath)
    try:
        hf: HumdrumFile = HumdrumFile(krnPath)
    except:
        print("Exception parsing", str(krnPath))
        continue

    resultsDict = dict(
        fileContentsUnmodified = not hf.fixedUpRecipOnlyToken,
        tpq = hf.tpq(),
        exclusiveInterpretationLineNumbers = generateExclusiveInterpretationLineNumbers(hf),
        manipulatorLineNumbers = generateManipulatorLineNumbers(hf),
        tokenDataTypeChanges = generateTokenDataTypeChanges(hf),
        spineInfoChanges = generateSpineInfoChanges(hf)
    )

    if len(resultsDict['exclusiveInterpretationLineNumbers']) > 1:
        print('**** > 1 exclusiveInterpretation in ', krnPath)

    resultsFileName = krnPath.stem + '.json'
    resultsPath = krnPath.parent / resultsFileName
    print("resultsPath =", resultsPath)
    with resultsPath.open('w') as resultsFile:
        resultsFile.write(json.dumps(resultsDict, indent=4))
