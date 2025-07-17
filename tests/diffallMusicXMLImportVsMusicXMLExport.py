from pathlib import Path
import argparse
import sys

import converter21
from tests.diffutilities import DiffUtilities

# ------------------------------------------------------------------------------

'''
    main entry point (parse arguments and do conversion)
'''
converter21.register()

parser = argparse.ArgumentParser()
parser.add_argument(
        'list_file',
        help='file containing a lis of the .musicxml/.mxl files to compare (full paths)')
args = parser.parse_args()

listPath: Path = Path(args.list_file)

DiffUtilities.runDiffAll(
    listPath,
    inFmt='musicxml',
    outFmt='musicxml',
    outExt='musicxml'
)

print('done.')
