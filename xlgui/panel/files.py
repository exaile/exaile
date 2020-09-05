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

import locale
import logging
import os

from gi.repository import Gdk, GdkPixbuf, Gio, GLib, GObject, Gtk, Pango

from xl import common, event, metadata, settings, trax
from xl.nls import gettext as _
from xl.trax.util import recursive_tracks_from_file
from xlgui import guiutil, icons, panel, xdg

from xlgui.panel import menus
from xlgui.widgets.common import DragTreeView


logger = logging.getLogger(__name__)


def gfile_enumerate_children(gfile, attributes, follow_symlinks=True):
    """Like Gio.File.enumerate_children but ignores errors"""
    flags = (
        Gio.FileQueryInfoFlags.NONE
        if follow_symlinks
        else Gio.FileQueryInfoFlags.NOFOLLOW_SYMLINKS
    )
    infos = gfile.enumerate_children(attributes, flags, None)
    it = iter(infos)
    while True:
        try:
            yield next(it)
        except StopIteration:
            break
        except GLib.Error:
            logger.warning(
                "Error while iterating on %r", gfile.get_parse_name(), exc_info=True
            )


class FilesPanel(panel.Panel):
    """
    The Files panel
    """

    __gsignals__ = {
        'append-items': (GObject.SignalFlags.RUN_LAST, None, (object, bool)),
        'replace-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'queue-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
    }

    ui_info = ('files.ui', 'FilesPanel')

    def __init__(self, parent, collection, name):
        """
        Initializes the files panel
        """
        panel.Panel.__init__(self, parent, name, _('Files'))
        self.collection = collection

        self.box = self.builder.get_object('FilesPanel')

        self.targets = [Gtk.TargetEntry.new('text/uri-list', 0, 0)]

        self._setup_tree()
        self._setup_widgets()
        self.menu = menus.FilesContextMenu(self)

        self.key_id = None
        self.i = 0

        first_dir = Gio.File.new_for_commandline_arg(
            settings.get_option('gui/files_panel_dir', xdg.homedir)
        )
        self.history = [first_dir]
        self.load_directory(first_dir, False)

    def _setup_tree(self):
        """
        Sets up tree widget for the files panel
        """
        self.model = Gtk.ListStore(Gio.File, GdkPixbuf.Pixbuf, str, str, bool)
        self.tree = tree = FilesDragTreeView(self, receive=False, source=True)
        tree.set_model(self.model)
        tree.connect('row-activated', self.row_activated)
        tree.connect('key-release-event', self.on_key_released)

        selection = tree.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        self.scroll = scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(tree)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        self.box.pack_start(scroll, True, True, 0)

        pb = Gtk.CellRendererPixbuf()
        text = Gtk.CellRendererText()
        self.colname = colname = Gtk.TreeViewColumn(_('Filename'))
        colname.pack_start(pb, False)
        colname.pack_start(text, True)
        if settings.get_option('gui/ellipsize_text_in_panels', False):
            text.set_property('ellipsize-set', True)
            text.set_property('ellipsize', Pango.EllipsizeMode.END)
        else:
            colname.connect('notify::width', self.set_column_width)

            width = settings.get_option('gui/files_filename_col_width', 130)

            colname.set_fixed_width(width)
            colname.set_sizing(Gtk.TreeViewColumnSizing.FIXED)

        colname.set_resizable(True)
        colname.set_attributes(pb, pixbuf=1)
        colname.set_attributes(text, text=2)
        colname.set_expand(True)

        tree.append_column(self.colname)

        text = Gtk.CellRendererText()
        text.set_property('xalign', 1.0)
        # TRANSLATORS: File size column in the file browser
        self.colsize = colsize = Gtk.TreeViewColumn(_('Size'))
        colsize.set_resizable(True)
        colsize.pack_start(text, False)
        colsize.set_attributes(text, text=3)
        colsize.set_expand(False)
        tree.append_column(colsize)

    def _setup_widgets(self):
        """
        Sets up the widgets for the files panel
        """
        self.directory = icons.MANAGER.pixbuf_from_icon_name(
            'folder', Gtk.IconSize.SMALL_TOOLBAR
        )
        self.track = icons.MANAGER.pixbuf_from_icon_name(
            'audio-x-generic', Gtk.IconSize.SMALL_TOOLBAR
        )
        self.back = self.builder.get_object('files_back_button')
        self.back.connect('clicked', self.go_back)
        self.forward = self.builder.get_object('files_forward_button')
        self.forward.connect('clicked', self.go_forward)
        self.up = self.builder.get_object('files_up_button')
        self.up.connect('clicked', self.go_up)
        self.builder.get_object('files_refresh_button').connect('clicked', self.refresh)
        self.builder.get_object('files_home_button').connect('clicked', self.go_home)

        # Set up the location bar
        self.location_bar = self.builder.get_object('files_entry')
        self.location_bar.connect('changed', self.on_location_bar_changed)
        event.add_ui_callback(
            self.fill_libraries_location, 'libraries_modified', self.collection
        )
        self.fill_libraries_location()
        self.location_bar.set_row_separator_func(lambda m, i: m[i][1] is None)
        self.entry = self.location_bar.get_children()[0]
        self.entry.connect('activate', self.entry_activate)

        # Set up the search entry
        self.filter = guiutil.SearchEntry(self.builder.get_object('files_search_entry'))
        self.filter.connect(
            'activate',
            lambda *e: self.load_directory(
                self.current,
                history=False,
                keyword=self.filter.get_text(),
            ),
        )

    def fill_libraries_location(self, *e):
        libraries = []
        for library in self.collection._serial_libraries:
            f = Gio.File.new_for_commandline_arg(library['location'])
            libraries.append((f.get_parse_name(), f.get_uri()))

        mounts = []
        for mount in Gio.VolumeMonitor.get().get_mounts():
            name = mount.get_name()
            uri = mount.get_default_location().get_uri()
            mounts.append((name, uri))
        mounts.sort(key=lambda row: locale.strxfrm(row[0]))

        model = self.location_bar.get_model()
        model.clear()
        for row in libraries:
            model.append(row)
        if libraries and mounts:
            model.append((None, None))
        for row in mounts:
            model.append(row)
        self.location_bar.set_model(model)

    def on_location_bar_changed(self, widget, *args):
        # Find out which one is selected, if any.
        iter = self.location_bar.get_active_iter()
        if not iter:
            return
        model = self.location_bar.get_model()
        uri = model.get_value(iter, 1)
        if uri:
            self.load_directory(Gio.File.new_for_uri(uri))

    def on_key_released(self, widget, event):
        """
        Called when a key is released in the tree
        """
        if event.keyval == Gdk.KEY_Menu:
            Gtk.Menu.popup(self.menu, None, None, None, None, 0, event.time)
            return True

        if (
            event.keyval == Gdk.KEY_Left
            and Gdk.ModifierType.MOD1_MASK & event.get_state()
        ):
            self.go_back(self.tree)
            return True

        if (
            event.keyval == Gdk.KEY_Right
            and Gdk.ModifierType.MOD1_MASK & event.get_state()
        ):
            self.go_forward(self.tree)
            return True

        if (
            event.keyval == Gdk.KEY_Up
            and Gdk.ModifierType.MOD1_MASK & event.get_state()
        ):
            self.go_up(self.tree)
            return True

        if event.keyval == Gdk.KEY_BackSpace:
            self.go_up(self.tree)
            return True

        if event.keyval == Gdk.KEY_F5:
            self.refresh(self.tree)
            return True
        return False

    def row_activated(self, *i):
        """
        Called when someone double clicks a row
        """
        selection = self.tree.get_selection()
        model, paths = selection.get_selected_rows()

        for path in paths:
            if model[path][4]:
                self.load_directory(model[path][0])
            else:
                self.emit('append-items', self.tree.get_selected_tracks(), True)

    def refresh(self, widget):
        """
        Refreshes the current view
        """
        treepath = self.tree.get_cursor()[0]
        cursorf = self.model[treepath][0] if treepath else None
        self.load_directory(self.current, history=False, cursor_file=cursorf)
        self.fill_libraries_location()

    def entry_activate(self, widget, event=None):
        """
        Called when the user presses enter in the entry box
        """
        path = self.entry.get_text()
        if path.startswith('~'):
            path = os.path.expanduser(path)
        f = Gio.file_parse_name(path)
        try:
            ftype = f.query_info(
                'standard::type', Gio.FileQueryInfoFlags.NONE, None
            ).get_file_type()
        except GLib.GError as e:
            logger.exception(e)
            self.entry.set_text(self.current.get_parse_name())
            return
        if ftype != Gio.FileType.DIRECTORY:
            f = f.get_parent()
        self.load_directory(f)

    def focus(self):
        self.tree.grab_focus()

    def go_forward(self, widget):
        """
        Goes to the next entry in history
        """
        assert 0 <= self.i < len(self.history)
        if self.i == len(self.history) - 1:
            return
        self.i += 1
        self.load_directory(
            self.history[self.i], history=False, cursor_file=self.current
        )
        if self.i >= len(self.history) - 1:
            self.forward.set_sensitive(False)
        if self.history:
            self.back.set_sensitive(True)

    def go_back(self, widget):
        """
        Goes to the previous entry in history
        """
        assert 0 <= self.i < len(self.history)
        if self.i == 0:
            return
        self.i -= 1
        self.load_directory(
            self.history[self.i], history=False, cursor_file=self.current
        )
        if self.i == 0:
            self.back.set_sensitive(False)
        if self.history:
            self.forward.set_sensitive(True)

    def go_up(self, widget):
        """
        Moves up one directory
        """
        parent = self.current.get_parent()
        if parent:
            self.load_directory(parent, cursor_file=self.current)

    def go_home(self, widget):
        """
        Goes to the user's home directory
        """
        home = Gio.File.new_for_commandline_arg(xdg.homedir)
        if home.get_uri() == self.current.get_uri():
            self.refresh(widget)
        else:
            self.load_directory(home, cursor_file=self.current)

    def set_column_width(self, col, stuff=None):
        """
        Called when the user resizes a column
        """
        name = {self.colname: 'filename', self.colsize: 'size'}[col]
        name = "gui/files_%s_col_width" % name

        # this option gets triggered all the time, which is annoying when debugging,
        # so only set it when it actually changes
        w = col.get_width()
        if settings.get_option(name, w) != w:
            settings.set_option(name, w, save=False)

    @common.threaded
    def load_directory(self, directory, history=True, keyword=None, cursor_file=None):
        """
        Load a directory into the files view.

        :param history: whether to record in history
        :param keyword: filter string
        :param cursor_file: file to (attempt to) put the cursor on.
            Will put the cursor on a subdirectory if the file is under it.
        """
        self.current = directory
        try:
            infos = gfile_enumerate_children(
                directory,
                'standard::display-name,standard::is-hidden,standard::name,standard::type',
            )
        except GLib.Error as e:
            logger.exception(e)
            if directory.get_path() != xdg.homedir:  # Avoid infinite recursion.
                self.load_directory(
                    Gio.File.new_for_commandline_arg(xdg.homedir),
                    history,
                    keyword,
                    cursor_file,
                )
            return
        if self.current != directory:  # Modified from another thread.
            return

        settings.set_option('gui/files_panel_dir', directory.get_uri())

        subdirs = []
        subfiles = []
        for info in infos:
            if info.get_is_hidden():
                # Ignore hidden files. They can still be accessed manually from
                # the location bar.
                continue
            name = info.get_display_name()
            low_name = name.lower()
            if keyword and keyword.lower() not in low_name:
                continue
            f = directory.get_child(info.get_name())

            ftype = info.get_file_type()
            sortname = locale.strxfrm(name)
            if ftype == Gio.FileType.DIRECTORY:
                subdirs.append((sortname, name, f))
            elif any(low_name.endswith('.' + ext) for ext in metadata.formats):
                subfiles.append((sortname, name, f))

        subdirs.sort()
        subfiles.sort()

        def idle():
            if self.current != directory:  # Modified from another thread.
                return

            model = self.model
            view = self.tree

            if cursor_file:
                cursor_uri = cursor_file.get_uri()
            cursor_row = -1

            model.clear()
            row = 0
            for sortname, name, f in subdirs:
                model.append((f, self.directory, name, '', True))
                uri = f.get_uri()
                if (
                    cursor_file
                    and cursor_row == -1
                    and (cursor_uri == uri or cursor_uri.startswith(uri + '/'))
                ):
                    cursor_row = row
                row += 1
            for sortname, name, f in subfiles:
                size = (
                    f.query_info(
                        'standard::size', Gio.FileQueryInfoFlags.NONE, None
                    ).get_size()
                    // 1000
                )

                # TRANSLATORS: File size (1 kB = 1000 bytes)
                size = _('%s kB') % locale.format_string('%d', size, True)

                model.append((f, self.track, name, size, False))
                if cursor_file and cursor_row == -1 and cursor_uri == f.get_uri():
                    cursor_row = row
                row += 1

            if cursor_file and cursor_row != -1:
                view.set_cursor((cursor_row,))
            else:
                view.set_cursor((0,))
                if view.get_realized():
                    view.scroll_to_point(0, 0)

            self.entry.set_text(directory.get_parse_name())
            if history:
                self.back.set_sensitive(True)
                self.history[self.i + 1 :] = [self.current]
                self.i = len(self.history) - 1
                self.forward.set_sensitive(False)
            self.up.set_sensitive(bool(directory.get_parent()))

        GLib.idle_add(idle)

    def drag_get_data(self, treeview, context, selection, target_id, etime):
        """
        Called when a drag source wants data for this drag operation
        """
        tracks = self.tree.get_selected_tracks()
        if not tracks:
            return
        for track in tracks:
            DragTreeView.dragged_data[track.get_loc_for_io()] = track
        uris = trax.util.get_uris_from_tracks(tracks)
        selection.set_uris(uris)


class FilesDragTreeView(DragTreeView):
    """
    Custom DragTreeView to retrieve data from files
    """

    def get_selection_empty(self):
        '''Returns True if there are no selected items'''
        return self.get_selection().count_selected_rows() == 0

    def get_selection_is_computed(self):
        """
        Returns True if anything in the selection is a directory
        """
        selection = self.get_selection()
        model, paths = selection.get_selected_rows()

        for path in paths:
            if model[path][4]:
                return True

        return False

    def get_selected_tracks(self):
        """
        Returns the currently selected tracks
        """
        selection = self.get_selection()
        model, paths = selection.get_selected_rows()
        tracks = []

        for path in paths:
            f = model[path][0]
            self.append_recursive(tracks, f)

        return trax.sort_tracks(common.BASE_SORT_TAGS, tracks, artist_compilations=True)

    def append_recursive(self, songs, f):
        """
        Appends recursively
        """
        ftype = f.query_info(
            'standard::type', Gio.FileQueryInfoFlags.NONE, None
        ).get_file_type()
        if ftype == Gio.FileType.DIRECTORY:
            file_infos = gfile_enumerate_children(f, 'standard::name')
            files = (f.get_child(fi.get_name()) for fi in file_infos)
            for subf in files:
                self.append_recursive(songs, subf)
        else:
            tr = self.get_track(f)
            if tr:
                songs.append(tr)

    def get_track(self, f):
        """
        Returns a single track from a Gio.File
        """
        uri = f.get_uri()
        if not trax.is_valid_track(uri):
            return None
        tr = trax.Track(uri)
        return tr

    def get_tracks_for_path(self, path):
        """
        Get tracks for a path from model (expand item)
        :param path: Gtk.TreePath
        :return: list of tracks [xl.trax.Track]
        """
        return recursive_tracks_from_file(self.get_model()[path][0])
