# converter21
A music21-extending converter package.  Currently contains an alternate music21 humdrum converter that completely replaces music21's humdrum parser, and adds the (until now) missing humdrum writer.

The Humdrum portion of this software is derived/translated from the C++ code in https://github.com/craigsapp/humlib, by Craig Stuart Sapp.

## Setup
Depends on music21, which should also be configured to display a musical score (e.g. with Musescore). Some of the tests depend on [musicdiff](https://github.com/gregchapman-dev/musicdiff.git), but converter21 itself does not.

## Usage
An example music file format conversion tool based on music21's conversion utilities can be found in [convertscore.py](convertscore.py).  This example shows you how to register converter21's humdrum converter so that music21 will use it in place of its own.  Thus, convertscore.py can convert to humdrum, even though music21 by itself cannot.

## License
Licensed under the [MIT license](LICENSE)
