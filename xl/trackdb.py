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

from xl import media, common, track, event, xdg

import logging, random, time, os
logger = logging.getLogger(__name__)

# this overrides storms' sqlite support to handle threading transparently
from lib import storm_threaded

from storm.uri import URI
from storm.locals import *
from storm.expr import Gt, Lt
import storm.properties
from storm.properties import *

try:
    import MySQLdb as mysqldb
except:
    mysqldb = False

SEARCH_ITEMS = ('artist', 'album', 'title')
SORT_FALLBACK = ('tracknumber', 'album')


# we don't use everything in these mappings, but include them for completeness
# List type ommitted as storm docs are not clear on the appropriate mappings
SQLITE_MAPPING = {
        Bool: "INTEGER",
        Int: "INTEGER",
        Float: "FLOAT",
        Decimal: "VARCHAR",
        Unicode: "VARCHAR",
        RawStr: "BLOB",
        Pickle: "BLOB",
        DateTime: "VARCHAR",
        Date: "VARCHAR",
        Time: "VARCHAR",
        TimeDelta: "VARCHAR"}

MYSQL_MAPPING = {
        Bool: "TINYINT",
        Int: "INTEGER",
        Float: "FLOAT",
        Decimal: "DECIMAL",
        Unicode: "TEXT CHARACTER SET utf8",
        RawStr: "BLOB", 
        Pickle: "BLOB",
        DateTime: "DATETIME",
        Date: "DATE",
        Time: "TIME"}

POSTGRESQL_MAPPING = {
        Bool: "BOOL",
        Int: "INTEGER",
        Float: "FLOAT",
        Decimal: "DECIMAL",
        Unicode: "VARCHAR",
        RawStr: "BYTEA",
        Pickle: "BYTEA",
        DateTime: "TIMESTAMP",
        Date: "DATE",
        Time: "TIME",
        TimeDelta: "INTERVAL"}


def get_database_connection(uri):
    dbtype = uri.split(":",1)[0]

    logger.debug("Connecting to database at %s"%uri)
    db = create_database(uri)

    #TODO: make this capable of handling connections to mysql, postgres

    if dbtype == "sqlite":
        attr_mapping = SQLITE_MAPPING
        sql_fields = ["id INTEGER PRIMARY KEY"]
    elif dbtype == "mysql":
        attr_mapping = MYSQL_MAPPING
        sql_fields = ["id INTEGER AUTO_INCREMENT PRIMARY KEY"]
    else:
        attr_mapping = {} #this just fails for eveything, whee!
        sql_fields = []

    # generate the SQL column info
    storm_properties = storm.properties.__dict__.values()
    for k, v in (x for x in track.Track.__dict__.iteritems() if x[0] != "id"):
        try:
            sql = "%s %s"%(k, attr_mapping[type(v)])
            sql_fields.append(sql)
        except KeyError:
            pass

    
    #FIXME: this doesn't handle errors in talking to the db
    store = Store(db)
    try:
        # make db, first run
        if dbtype == "sqlite":
            query = "CREATE TABLE tracks("
        elif dbtype == "mysql":
            dbname = uri.split("/")[-1]
            query = "CREATE TABLE tracks ("
        query += sql_fields[0]
        for item in sql_fields[1:]:
            query += ", \n" + item
        query += ");"
        store.execute(query)
        logger.debug("Created initial DB")
    except:
        # table exists, try adding any fields individually, this handles
        # added fields between versions transparently.
        logger.debug("DB exists, attempting to add any missing fields")
        for item in sql_fields[1:]:
            try:
                query = "ALTER TABLE tracks ADD %s;"%item
                store.execute(query)
                logger.debug("Added missing field \"%s\""%item)
            except:
                pass
    store.commit()

    return db


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
        """
        self.tracks = dict()
        self.name = name
        self.location = location

        self.db = get_database_connection(location)
        self.store = Store(self.db)

    def set_name(self, name):
        """
            Sets the name of this TrackDB

            name:   The new name. [string]
        """
        self._dirty = True
        self.name = name

    def get_name(self):
        """
            Gets the name of this TrackDB

            returns: The name. [string]
        """
        return self.name

    def set_location(self, location):
        pass #FIXME

    def load_from_location(self):
        pass
            
    def save_to_location(self, location=None):
        pass #FIXME

    def add(self, track):
        """
            Adds a track to the database of tracks

            track: The Track to add [Track]
        """
        self.store.add(track)
        event.log_event("track_added", self, track.get_loc())

    def remove(self, track):
        """
            Removes a track from the database

            track: the Track to remove [Track]    
        """
        self.store.remove(track)
        event.log_event("track_removed", self, track.get_loc())

    def list_tag(self, tag, search_terms=None):
        def search(search_terms):
            if search_terms:
                return self.search(search_terms)
            else:
                return self.store.find(track.Track)

        store = self.store

        retset = None
        #FIXME: this code could be clearer
        if tag == "artist":
            albumartists = set(store.find(
                    track.Track).values(track.Track.albumartist))
            if len(albumartists) == 0: #SQL fails on empty list with In
                retset =  set(search(search_terms).values(
                        getattr(track.Track, tag)))
            aaalbums = list(set(store.find(track.Track, 
                    In(track.Track.albumartist, 
                    list(albumartists))).values(track.Track.album)))
            artists = set(store.find(track.Track, Not(In(track.Track.album, 
                    aaalbums))).values(track.Track.artist))
            retset = artists.union(albumartists)
        else:
            retset = set(search(search_terms).values(getattr(track.Track, 
                    tag)))

        return [ x for x in retset ]

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
        tracks = searcher.search_collection(query, self)
        return tracks


class TrackSearcher(object):
    """
        Search a TrackDB for matching tracks
    """ 
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

    def stormize(self, tokens, last_val=None):
        try:
            token = tokens[0]
        except IndexError:
            return last_val
        val = None
        if type(token) == list:
            if len(token) == 1:
                token = token[0]
            subtoken = token[0]
            if subtoken == "!":
                val = Not(self.stormize(token[1]))
            elif subtoken == "|":
                val = Or(self.stormize(token([1][0])), 
                        self.stormize(token([1][1])))
            elif subtoken == "(":
                val = And(self.stormize(token[1]))
            else:
                logger.warning("bad search token")
        else:
            if "==" in token:
                tag, sym, content = token.partition("==")
                content = content.strip().strip('"')
                val = Like(getattr(track.Track, tag), content)
            elif "=" in token:
                tag, sym, content = token.partition("=")
                content = content.strip().strip('"')
                val = Like(getattr(track.Track, tag), "%"+content+"%")
            elif ">" in token:
                tag, sym, content = token.partition("=")
                content = content.strip().strip('"')
                val = Gt(getattr(track.Track, tag), float(content))
            elif "<" in token:
                tag, sym, content = token.partition("=")
                content = content.strip().strip('"')
                val = Lt(getattr(track.Track, tag), float(content))
            else:
                content = token.strip().strip('"')
                l = []
                for item in SEARCH_ITEMS:
                    l.append(Like(getattr(track.Track, item), "%"+content+"%"))
                val = Or(*l)

        if last_val:
            val = And(last_val, val)
        
        return self.stormize(tokens[1:], last_val=val)


    def search_collection(self, query, collection, sort_fields=None, 
            return_lim=-1):
        tokens = self.tokenize_query(query)
        storm_tokens = self.stormize(tokens)
        tracks = collection.store.find(track.Track, storm_tokens)
        return tracks

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


# vim: et sts=4 sw=4

