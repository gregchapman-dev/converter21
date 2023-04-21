# ------------------------------------------------------------------------------
# Name:          HumHash.py
# Purpose:       A dictionary (with three levels of keys: namespace1, namespace2, key).
#                Each HumdrumToken, HumdrumLine, and HumdrumFile is derived from (has a)
#                HumHash, to hold the interesting info we have analyzed about that object.
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------

import typing as t

from music21 import Music21Object
from music21.common import opFrac
from music21.common import OffsetQL

from converter21.humdrum import HumdrumInternalError

def getKeyTuple(inKey: str) -> tuple[str, str, str]:
    keyList: list[str] = inKey.split(':')
    if len(keyList) == 1:
        return ('', '', keyList[0])

    if len(keyList) == 2:
        return ('', keyList[0], keyList[1])

    return (keyList[0], keyList[1], keyList[2])

def fixupNamespace1Namespace2Key(*ns1ns2key: str) -> tuple[str, str, str]:
    if len(ns1ns2key) < 1:
        raise ValueError("too few specifiers (need at least a key)")
    if len(ns1ns2key) > 3:
        raise ValueError("too many specifiers (should be at most 3: ns1, ns2, key)")

    ns1 = ''
    ns2 = ''

    if len(ns1ns2key) == 1:
        key = ns1ns2key[0]
    elif len(ns1ns2key) == 2:
        ns2 = ns1ns2key[0]
        key = ns1ns2key[1]
    else:  # len(ns1ns2key) == 3
        ns1 = ns1ns2key[0]
        ns2 = ns1ns2key[1]
        key = ns1ns2key[2]

    # If ns1 and ns2 are not specified, key might have colon-delimited
    # namespaces in it, so we need to parse them out.
    if ns1 == '' and ns2 == '':
        ns1, ns2, key = getKeyTuple(key)

    # We support single level namespace key/value pairs that have either
    # ns1 == '' or ns2 == '' as equivalent. In other words, they both will
    # land in {'', {singleNS, {key, value}}}.
    if ns2 == '' and ns1 != '':
        # swap them, for equivalency (make ns1 the empty string instead of ns2)
        ns1, ns2 = ns2, ns1

    return (ns1, ns2, key)

def fixupNamespace1Namespace2(
        ns1: str | None = None,
        ns2: str | None = None
) -> tuple[str | None, str | None]:
    if ns1 is None and ns2 is not None:
        ns1, ns2 = ns2, ns1  # make ns2 be the one that is None, if one of them is

    if ns1 is not None and ns2 is None:
        # check for a colon in ns1 -> generate ns1, ns2 from ns2 in that case
        keyTuple = getKeyTuple(ns1)
        if len(keyTuple) == 2:
            ns1 = keyTuple[0]
            ns2 = keyTuple[1]

    return (ns1, ns2)

class HumParameter:
    def __init__(self, value: t.Any | None, origin=None) -> None:
        # value can be of any type (different from humlib, where it's always a string)
        from converter21.humdrum import HumdrumToken
        if origin is not None and not isinstance(origin, HumdrumToken):
            raise HumdrumInternalError('HumParameter origin must be HumdrumToken | None')
        self._value: t.Any | None = value
        self._origin: HumdrumToken | None = origin

    @property
    def value(self) -> t.Any | None:
        return self._value

    @value.setter
    def value(self, newValue: t.Any | None) -> None:
        self._value = newValue

    @property
    def origin(self):  # -> HumdrumToken | None:
        return self._origin

    @origin.setter
    def origin(self, newOrigin) -> None:  # newOrigin: HumdrumToken | None
        from converter21.humdrum import HumdrumToken
        if newOrigin is not None and not isinstance(newOrigin, HumdrumToken):
            raise HumdrumInternalError('invalid newOrigin')
        self._origin = newOrigin

class HumHash:
    def __init__(self) -> None:
        # {ns1...,{ns2..., {key..., value...}}}
        self._parameters: dict[str, dict[str, dict[str, HumParameter]]] = {}
        self._prefix: str = ''

    '''
    //////////////////////////////
    //
    // HumHash::setPrefix -- initial string to print when using
    //   operator<<.  This is used for including the "!" for local
    //   comments or "!!" for global comments.   The prefix will
    //   remain the same until it is changed.  The default prefix
    //   of the object it the empty string.
    '''
    @property
    def prefix(self) -> str:
        return self._prefix

    @prefix.setter
    def prefix(self, newPrefix: str) -> None:
        self._prefix = newPrefix

    '''
    //////////////////////////////
    //
    // HumHash::setValue -- Set the parameter to the given value,
    //     over-writing any previous value for the parameter.  The
    //     value is any arbitrary string, but preferably does not
    //     include tabs or colons.  If a colon is needed, then specify
    //     as "&colon;" without the quotes.  Values such as integers
    //     fractions and floats can be specified, and these wil be converted
    //     internally into strings (use getValueInt() or getValueFloat()
    //     to recover the original type).
        GregC says: I have redefined this to store the value in its original
        form, and getValueString() if necessary (which might fail and return
        None).  Python (and I) cannot tolerate the HumdrumToken <->
        "HT_<64-bit-pointer>" string conversions, so I disallow that, and
        I hope that storing a reference to the actual HumdrumToken instead
        is a much better choice.
        Q: Perhaps we should store a weak reference to the HumdrumToken value
        Q: instead, to avoid circular references?
    '''
    def setValue(self, *ns1ns2keyvalue) -> None:
        value: t.Any | None = ns1ns2keyvalue[-1]       # value is last
        ns1ns2key = ns1ns2keyvalue[:-1]  # ns1ns2key is all but last
        ns1: str
        ns2: str
        key: str
        ns1, ns2, key = fixupNamespace1Namespace2Key(*ns1ns2key)

        if ns1 not in self._parameters:
            self._parameters[ns1] = dict([(ns2, dict([(key, HumParameter(value))]))])
        elif ns2 not in self._parameters[ns1]:
            self._parameters[ns1][ns2] = dict([(key, HumParameter(value))])
        else:
            self._parameters[ns1][ns2][key] = HumParameter(value)

    '''
    //////////////////////////////
    //
    // HumHash::getValue -- Returns the value specified by the given key.
    //    If there is no colon in the key then return the value for the key
    //    in the default namespaces (NS1="" and NS2="").  If there is one colon,
    //    then the two pieces of the string as NS2 and the key, with NS1="".
    //    If there are two colons, then that specified the complete namespaces/key
    //    address of the value.  The namespaces and key can be specified as
    //    separate parameters in a similar manner to the single-string version.
    //    But in these cases colon concatenation of the namespaces and/or key
    //    are not allowed.
    '''
    def getValue(self, *ns1ns2key) -> t.Any | None:
        if not self._parameters:
            return None

        ns1, ns2, key = fixupNamespace1Namespace2Key(*ns1ns2key)
        if ns1 not in self._parameters:
            return None
        if ns2 not in self._parameters[ns1]:
            return None
        if key not in self._parameters[ns1][ns2]:
            return None

        return self._parameters[ns1][ns2][key].value

    # getValue variants that convert to requested type (might return None if conversion fails)

    def getValueString(self, *ns1ns2key) -> str | None:
        value = self.getValue(*ns1ns2key)
        if value is None:
            return None

        from converter21.humdrum import HumdrumToken
        if isinstance(value, HumdrumToken):
            return None

        if isinstance(value, Music21Object):
            return None

        try:
            return str(value)  # can convert from int, HumNum, Fraction, float, str, etc
        except Exception:
            return None

    def getValueToken(self, *ns1ns2key):  # -> HumdrumToken | None:
        value = self.getValue(*ns1ns2key)
        if value is None:
            return None

        from converter21.humdrum import HumdrumToken
        if isinstance(value, HumdrumToken):
            return value

        return None  # can't convert to anything else

    def getValueM21Object(self, *ns1ns2key) -> Music21Object | None:
        value = self.getValue(*ns1ns2key)
        if value is None:
            return None

        if isinstance(value, Music21Object):
            return value

        return None  # can't convert to anything else

    def getValueInt(self, *ns1ns2key) -> int:
        value = self.getValue(*ns1ns2key)
        if value is None:
            return 0

        from converter21.humdrum import HumdrumToken
        if isinstance(value, HumdrumToken):
            return 0

        try:
            return int(value)  # can convert from int, float, HumNum, Fraction, str
        except Exception:
            return 0

    def getValueHumNum(self, *ns1ns2key) -> OffsetQL:  # -> HumNum:
        value = self.getValue(*ns1ns2key)
        if value is None:
            return opFrac(0)

        from converter21.humdrum import HumdrumToken
        if isinstance(value, HumdrumToken):
            return opFrac(0)

        try:
            return opFrac(value)  # can convert from int, float, Fraction, str
        except Exception:
            return opFrac(0)

    def getValueFloat(self, *ns1ns2key) -> float:
        value = self.getValue(*ns1ns2key)
        if value is None:
            return 0.0

        from converter21.humdrum import HumdrumToken
        if isinstance(value, HumdrumToken):
            return 0.0

        try:
            return float(value)  # can convert from int, HumNum, Fraction, str
        except Exception:
            return 0.0

    def getValueBool(self, *ns1ns2key) -> bool:
        # this one's weird.  We default to True (unless there's some fairly
        # obvious reason to interpret as False, e.g. string == '0', int = 0, etc)
        value = self.getValue(*ns1ns2key)
        if value is None:
            return False

        if isinstance(value, bool):
            return value

        from converter21.humdrum import HumdrumToken
        if isinstance(value, HumdrumToken):
            return True  # it's not None, so...

        if isinstance(value, str):
            if value == 'false':
                return False
            if value == '0':
                return False
            return True

        try:
            return int(value) != 0
        except Exception:
            return True  # it's not None, so...

    '''
    //////////////////////////////
    //
    // HumHash::isDefined -- Returns true if the given parameter exists in the
    //    map.   Format of the input string:   NS1:NS2:key or "":NS2:key for the
    //    two argument version of the function.  OR "":"":key if no colons in
    //    single string argument version.
    '''
    def isDefined(self, *ns1ns2key) -> bool:
        if not self._parameters:
            return False

        ns1, ns2, key = fixupNamespace1Namespace2Key(*ns1ns2key)
        if ns1 not in self._parameters:
            return False
        if ns2 not in self._parameters[ns1]:
            return False

        return key in self._parameters[ns1][ns2]

    '''
    //////////////////////////////
    //
    // HumHash::deleteValue -- Delete the given parameter key from the HumHash
    //   object.  Three string version is N1,NS2,key; two string version is
    //   "",NS2,key; and one argument version is "","",key.
    '''
    def deleteValue(self, *ns1ns2key) -> None:
        if not self._parameters:
            return

        ns1, ns2, key = fixupNamespace1Namespace2Key(*ns1ns2key)

        if ns1 not in self._parameters:
            return

        if ns2 not in self._parameters[ns1]:
            return

        if key in self._parameters[ns1][ns2]:
            del self._parameters[ns1][ns2][key]

    '''
    //////////////////////////////
    //
    // HumHash::setOrigin -- Set the source token for the parameter.
    '''
    def setOrigin(self, *ns1ns2keyvalue):  # origin: HumdrumToken
        if not self._parameters:
            return

        origin = ns1ns2keyvalue[-1]
        ns1ns2key = ns1ns2keyvalue[:-1]
        ns1, ns2, key = fixupNamespace1Namespace2Key(*ns1ns2key)

        from converter21.humdrum import HumdrumToken
        if not isinstance(origin, HumdrumToken):
            raise HumdrumInternalError('invalid origin token in HumHash.setOrigin')

        if ns1 not in self._parameters:
            return

        if ns2 not in self._parameters[ns1]:
            return

        if key not in self._parameters[ns1][ns2]:
            return

        self._parameters[ns1][ns2][key].origin = origin

    '''
    //////////////////////////////
    //
    // HumHash::getOrigin -- Get the source token for the parameter.
    //    Returns NULL if there is no origin.
    '''
    def getOrigin(self, *ns1ns2key):  # -> HumdrumToken:
        if not self._parameters:
            return None

        ns1, ns2, key = fixupNamespace1Namespace2Key(*ns1ns2key)

        if ns1 not in self._parameters:
            return None

        if ns2 not in self._parameters[ns1]:
            return None

        if key not in self._parameters[ns1][ns2]:
            return None

        return self._parameters[ns1][ns2][key].origin

    '''
    //////////////////////////////
    //
    // HumHash::getKeys -- Return a list of keys in a particular namespace
    //     combination.  With no parameters, a complete list of all
    //     namespaces/keys will be returned.  Giving one parameter will
    //     produce a list will give all NS2:key values in the NS1 namespace.
    //     If there is a colon in the single parameter version of the function,
    //     then this will be interpreted as "NS1", "NS2" version of the parameters
    //     described above.
    '''
    def getKeys(self, ns1: str | None = None, ns2: str | None = None) -> list[str]:
        retKeys: list[str] = []
        if not self._parameters:
            # return empty list of keys
            return retKeys

        ns1, ns2 = fixupNamespace1Namespace2(ns1, ns2)

        if ns1 is None and ns2 is None:
            # return all 'namespace1:namespace2:key's in self._parameters
            for my1 in self._parameters:
                for my2 in self._parameters[my1]:
                    for key in self._parameters[my1][my2]:
                        retKeys.append(my1 + ':' + my2 + ':' + key)
            return retKeys

        if ns2 is None:
            # return all 'namespace2:key's in the specified ns1 namespace
            if ns1 in self._parameters:
                for my2 in self._parameters[ns1]:
                    for key in self._parameters[ns1][my2]:
                        retKeys.append(my2 + ':' + key)
            return retKeys

        # return all keys in the specified ns1,ns2 namespace
        if ns1 in self._parameters:
            if ns2 in self._parameters[ns1]:
                for key in self._parameters[ns1][ns2]:
                    retKeys.append(key)
        return retKeys

    '''
    //////////////////////////////
    //
    // HumHash::hasParameters -- Returns true if at least one parameter is defined
    //     in the HumHash object (when no arguments are given to the function).
    //     When two strings are given as arguments, the function checks to see if
    //     the given namespace pair has any keys.  If only one string argument,
    //     then check if the given NS1 has any parameters, unless there is a
    //     colon in the string which means to check NS1:NS2.
    '''
    def hasParameters(self, ns1: str | None = None, ns2: str | None = None) -> bool:
        if not self._parameters:
            # return empty list of keys
            return False

        ns1, ns2 = fixupNamespace1Namespace2(ns1, ns2)

        if ns1 is None and ns2 is None:
            # return whether there are any parameters in self._parameters
            for my1 in self._parameters:
                for my2 in self._parameters[my1]:
                    if self._parameters[my1][my2]:
                        return True
            return False

        if ns2 is None:
            # return whether there are any parameters in the specified ns1 namespace
            if ns1 in self._parameters:
                for my2 in self._parameters[ns1]:
                    if self._parameters[ns1][my2]:
                        return True
            return False

        # return whether there are any parameters in the specified ns1,ns2 namespace
        if ns1 in self._parameters:
            if ns2 in self._parameters[ns1]:
                if self._parameters[ns1][ns2]:
                    return True
        return False

    '''
    //////////////////////////////
    //
    // HumHash::getParameterCount -- Return a count of the parameters which are
    //     stored in the HumHash.  If no arguments, then count all value in
    //     all namespaces.  If two arguments, then return the count for a
    //     specific NS1:NS2 namespace.  If one argument, then return the
    //     parameters in NS1, but if there is a colon in the string,
    //     return the parameters in NS1:NS2.
    //
    '''
    def getParameterCount(self, ns1: str | None = None, ns2: str | None = None) -> int:
        if not self._parameters:
            return 0

        ns1, ns2 = fixupNamespace1Namespace2(ns1, ns2)

        count = 0
        if ns1 is None and ns2 is None:
            # return count of parameters in self._parameters
            for my1 in self._parameters:
                for my2 in self._parameters[my1]:
                    count += len(self._parameters[my1][my2])
            return count

        count = 0
        if ns2 is None:
            # return count of parameters in the specified ns1 namespace
            if ns1 in self._parameters:
                for my2 in self._parameters[ns1]:
                    count += len(self._parameters[ns1][my2])
            return count

        # return count of parameters in the specified ns1,ns2 namespace
        if ns1 in self._parameters:
            if ns2 in self._parameters[ns1]:
                count = len(self._parameters[ns1][ns2])
        return count
