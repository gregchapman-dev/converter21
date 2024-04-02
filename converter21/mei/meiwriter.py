# ------------------------------------------------------------------------------
# Name:          meiwriter.py
# Purpose:       MeiWriter is an object that takes a music21 stream and
#                writes it to a file as MEI data.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
# import typing as t
from xml.etree.ElementTree import Element, ElementTree, indent

import music21 as m21
# from music21.common import opFrac

from converter21.mei import MeiExportError
# from converter21.mei import MeiInternalError
from converter21.mei import MeiScore

from converter21.shared import M21Utilities

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

class MeiWriter:
    Debug: bool = False  # can be set to True for more debugging

    def __init__(self, obj: m21.prebase.ProtoM21Object) -> None:
        M21Utilities.adjustMusic21Behavior()

        self._m21Object: m21.prebase.ProtoM21Object = obj
        self._m21Score: m21.stream.Score | None = None

        # default options (these can be set to non-default values by clients,
        # as long as they do it before they call write())

        # client can set to False if obj is a Score
        self.makeNotation: bool = True

        # client can set to '4' or '5' (or anything starting with '4' or '5')
        self.meiVersion: str = '5'

    def write(self, fp) -> bool:
        if self.makeNotation:
            self._m21Score = M21Utilities.makeScoreFromObject(self._m21Object)
        else:
            if not isinstance(self._m21Object, m21.stream.Score):
                raise MeiExportError(
                    'Since makeNotation=False, source obj must be a music21 Score, and it is not.'
                )
            if not self._m21Object.isWellFormedNotation():
                print('Source obj is not well-formed; see isWellFormedNotation()', file=sys.stderr)

            self._m21Score = self._m21Object
        del self._m21Object  # everything after this uses self._m21Score

        # Here we convert a music21 Score to an MeiScore. It's still all m21 objects, but
        # the object structure is MEI-like. For example:
        #   music21 scores are {Staff1(Measure1 .. MeasureN), Staff2(Measure1 .. MeasureN)}
        #   but MEI scores are {Measure1{Staff1, Staff2} .. MeasureN{Staff1, Staff2}}.
        meiScore: MeiScore = MeiScore(self._m21Score, self.meiVersion)

        # Here we convert the MeiScore to an in-memory tree of Elements
        meiElement: Element = meiScore.makeRootElement()
        indent(meiElement, space='   ', level=0)

        # Write to the output MEI XML file
        # pylint: disable=line-too-long
        prefix: str
        if self.meiVersion.startswith('4'):
            prefix = (
                '''<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="https://music-encoding.org/schema/4.0.1/mei-CMN.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>
<?xml-model href="https://music-encoding.org/schema/4.0.1/mei-CMN.rng" type="application/xml" schematypens="http://purl.oclc.org/dsdl/schematron"?>
'''
            )
        elif self.meiVersion.startswith('5'):
            prefix = (
                '''<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="https://music-encoding.org/schema/5.0/mei-CMN.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>
<?xml-model href="https://music-encoding.org/schema/5.0/mei-CMN.rng" type="application/xml" schematypens="http://purl.oclc.org/dsdl/schematron"?>
'''
            )
        else:
            raise MeiExportError(
                f'invalid meiVersion: {self.meiVersion}. Must start with \'4\' or \'5\'.'
            )
        # pylint: enable=line-too-long

        fp.write(prefix)
        ElementTree(meiElement).write(fp, encoding='unicode')
        fp.write('\n')

        # clean up all the notes-to-self MeiScore wrote in the score.
        meiScore.deannotateScore()

        return True
