# ------------------------------------------------------------------------------
# Name:          abcwriter.py
# Purpose:       AbcWriter is an object that takes a music21 stream and
#                writes it to a file as ABC data.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2025 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
import music21 as m21
from converter21.shared import M21Utilities

class AbcExportError(Exception):
    pass

class AbcWriter:
    def __init__(self, obj: m21.prebase.ProtoM21Object) -> None:
        M21Utilities.adjustMusic21Behavior()

        self._m21Object: m21.prebase.ProtoM21Object = obj
        self._m21Score: m21.stream.Score | None = None

        # default options (these can be set to non-default values by clients,
        # as long as they do it before they call write())

        # client can set to False if obj is a Score
        self.makeNotation: bool = True

        # in future, client will be able to set to '2.1' or '2.2'.
        # Always 2.1 for now.
        self.abcVersion: str = '2.1'

    def write(self, fp) -> bool:
        if self.makeNotation:
            self._m21Score = M21Utilities.makeScoreFromObject(self._m21Object)
        else:
            if not isinstance(self._m21Object, m21.stream.Score):
                raise AbcExportError(
                    'Since makeNotation=False, source obj must be a music21 Score, and it is not.'
                )
            if not self._m21Object.isWellFormedNotation():
                print('Source obj is not well-formed; see isWellFormedNotation()', file=sys.stderr)

            self._m21Score = self._m21Object
        del self._m21Object  # everything after this uses self._m21Score

        # Now convert to MusicXML, then run that MusicXML through xml2abc.
        return True
