# ------------------------------------------------------------------------------
# Name:          converter21.py
# Purpose:       Command-line app to convert from any music file format to any another,
#                using music21's converter architecture.  Replaces music21's built-in
#                humdrum subconverter with ours, prior to doing any conversion.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021 Greg Chapman
# License:       BSD, see LICENSE
# ------------------------------------------------------------------------------
import argparse
import os
import sys

from music21 import converter
from humdrum.HumdrumConverter import HumdrumConverter

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
        print("Supported input formats are:")
        for subc in inList:
            if subc.registerInputExtensions:
                print('\tformats   : ' + ', '.join(subc.registerFormats)
                        + '\textensions: ' + ', '.join(subc.registerInputExtensions))
    else:
        outList = c.subconvertersList('output')
        print("Supported output formats are:")
        for subc in outList:
            if subc.registerOutputExtensions:
                print('\tformats   : ' + ', '.join(subc.registerFormats)
                        + '\textensions: ' + ', '.join(subc.registerOutputExtensions))

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
parser.add_argument("inputFile",
                    help="input music file to convert from (extension is used to determine "
                        + "input format if -if/--inputFormat is not specified")
parser.add_argument("outputFile",
                    help="output music file to convert to (extension is NOT used to "
                        + "determine/validate output format, so if you're not careful "
                        + "you'll end up with contents not matching extension)")
parser.add_argument("-if", "--inputFormat",
                    choices=getInputFormatsList(),
                    help="format of the input file (only necessary if inputFile has no "
                        + "supported extension)")
parser.add_argument("-of", "--outputFormat", required=True,
                    choices=getOutputFormatsList(),
                    help="format of the output file (required)")
parser.add_argument("-fs", "--forceSource", type=bool, default=True,
                    help="force complete parsing of input file, ignoring any cached parse")

args = parser.parse_args()

if args.inputFormat is None:
    # validate inputFile extension
    _, fileExt = os.path.splitext(args.inputFile)
    if fileExt not in getInputExtensionsList():
        print("Input file extension '{}' not supported unless inputFormat specified."
                .format(fileExt))
        printSupportedFormats('input')
        sys.exit(1)
else:
    # validate inputFormat
    if args.inputFormat not in getInputFormatsList():
        print("Input file format '{}' not supported.".format(args.inputFormat))
        printSupportedFormats('input')
        sys.exit(1)

# parse the inputFile
s = converter.parse(args.inputFile, format=args.inputFormat, forceSource=args.forceSource)

#s.show()
s.show('text')
s.show('musicxml.pdf')
#s.show('lilypond.pdf')

# check validity of outputFormat
if args.outputFormat not in getOutputFormatsList():
    print("Output format '{}' not supported.".format(args.outputFormat))
    printSupportedFormats('output')
    sys.exit(1)

# Validate outputFile extension by hand, and if necessary change it to be valid
# for the output format.
outputFile = args.outputFile
outFileName, outFileExt = os.path.splitext(outputFile)
validOutputExtList = getOutputExtensionsListForFormat(args.outputFormat)
if outFileExt not in validOutputExtList:
    # because we already checked the outputFormat, we can assume that there is a
    # valid extension for it
    outputFile = outFileName + getValidOutputExtensionForFormat(args.outputFormat)

s.write(fmt=args.outputFormat, fp=outputFile)
print("Success!  Output can be found in", outputFile)
