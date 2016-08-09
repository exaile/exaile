# Copyright (C) 2008-2010 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

import time
import re
import unicodedata
import string

__all__ = ['TracksMatcher', 'search_tracks']

class SearchResultTrack(object):
    """
        Holds a track with search result metadata included.

        :param track: The Track object
    """
    __slots__ = ['track', 'on_tags']
    def __init__(self, track):
        self.track = track
        self.on_tags = []

class _Matcher(object):
    """
        Base class for match conditions
    """
    __slots__ = ['tag', 'content', 'lower']
    def __init__(self, tag, content, lower):
        self.tag = tag
        if content and not self.tag.startswith("__"):
            content = lower(content)
        self.content = content
        self.lower = lower

    def match(self, srtrack):
        vals = srtrack.track.get_tag_search(self.tag, format=False)
        if vals == '__null__':
            vals = None
        if self.tag.startswith("__"):
            if self._matches(vals):
                return True
        else:
            if type(vals) != list:
                vals = [vals]
            for item in vals:
                if item is not None:
                    try:
                        item = item.decode('ascii')
                    except:
                        item = shave_marks(item)
                    item = self.lower(item)
                if self._matches(item):
                    return True
        return False

    def _matches(self, value):
        raise NotImplementedError

class _ExactMatcher(_Matcher):
    """
        Condition for exact matches
    """
    def _matches(self, value):
        if self.tag.startswith("__"):
            try:
                newvalue = float(value)
                newcontent = float(self.content)
                return abs(newvalue - newcontent) < 0.0001
            except (TypeError, ValueError):
                newvalue = value
                newcontent = self.content
        else:
            newvalue = value
            newcontent = self.content
        return newvalue == newcontent

class _InMatcher(_Matcher):
    """
        Condition for inexact (ie. containing) matches
    """
    def _matches(self, value):
        if not value:
            return False
        try:
            return self.content in value
        except TypeError:
            return False

class _RegexMatcher(_Matcher):
    """
        Condition for regular expression matches
    """
    def __init__(self, tag, content, lower):
        _Matcher.__init__(self, tag, content, lower)
        self._re = re.compile(content)

    def _matches(self, value):
        if not value:
            return False
        try:
            return self._re.search( value ) is not None
        except TypeError:
            return False

class _GtMatcher(_Matcher):
    """
        Condition for greater than matches.
    """
    def _matches(self, value):
        try:
            value = float(value)
            content = float(self.content) # kinda inefficient
        except (TypeError, ValueError):
            return False
        return value > content

class _LtMatcher(_Matcher):
    """
        Condition for less than matches.
    """
    def _matches(self, value):
        try:
            if value is None:
                value = 0
            else:
                value = float(value)
            content = float(self.content) # kinda inefficient
        except (TypeError, ValueError):
            return False
        return value < content

class _NotMetaMatcher(object):
    """
        Condition for boolean NOT
    """
    __slots__ = ['matcher']
    tag = None
    def __init__(self, matcher):
        self.matcher = matcher

    def match(self, srtrack):
        return not self.matcher.match(srtrack)

class _OrMetaMatcher(object):
    """
        Condition for boolean OR
    """
    __slots__ = ['left', 'right']
    tag = None
    def __init__(self, left, right):
        self.left, self.right = left, right

    def match(self, srtrack):
        return self.left.match(srtrack) or self.right.match(srtrack)

class _MultiMetaMatcher(object):
    """
        Condition for boolean AND
    """
    __slots__ = ['matchers']
    tag = None
    def __init__(self, matchers):
        self.matchers = matchers

    def match(self, srtrack):
        for ma in self.matchers:
            if not ma.match(srtrack):
                return False
        return True

class _ManyMultiMetaMatcher(object):
    """
        TODO: think of a proper docstring for this

        This handles the case where we want to match in an OR-like
        fashion, but also know which tags were matched. Useful for
        the collection panel expansion.
    """
    __slots__ = ['matchers', 'tags']
    tag = None
    def __init__(self, matchers):
        self.matchers = matchers
        self.tags = set()

    def match(self, srtrack):
        self.tags = set()
        matched = False
        for ma in self.matchers:
            if ma.match(srtrack):
                if ma.tag:
                    matched = True
                    self.tags.add(ma.tag)
                elif hasattr(ma, 'tags') and ma.tags:
                    matched = True
                    self.tags.update(ma.tags)
        return matched

class TracksMatcher(object):
    """
        Holds criteria and determines whether
        a given track matches those criteria.
    """
    __slots__ = ['matchers', 'case_sensitive', 'keyword_tags']
    def __init__(self, search_string, case_sensitive=True, keyword_tags=None):
        """
            :param search_string: a string describing the match conditions
            :param case_sensitive: whether to search in a case-sensitive
                manner.
            :param keyword_tags: a list of tags to match search keywords
                in.
        """
        self.case_sensitive = case_sensitive
        self.keyword_tags = keyword_tags or []
        try:
            search_string = search_string.decode('ascii')
        except:
            search_string = shave_marks(search_string)
        tokens = self.__tokenize_query(search_string)
        tokens = self.__red(tokens)
        tokens = self.__optimize_tokens(tokens)
        self.matchers = self.__tokens_to_matchers(tokens)

    def append_matcher(self, matcher, or_match=False):
        '''Here so you can use playlist matchers. Probably needs better impl'''
        if not or_match or len(self.matchers) == 0:
            self.matchers.append(matcher)
        else:
            self.matchers[-1] = _OrMetaMatcher(self.matchers[-1], matcher)

    def prepend_matcher(self, matcher, or_match=False):
        '''Here so you can use playlist matchers. Probably needs better impl'''
        if not or_match or len(self.matchers) == 0:
            self.matchers.insert(0, matcher)
        else:
            self.matchers[0] = _OrMetaMatcher(matcher, self.matchers[0])

    def match(self, srtrack):
        """
            Determine whether a given SearchResultTrack's internal
            Track object matches this search condition.
        """
        for ma in self.matchers:
            if not ma.match(srtrack):
                break
            if ma.tag is not None:
                if ma.tag not in srtrack.on_tags:
                    srtrack.on_tags.append(ma.tag)
            elif hasattr(ma, 'tags'):
                for t in ma.tags:
                    if t not in srtrack.on_tags:
                        srtrack.on_tags.append(t)
        else:
            return True
        return False

    def __tokens_to_matchers(self, tokens, matchers=None):
        """
            Converts a token hierarchy to a list of matchers
        """
        if not matchers:
            matchers = []

        # if there's no more tokens, we're done
        try:
            token = tokens[0]
        except IndexError:
            return matchers

        # is it a special operator?
        if type(token) == list:
            if len(token) == 1:
                token = token[0]
            subtoken = token[0]
            # NOT
            if subtoken == "!":
                nots = self.__tokens_to_matchers(token[1])
                matchers.append(_NotMetaMatcher(_MultiMetaMatcher(nots)))
            # OR
            elif subtoken == "|":
                left = self.__tokens_to_matchers([token[1][0]])
                right = self.__tokens_to_matchers([token[1][1]])
                matchers.append(_OrMetaMatcher(
                    _MultiMetaMatcher(left), _MultiMetaMatcher(right)))
            # ()
            elif subtoken == "(":
                inner = self.__tokens_to_matchers([token[1]])
                matchers.append(_MultiMetaMatcher(inner))
            else:
                return matchers

        elif token == '':
            pass

        # normal token
        else:
            if not self.case_sensitive:
                lower = lambda x: x.lower()
            else:
                lower = lambda x: x

            # TODO: this stuff is kinda repetitive, can we consolidate
            # it? Maybe move some of this into the matcher classes?

            # exact match in tag
            if "==" in token:
                tag, content = token.split("==", 1)
                if content == "__null__":
                    content = None
                matcher = _ExactMatcher(tag, content, lower)
                matchers.append(matcher)

            # keyword in tag
            elif "=" in token:
                tag, content = token.split("=", 1)
                content = content.strip().strip('"')
                matcher = _InMatcher(tag, content, lower)
                matchers.append(matcher)

            elif ">" in token:
                tag, content = token.split(">", 1)
                content = content.strip().strip('"')
                matcher = _GtMatcher(tag, content, lower)
                matchers.append(matcher)

            elif "<" in token:
                tag, content = token.split("<", 1)
                content = content.strip().strip('"')
                matcher = _LtMatcher(tag, content, lower)
                matchers.append(matcher)

            elif "~" in token:
                tag, content = token.split("~", 1)
                content = content.strip().strip('"')
                matcher = _RegexMatcher(tag, content, lower)
                matchers.append(matcher)

            # plain keyword
            else:
                content = token.strip().strip('"')
                mmm = []
                for tag in self.keyword_tags:
                    matcher = _InMatcher(tag, content, lower)
                    mmm.append(matcher)
                matchers.append(_ManyMultiMetaMatcher(mmm))

        return self.__tokens_to_matchers(tokens[1:], matchers)

    def __tokenize_query(self, search):
        """
            Turns a search string into a list of tokens.
        """
        search = " " + search + " "

        tokens = []
        newsearch = ""
        in_quotes = False
        in_regex = False
        n = 0
        while n < len(search):
            c = search[n]
            if c == "\\":
                if not in_regex:
                    n += 1
                try:
                    newsearch += search[n]
                except IndexError:
                    pass
            elif in_quotes and c != "\"":
                newsearch += c
            elif c == "~":
                in_regex = True
                newsearch += c
            elif c == "\"":
                in_quotes = not in_quotes # toggle
                #newsearch += c
            elif c in ["|", "!", "(", ")"]:
                newsearch += c
            elif c == " ":
                in_regex = False
                tokens.append(newsearch)
                newsearch = ""
            else:
                newsearch += c
            n += 1
        return tokens

    def __red(self, tokens):
        """
            Turn the token list into a token list hierarchy that is
            easier to parse.
        """
        # base case since we use recursion
        if tokens == []:
            return []

        # handle parentheses
        elif "(" in tokens:
            num_found = 0
            start = None
            end = None
            count = 0
            for t in tokens:
                if t == "(":
                    if start is None:
                        start = count
                    else:
                        num_found += 1
                elif t == ")":
                    if end is None and num_found == 0:
                        end = count
                    else:
                        num_found -= 1
                if start and end:
                    break
                count += 1
            before = tokens[:start]
            inside = self.__red(tokens[start+1:end])
            after = tokens[end+1:]
            tokens = before + [["(", inside]] + after

        # handle NOT
        elif "!" in tokens:
            start = tokens.index("!")
            end = start+2
            before = tokens[:start]
            inside = tokens[start+1:end]
            after = tokens[end:]
            tokens = before + [["!", inside]] + after

        # handle OR
        elif "|" in tokens:
            start = tokens.index("|")
            inside = [tokens[start-1], tokens[start+1]]
            before = tokens[:start-1]
            after = tokens[start+2:]
            tokens = before + [["|", inside]] + after

        # nothing special, so just return it
        else:
            return tokens

        return self.__red(tokens)

    def __optimize_tokens(self, tokens):
        """
            Attempt to optimize tokens, to speed up matching.
        """
        # longer queries tend to reject more tracks, which speeds up
        # processing, so we put them first.
        tokens.sort(key=len)
        return tokens


class TracksInList(object):
    '''
        Matches tracks contained in a list/dict/set. Copies the list.
    '''

    __slots__ = ['_tracks', 'tag']
    tag = None
    def __init__(self, tracks):
        if isinstance(tracks, dict):
            self._tracks = set(tracks.keys())
        else:
            self._tracks = {t for t in tracks}

    def match(self, track):
        return track.track in self._tracks


class TracksNotInList(TracksInList):
    '''
        Matches tracks not in a list/dict/set
    '''
    def match(self, track):
        return track.track not in self._tracks


def search_tracks(trackiter, trackmatchers):
    """
        Search a set of tracks for those that match specified conditions.

        :param trackiter: An iterable object returning Track objects
        :param trackmatchers: A list of TrackMatcher objects
    """
    for srtr in trackiter:
        if not isinstance(srtr, SearchResultTrack):
            srtr = SearchResultTrack(srtr)
        for tma in trackmatchers:
            if not tma.match(srtr):
                break
        else:
            yield srtr

        # On large collections, searching can take a while. Due to
        # peculiarities in python's GIL that means the now-cpu-bound
        # thread running the search can end up blocking other threads.
        # Calling out to time.sleep forces a release of the GIL and
        # allows other threads to run. Benchmarks show this has no
        # noticable effect on search speed.
        time.sleep(0)


def search_tracks_from_string(trackiter, search_string,
        case_sensitive=True, keyword_tags=None):
    """
        Convenience wrapper around search_tracks that builds matchers
        automatically from the search string.

        Arguments have the same meaning as the corresponding arguments on
        on :class:`search_tracks` and :class:`TracksMatcher`.
    """
    matchers = [TracksMatcher(search_string, case_sensitive=case_sensitive,
        keyword_tags=keyword_tags)]
    return search_tracks(trackiter, matchers)


def match_track_from_string(track, search_string,
        case_sensitive=True, keyword_tags=None):
    matcher = TracksMatcher(search_string, case_sensitive=case_sensitive,
        keyword_tags=keyword_tags)
    return matcher.match(SearchResultTrack(track))


def shave_marks(text):
    '''
    Removes diacritics from Latin characters and replaces them with their base
    characters
    '''
    decomposed_text = unicodedata.normalize('NFD', text)
    latin_base = False
    keepers = []
    for character in decomposed_text:
        if unicodedata.combining(character) and latin_base:
            continue # Ignore diacritic on any Latin base character
        keepers.append(character)
        if not unicodedata.combining(character):
            latin_base = character in string.ascii_letters
    shaved = ''.join(keepers)
    return unicodedata.normalize('NFC', shaved)
