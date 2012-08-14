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

from xl.nls import gettext as _
from xl import (
    common,
    covers,
    event,
    formatter,
    player,
    playlist,
    providers,
    settings,
    trax,
    xdg
)
from xlgui.accelerators import AcceleratorManager
from xlgui.playlist import PlaylistNotebook
from xlgui.widgets import (
    dialogs,
    info,
    menu,
    playback
)
from xlgui.widgets.playlist import (
    PlaylistPage,
    PlaylistView
)
from xlgui import (
    cover,
    guiutil,
    tray,
    menu as mainmenu
)

logger = logging.getLogger(__name__)


class MainWindow(gobject.GObject):
    """
        Main Exaile Window
    """
    __gsignals__ = {'main-visible-toggle': (gobject.SIGNAL_RUN_LAST, bool, ())}
    _mainwindow = None
    def __init__(self, controller, builder, collection):
        """
            Initializes the main window

            @param controller: the main gui controller
        """
        gobject.GObject.__init__(self)

        self.controller = controller
        self.collection =  collection
        self.playlist_manager = controller.exaile.playlists
        self.current_page = -1
        self._fullscreen = False
        self.resuming = False

        self.builder = builder

        self.window = self.builder.get_object('ExaileWindow')
        self.window.set_title('Exaile')
        self.title_formatter = formatter.TrackFormatter(settings.get_option(
            'gui/main_window_title_format', _('$title (by $artist)') +
		' - Exaile'))

        self.accelgroup = gtk.AccelGroup()
        self.window.add_accel_group(self.accelgroup)
        self.accel_manager = AcceleratorManager('mainwindow-accelerators', self.accelgroup)
        self.menubar = self.builder.get_object("mainmenu")

        fileitem = self.builder.get_object("file_menu_item")
        filemenu = menu.ProviderMenu('menubar-file-menu', self)
        fileitem.set_submenu(filemenu)

        edititem = self.builder.get_object("edit_menu_item")
        editmenu = menu.ProviderMenu('menubar-edit-menu', self)
        edititem.set_submenu(editmenu)

        viewitem = self.builder.get_object("view_menu_item")
        viewmenu = menu.ProviderMenu('menubar-view-menu', self)
        viewitem.set_submenu(viewmenu)

        viewitem = self.builder.get_object("tools_menu_item")
        viewmenu = menu.ProviderMenu('menubar-tools-menu', self)
        viewitem.set_submenu(viewmenu)

        helpitem = self.builder.get_object("help_menu_item")
        helpmenu = menu.ProviderMenu('menubar-help-menu', self)
        helpitem.set_submenu(helpmenu)

        self._setup_widgets()
        self._setup_position()
        self._setup_hotkeys()
        logger.info("Connecting main window events...")
        self._connect_events()
        MainWindow._mainwindow = self

        mainmenu._create_menus()

    def _setup_hotkeys(self):
        """
            Sets up accelerators that haven't been set up in UI designer
        """
        hotkeys = (
            ('<Control>S', lambda *e: self.on_save_playlist()),
            ('<Shift><Control>S', lambda *e: self.on_save_playlist_as()),
            ('<Control>F', lambda *e: self.on_panel_filter_focus()),
            ('<Control>G', lambda *e: self.on_search_playlist_focus()), # FIXME
            ('<Control><Alt>l', lambda *e: player.QUEUE.clear()), # FIXME
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
        # TODO: Maybe make this stackable
        self.message = dialogs.MessageBar(
            parent=self.builder.get_object('player_box'),
            buttons=gtk.BUTTONS_CLOSE
        )
        self.message.connect('response', self.on_messagebar_response)

        self.info_area = info.TrackInfoPane(player.PLAYER)
        self.info_area.set_auto_update(True)
        self.info_area.set_padding(3, 3, 3, 3)
        self.info_area.hide_all()
        self.info_area.set_no_show_all(True)
        guiutil.gtk_widget_replace(self.builder.get_object('info_area'), self.info_area)

        self.cover = cover.CoverWidget(self.info_area.cover_image, player.PLAYER)

        self.volume_control = playback.VolumeControl(player.PLAYER)
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
        self.playlist_notebook = PlaylistNotebook('saved_tabs', player.PLAYER)
        self.playlist_notebook.connect_after('switch-page',
            self.on_playlist_notebook_switch_page)
        playlist_area.pack_start(self.playlist_notebook, padding=3)
        page_num = self.playlist_notebook.get_current_page()
        page = self.playlist_notebook.get_nth_page(page_num)
        selection = page.view.get_selection()
        selection.connect('changed', self.on_playlist_view_selection_changed)

        self.splitter = self.builder.get_object('splitter')

        self.progress_bar = playback.SeekProgressBar(player.PLAYER)
        guiutil.gtk_widget_replace(
            self.builder.get_object('playback_progressbar'),
            self.progress_bar
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
        self.stop_button.connect('button-release-event',
            self.on_stop_button_release_event)
        self.stop_button.drag_dest_set(gtk.DEST_DEFAULT_ALL,
            [("exaile-index-list", gtk.TARGET_SAME_APP, 0)], gtk.gdk.ACTION_COPY)
        self.stop_button.connect('drag-motion',
            self.on_stop_button_drag_motion)
        self.stop_button.connect('drag-leave',
            self.on_stop_button_drag_leave)
        self.stop_button.connect('drag-data-received',
            self.on_stop_button_drag_data_received)

        self.statusbar = info.Statusbar(self.builder.get_object('status_bar'))
        event.add_callback(self.on_exaile_loaded, 'exaile_loaded')

    def _connect_events(self):
        """
            Connects the various events to their handlers
        """
        self.builder.connect_signals({
            'on_configure_event':   self.configure_event,
            'on_window_state_event': self.window_state_change_event,
            'on_delete_event':      self.on_delete_event,
            'on_playpause_button_clicked': self.on_playpause_button_clicked,
            'on_next_button_clicked':
                lambda *e: player.QUEUE.next(),
            'on_prev_button_clicked':
                lambda *e: player.QUEUE.prev(),
            'on_about_item_activate': self.on_about_item_activate,
            # Controller
#            'on_scan_collection_item_activate': self.controller.on_rescan_collection,
#            'on_device_manager_item_activate': lambda *e: self.controller.show_devices(),
            'on_panel_notebook_switch_page': self.controller.on_panel_switch,
#            'on_track_properties_activate':self.controller.on_track_properties,
        })

        event.add_callback(self.on_playback_resume, 'playback_player_resume',
            player.PLAYER)
        event.add_callback(self.on_playback_end, 'playback_player_end',
            player.PLAYER)
        event.add_callback(self.on_playback_end, 'playback_error',
            player.PLAYER)
        event.add_callback(self.on_playback_start, 'playback_track_start',
            player.PLAYER)
        event.add_callback(self.on_toggle_pause, 'playback_toggle_pause',
            player.PLAYER)
        event.add_callback(self.on_tags_parsed, 'tags_parsed',
            player.PLAYER)
        event.add_callback(self.on_track_tags_changed, 'track_tags_changed')
        event.add_callback(self.on_buffering, 'playback_buffering',
            player.PLAYER)
        event.add_callback(self.on_playback_error, 'playback_error',
            player.PLAYER)

        event.add_callback(self.on_playlist_tracks_added,
            'playlist_tracks_added')
        event.add_callback(self.on_playlist_tracks_removed,
            'playlist_tracks_removed')

        # Settings
        self._on_option_set('gui_option_set', settings, 'gui/show_info_area')
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

            panel.connect('append-items', lambda panel, items, force_play, sort=sort:
                self.on_append_items(items, force_play, sort=sort))
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
                player.PLAYER.stop()

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
        elif event.button == 3:
            menu = guiutil.Menu()
            menu.append(_("Toggle: Stop after Selected Track"),
                self.on_spat_clicked,
                gtk.STOCK_STOP)
            menu.popup(None, None, None, event.button, event.time)

    def on_stop_button_release_event(self, widget, event):
        """
            Called when the user releases the mouse from the stop button
        """
        rect = widget.get_allocation()
        if 0 <= event.x < rect.width and 0 <= event.y < rect.height:
            player.PLAYER.stop()

    def on_stop_button_drag_motion(self, widget, context, x, y, time):
        """
            Indicates possible SPAT during drag motion of tracks
        """
        target = widget.drag_dest_find_target(context, widget.drag_dest_get_target_list())
        if target == 'exaile-index-list':
            widget.set_image(gtk.image_new_from_stock(
                gtk.STOCK_STOP, gtk.ICON_SIZE_BUTTON))

    def on_stop_button_drag_leave(self, widget, context, time):
        """
            Resets the stop button
        """
        widget.set_image(gtk.image_new_from_stock(
            gtk.STOCK_MEDIA_STOP, gtk.ICON_SIZE_BUTTON))

    def on_stop_button_drag_data_received(self, widget, context, x, y, selection, info, time):
        """
            Allows for triggering the SPAT feature
            by dropping tracks on the stop button
        """
        source_widget = context.get_source_widget()

        if selection.target == 'exaile-index-list' and isinstance(source_widget, PlaylistView):
            position = int(selection.data.split(',')[0])
            
            if position == source_widget.playlist.spat_position:
                position = -1

            source_widget.playlist.spat_position = position
            source_widget.queue_draw()

    def on_spat_clicked(self, *e):
        """
            Called when the user clicks on the SPAT item
        """
        trs = self.get_selected_page().view.get_selected_items()
        if not trs: return
        
        # TODO: this works, but implement this some other way in the future
        if player.QUEUE.current_playlist.spat_position == -1:
            player.QUEUE.current_playlist.spat_position = trs[0][0]
        else:
            player.QUEUE.current_playlist.spat_position = -1

        self.get_selected_page().view.queue_draw()

    def on_append_items(self, tracks, force_play=False, queue=False, sort=False, replace=False):
        """
            Called when a panel (or other component)
            has tracks to append and possibly queue

            :param tracks: The tracks to append
            :param force_play: Force playing the first track if there
                                is no track currently playing. Otherwise
                                check a setting to determine whether the
                                track should be played
            :param queue: Additionally queue tracks
            :param sort: Sort before adding
            :param replace: Clear playlist before adding
        """
        if not tracks:
            return

        page = self.get_selected_page()

        if sort:
            tracks = trax.sort_tracks(
                ('artist', 'date', 'album', 'discnumber', 'tracknumber'),
                tracks)

        if replace:
            page.playlist.clear()

        offset = len(page.playlist)
        page.playlist.extend(tracks)

        # extending the queue automatically starts playback
        if queue:
            if player.QUEUE is not page.playlist:
                player.QUEUE.extend(tracks)

        elif (force_play or settings.get_option( 'playlist/append_menu_starts_playback', False )) and \
                not player.PLAYER.current:
            page.view.play_track_at(offset, tracks[0])

    def on_playback_error(self, type, player, message):
        """
            Called when there has been a playback error
        """
        glib.idle_add(self.message.show_error, _('Playback error encountered!'), message)

    def on_buffering(self, type, player, percent):
        """
            Called when a stream is buffering
        """
        percent = min(percent, 100)
        glib.idle_add(self.statusbar.set_status, _("Buffering: %d%%...") % percent, 1)

    def on_tags_parsed(self, type, player, args):
        """
            Called when tags are parsed from a stream/track
        """
        (tr, args) = args
        if not tr or tr.is_local():
            return
        if player.parse_stream_tags(tr, args):
            self._update_track_information()

    def on_track_tags_changed(self, type, track, tag):
        """
            Called when tags are changed
        """
        if track is player.PLAYER.current:
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
        glib.idle_add(self.statusbar.update_info)
        event.remove_callback(self.on_exaile_loaded, 'exaile_loaded')

    def on_playlist_tracks_added(self, type, playlist, tracks):
        """
            Updates information on track add
        """
        glib.idle_add(self.statusbar.update_info)

    def on_playlist_tracks_removed(self, type, playlist, tracks):
        """
            Updates information on track removal
        """
        glib.idle_add(self.statusbar.update_info)

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

        glib.idle_add(self.playpause_button.set_image, image)
        glib.idle_add(self.playpause_button.set_tooltip_text, tooltip)
        self._update_track_information()

        # refresh the current playlist
        pl = self.get_selected_page()


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

    def on_panel_filter_focus(self, *e):
        """
            Gives focus to the filter field of the current panel
        """
        panel_name = settings.get_option('gui/last_selected_panel', 'collection')
        try:
            self.controller.panels[panel_name].filter.grab_focus()
        except (AttributeError, KeyError):
            pass

    def on_search_playlist_focus(self, *e):
        """
            Gives focus to the playlist search bar
        """
        plpage = get_selected_playlist()
        if plpage:
            plpage.get_search_entry().grab_focus()

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

    def on_clear_playlist(self, *e):
        """
            Clears the current playlist tab
        """
        page = self.get_selected_page()
        if page:
            page.playlist.clear()

    def on_open_item_activate(self, menuitem):
        """
            Shows a dialog to open media
        """
        def on_uris_selected(dialog, uris):
            uris.reverse()

            if len(uris) > 0:
                self.controller.open_uri(uris.pop(), play=True)

            for uri in uris:
                self.controller.open_uri(uri, play=False)

        dialog = dialogs.MediaOpenDialog(self.window)
        dialog.connect('uris-selected', on_uris_selected)
        dialog.show()

    def on_open_url_item_activate(self, menuitem):
        """
            Shows a dialog to open an URI
        """
        def on_uri_selected(dialog, uri):
            self.controller.open_uri(uri, play=False)

        dialog = dialogs.URIOpenDialog(self.window)
        dialog.connect('uri-selected', on_uri_selected)
        dialog.show()

    def on_open_directories_item_activate(self, menuitem):
        """
            Shows a dialog to open directories
        """
        def on_uris_selected(dialog, uris):
            uris.reverse()

            if len(uris) > 0:
                self.controller.open_uri(uris.pop(), play=True)

            for uri in uris:
                self.controller.open_uri(uri, play=False)

        dialog = dialogs.DirectoryOpenDialog(self.window)
        # Selecting empty folders is useless
        dialog.props.create_folders = False
        dialog.connect('uris-selected', on_uris_selected)
        dialog.show()

    def on_export_current_playlist_activate(self, menuitem):
        """
            Shows a dialog to export the current playlist
        """
        page = self.get_selected_page()

        if not page or not isinstance(page, PlaylistPage):
            return

        def on_message(dialog, message_type, message):
            """
                Show messages in the main window message area
            """
            if message_type == gtk.MESSAGE_INFO:
                self.message.show_info(markup=message)
            elif message_type == gtk.MESSAGE_ERROR:
                self.message.show_error(_('Playlist export failed!'), message)

            return True

        dialog = dialogs.PlaylistExportDialog(page.playlist, self.window)
        dialog.connect('message', on_message)
        dialog.show()

    def on_playlist_utilities_bar_visible_toggled(self, checkmenuitem):
        """
            Shows or hides the playlist utilities bar
        """
        settings.set_option('gui/playlist_utilities_bar_visible',
            checkmenuitem.get_active())

    def on_show_playing_track_item_activate(self, menuitem):
        """
            Tries to show the currently playing track
        """
        self.playlist_notebook.show_current_track()

    def on_about_item_activate(self, menuitem):
        """
            Shows the about dialog
        """
        dialog = dialogs.AboutDialog(self.window)
        dialog.show()

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
        glib.idle_add(self.playpause_button.set_image,
            gtk.image_new_from_stock(gtk.STOCK_MEDIA_PAUSE,
            gtk.ICON_SIZE_SMALL_TOOLBAR))
        glib.idle_add(self.playpause_button.set_tooltip_text,
            _('Pause Playback'))

    def on_playback_end(self, type, player, object):
        """
            Called when playback ends
        """
        glib.idle_add(self.window.set_title, 'Exaile')

        glib.idle_add(self.playpause_button.set_image,
            gtk.image_new_from_stock(gtk.STOCK_MEDIA_PLAY,
            gtk.ICON_SIZE_SMALL_TOOLBAR))
        glib.idle_add(self.playpause_button.set_tooltip_text,
            _('Start Playback'))

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
                glib.idle_add(self.controller.tray_icon.destroy)
                self.controller.tray_icon = None
            elif not self.controller.tray_icon and usetray:
                self.controller.tray_icon = tray.TrayIcon(self)
	
        if option == 'gui/show_info_area':
            glib.idle_add(self.info_area.set_no_show_all, False)
            if settings.get_option(option, True):
                glib.idle_add(self.info_area.show_all)
            else:
                glib.idle_add(self.info_area.hide_all)
            glib.idle_add(self.info_area.set_no_show_all, True)

    def _update_track_information(self):
        """
            Sets track information
        """
        track = player.PLAYER.current

        if not track:
            return

        glib.idle_add(self.window.set_title,
            self.title_formatter.format(track))

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

    def on_delete_event(self, *e):
        """
            Called when the user attempts to close the window
        """
        sash_pos = self.splitter.get_position()
        if sash_pos > 10:
            settings.set_option('gui/mainw_sash_pos', sash_pos)

        if settings.get_option('gui/use_tray', False) and \
           settings.get_option('gui/close_to_tray', False):
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
            else:
                self.window.show()
                self.window.deiconify()

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

def get_selected_playlist():
    try:
        page = get_selected_page()
    except AttributeError:
        return None
    if not isinstance(page, PlaylistPage):
        return None
    return page

def mainwindow():
    return MainWindow._mainwindow

# vim: et sts=4 sw=4
