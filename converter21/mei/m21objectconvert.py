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
from music21.common import OffsetQLIn  # , opFrac

# from converter21.mei import MeiExportError
from converter21.mei import MeiInternalError
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

    _M21_OCTAVE_CHANGE_TO_MEI_DIS_AND_DISPLACE: dict[int, tuple[str, str]] = {
        1: ('8', 'above'),
        -1: ('8', 'below'),
        2: ('15', 'above'),
        -2: ('15', 'below'),
        3: ('22', 'above'),
        -3: ('22', 'below')
    }

    @staticmethod
    def m21ClefToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.clef.Clef)
        if obj.sign is None or obj.sign == 'none':
            # no clef, nothing to see here
            return

        clefAttr: dict[str, str] = {'shape': obj.sign, 'line': str(obj.line)}
        if obj.octaveChange:
            dis: str
            disPlace: str
            dis, disPlace = (
                M21ObjectConvert._M21_OCTAVE_CHANGE_TO_MEI_DIS_AND_DISPLACE.get(
                    obj.octaveChange,
                    ('', '')
                )
            )
            if dis and disPlace:
                clefAttr['dis'] = dis
                clefAttr['dis.place'] = disPlace
        tb.start('clef', clefAttr)
        tb.end('clef')

    _M21_SHARPS_TO_MEI_SIG: dict[int, str] = {
        0: '0',
        1: '1s',
        2: '2s',
        3: '3s',
        4: '4s',
        5: '5s',
        6: '6s',
        7: '7s',
        8: '8s',
        9: '9s',
        10: '10s',
        11: '11s',
        12: '12s',
        -1: '1f',
        -2: '2f',
        -3: '3f',
        -4: '4f',
        -5: '5f',
        -6: '6f',
        -7: '7f',
        -8: '8f',
        -9: '9f',
        -10: '10f',
        -11: '11f',
        -12: '12f',
    }

    @staticmethod
    def m21KeySigToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.key.KeySignature)

        keySigAttr: dict[str, str] = {}

        if isinstance(obj, m21.key.Key):
            # we know tonic (aka pname) and mode
            m21Tonic: m21.pitch.Pitch = obj.tonic
            mode: str = obj.mode
            pname: str = str(m21Tonic.step).lower()
            if m21Tonic.accidental is not None:
                pname += M21ObjectConvert.m21AccidToMeiAccid(m21Tonic.accidental.modifier)

            if pname and mode:
                keySigAttr['pname'] = pname
                keySigAttr['mode'] = mode

        keySigAttr['sig'] = M21ObjectConvert._M21_SHARPS_TO_MEI_SIG.get(obj.sharps, '0')
        tb.start('keySig', keySigAttr)
        tb.end('keySig')

    @staticmethod
    def m21TimeSigToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.meter.TimeSignature)

        meterSigAttr: dict[str, str] = {}

        # This is a weird attribute order, but it matches what Verovio does,
        # which makes bbdiff comparisons work better.
        meterSigAttr['count'] = str(obj.numerator)

        if obj.symbol:
            # 'cut' or 'common' (both music21 and MEI use these terms)
            meterSigAttr['sym'] = obj.symbol

        meterSigAttr['unit'] = str(obj.denominator)

        tb.start('meterSig', meterSigAttr)
        tb.end('meterSig')


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
    def offsetToTstamp(
        offsetInScore: OffsetQLIn,
        offsetInMeasure: OffsetQLIn,
        meterStream: m21.stream.Stream[m21.meter.TimeSignature]
    ) -> str:
        raise MeiInternalError

    @staticmethod
    def offsetsToTstamp2(
        offset1InScore: OffsetQLIn,
        offset1InMeasure: OffsetQLIn,
        offset2InScore: OffsetQLIn,
        meterStream: m21.stream.Stream[m21.meter.TimeSignature]
    ) -> str:
        raise MeiInternalError

    @staticmethod
    def _fillInStandardPostStavesAttributes(
        attr: dict[str, str],
        first: m21.base.Music21Object,
        last: m21.base.Music21Object | None,
        staffNStr: str,
        m21Part: m21.stream.Part,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
    ):
        attr['staff'] = staffNStr  # 888 what about "1 2"

        if first is None:
            # we're done
            return

        if isinstance(first, m21.spanner.SpannerAnchor):
            attr['tstamp'] = M21ObjectConvert.offsetToTstamp(
                offsetInScore=first.getOffsetInHierarchy(m21Part),
                offsetInMeasure=first.getOffsetInHierarchy(m21Measure),
                meterStream=scoreMeterStream
            )
        else:
            attr['startid'] = f'#{first.id}'

        if last is None or last is first:
            # no unique last element, we're done
            return

        # unique last element, we need @tstamp2 or @endid
        if isinstance(last, m21.spanner.SpannerAnchor):
            attr['tstamp2'] = M21ObjectConvert.offsetsToTstamp2(
                offset1InScore=first.getOffsetInHierarchy(m21Part),
                offset1InMeasure=first.getOffsetInHierarchy(m21Measure),
                offset2InScore=last.getOffsetInHierarchy(m21Part),
                meterStream=scoreMeterStream
            )
        else:
            attr['endid'] = f'#{last.id}'

    @staticmethod
    def postStavesSpannerToMei(
        spanner: m21.spanner.Spanner,
        staffNStr: str,
        m21Part: m21.stream.Part,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
        tb: TreeBuilder
    ) -> None:
        first: m21.base.Music21Object = spanner.getFirst()
        last: m21.base.Music21Object = spanner.getLast()
        tag: str = ''
        attr: dict[str, str] = {}

        if isinstance(spanner, MeiBeamSpanner):
            if hasattr(spanner, 'mei_beam'):
                # already emitted as <beam> within <layer>
                return

        M21ObjectConvert._fillInStandardPostStavesAttributes(
            attr,
            first,
            last,
            staffNStr,
            m21Part,
            m21Measure,
            scoreMeterStream
        )

        if isinstance(spanner, m21.spanner.Slur):
            tag = 'slur'
        elif isinstance(spanner, m21.dynamics.DynamicWedge):
            tag = 'hairpin'
            if isinstance(spanner, m21.dynamics.Crescendo):
                attr['form'] = 'cres'
            else:
                attr['form'] = 'dim'
        elif isinstance(spanner, MeiBeamSpanner):
            tag = 'beamSpan'
            # set up plist for every spanned element (yes, even the ones that are already
            # in attr as 'startid' and 'endid')
            attr['plist'] = f'#{el.id for el in spanner.getSpannedElements()}'
        elif isinstance(spanner, m21.expressions.TrillExtension):
            tag = 'trill'
            if isinstance(first, m21.note.GeneralNote):
                # search first.expressions for a Trill, and if found emit that, too.
                for expr in first.expressions:
                    if isinstance(expr, m21.expressions.Trill):
                        # passing None for trillToMei's last param (tb) means "just
                        # add the Trill info to attr, I'll emit this <trill> myself".
                        M21ObjectConvert.trillToMei(
                            first,
                            expr,
                            staffNStr,
                            m21Part,
                            m21Measure,
                            scoreMeterStream,
                            tb=None,
                            attr=attr
                        )
                        # mark the Trill as handled, so when we see it during note.expressions
                        # processing, we won't emit it again.
                        expr.mei_trill_already_handled = True  # type: ignore
                        break

        if tag:
            tb.start(tag, attr)
            tb.end(tag)

    @staticmethod
    def trillToMei(
        gn: m21.note.GeneralNote,
        trill: m21.expressions.Trill,
        staffNStr: str,
        m21Part: m21.stream.Part,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
        tb: TreeBuilder | None,
        attr: dict[str, str] | None = None,
    ) -> None:
        # This can be called with a real TreeBuilder (not None). In that case, we do the full
        # job of emitting the <trill>.
        # This can be called with attr partly filled in, and tb is None (during TrillExtension
        # processing). In this case, we just add the Trill info to the attr dict.  One <trill>
        # will be emitted for both Trill and TrillExtension in that case, by the caller.
        if tb is not None:
            # do the full job (ignore any attr passed in, it should be None)
            attr = {}
            M21ObjectConvert._fillInStandardPostStavesAttributes(
                attr,
                gn,
                None,
                staffNStr,
                m21Part,
                m21Measure,
                scoreMeterStream
            )

        if attr is None:
            raise MeiInternalError('trillToMei called without attr or tree builder')

        # in both cases we add to attr here
        if trill.accidental is not None:
            accid: str = M21ObjectConvert.m21AccidToMeiAccid(trill.accidental.name)
            if trill.direction == 'up':
                attr['accidupper'] = accid
            else:
                attr['accidlower'] = accid

        if tb is not None:
            # do the full job
            tb.start('trill', attr)
            tb.end('trill')

    @staticmethod
    def turnToMei(
        gn: m21.note.GeneralNote,
        turn: m21.expressions.Turn,
        staffNStr: str,
        m21Part: m21.stream.Part,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
        tb: TreeBuilder,
    ) -> None:
        attr: dict[str, str] = {}
        M21ObjectConvert._fillInStandardPostStavesAttributes(
            attr,
            gn,
            None,
            staffNStr,
            m21Part,
            m21Measure,
            scoreMeterStream
        )

        if turn.upperAccidental is not None:
            accidupper: str = M21ObjectConvert.m21AccidToMeiAccid(turn.upperAccidental.name)
            attr['accidupper'] = accidupper
        if turn.lowerAccidental is not None:
            accidlower: str = M21ObjectConvert.m21AccidToMeiAccid(turn.lowerAccidental.name)
            attr['accidlower'] = accidlower

        if turn.isDelayed:
            print('delayed turn not yet implemented: emitting non-delayed turn')

        tb.start('turn', attr)
        tb.end('turn')

    @staticmethod
    def mordentToMei(
        gn: m21.note.GeneralNote,
        mordent: m21.expressions.GeneralMordent,
        staffNStr: str,
        m21Part: m21.stream.Part,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
        tb: TreeBuilder,
    ) -> None:
        attr: dict[str, str] = {}
        M21ObjectConvert._fillInStandardPostStavesAttributes(
            attr,
            gn,
            None,
            staffNStr,
            m21Part,
            m21Measure,
            scoreMeterStream
        )

        if mordent.accidental is not None:
            accid: str = M21ObjectConvert.m21AccidToMeiAccid(mordent.accidental.name)
            if mordent.direction == 'up':
                attr['accidupper'] = accid
            else:
                attr['accidlower'] = accid

        tb.start('mordent', attr)
        tb.end('mordent')

    @staticmethod
    def m21DynamicToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        print('Dynamic not yet implemented', file=sys.stderr)

    @staticmethod
    def m21TextExpressionToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        print('TextExpression not yet implemented', file=sys.stderr)

    @staticmethod
    def m21TempoIndicationToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        print('TempoIndication not yet implemented', file=sys.stderr)

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

    @staticmethod
    def streamElementBelongsInPostStaves(obj: m21.base.Music21Object) -> bool:
        if isinstance(obj, m21.stream.Stream):
            return False

        for className in obj.classes:
            if className in M21_OBJECT_CLASS_NAMES_FOR_POST_STAVES:
                return True

        return False

    @staticmethod
    def streamElementBelongsInLayer(obj: m21.base.Music21Object) -> bool:
        if isinstance(obj, m21.stream.Stream):
            return False

        for className in obj.classes:
            if className in M21_OBJECT_CLASS_NAMES_FOR_POST_STAVES:
                return False

        return True


class MeiBeamSpanner(m21.spanner.Spanner):
    pass


_M21_OBJECT_CONVERTER: dict[str, t.Callable[
    [m21.base.Music21Object, TreeBuilder],
    None]
] = {
    'Note': M21ObjectConvert.m21NoteToMei,
    'Chord': M21ObjectConvert.m21ChordToMei,
    'Rest': M21ObjectConvert.m21RestToMei,
    'Clef': M21ObjectConvert.m21ClefToMei,
    'KeySignature': M21ObjectConvert.m21KeySigToMei,
    'TimeSignature': M21ObjectConvert.m21TimeSigToMei,
    'Dynamic': M21ObjectConvert.m21DynamicToMei,
    'TextExpression': M21ObjectConvert.m21TextExpressionToMei,
    'TempoIndication': M21ObjectConvert.m21TempoIndicationToMei,
}

M21_OBJECT_CLASS_NAMES_FOR_POST_STAVES: list[str] = [
    # This does not include spanners, since spanners are handled separately.
    # This does not include ornaments, since ornaments are handled separately.
    # This only includes single objects that might be found directly in a Voice,
    # and that should not be emitted in the Voice's associated <layer>, but rather
    # saved for the post-staves elements.
    'Dynamic',
    'TextExpression',
    'TempoIndication',
]
