# Copyright (C) 2009-2010 Mathias Brodala
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

import os.path

from xl import providers
from xl.nls import gettext as _
from xlgui import icons
from xlgui.preferences import widgets

name = _('Mini Mode')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "minimode_preferences.ui")
icons.MANAGER.add_icon_name_from_directory(
    'exaile-minimode', os.path.join(basedir, 'icons')
)
icon = 'exaile-minimode'


class AlwaysOnTopPreference(widgets.CheckPreference):
    name = 'plugin/minimode/always_on_top'
    default = True


class ShowInPanelPreference(widgets.CheckPreference):
    name = 'plugin/minimode/show_in_panel'
    default = False


class OnAllDesktopsPreference(widgets.CheckPreference):
    name = 'plugin/minimode/on_all_desktops'
    default = True


class ButtonInMainWindowPreference(widgets.CheckPreference):
    name = 'plugin/minimode/button_in_mainwindow'
    default = False


class DisplayWindowDecorationsPreference(widgets.CheckPreference):
    name = 'plugin/minimode/display_window_decorations'
    default = True


class WindowDecorationTypePreference(widgets.ComboPreference, widgets.CheckConditional):
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
    default = [
        'previous',
        'play_pause',
        'next',
        'playlist_button',
        'progress_bar',
        'restore',
    ]

    def __init__(self, preferences, widget):
        self.items = [
            self.Item(p.name, p.title, p.description, p.fixed)
            for p in providers.get('minimode-controls')
        ]
        widgets.SelectionListPreference.__init__(self, preferences, widget)


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
        '$__loc': _('Location'),
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
        _('$title ($__length)'),
    ]
    default = _('$tracknumber - $title')
