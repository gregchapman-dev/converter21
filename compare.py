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
from timeit import default_timer as timer
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

#print('stack limit =', resource.getrlimit(resource.RLIMIT_STACK))
print('recursion limit =', sys.getrecursionlimit())

sys.setrecursionlimit(1024*1024)

#print('new stack limit =', resource.getrlimit(resource.RLIMIT_STACK))
print('new recursion limit =', sys.getrecursionlimit())

start = timer()
score1 = m21.converter.parse(args.file1, forceSource=True)
end = timer()
print('parse first file took:', end - start, 'seconds')

start = timer()
score2 = m21.converter.parse(args.file2, forceSource=True)
end = timer()
print('parse second file took:', end - start, 'seconds')

# build ScoreTrees
start = timer()
score_lin1 = nlin.Score(score1)
end = timer()
print('build first ScoreTree took:', end - start, 'seconds')

start = timer()
score_lin2 = nlin.Score(score2)
end = timer()
print('build second ScoreTree took:', end - start, 'seconds')

# compute the complete score diff
start = timer()
op_list, cost = scl.complete_scorelin_diff(score_lin1, score_lin2)
end = timer()
print('complete_scorelin_diff took:', end - start, 'seconds')

# annotate the scores to show differences
start = timer()
sv.annotate_differences(score1, score2, op_list)
end = timer()
print('annotate_differences took:', end - start, 'seconds')

# display the two annotated scores
start = timer()
sv.show_differences(score1, score2)
end = timer()
print('show_differences (both scores) took:', end - start, 'seconds')
print('')