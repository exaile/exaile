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

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
import collections
import locale
import logging
import os
from gi.repository import Pango
import re
import urllib

from xl import (
    common,
    event,
    metadata,
    providers,
    settings,
    trax
)
from xl.nls import gettext as _
from xlgui import (
    guiutil,
    icons,
    panel,
    xdg
)

from xlgui.panel import menus
from xlgui.widgets.common import DragTreeView


logger = logging.getLogger(__name__)


# TODO: Cursor is wrong if the directory content is modified.
# Maybe use the selected gfiles instead.
HistoryEntry = collections.namedtuple('HistoryEntry', 'gfile cursor')


class FilesPanel(panel.Panel):
    """
        The Files panel
    """
    __gsignals__ = {
        'append-items': (GObject.SignalFlags.RUN_LAST, None, (object, bool)),
        'replace-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'queue-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
    }

    ui_info = ('files.ui', 'FilesPanelWindow')

    def __init__(self, parent, collection, name):
        """
            Initializes the files panel
        """
        panel.Panel.__init__(self, parent, name)
        self.collection = collection

        self.box = self.builder.get_object('files_box')

        self.targets = [Gtk.TargetEntry.new('text/uri-list', 0, 0)]

        self._setup_tree()
        self._setup_widgets()
        self.menu = menus.FilesContextMenu(self)

        self.key_id = None
        self.i = 0

        first_dir = Gio.File.new_for_commandline_arg(settings.get_option('gui/files_panel_dir',
            xdg.homedir))
        self.history = [HistoryEntry(first_dir, None)]
        self.load_directory(first_dir, False)

    def _setup_tree(self):
        """
            Sets up tree widget for the files panel
        """
        self.model = Gtk.ListStore(Gio.File, GdkPixbuf.Pixbuf, str, str)
        self.tree = tree = FilesDragTreeView(self, True, True)
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
        self.directory = self.tree.render_icon(
            Gtk.STOCK_DIRECTORY, Gtk.IconSize.SMALL_TOOLBAR)
        self.track = icons.MANAGER.pixbuf_from_icon_name(
            'audio-x-generic', Gtk.IconSize.SMALL_TOOLBAR)
        self.back = self.builder.get_object('files_back_button')
        self.back.connect('clicked', self.go_back)
        self.forward = self.builder.get_object('files_forward_button')
        self.forward.connect('clicked', self.go_forward)
        self.up = self.builder.get_object('files_up_button')
        self.up.connect('clicked', self.go_up)
        self.builder.get_object('files_refresh_button').connect('clicked',
            self.refresh)
        self.builder.get_object('files_home_button').connect('clicked',
            self.go_home)

        # Set up the location bar
        self.location_bar = self.builder.get_object('files_entry')
        self.location_bar.connect('changed', self.on_location_bar_changed)
        event.add_ui_callback(self.fill_libraries_location,
            'libraries_modified', self.collection)
        self.fill_libraries_location()
        self.entry = self.location_bar.get_children()[0]
        self.entry.connect('activate', self.entry_activate)

        # Set up the search entry
        self.filter = guiutil.SearchEntry(self.builder.get_object('files_search_entry'))
        self.filter.connect('activate', lambda *e:
            self.load_directory(self.current, history=False,
                keyword=unicode(self.filter.get_text(), 'utf-8')))

    def fill_libraries_location(self, *e):
        model = self.location_bar.get_model()
        model.clear()
        libraries = self.collection._serial_libraries

        if len(libraries) > 0:
            for library in libraries:
                model.append([Gio.File.new_for_commandline_arg(library['location']).get_parse_name()])
        self.location_bar.set_model(model)

    def on_location_bar_changed(self, widget, *args):
        # Find out which one is selected, if any.
        iter = self.location_bar.get_active_iter()
        if not iter: return
        model = self.location_bar.get_model()
        location = model.get_value(iter, 0)
        if location != '':
            self.load_directory(Gio.File.new_for_commandline_arg(location))

    def on_key_released(self, widget, event):
        """
            Called when a key is released in the tree
        """
        if event.keyval == Gdk.KEY_Menu:
            Gtk.Menu.popup(self.menu, None, None, None, None, 0, event.time)
            return True

        if event.keyval == Gdk.KEY_Left and Gdk.ModifierType.MOD1_MASK & event.get_state():
            self.go_back(self.tree)
            return True

        if event.keyval == Gdk.KEY_Right and Gdk.ModifierType.MOD1_MASK & event.get_state():
            self.go_forward(self.tree)
            return True

        if event.keyval == Gdk.KEY_Up and Gdk.ModifierType.MOD1_MASK & event.get_state():
            self.go_up(self.tree)
            return True

        if event.keyval == Gdk.KEY_BackSpace:
            self.go_up(self.tree)
            return True

        if event.keyval == Gdk.KEY_F5:
            self.refresh(self.tree)
            return True
        return False

    def button_release(self, button, event):
        """
            Called when the user clicks on the playlist
        """
        if event.button == 3:
            selection = self.tree.get_selection()
            (x, y) = map(int, event.get_coords())
            path = self.tree.get_path_at_pos(x, y)
            self.menu.popup(event)

            if not path:
                return False

            model, paths = selection.get_selected_rows()
            if path[0] in paths:
                if event.get_state() & (Gdk.ModifierType.SHIFT_MASK|Gdk.ModifierType.CONTROL_MASK):
                    return False
                return True
            else:
                return False
        return False

    def row_activated(self, *i):
        """
            Called when someone double clicks a row
        """
        selection = self.tree.get_selection()
        model, paths = selection.get_selected_rows()

        for path in paths:
            f = model[path][0]
            ftype = f.query_info('standard::type', Gio.FileQueryInfoFlags.NONE, None).get_file_type()
            if ftype == Gio.FileType.DIRECTORY:
                self.load_directory(f)
            else:
                self.emit('append-items', self.tree.get_selected_tracks(), True)

    def refresh(self, widget):
        """
            Refreshes the current view
        """
        cursor = self.tree.get_cursor()
        self.load_directory(self.current, False, cursor=cursor)

    def entry_activate(self, widget, event=None):
        """
            Called when the user presses enter in the entry box
        """
        path = self.entry.get_text()
        if path.startswith('~'):
            path = os.path.expanduser(path)
        f = Gio.file_parse_name(path)
        try:
            ftype = f.query_info('standard::type', Gio.FileQueryInfoFlags.NONE, None).get_file_type()
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
        if self.i < len(self.history) - 1:
            self.i += 1
            hentry = self.history[self.i]
            self.load_directory(hentry.gfile, False, cursor=hentry.cursor)
            if self.i >= len(self.history) - 1:
                self.forward.set_sensitive(False)
            if len(self.history):
                self.back.set_sensitive(True)

    def go_back(self, widget):
        """
            Goes to the previous entry in history
        """
        if self.i > 0:
            self.i -= 1
            hentry = self.history[self.i]
            self.load_directory(hentry.gfile, False, cursor=hentry.cursor)
            if self.i == 0:
                self.back.set_sensitive(False)
            if len(self.history):
                self.forward.set_sensitive(True)

    def go_up(self, widget):
        """
            Moves up one directory
        """
        parent = self.current.get_parent()
        if parent:
            self.load_directory(parent)

    def go_home(self, widget):
        """
            Goes to the user's home directory
        """
        self.load_directory(Gio.File.new_for_commandline_arg(xdg.homedir))

    def set_column_width(self, col, stuff=None):
        """
            Called when the user resizes a column
        """
        name = {self.colname: 'filename', self.colsize: 'size'}[col]
        name = "gui/files_%s_col_width" % name
        settings.set_option(name, col.get_width(), save=False)

    @common.threaded
    def load_directory(self, directory, history=True, keyword=None, cursor=None):
        """
            Load a directory into the files view.

            :param history: whether to record in history
            :param keyword: filter string
            :param cursor: path or (path, column) to select after loading.
                    Useful while refreshing a directory.
        """
        self.current = directory
        try:
            infos = directory.enumerate_children('standard::is-hidden,'
                'standard::name,standard::display-name,standard::type',
                Gio.FileQueryInfoFlags.NONE, None)
        except GLib.Error as e:
            logger.exception(e)
            if directory.get_path() != xdg.homedir: # Avoid infinite recursion.
                return self.load_directory(
                    Gio.File.new_for_commandline_arg(xdg.homedir), history, keyword, cursor)
        if self.current != directory: # Modified from another thread.
            return

        settings.set_option('gui/files_panel_dir', directory.get_uri())

        subdirs = []
        subfiles = []
        for info in infos:
            if info.get_is_hidden():
                # Ignore hidden files. They can still be accessed manually from
                # the location bar.
                continue
            name = unicode(info.get_display_name(), 'utf-8')
            low_name = name.lower()
            if keyword and keyword.lower() not in low_name:
                continue
            f = directory.get_child(info.get_name())
            def sortkey():
                # HACK: Python 2 bug: strxfrm doesn't support unicode.
                # https://bugs.python.org/issue2481
                sortname = locale.strxfrm(name.encode('utf-8'))
                return sortname, name, f
            ftype = info.get_file_type()
            if ftype == Gio.FileType.DIRECTORY:
                subdirs.append(sortkey())
            elif any(low_name.endswith('.' + ext)
                    for ext in metadata.formats):
                subfiles.append(sortkey())

        subdirs.sort()
        subfiles.sort()

        def idle():
            if self.current != directory: # Modified from another thread.
                return

            model = self.model
            view = self.tree

            old_cursor = view.get_cursor()

            model.clear()
            for sortname, name, f in subdirs:
                model.append((f, self.directory, name, ''))
            for sortname, name, f in subfiles:
                size = f.query_info('standard::size', Gio.FileQueryInfoFlags.NONE, None).get_size() // 1000
                
                # locale.format_string does not support unicode objects
                # correctly, so we call it with an str and convert the 
                # locale-dependent output to unicode.
                size = locale.format_string('%d', size, True)
                size = _('%s kB') % unicode(size, locale.getpreferredencoding())
                
                model.append((f, self.track, name, size))

            if cursor:
                view.set_cursor(*cursor)
            else:
                view.set_cursor((0,))
                if view.get_realized():
                    view.scroll_to_point(0, 0)

            self.entry.set_text(directory.get_parse_name())
            if history:
                self.back.set_sensitive(True)
                hist = self.history
                del hist[self.i+1:]
                hist[-1] = HistoryEntry(hist[-1].gfile, old_cursor)
                hist.append(HistoryEntry(self.current, None))
                self.i = len(hist) - 1
                self.forward.set_sensitive(False)
            self.up.set_sensitive(bool(directory.get_parent()))

        GLib.idle_add(idle)

    def drag_data_received(self, *e):
        """
            stub
        """
        pass

    def drag_data_delete(self, *e):
        """
            stub
        """
        pass

    def drag_get_data(self, treeview, context, selection, target_id, etime):
        """
            Called when a drag source wants data for this drag operation
        """
        tracks = self.tree.get_selected_tracks()
        if not tracks: return
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

        return tracks

    def append_recursive(self, songs, f):
        """
            Appends recursively
        """
        ftype = f.query_info('standard::type', Gio.FileQueryInfoFlags.NONE, None).get_file_type()
        if ftype == Gio.FileType.DIRECTORY:
            file_infos = f.enumerate_children('standard::name', Gio.FileQueryInfoFlags.NONE, None)
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
