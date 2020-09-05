# Copyright (C) 2010 Mathias Brodala
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

from gi.repository import Gdk

from xl import event, player, providers
from xl.nls import gettext as _
from xlgui.widgets import playback


class ABRepeatPlugin:
    def __init__(self):
        self.__menu_item = None

    def enable(self, _exaile):
        """
        Enables the plugin
        """
        pass  # needs to be implemented, otherwise xl.plugins will break

    def on_gui_loaded(self):
        self.__menu_item = RepeatSegmentMenuItem()
        providers.register('progressbar-context-menu', self.__menu_item)

    def disable(self, _exaile):
        """
        Disables the plugin
        """
        self.__menu_item.destroy()
        providers.unregister('progressbar-context-menu', self.__menu_item)


plugin_class = ABRepeatPlugin


class RepeatSegmentMenuItem(playback.MoveMarkerMenuItem, providers.ProviderHandler):
    """
    Menu item allowing for insertion of two markers
    to signify beginning and end of the segment to repeat
    """

    def __init__(self):
        playback.MoveMarkerMenuItem.__init__(
            self, 'repeat-segment', [], _('Repeat Segment'), 'media-playlist-repeat'
        )
        providers.ProviderHandler.__init__(self, 'playback-markers')

        self.beginning_marker = playback.Marker()
        self.beginning_marker.name = 'repeat-beginning'
        self.beginning_marker.props.anchor = playback.Anchor.NORTH_WEST
        self.beginning_marker.props.label = _('Repeat Beginning')
        self.end_marker = playback.Marker()
        self.end_marker.name = 'repeat-end'
        self.end_marker.props.anchor = playback.Anchor.NORTH_EAST
        self.end_marker.props.label = _('Repeat End')
        self.end_marker.connect('reached', self.on_end_marker_reached)

        event.add_ui_callback(self.on_playback_track_end, 'playback_track_end')

    def destroy(self):
        """
        Cleanups
        """
        event.remove_callback(self.on_playback_track_end, 'playback_track_end')
        self.clear_markers()

    def factory(self, menu, parent, context):
        """
        Generates the menu item
        """
        item = playback.MoveMarkerMenuItem.factory(self, menu, parent, context)

        markers = (
            providers.get_provider('playback-markers', n)
            for n in ('repeat-beginning', 'repeat-end')
        )

        if player.PLAYER.current is None:
            item.set_sensitive(False)
        elif None not in markers:
            # Disable if the markers have already been set
            item.set_sensitive(False)

        return item

    def clear_markers(self):
        """
        Removes both markers
        """
        for name in ('repeat-beginning', 'repeat-end'):
            marker = providers.get_provider('playback-markers', name)

            if marker is not None:
                providers.unregister('playback-markers', marker)

    def on_activate(self, widget, parent, context):
        """
        Inserts the beginning (A) marker
        """
        self.beginning_marker.props.position = context['current-position']
        providers.register('playback-markers', self.beginning_marker)
        context['current-marker'] = self.beginning_marker

        playback.MoveMarkerMenuItem.on_activate(self, widget, parent, context)

    def on_parent_button_press_event(self, widget, event):
        """
        Finishes or cancels insertion of markers
        """
        if event.button == Gdk.BUTTON_PRIMARY:
            if self.move_finish():
                if providers.get_provider('playback-markers', 'repeat-end') is None:
                    position = event.x / widget.get_allocation().width
                    self.end_marker.props.position = position
                    providers.register('playback-markers', self.end_marker)
                    self.move_begin(self.end_marker)

                return True
        elif event.triggers_context_menu():
            if self.move_cancel():
                self.clear_markers()

                return True

        return False

    def on_end_marker_reached(self, marker):
        """
        Seeks to the beginning marker
        """
        player.PLAYER.set_progress(self.beginning_marker.props.position)

    def on_provider_removed(self, provider):
        """
        Removes the opposite marker if one
        of the two markers is removed
        """
        names = ('repeat-beginning', 'repeat-end')

        if provider.name in names:
            self.clear_markers()

    def on_playback_track_end(self, event_type, player, track):
        """
        Removes both markers
        """
        self.clear_markers()
