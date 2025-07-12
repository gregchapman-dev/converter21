import argparse
from pathlib import Path

from tests.diffutilities import DiffUtilities

# ------------------------------------------------------------------------------

'''
    main entry point (parse arguments and run test)
'''

parser = argparse.ArgumentParser()
parser.add_argument('input_file')
parser.add_argument('-n', '--num', default=None)
args = parser.parse_args()

DiffUtilities.runShowDiff(
    inputPath=Path(args.input_file),
    inFmt='pickled',
    outFmt='mei',
    outExt='mei',
    scoreNum=int(args.num) if args.num is not None else None
)
