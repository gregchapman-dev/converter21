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
import typing as t

# HumNum is a type that can be float or Fraction.  The idea is that float
# should be used for performance (if exactly accurate), and Fraction will
# be used for accuracy (but only if necessary).
# music21.common.opFrac(num) will convert from int, float, or Fraction to
# the appropriate HumNum type (float or Fraction), and should be called on
# the result of any HumNum math, to get things back to the most performant
# type possible (given the newly computed value).
HumNum = t.Union[float, Fraction]

# HumNumIn is a type that can be converted to HumNum (int will turn into float,
# since it obviously can be accurately represented).
HumNumIn = t.Union[int, float, Fraction]
