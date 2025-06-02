import os
# import sys
import argparse

from pathlib import Path

import music21 as m21
import converter21

def parseTheFile(theFile: Path):
    try:
        isGT: bool = 'gt' in str(theFile)
        if isGT:
            score = m21.converter.parse(theFile, forceSource=True)
        else:
            score = m21.converter.parse(theFile, forceSource=True, acceptSyntaxErrors=True)
        if score is None:
            print('None')
            return

        numParts: int = len(list(score.parts))
        err: str = ''
        if hasattr(score, 'c21_parse_err'):
            err = score.c21_parse_err

        if not score.elements:
            if err:
                print(f'empty score: {err}')
            else:
                print('empty score')
            return

        if numParts == 0:
            if err:
                print(f'no parts in score: {err}')
            else:
                print('no parts in score')
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
