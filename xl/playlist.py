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

import cgi
from datetime import datetime, timedelta
import gio
import logging
import os
import random
import time
import urllib
import urlparse
import xml.etree.cElementTree as ETree

try:
    import cPickle as pickle
except:
    import pickle

from xl import (
    collection,
    common,
    dynamic,
    event,
    providers,
    settings,
    trax,
    xdg,
)
from xl.common import MetadataList
from xl.nls import gettext as _

logger = logging.getLogger(__name__)

class InvalidPlaylistTypeException(Exception):
    pass

def encode_filename(name):
    """Converts name into a valid filename.
    """
    # list of invalid chars that need to be encoded
    # Note: '%' is the prefix for encoded chars so blacklist it too
    blacklist = r'<>:"/\|?*%'

    def encode_char(c):
        return '%' + hex(ord(c))[2:] if c in blacklist else c

    # encode any blacklisted chars
    name = ''.join([encode_char(c) for c in name]) + '.playlist'

    return name

class FormatConverter(object):
    """
        Base class for all converters allowing to
        import from and export to a specific format
    """
    title = _('Playlist')
    file_extensions = property(lambda self: [self.name])

    def __init__(self, name):
        self.name = name

    def export_to_file(self, playlist, path):
        """
            Export a playlist to a given path

            :param playlist: the playlist
            :type playlist: :class:`Playlist`
            :param path: the target path
            :type path: string
        """
        pass

    def import_from_file(self, path):
        """
            Import a playlist from a given path

            :param path: the source path
            :type path: string
            :returns: the playlist
            :rtype: :class:`Playlist`
        """
        pass

class M3UConverter(FormatConverter):
    """
        Import from and export to M3U format
    """
    title = _('M3U Playlist')

    def __init__(self):
        FormatConverter.__init__(self, 'm3u')

    def export_to_file(self, playlist, path):
        """
            Export a playlist to a given path

            :param playlist: the playlist
            :type playlist: :class:`Playlist`
            :param path: the target path
            :type path: string
        """
        gfile = gio.File(path)
        stream = gfile.replace('', False)

        stream.write("#EXTM3U\n")

        if playlist.name:
            stream.write("#PLAYLIST: %s\n" % playlist.name)

        for track in playlist:
            length = round(float(track.get_tag_raw('__length') or -1))
            title = [track.get_tag_raw('title', join=True)]
            artist = track.get_tag_raw('artist', join=True)

            if artist:
                title += [artist]

            stream.write("#EXTINF:%d,%s\n%s\n" % (
                length, ' - '.join(title), track.get_loc_for_io()))

        stream.close()

    def import_from_file(self, path):
        """
            Import a playlist from a given path

            :param path: the source path
            :type path: string
            :returns: the playlist
            :rtype: :class:`Playlist`
        """
        url_parsed = urlparse.urlparse(path)
        # Local file, possibly on Windows ?
        if not url_parsed[0] or len(url_parsed[0]) == 1:
            handle = open(path, 'r')
            name = os.path.basename(path).replace(".m3u","")
            is_local = True
        else:
            handle = urllib.urlopen(path)
            name = url_parsed[2].split('/')[-1].replace('.m3u', '')
            is_local = False

        gfile = gio.File(path)

        if gfile.is_native():
            name = os.path.basename(gfile.get_path())
        else:
            name = gfile.get_uri().split('/')[-1]

        for extension in self.file_extensions:
            try:
                name = name[:name.rindex('.%s' % extension)]
            except ValueError:
                pass
            else:
                break

        playlist = Playlist(name)

        stream = gio.DataInputStream(gfile.read())

        while True:
            line = stream.read_line()

            if not line:
                break

            line = line.strip()

            if not line:
                continue

            if line.upper().startswith('#PLAYLIST: '):
                playlist.name = line[len('#PLAYLIST: '):]
            elif line.startswith('#EXTINF:'):
                extinf_line = line[len('#EXTINF:'):]
                uri = stream.read_line()

                if uri is None:
                    continue

                track = trax.Track(uri)

                parts = extinf_line.split(',', 1)
                length = 0

                if len(parts) > 1 and int(parts[0]) > 0:
                    length = parts[0]

                track.set_tag_raw('__length', float(length))

                parts = parts[-1].rsplit(' - ', 1)
                track.set_tag_raw('title', parts[-1])

                if len(parts) > 1:
                    track.set_tag_raw('artist', parts[0])

                playlist.append(track)

            elif line.startswith('#'):
                continue

        stream.close()

        return playlist
providers.register('playlist-format-converter', M3UConverter())

class PLSConverter(FormatConverter):
    """
        Import from and export to PLS format
    """
    title = _('PLS Playlist')

    def __init__(self):
        FormatConverter.__init__(self, 'pls')

    def export_to_file(self, playlist, path):
        """
            Export a playlist to a given path

            :param playlist: the playlist
            :type playlist: :class:`Playlist`
            :param path: the target path
            :type path: string
        """
        gfile = gio.File(path)
        stream = gfile.replace('', False)

        stream.write('[playlist]\n')
        stream.write('NumberOfEntries=%d\n\n' % len(playlist))

        for index, track in enumerate(playlist):
            position = index + 1
            title = [track.get_tag_raw('title', join=True)]
            artist = track.get_tag_raw('artist', join=True)

            if artist:
                title = [artist] + title

            length = round(float(track.get_tag_raw('__length') or -1))

            if length < 0:
                length = -1

            stream.write('File%d=%s\n' % (position, track.get_loc_for_io()))
            stream.write('Title%d=%s\n' % (position, ' - '.join(title)))
            stream.write('Length%d=%d\n\n' % (position, length))

        stream.write('Version=2')
        stream.close()

    def import_from_file(self, path):
        """
            Import a playlist from a given path

            :param path: the source path
            :type path: string
            :returns: the playlist
            :rtype: :class:`Playlist`
        """
        if not handle: handle = urllib.urlopen(path)

        #PLS doesn't store a name, so assume the filename is the name
        name = os.path.split(path)[-1].replace(".pls","")

        line = handle.readline().strip()
        if line != '[playlist]':
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
            logger.warning("No PLS version specified, "
                           "assuming 2. [%s]" % path)
        else:
            if linedict["version"].strip() != '2':
                logger.error("PLS file is not a supported version!")
                return None
        if not linedict.has_key("numberofentries"):
            return None

        num = int(linedict["numberofentries"])

        playlist = Playlist(name=name)

        for n in range(1,num+1):
            track = trax.Track(linedict["file%d" % n])
            if ("title%d" % n) in linedict:
                title = linedict["title%d" % n]
                artist_title = title.split(' - ', 1)
                if len(artist_title) > 1:
                    artist, title = artist_title
                    track.set_tag_raw('artist', artist)
            else:
                title = os.path.splitext(
                    os.path.basename(linedict["file%d" % n]))[0]
            track.set_tag_raw('title', title)
            if ("Length%d" % n) in linedict:
                length = float(linedict["Length%d" % n])
                if length < 0:
                    length = 0
            else:
                length = 0
            track.set_tag_raw('__length', length)
            playlist.append(track)

        handle.close()

        return playlist
providers.register('playlist-format-converter', PLSConverter())

class ASXConverter(FormatConverter):
    """
        Import from and export to ASX format
    """
    title = _('ASX Playlist')

    def __init__(self):
        FormatConverter.__init__(self, 'asx')

    def export_to_file(self, playlist, path):
        """
            Export a playlist to a given path

            :param playlist: the playlist
            :type playlist: :class:`Playlist`
            :param path: the target path
            :type path: string
        """
        handle = open(path, "w")

        handle.write("<asx version=\"3.0\">\n")
        if playlist.name == '':
            name = ''
        else:
            name = playlist.name
        handle.write("  <title>%s</title>\n" % name)

        for track in playlist:
            handle.write("<entry>\n")
            handle.write("  <title>%s</title>\n" % \
                    track.get_tag_raw('title', join=True))
            handle.write("  <ref href=\"%s\" />\n" % track.get_loc_for_io())
            handle.write("</entry>\n")

        handle.write("</asx>")
        handle.close()

    def import_from_file(self, path):
        """
            Import a playlist from a given path

            :param path: the source path
            :type path: string
            :returns: the playlist
            :rtype: :class:`Playlist`
        """
        tree = ETree.ElementTree(file=urllib.urlopen(path))
        # bad hack to support non-lowercase elems. FIXME
        trys = [lambda x: x, lambda x: x.upper(), lambda x: x[0].upper() + x[1:]]
        name = _("Unknown")
        nodes = []

        for ty in trys:
            try:
                name = tree.find(ty("title")).text.strip()
            except:
                continue
            break

        for ty in trys:
            nodes = tree.findall(ty("entry"))
            if nodes != []:
                break

        playlist = Playlist(name=name)

        for n in nodes:
            loc = n.find("ref").get("href")
            track = trax.Track(loc)
            try:
                track.set_tag_raw('title', n.find("title").text.strip())
            except:
                pass
            playlist.append(track)

        return playlist
providers.register('playlist-format-converter', ASXConverter())

class XSPFConverter(FormatConverter):
    """
        Import from and export to XSPF format
    """
    title = _('XSPF Playlist')

    def __init__(self):
        FormatConverter.__init__(self, 'xspf')
        # TODO: support image tag for CoverManager
        self.tags = {
            'title': 'title',
            'creator': 'artist',
            'album': 'album',
            'trackNum': 'tracknumber'
        }

    def export_to_file(self, playlist, path):
        """
            Export a playlist to a given path

            :param playlist: the playlist
            :type playlist: :class:`Playlist`
            :param path: the target path
            :type path: string
        """
        handle = open(path, "w")

        handle.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        handle.write("<playlist version=\"1\" xmlns=\"http://xspf.org/ns/0/\">\n")
        if playlist.name != '':
            handle.write("  <title>%s</title>\n" % playlist.name)

        handle.write("  <trackList>\n")
        for track in playlist:
            handle.write("    <track>\n")
            for element, tag in self.tags.iteritems():
                if not track.get_tag_raw(tag):
                    continue
                handle.write("      <%s>%s</%s>\n" % (
                    element,
                    track.get_tag_raw(tag, join=True),
                    element
                ))
            url = track.get_loc_for_io()
            handle.write("      <location>%s</location>\n" % url)
            handle.write("    </track>\n")

        handle.write("  </trackList>\n")
        handle.write("</playlist>\n")
        handle.close()

    def import_from_file(self, path):
        """
            Import a playlist from a given path

            :param path: the source path
            :type path: string
            :returns: the playlist
            :rtype: :class:`Playlist`
        """
        #TODO: support content resolution
        tree = ETree.ElementTree(file=urllib.urlopen(path))
        ns = "{http://xspf.org/ns/0/}"
        nodes = tree.find("%strackList" % ns).findall("%strack" % ns)
        name = tree.find("%stitle" % ns).text.strip()
        playlist = Playlist(name=name)

        for n in nodes:
            loc = n.find("%slocation" % ns).text.strip()
            track = trax.Track(loc)
            for element, tag in self.tags.iteritems():
                try:
                    track.set_tag_raw(tag,
                        n.find("%s%s" % (ns, element)).text.strip())
                except:
                    pass
            playlist.append(track)

        return playlist
providers.register('playlist-format-converter', XSPFConverter())

def is_valid_playlist(path):
    """
        Returns whether the file at a given path is a valid
        playlist. Based on file extension but could possibly
        be extended to actual content sniffing.

        :param path: the source path
        :type path: string
    """
    file_extension = path.split('.')[-1]

    for provider in providers.get('playlist-format-converter'):
        if file_extension in provider.file_extensions:
            return True

    return False

def import_playlist(path):
    """
        Determines the type of playlist and creates
        a playlist from it

        :param path: the source path
        :type path: string
        :returns: the playlist
        :rtype: :class:`Playlist`
    """
    file_extension = path.split('.')[-1]

    for provider in providers.get('playlist-format-converter'):
        if file_extension in provider.file_extensions:
            return provider.import_from_file(path)

    raise InvalidPlaylistTypeException()

def export_playlist(playlist, path):
    """
        Exact same as @see import_playlist except
        it exports
    """
    file_extension = path.split('.')[-1]

    for provider in providers.get('playlist-format-converter'):
        if file_extension in provider.file_extensions:
            provider.export_to_file(playlist, path)
            break
    else:
        raise InvalidPlaylistTypeException()

class Playlist(object):
    shuffle_modes = ['disabled', 'track', 'album']
    shuffle_mode_names = [_('Shuffle _Off'),
            _('Shuffle _Tracks'), _('Shuffle _Albums')]
    repeat_modes = ['disabled', 'all', 'track']
    repeat_mode_names = [_('Repeat _Off'), _('Repeat _All'), _('Repeat _One')]
    dynamic_modes = ['disabled', 'enabled']
    dynamic_mode_names = [_('Dynamic Playlists O_ff'), _('Dynamic Playlists O_n')]
    # TODO: how do we document properties/events in sphinx?
    """

        PROPERTIES:
            name: playlist name. read/write.

        EVENTS: (all events are synchronous)
            playlist_tracks_added
                fired: after tracks are added
                data: list of tuples of (index, track)
            playlist_tracks_removed
                fired: after tracks are removed
                data: list of tuples of (index, track)
            playlist_current_position_changed
            playlist_shuffle_mode_changed
            playlist_random_mode_changed
            playlist_dynamic_mode_changed
    """
    save_attrs = ['shuffle_mode', 'repeat_mode', 'dynamic_mode',
            'current_position', 'name']
    __playlist_format_version = [2, 0]
    def __init__(self, name, initial_tracks=[]):
        self.__tracks = MetadataList()
        for track in initial_tracks:
            if not isinstance(track, trax.Track):
                raise ValueError, "Need trax.Track object, got %s" % repr(type(x))
            self.__tracks.append(track)
        self.__shuffle_mode = self.shuffle_modes[0]
        self.__repeat_mode = self.repeat_modes[0]
        self.__dynamic_mode = self.dynamic_modes[0]

        # dirty: any change that would alter the on-disk
        #   representation should set this
        # needs_save: changes to list content should set this.
        #   Determines when the 'unsaved' indicator is shown to the user.
        self.__dirty = False
        self.__needs_save = False
        self.__name = name
        self.__current_position = -1
        self.__spat_position = -1
        self.__shuffle_history_counter = 1 # start positive so we can
                                # just do an if directly on the value
        event.add_callback(self.fetch_dynamic_tracks,
                "playback_track_start")

    ### playlist-specific API ###

    def _set_name(self, name):
        self.__name = name
        self.__needs_save = self.__dirty = True
        event.log_event("playlist_name_changed", self, name)

    name = property(lambda self: self.__name, _set_name)
    dirty = property(lambda self: self.__dirty)

    def clear(self):
        del self[:]

    def get_current_position(self):
        return self.__current_position

    def set_current_position(self, position):
        oldposition = self.__current_position
        if position != -1:
            self.__tracks.set_meta_key(position, "playlist_current_position", True)
        self.__current_position = position
        if oldposition != -1:
            try:
                self.__tracks.del_meta_key(oldposition, "playlist_current_position")
            except KeyError:
                pass
        self.__dirty = True
        event.log_event("playlist_current_position_changed", self, (position, oldposition))

    current_position = property(get_current_position, set_current_position)

    def get_spat_position(self):
        return self.__spat_position

    def set_spat_position(self, position):
        oldposition = self.spat_position
        self.__tracks.set_meta_key(position, "playlist_spat_position", True)
        self.__spat_position = position
        if oldposition != -1:
            try:
                self.__tracks.del_meta_key(oldposition, "playlist_spat_position")
            except KeyError:
                pass
        self.__dirty = True
        event.log_event("playlist_spat_position_changed", self, (position, oldposition))

    spat_position = property(get_spat_position, set_spat_position)

    def get_current(self):
        if self.current_position == -1:
            return None
        return self.__tracks[self.current_position]

    current = property(get_current)

    def on_tracks_changed(self, *args):
        for idx in xrange(len(self.__tracks)):
            if self.__tracks.get_meta_key(idx, "playlist_current_position"):
                self.__current_position = idx
                break
        else:
            self.__current_position = -1
        for idx in xrange(len(self.__tracks)):
            if self.__tracks.get_meta_key(idx, "playlist_spat_position"):
                self.__spat_position = idx
                break
        else:
            self.__spat_position = -1

    def get_shuffle_history(self):
        return  [ (i, self.__tracks[i]) for i in range(len(self)) if \
                self.__tracks.get_meta_key(i, 'playlist_shuffle_history') ]

    def clear_shuffle_history(self):
        for i in xrange(len(self)):
            try:
                self.__tracks.del_meta_key(i, "playlist_shuffle_history")
            except:
                pass

    def fetch_dynamic_tracks(self, *args):
        from xl import player
        if player.QUEUE.current_playlist == self:
            if self.dynamic_mode != 'disabled':
                self.__fetch_dynamic_tracks()

    @common.threaded
    def __fetch_dynamic_tracks(self):
        dynamic.MANAGER.populate_playlist(self)

    def __next_random_track(self, mode="track"):
        """
            Returns a valid next track if shuffle is activated based
            on random_mode
        """
        if mode == "album":
            # TODO: we really need proper album-level operations in
            # xl.trax for this
            try:
                # Try and get the next track on the album
                # NB If the user starts the playlist from the middle
                # of the album some tracks of the album remain off the
                # tracks_history, and the album can be selected again
                # randomly from its first track
                curr = self.current
                if not curr:
                    raise IndexError
                t = [ x for i, x in enumerate(self) \
                    if x.get_tag_raw('album') == curr.get_tag_raw('album') \
                    and i > self.current_position ]
                t = trax.sort_tracks(['discnumber', 'tracknumber'], t)
                return self.__tracks.index(t[0]), t[0]

            except IndexError: #Pick a new album
                hist = set(self.get_shuffle_history())
                albums = set()
                for i, x in enumerate(self):
                    if (i, x) in hist:
                        continue
                    alb = x.get_tag_raw('album')
                    if alb:
                        albums.add(tuple(alb))
                print albums
                if not albums:
                    return None, None
                album = list(random.choice(list(albums)))
                t = [ x for x in self if x.get_tag_raw('album') == album ]
                t = trax.sort_tracks(['tracknumber'], t)
                return self.__tracks.index(t[0]), t[0]
        else:
            hist = set([ i for i, tr in self.get_shuffle_history() ])
            try:
                return random.choice([ (i, self.__tracks[i]) for i, tr in enumerate(self.__tracks)
                        if i not in hist])
            except IndexError: # no more tracks
                return None, None

    def next(self):
        repeat_mode = self.repeat_mode
        shuffle_mode = self.shuffle_mode
        if self.current_position == self.spat_position and self.current_position != -1:
            self.spat_position = -1
            return None

        if repeat_mode == 'track':
            return self.current
        else:
            next = None
            if shuffle_mode != 'disabled':
                if self.current is not None:
                    self.__tracks.set_meta_key(self.current_position,
                            "playlist_shuffle_history", self.__shuffle_history_counter)
                    self.__shuffle_history_counter += 1
                next_index, next = self.__next_random_track(shuffle_mode)
                if next is not None:
                    self.current_position = next_index
                else:
                    self.clear_shuffle_history()
            else:
                try:
                    next = self[self.current_position+1]
                    self.current_position += 1
                except IndexError:
                    next = None

            if next is None:
                self.current_position = -1
                if repeat_mode == 'all' and len(self) > 0:
                    next = self.next()

            return next

    def prev(self):
        repeat_mode = self.repeat_mode
        shuffle_mode = self.shuffle_mode
        if repeat_mode == 'track':
            return self.current

        if shuffle_mode != 'disabled':
            try:
                prev_index, prev = max(self.get_shuffle_history())
            except IndexError:
                return self.get_current()
            self.__tracks.del_meta_key(prev_index, 'playlist_shuffle_history')
            self.current_position = prev_index
        else:
            position = self.current_position - 1
            if position < 0:
                if repeat_mode == 'all':
                    position = len(self) - 1
                else:
                    position = 0
            self.current_position = position
        return self.get_current()

    ### track advance modes ###
    # This code may look a little overkill, but it's this way to
    # maximize forwards-compatibility. get_ methods will not overwrite
    # currently-set modes which may be from a future version, while set_
    # methods explicitly disallow modes not supported in this version.
    # This ensures that 1) saved modes are never clobbered unless a
    # known mode is to be set, and 2) the values returned in _mode will
    # always be supported in the running version.

    def __get_mode(self, modename):
        mode = getattr(self, "_Playlist__%s_mode"%modename)
        modes = getattr(self, "%s_modes"%modename)
        if mode in modes:
            return mode
        else:
            return modes[0]

    def __set_mode(self, modename, mode):
        modes = getattr(self, "%s_modes"%modename)
        if mode not in modes:
            raise TypeError, "Mode %s is invalid" % mode
        else:
            self.__dirty = True
            setattr(self, "_Playlist__%s_mode"%modename, mode)
            event.log_event("playlist_%s_mode_changed"%modename, self, mode)

    def get_shuffle_mode(self):
        return self.__get_mode("shuffle")

    def set_shuffle_mode(self, mode):
        self.__set_mode("shuffle", mode)
        if mode == 'disabled':
            self.clear_shuffle_history()

    shuffle_mode = property(get_shuffle_mode, set_shuffle_mode)

    def get_repeat_mode(self):
        return self.__get_mode('repeat')

    def set_repeat_mode(self, mode):
        self.__set_mode("repeat", mode)

    repeat_mode = property(get_repeat_mode, set_repeat_mode)

    def get_dynamic_mode(self):
        return self.__get_mode("dynamic")

    def set_dynamic_mode(self, mode):
        self.__set_mode("dynamic", mode)

    dynamic_mode = property(get_dynamic_mode, set_dynamic_mode)

    def randomize(self):
        # TODO: add support for randomizing a subset of the list?
        trs = zip(self.__tracks, self.__tracks.metadata)
        random.shuffle(trs)
        self[:] = MetadataList([x[0] for x in trs], [x[1] for x in trs])

    def sort(self, tags, reverse=False):
        data = zip(self.__tracks, self.__tracks.metadata)
        data = trax.sort_tracks(tags, data,
                trackfunc=lambda tr: tr[0], reverse=reverse)
        l = MetadataList()
        l.extend([x[0] for x in data])
        l.metadata = [x[1] for x in data]
        self[:] = l

    # TODO[0.4?]: drop our custom disk playlist format in favor of an
    # extended XSPF playlist (using xml namespaces?).

    # TODO: add timeout saving support. 5-10 seconds after last change,
    # perhaps?

    def save_to_location(self, location):
        if os.path.exists(location):
            f = open(location + ".new", "w")
        else:
            f = open(location, "w")
        for track in self.__tracks:
            buffer = track.get_loc_for_io()
            # write track metadata
            meta = {}
            items = ('artist', 'album', 'tracknumber',
                    'title', 'genre', 'date')
            for item in items:
                value = track.get_tag_raw(item)
                if value is not None:
                    meta[item] = value[0]
            buffer += '\t%s\n' % urllib.urlencode(meta)
            try:
                f.write(buffer.encode('utf-8'))
            except UnicodeDecodeError:
                continue

        f.write("EOF\n")
        for item in self.save_attrs:
            val = getattr(self, item)
            try:
                strn = settings.MANAGER._val_to_str(val)
            except ValueError:
                strn = ""

            f.write("%s=%s\n"%(item,strn))
        f.close()
        if os.path.exists(location + ".new"):
            os.remove(location)
            os.rename(location + ".new", location)
        self.__needs_save = self.__dirty = False

    def load_from_location(self, location):
        # note - this is not guaranteed to fire events when it sets
        # attributes. It is intended ONLY for initial setup, not for
        # reloading a playlist inline.
        f = None
        for loc in [location, location+".new"]:
            try:
                f = open(loc, 'r')
                break
            except:
                pass
        if not f:
            return
        locs = []
        while True:
            line = f.readline()
            if line == "EOF\n" or line == "":
                break
            locs.append(line.strip())
        items = {}
        while True:
            line = f.readline()
            if line == "":
                break
            item, strn = line[:-1].split("=",1)
            val = settings.MANAGER._str_to_val(strn)
            items[item] = val

        ver = items.get("__playlist_format_version", [1])
        if ver[0] == 1:
            if items.get("repeat_mode") == "playlist":
                items['repeat_mode'] = "all"
            for m in ['random', 'repeat', 'dynamic']:
                if not items.get("%s_enabled"%m):
                    items['%s_mode'%m] = 'disabled'
        elif ver[0] > self.__playlist_format_version[0]:
            raise IOError, "Cannot load playlist, unknown format"
        elif ver > self.__playlist_format_version:
            logger.warning("Playlist created on a newer Exaile version, some attributes may not be handled.")
        f.close()

        trs = []

        for loc in locs:
            meta = None
            if loc.find('\t') > -1:
                splitted = loc.split('\t')
                loc = "\t".join(splitted[:-1])
                meta = splitted[-1]

            track = None
            track = trax.Track(uri=loc)

            # readd meta
            if not track: continue
            if not track.is_local() and meta is not None:
                meta = cgi.parse_qs(meta)
                for k, v in meta.iteritems():
                    track.set_tag_raw(k, v[0], notify_changed=False)

            trs.append(track)

        self.__tracks[:] = trs


        for item, val in items.iteritems():
            if item in self.save_attrs:
                setattr(self, item, val)

    def reverse(self):
        # reverses current view
        pass

    def sort(self, tags, reverse=False):
        data = zip(self.__tracks, self.__tracks.metadata)
        data = trax.sort_tracks(tags, data,
                trackfunc=lambda tr: tr[0], reverse=reverse)
        l = MetadataList()
        l.extend([x[0] for x in data])
        l.metadata = [x[1] for x in data]
        self[:] = l


    ### list-like API methods ###
    # parts of this section are taken from
    # http://code.activestate.com/recipes/440656-list-mixin/

    def __len__(self):
        return len(self.__tracks)

    def __contains__(self, track):
        return track in self.__tracks

    def __tuple_from_slice(self, i):
        """
            Get (start, end, step) tuple from slice object.
        """
        (start, end, step) = i.indices(len(self))
        if i.step == None:
            step = 1
        return (start, end, step)

    def __getitem__(self, i):
        return self.__tracks.__getitem__(i)

    def __setitem__(self, i, value):
        oldtracks = self.__getitem__(i)
        removed = MetadataList()
        added = MetadataList()

        if isinstance(i, slice):
            for x in value:
                if not isinstance(x, trax.Track):
                    raise ValueError, "Need trax.Track object, got %s"%repr(type(x))

            (start, end, step) = self.__tuple_from_slice(i)

            if isinstance(value, MetadataList):
                metadata = value.metadata
            else:
                metadata = [None] * len(value)

            if step != 1:
                if len(value) != len(oldtracks):
                    raise ValueError, "Extended slice assignment must match sizes."
            self.__tracks.__setitem__(i, value)
            removed = MetadataList(zip(range(start, end, step), oldtracks),
                    oldtracks.metadata)
            if step == 1:
                end = start + len(value)

            added = MetadataList(zip(range(start, end, step), value), metadata)
        else:
            if not isinstance(value, trax.Track):
                raise ValueError, "Need trax.Track object, got %s"%repr(type(x))
            self.__tracks[i] = value
            removed = [(i, oldtracks)]
            added = [(i, value)]

        self.on_tracks_changed()
        event.log_event('playlist_tracks_removed', self, removed)
        event.log_event('playlist_tracks_added', self, added)
        self.__needs_save = self.__dirty = True

    def __delitem__(self, i):
        if isinstance(i, slice):
            (start, end, step) = self.__tuple_from_slice(i)
        oldtracks = self.__getitem__(i)
        self.__tracks.__delitem__(i)
        removed = MetadataList()

        if isinstance(i, slice):
            removed = MetadataList(zip(xrange(start, end, step), oldtracks),
                    oldtracks.metadata)
        else:
            removed = [(i, oldtracks)]

        self.on_tracks_changed()
        event.log_event('playlist_tracks_removed', self, removed)
        self.__needs_save = self.__dirty = True

    def append(self, other):
        self[len(self):len(self)] = [other]

    def extend(self, other):
        self[len(self):len(self)] = other

    def count(self, other):
        return self.__tracks.count(other)

    def index(self, item, start=0, end=None):
        if end is None:
            return self.__tracks.index(item, start)
        else:
            return self.__tracks.index(item, start, end)

    def pop(self, i=-1):
        item = self[i]
        del self[i]
        return item



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
            Set to True to make this an or match: match any of the
            parameters

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
            @param index:  Where to insert the parameter in the search
                    order.  -1 to append [int]
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

            @param collection: the collection to search (leave None to
                    search internal ref)
        """
        if not collection:
            collection = self.collection
        if not collection: #if there wasnt one set we might not have one
            return

        search_string = self._create_search_string()

        matcher = trax.TracksMatcher(search_string, case_sensitive=False)
        trs = [ t.track for t in trax.search_tracks(collection, [matcher]) ]
        if self.random_sort:
            random.shuffle(trs)
        else:
            sort_field = ('artist', 'date', 'album', 'discnumber',
                    'tracknumber', 'title')
            trs = trax.sort_tracks(sort_field, trs)
        if self.track_count > 0 and len(trs) > self.track_count:
            trs=trs[:self.track_count]


        pl = Playlist(name=self.name)
        pl.extend(trs)

        return pl

    def _create_search_string(self):
        """
            Creates a search string based on the internal params
        """

        params = [] # parameter list
        maximum = settings.get_option('rating/maximum', 5)
        durations = {
            _('seconds'): lambda value: timedelta(seconds=value),
            _('minutes'): lambda value: timedelta(minutes=value),
            _('hours'): lambda value: timedelta(hours=value),
            _('days'): lambda value: timedelta(days=value),
            _('weeks'): lambda value: timedelta(weeks=value),
        }

        for param in self.search_params:
            if type(param) == str:
                params += [param]
                continue
            (field, op, value) = param
            s = ""

            if field == '__rating':
                value = float((100.0*value)/maximum)
            elif field in ('__date_added', '__last_played'):
                duration, unit = value
                delta = durations[unit](duration)
                point = datetime.now() - delta
                value = time.mktime(point.timetuple())

            if op == ">=" or op == "<=":
                s += '( %(field)s%(op)s%(value)s ' \
                    '| %(field)s==%(value)s )' % \
                    {
                        'field': field,
                        'value': value,
                        'op':    op[0]
                    }
            elif op == "!=" or op == "!==":
                s += '! %(field)s%(op)s"%(value)s"' % \
                    {
                        'field': field,
                        'value': value,
                        'op':    op[1:]
                    }
            elif op == "><":
                s+= '( %(field)s>%(value1)s ' \
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
            return ' | '.join(params)
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
        name = pl.name
        if overwrite or name not in self.playlists:
            pl.save_to_location(os.path.join(self.playlist_dir,
                encode_filename(name)))

            if not name in self.playlists:
                self.playlists.append(name)
            #self.playlists.sort()
            self.save_order()
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
                os.remove(os.path.join(self.playlist_dir,
                    encode_filename(name)))
            except OSError:
                pass
            self.playlists.remove(name)
            event.log_event('playlist_removed', self, name)

    def rename_playlist(self, playlist, new_name):
        """
            Renames the playlist to new_name
        """
        old_name = playlist.name
        if old_name in self.playlists:
            self.remove_playlist(old_name)
            playlist.set_name(new_name)
            self.save_playlist(playlist)

    def load_names(self):
        """
            Loads the names of the playlists from the order file
        """
        # collect the names of all playlists in playlist_dir
        existing = []
        for f in os.listdir(self.playlist_dir):
            # everything except the order file shold be a playlist
            if f != os.path.basename(self.order_file):
                pl = self.playlist_class(f)
                pl.load_from_location(os.path.join(self.playlist_dir, f))
                existing.append(pl.name)

        # if order_file exists then use it
        if os.path.isfile(self.order_file):
            ordered_playlists = self.load_from_location(self.order_file)
            self.playlists = [n for n in ordered_playlists if n in existing]
        else:
            self.playlists = existing

    def get_playlist(self, name):
        """
            Gets a playlist by name

            @param name: the name of the playlist you wish to retrieve
        """
        if name in self.playlists:
            pl = self.playlist_class(name=name)
            pl.load_from_location(os.path.join(self.playlist_dir,
                encode_filename(name)))
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

