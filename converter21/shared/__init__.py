# ------------------------------------------------------------------------------
# Purpose:       shared is a module of converter21 containing shared items for
#                use by the new subconverter plug-ins for Humdrum and MEI.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
__all__ = [
    'SharedConstants',
]

from .sharedconstants import SharedConstants
from .m21utilities import M21Utilities
from .m21utilities import M21StaffGroupTree
from .m21utilities import M21StaffGroupDescriptionTree
