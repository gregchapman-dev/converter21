# converter21
A music21-extending converter package, and score conversion command line tool.  Contains an alternate music21 humdrum converter that adds a humdrum writer and replaces music21's humdrum parser.

The Humdrum portion of this software is derived/translated from the C++ code in [humlib](https://github.com/craigsapp/humlib), by Craig Stuart Sapp.

## Setup
Depends on [music21](https://pypi.org/project/music21), which should also be configured (instructions [here](https://web.mit.edu/music21/doc/usersGuide/usersGuide_01_installing.html)) to display a musical score (e.g. with Musescore). Some of the tests depend on [musicdiff](https://pypi.org/project/musicdiff), but converter21 itself does not.

## Command line tool usage:
```
python3 -m converter21 [-h]
                       [-f from_format]
                       -t to_format
                       [-c]
                       input_file output_file

Positional arguments:
  input_file            input music file to convert from (extension is used to determine input
                        format if --input-from/-f is not specified)
  output_file           output music file to convert to (extension is NOT used to determine or
                        validate output format, so if you're not careful you'll end up with
                        contents not matching the extension)

Named arguments:
  -h, --help            show help message and exit
  -f, --input-from {humdrum,musicxml,mei,abc...}
                        format of the input file (only necessary if input file has unsupported or
                        incorrect extension)
  -t, --output-to {humdrum,musicxml,lilypond,braille...}
                        format of the output file (required)
  -c, --cached-parse-ok
                        use music21's cached parse of the input file if it exists
```

## API usage:

See `converter21/__main__.py` (the source code for the command line tool) for an example of how to get music21 to use converter21's alternate Humdrum converter in your own code.

## License
The MIT License (MIT)
Copyright (c) 2021-2022 Greg Chapman

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

The Humdrum parsing portion of this software is derived/translated from the
C++ code in [humlib](https://github.com/craigsapp/humlib), which uses the BSD 2-Clause
License:

Copyright (c) 2015-2021 Craig Stuart Sapp
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   and the following disclaimer in the documentation and/or other materials
   provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
