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

# Playlist
#
# Playlist - essentially an ordered TrackDB
#
# SmartPlaylist - playlist that auto-populates from a collection
#
# PlaylistManager - playlist persistence manager
#
# also contains functions for saving and loading various playlist formats.

from xl import trackdb, event, xdg, track, collection
from xl.settings import SettingsManager
SettingsManager = SettingsManager.settings
import urllib, random, os, time, cgi

try:
    import cPickle as pickle
except:
    import pickle

try:
    import xml.etree.cElementTree as ETree
except ImportError:
    try:
        import cElementTree as ETree
    except ImportError:
        import elementtree as ETree

from urlparse import urlparse
import logging
logger = logging.getLogger(__name__)

class InvalidPlaylistTypeException(Exception):
    pass

def save_to_m3u(playlist, path):
    """
        Saves a Playlist to an m3u file
    """
    handle = open(path, "w")

    handle.write("#EXTM3U\n")
    if playlist.get_name() != '':
        handle.write("#PLAYLIST: %s\n" % playlist.get_name())

    for track in playlist:
        leng = float(track['length'])
        if leng < 1: 
            leng = -1
        handle.write("#EXTINF:%d,%s\n%s\n" % (leng,
            track['title'], track.get_loc()))

    handle.close()

def import_from_m3u(path):
    handle = open(path, 'r')

    name = os.path.split(path)[-1].replace(".m3u","")
    
    #if not handle.readline().startswith("#EXTM3U"):
    #    return None

    pl = Playlist(name=name)

    current = None
    for line in handle:
        line = line.strip()
        if line == "":
            pass
        elif line.startswith("#Playlist: "):
            pl.set_name(line[12:])
        elif line.startswith("#EXTINF:"):
            current = track.Track()
            len, title = line[9:].split(",", 1)
            len = float(len)
            if len < 1:
                len = 0
            current['title'] = title
            current['length'] = len
        elif line.startswith("#"):
            pass
        else:
            if not current:
                current = track.Track()
            if not os.path.isabs(line):
                line = os.path.join(os.path.dirname(path), line)
            current.set_loc(line)
            current.read_tags()
            pl.add(current)
            current = None

    handle.close()

    return pl

def save_to_pls(playlist, path):
    """
        Saves a Playlist to an pls file
    """
    handle = open(path, "w")
    
    handle.write("[playlist]\n")
    handle.write("NumberOfEntries=%d\n\n" % len(playlist))
    
    count = 1 
    
    for track in playlist:
        handle.write("File%d=%s\n" % (count, track.get_loc()))
        handle.write("Title%d=%s\n" % (count, track['title']))
        if track['length'] < 1:
            handle.write("Length%d=%d\n\n" % (count, -1))
        else:
            handle.write("Length%d=%d\n\n" % (count, float(track['length'])))
        count += 1
    
    handle.write("Version=2")
    handle.close()

def import_from_pls(path, handle=None):
    if not handle: handle = open(path, 'r')

    #PLS doesn't store a name, so assume the filename is the name
    name = os.path.split(path)[-1].replace(".pls","")

    if handle.readline().strip() != '[playlist]':
        return None # not a valid pls playlist

    linedict = {}

    for line in handle:
        newline = line.strip()
        if newline == "":
            continue
        try:
            entry, value = newline.split("=",1)
            linedict[entry.lower()] = value
        except:
            return None

    if not linedict.has_key("version"):
        return None
    if not linedict.has_key("numberofentries"):
        return None

    num = int(linedict["numberofentries"])

    pl = Playlist(name=name)

    for n in range(1,num+1):
        tr = track.Track()
        tr.set_loc(linedict["file%s"%n])
        tr['title'] = linedict["title%s"%n]
        len = float(linedict["length%s"%n])
        if len < 1:
            len = 0
        tr['length'] = len
        tr.read_tags()
        pl.add(tr, ignore_missing_files=False)

    handle.close()

    return pl

    
def save_to_asx(playlist, path):
    """
        Saves a Playlist to an asx file
    """
    handle = open(path, "w")
    
    handle.write("<asx version=\"3.0\">\n")
    if playlist.get_name() == '':
        name = ''
    else:
        name = playlist.get_name()
    handle.write("  <title>%s</title>\n" % name)
    
    for track in playlist:
        handle.write("<entry>\n")
        handle.write("  <title>%s</title>\n" % track['title'])
        handle.write("  <ref href=\"%s\" />\n" % urllib.quote(track.get_loc()))
        handle.write("</entry>\n")
    
    handle.write("</asx>")
    handle.close()
    
def import_from_asx(path):
    tree = ETree.ElementTree(file=open(path))
    tracks = tree.findall("entry")
    name = tree.find("title").text.strip()
    pl = Playlist(name=name)
    for t in tracks:
        tr = track.Track()
        loc = urllib.unquote(t.find("ref").get("href"))
        tr.set_loc(loc)
        tr['title'] = t.find("title").text.strip()
        tr.read_tags()
        pl.add(tr)
    return pl

XSPF_MAPPING = {
        'title': 'title',
        'creator': 'artist',
        'album': 'album',
        'trackNum': 'tracknumber'}
# TODO: support image tag for CoverManager

def save_to_xspf(playlist, path):
    """
        Saves a Playlist to a xspf file
    """
    handle = open(path, "w")
    
    handle.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
    handle.write("<playlist version=\"1\" xmlns=\"http://xspf.org/ns/0/\">\n")
    if playlist.get_name() != '':
        handle.write("  <title>%s</title>\n" % playlist.get_name())
    
    handle.write("  <trackList>\n")
    for track in playlist:
        handle.write("    <track>\n")
        for xs, tag in XSPF_MAPPING.iteritems():
            if track[tag] == u"":
                continue
            handle.write("      <%s>%s</%s>\n" % (xs, track[tag],xs) )
        url = urllib.quote(track.get_loc())
        if urlparse(track.get_loc())[0] == "":
            handle.write("      <location>file://%s</location>\n" % url)
        else:
            handle.write("      <location>%s</location>\n" % url)
        handle.write("    </track>\n")
    
    handle.write("  </trackList>\n")
    handle.write("</playlist>\n")
    handle.close()
    
def import_from_xspf(path):
    #TODO: support content resolution
    tree = ETree.ElementTree(file=open(path))
    ns = "{http://xspf.org/ns/0/}"
    tracks = tree.find("%strackList"%ns).findall("%strack"%ns)
    name = tree.find("%stitle"%ns).text.strip()
    pl = Playlist(name=name)
    for t in tracks:
        tr = track.Track()
        loc = urllib.unquote(t.find("%slocation"%ns).text.strip())
        tr.set_loc(loc)
        for xs, tag in XSPF_MAPPING.iteritems():
            try:
                tr[tag] = t.find("%s%s"%(ns,xs)).text.strip()
            except:
                pass
        tr.read_tags()
        pl.add(tr)
    return pl

def is_valid_playlist(loc):
    """
        Returns whether the file at loc is a valid playlist
        right now determines based on file extension but
        possibly could be extended to actually opening
        the file and determining
    """
    sections = loc.split('.')
    return sections[-1] in ['m3u', 'pls','asx', 'xspf']

def import_playlist(path):
    """
        Determines what type of playlist it is and
        based on that calls the appropriate import
        function
    """
    sections = path.split('.')
    extension = sections[-1]
    if extension == 'm3u':
        return import_from_m3u(path)
    elif extension == 'pls':
        return import_from_pls(path)
    elif extension == 'asx':
        return import_from_asx(path)
    elif extension == 'xspf':
        return import_from_xspf(path)
    else:
        raise InvalidPlaylistTypeException()
    
def export_playlist(playlist, path):
    """
        Exact same as @see import_playlist except 
        it exports
    """
    sections = path.split('.')
    extension = sections[-1]
    if extension == 'm3u':
        return save_to_m3u(playlist, path)
    elif extension == 'pls':
        return save_to_pls(playlist, path)
    elif extension == 'asx':
        return save_to_asx(playlist, path)
    elif extension == 'xspf':
        return save_to_xspf(playlist, path)
    else:
        raise InvalidPlaylistTypeException()
    

class PlaylistIterator(object):
    def __init__(self, pl):
        self.pos = -1
        self.pl = pl
    def __iter__(self):
        return self
    def next(self):
        self.pos+=1
        try:
            return self.pl.ordered_tracks[self.pos]
        except:
            raise StopIteration


class Playlist(object):
    """
        Represents a playlist, which is basically just a TrackDB
        with ordering.
    """
    def __init__(self, name="Playlist"):
        """
            Sets up the Playlist

            Events:
                - tracks_added - Sent when tracks are added
                - tracks_removed - Sent when tracks are removed

            @param name: the name of this playlist [string]
        """
        self._ordered_tracks = []
        self.filtered_tracks = []
        self.filtered = False
        self.current_pos = -1
        self.current_playing = False
        self.random_enabled = False
        self.repeat_enabled = False
        self.dynamic_enabled = False
        self.name = name
        self.tracks_history = []
        self.extra_save_items = ['random_enabled', 'repeat_enabled', 
                'dynamic_enabled', 'current_pos', 'name']

    def get_name(self):
        return self.name

    def set_name(self, name):
        self.name = name

    def get_ordered_tracks(self):
        """
            Returns _ordered_tracks, or filtered tracks if it's been set
        """
        if self.filtered:
            return self.filtered_tracks
        else:   
            return self._ordered_tracks

    def set_ordered_tracks(self, tracks):
        """
            Sets the ordered tracks
        """
        if self.filtered:
            self.filtered_tracks = tracks
        else:
            self._ordered_tracks = tracks

    ordered_tracks = property(get_ordered_tracks,
        set_ordered_tracks)

    def filter(self, keyword):
        """
            Filters the ordered tracks based on a keyword
        """
        if not keyword:
            self.filtered = False
            return self._ordered_tracks
        else:
            self.filtered_tracks = self.search(keyword,
                sort_fields=('artist', 'date', 'album', 'discnumber', 'tracknumber'))
            self.filtered = True
            return self.filtered_tracks

    def __len__(self):
        """
            Returns the length of the playlist.
        """
        return len(self.ordered_tracks)

    def __iter__(self):
        """
            allows "for song in playlist" synatax

            warning: assumes playlist doesn't change while iterating.
            behavior is undefined if playlist changes while iterating.
        """
        return PlaylistIterator(self)

    def add(self, track, location=None, ignore_missing_files = True):
        """
            insert the track into the playlist at the specified
            location (default: append). by default it the track can
            not be found by the os it is not added

            @param ignore_missing_files:
                if true tracks that cannot be found are ignored
            track: the track to add [Track]
            location: the index to insert at [int]
        """
        if os.path.exists(track.get_loc_for_io()) or not ignore_missing_files:
            self.add_tracks([track], location)

    def add_tracks(self, tracks, location=None, add_duplicates=True):
        """
            like add(), but takes a list of tracks instead of a single one

            @param tracks: the tracks to add [list of Track]
            @param location: the index to insert at [int]
            @param add_duplicates: Set to [False] if you wouldn't like to add
                tracks that are already in the playlist
        """
        if not add_duplicates:
            new = []
            for track in tracks:
                if track not in self.get_tracks():
                    new.append(track)
            tracks = new

        if location == None:
            self.ordered_tracks.extend(tracks)
        else:
            self.ordered_tracks = self.ordered_tracks[:location] + \
                    tracks + self.ordered_tracks[location:]
        
        if location != None and location <= self.current_pos:
            self.current_pos += len(tracks)

        event.log_event('tracks_added', self, tracks)

    def remove(self, index):
        """
            removes the track at the specified index from the playlist

            index: the index to remove at [int]
        """
        self.remove_tracks(index, index)

    def index(self, track):
        """
            Gets the index of a specific track
        """
        return self.ordered_tracks.index(track)

    def remove_tracks(self, start, end):
        """
            remove the specified range of tracks from the playlist

            @param start: index to start at [int]
            @param end: index to end at (inclusive) [int]
        """
        end = end + 1
        removed = self.ordered_tracks[start:end]
        self.ordered_tracks = self.ordered_tracks[:start] + \
                self.ordered_tracks[end:]

        if end < self.current_pos:
            self.current_pos -= len(removed)
        elif start <= self.current_pos <= end:
            self.current_pos = start+1

        event.log_event('tracks_removed', self, (start, end, removed))

    def clear(self):
        """
            Clears the playlist of any tracks
        """
        self.remove_tracks(0, len(self))

    def set_tracks(self, tracks):
        """
            Clears the playlist and adds the specified tracks

            @param tracks: the tracks to add
        """
        self.clear()
        self.add_tracks(tracks)

    def get_tracks(self):
        """
            gets the list of tracks in this playlist, in order

            returns: [list of Track]
        """
        return self.ordered_tracks[:]

    def get_current_pos(self):
        """
            gets current playback position, -1 if not playing

            returns: the position [int]
        """
        return self.current_pos

    def set_current_pos(self, pos):
        if pos < len(self.ordered_tracks):
            self.current_pos = pos
        event.log_event('pl_current_changed', self, pos)

    def get_current(self):
        """
            gets the currently-playing Track, or None if no current

            returns: the current track [Track]
        """
        if self.current_pos >= len(self.ordered_tracks) or \
                self.current_pos == -1:
            return None
        else:
            return self.ordered_tracks[self.current_pos]

    def peek(self):
        """
            returns the next track that will be played
        """
        if self.random_enabled:
            return None #peek() is meaningless with random
        nextpos = self.current_pos + 1
        if nextpos >= len(self):
            if self.repeat_enabled:
                nextpos = 0
            else:
                return None # end of playlist
        return self.ordered_tracks[nextpos]

    def next(self):
        """
            moves to the next track in the playlist

            returns: the next track [Track], None if no more tracks
        """
        if self.random_enabled:
            if self.current_pos != -1:
                self.tracks_history.append(self.get_current())
                if self.repeat_enabled and len(self.tracks_history) == \
                        len(self.ordered_tracks):
                    self.tracks_history = []
            if len(self.ordered_tracks) == 1 and \
                    len(self.tracks_history) == 1:
                return None
            
            try:
                next = random.choice([ x for x in self.ordered_tracks \
                    if x not in self.tracks_history])
            except IndexError:
                logger.info(_('Ran out of tracks to shuffle'))
                return None
            self.current_pos = self.ordered_tracks.index(next)            
        else:
            if len(self.ordered_tracks) == 0:
                return None
            self.current_pos += 1

        if self.current_pos >= len(self.ordered_tracks):
            if self.repeat_enabled:
                self.current_pos = 0
            else:
                self.current_pos = -1

        self._dirty = True
        event.log_event('pl_current_changed', self, self.current_pos)
        return self.get_current()

    def prev(self):
        """
            moves to the previous track in the playlist

            returns: the previous track [Track]
        """
        if self.random_enabled:
            try:
                prev = self.tracks_history[-1]
            except:
                return self.get_current()
            self.tracks_history = self.tracks_history[:-1]
            self.current_pos = self.ordered_tracks.index(prev)
        else:
            self.current_pos -= 1
            if self.current_pos < 0:
                if self.repeat_enabled:
                    self.current_pos = len(self.ordered_tracks) - 1
                else:
                    self.current_pos = 0

        self._dirty = True
        event.log_event('pl_current_changed', self, self.current_pos)
        return self.get_current()

    def search(self, phrase, sort_fields=None, return_lim=-1):
        """
            searches the playlist
        """
        searcher = trackdb.TrackSearcher()

        search_db = {}
        for track in self.ordered_tracks:
            search_db[track.get_loc()] = track
        tracks = searcher.search(phrase, search_db)
        tracks = tracks.values()

        if sort_fields:
            if sort_fields == 'RANDOM':
                random.shuffle(tracks)
            else:
                tracks = trackdb.sort_tracks(sort_fields, tracks)
        if return_lim != -1:
            tracks = tracks[:return_lim]

        return tracks

    def toggle_random(self):
        """
            toggle random playback order
        """
        if not self.random_enabled:
            self.tracks_history = []
        self.random_enabled = self.random_enabled == False
        self._dirty = True

    def toggle_repeat(self):
        """
            toggle repeat playback
        """
        self.repeat_enabled = self.repeat_enabled == False
        self._dirty = True

    def toggle_dynamic(self):
        """
            toggle dynamic adding of similar tracks to the playlist
        """
        self.dynamic_enabled = self.repeat_enabled == False
        self._dirty = True

    def set_random(self, value):
        """
            Enables random mode if it isn't already enabled

            @param value: [bool]
        """
        if not self.random_enabled:
            self.tracks_history = []
        self.random_enabled = value
        self._dirty = True

    def set_repeat(self, value):
        """
            Enables repeat mode if it isn't already enabled

            @param value: [bool]
        """
        self.repeat_enabled = value
        self.dirty = True

    def set_dynamic(self, value):
        """
            Enables dynamic mode if it isn't already enabled

            @param value: [bool]
        """
        self.dynamic_enabled = value
        self._dirty = True

    def is_random(self):
        return self.random_enabled

    def is_repeat(self):
        return self.repeat_enabled

    def is_dynamic(self):
        return self.dynamic_enabled

    def __str__(self):
        """
            Returns the name of the playlist
        """
        return "%s: %s" % (type(self), self.name)

    def save_to_location(self, location):
        if os.path.exists(location):
            f = open(location + ".new", "w")
        else:
            f = open(location, "w")
        for tr in self:
            buffer = tr.get_loc()
            # write track metadata
            meta = {}
            items = ('artist', 'album', 'tracknumber', 'title', 'genre')
            for item in items:
                value = tr[item]
                if value is not None: meta[item] = value[0]
            buffer += '\t%s\n' % urllib.urlencode(meta)
            f.write(buffer.encode('utf-8'))

        f.write("EOF\n")
        for item in self.extra_save_items:
            val = getattr(self, item)
            strn = SettingsManager._val_to_str(val)
            f.write("%s=%s\n"%(item,strn))
        f.close()
        if os.path.exists(location + ".new"):
            os.remove(location)
            os.rename(location + ".new", location)

    def load_from_location(self, location):
        f = None
        for loc in [location, location+".new"]:
            try:
                f = open(loc, 'r')
                break
            except:
                pass
        locs = []
        if not f: return
        while True:
            line = f.readline()
            if line == "EOF\n" or line == "":
                break
            locs.append(line.decode('utf-8').strip())
        while True:
            line = f.readline()
            if line == "":
                break
            item, strn = line[:-1].split("=",1)
            val = SettingsManager._str_to_val(strn)
            if hasattr(self, item):
                setattr(self, item, val)
        f.close()

        tracks = []

        for loc in locs:
            meta = None
            if loc.find('\t') > -1:
                (loc, meta) = loc.split('\t')
               
            tr = None
            col = collection.get_collection_by_loc(loc)
            if col:
                tr = col.get_track_by_loc(loc)
            if not tr:
                tr = track.Track(uri=loc)
                if tr.is_local() and not tr._scan_valid:
                    tr = None
            
            # readd meta
            if not tr: continue
            if not tr.is_local() and meta is not None:
                meta = cgi.parse_qs(meta)
                for k, v in meta.iteritems():
                    tr[k] = v[0]

            tracks.append(tr)

        self.ordered_tracks = tracks


class SmartPlaylist(object):
    """ 
        Represents a Smart Playlist.  
        This will query a collection object using a set of parameters

        Simple usage:

        >>> import xl.collection
        >>> col = xl.collection.Collection("Test Collection")
        >>> col.add_library(xl.collection.Library("./tests/data"))
        >>> col.rescan_libraries()
        >>> sp = SmartPlaylist(collection=col)
        >>> sp.add_param("artist", "==", "Delerium")
        >>> p = sp.get_playlist()
        >>> p.get_tracks()[1]['album'][0]
        u'Chimera'
        >>> 
    """
    def __init__(self, name="", collection=None):
        """
            Sets up a smart playlist

            @param collection: a reference to a TrackDB object.
            args: See TrackDB
        """
        self.search_params = []
        self.custom_params = []
        self.collection = collection
        self.or_match = False
        self.track_count = -1
        self.random_sort = False
        self.name = name

    def set_location(self, location):
        pass

    def get_name(self):
        return self.name

    def set_name(self, name):
        self.name = name

    def set_collection(self, collection):
        """
            change the collection backing this playlist

            collection: the collection to use [Collection]
        """
        self.collection = collection

    def set_random_sort(self, sort):
        """ 
            If True, the tracks added during update() will be randomized

            @param sort: bool
        """
        self.random_sort = sort
        self._dirty = True

    def get_random_sort(self):
        """
            Returns True if this playlist will randomly be sorted
        """
        return self.random_sort
    
    def set_return_limit(self, count):
        """
            Sets the max number of tracks to return.  

            @param count:  number of tracks to return.  Set to -1 to return
                all matched
        """
        self.track_count = count
        self._dirty = True

    def get_return_limit(self):
        """
            Returns the track count setting
        """
        return self.track_count

    def set_or_match(self, value):
        """
            Set to True to make this an or match: match any of the parameters

            value: True to match any, False to match all params
        """
        self.or_match = value
        self._dirty = True

    def get_or_match(self):
        """
            Return if this is an any or and playlist
        """
        return self.or_match
        
    def add_param(self, field, op, value, index=-1):
        """
            Adds a search parameter.

            @param field:  The field to operate on. [string]
            @param op:     The operator.  Valid operators are:
                    >,<,>=,<=,=,!=,==,!==,>< (between) [string]
            @param value:  The value to match against [string]
            @param index:  Where to insert the parameter in the search order.  -1 
                    to append [int]
        """
        if index:
            self.search_params.insert(index, [field, op, value])
        else:
            self.search_params.append([field, op, value])
        self._dirty = True

    def set_custom_param(self, param, index=-1):
        """
            Adds an arbitrary search parameter, exposing the full power
            of the new search system to the user.

            param:  the search query to use. [string]
            index:  the index to insert at. default is append [int]
        """
        if index:
            self.search_params.insert(index, param)
        else:
            self.search_params.append(param)
        self._dirty = True

    def remove_param(self, index):
        """
            Removes a parameter at the speficied index
        
            index:  the index of the parameter to remove
        """
        self._dirty = True
        return self.search_params.pop(index)

    def get_playlist(self, collection=None):
        """
            Generates a playlist by querying the collection
            
            @param collection: the collection to search (leave None to search
                        internal ref)
        """
        if not collection:
            collection = self.collection
        if not collection: #if there wasnt one set we might not have one
            return

        search_string = self._create_search_string()
        sort_field = None
        if self.random_sort: 
            sort_field = 'RANDOM'
        else:
            sort_field = ('artist', 'date', 'album', 'discnumber', 'tracknumber', 'title')

        pl = Playlist(name=self.get_name())

        tracks = list(collection.search(search_string, sort_field,
            self.track_count))

        pl.add_tracks(tracks)

        return pl

    def _create_search_string(self):
        """
            Creates a search string based on the internal params
        """

        params = [] # parameter list

        for param in self.search_params:
            if type(param) == str:
                params += [param]
                continue
            (field, op, value) = param
            s = ""
            if op == ">=" or op == "<=":
                s += '( %(field)s%(op)s%(value)s ' \
                    'OR %(field)s==%(value)s )' % \
                    {
                        'field': field,
                        'value': value,
                        'op':    op[0]
                    }
            elif op == "!=" or op == "!==":
                s += 'NOT %(field)s%(op)s"%(value)s"' % \
                    {
                        'field': field,
                        'value': value,
                        'op':    op[1:]
                    }
            elif op == "><":
                s+= '( %(field)s>%(value1)s AND ' \
                    '%(field)s<%(value2)s )' % \
                    {
                        'field':  field,
                        'value1': value[0],
                        'value2': value[1]
                    }
            else:
                s += '%(field)s%(op)s"%(value)s"' % \
                    {
                        'field': field,
                        'value': value,
                        'op':    op
                    }

            params.append(s)

        if self.or_match:
            return ' OR '.join(params)
        else:
            return ' '.join(params)

    def save_to_location(self, location):
        pdata = {}
        for item in ['search_params', 'custom_params', 'or_match',
                'track_count', 'random_sort', 'name']:
            pdata[item] = getattr(self, item)
        f = open(location, 'wb')
        pickle.dump(pdata, f)
        f.close()

    def load_from_location(self, location):
        try:
            f = open(location, 'rb')
            pdata = pickle.load(f)
            f.close()
        except:
            return
        for item in pdata:
            if hasattr(self, item):
                setattr(self, item, pdata[item])


class PlaylistExists(Exception):
    pass

class PlaylistManager(object):
    """
        Manages saving and loading of playlists
    """
    def __init__(self, playlist_dir='playlists', playlist_class=Playlist):
        """
            Initializes the playlist manager

            @param playlist_dir: the data dir to save playlists to
            @param playlist_class: the playlist class to use
        """
        self.playlist_class = playlist_class
        self.playlist_dir = os.path.join(xdg.get_data_dirs()[0],playlist_dir)
        if not os.path.exists(self.playlist_dir):
            os.makedirs(self.playlist_dir)
        self.order_file = os.path.join(self.playlist_dir, 'order_file')
        self.playlists = []

        self.load_names()

    def save_playlist(self, pl, overwrite=False):
        """
            Saves a playlist

            @param pl: the playlist
            @param overwrite: Set to [True] if you wish to overwrite a
                playlist should it happen to already exist
        """
        name = pl.get_name()
        if overwrite or name not in self.playlists:
            pl.save_to_location(os.path.join(self.playlist_dir, pl.get_name()))

            if not name in self.playlists: 
                self.playlists.append(name)
            #self.playlists.sort()
        else:
            raise PlaylistExists

        event.log_event('playlist_added', self, name)

    def remove_playlist(self, name):
        """
            Removes a playlist from the manager, also
            physically deletes its

            @param name: the name of the playlist to remove
        """
        if name in self.playlists:
            try:
                os.remove(os.path.join(self.playlist_dir, name))
            except OSError:
                pass
            self.playlists.remove(name)
            event.log_event('playlist_removed', self, name)
            
    def rename_playlist(self, playlist, new_name):
        """
            Renames the playlist to new_name
        """
        old_name = playlist.get_name()
        if old_name in self.playlists:
            self.remove_playlist(old_name)
            playlist.set_name(new_name)
            self.save_playlist(playlist)

    def load_names(self):
        """
            Loads the names of the playlists from the order file
        """
        if os.path.isfile(self.order_file):
            ordered_playlists = self.load_from_location(self.order_file)
        else:
            ordered_playlists = []
            playlists = os.listdir(self.playlist_dir)
            for playlist in playlists:
                if playlist not in ordered_playlists:
                    ordered_playlists.append(playlist)
        self.playlists = ordered_playlists 

    def get_playlist(self, name):
        """
            Gets a playlist by name

            @param name: the name of the playlist you wish to retrieve
        """
        if name in self.playlists:
            pl = self.playlist_class(name=name)
            pl.load_from_location(os.path.join(self.playlist_dir, name))
            return pl
        else:
            raise ValueError("No such playlist")

    def list_playlists(self):
        """
            Returns all the contained playlist names
        """
        return self.playlists[:]
        
    def move(self, playlist, position, after = True):
        """
            Moves the playlist to where position is
        """
        #Remove the playlist first
        playlist_index = self.playlists.index(playlist)
        self.playlists.pop(playlist_index)
        #insert it now after position
        position_index = self.playlists.index(position)
        if after:
            position_index = position_index + 1
        self.playlists.insert(position_index, playlist)
    
    def save_order(self):
        """
            Saves the order to the order file
        """
        self.save_to_location(self.order_file)
    
    def save_to_location(self, location):
        """
            Saves the names of the playlist to a file that is
            used to restore their order
        """
        if os.path.exists(location):
            f = open(location + ".new", "w")
        else:
            f = open(location, "w")
        for playlist in self.playlists:
            f.write(playlist)
            f.write('\n')

        f.write("EOF\n")
        f.close()
        if os.path.exists(location + ".new"):
            os.remove(location)
            os.rename(location + ".new", location)

    def load_from_location(self, location):
        """
            Loads the names of the playlist from a file.
            Their load order is their view order
            
            @return: a list of the playlist names
        """
        f = None
        for loc in [location, location+".new"]:
            try:
                f = open(loc, 'r')
                break
            except:
                pass
        if f is None:
            return []
        playlists = []
        while True:
            line = f.readline()
            if line == "EOF\n" or line == "":
                break
            playlists.append(line.strip())
        f.close()
        return playlists

# vim: et sts=4 sw=4

