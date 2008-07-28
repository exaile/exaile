# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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

# TrackDB
#
# TrackDB - a track database. basis for playlist, collection
#
# TrackSearcher - fast, advanced method for searching a dictionary of tracks

from xl import common, track, event, xdg

try:
    import cPickle as pickle
except:
    import pickle
from copy import deepcopy
import logging, random, time, os, time
logger = logging.getLogger(__name__)

#FIXME: make these user-customizable
SEARCH_ITEMS = ('artist', 'albumartist', 'album', 'title')
SORT_FALLBACK = ('tracknumber', 'album')



def get_sort_tuple(fields, track):
    """
        Returns the sort tuple for a single track

        fields: the tag(s) to sort by (a single string or iterable of strings)
        track: the track to sort [Track]
    """
    if not type(fields) in (list, tuple):
        items = [track.sort_param(field)]
    else:
        items = [track.sort_param(field) for field in fields]

    for item in ('album', 'track', 'artist', 'title'):
        if track.sort_param(item) not in items:
            items.append(track.sort_param(item))

    items.append(track)
    return tuple(items)

def sort_tracks(fields, tracks, reverse=False):
    """
        Sorts tracks by the field passed

        fields: field(s) to sort by [string] or [list] of strings
        tracks: tracks to sort [list of Track]
        reverse: sort in reverse? [bool]
    """
    tracks = [get_sort_tuple(fields, t) for t in tracks]
    tracks.sort()
    if reverse: tracks.reverse()

    return [t[-1:][0] for t in tracks]

class TrackDB(object):
    """
        Manages a track database. 

        Allows you to add, remove, retrieve, search, save and load
        Track objects.

        This particular implementation is done using storm
    """
    def __init__(self, name='', location="", pickle_attrs=[]):
        """
            Sets up the trackDB.

            @param name:   The name of this TrackDB. [string]
            @param location:   Path to a file where this trackDB
                    should be stored. [string]
            @param pickle_attrs:   A list of attributes to store in the
                    pickled representation of this object. All
                    attributes listed must be built-in types, with
                    one exception: If the object contains the phrase
                    'tracks' in its name it may be a list or dict
                    or Track objects. [list of string]
        """
        self.name = name
        self.location = location
        self._dirty = False
        self.tracks = {}
        self.pickle_attrs = pickle_attrs
        self.pickle_attrs += ['tracks', 'name']
        if location:
            self.load_from_location()

    def set_name(self, name):
        """
            Sets the name of this TrackDB

            name:   The new name. [string]
        """
        self.name = name
        self._dirty = True

    def get_name(self):
        """
            Gets the name of this TrackDB

            returns: The name. [string]
        """
        return self.name

    def set_location(self, location):
        self.location = location
        self._dirty = True

    def load_from_location(self, location=None):
        """
            Restores TrackDB state from the pickled representation
            stored at the specified location.

            @param location: the location to load the data from [string]
        """
        if not location:
            location = self.location
        if not location:
            raise AttributeError("You did not specify a location to save the db")

        pdata = None
        for loc in [location, location+".old", location+".new"]:
            try:
                f = open(loc, 'rb')
                pdata = pickle.load(f)
                f.close()
            except:
                pdata = None
            if pdata:
                break
        if not pdata:
            pdata = dict()

        for attr in self.pickle_attrs:
            try:
                if 'tracks' in attr:
                    if type(pdata[attr]) == list:
                        setattr(self, attr,
                                [ track.Track(_unpickles=x) for x in pdata[attr] ] )
                    elif type(pdata[attr]) == dict:
                        data = pdata[attr]
                        for k, v in data.iteritems():
                            data[k] = track.Track(_unpickles=v)
                        setattr(self, attr, data)
                else:
                    setattr(self, attr, pdata[attr])
            except:
                pass #FIXME

        self._dirty = False 

    def save_to_location(self, location=None):
        """
            Saves a pickled representation of this TrackDB to the 
            specified location.
            
            location: the location to save the data to [string]
        """
        if not self._dirty:
            return

        if not location:
            location = self.location
        if not location:
            raise AttributeError("You did not specify a location to save the db")

        try:
            f = file(location, 'rb')
            pdata = pickle.load(f)
            f.close()
        except:
            pdata = dict()
        for attr in self.pickle_attrs:
            if True:
                # bad hack to allow saving of lists/dicts of Tracks
                if 'tracks' in attr:
                    if type(getattr(self, attr)) == list:
                        pdata[attr] = [ x._pickles() \
                                for x in getattr(self, attr) ]
                    elif type(getattr(self, attr)) == dict:
                        data = deepcopy(getattr(self, attr))
                        for k,v in data.iteritems():
                            data[k] = v._pickles()
                        pdata[attr] = data
                else:
                    pdata[attr] = deepcopy(getattr(self, attr))
            else:
                pass
        try:
            os.remove(location + ".old")
        except:
            pass
        try:
            os.remove(location + ".new")
        except:
            pass
        f = file(location + ".new", 'wb')
        pickle.dump(pdata, f, common.PICKLE_PROTOCOL)
        f.close()
        try:
            os.rename(location, location + ".old")
        except:
            pass # if it doesn'texist we don't care
        os.rename(location + ".new", location)
        try:
            os.remove(location + ".old")
        except:
            pass
        
        self._dirty = False

    def list_tag(self, tag, search_terms="", use_albumartist=False, sort=False):
        """
            lists out all the values for a particular, tag, without duplicates
            
            can also optionally prefer albumartist's value over artist's,
            this is primarily useful for the collection panel
        """
        tset = set()
        for t in self.search(search_terms):
            try:
                for i in t[tag]:
                    tset.add(i)
            except:
                tset.add(t[tag])
        return sorted(list(tset))

    def get_track_by_loc(self, loc, raw=False):
        """
            returns the track having the given loc. if no such
            track exists, returns None
        """
        try:
            return self.tracks[unicode(loc)]
        except KeyError:
            return None

    def get_tracks_by_locs(self, locs):
        """
            returns the track having the given loc. if no such
            track exists, returns None
        """
        return [self.get_track_by_loc(loc) for loc in locs]

    def get_track_attr(self, loc, attr):
        return self.get_track_by_loc(loc)[attr]

    def search(self, query, sort_fields=None, return_lim=-1):
        """
            Search the trackDB, optionally sorting by sort_field

            @param query:  the search
            @param sort_fields:  the field(s) to sort by.  Use RANDOM to sort
                randomly.  A [string] or [list] of strings
            @param return_lim:  limit the number of tracks returned to a
                maximum
        """
        searcher = TrackSearcher()
        tracks = searcher.search(query, self.tracks)

        tracks = tracks.values()

        if sort_fields:
            if sort_fields == 'RANDOM':
                random.shuffle(tracks)
            else:
                tracks = sort_tracks(sort_fields, tracks)
        if return_lim != -1:
            tracks = tracks[:return_lim]

        return tracks

    def loc_is_member(self, loc):
        """
            returns True if loc is a track in this collection, False
            if it is not
        """
        # check to see if it's in one of our libraries, this speeds things
        # up if we have a slow DB
        lib = None
        if hasattr(self, 'libraries'):
            for k, v in self.libraries.iteritems():
                if loc.startswith(k):
                    lib = v
                    return True
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

            track: The Track to add [Track]
        """
        self.add_tracks([track])

    def add_tracks(self, tracks):
        for tr in tracks:
            self.tracks[tr.get_loc()] = tr
            event.log_event("track_added", self, tr.get_loc())
        self._dirty = True 

    def remove(self, track):
        """
            Removes a track from the database

            track: the Track to remove [Track]    
        """
        self.remove_tracks([track])
                
    def remove_tracks(self, tracks):
        for tr in tracks:
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
        search = " " + search.lower() + " "
        tokens = search.split(" ")
        tokens = [t for t in tokens if t != ""]

        # handle "" grouping
        etokens = []
        counter = 0
        while counter < len(tokens):
            if '"' in tokens[counter]:
                tk = tokens[counter]
                while tk.count('"') - tk.count('\\"') < 2:
                    tk += " " + tokens[counter+1]
                    counter += 1
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

            tokens: tokens to optimize [token list]
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

            tokens: the list of tokens to reduce [list of string]
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

            query: the query to search for [string]
            tracks: the dict of tracks to use [dict of tracks]
        """
        tokens = self.tokenize_query(query)
        tracks = self.__do_search(tokens, tracks)
        return tracks

    def __do_search(self, tokens, current_list):
        """ 
            search for tracks by using the parsed tokens 

            tokens: tokens to use when searching [token list]
            current_list: dict of tracks to search [dict of Track]
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
                logger.warning("bad search token")
                return current_list

        # normal token
        else:
            # exact match in tag
            if "==" in token:
                tag, sym, content = token.partition("==")
                content = content.strip().strip('"')
                if content == "NONE":
                    content == None
                for l,tr in current_list.iteritems():
                    try:
                        for t in tr[tag]:
                            if str(t).lower() == content or t == content:
                                new_list[l]=tr
                                break
                    except:
                        pass
            # keyword in tag
            elif "=" in token:
                tag, sym, content = token.partition("=")
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
                tag, sym, content = token.partition(">")
                content = content.strip().strip('"')
                for l,tr in current_list.iteritems():
                    try:
                        if float(content) < float(tr[tag]):
                            new_list[l]=tr
                    except:
                        pass
            # less than
            elif "<" in token:
                tag, sym, content = token.partition("<")
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

