import pytest

# The things we're testing
import music21 as m21
from converter21.shared import M21Utilities

# test utilities
from tests.Utilities import *

def test_DateSingle():
    string = '///::.11'  # eleven one-hundredths of a second
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedSecond = 0)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '///::') # truncates the 11 milliseconds, so no seconds at all

    string = 'year/month/day/hour:minutes:.11'  # unparseable (but reasonably well-formed)
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    assert dateSingle is None # no elaborate check needed
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '')

    string = '///::11' # 11th second
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedSecond = 11)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '///::11')

    string = '///:11' # 11th minute
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedMinute = 11)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '///:11:') # adds trailing ':'

    string = '///11' # 11 o’clock
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedHour = 11)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '///11::') # adds trailing ':'s

    string = '11' # the year 11 A.D.
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = 11)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = string)

    string = '11/' # the year 11 A.D.
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = 11)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '11') # removes trailing '/'s

    string = '11//' # the year 11 A.D.
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = 11)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '11') # removes trailing '/'s

    string = '11///' # the year 11 A.D.
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = 11)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '11') # removes trailing '/'s

    string = '@11' # the year 11 B.C.E.
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = -11)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = string)

    string = '@11/' # the year 11 B.C.E.
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = -11)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '@11') # removes trailing '/'

    string = '@11//' # the year 11 B.C.E.
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = -11)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '@11') # removes trailing '/'s

    string = '@11///' # the year 11 B.C.E.
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = -11)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '@11') # removes trailing '/'s

    string = '/11' # November
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedMonth = 11)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = string)

    string = '//11' # 11th day of the month
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedDay = 11)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = string)

    # more normal cases (just date, no time)
    string = '1943'
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = 1943)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = string)

    string = '1960/3/22'
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = 1960,
                                   expectedMonth = 3,
                                   expectedDay = 22)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '1960/03/22') # adds leading 0 to month

    string = '@12345/10/31'
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = -12345,
                                   expectedMonth = 10,
                                   expectedDay = 31)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = string)

    # now with some approximations (~ for the whole date, x for a value within the date)
    # and uncertainty (? for the whole date, z for a value within the date)
    string = '~1979/06/01'
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = 1979,
                                   expectedMonth = 6,
                                   expectedDay = 1,
                                   expectedHour = None,
                                   expectedRelevance = 'approximate')
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = string)

    string = '1979x/06z/01z'
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = 1979,
                                   expectedMonth = 6,
                                   expectedDay = 1,
                                   expectedYearError = 'approximate',
                                   expectedMonthError = 'uncertain',
                                   expectedDayError = 'uncertain',
                                   expectedRelevance = 'certain')
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = string)

    string = '1979x/06z/01y' # that 'y' is not a valid error symbol
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    assert dateSingle is None
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '')

    string = '~1979x/06z/01z'
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = 1979,
                                   expectedMonth = 6,
                                   expectedDay = 1,
                                   expectedYearError = 'approximate',
                                   expectedMonthError = 'uncertain',
                                   expectedDayError = 'uncertain',
                                   expectedRelevance = 'approximate')
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = string)

    string = '?1979z/06x/01z'
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = 1979,
                                   expectedMonth = 6,
                                   expectedDay = 1,
                                   expectedYearError = 'uncertain',
                                   expectedMonthError = 'approximate',
                                   expectedDayError = 'uncertain',
                                   expectedRelevance = 'uncertain')
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = string)

    string = '?1979z/06x/01z/17:03:58.999'
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = 1979,
                                   expectedMonth = 6,
                                   expectedDay = 1,
                                   expectedHour = 17,
                                   expectedMinute = 3,
                                   expectedSecond = 58,  # truncated off the 999 milliseconds
                                   expectedYearError = 'uncertain',
                                   expectedMonthError = 'approximate',
                                   expectedDayError = 'uncertain',
                                   expectedRelevance = 'uncertain')
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '?1979z/06x/01z/17:03:58')

    string = '?1979z/06x/01z/17:03:59.999'
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = 1979,
                                   expectedMonth = 6,
                                   expectedDay = 1,
                                   expectedHour = 17,
                                   expectedMinute = 3,
                                   expectedSecond = 59,
                                   expectedYearError = 'uncertain',
                                   expectedMonthError = 'approximate',
                                   expectedDayError = 'uncertain',
                                   expectedRelevance = 'uncertain')
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '?1979z/06x/01z/17:03:59')

    string = '1979z/06x/01z/17x:03z:59.999x'
    dateSingle = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSingle(dateSingle, expectedYear = 1979,
                                   expectedMonth = 6,
                                   expectedDay = 1,
                                   expectedHour = 17,
                                   expectedMinute = 3,
                                   expectedSecond = 59,
                                   expectedYearError = 'uncertain',
                                   expectedMonthError = 'approximate',
                                   expectedDayError = 'uncertain',
                                   expectedHourError = 'approximate',
                                   expectedMinuteError = 'uncertain',
                                   expectedSecondError = 'approximate',
                                   expectedRelevance = 'certain')
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '1979z/06x/01z/17x:03z:59x')

    # test a DateSingle object that was created by hand to be problematic for the writer...
    # We have an invalid yearError, which we should ignore, since it has no associated
    # error symbol ('x' for 'approximate' or 'z' for 'uncertain', but nothing at all for
    # 'what-the-even-heck')
    date = m21.metadata.Date(year=1943, month=7, yearError='what-the-even-heck')
    dateSingle = m21.metadata.DateSingle(date)
    newString: str = M21Utilities.stringFromM21DateObject(dateSingle)
    CheckString(newString, expectedString = '1943/07')

def test_DateRelative():
    # We don't need lots of different date formats here (they're tested in test_DateSingle).
    # Just a few examples of '<' and '>' dates.
    string = '>1979z/06x/01z/17x:03z:59.999x'
    dateRelative = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateRelative(dateRelative, expectedYear = 1979,
                                   expectedMonth = 6,
                                   expectedDay = 1,
                                   expectedHour = 17,
                                   expectedMinute = 3,
                                   expectedSecond = 59,
                                   expectedYearError = 'uncertain',
                                   expectedMonthError = 'approximate',
                                   expectedDayError = 'uncertain',
                                   expectedHourError = 'approximate',
                                   expectedMinuteError = 'uncertain',
                                   expectedSecondError = 'approximate',
                                   expectedRelevance = 'after')
    newString: str = M21Utilities.stringFromM21DateObject(dateRelative)
    CheckString(newString, expectedString = '>1979z/06x/01z/17x:03z:59x')

    string = '<1979z/06x/01z/17x:03z:59.999x'
    dateRelative = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateRelative(dateRelative, expectedYear = 1979,
                                   expectedMonth = 6,
                                   expectedDay = 1,
                                   expectedHour = 17,
                                   expectedMinute = 3,
                                   expectedSecond = 59,
                                   expectedYearError = 'uncertain',
                                   expectedMonthError = 'approximate',
                                   expectedDayError = 'uncertain',
                                   expectedHourError = 'approximate',
                                   expectedMinuteError = 'uncertain',
                                   expectedSecondError = 'approximate',
                                   expectedRelevance = 'prior')
    newString: str = M21Utilities.stringFromM21DateObject(dateRelative)
    CheckString(newString, expectedString = '<1979z/06x/01z/17x:03z:59x')

    # Try one with a '<' in the wrong location to make sure it doesn't parse
    string = '1979</06/01/17:03:56'
    dateRelative = M21Utilities.m21DatePrimitiveFromString(string)
    assert dateRelative is None

    # Try one with a '>' in the wrong location to make sure it doesn't parse
    string = '1979/06/01/17:03:56>'
    dateRelative = M21Utilities.m21DatePrimitiveFromString(string)
    assert dateRelative is None

def test_DateBetween():
    # a few straightforward examples (using both '-' and '^'), then some malformed ones (e.g.
    # 3 dates instead of two, or two dates, one of which is malformed, or 1 date)
    string = '1979/06/01/17:03:56-1979/06/30/17:03:56' # June 1-30, 1979 (timestamps equal)
    dateBetween = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateBetween(dateBetween, expectedYear = 1979,
                                   expectedMonth = 6,
                                   expectedDay = (1, 30),
                                   expectedHour = 17,
                                   expectedMinute = 3,
                                   expectedSecond = 56)
    newString: str = M21Utilities.stringFromM21DateObject(dateBetween)
    CheckString(newString, expectedString = string)

    string = '1979/06/01/17:03:56^1979/06/30/17:03:56' # June 1-30, 1979 (timestamps equal)
    dateBetween = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateBetween(dateBetween, expectedYear = 1979,
                                   expectedMonth = 6,
                                   expectedDay = (1, 30),
                                   expectedHour = 17,
                                   expectedMinute = 3,
                                   expectedSecond = 56)
    newString: str = M21Utilities.stringFromM21DateObject(dateBetween)
    CheckString(newString, expectedString = '1979/06/01/17:03:56-1979/06/30/17:03:56') # ^ -> -

    # this one has a backward range.  Apparently no-one cares...
    string = '1979/06/30/17:03:56-1979/06/01/17:03:56' # June 30-1, 1979 (timestamps equal)
    dateBetween = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateBetween(dateBetween, expectedYear = 1979,
                                   expectedMonth = 6,
                                   expectedDay = (30, 1),
                                   expectedHour = 17,
                                   expectedMinute = 3,
                                   expectedSecond = 56)
    newString: str = M21Utilities.stringFromM21DateObject(dateBetween)
    CheckString(newString, expectedString = string)

    # very simple example
    string = '1942-1943'
    dateBetween = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateBetween(dateBetween, expectedYear = (1942, 1943))
    newString: str = M21Utilities.stringFromM21DateObject(dateBetween)
    CheckString(newString, expectedString = string)

    # very simple bad example (3 dates)
    string = '1942-1943-1944'
    dateBetween = M21Utilities.m21DatePrimitiveFromString(string)
    assert dateBetween is None # should fail because '1943-1944' can't parse as a year number

    # very simple bad example (1 date)
    string = '1942-'
    dateBetween = M21Utilities.m21DatePrimitiveFromString(string)
    assert dateBetween is None # should fail because '' has no numeric date fields in it

def test_DateSelection():
    # a few straightforward examples, then some malformed ones
    string = '1979/06/01/17:03:56|1979/06/30/17:03:56' # June 1 or June 30, 1979 (timestamps equal)
    dateSelection = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSelection(dateSelection, expectedNumDates = 2,
                                   expectedYear = 1979,
                                   expectedMonth = 6,
                                   expectedDay = (1, 30),
                                   expectedHour = 17,
                                   expectedMinute = 3,
                                   expectedSecond = 56)
    newString: str = M21Utilities.stringFromM21DateObject(dateSelection)
    CheckString(newString, expectedString = string)

    # June 1, June 15, or June 30, 1979 (timestamps equal)
    string = '1979/06/01/17:03:56|1979/06/15/17:03:56|1979/06/30/17:03:56'
    dateSelection = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSelection(dateSelection, expectedNumDates = 3,
                                   expectedYear = 1979,
                                   expectedMonth = 6,
                                   expectedDay = (1, 15, 30),
                                   expectedHour = 17,
                                   expectedMinute = 3,
                                   expectedSecond = 56)
    newString: str = M21Utilities.stringFromM21DateObject(dateSelection)
    CheckString(newString, expectedString = string)

    string = '1940 | @100 | 1765 | @10000 | 1960 | 1961|1978|1979| 1995'
    dateSelection = M21Utilities.m21DatePrimitiveFromString(string)
    CheckM21DateSelection(dateSelection, expectedNumDates = 9,
        expectedYear = (1940, -100, 1765, -10000, 1960, 1961, 1978, 1979, 1995) )
    newString: str = M21Utilities.stringFromM21DateObject(dateSelection)
    CheckString(newString, expectedString = '1940|@100|1765|@10000|1960|1961|1978|1979|1995') # no spaces

