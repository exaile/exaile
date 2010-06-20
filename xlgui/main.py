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

import datetime
import logging
import os
import re
import threading

import cairo
import glib
import gobject
import pygst
pygst.require('0.10')
import gst
import pygtk
pygtk.require('2.0')
import gtk
import pango

from xl import (
    common,
    event,
    formatter,
    player,
    providers,
    settings,
    trax,
    xdg
)
from xl.nls import gettext as _
import xl.playlist
from xlgui import (
    cover,
    guiutil,
    playlist,
    tray
)
from xlgui.widgets import dialogs, info, menu

logger = logging.getLogger(__name__)

class PlaybackProgressBar(object):
    def __init__(self, bar, player):
        self.bar = bar
        self.player = player
        self.timer_id = None
        self.seeking = False
        self.formatter = guiutil.ProgressBarFormatter()

        self.bar.set_text(_('Not Playing'))
        self.bar.connect('button-press-event', self.seek_begin)
        self.bar.connect('button-release-event', self.seek_end)
        self.bar.connect('motion-notify-event', self.seek_motion_notify)

        event.add_callback(self.playback_start,
            'playback_player_start', player)
        event.add_callback(self.playback_toggle_pause,
            'playback_toggle_pause', player)
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

        tr = self.player.current
        if not tr or not (tr.is_local() or \
                tr.get_tag_raw('__length')): return
        length = tr.get_tag_raw('__length')

        seconds = float(value * length)
        self.player.seek(seconds)
        self.seeking = False
        self.bar.set_fraction(value)
        self.bar.set_text(self.formatter.format(seconds, length))
#        self.emit('seek', seconds)

    def seek_motion_notify(self, widget, event):
        tr = self.player.current
        if not tr or not(tr.is_local() or \
                tr.get_tag_raw('__length')): return

        mouse_x, mouse_y = event.get_coords()
        progress_loc = self.bar.get_allocation()

        value = mouse_x / progress_loc.width

        if value < 0: value = 0
        if value > 1: value = 1

        self.bar.set_fraction(value)
        length = tr.get_tag_raw('__length')
        seconds = float(value * length)
        remaining_seconds = length - seconds
        self.bar.set_text(self.formatter.format(seconds, length))

    def playback_start(self, type, player, object):
        if self.timer_id:
            glib.source_remove(self.timer_id)
            self.timer_id = None
        self.__add_timer_update()

    def playback_toggle_pause(self, type, player, object):
        if self.timer_id:
            glib.source_remove(self.timer_id)
            self.timer_id = None
        if not player.is_paused():
            self.__add_timer_update()

    def __add_timer_update(self):
        freq = settings.get_option("gui/progress_update_millisecs", 1000)
        if freq % 1000 == 0:
            self.timer_id = glib.timeout_add_seconds(freq/1000, self.timer_update)
        else:
            self.timer_id = glib.timeout_add(freq, self.timer_update)

    def playback_end(self, type, player, object):
        if self.timer_id: glib.source_remove(self.timer_id)
        self.timer_id = None
        self.bar.set_text(_('Not Playing'))
        self.bar.set_fraction(0)

    def timer_update(self, *e):
        tr = self.player.current
        if not tr: return
        if self.seeking: return True

        if not tr.is_local() and not tr.get_tag_raw('__length'):
            self.bar.set_fraction(0)
            self.bar.set_text(_('Streaming...'))
            return True

        self.bar.set_fraction(self.player.get_progress())

        seconds = self.player.get_time()
        length = tr.get_tag_raw('__length')
        self.bar.set_text(self.formatter.format(seconds, length))

        return True



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

        self.controller = controller
        self.covers = covers
        self.collection =  collection
        self.player = player
        self.playlist_manager = controller.exaile.playlists
        self.queue = queue
        self.current_page = -1
        self._fullscreen = False
        self.resuming = False

        self.builder = builder

        self.window = self.builder.get_object('ExaileWindow')
        self.window.set_title('Exaile')
        self.title_formatter = formatter.TrackFormatter(settings.get_option(
            'gui/main_window_title_format', _('$title (by $artist)')))

        self._setup_widgets()
        self._setup_position()
        self._setup_hotkeys()
        logger.info("Connecting main window events...")
        self._connect_events()
        from xlgui import osd
        self.osd = osd.OSDWindow(self.player)
        MainWindow._mainwindow = self

    def _setup_hotkeys(self):
        """
            Sets up accelerators that haven't been set up in UI designer
        """
        hotkeys = (
            ('<Control>W', lambda *e: self.close_playlist_tab()), # FIXME
            ('<Control>S', lambda *e: self.on_save_playlist()),
            ('<Shift><Control>S', lambda *e: self.on_save_playlist_as()),
            ('<Control>F', lambda *e: self.on_search_collection_focus()),
            ('<Control>G', lambda *e: self.on_search_playlist_focus()), # FIXME
            ('<Control>D', lambda *e: self.on_queue()), # FIXME
            ('<Control><Alt>l', lambda *e: self.on_clear_queue()), # FIXME
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
        if self.controller.exaile.options.Debug:
            logger.info("Enabling Restart menu item")
            restart_item = self.builder.get_object('restart_item')
            restart_item.set_property('visible', True)
            restart_item.set_no_show_all(False)

        playlist_columns_menu = menu.ProviderMenu('playlist-columns-menu', self.window)
        self.builder.get_object('columns_menu').set_submenu(playlist_columns_menu)

        # TODO: Maybe make this stackable
        self.message = dialogs.MessageBar(
            parent=self.builder.get_object('player_box'),
            buttons=gtk.BUTTONS_CLOSE
        )
        self.message.connect('response', self.on_messagebar_response)

        self.info_area = info.TrackInfoPane(auto_update=True)
        self.info_area.set_padding(3, 3, 3, 3)
        guiutil.gtk_widget_replace(self.builder.get_object('info_area'), self.info_area)

        self.cover = cover.CoverWidget(self.info_area.cover_image)

        self.volume_control = guiutil.VolumeControl()
        self.info_area.get_action_area().pack_start(self.volume_control)

        if settings.get_option('gui/use_alpha', False):
            screen = self.window.get_screen()
            colormap = screen.get_rgba_colormap()

            if colormap is not None:
                self.window.set_app_paintable(True)
                self.window.set_colormap(colormap)

                self.window.connect('expose-event', self.on_expose_event)
                self.window.connect('screen-changed', self.on_screen_changed)

        playlist_area = self.builder.get_object('playlist_area')
        self.playlist_notebook = playlist.PlaylistNotebook('saved_tabs')
        self.playlist_notebook.connect_after('switch-page',
            self.on_playlist_notebook_switch_page)
        playlist_area.pack_start(self.playlist_notebook, padding=3)
        page_num = self.playlist_notebook.get_current_page()
        page = self.playlist_notebook.get_nth_page(page_num)
        selection = page.view.get_selection()
        selection.connect('changed', self.on_playlist_view_selection_changed)

        visible = settings.get_option('gui/playlist_utilities_bar_visible', True)
        self.builder.get_object('playlist_utilities_bar_visible').set_active(visible)

        self.splitter = self.builder.get_object('splitter')

        self.progress_bar = PlaybackProgressBar(
            self.builder.get_object('playback_progressbar'),
            self.player
        )

        for button in ('playpause', 'next', 'prev', 'stop'):
            setattr(self, '%s_button' % button,
                self.builder.get_object('%s_button' % button))

        self.stop_button.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.stop_button.connect('motion-notify-event',
            self.on_stop_button_motion_notify_event)
        self.stop_button.connect('leave-notify-event',
            self.on_stop_button_leave_notify_event)
        self.stop_button.connect('key-press-event',
            self.on_stop_button_key_press_event)
        self.stop_button.connect('key-release-event',
            self.on_stop_button_key_release_event)
        self.stop_button.connect('focus-out-event',
            self.on_stop_button_focus_out_event)
        self.stop_button.connect('button-press-event',
            self.on_stop_button_press_event)

        self.statusbar = info.Statusbar(self.builder.get_object('status_bar'))
        event.add_callback(self.on_exaile_loaded, 'exaile_loaded')

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
            'on_restart_item_activate': self.on_restart_item_activate,
            'on_playpause_button_clicked': self.on_playpause_button_clicked,
            'on_next_button_clicked':
                lambda *e: self.queue.next(),
            'on_prev_button_clicked':
                lambda *e: self.queue.prev(),
            'on_new_playlist_item_activated': lambda *e:
                self.playlist_notebook.create_new_playlist(),
            'on_queue_count_clicked': self.controller.queue_manager,
            'on_clear_playlist_item_activate': self.on_clear_playlist,
            'on_playlist_utilities_bar_visible_toggled': self.on_playlist_utilities_bar_visible_toggled,
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
            'on_open_dir_item_activate': self.controller.open_dir,
            'on_export_current_playlist_activate': self.controller.export_current_playlist,
            'on_panel_notebook_switch_page': self.controller.on_panel_switch,
            'on_track_properties_activate':self.controller.on_track_properties,
        })

        event.add_callback(self.on_playback_resume, 'playback_player_resume',
            self.player)
        event.add_callback(self.on_playback_end, 'playback_player_end',
            self.player)
        event.add_callback(self.on_playback_end, 'playback_error',
            self.player)
        event.add_callback(self.on_playback_start, 'playback_track_start',
            self.player)
        event.add_callback(self.on_toggle_pause, 'playback_toggle_pause',
            self.player)
        event.add_callback(self.on_tags_parsed, 'tags_parsed',
            self.player)
        event.add_callback(self.on_track_tags_changed, 'track_tags_changed')
        event.add_callback(self.on_buffering, 'playback_buffering',
            self.player)
        event.add_callback(self.on_playback_error, 'playback_error',
            self.player)

        event.add_callback(self.on_playlist_tracks_added,
            'playlist_tracks_added')
        event.add_callback(self.on_playlist_tracks_removed,
            'playlist_tracks_removed')

        # Settings
        event.add_callback(self._on_option_set, 'option_set')

    def _connect_panel_events(self):
        """
            Sets up panel events
        """
        # panels
        panels = self.controller.panels

        for panel_name in ('playlists', 'radio', 'files', 'collection'):
            panel = panels[panel_name]
            sort = False

            if panel_name in ('files', 'collection'):
                sort = True

            panel.connect('append-items', lambda panel, items, sort=sort:
                self.on_append_items(items, sort=sort))
            panel.connect('queue-items', lambda panel, items, sort=sort:
                self.on_append_items(items, queue=True, sort=sort))
            panel.connect('replace-items', lambda panel, items, sort=sort:
                self.on_append_items(items, replace=True, sort=sort))

        ## Collection Panel
        panel = panels['collection']
        panel.connect('collection-tree-loaded', self.on_collection_tree_loaded)

        ## Playlist Panel
        panel = panels['playlists']
        panel.connect('playlist-selected',
            lambda panel, playlist:
                self.playlist_notebook.create_tab_from_playlist(playlist))

        ## Radio Panel
        panel = panels['radio']
        panel.connect('playlist-selected',
            lambda panel, playlist:
                self.playlist_notebook.create_tab_from_playlist(playlist))

        ## Files Panel
        panel = panels['files']

    def on_expose_event(self, widget, event):
        """
            Paints the window alpha transparency
        """
        opacity = 1 - settings.get_option('gui/transparency', 0.3)
        context = widget.window.cairo_create()
        background = widget.style.bg[gtk.STATE_NORMAL]
        context.set_source_rgba(
            float(background.red) / 256**2,
            float(background.green) / 256**2,
            float(background.blue) / 256**2,
            opacity
        )
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()

    def on_screen_changed(self, widget, event):
        """
            Updates the colormap on screen change
        """
        screen = widget.get_screen()
        colormap = screen.get_rgba_colormap() or screen.get_rgb_colormap()
        self.window.set_colormap(rgbamap)

    def on_messagebar_response(self, widget, response):
        """
            Hides the messagebar if requested
        """
        if response == gtk.RESPONSE_CLOSE:
            widget.hide()

    def on_stop_button_motion_notify_event(self, widget, event):
        """
            Sets the hover state and shows SPAT icon
        """
        widget.set_data('hovered', True)
        if event.state & gtk.gdk.SHIFT_MASK:
            widget.set_image(gtk.image_new_from_stock(
                gtk.STOCK_STOP, gtk.ICON_SIZE_BUTTON))
        else:
            widget.set_image(gtk.image_new_from_stock(
                gtk.STOCK_MEDIA_STOP, gtk.ICON_SIZE_BUTTON))

    def on_stop_button_leave_notify_event(self, widget, event):
        """
            Unsets the hover state and resets the button icon
        """
        widget.set_data('hovered', False)
        if not widget.is_focus() and \
           ~(event.state & gtk.gdk.SHIFT_MASK):
            widget.set_image(gtk.image_new_from_stock(
                gtk.STOCK_MEDIA_STOP, gtk.ICON_SIZE_BUTTON))

    def on_stop_button_key_press_event(self, widget, event):
        """
            Shows SPAT icon on Shift key press
        """
        if event.keyval in (gtk.keysyms.Shift_L, gtk.keysyms.Shift_R):
            widget.set_image(gtk.image_new_from_stock(
                gtk.STOCK_STOP, gtk.ICON_SIZE_BUTTON))
            widget.set_data('toggle_spat', True)

        if event.keyval in (gtk.keysyms.space, gtk.keysyms.Return):
            if widget.get_data('toggle_spat'):
                self.on_spat_clicked()
            else:
                self.player.stop()

    def on_stop_button_key_release_event(self, widget, event):
        """
            Resets the button icon
        """
        if event.keyval in (gtk.keysyms.Shift_L, gtk.keysyms.Shift_R):
            widget.set_image(gtk.image_new_from_stock(
                gtk.STOCK_MEDIA_STOP, gtk.ICON_SIZE_BUTTON))
            widget.set_data('toggle_spat', False)

    def on_stop_button_focus_out_event(self, widget, event):
        """
            Resets the button icon unless
            the button is still hovered
        """
        if not widget.get_data('hovered'):
            widget.set_image(gtk.image_new_from_stock(
                gtk.STOCK_MEDIA_STOP, gtk.ICON_SIZE_BUTTON))

    def on_stop_button_press_event(self, widget, event):
        """
            Called when the user clicks on the stop button
        """
        if event.button == 1:
            if event.state & gtk.gdk.SHIFT_MASK:
                self.on_spat_clicked()
            else:
                self.player.stop()
        elif event.button == 3:
            menu = guiutil.Menu()
            menu.append(_("Toggle: Stop after Selected Track"),
                self.on_spat_clicked,
                gtk.STOCK_STOP)
            menu.popup(None, None, None, event.button, event.time)

    def on_spat_clicked(self, *e):
        """
            Called when the user clicks on the SPAT item
        """
        trs = self.get_selected_page().get_selected_tracks()
        if not trs: return
        tr = trs[0]

        if tr == self.queue.stop_track:
            self.queue.stop_track = None
        else:
            self.queue.stop_track = tr

        self.get_selected_page().list.queue_draw()

    def on_append_items(self, tracks, queue=False, sort=False, replace=False):
        """
            Called when a panel (or other component)
            has tracks to append and possibly queue

            :param tracks: The tracks to append
            :param queue: Additionally queue tracks
            :param sort: Sort before adding
            :param replace: Clear playlist before adding
        """
        if not tracks:
            return

        pl = self.get_selected_page()

        if sort:
            tracks = trax.sort_tracks(
                ('artist', 'date', 'album', 'discnumber', 'tracknumber'),
                tracks)

        if replace:
            pl.playlist.clear()

        offset = len(pl.playlist)
        pl.playlist.extend(tracks)

        if queue:
            self.queue.extend(tracks)

        if not self.player.current:
            track = tracks[0]
            pl.playlist.current_position = offset
            player.QUEUE.set_current_playlist(pl.playlist)
            player.QUEUE.play(track=track)

    def on_playback_error(self, type, player, message):
        """
            Called when there has been a playback error
        """
        self.message.show_error(_('Playback error encountered!'), message)

    def on_buffering(self, type, player, percent):
        """
            Called when a stream is buffering
        """
        percent = min(percent, 100)
        self.statusbar.set_status(_("Buffering: %d%%...") % percent, 1)

    def on_tags_parsed(self, type, player, args):
        """
            Called when tags are parsed from a stream/track
        """
        (tr, args) = args
        if not tr or tr.is_local():
            return
        if player.parse_stream_tags(tr, args):
            self._update_track_information()
            self.cover.on_playback_start('', self.player, None)
            self.get_selected_page().refresh_row(tr)

        if settings.get_option('osd/enabled', True):
            self.osd.show(player.current)

    def on_track_tags_changed(self, type, track, tag):
        """
            Called when tags are changed
        """
        if track is self.player.current:
            self._update_track_information()

    def on_collection_tree_loaded(self, tree):
        """
            Updates information on collection tree load
        """
        self.statusbar.update_info()

    def on_exaile_loaded(self, event_type, exaile, nothing):
        """
            Updates information on exaile load
        """
        self.statusbar.update_info()
        event.remove_callback(self.on_exaile_loaded, 'exaile_loaded')

    def on_playlist_tracks_added(self, type, playlist, tracks):
        """
            Updates information on track add
        """
        self.statusbar.update_info()

    def on_playlist_tracks_removed(self, type, playlist, tracks):
        """
            Updates information on track removal
        """
        self.statusbar.update_info()

    def on_toggle_pause(self, type, player, object):
        """
            Called when the user clicks the play button after playback has
            already begun
        """
        if player.is_paused():
            image = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PLAY,
                gtk.ICON_SIZE_SMALL_TOOLBAR)
            tooltip = _('Continue Playback')
        else:
            image = gtk.image_new_from_stock(gtk.STOCK_MEDIA_PAUSE,
                gtk.ICON_SIZE_SMALL_TOOLBAR)
            tooltip = _('Pause Playback')

        self.playpause_button.set_image(image)
        self.playpause_button.set_tooltip_text(tooltip)
        self._update_track_information()

        # refresh the current playlist
        pl = self.get_selected_page()

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

    def on_collection_tree_loaded(self, tree):
        """
            Updates info after collection tree load
        """
        self.statusbar.update_info()

    def on_playlist_notebook_switch_page(self, notebook, page, page_num):
        """
            Updates info after notebook page switch
        """
        page = self.playlist_notebook.get_nth_page(page_num)
        selection = page.view.get_selection()
        selection.connect('changed', self.on_playlist_view_selection_changed)
        self.statusbar.update_info()

    def on_playlist_view_selection_changed(self, selection):
        """
            Updates info after playlist page selection change
        """
        self.statusbar.update_info()

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
        playlist = self.get_selected_page()
        if not playlist: return
        playlist.playlist.clear()

    def on_playlist_utilities_bar_visible_toggled(self, checkmenuitem):
        """
            Shows or hides the playlist utilities bar
        """
        settings.set_option('gui/playlist_utilities_bar_visible',
            checkmenuitem.get_active())

    def on_playback_resume(self, type, player, data):
        self.resuming = True

    def on_playback_start(self, type, player, object):
        """
            Called when playback starts
            Sets the currently playing track visible in the currently selected
            playlist if the user has chosen this setting
        """
        if self.resuming:
            self.resuming = False
            return

        self._update_track_information()
        self.playpause_button.set_image(gtk.image_new_from_stock(gtk.STOCK_MEDIA_PAUSE,
                gtk.ICON_SIZE_SMALL_TOOLBAR))
        self.playpause_button.set_tooltip_text(_('Pause Playback'))

        if settings.get_option('playback/dynamic', False):
            self._get_dynamic_tracks()

        if settings.get_option('osd/enabled', True):
            self.osd.show(self.player.current)

    def on_playback_end(self, type, player, object):
        """
            Called when playback ends
        """
        self.window.set_title('Exaile')
        self._update_track_information()

        self.playpause_button.set_image(gtk.image_new_from_stock(gtk.STOCK_MEDIA_PLAY,
                gtk.ICON_SIZE_SMALL_TOOLBAR))
        self.playpause_button.set_tooltip_text(_('Start Playback'))

    def _on_option_set(self, name, object, option):
        """
           Handles changes of settings
        """
        if option == 'gui/main_window_title_format':
            self.title_formatter.props.format = settings.get_option(
                option, self.title_formatter.props.format)

        if option == 'gui/use_tray':
            usetray = settings.get_option(option, False)
            if self.controller.tray_icon and not usetray:
                self.controller.tray_icon.destroy()
                self.controller.tray_icon = None
            elif not self.controller.tray_icon and usetray:
                self.controller.tray_icon = tray.TrayIcon(self)

    def _update_track_information(self):
        """
            Sets track information
        """
        track = self.player.current

        if not track:
            return

        self.window.set_title(self.title_formatter.format(track))

    def on_playpause_button_clicked(self, *e):
        """
            Called when the play button is clicked
        """
        if player.PLAYER.is_paused() or player.PLAYER.is_playing():
            player.PLAYER.toggle_pause()
        else:
            pl = self.get_selected_page()
            player.QUEUE.set_current_playlist(pl.playlist)
            try:
                trackpath = pl.view.get_selected_paths()[0]
                pl.playlist.current_position = trackpath[0]
            except IndexError:
                pass
            player.QUEUE.play(track=pl.playlist.current)

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
            Quits Exaile
        """
        self.window.hide()
        glib.idle_add(self.controller.exaile.quit)
        return True

    def on_restart_item_activate(self, menuitem):
        """
            Restarts Exaile
        """
        self.window.hide()
        glib.idle_add(self.controller.exaile.quit, True)

    def toggle_visible(self, bringtofront=False):
        """
            Toggles visibility of the main window
        """
        toggle_handled = self.emit('main-visible-toggle')

        if not toggle_handled:
            if bringtofront and self.window.is_active() or \
               not bringtofront and self.window.get_property('visible'):
                self.window.hide()
            elif not toggle_handled:
                self.window.present()

    def configure_event(self, *e):
        """
            Called when the window is resized or moved
        """
        pos = self.splitter.get_position()
        if pos > 10 and pos != settings.get_option(
                "gui/mainw_sash_pos", -1):
            settings.set_option('gui/mainw_sash_pos', pos)

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

        if settings.get_option('gui/minimize_to_tray', False):
            wm_state = window.window.property_get('_NET_WM_STATE')

            if wm_state is not None:
                if '_NET_WM_STATE_HIDDEN' in wm_state[2]:
                    if not settings.get_option('gui/use_tray', False) and \
                        self.controller.tray_icon is None:
                        self.controller.tray_icon = tray.TrayIcon(self)
                    window.hide()
                else:
                    if not settings.get_option('gui/use_tray', False) and \
                        self.controller.tray_icon is not None:
                        self.controller.tray_icon.destroy()
                        self.controller.tray_icon = None

        return False

    def get_selected_page(self):
        return get_selected_page()

def get_playlist_notebook():
    return MainWindow._mainwindow.playlist_notebook

def get_selected_page():
    return MainWindow._mainwindow.playlist_notebook.get_current_tab()

def mainwindow():
    return MainWindow._mainwindow

# vim: et sts=4 sw=4
