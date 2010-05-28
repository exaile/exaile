# Copyright (C) 2010 Aren Olson
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

import gtk, gobject, glib, pango
import collections
import os, sys
import random

from xl.nls import gettext as _
from xl import (event, common, trax, formatter, settings, providers,
        player)
from xlgui import guiutil, icons
import playlist_columns, menu as plmenu

import logging
logger = logging.getLogger(__name__)


WINDOW = None

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

def _enable(o1, exaile, o2):
    global WINDOW
    WINDOW = TestWindow(exaile)

def disable(exaile):
    global WINDOW
    WINDOW.destroy()
    WINDOW = None


class TestWindow(object):
    def __init__(self, exaile):
        self.exaile = exaile
        trs = exaile.collection
        pl = Playlist("test", trs)
        exaile.shortcut = pl
        self.window = gtk.Window()
        self.tabs = PlaylistNotebook()
        self.tabs.create_tab_from_playlist(pl)
        self.window.add(self.tabs)
        self.window.resize(800, 600)
        self.window.show_all()

    def destroy(self):
        self.window.destroy()


class PlaylistNotebook(gtk.Notebook):
    def __init__(self):
        gtk.Notebook.__init__(self)

    def add_tab(self, tab, page):
        """
            Add a tab to the notebook. It will be given focus.

            :param tab: The tab to use
            :type tab: NotebookTab
            :param page: The page to use
            :type page: NotebookPage
        """
        self.append_page(page, tab)
        self.set_current_page(self.page_num(page))

    def create_tab_from_playlist(self, playlist):
        """
            Create a tab that will contain the passed-in playlist

            :param playlist: The playlist to create tab from
            :type playlist: :class:`xl.playlist.Playlist`
        """
        page = PlaylistPage(playlist)
        tab = NotebookTab(self, page)
        self.add_tab(tab, page)
        return tab

    def create_new_playlist(self):
        """
            Create a new tab containing a blank playlist. The tab will
            be automatically given a unique name.
        """
        seen = []
        for n in range(self.get_n_pages()):
            page = self.get_nth_page(n)
            name = page.get_name()
            if name.startswith('Playlist '):
                try:
                    val = int(name[9:])
                except:
                    pass
                else:
                    seen.append(val)
        n = 1
        while True:
            if n not in seen:
                break
            n += 1
        pl = Playlist("Playlist %d"%n)
        return self.create_tab_from_playlist(pl)


class NotebookTab(gtk.EventBox):
    """
        Class to represent a generic tab in a gtk.Notebook.
    """
    menu_provider_name = 'notebooktab' # Change this in subclasses!
    def __init__(self, notebook, page):
        """
            :param notebook: The notebook this tab will belong to
            :param page: The page this tab will be associated with
        """
        gtk.EventBox.__init__(self)
        self.set_visible_window(False)

        self.notebook = notebook
        self.page = page
        page.set_tab(self)

        self.menu = plmenu.ProviderMenu(self.menu_provider_name, self)

        self.connect('button-press-event', self.on_button_press)

        box = gtk.HBox(False, 2)
        self.add(box)

        self.icon = gtk.Image()
        self.icon.set_property("visible", False)
        box.pack_start(self.icon, False, False)

        self.label = gtk.Label(self.page.get_name())
        self.label.set_max_width_chars(20)
        self.label.set_ellipsize(pango.ELLIPSIZE_END)
        box.pack_start(self.label, False, False)

        self.entry = gtk.Entry()
        self.entry.set_width_chars(self.label.get_max_width_chars())
        self.entry.set_text(self.label.get_text())
        self.entry.connect('activate', self.on_entry_activate)
        self.entry.connect('focus-out-event', self.on_entry_focus_out_event)
        self.entry.connect('key-press-event', self.on_entry_key_press_event)
        self.entry.set_no_show_all(True)
        box.pack_start(self.entry, False, False)

        self.button = button = gtk.Button()
        button.set_name("tabCloseButton")
        button.set_relief(gtk.RELIEF_NONE)
        button.set_focus_on_click(False)
        button.set_tooltip_text(_("Close tab"))
        button.add(gtk.image_new_from_stock(gtk.STOCK_CLOSE, gtk.ICON_SIZE_MENU))
        button.connect('clicked', self.close)
        button.connect('button-press-event', self.on_button_press)
        box.pack_start(button, False, False)

        self.show_all()

    def set_icon(self, pixbuf):
        """
            Set the primary icon for the tab.

            :param pixbuf: The icon to use, or None to hide
            :type pixbuf: :class:`gtk.gdk.Pixbuf`
        """
        if pixbuf is None:
            self.icon.set_property("visible", False)
        else:
            self.icon.set_from_pixbuf(pixbuf)
            self.icon.set_property("visible", True)

    def on_button_press(self, widget, event):
        """
            Handles mouse button events on the tab.

            Typically triggers renaming, closing and menu.
        """
        if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            self.start_rename()
        elif event.button == 2:
            self.close()
        elif event.button == 3:
            self.page.tab_menu.popup( None, None, None,
                    event.button, event.time)
            return True

    def on_entry_activate(self, entry):
        """
            Handles end of editing and triggers the actual rename.
        """
        self.entry.props.editing_canceled = False
        self.end_rename()

    def on_entry_focus_out_event(self, widget, event):
        """
            Make defocusing the rename box equivalent to activating it.
        """
        if not self.entry.props.editing_canceled:
            widget.activate()

    def on_entry_key_press_event(self, widget, event):
        """
            Cancel rename if Escape is pressed
        """
        if event.keyval == gtk.keysyms.Escape:
            self.entry.props.editing_canceled = True
            self.end_rename()
            return True

    def start_rename(self):
        """
            Initiates the renaming of a tab, if the page supports this.
        """
        if not self.can_rename():
            return
        self.entry.set_text(self.page.get_name())
        self.label.hide()
        self.button.hide()
        self.entry.show()
        self.entry.select_region(0, -1)
        self.entry.grab_focus()

    def end_rename(self, cancel=False):
        """
            Finishes or cancels the renaming
        """
        name = self.entry.get_text()

        if name.strip() != "" and not self.entry.props.editing_canceled:
            self.page.set_name(name)
            self.label.set_text(name)

        self.entry.hide()
        self.label.show()
        self.button.show()

        self.entry.props.editing_canceled = False

    def can_rename(self):
        return hasattr(self.page, 'set_name')

    def close(self, *args):
        if self.page.handle_close():
            self.notebook.remove_page(self.notebook.page_num(self.page))


class NotebookPage(object):
    """
        Base class representing a page. Should never be used directly.

        Subclasses will also need to inherit from gtk.VBox or some
        other gtk widget, as Pages are generally directly added to the
        Notebook.
    """
    menu_provider_name = 'tab-context' #override this in subclasses
    def __init__(self):
        self.tab = None
        self.tab_menu = plmenu.ProviderMenu(self.menu_provider_name, self)

    def get_name(self):
        """
            Returns the name of this tab. Should be overriden in subclasses.

            Subclasses can also implement set_name(self, name) to allow
            renaming, but this is not mandatory.
        """
        return "UNNAMED PAGE"

    def set_tab(self, tab):
        """
            Set the tab that holds this page.  This will be called directly
            from the tab itself when it is created, and should not be used
            outside of that.
        """
        self.tab = tab

    def handle_close(self):
        """
            Called when the tab is about to be closed. This can be used to
            handle showing a save dialog or similar actions. Should return
            True if we're OK with continuing to close, or False to abort
            the close.
        """
        raise NotImplementedError


# do this in a function to avoid polluting the global namespace
def __create_playlist_tab_context_menu():
    smi = plmenu.simple_menu_item
    sep = plmenu.simple_separator
    items = []
    items.append(smi('new-tab', [], _("New Playlist"), 'tab-new',
        lambda w, o, c: o.tab.notebook.create_new_playlist()))
    items.append(sep('new-tab-sep', ['new-tab']))
    items.append(smi('rename', ['new-tab-sep'], _("Rename"), 'gtk-edit',
        lambda w, o, c: o.tab.start_rename()))
    items.append(smi('clear', ['rename'], _("Clear"), 'gtk-clear',
        lambda w, o, c: o.playlist.clear()))
    items.append(sep('tab-close-sep', ['clear']))
    items.append(smi('tab-close', ['tab-close-sep'], _("Close"), 'gtk-close',
        lambda w, o, c: o.tab.close()))
    for item in items:
        providers.register('playlist-tab-context', item)
__create_playlist_tab_context_menu()


class PlaylistContextMenu(plmenu.ProviderMenu):
    def __init__(self, page):
        """
            :param page: The :class:`PlaylistPage` this menu is
                associated with.
        """
        plmenu.ProviderMenu.__init__(self, 'playlist-context', page)

    def get_parent_context(self):
        ctx = {}
        ctx['selected-tracks'] = self._parent.get_selected_tracks()
        return ctx

def __create_playlist_context_menu():
    smi = plmenu.simple_menu_item
    sep = plmenu.simple_separator
    items = []
    items.append(smi('append-queue', [], _("Append to Queue"), 'gtk-add',
            lambda w, o, c: player.QUEUE.add_tracks(
            [t[1] for t in c['selected-tracks']])))
    def toggle_spat_cb(widget, playlistpage, context):
        pos = context['selected-tracks'][0][0]
        if pos != playlistpage.playlist.spat_pos:
            playlistpage.playlist.spat_pos = pos
        else:
            playlistpage.playlist.spat_pos = -1
    items.append(smi('toggle-spat', ['append-queue'],
            _("Toggle Stop After This Track"), 'gtk-stop', toggle_spat_cb))
    items.append(plmenu.RatingMenuItem('rating', ['toggle-spat'],
            lambda o, c: [t[1] for t in c['selected-tracks']]))
    # TODO: custom playlist item here
    items.append(sep('sep1', ['rating']))
    def remove_tracks_cb(widget, playlistpage, context):
        tracks = context['selected-tracks']
        pl = playlistpage.playlist
        # If it's all one block, just delete it in one chunk for
        # maximum speed.
        idxs = [t[0] for t in tracks]
        if idxs == range(idxs[0], idxs[0]+len(idxs)+1):
            del pl[idxs[0]:idxs[0]+len(idxs)+1]
        else:
            for idx, tr in tracks[::-1]:
                del pl[idx]
    items.append(smi('remove', ['sep1'], _("Remove"), 'gtk-remove',
        remove_tracks_cb))
    items.append(sep('sep2', ['remove']))
    items.append(smi('properties', ['sep2'], _("Properties"), 'gtk-properties',
        lambda w, o, c: False))
    for item in items:
        providers.register('playlist-context', item)
__create_playlist_context_menu()


class PlaylistPage(gtk.VBox, NotebookPage):
    """
        Displays a playlist and associated controls.
    """
    default_columns = ['tracknumber', 'title', 'album', 'artist', '__rating', '__length']
    menu_provider_name = 'playlist-tab-context'

    def __init__(self, playlist):
        """
            :param playlist: The :class:`xl.playlist.Playlist` to display
                in this page.
        """
        gtk.VBox.__init__(self)
        NotebookPage.__init__(self)

        self.playlist = playlist
        self.icon = None
        self.menu = PlaylistContextMenu(self)

        uifile = os.path.join(os.path.dirname(__file__), "playlist.ui")
        self.builder = gtk.Builder()
        self.builder.add_from_file(uifile)
        plpage = self.builder.get_object("playlist_page")
        for child in plpage.get_children():
            plpage.remove(child)

        self.builder.connect_signals(self)

        self.plwin = self.builder.get_object("playlist_window")
        self.controls = self.builder.get_object("controls_box")
        self.pack_start(self.plwin, True, True, padding=2)
        self.pack_start(self.controls, False, False, padding=2)

        self.view = guiutil.DragTreeView(self, drop_pos="between")
        self.plwin.add(self.view)
        self.shuffle_button = self.builder.get_object("shuffle_button")
        self.repeat_button = self.builder.get_object("repeat_button")
        self.dynamic_button = self.builder.get_object("dynamic_button")

        self.model = PlaylistModel(playlist, self.default_columns)
        self.view.set_rules_hint(True)
        self.view.set_enable_search(True)
        self.selection = self.view.get_selection()
        self.selection.set_mode(gtk.SELECTION_MULTIPLE)

        self.view.set_model(self.model)

        for idx, col in enumerate(self.model.columns):
            idx += 1 # offset for pixbuf column
            plcol = playlist_columns.COLUMNS[col](self)
            gcol = plcol.get_column(idx)
            self.view.append_column(gcol)

        self.view.connect("drag-drop", self.on_drag_drop)
        self.view.connect("row-activated", self.on_row_activated)

        event.add_callback(self.on_shuffle_mode_changed,
                "playlist_shuffle_mode_changed", self.playlist)
        event.add_callback(self.on_repeat_mode_changed,
                "playlist_repeat_mode_changed", self.playlist)
        self.model.connect('row-changed', self.on_row_changed)

        self.show_all()

    def get_name(self):
        return self.playlist.name

    def set_name(self, name):
        self.playlist.name = name

    def set_cell_weight(self, cell, iter):
        """
            Called by columns in playlist_columns to set a CellRendererText's
            weight property for the playing track.
        """
        path = self.model.get_path(iter)
        track = self.model.get_track(path)
        if track == player.PLAYER.current and \
                path[0] == self.playlist.get_current_pos() and \
                self.playlist == player.QUEUE.current_playlist:
            weight = pango.WEIGHT_HEAVY
        else:
            weight = pango.WEIGHT_NORMAL
        cell.set_property('weight', weight)

    def handle_close(self):
        return True

    def clear(self, *args):
        self.playlist.clear()

    def get_selected_tracks(self):
        """
            Returns a list of :class:`xl.trax.Track` which are currently
            slected in the playlist.
        """
        selection = self.view.get_selection()
        model, paths = selection.get_selected_rows()
        tracks = [(path[0], model.get_track(path)) for path in paths]
        return tracks

    def on_drag_drop(self, view, context, x, y, etime):
        #self.drag_data_received(view, context, x, y,
        #        view.get_selection(), None, etime)
        context.finish(True, False)
        return True

    def on_row_activated(self, *args):
        try:
            idx, track = self.get_selected_tracks()[0]
        except IndexError:
            return

        player.QUEUE.play(track=track)
        player.QUEUE.set_current_playlist(self.playlist)
        self.playlist.set_current_pos(idx)


    def on_shuffle_button_press_event(self, widget, event):
        self.__show_toggle_menu(Playlist.shuffle_modes,
                Playlist.shuffle_mode_names, self.on_shuffle_mode_set,
                'shuffle_mode', widget, event)

    def on_repeat_button_press_event(self, widget, event):
        self.__show_toggle_menu(Playlist.repeat_modes,
                Playlist.repeat_mode_names, self.on_repeat_mode_set,
                'repeat_mode', widget, event)

    def on_dynamic_button_toggled(self, widget):
        pass

    def on_search_entry_activate(self, entry):
        pass

    def __show_toggle_menu(self, names, display_names, callback, attr,
            widget, event):
        """
            Display the menu on the shuffle/repeat toggle buttons

            :param names: The list of names of the menu entries
            :param display_names: The list of names to display on
                each menu entry.
            :param callback: The function to call when a menu item is
                activated. It will be passed the name of the activated item.
            :param attr: The attribute of self.playlist to look at to
                determine the currently-selected item.
            :param widget: The ToggleButton to display the menu on
            :param event: The gtk event that triggered the menu display
        """
        widget.set_active(True)
        menu = gtk.Menu()
        prev = None
        mode = getattr(self.playlist, attr)
        for name, disp in zip(names, display_names):
            item = gtk.RadioMenuItem(prev, disp)
            if name == mode:
                item.set_active(True)
            item.connect('activate', callback, name)
            menu.append(item)
            if prev is None:
                menu.append(gtk.SeparatorMenuItem())
            prev = item
        menu.show_all()
        menu.popup(None, None, self._mode_menu_set_pos,
                event.button, event.time, widget)
        menu.reposition()

    def _mode_menu_set_pos(self, menu, button):
        """
            Nicely position the shuffle/repeat popup menu with the
            button's corner.
        """
        w = self.window.get_position()
        b = button.get_allocation()
        m = menu.get_allocation()
        pos = (w[0]+b.x+1, w[1]+b.y-m.height-1)
        return (pos[0], pos[1], True)

    def on_shuffle_mode_set(self, widget, mode):
        """
            Callback for the Shuffle mode menu
        """
        self.playlist.shuffle_mode = mode

    def on_shuffle_mode_changed(self, evtype, playlist, mode):
        """
            Updates the UI to reflect changes in the shuffle mode
        """
        if mode == 'disabled':
            self.shuffle_button.set_active(False)
        else:
            self.shuffle_button.set_active(True)

    def on_repeat_mode_set(self, widget, mode):
        """
            Callback for the Repeat mode menu
        """
        self.playlist.repeat_mode = mode

    def on_repeat_mode_changed(self, evtype, playlist, mode):
        """
            Updates the UI to reflect changes in the repeat mode
        """
        if mode == 'disabled':
            self.repeat_button.set_active(False)
        else:
            self.repeat_button.set_active(True)

    def on_row_changed(self, model, path, iter):
        """
            Sets the tab icon to reflect the playback status
        """
        if path[0] == self.playlist.current_pos:
            pixbuf = model.get_value(iter, 0)
            if pixbuf == model.clear_pixbuf:
                pixbuf = None
            self.tab.set_icon(pixbuf)

    ### needed for DragTreeView ###

    def drag_data_received(self, view, context, x, y, selection, info, etime):
        print "data recieved"
        self.view.unset_rows_drag_dest()
        self.view.drag_dest_set(gtk.DEST_DEFAULT_ALL,
            self.view.targets,
            gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)
        locs = list(selection.get_uris())
        drop_info = view.get_dest_row_at_pos(x, y)
        if drop_info:
            path, position = drop_info
            iter = self.model.get_iter(path)
        trs, playlists = self.view.get_drag_data(locs)
        print locs, trs, playlists, drop_info
        context.finish(True, False, etime)

    def drag_data_delete(self, view, context):
        print "data delete"
        pass

    def drag_get_data(self, view, context, selection, target_id, etime):
        print "get data"
        tracks = [ x[1] for x in self.get_selected_tracks() ]
        for track in tracks:
            guiutil.DragTreeView.dragged_data[track.get_loc_for_io()] = track

        uris = trax.get_uris_from_tracks(tracks)
        selection.set_uris(uris)

    def button_press(self, widget, event):
        if event.button == 3:
            self.menu.popup(None, None, None, event.button, event.time)
            return True
        return False

    def button_release(self, widget, event):
        pass

    ### end DragTreeView ###


class PlaylistModel(gtk.GenericTreeModel):
    def __init__(self, playlist, columns):
        gtk.GenericTreeModel.__init__(self)
        self.playlist = playlist
        self.columns = columns

        event.add_callback(self.on_tracks_added,
                "playlist_tracks_added", playlist)
        event.add_callback(self.on_tracks_removed,
                "playlist_tracks_removed", playlist)
        event.add_callback(self.on_pos_changed,
                "playlist_current_pos_changed", playlist)
        event.add_callback(self.on_pos_changed,
                "playlist_spat_pos_changed", playlist)
        event.add_callback(self.on_playback_state_change,
                "playback_track_start")
        event.add_callback(self.on_playback_state_change,
                "playback_track_end")
        event.add_callback(self.on_playback_state_change,
                "playback_player_pause")
        event.add_callback(self.on_playback_state_change,
                "playback_player_resume")

        self.play_pixbuf = icons.ExtendedPixbuf(
                icons.MANAGER.pixbuf_from_stock(gtk.STOCK_MEDIA_PLAY))
        self.pause_pixbuf = icons.ExtendedPixbuf(
                icons.MANAGER.pixbuf_from_stock(gtk.STOCK_MEDIA_PAUSE))
        self.stop_pixbuf = icons.ExtendedPixbuf(
                icons.MANAGER.pixbuf_from_stock(gtk.STOCK_STOP))
        stop_overlay_pixbuf = self.stop_pixbuf.scale_simple(
                8, 8, gtk.gdk.INTERP_BILINEAR)
        stop_overlay_pixbuf = stop_overlay_pixbuf.move(
                offset_x=8, offset_y=8, resize=True)
        self.play_stop_pixbuf = self.play_pixbuf & stop_overlay_pixbuf
        self.pause_stop_pixbuf = self.pause_pixbuf & stop_overlay_pixbuf
        self.clear_pixbuf = self.play_pixbuf.copy()
        self.clear_pixbuf.fill(0x00000000)

    def get_track(self, path):
        """
            Returns the Track object associated with the given path. Raises
            IndexError if there is no such track.
        """
        return self.playlist[path[0]]

    ### API for GenericTreeModel ###

    def on_get_flags(self):
        return gtk.TREE_MODEL_LIST_ONLY

    def on_get_n_columns(self):
        return len(self.columns)+1

    def on_get_column_type(self, index):
        if index == 0:
            return gtk.gdk.Pixbuf
        else:
            return playlist_columns.COLUMNS[self.columns[index-1]].datatype

    def on_get_iter(self, path):
        rowref = path[0]
        if rowref < len(self.playlist):
            return rowref
        else:
            return None

    def on_get_path(self, rowref):
        return (rowref,)

    def on_get_value(self, rowref, column):
        if column == 0:
            if self.playlist.current_pos == rowref and \
                    self.playlist[rowref] == player.PLAYER.current and \
                    self.playlist == player.QUEUE.current_playlist:
                state = player.PLAYER.get_state()
                spat = self.playlist.spat_pos == rowref
                if state == 'playing':
                    if spat:
                        return self.play_stop_pixbuf
                    else:
                        return self.play_pixbuf
                elif state == 'paused':
                    if spat:
                        return self.pause_stop_pixbuf
                    else:
                        return self.pause_pixbuf
            if self.playlist.spat_pos == rowref:
                return self.stop_pixbuf
            return self.clear_pixbuf
        else:
            tagname = self.columns[column-1]
            track = self.playlist[rowref]
            formatter = playlist_columns.FORMATTERS[tagname]
            return formatter.format(track)

    def on_iter_next(self, rowref):
        rowref = rowref+1
        if rowref < len(self.playlist):
            return rowref
        else:
            return None

    def on_iter_children(self, parent):
        if rowref:
            return None
        try:
            return self.playlist[0]
        except IndexError:
            return None

    def on_iter_has_child(self, rowref):
        return False

    def on_iter_n_children(self, rowref):
        if rowref:
            return 0
        return len(self.playlist)

    def on_iter_nth_child(self, parent, n):
        if parent:
            return None
        try:
            return self.playlist[n]
        except IndexError:
            return None

    def on_iter_parent(self, child):
        return None


    ### Event callbacks to keep the model in sync with the playlist ###

    def on_tracks_added(self, typ, playlist, tracktups):
        for idx, tr in tracktups:
            self.row_inserted((idx,), self.get_iter((idx,)))

    def on_tracks_removed(self, typ, playlist, tracktups):
        tracktups.reverse()
        for idx, tr in tracktups:
            self.row_deleted((idx,))

    def on_pos_changed(self, typ, playlist, pos):
        for p in pos:
            if p < 0:
                continue
            path = (p,)
            try:
                iter = self.get_iter(path)
            except ValueError:
                continue
            self.row_changed(path, iter)

    def on_playback_state_change(self, typ, player_obj, tr):
        path = (self.playlist.current_pos,)
        try:
            iter = self.get_iter(path)
        except ValueError:
            return
        self.row_changed(path, iter)


class Playlist(object):
    shuffle_modes = ['disabled', 'track', 'album']
    shuffle_mode_names = [_('Shuffle Off'),
            _('Shuffle Tracks'), _('Shuffle Albums')]
    repeat_modes = ['disabled', 'all', 'track']
    repeat_mode_names = [_('Repeat Off'), _('Repeat All'), _('Repeat One')]
    dynamic_modes = ['disabled', 'enabled']
    dynamic_mode_names = [_('Dynamic Off'), _('Dynamic On')]
    # TODO: how do we document properties/events in sphinx?
    """

        PROPERTIES:
            name: playlist name. read/write.

        EVENTS: (all events are synchronous)
            playlist_tracks_added
                fired: after tracks are added
                data: list of tuples of (index, track)
            playlist_tracks_removed
                fired: after tracks are removed
                data: list of tuples of (index, track)
            playlist_current_pos_changed
            playlist_shuffle_mode_changed
            playlist_random_mode_changed
            playlist_dynamic_mode_changed
    """
    save_attrs = ['shuffle_mode', 'repeat_mode', 'dynamic_mode',
            'current_pos', 'name']
    __playlist_format_version = [2, 0]
    def __init__(self, name, initial_tracks=[]):
        self.__tracks = []
        for tr in initial_tracks:
            if not isinstance(tr, trax.Track):
                raise ValueError, "Need trax.Track object, got %s"%repr(type(x))
            self.__tracks.append(tr)
        self.__shuffle_mode = self.shuffle_modes[0]
        self.__repeat_mode = self.repeat_modes[0]
        self.__dynamic_mode = self.dynamic_modes[0]

        # dirty: any change that would alter the on-disk
        #   representation should set this
        # needs_save: changes to list content should set this.
        #   Determines when the 'unsaved' indicator is shown to the user.
        self.__dirty = False
        self.__needs_save = False
        self.__name = name
        self.__current_pos = -1
        self.__spat_pos = -1

        # FIXME: this is not ideal since duplicate tracks are not
        # weighted appropriately when shuffling, however without a
        # proper api for reordering this is basically impossible to fix.
        self.__tracks_history = collections.deque()

    ### playlist-specific API ###

    def _set_name(self, name):
        self.__name = name
        self.__needs_save = self.__dirty = True
        event.log_event_sync("playlist_name_changed", self, name)

    name = property(lambda self: self.__name, _set_name)
    dirty = property(lambda self: self.__dirty)

    def clear(self):
        del self[:]

    def get_current_pos(self):
        return self.__current_pos

    def set_current_pos(self, pos):
        oldpos = self.__current_pos
        self.__current_pos = pos
        self.__dirty = True
        event.log_event_sync("playlist_current_pos_changed", self, (pos, oldpos))

    current_pos = property(get_current_pos, set_current_pos)

    def get_spat_pos(self):
        return self.__spat_pos

    def set_spat_pos(self, pos):
        oldpos = self.__spat_pos
        self.__spat_pos = pos
        self.__dirty = True
        event.log_event_sync("playlist_spat_pos_changed", self, (pos, oldpos))

    spat_pos = property(get_spat_pos, set_spat_pos)

    def get_current(self):
        return self.__tracks[self.current_pos]

    current = property(get_current)

    def __next_random_track(self, mode="track"):
        """
            Returns a valid next track if shuffle is activated based
            on random_mode
        """
        if mode == "album":
            # TODO: we really need proper album-level operations in
            # xl.trax for this
            try:
                # Try and get the next track on the album
                # NB If the user starts the playlist from the middle
                # of the album some tracks of the album remain off the
                # tracks_history, and the album can be selected again
                # randomly from its first track
                curr = self.current
                t = [ x for i, x in enumerate(self) \
                    if x.get_tag_raw('album') == curr.get_tag_raw('album') \
                    and i > self.current_pos ]
                t = trax.sort_tracks(['discnumber', 'tracknumber'], t)
                return t[0]

            except IndexError: #Pick a new album
                t = [ x for x in self \
                        if x not in self.__tracks_history ]
                albums = []
                for x in t:
                    if not x.get_tag_raw('album') in albums:
                        albums.append(x.get_tag_raw('album'))

                album = random.choice(albums)
                t = [ x for x in self.ordered_tracks \
                        if x.get_tag_raw('album') == album ]
                t = trax.sort_tracks(['tracknumber'], t)
                return t[0]
        else:
            return random.choice([ x for x in self \
                    if x not in self.__tracks_history])

    def next(self):
        repeat_mode = self.repeat_mode
        shuffle_mode = self.shuffle_mode
        if self.current_pos == self.spat_pos:
            self.spat_pos = -1
            return None

        if repeat_mode == 'track':
            return self.current
        else:
            next = None
            if shuffle_mode != 'disabled':
                curr = self.current
                if curr is not None:
                    self.__tracks_history.append(curr)
                next = self.__next_random_track(shuffle_mode)
                if next is not None:
                    self.current_pos = self.index(next)
            else:
                try:
                    next = self[self.current_pos+1]
                    self.current_pos += 1
                except IndexError:
                    next = None
                    self.current_pos = -1

            if repeat_mode == 'all':
                if next is None:
                    self.__tracks_history = []
                    if len(self) > 0:
                        return self.next()

            return next

    def prev(self):
        repeat_mode = self.repeat_mode
        shuffle_mode = self.shuffle_mode
        if repeat_mode == 'track':
            return self.current

        if shuffle_mode != 'disabled':
            try:
                prev = self.__tracks_history[-1]
            except IndexError:
                return self.get_current()
            self.__tracks_history = self.__tracks_history[:-1]
            self.current_pos = self.index(prev) #FIXME
        else:
            pos = self.current_pos - 1
            if pos < 0:
                if repeat_mode == 'all':
                    pos = len(self) - 1
                else:
                    pos = 0
            self.current_pos = pos
        return self.get_current()

    ### track advance modes ###
    # This code may look a little overkill, but it's this way to
    # maximize forwards-compatibility. get_ methods will not overwrite
    # currently-set modes which may be from a future version, while set_
    # methods explicitly disallow modes not supported in this version.
    # This ensures that 1) saved modes are never clobbered unless a
    # known mode is to be set, and 2) the values returned in _mode will
    # always be supported in the running version.

    def get_shuffle_mode(self):
        if self.__shuffle_mode in self.shuffle_modes:
            return self.__shuffle_mode
        else:
            return self.shuffle_modes[0]

    def set_shuffle_mode(self, mode):
        if mode not in self.shuffle_modes:
            raise TypeError, "Shuffle mode %s is invalid" % mode
        else:
            if mode == 'disabled':
                self.__tracks_history = []
            self.__dirty = True
            self.__shuffle_mode = mode
            event.log_event_sync("playlist_shuffle_mode_changed", self, mode)

    shuffle_mode = property(get_shuffle_mode, set_shuffle_mode)

    def get_repeat_mode(self):
        if self.__repeat_mode in self.repeat_modes:
            return self.__repeat_mode
        else:
            return self.repeat_modes[0]

    def set_repeat_mode(self, mode):
        if mode not in self.repeat_modes:
            raise TypeError, "Repeat mode %s is invalid" % mode
        else:
            self.__dirty = True
            self.__repeat_mode = mode
            event.log_event_sync("playlist_repeat_mode_changed", self, mode)

    repeat_mode = property(get_repeat_mode, set_repeat_mode)

    def get_dynamic_mode(self):
        if self.__dynamic_mode in self.dynamic_modes:
            return self.__dynamic_mode
        else:
            return self.dynamic_modes[0]

    def set_dynamic_mode(self, mode):
        if mode not in self.dynamic_modes:
            raise TypeError, "Dynamic mode %s is invalid" % mode
        else:
            self.__dirty = True
            self.__dynamic_mode = mode
            event.log_event_sync("dynamic_repeat_mode_changed", self, mode)

    dynamic_mode = property(get_dynamic_mode, set_dynamic_mode)

    def randomize(self):
        # TODO: add support for randomizing a subset of the list?
        trs = self[:]
        random.shuffle(trs)
        self[:] = trs


    # TODO[0.4?]: drop our custom disk playlist format in favor of an
    # extended XSPF playlist (using xml namespaces?).

    # TODO: add timeout saving support. 5-10 seconds after last change,
    # perhaps?

    def save_to_location(self, location):
        if os.path.exists(location):
            f = open(location + ".new", "w")
        else:
            f = open(location, "w")
        for tr in self.__tracks:
            buffer = tr.get_loc_for_io()
            # write track metadata
            meta = {}
            items = ('artist', 'album', 'tracknumber',
                    'title', 'genre', 'date')
            for item in items:
                value = tr.get_tag_raw(item)
                if value is not None:
                    meta[item] = value[0]
            buffer += '\t%s\n' % urllib.urlencode(meta)
            try:
                f.write(buffer.encode('utf-8'))
            except UnicodeDecodeError:
                continue

        f.write("EOF\n")
        for item in self.save_attrs:
            val = getattr(self, item)
            try:
                strn = settings.MANAGER._val_to_str(val)
            except ValueError:
                strn = ""

            f.write("%s=%s\n"%(item,strn))
        f.close()
        if os.path.exists(location + ".new"):
            os.remove(location)
            os.rename(location + ".new", location)
        self.__needs_save = self.__dirty = False

    def load_from_location(self, location):
        # note - this is not guaranteed to fire events when it sets
        # attributes. It is intended ONLY for initial setup, not for
        # reloading a playlist inline.
        f = None
        for loc in [location, location+".new"]:
            try:
                f = open(loc, 'r')
                break
            except:
                pass
        if not f:
            return
        locs = []
        while True:
            line = f.readline()
            if line == "EOF\n" or line == "":
                break
            locs.append(line.strip())
        items = {}
        while True:
            line = f.readline()
            if line == "":
                break
            item, strn = line[:-1].split("=",1)
            val = settings.MANAGER._str_to_val(strn)
            items[item] = val

        ver = items.get("__playlist_format_version", [1])
        if ver[0] == 1:
            if items.get("repeat_mode") == "playlist":
                items['repeat_mode'] = "all"
        elif ver[0] > self.__playlist_format_version[0]:
            raise IOError, "Cannot load playlist, unknown format"
        elif ver > self.__playlist_format_version:
            logger.warning("Playlist created on a newer Exaile version, some attributes may not be handled.")
        for item, val in items.iteritems():
            if item in self.save_attrs:
                setattr(self, item, val)
        f.close()

        trs = []

        for loc in locs:
            meta = None
            if loc.find('\t') > -1:
                splitted = loc.split('\t')
                loc = "\t".join(splitted[:-1])
                meta = splitted[-1]

            tr = None
            tr = trax.Track(uri=loc)

            # readd meta
            if not tr: continue
            if not tr.is_local() and meta is not None:
                meta = cgi.parse_qs(meta)
                for k, v in meta.iteritems():
                    tr.set_tag_raw(k, v[0], notify_changed=False)

            trs.append(tr)

        self.__tracks = trs

    ### view API ###

    # how views need to work:
    #   when the following methods are called, they do NOT affect the
    #   underlying order, only the 'apparent' order. HOWEVER, if the
    #   structure is modified when a view is in effect, the view
    #   replaces the current order.

    def reverse(self):
        # reverses current view
        pass

    def sort(self):
        # sorts current view
        pass

    # filter acts like a view method, EXCEPT that when it is active, it
    # is illegal to add or reorder items in the playlist. attempting to do
    # so will raise a <TODO>Exception. Deletion while a filter is active
    # is allowed, however items deleted must be visible under the
    # filter.
    # GUI should disable (grey out, beocme insensitive to DnD, etc.)
    # appropriate actions when these conditions are in effect.

    def filter(self):
        pass


    ### list-like API methods ###
    # parts of this section are taken from
    # http://code.activestate.com/recipes/440656-list-mixin/

    def __len__(self):
        return len(self.__tracks)

    def __contains__(self, track):
        return self.__tracks.__contains__(track)

    def __tuple_from_slice(self, i):
        """
            Get (start, end, step) tuple from slice object.
        """
        (start, end, step) = i.indices(len(self))
        if i.step == None:
            step = 1
        return (start, end, step)

    def __getitem__(self, i):
        return self.__tracks.__getitem__(i)

    def __setitem__(self, i, value):
        oldtracks = self.__getitem__(i)
        removed = []
        added = []
        if isinstance(i, slice):
            for x in value:
                if not isinstance(x, trax.Track):
                    raise ValueError, "Need trax.Track object, got %s"%repr(type(x))
            (start, end, step) = self.__tuple_from_slice(i)
            if step != 1:
                if len(value) != len(oldtracks):
                    raise ValueError, "Extended slice assignment must match sizes."
                self.__tracks.__setitem__(i, value)
                removed = zip(range(start, end, step), oldtracks)
            else:
                self.__tracks.__setitem__(i, value)
                removed = zip(range(start, end, step), oldtracks)
                end = start + len(value)
            added = zip(range(start, end, step), value)
        else:
            if not isinstance(value, trax.Track):
                raise ValueError, "Need trax.Track object, got %s"%repr(type(x))
            self.__tracks[i] = value
            removed = [(i, oldtracks)]
            added = [(i, value)]
        curpos = self.current_pos
        spatpos = self.spat_pos
        for idx, tr in removed[::-1]:
            if curpos > idx:
                curpos -= 1
            if spatpos > idx:
                spatpos -= 1
        for idx, tr in added:
            if curpos > idx:
                curpos += 1
            if spatpos > idx:
                spatpos += 1
        self.spat_pos = spatpos
        self.current_pos = curpos
        event.log_event_sync('playlist_tracks_removed', self, removed)
        event.log_event_sync('playlist_tracks_added', self, added)
        self.__needs_save = self.__dirty = True

    def __delitem__(self, i):
        if isinstance(i, slice):
            (start, end, step) = self.__tuple_from_slice(i)
        oldtracks = self.__getitem__(i)
        self.__tracks.__delitem__(i)
        removed = []
        if isinstance(i, slice):
            removed = zip(xrange(start, end, step), oldtracks)
        else:
            removed = [(i, oldtracks)]
        curpos = self.current_pos
        spatpos = self.spat_pos
        for idx, tr in removed[::-1]:
            if curpos > idx:
                curpos -= 1
            if spatpos > idx:
                spatpos -= 1
        self.spat_pos = spatpos
        self.current_pos = curpos
        event.log_event_sync('playlist_tracks_removed', self, removed)
        self.__needs_save = self.__dirty = True

    def append(self, other):
        self[len(self):len(self)] = [other]

    def extend(self, other):
        self[len(self):len(self)] = other

    def count(self, other):
        return self.__tracks.count(other)

    def index(self, item, start=0, end=None):
        if end is None:
            return self.__tracks.index(item, start)
        else:
            return self.__tracks.index(item, start, end)




