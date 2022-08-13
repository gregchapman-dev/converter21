# ------------------------------------------------------------------------------
# Name:          HumSignifiers.py
# Purpose:       Parsing/interpreting of RDF signifiers during Humdrum import
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
import re
import typing as t

SIGNIFIER_UNKNOWN: str = 'unknown'
SIGNIFIER_LINK: str = 'link'
SIGNIFIER_ABOVE: str = 'above'
SIGNIFIER_BELOW: str = 'below'

class HumSignifier:
    def __init__(self) -> None:
        self._exInterp: str = ''
        self._signifier: str = ''

        # _definition is either:
        #   the string after the first '=' in '!!!RDF:**kern: i = blah bleah blech'
        #       (in this case, _signifier = 'i', and _definition = 'blah bleah blech')
        # or _definition is:
        #   the string after the second ':' in '!!!RDF:**kern: show spaces color=hotpink'
        #       (in this case, _signifier = '', and _definition = 'show spaces color=hotpink')
        self._definition: str = ''

    '''
    //////////////////////////////
    //
    // HumSignifier::parseSignifier --
    '''
    def parseSignifier(self, rdfLine: str) -> bool:
        # in case this HumSignifier is pre-owned...
        self._exInterp = ''
        self._signifier = ''
        self._definition = ''

        # tease apart exInterp and "the rest" (rdfValue)
        m1 = re.search(r'!!!RDF(\*\*[^\s:]+)\s*:\s*(.*)\s*$', rdfLine)
        if m1 is None:
            return False

        self._exInterp = m1.group(1)
        rdfValue = m1.group(2)

        # Look in rdfValue for the form 'i = blah bleah blech'
        # This pattern actually matches multi-char signifiers as well...
        m2 = re.search(r'^\s*([^\s=]+)\s*=\s*(.*)\s*$', rdfValue)
        if m2 is not None:
            self._signifier = m2.group(1)   # 'i'
            self._definition = m2.group(2)  # 'blah bleah blech'
            return True

        # Must be a meta signifier; _definition is rdfValue without leading/trailing
        # space-ish characters (spaces, tabs, etc)
        # e.g. 'show spaces color=hotpink'
        m2 = re.search(r'\s*(.*)\s*$', rdfValue)
        self._signifier = ''
        if m2 is not None:
            self._definition = m2.group(1)
            return True

        return False

    '''
    //////////////////////////////
    //
    // HumSignifier::getSignifier --
    '''
    @property
    def signifier(self) -> str:
        return self._signifier

    '''
    //////////////////////////////
    //
    // HumSignifier::getDefinition --
    '''
    @property
    def definition(self) -> str:
        return self._definition

    @property
    def exInterp(self) -> str:
        return self._exInterp


QUOTEDSTRING_PATTERN: str = r'\s*"\s*([^"]+)\s*"'
SPACEDSTRING_PATTERN: str = r'\s*([^\s]+)'
EQUALSVALUE_PATTERN: str = r'\s*=\s*"?\s*([^"\s]+)\s*"?'
EQUALSVALUEWITHSPACES_PATTERN: str = r'\s*=\s*"?([^"]+)"?'


class HumSignifiers:
    def __init__(self) -> None:
        self._signifiers: t.List[HumSignifier] = []

        # pre-chewed known info

        # whether or not various types of invisible rests should be printed (with color)
        self.spaceColor: str = ''       # !!!RDF**kern: show spaces color=hotpink
        self.ispaceColor: str = ''      # !!!RDF**kern: show implicit spaces color=blueviolet
        self.rspaceColor: str = ''      # !!!RDF**kern: show recip spaces color=royalblue
        self.irestColor: str = ''       # !!!RDF**kern: show invisible rests color=chartreuse

        # colored lyrics
        self.textMarks: t.List[str] = []      # a list of text mark signifiers
        self.textColors: t.List[str] = []     # a matching list of color strings

        # colored notes (with optional 'direction' text to print)
        # !!!RDF**kern: i = marked note, color="#553325", text="print this"
        # !!!RDF**kern: i = matched note, color=red
        # !!!RDF**kern: i = color="blue"
        # default is red if no color given:
        # !!!RDF**kern: i = matched note, text="print this"
        # !!!RDF**kern: i = marked note
        self.noteMarks: t.List[str] = []       # a list of note mark signifiers
        self.noteColors: t.List[str] = []  # a matching list of color strings
        self.noteDirs: t.List[str] = []    # a matching list of mark "direction" strings

        # for **dynam:
        # The signifiers must be < for crescendo and > for decrescendo.
        # Others are silently ignored. In that sense, these are meta signifiers,
        # describing what text/style should be printed for every crescendo and
        # decrescendo in the score.
        self.crescText: str = ''         # !!!RDF**dynam: < = "cresc."
        self.crescFontStyle: str = ''    # !!!RDF**dynam: < = "cresc."
        #                                        fontstyle = "normal | italic | bold | bold-italic"
        self.decrescText: str = ''       # !!!RDF**dynam: > = "decresc."
        self.decrescFontStyle: str = ''  # !!!RDF**dynam: > = "decresc."
        #                                        fontstyle = "normal | italic | bold | bold-italic"

        # boolean switches:
        self.noStem: str = ''            # !!!RDF**kern: N = no stem
        self.cueSize: str = ''           # !!!RDF**kern: ! = cue size
        self.hairpinAccent: str = ''     # !!!RDF**kern: j = hairpin accent
        self.verticalStroke: str = ''    # !!!RDF**kern: | = vertical stroke
        self.terminalLong: str = ''      # !!!RDF**kern: l = terminal long|long note
        self.above: str = ''             # !!!RDF**kern: > = above
        self.below: str = ''             # !!!RDF**kern: < = below
        self.linked: str = ''            # !!!RDF**kern: N = linked

        # editorial accidentals
        # !!!RDF**kern: i = editorial accidental
        # !!!RDF**kern: i = editorial accidental, brack[ets]/paren[theses]
        self.editorialAccidentals: t.List[str] = []       # a list of signifiers
        self.editorialAccidentalTypes: t.List[str] = []   # a matching list of types (e.g. 'brack')

        # for global styling of phrase markers
        # !!!RDF**kern: <something something phrase something dot something slur> color="blue"
        # Supported phraseStyles are none, brack, dot, dash
        # phraseIsSlur is set to True if "slur" is seen
        # phraseColor is set if "color=<something>" is seen
        self.phraseStyle: str = ''  # e.g. 'dot', 'dash', 'brack', 'none', ''
        self.phraseIsSlur: bool = False
        self.phraseColor: str = ''

    '''
    //////////////////////////////
    //
    // HumSignifiers::addSignifier --
    '''
    def addSignifier(self, rdfLine: str) -> bool:
        humSig: HumSignifier = HumSignifier()
        if not humSig.parseSignifier(rdfLine):
            return False

        self._signifiers.append(humSig)

        return True

    '''
        generateKnownInfo -- to be called after adding all the RDF signifiers... generates
        high-level properties that can be easily asked about by the converter code without
        having to dive into each RDF signifier looking for "above", or whatever.  Patterned
        after how HumdrumInput::parseSignifiers does it in iohumdrum.cpp.
        If your Humdrum file has custom RDF signifiers in it, you can still look through
        the parsed RDF signifiers yourself to see what they say.
    '''
    def generateKnownInfo(self) -> None:
        for rdf in self._signifiers:
            if rdf.signifier == '' and rdf.exInterp == '**kern':
                # meta signifier (no actual signifier)

                # colored spaces (meta signifiers)
                # !!!RDF**kern: show spaces color=hotpink
                # !!!RDF**kern: show invisible rests color=chartreuse
                # !!!RDF**kern: show implicit spaces color=purple
                # !!!RDF**kern: show recip spaces color=royalblue
                m = re.search('color' + EQUALSVALUE_PATTERN, rdf.definition)
                if 'show space' in rdf.definition:
                    self.spaceColor = 'hotpink'
                    if m:
                        self.spaceColor = m.group(1)
                    continue

                if 'show invisible rest' in rdf.definition:
                    self.irestColor = 'chartreuse'
                    if m:
                        self.irestColor = m.group(1)
                    continue

                if 'show implicit space' in rdf.definition:
                    self.ispaceColor = 'blueviolet'
                    if m:
                        self.ispaceColor = m.group(1)
                    continue

                if 'show recip space' in rdf.definition:
                    self.rspaceColor = 'royalblue'
                    if m:
                        self.rspaceColor = m.group(1)
                    continue

                continue

            if rdf.signifier == '':
                continue

            # actual signifier

            # lyrics tracks
            if rdf.exInterp in ('**silbe', '**text'):
                if 'marked text' in rdf.definition or 'matched text' in rdf.definition:
                    self.textMarks.append(rdf.signifier)
                    m = re.search('color' + EQUALSVALUE_PATTERN, rdf.definition)
                    if m:
                        self.textColors.append(m.group(1))
                    else:
                        self.textColors.append('red')
                continue

            # dynamics tracks
            if rdf.exInterp == '**dynam':
                if rdf.signifier == '>':
                    m = re.search(QUOTEDSTRING_PATTERN, rdf.definition)
                    if not m:
                        m = re.search(SPACEDSTRING_PATTERN, rdf.definition)
                    if m:
                        self.decrescText = m.group(1)
                        m = re.search('fontstyle' + EQUALSVALUE_PATTERN, rdf.definition)
                        if m:
                            self.decrescFontStyle = m.group(1)
                    continue

                if rdf.signifier == '<':
                    m = re.search(QUOTEDSTRING_PATTERN, rdf.definition)
                    if not m:
                        m = re.search(SPACEDSTRING_PATTERN, rdf.definition)
                    if m:
                        self.crescText = m.group(1)
                        m = re.search('fontstyle' + EQUALSVALUE_PATTERN, rdf.definition)
                        if m:
                            self.crescFontStyle = m.group(1)
                    continue

                continue

            if rdf.exInterp != '**kern':
                continue

            # kern tracks

            # stemless note:
            # !!!RDF**kern: i = no stem
            if 'no stem' in rdf.definition:
                self.noStem = rdf.signifier
                continue

            # cue-sized note:
            # !!!RDF**kern: i = cue size
            if 'cue size' in rdf.definition:
                self.cueSize = rdf.signifier
                continue

            # hairpin accents:
            # !!!RDF**kern: i = hairpin accent
            if 'hairpin accent' in rdf.definition:
                self.hairpinAccent = rdf.signifier
                continue

            # vertical strokes:
            # !!!RDF**kern: | = vertical stroke
            if 'vertical stroke' in rdf.definition:
                self.verticalStroke = rdf.signifier

            # terminal longs
            # !!!RDF**kern: i = terminal long
            if 'terminal long' in rdf.definition or 'long note' in rdf.definition:
                self.terminalLong = rdf.signifier
                continue

            # slur directions and other above/below things
            if 'above' in rdf.definition:
                self.above = rdf.signifier
                continue

            if 'below' in rdf.definition:
                self.below = rdf.signifier
                continue

            if 'link' in rdf.definition:  # matches 'linked' too
                self.linked = rdf.signifier
                continue

            # editorial accidentals:
            if 'editorial accidental' in rdf.definition:
                self.editorialAccidentals.append(rdf.signifier)
                if 'brack' in rdf.definition:  # matches 'bracket' too
                    self.editorialAccidentalTypes.append('brack')
                    continue
                if 'paren' in rdf.definition:  # matches 'parentheses', 'parens', and 'parenthesis'
                    self.editorialAccidentalTypes.append('paren')
                    continue
                if 'none' in rdf.definition:
                    self.editorialAccidentalTypes.append('none')
                    continue
                self.editorialAccidentalTypes.append('')
                continue

            # phrase styles (including whether we should just insert it as a slur)
            if 'phrase' in rdf.definition:
                # is it just a slur?
                if 'slur' in rdf.definition:
                    self.phraseIsSlur = True

                # what is its color?
                m = re.search('color' + EQUALSVALUE_PATTERN, rdf.definition)
                if m:
                    self.phraseColor = m.group(1)

                # phrase drawing style:
                if 'none' in rdf.definition:
                    self.phraseStyle = 'none'
                    continue
                if 'brack' in rdf.definition:
                    self.phraseStyle = 'brack'
                    continue
                if 'dot' in rdf.definition:
                    self.phraseStyle = 'dot'
                    continue
                if 'dash' in rdf.definition:
                    self.phraseStyle = 'dash'
                    continue
                continue

            # colored notes
            # !!!RDF**kern: i = marked note, color="#ff0000"
            # !!!RDF**kern: i = matched note, color=blue
            # !!!RDF**kern: i = <anything at all>color=red
            m = re.search('color' + EQUALSVALUE_PATTERN, rdf.definition)
            if m:
                self.noteMarks.append(rdf.signifier)
                self.noteColors.append(m.group(1))
                m = re.search('text' + EQUALSVALUEWITHSPACES_PATTERN, rdf.definition)
                if m:
                    self.noteDirs.append(m.group(1))
                else:
                    self.noteDirs.append('')
                continue

            if 'marked note' in rdf.definition or 'matched note' in rdf.definition:
                self.noteMarks.append(rdf.signifier)
                # no color, since we checked above
                self.noteColors.append('red')
                m = re.search('text' + EQUALSVALUEWITHSPACES_PATTERN, rdf.definition)
                if m:
                    self.noteDirs.append(m.group(1))
                else:
                    self.noteDirs.append('')
                continue

    '''
    //////////////////////////////
    //
    // HumSignifiers::getSignifierCount --
    '''
    @property
    def signifierCount(self) -> int:
        return len(self._signifiers)

    '''
    //////////////////////////////
    //
    // HumSignifiers::getSignifier --
    '''
    def __getitem__(self, index: int) -> t.Optional[HumSignifier]:
        if index < 0:
            index += self.signifierCount

        if index < 0:
            return None
        if index >= self.signifierCount:
            return None

        return self._signifiers[index]
