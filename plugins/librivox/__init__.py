# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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
# Arunas Radzvilavicius, arunas.rv@gmail.com
#    TODO: download books?
#    Drag and drop for books with yet unknown chapters works with
#    main playlist only (see get_chapters_and_drop and related functions).
#    Otherwise, (without threaded functions) UI is non responsive, while
#    fetching that info...

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gtk

import os

from . import librivoxsearch as LS
from . import about_window as AW
from xl import common, event, providers, settings, trax
from xlgui import guiutil, icons, main
from xlgui.widgets.common import DragTreeView
from xlgui.widgets.notebook import NotebookPage


def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)


def _enable(o1, exaile, o2):
    global LVPANEL
    LVPANEL = LVPanel(exaile)

    providers.register('main-panel', LVPANEL)


def disable(exaile):
    global LVPANEL
    if LVPANEL.aboutwindow is not None:
        LVPANEL.aboutwindow.win.destroy()

    providers.unregister('main-panel', LVPANEL)


class LVPanel:
    def on_search(self, widget):
        self.run_search(widget)

    @common.threaded
    def run_search(self, widget):
        (c_id, msg_id) = self.statusbar.set_status('Searching...')
        self.keyword = self.entry.get_text()
        self.books = LS.find_books(self.keyword, self._user_agent)
        self.generate_treestore(self.books)
        self.statusbar.unset_status(c_id, msg_id)

    def on_row_exp(self, treeview, iter, path):
        row = path[0]
        if not self.books[row].is_loading and not self.books[row].loaded:
            self.get_chapters(row)

    @common.threaded
    def get_chapters(self, row):
        self.get_all(row)
        return

    @common.threaded
    def get_chapters_and_add(self, row):
        self.get_all(row)
        self.add_to_playlist(self.books[row].chapters)
        return

    @common.idle_add()
    def done_getting_chapters(self, row):
        # adds chapters to treeview and removes "Loading..." message
        l_iter = self.treestore.get_iter((row, 0))
        iter = self.treestore.get_iter((row,))
        for chapter in self.books[row].chapters:
            self.rowlvl2 = self.treestore.append(iter, [chapter[0], self.chapter_icon])
        if len(self.books[row].chapters) > 0:
            self.treestore.remove(l_iter)

    def __init__(self, exaile):

        self.name = 'librivox'  # needed for panel provider
        self._panel = None

        self._user_agent = exaile.get_user_agent_string('librivox')

        self.librivoxdir = os.path.dirname(__file__)
        self.abicon = GdkPixbuf.Pixbuf.new_from_file(self.librivoxdir + '/ebook.png')
        self.clock_icon = GdkPixbuf.Pixbuf.new_from_file(
            self.librivoxdir + '/clock.png'
        )
        self.chapter_icon = icons.MANAGER.pixbuf_from_icon_name(
            'audio-x-generic', Gtk.IconSize.SMALL_TOOLBAR
        )
        self.gui_init(exaile)
        self.connect_events()
        self.getting_info = False

    def gui_init(self, exaile):
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.vbox.set_border_width(3)
        self.search_label = Gtk.Label(label="LibriVox.org")
        self.vbox.pack_start(self.search_label, False, True, 4)
        self.entry = guiutil.SearchEntry()
        self.entry.connect("activate", self.run_search)

        self.hbox = Gtk.Box()
        self.vbox.pack_start(self.hbox, False, True, 0)
        self.hbox.pack_start(self.entry.entry, True, True, 0)
        self.searchbutton = Gtk.Button()

        self.searchimage = Gtk.Image.new_from_icon_name('edit-find', Gtk.IconSize.MENU)
        self.searchbutton.set_image(self.searchimage)
        self.searchbutton.connect("pressed", self.run_search)
        self.hbox.pack_start(self.searchbutton, False, True, 0)

        self.statusbar = Status()
        self.vbox.pack_start(self.statusbar.bar, False, True, 0)

        self.scrlw = Gtk.ScrolledWindow()
        self.scrlw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scrlw.set_shadow_type(Gtk.ShadowType.IN)
        self.vbox.pack_start(self.scrlw, True, True, 0)

        self.treestore = Gtk.TreeStore(str, GdkPixbuf.Pixbuf)
        self.treeview = Gtk.TreeView.new_with_model(self.treestore)
        self.treeview.set_headers_visible(False)
        self.column = Gtk.TreeViewColumn(None)
        self.cell = Gtk.CellRendererText()
        if settings.get_option('gui/ellipsize_text_in_panels', False):
            from gi.repository import Pango

            self.cell.set_property('ellipsize-set', True)
            self.cell.set_property('ellipsize', Pango.EllipsizeMode.END)
        self.cellpb = Gtk.CellRendererPixbuf()
        self.column.pack_start(self.cellpb, False)
        self.column.pack_start(self.cell, True)
        self.column.set_attributes(self.cell, text=0)
        self.column.set_attributes(self.cellpb, pixbuf=1)
        self.treeview.append_column(self.column)
        self.treeview.connect("row-expanded", self.on_row_exp)

        self.treeview.drag_source_set(
            Gdk.ModifierType.BUTTON1_MASK,
            [Gtk.TargetEntry.new('text/uri-list', 0, 0)],
            Gdk.DragAction.COPY,
        )
        self.treeview.connect("drag-data-get", self.drag_data_get)
        self.scrlw.add(self.treeview)

        self.title = 'LibriVox'
        self.vbox.show_all()

        self.popup_menu = Gtk.Menu()
        self.add_to_pl = Gtk.ImageMenuItem.new_with_label("Append to Current")
        self.add_to_pl.set_image(
            Gtk.Image.new_from_icon_name('list-add', Gtk.IconSize.MENU)
        )
        self.about_book = Gtk.ImageMenuItem.new_with_label("About the Book")
        self.about_book.set_image(
            Gtk.Image.new_from_icon_name('help-about', Gtk.IconSize.MENU)
        )
        self.popup_menu.add(self.add_to_pl)
        self.popup_menu.add(self.about_book)
        self.popup_menu.show_all()

        self.aboutwindow = None

    def connect_events(self):
        self.treeview.connect("row-activated", self.on_append_to_playlist)
        self.treeview.connect("button-press-event", self.menu_popup)
        self.add_to_pl.connect("activate", self.on_append_to_playlist)
        self.about_book.connect("button-press-event", self.on_about_book)
        self.treeview.connect("drag_begin", self.on_drag_begin)

    def generate_tracks(self, chapters):
        tracks = []
        for chapter in chapters:
            chapter_track = trax.Track(chapter[1])
            chapter_track.set_tags(
                artist='Librivox.org', title=chapter[0], album='Audiobook'
            )
            tracks.append(chapter_track)
        return tracks

    def on_append_to_playlist(self, widget, path=None, column=None):
        if not path:
            path = self.treeview.get_cursor()[0]
        row = path[0]
        if self.books[row].is_loading:
            return
        if len(path) == 1:  # selected item is book
            if self.books[row].loaded:  # book info already loaded
                self.add_to_playlist(self.books[row].chapters)
            else:
                self.get_chapters_and_add(row)

        if len(path) > 1:  # selected item is chapter
            chapter = self.books[path[0]].chapters[path[1]]
            self.add_to_playlist([chapter])

    def add_to_playlist(self, chapters):
        current_playlist = main.get_selected_playlist()
        if not current_playlist:
            return

        tracks = self.generate_tracks(chapters)
        current_playlist.playlist.extend(tracks)

    def menu_popup(self, treeview, event):
        if event.triggers_context_menu():
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = self.treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                self.treeview.grab_focus()
                self.treeview.set_cursor(path, col, 0)
                self.popup_menu.popup(None, None, None, None, event.button, time)
            return 1

    @common.idle_add()
    def generate_treestore(self, books):
        self.treestore.clear()
        for book in books:
            self.rowlvl1 = self.treestore.append(None, [book.title, self.abicon])
            self.rowlvl2 = self.treestore.append(
                self.rowlvl1, ["Loading...", self.clock_icon]
            )

    def drag_data_get(self, treeview, context, selection, info, timestamp):
        path = self.treeview.get_cursor()[0]
        if not path:
            return
        if len(path) == 1:  # book selected
            book = self.books[path[0]]
            uris = []
            if book.loaded:  # chapters loaded
                for chapter in book.chapters:
                    chapter_track = self.generate_tracks([chapter])
                    DragTreeView.dragged_data[chapter[1]] = chapter_track[0]
                    uris.append(chapter[1])
                selection.set_uris(uris)
                del uris

            else:
                if book.is_loading:
                    return

                current_playlist = main.get_selected_playlist()
                if not current_playlist:
                    return

                current_playlist_tv = current_playlist.list

                (x, y) = current_playlist_tv.get_pointer()
                rect = current_playlist_tv.get_allocation()
                if x < 0 or x > rect.width or y < 0 or y > rect.height:
                    # dropping not in main playlist
                    return
                drop_info = current_playlist_tv.get_dest_row_at_pos(x, y)

                if drop_info:
                    PLpath, position = drop_info
                    if position == Gtk.TreeViewDropPosition.AFTER:
                        after = True
                    else:
                        after = False

                    self.get_chapters_and_drop(book, current_playlist, PLpath, after)

                else:
                    self.get_chapters_and_add(path[0])

        elif len(path) == 2:
            if self.books[path[0]].is_loading:
                return
            chapter = self.books[path[0]].chapters[path[1]]
            chapter_track = self.generate_tracks([chapter])
            DragTreeView.dragged_data[chapter[1]] = chapter_track[0]
            uri = chapter[1]
            selection.set('text/uri-list', 0, uri)

    @common.threaded
    def get_chapters_and_drop(self, book, current_playlist, PLpath, after):
        path = self.treeview.get_cursor()[0]
        row = path[0]
        self.get_all(row)
        self.drop_after_getting(book, current_playlist, PLpath, after)

    @common.idle_add()
    def drop_after_getting(self, book, current_playlist, PLpath, after):
        # simulates drag_data_received() function of xlgui/playlist.py
        if current_playlist.playlist.ordered_tracks:
            curtrack = current_playlist.playlist.get_current()
        else:
            curtrack = None
        iter = current_playlist.model.get_iter(PLpath)
        tracks = self.generate_tracks(book.chapters)
        for track in tracks:
            ar = current_playlist._get_ar(track)
            if not after:
                after = True
                iter = current_playlist.model.insert_before(iter, ar)
            else:
                iter = current_playlist.model.insert_after(iter, ar)
        # re add to ordered playlist
        current_playlist.playlist.ordered_tracks = []
        for row in current_playlist.model:
            current_playlist.playlist.ordered_tracks.append(row[0])
        current_playlist.main.update_track_counts()
        if curtrack is not None:
            index = current_playlist.playlist.index(curtrack)
            current_playlist.playlist.set_current_pos(index)

    def on_drag_begin(self, widget, context):
        self.treeview.drag_source_set_icon_pixbuf(self.abicon)

    @common.threaded
    def on_about_book(self, widget, event):
        path = self.treeview.get_cursor()[0]
        row = path[0]
        if self.books[row].is_loading:
            return
        if not self.books[row].loaded:
            self.get_all(row)
        self.done_getting_info(row)

    @common.idle_add()
    def done_getting_info(self, row):
        if self.aboutwindow is None:
            self.aboutwindow = AW.AboutWindow()
        self.aboutwindow.set_text(self.books[row])
        if not self.aboutwindow.showing:
            self.aboutwindow.win.show()
            self.aboutwindow.showing = True
        elif self.aboutwindow.showing:
            self.aboutwindow.win.present()

    def get_all(self, row):
        (c_id, msg_id) = self.statusbar.set_status('Loading...')
        self.books[row].is_loading = True
        self.books[row].get_all()
        self.done_getting_chapters(row)
        self.books[row].is_loading = False
        self.statusbar.unset_status(c_id, msg_id)

    def get_panel(self):
        if self._panel is None:
            self._panel = NotebookPage(self.vbox, self.title, 'panel-tab-context')
        return self._panel


class Status:
    '''Status bar'''

    def __init__(self):
        self.bar = Gtk.Statusbar()
        self.bar.show_all()

    def set_status(self, status):
        context_id = 1
        msg_id = self.bar.push(context_id, status)
        return (context_id, msg_id)

    def unset_status(self, context_id, msg_id):
        self.bar.remove(context_id, msg_id)
