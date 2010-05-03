# exaile/exfalso - Tagger plugin for Exaile using the Ex Falso app
# Copyright (C) 2010  Johannes Sasongko <sasongko@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import gio, gtk
import quodlibet as ql

# Modify Quod Libet's print_ function to default to not print anything.
qlprint = ql.print_
def print_(string_, frm='utf-8', prefix='', output=None, log=None):
    qlprint(string_, frm, prefix, output, log)
import __builtin__
__builtin__.__dict__['print_'] = print_
ql.print_ = print_

class ExFalsoController:
    def __init__(self, on_changed=None):
        from quodlibet import const, config
        from quodlibet.qltk.exfalsowindow import ExFalsoWindow

        config.init(const.CONFIG)
        self.instance = instance = ql.init(backend='nullbe')
        backend, library, player = instance

        self.on_changed = on_changed
        if on_changed:
            library.connect('changed', self._on_changed)

        self.window = window = ExFalsoWindow(library)

        # Ex Falso doesn't have any shortcut for the directory and file list
        # widgets, so we hack into them using multiple get_children calls.
        # Hierarchy:
        #   Window > HPaned > VBox > FileSelector (VPaned)
        #   - ScrolledWindow > DirectoryTree (TreeView)  # directory list
        #   - ScrolledWindow > AllTreeView (TreeView)  # file list
        filesel = window.child.get_children()[0].get_children()[0]
        children = filesel.get_children()
        self.dirlist = dirlist = children[0].child
        self.filelist = filelist = children[1].child
        assert isinstance(dirlist, gtk.TreeView)
        assert isinstance(filelist, gtk.TreeView)

    def _on_changed(self, library, items):
        # We can't directly use the items passed in because Ex Falso converts
        # all the paths into real paths, removing symlink information; so, we
        # manually read the selected files from the file list.
        filelist = self.filelist
        filesel = filelist.get_selection()
        model, paths = filesel.get_selected_rows()
        fpaths = [model[path][0] for path in paths]
        self.on_changed(fpaths)

    def select(self, paths):
        # We are calling a "private" method here, but there's no other way to
        # make Ex Falso show the confirmation dialog when changing files.
        cancel = self.window._ExFalsoWindow__pre_selection_changed(None, None)
        if cancel: return

        dirlist = self.dirlist
        dirsel = dirlist.get_selection()
        dirsel.unselect_all()
        filelist = self.filelist
        filesel = filelist.get_selection()
        filesel.unselect_all()

        paths = frozenset(paths)
        dirs = frozenset(os.path.split(path)[0] for path in paths)
        map(dirlist.go_to, dirs)
        treepaths = [row.path for row in filelist.get_model() if row[0] in paths]
        map(filesel.select_path, treepaths)

    def main(self):
        ql.main(self.window)

    def cleanup(self):
        ql.quit(self.instance)
        from quodlibet import config, const
        config.write(const.CONFIG)
        config.quit()

import xl.event, xl.trax
from xlgui import guiutil

class ExFalsoTagger:
    def __init__(self, exaile):
        self.exaile = exaile
        self.exfalso = None
    def destroy(self, *a):
        if self.exfalso:
            self.exfalso.cleanup()
            self.exfalso = None
    def run(self, tracks):
        ef = self.exfalso
        if ef is None:
            ef = self.exfalso = ExFalsoController(self.on_changed)
            ef.window.connect('destroy', self.destroy)
        ef.window.present()
        ef.select(track.local_file_name() for track in tracks)
    def on_changed(self, paths):
        get_track = self.exaile.collection.get_track_by_loc
        for path in paths:
            uri = gio.File(path).get_uri()
            track = get_track(uri) or xl.trax.Track(uri)
            track.read_tags()
            xl.event.log_event('track_tags_changed', track, None)

PLUGIN = None

# Hook to replace the Properties dialog opened from Collection panel or playlist
# context menu.
from xlgui.playlist import Playlist
from xlgui.panel.collection import CollectionPanel
xl_playlist_properties = Playlist.properties_dialog
xl_panel_properties = CollectionPanel.properties_dialog
def properties_dialog(self):
    tracks = self.get_selected_tracks()
    if len(tracks) == 0:
        return False
    PLUGIN.run(tracks)
    return True

def enable(exaile):
    if exaile.loading:
        xl.event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

@guiutil.idle_add()
def _enable(event, exaile, nothing):
    global PLUGIN
    PLUGIN = ExFalsoTagger(exaile)
    Playlist.properties_dialog = properties_dialog
    CollectionPanel.properties_dialog = properties_dialog

def disable(exaile):
    global PLUGIN
    PLUGIN.destroy()
    PLUGIN = None
    Playlist.properties_dialog = xl_playlist_properties
    CollectionPanel.properties_dialog = xl_panel_properties

if __name__ == "__main__":
    ef = ExFalsoController()
    ef.main()
    ef.cleanup()

# vi: et sts=4 sw=4 tw=80
