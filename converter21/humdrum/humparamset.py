# ------------------------------------------------------------------------------
# Name:          HumParamSet.py
# Purpose:       Set of parameters, derived from a single '!LO:'-style comment
#
# Authors:       Greg Chapman <gregc@mac.com>
#                Humdrum code derived/translated from humlib (authored by
#                       Craig Stuart Sapp <craig@ccrma.stanford.edu>)
#
# Copyright:     (c) 2021-2022 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
NAME_IDX = 0
VALUE_IDX = 1
class HumParamSet:
    '''
    //////////////////////////////
    //
    // HumParamSet::HumParamSet --
    '''
    def __init__(self, token = None): # token can be HumdrumToken, or str, or None
        from converter21.humdrum import HumdrumToken
        self._token: HumdrumToken = None
        self._ns1: str = ''
        self._ns2: str = ''
        self._parameters: [[str]] = [] # _parameters is a list of parameters.
                                         # _parameters[i] is a 2-element list of str, ['key', 'value']

        if isinstance(token, str):
            self.readString(token)
        elif isinstance(token, HumdrumToken):
            self._token = token
            self.readString(token.text)

    '''
    //////////////////////////////
    //
    // HumParamSet::getNamespace1 --
    '''
    @property
    def namespace1(self) -> str:
        return self._ns1

    '''
    //////////////////////////////
    //
    // HumParamSet::setNamespace1 --
    '''
    @namespace1.setter
    def namespace1(self, newNS1: str):
        self._ns1 = newNS1

    '''
    //////////////////////////////
    //
    // HumParamSet::getNamespace2 --
    '''
    @property
    def namespace2(self) -> str:
        return self._ns2

    '''
    //////////////////////////////
    //
    // HumParamSet::setNamespace2 --
    '''
    @namespace2.setter
    def namespace2(self, newNS2: str):
        self._ns2 = newNS2

    '''
    //////////////////////////////
    //
    // HumParamSet::getNamespace --
    '''
    @property
    def namespace(self) -> str:
        return self._ns1 + ':' + self._ns2

    '''
    //////////////////////////////
    //
    // HumParamSet::setNamespace --
    '''
    @namespace.setter
    def namespace(self, newNS: str):
        namespaces = newNS.split(':')
        if len(namespaces) == 1:
            self._ns1 = ''
            self._ns2 = namespaces[0]
        else:
            self._ns1 = namespaces[0]
            self._ns2 = namespaces[1]

    '''
    //////////////////////////////
    //
    // HumParamSet::setNamespace --
    '''
    def setNamespace(self, ns1: str, ns2: str):
        self._ns1 = ns1
        self._ns2 = ns2

    '''
    //////////////////////////////
    //
    // HumParamSet::getCount --
    '''
    @property
    def count(self) -> int:
        return len(self._parameters)

    '''
    //////////////////////////////
    //
    // HumParamSet::getParameterName --
    '''
    def getParameterName(self, index: int) -> str:
        if index >= self.count:
            return ''
        if index < 0:
            return ''
        return self._parameters[index][NAME_IDX]

    '''
    //////////////////////////////
    //
    // HumParamSet::getParameterValue --
    '''
    def getParameterValue(self, index: int) -> str:
        if index >= self.count:
            return ''
        if index < 0:
            return ''
        return self._parameters[index][VALUE_IDX]

    '''
    //////////////////////////////
    //
    // HumParamSet::addParameter --
    '''
    def addParameter(self, name: str, value: str) -> int:
        self._parameters.append([name, value])
        return self.count - 1

    '''
    //////////////////////////////
    //
    // HumParamSet::setParameter --
    '''
    def setParameter(self, name: str, value: str) -> int:
        # first try to replace value in place
        for i, param in enumerate(self._parameters):
            if param[NAME_IDX] == name:
                param[VALUE_IDX] = value
                return i

        # Parameter does not exist so create at end of list
        return self.addParameter(name, value)

    '''
    //////////////////////////////
    //
    // HumParamSet::readString --
    '''
    def readString(self, text: str):
        # step over any bangs
        firstNonBang = 0
        for i, ch in enumerate(text):
            if ch == '!':
                continue
            firstNonBang = i
            break

        pieces: [str] = text[firstNonBang:].split(':')

        if len(pieces) < 3:
            return

        for i, piece in enumerate(pieces):
            if i == 0:
                self._ns1 = piece
                continue

            if i == 1:
                self._ns2 = piece
                continue

            piece.replace('&colon;', ':')
            nameValueStrings = piece.split('=', 1) # splits only on first instance of '='
            if len(nameValueStrings) == 1:
                name = nameValueStrings[0]
                value = "true"
            else:
                name = nameValueStrings[0]
                value = nameValueStrings[1]
            self.addParameter(name, value)
