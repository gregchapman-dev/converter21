import os
# import sys
import argparse
import json

from pathlib import Path

import music21 as m21
import converter21

# ------------------------------------------------------------------------------

'''
    main entry point
'''
converter21.register()
converter21.M21Utilities.adjustMusic21Behavior()

parser = argparse.ArgumentParser(
    description='Loop over SMB-style jsonl file (containing kern scores split into regions)'
    ', looking at each entry and fixing the region-splitting errors.'
)
parser.add_argument(
    'file',
    help='metadata.jsonl file (each line is separate JSON data for a score)')

args = parser.parse_args()

# for now all we do is dump out the metadata.jsonl file (no finding errors, or fixing them)
filename: str = os.path.expanduser(args.file)

allscores: list = []
numUnparseable: int = 0
numCrashes: int = 0
numEmptyStrings: int = 0
numOK: int = 0
numRegions: int = 0
with open(args.file) as f:
    for line in f:
        scoredata: dict = json.loads(line)
        scoredata['regions'] = json.loads(scoredata['regions'])
        # for i, region in enumerate(scoredata['regions']):
        #     scoredata['regions'][i] = json.loads(region)
        scoredata['page'] = json.loads(scoredata['page'])

        # check to see if every regions 'kern' will parse
        for i, region in enumerate(scoredata['regions']):
            numRegions += 1
            kern: str = region['kern']
            if kern:
                try:
                    kernScore: m21.stream.Score = m21.converter.parseData(
                        kern, format='humdrum', forceSource=True
                    )
                    numParts = len(list(kernScore.parts))
                    if not numParts:
                        print(f'{scoredata["file_name"]} region {i} is unparseable')
                        numUnparseable += 1
                    else:
                        numOK += 1
                except Exception:
                    print(f'{scoredata["file_name"]} region {i} crashed during parse')
                    numCrashes += 1
            else:
                print(f'{scoredata["file_name"]} region {i} is empty')
                numEmptyStrings += 1
        allscores.append(scoredata)

print(f'num unparseable regions = {numUnparseable}')
print(f'num empty kern strings = {numEmptyStrings}')
print(f'num crashes during parse = {numCrashes}')
print(f'num successful = {numOK}')
print('===========================================')
print(f'total regions = {numRegions}')

