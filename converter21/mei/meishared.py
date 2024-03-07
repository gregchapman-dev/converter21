# ------------------------------------------------------------------------------
# Name:          meishared.py
# Purpose:       Shared utilities for MEI parser and MEI metadata parser
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2021-2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
from xml.etree.ElementTree import Element
import re

import music21 as m21

from converter21.mei import MeiElement
from converter21.shared import SharedConstants

environLocal = m21.environment.Environment('converter21.mei.meireader')

_XMLID = '{http://www.w3.org/XML/1998/namespace}id'
MEI_NS = '{http://www.music-encoding.org/ns/mei}'

class MeiShared:
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

    _EDITORIAL_ELEMENTS_NO_NAMESPACE: tuple[str, ...] = (
        'abbr',
        'add',
        'app',
        'choice',
        'corr',
        'damage',
        'del',
        'expan',
        'orig',
        'ref',
        'reg',
        'restore',
        'sic',
        'subst',
        'supplied',
        'unclear',
    )

    _IGNORED_EDITORIALS_NO_NAMESPACE: tuple[str, ...] = (
        'abbr',
        'del',
        'ref',
        'restore',  # I could support restore with a special FromElement API
    )                        # that reverses the meaning of del and add

    _PASSTHRU_EDITORIALS_NO_NAMESPACE: tuple[str, ...] = (
        'add',
        'corr',
        'damage',
        'expan',
        'orig',
        'reg',
        'sic',
        'subst',
        'supplied',
        'unclear',
    )

    _CHOOSING_EDITORIALS_NO_NAMESPACE: tuple[str, ...] = (
        'app',
        'choice',
    )

    @staticmethod
    def _glyphNameToUnicodeChar(name: str) -> str:
        # name is things like 'noteQuarterUp', which can be looked up
        return SharedConstants.SMUFL_NAME_TO_UNICODE_CHAR.get(name, '')

    @staticmethod
    def _glyphNumToUnicodeChar(num: str) -> str:
        # num can be '#xNNNN' or 'U+NNNN'
        pattern: str = r'^(#x|U\+)([A-F0-9]+)$'
        m = re.match(pattern, num)
        if m is None:
            return ''
        return chr(int(m.group(2), 16))

    @staticmethod
    def removeOctothorpe(xmlid: str) -> str:
        '''
        Given a string with an @xml:id to search for, remove a leading octothorpe, if present.

        >>> from converter21.mei import MeiShared
        >>> MeiShared.removeOctothorpe('110a923d-a13a-4a2e-b85c-e1d438e4c5d6')
        '110a923d-a13a-4a2e-b85c-e1d438e4c5d6'
        >>> MeiShared.removeOctothorpe('#e46cbe82-95fc-4522-9f7a-700e41a40c8e')
        'e46cbe82-95fc-4522-9f7a-700e41a40c8e'
        '''
        if xmlid.startswith('#'):
            return xmlid[1:]
        return xmlid

    @staticmethod
    def chooseSubElement(appOrChoice: Element) -> Element | None:
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

    @staticmethod
    def chooseSubMeiElement(appOrChoice: MeiElement) -> MeiElement | None:
        chosen: MeiElement | None = None
        if appOrChoice.tag.endswith('app'):
            # choose 'lem' (lemma) if present, else first 'rdg' (reading)
            chosen = appOrChoice.findFirst('lem', recurse=False)
            if chosen is None:
                chosen = appOrChoice.findFirst('rdg', recurse=False)
            return chosen

        if appOrChoice.tag.endswith('choice'):
            # choose 'corr' (correction) if present,
            # else 'reg' (regularization) if present,
            # else first sub-element.
            chosen = appOrChoice.findFirst('corr', recurse=False)
            if chosen is None:
                chosen = appOrChoice.findFirst('reg', recurse=False)
            if chosen is None:
                chosen = appOrChoice.findFirst('*', recurse=False)
            return chosen

        environLocal.warn('Internal error: chooseSubMeiElement expects <app> or <choice>')
        return chosen  # None, if we get here

    @staticmethod
    def textFromElem(elem: Element | MeiElement, endAt: str = '') -> tuple[str, dict[str, str]]:
        # can take Element by converting directly to MeiElement
        if isinstance(elem, Element):
            elem = MeiElement(elem)

        styleDict: dict[str, str] = {}
        text: str = ''
        if elem.text:
            if elem.text[0] != '\n' or not elem.text.isspace():
                text += elem.text

        for el in elem.findAll('*', recurse=False):
            # do whatever is appropriate given el.tag (<rend> for example)

            if endAt and el.name == endAt:
                # for example, <title> text ends at first <titlePart>, but needs to parse <lb>.
                # in that case, endAt == 'titlePart'.
                break

            if el.name == 'rend':
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

            elif el.name in MeiShared._CHOOSING_EDITORIALS_NO_NAMESPACE:
                subEl: MeiElement | None = MeiShared.chooseSubMeiElement(el)
                if subEl is None:
                    continue
                el = subEl
            elif el.name in MeiShared._PASSTHRU_EDITORIALS_NO_NAMESPACE:
                # for now assume all we care about here is the text/tail of these subElements
                for subEl in el.findAll('*', recurse=True):
                    if subEl.text:
                        if subEl.text[0] != '\n' or not subEl.text.isspace():
                            text += subEl.text
                    if subEl.tail:
                        if subEl.tail[0] != '\n' or not subEl.tail.isspace():
                            text += subEl.tail
            elif el.name == 'lb':
                text += '\n'
            elif el.name == 'symbol':
                # This is a glyph in the SMUFL font (@glyph.auth="smufl"), with a
                # particular name (@glyph.name="metNoteQuarterUp").  Sometimes
                # instead of @glyph.name, there is @glyph.num, which is just the
                # utf16 code as 'U+NNNN' or '#xNNNN'.
                glyphAuth: str = el.get('glyph.auth', '')
                if not glyphAuth or glyphAuth == 'smufl':
                    glyphName: str = el.get('glyph.name', '')
                    glyphNum: str = el.get('glyph.num', '')
                    if glyphNum:
                        text += MeiShared._glyphNumToUnicodeChar(glyphNum)
                    elif glyphName:
                        text += MeiShared._glyphNameToUnicodeChar(glyphName)

            # grab the text from el
            elText: str
            elStyleDict: dict[str, str]
            elText, elStyleDict = MeiShared.textFromElem(el)
            text += elText
            styleDict.update(elStyleDict)

            # grab the text between this el and the next el
            if el.tail:
                if el.tail[0] != '\n' or not el.tail.isspace():
                    text += el.tail

        return text, styleDict
