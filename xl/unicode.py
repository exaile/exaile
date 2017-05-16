'''
    Routines useful for dealing with unicode data
'''

import locale
import unicodedata
import string


def shave_marks(text):
    '''
        Removes diacritics from Latin characters and replaces them with their
        base characters

        :param text: Some input that will be converted to unicode string
        :returns: unicode string
    '''
    text = unicode(text)
    decomposed_text = unicodedata.normalize('NFD', text)

    # Don't look for decomposed characters if there aren't any..
    if decomposed_text == text:
        return text

    keepers = []
    last = ' '
    for character in decomposed_text:
        if unicodedata.combining(character) and last in string.ascii_letters:
            continue  # Ignore diacritic on any Latin base character
        keepers.append(character)
        last = character
    shaved = ''.join(keepers)
    return unicodedata.normalize('NFC', shaved)


def strxfrm(x):
    """Like locale.strxfrm but also supports Unicode.

    This works around a bug in Python 2 causing strxfrm to fail on unicode
    objects that cannot be encoded with sys.getdefaultencoding (ASCII in most
    cases): https://bugs.python.org/issue2481
    """

    if isinstance(x, unicode):
        return locale.strxfrm(x.encode('utf-8', 'replace'))
    return locale.strxfrm(x)


def to_unicode(x, encoding=None, errors='strict'):
    """Force getting a unicode string from any object."""
    # unicode() only accepts "string or buffer", so check the type of x first.
    if isinstance(x, unicode):
        return x
    elif isinstance(x, str):
        if encoding:
            return unicode(x, encoding, errors)
        else:
            return unicode(x, errors=errors)
    else:
        return unicode(x)
