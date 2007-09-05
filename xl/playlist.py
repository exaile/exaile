# Copyright (C) 2006 Adam Olsen
#
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

import os, re, urlparse, urllib
from gettext import gettext as _
import gtk, gobject
import common, xlmisc, library, media
from xl.gui import playlist as trackslist
import xl.path

class PlaylistManager(gobject.GObject):
    __gsignals__ = {
        'last-playlist-loaded': (gobject.SIGNAL_RUN_LAST, None, ()),
    }

    def __init__(self, exaile):
        gobject.GObject.__init__(self)
        self.exaile = exaile
        self.settings = exaile.settings
        self.db = exaile.db

    @common.threaded
    def import_playlist(self, path, play=False, title=None, newtab=True,
        set_current=True):
        """
            Threaded wrapper for _import_playlist_wrapped
        """
        self._import_playlist_wrapped(path, play, title, newtab, set_current)
    
    def _import_playlist_wrapped(self, path, play=False, title=None,
        newtab=True, set_current=True):
        """
            Imports a playlist file, regardless of it's location (it can be
            a local file (ie, file:///somefile.m3u) or online.
        """
        xlmisc.log("Importing %s" % path)
        gobject.idle_add(self.exaile.status.set_first, _("Importing playlist..."))

        ## Create playlist object

        url = common.to_url(path)
        spliturl = urlparse.urlsplit(path)

        path = urllib.unquote(spliturl[2])
        name, ext = os.path.splitext(os.path.basename(path))
        name = name.replace("_", " ")

        if ext.lower() == ".asx":
            playlist = xlmisc.ASXParser(name, url)
        else:
            # TODO: This is inefficient because we're reopening the file later.
            file = urllib.urlopen(url)
            first_line = file.readline().strip()
            file.close()
            if first_line == '[playlist]':
                playlist = xlmisc.PlsParser(name, url)
            else:
                playlist = xlmisc.M3UParser(name, url)

        ## Add tracks from the playlist

        first = True
        songs = library.TrackData()
        t = trackslist.TracksListCtrl

        count = 0
        for item in playlist.get_urls():
            url = item['url']
            if url[0] == 'device': continue
            elif url[0] == 'file':
                filename = urllib.unquote(url[2])
                tr = library.read_track(self.db, self.exaile.all_songs, filename)
                  
            else: 
                tr = media.Track(urlparse.urlunsplit(url))
                tr.type = 'stream'
                tr.title = item['title']
                tr.album = item['album']

                if first and play:
                    play = tr
                    
            if tr:
                songs.append(tr)

            first = False

        if title: name = title
        if not songs: 
            gobject.idle_add(self.exaile.status.set_first, None)
            return
        
        if newtab:
            def _new_page(name, songs, set_current):
                t = self.exaile.new_page(name, songs, set_current)
                if not set_current: t.set_songs(songs)

            gobject.idle_add(_new_page, name, songs, set_current)
        else:
            gobject.idle_add(self.append_songs, songs, False, False)

        if type(play) != bool and play.type == 'stream':
            gobject.idle_add(self.exaile.player.stop)
            gobject.idle_add(self.exaile.player.play_track, play, False, False)

        gobject.idle_add(self.exaile.status.set_first, None)

    def load_last_playlist(self): 
        """
            Loads the playlist that was in the player on last exit
        """
        dir = xl.path.get_config('saved')
        if not os.path.isdir(dir):
            os.mkdir(dir, 0744)

        last_active = self.settings.get_int('last_active', -1)
        if self.settings.get_boolean("open_last", True):
            files = os.listdir(dir)
            for i, file in enumerate(files):
                if not file.endswith(".m3u"): continue
                h = open(os.path.join(dir, file))
                line = h.readline()
                line = h.readline()
                h.close()
                title = _("Playlist")
                m = re.search('^#PLAYLIST: (.*)$', line)
                if m:
                    title = m.group(1)

                self._import_playlist_wrapped(os.path.join(dir, file),
                    title=title, set_current=False)

            if last_active > -1:
                xlmisc.finish()
                gobject.idle_add(self.exaile._load_tab, last_active)

        # load queue
        if self.settings.get_boolean('save_queue', True):
            if os.path.isfile(os.path.join(dir, "queued.save")):
                h = open(os.path.join(dir, "queued.save"))
                for line in h.readlines():
                    line = line.strip()
                    song = self.exaile.all_songs.for_path(line)
                    if song:
                        self.exaile.player.queued.append(song)
                h.close()

            trackslist.update_queued(self.exaile)
        stop_track = self.settings.get_str('stop_track', '')
        if stop_track != '':
            stop_track = self.exaile.all_songs.for_path(stop_track)
            self.exaile.player.stop_track = stop_track
            self.exaile.tracks.queue_draw()

        if not self.exaile.playlists_nb.get_n_pages():
            self.exaile.new_page(_("Playlist"))

        # PLUGIN: send plugins event when the last playlist is loaded
        xlmisc.log('Last playlist loaded')
        self.emit('last-playlist-loaded')

    def export_playlist(self): 
        """
            Exports the current selected playlist as an .m3u file
        """
        filter = gtk.FileFilter()
        filter.add_pattern('*.m3u')

        dialog = gtk.FileChooserDialog(_("Choose a file"),
            self.exaile.window, gtk.FILE_CHOOSER_ACTION_SAVE, 
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        dialog.set_current_folder(self.exaile.get_last_dir())
        dialog.set_filter(filter)

        result = dialog.run()
        dialog.hide()

        if result == gtk.RESPONSE_OK:
            path = dialog.get_filename()
            self.exaile.last_open_dir = dialog.get_current_folder()

            self.save_m3u(path, self.exaile.playlist_songs)

    def save_m3u(self, path, songs, playlist_name=''):
        """
            Saves a list of songs to an m3u file
        """
        handle = open(path, "w")

        handle.write("#EXTM3U\n")
        if playlist_name:
            handle.write("#PLAYLIST: %s\n" % playlist_name)

        for track in songs:
            handle.write("#EXTINF:%d,%s\n%s\n" % (track.duration,
                track.title, track.loc))

        handle.close()

    def append_songs(self, songs, queue=False, play=True):
        """
            Adds songs to the current playlist
        """
        if queue: play = False
        if len(self.exaile.playlist_songs) == 0:
            self.exaile.playlist_songs = library.TrackData()

        # loop through all the tracks
        for song in songs:

            # if the song isn't already in the current playlist, append it
            if not song.loc in self.exaile.playlist_songs.paths:
                self.exaile.playlist_songs.append(song)

            # if we want to queue this song, make sure it's not already
            # playing and make sure it's not already in the queue
            if queue and not song in self.exaile.player.queued and song != \
                self.exaile.player.current:

                # if there isn't a queue yet, be sure to set which song is
                # going to be played after the queue is empty
                if not self.exaile.player.queued and self.exaile.player.current:
                    self.next = self.exaile.player.current 
                self.exaile.player.queued.append(song)
                num = len(self.exaile.player.queued)

        # update the current playlist
        gobject.idle_add(self.exaile.update_songs, self.exaile.playlist_songs)
        gobject.idle_add(trackslist.update_queued, self.exaile)
        if not play: return

        track = self.exaile.player.current
        if track != None and (self.exaile.player.is_playing() or self.exaile.player.is_paused): return
        gobject.idle_add(self.exaile.player.play_track, songs[0], False, False)
