# Copyright (C) 2008-2009 Adam Olsen
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

import gio, gtk, gobject, os, locale, re
import xl.track, urllib
from xl import common, trackdb, metadata
from xl import settings
from xl import event
from xlgui import panel, guiutil, xdg, menu, playlist
from xl.nls import gettext as _
locale.setlocale(locale.LC_ALL, '')

class FilesPanel(panel.Panel):
    """
        The Files panel
    """
    __gsignals__ = {
        'append-items': (gobject.SIGNAL_RUN_LAST, None, (object,)),
        'queue-items': (gobject.SIGNAL_RUN_LAST, None, (object,)),
    }

    ui_info = ('files_panel.glade', 'FilesPanelWindow')

    def __init__(self, parent, collection):
        """
            Initializes the files panel
        """
        panel.Panel.__init__(self, parent)
        self.collection = collection

        self.box = self.builder.get_object('files_box')

        self.targets = [('text/uri-list', 0, 0)]

        self._setup_tree()
        self._setup_widgets()
        self.menu = menu.FilesPanelMenu()
        self.menu.connect('append-items', lambda *e:
            self.emit('append-items', self.get_selected_tracks()))
        self.menu.connect('queue-items', lambda *e:
            self.emit('queue-items', self.get_selected_tracks()))
        self.menu.connect('rating-set', self.set_rating)

        self.key_id = None
        self.i = 0

        first_dir = gio.File(settings.get_option('gui/files_panel_dir',
            xdg.homedir))
        self.history = [first_dir]
        self.load_directory(first_dir, False)

    def set_rating(self, widget, rating):
        tracks = self.get_selected_tracks()
        steps = settings.get_option('miscellaneous/rating_steps', 5)
        for track in tracks:
            track['__rating'] = 100.0 * rating / steps

    def _setup_tree(self):
        """
            Sets up tree widget for the files panel
        """
        self.model = gtk.ListStore(gio.File, gtk.gdk.Pixbuf, str, str)
        self.tree = tree = guiutil.DragTreeView(self, True, True)
        tree.set_model(self.model)
        tree.connect('row-activated', self.row_activated)
        tree.connect('key-release-event', self.on_key_released)

        selection = tree.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        self.scroll = scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.add(tree)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        self.box.pack_start(scroll, True, True)

        pb = gtk.CellRendererPixbuf()
        text = gtk.CellRendererText()
        # TRANSLATORS: Filename column in the file browser
        self.colname = colname = gtk.TreeViewColumn(_('Filename'))
        colname.pack_start(pb, False)
        colname.pack_start(text, True)
        if settings.get_option('gui/ellipsize_text_in_panels', False):
            import pango
            text.set_property('ellipsize-set', True)
            text.set_property('ellipsize', pango.ELLIPSIZE_END)
        else:
            colname.connect('notify::width', self.set_column_width)

            width = settings.get_option('gui/files_filename_col_width', 130)

            colname.set_fixed_width(width)
            colname.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)

        colname.set_resizable(True)
        colname.set_attributes(pb, pixbuf=1)
        colname.set_attributes(text, text=2)
        colname.set_expand(True)

        tree.append_column(self.colname)

        text = gtk.CellRendererText()
        text.set_property('xalign', 1.0)
        # TRANSLATORS: Filesize column in the file browser
        self.colsize = colsize = gtk.TreeViewColumn(_('Size'))
        colsize.set_resizable(True)
        colsize.pack_start(text, False)
        colsize.set_attributes(text, text=3)
        colsize.set_expand(False)
        tree.append_column(colsize)

#        tree.resize_children()
#        tree.realize()
#        tree.columns_autosize()
#        colsize.set_fixed_width(tree.get


    def _setup_widgets(self):
        """
            Sets up the widgets for the files panel
        """
        self.directory = guiutil.get_icon('gnome-fs-directory')
        self.track = gtk.gdk.pixbuf_new_from_file(
            xdg.get_data_path('images/track.png'))
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
        self.entry = self.builder.get_object('files_entry').child
        self.entry.connect('activate', self.entry_activate)

        # set up the location of libraries combobox
        self.libraries_location = self.builder.get_object('files_entry')
        self.libraries_location_changed_handler_id = \
            self.libraries_location.connect('changed',
            self.on_libraries_location_combobox_changed)
        # Connect to Collection Panel
        event.add_callback(self.fill_libraries_location,
            'libraries_modified', self.collection)

        self.fill_libraries_location()

        # set up the search entry
        self.search = self.builder.get_object('files_search_entry')
        self.search.connect('key-release-event', self.key_release)
        self.search.connect('activate', lambda *e:
            self.load_directory(self.current, history=False,
            keyword=unicode(self.search.get_text(), 'utf-8')))

    def fill_libraries_location(self, *e):
        self.libraries_location.handler_block(
            self.libraries_location_changed_handler_id)
        libraries_location_model = self.libraries_location.get_model()
        libraries_location_model.clear()
        len_libraries = len(self.collection._serial_libraries)

        self.libraries_location.set_sensitive(len_libraries > 0)

        if len_libraries > 0:
            for library in self.collection._serial_libraries:
                print library['location']
                libraries_location_model.append([library['location']])

        self.libraries_location.set_active(-1)
        self.libraries_location.handler_unblock(
            self.libraries_location_changed_handler_id)

    def on_libraries_location_combobox_changed(self, widget, *args):
        # find out which one
        iter = self.libraries_location.get_active_iter()
        if not iter: return
        model = self.libraries_location.get_model()
        location = model.get_value(iter, 0)
        if location != '':
            self.load_directory(gio.File(location))

    def on_key_released(self, widget, event):
        """
            Called when a key is released in the tree
        """
        if event.keyval == gtk.keysyms.Menu:
            gtk.Menu.popup(self.menu, None, None, None, 0, event.time)
            return True

        if event.keyval == gtk.keysyms.Left and gtk.gdk.MOD1_MASK & event.state:
            self.go_back(self.tree)
            return True

        if event.keyval == gtk.keysyms.Right and gtk.gdk.MOD1_MASK & event.state:
            self.go_forward(self.tree)
            return True

        if event.keyval == gtk.keysyms.Up and gtk.gdk.MOD1_MASK & event.state:
            self.go_up(self.tree)
            return True

        if event.keyval == gtk.keysyms.F5:
            (mods,paths) = self.tree.get_selection().get_selected_rows()
            self.refresh(self.tree)
            if paths and paths[0]:
                try:
                    self.tree.set_cursor(paths[0], None, False)
                except:
                    pass
            return True
        return False

    def button_press(self, button, event):
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

            if len(self.get_selected_tracks()) >= 2:
                model, paths = selection.get_selected_rows()
                if path[0] in paths:
                    if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
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
            ftype = f.query_info('standard::type').get_file_type()
            if ftype == gio.FILE_TYPE_DIRECTORY:
                self.load_directory(f)
            else:
                self.emit('append-items', self.get_selected_tracks())

    def key_release(self, *e):
        """
            Called when someone releases a key.
            Sets up a timer to simulate live-search
        """
        if self.key_id:
            gobject.source_remove(self.key_id)
            self.key_id = None

        self.key_id = gobject.timeout_add(700, lambda *e:
            self.load_directory(self.current, history=False,
            keyword=unicode(self.search.get_text(), 'utf-8')))

    def refresh(self, widget):
        """
            Refreshes the current view
        """
        self.load_directory(self.current, False)

    def entry_activate(self, widget, event=None):
        """
            Called when the user presses enter in the entry box
        """
        path = self.entry.get_text()
        if path.startswith('~'):
            path = os.path.expanduser(path)
        f = gio.file_parse_name(path)
        ftype = f.query_info('standard::type').get_file_type()
        if ftype != gio.FILE_TYPE_DIRECTORY:
            self.entry.set_text(self.current.get_parse_name())
            return
        self.load_directory(f)

    def go_forward(self, widget):
        """
            Goes to the next entry in history
        """
        if self.i < len(self.history) - 1:
            self.i += 1
            self.load_directory(self.history[self.i], False)
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
            self.load_directory(self.history[self.i], False)
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
        self.load_directory(gio.File(xdg.homedir))

    def set_column_width(self, col, stuff=None):
        """
            Called when the user resizes a column
        """
        name = {self.colname: 'filename', self.colsize: 'size'}[col]
        name = "gui/files_%s_col_width" % name
        settings.set_option(name, col.get_width())

    @common.threaded
    def load_directory(self, directory, history=True, keyword=None):
        """
            Loads a directory into the files view
        """
        self.current = directory
        try:
            infos = directory.enumerate_children('standard::is-hidden,'
                'standard::name,standard::display-name,standard::type')
        except gio.Error:
            if directory.get_path() != xdg.homedir:
                return self.load_directory(
                    gio.File(xdg.homedir), history, keyword)
        if self.current != directory: # Modified from another thread.
            return

        settings.set_option('gui/files_panel_dir', directory.get_uri())

        subdirs = []
        subfiles = []
        import locale
        for info in infos:
            if info.get_is_hidden():
                # Ignore hidden files. They can still be accessed manually from
                # the location bar.
                continue
            f = directory.get_child(info.get_name())
            basename = f.get_basename()
            low_basename = basename.lower()
            if keyword and keyword.lower() not in low_basename:
                continue
            def sortkey():
                name = info.get_display_name()
                sortname = locale.strxfrm(name)
                return sortname, name, f
            ftype = info.get_file_type()
            if ftype == gio.FILE_TYPE_DIRECTORY:
                subdirs.append(sortkey())
            elif any(low_basename.endswith('.' + ext)
                    for ext in metadata.formats):
                subfiles.append(sortkey())

        subdirs.sort()
        subfiles.sort()

        self.model.clear()

        for sortname, name, f in subdirs:
            self.model.append((f, self.directory, name, ''))

        for sortname, name, f in subfiles:
            size = f.query_info('standard::size').get_size() // 1024
            size = locale.format_string(_("%d KB"), size, True)
            self.model.append((f, self.track, name, size))

        self.tree.set_model(self.model)
        self.entry.set_text(directory.get_parse_name())

        # Change the selection in the library location combobox
        iter_libraries_location = self.libraries_location.get_active_iter()
        if not iter_libraries_location is None:
            model_libraries_location = self.libraries_location.get_model()
            location = gio.File(model_libraries_location.get_value(iter_libraries_location, 0))
            location_name = location.get_parse_name()
            if location_name != '' and location_name != directory.get_parse_name():
                    self.libraries_location.handler_block(self.libraries_location_changed_handler_id)
                    self.libraries_location.set_active(-1)
                    self.libraries_location.handler_unblock(self.libraries_location_changed_handler_id)

        if history:
            self.back.set_sensitive(True)
            self.history = self.history[:self.i + 1]
            self.history.append(self.current)
            self.i = len(self.history) - 1
            self.forward.set_sensitive(False)
        self.up.set_sensitive(bool(directory.get_parent()))

        def idle():
            if self.current != directory: # Modified from another thread.
                return

            self.model.clear()

            for sortname, name, f in subdirs:
                self.model.append((f, self.directory, name, ''))

            for sortname, name, f in subfiles:
                size = f.query_info('standard::size').get_size() // 1024
                size = locale.format_string(_("%d KB"), size, True)
                self.model.append((f, self.track, name, size))

            self.tree.set_model(self.model)
            self.entry.set_text(directory.get_parse_name())
            if history:
                self.back.set_sensitive(True)
                self.history = self.history[:self.i + 1]
                self.history.append(self.current)
                self.i = len(self.history) - 1
                self.forward.set_sensitive(False)
            self.up.set_sensitive(bool(directory.get_parent()))

        gobject.idle_add(idle)

    def get_selected_tracks(self):
        """
            Returns the selected tracks
        """
        selection = self.tree.get_selection()
        model, paths = selection.get_selected_rows()

        tracks = []
        for path in paths:
            f = model[path][0]
            self.append_recursive(tracks, f)

        return tracks or None

    def append_recursive(self, songs, f):
        """
            Appends recursively
        """
        ftype = f.query_info('standard::type').get_file_type()
        if ftype == gio.FILE_TYPE_DIRECTORY:
            file_infos = f.enumerate_children('standard::name')
            files = (f.get_child(fi.get_name()) for fi in file_infos)
            for subf in files:
                self.append_recursive(songs, subf)
        else:
            tr = self.get_track(f)
            if tr:
                songs.append(tr)

    def get_track(self, f):
        """
            Returns a single track from a gio.File
        """
        uri = f.get_uri()
        if not xl.track.is_valid_track(uri):
            return None
        tr = self.collection.get_track_by_loc(uri)
        if tr:
            return tr
        tr = xl.track.Track(uri)
        return tr

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
        tracks = self.get_selected_tracks()
        if not tracks: return
        for track in tracks:
            guiutil.DragTreeView.dragged_data[track.get_loc_for_io()] = track
        urls = guiutil.get_urls_for(tracks)
        selection.set_uris(urls)
