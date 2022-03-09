# ------------------------------------------------------------------------------
# Name:          convertscore.py
# Purpose:       Command-line app to convert from any music file format to any another,
#                using music21's converter architecture.  Replaces music21's built-in
#                humdrum subconverter with ours, prior to doing any conversion.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import argparse
import os
import sys

# import cProfile

from music21 import converter
from music21.base import VERSION_STR
from converter21 import HumdrumConverter

def getInputFormatsList() -> [str]:
    c = converter.Converter()
    inList = c.subconvertersList('input')
    result = []
    for subc in inList:
        if subc.registerInputExtensions: # if this subc supports input at all
            for form in subc.registerFormats:
                result.append(form)
    return result

def getInputExtensionsList() -> [str]:
    c = converter.Converter()
    inList = c.subconvertersList('input')
    result = []
    for subc in inList:
        for inputExt in subc.registerInputExtensions:
            result.append('.' + inputExt)
    return result

def getOutputFormatsList() -> [str]:
    c = converter.Converter()
    outList = c.subconvertersList('output')
    result = []
    for subc in outList:
        if subc.registerOutputExtensions: # if this subc supports output at all
            for form in subc.registerFormats:
                result.append(form)
    return result

def printSupportedFormats(whichList: str): # whichList should be 'input' or 'output'
    c = converter.Converter()
    if whichList == 'input':
        inList = c.subconvertersList('input')
        print('Supported input formats are:', file=sys.stderr)
        for subc in inList:
            if subc.registerInputExtensions:
                print('\tformats   : ' + ', '.join(subc.registerFormats)
                        + '\textensions: ' + ', '.join(subc.registerInputExtensions), file=sys.stderr)
    else:
        outList = c.subconvertersList('output')
        print('Supported output formats are:', file=sys.stderr)
        for subc in outList:
            if subc.registerOutputExtensions:
                print('\tformats   : ' + ', '.join(subc.registerFormats)
                        + '\textensions: ' + ', '.join(subc.registerOutputExtensions), file=sys.stderr)

def getValidOutputExtensionForFormat(form: str) -> str:
    c = converter.Converter()
    outList = c.subconvertersList('output')
    for subc in outList:
        if subc.registerOutputExtensions:
            if form in subc.registerFormats:
                return '.' + subc.registerOutputExtensions[0]
    return ''

def getOutputExtensionsListForFormat(form: str) -> [str]:
    c = converter.Converter()
    outList = c.subconvertersList('output')
    result = []
    for subc in outList:
        if subc.registerOutputExtensions:
            if form in subc.registerFormats:
                for outputExt in subc.registerOutputExtensions:
                    result.append('.' + outputExt)
    return result

# ------------------------------------------------------------------------------

'''
    main entry point (parse arguments and do conversion)
'''
# unregister built-in Humdrum converter, and replace with our better one
converter.unregisterSubconverter(converter.subConverters.ConverterHumdrum)
converter.registerSubconverter(HumdrumConverter)

parser = argparse.ArgumentParser()
parser.add_argument('input_file',
                    help=
'input music file to convert from (extension is used to determine '
                        + 'input format if --input-from/-f is not specified)')
parser.add_argument('output_file',
                    help='output music file to convert to (extension is NOT used to '
                        + 'determine/validate output format, so if you\'re not careful '
                        + 'you\'ll end up with contents not matching extension)')
parser.add_argument('-f', '--input-from',
                    choices=getInputFormatsList(),
                    help='format of the input file (only necessary if input file has no '
                        + 'supported extension)')
parser.add_argument('-t', '--output-to', required=True,
                    choices=getOutputFormatsList(),
                    help='format of the output file (required)')
parser.add_argument('-c', '--cached-parse-ok', action='store_true', default=False,
                    help='use cached parse of input file if it exists')

print('music21 version:', VERSION_STR, file=sys.stderr)
args = parser.parse_args()

if args.input_from is None:
    # can't parse stdin without input_from
    if args.input_file == '-':
        print('Input from stdin not supported unless input-from/-f specified', file=sys.stderr)
        sys.exit(1)

    # validate inputFile extension
    _, fileExt = os.path.splitext(args.input_file)
    if fileExt not in getInputExtensionsList():
        print(f'Input file extension \'{fileExt}\' not supported unless input-from/-f specified.', file=sys.stderr)
        printSupportedFormats('input')
        sys.exit(1)
else:
    # validate inputFormat
    if args.input_from not in getInputFormatsList():
        print(f'Input file format \'{args.input_from}\' not supported.', file=sys.stderr)
        printSupportedFormats('input')
        sys.exit(1)

# parse the inputFile
# cProfile.run('s = converter.parse(args.input_file, format=args.input_from,
#                                   forceSource = not args.cached_parse_ok)',
#              sort='cumulative')

# support stdin and stdout
if args.input_file == '-':
    args.input_file = sys.stdin.read() # args.input_file now contains the entire input as a string

s = converter.parse(args.input_file, format=args.input_from, forceSource = not args.cached_parse_ok)

#s.show('text')
#s.show('musicxml.pdf', makeNotation=False) # makeNotation=False only works with recent music21 v7
#s.show('lilypond.pdf')

# check validity of outputFormat
if args.output_to not in getOutputFormatsList():
    print('Output format \'{args.output_to}\' not supported.', file=sys.stderr)
    printSupportedFormats('output')
    sys.exit(1)

if args.output_file == '-':
    outputFile = None
else:
    # Validate outputFile extension by hand, and if necessary change it to be valid
    # for the output format.
    outputFile = args.output_file
    outFileName, outFileExt = os.path.splitext(outputFile)
    validOutputExtList = getOutputExtensionsListForFormat(args.output_to)
    if outFileExt not in validOutputExtList:
        # because we already checked the outputFormat, we can assume that there is a
        # valid extension for it
        outputFile = outFileName + getValidOutputExtensionForFormat(args.output_to)

# makeNotation=False only works with recent music21 v7
actualOutFile = s.write(fmt=args.output_to, fp=outputFile, makeNotation=False)
if outputFile is None:
    # read actualOutFile (a temp file in this case) into a string, and then write it to stdout
    with open(actualOutFile, encoding='utf-8') as f:
        outStr: str = f.read()
        sys.stdout.write(outStr)
else:
    print('Success!  Output can be found in', outputFile, file=sys.stderr)
