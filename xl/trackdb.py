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

"""
TrackDB

:class:`TrackDB`:
    a track database. basis for playlist, collection

:class:`TrackSearcher`
    fast, advanced method for searching a dictionary of tracks
"""

from xl.nls import gettext as _
from xl import common, track, event, xdg

try:
    import cPickle as pickle
except:
    import pickle

import shelve

from copy import deepcopy
import logging, random, time, os, time
logger = logging.getLogger(__name__)

#FIXME: make these user-customizable
SEARCH_ITEMS = ('artist', 'albumartist', 'album', 'title')
SORT_FALLBACK = ('tracknumber', 'discnumber', 'album')

def get_sort_tuple(fields, track):
    """
        Returns the sort tuple for a single track

        :param fields: the tag(s) to sort by
        :type fields: a single string or iterable of strings
        :param track: the track to sort
        :type track: :class:`xl.track.Track`
    """
    def lower(x):
        if type(x) == type(""):
            return x.lower()
        return x
    items = []
    if not type(fields) in (list, tuple):
        items = [lower(track.sort_param(field))]
    else:
        items = [lower(track.sort_param(field)) for field in fields]

    items.append(track)
    return tuple(items)

def sort_tracks(fields, tracks, reverse=False):
    """
        Sorts tracks by the field passed

        :param fields: field(s) to sort by 
        :type fields: string or list of strings

        :param tracks: tracks to sort 
        :type tracks: list of :class:`xl.track.Track`

        :param reverse: sort in reverse?
        :type reverse: bool
    """
    tracks = [get_sort_tuple(fields, t) for t in tracks]
    tracks.sort(reverse=reverse)
    return [t[-1] for t in tracks]

class TrackHolder(object):
    def __init__(self, track, key, **kwargs):
        self._track = track
        self._key = key
        self._attrs = kwargs

    def __getitem__(self, tag):
        return self._track[tag]

    def __setitem__(self, tag, values):
        self._track[tag] = values


class TrackDB(object):
    """
        Manages a track database. 

        Allows you to add, remove, retrieve, search, save and load
        Track objects.

        :param name:   The name of this TrackDB.
        :type name: string
        :param location:   Path to a file where this trackDB
                should be stored.
        :type location: string
        :param pickle_attrs:   A list of attributes to store in the
                pickled representation of this object. All
                attributes listed must be built-in types, with
                one exception: If the object contains the phrase
                'tracks' in its name it may be a list or dict
                or :class:`xl.track.Track` objects.
        :type pickle_attrs: list of strings
    """
    def __init__(self, name='', location="", pickle_attrs=[]):
        """
            Sets up the trackDB.
        """
        self.name = name
        self.location = location
        self._dirty = False
        self.tracks = {}
        self.pickle_attrs = pickle_attrs
        self.pickle_attrs += ['tracks', 'name', '_key']
        self._saving = False
        self._key = 0
        self._dbversion = 1
        self._deleted_keys = []
        if location:
            self.load_from_location()
            event.timeout_add(300000, self._timeout_save)

    def _timeout_save(self):
        self.save_to_location()
        return True

    def set_name(self, name):
        """
            Sets the name of this :class:`TrackDB`

            :param name:   The new name.
            :type name: string
        """
        self.name = name
        self._dirty = True

    def get_name(self):
        """
            Gets the name of this :class:`TrackDB`

            :return: The name.
            :rtype: string
        """
        return self.name

    def set_location(self, location):
        self.location = location
        self._dirty = True

    @common.synchronized
    def load_from_location(self, location=None):
        """
            Restores :class:`TrackDB` state from the pickled representation
            stored at the specified location.

            :param location: the location to load the data from
            :type location: string
        """
        if not location:
            location = self.location
        if not location:
            raise AttributeError(
                    _("You did not specify a location to load the db from"))

        try:
            pdata = shelve.open(self.location, flag='c', 
                    protocol=common.PICKLE_PROTOCOL)
            if pdata.has_key("_dbversion"):
                if pdata['_dbversion'] > self._dbversion:
                    raise common.VersionError, \
                            "DB was created on a newer Exaile version."
        except common.VersionError:
            raise
        except:
            logger.error(_("Failed to open music DB."))
            return

        for attr in self.pickle_attrs:
            try:
                if 'tracks' == attr:
                    data = {}
                    for k in (x for x in pdata.keys() \
                            if x.startswith("tracks-")):
                        p = pdata[k]
                        tr = track.Track(_unpickles=p[0])
                        data[tr.get_loc()] = TrackHolder(tr, p[1], **p[2])
                    setattr(self, attr, data)
                else:
                    setattr(self, attr, pdata[attr])
            except:
                pass #FIXME

        pdata.close()

        self._dirty = False 

    @common.synchronized
    def save_to_location(self, location=None):
        """
            Saves a pickled representation of this :class:`TrackDB` to the
            specified location.
            
            :param location: the location to save the data to
            :type location: string
        """
        logger.debug(_("Saving %(name)s DB to %(location)s." %
            {'name' : self.name, 'location' : location or self.location}))
        if not self._dirty:
            for k, track in self.tracks.iteritems():
                if track._track._dirty: 
                    self._dirty = True
                    break

        if not self._dirty:
            return

        if not location:
            location = self.location
        if not location:
            raise AttributeError(_("You did not specify a location to save the db"))

        if self._saving: 
            return
        self._saving = True

        try:
            pdata = shelve.open(self.location, flag='c', 
                    protocol=common.PICKLE_PROTOCOL)
            if pdata.has_key("_dbversion"):
                if pdata['_dbversion'] > self._dbversion:
                    raise ValueError, "DB was created on a newer Exaile version."
        except:
            logger.error(_("Failed to open music DB for write."))
            return

        for attr in self.pickle_attrs:
            # bad hack to allow saving of lists/dicts of Tracks
            if 'tracks' == attr:
                for k, track in self.tracks.iteritems():
                    if track._track._dirty or "tracks-%s"%track._key not in pdata:
                        pdata["tracks-%s"%track._key] = (
                                track._track._pickles(),
                                track._key,
                                deepcopy(track._attrs))
            else:
                pdata[attr] = deepcopy(getattr(self, attr))

        pdata['_dbversion'] = self._dbversion

        for key in self._deleted_keys:
            if "tracks-%s"%key in pdata:
                del pdata["tracks-%s"%key]

        pdata.sync()
        pdata.close()
        
        for track in self.tracks.itervalues():
            if track._track._dirty: 
                track._dirty = False

        self._dirty = False
        self._saving = False

    def list_tag(self, tag, search_terms="", use_albumartist=False, 
                 ignore_the=False, sort=False, sort_by=[], reverse=False):
        """
            lists out all the values for a particular, tag, without duplicates
            
            can also optionally prefer albumartist's value over artist's, this
            is primarily useful for the collection panel
        """
        def the_cmp(x, y):
            if isinstance(x, basestring):
                x = x.lower()
                x = common.the_cutter(x)
            if isinstance(y, basestring):
                y = y.lower()
                y = common.the_cutter(y)
            return cmp(x, y)

        if sort_by == []:
            tset = set()

            for t in self.search(search_terms):
                try:
                    for i in t[tag]:
                        tset.add(i)
                except:
                    tset.add(t[tag])

            vals = list(tset)
            if ignore_the:
                cmp_type = the_cmp
            else:
                cmp_type = lambda x,y: cmp(x.lower(), y.lower())
            vals = sorted(vals, cmp=cmp_type)
        else:
            tracks = self.search(search_terms)
            tracks = sort_tracks(sort_by, tracks, reverse)
            count = 1
            while count < len(tracks):
                if tracks[count][tag] == tracks[count-1][tag]:
                    del tracks[count]
                count += 1
            vals = [u" / ".join(x[tag]) for x in tracks if x[tag]]

        return vals

    def get_track_by_loc(self, loc, raw=False):
        """
            returns the track having the given loc. if no such track exists,
            returns None
        """
        try:
            return self.tracks[loc]._track
        except KeyError:
            return None

    def get_tracks_by_locs(self, locs):
        """
            returns the track having the given loc. if no such track exists,
            returns None
        """
        return [self.get_track_by_loc(loc) for loc in locs]

    def get_track_attr(self, loc, attr):
        return self.get_track_by_loc(loc)[attr]

    def search(self, query, sort_fields=None, return_lim=-1, tracks=None, reverse=False):
        """
            Search the trackDB, optionally sorting by sort_field

            :param query:  the search
            :param sort_fields:  the field(s) to sort by.  Use RANDOM to sort
                randomly.
            :type sort_fields: A string or list of strings
            :param return_lim:  limit the number of tracks returned to a
                maximum
        """
        searcher = TrackSearcher()
        if not tracks:
            tracks = self.tracks
        elif type(tracks) == list:
            do_search = {}
            for track in tracks:
                do_search[track.get_loc()] = track
            tracks = do_search
        elif type(tracks) == dict:
            pass
        else:
            raise ValueError

        tracksres = searcher.search(query, tracks)
        tracks = []
        for tr in tracksres.itervalues():
            if hasattr(tr, '_track'):
                #print "GOOD"
                tracks.append(tr._track)
            else:
                #print "BAD"
                tracks.append(tr)

        if sort_fields:
            if sort_fields == 'RANDOM':
                random.shuffle(tracks)
            else:
                tracks = sort_tracks(sort_fields, tracks, reverse)
        if return_lim > 0:
            tracks = tracks[:return_lim]

        return tracks

    def loc_is_member(self, loc):
        """
            Returns True if loc is a track in this collection, False
            if it is not
        """
        # check to see if it's in one of our libraries, this speeds things
        # up if it isn't
        lib = None
        if hasattr(self, 'libraries'):
            for k, v in self.libraries.iteritems():
                if loc.startswith('file://%s' % k):
                    lib = v
            if not lib:
                return False

        # check for the actual track
        if self.get_track_by_loc(loc):
            return True
        else:
            return False

    def get_count(self):
        """
            Returns the number of tracks stored in this database
        """
        count = len(self.tracks)
        return count

    def add(self, track):
        """
            Adds a track to the database of tracks

            :param track: The Track to add 
            :type track: :class:`xl.track.Track`
        """
        self.add_tracks([track])

    @common.synchronized
    def add_tracks(self, tracks):
        for tr in tracks:
            self.tracks[tr.get_loc()] = TrackHolder(tr, self._key)
            self._key += 1
            event.log_event("track_added", self, tr.get_loc())
        self._dirty = True 

    def remove(self, track):
        """
            Removes a track from the database

            :param track: the Track to remove 
            :type track: Track]   
        """
        self.remove_tracks([track])
    
    @common.synchronized            
    def remove_tracks(self, tracks):
        for tr in tracks:
            self._deleted_keys.append(self.tracks[tr.get_loc()]._key)
            del self.tracks[tr.get_loc()]
            event.log_event("track_removed", self, tr.get_loc())
        self._dirty = True
      

class TrackSearcher(object):
    """
        Search a TrackDB for matching tracks
    """ 
    def tokenize_query(self, search):
        """ 
            tokenizes a search query 
        """
        search = " " + search + " "

        search = search.replace(" OR ", " | ")
        search = search.replace(" NOT ", " ! ")

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
                    pass
            elif in_quotes and c != "\"":
                newsearch += c
            elif c == "\"":
                in_quotes = in_quotes == False # toggle
                newsearch += c
            elif c in ["|", "!", "(", ")"]:
                newsearch += " " + c + " "
            elif c == " ":
                try:
                    if search[n+1] != " ":
                        if search[n+1] not in ["=", ">", "<"]:
                            newsearch += " "
                except IndexError:
                    pass
            else:
                newsearch += c
            n += 1


        # split the search into tokens to be parsed
        search = " " + newsearch.lower() + " "
        tokens = search.split(" ")
        tokens = [t for t in tokens if t != ""]

        # handle "" grouping
        etokens = []
        counter = 0
        while counter < len(tokens):
            if '"' in tokens[counter]:
                tk = tokens[counter]
                while tk.count('"') - tk.count('\\"') < 2:
                    try:
                        tk += " " + tokens[counter+1]
                        counter += 1
                    except IndexError: # someone didnt match their "s
                        break
                first = tk.index('"', 0)
                last = first
                while True:
                    try:
                        last = tk.index('"', last+1)
                    except ValueError:
                        break
                tk = tk[:first] + tk[first+1:last] + tk[last+1:]
                etokens.append(tk)
                counter += 1
            else:
                if tokens[counter].strip() is not "":
                    etokens.append(tokens[counter])
                counter += 1
        tokens = etokens

        # reduce tokens to a search tree and optimize it
        tokens = self.__red(tokens)
        tokens = self.__optimize_tokens(tokens)

        return tokens

    def __optimize_tokens(self, tokens):
        """ 
            optimizes token order for fast search 

            :param tokens: tokens to optimize 
            :type tokens: token list
        """
        # only optimizes the top level of tokens, the speed
        # gains from optimizing recursively are usually negligible
        l1 = []
        l2 = []
        l3 = []

        for token in tokens:
            # direct equality is the most reducing so put them first
            if type(token) == str and "=" in token:
                l1.append(token)
            # then other normal keywords
            elif type(token) == str and "=" not in token:
                l2.append(token)
            # then anything else like ! or ()
            else:
                l3.append(token)

        tokens = l1 + l2 + l3
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

    def search(self, query, tracks, sort_order=None):
        """
            executes a search using the passed query and (optionally) 
            the passed tracks

            :param query: the query to search for
            :type query: string
            :param tracks: the dict of tracks to use 
            :type tracks: dict of :class:`xl.track.Track`
        """
        tokens = self.tokenize_query(query)
        tracks = self.__do_search(tokens, tracks)
        return tracks

    def __do_search(self, tokens, current_list):
        """ 
            search for tracks by using the parsed tokens 

            :param tokens: tokens to use when searching 
            :type tokens: token list
            :param current_list: dict of tracks to search 
            :type current_list: dict of Track
        """
        new_list = {}
        # if there's no more tokens, everything matches!
        try:
            token = tokens[0]
        except IndexError:
            return current_list

        # is it a special operator?
        if type(token) == list:
            if len(token) == 1:
                token = token[0]
            subtoken = token[0]
            # NOT
            if subtoken == "!":
                to_remove = self.__do_search(token[1], current_list)
                for l,track in current_list.iteritems():
                    if l not in to_remove:
                        new_list[l]=track
            # OR
            elif subtoken == "|":
                new_list.update(
                        self.__do_search([token[1][0]], current_list))
                new_list.update(
                        self.__do_search([token[1][1]], current_list))
            # ()
            elif subtoken == "(":
                new_list = self.__do_search(token[1], current_list)
            else:
                logger.warning(_("bad search token"))
                return current_list

        # normal token
        else:
            # exact match in tag
            if "==" in token:
                tag, content = token.split("==", 1)
                if content[0] == "\"" and content[-1] == "\"":
                    content = content[1:-1]
                #content = content.strip().strip('"')
                if content == "__null__":
                    content = None
                for l,tr in current_list.iteritems():
                    if content == tr[tag]:
                        new_list[l] = tr
                        continue
                    try:
                        for t in tr[tag]:
                            if str(t).lower() == content or t == content:
                                new_list[l]=tr
                                break
                    except:
                        pass
            # keyword in tag
            elif "=" in token:
                tag, content = token.split("=", 1)
                content = content.strip().strip('"')
                for l,tr in current_list.iteritems():
                    try:
                        for t in tr[tag]:
                            if content in str(t).lower():
                                new_list[l]=tr
                                break
                    except:
                        pass
            # greater than
            elif ">" in token:
                tag, content = token.split(">", 1)
                content = content.strip().strip('"')
                for l,tr in current_list.iteritems():
                    try:
                        if float(content) < float(tr[tag]):
                            new_list[l]=tr
                    except:
                        pass
            # less than
            elif "<" in token:
                tag, content = token.split("<", 1)
                content = content.strip().strip('"')
                for l,tr in current_list.iteritems():
                    try:
                        if float(content) > float(tr[tag]):
                            new_list[l]=tr
                    except:
                        pass
            # plain keyword
            else:
                content = token.strip().strip('"')
                for l,tr in current_list.iteritems():
                    for item in SEARCH_ITEMS:
                        try:
                            for t in tr[item]:
                                if content in t.lower():
                                    new_list[l]=tr
                                    break
                        except:
                            pass

        return self.__do_search(tokens[1:], new_list)


# vim: et sts=4 sw=4

