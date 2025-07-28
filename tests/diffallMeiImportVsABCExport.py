from pathlib import Path
import argparse
import sys

import converter21
from musicdiff import DetailLevel
from tests.diffutilities import DiffUtilities

# ------------------------------------------------------------------------------

'''
    main entry point (parse arguments and do conversion)
'''
converter21.register()

parser = argparse.ArgumentParser()
parser.add_argument(
        'list_file',
        help='file containing a list of the files to read/write/compare (full paths)')
args = parser.parse_args()

listPath: Path = Path(args.list_file)

DiffUtilities.runDiffAll(
    listPath,
    inFmt='mei',
    outFmt='abc',
    outExt='abc',
    detail=DetailLevel.AllObjects | DetailLevel.Metadata  # no Style for ABC
)

print('done.')
