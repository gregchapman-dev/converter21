# ------------------------------------------------------------------------------
# Name:          abcreader.py
# Purpose:       AbcReader reads an ABC file, and converts it to a music21 stream.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2025 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import music21 as m21

class AbcReader:
    def __init__(self, dataString: str):
        self.dataString: str = dataString

    def run(self) -> m21.stream.Score | m21.stream.Part | m21.stream.Opus:
        # convert self.dataString (abc data) to musicxml data,
        # then import _that_ into music21.
        return m21.stream.Score()
