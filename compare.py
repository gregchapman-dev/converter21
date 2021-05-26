import music21 as m21
from pathlib import Path
import lib.score_visualization as sv
import lib.m21utils as m21u
import lib.NotationLinear as nlin
import lib.score_comparison_lib as scl
import json
import sys
import os
import resource
import argparse
from humdrum import HumdrumConverter

def getInputExtensionsList() -> [str]:
    c = m21.converter.Converter()
    inList = c.subconvertersList('input')
    result = []
    for subc in inList:
        for inputExt in subc.registerInputExtensions:
            result.append('.' + inputExt)
    return result

def printSupportedInputFormats():
    c = m21.converter.Converter()
    inList = c.subconvertersList('input')
    print("Supported input formats are:")
    for subc in inList:
        if subc.registerInputExtensions:
            print('\tformats   : ' + ', '.join(subc.registerFormats)
                    + '\textensions: ' + ', '.join(subc.registerInputExtensions))

# ------------------------------------------------------------------------------

'''
    main entry point (parse arguments and do conversion)
'''
# unregister built-in Humdrum converter, and replace with our better one
m21.converter.unregisterSubconverter(m21.converter.subConverters.ConverterHumdrum)
m21.converter.registerSubconverter(HumdrumConverter)

parser = argparse.ArgumentParser()
parser.add_argument("file1",
                    help="first music file to compare")
parser.add_argument("file2",
                    help="second music file to compare")

print('music21 version:', m21._version.__version__)
args = parser.parse_args()

# check file1 and file2 extensions for support within music21
badExt: bool = False
_, fileExt1 = os.path.splitext(args.file1)
_, fileExt2 = os.path.splitext(args.file2)

if fileExt1 not in getInputExtensionsList():
    print("file1 extension '{}' not supported.".format(fileExt1))
    badExt = True
if fileExt2 not in getInputExtensionsList():
    print("file2 extension '{}' not supported.".format(fileExt2))
    badExt = True
if badExt:
    printSupportedInputFormats()
    sys.exit(1)

print('stack limit =', resource.getrlimit(resource.RLIMIT_STACK))
#lower, maximum = resource.getrlimit(resource.RLIMIT_STACK)
print('recursion limit =', sys.getrecursionlimit())
# sys.exit(0)

#resource.setrlimit(resource.RLIMIT_STACK, (lower, maximum))
sys.setrecursionlimit(1024*1024)

print('new stack limit =', resource.getrlimit(resource.RLIMIT_STACK))
print('new recursion limit =', sys.getrecursionlimit())

score1 = m21.converter.parse(args.file1)
score2 = m21.converter.parse(args.file2)

# build ScoreTrees
score_lin1 = nlin.Score(score1)
score_lin2 = nlin.Score(score2)

# compute the complete score diff
op_list, cost = scl.complete_scorelin_diff(score_lin1, score_lin2)

# annotate the scores to show differences
sv.annotate_differences(score1, score2, op_list)

# display the two annotated scores
sv.show_differences(score1, score2)
