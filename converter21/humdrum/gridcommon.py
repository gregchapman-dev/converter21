# ------------------------------------------------------------------------------
# Name:          GridCommon.py
# Purpose:       Common enums: SliceType and MeasureStyle
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
from enum import IntEnum, Enum, unique, auto

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
    Notes = 1                  # Duration, Data, Spined
    Duration_ = auto()
    GraceNotes = auto()        # Data, Spined
    Data_ = auto()
    Measures = auto()          # Measure, Spined
    Measure_ = auto()
    Stria = auto()             # Interpretation, RegularInterpretation, Spined
    Clefs = auto()             # Interpretation, RegularInterpretation, Spined
    Transpositions = auto()    # Interpretation, RegularInterpretation, Spined
    KeyDesignations = auto()   # Interpretation, RegularInterpretation, Spined
    KeySigs = auto()           # Interpretation, RegularInterpretation, Spined
    TimeSigs = auto()          # Interpretation, RegularInterpretation, Spined
    MeterSigs = auto()         # Interpretation, RegularInterpretation, Spined
    Tempos = auto()            # Interpretation, RegularInterpretation, Spined
    Labels = auto()            # Interpretation, RegularInterpretation, Spined
    LabelAbbrs = auto()        # Interpretation, RegularInterpretation, Spined
    Ottavas = auto()           # Interpretation, RegularInterpretation, Spined
    VerseLabels = auto()       # Interpretation, RegularInterpretation, Spined
    SectionNames = auto()      # Interpretation, RegularInterpretation, Spined
    RegularInterpretation_ = auto()
    Exclusives = auto()        # Interpretation, Manipulator, Spined
    Terminators = auto()       # Interpretation, Manipulator, Spined
    Manipulators = auto()      # Interpretation, Manipulator, Spined
    Manipulator_ = auto()
    Interpretation_ = auto()
    Layouts = auto()           # Spined
    LocalComments = auto()     # Spined
    Spined_ = auto()
    GlobalComments = auto()    # Other (not Spined)
    GlobalLayouts = auto()     # Other (not Spined)
    ReferenceRecords = auto()  # Other (not Spined)
    Other_ = auto()
    Invalid = auto()


@unique
class MeasureVisualStyle(IntEnum):
    # this enum is sorted so that we can use max() to pick between
    # previous right barline and current left barline visual style
    NoBarline = auto()
    Regular = auto()
    Double = auto()
    HeavyHeavy = auto()
    HeavyLight = auto()
    Final = auto()      # In MusicXML, this is called 'light-heavy'
    Short = auto()
    Tick = auto()
    Dotted = auto()
    Dashed = auto()
    Heavy = auto()
    # some special ones only used with RepeatBoth
    HeavyLightHeavy = auto()
    LightHeavyLight = auto()
    # Invisible comes last
    Invisible = auto()


@unique
class MeasureType(IntEnum):
    NotRepeat = auto()
    RepeatBackward = auto()
    RepeatForward = auto()
    RepeatBoth = auto()

# Each MeasureStyle enum value is a tuple = (MeasureVisualStyle, MeasureType)
class MeasureStyle(Enum):
    Double = (MeasureVisualStyle.Double, MeasureType.NotRepeat)
    HeavyHeavy = (MeasureVisualStyle.HeavyHeavy, MeasureType.NotRepeat)
    HeavyLight = (MeasureVisualStyle.HeavyLight, MeasureType.NotRepeat)
    Final = (MeasureVisualStyle.Final, MeasureType.NotRepeat)  # aka. 'light-heavy'
    Short = (MeasureVisualStyle.Short, MeasureType.NotRepeat)
    Tick = (MeasureVisualStyle.Tick, MeasureType.NotRepeat)
    Dotted = (MeasureVisualStyle.Dotted, MeasureType.NotRepeat)
    Dashed = (MeasureVisualStyle.Dashed, MeasureType.NotRepeat)
    Invisible = (MeasureVisualStyle.Invisible, MeasureType.NotRepeat)
    Regular = (MeasureVisualStyle.Regular, MeasureType.NotRepeat)
    Heavy = (MeasureVisualStyle.Heavy, MeasureType.NotRepeat)
    NoBarline = (MeasureVisualStyle.NoBarline, MeasureType.NotRepeat)

    RepeatBackwardRegular = (MeasureVisualStyle.Regular, MeasureType.RepeatBackward)
    RepeatBackwardHeavy = (MeasureVisualStyle.Heavy, MeasureType.RepeatBackward)
    RepeatBackwardHeavyLight = (MeasureVisualStyle.HeavyLight, MeasureType.RepeatBackward)
    RepeatBackwardFinal = (MeasureVisualStyle.Final, MeasureType.RepeatBackward)
    RepeatBackwardHeavyHeavy = (MeasureVisualStyle.HeavyHeavy, MeasureType.RepeatBackward)
    RepeatBackwardDouble = (MeasureVisualStyle.Double, MeasureType.RepeatBackward)

    RepeatForwardRegular = (MeasureVisualStyle.Regular, MeasureType.RepeatForward)
    RepeatForwardHeavy = (MeasureVisualStyle.Heavy, MeasureType.RepeatForward)
    RepeatForwardHeavyLight = (MeasureVisualStyle.HeavyLight, MeasureType.RepeatForward)
    RepeatForwardFinal = (MeasureVisualStyle.Final, MeasureType.RepeatForward)
    RepeatForwardHeavyHeavy = (MeasureVisualStyle.HeavyHeavy, MeasureType.RepeatForward)
    RepeatForwardDouble = (MeasureVisualStyle.Double, MeasureType.RepeatForward)

    RepeatBothRegular = (MeasureVisualStyle.Regular, MeasureType.RepeatBoth)
    RepeatBothHeavy = (MeasureVisualStyle.Heavy, MeasureType.RepeatBoth)
    RepeatBothHeavyLight = (MeasureVisualStyle.HeavyLight, MeasureType.RepeatBoth)
    RepeatBothFinal = (MeasureVisualStyle.Final, MeasureType.RepeatBoth)
    RepeatBothHeavyHeavy = (MeasureVisualStyle.HeavyHeavy, MeasureType.RepeatBoth)
    RepeatBothDouble = (MeasureVisualStyle.Double, MeasureType.RepeatBoth)

    RepeatBothHeavyLightHeavy = (MeasureVisualStyle.HeavyLightHeavy, MeasureType.RepeatBoth)
    RepeatBothLightHeavyLight = (MeasureVisualStyle.LightHeavyLight, MeasureType.RepeatBoth)

    # This is just here so clients can do blah.measureType and blah.measureVisualType instead
    # of having to know the layout of the tuple.
    def __init__(self, vStyle: MeasureVisualStyle, mType: MeasureType) -> None:
        self.vStyle = vStyle
        self.mType = mType

class FermataStyle(IntEnum):
    NoFermata = auto()
    Fermata = auto()
    FermataAbove = auto()
    FermataBelow = auto()
