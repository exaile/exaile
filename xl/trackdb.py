# TrackDB
#
# TrackDB - a track database. basis for playlist, collection
#
# TrackSearcher - fast, advanced method for searching a dictionary of tracks

try:
    import cPickle as pickle
except ImportError:
    import pickle

from xl import media, common, track, event
from copy import deepcopy

SEARCH_ITEMS = ('albumartist', 'artist', 'album', 'title')
SORT_ORDER = ('album', 'track', 'artist', 'title')

import logging
logger = logging.getLogger(__name__)

def get_sort_tuple(field, track):
    """
        Returns the sort tuple for a single track

        field: the tag to sort by [string]
        track: the track to sort [Track]
    """
    items = [track[field]]
    for item in SORT_ORDER:
        items.append(track[item])

    items.append(track)
    return tuple(items)

def sort_tracks(field, tracks, reverse=False):
    """
        Sorts tracks by the field passed

        field: field to sort by [string]
        tracks: tracks to sort [list of Track]
        reverse: sort in reverse? [bool]
    """

    #sort_order = [field].extend(SORT_ORDER)
    tracks = [get_sort_tuple(field, t) for t in tracks]
    tracks.sort()
    if reverse: tracks.reverse()

    return [t[-1:][0] for t in tracks]


class TrackDB(object):
    """
        Manages a track database. 

        Allows you to add, remove, retrieve, search, save and load
        Track objects.

        This particular implementation is done using pickle
    """
    def __init__(self, name='', location=None, pickle_attrs=[]):
        """
            Sets up the trackDB.

            name:   The name of this TrackDB. [string]
            location:   Path to a file where this trackDB
                    should be stored. [string]
            pickle_attrs:   A list of attributes to store in the
                    pickled representation of this object. All
                    attributes listed must be built-in types, with
                    one exception: If the object contains the phrase
                    'tracks' in its name it may be a list or dict
                    or Track objects. [list of string]
        """
        self.tracks = dict()
        self.name = name
        self.location = location
        self.pickle_attrs = pickle_attrs
        self.pickle_attrs += ['tracks', 'name']

        if location:
            self.load_from_location(location)

        self.searcher = TrackSearcher(self.tracks)

    def set_name(self, name):
        """
            Sets the name of this TrackDB

            name:   The new name. [string]
        """
        self.name = name

    def get_name(self):
        """
            Gets the name of this TrackDB

            returns: The name. [string]
        """
        return self.name

    def set_location(self, location):
        self.location = location

    def load_from_location(self, location=None):
        """
            Restores TrackDB state from the pickled representation
            stored at the specified location.

            location: the location to load the data from [string]
        """
        if not location:
            location = self.location
        if not location:
            raise AttributeError("You did not specify a location to save the db")

        try:
            f = open(location, 'rb')
            pdata = pickle.load(f)
            f.close()
        except:
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
                pass

    def save_to_location(self, location=None):
        """
            Saves a pickled representation of this TrackDB to the 
            specified location.
            
            location: the location to save the data to [string]
        """
        if not location:
            location = self.location
        if not location:
            raise AttributeError("You did not specify a location to save the db")

        try:
            f = file(location, 'rb')
            pdata = pickle.load(f)
        except:
            pdata = dict()
        for attr in self.pickle_attrs:
            if True:
                # bad hack to allow saving of lists/dicts of Tracks
                if 'tracks' in attr:
                    if type(getattr(self, attr)) == list:
                        pdata[attr] = [ x._pickles() for x in getattr(self, attr) ]
                    elif type(getattr(self, attr)) == dict:
                        data = deepcopy(getattr(self, attr))
                        for k,v in data.iteritems():
                            data[k] = v._pickles()
                        pdata[attr] = data
                else:
                    pdata[attr] = deepcopy(getattr(self, attr))
            else:
                pass
        f = file(location, 'wb')
        pickle.dump(pdata, f, common.PICKLE_PROTOCOL)
        f.close()

    def add(self, track):
        """
            Adds a track to the database of tracks

            track: The Track to add [Track]
        """
        self.tracks[track.get_loc()] = track
        event.log_event("track_added", self, track.get_loc())

    def remove(self, track):
        """
            Removes a track from the database

            track: the Track to remove [Track]    
        """
        if track.get_loc() in self.tracks:
            del self.tracks[track.get_loc()]
            event.log_event("track_removed", self, track.get_loc())

    def search(self, phrase, sort_field=None):
        """
            Search the trackDB, optionally sorting by sort_field
        """
        if phrase != "":
            tracks = self.searcher.search(phrase).values()
        else:
            tracks = self.tracks.values()

        if sort_field:
            tracks = sort_tracks(sort_field, tracks)
        return tracks


class TrackSearcher(object):
    """
        Search a TrackDB for matching tracks
    """
    def __init__(self, tracks=dict()):
        self.tracks = tracks
        self.tokens = None

    def set_tracks(self, tracks):
        """
            Sets the tracks dict to use

            tracks: the dictionary of tracks to use [dict of Track]
        """
        self.tracks = tracks

    def set_query(self, query):
        """
            Set the search query

            query: the query to use [string]
        """
        self.tokens = self.tokenize_query(query)
        
    def tokenize_query(self, search):
        """ 
            tokenizes a search query 
        """
        search = " " + search + " "

        # convert bool ops to symbol
        search = search.replace("|", " | ")
        search = search.replace("!", " ! ")
        search = search.replace("&", " ")
        search = search.replace(" OR ", " | ")
        search = search.replace(" NOT ", " ! ")
        search = search.replace(" AND ", " ")
        search = search.replace("(", " ( ")
        search = search.replace(")", " ) ")

        # ensure spacing is uniform
        replaces = [ 
                ("  "," "),
                (" =","="),
                ("= ","="),
                (" >",">"),
                ("> ",">"),
                (" <","<"),
                ("< ","<") ]
        oldsearch = search
        for pair in replaces:
            while True:
                search = search.replace(pair[0], pair[1])
                if search == oldsearch:
                    break
                else:
                    oldsearch = search

        # split the search into tokens to be parsed
        search = " " + search.lower() + " "
        tokens = search.split(" ")

        # handle "" grouping
        etokens = []
        counter = 0
        while counter < len(tokens):
            if '"' in tokens[counter]:
                tk = tokens[counter]
                while tk.count('"') < 2:
                    tk += " " + tokens[counter+1]
                    counter += 1
                tk.replace('"', "")
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

    def search(self, query, tracks=None):
        """
            executes a search using the passed query and (optionally) 
            the passed tracks

            query: the query to search for [string]
            tracks: the dict of tracks to use [dict of tracks]
        """
        if not tracks:
            tracks = self.tracks
        tokens = self.tokenize_query(query)
        tracks = self.__do_search(tokens, tracks)
        return tracks

    def get_results(self):
        """
            get the results for the stored search query and tracks
        """
        return self.__do_search(self.tokens, self.tracks)

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
                for l,tr in current_list.iteritems():
                    try:
                        if str(tr[tag]).lower() == content:
                            new_list[l]=tr
                    except:
                        pass
            # keyword in tag
            elif "=" in token:
                tag, sym, content = token.partition("=")
                content = content.strip().strip('"')
                for l,tr in current_list.iteritems():
                    try:
                        if content in str(tr[tag]).lower():
                            new_list[l]=tr
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
                            if content in tr[item].lower():
                                new_list[l]=tr
                        except:
                            pass

        return self.__do_search(tokens[1:], new_list)
