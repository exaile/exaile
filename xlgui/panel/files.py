# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 3, or (at your option)
# any later version.
#
# this program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with this program; if not, write to the free software
# foundation, inc., 675 mass ave, cambridge, ma 02139, usa.

import gtk, os, locale, re
import xl.track, urllib
from xl import common, trackdb
from xlgui import panel, guiutil, xdg, menu
from gettext import gettext as _
locale.setlocale(locale.LC_ALL, '')

class FilesPanel(panel.Panel):
    """
        The Files panel
    """

    gladeinfo = ('files_panel.glade', 'FilesPanelWindow')

    def __init__(self, controller, collection):
        """
            Initializes the files panel
        """
        panel.Panel.__init__(self, controller)
        self.settings = controller.exaile.settings
        self.collection = collection

        self.box = self.xml.get_widget('files_box')

        self.targets = [('text/uri-list', 0, 0)]
       
        self._setup_tree()
        self._setup_widgets()
        self.menu = menu.FilesPanelMenu(self, controller.main)

        self.key_id = None
        self.i = 0

        self.first_dir = self.settings.get_option('gui/files_panel_dir',
            xdg.homedir)
        self.history = [self.first_dir]
        self.load_directory(self.first_dir, False)

    def _setup_tree(self):
        """
            Sets up tree widget for the files panel
        """
        self.model = gtk.ListStore(gtk.gdk.Pixbuf, str, str)
        self.tree = guiutil.DragTreeView(self, True, True)
        self.tree.set_model(self.model)
        self.tree.set_headers_visible(False)
        self.tree.connect('row-activated', self.row_activated)

        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.tree)
        self.scroll.set_shadow_type(gtk.SHADOW_IN)
        self.box.pack_start(self.scroll, True, True)

        pb = gtk.CellRendererPixbuf()
        text = gtk.CellRendererText()
        # TRANSLATORS: Filename column in the file browser
        col = gtk.TreeViewColumn(_('Filename'))
        col.pack_start(pb, False)
        col.pack_start(text, True)
        col.connect('notify::width', self.set_column_width)

        width = self.settings.get_option('gui/files_%s_col_width' %
            _('Filename'), 130)

        col.set_fixed_width(width)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        col.set_resizable(True)
        col.set_attributes(pb, pixbuf=0)
        col.set_attributes(text, text=1)

        self.tree.append_column(col)

        width = self.settings.get_option('gui/files_%s_col_width' %
            _('Size'), 50)

        text = gtk.CellRendererText()
        text.set_property('xalign', 1.0)
        # TRANSLATORS: Filesize column in the file browser
        col = gtk.TreeViewColumn(_('Size'))
        col.set_fixed_width(width)
        col.set_resizable(True)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        col.pack_start(text, False)
        col.set_attributes(text, text=2)
        col.connect('notify::width', self.set_column_width)
        self.tree.append_column(col)

    def _setup_widgets(self):
        """
            Sets up the widgets for the files panel
        """
        self.directory = guiutil.get_icon('gnome-fs-directory')
        self.track = gtk.gdk.pixbuf_new_from_file(
            xdg.get_data_path('images/track.png'))
        self.up = self.xml.get_widget('files_up_button')
        self.up.connect('clicked', self.go_up)
        self.back = self.xml.get_widget('files_back_button')
        self.back.connect('clicked', self.go_prev)
        self.next = self.xml.get_widget('files_next_button')
        self.next.connect('clicked', self.go_next)
        self.entry = self.xml.get_widget('files_entry')
        self.entry.connect('activate', self.entry_activate)
        self.xml.get_widget('files_refresh_button').connect('clicked',
            self.refresh)

        # set up the search entry
        self.search = self.xml.get_widget('files_search_entry')
        self.search.connect('key-release-event', self.key_release)
        self.search.connect('activate', lambda *e:
            self.load_directory(self.current, history=False,
            keyword=unicode(self.search.get_text(), 'utf-8')))

    def button_press(self, button, event):
        """
            Called when the user clicks on the playlist
        """
        if event.button == 3:
            selection = self.tree.get_selection()
            self.menu.popup(event)

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
#            else:
#                if common.any(dir.endswith(ext) for ext in xlmisc.PLAYLIST_EXTS):
#                    self.exaile.import_playlist(dir, True)
#                else:
#                    tr = library.read_track(self.exaile.db, self.exaile.all_songs,
#                        dir)
#                    if tr:
#                        self.exaile.playlist_manager.append_songs((tr, ))

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
        self.load_directory(dir)

    def go_next(self, widget):
        """
            Goes to the next entry in history
        """
        self.i += 1 
        self.load_directory(self.history[self.i], False)
        if self.i >= len(self.history) - 1:
            self.next.set_sensitive(False)
        if len(self.history):
            self.back.set_sensitive(True)
            
    def go_prev(self, widget):
        """
            Previous entry
        """
        self.i -= 1
        self.load_directory(self.history[self.i], False)
        if self.i == 0:
            self.back.set_sensitive(False)
        if len(self.history):
            self.next.set_sensitive(True)

    def go_up(self, widget):
        """
            Moves up one directory
        """
        cur = re.sub('(.*)%s[^%s]*$' % (os.sep, os.sep),
            r'\1', self.current)
        if not cur: cur = os.sep

        self.load_directory(cur)

    def set_column_width(self, col, stuff=None):
        """
            Called when the user resizes a column
        """
        name = "gui/files_%s_col_width" % col.get_title()
        self.settings[name] = col.get_width()

    def load_directory(self, dir, history=True, keyword=None):
        """
            Loads a directory into the files view
        """
        dir = str(dir)
        try:
            paths = os.listdir(dir)
        except OSError:
            paths = os.listdir(xdg.homedir)

        self.settings['gui/files_panel_dir'] = dir
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
                if ext.lower() in xl.track.SUPPORTED_MEDIA:
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
            self.next.set_sensitive(False)

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
            (stuff, ext) = os.path.splitext(value)
            if os.path.isdir(value):
                self.append_recursive(tracks, value)
            elif ext.lower() in media.SUPPORTED_MEDIA:
                tr = self.get_track(value)
                if tr:
                    tracks.append(tr)

        if tracks:
            # sort the tracks
            tracks = trackdb.sort_tracks(('artist', 'album', 'tracknumber'),
                tracks)
            return tracks

        # no tracks found
        return None

    def append_recursive(self, songs, dir):
        """
            Appends recursively
        """
        for file in os.listdir(dir):
            if os.path.isdir(os.path.join(dir, file)):
                self.append_recursive(songs, os.path.join(dir, file))
            else:
                (stuff, ext) = os.path.splitext(file)
                if ext.lower() in xl.track.SUPPORTED_MEDIA:
                    tr = self.get_track(os.path.join(dir, file))
                    if tr:
                        songs.append(tr)

    def get_track(self, path):
        """
            Returns a single track from a path
        """
        if path in self.collection.tracks:
            return self.collection.tracks[path]

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
        for track in tracks:
            guiutil.DragTreeView.dragged_data[track.get_loc()] = track
        urls = self._get_urls_for(tracks)
        selection.set_uris(urls)

    def _get_urls_for(self, items):
        """
            Returns the items' URLs
        """
        return [urllib.quote(item.get_loc().encode(common.get_default_encoding()))
            for item in items]
