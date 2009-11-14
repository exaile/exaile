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

name = _('Mini Mode')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "minimodeprefs_pane.ui")

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
        'progress_bar': _('Progress bar'),
        'volume': _('Volume'),
        'playlist_button': _('Playlist button'),
    }
    fixed_items = {
        'restore': _('Restore')
    }
    default = ['previous', 'play_pause', 'next', 'track_selector', 'progress_bar']

class TrackTitleFormatPreference(widgets.ComboEntryPrefsItem):
    name = 'plugin/minimode/track_title_format'
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
        '$last_played': _('Last played'),
        '$bpm': _('BPM'),
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
