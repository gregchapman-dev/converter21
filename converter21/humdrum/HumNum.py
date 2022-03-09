# ------------------------------------------------------------------------------
# Name:          HumNum.py
# Purpose:       Rational number representing (usually) a duration or offset
#                measured in quarter-notes.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
from fractions import Fraction

class HumNum(Fraction):
    pass # all we are is a rename of Fraction; added utility functions can be found in Convert.py
    # I couldn't figure out how to put the utility functions here, without also implementing
    # pass through versions of all math routines that returned HumNum(mathresult).
