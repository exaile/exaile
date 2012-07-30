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

"""
Provides the fundamental objects for handling a list of tracks contained
in playlists as well as methods to import and export from various file formats.
"""

from __future__ import with_statement
import cgi
from contextlib import closing
from datetime import datetime, timedelta
import gio
import logging
import os
import random
import time
import urllib

try:
    import cPickle as pickle
except ImportError:
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

class InvalidPlaylistTypeError(Exception):
    pass

def encode_filename(filename):
    """
        Converts a file name into a valid filename most
        likely to not cause problems on any platform.

        :param filename: the name of the file
        :type filename: string
    """
    # list of invalid chars that need to be encoded
    # Note: '%' is the prefix for encoded chars so blacklist it too
    blacklist = r'<>:"/\|?*%'

    def encode_char(c):
        return '%' + hex(ord(c))[2:] if c in blacklist else c

    # encode any blacklisted chars
    filename = ''.join([encode_char(c) for c in filename]) + '.playlist'

    return filename

def is_valid_playlist(path):
    """
        Returns whether the file at a given path is a valid
        playlist. Checks for content type and falls back to
        file extension if unknown.

        :param path: the source path
        :type path: string
    """
    content_type = gio.content_type_guess(path)

    if not gio.content_type_is_unknown(content_type):
        for provider in providers.get('playlist-format-converter'):
            if content_type in provider.content_types:
                return True

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
    content_type = gio.content_type_guess(path)

    if not gio.content_type_is_unknown(content_type):
        for provider in providers.get('playlist-format-converter'):
            if content_type in provider.content_types:
                return provider.import_from_file(path)

    file_extension = path.split('.')[-1]

    for provider in providers.get('playlist-format-converter'):
        if file_extension in provider.file_extensions:
            return provider.import_from_file(path)

    raise InvalidPlaylistTypeError(_('Invalid playlist type.'))

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
        raise InvalidPlaylistTypeError(_('Invalid playlist type.'))

class FormatConverter(object):
    """
        Base class for all converters allowing to
        import from and export to a specific format
    """
    title = _('Playlist')
    content_types = []
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

    def name_from_path(self, path):
        """
            Convenience method to retrieve a sane
            name from a path

            :param path: the source path
            :type path: string
            :returns: a name
            :rtype: string
        """
        gfile = gio.File(path)
        name = gfile.get_basename()

        for extension in self.file_extensions:
            if name.endswith(extension):
                # Remove known extension
                return name[:-len(extension)-1]
        return name

class M3UConverter(FormatConverter):
    """
        Import from and export to M3U format
    """
    title = _('M3U Playlist')
    content_types = ['audio/x-mpegurl', 'audio/mpegurl']

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

        with closing(gfile.replace('', False)) as stream:
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


    def import_from_file(self, path):
        """
            Import a playlist from a given path

            :param path: the source path
            :type path: string
            :returns: the playlist
            :rtype: :class:`Playlist`
        """
        gfile = gio.File(path)
        playlist = Playlist(name=self.name_from_path(path))
        extinf = {}

        with closing(gio.DataInputStream(gfile.read())) as stream:
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

                    parts = extinf_line.split(',', 1)
                    length = 0

                    if len(parts) > 1 and int(parts[0]) > 0:
                        length = parts[0]

                    extinf['__length'] = length

                    parts = parts[-1].rsplit(' - ', 1)

                    extinf['title'] = parts[-1]

                    if len(parts) > 1:
                        extinf['artist'] = parts[0]
                elif line.startswith('#'):
                    continue
                else:
                    track = trax.Track(line)

                    if extinf:
                        for tag, value in extinf.iteritems():
                            if track.get_tag_raw(tag) is None:
                                track.set_tag_raw(tag, value)

                    playlist.append(track)
                    extinf = {}

        return playlist
providers.register('playlist-format-converter', M3UConverter())

class PLSConverter(FormatConverter):
    """
        Import from and export to PLS format
    """
    title = _('PLS Playlist')
    content_types = ['audio/x-scpls']

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
        from ConfigParser import RawConfigParser

        pls_playlist = RawConfigParser()
        pls_playlist.optionxform = str # Make case sensitive
        pls_playlist.add_section('playlist')
        pls_playlist.set('playlist', 'NumberOfEntries', len(playlist))

        for index, track in enumerate(playlist):
            position = index + 1
            title = [track.get_tag_raw('title', join=True)]
            artist = track.get_tag_raw('artist', join=True)

            if artist is not None:
                title = [artist] + title

            length = int(round(float(track.get_tag_raw('__length') or -1)))

            if length < 0:
                length = -1

            pls_playlist.set('playlist', 'File%d' % position,
                track.get_loc_for_io())
            pls_playlist.set('playlist', 'Title%d' % position,
                ' - '.join(title))
            pls_playlist.set('playlist', 'Length%d' % position,
                length)

        pls_playlist.set('playlist', 'Version', 2)

        with open(path, 'w') as playlist_file:
            pls_playlist.write(playlist_file)

    def import_from_file(self, path):
        """
            Import a playlist from a given path

            :param path: the source path
            :type path: string
            :returns: the playlist
            :rtype: :class:`Playlist`
        """
        from ConfigParser import RawConfigParser, MissingSectionHeaderError

        pls_playlist = RawConfigParser()
        gfile = gio.File(path)

        try:
            with closing(gio.DataInputStream(gfile.read())) as stream:
                # RawConfigParser.readfp() requires fp.readline()
                stream.readline = stream.read_line
                pls_playlist.readfp(stream)
        except MissingSectionHeaderError:
            # Most likely version 1, thus only a list of URIs
            playlist = Playlist(self.name_from_path(path))

            with closing(gio.DataInputStream(gfile.read())) as stream:

                while True:
                    line = stream.read_line()

                    if not line:
                        break

                    line = line.strip()

                    if not line:
                        continue

                    track = trax.Track(line)
                    
                    if track.get_tag_raw('title') is None:
                        track.set_tag_raw('title', self.name_from_path(line))

                    playlist.append(track)

            return playlist

        if not pls_playlist.has_section('playlist'):
            raise InvalidPlaylistTypeError(
                _('Invalid format for %s.') % self.title)

        if not pls_playlist.has_option('playlist', 'version'):
            logger.warning('No PLS version specified, '
                'assuming 2. [%s]' % path)
            pls_playlist.set('playlist', 'version', 2)

        version = pls_playlist.getint('playlist', 'version')

        if version != 2:
            raise InvalidPlaylistTypeError(
                _('Unsupported version %(version)s for %(type)s') % {
                    'version': version, 'type': self.title})

        if not pls_playlist.has_option('playlist', 'numberofentries'):
            raise InvalidPlaylistTypeError(
                _('Invalid format for %s.') % self.title)

        # PLS playlists store no name, thus retrieve from path
        playlist = Playlist(self.name_from_path(path))
        numberofentries = pls_playlist.getint('playlist',
            'numberofentries')

        for position in xrange(1, numberofentries + 1):
            try:
                uri = pls_playlist.get('playlist',
                    'file%d' % position)
            except NoOptionError:
                continue

            track = trax.Track(uri)
            title = artist = None
            length = 0

            try:
                title = pls_playlist.get('playlist',
                    'title%d' % position)
            except NoOptionError:
                title = self.name_from_path(uri)
            else:
                title = title.split(' - ', 1)

                if len(title) > 1: # "Artist - Title"
                    artist, title = title
                else:
                    title = title[0]

            try:
                length = pls_playlist.getint('playlist',
                    'length%d' % position)
            except NoOptionError:
                pass

            if track.get_tag_raw('title') is None and title:
                track.set_tag_raw('title', title)

            if track.get_tag_raw('artist') is None and artist:
                track.get_tag_raw('artist', artist)

            if track.get_tag_raw('__length') is None:
                track.set_tag_raw('__length', max(0, length))

            playlist.append(track)

        return playlist
providers.register('playlist-format-converter', PLSConverter())

class ASXConverter(FormatConverter):
    """
        Import from and export to ASX format
    """
    title = _('ASX Playlist')
    content_types = ['video/x-ms-asf', 'audio/x-ms-asx',
                     'audio/x-ms-wax', 'video/x-ms-wvx']
    file_extensions = ['asx', 'wax', 'wvx']

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
        import libxml2

        playlist = Playlist(self.name_from_path(path))
        tracks = []

        try:
            asx_playlist = libxml2.parseFile(path)
        except libxml2.parserError:
            tracks = [trax.Track(path)]
        else:
            def compare(name):
                """
                    Returns an XPath evaluation for
                    case-insensitive comparison
                """
                return ('*[translate(local-name(), '
                '"ABCDEFGHIJKLMNOPQRSTUVWXYZ", '
                '"abcdefghijklmnopqrstuvwxyz") = "%s"]') % name

            for title in asx_playlist.xpathEval2('/asx/%s' % compare('title')):
                name = title.get_content().strip()
                break


            for entry in asx_playlist.xpathEval2('/asx/%s' % compare('entry')):
                uris = entry.xpathEval2('%s/@href' % compare('ref'))
                titles = entry.xpathEval2(compare('title'))
                authors = entry.xpathEval2(compare('author'))

                if len(uris) != 1:
                    continue

                track = trax.Track(uris[0].get_content())

                if track.get_tag_raw('title') is None \
                    and len(titles) == 1:
                    track.set_tag_raw('title',
                        titles[0].get_content().strip())

                if track.get_tag_raw('artist') is None \
                    and len(authors) == 1:
                    track.set_tag_raw('artist',
                        authors[0].get_content().strip())

                tracks += [track]

        playlist.extend(tracks)

        return playlist
providers.register('playlist-format-converter', ASXConverter())

class XSPFConverter(FormatConverter):
    """
        Import from and export to XSPF format
    """
    title = _('XSPF Playlist')
    content_types = ['application/xspf+xml']

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
        import xml.etree.cElementTree as ETree

        gfile = gio.File(path)
        playlist = Playlist(name=self.name_from_path(path))

        with closing(gio.DataInputStream(gfile.read())) as stream:
            tree = ETree.ElementTree(file=stream)
            ns = "{http://xspf.org/ns/0/}"
            nodes = tree.find("%strackList" % ns).findall("%strack" % ns)
            titlenode = tree.find("%stitle" % ns)

            if titlenode is not None:
                playlist.name = titlenode.text.strip()

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

class Playlist(object):
    # TODO: how do we document events in sphinx?
    """
        Basic class for handling a list of tracks

        EVENTS: (all events are synchronous)
            * playlist_tracks_added
                * fired: after tracks are added
                * data: list of tuples of (index, track)
            * playlist_tracks_removed
                * fired: after tracks are removed
                * data: list of tuples of (index, track)
            * playlist_current_position_changed
            * playlist_shuffle_mode_changed
            * playlist_random_mode_changed
            * playlist_dynamic_mode_changed
    """
    #: Valid shuffle modes (list of string)
    shuffle_modes = ['disabled', 'track', 'album']
    #: Titles of the valid shuffle modes (list of string)
    shuffle_mode_names = [_('Shuffle _Off'),
            _('Shuffle _Tracks'), _('Shuffle _Albums')]
    #: Valid repeat modes (list of string)
    repeat_modes = ['disabled', 'all', 'track']
    #: Titles of the valid repeat modes (list of string)
    repeat_mode_names = [_('Repeat _Off'), _('Repeat _All'), _('Repeat O_ne')]
    #: Valid dynamic modes
    dynamic_modes = ['disabled', 'enabled']
    #: Titles of the valid dynamic modes
    dynamic_mode_names = [_('Dynamic _Off'), _('Dynamic by Similar _Artists')]
    save_attrs = ['shuffle_mode', 'repeat_mode', 'dynamic_mode',
            'current_position', 'name']
    __playlist_format_version = [2, 0]

    def __init__(self, name, initial_tracks=[]):
        """
            :param name: the initial name of the playlist
            :type name: string
            :param initial_tracks: the tracks which shall
                populate the playlist initially
            :type initial_tracks: list of :class:`xl.trax.Track`
        """
        self.__tracks = MetadataList()
        for track in initial_tracks:
            if not isinstance(track, trax.Track):
                raise ValueError, "Need trax.Track object, got %s" % repr(type(track))
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
        event.add_callback(self.on_playback_track_start,
                "playback_track_start")

    ### playlist-specific API ###

    def _set_name(self, name):
        self.__name = name
        self.__needs_save = self.__dirty = True
        event.log_event("playlist_name_changed", self, name)

    #: The playlist name (string)
    name = property(lambda self: self.__name, _set_name)
    #: Whether the playlist was changed or not (boolean)
    dirty = property(lambda self: self.__dirty)

    def clear(self):
        """
            Removes all contained tracks
        """
        del self[:]

    def get_current_position(self):
        """
            Retrieves the current position within the playlist

            :returns: the position
            :rtype: int
        """
        return self.__current_position

    def set_current_position(self, position):
        """
            Sets the current position within the playlist

            :param position: the new position
            :type position: int
        """
        oldposition = self.__current_position
        if oldposition == position:
            return
        if position != -1:
            if position >= len(self.__tracks):
                raise IndexError, "Cannot set position past end of playlist"
            self.__tracks.set_meta_key(position, "playlist_current_position", True)
        self.__current_position = position
        if oldposition != -1:
            try:
                self.__tracks.del_meta_key(oldposition, "playlist_current_position")
            except KeyError:
                pass
        self.__dirty = True
        event.log_event("playlist_current_position_changed", self, (position, oldposition))

    #: The position within the playlist (int)
    current_position = property(get_current_position, set_current_position)

    def get_spat_position(self):
        """
            Retrieves the current position within the playlist
            after which progressing shall be stopped

            :returns: the position
            :rtype: int
        """
        return self.__spat_position

    def set_spat_position(self, position):
        """
            Sets the current position within the playlist
            after which progressing shall be stopped

            :param position: the new position
            :type position: int
        """
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

    #: The position within the playlist after which to stop progressing (int)
    spat_position = property(get_spat_position, set_spat_position)

    def get_current(self):
        """
            Retrieves the track at the current position

            :returns: the track
            :rtype: :class:`xl.trax.Track` or None
        """
        if self.current_position == -1:
            return None
        return self.__tracks[self.current_position]

    current = property(get_current)

    def get_shuffle_history(self):
        """
            Retrieves the history of played
            tracks from a shuffle run

            :returns: the tracks
            :rtype: list
        """
        return  [ (i, self.__tracks[i]) for i in range(len(self)) if \
                self.__tracks.get_meta_key(i, 'playlist_shuffle_history') ]

    def clear_shuffle_history(self):
        """
            Clear the history of played
            tracks from a shuffle run
        """
        for i in xrange(len(self)):
            try:
                self.__tracks.del_meta_key(i, "playlist_shuffle_history")
            except:
                pass

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
        """
            Progresses to the next track within the playlist
            and takes shuffle and repeat modes into account

            :returns: the new current track
            :rtype: :class:`xl.trax.Track` or None
        """
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
        """
            Progresses to the previous track within the playlist
            and takes shuffle and repeat modes into account

            :returns: the new current track
            :rtype: :class:`xl.trax.Track` or None
        """
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
                    position = 0 if len(self) else -1
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
        """
            Retrieves the current shuffle mode

            :returns: the shuffle mode
            :rtype: string
        """
        return self.__get_mode("shuffle")

    def set_shuffle_mode(self, mode):
        """
            Sets the current shuffle mode

            :param mode: the new shuffle mode
            :type mode: string
        """
        self.__set_mode("shuffle", mode)
        if mode == 'disabled':
            self.clear_shuffle_history()

    #: The current shuffle mode (string)
    shuffle_mode = property(get_shuffle_mode, set_shuffle_mode)

    def get_repeat_mode(self):
        """
            Retrieves the current repeat mode

            :returns: the repeat mode
            :rtype: string
        """
        return self.__get_mode('repeat')

    def set_repeat_mode(self, mode):
        """
            Sets the current repeat mode

            :param mode: the new repeat mode
            :type mode: string
        """
        self.__set_mode("repeat", mode)

    #: The current repeat mode (string)
    repeat_mode = property(get_repeat_mode, set_repeat_mode)

    def get_dynamic_mode(self):
        """
            Retrieves the current dynamic mode

            :returns: the dynamic mode
            :rtype: string
        """
        return self.__get_mode("dynamic")

    def set_dynamic_mode(self, mode):
        """
            Sets the current dynamic mode

            :param mode: the new dynamic mode
            :type mode: string
        """
        self.__set_mode("dynamic", mode)

    #: The current dynamic mode (string)
    dynamic_mode = property(get_dynamic_mode, set_dynamic_mode)

    def randomize(self):
        """
            Randomizes the content of the playlist contrary to
            shuffle which affects only the progressing order
        """
        # TODO: add support for randomizing a subset of the list?
        trs = zip(self.__tracks, self.__tracks.metadata)
        random.shuffle(trs)
        self[:] = MetadataList([x[0] for x in trs], [x[1] for x in trs])

    def sort(self, tags, reverse=False):
        """
            Sorts the content of the playlist
            
            :param tags: tags to sort by
            :type tags: list of strings
            :param reverse: whether the sorting shall be reversed
            :type reverse: boolean
        """
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
        """
            Writes the content of the playlist to a given location

            :param location: the location to save to
            :type location: string
        """
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
        """
            Loads the content of the playlist from a given location

            :param location: the location to load from
            :type location: string
        """
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

            try:
                item, strn = line[:-1].split("=",1)
            except ValueError:
                continue # Skip erroneous lines

            val = settings.MANAGER._str_to_val(strn)
            items[item] = val

        ver = items.get("__playlist_format_version", [1])
        if ver[0] == 1:
            if items.get("repeat_mode") == "playlist":
                items['repeat_mode'] = "all"
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
                try:
                    setattr(self, item, val)
                except TypeError: # don't bail if we try to set an invalid mode
                    logger.debug("Got a TypeError when trying to set attribute %s to %s during playlist restore." % (item, val))

    def reverse(self):
        # reverses current view
        pass

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

    def __adjust_current_pos(self, oldpos, removed, added):
        newpos = oldpos
        for i, tr in removed:
            if i <= oldpos:
                newpos -= 1
        for i, tr in added:
            if i <= newpos:
                newpos += 1
        self.current_position = newpos

    def __getitem__(self, i):
        return self.__tracks.__getitem__(i)

    def __setitem__(self, i, value):
        oldtracks = self.__getitem__(i)
        removed = MetadataList()
        added = MetadataList()
        oldpos = self.current_position

        if isinstance(i, slice):
            for x in value:
                if not isinstance(x, trax.Track):
                    raise ValueError, "Need trax.Track object, got %s" % repr(type(x))

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
                raise ValueError, "Need trax.Track object, got %s" % repr(type(value))
            self.__tracks[i] = value
            removed = [(i, oldtracks)]
            added = [(i, value)]

        self.on_tracks_changed()

        if removed:
            event.log_event('playlist_tracks_removed', self, removed)
        if added:
            event.log_event('playlist_tracks_added', self, added)
        self.__adjust_current_pos(oldpos, removed, added)

        self.__needs_save = self.__dirty = True

    def __delitem__(self, i):
        if isinstance(i, slice):
            (start, end, step) = self.__tuple_from_slice(i)
        oldtracks = self.__getitem__(i)
        oldpos = self.current_position
        self.__tracks.__delitem__(i)
        removed = MetadataList()

        if isinstance(i, slice):
            removed = MetadataList(zip(xrange(start, end, step), oldtracks),
                    oldtracks.metadata)
        else:
            removed = [(i, oldtracks)]

        self.on_tracks_changed()
        event.log_event('playlist_tracks_removed', self, removed)
        self.__adjust_current_pos(oldpos, removed, [])
        self.__needs_save = self.__dirty = True

    def append(self, other):
        """
            Appends a single track to the playlist

            :param other: list of :class:`xl.trax.Track`
        """
        self[len(self):len(self)] = [other]

    def extend(self, other):
        """
            Extends the playlist by another playlist

            :param other: list of :class:`xl.trax.Track`
        """
        self[len(self):len(self)] = other

    def count(self, other):
        """
            Returns the count of contained tracks

            :returns: the count
            :rtype: int
        """
        return self.__tracks.count(other)

    def index(self, item, start=0, end=None):
        """
            Retrieves the index of a track within the playlist

            :returns: the index
            :rtype: int
        """
        if end is None:
            return self.__tracks.index(item, start)
        else:
            return self.__tracks.index(item, start, end)

    def pop(self, i=-1):
        """
            Pops a track from the playlist

            :param i: the index
            :type i: int
            :returns: the track
            :rtype: :class:`xl.trax.Track`
        """
        item = self[i]
        del self[i]
        return item

    def on_playback_track_start(self, event_type, player, track):
        
        if player.queue and player.queue.current_playlist == self:
            if self.dynamic_mode != 'disabled':
                self.__fetch_dynamic_tracks()

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
            elif op == "!=" or op == "!==" or op == "!~":
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
            elif op == '<!==>':     # NOT NULL
                s += '! %(field)s=="__null__"' % \
                    {
                        'field': field
                    }
            elif op == '<==>':      # IS NULL
                s += '%(field)s=="__null__"' % \
                    {
                        'field': field
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
            # everything except the order file shold be a playlist, but
            # check against hidden files since some editors put
            # temporary stuff in the same dir.
            if f != os.path.basename(self.order_file) and not f.startswith("."):
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

