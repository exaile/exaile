#!/usr/bin/env python
# Copyright (C) 2006 Adam Olsen <arolsen@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import gtk, gobject, re, time
from xl import library, media, common, xlmisc
import xl, os
from gettext import gettext as _
import xl.plugins as plugins

PLUGIN_NAME = _("iPod Device Driver")
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = '0.4.3'
PLUGIN_DESCRIPTION = _(r"""iPod Driver for the Devices Panel""")
PLUGIN_ENABLED = False
button = gtk.Button()
PLUGIN_ICON = button.render_icon('gnome-dev-ipod', gtk.ICON_SIZE_MENU)
button.destroy()

PLUGIN = None

try:
    import gpod
    IPOD_AVAIL = True
except ImportError:
    IPOD_AVAIL = False

def configure():
    """
        Shows the configuration dialog
    """
    exaile = APP
    dialog = plugins.PluginConfigDialog(exaile.window, PLUGIN_NAME)
    table = gtk.Table(1, 2)
    table.set_row_spacings(2)
    bottom = 0
    label = gtk.Label(_("Mount Point:      "))
    label.set_alignment(0.0, 0.5)

    table.attach(label, 0, 1, bottom, bottom + 1)

    location = exaile.settings.get_str("ipod_mount", plugin=plugins.name(__file__),
        default="/media/ipod")

    loc_entry = gtk.FileChooserButton(_("Location"))
    loc_entry.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
    loc_entry.set_current_folder(location)
    table.attach(loc_entry, 1, 2, bottom, bottom + 1, gtk.SHRINK)

    dialog.child.pack_start(table)
    dialog.show_all()

    result = dialog.run()
    dialog.hide()
    if result == gtk.RESPONSE_OK:
        exaile.settings.set_str("ipod_mount", loc_entry.get_current_folder(),
            plugin=plugins.name(__file__))

class iPodTrack(media.Track):
    
    type = 'device'
    def __init__(self, *args):
        """
            Initializes the track
        """
        media.Track.__init__(self, *args)

        self.itrack = None

    def ipod_track(self):
        """
            Returns the ipod track
        """
        return self.itrack

    def get_rating(self): 
        """
            Gets the rating
        """
        # this is an approximate conversion from the iPod's rating system
        return "* " * int(self._rating / 14) 
    
    def set_rating(self, rating):
        """
            Sets the rating
        """
        self._rating = rating

    rating = property(get_rating, set_rating)

class iPodPlaylist(object):
    """
        Container for iPod playlist
    """
    def __init__(self, playlist, root=False):
        """
            requires an gpod playlist object
        """
        self.playlist = playlist
        self.name = playlist.name
        self.root = root

    def __str__(self):
        """
            Returns the playlist name
        """
        return self.playlist.name

class iPodDriver(plugins.DeviceDriver):
    name = 'ipod'
    def __init__(self):
        plugins.DeviceDriver.__init__(self)
        self.itdb = None
        self.db = None
        self.exaile = APP
        self.dp = APP.device_panel

        self.ipod_image = xlmisc.get_icon('gnome-dev-ipod')
        self.iplaylist_image = xlmisc.get_icon('gtk-justify-center')
        self.stopped = False

    def remove_tracks(self, tracks):
        """ 
            Removes tracks from the ipod
        """
        for track in tracks:
            song = track 
            track = song.itrack 
            for playlist in gpod.sw_get_playlists(self.itdb):
                if gpod.itdb_playlist_contains_track(playlist, track):
                    gpod.itdb_playlist_remove_track(playlist, track)

            gpod.itdb_track_unlink(track)
            self.all.remove(song)
            for k, v in self.lists.iteritems():
                if track.loc in v:
                    self.lists[k].remove(track.loc)

        self.transfer_done()

    def get_menu(self, item, menu):
        """
            Returns the appropriate menu for a specific item
        """
        if isinstance(item, iPodPlaylist):
            menu = xlmisc.Menu()
            menu.append(_('Add Playlist'), self.on_add_playlist)
            menu.append(_('Rename Playlist'), self.on_rename_playlist)
            menu.append(_('Remove Playlist'), self.on_remove_playlist)

        return menu

    def check_open_item(self, item):
        """
            Checks to see if this is an ipod playlist, and if it is, opens the
            playlist
        """
        if isinstance(item, iPodPlaylist):
            songs = library.TrackData()
            for path in self.lists[item]:
                song = self.all.for_path(path)
                if song:
                    songs.append(song)
            self.exaile.new_page(item.name, songs)
            self.exaile.tracks.playlist = item.name
            return True

        return False

    def on_add_playlist(self, *e): 
        """
            Creates a new playlist on the ipod
        """
        dialog = common.TextEntryDialog(self.exaile.window, 
            _("Enter a name for the new playlist"), _("New Playlist"))
        result = dialog.run()
        if result == gtk.RESPONSE_OK:
            name = str(dialog.get_value())
            playlist = gpod.itdb_playlist_new(name, False)
            p = iPodPlaylist(playlist)
            self.lists[p] = []
            gpod.itdb_playlist_add(self.itdb, playlist, -1)
            item = self.dp.model.append(self.iroot, [self.iplaylist_image,
                p, 'nofield'])
            self.lists_dict[name] = playlist
            self.transfer_done()

            self.dp.load_tree()

    def on_rename_playlist(self, *e): 
        """
            Renames a playlist on the ipod
        """
        selection = self.dp.tree.get_selection()
        (model, paths) = selection.get_selected_rows()
        for path in paths:
            iter = model.get_iter(path)
            playlist = model.get_value(iter, 1)

            dialog = common.TextEntryDialog(self.exaile.window, 
                _("Enter the new name for the playlist"), 
                _("Rename Playlist"))
            result = dialog.run()
            if result == gtk.RESPONSE_OK:
                name = str(dialog.get_value())

                if self.list_dict.has_key(playlist.name):
                    del self.list_dict[playlist.name]
                playlist.playlist.name = name
                playlist.name = name
                self.list_dict[name] = playlist
                self.transfer_done()
                self.dp.tree.queue_draw()

    def on_remove_playlist(self, *e): 
        selection = self.dp.tree.get_selection()
        (model, paths) = selection.get_selected_rows()
        for path in paths:
            iter = model.get_iter(path)
            playlist = model.get_value(iter, 1)

            dialog = gtk.MessageDialog(self.exaile.window, 
                gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, 
                _("Are you sure you want to permanently delete the selected"
                " playlist?"))
            result = dialog.run()
            dialog.destroy()
            if result == gtk.RESPONSE_YES:
                gpod.itdb_playlist_remove(playlist.playlist)
                if self.list_dict.has_key(playlist.name):
                    del self.list_dict[playlist.name]
                if self.lists.has_key(playlist):
                    del self.lists[playlist]
                self.dp.model.remove(iter) 
                self.transfer_done()
                self.dp.tree.queue_draw()
            break

    def get_initial_root(self, model):
        """
            Adds new nodes and returns the one tracks should be added to
        """
        if not self.lists: return None

        self.iroot = model.append(None, [self.ipod_image, self.root_playlist,
			'nofield'])

        for k, v in self.lists.iteritems():
            if k != self.root_playlist:
                item = model.append(self.iroot, [self.iplaylist_image,
                k, 'nofield'])
        path = model.get_path(self.iroot)
        new_root = model.append(None, [self.ipod_image, _("iPod Collection"),
			'nofield'])
        return new_root

    def done_loading_tree(self):
        """
            Called when the tree is done loading
        """
        path = self.dp.model.get_path(self.iroot)
        self.dp.tree.expand_row(path, False)

    def put_item(self, item):
        """
            Transfers a track to the ipod
        """
        (song, target) = (item.track, item.target)
        xlmisc.log("Transferring %s %s" % (song, type(song)))

        # check to see if the track is transferrable
        if self.find_dup(song): return
        if song.type != 'mp3' and song.type != 'aac': return
        if hasattr(song, 'itrack'): return

        track = self.get_ipod_track(song)
        if not track: return
        song.itrack = track
        cover = self.get_cover_location(song)
        track.itdb = self.itdb
        if cover:
            gpod.itdb_track_set_thumbnails(track, cover)

        loc = str(song.io_loc)

        gpod.itdb_cp_track_to_ipod(track, loc, None)
        gpod.itdb_track_add(self.itdb, track, -1)
        mpl = gpod.itdb_playlist_mpl(self.itdb)
        gpod.itdb_playlist_add_track(mpl, track, -1)

        if isinstance(target, iPodPlaylist):
            gpod.itdb_playlist_add_track(target.playlist, track, -1)
            if not loc in self.lists[target]:
                self.lists[target].append(loc)

        song = iPodTrack(loc, track.title, track.artist, track.album, 0,
        track.genre, track.track_nr, track.tracklen / 1000, track.bitrate,
            track.year)
        song.itrack = track
        self.all.append(song)

    def find_dup(self, song):
        """
            Finds if the song is already on the ipod
        """
        for s in self.all:
            if s.title != song.title:
                continue
            elif s.artist != song.artist:
                continue
            elif s.album != song.album:
                continue
            elif s.duration != song.duration:
                continue
            elif s.title != song.title:
                continue
            else:
                return True

        return False

    def get_ipod_track(self, song):
        """
            Returns an ipod compatible track
        """
        try:
            track = gpod.itdb_track_new()
            track.title = str(song.title)
            track.album = str(song.album)
            track.artist = str(song.artist)
            track.tracklen = song.duration * 1000

            try: track.bitrate = int(song._bitrate)
            except: pass
            try: track.track_nr = int(song.track)
            except: pass
            try: track.year = int(song.year)
            except: pass

            if song.type != 'podcast':
                info = os.stat(song.loc)
            else:
                info = os.stat(song.download_path)
            track.size = info[6]

            # libgpod >= 0.5.2 doesn't use mac-type timestamps
            try:
                track.time_added = int(time.time()) + 2082844800
            except TypeError:
                track.time_added = int(time.time())
            track.time_modified = track.time_added
            track.genre = str(song.genre)

            return track 
        except: 
            xlmisc.log_exception()
            return None

    def transfer_done(self):
        gpod.itdb_write(self.itdb, None)

    def get_cover_location(self, track):
        """
            Gets the location of the album art
        """
        db = APP.db
        
        rows = db.select("SELECT image FROM tracks,albums,paths WHERE paths.name=?"
            " AND paths.id=tracks.path AND albums.id=tracks.album",
            (track.loc,))
        if not rows: return None
        row = rows[0]
        if not row or row[0] == '': return None
        return "%s%scovers%s%s" % (APP.get_settings_dir(), os.sep,
            os.sep, str(row[0]))

    @common.threaded
    def connect(self, panel):
        """
            Connects to the ipod
        """
        self.stopped = False
        self.mount = self.exaile.settings.get_str("ipod_mount",
            plugin=plugins.name(__file__), default="/media/ipod")

        self.mount = str(self.mount)
        self.itdb = gpod.itdb_parse(self.mount, None)
        self.panel = panel

        self.lists = {} 
        self.lists_dict = {}
        self.all = library.TrackData()
        self.root_playlist = None

        if not self.itdb: 
            self.connected = False
            self.all = library.TrackData()
            gobject.idle_add(panel.on_error, _("Error connecting to "
                "iPod. Make sure you specify the right mount point "
                "in the plugin configuration."))
            return False

        self.all = library.TrackData()

        for playlist in gpod.sw_get_playlists(self.itdb):
            if playlist.type == 1:
                p = iPodPlaylist(playlist, True)
                self.root_playlist = p
            else:
                p = iPodPlaylist(playlist, False)

            self.lists[p] = []
            self.lists_dict[p.name] = p
            for track in gpod.sw_get_playlist_tracks(playlist):
                loc = self.mount + track.ipod_path.replace(":", "/")
                self.lists[p].append(loc)

        tracks = library.TrackData() 
        for track in gpod.sw_get_tracks(self.itdb):
            if self.stopped:
                self.stopped = False
                return
            loc = self.mount + track.ipod_path.replace(":", "/")
            loc = unicode(loc)
            song = iPodTrack(loc)
            song.itrack = track
            for item in ('title', 'bitrate', 'album', 'artist', 'year',
                'genre', 'rating'):
                if hasattr(track, item) and getattr(track, item):
                    setattr(song, item, getattr(track, item))
            
            song.track = track.track_nr
            song.length = track.tracklen / 1000
        
            tracks.append(song)

        self.all = tracks
        self.connected = True
        self.panel.on_connect_complete(self)
        
    def search_tracks(self, keyword):

        if keyword:
            check = []
            for track in self.all:
                for item in ('artist', 'album', 'title'):
                    attr = getattr(track, item)
                    if keyword.lower() in attr.lower():
                        check.append(track) 
        else:
            check = self.all
        new = [(a.artist, a.album, a.track, a.title, a) for a in check]
        new.sort()
        return library.TrackData([a[4] for a in new])
    
    def disconnect(self):
        self.stopped = True

def initialize():
    global PLUGIN

    if not IPOD_AVAIL:
        common.error(APP.window, _("python-gpod could not be loaded. iPod"
            " device driver will not be available"))
        return False
    PLUGIN = iPodDriver()
    APP.device_panel.add_driver(PLUGIN, PLUGIN_NAME)

    return True

def destroy():
    global PLUGIN

    if PLUGIN:
        APP.device_panel.remove_driver(PLUGIN)

    PLUGIN = None
