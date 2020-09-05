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

from gi.repository import Gio

from os.path import dirname, join

from contextlib import closing

from xl.nls import gettext as _
from xl.metadata.tags import tag_data

from xlgui.widgets import menu
from .analyzer_dialog import AnalyzerDialog


class PlaylistAnalyzerPlugin:
    def __init__(self):
        self.menu_items = []
        self.dialog = None
        self._get_track_groups = None

        self.d3_loc = join(dirname(__file__), 'ext', 'd3.min.js')

    def enable(self, exaile):
        self.exaile = exaile

    def on_gui_loaded(self):

        # register menu items
        item = menu.simple_menu_item(
            'pz-run', [], _('Analyze playlists'), callback=self.on_analyze_playlists
        )
        item.register('menubar-tools-menu')
        self.menu_items.append(item)

        item = menu.simple_menu_item(
            'pz-run',
            ['export-files'],
            _('Analyze playlist'),
            callback=self.on_analyze_playlist,
        )
        item.register('playlist-panel-context-menu')
        self.menu_items.append(item)

        # -> this could have a submenu that gets filled in with all
        #    of the presets

    def on_exaile_loaded(self):
        pass

    def disable(self, exaile):

        if self.dialog is not None:
            self.dialog.destroy()
            self.dialog = None

        for menu_item in self.menu_items:
            menu_item.unregister()

    #
    # Misc
    #

    def get_track_groups(self, track):

        if self._get_track_groups is None:

            if 'grouptagger' not in self.exaile.plugins.enabled_plugins:
                raise ValueError(
                    "GroupTagger plugin must be loaded to use the GroupTagger tag"
                )

            self._get_track_groups = self.exaile.plugins.enabled_plugins[
                'grouptagger'
            ].get_track_groups

        return self._get_track_groups(track)

    #
    # Menu functions
    #

    def on_analyze_playlist(self, widget, name, parent, context):
        """
        :param parent: The PlaylistsPanel that triggered this callback
        """

        if self.dialog is None:
            self.dialog = AnalyzerDialog(
                self, parent.parent, context['selected-playlist']
            )

    def on_analyze_playlists(self, widget, name, parent, context):
        """
        :param parent: The Exaile MainWindow object
        """

        if self.dialog is None:
            self.dialog = AnalyzerDialog(self, parent.window)

    #
    # Functions to generate the analysis
    #

    def get_tag(self, track, tagname, extra):

        data = tag_data.get(tagname)

        if data is not None:
            if data.type == 'int':
                ret = track.get_tag_raw(tagname, join=True)
                if ret is not None:
                    if extra == 0:
                        return int(ret)
                    else:
                        return int(ret) - (int(ret) % extra)
                return

            if data.use_disk:
                return track.get_tag_disk(tagname)

        if tagname == '__grouptagger':
            return list(self.get_track_groups(track))

        return track.get_tag_raw(tagname, join=True)

    def generate_data(self, tracks, tagdata):

        data = []

        for track in tracks:
            if track is None:
                data.append(None)
            else:
                data.append([self.get_tag(track, tag, extra) for tag, extra in tagdata])

        return data

    def write_to_file(self, tmpl, uri, **kwargs):
        """
        Opens a template file, performs substitution, writes it to the
        output URI, and also writes d3.min.js to the output directory.

        :param tmpl: Local pathname to template file
        :param uri: URI of output file suitable for passing to Gio.File
        :param kwargs: Named parameters to substitute in template
        """

        # read the template file
        # NOTE: must be opened in non-binary mode because we treat the
        # contents as string
        with open(tmpl, 'r') as fp:
            contents = fp.read()

        try:
            contents = contents % kwargs
        except Exception:
            raise RuntimeError(
                "Format string error in template (probably has unescaped % in it)"
            )

        outfile = Gio.File.new_for_uri(uri)
        parent_dir = outfile.get_parent()
        if parent_dir:
            parent_dir = parent_dir.get_child("d3.min.js")

        with closing(
            outfile.replace(None, False, Gio.FileCreateFlags.NONE, None)
        ) as fp:
            fp.write(
                contents.encode('utf-8')
            )  # Gio.FileOutputStream.write() needs bytes argument

        # copy d3 to the destination
        # -> TODO: add checkbox to indicate whether it should write d3 there or not
        if parent_dir:
            # Open in binary mode, so that we can directly read bytes
            # and write them via Gio.FileOutputStream.write()
            with open(self.d3_loc, 'rb') as d3fp:
                with closing(
                    parent_dir.replace(None, False, Gio.FileCreateFlags.NONE, None)
                ) as pfp:
                    pfp.write(d3fp.read())


# New plugin API; requires exaile 3.4.0 or later
plugin_class = PlaylistAnalyzerPlugin
