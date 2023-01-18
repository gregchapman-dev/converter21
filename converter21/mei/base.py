# ------------------------------------------------------------------------------
# Name:          base.py
# Purpose:       MEI parser
#
# Authors:       Greg Chapman <gregc@mac.com>
#                The core of this code was based on the MEI parser (primarily written
#                by Christopher Antila) in https://github.com/cuthbertLab/music21
#                (music21 is Copyright 2006-2022 by Michael Scott Asato Cuthbert)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
'''
These are the public interfaces for the MEI module by Christopher Antila

To convert a string with MEI markup into music21 objects,
use :meth:`~converter21.mei.MeiToM21Converter.convertFromString`.

In the future, most of the functions in this module should be moved to a separate, import-only
module, so that functions for writing music21-to-MEI will fit nicely.

**Simple "How-To"**

Use :class:`MeiToM21Converter` to convert a string to a set of music21 objects. In the future, the
:class:`M21ToMeiConverter` class will convert a set of music21 objects into a string with an MEI
document.

>>> meiString = """<?xml version="1.0" encoding="UTF-8"?>
... <mei xmlns="http://www.music-encoding.org/ns/mei" meiversion="2013">
...     <music>
...     <score>
...         <scoreDef meter.count="6" meter.unit="8">
...             <staffGrp>
...                 <staffDef n="1" clef.shape="F" clef.line="4"/>
...             </staffGrp>
...         </scoreDef>
...         <section>
...             <scoreDef key.sig="1f" key.mode="major"/>
...             <measure n="1">
...                 <staff n="1">
...                     <layer n="1">
...                         <beam>
...                             <note pname="E" oct="3" dur="8" artic="stacc"/>
...                             <note pname="E" oct="3" dur="8"/>
...                             <note pname="E" oct="3" dur="8"/>
...                         </beam>
...                         <chord dur="4" dots="1">
...                             <note pname="F" oct="2"/>
...                             <note pname="A" oct="2" accid="f"/>
...                         </chord>
...                     </layer>
...                 </staff>
...             </measure>
...         </section>
... </score>
...     </music>
... </mei>
... """
>>> from converter21.mei.base import MeiToM21Converter
>>> conv = MeiToM21Converter(meiString)
>>> result = conv.run()
>>> result
<music21.stream.Score 0x10ee474f0>

**Terminology**

This module's documentation adheres to the following terminology regarding XML documents, using
this snippet, ``<note pname="C"/>`` as an example:

- the entire snippet is an *element*.
- the word ``note`` is the *tag*.
- the word ``pname`` is an *attribute*.
- the letter ``C`` is a *value*.

Because Python also uses "attributes," an XML attribute is always preceded by an "at sign," as in
@pname, whereas a Python attribute is set as :attr:`pname`.

**Ignored Elements**

The following elements are not yet imported, though you might expect they would be:

* <sb>: a system break, since this is not usually semantically significant
* <lb>: a line break, since this is not usually semantically significant
* <pb>: a page break, since this is not usually semantically significant

**Where Elements Are Processed**

Most elements are processed in functions called :func:`tagFromElement`, where "tag" is replaced by
the element's tag name (e.g., :func:`staffDefFromElement` for <staffDef> elements). These functions
convert from a Python :class:`xml.etree.ElementTree.Element`
object to the appropriate music21 object.

However, certain elements are processed primarily in
another way, by "private" functions that are not
documented in this API. Rather than converting an :class:`Element` object into a music21 object,
these functions modify the MEI document tree by adding instructions for the :func:`tagFromElement`
functions. The elements processed by private functions include:

* <slur>
* <tie>
* <beamSpan>
* <tupletSpan>

Whereas you can expect functions like :func:`clefFromElement`
to convert a <clef> into a :class:`Clef`
with no loss of information. Because we cannot provide a simple one-to-one conversion for  slurs,
ties, and tuplets, we have kept their conversion functions "private,"
to emphasize the fact that you
must use the :class:`MeiToM21Converter` to process them properly.

**Guidelines for Encoders**

While we aim for the best possible compatibility, the MEI
specification is very large. The following
guidelines will help you produce a file that this MEI-to-music21 module will import correctly and
in the most efficient way. These should not necessarily be considered recommendations when using
MEI in any other context.

* Tuplets indicated only in a @tuplet attribute do not work.
* For elements that allow @startid, @endid, and @plist attributes,
  use all three for faster importing.
* For a <tupletSpan> that does not specify a @plist attribute, a tuplet spanning more than two
  measures will always and unavoidably be imported incorrectly.
* For any tuplet, specify at least @num and @numbase. The module refuses to import a tuplet that
  does not have the @numbase attribute.
* Retain consistent @n values for the same layer, staff, and instrument throughout the score.
* Always indicate the duration of <mRest> and <mSpace> elements.
* Avoid using the <barLine> element if you require well-formatted output from music21, since (as of
  January 2015) the music21-to-something converters will only output a :class:`Barline` that is
  part of a :class:`Measure`.

**List of Supported Elements**

Alphabetical list of the elements currently supported by this module:

* :func:`accidFromElement`
* :func:`articFromElement`
* :func:`barLineFromElement`
* :func:`beamFromElement`
* :func:`chordFromElement`
* :func:`clefFromElement`
* :func:`dotFromElement`
* :func:`instrDefFromElement`
* :func:`layerFromElement`
* :func:`measureFromElement`
* :func:`noteFromElement`
* :func:`restFromElement`
* :func:`mRestFromElement`
* :func:`spaceFromElement`
* :func:`mSpaceFromElement`
* :func:`scoreFromElement`
* :func:`scoreDefFromElement`
* :func:`sectionFromElement`
* :func:`staffFromElement`
* :func:`staffDefFromElement`
* :func:`staffGrpFromElement`
* :func:`sylFromElement`
* :func:`tupletFromElement`
* :func:`verseFromElement`

To know which MEI attributes are known to import correctly, read the documentation for the relevant
element. For example, to know whether the @color attribute on a <note> element is supported, read
the "Attributes/Elements Implemented" section of the :func:`noteFromElement` documentation.

**List of Ignored Elements**

The following elements are (silently) ignored by the MEI-to-music21 converter because they primarily
affect the layout and typesetting of a musical score. We may choose to implement these elements in
the future, but they are a lower priority because music21 is not primarily a layout or typesetting
tool.

* <multiRest>: a multi-measure rest (these will be "converted" to single-measure rests)
* <pb>: a page break
* <lb>: a line break
* <sb>: a system break

'''
import typing as t
from xml.etree.ElementTree import Element, ParseError, fromstring, ElementTree
import re
import html

from collections import defaultdict
from copy import deepcopy
from fractions import Fraction  # for typing
from uuid import uuid4

# music21
from music21.base import Music21Object
from music21.common.types import OffsetQL
from music21.common.numberTools import opFrac
from music21 import articulations
from music21 import bar
from music21 import beam
from music21 import chord
from music21 import clef
from music21 import duration
from music21 import dynamics
from music21 import environment
from music21 import exceptions21
from music21 import expressions
from music21 import instrument
from music21 import interval
from music21 import key
from music21 import metadata
from music21 import meter
from music21 import note
from music21 import pitch
from music21 import spanner
from music21 import stream
from music21 import style
from music21 import tempo
from music21 import tie

from converter21.shared import SharedConstants
from converter21.shared import M21Utilities

environLocal = environment.Environment('converter21.mei.base')


# Module-Level Constants
# -----------------------------------------------------------------------------
_XMLID = '{http://www.w3.org/XML/1998/namespace}id'
MEI_NS = '{http://www.music-encoding.org/ns/mei}'
# when these tags aren't processed, we won't worry about them (at least for now)
_IGNORE_UNPROCESSED = (
    # f'{MEI_NS}sb',        # system break
    # f'{MEI_NS}lb',        # line break
    # f'{MEI_NS}pb',        # page break
    f'{MEI_NS}annot',       # annotations are skipped; someday maybe goes into editorial?
    f'{MEI_NS}slur',        # slurs; handled in convertFromString()
    f'{MEI_NS}tie',         # ties; handled in convertFromString()
    f'{MEI_NS}tupletSpan',  # tuplets; handled in convertFromString()
    f'{MEI_NS}beamSpan',    # beams; handled in convertFromString()
    f'{MEI_NS}verse',       # lyrics; handled separately by noteFromElement()
    f'{MEI_NS}instrDef',    # instrument; handled separately by staffDefFromElement()
    f'{MEI_NS}measure',     # measure; handled separately by {score,section}FromElement()
)


# Exceptions
# -----------------------------------------------------------------------------
class MeiValidityError(exceptions21.Music21Exception):
    '''When there is an otherwise-unspecified validity error that prevents parsing.'''
    pass


class MeiValueError(exceptions21.Music21Exception):
    '''When an attribute has an invalid value.'''
    pass


class MeiAttributeError(exceptions21.Music21Exception):
    '''When an element has an invalid attribute.'''
    pass


class MeiElementError(exceptions21.Music21Exception):
    '''When an element itself is invalid.'''
    pass

class MeiInternalError(exceptions21.Music21Exception):
    '''When an internal assumption is broken.'''
    pass


# Text Strings for Error Conditions
# -----------------------------------------------------------------------------
# NOTE: these are all collected handily at the top for two reasons: help you find the easier, and
#       help you translate them easier
_TEST_FAILS = 'MEI module had {} failures and {} errors; run music21/mei/base.py to find out more.'
_INVALID_XML_DOC = 'MEI document is not valid XML.'
_WRONG_ROOT_ELEMENT = 'Root element should be <mei> in the MEI namespace, not <{}>.'
_UNKNOWN_TAG = 'Found unexpected tag while parsing MEI: <{}>.'
_UNEXPECTED_ATTR_VALUE = 'Unexpected value for "{}" attribute: {}, ignoring.'
_SEEMINGLY_NO_PARTS = 'There appear to be no <staffDef> tags in this score.'
_STAFF_MUST_HAVE_N = 'Found a <staff> tag with no @n attribute'
_STAFFITEM_MUST_HAVE_VALID_STAFF = 'Staff item "{}" found with invalid @staff="{}".'
_MISSING_VOICE_ID = 'Found a <layer> without @n attribute and no override.'
_CANNOT_FIND_XMLID = 'Could not find the @{} so we could not create the {}.'
_MISSING_TUPLET_DATA = 'Both @num and @numbase attributes are required on <tuplet> tags.'
_UNIMPLEMENTED_IMPORT_WITHOUT = 'Importing {} without {} is not yet supported.'
_UNIMPLEMENTED_IMPORT_WITH = 'Importing {} with {} is not yet supported.'
_UNPROCESSED_SUBELEMENT = 'Found an unprocessed <{}> element in a <{}>.'
_MISSED_DATE = 'Unable to decipher the composition date "{}"'
_BAD_VERSE_NUMBER = 'Verse number must be an int (got "{}")'
_EXTRA_KEYSIG_IN_STAFFDEF = 'Multiple keys specified in <staffdef>, ignoring {} in favor of {}'
_EXTRA_METERSIG_IN_STAFFDEF = 'Multiple meters specified in <staffdef> ignoring {} in favor of {}'
_EXTRA_CLEF_IN_STAFFDEF = 'Multiple clefs specified in <staffdef> ignoring {} in favor of {}'

# Module-level Functions
# -----------------------------------------------------------------------------
class MeiToM21Converter:
    '''
    A :class:`MeiToM21Converter` instance manages the conversion of an MEI document into music21
    objects.

    If ``theDocument`` does not have <mei> as the root element, the class raises an
    :class:`MeiElementError`. If ``theDocument`` is not a valid XML file, the class raises an
    :class:`MeiValidityError`.

    :param str theDocument: A string containing an MEI document.
    :raises: :exc:`MeiElementError` when the root element is not <mei>
    :raises: :exc:`MeiValidityError` when the MEI file is not valid XML.
    '''

    def __init__(self, theDocument: t.Optional[str] = None) -> None:
        #  The __init__() documentation doesn't isn't processed by Sphinx,
        #  so I put it at class level.
        environLocal.printDebug('*** initializing MeiToM21Converter')

        self.documentRoot: Element

        if theDocument is None:
            # Without this, the class can't be pickled.
            self.documentRoot = Element(f'{MEI_NS}mei')
        else:
            try:
                self.documentRoot = fromstring(theDocument)
            except ParseError as parseErr:
                environLocal.warn(
                    '\n\nERROR: Parsing the MEI document with ElementTree failed.')
                environLocal.warn(f'We got the following error:\n{parseErr}')
                raise MeiValidityError(_INVALID_XML_DOC)

            if isinstance(self.documentRoot, ElementTree):
                self.documentRoot = self.documentRoot.getroot()

            if f'{MEI_NS}mei' != self.documentRoot.tag:
                raise MeiElementError(_WRONG_ROOT_ELEMENT.format(self.documentRoot.tag))

        # This defaultdict stores extra, music21-specific attributes that we add to elements to help
        # importing. The key is an element's @xml:id, and the value is a regular dict with keys
        # corresponding to attributes we'll add and values
        # corresponding to those attributes' values.
        self.m21Attr: defaultdict = defaultdict(lambda: {})

        # This SpannerBundle holds (among other things) the slurs that will be created by
        # _ppSlurs() and used while importing whatever note, rest, chord, or other object.
        self.spannerBundle: spanner.SpannerBundle = spanner.SpannerBundle()

    def run(self) -> t.Union[stream.Score, stream.Part, stream.Opus]:
        '''
        Run conversion of the internal MEI document to produce a music21 object.

        Returns a :class:`~music21.stream.Stream` subclass, depending on the MEI document.
        '''

        environLocal.printDebug('*** pre-processing spanning/timestamped elements')

        _ppSlurs(self)
        _ppTies(self)
        _ppBeams(self)
        _ppTuplets(self)

        _ppFermatas(self)
        _ppArpeggios(self)
        _ppOctaves(self)

        _ppTrills(self)
        _ppMordents(self)
        _ppTurns(self)

        _ppConclude(self)

        environLocal.printDebug('*** processing <score> elements')
        scoreElem: t.Optional[Element] = self.documentRoot.find(f'.//{MEI_NS}music//{MEI_NS}score')
        if scoreElem is None:
            # no <score> found, return an empty Score
            return stream.Score()

        otherInfo: t.Dict = {}
        activeMeter: t.Optional[meter.TimeSignature] = None
        theScore: stream.Score = scoreFromElement(
            scoreElem, activeMeter, self.spannerBundle, otherInfo
        )

        environLocal.printDebug('*** preparing metadata')
        theScore.metadata = makeMetadata(self.documentRoot)

        return theScore


# Module-level Functions
# -----------------------------------------------------------------------------
def safePitch(
    name: str,
    accidental: t.Optional[t.Union[pitch.Accidental, str]] = None,
    octave: t.Union[str, int] = ''
) -> pitch.Pitch:
    '''
    Safely build a :class:`~music21.pitch.Pitch` from a string.

    When :meth:`~music21.pitch.Pitch.__init__` is given an empty string,
    it raises a :exc:`~music21.pitch.PitchException`. This
    function instead returns a default :class:`~music21.pitch.Pitch` instance.

    name: Desired name of the :class:`~music21.pitch.Pitch`.

    accidental: (Optional) Symbol for the accidental.

    octave: (Optional) Octave number.

    Returns A :class:`~music21.pitch.Pitch` with the appropriate properties.

    >>> from converter21.mei.base import safePitch  # OMIT_FROM_DOCS
    >>> safePitch('D#6')
    <music21.pitch.Pitch D#6>
    >>> safePitch('D', '#', '6')
    <music21.pitch.Pitch D#6>
    >>> safePitch('D', '#')
    <music21.pitch.Pitch D#>
    '''
    if not name:
        return pitch.Pitch()
    if octave and accidental is not None:
        return pitch.Pitch(name, octave=int(octave), accidental=accidental)
    if octave:
        return pitch.Pitch(name, octave=int(octave))
    if accidental is not None:
        return pitch.Pitch(name, accidental=accidental)
    return pitch.Pitch(name)


def makeDuration(
    base: t.Union[float, int, Fraction] = 0.0,
    dots: int = 0
) -> duration.Duration:
    '''
    Given a ``base`` duration and a number of ``dots``, create a :class:`~music21.duration.Duration`
    instance with the
    appropriate ``quarterLength`` value.

    Returns a :class:`Duration` corresponding to the fully-augmented value.

    **Examples**

    >>> from converter21.mei.base import makeDuration
    >>> from fractions import Fraction
    >>> makeDuration(base=2.0, dots=0).quarterLength  # half note, no dots
    2.0
    >>> makeDuration(base=2.0, dots=1).quarterLength  # half note, one dot
    3.0
    >>> makeDuration(base=2, dots=2).quarterLength  # 'base' can be an int or float
    3.5
    >>> makeDuration(2.0, 10).quarterLength  # you want ridiculous dots? Sure...
    3.998046875
    >>> makeDuration(0.33333333333333333333, 0).quarterLength  # works with fractions too
    Fraction(1, 3)
    >>> makeDuration(Fraction(1, 3), 1).quarterLength
    0.5
    '''
    returnDuration: duration.Duration = duration.Duration(base)
    returnDuration.dots = dots
    return returnDuration


def allPartsPresent(scoreElem: Element) -> t.Tuple[t.Tuple[str, ...], str]:
    # noinspection PyShadowingNames
    '''
    Find the @n values for all <staffDef> elements in a <score> element. This assumes that every
    MEI <staff> corresponds to a music21 :class:`~music21.stream.Part`.

    scoreElem is the <score> `Element` in which to find the staff names.
    Returns a tuple containing all the unique @n values associated with a staff in the <score>.
    Returns also, the specific unique @n value associated with the top staff of the score.

    **Example**

    >>> meiDoc = """<?xml version="1.0" encoding="UTF-8"?>
    ... <score xmlns="http://www.music-encoding.org/ns/mei">
    ...     <scoreDef>
    ...         <staffGrp>
    ...             <staffDef n="1" clef.shape="G" clef.line="2"/>
    ...             <staffDef n="2" clef.shape="F" clef.line="4"/>
    ...         </staffGrp>
    ...     </scoreDef>
    ...     <section>
    ...         <!-- ... some music ... -->
    ...         <staffDef n="2" clef.shape="C" clef.line="4"/>
    ...         <!-- ... some music ... -->
    ...     </section>
    ... </score>"""
    >>> import xml.etree.ElementTree as ETree
    >>> from converter21.mei.base import allPartsPresent
    >>> meiDoc = ETree.fromstring(meiDoc)
    >>> allPartsPresent(meiDoc)
    (('1', '2'), '1')

    Even though there are three <staffDef> elements in the document, there are only two unique @n
    attributes. The second appearance of <staffDef> with @n="2" signals a change of clef on that
    same staff---not that there is a new staff.
    '''
    # xpathQuery = f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}staffDef'
    xpathQuery: str = f'.//{MEI_NS}staffDef'
    partNs: t.List[str] = []  # hold the @n attribute for all the parts
    topPart: str = ''

    for staffDef in scoreElem.findall(xpathQuery):
        nStr: t.Optional[str] = staffDef.get('n')
        if nStr and nStr not in partNs:
            partNs.append(nStr)
            if not topPart:
                # This first 'n' we see is special, it's the 'n' of the top staff
                topPart = nStr

    if not partNs:
        raise MeiValidityError(_SEEMINGLY_NO_PARTS)

    return tuple(partNs), topPart


# Constants for One-to-One Translation
# -----------------------------------------------------------------------------
# for _accidentalFromAttr()
# None is for when @accid is omitted
_ACCID_ATTR_DICT: t.Dict[t.Optional[str], t.Optional[str]] = {
    's': '#', 'f': '-', 'ss': '##', 'x': '##', 'ff': '--', 'xs': '###',
    'ts': '###', 'tf': '---', 'n': 'n', 'nf': '-', 'ns': '#',
    'su': '#~', 'sd': '~', 'fu': '`', 'fd': '-`', 'nu': '~', 'nd': '`',
    '1qf': '`', '3qf': '-`', '1qs': '~', '3qs': '#~',
    None: None
}

# for _accidGesFromAttr()
# None is for when @accid is omitted
_ACCID_GES_ATTR_DICT: t.Dict[t.Optional[str], t.Optional[str]] = {
    's': '#', 'f': '-', 'ss': '##', 'ff': '--', 'n': 'n',
    'su': '#~', 'sd': '~', 'fu': '`', 'fd': '-`',
    None: None
}

# for _qlDurationFromAttr()
# None is for when @dur is omitted; it's silly so it can be identified
_DUR_ATTR_DICT: t.Dict[t.Optional[str], float] = {
    'maxima': 32.0,                # maxima is not mei-CMN, but we'll allow it
    'long': 16.0, 'longa': 16.0,   # longa is not mei-CMN, but we'll allow it
    'breve': 8.0, 'brevis': 8.0,   # brevis is not mei-CMN, but we'll allow it
    '1': 4.0, 'semibrevis': 4.0,   # semibrevis is not mei-CMN, but we'll allow it
    '2': 2.0, 'minima': 2.0,       # minima is not mei-CMN, but we'll allow it
    '4': 1.0, 'semiminima': 1.0,   # semiminima is not mei-CMN, but we'll allow it
    '8': 0.5, 'fusa': 0.5,         # fusa is not mei-CMN, but we'll allow it
    '16': 0.25, 'semifusa': 0.25,  # semifusa is not mei-CMN, but we'll allow it
    '32': 0.125,
    '64': 0.0625,
    '128': 0.03125,
    '256': 0.015625,
    '512': 0.0078125,
    '1024': 0.00390625,
    '2048': 0.001953125,
    None: 0.00390625
}

_DUR_TO_NUMBEAMS: t.Dict[str, int] = {
    # not present implies zero beams
    '8': 1, 'fusa': 1,       # fusa is not mei-CMN, but we'll allow it
    '16': 2, 'semifusa': 2,  # semifusa is not mei-CMN, but we'll allow it
    '32': 3,
    '64': 4,
    '128': 5,
    '256': 6,
    '512': 7,
    '1024': 8,
    '2048': 9
}

_QL_TO_NUMFLAGS: t.Dict[OffsetQL, int] = {
    # not present implies zero beams
    0.5: 1,  # 0.5ql is an eighth note -> one beam
    0.25: 2,
    0.125: 3,
    0.0625: 4,
    0.03125: 5,
    0.015625: 6,
    0.0078125: 7,
    0.00390625: 8,
    0.001953125: 9
}

_STEMMOD_TO_NUMSLASHES: t.Dict[str, int] = {
    # not present implies zero slashes
    '1slash': 1,
    '2slash': 2,
    '3slash': 3,
    '4slash': 4,
    '5slash': 5,
    '6slash': 6,
    '7slash': 7,
    '8slash': 8,
    '9slash': 9  # not actually supported, but might happen
}

# for _articulationFromAttr()
# NOTE: 'marc-stacc' and 'ten-stacc' require multiple music21 events, so they are handled
#       separately in _articulationFromAttr().
_ARTIC_ATTR_DICT: t.Dict[t.Optional[str], t.Type] = {
    'acc': articulations.Accent,
    'stacc': articulations.Staccato,
    'ten': articulations.Tenuto,
    'stacciss': articulations.Staccatissimo,
    'marc': articulations.StrongAccent,
    'spicc': articulations.Spiccato,
    'doit': articulations.Doit,
    'plop': articulations.Plop,
    'fall': articulations.Falloff,
    'dnbow': articulations.DownBow,
    'upbow': articulations.UpBow,
    'harm': articulations.Harmonic,
    'snap': articulations.SnapPizzicato,
    'stop': articulations.Stopped,
    'open': articulations.OpenString,  # this may also mean "no mute?"
    'dbltongue': articulations.DoubleTongue,
    'toe': articulations.OrganToe,
    'trpltongue': articulations.TripleTongue,
    'heel': articulations.OrganHeel,
    # TODO: these aren't implemented in music21, so I'll make new ones
    'tap': articulations.Articulation,
    'lhpizz': articulations.Articulation,
    'dot': articulations.Articulation,
    'stroke': articulations.Articulation,
    'rip': articulations.Articulation,
    'bend': articulations.Articulation,
    'flip': articulations.Articulation,
    'smear': articulations.Articulation,
    'fingernail': articulations.Articulation,  # (u1D1B3)
    'damp': articulations.Articulation,
    'dampall': articulations.Articulation,
}

# for _barlineFromAttr()
# TODO: make new music21 Barline styles for 'dbldashed' and 'dbldotted'
_BAR_ATTR_DICT: t.Dict[t.Optional[str], str] = {
    'dashed': 'dashed',
    'dotted': 'dotted',
    'dbl': 'double',
    'end': 'final',
    'invis': 'none',
    'single': 'regular',
}

# for _stemDirectionFromAttr()
_STEMDIR_ATTR_DICT: t.Dict[t.Optional[str], t.Optional[str]] = {
    'down': 'down',
    'up': 'up'
}


# One-to-One Translator Functions
# -----------------------------------------------------------------------------
def _attrTranslator(
    attr: t.Optional[str],
    name: str,
    mapping: t.Dict[t.Optional[str], t.Any]
) -> t.Any:
    '''
    Helper function for other functions that need to translate the value of an attribute to another
    known value. :func:`_attrTranslator` tries to return the value of ``attr`` in ``mapping`` and,
    if ``attr`` isn't in ``mapping``, an exception is raised.

    :param str attr: The value of the attribute to look up in ``mapping``.
    :param str name: Name of the attribute, used when raising an exception (read below).
    :param mapping: A mapping type (nominally a dict) with relevant key-value pairs.

    :raises: :exc:`MeiValueError` when ``attr`` is not found in ``mapping``. The error message will
        be of this format: 'Unexpected value for "name" attribute: attr'.

    Examples:

    >>> from converter21.mei.base import _attrTranslator, _ACCID_ATTR_DICT, _DUR_ATTR_DICT
    >>> _attrTranslator('s', 'accid', _ACCID_ATTR_DICT)
    '#'
    >>> _attrTranslator('9', 'dur', _DUR_ATTR_DICT) == None
    True
    '''
    try:
        return mapping[attr]
    except KeyError:
        # rather than raising an exception, simply warn
        environLocal.warn(_UNEXPECTED_ATTR_VALUE.format(name, attr))
        return None


def _accidentalFromAttr(attr: t.Optional[str]) -> t.Optional[str]:
    '''
    Use :func:`_attrTranslator` to convert the value of an "accid" attribute to its music21 string.

    >>> from converter21.mei.base import _accidentalFromAttr
    >>> _accidentalFromAttr('s')
    '#'
    '''
    return _attrTranslator(attr, 'accid', _ACCID_ATTR_DICT)


def _accidGesFromAttr(attr: t.Optional[str]) -> t.Optional[str]:
    '''
    Use :func:`_attrTranslator` to convert the value of an @accid.ges
    attribute to its music21 string.

    >>> from converter21.mei.base import _accidGesFromAttr
    >>> _accidGesFromAttr('s')
    '#'
    '''
    return _attrTranslator(attr, 'accid.ges', _ACCID_GES_ATTR_DICT)


def _qlDurationFromAttr(attr: t.Optional[str]) -> float:
    '''
    Use :func:`_attrTranslator` to convert an MEI "dur" attribute to a music21 quarterLength.

    >>> from converter21.mei.base import _qlDurationFromAttr
    >>> _qlDurationFromAttr('4')
    1.0

    .. note:: This function only handles data.DURATION.cmn, not data.DURATION.mensural.
    '''
    return _attrTranslator(attr, 'dur', _DUR_ATTR_DICT)


def _articulationFromAttr(attr: t.Optional[str]) -> t.Tuple[articulations.Articulation, ...]:
    '''
    Use :func:`_attrTranslator` to convert an MEI "artic" attribute to a
    :class:`music21.articulations.Articulation` subclass.

    :returns: A **tuple** of one or two :class:`Articulation` subclasses.

    .. note:: This function returns a singleton tuple *unless* ``attr`` is ``'marc-stacc'`` or
        ``'ten-stacc'``. These return ``(StrongAccent, Staccato)`` and ``(Tenuto, Staccato)``,
        respectively.
    '''
    if 'marc-stacc' == attr:
        return (articulations.StrongAccent(), articulations.Staccato())
    elif 'ten-stacc' == attr:
        return (articulations.Tenuto(), articulations.Staccato())
    else:
        articClass: t.Type = _attrTranslator(attr, 'artic', _ARTIC_ATTR_DICT)
        if articClass is not None:
            return (articClass(),)
    return tuple()  # empty t.Tuple


def _makeArticList(attr: str) -> t.List[articulations.Articulation]:
    '''
    Use :func:`_articulationFromAttr` to convert the actual value of an MEI "artic" attribute
    (including multiple items) into a list suitable for :attr:`GeneralNote.articulations`.
    '''
    articList: t.List[articulations.Articulation] = []
    for eachArtic in attr.split(' '):
        articList.extend(_articulationFromAttr(eachArtic))
    return articList


def _getOctaveShift(dis: t.Optional[str], disPlace: t.Optional[str]) -> int:
    '''
    Use :func:`_getOctaveShift` to calculate the :attr:`octaveShift` attribute for a
    :class:`~music21.clef.Clef` subclass. Any of the arguments may be ``None``.

    :param str dis: The "dis" attribute from the <clef> tag.
    :param str disPlace: The "dis.place" attribute from the <clef> tag.

    :returns: The octave displacement compared to the clef's normal position. This may be 0.
    :rtype: integer
    '''
    # NB: dis: 8, 15, or 22 (or "ottava" clefs)
    # NB: dis.place: "above" or "below" depending on whether the ottava clef is Xva or Xvb
    octavesDict = {None: 0, '8': 1, '15': 2, '22': 3}
    if dis not in octavesDict:
        return 0

    if 'below' == disPlace:
        return -1 * octavesDict[dis]
    else:
        return octavesDict[dis]


def _sharpsFromAttr(signature: t.Optional[str]) -> int:
    '''
    Use :func:`_sharpsFromAttr` to convert MEI's ``data.KEYSIGNATURE`` datatype to an integer
    representing the number of sharps, for use with music21's :class:`~music21.key.KeySignature`.

    :param str signature: The @key.sig attribute, or the @sig attribute
    :returns: The number of sharps.
    :rtype: int

    >>> from converter21.mei.base import _sharpsFromAttr
    >>> _sharpsFromAttr('3s')
    3
    >>> _sharpsFromAttr('3f')
    -3
    >>> _sharpsFromAttr('0')
    0
    >>> _sharpsFromAttr(None)
    0
    '''
    if not signature:
        return 0
    elif signature.startswith('0'):
        return 0
    elif signature.endswith('s'):
        return int(signature[0])
    else:
        return -1 * int(signature[0])

def _stemDirectionFromAttr(stemDirStr: str) -> str:
    return _attrTranslator(stemDirStr, 'stem.dir', _STEMDIR_ATTR_DICT)



# "Preprocessing" and "Postprocessing" Functions for convertFromString()
# -----------------------------------------------------------------------------
def _ppSlurs(theConverter: MeiToM21Converter):
    # noinspection PyShadowingNames
    '''
    Pre-processing helper for :func:`convertFromString` that handles slurs specified in <slur>
    elements. The input is a :class:`MeiToM21Converter` with data about the file currently being
    processed. This function reads from ``theConverter.documentRoot`` and writes into
    ``theConverter.m21Attr`` and ``theConverter.spannerBundle``.

    :param theConverter: The object responsible for storing data about this import.
    :type theConverter: :class:`MeiToM21Converter`.

    **This Preprocessor**

    The slur preprocessor adds @m21SlurStart and @m21SlurEnd attributes to elements that are at the
    beginning or end of a slur. The value of these attributes is the ``idLocal`` of a :class:`Slur`
    in the :attr:`spannerBundle` attribute of ``theConverter``. This attribute is not part of the
    MEI specification, and must therefore be handled specially.

    If :func:`noteFromElement` encounters an element like ``<note m21SlurStart="82f87cd7"/>``, the
    resulting :class:`music21.note.Note` should be set as the starting point of the slur with an
    ``idLocal`` of ``'82f87cd7'``.

    **Example of Changes to ``m21Attr``**

    The ``theConverter.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
    dict for non-existant keys. The defaultdict stores the @xml:id attribute of an element; the
    dict holds attribute names and their values that should be added to the element with the
    given @xml:id.

    For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
    element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.

    **Example**

    Consider the following example.

    >>> meiDoc = """<?xml version="1.0" encoding="UTF-8"?>
    ... <mei xmlns="http://www.music-encoding.org/ns/mei" meiversion="2013">
    ...     <music><score>
    ...     <section>
    ...         <note xml:id="1234"/>
    ...         <note xml:id="2345"/>
    ...         <slur startid="#1234" endid="#2345"/>
    ...     </section>
    ...     </score></music>
    ... </mei>"""
    >>> from converter21.mei import MeiToM21Converter
    >>> from converter21.mei.base import _ppSlurs
    >>> theConverter = MeiToM21Converter(meiDoc)
    >>>
    >>> _ppSlurs(theConverter)
    >>> 'm21SlurStart' in theConverter.m21Attr['1234']
    True
    >>> 'm21SlurEnd' in theConverter.m21Attr['2345']
    True
    >>> theConverter.spannerBundle
    <music21.spanner.SpannerBundle of size 1>
    >>> firstSpanner = list(theConverter.spannerBundle)[0]
    >>> (theConverter.m21Attr['1234']['m21SlurStart'] ==
    ...  theConverter.m21Attr['2345']['m21SlurEnd'] ==
    ...  firstSpanner.idLocal)
    True

    This example is a little artificial because of the limitations of a doctest, where we need
    to know all values in advance. The point here is that the values of 'm21SlurStart' and
    'm21SlurEnd' of a particular slur-attached object will match the 'idLocal' of a slur in
    :attr:`spannerBundle`. The "id" is a UUID determined at runtime, which looks something like
    ``'d3731f89-8a2f-4b82-ad02-f0bc6f5f8b04'``.
    '''
    environLocal.printDebug('*** pre-processing slurs')
    # for readability, we use a single-letter variable
    c = theConverter
    # pre-processing for <slur> tags
    for eachSlur in c.documentRoot.iterfind(
            f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}slur'
    ):
        if eachSlur.get('startid') is not None and eachSlur.get('endid') is not None:
            thisIdLocal = str(uuid4())
            thisSlur = spanner.Slur()
            if t.TYPE_CHECKING:
                # work around Spanner.idLocal being incorrectly type-hinted as None
                assert isinstance(thisSlur.idLocal, str)
            thisSlur.idLocal = thisIdLocal
            c.spannerBundle.append(thisSlur)

            c.m21Attr[removeOctothorpe(eachSlur.get('startid'))]['m21SlurStart'] = thisIdLocal
            c.m21Attr[removeOctothorpe(eachSlur.get('endid'))]['m21SlurEnd'] = thisIdLocal
        else:
            environLocal.warn(_UNIMPLEMENTED_IMPORT_WITHOUT.format('<slur>', '@startid and @endid'))


def _ppTies(theConverter: MeiToM21Converter):
    '''
    Pre-processing helper for :func:`convertFromString` that handles ties specified in <tie>
    elements. The input is a :class:`MeiToM21Converter` with data about the file currently being
    processed. This function reads from ``theConverter.documentRoot`` and writes into
    ``theConverter.m21Attr``.

    :param theConverter: The object responsible for storing data about this import.
    :type theConverter: :class:`MeiToM21Converter`.

    **This Preprocessor**

    The tie preprocessor works similarly to the slur preprocessor, adding @tie attributes. The
    value of these attributes conforms to the MEI Guidelines, so no special action is required.

    **Example of ``m21Attr``**

    The ``theConverter.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
    dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
    dict holds attribute names and their values that should be added to the element with the
    given @xml:id.

    For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
    element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
    '''
    environLocal.printDebug('*** pre-processing ties')
    # for readability, we use a single-letter variable
    c = theConverter

    for eachTie in c.documentRoot.iterfind(
            f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}tie'):
        startId: t.Optional[str] = removeOctothorpe(eachTie.get('startid'))
        endId: t.Optional[str] = removeOctothorpe(eachTie.get('endid'))
        if startId is not None and endId is not None:
            if startId in c.m21Attr and c.m21Attr[startId].get('tie', '') == 't':
                # the startid note is already a tie end, so now it's both end and start
                c.m21Attr[startId]['tie'] = 'ti'
            else:
                c.m21Attr[startId]['tie'] = 'i'

            if endId in c.m21Attr and c.m21Attr[endId].get('tie', '') == 'i':
                # the endid note is already a tie start, so now it's both end and start
                c.m21Attr[endId]['tie'] = 'it'
            else:
                c.m21Attr[endId]['tie'] = 't'
        else:
            environLocal.warn(_UNIMPLEMENTED_IMPORT_WITHOUT.format('<tie>', '@startid and @endid'))


def _ppBeams(theConverter: MeiToM21Converter):
    '''
    Pre-processing helper for :func:`convertFromString` that handles beams specified in <beamSpan>
    elements. The input is a :class:`MeiToM21Converter` with data about the file currently being
    processed. This function reads from ``theConverter.documentRoot`` and writes into
    ``theConverter.m21Attr``.

    :param theConverter: The object responsible for storing data about this import.
    :type theConverter: :class:`MeiToM21Converter`.

    **This Preprocessor**

    The beam preprocessor works similarly to the slur preprocessor, adding the @m21Beam attribute.
    The value of this attribute is either ``'start'``, ``'continue'``, or ``'stop'``, indicating
    the music21 ``type`` of the primary beam attached to this element. This attribute is not
    part of the MEI specification, and must therefore be handled specially.

    **Example of ``m21Attr``**

    The ``theConverter.m21Attr`` argument must be a defaultdict that returns an empty (regular)
    dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
    dict holds attribute names and their values that should be added to the element with the
    given @xml:id.

    For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
    element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
    '''
    environLocal.printDebug('*** pre-processing beams')
    # for readability, we use a single-letter variable
    c = theConverter

    # pre-processing for <beamSpan> elements
    for eachBeam in c.documentRoot.iterfind(
            f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}beamSpan'):
        if eachBeam.get('startid') is None or eachBeam.get('endid') is None:
            environLocal.warn(
                _UNIMPLEMENTED_IMPORT_WITHOUT.format('<beamSpan>', '@startid and @endid')
            )
            continue

        c.m21Attr[removeOctothorpe(eachBeam.get('startid'))]['m21Beam'] = 'start'
        c.m21Attr[removeOctothorpe(eachBeam.get('endid'))]['m21Beam'] = 'stop'

        # iterate things in the @plist attribute
        for eachXmlid in eachBeam.get('plist', '').split(' '):
            eachXmlid = removeOctothorpe(eachXmlid)  # type: ignore
            # if not eachXmlid:
            #     # this is either @plist not set or extra spaces around the contained xml:id values
            #     pass
            if 'm21Beam' not in c.m21Attr[eachXmlid]:
                # only set to 'continue' if it wasn't previously set to 'start' or 'stop'
                c.m21Attr[eachXmlid]['m21Beam'] = 'continue'


def _ppTuplets(theConverter: MeiToM21Converter):
    '''
    Pre-processing helper for :func:`convertFromString` that handles tuplets specified in
    <tupletSpan> elements. The input is a :class:`MeiToM21Converter` with data about the file
    currently being processed. This function reads from ``theConverter.documentRoot`` and writes
    into ``theConverter.m21Attr``.

    :param theConverter: The object responsible for storing data about this import.
    :type theConverter: :class:`MeiToM21Converter`.

    **This Preprocessor**

    The slur preprocessor works similarly to the slur preprocessor, adding @m21TupletNum and
    @m21TupletNumbase attributes. The value of these attributes corresponds to the @num and
    @numbase attributes found on a <tuplet> element. This preprocessor also performs a significant
    amount of guesswork to try to handle <tupletSpan> elements that do not include a @plist
    attribute. This attribute is not part of the MEI specification, and must therefore be handled
    specially.

    **Example of ``m21Attr``**

    The ``theConverter.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
    dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
    dict holds attribute names and their values that should be added to the element with the
    given @xml:id.

    For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
    element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
    '''
    environLocal.printDebug('*** pre-processing tuplets')
    # for readability, we use a single-letter variable
    c = theConverter

    # pre-processing <tupletSpan> tags
    for eachTuplet in c.documentRoot.iterfind(
            f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}tupletSpan'):
        if ((eachTuplet.get('startid') is None or eachTuplet.get('endid') is None)
                and eachTuplet.get('plist') is None):
            environLocal.warn(_UNIMPLEMENTED_IMPORT_WITHOUT.format('<tupletSpan>',
                                                           '@startid and @endid, or @plist'))
        elif eachTuplet.get('plist') is not None:
            # Ideally (for us) <tupletSpan> elements will have a @plist that enumerates the
            # @xml:id of every affected element. In this case, tupletSpanFromElement() can use the
            # @plist to add our custom @m21TupletNum and @m21TupletNumbase attributes.
            for eachXmlid in eachTuplet.get('plist', '').split(' '):
                eachXmlid = removeOctothorpe(eachXmlid)  # type: ignore
                if eachXmlid:
                    # protect against extra spaces around the contained xml:id values
                    c.m21Attr[eachXmlid]['m21TupletNum'] = eachTuplet.get('num')
                    c.m21Attr[eachXmlid]['m21TupletNumbase'] = eachTuplet.get('numbase')
        else:
            # For <tupletSpan> elements that don't give a @plist attribute, we have to do some
            # guesswork and hope we find all the related elements. Right here, we're only setting
            # the "flags" that this guesswork must be done later.
            startid = removeOctothorpe(eachTuplet.get('startid'))
            endid = removeOctothorpe(eachTuplet.get('endid'))

            c.m21Attr[startid]['m21TupletSearch'] = 'start'
            c.m21Attr[startid]['m21TupletNum'] = eachTuplet.get('num')
            c.m21Attr[startid]['m21TupletNumbase'] = eachTuplet.get('numbase')
            c.m21Attr[endid]['m21TupletSearch'] = 'end'
            c.m21Attr[endid]['m21TupletNum'] = eachTuplet.get('num')
            c.m21Attr[endid]['m21TupletNumbase'] = eachTuplet.get('numbase')


def _ppFermatas(theConverter: MeiToM21Converter):
    '''
    Pre-processing helper for :func:`convertFromString` that handles fermats specified in <fermata>
    elements. The input is a :class:`MeiToM21Converter` with data about the file currently being
    processed. This function reads from ``theConverter.documentRoot`` and writes into
    ``theConverter.m21Attr``.

    :param theConverter: The object responsible for storing data about this import.
    :type theConverter: :class:`MeiToM21Converter`.

    **This Preprocessor**

    The fermata preprocessor works similarly to the tie preprocessor, adding @fermata
    attributes. The @fermata attribute looks like it would if specified according to the
    Guidelines (e.g. @fermata="above", where "above" comes from the <fermata> element's
    @place attribute).  The other attributes from the <fermata> element (@form and @shape)
    are also added, prefixed with 'fermata_' as follows: @fermata_form and @fermata_shape.

    **Example of ``m21Attr``**

    The ``theConverter.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
    dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
    dict holds attribute names and their values that should be added to the element with the
    given @xml:id.

    For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
    element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
    '''
    environLocal.printDebug('*** pre-processing fermatas')
    # for readability, we use a single-letter variable
    c = theConverter

    for eachFermata in c.documentRoot.iterfind(
            f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}fermata'):
        startId: t.Optional[str] = removeOctothorpe(eachFermata.get('startid'))
        if startId is None:
            # leave this alone, we'll handle it later in fermataFromElement
            continue

        # mark as handled, so we WON'T handle it later in fermataFromElement
        eachFermata.set('ignore_in_fermataFromElement', 'true')

        place: str = eachFermata.get('place', 'above')  # default @place is "above"
        c.m21Attr[startId]['fermata'] = place

        form: str = eachFermata.get('form', '')
        shape: str = eachFermata.get('shape', '')
        if form:
            c.m21Attr[startId]['fermata_form'] = form
        if shape:
            c.m21Attr[startId]['fermata_shape'] = shape


def _ppTrills(theConverter: MeiToM21Converter):
    '''
    Pre-processing helper for :func:`convertFromString` that handles trills specified in <trill>
    elements. The input is a :class:`MeiToM21Converter` with data about the file currently being
    processed. This function reads from ``theConverter.documentRoot`` and writes into
    ``theConverter.m21Attr``.

    :param theConverter: The object responsible for storing data about this import.
    :type theConverter: :class:`MeiToM21Converter`.

    **This Preprocessor**

    The trill preprocessor works similarly to the tie preprocessor, adding @m21Trill,
    @m21TrillExtStart and @m21TrillExtEnd attributes to any referenced notes/chords.

    **Example of ``m21Attr``**

    The ``theConverter.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
    dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
    dict holds attribute names and their values that should be added to the element with the
    given @xml:id.

    For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
    element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
    '''
    environLocal.printDebug('*** pre-processing trills')
    # for readability, we use a single-letter variable
    c = theConverter

    for eachTrill in c.documentRoot.iterfind(
            f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}trill'):
        startId: str = removeOctothorpe(eachTrill.get('startid', ''))  # type: ignore
        endId: str = removeOctothorpe(eachTrill.get('endid', ''))  # type: ignore
        tstamp2: str = eachTrill.get('tstamp2', '')
        hasExtension: bool = bool(endId) or bool(tstamp2)
        place: str = eachTrill.get('place', 'place_unspecified')

        if startId:
            # The trill info gets stashed on the note/chord referenced by startId
            accidUpper: str = eachTrill.get('accidupper', '')
            accidLower: str = eachTrill.get('accidlower', '')

            c.m21Attr[startId]['m21Trill'] = place
            if accidUpper:
                c.m21Attr[startId]['m21TrillAccidUpper'] = accidUpper
            if accidLower:
                c.m21Attr[startId]['m21TrillAccidLower'] = accidLower

            eachTrill.set('ignore_trill_in_trillFromElement', 'true')

        if not hasExtension:
            # save some figuring out in trillFromElement, we already know there is
            # no trill extension
            eachTrill.set('ignore_trill_extension_in_trillFromElement', 'true')
            continue

        # Making the extension is tricky.  If we have startId and endId, we can finish it here.
        # If we are missing either, we'll have to take notes and finish it in trillFromElement.
        trillExt = expressions.TrillExtension()
        if place and place != 'place_unspecified':
            trillExt.placement = place
        else:
            trillExt.placement = None  # type: ignore

        if t.TYPE_CHECKING:
            # work around Spanner.idLocal being incorrectly type-hinted as None
            assert isinstance(trillExt.idLocal, str)
        thisIdLocal = str(uuid4())
        trillExt.idLocal = thisIdLocal
        c.spannerBundle.append(trillExt)

        if startId:
            c.m21Attr[startId]['m21TrillExtensionStart'] = thisIdLocal
        if endId:
            c.m21Attr[endId]['m21TrillExtensionEnd'] = thisIdLocal

        if startId and endId:
            # we're finished (well, once we've processed both of those note/chord elements)
            eachTrill.set('ignore_trill_extension_in_trillFromElement', 'true')
        else:
            # we have to finish in trillFromElement, tell him about our TrillExtension
            eachTrill.set('m21TrillExtension', thisIdLocal)


def _ppMordents(theConverter: MeiToM21Converter):
    '''
    Pre-processing helper for :func:`convertFromString` that handles mordents in <mordent>
    elements. The input is a :class:`MeiToM21Converter` with data about the file currently being
    processed. This function reads from ``theConverter.documentRoot`` and writes into
    ``theConverter.m21Attr``.

    :param theConverter: The object responsible for storing data about this import.
    :type theConverter: :class:`MeiToM21Converter`.

    **This Preprocessor**

    The mordent preprocessor works similarly to the tie preprocessor, adding @m21Mordent
    attributes to any referenced notes/chords.

    **Example of ``m21Attr``**

    The ``theConverter.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
    dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
    dict holds attribute names and their values that should be added to the element with the
    given @xml:id.

    For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
    element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
    '''
    environLocal.printDebug('*** pre-processing mordents')
    # for readability, we use a single-letter variable
    c = theConverter

    for eachMordent in c.documentRoot.iterfind(
            f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}mordent'):
        startId: str = removeOctothorpe(eachMordent.get('startid', ''))  # type: ignore
        place: str = eachMordent.get('place', 'place_unspecified')
        form: str = eachMordent.get('form', '')
        long: str = eachMordent.get('long', '')

        if startId:
            if long == 'true':
                environLocal.warn(_UNIMPLEMENTED_IMPORT_WITH.format('<mordent>', '@long="true"'))
                environLocal.warn('@long will be ignored')

            # The mordent info gets stashed on the note/chord referenced by startId
            accidUpper: str = eachMordent.get('accidupper', '')
            accidLower: str = eachMordent.get('accidlower', '')

            c.m21Attr[startId]['m21Mordent'] = place
            if form:
                c.m21Attr[startId]['m21MordentForm'] = form
            if accidUpper:
                c.m21Attr[startId]['m21MordentAccidUpper'] = accidUpper
            if accidLower:
                c.m21Attr[startId]['m21MordentAccidLower'] = accidLower

            eachMordent.set('ignore_mordent_in_mordentFromElement', 'true')


def _ppTurns(theConverter: MeiToM21Converter):
    '''
    Pre-processing helper for :func:`convertFromString` that handles turns in <turn>
    elements. The input is a :class:`MeiToM21Converter` with data about the file currently being
    processed. This function reads from ``theConverter.documentRoot`` and writes into
    ``theConverter.m21Attr``.

    :param theConverter: The object responsible for storing data about this import.
    :type theConverter: :class:`MeiToM21Converter`.

    **This Preprocessor**

    The turn preprocessor works similarly to the tie preprocessor, adding @m21Turn
    attributes to any referenced notes/chords.

    **Example of ``m21Attr``**

    The ``theConverter.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
    dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
    dict holds attribute names and their values that should be added to the element with the
    given @xml:id.

    For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
    element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
    '''
    environLocal.printDebug('*** pre-processing turns')
    # for readability, we use a single-letter variable
    c = theConverter

    for eachTurn in c.documentRoot.iterfind(
            f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}turn'):
        startId: str = removeOctothorpe(eachTurn.get('startid', ''))  # type: ignore
        place: str = eachTurn.get('place', 'place_unspecified')
        form: str = eachTurn.get('form', '')
        theType: str = eachTurn.get('type', '')
        delayed: str = eachTurn.get('delayed', '')

        if startId:
            if delayed == 'true':
                environLocal.warn(_UNIMPLEMENTED_IMPORT_WITH.format('<turn>', '@delayed="true"'))
                environLocal.warn('@delayed will be ignored')

            # The turn info gets stashed on the note/chord referenced by startId
            accidUpper: str = eachTurn.get('accidupper', '')
            accidLower: str = eachTurn.get('accidlower', '')

            c.m21Attr[startId]['m21Turn'] = place
            if form:
                c.m21Attr[startId]['m21TurnForm'] = form
            if theType:
                c.m21Attr[startId]['m21TurnType'] = theType
            if accidUpper:
                c.m21Attr[startId]['m21TurnAccidUpper'] = accidUpper
            if accidLower:
                c.m21Attr[startId]['m21TurnAccidLower'] = accidLower

            eachTurn.set('ignore_turn_in_turnFromElement', 'true')


_M21_OTTAVA_TYPE_FROM_DIS_AND_DIS_PLACE: t.Dict[t.Tuple[str, str], str] = {
    ('8', 'above'): '8va',
    ('8', 'below'): '8vb',
    ('15', 'above'): '15ma',
    ('15', 'below'): '15mb',
    ('22', 'above'): '22da',
    ('22', 'below'): '22db',
}

def _ppOctaves(theConverter: MeiToM21Converter):
    '''
    Pre-processing helper for :func:`convertFromString` that handles ottavas specified in <octave>
    elements. The input is a :class:`MeiToM21Converter` with data about the file currently being
    processed. This function reads from ``theConverter.documentRoot`` and writes into
    ``theConverter.m21Attr``.

    :param theConverter: The object responsible for storing data about this import.
    :type theConverter: :class:`MeiToM21Converter`.

    **This Preprocessor**

    The octave preprocessor works similarly to the tie preprocessor, adding @m21OttavaStart and
    @m21OttavaEnd attributes to any referenced notes/chords.

    **Example of ``m21Attr``**

    The ``theConverter.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
    dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
    dict holds attribute names and their values that should be added to the element with the
    given @xml:id.

    For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
    element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
    '''
    environLocal.printDebug('*** pre-processing octaves')
    # for readability, we use a single-letter variable
    c = theConverter

    for eachOctave in c.documentRoot.iterfind(
            f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}octave'):
        startId: str = removeOctothorpe(eachOctave.get('startid', ''))  # type: ignore
        endId: str = removeOctothorpe(eachOctave.get('endid', ''))  # type: ignore
        amount: str = eachOctave.get('dis', '')
        direction: str = eachOctave.get('dis.place', '')
        if not amount or not direction:
            environLocal.warn('<octave> without @dis and/or @dis.place: ignoring')
            continue
        if (amount, direction) not in _M21_OTTAVA_TYPE_FROM_DIS_AND_DIS_PLACE:
            environLocal.warn(
                f'octave@dis ({amount}) or octave@dis.place ({direction}) invalid: ignoring'
            )
            continue

        ottavaType: str = _M21_OTTAVA_TYPE_FROM_DIS_AND_DIS_PLACE[(amount, direction)]
        ottava = spanner.Ottava(type=ottavaType)
        ottava.transposing = True  # we will use @oct (not @oct.ges) in octave-shifted notes/chords
        if t.TYPE_CHECKING:
            # work around Spanner.idLocal being incorrectly type-hinted as None
            assert isinstance(ottava.idLocal, str)
        thisIdLocal: str = str(uuid4())
        ottava.idLocal = thisIdLocal
        c.spannerBundle.append(ottava)
        if startId:
            c.m21Attr[startId]['m21OttavaStart'] = thisIdLocal
        if endId:
            c.m21Attr[endId]['m21OttavaEnd'] = thisIdLocal
        eachOctave.set('m21Ottava', thisIdLocal)
        staffNStr: str = eachOctave.get('staff', '')
        if staffNStr:
            ottava.mei_staff = staffNStr  # type: ignore


_ARPEGGIO_ARROW_AND_ORDER_TO_ARPEGGIOTYPE: t.Dict[t.Tuple[str, str], str] = {
    # default arrow is 'false'
    ('', ''): 'normal',
    ('', 'up'): 'normal',
    ('', 'down'): 'down',                 # down arrow is implied
    ('', 'nonarp'): 'non-arpeggio',       # arrow is ignored
    # same again, because default arrow is 'false'
    ('false', ''): 'normal',
    ('false', 'up'): 'normal',
    ('false', 'down'): 'down',            # down arrow is implied
    ('false', 'nonarp'): 'non-arpeggio',  # arrow is ignored
    # arrow is true, so order matters
    ('true', ''): 'up',                   # default arrow direction is up
    ('true', 'up'): 'up',
    ('true', 'down'): 'down',
    ('true', 'nonarp'): 'non-arpeggio',   # arrow is ignored
}


def _ppArpeggios(theConverter: MeiToM21Converter):
    '''
    Pre-processing helper for :func:`convertFromString` that handles arpeggios specified in <arpeg>
    elements. The input is a :class:`MeiToM21Converter` with data about the file currently being
    processed. This function reads from ``theConverter.documentRoot`` and writes into
    ``theConverter.m21Attr``.

    :param theConverter: The object responsible for storing data about this import.
    :type theConverter: :class:`MeiToM21Converter`.

    **This Preprocessor**

    The arpeggio preprocessor works similarly to the tie preprocessor, adding @arpeg
    attributes.

    **Example of ``m21Attr``**

    The ``theConverter.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
    dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
    dict holds attribute names and their values that should be added to the element with the
    given @xml:id.

    For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
    element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
    '''
    environLocal.printDebug('*** pre-processing arpeggios')
    # for readability, we use a single-letter variable
    c = theConverter

    for eachArpeg in c.documentRoot.iterfind(
            f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}arpeg'):
        plistStr: t.Optional[str] = eachArpeg.get('plist')
        plist: t.List[str] = []
        if plistStr:
            # if there's a plist, split it into a list
            plist = plistStr.split(' ')

        # If there's a startid, put it at the front of the list (but don't duplicate it
        # if it's already there).
        startId: t.Optional[str] = eachArpeg.get('startid')
        if startId:
            if startId in plist:
                plist.remove(startId)
            plist.insert(0, startId)

        # Now if we have a plist, it contains all the ids that should
        # be arpeggiated together.  But we only need an ArpeggioMarkSpanner if there
        # is more than one id in the plist.  An ArpeggioMark is fine for just one.
        # No plist and no startId?  Leave it for arpegFromElement.
        if plist:
            arrow: str = eachArpeg.get('arrow', '')
            order: str = eachArpeg.get('order', '')
            arpeggioType: str = _ARPEGGIO_ARROW_AND_ORDER_TO_ARPEGGIOTYPE.get(
                (arrow, order),
                'normal'
            )

            if len(plist) > 1:
                # make an ArpeggioMarkSpanner (put it in self.spannerBundle)
                arpeggio = expressions.ArpeggioMarkSpanner(arpeggioType=arpeggioType)
                if t.TYPE_CHECKING:
                    # work around Spanner.idLocal being incorrectly type-hinted as None
                    assert isinstance(arpeggio.idLocal, str)
                thisIdLocal = str(uuid4())
                arpeggio.idLocal = thisIdLocal
                c.spannerBundle.append(arpeggio)

                # iterate things in the @plist attribute,  and reference the
                # ArpeggioMarkSpanner from each of the notes/chords in the plist
                for eachXmlid in plist:
                    eachXmlid = removeOctothorpe(eachXmlid)  # type: ignore
                    c.m21Attr[eachXmlid]['m21ArpeggioMarkSpanner'] = thisIdLocal
            else:
                eachXmlid = removeOctothorpe(plist[0])  # type: ignore
                c.m21Attr[eachXmlid]['m21ArpeggioMarkType'] = arpeggioType

            # mark the element as handled, so we WON'T handle it later in arpegFromElement
            eachArpeg.set('ignore_in_arpegFromElement', 'true')


def _ppConclude(theConverter: MeiToM21Converter):
    '''
    Pre-processing helper for :func:`convertFromString` that adds attributes from ``m21Attr`` to the
    appropriate elements in ``documentRoot``. The input is a :class:`MeiToM21Converter` with data
    about the file currently being processed. This function reads from ``theConverter.m21Attr`` and
    writes into ``theConverter.documentRoot``.

    :param theConverter: The object responsible for storing data about this import.
    :type theConverter: :class:`MeiToM21Converter`.

    **Example of ``m21Attr``**

    The ``m21Attr`` argument must be a defaultdict that returns an empty (regular) dict for
    non-existent keys. The defaultdict stores the @xml:id attribute of an element; the dict holds
    attribute names and their values that should be added to the element with the given @xml:id.

    For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
    element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.

    **This Preprocessor**
    The conclude preprocessor adds all attributes from the ``m21Attr`` to the appropriate element in
    ``documentRoot``. In effect, it finds the element corresponding to each key in ``m21Attr``,
    then iterates the keys in its dict, *appending* the ``m21Attr``-specified value to any existing
    value.
    '''
    environLocal.printDebug('*** concluding pre-processing')
    # for readability, we use a single-letter variable
    c = theConverter

    # conclude pre-processing by adding music21-specific attributes to their respective elements
    for eachObject in c.documentRoot.iterfind('*//*'):
        objXmlId: t.Optional[str] = eachObject.get(_XMLID)
        # we have a defaultdict, so this "if" isn't strictly necessary; but without it, every single
        # element with an @xml:id creates a new, empty dict, which would consume a lot of memory
        if objXmlId and objXmlId in c.m21Attr:
            objAttrs: t.Dict = c.m21Attr[objXmlId]
            for eachAttr in objAttrs:
                oldAttrValue: str = eachObject.get(eachAttr, '')
                newAttrValue: str = objAttrs[eachAttr]
                eachObject.set(eachAttr, oldAttrValue + newAttrValue)


# Helper Functions
# -----------------------------------------------------------------------------
def _processEmbeddedElements(
    elements: t.Iterable[Element],
    mapping: t.Dict[str, t.Callable[
        [Element,
            t.Optional[meter.TimeSignature],
            spanner.SpannerBundle,
            t.Dict[str, str]],
        t.Any]
    ],
    callerTag: str,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List:
    # noinspection PyShadowingNames
    '''
    From an iterable of MEI ``elements``, use functions in the ``mapping`` to convert each element
    to its music21 object (or a tuple containing its music21 object plus some other stuff). This
    function was designed for use with elements that may contain other elements; the contained
    elements will be converted as appropriate.

    If an element itself has embedded elements (i.e., its converter function in ``mapping`` returns
    a sequence), those elements will appear in the returned sequence in order---there are no
    hierarchic lists.

    :param elements: A list of :class:`Element` objects to convert to music21 objects.
    :type elements: iterable of :class:`~xml.etree.ElementTree.Element`
    :param mapping: A dictionary where keys are the :attr:`Element.tag` attribute and values are
        the function to call to convert that :class:`Element` to a music21 object.
    :type mapping: mapping of str to function
    :param str callerTag: The tag of the element on behalf of which this function is processing
        sub-elements (e.g., 'note' or 'staffDef'). Do not include < and >. This is used in a
        warning message on finding an unprocessed element.
    :param spannerBundle: A slur bundle, as used by the other :func:`*fromElements` functions.
    :type spannerBundle: :class:`music21.spanner.SpannerBundle`
    :returns: A list of the music21 objects returned by the converter functions, or an empty list
        if no objects were returned.
    :rtype: sequence of :class:`~music21.base.Music21Object`

    **Examples:**

    Because there is no ``'rest'`` key in the ``mapping``, that :class:`Element` is ignored.

    >>> from xml.etree.ElementTree import Element
    >>> from music21 import note
    >>> from converter21.mei.base import _processEmbeddedElements
    >>> elements = [Element('note'), Element('rest'), Element('note')]
    >>> mapping = {'note': lambda w, x, y, z: note.Note('D2')}
    >>> _processEmbeddedElements(elements, mapping, 'doctest1', None, None, {})
    [<music21.note.Note D>, <music21.note.Note D>]

    If debugging is enabled for the previous example, this warning would be displayed:

    ``mei.base: Found an unprocessed <rest> element in a <doctest1>.

    The "beam" element holds "note" elements. All elements appear in a single level of the list:

    >>> elements = [Element('note'), Element('beam'), Element('note')]
    >>> mapping = {'note': lambda w, x, y, z: note.Note('D2'),
    ...            'beam': lambda w, x, y, z: [note.Note('E2') for _ in range(2)]}
    >>> _processEmbeddedElements(elements, mapping, 'doctest2', None, None, {})
    [<music21.note.Note D>, <music21.note.Note E>, <music21.note.Note E>, <music21.note.Note D>]
    '''
    processed: t.List = []

    for eachElem in elements:
        if eachElem.tag in mapping:
            result: t.Union[Music21Object, t.Tuple[Music21Object], t.List[Music21Object]] = (
                mapping[eachElem.tag](eachElem, activeMeter, spannerBundle, otherInfo)
            )
            if isinstance(result, list):
                for eachObject in result:
                    processed.append(eachObject)
            elif result is not None:
                processed.append(result)
        elif eachElem.tag not in _IGNORE_UNPROCESSED:
            environLocal.warn(_UNPROCESSED_SUBELEMENT.format(eachElem.tag, callerTag))

    return processed


def _timeSigFromAttrs(elem: Element, prefix: str = '') -> t.Optional[meter.TimeSignature]:
    '''
    From any tag with @meter.count and @meter.unit attributes, make a :class:`TimeSignature`.

    :param :class:`~xml.etree.ElementTree.Element` elem: An :class:`Element` with @meter.count and
        @meter.unit attributes.
    :returns: The corresponding time signature.
    :rtype: :class:`~music21.meter.TimeSignature`
    '''
    timeSig: meter.TimeSignature
    count: t.Optional[str] = elem.get(prefix + 'count')
    unit: t.Optional[str] = elem.get(prefix + 'unit')
    sym: t.Optional[str] = elem.get(prefix + 'sym')
    # We ignore form="invis" because this usually happens in the presence of
    # <mensur>, which we (and music21) do not support, so we really need this guy.
    # form: t.Optional[str] = elem.get(prefix + 'form')
    if sym:
        if (sym == 'cut'
                and (count is None or count == '2')
                and (unit is None or unit == '2')):
            timeSig = meter.TimeSignature('cut')
            # if form == 'invis':
            #     timeSig.style.hideObjectOnPrint = True
            return timeSig
        if (sym == 'common'
                and (count is None or count == '4')
                and (unit is None or unit == '4')):
            timeSig = meter.TimeSignature('common')
            # if form == 'invis':
            #     timeSig.style.hideObjectOnPrint = True
            return timeSig

    if count and unit:
        timeSig = meter.TimeSignature(f'{count}/{unit}')
        # if form == 'invis':
        #     timeSig.style.hideObjectOnPrint = True
        return timeSig

    return None


def _keySigFromAttrs(
    elem: Element,
    prefix: str = ''
) -> t.Optional[t.Union[key.Key, key.KeySignature]]:
    '''
    From any tag with (at minimum) either @pname or @sig attributes, make a
    :class:`KeySignature` or :class:`Key`, as possible.

    elem is an :class:`Element` with either the @pname or @sig attribute

    Note that the prefix 'key.' can be passed in to parse @key.pname, @key.sig, etc

    Returns the key or key signature.
    '''
    theKeySig: t.Optional[t.Union[key.KeySignature, key.Key]] = None
    theKey: t.Optional[key.Key] = None

    pname: t.Optional[str] = elem.get(prefix + 'pname')
    mode: t.Optional[str] = elem.get(prefix + 'mode')
    accid: t.Optional[str] = elem.get(prefix + 'accid')
    sig: t.Optional[str] = elem.get(prefix + 'sig')
    form: t.Optional[str] = elem.get(prefix + 'form')
    if pname is not None and mode is not None:
        accidental: t.Optional[str] = _accidentalFromAttr(accid)
        tonic: str
        if accidental is None:
            tonic = pname
        else:
            tonic = pname + accidental
        theKey = key.Key(tonic=tonic, mode=mode)

    if sig is not None:
        theKeySig = key.KeySignature(sharps=_sharpsFromAttr(sig))
        if mode:
            theKeySig = theKeySig.asKey(mode=mode)

    output: t.Optional[t.Union[key.KeySignature, key.Key]]
    if theKey is not None and theKeySig is not None:
        if theKey.sharps != theKeySig.sharps:
            # if they disagree, pick the one that was specified by number of sharps/flats
            output = theKeySig
        else:
            # if they agree, pick the one with more info
            output = theKey
    elif theKey is not None:
        output = theKey
    elif theKeySig is not None:
        output = theKeySig
    else:
        # malformed elem: return None
        output = None

    if output is not None and form == 'invis':
        output.style.hideObjectOnPrint = True
    return output

def _transpositionFromAttrs(elem: Element) -> interval.Interval:
    '''
    From any element with the @trans.diat and @trans.semi attributes, make an :class:`Interval` that
    represents the interval of transposition from written to concert pitch.

    :param :class:`~xml.etree.ElementTree.Element` elem: An :class:`Element` with the @trans.diat
        and @trans.semi attributes.
    :returns: The interval of transposition from written to concert pitch.
    :rtype: :class:`music21.interval.Interval`
    '''
    transDiat: int = int(float(elem.get('trans.diat', 0)))
    transSemi: int = int(float(elem.get('trans.semi', 0)))

    # If the difference between transSemi and transDiat is greater than five per octave...
    if abs(transSemi - transDiat) > 5 * (abs(transSemi) // 12 + 1):
        # ... we need to add octaves to transDiat so it's the proper size. Otherwise,
        #     intervalFromGenericAndChromatic() tries to create things like AAAAAAAAA5. Except it
        #     actually just fails.
        # NB: we test this against transSemi because transDiat could be 0 when transSemi is a
        #     multiple of 12 *either* greater or less than 0.
        if transSemi < 0:
            transDiat -= 7 * (abs(transSemi) // 12)
        elif transSemi > 0:
            transDiat += 7 * (abs(transSemi) // 12)

    # NB: MEI uses zero-based unison rather than 1-based unison, so for music21 we must make every
    #     diatonic interval one greater than it was. E.g., '@trans.diat="2"' in MEI means to
    #     "transpose up two diatonic steps," which music21 would rephrase as "transpose up by a
    #     diatonic third."
    if transDiat < 0:
        transDiat -= 1
    elif transDiat >= 0:
        transDiat += 1

    return interval.intervalFromGenericAndChromatic(interval.GenericInterval(transDiat),
                                                    interval.ChromaticInterval(transSemi))


def _barlineFromAttr(
    attr: t.Optional[str]
) -> t.Union[bar.Barline, bar.Repeat, t.Tuple[bar.Repeat, bar.Repeat]]:
    '''
    Use :func:`_attrTranslator` to convert the value of a "left" or "right" attribute to a
    :class:`Barline` or :class:`Repeat` or occasionally a tuple of :class:`Repeat`. The only time a
    tuple is returned is when "attr" is ``'rptboth'``, in which case the end and start barlines are
    both returned.

    :param str attr: The MEI @left or @right attribute to convert to a barline.
    :returns: The barline.
    :rtype: :class:`music21.bar.Barline` or :class:`~music21.bar.Repeat` or list of them
    '''
    # NB: the MEI Specification says @left is used only for legacy-format conversions, so we'll
    #     just assume it's a @right attribute. Not a huge deal if we get this wrong (I hope).
    if attr and attr.startswith('rpt'):
        if 'rptboth' == attr:
            endingRpt = _barlineFromAttr('rptend')
            startingRpt = _barlineFromAttr('rptstart')
            if t.TYPE_CHECKING:
                assert isinstance(endingRpt, bar.Repeat)
                assert isinstance(startingRpt, bar.Repeat)
            return endingRpt, startingRpt
        elif 'rptend' == attr:
            return bar.Repeat('end')
        else:
            return bar.Repeat('start')
    else:
        return bar.Barline(_attrTranslator(attr, 'right', _BAR_ATTR_DICT))


def _tieFromAttr(attr: str) -> tie.Tie:
    '''
    Convert a @tie attribute to the required :class:`Tie` object.

    :param str attr: The MEI @tie attribute to convert.
    :return: The relevant :class:`Tie` object.
    :rtype: :class:`music21.tie.Tie`
    '''
    if 'm' in attr or ('t' in attr and 'i' in attr):
        return tie.Tie('continue')
    elif 'i' in attr:
        return tie.Tie('start')
    else:
        return tie.Tie('stop')


def safeGetSpannerByIdLocal(
    theId: str,
    spannerBundle: spanner.SpannerBundle
) -> t.Optional[spanner.Spanner]:
    try:
        return spannerBundle.getByIdLocal(theId)[0]
    except IndexError:
        return None

def safeAddToSpannerByIdLocal(
    theObj: Music21Object,
    theId: str,
    spannerBundle: spanner.SpannerBundle
) -> bool:
    '''Avoid crashing when getByIdLocal() doesn't find the spanner'''
    try:
        spannerBundle.getByIdLocal(theId)[0].addSpannedElements(theObj)
        return True
    except IndexError:
        # when getByIdLocal() couldn't find the Slur
        return False


def addSlurs(
    elem: Element,
    obj: note.NotRest,
    spannerBundle: spanner.SpannerBundle
) -> bool:
    '''
    If relevant, add a slur to an ``obj`` (object) that was created from an ``elem`` (element).

    :param elem: The :class:`Element` that caused creation of the ``obj``.
    :type elem: :class:`xml.etree.ElementTree.Element`
    :param obj: The musical object (:class:`Note`, :class:`Chord`, etc.) created from ``elem``, to
        which a slur might be attached.
    :type obj: :class:`music21.base.Music21Object`
    :param spannerBundle: The :class:`Slur`-holding :class:`SpannerBundle` associated with the
        :class:`Stream` that holds ``obj``.
    :type spannerBundle: :class:`music21.spanner.SpannerBundle`
    :returns: Whether at least one slur was added.
    :rtype: bool

    **A Note about Importing Slurs**

    Because of how the MEI format specifies slurs, the strategy required for proper import to
    music21 is not obvious. There are two ways to specify a slur:

    #. With a ``@slur`` attribute, in which case :func:`addSlurs` reads the attribute and manages
       creating a :class:`Slur` object, adding the affected objects to it, and storing the
       :class:`Slur` in the ``spannerBundle``.
    #. With a ``<slur>`` element, which requires pre-processing. In this case, :class:`Slur` objects
       must already exist in the ``spannerBundle``, and special attributes must be added to the
       affected elements (``@m21SlurStart`` to the element at the start of the slur and
       ``@m21SlurEnd`` to the element at the end). These attributes hold the ``id`` of a
       :class:`Slur` in the ``spannerBundle``, allowing :func:`addSlurs` to find the slur and add
       ``obj`` to it.

    .. caution:: If an ``elem`` has an @m21SlurStart or @m21SlurEnd attribute that refer to an
        object not found in the ``spannerBundle``, the slur is silently dropped.
    '''
    addedSlur: bool = False

    def getSlurNumAndType(eachSlur: str) -> t.Tuple[str, str]:
        # eachSlur is of the form "[i|m|t][1-6]"
        slurNum: str = eachSlur[1:]
        slurType: str = eachSlur[:1]
        return slurNum, slurType

    startStr: t.Optional[str] = elem.get('m21SlurStart')
    endStr: t.Optional[str] = elem.get('m21SlurEnd')
    if startStr is not None:
        addedSlur = safeAddToSpannerByIdLocal(obj, startStr, spannerBundle)
    if endStr is not None:
        addedSlur = safeAddToSpannerByIdLocal(obj, endStr, spannerBundle)

    slurStr: t.Optional[str] = elem.get('slur')
    if slurStr is not None:
        theseSlurs = slurStr.split(' ')
        for eachSlur in theseSlurs:
            slurNum: str
            slurType: str
            slurNum, slurType = getSlurNumAndType(eachSlur)
            if 'i' == slurType:
                newSlur = spanner.Slur()
                if t.TYPE_CHECKING:
                    # work around Spanner.idLocal being incorrectly type-hinted as None
                    assert isinstance(newSlur.idLocal, str)
                newSlur.idLocal = slurNum
                spannerBundle.append(newSlur)
                newSlur.addSpannedElements(obj)
                addedSlur = True
            elif 't' == slurType:
                addedSlur = safeAddToSpannerByIdLocal(obj, slurNum, spannerBundle)
            # 'm' is currently ignored; we may need it for cross-staff slurs

    return addedSlur


def addOttavas(
    elem: Element,
    obj: note.NotRest,
    spannerBundle: spanner.SpannerBundle
) -> t.List[spanner.Spanner]:
    completedOttavas: t.List[spanner.Spanner] = []

    ottavaId: str = elem.get('m21OttavaStart', '')
    if ottavaId:
        safeAddToSpannerByIdLocal(obj, ottavaId, spannerBundle)

    ottavaId = elem.get('m21OttavaEnd', '')
    if ottavaId:
        ottava: t.Optional[spanner.Spanner] = safeGetSpannerByIdLocal(ottavaId, spannerBundle)
        if ottava is not None:
            ottava.addSpannedElements(obj)
            completedOttavas.append(ottava)

    return completedOttavas


def addArpeggio(
    elem: Element,
    obj: note.NotRest,
    spannerBundle: spanner.SpannerBundle
) -> t.List[spanner.Spanner]:
    completedArpeggioMarkSpanners: t.List[spanner.Spanner] = []

    # if appropriate, add this note/chord to an ArpeggioMarkSpanner
    arpId: str = elem.get('m21ArpeggioMarkSpanner', '')
    if arpId:
        arpSpanner: t.Optional[spanner.Spanner] = (
            safeGetSpannerByIdLocal(arpId, spannerBundle)
        )
        if arpSpanner is not None:
            arpSpanner.addSpannedElements(obj)
            completedArpeggioMarkSpanners.append(arpSpanner)

    # check to see if this note/chord is arpeggiated all by itself,
    # and if so, make the ArpeggioMark and append it to the note/chord's
    # expressions.
    arpeggioType: str = elem.get('m21ArpeggioMarkType', '')
    if arpeggioType:
        arpeggio = expressions.ArpeggioMark(arpeggioType=arpeggioType)
        obj.expressions.append(arpeggio)

    return completedArpeggioMarkSpanners


def addTrill(
    elem: Element,
    obj: note.NotRest,
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[spanner.Spanner]:
    completedTrillExtensions: t.List[spanner.Spanner] = []
    # if appropriate, add this note/chord to a trillExtension
    trillExtId: str = elem.get('m21TrillExtensionStart', '')
    if trillExtId:
        safeAddToSpannerByIdLocal(obj, trillExtId, spannerBundle)
    trillExtId = elem.get('m21TrillExtensionEnd', '')
    if trillExtId:
        trillExt: t.Optional[spanner.Spanner] = (
            safeGetSpannerByIdLocal(trillExtId, spannerBundle)
        )
        if trillExt is not None:
            trillExt.addSpannedElements(obj)
            completedTrillExtensions.append(trillExt)

    # check to see if this note/chord needs a trill by itself,
    # and if so, make the Trill and append it to the note/chord's
    # expressions.
    trill: expressions.Trill
    place: str = elem.get('m21Trill', '')
    if not place:
        return completedTrillExtensions

    accidUpper: str = elem.get('m21TrillAccidUpper', '')
    accidLower: str = elem.get('m21TrillAccidLower', '')

    # by default this goes up a note in the scale of the current key
    trill = expressions.Trill()
    if accidUpper:
        trill.mei_accidupper = accidUpper  # type: ignore
    elif accidLower:
        trill.mei_accidlower = accidLower  # type: ignore

    trill = t.cast(
        expressions.Trill,
        updateExpression(
            trill, obj, otherInfo['staffNumberForNotes'], otherInfo
        )
    )

    if place and place != 'place_unspecified':
        trill.placement = place
    else:
        trill.placement = None  # type: ignore

    obj.expressions.append(trill)

    return completedTrillExtensions


def addMordent(
    elem: Element,
    obj: note.NotRest,
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
):
    # Check to see if this note/chord needs a mordent, and if so,
    # make the Mordent and append it to the note/chord's expressions.
    mordent: expressions.GeneralMordent
    place: str = elem.get('m21Mordent', '')
    if not place:
        return

    accidUpper: str = elem.get('m21MordentAccidUpper', '')
    accidLower: str = elem.get('m21MordentAccidLower', '')
    form: str = elem.get('m21MordentForm', '')
    mei_accidupper: str = ''
    mei_accidlower: str = ''

    if accidUpper:
        if not form:
            form = 'upper'
        if form == 'upper':
            mei_accidupper = accidUpper  # type: ignore

    if accidLower:
        if not form:
            form = 'lower'
        if form == 'lower':
            mei_accidlower = accidLower  # type: ignore

    if not form:
        form = 'lower'  # I would prefer upper, but match Verovio

    if form == 'upper':
        # music21 calls an upper mordent (i.e that goes up from the main note) an InvertedMordent
        mordent = expressions.InvertedMordent()
    elif form == 'lower':
        mordent = expressions.Mordent()

    if mei_accidupper:
        mordent.mei_accidupper = mei_accidupper  # type: ignore
    elif mei_accidlower:
        mordent.mei_accidlower = mei_accidlower  # type: ignore

    mordent = t.cast(
        expressions.GeneralMordent,
        updateExpression(
            mordent, obj, otherInfo['staffNumberForNotes'], otherInfo
        )
    )

    # m21 mordents might not have placement... sigh...
    # But if I set it, it _will_ get exported to MusicXML (ha!).
    if place and place != 'place_unspecified':
        mordent.placement = place  # type: ignore
    else:
        mordent.placement = None  # type: ignore

    obj.expressions.append(mordent)


def addTurn(
    elem: Element,
    obj: note.NotRest,
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
):
    # Check to see if this note/chord needs a turn, and if so,
    # make the Turn and append it to the note/chord's expressions.
    turn: expressions.Turn  # this includes InvertedTurn as well
    place: str = elem.get('m21Turn', '')
    if not place:
        return

    accidUpper: str = elem.get('m21TurnAccidUpper', '')
    accidLower: str = elem.get('m21TurnAccidLower', '')
    form: str = elem.get('m21TurnForm', '')
    theType: str = elem.get('m21TurnType', '')
    mei_accidupper: str = ''
    mei_accidlower: str = ''

    if accidUpper:
        mei_accidupper = accidUpper  # type: ignore

    if accidLower:
        mei_accidlower = accidLower  # type: ignore

    if not form:
        if theType == 'slashed':
            form = 'lower'
        else:
            form = 'upper'  # default

    if form == 'upper':
        turn = expressions.Turn()
    elif form == 'lower':
        turn = expressions.InvertedTurn()

    if mei_accidupper:
        turn.mei_accidupper = mei_accidupper  # type: ignore
    elif mei_accidlower:
        turn.mei_accidlower = mei_accidlower  # type: ignore

    turn = t.cast(
        expressions.Turn,
        updateExpression(
            turn, obj, otherInfo['staffNumberForNotes'], otherInfo
        )
    )

    if place and place != 'place_unspecified':
        turn.placement = place
    else:
        turn.placement = None  # type: ignore

    obj.expressions.append(turn)


def updateExpression(
    expr: expressions.Expression,
    obj: note.GeneralNote,
    staffNStr: str,
    otherInfo: t.Dict[str, t.Any]
) -> expressions.Expression:
    if not isinstance(expr, (expressions.Trill, expressions.GeneralMordent, expressions.Turn)):
        return expr
    if not isinstance(obj, note.NotRest):
        return expr

    updatedExpr: expressions.Expression
    pitchUp: pitch.Pitch
    pitchDown: pitch.Pitch
    stepUp: str = ''
    stepDown: str = ''
    otherPitches: t.List[pitch.Pitch] = []
    mainPitch: pitch.Pitch = obj.pitches[-1]  # top-most pitch if it's a chord

    if hasattr(expr, 'mei_accidupper'):
        minorSecondUp: interval.DiatonicInterval = interval.DiatonicInterval('minor', 2)
        halfStepUpPitch: pitch.Pitch = minorSecondUp.transposePitch(mainPitch)
        accidUpper: str = expr.mei_accidupper  # type: ignore
        _, halfStepUpAccid, _ = (
            M21Utilities.splitM21PitchNameIntoNameAccidOctave(halfStepUpPitch.nameWithOctave)
        )
        if halfStepUpAccid == _ACCID_GES_ATTR_DICT.get(accidUpper, ''):
            stepUp = 'half'
            pitchUp = halfStepUpPitch
        else:
            stepUp = 'whole'
            pitchUp = interval.DiatonicInterval('major', 2).transposePitch(mainPitch)
        otherPitches.append(pitchUp)

    elif hasattr(expr, 'mei_accidlower'):
        minorSecondDown: interval.DiatonicInterval = (
            interval.DiatonicInterval('minor', 2).reverse()
        )
        halfStepDownPitch: pitch.Pitch = minorSecondDown.transposePitch(mainPitch)
        accidLower: str = expr.mei_accidlower  # type: ignore
        _, halfStepDownAccid, _ = (
            M21Utilities.splitM21PitchNameIntoNameAccidOctave(halfStepDownPitch.nameWithOctave)
        )
        if halfStepDownAccid == _ACCID_GES_ATTR_DICT.get(accidLower, ''):
            stepDown = 'half'
            pitchDown = halfStepDownPitch
        else:
            stepDown = 'whole'
            pitchDown = interval.DiatonicInterval('major', 2).reverse().transposePitch(mainPitch)
        otherPitches.append(pitchDown)

    else:
        # Has no upper/lower accid, just follows the current alter for next note up/down.
        # No need to updateStaffAltersWithPitches (since we're using the current alter).
        # But we still need to figure out HalfStep vs WholeStep.
        alterIdx: int
        alter: int
        if isinstance(expr, (expressions.Trill, expressions.InvertedMordent)):
            # going up
            pitchUp = interval.GenericInterval(2).transposePitch(mainPitch)
            alterIdx = M21Utilities.pitchToBase7(pitchUp)
            alter = otherInfo['currentImpliedAltersPerStaff'][staffNStr][alterIdx]
            if alter == 0:
                pitchUp.accidental = None
            else:
                pitchUp.accidental = pitch.Accidental()
                pitchUp.accidental.alter = alter

            if pitchUp.ps - mainPitch.ps == 1:
                stepUp = 'half'
            else:
                stepUp = 'whole'

            otherPitches.append(pitchUp)

        else:
            # going down
            pitchDown = interval.GenericInterval(2).reverse().transposePitch(mainPitch)
            alterIdx = M21Utilities.pitchToBase7(pitchDown)
            alter = otherInfo['currentImpliedAltersPerStaff'][staffNStr][alterIdx]
            if alter == 0:
                pitchDown.accidental = None
            else:
                pitchDown.accidental = pitch.Accidental()
                pitchDown.accidental.alter = alter
            if mainPitch.ps - pitchDown.ps == 1:
                stepDown = 'half'
            else:
                stepDown = 'whole'

            otherPitches.append(pitchDown)


    if isinstance(expr, expressions.Trill):
        if stepUp == 'half':
            updatedExpr = expressions.HalfStepTrill()
        else:
            updatedExpr = expressions.WholeStepTrill()
    elif isinstance(expr, expressions.InvertedMordent):
        if stepUp == 'half':
            updatedExpr = expressions.HalfStepInvertedMordent()
        else:
            updatedExpr = expressions.WholeStepInvertedMordent()
    elif isinstance(expr, expressions.Mordent):
        if stepDown == 'half':
            updatedExpr = expressions.HalfStepMordent()
        else:
            updatedExpr = expressions.WholeStepMordent()
    elif isinstance(expr, (expressions.Turn, expressions.InvertedTurn)):
        # note that music21 doesn't (yet) really allow a Turn to specify its
        # upper/lower interval.  You sort of can, but you can only specify one
        # interval that is used for both.  See comments in music21 issue #1507
        # about this.
        # For now, while we have done the accidental analysis (because it has
        # side-effects), we will not do anything here with that info.
        updatedExpr = expr

    # don't lose placement
    if hasattr(expr, 'placement'):
        updatedExpr.placement = expr.placement  # type: ignore

    # update alters (might be a no-op if we had no upper/loweraccid)
    updateStaffAltersWithPitches(staffNStr, otherPitches, otherInfo)

    return updatedExpr


def beamTogether(someThings: t.List[Music21Object]):
    '''
    Beam some things together. The function beams every object that has a :attr:`beams` attribute,
    leaving the other objects unmodified.

    :param someThings: An iterable of things to beam together.
    :type someThings: iterable of :class:`~music21.base.Music21Object`
    '''

    # First see if this is a beamed grace note group, or a beamed non-grace note group.
    # Each will skip over the other type of note.
    isGraceBeam: bool = False
    for thing in someThings:
        if not hasattr(thing, 'beams'):
            continue

        isGraceBeam = thing.duration.isGrace
        break

    # Index of the most recent beamedNote/Chord in someThings. Not all Note/Chord objects will
    # necessarily be beamed, so we have to make that distinction.
    iLastBeamedNote = -1

    for i, thing in enumerate(someThings):
        if not hasattr(thing, 'beams'):
            continue
        if thing.duration.isGrace != isGraceBeam:
            continue

        if iLastBeamedNote == -1:
            beamType = 'start'
        else:
            beamType = 'continue'

        # checking for len(thing.beams) avoids clobbering beams that were set with a nested
        # <beam> element, like a grace note
        if (duration.convertTypeToNumber(thing.duration.type) > 4
                and not thing.beams):  # type: ignore
            thing.beams.fill(thing.duration.type, beamType)  # type: ignore
            iLastBeamedNote = i

    if iLastBeamedNote != -1:
        someThings[iLastBeamedNote].beams.setAll('stop')  # type: ignore

    # loop over them again, looking for 'continue' that should be 'stop' (and 'start'
    # that should be 'partial'/'right') because there are fewer beams in the next note.
    for i, thing in enumerate(someThings):
        if not hasattr(thing, 'beams'):
            continue
        if thing.duration.isGrace != isGraceBeam:
            continue
        if duration.convertTypeToNumber(thing.duration.type) <= 4:
            continue

        nextThing: t.Optional[Music21Object] = None
        for j in range(i + 1, len(someThings)):
            if (hasattr(someThings[j], 'beams')
                    and someThings[j].duration.isGrace == isGraceBeam
                    and duration.convertTypeToNumber(someThings[j].duration.type) > 4):
                nextThing = someThings[j]
                break

        if nextThing is None:
            continue

        for beamNum in range(len(nextThing.beams) + 1, len(thing.beams) + 1):  # type: ignore
            b: beam.Beam = thing.beams.getByNumber(beamNum)  # type: ignore
            if b.type == 'continue':
                b.type = 'stop'
            elif b.type == 'start':
                b.type = 'partial'
                b.direction = 'right'

    # loop over them again, looking for 'stop' that should be 'partial'/'left' because
    # there are fewer beams in the previous note
    for i, thing in enumerate(someThings):
        if not hasattr(thing, 'beams'):
            continue
        if thing.duration.isGrace != isGraceBeam:
            continue
        if duration.convertTypeToNumber(thing.duration.type) <= 4:
            continue

        prevThing: t.Optional[Music21Object] = None
        for j in reversed(range(0, i)):  # i - 1 .. 0
            if (hasattr(someThings[j], 'beams')
                    and someThings[j].duration.isGrace == isGraceBeam
                    and duration.convertTypeToNumber(someThings[j].duration.type) > 4):
                prevThing = someThings[j]
                break

        if prevThing is None:
            continue

        for beamNum in range(len(prevThing.beams) + 1, len(thing.beams) + 1):  # type: ignore
            b: beam.Beam = thing.beams.getByNumber(beamNum)  # type: ignore
            if b.type == 'stop':
                b.type = 'partial'
                b.direction = 'left'


def applyBreaksecs(someThings: t.List[Music21Object]):
    # First see if this is a beamed grace note group, or a beamed non-grace note group.
    # Each will skip over the other type of note.
    isGraceBeam: bool = False
    for thing in someThings:
        if not hasattr(thing, 'beams'):
            continue

        isGraceBeam = thing.duration.isGrace
        break

    for i, thing in enumerate(someThings):
        if not hasattr(thing, 'beams'):
            continue
        if thing.duration.isGrace != isGraceBeam:
            continue
        if duration.convertTypeToNumber(thing.duration.type) <= 4:
            continue

        breaksecNum: t.Optional[int] = None
        if not hasattr(thing, 'mei_breaksec'):
            continue

        try:
            breaksecNum = int(thing.mei_breaksec)  # type: ignore
        except:  # pylint: disable=bare-except
            pass
        if breaksecNum is None:
            continue

        # delete the custom mei_breaksec attribute so that nested <beam> elements
        # won't process it twice.
        del thing.mei_breaksec  # type: ignore

        # stop the extra (not included in breaksecNum) beams in this thing
        for beamNum in range(breaksecNum + 1, len(thing.beams) + 1):  # type: ignore
            b: beam.Beam = thing.beams.getByNumber(beamNum)  # type: ignore
            if b.type == 'continue':
                b.type = 'stop'

        nextThing: t.Optional[Music21Object] = None
        for j in range(i + 1, len(someThings)):
            if (hasattr(someThings[j], 'beams')
                    and someThings[j].duration.isGrace == isGraceBeam
                    and duration.convertTypeToNumber(someThings[j].duration.type) > 4):
                nextThing = someThings[j]
                break

        if nextThing is None:
            continue

        # start the extra (not included in breaksecNum) beams in the next thing
        for beamNum in range(breaksecNum + 1, len(nextThing.beams) + 1):  # type: ignore
            b: beam.Beam = nextThing.beams.getByNumber(beamNum)  # type: ignore
            if b.type == 'continue':
                b.type = 'start'


def removeOctothorpe(xmlid: t.Optional[str]) -> t.Optional[str]:
    '''
    Given a string with an @xml:id to search for, remove a leading octothorpe, if present.

    >>> from converter21.mei.base import removeOctothorpe
    >>> removeOctothorpe('110a923d-a13a-4a2e-b85c-e1d438e4c5d6')
    '110a923d-a13a-4a2e-b85c-e1d438e4c5d6'
    >>> removeOctothorpe('#e46cbe82-95fc-4522-9f7a-700e41a40c8e')
    'e46cbe82-95fc-4522-9f7a-700e41a40c8e'
    '''
    if xmlid and xmlid.startswith('#'):
        return xmlid[1:]
    return xmlid


def makeMetadata(documentRoot: Element) -> metadata.Metadata:
    '''
    Produce metadata objects for all the metadata stored in the MEI header.

    :param documentRoot: The MEI document's root element.
    :type documentRoot: :class:`~xml.etree.ElementTree.Element`
    :returns: A :class:`Metadata` object with some of the metadata stored in the MEI document.
    :rtype: :class:`music21.metadata.Metadata`
    '''
    meta = metadata.Metadata()
    work = documentRoot.find(f'.//{MEI_NS}work')
    if work is not None:
        # title, subtitle, and movement name
        meta = metaSetTitle(work, meta)
        # composer
        meta = metaSetComposer(work, meta)
        # date
        meta = metaSetDate(work, meta)

    return meta


def metaSetTitle(work: Element, meta: metadata.Metadata) -> metadata.Metadata:
    '''
    From a <work> element, find the title, subtitle, and movement name (<tempo> element) and store
    the values in a :class:`Metadata` object.

    :param work: A <work> :class:`~xml.etree.ElementTree.Element` with metadata you want to find.
    :param meta: The :class:`~music21.metadata.Metadata` object in which to store the metadata.
    :return: The ``meta`` argument, having relevant metadata added.
    '''
    # title, subtitle, and movement name
    subtitle = None
    for title in work.findall(f'./{MEI_NS}titleStmt/{MEI_NS}title'):
        if title.get('type', '') == 'subtitle':  # or 'subordinate', right?
            subtitle = title.text
        elif meta.title is None:
            meta.title = title.text

    if subtitle:
        # Since m21.Metadata doesn't actually have a "subtitle" attribute, we'll put the subtitle
        # in the title
        meta.title = f'{meta.title} ({subtitle})'

    tempoEl = work.find(f'./{MEI_NS}tempo')
    if tempoEl is not None:
        meta.movementName = tempoEl.text

    return meta


def metaSetComposer(work: Element, meta: metadata.Metadata) -> metadata.Metadata:
    '''
    From a <work> element, find the composer(s) and store the values in a :class:`Metadata` object.

    :param work: A <work> :class:`~xml.etree.ElementTree.Element` with metadata you want to find.
    :param meta: The :class:`~music21.metadata.Metadata` object in which to store the metadata.
    :return: The ``meta`` argument, having relevant metadata added.
    '''
    composers = []
    persName: t.Optional[Element]
    for persName in work.findall(f'./{MEI_NS}titleStmt/{MEI_NS}respStmt/{MEI_NS}persName'):
        if persName is not None and persName.get('role') == 'composer' and persName.text:
            composers.append(persName.text)
    for composer in work.findall(f'./{MEI_NS}titleStmt/{MEI_NS}composer'):
        if composer.text:
            composers.append(composer.text)
        else:
            persName = composer.find(f'./{MEI_NS}persName')
            if persName is not None and persName.text:
                composers.append(persName.text)
    if len(composers) == 1:
        meta.composer = composers[0]
    elif len(composers) > 1:
        meta.composers = composers

    return meta


def metaSetDate(work: Element, meta: metadata.Metadata) -> metadata.Metadata:
    '''
    From a <work> element, find the date (range) of composition and store the values in a
    :class:`Metadata` object.

    :param work: A <work> :class:`~xml.etree.ElementTree.Element` with metadata you want to find.
    :param meta: The :class:`~music21.metadata.Metadata` object in which to store the metadata.
    :return: The ``meta`` argument, having relevant metadata added.
    '''
    date = work.find(f'./{MEI_NS}history/{MEI_NS}creation/{MEI_NS}date')
    if date is not None:  # must use explicit "is not None" for an Element
        isodate: t.Optional[str] = date.get('isodate')
        if date.text or isodate:
            dateStr: str
            if isodate:
                dateStr = isodate
            else:
                if t.TYPE_CHECKING:
                    # because not isodate, and (date.text or isodate) is True
                    assert date.text is not None
                dateStr = date.text

            theDate = metadata.Date()
            try:
                theDate.loadStr(dateStr.replace('-', '/'))
            except ValueError:
                environLocal.warn(_MISSED_DATE.format(dateStr))
            else:
                meta.dateCreated = theDate
        else:
            dateStart = date.get('notbefore') if date.get('notbefore') else date.get('startdate')
            dateEnd = date.get('notafter') if date.get('notafter') else date.get('enddate')
            if dateStart and dateEnd:
                meta.dateCreated = metadata.DateBetween((dateStart, dateEnd))

    return meta


# def getVoiceId(fromThese):
#     '''
#     From a list of objects with mixed type, find the "id" of the :class:`music21.stream.Voice`
#     instance.
#
#     :param list fromThese: A list of objects of any type, at least one of which must be a
#         :class:`~music21.stream.Voice` instance.
#     :returns: The ``id`` of the :class:`Voice` instance.
#     :raises: :exc:`RuntimeError` if zero or many :class:`Voice` objects are found.
#     '''
#     fromThese = [item for item in fromThese if isinstance(item, stream.Voice)]
#     if len(fromThese) == 1:
#         return fromThese[0].id
#     else:
#         raise RuntimeError('getVoiceId: found too few or too many Voice objects')

# noinspection PyTypeChecker
def scaleToTuplet(
    objs: t.Union[Music21Object, t.List[Music21Object]],
    elem: Element
) -> t.Union[Music21Object, t.List[Music21Object]]:
    '''
    Scale the duration of some objects by a ratio indicated by a tuplet. The ``elem`` must have the
    @m21TupletNum and @m21TupletNumbase attributes set, and optionally the @m21TupletSearch or
    @m21TupletType attributes.

    The @m21TupletNum and @m21TupletNumbase attributes should be equal to the @num and @numbase
    values of the <tuplet> or <tupletSpan> that indicates this tuplet.

    The @m21TupletSearch attribute, whose value must either be ``'start'`` or ``'end'``, is required
    when a <tupletSpan> does not include a @plist attribute. It indicates that the importer must
    "search" for a tuplet near the end of the import process, which involves scaling the durations
    of all objects discovered between those with the "start" and "end" search values.

    The @m21TupletType attribute is set directly as the :attr:`type` attribute of the music21
    object's :class:`Tuplet` object. If @m21TupletType is not set, the @tuplet attribute will be
    consulted. Note that this attribute is ignored if the @m21TupletSearch attribute is present,
    since the ``type`` will be set later by the tuplet-finding algorithm.

    .. note:: Objects without a :attr:`duration` attribute will be skipped silently, unless they
        will be given the @m21TupletSearch attribute.

    :param objs: The object(s) whose durations will be scaled.
        You may provide either a single object
        or an iterable; the return type corresponds to the input type.
    :type objs: (list of) :class:`~music21.base.Music21Object`
    :param elem: An :class:`Element` with the appropriate attributes (as specified above).
    :type elem: :class:`xml.etree.ElementTree.Element`
    :returns: ``objs`` with scaled durations.
    :rtype: (list of) :class:`~music21.base.Music21Object`
    '''
    wasList: bool = True
    if not isinstance(objs, list):
        objs = [objs]
        wasList = False

    for obj in objs:
        if not isinstance(obj, (note.Note, note.Rest, chord.Chord)):
            # silently skip objects that don't have a duration
            continue
#         if isinstance(obj, note.Note) and isinstance(obj.duration, duration.GraceDuration):
#             # silently skip grace notes (they don't have a duration either)
#             continue
# THIS CAUSED TEST FAILURE

        elif elem.get('m21TupletSearch') is not None:
            obj.m21TupletSearch = elem.get('m21TupletSearch')  # type: ignore
            obj.m21TupletNum = elem.get('m21TupletNum')  # type: ignore
            obj.m21TupletNumbase = elem.get('m21TupletNumbase')  # type: ignore

        else:
            num: t.Optional[str] = elem.get('m21TupletNum')
            numbase: t.Optional[str] = elem.get('m21TupletNumbase')
            if num and numbase:
                obj.duration.appendTuplet(duration.Tuplet(
                    numberNotesActual=int(num),
                    numberNotesNormal=int(numbase),
                    durationNormal=obj.duration.type,
                    durationActual=obj.duration.type))

                tupletType: t.Optional[str] = elem.get('m21TupletType')
                if tupletType is not None:
                    obj.duration.tuplets[0].type = tupletType  # type: ignore
                elif elem.get('tuplet', '').startswith('i'):
                    obj.duration.tuplets[0].type = 'start'
                elif elem.get('tuplet', '').startswith('t'):
                    obj.duration.tuplets[0].type = 'stop'

    if wasList:
        return objs
    else:
        return objs[0]


def _guessTuplets(theLayer: t.List[Music21Object]) -> t.List[Music21Object]:
    # TODO: nested tuplets don't work when they're both specified with <tupletSpan>
    # TODO: adjust this to work with cross-measure tuplets (i.e., where only the "start" or "end"
    #       is found in theLayer)
    '''
    Given a list of music21 objects, possibly containing :attr:`m21TupletSearch`,
    :attr:`m21TupletNum`, and :attr:`m21TupletNumbase` attributes, adjust the durations of the
    objects as specified by those "m21Tuplet" attributes, then remove the attributes.

    This function finishes processing for tuplets encoded as a <tupletSpan> where @startid and
    @endid are indicated, but not @plist. Knowing the starting and ending object in the tuplet, we
    can guess that all the Note, Rest, and Chord objects between the starting and ending objects
    in that <layer> are part of the tuplet. (Grace notes retain a 0.0 duration).

    .. note:: At the moment, this will likely only work for simple tuplets---not nested tuplets.

    :param theLayer: Objects from the <layer> in which to search for objects that have the
        :attr:`m21TupletSearch` attribute.
    :type theScore: list
    :returns: The same list, with durations adjusted to account for tuplets.
    '''
    # NB: this is a hidden function because it uses the "m21TupletSearch" attribute, which are only
    #     supposed to be used within the MEI import module

    inATuplet = False  # we hit m21TupletSearch=='start' but not 'end' yet
    tupletNum = None
    tupletNumbase = None

    for eachNote in theLayer:
        # we'll skip objects that don't have a duration
        if not isinstance(eachNote, (note.Note, note.Rest, chord.Chord)):
            continue

        if (hasattr(eachNote, 'm21TupletSearch')
                and eachNote.m21TupletSearch == 'start'):  # type: ignore
            inATuplet = True
            tupletNum = int(eachNote.m21TupletNum)  # type: ignore
            tupletNumbase = int(eachNote.m21TupletNumbase)  # type: ignore

            del eachNote.m21TupletSearch  # type: ignore
            del eachNote.m21TupletNum  # type: ignore
            del eachNote.m21TupletNumbase  # type: ignore

        if inATuplet:
            scaleToTuplet(eachNote, Element('',
                                            m21TupletNum=str(tupletNum),
                                            m21TupletNumbase=str(tupletNumbase)))

            if (hasattr(eachNote, 'm21TupletSearch')
                    and eachNote.m21TupletSearch == 'end'):  # type: ignore
                # we've reached the end of the tuplet!
                eachNote.duration.tuplets[0].type = 'stop'

                del eachNote.m21TupletSearch  # type: ignore
                del eachNote.m21TupletNum  # type: ignore
                del eachNote.m21TupletNumbase  # type: ignore

                # reset the tuplet-tracking variables
                inATuplet = False

    return theLayer


# Element-Based Converter Functions
# -----------------------------------------------------------------------------
def scoreDefFromElement(
    elem: Element,
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.Dict[str, t.Union[t.List[Music21Object], t.Dict[str, Music21Object]]]:
    '''
    <scoreDef> Container for score meta-information.

    In MEI 2013: pg.431 (445 in PDF) (MEI.shared module)

    This function returns a dictionary with objects that may relate to the entire score, to all
    parts at a particular moment, or only to a specific part at a particular moment. The dictionary
    keys determine the object's scope. If the key is...

    * ``'whole-score objects'``, it applies to the entire score (e.g., page size);
    * ``'all-part objects'``, it applies to all parts at the moment this <scoreDef> appears;
    * the @n attribute of a part, it applies only to
      that part at the moment this <scoreDef> appears.

    While the multi-part objects will be held in a list, the single-part objects will be in a dict
    like that returned by :func:`staffDefFromElement`.

    Note that it is the caller's responsibility to determine the right action if there are
    conflicting objects in the returned dictionary.

    For example:

    >>> meiDoc = """<?xml version="1.0" encoding="UTF-8"?>
    ... <scoreDef meter.count="3" meter.unit="4" xmlns="http://www.music-encoding.org/ns/mei">
    ...     <staffGrp>
    ...         <staffDef n="1" label="Clarinet"/>
    ...         <staffGrp>
    ...             <staffDef n="2" label="Flute"/>
    ...             <staffDef n="3" label="Violin"/>
    ...         </staffGrp>
    ...     </staffGrp>
    ... </scoreDef>
    ... """
    >>> from converter21.mei.base import scoreDefFromElement
    >>> from xml.etree import ElementTree as ET
    >>> scoreDef = ET.fromstring(meiDoc)
    >>> result = scoreDefFromElement(scoreDef, None, {})
    >>> len(result)
    5
    >>> result['1']
    {'instrument': <music21.instrument.Clarinet '1: Clarinet: Clarinet'>}
    >>> result['3']
    {'instrument': <music21.instrument.Violin '3: Violin: Violin'>}
    >>> result['all-part objects']
    [<music21.meter.TimeSignature 3/4>]
    >>> result['whole-score objects']
    []

    :param elem: The ``<scoreDef>`` element to process.
    :type elem: :class:`~xml.etree.ElementTree.Element`
    :returns: Objects from the ``<scoreDef>``, as described above.
    :rtype: dict

    **Attributes/Elements Implemented:**

    - (att.meterSigDefault.log (@meter.count, @meter.unit))
    - (att.keySigDefault.log (@key.accid, @key.mode, @key.pname, @key.sig))
    - contained <staffGrp>

    **Attributes/Elements in Testing:** None

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base) (att.id (@xml:id))
    - att.scoreDef.log

        - (att.cleffing.log (@clef.shape, @clef.line, @clef.dis, @clef.dis.place))
        - (att.duration.default (@dur.default, @num.default, @numbase.default))
        - (att.keySigDefault.log (@key.sig.mixed))
        - (att.octavedefault (@octave.default))
        - (att.transposition (@trans.diat, @trans.semi))
        - (att.scoreDef.log.cmn (att.beaming.log (@beam.group, @beam.rests)))
        - (att.scoreDef.log.mensural

            - (att.mensural.log (@mensur.dot, @mensur.sign,
                 @mensur.slash, @proport.num, @proport.numbase)
            - (att.mensural.shared (@modusmaior, @modusminor, @prolatio, @tempus))))

    - att.scoreDef.vis (all)
    - att.scoreDef.ges (all)
    - att.scoreDef.anl (none exist)

    **Contained Elements not Implemented:**

    - MEI.cmn: meterSigGrp
    - MEI.harmony: chordTable
    - MEI.linkalign: timeline
    - MEI.midi: instrGrp
    - MEI.shared: pgFoot pgFoot2 pgHead pgHead2
    - MEI.usersymbols: symbolTable
    '''

    # make the dict
    topPart: str = 'top-part objects'
    allParts: str = 'all-part objects'
    wholeScore: str = 'whole-score objects'
    post: t.Dict[str, t.Union[t.List[Music21Object], t.Dict[str, Music21Object]]] = {
        topPart: [],
        allParts: [],
        wholeScore: []
    }

    # 0.) process top-part attributes (none actually get posted yet, but...)
    bpmStr: str = elem.get('midi.bpm', '')
    if bpmStr:
        # stick it in other info, for the very first MetronomeMark to use (if necessary)
        otherInfo['pending scoredef@midi.bpm'] = bpmStr

    # 1.) process all-part attributes
    pap = post[allParts]
    if t.TYPE_CHECKING:
        assert isinstance(pap, list)
    postAllParts: t.List[Music21Object] = pap

    # --> time signature
    if elem.get('meter.count') is not None or elem.get('meter.sym') is not None:
        timesig = _timeSigFromAttrs(elem, prefix='meter.')
        if timesig is not None:
            postAllParts.append(timesig)
    meterSigElem: t.Optional[Element] = elem.find(f'{MEI_NS}meterSig')
    if meterSigElem is not None:
        timesig = _timeSigFromAttrs(meterSigElem)
        if timesig is not None:
            postAllParts.append(timesig)

    # --> key signature
    if elem.get('key.pname') is not None or elem.get('key.sig') is not None:
        keysig = _keySigFromAttrs(elem, prefix='key.')
        if keysig is not None:
            postAllParts.append(keysig)
    keySigElem: t.Optional[Element] = elem.find(f'{MEI_NS}keySig')
    if keySigElem is not None:
        keysig = _keySigFromAttrs(keySigElem)
        if keysig is not None:
            postAllParts.append(keysig)

    # 2.) staff-specific things (from contained <staffGrp> >> <staffDef>)
    for eachGrp in elem.iterfind(f'{MEI_NS}staffGrp'):
        post.update(staffGrpFromElement(eachGrp, spannerBundle, otherInfo))

    return post


def staffGrpFromElement(
    elem: Element,
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any],
    staffDefDict: t.Optional[
        t.Dict[str, t.Union[t.List[Music21Object], t.Dict[str, Music21Object]]]
    ] = None,
) -> t.Dict[str, t.Union[t.List[Music21Object], t.Dict[str, Music21Object]]]:
    '''
    <staffGrp> A group of bracketed or braced staves.

    In MEI 2013: pg.448 (462 in PDF) (MEI.shared module)

    For now, this function is merely a container-processor  for <staffDef> elements contained
    in this <staffGrp> element given as the "elem" argument. That is, the function does not yet
    create the brackets/braces and labels expected of a staff group.
    Note however that all <staffDef>
    elements will be processed, even if they're contained within several layers of <staffGrp>.

    :param elem: The ``<staffGrp>`` element to process.
    :type elem: :class:`~xml.etree.ElementTree.Element`
    :returns: Dictionary where keys are the @n attribute on a contained <staffDef>, and values are
        the result of calling :func:`staffDefFromElement` with that <staffDef>.

    **Attributes/Elements Implemented:**

    - contained <staffDef>
    - contained <staffGrp>

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base) (att.id (@xml:id))
    - att.declaring (@decls)
    - att.facsimile (@facs)
    - att.staffGrp.vis (@barthru)

        - (att.labels.addl (@label.abbr))
        - (att.staffgroupingsym (@symbol))
        - (att.visibility (@visible))

    - att.staffGrp.ges (att.instrumentident (@instr))

    **Contained Elements not Implemented:**

    - MEI.midi: instrDef
    - MEI.shared: grpSym label
    '''

    staffDefTag = f'{MEI_NS}staffDef'
    staffGroupTag = f'{MEI_NS}staffGrp'

    staffDefDict = staffDefDict if staffDefDict is not None else {}

    for el in elem.findall('*'):
        # return all staff defs in this staff group
        nStr: t.Optional[str] = el.get('n')
        if nStr and (el.tag == staffDefTag):
            otherInfo['staffNumberForDef'] = nStr
            staffDefDict[nStr] = staffDefFromElement(el, spannerBundle, otherInfo)
            otherInfo.pop('staffNumberForDef')

        # recurse if there are more groups, append to the working staffDefDict
        elif el.tag == staffGroupTag:
            staffGrpFromElement(el, spannerBundle, otherInfo, staffDefDict)

    return staffDefDict


def staffDefFromElement(
    elem: Element,
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.Dict[str, Music21Object]:
    '''
    <staffDef> Container for staff meta-information.

    In MEI 2013: pg.445 (459 in PDF) (MEI.shared module)

    :returns: A dict with various types of metadata information, depending on what is specified in
        this <staffDef> element. Read below for more information.
    :rtype: dict

    **Possible Return Values**

    The contents of the returned dictionary depend on the contents of the <staffDef> element. The
    dictionary keys correspond to types of information. Possible keys include:

    - ``'instrument'``: for a :class:`music21.instrument.Instrument` subclass
    - ``'clef'``: for a :class:`music21.clef.Clef` subclass
    - ``'key'``: for a :class:`music21.key.Key` or :class:`~music21.key.KeySignature` subclass
    - ``'meter'``: for a :class:`music21.meter.TimeSignature`

    **Examples**

    This <staffDef> only returns a single item.

    >>> meiDoc = """<?xml version="1.0" encoding="UTF-8"?>
    ... <staffDef n="1" label="Clarinet" xmlns="http://www.music-encoding.org/ns/mei"/>
    ... """
    >>> from converter21.mei.base import staffDefFromElement
    >>> from xml.etree import ElementTree as ET
    >>> staffDef = ET.fromstring(meiDoc)
    >>> result = staffDefFromElement(staffDef, None, {})
    >>> len(result)
    1
    >>> result
    {'instrument': <music21.instrument.Clarinet '1: Clarinet: Clarinet'>}
    >>> result['instrument'].partId
    '1'
    >>> result['instrument'].partName
    'Clarinet'

    This <staffDef> returns many objects.

    >>> meiDoc = """<?xml version="1.0" encoding="UTF-8"?>
    ... <staffDef n="2" label="Tuba" key.pname="B" key.accid="f" key.mode="major"
    ...  xmlns="http://www.music-encoding.org/ns/mei">
    ...     <clef shape="F" line="4"/>
    ... </staffDef>
    ... """
    >>> from converter21.mei.base import staffDefFromElement
    >>> from xml.etree import ElementTree as ET
    >>> staffDef = ET.fromstring(meiDoc)
    >>> result = staffDefFromElement(staffDef, None, {})
    >>> len(result)
    3
    >>> result['instrument']
    <music21.instrument.Tuba '2: Tuba: Tuba'>
    >>> result['clef']
    <music21.clef.BassClef>
    >>> result['key']
    <music21.key.Key of B- major>

    **Attributes/Elements Implemented:**

    - @label (att.common) as Instrument.partName
    - @label.abbr (att.labels.addl) as Instrument.partAbbreviation
    - @n (att.common) as Instrument.partId
    - (att.keySigDefault.log (@key.accid, @key.mode, @key.pname, @key.sig))
    - (att.meterSigDefault.log (@meter.count, @meter.unit))
    - (att.cleffing.log (@clef.shape, @clef.line, @clef.dis, @clef.dis.place))
      (via :func:`clefFromElement`)
    - @trans.diat and @trans.demi (att.transposition)
    - <instrDef> held within
    - <clef> held within

    **Attributes/Elements Ignored:**

    - @key.sig.mixed (from att.keySigDefault.log)

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@n, @xml:base) (att.id (@xml:id))
    - att.declaring (@decls)
    - att.staffDef.log

        - (att.duration.default (@dur.default, @num.default, @numbase.default))
        - (att.octavedefault (@octave.default))
        - (att.staffDef.log.cmn (att.beaming.log (@beam.group, @beam.rests)))
        - (att.staffDef.log.mensural

            - (att.mensural.log (@mensur.dot, @mensur.sign, @mensur.slash,
                                 @proport.num, @proport.numbase)
            - (att.mensural.shared (@modusmaior, @modusminor, @prolatio, @tempus))))

    - att.staffDef.vis (all)
    - att.staffDef.ges (all)
    - att.staffDef.anl (none exist)

    **Contained Elements not Implemented:**

    - MEI.cmn: meterSigGrp
    - MEI.mensural: mensural support
    - MEI.shared: clefGrp label layerDef
    '''
    # mapping from tag name to our converter function
    tagToFunction: t.Dict[str, t.Callable[
        [Element,
            t.Optional[meter.TimeSignature],
            spanner.SpannerBundle,
            t.Dict[str, str]],
        t.Any]
    ] = {
        f'{MEI_NS}clef': clefFromElement,
        f'{MEI_NS}keySig': keySigFromElementInStaffDef,
        f'{MEI_NS}meterSig': timeSigFromElement,
    }

    # first make the Instrument
    instrDefElem = elem.find(f'{MEI_NS}instrDef')
    post: t.Dict[str, Music21Object]
    if instrDefElem is not None:
        post = {'instrument': instrDefFromElement(instrDefElem, None, spannerBundle, otherInfo)}
    else:
        try:
            post = {'instrument': instrument.fromString(elem.get('label', ''))}
        except instrument.InstrumentException:
            post = {}

    if 'instrument' in post:
        inst = post['instrument']
        if t.TYPE_CHECKING:
            assert isinstance(inst, instrument.Instrument)
        inst.partName = elem.get('label')
        inst.partAbbreviation = elem.get('label.abbr')
        inst.partId = elem.get('n')

    # --> transposition
    if elem.get('trans.semi') is not None:
        if 'instrument' not in post:
            post['instrument'] = instrument.Instrument()
        inst = post['instrument']
        if t.TYPE_CHECKING:
            assert isinstance(inst, instrument.Instrument)
        inst.transposition = _transpositionFromAttrs(elem)

    # process other part-specific information
    # --> time signature
    if elem.get('meter.count') is not None or elem.get('meter.sym') is not None:
        timesig = _timeSigFromAttrs(elem, prefix='meter.')
        if timesig is not None:
            post['meter'] = timesig

    # --> key signature
    updateStaffKeyAndAlters: bool = False
    if elem.get('key.pname') is not None or elem.get('key.sig') is not None:
        keysig = _keySigFromAttrs(elem, prefix='key.')
        if keysig is not None:
            post['key'] = keysig
            updateStaffKeyAndAlters = True

    # --> clef
    if elem.get('clef.shape') is not None:
        shape: t.Optional[str] = elem.get('clef.shape')
        line: t.Optional[str] = elem.get('clef.line')
        dis: t.Optional[str] = elem.get('clef.dis')
        displace: t.Optional[str] = elem.get('clef.dis.place')
        attribDict: t.Dict[str, str] = {}
        if shape:
            attribDict['shape'] = shape
        if line:
            attribDict['line'] = line
        if dis:
            attribDict['dis'] = dis
        if displace:
            attribDict['dis.place'] = displace
        el = Element('clef', attribDict)
        clefObj = clefFromElement(el, None, spannerBundle, otherInfo)
        if clefObj is not None:
            post['clef'] = clefObj

    embeddedItems = _processEmbeddedElements(
        elem.findall('*'), tagToFunction, elem.tag, None, spannerBundle, otherInfo
    )

    for eachItem in embeddedItems:
        if isinstance(eachItem, clef.Clef):
            if 'clef' in post:
                environLocal.warn(_EXTRA_CLEF_IN_STAFFDEF.format(post['clef'], eachItem))
            post['clef'] = eachItem
        if isinstance(eachItem, key.KeySignature):
            if 'key' in post:
                environLocal.warn(_EXTRA_KEYSIG_IN_STAFFDEF.format(post['key'], eachItem))
            post['key'] = eachItem
            updateStaffKeyAndAlters = False  # keySigFromElementInStaffDef just did this
        if isinstance(eachItem, meter.TimeSignature):
            if 'meter' in post:
                environLocal.warn(_EXTRA_METERSIG_IN_STAFFDEF.format(post['meter'], eachItem))
            post['meter'] = eachItem

    if updateStaffKeyAndAlters and 'key' in post:
        nStr: str = otherInfo.get('staffNumberForDef', '')
        if nStr:
            updateStaffKeyAndAltersWithNewKey(
                nStr,
                t.cast(key.KeySignature, post['key']),
                otherInfo
            )

    return post


def updateStaffKeyAndAltersWithNewKey(
    staffNStr: str,
    newKey: t.Optional[t.Union[key.Key, key.KeySignature]],
    otherInfo: t.Dict[str, t.Any]
):
    if otherInfo.get('currKeyPerStaff', None) is None:
        otherInfo['currKeyPerStaff'] = {}
    otherInfo['currKeyPerStaff'][staffNStr] = newKey

    keyAltersForStaff: t.List[int] = M21Utilities.getAltersForKey(newKey)

    if otherInfo.get('currentImpliedAltersPerStaff', None) is None:
        otherInfo['currentImpliedAltersPerStaff'] = {}
    otherInfo['currentImpliedAltersPerStaff'][staffNStr] = keyAltersForStaff


def updateStaffAltersWithPitches(
    staffNStr: str,
    pitches: t.Sequence[pitch.Pitch],
    otherInfo: t.Dict[str, t.Any]
):
    # every note and chord flows through this routine as it is parsed
    if otherInfo.get('currentImpliedAltersPerStaff', None) is None:
        otherInfo['currentImpliedAltersPerStaff'] = {}
    if otherInfo['currentImpliedAltersPerStaff'].get(staffNStr, None) is None:
        # should never happen, but...
        otherInfo['currentImpliedAltersPerStaff'][staffNStr] = [0] * 70

    for thePitch in pitches:
        alterIdx: int = M21Utilities.pitchToBase7(thePitch)
        alter: int = 0
        if thePitch.accidental is not None:
            alter = int(thePitch.accidental.alter)
        otherInfo['currentImpliedAltersPerStaff'][staffNStr][alterIdx] = int(alter)


def dotFromElement(
    elem: Element,  # pylint: disable=unused-argument
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]  # pylint: disable=unused-argument
) -> int:
    '''
    Returns ``1`` no matter what is passed in.

    <dot> Dot of augmentation or division.

    In MEI 2013: pg.304 (318 in PDF) (MEI.shared module)

    :returns: 1
    :rtype: int

    **Attributes/Elements Implemented:** none

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base) (att.id (@xml:id))
    - att.facsimile (@facs)
    - att.dot.log (all)
    - att.dot.vis (all)
    - att.dot.gesatt.dot.anl (all)

    **Elements not Implemented:** none
    '''
    return 1


def articFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> t.List[articulations.Articulation]:
    '''
    <artic> An indication of how to play a note or chord.

    In MEI 2013: pg.259 (273 in PDF) (MEI.shared module)

    :returns: A list of :class:`~music21.articulations.Articulation` objects.

    **Examples**

    This function is normally called by, for example, :func:`noteFromElement`, to determine the
    :class:`Articulation` objects that will be assigned to the
    :attr:`~music21.note.GeneralNote.articulations` attribute.

    >>> from xml.etree import ElementTree as ET
    >>> from converter21.mei.base import articFromElement
    >>> meiSnippet = """<artic artic="acc" xmlns="http://www.music-encoding.org/ns/mei"/>"""
    >>> meiSnippet = ET.fromstring(meiSnippet)
    >>> articFromElement(meiSnippet, None, None, {})
    [<music21.articulations.Accent>]

    A single <artic> element may indicate many :class:`Articulation` objects.

    >>> meiSnippet = """<artic artic="acc ten" xmlns="http://www.music-encoding.org/ns/mei"/>"""
    >>> meiSnippet = ET.fromstring(meiSnippet)
    >>> articFromElement(meiSnippet, None, None, {})
    [<music21.articulations.Accent>, <music21.articulations.Tenuto>]

    **Attributes Implemented:**

    - @artic

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base) (att.id (@xml:id))
    - att.facsimile (@facs)
    - att.typography (@fontfam, @fontname, @fontsize, @fontstyle, @fontweight)
    - att.artic.log

        - (att.controlevent

            - (att.plist (@plist, @evaluate))
            - (att.timestamp.musical (@tstamp))
            - (att.timestamp.performed (@tstamp.ges, @tstamp.real))
            - (att.staffident (@staff))
            - (att.layerident (@layer)))

    - att.artic.vis (all)
    - att.artic.gesatt.artic.anl (all)

    **Contained Elements not Implemented:** none
    '''
    articElement = elem.get('artic')
    if articElement is not None:
        return _makeArticList(articElement)
    else:
        return []


def accidFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> t.Optional[pitch.Accidental]:
    '''
    <accid> Records a temporary alteration to the pitch of a note.

    In MEI 2013: pg.248 (262 in PDF) (MEI.shared module)

    :returns: A music21 Accidental

    **Examples**

    >>> from xml.etree import ElementTree as ET
    >>> from converter21.mei.base import accidFromElement
    >>> meiSnippet = """<accid accid.ges="s" xmlns="http://www.music-encoding.org/ns/mei"/>"""
    >>> meiSnippet = ET.fromstring(meiSnippet)
    >>> accidFromElement(meiSnippet, None, None, {})
    <music21.pitch.Accidental sharp>
    >>> meiSnippet = """<accid accid="tf" xmlns="http://www.music-encoding.org/ns/mei"/>"""
    >>> meiSnippet = ET.fromstring(meiSnippet)
    >>> accidFromElement(meiSnippet, None, None, {})
    <music21.pitch.Accidental triple-flat>

    **Attributes/Elements Implemented:**

    - @accid (from att.accid.log)
    - @accid.ges (from att.accid.ges)

    .. note:: If set, the @accid.ges attribute is always imported as the music21 :class:`Accidental`
        for this note. We assume it corresponds to the accidental implied by a key signature.

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base) (att.id (@xml:id))
    - att.facsimile (@facs)
    - att.typography (@fontfam, @fontname, @fontsize, @fontstyle, @fontweight)
    - att.accid.log (@func)

        - (att.controlevent

            - (att.plist (@plist, @evaluate))
            - (att.timestamp.musical (@tstamp))
            - (att.timestamp.performed (@tstamp.ges, @tstamp.real))
            - (att.staffident (@staff)) (att.layerident (@layer)))

    - att.accid.vis (all)
    - att.accid.anl (all)

    **Contained Elements not Implemented:** none
    '''
    # 1. get @accid/@accid.ges string and displayStatus
    accidStr: t.Optional[str] = None
    displayStatus: t.Optional[bool] = None
    if elem.get('accid.ges') is not None:
        accidStr = _accidGesFromAttr(elem.get('accid.ges'))
        displayStatus = False
    if elem.get('accid') is not None:
        accidStr = _accidentalFromAttr(elem.get('accid'))
        displayStatus = True

    # 2. is it cautionary (display unconditionally in normal position)
    #       or editorial (display unconditionally above the note)
    displayLocation: t.Optional[str] = None
    func: t.Optional[str] = elem.get('func')
    if func is not None:
        if func == 'edit':
            displayStatus = True
            displayLocation = 'above'
        elif func == 'caution':
            displayStatus = True
            displayLocation = 'normal'

    # 3. paren or bracket?
    displayStyle: t.Optional[str] = None
    enclose: t.Optional[str] = elem.get('enclose')
    if enclose is not None:
        if enclose == 'paren':
            displayStatus = True
            displayStyle = 'parentheses'
        elif enclose == 'brack':
            displayStatus = True
            displayStyle = 'bracket'

    if accidStr is None:
        return None

    accidental: pitch.Accidental = pitch.Accidental(accidStr)
    accidental.displayStatus = displayStatus
    if displayLocation:
        accidental.displayLocation = displayLocation
    if displayStyle:
        accidental.displayStyle = displayStyle
    return accidental


def sylFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> note.Lyric:
    '''
    <syl> Individual lyric syllable.

    In MEI 2013: pg.454 (468 in PDF) (MEI.shared module)

    :returns: An appropriately-configured :class:`music21.note.Lyric`.

    **Attributes/Elements Implemented:**

    - @con and @wordpos (from att.syl.log)

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base) (att.id (@xml:id))
    - att.facsimile (@facs)
    - att.syl.vis (att.typography (@fontfam, @fontname, @fontsize, @fontstyle, @fontweight))

        - (att.visualoffset (att.visualoffset.ho (@ho))

            - (att.visualoffset.to (@to))
            - (att.visualoffset.vo (@vo)))

        - (att.xy (@x, @y))
        - (att.horizontalalign (@halign))

    - att.syl.anl (att.common.anl (@copyof, @corresp, @next, @prev, @sameas, @synch)

        -  (att.alignment (@when)))

    **Contained Elements not Implemented:**

    - MEI.edittrans: (all)
    - MEI.figtable: fig
    - MEI.namesdates: corpName geogName periodName persName styleName
    - MEI.ptrref: ptr ref
    - MEI.shared: address bibl date identifier lb name num rend repository stack title
    '''
    wordPosDict: t.Dict[t.Optional[str], t.Optional[t.Literal['begin', 'middle', 'end']]] = {
        'i': 'begin',
        'm': 'middle',
        't': 'end',
        None: None
    }

    # music21 only supports hyphen continuations.
    # conDict: t.Dict[t.Optional[str], str] = {
    #     's': ' ',
    #     'd': '-',
    #     't': '~',
    #     'u': '_',
    #     None: '-'
    # }

    wordPos: t.Optional[str] = elem.get('wordpos')

#     conAttr: t.Optional[str] = elem.get('con')
#     con: t.Optional[str] = conDict.get(conAttr, '-')

    output: note.Lyric
    text: str
    styleDict: t.Dict[str, str]

    text, styleDict = textFromElem(elem)
    text = html.unescape(text)
    text = text.strip()
#     if 'i' == wordPos:
#         text = text + con
#     elif 'm' == wordPos:
#         text = con + text + con
#     elif 't' == wordPos:
#         text = con + text

    # undo the weird "Approximate centering of single-letter text on noteheads" thing
    # that Verovio does:
    if len(text) == 2 and text[0] == '\u00a0':
        text = text[1]

    fontStyle = styleDict.get('fontStyle', None)
    fontWeight = styleDict.get('fontWeight', None)
    fontFamily = styleDict.get('fontFamily', None)
    justify = styleDict.get('justify', None)

    if wordPos is None:
        # no wordPos? Last chance is to use trailing and leading hyphens (applyRaw=False)
        output = note.Lyric(text=text, applyRaw=False)
    else:
        syllabic: t.Optional[t.Literal['begin', 'middle', 'end']] = wordPosDict.get(wordPos, None)
        output = note.Lyric(text=text, syllabic=syllabic, applyRaw=True)

    if fontStyle is not None or fontWeight is not None:
        output.style.fontStyle = (  # type: ignore
            _m21FontStyleFromMeiFontStyleAndWeight(fontStyle, fontWeight)
        )
    if fontFamily is not None:
        output.style.fontFamily = fontFamily  # type: ignore
    if justify is not None:
        output.style.justify = justify  # type: ignore

    return output

def verseFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> note.Lyric:
    '''
    <verse> Lyric verse.

    In MEI 2013: pg.480 (494 in PDF) (MEI.lyrics module)

    :param int backupN: The backup verse number to use if no @n attribute exists on ``elem``.
    :returns: The appropriately-configured :class:`Lyric` objects.
    :rtype: list of :class:`music21.note.Lyric`

    **Attributes/Elements Implemented:**

    - @n and <syl>

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base) (att.id (@xml:id))
    - att.facsimile (@facs)
    - att.lang (@xml:lang)
    - att.verse.log (@refrain, @rhythm)
    - att.verse.vis (att.typography (@fontfam, @fontname, @fontsize, @fontstyle, @fontweight))

        - (att.visualoffset.to (@to))
        - ((att.visualoffset.vo (@vo))

            - (att.xy (@x, @y))

    - att.verse.anl (att.common.anl (@copyof, @corresp, @next, @prev, @sameas, @synch)

        - (att.alignment (@when)))

    **Contained Elements not Implemented:**

    - MEI.shared: dir dynam lb space tempo
    '''
    tagToFunction: t.Dict[str, t.Callable[
        [Element,
            t.Optional[meter.TimeSignature],
            spanner.SpannerBundle,
            t.Dict[str, str]],
        t.Any]
    ] = {
        f'{MEI_NS}label': stringFromElement,
        # music21 doesn't support verse label abbreviations
        # f'{MEI_NS}labelAbbr': labelAbbrFromElement,
        f'{MEI_NS}syl': sylFromElement
    }

    nStr: t.Optional[str] = elem.get('n')
    label: t.Optional[str] = None
    syllables: t.List[note.Lyric] = []

    for subElement in _processEmbeddedElements(elem.findall('*'),
                                               tagToFunction,
                                               elem.tag,
                                               activeMeter,
                                               spannerBundle,
                                               otherInfo):
        if isinstance(subElement, str):
            label = subElement
        elif isinstance(subElement, note.Lyric):
            syllables.append(subElement)

    verse: note.Lyric
    if len(syllables) == 1:
        verse = syllables[0]
    else:
        verse = note.Lyric()

    if nStr is not None:
        try:
            verse.number = int(nStr)
        except (TypeError, ValueError):
            environLocal.warn(_BAD_VERSE_NUMBER.format(nStr))
    if label is not None:
        verse.identifier = label

    if len(syllables) == 1:
        return verse

    verse.components = []
    for eachSyl in syllables:
        verse.components.append(eachSyl)
    return verse


def stringFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> str:
    text: str = ''
    for el in elem.iter():
        # Here is where we would need to handle various editorial elements
        # eg. el.tag being 'app' or 'choice', or ...

        if el.text and el.text[0] != '\n':
            text += el.text

        # we are uninterested in elem.tail
        if el is not elem:
            # we are uninterested in el.tail if it's just due to a LF in the XML file
            if el.tail and el.tail[0] != '\n':
                text += el.tail
    return text

def fermataFromNoteChordOrRestElement(elem: Element) -> t.Optional[expressions.Fermata]:
    fermataPlace: t.Optional[str] = elem.get('fermata')
    if fermataPlace is None:
        return None

    fermata: expressions.Fermata = expressions.Fermata()
    fermataShape: str = elem.get('fermata_shape', '')
    fermataForm: str = elem.get('fermata_form', '')
    # place = 'above' or 'below'
    # form = 'norm' or 'inv'
    # shape = 'angular', 'square', None -> the usual default shape
    # Music21, however, does not support place, just fermata.type = 'inverted'
    # and type = 'upright', which also imply 'below' and 'above', respectively.
    if fermataPlace == 'above':
        fermata.type = 'upright'
    elif fermataPlace == 'below':
        fermata.type = 'inverted'

    if fermataForm == 'norm':
        fermata.type = 'upright'
    elif fermataForm == 'inv':
        fermata.type = 'inverted'

    if fermataShape == 'angular':
        fermata.shape = 'angled'
    elif fermataShape == 'square':
        fermata.shape = 'square'

    return fermata


def durationFromAttributes(
    elem: Element,
    optionalDots: t.Optional[int] = None
) -> duration.Duration:
    durFloat: float = _qlDurationFromAttr(elem.get('dur'))
    durGesFloat: t.Optional[float] = None
    if elem.get('dur.ges'):
        durGesFloat = _qlDurationFromAttr(elem.get('dur.ges'))

    numDots: int
    if optionalDots is not None:
        numDots = optionalDots
    else:
        numDots = int(elem.get('dots', 0))

    numDotsGes: t.Optional[int] = None
    dotsGesStr: str = elem.get('dots.ges', '')
    if dotsGesStr:
        numDotsGes = int(dotsGesStr)

    visualDuration: duration.Duration = makeDuration(durFloat, numDots)
    if durGesFloat is not None or numDotsGes is not None:
        gesDuration: duration.Duration
        if durGesFloat is not None and numDotsGes is not None:
            gesDuration = makeDuration(durGesFloat, numDotsGes)
        elif durGesFloat is not None and numDotsGes is None:
            gesDuration = makeDuration(durGesFloat, numDots)
        elif durGesFloat is None and numDotsGes is not None:
            gesDuration = makeDuration(durFloat, numDotsGes)

        visualDuration.linked = False
        visualDuration.quarterLength = gesDuration.quarterLength

    return visualDuration


def noteFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> note.Note:
    # NOTE: this function should stay in sync with chordFromElement() where sensible
    '''
    <note> is a single pitched event.

    In MEI 2013: pg.382 (396 in PDF) (MEI.shared module)

    .. note:: If set, the @accid.ges attribute is always imported as the music21 :class:`Accidental`
        for this note. We assume it corresponds to the accidental implied by a key signature.

    .. note:: If ``elem`` contains both <syl> and <verse> elements as immediate children, the lyrics
        indicated with <verse> element(s) will always obliterate those given indicated with <syl>
        elements.

    **Attributes/Elements Implemented:**

    - @accid and <accid>
    - @accid.ges for key signatures
    - @pname, from att.pitch: [a--g]
    - @oct, from att.octave: [0..9]
    - @dur, from att.duration.musical: (via _qlDurationFromAttr())
    - @dots: [0..4], and <dot> contained within
    - @xml:id (or id), an XML id (submitted as the Music21Object "id")
    - @artic and <artic>
    - @tie, (many of "[i|m|t]")
    - @slur, (many of "[i|m|t][1-6]")
    - @cue="true" for cue-sized notes
    - @grace, from att.note.ges.cmn: partial implementation (notes marked as grace, but the
        duration is 0 because we ignore the question of which neighbouring note to borrow time from)
    - <syl> and <verse>

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base)
    - att.facsimile (@facs)
    - att.note.log

        - (att.event

            - (att.timestamp.musical (@tstamp))
            - (att.timestamp.performed (@tstamp.ges, @tstamp.real))
            - (att.staffident (@staff))
            - (att.layerident (@layer)))

        - (att.fermatapresent (@fermata))
        - (att.syltext (@syl))
        - (att.note.log.cmn

            - (att.tupletpresent (@tuplet))
            - (att.beamed (@beam))
            - (att.lvpresent (@lv))
            - (att.ornam (@ornam)))

        - (att.note.log.mensural (@lig))

    - att.note.vis (all)

    - att.note.ges

        - (@oct.ges, @pname.ges, @pnum)
        - att.articulation.performed (@artic.ges))
        - (att.duration.performed (@dur.ges))
        - (att.instrumentident (@instr))
        - (att.note.ges.cmn (@gliss)

            - (att.graced (@grace, @grace.time)))  <-- partially implemented

        - (att.note.ges.mensural (att.duration.ratio (@num, @numbase)))
        - (att.note.ges.tablature (@tab.fret, @tab.string))

    - att.note.anl (all)

    **Contained Elements not Implemented:**

    - MEI.critapp: app
    - MEI.edittrans: (all)
    '''
    # make the note (no pitch yet, that has to wait until we have parsed the subelements)
    theNote: note.Note = note.Note()

    # set the Note's duration (we will update this if we find any inner <dot> elements)
    theDuration: duration.Duration = durationFromAttributes(elem)
    theNote.duration = theDuration

    # get any @accid/@accid.ges from this element.
    # We'll overwrite with any subElements below.
    theAccid: t.Optional[str] = _accidentalFromAttr(elem.get('accid'))
    theAccidGes: t.Optional[str] = _accidGesFromAttr(elem.get('accid.ges'))
    theAccidObj: t.Optional[pitch.Accidental] = None

    # iterate all immediate children
    dotElements = 0  # count the number of <dot> elements
    for subElement in _processEmbeddedElements(elem.findall('*'),
                                               noteChildrenTagToFunction,
                                               elem.tag,
                                               activeMeter,
                                               spannerBundle,
                                               otherInfo):
        if isinstance(subElement, int):
            dotElements += subElement
        elif isinstance(subElement, articulations.Articulation):
            theNote.articulations.append(subElement)
        elif isinstance(subElement, pitch.Accidental):
            theAccidObj = subElement
        elif isinstance(subElement, note.Lyric):
            if theNote.lyrics is None:
                theNote.lyrics = []
            theNote.lyrics.append(subElement)

    # dots from inner <dot> elements are an alternate to @dots.
    # If both are present use the <dot> elements.  Shouldn't ever happen.
    if dotElements > 0:
        theDuration = durationFromAttributes(elem, dotElements)
        theNote.duration = theDuration

    # grace note (only mark as accented or unaccented grace note; don't worry about "time-stealing")
    graceStr: t.Optional[str] = elem.get('grace')
    if graceStr == 'acc':
        theNote = theNote.getGrace(appoggiatura=True)
        theNote.duration.slash = False  # type: ignore
    elif graceStr == 'unacc':
        theNote = theNote.getGrace(appoggiatura=False)
        theNote.duration.slash = True  # type: ignore
    elif graceStr is not None:
        # treat it like an unaccented grace note
        theNote = theNote.getGrace(appoggiatura=False)
        theNote.duration.slash = True  # type: ignore

    pnameStr: str = elem.get('pname', '')

    octStr: str = elem.get('oct', '')
    if not octStr:
        octStr = elem.get('oct.ges', '')
    if theAccidObj is not None:
        theNote.pitch = safePitch(pnameStr, theAccidObj, octStr)
    elif theAccidGes is not None:
        theNote.pitch = safePitch(pnameStr, theAccidGes, octStr)
        if theNote.pitch.accidental is not None:
            # since the accidental was due to theAccidGes,
            # the accidental should NOT be displayed.
            theNote.pitch.accidental.displayStatus = False
    elif theAccid is not None:
        theNote.pitch = safePitch(pnameStr, theAccid, octStr)
        if theNote.pitch.accidental is not None:
            # since the accidental was due to theAccid,
            # the accidental should be displayed.
            theNote.pitch.accidental.displayStatus = True
    else:
        theNote.pitch = safePitch(pnameStr, None, octStr)

    nStr: str = otherInfo.get('staffNumberForNotes', '')
    if nStr:
        updateStaffAltersWithPitches(nStr, theNote.pitches, otherInfo)

    # we can only process slurs if we got a SpannerBundle as the "spannerBundle" argument
    if spannerBundle is not None:
        addSlurs(elem, theNote, spannerBundle)

    # id in the @xml:id attribute
    xmlId: t.Optional[str] = elem.get(_XMLID)
    if xmlId is not None:
        theNote.id = xmlId

    # articulations in the @artic attribute
    articStr: t.Optional[str] = elem.get('artic')
    if articStr is not None:
        theNote.articulations.extend(_makeArticList(articStr))

    # expressions from element attributes (perhaps fake attributes created during preprocessing)
    fermata: t.Optional[expressions.Fermata] = fermataFromNoteChordOrRestElement(elem)
    if fermata is not None:
        theNote.expressions.append(fermata)

    addArpeggio(elem, theNote, spannerBundle)
    addTrill(elem, theNote, spannerBundle, otherInfo)
    addMordent(elem, theNote, spannerBundle, otherInfo)
    addTurn(elem, theNote, spannerBundle, otherInfo)
    addOttavas(elem, theNote, spannerBundle)

    # ties in the @tie attribute
    tieStr: t.Optional[str] = elem.get('tie')
    if tieStr is not None:
        theNote.tie = _tieFromAttr(tieStr)

    if elem.get('cue') == 'true':
        if t.TYPE_CHECKING:
            assert isinstance(theNote.style, style.NoteStyle)
        theNote.style.noteSize = 'cue'

    colorStr: t.Optional[str] = elem.get('color')
    if colorStr is not None:
        theNote.style.color = colorStr

    headShape: t.Optional[str] = elem.get('head.shape')
    if headShape is not None:
        if headShape == '+':
            theNote.notehead = 'cross'
        elif headShape == 'diamond':
            theNote.notehead = 'diamond'
        elif headShape == 'isotriangle':
            theNote.notehead = 'triangle'
        elif headShape == 'rectangle':
            theNote.notehead = 'rectangle'
        elif headShape == 'slash':
            theNote.notehead = 'slash'
        elif headShape == 'square':
            theNote.notehead = 'square'
        elif headShape == 'x':
            theNote.notehead = 'x'
        else:
            try:
                theNote.notehead = headShape
            except note.NotRestException:
                # use default notehead if unrecognized (NotRestException)
                pass

    stemDirStr: t.Optional[str] = elem.get('stem.dir')
    if stemDirStr is not None:
        # We don't pay attention to stem direction if the note
        # is supposed to be in another staff (which we don't yet
        # support).
        theNote.stemDirection = _stemDirectionFromAttr(stemDirStr)

    stemModStr: t.Optional[str] = elem.get('stem.mod')
    if stemModStr is not None:
        # just add it as an attribute, to be read by callers if they like
        theNote.mei_stem_mod = stemModStr  # type: ignore

    stemLenStr: t.Optional[str] = elem.get('stem.len')
    stemLen: t.Optional[float] = None
    if stemLenStr is not None:
        try:
            stemLen = float(stemLenStr)
        except:  # pylint: disable=bare-except
            pass
        if stemLen is not None and stemLen == 0:
            theNote.stemDirection = 'noStem'

    stemVisible: t.Optional[str] = elem.get('stem.visible')
    if stemVisible is not None and stemVisible == 'false':
        theNote.stemDirection = 'noStem'

    # breaksec="n" means that the beams that cross this note drop down to "n" beams
    # between this note and the next note.  Mark this in theNote with a custom attribute.
    breaksec: t.Optional[str] = elem.get('breaksec')
    if breaksec is not None:
        theNote.mei_breaksec = breaksec  # type: ignore

    # beams indicated by a <beamSpan> held elsewhere
    if elem.get('m21Beam') is not None:
        if duration.convertTypeToNumber(theNote.duration.type) > 4:
            theNote.beams.fill(theNote.duration.type, elem.get('m21Beam'))

    # tuplets
    if elem.get('m21TupletNum') is not None:
        obj = scaleToTuplet(theNote, elem)
        if t.TYPE_CHECKING:
            # because scaleToTuplet always returns whatever objs it was passed (modified)
            assert isinstance(obj, note.Note)
        theNote = obj

    # visibility
    if elem.get('visible') == 'false':
        theNote.style.hideObjectOnPrint = True

    # stash the staffNum in theNote.mei_staff (in case a spanner needs to know)
    staffNumStr: str = otherInfo.get('staffNumberForNotes', '')
    if staffNumStr:
        theNote.mei_staff = staffNumStr  # type: ignore

    return theNote


def restFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> note.Rest:
    '''
    <rest/> is a non-sounding event found in the source being transcribed

    In MEI 2013: pg.424 (438 in PDF) (MEI.shared module)

    **Attributes/Elements Implemented:**

    - xml:id (or id), an XML id (submitted as the Music21Object "id")
    - dur, from att.duration.musical: (via _qlDurationFromAttr())
    - dots, from att.augmentdots: [0..4]
    - @cue="true" for cue-sized rests

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base)
    - att.facsimile (@facs)
    - att.rest.log

        - (att.event

            - (att.timestamp.musical (@tstamp))
            - (att.timestamp.performed (@tstamp.ges, @tstamp.real))
            - (att.staffident (@staff))
            - (att.layerident (@layer)))

        - (att.fermatapresent (@fermata))

            - (att.tupletpresent (@tuplet))
            - (att.rest.log.cmn (att.beamed (@beam)))

    - att.rest.vis (all)
    - att.rest.ges (all)
    - att.rest.anl (all)

    **Contained Elements not Implemented:** none
    '''
    # NOTE: keep this in sync with spaceFromElement()

    theDuration: duration.Duration = durationFromAttributes(elem)
    theRest = note.Rest(duration=theDuration)

    xmlId: t.Optional[str] = elem.get(_XMLID)
    if xmlId is not None:
        theRest.id = xmlId

    # expressions from element attributes (perhaps fake attributes created during preprocessing)
    fermata = fermataFromNoteChordOrRestElement(elem)
    if fermata is not None:
        theRest.expressions.append(fermata)

    if elem.get('cue') == 'true':
        if t.TYPE_CHECKING:
            assert isinstance(theRest.style, style.NoteStyle)
        theRest.style.noteSize = 'cue'

    colorStr: t.Optional[str] = elem.get('color')
    if colorStr is not None:
        theRest.style.color = colorStr

    # tuplets
    if elem.get('m21TupletNum') is not None:
        obj = scaleToTuplet(theRest, elem)
        if t.TYPE_CHECKING:
            # because scaleToTuplet returns whatever it was passed (modified)
            assert isinstance(obj, note.Rest)
        theRest = obj

    # visibility
    if elem.get('visible') == 'false':
        theRest.style.hideObjectOnPrint = True

    # stash the staffNum in theRest.mei_staff (in case a spanner needs to know)
    staffNumStr: str = otherInfo.get('staffNumberForNotes', '')
    if staffNumStr:
        theRest.mei_staff = staffNumStr  # type: ignore

    return theRest


def mRestFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> note.Rest:
    '''
    <mRest/> Complete measure rest in any meter.

    In MEI 2013: pg.375 (389 in PDF) (MEI.cmn module)

    This is a function wrapper for :func:`restFromElement`.

    .. note:: If the <mRest> element does not have a @dur attribute, it will have the default
        duration of 1.0. This must be fixed later, so the :class:`Rest` object returned from this
        method is given the :attr:`m21wasMRest` attribute, set to True.
    '''
    # NOTE: keep this in sync with mSpaceFromElement()

    if elem.get('dur') is not None:
        return restFromElement(elem, activeMeter, spannerBundle, otherInfo)
    else:
        theRest = restFromElement(elem, activeMeter, spannerBundle, otherInfo)
        theRest.m21wasMRest = True  # type: ignore
        return theRest


def spaceFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> note.Rest:
    '''
    <space>  A placeholder used to fill an incomplete measure, layer, etc. most often so that the
    combined duration of the events equals the number of beats in the measure.

    Returns a Rest element with hideObjectOnPrint = True

    In MEI 2013: pg.440 (455 in PDF) (MEI.shared module)
    '''
    # NOTE: keep this in sync with restFromElement()

    theDuration: duration.Duration = durationFromAttributes(elem)
    theSpace: note.Rest = note.Rest(duration=theDuration)
    theSpace.style.hideObjectOnPrint = True

    xmlId: t.Optional[str] = elem.get(_XMLID)
    if xmlId is not None:
        theSpace.id = xmlId

    # tuplets
    if elem.get('m21TupletNum') is not None:
        obj = scaleToTuplet(theSpace, elem)
        if t.TYPE_CHECKING:
            # because scaleToTuplet returns the same type it was passed
            assert isinstance(obj, note.Rest)
        theSpace = obj

    return theSpace


def mSpaceFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> note.Rest:
    '''
    <mSpace/> A measure containing only empty space in any meter.

    In MEI 2013: pg.377 (391 in PDF) (MEI.cmn module)

    This is a function wrapper for :func:`spaceFromElement`.

    .. note:: If the <mSpace> element does not have a @dur attribute, it will have the default
        duration of 1.0. This must be fixed later, so the :class:`Space` object returned from this
        method is given the :attr:`m21wasMRest` attribute, set to True.
    '''
    # NOTE: keep this in sync with mRestFromElement()

    if elem.get('dur') is not None:
        return spaceFromElement(elem, activeMeter, spannerBundle, otherInfo)
    else:
        theSpace = spaceFromElement(elem, activeMeter, spannerBundle, otherInfo)
        theSpace.m21wasMRest = True  # type: ignore
        return theSpace


def chordFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> chord.Chord:
    # NOTE: this function should stay in sync with noteFromElement() where sensible
    '''
    <chord> is a simultaneous sounding of two or
    more notes in the same layer with the same duration.

    In MEI 2013: pg.280 (294 in PDF) (MEI.shared module)

    **Attributes/Elements Implemented:**

    - @xml:id (or id), an XML id (submitted as the Music21Object "id")
    - <note> contained within
    - @dur, from att.duration.musical: (via _qlDurationFromAttr())
    - @dots, from att.augmentdots: [0..4]
    - @artic and <artic>
    - @tie, (many of "[i|m|t]")
    - @slur, (many of "[i|m|t][1-6]")
    - @cue="true" for cue-sized chords
    - @grace, from att.note.ges.cmn: partial implementation (notes marked as grace, but the
        duration is 0 because we ignore the question of which neighbouring note to borrow time from)

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base)
    - att.facsimile (@facs)
    - att.chord.log

        - (att.event

            - (att.timestamp.musical (@tstamp))
            - (att.timestamp.performed (@tstamp.ges, @tstamp.real))
            - (att.staffident (@staff))
            - (att.layerident (@layer)))

        - (att.fermatapresent (@fermata))
        - (att.syltext (@syl))
        - (att.chord.log.cmn

            - (att.tupletpresent (@tuplet))
            - (att.beamed (@beam))
            - (att.lvpresent (@lv))
            - (att.ornam (@ornam)))

    - att.chord.vis (all)
    - att.chord.ges

        - (att.articulation.performed (@artic.ges))
        - (att.duration.performed (@dur.ges))
        - (att.instrumentident (@instr))
        - (att.chord.ges.cmn (att.graced (@grace, @grace.time)))  <-- partially implemented

    - att.chord.anl (all)

    **Contained Elements not Implemented:**

    - MEI.edittrans: (all)
    '''
    theNoteList: t.List[note.Note] = []
    theArticList: t.List[articulations.Articulation] = []
    theLyricList: t.List[note.Lyric] = []
    spannersFromNotes: t.List[t.Tuple[note.Note, t.List[spanner.Spanner]]] = []
    # iterate all immediate children
    for subElement in _processEmbeddedElements(elem.findall('*'),
                                               chordChildrenTagToFunction,
                                               elem.tag,
                                               activeMeter,
                                               spannerBundle,
                                               otherInfo):
        if isinstance(subElement, note.Note):
            theNoteList.append(subElement)
            spannersFromThisNote: t.List[spanner.Spanner] = subElement.getSpannerSites()
            if spannersFromThisNote:
                spannersFromNotes.append((subElement, spannersFromThisNote))
        if isinstance(subElement, articulations.Articulation):
            theArticList.append(subElement)
        elif isinstance(subElement, note.Lyric):
            theLyricList.append(subElement)

    theChord: chord.Chord = chord.Chord(notes=theNoteList)
    if theArticList:
        theChord.articulations = theArticList
    if theLyricList:
        theChord.lyrics = theLyricList
    if spannersFromNotes:
        for eachNote, spanners in spannersFromNotes:
            for eachSpanner in spanners:
                eachSpanner.replaceSpannedElement(eachNote, theChord)

    # set the Chord's duration
    theDuration: duration.Duration = durationFromAttributes(elem)
    theChord.duration = theDuration

    # grace note (only mark as accented or unaccented grace note; don't worry about "time-stealing")
    graceStr: t.Optional[str] = elem.get('grace')
    if graceStr == 'acc':
        theChord = theChord.getGrace(appoggiatura=True)
        theChord.duration.slash = False  # type: ignore
    elif graceStr == 'unacc':
        theChord = theChord.getGrace(appoggiatura=False)
        theChord.duration.slash = True  # type: ignore
    elif graceStr is not None:
        # treat it like an unaccented grace note
        theChord = theChord.getGrace(appoggiatura=False)
        theChord.duration.slash = True  # type: ignore

    nStr: str = otherInfo.get('staffNumberForNotes', '')
    if nStr:
        updateStaffAltersWithPitches(nStr, theChord.pitches, otherInfo)

    # we can only process slurs if we got a SpannerBundle as the "spannerBundle" argument
    if spannerBundle is not None:
        addSlurs(elem, theChord, spannerBundle)

    # id in the @xml:id attribute
    xmlId: t.Optional[str] = elem.get(_XMLID)
    if xmlId is not None:
        theChord.id = xmlId

    # articulations in the @artic attribute
    articStr: t.Optional[str] = elem.get('artic')
    if articStr is not None:
        theChord.articulations.extend(_makeArticList(articStr))

    # expressions from element attributes (perhaps fake attributes created during preprocessing)
    fermata = fermataFromNoteChordOrRestElement(elem)
    if fermata is not None:
        theChord.expressions.append(fermata)

    addArpeggio(elem, theChord, spannerBundle)
    addTrill(elem, theChord, spannerBundle, otherInfo)
    addMordent(elem, theChord, spannerBundle, otherInfo)
    addTurn(elem, theChord, spannerBundle, otherInfo)
    addOttavas(elem, theChord, spannerBundle)

    # See if any of the notes within the chord have a trill/mordent/turn,
    # and if so, pull it up to the chord (because music21 doesn't really
    # support those ornaments on notes within chords).
    gotOne: bool = False
    for n in theChord.notes:
        for expr in n.expressions:
            if isinstance(
                expr,
                (expressions.Trill, expressions.GeneralMordent, expressions.Turn)
            ):
                gotOne = True
                theChord.expressions.append(expr)
                n.expressions.remove(expr)
                break
        if gotOne:
            break

    # ties in the @tie attribute
    tieStr: t.Optional[str] = elem.get('tie')
    if tieStr is not None:
        theChord.tie = _tieFromAttr(tieStr)

    if elem.get('cue') == 'true':
        if t.TYPE_CHECKING:
            assert isinstance(theChord.style, style.NoteStyle)
        theChord.style.noteSize = 'cue'

    colorStr: t.Optional[str] = elem.get('color')
    if colorStr is not None:
        theChord.style.color = colorStr

    stemDirStr: t.Optional[str] = elem.get('stem.dir')
    if stemDirStr is not None:
        # We don't pay attention to stem direction if the chord
        # is supposed to be in another staff (which we don't yet
        # support).
        theChord.stemDirection = _stemDirectionFromAttr(stemDirStr)

    stemModStr: t.Optional[str] = elem.get('stem.mod')
    if stemModStr is not None:
        # just add it as an attribute, to be read by callers if they like
        theChord.mei_stem_mod = stemModStr  # type: ignore

    # breaksec="n" means that the beams that cross this note drop down to "n" beams
    # between this note and the next note.  Mark this in theNote with a custom attribute.
    breaksec: t.Optional[str] = elem.get('breaksec')
    if breaksec is not None:
        theChord.mei_breaksec = breaksec  # type: ignore

    # beams indicated by a <beamSpan> held elsewhere
    m21BeamStr: t.Optional[str] = elem.get('m21Beam')
    if m21BeamStr is not None:
        if duration.convertTypeToNumber(theChord.duration.type) > 4:
            theChord.beams.fill(theChord.duration.type, m21BeamStr)

    # tuplets
    if elem.get('m21TupletNum') is not None:
        obj = scaleToTuplet(theChord, elem)
        if t.TYPE_CHECKING:
            # because scaleToTuplet returns whatever type it was passed
            assert isinstance(obj, chord.Chord)
        theChord = obj

    # visibility
    if elem.get('visible') == 'false':
        theChord.style.hideObjectOnPrint = True

    # stash the staffNum in theChord.mei_staff (in case a spanner needs to know)
    staffNumStr: str = otherInfo.get('staffNumberForNotes', '')
    if staffNumStr:
        theChord.mei_staff = staffNumStr  # type: ignore

    return theChord


def clefFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> t.Optional[clef.Clef]:
    '''
    <clef> Indication of the exact location of a particular note on the staff and, therefore,
    the other notes as well.

    In MEI 2013: pg.284 (298 in PDF) (MEI.shared module)

    **Attributes/Elements Implemented:**

    - @xml:id (or id), an XML id (submitted as the Music21Object "id")
    - @shape, from att.clef.gesatt.clef.log
    - @line, from att.clef.gesatt.clef.log
    - @dis, from att.clef.gesatt.clef.log
    - @dis.place, from att.clef.gesatt.clef.log

    **Attributes/Elements Ignored:**

    - @cautionary, since this has no obvious implication for a music21 Clef
    - @octave, since this is likely obscure

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base)
    - att.event

        - (att.timestamp.musical (@tstamp))
        - (att.timestamp.performed (@tstamp.ges, @tstamp.real))
        - (att.staffident (@staff))
        - (att.layerident (@layer))

    - att.facsimile (@facs)
    - att.clef.anl (all)
    - att.clef.vis (all)

    **Contained Elements not Implemented:** none
    '''
    theClef: clef.Clef
    if elem.get('sameas') is not None:
        return None

    shapeStr: t.Optional[str] = elem.get('shape')
    lineStr: t.Optional[str] = elem.get('line')
    octaveShiftOverride: t.Optional[int] = None
    if 'perc' == shapeStr:
        theClef = clef.PercussionClef()
    elif 'TAB' == shapeStr:
        theClef = clef.TabClef()
    else:
        if shapeStr is None:
            # default to treble clef shape
            shapeStr = 'G'
        if lineStr is None:
            # music21 has defaults for missing lineStr, but it has to be ''
            lineStr = ''
        if shapeStr == 'GG':
            shapeStr = 'G'
            octaveShiftOverride = -1
        if octaveShiftOverride is not None:
            theClef = clef.clefFromString(shapeStr + lineStr, octaveShiftOverride)
        else:
            theClef = clef.clefFromString(
                shapeStr + lineStr,
                _getOctaveShift(elem.get('dis'), elem.get('dis.place'))
            )

    xmlId: t.Optional[str] = elem.get(_XMLID)
    if xmlId is not None:
        theClef.id = xmlId

    return theClef


def keySigFromElementInStaffDef(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> t.Optional[t.Union[key.Key, key.KeySignature]]:
    newKey: t.Optional[t.Union[key.Key, key.KeySignature]] = (
        _keySigFromElement(elem, activeMeter, spannerBundle, otherInfo)
    )
    nStr: str = otherInfo.get('staffNumberForDef', '')
    if nStr:
        updateStaffKeyAndAltersWithNewKey(nStr, newKey, otherInfo)

    return newKey


def keySigFromElementInLayer(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> t.Optional[t.Union[key.Key, key.KeySignature]]:
    newKey: t.Optional[t.Union[key.Key, key.KeySignature]] = (
        _keySigFromElement(elem, activeMeter, spannerBundle, otherInfo)
    )
    nStr: str = otherInfo.get('staffNumberForLayer', '')
    if nStr:
        updateStaffKeyAndAltersWithNewKey(nStr, newKey, otherInfo)

    return newKey


def _keySigFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> t.Optional[t.Union[key.Key, key.KeySignature]]:
    theKey: t.Optional[t.Union[key.Key, key.KeySignature]] = _keySigFromAttrs(elem)
    if theKey is None:
        return None

    xmlId: t.Optional[str] = elem.get(_XMLID)
    if xmlId is not None:
        theKey.id = xmlId

    return theKey


def timeSigFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> t.Optional[meter.TimeSignature]:
    theTimeSig: t.Optional[meter.TimeSignature] = _timeSigFromAttrs(elem)
    if theTimeSig is None:
        return None

    xmlId: t.Optional[str] = elem.get(_XMLID)
    if xmlId is not None:
        theTimeSig.id = xmlId

    return theTimeSig


def instrDefFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> instrument.Instrument:
    # TODO: robuster handling of <instrDef>, including <instrGrp> and if held in a <staffGrp>
    '''
    <instrDef> (instrument definition)---MIDI instrument declaration.

    In MEI 2013: pg.344 (358 in PDF) (MEI.midi module)

    :returns: An :class:`Instrument`

    **Attributes/Elements Implemented:**

    - @midi.instrname (att.midiinstrument)
    - @midi.instrnum (att.midiinstrument)

    **Attributes/Elements in Testing:** none

    **Attributes/Elements Ignored:**

    - @xml:id

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base)
    - att.channelized (@midi.channel, @midi.duty, @midi.port, @midi.track)
    - att.midiinstrument (@midi.pan, @midi.volume)

    **Contained Elements not Implemented:** none
    '''
    instrNumStr: t.Optional[str] = elem.get('midi.instrnum')
    if instrNumStr is not None:
        try:
            return instrument.instrumentFromMidiProgram(int(instrNumStr))
        except (TypeError, instrument.InstrumentException):
            pass

    instrNameStr: t.Optional[str] = elem.get('midi.instrname', '')
    if t.TYPE_CHECKING:
        # default if missing is ''
        assert instrNameStr is not None

    try:
        return instrument.fromString(instrNameStr)
    except (AttributeError, instrument.InstrumentException):
        pass

    # last fallback: just use instrNameStr (might even be '') as a custom name
    theInstr = instrument.Instrument()
    theInstr.partName = instrNameStr
    return theInstr


def beamFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.Sequence[Music21Object]:
    '''
    <beam> A container for a series of explicitly beamed events that begins and ends entirely
           within a measure.

    In MEI 2013: pg.264 (278 in PDF) (MEI.cmn module)

    :param elem: The ``<beam>`` element to process.
    :type elem: :class:`~xml.etree.ElementTree.Element`
    :returns: An iterable of all the objects contained within the ``<beam>`` container.
    :rtype: list of :class:`~music21.base.Music21Object`

    **Example**

    Here, three :class:`Note` objects are beamed together. Take note that the function returns
    a list of three objects, none of which is a :class:`Beam` or similar.

    >>> from xml.etree import ElementTree as ET
    >>> from converter21.mei.base import beamFromElement
    >>> meiSnippet = """<beam xmlns="http://www.music-encoding.org/ns/mei">
    ...     <note pname='A' oct='7' dur='8'/>
    ...     <note pname='B' oct='7' dur='8'/>
    ...     <note pname='C' oct='6' dur='8'/>
    ... </beam>"""
    >>> meiSnippet = ET.fromstring(meiSnippet)
    >>> result = beamFromElement(meiSnippet, None, None, {})
    >>> isinstance(result, list)
    True
    >>> len(result)
    3
    >>> result[0].pitch.nameWithOctave
    'A7'
    >>> result[0].beams
    <music21.beam.Beams <music21.beam.Beam 1/start>>
    >>> result[1].pitch.nameWithOctave
    'B7'
    >>> result[1].beams
    <music21.beam.Beams <music21.beam.Beam 1/continue>>
    >>> result[2].pitch.nameWithOctave
    'C6'
    >>> result[2].beams
    <music21.beam.Beams <music21.beam.Beam 1/stop>>

    **Attributes/Elements Implemented:**

    - <clef>, <chord>, <note>, <rest>, <space>, <tuplet>, <beam>, <barLine>

    **Attributes/Elements Ignored:**

    - @xml:id

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base)
    - att.facsimile (@facs)
    - att.beam.log

        - (att.event

            - (att.timestamp.musical (@tstamp))
            - (att.timestamp.performed (@tstamp.ges, @tstamp.real))
            - (att.staffident (@staff))
            - (att.layerident (@layer)))

        - (att.beamedwith (@beam.with))

    - att.beam.vis (all)
    - att.beam.gesatt.beam.anl (all)

    **Contained Elements not Implemented:**

    - MEI.cmn: beatRpt halfmRpt meterSig meterSigGrp
    - MEI.critapp: app
    - MEI.edittrans: (all)
    - MEI.mensural: ligature mensur proport
    - MEI.shared: clefGrp custos keySig pad
    '''
    # NB: The doctest is a sufficient integration test. Since there is no logic, I don't think we
    #     need to bother with unit testing.

    beamedStuff: t.List[Music21Object] = _processEmbeddedElements(
        elem.findall('*'),
        beamChildrenTagToFunction,
        elem.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    beamTogether(beamedStuff)
    applyBreaksecs(beamedStuff)

    return beamedStuff


def bTremFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    '''
    <bTrem> contains one <note> or <chord> (or editorial elements that resolve to a single
    note or chord)
    '''
    bTremStuff: t.List[Music21Object] = _processEmbeddedElements(
        elem.findall('*'),
        bTremChildrenTagToFunction,
        elem.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    if len(bTremStuff) != 1:
        raise MeiElementError('<bTrem> without exactly one note or chord within')

    noteOrChord: Music21Object = bTremStuff[0]
    if t.TYPE_CHECKING:
        assert isinstance(noteOrChord, note.NotRest)
    tremolo: expressions.Tremolo = expressions.Tremolo()
    unitdurStr: str = elem.get('unitdur', '')
    numMarks: int = _DUR_TO_NUMBEAMS.get(unitdurStr, 0)
    if numMarks == 0:
        # check the note or chord itself to see if it has @stem.mod = '3slashes' or the like
        if hasattr(noteOrChord, 'mei_stem_mod'):
            numMarks = _STEMMOD_TO_NUMSLASHES.get(noteOrChord.mei_stem_mod, 0)  # type: ignore

    if numMarks == 9:
        numMarks = 8  # music21 doesn't support a 2048th note tremolo, pretend it's 1024th note

    if numMarks > 0:
        tremolo.numberOfMarks = numMarks
        noteOrChord.expressions.append(tremolo)

    return bTremStuff


def fTremFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    '''
    <fTrem> contains two <note>s or two <chord>s or one of each (or editorial elements that
    resolve to two <note>s or two <chord>s or one of each)
    '''
    fTremStuff: t.List[Music21Object] = _processEmbeddedElements(
        elem.findall('*'),
        fTremChildrenTagToFunction,
        elem.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    if len(fTremStuff) != 2:
        raise MeiElementError('<fTrem> without exactly two notes/chords (or one of each) within')

    firstNoteOrChord: Music21Object = fTremStuff[0]
    secondNoteOrChord: Music21Object = fTremStuff[1]
    if t.TYPE_CHECKING:
        assert isinstance(firstNoteOrChord, note.NotRest)
        assert isinstance(secondNoteOrChord, note.NotRest)

    numMarks: int = 0
    beamsStr: str = elem.get('beams', '0')
    try:
        numMarks = int(beamsStr)
    except (TypeError, ValueError):
        pass

    if numMarks == 0:
        # check the notes or chords themselves to see if they have @stem.mod = '3slashes'
        # or the like
        if hasattr(firstNoteOrChord, 'mei_stem_mod'):
            numMarks = _STEMMOD_TO_NUMSLASHES.get(firstNoteOrChord.mei_stem_mod, 0)  # type: ignore
        if numMarks == 0 and hasattr(secondNoteOrChord, 'mei_stem_mod'):
            numMarks = _STEMMOD_TO_NUMSLASHES.get(secondNoteOrChord.mei_stem_mod, 0)  # type: ignore

    # numMarks should be total number of beams - beams due to note duration
    numNoteBeams: int = _QL_TO_NUMFLAGS.get(firstNoteOrChord.duration.quarterLength, 0)
    numMarks -= numNoteBeams

    if numMarks == 9:
        numMarks = 8  # music21 doesn't support a 2048th note tremolo, pretend it's 1024th note

    if numMarks > 0:
        # music21 needs the gestural duration to be set properly, and visual duration left at
        # full fTrem duration
        visualDur: OffsetQL = firstNoteOrChord.duration.quarterLength
        firstNoteOrChord.duration.linked = False
        firstNoteOrChord.duration.quarterLength = opFrac(visualDur / 2.)
        secondNoteOrChord.duration.linked = False
        secondNoteOrChord.duration.quarterLength = firstNoteOrChord.duration.quarterLength

        tremoloSpanner: expressions.TremoloSpanner = (
            expressions.TremoloSpanner(firstNoteOrChord, secondNoteOrChord)
        )
        tremoloSpanner.numberOfMarks = numMarks
        spannerBundle.append(tremoloSpanner)

    return fTremStuff


def barLineFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,  # pylint: disable=unused-argument
    otherInfo: t.Dict[str, t.Any]
) -> t.Union[bar.Barline, bar.Repeat, t.Tuple[bar.Repeat, ...]]:
    '''
    <barLine> Vertical line drawn through one or more staves that divides musical notation into
    metrical units.

    In MEI 2013: pg.262 (276 in PDF) (MEI.shared module)

    :returns: A :class:`music21.bar.Barline` or :class:`~music21.bar.Repeat`, depending on the
        value of @rend. If @rend is ``'rptboth'``, a 2-tuplet of :class:`Repeat` objects will be
        returned, represented an "end" and "start" barline, as specified in the :mod:`music21.bar`
        documentation.

    .. note:: The music21-to-other converters expect that a :class:`Barline` will be attached to a
        :class:`Measure`, which it will not be when imported from MEI as a <barLine> element.
        However, this function does import correctly to a :class:`Barline` that you can access from
        Python in the :class:`Stream` object as expected.

    **Attributes/Elements Implemented:**

    - @rend from att.barLine.log

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base) (att.id (@xml:id))
    - att.facsimile (@facs)
    - att.pointing (@xlink:actuate, @xlink:role, @xlink:show, @target, @targettype, @xlink:title)
    - att.barLine.log

        - (att.meterconformance.bar (@metcon, @control))

    - att.barLine.vis

        - (att.barplacement (@barplace, @taktplace))
        - (att.color (@color))
        - (att.measurement (@unit))
        - (att.width (@width))

    - att.barLine.ges (att.timestamp.musical (@tstamp))
    - att.barLine.anl

        - (att.common.anl

            - (@copyof, @corresp, @next, @prev, @sameas, @synch)
            - (att.alignment (@when)))

    **Contained Elements not Implemented:** none
    '''
    return _barlineFromAttr(elem.get('rend', 'single'))


def tupletFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    '''
    <tuplet> A group of notes with "irregular" (sometimes called "irrational") rhythmic values,
    for example, three notes in the time normally occupied by two or nine in the time of five.

    In MEI 2013: pg.473 (487 in PDF) (MEI.cmn module)

    :param elem: The ``<tuplet>`` element to process.
    :type elem: :class:`~xml.etree.ElementTree.Element`
    :returns: An iterable of all the objects contained within the ``<tuplet>`` container.
    :rtype: tuple of :class:`~music21.base.Music21Object`

    **Attributes/Elements Implemented:**

    - <tuplet>, <beam>, <note>, <rest>, <chord>, <clef>, <space>, <barLine>
    - @num and @numbase

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base) (att.id (@xml:id))
    - att.facsimile (@facs)
    - att.tuplet.log

        - (att.event

            - (att.timestamp.musical (@tstamp))
            - (att.timestamp.performed (@tstamp.ges, @tstamp.real))
            - (att.staffident (@staff))
            - (att.layerident (@layer)))

        - (att.beamedwith (@beam.with))
        - (att.augmentdots (@dots))
        - (att.duration.additive (@dur))
        - (att.startendid (@endid) (att.startid (@startid)))

    - att.tuplet.vis (all)
    - att.tuplet.ges (att.duration.performed (@dur.ges))
    - att.tuplet.anl (all)

    **Contained Elements not Implemented:**

    - MEI.cmn: beatRpt halfmRpt meterSig meterSigGrp
    - MEI.critapp: app
    - MEI.edittrans: (all)
    - MEI.mensural: ligature mensur proport
    - MEI.shared: clefGrp custos keySig pad
    '''
    # get the @num and @numbase attributes, without which we can't properly calculate the tuplet
    numStr: t.Optional[str] = elem.get('num')
    numbaseStr: t.Optional[str] = elem.get('numbase')
    if numStr is None or numbaseStr is None:
        raise MeiAttributeError(_MISSING_TUPLET_DATA)

    # iterate all immediate children
    tupletMembers: t.List[Music21Object] = _processEmbeddedElements(
        elem.findall('*'),
        tupletChildrenTagToFunction,
        elem.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    # "tuplet-ify" the duration of everything held within
    newElem = Element('c', m21TupletNum=numStr, m21TupletNumbase=numbaseStr)
    tupletMembers = t.cast(t.List[Music21Object], scaleToTuplet(tupletMembers, newElem))

    # Set the Tuplet.type property for the first and final note in a tuplet.
    # We have to find the first and last duration-having thing, not just the first and last objects
    # between the <tuplet> tags.
    firstNote = None
    lastNote = None
    for i, eachObj in enumerate(tupletMembers):
        if firstNote is None and isinstance(eachObj, note.GeneralNote):
            firstNote = i
        elif isinstance(eachObj, note.GeneralNote):
            lastNote = i

    if firstNote is None:
        # no members of tuplet
        return []

    tupletMembers[firstNote].duration.tuplets[0].type = 'start'
    if lastNote is None:
        # when there is only one object in the tuplet
        tupletMembers[firstNote].duration.tuplets[0].type = 'stop'
    else:
        tupletMembers[lastNote].duration.tuplets[0].type = 'stop'

    return tupletMembers


def _isLastDurationalElement(idx: int, elements: t.List[Music21Object]) -> bool:
    if elements[idx].quarterLength == 0:
        # it's not a durational element at all
        return False
    for i in range(idx + 1, len(elements) - 1):
        if elements[i].quarterLength != 0:
            # found a subsequent durational element, so it's not the last one
            return False
    return True

def layerFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any],
    overrideN: t.Optional[str] = None
) -> stream.Voice:
    '''
    <layer> An independent stream of events on a staff.

    In MEI 2013: pg.353 (367 in PDF) (MEI.shared module)

    .. note:: The :class:`Voice` object's :attr:`~music21.stream.Voice.id` attribute must be set
        properly in order to ensure continuity of voices between measures. If the ``elem`` does not
        have an @n attribute, you can set one with the ``overrideN`` parameter in this function. If
        you provide a value for ``overrideN``, it will be used instead of the ``elemn`` object's
        @n attribute.

        Because improperly-set :attr:`~music21.stream.Voice.id` attributes nearly guarantees errors
        in the imported :class:`Score`, either ``overrideN`` or @n must be specified.

    :param elem: The ``<layer>`` element to process.
    :type elem: :class:`~xml.etree.ElementTree.Element`
    :param str overrideN: The value to be set as the ``id``
        attribute in the outputted :class:`Voice`.
    :returns: A :class:`Voice` with the objects found in the provided :class:`Element`.
    :rtype: :class:`music21.stream.Voice`
    :raises: :exc:`MeiAttributeError` if neither ``overrideN`` nor @n are specified.

    **Attributes/Elements Implemented:**

    - <clef>, <chord>, <note>, <rest>, <mRest>, <beam>, <tuplet>, <space>, <mSpace> , and
      <barLine> contained within
    - @n, from att.common

    **Attributes Ignored:**

    - @xml:id

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @xml:base)
    - att.declaring (@decls)
    - att.facsimile (@facs)
    - att.layer.log (@def) and (att.meterconformance (@metcon))
    - att.layer.vis (att.visibility (@visible))
    - att.layer.gesatt.layer.anl (all)

    **Contained Elements not Implemented:**

    - MEI.cmn: arpeg beamSpan beatRpt bend breath fermata gliss hairpin halfmRpt
               harpPedal mRpt mRpt2 meterSigGrp multiRest multiRpt octave pedal
               reh slur tie tuplet tupletSpan
    - MEI.cmnOrnaments: mordent trill turn
    - MEI.critapp: app
    - MEI.edittrans: (all)
    - MEI.harmony: harm
    - MEI.lyrics: lyrics
    - MEI.mensural: ligature mensur proport
    - MEI.midi: midi
    - MEI.neumes: ineume syllable uneume
    - MEI.shared: accid annot artic barLine clefGrp custos dir dot dynam pad pb phrase sb
                  scoreDef staffDef tempo
    - MEI.text: div
    - MEI.usersymbols: anchoredText curve line symbol
    '''

    # iterate all immediate children
    theLayer: t.List[Music21Object] = _processEmbeddedElements(
        elem.iterfind('*'),
        layerChildrenTagToFunction,
        elem.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    # adjust the <layer>'s elements for possible tuplets
    theLayer = _guessTuplets(theLayer)

    # Verovio, when converting from Humdrum to MEI, has been known to put <space> fillers
    # immediately after the end of a measure's/layer's usual duration, as an errant response
    # to a *clef token in the middle of a final rest or note.  This was fixed recently, but
    # because many such MEI files have been saved, we need to ignore these.
    if activeMeter is not None:
        expectedLayerDur: OffsetQL = 4.0 * opFrac(
            Fraction(activeMeter.numerator, activeMeter.denominator)
        )
        removeThisOne: t.Optional[int] = None
        currOffset: OffsetQL = 0.
        for i, each in enumerate(theLayer):
            if currOffset == expectedLayerDur:
                if isinstance(each, note.Rest) and each.style.hideObjectOnPrint:
                    if _isLastDurationalElement(i, theLayer):
                        removeThisOne = i
                        break
            currOffset = opFrac(currOffset + each.quarterLength)
        if removeThisOne is not None:
            theLayer.pop(removeThisOne)

    # make the Voice
    theVoice: stream.Voice = stream.Voice()
    for each in theLayer:
        theVoice.coreAppend(each)
    theVoice.coreElementsChanged()

    # try to set the Voice's "id" attribute

    if overrideN:
        theVoice.id = overrideN
    else:
        nStr: t.Optional[str] = elem.get('n')
        if nStr is not None:
            theVoice.id = nStr
        else:
            raise MeiAttributeError(_MISSING_VOICE_ID)

    return theVoice


def appChoiceLayerChildrenFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    chosen: t.Optional[Element] = chooseSubElement(elem)
    if chosen is None:
        return []

    # iterate all immediate children
    theList: t.List[Music21Object] = _processEmbeddedElements(
        chosen.iterfind('*'),
        layerChildrenTagToFunction,
        chosen.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    return theList

def passThruEditorialLayerChildrenFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    # iterate all immediate children
    theList: t.List[Music21Object] = _processEmbeddedElements(
        elem.iterfind('*'),
        layerChildrenTagToFunction,
        elem.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    return theList


def appChoiceStaffItemsFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[
    t.Tuple[
        str,
        t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
        Music21Object
    ]
]:
    chosen: t.Optional[Element] = chooseSubElement(elem)
    if chosen is None:
        return []

    # iterate all immediate children
    theList: t.List[
        t.Tuple[
            str,
            t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
            Music21Object
        ]
    ] = (
        _processEmbeddedElements(
            chosen.iterfind('*'),
            staffItemsTagToFunction,
            chosen.tag,
            activeMeter,
            spannerBundle,
            otherInfo)
    )

    return theList


def passThruEditorialStaffItemsFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[
    t.Tuple[
        str,
        t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
        Music21Object
    ]
]:
    # iterate all immediate children
    theList: t.List[
        t.Tuple[
            str,
            t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
            Music21Object
        ]
    ] = (
        _processEmbeddedElements(
            elem.iterfind('*'),
            staffItemsTagToFunction,
            elem.tag,
            activeMeter,
            spannerBundle,
            otherInfo)
    )

    return theList


def appChoiceNoteChildrenFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    chosen: t.Optional[Element] = chooseSubElement(elem)
    if chosen is None:
        return []

    # iterate all immediate children
    theList: t.List[Music21Object] = _processEmbeddedElements(
        chosen.iterfind('*'),
        noteChildrenTagToFunction,
        chosen.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    return theList


def passThruEditorialNoteChildrenFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    # iterate all immediate children
    theList: t.List[Music21Object] = _processEmbeddedElements(
        elem.iterfind('*'),
        noteChildrenTagToFunction,
        elem.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    return theList


def appChoiceChordChildrenFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    chosen: t.Optional[Element] = chooseSubElement(elem)
    if chosen is None:
        return []

    # iterate all immediate children
    theList: t.List[Music21Object] = _processEmbeddedElements(
        chosen.iterfind('*'),
        chordChildrenTagToFunction,
        chosen.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    return theList


def passThruEditorialChordChildrenFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    # iterate all immediate children
    theList: t.List[Music21Object] = _processEmbeddedElements(
        elem.iterfind('*'),
        chordChildrenTagToFunction,
        elem.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    return theList


def appChoiceBeamChildrenFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    chosen: t.Optional[Element] = chooseSubElement(elem)
    if chosen is None:
        return []

    # iterate all immediate children
    theList: t.List[Music21Object] = _processEmbeddedElements(
        chosen.iterfind('*'),
        beamChildrenTagToFunction,
        chosen.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    return theList


def passThruEditorialBeamChildrenFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    # iterate all immediate children
    theList: t.List[Music21Object] = _processEmbeddedElements(
        elem.iterfind('*'),
        beamChildrenTagToFunction,
        elem.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    return theList


def appChoiceTupletChildrenFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    chosen: t.Optional[Element] = chooseSubElement(elem)
    if chosen is None:
        return []

    # iterate all immediate children
    theList: t.List[Music21Object] = _processEmbeddedElements(
        chosen.iterfind('*'),
        tupletChildrenTagToFunction,
        chosen.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    return theList


def passThruEditorialTupletChildrenFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    # iterate all immediate children
    theList: t.List[Music21Object] = _processEmbeddedElements(
        elem.iterfind('*'),
        tupletChildrenTagToFunction,
        elem.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    return theList


def appChoiceBTremChildrenFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    chosen: t.Optional[Element] = chooseSubElement(elem)
    if chosen is None:
        return []

    # iterate all immediate children
    theList: t.List[Music21Object] = _processEmbeddedElements(
        chosen.iterfind('*'),
        bTremChildrenTagToFunction,
        chosen.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    return theList


def passThruEditorialBTremChildrenFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    # iterate all immediate children
    theList: t.List[Music21Object] = _processEmbeddedElements(
        elem.iterfind('*'),
        bTremChildrenTagToFunction,
        elem.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    return theList


def appChoiceFTremChildrenFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    chosen: t.Optional[Element] = chooseSubElement(elem)
    if chosen is None:
        return []

    # iterate all immediate children
    theList: t.List[Music21Object] = _processEmbeddedElements(
        chosen.iterfind('*'),
        fTremChildrenTagToFunction,
        chosen.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    return theList


def passThruEditorialFTremChildrenFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[Music21Object]:
    # iterate all immediate children
    theList: t.List[Music21Object] = _processEmbeddedElements(
        elem.iterfind('*'),
        fTremChildrenTagToFunction,
        elem.tag,
        activeMeter,
        spannerBundle,
        otherInfo
    )

    return theList


def staffFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> t.List[stream.Voice]:
    '''
    <staff> A group of equidistant horizontal lines on which notes are placed in order to
    represent pitch or a grouping element for individual 'strands' of notes, rests, etc. that may
    or may not actually be rendered on staff lines; that is, both diastematic and non-diastematic
    signs.

    In MEI 2013: pg.444 (458 in PDF) (MEI.shared module)

    :param elem: The ``<staff>`` element to process.
    :type elem: :class:`~xml.etree.ElementTree.Element`
    :returns: The :class:`Voice` classes corresponding to the ``<layer>`` tags in ``elem``.
    :rtype: list of :class:`music21.stream.Voice`

    **Attributes/Elements Implemented:**

    - <layer> contained within

    **Attributes Ignored:**

    - @xml:id

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base)
    - att.declaring (@decls)
    - att.facsimile (@facs)
    - att.staff.log (@def) (att.meterconformance (@metcon))
    - att.staff.vis (att.visibility (@visible))
    - att.staff.gesatt.staff.anl (all)

    **Contained Elements not Implemented:**

    - MEI.cmn: ossia
    - MEI.critapp: app
    - MEI.edittrans: (all)
    - MEI.shared: annot pb sb scoreDef staffDef
    - MEI.text: div
    - MEI.usersymbols: anchoredText curve line symbol
    '''
    # mapping from tag name to our converter function
    layerTagName: str = f'{MEI_NS}layer'
    tagToFunction: t.Dict[str, t.Callable[
        [Element,
            t.Optional[meter.TimeSignature],
            spanner.SpannerBundle,
            t.Dict[str, str]],
        t.Any]
    ] = {
    }

    # Initialize otherInfo['currentImpliedAltersPerStaff'] from the keysig for this staff.
    # This staff's currentImpliedAlters will be updated as notes/ornaments with visual
    # accidentals are seen in this layer.
    staffNStr: str = otherInfo.get('staffNumberForNotes', '')
    if staffNStr:
        currKeyPerStaff: t.Dict = otherInfo.get('currKeyPerStaff', {})
        currentKey: t.Optional[t.Union[key.Key, key.KeySignature]] = (
            currKeyPerStaff.get(staffNStr, None)
        )
        updateStaffKeyAndAltersWithNewKey(staffNStr, currentKey, otherInfo)

    layers: t.List[stream.Voice] = []

    # track the @n values given to layerFromElement()
    currentNValue: str = '1'

    # iterate all immediate children
    for eachTag in elem.iterfind('*'):
        if layerTagName == eachTag.tag:
            layers.append(layerFromElement(
                eachTag, activeMeter, spannerBundle, otherInfo, overrideN=currentNValue
            ))
            currentNValue = f'{int(currentNValue) + 1}'  # inefficient, but we need a string
        elif eachTag.tag in tagToFunction:
            # NB: this won't be tested until there's something in tagToFunction
            layers.append(
                tagToFunction[eachTag.tag](eachTag, activeMeter, spannerBundle, otherInfo)
            )
        elif eachTag.tag not in _IGNORE_UNPROCESSED:
            environLocal.warn(_UNPROCESSED_SUBELEMENT.format(eachTag.tag, elem.tag))

    return layers


def _correctMRestDurs(
    staves: t.Dict[str, t.Union[stream.Measure, bar.Repeat]],
    targetQL: OffsetQL
):
    '''
    Helper function for measureFromElement(), not intended to be used elsewhere. It's a separate
    function only (1) to reduce duplication, and (2) to improve testability.

    Iterate the imported objects of <layer> elements in the <staff> elements in a <measure>,
    detecting those with the "m21wasMRest" attribute and setting their duration to "targetLength."

    The "staves" argument should be a dictionary where the values are Measure objects with at least
    one Voice object inside.

    The "targetQL" argument should be the duration of the measure.

    Nothing is returned; the duration of affected objects is modified in-place.
    '''
    for eachMeasure in staves.values():
        if not isinstance(eachMeasure, stream.Measure):
            continue

        for eachVoice in eachMeasure:
            if not isinstance(eachVoice, stream.Stream):
                continue

            correctionOffset: OffsetQL = 0.
            for eachObject in eachVoice:
                if correctionOffset != 0:
                    # Anything after an mRest needs its offset corrected.
                    # What could that be, you ask?  How about a clef change?
                    newOffset = opFrac(eachObject.offset + correctionOffset)
                    eachVoice.setElementOffset(eachObject, newOffset)

                if hasattr(eachObject, 'm21wasMRest'):
                    correctionOffset = (
                        opFrac(correctionOffset + (targetQL - eachObject.quarterLength))
                    )
                    eachObject.quarterLength = targetQL
                    del eachObject.m21wasMRest


def _makeBarlines(
    elem: Element,
    staves: t.Dict[str, t.Union[stream.Measure, bar.Repeat]]
) -> t.Dict[str, t.Union[stream.Measure, bar.Repeat]]:
    '''
    This is a helper function for :func:`measureFromElement`, made independent only to improve
    that function's ease of testing.

    Given a <measure> element and a dictionary with the :class:`Measure` objects that have already
    been processed, change the barlines of the :class:`Measure` objects in accordance with the
    element's @left and @right attributes.

    :param :class:`~xml.etree.ElementTree.Element` elem: The ``<measure>`` tag to process.
    :param dict staves: Dictionary where keys are @n attributes and values are corresponding
        :class:`~music21.stream.Measure` objects.
    :returns: The ``staves`` dictionary with properly-set barlines.
    :rtype: dict
    '''
    leftStr: t.Optional[str] = elem.get('left')
    if leftStr is not None:
        bars = _barlineFromAttr(leftStr)
        if isinstance(bars, tuple):
            # this means @left was "rptboth"
            bars = bars[1]

        for eachMeasure in staves.values():
            if isinstance(eachMeasure, stream.Measure):
                eachMeasure.leftBarline = deepcopy(bars)

    rightStr: t.Optional[str] = elem.get('right', 'single')
    bars = _barlineFromAttr(rightStr)
    if isinstance(bars, tuple):
        # this means @right was "rptboth"
        staves['next @left'] = bars[1]
        bars = bars[0]

    for eachMeasure in staves.values():
        if isinstance(eachMeasure, stream.Measure):
            eachMeasure.rightBarline = deepcopy(bars)

    return staves


def _canBeOnRest(expr: expressions.Expression) -> bool:
    if isinstance(expr, expressions.Fermata):
        return True
    return False

def _addTimestampedExpressions(
    staves: t.Dict[str, t.Union[stream.Measure, bar.Repeat]],
    tsExpressions: t.List[t.Tuple[t.List[str], OffsetQL, expressions.Expression]],
    otherInfo: t.Dict[str, t.Any]
):
    clonedExpression: expressions.Expression

    for staffNs, offset, expression in tsExpressions:
        canBeOnRest: bool = _canBeOnRest(expression)
        isDelayedTurn: bool = (
            isinstance(expression, expressions.Turn)
            and hasattr(expression, 'mei_delayed')
            and expression.mei_delayed == 'true'  # type: ignore
        )

        for i, staffN in enumerate(staffNs):
            doneWithStaff: bool = False
            eachMeasure: t.Union[stream.Measure, bar.Repeat] = staves[staffN]
            if not isinstance(eachMeasure, stream.Measure):
                continue

            nearestPrevNoteInStaff: t.Optional[note.GeneralNote] = None
            offsetFromNearestPrevNote: t.Optional[OffsetQL] = None
            staffForNearestNote: t.Optional[str] = None
            for eachMObj in eachMeasure:
                if not isinstance(eachMObj, (stream.Stream, bar.Barline)):
                    continue

                if isinstance(eachMObj, bar.Barline):
                    if isinstance(expression, expressions.Fermata):
                        if i == 0:
                            if eachMObj.pause is None:
                                eachMObj.pause = expression
                            else:
                                environLocal.warn(
                                    'Extra Barline fermata ignored; music21 only allows one'
                                )
                        else:
                            if eachMObj.pause is None:
                                clonedExpression = deepcopy(expression)
                                eachMObj.pause = clonedExpression
                            else:
                                environLocal.warn(
                                    'Extra Barline fermata ignored; music21 only allows one'
                                )
                        doneWithStaff = True
                        break

                if isinstance(eachMObj, stream.Stream):
                    eachVoice: stream.Stream = eachMObj
                    for eachObject in eachVoice:
                        if canBeOnRest and not isinstance(eachObject, note.GeneralNote):
                            continue
                        if not canBeOnRest and not isinstance(eachObject, note.NotRest):
                            continue

                        if not isDelayedTurn:
                            if eachObject.offset == offset:
                                if i == 0:
                                    expression = updateExpression(
                                        expression, eachObject, staffN, otherInfo
                                    )
                                    eachObject.expressions.append(expression)
                                else:
                                    clonedExpression = deepcopy(expression)
                                    clonedExpression = updateExpression(
                                        clonedExpression, eachObject, staffN, otherInfo
                                    )
                                    eachObject.expressions.append(clonedExpression)

                                doneWithStaff = True
                                break
                        else:
                            # If expression is a delayed turn, look to see if eachObject
                            # is the nearest previous object so far in this staff.
                            if eachObject.offset < offset:
                                offsetFromThisPrevNote: OffsetQL = opFrac(
                                    offset - eachObject.offset
                                )
                                if (offsetFromNearestPrevNote is None
                                        or offsetFromNearestPrevNote > offsetFromThisPrevNote):
                                    offsetFromNearestPrevNote = opFrac(offset - eachObject.offset)
                                    nearestPrevNoteInStaff = eachObject
                                    staffForNearestNote = staffN

                    if doneWithStaff:
                        break

            if not doneWithStaff:
                # We didn't find any place for the expression at the offset in this staff.
                # But if it is a delayed turn, then we should use the note with the closest
                # offset LESS than the expression's offset.  Which we have stashed off in
                # "nearestPrevNoteInStaff".
                if nearestPrevNoteInStaff is not None:
                    if t.TYPE_CHECKING:
                        # Since nearestPrevNoteInStaff is set, so is staffForNearestNote
                        assert staffForNearestNote is not None
                    expression = updateExpression(
                        expression, nearestPrevNoteInStaff, staffForNearestNote, otherInfo
                    )
                    nearestPrevNoteInStaff.expressions.append(expression)
                else:
                    environLocal.warn(
                        f'No obj at offset {offset} found in staff {staffN}'
                        f'for timestamped {expression.classes[0]}.'
                    )


def _tstampToOffset(
    tstamp: str,
    activeMeter: t.Optional[meter.TimeSignature]
) -> OffsetQL:
    beat: float
    try:
        beat = float(tstamp)
    except (TypeError, ValueError):
        # warn about malformed tstamp, assuming 0.0
        return 0.0

    return _beatToOffset(beat, activeMeter)


def _beatToOffset(beat: float, activeMeter: t.Optional[meter.TimeSignature]) -> OffsetQL:
    # beat is expressed in beats, as expressed in the written time signature.
    # We will need to offset it (beats are 1-based, offsets are 0-based) and convert
    # it to quarter notes (OffsetQL)

    # make it 0-based
    beat -= 1.0

    activeMeterDenom: int = 4  # if no activeMeter, pretend it's <something> / 4
    if activeMeter is not None:
        activeMeterDenom = activeMeter.denominator

    # convert to whole notes
    beat /= float(activeMeterDenom)

    # convert to quarter notes
    beat *= 4.0

    return opFrac(beat)

def _tstamp2ToMeasSkipAndOffset(
    tstamp2: str,
    activeMeter: t.Optional[meter.TimeSignature]
) -> t.Tuple[int, OffsetQL]:
    measSkip: int
    beat: float
    offset: OffsetQL

    tstamp2Patt: str = r'(([0-9]+)m\s*\+\s*)?([0-9]+(\.?[0-9]*)?)'
    m = re.match(tstamp2Patt, tstamp2)
    if m is None:
        # warn about malformed tstamp2, assuming '0m+0.000'
        return 0, 0.

    try:
        if not m.group(1):
            # no 'Nm+' at all
            measSkip = 0
        else:
            measSkip = int(m.group(2))
        if not m.group(4):
            # no '.5000', m.group(3) is an integer
            beat = float(int(m.group(3)))
        else:
            beat = float(m.group(3))
    except:  # pylint: disable=bare-except
        # warn about malformed tstamp2, assuming '0m+0.000'
        return 0, 0.

    offset = _beatToOffset(beat, activeMeter)
    return measSkip, offset


def _tstampsToOffset1AndMeasSkipAndOffset2(
    tstamp: str,
    tstamp2: str,
    activeMeter: t.Optional[meter.TimeSignature]
) -> t.Tuple[OffsetQL, int, OffsetQL]:
    offset: OffsetQL = _tstampToOffset(tstamp, activeMeter)
    measSkip: int
    offset2: OffsetQL
    measSkip, offset2 = _tstamp2ToMeasSkipAndOffset(tstamp2, activeMeter)

    return offset, measSkip, offset2


_NOTE_UNICODE_CHAR_TO_NOTE_NAME: t.Dict[str, str] = {
    '\uE1D0': 'breve',    # noteDoubleWhole
    '\uE1D1': 'breve',    # noteDoubleWholeSquare
    '\uE1D2': 'whole',    # noteWhole
    '\uE1D3': 'half',     # noteHalfUp
    '\uE1D4': 'half',     # noteHalfDown
    '\uE1D5': 'quarter',  # noteQuarterUp
    '\uE1D6': 'quarter',  # noteQuarterDown
    '\uE1D7': 'eighth',   # note8thUp
    '\uE1D8': 'eighth',   # note8thDown
    '\uE1D9': '16th',     # note16thUp
    '\uE1DA': '16th',     # note16thDown
    '\uE1DB': '32nd',     # ...
    '\uE1DC': '32nd',
    '\uE1DD': '64th',
    '\uE1DE': '64th',
    '\uE1DF': '128th',
    '\uE1E0': '128th',
    '\uE1E1': '256th',
    '\uE1E2': '256th',
    '\uE1E3': '512th',
    '\uE1E4': '512th',    # ...
    '\uE1E5': '1024th',   # note1024thUp
    '\uE1E6': '1024th',   # note1024thDown
}

_METRONOME_MARK_PATTERN: str = r'^((.*?)\s*)([^=\s])\s*=\s*(\d+\.?\d*)[\s]*$'
def _getBPMInfo(
    text: str
) -> t.Tuple[t.Optional[str], t.Optional[str], t.Optional[int]]:
    # takes strings like "Andante M.M. 𝅗𝅥 = 128" and returns
    # 'Andante M.M.', '𝅗𝅥', and 128 (but only if the first match
    # is actually a note symbol from the SMuFL range (0xE1D0 - 0xE1EF).
    m = re.search(_METRONOME_MARK_PATTERN, text)
    if m is None:
        return None, None, None

    tempoName: t.Optional[str] = m.group(2)
    noteChar: t.Optional[str] = m.group(3)
    notesPerMinute: t.Optional[str] = m.group(4)

    if notesPerMinute is None or noteChar is None:
        return None, None, None

    if noteChar in _NOTE_UNICODE_CHAR_TO_NOTE_NAME:
        return tempoName, noteChar, int(float(notesPerMinute) + 0.5)

    return None, None, None


def chooseSubElement(appOrChoice: Element) -> t.Optional[Element]:
    chosen: t.Optional[Element] = None
    if appOrChoice.tag == f'{MEI_NS}app':
        # choose 'lem' (lemma) if present, else first 'rdg' (reading)
        chosen = appOrChoice.find(f'{MEI_NS}lem')
        if chosen is None:
            chosen = appOrChoice.find(f'{MEI_NS}rdg')
        return chosen

    if appOrChoice.tag == f'{MEI_NS}choice':
        # choose 'corr' (correction) if present,
        # else 'reg' (regularization) if present,
        # else first sub-element.
        chosen = appOrChoice.find(f'{MEI_NS}corr')
        if chosen is None:
            chosen = appOrChoice.find(f'{MEI_NS}reg')
        if chosen is None:
            chosen = appOrChoice.find('*')
        return chosen

    environLocal.warn('Internal error: chooseSubElement expects <app> or <choice>')
    return chosen  # None, if we get here


_EDITORIAL_ELEMENTS: t.Tuple[str, ...] = (
    f'{MEI_NS}abbr',
    f'{MEI_NS}add',
    f'{MEI_NS}app',
    f'{MEI_NS}choice',
    f'{MEI_NS}corr',
    f'{MEI_NS}damage',
    f'{MEI_NS}del',
    f'{MEI_NS}expan',
    f'{MEI_NS}orig',
    f'{MEI_NS}ref',
    f'{MEI_NS}reg',
    f'{MEI_NS}restore',
    f'{MEI_NS}sic',
    f'{MEI_NS}subst',
    f'{MEI_NS}supplied',
    f'{MEI_NS}unclear',
)

_IGNORED_EDITORIALS: t.Tuple[str, ...] = (
    f'{MEI_NS}abbr',
    f'{MEI_NS}del',
    f'{MEI_NS}ref',
    f'{MEI_NS}restore',  # I could support restore with a special FromElement API
)                        # that reverses the meaning of del and add

_PASSTHRU_EDITORIALS: t.Tuple[str, ...] = (
    f'{MEI_NS}add',
    f'{MEI_NS}corr',
    f'{MEI_NS}damage',
    f'{MEI_NS}expan',
    f'{MEI_NS}orig',
    f'{MEI_NS}reg',
    f'{MEI_NS}sic',
    f'{MEI_NS}subst',
    f'{MEI_NS}supplied',
    f'{MEI_NS}unclear',
)

_CHOOSING_EDITORIALS: t.Tuple[str, ...] = (
    f'{MEI_NS}app',
    f'{MEI_NS}choice',
)


def octaveFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any],
) -> t.Tuple[
        str,
        t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
        t.Optional[spanner.Ottava]
]:
    offset: OffsetQL = -1.
    measSkip: t.Optional[int] = None
    offset2: t.Optional[OffsetQL] = None

    ottavaLocalId = elem.get('m21Ottava', '')
    if not ottavaLocalId:
        environLocal.warn('no Ottava created in octave preprocessing')
        return ('', (-1., None, None), None)
    ottava: t.Optional[spanner.Spanner] = (
        safeGetSpannerByIdLocal(ottavaLocalId, spannerBundle)
    )
    if ottava is None:
        environLocal.warn('no Ottava found from octave preprocessing')
        return ('', (-1., None, None), None)

    if t.TYPE_CHECKING:
        assert isinstance(ottava, spanner.Ottava)

    staffNStr: str = elem.get('staff', '')
    if not staffNStr:
        # get it from start note in ottava (should already be there)
        startObj: t.Optional[Music21Object] = ottava.getFirst()
        if startObj is not None and hasattr(startObj, 'mei_staff'):
            staffNStr = startObj.mei_staff  # type: ignore
    if not staffNStr:
        staffNStr = '1'  # best we can do, hope it's ok

    startId: str = elem.get('startid', '')
    tstamp: str = elem.get('tstamp', '')
    endId: str = elem.get('endid', '')
    tstamp2: str = elem.get('tstamp2', '')
    if not tstamp2 and not endId:
        environLocal.warn('missing @tstamp2/@endid in <octave> element')
        return ('', (-1., None, None), None)
    if not tstamp and not startId:
        environLocal.warn('missing @tstamp/@startid in <octave> element')
        return ('', (-1., None, None), None)
    if not startId:
        ottava.mei_needs_start_anchor = True  # type: ignore
    if not endId:
        ottava.mei_needs_end_anchor = True  # type: ignore
    if tstamp:
        offset = _tstampToOffset(tstamp, activeMeter)
    if tstamp2:
        measSkip, offset2 = _tstamp2ToMeasSkipAndOffset(tstamp2, activeMeter)

    return staffNStr, (offset, measSkip, offset2), ottava


def arpegFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any],
) -> t.Tuple[
        str,
        t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
        t.Optional[expressions.ArpeggioMark]
]:
    if elem.get('ignore_in_arpegFromElement') == 'true':
        return '', (-1., None, None), None

    staffNStr: str = elem.get('staff', '1')
    tstamp: t.Optional[str] = elem.get('tstamp')
    if tstamp is None:
        environLocal.warn('missing @tstamp/@startid/@plist in <arpeg> element')
        return '', (-1., None, None), None

    offset: OffsetQL = _tstampToOffset(tstamp, activeMeter)

    arrow: str = elem.get('arrow', '')
    order: str = elem.get('order', '')
    arpeggioType: str = _ARPEGGIO_ARROW_AND_ORDER_TO_ARPEGGIOTYPE.get(
        (arrow, order),
        'normal'
    )

    arp = expressions.ArpeggioMark(arpeggioType=arpeggioType)
    return staffNStr, (offset, None, None), arp


def trillFromElement(
        elem: Element,
        activeMeter: t.Optional[meter.TimeSignature],
        spannerBundle: spanner.SpannerBundle,
        otherInfo: t.Dict[str, t.Any],
) -> t.List[
    t.Tuple[
        str,
        t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
        t.Optional[t.Union[expressions.Trill, expressions.TrillExtension]]
    ]
]:
    output: t.List[
        t.Tuple[
            str,
            t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
            t.Optional[t.Union[expressions.Trill, expressions.TrillExtension]]
        ]
    ] = []

    # If no @staff, presume it is staff 1
    staffNStr = elem.get('staff', '')

    startId: str = elem.get('startid', '')
    tstamp: str = elem.get('tstamp', '')
    place: str = elem.get('place', 'place_unspecified')
    offset: t.Optional[OffsetQL] = None

    if elem.get('ignore_trill_in_trillFromElement') != 'true':
        # this happens if we need a trill, but are missing @startid
        if not tstamp:
            environLocal.warn('missing @tstamp/@startid in <trill> element')
            return [('', (-1., None, None), None)]

        accidupper: str = elem.get('accidupper', '')
        accidlower: str = elem.get('accidlower', '')

        # Make a placeholder Trill, we'll interpret later (once we've found
        # the note/chord) to figure out WholeStepTrill vs HalfStepTrill.
        trill = expressions.Trill()

        if place and place != 'place_unspecified':
            trill.placement = place
        else:
            trill.placement = None  # type: ignore

        if accidupper:
            trill.mei_accidupper = accidupper  # type: ignore
        if accidlower:
            trill.mei_accidlower = accidlower  # type: ignore

        offset = _tstampToOffset(tstamp, activeMeter)
        trillStaffNStr: str = staffNStr
        if not trillStaffNStr:
            trillStaffNStr = '1'
        output.append((trillStaffNStr, (offset, None, None), trill))

    if elem.get('ignore_trill_extension_in_trillFromElement') != 'true':
        # this happens if we need a trill extension, but are missing @startid, @endid, or both
        trillExtLocalId = elem.get('m21TrillExtension', '')
        if not trillExtLocalId:
            environLocal.warn('no TrillExtension created in trill preprocessing')
            return [('', (-1., None, None), None)]
        trillExt: t.Optional[spanner.Spanner] = (
            safeGetSpannerByIdLocal(trillExtLocalId, spannerBundle)
        )
        if trillExt is None:
            environLocal.warn('no TrillExtension found from trill preprocessing')
            return [('', (-1., None, None), None)]

        if t.TYPE_CHECKING:
            assert isinstance(trillExt, expressions.TrillExtension)

        endId: str = elem.get('endid', '')
        tstamp2: str = elem.get('tstamp2', '')
        if not tstamp2 and not endId:
            environLocal.warn('missing @tstamp2/@endid in <trill> element')
            return [('', (-1., None, None), None)]
        if not tstamp and not startId:
            environLocal.warn('missing @tstamp/@startid in <trill> element')
            return [('', (-1., None, None), None)]
        if not startId:
            trillExt.mei_needs_start_anchor = True  # type: ignore
        if not endId:
            trillExt.mei_needs_end_anchor = True  # type: ignore

        measSkip: t.Optional[int] = None
        offset2: t.Optional[OffsetQL] = None
        if tstamp:
            offset = _tstampToOffset(tstamp, activeMeter)
        if tstamp2:
            measSkip, offset2 = _tstamp2ToMeasSkipAndOffset(tstamp2, activeMeter)

        trillExtStaffNStr: str = staffNStr
        if not trillExtStaffNStr:
            # get it from start note in trillExt (should already be there)
            startObj: t.Optional[Music21Object] = trillExt.getFirst()
            if startObj is not None and hasattr(startObj, 'mei_staff'):
                trillExtStaffNStr = startObj.mei_staff  # type: ignore
        if not trillExtStaffNStr:
            trillExtStaffNStr = '1'  # best we can do, hope it's ok

        output.append((trillExtStaffNStr, (offset, measSkip, offset2), trillExt))

    if not output:
        return [('', (-1., None, None), None)]
    return output


def mordentFromElement(
        elem: Element,
        activeMeter: t.Optional[meter.TimeSignature],
        spannerBundle: spanner.SpannerBundle,
        otherInfo: t.Dict[str, t.Any],
) -> t.List[
    t.Tuple[
        str,
        t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
        t.Optional[expressions.GeneralMordent]
    ]
]:
    output: t.List[
        t.Tuple[
            str,
            t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
            t.Optional[expressions.GeneralMordent]
        ]
    ] = []

    # If no @staff, presume it is staff 1
    staffNStr = elem.get('staff', '1')

    tstamp: str = elem.get('tstamp', '')
    form: str = elem.get('form', '')
    place: str = elem.get('place', 'place_unspecified')
    offset: t.Optional[OffsetQL] = None

    if elem.get('ignore_mordent_in_mordentFromElement') != 'true':
        # this happens if we need a mordent, but are missing @startid
        if not tstamp:
            environLocal.warn('missing @tstamp/@startid in <mordent> element')
            return [('', (-1., None, None), None)]

        accidupper: str = elem.get('accidupper', '')
        accidlower: str = elem.get('accidlower', '')

        # Make a placeholder Mordent or InvertedMordent; we'll interpret later
        # (once we've found the note/chord) to figure out HalfStep vs WholeStep.
        if not form:
            if accidupper:
                form = 'upper'
            elif accidlower:
                form = 'lower'
            else:
                form = 'upper'  # default

        mordent: expressions.GeneralMordent
        if form == 'upper':
            # music21 calls an upper mordent (i.e that goes up from the main note)
            # an InvertedMordent
            mordent = expressions.InvertedMordent()
        else:
            mordent = expressions.Mordent()

        # m21 mordents might not have placement... sigh...
        # But if I set it, it _will_ get exported to MusicXML (ha!).
        if place and place != 'place_unspecified':
            mordent.placement = place  # type: ignore
        else:
            mordent.placement = None  # type: ignore

        if accidupper:
            mordent.mei_accidupper = accidupper  # type: ignore
        if accidlower:
            mordent.mei_accidlower = accidlower  # type: ignore

        offset = _tstampToOffset(tstamp, activeMeter)
        output.append((staffNStr, (offset, None, None), mordent))

    if not output:
        return [('', (-1., None, None), None)]
    return output


def turnFromElement(
        elem: Element,
        activeMeter: t.Optional[meter.TimeSignature],
        spannerBundle: spanner.SpannerBundle,
        otherInfo: t.Dict[str, t.Any],
) -> t.List[
    t.Tuple[
        str,
        t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
        t.Optional[expressions.Turn]
    ]
]:
    output: t.List[
        t.Tuple[
            str,
            t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
            t.Optional[expressions.Turn]
        ]
    ] = []

    # If no @staff, presume it is staff 1
    staffNStr = elem.get('staff', '1')

    tstamp: str = elem.get('tstamp', '')
    form: str = elem.get('form', '')
    theType: str = elem.get('type', '')
    delayed: str = elem.get('delayed', 'false')
    place: str = elem.get('place', 'place_unspecified')
    offset: t.Optional[OffsetQL] = None

    if elem.get('ignore_turn_in_turnFromElement') != 'true':
        # this happens if we need a turn, but are missing @startid
        if not tstamp:
            environLocal.warn('missing @tstamp/@startid in <turn> element')
            return [('', (-1., None, None), None)]

        if delayed == 'true':
            environLocal.warn(_UNIMPLEMENTED_IMPORT_WITH.format('<turn>', '@delayed="true"'))
            environLocal.warn('@delayed will be ignored')

        accidupper: str = elem.get('accidupper', '')
        accidlower: str = elem.get('accidlower', '')

        # Make a placeholder Turn or InvertedTurn; we'll interpret later
        # (once we've found the note/chord) to figure out HalfStep vs WholeStep.
        # ACTUALLY, music21 has some shortcomings here, that interpretation
        # won't really happen until I have music21 issue #1507 completed.
        if not form:
            if theType == 'slashed':
                form = 'lower'
            else:
                form = 'upper'  # default

        turn: expressions.Turn
        if form == 'upper':
            turn = expressions.Turn()
        else:
            turn = expressions.InvertedTurn()

        if place and place != 'place_unspecified':
            turn.placement = place
        else:
            turn.placement = None  # type: ignore


        if accidupper:
            turn.mei_accidupper = accidupper  # type: ignore
        if accidlower:
            turn.mei_accidlower = accidlower  # type: ignore

        if delayed == 'true':
            # we said we would ignore @delayed, and we do, but we have a little
            # extra searching to do to find the right note to put delayed turns
            # on, and we can't ignore _that_.
            turn.mei_delayed = 'true'  # type: ignore

        offset = _tstampToOffset(tstamp, activeMeter)
        output.append((staffNStr, (offset, None, None), turn))

    if not output:
        return [('', (-1., None, None), None)]
    return output


def hairpinFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any],
) -> t.Tuple[
        str,
        t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
        t.Optional[dynamics.DynamicWedge]
]:
    # If no @staff, presume it is staff 1
    staffNStr = elem.get('staff', '1')
    offsets: t.Tuple[OffsetQL, int, OffsetQL]
    dw: dynamics.DynamicWedge

    # @tstamp/@tstamp2 only for the moment.
    tstamp: t.Optional[str] = elem.get('tstamp')
    if tstamp is None:
        environLocal.warn('missing @tstamp in <hairpin> element')
        return '', (-1., None, None), None
    tstamp2: t.Optional[str] = elem.get('tstamp2')
    if tstamp2 is None:
        environLocal.warn('missing @tstamp2 in <hairpin> element')
        return '', (-1., None, None), None

    offsets = _tstampsToOffset1AndMeasSkipAndOffset2(tstamp, tstamp2, activeMeter)

    form: str = elem.get('form', '')
    if form == 'cres':
        dw = dynamics.Crescendo()
    elif form == 'dim':
        dw = dynamics.Diminuendo()
    else:
        environLocal.warn(f'invalid @form = "{form}" in <hairpin>')
        return '', (-1., None, None), None

    place: t.Optional[str] = elem.get('place')
    if place:
        if place == 'above':
            dw.placement = 'above'
        elif place == 'below':
            dw.placement = 'below'
        elif place == 'between':
            dw.placement = 'below'
            dw.style.alignVertical = 'middle'  # type: ignore
        else:
            environLocal.warn(f'invalid @place = "{place}" in <hairpin>')

    dw.mei_needs_start_anchor = True  # type: ignore
    dw.mei_needs_end_anchor = True  # type: ignore
    spannerBundle.append(dw)
    return staffNStr, offsets, dw


def dynamFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any],
) -> t.Tuple[
    str,
    t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
    t.Optional[dynamics.Dynamic]
]:
    staffNStr: str
    offsets: t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]]
    dynamObj: dynamics.Dynamic

    # first parse as a <dir> giving a TextExpression with style,
    # then try to derive dynamic info from that.
    teWithStyle: t.Optional[expressions.TextExpression]
    staffNStr, offsets, teWithStyle = (
        dirFromElement(elem, activeMeter, spannerBundle, otherInfo)
    )
    if teWithStyle is None:
        return '', (-1., None, None), None

    if t.TYPE_CHECKING:
        assert isinstance(teWithStyle.style, style.TextStyle)

    text: str = teWithStyle.content
    dynamObj = dynamics.Dynamic(text)
    if teWithStyle.hasStyleInformation:
        dynamObj.style = teWithStyle.style
    else:
        # Undo music21's default Dynamic absolute positioning
        dynamObj.style.absoluteX = None
        dynamObj.style.absoluteY = None

    if teWithStyle.placement is not None:
        dynamObj.placement = teWithStyle.placement

    return staffNStr, offsets, dynamObj


def tempoFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any],
) -> t.Tuple[
    str,
    t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
    t.Optional[tempo.TempoIndication]
]:
    tempoObj: tempo.TempoIndication  # either TempoText or MetronomeMark

    # first parse as a <dir> giving a TextExpression with style,
    # then try to derive tempo info from that.
    staffNStr: str
    offsets: t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]]
    teWithStyle: t.Optional[expressions.TextExpression]
    staffNStr, offsets, teWithStyle = (
        dirFromElement(elem, activeMeter, spannerBundle, otherInfo)
    )
    if teWithStyle is None:
        return '', (-1., None, None), None

    # default tempo placement should be above
    if teWithStyle.placement is None:
        teWithStyle.placement = 'above'

    if t.TYPE_CHECKING:
        assert isinstance(teWithStyle.style, style.TextStyle)

    # default tempo text style should be bold
    if not teWithStyle.hasStyleInformation:
        teWithStyle.style.fontStyle = 'bold'
    elif teWithStyle.style.fontWeight is None and teWithStyle.style.fontStyle is None:
        teWithStyle.style.fontStyle = 'bold'

    pendingMidiBPMStr: str = otherInfo.pop('pending scoredef@midi.bpm', '')
    midiBPMStr: str = elem.get('midi.bpm', '')
    if not midiBPMStr:
        # only use the pending one if it's useful.  We pop it out of otherInfo either way.
        midiBPMStr = pendingMidiBPMStr
    midiBPM: t.Optional[int] = None
    if midiBPMStr:
        try:
            midiBPM = int(float(midiBPMStr))
        except (TypeError, ValueError):
            pass

    # Note that we have to make a TempoText from teWithStyle first, since
    # MetronomeMark won't take text=TextExpression.
    tempoObj = tempo.TempoText()
    tempoObj.setTextExpression(teWithStyle)

    tempoObj = tempo.MetronomeMark(
        text=tempoObj,
        number=midiBPM,
        referent=None  # implies quarter note
    )

    # Avoid adding any extra "𝅗𝅥 = 128" text to the display of this metronome mark
    tempoObj.numberImplicit = True

    # work around bug in MetronomeMark.text setter where style is not linked
    # when text is a TempoText
    tempoObj.style = teWithStyle.style

    # transfer placement to the metronome mark
    tempoObj.placement = teWithStyle.placement

    return staffNStr, offsets, tempoObj


def _glyphNameToUnicodeChar(name: str) -> str:
    # name is things like 'noteQuarterUp', which can be looked up
    return SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get(name, '')


def _glyphNumToUnicodeChar(num: str) -> str:
    # num can be '#xNNNN' or 'U+NNNN'
    pattern: str = r'^(#x|U\+)([A-F0-9]+)$'
    m = re.match(pattern, num)
    if m is None:
        return ''
    return chr(int(m.group(2), 16))


def textFromElem(elem: Element) -> t.Tuple[str, t.Dict[str, str]]:
    styleDict: t.Dict[str, str] = {}
    text: str = ''
    if elem.text:
        if elem.text[0] != '\n' or not elem.text.isspace():
            text += elem.text

    for el in elem.iterfind('*'):
        # do whatever is appropriate given el.tag (<rend> for example)
        if el.tag == f'{MEI_NS}rend':
            # music21 doesn't currently support changing style in the middle of a TextExpression,
            # so we just grab the first ones we see and save them off to use.
            fontStyle: str = el.get('fontstyle', '')
            fontWeight: str = el.get('fontweight', '')
            fontFamily: str = el.get('fontfam', '')
            justify: str = el.get('halign', '')
            if fontStyle:
                styleDict['fontStyle'] = fontStyle
            if fontWeight:
                styleDict['fontWeight'] = fontWeight
            if fontFamily:
                styleDict['fontFamily'] = fontFamily
            if justify:
                styleDict['justify'] = justify

        elif el.tag in _CHOOSING_EDITORIALS:
            subEl: t.Optional[Element] = chooseSubElement(el)
            if subEl is None:
                continue
            el = subEl
        elif el.tag in _PASSTHRU_EDITORIALS:
            # for now assume all we care about here is the text/tail of these subElements
            for subEl in el.iterfind('*'):
                if subEl.text:
                    if subEl.text[0] != '\n' or not subEl.text.isspace():
                        text += subEl.text
                if subEl.tail:
                    if subEl.tail[0] != '\n' or not subEl.tail.isspace():
                        text += subEl.tail
        elif el.tag == f'{MEI_NS}lb':
            text += '\n'
        elif el.tag == f'{MEI_NS}symbol':
            # This is a glyph in the SMUFL font (@glyph.auth="smufl"), with a
            # particular name (@glyph.name="metNoteQuarterUp").  Sometimes
            # instead of @glyph.name, there is @glyph.num, which is just the
            # utf16 code as 'U+NNNN' or '#xNNNN'.
            glyphAuth: str = el.get('glyph.auth', '')
            if not glyphAuth or glyphAuth == 'smufl':
                glyphName: str = el.get('glyph.name', '')
                glyphNum: str = el.get('glyph.num', '')
                if glyphNum:
                    text += _glyphNumToUnicodeChar(glyphNum)
                elif glyphName:
                    text += _glyphNameToUnicodeChar(glyphName)

        # grab the text from el
        elText: str
        elStyleDict: t.Dict[str, str]
        elText, elStyleDict = textFromElem(el)
        text += elText
        styleDict.update(elStyleDict)

        # grab the text between this el and the next el
        if el.tail:
            if el.tail[0] != '\n' or not el.tail.isspace():
                text += el.tail

    return text, styleDict

def dirFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any],
) -> t.Tuple[
    str,
    t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
    t.Optional[expressions.TextExpression]
]:
    # returns (staffNStr, (offset, None, None), te)

    # If no @staff, presume it is staff 1; I've seen <tempo> without @staff, for example.
    staffNStr = elem.get('staff', '1')
    offset: OffsetQL
    te: expressions.TextExpression

    typeAtt: t.Optional[str] = elem.get('type')
    if typeAtt is not None and typeAtt == 'fingering':
        return '', (-1., None, None), None

    # @tstamp is required for now, someday we'll be able to derive offsets from @startid
    tstamp: t.Optional[str] = elem.get('tstamp')
    if tstamp is None:
        environLocal.warn('missing @tstamp in <dir> element')
        return '', (-1., None, None), None

    offset = _tstampToOffset(tstamp, activeMeter)

    # technically not always legal, but I've seen it in <dynam>, so support it here for everyone.
    enclose: t.Optional[str] = elem.get('enclose')

    fontStyle: t.Optional[str] = None
    fontWeight: t.Optional[str] = None
    fontFamily: t.Optional[str] = None
    justify: t.Optional[str] = None
    text: str
    styleDict: t.Dict[str, str]

    text, styleDict = textFromElem(elem)
    text = html.unescape(text)
    text = text.strip()

    fontStyle = styleDict.get('fontStyle', None)
    fontWeight = styleDict.get('fontWeight', None)
    fontFamily = styleDict.get('fontFamily', None)
    justify = styleDict.get('justify', None)

    if enclose is not None:
        if enclose == 'paren':
            text = '( ' + text + ' )'
        elif enclose == 'brack':
            text = '[ ' + text + ' ]'

    te = expressions.TextExpression(text)

    if t.TYPE_CHECKING:
        assert isinstance(te.style, style.TextStyle)

#     if elem.tag == f'{MEI_NS}dir':
#         # Match Verovio's default: <dir> with no fontStyle should be italic
#         if fontStyle is None:
#             fontStyle = 'italic'
    if fontStyle is not None or fontWeight is not None:
        te.style.fontStyle = (
            _m21FontStyleFromMeiFontStyleAndWeight(fontStyle, fontWeight)
        )
    if fontFamily is not None:
        te.style.fontFamily = fontFamily
    if justify is not None:
        te.style.justify = justify

    place: t.Optional[str] = elem.get('place')
    if place:
        if place == 'above':
            te.placement = 'above'
        elif place == 'below':
            te.placement = 'below'
        elif place == 'between':
            te.placement = 'below'
            te.style.alignVertical = 'middle'
        else:
            environLocal.warn(f'invalid @place = "{place}" in <dir>')
    return staffNStr, (offset, None, None), te


def fermataFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any],
) -> t.Tuple[
    str,
    t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
    t.Optional[expressions.Fermata]
]:
    # returns (staffNStr, (offset, None, None), fermata)

    # if the fermata element has already been processed in _ppFermatas, ignore it here
    if elem.get('ignore_in_fermataFromElement') == 'true':
        return '', (-1., None, None), None

    # If no @staff, presume it is staff 1; I've seen <tempo> without @staff, for example.
    staffNStr = elem.get('staff', '1')
    offset: OffsetQL
    fermata: expressions.Fermata

    # tstamp is required, since it doesn't have a @startid (if it had a @startid, we
    # would have processed it in _ppFermatas, and ignored it here).
    tstamp: t.Optional[str] = elem.get('tstamp')
    if tstamp is None:
        environLocal.warn('<fermata> element is missing @tstamp and @startid')
        return '', (-1., None, None), None

    offset = _tstampToOffset(tstamp, activeMeter)

    fermataPlace: str = elem.get('place', 'above')  # default @place is "above"
    fermataForm: str = elem.get('form', '')
    fermataShape: str = elem.get('shape', '')

    fermata = expressions.Fermata()
    if fermataPlace == 'above':
        fermata.type = 'upright'
    elif fermataPlace == 'below':
        fermata.type = 'inverted'

    if fermataForm == 'norm':
        fermata.type = 'upright'
    elif fermataForm == 'inv':
        fermata.type = 'inverted'

    if fermataShape == 'angular':
        fermata.shape = 'angled'
    elif fermataShape == 'square':
        fermata.shape = 'square'

    return staffNStr, (offset, None, None), fermata


def _m21FontStyleFromMeiFontStyleAndWeight(
    meiFontStyle: t.Optional[str],
    meiFontWeight: t.Optional[str]
) -> t.Optional[str]:
    if meiFontStyle is None:
        meiFontStyle = 'normal'
    if meiFontWeight is None:
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
    return None

def measureFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any],
    backupNum: int,
    expectedNs: t.Iterable[str]
) -> t.Dict[str, t.Union[stream.Measure, bar.Repeat]]:
    '''
    <measure> Unit of musical time consisting of a fixed number of note-values of a given type, as
    determined by the prevailing meter, and delimited in musical notation by two bar lines.

    In MEI 2013: pg.365 (379 in PDF) (MEI.cmn module)

    :param elem: The ``<measure>`` element to process.
    :type elem: :class:`~xml.etree.ElementTree.Element`
    :param int backupNum: A fallback value for the resulting
        :class:`~music21.stream.Measure` objects' number attribute.
    :param expectedNs: A list of the expected @n attributes for the <staff> tags in this <measure>.
        If an expected <staff> isn't in the <measure>, it will be created with a full-measure rest.
    :type expectedNs: iterable of str
    :param activeMeter: The :class:`~music21.meter.TimeSignature` active in this <measure>. This is
        used to adjust the duration of an <mRest> that was given without a @dur attribute.
    :returns: A dictionary where keys are the @n attributes for <staff> tags found in this
        <measure>, and values are :class:`~music21.stream.Measure` objects that should be appended
        to the :class:`~music21.stream.Part` instance with the value's @n attributes.
    :rtype: dict of :class:`~music21.stream.Measure`, with one exception.

    .. note:: When the right barline is set to ``'rptboth'`` in MEI, it requires adjusting the left
        barline of the following <measure>. If this happens, a :class:`Repeat` object is assigned
        to the ``'next @left'`` key in the returned dictionary.

    **Attributes/Elements Implemented:**

    - contained elements: <staff> and <staffDef>
    - @right and @left (att.measure.log)
    - @n (att.common)

    **Attributes Ignored:**

    - @xml:id (att.id)
    - <slur> and <tie> contained within. These spanners will usually be attached to their starting
      and ending notes with @xml:id attributes, so it's not necessary to process them when
      encountered in a <measure>. Furthermore, because the possibility exists for cross-measure
      slurs and ties, we can't guarantee we'll be able to process all spanners until all
      spanner-attachable objects are processed. So we manage these tags at a higher level.

    **Attributes/Elements in Testing:** none

    **Attributes not Implemented:**

    - att.common (@label, @xml:base)
    - att.declaring (@decls)
    - att.facsimile (@facs)
    - att.typed (@type, @subtype)
    - att.pointing (@xlink:actuate, @xlink:role, @xlink:show, @target, @targettype, @xlink:title)
    - att.measure.log (att.meterconformance.bar (@metcon, @control))
    - att.measure.vis (all)
    - att.measure.ges (att.timestamp.performed (@tstamp.ges, @tstamp.real))
    - att.measure.anl (all)

    **Contained Elements not Implemented:**

    - MEI.cmn: arpeg beamSpan bend breath fermata gliss hairpin harpPedal octave ossia pedal reh
               tupletSpan
    - MEI.cmnOrnaments: mordent trill turn
    - MEI.critapp: app
    - MEI.edittrans: add choice corr damage del gap handShift orig reg restore sic subst supplied
                     unclear
    - MEI.harmony: harm
    - MEI.lyrics: lyrics
    - MEI.midi: midi
    - MEI.shared: annot dir dynam pb phrase sb tempo
    - MEI.text: div
    - MEI.usersymbols: anchoredText curve line symbol
    '''
    # staves is mostly Measures, but can contain a single Repeat, as well
    staves: t.Dict[str, t.Union[stream.Measure, bar.Repeat]] = {}

    # for staff-specific objects processed before the corresponding staff
    # key1 is @n, key2 is 'meter', 'key', 'instrument', etc
    stavesWaitingFromStaffDef: t.Dict[str, t.Dict[str, Music21Object]] = {}

    # for staffItem objects processed before the corresponding staff
    # key is @staff, value is a list of tuple(offsets, object)
    stavesWaitingFromStaffItem: t.Dict[
        str,
        t.List[
            t.Tuple[
                t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],  # offsets
                Music21Object
            ]
        ]
    ] = {}

    # spanner end GeneralNotes we are waiting to insert in the correct measure
    pendingSpannerEnds: t.Optional[
        t.List[
            t.Tuple[str, spanner.Spanner, int, OffsetQL]
        ]
    ] = otherInfo.pop('pendingSpannerEnds', None)

    # spanner end GeneralNotes we are STILL waiting to insert after processing this measure
    newPendingSpannerEnds: t.Optional[
        t.List[
            t.Tuple[str, spanner.Spanner, int, OffsetQL]
        ]
    ] = None

    spannerObj: spanner.Spanner
    startObj: Music21Object
    endObj: Music21Object

    # Check if we can insert any of the pendingSpannerEnds in this measure.
    # For any we can't, put them in newPendingSpannerEnds so we can try again next measure.
    if pendingSpannerEnds:
        for pendingSpannerEnd in pendingSpannerEnds:
            staffNStr: str = pendingSpannerEnd[0]
            spannerObj = pendingSpannerEnd[1]
            measSkip: int = pendingSpannerEnd[2]
            offset: OffsetQL = pendingSpannerEnd[3]
            if t.TYPE_CHECKING:
                assert isinstance(spannerObj, spanner.Spanner)

            measSkip -= 1
            if measSkip < 0:
                environLocal.warn('pendingSpannerEnd skipped too many measures')
                measSkip = 0

            if measSkip == 0:
                # do the spannerEnd, it's in this Measure
                if M21Utilities.m21SupportsSpannerAnchor():
                    # pylint: disable=no-member
                    endObj = spanner.SpannerAnchor()  # type: ignore
                    # pylint: enable=no-member
                else:
                    endObj = note.GeneralNote(duration=duration.Duration(0.))
                spannerObj.addSpannedElements(endObj)
                if staffNStr not in stavesWaitingFromStaffItem:
                    stavesWaitingFromStaffItem[staffNStr] = []
                stavesWaitingFromStaffItem[staffNStr].append(
                    ((offset, None, None), endObj)
                )
            else:
                # spannerEnd is still pending (albeit with decremented measSkip)
                if newPendingSpannerEnds is None:
                    newPendingSpannerEnds = []
                newPendingSpannerEnds.append(
                    (staffNStr, spannerObj, measSkip, offset)
                )
        if newPendingSpannerEnds:
            otherInfo['pendingSpannerEnds'] = newPendingSpannerEnds

    # mapping from tag name to our converter function
    staffTag: str = f'{MEI_NS}staff'
    staffDefTag: str = f'{MEI_NS}staffDef'

    measureNum: t.Union[str, int] = elem.get('n', backupNum)

    # track the bar's duration
    maxBarDuration: t.Optional[OffsetQL] = None

    # iterate all immediate children
    for eachElem in elem.iterfind('*'):
        nStr: t.Optional[str] = eachElem.get('n')
        if staffTag == eachElem.tag:
            if nStr is None:
                raise MeiElementError(_STAFF_MUST_HAVE_N)

            otherInfo['staffNumberForNotes'] = nStr
            staves[nStr] = stream.Measure(
                staffFromElement(eachElem, activeMeter, spannerBundle, otherInfo),
                number=measureNum
            )
            thisBarDuration: OffsetQL = staves[nStr].duration.quarterLength
            if maxBarDuration is None or maxBarDuration < thisBarDuration:
                maxBarDuration = thisBarDuration
            otherInfo.pop('staffNumberForNotes')

        elif staffDefTag == eachElem.tag:
            if nStr is None:
                environLocal.warn(_UNIMPLEMENTED_IMPORT_WITHOUT.format('<staffDef>', '@n'))
            else:
                otherInfo['staffNumberForDef'] = nStr
                stavesWaitingFromStaffDef[nStr] = staffDefFromElement(
                    eachElem, spannerBundle, otherInfo
                )
                otherInfo.pop('staffNumberForDef')

        elif eachElem.tag in staffItemsTagToFunction:
            offsets: t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]]
            m21Obj: t.Optional[Music21Object]
            triple: t.Tuple[
                str,
                t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
                Music21Object
            ]
            triple = staffItemsTagToFunction[eachElem.tag](
                eachElem, activeMeter, spannerBundle, otherInfo
            )

            # Sometimes staffItemsTagToFunction actually returns a _list_ of
            # (staffNStr, offsets, m21Obj) triples instead of just one such triple.
            triples: t.List[
                t.Tuple[
                    str,
                    t.Tuple[t.Optional[OffsetQL], t.Optional[int], t.Optional[OffsetQL]],
                    Music21Object
                ]
            ]
            if isinstance(triple, list):
                triples = triple
            else:
                triples = [triple]

            for staffNStr, offsets, m21Obj in triples:
                if m21Obj is not None:
                    if staffNStr not in stavesWaitingFromStaffItem:
                        stavesWaitingFromStaffItem[staffNStr] = []
                    offset1: t.Optional[OffsetQL] = offsets[0]
                    measSkip2: t.Optional[int] = offsets[1]
                    offset2: t.Optional[OffsetQL] = offsets[2]

                    if isinstance(m21Obj, spanner.Spanner):
                        spannerObj = m21Obj
                        # If it needs start or end notes make them now.
                        needsStartAnchor: bool = False
                        needsEndAnchor: bool = False
                        if hasattr(m21Obj, 'mei_needs_start_anchor'):
                            needsStartAnchor = spannerObj.mei_needs_start_anchor  # type: ignore
                            del spannerObj.mei_needs_start_anchor  # type: ignore
                        if hasattr(m21Obj, 'mei_needs_end_anchor'):
                            needsEndAnchor = spannerObj.mei_needs_end_anchor  # type: ignore
                            del spannerObj.mei_needs_end_anchor  # type: ignore

                        if needsStartAnchor:
                            if M21Utilities.m21SupportsSpannerAnchor():
                                # pylint: disable=no-member
                                startObj = spanner.SpannerAnchor()  # type: ignore
                                # pylint: enable=no-member
                            else:
                                startObj = note.GeneralNote(duration=duration.Duration(0.))
                            spannerObj.addSpannedElements(startObj)
                            stavesWaitingFromStaffItem[staffNStr].append(
                                ((offset1, None, None), startObj)
                            )
                        if needsEndAnchor:
                            if measSkip2 == 0:
                                # do the endObj as well, it's in this same Measure
                                if M21Utilities.m21SupportsSpannerAnchor():
                                    # pylint: disable=no-member
                                    endObj = spanner.SpannerAnchor()  # type: ignore
                                    # pylint: enable=no-member
                                else:
                                    endObj = note.GeneralNote(duration=duration.Duration(0.))
                                spannerObj.addSpannedElements(endObj)
                                stavesWaitingFromStaffItem[staffNStr].append(
                                    ((offset2, None, None), endObj)
                                )
                            else:
                                # endNote has to wait for a subsequent measure
                                if otherInfo.get('pendingSpannerEnds', None) is None:
                                    otherInfo['pendingSpannerEnds'] = []
                                otherInfo['pendingSpannerEnds'].append(
                                    (staffNStr, spannerObj, measSkip2, offset2)
                                )
                    else:
                        # not a spanner
                        stavesWaitingFromStaffItem[staffNStr].append(
                            (offsets, m21Obj)
                        )

        elif eachElem.tag not in _IGNORE_UNPROCESSED:
            environLocal.warn(_UNPROCESSED_SUBELEMENT.format(eachElem.tag, elem.tag))

    # Process objects from a <staffDef>...
    # We must process them now because, if we did it in the loop above, the respective <staff> may
    # not be processed before the <staffDef>.
    for whichN, eachDict in stavesWaitingFromStaffDef.items():
        for eachObj in eachDict.values():
            # We must insert() these objects because a <staffDef> signals its changes for the
            # *start* of the <measure> in which it appears.
            staveN = staves[whichN]
            if t.TYPE_CHECKING:
                assert isinstance(staveN, stream.Measure)
            staveN.insert(0, eachObj)

    # a list of (offset, expression) pairs containing all the expressions (e.g.
    # fermatas, arpeggios) that have @timestamp instead of @startid/@plist (the
    # ones with @startid/@plist have already been processed).
    tsExpressions: t.List[t.Tuple[t.List[str], OffsetQL, expressions.Expression]] = []

    # Process objects from staffItems (e.g. Direction, Fermata, etc)
    for whichStaff, eachList in stavesWaitingFromStaffItem.items():
        for (eachOffset, eachMeasSkip2, eachOffset2), eachObj in eachList:
            # parse whichStaff, which might be '1', '2', '1 2', etc
            staffNs: t.List[str] = re.findall(r'[\d]+', whichStaff)
            if not staffNs:
                raise MeiAttributeError(
                    _STAFFITEM_MUST_HAVE_VALID_STAFF.format(eachObj.classes[0], whichStaff)
                )
            if (eachOffset is not None
                    and isinstance(eachObj, (
                        expressions.Fermata,
                        expressions.ArpeggioMark,
                        expressions.Trill,
                        expressions.GeneralMordent,
                        expressions.Turn))):
                # save off to process later, skip for now
                tsExpressions.append((staffNs, eachOffset, eachObj))
                continue

            if eachMeasSkip2 is not None or eachOffset2 is not None:
                # This should never happen, because we will have already split such a thing
                # into two objects with a simple offset and put the two of them in a spanner.
                raise MeiInternalError('StaffItem spanner seen unexpectedly')

            spanners: t.List[spanner.Spanner] = eachObj.getSpannerSites()
            isSpannedObject: bool = bool(spanners)
            betweenTwoStaves: bool = False
            if len(staffNs) == 2:
                if (eachObj.hasStyleInformation
                        and hasattr(eachObj.style, 'alignVertical')
                        and eachObj.style.alignVertical == 'middle'):  # type: ignore
                    betweenTwoStaves = True
                else:
                    # TODO: what if it's also in a slur? We should look for any spanners
                    # TODO: with alignVertical, or something.
                    if (spanners
                            and spanners[0].hasStyleInformation
                            and hasattr(spanners[0].style, 'alignVertical')
                            and spanners[0].style.alignVertical == 'middle'):  # type: ignore
                        betweenTwoStaves = True

            if len(staffNs) == 1:
                staffNumStr = staffNs[0]
                staveN = staves[staffNumStr]
                if t.TYPE_CHECKING:
                    assert isinstance(staveN, stream.Measure)
                staveN.insert(eachOffset, eachObj)

            elif betweenTwoStaves:
                # Put it in the first staff (it will go below it)
                staffNumStr = staffNs[0]
                staveN = staves[staffNumStr]
                if t.TYPE_CHECKING:
                    assert isinstance(staveN, stream.Measure)
                staveN.insert(eachOffset, eachObj)

            elif isSpannedObject:
                # last chance for spanned objects, put in top staff (we can't duplicate them)
                staffNumStr = staffNs[0]
                staveN = staves[staffNumStr]
                if t.TYPE_CHECKING:
                    assert isinstance(staveN, stream.Measure)
                staveN.insert(eachOffset, eachObj)

            else:
                # we need to put eachObj in each listed staff (deepcopy them!)
                for i, staffNumStr in enumerate(staffNs):
                    staveN = staves[staffNumStr]
                    if t.TYPE_CHECKING:
                        assert isinstance(staveN, stream.Measure)
                    if i == 0:
                        staveN.insert(eachOffset, eachObj)
                        continue

                    clonedObj: Music21Object = deepcopy(eachObj)
                    staveN.insert(eachOffset, clonedObj)

    # create rest-filled measures for expected parts that had no <staff> tag in this <measure>
    for eachN in expectedNs:
        if eachN not in staves:
            restVoice = stream.Voice([note.Rest(quarterLength=maxBarDuration)])
            restVoice.id = '1'
            # just in case (e.g., when all the other voices are <mRest>)
            restVoice[0].m21wasMRest = True
            staves[eachN] = stream.Measure([restVoice], number=measureNum)

    # First search for Rest objects created by an <mRest> element that didn't have @dur set. This
    # will only work in cases where not all of the parts are resting. However, it avoids a more
    # time-consuming search later.
    if (maxBarDuration == _DUR_ATTR_DICT[None]
            and activeMeter is not None
            and maxBarDuration != activeMeter.barDuration.quarterLength):
        # In this case, all the staves have <mRest> elements without a @dur.
        _correctMRestDurs(staves, activeMeter.barDuration.quarterLength)
    else:
        # In this case, some or none of the staves have an <mRest> element without a @dur.
        if t.TYPE_CHECKING:
            assert maxBarDuration is not None
        _correctMRestDurs(staves, maxBarDuration)

    # assign left and right barlines
    staves = _makeBarlines(elem, staves)

    # take the timestamped fermatas, etc, and find notes/barlines to put them on
    _addTimestampedExpressions(staves, tsExpressions, otherInfo)

    return staves


def sectionScoreCore(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any],
    allPartNs: t.Tuple[str, ...],
    nextMeasureLeft: t.Optional[bar.Repeat] = None,
    backupMeasureNum: int = 0,
) -> t.Tuple[
        t.Dict[str, t.List[t.Union[Music21Object, t.List[Music21Object]]]],
        t.Optional[meter.TimeSignature],
        t.Optional[bar.Repeat],
        int]:
    '''
    This function is the "core" of both :func:`sectionFromElement` and :func:`scoreFromElement`,
    since both elements are treated quite similarly (though not identically). It is also used to
    process 'ending' elements (which are a sort of section, I guess).  It's a separate and
    shared function to reduce code duplication and increase ease of testing. It's a "public"
    function to help spread the burden of API documentation complexity: while the parameters and
    return values are described in this function, the compliance with the MEI Guidelines is
    described in both :func:`sectionFromElement` and :func:`scoreFromElement`, as expected.

    **Required Parameters**

    :param elem: The <section> or <score> element to process.
    :type elem: :class:`xml.etree.ElementTree.Element`
    :param allPartNs: A tuple of the expected @n attributes for the <staff> tags in this
        <section>. This tells the function how many parts there are and what @n values they use.
    :type allPartNs: tuple of str
    :param spannerBundle: This :class:`SpannerBundle` holds the :class:`~music21.spanner.Slur`
        objects created during pre-processing. The slurs are attached to their respective
        :class:`Note` and :class:`Chord` objects as they are processed.
    :type spannerBundle: :class:`music21.spanner.SpannerBundle`

    **Optional Keyword Parameters**

    The following parameters are all optional, and must be specified as a keyword argument (i.e.,
    you specify the parameter name before its value).

    :param activeMeter: The :class:`~music21.meter.TimeSignature` active at the start of this
        <section> or <score>. This is updated automatically as the music is processed, and the
        :class:`TimeSignature` active at the end of the element is returned.
    :type activeMeter: :class:`music21.meter.TimeSignature`
    :param nextMeasureLeft: The @left attribute to use for the next <measure> element encountered.
        This is used for situations where one <measure> element specified a @right attribute that
        must be imported by music21 as *both* the right barline of one measure and the left barline
        of the following; at the moment this is only @rptboth, which requires a :class:`Repeat` in
        both cases.
    :type nextMeasureLeft: :class:`music21.bar.Barline` or :class:`music21.bar.Repeat`
    :param backupMeasureNum: In case a <measure> element is missing its @n attribute,
        :func:`measureFromElement` will use this automatically-incremented number instead. The
        ``backupMeasureNum`` corresponding to the final <measure> in this <score> or <section> is
        returned from this function.
    :type backupMeasureNum: int
    :returns: Four-tuple with a dictionary of results, the new value of ``activeMeter``, the new
        value of ``nextMeasureLeft``, and the new value of ``backupMeasureNum``.
    :rtype: (dict, :class:`~music21.meter.TimeSignature`, :class:`~music21.bar.Barline`, int)

    **Return Value**

    In short, it's ``parsed``, ``activeMeter``, ``nextMeasureLeft``, ``backupMeasureNum``.

    - ``'parsed'`` is a dictionary where the keys are the values in ``allPartNs`` and the values are
        a list of all the :class:`Measure` objects in that part, as found in this <section> or
        <score>.
    - ``'activeMeter'`` is the :class:`~music21.meter.TimeSignature` in effect at the end of this
        <section> or <score>.
    - ``'nextMeasureLeft'`` is the value that should be
        assigned to the :attr:`leftBarline` attribute
        of the first :class:`Measure` found in the next <section>. This will almost always be None.
    - ``'backupMeasureNum'`` is equal to the ``backupMeasureNum`` argument plus the number of
        <measure> elements found in this <score> or <section>.
    '''
    # pylint: disable=too-many-nested-blocks
    # ^^^ -- was not required at time of contribution

    # TODO: replace the returned 4-tuple with a namedtuple

    # NOTE: "activeMeter" holds the TimeSignature object that's currently active; it's used in the
    # loop below to help determine the proper duration of a full-measure rest. It must persist
    # between <section> elements, so it's a parameter for this function.

    scoreTag: str = f'{MEI_NS}score'
    sectionTag: str = f'{MEI_NS}section'
    endingTag: str = f'{MEI_NS}ending'
    measureTag: str = f'{MEI_NS}measure'
    scoreDefTag: str = f'{MEI_NS}scoreDef'
    staffDefTag: str = f'{MEI_NS}staffDef'

    # hold the music21.stream.Part that we're building
    parsed: t.Dict[str, t.List[t.Union[Music21Object, t.List[Music21Object]]]] = {
        n: [] for n in allPartNs
    }
    # hold things that belong in the following "Thing" (either Measure or Section)
    inNextThing: t.Dict[str, t.List[t.Union[Music21Object, t.List[Music21Object]]]] = {
        n: [] for n in allPartNs
    }
    pendingInNextThing = otherInfo.pop('pending inNextThing', None)
    if pendingInNextThing is not None:
        inNextThing.update(pendingInNextThing)

    topPartN: str = otherInfo.get('topPartN', '')
    if topPartN == '' and allPartNs:
        topPartN = allPartNs[0]

    for eachElem in elem.iterfind('*'):
        # only process <measure> elements if this is a <section> or <ending>
        if measureTag == eachElem.tag and elem.tag in (sectionTag, endingTag):
            backupMeasureNum += 1

            # Make a new measureInfo to pass in for each measure.
            # It will contain the current otherInfo contents, but
            # any measure-specific info will be cleared here.
            measureInfo: t.Dict[str, t.Any] = {}
            measureInfo.update(otherInfo)

            # process all the stuff in the <measure>
            measureResult = measureFromElement(
                eachElem, activeMeter, spannerBundle, measureInfo, backupMeasureNum, allPartNs
            )

            # we toss measureInfo to clear the measure-specific stuff, BUT we don't want
            # to clear info['pendingSpannerEnds'] because they need to keep getting passed
            # around until all spanners have ended. So we put it in otherInfo here.
            pendingSpannerEnds = measureInfo.get('pendingSpannerEnds', None)
            if pendingSpannerEnds:
                otherInfo['pendingSpannerEnds'] = pendingSpannerEnds
            else:
                otherInfo.pop('pendingSpannerEnds', None)

            # process and append each part's stuff to the staff
            for eachN in allPartNs:
                measureResultN = measureResult[eachN]
                if t.TYPE_CHECKING:
                    assert isinstance(measureResultN, stream.Measure)
                # insert objects specified in the immediately-preceding <scoreDef>
                for eachThing in inNextThing[eachN]:
                    measureResultN.insert(0, eachThing)
                inNextThing[eachN] = []
                # if we got a left-side barline from the previous measure, use it
                if nextMeasureLeft is not None:
                    measureResultN.leftBarline = deepcopy(nextMeasureLeft)
                # add this Measure to the Part
                parsed[eachN].append(measureResultN)
            # if we got a barline for the next <measure>
            if 'next @left' in measureResult:
                nl = measureResult['next @left']
                if t.TYPE_CHECKING:
                    assert isinstance(nl, bar.Repeat)
                nextMeasureLeft = nl
            else:
                nextMeasureLeft = None

        elif scoreDefTag == eachElem.tag:
            localResult = scoreDefFromElement(
                eachElem, spannerBundle, otherInfo
            )
            for topPartObject in localResult['top-part objects']:
                if t.TYPE_CHECKING:
                    # because 'top-part objects' is a list of objects
                    assert isinstance(topPartObject, Music21Object)
                inNextThing[topPartN].append(topPartObject)

            for allPartObject in localResult['all-part objects']:
                if t.TYPE_CHECKING:
                    # because 'all-part objects' is a list of objects
                    assert isinstance(allPartObject, Music21Object)

                newKey: t.Optional[t.Union[key.Key, key.KeySignature]] = None
                if isinstance(allPartObject, key.KeySignature):
                    newKey = allPartObject

                if isinstance(allPartObject, meter.TimeSignature):
                    activeMeter = allPartObject

                for i, eachN in enumerate(allPartNs):
                    if i == 0:
                        to_insert = allPartObject
                    else:
                        # a single Music21Object should not exist in multiple parts
                        to_insert = deepcopy(allPartObject)
                    inNextThing[eachN].append(to_insert)

                    if newKey is not None:
                        updateStaffKeyAndAltersWithNewKey(eachN, newKey, otherInfo)

            for eachN in allPartNs:
                if eachN in localResult:
                    resultNDict = localResult[eachN]
                    if t.TYPE_CHECKING:
                        # because 'n' is a dict[str, Music21Object]
                        assert isinstance(resultNDict, dict)
                    for eachObj in resultNDict.values():
                        if isinstance(eachObj, meter.TimeSignature):
                            activeMeter = eachObj
                        inNextThing[eachN].append(eachObj)

        elif staffDefTag == eachElem.tag:
            nStr: t.Optional[str] = eachElem.get('n')
            if nStr is not None:
                otherInfo['staffNumberForDef'] = nStr
                for eachObj in staffDefFromElement(
                    eachElem, spannerBundle, otherInfo
                ).values():
                    if isinstance(eachObj, meter.TimeSignature):
                        activeMeter = eachObj
                    inNextThing[nStr].append(eachObj)
                otherInfo.pop('staffNumberForDef')
            else:
                # At the moment, to process this here, we need an @n on the <staffDef>. A document
                # may have a still-valid <staffDef> if the <staffDef> has an @xml:id with which
                # <staff> elements may refer to it.
                environLocal.warn(_UNIMPLEMENTED_IMPORT_WITHOUT.format('<staffDef>', '@n'))

        elif eachElem.tag in (sectionTag, endingTag):
            # NOTE: same as scoreFE() (except the name of "inNextThing")
            localParsed, activeMeter, nextMeasureLeft, backupMeasureNum = sectionFromElement(
                eachElem,
                activeMeter,
                spannerBundle,
                otherInfo,
                allPartNs,
                nextMeasureLeft,
                backupMeasureNum)
            for eachN, eachList in localParsed.items():
                # NOTE: "eachList" is a list of objects that will become a music21 Part.
                #
                # first: if there were objects from a previous <scoreDef> or <staffDef>, we need to
                #        put those into the first Measure object we encounter in this Part
                # TODO: this is where the Instruments get added
                # TODO: I think "eachList" really means "each list that will become a Part"
                if inNextThing[eachN]:
                    # we have to put Instrument objects just before the Measure to which they apply
                    theInstr = None
                    theInstrI = None
                    for i, eachInsertion in enumerate(inNextThing[eachN]):
                        if isinstance(eachInsertion, instrument.Instrument):
                            theInstr = eachInsertion
                            theInstrI = i
                            break

                    # Put the Instrument right in front, then remove it from "inNextThing" so it
                    # doesn't show up twice.
                    if theInstr:
                        if t.TYPE_CHECKING:
                            assert theInstrI is not None
                        eachList.insert(0, theInstr)
                        del inNextThing[eachN][theInstrI]

                    for eachMeasure in eachList:
                        # NOTE: "eachMeasure" is one of the things that will be in the Part,
                        # which are probably but not necessarily Measures
                        if isinstance(eachMeasure, stream.Stream):
                            # NOTE: ... but now eachMeasure is virtually guaranteed to be a Measure
                            for eachInsertion in inNextThing[eachN]:
                                eachMeasure.insert(0.0, eachInsertion)
                            break
                    inNextThing[eachN] = []

                # Then we can append the objects in this Part to the dict of all parsed objects, but
                # NOTE that this is different for <section> and <score>.
                if elem.tag in (sectionTag, endingTag):
                    # First make a RepeatBracket if this is an <ending>.
                    rb: t.Optional[spanner.RepeatBracket] = None
                    if endingTag == eachElem.tag:
                        # make the RepeatBracket for the ending
                        bracketNStr: t.Optional[str] = eachElem.get('n')
                        n: int = 0
                        if bracketNStr is not None:
                            try:
                                n = int(bracketNStr)
                            except:  # pylint: disable=bare-except
                                pass
                        rb = spanner.RepeatBracket(number=n)

                    # This is a <section> or <ending>, which is nested in a <section>.
                    # We must "flatten" everything so it doesn't cause a disaster when
                    # we try to make a Part out of it.
                    for eachMeas in eachList:
                        parsed[eachN].append(eachMeas)
                        # If we have a RepeatBracket (i.e. we're in an <ending>), and
                        # this is a Measure, put it in the RepeatBracket.
                        if rb is not None and isinstance(eachMeas, stream.Measure):
                            rb.addSpannedElements(eachMeas)

                    # If we have a RepeatBracket, it should end up in the Part as well.
                    if rb is not None:
                        parsed[eachN].append(rb)

                elif scoreTag == elem.tag:
                    # If this is a <score>, we can just append the result of each <section> to the
                    # list that will become the Part.

                    # we know eachList is not a list of lists, it's just a list or an object,
                    # so disable mypy checking the type.
                    parsed[eachN].append(eachList)  # type: ignore

        elif eachElem.tag not in _IGNORE_UNPROCESSED:
            environLocal.warn(_UNPROCESSED_SUBELEMENT.format(eachElem.tag, elem.tag))

    # TODO: write the <section @label=""> part

    # if there's anything left in "inNextThing", stash it off for the _next_ measure or section
    otherInfo['pending inNextThing'] = inNextThing

    return parsed, activeMeter, nextMeasureLeft, backupMeasureNum


def sectionFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any],
    allPartNs: t.Tuple[str, ...],
    nextMeasureLeft: t.Optional[bar.Repeat],
    backupMeasureNum: int
) -> t.Tuple[
        t.Dict[str, t.List[t.Union[Music21Object, t.List[Music21Object]]]],
        t.Optional[meter.TimeSignature],
        t.Optional[bar.Repeat],
        int]:
    '''
    <section> Segment of music data.

    In MEI 2013: pg.432 (446 in PDF) (MEI.shared module)

    .. note:: The parameters and return values are exactly the same for :func:`sectionFromElement`
        and :func:`sectionScoreCore`, so refer to the latter function's documentation for more
        information.

    **Attributes/Elements Implemented:**

    **Attributes Ignored:**

    **Attributes/Elements in Testing:**

    - @label
    - contained <measure>, <scoreDef>, <staffDef>, <section>

    **Attributes not Implemented:**

    - att.common (@n, @xml:base) (att.id (@xml:id))
    - att.declaring (@decls)
    - att.facsimile (@facs)
    - att.typed (@type, @subtype)
    - att.pointing (@xlink:actuate, @xlink:role, @xlink:show, @target, @targettype, @xlink:title)
    - att.section.vis (@restart)
    - att.section.anl (att.common.anl (@copyof, @corresp, @next, @prev, @sameas, @synch)
                                      (att.alignment (@when)))

    **Contained Elements not Implemented:**

    - MEI.critapp: app
    - MEI.edittrans: add choice corr damage del gap handShift orig reg
                     restore sic subst supplied unclear
    - MEI.shared: annot ending expansion pb sb section staff
    - MEI.text: div
    - MEI.usersymbols: anchoredText curve line symbol
    '''
    environLocal.printDebug('*** processing a <section>')
    return sectionScoreCore(elem,
                            activeMeter,
                            spannerBundle,
                            otherInfo,
                            allPartNs,
                            nextMeasureLeft,
                            backupMeasureNum)


def scoreFromElement(
    elem: Element,
    activeMeter: t.Optional[meter.TimeSignature],
    spannerBundle: spanner.SpannerBundle,
    otherInfo: t.Dict[str, t.Any]
) -> stream.Score:
    '''
    <score> Full score view of the musical content.

    In MEI 2013: pg.430 (444 in PDF) (MEI.shared module)

    :param elem: The <score> element to process.
    :type elem: :class:`~xml.etree.ElementTree.Element`
    :param spannerBundle: This :class:`SpannerBundle` holds the :class:`~music21.spanner.Slur`
        objects created during pre-processing. The slurs are attached to their respective
        :class:`Note` and :class:`Chord` objects as they are processed.
    :type spannerBundle: :class:`music21.spanner.SpannerBundle`
    :returns: A completed :class:`~music21.stream.Score` object.

    **Attributes/Elements Implemented:**

    **Attributes Ignored:**

    **Attributes/Elements in Testing:**

    - contained <section>, <scoreDef>, and <staffDef>

    **Attributes not Implemented:**

    - att.common (@label, @n, @xml:base) (att.id (@xml:id))
    - att.declaring (@decls)
    - att.typed (@type, @subtype)
    - att.score.anl (att.common.anl (@copyof, @corresp, @next, @prev, @sameas, @synch)
                                    (att.alignment (@when)))

    **Contained Elements not Implemented:**

    - MEI.critapp: app
    - MEI.edittrans: add choice corr damage del gap handShift orig
                     reg restore sic subst supplied unclear
    - MEI.shared: annot ending pb sb
    - MEI.text: div
    - MEI.usersymbols: anchoredText curve line symbol
    '''

    environLocal.printDebug('*** processing a <score>')
    # That's an outright lie. We're also processing <scoreDef>, <staffDef>, and other elements!

    # Get a tuple of all the @n attributes for the <staff> tags in this score. Each <staff> tag
    # corresponds to what will be a music21 Part.
    allPartNs: t.Tuple[str, ...]
    topPartN: str
    allPartNs, topPartN = allPartsPresent(elem)
    otherInfo['topPartN'] = topPartN

    # This is the actual processing.
    parsed: t.Dict[str, t.List[t.Union[Music21Object, t.List[Music21Object]]]] = (
        sectionScoreCore(
            elem,
            activeMeter,
            spannerBundle,
            otherInfo,
            allPartNs)[0]
    )
    # Convert the dict to a Score
    # We must iterate here over "allPartNs," which preserves the part-order found in the MEI
    # document. Iterating the keys in "parsed" would not preserve the order.
    environLocal.printDebug('*** making the Score')
    thePartList: t.List[stream.Part] = [stream.Part() for _ in range(len(allPartNs))]
    for i, eachN in enumerate(allPartNs):
        # set "atSoundingPitch" so transposition works
        thePartList[i].atSoundingPitch = False
        for eachObj in parsed[eachN]:
            thePartList[i].append(eachObj)
    theScore: stream.Score = stream.Score(thePartList)

    # fill in any Ottava spanners
    for sp in spannerBundle:
        if not isinstance(sp, spanner.Ottava):
            continue
        staffNStr: str = ''
        if hasattr(sp, 'mei_staff'):
            staffNStr = sp.mei_staff  # type: ignore
        if not staffNStr:
            # get it from start note in ottava (should already be there)
            startObj: t.Optional[Music21Object] = sp.getFirst()
            if startObj is not None and hasattr(startObj, 'mei_staff'):
                staffNStr = startObj.mei_staff  # type: ignore
        if not staffNStr:
            staffNStr = '1'  # best we can do, hope it's ok

        staffNs: t.List[str] = staffNStr.split(' ')
        for i, staffN in enumerate(staffNs):
            if i > 0:
                environLocal.warn(
                    'Single Ottava in multiple staves: only filling from the first staff'
                )
                break
            partIdx: int = allPartNs.index(staffN)
            if M21Utilities.m21SupportsInheritAccidentalDisplayAndSpannerFill():
                sp.fillIntermediateSpannedElements(thePartList[partIdx])  # type: ignore
            else:
                # we use our own spanner fill routine, since music21 doesn't have one
                M21Utilities.fillIntermediateSpannedElements(sp, thePartList[partIdx])

    # put spanners in the Score
    theScore.append(list(spannerBundle))

    return theScore


layerChildrenTagToFunction: t.Dict[str, t.Callable[
    [Element,
        t.Optional[meter.TimeSignature],
        spanner.SpannerBundle,
        t.Dict[str, str]],
    t.Any]
] = {
    f'{MEI_NS}app': appChoiceLayerChildrenFromElement,
    f'{MEI_NS}choice': appChoiceLayerChildrenFromElement,
    f'{MEI_NS}add': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}corr': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}damage': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}expan': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}orig': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}reg': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}sic': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}subst': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}supplied': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}unclear': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}clef': clefFromElement,
    f'{MEI_NS}chord': chordFromElement,
    f'{MEI_NS}note': noteFromElement,
    f'{MEI_NS}rest': restFromElement,
    f'{MEI_NS}mRest': mRestFromElement,
    f'{MEI_NS}beam': beamFromElement,
    f'{MEI_NS}tuplet': tupletFromElement,
    f'{MEI_NS}bTrem': bTremFromElement,
    f'{MEI_NS}fTrem': fTremFromElement,
    f'{MEI_NS}space': spaceFromElement,
    f'{MEI_NS}mSpace': mSpaceFromElement,
    f'{MEI_NS}barLine': barLineFromElement,
    f'{MEI_NS}meterSig': timeSigFromElement,
    f'{MEI_NS}keySig': keySigFromElementInLayer,
}

staffItemsTagToFunction: t.Dict[str, t.Callable[
    [Element,
        t.Optional[meter.TimeSignature],
        spanner.SpannerBundle,
        t.Dict[str, str]],
    t.Any]
] = {
    f'{MEI_NS}app': appChoiceStaffItemsFromElement,
    f'{MEI_NS}choice': appChoiceStaffItemsFromElement,
    f'{MEI_NS}add': passThruEditorialStaffItemsFromElement,
    f'{MEI_NS}corr': passThruEditorialStaffItemsFromElement,
    f'{MEI_NS}damage': passThruEditorialStaffItemsFromElement,
    f'{MEI_NS}expan': passThruEditorialStaffItemsFromElement,
    f'{MEI_NS}orig': passThruEditorialStaffItemsFromElement,
    f'{MEI_NS}reg': passThruEditorialStaffItemsFromElement,
    f'{MEI_NS}sic': passThruEditorialStaffItemsFromElement,
    f'{MEI_NS}subst': passThruEditorialStaffItemsFromElement,
    f'{MEI_NS}supplied': passThruEditorialStaffItemsFromElement,
    f'{MEI_NS}unclear': passThruEditorialStaffItemsFromElement,
    #         f'{MEI_NS}anchoredText': anchoredTextFromElement,
    f'{MEI_NS}arpeg': arpegFromElement,
    #         f'{MEI_NS}bracketSpan': bracketSpanFromElement,
    #         f'{MEI_NS}breath': breathFromElement,
    #         f'{MEI_NS}caesura': caesuraFromElement,
    f'{MEI_NS}dir': dirFromElement,
    f'{MEI_NS}dynam': dynamFromElement,
    f'{MEI_NS}fermata': fermataFromElement,
    #         f'{MEI_NS}fing': fingFromElement,
    #         f'{MEI_NS}gliss': glissFromElement,
    f'{MEI_NS}hairpin': hairpinFromElement,
    #         f'{MEI_NS}harm': harmFromElement,
    #         f'{MEI_NS}lv': lvFromElement,
    #        f'{MEI_NS}mNum': mNumFromElement,
    f'{MEI_NS}mordent': mordentFromElement,
    f'{MEI_NS}octave': octaveFromElement,
    #         f'{MEI_NS}pedal': pedalFromElement,
    #         f'{MEI_NS}phrase': phraseFromElement,
    #         f'{MEI_NS}pitchInflection': pitchInflectionFromElement,
    #         f'{MEI_NS}reh': rehFromElement,
    f'{MEI_NS}tempo': tempoFromElement,
    f'{MEI_NS}trill': trillFromElement,
    f'{MEI_NS}turn': turnFromElement,
}

noteChildrenTagToFunction: t.Dict[str, t.Callable[
    [Element,
        t.Optional[meter.TimeSignature],
        spanner.SpannerBundle,
        t.Dict[str, str]],
    t.Any]
] = {
    f'{MEI_NS}app': appChoiceNoteChildrenFromElement,
    f'{MEI_NS}choice': appChoiceNoteChildrenFromElement,
    f'{MEI_NS}add': passThruEditorialNoteChildrenFromElement,
    f'{MEI_NS}corr': passThruEditorialNoteChildrenFromElement,
    f'{MEI_NS}damage': passThruEditorialNoteChildrenFromElement,
    f'{MEI_NS}expan': passThruEditorialNoteChildrenFromElement,
    f'{MEI_NS}orig': passThruEditorialNoteChildrenFromElement,
    f'{MEI_NS}reg': passThruEditorialNoteChildrenFromElement,
    f'{MEI_NS}sic': passThruEditorialNoteChildrenFromElement,
    f'{MEI_NS}subst': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}supplied': passThruEditorialNoteChildrenFromElement,
    f'{MEI_NS}unclear': passThruEditorialNoteChildrenFromElement,
    f'{MEI_NS}dot': dotFromElement,
    f'{MEI_NS}artic': articFromElement,
    f'{MEI_NS}accid': accidFromElement,
    f'{MEI_NS}verse': verseFromElement,
    f'{MEI_NS}syl': sylFromElement
}

chordChildrenTagToFunction: t.Dict[str, t.Callable[
    [Element,
        t.Optional[meter.TimeSignature],
        spanner.SpannerBundle,
        t.Dict[str, str]],
    t.Any]
] = {
    f'{MEI_NS}app': appChoiceChordChildrenFromElement,
    f'{MEI_NS}choice': appChoiceChordChildrenFromElement,
    f'{MEI_NS}add': passThruEditorialChordChildrenFromElement,
    f'{MEI_NS}corr': passThruEditorialChordChildrenFromElement,
    f'{MEI_NS}damage': passThruEditorialChordChildrenFromElement,
    f'{MEI_NS}expan': passThruEditorialChordChildrenFromElement,
    f'{MEI_NS}orig': passThruEditorialChordChildrenFromElement,
    f'{MEI_NS}reg': passThruEditorialChordChildrenFromElement,
    f'{MEI_NS}sic': passThruEditorialChordChildrenFromElement,
    f'{MEI_NS}subst': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}supplied': passThruEditorialChordChildrenFromElement,
    f'{MEI_NS}unclear': passThruEditorialChordChildrenFromElement,
    f'{MEI_NS}note': noteFromElement,
    f'{MEI_NS}artic': articFromElement,
    f'{MEI_NS}verse': verseFromElement,
    f'{MEI_NS}syl': sylFromElement,
}

beamChildrenTagToFunction: t.Dict[str, t.Callable[
    [Element,
        t.Optional[meter.TimeSignature],
        spanner.SpannerBundle,
        t.Dict[str, str]],
    t.Any]
] = {
    f'{MEI_NS}app': appChoiceBeamChildrenFromElement,
    f'{MEI_NS}choice': appChoiceBeamChildrenFromElement,
    f'{MEI_NS}add': passThruEditorialBeamChildrenFromElement,
    f'{MEI_NS}corr': passThruEditorialBeamChildrenFromElement,
    f'{MEI_NS}damage': passThruEditorialBeamChildrenFromElement,
    f'{MEI_NS}expan': passThruEditorialBeamChildrenFromElement,
    f'{MEI_NS}orig': passThruEditorialBeamChildrenFromElement,
    f'{MEI_NS}reg': passThruEditorialBeamChildrenFromElement,
    f'{MEI_NS}sic': passThruEditorialBeamChildrenFromElement,
    f'{MEI_NS}subst': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}supplied': passThruEditorialBeamChildrenFromElement,
    f'{MEI_NS}unclear': passThruEditorialBeamChildrenFromElement,
    f'{MEI_NS}clef': clefFromElement,
    f'{MEI_NS}chord': chordFromElement,
    f'{MEI_NS}note': noteFromElement,
    f'{MEI_NS}rest': restFromElement,
    f'{MEI_NS}tuplet': tupletFromElement,
    f'{MEI_NS}beam': beamFromElement,
    f'{MEI_NS}bTrem': bTremFromElement,
    f'{MEI_NS}fTrem': fTremFromElement,
    f'{MEI_NS}space': spaceFromElement,
    f'{MEI_NS}barLine': barLineFromElement,
}

tupletChildrenTagToFunction: t.Dict[str, t.Callable[
    [Element,
        t.Optional[meter.TimeSignature],
        spanner.SpannerBundle,
        t.Dict[str, str]],
    t.Any]
] = {
    f'{MEI_NS}app': appChoiceTupletChildrenFromElement,
    f'{MEI_NS}choice': appChoiceTupletChildrenFromElement,
    f'{MEI_NS}add': passThruEditorialTupletChildrenFromElement,
    f'{MEI_NS}corr': passThruEditorialTupletChildrenFromElement,
    f'{MEI_NS}damage': passThruEditorialTupletChildrenFromElement,
    f'{MEI_NS}expan': passThruEditorialTupletChildrenFromElement,
    f'{MEI_NS}orig': passThruEditorialTupletChildrenFromElement,
    f'{MEI_NS}reg': passThruEditorialTupletChildrenFromElement,
    f'{MEI_NS}sic': passThruEditorialTupletChildrenFromElement,
    f'{MEI_NS}subst': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}supplied': passThruEditorialTupletChildrenFromElement,
    f'{MEI_NS}unclear': passThruEditorialTupletChildrenFromElement,
    f'{MEI_NS}tuplet': tupletFromElement,
    f'{MEI_NS}beam': beamFromElement,
    f'{MEI_NS}bTrem': bTremFromElement,
    f'{MEI_NS}fTrem': fTremFromElement,
    f'{MEI_NS}note': noteFromElement,
    f'{MEI_NS}rest': restFromElement,
    f'{MEI_NS}chord': chordFromElement,
    f'{MEI_NS}clef': clefFromElement,
    f'{MEI_NS}space': spaceFromElement,
    f'{MEI_NS}barLine': barLineFromElement,
}

bTremChildrenTagToFunction: t.Dict[str, t.Callable[
    [Element,
        t.Optional[meter.TimeSignature],
        spanner.SpannerBundle,
        t.Dict[str, str]],
    t.Any]
] = {
    f'{MEI_NS}app': appChoiceBTremChildrenFromElement,
    f'{MEI_NS}choice': appChoiceBTremChildrenFromElement,
    f'{MEI_NS}add': passThruEditorialBTremChildrenFromElement,
    f'{MEI_NS}corr': passThruEditorialBTremChildrenFromElement,
    f'{MEI_NS}damage': passThruEditorialBTremChildrenFromElement,
    f'{MEI_NS}expan': passThruEditorialBTremChildrenFromElement,
    f'{MEI_NS}orig': passThruEditorialBTremChildrenFromElement,
    f'{MEI_NS}reg': passThruEditorialBTremChildrenFromElement,
    f'{MEI_NS}sic': passThruEditorialBTremChildrenFromElement,
    f'{MEI_NS}subst': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}supplied': passThruEditorialBTremChildrenFromElement,
    f'{MEI_NS}unclear': passThruEditorialBTremChildrenFromElement,
    f'{MEI_NS}note': noteFromElement,
    f'{MEI_NS}chord': chordFromElement,
}

fTremChildrenTagToFunction: t.Dict[str, t.Callable[
    [Element,
        t.Optional[meter.TimeSignature],
        spanner.SpannerBundle,
        t.Dict[str, str]],
    t.Any]
] = {
    f'{MEI_NS}app': appChoiceFTremChildrenFromElement,
    f'{MEI_NS}choice': appChoiceFTremChildrenFromElement,
    f'{MEI_NS}add': passThruEditorialFTremChildrenFromElement,
    f'{MEI_NS}corr': passThruEditorialFTremChildrenFromElement,
    f'{MEI_NS}damage': passThruEditorialFTremChildrenFromElement,
    f'{MEI_NS}expan': passThruEditorialFTremChildrenFromElement,
    f'{MEI_NS}orig': passThruEditorialFTremChildrenFromElement,
    f'{MEI_NS}reg': passThruEditorialFTremChildrenFromElement,
    f'{MEI_NS}sic': passThruEditorialFTremChildrenFromElement,
    f'{MEI_NS}subst': passThruEditorialLayerChildrenFromElement,
    f'{MEI_NS}supplied': passThruEditorialFTremChildrenFromElement,
    f'{MEI_NS}unclear': passThruEditorialFTremChildrenFromElement,
    f'{MEI_NS}note': noteFromElement,
    f'{MEI_NS}chord': chordFromElement,
}


# -----------------------------------------------------------------------------
_DOC_ORDER = [
    accidFromElement,
    articFromElement,
    beamFromElement,
    chordFromElement,
    clefFromElement,
    dotFromElement,
    instrDefFromElement,
    layerFromElement,
    measureFromElement,
    noteFromElement,
    spaceFromElement,
    mSpaceFromElement,
    restFromElement,
    mRestFromElement,
    scoreFromElement,
    sectionFromElement,
    scoreDefFromElement,
    staffFromElement,
    staffDefFromElement,
    staffGrpFromElement,
    tupletFromElement,
]

if __name__ == '__main__':
    import music21
    music21.mainTest()
