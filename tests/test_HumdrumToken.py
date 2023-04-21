import pytest

# The things we're testing
from converter21.humdrum import HumdrumFile
from converter21.humdrum import HumdrumLine
from converter21.humdrum import *

# Test utilities
from tests.Utilities import *

def test_HumdrumToken_default_init():
    token = HumdrumToken()
    CheckHumdrumToken(token)

def test_HumdrumToken_exinterp_kern():
    token = HumdrumToken('**kern')
    CheckHumdrumToken(token,
                        expectedText='**kern',
                        expectedDataType='', # because there is no owner line or file
                        expectedTokenType=TOKENTYPE_INTERPRETATION,
                        expectedSpecificType=SPECIFICTYPE_EXINTERP,
                        expectedDuration=-1,
                        )

def test_HumdrumToken_global_param():
    hf = HumdrumFile()
    hf.readString(\
'''**kern
*M4/4
=1-
!!LO:CL:x=3
*clefG2
4c
4d
!!LO:N:vis=1:t=this is a colon&colon;:i
.
4e
!!LO:B:i
==
*-''')
    for lineIdx, line in enumerate(hf.lines()):
        #print('line: {}'.format(line.text))
        for tokenIdx, token in enumerate(line.tokens()):
            #print('line[{}]: {}'.format(tokenIdx, token))
            assert tokenIdx == 0 # this file has only one token per line

            if lineIdx == 0:
                # **kern
                CheckHumdrumToken(token,
                                  expectedText='**kern',
                                  expectedDataType='**kern',
                                  expectedTokenType=TOKENTYPE_INTERPRETATION,
                                  expectedSpecificType=SPECIFICTYPE_EXINTERP,
                                  expectedDuration=-1,
                                  )
            elif lineIdx == 1:
                # *M4/4
                CheckHumdrumToken(token,
                                  expectedText='*M4/4',
                                  expectedDataType='**kern',
                                  expectedTokenType=TOKENTYPE_INTERPRETATION,
                                  expectedSpecificType=SPECIFICTYPE_TIMESIGNATURE,
                                  expectedDuration=-1,
                                  )
            elif lineIdx == 2:
                # =1-
                CheckHumdrumToken(token,
                                  expectedText='=1-',
                                  expectedDataType='**kern',
                                  expectedTokenType=TOKENTYPE_BARLINE,
                                  expectedSpecificType=SPECIFICTYPE_NOTHINGSPECIFIC,
                                  expectedDuration=-1,
                                  )
            elif lineIdx == 3:
                # !!LO:CL:x=3
                CheckHumdrumToken(token,
                                  expectedText='!!LO:CL:x=3',
                                  expectedDataType='',
                                  expectedTokenType=TOKENTYPE_GLOBALCOMMENT,
                                  expectedSpecificType=SPECIFICTYPE_NOTHINGSPECIFIC,
                                  expectedDuration=-1,
                                  )
            elif lineIdx == 4:
                # *clefG2
                CheckHumdrumToken(token,
                                  expectedText='*clefG2',
                                  expectedDataType='**kern',
                                  expectedTokenType=TOKENTYPE_INTERPRETATION,
                                  expectedSpecificType=SPECIFICTYPE_CLEF,
                                  expectedDuration=-1,
                                  )
            elif lineIdx == 5:
                # 4c
                CheckHumdrumToken(token,
                                  expectedText='4c',
                                  expectedDataType='**kern',
                                  expectedTokenType=TOKENTYPE_DATA,
                                  expectedSpecificType=SPECIFICTYPE_NOTE,
                                  expectedDuration=1, # one quarter-note
                                  )
            elif lineIdx == 6:
                # 4d
                CheckHumdrumToken(token,
                                  expectedText='4d',
                                  expectedDataType='**kern',
                                  expectedTokenType=TOKENTYPE_DATA,
                                  expectedSpecificType=SPECIFICTYPE_NOTE,
                                  expectedDuration=1,
                                  )
            elif lineIdx == 7:
                # !!LO:N:vis=1:t=this is a colon&colon;:i
                CheckHumdrumToken(token,
                                  expectedText='!!LO:N:vis=1:t=this is a colon&colon;:i',
                                  expectedDataType='',
                                  expectedTokenType=TOKENTYPE_GLOBALCOMMENT,
                                  expectedSpecificType=SPECIFICTYPE_NOTHINGSPECIFIC,
                                  expectedDuration=-1,
                                  )
            elif lineIdx == 8:
                # .
                CheckHumdrumToken(token,
                                  expectedText='.',
                                  expectedDataType='**kern',
                                  expectedTokenType=TOKENTYPE_DATA,
                                  expectedSpecificType=SPECIFICTYPE_NULLDATA,
                                  expectedDuration=-1,
                                  )
            elif lineIdx == 9:
                # 4e
                CheckHumdrumToken(token,
                                  expectedText='4e',
                                  expectedDataType='**kern',
                                  expectedTokenType=TOKENTYPE_DATA,
                                  expectedSpecificType=SPECIFICTYPE_NOTE,
                                  expectedDuration=1,
                                  )
            elif lineIdx == 10:
                # !!LO:B:i
                CheckHumdrumToken(token,
                                  expectedText='!!LO:B:i',
                                  expectedDataType='',
                                  expectedTokenType=TOKENTYPE_GLOBALCOMMENT,
                                  expectedSpecificType=SPECIFICTYPE_NOTHINGSPECIFIC,
                                  expectedDuration=-1,
                                  )
            elif lineIdx == 11:
                # ==
                CheckHumdrumToken(token,
                                  expectedText='==',
                                  expectedDataType='**kern',
                                  expectedTokenType=TOKENTYPE_BARLINE,
                                  expectedSpecificType=SPECIFICTYPE_NOTHINGSPECIFIC,
                                  expectedDuration=-1,
                                  )
            elif lineIdx == 12:
                # *-
                CheckHumdrumToken(token,
                                  expectedText='*-',
                                  expectedDataType='**kern',
                                  expectedTokenType=TOKENTYPE_INTERPRETATION,
                                  expectedSpecificType=SPECIFICTYPE_TERMINATE,
                                  expectedDuration=-1,
                                  )
            else:
                assert False # too many lines in file!
