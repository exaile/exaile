# Copyright (C) 2008-2009 Adam Olsen 
#
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

import gtk, gobject, os, locale, re
import xl.track, urllib
from xl import common, trackdb, metadata
from xl import settings
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

    gladeinfo = ('files_panel.glade', 'FilesPanelWindow')

    def __init__(self, parent, collection):
        """
            Initializes the files panel
        """
        panel.Panel.__init__(self, parent)
        self.collection = collection

        self.box = self.xml.get_widget('files_box')

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

        self.first_dir = settings.get_option('gui/files_panel_dir',
            xdg.homedir)
        self.history = [self.first_dir]
        self.load_directory(self.first_dir, False)

    def set_rating(self, widget, rating):
        tracks = self.get_selected_tracks()
        steps = settings.get_option('miscellaneous/rating_steps', 5)
        for track in tracks:
            track['__rating'] = float((100.0*rating)/steps)

    def _setup_tree(self):
        """
            Sets up tree widget for the files panel
        """
        self.model = gtk.ListStore(gtk.gdk.Pixbuf, str, str)
        self.tree = guiutil.DragTreeView(self, True, True)
        self.tree.set_model(self.model)
        self.tree.connect('row-activated', self.row_activated)
        self.tree.connect('key-release-event', self.on_key_released)

        selection = self.tree.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.tree)
        self.scroll.set_shadow_type(gtk.SHADOW_IN)
        self.box.pack_start(self.scroll, True, True)

        pb = gtk.CellRendererPixbuf()
        text = gtk.CellRendererText()
        # TRANSLATORS: Filename column in the file browser
        self.colname = gtk.TreeViewColumn(_('Filename'))
        self.colname.pack_start(pb, False)
        self.colname.pack_start(text, True)
        if settings.get_option('gui/ellipsize_text_in_panels', False):
            import pango
            text.set_property( 'ellipsize-set', True)
            text.set_property( 'ellipsize', pango.ELLIPSIZE_END)
        else:
            self.colname.connect('notify::width', self.set_column_width)

            width = settings.get_option('gui/files_filename_col_width', 130)

            self.colname.set_fixed_width(width)
            self.colname.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)

        self.colname.set_resizable(True)
        self.colname.set_attributes(pb, pixbuf=0)
        self.colname.set_attributes(text, text=1)
        self.colname.set_expand(True)

        self.tree.append_column(self.colname)

        text = gtk.CellRendererText()
        text.set_property('xalign', 1.0)
        # TRANSLATORS: Filesize column in the file browser
        self.colsize = gtk.TreeViewColumn(_('Size'))
        self.colsize.set_resizable(True)
        self.colsize.pack_start(text, False)
        self.colsize.set_attributes(text, text=2)
        self.colsize.set_expand(False)
        self.tree.append_column(self.colsize)

#        self.tree.resize_children()
#        self.tree.realize()
#        self.tree.columns_autosize()
#        self.colsize.set_fixed_width(self.tree.get
        

    def _setup_widgets(self):
        """
            Sets up the widgets for the files panel
        """
        self.directory = guiutil.get_icon('gnome-fs-directory')
        self.track = gtk.gdk.pixbuf_new_from_file(
            xdg.get_data_path('images/track.png'))
        self.back = self.xml.get_widget('files_back_button')
        self.back.connect('clicked', self.go_back)
        self.forward = self.xml.get_widget('files_forward_button')
        self.forward.connect('clicked', self.go_forward)
        self.up = self.xml.get_widget('files_up_button')
        self.up.connect('clicked', self.go_up)
        self.xml.get_widget('files_refresh_button').connect('clicked',
            self.refresh)
        self.xml.get_widget('files_home_button').connect('clicked',
            self.go_home)
        self.entry = self.xml.get_widget('files_entry')
        self.entry.connect('activate', self.entry_activate)

        # set up the search entry
        self.search = self.xml.get_widget('files_search_entry')
        self.search.connect('key-release-event', self.key_release)
        self.search.connect('activate', lambda *e:
            self.load_directory(self.current, history=False,
            keyword=unicode(self.search.get_text(), 'utf-8')))

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
                (mods,paths) = selection.get_selected_rows()
                if (path[0] in paths):
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
        (model, paths) = selection.get_selected_rows()

        for path in paths:
            iter = self.model.get_iter(path)
            value = unicode(model.get_value(iter, 1), 'utf-8')
            dir = os.path.join(self.current, value)
            if os.path.isdir(dir):
                self.load_directory(dir)
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
        dir = os.path.expanduser(unicode(self.entry.get_text(), 'utf-8'))
        if not os.path.isdir(dir):
            self.entry.set_text(self.current)
            return
        self.load_directory(os.path.normpath(dir))

    def go_forward(self, widget):
        """
            Goes to the next entry in history
        """
        try:
            self.i += 1 
            self.load_directory(self.history[self.i], False)
            if self.i >= len(self.history) - 1:
                self.forward.set_sensitive(False)
            if len(self.history):
                self.back.set_sensitive(True)
        except IndexError:
            return
            
    def go_back(self, widget):
        """
            Goes to the previous entry in history
        """
        try:
            self.i -= 1
            self.load_directory(self.history[self.i], False)
            if self.i == 0:
                self.back.set_sensitive(False)
            if len(self.history):
                self.forward.set_sensitive(True)
        except IndexError:
            return

    def go_up(self, widget):
        """
            Moves up one directory
        """
        self.load_directory(os.path.dirname(self.current))

    def go_home(self, widget):
        """
            Goes to the user's home directory
        """
        self.load_directory(xdg.homedir)
        
    def set_column_width(self, col, stuff=None):
        """
            Called when the user resizes a column
        """
        name = "gui/files_%s_col_width" % col.get_title()
        settings.set_option(name, col.get_width())

    def load_directory(self, dir, history=True, keyword=None):
        """
            Loads a directory into the files view
        """
        dir = str(dir)
        try:
            paths = os.listdir(dir)
        except OSError:
            paths = os.listdir(xdg.homedir)

        settings.set_option('gui/files_panel_dir', dir)
        self.current = dir
        directories = []
        files = []
        for path in paths:
            if path.startswith('.'): continue

            if keyword and path.lower().find(keyword.lower()) == -1:
                continue
            full = os.path.join(dir, path)
            if os.path.isdir(full):
                directories.append(path)

            else:
                (stuff, ext) = os.path.splitext(path)
                if ext.lower()[1:] in metadata.formats:
                    files.append(path)

        directories.sort()
        files.sort()

        self.model.clear()
        
        for d in directories:
            self.model.append([self.directory, d, '-'])

        for f in files:
            try:
                info = os.stat(os.path.join(dir, f))
            except OSError:
                continue
            size = info[6]
            size = size / 1024
            # The next two lines are equivalent to
            # locale.format_string(_("%d KB"), size, True)
            # which is only available in Python >=2.5.
            size = locale.format('%d', size, True)
            size = _("%s KB") % size

            self.model.append([self.track, f, size])

        self.tree.set_model(self.model)
        self.entry.set_text(self.current)
        if history: 
            self.back.set_sensitive(True)
            self.history = self.history[:self.i + 1]
            self.history.append(self.current)
            self.i = len(self.history) - 1
            self.forward.set_sensitive(False)

    def get_selected_tracks(self):
        """
            Returns the selected tracks
        """
        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()

        tracks = []
        for path in paths:
            iter = self.model.get_iter(path)
            value = unicode(model.get_value(iter, 1), 'utf-8')
            value = os.path.join(self.current, value)
            self.append_recursive(tracks, value)

        if tracks:
            return tracks

        # no tracks found
        return None

    def append_recursive(self, songs, value):
        """
            Appends recursively
        """
        if os.path.isdir(value):
            for filename in os.listdir(value):
                self.append_recursive(songs, os.path.join(value, filename))
        else:
            if xl.track.is_valid_track(value):
                tr = self.get_track(value)
                if tr:
                    songs.append(tr)

    def get_track(self, path):
        """
            Returns a single track from a path
        """
        tr = self.collection.get_track_by_loc(path)
        if tr: return tr

        tr = xl.track.Track(path)
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
            guiutil.DragTreeView.dragged_data[track.get_loc()] = track
        urls = guiutil.get_urls_for(tracks)
        selection.set_uris(urls)
        
