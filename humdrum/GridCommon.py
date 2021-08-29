# ------------------------------------------------------------------------------
# Name:          GridCommon.py
# Purpose:       Common enums: SliceType and MeasureStyle
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021 Greg Chapman
# License:       BSD, see LICENSE
# ------------------------------------------------------------------------------
from enum import IntEnum, unique, auto

# SliceType is a list of various Humdrum line types.  Groupings are
# segmented by categories which are prefixed with an underscore.
# For example Notes are in the _Duration group, since they have
# non-zero durations.  Notes and Gracenotes are in the _Data group.
# The indentation _would_ show the various types of groups, if python
# would let us indent.  You can see the indentation in the commented
# version.

#                 Notes = 1,
#             _Duration,
#                 GraceNotes,
#         _Data,
#             Measures,
#         _Measure,
#                 Stria,
#                 Clefs,
#                 Transpositions,
#                 KeyDesignations,
#                 KeySigs,
#                 TimeSigs,
#                 MeterSigs,
#                 Tempos,
#                 Labels,
#                 LabelAbbrs,
#                 Ottavas,
#             _RegularInterpretation,
#                 Exclusives,
#                 Terminators,
#                 Manipulators,
#             _Manipulator,
#         _Interpretation,
#             Layouts,
#             LocalComments,
#     _Spined,
#         GlobalComments,
#         GlobalLayouts,
#         ReferenceRecords,
#     _Other,
#         Invalid

@unique
class SliceType(IntEnum):
    Notes = 1                 # Duration, Data, Spined
    Duration_ = auto()
    GraceNotes = auto()       # Data, Spined
    Data_ = auto()
    Measures = auto()         # Measure, Spined
    Measure_ = auto()
    Stria = auto()            # Interpretation, RegularInterpretation, Spined
    Clefs = auto()            # Interpretation, RegularInterpretation, Spined
    Transpositions = auto()   # Interpretation, RegularInterpretation, Spined
    KeyDesignations = auto()  # Interpretation, RegularInterpretation, Spined
    KeySigs = auto()          # Interpretation, RegularInterpretation, Spined
    TimeSigs = auto()         # Interpretation, RegularInterpretation, Spined
    MeterSigs = auto()        # Interpretation, RegularInterpretation, Spined
    Tempos = auto()           # Interpretation, RegularInterpretation, Spined
    Labels = auto()           # Interpretation, RegularInterpretation, Spined
    LabelAbbrs = auto()       # Interpretation, RegularInterpretation, Spined
    Ottavas = auto()          # Interpretation, RegularInterpretation, Spined
    RegularInterpretation_ = auto()
    Exclusives = auto()       # Interpretation, Manipulator, Spined
    Terminators = auto()      # Interpretation, Manipulator, Spined
    Manipulators = auto()     # Interpretation, Manipulator, Spined
    Manipulator_ = auto()
    Interpretation_ = auto()
    Layouts = auto()          # Interpretation, Spined
    LocalComments = auto()    # Interpretation, Spined
    Spined_ = auto()
    GlobalComments = auto()   # Other (not Spined)
    GlobalLayouts = auto()    # Other (not Spined)
    ReferenceRecords = auto() # Other (not Spined)
    Other_ = auto()
    Invalid = auto()

# MeasureType is a list of the style types for a measure (ending type for now)

@unique
class MeasureStyle(IntEnum):
    Invisible = auto()
    Plain = auto()
    RepeatBackward = auto()
    RepeatForward = auto()
    RepeatBoth = auto()
    Double = auto()
    Final = auto()
