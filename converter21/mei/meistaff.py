# ------------------------------------------------------------------------------
# Name:          meistaff.py
# Purpose:       MeiStaff is an object that represents a single music21
#                Part/PartStaff's contributions to a particular MeiMeasure.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
from xml.etree.ElementTree import TreeBuilder
# import typing as t

import music21 as m21
# from music21.common import opFrac

# from converter21.mei import MeiExportError
# from converter21.mei import MeiInternalError
# from converter21.shared import M21Utilities
from converter21.mei import M21ObjectConvert
from converter21.mei import MeiLayer

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class MeiStaff:
    Debug: bool = False  # can be set to True for more debugging

    def __init__(
        self,
        staffNStr: str,
        m21Measure: m21.stream.Measure,
        m21Part: m21.stream.Part
    ) -> None:
        self.staffNStr: str = staffNStr
        self.m21Measure = m21Measure
        self.m21Part = m21Part
        self.nextFreeVoiceNumber = 1
        self.layers: list[MeiLayer] = []
        self.theOneLayerIsTheMeasureItself = False

        voices: list[m21.stream.Voice | m21.stream.Measure]
        if m21Measure.voices:
            voices = list(m21Measure.voices)
        else:
            voices = [m21Measure]
            self.theOneLayerIsTheMeasureItself = True

        for voice in voices:
            self.layers.append(MeiLayer(voice, self))

    def makeRootElement(self, tb: TreeBuilder):
        self.nextFreeVoiceNumber = 1
        tb.start('staff', {'n': self.staffNStr})
        if not self.theOneLayerIsTheMeasureItself and self.m21Measure.offset != 0:
            # Process any clef/timesig/keysig at offset 0 in enclosing measure.
            # But only if the m21Measure itself is not the first measure in the m21Part.
            # These are separate because we'll have to make <staffdef> around them.
            staffDefDone: bool = False
            for el in self.m21Measure:
                if el.offset == 0:
                    if isinstance(el, (m21.clef.Clef, m21.meter.TimeSignature, m21.key.KeySignature)):
                        if not staffDefDone:
                            tb.start('staffDef', {'n': self.staffNStr})
                            staffDefDone = True
                        M21ObjectConvert.convertM21ObjectToMei(el, tb)
            if staffDefDone:
                tb.end('staffDef')

        for layer in self.layers:
            layer.makeRootElement(tb)

        # 888 process any final barline in the Measure (MeiStaff)

        tb.end('staffs')

    def makePostStavesElements(self, tb: TreeBuilder):
        # for el in self.m21Measure.recurse():
        #   make sure you get the stuff in the top-level measure
        #   blah blah blah
        return
