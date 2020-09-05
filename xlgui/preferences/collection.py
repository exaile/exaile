# Copyright (C) 2010 Adam Olsen
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

from xl import xdg
from xl.nls import gettext as _
from xlgui.preferences import widgets

name = _('Collection')
icon = 'folder-music'
ui = xdg.get_data_path('ui', 'preferences', 'collection.ui')


def _get_default_strip_list():
    return []
    # FIXME:  currently, this is broken by the backend not also having access
    # to the default set here, so we will just NOT set one.

    # TRANSLATORS: Grammatical articles that are ignored while sorting the
    # collection panel. For example, in French locales this could be
    # the space-separated list "l' la le les".
    # If this practice is not common in your locale, simply
    # translate this to string with single space.
    default_strip_list = _("the")
    return [v.lower() for v in default_strip_list.split(' ') if v]


class CollectionStripArtistPreference(widgets.ListPreference):
    default = _get_default_strip_list()
    name = 'collection/strip_list'

    def __init__(self, preferences, widget):
        widgets.ListPreference.__init__(self, preferences, widget)
        self.widget.connect('populate-popup', self._populate_popup_cb)

    def _get_value(self):
        """
        Get the value, overrides the base class function
        because we don't need shlex parsing. We actually
        want values like "l'" here.
        """
        values = [v.lower() for v in self.widget.get_text().split(' ') if v]
        return values

    def _populate_popup_cb(self, entry, menu):
        from gi.repository import Gtk

        entry = Gtk.MenuItem.new_with_mnemonic(_('Reset to _Defaults'))
        entry.connect('activate', self._reset_to_defaults_cb)
        entry.show()

        sep = Gtk.SeparatorMenuItem()
        sep.show()

        menu.attach(entry, 0, 1, 0, 1)
        menu.attach(sep, 0, 1, 1, 2)

    def _reset_to_defaults_cb(self, item):
        self.widget.set_text(' '.join(_get_default_strip_list()))


class FileBasedCompilationsPreference(widgets.CheckPreference):
    default = True
    name = 'collection/file_based_compilations'


# vim:ts=4 et sw=4
