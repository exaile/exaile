# Copyright (C) 2008-2009 Adam Olsen
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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
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

__all__ = ['TracksMatcher', 'search_tracks']

import logging
logger = logging.getLogger(__name__)

class SearchResultTrack(object):
    __slots__ = ['track', 'on_tags']
    def __init__(self, track):
        self.track = track
        self.on_tags = set()

class _Matcher(object):
    __slots__ = ['tag', 'content', 'lower']
    def __init__(self, tag, content, lower):
        self.tag = tag
        self.content = content
        self.lower = lower

    def match(self, srtrack):
        vals = srtrack.track.get_tag_raw(self.tag)
        if type(vals) != list:
            vals = [vals]
        for item in vals:
            try:
                item = self.lower(item)
            except:
                pass
            if self.matches(item):
                return True
        else:
            return False

    def matches(self, value):
        raise NotImplementedError

class _ExactMatcher(_Matcher):
    def matches(self, value):
        return value == self.content

class _InMatcher(_Matcher):
    def matches(self, value):
        if not value: return False
        return self.content in value

class _NotMetaMatcher(object):
    __slots__ = ['matcher']
    tag = None
    def __init__(self, matcher):
        self.matcher = matcher

    def match(self, srtrack):
        return not self.matcher.matches(srtrack)

class _MultiMetaMatcher(object):
    __slots__ = ['matchers']
    tag = None
    def __init__(self, matchers):
        self.matchers = matchers

    def match(self, srtrack):
        for ma in self.matchers:
            if not ma.match(srtrack):
                return False
        return True

class _OrMetaMatcher(object):
    __slots__ = ['left', 'right']
    tag = None
    def __init__(self, left, right):
        self.left, self.right = left, right

    def match(self, srtrack):
        return self.left.matches(srtrack) or self.right.matches(srtrack)

class _ManyMultiMetaMatcher(object):
    __slots__ = ['matchers', 'tags']
    tag = None
    def __init__(self, matchers):
        self.matchers = matchers
        self.tags = []

    def match(self, srtrack):
        self.tags = []
        matched = False
        for ma in self.matchers:
            if ma.match(srtrack):
                if ma.tag:
                    matched = True
                self.tags.append(ma.tag)
        return matched

class TracksMatcher(object):
    __slots__ = ['matchers', 'case_sensitive', 'keyword_tags']
    def __init__(self, searchstring, case_sensitive=True, keyword_tags=[]):
        self.case_sensitive = case_sensitive
        self.keyword_tags = keyword_tags
        tokens = self.__tokenize_query(searchstring)
        tokens = self.__red(tokens)
        tokens = self.__optimize_tokens(tokens)
        self.matchers = self.__tokens_to_matchers(tokens, [])

    def match(self, srtrack):
        for ma in self.matchers:
            if not ma.match(srtrack):
                break
            if ma.tag is not None:
                srtrack.on_tags.add(ma.tag)
            elif hasattr(ma, 'tags'):
                srtrack.on_tags.update(ma.tags)
        else:
            return True
        return False

    def __tokens_to_matchers(self, tokens, matchers):
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
                nots = self.__tokens_to_matchers(token[1], [])
                matchers.append(_NotMetaMatcher(_MultiMetaMatcher(nots)))
            # OR
            elif subtoken == "|":
                left = self.__tokens_to_matchers([token[1][0]], [])
                right = self.__tokens_to_matchers([token[1][1]], [])
                matchers.append(_OrMetaMatcher(
                    _MultiMetaMatcher(left), _MultiMetaMatcher(right)))
            # ()
            elif subtoken == "(":
                inner = self.__tokens_to_matchers([token[1]], [])
                matchers.append(_MultiMetaMatcher(inner))
            else:
                logger.warning("Bad search token")
                return matchers

        elif token == '':
            pass

        # normal token
        else:
            if not self.case_sensitive:
                from string import lower
            else:
                lower = lambda x: x
            # exact match in tag
            if "==" in token:
                tag, content = token.split("==", 1)
                if content == "__null__":
                    content = None
                matcher = _ExactMatcher(tag, lower(content), lower)
                matchers.append(matcher)

            # keyword in tag
            elif "=" in token:
                tag, content = token.split("=", 1)
                content = content.strip().strip('"')
                matcher = _InMatcher(tag, lower(content), lower)
                matchers.append(matcher)

            # plain keyword
            else:
                content = token.strip().strip('"')
                mmm = []
                for tag in self.keyword_tags:
                    matcher = _InMatcher(tag, lower(content), lower)
                    mmm.append(matcher)
                matchers.append(_ManyMultiMetaMatcher(mmm))

        return self.__tokens_to_matchers(tokens[1:], matchers)

    def __tokenize_query(self, search):
        """
            tokenizes a search query
        """
        search = " " + search + " "

        tokens = []
        newsearch = ""
        in_quotes = False
        n = 0
        while n < len(search):
            c = search[n]
            if c == "\\":
                n += 1
                try:
                    newsearch += search[n]
                except IndexError:
                    traceback.print_exc()
            elif in_quotes and c != "\"":
                newsearch += c
            elif c == "\"":
                in_quotes = not in_quotes # toggle
                #newsearch += c
            elif c in ["|", "!", "(", ")"]:
                newsearch += c
            elif c == " ":
                tokens.append(newsearch)
                newsearch = ""
            else:
                newsearch += c
            n += 1


        return tokens

    def __red(self, tokens):
        """
            reduce tokens to a parsable format

            :param tokens: the list of tokens to reduce
            :type tokens: list of string
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
            tokens = before + [["(",inside]] + after

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
            tokens = before + [["|",inside]] + after

        # nothing special, so just return it
        else:
            return tokens

        return self.__red(tokens)

    def __optimize_tokens(self, tokens):
        # longer queries tend to reject more tracks, which speeds up
        # processing, so we put them first.
        tokens.sort(key=len)
        return tokens


def search_tracks(trackiter, trackmatchers):
    for tr in trackiter:
        srtr = SearchResultTrack(tr)
        for tma in trackmatchers:
            if not tma.match(srtr):
                break
        else:
            yield srtr

