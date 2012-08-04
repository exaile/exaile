#encoding:utf-8

# Copyright (C) 2006 Amit Man <amit.man@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# SentenceSplitter was taken from SentenceSplitter.py
# Copyright (C) 2004  Mickel Grönroos <Mickel.Gronroos@csc.fi>
# licensed under the GNU General Public License version 2 or later.

import config
import locale
import re
import string

class SentenceSplitter(object):
    """The SentenceSplitter class."""

    def __init__(self,
                 loc=config.LOCALE,
                 abbreviations=[],
                 escape=config.ESCAPE):
        """Construct a SentenceSplitter object.

        Parameters:
        1. loc (a string or tuple to feed locale.setlocale()
           (Default: """+str(config.LOCALE)+""")
        2. abbreviations (a "stop list" of abbreviations that should not be
           split)
           (Default: [])
        3. escape (a sequence of tuples to escape punctuation in the stop list)
           (Default: """+str(config.ESCAPE)+""")
        """

        ## Set prerequisites
        self.setLocale(loc)
        self.setAbbreviations(abbreviations)
        self.setEscape(escape)

        ## The regular expression matching sentence boundaries
        self._regexpstring   = ("""([\!\"#\'\(\)\.\?]+) ([\"\'\(\-]*\s?["""+
                                string.uppercase+string.digits+"""])""")
        ## A pattern to go with the regular expression for splitting
        ## a chunk of text into sentences
        self._replacepattern = r"\1\n\2"

        ## Compile the regular expression object
        self._regexpobject   = re.compile(self._regexpstring)

    def setLocale(self, loc):
        """Sets the locale. Parameter must be in the format accepted
        by locale.setlocale()."""
        locale.setlocale(locale.LC_ALL)

    def getLocale(self):
        """Returns the current locale."""
        return locale.getlocale()
    
    def setAbbreviations(self, abbreviations):
        """Sets the abbreviation "stop list", i.e. a list of abbreviations
        that should not trigger a split."""
        self._abbreviations = abbreviations

    def getAbbreviations(self):
        """Returns the "stop list" of abbreviations."""
        try:
            return self._abbreviations
        except:
            return []

    def setEscape(self, escape):
        """Sets the the escape handling, i.e. how the punctuation characters
        in the abbreviation stop list should be escaped before splitting
        and turned back to after splitting. The parameter should be a sequence
        of tuples.
        (Example: escape=[(".", "_PERIOD_"), (":", "_COLON_")]
        """
        self._escape = escape

    def getEscape(self):
        """Returns the current sequence of tuples used for escaping
        punctuation in the abbreviations in the stop list."""
        try:
            return self._escape
        except:
            return []

    def split(self, text):
        """Splits a chunk of text into a list of sentences."""

        ## First "escape" all abbreviations in a rather ugly manner
        for abbrev in self.getAbbreviations():
            if text.count(abbrev):
                for t_escapemapping in self.getEscape():
                    escabbrev = abbrev.replace(t_escapemapping[0],
                                               t_escapemapping[1])
                    text = text.replace(abbrev, escabbrev)
                
        ## Then try doing the replace given the regular expression
        ## and the replace pattern
        sentencestring = self._regexpobject.sub(self._replacepattern, text)

        ## Now "unescape" the abbreviations
        for t_escapemapping in self.getEscape():
            if sentencestring.count(t_escapemapping[1]):
                sentencestring = sentencestring.replace(t_escapemapping[1],
                                                         t_escapemapping[0])

        ## Split sentencestring on newlines and return the list
        return sentencestring.split("\n")

