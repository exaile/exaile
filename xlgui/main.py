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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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

import logging

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from xl.nls import gettext as _
from xl import common, event, formatter, player, providers, settings, trax
from xlgui.accelerators import AcceleratorManager
from xlgui.accelerators import Accelerator
from xlgui.playlist_container import PlaylistContainer
from xlgui.widgets import dialogs, info, menu, playback
from xlgui.widgets.playlist import PlaylistPage, PlaylistView
from xlgui import guiutil, tray, menu as mainmenu

logger = logging.getLogger(__name__)

# Length of playback step when user presses seek key (sec)
SEEK_STEP_DEFAULT = 10

# Length of volume steps when user presses up/down key
VOLUME_STEP_DEFAULT = 0.1


class MainWindow(GObject.GObject):
    """
    Main Exaile Window
    """

    __gproperties__ = {
        'is-fullscreen': (
            bool,
            'Fullscreen',
            'Whether the window is fullscreen.',
            False,  # Default
            GObject.ParamFlags.READWRITE,
        )
    }

    __gsignals__ = {'main-visible-toggle': (GObject.SignalFlags.RUN_LAST, bool, ())}

    _mainwindow = None

    def __init__(self, controller, builder, collection):
        """
        Initializes the main window

        @param controller: the main gui controller
        """
        GObject.GObject.__init__(self)

        self.controller = controller
        self.collection = collection
        self.playlist_manager = controller.exaile.playlists
        self.current_page = -1
        self._fullscreen = False

        self.window_state = 0
        self.minimized = False

        self.builder = builder

        self.window = self.builder.get_object('ExaileWindow')
        self.window.set_title('Exaile')
        self.title_formatter = formatter.TrackFormatter(
            settings.get_option(
                'gui/main_window_title_format', _('$title (by $artist)') + ' - Exaile'
            )
        )

        self.accel_group = Gtk.AccelGroup()
        self.window.add_accel_group(self.accel_group)
        self.accel_manager = AcceleratorManager(
            'mainwindow-accelerators', self.accel_group
        )
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

        toolsitem = self.builder.get_object("tools_menu_item")
        toolsmenu = menu.ProviderMenu('menubar-tools-menu', self)
        toolsitem.set_submenu(toolsmenu)

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

        def factory(integer, description):
            """Generate key bindings for Alt keys"""
            keybinding = '<Alt>%s' % str(integer)
            callback = lambda *_e: self._on_focus_playlist_tab(integer - 1)
            return (keybinding, description, callback)

        hotkeys = (
            (
                '<Primary>S',
                _('Save currently selected playlist'),
                lambda *_e: self.on_save_playlist(),
            ),
            (
                '<Shift><Primary>S',
                _('Save currently selected playlist under a custom name'),
                lambda *_e: self.on_save_playlist_as(),
            ),
            (
                '<Primary>F',
                _('Focus filter in currently focused panel'),
                lambda *_e: self.on_panel_filter_focus(),
            ),
            (
                '<Primary>G',
                _('Focus playlist search'),
                lambda *_e: self.on_search_playlist_focus(),
            ),  # FIXME
            (
                '<Primary><Alt>l',
                _('Clear queue'),
                lambda *_e: player.QUEUE.clear(),
            ),  # FIXME
            (
                '<Primary>P',
                _('Start, pause or resume the playback'),
                self._on_playpause_button,
            ),
            (
                '<Primary>Right',
                _('Seek to the right'),
                lambda *_e: self._on_seek_key(True),
            ),
            (
                '<Primary>Left',
                _('Seek to the left'),
                lambda *_e: self._on_seek_key(False),
            ),
            (
                '<Primary>plus',
                _('Increase the volume'),
                lambda *_e: self._on_volume_key(True),
            ),
            (
                '<Primary>equal',
                _('Increase the volume'),
                lambda *_e: self._on_volume_key(True),
            ),
            (
                '<Primary>minus',
                _('Decrease the volume'),
                lambda *_e: self._on_volume_key(False),
            ),
            ('<Primary>Page_Up', _('Switch to previous tab'), self._on_prev_tab_key),
            ('<Primary>Page_Down', _('Switch to next tab'), self._on_next_tab_key),
            (
                '<Alt>N',
                _('Focus the playlist container'),
                self._on_focus_playlist_container,
            ),
            # These 4 are subject to change.. probably should do this
            # via a different mechanism too...
            (
                '<Alt>I',
                _('Focus the files panel'),
                lambda *_e: self.controller.focus_panel('files'),
            ),
            # ('<Alt>C', _('Focus the collection panel'),  # TODO: Does not work, why?
            # lambda *_e: self.controller.focus_panel('collection')),
            (
                '<Alt>R',
                _('Focus the radio panel'),
                lambda *_e: self.controller.focus_panel('radio'),
            ),
            (
                '<Alt>L',
                _('Focus the playlists panel'),
                lambda *_e: self.controller.focus_panel('playlists'),
            ),
            factory(1, _('Focus the first tab')),
            factory(2, _('Focus the second tab')),
            factory(3, _('Focus the third tab')),
            factory(4, _('Focus the fourth tab')),
            factory(5, _('Focus the fifth tab')),
            factory(6, _('Focus the sixth tab')),
            factory(7, _('Focus the seventh tab')),
            factory(8, _('Focus the eighth tab')),
            factory(9, _('Focus the ninth tab')),
            factory(0, _('Focus the tenth tab')),
        )

        for keys, helptext, function in hotkeys:
            accelerator = Accelerator(keys, helptext, function)
            providers.register('mainwindow-accelerators', accelerator)

    def _setup_widgets(self):
        """
        Sets up the various widgets
        """
        # TODO: Maybe make this stackable
        self.message = dialogs.MessageBar(
            parent=self.builder.get_object('player_box'), buttons=Gtk.ButtonsType.CLOSE
        )

        self.info_area = MainWindowTrackInfoPane(player.PLAYER)
        self.info_area.set_auto_update(True)
        self.info_area.set_border_width(3)
        self.info_area.hide()
        self.info_area.set_no_show_all(True)
        guiutil.gtk_widget_replace(self.builder.get_object('info_area'), self.info_area)

        self.statusbar = MainWindowStatusBarPane(player.PLAYER)
        guiutil.gtk_widget_replace(
            self.builder.get_object('status_bar'), self.statusbar
        )

        self.volume_control = playback.VolumeControl(player.PLAYER)
        self.info_area.get_action_area().pack_end(self.volume_control, False, False, 0)

        if settings.get_option('gui/use_alpha', False):
            screen = self.window.get_screen()
            visual = screen.get_rgba_visual()
            self.window.set_visual(visual)
            self.window.connect('screen-changed', self.on_screen_changed)
            self._update_alpha()

        self._update_dark_hint()

        playlist_area = self.builder.get_object('playlist_area')
        self.playlist_container = PlaylistContainer('saved_tabs', player.PLAYER)
        for notebook in self.playlist_container.notebooks:
            notebook.connect_after(
                'switch-page', self.on_playlist_container_switch_page
            )
            page = notebook.get_current_tab()
            if page is not None:
                selection = page.view.get_selection()
                selection.connect('changed', self.on_playlist_view_selection_changed)

        playlist_area.pack_start(self.playlist_container, True, True, 3)

        self.splitter = self.builder.get_object('splitter')

        # In most (all?) RTL locales, the playback controls should still be LTR.
        # Just in case that's not always the case, we provide a hidden option to
        # force RTL layout instead. This can be removed once we're more certain
        # that the default behavior (always LTR) is correct.
        controls_direction = (
            Gtk.TextDirection.RTL
            if settings.get_option('gui/rtl_playback_controls')
            else Gtk.TextDirection.LTR
        )

        self.play_image = Gtk.Image.new_from_icon_name(
            'media-playback-start', Gtk.IconSize.SMALL_TOOLBAR
        )
        self.play_image.set_direction(controls_direction)
        self.pause_image = Gtk.Image.new_from_icon_name(
            'media-playback-pause', Gtk.IconSize.SMALL_TOOLBAR
        )
        self.pause_image.set_direction(controls_direction)

        self.stop_image = Gtk.Image.new_from_icon_name(
            'media-playback-stop', Gtk.IconSize.BUTTON
        )
        self.stop_image.set_direction(controls_direction)
        self.spat_image = Gtk.Image.new_from_icon_name(
            'process-stop', Gtk.IconSize.BUTTON
        )
        self.spat_image.set_direction(controls_direction)

        play_toolbar = self.builder.get_object('play_toolbar')
        play_toolbar.set_direction(controls_direction)
        for button in ('playpause', 'next', 'prev', 'stop'):
            widget = self.builder.get_object('%s_button' % button)
            setattr(self, '%s_button' % button, widget)
            widget.get_child().set_direction(controls_direction)

        """Set the button icon size here to prevent resizing later"""
        self.playpause_button.set_image(self.play_image)
        self.stop_button.set_image(self.stop_image)

        self.progress_bar = playback.SeekProgressBar(player.PLAYER)
        self.progress_bar.get_child().set_direction(controls_direction)
        # Don't expand vertically; looks awful on Adwaita.
        self.progress_bar.set_valign(Gtk.Align.CENTER)
        guiutil.gtk_widget_replace(
            self.builder.get_object('playback_progressbar_dummy'), self.progress_bar
        )

        self.stop_button.toggle_spat = False
        self.stop_button.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.stop_button.connect(
            'motion-notify-event', self.on_stop_button_motion_notify_event
        )
        self.stop_button.connect(
            'leave-notify-event', self.on_stop_button_leave_notify_event
        )
        self.stop_button.connect('key-press-event', self.on_stop_button_key_press_event)
        self.stop_button.connect(
            'key-release-event', self.on_stop_button_key_release_event
        )
        self.stop_button.connect('focus-out-event', self.on_stop_button_focus_out_event)
        self.stop_button.connect('button-press-event', self.on_stop_button_press_event)
        self.stop_button.connect(
            'button-release-event', self.on_stop_button_release_event
        )
        self.stop_button.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [Gtk.TargetEntry.new("exaile-index-list", Gtk.TargetFlags.SAME_APP, 0)],
            Gdk.DragAction.COPY,
        )
        self.stop_button.connect('drag-motion', self.on_stop_button_drag_motion)
        self.stop_button.connect('drag-leave', self.on_stop_button_drag_leave)
        self.stop_button.connect(
            'drag-data-received', self.on_stop_button_drag_data_received
        )

        event.add_ui_callback(self.on_exaile_loaded, 'exaile_loaded')

    def _connect_events(self):
        """
        Connects the various events to their handlers
        """
        self.builder.connect_signals(
            {
                'on_configure_event': self.configure_event,
                'on_window_state_event': self.window_state_change_event,
                'on_delete_event': self.on_delete_event,
                'on_playpause_button_clicked': self._on_playpause_button,
                'on_next_button_clicked': lambda *e: player.QUEUE.next(),
                'on_prev_button_clicked': lambda *e: player.QUEUE.prev(),
                'on_about_item_activate': self.on_about_item_activate,
                # Controller
                #            'on_scan_collection_item_activate': self.controller.on_rescan_collection,
                #            'on_device_manager_item_activate': lambda *e: self.controller.show_devices(),
                #            'on_track_properties_activate':self.controller.on_track_properties,
            }
        )

        event.add_ui_callback(
            self.on_playback_end, 'playback_player_end', player.PLAYER
        )
        event.add_ui_callback(self.on_playback_end, 'playback_error', player.PLAYER)
        event.add_ui_callback(
            self.on_playback_start, 'playback_track_start', player.PLAYER
        )
        event.add_ui_callback(
            self.on_toggle_pause, 'playback_toggle_pause', player.PLAYER
        )
        event.add_ui_callback(self.on_track_tags_changed, 'track_tags_changed')
        event.add_ui_callback(self.on_buffering, 'playback_buffering', player.PLAYER)
        event.add_ui_callback(self.on_playback_error, 'playback_error', player.PLAYER)

        event.add_ui_callback(self.on_playlist_tracks_added, 'playlist_tracks_added')
        event.add_ui_callback(
            self.on_playlist_tracks_removed, 'playlist_tracks_removed'
        )

        # Settings
        self._on_option_set('gui_option_set', settings, 'gui/show_info_area')
        self._on_option_set('gui_option_set', settings, 'gui/show_info_area_covers')
        self._on_option_set('gui_option_set', settings, 'gui/show_status_bar')
        event.add_ui_callback(self._on_option_set, 'option_set')

    def _connect_panel_events(self):
        """
        Sets up panel events
        """

        # When there's nothing in the notebook, hide it
        self.controller.panel_notebook.connect(
            'page-added', self.on_panel_notebook_add_page
        )
        self.controller.panel_notebook.connect(
            'page-removed', self.on_panel_notebook_remove_page
        )

        # panels
        panels = self.controller.panel_notebook.panels

        for panel_name in ('playlists', 'radio', 'files', 'collection'):
            panel = panels[panel_name].panel
            do_sort = False

            if panel_name in ('files', 'collection'):
                do_sort = True

            panel.connect(
                'append-items',
                lambda panel, items, force_play: self.on_append_items(
                    items, force_play, sort=do_sort
                ),
            )
            panel.connect(
                'queue-items',
                lambda panel, items: self.on_append_items(
                    items, queue=True, sort=do_sort
                ),
            )
            panel.connect(
                'replace-items',
                lambda panel, items: self.on_append_items(
                    items, replace=True, sort=do_sort
                ),
            )

        ## Collection Panel
        panel = panels['collection'].panel
        panel.connect('collection-tree-loaded', self.on_collection_tree_loaded)

        ## Playlist Panel
        panel = panels['playlists'].panel
        panel.connect(
            'playlist-selected',
            lambda panel, playlist: self.playlist_container.create_tab_from_playlist(
                playlist
            ),
        )

        ## Radio Panel
        panel = panels['radio'].panel
        panel.connect(
            'playlist-selected',
            lambda panel, playlist: self.playlist_container.create_tab_from_playlist(
                playlist
            ),
        )

        ## Files Panel
        # panel = panels['files']

    def _update_alpha(self):
        if not settings.get_option('gui/use_alpha', False):
            return
        opac = 1.0 - float(settings.get_option('gui/transparency', 0.3))
        Gtk.Widget.set_opacity(self.window, opac)

    def _update_dark_hint(self):
        gs = Gtk.Settings.get_default()

        # We should use reset_property, but that's only available in > 3.20...
        if not hasattr(self, '_default_dark_hint'):
            self._default_dark_hint = gs.props.gtk_application_prefer_dark_theme

        if settings.get_option('gui/gtk_dark_hint', False):
            gs.props.gtk_application_prefer_dark_theme = True

        elif gs.props.gtk_application_prefer_dark_theme != self._default_dark_hint:
            # don't set it explicitly otherwise the app will revert to a light
            # theme -- what we actually want is to leave it up to the OS
            gs.props.gtk_application_prefer_dark_theme = self._default_dark_hint

    def do_get_property(self, prop):
        if prop.name == 'is-fullscreen':
            return self._fullscreen
        else:
            return GObject.GObject.do_get_property(self, prop)

    def do_set_property(self, prop, value):
        if prop.name == 'is-fullscreen':
            if value:
                self.window.fullscreen()
            else:
                self.window.unfullscreen()
        else:
            GObject.GObject.do_set_property(self, prop, value)

    def on_screen_changed(self, widget, event):
        """
        Updates the colormap on screen change
        """
        screen = widget.get_screen()
        visual = screen.get_rgba_visual() or screen.get_rgb_visual()
        self.window.set_visual(visual)

    def on_panel_notebook_add_page(self, notebook, page, page_num):
        if self.splitter.get_child1() is None:
            self.splitter.pack1(self.controller.panel_notebook)
            self.controller.panel_notebook.get_parent().child_set_property(
                self.controller.panel_notebook, 'shrink', False
            )

    def on_panel_notebook_remove_page(self, notebook, page, page_num):
        if notebook.get_n_pages() == 0:
            self.splitter.remove(self.controller.panel_notebook)

    def on_stop_button_motion_notify_event(self, widget, event):
        """
        Sets the hover state and shows SPAT icon
        """
        widget.__hovered = True
        if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
            widget.set_image(self.spat_image)
        else:
            widget.set_image(self.stop_image)

    def on_stop_button_leave_notify_event(self, widget, event):
        """
        Unsets the hover state and resets the button icon
        """
        widget.__hovered = False
        if not widget.is_focus() and ~(event.get_state() & Gdk.ModifierType.SHIFT_MASK):
            widget.set_image(self.stop_image)

    def on_stop_button_key_press_event(self, widget, event):
        """
        Shows SPAT icon on Shift key press
        """
        if event.keyval in (Gdk.KEY_Shift_L, Gdk.KEY_Shift_R):
            widget.set_image(
                Gtk.Image.new_from_icon_name('process-stop', Gtk.IconSize.BUTTON)
            )
            widget.toggle_spat = True

        if event.keyval in (Gdk.KEY_space, Gdk.KEY_Return):
            if widget.toggle_spat:
                self.on_spat_clicked()
            else:
                player.PLAYER.stop()

    def on_stop_button_key_release_event(self, widget, event):
        """
        Resets the button icon
        """
        if event.keyval in (Gdk.KEY_Shift_L, Gdk.KEY_Shift_R):
            widget.set_image(self.stop_image)
            widget.toggle_spat = False

    def on_stop_button_focus_out_event(self, widget, event):
        """
        Resets the button icon unless
        the button is still hovered
        """
        if not getattr(widget, '__hovered', False):
            widget.set_image(self.stop_image)

    def on_stop_button_press_event(self, widget, event):
        """
        Called when the user clicks on the stop button
        """
        if event.button == Gdk.BUTTON_PRIMARY:
            if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                self.on_spat_clicked()
        elif event.triggers_context_menu():
            m = menu.Menu(self)
            m.attach_to_widget(widget)
            m.add_simple(
                _("Toggle: Stop after Selected Track"),
                self.on_spat_clicked,
                'process-stop',
            )
            m.popup(event)

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
        target = widget.drag_dest_find_target(context, None).name()
        if target == 'exaile-index-list':
            widget.set_image(self.spat_image)

    def on_stop_button_drag_leave(self, widget, context, time):
        """
        Resets the stop button
        """
        widget.set_image(self.stop_image)

    def on_stop_button_drag_data_received(
        self, widget, context, x, y, selection, info, time
    ):
        """
        Allows for triggering the SPAT feature
        by dropping tracks on the stop button
        """
        source_widget = Gtk.drag_get_source_widget(context)

        if selection.target.name() == 'exaile-index-list' and isinstance(
            source_widget, PlaylistView
        ):
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
        if not trs:
            return

        # TODO: this works, but implement this some other way in the future
        if player.QUEUE.current_playlist.spat_position == -1:
            player.QUEUE.current_playlist.spat_position = trs[0][0]
        else:
            player.QUEUE.current_playlist.spat_position = -1

        self.get_selected_page().view.queue_draw()

    def on_append_items(
        self, tracks, force_play=False, queue=False, sort=False, replace=False
    ):
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
        if len(tracks) == 0:
            return

        page = self.get_selected_page()

        if sort:
            tracks = trax.sort_tracks(common.BASE_SORT_TAGS, tracks)

        if replace:
            page.playlist.clear()

        offset = len(page.playlist)
        page.playlist.extend(tracks)

        # extending the queue automatically starts playback
        if queue:
            if player.QUEUE is not page.playlist:
                player.QUEUE.extend(tracks)

        elif (
            force_play
            or settings.get_option('playlist/append_menu_starts_playback', False)
        ) and not player.PLAYER.current:
            page.view.play_track_at(offset, tracks[0])

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

    def on_track_tags_changed(self, type, track, tags):
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
            image = self.play_image
            tooltip = _('Continue Playback')
        else:
            image = self.pause_image
            tooltip = _('Pause Playback')

        self.playpause_button.set_image(image)
        self.playpause_button.set_tooltip_text(tooltip)
        self._update_track_information()

    def on_playlist_container_switch_page(self, notebook, page, page_num):
        """
        Updates info after notebook page switch
        """
        page = notebook.get_nth_page(page_num)
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
        try:
            self.controller.get_active_panel().filter.grab_focus()
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
        """
        page = self.get_selected_playlist()
        if page:
            page.on_save()

    def on_save_playlist_as(self, *e):
        """
        Called when the user presses Ctrl+S
        Spawns the save as dialog of the current playlist tab
        """
        page = self.get_selected_playlist()
        if page:
            page.on_saveas()

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
            if message_type == Gtk.MessageType.INFO:
                self.message.show_info(markup=message)
            elif message_type == Gtk.MessageType.ERROR:
                self.message.show_error(_('Playlist export failed!'), message)

            return True

        dialog = dialogs.PlaylistExportDialog(page.playlist, self.window)
        dialog.connect('message', on_message)
        dialog.show()

    def on_playlist_utilities_bar_visible_toggled(self, checkmenuitem):
        """
        Shows or hides the playlist utilities bar
        """
        settings.set_option(
            'gui/playlist_utilities_bar_visible', checkmenuitem.get_active()
        )

    def on_show_playing_track_item_activate(self, menuitem):
        """
        Tries to show the currently playing track
        """
        self.playlist_container.show_current_track()

    def on_about_item_activate(self, menuitem):
        """
        Shows the about dialog
        """
        dialog = dialogs.AboutDialog(self.window)
        dialog.show()

    def on_playback_start(self, type, player, object):
        """
        Called when playback starts
        Sets the currently playing track visible in the currently selected
        playlist if the user has chosen this setting
        """
        self._update_track_information()
        self.playpause_button.set_image(self.pause_image)
        self.playpause_button.set_tooltip_text(_('Pause Playback'))

    def on_playback_end(self, type, player, object):
        """
        Called when playback ends
        """
        self.window.set_title('Exaile')

        self.playpause_button.set_image(self.play_image)
        self.playpause_button.set_tooltip_text(_('Start Playback'))

    def _on_option_set(self, name, object, option):
        """
        Handles changes of settings
        """
        if option == 'gui/main_window_title_format':
            self.title_formatter.props.format = settings.get_option(
                option, self.title_formatter.props.format
            )

        elif option == 'gui/use_tray':
            usetray = settings.get_option(option, False)
            if self.controller.tray_icon and not usetray:
                self.controller.tray_icon.destroy()
                self.controller.tray_icon = None
            elif not self.controller.tray_icon and usetray:
                self.controller.tray_icon = tray.TrayIcon(self)

        elif option == 'gui/show_info_area':
            self.info_area.set_no_show_all(False)
            if settings.get_option(option, True):
                self.info_area.show_all()
            else:
                self.info_area.hide()
            self.info_area.set_no_show_all(True)

        elif option == 'gui/show_info_area_covers':
            cover = self.info_area.cover
            cover.set_no_show_all(False)
            if settings.get_option(option, True):
                cover.show_all()
            else:
                cover.hide()
            cover.set_no_show_all(True)

        elif option == 'gui/transparency':
            self._update_alpha()

        elif option == 'gui/gtk_dark_hint':
            self._update_dark_hint()

        elif option == 'gui/show_status_bar':
            if not settings.get_option('gui/show_status_bar', True):
                self.statusbar.hide()
            else:
                self.statusbar.show()

    def _on_volume_key(self, is_up):
        diff = int(
            100 * settings.get_option('gui/volue_key_step_size', VOLUME_STEP_DEFAULT)
        )
        if not is_up:
            diff = -diff

        player.PLAYER.modify_volume(diff)
        return True

    def _on_seek_key(self, is_forward):
        diff = settings.get_option('gui/seek_key_step_size', SEEK_STEP_DEFAULT)
        if not is_forward:
            diff = -diff

        if player.PLAYER.current:
            player.PLAYER.modify_time(diff)
            self.progress_bar.update_progress()

        return True

    def _on_prev_tab_key(self, *e):
        self.playlist_container.get_current_notebook().select_prev_tab()
        return True

    def _on_next_tab_key(self, *e):
        self.playlist_container.get_current_notebook().select_next_tab()
        return True

    def _on_playpause_button(self, *e):
        self.playpause()
        return True

    def _on_focus_playlist_tab(self, tab_nr):
        self.playlist_container.get_current_notebook().focus_tab(tab_nr)
        return True

    def _on_focus_playlist_container(self, *_e):
        self.playlist_container.focus()
        return True

    def _update_track_information(self):
        """
        Sets track information
        """
        track = player.PLAYER.current

        if not track:
            return

        self.window.set_title(self.title_formatter.format(track))

    def playpause(self):
        """
        Pauses the playlist if it is playing, starts playing if it is
        paused. If stopped, try to start playing the next suitable track.
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

        if settings.get_option('gui/use_tray', False) and settings.get_option(
            'gui/close_to_tray', False
        ):
            self.window.hide()
        else:
            self.quit()
        return True

    def quit(self, *e):
        """
        Quits Exaile
        """
        self.window.hide()
        GLib.idle_add(self.controller.exaile.quit)
        return True

    def on_restart_item_activate(self, menuitem):
        """
        Restarts Exaile
        """
        self.window.hide()
        GLib.idle_add(self.controller.exaile.quit, True)

    def toggle_visible(self, bringtofront=False):
        """
        Toggles visibility of the main window
        """
        toggle_handled = self.emit('main-visible-toggle')

        if not toggle_handled:
            if (
                bringtofront
                and self.window.is_active()
                or not bringtofront
                and self.window.get_property('visible')
            ):
                self.window.hide()
            else:
                # the ordering for deiconify/show matters -- if this gets
                # switched, then the minimization detection breaks
                self.window.deiconify()
                self.window.show()

    def configure_event(self, *e):
        """
        Called when the window is resized or moved
        """
        # Don't save window size if it is maximized or fullscreen.
        if settings.get_option('gui/mainw_maximized', False) or self._fullscreen:
            return False

        (width, height) = self.window.get_size()
        if [width, height] != [
            settings.get_option("gui/mainw_" + key, -1) for key in ["width", "height"]
        ]:
            settings.set_option('gui/mainw_height', height, save=False)
            settings.set_option('gui/mainw_width', width, save=False)
        (x, y) = self.window.get_position()
        if [x, y] != [
            settings.get_option("gui/mainw_" + key, -1) for key in ["x", "y"]
        ]:
            settings.set_option('gui/mainw_x', x, save=False)
            settings.set_option('gui/mainw_y', y, save=False)

        return False

    def window_state_change_event(self, window, event):
        """
        Saves the current maximized and fullscreen
        states and minimizes to tray if requested
        """
        if event.changed_mask & Gdk.WindowState.MAXIMIZED:
            settings.set_option(
                'gui/mainw_maximized',
                bool(event.new_window_state & Gdk.WindowState.MAXIMIZED),
            )
        if event.changed_mask & Gdk.WindowState.FULLSCREEN:
            self._fullscreen = bool(event.new_window_state & Gdk.WindowState.FULLSCREEN)
            self.notify('is-fullscreen')

        # detect minimization state changes
        prev_minimized = self.minimized

        if not self.minimized:

            if (
                event.changed_mask & Gdk.WindowState.ICONIFIED
                and not event.changed_mask & Gdk.WindowState.WITHDRAWN
                and event.new_window_state & Gdk.WindowState.ICONIFIED
                and not event.new_window_state & Gdk.WindowState.WITHDRAWN
                and not self.window_state & Gdk.WindowState.ICONIFIED
            ):
                self.minimized = True
        else:
            if (
                event.changed_mask & Gdk.WindowState.WITHDRAWN
                and not event.new_window_state & (Gdk.WindowState.WITHDRAWN)
            ):  # and \
                self.minimized = False

        # track this
        self.window_state = event.new_window_state

        if settings.get_option('gui/minimize_to_tray', False):

            # old code to detect minimization
            # -> it must have worked at some point, perhaps this is a GTK version
            # specific set of behaviors? Current code works now on 2.24.17

            # if wm_state is not None:
            #    if '_NET_WM_STATE_HIDDEN' in wm_state[2]:
            #        show tray
            #        window.hide
            # else
            #    destroy tray

            if self.minimized != prev_minimized and self.minimized is True:
                if (
                    not settings.get_option('gui/use_tray', False)
                    and self.controller.tray_icon is None
                ):
                    self.controller.tray_icon = tray.TrayIcon(self)

                window.hide()
            elif (
                not settings.get_option('gui/use_tray', False)
                and self.controller.tray_icon is not None
            ):
                self.controller.tray_icon.destroy()
                self.controller.tray_icon = None

        return False

    def get_selected_page(self):
        """
        Returns the currently displayed playlist notebook page
        """
        return self.playlist_container.get_current_tab()

    def get_selected_playlist(self):
        try:
            page = self.get_selected_page()
        except AttributeError:
            return None
        if not isinstance(page, PlaylistPage):
            return None
        return page


class MainWindowTrackInfoPane(info.TrackInfoPane, providers.ProviderHandler):
    """
    Extends the regular track info pane by an area for custom widgets

    The mainwindow-info-area-widget provider is used to show widgets
    on the right of the info area. They should be small. The registered
    provider should provide a method 'create_widget' that takes the info
    area instance as a parameter, and that returns a Gtk.Widget to be
    inserted into the widget_area of the info area, and an attribute
    'name' that will be used when removing the provider.
    """

    def __init__(self, player):
        info.TrackInfoPane.__init__(self, player)

        self.__player = player
        self.widget_area = Gtk.Box()

        self.get_child().pack_start(self.widget_area, False, False, 0)

        self.__widget_area_widgets = {}

        # call this last if we're using simple_init=True
        providers.ProviderHandler.__init__(
            self, 'mainwindow-info-area-widget', target=player, simple_init=True
        )

    def get_player(self):
        """
        Retrieves the player object that this info area
        is associated with
        """
        return self._TrackInfoPane__player

    def on_provider_added(self, provider):
        name = provider.name
        widget = provider.create_widget(self)

        old_widget = self.__widget_area_widgets.get(name)
        if old_widget is not None:
            self.widget_area.remove(old_widget)
            old_widget.destroy()

        self.__widget_area_widgets[name] = widget
        self.widget_area.pack_start(widget, False, False, 0)
        widget.show_all()

    def on_provider_removed(self, provider):
        widget = self.__widget_area_widgets.pop(provider.name, None)
        if widget is not None:
            self.widget_area.remove(widget)
            widget.destroy()


class MainWindowStatusBarPane(Gtk.Statusbar, info.Statusbar, providers.ProviderHandler):
    """
    Extends the regular track info pane by an area for custom widgets

    The mainwindow-info-area-widget provider is used to show widgets
    on the right of the info area. They should be small. The registered
    provider should provide a method 'create_widget' that takes the info
    area instance as a parameter, and that returns a Gtk.Widget to be
    inserted into the widget_area of the info area, and an attribute
    'name' that will be used when removing the provider.
    """

    def __init__(self, player):

        Gtk.Statusbar.__init__(self)
        info.Statusbar.__init__(self, self)
        self.__player = player
        self.widget_area = Gtk.Box()

        self.set_halign(Gtk.Align.END)
        self.pack_start(self.widget_area, False, True, 0)
        self.reorder_child(self.widget_area, 0)

        self.__widget_area_widgets = {}

        # call this last if we're using simple_init=True
        providers.ProviderHandler.__init__(
            self, 'mainwindow-statusbar-widget', target=player, simple_init=True
        )

    def get_player(self):
        """
        Retrieves the player object that this info area
        is associated with
        """
        return self._TrackInfoPane__player

    def on_provider_added(self, provider):
        name = provider.name
        widget = provider.create_widget(self)

        old_widget = self.__widget_area_widgets.get(name)
        if old_widget is not None:
            self.widget_area.remove(old_widget)
            old_widget.destroy()

        self.__widget_area_widgets[name] = widget
        self.widget_area.pack_start(widget, False, True, 0)
        self.widget_area.show()

    def on_provider_removed(self, provider):
        widget = self.__widget_area_widgets.pop(provider.name, None)
        if widget is not None:
            self.widget_area.remove(widget)
            widget.destroy()


def get_playlist_container():
    return MainWindow._mainwindow.playlist_container


def get_playlist_notebook():
    '''Retrieves the primary playlist notebook'''
    return MainWindow._mainwindow.playlist_container.notebooks[0]


def get_selected_page():
    return MainWindow._mainwindow.get_selected_page()


def get_selected_playlist():
    return MainWindow._mainwindow.get_selected_playlist()


def mainwindow():
    return MainWindow._mainwindow


# vim: et sts=4 sw=4
