# ------------------------------------------------------------------------------
# Name:          meiexceptions.py
# Purpose:       Exceptions that can be raised during MEI operations.
#
# Authors:       Greg Chapman <gregc@mac.com>
#
# Copyright:     (c) 2023 Greg Chapman
# License:       MIT, see LICENSE
# ------------------------------------------------------------------------------
class MeiValidityError(Exception):
    '''When there is an otherwise-unspecified validity error that prevents parsing.'''
    pass

class MeiValueError(Exception):
    '''When an attribute has an invalid value.'''
    pass

class MeiAttributeError(Exception):
    '''When an element has an invalid attribute.'''
    pass

class MeiElementError(Exception):
    '''When an element itself is invalid.'''
    pass

class MeiInternalError(Exception):
    '''When an internal assumption is broken.'''
    pass

class MeiExportError(Exception):
    '''When an error occurs while converting to MEI.'''
    pass
