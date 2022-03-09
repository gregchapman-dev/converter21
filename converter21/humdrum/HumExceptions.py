# ------------------------------------------------------------------------------
# Name:          HumExceptions.py
# Purpose:       Exceptions that can be raised during Humdrum operations.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
class HumdrumSyntaxError(Exception):
    # poorly formed humdrum input
    pass

class HumdrumInternalError(Exception):
    # unexpected state during import or export
    pass

class HumdrumExportError(Exception):
    # error converting something to humdrum
    pass
