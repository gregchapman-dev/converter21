from pathlib import Path
import tempfile
import argparse
import sys
import subprocess

from music21.base import VERSION_STR
from music21 import converter
from converter21 import MEIConverter


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
        print('MEIConverter parse failure')
        return False

    if not score1.isWellFormedNotation():
        print('score1 not well formed')
        return False

    score1.show('musicxml.pdf')

    return True

# ------------------------------------------------------------------------------

'''
    main entry point (parse arguments and do conversion)
'''
converter.unregisterSubconverter(converter.subConverters.ConverterMEI)
converter.registerSubconverter(MEIConverter)

parser = argparse.ArgumentParser()
parser.add_argument('input_file')
print('music21 version:', VERSION_STR, file=sys.stderr)
args = parser.parse_args()

runTheTest(Path(args.input_file))
