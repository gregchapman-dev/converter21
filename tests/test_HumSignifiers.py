import pytest

# The things we're testing
from converter21.humdrum import HumSignifiers
from converter21.humdrum import HumSignifier

from tests.Utilities import CheckHumSignifier, CheckHumSignifiers

def test_HumSignifier_default_init():
    s = HumSignifier()
    CheckHumSignifier(s,
                        expectedExInterp='',
                        expectedSignifier='',
                        expectedDefinition='')

def test_HumSignifier_above():
    s = HumSignifier()
    assert True == s.parseSignifier('!!!RDF**kern: > = above')
    CheckHumSignifier(s,
                        expectedExInterp='**kern',
                        expectedSignifier='>',
                        expectedDefinition='above')

def test_HumSignifier_below():
    s = HumSignifier()
    assert True == s.parseSignifier('!!!RDF**kern: < = below')
    CheckHumSignifier(s,
                        expectedExInterp='**kern',
                        expectedSignifier='<',
                        expectedDefinition='below')

def test_HumSignifier_meta():
    s = HumSignifier()
    assert True == s.parseSignifier('!!!RDF**kern: show implicit spaces color=blueviolet')
    CheckHumSignifier(s,
                        expectedExInterp='**kern',
                        expectedSignifier='',
                        expectedDefinition='show implicit spaces color=blueviolet')

def test_HumSignifiers_metas():
    testStrings = ['!!!RDF**kern: show spaces color=hotpink',
                   '!!!RDF**kern: show implicit spaces color=blueviolet',
                   '!!!RDF**kern: show recip spaces color=royalblue',
                   '!!!RDF**kern: show invisible rests color=chartreuse',
                   ]
    hss = HumSignifiers()
    for testString in testStrings:
        assert hss.addSignifier(testString) == True

    hss.generateKnownInfo()

    CheckHumSignifiers(hss,
                       spaceColor='hotpink',
                       ispaceColor='blueviolet',
                       rspaceColor='royalblue',
                       irestColor='chartreuse'
                       )

def test_HumSignifiers_booleans():
    testStrings = ['!!!RDF**kern: > = above',
                   '!!!RDF**kern: < = below',
                   '!!!RDF**kern: N = linked',
                   '!!!RDF**kern: N = no stem',
                   '!!!RDF**kern: @ = cue size',
                   '!!!RDF**kern: j = hairpin accent',
                   '!!!RDF**kern: l = terminal long',
                   ]
    hss = HumSignifiers()
    for testString in testStrings:
        assert hss.addSignifier(testString) == True

    hss.generateKnownInfo()

    CheckHumSignifiers(hss,
                       above='>', below='<', linked='N',
                       noStem='N', cueSize='@',
                       hairpinAccent='j', terminalLong='l'
                       )

def test_HumSignifiers_booleansalternatenames():
    testStrings = ['!!!RDF**kern: N = link',
                   '!!!RDF**kern: l = long note',
                   ]
    hss = HumSignifiers()
    for testString in testStrings:
        assert hss.addSignifier(testString) == True

    hss.generateKnownInfo()

    CheckHumSignifiers(hss, linked='N', terminalLong='l')

def test_HumSignifiers_coloredMarkedMatchedNotes():
    testStrings = ['!!!RDF**kern: i = marked note, color="hotpink", text="extra("',
                   '!!!RDF**kern: j = marked note, color="magenta", text="extra)"',
                   '!!!RDF**kern: ia = matched note, color="blue", text="something"',
                   '!!!RDF**kern: ja = matched note, color="green", text="something else"',
                   '!!!RDF**kern: jjbb = color="skybluepink"',
                   '!!!RDF**kern: jjj = marked note',
                   '!!!RDF**kern: jj = matched note, text=whatever it might be',
                   ]
    hss = HumSignifiers()
    for testString in testStrings:
        assert hss.addSignifier(testString) == True

    hss.generateKnownInfo()

    CheckHumSignifiers(hss,
        noteMarks = ['i', 'j', 'ia', 'ja', 'jjbb', 'jjj', 'jj'],
        noteColors = ['hotpink', 'magenta', 'blue', 'green', 'skybluepink', 'red', 'red'],
        noteDirs = ['extra(', 'extra)', 'something', 'something else', '', '', 'whatever it might be'])

def test_HumSignifiers_dynamics():
    testStrings = ['!!!RDF**dynam: < = "cresc."',
                   '!!!RDF**dynam: > = decresc.',
                   ]
    hss = HumSignifiers()
    for testString in testStrings:
        assert hss.addSignifier(testString) == True

    hss.generateKnownInfo()

    CheckHumSignifiers(hss, crescText='cresc.', decrescText='decresc.',
                            crescFontStyle='', decrescFontStyle='')

def test_HumSignifiers_dynamicsWithStyle():
    testStrings = ['!!!RDF**dynam: < = crescendo fontstyle=normal',
                   '!!!RDF**dynam: > = "decrescendo lots" fontstyle="italic"',
                   ]
    hss = HumSignifiers()
    for testString in testStrings:
        assert hss.addSignifier(testString) == True

    hss.generateKnownInfo()

    CheckHumSignifiers(hss, crescText='crescendo', decrescText='decrescendo lots',
                            crescFontStyle='normal', decrescFontStyle='italic')

def test_HumSignifiers_coloredLyrics():
    testStrings = ['!!!RDF**text: @ = marked text, color=#00FF00',
                   '!!!RDF**silbe: ` = marked text, color=#FFFF00',
                   '!!!RDF**silbe: & = matched text', # default color is red
                   ]
    hss = HumSignifiers()
    for testString in testStrings:
        assert hss.addSignifier(testString) == True

    hss.generateKnownInfo()

    CheckHumSignifiers(hss, textMarks=['@', '`', '&'],
                            textColors=['#00FF00', '#FFFF00', 'red'])

def test_HumSignifiers_editorialAccidentals():
    testStrings = ['!!!RDF**kern: i = editorial accidental',
                   '!!!RDF**kern: ii = editorial accidental, brackets',
                   '!!!RDF**kern: iii = editorial accidental, brack',
                   '!!!RDF**kern: j = editorial accidental, parenthesis',
                   '!!!RDF**kern: jj = editorial accidental, paren',
                   '!!!RDF**kern: jjj = editorial accidental, none',
                   '!!!RDF**kern: kk = editorial accidental, something weird',
                   ]
    hss = HumSignifiers()
    for testString in testStrings:
        assert hss.addSignifier(testString) == True

    hss.generateKnownInfo()

    CheckHumSignifiers(hss,
                       editorialAccidentals=['i', 'ii', 'iii', 'j', 'jj', 'jjj', 'kk'],
                       editorialAccidentalTypes=['', 'brack', 'brack', 'paren', 'paren', 'none', ''])

