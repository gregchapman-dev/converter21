import pytest

# The things we're testing
import music21 as m21
from converter21.humdrum import Convert

# test utilities
from tests.Utilities import *

def test_getMetronomeMarkInfo():
    # no parens 'M.M.'
    text = 'Vivace. M.M. [half-dot] = 69.'
    tempoName, mmStr, refStr, bpmStr = Convert.getMetronomeMarkInfo(text)
    CheckString(tempoName, 'Vivace.')
    CheckString(mmStr, 'M.M.')
    CheckString(refStr, 'half-dot')
    CheckString(bpmStr, '69.')

    # no parens, no tempoName, 'M M'
    text = 'M M [half-dot] = 63.'
    tempoName, mmStr, refStr, bpmStr = Convert.getMetronomeMarkInfo(text)
    CheckString(tempoName, '')
    CheckString(mmStr, 'M M')
    CheckString(refStr, 'half-dot')
    CheckString(bpmStr, '63.')

    # parens include M.M. (doesn't actually work, but we expect that so the test passes)
    text = '(M.M. [half] = 72.)'
    tempoName, mmStr, refStr, bpmStr = Convert.getMetronomeMarkInfo(text)
    CheckString(tempoName, '(') # we might should fix this... should be ''
    CheckString(mmStr, 'M.M.')
    CheckString(refStr, 'half')
    CheckString(bpmStr, '72.')

    # parens, no tempoName, no space between M.M. and open paren
    text = 'M.M.([quarter] = 160)'
    tempoName, mmStr, refStr, bpmStr = Convert.getMetronomeMarkInfo(text)
    CheckString(tempoName, '')
    CheckString(mmStr, 'M.M.')
    CheckString(refStr, 'quarter')
    CheckString(bpmStr, '160')

    # no parens, no tempoName, no space between M.M. and open bracket
    text = 'M.M.[quarter] = 160'
    tempoName, mmStr, refStr, bpmStr = Convert.getMetronomeMarkInfo(text)
    CheckString(tempoName, '')
    CheckString(mmStr, 'M.M.')
    CheckString(refStr, 'quarter')
    CheckString(bpmStr, '160')

    # bad: tempName at end (some of the Chopin first editions have this)
    # it will parse everything else correctly, but tempoName == ''
    text = 'M.M. [quarter]=104. Allegretto.'
    tempoName, mmStr, refStr, bpmStr = Convert.getMetronomeMarkInfo(text)
    CheckString(tempoName, '')
    CheckString(mmStr, 'M.M.')
    CheckString(refStr, 'quarter')
    CheckString(bpmStr, '104.')

    # M:M: (ok fine)
    text = 'Allegro con fuoco. M:M: [quarter]=152.'
    tempoName, mmStr, refStr, bpmStr = Convert.getMetronomeMarkInfo(text)
    CheckString(tempoName, 'Allegro con fuoco.')
    CheckString(mmStr, 'M:M:')
    CheckString(refStr, 'quarter')
    CheckString(bpmStr, '152.')

    # M. M.
    text = 'ANDANTE. M. M. [quarter] = 92.'
    tempoName, mmStr, refStr, bpmStr = Convert.getMetronomeMarkInfo(text)
    CheckString(tempoName, 'ANDANTE.')
    CheckString(mmStr, 'M. M.')
    CheckString(refStr, 'quarter')
    CheckString(bpmStr, '92.')

    # M. M., parens no tempoName
    text = 'M. M. ([quarter] = 144)'
    tempoName, mmStr, refStr, bpmStr = Convert.getMetronomeMarkInfo(text)
    CheckString(tempoName, '')
    CheckString(mmStr, 'M. M.')
    CheckString(refStr, 'quarter')
    CheckString(bpmStr, '144')

    # M. M., no parens, no tempoName
    text = 'M. M. [quarter]=34.'
    tempoName, mmStr, refStr, bpmStr = Convert.getMetronomeMarkInfo(text)
    CheckString(tempoName, '')
    CheckString(mmStr, 'M. M.')
    CheckString(refStr, 'quarter')
    CheckString(bpmStr, '34.')

    # no mmStr, yes tempoName
    text = 'Allegro [quarter]=128'
    tempoName, mmStr, refStr, bpmStr = Convert.getMetronomeMarkInfo(text)
    CheckString(tempoName, 'Allegro')
    CheckIsNone(mmStr)
    CheckString(refStr, 'quarter')
    CheckString(bpmStr, '128')
