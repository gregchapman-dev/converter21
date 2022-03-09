# ------------------------------------------------------------------------------
# Purpose:       converter21 is a music21-based music notation file format converter CLI app,
#                and a new Humdrum subconverter plug-in
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------

__all__ = [
    'humdrum',
    'HumdrumConverter'
]

from .HumdrumConverter import HumdrumConverter
