# Copyright (C) 2009 Mathias Brodala
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

import gobject, gtk, os
import minimodeprefs, mmwidgets
from xl import event, plugins, settings, xdg
from xl.nls import gettext as _
from xlgui.guiutil import get_workarea_size

MINIMODE = None

def enable(exaile):
    """
        Enables the mini mode plugin
    """
    if exaile.loading:
        event.add_callback(_enable, 'gui_loaded')
    else:
        _enable(None, exaile, None)

def _enable(event, exaile, nothing):
    """
        Handles the deferred enable call
    """
    global MINIMODE
    MINIMODE = MiniMode(exaile)

def disable(exaile):
    """
        Disables the mini mode plugin
    """
    global MINIMODE
    if MINIMODE:
        MINIMODE.destroy()
        MINIMODE = None
    
def get_prefs_pane():
    return minimodeprefs

class MiniMode(gtk.Window):
    """
        A compact mode for Exaile
    """
    def __init__(self, exaile):
        """
            Sets up the mini mode main window and
            options to access it
        """
        self.exaile = exaile
        self._active = False
        self.defaults = self.exaile.plugins.get_plugin_default_preferences('minimode')
        self.defaults['plugin/minimode/horizontal_position'] = 10
        self.defaults['plugin/minimode/vertical_position'] = 10

        controlpref = minimodeprefs.SelectedControlsPreference
        self.available_controls = controlpref.available_items.keys() or []
        self.fixed_items = controlpref.fixed_items.keys() or []

        gtk.Window.__init__(self)
        self.set_title('Exaile')
        self.set_resizable(False)

        self.setup_controls()
        self.update_position()

        basedir = os.path.dirname(os.path.abspath(__file__))
        self.exaile.gui.icons.add_stock_from_directory('exaile-minimode',
            os.path.join(basedir, 'icons'))

        self.menuitem = mmwidgets.MMMenuItem(self.on_menuitem_activate)
        self.exaile.gui.builder.get_object('view_menu').append(self.menuitem)
        self.menuitem.show()

        key, modifier = gtk.accelerator_parse('<Control><Alt>M')
        self.accel_group = gtk.AccelGroup()
        self.menuitem.add_accelerator('activate', self.accel_group,
            key, modifier, gtk.ACCEL_VISIBLE)
        self.exaile.gui.main.window.add_accel_group(self.accel_group)
        self.add_accel_group(self.accel_group)

        self._configure_id = None
        self._main_visible_toggle_id = None

        self.connect('show', self.on_show)
        self.exaile.gui.main.connect('main-visible-toggle',
            self.on_main_visible_toggle)

        self.exaile.gui.builder.connect_signals({
          'on_playlist_notebook_switch': self.on_playlist_notebook_switch
        })

    def destroy(self):
        """
            Cleans up and hides
            the mini mode window
        """
        if self._configure_id is not None:
            self.disconnect(self._configure_id)
            self._configure_id = None
        if self._main_visible_toggle_id is not None:
            self.disconnect(self._main_visible_toggle_id)
            self._main_visible_toggle_id = None

        self.remove_accel_group(self.accel_group)
        self.exaile.gui.main.window.remove_accel_group(self.accel_group)
        self.exaile.gui.builder.get_object('view_menu').remove(self.menuitem)

        self._active = False
        self._hide()
        gtk.Window.destroy(self)

    def _hide(self):
        """
            Hides the mini mode window, shows the main window
        """
        if self._active:
            self.hide()
        else:
            if self._configure_id is not None:
                self.disconnect(self._configure_id)
                self._configure_id = None
            self.hide_all()

        self.exaile.gui.main.window.show()

    def _show(self):
        """
            Shows the mini mode window, hides the main window
        """
        self.exaile.gui.main.window.hide()

        if not self._active:
            self.update_window()

        self.show_all()
        if self._configure_id is None:
            self._configure_id = self.connect('configure-event',
                self.on_configure)

    def toggle_visible(self):
        """
            Toggles visibility of the mini mode window
        """
        if self.get_property('visible'):
            self._hide()
        else:
            self._show()

    def update_window(self):
        """
            Changes the appearance of the mini mode window
            based on user setting
        """
        for option in self.defaults.keys():
            value = self.get_option(option)

            if option == 'plugin/minimode/always_on_top':
                self.set_keep_above(value)
            elif option == 'plugin/minimode/show_in_panel':
                self.set_property('skip-taskbar-hint', not value)
            elif option == 'plugin/minimode/on_all_desktops':
                if value: self.stick()
                else: self.unstick()
            elif option == 'plugin/minimode/display_window_decorations':
                self.set_decorated(value)
            elif option == 'plugin/minimode/horizontal_position':
                self.update_position()
            elif option == 'plugin/minimode/vertical_position':
                self.update_position()
            elif option == 'plugin/minimode/selected_controls':
                self.update_controls()
            elif option == 'plugin/minimode/track_title_format':
                self.box['track_selector'].update_track_list()
    
    def update_position(self):
        """
            Changes the position of the mini mode window
            based on user setting
        """
        x = self.get_option('plugin/minimode/horizontal_position')
        y = self.get_option('plugin/minimode/vertical_position')
        self.move(int(x), int(y))

    def setup_controls(self):
        """
            Sets up all available controls
        """
        self.box = mmwidgets.MMBox(spacing=3)

        self.box.pack_start(mmwidgets.MMButton('previous',
            'gtk-media-previous', _('Previous Track'), self.on_previous))
        self.box.pack_start(mmwidgets.MMButton('next',
            'gtk-media-next', _('Next Track'), self.on_next))
        self.box.pack_start(mmwidgets.MMPlayPauseButton(
            self.exaile.player, self.on_play_pause))
        self.box.pack_start(mmwidgets.MMButton('stop',
            'gtk-media-stop', _('Stop Playback'), self.on_stop))
        self.box.pack_start(mmwidgets.MMButton('restore',
            'gtk-fullscreen', _('Restore Main Window'), self.on_restore))
        self.box.pack_start(mmwidgets.MMTrackSelector(
            self.exaile.queue,
            self.on_track_change, self.on_format_request))
        self.box.pack_start(mmwidgets.MMProgressBar(
            self.exaile.player, self.on_track_seeked))
        self.box.pack_start(mmwidgets.MMVolumeButton(
            self.exaile.player, self.on_volume_changed))
        self.box.pack_start(mmwidgets.MMPlaylistButton(
            self.exaile.gui.main, self.exaile.queue,
            self.exaile.queue.current_playlist,
            self.on_track_change, self.on_format_request))

        # TODO: track_bar

        self.update_controls()
        self.add(self.box)

    def update_controls(self):
        """
            Shows, hides and reorders controls
            based on user setting
        """
        self.box.hide_all_children()
        selected_controls = self.get_option('plugin/minimode/selected_controls')

        for id in selected_controls:
            try:
                self.box.show_child(id)
            except KeyError:
                pass

        for id in self.fixed_items:
            try:
                self.box.show_child(id)
            except KeyError:
                pass

    def get_option(self, option):
        """
            Wrapper function, automatically inserts default values
        """
        return settings.get_option(option, self.defaults[option])

    def set_option(self, option, value):
        """
            Wrapper function, automatically inserts default values
            and sets value only if it has changed
        """
        oldvalue = self.get_option(option)
        if value != oldvalue:
            settings.set_option(option, value)

    def on_menuitem_activate(self, menuitem):
        """
            Shows mini mode on activation of a menu item
        """
        self.toggle_visible()
        self._active = True

    def on_previous(self, button):
        """
            Jumps to the previous track
        """
        self.exaile.queue.prev()

    def on_next(self, button):
        """
            Jumps to the next track
        """
        self.exaile.queue.next()

    def on_play_pause(self, button):
        """
            Toggles between playback and pause mode
        """
        if self.exaile.player.is_paused() or self.exaile.player.is_playing():
            self.exaile.player.toggle_pause()
        else:
            self.exaile.queue.play()

    def on_stop(self, button):
        """
            Stops playback
        """
        self.exaile.player.stop()

    def on_restore(self, button):
        """
            Hides mini mode on button click
        """
        self.toggle_visible()
        self._active = False

    def on_playlist_notebook_switch(self, notebook, page, page_num):
        """
            Updates the track selector on playlist notebook switching
        """
        notebook_page = self.exaile.gui.main.get_selected_playlist()
        if notebook_page is None:
            return
        playlist = notebook_page.playlist
        self.box['track_selector'].update_track_list(playlist)
        self.box['playlist_button'].set_tracks(playlist.get_tracks())

    def on_track_change(self, sender, track):
        """
            Handles changes in track list controls
        """
        if track is not None:
            index = self.exaile.queue.current_playlist.index(track)
            self.exaile.queue.current_playlist.set_current_pos(index)
            self.exaile.queue.play(track)

    def on_format_request(self, formatter):
        """
            Tells the track formatter about the user preference
        """
        return self.get_option('plugin/minimode/track_title_format')

    def on_track_seeked(self, progress_bar, position):
        """
            Handles seeking in the progress bar
        """
        duration = self.exaile.player.current.get_duration()
        self.exaile.player.seek(duration * float(position))

    def on_volume_changed(self, volume_button, value):
        """
            Handles changes to the volume
        """
        settings.set_option('player/volume', value)

    def on_main_visible_toggle(self, main):
        """
            Handles tray icon toggles
        """
        if self._active:
            if self.get_property('visible'):
                self.hide()
            else:
                self.show()
            return True
        return False

    def on_configure(self, widget, event):
        """
            Handles movement of the window
        """
        x, y = self.get_position()
        self.set_option('plugin/minimode/horizontal_position', x)
        self.set_option('plugin/minimode/vertical_position', y)

    def on_show(self, widget):
        """
            Updates window size on exposure
        """
        self.resize(*self.size_request())
        self.queue_draw()

