# converter21
A music21-based music notation file format converter CLI app, and some new sub converter plug-ins

My initial goal here is to make a really accurate (and thorough) Humdrum importer and exporter for music21.

converter21.py is a general-purpose music21-based converter which also happens to use my Humdrum importer instead of music21's.

Examples of converter21.py usage can be seen below.

Convert humdrum file to musicxml format:

python3 converter21.py --output-to musicxml infile.krn outfile.musicxml

Same but specifying stdin and stdout (with '-'):

cat infile.krn | python3 converter21.py --input-from humdrum --output-to musicxml - - > outfile.musicxml

The Humdrum portion of this software is derived/translated from the C++ code in https://github.com/craigsapp/humlib, by Craig Stuart Sapp.
