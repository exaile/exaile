# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

try:
    import cPickle as pickle
except ImportError:
    import pickle

from xl import media, common, track, event
from copy import deepcopy

SEARCH_ITEMS = ('artist', 'album', 'title')
SORT_ORDER = ('album', 'track', 'artist', 'title')

def get_sort_tuple(field, track):
    """
        Returns the sort tuple for a single track

        @type   field: str
        @param  field: the field to sort by
        @type   track: L{media.Track}
        @param  track: the track from which to retrieve the sort tuple

        @rtype: tuple
        @return: a tuple containing the sortable items for a track
    """

    items = [getattr(track, field)]
    for item in SORT_ORDER:
        items.append(getattr(track, item))

    items.append(track)
    return tuple(items)

def sort_tracks(field, tracks, reverse=False):
    """
        Sorts tracks by the field passed

        @type   field: str
        @param  field: the field to sort by
        @type   tracks: list
        @param  tracks: the tracks to sort
        @type   reverse: bool
        @param  reverse: True to reverse the sort order

        @rtype:  list
        @return: the sorted list of tracks
    """

    sort_order = [field].extend(SORT_ORDER)
    tracks = [get_sort_tuple(field, t) for t in tracks]
    tracks.sort()
    if reverse: tracks.reverse()

    return [t[-1:][0] for t in tracks]


class TrackDB:
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
                    or Track objects. [list of strings]
        """
        self.tracks = dict()
        self.name = name
        self.location = location
        self.pickle_attrs = pickle_attrs
        self.pickle_attrs += ['tracks', 'name']

        if location:
            self.load_from_location(location)

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
                #bad hack
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
            del self.tracks[track]
            event.log_event("track_removed", self, track.get_loc())

    def search(self, keyword, sort_field=None):
        """
            Simple search of the database

            keyword: term to search for [string]
            sort_field: field to sort by [string] #not functional
        """
        kw = keyword.lower()

        tracks = []
        for k, track in self.tracks.iteritems():
            for item in SEARCH_ITEMS:
                v = track[item].lower()
                if v.find(kw) > -1:
                    tracks.append(track)
                    break

        return tracks

    def advanced_search(self, search, sort_field=None):
        """
            Advanced search of the database

            search: the advanced search query [string]
            sort_field: field to sort by [string]
        """
        def tokenize(search):
            """ tokenize a search query """

            # convert bool ops to symbols
            search = search.replace("|", " | ")
            search = search.replace("!", " ! ")
            search = search.replace("&", " & ")
            search = search.replace(" OR ", " | ")
            search = search.replace(" NOT ", " ! ")
            search = search.replace(" AND ", " & ")
            search = search.replace("(", " ( ")
            search = search.replace(")", " ) ")

            replaces = [ ("  ", " "),
                    (" =", "="),
                    ("= ", "=")]
            oldsearch = search
            for pair in replaces:
                while True:
                    search = search.replace(pair[0], pair[1])
                    if search == oldsearch:
                        break
                    else:
                        oldsearch = search

            search = search.lower()
            tokens = search.split(" ")

            etokens = []
            counter = 0
            while counter < len(tokens):
                if '"' in tokens[counter]:
                    tk = tokens[counter] + " " + tokens[counter+1]
                    tk.replace('"', "")
                    etokens.append(tk)
                    counter += 2
                else:
                    if tokens[counter].strip() is not "":
                        etokens.append(tokens[counter])
                    counter += 1
            tokens = etokens

            def red(tokens):
                """ reduce tokens to a parsable format """
                if tokens == []:
                    return []
                elif "(" in tokens:
                    start = tokens.index("(")
                    end = tokens.index(")")
                    before = tokens[:start]
                    inside = red(tokens[start+1:end])
                    after = tokens[end+1:]
                    tokens = before + [["(",inside]] + after
                elif "!" in tokens:
                    start = tokens.index("!")
                    end = start+2
                    before = tokens[:start]
                    inside = tokens[start+1:end]
                    after = tokens[end:]
                    tokens = before + [["!", inside]] + after
                elif "|" in tokens:
                    start = tokens.index("|")
                    inside = [tokens[start-1], tokens[start+1]]
                    before = tokens[:start-1]
                    after = tokens[start+2:]
                    tokens = before + [["|",inside]] + after
                else:
                    return tokens

                return red(tokens)

            return red(tokens)

        def do_search(tokens, current_list):
            """ search for tracks by using the parsed tokens """
            new_list = {}
            try:
                token = tokens[0]
            except IndexError:
                return current_list

            if type(token) == list:
                if len(token) == 1:
                    token = token[0]
                subtoken = token[0]
                if subtoken == "!":
                    to_remove = do_search(token[1], current_list)
                    for l,track in current_list.iteritems():
                        if l not in to_remove:
                            new_list[l]=track
                elif subtoken == "|":
                    new_list.update(do_search([token[1][0]], current_list))
                    new_list.update(do_search([token[1][1]], current_list))
                elif subtoken == "(":
                    new_list = do_search(token[1], current_list)
                else:
                    print "whoops!"
                    return current_list
            else:
                if "==" in token:
                    tag, content = token.split("==")
                    content = content.strip('"')
                    for l,tr in current_list.iteritems():
                        try:
                            if tr[tag].lower() == content:
                                new_list[l]=tr
                        except:
                            pass
                elif "=" in token:
                    tag, content = token.split("=")
                    content = content.strip('"')
                    for l,tr in current_list.iteritems():
                        try:
                            if content in tr[tag].lower():
                                new_list[l]=tr
                        except:
                            pass
                else:
                    content = token.strip('"')
                    for l,tr in current_list.iteritems():
                        for item in SEARCH_ITEMS:
                            try:
                                if content in tr[item].lower():
                                    new_list[l]=tr
                            except:
                                pass

            return do_search(tokens[1:], new_list)

        
        tokens = tokenize(search)
        results = do_search(tokens, self.tracks).values()

        return results

        """
        Search queries could be something like this:

        days artist==flow NOT (album="Complete Best" OR album=OST)

        ==disccetion of example==
        days - general search query, matches any field
        artist==flow - matches only the artist "flow"
        NOT - exclude items that match the following term
        () - parentheses can be used to group terms. without these the
             NOT would only apply to album="Complete Best", with them,
             it applies to everything inside the parentheses.
        album="Complete Best" - matches albums that contain the exact 
             phrase "Complete Best"
        OR - causes results matching the terms on either side to be 
             returned. the default linker for terms is AND.
        album=OST - match albums containing "OST"

        ==other examples==

        artist=("rie fu" afromania) - matches the artists "rie fu" or 
                                      afromania
        

        so, this query would match tracks by the artist "flow", that are 
        in albums not containing "complete best" or "ost", and that 
        contain the phrase "days" is any tag.

        ==list of search operators==

        =
        syntax: <tag>=<phrase>
        effect: match tracks having that phrase contained in that tag
        
        ==
        syntax: <tag>==<phrase>
        effect: match tracks a tag content exactly matching that phrase

        ", '
        syntax: "<word> <word>"
        effect: treat multiple words as one phrase instead of several

        NOT, !
        syntax: NOT <term>
        effect: exclude tracks matching the following term. only affects
                one term after.

        OR, |
        syntax: <term> OR <term>
        effect: include tracks matching either the terms before or after.
                affects only one term before or after.

        AND, &
        syntax: <term> AND <term>
        effect: include tracks matching both the terms before and after.
                affects only one term before or after. This is the default
                if nothing else is specified.

        ()
        syntax: ( <terms> ) or ( <phrases> )
        effect: makes the enclosed terms appear as one term to outside
                operators, or, use to make = or == match more than one
                phrase (eg.  a=(b OR c)  instead of  a=b OR a=c  )
        
        ==misc notes==
        search terms are case-insensitive, but operators are not. thus,
        "or" is a phrase while "OR" is an operator.

        """

