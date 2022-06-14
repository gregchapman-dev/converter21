import argparse
import os
import sys
import subprocess

from music21 import converter
from music21.base import VERSION_STR
from music21.musicxml.m21ToXml import ScoreExporter
from music21.musicxml.xmlToM21 import MusicXMLImporter
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
if __name__ == "__main__":
    # unregister music21's built-in Humdrum converter, and replace with ours
    converter.unregisterSubconverter(converter.subConverters.ConverterHumdrum)
    converter.registerSubconverter(HumdrumConverter)

    parser = argparse.ArgumentParser(
                prog='python3 -m converter21',
                description='Music score file format converter')
    parser.add_argument('input_file',
                        help=
    'input music file to convert from (extension is used to determine '
                            + 'input format if --input-from/-f is not specified)')
    parser.add_argument('-f', '--input-from',
                        choices=getInputFormatsList(),
                        help='format of the input file (only necessary if input file has no '
                            + 'supported extension)')

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

    # support stdin and stdout
    if args.input_file == '-':
        args.input_file = sys.stdin.read() # args.input_file now contains the entire input as a string

    # import from input file
    s0 = converter.parse(args.input_file, format=args.input_from, forceSource=True)

    # export to musicxml
    outFile1 = s0.write(fmt='musicxml', makeNotation=False)

    # import from new musicxml
    s1 = converter.parse(outFile1, forceSource=True)

    # export to input format
    outFile2 = s1.write(fmt=fileExt, makeNotation=False)
    # outFile2 = s0.write(fmt=fileExt, makeNotation=False)

    # bbdiff the first and last (both input format)
    subprocess.run(['bbdiff', str(args.input_file), str(outFile2)], check=False)

    print('Success!', file=sys.stderr)
