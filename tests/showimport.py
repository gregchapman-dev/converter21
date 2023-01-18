from pathlib import Path
import tempfile
import argparse
import sys
import subprocess

from music21.base import VERSION_STR
from music21 import converter
import converter21


def runTheTest(filePath: Path):
    print(f'importing {filePath}')

    # import into music21
    try:
        score1: m21.stream.Score = converter.parse(filePath, forceSource=True)
    except KeyboardInterrupt:
        sys.exit(0)
    # except:
    #     print('MEIConverter parse crash')
    #     return False

    if score1 is None:
        print('parse failure')
        return False

    if not score1.isWellFormedNotation():
        print('score1 not well formed')
        return False

    # render and open the resulting PDF in Preview.app
    score1.show('musicxml.pdf', makeNotation=False)

    # write the musicxml file and open in bbedit
    fp = score1.write('musicxml', makeNotation=False)
    subprocess.run(['bbedit', str(fp)], check=False)
    return True

# ------------------------------------------------------------------------------

'''
    main entry point (parse arguments and do conversion)
'''
# replace music21's built-in converters with ours (currently Humdrum and MEI)
converter21.register()

parser = argparse.ArgumentParser()
parser.add_argument('input_file')
print('music21 version:', VERSION_STR, file=sys.stderr)
args = parser.parse_args()

runTheTest(Path(args.input_file))
