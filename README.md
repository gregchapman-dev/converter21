# converter21
A music21-based music notation file format converter CLI app, and some new sub converter plug-ins

My initial goal here is to make a really accurate (and thorough) Humdrum importer and exporter for music21.

converter21.py is a general-purpose music21-based converter which also happens to use my Humdrum importer instead of music21's.

Usage of CLI script (converter21.py):

python3 converter21.py inputfile outputfile -of outputformat

Example (convert humdrum file to musicxml format):

python3 converter21.py infile.krn outfile.xml -of musicxml

The Humdrum portion of this software is derived/translated from the C++ code in https://github.com/craigsapp/humlib, by Craig Stuart Sapp.
