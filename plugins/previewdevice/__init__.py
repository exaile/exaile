# Copyright (C) 2012 Dustin Spicuzza
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

from gi.repository import Gdk
from gi.repository import Gtk

import os

from xl import event, providers, player, settings, xdg

from xl.nls import gettext as _

from xlgui import main
from xlgui.widgets import menu, playback

from . import previewprefs

import logging

logger = logging.getLogger(__name__)


class SecondaryOutputPlugin:
    '''Implements logic for plugin'''

    __play_image = Gtk.Image.new_from_icon_name(
        'media-playback-start', Gtk.IconSize.BUTTON
    )
    __pause_image = Gtk.Image.new_from_icon_name(
        'media-playback-pause', Gtk.IconSize.BUTTON
    )

    def get_preferences_pane(self):
        return previewprefs

    def enable(self, exaile):
        self.exaile = exaile

    def on_gui_loaded(self):

        self.hooked = False

        #
        # Initialize the player objects needed
        #

        self.player = player.player.ExailePlayer(
            'preview_device', disable_autoswitch=True
        )
        self.queue = player.queue.PlayQueue(
            self.player,
            location=os.path.join(xdg.get_data_dir(), 'preview_device_queue.state'),
            name='Preview Device Queue',
        )

        #
        # Initialize the GUI stuff
        #

        self._init_gui()

        # preserve state
        if settings.get_option('plugin/previewdevice/shown', True):
            self._init_gui_hooks()

    def disable(self, exaile):
        logger.debug('Disabling Preview Device')
        event.log_event('preview_device_disabling', self, None)
        self._destroy_gui_hooks()
        self._destroy_gui()
        self.player.destroy()

        self.player = None
        self.queue = None

        logger.debug('Preview Device Disabled')

    def _init_gui(self):
        self.pane = Gtk.Paned()

        # stolen from main
        self.info_area = main.MainWindowTrackInfoPane(self.player)
        self.info_area.set_auto_update(True)
        self.info_area.set_border_width(3)
        self.info_area.hide()
        self.info_area.set_no_show_all(True)

        volume_control = playback.VolumeControl(self.player)
        self.info_area.get_action_area().pack_end(volume_control, False, False, 0)

        self.playpause_button = Gtk.Button()
        self.playpause_button.set_relief(Gtk.ReliefStyle.NONE)
        self._on_playback_end(None, None, None)
        self.playpause_button.connect(
            'button-press-event', self._on_playpause_button_clicked
        )

        self.progress_bar = playback.SeekProgressBar(self.player, use_markers=False)
        self.progress_bar.set_valign(Gtk.Align.CENTER)

        play_toolbar = Gtk.Box()
        play_toolbar.pack_start(self.playpause_button, False, False, 0)
        play_toolbar.pack_start(self.progress_bar, True, True, 0)
        play_toolbar.child_set_property(self.progress_bar, 'padding', 3)

        # stick our player controls into this box
        self.pane1_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.pane2_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.pane2_box.pack_start(self.info_area, False, False, 0)
        self.pane2_box.pack_start(play_toolbar, False, False, 0)

        self.pane.pack1(self.pane1_box, resize=True, shrink=True)
        self.pane.pack2(self.pane2_box, resize=True, shrink=True)

        # setup menus

        # add menu item to 'view' to display our playlist
        self.menu = menu.check_menu_item(
            'preview_player',
            '',
            _('Preview Player'),
            lambda *e: self.hooked,
            self._on_view,
        )

        providers.register('menubar-view-menu', self.menu)

        self.preview_menuitem = menu.simple_menu_item(
            '_preview',
            ['enqueue'],
            _('Preview'),
            callback=self._on_preview,
            condition_fn=lambda n, p, c: not c['selection-empty'],
        )

        # TODO: Setup on other context menus
        self.preview_provides = ['track-panel-menu', 'playlist-context-menu']

        for provide in self.preview_provides:
            providers.register(provide, self.preview_menuitem)

        self._on_option_set('gui_option_set', settings, 'gui/show_info_area')
        self._on_option_set('gui_option_set', settings, 'gui/show_info_area_covers')
        event.add_ui_callback(self._on_option_set, 'option_set')

    def _destroy_gui(self):
        event.remove_callback(self._on_option_set, 'option_set')

        for provide in self.preview_provides:
            providers.unregister(provide, self.preview_menuitem)
        providers.unregister('menubar-view-menu', self.menu)

        self.info_area.destroy()
        self.playpause_button.destroy()

        self.pane2_box.destroy()
        self.pane1_box.destroy()
        self.pane.destroy()

    def _setup_events(self, setup):
        setup(self._on_playback_end, 'playback_player_end', self.player)
        setup(self._on_playback_error, 'playback_error', self.player)
        setup(self._on_playback_start, 'playback_track_start', self.player)
        setup(self._on_toggle_pause, 'playback_toggle_pause', self.player)

    def _init_gui_hooks(self):
        """
        Initializes any hooks into the main Exaile GUI

        Note that this is rather ugly, but currently exaile doesn't really
        have a better way to do this, and there isn't a better place to
        stick our gui objects.
        """

        if self.hooked:
            return

        # the info_area will be where we sit, and the info_area
        # will be duplicated for two sides

        # need to move the play_toolbar, and duplicate it
        # also once for each side

        info_area = main.mainwindow().info_area
        play_toolbar = main.mainwindow().builder.get_object('play_toolbar')

        parent = play_toolbar.get_parent()
        parent.remove(play_toolbar)

        parent = info_area.get_parent()
        parent.remove(info_area)

        parent.pack_start(self.pane, False, False, 0)
        parent.reorder_child(self.pane, 0)

        # stick the main player controls into this box
        self.pane1_box.pack_start(info_area, False, False, 0)
        self.pane1_box.pack_start(play_toolbar, False, False, 0)

        # and do it
        self.pane.show_all()

        # add player events
        self._setup_events(event.add_ui_callback)

        self.hooked = True
        settings.set_option('plugin/previewdevice/shown', True)

        logger.debug("Preview device gui hooked")
        event.log_event('preview_device_enabled', self, None)

    def _destroy_gui_hooks(self):
        """
        Removes any hooks from the main Exaile GUI
        """

        if not self.hooked:
            return

        info_area = main.mainwindow().info_area
        play_toolbar = main.mainwindow().builder.get_object('play_toolbar')

        # detach main GUI elements
        parent = play_toolbar.get_parent()
        parent.remove(play_toolbar)

        parent = info_area.get_parent()
        parent.remove(info_area)

        # detach the element we added to hold them
        parent = self.pane.get_parent()
        parent.remove(self.pane)

        # reattach
        parent.pack_start(info_area, False, False, 0)
        parent.reorder_child(info_area, 0)
        parent.pack_start(play_toolbar, False, False, 0)

        # remove player events
        self._setup_events(event.remove_callback)

        self.hooked = False
        settings.set_option('plugin/previewdevice/shown', False)
        logger.debug('Preview device unhooked')

    #
    # Menu events
    #

    def _on_view(self, menu, name, parent, context):
        if self.hooked:
            self._destroy_gui_hooks()
        else:
            self._init_gui_hooks()

    def _on_preview(self, menu, display_name, playlist_view, context):
        self._init_gui_hooks()
        tracks = context['selected-tracks']
        if len(tracks) > 0:
            self.queue.play(tracks[0])

    #
    # Various player events
    #

    def _on_playpause_button_clicked(self, widget, event):
        """
        Called when the play button is clicked
        """

        if event.button == Gdk.BUTTON_PRIMARY:
            if event.type == Gdk.EventType.BUTTON_PRESS and (
                self.player.is_paused() or self.player.is_playing()
            ):
                self.player.toggle_pause()
            elif event.type == Gdk.EventType._2BUTTON_PRESS:
                self.player.stop()

    def _on_option_set(self, name, object, option):
        """
        Handles changes of settings
        """
        if option == 'gui/show_info_area':
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

    def _on_playback_start(self, type, player, object):
        """
        Called when playback starts
        Sets the currently playing track visible in the currently selected
        playlist if the user has chosen this setting
        """
        self.playpause_button.set_image(self.__pause_image)
        self.playpause_button.set_tooltip_text(
            _('Pause Playback (double click to stop)')
        )

    def _on_playback_end(self, type, player, object):
        """
        Called when playback ends
        """
        self.playpause_button.set_image(self.__play_image)
        self.playpause_button.set_tooltip_text(_('Start Playback'))

    def _on_playback_error(self, type, player, message):
        """
        Called when there has been a playback error
        """
        main.mainwindow().message.show_error(_('Playback error encountered!'), message)

    def _on_toggle_pause(self, type, player, object):
        """
        Called when the user clicks the play button after playback has
        already begun
        """
        if player.is_paused():
            image = self.__play_image
            tooltip = _('Continue Playback')
        else:
            image = self.__pause_image
            tooltip = _('Pause Playback')

        self.playpause_button.set_image(image)
        self.playpause_button.set_tooltip_text(tooltip)


plugin_class = SecondaryOutputPlugin
