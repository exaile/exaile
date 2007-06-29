# Copyright (C) 2006 Adam Olsen
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

from gettext import gettext as _
import locale, os, gtk, urllib, re
from xl import xlmisc, media, library
locale.setlocale(locale.LC_ALL, '')

class FilesPanel(object):
    """
        Represents a built in file browser.
    """

    def __init__(self, exaile):
        """
            Expects a Notebook and Exaile instance
        """
        self.exaile = exaile
        self.db = exaile.db
        self.xml = exaile.xml
        self.first_dir = self.exaile.settings.get_str('files_panel_dir',
            os.getenv('HOME'))
        self.history = [self.first_dir]

        self.tree = xlmisc.DragTreeView(self, False)
        self.tree.set_headers_visible(True)
        container = self.xml.get_widget('files_box')
        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.set_shadow_type(gtk.SHADOW_IN)
        self.scroll.add(self.tree)
        container.pack_start(self.scroll, True, True)
        container.show_all()

        self.model = gtk.ListStore(gtk.gdk.Pixbuf, str, str)
        self.tree.set_model(self.model)
        selection = self.tree.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        self.directory = xlmisc.get_icon('gnome-fs-directory')
        self.track = gtk.gdk.pixbuf_new_from_file(os.path.join('images',
            'track.png'))
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
        self.counter = 0

        pb = gtk.CellRendererPixbuf()
        text = gtk.CellRendererText()
        col = gtk.TreeViewColumn(_('Path'))
        col.pack_start(pb, False)
        col.pack_start(text, True)
        col.set_fixed_width(130)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        col.set_resizable(True)
        col.set_attributes(pb, pixbuf=0)
        col.set_attributes(text, text=1)
        self.i = 0

        self.tree.append_column(col)

        text = gtk.CellRendererText()
        text.set_property('xalign', 1.0)
        col = gtk.TreeViewColumn(_('Size'))
        col.set_fixed_width(50)
        col.set_resizable(True)
        col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        col.pack_start(text, False)
        col.set_attributes(text, text=2)
        self.tree.append_column(col)

        # set up the search entry
        self.search = self.xml.get_widget('files_search_entry')
        self.search.connect('key-release-event', self.key_release)
        self.search.connect('activate', lambda *e:
            self.load_directory(self.current, history=False,
            keyword=self.search.get_text()))

        self.key_id = None

        self.load_directory(self.first_dir, False)
        self.tree.connect('row-activated', self.row_activated)
        self.menu = xlmisc.Menu()
        self.menu.append(_("Append to Playlist"), self.append)
        self.queue_item = self.menu.append(_("Queue Items"), self.append)

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
            keyword=self.search.get_text()))

    def drag_get_data(self, treeview, context, sel, target_id, etime):
        """
            Called when a drag source wants data for this drag operation
        """

        songs = self.get_selected_songs()
        uris = [urllib.quote(song.loc.encode(xlmisc.get_default_encoding())) for song in songs]

        sel.set_uris(uris)

    def button_press(self, widget, event):
        """
            Called to show the menu when someone right clicks
        """
        selection = self.tree.get_selection()
        if event.button == 3:
            self.menu.popup(None, None, None, event.button, event.time)
            return True
        if selection.count_selected_rows() <= 1: return False

    def append(self, widget, event):
        self.exaile.status.set_first(_("Scanning and adding files..."))
        songs = self.get_selected_songs()
        if songs:
            self.exaile.playlist_manager.append_songs(songs, queue=(widget == self.queue_item),
                play=False)
        self.counter = 0
        self.exaile.status.set_first(None)

    def get_selected_songs(self):
        """
            Appends recursively the selected directory/files
        """
        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()
        songs = library.TrackData()

        for path in paths:
            iter = self.model.get_iter(path)
            value = model.get_value(iter, 1)
            value = os.path.join(self.current, value)
            (stuff, ext) = os.path.splitext(value)
            if os.path.isdir(value):
                self.append_recursive(songs, value)
            elif ext.lower() in media.SUPPORTED_MEDIA:
                tr = self.get_track(value)
                if tr:
                    songs.append(tr)

        if songs:
            # sort the songs
            ar = [(song.artist, song.album, song.track, song.title, song)
                for song in songs]
            ar.sort()
            songs = [item[-1] for item in ar]
            return songs
        else:
            return None

    def get_track(self, path):
        """
            Gets a track
        """
        tr = library.read_track(self.exaile.db, self.exaile.all_songs, path)
        return tr

    def append_recursive(self, songs, dir):
        """
            Appends recursively
        """
        for file in os.listdir(dir):
            if os.path.isdir(os.path.join(dir, file)):
                self.append_recursive(songs, os.path.join(dir, file))
            else:
                (stuff, ext) = os.path.splitext(file)
                if ext.lower() in media.SUPPORTED_MEDIA:
                    tr = self.get_track(os.path.join(dir, file))
                    if tr:
                        songs.append(tr)
                if self.counter >= 15:
                    xlmisc.finish()
                    self.counter = 0
                else:
                    self.counter += 1

    def refresh(self, widget):
        """
            Refreshes the current view
        """
        self.load_directory(self.current, False)

    def entry_activate(self, widget, event=None):
        """
            Called when the user presses enter in the entry box
        """
        dir = os.path.expanduser(self.entry.get_text())
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

    def row_activated(self, *i):
        """
            Called when someone double clicks a row
        """
        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()

        for path in paths:
            iter = self.model.get_iter(path)
            value = model.get_value(iter, 1)
            dir = os.path.join(self.current, value)
            if os.path.isdir(dir):
                self.load_directory(dir)
            else:
                if any(dir.endswith(ext) for ext in xlmisc.PLAYLIST_EXTS):
                    self.exaile.import_playlist(dir, True)
                else:
                    tr = library.read_track(self.exaile.db, self.exaile.all_songs,
                        dir)
                    if tr:
                        self.exaile.playlist_manager.append_songs((tr, ))

    def load_directory(self, dir, history=True, keyword=None):
        """
            Loads a directory into the files view
        """
        try:
            paths = os.listdir(dir)
        except OSError:
            dir = os.getenv('HOME')
            paths = os.listdir(dir)

        self.exaile.settings['files_panel_dir'] = dir
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
                if ext.lower() in media.SUPPORTED_MEDIA:
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
            size = locale.format("%d", size, True) + " KB"

            self.model.append([self.track, f, size])

        self.tree.set_model(self.model)
        self.entry.set_text(self.current)
        if history: 
            self.back.set_sensitive(True)
            self.history = self.history[:self.i + 1]
            self.history.append(self.current)
            self.i = len(self.history) - 1
            self.next.set_sensitive(False)
