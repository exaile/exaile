#!/usr/bin/env python

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

__version__ = '0.2.8b'
import traceback, sys, gobject
gobject.threads_init()

# this stuff is done first so that only the modules required to connect to an
# already loaded exaile (if available) are loaded.  This helps with the speed
# of remote commands, like --next, --prev
import xl.dbusinterface
EXAILE_OPTIONS = xl.dbusinterface.get_options()
DBUS_EXIT = xl.dbusinterface.test(EXAILE_OPTIONS)
import gobject

# find out if they are asking for help
HELP = False
for val in sys.argv:
    if val == '-h' or val == '--help': HELP = True

if '-h' in sys.argv: sys.argv.remove('-h')
if '--help' in sys.argv: sys.argv.remove('--help')
if '--version' in sys.argv:
    print "Exaile version:", __version__
    sys.exit(0)

import pygtk
pygtk.require('2.0')
import gtk, gtk.glade, pango, dbus

import os, re, random, fileinput, gc, urllib, md5, urlparse
import os.path, traceback, thread, gettext, time
import locale, tempfile, subprocess

# set up gettext for translations
locale.setlocale(locale.LC_ALL, '')
from gettext import gettext as _
gettext.bindtextdomain('exaile', 'po')
gettext.textdomain('exaile')

## Find out the location of exaile's working directory, and go there
basedir = os.path.dirname(os.path.realpath(__file__))
if not os.path.exists(os.path.join(basedir, "exaile.py")):
    if os.path.exists(os.path.join(os.getcwd(), "exaile.py")):
        basedir = os.getcwd()
sys.path.insert(0, basedir)
os.chdir(basedir)

from xl import *
import plugins.manager, plugins, plugins.gui

sys_var = "HOME"
if os.sys.platform.startswith("win"): sys_var = "USERPROFILE"
gtk.window_set_default_icon_from_file("images%sicon.png"% os.sep)
SETTINGS_DIR = "%s%s%s" % (os.getenv(sys_var), os.sep, ".exaile")

class ExaileWindow(gobject.GObject): 
    """
        The main interface class
    """
    __gsignals__ = {
        'play-track': (gobject.SIGNAL_RUN_LAST, None, (media.Track,)),
        'stop-track': (gobject.SIGNAL_RUN_LAST, None, (media.Track,)),
        'volume-changed': (gobject.SIGNAL_RUN_LAST, None, (int,)),
        'seek': (gobject.SIGNAL_RUN_LAST, None, (int,)),
        'pause-toggled': (gobject.SIGNAL_RUN_LAST, None, (media.Track,)),
        'quit': (gobject.SIGNAL_RUN_LAST, None, ()),
        'last-playlist-loaded': (gobject.SIGNAL_RUN_LAST, None, ())
    }


    def __init__(self, options, first_run = False): 
        """
            Initializes the main Exaile window
        """
        gobject.GObject.__init__(self)
        self.cover_width = 100
        self.xml = gtk.glade.XML('exaile.glade', 'ExaileWindow', 'exaile')
        self.window = self.xml.get_widget('ExaileWindow')
        media.exaile_instance = self

        self.settings = config.Config("%s%ssettings.ini" % (SETTINGS_DIR,
            os.sep))
        self.options = options
        config.settings = self.settings
        self.database_connect()
        self.timer_count = 0
        self.current_track = None
        self.gamin_watched = []
        self.played = []
        self.mon = None
        self.all_songs = tracks.TrackData()
        self.songs = tracks.TrackData()
        self.playlist_songs = tracks.TrackData()
        self.queued = []
        self.queue_images = []
        self.last_track = None
        self.tracks = None
        self.playlists_menu = None
        self.history = []
        self.cover_thread = None
        self.timer = xlmisc.MiscTimer(self.timer_update, 1000)
        self.playing = False
        self.next = None
        self.thread_pool = []
        self.dir_queue = []
        self.scan_timer = None
        self.debug_dialog = xlmisc.DebugDialog(self)
        self.col_menus = dict()
        self.setup_col_menus('track', trackslist.TracksListCtrl.col_map)
        self.plugins_menu = xlmisc.Menu()
        self.rewind_track = 0
        self.volume_id = None

        if self.settings.get_boolean("use_splash", True):
            image = gtk.Image()
            image.set_from_file("images%ssplash.png" % os.sep)

            xml = gtk.glade.XML('exaile.glade', 'SplashScreen', 'exaile')
            splash_screen = xml.get_widget('SplashScreen')
            box = xml.get_widget('splash_box')
            box.pack_start(image, True, True)
            splash_screen.set_transient_for(None)
            splash_screen.show_all()
            xlmisc.finish()
            gobject.timeout_add(2500, splash_screen.destroy) 
        
        # connect to dbus
        if not "win" in sys.platform:
            try:
                session_bus = dbus.SessionBus()
                name = dbus.service.BusName("org.exaile.DBusInterface", bus=session_bus)
                object = xl.dbusinterface.DBusInterfaceObject(name, self)
            except dbus.DBusException:
                xlmisc.log("Could not connect to dbus session bus.  "
                    "dbus will be unavailable.")

        media.set_audio_sink(self.settings.get('audio_sink', 'Use GConf '
            'Settings'))

        self.tray_icon = None

        volume_image = xlmisc.get_icon('stock_volume', gtk.ICON_SIZE_BUTTON)
        image = gtk.Image()
        image.set_from_pixbuf(volume_image)

        self.volume = self.xml.get_widget('volume_slider')
        self.volume_id = \
            self.volume.connect('change-value', self.on_volume_set)
        self.volume.connect('scroll-event', self.volume_scroll)
        self.volume.set_value(self.settings.get_float('volume', 1) *
            100)
        if self.settings.get_boolean("use_tray", True): 
            self.setup_tray()

        self.window.set_title(_("Exaile!"))

        # log in to audio scrobbler
        user = self.settings.get("lastfm_user", "")
        password = self.settings.get("lastfm_pass", "")
        thread.start_new_thread(media.get_scrobbler_session,
            (user, password))

        self.playlists_nb = self.xml.get_widget('playlists_nb')
        self.set_tab_placement()
        self.setup_left()
        self.setup_right()
        self.connect_events()
        self.setup_menus()

        pos = self.settings.get_int("mainw_sash_pos", 200)
        self.setup_location()

        media.set_volume(self.settings.get_float("volume", 1))

        self.splitter = self.xml.get_widget('splitter')
        self.splitter.connect('notify::position', self.on_resize)
        self.splitter.set_position(pos)

        self.status = xlmisc.StatusBar(self)

        self.playlists_nb.connect('switch-page',
            self.page_changed)
        self.playlists_nb.remove_page(0)

        self.timer.start()

        self.window.show_all()
        self.pmanager = plugins.manager.Manager(self) 
        enabled_plugins = []
        for k, v in self.settings.iteritems():
            if k.find("_plugin_enabled") > -1:
                if v == 'true':
                    enabled_plugins.append(k.replace("_plugin_enabled", ""))

        self.pmanager.load_plugins("%s%splugins" % (basedir, os.sep), enabled_plugins)
        self.pmanager.load_plugins("%s%splugins" % (SETTINGS_DIR, os.sep),
            enabled_plugins)
        self.load_songs(False, True)

        if first_run:
            dialog = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL,
                gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,
                _("You have not specified any search directories for your "
                "music library. You may do so now, or choose to do it later.  "
                "If you want to do it later, you can manage your library "
                "search directories by going to Tools->Library Manager.  "
                "Do you want to choose your library directories now?")) 
            result = dialog.run()
            dialog.destroy()
            if result == gtk.RESPONSE_YES:
                self.show_library_manager()

        interval = self.settings.get_float('scan_interval', '25')
        if interval:
            self.start_scan_interval(interval)

    def get_version(self):
        """
            Returns the version of Exaile
        """
        return __version__

    def start_scan_interval(self, value):
        """
            Starts the scan timer with the specified value in minutes, or 0 to
            disable
        """
        if not value:
            if self.scan_timer:
                self.scan_timer.stop()
                self.scan_timer = None
            xlmisc.log("Scan timer is disabled.")
            return

        if not self.scan_timer:
            self.scan_timer = xlmisc.MiscTimer(lambda:
                self.on_library_rescan(load_tree=False), 1) 

        self.scan_timer.stop()
        self.scan_timer.time = int(value * 60 * 60 * 1000)
        self.scan_timer.start()

    def setup_location(self):
        """
            Sets up the location and size of the window based on settings
        """
        width = self.settings.get_int("mainw_width", 640)
        height = self.settings.get_int("mainw_height", 475)

        x = self.settings.get_int("mainw_x", 10)
        y = self.settings.get_int("mainw_y", 10)

        self.window.resize(width, height)
        self.window.move(x, y)

    def setup_col_menus(self, pref, map):
        """
            Fetches the view column menus from the glade xml definition
        """
        self.resizable_cols = self.xml.get_widget('cols_resizable_item')
        self.not_resizable_cols = \
            self.xml.get_widget('cols_not_resizable_item')
        self.resizable_cols.set_active(self.settings.get_boolean('resizable_cols',
            False))
        self.resizable_cols.connect('activate', self.activate_cols_resizable)
        self.not_resizable_cols.connect('activate',
            self.activate_cols_resizable)

        # setup up default shown columns
        if not self.settings.get_boolean('trackslist_defaults_set', False):
            self.settings.set_boolean('trackslist_defaults_set', True)
            for col in trackslist.TracksListCtrl.col_items:
                self.settings.set_boolean('show_%s_col_%s' %
                    (pref, col), False)
            for col in trackslist.TracksListCtrl.default_columns:
                self.settings.set_boolean('show_%s_col_%s' %
                    (pref, col), True)

        self.col_menus[pref] = dict()
        for k, v in map.iteritems():
            self.col_menus[v] = self.xml.get_widget('%s_%s_col' % (pref,
                v))
            show = self.settings.get_boolean("show_%s_col_%s" %
                (pref, k), True)

            self.col_menus[v].set_active(show)
            self.col_menus[v].connect('activate', 
                self.change_column_settings, 'show_%s_col_%s' % (pref, k))

    def activate_cols_resizable(self, widget, event=None):
        """
            Called when the user chooses whether or not columns can be
            resizable
        """
        self.settings.set_boolean('resizable_cols',
            self.resizable_cols.get_active())
        for i in range(0, self.playlists_nb.get_n_pages()):
            page = self.playlists_nb.get_nth_page(i)
            if isinstance(page, trackslist.TracksListCtrl):
                page.update_col_settings()

    def change_column_settings(self, item, data):
        """
            Changes column view settings
        """
        print "setting %s to %s" % (data, item.get_active())
        self.settings.set_boolean(data, item.get_active())
        for i in range(0, self.playlists_nb.get_n_pages()):
            page = self.playlists_nb.get_nth_page(i)
            if isinstance(page, trackslist.TracksListCtrl):
                page.update_col_settings()

    def page_changed(self, nb, page, num):
        """
            Called when the user switches pages
        """
        page = nb.get_nth_page(num)
        if isinstance(page, trackslist.TracksListCtrl):
            if isinstance(page, trackslist.QueueManager): return
            self.tracks = page
            self.update_songs(page.songs, False)

    def queue_count_clicked(self, *e):
        """
            Called when the user clicks the queue count label
        """
        if self.queue_count_label.get_label(): 
            self.show_queue_manager()

    def connect_events(self):
        """
            Connects events to the various widgets
        """
        self.window.connect('configure_event', self.on_resize)
        self.window.connect('delete_event', self.on_quit)
        self.queue_count_label = self.xml.get_widget('queue_count_label')
        self.xml.get_widget('queue_count_box').connect('button-release-event',
            self.queue_count_clicked)
        self.progress_label = self.xml.get_widget('progress_label')

        # for multimedia keys
        if MMKEYS_AVAIL:
            self.keys = mmkeys.MmKeys()
            self.keys.connect("mm_playpause", lambda e, f: self.toggle_pause())
            self.keys.connect("mm_stop", lambda e, f: self.stop(1))
            self.keys.connect("mm_next", lambda e, f: self.on_next())
            self.keys.connect("mm_prev", lambda e, f: self.on_previous())

        self.play_button = self.xml.get_widget('play_button')
        self.play_button.connect('clicked', self.toggle_pause)

        self.stop_button = self.xml.get_widget('stop_button')
        self.stop_button.connect('clicked', self.stop)

        self.xml.get_widget('show_visualizations_item').connect('activate', 
            media.show_visualizations)

        self.quit_item = self.xml.get_widget('quit_item')
        self.quit_item.connect('activate', self.on_quit)

        self.plugins_item = self.xml.get_widget('plugins_item')
        self.plugins_item.connect('activate', self.show_plugin_manager)
        self.view_menu = self.xml.get_widget('view_menu')

        self.progress = self.xml.get_widget('track_slider')
        self.progress.connect('change-value', self.seek)

        self.clear_button = self.xml.get_widget('clear_button')
        self.clear_button.connect('clicked', lambda *e:
            self.clear_playlist(None))

        self.next_button = self.xml.get_widget('next_button')
        self.next_button.connect('clicked', lambda e: self.on_next())

        self.previous_button = self.xml.get_widget('prev_button')
        self.previous_button.connect('clicked', self.on_previous)

        self.cover_box.connect('button_press_event', self.cover_clicked)

        self.tracks_filter = xlmisc.ClearEntry(self.live_search)
        self.xml.get_widget('tracks_filter_box').pack_start(
            self.tracks_filter.entry,
            True, True)
        self.tracks_filter.connect('activate', self.on_search)
        self.key_id = None

        self.rescan_collection = self.xml.get_widget('rescan_collection')
        self.rescan_collection.connect('activate', self.on_library_rescan)

        self.library_item = self.xml.get_widget('library_manager')
        self.library_item.connect('activate', lambda e:
            self.show_library_manager())

        self.queue_manager_item = self.xml.get_widget('queue_manager_item')
        self.queue_manager_item.connect('activate', 
            lambda *e: self.show_queue_manager())

        self.blacklist_item = self.xml.get_widget('blacklist_manager_item')
        self.blacklist_item.connect('activate', lambda e:
            self.show_blacklist_manager())

        self.xml.get_widget('clear_button').connect('clicked',
            self.clear_playlist)

        self.xml.get_widget('preferences_item').connect('activate',
            lambda e: prefs.Preferences(self).run())

        self.clear_queue_item = self.xml.get_widget('clear_queue_item')
        self.clear_queue_item.connect('activate', self.on_clear_queue)

        self.goto_current_item = self.xml.get_widget('goto_current_item')
        self.goto_current_item.connect('activate', self.goto_current)

        self.xml.get_widget('about_item').connect('activate',
            lambda *e: xlmisc.AboutDialog(self.window, __version__))
        
        self.xml.get_widget('new_item').connect('activate',
            lambda *e: self.new_page())

        self.open_item = self.xml.get_widget('open_item')
        self.open_item.connect('activate', self.on_add_media)

        self.xml.get_widget('export_playlist_item').connect('activate',
            self.export_playlist)

        self.xml.get_widget('open_url_item').connect('activate',
            self.open_url)

        self.fetch_item = self.xml.get_widget('fetch_covers_item')
        self.fetch_item.connect('activate',
            self.fetch_covers)


        self.open_disc_item = self.xml.get_widget('open_disc_item')
        self.open_disc_item.connect('activate',
            self.open_disc)
        self.open_disc_item.set_sensitive(tracks.CDDB_AVAIL)

        self.xml.get_widget('track_artist_item').connect('activate',
            lambda *e: self.jump_to(1))

        self.xml.get_widget('track_album_item').connect('activate',
            lambda *e: self.jump_to(2))

        self.xml.get_widget('track_lyrics_item').connect('activate',
            lambda *e: self.jump_to(3))

        action_log_item = self.xml.get_widget('action_log_item')
        action_log_item.connect('activate',
            lambda *e: self.show_debug_dialog()) 

        self.xml.get_widget('clear_playlist_item').connect('activate',
            lambda *e: self.clear_playlist(None))

        self.xml.get_widget('close_playlist_item').connect('activate',
            lambda *e: self.close_page())
            
        self.xml.get_widget('import_directory_item').connect('activate',
            lambda *e: self.import_directory())

        self.rating_combo = self.xml.get_widget('rating_combo')
        self.rating_combo.set_active(0)
        self.rating_combo.set_sensitive(False)
        self.rating_signal = self.rating_combo.connect('changed', self.set_rating)

    def show_plugin_manager(self, *e):
        """
            Shows the plugin manager
        """
        manager = plugins.gui.PluginManager(self.window, self.pmanager,
            self.update_plugin)

    def update_plugin(self, plugin):
        """
            Sets whether or not a plugin is enabled
        """
        self.settings['%s_plugin_enabled' % plugin.FILE_NAME] = \
            plugin.PLUGIN_ENABLED

    def set_rating(self, combo):
        """
            Sets the user rating of a track
        """
        track = self.current_track
        if not track: return

        rating = combo.get_active() + 1
        track.rating = rating
        path_id = tracks.get_column_id(self.db, 'paths', 'name', track.loc)
        self.db.execute("UPDATE tracks SET user_rating=? WHERE path=?", 
            (rating, path_id))

        xlmisc.log("Set rating to %d for track %s" % (rating, track))
        if self.tracks:
            self.tracks.refresh_row(track)

    def import_directory(self):
        """
            Imports a single directory into the database
        """
        dialog = gtk.FileChooserDialog(_("Add a directory"),
            self.window, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            (_("Cancel"), gtk.RESPONSE_CANCEL, _("Choose"), gtk.RESPONSE_OK))
        dialog.set_current_folder(self.get_last_dir())

        check = gtk.CheckButton(_("Add tracks to current playlist after importing"))
        dialog.set_extra_widget(check)

        items = []
        tmp = self.settings.get("search_paths", "").split(":")
        for i in tmp:
            if i != "": items.append(i)

        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            path = dialog.get_filename()
            if not path in items:
                items.append(path)

            self.settings['search_paths'] = ':'.join(items)

            done_func = None
            if check.get_active():
                done_func = self.after_import
            self.update_library((path,), done_func=done_func, load_tree=False)
        dialog.destroy()

    def after_import(self, songs):
        """
            Adds songs that have just been imported to the current playlist
            after importing a directory
        """

        self.append_songs(songs, play=False)

    def show_debug_dialog(self):
        """
            Shows the debug dialog if it has been initialized
        """
        if xlmisc.DebugDialog.debug:
            xlmisc.DebugDialog.debug.dialog.show()

    def live_search(self, *e):
        """
            Simulates live search of tracks
        """
        if self.key_id:
            gobject.source_remove(self.key_id)

        self.key_id = gobject.timeout_add(700, self.on_search, None, None,
            False)

    def on_clear_queue(self, *e):
        """
            Called when someone wants to clear the queue
        """
        self.queued = []
        if not self.tracks: return
        self.tracks.queue_draw()

    def show_queue_manager(self):
        """
            Shows the queue manager
        """
        nb = self.playlists_nb
        for i in range(0, nb.get_n_pages()):
            page = nb.get_nth_page(i)
            if page.type == 'queue':
                nb.set_current_page(i)
                return
        page = trackslist.QueueManager(self)
        tab = xlmisc.NotebookTab(self, _("Queue"), page)
        self.playlists_nb.append_page(page, tab)
        self.playlists_nb.set_current_page(
            self.playlists_nb.get_n_pages() - 1)

    def show_blacklist_manager(self, new=True):
        """
            Shows the blacklist manager
        """
        nb = self.playlists_nb
        all = self.db.select("SELECT path FROM tracks WHERE blacklisted=1 ORDER BY " \
            "artist, album, track, title")
        songs = []
        for row in all:
            song = tracks.read_track(self.db, None, row[0], True)
            if song: songs.append(song)

        for i in range(0, nb.get_n_pages()):
            page = nb.get_nth_page(i)
            if page.type == 'blacklist':
                nb.set_current_page(i)
                page.set_songs(songs)
                return
        if not new: return

        page = trackslist.BlacklistedTracksList(self)
        page.set_songs(songs)
        tab = xlmisc.NotebookTab(self, _("Blacklist"), page)
        self.playlists_nb.append_page(page, tab)
        self.playlists_nb.set_current_page(
            self.playlists_nb.get_n_pages() - 1)

    def show_library_manager(self):
        """
            Displays the library manager
        """
        dialog = xlmisc.LibraryManager(self)
        response = dialog.run()
        dialog.dialog.hide()
        if response == gtk.RESPONSE_APPLY:
            self.on_library_rescan()
        dialog.destroy()

    def cover_clicked(self, widget, event):
        """
            Called when the cover is clicked on
        """
        if event.type == gtk.gdk._2BUTTON_PRESS:
            if self.cover.loc.find('nocover') > -1: return
            track = self.current_track
            
            xlmisc.CoverWindow(self.window, self.cover.loc, "%s by %s" %
                (track.album, track.artist))
        elif event.button == 3:
            if not self.current_track: return
            self.cover_menu.popup(None, None, None, 
                event.button, event.time)

    def get_play_image(self, size=gtk.ICON_SIZE_SMALL_TOOLBAR):
        """
            Returns a play image
        """
        return gtk.image_new_from_stock('gtk-media-play', size)

    def get_pause_image(self, size=gtk.ICON_SIZE_SMALL_TOOLBAR):
        """
            Returns a pause image
        """
        return gtk.image_new_from_stock('gtk-media-pause', size)

    def get_settings_dir(self): 
        """
            Returns the location of the settings directory
        """
        return SETTINGS_DIR
   
    def set_tab_placement(self, setting=None):
        """
            Sets the placement of the tabs on the playlists notebook
        """
        if not setting:
            p = self.settings.get_int('tab_placement', 0)
        else: p = setting
        s = gtk.POS_LEFT
        if p == 0: s = gtk.POS_TOP
        elif p == 1: s = gtk.POS_LEFT
        elif p == 2: s = gtk.POS_RIGHT
        elif p == 3: s = gtk.POS_BOTTOM

        self.playlists_nb.set_tab_pos(s)

    def setup_tray(self): 
        """
            Sets up the tray icon
        """
        if not xlmisc.USE_TRAY:
            xlmisc.log("Sorry, tray icon is NOT available")
            return
        if self.tray_icon: return
        self.tray_icon = xlmisc.TrayIcon(self)

    def remove_tray(self):
        """
            Removes the tray icon
        """
        if self.tray_icon:
            self.tray_icon.destroy()
            self.tray_icon = None

    def load_last_playlist(self): 
        """
            Loads the playlist that was in the player on last exit
        """
        dir = "%s%ssaved" % (SETTINGS_DIR, os.sep)
        if not os.path.isdir(dir):
            os.mkdir(dir, 0744)

        if self.settings.get_boolean("open_last", True):
            files = os.listdir(dir)
            for file in files:
                if not file.endswith(".m3u"): continue
                h = open("%s%s%s" % (dir, os.sep, file))
                line = h.readline()
                h.close()
                title = "Playlist"
                m = re.search('^# PLAYLIST: (.*)$', line)
                if m:
                    title = m.group(1)

                self.import_m3u("%s%s%s" % (dir, os.sep, file), title=title)

        # load queue
        if self.settings.get_boolean('save_queue', True):
            if os.path.isfile("%s%squeued.save" % (dir, os.sep)):
                h = open("%s%squeued.save" % (dir, os.sep))
                for line in h.readlines():
                    line = line.strip()
                    song = self.all_songs.for_path(line)
                    if song:
                        self.queued.append(song)
                h.close()

            trackslist.update_queued(self)
        last_active = self.settings.get_int('last_active', -1)
        if last_active > -1:
            xlmisc.log("Last active playlist: %d" % last_active)
            gobject.timeout_add(500, self.playlists_nb.set_current_page, last_active)
        
        if not self.playlists_nb.get_n_pages():
            self.new_page(_("Playlist"))

        # PLUGIN: send plugins event when the last playlist is loaded
        self.emit('last-playlist-loaded')


    def append_songs(self, songs, queue=False, play=True, title="Playlist"): 
        """
            Adds songs to the current playlist
        """
        if queue: play = False
        if len(self.playlist_songs) == 0:
            self.playlist_songs = tracks.TrackData()

        # loop through all the tracks
        for song in songs:

            # if the song isn't already in the current playlist, append it
            if not song.loc in self.playlist_songs.paths:
                self.playlist_songs.append(song)

            # if we want to queue this song, make sure it's not already
            # playing and make sure it's not already in the queue
            if queue and not song in self.queued and not (song.is_playing()
                or song.is_paused()):

                # if there isn't a queue yet, be sure to set which song is
                # going to be played after the queue is empty
                if not self.queued and self.current_track:
                    self.next = self.current_track 
                self.queued.append(song)
                num = len(self.queued)

        # update the current playlist
        gobject.idle_add(self.update_songs, self.playlist_songs)
        gobject.idle_add(trackslist.update_queued, self)
        if not play: return

        track = self.current_track
        if track != None and (track.is_playing() or track.is_paused): return
        gobject.idle_add(self.play_track, songs[0])

    def on_blacklist(self, item, event):
        """
            Blacklists tracks (they will not be added to the library on
            collection scan
        """
        if not self.tracks: return
        result = common.yes_no_dialog(self.window, _("Blacklisting the selected "
            "tracks will prevent them from being added to the library on"
            " rescan.  Are you sure you want to continue?"))
        if result == gtk.RESPONSE_YES:
            self.tracks.delete_tracks(None, 'blacklist')

    def on_dequeue(self, item, param): 
        """
            Dequeues the selected tracks
        """
        tracks = self.tracks.get_selected_tracks()
        for track in tracks:
            try: self.queued.remove(track)
            except ValueError: pass
            
        self.tracks.queue_draw()
        trackslist.update_queued(self)

    def on_queue(self, item, param, toggle=True): 
        """
            Queues the selected tracks to be played after the current lineup
        """
        songs = self.tracks.get_selected_tracks()

        first = True
        for track in songs:
            if track in self.queued:
                if toggle:
                    self.queued.remove(track)
            elif first and track.is_playing():
                pass
            else:
                self.queued.append(track)

            first = False

        self.tracks.queue_draw()
        trackslist.update_queued(self)

    def setup_left(self): 
        """
            Sets up the left panel
        """
        self.playlists_panel = panels.PlaylistsPanel(self)
        self.collection_panel = panels.CollectionPanel(self)
        self.radio_panel = panels.RadioPanel(self)
        self.side_notebook = self.xml.get_widget('side_notebook')
        self.files_panel = panels.FilesPanel(self)
        self.device_panel = panels.DevicePanel(self)
        self.device_panel_widget = self.side_notebook.get_nth_page(4)
        self.device_panel_label = self.side_notebook.get_tab_label(
            self.device_panel_widget)

        self.side_notebook.remove_page(-1)
        self.device_panel_showing = False

    def show_device_panel(self, show):
        """
            Toggles whether or not the device panel is showing
        """
        if not self.device_panel_showing and show:
            self.side_notebook.append_page(self.device_panel_widget,
                self.device_panel_label)
        elif self.device_panel_showing and not show:
            self.side_notebook.remove_page(
                self.side_notebook.page_num(self.device_panel_widget))

        self.device_panel_showing = show

    def get_database(self):
        """
            Returns a new database connection
        """
        loc = "%s%smusic.db" % (SETTINGS_DIR, os.sep)
        database = db.DBManager(loc)
        database.add_function_create(('THE_CUTTER', 1, tracks.the_cutter))
        return database

    def database_connect(self):
        """
            Connects to the database
        """

        im = False
        if not os.path.isfile("%s%smusic.db" % (SETTINGS_DIR,
            os.sep)):
                im = True
        try:
            self.db = self.get_database()
        except db.DBOperationalError, e:
            common.error(self.window, _("Error connecting to database: %s" %
                str(e)))
            sys.exit(1)
        if im:
            try:
                self.db.import_sql("sql/db.sql")
            except db.DBOperationalError, e:
                common.error(self.window, "Error "
                    "creating collection database: %s" % (str(e)))
                sys.exit(1)

        # here we check for the "version" table.  If it's there, it's an old
        # style (0.2.6) database, so we upgrade it
        else:
            try:
                cur = self.db.realcursor()
                cur.execute('SELECT version FROM version')
                cur.close()
                self.db = db.convert_to027(self.db.db_loc)
                self.db.add_function_create(('THE_CUTTER', 1, 
                    tracks.the_cutter))
            except:
                pass # db is ok, continue!                

        self.db.check_version("sql")

    @common.threaded
    def load_songs(self, updating=False, first_run=False): 
        """
            Loads the entire library from the database
        """
        gobject.idle_add(self.status.set_first, 
            _("Loading library from database..."))

        if not updating:
            xlmisc.log("loading tracks...")
            self.all_songs = tracks.load_tracks(self.db, 
                self.all_songs)
            self.db._close_thread()
            gobject.idle_add(self.setup_gamin)
            xlmisc.log("done loading tracks...")
        gobject.idle_add(self.status.set_first, None)

        self.collection_panel.songs = self.all_songs
        self.collection_panel.track_cache = dict()

        if not updating:
            xlmisc.log("loading songs")
            gobject.idle_add(self.playlists_panel.load_playlists)
            gobject.idle_add(self.collection_panel.load_tree, True)
            
        if len(sys.argv) > 1 and sys.argv[1] and \
            not sys.argv[1].startswith("-"):
            if sys.argv[1].endswith(".m3u") or sys.argv[1].endswith(".pls"):
                gobject.idle_add(self.import_m3u, sys.argv[1], True)
            else:
                if not self.tracks: self.new_page("Last", [])
        if first_run: 
            gobject.idle_add(self.load_last_playlist)
            if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
                f = sys.argv[1]
                if f.endswith('.m3u') or f.endswith('.pls'):
                    self.import_m3u(f, True)
                else:
                    gobject.idle_add(self.stream, f)

    def setup_gamin(self, skip_prefs=False):
        """
            Sets up gamin to monitor directories for changes
        """
        self.db.db.commit()
        if not self.settings.get_boolean('watch_directories', False) \
            and not skip_prefs: return
        if not GAMIN_AVAIL:
            xlmisc.log("Gamin not available, not watching directories")
            return
    
        xlmisc.log("Setting up directory monitoring with gamin...")

        self.mon = gamin.WatchMonitor()

        items = []
        tmp = self.settings.get("search_paths", "").split(":")
        for i in tmp:
            if i != "": items.append(i)

        # check directories for changes since the last time we ran
        scan = []
        cur = self.db.cursor()
        for item in items:
            for root, dirs, files in os.walk(item):
                for dir in dirs:
                    dir = os.path.join(root, dir)
                    mod = os.path.getmtime(dir)
                    cur.execute("SELECT paths.name, modified FROM "
                        "directories,paths WHERE directories.path=paths.id "
                        "AND paths.name=?", (dir,))
                    row = cur.fetchone()
                    if not row or int(row[1]) != mod:
                        path_id = tracks.get_column_id(self.db, 'paths',
                            'name', dir)
                        self.db.execute("REPLACE INTO directories( path, "
                            "modified) VALUES( ?, ? )", (path_id, mod))
                        scan.append(dir)


        for item in items:
            if item in self.gamin_watched: continue
            self.mon.watch_directory(item, lambda path, event, dir=item:
                self.directory_changed(dir, path, event))      

            self.gamin_watched.append(item)

        self.mon.handle_events()
        if scan:
            xlmisc.log("Scanning new directories...")
            self.update_library(scan)

    @common.synchronized
    def directory_changed(self, directory, path, event):
        """
            Called when a changes happens in a directory
        """
        # if it matches the exclude directories, ignore it
        items = self.settings.get('watch_exclude_dirs', 'incomplete').split()
        for item in items:
            if item and (directory.find(item) > -1
                or path == item):
                return

        d = os.path.join(directory, path)
        if os.path.isdir(d) and not d in self.gamin_watched:
            self.mon.watch_directory(d, lambda path, event, dir=d:
                self.directory_changed(dir, path, event))
            self.gamin_watched.append(d)
            return

        if event != 8 and event != 9:
            path_id = tracks.get_column_id(self.db, 'paths', 'name', 
                os.path.join(directory, path))

            if os.path.isdir(os.path.join(directory, path)) and event == 5:
                self.mon.watch_directory(os.path.join(directory, path), 
                    lambda path, event, dir=os.path.join(directory, path):
                    self.directory_changed(dir, path, event))
                mod = os.path.getmtime(os.path.join(directory, path))
                self.gamin_watched.append(os.path.join(directory, path))

                self.db.execute("REPLACE INTO directories( path, modified ) "
                    "VALUES( ?, ? )", (path_id, mod))
                xlmisc.log("Dir created event on %s" % os.path.join(directory, path))
                return

            mod = os.path.getmtime(directory)
            self.dir_queue.append(directory)
            self.db.execute("UPDATE directories SET modified=? "
                "WHERE path=?", (mod, path_id))

    def run_dir_queue(self):
        """
            Runs one directory in the dir queue
        """
        if not self.dir_queue: return
        new = []

        # remove dups
        for item in self.dir_queue:
            if not item in new:
                new.append(item)

        self.dir_queue = new
        item = self.dir_queue.pop(0)
        xlmisc.log("Running gamin queued item %s" % item)

        tracks.populate(self, self.db,
            (item,), self.on_library_update, False, 
            load_tree=False)
   
    @common.threaded
    def update_songs(self, songs=None, set=True): 
        """
            Sets the songs and playlist songs
        """
        tracks = self.tracks
        if not songs: songs = tracks.songs
        self.songs = songs
        self.playlist_songs = songs

        if not tracks: return

        if set: gobject.idle_add(tracks.set_songs, songs)

    def timer_update(self, event=None): 
        """
            Fired every half second.
            Updates the seeker position, the "now playing" title, and
            submits the track to last.fm when appropriate
        """
        self.status.set_track_count("%d showing, %d in collection" % (len(self.songs),
            len(self.all_songs)))   
        track = self.current_track
        if GAMIN_AVAIL and self.mon:
            self.mon.handle_events()

        # run the gamin changes queue and flush configuration every 4 laps
        if self.timer_count % 4 == 0:
            self.run_dir_queue()
            self.settings.save()

        self.timer_count += 1
        self.rewind_track += 1

        if track == None: 
            return True
        duration = track.duration * 1000000000 # this is gst.SECOND

        # update the progress bar/label
        value = track.current_position()
        if duration == -1:
            real = 0
        else:
            real = value * duration / 100
        seconds = real / 1000000000 # this is gst.SECOND
        self.progress.set_value(value)
        self.progress_label = self.xml.get_widget('progress_label')

        if track.duration.stream:
            if track.start_time and track.is_playing():
                seconds = time.time() - track.start_time
                self.progress_label.set_label("%d:%02d" % (seconds / 60, seconds %
                    60))
        else:
            self.progress_label.set_label("%d:%02d" % (seconds / 60, seconds % 60))

        if not track.submitting and (seconds > 240 or value > 50): 
            self.update_rating(track, plays="plays + 1",
                rating="rating + 1")
            if track.submit_to_scrobbler() and \
                track.get_scrobbler_session() != None:
                track.submitting = True
                self.status.set_first(_("Submitting to Last.fm..."), 2000)

        return True

    def update_track_information(self, event=None):
        """
            Updates track status information
        """
        self.rating_combo.disconnect(self.rating_signal)
        track = self.current_track

        self.artist_label = self.xml.get_widget('artist_label')
        if track == None:
            self.progress_label.set_label('0:00')
            self.title_label.set_label('Not Playing')
            self.artist_label.set_label('Stopped')
            self.rating_combo.set_active(0)
            self.rating_combo.set_sensitive(False)

            self.rating_signal = self.rating_combo.connect('changed',
                self.set_rating)
            return

        album = track.album
        artist = track.artist
        if album == "": album = "Unknown"
        if artist == "": artist = "Unknown"

        self.title_label.set_label(track.title)

        # set up the playing/track labels based on the type of track
        if isinstance(track, media.RadioTrack):
            self.artist_label.set_label(track.artist)
            self.window.set_title("Exaile %s on %s" % (track.title,
                track.artist))
        elif isinstance(track, media.StreamTrack):
            self.window.set_title("Exaile %s" % track.title)
            self.artist_label.set_label(track.album)
        else:
            self.window.set_title("Exaile: playing %s from %s by %s" %
                (track.title, album, artist))
            self.artist_label.set_label("from %s\nby %s" % (album, artist))

        if self.tray_icon:
            self.tray_icon.set_tooltip(self.window.get_title())

        row = self.db.read_one("tracks, paths", "paths.name, user_rating", 
            "paths.name=? AND paths.id=tracks.path", (track.loc,))

        if not row:
            self.rating_combo.set_active(0)
            self.rating_combo.set_sensitive(False)
        else:
            rating = row[1]
            if rating <= 0 or rating == '' or rating is None: 
                rating = 0
            self.rating_combo.set_active(rating - 1)
            track.user_rating = rating
            self.rating_combo.set_sensitive(True)

        self.rating_signal = self.rating_combo.connect('changed',
            self.set_rating)

    def update_rating(self, track, **info): 
        """
            Adds one to the "plays" of this track
        """

        update_string = []
        for k, v in info.iteritems():
            update_string.append("%s = %s" % (k, v))

        update_string = ", ".join(update_string)

        path_id = tracks.get_column_id('paths', 'name', track.loc)
        self.db.execute("UPDATE tracks SET %s WHERE path=?" % update_string, 
            (path_id,))

    def got_covers(self, covers): 
        """
            Gets called when all covers have been downloaded from amazon
        """
        track = self.current_track
        artist_id = tracks.get_column_id(self.db, 'artists', 'name', track.artist)
        album_id = tracks.get_album_id(self.db, artist_id, track.album)

        self.status.set_first(None)
        if len(covers) == 0:
            self.status.set_first(_("No covers found."), 2000)
            self.db.execute("UPDATE albums SET image='nocover' WHERE id=?",
                (album_id,))

        # loop through all of the covers that have been found
        for cover in covers:
            if(cover['status'] == 200):
                cover.save("%s%scovers" % (SETTINGS_DIR, os.sep))
                xlmisc.log(cover['filename'])
                self.cover.set_image(cover['filename'])

                self.db.execute("UPDATE albums SET image=? WHERE id=?",
                    (cover['md5'] + ".jpg", album_id))
                
                break
   
    def fetch_cover(self, track, popup=None): 
        """
            Fetches the cover from the database.  If it can't be found
            there it fetches it from amazon
        """
        w = self.cover_width
        if not popup:
            self.cover.set_image("images%snocover.png" % os.sep)
        if track == None: return
        artist_id = tracks.get_column_id(self.db, 'artists', 'name', track.artist)
        album_id = tracks.get_album_id(self.db, artist_id, track.album)

        # check to see if a cover already exists
        row = self.db.read_one("albums", "image", 'id=?', (album_id,))

        if row != None and row[0] != "" and row[0] != None:
            if row[0] == "nocover": 
                cover = self.fetch_from_fs(track)
                if cover:
                    self.cover.set_image(cover)
                    return
                return "images%snocover.png" % os.sep
            if os.path.isfile("%s%scovers%s%s" %
                (SETTINGS_DIR, os.sep, os.sep, row[0])):

                if popup: return "%s%scovers%s%s" % \
                    (SETTINGS_DIR, os.sep, os.sep, row[0])

                self.cover.set_image("%s%scovers%s%s" %
                    (SETTINGS_DIR, os.sep, os.sep, row[0]))
                return

        cover = self.fetch_from_fs(track)
        if cover:
            if popup: return cover
            else: self.cover.set_image(cover)
            return

        if popup != None: return "images%snocover.png" % os.sep
        self.stop_cover_thread()

        if self.settings.get_boolean("fetch_art", True):
            locale = self.settings.get('amazon_locale', 'us')
            self.cover_thread = covers.CoverFetcherThread("%s - %s" %
                (track.artist, track.album),
                self.got_covers, locale=locale)

            self.status.set_first(_("Fetching cover art from Amazon..."))
            self.cover_thread.start()
            
    def fetch_from_fs(self, track, event=None):
        """
            Fetches the cover from the filesystem (if there is one)
        """
        dir = os.path.dirname(track.loc)

        names = self.settings.get('art_filenames', 
            'cover.jpg folder.jpg .folder.jpg album.jpg art.jpg')
        if not names: return None
        names = names.split(" ")

        for f in names:
            f = f.strip()
            if os.path.isfile("%s%s%s" % (dir, os.sep, f)):
                return "%s%s%s" % (dir, os.sep, f)

        return None

    def stop_cover_thread(self): 
        """
            Aborts the cover thread
        """

        if self.cover_thread != None:
            xlmisc.log("Aborted cover thread")
            self.cover_thread.abort()
            self.cover_thread = None
    
    def setup_right(self): 
        """
            Sets up the right side of the sash (this is the playlist area)
        """
        self.cover = xlmisc.ImageWidget()
        self.cover.set_image_size(self.cover_width, self.cover_width)
        self.cover_box = gtk.EventBox()
        self.cover_box.add(self.cover)
        self.xml.get_widget('image_box').pack_start(self.cover_box)
        self.cover.set_image('images%snocover.png' % os.sep)

        # set the font/etc 
        self.title_label = self.xml.get_widget('title_label')
        attr = pango.AttrList()
        attr.change(pango.AttrWeight(pango.WEIGHT_BOLD, 0, 800))
        attr.change(pango.AttrSize(12500, 0, 600))
        self.title_label.set_attributes(attr)
        self.setup_cover_menu()

    def setup_cover_menu(self):
        """
            Sets up the menu for when the user right clicks on the album cover
        """
        menu = xlmisc.Menu()
        self.cover_full = menu.append(_("View Full Image"),
            self.cover_menu_activate)
        self.cover_fetch = menu.append(_("Fetch from Amazon"),
            self.cover_menu_activate)
        self.cover_search = menu.append(_("Search Amazon"),
            self.cover_menu_activate)
        self.cover_custom = menu.append(_("Set Custom Image"),
            self.cover_menu_activate)
        self.remove_cover = menu.append(_("Remove Cover"),
            self.remove_cover)
        self.cover_menu = menu

    def remove_cover(self, item, param=None):
        """
            removes the cover art for the current track
        """
        track = self.current_track
        if not track: return

        artist_id = tracks.get_column_id(self.db, 'artists', 'name',
            track.artist)
        album_id = tracks.get_album_id(self.db, artist_id, track.album)

        self.db.execute("UPDATE albums SET image='nocover' WHERE id=?", (album_id,))
        self.cover.set_image("images%snocover.png" % os.sep)

    def cover_menu_activate(self, item, user_param=None): 
        """
            Called when one of the menu items in the album cover popup is
            selected
        """
        if item == self.cover_fetch:
            self.status.set_first(_("Fetching from amazon..."))
            xlmisc.CoverFrame(self, self.current_track)
        elif item == self.cover_search:
            xlmisc.CoverFrame(self, self.current_track, True)
        elif item == "showcover" or item == self.cover_full:
            if self.cover.loc.find("nocover") > -1: return
            track = self.current_track
            xlmisc.CoverWindow(self.window, self.cover.loc, "%s by %s" %
                (track.album, track.artist))
        elif item == self.cover_custom:
            track = self.current_track
            wildcard = ['*.jpg', '*.jpeg', '*.gif', '*.png', '*.*'] 
            filter = gtk.FileFilter()
            for pattern in wildcard:
                filter.add_pattern(pattern)

            dialog = gtk.FileChooserDialog(_("Choose an image"), self.window,
                buttons=('Open', gtk.RESPONSE_OK, 'Cancel',
                gtk.RESPONSE_CANCEL))
            dialog.set_filter(filter)
            dialog.set_current_folder(self.get_last_dir())

            result = dialog.run()
            dialog.hide()

            if result == gtk.RESPONSE_OK:
                self.last_open_dir = dialog.get_current_folder()
                handle = open(dialog.get_filename(), "r")
                data = handle.read()
                handle.close()

                (f, ext) = os.path.splitext(dialog.get_filename())
                newname = md5.new(data).hexdigest() + ext
                handle = open("%s%scovers%s%s" %
                    (self.get_settings_dir(), os.sep, os.sep,
                    newname), "w")
                handle.write(data)
                handle.close()

                path_id = tracks.get_column_id(self.db, 'paths', 'name',
                    track.loc)
                artist_id = tracks.get_column_id(self.db, 'artists', 'name',
                    track.artist)
                album_id  = tracks.get_album_id(self.db, artist_id,
                    track.album)

                xlmisc.log(newname)

                self.db.execute("UPDATE albums SET image=? WHERE id=?",
                    (newname, album_id))

                if track == self.current_track:
                    self.stop_cover_thread()
                    self.cover.set_image("%s%scovers%s%s" %
                        (self.get_settings_dir(), os.sep, os.sep,
                        newname))

    @common.synchronized
    def new_page(self, title=_("Playlist"), songs=None):
        """
            Create a new tab with the included title with the specified type
        """
        # if there is currently only one tab, and it's an empty "Playlist"
        # tab, remove it before adding this new one
        if self.playlists_nb.get_n_pages() == 1:
            page = self.playlists_nb.get_nth_page(0)
            tab = self.playlists_nb.get_tab_label(page)
            if tab.title == _("Playlist") and self.tracks and not \
                self.tracks.songs:
                self.playlists_nb.remove_page(0)
        
        if not songs: songs = tracks.TrackData()
        self.tracks = trackslist.TracksListCtrl(self)
        self.tracks.playlist_songs = songs 
        tab = xlmisc.NotebookTab(self, title, self.tracks)
        self.playlists_nb.append_page(self.tracks, tab)
        self.playlists_nb.set_current_page( 
            self.playlists_nb.get_n_pages() - 1)
        self.update_songs(songs)

    def close_page(self, page=None): 
        """
            Called when the user clicks "Close" in the notebook popup menu
        """
        nb = self.playlists_nb
        if not page:
            i = self.playlists_nb.get_current_page()
            page = self.playlists_nb.get_nth_page(i)
            page.close_page()
            if i > -1:
                self.playlists_nb.remove_page(i)
        else:
            for i in range(0, nb.get_n_pages()):
                p = nb.get_nth_page(i)
                if p == page:
                    page.close_page()
                    nb.remove_page(i)
                    break

        self.tracks = None

        if self.playlists_nb.get_n_pages() == 0:
            self.new_page(_("Playlist"))
            return False

        num = nb.get_current_page()
        self.page_changed(nb, None, num)
        return False

    def clear_playlist(self, widget): 
        """
            Clears the current playlist
        """

        if self.tracks == None:
            self.new_page()

        self.tracks.set_songs(tracks.TrackData())
        self.tracks.playlist_songs = self.tracks.songs
        self.playlist_songs = self.tracks.songs
        self.songs = self.tracks.songs
    
    def on_search(self, widget=None, event=None, custom=True): 
        """
            Called when something is typed into the filter box
        """

        keyword = self.tracks_filter.get_text()
        if keyword.startswith("where ") and not widget: return
        if keyword == "": keyword = None
        self.songs = tracks.search(self, self.tracks.playlist_songs, keyword,
            custom=custom)
        self.tracks.set_songs(self.songs, False)

    def volume_scroll(self, widget, ev):
        """
            Called when the user scrolls their mouse wheel over the tray icon
        """
        v = widget.get_value()
        if ev.direction == gtk.gdk.SCROLL_RIGHT or ev.direction == \
            gtk.gdk.SCROLL_UP:
            v += 9
        else:
            v -= 9

        if v < 0: v = 0
        elif v > 120: v = 120

        self.on_volume_set(self.volume, None, v)
        return True

    def on_volume_set(self, range, scroll, value): 
        """
            Sets the volume based on the slider position
        """

        media.set_volume(float(value) / 100.0)
        self.settings['volume'] = value / 100.0
        self.emit('volume-changed', value)        
        self.volume.disconnect(self.volume_id)
        self.volume.set_value(value)
        self.volume_id = self.volume.connect('change-value',
            self.on_volume_set)

    def seek(self, range, scroll, value): 
        """
            Seeks in the current track
        """
        if not self.current_track or \
            isinstance(self.current_track, media.StreamTrack):
            self.progress.set_value(0)
            return
        duration = self.current_track.duration
        real = long(range.get_value() * duration / 100)
        self.current_track.seek(real)
        self.current_track.submitting = True
        self.emit('seek', real)

    def play_track(self, track): 
        """
            Plays a track, gets the cover art, and sets up the context panel
        """
        if isinstance(track, media.PodcastTrack):
            if not track.download_path:
                common.error(self.window, _("Podcast has not yet been "
                    "downloaded"))
                return
        track.play(self.on_next)
        self.play_button.set_image(self.get_pause_image())
        self.current_track = track
        self.update_track_information()
        self.played.append(track)

        artist_id = tracks.get_column_id(self.db, 'artists', 'name', track.artist)
        tracks.get_album_id(self.db, artist_id, track.album)

        if track.type != 'stream' and self.settings.get_boolean('fetch_covers', True):
            self.fetch_cover(track)

        self.show_osd()
        if self.tracks: self.tracks.queue_draw()

        if self.settings.get_boolean('ensure_visible', False):
            self.goto_current()

        trackslist.update_queued(self)
        xl.track.update_info(self.playlists_nb, track)

        # if we're in dynamic mode, find some tracks to add
        if self.dynamic.get_active():
            thread.start_new_thread(self.get_suggested_songs, tuple())

        # PLUGIN: send plugins events of this playing track
        self.emit('play-track', track)

        track.last_played = time.strftime("%Y-%m-%d %H:%M:%S",
            time.localtime())

        path_id = tracks.get_column_id(self.db, 'paths', 'name', track.loc)
        self.db.execute("UPDATE tracks SET last_played=? WHERE path=?",
            (track.last_played, track.loc))
        gc.collect()
        self.rewind_track = 0

    def get_suggested_songs(self):
        """
            Gets suggested tracks from last.fm
        """
        if not self.tracks or not self.current_track: return

        played = 0
        for song in self.songs:
            if song in self.played:
                played += 1

        count = 5 - (len(self.songs) - played)
        xlmisc.log("suggested song count is %d" % count)
        if count <= 0: count = 1

        songs = tracks.get_suggested_songs(self, self.db, 
            self.current_track, self.songs, count, self.add_suggested)

    def add_suggested(self, artists, count):
        """
            adds suggested tracks that were fetched
        """
        songs = tracks.TrackData()
        for artist in artists:
            rows = self.db.select("SELECT paths.name FROM artists,tracks,paths WHERE " 
                "tracks.path=paths.id AND artists.id=tracks.artist AND "
                "artists.name=?", (unicode(artist),))
            if rows:
                search_songs = []
                for row in rows:
                    song = self.all_songs.for_path(row[0])
                    if song:
                        search_songs.append(song)

                if search_songs:
                    random.shuffle(search_songs)
                    song = search_songs[0]
                    if not song in self.tracks.songs \
                        and not song in self.played and not \
                        song in self.queued:
                        songs.append(song)

            if len(songs) >= count: break

        if not songs:
            self.status.set_first("Could not find any"
            " suggested songs", 4000)

        for song in songs:
            self.tracks.append_song(song)

        self.update_songs(None, False)

    def show_osd(self, tray=False):
        """
            Shows a popup window with information about the current track
        """
        if not self.settings.get_boolean("use_popup", True): return
        if tray:
            if not self.settings.get_boolean('osd_tray', True): return
        track = self.current_track
        if not track: return
        pop = xlmisc.get_osd(self, xlmisc.get_osd_settings(self.settings))
        cover = self.fetch_cover(track, 1)

        text_display = self.settings.get('osd_display_text',
            xl.prefs.TEXT_VIEW_DEFAULT)
        pop.show_track_osd(track, text_display,
            cover)

    def setup_menus(self):
        """
            Sets up menus
        """
        self.shuffle = self.xml.get_widget('shuffle_button')
        self.shuffle.set_active(self.settings.get_boolean('shuffle', False))
        self.shuffle.connect('toggled', self.toggle_mode, 'shuffle')

        self.repeat = self.xml.get_widget('repeat_button')
        self.repeat.set_active(self.settings.get_boolean('repeat', False))
        self.repeat.connect('toggled', self.toggle_mode, 'repeat')

        self.dynamic = self.xml.get_widget('dynamic_button')
        self.dynamic.set_active(self.settings.get_boolean('dynamic', False))
        self.dynamic.connect('toggled', self.toggle_mode, 'dynamic')

    def toggle_mode(self, item, param):
        """
            Toggles the settings for the specified playback mode
        """
        self.settings.set_boolean(param, item.get_active())

    def on_next(self, widget=None, event=None): 
        """
            Finds out what track is next and plays it
        """

        self.stop()
        if self.tracks == None: return

        track = self.tracks.get_next_track(self.current_track)
        if not track: 
            if not self.tracks.get_songs():
                if not self.queued: return
            else: track = self.tracks.get_songs()[0]

        if self.next != None and not self.queued:
            track = self.tracks.get_next_track(self.next)
            if not track: track = self.tracks.get_songs()[0]
            self.next = None

        if self.current_track != None:
            if self.current_track.current_position() < 50:
                self.update_rating(self.current_track, rating="rating - 1")
            self.history.append(self.current_track)

        # for queued tracks
        if len(self.queued) > 0:
            if self.next == None:
                self.next = self.current_track
            track = self.queued[0]
            if not track in self.tracks.songs:
                self.tracks.append_song(track)
            self.queued = self.queued[1:len(self.queued)]
            xlmisc.log("Playing queued track '%s'" % track)

            # if the track isn't currently showing in search results
            self.play_track(track)
            self.current_track = track
            self.played.append(track)
            return
        else:
            # for shuffle mode
            if self.shuffle.get_active():

                count = 0
                while True:
                    if len(self.songs) == 0: return
                    current_index = \
                        random.randint(0, len(self.songs) - 1)
                    track = self.tracks.songs[current_index]
                    if count >= 500 or track not in \
                        self.played:

                        if track in self.played:
                            for track in self.tracks.songs:
                                if not track in self.played:
                                    break
                            self.played = [] # all songs have been played
                            if not self.repeat.get_active():
                                return
                        break

                    count = count + 1

        if not self.shuffle.get_active() and \
            not self.tracks.get_next_track(self.current_track):
            if self.repeat.get_active(): 
                self.current_track = self.tracks.get_songs()[0]
            else:
                self.played = []
                if self.current_track: return

        self.play_track(track)
        self.current_track = track
    
    def on_previous(self, widget=None, event=None): 
        """
            Plays the previous track in the history
        """

        # if the current track has been playing for 5 seconds, just restart it
        if self.rewind_track >= 6:
            track = self.current_track
            if track:
                track.stop()
                track.play(self.on_next)
                self.rewind_track = 0
            return

        # otherwise go back in the history
        if len(self.history) > 0:
            self.stop()
            track = self.history.pop()
            self.play_track(track)
            self.current_track = track

    def toggle_pause(self, widget=None, event=None):
        """
            Pauses the current track
        """
        track = self.current_track
        if not track:
            self.play()
            return

        if track.is_paused(): 
            self.play_button.set_image(self.get_pause_image())
            track.play()
        elif track.is_playing(): 
            self.play_button.set_image(self.get_play_image())
            track.pause()
        if self.tracks: self.tracks.queue_draw()
        self.emit('pause-toggled', self.current_track)
    
    def play(self, treeview=None, path=None, column=None): 
        """
            Called when someone double clicks on a track or presses the play
            button.  If the track is already playing, it is restarted
        """
        
        self.stop()

        if self.tracks == None: return

        self.last_played = self.current_track
        track = self.tracks.get_selected_track()
        if not track: 
            if self.tracks.songs:
                self.on_next()
                return
            else: return

        if track in self.queued: del self.queued[self.queued.index(track)]
        self.current_track = track
        self.played = []
        self.play_track(track)

    def stop(self, event=None): 
        """
            Stops playback
        """
        self.status.set_first(None)
        self.cover.set_image("images%snocover.png" % os.sep)
        self.stop_cover_thread()

        self.playing = False
        if self.tray_icon:
            self.tray_icon.set_tooltip("Exaile Media Player")
        self.window.set_title("Exaile!")

        track = self.current_track
        if track != None: 
            track.stop()
            # PLUGIN: alert plugins that this track has stopped playing
            self.emit('stop-track', track)

        if event != None:
            self.played = []
            self.current_track = None

        self.play_button.set_image(self.get_play_image())
        if self.tracks: self.tracks.queue_draw()

        self.update_track_information()
        self.progress.set_value(0)

    def import_m3u(self, path, play=False, title=None, newtab=True): 
        """
            Imports a playlist file, regardless of it's location (it can be
            a local file (ie, file:///somefile.m3u) or online.
        """
        xlmisc.log("Importing %s" % path)
        self.status.set_first("Importing playlist...")
        xlmisc.finish()

        url = list(urlparse.urlsplit(path))
        if not url[0]: #local file
            url [0] = 'file'
            url [2] = os.path.abspath(os.path.expanduser(url[2]))
        path = urlparse.urlunsplit(url)

        name = os.path.basename(os.path.splitext(url[2])[1]).replace("_", " ")
        file = urllib.urlopen(path)

        
        if file.readline().strip() == '[playlist]':
            file.close()
            playlist = xlmisc.PlsParser(name,path)
        else:
            file.close()
            playlist = xlmisc.M3UParser(name,path)

        first = True
        songs = tracks.TrackData()
        t = trackslist.TracksListCtrl

        count = 0
        for url in playlist.get_urls():
            if url[0] == 'device': continue
            elif url[0] == 'file':
                if self.all_songs.for_path(url[2]):
                    tr = self.all_songs.for_path(url[2])
                else:
                    tr = tracks.read_track(self.db, self.all_songs, url[2], adddb=False)
                  
            else:
                tr = media.RadioTrack({
                    'url':urlparse.urlunsplit(url),
                    'title':'Radio Stream'
                    })
                if first and play:
                    play = tr
                    
                if isinstance(tr, media.StreamTrack):
                    name = "Stream"

            if tr:
                songs.append(tr)

            if count >= 10:
                xlmisc.finish()
                count = 0

            count += 1
            first = False

        self.db.commit()
        if title: name = title
        if not songs: 
            self.status.set_first(None)
            return
        
        if newtab:
            self.new_page(name, songs)
        else:
            self.append_songs(songs, play=False)

        if isinstance(play, media.StreamTrack):
            self.stop()
            self.play_track(play)

        self.status.set_first(None)
    
    def get_last_dir(self):
        """
            Gets the last working directory
        """

        try:
            f = self.last_open_dir
        except:
            self.last_open_dir = self.settings.get('last_open_dir',
                os.getenv('HOME'))
        return self.last_open_dir

    def on_add_media(self, item, event=None): 
        """
            Adds media to the current selected tab regardless of whether or
            not they are contained in the library
        """
        types = media.SUPPORTED_MEDIA
        wildcard = ['*%s' % t for t in types]
        wildcard.extend(['.pls', '.m3u'])
        wildcard.append('*')

        filter = gtk.FileFilter()
        for pattern in wildcard:
            filter.add_pattern(pattern)

        dialog = gtk.FileChooserDialog(_("Choose a file"), self.window,
            buttons=('Open', gtk.RESPONSE_OK, 'Cancel', gtk.RESPONSE_CANCEL))

        new_tab = gtk.CheckButton(_("Open in new tab"))
        dialog.set_extra_widget(new_tab)
        dialog.set_current_folder(self.get_last_dir())
        dialog.set_filter(filter)
        dialog.set_select_multiple(True)

        result = dialog.run()
        dialog.hide()

        if result == gtk.RESPONSE_OK:
            paths = dialog.get_filenames()
            self.last_open_dir = dialog.get_current_folder()
            self.status.set_first(_("Populating playlist..."))
            songs = tracks.TrackData()

            count = 0
            for path in paths:
                (f, ext) = os.path.splitext(path)
                if ext in types:
                    if count >= 10:
                        xlmisc.finish()
                        count = 0
                    tr = tracks.read_track(self.db, self.all_songs, path, 
                        adddb=False)

                    count = count + 1
                    if tr:
                        songs.append(tr)
                if ext in (".m3u", ".pls"):
                    self.import_m3u(path, newtab=new_tab.get_active())

            if songs:
                if new_tab.get_active():
                    self.new_page(_("Playlist"), songs)
                else:
                    self.append_songs(songs)

            self.status.set_first(None)

    def export_playlist(self, item): 
        """
            Exports the current selected playlist as a .m3u file
        """
        wildcard = ['*.m3u', '*.pls']
        filter = gtk.FileFilter()
        for w in wildcard:
            filter.add_pattern(w)

        dialog = gtk.FileChooserDialog(_("Choose a file"),
            self.window, gtk.FILE_CHOOSER_ACTION_SAVE, 
            buttons=('Save', gtk.RESPONSE_OK, 'Cancel',
            gtk.RESPONSE_CANCEL))
        dialog.set_current_folder(self.get_last_dir())
        dialog.set_filter(filter)

        result = dialog.run()
        dialog.hide()

        if result == gtk.RESPONSE_OK:
            path = dialog.get_filename()
            self.last_open_dir = dialog.get_current_folder()
            handle = open(path, "w")
            handle.write("#EXTM3U\n")

            for track in self.playlist_songs:
                handle.write("#EXTINF:%d,%s\n%s\n" % (track.duration,
                    track.title, track.loc))

            handle.close()

    def get_volume_percent(self):
        """
            Returns the current volume level as a percent
        """
        vol = self.volume.get_value()
        percent = float(vol) / 120.0
        return int(percent * 100)

    def stream(self, url): 
        """
            Play a radio stream
        """
        self.stop()

        # if it's a .m3u or .pls
        if url.lower().endswith(".m3u") or \
            url.lower().endswith(".pls"):
            self.import_m3u(url, True)
            return
        elif url.find("://") == -1:
            track = tracks.read_track(self.db, self.all_songs, url,
                adddb=False)
        else:
            info = ({'url': url})
            track = media.RadioTrack(info)

        songs = tracks.TrackData((track, ))
        if not songs: return

        self.append_songs(songs)
        self.play_track(track)

    def open_url(self, event): 
        """
            Prompts for a url to open
        """
        dialog = xlmisc.TextEntryDialog(self.window,
            _("Enter the address"), _("Enter the address"))
        result = dialog.run()
        dialog.dialog.hide()

        if result == gtk.RESPONSE_OK:
            path = dialog.get_value()
            self.stream(path)

    def open_disc(self, widget):
        """
            Opens an audio disc
        """
        songs = xl.tracks.read_audio_disc(self)
        if not songs: return
        self.new_page(_("Audio Disc"), songs)

    def fetch_covers(self, event):
        """
            Fetches all covers
        """
        fetcher = xlmisc.get_cover_fetcher(self)
        fetcher.dialog.show_all()

    def goto_current(self, *e): 
        """
            Ensures that the currently playing track is visible
        """
        if not self.tracks: return
        self.tracks.ensure_visible(self.current_track)

    def on_library_rescan(self, widget=None, event=None, data=None,
        load_tree=True): 
        """
            Rescans the library for newly added tracks
        """
        items = []
        tmp = self.settings.get("search_paths", "").split(":")
        for i in tmp:
            if i != "": items.append(i)

        if len(items): self.update_library(items, load_tree=load_tree)
    
    def update_library(self, items, done_func=None,
        load_tree=True): 
        """
            Updates the library
        """
        self.status.set_first(_("Scanning collection..."))

        tracks.populate(self, self.db,
            items, self.on_library_update, False,
            load_tree=load_tree, done_func=done_func)

    def on_library_update(self, percent, songs=None, done_func=None): 
        """
            Scans the library
        """
        self.collection_panel.update_progress(percent)
        
        if percent < 0:
            self.db.db.commit()
            self.db._cursor.close()
            self.db._cursor = self.db.realcursor()
            self.load_songs(percent==-1)

        if done_func:
            done_func(songs)

    def on_quit(self, widget=None, event=None): 
        """
            Saves the current playlist and exits
        """
        # PLUGIN: send plugins event before quitting
        self.emit('quit')
        if self.gamin_watched and self.mon:
            for item in self.gamin_watched:
                try:
                    self.mon.stop_watch(item)
                except gamin.GaminException:
                    pass

        if self.mon:
            self.mon.disconnect()

        self.window.hide()
        xlmisc.finish()
        if self.tray_icon and widget == self.window:
            return True

        self.stop()
        self.stop_cover_thread()
        for thread in self.thread_pool:
            thread.done = True

        dir = "%s%ssaved" % (SETTINGS_DIR, os.sep)
        if not os.path.isdir(dir):
            os.mkdir(dir)

        # delete all current saved playlists
        for file in os.listdir(dir):
            if file.endswith(".m3u"):
                os.unlink("%s%s%s" % (dir, os.sep, file))

        if os.path.isfile("%s%squeued.save" % (dir, os.sep)):
            os.unlink("%s%squeued.save" % (dir, os.sep))

        if self.current_track: self.current_track.stop()

        for i in range(self.playlists_nb.get_n_pages()):
            page = self.playlists_nb.get_nth_page(i)
            title = self.playlists_nb.get_tab_label(page).title
            if page.type != 'track': continue
            songs = page.songs
            h = open("%s%ssaved%splaylist%.4d.m3u" % 
                (SETTINGS_DIR, os.sep, os.sep, i), "w")
            h.write("# PLAYLIST: %s\n" % title)
            for song in songs:
                if isinstance(song, media.PodcastTrack): continue
                h.write("%s\n" % song.loc)

            h.close()

        # save queued tracks
        if self.queued:
            h = open("%s%squeued.save" % (dir, os.sep), "w")
            for song in self.queued:
                h.write("%s\n" % song.loc)
            h.close()
        self.db.db.commit()
        last_active = self.playlists_nb.get_current_page()
        self.settings['last_active'] = last_active

        gtk.main_quit()

    def on_resize(self, widget, event): 
        """
            Saves the current size and position
        """
        (width, height) = self.window.get_size()
        self.settings['mainw_width'] = width
        self.settings['mainw_height'] = height
        (x, y) = self.window.get_position()
        self.settings['mainw_x'] = x
        self.settings['mainw_y'] = y
        if self.splitter.get_position() > 10:
            sash = self.splitter.get_position()
            self.settings['mainw_sash_pos'] = sash
        return False

    def submit_to_scrobbler(self, event=None): 
        """
            Submits this track to audioscrobbler, regardless of how long the
            track has actually been playing
        """
        track = self.current_track
        if track == None: return
        if track.get_scrobbler_session() != None:
            self.current_track.submitting = False
            self.current_track.submit_to_scrobbler()
            self.status.set_first(_("Submitting to Last.fm..."), 2000)
    
    def jump_to(self, index):
        """
            Show the a specific page in the track information tab about
            the current track
        """
        track = self.current_track
        if not track and not self.tracks: return
        if not track: track = self.tracks.get_selected_track() 
        if not track: return
            
        page = xl.track.show_information(self, track)
        page.set_current_page(index)
        
def check_dirs():
    """
        Makes sure the required directories have been created
    """
    covers = "%s%scovers" % (SETTINGS_DIR, os.sep)
    cache = "%s%scache" % (SETTINGS_DIR, os.sep)
    if not os.path.isdir(covers):
        os.mkdir(covers)

    if not os.path.isdir(cache):
        os.mkdir(cache)
    
def first_run(): 
    """
        Called if the music database or settings files are missing.

        Creates the settings directory, and, if necessary, creates the initial
        database file.
    """
    try:
        os.mkdir(SETTINGS_DIR)
    except:
        print "Could not create settings directory"

# try to import mmkeys and gtk to allow support for the multimedia keys
try:
    import mmkeys
    MMKEYS_AVAIL = True
except ImportError:
    xlmisc.log("mmkeys are NOT available")
    MMKEYS_AVAIL = False

# try to import gpod for iPod support
try:
    import gpod
    IPOD_AVAIL = True
except ImportError:
    IPOD_AVAIL = False

try:
    import gamin
    GAMIN_AVAIL = True
except ImportError:
    GAMIN_AVAIL = False

def main(): 
    """
        Everything dispatches from this main function
    """
    global SETTINGS_DIR
    p = EXAILE_OPTIONS

    if HELP:
        p.print_help()
        sys.exit(0)

    options, args = p.parse_args()
    if options.settings:
        SETTINGS_DIR = options.settings
    elif options.dups:
        xlmisc.log("Searching for duplicates in: %s" % options.dups)
        track.find_and_delete_dups(options.dups)
        sys.exit(0)

    running_checks = ('next', 'prev', 'stop', 'play', 'guiquery', 'get_title',
        'get_artist', 'get_album', 'get_length', 'current_position',
        'inc_vol', 'dec_vol', 'query')


    # check passed arguments for options that require exaile to currently be
    # running
    if not DBUS_EXIT:
        for check in running_checks:
            if getattr(options, check):
                print "No running Exaile instance found."
                sys.exit(1)

        random.seed()
        fr = False
        if not os.path.isdir(SETTINGS_DIR):
            first_run()
            fr = True


        check_dirs()
        if options.stream: sys.argv[1] = options.stream
        
        exaile = ExaileWindow(options, fr)

        if MMKEYS_AVAIL:
            xlmisc.log("mmkeys are available.")
    else:
        sys.exit(0)
    gtk.main()

if __name__ == "__main__": 
    try:
        main()
    except SystemExit:
        pass
    except: 
        traceback.print_exc()
        xlmisc.log_exception()
