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
    def textFromElem(elem: Element) -> tuple[str, dict[str, str]]:
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

            elif el.tag in MeiShared._CHOOSING_EDITORIALS:
                subEl: Element | None = MeiShared.chooseSubElement(el)
                if subEl is None:
                    continue
                el = subEl
            elif el.tag in MeiShared._PASSTHRU_EDITORIALS:
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