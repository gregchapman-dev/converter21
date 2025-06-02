import os
# import sys
import argparse

from pathlib import Path

import music21 as m21
import converter21

def show_file(filePath: Path):
    print(f'importing {filePath}')

    # import into music21
    try:
        isGT: bool = 'gt' in str(filePath)
        if isGT:
            score1 = m21.converter.parse(filePath, forceSource=True)
        else:
            score1 = m21.converter.parse(filePath, forceSource=True, acceptSyntaxErrors=True)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f'converter.parse crash: {e}')
        return False

    if score1 is None:
        print('parse failure')
        return False

    if not score1.isWellFormedNotation():
        print('score1 not well formed')
        return False

    # try:
    # render and open the resulting PDF in Preview.app
    score1.show('musicxml.pdf', makeNotation=False)
    # except Exception as e:
        # print(f'score1.show crash: {e}')

    # write the musicxml file and open in bbedit
    # fp = score1.write('musicxml', makeNotation=False)
    # subprocess.run(['bbedit', str(fp)], check=False)
    return True

# ------------------------------------------------------------------------------

def show_folder(folder: str):
    # iterate over files in
    # that directory
    for filename in os.listdir(folder):
        f = os.path.join(folder, filename)
        if not os.path.isfile(f):
            show_folder(f)
            continue

        result: bool = show_file(Path(f))

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

show_folder(args.score_folder)

