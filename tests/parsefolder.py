import os
# import sys
import argparse

from pathlib import Path

import music21 as m21
import converter21

def parseTheFile(theFile: Path):
    try:
        isGT: bool = str(theFile).endswith('gt.kern')
        if isGT:
            score = m21.converter.parse(theFile, forceSource=True)
        else:
            score = m21.converter.parse(theFile, forceSource=True, acceptSyntaxErrors=True)
        if score is None:
            print('None')
            return
        numParts: int = len(list(score.parts))
        if not score.elements:
            print('empty score (exception raised)')
            return
        if numParts == 0:
            print('no parts in score')
            return
        # if isGT and numParts not in (2, 4):
        #     print(f'{numParts} parts, should be 2 or 4')
        #     return
        if not score.isWellFormedNotation():
            print('ill-formed score')
            return
        print('GOOD')
    except Exception as e:
        print(f'raised {e}')

# ------------------------------------------------------------------------------


'''
    main entry point (parse arguments and do conversion)
'''
converter21.register()
converter21.M21Utilities.adjustMusic21Behavior()

parser = argparse.ArgumentParser(
    description='Loop over folder (containing score files of any supported format)'
    ', importing each file and checking the resulting score is well-formed, and not empty.'
)
parser.add_argument(
    'score_folder',
    help='path to folder containing score files to parse')

args = parser.parse_args()

# iterate over files in
# that directory
for filename in os.listdir(args.score_folder):
    f = os.path.join(args.score_folder, filename)
    # checking if it is a file
    if not os.path.isfile(f):
        continue

    print(f + ': ', end='')

    result: bool = parseTheFile(Path(f))
