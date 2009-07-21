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

import os, gtk
from xlgui.prefs import widgets
from xl import event, settings, xdg
from xl.nls import gettext as _

name = 'Mini Mode'
basedir = os.path.dirname(os.path.realpath(__file__))
glade = os.path.join(basedir, "minimodeprefs_pane.glade")

def get_workarea_size():
    """
        Returns the height and width of the work area
    """
    rootwindow = gtk.gdk.get_default_root_window()
    workarea = gtk.gdk.atom_intern('_NET_WORKAREA')
    width, height = rootwindow.property_get(workarea)[2][2:4]

    return height, width

class AlwaysOnTopPreference(widgets.CheckPrefsItem):
    name = 'plugin/minimode/always_on_top'
    default = True

class ShowInPanelPreference(widgets.CheckPrefsItem):
    name = 'plugin/minimode/show_in_panel'
    default = False

class OnAllDesktopsPreference(widgets.CheckPrefsItem):
    name = 'plugin/minimode/on_all_desktops'
    default = True

class DisplayWindowDecorationsPreference(widgets.CheckPrefsItem):
    name = 'plugin/minimode/display_window_decorations'
    default = True

class HorizontalPositionPreference(widgets.SpinPrefsItem):
    name = 'plugin/minimode/horizontal_position'
    default = 10
    def __init__(self, prefs, widget):
        """
            Sets the maximum value to the highest
            possible horizontal position
        """
        height, width = get_workarea_size()
        widget.set_range(0, width)
        widgets.SpinPrefsItem.__init__(self, prefs, widget)
        event.add_callback(self._on_setting_change, 'option_set')

    def _on_setting_change(self, event, settings_manager, option):
        """
            Handles changed position triggered by
            moving the mini mode window
        """
        if option == self.name:
            value = settings.get_option(option, self.default)
            self.widget.set_value(value)

class VerticalPositionPreference(widgets.SpinPrefsItem):
    name = 'plugin/minimode/vertical_position'
    default = 10
    def __init__(self, prefs, widget):
        """
            Sets the maximum value to the highest
            possible vertical position
        """
        height, width = get_workarea_size()
        widget.set_range(0, height)
        widgets.SpinPrefsItem.__init__(self, prefs, widget)
        event.add_callback(self._on_setting_change2, 'option_set')

    def _on_setting_change2(self, event, settings_manager, option):
        """
            Handles changed position triggered by
            moving the mini mode window
        """
        if option == self.name:
            value = settings.get_option(option, self.default)
            self.widget.set_value(value)

class SelectedControlsPreference(widgets.SelectionListPrefsItem):
    name = 'plugin/minimode/selected_controls'
    available_title = _('Available controls')
    selected_title = _('Selected controls')
    available_items = {
        'previous': _('Previous'),
        'play_pause': _('Play/Pause'),
        'stop': _('Stop'),
        'next': _('Next'),
        'track_selector': _('Track selector'),
        'progress_bar': _('Progress bar')
    }
    fixed_items = {
        'restore': _('Restore')
    }
    default = ['previous', 'play_pause', 'next', 'track_selector', 'progress_bar']

class TrackSelectorTitlePreference(widgets.ComboEntryPrefsItem):
    name = 'plugin/minimode/track_selector_title'
    completion_items = {
        '$tracknumber': _('Track number'),
        '$title': _('Title'),
        '$artist': _('Artist'),
        '$composer': _('Composer'),
        '$album': _('Album'),
        '$length': _('Length'),
        '$discnumber': _('Disc number'),
        '$rating': _('Rating'),
        '$date': _('Date'),
        '$genre': _('Genre'),
        '$bitrate': _('Bitrate'),
        '$location': _('Location'),
        '$filename': _('Filename'),
        '$playcount': _('Play count'),
        '$bpm': _('BPM')
    }
    preset_items = [
        # TRANSLATORS: Mini mode track selector title preset
        _('$tracknumber - $title'),
        # TRANSLATORS: Mini mode track selector title preset
        _('$title by $artist'),
        # TRANSLATORS: Mini mode track selector title preset
        _('$title ($length)')
    ]
    default = _('$tracknumber - $title')
