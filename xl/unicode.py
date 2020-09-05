'''
    Routines useful for dealing with unicode data
'''

import locale
import logging
import string
import unicodedata

logger = logging.getLogger(__name__)


def shave_marks(text):
    """
    Removes diacritics from Latin characters and replaces them with their
    base characters

    :param text: Some input that will be converted to unicode string
    :returns: unicode string
    """
    text = str(text)
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


def to_unicode(x, encoding='utf-8', errors='strict'):
    """Force getting a unicode string from any object."""
    if isinstance(x, str):
        return x
    elif isinstance(x, bytes):
        return str(x, encoding, errors)
    else:
        return str(x)
