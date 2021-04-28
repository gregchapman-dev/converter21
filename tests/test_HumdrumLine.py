import pytest

# The things we're testing
from humdrum.HumdrumLine import *

# test utilities
from tests.Utilities import *

def test_HumdrumLine_default_init():
    line = HumdrumLine()
    CheckHumdrumLine(line)

def test_HumdrumLine_single_exinterp():
    line = HumdrumLine('**kern')
    CheckHumdrumLine(line, expectedLine = '**kern',
                           expectedLineNumber = None,
                           expectedType = LINETYPE_INTERPRETATION,
                           expectedTokenCount = 1,
                           expectedIsExclusiveInterpretation = True,
                           expectedIsManipulator = True,
                           expectedTokens = ['**kern'])

def test_HumdrumLine_manipulators():
    line = HumdrumLine('*\t*^\t*-\t*')
    CheckHumdrumLine(line, expectedLine = '*\t*^\t*-\t*',
                           expectedLineNumber = None,
                           expectedType = LINETYPE_INTERPRETATION,
                           expectedTokenCount = 4,
                           expectedIsExclusiveInterpretation = False,
                           expectedIsManipulator = True,
                           expectedTokens = ['*', '*^', '*-', '*'])

def test_HumdrumLine_barline():
    line = HumdrumLine('=1\t=1\t=1')
    CheckHumdrumLine(line, expectedLine = '=1\t=1\t=1',
                           expectedLineNumber = None,
                           expectedType = LINETYPE_BARLINE,
                           expectedTokenCount = 3,
                           expectedIsExclusiveInterpretation = False,
                           expectedIsManipulator = False,
                           expectedTokens = ['=1', '=1', '=1'])

def test_HumdrumLine_data():
    line = HumdrumLine('4f]\t.\t2D\t(1cc\t.')
    CheckHumdrumLine(line, expectedLine = '4f]\t.\t2D\t(1cc\t.',
                           expectedLineNumber = None,
                           expectedType = LINETYPE_DATA,
                           expectedTokenCount = 5,
                           expectedIsExclusiveInterpretation = False,
                           expectedIsManipulator = False,
                           expectedTokens = ['4f]', '.', '2D', '(1cc', '.'])



# add more tests for coverage...
