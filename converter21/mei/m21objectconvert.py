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

import music21 as m21
from music21.common import OffsetQLIn, OffsetQL
from music21.common.numberTools import opFrac

# from converter21.mei import MeiExportError
from converter21.mei import MeiInternalError
from converter21.shared import M21Utilities
from converter21.shared import SharedConstants

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
    def convertM21ObjectToMei(obj: m21.base.Music21Object, tb: TreeBuilder):
        convert: t.Callable[[m21.base.Music21Object, TreeBuilder], None] | None = (
            M21ObjectConvert._getM21ObjectConverter(obj)
        )
        if convert is not None:
            convert(obj, tb)

    @staticmethod
    def m21NoteToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, (m21.note.Note, m21.note.Unpitched))
        M21ObjectConvert._noteToMei(obj, tb, withDuration=True)

    @staticmethod
    def _addStemMod(obj: m21.note.NotRest, attr: dict[str, str]):
        if hasattr(obj, 'mei_stem_mod'):
            stemMod: str = getattr(obj, 'mei_stem_mod')
            attr['stem.mod'] = stemMod

    @staticmethod
    def _addBreakSec(obj: m21.note.NotRest, attr: dict[str, str]):
        if hasattr(obj, 'mei_breaksec'):
            num: int = getattr(obj, 'mei_breaksec')
            if num > 0:
                attr['breaksec'] = str(num)

    @staticmethod
    def _addTupletAttribute(obj: m21.note.GeneralNote, attr: dict[str, str]):
        tupletSpanners: list[m21.spanner.Spanner] = obj.getSpannerSites([MeiTupletSpanner])
        for tuplet in tupletSpanners:
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
    def _addStylisticAttributes(obj: m21.base.Music21Object, attr: dict[str, str]):
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
    def m21PlacementToMei(obj: m21.base.Music21Object) -> str | None:
        style: m21.style.Style | None = None
        if obj.hasStyleInformation:
            style = obj.style
        alignVertical: str = ''
        if style is not None and hasattr(style, 'alignVertical'):
            alignVertical = getattr(style, 'alignVertical')

        placement: str | None = None
        if hasattr(obj, 'placement'):
            placement = getattr(obj, 'placement')
        elif style is not None and hasattr(style, 'placement'):
            placement = getattr(style, 'placement')

        if placement is None:
            return None

        if placement == 'below' and alignVertical == 'middle':
            return 'between'
        if placement in ('above', 'below'):
            return placement

        return None

    # Edit this list of characters as desired (but be careful about 'xml:id' value rules)
    _XMLID_BASE_ALPHABET = tuple("abcdefghijklmnopqrstuvwxyz")
    # _XMLID_BASE_DICT = dict((c, v) for v, c in enumerate(_XMLID_BASE_ALPHABET))
    _XMLID_BASE_LEN = len(_XMLID_BASE_ALPHABET)
#     def alphabet_decode(encodedStr: str) -> int:
#         num: int = 0
#         for char in encodedStr:
#             num = num * M21ObjectConvert._XMLID_BASE_LEN + M21ObjectConvert._XMLID_BASE_DICT[char]
#         return num


    @staticmethod
    def makeXmlIdFrom(identifier: int | str, prefix: str = '') -> str:
        output: str = ''

        def alphabet_encode(numToEncode: int) -> str:
            if numToEncode == 0:
                return M21ObjectConvert._XMLID_BASE_ALPHABET[0]

            encoded: str = ''
            while numToEncode:
                numToEncode, remainder = divmod(numToEncode, M21ObjectConvert._XMLID_BASE_LEN)
                encoded = M21ObjectConvert._XMLID_BASE_ALPHABET[remainder] + encoded
            return encoded

        if isinstance(identifier, str):
            # str, use as is
            output = identifier
        elif (isinstance(identifier, int)
                and identifier < m21.defaults.minIdNumberToConsiderMemoryLocation):
            # Nice low integer, use as is (converted to str)
            output = str(identifier)
        elif isinstance(identifier, int):
            # Actually a memory location, so make it a nice short ASCII string,
            # with lower-case class name prefix.
            output = alphabet_encode(identifier)
        else:
            raise MeiInternalError('identifier not int or str')

        if not prefix:
            return output

        if not output.lower().startswith(prefix.lower()):
            # don't put a prefix on that's already there
            output = prefix + '-' + output
        return output

    @staticmethod
    def assureXmlId(obj: m21.base.Music21Object):
        # if xml id has already been set, leave it as is
        if hasattr(obj, 'mei_xml_id'):
            return
        obj.mei_xml_id = M21ObjectConvert.makeXmlIdFrom(  # type: ignore
            obj.id, obj.classes[0].lower()
        )

    @staticmethod
    def assureXmlIds(objs: list[m21.base.Music21Object] | m21.spanner.Spanner):
        if isinstance(objs, m21.spanner.Spanner):
            objs = objs.getSpannedElements()

        for obj in objs:
            M21ObjectConvert.assureXmlId(obj)

    @staticmethod
    def getXmlId(obj: m21.base.Music21Object, required: bool = False) -> str:
        # only returns something if assureXmlId has been called already on this object
        if hasattr(obj, 'mei_xml_id'):
            return obj.mei_xml_id  # type: ignore
        if required:
            raise MeiInternalError('required xml:id is missing')
        return ''

    @staticmethod
    def m21ChordToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.chord.Chord)
        attr: dict[str, str] = {}
        xmlId: str = M21ObjectConvert.getXmlId(obj)
        if xmlId:
            attr['xml:id'] = xmlId

        inFTrem: bool = False
        if hasattr(obj, 'mei_in_ftrem'):
            inFTrem = getattr(obj, 'mei_in_ftrem')
        M21ObjectConvert.m21DurationToMeiDurDotsGrace(obj.duration, attr, inFTrem=inFTrem)
        M21ObjectConvert._addTupletAttribute(obj, attr)
        M21ObjectConvert._addBreakSec(obj, attr)
        M21ObjectConvert._addStylisticAttributes(obj, attr)
        M21ObjectConvert._addStemMod(obj, attr)

        tb.start('chord', attr)
        M21ObjectConvert.m21ArticulationsToMei(obj.articulations, tb)
        M21ObjectConvert.m21LyricsToMei(obj.lyrics, tb)
        for note in obj.notes:
            M21ObjectConvert._noteToMei(note, tb, withDuration=False)
        tb.end('chord')

    @staticmethod
    def m21RestToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.note.Rest)
        attr: dict[str, str] = {}

        xmlId: str = M21ObjectConvert.getXmlId(obj)
        if xmlId:
            attr['xml:id'] = xmlId
        M21ObjectConvert.m21DurationToMeiDurDotsGrace(obj.duration, attr)
        M21ObjectConvert._addTupletAttribute(obj, attr)

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
    def _getOttavaShiftAndTransposing(gn: m21.note.GeneralNote) -> tuple[int, bool]:
        for spanner in gn.getSpannerSites():
            if isinstance(spanner, m21.spanner.Ottava):
                return (
                    M21ObjectConvert._OTTAVA_TYPE_TO_OCTAVE_SHIFT[spanner.type],
                    spanner.transposing
                )
        return 0, True

    @staticmethod
    def _noteToMei(
        note: m21.note.Note | m21.note.Unpitched,
        tb: TreeBuilder,
        withDuration: bool
    ) -> None:
        attr: dict[str, str] = {}
        xmlId: str = M21ObjectConvert.getXmlId(note)
        if xmlId:
            attr['xml:id'] = xmlId

        M21ObjectConvert._addStemMod(note, attr)

        if withDuration:
            inFTrem: bool = False
            if hasattr(note, 'mei_in_ftrem'):
                inFTrem = getattr(note, 'mei_in_ftrem')
            M21ObjectConvert.m21DurationToMeiDurDotsGrace(note.duration, attr, inFTrem=inFTrem)
            M21ObjectConvert._addTupletAttribute(note, attr)

        if isinstance(note, m21.note.Unpitched):
            loc: str = M21ObjectConvert.m21DisplayPitchToMeiLoc(note.displayPitch())
            attr['loc'] = loc
        else:
            # @pname, @oct, @accid/@accid.ges
            attr['pname'] = note.pitch.step.lower()
            octaveShift: int
            ottavaTransposes: bool
            octaveShift, ottavaTransposes = M21ObjectConvert._getOttavaShiftAndTransposing(note)
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
        # attr['con'] = 'd'  # music21 always uses dashes between syllables
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
    def m21ClefToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.clef.Clef)
        if obj.sign is None or obj.sign == 'none':
            # no clef, nothing to see here
            return

        attr: dict[str, str] = {}

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
    def m21KeySigToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.key.KeySignature)

        attr: dict[str, str] = {}

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
    def m21TimeSigToMei(obj: m21.base.Music21Object, tb: TreeBuilder) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(obj, m21.meter.TimeSignature)

        attr: dict[str, str] = {}

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

        if isinstance(duration, m21.duration.GraceDuration):
            if duration.slash:
                grace = 'unacc'
            else:
                grace = 'acc'
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
        m21Part: m21.stream.Part,
        meterStream: m21.stream.Stream[m21.meter.TimeSignature]
    ) -> str:
        # count steps from m21StartMeasure to measure containing endObject in m21Part
        measureStepCount: int = -1
        endOffsetInMeasure: OffsetQL | None = None
        counting: bool = False
        endOffsetInScore: OffsetQL | None = (
            M21Utilities.safeGetOffsetInHierarchy(endObject, m21Part)
        )
        if endOffsetInScore is None:
            raise MeiInternalError('makeTstamp2: failed to find endObject in m21Part')

        for meas in m21Part:
            if not isinstance(meas, m21.stream.Measure):
                continue  # don't count RepeatBrackets!

            if meas is m21StartMeasure:
                # We found the start measure! Start counting steps.
                measureStepCount = 0
                counting = True

            if counting:
                endOffsetInMeasure = M21Utilities.safeGetOffsetInHierarchy(endObject, meas)
                if endOffsetInMeasure is not None:
                    # We found the end measure!
                    break

            if counting:
                measureStepCount += 1

        if measureStepCount == -1:
            raise MeiInternalError('makeTstamp2: failed to find m21StartMeasure in m21Part')

        if endOffsetInMeasure is None:
            raise MeiInternalError(
                'makeTstamp2: failed to find endObject in or after m21StartMeasure in m21Part'
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
    def _fillInStandardPostStavesAttributes(
        attr: dict[str, str],
        first: m21.base.Music21Object,
        last: m21.base.Music21Object | None,
        staffNStr: str,
        m21Part: m21.stream.Part,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
    ):
        attr['staff'] = staffNStr  # TODO: what about "1 2"

        if first is None:
            # we're done
            return

        if not isinstance(first, m21.note.GeneralNote):
            attr['tstamp'] = M21ObjectConvert.makeTstamp(
                offsetInScore=first.getOffsetInHierarchy(m21Part),
                offsetInMeasure=first.getOffsetInHierarchy(m21Measure),
                meterStream=scoreMeterStream
            )
        else:
            attr['startid'] = f'#{M21ObjectConvert.getXmlId(first, required=True)}'

        if last is None or last is first:
            # no unique last element, we're done
            return

        # unique last element, we need @tstamp2 or @endid
        if not isinstance(last, m21.note.GeneralNote):
            attr['tstamp2'] = M21ObjectConvert.makeTstamp2(
                endObject=last,
                m21StartMeasure=m21Measure,
                m21Part=m21Part,
                meterStream=scoreMeterStream
            )
        else:
            attr['endid'] = f'#{M21ObjectConvert.getXmlId(last, required=True)}'

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

        if isinstance(spanner, MeiTupletSpanner):
            if hasattr(spanner, 'mei_tuplet'):
                # already emitted as <tuplet> within <layer>
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
        elif isinstance(spanner, MeiBeamSpanner):
            tag = 'beamSpan'
            # set up plist for every spanned element (yes, even the ones that are already
            # in attr as 'startid' and 'endid')
            plistStr = ''
            for el in spanner.getSpannedElements():
                if plistStr:
                    plistStr += ' '
                plistStr += M21ObjectConvert.getXmlId(el, required=True)
            attr['plist'] = plistStr
        elif isinstance(spanner, MeiTupletSpanner):
            tag = 'tupletSpan'
            M21ObjectConvert.fillInTupletAttributes(spanner.startTuplet, attr)
            # set up plist for every spanned element (yes, even the ones that are already
            # in attr as 'startid' and 'endid')
            plistStr = ''
            for el in spanner.getSpannedElements():
                if plistStr:
                    plistStr += ' '
                plistStr += M21ObjectConvert.getXmlId(el, required=True)
            attr['plist'] = plistStr
        elif isinstance(spanner, MeiTieSpanner):
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
                            m21Part,
                            m21Measure,
                            scoreMeterStream,
                            tb=None,
                            attr=attr
                        )
                        # mark the Trill as handled, so when we see it during note.expressions
                        # processing, we won't emit it again.
                        expr.mei_trill_already_handled = True  # type: ignore
                        # mark the TrillExtension as handled, so when we (might) see it during
                        # Trill processing or measure-level SpannerAnchor scanning, we won't
                        # re-issue it.
                        spanner.mei_trill_already_handled = True  # type: ignore
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
                plistStr += M21ObjectConvert.getXmlId(el, required=True)
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
        m21Part: m21.stream.Part,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
        tb: TreeBuilder
    ):
        attr: dict[str, str] = {}
        attr['startid'] = f'#{M21ObjectConvert.getXmlId(gn, required=True)}'
        M21ObjectConvert.fillInArpeggioAttributes(arpeggio, attr)
        tb.start('arpeg', attr)
        tb.end('arpeg')

    @staticmethod
    def fillInTupletAttributes(startTuplet: m21.duration.Tuplet, attr: dict[str, str]):
        attr['num'] = str(startTuplet.numberNotesActual)
        attr['numbase'] = str(startTuplet.numberNotesNormal)

        # bracket visibility (MEI default is 'true', so we don't set that)
        bracketIsVisible: bool = bool(startTuplet.bracket)  # False, True, or 'slur'
        if not bracketIsVisible:
            attr['bracket.visible'] = 'false'

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
        if startTuplet.placement is not None:
            if bracketIsVisible:
                attr['bracket.place'] = startTuplet.placement
            if numIsVisible:
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
        trillExtension: m21.expressions.TrillExtension | None = None
        if tb is not None:
            # do the full job (ignore any attr passed in, it should be None)
            # Also, if we're doing the full job, we need to find any associated
            # TrillExtension, and include the last element in trill@endid or trill@tstamp2.

            # 1. Look for a TrillExtension with gn as first element.
            for spanner in gn.getSpannerSites():
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
            M21ObjectConvert._fillInStandardPostStavesAttributes(
                attr,
                gn,
                last,
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
            if trillExtension is not None:
                trillExtension.mei_trill_already_handled = True  # type: ignore

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
        m21Part: m21.stream.Part,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
        tb: TreeBuilder,
    ) -> None:
        attr: dict[str, str] = {}
        M21ObjectConvert._fillInStandardPostStavesAttributes(
            attr,
            obj,
            None,
            staffNStr,
            m21Part,
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
        m21Part: m21.stream.Part,
        m21Measure: m21.stream.Measure,
        scoreMeterStream: m21.stream.Stream[m21.meter.TimeSignature],
        tb: TreeBuilder,
    ):
        attr: dict[str, str] = {}
        M21ObjectConvert._fillInStandardPostStavesAttributes(
            attr,
            obj,
            None,
            staffNStr,
            m21Part,
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
                    # figure out @midi.bpm from obj.number, converting from referent
                    # to quarter note (e.g. referent might be half note)
                    attr['midi.bpm'] = obj.number * obj.referent.quarterLength

                    tb.start(tag, attr)
                    # also construct "blah=128" or whatever, using SMUFL for noteheads, and
                    # append it to the text before calling tb.data().  It will need a <rend>
                    # element in the middle of the text (thus it's mixed text and elements)
                    M21ObjectConvert._convertMetronomeMarkToMixedText(obj, tb)
                    tb.end(tag)

    @staticmethod
    def _convertMetronomeMarkToMixedText(mm: m21.tempo.MetronomeMark, tb: TreeBuilder):
        tb.data(mm.text)
        if not mm.numberImplicit:
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
        output: str = SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR[noteHeadSMUFLName]

        if referent.dots:
            dotUnicode: str = SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR['metAugmentationDot']
            output += dotUnicode * referent.dots

        return output

    _M21_BARLINE_TYPE_OR_DIRECTION_TO_MEI_BARLINE_TYPE: dict[str, str] = {
        'regular': '',  # or 'normal'? (but update meiMeasureBarlineAttrCombine if you do that)
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
        barline: m21.bar.Barline | None
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
            return output

        # not a repeat, use barline.type
        output = (
            M21ObjectConvert._M21_BARLINE_TYPE_OR_DIRECTION_TO_MEI_BARLINE_TYPE[
                barline.type
            ]
        )
        barline.mei_emitted_as_measure_attr = True  # type: ignore
        return output

    @staticmethod
    def m21BarlinesToMeiMeasureBarlineAttr(
        barline1: m21.bar.Barline | None,
        barline2: m21.bar.Barline | None
    ) -> str:
        # barline1 and barline2 are simultaneous, and need to be combined.
        # For example, barline1 may be the right barline of one measure, and barline2
        # may be the left barline of the immediately following measure.
        if barline1 is None and barline2 is None:
            return ''

        attr1: str = M21ObjectConvert.m21BarlineToMeiMeasureBarlineAttr(barline1)
        attr2: str = M21ObjectConvert.m21BarlineToMeiMeasureBarlineAttr(barline2)

        output: str = M21ObjectConvert.meiMeasureBarlineAttrCombine(attr1, attr2)
        return output

    @staticmethod
    def m21BarlineToMei(barline: m21.base.Music21Object, tb: TreeBuilder) -> None:
        if t.TYPE_CHECKING:
            assert isinstance(barline, m21.bar.Barline)

        if hasattr(barline, 'mei_emitted_as_measure_attr'):
            # ignore it, it's already represented in the output MEI
            delattr(barline, 'mei_emitted_as_measure_attr')
            return

        attr: dict[str, str] = {}
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
            if className in M21_OBJECT_CLASS_NAMES_FOR_POST_STAVES_TO_MEI_TAG:
                return True

        return False

    @staticmethod
    def streamElementBelongsInLayer(obj: m21.base.Music21Object) -> bool:
        if isinstance(obj, m21.stream.Stream):
            return False

        for className in obj.classes:
            if className in M21_OBJECT_CLASS_NAMES_FOR_POST_STAVES_TO_MEI_TAG:
                return False

        return True


class MeiTemporarySpanner(m21.spanner.Spanner):
    pass


class MeiBeamSpanner(MeiTemporarySpanner):
    pass


class MeiTupletSpanner(MeiTemporarySpanner):
    def __init__(self, startTuplet: m21.duration.Tuplet) -> None:
        super().__init__()
        self.startTuplet: m21.duration.Tuplet = startTuplet


class MeiTieSpanner(MeiTemporarySpanner):
    def __init__(
        self,
        startTie: m21.tie.Tie,
        startParentChord: m21.chord.Chord | None
    ) -> None:
        super().__init__()
        self.startTie: m21.tie.Tie = startTie
        self.startParentChord: m21.chord.Chord | None = startParentChord


_M21_OBJECT_CONVERTER: dict[str, t.Callable[
    [m21.base.Music21Object, TreeBuilder],
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
    'TempoIndication': 'tempo',
    'TempoText': 'tempo',
    'MetronomeMark': 'tempo',
    'MetricModulation': 'tempo'
}
