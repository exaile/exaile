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
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os, gtk
from xlgui.preferences import widgets
from xl import event, settings, xdg
from xl.nls import gettext as _

name = _('Mini Mode')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "minimodeprefs_pane.ui")

class AlwaysOnTopPreference(widgets.CheckPreference):
    name = 'plugin/minimode/always_on_top'
    default = True

class ShowInPanelPreference(widgets.CheckPreference):
    name = 'plugin/minimode/show_in_panel'
    default = False

class OnAllDesktopsPreference(widgets.CheckPreference):
    name = 'plugin/minimode/on_all_desktops'
    default = True

class DisplayWindowDecorationsPreference(widgets.CheckPreference):
    name = 'plugin/minimode/display_window_decorations'
    default = True

class WindowDecorationTypePreference(widgets.ComboPreference,
        widgets.CheckConditional):
    name = 'plugin/minimode/window_decoration_type'
    default = 'full'
    condition_preference_name = 'plugin/minimode/display_window_decorations'

    def __init__(self, preferences, widget):
        widgets.ComboPreference.__init__(self, preferences, widget)
        widgets.CheckConditional.__init__(self)

class UseAlphaTransparencyPreference(widgets.CheckPreference):
    default = False
    name = 'plugin/minimode/use_alpha'

class TransparencyPreference(widgets.ScalePreference, widgets.CheckConditional):
    default = 0.3
    name = 'plugin/minimode/transparency'
    condition_preference_name = 'plugin/minimode/use_alpha'

    def __init__(self, preferences, widget):
        widgets.ScalePreference.__init__(self, preferences, widget)
        widgets.CheckConditional.__init__(self)

class SelectedControlsPreference(widgets.SelectionListPreference):
    name = 'plugin/minimode/selected_controls'
    available_title = _('Available Controls')
    selected_title = _('Selected Controls')
    available_items = {
        'previous': _('Previous'),
        'play_pause': _('Play/Pause'),
        'stop': _('Stop'),
        'next': _('Next'),
        'track_selector': _('Track selector'),
        'progress_bar': _('Progress bar'),
        'volume': _('Volume'),
        'playlist_button': _('Playlist button'),
    }
    fixed_items = {
        'restore': _('Restore')
    }
    default = ['previous', 'play_pause', 'next', 'playlist_button', 'progress_bar']

class TrackTitleFormatPreference(widgets.ComboEntryPreference):
    name = 'plugin/minimode/track_title_format'
    completion_items = {
        '$tracknumber': _('Track number'),
        '$title': _('Title'),
        '$artist': _('Artist'),
        '$composer': _('Composer'),
        '$album': _('Album'),
        '$__length': _('Length'),
        '$discnumber': _('Disc number'),
        '$__rating': _('Rating'),
        '$date': _('Date'),
        '$genre': _('Genre'),
        '$bitrate': _('Bitrate'),
        '$__location': _('Location'),
        '$filename': _('Filename'),
        '$__playcount': _('Play count'),
        '$__last_played': _('Last played'),
        '$bpm': _('BPM'),
    }
    preset_items = [
        # TRANSLATORS: Mini mode track selector title preset
        _('$tracknumber - $title'),
        # TRANSLATORS: Mini mode track selector title preset
        _('$title by $artist'),
        # TRANSLATORS: Mini mode track selector title preset
        _('$title ($__length)')
    ]
    default = _('$tracknumber - $title')
