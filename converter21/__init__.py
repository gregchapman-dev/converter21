# ------------------------------------------------------------------------------
# Purpose:       converter21 is a music21-based music notation file format converter CLI app,
#                along with new subconverter plug-ins for Humdrum and MEI.
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
    'mei',
    'HumdrumConverter',
    'MEIConverter',
]

import typing as t
from enum import IntEnum, auto

from .HumdrumConverter import HumdrumConverter
from .MEIConverter import MEIConverter

class ConverterName(IntEnum):
    HUMDRUM = auto()
    MEI = auto()

def register(
    *converterNames: ConverterName
):
    import music21 as m21

    # default (if no converterNames passed in) is to register everything we have
    if not converterNames:
        converterNames = (ConverterName.HUMDRUM, ConverterName.MEI)

    if ConverterName.HUMDRUM in converterNames:
        m21.converter.unregisterSubconverter(m21.converter.subConverters.ConverterHumdrum)
        m21.converter.registerSubconverter(HumdrumConverter)
    if ConverterName.MEI in converterNames:
        m21.converter.unregisterSubconverter(m21.converter.subConverters.ConverterMEI)
        m21.converter.registerSubconverter(MEIConverter)
