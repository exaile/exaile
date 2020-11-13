# Copyright (C) 2014 Dustin Spicuzza
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

from xl.nls import gettext as _, ngettext

from xlgui.guiutil import GtkTemplate
from xlgui.widgets import dialogs

from . import gt_common


@GtkTemplate('gt_mass.ui', relto=__file__)
class GtMassRename(Gtk.Window):

    __gtype_name__ = 'GTMassRename'

    (
        found_label,
        playlists,
        replace,
        replace_entry,
        search_entry,
        tracks_list,
    ) = GtkTemplate.Child.widgets(6)

    def __init__(self, exaile):
        Gtk.Window.__init__(self, transient_for=exaile.gui.main.window)
        self.init_template()

        self.exaile = exaile

        self.tracks_list.get_model().set_sort_column_id(1, Gtk.SortType.ASCENDING)

        # initialize playlist list
        model = self.playlists.get_model()

        for pl in exaile.smart_playlists.list_playlists():
            model.append((True, pl))

        for pl in exaile.playlists.list_playlists():
            model.append((False, pl))

        self.show_all()

    def reset(self):
        self.tracks_list.get_model().clear()
        self.replace.set_sensitive(False)

    @GtkTemplate.Callback
    def on_find_clicked(self, widget):

        self.search_str = self.search_entry.get_text().strip()
        self.tagname = gt_common.get_tagname()

        # freeze update
        model = self.tracks_list.get_model()
        self.tracks_list.freeze_child_notify()
        self.tracks_list.set_model(None)

        model.clear()

        idx = self.playlists.get_active()
        if idx != -1 and self.search_str != '':

            smart, name = self.playlists.get_model()[idx]
            if smart:
                pl = self.exaile.smart_playlists.get_playlist(name)
            else:
                pl = self.exaile.playlists.get_playlist(name)

            if hasattr(pl, 'get_playlist'):
                pl = pl.get_playlist(self.exaile.collection)

            for track in pl:

                groups = gt_common._get_track_groups(track, self.tagname)

                if self.search_str != '' and self.search_str not in groups:
                    continue

                name = ' - '.join(
                    [
                        track.get_tag_display('artist'),
                        track.get_tag_display('album'),
                        track.get_tag_display('title'),
                    ]
                )
                model.append((True, name, track))

        # unfreeze, draw it up
        self.tracks_list.set_model(model)
        self.tracks_list.thaw_child_notify()

        self.found_label.set_text(
            ngettext(
                '{amount} track found', '{amount} tracks found', len(model)
            ).format(amount=len(model))
        )

        self.replace.set_sensitive(len(model) != 0)

    @GtkTemplate.Callback
    def on_replace_clicked(self, widget):

        tracks = [row[2] for row in self.tracks_list.get_model() if row[1]]
        replace_str = self.replace_entry.get_text().strip()

        if replace_str:
            query = ngettext(
                "Replace '{old_tag}' with '{new_tag}' on {amount} track?",
                "Replace '{old_tag}' with '{new_tag}' on {amount} tracks?",
                len(tracks),
            ).format(
                old_tag=self.search_str,
                new_tag=replace_str,
                amount=len(tracks),
            )
        else:
            query = ngettext(
                "Delete '{tag}' from {amount} track?",
                "Delete '{tag}' from {amount} tracks?",
                len(tracks),
            ).format(tag=self.search_str, amount=len(tracks))

        if dialogs.yesno(self, query) != Gtk.ResponseType.YES:
            return

        for track in tracks:

            groups = gt_common._get_track_groups(track, self.tagname)

            if self.search_str != '':
                groups.discard(self.search_str)

            if replace_str != '':
                groups.add(replace_str)

            if not gt_common.set_track_groups(track, groups):
                return

        dialogs.info(self, "Tags successfully renamed!")
        self.reset()


def mass_rename(exaile):
    message = _(
        "You should rescan your collection before using mass tag "
        "rename to ensure that all tags are up to date. Rescan now?"
    )

    if dialogs.yesno(exaile.gui.main.window, message) == Gtk.ResponseType.YES:
        exaile.gui.on_rescan_collection()

    GtMassRename(exaile)
