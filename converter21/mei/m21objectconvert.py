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
import re
import typing as t
# from copy import deepcopy
# from xml.etree.ElementTree import TreeBuilder

import music21 as m21
from music21.common import OffsetQLIn, OffsetQL
from music21.common.numberTools import opFrac

# from converter21.mei import MeiExportError
from converter21.mei import MeiInternalError
from converter21.shared import M21BeamSpanner
from converter21.shared import M21TupletSpanner
from converter21.shared import M21TieSpanner
from converter21.shared import M21Utilities
from converter21.shared import SharedConstants
from converter21.shared import DebugTreeBuilder as TreeBuilder

environLocal = m21.environment.Environment('converter21.mei.m21objectconvert')

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
    def convertM21ObjectToMei(
        obj: m21.base.Music21Object,
        spannerBundle: m21.spanner.SpannerBundle,
        tb: TreeBuilder
    ):
        convert: t.Callable[
            [m21.base.Music21Object, m21.spanner.SpannerBundle, TreeBuilder],
            None
        ] | None = (
            M21ObjectConvert._getM21ObjectConverter(obj)
        )
        if convert is not None:
            convert(obj, spannerBundle, tb)

    @staticmethod
    def m21NoteToMei(
        obj: m21.base.Music21Object,
        spannerBundle: m21.spanner.SpannerBundle,
        tb: TreeBuilder
    ) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, (m21.note.Note, m21.note.Unpitched))
        M21ObjectConvert._noteToMei(obj, spannerBundle, tb, withDuration=True)

    @staticmethod
    def _addStemMod(obj: m21.note.NotRest, attr: dict[str, str]):
        if hasattr(obj, 'mei_stem_mod'):
            # 888 nowhere in mei exporter does 'mei_stem_mod' get set.
            stemMod: str = getattr(obj, 'mei_stem_mod')
            attr['stem.mod'] = stemMod

    @staticmethod
    def _addBreakSec(obj: m21.note.NotRest, attr: dict[str, str]):
        if hasattr(obj, 'mei_breaksec'):
            num: int = getattr(obj, 'mei_breaksec')
            if num > 0:
                attr['breaksec'] = str(num)

    @staticmethod
    def _addTupletAttribute(
        obj: m21.note.GeneralNote,
        spannerBundle: m21.spanner.SpannerBundle,
        attr: dict[str, str]
    ):
        tupletSpanners: list[m21.spanner.Spanner] = obj.getSpannerSites([M21TupletSpanner])
        for tuplet in tupletSpanners:
            if not M21Utilities.isIn(tuplet, spannerBundle):
                continue
            if hasattr(tuplet, 'mei_tuplet'):
                # tuplet is handled by <tuplet> element, no need for @tuplet attributes
                continue

            if tuplet.isFirst(obj):
                attr['tuplet'] = 'i1'
            elif tuplet.isLast(obj):
                attr['tuplet'] = 't1'
            else:
                attr['tuplet'] = 'm1'

    @staticmethod
    def _addStylisticAttributes(
        obj: m21.base.Music21Object | m21.style.StyleMixin,
        attr: dict[str, str]
    ):
        if isinstance(obj, m21.note.NotRest):
            if obj.stemDirection == 'noStem':
                attr['stem.visible'] = 'false'
            elif obj.stemDirection in ('up', 'down'):
                attr['stem.dir'] = obj.stemDirection

        if isinstance(obj, (m21.note.Note, m21.note.Unpitched)):
            if obj.notehead == 'cross':
                attr['head.shape'] = '+'
            elif obj.notehead == 'diamond':
                attr['head.shape'] = 'diamond'
            elif obj.notehead == 'triangle':
                attr['head.shape'] = 'isotriangle'
            elif obj.notehead == 'rectangle':
                attr['head.shape'] = 'rectangle'
            elif obj.notehead == 'slash':
                attr['head.shape'] = 'slash'
            elif obj.notehead == 'square':
                attr['head.shape'] = 'square'
            elif obj.notehead == 'x':
                attr['head.shape'] = 'x'

        # placement (we pass obj because placement might be in obj or obj.style)
        place: str | None = M21ObjectConvert.m21PlacementToMei(obj)
        if place:
            if isinstance(obj, m21.spanner.Slur):
                attr['curvedir'] = place
            else:
                attr['place'] = place

        style: m21.style.Style | None = None
        if obj.hasStyleInformation:
            style = obj.style

        if style is not None:
            if style.hideObjectOnPrint:
                attr['visible'] = 'false'
            if style.color:
                attr['color'] = style.color
            if isinstance(style, m21.style.NoteStyle):
                if style.noteSize == 'cue':
                    attr['cue'] = 'true'

    @staticmethod
    def m21PlacementToMei(obj: m21.base.Music21Object | m21.style.StyleMixin) -> str | None:
        style: m21.style.Style | None = None
        if obj.hasStyleInformation:
            style = obj.style
        objHasPlacement: bool = hasattr(obj, 'placement')
        styleHasPlacement: bool = style is not None and hasattr(style, 'placement')

        alignVertical: str = ''
        if style is not None and hasattr(style, 'alignVertical'):
            alignVertical = getattr(style, 'alignVertical')

        placement: str | None = None
        if objHasPlacement:
            placement = getattr(obj, 'placement')
        elif styleHasPlacement:
            placement = getattr(style, 'placement')

        if placement is None:
            # last chance for placement (but only if obj or style has a .placement
            # field) is style.absoluteY > or < 0
            if not objHasPlacement and not styleHasPlacement:
                return None
            if style is None or style.absoluteY is None:
                return None

            if style.absoluteY > 0:
                placement = 'above'
            elif style.absoluteY < 0:
                placement = 'below'

        if placement == 'below' and alignVertical == 'middle':
            if not isinstance(obj, m21.spanner.Slur):
                return 'between'

        if placement in ('above', 'below'):
            return placement

        return None

    @staticmethod
    def convertM21ObjectToMeiSameAs(obj: m21.base.Music21Object, tb: TreeBuilder):
        if not isinstance(obj, (m21.clef.Clef, m21.meter.TimeSignature, m21.key.KeySignature)):
            raise MeiInternalError('convertM21ObjectToMeiSameAs only supports clef/timesig/keysig')

        # This obj has already been emitted with the appropriate xml:id, and here
        # we just emit a stub object with @sameas set to that same xml:id.
        attr: dict[str, str] = {'sameas': M21Utilities.getXmlId(obj, required=True)}
        if isinstance(obj, m21.clef.Clef):
            tb.start('clef', attr)
            tb.end('clef')
        elif isinstance(obj, m21.meter.TimeSignature):
            tb.start('meterSig', attr)
            tb.end('meterSig')
        elif isinstance(obj, m21.key.KeySignature):
            tb.start('keySig', attr)
            tb.end('keySig')
        else:
            raise MeiInternalError('unsupported @sameas object type: {obj.classes[0]}')

    @staticmethod
    def m21ChordToMei(
        obj: m21.base.Music21Object,
        spannerBundle: m21.spanner.SpannerBundle,
        tb: TreeBuilder
    ) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.chord.Chord)
        attr: dict[str, str] = {}
        xmlId: str = M21Utilities.getXmlId(obj)
        if xmlId:
            attr['xml:id'] = xmlId

        inFTrem: bool = False
        if hasattr(obj, 'mei_in_ftrem'):
            inFTrem = getattr(obj, 'mei_in_ftrem')
        M21ObjectConvert.m21DurationToMeiDurDotsGrace(obj.duration, attr, inFTrem=inFTrem)
        M21ObjectConvert._addTupletAttribute(obj, spannerBundle, attr)
        M21ObjectConvert._addBreakSec(obj, attr)
        M21ObjectConvert._addStylisticAttributes(obj, attr)
        M21ObjectConvert._addStemMod(obj, attr)

        tb.start('chord', attr)
        M21ObjectConvert.m21ArticulationsToMei(obj.articulations, tb)
        M21ObjectConvert.m21LyricsToMei(obj.lyrics, tb)
        for note in obj.notes:
            M21ObjectConvert._noteToMei(note, spannerBundle, tb, withDuration=False)
        tb.end('chord')

    @staticmethod
    def m21RestToMei(
        obj: m21.base.Music21Object,
        spannerBundle: m21.spanner.SpannerBundle,
        tb: TreeBuilder
    ) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.note.Rest)
        attr: dict[str, str] = {}

        xmlId: str = M21Utilities.getXmlId(obj)
        if xmlId:
            attr['xml:id'] = xmlId
        M21ObjectConvert.m21DurationToMeiDurDotsGrace(obj.duration, attr)
        M21ObjectConvert._addTupletAttribute(obj, spannerBundle, attr)

        oloc: str = getattr(obj, 'mei_oloc', '')
        ploc: str = getattr(obj, 'mei_ploc', '')
        if oloc and ploc:
            attr['ploc'] = ploc
            attr['oloc'] = oloc

        M21ObjectConvert._addStylisticAttributes(obj, attr)

        if obj.hasStyleInformation and obj.style.hideObjectOnPrint:
            attr.pop('visible', None)  # remove @visible="false", since <space> is always invisible
            tb.start('space', attr)
            tb.end('space')
        else:
            tb.start('rest', attr)
            tb.end('rest')

    @staticmethod
    def meiLocToM21DisplayName(
        locStr: str
    ) -> str:
        loc: int = 0
        if locStr:
            try:
                loc = int(locStr)
            except Exception:
                pass

        # loc=0 is bottom line of treble clef (E4); -1 = D4, +1 = F4, etc

        # Convert to base7 (so 0 is C0).
        loc += 30  # add 4 base7 octaves (4*7) plus distance from C to E (2) so 0 is C0

        # now we can easily get the display name
        displayName: str = M21Utilities.base7ToDisplayName(loc)
        return displayName

    @staticmethod
    def m21DisplayPitchToMeiLoc(
        m21Pitch: m21.pitch.Pitch
    ) -> str:
        base7: int = M21Utilities.pitchToBase7(m21Pitch)

        # base7 == 0 is C0
        # loc == 0 is E4
        # Conversion from base7 to loc is simple subtraction:
        #   subtract 4 base7 octaves (4*7) and distance from C to E (2)
        loc: int = base7 - 30
        return str(loc)

    _OTTAVA_TYPE_TO_OCTAVE_SHIFT: dict[str, int] = {
        '8va': +1,
        '8vb': -1,
        '15ma': +2,
        '15mb': -2,
        '22da': +3,
        '22db': -3
    }

    @staticmethod
    def _getOttavaShiftAndTransposing(
        gn: m21.note.GeneralNote,
        spannerBundle: m21.spanner.SpannerBundle
    ) -> tuple[int, bool]:
        for spanner in gn.getSpannerSites():
            if not M21Utilities.isIn(spanner, spannerBundle):
                continue
            if isinstance(spanner, m21.spanner.Ottava):
                return (
                    M21ObjectConvert._OTTAVA_TYPE_TO_OCTAVE_SHIFT[spanner.type],
                    spanner.transposing
                )
        return 0, True

    @staticmethod
    def _noteToMei(
        note: m21.note.Note | m21.note.Unpitched,
        spannerBundle: m21.spanner.SpannerBundle,
        tb: TreeBuilder,
        withDuration: bool
    ) -> None:
        attr: dict[str, str] = {}
        xmlId: str = M21Utilities.getXmlId(note)
        if xmlId:
            attr['xml:id'] = xmlId

        M21ObjectConvert._addStemMod(note, attr)

        if withDuration:
            inFTrem: bool = False
            if hasattr(note, 'mei_in_ftrem'):
                inFTrem = getattr(note, 'mei_in_ftrem')
            M21ObjectConvert.m21DurationToMeiDurDotsGrace(note.duration, attr, inFTrem=inFTrem)
            M21ObjectConvert._addTupletAttribute(note, spannerBundle, attr)

        if isinstance(note, m21.note.Unpitched):
            loc: str = M21ObjectConvert.m21DisplayPitchToMeiLoc(note.displayPitch())
            attr['loc'] = loc
        else:
            # @pname, @oct, @accid/@accid.ges
            attr['pname'] = note.pitch.step.lower()
            octaveShift: int
            ottavaTransposes: bool
            octaveShift, ottavaTransposes = (
                M21ObjectConvert._getOttavaShiftAndTransposing(note, spannerBundle)
            )
            if octaveShift == 0:
                attr['oct'] = str(note.pitch.implicitOctave)
            else:
                # there is an ottava in play, does it transpose or not?
                if ottavaTransposes:
                    attr['oct'] = str(note.pitch.implicitOctave)
                    attr['oct.ges'] = str(note.pitch.implicitOctave + octaveShift)
                else:
                    attr['oct'] = str(note.pitch.implicitOctave - octaveShift)
                    attr['oct.ges'] = str(note.pitch.implicitOctave)

        M21ObjectConvert._addBreakSec(note, attr)
        M21ObjectConvert._addStylisticAttributes(note, attr)

        if isinstance(note, m21.note.Note):
            if note.pitch.accidental is not None:
                if note.pitch.accidental.displayStatus:
                    attr['accid'] = (
                        M21ObjectConvert.m21AccidToMeiAccid(note.pitch.accidental.name)
                    )
                else:
                    accidGes: str = (
                        M21ObjectConvert.m21AccidToMeiAccidGes(note.pitch.accidental.name)
                    )
                    if accidGes and accidGes != 'n':
                        attr['accid.ges'] = accidGes

        tb.start('note', attr)
        M21ObjectConvert.m21ArticulationsToMei(note.articulations, tb)
        M21ObjectConvert.m21LyricsToMei(note.lyrics, tb)
        tb.end('note')

    @staticmethod
    def m21LyricsToMei(lyrics: list[m21.note.Lyric], tb: TreeBuilder):
        for verse in lyrics:
            attr: dict[str, str] = {}
            label: str = ''
            if verse.number:
                attr['n'] = str(verse.number)
            if verse.identifier and verse.identifier != verse.number:
                label = str(verse.identifier)
            M21ObjectConvert._addStylisticAttributes(verse, attr)

            tb.start('verse', attr)
            if label:
                tb.start('label', {})
                tb.data(label)
                tb.end('label')
            if verse.isComposite:
                if t.TYPE_CHECKING:
                    assert verse.components is not None
                # multiple <syl> must be generated
                for syl in verse.components:
                    M21ObjectConvert.m21SyllableToMei(syl, tb)
            else:
                # just one <syl>
                M21ObjectConvert.m21SyllableToMei(verse, tb)
            tb.end('verse')

    _M21_SYLLABIC_TO_WORD_POS: dict[
        t.Literal['begin', 'middle', 'end', 'composite', 'single'] | None,
        str | None
    ] = {
        'begin': 'i',
        'middle': 'm',
        'end': 't',
        'composite': None,
        'single': None,
        None: None
    }

    @staticmethod
    def m21SyllableToMei(lyric: m21.note.Lyric, tb: TreeBuilder):
        attr: dict[str, str] = {}
        wordPos: str | None = M21ObjectConvert._M21_SYLLABIC_TO_WORD_POS.get(lyric.syllabic, None)
        if wordPos:
            attr['wordpos'] = wordPos

        style: m21.style.TextStylePlacement | None = None
        if lyric.hasStyleInformation:
            if t.TYPE_CHECKING:
                assert isinstance(lyric.style, m21.style.TextStylePlacement)
            style = lyric.style

        M21ObjectConvert.emitStyledTextElement(
            lyric.text,
            style,
            'syl',
            attr,
            tb
        )

    _M21_ARTICULATION_NAME_TO_MEI_ARTIC_NAME: dict[str, str] = {
        'accent': 'acc',
        'staccato': 'stacc',
        'tenuto': 'ten',
        'staccatissimo': 'stacciss',
        'spiccato': 'spicc',
        'down bow': 'dnbow',
        'up bow': 'upbow',
        'harmonic': 'harm',
        'snap pizzicato': 'snap',
        'strong accent': 'marc',
        'doit': 'doit',
        'plop': 'plop',
        'falloff': 'fall',
        'stopped': 'stop',
        'open string': 'open',
        'double tongue': 'dbltongue',
        'triple tongue': 'trpltongue',
        'organ toe': 'toe',
        'organ heel': 'heel',
    }

    @staticmethod
    def m21ArticulationsToMei(
        articulations: list[m21.articulations.Articulation],
        tb
    ):
        for artic in articulations:
            name: str = (
                M21ObjectConvert._M21_ARTICULATION_NAME_TO_MEI_ARTIC_NAME.get(
                    artic.name,
                    ''
                )
            )
            attr: dict[str, str] = {}  # above/below, etc
            xmlId: str = M21Utilities.getXmlId(artic)
            if xmlId:
                attr['xml:id'] = xmlId
            if name:
                attr['artic'] = name
                M21ObjectConvert._addStylisticAttributes(artic, attr)
                tb.start('artic', attr)
                tb.end('artic')


    _M21_OCTAVE_CHANGE_TO_MEI_DIS_AND_DISPLACE: dict[int, tuple[str, str]] = {
        1: ('8', 'above'),
        -1: ('8', 'below'),
        2: ('15', 'above'),
        -2: ('15', 'below'),
        3: ('22', 'above'),
        -3: ('22', 'below')
    }

    _M21_CLEF_SIGN_TO_MEI_CLEF_SHAPE: dict[str, str] = {
        'percussion': 'perc'
    }

    @staticmethod
    def m21ClefToMei(
        obj: m21.base.Music21Object,
        spannerBundle: m21.spanner.SpannerBundle,
        tb: TreeBuilder
    ) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.clef.Clef)
        if obj.sign is None or obj.sign == 'none':
            # no clef, nothing to see here
            return

        if hasattr(obj, 'mei_handled_already'):
            return

        attr: dict[str, str] = {}
        xmlId: str = M21Utilities.getXmlId(obj)
        if xmlId:
            attr['xml:id'] = xmlId

        # default to shape == sign
        shape: str = M21ObjectConvert._M21_CLEF_SIGN_TO_MEI_CLEF_SHAPE.get(obj.sign, obj.sign)
        if shape:
            attr['shape'] = shape

        if obj.line is not None:
            attr['line'] = str(obj.line)

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
                attr['dis'] = dis
                attr['dis.place'] = disPlace

        M21ObjectConvert._addStylisticAttributes(obj, attr)
        tb.start('clef', attr)
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
    def m21KeySigToMei(
        obj: m21.base.Music21Object,
        spannerBundle: m21.spanner.SpannerBundle,
        tb: TreeBuilder
    ) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.key.KeySignature)

        if hasattr(obj, 'mei_handled_already'):
            return

        attr: dict[str, str] = {}
        xmlId: str = M21Utilities.getXmlId(obj)
        if xmlId:
            attr['xml:id'] = xmlId

        if isinstance(obj, m21.key.Key):
            # we know tonic (aka pname) and mode
            m21Tonic: m21.pitch.Pitch = obj.tonic
            mode: str = obj.mode
            pname: str = str(m21Tonic.step).lower()
            accid: str = ''
            if m21Tonic.accidental is not None:
                accid = M21ObjectConvert.m21AccidToMeiAccid(m21Tonic.accidental.modifier)

            if pname and mode:
                attr['pname'] = pname
                attr['mode'] = mode
                if accid:
                    attr['accid'] = accid

        attr['sig'] = M21ObjectConvert._M21_SHARPS_TO_MEI_SIG.get(obj.sharps, '0')
        M21ObjectConvert._addStylisticAttributes(obj, attr)
        tb.start('keySig', attr)
        tb.end('keySig')

    @staticmethod
    def m21TimeSigToMei(
        obj: m21.base.Music21Object,
        spannerBundle: m21.spanner.SpannerBundle,
        tb: TreeBuilder
    ) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.meter.TimeSignature)

        if hasattr(obj, 'mei_handled_already'):
            return

        attr: dict[str, str] = {}
        xmlId: str = M21Utilities.getXmlId(obj)
        if xmlId:
            attr['xml:id'] = xmlId

        # This is a weird attribute order, but it matches what Verovio does,
        # which makes bbdiff comparisons work better.
        attr['count'] = str(obj.numerator)

        if obj.symbol:
            # 'cut' or 'common' (both music21 and MEI use these terms)
            attr['sym'] = obj.symbol

        attr['unit'] = str(obj.denominator)

        M21ObjectConvert._addStylisticAttributes(obj, attr)
        tb.start('meterSig', attr)
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
        attr: dict[str, str],
        inFTrem: bool = False
    ):
        # Note that the returned values ignore any tuplets (that's the way MEI likes it)
        dur: str = ''
        dots: str = ''
        durGes: str = ''
        dotsGes: str = ''
        grace: str = ''

        dur = M21ObjectConvert._M21_DUR_TYPE_TO_MEI_DUR.get(duration.type, '')
        dots = str(duration.dots)

        if isinstance(duration, m21.duration.AppoggiaturaDuration):
            grace = 'acc'
        elif isinstance(duration, m21.duration.GraceDuration):
            # might be accented or unaccented.  duration.slash isn't always reliable
            # (historically), but we can use it as a fallback.
            # Check duration.stealTimePrevious and duration.stealTimeFollowing first.
            if duration.stealTimePrevious is not None:
                grace = 'unacc'
            elif duration.stealTimeFollowing is not None:
                grace = 'acc'
            elif duration.slash is True:
                grace = 'unacc'
            elif duration.slash is False:
                grace = 'acc'
            else:
                # by default, GraceDuration with no other indications (slash is None)
                # is assumed to be unaccented.
                grace = 'unacc'
        elif not duration.linked:
            # duration is not linked and not grace, so we have to
            # compute @dur.ges and @dots.ges
            gesQL: OffsetQL = 0.0
            if duration.tuplets:
                mult: OffsetQL = 1.0
                for tuplet in duration.tuplets:
                    mult = opFrac(mult * tuplet.tupletMultiplier())
                gesQL = duration.quarterLength / mult
            else:
                gesQL = duration.quarterLength

            if inFTrem:
                # multiply gestural duration by 2 to adjust for how music21 represents
                # gestural duration of notes/chords in TremoloSpanner.  If this makes
                # it equivalent to visual duration, no @dur.ges or @dots.ges will be
                # emitted.
                gesQL = opFrac(gesQL * 2.0)

            gesDuration = m21.duration.Duration(gesQL)
            durGes = M21ObjectConvert._M21_DUR_TYPE_TO_MEI_DUR.get(gesDuration.type, '')
            dotsGes = str(gesDuration.dots)

            # only emit @dur.ges if different from @dur
            # @dots.ges is more complicated.  There is a question about
            # whether missing @dots.ges should fall back to @dots or to '0'
            # in the presence of @dur.ges.  So we avoid the ambiguity and
            # if there is a @dur.ges and non-zero @dots, we _always_ emit @dots.ges,
            # even if it's '0' or the same as @dots.  And if there is a @dur.ges and
            # no @dots, we can skip @dots.ges only if it also represents no dots.
            if durGes == dur:
                durGes = ''
            if not durGes:
                # There is no @dur.ges, so we can remove @dots.ges if it's the
                # same as @dots.
                if dotsGes == dots:
                    dotsGes = ''
            else:
                # There is a @dur.ges, so we can only remove @dots.ges if it is
                # '0' _and_ @dots is '0'.
                if dotsGes in ('0', '') and dots in ('0', ''):
                    dotsGes = ''

        # all computed, put the relevant ones in the attr dict
        if dots and dots != '0':
            attr['dots'] = dots
        if dur:
            attr['dur'] = dur
        if dotsGes:
            attr['dots.ges'] = dotsGes
        if durGes:
            attr['dur.ges'] = durGes
        if grace:
            attr['grace'] = grace

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
    def floatToStringWithDecimalPlacesMinMax(
        f: float,
        minDecimals: int,
        maxDecimals: int
    ) -> str:
        formatStr: str

        if f == round(f, minDecimals):
            # if you need minDecimals or less...
            # use exactly minDecimals, no less.
            formatStr = f':.{minDecimals}f'
        else:
            # if you need more than minDecimals...
            # use as many as you need, up to maxDecimals.
            formatStr = f':.{maxDecimals}g'

        formatStr = '{' + formatStr + '}'
        output: str = formatStr.format(f)
        return output

    @staticmethod
    def makeTstamp(
        offsetInScore: OffsetQLIn,
        offsetInMeasure: OffsetQLIn,
        meterStream: m21.stream.Stream[m21.meter.TimeSignature]
    ) -> str:
        beat: float = M21ObjectConvert._offsetToBeat(
            opFrac(offsetInMeasure),
            M21Utilities.getActiveTimeSigFromMeterStream(offsetInScore, meterStream)
        )

        beatStr: str = M21ObjectConvert.floatToStringWithDecimalPlacesMinMax(beat, 1, 6)
        return beatStr

    @staticmethod
    def _offsetToBeat(
        offset: OffsetQL,
        currTimeSig: m21.meter.TimeSignature | None
    ) -> float:
        # convert from quarter notes to whole notes
        beat: float = float(offset) / 4.0

        # convert to beats (if there is no current time signature,
        # assume beats are quarter notes).
        currTimeSigDenom: int = 4
        if currTimeSig is not None:
            currTimeSigDenom = currTimeSig.denominator
        beat *= float(currTimeSigDenom)

        # make it 1-based
        return beat + 1.0

    @staticmethod
    def makeTstamp2(
        endObject: m21.base.Music21Object,
        m21StartMeasure: m21.stream.Measure,
        m21Score: m21.stream.Score,
        meterStream: m21.stream.Stream[m21.meter.TimeSignature]
    ) -> str:
        # count steps from m21StartMeasure to measure containing endObject in m21Score
        measureStepCount: int = -1
        endOffsetInMeasure: OffsetQL | None = None
        counting: bool = False
        endOffsetInScore: OffsetQL | None = None
        m21StartPart: m21.stream.Part | None = None
        m21EndPart: m21.stream.Part | None = None

        for part in m21Score.parts:
            if M21Utilities.safeGetOffsetInHierarchy(m21StartMeasure, part) is not None:
                m21StartPart = part
                break

        if m21StartPart is None:
            raise MeiInternalError('makeTstamp2: failed to find m21StartMeasure in m21Score')

        for part in m21Score.parts:
            endOffsetInScore = M21Utilities.safeGetOffsetInHierarchy(endObject, part)
            if endOffsetInScore is not None:
                m21EndPart = part
                break

        if endOffsetInScore is None or m21EndPart is None:
            raise MeiInternalError('makeTstamp2: failed to find endObject in m21Score')

        startPartMeasures: list[m21.stream.Measure] = list(m21StartPart[m21.stream.Measure])
        endPartMeasures: list[m21.stream.Measure] = list(m21EndPart[m21.stream.Measure])

        for startMeas, endMeas in zip(startPartMeasures, endPartMeasures):
            if startMeas is m21StartMeasure:
                # We found the start measure! Start counting steps.
                measureStepCount = 0
                counting = True

            if counting:
                endOffsetInMeasure = M21Utilities.safeGetOffsetInHierarchy(endObject, endMeas)
                if endOffsetInMeasure is not None:
                    # We found the end measure!
                    break

            if counting:
                measureStepCount += 1

        if measureStepCount == -1:
            raise MeiInternalError('makeTstamp2: failed to find m21StartMeasure in m21Score')

        if endOffsetInMeasure is None:
            raise MeiInternalError(
                'makeTstamp2: failed to find endObject in or after m21StartMeasure in m21Score'
            )

        # we have measureStepCount; now we need to compute beats from endOffsetInMeasure
        beat: float = M21ObjectConvert._offsetToBeat(
            opFrac(endOffsetInMeasure),
            M21Utilities.getActiveTimeSigFromMeterStream(endOffsetInScore, meterStream)
        )

        # use as many decimal places as you need, between min of 1 and max of 6
        beatStr: str = M21ObjectConvert.floatToStringWithDecimalPlacesMinMax(beat, 1, 6)
        return f'{measureStepCount}m+{beatStr}'

    @staticmethod
    def makeTstamp2FromScoreOffset(
        endOffsetInScore: OffsetQL,
        m21StartMeasure: m21.stream.Measure,
        m21Score: m21.stream.Score,
        meterStream: m21.stream.Stream[m21.meter.TimeSignature]
    ) -> str:
        # count steps from m21StartMeasure to measure containing endScoreOffset in m21Score
        measureStepCount: int = -1
        endOffsetInMeasure: OffsetQL | None = None
        counting: bool = False
        m21Part: m21.stream.Part | None = None

        for part in m21Score.parts:
            if M21Utilities.safeGetOffsetInHierarchy(m21StartMeasure, part) is not None:
                m21Part = part
                break

        if m21Part is None:
            raise MeiInternalError('makeTstamp2: failed to find m21StartMeasure in m21Score')

        partMeasures: list[m21.stream.Measure] = list(m21Part[m21.stream.Measure])

        for meas in partMeasures:
            if meas is m21StartMeasure:
                # We found the start measure! Start counting steps.
                measureStepCount = 0
                counting = True

            if counting:
                endOffsetInMeasure = opFrac(endOffsetInScore - meas.getOffsetInHierarchy(m21Score))
                if 0 <= endOffsetInMeasure <= meas.duration.quarterLength:
                    # We found the end measure!
                    break
                # gotta keep searching
                endOffsetInMeasure = None

            if counting:
                measureStepCount += 1

        if measureStepCount == -1:
            raise MeiInternalError(
                'makeTstamp2FromScoreOffset: failed to find m21StartMeasure in m21Score'
            )

        if endOffsetInMeasure is None:
            print(
                'endOffsetInScore is before startMeasure.  Ending at startMeasure offset 0.',
                file=sys.stderr
            )
            endOffsetInMeasure = 0.0

        # we have measureStepCount; now we need to compute beats from endOffsetInMeasure
        beat: float = M21ObjectConvert._offsetToBeat(
            opFrac(endOffsetInMeasure),
            M21Utilities.getActiveTimeSigFromMeterStream(endOffsetInScore, meterStream)
        )

        # use as many decimal places as you need, between min of 1 and max of 6
        beatStr: str = M21ObjectConvert.floatToStringWithDecimalPlacesMinMax(beat, 1, 6)
        return f'{measureStepCount}m+{beatStr}'

    @staticmethod
    def _fillInStandardPostStavesAttributes(
        attr: dict[str, str],
        first: m21.base.Music21Object,
        last: m21.base.Music21Object | None,
        staffNStr: str,
        m21Score: m21.stream.Score,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
        forceTstamp2AtEndOfLast: bool = False,
    ):
        attr['staff'] = staffNStr  # TODO: what about "1 2"

        if first is None:
            # we're done
            return

        firstIsNote: bool = isinstance(first, m21.note.GeneralNote)
        if firstIsNote:
            # ChordSymbol is a GeneralNote, but we treat it like it isn't.
            firstIsNote = not isinstance(first, m21.harmony.ChordSymbol)

        if not firstIsNote:
            attr['tstamp'] = M21ObjectConvert.makeTstamp(
                offsetInScore=first.getOffsetInHierarchy(m21Score),
                offsetInMeasure=first.getOffsetInHierarchy(m21Measure),
                meterStream=scoreMeterStream
            )
        else:
            attr['startid'] = f'#{M21Utilities.getXmlId(first, required=True)}'

        if last is None or last is first:
            # no unique last element, we're done
            return

        # unique last element, we need @tstamp2 or @endid
        if forceTstamp2AtEndOfLast:
            offsetAtEndOfLast: OffsetQL = opFrac(
                last.getOffsetInHierarchy(m21Score) + last.duration.quarterLength
            )
            attr['tstamp2'] = M21ObjectConvert.makeTstamp2FromScoreOffset(
                endOffsetInScore=offsetAtEndOfLast,
                m21StartMeasure=m21Measure,
                m21Score=m21Score,
                meterStream=scoreMeterStream
            )
        elif not isinstance(last, m21.note.GeneralNote):
            attr['tstamp2'] = M21ObjectConvert.makeTstamp2(
                endObject=last,
                m21StartMeasure=m21Measure,
                m21Score=m21Score,
                meterStream=scoreMeterStream
            )
        else:
            attr['endid'] = f'#{M21Utilities.getXmlId(last, required=True)}'

    _ARPEGGIO_TYPE_TO_ARROW_AND_ORDER: dict[str, tuple[str, str]] = {
        'normal': ('', ''),
        'up': ('true', 'up'),
        'down': ('true', 'down'),
        'non-arpeggio': ('false', 'nonarp')
    }

    _DIS_AND_DIS_PLACE_FROM_M21_OTTAVA_TYPE: dict[str, tuple[str, str]] = {
        '8va': ('8', 'above'),
        '8vb': ('8', 'below'),
        '15ma': ('15', 'above'),
        '15mb': ('15', 'below'),
        '22da': ('22', 'above'),
        '22db': ('22', 'below')
    }

    @staticmethod
    def postStavesSpannerToMei(
        spanner: m21.spanner.Spanner,
        staffNStr: str,
        m21Score: m21.stream.Score,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
        customAttributes: dict[m21.base.Music21Object, list[str]],
        spannerBundle: m21.spanner.SpannerBundle,
        tb: TreeBuilder
    ) -> None:
        forceTstamp2: bool = False
        first: m21.base.Music21Object = spanner.getFirst()
        last: m21.base.Music21Object = spanner.getLast()
        tag: str = ''
        attr: dict[str, str] = {}
        xmlId: str = M21Utilities.getXmlId(spanner)
        if xmlId:
            attr['xml:id'] = xmlId

        if isinstance(spanner, M21BeamSpanner):
            if hasattr(spanner, 'mei_beam'):
                # already emitted as <beam> within <layer>
                return

        if isinstance(spanner, M21TupletSpanner):
            if hasattr(spanner, 'mei_tuplet'):
                # already emitted as <tuplet> within <layer>
                return

        if isinstance(spanner, m21.dynamics.DynamicWedge):
            # music21 defines a DynamicWedge as ending at the end of spanner.getLast()
            # MEI defines a hairpin as ending at the beginning of @endid
            # So we always have to emit a tstamp2 for hairpins, because we have no
            # easy way of searching for a different object that might have the
            # correct offset.
            forceTstamp2 = True

        M21ObjectConvert._fillInStandardPostStavesAttributes(
            attr,
            first,
            last,
            staffNStr,
            m21Score,
            m21Measure,
            scoreMeterStream,
            forceTstamp2AtEndOfLast=forceTstamp2,
        )

        if isinstance(spanner, m21.spanner.Slur):
            tag = 'slur'
        elif isinstance(spanner, m21.dynamics.DynamicWedge):
            tag = 'hairpin'
            if isinstance(spanner, m21.dynamics.Crescendo):
                attr['form'] = 'cres'
            else:
                attr['form'] = 'dim'
        elif isinstance(spanner, m21.expressions.ArpeggioMarkSpanner):
            tag = 'arpeg'
            # set up plist for every spanned element (yes, even the ones that are already
            # in attr as 'startid' and 'endid')
            M21ObjectConvert.fillInArpeggioAttributes(spanner, attr)
        elif isinstance(spanner, m21.spanner.Ottava):
            tag = 'octave'
            dis: str
            disPlace: str
            dis, disPlace = M21ObjectConvert._DIS_AND_DIS_PLACE_FROM_M21_OTTAVA_TYPE[spanner.type]
            attr['dis'] = dis
            attr['dis.place'] = disPlace
        elif isinstance(spanner, M21BeamSpanner):
            tag = 'beamSpan'
            # set up plist for every spanned element (yes, even the ones that are already
            # in attr as 'startid' and 'endid')
            plistStr = ''
            for el in spanner.getSpannedElements():
                if plistStr:
                    plistStr += ' '
                plistStr += M21Utilities.getXmlId(el, required=True)
            attr['plist'] = plistStr
        elif isinstance(spanner, M21TupletSpanner):
            tag = 'tupletSpan'
            M21ObjectConvert.fillInTupletAttributes(spanner.startTuplet, attr)
            # set up plist for every spanned element (yes, even the ones that are already
            # in attr as 'startid' and 'endid')
            plistStr = ''
            for el in spanner.getSpannedElements():
                if plistStr:
                    plistStr += ' '
                plistStr += M21Utilities.getXmlId(el, required=True)
            attr['plist'] = plistStr
        elif isinstance(spanner, M21TieSpanner):
            if spanner.startTie.style != 'hidden':
                tag = 'tie'
                M21ObjectConvert.fillInTieAttributes(spanner.startTie, attr)
                # startid/endid only, which are already handled

        elif isinstance(spanner, m21.expressions.TrillExtension):
            if hasattr(spanner, 'mei_trill_already_handled'):
                return

            # Note that we don't set tag (i.e. we don't emit a <trill> here) unless
            # we find an actual m21.expressions.Trill.  A TrillExtension with no
            # Trill is not a <trill>.  Maybe it's a <line form="wavy"> or something,
            # but not today.
            notes: list[m21.note.GeneralNote] = []
            if isinstance(first, m21.spanner.SpannerAnchor):
                # look for an actual note at the same offset in this m21Measure
                offsetInMeasure: OffsetQL = first.getOffsetInHierarchy(m21Measure)
                notes = list(
                    m21Measure.recurse()
                    .getElementsByOffset(offsetInMeasure)
                    .getElementsByClass(m21.note.GeneralNote)
                )
            elif isinstance(first, m21.note.GeneralNote):
                notes = [first]

            for note in notes:
                # search note.expressions for a Trill, and if found gather attr from that, too.
                for expr in note.expressions:
                    if isinstance(expr, m21.expressions.Trill):
                        if hasattr(expr, 'mei_trill_already_handled'):
                            # not this one, we already emitted it.
                            continue

                        # There is an assocated Trill, so go ahead an emit a <trill>.
                        tag = 'trill'
                        # passing None for trillToMei's last param (tb) means "just
                        # add the Trill info to attr, I'll emit this <trill> myself".
                        M21ObjectConvert.trillToMei(
                            note,
                            expr,
                            staffNStr,
                            m21Score,
                            m21Measure,
                            scoreMeterStream,
                            customAttributes,
                            spannerBundle,
                            tb=None,
                            attr=attr
                        )
                        # mark the Trill as handled, so when we see it during note.expressions
                        # processing, we won't emit it again.
                        expr.mei_trill_already_handled = True  # type: ignore
                        M21Utilities.extendCustomM21Attributes(
                            customAttributes,
                            expr,
                            ['mei_trill_already_handled']
                        )

                        # mark the TrillExtension as handled, so when we (might) see it during
                        # Trill processing or measure-level SpannerAnchor scanning, we won't
                        # re-issue it.
                        spanner.mei_trill_already_handled = True  # type: ignore
                        M21Utilities.extendCustomM21Attributes(
                            customAttributes,
                            spanner,
                            ['mei_trill_already_handled']
                        )
                        break
                if tag:
                    break

        if tag:
            M21ObjectConvert._addStylisticAttributes(spanner, attr)
            tb.start(tag, attr)
            tb.end(tag)

    @staticmethod
    def fillInArpeggioAttributes(
        arpeggio: m21.expressions.ArpeggioMark | m21.expressions.ArpeggioMarkSpanner,
        attr: dict[str, str]
    ):
        if isinstance(arpeggio, m21.expressions.ArpeggioMarkSpanner):
            plistStr: str = ''
            for el in arpeggio.getSpannedElements():
                if plistStr:
                    plistStr += ' '
                plistStr += M21Utilities.getXmlId(el, required=True)
            attr['plist'] = plistStr

        arrow: str
        order: str
        arrow, order = M21ObjectConvert._ARPEGGIO_TYPE_TO_ARROW_AND_ORDER.get(
            arpeggio.type, ('', '')
        )
        if arrow:
            attr['arrow'] = arrow
        if order:
            attr['order'] = order

    @staticmethod
    def arpeggioMarkToMei(
        gn: m21.note.GeneralNote,
        arpeggio: m21.expressions.ArpeggioMark,
        staffNStr: str,
        m21Score: m21.stream.Score,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
        tb: TreeBuilder
    ):
        attr: dict[str, str] = {}
        xmlId: str = M21Utilities.getXmlId(arpeggio)
        if xmlId:
            attr['xml:id'] = xmlId
        attr['startid'] = f'#{M21Utilities.getXmlId(gn, required=True)}'
        M21ObjectConvert.fillInArpeggioAttributes(arpeggio, attr)
        tb.start('arpeg', attr)
        tb.end('arpeg')

    @staticmethod
    def fillInTupletAttributes(startTuplet: m21.duration.Tuplet, attr: dict[str, str]):
        attr['num'] = str(startTuplet.numberNotesActual)
        attr['numbase'] = str(startTuplet.numberNotesNormal)

        # bracket visibility (startTuplet.bracket can be False, True, 'slur', or None)
        bracketIsVisible: bool | None = None
        if startTuplet.bracket is False:
            attr['bracket.visible'] = 'false'
            bracketIsVisible = False
        elif startTuplet.bracket is True:
            attr['bracket.visible'] = 'true'
            bracketIsVisible = True
        elif startTuplet.bracket == 'slur':
            # MEI has no support for curved tuplet brackets, go with "visible"
            attr['bracket.visible'] = 'true'
            bracketIsVisible = True

        # number visibility and format
        numIsVisible: bool = (
            startTuplet.tupletActualShow is not None or startTuplet.tupletNormalShow is not None
        )
        if numIsVisible:
            # MEI default for @num.visible is 'true', so we don't set that
            # But we do set the format as appropriate.
            if startTuplet.tupletActualShow == 'number':
                if startTuplet.tupletNormalShow == 'number':
                    attr['num.format'] = 'ratio'
                elif startTuplet.tupletNormalShow is None:
                    attr['num.format'] = 'count'
        else:
            attr['num.visible'] = 'false'

        # placement (MEI has two: num and bracket placement, but music21 only has one)
        # Note that we check isVisible is not False, so we set placement if visibility
        # is True or even if it is unspecified.
        if startTuplet.placement is not None:
            if bracketIsVisible is not False:
                attr['bracket.place'] = startTuplet.placement
            if numIsVisible is not False:
                attr['num.place'] = startTuplet.placement

    @staticmethod
    def fillInTieAttributes(startTie: m21.tie.Tie, attr: dict[str, str]):
        if startTie.placement in ('above', 'below'):
            attr['curvedir'] = startTie.placement
        if startTie.style in ('dotted', 'dashed'):
            attr['lform'] = startTie.style

    @staticmethod
    def trillToMei(
        gn: m21.note.GeneralNote,
        trill: m21.expressions.Trill,
        staffNStr: str,
        m21Score: m21.stream.Score,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
        customAttributes: dict[m21.base.Music21Object, list[str]],
        spannerBundle: m21.spanner.SpannerBundle,
        tb: TreeBuilder | None,
        attr: dict[str, str] | None = None,
    ) -> None:
        # This can be called with a real TreeBuilder (not None). In that case, we do the full
        # job of emitting the <trill>.
        # This can be called with attr partly filled in, and tb is None (during TrillExtension
        # processing). In this case, we just add the Trill info to the attr dict.  One <trill>
        # will be emitted for both Trill and TrillExtension in that case, by the caller.
        trillExtension: m21.expressions.TrillExtension | None = None
        if tb is not None:
            # do the full job (ignore any attr passed in, it should be None)
            # Also, if we're doing the full job, we need to find any associated
            # TrillExtension, and include the last element in trill@endid or trill@tstamp2.

            # 1. Look for a TrillExtension with gn as first element.
            for spanner in gn.getSpannerSites():
                if not M21Utilities.isIn(spanner, spannerBundle):
                    continue
                if isinstance(spanner, m21.expressions.TrillExtension):
                    # found it!
                    trillExtension = spanner
                    break

            # 2. Look for any SpannerAnchors with same offset in m21Measure as gn,
            #       and look for a TrillExtension with one of those as first element.
            if trillExtension is None:
                anchors: list[m21.spanner.SpannerAnchor] = []
                offsetInMeasure: OffsetQL = gn.getOffsetInHierarchy(m21Measure)
                anchors = list(
                    m21Measure.recurse()
                    .getElementsByOffset(offsetInMeasure)
                    .getElementsByClass(m21.spanner.SpannerAnchor)
                )

                for anchor in anchors:
                    for spanner in anchor.getSpannerSites():
                        if not M21Utilities.isIn(spanner, spannerBundle):
                            continue
                        if isinstance(spanner, m21.expressions.TrillExtension):
                            # found it!
                            trillExtension = spanner
                            break
                    if trillExtension is not None:
                        break

            last: m21.base.Music21Object | None = None
            if trillExtension is not None:
                last = trillExtension.getLast()

            attr = {}
            xmlId: str = M21Utilities.getXmlId(trill)
            if xmlId:
                attr['xml:id'] = xmlId
            M21ObjectConvert._fillInStandardPostStavesAttributes(
                attr,
                gn,
                last,
                staffNStr,
                m21Score,
                m21Measure,
                scoreMeterStream
            )

        if attr is None:
            raise MeiInternalError('trillToMei called without attr or tree builder')

        # in both cases we add to attr here
        if trill.accidental is not None and trill.accidental.displayStatus:
            accid: str = M21ObjectConvert.m21AccidToMeiAccid(trill.accidental.name)
            if trill.direction == 'up':
                attr['accidupper'] = accid
            else:
                attr['accidlower'] = accid

        M21ObjectConvert._addStylisticAttributes(trill, attr)

        if trill.direction == 'up':
            attr['form'] = 'upper'
        elif trill.direction == 'down':
            attr['form'] = 'lower'

        if tb is not None:
            # do the full job
            tb.start('trill', attr)
            tb.end('trill')
            trill.mei_trill_already_handled = True  # type: ignore
            M21Utilities.extendCustomM21Attributes(
                customAttributes,
                trill,
                ['mei_trill_already_handled']
            )
            if trillExtension is not None:
                trillExtension.mei_trill_already_handled = True  # type: ignore
                M21Utilities.extendCustomM21Attributes(
                    customAttributes,
                    trillExtension,
                    ['mei_trill_already_handled']
                )

    @staticmethod
    def turnToMei(
        gn: m21.note.GeneralNote,
        turn: m21.expressions.Turn,
        staffNStr: str,
        m21Score: m21.stream.Score,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
        tb: TreeBuilder,
    ) -> None:
        attr: dict[str, str] = {}
        xmlId: str = M21Utilities.getXmlId(turn)
        if xmlId:
            attr['xml:id'] = xmlId
        M21ObjectConvert._fillInStandardPostStavesAttributes(
            attr,
            gn,
            None,
            staffNStr,
            m21Score,
            m21Measure,
            scoreMeterStream
        )

        if turn.upperAccidental is not None and turn.upperAccidental.displayStatus:
            accidupper: str = M21ObjectConvert.m21AccidToMeiAccid(turn.upperAccidental.name)
            attr['accidupper'] = accidupper
        if turn.lowerAccidental is not None and turn.lowerAccidental.displayStatus:
            accidlower: str = M21ObjectConvert.m21AccidToMeiAccid(turn.lowerAccidental.name)
            attr['accidlower'] = accidlower

        if isinstance(turn, m21.expressions.InvertedTurn):
            attr['form'] = 'lower'
        else:
            attr['form'] = 'upper'

        if turn.isDelayed:
            # TODO: non-standard turn delays (use tstamp instead of startid)
            attr['delayed'] = 'true'

        M21ObjectConvert._addStylisticAttributes(turn, attr)
        tb.start('turn', attr)
        tb.end('turn')

    @staticmethod
    def mordentToMei(
        gn: m21.note.GeneralNote,
        mordent: m21.expressions.GeneralMordent,
        staffNStr: str,
        m21Score: m21.stream.Score,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
        tb: TreeBuilder,
    ) -> None:
        attr: dict[str, str] = {}
        xmlId: str = M21Utilities.getXmlId(mordent)
        if xmlId:
            attr['xml:id'] = xmlId
        M21ObjectConvert._fillInStandardPostStavesAttributes(
            attr,
            gn,
            None,
            staffNStr,
            m21Score,
            m21Measure,
            scoreMeterStream
        )

        if mordent.accidental is not None and mordent.accidental.displayStatus:
            accid: str = M21ObjectConvert.m21AccidToMeiAccid(mordent.accidental.name)
            if mordent.direction == 'up':
                attr['accidupper'] = accid
            else:
                attr['accidlower'] = accid

        if mordent.direction == 'up':
            attr['form'] = 'upper'
        elif mordent.direction == 'down':
            attr['form'] = 'lower'

        M21ObjectConvert._addStylisticAttributes(mordent, attr)
        tb.start('mordent', attr)
        tb.end('mordent')

    @staticmethod
    def fermataToMei(
        obj: m21.note.GeneralNote | m21.bar.Barline,
        fermata: m21.expressions.Fermata,
        staffNStr: str,
        m21Score: m21.stream.Score,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
        tb: TreeBuilder,
    ) -> None:
        attr: dict[str, str] = {}
        xmlId: str = M21Utilities.getXmlId(fermata)
        if xmlId:
            attr['xml:id'] = xmlId
        M21ObjectConvert._fillInStandardPostStavesAttributes(
            attr,
            obj,
            None,
            staffNStr,
            m21Score,
            m21Measure,
            scoreMeterStream
        )

        if fermata.type == 'inverted':
            attr['form'] = 'inv'

        if fermata.shape == 'square':
            attr['shape'] = 'square'
        elif fermata.shape == 'angled':
            attr['shape'] = 'angular'

        M21ObjectConvert._addStylisticAttributes(fermata, attr)
        tb.start('fermata', attr)
        tb.end('fermata')

    @staticmethod
    def emitStyledTextElement(
        text: str,
        style: m21.style.TextStyle | None,
        tag: str,
        attr: dict[str, str],
        tb: TreeBuilder
    ):
        tb.start(tag, attr)
        needsRend: bool = False
        if style is not None:
            meiFontStyle: str | None = None
            meiFontWeight: str | None = None
            meiFontFamily: str | None = None
            meiJustify: str | None = None

            meiFontStyle, meiFontWeight = M21ObjectConvert.m21FontStyleAndWeightToMei(
                style.fontStyle,
                style.fontWeight
            )

            # style.fontFamily is always a list; just take the first one, I guess...
            if style.fontFamily:
                meiFontFamily = style.fontFamily[0]

            if style.justify:
                meiJustify = style.justify

            needsRend = (
                bool(meiFontStyle)
                or bool(meiFontWeight)
                or bool(meiFontFamily)
                or bool(meiJustify)
            )
            if needsRend:
                rendAttr: dict[str, str] = {}
                if meiFontStyle:
                    rendAttr['fontstyle'] = meiFontStyle
                if meiFontWeight:
                    rendAttr['fontweight'] = meiFontWeight
                if meiFontFamily:
                    rendAttr['fontfam'] = meiFontFamily
                if meiJustify:
                    rendAttr['halign'] = meiJustify
                tb.start('rend', rendAttr)

        tb.data(text)

        if needsRend:
            tb.end('rend')
        tb.end(tag)

    @staticmethod
    def convertPostStaveStreamElement(
        obj: m21.base.Music21Object,
        staffNStr: str,
        m21Score: m21.stream.Score,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
        tb: TreeBuilder,
    ):
        attr: dict[str, str] = {}
        xmlId: str = M21Utilities.getXmlId(obj)
        if xmlId:
            attr['xml:id'] = xmlId
        M21ObjectConvert._fillInStandardPostStavesAttributes(
            attr,
            obj,
            None,
            staffNStr,
            m21Score,
            m21Measure,
            scoreMeterStream
        )

        M21ObjectConvert._addStylisticAttributes(obj, attr)

        tag: str = M21_OBJECT_CLASS_NAMES_FOR_POST_STAVES_TO_MEI_TAG.get(obj.classes[0], '')
        style: m21.style.Style | None = None
        if obj.hasStyleInformation:
            style = obj.style

        if tag == 'dynam':
            if t.TYPE_CHECKING:
                assert isinstance(obj, m21.dynamics.Dynamic)
                assert style is None or isinstance(style, m21.style.TextStyle)
            M21ObjectConvert.emitStyledTextElement(obj.value, style, tag, attr, tb)
            return

        if tag == 'dir':
            if t.TYPE_CHECKING:
                assert isinstance(obj, m21.expressions.TextExpression)
                assert style is None or isinstance(style, m21.style.TextStyle)
            M21ObjectConvert.emitStyledTextElement(obj.content, style, tag, attr, tb)
            return

        if tag == 'harm':
            if t.TYPE_CHECKING:
                assert isinstance(obj, m21.harmony.ChordSymbol)
            M21ObjectConvert.emitHarmony(obj, tag, attr, tb)

        if tag == 'tempo':
            assert style is None or isinstance(style, m21.style.TextStyle)
            if isinstance(obj, m21.tempo.MetricModulation):
                obj = obj.newMetronome

            if isinstance(obj, m21.tempo.TempoText):
                M21ObjectConvert.emitStyledTextElement(obj.text, style, tag, attr, tb)
                return

            if isinstance(obj, m21.tempo.MetronomeMark):
                if obj.numberImplicit:
                    M21ObjectConvert.emitStyledTextElement(obj.text, style, tag, attr, tb)
                else:
                    number: int | float | None = obj.number
                    if number is None:
                        number = obj.numberSounding
                    if number is not None:
                        # figure out @midi.bpm from number, converting from referent
                        # to quarter note (e.g. referent might be half note)
                        attr['midi.bpm'] = str(number * obj.referent.quarterLength)

                        tb.start(tag, attr)
                        # also construct "blah=128" or whatever, using SMUFL for noteheads, and
                        # append it to the text before calling tb.data().  It will need a <rend>
                        # element in the middle of the text (thus it's mixed text and elements)
                        M21ObjectConvert._convertMetronomeMarkToMixedText(obj, tb)
                        tb.end(tag)

    @staticmethod
    def emitHarmony(cs: m21.harmony.ChordSymbol, tag: str, attr: dict[str, str], tb: TreeBuilder):
        # set @type to our favorite standard abbreviation, for ease of parsing later.
        # Harte contains ','s, so we have to convert them all to '.'s to make @type
        # a legal NMTOKEN. (When we read it up, we will convert them back to commas
        # before parsing.)

        # @reg = harte or music21? (@type for now...)
        harteRegPrefix: str = 'harte-no-commas:'
        harte: str = M21Utilities.makeHarteFromChordSymbol(cs)
        if harte:
            attr['type'] = harteRegPrefix + re.sub(',', '.', harte)

#             m21RegPrefix: str = 'music21-no-spaces:'
#             m21Reg: str = M21Utilities.makeM21RegFromChordSymbol(cs)
#             if m21Reg:
#                 m21Reg = re.sub(' add ', 'add', m21Reg)
#                 m21Reg = re.sub(' subtract ', 'subtract', m21Reg)
#                 m21Reg = re.sub(' alter ', 'alter', m21Reg)
#                 attr['type'] = m21RegPrefix + m21Reg

        tb.start(tag, attr)
        M21ObjectConvert._convertChordSymbolToMixedText(cs, tb)
        tb.end(tag)

    @staticmethod
    def _convertChordSymbolToMixedText(cs: m21.harmony.ChordSymbol, tb: TreeBuilder):
        text: str = M21Utilities.convertChordSymbolToText(cs)
        # Here is where we would start a 'rend' tag and do some style stuff (color, italic, etc)
        if text:
            tb.data(text)
        # Here is where we would end the 'rend' tag, if we had started it.

    @staticmethod
    def _convertMetronomeMarkToMixedText(mm: m21.tempo.MetronomeMark, tb: TreeBuilder):
        if mm.text is None:
            return

        if not mm.textImplicit:
            tb.data(mm.text)

        if not mm.numberImplicit and mm.number is not None:
            tb.data(' ')
            tb.start('rend', {'fontfam': 'smufl'})
            noteHead: str = M21ObjectConvert._getNoteHeadSMUFLUnicodeForReferent(mm.referent)
            tb.data(noteHead)
            tb.data(f' = {int(mm.number)}')
            tb.end('rend')

    @staticmethod
    def meiFontStyleAndWeightToM21FontStyle(
        meiFontStyle: str | None,
        meiFontWeight: str | None
    ) -> str | None:
        if not meiFontStyle:
            meiFontStyle = 'normal'
        if not meiFontWeight:
            meiFontWeight = 'normal'

        if meiFontStyle == 'oblique':
            environLocal.warn('@fontstyle="oblique" not supported, treating as "italic"')
            meiFontStyle = 'italic'
        if meiFontStyle not in ('normal', 'italic'):
            environLocal.warn(f'@fontstyle="{meiFontStyle}" not supported, treating as "normal"')
            meiFontStyle = 'normal'
        if meiFontWeight not in ('normal', 'bold'):
            environLocal.warn(f'@fontweight="{meiFontWeight}" not supported, treating as "normal"')
            meiFontWeight = 'normal'

        if meiFontStyle == 'normal':
            if meiFontWeight == 'normal':
                return 'normal'
            if meiFontWeight == 'bold':
                return 'bold'

        if meiFontStyle == 'italic':
            if meiFontWeight == 'normal':
                return 'italic'
            if meiFontWeight == 'bold':
                return 'bolditalic'

        # should not ever get here...
        raise MeiInternalError('Failed to compute m21FontStyle.')

    @staticmethod
    def m21FontStyleAndWeightToMei(
        m21FontStyle: str | None,
        m21FontWeight: str | None
    ) -> tuple[str | None, str | None]:
        # We derive everything we need from m21FontStyle (None, 'normal', 'bold', 'bolditalic')
        # and then if m21FontWeight is set ('normal', 'bold'), then we use that to override
        # the boldness of that result we derived.
        meiFontStyle: str | None = None
        meiFontWeight: str | None = None
        if m21FontStyle == 'normal':
            meiFontStyle = 'normal'
        elif m21FontStyle == 'italic':
            meiFontStyle = 'italic'
        elif m21FontStyle == 'bold':
            meiFontWeight = 'bold'
        elif m21FontStyle == 'bolditalic':
            meiFontStyle = 'italic'
            meiFontWeight = 'bold'

        if m21FontWeight:
            meiFontWeight = m21FontWeight

        return (meiFontStyle, meiFontWeight)

    _M21_DURATION_TYPE_TO_SMUFL_MM_NOTE_HEAD: dict[str, str] = {
        'breve': 'metNoteDoubleWhole',
        'whole': 'metNoteWhole',
        'half': 'metNoteHalfUp',
        'quarter': 'metNoteQuarterUp',
        'eighth': 'metNote8thUp',
        '16th': 'metNote16thUp',
        '32nd': 'metNote32thUp',
        '64th': 'metNote64thUp',
        '128th': 'metNote128thUp',
        '256th': 'metNote256thUp',
        '512th': 'metNote512thUp',
        '1024th': 'metNote1024thUp',
    }
    @staticmethod
    def _getNoteHeadSMUFLUnicodeForReferent(referent: m21.duration.Duration) -> str:
        noteHeadSMUFLName: str = M21ObjectConvert._M21_DURATION_TYPE_TO_SMUFL_MM_NOTE_HEAD.get(
            referent.type, 'metNoteQuarterUp'
        )
        output: str = SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR[noteHeadSMUFLName]

        if referent.dots:
            dotUnicode: str = SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR['metAugmentationDot']
            output += dotUnicode * referent.dots

        return output

    _M21_BARLINE_TYPE_OR_DIRECTION_TO_MEI_BARLINE_TYPE: dict[str, str] = {
        'regular': '',  # or 'normal'? (but update meiMeasureBarlineAttrCombine if you do that)
        'heavy-light': '',  # treat heavy-light as normal (MEI has no such thing)
        'heavy': 'heavy',
        'dotted': 'dotted',
        'dashed': 'dashed',
        'double': 'dbl',
        'final': 'end',
        'none': 'invis',
        'start': 'rptstart',
        'end': 'rptend'
    }

    @staticmethod
    def m21BarlineToMeiMeasureBarlineAttr(
        barline: m21.bar.Barline | None,
        customAttributes: dict[m21.base.Music21Object, list[str]]
    ) -> str:
        if barline is None:
            return ''
        if isinstance(barline, m21.bar.Repeat):
            # ignore barline.type, and just use barline.direction ('start' or 'end')
            output = (
                M21ObjectConvert._M21_BARLINE_TYPE_OR_DIRECTION_TO_MEI_BARLINE_TYPE[
                    barline.direction
                ]
            )
            barline.mei_emitted_as_measure_attr = True  # type: ignore
            M21Utilities.extendCustomM21Attributes(
                customAttributes,
                barline,
                ['mei_emitted_as_measure_attr']
            )
            return output

        # not a repeat, use barline.type
        output = (
            M21ObjectConvert._M21_BARLINE_TYPE_OR_DIRECTION_TO_MEI_BARLINE_TYPE[
                barline.type
            ]
        )
        barline.mei_emitted_as_measure_attr = True  # type: ignore
        M21Utilities.extendCustomM21Attributes(
            customAttributes,
            barline,
            ['mei_emitted_as_measure_attr']
        )
        return output

    @staticmethod
    def m21BarlinesToMeiMeasureBarlineAttr(
        barline1: m21.bar.Barline | None,
        barline2: m21.bar.Barline | None,
        customAttributes: dict[m21.base.Music21Object, list[str]]
    ) -> str:
        # barline1 and barline2 are simultaneous, and need to be combined.
        # For example, barline1 may be the right barline of one measure, and barline2
        # may be the left barline of the immediately following measure.
        if barline1 is None and barline2 is None:
            return ''

        attr1: str = M21ObjectConvert.m21BarlineToMeiMeasureBarlineAttr(barline1, customAttributes)
        attr2: str = M21ObjectConvert.m21BarlineToMeiMeasureBarlineAttr(barline2, customAttributes)

        output: str = M21ObjectConvert.meiMeasureBarlineAttrCombine(attr1, attr2)
        return output

    @staticmethod
    def m21BarlineToMei(
        barline: m21.base.Music21Object,
        spannerBundle: m21.spanner.SpannerBundle,
        tb: TreeBuilder
    ) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(barline, m21.bar.Barline)

        if hasattr(barline, 'mei_emitted_as_measure_attr'):
            # ignore it, it's already represented in the output MEI
            delattr(barline, 'mei_emitted_as_measure_attr')
            return

        attr: dict[str, str] = {}
        xmlId: str = M21Utilities.getXmlId(barline)
        if xmlId:
            attr['xml:id'] = xmlId
        form: str
        if isinstance(barline, m21.bar.Repeat):
            form = M21ObjectConvert._M21_BARLINE_TYPE_OR_DIRECTION_TO_MEI_BARLINE_TYPE[
                barline.direction
            ]
        else:
            form = M21ObjectConvert._M21_BARLINE_TYPE_OR_DIRECTION_TO_MEI_BARLINE_TYPE[
                barline.type
            ]

        if not form:
            # unlike <measure>, in <barline> we like form='single' for regular barlines.
            form = 'single'

        attr['form'] = form

        tb.start('barLine', attr)
        tb.end('barLine')

    @staticmethod
    def meiMeasureBarlineAttrCombine(
        attr1: str,
        attr2: str
    ) -> str:
        # if they are the same, the answer is obvious
        if attr1 == attr2:
            return attr1

        # '' loses to anything else
        if not attr1:
            return attr2
        if not attr2:
            return attr1

        # invisibility beats everything
        if attr1 == 'invis' or attr2 == 'invis':
            return 'invis'

        # check for the obvious repeat combinations
        if attr1 == 'rptstart' and attr2 == 'rptend':
            return 'rptboth'
        if attr1 == 'rptend' and attr2 == 'rptstart':
            return 'rptboth'

        # any repeat is the next highest priority (rptboth wins)
        if attr1 == 'rptboth':
            return attr1
        if attr2 == 'rptboth':
            return attr2
        if attr1.startswith('rpt'):
            return attr1
        if attr2.startswith('rpt'):
            return attr2

        # remaining possibilities are 'end', 'dbl', 'dashed', 'dotted'
        # in that (fairly arbitrary) order of priority
        if attr1 == 'end':
            return attr1
        if attr2 == 'end':
            return attr2
        if attr1 == 'dbl':
            return attr1
        if attr2 == 'dbl':
            return attr2
        if attr1 == 'dashed':
            return attr1
        if attr2 == 'dashed':
            return attr2
        if attr1 == 'dotted':
            return attr1
        if attr2 == 'dotted':
            return attr2

        # we shouldn't get here, but if we do, we didn't recognize either one.
        return ''

    @staticmethod
    def _getM21ObjectConverter(
        obj: m21.base.Music21Object
    ) -> t.Callable[[m21.base.Music21Object, m21.spanner.SpannerBundle, TreeBuilder], None] | None:
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
            if className in M21_OBJECT_CLASS_NAMES_FOR_POST_STAVES_TO_MEI_TAG:
                return True

        return False

    @staticmethod
    def streamElementBelongsInLayer(obj: m21.base.Music21Object) -> bool:
        if isinstance(obj, m21.stream.Stream):
            return False

        if isinstance(obj, m21.harmony.ChordSymbol):
            # special case that looks handleable (isinstance(Chord) is True),
            # but must be skipped (if not .writeAsChord).
            if not obj.writeAsChord:
                return False

        for className in obj.classes:
            if className in M21_OBJECT_CLASS_NAMES_FOR_POST_STAVES_TO_MEI_TAG:
                return False

        return True


_M21_OBJECT_CONVERTER: dict[str, t.Callable[
    [m21.base.Music21Object, m21.spanner.SpannerBundle, TreeBuilder],
    None]
] = {
    'Note': M21ObjectConvert.m21NoteToMei,
    'Unpitched': M21ObjectConvert.m21NoteToMei,
    'Chord': M21ObjectConvert.m21ChordToMei,
    'Rest': M21ObjectConvert.m21RestToMei,
    'Clef': M21ObjectConvert.m21ClefToMei,
    'KeySignature': M21ObjectConvert.m21KeySigToMei,
    'TimeSignature': M21ObjectConvert.m21TimeSigToMei,
    'Barline': M21ObjectConvert.m21BarlineToMei
}

M21_OBJECT_CLASS_NAMES_FOR_POST_STAVES_TO_MEI_TAG: dict[str, str] = {
    # This does not include spanners, since spanners are handled separately.
    # This does not include ornaments, since ornaments are handled separately.
    # This only includes single objects that might be found directly in a Voice,
    # and that should not be emitted in the Voice's associated <layer>, but rather
    # saved for the post-staves elements.
    'Dynamic': 'dynam',
    'TextExpression': 'dir',
    'ChordSymbol': 'harm',
    'NoChord': 'harm',
    'TempoIndication': 'tempo',
    'TempoText': 'tempo',
    'MetronomeMark': 'tempo',
    'MetricModulation': 'tempo'
}
