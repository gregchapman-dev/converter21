# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Name:         mei/__init__.py
# Purpose:      MEI: The Music Encoding Initiative modules and classes
#
# Authors:      Greg Chapman
#
# Copyright:    Copyright © 2021-2022 Greg Chapman
# License:      BSD, see license.txt
# -----------------------------------------------------------------------------
'''
The :mod:`mei` module provides import from and export to MEI files for music21.
'''

from .meiexceptions import MeiValidityError
from .meiexceptions import MeiValueError
from .meiexceptions import MeiAttributeError
from .meiexceptions import MeiElementError
from .meiexceptions import MeiExportError
from .meiexceptions import MeiInternalError

from .m21objectconvert import M21ObjectConvert

from .meielement import MeiElement
from .meishared import MeiShared
from .meimetadatareader import MeiMetadataReader
from .meireader import MeiReader

from .meimetadata import MeiMetadataItem
from .meimetadata import MeiMetadata
from .meilayer import MeiLayer
from .meistaff import MeiStaff
from .meimeasure import MeiMeasure
from .meiscore import MeiScore
from .meiwriter import MeiWriter
