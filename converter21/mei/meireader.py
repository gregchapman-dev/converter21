# ------------------------------------------------------------------------------
# Name:          meireader.py
# Purpose:       MEI parser
#
# Authors:       Greg Chapman <gregc@mac.com>
#                The core of this code was based on the MEI parser (primarily written
#                by Christopher Antila) in https://github.com/cuthbertLab/music21
#                (music21 is Copyright 2006-2023 by Michael Scott Asato Cuthbert)
#
# Copyright:     (c) 2021-2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
'''
These are the public interfaces for the MEI module by Christopher Antila

To convert a string with MEI markup into music21 objects,
use :meth:`~converter21.mei.MeiReader.convertFromString`.

In the future, most of the functions in this module should be moved to a separate, import-only
module, so that functions for writing music21-to-MEI will fit nicely.

**Simple "How-To"**

Use :class:`MeiReader` to convert a string to a set of music21 objects. In the future, the
:class:`M21ToMeiConverter` class will convert a set of music21 objects into a string with a MEI
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
>>> from converter21.mei.meireader import MeiReader
>>> conv = MeiReader(meiString)
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
must use the :class:`MeiReader` to process them properly.

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
* <lb>: a line break

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
import music21 as m21
from music21.base import Music21Object
if hasattr(m21.common.enums, 'OrnamentDelay'):
    from music21.common.enums import OrnamentDelay  # type: ignore
from music21.common.numberTools import opFrac
from music21.common.types import OffsetQL
from music21 import articulations
from music21 import bar
from music21 import beam
from music21 import chord
from music21 import clef
from music21 import duration
from music21 import dynamics
from music21 import environment
from music21 import expressions
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

from converter21.mei import MeiValidityError
# from converter21.mei import MeiValueError
from converter21.mei import MeiAttributeError
from converter21.mei import MeiElementError
from converter21.mei import MeiInternalError

from converter21.shared import SharedConstants
from converter21.shared import M21Utilities
from converter21.shared import M21StaffGroupDescriptionTree

environLocal = environment.Environment('converter21.mei.meireader')


_XMLID = '{http://www.w3.org/XML/1998/namespace}id'
MEI_NS = '{http://www.music-encoding.org/ns/mei}'
# when these tags aren't processed, we won't worry about them (at least for now)
_IGNORE_UNPROCESSED = (
    f'{MEI_NS}annot',        # annotations are skipped; someday maybe goes into editorial?
    f'{MEI_NS}pedal',        # pedal marks are skipped for now
    f'{MEI_NS}harm',         # harm (chord symbols) are skipped for now
    f'{MEI_NS}expansion',    # expansions are intentionally skipped
    f'{MEI_NS}bracketSpan',  # bracketSpans (phrases, ligatures, ...) are intentionally skipped
    f'{MEI_NS}mensur',       # mensur is intentionally skipped, we use the invis <meterSig> instead
    f'{MEI_NS}slur',         # slurs; handled in convertFromString()
    f'{MEI_NS}tie',          # ties; handled in convertFromString()
    f'{MEI_NS}tupletSpan',   # tuplets; handled in convertFromString()
    f'{MEI_NS}beamSpan',     # beams; handled in convertFromString()
    f'{MEI_NS}verse',        # lyrics; handled separately by noteFromElement()
    f'{MEI_NS}instrDef',     # instrument; handled separately by staffDefFromElement()
    f'{MEI_NS}label',        # instrument; handled separately by staffDefFromElement()
    f'{MEI_NS}labelAbbr',    # instrument; handled separately by staffDefFromElement()
    f'{MEI_NS}measure',      # measure; handled separately by {score,section}FromElement()
)


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

class MeiReader:
    '''
    A :class:`MeiReader` instance manages the conversion of a MEI document into music21
    objects.

    If ``theDocument`` does not have <mei> as the root element, the class raises an
    :class:`MeiElementError`. If ``theDocument`` is not a valid XML file, the class raises an
    :class:`MeiValidityError`.

    :param str theDocument: A string containing a MEI document.
    :raises: :exc:`MeiElementError` when the root element is not <mei>
    :raises: :exc:`MeiValidityError` when the MEI file is not valid XML.
    '''

    def __init__(self, theDocument: str | None = None) -> None:
        #  The __init__() documentation doesn't isn't processed by Sphinx,
        #  so I put it at class level.
        environLocal.printDebug('*** initializing MeiReader')

        self.initializeTagToFunctionTables()

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

        # This defaultdict stores extra, music21-specific attributes that we add to elements to
        # help importing. The key is an element's @xml:id, and the value is a regular dict with
        # keys corresponding to attributes we'll add and values corresponding to those
        # attributes' values.
        # This is only used during the preprocessing phase (ending with the call to
        # self._ppConclude, which adds all the music21-specific attributes to elements in
        # the MEI tree).
        self.m21Attr: defaultdict = defaultdict(lambda: {})

        # This SpannerBundle holds (among other things) the slurs that will be created by
        # _ppSlurs() and used while importing whatever note, rest, chord, or other object.
        self.spannerBundle: spanner.SpannerBundle = spanner.SpannerBundle()

        # Current parse state:

        # The staff number for the notes we are parsing.
        self.staffNumberForNotes: str = ''

        # The staff number for the staffdef we are parsing.
        self.staffNumberForDef: str = ''

        # The scoredef@midi.bpm; we'll use it later for the very first tempo
        # if there's no tempo@midi.bpm.
        self.pendingMIDIBPM: str = ''

        # key = staffNStr, value = current Key/KeySignature
        self.currKeyPerStaff: dict[str, key.Key | key.KeySignature | None] = {}

        # The list of implied alters is implied by the current key, modified by
        # any prior accidentals in the current measure.  These lists are updated
        # any time an accidental is seen (including any above or below an ornament).
        # key = staffNStr, value = list of alters
        self.currentImpliedAltersPerStaff: dict[str, list[int]] = {}

        # In a MEI file, the parts in the score are ordered in document order, not
        # in order of staff@n.  So we need to know which of the staff@n values is
        # the top-most part.
        self.topPartN: str = ''

        # When we encounter a <pb> or <sb> element, we store the PageLayout or
        # SystemLayout here, and then back-insert it appropriately later.
        # If a <pb> and <sb> show up together, the system break is ignored and
        # only the page break is used.
        self.nextBreak: m21.layout.PageLayout | m21.layout.SystemLayout | None = None

        # Here is where we store any spanners that are waiting for the measure that
        # contains their end element.  Once they get an end element, they are removed
        # from this list.
        self.pendingSpannerEnds: list[tuple[str, spanner.Spanner, int, OffsetQL]] = []

        # this is a dictionary (keyed by staff@n) of stuff that has been gathered up during
        # the parse that should go in the next measure or section.
        self.pendingInNextThing: dict[str, list[Music21Object | list[Music21Object]]] = {}

        # activeMeter is kept up-to-date as the score is parsed.
        # It is used in various places, but mostly to compute what a @tstamp means.
        self.activeMeter: meter.TimeSignature | None = None

    def run(self) -> stream.Score | stream.Part | stream.Opus:
        '''
        Run conversion of the internal MEI document to produce a music21 object.

        Returns a :class:`~music21.stream.Stream` subclass, depending on the MEI document.
        '''

        environLocal.printDebug('*** pre-processing elements with startid/endid/plist/etc')

        self._ppSlurs()
        self._ppTies()
        self._ppBeams()
        self._ppTuplets()
        self._ppHairpins()

        self._ppFermatas()
        self._ppArpeggios()
        self._ppOctaves()

        self._ppTrills()
        self._ppMordents()
        self._ppTurns()

        self._ppDirsDynamsTempos()

        self._ppConclude()

        # This is a lie; we only process the first <score> element we see.
        environLocal.printDebug('*** processing <score> elements')

        scoreElem: Element | None = self.documentRoot.find(f'.//{MEI_NS}music//{MEI_NS}score')
        if scoreElem is None:
            # no <score> found, return an empty Score
            return stream.Score()

        theScore: stream.Score = self.scoreFromElement(scoreElem)

        environLocal.printDebug('*** preparing metadata')
        theScore.metadata = self.makeMetadata()

        return theScore


    # Static Utility Functions
    # -----------------------------------------------------------------------------
    def allPartsPresent(self, scoreElem: Element) -> tuple[tuple[str, ...], str]:
        # noinspection PyShadowingNames
        '''
        Find the @n values for all <staffDef> elements in a <score> element. This assumes
        that every MEI <staff> corresponds to a music21 :class:`~music21.stream.Part`.

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
        >>> from converter21.mei import MeiReader
        >>> meiDoc = ETree.fromstring(meiDoc)
        >>> c = MeiReader()
        >>> c.allPartsPresent(meiDoc)
        (('1', '2'), '1')

        Even though there are three <staffDef> elements in the document, there are only
        two unique @n attributes. The second appearance of <staffDef> with @n="2" signals
        a change of clef on that same staff---not that there is a new staff.
        '''
        # xpathQuery = f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}staffDef'
        xpathQuery: str = f'.//{MEI_NS}staffDef'
        partNs: list[str] = []  # hold the @n attribute for all the parts
        topPart: str = ''

        for staffDef in scoreElem.findall(xpathQuery):
            nStr: str | None = staffDef.get('n')
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
    _ACCID_ATTR_DICT: dict[str | None, str | None] = {
        's': '#', 'f': '-', 'ss': '##', 'x': '##', 'ff': '--', 'xs': '###',
        'ts': '###', 'tf': '---', 'n': 'n', 'nf': '-', 'ns': '#',
        'su': '#~', 'sd': '~', 'fu': '`', 'fd': '-`', 'nu': '~', 'nd': '`',
        '1qf': '`', '3qf': '-`', '1qs': '~', '3qs': '#~',
        None: None
    }

    # for _accidGesFromAttr()
    # None is for when @accid is omitted
    _ACCID_GES_ATTR_DICT: dict[str | None, str | None] = {
        's': '#', 'f': '-', 'ss': '##', 'ff': '--', 'n': 'n',
        'su': '#~', 'sd': '~', 'fu': '`', 'fd': '-`',
        None: None
    }

    # for _qlDurationFromAttr()
    # None is for when @dur is omitted; it's silly so it can be identified
    _DUR_ATTR_DICT: dict[str | None, float] = {
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

    _DUR_TO_NUMBEAMS: dict[str, int] = {
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

    _QL_TO_NUMFLAGS: dict[OffsetQL, int] = {
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

    _STEMMOD_TO_NUMSLASHES: dict[str, int] = {
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
    _ARTIC_ATTR_DICT: dict[str | None, t.Type] = {
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
    _BAR_ATTR_DICT: dict[str | None, str] = {
        'dashed': 'dashed',
        'dotted': 'dotted',
        'dbl': 'double',
        'end': 'final',
        'invis': 'none',
        'single': 'regular',
    }

    # for _stemDirectionFromAttr()
    _STEMDIR_ATTR_DICT: dict[str | None, str | None] = {
        'down': 'down',
        'up': 'up'
    }


    # Static One-to-One Translator Functions
    # -----------------------------------------------------------------------------
    def _attrTranslator(
        self,
        attr: str | None,
        name: str,
        mapping: dict[str | None, t.Any]
    ) -> t.Any:
        '''
        Helper function for other functions that need to translate the value of an attribute
        to another known value. :func:`_attrTranslator` tries to return the value of ``attr``
        in ``mapping`` and, if ``attr`` isn't in ``mapping``, an exception is raised.

        :param str attr: The value of the attribute to look up in ``mapping``.
        :param str name: Name of the attribute, used when raising an exception (read below).
        :param mapping: A mapping type (nominally a dict) with relevant key-value pairs.

        Examples:

        >>> from converter21.mei import MeiReader
        >>> c = MeiReader()
        >>> c._attrTranslator('s', 'accid', MeiReader._ACCID_ATTR_DICT)
        '#'
        >>> c._attrTranslator('9', 'dur', MeiReader._DUR_ATTR_DICT) == None
        True
        '''
        try:
            return mapping[attr]
        except KeyError:
            # rather than raising an exception, simply warn
            environLocal.warn(_UNEXPECTED_ATTR_VALUE.format(name, attr))
            return None

    def _accidentalFromAttr(self, attr: str | None) -> str | None:
        '''
        Use :func:`_attrTranslator` to convert the value of an "accid" attribute to its
        music21 string.

        >>> from converter21.mei import MeiReader
        >>> c = MeiReader()
        >>> c._accidentalFromAttr('s')
        '#'
        '''
        return self._attrTranslator(attr, 'accid', self._ACCID_ATTR_DICT)

    def _accidGesFromAttr(self, attr: str | None) -> str | None:
        '''
        Use :func:`_attrTranslator` to convert the value of an @accid.ges
        attribute to its music21 string.

        >>> from converter21.mei import MeiReader
        >>> c = MeiReader()
        >>> c._accidGesFromAttr('s')
        '#'
        '''
        return self._attrTranslator(attr, 'accid.ges', self._ACCID_GES_ATTR_DICT)

    def _qlDurationFromAttr(self, attr: str | None) -> float:
        '''
        Use :func:`_attrTranslator` to convert a MEI "dur" attribute to a music21 quarterLength.

        >>> from converter21.mei import MeiReader
        >>> c = MeiReader()
        >>> c._qlDurationFromAttr('4')
        1.0

        .. note:: This function only handles data.DURATION.cmn, not data.DURATION.mensural.
        '''
        return self._attrTranslator(attr, 'dur', self._DUR_ATTR_DICT)

    def _articulationFromAttr(self, attr: str | None) -> tuple[articulations.Articulation, ...]:
        '''
        Use :func:`_attrTranslator` to convert a MEI "artic" attribute to a
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
            articClass: t.Type = self._attrTranslator(attr, 'artic', self._ARTIC_ATTR_DICT)
            if articClass is not None:
                return (articClass(),)
        return tuple()  # empty tuple

    def _makeArticList(self, attr: str) -> list[articulations.Articulation]:
        '''
        Use :func:`_articulationFromAttr` to convert the actual value of a MEI "artic" attribute
        (including multiple items) into a list suitable for :attr:`GeneralNote.articulations`.
        '''
        articList: list[articulations.Articulation] = []
        for eachArtic in attr.split(' '):
            articList.extend(self._articulationFromAttr(eachArtic))
        return articList

    @staticmethod
    def _getOctaveShift(dis: str | None, disPlace: str | None) -> int:
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

    @staticmethod
    def _sharpsFromAttr(signature: str | None) -> int:
        '''
        Use :func:`_sharpsFromAttr` to convert MEI's ``data.KEYSIGNATURE`` datatype to
        an integer representing the number of sharps, for use with music21's
        :class:`~music21.key.KeySignature`.

        :param str signature: The @key.sig attribute, or the @sig attribute
        :returns: The number of sharps.
        :rtype: int

        >>> from converter21.mei import MeiReader
        >>> c = MeiReader()
        >>> c._sharpsFromAttr('3s')
        3
        >>> c._sharpsFromAttr('3f')
        -3
        >>> c._sharpsFromAttr('0')
        0
        >>> c._sharpsFromAttr(None)
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

    def _stemDirectionFromAttr(self, stemDirStr: str) -> str:
        return self._attrTranslator(stemDirStr, 'stem.dir', self._STEMDIR_ATTR_DICT)

    # "Preprocessing" Functions
    # -----------------------------------------------------------------------------
    def _ppSlurs(self) -> None:
        # noinspection PyShadowingNames
        '''
        Pre-processing helper for :func:`convertFromString` that handles slurs specified in <slur>
        elements. The input is a :class:`MeiReader` with data about the file currently being
        processed. This function reads from ``self.documentRoot`` and writes into
        ``self.m21Attr`` and ``self.spannerBundle``.

        **This Preprocessor**

        The slur preprocessor adds @m21SlurStart and @m21SlurEnd attributes to elements that
        are at the beginning or end of a slur. The value of these attributes is the ``idLocal``
        of a :class:`Slur` in the :attr:`spannerBundle` attribute. This attribute is not part
        of the MEI specification, and must therefore be handled specially.

        If :func:`noteFromElement` encounters an element like ``<note m21SlurStart="82f87cd7"/>``,
        the resulting :class:`music21.note.Note` should be set as the starting point of the slur
        with an ``idLocal`` of ``'82f87cd7'``.

        **Example of Changes to ``m21Attr``**

        The ``self.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
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
        >>> from converter21.mei import MeiReader
        >>> theConverter = MeiReader(meiDoc)
        >>>
        >>> theConverter._ppSlurs()
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
        # pre-processing for <slur> tags
        for eachSlur in self.documentRoot.iterfind(
                f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}slur'
        ):
            startId: str | None = self.removeOctothorpe(eachSlur.get('startid'))
            endId: str | None = self.removeOctothorpe(eachSlur.get('endid'))
            if startId is not None and endId is not None:
                thisIdLocal = str(uuid4())
                thisSlur = spanner.Slur()
                if t.TYPE_CHECKING:
                    # work around Spanner.idLocal being incorrectly type-hinted as None
                    assert isinstance(thisSlur.idLocal, str)
                thisSlur.idLocal = thisIdLocal
                self.spannerBundle.append(thisSlur)


                self.m21Attr[startId]['m21SlurStart'] = thisIdLocal
                self.m21Attr[endId]['m21SlurEnd'] = thisIdLocal
            else:
                environLocal.warn(
                    _UNIMPLEMENTED_IMPORT_WITHOUT.format('<slur>', '@startid and @endid')
                )

    def _ppTies(self) -> None:
        '''
        Pre-processing helper for :func:`convertFromString` that handles ties specified in <tie>
        elements. The input is a :class:`MeiReader` with data about the file currently being
        processed. This function reads from ``self.documentRoot`` and writes into
        ``self.m21Attr``.

        **This Preprocessor**

        The tie preprocessor works similarly to the slur preprocessor, adding @tie attributes. The
        value of these attributes conforms to the MEI Guidelines, so no special action is required.

        **Example of ``m21Attr``**

        The ``self.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
        dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
        dict holds attribute names and their values that should be added to the element with the
        given @xml:id.

        For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
        element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
        '''
        environLocal.printDebug('*** pre-processing ties')

        for eachTie in self.documentRoot.iterfind(
                f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}tie'):
            startId: str | None = self.removeOctothorpe(eachTie.get('startid'))
            endId: str | None = self.removeOctothorpe(eachTie.get('endid'))
            if startId is not None and endId is not None:
                if startId in self.m21Attr and self.m21Attr[startId].get('tie', '') == 't':
                    # the startid note is already a tie end, so now it's both end and start
                    self.m21Attr[startId]['tie'] = 'ti'
                else:
                    self.m21Attr[startId]['tie'] = 'i'

                if endId in self.m21Attr and self.m21Attr[endId].get('tie', '') == 'i':
                    # the endid note is already a tie start, so now it's both end and start
                    self.m21Attr[endId]['tie'] = 'it'
                else:
                    self.m21Attr[endId]['tie'] = 't'
            else:
                environLocal.warn(
                    _UNIMPLEMENTED_IMPORT_WITHOUT.format('<tie>', '@startid and @endid')
                )

    def _ppBeams(self) -> None:
        '''
        Pre-processing helper for :func:`convertFromString` that handles beams specified
        in <beamSpan> elements. The input is a :class:`MeiReader` with data about
        the file currently being processed. This function reads from ``self.documentRoot``
        and writes into ``self.m21Attr``.

        **This Preprocessor**

        The beam preprocessor works similarly to the slur preprocessor, adding the @m21Beam
        attribute. The value of this attribute is either ``'start'``, ``'continue'``, or
        ``'stop'``, indicating the music21 ``type`` of the primary beam attached to this
        element. This attribute is not part of the MEI specification, and must therefore be
        handled specially.

        **Example of ``m21Attr``**

        The ``self.m21Attr`` argument must be a defaultdict that returns an empty (regular)
        dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
        dict holds attribute names and their values that should be added to the element with the
        given @xml:id.

        For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
        element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
        '''
        environLocal.printDebug('*** pre-processing beams')

        # pre-processing for <beamSpan> elements
        for eachBeam in self.documentRoot.iterfind(
                f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}beamSpan'):
            if eachBeam.get('startid') is None or eachBeam.get('endid') is None:
                environLocal.warn(
                    _UNIMPLEMENTED_IMPORT_WITHOUT.format('<beamSpan>', '@startid and @endid')
                )
                continue

            self.m21Attr[self.removeOctothorpe(eachBeam.get('startid'))]['m21Beam'] = 'start'
            self.m21Attr[self.removeOctothorpe(eachBeam.get('endid'))]['m21Beam'] = 'stop'

            # iterate things in the @plist attribute
            for eachXmlid in eachBeam.get('plist', '').split(' '):
                eachXmlid = self.removeOctothorpe(eachXmlid)  # type: ignore
                if 'm21Beam' not in self.m21Attr[eachXmlid]:
                    # only set to 'continue' if it wasn't previously set to 'start' or 'stop'
                    self.m21Attr[eachXmlid]['m21Beam'] = 'continue'

    def _ppTuplets(self) -> None:
        '''
        Pre-processing helper for :func:`convertFromString` that handles tuplets specified in
        <tupletSpan> elements. The input is a :class:`MeiReader` with data about the file
        currently being processed. This function reads from ``self.documentRoot`` and writes
        into ``self.m21Attr``.

        **This Preprocessor**

        The slur preprocessor works similarly to the slur preprocessor, adding @m21TupletNum and
        @m21TupletNumbase attributes. The value of these attributes corresponds to the @num and
        @numbase attributes found on a <tuplet> element. This preprocessor also performs a
        significant amount of guesswork to try to handle <tupletSpan> elements that do not include
        a @plist attribute. This attribute is not part of the MEI specification, and must therefore
        be handled specially.

        **Example of ``m21Attr``**

        The ``self.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
        dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
        dict holds attribute names and their values that should be added to the element with the
        given @xml:id.

        For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
        element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
        '''
        environLocal.printDebug('*** pre-processing tuplets')

        tempStr: str

        # pre-processing <tupletSpan> tags
        for eachTuplet in self.documentRoot.iterfind(
                f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}tupletSpan'):
            if ((eachTuplet.get('startid') is None or eachTuplet.get('endid') is None)
                    and eachTuplet.get('plist') is None):
                environLocal.warn(_UNIMPLEMENTED_IMPORT_WITHOUT.format('<tupletSpan>',
                                                               '@startid and @endid, or @plist'))
            elif eachTuplet.get('plist') is not None:
                # Ideally (for us) <tupletSpan> elements will have a @plist that enumerates the
                # @xml:id of every affected element. In this case, tupletSpanFromElement() can
                # use the @plist to add our custom @m21TupletNum and @m21TupletNumbase attributes.
                for eachXmlid in eachTuplet.get('plist', '').split(' '):
                    eachXmlid = self.removeOctothorpe(eachXmlid)  # type: ignore
                    if eachXmlid:
                        # protect against extra spaces around the contained xml:id values
                        self.m21Attr[eachXmlid]['m21TupletNum'] = eachTuplet.get('num')
                        self.m21Attr[eachXmlid]['m21TupletNumbase'] = eachTuplet.get('numbase')
                        # the following attributes may or may not be there
                        tempStr = eachTuplet.get('bracket.visible', '')
                        if tempStr:
                            self.m21Attr[eachXmlid]['m21TupletBracketVisible'] = tempStr
                        tempStr = eachTuplet.get('bracket.place', '')
                        if tempStr:
                            self.m21Attr[eachXmlid]['m21TupletBracketPlace'] = tempStr
                        tempStr = eachTuplet.get('num.visible', '')
                        if tempStr:
                            self.m21Attr[eachXmlid]['m21TupletNumVisible'] = tempStr
                        tempStr = eachTuplet.get('num.place', '')
                        if tempStr:
                            self.m21Attr[eachXmlid]['m21TupletNumPlace'] = tempStr
                        tempStr = eachTuplet.get('num.format', '')
                        if tempStr:
                            self.m21Attr[eachXmlid]['m21TupletNumFormat'] = tempStr
            else:
                # For <tupletSpan> elements that don't give a @plist attribute, we have to do
                # some guesswork and hope we find all the related elements. Right here, we're
                # only setting the "flags" that this guesswork must be done later.
                startid = self.removeOctothorpe(eachTuplet.get('startid'))
                endid = self.removeOctothorpe(eachTuplet.get('endid'))

                self.m21Attr[startid]['m21TupletSearch'] = 'start'
                self.m21Attr[startid]['m21TupletNum'] = eachTuplet.get('num')
                self.m21Attr[startid]['m21TupletNumbase'] = eachTuplet.get('numbase')
                # the following attributes may or may not be there
                tempStr = eachTuplet.get('bracket.visible', '')
                if tempStr:
                    self.m21Attr[startid]['m21TupletBracketVisible'] = tempStr
                tempStr = eachTuplet.get('bracket.place', '')
                if tempStr:
                    self.m21Attr[startid]['m21TupletBracketPlace'] = tempStr
                tempStr = eachTuplet.get('num.visible', '')
                if tempStr:
                    self.m21Attr[startid]['m21TupletNumVisible'] = tempStr
                tempStr = eachTuplet.get('num.place', '')
                if tempStr:
                    self.m21Attr[startid]['m21TupletNumPlace'] = tempStr
                tempStr = eachTuplet.get('num.format', '')
                if tempStr:
                    self.m21Attr[startid]['m21TupletNumFormat'] = tempStr

                self.m21Attr[endid]['m21TupletSearch'] = 'end'
                self.m21Attr[endid]['m21TupletNum'] = eachTuplet.get('num')
                self.m21Attr[endid]['m21TupletNumbase'] = eachTuplet.get('numbase')
                # the following attributes may or may not be there
                tempStr = eachTuplet.get('bracket.visible', '')
                if tempStr:
                    self.m21Attr[endid]['m21TupletBracketVisible'] = tempStr
                tempStr = eachTuplet.get('bracket.place', '')
                if tempStr:
                    self.m21Attr[endid]['m21TupletBracketPlace'] = tempStr
                tempStr = eachTuplet.get('num.visible', '')
                if tempStr:
                    self.m21Attr[endid]['m21TupletNumVisible'] = tempStr
                tempStr = eachTuplet.get('num.place', '')
                if tempStr:
                    self.m21Attr[endid]['m21TupletNumPlace'] = tempStr
                tempStr = eachTuplet.get('num.format', '')
                if tempStr:
                    self.m21Attr[endid]['m21TupletNumFormat'] = tempStr

    def _ppHairpins(self) -> None:
        # Hairpins can have any of @startid/@endid, @tstamp/@tstamp2,
        # @startid/@tstamp2, or @tstamp/@endid.  We process all of them
        # here, to create the DynamicWedge, put it in the spannerBundle,
        # and set up any @startid and @endid notes for insertion into a
        # hairpin spanner, and then all of them again in hairpinFromElement,
        # to possibly set up SpannerAnchors as needed for @tstamp and
        # @tstamp2.
        environLocal.printDebug('*** pre-processing hairpins')

        for eachElem in self.documentRoot.iterfind(
                f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}hairpin'):
            startId: str = self.removeOctothorpe(eachElem.get('startid', ''))  # type: ignore
            endId: str = self.removeOctothorpe(eachElem.get('endid', ''))  # type: ignore
            form: str = eachElem.get('form', '')
            dw: m21.dynamics.DynamicWedge
            if form == 'cres':
                dw = dynamics.Crescendo()
            elif form == 'dim':
                dw = dynamics.Diminuendo()
            else:
                environLocal.warn(f'invalid @form = "{form}" in <hairpin>')
                continue

            place: str | None = eachElem.get('place')
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

            if t.TYPE_CHECKING:
                # work around Spanner.idLocal being incorrectly type-hinted as None
                assert isinstance(dw.idLocal, str)
            thisIdLocal: str = str(uuid4())
            dw.idLocal = thisIdLocal
            self.spannerBundle.append(dw)

            eachElem.set('m21Hairpin', thisIdLocal)
            if startId:
                self.m21Attr[startId]['m21HairpinStart'] = thisIdLocal
            if endId:
                self.m21Attr[endId]['m21HairpinEnd'] = thisIdLocal

            staffNStr: str = eachElem.get('staff', '')
            if staffNStr:
                dw.mei_staff = staffNStr  # type: ignore

    def _ppFermatas(self) -> None:
        '''
        Pre-processing helper for :func:`convertFromString` that handles fermats specified
        in <fermata> elements. The input is a :class:`MeiReader` with data about
        the file currently being processed. This function reads from ``self.documentRoot``
        and writes into ``self.m21Attr``.

        **This Preprocessor**

        The fermata preprocessor works similarly to the tie preprocessor, adding @fermata
        attributes. The @fermata attribute looks like it would if specified according to the
        Guidelines (e.g. @fermata="above", where "above" comes from the <fermata> element's
        @place attribute).  The other attributes from the <fermata> element (@form and @shape)
        are also added, prefixed with 'fermata_' as follows: @fermata_form and @fermata_shape.

        **Example of ``m21Attr``**

        The ``self.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
        dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
        dict holds attribute names and their values that should be added to the element with the
        given @xml:id.

        For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
        element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
        '''
        environLocal.printDebug('*** pre-processing fermatas')

        for eachFermata in self.documentRoot.iterfind(
                f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}fermata'):
            startId: str | None = self.removeOctothorpe(eachFermata.get('startid'))
            if startId is None:
                # leave this alone, we'll handle it later in fermataFromElement
                continue

            # mark as handled, so we WON'T handle it later in fermataFromElement
            eachFermata.set('ignore_in_fermataFromElement', 'true')

            place: str = eachFermata.get('place', 'above')  # default @place is "above"
            self.m21Attr[startId]['fermata'] = place

            form: str = eachFermata.get('form', '')
            shape: str = eachFermata.get('shape', '')
            if form:
                self.m21Attr[startId]['fermata_form'] = form
            if shape:
                self.m21Attr[startId]['fermata_shape'] = shape

    def _ppTrills(self) -> None:
        '''
        Pre-processing helper for :func:`convertFromString` that handles trills specified in <trill>
        elements. The input is a :class:`MeiReader` with data about the file currently being
        processed. This function reads from ``self.documentRoot`` and writes into
        ``self.m21Attr``.

        **This Preprocessor**

        The trill preprocessor works similarly to the tie preprocessor, adding @m21Trill,
        @m21TrillExtStart and @m21TrillExtEnd attributes to any referenced notes/chords.

        **Example of ``m21Attr``**

        The ``self.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
        dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
        dict holds attribute names and their values that should be added to the element with the
        given @xml:id.

        For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
        element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
        '''
        environLocal.printDebug('*** pre-processing trills')

        for eachTrill in self.documentRoot.iterfind(
                f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}trill'):
            startId: str = self.removeOctothorpe(eachTrill.get('startid', ''))  # type: ignore
            endId: str = self.removeOctothorpe(eachTrill.get('endid', ''))  # type: ignore
            tstamp2: str = eachTrill.get('tstamp2', '')
            hasExtension: bool = bool(endId) or bool(tstamp2)
            place: str = eachTrill.get('place', 'place_unspecified')

            if startId:
                # The trill info gets stashed on the note/chord referenced by startId
                accidUpper: str = eachTrill.get('accidupper', '')
                accidLower: str = eachTrill.get('accidlower', '')

                self.m21Attr[startId]['m21Trill'] = place
                if accidUpper:
                    self.m21Attr[startId]['m21TrillAccidUpper'] = accidUpper
                if accidLower:
                    self.m21Attr[startId]['m21TrillAccidLower'] = accidLower

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
            self.spannerBundle.append(trillExt)

            if startId:
                self.m21Attr[startId]['m21TrillExtensionStart'] = thisIdLocal
            if endId:
                self.m21Attr[endId]['m21TrillExtensionEnd'] = thisIdLocal

            if startId and endId:
                # we're finished (well, once we've processed both of those note/chord elements)
                eachTrill.set('ignore_trill_extension_in_trillFromElement', 'true')
            else:
                # we have to finish in trillFromElement, tell him about our TrillExtension
                eachTrill.set('m21TrillExtension', thisIdLocal)

    def _ppMordents(self) -> None:
        '''
        Pre-processing helper for :func:`convertFromString` that handles mordents in <mordent>
        elements. The input is a :class:`MeiReader` with data about the file currently being
        processed. This function reads from ``self.documentRoot`` and writes into
        ``self.m21Attr``.

        **This Preprocessor**

        The mordent preprocessor works similarly to the tie preprocessor, adding @m21Mordent
        attributes to any referenced notes/chords.

        **Example of ``m21Attr``**

        The ``self.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
        dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
        dict holds attribute names and their values that should be added to the element with the
        given @xml:id.

        For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
        element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
        '''
        environLocal.printDebug('*** pre-processing mordents')

        for eachMordent in self.documentRoot.iterfind(
                f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}mordent'):
            startId: str = self.removeOctothorpe(eachMordent.get('startid', ''))  # type: ignore
            place: str = eachMordent.get('place', 'place_unspecified')
            form: str = eachMordent.get('form', '')
            long: str = eachMordent.get('long', '')

            if startId:
                if long == 'true':
                    environLocal.warn(
                        _UNIMPLEMENTED_IMPORT_WITH.format('<mordent>', '@long="true"')
                    )
                    environLocal.warn('@long will be ignored')

                # The mordent info gets stashed on the note/chord referenced by startId
                accidUpper: str = eachMordent.get('accidupper', '')
                accidLower: str = eachMordent.get('accidlower', '')

                self.m21Attr[startId]['m21Mordent'] = place
                if form:
                    self.m21Attr[startId]['m21MordentForm'] = form
                if accidUpper:
                    self.m21Attr[startId]['m21MordentAccidUpper'] = accidUpper
                if accidLower:
                    self.m21Attr[startId]['m21MordentAccidLower'] = accidLower

                eachMordent.set('ignore_mordent_in_mordentFromElement', 'true')

    def _ppTurns(self) -> None:
        '''
        Pre-processing helper for :func:`convertFromString` that handles turns in <turn>
        elements. The input is a :class:`MeiReader` with data about the file currently being
        processed. This function reads from ``self.documentRoot`` and writes into
        ``self.m21Attr``.

        **This Preprocessor**

        The turn preprocessor works similarly to the tie preprocessor, adding @m21Turn
        attributes to any referenced notes/chords.

        **Example of ``m21Attr``**

        The ``self.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
        dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
        dict holds attribute names and their values that should be added to the element with the
        given @xml:id.

        For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
        element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
        '''
        environLocal.printDebug('*** pre-processing turns')

        for eachTurn in self.documentRoot.iterfind(
                f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}turn'):
            startId: str = self.removeOctothorpe(eachTurn.get('startid', ''))  # type: ignore
            place: str = eachTurn.get('place', 'place_unspecified')
            form: str = eachTurn.get('form', '')
            theType: str = eachTurn.get('type', '')
            delayed: str = eachTurn.get('delayed', '')

            if startId:
                # The turn info gets stashed on the note/chord referenced by startId
                accidUpper: str = eachTurn.get('accidupper', '')
                accidLower: str = eachTurn.get('accidlower', '')

                self.m21Attr[startId]['m21Turn'] = place
                if form:
                    self.m21Attr[startId]['m21TurnForm'] = form
                if theType:
                    self.m21Attr[startId]['m21TurnType'] = theType
                if accidUpper:
                    self.m21Attr[startId]['m21TurnAccidUpper'] = accidUpper
                if accidLower:
                    self.m21Attr[startId]['m21TurnAccidLower'] = accidLower
                if delayed:
                    self.m21Attr[startId]['m21TurnDelayed'] = delayed

                eachTurn.set('ignore_turn_in_turnFromElement', 'true')

    _M21_OTTAVA_TYPE_FROM_DIS_AND_DIS_PLACE: dict[tuple[str, str], str] = {
        ('8', 'above'): '8va',
        ('8', 'below'): '8vb',
        ('15', 'above'): '15ma',
        ('15', 'below'): '15mb',
        ('22', 'above'): '22da',
        ('22', 'below'): '22db',
    }

    def _ppOctaves(self) -> None:
        '''
        Pre-processing helper for :func:`convertFromString` that handles ottavas specified in
        <octave> elements. The input is a :class:`MeiReader` with data about the file
        currently being processed. This function reads from ``self.documentRoot`` and writes
        into ``self.m21Attr``.

        **This Preprocessor**

        The octave preprocessor works similarly to the tie preprocessor, adding @m21OttavaStart and
        @m21OttavaEnd attributes to any referenced notes/chords.

        **Example of ``m21Attr``**

        The ``self.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
        dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
        dict holds attribute names and their values that should be added to the element with the
        given @xml:id.

        For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
        element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
        '''
        environLocal.printDebug('*** pre-processing octaves')

        for eachOctave in self.documentRoot.iterfind(
                f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}octave'):
            startId: str = self.removeOctothorpe(eachOctave.get('startid', ''))  # type: ignore
            endId: str = self.removeOctothorpe(eachOctave.get('endid', ''))  # type: ignore
            amount: str = eachOctave.get('dis', '')
            direction: str = eachOctave.get('dis.place', '')
            if not amount or not direction:
                environLocal.warn('<octave> without @dis and/or @dis.place: ignoring')
                continue
            if (amount, direction) not in self._M21_OTTAVA_TYPE_FROM_DIS_AND_DIS_PLACE:
                environLocal.warn(
                    f'octave@dis ({amount}) or octave@dis.place ({direction}) invalid: ignoring'
                )
                continue

            ottavaType: str = self._M21_OTTAVA_TYPE_FROM_DIS_AND_DIS_PLACE[(amount, direction)]
            ottava = spanner.Ottava(type=ottavaType)

            # we will use @oct (not @oct.ges) in octave-shifted notes/chords
            ottava.transposing = True
            if t.TYPE_CHECKING:
                # work around Spanner.idLocal being incorrectly type-hinted as None
                assert isinstance(ottava.idLocal, str)
            thisIdLocal: str = str(uuid4())
            ottava.idLocal = thisIdLocal
            self.spannerBundle.append(ottava)
            if startId:
                self.m21Attr[startId]['m21OttavaStart'] = thisIdLocal
            if endId:
                self.m21Attr[endId]['m21OttavaEnd'] = thisIdLocal
            eachOctave.set('m21Ottava', thisIdLocal)
            staffNStr: str = eachOctave.get('staff', '')
            if staffNStr:
                ottava.mei_staff = staffNStr  # type: ignore

    _ARPEGGIO_ARROW_AND_ORDER_TO_ARPEGGIOTYPE: dict[tuple[str, str], str] = {
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

    def _ppArpeggios(self) -> None:
        '''
        Pre-processing helper for :func:`convertFromString` that handles arpeggios specified in
        <arpeg> elements. The input is a :class:`MeiReader` with data about the file
        currently being processed. This function reads from ``self.documentRoot`` and writes
        into ``self.m21Attr``.

        **This Preprocessor**

        The arpeggio preprocessor works similarly to the tie preprocessor, adding @arpeg
        attributes.

        **Example of ``m21Attr``**

        The ``self.m21Attr`` attribute must be a defaultdict that returns an empty (regular)
        dict for non-existent keys. The defaultdict stores the @xml:id attribute of an element; the
        dict holds attribute names and their values that should be added to the element with the
        given @xml:id.

        For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
        element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.
        '''
        environLocal.printDebug('*** pre-processing arpeggios')

        for eachArpeg in self.documentRoot.iterfind(
                f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}arpeg'):
            plistStr: str | None = eachArpeg.get('plist')
            plist: list[str] = []
            if plistStr:
                # if there's a plist, split it into a list
                plist = plistStr.split(' ')

            # If there's a startid, put it at the front of the list (but don't duplicate it
            # if it's already there).
            startId: str | None = eachArpeg.get('startid')
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
                arpeggioType: str = self._ARPEGGIO_ARROW_AND_ORDER_TO_ARPEGGIOTYPE.get(
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
                    self.spannerBundle.append(arpeggio)

                    # iterate things in the @plist attribute,  and reference the
                    # ArpeggioMarkSpanner from each of the notes/chords in the plist
                    for eachXmlid in plist:
                        eachXmlid = self.removeOctothorpe(eachXmlid)  # type: ignore
                        self.m21Attr[eachXmlid]['m21ArpeggioMarkSpanner'] = thisIdLocal
                else:
                    eachXmlid = self.removeOctothorpe(plist[0])  # type: ignore
                    self.m21Attr[eachXmlid]['m21ArpeggioMarkType'] = arpeggioType

                # mark the element as handled, so we WON'T handle it later in arpegFromElement
                eachArpeg.set('ignore_in_arpegFromElement', 'true')

    def _ppDirsDynamsTempos(self) -> None:
        environLocal.printDebug('*** pre-processing dirs/dynams/tempos')

        elems: list[Element] = self.documentRoot.findall(
            f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}dir'
        )
        elems += self.documentRoot.findall(
            f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}dynam'
        )
        elems += self.documentRoot.findall(
            f'.//{MEI_NS}music//{MEI_NS}score//{MEI_NS}tempo'
        )

        for eachElem in elems:
            if eachElem.tag.endswith('dir'):
                lowerName = 'dir'
                name = 'Dir'
            elif eachElem.tag.endswith('dynam'):
                lowerName = 'dynam'
                name = 'Dynam'
            elif eachElem.tag.endswith('tempo'):
                lowerName = 'tempo'
                name = 'Dynam'
            else:
                # shouldn't ever get here
                continue

            if lowerName == 'dir':
                theType: str = eachElem.get('type', '')
                if theType == 'fingering':
                    continue

            startId: str | None = self.removeOctothorpe(eachElem.get('startid'))
            if not startId:
                continue

            # All the info gets stashed on the note/chord element referenced by startId
            place: str = eachElem.get('place', '')
            staff: str = eachElem.get('staff', '')
            # technically not always legal, but I've seen enclose in <dynam>,
            # so support it here for everyone.
            enclose: str | None = eachElem.get('enclose')
            # @midi.bpm is only expected for tempo.
            midiBPM: str = ''
            if lowerName == 'tempo':
                midiBPM = eachElem.get('midi.bpm', '')
            fontStyle: str | None = None
            fontWeight: str | None = None
            fontFamily: str | None = None
            justify: str | None = None
            text: str
            styleDict: dict[str, str]

            text, styleDict = self.textFromElem(eachElem)
            text = html.unescape(text)
            text = text.strip()
            if not text:
                continue

            if enclose is not None:
                if enclose == 'paren':
                    text = '( ' + text + ' )'
                elif enclose == 'brack':
                    text = '[ ' + text + ' ]'

            fontStyle = styleDict.get('fontStyle', None)
            fontWeight = styleDict.get('fontWeight', None)
            fontFamily = styleDict.get('fontFamily', None)
            justify = styleDict.get('justify', None)

            self.m21Attr[startId][f'm21{name}'] = text
            if place:
                self.m21Attr[startId][f'm21{name}Place'] = place
            if staff:
                self.m21Attr[startId][f'm21{name}Staff'] = staff
            if midiBPM:
                self.m21Attr[startId][f'm21{name}MidiBPM'] = midiBPM
            if fontStyle:
                self.m21Attr[startId][f'm21{name}FontStyle'] = fontStyle
            if fontWeight:
                self.m21Attr[startId][f'm21{name}FontWeight'] = fontWeight
            if fontFamily:
                self.m21Attr[startId][f'm21{name}FontFamily'] = fontFamily
            if justify:
                self.m21Attr[startId][f'm21{name}Justify'] = justify

            eachElem.set(f'ignore_in_{lowerName}FromElement', 'true')

    def _ppConclude(self) -> None:
        '''
        Pre-processing helper for :func:`convertFromString` that adds attributes from
        ``m21Attr`` to the appropriate elements in ``documentRoot``. The input is a
        :class:`MeiReader` with data about the file currently being processed.
        This function reads from ``self.m21Attr`` and writes into ``self.documentRoot``.

        **Example of ``m21Attr``**

        The ``m21Attr`` argument must be a defaultdict that returns an empty (regular) dict for
        non-existent keys. The defaultdict stores the @xml:id attribute of an element; the dict
        holds attribute names and their values that should be added to the element with the
        given @xml:id.

        For example, if the value of ``m21Attr['fe93129e']['tie']`` is ``'i'``, then this means the
        element with an @xml:id of ``'fe93129e'`` should have the @tie attribute set to ``'i'``.

        **This Preprocessor**
        The conclude preprocessor adds all attributes from the ``m21Attr`` to the appropriate
        element in ``documentRoot``. In effect, it finds the element corresponding to each key
        in ``m21Attr``, then iterates the keys in its dict, *appending* the ``m21Attr``-specified
        value to any existing value.
        '''
        environLocal.printDebug('*** concluding pre-processing')

        # conclude pre-processing by adding music21-specific attributes to their respective elements
        for eachObject in self.documentRoot.iterfind('*//*'):
            objXmlId: str | None = eachObject.get(_XMLID)
            # we have a defaultdict, so this "if" isn't strictly necessary; but without it, every
            # single element with an @xml:id creates a new, empty dict, which would consume a lot
            # of memory.
            if objXmlId and objXmlId in self.m21Attr:
                objAttrs: dict = self.m21Attr[objXmlId]
                for eachAttr in objAttrs:
                    oldAttrValue: str = eachObject.get(eachAttr, '')
                    newAttrValue: str = objAttrs[eachAttr]
                    eachObject.set(eachAttr, oldAttrValue + newAttrValue)

    # Helper Functions
    # -----------------------------------------------------------------------------
    def _processEmbeddedElements(
        self,
        elements: t.Iterable[Element],
        mapping: dict[str, t.Callable[
            [Element],
            t.Any]
        ],
        callerTag: str,
    ) -> list[t.Any]:
        # noinspection PyShadowingNames
        '''
        From an iterable of MEI ``elements``, use functions in the ``mapping`` to convert each
        element to its music21 object (or a tuple containing its music21 object plus some other
        stuff). This function was designed for use with elements that may contain other elements;
        the contained elements will be converted as appropriate.

        If an element itself has embedded elements (i.e., its converter function in ``mapping``
        returns a sequence), those elements will appear in the returned sequence in order ---
        there are no hierarchic lists.

        :param elements: A list of :class:`Element` objects to convert to music21 objects.
        :type elements: iterable of :class:`~xml.etree.ElementTree.Element`
        :param mapping: A dictionary where keys are the :attr:`Element.tag` attribute and values are
            the function to call to convert that :class:`Element` to a music21 object.
        :type mapping: mapping of str to function
        :param str callerTag: The tag of the element on behalf of which this function is processing
            sub-elements (e.g., 'note' or 'staffDef'). Do not include < and >. This is used in a
            warning message on finding an unprocessed element.
        :returns: A list of the music21 objects returned by the converter functions, or an empty
            list if no objects were returned.
        :rtype: list of :class:`~music21.base.Music21Object`

        **Examples:**

        Because there is no ``'rest'`` key in the ``mapping``, that :class:`Element` is ignored.

        >>> from xml.etree.ElementTree import Element
        >>> from music21 import note
        >>> from converter21.mei import MeiReader
        >>> elements = [Element('note'), Element('rest'), Element('note')]
        >>> mapping = {'note': lambda w: note.Note('D2')}
        >>> c = MeiReader()
        >>> c._processEmbeddedElements(elements, mapping, 'doctest1')
        [<music21.note.Note D>, <music21.note.Note D>]

        If debugging is enabled for the previous example, this warning would be displayed:

        ``mei.meireader: Found an unprocessed <rest> element in a <doctest1>.

        The "beam" element holds "note" elements. All elements appear in a single level of the list:

        >>> elements = [Element('note'), Element('beam'), Element('note')]
        >>> mapping = {'note': lambda w: note.Note('D2'),
        ...            'beam': lambda w: [note.Note('E2') for _ in range(2)]}
        >>> c._processEmbeddedElements(elements, mapping, 'doctest2')
        [<music21.note.Note D>, <music21.note.Note E>, <music21.note.Note E>, <music21.note.Note D>]
        '''
        processed: list[t.Any] = []

        for eachElem in elements:
            if eachElem.tag in mapping:
                result: Music21Object | tuple[Music21Object, ...] | list[Music21Object] | None = (
                    mapping[eachElem.tag](eachElem)
                )
                if isinstance(result, list):
                    for eachObject in result:
                        processed.append(eachObject)
                elif result is not None:
                    processed.append(result)
            elif eachElem.tag not in _IGNORE_UNPROCESSED:
                environLocal.warn(_UNPROCESSED_SUBELEMENT.format(eachElem.tag, callerTag))

        return processed

    @staticmethod
    def _timeSigFromAttrs(elem: Element, prefix: str = '') -> meter.TimeSignature | None:
        '''
        From any tag with @meter.count and @meter.unit attributes, make a :class:`TimeSignature`.

        :param :class:`~xml.etree.ElementTree.Element` elem: An :class:`Element` with @meter.count
            and @meter.unit attributes.
        :returns: The corresponding time signature.
        :rtype: :class:`~music21.meter.TimeSignature`
        '''
        timeSig: meter.TimeSignature
        count: str | None = elem.get(prefix + 'count')
        unit: str | None = elem.get(prefix + 'unit')
        sym: str | None = elem.get(prefix + 'sym')
        # We ignore form="invis" because this usually happens in the presence of
        # <mensur>, which we (and music21) do not support, so we really need this guy.
        # form: str | None = elem.get(prefix + 'form')
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
        self,
        elem: Element,
        prefix: str = ''
    ) -> key.Key | key.KeySignature | None:
        '''
        From any tag with (at minimum) either @pname or @sig attributes, make a
        :class:`KeySignature` or :class:`Key`, as possible.

        elem is an :class:`Element` with either the @pname or @sig attribute

        Note that the prefix 'key.' can be passed in to parse @key.pname, @key.sig, etc

        Returns the key or key signature.
        '''
        theKeySig: key.KeySignature | key.Key | None = None
        theKey: key.Key | None = None

        pname: str | None = elem.get(prefix + 'pname')
        mode: str | None = elem.get(prefix + 'mode')
        accid: str | None = elem.get(prefix + 'accid')
        sig: str | None = elem.get(prefix + 'sig')
        form: str | None = elem.get(prefix + 'form')
        if pname is not None and mode is not None:
            accidental: str | None = self._accidentalFromAttr(accid)
            tonic: str
            if accidental is None:
                tonic = pname
            else:
                tonic = pname + accidental
            theKey = key.Key(tonic=tonic, mode=mode)

        if sig is not None:
            theKeySig = key.KeySignature(sharps=self._sharpsFromAttr(sig))
            if mode:
                theKeySig = theKeySig.asKey(mode=mode)

        output: key.KeySignature | key.Key | None
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

    @staticmethod
    def _transpositionFromAttrs(elem: Element) -> interval.Interval:
        '''
        From any element with the @trans.diat and @trans.semi attributes, make an :class:`Interval`
        that represents the interval of transposition from written to concert pitch.

        :param :class:`~xml.etree.ElementTree.Element` elem: An :class:`Element` with the
            @trans.diat and @trans.semi attributes.
        :returns: The interval of transposition from written to concert pitch.
        :rtype: :class:`music21.interval.Interval`
        '''
        transDiat: int = int(float(elem.get('trans.diat', 0)))
        transSemi: int = int(float(elem.get('trans.semi', 0)))

        # If the difference between transSemi and transDiat is greater than five per octave...
        if abs(transSemi - transDiat) > 5 * (abs(transSemi) // 12 + 1):
            # We need to add octaves to transDiat so it's the proper size. Otherwise,
            # intervalFromGenericAndChromatic() tries to create things like AAAAAAAAA5.
            # Except it actually just fails.

            # NB: we test this against transSemi because transDiat could be 0 when transSemi is a
            #     multiple of 12 *either* greater or less than 0.
            if transSemi < 0:
                transDiat -= 7 * (abs(transSemi) // 12)
            elif transSemi > 0:
                transDiat += 7 * (abs(transSemi) // 12)

        # NB: MEI uses zero-based unison rather than 1-based unison, so for music21 we must make
        # every diatonic interval one greater than it was. E.g., '@trans.diat="2"' in MEI means to
        # "transpose up two diatonic steps," which music21 would rephrase as "transpose up by a
        # diatonic third."
        if transDiat < 0:
            transDiat -= 1
        elif transDiat >= 0:
            transDiat += 1

        return interval.intervalFromGenericAndChromatic(
            interval.GenericInterval(transDiat),
            interval.ChromaticInterval(transSemi)
        )

    def _barlineFromAttr(
        self,
        attr: str | None
    ) -> bar.Barline | bar.Repeat | tuple[bar.Repeat, bar.Repeat]:
        '''
        Use :func:`_attrTranslator` to convert the value of a "left" or "right" attribute to a
        :class:`Barline` or :class:`Repeat` or occasionally a tuple of :class:`Repeat`. The only
        time a tuple is returned is when "attr" is ``'rptboth'``, in which case the end and start
        barlines are both returned.

        :param str attr: The MEI @left or @right attribute to convert to a barline.
        :returns: The barline.
        :rtype: :class:`music21.bar.Barline` or :class:`~music21.bar.Repeat` or list of them
        '''
        # NB: the MEI Specification says @left is used only for legacy-format conversions, so we'll
        #     just assume it's a @right attribute. Not a huge deal if we get this wrong (I hope).
        if attr and attr.startswith('rpt'):
            if 'rptboth' == attr:
                endingRpt = self._barlineFromAttr('rptend')
                startingRpt = self._barlineFromAttr('rptstart')
                if t.TYPE_CHECKING:
                    assert isinstance(endingRpt, bar.Repeat)
                    assert isinstance(startingRpt, bar.Repeat)
                return endingRpt, startingRpt
            elif 'rptend' == attr:
                return bar.Repeat('end')
            else:
                return bar.Repeat('start')
        else:
            return bar.Barline(self._attrTranslator(attr, 'right', self._BAR_ATTR_DICT))

    @staticmethod
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

    @staticmethod
    def safeGetSpannerByIdLocal(
        theId: str,
        spannerBundle: spanner.SpannerBundle
    ) -> spanner.Spanner | None:
        try:
            return spannerBundle.getByIdLocal(theId)[0]
        except IndexError:
            return None

    @staticmethod
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
        self,
        elem: Element,
        obj: note.NotRest,
    ) -> bool:
        '''
        If relevant, add a slur to an ``obj`` (object) that was created from an ``elem`` (element).

        :param elem: The :class:`Element` that caused creation of the ``obj``.
        :type elem: :class:`xml.etree.ElementTree.Element`
        :param obj: The musical object (:class:`Note`, :class:`Chord`, etc.) created from ``elem``,
            to which a slur might be attached.
        :type obj: :class:`music21.base.Music21Object`
        :returns: Whether at least one slur was added.
        :rtype: bool

        **A Note about Importing Slurs**

        Because of how the MEI format specifies slurs, the strategy required for proper import to
        music21 is not obvious. There are two ways to specify a slur:

        #. With a ``@slur`` attribute, in which case :func:`addSlurs` reads the attribute and
            manages creating a :class:`Slur` object, adding the affected objects to it, and
            storing the :class:`Slur` in the ``spannerBundle``.
        #. With a ``<slur>`` element, which requires pre-processing. In this case, :class:`Slur`
            objects must already exist in the ``spannerBundle``, and special attributes must be
            added to the affected elements (``@m21SlurStart`` to the element at the start of the
            slur and ``@m21SlurEnd`` to the element at the end). These attributes hold the ``id``
            of a :class:`Slur` in the ``spannerBundle``, allowing :func:`addSlurs` to find the
            slur and add ``obj`` to it.

        .. caution:: If an ``elem`` has an @m21SlurStart or @m21SlurEnd attribute that refer to an
            object not found in the ``spannerBundle``, the slur is silently dropped.
        '''
        addedSlur: bool = False

        def getSlurNumAndType(eachSlur: str) -> tuple[str, str]:
            # eachSlur is of the form "[i|m|t][1-6]"
            slurNum: str = eachSlur[1:]
            slurType: str = eachSlur[:1]
            return slurNum, slurType

        startStr: str | None = elem.get('m21SlurStart')
        endStr: str | None = elem.get('m21SlurEnd')
        if startStr is not None:
            addedSlur = self.safeAddToSpannerByIdLocal(obj, startStr, self.spannerBundle)
        if endStr is not None:
            addedSlur = self.safeAddToSpannerByIdLocal(obj, endStr, self.spannerBundle)

        slurStr: str | None = elem.get('slur')
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
                    self.spannerBundle.append(newSlur)
                    newSlur.addSpannedElements(obj)
                    addedSlur = True
                elif 't' == slurType:
                    addedSlur = self.safeAddToSpannerByIdLocal(obj, slurNum, self.spannerBundle)
                # 'm' is currently ignored; we may need it for cross-staff slurs

        return addedSlur

    def addOttavas(
        self,
        elem: Element,
        obj: note.NotRest,
    ) -> list[spanner.Spanner]:
        completedOttavas: list[spanner.Spanner] = []

        ottavaId: str = elem.get('m21OttavaStart', '')
        if ottavaId:
            self.safeAddToSpannerByIdLocal(obj, ottavaId, self.spannerBundle)

        ottavaId = elem.get('m21OttavaEnd', '')
        if ottavaId:
            ottava: spanner.Spanner | None = self.safeGetSpannerByIdLocal(
                ottavaId, self.spannerBundle
            )
            if ottava is not None:
                ottava.addSpannedElements(obj)
                completedOttavas.append(ottava)

        return completedOttavas

    def addHairpins(
        self,
        elem: Element,
        obj: note.GeneralNote,
    ):
        hairpinId: str = elem.get('m21HairpinStart', '')
        if hairpinId:
            self.safeAddToSpannerByIdLocal(obj, hairpinId, self.spannerBundle)

        hairpinId = elem.get('m21HairpinEnd', '')
        if hairpinId:
            hairpin: spanner.Spanner | None = self.safeGetSpannerByIdLocal(
                hairpinId, self.spannerBundle
            )
            if hairpin is not None:
                hairpin.addSpannedElements(obj)

    def addDirsDynamsTempos(
        self,
        elem: Element,
        obj: note.GeneralNote
    ):
        textsToProcess: dict[str, str] = {
            'm21Dir': elem.get('m21Dir', ''),
            'm21Dynam': elem.get('m21Dynam', ''),
            'm21Tempo': elem.get('m21Tempo', ''),
        }

        outputList: list[
            m21.expressions.TextExpression | m21.dynamics.Dynamic | m21.tempo.TempoIndication
        ] = []

        for prefix, text in textsToProcess.items():
            if not text:
                # no text in element, so ignore it
                continue

            place: str = elem.get(f'{prefix}Place', '')
            staff: str = elem.get(f'{prefix}Staff', '')
            if not staff:
                staff = self.staffNumberForNotes
            fontStyle: str = elem.get(f'{prefix}FontStyle', '')
            fontWeight: str = elem.get(f'{prefix}FontWeight', '')
            fontFamily: str = elem.get(f'{prefix}FontFamily', '')
            justify: str = elem.get(f'{prefix}Justify', '')

            # make the appropriate m21 object (TextExpression, Dynamic, TempoIndication)
            # and put it in a custom list in obj: obj.mei_dir_dynam_tempo_list
            te: m21.expressions.TextExpression = (
                self._textExpressionFromPieces(
                    text,
                    fontStyle,
                    fontWeight,
                    fontFamily,
                    justify,
                    place)
            )

            if prefix == 'm21Dir':
                outputList.append(te)
                continue

            if prefix == 'm21Dynam':
                dynam: m21.dynamics.Dynamic = self._dynamFromTextExpression(te)
                outputList.append(dynam)
                continue

            if prefix == 'm21Tempo':
                midiBPM: str = elem.get(f'{prefix}MidiBPM', '')
                mm: m21.tempo.MetronomeMark = (
                    self._metronomeMarkFromTextExpressionAndMidiBPMStr(te, midiBPM)
                )
                outputList.append(mm)

        if outputList:
            obj.mei_dir_dynam_tempo_list = outputList  # type: ignore

    def addArpeggio(
        self,
        elem: Element,
        obj: note.NotRest,
    ) -> list[spanner.Spanner]:
        completedArpeggioMarkSpanners: list[spanner.Spanner] = []

        # if appropriate, add this note/chord to an ArpeggioMarkSpanner
        arpId: str = elem.get('m21ArpeggioMarkSpanner', '')
        if arpId:
            arpSpanner: spanner.Spanner | None = (
                self.safeGetSpannerByIdLocal(arpId, self.spannerBundle)
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

    def _m21AccidentalNameFromAccid(self, accidStr: str) -> str:
        m21AccidName: str = ''
        if accidStr:
            accidName: str | None = self._ACCID_ATTR_DICT.get(accidStr, '')
            if accidName:
                m21AccidName = accidName
        return m21AccidName

    def addTrill(
        self,
        elem: Element,
        obj: note.NotRest,
    ) -> list[spanner.Spanner]:
        completedTrillExtensions: list[spanner.Spanner] = []
        # if appropriate, add this note/chord to a trillExtension
        trillExtId: str = elem.get('m21TrillExtensionStart', '')
        if trillExtId:
            self.safeAddToSpannerByIdLocal(obj, trillExtId, self.spannerBundle)
        trillExtId = elem.get('m21TrillExtensionEnd', '')
        if trillExtId:
            trillExt: spanner.Spanner | None = (
                self.safeGetSpannerByIdLocal(trillExtId, self.spannerBundle)
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
        m21AccidName: str = ''
        if accidUpper:
            m21AccidName = self._m21AccidentalNameFromAccid(accidUpper)
        elif accidLower:
            m21AccidName = self._m21AccidentalNameFromAccid(accidLower)
        trill = expressions.Trill()
        if m21AccidName:
            m21Accid: pitch.Accidental = pitch.Accidental(m21AccidName)
            m21Accid.displayStatus = True
            trill.accidental = m21Accid

        if self.staffNumberForNotes:
            # Now, resolve the Trill's ornamental pitch based on obj
            trill.resolveOrnamentalPitches(
                obj,
                keySig=self._currKeyForStaff(self.staffNumberForNotes)
            )
            self.updateAltersFromExpression(
                trill, obj, self.staffNumberForNotes
            )

        if place and place != 'place_unspecified':
            trill.placement = place
        else:
            trill.placement = None  # type: ignore

        obj.expressions.append(trill)

        return completedTrillExtensions

    def addMordent(
        self,
        elem: Element,
        obj: note.NotRest,
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
        m21AccidName: str = ''
        if accidUpper:
            m21AccidName = self._m21AccidentalNameFromAccid(accidUpper)
        elif accidLower:
            m21AccidName = self._m21AccidentalNameFromAccid(accidLower)

        if accidUpper:
            if not form:
                form = 'upper'

        if accidLower:
            if not form:
                form = 'lower'

        if not form:
            form = 'lower'  # I would prefer upper, but match Verovio

        if form == 'upper':
            # music21 calls an upper mordent (i.e that goes up from the main note)
            # an InvertedMordent.
            mordent = expressions.InvertedMordent(accidentalName=m21AccidName)
        elif form == 'lower':
            mordent = expressions.Mordent(accidentalName=m21AccidName)

        if m21AccidName:
            m21Accid: pitch.Accidental = pitch.Accidental(m21AccidName)
            m21Accid.displayStatus = True
            mordent.accidental = m21Accid

        # Now, resolve the mordent's ornamental pitch based on obj
        if self.staffNumberForNotes:
            mordent.resolveOrnamentalPitches(
                obj,
                keySig=self._currKeyForStaff(self.staffNumberForNotes)
            )
            self.updateAltersFromExpression(
                mordent, obj, self.staffNumberForNotes
            )


        # m21 mordents might not have placement... sigh...
        # But if I set it, it _will_ get exported to MusicXML (ha!).
        if place and place != 'place_unspecified':
            mordent.placement = place  # type: ignore
        else:
            mordent.placement = None  # type: ignore

        obj.expressions.append(mordent)

    def addTurn(
        self,
        elem: Element,
        obj: note.NotRest,
    ):
        # Check to see if this note/chord needs a turn, and if so,
        # make the Turn and append it to the note/chord's expressions.
        turn: expressions.Turn  # this includes InvertedTurn as well
        place: str = elem.get('m21Turn', '')
        if not place:
            return

        accidUpper: str = elem.get('m21TurnAccidUpper', '')
        accidLower: str = elem.get('m21TurnAccidLower', '')
        delayed: str = elem.get('m21TurnDelayed', '')
        form: str = elem.get('m21TurnForm', '')
        theType: str = elem.get('m21TurnType', '')

        if not form:
            if theType == 'slashed':
                form = 'lower'
            else:
                form = 'upper'  # default

        m21AccidNameUpper: str = ''
        m21AccidNameLower: str = ''
        if accidUpper:
            m21AccidNameUpper = self._m21AccidentalNameFromAccid(accidUpper)
        if accidLower:
            m21AccidNameLower = self._m21AccidentalNameFromAccid(accidLower)

        m21AccidUpper: pitch.Accidental | None = None
        if m21AccidNameUpper:
            m21AccidUpper = pitch.Accidental(m21AccidNameUpper)
            m21AccidUpper.displayStatus = True

        m21AccidLower: pitch.Accidental | None = None
        if m21AccidNameLower:
            m21AccidLower = pitch.Accidental(m21AccidNameLower)
            m21AccidLower.displayStatus = True


        delay: OrnamentDelay | OffsetQL = OrnamentDelay.NO_DELAY
        if delayed == 'true':
            # this is not a timed delay, because we have @startid, not @tstamp
            delay = OrnamentDelay.DEFAULT_DELAY

        if form == 'upper':
            turn = expressions.Turn(
                delay=delay,
                upperAccidental=m21AccidUpper,
                lowerAccidental=m21AccidLower
            )
        else:
            turn = expressions.InvertedTurn(
                delay=delay,
                upperAccidental=m21AccidUpper,
                lowerAccidental=m21AccidLower
            )

        # Now, resolve the turn's "other" pitch based on obj's pitch (or highest pitch
        # if obj is a chord with pitches)
        if self.staffNumberForNotes:
            turn.resolveOrnamentalPitches(
                obj,
                keySig=self._currKeyForStaff(self.staffNumberForNotes)
            )
            self.updateAltersFromExpression(
                turn, obj, self.staffNumberForNotes
            )

        if place and place != 'place_unspecified':
            turn.placement = place
        else:
            turn.placement = None  # type: ignore

        obj.expressions.append(turn)

    def updateAltersFromExpression(
        self,
        expr: expressions.Expression,
        obj: note.GeneralNote,
        staffNStr: str,
    ):
        if not isinstance(expr, (expressions.Trill, expressions.GeneralMordent, expressions.Turn)):
            return

        self.updateStaffAltersWithPitches(staffNStr, list(expr.ornamentalPitches))
        return

    @staticmethod
    def beamTogether(someThings: list[Music21Object]):
        '''
        Beam some things together. The function beams every object that has a :attr:`beams`
        attribute, leaving the other objects unmodified.

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

            nextThing: Music21Object | None = None
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

            prevThing: Music21Object | None = None
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

    @staticmethod
    def applyBreaksecs(someThings: list[Music21Object]):
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

            breaksecNum: int | None = None
            if not hasattr(thing, 'mei_breaksec'):
                continue

            try:
                breaksecNum = int(thing.mei_breaksec)  # type: ignore
            except Exception:
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

            nextThing: Music21Object | None = None
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

    @staticmethod
    def removeOctothorpe(xmlid: str | None) -> str | None:
        '''
        Given a string with an @xml:id to search for, remove a leading octothorpe, if present.

        >>> from converter21.mei import MeiReader
        >>> c = MeiReader()
        >>> c.removeOctothorpe('110a923d-a13a-4a2e-b85c-e1d438e4c5d6')
        '110a923d-a13a-4a2e-b85c-e1d438e4c5d6'
        >>> c.removeOctothorpe('#e46cbe82-95fc-4522-9f7a-700e41a40c8e')
        'e46cbe82-95fc-4522-9f7a-700e41a40c8e'
        '''
        if xmlid and xmlid.startswith('#'):
            return xmlid[1:]
        return xmlid

    def makeMetadata(self) -> metadata.Metadata:
        '''
        Produce metadata objects for all the metadata stored in the MEI header.

        :returns: A :class:`Metadata` object with some of the metadata stored in the MEI document.
        :rtype: :class:`music21.metadata.Metadata`
        '''
        meta = metadata.Metadata()
        work = self.documentRoot.find(f'.//{MEI_NS}work')
        if work is not None:
            # title, subtitle, and movement name
            meta = self.metaSetTitle(work, meta)
            # composer
            meta = self.metaSetComposer(work, meta)
            # date
            meta = self.metaSetDate(work, meta)

        return meta

    @staticmethod
    def metaSetTitle(work: Element, meta: metadata.Metadata) -> metadata.Metadata:
        '''
        From a <work> element, find the title, subtitle, and movement name (<tempo> element)
        and store the values in a :class:`Metadata` object.

        :param work: A <work> :class:`~xml.etree.ElementTree.Element` with metadata you want
            to find.
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
            # Since m21.Metadata doesn't actually have a "subtitle" attribute, we'll put the
            # subtitle in the title.
            meta.title = f'{meta.title} ({subtitle})'

        tempoEl = work.find(f'./{MEI_NS}tempo')
        if tempoEl is not None:
            meta.movementName = tempoEl.text

        return meta

    @staticmethod
    def metaSetComposer(work: Element, meta: metadata.Metadata) -> metadata.Metadata:
        '''
        From a <work> element, find the composer(s) and store the values in a :class:`Metadata`
        object.

        :param work: A <work> :class:`~xml.etree.ElementTree.Element` with metadata you want
            to find.
        :param meta: The :class:`~music21.metadata.Metadata` object in which to store the metadata.
        :return: The ``meta`` argument, having relevant metadata added.
        '''
        composers = []
        persName: Element | None
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

    def metaSetDate(self, work: Element, meta: metadata.Metadata) -> metadata.Metadata:
        '''
        From a <work> element, find the date (range) of composition and store the values in a
        :class:`Metadata` object.

        :param work: A <work> :class:`~xml.etree.ElementTree.Element` with metadata you want
            to find.
        :param meta: The :class:`~music21.metadata.Metadata` object in which to store the metadata.
        :return: The ``meta`` argument, having relevant metadata added.
        '''
        date = work.find(f'./{MEI_NS}history/{MEI_NS}creation/{MEI_NS}date')
        if date is not None:  # must use explicit "is not None" for an Element
            isodate: str | None = date.get('isodate')
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
                dateStart = date.get('notbefore') or date.get('startdate')
                dateEnd = date.get('notafter') or date.get('enddate')
                if dateStart and dateEnd:
                    meta.dateCreated = metadata.DateBetween((dateStart, dateEnd))

        return meta

    @staticmethod
    def scaleToTuplet(
        objs: Music21Object | list[Music21Object],
        elem: Element
    ) -> Music21Object | list[Music21Object]:
        '''
        Scale the duration of some objects by a ratio indicated by a tuplet. The ``elem`` must have
        the @m21TupletNum and @m21TupletNumbase attributes set, and optionally the @m21TupletSearch
        or @m21TupletType attributes.

        The @m21TupletNum and @m21TupletNumbase attributes should be equal to the @num and @numbase
        values of the <tuplet> or <tupletSpan> that indicates this tuplet.

        The @m21TupletSearch attribute, whose value must either be ``'start'`` or ``'end'``, is
        required when a <tupletSpan> does not include a @plist attribute. It indicates that the
        importer must "search" for a tuplet near the end of the import process, which involves
        scaling the durations of all objects discovered between those with the "start" and "end"
        search values.

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
            bracketVisible: str | None = None
            bracketPlace: str | None = None
            numVisible: str | None = None
            numPlace: str | None = None
            numFormat: str | None = None

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

                bracketVisible = elem.get('m21TupletBracketVisible')
                bracketPlace = elem.get('m21TupletBracketPlace')
                numVisible = elem.get('m21TupletNumVisible')
                numPlace = elem.get('m21TupletNumPlace')
                numFormat = elem.get('m21TupletNumFormat')
                if bracketVisible is not None:
                    obj.m21TupletBracketVisible = bracketVisible  # type: ignore
                if bracketPlace is not None:
                    obj.m21TupletBracketPlace = bracketPlace  # type: ignore
                if numVisible is not None:
                    obj.m21TupletNumVisible = numVisible  # type: ignore
                if numPlace is not None:
                    obj.m21TupletNumPlace = numPlace  # type: ignore
                if numFormat is not None:
                    obj.m21TupletNumFormat = numFormat  # type: ignore

            else:
                num: str | None = elem.get('m21TupletNum')
                numbase: str | None = elem.get('m21TupletNumbase')
                if num and numbase:
                    newTuplet = duration.Tuplet(
                        numberNotesActual=int(num),
                        numberNotesNormal=int(numbase),
                        durationNormal=obj.duration.type,
                        durationActual=obj.duration.type
                    )

                    tupletType: str | None = elem.get('m21TupletType')
                    if tupletType is not None:
                        newTuplet.type = tupletType  # type: ignore
                    elif elem.get('tuplet', '').startswith('i'):
                        newTuplet.type = 'start'
                    elif elem.get('tuplet', '').startswith('t'):
                        newTuplet.type = 'stop'

                    bracketVisible = elem.get('m21TupletBracketVisible')
                    bracketPlace = elem.get('m21TupletBracketPlace')
                    numVisible = elem.get('m21TupletNumVisible')
                    numPlace = elem.get('m21TupletNumPlace')
                    numFormat = elem.get('m21TupletNumFormat')

                    # placement (MEI has two: num and bracket placement, music21 has only one)
                    placement: str | None = None
                    if bracketVisible is None or bracketVisible == 'true':
                        placement = bracketPlace
                    if placement is None and (numVisible is None or numVisible == 'true'):
                        placement = numPlace
                    if placement is not None:
                        newTuplet.placement = placement  # type: ignore
                    else:
                        newTuplet.placement = None  # type: ignore

                    # bracket visibility
                    if bracketVisible is None or bracketVisible == 'true':
                        newTuplet.bracket = True
                    elif bracketVisible == 'false':
                        newTuplet.bracket = False

                    # num visibility (True/False) and format('number'/'ratio')
                    # (MEI has visibility and format, music21 has visibility for each number)
                    if numVisible == 'false':
                        newTuplet.tupletActualShow = None
                        newTuplet.tupletNormalShow = None
                    elif numVisible is None or numVisible == 'true':
                        if numFormat is None or numFormat == 'count':
                            newTuplet.tupletActualShow = 'number'
                            newTuplet.tupletNormalShow = None
                        elif numFormat == 'ratio':
                            newTuplet.tupletActualShow = 'number'
                            newTuplet.tupletNormalShow = 'number'

                    obj.duration.appendTuplet(newTuplet)

        if wasList:
            return objs
        else:
            return objs[0]

    def _guessTuplets(self, theLayer: list[Music21Object]) -> list[Music21Object]:
        # TODO: nested tuplets don't work when they're both specified with <tupletSpan>
        # TODO: adjust this to work with cross-measure tuplets (i.e., where only the
        # TODO: "start" or "end" is found in theLayer)
        '''
        Given a list of music21 objects, possibly containing :attr:`m21TupletSearch`,
        :attr:`m21TupletNum`, and :attr:`m21TupletNumbase` attributes, adjust the durations of the
        objects as specified by those "m21Tuplet" attributes, then remove the attributes.

        This function finishes processing for tuplets encoded as a <tupletSpan> where @startid and
        @endid are indicated, but not @plist. Knowing the starting and ending object in the tuplet,
        we can guess that all the Note, Rest, and Chord objects between the starting and ending
        objects in that <layer> are part of the tuplet. (Grace notes retain a 0.0 duration).

        .. note:: At the moment, this will likely only work for simple tuplets---not nested tuplets.

        :param theLayer: Objects from the <layer> in which to search for objects that have the
            :attr:`m21TupletSearch` attribute.
        :type theScore: list
        :returns: The same list, with durations adjusted to account for tuplets.
        '''
        # NB: this is a hidden function because it uses the "m21TupletSearch" attribute, which
        # are only supposed to be used within the MEI import module.

        inATuplet: bool = False  # we hit m21TupletSearch=='start' but not 'end' yet
        tupletNum: str | None = None
        tupletNumbase: str | None = None
        tupletBracketVisible: str | None = None
        tupletBracketPlace: str | None = None
        tupletNumVisible: str | None = None
        tupletNumPlace: str | None = None
        tupletNumFormat: str | None = None
        fakeTupletElem: Element | None = None

        for eachNote in theLayer:
            # we'll skip objects that don't have a duration
            if not isinstance(eachNote, (note.Note, note.Rest, chord.Chord)):
                continue

            if (hasattr(eachNote, 'm21TupletSearch')
                    and eachNote.m21TupletSearch == 'start'):  # type: ignore
                inATuplet = True
                tupletNum = eachNote.m21TupletNum  # type: ignore
                tupletNumbase = eachNote.m21TupletNumbase  # type: ignore
                if hasattr(eachNote, 'm21TupletBracketVisible'):
                    tupletBracketVisible = eachNote.m21TupletBracketVisible  # type: ignore
                    del eachNote.m21TupletBracketVisible  # type: ignore
                if hasattr(eachNote, 'm21TupletBracketPlace'):
                    tupletBracketPlace = eachNote.m21TupletBracketPlace  # type: ignore
                    del eachNote.m21TupletBracketPlace  # type: ignore
                if hasattr(eachNote, 'm21TupletNumVisible'):
                    tupletNumVisible = eachNote.m21TupletNumVisible  # type: ignore
                    del eachNote.m21TupletNumVisible  # type: ignore
                if hasattr(eachNote, 'm21TupletNumPlace'):
                    tupletNumPlace = eachNote.m21TupletNumPlace  # type: ignore
                    del eachNote.m21TupletNumPlace  # type: ignore
                if hasattr(eachNote, 'm21TupletNumFormat'):
                    tupletNumFormat = eachNote.m21TupletNumFormat  # type: ignore
                    del eachNote.m21TupletNumFormat  # type: ignore

                del eachNote.m21TupletSearch  # type: ignore
                del eachNote.m21TupletNum  # type: ignore
                del eachNote.m21TupletNumbase  # type: ignore

                if t.TYPE_CHECKING:
                    assert tupletNum is not None
                    assert tupletNumbase is not None

                fakeTupletElem = Element('',
                                         m21TupletNum=tupletNum,
                                         m21TupletNumbase=tupletNumbase)
                if tupletBracketVisible is not None:
                    fakeTupletElem.set('m21TupletBracketVisible', tupletBracketVisible)
                if tupletBracketPlace is not None:
                    fakeTupletElem.set('m21TupletBracketPlace', tupletBracketPlace)
                if tupletNumVisible is not None:
                    fakeTupletElem.set('m21TupletNumVisible', tupletNumVisible)
                if tupletNumPlace is not None:
                    fakeTupletElem.set('m21TupletNumPlace', tupletNumPlace)
                if tupletNumFormat is not None:
                    fakeTupletElem.set('m21TupletNumFormat', tupletNumFormat)

            if inATuplet:
                if t.TYPE_CHECKING:
                    assert fakeTupletElem is not None

                self.scaleToTuplet(eachNote, fakeTupletElem)

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
        self,
        elem: Element,
        allPartNs: tuple[str, ...],
        parseStaffGrps: bool = True
    ) -> dict[str, list[Music21Object] | dict[str, Music21Object]]:
        '''
        <scoreDef> Container for score meta-information.

        In MEI 2013: pg.431 (445 in PDF) (MEI.shared module)

        This function returns a dictionary with objects that may relate to the entire score, to all
        parts at a particular moment, or only to a specific part at a particular moment. The
        dictionary keys determine the object's scope. If the key is...

        * ``'whole-score objects'``, it applies to the entire score (e.g., page size);
        * ``'all-part objects'``, it applies to all parts at the moment this <scoreDef> appears;
        * the @n attribute of a part, it applies only to that part at the moment this <scoreDef>
            appears.

        While the multi-part objects will be held in a list, the single-part objects will be in a
        dict like that returned by :func:`staffDefFromElement`.

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
        >>> from converter21.mei import MeiReader
        >>> from xml.etree import ElementTree as ET
        >>> c = MeiReader()
        >>> scoreDef = ET.fromstring(meiDoc)
        >>> result = c.scoreDefFromElement(scoreDef, ['1','2','3'], parseStaffGrps=True)
        >>> len(result)
        6
        >>> result['1']
        {'instrument': <music21.instrument.Clarinet '1: Clarinet: Clarinet'>}
        >>> result['2']
        {'instrument': <music21.instrument.Flute '2: Flute: Flute'>}
        >>> result['3']
        {'instrument': <music21.instrument.Violin '3: Violin: Violin'>}
        >>> result['all-part objects']
        [<music21.meter.TimeSignature 3/4>]
        >>> result['whole-score objects'].keys()
        dict_keys(['staff-groups', 'parts'])
        >>> len(result['whole-score objects']['staff-groups'])
        2
        >>> len(result['whole-score objects']['parts'])
        3

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
        post: dict[str, list[Music21Object] | dict[str, Music21Object]] = {
            topPart: [],
            allParts: [],
            wholeScore: {}
        }

        # 0.) process top-part attributes (none actually get posted yet, but...)
        bpmStr: str = elem.get('midi.bpm', '')
        if bpmStr:
            # save it off, for the very first MetronomeMark to use (if necessary)
            self.pendingMIDIBPM = bpmStr

        # 1.) process all-part attributes
        pap = post[allParts]
        if t.TYPE_CHECKING:
            assert isinstance(pap, list)
        postAllParts: list[Music21Object] = pap

        # --> time signature
        if elem.get('meter.count') is not None or elem.get('meter.sym') is not None:
            timesig = self._timeSigFromAttrs(elem, prefix='meter.')
            if timesig is not None:
                postAllParts.append(timesig)
        meterSigElem: Element | None = elem.find(f'{MEI_NS}meterSig')
        if meterSigElem is not None:
            timesig = self._timeSigFromAttrs(meterSigElem)
            if timesig is not None:
                postAllParts.append(timesig)

        # --> key signature
        if elem.get('key.pname') is not None or elem.get('key.sig') is not None:
            keysig = self._keySigFromAttrs(elem, prefix='key.')
            if keysig is not None:
                postAllParts.append(keysig)
        keySigElem: Element | None = elem.find(f'{MEI_NS}keySig')
        if keySigElem is not None:
            keysig = self._keySigFromAttrs(keySigElem)
            if keysig is not None:
                postAllParts.append(keysig)

        # 2.) staff-specific things (from contained <staffGrp> >> <staffDef>)
        fakeTopLevelGroup: M21StaffGroupDescriptionTree | None = None
        topLevelGroupDescs: list[M21StaffGroupDescriptionTree] = []

        topLevelStaffGrps: list[Element] = elem.findall(f'{MEI_NS}staffGrp')
        if len(topLevelStaffGrps) == 0:
            return post

        if parseStaffGrps:
            if len(topLevelStaffGrps) > 1:
                # There is no outer group, so make a fake one.
                fakeTopLevelGroup = M21StaffGroupDescriptionTree()
                fakeTopLevelGroup.symbol = 'none'  # no visible bracing
                fakeTopLevelGroup.barTogether = False  # no barline across the staves

            # We process the list of staffGrp elements twice, once to gather up a tree of
            # staff group descriptions (symbol, barTogether, staff numbers), and once to
            # gather up a dictionary of staff definition Music21Objects in a dictionary
            # per staff (intrument, keysig, metersig, etc), keyed by staff number).

            # Gather up the M21StaffGroupDescriptionTree.
            for eachGrp in topLevelStaffGrps:
                groupDesc: M21StaffGroupDescriptionTree = (
                    self.staffGroupDescriptionTreeFromStaffGrp(
                        eachGrp,
                        fakeTopLevelGroup  # will be None if len(topLevelStaffGrps) == 1
                    )
                )
                topLevelGroupDescs.append(groupDesc)

        # Gather up the staffDefDict.
        for eachGrp in topLevelStaffGrps:
            post.update(self.staffGrpFromElement(eachGrp))

        if parseStaffGrps:
            # process the staffGroup description tree, generating a list of m21 StaffGroup objects.
            # Put them in post[wholeScore].
            pws = post[wholeScore]
            if t.TYPE_CHECKING:
                assert isinstance(pws, dict)
            postWholeScore: dict[str, t.Any] = pws

            # If we had to make a fake top-level group desc, use that.
            # Otherwise there is only one top-level group desc in the list, use that.
            topLevelGroup: M21StaffGroupDescriptionTree = (
                fakeTopLevelGroup or topLevelGroupDescs[0]
            )

            staffGroups: list[m21.layout.StaffGroup]
            parts: list[m21.stream.Part]
            partNs: list[str]
            staffGroups, parts, partNs = (
                self.processStaffGroupDescriptionTree(topLevelGroup, allPartNs)
            )
            if partNs != list(allPartNs):
                raise MeiInternalError(
                    'processStaffGroupDescriptionTree did not produce allPartNs'
                )

            partsPerN: dict[str, m21.stream.Part] = {}
            for staffN, part in zip(allPartNs, parts):
                partsPerN[staffN] = part

            postWholeScore['staff-groups'] = staffGroups
            postWholeScore['parts'] = partsPerN

        return post

    _MEI_STAFFGROUP_SYMBOL_TO_M21: dict[str, str] = {
        # m21 symbol can be 'brace', 'bracket', 'square', 'line', None
        # mei symbol can be 'brace', 'bracket', 'bracketsq', 'line', 'none'
        # In M21StaffGroupDescriptionTree we use the m21 symbols (except we use 'none')
        'brace': 'brace',
        'bracket': 'bracket',
        'bracketsq': 'square',
        'line': 'line',
        'none': 'none'
    }

    _MEI_BAR_THRU_TO_M21_BAR_TOGETHER: dict[str, bool] = {
        'false': False,
        'true': True,
        '': False,
    }

    def staffGroupDescriptionTreeFromStaffGrp(
        self,
        elem: Element,
        parentGroupDesc: M21StaffGroupDescriptionTree | None
    ) -> M21StaffGroupDescriptionTree:
        staffGroupTag: str = f'{MEI_NS}staffGrp'
        staffDefTag: str = f'{MEI_NS}staffDef'

        if elem.tag != staffGroupTag:
            raise MeiInternalError('expected <{staffGroupTag}>, got <{elem.tag}>')

        # Set up a groupDesc for this group (elem), and insert it in parentGroupDesc tree.
        thisGroupDesc: M21StaffGroupDescriptionTree = M21StaffGroupDescriptionTree()
        symbol: str = self._MEI_STAFFGROUP_SYMBOL_TO_M21.get(elem.get('symbol', 'none'), 'none')
        thisGroupDesc.symbol = symbol
        thisGroupDesc.barTogether = (
            self._MEI_BAR_THRU_TO_M21_BAR_TOGETHER.get(elem.get('bar.thru', ''), '')
        )

        # check for 'Mensurstrich' (barline between staves only, doesn't cross staff)
        barMethod: str = elem.get('bar.method', '')
        if not barMethod:
            # try the old MEI 3.0 attribute @barplace, which has the same values
            barMethod = elem.get('barplace', '')
        if barMethod == 'mensur':
            thisGroupDesc.barTogether = 'Mensurstrich'

        # check for any group label
        inst: m21.instrument.Instrument | None = (
            self._instrumentFromStaffDefOrStaffGrp(elem)
        )
        if inst is not None:
            # Put inst.name and inst.abbreviation into thisGroupDesc.groupName/.groupAbbrev
            thisGroupDesc.instrument = inst

        if parentGroupDesc is not None:
            parentGroupDesc.children.append(thisGroupDesc)
            thisGroupDesc.parent = parentGroupDesc

        # Add any staves and nested groups to thisGroupDesc
        for el in elem.findall('*'):
            nStr: str = el.get('n', '')
            if nStr and (el.tag == staffDefTag):
                # yes, we already have the instrument computed; simplest to just compute it again
                staffInst: m21.instrument.Instrument | None = (
                    self._instrumentFromStaffDefOrStaffGrp(el)
                )
                # We put this nStr and staffInst in the current group (noted as 'owned')
                # and as 'referenced' in current group and all its ancestors.
                ancestor: M21StaffGroupDescriptionTree | None = thisGroupDesc
                while ancestor is not None:
                    if ancestor is thisGroupDesc:
                        thisGroupDesc.ownedStaffIds.append(nStr)
                        thisGroupDesc.ownedStaffInstruments.append(staffInst)
                    ancestor.staffIds.append(nStr)
                    ancestor.staffInstruments.append(staffInst)
                    ancestor = ancestor.parent

            # recurse if there are groups within this group
            elif el.tag == staffGroupTag:
                self.staffGroupDescriptionTreeFromStaffGrp(
                    el, thisGroupDesc
                )

        return thisGroupDesc

    @staticmethod
    def _groupShouldContainPartStaffs(
        groupDescTree: M21StaffGroupDescriptionTree
    ) -> bool:
        numStaves: int = len(groupDescTree.staffIds)
        if numStaves in (2, 3):
            if M21Utilities.isMultiStaffInstrument(groupDescTree.instrument):
                return True

            commonMultiStaffInstrument: m21.instrument.Instrument | None = None
            for inst in groupDescTree.staffInstruments:
                if inst is None:
                    continue

                if not M21Utilities.isMultiStaffInstrument(inst):
                    # found a non-multistaff instrument, get the heck out
                    return False

                if commonMultiStaffInstrument is None:
                    commonMultiStaffInstrument = inst
                    continue

                if inst.instrumentName != commonMultiStaffInstrument.instrumentName:
                    # found a non-common instrument in the staffGroup, get the heck out
                    return False

                if inst.instrumentAbbreviation != commonMultiStaffInstrument.instrumentAbbreviation:
                    # found a non-common instrument in the staffGroup, get the heck out
                    return False

            if commonMultiStaffInstrument is not None:
                # if there is a common multi-staff instrument we do partStaffs
                return True

            if numStaves == 2:
                # if there are NO instruments at all, and exactly two staves,
                # we assume Piano, and do partStaffs
                return True

        return False

    def processStaffGroupDescriptionTree(
        self,
        groupDescTree: M21StaffGroupDescriptionTree,
        allPartNs: tuple[str, ...]
    ) -> tuple[list[m21.layout.StaffGroup], list[m21.stream.Part], list[str]]:
        '''
        processStaffGroupDescriptionTree returns three lists: the StaffGroups generated,
        the Parts/PartStaffs contained by those StaffGroups, and the staffDef "n" number
        for those Parts/PartStaffs.  The StaffGroup list length will be <= the Part/PartStaff
        list length, and the staff ids list length will be == the Part/PartStaff list length.
        '''
        if groupDescTree is None:
            return ([], [], [])
        if not groupDescTree.staffIds:
            return ([], [], [])

        staffGroups: list[m21.layout.StaffGroup] = []
        staves: list[m21.stream.Part] = []
        staffIds: list[int | str] = []

        # top-level staffGroup for this groupDescTree
        staffGroups.append(m21.layout.StaffGroup())

        # Iterate over each sub-group (check for owned groups of staves between subgroups)
        # Process owned groups here, recurse to process sub-groups
        staffIdsToProcess: set[int | str] = set(groupDescTree.staffIds)

        makePartStaffs: bool = self._groupShouldContainPartStaffs(groupDescTree)
        if makePartStaffs:
            if groupDescTree.instrument:
                inst: m21.instrument.Instrument = groupDescTree.instrument
                staffGroups[0].name = (
                    inst.partName or inst.instrumentName or ''
                )
                staffGroups[0].abbreviation = (
                    inst.partAbbreviation or inst.instrumentAbbreviation or ''
                )

        part: m21.stream.Part | m21.stream.PartStaff
        for subgroup in groupDescTree.children:
            firstStaffIdInSubgroup: int | str = subgroup.staffIds[0]

            # 1. any owned group just before this subgroup
            # (while loop will not execute if there is no owned group before this subgroup)
            for ownedStaffId, ownedStaffInstrument in zip(
                groupDescTree.ownedStaffIds, groupDescTree.ownedStaffInstruments
            ):
                if ownedStaffId == firstStaffIdInSubgroup:
                    # we're done with this owned group (there may be another one later)
                    break

                if ownedStaffId not in staffIdsToProcess:
                    # we already did this one
                    continue

                if makePartStaffs:
                    part = m21.stream.PartStaff()
                else:
                    part = m21.stream.Part()
                    if ownedStaffInstrument is not None:
                        part.partName = (
                            ownedStaffInstrument.partName
                            or ownedStaffInstrument.instrumentName
                            or ''
                        )
                        part.partAbbreviation = (
                            ownedStaffInstrument.partAbbreviation
                            or ownedStaffInstrument.instrumentAbbreviation
                            or ''
                        )

                staffGroups[0].addSpannedElements(part)
                staves.append(part)
                staffIds.append(ownedStaffId)

                staffIdsToProcess.remove(ownedStaffId)

            # 2. now the subgroup (returns a list of StaffGroups for the subtree)
            newStaffGroups: list[m21.layout.StaffGroup]
            newStaves: list[m21.stream.Part]
            newIds: list[str]

            newStaffGroups, newStaves, newIds = (
                self.processStaffGroupDescriptionTree(subgroup, allPartNs)
            )

            # add newStaffGroups to staffGroups
            staffGroups += newStaffGroups

            # add newStaves to staves and to our top-level staffGroup (staffGroups[0])
            staves += newStaves
            staffGroups[0].addSpannedElements(newStaves)

            # add newIds to staffIds
            staffIds += newIds

            # remove newIds from staffIdsToProcess
            staffIdsProcessed: set[str] = set(newIds)  # for speed of "in" checking
            staffIdsToProcess = {
                sid for sid in staffIdsToProcess if sid not in staffIdsProcessed
            }

        # done with everything but the very last owned group (if present)
        if staffIdsToProcess:
            # 3. any unprocessed owned group just after the last subgroup
            for ownedStaffId, ownedStaffInstrument in zip(
                groupDescTree.ownedStaffIds, groupDescTree.ownedStaffInstruments
            ):
                if ownedStaffId not in staffIdsToProcess:
                    # we already did this one
                    continue

                if makePartStaffs:
                    part = m21.stream.PartStaff()
                else:
                    part = m21.stream.Part()
                    if ownedStaffInstrument is not None:
                        part.partName = (
                            ownedStaffInstrument.partName
                            or ownedStaffInstrument.instrumentName
                            or ''
                        )
                        part.partAbbreviation = (
                            ownedStaffInstrument.partAbbreviation
                            or ownedStaffInstrument.instrumentAbbreviation
                            or ''
                        )

                staffGroups[0].addSpannedElements(part)
                staves.append(part)
                staffIds.append(ownedStaffId)

                staffIdsToProcess.remove(ownedStaffId)

        # assert that we are done
        assert not staffIdsToProcess

        # configure our top-level staffGroup
        sg: m21.layout.StaffGroup = staffGroups[0]
        sg.symbol = groupDescTree.symbol
        sg.barTogether = groupDescTree.barTogether

        # reverse the staff groups list, because we also do that in HumdrumFile
        # (read the comment there).
        returnStaffGroups: list[m21.layout.StaffGroup] = list(reversed(staffGroups))
        returnStaffIds: list[str] = staffIds  # type: ignore

        return (returnStaffGroups, staves, returnStaffIds)

    def staffGrpFromElement(
        self,
        elem: Element,
        staffDefDict: dict[str, list[Music21Object] | dict[str, Music21Object]] | None = None,
    ) -> dict[str, list[Music21Object] | dict[str, Music21Object]]:
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
        :returns: Dictionary where keys are the @n attribute on a contained <staffDef>, and values
            are the result of calling :func:`staffDefFromElement` with that <staffDef>.

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

        - MEI.shared: grpSym
        '''

        staffDefTag = f'{MEI_NS}staffDef'
        staffGroupTag = f'{MEI_NS}staffGrp'

        staffDefDict = staffDefDict if staffDefDict is not None else {}

        for el in elem.findall('*'):
            # return all staff defs in this staff group
            nStr: str = el.get('n', '')
            if nStr and (el.tag == staffDefTag):
                self.staffNumberForDef = nStr
                staffDefDict[nStr] = self.staffDefFromElement(el)
                self.staffNumberForDef = ''

            # recurse if there are more groups, append to the working staffDefDict
            elif el.tag == staffGroupTag:
                self.staffGrpFromElement(el, staffDefDict)

        return staffDefDict

    def _instrumentFromStaffDefOrStaffGrp(
        self,
        elem: Element,
    ) -> m21.instrument.Instrument | None:
        inst: m21.instrument.Instrument | None = None

        instrDefElem = elem.find(f'{MEI_NS}instrDef')
        label: str = ''
        labelAbbr: str = ''
        labelEl: Element | None = elem.find(f'{MEI_NS}label')
        labelAbbrEl: Element | None = elem.find(f'{MEI_NS}labelAbbr')
        if labelEl is not None:
            label = labelEl.text or ''
        else:
            label = elem.get('label', '')
        if labelAbbrEl is not None:
            labelAbbr = labelAbbrEl.text or ''
        else:
            labelAbbr = elem.get('label.abbr', '')

        if instrDefElem is not None:
            inst = self.instrDefFromElement(instrDefElem)
        else:
            try:
                inst = m21.instrument.fromString(label)
            except m21.instrument.InstrumentException:
                pass

        # --> transposition
        if elem.get('trans.semi') is not None:
            if inst is None:
                # make an instrument, or the transposition will be lost
                inst = m21.instrument.Instrument()
            inst.transposition = self._transpositionFromAttrs(elem)

        if (label or labelAbbr) and inst is None:
            # make an instrument, or that staff label/abbrev will be lost
            inst = m21.instrument.Instrument()

        if inst is not None:
            # add the staff label/abbrev and the partId
            inst.partName = label
            inst.partAbbreviation = labelAbbr
            inst.partId = elem.get('n')

        return inst

    def staffDefFromElement(
        self,
        elem: Element,
    ) -> dict[str, Music21Object]:
        '''
        <staffDef> Container for staff meta-information.

        In MEI 2013: pg.445 (459 in PDF) (MEI.shared module)

        :returns: A dict with various types of metadata information, depending on what is specified
            in this <staffDef> element. Read below for more information.
        :rtype: dict

        **Possible Return Values**

        The contents of the returned dictionary depend on the contents of the <staffDef> element.
        The dictionary keys correspond to types of information. Possible keys include:

        - ``'instrument'``: for a :class:`music21.instrument.Instrument` subclass
        - ``'clef'``: for a :class:`music21.clef.Clef` subclass
        - ``'key'``: for a :class:`music21.key.Key` or :class:`~music21.key.KeySignature` subclass
        - ``'meter'``: for a :class:`music21.meter.TimeSignature`

        **Examples**

        This <staffDef> only returns a single item.

        >>> meiDoc = """<?xml version="1.0" encoding="UTF-8"?>
        ... <staffDef n="1" label="Clarinet" xmlns="http://www.music-encoding.org/ns/mei"/>
        ... """
        >>> from converter21.mei import MeiReader
        >>> from xml.etree import ElementTree as ET
        >>> c = MeiReader()
        >>> staffDef = ET.fromstring(meiDoc)
        >>> result = c.staffDefFromElement(staffDef)
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
        >>> from xml.etree import ElementTree as ET
        >>> staffDef = ET.fromstring(meiDoc)
        >>> result = c.staffDefFromElement(staffDef)
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
        tagToFunction: dict[str, t.Callable[
            [Element],
            t.Any]
        ] = {
            f'{MEI_NS}clef': self.clefFromElement,
            f'{MEI_NS}keySig': self.keySigFromElementInStaffDef,
            f'{MEI_NS}meterSig': self.timeSigFromElement,
        }

        post: dict[str, Music21Object] = {}

        # first make the Instrument
        inst: m21.instrument.Instrument | None = (
            self._instrumentFromStaffDefOrStaffGrp(elem)
        )
        if inst is not None:
            post['instrument'] = inst

        # process other staff-specific information
        # --> time signature
        if elem.get('meter.count') is not None or elem.get('meter.sym') is not None:
            timesig = self._timeSigFromAttrs(elem, prefix='meter.')
            if timesig is not None:
                post['meter'] = timesig

        # --> key signature
        updateStaffKeyAndAlters: bool = False
        if elem.get('key.pname') is not None or elem.get('key.sig') is not None:
            keysig = self._keySigFromAttrs(elem, prefix='key.')
            if keysig is not None:
                post['key'] = keysig
                updateStaffKeyAndAlters = True

        # --> clef
        if elem.get('clef.shape') is not None:
            shape: str | None = elem.get('clef.shape')
            line: str | None = elem.get('clef.line')
            dis: str | None = elem.get('clef.dis')
            displace: str | None = elem.get('clef.dis.place')
            attribDict: dict[str, str] = {}
            if shape:
                attribDict['shape'] = shape
            if line:
                attribDict['line'] = line
            if dis:
                attribDict['dis'] = dis
            if displace:
                attribDict['dis.place'] = displace
            el = Element('clef', attribDict)
            clefObj = self.clefFromElement(el)
            if clefObj is not None:
                post['clef'] = clefObj

        embeddedItems = self._processEmbeddedElements(
            elem.findall('*'), tagToFunction, elem.tag
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
            if self.staffNumberForDef:
                self.updateStaffKeyAndAltersWithNewKey(
                    self.staffNumberForDef,
                    t.cast(key.KeySignature, post['key']),
                )

        return post


    def updateStaffKeyAndAltersWithNewKey(
        self,
        staffNStr: str,
        newKey: key.Key | key.KeySignature | None,
    ):
        self.currKeyPerStaff[staffNStr] = newKey
        self.currentImpliedAltersPerStaff[staffNStr] = M21Utilities.getAltersForKey(newKey)

    def updateStaffAltersWithPitches(
        self,
        staffNStr: str,
        pitches: t.Sequence[pitch.Pitch],
    ):
        # every note and chord (and Trill/Mordent/Turn) flows through this routine
        if self.currentImpliedAltersPerStaff.get(staffNStr, None) is None:
            # If there is no alters list for this staff, that means we haven't
            # seen a key yet for this staff.  Assume no flats/sharps.
            self.currentImpliedAltersPerStaff[staffNStr] = M21Utilities.getAltersForKey(None)

        for thePitch in pitches:
            alterIdx: int = M21Utilities.pitchToBase7(thePitch)
            alter: int = 0
            if thePitch.accidental is not None:
                alter = int(thePitch.accidental.alter)
            self.currentImpliedAltersPerStaff[staffNStr][alterIdx] = int(alter)

    def updateStaffAltersForMeasureStart(
        self,
        staffNStr: str
    ):
        # Restores the staff's alters list to just the current key (removing any
        # other accidentals seen)
        self.currentImpliedAltersPerStaff[staffNStr] = (
            M21Utilities.getAltersForKey(self._currKeyForStaff(staffNStr))
        )

    def dotFromElement(
        self,
        elem: Element,  # pylint: disable=unused-argument
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
        self,
        elem: Element,
    ) -> list[articulations.Articulation]:
        '''
        <artic> An indication of how to play a note or chord.

        In MEI 2013: pg.259 (273 in PDF) (MEI.shared module)

        :returns: A list of :class:`~music21.articulations.Articulation` objects.

        **Examples**

        This function is normally called by, for example, :func:`noteFromElement`, to determine the
        :class:`Articulation` objects that will be assigned to the
        :attr:`~music21.note.GeneralNote.articulations` attribute.

        >>> from xml.etree import ElementTree as ET
        >>> from converter21.mei import MeiReader
        >>> meiSnippet = '<artic artic="acc" xmlns="http://www.music-encoding.org/ns/mei"/>'
        >>> meiSnippet = ET.fromstring(meiSnippet)
        >>> c = MeiReader()
        >>> c.articFromElement(meiSnippet)
        [<music21.articulations.Accent>]

        A single <artic> element may indicate many :class:`Articulation` objects.

        >>> meiSnippet = '<artic artic="acc ten" xmlns="http://www.music-encoding.org/ns/mei"/>'
        >>> meiSnippet = ET.fromstring(meiSnippet)
        >>> c. articFromElement(meiSnippet)
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
            return self._makeArticList(articElement)
        else:
            return []


    def accidFromElement(
        self,
        elem: Element,
    ) -> pitch.Accidental | None:
        '''
        <accid> Records a temporary alteration to the pitch of a note.

        In MEI 2013: pg.248 (262 in PDF) (MEI.shared module)

        :returns: A music21 Accidental

        **Examples**

        >>> from xml.etree import ElementTree as ET
        >>> from converter21.mei import MeiReader
        >>> meiSnippet = '<accid accid.ges="s" xmlns="http://www.music-encoding.org/ns/mei"/>'
        >>> meiSnippet = ET.fromstring(meiSnippet)
        >>> c = MeiReader()
        >>> c.accidFromElement(meiSnippet)
        <music21.pitch.Accidental sharp>
        >>> meiSnippet = '<accid accid="tf" xmlns="http://www.music-encoding.org/ns/mei"/>'
        >>> meiSnippet = ET.fromstring(meiSnippet)
        >>> c.accidFromElement(meiSnippet)
        <music21.pitch.Accidental triple-flat>

        **Attributes/Elements Implemented:**

        - @accid (from att.accid.log)
        - @accid.ges (from att.accid.ges)

        .. note:: If set, the @accid.ges attribute is always imported as the music21
            :class:`Accidental` for this note. We assume it corresponds to the accidental
            implied by a key signature.

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
        accidStr: str | None = None
        displayStatus: bool | None = None
        if elem.get('accid.ges') is not None:
            accidStr = self._accidGesFromAttr(elem.get('accid.ges'))
            displayStatus = False
        if elem.get('accid') is not None:
            accidStr = self._accidentalFromAttr(elem.get('accid'))
            displayStatus = True

        # 2. is it cautionary (display unconditionally in normal position)
        #       or editorial (display unconditionally above the note)
        displayLocation: str | None = None
        func: str | None = elem.get('func')
        if func is not None:
            if func == 'edit':
                displayStatus = True
                displayLocation = 'above'
            elif func == 'caution':
                displayStatus = True
                displayLocation = 'normal'

        # 3. paren or bracket?
        displayStyle: str | None = None
        enclose: str | None = elem.get('enclose')
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
        self,
        elem: Element,
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
        wordPosDict: dict[str | None, t.Literal['begin', 'middle', 'end'] | None] = {
            'i': 'begin',
            'm': 'middle',
            't': 'end',
            None: None
        }

        # music21 only supports hyphen continuations.
        # conDict: dict[str | None, str] = {
        #     's': ' ',
        #     'd': '-',
        #     't': '~',
        #     'u': '_',
        #     None: '-'
        # }

        wordPos: str | None = elem.get('wordpos')

    #     conAttr: str | None = elem.get('con')
    #     con: str | None = conDict.get(conAttr, '-')

        output: note.Lyric
        text: str
        styleDict: dict[str, str]

        text, styleDict = self.textFromElem(elem)
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
            syllabic: t.Literal['begin', 'middle', 'end'] | None = wordPosDict.get(wordPos, None)
            output = note.Lyric(text=text, syllabic=syllabic, applyRaw=True)

        if fontStyle is not None or fontWeight is not None:
            output.style.fontStyle = (  # type: ignore
                self._m21FontStyleFromMeiFontStyleAndWeight(fontStyle, fontWeight)
            )
        if fontFamily is not None:
            output.style.fontFamily = fontFamily  # type: ignore
        if justify is not None:
            output.style.justify = justify  # type: ignore

        return output

    def verseFromElement(
        self,
        elem: Element,
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
        tagToFunction: dict[str, t.Callable[
            [Element],
            t.Any]
        ] = {
            f'{MEI_NS}label': self.stringFromElement,
            # music21 doesn't support verse label abbreviations
            # f'{MEI_NS}labelAbbr': labelAbbrFromElement,
            f'{MEI_NS}syl': self.sylFromElement
        }

        nStr: str | None = elem.get('n')
        label: str | None = None
        syllables: list[note.Lyric] = []

        for subElement in self._processEmbeddedElements(
            elem.findall('*'),
            tagToFunction,
            elem.tag
        ):
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
        self,
        elem: Element,
    ) -> str:
        # 888 should we use more of textFromElem here?
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

    @staticmethod
    def fermataFromNoteChordOrRestElement(elem: Element) -> expressions.Fermata | None:
        fermataPlace: str | None = elem.get('fermata')
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
        self,
        elem: Element,
        optionalDots: int | None = None
    ) -> duration.Duration:
        durFloat: float | None = None
        durGesFloat: float | None = None
        if elem.get('dur'):
            durFloat = self._qlDurationFromAttr(elem.get('dur'))
        if elem.get('dur.ges'):
            durGesFloat = self._qlDurationFromAttr(elem.get('dur.ges'))

        numDots: int
        if optionalDots is not None:
            numDots = optionalDots
        else:
            numDots = int(elem.get('dots', 0))

        numDotsGes: int | None = None
        dotsGesStr: str = elem.get('dots.ges', '')
        if dotsGesStr:
            numDotsGes = int(dotsGesStr)

        if durFloat is None:
            durFloat = durGesFloat
            durGesFloat = None
        if durFloat is None:
            # There's no @dur or @dur.ges, go with that weird default 1/1024th note
            durFloat = self._qlDurationFromAttr(None)

        visualDuration: duration.Duration = M21Utilities.makeDuration(durFloat, numDots)
        if durGesFloat is not None or numDotsGes is not None:
            gesDuration: duration.Duration
            if durGesFloat is not None and numDotsGes is not None:
                gesDuration = M21Utilities.makeDuration(durGesFloat, numDotsGes)
            elif durGesFloat is not None and numDotsGes is None:
                gesDuration = M21Utilities.makeDuration(durGesFloat, numDots)
            elif durGesFloat is None and numDotsGes is not None:
                gesDuration = M21Utilities.makeDuration(durFloat, numDotsGes)

            visualDuration.linked = False
            visualDuration.quarterLength = gesDuration.quarterLength

        return visualDuration

    def noteFromElement(
        self,
        elem: Element,
    ) -> note.Note:
        # NOTE: this function should stay in sync with chordFromElement() where sensible
        '''
        <note> is a single pitched event.

        In MEI 2013: pg.382 (396 in PDF) (MEI.shared module)

        .. note:: If set, the @accid.ges attribute is always imported as the music21
            :class:`Accidental` for this note. We assume it corresponds to the accidental
            implied by a key signature.

        .. note:: If ``elem`` contains both <syl> and <verse> elements as immediate children, the
            lyrics indicated with <verse> element(s) will always obliterate those given indicated
            with <syl> elements.

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
            duration is 0 because we ignore the question of which neighbouring note to borrow
            time from)
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
        theDuration: duration.Duration = self.durationFromAttributes(elem)
        theNote.duration = theDuration

        # get any @accid/@accid.ges from this element.
        # We'll overwrite with any subElements below.
        theAccid: str | None = self._accidentalFromAttr(elem.get('accid'))
        theAccidGes: str | None = self._accidGesFromAttr(elem.get('accid.ges'))
        theAccidObj: pitch.Accidental | None = None

        dotElements: int = 0  # count the number of <dot> elements
        for subElement in self._processEmbeddedElements(
            elem.findall('*'),
            self.noteChildrenTagToFunction,
            elem.tag,
        ):
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
            theDuration = self.durationFromAttributes(elem, dotElements)
            theNote.duration = theDuration

        # grace note (only mark as accented or unaccented grace note;
        # don't worry about "time-stealing")
        graceStr: str | None = elem.get('grace')
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
            theNote.pitch = M21Utilities.safePitch(pnameStr, theAccidObj, octStr)
        elif theAccidGes is not None:
            theNote.pitch = M21Utilities.safePitch(pnameStr, theAccidGes, octStr)
            if theNote.pitch.accidental is not None:
                # since the accidental was due to theAccidGes,
                # the accidental should NOT be displayed.
                theNote.pitch.accidental.displayStatus = False
        elif theAccid is not None:
            theNote.pitch = M21Utilities.safePitch(pnameStr, theAccid, octStr)
            if theNote.pitch.accidental is not None:
                # since the accidental was due to theAccid,
                # the accidental should be displayed.
                theNote.pitch.accidental.displayStatus = True
        else:
            theNote.pitch = M21Utilities.safePitch(pnameStr, None, octStr)

        if self.staffNumberForNotes:
            self.updateStaffAltersWithPitches(self.staffNumberForNotes, theNote.pitches)

        self.addSlurs(elem, theNote)

        # id in the @xml:id attribute
        xmlId: str | None = elem.get(_XMLID)
        if xmlId is not None:
            theNote.id = xmlId

        # articulations in the @artic attribute
        articStr: str | None = elem.get('artic')
        if articStr is not None:
            theNote.articulations.extend(self._makeArticList(articStr))

        # expressions from element attributes (perhaps fake attributes
        # created during preprocessing)
        fermata: expressions.Fermata | None = self.fermataFromNoteChordOrRestElement(elem)
        if fermata is not None:
            theNote.expressions.append(fermata)

        self.addArpeggio(elem, theNote)
        self.addTrill(elem, theNote)
        self.addMordent(elem, theNote)
        self.addTurn(elem, theNote)
        self.addOttavas(elem, theNote)
        self.addHairpins(elem, theNote)
        self.addDirsDynamsTempos(elem, theNote)

        # ties in the @tie attribute
        tieStr: str | None = elem.get('tie')
        if tieStr is not None:
            theNote.tie = self._tieFromAttr(tieStr)

        if elem.get('cue') == 'true':
            if t.TYPE_CHECKING:
                assert isinstance(theNote.style, style.NoteStyle)
            theNote.style.noteSize = 'cue'

        colorStr: str | None = elem.get('color')
        if colorStr is not None:
            theNote.style.color = colorStr

        headShape: str | None = elem.get('head.shape')
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

        stemDirStr: str | None = elem.get('stem.dir')
        if stemDirStr is not None:
            # We don't pay attention to stem direction if the note
            # is supposed to be in another staff (which we don't yet
            # support).
            theNote.stemDirection = self._stemDirectionFromAttr(stemDirStr)

        stemModStr: str | None = elem.get('stem.mod')
        if stemModStr is not None:
            # just add it as an attribute, to be read by callers if they like
            theNote.mei_stem_mod = stemModStr  # type: ignore

        stemLenStr: str | None = elem.get('stem.len')
        stemLen: float | None = None
        if stemLenStr is not None:
            try:
                stemLen = float(stemLenStr)
            except Exception:
                pass
            if stemLen is not None and stemLen == 0:
                theNote.stemDirection = 'noStem'

        stemVisible: str | None = elem.get('stem.visible')
        if stemVisible is not None and stemVisible == 'false':
            theNote.stemDirection = 'noStem'

        # breaksec="n" means that the beams that cross this note drop down to "n" beams
        # between this note and the next note.  Mark this in theNote with a custom attribute.
        breaksec: str | None = elem.get('breaksec')
        if breaksec is not None:
            theNote.mei_breaksec = breaksec  # type: ignore

        # beams indicated by a <beamSpan> held elsewhere
        if elem.get('m21Beam') is not None:
            if duration.convertTypeToNumber(theNote.duration.type) > 4:
                theNote.beams.fill(theNote.duration.type, elem.get('m21Beam'))

        # tuplets
        if elem.get('m21TupletNum') is not None:
            obj = self.scaleToTuplet(theNote, elem)
            if t.TYPE_CHECKING:
                # because scaleToTuplet always returns whatever objs it was passed (modified)
                assert isinstance(obj, note.Note)
            theNote = obj

        # visibility
        if elem.get('visible') == 'false':
            theNote.style.hideObjectOnPrint = True

        # stash the staff number in theNote.mei_staff (in case a spanner needs to know)
        if self.staffNumberForNotes:
            theNote.mei_staff = self.staffNumberForNotes  # type: ignore

        return theNote

    def restFromElement(
        self,
        elem: Element,
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

        theDuration: duration.Duration = self.durationFromAttributes(elem)
        theRest = note.Rest(duration=theDuration)

        xmlId: str | None = elem.get(_XMLID)
        if xmlId is not None:
            theRest.id = xmlId

        # expressions from element attributes (perhaps fake attributes
        # created during preprocessing)
        fermata = self.fermataFromNoteChordOrRestElement(elem)
        if fermata is not None:
            theRest.expressions.append(fermata)

        self.addHairpins(elem, theRest)
        self.addDirsDynamsTempos(elem, theRest)

        if elem.get('cue') == 'true':
            if t.TYPE_CHECKING:
                assert isinstance(theRest.style, style.NoteStyle)
            theRest.style.noteSize = 'cue'

        colorStr: str | None = elem.get('color')
        if colorStr is not None:
            theRest.style.color = colorStr

        # tuplets
        if elem.get('m21TupletNum') is not None:
            obj = self.scaleToTuplet(theRest, elem)
            if t.TYPE_CHECKING:
                # because scaleToTuplet returns whatever it was passed (modified)
                assert isinstance(obj, note.Rest)
            theRest = obj

        # visibility
        if elem.get('visible') == 'false':
            theRest.style.hideObjectOnPrint = True

        # stash the staff number in theRest.mei_staff (in case a spanner needs to know)
        if self.staffNumberForNotes:
            theRest.mei_staff = self.staffNumberForNotes  # type: ignore

        return theRest

    def mRestFromElement(
        self,
        elem: Element,
    ) -> note.Rest:
        '''
        <mRest/> Complete measure rest in any meter.

        In MEI 2013: pg.375 (389 in PDF) (MEI.cmn module)

        This is a function wrapper for :func:`restFromElement`.

        .. note:: If the <mRest> element does not have a @dur attribute, it will have the default
            duration of 1.0. This must be fixed later, so the :class:`Rest` object returned from
            this method is given the :attr:`m21wasMRest` attribute, set to True.
        '''
        # NOTE: keep this in sync with mSpaceFromElement()

        if elem.get('dur') is not None:
            return self.restFromElement(elem)
        else:
            theRest = self.restFromElement(elem)
            theRest.m21wasMRest = True  # type: ignore
            return theRest

    def spaceFromElement(
        self,
        elem: Element,
    ) -> note.Rest:
        '''
        <space>  A placeholder used to fill an incomplete measure, layer, etc. most often so that
        the combined duration of the events equals the number of beats in the measure.

        Returns a Rest element with hideObjectOnPrint = True

        In MEI 2013: pg.440 (455 in PDF) (MEI.shared module)
        '''
        # NOTE: keep this in sync with restFromElement()

        theDuration: duration.Duration = self.durationFromAttributes(elem)
        theSpace: note.Rest = note.Rest(duration=theDuration)
        theSpace.style.hideObjectOnPrint = True

        xmlId: str | None = elem.get(_XMLID)
        if xmlId is not None:
            theSpace.id = xmlId

        # tuplets
        if elem.get('m21TupletNum') is not None:
            obj = self.scaleToTuplet(theSpace, elem)
            if t.TYPE_CHECKING:
                # because scaleToTuplet returns the same type it was passed
                assert isinstance(obj, note.Rest)
            theSpace = obj

        return theSpace

    def mSpaceFromElement(
        self,
        elem: Element,
    ) -> note.Rest:
        '''
        <mSpace/> A measure containing only empty space in any meter.

        In MEI 2013: pg.377 (391 in PDF) (MEI.cmn module)

        This is a function wrapper for :func:`spaceFromElement`.

        .. note:: If the <mSpace> element does not have a @dur attribute, it will have the default
            duration of 1.0. This must be fixed later, so the :class:`Space` object returned from
            this method is given the :attr:`m21wasMRest` attribute, set to True.
        '''
        # NOTE: keep this in sync with mRestFromElement()

        if elem.get('dur') is not None:
            return self.spaceFromElement(elem)
        else:
            theSpace = self.spaceFromElement(elem)
            theSpace.m21wasMRest = True  # type: ignore
            return theSpace

    def chordFromElement(
        self,
        elem: Element,
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
            duration is 0 because we ignore the question of which neighbouring note to borrow
            time from)

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
        theNoteList: list[note.Note] = []
        theArticList: list[articulations.Articulation] = []
        theLyricList: list[note.Lyric] = []
        spannersFromNotes: list[tuple[note.Note, list[spanner.Spanner]]] = []
        # iterate all immediate children
        for subElement in self._processEmbeddedElements(
            elem.findall('*'),
            self.chordChildrenTagToFunction,
            elem.tag,
        ):
            if isinstance(subElement, note.Note):
                theNoteList.append(subElement)
                spannersFromThisNote: list[spanner.Spanner] = subElement.getSpannerSites()
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
        theDuration: duration.Duration = self.durationFromAttributes(elem)
        theChord.duration = theDuration

        # grace note (only mark as accented or unaccented grace note;
        # don't worry about "time-stealing")
        graceStr: str | None = elem.get('grace')
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

        if self.staffNumberForNotes:
            self.updateStaffAltersWithPitches(self.staffNumberForNotes, theChord.pitches)

        self.addSlurs(elem, theChord)

        # id in the @xml:id attribute
        xmlId: str | None = elem.get(_XMLID)
        if xmlId is not None:
            theChord.id = xmlId

        # articulations in the @artic attribute
        articStr: str | None = elem.get('artic')
        if articStr is not None:
            theChord.articulations.extend(self._makeArticList(articStr))

        # expressions from element attributes (perhaps fake attributes
        # created during preprocessing)
        fermata = self.fermataFromNoteChordOrRestElement(elem)
        if fermata is not None:
            theChord.expressions.append(fermata)

        self.addArpeggio(elem, theChord)
        self.addTrill(elem, theChord)
        self.addMordent(elem, theChord)
        self.addTurn(elem, theChord)
        self.addOttavas(elem, theChord)
        self.addHairpins(elem, theChord)
        self.addDirsDynamsTempos(elem, theChord)

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
        tieStr: str | None = elem.get('tie')
        if tieStr is not None:
            theChord.tie = self._tieFromAttr(tieStr)

        if elem.get('cue') == 'true':
            if t.TYPE_CHECKING:
                assert isinstance(theChord.style, style.NoteStyle)
            theChord.style.noteSize = 'cue'

        colorStr: str | None = elem.get('color')
        if colorStr is not None:
            theChord.style.color = colorStr

        stemDirStr: str | None = elem.get('stem.dir')
        if stemDirStr is not None:
            # We don't pay attention to stem direction if the chord
            # is supposed to be in another staff (which we don't yet
            # support).
            theChord.stemDirection = self._stemDirectionFromAttr(stemDirStr)

        stemModStr: str | None = elem.get('stem.mod')
        if stemModStr is not None:
            # just add it as an attribute, to be read by callers if they like
            theChord.mei_stem_mod = stemModStr  # type: ignore

        # breaksec="n" means that the beams that cross this note drop down to "n" beams
        # between this note and the next note.  Mark this in theNote with a custom attribute.
        breaksec: str | None = elem.get('breaksec')
        if breaksec is not None:
            theChord.mei_breaksec = breaksec  # type: ignore

        # beams indicated by a <beamSpan> held elsewhere
        m21BeamStr: str | None = elem.get('m21Beam')
        if m21BeamStr is not None:
            if duration.convertTypeToNumber(theChord.duration.type) > 4:
                theChord.beams.fill(theChord.duration.type, m21BeamStr)

        # tuplets
        if elem.get('m21TupletNum') is not None:
            obj = self.scaleToTuplet(theChord, elem)
            if t.TYPE_CHECKING:
                # because scaleToTuplet returns whatever type it was passed
                assert isinstance(obj, chord.Chord)
            theChord = obj

        # visibility
        if elem.get('visible') == 'false':
            theChord.style.hideObjectOnPrint = True

        # stash the staff number in theChord.mei_staff (in case a spanner needs to know)
        if self.staffNumberForNotes:
            theChord.mei_staff = self.staffNumberForNotes  # type: ignore

        return theChord


    def clefFromElement(
        self,
        elem: Element,
    ) -> clef.Clef | None:
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

        shapeStr: str | None = elem.get('shape')
        lineStr: str | None = elem.get('line')
        octaveShiftOverride: int | None = None
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
                    self._getOctaveShift(elem.get('dis'), elem.get('dis.place'))
                )

        xmlId: str | None = elem.get(_XMLID)
        if xmlId is not None:
            theClef.id = xmlId

        return theClef

    def pageBreakFromElement(
        self,
        elem: Element,
    ) -> m21.layout.PageLayout | None:
        pbType: str = elem.get('type', '')
        if pbType.startswith('original'):  # startswith because sometimes there are '\t*'s after
            # ignore any original page breaks (like our Humdrum parser does)
            return None

        # Some day music21 will support non-numeric page numbers (e.g. 'iv' or 'p17-3').
        # In the meantime, we drop them on the floor.
        pageNumber: int | None = None
        nStr: str = elem.get('n', '')
        if nStr:
            try:
                pageNumber = int(nStr)
            except Exception:
                pass

        pageLayout: m21.layout.PageLayout = (
            m21.layout.PageLayout(isNew=True, pageNumber=pageNumber)
        )

        xmlId: str | None = elem.get(_XMLID)
        if xmlId is not None:
            pageLayout.id = xmlId

        return pageLayout


    def systemBreakFromElement(
        self,
        elem: Element,
    ) -> m21.layout.SystemLayout | None:
        sbType: str = elem.get('type', '')
        if sbType.startswith('original'):  # startswith because sometimes there are '\t*'s after
            # ignore any 'original' system breaks (like our Humdrum parser does)
            return None

        systemLayout: m21.layout.SystemLayout = m21.layout.SystemLayout(isNew=True)
        xmlId: str | None = elem.get(_XMLID)
        if xmlId is not None:
            systemLayout.id = xmlId

        return systemLayout

    def keySigFromElementInStaffDef(
        self,
        elem: Element,
    ) -> key.Key | key.KeySignature | None:
        newKey: key.Key | key.KeySignature | None = (
            self._keySigFromElement(elem)
        )
        if self.staffNumberForDef:
            self.updateStaffKeyAndAltersWithNewKey(self.staffNumberForDef, newKey)

        return newKey

    def keySigFromElementInLayer(
        self,
        elem: Element,
    ) -> key.Key | key.KeySignature | None:
        newKey: key.Key | key.KeySignature | None = (
            self._keySigFromElement(elem)
        )
        if self.staffNumberForNotes:
            self.updateStaffKeyAndAltersWithNewKey(self.staffNumberForNotes, newKey)

        return newKey

    def _keySigFromElement(
        self,
        elem: Element,
    ) -> key.Key | key.KeySignature | None:
        theKey: key.Key | key.KeySignature | None = self._keySigFromAttrs(elem)
        if theKey is None:
            return None

        xmlId: str | None = elem.get(_XMLID)
        if xmlId is not None:
            theKey.id = xmlId

        return theKey

    def timeSigFromElement(
        self,
        elem: Element,
    ) -> meter.TimeSignature | None:
        theTimeSig: meter.TimeSignature | None = self._timeSigFromAttrs(elem)
        if theTimeSig is None:
            return None

        xmlId: str | None = elem.get(_XMLID)
        if xmlId is not None:
            theTimeSig.id = xmlId

        return theTimeSig

    def instrDefFromElement(
        self,
        elem: Element,
    ) -> m21.instrument.Instrument:
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
        instrNumStr: str | None = elem.get('midi.instrnum')
        if instrNumStr is not None:
            try:
                return m21.instrument.instrumentFromMidiProgram(int(instrNumStr))
            except (TypeError, m21.instrument.InstrumentException):
                pass

        instrNameStr: str = elem.get('midi.instrname', '')
        try:
            return m21.instrument.fromString(instrNameStr)
        except (AttributeError, m21.instrument.InstrumentException):
            pass

        # last fallback: just use instrNameStr (might even be '') as a custom name
        theInstr = m21.instrument.Instrument()
        theInstr.partName = instrNameStr
        return theInstr

    def beamFromElement(
        self,
        elem: Element,
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
        >>> from converter21.mei import MeiReader
        >>> meiSnippet = """<beam xmlns="http://www.music-encoding.org/ns/mei">
        ...     <note pname='A' oct='7' dur='8'/>
        ...     <note pname='B' oct='7' dur='8'/>
        ...     <note pname='C' oct='6' dur='8'/>
        ... </beam>"""
        >>> meiSnippet = ET.fromstring(meiSnippet)
        >>> c = MeiReader()
        >>> result = c.beamFromElement(meiSnippet)
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
        beamedStuff: list[Music21Object] = self._processEmbeddedElements(
            elem.findall('*'),
            self.beamChildrenTagToFunction,
            elem.tag,
        )

        self.beamTogether(beamedStuff)
        self.applyBreaksecs(beamedStuff)

        return beamedStuff

    def bTremFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        '''
        <bTrem> contains one <note> or <chord> (or editorial elements that resolve to a single
        note or chord)
        '''
        bTremStuff: list[Music21Object] = self._processEmbeddedElements(
            elem.findall('*'),
            self.bTremChildrenTagToFunction,
            elem.tag,
        )

        if len(bTremStuff) != 1:
            raise MeiElementError('<bTrem> without exactly one note or chord within')

        noteOrChord: Music21Object = bTremStuff[0]
        if t.TYPE_CHECKING:
            assert isinstance(noteOrChord, note.NotRest)
        tremolo: expressions.Tremolo = expressions.Tremolo()
        unitdurStr: str = elem.get('unitdur', '')
        numMarks: int = self._DUR_TO_NUMBEAMS.get(unitdurStr, 0)
        if numMarks == 0:
            # check the note or chord itself to see if it has @stem.mod = '3slashes' or the like
            if hasattr(noteOrChord, 'mei_stem_mod'):
                numMarks = self._STEMMOD_TO_NUMSLASHES.get(
                    noteOrChord.mei_stem_mod, 0  # type: ignore
                )

        if numMarks == 9:
            numMarks = 8  # music21 doesn't support a 2048th note tremolo, pretend it's 1024th note

        if numMarks > 0:
            tremolo.numberOfMarks = numMarks
            noteOrChord.expressions.append(tremolo)

        return bTremStuff


    def fTremFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        '''
        <fTrem> contains two <note>s or two <chord>s or one of each (or editorial elements that
        resolve to two <note>s or two <chord>s or one of each)
        '''
        fTremStuff: list[Music21Object] = self._processEmbeddedElements(
            elem.findall('*'),
            self.fTremChildrenTagToFunction,
            elem.tag,
        )

        if len(fTremStuff) != 2:
            raise MeiElementError(
                '<fTrem> without exactly two notes/chords (or one of each) within'
            )

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
                numMarks = self._STEMMOD_TO_NUMSLASHES.get(
                    firstNoteOrChord.mei_stem_mod, 0  # type: ignore
                )
            if numMarks == 0 and hasattr(secondNoteOrChord, 'mei_stem_mod'):
                numMarks = self._STEMMOD_TO_NUMSLASHES.get(
                    secondNoteOrChord.mei_stem_mod, 0  # type: ignore
                )

        # numMarks should be total number of beams - beams due to note duration
        numNoteBeams: int = self._QL_TO_NUMFLAGS.get(firstNoteOrChord.duration.quarterLength, 0)
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
            self.spannerBundle.append(tremoloSpanner)

        return fTremStuff

    def barLineFromElement(
        self,
        elem: Element,
    ) -> bar.Barline | bar.Repeat | tuple[bar.Repeat, bar.Repeat]:
        '''
        <barLine> Vertical line drawn through one or more staves that divides musical notation into
        metrical units.

        In MEI 2013: pg.262 (276 in PDF) (MEI.shared module)

        :returns: A :class:`music21.bar.Barline` or :class:`~music21.bar.Repeat`, depending on
            the value of @rend. If @rend is ``'rptboth'``, a 2-tuplet of :class:`Repeat` objects
            will be returned, represented an "end" and "start" barline, as specified in the
            :mod:`music21.bar` documentation.

        .. note:: The music21-to-other converters expect that a :class:`Barline` will be attached
            to a :class:`Measure`, which it will not be when imported from MEI as a <barLine>
            element. However, this function does import correctly to a :class:`Barline` that you
            can access from Python in the :class:`Stream` object as expected.

        **Attributes/Elements Implemented:**

        - @rend from att.barLine.log

        **Attributes/Elements in Testing:** none

        **Attributes not Implemented:**

        - att.common (@label, @n, @xml:base) (att.id (@xml:id))
        - att.facsimile (@facs)
        - att.pointing (@xlink:*, @target, @targettype)
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
        return self._barlineFromAttr(elem.get('rend', 'single'))

    def tupletFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
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
        # get the @num and @numbase attributes, without which we can't properly
        # calculate the tuplet
        numStr: str | None = elem.get('num')
        numbaseStr: str | None = elem.get('numbase')
        if numStr is None or numbaseStr is None:
            raise MeiAttributeError(_MISSING_TUPLET_DATA)
        bracketVisibleStr: str | None = elem.get('bracket.visible')
        bracketPlaceStr: str | None = elem.get('bracket.place')
        numVisibleStr: str | None = elem.get('num.visible')
        numPlaceStr: str | None = elem.get('num.place')
        numFormatStr: str | None = elem.get('num.format')

        # iterate all immediate children
        tupletMembers: list[Music21Object] = self._processEmbeddedElements(
            elem.findall('*'),
            self.tupletChildrenTagToFunction,
            elem.tag,
        )

        # "tuplet-ify" the duration of everything held within
        newElem = Element('', m21TupletNum=numStr, m21TupletNumbase=numbaseStr)
        if bracketVisibleStr is not None:
            newElem.set('m21TupletBracketVisible', bracketVisibleStr)
        if bracketPlaceStr is not None:
            newElem.set('m21TupletBracketPlace', bracketPlaceStr)
        if numVisibleStr is not None:
            newElem.set('m21TupletNumVisible', numVisibleStr)
        if numPlaceStr is not None:
            newElem.set('m21TupletNumPlace', numPlaceStr)
        if numFormatStr is not None:
            newElem.set('m21TupletNumFormat', numFormatStr)

        tupletMembers = t.cast(list[Music21Object], self.scaleToTuplet(tupletMembers, newElem))

        # Set the Tuplet.type property for the first and final note in a tuplet.
        # We have to find the first and last duration-having thing, not just the
        # first and last objects between the <tuplet> tags.
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

        tupletMembers[firstNote].duration.tuplets[-1].type = 'start'
        if lastNote is None:
            # when there is only one object in the tuplet
            tupletMembers[firstNote].duration.tuplets[-1].type = 'stop'
        else:
            tupletMembers[lastNote].duration.tuplets[-1].type = 'stop'

        return tupletMembers

    @staticmethod
    def _isLastDurationalElement(idx: int, elements: list[Music21Object]) -> bool:
        if elements[idx].quarterLength == 0:
            # it's not a durational element at all
            return False
        for i in range(idx + 1, len(elements) - 1):
            if elements[i].quarterLength != 0:
                # found a subsequent durational element, so it's not the last one
                return False
        return True

    def layerFromElement(
        self,
        elem: Element,
        overrideN: str | None = None
    ) -> stream.Voice:
        '''
        <layer> An independent stream of events on a staff.

        In MEI 2013: pg.353 (367 in PDF) (MEI.shared module)

        .. note:: The :class:`Voice` object's :attr:`~music21.stream.Voice.id` attribute must be
            set properly in order to ensure continuity of voices between measures. If the ``elem``
            does not have an @n attribute, you can set one with the ``overrideN`` parameter in
            this function. If you provide a value for ``overrideN``, it will be used instead of
            the ``elemn`` object's @n attribute.

            Because improperly-set :attr:`~music21.stream.Voice.id` attributes nearly guarantees
            errors in the imported :class:`Score`, either ``overrideN`` or @n must be specified.

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
        theLayer: list[Music21Object] = self._processEmbeddedElements(
            elem.iterfind('*'),
            self.layerChildrenTagToFunction,
            elem.tag,
        )

        # adjust the <layer>'s elements for possible tuplets
        theLayer = self._guessTuplets(theLayer)

        # Verovio, when converting from Humdrum to MEI, has been known to put <space> fillers
        # immediately after the end of a measure's/layer's usual duration, as an errant response
        # to a *clef token in the middle of a final rest or note.  This was fixed recently, but
        # because many such MEI files have been saved, we need to ignore these.
        if self.activeMeter is not None:
            expectedLayerDur: OffsetQL = 4.0 * opFrac(
                Fraction(self.activeMeter.numerator, self.activeMeter.denominator)
            )
            removeThisOne: int | None = None
            currOffset: OffsetQL = 0.
            for i, each in enumerate(theLayer):
                if currOffset == expectedLayerDur:
                    if isinstance(each, note.Rest) and each.style.hideObjectOnPrint:
                        if self._isLastDurationalElement(i, theLayer):
                            removeThisOne = i
                            break
                currOffset = opFrac(currOffset + each.quarterLength)
            if removeThisOne is not None:
                theLayer.pop(removeThisOne)

        # make the Voice
        theVoice: stream.Voice = stream.Voice()
        for obj in theLayer:
            # Check for dir/dynam/tempo attached to the obj.
            # If there, append them first, then the obj, so
            # they all get the same offset (since dir/dynam/tempo
            # have zero duration).
            if hasattr(obj, 'mei_dir_dynam_tempo_list'):
                dirDynamTempoList: list[
                    m21.expressions.TextExpression
                    | m21.dynamics.Dynamic
                    | m21.tempo.TempoIndication
                ] = obj.mei_dir_dynam_tempo_list  # type: ignore
                if dirDynamTempoList:
                    for each in dirDynamTempoList:
                        theVoice.coreAppend(each)
            theVoice.coreAppend(obj)
        theVoice.coreElementsChanged()

        # try to set the Voice's "id" attribute

        if overrideN:
            theVoice.id = overrideN
        else:
            nStr: str | None = elem.get('n')
            if nStr is not None:
                theVoice.id = nStr
            else:
                raise MeiAttributeError(_MISSING_VOICE_ID)

        return theVoice

    def appChoiceLayerChildrenFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        chosen: Element | None = self.chooseSubElement(elem)
        if chosen is None:
            return []

        # iterate all immediate children
        theList: list[Music21Object] = self._processEmbeddedElements(
            chosen.iterfind('*'),
            self.layerChildrenTagToFunction,
            chosen.tag,
        )

        return theList

    def passThruEditorialLayerChildrenFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        # iterate all immediate children
        theList: list[Music21Object] = self._processEmbeddedElements(
            elem.iterfind('*'),
            self.layerChildrenTagToFunction,
            elem.tag,
        )

        return theList

    def appChoiceStaffItemsFromElement(
        self,
        elem: Element,
    ) -> list[
        tuple[
            str,
            tuple[OffsetQL | None, int | None, OffsetQL | None],
            Music21Object
        ]
    ]:
        chosen: Element | None = self.chooseSubElement(elem)
        if chosen is None:
            return []

        # iterate all immediate children
        theList: list[
            tuple[
                str,
                tuple[OffsetQL | None, int | None, OffsetQL | None],
                Music21Object
            ]
        ] = (
            self._processEmbeddedElements(
                chosen.iterfind('*'),
                self.staffItemsTagToFunction,
                chosen.tag)
        )

        return theList

    def passThruEditorialStaffItemsFromElement(
        self,
        elem: Element,
    ) -> list[
        tuple[
            str,
            tuple[OffsetQL | None, int | None, OffsetQL | None],
            Music21Object
        ]
    ]:
        # iterate all immediate children
        theList: list[
            tuple[
                str,
                tuple[OffsetQL | None, int | None, OffsetQL | None],
                Music21Object
            ]
        ] = (
            self._processEmbeddedElements(
                elem.iterfind('*'),
                self.staffItemsTagToFunction,
                elem.tag
            )
        )

        return theList

    def appChoiceNoteChildrenFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        chosen: Element | None = self.chooseSubElement(elem)
        if chosen is None:
            return []

        # iterate all immediate children
        theList: list[Music21Object] = self._processEmbeddedElements(
            chosen.iterfind('*'),
            self.noteChildrenTagToFunction,
            chosen.tag,
        )

        return theList

    def passThruEditorialNoteChildrenFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        # iterate all immediate children
        theList: list[Music21Object] = self._processEmbeddedElements(
            elem.iterfind('*'),
            self.noteChildrenTagToFunction,
            elem.tag,
        )

        return theList

    def appChoiceChordChildrenFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        chosen: Element | None = self.chooseSubElement(elem)
        if chosen is None:
            return []

        # iterate all immediate children
        theList: list[Music21Object] = self._processEmbeddedElements(
            chosen.iterfind('*'),
            self.chordChildrenTagToFunction,
            chosen.tag,
        )

        return theList

    def passThruEditorialChordChildrenFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        # iterate all immediate children
        theList: list[Music21Object] = self._processEmbeddedElements(
            elem.iterfind('*'),
            self.chordChildrenTagToFunction,
            elem.tag,
        )

        return theList

    def appChoiceBeamChildrenFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        chosen: Element | None = self.chooseSubElement(elem)
        if chosen is None:
            return []

        # iterate all immediate children
        theList: list[Music21Object] = self._processEmbeddedElements(
            chosen.iterfind('*'),
            self.beamChildrenTagToFunction,
            chosen.tag,
        )

        return theList

    def passThruEditorialBeamChildrenFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        # iterate all immediate children
        theList: list[Music21Object] = self._processEmbeddedElements(
            elem.iterfind('*'),
            self.beamChildrenTagToFunction,
            elem.tag,
        )

        return theList

    def appChoiceTupletChildrenFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        chosen: Element | None = self.chooseSubElement(elem)
        if chosen is None:
            return []

        # iterate all immediate children
        theList: list[Music21Object] = self._processEmbeddedElements(
            chosen.iterfind('*'),
            self.tupletChildrenTagToFunction,
            chosen.tag,
        )

        return theList

    def passThruEditorialTupletChildrenFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        # iterate all immediate children
        theList: list[Music21Object] = self._processEmbeddedElements(
            elem.iterfind('*'),
            self.tupletChildrenTagToFunction,
            elem.tag,
        )

        return theList

    def appChoiceBTremChildrenFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        chosen: Element | None = self.chooseSubElement(elem)
        if chosen is None:
            return []

        # iterate all immediate children
        theList: list[Music21Object] = self._processEmbeddedElements(
            chosen.iterfind('*'),
            self.bTremChildrenTagToFunction,
            chosen.tag,
        )

        return theList

    def passThruEditorialBTremChildrenFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        # iterate all immediate children
        theList: list[Music21Object] = self._processEmbeddedElements(
            elem.iterfind('*'),
            self.bTremChildrenTagToFunction,
            elem.tag,
        )

        return theList

    def appChoiceFTremChildrenFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        chosen: Element | None = self.chooseSubElement(elem)
        if chosen is None:
            return []

        # iterate all immediate children
        theList: list[Music21Object] = self._processEmbeddedElements(
            chosen.iterfind('*'),
            self.fTremChildrenTagToFunction,
            chosen.tag,
        )

        return theList

    def passThruEditorialFTremChildrenFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        # iterate all immediate children
        theList: list[Music21Object] = self._processEmbeddedElements(
            elem.iterfind('*'),
            self.fTremChildrenTagToFunction,
            elem.tag,
        )

        return theList

    def _currKeyForStaff(
        self,
        staffNStr: str,
    ) -> key.Key | key.KeySignature | None:
        currentKey: key.Key | key.KeySignature | None = (
            self.currKeyPerStaff.get(staffNStr, None)
        )
        return currentKey

    def staffFromElement(
        self,
        elem: Element,
    ) -> list[Music21Object]:
        '''
        <staff> A group of equidistant horizontal lines on which notes are placed in order to
        represent pitch or a grouping element for individual 'strands' of notes, rests, etc.
        that may or may not actually be rendered on staff lines; that is, both diastematic and
        non-diastematic signs.

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
        # mapping from tag name to our converter function (currently empty)
        layerTagName: str = f'{MEI_NS}layer'
        tagToFunction: dict[str, t.Callable[
            [Element],
            t.Any]
        ] = {
        }

        nextBreak: m21.layout.PageLayout | m21.layout.SystemLayout | None = None

        if self.staffNumberForNotes:
            # Initialize self.currentImpliedAltersPerStaff from the keysig for this staff.
            # This staff's currentImpliedAlters will be updated as notes/ornaments with visual
            # accidentals are seen in this layer.
            currentKey: key.Key | key.KeySignature | None = (
                self._currKeyForStaff(self.staffNumberForNotes)
            )
            self.updateStaffKeyAndAltersWithNewKey(self.staffNumberForNotes, currentKey)

            if self.staffNumberForNotes == self.topPartN:
                # this is the top Part; in music21 page breaks/system breaks go
                # at the start of the measure in the topmost Part.
                nextBreak = self.nextBreak
                self.nextBreak = None

        layers: list[Music21Object] = []

        # track the @n values given to layerFromElement()
        currentNValue: str = '1'

        # iterate all immediate children
        for eachTag in elem.iterfind('*'):
            if layerTagName == eachTag.tag:
                layers.append(self.layerFromElement(
                    eachTag, overrideN=currentNValue
                ))
                currentNValue = f'{int(currentNValue) + 1}'  # inefficient, but we need a string
            elif eachTag.tag in tagToFunction:
                # NB: this won't be tested until there's something in tagToFunction
                layers.append(
                    tagToFunction[eachTag.tag](eachTag)
                )
            elif eachTag.tag not in _IGNORE_UNPROCESSED:
                environLocal.warn(_UNPROCESSED_SUBELEMENT.format(eachTag.tag, elem.tag))

        if nextBreak is not None:
            # return the page/system break as the first element of the list
            return [nextBreak] + layers

        return layers

    @staticmethod
    def _correctMRestDurs(
        staves: dict[str, stream.Measure | bar.Repeat],
        targetQL: OffsetQL
    ):
        '''
        Helper function for measureFromElement(), not intended to be used elsewhere. It's a
        separate function only (1) to reduce duplication, and (2) to improve testability.

        Iterate the imported objects of <layer> elements in the <staff> elements in a <measure>,
        detecting those with the "m21wasMRest" attribute and setting their duration to
        "targetLength."

        The "staves" argument should be a dictionary where the values are Measure objects with
        at least one Voice object inside.

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
        self,
        elem: Element,
        staves: dict[str, stream.Measure | bar.Repeat]
    ) -> dict[str, stream.Measure | bar.Repeat]:
        '''
        This is a helper function for :func:`measureFromElement`, made independent only to improve
        that function's ease of testing.

        Given a <measure> element and a dictionary with the :class:`Measure` objects that have
        already been processed, change the barlines of the :class:`Measure` objects in accordance
        with the element's @left and @right attributes.

        :param :class:`~xml.etree.ElementTree.Element` elem: The ``<measure>`` tag to process.
        :param dict staves: Dictionary where keys are @n attributes and values are corresponding
            :class:`~music21.stream.Measure` objects.
        :returns: The ``staves`` dictionary with properly-set barlines.
        :rtype: dict
        '''
        leftStr: str | None = elem.get('left')
        if leftStr is not None:
            bars = self._barlineFromAttr(leftStr)
            if isinstance(bars, tuple):
                # this means @left was "rptboth"
                bars = bars[1]

            for eachMeasure in staves.values():
                if isinstance(eachMeasure, stream.Measure):
                    eachMeasure.leftBarline = deepcopy(bars)

        rightStr: str | None = elem.get('right', 'single')
        bars = self._barlineFromAttr(rightStr)
        if isinstance(bars, tuple):
            # this means @right was "rptboth"
            staves['next @left'] = bars[1]
            bars = bars[0]

        for eachMeasure in staves.values():
            if isinstance(eachMeasure, stream.Measure):
                eachMeasure.rightBarline = deepcopy(bars)

        return staves

    @staticmethod
    def _canBeOnRest(expr: expressions.Expression) -> bool:
        if isinstance(expr, expressions.Fermata):
            return True
        return False

    def _addTimestampedExpressions(
        self,
        staves: dict[str, stream.Measure | bar.Repeat],
        tsExpressions: list[tuple[list[str], OffsetQL, expressions.Expression]],
    ):
        clonedExpression: expressions.Expression

        for staffNs, offset, expression in tsExpressions:
            canBeOnRest: bool = self._canBeOnRest(expression)
            isDelayedTurn: bool = (
                isinstance(expression, expressions.Turn)
                and hasattr(expression, 'delayed')
                and expression.delayed == 'true'
            )

            for i, staffN in enumerate(staffNs):
                doneWithStaff: bool = False
                eachMeasure: stream.Measure | bar.Repeat = staves[staffN]
                if not isinstance(eachMeasure, stream.Measure):
                    continue

                nearestPrevNoteInStaff: note.GeneralNote | None = None
                offsetFromNearestPrevNote: OffsetQL | None = None
                staffForNearestNote: str | None = None
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
                                        if isinstance(expression, expressions.Ornament):
                                            # Resolve the ornament's ornamental pitches
                                            # based on eachObject
                                            expression.resolveOrnamentalPitches(
                                                eachObject,
                                                keySig=self._currKeyForStaff(staffN)
                                            )
                                            self.updateAltersFromExpression(
                                                expression, eachObject, staffN
                                            )
                                        eachObject.expressions.append(expression)
                                    else:
                                        clonedExpression = deepcopy(expression)
                                        if isinstance(clonedExpression, expressions.Ornament):
                                            # Resolve the ornament's ornamental pitches
                                            # based on eachObject
                                            clonedExpression.resolveOrnamentalPitches(
                                                eachObject,
                                                keySig=self._currKeyForStaff(staffN)
                                            )
                                            self.updateAltersFromExpression(
                                                clonedExpression, eachObject, staffN
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
                                        offsetFromNearestPrevNote = (
                                            opFrac(offset - eachObject.offset)
                                        )
                                        nearestPrevNoteInStaff = eachObject
                                        staffForNearestNote = staffN

                        if doneWithStaff:
                            break

                if not doneWithStaff:
                    # We didn't find any place for the expression at the offset in this staff.
                    # But if it is a delayed turn, then we should use the note with the closest
                    # offset LESS than the expression's offset.  Which we have stashed off in
                    # "nearestPrevNoteInStaff".  offsetFromNearestPrevNote is the turn's delay.
                    if nearestPrevNoteInStaff is not None:
                        if t.TYPE_CHECKING:
                            # Since nearestPrevNoteInStaff is set, so is staffForNearestNote
                            # and offsetFromNearestPrevNote
                            assert staffForNearestNote is not None
                            assert offsetFromNearestPrevNote is not None

                        if isDelayedTurn:
                            if t.TYPE_CHECKING:
                                assert isinstance(expression, expressions.Turn)
                            expression.delay = offsetFromNearestPrevNote

                        # Resolve the expression's "other" pitches based on
                        # nearestPrevNoteInStaff's pitch (or highest pitch if
                        # nearestPrevNoteInStaff is a chord with pitches)
                        if isinstance(expression, expressions.Ornament):
                            expression.resolveOrnamentalPitches(
                                nearestPrevNoteInStaff,
                                keySig=self._currKeyForStaff(staffForNearestNote)
                            )

                            self.updateAltersFromExpression(
                                expression, nearestPrevNoteInStaff, staffForNearestNote
                            )

                        nearestPrevNoteInStaff.expressions.append(expression)
                    else:
                        environLocal.warn(
                            f'No obj at offset {offset} found in staff {staffN}'
                            f'for timestamped {expression.classes[0]}.'
                        )

    def _tstampToOffset(
        self,
        tstamp: str,
    ) -> OffsetQL:
        beat: float
        try:
            beat = float(tstamp)
        except (TypeError, ValueError):
            # warn about malformed tstamp, assuming 0.0
            return 0.0

        return self._beatToOffset(beat, self.activeMeter)

    @staticmethod
    def _beatToOffset(beat: float, activeMeter: meter.TimeSignature | None) -> OffsetQL:
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
        self,
        tstamp2: str,
    ) -> tuple[int, OffsetQL]:
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
        except Exception:
            # warn about malformed tstamp2, assuming '0m+0.000'
            return 0, 0.

        offset = self._beatToOffset(beat, self.activeMeter)
        return measSkip, offset

    def _tstampsToOffset1AndMeasSkipAndOffset2(
        self,
        tstamp: str,
        tstamp2: str,
    ) -> tuple[OffsetQL, int, OffsetQL]:
        offset: OffsetQL = self._tstampToOffset(tstamp)
        measSkip: int
        offset2: OffsetQL
        measSkip, offset2 = self._tstamp2ToMeasSkipAndOffset(tstamp2)

        return offset, measSkip, offset2

    _NOTE_UNICODE_CHAR_TO_NOTE_NAME: dict[str, str] = {
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
        self,
        text: str
    ) -> tuple[str | None, str | None, int | None]:
        # takes strings like "Andante M.M. 𝅗𝅥 = 128" and returns
        # 'Andante M.M.', '𝅗𝅥', and 128 (but only if the first match
        # is actually a note symbol from the SMuFL range (0xE1D0 - 0xE1EF).
        m = re.search(self._METRONOME_MARK_PATTERN, text)
        if m is None:
            return None, None, None

        tempoName: str | None = m.group(2)
        noteChar: str | None = m.group(3)
        notesPerMinute: str | None = m.group(4)

        if notesPerMinute is None or noteChar is None:
            return None, None, None

        if noteChar in self._NOTE_UNICODE_CHAR_TO_NOTE_NAME:
            return tempoName, noteChar, int(float(notesPerMinute) + 0.5)

        return None, None, None


    @staticmethod
    def chooseSubElement(appOrChoice: Element) -> Element | None:
        # self will eventually be used if we have a specified choice mechanism there...
        chosen: Element | None = None
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

    _EDITORIAL_ELEMENTS: tuple[str, ...] = (
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

    _IGNORED_EDITORIALS: tuple[str, ...] = (
        f'{MEI_NS}abbr',
        f'{MEI_NS}del',
        f'{MEI_NS}ref',
        f'{MEI_NS}restore',  # I could support restore with a special FromElement API
    )                        # that reverses the meaning of del and add

    _PASSTHRU_EDITORIALS: tuple[str, ...] = (
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

    _CHOOSING_EDITORIALS: tuple[str, ...] = (
        f'{MEI_NS}app',
        f'{MEI_NS}choice',
    )

    def octaveFromElement(
        self,
        elem: Element,
    ) -> tuple[
            str,
            tuple[OffsetQL | None, int | None, OffsetQL | None],
            spanner.Ottava | None
    ]:
        offset: OffsetQL = -1.
        measSkip: int | None = None
        offset2: OffsetQL | None = None

        ottavaLocalId = elem.get('m21Ottava', '')
        if not ottavaLocalId:
            environLocal.warn('no Ottava created in octave preprocessing')
            return ('', (-1., None, None), None)
        ottava: spanner.Spanner | None = (
            self.safeGetSpannerByIdLocal(ottavaLocalId, self.spannerBundle)
        )
        if ottava is None:
            environLocal.warn('no Ottava found from octave preprocessing')
            return ('', (-1., None, None), None)

        if t.TYPE_CHECKING:
            assert isinstance(ottava, spanner.Ottava)

        staffNStr: str = elem.get('staff', '')
        if not staffNStr:
            # get it from start note in ottava (should already be there)
            startObj: Music21Object | None = ottava.getFirst()
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
            offset = self._tstampToOffset(tstamp)
        if tstamp2:
            measSkip, offset2 = self._tstamp2ToMeasSkipAndOffset(tstamp2)

        return staffNStr, (offset, measSkip, offset2), ottava

    def arpegFromElement(
        self,
        elem: Element,
    ) -> tuple[
            str,
            tuple[OffsetQL | None, int | None, OffsetQL | None],
            expressions.ArpeggioMark | None
    ]:
        if elem.get('ignore_in_arpegFromElement') == 'true':
            return '', (-1., None, None), None

        staffNStr: str = elem.get('staff', '1')
        tstamp: str | None = elem.get('tstamp')
        if tstamp is None:
            environLocal.warn('missing @tstamp/@startid/@plist in <arpeg> element')
            return '', (-1., None, None), None

        offset: OffsetQL = self._tstampToOffset(tstamp)

        arrow: str = elem.get('arrow', '')
        order: str = elem.get('order', '')
        arpeggioType: str = self._ARPEGGIO_ARROW_AND_ORDER_TO_ARPEGGIOTYPE.get(
            (arrow, order),
            'normal'
        )

        arp = expressions.ArpeggioMark(arpeggioType=arpeggioType)
        return staffNStr, (offset, None, None), arp


    def trillFromElement(
        self,
        elem: Element,
    ) -> list[
        tuple[
            str,
            tuple[OffsetQL | None, int | None, OffsetQL | None],
            expressions.Trill | expressions.TrillExtension | None
        ]
    ]:
        output: list[
            tuple[
                str,
                tuple[OffsetQL | None, int | None, OffsetQL | None],
                expressions.Trill | expressions.TrillExtension | None
            ]
        ] = []

        # If no @staff, presume it is staff 1
        staffNStr = elem.get('staff', '')

        startId: str = elem.get('startid', '')
        tstamp: str = elem.get('tstamp', '')
        place: str = elem.get('place', 'place_unspecified')
        offset: OffsetQL | None = None

        if tstamp and elem.get('ignore_trill_in_trillFromElement') != 'true':
            accidUpper: str = elem.get('accidupper', '')
            accidLower: str = elem.get('accidlower', '')
            m21AccidName: str = ''
            if accidUpper:
                m21AccidName = self._m21AccidentalNameFromAccid(accidUpper)
            elif accidLower:
                m21AccidName = self._m21AccidentalNameFromAccid(accidLower)

            trill = expressions.Trill(accidentalName=m21AccidName)

            if place and place != 'place_unspecified':
                trill.placement = place
            else:
                trill.placement = None  # type: ignore

            offset = self._tstampToOffset(tstamp)
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
            trillExt: spanner.Spanner | None = (
                self.safeGetSpannerByIdLocal(trillExtLocalId, self.spannerBundle)
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

            measSkip: int | None = None
            offset2: OffsetQL | None = None
            if tstamp:
                offset = self._tstampToOffset(tstamp)
            if tstamp2:
                measSkip, offset2 = self._tstamp2ToMeasSkipAndOffset(tstamp2)

            trillExtStaffNStr: str = staffNStr
            if not trillExtStaffNStr:
                # get it from start note in trillExt (should already be there)
                startObj: Music21Object | None = trillExt.getFirst()
                if startObj is not None and hasattr(startObj, 'mei_staff'):
                    trillExtStaffNStr = startObj.mei_staff  # type: ignore
            if not trillExtStaffNStr:
                trillExtStaffNStr = '1'  # best we can do, hope it's ok

            output.append((trillExtStaffNStr, (offset, measSkip, offset2), trillExt))

        if not output:
            return [('', (-1., None, None), None)]
        return output

    def mordentFromElement(
        self,
        elem: Element,
    ) -> list[
        tuple[
            str,
            tuple[OffsetQL | None, int | None, OffsetQL | None],
            expressions.GeneralMordent | None
        ]
    ]:
        output: list[
            tuple[
                str,
                tuple[OffsetQL | None, int | None, OffsetQL | None],
                expressions.GeneralMordent | None
            ]
        ] = []

        # If no @staff, presume it is staff 1
        staffNStr = elem.get('staff', '1')

        tstamp: str = elem.get('tstamp', '')
        form: str = elem.get('form', '')
        place: str = elem.get('place', 'place_unspecified')
        offset: OffsetQL | None = None

        if elem.get('ignore_mordent_in_mordentFromElement') != 'true':
            # this happens if we need a mordent, but are missing @startid
            if not tstamp:
                environLocal.warn('missing @tstamp/@startid in <mordent> element')
                return [('', (-1., None, None), None)]

            accidUpper: str = elem.get('accidupper', '')
            accidLower: str = elem.get('accidlower', '')
            m21AccidName: str = ''
            if accidUpper:
                m21AccidName = self._m21AccidentalNameFromAccid(accidUpper)
            elif accidLower:
                m21AccidName = self._m21AccidentalNameFromAccid(accidLower)

            if not form:
                if accidUpper:
                    form = 'upper'
                elif accidLower:
                    form = 'lower'
                else:
                    form = 'upper'  # default

            mordent: expressions.GeneralMordent
            if form == 'upper':
                # music21 calls an upper mordent (i.e that goes up from the main note)
                # an InvertedMordent
                mordent = expressions.InvertedMordent(accidentalName=m21AccidName)
            else:
                mordent = expressions.Mordent(accidentalName=m21AccidName)

            # m21 mordents might not have placement... sigh...
            # But if I set it, it _will_ get exported to MusicXML (ha!).
            if place and place != 'place_unspecified':
                mordent.placement = place  # type: ignore
            else:
                mordent.placement = None  # type: ignore

            offset = self._tstampToOffset(tstamp)
            output.append((staffNStr, (offset, None, None), mordent))

        if not output:
            return [('', (-1., None, None), None)]
        return output

    def turnFromElement(
        self,
        elem: Element,
    ) -> list[
        tuple[
            str,
            tuple[OffsetQL | None, int | None, OffsetQL | None],
            expressions.Turn | None
        ]
    ]:
        output: list[
            tuple[
                str,
                tuple[OffsetQL | None, int | None, OffsetQL | None],
                expressions.Turn | None
            ]
        ] = []

        # If no @staff, presume it is staff 1
        staffNStr = elem.get('staff', '1')

        tstamp: str = elem.get('tstamp', '')
        form: str = elem.get('form', '')
        theType: str = elem.get('type', '')
        delayed: str = elem.get('delayed', 'false')
        place: str = elem.get('place', 'place_unspecified')
        offset: OffsetQL | None = None

        if elem.get('ignore_turn_in_turnFromElement') != 'true':
            # this happens if we need a turn, but are missing @startid
            if not tstamp:
                environLocal.warn('missing @tstamp/@startid in <turn> element')
                return [('', (-1., None, None), None)]

            accidUpper: str = elem.get('accidupper', '')
            accidLower: str = elem.get('accidlower', '')
            m21AccidUpper: str = ''
            m21AccidLower: str = ''
            if accidUpper:
                m21AccidUpper = self._m21AccidentalNameFromAccid(accidUpper)
            if accidLower:
                m21AccidLower = self._m21AccidentalNameFromAccid(accidLower)

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
            delay: OrnamentDelay | OffsetQL = OrnamentDelay.NO_DELAY
            if delayed == 'true':
                # we'll mark it as "default" delayed for now.
                # Once we have a note for it, we'll figure out
                # what the delay is (turn.offset - note.offset)
                # and recreate a turn/inverted turn with that
                # exact delay at that point.
                delay = OrnamentDelay.DEFAULT_DELAY

            if form == 'upper':
                turn = expressions.Turn(
                    delay=delay,
                    upperAccidentalName=m21AccidUpper,
                    lowerAccidentalName=m21AccidLower
                )
            else:
                turn = expressions.InvertedTurn(
                    delay=delay,
                    upperAccidentalName=m21AccidUpper,
                    lowerAccidentalName=m21AccidLower
                )

            if place and place != 'place_unspecified':
                turn.placement = place
            else:
                turn.placement = None  # type: ignore


            offset = self._tstampToOffset(tstamp)
            output.append((staffNStr, (offset, None, None), turn))

        if not output:
            return [('', (-1., None, None), None)]
        return output


    def hairpinFromElement(
        self,
        elem: Element,
    ) -> tuple[
            str,
            tuple[OffsetQL | None, int | None, OffsetQL | None],
            m21.dynamics.DynamicWedge | None
    ]:
        offset: OffsetQL = -1.
        measSkip: int | None = None
        offset2: OffsetQL | None = None

        hairpinLocalId = elem.get('m21Hairpin', '')
        if not hairpinLocalId:
            environLocal.warn('no Hairpin created in hairpin preprocessing')
            return ('', (-1., None, None), None)
        hairpin: m21.spanner.Spanner | None = (
            self.safeGetSpannerByIdLocal(hairpinLocalId, self.spannerBundle)
        )
        if hairpin is None:
            environLocal.warn('no Hairpin found from hairpin preprocessing')
            return ('', (-1., None, None), None)

        if t.TYPE_CHECKING:
            assert isinstance(hairpin, m21.dynamics.DynamicWedge)

        staffNStr: str = elem.get('staff', '')
        if not staffNStr:
            # get it from hairpin
            if hasattr(hairpin, 'mei_staff'):
                staffNStr = hairpin.mei_staff  # type: ignore
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
            hairpin.mei_needs_start_anchor = True  # type: ignore
        if not endId:
            hairpin.mei_needs_end_anchor = True  # type: ignore
        if tstamp:
            offset = self._tstampToOffset(tstamp)
        if tstamp2:
            measSkip, offset2 = self._tstamp2ToMeasSkipAndOffset(tstamp2)

        return staffNStr, (offset, measSkip, offset2), hairpin

    def dynamFromElement(
        self,
        elem: Element,
    ) -> tuple[
        str,
        tuple[OffsetQL | None, int | None, OffsetQL | None],
        dynamics.Dynamic | None
    ]:
        if elem.get('ignore_in_dynamFromElement') == 'true':
            return '', (-1., None, None), None

        staffNStr: str
        offsets: tuple[OffsetQL | None, int | None, OffsetQL | None]
        dynamObj: dynamics.Dynamic

        # first parse as a <dir> giving a TextExpression with style,
        # then try to derive dynamic info from that.
        teWithStyle: expressions.TextExpression | None
        staffNStr, offsets, teWithStyle = (
            self.dirFromElement(elem)
        )
        if teWithStyle is None:
            return '', (-1., None, None), None

        if t.TYPE_CHECKING:
            assert isinstance(teWithStyle.style, style.TextStyle)

        dynamObj = self._dynamFromTextExpression(teWithStyle)
        return staffNStr, offsets, dynamObj

    @staticmethod
    def _dynamFromTextExpression(te: m21.expressions.TextExpression) -> m21.dynamics.Dynamic:
        dynamObj = dynamics.Dynamic(te.content)
        if te.hasStyleInformation:
            dynamObj.style = te.style
        else:
            # Undo music21's default Dynamic absolute positioning
            dynamObj.style.absoluteX = None
            dynamObj.style.absoluteY = None

        if te.placement is not None:
            dynamObj.placement = te.placement

        return dynamObj

    def tempoFromElement(
        self,
        elem: Element,
    ) -> tuple[
        str,
        tuple[OffsetQL | None, int | None, OffsetQL | None],
        tempo.TempoIndication | None
    ]:
        if elem.get('ignore_in_tempoFromElement') == 'true':
            return '', (-1., None, None), None

        # first parse as a <dir> giving a TextExpression with style,
        # then try to derive tempo info from that.
        staffNStr: str
        offsets: tuple[OffsetQL | None, int | None, OffsetQL | None]
        teWithStyle: expressions.TextExpression | None
        staffNStr, offsets, teWithStyle = (
            self.dirFromElement(elem)
        )
        if teWithStyle is None:
            return '', (-1., None, None), None

        midiBPMStr: str = elem.get('midi.bpm', '')
        if not midiBPMStr:
            # only use the pending one if it's useful.
            midiBPMStr = self.pendingMIDIBPM
        # Whether we used it or not, self.pendingMIDIBPM is only intended
        # for the first <tempo> so we clear it here.
        self.pendingMIDIBPM = ''

        tempoObj: m21.tempo.MetronomeMark = (
            self._metronomeMarkFromTextExpressionAndMidiBPMStr(teWithStyle, midiBPMStr)
        )

        return staffNStr, offsets, tempoObj

    def _metronomeMarkFromTextExpressionAndMidiBPMStr(
        self,
        te: m21.expressions.TextExpression,
        midiBPMStr: str
    ) -> m21.tempo.MetronomeMark:
        midiBPM: int | None = None
        if midiBPMStr:
            try:
                midiBPM = int(float(midiBPMStr))
            except (TypeError, ValueError):
                pass

        # default tempo placement should be above
        if te.placement is None:
            te.placement = 'above'

        if t.TYPE_CHECKING:
            assert isinstance(te.style, style.TextStyle)

        # default tempo text style should be bold
        if not te.hasStyleInformation:
            te.style.fontStyle = 'bold'
        elif te.style.fontWeight is None and te.style.fontStyle is None:
            te.style.fontStyle = 'bold'

        # Note that we have to make a TempoText from te first, since
        # MetronomeMark won't take text=TextExpression.
        tempoObj: m21.tempo.TempoIndication
        tempoObj = m21.tempo.TempoText()
        tempoObj.setTextExpression(te)

        tempoObj = m21.tempo.MetronomeMark(
            text=tempoObj,
            number=midiBPM,
            referent=None  # implies quarter note
        )

        # Avoid adding any extra "𝅗𝅥 = 128" text to the display of this metronome mark
        tempoObj.numberImplicit = True

        # work around bug in MetronomeMark.text setter where style is not linked
        # when text is a TempoText
        tempoObj.style = te.style

        # transfer placement to the metronome mark
        tempoObj.placement = te.placement

        return tempoObj

    @staticmethod
    def _glyphNameToUnicodeChar(name: str) -> str:
        # name is things like 'noteQuarterUp', which can be looked up
        return SharedConstants._SMUFL_NAME_TO_UNICODE_CHAR.get(name, '')

    @staticmethod
    def _glyphNumToUnicodeChar(num: str) -> str:
        # num can be '#xNNNN' or 'U+NNNN'
        pattern: str = r'^(#x|U\+)([A-F0-9]+)$'
        m = re.match(pattern, num)
        if m is None:
            return ''
        return chr(int(m.group(2), 16))

    def textFromElem(self, elem: Element) -> tuple[str, dict[str, str]]:
        styleDict: dict[str, str] = {}
        text: str = ''
        if elem.text:
            if elem.text[0] != '\n' or not elem.text.isspace():
                text += elem.text

        for el in elem.iterfind('*'):
            # do whatever is appropriate given el.tag (<rend> for example)
            if el.tag == f'{MEI_NS}rend':
                # music21 doesn't currently support changing style in the middle of a
                # TextExpression, so we just grab the first ones we see and save them
                # off to use.
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

            elif el.tag in self._CHOOSING_EDITORIALS:
                subEl: Element | None = self.chooseSubElement(el)
                if subEl is None:
                    continue
                el = subEl
            elif el.tag in self._PASSTHRU_EDITORIALS:
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
                        text += self._glyphNumToUnicodeChar(glyphNum)
                    elif glyphName:
                        text += self._glyphNameToUnicodeChar(glyphName)

            # grab the text from el
            elText: str
            elStyleDict: dict[str, str]
            elText, elStyleDict = self.textFromElem(el)
            text += elText
            styleDict.update(elStyleDict)

            # grab the text between this el and the next el
            if el.tail:
                if el.tail[0] != '\n' or not el.tail.isspace():
                    text += el.tail

        return text, styleDict

    def dirFromElement(
        self,
        elem: Element,
    ) -> tuple[
        str,
        tuple[OffsetQL | None, int | None, OffsetQL | None],
        expressions.TextExpression | None
    ]:
        # returns (staffNStr, (offset, None, None), te)
        if elem.get('ignore_in_dirFromElement') == 'true':
            return '', (-1., None, None), None

        # If no @staff, presume it is staff 1; I've seen <tempo> without @staff, for example.
        staffNStr = elem.get('staff', '1')
        offset: OffsetQL
        te: expressions.TextExpression

        typeAtt: str | None = elem.get('type')
        if typeAtt is not None and typeAtt == 'fingering':
            return '', (-1., None, None), None

        # @tstamp is required for now, someday we'll be able to derive offsets from @startid
        tstamp: str | None = elem.get('tstamp')
        if tstamp is None:
            environLocal.warn('missing @tstamp in <dir> element')
            return '', (-1., None, None), None

        offset = self._tstampToOffset(tstamp)

        # @enclose is technically not always legal, but I've seen it in <dynam>,
        # so support it here for everyone.
        enclose: str | None = elem.get('enclose')
        place: str | None = elem.get('place')
        text: str
        styleDict: dict[str, str]

        text, styleDict = self.textFromElem(elem)
        text = html.unescape(text)
        text = text.strip()
        if enclose is not None:
            if enclose == 'paren':
                text = '( ' + text + ' )'
            elif enclose == 'brack':
                text = '[ ' + text + ' ]'

        fontStyle: str | None = styleDict.get('fontStyle', None)
        fontWeight: str | None = styleDict.get('fontWeight', None)
        fontFamily: str | None = styleDict.get('fontFamily', None)
        justify: str | None = styleDict.get('justify', None)

        te = self._textExpressionFromPieces(
            text,
            fontStyle,
            fontWeight,
            fontFamily,
            justify,
            place
        )

        return staffNStr, (offset, None, None), te

    def _textExpressionFromPieces(
        self,
        text: str,
        fontStyle: str | None,
        fontWeight: str | None,
        fontFamily: str | None,
        justify: str | None,
        place: str | None
    ) -> m21.expressions.TextExpression:
        te = m21.expressions.TextExpression(text)

        if t.TYPE_CHECKING:
            assert isinstance(te.style, m21.style.TextStyle)

    #     if elem.tag == f'{MEI_NS}dir':
    #         # Match Verovio's default: <dir> with no fontStyle should be italic
    #         if fontStyle is None:
    #             fontStyle = 'italic'

        if fontStyle or fontWeight:
            te.style.fontStyle = (
                self._m21FontStyleFromMeiFontStyleAndWeight(fontStyle, fontWeight)
            )
        if fontFamily:
            te.style.fontFamily = fontFamily
        if justify:
            te.style.justify = justify

        if place:
            if place == 'above':
                te.placement = 'above'
            elif place == 'below':
                te.placement = 'below'
            elif place == 'between':
                te.placement = 'below'
                te.style.alignVertical = 'middle'
            else:
                environLocal.warn(f'invalid @place="{place}"')

        return te

    def fermataFromElement(
        self,
        elem: Element,
    ) -> tuple[
        str,
        tuple[OffsetQL | None, int | None, OffsetQL | None],
        expressions.Fermata | None
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
        tstamp: str | None = elem.get('tstamp')
        if tstamp is None:
            environLocal.warn('<fermata> element is missing @tstamp and @startid')
            return '', (-1., None, None), None

        offset = self._tstampToOffset(tstamp)

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

    @staticmethod
    def _m21FontStyleFromMeiFontStyleAndWeight(
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

    def measureFromElement(
        self,
        elem: Element,
        backupNum: int,
        expectedNs: t.Iterable[str]
    ) -> dict[str, stream.Measure | bar.Repeat]:
        '''
        <measure> Unit of musical time consisting of a fixed number of note-values of a given type,
        as determined by the prevailing meter, and delimited in musical notation by two bar lines.

        In MEI 2013: pg.365 (379 in PDF) (MEI.cmn module)

        :param elem: The ``<measure>`` element to process.
        :type elem: :class:`~xml.etree.ElementTree.Element`
        :param int backupNum: A fallback value for the resulting
            :class:`~music21.stream.Measure` objects' number attribute.
        :param expectedNs: A list of the expected @n attributes for the <staff> tags in this
            <measure>. If an expected <staff> isn't in the <measure>, it will be created with
            a full-measure rest.
        :type expectedNs: iterable of str
        :returns: A dictionary where keys are the @n attributes for <staff> tags found in this
            <measure>, and values are :class:`~music21.stream.Measure` objects that should be
            appended to the :class:`~music21.stream.Part` instance with the value's @n attributes.
        :rtype: dict of :class:`~music21.stream.Measure`, with one exception.

        .. note:: When the right barline is set to ``'rptboth'`` in MEI, it requires adjusting the
            left barline of the following <measure>. If this happens, a :class:`Repeat` object is
            assigned to the ``'next @left'`` key in the returned dictionary.

        **Attributes/Elements Implemented:**

        - contained elements: <staff> and <staffDef>
        - @right and @left (att.measure.log)
        - @n (att.common)

        **Attributes Ignored:**

        - @xml:id (att.id)
        - <slur> and <tie> contained within. These spanners will usually be attached to their
            starting and ending notes with @xml:id attributes, so it's not necessary to process
            them when encountered in a <measure>. Furthermore, because the possibility exists for
            cross-measure slurs and ties, we can't guarantee we'll be able to process all spanners
            until all spanner-attachable objects are processed. So we manage these tags at a higher
            level.

        **Attributes/Elements in Testing:** none

        **Attributes not Implemented:**

        - att.common (@label, @xml:base)
        - att.declaring (@decls)
        - att.facsimile (@facs)
        - att.typed (@type, @subtype)
        - att.pointing (@xlink:*, @target, @targettype)
        - att.measure.log (att.meterconformance.bar (@metcon, @control))
        - att.measure.vis (all)
        - att.measure.ges (att.timestamp.performed (@tstamp.ges, @tstamp.real))
        - att.measure.anl (all)

        **Contained Elements not Implemented:**

        - MEI.cmn: beamSpan bend breath gliss harpPedal ossia pedal reh tupletSpan
        - MEI.edittrans: gap handShift
        - MEI.harmony: harm
        - MEI.midi: midi
        - MEI.shared: annot phrase
        - MEI.text: div
        - MEI.usersymbols: anchoredText curve line symbol
        '''
        # staves is mostly Measures, but can contain a single Repeat, as well
        staves: dict[str, stream.Measure | bar.Repeat] = {}

        # for staff-specific objects processed before the corresponding staff
        # key1 is @n, key2 is 'meter', 'key', 'instrument', etc
        stavesWaitingFromStaffDef: dict[str, dict[str, Music21Object]] = {}

        # for staffItem objects processed before the corresponding staff
        # key is @staff, value is a list of tuple(offsets, object)
        stavesWaitingFromStaffItem: dict[
            str,
            list[
                tuple[
                    tuple[OffsetQL | None, int | None, OffsetQL | None],  # offsets
                    Music21Object
                ]
            ]
        ] = {}

        # spanner end GeneralNotes we are waiting to insert in the correct measure
        pendingSpannerEnds: list[tuple[str, spanner.Spanner, int, OffsetQL]] | None = (
            self.pendingSpannerEnds
        )
        self.pendingSpannerEnds = []

        # spanner end GeneralNotes we are STILL waiting to insert after processing this measure
        newPendingSpannerEnds: list[tuple[str, spanner.Spanner, int, OffsetQL]] = []

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
                    endObj = spanner.SpannerAnchor()
                    spannerObj.addSpannedElements(endObj)
                    if staffNStr not in stavesWaitingFromStaffItem:
                        stavesWaitingFromStaffItem[staffNStr] = []
                    stavesWaitingFromStaffItem[staffNStr].append(
                        ((offset, None, None), endObj)
                    )
                else:
                    # spannerEnd is still pending (albeit with decremented measSkip)
                    newPendingSpannerEnds.append(
                        (staffNStr, spannerObj, measSkip, offset)
                    )
            if newPendingSpannerEnds:
                self.pendingSpannerEnds = newPendingSpannerEnds

        # mapping from tag name to our converter function
        staffTag: str = f'{MEI_NS}staff'
        staffDefTag: str = f'{MEI_NS}staffDef'

        measureNum: str | int = elem.get('n', backupNum)

        # track the bar's duration
        maxBarDuration: OffsetQL | None = None

        # iterate all immediate children
        for eachElem in elem.iterfind('*'):
            nStr: str | None = eachElem.get('n')
            if staffTag == eachElem.tag:
                if nStr is None:
                    raise MeiElementError(_STAFF_MUST_HAVE_N)

                self.staffNumberForNotes = nStr
                measureList = self.staffFromElement(eachElem)
                self.staffNumberForNotes = ''

                meas: stream.Measure = stream.Measure(number=measureNum)

                # We can't pass measureList to Measure() because it's a mixture of obj/Voice, and
                # if it starts with obj, Measure() will get confused and append everything,
                # including Voices, and that will be all wrong.  This by-hand approach
                # (insert(0) everything) will work until such time as we generate top-level
                # objects in the measure that are not at offset 0, and at that point we will
                # need to return object offsets with each object, so we can insert them
                # appropriately.
                for measureObj in measureList:
                    meas.insert(0, measureObj)

                staves[nStr] = meas

                thisBarDuration: OffsetQL = staves[nStr].duration.quarterLength
                if maxBarDuration is None or maxBarDuration < thisBarDuration:
                    maxBarDuration = thisBarDuration

            elif staffDefTag == eachElem.tag:
                if nStr is None:
                    environLocal.warn(_UNIMPLEMENTED_IMPORT_WITHOUT.format('<staffDef>', '@n'))
                else:
                    self.staffNumberForDef = nStr
                    stavesWaitingFromStaffDef[nStr] = self.staffDefFromElement(
                        eachElem
                    )
                    self.staffNumberForDef = ''

            elif eachElem.tag in self.staffItemsTagToFunction:
                offsets: tuple[OffsetQL | None, int | None, OffsetQL | None]
                m21Obj: Music21Object | None
                triple: tuple[
                    str,
                    tuple[OffsetQL | None, int | None, OffsetQL | None],
                    Music21Object
                ]
                triple = self.staffItemsTagToFunction[eachElem.tag](
                    eachElem
                )

                # Sometimes staffItemsTagToFunction actually returns a _list_ of
                # (staffNStr, offsets, m21Obj) triples instead of just one such triple.
                triples: list[
                    tuple[
                        str,
                        tuple[OffsetQL | None, int | None, OffsetQL | None],
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
                        offset1: OffsetQL | None = offsets[0]
                        measSkip2: int | None = offsets[1]
                        offset2: OffsetQL | None = offsets[2]

                        if isinstance(m21Obj, spanner.Spanner):
                            spannerObj = m21Obj
                            # If it needs start or end notes make them now.
                            needsStartAnchor: bool = False
                            needsEndAnchor: bool = False
                            if hasattr(m21Obj, 'mei_needs_start_anchor'):
                                needsStartAnchor = (
                                    spannerObj.mei_needs_start_anchor  # type: ignore
                                )
                                del spannerObj.mei_needs_start_anchor  # type: ignore
                            if hasattr(m21Obj, 'mei_needs_end_anchor'):
                                needsEndAnchor = (
                                    spannerObj.mei_needs_end_anchor  # type: ignore
                                )
                                del spannerObj.mei_needs_end_anchor  # type: ignore

                            if needsStartAnchor:
                                startObj = spanner.SpannerAnchor()
                                spannerObj.addSpannedElements(startObj)
                                stavesWaitingFromStaffItem[staffNStr].append(
                                    ((offset1, None, None), startObj)
                                )
                            if needsEndAnchor:
                                if measSkip2 == 0:
                                    # do the endObj as well, it's in this same Measure
                                    endObj = spanner.SpannerAnchor()
                                    spannerObj.addSpannedElements(endObj)
                                    stavesWaitingFromStaffItem[staffNStr].append(
                                        ((offset2, None, None), endObj)
                                    )
                                else:
                                    # endNote has to wait for a subsequent measure
                                    if measSkip2 is None or offset2 is None:
                                        raise MeiInternalError(
                                            'spanner needing endAnchor had no measSkip2/offset2'
                                        )
                                    self.pendingSpannerEnds.append(
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
        # We must process them now because, if we did it in the loop above,
        # the respective <staff> may not be processed before the <staffDef>.
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
        tsExpressions: list[tuple[list[str], OffsetQL, expressions.Expression]] = []

        # Process objects from staffItems (e.g. Direction, Fermata, etc)
        for whichStaff, eachList in stavesWaitingFromStaffItem.items():
            for (eachOffset, eachMeasSkip2, eachOffset2), eachObj in eachList:
                # parse whichStaff, which might be '1', '2', '1 2', etc
                staffNs: list[str] = re.findall(r'[\d]+', whichStaff)
                if not staffNs:
                    raise MeiAttributeError(
                        _STAFFITEM_MUST_HAVE_VALID_STAFF.format(
                            eachObj.classes[0], whichStaff
                        )
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

                spanners: list[spanner.Spanner] = eachObj.getSpannerSites()
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
        # 888 These should likely be invisible rests.
        for eachN in expectedNs:
            if eachN not in staves:
                restVoice = stream.Voice([note.Rest(quarterLength=maxBarDuration)])
                restVoice.id = '1'
                # just in case (e.g., when all the other voices are <mRest>)
                restVoice[0].m21wasMRest = True
                staves[eachN] = stream.Measure([restVoice], number=measureNum)

        # First search for Rest objects created by an <mRest> element that didn't have @dur set.
        # This will only work in cases where not all of the parts are resting. However, it avoids
        # a more time-consuming search later.
        if (maxBarDuration == self._DUR_ATTR_DICT[None]
                and self.activeMeter is not None
                and maxBarDuration != self.activeMeter.barDuration.quarterLength):
            # In this case, all the staves have <mRest> elements without a @dur.
            self._correctMRestDurs(staves, self.activeMeter.barDuration.quarterLength)
        else:
            # In this case, some or none of the staves have an <mRest> element without a @dur.
            if t.TYPE_CHECKING:
                assert maxBarDuration is not None
            self._correctMRestDurs(staves, maxBarDuration)

        # assign left and right barlines
        staves = self._makeBarlines(elem, staves)

        # take the timestamped fermatas, etc, and find notes/barlines to put them on
        self._addTimestampedExpressions(staves, tsExpressions)

        return staves

    def sectionScoreCore(
        self,
        elem: Element,
        allPartNs: tuple[str, ...],
        nextMeasureLeft: bar.Repeat | None = None,
        backupMeasureNum: int = 0
    ) -> tuple[
            dict[str, list[Music21Object | list[Music21Object]]],
            bar.Repeat | None,
            int]:
        '''
        This function is the "core" of both :func:`sectionFromElement` and
        :func:`scoreFromElement`, since both elements are treated quite similarly (though not
        identically). It is also used to process 'ending' elements (which are a sort of section,
        I guess).  It's a separate and shared function to reduce code duplication and increase
        ease of testing. It's a "public" function to help spread the burden of API documentation
        complexity: while the parameters and return values are described in this function, the
        compliance with the MEI Guidelines is described in both :func:`sectionFromElement` and
        :func:`scoreFromElement`, as expected.

        **Required Parameters**

        :param elem: The <section> or <score> element to process.
        :type elem: :class:`xml.etree.ElementTree.Element`
        :param allPartNs: A tuple of the expected @n attributes for the <staff> tags in this
            <section>. This tells the function how many parts there are and what @n values
            they use.
        :type allPartNs: tuple of str

        **Optional Keyword Parameters**

        The following parameters are all optional, and must be specified as a keyword argument
        (i.e. you specify the parameter name before its value).

        :param nextMeasureLeft: The @left attribute to use for the next <measure> element
            encountered. This is used for situations where one <measure> element specified a
            @right attribute that must be imported by music21 as *both* the right barline of one
            measure and the left barline of the following; at the moment this is only @rptboth,
            which requires a :class:`Repeat` in both cases.
        :type nextMeasureLeft: :class:`music21.bar.Barline` or :class:`music21.bar.Repeat`
        :param backupMeasureNum: In case a <measure> element is missing its @n attribute,
            :func:`measureFromElement` will use this automatically-incremented number instead. The
            ``backupMeasureNum`` corresponding to the final <measure> in this <score> or <section>
            is returned from this function.
        :type backupMeasureNum: int
        :returns: Three-tuple with a dictionary of results, the new value of ``nextMeasureLeft``,
            and the new value of ``backupMeasureNum``.
        :rtype: (dict, :class:`~music21.bar.Barline`, int)

        **Return Value**

        In short, it's ``parsed``, ``nextMeasureLeft``, ``backupMeasureNum``.

        - ``'parsed'`` is a dictionary where the keys are the values in ``allPartNs`` and the
            values are a list of all the :class:`Measure` objects in that part, as found in this
            <section> or <score>.
        - ``'nextMeasureLeft'`` is the value that should be assigned to the :attr:`leftBarline`
            attribute of the first :class:`Measure` found in the next <section>. This will almost
            always be None.
        - ``'backupMeasureNum'`` is equal to the ``backupMeasureNum`` argument plus the number of
            <measure> elements found in this <score> or <section>.
        '''
        # pylint: disable=too-many-nested-blocks
        # ^^^ -- was not required at time of contribution

        # TODO: replace the returned 4-tuple with a namedtuple

        scoreTag: str = f'{MEI_NS}score'
        sectionTag: str = f'{MEI_NS}section'
        endingTag: str = f'{MEI_NS}ending'
        measureTag: str = f'{MEI_NS}measure'
        scoreDefTag: str = f'{MEI_NS}scoreDef'
        staffDefTag: str = f'{MEI_NS}staffDef'
        pbTag: str = f'{MEI_NS}pb'
        sbTag: str = f'{MEI_NS}sb'

        # hold the list of music21.Music21Objects that we're building for each music21.stream.Part
        parsed: dict[str, list[Music21Object | list[Music21Object]]] = {
            n: [] for n in allPartNs
        }

        # if elem is a <score> and this is the first scoreDef in that score, then we also will
        # be creating a dict of Part/PartStaffs, keyed by every 'n' in allPartNs, as well as a list
        # of StaffGroups, which reference the PartStaffs.
        scoreDefSeen: bool = False

        # hold things that belong in the following "Thing" (either Measure or Section)
        inNextThing: dict[str, list[Music21Object | list[Music21Object]]] = {
            n: [] for n in allPartNs
        }
        if self.pendingInNextThing:
            inNextThing.update(self.pendingInNextThing)
            self.pendingInNextThing = {}

        if not self.topPartN:
            # This will only happen if scoreFromElement hasn't been called, which would
            # only happen in a test scenario.  But we can figure it out, so we do.
            self.topPartN = allPartNs[0]

        # we ignore any <pb>/<sb> elements before the first <measure> in the document
        # This is because Verovio's Humdrum -> MEI conversion likes to put one in that
        # wasn't in the Humdrum doc, leaving the first page blank.
        # Here's the verovio/src/iohumdrum.cpp comment:
        #   // An initial page break is required in order for the system
        #   // breaks encoded in the file to be activated, so adding a
        #   // dummy page break here:

        haveSeenMeasure: bool = False

        for eachElem in elem.iterfind('*'):
            # only process <measure> elements if this is a <section> or <ending>
            if measureTag == eachElem.tag and elem.tag in (sectionTag, endingTag):
                haveSeenMeasure = True
                backupMeasureNum += 1

                # start of new measure, clear accidentals from all staff alter lists
                for eachN in allPartNs:
                    self.updateStaffAltersForMeasureStart(eachN)

                # process all the stuff in the <measure>
                measureResult = self.measureFromElement(
                    eachElem, backupMeasureNum, allPartNs
                )

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
                # we only fully parse staffGrps (creating Parts/PartStaffs and StaffGroups)
                # in the very first <scoreDef> in the <score>.  After that we just scan them
                # for staffDefs.
                parseStaffGrps: bool = elem.tag == scoreTag and not scoreDefSeen
                localResult = self.scoreDefFromElement(
                    eachElem,
                    allPartNs,
                    parseStaffGrps=parseStaffGrps
                )
                scoreDefSeen = True

                # copy all the parts and staffGroups from localResult to parsed
                wholeScoreObjects = localResult.get('whole-score objects')
                if wholeScoreObjects:
                    parsed['whole-score objects'] = wholeScoreObjects  # type: ignore

                for topPartObject in localResult['top-part objects']:
                    if t.TYPE_CHECKING:
                        # because 'top-part objects' is a list of objects
                        assert isinstance(topPartObject, Music21Object)
                    inNextThing[self.topPartN].append(topPartObject)

                for allPartObject in localResult['all-part objects']:
                    if t.TYPE_CHECKING:
                        # because 'all-part objects' is a list of objects
                        assert isinstance(allPartObject, Music21Object)

                    newKey: key.Key | key.KeySignature | None = None
                    if isinstance(allPartObject, key.KeySignature):
                        newKey = allPartObject

                    if isinstance(allPartObject, meter.TimeSignature):
                        self.activeMeter = allPartObject

                    for i, eachN in enumerate(allPartNs):
                        if i == 0:
                            to_insert = allPartObject
                        else:
                            # a single Music21Object should not exist in multiple parts
                            to_insert = deepcopy(allPartObject)
                        inNextThing[eachN].append(to_insert)

                        if newKey is not None:
                            self.updateStaffKeyAndAltersWithNewKey(eachN, newKey)

                for eachN in allPartNs:
                    if eachN in localResult:
                        resultNDict = localResult[eachN]
                        if t.TYPE_CHECKING:
                            # because localResult['n'] is a dict[str, Music21Object]
                            assert isinstance(resultNDict, dict)
                        for eachObj in resultNDict.values():
                            if isinstance(eachObj, meter.TimeSignature):
                                self.activeMeter = eachObj
                            inNextThing[eachN].append(eachObj)

            elif staffDefTag == eachElem.tag:
                nStr: str | None = eachElem.get('n')
                if nStr is not None:
                    self.staffNumberForDef = nStr
                    for eachObj in self.staffDefFromElement(eachElem).values():
                        if isinstance(eachObj, meter.TimeSignature):
                            self.activeMeter = eachObj
                        inNextThing[nStr].append(eachObj)
                    self.staffNumberForDef = ''
                else:
                    # At the moment, to process this here, we need an @n on the <staffDef>. A
                    # document may have a still-valid <staffDef> if the <staffDef> has an @xml:id
                    # with which <staff> elements may refer to it.
                    environLocal.warn(_UNIMPLEMENTED_IMPORT_WITHOUT.format('<staffDef>', '@n'))

            elif eachElem.tag in (sectionTag, endingTag):
                # NOTE: same as scoreFE() (except the name of "inNextThing")
                localParsed, nextMeasureLeft, backupMeasureNum = (
                    self.sectionFromElement(
                        eachElem,
                        allPartNs,
                        nextMeasureLeft,
                        backupMeasureNum)
                )

                for eachN, eachList in localParsed.items():
                    # NOTE: "eachList" is a list of objects that will become a music21 Part.
                    #
                    # first: if there were objects from a previous <scoreDef> or <staffDef>, we
                    # need to put those into the first Measure object we encounter in this Part.
                    # TODO: this is where the Instruments get added
                    # TODO: I think "eachList" really means "each list that will become a Part"
                    if eachN == 'whole-score objects':
                        continue

                    if inNextThing[eachN]:
                        # we have to put Instrument objects just before the Measure
                        # to which they apply
                        theInstr = None
                        theInstrI = None
                        for i, eachInsertion in enumerate(inNextThing[eachN]):
                            if isinstance(eachInsertion, m21.instrument.Instrument):
                                theInstr = eachInsertion
                                theInstrI = i
                                break

                        # Put the Instrument right in front, then remove it from "inNextThing"
                        # so it doesn't show up twice.
                        if theInstr:
                            if t.TYPE_CHECKING:
                                assert theInstrI is not None
                            eachList.insert(0, theInstr)
                            del inNextThing[eachN][theInstrI]

                        for eachMeasure in eachList:
                            # NOTE: "eachMeasure" is one of the things that will be in the Part,
                            # which are probably but not necessarily Measures
                            if isinstance(eachMeasure, stream.Stream):
                                # NOTE: ... but now eachMeasure is virtually guaranteed to
                                # be a Measure
                                for eachInsertion in inNextThing[eachN]:
                                    eachMeasure.insert(0.0, eachInsertion)
                                break
                        inNextThing[eachN] = []

                    # Then we can append the objects in this Part to the dict of all parsed
                    # objects, but NOTE that this is different for <section> and <score>.
                    if elem.tag in (sectionTag, endingTag):
                        # First make a RepeatBracket if this is an <ending>.
                        rb: spanner.RepeatBracket | None = None
                        if endingTag == eachElem.tag:
                            # make the RepeatBracket for the ending
                            bracketNStr: str | None = eachElem.get('n')
                            n: int = 0
                            if bracketNStr is not None:
                                try:
                                    n = int(bracketNStr)
                                except Exception:
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
                        # If this is a <score>, we can just append the result of each <section>
                        # to the list that will become the Part.

                        # we know eachList is not a list of lists, it's just a list or an object,
                        # so disable mypy checking the type.
                        parsed[eachN].append(eachList)  # type: ignore

            elif eachElem.tag == pbTag:
                if haveSeenMeasure:
                    pageBreak: m21.layout.PageLayout | None = self.pageBreakFromElement(
                        eachElem,
                    )
                    if pageBreak is not None:
                        self.nextBreak = pageBreak

            elif eachElem.tag == sbTag:
                if haveSeenMeasure:
                    systemBreak: m21.layout.SystemLayout | None = self.systemBreakFromElement(
                        eachElem,
                    )
                    # if we see both breaks, ignore the system break and use the page break
                    if systemBreak is not None:
                        if not isinstance(self.nextBreak, m21.layout.PageLayout):
                            self.nextBreak = systemBreak

            elif eachElem.tag == f'{MEI_NS}choice':
                # ignore <choice> in <section> silently if contents are:
                # <orig> <expansion/> </orig> <reg> <expansion/> </reg>...
                # because there isn't anything interesting there, and verovio's humdrum -> MEI
                # conversion puts this in <section> all the time.
                if not self._isExpansionChoice(eachElem):
                    environLocal.warn(_UNPROCESSED_SUBELEMENT.format(eachElem.tag, elem.tag))

            elif eachElem.tag not in _IGNORE_UNPROCESSED:
                environLocal.warn(_UNPROCESSED_SUBELEMENT.format(eachElem.tag, elem.tag))

        # TODO: write the <section @label=""> part

        # if there's anything left in "inNextThing", stash it off for the _next_ measure or section
        self.pendingInNextThing = inNextThing

        return parsed, nextMeasureLeft, backupMeasureNum

    @staticmethod
    def _isExpansionChoice(elem: Element) -> bool:
        if elem.tag != f'{MEI_NS}choice':
            return False

        for choice in elem.iterfind('*'):
            if choice.tag not in (f'{MEI_NS}orig', f'{MEI_NS}reg'):
                return False
            items: list[Element] = choice.findall('*')
            if len(items) != 1:
                return False
            if items[0].tag != f'{MEI_NS}expansion':
                return False

        return True

    def sectionFromElement(
        self,
        elem: Element,
        allPartNs: tuple[str, ...],
        nextMeasureLeft: bar.Repeat | None,
        backupMeasureNum: int
    ) -> tuple[
            dict[str, list[Music21Object | list[Music21Object]]],
            bar.Repeat | None,
            int]:
        '''
        <section> Segment of music data.

        In MEI 2013: pg.432 (446 in PDF) (MEI.shared module)

        .. note:: The parameters and return values are exactly the same for
            :func:`sectionFromElement` and :func:`sectionScoreCore`, so refer to the latter
            function's documentation for more information.

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
        - att.pointing (@xlink:*, @target, @targettype)
        - att.section.vis (@restart)
        - att.section.anl (att.common.anl (@copyof, @corresp, @next, @prev, @sameas, @synch)
                                          (att.alignment (@when)))

        **Contained Elements not Implemented:**

        - MEI.edittrans: gap handShift
        - MEI.shared: annot expansion
        - MEI.text: div
        - MEI.usersymbols: anchoredText curve line symbol
        '''
        environLocal.printDebug('*** processing a <section>')
        return self.sectionScoreCore(
            elem,
            allPartNs,
            nextMeasureLeft,
            backupMeasureNum
        )

    def scoreFromElement(
        self,
        elem: Element,
    ) -> stream.Score:
        '''
        <score> Full score view of the musical content.

        In MEI 2013: pg.430 (444 in PDF) (MEI.shared module)

        :param elem: The <score> element to process.
        :type elem: :class:`~xml.etree.ElementTree.Element`
        :returns: A completed :class:`~music21.stream.Score` object.

        **Attributes/Elements Implemented:**

        - contained <section>, <scoreDef>, and <staffDef>

        **Attributes Ignored:**

        **Attributes/Elements in Testing:**

        **Attributes not Implemented:**

        - att.common (@label, @n, @xml:base) (att.id (@xml:id))
        - att.declaring (@decls)
        - att.typed (@type, @subtype)
        - att.score.anl (att.common.anl (@copyof, @corresp, @next, @prev, @sameas, @synch)
                                        (att.alignment (@when)))

        **Contained Elements not Implemented:**

        - MEI.edittrans: gap handShift
        - MEI.shared: annot ending pb sb
        - MEI.text: div
        - MEI.usersymbols: anchoredText curve line symbol
        '''

        environLocal.printDebug('*** processing a <score>')

        # Get a tuple of all the @n attributes for the <staff> tags in this score. Each <staff> tag
        # corresponds to what will be a music21 Part.
        allPartNs: tuple[str, ...]
        allPartNs, self.topPartN = self.allPartsPresent(elem)

        # This is the actual processing.
        parsed: dict[str, list[Music21Object | list[Music21Object]]] = (
            # sectionScoreCore returns a dictionary containing every bit of the score,
            # and two other things to do with measure numbering.  Here in scoreFromElement,
            # we only care about the dictionary, from which we create the score, so we only
            # use sectionScoreCore(...)[0].
            self.sectionScoreCore(
                elem,
                allPartNs)[0]
        )

        # Convert the dict to a Score
        environLocal.printDebug('*** making the Score')

        wso = parsed.get('whole-score objects')
        if wso is None:
            # no parts, return empty score
            return m21.stream.Score()

        if t.TYPE_CHECKING:
            assert isinstance(wso, dict)
        wholeScoreObjects: dict[str, Music21Object] | None = wso
        parts = wholeScoreObjects['parts']
        staffGroups = wholeScoreObjects['staff-groups']

        # we create thePartList in the order of allPartNs (since that's document order),
        # NOT ordered numerically by 'n'.
        thePartList: list[m21.stream.Part] = []
        for eachN in allPartNs:
            thePartList.append(parts[eachN])
            # set "atSoundingPitch" so transposition works
            thePartList[-1].atSoundingPitch = False
            for eachObj in parsed[eachN]:
                thePartList[-1].append(eachObj)

        theScore: stream.Score = stream.Score(thePartList)

        # put the staffGroups in the score, too
        for staffGroup in staffGroups:
            theScore.insert(0, staffGroup)

        # fill in any Ottava spanners
        for sp in self.spannerBundle:
            if not isinstance(sp, spanner.Ottava):
                continue
            staffNStr: str = ''
            if hasattr(sp, 'mei_staff'):
                staffNStr = sp.mei_staff  # type: ignore
            if not staffNStr:
                # get it from start note in ottava (should already be there)
                startObj: Music21Object | None = sp.getFirst()
                if startObj is not None and hasattr(startObj, 'mei_staff'):
                    staffNStr = startObj.mei_staff  # type: ignore
            if not staffNStr:
                staffNStr = '1'  # best we can do, hope it's ok

            staffNs: list[str] = staffNStr.split(' ')
            for i, staffN in enumerate(staffNs):
                if i > 0:
                    environLocal.warn(
                        'Single Ottava in multiple staves: only filling from the first staff'
                    )
                    break
                partIdx: int = allPartNs.index(staffN)
                sp.fill(thePartList[partIdx])

        # put spanners in the Score
        for sp in self.spannerBundle:
            theScore.insert(0, sp)

        return theScore

    def initializeTagToFunctionTables(self) -> None:
        self.layerChildrenTagToFunction: dict[str, t.Callable[
            [Element],
            t.Any]
        ] = {
            f'{MEI_NS}app': self.appChoiceLayerChildrenFromElement,
            f'{MEI_NS}choice': self.appChoiceLayerChildrenFromElement,
            f'{MEI_NS}add': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}corr': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}damage': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}expan': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}orig': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}reg': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}sic': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}subst': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}supplied': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}unclear': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}clef': self.clefFromElement,
            f'{MEI_NS}chord': self.chordFromElement,
            f'{MEI_NS}note': self.noteFromElement,
            f'{MEI_NS}rest': self.restFromElement,
            f'{MEI_NS}mRest': self.mRestFromElement,
            f'{MEI_NS}beam': self.beamFromElement,
            f'{MEI_NS}tuplet': self.tupletFromElement,
            f'{MEI_NS}bTrem': self.bTremFromElement,
            f'{MEI_NS}fTrem': self.fTremFromElement,
            f'{MEI_NS}space': self.spaceFromElement,
            f'{MEI_NS}mSpace': self.mSpaceFromElement,
            f'{MEI_NS}barLine': self.barLineFromElement,
            f'{MEI_NS}meterSig': self.timeSigFromElement,
            f'{MEI_NS}keySig': self.keySigFromElementInLayer,
        }

        self.staffItemsTagToFunction: dict[str, t.Callable[
            [Element],
            t.Any]
        ] = {
            f'{MEI_NS}app': self.appChoiceStaffItemsFromElement,
            f'{MEI_NS}choice': self.appChoiceStaffItemsFromElement,
            f'{MEI_NS}add': self.passThruEditorialStaffItemsFromElement,
            f'{MEI_NS}corr': self.passThruEditorialStaffItemsFromElement,
            f'{MEI_NS}damage': self.passThruEditorialStaffItemsFromElement,
            f'{MEI_NS}expan': self.passThruEditorialStaffItemsFromElement,
            f'{MEI_NS}orig': self.passThruEditorialStaffItemsFromElement,
            f'{MEI_NS}reg': self.passThruEditorialStaffItemsFromElement,
            f'{MEI_NS}sic': self.passThruEditorialStaffItemsFromElement,
            f'{MEI_NS}subst': self.passThruEditorialStaffItemsFromElement,
            f'{MEI_NS}supplied': self.passThruEditorialStaffItemsFromElement,
            f'{MEI_NS}unclear': self.passThruEditorialStaffItemsFromElement,
            #         f'{MEI_NS}anchoredText': self.anchoredTextFromElement,
            f'{MEI_NS}arpeg': self.arpegFromElement,
            #         f'{MEI_NS}bracketSpan': self.bracketSpanFromElement,
            #         f'{MEI_NS}breath': self.breathFromElement,
            #         f'{MEI_NS}caesura': self.caesuraFromElement,
            f'{MEI_NS}dir': self.dirFromElement,
            f'{MEI_NS}dynam': self.dynamFromElement,
            f'{MEI_NS}fermata': self.fermataFromElement,
            #         f'{MEI_NS}fing': self.fingFromElement,
            #         f'{MEI_NS}gliss': self.glissFromElement,
            f'{MEI_NS}hairpin': self.hairpinFromElement,
            #         f'{MEI_NS}harm': self.harmFromElement,
            #         f'{MEI_NS}lv': self.lvFromElement,
            #        f'{MEI_NS}mNum': self.mNumFromElement,
            f'{MEI_NS}mordent': self.mordentFromElement,
            f'{MEI_NS}octave': self.octaveFromElement,
            #         f'{MEI_NS}pedal': self.pedalFromElement,
            #         f'{MEI_NS}phrase': self.phraseFromElement,
            #         f'{MEI_NS}pitchInflection': self.pitchInflectionFromElement,
            #         f'{MEI_NS}reh': self.rehFromElement,
            f'{MEI_NS}tempo': self.tempoFromElement,
            f'{MEI_NS}trill': self.trillFromElement,
            f'{MEI_NS}turn': self.turnFromElement,
        }

        self.noteChildrenTagToFunction: dict[str, t.Callable[
            [Element],
            t.Any]
        ] = {
            f'{MEI_NS}app': self.appChoiceNoteChildrenFromElement,
            f'{MEI_NS}choice': self.appChoiceNoteChildrenFromElement,
            f'{MEI_NS}add': self.passThruEditorialNoteChildrenFromElement,
            f'{MEI_NS}corr': self.passThruEditorialNoteChildrenFromElement,
            f'{MEI_NS}damage': self.passThruEditorialNoteChildrenFromElement,
            f'{MEI_NS}expan': self.passThruEditorialNoteChildrenFromElement,
            f'{MEI_NS}orig': self.passThruEditorialNoteChildrenFromElement,
            f'{MEI_NS}reg': self.passThruEditorialNoteChildrenFromElement,
            f'{MEI_NS}sic': self.passThruEditorialNoteChildrenFromElement,
            f'{MEI_NS}subst': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}supplied': self.passThruEditorialNoteChildrenFromElement,
            f'{MEI_NS}unclear': self.passThruEditorialNoteChildrenFromElement,
            f'{MEI_NS}dot': self.dotFromElement,
            f'{MEI_NS}artic': self.articFromElement,
            f'{MEI_NS}accid': self.accidFromElement,
            f'{MEI_NS}verse': self.verseFromElement,
            f'{MEI_NS}syl': self.sylFromElement
        }

        self.chordChildrenTagToFunction: dict[str, t.Callable[
            [Element],
            t.Any]
        ] = {
            f'{MEI_NS}app': self.appChoiceChordChildrenFromElement,
            f'{MEI_NS}choice': self.appChoiceChordChildrenFromElement,
            f'{MEI_NS}add': self.passThruEditorialChordChildrenFromElement,
            f'{MEI_NS}corr': self.passThruEditorialChordChildrenFromElement,
            f'{MEI_NS}damage': self.passThruEditorialChordChildrenFromElement,
            f'{MEI_NS}expan': self.passThruEditorialChordChildrenFromElement,
            f'{MEI_NS}orig': self.passThruEditorialChordChildrenFromElement,
            f'{MEI_NS}reg': self.passThruEditorialChordChildrenFromElement,
            f'{MEI_NS}sic': self.passThruEditorialChordChildrenFromElement,
            f'{MEI_NS}subst': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}supplied': self.passThruEditorialChordChildrenFromElement,
            f'{MEI_NS}unclear': self.passThruEditorialChordChildrenFromElement,
            f'{MEI_NS}note': self.noteFromElement,
            f'{MEI_NS}artic': self.articFromElement,
            f'{MEI_NS}verse': self.verseFromElement,
            f'{MEI_NS}syl': self.sylFromElement,
        }

        self.beamChildrenTagToFunction: dict[str, t.Callable[
            [Element],
            t.Any]
        ] = {
            f'{MEI_NS}app': self.appChoiceBeamChildrenFromElement,
            f'{MEI_NS}choice': self.appChoiceBeamChildrenFromElement,
            f'{MEI_NS}add': self.passThruEditorialBeamChildrenFromElement,
            f'{MEI_NS}corr': self.passThruEditorialBeamChildrenFromElement,
            f'{MEI_NS}damage': self.passThruEditorialBeamChildrenFromElement,
            f'{MEI_NS}expan': self.passThruEditorialBeamChildrenFromElement,
            f'{MEI_NS}orig': self.passThruEditorialBeamChildrenFromElement,
            f'{MEI_NS}reg': self.passThruEditorialBeamChildrenFromElement,
            f'{MEI_NS}sic': self.passThruEditorialBeamChildrenFromElement,
            f'{MEI_NS}subst': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}supplied': self.passThruEditorialBeamChildrenFromElement,
            f'{MEI_NS}unclear': self.passThruEditorialBeamChildrenFromElement,
            f'{MEI_NS}clef': self.clefFromElement,
            f'{MEI_NS}chord': self.chordFromElement,
            f'{MEI_NS}note': self.noteFromElement,
            f'{MEI_NS}rest': self.restFromElement,
            f'{MEI_NS}tuplet': self.tupletFromElement,
            f'{MEI_NS}beam': self.beamFromElement,
            f'{MEI_NS}bTrem': self.bTremFromElement,
            f'{MEI_NS}fTrem': self.fTremFromElement,
            f'{MEI_NS}space': self.spaceFromElement,
            f'{MEI_NS}barLine': self.barLineFromElement,
        }

        self.tupletChildrenTagToFunction: dict[str, t.Callable[
            [Element],
            t.Any]
        ] = {
            f'{MEI_NS}app': self.appChoiceTupletChildrenFromElement,
            f'{MEI_NS}choice': self.appChoiceTupletChildrenFromElement,
            f'{MEI_NS}add': self.passThruEditorialTupletChildrenFromElement,
            f'{MEI_NS}corr': self.passThruEditorialTupletChildrenFromElement,
            f'{MEI_NS}damage': self.passThruEditorialTupletChildrenFromElement,
            f'{MEI_NS}expan': self.passThruEditorialTupletChildrenFromElement,
            f'{MEI_NS}orig': self.passThruEditorialTupletChildrenFromElement,
            f'{MEI_NS}reg': self.passThruEditorialTupletChildrenFromElement,
            f'{MEI_NS}sic': self.passThruEditorialTupletChildrenFromElement,
            f'{MEI_NS}subst': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}supplied': self.passThruEditorialTupletChildrenFromElement,
            f'{MEI_NS}unclear': self.passThruEditorialTupletChildrenFromElement,
            f'{MEI_NS}tuplet': self.tupletFromElement,
            f'{MEI_NS}beam': self.beamFromElement,
            f'{MEI_NS}bTrem': self.bTremFromElement,
            f'{MEI_NS}fTrem': self.fTremFromElement,
            f'{MEI_NS}note': self.noteFromElement,
            f'{MEI_NS}rest': self.restFromElement,
            f'{MEI_NS}chord': self.chordFromElement,
            f'{MEI_NS}clef': self.clefFromElement,
            f'{MEI_NS}space': self.spaceFromElement,
            f'{MEI_NS}barLine': self.barLineFromElement,
        }

        self.bTremChildrenTagToFunction: dict[str, t.Callable[
            [Element],
            t.Any]
        ] = {
            f'{MEI_NS}app': self.appChoiceBTremChildrenFromElement,
            f'{MEI_NS}choice': self.appChoiceBTremChildrenFromElement,
            f'{MEI_NS}add': self.passThruEditorialBTremChildrenFromElement,
            f'{MEI_NS}corr': self.passThruEditorialBTremChildrenFromElement,
            f'{MEI_NS}damage': self.passThruEditorialBTremChildrenFromElement,
            f'{MEI_NS}expan': self.passThruEditorialBTremChildrenFromElement,
            f'{MEI_NS}orig': self.passThruEditorialBTremChildrenFromElement,
            f'{MEI_NS}reg': self.passThruEditorialBTremChildrenFromElement,
            f'{MEI_NS}sic': self.passThruEditorialBTremChildrenFromElement,
            f'{MEI_NS}subst': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}supplied': self.passThruEditorialBTremChildrenFromElement,
            f'{MEI_NS}unclear': self.passThruEditorialBTremChildrenFromElement,
            f'{MEI_NS}note': self.noteFromElement,
            f'{MEI_NS}chord': self.chordFromElement,
        }

        self.fTremChildrenTagToFunction: dict[str, t.Callable[
            [Element],
            t.Any]
        ] = {
            f'{MEI_NS}app': self.appChoiceFTremChildrenFromElement,
            f'{MEI_NS}choice': self.appChoiceFTremChildrenFromElement,
            f'{MEI_NS}add': self.passThruEditorialFTremChildrenFromElement,
            f'{MEI_NS}corr': self.passThruEditorialFTremChildrenFromElement,
            f'{MEI_NS}damage': self.passThruEditorialFTremChildrenFromElement,
            f'{MEI_NS}expan': self.passThruEditorialFTremChildrenFromElement,
            f'{MEI_NS}orig': self.passThruEditorialFTremChildrenFromElement,
            f'{MEI_NS}reg': self.passThruEditorialFTremChildrenFromElement,
            f'{MEI_NS}sic': self.passThruEditorialFTremChildrenFromElement,
            f'{MEI_NS}subst': self.passThruEditorialLayerChildrenFromElement,
            f'{MEI_NS}supplied': self.passThruEditorialFTremChildrenFromElement,
            f'{MEI_NS}unclear': self.passThruEditorialFTremChildrenFromElement,
            f'{MEI_NS}note': self.noteFromElement,
            f'{MEI_NS}chord': self.chordFromElement,
        }


# -----------------------------------------------------------------------------
_DOC_ORDER = [
    MeiReader.accidFromElement,
    MeiReader.articFromElement,
    MeiReader.beamFromElement,
    MeiReader.chordFromElement,
    MeiReader.clefFromElement,
    MeiReader.dotFromElement,
    MeiReader.instrDefFromElement,
    MeiReader.layerFromElement,
    MeiReader.measureFromElement,
    MeiReader.noteFromElement,
    MeiReader.spaceFromElement,
    MeiReader.mSpaceFromElement,
    MeiReader.restFromElement,
    MeiReader.mRestFromElement,
    MeiReader.scoreFromElement,
    MeiReader.sectionFromElement,
    MeiReader.scoreDefFromElement,
    MeiReader.staffFromElement,
    MeiReader.staffDefFromElement,
    MeiReader.staffGrpFromElement,
    MeiReader.tupletFromElement,
]

if __name__ == '__main__':
    m21.mainTest()