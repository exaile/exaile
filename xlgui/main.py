# Copyright (C) 2008-2009 Adam Olsen 
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

from xl.nls import gettext as _
import pygtk, pygst
pygtk.require('2.0')
pygst.require('0.10')
import gst, logging
import gtk, gobject, pango, datetime
from xl import xdg, event, track, common
from xl import settings, trackdb
import xl.playlist
from xlgui import playlist, cover, guiutil, menu, commondialogs, tray
import xl.playlist, re, os, threading

logger = logging.getLogger(__name__)

class PlaybackProgressBar(object):
    def __init__(self, bar, player):
        self.bar = bar
        self.player = player
        self.timer_id = None
        self.seeking = False

        self.bar.set_text(_('Not Playing'))
        self.bar.connect('button-press-event', self.seek_begin)
        self.bar.connect('button-release-event', self.seek_end)
        self.bar.connect('motion-notify-event', self.seek_motion_notify)

        event.add_callback(self.playback_start, 
                'playback_player_start', player)
        event.add_callback(self.playback_toggle_pause, 'playback_toggle_pause',
            player)
        event.add_callback(self.playback_end, 
                'playback_player_end', player)

    def destroy(self):
        event.remove_callback(self.playback_start, 
                'playback_player_start', self.player)
        event.remove_callback(self.playback_end, 
                'playback_player_end', self.player)

    def seek_begin(self, *e):
        self.seeking = True

    def seek_end(self, widget, event):
        mouse_x, mouse_y = event.get_coords()
        progress_loc = self.bar.get_allocation()

        value = mouse_x / progress_loc.width
        if value < 0: value = 0
        if value > 1: value = 1

        track = self.player.current
        if not track or not (track.is_local() or track['__length']): return
        length = track.get_duration()

        seconds = float(value * length)
        self.player.seek(seconds)
        self.seeking = False
        self.bar.set_fraction(value)
        self._set_bar_text(seconds, length)
#        self.emit('seek', seconds)

    def seek_motion_notify(self, widget, event):
        track = self.player.current
        if not track or not(track.is_local() or track['__length']): return

        mouse_x, mouse_y = event.get_coords()
        progress_loc = self.bar.get_allocation()

        value = mouse_x / progress_loc.width

        if value < 0: value = 0
        if value > 1: value = 1

        self.bar.set_fraction(value)
        length = track.get_duration()
        seconds = float(value * length)
        remaining_seconds = length - seconds
        self._set_bar_text(seconds, length)
       
    def playback_start(self, type, player, object):
        self.timer_id = gobject.timeout_add(1000, self.timer_update)

    def playback_toggle_pause(self, type, player, object):
        if self.timer_id: 
            gobject.source_remove(self.timer_id)
            self.timer_id = None
        if not player.is_paused():
            self.timer_id = gobject.timeout_add(1000, self.timer_update)

    def playback_end(self, type, player, object):
        if self.timer_id: gobject.source_remove(self.timer_id)
        self.timer_id = None
        self.bar.set_text(_('Not Playing'))
        self.bar.set_fraction(0)

    def timer_update(self, *e):
        track = self.player.current
        if not track: return
        if self.seeking: return True

        if not track.is_local() and not track['__length']:
            self.bar.set_fraction(0)
            self.bar.set_text(_('Streaming...'))
            return True
        length = track.get_duration()

        self.bar.set_fraction(self.player.get_progress())

        seconds = self.player.get_time()
        self._set_bar_text(seconds, length)

        return True

    def _set_bar_text(self, seconds, length):
        """
            Sets the text of the progress bar based on the number of seconds
            into the song
        """
        remaining_seconds = length - seconds
        time = datetime.timedelta(seconds=int(seconds))
        time_left = datetime.timedelta(seconds=int(remaining_seconds))
        def str_time(t):
            """
                Converts a datetime.timedelta object to a sensible human-
                readable format
            """
            text = unicode(t)
            if t.seconds > 3600:
                return text
            elif t.seconds > 60:
                return text.lstrip("0:")
            else:
                # chop off first zero to get 0:20
                return text[3:]
        self.bar.set_text("%s / %s" % (str_time(time), str_time(time_left)))


# Reduce the notebook tabs' close button padding size.
gtk.rc_parse_string("""
    style "thinWidget" {
        xthickness = 0
        ythickness = 0
    }
    widget "*.tabCloseButton" style "thinWidget"
    """)
class NotebookTab(gtk.EventBox):
    """
        A notebook tab, complete with a close button
    """
    def __init__(self, main, notebook, title, page):
        """
            Initializes the tab
        """
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)

        self.main = main
        self.nb = notebook
        self.page = page
        self.already_needs_save = self.page.playlist.get_is_custom() and self.page.get_needs_save()
        
        self.connect('button_press_event', self.on_button_press)
        self.page.connect('playlist-content-changed', lambda widget, dirty:
                    self.on_playlist_content_change(dirty))
        self.page.connect('customness-changed', lambda widget, custom:
                    self.on_customness_change(custom))
        event.add_callback(self.on_playlist_removed, 'playlist_removed')

        self.hbox = hbox = gtk.HBox(False, 2)
        self.add(hbox)

        if self.already_needs_save and self.page.playlist.get_is_custom():
            self.label = gtk.Label("*" + title)
        else:
            self.label = gtk.Label(title)
        self.label.set_max_width_chars(20)
        self.label.set_ellipsize(pango.ELLIPSIZE_END)
        self.label.set_tooltip_text(self.label.get_text())
        hbox.pack_start(self.label, False, False)

        self.menu = menu.PlaylistTabMenu(self, self.page.playlist.get_is_custom())

        self.button = btn = gtk.Button()
        btn.set_name('tabCloseButton')
        btn.set_relief(gtk.RELIEF_NONE)
        btn.set_focus_on_click(False)
        btn.set_tooltip_text(_("Close tab"))
        btn.connect('clicked', self.do_close)
        btn.connect('button_press_event', self.on_button_press)
        image = gtk.Image()
        image.set_from_stock('gtk-close', gtk.ICON_SIZE_MENU)
        btn.add(image)
        hbox.pack_end(btn, False, False)

        self.show_all()

    def get_title(self):
        return unicode(self.label.get_text(), 'utf-8')
    def set_title(self, title):
        self.label.set_text(title)
        self.label.set_tooltip_text(self.label.get_text())
    title = property(get_title, set_title)
    
    def on_customness_change(self, custom):
        self.menu.destroy()
        self.menu = None
        self.menu = menu.PlaylistTabMenu(self, custom)
    
    def on_playlist_removed(self, type, object, name):
        if name == self.page.playlist.name and self.page.playlist.get_is_custom():
            self.page.playlist.set_needs_save(False)
            self.on_playlist_content_change(False)
            self.page.playlist.set_is_custom(False)
            self.on_customness_change(False)
    
    def on_playlist_content_change(self, dirty):
        if self.page.playlist.get_is_custom():
            if dirty and not self.already_needs_save:
                self.already_needs_save = True
                self.label.set_text('*' + self.label.get_text())
            elif not dirty and self.already_needs_save:
                self.already_needs_save = False
                if self.label.get_text()[0] == '*':
                    self.label.set_text(self.label.get_text()[1:])

    def on_button_press(self, widget, event):
        """
            Called when the user clicks on the tab
        """
        if event.button == 3:
            self.menu.popup(None, None, None, event.button, event.time)
            return True
        elif event.button == 2:
            self.do_close()
            return True
        elif event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            return True # stop the event propagating

    def do_new_playlist(self, *args):
        self.main.add_playlist()

    def do_rename(self, *args):
        dialog = commondialogs.TextEntryDialog(
            _("New playlist title:"), _("Rename Playlist"),
            self.title, self.main.window)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self.title = dialog.get_value()

    def do_save_custom(self, *args):
        dialog = commondialogs.TextEntryDialog(
            _("Custom playlist name:"), _("Save As..."),
            self.title, self.main.window, okbutton=gtk.STOCK_SAVE)
        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self.title = dialog.get_value()
            pl = self.main.get_selected_playlist()
            pl.set_name(self.title)
            pl.playlist.set_name(self.title)
            self.main.controller.panels['playlists'].add_new_playlist(pl.playlist.get_tracks(), self.title)
            pl.playlist.set_is_custom(True)
            pl.emit('customness-changed', True)
            pl.set_needs_save(False)
            event.log_event('custom_playlist_saved', self, pl.playlist)
        
    def do_save_changes_to_custom(self, *args):
        pl = self.main.get_selected_playlist()
        pl.set_needs_save(False)
        self.main.playlist_manager.save_playlist(pl.playlist, overwrite = True)
        event.log_event('custom_playlist_saved', self, pl.playlist)

    def do_close(self, *args):
        """
            Called when the user clicks the close button on the tab
        """
        if self.page.on_closing():
            if self.main.queue.current_playlist == self.page.playlist:
                self.main.queue.set_current_playlist(None)
            num = self.nb.page_num(self.page)
            self.nb.remove_page(num)

    def do_clear(self, *args):
        """
            Clears the current playlist tab
        """
        playlist = self.main.get_selected_playlist()
        if not playlist: return
        playlist.playlist.clear()

class MainWindow(gobject.GObject):
    """
        Main Exaile Window
    """
    __gsignals__ = {'main-visible-toggle': (gobject.SIGNAL_RUN_LAST, bool, ())}
    _mainwindow = None
    def __init__(self, controller, builder, collection, 
        player, queue, covers):
        """
            Initializes the main window

            @param controller: the main gui controller
        """
        gobject.GObject.__init__(self)

        from xlgui import osd
        self.controller = controller
        self.covers = covers
        self.collection =  collection
        self.player = player
        self.playlist_manager = controller.exaile.playlists
        self.queue = queue
        self.current_page = -1 
        self._fullscreen = False

        if settings.get_option('gui/use_alpha', False):
            gtk_screen = gtk.gdk.screen_get_default()
            rgbamap = gtk_screen.get_rgba_colormap()
            if rgbamap is not None:
                gtk.widget_set_default_colormap(rgbamap)

        self.builder = builder
        self.window = self.builder.get_object('ExaileWindow')
        self.window.set_title('Exaile')
        self.playlist_notebook = self.builder.get_object('playlist_notebook')
        self.playlist_notebook.remove_page(0)
        self.playlist_notebook.set_show_tabs(settings.get_option('gui/show_tabbar', True))
        map = {
            'left': gtk.POS_LEFT,
            'right': gtk.POS_RIGHT,
            'top': gtk.POS_TOP,
            'bottom': gtk.POS_BOTTOM
        }
        self.playlist_notebook.set_tab_pos(map.get(
            settings.get_option('gui/tab_placement', 'top')))
        self.splitter = self.builder.get_object('splitter')

        self._setup_position()
        self._setup_widgets()
        self._setup_hotkeys()
        self._connect_events()
        self.osd = osd.OSDWindow(self.cover, self.covers, self.player)
        self.tab_manager = xl.playlist.PlaylistManager(
            'saved_tabs')
        self.load_saved_tabs()
        MainWindow._mainwindow = self

    def load_saved_tabs(self):
        """
            Loads the saved tabs
        """
        if not settings.get_option('playlist/open_last', False):
            self.add_playlist()
            return
        names = self.tab_manager.list_playlists()
        if not names:
            self.add_playlist()
            return

        count = -1
        count2 = 0
        names.sort()
        # holds the order#'s of the already added tabs
        added_tabs = {}
        name_re = re.compile(
                r'^order(?P<tab>\d+)\.((?P<tag>[^.]+)\.)?(?P<name>.*)$')
        for i, name in enumerate(names):
            match = name_re.match(name)
            if not match or not match.group('tab') or not match.group('name'):
                logger.error("%s did not match valid playlist file"
                        % repr(name))
                continue

            logger.debug("Adding playlist %d: %s" % (i, name))
            logger.debug("Tab:%s; Tag:%s; Name:%s" % (match.group('tab'),
                                                     match.group('tag'),
                                                     match.group('name'),
                                                     ))
            pl = self.tab_manager.get_playlist(name)
            pl.name = match.group('name')

            if match.group('tab') not in added_tabs:
                pl = self.add_playlist(pl, erase_empty=False)
                added_tabs[match.group('tab')] = pl
            pl = added_tabs[match.group('tab')]

            if match.group('tag') == 'current':
                count = i
                if self.queue.current_playlist is None:
                    self.queue.set_current_playlist(pl.playlist)
            elif match.group('tag') == 'playing':
                count2 = i
                self.queue.set_current_playlist(pl.playlist)

        # If there's no selected playlist saved, use the currently 
        # playing
        if count == -1:
            count = count2 

        self.playlist_notebook.set_current_page(count)

    def save_current_tabs(self):
        """
            Saves the open tabs
        """
        # first, delete the current tabs
        names = self.tab_manager.list_playlists()
        for name in names:
            logger.debug("Removing tab %s" % name)
            self.tab_manager.remove_playlist(name)

        for i in range(self.playlist_notebook.get_n_pages()):
            pl = self.playlist_notebook.get_nth_page(i).playlist
            tag = ''
            if pl is self.queue.current_playlist:
                tag = 'playing.'
            elif i == self.playlist_notebook.get_current_page():
                tag = 'current.'
            pl.name = "order%d.%s%s" % (i, tag, pl.name)
            logger.debug("Saving tab %d: %s" % (i, pl.name))
            self.tab_manager.save_playlist(pl, True)            

    def add_playlist(self, pl=None, erase_empty=True):
        """
            Adds a playlist to the playlist tab

            @param pl: the xl.playlist.Playlist instance to add
        """
        new_empty_pl = False
        if pl is None:
            pl = xl.playlist.Playlist()
            new_empty_pl = True
        if len(pl.get_tracks()) == 0:
            new_empty_pl = True

        name = pl.get_name()
        nb = self.playlist_notebook
        if pl.get_is_custom():
            for n in range(nb.get_n_pages()):
                nth = nb.get_nth_page(n)
                if nth.playlist.get_is_custom() and not nth.get_needs_save() \
                        and nth.playlist.get_name() == pl.get_name():
                    nb.set_current_page(n)
                    return

        pl = playlist.Playlist(self, self.queue, pl)
        self._connect_playlist_events(pl)

        # Get displayed names for all open playlists, then find a free "slot",
        # e.g. "Playlist 3" if 1 and 2 already exist.
        names = frozenset(nb.get_tab_label(nb.get_nth_page(i)).label.get_text()
            for i in xrange(nb.get_n_pages()))
        i = 1
        try:
            while (name % i) in names:
                i += 1
        except TypeError:
            pass
        else:
            name = name % i

        tab = NotebookTab(self, nb, name, pl)
        # We check if the current playlist is empty, to know if it should be replaced
        cur = nb.get_current_page()
        remove_cur = False
        curpl = nb.get_nth_page(cur)
        if curpl and len(curpl.playlist.get_tracks()) == 0:
            remove_cur = True
        
        nb.append_page(pl, tab)
        nb.set_tab_reorderable(pl, True)
        if remove_cur and not new_empty_pl and erase_empty:
            nb.remove_page(cur)
            nb.reorder_child(pl, cur)
            nb.set_current_page(cur)
        else:
            nb.set_current_page(nb.get_n_pages() - 1)
        self.set_mode_toggles()
        
        # Always show tab bar for more than one tab
        if nb.get_n_pages() > 1:
            nb.set_show_tabs(True)

        self.queue.set_current_playlist(pl.playlist)
        
        return pl

    def _connect_playlist_events(self, pl):
        pl.connect('track-count-changed', lambda *e:
            self.update_track_counts())
        pl.connect('column-settings-changed', self._column_settings_changed)
        pl.list.connect('key-press-event', self._on_pl_key_pressed)

    def _on_pl_key_pressed(self, widget, event):
        if event.keyval == gtk.keysyms.Left:
            # Modifying current position
            if not self.player.current: return
            self.player.scroll(-10)
            self.progress_bar.timer_update() # Needed to evade progressbar lag
        elif event.keyval == gtk.keysyms.Right:
            # Modifying current position
            if not self.player.current: return
            self.player.scroll(10)
            self.progress_bar.timer_update() # Needed to evade progressbar lag

        return False

    def _column_settings_changed(self, *e):
        for page in self.playlist_notebook:
            page.update_col_settings()

    def _setup_hotkeys(self):
        """
            Sets up accelerators that haven't been set up in UI designer
        """
        hotkeys = (
            ('<Control>W', lambda *e: self.close_playlist_tab()),
            ('<Control>S', lambda *e: self.on_save_playlist()),
            ('<Shift><Control>S', lambda *e: self.on_save_playlist_as()),
            ('<Control>F', lambda *e: self.on_search_collection_focus()),
            ('<Control>G', lambda *e: self.on_search_playlist_focus()),
            ('<Control>D', lambda *e: self.on_queue()),
            ('<Control><Alt>l', lambda *e: self.on_clear_queue()),
            ('Left', lambda *e: self._on_left_pressed()),
        )

        self.accel_group = gtk.AccelGroup()
        for key, function in hotkeys:
            key, mod = gtk.accelerator_parse(key)
            self.accel_group.connect_group(key, mod, gtk.ACCEL_VISIBLE,
                function)
        self.window.add_accel_group(self.accel_group)

    def _setup_widgets(self):
        """
            Sets up the various widgets
        """
        self.volume_slider = self.builder.get_object('volume_slider')
        self.volume_slider.set_value(settings.get_option("player/volume", 1))
        self.volume_slider.connect('scroll-event', guiutil.on_slider_scroll)
        self.volume_slider.connect('key-press-event',
            guiutil.on_slider_key_press)

        self.shuffle_toggle = self.builder.get_object('shuffle_button')
        self.shuffle_toggle.set_active(settings.get_option('playback/shuffle', False))
        self.repeat_toggle = self.builder.get_object('repeat_button')
        self.repeat_toggle.set_active(settings.get_option('playback/repeat', False))
        self.dynamic_toggle = self.builder.get_object('dynamic_button')
        self.dynamic_toggle.set_active(settings.get_option('playback/dynamic', False))

        # Cover box
        self.cover_event_box = self.builder.get_object('cover_event_box')
        self.cover = cover.CoverWidget(self, self.covers, self.player)
        self.cover_event_box.add(self.cover)
        self.track_title_label = self.builder.get_object('track_title_label')
        attr = pango.AttrList()
        attr.change(pango.AttrWeight(pango.WEIGHT_BOLD, 0, 800))
        attr.change(pango.AttrSize(12500, 0, 600))
        self.track_title_label.set_attributes(attr)
        self.track_info_label = self.builder.get_object('track_info_label')

        self.progress_bar = PlaybackProgressBar(
            self.builder.get_object('playback_progressbar'),
            self.player)

        # Playback buttons
        for button in ('play', 'next', 'prev', 'stop'):
            setattr(self, '%s_button' % button,
                self.builder.get_object('%s_button' % button))
        
        self.stop_button.connect('button-press-event',
            self.on_stop_buttonpress)

        # Status bar
        self.statusbar = guiutil.Statusbar(self.builder)

        # Search filter
        box = self.builder.get_object('playlist_search_entry_box')
        self.filter = guiutil.SearchEntry()
        self.filter.connect('activate', self.on_playlist_search)
        box.pack_start(self.filter.entry, True, True)


    def on_queue(self):
        """
            Toggles queue on the current playlist
        """
        cur_page = self.playlist_notebook.get_children()[
                self.playlist_notebook.get_current_page()]
        cur_page.menu.on_queue()

    def on_playlist_search(self, *e):
        """
            Filters the currently selected playlist
        """
        pl = self.get_selected_playlist()
        if pl:
            pl.search(unicode(self.filter.get_text(), 'utf-8'))

    def on_volume_changed(self, range):
        settings.set_option('player/volume', range.get_value())

    def on_stop_buttonpress(self, widget, event):
        """
            Called when the user clicks on the stop button.  We're looking for
            a right click so we can display the SPAT menu
        """
        if event.button != 3: return
        menu = guiutil.Menu()
        menu.append(_("Toggle: Stop after selected track"), self.on_spat_clicked,
            'gtk-stop')
        menu.popup(None, None, None, event.button, event.time)

    def on_spat_clicked(self, *e):
        """
            Called when the user clicks on the SPAT item
        """
        tracks = self.get_selected_playlist().get_selected_tracks()
        if not tracks: return
        track = tracks[0]

        if track == self.queue.stop_track:
            self.queue.stop_track = None
        else:
            self.queue.stop_track = track

        self.get_selected_playlist().list.queue_draw()

    def update_track_counts(self, *e):
        """
            Updates the track count information
        """
        if not self.get_selected_playlist(): return

        self.statusbar.set_track_count(
            len(self.get_selected_playlist().playlist),
            self.collection.get_count())
        self.statusbar.set_queue_count(len(self.queue))

    def _connect_events(self):
        """
            Connects the various events to their handlers
        """
        self.splitter.connect('notify::position', self.configure_event)
        self.builder.connect_signals({
            'on_configure_event':   self.configure_event,
            'on_window_state_event': self.window_state_change_event,
            'on_delete_event':      self.delete_event,
            'on_quit_item_activated': self.quit,
            'on_play_button_clicked': self.on_play_clicked,
            'on_next_button_clicked':
                lambda *e: self.queue.next(),
            'on_prev_button_clicked':
                lambda *e: self.queue.prev(),
            'on_stop_button_clicked':
                lambda *e: self.player.stop(),
            'on_shuffle_button_toggled': self.set_mode_toggles,
            'on_repeat_button_toggled': self.set_mode_toggles,
            'on_dynamic_button_toggled': self.set_mode_toggles,
            'on_clear_playlist_button_clicked': self.on_clear_playlist,
            'on_playlist_notebook_switch':  self.on_playlist_notebook_switch,
            'on_playlist_notebook_remove': self.on_playlist_notebook_remove,
            'on_playlist_notebook_button_press': self.on_playlist_notebook_button_press,
            'on_new_playlist_item_activated': lambda *e:
                self.add_playlist(),
            'on_volume_slider_value_changed': self.on_volume_changed,
            'on_queue_count_label_button_press_event': self.controller.queue_manager,
            # Controller
            'on_about_item_activate': self.controller.show_about_dialog,
            'on_scan_collection_item_activate': self.controller.on_rescan_collection,
            'on_randomize_playlist_item_activate': self.controller.on_randomize_playlist,
            'on_collection_manager_item_activate': self.controller.collection_manager,
            'on_goto_playing_track_activate': self.controller.on_goto_playing_track,
            'on_queue_manager_item_activate': self.controller.queue_manager,
            'on_preferences_item_activate': lambda *e: self.controller.show_preferences(),
            'on_device_manager_item_activate': lambda *e: self.controller.show_devices(),
            'on_cover_manager_item_activate': self.controller.show_cover_manager,
            'on_open_item_activate': self.controller.open_dialog,
            'on_open_url_item_activate': self.controller.open_url,
            'on_export_current_playlist_activate': self.controller.export_current_playlist,
            'on_panel_notebook_switch_page': self.controller.on_panel_switch,
            'on_track_properties_activate':self.controller.on_track_properties,
            'on_clear_playlist_item_activate': self.on_clear_playlist,
        })        

        event.add_callback(self.on_playback_end, 'playback_player_end',
            self.player)
        event.add_callback(self.on_playback_start, 'playback_track_start',
            self.player) 
        event.add_callback(self.on_toggle_pause, 'playback_toggle_pause',
            self.player)
        event.add_callback(self.on_tags_parsed, 'tags_parsed',
            self.player)
        event.add_callback(self.on_buffering, 'playback_buffering',
            self.player)
        event.add_callback(self.on_playback_error, 'playback_error', 
            self.player)

        # Monitor the queue
        event.add_callback(self.update_track_counts,
            'tracks_added', self.queue)
        event.add_callback(self.update_track_counts,
            'tracks_removed', self.queue)

        event.add_callback(self.queue_playlist_draw, 'stop_track', self.queue)
        
        # Settings
        event.add_callback(self._on_setting_change, 'option_set')

    def queue_playlist_draw(self, *e):
        self.get_selected_playlist().list.queue_draw()

    def _connect_panel_events(self):
        """
            Sets up panel events
        """
        # panels
        panels = self.controller.panels

        for panel_name in ('playlists', 'radio', 'files', 'collection'):
            panel = panels[panel_name]
            sort = False
            if panel_name in ('files', 'collection'): sort = True
            panel.connect('append-items', lambda panel, items, sort=sort:
                self.on_append_items(items, sort=sort))
            panel.connect('queue-items', lambda panel, items, sort=sort:
                self.on_append_items(items, queue=True, sort=sort))

        ## Collection Panel
        panel = panels['collection']
        panel.connect('collection-tree-loaded', lambda *e:
            self.update_track_counts())

        ## Playlist Panel
        panel = panels['playlists']
        panel.connect('playlist-selected',
            lambda panel, playlist: self.add_playlist(playlist))

        ## Radio Panel
        panel = panels['radio']
        panel.connect('playlist-selected',
            lambda panel, playlist: self.add_playlist(playlist))

        ## Files Panel
        panel = panels['files']

    def on_append_items(self, items, queue=False, sort=False):
        """
            Called when a panel (or other component) has tracks to append and
            possibly queue
        """
        if not items: return
        pl = self.get_selected_playlist()

        if sort:
            items = trackdb.sort_tracks(
                ('artist', 'date', 'album', 'discnumber', 'tracknumber'),
                items)

        pl.playlist.add_tracks(items, add_duplicates=False)
        if queue:
            self.queue.add_tracks(items, add_duplicates=False)
        pl.list.queue_draw()

    @guiutil.idle_add()
    def on_playback_error(self, type, player, message):
        """
            Called when there has been a playback error
        """
        # for some reason using the gtk.MessageDialog.run() and
        # gtk.MessageDialog.hide() here causes the whole system to lock up, so
        # instead we just connect to the response method and hide it when the
        # ok button is clicked
        dialog = gtk.MessageDialog(self.window, gtk.DIALOG_MODAL, gtk.MESSAGE_INFO,
            gtk.BUTTONS_OK)
        dialog.set_markup(message)
        dialog.connect('response', lambda dialog=dialog, *e: dialog.hide())
        dialog.show_all()

    def on_buffering(self, type, player, percent):
        """
            Called when a stream is buffering
        """
        if percent < 100:
            self.statusbar.set_status(_("Buffering: %d%%...") % percent, 1000)
        else:
            self.statusbar.set_status(_("Buffering: 100%..."), 1000)

    def on_tags_parsed(self, type, player, args):
        """
            Called when tags are parsed from a stream/track
        """
        (tr, args) = args
        if not tr or tr.is_local(): 
            return
        if track.parse_stream_tags(tr, args):
            self._update_track_information()
            self.cover.on_playback_start('', self.player, None)
            self.get_selected_playlist().refresh_row(tr)

    def on_toggle_pause(self, type, player, object):
        """
            Called when the user clicks the play button after playback has
            already begun
        """
        if player.is_paused():
            image = gtk.image_new_from_stock('gtk-media-play',
                gtk.ICON_SIZE_SMALL_TOOLBAR)
        else:
            image = gtk.image_new_from_stock('gtk-media-pause',
                gtk.ICON_SIZE_SMALL_TOOLBAR)
            
        self.play_button.set_image(image)
        self._update_track_information()
        
        # refresh the current playlist
        pl = self.get_selected_playlist()
        if pl:
            pl.list.queue_draw()

    def close_playlist_tab(self, tab=None):
        """
            Closes the tab specified
            @param tab: the tab number to close.  If no number is specified,
                the currently selected tab is closed
        """
        if tab is None:
            tab = self.playlist_notebook.get_current_page()
        pl = self.playlist_notebook.get_nth_page(tab)
        if pl.on_closing():
            if self.queue.current_playlist == pl.playlist:
                self.queue.current_playlist = None
            self.playlist_notebook.remove_page(tab)

    def on_playlist_notebook_switch(self, notebook, page, page_num):
        """
            Called when the page is changed in the playlist notebook
        """
        page = notebook.get_nth_page(page_num)
        self.current_page = page_num
        playlist = self.get_selected_playlist()
        self.queue.set_current_playlist(playlist.playlist)
        self.set_mode_toggles()
        self.update_track_counts()

    def on_playlist_notebook_remove(self, notebook, widget):
        """
            Called when a tab is removed from the playlist notebook
        """
        pagecount = notebook.get_n_pages()
        if pagecount == 1:
            notebook.set_show_tabs(settings.get_option('gui/show_tabbar', True))
        elif pagecount == 0:
            self.add_playlist()

    def on_playlist_notebook_button_press(self, notebook, event):
        if event.type == gtk.gdk.BUTTON_PRESS and event.button == 2:
            self.add_playlist()

    def on_search_collection_focus(self, *e):
        """
            Gives focus to the collection search bar
        """
        
        self.controller.panels['collection'].filter.grab_focus()

    def on_search_playlist_focus(self, *e):
        """
            Gives focus to the playlist search bar
        """
        self.filter.grab_focus()

    def on_save_playlist(self, *e):
        """
            Called when the user presses Ctrl+S
            Spawns the save dialog of the currently selected playlist tab if
            not custom, saves changes directly if custom
        """
        tab = self.get_selected_tab()
        if not tab: return
        if tab.page.playlist.get_is_custom():
            tab.do_save_changes_to_custom()
        else:
            tab.do_save_custom()

    def on_save_playlist_as(self, *e):
        """
            Called when the user presses Ctrl+S
            Spawns the save as dialog of the current playlist tab
        """
        tab = self.get_selected_tab()
        if not tab: return
        tab.do_save_custom()

    def on_clear_queue(self):
        """
            Called when the user requests to clear the queue
        """
        self.queue.clear()
        self.queue_playlist_draw()

    def on_clear_playlist(self, *e):
        """
            Clears the current playlist tab
        """
        playlist = self.get_selected_playlist()
        if not playlist: return
        playlist.playlist.clear()

    def set_mode_toggles(self, *e):
        """
            Called when the user clicks one of the playback mode buttons
        """
        settings.set_option('playback/shuffle', 
                self.shuffle_toggle.get_active())
        settings.set_option('playback/repeat', 
                self.repeat_toggle.get_active())
        settings.set_option('playback/dynamic', 
                self.dynamic_toggle.get_active())

        pl = self.get_selected_playlist()
        if pl:
            pl.playlist.set_random(self.shuffle_toggle.get_active())
            pl.playlist.set_repeat(self.repeat_toggle.get_active())

    def on_playback_start(self, type, player, object):
        """
            Called when playback starts
            Sets the currently playing track visible in the currently selected
            playlist if the user has chosen this setting
        """
        pl = self.get_selected_playlist()
        if player.current in pl.playlist.ordered_tracks:
            path = (pl.playlist.index(player.current),)
        
            if settings.get_option('gui/ensure_visible', True):
                pl.list.scroll_to_cell(path)

            gobject.idle_add(pl.list.set_cursor, path)

        self._update_track_information()
        self.draw_playlist(type, player, object)
        self.play_button.set_image(gtk.image_new_from_stock('gtk-media-pause',
                gtk.ICON_SIZE_SMALL_TOOLBAR))
        self.update_track_counts()

        if settings.get_option('playback/dynamic', False):
            self._get_dynamic_tracks()

        if settings.get_option('osd/enabled', True):
            self.osd.show(self.player.current)

    def on_playback_end(self, type, player, object):
        """
            Called when playback ends
        """
        self.track_title_label.set_label(_('Not Playing'))
        self.track_info_label.set_label(_('Stopped'))
        self.window.set_title('Exaile')
        self._update_track_information()

        self.draw_playlist(type, player, object)
        self.play_button.set_image(gtk.image_new_from_stock('gtk-media-play',
                gtk.ICON_SIZE_SMALL_TOOLBAR))

    def _on_setting_change(self, name, object, option):
        """
           Handles changes of settings
        """
        if option == 'player/volume':
            self.volume_slider.set_value(settings.get_option(option, 1))

        if option == 'gui/show_tabbar':
            self.playlist_notebook.set_show_tabs(
                settings.get_option(option, True)
            )

        if option == 'gui/tab_placement':
            map = {
                'left': gtk.POS_LEFT,
                'right': gtk.POS_RIGHT,
                'top': gtk.POS_TOP,
                'bottom': gtk.POS_BOTTOM
            }
            self.playlist_notebook.set_tab_pos(map.get(
                settings.get_option(option, 'top')))

        if option == 'gui/use_tray':
            usetray = settings.get_option(option, False)
            if self.controller.tray_icon and not usetray:
                self.controller.tray_icon.destroy()
                self.controller.tray_icon = None
            elif not self.controller.tray_icon and usetray:
                self.controller.tray_icon = tray.TrayIcon(self)

        if option == 'playback/dynamic':
            if self.controller.tray_icon:
                self.controller.tray_icon.check_dyna.set_active(settings.get_option('playback/dynamic', False))
            self.dynamic_toggle.set_active(settings.get_option('playback/dynamic', False))

        if option == 'playback/shuffle':
            if self.controller.tray_icon:
                self.controller.tray_icon.check_shuffle.set_active(settings.get_option('playback/shuffle', False))
            self.shuffle_toggle.set_active(settings.get_option('playback/shuffle', False))

        if option == 'playback/repeat':
            if self.controller.tray_icon:
                self.controller.tray_icon.check_repeat.set_active(settings.get_option('playback/repeat', False))
            self.repeat_toggle.set_active(settings.get_option('playback/repeat', False))

    @common.threaded
    def _get_dynamic_tracks(self):
        """
            Gets some dynamic tracks from the dynamic manager.  

            This tries to keep at least 5 tracks the current playlist... if
            there are already 5, it just adds one
        """
        playlist = self.get_selected_playlist().playlist
        
        self.controller.exaile.dynamic.populate_playlist(playlist)

    def _update_track_information(self):
        """
            Sets track information
        """
        track = self.player.current
        tray_icon = self.controller.tray_icon

        if not track:
            if tray_icon:
                tray_icon.set_tooltip(_("Exaile Music Player\nNot playing"))
            return

        artist = track['artist']
        album = track['album']
        title = track['title']
        if title is None: 
            title = ''
        else:
            title = " / ".join(title)
        if album is None: 
            album = ''
        else:
            album = " / ".join(album)
        if artist is None: 
            artist = ''
        else:
            artist = " / ".join(artist)

        # Update window title.
        if artist:
            # TRANSLATORS: Window title
            self.window.set_title(_("%(title)s (by %(artist)s)" %
                { 'title': title, 'artist': artist }) + " - Exaile")
        else:
            self.window.set_title(title + " - Exaile")

        # Update track info display and tray tooltip.
        self.track_title_label.set_label(title)
        if album or artist:
            desc = []
            # TRANSLATORS: Part of the sentence: "(title) by (artist) from (album)"
            if artist: desc.append(_("by %s") % artist)
            # TRANSLATORS: Part of the sentence: "(title) by (artist) from (album)"
            if album: desc.append(_("from %s") % album)

            desc = '\n'.join(desc)
            self.track_info_label.set_label(desc)
        else:
            self.track_info_label.set_label("")
            desc = None
        if tray_icon:
            tip = title
            if desc: tip += '\n' + desc
            if self.player.is_paused():
                tray_icon.set_tooltip(_("In pause: %s") % tip)
            else:
                tray_icon.set_tooltip(_("Playing %s") % tip)

    def draw_playlist(self, *e):
        """
            Called when playback starts, redraws the playlist
        """
        page = self.playlist_notebook.get_current_page()
        page = self.playlist_notebook.get_nth_page(page)
        gobject.idle_add(page.queue_draw)

    def get_selected_playlist(self):
        """
            Returns the currently selected playlist
        """
        page = self.playlist_notebook.get_nth_page(self.current_page)
        if page: return page
        num = self.playlist_notebook.get_current_page()
        page = self.playlist_notebook.get_nth_page(num)
        return page

    get_current_playlist = get_selected_playlist

    def get_selected_tab(self):
        """
            Returns the currently selected tab
        """
        page = self.playlist_notebook.get_nth_page(self.current_page)
        if not page:
            num = self.playlist_notebook.get_current_page()
            page = self.playlist_notebook.get_nth_page(num)
        return self.playlist_notebook.get_tab_label(page)

    get_current_tab = get_selected_tab

    def on_play_clicked(self, *e):
        """
            Called when the play button is clicked
        """
        if self.player.is_paused() or self.player.is_playing():
            self.player.toggle_pause()
        else:
            pl = self.get_selected_playlist()
            self.queue.set_current_playlist(pl.playlist)
            if pl:
                track = pl.get_selected_track()
                if track:
                    pl.playlist.set_current_pos(
                        pl.playlist.index(track))
            self.queue.play()

    def _setup_position(self):
        """
            Sets up the position and sized based on the size the window was
            when it was last moved or resized
        """
        if settings.get_option('gui/mainw_maximized', False):
            self.window.maximize()
            
        width = settings.get_option('gui/mainw_width', 500)
        height = settings.get_option('gui/mainw_height', 475)
        x = settings.get_option('gui/mainw_x', 10)
        y = settings.get_option('gui/mainw_y', 10)

        self.window.move(x, y)
        self.window.resize(width, height)

        pos = settings.get_option('gui/mainw_sash_pos', 200)
        self.splitter.set_position(pos)

    def delete_event(self, *e):
        """
            Called when the user attempts to close the window
        """
        if self.controller.tray_icon:
            self.window.hide()
        else:
            self.quit()
        return True

    def quit(self, *e):
        """
            quits exaile
        """
        self.window.hide()
        gobject.idle_add(self.controller.exaile.quit)
        return True

    def toggle_visible(self):
        """
            Toggles visibility of the main window
        """
        toggle_handled = self.emit('main-visible-toggle')
        if not toggle_handled and self.window.is_active(): # focused
            self.window.hide()
        elif not toggle_handled:
            self.window.deiconify()
            self.window.present()

    def configure_event(self, *e):
        """
            Called when the window is resized or moved
        """
        # Don't save window size if it is maximized or fullscreen.
        if settings.get_option('gui/mainw_maximized', False) or \
                self._fullscreen:
            return False

        (width, height) = self.window.get_size()
        if [width, height] != [ settings.get_option("gui/mainw_"+key, -1) for \
                key in ["width", "height"] ]:
            settings.set_option('gui/mainw_height', height)
            settings.set_option('gui/mainw_width', width)
        (x, y) = self.window.get_position()
        if [x, y] != [ settings.get_option("gui/mainw_"+key, -1) for \
                key in ["x", "y"] ]:
            settings.set_option('gui/mainw_x', x)
            settings.set_option('gui/mainw_y', y)
        pos = self.splitter.get_position()
        if pos > 10 and pos != settings.get_option(
                "gui/mainw_sash_pos", -1):
            settings.set_option('gui/mainw_sash_pos', pos)

        return False

    def window_state_change_event(self, window, event):
        """
            Saves the current maximized and fullscreen
            states and minimizes to tray if requested
        """
        if event.changed_mask & gtk.gdk.WINDOW_STATE_MAXIMIZED:
            settings.set_option('gui/mainw_maximized',
                bool(event.new_window_state & gtk.gdk.WINDOW_STATE_MAXIMIZED))
        if event.changed_mask & gtk.gdk.WINDOW_STATE_FULLSCREEN:
            self._fullscreen = bool(event.new_window_state & gtk.gdk.WINDOW_STATE_FULLSCREEN)

        if settings.get_option('gui/minimize_to_tray', False) and \
            self.controller.tray_icon is not None:
            data = window.window.property_get('_NET_WM_STATE')
            if data is not None and '_NET_WM_STATE_HIDDEN' in data[2]:
                window.hide()

        return False

def get_playlist_nb():
    return MainWindow._mainwindow.playlist_notebook

def get_selected_playlist():
    return MainWindow._mainwindow.get_selected_playlist()

def mainwindow():
    return MainWindow._mainwindow
