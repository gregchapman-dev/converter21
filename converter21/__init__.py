# ------------------------------------------------------------------------------
# Purpose:       converter21 is a music21-based music notation file format converter CLI app,
#                along with new subconverter plug-ins for Humdrum and MEI.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------

__all__ = [
    'humdrum',
    'mei',
    'HumdrumConverter',
    'MEIConverter',
]

import typing as t
from enum import IntEnum, auto

from .HumdrumConverter import HumdrumConverter
from .MEIConverter import MEIConverter
from .shared import M21Utilities
from .shared import StreamFreezer
from .shared import StreamThawer

class Music21VersionException(Exception):
    # raised if the version of music21 is not recent enough
    pass

class ConverterName(IntEnum):
    HUMDRUM = auto()
    MEI = auto()

def register(
    *converterNames: ConverterName
):
    import music21 as m21

    if not M21Utilities.m21VersionIsAtLeast((9, 0, 0, 'a11')):
        raise Music21VersionException('music21 version needs to be 9.1 or greater')

    # default (if no converterNames passed in) is to register everything we have
    if not converterNames:
        converterNames = (ConverterName.HUMDRUM, ConverterName.MEI)

    # Currently this adjusts MusicXML import/export to handle more names for ChordSymbols
    # (this also allows converter21 to do so as well).
    M21Utilities.adjustMusic21Behavior()

    if ConverterName.HUMDRUM in converterNames:
        m21.converter.unregisterSubConverter(m21.converter.subConverters.ConverterHumdrum)
        m21.converter.registerSubConverter(HumdrumConverter)
    if ConverterName.MEI in converterNames:
        m21.converter.unregisterSubConverter(m21.converter.subConverters.ConverterMEI)
        m21.converter.registerSubConverter(MEIConverter)
