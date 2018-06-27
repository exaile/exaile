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

from gi.repository import Gtk

from xl import xdg
from xl.nls import gettext as _
from xlgui.preferences import widgets
from xlgui import tray

name = _('Appearance')
icon = 'preferences-desktop-theme'
ui = xdg.get_data_path('ui', 'preferences', 'appearance.ui')


class ShowInfoAreaPreference(widgets.CheckPreference):
    default = True
    name = 'gui/show_info_area'


class ShowInfoAreaCoversPreference(widgets.CheckPreference):
    default = True
    name = 'gui/show_info_area_covers'


class SplashPreference(widgets.CheckPreference):
    default = True
    name = 'gui/use_splash'


class ShowTabBarPreference(widgets.CheckPreference):
    default = True
    name = 'gui/show_tabbar'


def _get_system_default_font():
    return Gtk.Widget.get_default_style().font_desc.to_string()


class PlaylistFontPreference(widgets.FontButtonPreference):
    default = _get_system_default_font()
    name = 'gui/playlist_font'


class PlaylistFontResetButtonPreference(widgets.FontResetButtonPreference):
    default = _get_system_default_font()
    name = 'gui/playlist_font_reset_button'
    condition_preference_name = 'gui/playlist_font'


class GtkDarkThemePreference(widgets.CheckPreference):
    default = False
    name = 'gui/gtk_dark_hint'


class UseAlphaTransparencyPreference(widgets.CheckPreference):
    default = False
    name = 'gui/use_alpha'
    restart_required = True


class TransparencyPreference(widgets.ScalePreference, widgets.CheckConditional):
    default = 0.3
    name = 'gui/transparency'
    condition_preference_name = 'gui/use_alpha'

    def __init__(self, preferences, widget):
        widgets.ScalePreference.__init__(self, preferences, widget)
        widgets.CheckConditional.__init__(self)


class TrackCountsPreference(widgets.CheckPreference):
    default = True
    name = 'gui/display_track_counts'

    def apply(self, value=None):
        return_value = widgets.CheckPreference.apply(self, value)

        import xlgui

        xlgui.get_controller().get_panel('collection').load_tree()

        return return_value


class UseTrayPreference(widgets.CheckPreference, widgets.Conditional):
    default = False
    name = 'gui/use_tray'

    def __init__(self, preferences, widget):
        widgets.CheckPreference.__init__(self, preferences, widget)
        widgets.Conditional.__init__(self)
        if not tray.is_supported():
            self.widget.set_tooltip_text(
                _("Tray icons are not supported on your platform")
            )

    def on_check_condition(self):
        return tray.is_supported()


class MinimizeToTrayPreference(widgets.CheckPreference, widgets.CheckConditional):
    default = False
    name = 'gui/minimize_to_tray'
    condition_preference_name = 'gui/use_tray'

    def __init__(self, preferences, widget):
        widgets.CheckPreference.__init__(self, preferences, widget)
        widgets.CheckConditional.__init__(self)


class CloseToTrayPreference(widgets.CheckPreference, widgets.CheckConditional):
    default = False
    name = 'gui/close_to_tray'
    condition_preference_name = 'gui/use_tray'

    def __init__(self, preferences, widget):
        widgets.CheckPreference.__init__(self, preferences, widget)
        widgets.CheckConditional.__init__(self)


class EnsureVisiblePreference(widgets.CheckPreference):
    default = True
    name = 'gui/ensure_visible'


class TabPlacementPreference(widgets.ComboPreference):
    default = 'top'
    name = 'gui/tab_placement'

    def __init__(self, preferences, widget):
        widgets.ComboPreference.__init__(self, preferences, widget)


"""
class ProgressBarTextFormatPreference(widgets.ComboEntryPreference):
    name = 'gui/progress_bar_text_format'
    completion_items = {
        '$current_time': _('Current playback position'),
        '$remaining_time': _('Remaining playback time'),
        '$total_time': _('Length of a track')
    }
    preset_items = [
        '$current_time / $remaining_time',
        '$current_time / $total_time'
    ]
    default = '$current_time / $remaining_time'
"""

# vim: et sts=4 sw=4
