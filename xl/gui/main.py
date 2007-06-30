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

__version__ = '0.2.11svn'
import pygtk, pygst
pygtk.require('2.0')
pygst.require('0.10')

import gtk, gobject, gettext, os, sys, dbus, thread, pango, gtk.glade
import xl.dbusinterface, time
from gettext import gettext as _
from xl import library, media, audioscrobbler, equalizer, burn, common
from xl import xlmisc, config, db, covers, player, prefs
from xl import playlist as playlistmanager
import plugins.manager, plugins.gui, gst
from xl.gui import playlist as trackslist
from xl.panels import collection, radio, playlists, files, device
import random
random.seed()

class ExaileWindow(gobject.GObject): 
    """
        The main interface class
    """
    __gsignals__ = {
        'seek': (gobject.SIGNAL_RUN_LAST, None, (int,)),
        'quit': (gobject.SIGNAL_RUN_LAST, None, ()),
        'tray-icon-toggled': (gobject.SIGNAL_RUN_LAST, None, (bool,)),

        # called when the title label is changed (sometimes it changes when
        # the track hasn't changed, for example when you're listening to a
        # shoutcast stream)
        'track-information-updated': (gobject.SIGNAL_RUN_LAST, None, ()),
        'quit': (gobject.SIGNAL_RUN_LAST, None, ()),
    }
    __single = None

    # ExaileWindow should be a singleton
    @classmethod
    def get_instance(caller, settings_dir, options, first_run = False):
        """
            Use this to get the Exaile instance
        """
        if not ExaileWindow.__single:
            instance = ExaileWindow(settings_dir, options, first_run)
            ExaileWindow.__single = instance

        return ExaileWindow.__single

    def __init__(self, settings_dir, options, first_run = False): 
        """
            Initializes the main Exaile window
        """
        if ExaileWindow.__single:
            raise 'Exaile instance has already been created'

        gobject.GObject.__init__(self)
        self.settings_dir = settings_dir
        self.xml = gtk.glade.XML('exaile.glade', 'ExaileWindow', 'exaile')
        self.window = self.xml.get_widget('ExaileWindow')
        media.exaile_instance = self

        self.settings = config.Config("%s%ssettings.ini" % (self.settings_dir, os.sep))

        self.options = options
        config.settings = self.settings
        self.database_connect()
        self.all_songs = library.TrackData()
        self.songs = library.TrackData()
        self.playlist_songs = library.TrackData()
        self.library_manager = library.LibraryManager(self)
        self.tracks = None
        self.playlists_menu = None
        self.playlist_manager = playlistmanager.PlaylistManager(self)
        self.timer = xlmisc.MiscTimer(self.timer_update, 1000)
        self.cover_manager = covers.CoverManager(self)
        self.plugin_tracks = {}
        self.playing = False
        self.thread_pool = []
        self.dir_queue = []
        self.scan_timer = None
        self.seeking = False
        self.debug_dialog = xlmisc.DebugDialog(self)
        self.col_menus = dict()
        self.setup_col_menus('track', trackslist.TracksListCtrl.col_map)
        self.plugins_menu = xlmisc.Menu()
        self.rewind_track = 0
        self.player = player.ExailePlayer(self)
        self.player.tag_func = self.tag_callback

        if self.settings.get_boolean("ui/use_splash", True):
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

        self.tray_icon = None

        self.volume = xlmisc.Adjustment(0, 0, 100, 1, 10, 0)
        self.volume.connect('value-changed', self.__on_volume_changed)
        self.volume.set_value(self.settings.get_float('volume', .7) * 100)

        vol = self.xml.get_widget('volume_slider')
        vol.set_adjustment(self.volume)
        vol.connect('scroll-event', self.__on_volume_scroll)
        vol.connect('key-press-event', self.__on_volume_key_press)

        if self.settings.get_boolean("ui/use_tray", False): 
            self.setup_tray()
    
        # sets the title of the main exaile window
        self.window.set_title(_("Exaile Music Player"))

        # log in to audio scrobbler
        user = self.settings.get_str("lastfm/user", "")
        password = self.settings.get_crypted("lastfm/pass", "")

        thread.start_new_thread(audioscrobbler.get_scrobbler_session,
            (self, user, password))

        self.playlists_nb = self.xml.get_widget('playlists_nb')
        self.set_tab_placement()
        self.setup_left()
        self.setup_right()
        self.connect_events()
        self.setup_menus()

        pos = self.settings.get_int("ui/mainw_sash_pos", 200)
        self.setup_location()

        self.splitter = self.xml.get_widget('splitter')
        self.splitter.connect('notify::position', self.on_resize)
        self.splitter.set_position(pos)

        self.status = xlmisc.StatusBar(self)

        self.playlists_nb.connect('switch-page',
            self.page_changed)
        self.playlists_nb.remove_page(0)

        self.timer.start()

        self.window.show_all()

        if not self.settings.get_boolean('ui/show_stop_button', True):
            self.stop_button.hide()
        if not self.settings.get_boolean('ui/show_clear_button', True):
            self.clear_button.hide()

        self.stop_track_button.set_sensitive(False)
        self.pmanager = plugins.manager.Manager(self) 
        enabled_plugins = []
        for k, v in self.settings.get_plugins().iteritems():
            if v:
                enabled_plugins.append("%s.py" % k)

        self.pmanager.load_plugins("%s%splugins" % (self.settings_dir, os.sep),
            enabled_plugins)
        self.library_manager.load_songs(False, True)

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
                self.library_manager.show_library_manager()

        interval = self.settings.get_float('scan_interval', 25)
        if interval:
            self.start_scan_interval(interval)

    def tag_callback(self, tags):
        """
            Called when a tag is found in a stream
        """
        newsong=False
        track = self.player.current
        if not track or not track.type == 'stream': return True
        for tag in tags.keys():
            if tag == 'bitrate': track.bitrate = int(tags[tag])/1000
            elif tag == 'comment': track.album = tags[tag]
            elif tag == 'title': 
                try:
                    if track.rawtitle != tags[tag]: 
                        track.rawtitle=tags[tag]
                        xlmisc.log("different song")
                        newsong=True
                except AttributeError:
                    xlmisc.log("new song")
                    track.rawtitle=tags[tag]
                    newsong=True
                
                titleArray=(tags[tag]).split(' - ',2)
                
                if len(titleArray) > 0:
                    track.artist = titleArray[0]
                else:
                    track.artist = track.rawtitle
                if len(titleArray) > 1:
                    track.title = titleArray[1].lstrip()
                else: 
                    track.title = track.rawtitle.lstrip()
            xlmisc.log('%s: %s' % (gst.tag_get_nick(tag), tags[tag]))           
        self.tracks.refresh_row(track)
        self.update_track_information()
        xlmisc.log("rawtitle:%s newsong:%s" % (track.title,newsong))
        if newsong:
            xlmisc.log("asking to fetch cover")
            self.cover_manager.fetch_cover(track)
        return True
        
    def get_version(self):
        """
            Returns the version of Exaile
        """
        return __version__

    def get_plugin_location(self):
        """
            Returns the location of the plugins
        """
        if __version__.find('svn') > -1:
            return 'trunk'
        else:
            return 'branch/%s' % __version__

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
                self.library_manager.on_library_rescan(load_tree=False), 1) 

        self.scan_timer.stop()
        self.scan_timer.time = int(value * 60 * 60 * 1000)
        self.scan_timer.start()

    def setup_location(self):
        """
            Sets up the location and size of the window based on settings
        """
        if self.settings.get_boolean('ui/mainw_maximized', False):
            self.window.maximize()

        width = self.settings.get_int("ui/mainw_width", 640)
        height = self.settings.get_int("ui/mainw_height", 475)

        x = self.settings.get_int("ui/mainw_x", 10)
        y = self.settings.get_int("ui/mainw_y", 10)

        self.window.resize(width, height)
        self.window.move(x, y)

    def setup_col_menus(self, pref, map):
        """
            Fetches the view column menus from the glade xml definition
        """
        self.resizable_cols = self.xml.get_widget('cols_resizable_item')
        self.not_resizable_cols = \
            self.xml.get_widget('cols_not_resizable_item')
        self.resizable_cols.set_active(self.settings.get_boolean('ui/resizable_cols',
            False))
        self.resizable_cols.connect('activate', self.activate_cols_resizable)
        self.not_resizable_cols.connect('activate',
            self.activate_cols_resizable)

        # setup up default shown columns
        if not self.settings.get_boolean('ui/trackslist_defaults_set', False):
            self.settings.set_boolean('ui/trackslist_defaults_set', True)
            columns = []
            for col in trackslist.TracksListCtrl.default_columns:
                columns.append(col)
            self.settings.set_list('ui/%s_columns' % (pref,), columns)

        self.col_menus[pref] = dict()
        column_settings = self.settings.get_list('ui/%s_columns' % (pref,))

        for k, v in map.iteritems():
            self.col_menus[v] = self.xml.get_widget('%s_%s_col' % (pref,
                v))
            show = False
            if k in column_settings:
                show = True

            self.col_menus[v].set_active(show)
            self.col_menus[v].connect('activate', 
                self.change_column_settings, {'key': 'ui/%s_columns' % (pref,), 'value': k})

    def activate_cols_resizable(self, widget, event=None):
        """
            Called when the user chooses whether or not columns can be
            resizable
        """
        self.settings.set_boolean('ui/resizable_cols',
            self.resizable_cols.get_active())
        for i in range(0, self.playlists_nb.get_n_pages()):
            page = self.playlists_nb.get_nth_page(i)
            if isinstance(page, trackslist.TracksListCtrl):
                page.update_col_settings()

    def change_column_settings(self, item, data):
        """
            Changes column view settings
        """
        columns = self.settings.get_list(data['key'])
        columns = list(columns)
        if item.get_active():
            if data['value'] not in columns:
                xlmisc.log("adding %s column to %s" % (data['value'], data['key']))
                columns.append(data['value'])
        else:
            if data['value'] in columns:
                xlmisc.log("removing %s column from %s" % (data['value'], data['key']))
                columns.remove(data['value'])
        self.settings.set_list(data['key'], columns)

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
        self.window.connect('window_state_event', self.on_state_change)
        self.window.connect('delete_event', self.on_quit)
        self.queue_count_label = self.xml.get_widget('queue_count_label')
        self.xml.get_widget('queue_count_box').connect('button-release-event',
            self.queue_count_clicked)

        # for multimedia keys
        self.mmkeys = xlmisc.MmKeys('Exaile', self.__on_mmkey)
        keygrabber = self.mmkeys.grab()
        xlmisc.log("Using multimedia keys from: " + str(keygrabber))

        self.play_button = self.xml.get_widget('play_button')
        self.play_button.connect('clicked', lambda *e: self.player.toggle_pause())

        self.stop_button = self.xml.get_widget('stop_button')
        self.stop_button.connect('clicked', lambda *e: self.player.stop())

        self.xml.get_widget('randomize_item').connect('activate', lambda *e:
            self.randomize_playlist())

        self.xml.get_widget('show_visualizations_item').connect('activate', 
            lambda *e: player.show_visualizations(self))

        self.quit_item = self.xml.get_widget('quit_item')
        self.quit_item.connect('activate', self.on_quit)

        self.plugins_item = self.xml.get_widget('plugins_item')
        self.plugins_item.connect('activate', self.show_plugin_manager)
        self.view_menu = self.xml.get_widget('view_menu')

        self.new_progressbar = self.xml.get_widget('new_progressbar')
        self.new_progressbar.set_fraction(0)
        self.new_progressbar.set_text(_("Not Playing"))
        self.new_progressbar.connect('button-press-event', self.seek_begin)
        self.new_progressbar.connect('button-release-event', self.seek_end)
        self.new_progressbar.connect('motion-notify-event',
            self.seek_motion_notify)

        self.clear_button = self.xml.get_widget('clear_button')
        self.clear_button.connect('clicked', lambda *e: self.clear_playlist(None))

        self.next_button = self.xml.get_widget('next_button')
        self.next_button.connect('clicked', lambda e: self.player.next())

        self.previous_button = self.xml.get_widget('prev_button')
        self.previous_button.connect('clicked', lambda *e: self.player.previous())

        self.tracks_filter = xlmisc.ClearEntry(self.live_search)
        self.xml.get_widget('tracks_filter_box').pack_start(
            self.tracks_filter.entry,
            True, True)
        self.tracks_filter.connect('activate', self.on_search)
        self.key_id = None

        self.rescan_collection = self.xml.get_widget('rescan_collection')
        self.rescan_collection.connect('activate', 
            self.library_manager.on_library_rescan)

        self.library_item = self.xml.get_widget('library_manager')
        self.library_item.connect('activate', lambda e:
            self.library_manager.show_library_manager())

        self.equalizer_item = self.xml.get_widget('equalizer_item')
        self.equalizer_item.connect('activate', lambda e:
            self.show_equalizer())

        self.queue_manager_item = self.xml.get_widget('queue_manager_item')
        self.queue_manager_item.connect('activate', 
            lambda *e: self.show_queue_manager())

        self.blacklist_item = self.xml.get_widget('blacklist_manager_item')
        self.blacklist_item.connect('activate', lambda e:
            self.show_blacklist_manager())

        self.xml.get_widget('clear_button').connect('clicked',
            self.clear_playlist)
        self.accel_group = gtk.AccelGroup()
        key, mod = gtk.accelerator_parse('<Control>C')
        self.accel_group.connect_group(key, mod, gtk.ACCEL_VISIBLE,
            self.clear_playlist)

        key, mod = gtk.accelerator_parse('<Control>W')
        self.accel_group.connect_group(key, mod, gtk.ACCEL_VISIBLE,
            lambda *e: self.close_page())

        key, mod = gtk.accelerator_parse('<Control>L')
        self.accel_group.connect_group(key, mod, gtk.ACCEL_VISIBLE,
            lambda *e: self.jump_to(3))
        
        # add the accel group to the window
        self.window.add_accel_group(self.accel_group)

        self.xml.get_widget('preferences_item').connect('activate',
            lambda e: prefs.Preferences(self).run())

        self.clear_queue_item = self.xml.get_widget('clear_queue_item')

        self.goto_current_item = self.xml.get_widget('goto_current_item')
        self.goto_current_item.connect('activate', self.goto_current)

        self.xml.get_widget('about_item').connect('activate',
            lambda *e: xlmisc.AboutDialog(self.window, __version__))
        
        self.xml.get_widget('new_item').connect('activate',
            lambda *e: self.new_page())

        self.open_item = self.xml.get_widget('open_item')
        self.open_item.connect('activate', self.on_add_media)

        self.xml.get_widget('export_playlist_item').connect('activate',
            lambda *e: self.playlist_manager.export_playlist())

        self.xml.get_widget('open_url_item').connect('activate',
            self.open_url)

        self.fetch_item = self.xml.get_widget('fetch_covers_item')
        self.fetch_item.connect('activate',
            self.cover_manager.fetch_covers)


        self.open_disc_item = self.xml.get_widget('open_disc_item')
        self.open_disc_item.connect('activate',
            self.open_disc)

        self.xml.get_widget('track_information_item').connect('activate',
            lambda *e: self.jump_to(0))

        action_log_item = self.xml.get_widget('action_log_item')
        action_log_item.connect('activate',
            lambda *e: self.show_debug_dialog()) 

        self.xml.get_widget('import_directory_item').connect('activate',
            lambda *e: self.library_manager.import_directory(load_tree=True))

        self.rating_combo = self.xml.get_widget('rating_combo')
        self.rating_combo.set_active(0)
        self.rating_combo.set_sensitive(False)
        self.rating_signal = self.rating_combo.connect('changed', self.set_rating)

        # stop track event box
        self.stop_track_button = self.xml.get_widget('stop_track_button')
        self.stop_track_button.connect('clicked',
            self.stop_track_toggle)

    def stop_track_toggle(self, *e):
        """
            Stop track toggle
        """
        if not self.player.stop_track: return
        result = common.yes_no_dialog(self.window, 
            _('Playback is currently set to stop on '
            'the track "%(title)s" by "%(artist)s". '
            'Would you like to remove this?') % {
                'title': self.player.stop_track.title,
                'artist': self.player.stop_track.artist
            })
        if result == gtk.RESPONSE_YES:
            self.player.stop_track = None
            self.tracks.queue_draw()

    def __on_mmkey(self, key):
        if key in ('Play', 'PlayPause', 'Pause'):
            self.player.toggle_pause()
        elif key == 'Stop':
            self.player.stop(1)
        elif key == 'Previous':
            self.player.previous()
        elif key == 'Next':
            self.player.next()

    def randomize_playlist(self):
        """
            Randomizes the current playlist
        """
        songs = self.tracks.songs
        random.shuffle(songs)
        self.tracks.set_songs(songs)

    def show_plugin_manager(self, *e):
        """
            Shows the plugin manager
        """
        manager = plugins.gui.PluginManager(self, self.window, self.pmanager,
            self.update_plugin,
            'http://www.exaile.org/plugins/plugins.py?version=%s' %
            self.get_plugin_location())

    def update_plugin(self, plugin):
        """
            Sets whether or not a plugin is enabled
        """
        self.settings.set_boolean("enabled", plugin.PLUGIN_ENABLED, plugin=plugin.FILE_NAME)

    def set_rating(self, combo=None, rating=None):
        """
            Sets the user rating of a track
        """
        track = self.player.current
        if not track: return

        if rating is None:
            rating = combo.get_active() + 1
        else:
            try:
                rating = int(rating)
            except ValueError:
                xlmisc.log('Invalid rating passed')
                return
            if rating < 0: rating = 0
            if rating > 8: rating = 8
        track.rating = rating
        path_id = library.get_column_id(self.db, 'paths', 'name', track.loc)
        self.db.execute("UPDATE tracks SET user_rating=? WHERE path=?", 
            (rating, path_id))

        xlmisc.log("Set rating to %d for track %s" % (rating, track))
        if self.tracks:
            self.tracks.refresh_row(track)


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
        self.player.queued = []
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
        all = self.db.select("""
            SELECT 
                paths.name, 
                path 
            FROM 
               tracks, paths 
            WHERE 
                paths.id=tracks.path AND 
                blacklisted=1 
            ORDER BY 
                artist, album, track, title
        """)
        songs = []
        for row in all:
            song = library.read_track(self.db, None, row[0])
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


    def show_equalizer(self):

        try: # Equalizer element is still not very common 
            gst.element_factory_make('equalizer-10bands')
        except gst.PluginNotFoundError: # Should probably log this..
            common.error(self.window, _('Gstreamer equalizer is not '
                ' available.  It can be found in gstreamer-plugins-bad '
                '(currently found in GST CVS).'))
            return
        eq = equalizer.EqualizerWindow(self)

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
        return self.settings_dir
   
    def set_tab_placement(self, setting=None):
        """
            Sets the placement of the tabs on the playlists notebook
        """
        if not setting:
            p = self.settings.get_int('ui/tab_placement', 0)
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
        self.emit('tray-icon-toggled', True)

    def remove_tray(self):
        """
            Removes the tray icon
        """
        if self.tray_icon:
            self.emit('tray-icon-toggled', False)
            self.tray_icon.destroy()
            self.tray_icon = None

    def _load_tab(self, last_active):
        """
            Selects the last loaded page
        """
        xlmisc.finish()
        xlmisc.log('Loading page %s' % last_active)
        self.playlists_nb.set_current_page(last_active)
        page = self.playlists_nb.get_nth_page(last_active)
        self.tracks = page
        if not page: return
        self.update_songs(page.songs, False)



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
            try: self.player.queued.remove(track)
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
            if track in self.player.queued:
                if toggle:
                    self.player.queued.remove(track)

            elif first and track == self.player and self.player.is_playing():
                pass
            else:
                self.player.queued.append(track)

            first = False
        
        self.tracks.queue_draw()
        trackslist.update_queued(self)
        
    def on_stop_track(self, item, param, toggle=True): 
        """
            Stops playback after the selected track
        """
        track = self.tracks.get_selected_track()

        if self.player.stop_track == track:
            self.player.stop_track = None
        else:
            self.player.stop_track = track

    def setup_left(self): 
        """
            Sets up the left panel
        """
        self.playlists_panel = playlists.PlaylistsPanel(self)
        self.collection_panel = collection.CollectionPanel(self)
        self.side_notebook = self.xml.get_widget('side_notebook')
        self.files_panel = files.FilesPanel(self)

        page_number = self._find_page_number('device_box')
        self.device_panel = device.DevicePanel(self)
        self.device_panel_widget = self.side_notebook.get_nth_page(page_number)
        self.device_panel_label = self.side_notebook.get_tab_label(
            self.device_panel_widget)

        self.side_notebook.remove_page(page_number)
        self.device_panel_showing = False

        self.pradio_panel = radio.RadioPanel(self)

    def _find_page_number(self, text):
        """
            Finds a specific page number for a label
        """
        for i in range(self.side_notebook.get_n_pages()):
            page = self.side_notebook.get_nth_page(i)
            if page.get_name() == text: return i

        return 0

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
        loc = os.path.join(self.settings_dir, "music.db")
        database = db.DBManager(loc)
        database.add_function_create(('THE_CUTTER', 1, library.the_cutter))
        database.add_function_create(('LSTRIP_SPEC', 1, library.lstrip_special))
        return database

    def database_connect(self):
        """
            Connects to the database
        """

        im = False
        if not os.path.isfile(os.path.join(self.settings_dir, "music.db")):
            im = True
        try:
            self.db = self.get_database()
        except db.DBOperationalError, e:
            common.error(self.window, _("Error connecting to database: %s" %
                str(e)))
            sys.exit(1)
        if im:
            try:
                self.db.import_sql(os.path.join("sql", "db.sql"))
            except db.DBOperationalError, e:
                common.error(self.window, _("Error "
                    "creating collection database: %s") % (str(e)))
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
                    library.the_cutter))
            except:
                pass # db is ok, continue!                

        self.db.check_version("sql")


    def initialize(self):
        """
            Called when everything is done loading
        """
        xlmisc.finish()
        self.playlist_manager.load_last_playlist()

        if len(sys.argv) > 1 and sys.argv[1] and \
            not sys.argv[1].startswith("-"):
            self.stream(sys.argv[1])
        if self.options.playcd:
            self.open_disc()
        if self.options.minim:
            try:
                self.tray_icon.toggle_exaile_visibility()
            except:
                pass
        return False

    @common.threaded
    def update_songs(self, songs=None, set=True): 
        """
            Sets the songs and playlist songs
        """
        tracks = self.tracks
        if not tracks:
            tracks = self.playlists_nb.get_nth_page(0)
        if not songs and tracks: songs = tracks.songs
        self.songs = songs
        self.playlist_songs = songs


        if set: 
            try:
                visible = self.tracks.list.get_visible_range()
            except AttributeError:
                # compatibility with old gtk versions (e.g. in Ubuntu Dapper)
                # that don't have TreeView.get_visible_range
                visible = None
            if visible: 
                (path1, path2) = visible

                scroll_to_end = False
                if path2 and path2[0] == len(self.tracks.songs):
                    scroll_to_end = True

            gobject.idle_add(tracks.set_songs, songs)

            if visible and path1 and path2:
                if scroll_to_end:
                    gobject.idle_add(tracks.list.scroll_to_cell,
                    (len(self.tracks.songs),))
                else:
                    gobject.idle_add(tracks.list.scroll_to_cell, path1[0]+1)

    def timer_update(self, event=None): 
        """
            Fired every half second.
            Updates the seeker position, the "now playing" title, and
            submits the track to last.fm when appropriate
        """
        self.status.set_track_count(_("%(track_count)d showing, "
            "%(track_total)d in collection") %
            {
                'track_count': len(self.songs),
                'track_total': len(self.all_songs)
            })
        track = self.player.current

        self.rewind_track += 1

        if track == None: 
            return True
        duration = track.duration

        # update the progress bar/label
        value = self.player.get_current_position()
        if duration == -1:
            real = 0
        else:
            real = value * duration / 100
        seconds = real

        if not self.seeking and not self.player.is_paused():
            self.new_progressbar = self.xml.get_widget('new_progressbar')
            fraction = value / 100
            if fraction > 1: fraction = 1
            self.new_progressbar.set_fraction(fraction)

            if track.type == 'stream':
                if track.start_time and self.player.is_playing():
                    seconds = time.time() - track.start_time
                    self.new_progressbar.set_text("%d:%02d" % (seconds / 60, seconds % 60))

            else:
                remaining_seconds = duration - seconds
                self.new_progressbar.set_text("%d:%02d / %d:%02d" % ((seconds / 60), (seconds % 60), (remaining_seconds / 60), (remaining_seconds % 60) )  )


        if (seconds > 240 or value > 50) and track.type != 'stream' and \
            self.player.is_playing() and not track.submitted: 
            track.submitted = True
            self.update_rating(track, plays=1,
                rating=1)
            self.status.set_first(_("Submitting to Last.fm..."), 2000)
            audioscrobbler.submit_to_scrobbler(self, track)

        return True

    def update_track_information(self, track='', returntrue=True):
        """
            Updates track status information
        """
        self.rating_combo.disconnect(self.rating_signal)
        if track == '':
            track = self.player.current

        self.artist_label = self.xml.get_widget('artist_label')
        if track == None:
            self.new_progressbar.set_fraction(0)
            self.new_progressbar.set_text(_("Not Playing"))
            self.title_label.set_label(_("Not Playing"))
            self.artist_label.set_label(_("Stopped"))
            self.rating_combo.set_active(0)
            self.rating_combo.set_sensitive(False)

            self.rating_signal = self.rating_combo.connect('changed',
                self.set_rating)
            return

        album = track.album
        artist = track.artist
        if album == "": album = _("Unknown")
        if artist == "": artist = _("Unknown")

        self.title_label.set_label(track.title)

        # set up the playing/track labels based on the type of track

        self.window.set_title(_("Exaile: playing %(title)s from %(album)s by %(artist)s") %
            {
                'title': track.title,
                'album': track.album,
                'artist': track.artist
            })
        self.artist_label.set_label(_("from %(album)s\nby %(artist)s") % 
            {
                'album': album, 
                'artist': artist
            })

        if self.tray_icon:
            self.tray_icon.set_tooltip(_("Playing %(title)s\nfrom %(album)s\nby %(artist)s") %
                {
                    'title': track.title,
                    'album': track.album,
                    'artist': track.artist
                })

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
        self.emit('track-information-updated')
        if returntrue: return True

    def update_rating(self, track, plays = 1, rating = 0): 
        """
            Adds one to the "plays" of this track
        """

        update_string = "rating = rating + " + str(rating) + " , " + \
            "plays = plays + " + str(plays)

        xlmisc.log("updated plays " + str(plays) + ", rating "+ str(rating))

        path_id = library.get_column_id(self.db, 'paths', 'name', track.loc)
        self.db.execute("UPDATE tracks SET %s WHERE path=?" % update_string, 
            (path_id,))

    
    def setup_right(self): 
        """
            Sets up the right side of the sash (this is the playlist area)
        """
        self.cover = xlmisc.ImageWidget()
        self.cover.set_image_size(covers.COVER_WIDTH, covers.COVER_WIDTH)
        self.cover_box = covers.CoverEventBox(self)
        self.cover_box.add(self.cover)
        self.xml.get_widget('image_box').pack_start(self.cover_box)
        self.cover.set_image(os.path.join('images', 'nocover.png'))

        # set the font/etc 
        self.title_label = self.xml.get_widget('title_label')
        attr = pango.AttrList()
        attr.change(pango.AttrWeight(pango.WEIGHT_BOLD, 0, 800))
        attr.change(pango.AttrSize(12500, 0, 600))
        self.title_label.set_attributes(attr)

        # set up the burn button, check for available burning programs
        burn_button = self.xml.get_widget('burn_button')
        burn_button.connect('clicked', self.on_burn_button_clicked)

        burnprogs = xl.burn.check_burn_progs()
        if not burnprogs:            
            xlmisc.log("A supported CD burning program was not found "
                    "in $PATH, disabling burning capabilities.")
            burn_button.set_sensitive(False)
        else:
            pref = self.settings.get_str('burn_prog', burn.check_burn_progs()[0])

    def on_burn_button_clicked(self, button):
        xl.burn.launch_burner(self.settings.get_str('burn_prog', burn.check_burn_progs()[0]), self.tracks.songs)

    @common.synchronized
    def new_page(self, title=_("Playlist"), songs=None, set_current=True,
        ret=True):
        """
            Create a new tab with the specified title, populates it with the
            specified songs, and sets it to be the current page if set_current
            is true.
        """
        # if there is currently only one tab, and it's an empty "Playlist"
        # tab, remove it before adding this new one
        if self.playlists_nb.get_n_pages() == 1:
            page = self.playlists_nb.get_nth_page(0)
            tab = self.playlists_nb.get_tab_label(page)
            if tab.title == _("Playlist") and self.tracks and not \
                self.tracks.songs:
                self.playlists_nb.remove_page(0)
        
        if not songs: songs = library.TrackData()
        self.tracks = trackslist.TracksListCtrl(self)
        t = self.tracks
        self.tracks.playlist_songs = songs 
        tab = xlmisc.NotebookTab(self, title, self.tracks)
        self.playlists_nb.append_page(self.tracks, tab)

        if set_current:
            self.playlists_nb.set_current_page( 
                self.playlists_nb.get_n_pages() - 1)
            self.update_songs(songs)
        if ret: return t

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

    def clear_playlist(self, *e): 
        """
            Clears the current playlist
        """

        if self.tracks == None:
            self.new_page()

        self.tracks.set_songs(library.TrackData())
        self.tracks.playlist_songs = self.tracks.songs
        self.playlist_songs = self.tracks.songs
        self.songs = self.tracks.songs
    
    def on_search(self, widget=None, event=None, custom=True): 
        """
            Called when something is typed into the filter box
        """

        keyword = self.tracks_filter.get_text()
        if keyword.startswith("where ") and not widget: return
        self.songs = library.search(self, self.tracks.playlist_songs, None,
            custom=custom)
        self.tracks.set_songs(self.songs, False)
        
        tokens = keyword.lower().split()
        for token in tokens:
            self.songs = library.search(self, self.songs, token, custom=custom)
            self.tracks.set_songs(self.songs, False)


    def __on_volume_scroll(self, widget, ev):
        """
            Called when the user scrolls their mouse wheel over the volume bar
        """
        # Modify default HScale up/down behaviour.
        if ev.direction == gtk.gdk.SCROLL_DOWN:
            self.volume.page_down()
            return True
        elif ev.direction == gtk.gdk.SCROLL_UP:
            self.volume.page_up()
            return True
        return False

    def __on_volume_key_press(self, widget, ev):
        """
            Called when the user presses a key when the volume bar is focused
        """
        # Modify default HScale up/down behaviour.
        inc = widget.get_adjustment().props.step_increment
        if ev.keyval == gtk.keysyms.Down:
            self.volume.step_down()
            return True
        elif ev.keyval == gtk.keysyms.Up:
            self.volume.step_up()
            return True
        return False

    def __on_volume_changed(self, adjustment): 
        """
            Called when the volume is changed
        """

        value = adjustment.get_value()
        frac_value = value / 100.0
        self.player.set_volume(frac_value)
        self.settings['volume'] = frac_value
        if not self.window.has_toplevel_focus() and self.settings.get_boolean("osd/enabled", True):
            pop = xlmisc.get_osd(self, xlmisc.get_osd_settings(self.settings))
            vol_text = "<big><b> " + _("Changing volume: %d %%") % \
                self.get_volume_percent() + "</b></big>"
            pop.show_osd(vol_text, None)

    def seek_begin(self, widget, event):
        """
            Starts when seek drag begins
        """
        if not self.player.current or self.player.current.type == \
            'stream': return
        self.seeking = True

    def seek_motion_notify(self, widget, event):
        """
            Simulates dragging on the new progressbar widget
        """
        if not self.player.current or self.player.current.type == \
            'stream': return
        mouse_x, mouse_y = event.get_coords()
        progress_loc = self.new_progressbar.get_allocation()

        value = mouse_x / progress_loc.width
        if value < 0: value = 0
        if value > 1: value = 1
        self.new_progressbar.set_fraction(value)
        track = self.player.current

        duration = track.duration
        if duration == -1:
            real = 0
        else:
            real = value * duration
        seconds = real

        remaining_seconds = duration - seconds
        self.new_progressbar.set_text("%d:%02d / %d:%02d" % ((seconds / 60), 
            (seconds % 60), (remaining_seconds / 60), (remaining_seconds % 60))) 

    def seek_end(self, widget, event):
        """
            Resets seeking flag, actually seeks to the requested location
        """

        mouse_x, mouse_y = event.get_coords()
        progress_loc = self.new_progressbar.get_allocation()

        value = mouse_x / progress_loc.width
        if value < 0: value = 0
        if value > 1: value = 1

        if not self.player.current or \
            self.player.current.type == 'stream':
            self.new_progressbar.set_fraction(0)
            return
        duration = self.player.current.duration * gst.SECOND
        if duration == -1:
            real = 0
        else:
            real = value * duration / 100
        seconds = real / gst.SECOND

        duration = self.player.current.duration
        real = float(value * duration)
        self.player.seek(real)
        self.seeking = False
        self.player.current.submitted = True
        self.emit('seek', real)

    def get_suggested_songs(self):
        """
            Gets suggested tracks from last.fm
        """
        if not self.tracks or not self.player.current: return

        played = 0
        for song in self.songs:
            if song in self.player.played:
                played += 1

        count = 5 - (len(self.songs) - played)
        xlmisc.log("suggested song count is %d" % count)
        if count <= 0: count = 1

        songs = library.get_suggested_songs(self, self.db, 
            self.player.current, self.songs, count, self.add_suggested)

    def add_suggested(self, artists, count):
        """
            adds suggested tracks that were fetched
        """
        songs = library.TrackData()
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
                        and not song in self.player.played and not \
                        song in self.player.queued:
                        songs.append(song)

            if len(songs) >= count: break

        if not songs:
            self.status.set_first(_("Could not find any"
            " suggested songs"), 4000)

        for song in songs:
            self.tracks.append_song(song)

        self.update_songs(None, False)

    def show_osd(self, tray=False):
        """
            Shows a popup window with information about the current track
        """
        if tray:
            if not self.settings.get_boolean('osd/tray', True): return
        else:
            if not self.settings.get_boolean("osd/enabled", True): return
        track = self.player.current
        if not track: return
        pop = xlmisc.get_osd(self, xlmisc.get_osd_settings(self.settings))
        cover = self.cover_manager.fetch_cover(track, 1)

        text_display = self.settings.get_str('osd/display_text',
            xl.prefs.TEXT_VIEW_DEFAULT)
        pop.show_track_osd(track, text_display,
            cover)

    def setup_menus(self):
        """
            Sets up menus
        """
        self.shuffle = self.xml.get_widget('shuffle_button')
        self.shuffle.set_active(self.settings.get_boolean('shuffle', False))
        self.player.shuffle = self.shuffle.get_active()
        self.shuffle.connect('toggled', self.toggle_mode, 'shuffle')

        self.repeat = self.xml.get_widget('repeat_button')
        self.repeat.set_active(self.settings.get_boolean('repeat', False))
        self.player.repeat = self.repeat.get_active()
        self.repeat.connect('toggled', self.toggle_mode, 'repeat')

        self.dynamic = self.xml.get_widget('dynamic_button')
        self.dynamic.set_active(self.settings.get_boolean('dynamic', False))
        self.dynamic.connect('toggled', self.toggle_mode, 'dynamic')

    def toggle_mode(self, item, param):
        """
            Toggles the settings for the specified playback mode
        """
        self.settings.set_boolean(param, item.get_active())
        setattr(self.player, param, item.get_active())

    
    def get_last_dir(self):
        """
            Gets the last working directory
        """

        try:
            f = self.last_open_dir
        except:
            self.last_open_dir = self.settings.get_str('last_open_dir',
                os.getenv('HOME'))
        return self.last_open_dir

    def on_add_media(self, item, event=None): 
        """
            Adds media to the current selected tab regardless of whether or
            not they are contained in the library
        """
        dialog = gtk.FileChooserDialog(_("Choose a file"), self.window,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_OPEN, gtk.RESPONSE_OK))

        new_tab = gtk.CheckButton(_("Open in new tab"))
        dialog.set_extra_widget(new_tab)
        dialog.set_current_folder(self.get_last_dir())
        dialog.set_select_multiple(True)

        # Media Files
        filter = gtk.FileFilter()
        filter.set_name(_("Media Files"))
        for ext in media.SUPPORTED_MEDIA:
            filter.add_pattern('*' + ext)
        dialog.add_filter(filter)
        filter = gtk.FileFilter()
        # Playlist Files
        filter.set_name(_("Playlist Files"))
        for ext in xlmisc.PLAYLIST_EXTS:
            filter.add_pattern('*' + ext)
        dialog.add_filter(filter)
        # All Files
        filter = gtk.FileFilter()
        filter.set_name(_("All Files"))
        filter.add_pattern('*')
        dialog.add_filter(filter)

        result = dialog.run()
        dialog.hide()

        if result == gtk.RESPONSE_OK:
            paths = dialog.get_filenames()
            self.last_open_dir = dialog.get_current_folder()
            self.status.set_first(_("Populating playlist..."))
            songs = library.TrackData()

            count = 0
            for path in paths:
                (f, ext) = os.path.splitext(path)
                if ext in media.SUPPORTED_MEDIA:
                    if count >= 10:
                        xlmisc.finish()
                        count = 0
                    tr = library.read_track(self.db, self.all_songs, path)

                    count = count + 1
                    if tr:
                        songs.append(tr)
                if ext in xlmisc.PLAYLIST_EXTS:
                    self.playlist_manager.import_playlist(path, 
                        newtab=new_tab.get_active())

            if songs:
                if new_tab.get_active():
                    self.new_page(_("Playlist"), songs)
                else:
                    self.playlist_manager.append_songs(songs)

            self.status.set_first(None)

    def get_volume_percent(self):
        """
            Returns the current volume level as a percentage
        """
        vol = self.volume.get_value()
        return round(vol)

    def stream(self, url): 
        """
            Play a radio stream
        """
        self.player.stop()

        if "://" in url:
            track = media.Track(url)
            track.type = 'stream'
        else:
            lowurl = url.lower()
            # if it's a playlist file
            if any(lowurl.endswith(ext) for ext in xlmisc.PLAYLIST_EXTS):
                self.playlist_manager.import_playlist(url, True)
                return
            else:
                track = library.read_track(self.db, self.all_songs, url)

        songs = library.TrackData((track, ))
        if not songs: return

        self.playlist_manager.append_songs(songs, play=False)
        self.player.play_track(track)

    def open_url(self, event): 
        """
            Prompts for a url to open
        """
        dialog = common.TextEntryDialog(self.window,
            _("Enter the address"), _("Enter the address"))
        result = dialog.run()

        if result == gtk.RESPONSE_OK:
            path = dialog.get_value()
            self.stream(path)

    def open_disc(self, widget=None):
        """
            Opens an audio disc
        """
        if not library.CDDB_AVAIL:
            common.error(self.window, _('You need the python-cddb package '
                ' in order to play audio discs.'))
            return
        songs = library.read_audio_disc(self)
        if not songs: return
        self.new_page(_("Audio Disc"), songs)

    def goto_current(self, *e): 
        """
            Ensures that the currently playing track is visible
        """
        if not self.tracks: return
        self.tracks.ensure_visible(self.player.current)


    def on_quit(self, widget=None, event=None): 
        """
            Saves the current playlist and exits.  If user closes the window
            while tray icon is present, simply hides the window.
        """
        self.window.hide()
        xlmisc.finish()
        if self.tray_icon and widget == self.window:
            return True

        # PLUGIN: send plugins event before quitting
        self.emit('quit')

        self.player.stop()
        self.cover_manager.stop_cover_thread()
        for thread in self.thread_pool:
            thread.done = True

        dir = os.path.join(self.settings_dir, "saved")
        if not os.path.isdir(dir):
            os.mkdir(dir)

        # delete all current saved playlists
        for file in os.listdir(dir):
            if file.endswith(".m3u"):
                os.unlink(os.path.join(dir, file))

        if os.path.isfile(os.path.join(dir, "queued.save")):
            os.unlink(os.path.join(dir, "queued.save"))

        if self.player.current: self.player.current.stop()

        for i in range(self.playlists_nb.get_n_pages()):
            page = self.playlists_nb.get_nth_page(i)
            title = self.playlists_nb.get_tab_label(page).title
            if page.type != 'track': continue
            songs = page.songs
            self.playlist_manager.save_m3u(os.path.join(self.settings_dir, "saved",
                "playlist%.4d.m3u" % i), songs, title)

        # save queued tracks
        if self.player.queued:
            h = open(os.path.join(dir, "queued.save"), "w")
            for song in self.player.queued:
                h.write("%s\n" % song.loc)
            h.close()

        if self.player.stop_track:
            self.settings.set_str('stop_track', self.player.stop_track.loc)
        else:
            self.settings['stop_track'] = ''

        self.db.db.commit()
        last_active = self.playlists_nb.get_current_page()
        xlmisc.log('Last active is: %d' % last_active)
        self.settings['last_active'] = last_active
        self.settings.save()
        
        gtk.main_quit()
        print 'Exiting, bye!'

    def on_resize(self, widget, event): 
        """
            Saves the current size and position
        """
        if self.settings.get_boolean('ui/mainw_maximized', False): return False

        (width, height) = self.window.get_size()
        self.settings['ui/mainw_width'] = width
        self.settings['ui/mainw_height'] = height
        (x, y) = self.window.get_position()
        self.settings['ui/mainw_x'] = x
        self.settings['ui/mainw_y'] = y
        if self.splitter.get_position() > 10:
            sash = self.splitter.get_position()
            self.settings['ui/mainw_sash_pos'] = sash
        return False

    def on_state_change(self, widget, event):
        """
            Saves the current maximized state
        """
        if event.changed_mask & gtk.gdk.WINDOW_STATE_MAXIMIZED:
            self.settings.set_boolean('ui/mainw_maximized',
                bool(event.new_window_state & gtk.gdk.WINDOW_STATE_MAXIMIZED))
        return False

    def jump_to(self, index):
        """
            Show the a specific page in the track information tab about
            the current track
        """
        track = self.player.current
        if not track and not self.tracks: return
        if not track: track = self.tracks.get_selected_track() 
        if not track: return
            
        page = xl.track.show_information(self, track)
        page.set_current_page(index)
