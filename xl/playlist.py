# Playlist
#
# Playlist - essentially an ordered TrackDB
#
# also contains functions for saving and loading various playlist formats.

from xl import trackdb, event, xdg, track
import urllib, random, os
import xml.etree.cElementTree as cETree
from urlparse import urlparse

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
    
    if not handle.readline().startswith("#EXTM3U"):
        return None

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

def import_from_pls(path):
    handle = open(path, 'r')

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
            linedict[entry] = value
        except:
            return None

    if not linedict.has_key("Version"):
        return None
    if not linedict.has_key("NumberOfEntries"):
        return None

    num = int(linedict["NumberOfEntries"])

    pl = Playlist(name=name)

    for n in range(1,num+1):
        tr = track.Track()
        tr.set_loc(linedict["File%s"%n])
        tr['title'] = linedict["Title%s"%n]
        len = float(linedict["Length%s"%n])
        if len < 1:
            len = 0
        tr['length'] = len
        tr.read_tags()
        pl.add(tr)

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
    tree = cETree.ElementTree(file=open(path))
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
            if track[tag] == "":
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
    tree = cETree.ElementTree(file=open(path))
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


class Playlist(trackdb.TrackDB):
    """
        Represents a playlist, which is basically just a TrackDB
        with ordering.
    """
    def __init__(self, name="", location=None, pickle_attrs=[]):
        """
            Sets up the Playlist

            args: see TrackDB
        """
        self.ordered_tracks = []
        self.current_pos = -1
        self.current_playing = False
        self.random_enabled = False
        self.repeat_enabled = False
        self.tracks_history = []
        pickle_attrs += ['name', 'ordered_tracks', 'current_pos', 
                'current_playing', "repeat_enabled", "random_enabled",
                'tracks_history']
        trackdb.TrackDB.__init__(self, name=name, location=location,
                pickle_attrs=pickle_attrs)

    def __len__(self):
        """
            Returns the lengh of the playlist.
        """
        return len(self.ordered_tracks)

    def __iter__(self):
        """
            allows "for song in playlist" synatax

            warning: assumes playlist doesn't change while iterating
        """
        return PlaylistIterator(self)

    def add(self, track, location=None):
        """
            insert the track into the playlist at the specified
            location (default: append)

            track: the track to add [Track]
            location: the index to insert at [int]
        """
        self.add_tracks([track], location)

    def add_tracks(self, tracks, location=None):
        """
            like add(), but takes a list of tracks instead of a single one

            tracks: the tracks to add [list of Track]
            location: the index to insert at [int]
        """
        if location == None:
            self.ordered_tracks.extend(tracks)
        else:
            self.ordered_tracks = self.ordered_tracks[:location] + \
                    tracks + self.ordered_tracks[location:]
        for t in tracks:
            trackdb.TrackDB.add(self, t)
        
        if location >= self.current_pos:
            self.current_pos += len(tracks)

    def remove(self, index):
        """
            removes the track at the specified index from the playlist

            index: the index to remove at [int]
        """
        self.remove_tracks(index, index)

    def remove_tracks(self, start, end):
        """
            remove the specified range of tracks from the playlist

            start: index to start at [int]
            end: index to end at (inclusive) [int]
        """
        end = end + 1
        removed = self.ordered_tracks[start:end]
        self.ordered_tracks = self.ordered_tracks[:start] + \
                self.ordered_tracks[end:]
        for t in removed:
            trackdb.TrackDB.remove(self, t)

        if end < self.current_pos:
            self.current_pos -= len(removed)
        elif start <= self.current_pos <= end:
            self.current_pos = start+1

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
        event.log_event('current_changed', self, pos)

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
            
            next = random.choice([ x for x in self.ordered_tracks \
                    if x not in self.tracks_history])
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

        event.log_event('current_changed', self, self.current_pos)
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

        event.log_event('current_changed', self, self.current_pos)
        return self.get_current()

    def search(self, phrase, sort_field=None):
        """
            searches the playlist
        """
        tracks = trackdb.TrackDB.search(self, phrase, sort_field)
        if sort_field is None:
            from copy import deepcopy
            new_tracks = []
            for tr in self.ordered_tracks:
                if tr in tracks:
                    new_tracks.append(tr)
            tracks = new_tracks
        return tracks

    def toggle_random(self, mode=None):
        """
            toggle random playback order

            mode: set random to this [bool]
        """
        if not self.random_enabled:
            self.tracks_history = []
        if mode is not None:
            self.random_enabled = mode
        else:
            self.random_enabled = self.random_enabled == False

    def toggle_repeat(self, mode=None):
        """
            toggle repeat playback

            mode: set repeat to this [bool]
        """
        if mode is not None:
            self.repeat_enabled = mode
        else:
            self.repeat_enabled = self.repeat_enabled == False


####
## Dynamic playlists.
## Aren:  I'm not sure if this is how you wanted to do this.  I'm only adding
## it here temporarily so I can create an entire library playlist easily and
## set it on shuffle :)
class EntireLibraryPlaylist(Playlist):
    """
        Dynamic playlist.  Loads entire library
    """
    def __init__(self, name="", location=None, collection=None,
        pickle_attrs=[]):
        """
            Initializes the playlist

            @param name:    the name of the playlist
            @param location: the location of the playlist
            @param collection: the collection to load.  REQUIRED for this
                dynamic playlist
            @param pickle_attrs: internal
        """
        if not collection:
            raise AttributeError("You must specify a collection!")
        
        Playlist.__init__(self, name=name, location=location,
            pickle_attrs=pickle_attrs)
        self.collection = collection
        self.update()

    def update(self, collection=None):
        """
            Updates this playlist

            @param collection:  To specify a Collection other than what was 
                passed in the constructor
        """
        if not collection:
            collection = self.collection

        tracks = collection.search('')
        self.add_tracks(tracks)

class SmartPlaylist(Playlist):
    """ 
        Represents a Smart Playlist.  
        This will query a collection object using a set of parameters
    """
    def __init__(self, name="", location=None, collection=None, 
        pickle_attrs=[]):
        """
            Sets up a smart playlist
            
            collection: a reference to a TrackDB object.
    
            args: See TrackDB
        """
        self.search_params = []
        self.custom_params = []
        self.collection = collection
        self.or_match = False
        pickle_attrs += ['search_params', 'or_match']
        Playlist.__init__(self, name=name, location=location,
                pickle_attrs=pickle_attrs)

    def set_collection(self, collection):
        """
            change the collection backing this playlist

            collection: the collection to use [Collection]
        """
        self.collection = collection

    def set_or_match(self, value):
        """
            Set to True to make this an or match: match any of the parameters

            value: True to match any, False to match all params
        """
        self.or_match = value

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
   

    def remove_param(self, index):
        """
            Removes a parameter at the speficied index
        
            index:  the index of the parameter to remove
        """
        return self.search_params.pop(index)

    def update(self, collection=None, clear=True):
        """
            Update internal tracks by querying the collection
            
            @param collection: the collection to search (leave none to search
                        internal ref)
            @param clear:      clear current tracks
        """
        self.remove_tracks(0, len(self))
        if not collection:
            collection = self.collection
        if not collection: #if there wasnt one set we might not have one
            return

        search_string = self._create_search_string()
        self.add_tracks(collection.search(search_string))

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


class PlaylistManager(object):

    def __init__(self):
        self.playlist_dir = os.path.join(xdg.get_data_dirs()[0],'playlists')
        self.smart_playlist_dir = os.path.join(xdg.get_data_dirs()[0],
                'smart_playlists')
        for dir in [self.playlist_dir, self.smart_playlist_dir]:
            if not os.path.exists(dir):
                os.makedirs(dir)
        self.playlists = {}
        self.smart_playlists = {}

        self.load_names()

    def add_playlist(self, pl):
        name = pl.get_name()
        pl.set_location(os.path.join(self.playlist_dir, pl.get_name()))
        self.playlists[name] = pl
        event.log_event('playlist_added', self, pl)

    def remove_playlist(self, name):
        if self.playlists.has_key(name):
            pl = self.playlists[name]
            del self.playlists[name]
            event.log_event('playlist_removed', self, pl)

    def add_smart_playlist(self, pl):
        name = pl.get_name()
        pl.set_location(os.path.join(self.smart_playlist_dir,pl.get_name()))
        self.smart_playlists[name] = pl
        event.log_event('smart_playlist_added', self, pl)

    def remove_smart_playlist(self, pl):
        if self.smart_playlists.has_key(name):
            pl = self.smart_playlists[name]
            del self.smart_playlists[name]
            event.log_event('smart_playlist_removed', self, pl)

    def save_all(self):
        for pl in self.playlists.values():
            if pl is not None:
                pl.save_to_location()
        for pl in self.smart_playlists.values():
            if pl is not None:
                pl.save_to_location()

    def rename_playlist(self, old, new):
        pl = self.get_playlist(old)
        self.remove_playlist(old)
        pl.set_name(new)
        self.add_playlist(pl)

    def rename_smart_playlist(self, old, new):
        pl = self.get_playlist(old)
        self.remove_playlist(old)
        pl.set_name(new)
        self.add_playlist(pl)

    def load_names(self):
        playlist_names = os.listdir(self.playlist_dir)
        for p in playlist_names:
            self.playlists[p] = None
        smart_playlist_names = os.listdir(self.smart_playlist_dir)
        for p in smart_playlist_names:
            self.smart_playlists[p] = None

    def get_playlist(self, name):
        if self.playlists.has_key(name):
            pl = self.playlists[name]
            if pl == None:
                pl = Playlist(name=name, 
                        location=os.path.join(self.playlist_dir, name))
            return pl
        else:
            raise ValueError("No such playlist")

    def list_playlists(self):
        return self.playlists.keys()

    def get_smart_playlist(self, name):
        if self.smart_playlists.has_key(name):
            pl = self.smart_playlists[name]
            if pl == None:
                pl = SmartPlaylist(name=name, 
                        location=os.path.join(self.smart_playlist_dir,name))
            return pl
        else:
            raise ValueError("No such playlist")

    def list_smart_playlists(self):
        return self.smart_playlists.keys()

# vim: et sts=4 sw=4

