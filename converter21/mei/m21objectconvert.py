# ------------------------------------------------------------------------------
# Name:          m21objectconvert.py
# Purpose:       M21ObjectConvert is a static class full of utility routines
#                that convert between m21 objects and a series of calls to
#                an MEI tree builder.  There are also some simple conversion
#                routines for object attributes.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import sys
import typing as t
from xml.etree.ElementTree import TreeBuilder
from copy import deepcopy

import music21 as m21
# from music21.common import opFrac

# from converter21.mei import MeiExportError
# from converter21.mei import MeiInternalError
# from converter21.shared import M21Utilities

# For debug or unit test print, a simple way to get a string which is the current function name
# with a colon appended.
# for current func name, specify 0 or no argument.
# for name of caller of current func, specify 1.
# for name of caller of caller of current func, specify 2. etc.
# pylint: disable=protected-access
funcName = lambda n=0: sys._getframe(n + 1).f_code.co_name + ':'  # pragma no cover
# pylint: enable=protected-access

nextFreeVoiceNumber: int = 0

class M21ObjectConvert:

    @staticmethod
    def convertM21ObjectToMei(obj: m21.base.Music21Object, tb: TreeBuilder):
        convert: t.Callable[[m21.base.Music21Object, TreeBuilder], None] | None = (
            M21ObjectConvert._getM21ObjectConverter(obj)
        )
        if convert is not None:
            convert(obj, tb)

    @staticmethod
    def m21NoteToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.note.Note)
        M21ObjectConvert._noteToMei(obj, tb, withDuration=True)

    @staticmethod
    def m21ChordToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.chord.Chord)
        chordAttr: dict[str, str] = {'xml:id': str(obj.id)}
        grace: str = M21ObjectConvert.m21DurationToMeiDurDotsGrace(obj.duration, chordAttr)
        if grace:
            chordAttr['grace'] = grace
        tb.start('chord', chordAttr)
        for note in obj.notes:
            M21ObjectConvert._noteToMei(note, tb, withDuration=False)
        tb.end('chord')

    @staticmethod
    def m21RestToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.note.Rest)
        restAttr: dict[str, str] = {'xml:id': str(obj.id)}
        grace = M21ObjectConvert.m21DurationToMeiDurDotsGrace(obj.duration, restAttr)
        if grace:
            restAttr['grace'] = grace
        if obj.hasStyleInformation and obj.style.hideObjectOnPrint:
            tb.start('space', restAttr)
            tb.end('space')
        else:
            tb.start('rest', restAttr)
            tb.end('rest')

    @staticmethod
    def _noteToMei(note: m21.note.Note, tb: TreeBuilder, withDuration: bool) -> None:
        noteAttr: dict[str, str] = {'xml:id': str(note.id)}
        grace: str = ''
        if withDuration:
            # @dur, @dots, etc
            grace = M21ObjectConvert.m21DurationToMeiDurDotsGrace(note.duration, noteAttr)

        # @pname, @oct, @accid/@accid.ges
        noteAttr['oct'] = str(note.pitch.octave)
        noteAttr['pname'] = note.pitch.step.lower()

        if grace:
            noteAttr['grace'] = grace

        if note.pitch.accidental is None:
            # not strictly necessary, but verovio does it, so...
            noteAttr['accid.ges'] = 'n'
        else:
            if note.pitch.accidental.displayStatus:
                noteAttr['accid'] = (
                    M21ObjectConvert.m21AccidToMeiAccid(note.pitch.accidental.name)
                )
            else:
                noteAttr['accid.ges'] = (
                    M21ObjectConvert.m21AccidToMeiAccidGes(note.pitch.accidental.name)
                )

        tb.start('note', noteAttr)
        tb.end('note')

    _M21_DUR_TYPE_TO_MEI_DUR: dict[str, str] = {
        'maxima': 'maxima',
        'longa': 'long',
        'breve': 'breve',
        'whole': '1',
        'half': '2',
        'quarter': '4',
        'eighth': '8',
        '16th': '16',
        '32nd': '32',
        '64th': '64',
        '128th': '128',
        '256th': '256',
        '512th': '512',
        '1024th': '1024',
        '2048th': '2048',
    }

    @staticmethod
    def m21DurationToMeiDurDotsGrace(
        duration: m21.duration.Duration,
        attr: dict[str, str]
    ) -> str:
        # returns grace instead of putting it in attr
        # Note that the returned values ignore any tuplets (that's the way MEI likes it)
        dur: str = ''
        dots: str = ''
        durGes: str = ''
        dotsGes: str = ''
        grace: str = ''

        dur = M21ObjectConvert._M21_DUR_TYPE_TO_MEI_DUR.get(duration.type, '')
        if duration.dots:
            dots = str(duration.dots)

        if isinstance(duration, m21.duration.GraceDuration):
            if duration.slash:
                grace = 'unacc'
            else:
                grace = 'acc'
        elif not duration.linked:
            # duration is not linked and not grace, so we have to
            # compute @dur.ges and @dots.ges
            if duration.tuplets:
                nonTupletduration: m21.duration.Duration = deepcopy(duration)
                nonTupletduration.tuplets = tuple()
                newDuration = m21.duration.Duration(nonTupletduration.quarterLength)
            else:
                newDuration = m21.duration.Duration(duration.quarterLength)

            durGes = M21ObjectConvert._M21_DUR_TYPE_TO_MEI_DUR.get(newDuration.type, '')
            if newDuration.dots:
                dotsGes = str(newDuration.dots)

            # only emit @dur.ges or @dots.ges if different from @dur or @dots
            if durGes == dur:
                durGes = ''
            if dotsGes == dots:
                dotsGes = ''

        # all computed, put the relevant ones in the attr dict
        if dots:
            attr['dots'] = dots
        if dur:
            attr['dur'] = dur
        if dotsGes:
            attr['dots.ges'] = dotsGes
        if durGes:
            attr['dur.ges'] = durGes

        return grace

    _M21_ACCID_TO_MEI_ACCID: dict[str, str] = {
        'natural': 'n',
        'sharp': 's',
        'double-sharp': 'ss',
        'triple-sharp': 'ts',
        'flat': 'f',
        'double-flat': 'ff',
        'triple-flat': 'tf',
        'half-sharp': 'sd',
        'one-and-a-half-sharp': 'su',
        'half-flat': 'fu',
        'one-and-a-half-flat': 'fd',
    }

    _M21_ACCID_TO_MEI_ACCID_GES: dict[str, str] = {
        'natural': 'n',
        'sharp': 's',
        'double-sharp': 'ss',
        'flat': 'f',
        'double-flat': 'ff',
        'half-sharp': 'sd',
        'one-and-a-half-sharp': 'su',
        'half-flat': 'fu',
        'one-and-a-half-flat': 'fd',
    }

    @staticmethod
    def m21AccidToMeiAccid(m21Accid: str) -> str:
        if not m21.pitch.isValidAccidentalName(m21Accid):
            return ''
        output: str = M21ObjectConvert._M21_ACCID_TO_MEI_ACCID.get(
            m21.pitch.standardizeAccidentalName(m21Accid),
            ''
        )
        return output

    @staticmethod
    def m21AccidToMeiAccidGes(m21Accid: str) -> str:
        if not m21.pitch.isValidAccidentalName(m21Accid):
            return ''
        output: str = M21ObjectConvert._M21_ACCID_TO_MEI_ACCID_GES.get(
            m21.pitch.standardizeAccidentalName(m21Accid),
            ''
        )
        return output

    @staticmethod
    def _getM21ObjectConverter(
        obj: m21.base.Music21Object
    ) -> t.Callable[[m21.base.Music21Object, TreeBuilder], None] | None:
        if isinstance(obj, m21.stream.Stream):
            print(f'skipping unexpected stream object: {obj.classes[0]}')
            return None

        # obj.classes[0] is the most specific class name; we look for that first
        for className in obj.classes:
            if className in _M21_OBJECT_CONVERTER:
                return _M21_OBJECT_CONVERTER[className]

        return None


_M21_OBJECT_CONVERTER: dict[str, t.Callable[
    [m21.base.Music21Object, TreeBuilder],
    None]
] = {
    'Note': M21ObjectConvert.m21NoteToMei,
    'Chord': M21ObjectConvert.m21ChordToMei,
    'Rest': M21ObjectConvert.m21RestToMei,
}
