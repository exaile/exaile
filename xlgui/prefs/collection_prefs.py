# Copyright (C) 2009 Thomas E. Zander
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

from xlgui.prefs import widgets
from xl import xdg
from xl.nls import gettext as _
from xlgui import commondialogs

name = _('Collection')
glade = xdg.get_data_path('glade/collection_prefs_pane.glade')

def _get_default_strip_list():
    from locale import getlocale, getdefaultlocale
    default_list = ["el", "l'", "la", "le", "les", "los", "the"]
    try:
        (loc, enc) = getlocale()
        if loc is None:
            (loc, enc) = getdefaultlocale()
        #TRANSLATORS: Alter default_list to appropriate content
        if loc == 'de_DE':
            default_list.extend(["der", "die", "das"])
    except:
        pass
    return default_list

class CollectionStripArtistPreference(widgets.ListPrefsItem):
    default = _get_default_strip_list()
    name = 'collection/strip_list'

    def __init__(self, prefs, widget):
        widgets.ListPrefsItem.__init__(self, prefs, widget)
        self.widget.connect('populate-popup', self._populate_popup_cb)

    def _get_value(self):
        """
            Get the value, overrides the base class function
            because we don't need shlex parsing. We actually
            want values like "l'" here.
        """
        values = [v.lower() for v in self.widget.get_text().split(' ') if v is not '']
        return values

    def _populate_popup_cb(self, entry, menu):
        import gtk
        entry = gtk.MenuItem(_('Reset to defaults'))
        entry.connect('activate', self._reset_to_defaults_cb)
        entry.show()

        sep = gtk.SeparatorMenuItem()
        sep.show()

        menu.attach(entry, 0, 1, 0, 1)
        menu.attach(sep, 0, 1, 1, 2)

    def _reset_to_defaults_cb(self, item):
        self.widget.set_text(' '.join(_get_default_strip_list()))

# vim:ts=4 et sw=4
