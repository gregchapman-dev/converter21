# ------------------------------------------------------------------------------
# Name:          meilayer.py
# Purpose:       MeiLayer is an object that represents a single music21
#                Voice (i.e. within a Measure). If there are no voices
#                within a given Measure, a single MeiLayer will be created
#                from the Measure itself.
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


# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

nextFreeVoiceNumber: int = 0

class MeiLayer:
    Debug: bool = False  # can be set to True for more debugging

    def __init__(
        self,
        m21Voice: m21.stream.Voice | m21.stream.Measure,
        meiParent  # MeiStaff
    ) -> None:
        from converter21.mei import MeiStaff
        self.m21Voice: m21.stream.Voice | m21.stream.Measure = m21Voice
        self.meiParent: MeiStaff = meiParent

    def makeRootElement(self, tb: TreeBuilder):
        # The following voice id fix-up code patterned after similar code in music21's
        # MusicXML writer.  The idea is to handle three cases (any or all of which
        # may be in play within any given measure):
        # 1. Someone has assigned integer voice.id values with great care (for cross-staff
        #       voices, for example).
        # 2. voice.id values have been left as default (mem address of voice). We need
        #       to fix them up to be reasonable low integers, unique within the parent
        #       MeiStaff.
        # 3. Someone has assigned string voice.id values with great care for some other
        #       reason, and we should simply use them.
        layerNStr: str = ''
        if isinstance(self.m21Voice, m21.stream.Voice):
            if (isinstance(self.m21Voice.id, int)
                    and self.m21Voice.id < m21.defaults.minIdNumberToConsiderMemoryLocation):
                # Someone assigned this voice id on purpose (tracking voice ids across
                # measures, for instance).  Use it, and set nextFreeVoiceNumber to use
                # the next available number (in case there are mem location ids later).
                layerNStr = str(self.m21Voice.id)
                self.meiParent.nextFreeVoiceNumber = self.m21Voice.id + 1
            elif isinstance(self.m21Voice.id, int):
                # This voice id is actually a memory location, so we need to change it
                # to a low number so it can be used in MEI.
                layerNStr = str(self.meiParent.nextFreeVoiceNumber)
                self.meiParent.nextFreeVoiceNumber += 1
            elif isinstance(self.m21Voice.id, str):
                layerNStr = self.m21Voice.id
            else:
                layerNStr = ''

        layerAttr: dict[str, str] = {}
        if layerNStr:
            layerAttr['n'] = layerNStr
        tb.start('layer', {'n': layerNStr})
        for el in self.m21Voice:
            M21ObjectConvert.convertM21ObjectToMei(el, tb)
        tb.end('layer')
