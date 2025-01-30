# ------------------------------------------------------------------------------
# Name:          test_meireader.py
# Purpose:       Tests for MEI parser
#
# Authors:       Greg Chapman <gregc@mac.com>
#                These tests are based on the tests by Christopher Antila in
#                https://github.com/cuthbertLab/music21
#                (music21 is Copyright 2006-2023 Michael Scott Asato Cuthbert)
#
# Copyright:     (c) 2021-2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
'''
Tests for :mod:`converter21.mei.meireader`.
'''
# part of the whole point is to test protect things too
# pylint: disable=protected-access

# this often happens on TestCase subclasses
# pylint: disable=too-many-public-methods

# if we mock many things, this may be triggered
# pylint: disable=too-many-arguments

# pylint is bad at guessing types in these tests---reasonably so
# pylint: disable=maybe-no-member

# pylint: disable=ungrouped-imports
# pylint: disable=import-error
import unittest

# To have working MagicMock objects, we can't use cElementTree even though it would be faster.
# The C implementation provides some methods/attributes dynamically (notably "tag"), so MagicMock
# won't know to mock them, and raises an exception instead.
from xml.etree import ElementTree as ETree

from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from unittest import mock  # pylint: disable=no-name-in-module

from music21 import articulations
from music21 import bar
from music21 import clef
from music21 import instrument
from music21 import interval
from music21 import key
from music21 import layout
from music21 import meter
from music21 import note
from music21 import pitch
from music21 import spanner
from music21 import stream
from music21 import tie

from converter21.mei import meiexceptions
from converter21.mei import meireader
from converter21.mei import MeiReader
from converter21.mei import MeiShared
from converter21.shared import M21Utilities

_XMLID = '{http://www.w3.org/XML/1998/namespace}id'
MEI_NS = '{http://www.music-encoding.org/ns/mei}'


class Test(unittest.TestCase):
    # class TestMeiToM21Class(unittest.TestCase):
    # '''Tests for the MeiReader class.'''

    def testInit1(self):
        '''__init__(): no argument gives an "empty" MeiReader instance'''
        actual = MeiReader()
        self.assertIsNotNone(actual.documentRoot)
        self.assertIsInstance(actual.m21Attr, defaultdict)
        self.assertIsInstance(actual.spannerBundle, spanner.SpannerBundle)

    def testInit2(self):
        '''__init__(): a valid MEI file is prepared properly'''
        inputFile = '''<?xml version="1.0" encoding="UTF-8"?>
                       <mei xmlns="http://www.music-encoding.org/ns/mei" meiversion="4.0">
                       <music><score></score></music></mei>'''
        actual = MeiReader(inputFile)
        # NB: at first I did this:
        # self.assertIsInstance(actual.documentRoot, ETree.Element)
        # ... but that doesn't work since it might be a C-Element instead
        self.assertIsNotNone(actual.documentRoot)
        self.assertEqual(f'{MEI_NS}mei', actual.documentRoot.tag)
        self.assertIsInstance(actual.m21Attr, defaultdict)
        self.assertIsInstance(actual.spannerBundle, spanner.SpannerBundle)

    def testInit3(self):
        '''__init__(): an invalid XML file causes an MeiValidityError'''
        inputFile = 'this is not an XML file'
        self.assertRaises(meiexceptions.MeiValidityError, MeiReader, inputFile)
        try:
            MeiReader(inputFile)
        except meiexceptions.MeiValidityError as theError:
            self.assertEqual(meireader._INVALID_XML_DOC, theError.args[0])

    def testInit4(self):
        '''__init__(): a MusicXML file causes an MeiElementError'''
        inputFile = '''<?xml version="1.0" encoding="UTF-8"?>
                       <!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN"
                                                       "http://www.musicxml.org/dtds/partwise.dtd">
                       <score-partwise meiversion="4.0"></score-partwise>'''
        self.assertRaises(meiexceptions.MeiElementError, MeiReader, inputFile)
        try:
            MeiReader(inputFile)
        except meiexceptions.MeiElementError as theError:
            self.assertEqual(
                meireader._WRONG_ROOT_ELEMENT.format('score-partwise'),
                theError.args[0]
            )

    # -----------------------------------------------------------------------------
    # class TestThings(unittest.TestCase):
    # '''Tests for utility functions.'''

    def testSafePitch1(self):
        '''safePitch(): when ``name`` is a valid pitch name'''
        name = 'D#6'
        expected = pitch.Pitch('D#6')
        actual = M21Utilities.safePitch(name)
        self.assertEqual(expected.name, actual.name)
        self.assertEqual(expected.accidental, actual.accidental)
        self.assertEqual(expected.octave, actual.octave)

    def testSafePitch2(self):
        '''safePitch(): when ``name`` is not a valid pitch name'''
        name = ''
        expected = pitch.Pitch()
        actual = M21Utilities.safePitch(name)
        self.assertEqual(expected.name, actual.name)
        self.assertEqual(expected.accidental, actual.accidental)
        self.assertEqual(expected.octave, actual.octave)

    def testSafePitch3(self):
        '''safePitch(): when ``name`` is not given, but there are various **keywords'''
        expected = pitch.Pitch('D#6')
        actual = M21Utilities.safePitch(name='D', accidental='#', octave='6')
        self.assertEqual(expected.name, actual.name)
        self.assertEqual(expected.accidental, actual.accidental)
        self.assertEqual(expected.octave, actual.octave)

    def testSafePitch4(self):
        '''safePitch(): when 2nd argument is None'''
        expected = pitch.Pitch('D6')
        actual = M21Utilities.safePitch(name='D', accidental=None, octave='6')
        self.assertEqual(expected.name, actual.name)
        self.assertEqual(expected.accidental, actual.accidental)
        self.assertEqual(expected.octave, actual.octave)

    def testTimeSigFromAttrs(self):
        '''_timeSigFromAttrs(): that it works (integration test)'''
        elem = ETree.Element('{mei}staffDef', attrib={'meter.count': '3', 'meter.unit': '8'})
        expectedRatioString = '3/8'
        actual = MeiReader._timeSigFromAttrs(elem, prefix='meter.')
        self.assertEqual(expectedRatioString, actual.ratioString)

    def testKeySigFromAttrs1(self):
        '''_keySigFromAttrs(): using @key.pname, @key.accid, and @key.mode (integration test)'''
        elem = ETree.Element('{mei}staffDef', attrib={'key.pname': 'B', 'key.accid': 'f',
                                                      'key.mode': 'minor'})
        expectedTPNWC = 'b-'
        c = MeiReader()
        actual = c._keySigFromAttrs(elem, prefix='key.')
        self.assertIsInstance(actual, key.Key)
        self.assertEqual(expectedTPNWC, actual.tonicPitchNameWithCase)

    def testKeySigFromAttrs2(self):
        '''_keySigFromAttrs(): using @key.sig, and @key.mode (integration test)'''
        elem = ETree.Element('{mei}staffDef', attrib={'keysig': '6s', 'key.mode': 'minor'})
        expectedSharps = 6
        expectedMode = 'minor'
        c = MeiReader()
        actual = c._keySigFromAttrs(elem, prefix='key.')
        self.assertIsInstance(actual, key.KeySignature)
        self.assertEqual(expectedSharps, actual.sharps)
        self.assertEqual(expectedMode, actual.mode)

    def testTranspositionFromAttrs1(self):
        '''_transpositionFromAttrs(): descending transposition (integration test)'''
        elem = ETree.Element('{mei}staffDef', attrib={'trans.semi': '-3', 'trans.diat': '-2'})
        expectedName = 'm-3'
        c = MeiReader()
        actual = c._transpositionFromAttrs(elem)
        self.assertIsInstance(actual, interval.Interval)
        self.assertEqual(expectedName, actual.directedName)

    def testTranspositionFromAttrs2(self):
        '''_transpositionFromAttrs(): ascending transposition (integration test)'''
        elem = ETree.Element('{mei}staffDef', attrib={'trans.semi': '7', 'trans.diat': '4'})
        expectedName = 'P5'
        c = MeiReader()
        actual = c._transpositionFromAttrs(elem)
        self.assertIsInstance(actual, interval.Interval)
        self.assertEqual(expectedName, actual.directedName)

    def testTranspositionFromAttrs3(self):
        '''_transpositionFromAttrs(): large ascending interval (integration test)'''
        elem = ETree.Element('{mei}staffDef', attrib={'trans.semi': '19', 'trans.diat': '11'})
        expectedName = 'P12'
        c = MeiReader()
        actual = c._transpositionFromAttrs(elem)
        self.assertIsInstance(actual, interval.Interval)
        self.assertEqual(expectedName, actual.directedName)

    def testTranspositionFromAttrs4(self):
        '''_transpositionFromAttrs(): alternate octave spec (integration test)'''
        elem = ETree.Element('{mei}staffDef', attrib={'trans.semi': '12', 'trans.diat': '0'})
        expectedName = 'P8'
        c = MeiReader()
        actual = c._transpositionFromAttrs(elem)
        self.assertIsInstance(actual, interval.Interval)
        self.assertEqual(expectedName, actual.directedName)

    def testTranspositionFromAttrs5(self):
        '''_transpositionFromAttrs(): alternate large descending interval (integration test)'''
        elem = ETree.Element('{mei}staffDef', attrib={'trans.semi': '-19', 'trans.diat': '-4'})
        expectedName = 'P-12'
        c = MeiReader()
        actual = c._transpositionFromAttrs(elem)
        self.assertIsInstance(actual, interval.Interval)
        self.assertEqual(expectedName, actual.directedName)

    def testTranspositionFromAttrs6(self):
        '''_transpositionFromAttrs(): alternate ascending sixteenth interval (integration test)'''
        elem = ETree.Element('{mei}staffDef', attrib={'trans.semi': '26', 'trans.diat': '1'})
        expectedName = 'M16'
        c = MeiReader()
        actual = c._transpositionFromAttrs(elem)
        self.assertIsInstance(actual, interval.Interval)
        self.assertEqual(expectedName, actual.directedName)

    def testRemoveOctothorpe1(self):
        '''removeOctothorpe(): when there's an octothorpe'''
        xmlid = '#14ccdc11-8090-49f4-b094-5935f534131a'
        expected = '14ccdc11-8090-49f4-b094-5935f534131a'
        actual = MeiShared.removeOctothorpe(xmlid)
        self.assertEqual(expected, actual)

    def testRemoveOctothorpe2(self):
        '''removeOctothorpe(): when there's not an octothorpe'''
        xmlid = 'b05c3007-bc49-4bc2-a970-bb5700cb634d'
        expected = 'b05c3007-bc49-4bc2-a970-bb5700cb634d'
        actual = MeiShared.removeOctothorpe(xmlid)
        self.assertEqual(expected, actual)

    def testAccidFromElement(self):
        '''accidFromElement(): very straight-forward test'''
        elem = ETree.Element('accid', attrib={'accid': 's'})
        c = MeiReader()
        actual = c.accidFromElement(elem)
        self.assertEqual(pitch.Accidental('#'), actual)

    # -----------------------------------------------------------------------------
    # class TestAttrTranslators(unittest.TestCase):
    # '''Tests for the one-to-one (string-to-simple-datatype) converter functions.'''

    def testAttrTranslator1(self):
        '''_attrTranslator(): the usual case works properly when "attr" is in "mapping"'''
        attr = 'two'
        name = 'numbers'
        mapping = {'one': 1, 'two': 2, 'three': 3}
        expected = 2
        c = MeiReader()
        actual = c._attrTranslator(attr, name, mapping)
        self.assertEqual(expected, actual)

    def testAttrTranslator2(self):
        '''_attrTranslator(): exception is NOT raised when "attr" isn't found'''
        attr = 'four'
        name = 'numbers'
        mapping = {'one': 1, 'two': 2, 'three': 3}
        c = MeiReader()
        try:
            c._attrTranslator(attr, name, mapping)
        except meiexceptions.MeiValueError:
            self.fail('MeiValueError incorrectly raised when attr isn\'t found')

    @mock.patch('converter21.mei.meireader.MeiReader._attrTranslator')
    def testAccidental(self, mockTrans):
        '''_accidentalFromAttr(): ensure proper arguments to _attrTranslator'''
        attr = 's'
        c = MeiReader()
        c._accidentalFromAttr(attr)
        mockTrans.assert_called_once_with(attr, 'accid', MeiReader._ACCID_ATTR_DICT)

    @mock.patch('converter21.mei.meireader.MeiReader._attrTranslator')
    def testAccidGes(self, mockTrans):
        '''_accidGesFromAttr(): ensure proper arguments to _attrTranslator'''
        attr = 's'
        c = MeiReader()
        c._accidGesFromAttr(attr)
        mockTrans.assert_called_once_with(attr, 'accid.ges', MeiReader._ACCID_GES_ATTR_DICT)

    @mock.patch('converter21.mei.meireader.MeiReader._attrTranslator')
    def testDuration(self, mockTrans):
        '''_qlDurationFromAttr(): ensure proper arguments to _attrTranslator'''
        attr = 's'
        c = MeiReader()
        c._qlDurationFromAttr(attr)
        mockTrans.assert_called_once_with(attr, 'dur', MeiReader._DUR_ATTR_DICT)

    def testOctaveShift1(self):
        '''_getOctaveShift(): properly handles positive displacement'''
        dis = '15'
        disPlace = 'above'
        expected = 2
        c = MeiReader()
        actual = c._getOctaveShift(dis, disPlace)
        self.assertEqual(expected, actual)

    def testOctaveShift2(self):
        '''_getOctaveShift(): properly handles negative displacement'''
        dis = '22'
        disPlace = 'below'
        expected = -3
        c = MeiReader()
        actual = c._getOctaveShift(dis, disPlace)
        self.assertEqual(expected, actual)

    def testOctaveShift3(self):
        '''_getOctaveShift(): properly handles positive displacement with "None"'''
        dis = '8'
        disPlace = None
        expected = 1
        c = MeiReader()
        actual = c._getOctaveShift(dis, disPlace)
        self.assertEqual(expected, actual)

    def testOctaveShift4(self):
        '''_getOctaveShift(): properly positive two "None" args'''
        dis = None
        disPlace = None
        expected = 0
        c = MeiReader()
        actual = c._getOctaveShift(dis, disPlace)
        self.assertEqual(expected, actual)

    def testBarlineFromAttr1(self):
        '''_barlineFromAttr(): rptboth'''
        right = 'rptboth'
        expected = (bar.Repeat('end', times=2), bar.Repeat('start'))
        c = MeiReader()
        actual = c._barlineFromAttr(right)
        self.assertEqual(type(expected[0]), type(actual[0]))
        self.assertEqual(type(expected[1]), type(actual[1]))

    def testBarlineFromAttr2(self):
        '''_barlineFromAttr(): rptend'''
        right = 'rptend'
        expected = bar.Repeat('end', times=2)
        c = MeiReader()
        actual = c._barlineFromAttr(right)
        self.assertEqual(type(expected), type(actual))
        self.assertEqual(expected.direction, expected.direction)
        self.assertEqual(expected.times, expected.times)

    def testBarlineFromAttr3(self):
        '''_barlineFromAttr(): rptstart'''
        right = 'rptstart'
        expected = bar.Repeat('start')
        c = MeiReader()
        actual = c._barlineFromAttr(right)
        self.assertEqual(type(expected), type(actual))
        self.assertEqual(expected.direction, expected.direction)
        self.assertEqual(expected.times, expected.times)

    def testBarlineFromAttr4(self):
        '''_barlineFromAttr(): end (--> final)'''
        right = 'end'
        expected = bar.Barline('final')
        c = MeiReader()
        actual = c._barlineFromAttr(right)
        self.assertEqual(type(expected), type(actual))
        self.assertEqual(expected.type, expected.type)

    def testTieFromAttr1(self):
        '''_tieFromAttr(): "i"'''
        right = ''
        expected = tie.Tie('start')
        c = MeiReader()
        actual = c._tieFromAttr(right)
        self.assertEqual(type(expected), type(actual))
        self.assertEqual(expected.type, expected.type)

    def testTieFromAttr2(self):
        '''_tieFromAttr(): "ti"'''
        right = ''
        expected = tie.Tie('continue')
        c = MeiReader()
        actual = c._tieFromAttr(right)
        self.assertEqual(type(expected), type(actual))
        self.assertEqual(expected.type, expected.type)

    def testTieFromAttr3(self):
        '''_tieFromAttr(): "m"'''
        right = ''
        expected = tie.Tie('continue')
        c = MeiReader()
        actual = c._tieFromAttr(right)
        self.assertEqual(type(expected), type(actual))
        self.assertEqual(expected.type, expected.type)

    def testTieFromAttr4(self):
        '''_tieFromAttr(): "t"'''
        right = ''
        expected = tie.Tie('stop')
        c = MeiReader()
        actual = c._tieFromAttr(right)
        self.assertEqual(type(expected), type(actual))
        self.assertEqual(expected.type, expected.type)

    # -----------------------------------------------------------------------------
    # class TestLyrics(unittest.TestCase):
    # '''Tests for sylFromElement() and verseFromElement()'''

    def testSyl1(self):
        '''
        sylFromElement() where @con is given and @wordpos="i"
        '''
        elem = ETree.Element('syl', attrib={'wordpos': 'i', 'con': 's'})
        elem.text = 'Chri'

        c = MeiReader()
        actual = c.sylFromElement(elem)

        self.assertIsInstance(actual, note.Lyric)
        self.assertEqual('begin', actual.syllabic)
        self.assertEqual('Chri', actual.text)  # music21 doesn't keep continuations in the text

    def testSyl2(self):
        '''
        sylFromElement() where @con is given and @wordpos="m"
        '''
        elem = ETree.Element('syl', attrib={'wordpos': 'm', 'con': 't'})
        elem.text = 'sto'

        c = MeiReader()
        actual = c.sylFromElement(elem)

        self.assertIsInstance(actual, note.Lyric)
        self.assertEqual('middle', actual.syllabic)
        self.assertEqual('sto', actual.text)  # music21 doesn't keep continuations in the text

    def testSyl3(self):
        '''
        sylFromElement() where @con is not given and @wordpos="t"
        '''
        elem = ETree.Element('syl', attrib={'wordpos': 't', 'con': 'd'})
        elem.text = 'pher'

        c = MeiReader()
        actual = c.sylFromElement(elem)

        self.assertIsInstance(actual, note.Lyric)
        self.assertEqual('end', actual.syllabic)
        self.assertEqual('pher', actual.text)  # music21 doesn't keep continuations in the text

    def testSyl4(self):
        '''
        sylFromElement() where @wordpos is not specified
        '''
        elem = ETree.Element('syl')
        elem.text = 'shoe'

        c = MeiReader()
        actual = c.sylFromElement(elem)

        self.assertIsInstance(actual, note.Lyric)
        self.assertEqual('single', actual.syllabic)
        self.assertEqual('shoe', actual.text)

    def testVerse1(self):
        '''
        verseFromElement() with one <syl> and @n given
        '''
        elem = ETree.Element('verse', attrib={'n': '42'})
        syl = ETree.Element(f'{MEI_NS}syl')
        syl.text = 'Hin-'
        elem.append(syl)

        c = MeiReader()
        actual = c.verseFromElement(elem)

        self.assertIsInstance(actual, note.Lyric)
        self.assertEqual('begin', actual.syllabic)
        self.assertEqual('Hin', actual.text)
        self.assertEqual(42, actual.number)

    def testVerse2(self):
        '''
        verseFromElement() with three <syl> and @n not given
        '''
        elem = ETree.Element('verse')
        syl = ETree.Element(f'{MEI_NS}syl')
        syl.text = 'Hin-'
        elem.append(syl)
        syl = ETree.Element(f'{MEI_NS}syl')
        syl.text = '-de-'
        elem.append(syl)
        syl = ETree.Element(f'{MEI_NS}syl')
        syl.text = '-mith'
        elem.append(syl)

        c = MeiReader()
        actual = c.verseFromElement(elem)

        self.assertEqual(3, len(actual.components))
        for eachSyl in actual.components:
            self.assertIsInstance(eachSyl, note.Lyric)
            self.assertEqual(1, eachSyl.number)
        self.assertEqual('begin', actual.components[0].syllabic)
        self.assertEqual('Hin', actual.components[0].text)
        self.assertEqual('middle', actual.components[1].syllabic)
        self.assertEqual('de', actual.components[1].text)
        self.assertEqual('end', actual.components[2].syllabic)
        self.assertEqual('mith', actual.components[2].text)

    @mock.patch('converter21.mei.meireader.environLocal')
    def testVerse3(self, mockEnviron):
        '''
        verseFromElement() with one <syl> and invalid @n
        '''
        elem = ETree.Element('verse', attrib={'n': 'mistake'})
        syl = ETree.Element(f'{MEI_NS}syl')
        syl.text = 'Hin-'
        elem.append(syl)

        c = MeiReader()
        actual = c.verseFromElement(elem)

        self.assertIsInstance(actual, note.Lyric)
        self.assertEqual('begin', actual.syllabic)
        self.assertEqual('Hin', actual.text)
        self.assertEqual(1, actual.number)
        mockEnviron.warn.assert_called_once_with(meireader._BAD_VERSE_NUMBER.format('mistake'))

    @mock.patch('converter21.mei.meireader.environLocal')
    def testVerse4(self, mockEnviron):
        '''
        verseFromElement() with one <syl> and no @n
        '''
        elem = ETree.Element('verse')
        syl = ETree.Element(f'{MEI_NS}syl')
        syl.text = 'Hin-'
        elem.append(syl)

        c = MeiReader()
        actual = c.verseFromElement(elem)

        self.assertIsInstance(actual, note.Lyric)
        self.assertEqual('begin', actual.syllabic)
        self.assertEqual('Hin', actual.text)
        self.assertEqual(1, actual.number)

    # -----------------------------------------------------------------------------
    # class TestNoteFromElement(unittest.TestCase):
    # '''Tests for noteFromElement()'''
    # NOTE: For this TestCase, in the unit tests, if you get...
    #       AttributeError: 'str' object has no attribute 'call_count'
    #       ... it means a test failure, because the str should have been a MagicMock but was
    #       replaced with a string by the unit under test.

    def testIntegration1a(self):
        '''
        noteFromElement(): all the elements that go in Note.__init__()...
                           'pname', 'accid', 'oct', 'dur', 'dots'
        (corresponds to testUnit1() with no mocks)
        '''
        elem = ETree.Element('note', attrib={'pname': 'D', 'accid': 's', 'oct': '2', 'dur': '4',
                                             'dots': '1'})
        c = MeiReader()
        actual = c.noteFromElement(elem)
        self.assertEqual('D#2', actual.nameWithOctave)
        self.assertEqual(1.5, actual.quarterLength)
        self.assertEqual(1, actual.duration.dots)

    def testIntegration1b(self):
        '''
        noteFromElement(): all the elements that go in Note.__init__()...
                           'pname', 'accid', 'oct', 'dur', 'dots'
        (this has different arguments than testIntegration1a())
        '''
        elem = ETree.Element('note', attrib={'pname': 'D', 'accid': 'n', 'oct': '2', 'dur': '4'})
        c = MeiReader()
        actual = c.noteFromElement(elem)
        self.assertEqual('D2', actual.nameWithOctave)
        self.assertEqual(1.0, actual.quarterLength)
        self.assertEqual(0, actual.duration.dots)

    def testIntegration2(self):
        '''
        noteFromElement(): adds <artic>, <accid>, and <dot> elements held within
        (corresponds to testUnit2() with no mocks)
        '''
        elem = ETree.Element('note', attrib={'pname': 'D', 'oct': '2', 'dur': '2'})
        elem.append(ETree.Element(f'{MEI_NS}dot'))
        elem.append(ETree.Element(f'{MEI_NS}artic', attrib={'artic': 'stacc'}))
        elem.append(ETree.Element(f'{MEI_NS}accid', attrib={'accid': 's'}))

        c = MeiReader()
        actual = c.noteFromElement(elem)

        self.assertEqual('D#2', actual.nameWithOctave)
        self.assertEqual(3.0, actual.quarterLength)
        self.assertEqual(1, actual.duration.dots)
        self.assertEqual(1, len(actual.articulations))
        self.assertIsInstance(actual.articulations[0], articulations.Staccato)

    def testIntegration3(self):
        '''
        noteFromElement(): adds @xml:id, @artic, and @tie attributes, and the spannerBundle
        (corresponds to testUnit3() with no mocks)
        '''
        elem = ETree.Element('note', attrib={'pname': 'D', 'accid.ges': 's', 'oct': '2', 'dur': '4',
                                             'dots': '1', _XMLID: 'asdf1234', 'artic': 'stacc',
                                             'tie': 'i1'})

        c = MeiReader()
        actual = c.noteFromElement(elem)

        self.assertEqual('D#2', actual.nameWithOctave)
        self.assertEqual(False, actual.pitch.accidental.displayStatus)  # because @accid.ges
        self.assertEqual(1.5, actual.quarterLength)
        self.assertEqual(1, actual.duration.dots)
        self.assertEqual('asdf1234', actual.id)
        self.assertEqual(1, len(actual.articulations))
        self.assertIsInstance(actual.articulations[0], articulations.Staccato)
        self.assertEqual(tie.Tie('start'), actual.tie)

    def testIntegration4(self):
        '''
        noteFromElement(): @m21TupletNum
        (corresponds to testUnit4() with no mocks)
        '''
        elem = ETree.Element('note', attrib={'pname': 'D', 'oct': '2', 'dur': '4',
                                             'm21TupletNum': '5', 'm21TupletNumbase': '4',
                                             'm21TupletSearch': 'start',
                                             'accid': 's', 'm21Beam': 'start'})

        c = MeiReader()
        actual = c.noteFromElement(elem)

        self.assertEqual('D#2', actual.nameWithOctave)
        self.assertEqual(True, actual.pitch.accidental.displayStatus)  # because @accid
        self.assertEqual(1.0, actual.quarterLength)
        self.assertEqual('quarter', actual.duration.type)
        self.assertEqual('5', actual.m21TupletNum)
        self.assertEqual('4', actual.m21TupletNumbase)
        self.assertEqual('start', actual.m21TupletSearch)

    def testIntegration5(self):
        '''
        noteFromElement(): test @grace and @m21Beam where the duration requires adjusting beams,
            and contained <syl>
        (corresponds to testUnit5() with no mocks)
        '''
        elem = ETree.Element('note', attrib={'pname': 'D', 'oct': '2', 'dur': '16',
                                             'm21Beam': 'start', 'grace': 'acc'})
        sylElem = ETree.Element(f'{MEI_NS}syl')
        sylElem.text = 'words!'
        elem.append(sylElem)

        c = MeiReader()
        actual = c.noteFromElement(elem)

        self.assertEqual('D2', actual.nameWithOctave)
        self.assertEqual(0.0, actual.quarterLength)
        self.assertEqual('16th', actual.duration.type)
        self.assertEqual(1, actual.beams.beamsList[0].number)
        self.assertEqual('start', actual.beams.beamsList[0].type)
        self.assertEqual(2, actual.beams.beamsList[1].number)
        self.assertEqual('start', actual.beams.beamsList[1].type)
        self.assertEqual(1, len(actual.lyrics))
        self.assertEqual('words!', actual.lyrics[0].text)

    def testIntegration6(self):
        '''
        noteFromElement(): test contained <verse>
        (corresponds to testUnit6() with no mocks)
        '''
        elem = '''<note pname="D" oct="2" dur="16" xmlns="http://www.music-encoding.org/ns/mei">
            <verse n="1">
                <syl>au</syl>
                <syl>luong</syl>
            </verse>
            <verse n="2">
                <syl>sun</syl>
            </verse>
        </note>
        '''
        elem = ETree.fromstring(elem)

        c = MeiReader()
        actual = c.noteFromElement(elem)

        self.assertEqual(2, len(actual.lyrics))
        self.assertEqual(1, actual.lyrics[0].number)
        self.assertEqual(2, actual.lyrics[1].number)
        self.assertEqual('au', actual.lyrics[0].components[0].text)
        self.assertEqual('luong', actual.lyrics[0].components[1].text)
        self.assertEqual('sun', actual.lyrics[1].text)

    # NOTE: consider adding to previous tests rather than making new ones

    # -----------------------------------------------------------------------------
    # class TestRestFromElement(unittest.TestCase):
    # '''Tests for restFromElement() and spaceFromElement()'''

    def testIntegration1(self):
        '''
        restFromElement(): test @dur, @dots, @xml:id, and tuplet-related attributes

        (without mock objects)
        '''
        elem = ETree.Element('rest', attrib={'dur': '4', 'dots': '1', _XMLID: 'the id',
                                             'm21TupletNum': '5', 'm21TupletNumbase': '4',
                                             'm21TupletType': 'start'})

        c = MeiReader()
        actual = c.restFromElement(elem)

        self.assertEqual(Fraction(6, 5), actual.quarterLength)
        self.assertEqual(1, actual.duration.dots)
        self.assertEqual('the id', actual.id)
        self.assertEqual('start', actual.duration.tuplets[0].type)

    def testUnit2TestRestFromElement(self):
        '''
        spaceFromElement(): test @dur, @dots, @xml:id, and tuplet-related attributes
        '''
        elem = ETree.Element('rest', attrib={'dur': '4',
                                             'dots': '1',
                                             _XMLID: 'the id',
                                             'm21TupletNum': '5',
                                             'm21TupletNumbase': '4',
                                             'm21TupletType': 'start',
                                             })
        c = MeiReader()
        actual = c.spaceFromElement(elem)
        self.assertIsInstance(actual, note.Rest)
        self.assertTrue(actual.style.hideObjectOnPrint)
        self.assertEqual('the id', actual.id)

    def testIntegration2TestRestFromElement(self):
        '''
        spaceFromElement(): test @dur, @dots, @xml:id, and tuplet-related attributes

        (without mock objects)
        '''
        elem = ETree.Element('space', attrib={'dur': '4', 'dots': '1', _XMLID: 'the id',
                                              'm21TupletNum': '5', 'm21TupletNumbase': '4',
                                              'm21TupletType': 'start'})

        c = MeiReader()
        actual = c.spaceFromElement(elem)

        self.assertEqual(Fraction(6, 5), actual.quarterLength)
        self.assertEqual(1, actual.duration.dots)
        self.assertEqual('the id', actual.id)
        self.assertEqual('start', actual.duration.tuplets[0].type)

    @mock.patch('converter21.mei.meireader.MeiReader.restFromElement')
    def testUnit3TestRestFromElement(self, mockRestFromElement):
        '''
        mRestFromElement(): reacts properly to an Element with the @dur attribute
        '''
        elem = ETree.Element('mRest', attrib={'dur': '2'})
        mockRestFromElement.return_value = 'the rest'

        c = MeiReader()
        actual = c.mRestFromElement(elem)

        self.assertEqual(mockRestFromElement.return_value, actual)
        mockRestFromElement.assert_called_once_with(elem)

    @mock.patch('converter21.mei.meireader.MeiReader.spaceFromElement')
    def testUnit5TestRestFromElement(self, mockSpace):
        '''
        mSpaceFromElement(): reacts properly to an Element with the @dur attribute
        '''
        elem = ETree.Element('mSpace', attrib={'dur': '2'})
        mockSpace.return_value = 'the spacer'

        c = MeiReader()
        actual = c.mSpaceFromElement(elem)

        self.assertEqual(mockSpace.return_value, actual)
        mockSpace.assert_called_once_with(elem)

    # -----------------------------------------------------------------------------
    # class TestChordFromElement(unittest.TestCase):
    # '''Tests for chordFromElement()'''
    # NOTE: For this TestCase, in the unit tests, if you get...
    #       AttributeError: 'str' object has no attribute 'call_count'
    #       ... it means a test failure, because the str should have been a MagicMock but was
    #       replaced with a string by the unit under test.

    @staticmethod
    def makeNoteElemsChordFromElement(pname, accid, octArg, dur, dots):
        '''Factory function for the Element objects that are a <note>.'''
        return ETree.Element(f'{MEI_NS}note', pname=pname, accid=accid,
                             oct=octArg, dur=dur, dots=dots)

    def testIntegration1ChordFromElement(self):
        '''
        chordFromElement(): all the basic attributes (i.e., @pname, @accid, @oct, @dur, @dots)

        (corresponds to testUnit1() with no mocks)
        '''
        elem = ETree.Element('chord', attrib={'dur': '4', 'dots': '1'})
        noteElements = [Test.makeNoteElemsChordFromElement(x, 'n', '4', '8', '0')
                        for x in ('c', 'e', 'g')]
        for eachElement in noteElements:
            elem.append(eachElement)
        expectedName = ('Chord {C-natural in octave 4 | E-natural in octave 4 | '
                        + 'G-natural in octave 4} Dotted Quarter')
        c = MeiReader()
        actual = c.chordFromElement(elem)
        self.assertEqual(expectedName, actual.fullName)

    def testIntegration2ChordFromElement(self):
        '''
        noteFromElement(): adds <artic>, <accid>, and <dot> elements held within

        (corresponds to testUnit2() with no mocks)
        '''
        elem = ETree.Element('chord', attrib={'dur': '4', 'dots': '1'})
        noteElements = [Test.makeNoteElemsChordFromElement(x, 'n', '4', '8', '0')
                        for x in ('c', 'e', 'g')]
        for eachElement in noteElements:
            elem.append(eachElement)
        elem.append(ETree.Element(f'{MEI_NS}artic', artic='stacc'))
        expectedName = ('Chord {C-natural in octave 4 | E-natural in octave 4 | '
                        + 'G-natural in octave 4} Dotted Quarter')
        c = MeiReader()
        actual = c.chordFromElement(elem)
        self.assertEqual(expectedName, actual.fullName)
        self.assertEqual(1, len(actual.articulations))
        self.assertIsInstance(actual.articulations[0], articulations.Staccato)

    def testIntegration3ChordFromElement(self):
        '''
        noteFromElement(): adds @xml:id, @artic, and @tie attributes, and the spannerBundle

        (corresponds to testUnit3() with no mocks)
        '''
        elem = ETree.Element('chord', attrib={'dur': '4', 'dots': '1', 'artic': 'stacc',
                                              _XMLID: 'asdf1234', 'tie': 'i1'})
        noteElements = [Test.makeNoteElemsChordFromElement(x, 'n', '4', '8', '0')
                        for x in ('c', 'e', 'g')]
        for eachElement in noteElements:
            elem.append(eachElement)

        nextElem = ETree.Element('chord', attrib={'dur': '4', 'dots': '1', 'artic': 'stacc',
                                              _XMLID: 'asdf1235', 'tie': 't1'})
        nextNoteElements = [Test.makeNoteElemsChordFromElement(x, 'n', '4', '8', '0')
                            for x in ('c', 'e', 'g')]
        for eachElement in nextNoteElements:
            nextElem.append(eachElement)

        expectedName = ('Chord {C-natural in octave 4 | E-natural in octave 4 | '
                        + 'G-natural in octave 4} Dotted Quarter')
        c = MeiReader()
        actual = c.chordFromElement(elem)
        c.chordFromElement(nextElem)  # necessary to finish off the ties in actual
        self.assertEqual(expectedName, actual.fullName)
        self.assertEqual(1, len(actual.articulations))
        self.assertIsInstance(actual.articulations[0], articulations.Staccato)
        self.assertEqual('asdf1234', actual.id)
        for n in actual.notes:
            self.assertEqual(tie.Tie('start'), n.tie)

    def testIntegration4ChordFromElement(self):
        '''
        noteFromElement(): adds tuplet-related attributes

        (corresponds to testUnit4() with no mocks)
        '''
        elem = ETree.Element('chord', attrib={'dur': '4', 'm21TupletNum': '5',
                                              'm21TupletNumbase': '4',
                                              'm21TupletSearch': 'start', 'm21Beam': 'start'})
        noteElements = [Test.makeNoteElemsChordFromElement(x, 'n', '4', '8', '0')
                        for x in ('c', 'e', 'g')]
        for eachElement in noteElements:
            elem.append(eachElement)
        expectedName = ('Chord {C-natural in octave 4 | E-natural in octave 4 | '
                        + 'G-natural in octave 4} Quarter')

        c = MeiReader()
        actual = c.chordFromElement(elem)

        self.assertEqual(expectedName, actual.fullName)
        self.assertEqual('5', actual.m21TupletNum)
        self.assertEqual('4', actual.m21TupletNumbase)
        self.assertEqual('start', actual.m21TupletSearch)

    def testIntegration5ChordFromElement(self):
        '''
        noteFromElement(): @grace and @m21Beam when the duration does require adjusting the beams

        (corresponds to testUnit5() with no mocks)
        '''
        elem = ETree.Element('chord', attrib={'dur': '16', 'm21Beam': 'start', 'grace': 'acc'})
        noteElements = [Test.makeNoteElemsChordFromElement(x, 'n', '4', '8', '0')
                        for x in ('c', 'e', 'g')]
        for eachElement in noteElements:
            elem.append(eachElement)
        expectedName = ('Chord {C-natural in octave 4 | E-natural in octave 4 | '
                        + 'G-natural in octave 4} 16th')

        c = MeiReader()
        actual = c.chordFromElement(elem)

        self.assertEqual(expectedName, actual.fullName)
        self.assertEqual(0.0, actual.quarterLength)
        self.assertEqual('16th', actual.duration.type)
        self.assertEqual(1, actual.beams.beamsList[0].number)
        self.assertEqual('start', actual.beams.beamsList[0].type)
        self.assertEqual(2, actual.beams.beamsList[1].number)
        self.assertEqual('start', actual.beams.beamsList[1].type)

    # NOTE: consider adding to previous tests rather than making new ones

    # -----------------------------------------------------------------------------
    # class TestClefFromElement(unittest.TestCase):
    # '''Tests for _clefFromElement()'''
    # NOTE: in this function's integration tests, the Element.tag attribute doesn't actually matter

    def testIntegration1aClefFromElement(self):
        '''
        _clefFromElement(): all the elements that go in clef.clefFromString()...
                           'shape', 'line', 'dis', and 'dis.place'
        (corresponds to testUnit1a, with real objects)
        '''
        clefElem = ETree.Element('clef')
        clefAttribs = {'shape': 'G', 'line': '2', 'dis': '8', 'dis.place': 'above'}
        for eachKey in clefAttribs:
            clefElem.set(eachKey, clefAttribs[eachKey])
        expectedClass = clef.Treble8vaClef

        c = MeiReader()
        actual = c._clefFromElement(clefElem)

        self.assertEqual(expectedClass, actual.__class__)

    def testIntegration1bClefFromElement(self):
        '''
        PercussionClef

        (corresponds to testUnit1b, with real objects)
        '''
        clefElem = ETree.Element('clef')
        clefAttribs = {'shape': 'perc'}
        for eachKey in clefAttribs:
            clefElem.set(eachKey, clefAttribs[eachKey])
        expectedClass = clef.PercussionClef

        c = MeiReader()
        actual = c._clefFromElement(clefElem)

        self.assertEqual(expectedClass, actual.__class__)

    def testIntegration1cClefFromElement(self):
        '''
        TabClef

        (corresponds to testUnit1c, with real objects)
        '''
        clefElem = ETree.Element('clef')
        clefAttribs = {'shape': 'TAB'}
        for eachKey in clefAttribs:
            clefElem.set(eachKey, clefAttribs[eachKey])
        expectedClass = clef.TabClef

        c = MeiReader()
        actual = c._clefFromElement(clefElem)

        self.assertEqual(expectedClass, actual.__class__)

    # -----------------------------------------------------------------------------
    # class TestLayerFromElement(unittest.TestCase):
    # '''Tests for layerFromElement()'''

    def testIntegration1aLayerFromElement(self):
        '''
        layerFromElement(): basic functionality (i.e., that the tag-name-to-converter-function
                            mapping works; that tags not in the mapping are ignored; and that a
                            Voice object is returned. And "xml:id" is set.
        (corresponds to testUnit1a() but without mock objects)
        '''
        inputXML = '''<layer n="so voice ID" xmlns="http://www.music-encoding.org/ns/mei">
                          <note pname="F" oct="2" dur="4" />
                          <note pname="E" oct="2" accid="f" dur="4" />
                          <imaginary awesome="true" />
                      </layer>'''
        elem = ETree.fromstring(inputXML)

        c = MeiReader()
        actual = c.layerFromElement(elem, '1')

        self.assertEqual(2, len(actual))
        self.assertEqual('so voice ID', actual.id)
        self.assertEqual(0.0, actual[0].offset)
        self.assertEqual(1.0, actual[1].offset)
        self.assertEqual(1.0, actual[0].quarterLength)
        self.assertEqual(1.0, actual[1].quarterLength)
        self.assertEqual('F2', actual[0].nameWithOctave)
        self.assertEqual('E-2', actual[1].nameWithOctave)

    def testIntegration1bLayerFromElement(self):
        '''
        (corresponds to testUnit1b() but without mock objects)
        '''
        inputXML = '''<layer xmlns="http://www.music-encoding.org/ns/mei">
                          <note pname="F" oct="2" dur="4" />
                          <note pname="E" oct="2" accid="f" dur="4" />
                          <imaginary awesome="true" />
                      </layer>'''
        elem = ETree.fromstring(inputXML)

        c = MeiReader()
        actual = c.layerFromElement(elem, overrideN='so voice ID')

        self.assertEqual(2, len(actual))
        self.assertEqual('so voice ID', actual.id)
        self.assertEqual(0.0, actual[0].offset)
        self.assertEqual(1.0, actual[1].offset)
        self.assertEqual(1.0, actual[0].quarterLength)
        self.assertEqual(1.0, actual[1].quarterLength)
        self.assertEqual('F2', actual[0].nameWithOctave)
        self.assertEqual('E-2', actual[1].nameWithOctave)

    def testIntegration1cLayerFromElement(self):
        '''
        (corresponds to testUnit1c() but without mock objects)
        '''
        inputXML = '''<layer xmlns="http://www.music-encoding.org/ns/mei">
                          <note pname="F" oct="2" dur="4" />
                          <note pname="E" oct="2" accid="f" dur="4" />
                          <imaginary awesome="true" />
                      </layer>'''
        elem = ETree.fromstring(inputXML)

        c = MeiReader()
        self.assertRaises(meiexceptions.MeiAttributeError, c.layerFromElement, elem, '')

        try:
            c.layerFromElement(elem, '')
        except meiexceptions.MeiAttributeError as maError:
            self.assertEqual(meireader._MISSING_VOICE_ID, maError.args[0])

    # -----------------------------------------------------------------------------
    # class TestStaffFromElement(unittest.TestCase):
    # '''Tests for staffFromElement()'''

    def testIntegration1StaffFromElement(self):
        '''
        staffFromElement(): basic functionality (i.e., that layerFromElement() is called with the
                            right arguments, and with properly-incrementing "id" attributes
        (corresponds to testUnit1() but without mock objects)
        '''
        inputXML = '''<staff xmlns="http://www.music-encoding.org/ns/mei">
                          <layer>
                              <note pname="F" oct="2" dur="4" />
                          </layer>
                          <layer>
                              <note pname="A" oct="2" dur="4" />
                          </layer>
                          <layer>
                              <note pname="C" oct="2" dur="4" />
                          </layer>
                      </staff>'''
        elem = ETree.fromstring(inputXML)

        c = MeiReader()
        actual = c.staffFromElement(elem)

        self.assertEqual(3, len(actual))
        # common to each part
        for i in range(len(actual)):
            self.assertEqual(1, len(actual[i]))
            self.assertEqual(0.0, actual[i][0].offset)
            self.assertEqual(1.0, actual[i][0].quarterLength)
        # first part
        self.assertEqual('1', actual[0].id)
        self.assertEqual('F2', actual[0][0].nameWithOctave)
        # second part
        self.assertEqual('2', actual[1].id)
        self.assertEqual('A2', actual[1][0].nameWithOctave)
        # third part
        self.assertEqual('3', actual[2].id)
        self.assertEqual('C2', actual[2][0].nameWithOctave)

    # -----------------------------------------------------------------------------
    # class TestStaffDefFromElement(unittest.TestCase):
    # '''Tests for staffDefFromElement()'''

    # noinspection SpellCheckingInspection
    @mock.patch('converter21.mei.meireader.MeiReader.instrDefFromElement')
    @mock.patch('converter21.mei.meireader.MeiReader._timeSigFromAttrs')
    @mock.patch('converter21.mei.meireader.MeiReader._keySigFromAttrs')
    @mock.patch('converter21.mei.meireader.MeiReader._clefFromElement')
    @mock.patch('converter21.mei.meireader.MeiReader._transpositionFromAttrs')
    def testUnit1StaffFromElementStaffDefFromElement(self, mockTrans,
                                                     mockClef, mockKey, mockTime, mockInstr):
        '''
        staffDefFromElement(): proper handling of the following attributes (see function docstring
            for more information).

        @label, @label.abbr  @n, @key.accid, @key.mode, @key.pname, @key.sig, @meter.count,
        @meter.unit, @clef.shape, @clef.line, @clef.dis, @clef.dis.place, @trans.diat, @trans.demi
        '''
        # 1.) prepare
        elem = ETree.Element(f'{MEI_NS}staffDef',
                             attrib={'clef.shape': 'F', 'clef.line': '4', 'clef.dis': 'cd',
                                     'clef.dis.place': 'cdp', 'label': 'the label',
                                     'label.abbr': 'the l.', 'n': '1', 'meter.count': '1',
                                     'key.pname': 'G', 'trans.semi': '123'})
        theInstrDef = ETree.Element(f'{MEI_NS}instrDef',
                                    attrib={'midi.channel': '1', 'midi.instrnum': '71',
                                            'midi.instrname': 'Clarinet'})
        elem.append(theInstrDef)
        theMockInstrument = mock.MagicMock('mock instrument')
        mockInstr.return_value = theMockInstrument
        mockTime.return_value = 'mockTime return'
        mockKey.return_value = 'mockKey return'
        mockClef.return_value = 'mockClef return'
        mockTrans.return_value = 'mockTrans return'
        expected = {'instrument': mockInstr.return_value,
                    'meter': mockTime.return_value,
                    'key': mockKey.return_value,
                    'clef': mockClef.return_value}
        # attributes on theMockInstrument that should be set by staffDefFromElement()
        expectedAttrs = [('partName', 'the label'),
                         ('partAbbreviation', 'the l.'),
                         ('partId', '1'),
                         ('transposition', mockTrans.return_value)]

        # 2.) run
        c = MeiReader()
        actual = c.staffDefFromElement(elem)

        # 3.) check
        self.assertDictEqual(expected, actual)
        mockInstr.assert_called_once_with(theInstrDef)
        mockTime.assert_called_once_with(elem, prefix='meter.')
        mockKey.assert_called_once_with(elem, prefix='key.')
        # mockClef is more difficult because it's given an Element
        mockTrans.assert_called_once_with(elem)
        # check that all attributes are set with their expected values
        for attrName, attrValue in expectedAttrs:
            self.assertEqual(getattr(theMockInstrument, attrName), attrValue)
        # now mockClef, which got an Element
        mockClef.assert_called_once_with(mock.ANY)
        mockClefArg = mockClef.call_args_list[0][0][0]
        self.assertEqual('clef', mockClefArg.tag)
        self.assertEqual('F', mockClefArg.get('shape'))
        self.assertEqual('4', mockClefArg.get('line'))
        self.assertEqual('cd', mockClefArg.get('dis'))
        self.assertEqual('cdp', mockClefArg.get('dis.place'))

    # noinspection SpellCheckingInspection
    def testIntegration1aStaffFromElement(self):
        '''
        staffDefFromElement(): corresponds to testUnit1() without mock objects
        '''
        # 1.) prepare
        elem = ETree.Element(f'{MEI_NS}staffDef',
                             attrib={'clef.shape': 'G', 'clef.line': '2', 'n': '12',
                                     'meter.count': '3', 'meter.unit': '8', 'keysig': '0',
                                     'key.mode': 'major', 'trans.semi': '-3', 'trans.diat': '-2'})
        theInstrDef = ETree.Element(f'{MEI_NS}instrDef',
                                    attrib={'midi.channel': '1', 'midi.instrnum': '71',
                                            'midi.instrname': 'Clarinet'})
        elem.append(theInstrDef)

        # 2.) run
        c = MeiReader()
        actual = c.staffDefFromElement(elem)

        # 3.) check
        self.assertIsInstance(actual['instrument'], instrument.Clarinet)
        self.assertIsInstance(actual['meter'], meter.TimeSignature)
        self.assertIsInstance(actual['key'], key.KeySignature)
        self.assertIsInstance(actual['clef'], clef.TrebleClef)
        self.assertEqual('12', actual['instrument'].partId)
        self.assertEqual('3/8', actual['meter'].ratioString)
        self.assertEqual('major', actual['key'].mode)
        self.assertEqual(0, actual['key'].sharps)

    # noinspection SpellCheckingInspection
    def testIntegration1bStaffFromElement(self):
        '''
        staffDefFromElement(): testIntegration1() with <clef> tag inside
        '''
        # 1.) prepare
        elem = ETree.Element(f'{MEI_NS}staffDef',
                             attrib={'n': '12', 'meter.count': '3', 'meter.unit': '8',
                                     'keysig': '0',
                                     'key.mode': 'major', 'trans.semi': '-3', 'trans.diat': '-2'})
        theInstrDef = ETree.Element(f'{MEI_NS}instrDef',
                                    attrib={'midi.channel': '1', 'midi.instrnum': '71',
                                            'midi.instrname': 'Clarinet'})
        elem.append(theInstrDef)
        elem.append(ETree.Element(f'{MEI_NS}clef', attrib={'shape': 'G', 'line': '2'}))

        # 2.) run
        c = MeiReader()
        actual = c.staffDefFromElement(elem)

        # 3.) check
        self.assertIsInstance(actual['instrument'], instrument.Clarinet)
        self.assertIsInstance(actual['meter'], meter.TimeSignature)
        self.assertIsInstance(actual['key'], key.KeySignature)
        self.assertIsInstance(actual['clef'], clef.TrebleClef)
        self.assertEqual('12', actual['instrument'].partId)
        self.assertEqual('3/8', actual['meter'].ratioString)
        self.assertEqual('major', actual['key'].mode)
        self.assertEqual(0, actual['key'].sharps)

    @mock.patch('music21.instrument.fromString')
    @mock.patch('converter21.mei.meireader.MeiReader.instrDefFromElement')
    @mock.patch('converter21.mei.meireader.MeiReader._timeSigFromAttrs')
    @mock.patch('converter21.mei.meireader.MeiReader._keySigFromAttrs')
    @mock.patch('converter21.mei.meireader.MeiReader._clefFromElement')
    @mock.patch('converter21.mei.meireader.MeiReader._transpositionFromAttrs')
    def testUnit2StaffFromElement(self, mockTrans, mockClef,
                                  mockKey, mockTime, mockInstr, mockFromString):
        '''
        staffDefFromElement(): same as testUnit1() *but* there's no <instrDef> so we have to use
            music21.instrument.fromString()
        '''
        # NB: differences from testUnit1() are marked with a "D1" comment at the end of the line
        # 1.) prepare
        elem = ETree.Element(f'{MEI_NS}staffDef',
                             attrib={'clef.shape': 'F', 'clef.line': '4', 'clef.dis': 'cd',
                                     'clef.dis.place': 'cdp', 'label': 'the label',
                                     'label.abbr': 'the l.', 'n': '1', 'meter.count': '1',
                                     'key.pname': 'G', 'trans.semi': '123'})
        theMockInstrument = mock.MagicMock('mock instrument')
        mockFromString.return_value = theMockInstrument  # D1
        mockTime.return_value = 'mockTime return'
        mockKey.return_value = 'mockKey return'
        mockClef.return_value = 'mockClef return'
        mockTrans.return_value = 'mockTrans return'
        expected = {'instrument': mockFromString.return_value,  # D1
                    'meter': mockTime.return_value,
                    'key': mockKey.return_value,
                    'clef': mockClef.return_value}
        # attributes on theMockInstrument that should be set by staffDefFromElement()
        expectedAttrs = [('partName', 'the label'),
                         ('partAbbreviation', 'the l.'),
                         ('partId', '1'),
                         ('transposition', mockTrans.return_value)]

        # 2.) run
        c = MeiReader()
        actual = c.staffDefFromElement(elem)

        # 3.) check
        self.assertDictEqual(expected, actual)
        self.assertEqual(0, mockInstr.call_count)  # D1
        mockTime.assert_called_once_with(elem, prefix='meter.')
        mockKey.assert_called_once_with(elem, prefix='key.')
        # mockClef is more difficult because it's given an Element
        mockTrans.assert_called_once_with(elem)
        # check that all attributes are set with their expected values
        for attrName, attrValue in expectedAttrs:
            self.assertEqual(getattr(theMockInstrument, attrName), attrValue)
        # now mockClef, which got an Element
        mockClef.assert_called_once_with(mock.ANY)
        mockClefArg = mockClef.call_args_list[0][0][0]
        self.assertEqual('clef', mockClefArg.tag)
        self.assertEqual('F', mockClefArg.get('shape'))
        self.assertEqual('4', mockClefArg.get('line'))
        self.assertEqual('cd', mockClefArg.get('dis'))
        self.assertEqual('cdp', mockClefArg.get('dis.place'))

    def testIntegration2StaffFromElement(self):
        '''
        staffDefFromElement(): corresponds to testUnit2() but without mock objects
        '''
        # 1.) prepare
        elem = ETree.Element(f'{MEI_NS}staffDef',
                             attrib={'n': '12', 'clef.line': '2', 'clef.shape': 'G',
                                     'keysig': '0',
                                     'key.mode': 'major', 'trans.semi': '-3', 'trans.diat': '-2',
                                     'meter.count': '3', 'meter.unit': '8', 'label': 'clarinet'})

        # 2.) run
        c = MeiReader()
        actual = c.staffDefFromElement(elem)

        # 3.) check
        self.assertIsInstance(actual['instrument'], instrument.Clarinet)
        self.assertIsInstance(actual['meter'], meter.TimeSignature)
        self.assertIsInstance(actual['key'], key.KeySignature)
        self.assertIsInstance(actual['clef'], clef.TrebleClef)
        self.assertEqual('12', actual['instrument'].partId)
        self.assertEqual('3/8', actual['meter'].ratioString)
        self.assertEqual('major', actual['key'].mode)
        self.assertEqual(0, actual['key'].sharps)

    @mock.patch('music21.instrument.Instrument')
    @mock.patch('music21.instrument.fromString')
    @mock.patch('converter21.mei.meireader.MeiReader.instrDefFromElement')
    @mock.patch('converter21.mei.meireader.MeiReader._timeSigFromAttrs')
    @mock.patch('converter21.mei.meireader.MeiReader._keySigFromAttrs')
    @mock.patch('converter21.mei.meireader.MeiReader._clefFromElement')
    @mock.patch('converter21.mei.meireader.MeiReader._transpositionFromAttrs')
    def testUnit3StaffFromElement(self, mockTrans, mockClef, mockKey, mockTime,
                                  mockInstr, mockFromString, mockInstrInit):
        '''
        staffDefFromElement(): same as testUnit1() *but* there's no <instrDef> so we have to use
          music21.instrument.fromString() *and* that raises an InstrumentException.
        '''
        # NB: differences from testUnit1() are marked with a "D1" comment at the end of the line
        # NB: differences from testUnit2() are marked with a "D2" comment at the end of the line
        # 1.) prepare
        elem = ETree.Element(f'{MEI_NS}staffDef',
                             attrib={'clef.shape': 'F', 'clef.line': '4', 'clef.dis': 'cd',
                                     'clef.dis.place': 'cdp', 'label': 'the label',
                                     'label.abbr': 'the l.', 'n': '1', 'meter.count': '1',
                                     'key.pname': 'G', 'trans.semi': '123'})
        theMockInstrument = mock.MagicMock('mock instrument')
        mockFromString.side_effect = instrument.InstrumentException  # D2
        mockInstrInit.return_value = theMockInstrument  # D1 & D2
        mockTime.return_value = 'mockTime return'
        mockKey.return_value = 'mockKey return'
        mockClef.return_value = 'mockClef return'
        mockTrans.return_value = 'mockTrans return'
        expected = {'instrument': mockInstrInit.return_value,  # D1 & D2
                    'meter': mockTime.return_value,
                    'key': mockKey.return_value,
                    'clef': mockClef.return_value}
        # attributes on theMockInstrument that should be set by staffDefFromElement()
        # NB: because the part name wasn't recognized by music21, there won't be a part name on the
        #     Instrument... the only reason we get an Instrument at all is because of @trans.semi
        expectedAttrs = [('transposition', mockTrans.return_value)]  # D3

        # 2.) run
        c = MeiReader()
        actual = c.staffDefFromElement(elem)

        # 3.) check
        self.assertDictEqual(expected, actual)
        self.assertEqual(0, mockInstr.call_count)  # D1
        mockTime.assert_called_once_with(elem, prefix='meter.')
        mockKey.assert_called_once_with(elem, prefix='key.')
        # mockClef is more difficult because it's given an Element
        mockTrans.assert_called_once_with(elem)
        # check that all attributes are set with their expected values
        for attrName, attrValue in expectedAttrs:
            self.assertEqual(getattr(theMockInstrument, attrName), attrValue)
        # now mockClef, which got an Element
        mockClef.assert_called_once_with(mock.ANY)
        mockClefArg = mockClef.call_args_list[0][0][0]
        self.assertEqual('clef', mockClefArg.tag)
        self.assertEqual('F', mockClefArg.get('shape'))
        self.assertEqual('4', mockClefArg.get('line'))
        self.assertEqual('cd', mockClefArg.get('dis'))
        self.assertEqual('cdp', mockClefArg.get('dis.place'))

    def testIntegration3StaffFromElement(self):
        '''
        staffDefFromElement(): corresponds to testUnit3() but without mock objects
        '''
        # 1.) prepare
        elem = ETree.Element(f'{MEI_NS}staffDef',
                             attrib={'n': '12', 'clef.line': '2', 'clef.shape': 'G',
                                     'keysig': '0',
                                     'key.mode': 'major', 'trans.semi': '-3', 'trans.diat': '-2',
                                     'meter.count': '3', 'meter.unit': '8'})

        # 2.) run
        c = MeiReader()
        actual = c.staffDefFromElement(elem)

        # 3.) check
        self.assertIsInstance(actual['instrument'], instrument.Instrument)
        self.assertIsInstance(actual['meter'], meter.TimeSignature)
        self.assertIsInstance(actual['key'], key.KeySignature)
        self.assertIsInstance(actual['clef'], clef.TrebleClef)
        self.assertEqual('3/8', actual['meter'].ratioString)
        self.assertEqual('major', actual['key'].mode)
        self.assertEqual(0, actual['key'].sharps)
        self.assertEqual('m-3', actual['instrument'].transposition.directedName)

    @mock.patch('music21.instrument.Instrument')
    @mock.patch('music21.instrument.fromString')
    @mock.patch('converter21.mei.meireader.MeiReader.instrDefFromElement')
    @mock.patch('converter21.mei.meireader.MeiReader._timeSigFromAttrs')
    @mock.patch('converter21.mei.meireader.MeiReader._keySigFromAttrs')
    @mock.patch('converter21.mei.meireader.MeiReader._clefFromElement')
    @mock.patch('converter21.mei.meireader.MeiReader._transpositionFromAttrs')
    def testUnit4StaffFromElement(self, mockTrans, mockClef, mockKey, mockTime,
                                  mockInstr, mockFromString, mockInstrInit):
        '''
        staffDefFromElement(): only specifies a meter
        '''
        # 1.) prepare
        elem = ETree.Element(f'{MEI_NS}staffDef', attrib={'meter.count': '1',
                                                                  'meter.unit': '3'})
        mockTime.return_value = 'mockTime return'
        mockFromString.side_effect = instrument.InstrumentException
        # otherwise staffDefFromElement() thinks it got a real Instrument
        expected = {'meter': mockTime.return_value}

        # 2.) run
        c = MeiReader()
        actual = c.staffDefFromElement(elem)

        # 3.) check
        self.assertDictEqual(expected, actual)

    def testIntegration4StaffFromElement(self):
        '''
        staffDefFromElement(): corresponds to testUnit3() but without mock objects
        '''
        # 1.) prepare
        elem = ETree.Element(f'{MEI_NS}staffDef', attrib={'meter.count': '1',
                                                                  'meter.unit': '3'})

        # 2.) run
        c = MeiReader()
        actual = c.staffDefFromElement(elem)

        # 3.) check
        self.assertIsInstance(actual['meter'], meter.TimeSignature)
        self.assertEqual('1/3', actual['meter'].ratioString)

    @mock.patch('converter21.mei.meireader.MeiReader.staffDefFromElement')
    def testStaffGrpUnit1StaffFromElement(self, mockStaffDefFE):
        '''
        staffGrpFromElement(): it's not a very complicated function!
        '''
        elem = ETree.Element('staffGrp')
        innerElems = [ETree.Element(f'{MEI_NS}staffDef', attrib={'n': str(n)})
                                                                    for n in range(4)]
        for eachElem in innerElems:
            elem.append(eachElem)
        mockStaffDefFE.side_effect = lambda x: f"processed {x.get('n')}"
        expected = {str(n): f'processed {n}' for n in range(4)}

        c = MeiReader()
        actual = c.staffGrpFromElement(elem)

        self.assertEqual(expected, actual)
        self.assertEqual(len(innerElems), mockStaffDefFE.call_count)
        for eachElem in innerElems:
            mockStaffDefFE.assert_any_call(eachElem)

    def testStaffGrpInt1StaffFromElement(self):
        '''
        staffGrpFromElement(): with <staffDef> directly inside this <staffGrp>
        '''
        elem = ETree.Element('staffGrp')
        innerElems = [ETree.Element(f'{MEI_NS}staffDef',
                                    attrib={'n': str(n + 1), 'key.mode': 'major',
                                            'keysig': f'{n + 1}f'})
                      for n in range(4)]
        for eachElem in innerElems:
            elem.append(eachElem)
        expected = {'1': {'key': key.Key('F')},
                    '2': {'key': key.Key('B-')},
                    '3': {'key': key.Key('E-')},
                    '4': {'key': key.Key('A-')}}

        c = MeiReader()
        actual = c.staffGrpFromElement(elem)

        self.assertDictEqual(expected, actual)

    def testStaffGrpInt2StaffFromElement(self):
        '''
        staffGrpFromElement(): with <staffDef> embedded in another <staffGrp>
        '''
        elem = ETree.Element('staffGrp')
        innerElems = [ETree.Element(f'{MEI_NS}staffDef',
                                    attrib={'n': str(n + 1), 'key.mode': 'major',
                                            'keysig': f'{n + 1}f'})
                      for n in range(4)]
        innerGrp = ETree.Element(f'{MEI_NS}staffGrp')
        for eachElem in innerElems:
            innerGrp.append(eachElem)
        elem.append(innerGrp)
        expected = {'1': {'key': key.Key('F')},
                    '2': {'key': key.Key('B-')},
                    '3': {'key': key.Key('E-')},
                    '4': {'key': key.Key('A-')}}

        c = MeiReader()
        actual = c.staffGrpFromElement(elem)

        self.assertDictEqual(expected, actual)

    # -----------------------------------------------------------------------------
    # class TestScoreDefFromElement(unittest.TestCase):
    # '''Tests for scoreDefFromElement()'''

    @mock.patch('converter21.mei.meireader.MeiReader._timeSigFromAttrs')
    @mock.patch('converter21.mei.meireader.MeiReader._keySigFromAttrs')
    def testUnit1ScoreDefFromElement(self, mockKey, mockTime):
        '''
        scoreDefFromElement(): proper handling of the following attributes (see function docstring
            for more information).

        @meter.count, @meter.unit, @key.accid, @key.mode, @key.pname, @key.sig
        '''
        # 1.) prepare
        elem = ETree.Element('staffDef', attrib={'keysig': '4s', 'key.mode': 'major',
                                                 'meter.count': '3', 'meter.unit': '8'})
        mockTime.return_value = 'mockTime return'
        mockKey.return_value = 'mockKey return'
        expected = {'top-part objects': [],
                    'all-part objects': [mockTime.return_value, mockKey.return_value],
                    'whole-score objects': {}}

        # 2.) run
        c = MeiReader()
        actual = c.scoreDefFromElement(elem, [])

        # 3.) check
        self.assertEqual(expected, actual)
        mockTime.assert_called_once_with(elem, prefix='meter.')
        mockKey.assert_called_once_with(elem, prefix='key.')

    def testIntegration1ScoreDefFromElement(self):
        '''
        scoreDefFromElement(): corresponds to testUnit1() without mock objects
        '''
        # 1.) prepare
        elem = ETree.Element('staffDef', attrib={'keysig': '4s', 'key.mode': 'major',
                                                 'meter.count': '3', 'meter.unit': '8'})

        # 2.) run
        c = MeiReader()
        actual = c.scoreDefFromElement(elem, [])

        # 3.) check
        self.assertIsInstance(actual['all-part objects'][0], meter.TimeSignature)
        self.assertIsInstance(actual['all-part objects'][1], key.KeySignature)
        self.assertEqual('3/8', actual['all-part objects'][0].ratioString)
        self.assertEqual('major', actual['all-part objects'][1].mode)
        self.assertEqual(4, actual['all-part objects'][1].sharps)

    def testIntegration2ScoreDefFromElement(self):
        '''
        scoreDefFromElement(): corresponds to testUnit2() without mock objects
        '''
        # 1.) prepare
        elem = ETree.Element('staffDef', attrib={'keysig': '4s', 'key.mode': 'major',
                                                 'meter.count': '3', 'meter.unit': '8'})
        staffGrp = ETree.Element(f'{MEI_NS}staffGrp')
        staffDef = ETree.Element(f'{MEI_NS}staffDef',
                                 attrib={'n': '1', 'label': 'Clarinet'})
        staffGrp.append(staffDef)
        elem.append(staffGrp)

        # 2.) run
        c = MeiReader()
        actual = c.scoreDefFromElement(elem, ['1'])

        # 3.) check
        self.assertIsInstance(actual['all-part objects'][0], meter.TimeSignature)
        self.assertIsInstance(actual['all-part objects'][1], key.KeySignature)
        self.assertEqual('3/8', actual['all-part objects'][0].ratioString)
        self.assertEqual('major', actual['all-part objects'][1].mode)
        self.assertEqual(4, actual['all-part objects'][1].sharps)
        self.assertEqual('1', actual['1']['instrument'].partId)
        self.assertEqual('Clarinet', actual['1']['instrument'].partName)
        self.assertIsInstance(actual['1']['instrument'], instrument.Clarinet)
        self.assertEqual(1, len(actual['whole-score objects']['parts']))
        self.assertIsInstance(actual['whole-score objects']['parts']['1'], stream.Part)
        self.assertTrue(
            not isinstance(
                actual['whole-score objects']['parts']['1'],
                stream.PartStaff)
        )
        self.assertEqual(1, len(actual['whole-score objects']['staff-groups']))
        self.assertIsInstance(
            actual['whole-score objects']['staff-groups'][0],
            layout.StaffGroup
        )
        self.assertIs(
            actual['whole-score objects']['staff-groups'][0].getFirst(),
            actual['whole-score objects']['parts']['1']
        )


        # -----------------------------------------------------------------------------
    # class TestEmbeddedElements(unittest.TestCase):
    # '''Tests for _processesEmbeddedElements()'''

    def testUnit1EmbeddedElements(self):
        '''
        _processesEmbeddedElements(): that single m21 objects are handled properly
        '''
        mockTranslator = mock.MagicMock(return_value='translator return')
        elements = [ETree.Element('note') for _ in range(2)]
        mapping = {'note': mockTranslator}
        expected = ['translator return', 'translator return']
        expectedCalls = [
            mock.call(elements[0]),
            mock.call(elements[1])
        ]

        c = MeiReader()
        actual = c._processEmbeddedElements(elements, mapping, 'tag')

        self.assertSequenceEqual(expected, actual)
        self.assertSequenceEqual(expectedCalls, mockTranslator.call_args_list)

    def testUnit2EmbeddedElements(self):
        '''
        _processesEmbeddedElements(): that iterables of m21 objects are handled properly
        '''
        mockTranslator = mock.MagicMock(return_value='translator return')
        mockBeamTranslator = mock.MagicMock(return_value=['embedded 1', 'embedded 2'])
        elements = [ETree.Element('note'), ETree.Element('beam')]
        mapping = {'note': mockTranslator, 'beam': mockBeamTranslator}
        expected = ['translator return', 'embedded 1', 'embedded 2']

        c = MeiReader()
        actual = c._processEmbeddedElements(elements, mapping, 'tag')

        self.assertSequenceEqual(expected, actual)
        mockTranslator.assert_called_once_with(elements[0])
        mockBeamTranslator.assert_called_once_with(elements[1])

    @mock.patch('converter21.mei.meireader.environLocal')
    def testUnit3EmbeddedElements(self, mockEnviron):
        '''
        _processesEmbeddedElements(): that un-translated elements are reported properly
        '''
        mockTranslator = mock.MagicMock(return_value='translator return')
        elements = [ETree.Element('note'), ETree.Element('bream')]
        mapping = {'note': mockTranslator}
        callerName = 'ocean'
        expected = ['translator return']
        expErr = meireader._UNPROCESSED_SUBELEMENT.format(elements[1].tag, callerName)

        c = MeiReader()
        actual = c._processEmbeddedElements(elements, mapping, callerName)

        self.assertSequenceEqual(expected, actual)
        mockTranslator.assert_called_once_with(elements[0])
        mockEnviron.warn.assert_called_once_with(expErr)


# -----------------------------------------------------------------------------
# class TestAddSlurs(unittest.TestCase):
    '''Tests for addSlurs()'''

    def testUnit1AddSlurs(self):
        '''
        addSlurs(): element with @m21SlurStart is handled correctly
        '''
        theUUID = 'ae0b1570-451f-4ee9-a136-2094e26a797b'
        elem = ETree.Element('note', attrib={'m21SlurStart': theUUID,
                                             'm21SlurEnd': None,
                                             'slur': None})
        spannerBundle = mock.MagicMock('slur bundle')
        mockNewSlur = mock.MagicMock('mock slur')
        mockNewSlur.addSpannedElements = mock.MagicMock()
        spannerBundle.getByIdLocal = mock.MagicMock(return_value=[mockNewSlur])
        obj = mock.MagicMock('object')

        c = MeiReader()
        c.spannerBundle = spannerBundle
        c.addSlurs(elem, obj)
        spannerBundle.getByIdLocal.assert_called_once_with(theUUID)
        mockNewSlur.addSpannedElements.assert_called_once_with(obj)

    def testIntegration1AddSlurs(self):
        '''
        addSlurs(): element with @m21SlurStart is handled correctly
        '''
        theUUID = 'ae0b1570-451f-4ee9-a136-2094e26a797b'
        elem = ETree.Element('note', attrib={'m21SlurStart': theUUID,
                                             'm21SlurEnd': None,
                                             'slur': None})
        spannerBundle = spanner.SpannerBundle()
        theSlur = spanner.Slur()
        theSlur.idLocal = theUUID
        spannerBundle.append(theSlur)
        obj = note.Note('E-7', quarterLength=2.0)

        c = MeiReader()
        c.spannerBundle = spannerBundle
        c.addSlurs(elem, obj)
        self.assertSequenceEqual([theSlur], list(spannerBundle))
        self.assertSequenceEqual([obj], list(spannerBundle)[0].getSpannedElements())

    def testUnit2AddSlurs(self):
        '''
        addSlurs(): element with @m21SlurEnd is handled correctly
        '''
        theUUID = 'ae0b1570-451f-4ee9-a136-2094e26a797b'
        elem = ETree.Element('note', attrib={'m21SlurStart': None,
                                             'm21SlurEnd': theUUID,
                                             'slur': None})
        spannerBundle = mock.MagicMock('slur bundle')
        mockNewSlur = mock.MagicMock('mock slur')
        mockNewSlur.addSpannedElements = mock.MagicMock()
        spannerBundle.getByIdLocal = mock.MagicMock(return_value=[mockNewSlur])
        obj = mock.MagicMock('object')

        c = MeiReader()
        c.spannerBundle = spannerBundle
        c.addSlurs(elem, obj)
        spannerBundle.getByIdLocal.assert_called_once_with(theUUID)
        mockNewSlur.addSpannedElements.assert_called_once_with(obj)

    # NB: skipping testIntegration2() ... if Integration1 and Unit2 work, this probably does too

    def testIntegration3AddSlurs(self):
        '''
        addSlurs(): element with @slur is handled correctly (both an 'i' and 't' slur)
        '''
        elem = ETree.Element('note', attrib={'m21SlurStart': None,
                                             'm21SlurEnd': None,
                                             'slur': 'i1 t2'})
        spannerBundle = spanner.SpannerBundle()
        theSlur = spanner.Slur()
        theSlur.idLocal = '2'
        spannerBundle.append(theSlur)
        obj = note.Note('E-7', quarterLength=2.0)

        c = MeiReader()
        c.spannerBundle = spannerBundle
        c.addSlurs(elem, obj)
        self.assertSequenceEqual([theSlur, mock.ANY], list(spannerBundle))
        self.assertIsInstance(list(spannerBundle)[1], spanner.Slur)
        self.assertSequenceEqual([obj], list(spannerBundle)[0].getSpannedElements())
        self.assertSequenceEqual([obj], list(spannerBundle)[1].getSpannedElements())

    def testIntegration6AddSlurs(self):
        '''
        addSlurs(): nothing was added; when the Slur with id of @m21SlurStart can't be found

        NB: this tests that the inner function works---catching the IndexError
        '''
        elem = ETree.Element('note',
                             attrib={'m21SlurStart': '07f5513a-436a-4247-8a5d-85c10c661920',
                                     'm21SlurEnd': None,
                                     'slur': None})
        obj = note.Note('E-7', quarterLength=2.0)

        c = MeiReader()
        c.addSlurs(elem, obj)
        self.assertSequenceEqual([], list(c.spannerBundle))

# -----------------------------------------------------------------------------
# class TestTuplets(unittest.TestCase):
    '''Tests for the tuplet-processing helper function, scaleToTuplet().'''

    # noinspection SpellCheckingInspection
    def testTuplets1(self):
        '''
        scaleToTuplet(): with three objects, the "tuplet search" attributes are set properly.
        '''
        objs = [note.Note() for _ in range(3)]
        elem = ETree.Element('tupletDef',
                             attrib={'m21TupletNum': '12',
                                     'm21TupletNumbase': '400',
                                     'm21TupletSearch': 'the forest'})

        c = MeiReader()
        c.scaleToTuplet(objs, elem)

        for obj in objs:
            self.assertEqual('12', obj.m21TupletNum)
            self.assertEqual('400', obj.m21TupletNumbase)
            self.assertEqual('the forest', obj.m21TupletSearch)

    def testTuplet10(self):
        '''
        _guessTuplets(): given a list of stuff without tuplet-guessing attributes, make no changes
        '''
        theLayer = [note.Note(quarterLength=1.0) for _ in range(5)]
        expectedDurs = [1.0 for _ in range(5)]

        c = MeiReader()
        c._guessTuplets(theLayer)  # pylint: disable=protected-access

        for i in range(len(expectedDurs)):
            self.assertEqual(expectedDurs[i], theLayer[i].quarterLength)

    def testTuplet11a(self):
        '''
        _guessTuplets(): with 5 notes, a triplet at the beginning is done correctly
        '''
        theLayer = [note.Note(quarterLength=1.0) for _ in range(5)]
        theLayer[0].m21TupletSearch = 'start'
        theLayer[0].m21TupletNum = '3'
        theLayer[0].m21TupletNumbase = '2'
        theLayer[2].m21TupletSearch = 'end'
        theLayer[2].m21TupletNum = '3'
        theLayer[2].m21TupletNumbase = '2'
        expectedDurs = [Fraction(2, 3), Fraction(2, 3), Fraction(2, 3), 1.0, 1.0]

        c = MeiReader()
        c._guessTuplets(theLayer)  # pylint: disable=protected-access

        for i in range(len(expectedDurs)):
            self.assertEqual(expectedDurs[i], theLayer[i].quarterLength)
        for i in [0, 2]:
            self.assertFalse(hasattr(theLayer[i], 'm21TupletSearch'))
            self.assertFalse(hasattr(theLayer[i], 'm21TupletNum'))
            self.assertFalse(hasattr(theLayer[i], 'm21TupletNumbase'))

    def testTuplet11b(self):
        '''
        _guessTuplets(): with 5 notes, a triplet in the middle is done correctly
        '''
        theLayer = [note.Note(quarterLength=1.0) for _ in range(5)]
        theLayer[1].m21TupletSearch = 'start'
        theLayer[1].m21TupletNum = '3'
        theLayer[1].m21TupletNumbase = '2'
        theLayer[3].m21TupletSearch = 'end'
        theLayer[3].m21TupletNum = '3'
        theLayer[3].m21TupletNumbase = '2'
        expectedDurs = [1.0, Fraction(2, 3), Fraction(2, 3), Fraction(2, 3), 1.0]

        c = MeiReader()
        c._guessTuplets(theLayer)  # pylint: disable=protected-access

        for i in range(len(expectedDurs)):
            self.assertEqual(expectedDurs[i], theLayer[i].quarterLength)
        for i in [1, 3]:
            self.assertFalse(hasattr(theLayer[i], 'm21TupletSearch'))
            self.assertFalse(hasattr(theLayer[i], 'm21TupletNum'))
            self.assertFalse(hasattr(theLayer[i], 'm21TupletNumbase'))

    def testTuplet11c(self):
        '''
        _guessTuplets(): with 5 notes, a triplet at the end is done correctly
        '''
        theLayer = [note.Note(quarterLength=1.0) for _ in range(5)]
        theLayer[2].m21TupletSearch = 'start'
        theLayer[2].m21TupletNum = '3'
        theLayer[2].m21TupletNumbase = '2'
        theLayer[4].m21TupletSearch = 'end'
        theLayer[4].m21TupletNum = '3'
        theLayer[4].m21TupletNumbase = '2'
        expectedDurs = [1.0, 1.0, Fraction(2, 3), Fraction(2, 3), Fraction(2, 3)]

        c = MeiReader()
        c._guessTuplets(theLayer)  # pylint: disable=protected-access

        for i in range(len(expectedDurs)):
            self.assertEqual(expectedDurs[i], theLayer[i].quarterLength)
        for i in [2, 4]:
            self.assertFalse(hasattr(theLayer[i], 'm21TupletSearch'))
            self.assertFalse(hasattr(theLayer[i], 'm21TupletNum'))
            self.assertFalse(hasattr(theLayer[i], 'm21TupletNumbase'))


# -----------------------------------------------------------------------------
# class TestInstrDef(unittest.TestCase):
    '''Tests for instrDefFromElement().'''

    @mock.patch('music21.instrument.instrumentFromMidiProgram')
    def testUnit1InstrDef(self, mockFromProg):
        '''instrDefFromElement(): when @midi.instrnum is given'''
        elem = ETree.Element('instrDef', attrib={'midi.instrnum': '71'})
        expFromProgArg = 71
        mockFromProg.return_value = 'Guess Which Instrument'
        expected = mockFromProg.return_value

        c = MeiReader()
        actual = c.instrDefFromElement(elem)

        self.assertEqual(expected, actual)
        mockFromProg.assert_called_once_with(expFromProgArg)

    @mock.patch('music21.instrument.fromString')
    def testUnit2InstrDef(self, mockFromString):
        '''instrDefFromElement(): when @midi.instrname is given, and it works'''
        elem = ETree.Element('instrDef', attrib={'midi.instrname': 'Tuba'})
        expFromStringArg = 'Tuba'
        mockFromString.return_value = "That's right: tuba"
        expected = mockFromString.return_value

        c = MeiReader()
        actual = c.instrDefFromElement(elem)

        self.assertEqual(expected, actual)
        mockFromString.assert_called_once_with(expFromStringArg)

# -----------------------------------------------------------------------------
# class TestMeasureFromElement(unittest.TestCase):
    '''Tests for measureFromElement() and its helper functions.'''

    def testMakeBarline1(self):
        '''
        _makeBarlines(): when @left and @right are None, you only get default
        right Barline, no left Barline
        '''
        elem = ETree.Element('measure')
        staves = {'1': stream.Measure(), '2': stream.Measure(), '3': stream.Measure(), '4': 4}

        c = MeiReader()
        staves = c._makeBarlines(elem, staves)

        for i in ('1', '2', '3'):
            self.assertIsNone(staves[i].leftBarline)
            self.assertEqual(staves[i].rightBarline.type, 'regular')
        self.assertEqual(4, staves['4'])

    def testMakeBarline2(self):
        '''
        _makeBarlines(): when @left and @right are a simple barline, that barline is assigned
        '''
        elem = ETree.Element('measure', attrib={'left': 'dbl', 'right': 'dbl'})
        staves = {'1': stream.Measure(), '2': stream.Measure(), '3': stream.Measure(), '4': 4}

        c = MeiReader()
        staves = c._makeBarlines(elem, staves)

        for i in ('1', '2', '3'):
            self.assertIsInstance(staves[i].leftBarline, bar.Barline)
            self.assertEqual('double', staves[i].leftBarline.type)
            self.assertIsInstance(staves[i].rightBarline, bar.Barline)
            self.assertEqual('double', staves[i].rightBarline.type)
        self.assertEqual(4, staves['4'])

    def testMakeBarline3(self):
        '''
        _makeBarlines(): when @left and @right are "rptboth," that's done properly
        '''
        elem = ETree.Element('measure', attrib={'left': 'rptboth', 'right': 'rptboth'})
        staves = {'1': stream.Measure(), '2': stream.Measure(), '3': stream.Measure(), '4': 4}

        c = MeiReader()
        staves = c._makeBarlines(elem, staves)

        for i in ('1', '2', '3'):
            self.assertIsInstance(staves[i].leftBarline, bar.Repeat)
            self.assertEqual('heavy-light', staves[i].leftBarline.type)
            self.assertIsInstance(staves[i].rightBarline, bar.Repeat)
            self.assertEqual('final', staves[i].rightBarline.type)
        self.assertEqual(4, staves['4'])

    def testCorrectMRestDurs1(self):
        '''
        _correctMRestDurs(): nothing happens when there isn't at object with "m21wasMRest"

        This is an integration test of sorts, using no Mock objects.
        '''
        staves = {'1': stream.Measure([stream.Voice([note.Rest(), note.Rest()])]),
                  '2': stream.Measure([stream.Voice([note.Rest(), note.Rest()])])}
        c = MeiReader()
        c._correctMRestDurs(staves, 2.0)
        self.assertEqual(1.0, staves['1'].voices[0][0].quarterLength)
        self.assertEqual(1.0, staves['1'].voices[0][1].quarterLength)
        self.assertEqual(1.0, staves['2'].voices[0][0].quarterLength)
        self.assertEqual(1.0, staves['2'].voices[0][1].quarterLength)

    def testCorrectMRestDurs2(self):
        '''
        _correctMRestDurs(): things with "m21wasMRest" are adjusted properly

        This is an integration test of sorts, using no Mock objects.
        '''
        staves = {'1': stream.Measure([stream.Voice([note.Rest()])]),
                  '2': stream.Measure([stream.Voice([note.Rest(), note.Rest()])])}
        staves['1'][0][0].m21wasMRest = True
        c = MeiReader()
        c._correctMRestDurs(staves, 2.0)
        self.assertEqual(2.0, staves['1'].voices[0][0].quarterLength)
        self.assertEqual(1.0, staves['2'].voices[0][0].quarterLength)
        self.assertEqual(1.0, staves['2'].voices[0][1].quarterLength)
        self.assertFalse(hasattr(staves['1'].voices[0][0], 'm21wasMRest'))

    def testCorrectMRestDurs3(self):
        '''
        _correctMRestDurs(): works with more than 1 voice per part,
        and for things that aren't Voice

        This is an integration test of sorts, using no Mock objects.
        '''
        staves = {'1': stream.Measure([stream.Voice([note.Rest()]), stream.Voice([note.Rest()])]),
                  '2': stream.Measure([meter.TimeSignature('4/4'), stream.Voice([note.Note()])])}
        staves['1'][0][0].m21wasMRest = True
        staves['1'][1][0].m21wasMRest = True
        c = MeiReader()
        c._correctMRestDurs(staves, 2.0)
        self.assertEqual(2.0, staves['1'].voices[0][0].quarterLength)
        self.assertEqual(2.0, staves['1'].voices[1][0].quarterLength)
        self.assertEqual(1.0, staves['2'].voices[0][0].quarterLength)
        self.assertFalse(hasattr(staves['1'][0][0], 'm21wasMRest'))
        self.assertFalse(hasattr(staves['1'][1][0], 'm21wasMRest'))

    def testMeasureIntegration1(self):
        '''
        measureFromElement(): test 1
            - "elem" has an @n attribute
            - some staves have <mRest> without @dur (same behaviour to as if no staves did)
            - a rest-filled measure is created for the "n" value in "expectedNs" that's missing a
              corresponding <staff> element, and its Measure has the same @n as "elem"
            - activeMeter isn't None, and it is larger than the (internal) maxBarDuration
            - the right barline is set properly ("dbl")

        no mocks
        '''
        staffTag = f'{MEI_NS}staff'
        layerTag = f'{MEI_NS}layer'
        noteTag = f'{MEI_NS}note'
        elem = ETree.Element('measure', attrib={'n': '42', 'right': 'dbl'})
        innerStaffs = [ETree.Element(staffTag, attrib={'n': str(n + 1)}) for n in range(3)]
        for i, eachStaff in enumerate(innerStaffs):
            thisLayer = ETree.Element(layerTag, attrib={'n': '1'})
            thisLayer.append(ETree.Element(noteTag,
                                           attrib={'pname': 'G', 'oct': str(i + 1), 'dur': '1'}))
            eachStaff.append(thisLayer)
            elem.append(eachStaff)
        # @n="4" is in "expectedNs" but we're leaving it out as part of the test
        expectedNs = ['1', '2', '3', '4']
        activeMeter = meter.TimeSignature('8/8')  # bet you thought this would be 4/4, eh?

        c = MeiReader()
        c.activeMeter = activeMeter
        actual = c.measureFromElement(
            elem, expectedNs
        )

        # ensure the right number and @n of parts
        self.assertEqual(4, len(actual.keys()))
        for eachN in expectedNs:
            self.assertTrue(eachN in actual)
        # ensure the measure number is set properly,
        #        there is one voice with one note with its octave set equal to the staff's @n,
        #        the right barline was set properly
        for eachN in ['1', '2', '3']:
            self.assertEqual(42, actual[eachN].number)
            self.assertEqual(2, len(actual[eachN]))  # first the Note, then the Barline
            self.assertIsInstance(actual[eachN][0], stream.Voice)
            self.assertEqual(1, len(actual[eachN][0]))
            self.assertIsInstance(actual[eachN][0][0], note.Note)
            self.assertEqual(int(eachN), actual[eachN][0][0].pitch.octave)
            self.assertIsInstance(actual[eachN].rightBarline, bar.Barline)
            self.assertEqual('double', actual[eachN].rightBarline.type)
        # ensure voice '4' with Rest of proper duration, right measure number, and right barline
        self.assertEqual(42, actual['4'].number)
        self.assertEqual(2, len(actual['4']))  # first the Rest, then the Barline
        self.assertIsInstance(actual['4'][0], stream.Voice)
        self.assertEqual(1, len(actual['4'][0]))
        self.assertIsInstance(actual['4'][0][0], note.Rest)
        self.assertEqual(c.activeMeter.barDuration.quarterLength,
                         actual['4'][0][0].duration.quarterLength)
        self.assertIsInstance(actual[eachN].rightBarline, bar.Barline)
        self.assertEqual('double', actual[eachN].rightBarline.type)

    def testMeasureIntegration2(self):
        '''
        measureFromElement(): test 2
            - "elem" doesn't have an @n attribute
            - all staves have <mRest> without @dur (and only 3 of the 4 are specified at all)
            - a rest-filled measure is created for the "n" value in "expectedNs" that's missing a
              corresponding <staff> element
            - the right barline is set properly ("rptboth")

        no mocks
        '''
        staffTag = f'{MEI_NS}staff'
        layerTag = f'{MEI_NS}layer'
        mRestTag = f'{MEI_NS}mRest'
        elem = ETree.Element('measure', attrib={'right': 'rptboth'})
        innerStaffs = [ETree.Element(staffTag, attrib={'n': str(n + 1)}) for n in range(3)]
        for eachStaff in innerStaffs:
            thisLayer = ETree.Element(layerTag, attrib={'n': '1'})
            thisLayer.append(ETree.Element(mRestTag))
            eachStaff.append(thisLayer)
            elem.append(eachStaff)
        # @n="4" is in "expectedNs" but we're leaving it out as part of the test
        expectedNs = ['1', '2', '3', '4']
        activeMeter = meter.TimeSignature('8/8')  # bet you thought this would be 4/4, eh?

        c = MeiReader()
        c.activeMeter = activeMeter
        actual = c.measureFromElement(
            elem, expectedNs
        )

        # ensure the right number and @n of parts (we expect one additional key, for the "rptboth")
        self.assertEqual(5, len(actual.keys()))
        for eachN in expectedNs:
            self.assertTrue(eachN in actual)
        self.assertTrue('next @left' in actual)
        # ensure the measure number is set properly,
        #        there is one voice with one note with its octave set equal to the staff's @n,
        #        the right barline was set properly
        # (Note we can test all four parts together this time---
        #     the fourth should be indistinguishable)
        for eachN in expectedNs:
            self.assertEqual(2, len(actual[eachN]))  # first the Note, then the Barline
            self.assertIsInstance(actual[eachN][0], stream.Voice)
            self.assertEqual(1, len(actual[eachN][0]))
            self.assertIsInstance(actual[eachN][0][0], note.Rest)
            self.assertEqual(c.activeMeter.barDuration.quarterLength,
                             actual['4'][0][0].duration.quarterLength)
            self.assertIsInstance(actual[eachN].rightBarline, bar.Repeat)
            self.assertEqual('final', actual[eachN].rightBarline.type)

    def testMeasureIntegration3(self):
        '''
        measureFromElement(): test 3
            - there is one part
            - there is a <staffDef> which has its required @n attribute

        NB: I won't bother making an integration equivalent to unit test 3b, since I would have to
            mock "environLocal" to know whether it worked, and "no mocks" is the whole point of this

        no mocks
        '''
        staffTag = f'{MEI_NS}staff'
        layerTag = f'{MEI_NS}layer'
        noteTag = f'{MEI_NS}note'
        staffDefTag = f'{MEI_NS}staffDef'
        elem = ETree.Element('measure')
        elem.append(ETree.Element(staffDefTag, attrib={'n': '1', 'lines': '5',
                                                       'clef.line': '4', 'clef.shape': 'F'}))
        innerStaff = ETree.Element(staffTag, attrib={'n': '1'})
        innerLayer = ETree.Element(layerTag, attrib={'n': '1'})
        innerLayer.append(ETree.Element(noteTag))
        innerStaff.append(innerLayer)
        elem.append(innerStaff)
        expectedNs = ['1']
        activeMeter = meter.TimeSignature('8/8')  # bet you thought this would be 4/4, eh?

        c = MeiReader()
        c.activeMeter = activeMeter
        actual = c.measureFromElement(
            elem, expectedNs
        )

        # ensure the right number and @n of parts
        self.assertEqual(['1'], list(actual.keys()))
        # ensure the Measure has its expected Voice, BassClef, and right Barline
        self.assertEqual(3, len(actual['1']))
        # the Voice, and a Clef and Instrument from staffDefFE()
        foundVoice = False
        foundClef = False
        foundBarline = False
        for item in actual['1']:
            if isinstance(item, stream.Voice):
                foundVoice = True
            elif isinstance(item, clef.BassClef):
                foundClef = True
            elif isinstance(item, bar.Barline) and item is actual['1'].rightBarline:
                foundBarline = True
        self.assertTrue(foundVoice)
        self.assertTrue(foundClef)
        self.assertTrue(foundBarline)


# -----------------------------------------------------------------------------
# class TestSectionScore(unittest.TestCase):
    '''Tests for scoreFromElement(), sectionFromElement(), and
    their helper function sectionScoreCore().'''

    @mock.patch('converter21.mei.meireader.MeiReader.sectionScoreCore')
    def testSection1(self, mockCore):
        '''
        Mock sectionScoreCore(). This is very straight-forward.
        '''
        mockCore.return_value = 5
        elem = ETree.Element('section')
        allPartNs = ['1', '2', '3']
        activeMeter = meter.TimeSignature('12/8')
        nextMeasureLeft = bar.Repeat()
        expected = mockCore.return_value

        c = MeiReader()
        c.activeMeter = activeMeter
        actual = c.sectionFromElement(elem, allPartNs, nextMeasureLeft)

        self.assertEqual(expected, actual)
        mockCore.assert_called_once_with(elem,
                                         allPartNs,
                                         nextMeasureLeft)

    def testScoreIntegration1(self):
        '''
        scoreFromElement(): integration test with all basic functionality

        It's two parts, each with two things in them.
        '''
        elem = '''<score xmlns="http://www.music-encoding.org/ns/mei">
            <scoreDef meter.count="8" meter.unit="8">
                <staffGrp>
                    <staffDef n="1" clef.shape="G" clef.line="2"/>
                    <staffDef n="2" clef.shape="F" clef.line="4"/>
                </staffGrp>
            </scoreDef>
            <section>
                <measure>
                    <staff n="1">
                        <layer n="1">
                            <note pname="G" oct="4" dur="2" slur="i1"/>
                            <note pname="A" oct="4" dur="2" slur="t1"/>
                        </layer>
                    </staff>
                    <staff n="2">
                        <layer n="1">
                            <note pname="G" oct="2" dur="1"/>
                        </layer>
                    </staff>
                </measure>
            </section>
        </score>'''
        elem = ETree.fromstring(elem)

        c = MeiReader()
        actual = c.scoreFromElement(elem)

        # This is complicated... I'm sorry... but it's a rather detailed test of the whole system,
        # so I hope it's worth it!
        self.assertEqual(2, len(actual.parts))
        self.assertEqual(4, len(actual))  # parts plus staffGroup plus spannerBundle
        self.assertEqual(1, len(actual.parts[0]))  # one Measure in each part
        self.assertEqual(1, len(actual.parts[1]))
        self.assertFalse(actual.parts[0].atSoundingPitch)  # each Part is set as not sounding pitch
        self.assertFalse(actual.parts[1].atSoundingPitch)
        self.assertIsInstance(actual.parts[0][0], stream.Measure)
        self.assertIsInstance(actual.parts[1][0], stream.Measure)
        self.assertEqual(4, len(actual.parts[0][0]))
        # each Measure has a Clef, a TimeSignature, a Voice, and a right Barline
        self.assertEqual(4, len(actual.parts[1][0]))
        # Inspect the Voice and the Note objects inside it
        self.assertIsInstance(actual.parts[0][0][2], stream.Voice)
        self.assertIsInstance(actual.parts[1][0][2], stream.Voice)
        self.assertEqual(2, len(actual.parts[0][0][2]))  # two Note in upper part
        self.assertEqual(1, len(actual.parts[1][0][2]))  # one Note in lower part
        self.assertIsInstance(actual.parts[0][0][2][0], note.Note)  # upper part, note 1
        self.assertEqual('G4', actual.parts[0][0][2][0].nameWithOctave)
        self.assertEqual(2.0, actual.parts[0][0][2][0].quarterLength)
        self.assertIsInstance(actual.parts[0][0][2][1], note.Note)  # upper part, note 2
        self.assertEqual('A4', actual.parts[0][0][2][1].nameWithOctave)
        self.assertEqual(2.0, actual.parts[0][0][2][1].quarterLength)
        self.assertIsInstance(actual.parts[1][0][2][0], note.Note)  # lower part
        self.assertEqual('G2', actual.parts[1][0][2][0].nameWithOctave)
        self.assertEqual(4.0, actual.parts[1][0][2][0].quarterLength)
        # Inspect the Clef and TimeSignature objects that follow the Voice
        self.assertIsInstance(actual.parts[0][0][0], clef.TrebleClef)  # upper
        self.assertIsInstance(actual.parts[0][0][1], meter.TimeSignature)
        self.assertEqual('8/8', actual.parts[0][0][1].ratioString)
        self.assertIsInstance(actual.parts[1][0][0], clef.BassClef)  # lower
        self.assertIsInstance(actual.parts[1][0][1], meter.TimeSignature)
        self.assertEqual('8/8', actual.parts[1][0][1].ratioString)

    def testCoreIntegration1(self):
        '''
        sectionScoreCore(): everything basic, as called by scoreFromElement()
            - no keywords
                - and the <measure> has no @n; it would be set to "1" automatically
            - one of everything (<section>, <scoreDef>, and <staffDef>)
            - that the <measure> in here won't be processed (<measure> must be in a <section>)
            - things in a <section> are appended properly (different for <score> and <section>)
        '''
        # setup the arguments
        elem = '''<score xmlns="http://www.music-encoding.org/ns/mei">
            <scoreDef meter.count="8" meter.unit="8"/>
            <staffDef n="1" clef.shape="G" clef.line="2"/>
            <measure/>
            <section>
                <measure>
                    <staff n="1">
                        <layer n="1">
                            <note pname="G" oct="4" dur="1"/>
                        </layer>
                    </staff>
                </measure>
            </section>
        </score>'''
        elem = ETree.fromstring(elem)
        allPartNs = ['1']

        c = MeiReader()
        parsed, nextMeasureLeft = c.sectionScoreCore(elem, allPartNs)

        # ensure simple returns are okay
        self.assertEqual('8/8', c.activeMeter.ratioString)
        self.assertIsNone(nextMeasureLeft)
        # ensure "parsed" is the right format
        self.assertEqual(1, len(parsed))
        self.assertTrue('1' in parsed)
        self.assertEqual(1, len(parsed['1']))  # one <measure> from one <section>
        meas = parsed['1'][0][0]
        self.assertIsInstance(meas, stream.Measure)
        # self.assertEqual(1, meas.number)
        self.assertEqual(4, len(meas))  # a Voice, a Clef, a TimeSignature, and a right Barline
        # the order of these doesn't matter, but it may change, so this is easier to adjust
        clefIndex = 0
        timeSigIndex = 1
        voiceIndex = 2
        self.assertIsInstance(meas[voiceIndex], stream.Voice)  # check out the Voice and its Note
        self.assertEqual(1, len(meas[voiceIndex]))
        self.assertIsInstance(meas[voiceIndex][0], note.Note)
        self.assertEqual('G4', meas[voiceIndex][0].nameWithOctave)
        self.assertIsInstance(meas[clefIndex], clef.TrebleClef)
        self.assertIsInstance(meas[timeSigIndex], meter.TimeSignature)
        self.assertEqual('8/8', meas[timeSigIndex].ratioString)

    def testCoreIntegration2(self):
        '''
        sectionScoreCore(): everything basic, as called by sectionFromElement()
            - no keywords
                - but the <measure> elements do have @n so those values should be used
            - one of most things (<section>, <scoreDef>, and <staffDef>)
            - two of <measure> (one in a <section>)
            - things in a <section> are appended properly (different for <score> and <section>)
        '''
        # setup the arguments
        elem = '''<section xmlns="http://www.music-encoding.org/ns/mei">
            <scoreDef meter.count="8" meter.unit="8"/>
            <staffDef n="1" clef.shape="G" clef.line="2"/>
            <measure n="400">
                <staff n="1">
                    <layer n="1">
                        <note pname="E" oct="7" dur="1"/>
                    </layer>
                </staff>
            </measure>
            <section>
                <measure n="92">
                    <staff n="1">
                        <layer n="1">
                            <note pname="G" oct="4" dur="1"/>
                        </layer>
                    </staff>
                </measure>
            </section>
        </section>'''
        elem = ETree.fromstring(elem)
        allPartNs = ['1']

        c = MeiReader()
        parsed, nextMeasureLeft = c.sectionScoreCore(elem, allPartNs)

        # ensure simple returns are okay
        self.assertEqual('8/8', c.activeMeter.ratioString)
        self.assertIsNone(nextMeasureLeft)
        # ensure "parsed" is the right format
        self.assertEqual(1, len(parsed))
        self.assertTrue('1' in parsed)
        self.assertEqual(2, len(parsed['1']))  # one <measure> plus one <section>
        # with one <measure> in it
        # check the first Measure
        meas = parsed['1'][0]
        # the order of these doesn't matter, but it may change, so this is easier to adjust
        clefIndex = 0
        timeSigIndex = 1
        voiceIndex = 2
        self.assertIsInstance(meas, stream.Measure)
        self.assertEqual(400, meas.number)
        self.assertEqual(4, len(meas))  # a Voice, a Clef, a TimeSignature, a right Barline
        self.assertIsInstance(meas[voiceIndex], stream.Voice)  # check out the Voice and its Note
        self.assertEqual(1, len(meas[voiceIndex]))
        self.assertIsInstance(meas[voiceIndex][0], note.Note)
        self.assertEqual('E7', meas[voiceIndex][0].nameWithOctave)
        self.assertIsInstance(meas[clefIndex], clef.TrebleClef)  # check out the Clef
        self.assertIsInstance(meas[timeSigIndex], meter.TimeSignature)  # check out the TS
        self.assertEqual('8/8', meas[timeSigIndex].ratioString)
        # check the second Measure
        meas = parsed['1'][1]
        # the order of these doesn't matter, but it may change, so this is easier to adjust
        clefIndex = 0
        timeSigIndex = 1
        voiceIndex = 2
        self.assertIsInstance(meas, stream.Measure)
        self.assertEqual(92, meas.number)
        self.assertEqual(2, len(meas))  # a Voice, a right Barline
        self.assertIsInstance(meas[0], stream.Voice)  # check out the Voice and its Note
        self.assertEqual(1, len(meas[0]))
        self.assertIsInstance(meas[0][0], note.Note)
        self.assertEqual('G4', meas[0][0].nameWithOctave)

    @mock.patch('converter21.mei.meireader.MeiReader.measureFromElement')
    @mock.patch('converter21.mei.meireader.MeiReader.sectionFromElement')
    @mock.patch('converter21.mei.meireader.MeiReader.scoreDefFromElement')
    @mock.patch('converter21.mei.meireader.MeiReader.staffDefFromElement')
    def testCoreUnit3(self, mockStaffDFE, mockScoreDFE, mockSectionFE, mockMeasureFE):
        '''
        sectionScoreCore(): everything basic, as called by sectionFromElement()
            - all keywords
                - and the <measure> has no @n
                - nextMeasureLeft = 'next left measure' (expected in the Measure)

        mocked:
            - measureFromElement()
            - sectionFromElement()
            - scoreDefFromElement()
            - staffDefFromElement()
        '''
        # setup the arguments
        # NB: there's more MEI here than we need, but it's shared between unit & integration tests
        elem = '''<section xmlns="http://www.music-encoding.org/ns/mei">
            <measure>
                <staff n="1">
                    <layer n="1">
                        <note pname="G" oct="4" dur="1"/>
                    </layer>
                </staff>
            </measure>
        </section>'''
        elem = ETree.fromstring(elem)
        allPartNs = ['1']
        activeMeter = mock.MagicMock(spec_set=meter.TimeSignature)
        nextMeasureLeft = 'next left measure'
        # setup measureFromElement()
        expMeas1 = mock.MagicMock(spect_set=stream.Stream)
        mockMeasureFE.return_value = {'1': expMeas1}
        # prepare the "expected" return
        expActiveMeter = activeMeter
        expNMLeft = None
        expected = {'1': [expMeas1]}
        expected = (expected, expNMLeft)

        c = MeiReader()
        c.activeMeter = activeMeter
        actual = c.sectionScoreCore(elem,
                                       allPartNs,
                                       nextMeasureLeft)

        self.assertEqual(expActiveMeter, c.activeMeter)

        # ensure expected == actual
        self.assertEqual(expected, actual)
        # ensure measureFromElement()
        mockMeasureFE.assert_called_once_with(mock.ANY,
                                              allPartNs)
        # ensure sectionFromElement()
        self.assertEqual(0, mockSectionFE.call_count)
        # ensure scoreDefFromElement()
        self.assertEqual(0, mockScoreDFE.call_count)
        # ensure staffDefFromElement()
        self.assertEqual(0, mockStaffDFE.call_count)
        # ensure the "nextMeasureLeft" was actually put onto the Measure
        self.assertEqual(nextMeasureLeft, actual[0]['1'][0].leftBarline)

    def testCoreIntegration3(self):
        '''
        sectionScoreCore(): everything basic, as called by sectionFromElement()
            - all keywords
                - and the <measure> has no @n
                - nextMeasureLeft = 'next left measure' (expected in the Measure)
        '''
        # setup the arguments
        elem = '''<section xmlns="http://www.music-encoding.org/ns/mei">
            <measure>
                <staff n="1">
                    <layer n="1">
                        <note pname="G" oct="4" dur="1"/>
                    </layer>
                </staff>
            </measure>
        </section>'''
        elem = ETree.fromstring(elem)
        allPartNs = ['1']
        activeMeter = meter.TimeSignature('8/8')
        nextMeasureLeft = bar.Repeat('start')

        c = MeiReader()
        c.activeMeter = activeMeter
        parsed, nextMeasureLeft = c.sectionScoreCore(
            elem,
            allPartNs,
            nextMeasureLeft=nextMeasureLeft)

        # ensure simple returns are okay
        self.assertEqual('8/8', c.activeMeter.ratioString)
        self.assertIsNone(nextMeasureLeft)
        # ensure "parsed" is the right format
        self.assertEqual(1, len(parsed))
        self.assertTrue('1' in parsed)
        self.assertEqual(1, len(parsed['1']))  # one <measure>
        # check the Measure
        meas = parsed['1'][0]
        # the order of these doesn't matter, but it may change, so this is easier to adjust
        repeatIndex = 0
        voiceIndex = 1
        self.assertIsInstance(meas, stream.Measure)
        # self.assertEqual(901, meas.number)
        self.assertEqual(3, len(meas))  # a Repeat, a Voice, a right Barline
        self.assertIsInstance(meas[voiceIndex], stream.Voice)  # check out the Voice and its Note
        self.assertEqual(1, len(meas[voiceIndex]))
        self.assertIsInstance(meas[voiceIndex][0], note.Note)
        self.assertEqual('G4', meas[voiceIndex][0].nameWithOctave)
        self.assertIsInstance(meas[repeatIndex], bar.Repeat)  # check the Repeat barline
        self.assertEqual('start', meas[repeatIndex].direction)
        self.assertIs(meas[repeatIndex], meas.leftBarline)

    @mock.patch('converter21.mei.meireader.environLocal')
    @mock.patch('converter21.mei.meireader.MeiReader.measureFromElement')
    @mock.patch('converter21.mei.meireader.MeiReader.sectionFromElement')
    @mock.patch('converter21.mei.meireader.MeiReader.scoreDefFromElement')
    @mock.patch('converter21.mei.meireader.MeiReader.staffDefFromElement')
    def testCoreUnit4(self, mockStaffDFE, mockScoreDFE, mockSectionFE, mockMeasureFE, mockEnviron):
        '''
        sectionScoreCore(): as called by sectionFromElement()
            - there's an "rptboth" barline, so we have to return a "nextMeasureLeft"
            - the <staffDef> gives a TimeSignature, so we have to expect "activeMeter" to change
            - there's a <staffDef> without @n attribute, so we have to warn the user about it
            - there's an unknown element, so we have to debug-warn the user

        mocked:
            - measureFromElement()
            - sectionFromElement()
            - scoreDefFromElement()
            - staffDefFromElement()
            - environLocal
        '''
        # setup the arguments
        # NB: there's more MEI here than we need, but it's shared between unit & integration tests
        elem = '''<section xmlns="http://www.music-encoding.org/ns/mei">
            <bogus>5</bogus>  <!-- this will be ignored -->
            <staffDef n="1" meter.count="6" meter.unit="8"/>
            <staffDef key.accid="3s" key.mode="minor"/>  <!-- this will be ignored -->
            <measure n="42" right="rptboth">
                <staff n="1"><layer n="1"><note pname="G" oct="4" dur="1"/></layer></staff>
            </measure>
        </section>'''
        elem = ETree.fromstring(elem)
        allPartNs = ['1']
        # setup measureFromElement()
        # return a Mock with the right measure number
        expMeas1 = mock.MagicMock(spec_set=stream.Stream)
        expRepeat = mock.MagicMock(spec_set=bar.Repeat)
        mockMeasureFE.return_value = {'1': expMeas1, 'next @left': expRepeat}
        # setup staffDefFromElement()
        expMeter = mock.MagicMock(spec_set=meter.TimeSignature)
        mockStaffDFE.return_value = {'meter': expMeter}
        # prepare the "expected" return
        expActiveMeter = expMeter
        expNMLeft = expRepeat
        expected = {'1': [expMeas1]}
        expected = (expected, expNMLeft)
        # prepare expected environLocal message
        expWarn1 = meireader._UNPROCESSED_SUBELEMENT.format(f'{MEI_NS}bogus', f'{MEI_NS}section')
        expWarn2 = meireader._UNIMPLEMENTED_IMPORT_WITHOUT.format('<staffDef>', '@n')
        c = MeiReader()
        c.activeMeter = expMeter
        actual = c.sectionScoreCore(elem, allPartNs)
        self.assertEqual(expActiveMeter, c.activeMeter)

        # ensure expected == actual
        self.assertEqual(expected, actual)

        # ensure environLocal
        mockEnviron.warn.assert_any_call(expWarn1)
        mockEnviron.warn.assert_any_call(expWarn2)

        # ensure measureFromElement()
        mockMeasureFE.assert_called_once_with(mock.ANY,
                                              allPartNs)
        # ensure sectionFromElement()
        self.assertEqual(0, mockSectionFE.call_count)
        # ensure scoreDefFromElement()
        self.assertEqual(0, mockScoreDFE.call_count)
        # ensure staffDefFromElement()
        mockStaffDFE.assert_called_once_with(mock.ANY)
        self.assertEqual(
            c.pendingInNextThing, {'1': []}
        )

    @mock.patch('converter21.mei.meireader.environLocal')
    def testCoreIntegration4(self, mockEnviron):
        '''
        sectionScoreCore(): as called by sectionFromElement()
            - there's an "rptboth" barline, so we have to return a "nextMeasureLeft"
            - the <staffDef> gives a TimeSignature, so we have to change "activeMeter" (and return)
            - there's a <staffDef> without @n attribute, so we have to warn the user about it
            - there's an unknown element, so we have to debug-warn the user
        '''
        # setup the arguments
        elem = '''<section xmlns="http://www.music-encoding.org/ns/mei">
            <bogus>5</bogus>  <!-- this will be ignored -->
            <staffDef n="1" meter.count="6" meter.unit="8"/>
            <staffDef key.accid="3s" key.mode="minor"/>  <!-- this will be ignored -->
            <measure n="42" right="rptboth">
                <staff n="1"><layer n="1"><note pname="G" oct="4" dur="1"/></layer></staff>
            </measure>
        </section>'''
        elem = ETree.fromstring(elem)
        allPartNs = ['1']

        c = MeiReader()
        parsed, nextMeasureLeft = c.sectionScoreCore(
            elem, allPartNs
        )

        expWarn1 = meireader._UNPROCESSED_SUBELEMENT.format(f'{MEI_NS}bogus', f'{MEI_NS}section')
        expWarn2 = meireader._UNIMPLEMENTED_IMPORT_WITHOUT.format('<staffDef>', '@n')

        mockEnviron.warn.assert_any_call(expWarn1)
        mockEnviron.warn.assert_any_call(expWarn2)

        # ensure simple returns are okay
        self.assertEqual('6/8', c.activeMeter.ratioString)
        self.assertIsInstance(nextMeasureLeft, bar.Repeat)
        # ensure "parsed" is the right format
        self.assertEqual(1, len(parsed))
        self.assertTrue('1' in parsed)
        self.assertEqual(1, len(parsed['1']))  # one <measure>
        # check the Measure
        meas = parsed['1'][0]
        # the order of these doesn't matter, but it may change, so this is easier to adjust
        timeSigIndex = 0
        voiceIndex = 1
        repeatIndex = 2
        self.assertIsInstance(meas, stream.Measure)
        self.assertEqual(42, meas.number)
        self.assertEqual(3, len(meas))  # a Voice, a TimeSignature, a Repeat
        self.assertIsInstance(meas[voiceIndex], stream.Voice)  # check out the Voice and its Note
        self.assertEqual(1, len(meas[voiceIndex]))
        self.assertIsInstance(meas[voiceIndex][0], note.Note)
        self.assertEqual('G4', meas[voiceIndex][0].nameWithOctave)
        self.assertIsInstance(meas[timeSigIndex], meter.TimeSignature)  # check the TimeSignature
        self.assertEqual('6/8', meas[timeSigIndex].ratioString)
        self.assertIsInstance(meas[repeatIndex], bar.Repeat)  # check the Repeat barline
        self.assertEqual('end', meas[repeatIndex].direction)
        self.assertIs(meas[repeatIndex], meas.rightBarline)

    def testCoreIntegration5(self):
        '''
        sectionScoreCore(): as called by scoreFromElement()

        With a preposterously embedded set of <section> elements, we have to ensure that
        staff-related metadata are cascaded properly into the <measure>

        NOTE there is no unit test corresponding to this integration test---this
            is really all about the cumulative effect
        '''
        # setup the arguments
        elem = '''<score xmlns="http://www.music-encoding.org/ns/mei">
            <scoreDef keysig="1f" key.mode="minor">
                <staffGrp>
                    <staffDef n="1" clef.line="4" clef.shape="F"/>
                </staffGrp>
            </scoreDef>
            <staffDef n="1" meter.count="6" meter.unit="8"/>
            <section>
                <staffDef n="1" label="tuba"/>
                <section>
                    <measure n="42">
                        <staff n="1">
                            <layer n="1"><note pname="C" oct="1" dur="1"/></layer>
                        </staff>
                    </measure>
                </section>
            </section>
            <section>
                <measure n="402">
                    <staff n="1">
                        <layer n="1"><note pname="C" oct="2" dur="1"/></layer>
                    </staff>
                </measure>
            </section>
        </score>'''
        elem = ETree.fromstring(elem)
        allPartNs = ['1']

        c = MeiReader()
        parsed, nextMeasureLeft = c.sectionScoreCore(
            elem, allPartNs
        )

        # ensure simple returns are okay
        self.assertEqual('6/8', c.activeMeter.ratioString)
        self.assertIsNone(nextMeasureLeft)
        # ensure "parsed" is the right format
        self.assertEqual(2, len(parsed))
        self.assertTrue('1' in parsed)
        self.assertEqual(2, len(parsed['1']))  # two <measure>s, each in a <section>
        self.assertTrue('whole-score objects' in parsed)
        self.assertTrue('staff-groups' in parsed['whole-score objects'])
        self.assertTrue('parts' in parsed['whole-score objects'])
        self.assertTrue('1' in parsed['whole-score objects']['parts'])
        # check the Instrument
        instr = parsed['1'][0][0]
        self.assertIsInstance(instr, instrument.Tuba)  # check out the Instrument
        # check the first Measure
        meas = parsed['1'][0][1]
        # the order of these doesn't matter, but it may change, so this is easier to adjust
        clefIndex = 0
        keysigIndex = 1
        timesigIndex = 2
        voiceIndex = 3
        self.assertIsInstance(meas, stream.Measure)
        self.assertEqual(42, meas.number)
        self.assertEqual(5, len(meas))  # Clef, KeySignature, TimeSignature, Voice, right Barline
        self.assertIsInstance(meas[voiceIndex], stream.Voice)  # check out the Voice and its Note
        self.assertEqual(1, len(meas[voiceIndex]))
        self.assertIsInstance(meas[voiceIndex][0], note.Note)
        self.assertEqual('C1', meas[voiceIndex][0].nameWithOctave)
        self.assertIsInstance(meas[clefIndex], clef.BassClef)  # check out the Clef
        self.assertIsInstance(meas[keysigIndex], key.KeySignature)  # check out the KeySignature
        self.assertEqual(-1, meas[keysigIndex].sharps)
        self.assertEqual('minor', meas[keysigIndex].mode)
        self.assertIsInstance(meas[timesigIndex], meter.TimeSignature)  # check the TimeSignature
        self.assertEqual('6/8', meas[timesigIndex].ratioString)
        # check the second Measure
        meas = parsed['1'][1][0]
        self.assertIsInstance(meas, stream.Measure)
        self.assertEqual(402, meas.number)
        self.assertEqual(2, len(meas))  # a Voice, a right Barline
        self.assertIsInstance(meas[0], stream.Voice)  # check out the Voice and its Note
        self.assertEqual(1, len(meas[0]))
        self.assertIsInstance(meas[0][0], note.Note)
        self.assertEqual('C2', meas[0][0].nameWithOctave)


# -----------------------------------------------------------------------------
# class TestBarLineFromElement(unittest.TestCase):
    '''Tests for barLineFromElement()'''

    def testBarLine1(self):
        '''
        barLineFromElement(): <barLine rend="dbl"/>
        '''
        elem = ETree.Element('barLine', attrib={'rend': 'dbl'})
        c = MeiReader()
        actual = c.barLineFromElement(elem)
        self.assertIsInstance(actual, bar.Barline)
        self.assertEqual('double', actual.type)

    def testBarLine2(self):
        '''
        barLineFromElement(): <barLine/>
        '''
        elem = ETree.Element('barLine')
        c = MeiReader()
        actual = c.barLineFromElement(elem)
        self.assertIsInstance(actual, bar.Barline)
        self.assertEqual('regular', actual.type)


# -----------------------------------------------------------------------------
# class RegressionIntegrationTests(unittest.TestCase):
    '''
    Targeted tests that address bugs, run without any mock objects.
    '''

    # noinspection SpellCheckingInspection
    def testInstrumentDetails(self):
        '''
        Ensure that instrument details are imported properly.

        There should be one instrument called "Clarinet."
        '''
        meiSource = '''<?xml version="1.0" encoding="UTF-8"?>
            <mei xmlns="http://www.music-encoding.org/ns/mei" meiversion="4.0">
            <music><score>
                <scoreDef meter.count="8" meter.unit="8">
                    <staffGrp>
                        <staffDef n="1" label="Clarinet" trans.diat="-2" trans.semi="-3">
                            <clef shape="F" line="4"/>
                        </staffDef>
                    </staffGrp>
                </scoreDef>
                <section>
                    <scoreDef key.sig="1f" key.mode="major"/>
                    <measure n="1">
                        <staff n="1">
                            <layer n="1" xml:id="asdf">
                                <note pname="E" oct="2" dur="1"/>
                            </layer>
                        </staff>
                    </measure>
                </section>
            </score></music></mei>
        '''
        testConv = MeiReader(meiSource)

        actual = testConv.run()

        self.assertEqual(1, len(actual.parts[0].getInstruments()))
        instr = actual.parts[0].getInstruments()[0]
        self.assertIsInstance(instr, instrument.Instrument)
        self.assertEqual(instr.partName, 'Clarinet')
        self.assertEqual(instr.transposition.directedName, 'm-3')

    def testUniqueInstances(self):
        from music21 import converter
        import converter21
        converter21.register(converter21.ConverterName.MEI)

        fp = Path('converter21') / 'mei' / 'test' / 'test_file.mei'
        s = converter.parse(fp, forceSource=True)

        seen_ids = set()
        for el in s.recurse():
            self.assertNotIn(id(el), seen_ids, el)
            seen_ids.add(id(el))


if __name__ == '__main__':
    import music21
    music21.mainTest(Test)

# -----------------------------------------------------------------------------
