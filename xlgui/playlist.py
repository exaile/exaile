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

import copy
import logging
import os
import os.path
import math
import urllib

import gobject
import gtk
import gtk.gdk
import pango

from xlgui import guiutil, menu, plcolumns
from xlgui import rating
from xlgui.plcolumns import *
from xl import playlist, event, collection, xdg, settings, trax
from xl.nls import gettext as _

logger = logging.getLogger(__name__)

class Playlist(gtk.VBox):
    """
        Represents an xl.playlist.Playlist in the GUI

        If you want to add a possible column to the display of each playlist,
        just define a class for it in plcolumns.py and the rest will be done
        automatically
    """
    COLUMNS = plcolumns.COLUMNS
    column_by_display = {}
    for col in COLUMNS.values():
        column_by_display[col.display] = col

    default_columns = ['tracknumber', 'title', 'album', 'artist', '__length']
    menu_items = {}
    _is_drag_source = False

    __gsignals__ = {
        'playlist-content-changed': (gobject.SIGNAL_RUN_LAST, None, (bool,)),
        'customness-changed': (gobject.SIGNAL_RUN_LAST, None, (bool,)),
        'track-count-changed': (gobject.SIGNAL_RUN_LAST, None, (int,)),
        'column-settings-changed': (gobject.SIGNAL_RUN_LAST, None, ()),
    }
    def __init__(self, main, queue, pl, _column_ids=[],
        _is_queue=False):
        """
            Initializes the playlist

            @param pl: the playlist.Playlist instace to represent
        """
        gtk.VBox.__init__(self)

        self.exaile = main.controller.exaile

        self.main = main
        self.player = self.exaile.player
        self.queue = queue
        self.search_keyword = ''
        self.builder = main.builder
        self._initial_column_ids = _column_ids
        self._is_queue = _is_queue

        self._redraw_queue = []
        self._redraw_id = 0

        if not _is_queue:
            self.playlist = copy.copy(pl)
            self.playlist.ordered_tracks = pl.ordered_tracks[:]
        else:
            self.playlist = pl

        # see plcolumns.py for more information on the columns menu
        if not Playlist.menu_items:
            plcolumns.setup_menu(self.builder.get_object('columns_menu_menu'),
                Playlist.menu_items)

        self._setup_tree()
        self._setup_col_menus()
        self._setup_columns()
        self._setup_events()
        self._set_tracks(self.playlist.get_tracks())

        self.menu = menu.PlaylistMenu(self, main.playlist_manager)
        self.menu.connect('rating-set', self.set_rating)
        self.menu.connect('remove-items', lambda *e:
            self.remove_selected_tracks())
        self.menu.connect('queue-items', lambda *e:
            self.queue_selected_tracks())
        self.menu.connect('properties', lambda *e:
            self.properties_dialog())

        self.show_all()

        # watch the playlist for changes
        event.add_callback(self.on_add_tracks, 'tracks_added', self.playlist)
        event.add_callback(self.on_remove_tracks, 'tracks_removed',
            self.playlist)
        event.add_callback(self.refresh_changed_tracks, 'track_tags_changed')
        event.add_callback(self.on_stop_track, 'stop_track')

    def properties_dialog(self):
        """
            Shows the properties dialog
        """
        from xlgui import properties
        tracks = self.get_selected_tracks()
        selected = None
        if len(tracks) == 1:
            tracks = self.get_all_tracks()
            selected = self.get_cursor()

        if not tracks:
            return False

        dialog = properties.TrackPropertiesDialog(self.main.window,
            tracks, selected)
        #result = dialog.run()
        #dialog.hide()

        #return True

    def refresh_changed_tracks(self, type, track, tag):
        """
            Called when a track is known to have a tag changed
        """
        if not track or not \
            settings.get_option('gui/sync_on_tag_change', True) or not\
            tag in self.get_column_ids():
            return

        if self._redraw_id:
            gobject.source_remove(self._redraw_id)
        self._redraw_queue.append(track)
        self._redraw_id = gobject.timeout_add(100,
                self.__refresh_changed_tracks)

    def __refresh_changed_tracks(self):
        tracks = {}
        for tr in self._redraw_queue:
            tracks[tr.get_loc_for_io()] = tr
        self._redraw_queue = []

        selection = self.list.get_selection()
        info = selection.get_selected_rows()

        it = self.model.get_iter_first()
        while it:
            loc = self.model.get_value(it, 0).get_loc_for_io()
            if loc in tracks:
                self.update_iter(it, tracks[loc])
            it = self.model.iter_next(it)
        self.list.queue_draw()

        if info:
            for path in info[1]:
                selection.select_path(path)

    def selection_changed(self):
        trs = self.get_selected_tracks()
        self.builder.get_object('track_properties_item').set_sensitive(bool(trs))

    def on_stop_track(self, event, queue, stop_track):
        """
            Makes sure to select the next track in the
            playlist after playback has stopped due to SPAT
        """
        next_track = self.playlist.next()
        next_index = self.playlist.index(next_track)
        self.list.set_cursor(next_index)

    def queue_selected_tracks(self):
        """
            Toggles queue of selected tracks
        """
        trs = self.get_selected_tracks()

        queue_tracks = self.queue.ordered_tracks
        for track in trs:
            if track in queue_tracks:
                queue_tracks.remove(track)
            else:
                queue_tracks.append(track)

        self.emit('track-count-changed', len(self.playlist))
        self.list.queue_draw()

    def set_rating(self, widget, rating):
        trs = self.get_selected_tracks()
        steps = settings.get_option('miscellaneous/rating_steps', 5)
        r = float((100.0*rating)/steps)
        for track in trs:
            track.set_rating(rating)
        event.log_event('rating_changed', self, r)

    def get_column_ids(self):
        column_ids = None
        if settings.get_option('gui/trackslist_defaults_set', False):
            ids = settings.get_option("gui/columns", [])
            # Don't add invalid columns.
            all_ids = frozenset(self.COLUMNS.iterkeys())
            column_ids = frozenset(id for id in ids if id in all_ids)

        if not column_ids:
            # Use default.
            ids = self.default_columns
            settings.set_option('gui/trackslist_defaults_set', True)
            settings.set_option('gui/columns', ids)
            column_ids = frozenset(ids)
        return column_ids

    def _setup_col_menus(self):
        """
            Sets up the column menus (IE, View->Column->Track, etc)
        """
        self.resizable_cols = self.builder.get_object('col_resizable_item')
        self.not_resizable_cols = \
            self.builder.get_object('col_not_resizable_item')
        if not self.resizable_cols and not self.not_resizable_cols:
            return # potentially dangerous if someone breaks the gladefile...
        self.resizable_cols.set_active(
                settings.get_option('gui/resizable_cols', False))
        self.not_resizable_cols.set_active(not \
            settings.get_option('gui/resizable_cols', False))
        self.resizable_cols.connect('activate', self.activate_cols_resizable)
        # activate_cols_resizable will be called by resizable_cols anyway, no need to call it twice
        #self.not_resizable_cols.connect('activate',
        #    self.activate_cols_resizable)

        column_ids = self.get_column_ids()
        if settings.get_option('gui/trackslist_defaults_set', False):
            ids = settings.get_option("gui/columns", [])
            # Don't add invalid columns.
            all_ids = frozenset(self.COLUMNS.iterkeys())
            column_ids = frozenset(id for id in ids if id in all_ids)

        if not column_ids:
            # Use default.
            ids = self.default_columns
            settings.set_option('gui/trackslist_defaults_set', True)
            settings.set_option('gui/columns', ids)
            column_ids = frozenset(ids)

        if not self._is_queue:
            for col_struct in self.COLUMNS.itervalues():
                try:
                    menu = Playlist.menu_items[col_struct.id]
                except KeyError:
                    logger.warning("No such column: %s" % col_struct.id)
                    continue

                menu.set_active(col_struct.id in column_ids)
                menu.connect('activate', self.change_column_settings,
                    ('gui/columns', col_struct))

    def search(self, keyword):
        """
            Filter the playlist with a keyword
        """
        trs = self.playlist.filter(keyword)
        self._set_tracks(trs)
        self.search_keyword = keyword

    def change_column_settings(self, item, data):
        """
            Changes column view settings
        """
        if self._is_queue: return
        pref, col_struct = data
        id = col_struct.id

        column_ids = list(settings.get_option(pref, []))
        if item.get_active():
            if id not in column_ids:
                logger.info("Adding %(column_id)s column to %(preference)s" %
                    {'column_id' : id, 'preference' : pref})
                column_ids.append(id)
        else:
            if col_struct.id in column_ids:
                logger.info("Removing %(column_id)s column from %(preference)s" %
                    {'column_id' : id, 'preference' : pref})
                column_ids.remove(id)
        settings.set_option(pref, column_ids)
        self.emit('column-settings-changed')

    def activate_cols_resizable(self, widget, event=None):
        """
            Called when the user chooses whether or not columns can be
            resizable
        """
        settings.set_option('gui/resizable_cols', widget.get_active())
        self.emit('column-settings-changed')

    def update_col_settings(self):
        """
            Updates the settings for a specific column
        """
        selection = self.list.get_selection()
        info = selection.get_selected_rows()
        # grab the first visible raw of the treeview
        firstpath = self.list.get_path_at_pos(4,4)
        topindex = None
        if firstpath:
            topindex = firstpath[0][0]

        self.list.disconnect(self.changed_id)
        columns = self.list.get_columns()
        for col in columns:
            self.list.remove_column(col)

        self._setup_columns()
        self._set_tracks(self.playlist.get_tracks())
        self.list.queue_draw()

        if firstpath:
            self.list.scroll_to_cell(topindex)
        if info:
            for path in info[1]:
                selection.select_path(path)

    def on_remove_tracks(self, type, playlist, info):
        """
            Called when someone removes tracks from the contained playlist
        """
        start = info[0]
        end = info[1]
        paths = [(x,) for x in range(start, end-1)]
        self.remove_rows(paths, playlist=False)

    def on_add_tracks(self, type, playlist, trs, scroll=False):
        """
            Called when someone adds tracks to the contained playlist
        """
        for track in trs:
            self._append_track(track)

        newlength = len(self.playlist)
        self.emit('track-count-changed', newlength)
        range = self.list.get_visible_range()
        offset = 0
        if range:
            offset = range[1][0] - range[0][0]

        if trs and scroll:
            try:
                if offset > newlength:
                    self.list.scroll_to_cell(self.playlist.index(tracks[-1]))
                else:
                    self.list.scroll_to_cell(self.playlist.index(tracks[offset]))
            except IndexError:
                self.list.scroll_to_cell(self.playlist.index(tracks[0]))
        self.set_needs_save(True)

    def _set_tracks(self, trs):
        """
            Sets the tracks that this playlist should display
        """
        self.model.clear()

        for track in trs:
            self._append_track(track)

        self.list.set_model(self.model)
        self.emit('track-count-changed', len(self.playlist))

        #Whenever we reset the model of the list
        #we need to mark the search column again
        self._set_search_column()

    def _set_search_column(self):
        count = 3
        search_column = settings.get_option("gui/search_column", "Title")
        for col in self.list.get_columns():
            if col.get_title().decode('utf-8') == search_column:
                self.list.set_search_column(count)
            count = count + 1

    def _get_ar(self, song):
        """
            Creates the array to be added to the model in the correct order
        """
        ar = [song, None, None]
        for field in self.append_map:
            value = song.get_tag_display(field, artist_compilations=False)
            if value is None:
                value = ''
            ar.append(value)
        return ar

    def _append_track(self, track):
        """
            Adds a track to this view
        """
        ar = self._get_ar(track)
        self.model.append(ar)

    def get_cursor(self):
        """
            Returns the track below the cursor
        """
        track_id = self.list.get_cursor()[0][0]
        return track_id

    def get_selected_track(self):
        """
            Returns the currently selected track
        """
        trs = self.get_selected_tracks()
        if not trs:
            return None
        else:
            return trs[0]

    def get_selected_tracks(self):
        """
            Gets the selected tracks in the tree view
        """
        selection = self.list.get_selection()
        (model, paths) = selection.get_selected_rows()
        songs = []
        for path in paths:
            iter = self.model.get_iter(path)
            song = self.model.get_value(iter, 0)
            songs.append(song)

        return songs

    def get_all_tracks(self):
        """
            Gets the all tracks in the tree view
        """
        return self.playlist.get_tracks()


    def get_tracks_rating(self):
        """
            Returns the rating of the selected tracks in the tree view
            Returns 0 if not all tracks have the same rating or if the selection
            is too big
        """
        rating = 0
        selection = self.list.get_selection()
        (model, paths) = selection.get_selected_rows()

        if paths != None and len(paths) > 0:
            iter = self.model.get_iter(paths[0])
            song = self.model.get_value(iter, 0)
            rating = song.get_rating ()
        else:
            return 0 # no tracks

        if rating == 0:
            return 0 # if first song has 0 as a rating, we know the final result

        if len(paths) > settings.get_option('miscellaneous/rating_widget_tracks_limit', 100):
            return 0 # too many tracks, skipping

        for path in paths:
            iter = self.model.get_iter(path)
            song = self.model.get_value(iter, 0)
            if song.get_rating() != rating:
                return 0 # different ratings

        return rating # only one rating in the tracks, returning it


    def update_iter(self, iter, song):
        """
            Updates the track at "iter"
        """
        ar = self._get_ar(song)
        self.model.insert_after(iter, ar)
        self.model.remove(iter)

    def refresh_row(self, song):
        """
            Refreshes the text for the specified row
        """
        selection = self.list.get_selection()
        model, paths = selection.get_selected_rows()
        iter = self.model.get_iter_first()
        if not iter: return
        while True:
            check = self.model.get_value(iter, 0)
            if not check: break
            if check == song or \
                    check.get_loc_for_io() == song.get_loc_for_io():
                self.update_iter(iter, song)
                break
            iter = self.model.iter_next(iter)
            if not iter: break

        self.list.queue_draw()

    def on_row_activated(self, *e):
        """
            Called when the user double clicks on a track
        """
        if self._is_queue: return
        track = self.get_selected_track()
        if not track: return

        index = self.playlist.index(track)
        self.playlist.set_current_pos(index)
        self.queue.play(track=track)
        self.queue.set_current_playlist(self.playlist)

    def on_closing(self):
        """
            Called by the NotebookTab when this playlist
            is about to be closed.  Handles such things
            as confirming a close on a modified playlist

            @return: True if we should continue to close,
                False otherwise
        """
        # Before closing check whether the playlist
        # changed, and if it did give the user an option to do something
        if self.get_needs_save():
            try:
                current_tracks = self.playlist.get_tracks()
                original_tracks = self.main.playlist_manager.get_playlist \
                    (self.playlist.get_name()).get_tracks()
                dirty = False
                if len(current_tracks) != len(original_tracks):
                    dirty = True
                else:
                    for i in range(0, len(original_tracks)):
                        o_track = original_tracks[i]
                        c_track = current_tracks[i]
                        if o_track != c_track:
                            dirty = True
                            break

                if dirty == True and self.playlist.get_is_custom() \
                    and settings.get_option('playlist/ask_save', True):
                    dialog = ConfirmCloseDialog(self.playlist.get_name())
                    result = dialog.run()
                    if result == 110:
                        # Save the playlist then close
                        self.set_needs_save(False)
                        self.main.playlist_manager.save_playlist(
                            self.playlist, overwrite = True)
                        return True
                    elif result == gtk.RESPONSE_CANCEL:
                        return False
            except ValueError:
                # Usually means that it was a smart playlist
                pass
        return True

    def button_press(self, button, event):
        """
            Called when the user clicks on the playlist
        """
        if self._is_queue: return
        if event.button == 3:
            tab = self.main.get_current_tab()
            (x, y) = event.get_coords()
            path = self.list.get_path_at_pos(int(x), int(y))
            if path:
                self.menu.popup(event)
            else:
                tab.menu.popup(None, None, None, event.button, event.time)
            if len(self.get_selected_tracks()) > 1: return True
        return False

    def _setup_events(self):
        self.list.connect('key-press-event', self.key_pressed)
        self.list.connect('button-release-event', self.update_rating)

    def key_pressed(self, widget, event):
        if event.keyval == gtk.keysyms.Delete:
            self.remove_selected_tracks()

        return False

    def _setup_tree(self):
        """
            Sets up the TreeView for this Playlist
        """
        self.list = guiutil.DragTreeView(self)
        self.list.set_rules_hint(True)
        self.list.set_enable_search(True)
        self.list.connect('row-activated', self.on_row_activated)

        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.list)
        self.pack_start(self.scroll, True, True)
        self.scroll.show_all()

        selection = self.list.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        selection.connect('changed', lambda s: self.selection_changed())

        img = self.list.render_icon('gtk-media-play',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.playimg = img.scale_simple(18, 18,
            gtk.gdk.INTERP_BILINEAR)
        img = self.list.render_icon('gtk-media-pause',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.pauseimg = img.scale_simple(18, 18,
            gtk.gdk.INTERP_BILINEAR)
        img = self.list.render_icon('gtk-stop',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.stopimg = img.scale_simple(12, 12,
            gtk.gdk.INTERP_BILINEAR)

    def column_changed(self, *e):
        """
            Called when columns are reordered
        """
        if self._is_queue: return
        self.list.disconnect(self.changed_id)
        cols = []
        for col in self.list.get_columns():
            cols.append(self.column_by_display[col.get_title().
                                               decode('utf-8')].id)
            self.list.remove_column(col)

        settings.set_option('gui/columns', cols)
        self._setup_columns()
        self._set_tracks(self.playlist.get_tracks())

    def get_needs_save(self):
        return self.playlist.get_needs_save()

    def set_needs_save(self, val=True):
        self.playlist.set_needs_save(val)
        self.emit('playlist-content-changed', self.get_needs_save())

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
            Called when data is recieved
        """
        if self.playlist.ordered_tracks:
            curtrack = self.playlist.get_current()
        else:
            curtrack = None

        # Remove callbacks so they are not fired when we perform actions
        event.remove_callback(self.on_add_tracks, 'tracks_added', self.playlist)
        event.remove_callback(self.on_remove_tracks, 'tracks_removed',
            self.playlist)

        self.list.unset_rows_drag_dest()
        self.list.drag_dest_set(gtk.DEST_DEFAULT_ALL,
            self.list.targets,
            gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)

        locs = list(selection.get_uris())

        if context.action != gtk.gdk.ACTION_MOVE:
            pass

        try:
            drop_info = tv.get_dest_row_at_pos(x, y)

            if drop_info:
                path, position = drop_info
                iter = self.model.get_iter(path)
                if (position == gtk.TREE_VIEW_DROP_BEFORE or
                    position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
                    first = False
                else:
                    first = True
        except AttributeError:
            drop_info = None
            pass

        (trs, playlists) = self.list.get_drag_data(locs)

        (column, descending) = self.get_sort_by()
        trs = trax.sort_tracks(self.return_order_tags(column), trs, reverse=descending)

        # Determine what to do with the tracks
        # by default we load all tracks.
        # TODO: should we load tracks we find in the collection from there??
        for track in trs:
            if not drop_info:
                self._append_track(track)
            else:
                if not first:
                    first = True
                    ar = self._get_ar(track)
                    if self.model.iter_is_valid(iter):
                        iter = self.model.insert_before(iter, ar)
                    else:
                        iter = self.model.append(ar)
                else:
                    ar = self._get_ar(track)
                    path = self.model.get_path(iter)
                    if self.model.iter_is_valid(iter):
                        iter = self.model.insert_after(iter, ar)
                    else:
                        iter = self.model.append(ar)

        Playlist._is_drag_source = False
        if context.action == gtk.gdk.ACTION_MOVE:
            # On a move action the second True makes the
            # drag_data_delete function called
            context.finish(True, True, etime)
        else:
            context.finish(True, False, etime)

        iter = self.model.get_iter_first()
        if not iter:
            # Do we need to reactivate the callbacks when this happens?
            gobject.idle_add(self.add_track_callbacks)
            return

        self.playlist.add_tracks(trs)

        # Re add all of the tracks so that they
        # become ordered
        iter = self.model.get_iter_first()
        if not iter:
            gobject.idle_add(self.add_track_callbacks)
            return

        self.playlist.ordered_tracks = []
        while True:
            track = self.model.get_value(iter, 0)
            self.playlist.ordered_tracks.append(track)
            iter = self.model.iter_next(iter)
            if not iter: break

        if trs:
            self.set_needs_save(True)

        gobject.idle_add(self.add_track_callbacks)
        self.emit('track-count-changed', len(self.playlist))

        if curtrack is not None:
            index = self.playlist.index(curtrack)
            self.playlist.set_current_pos(index)

    def add_track_callbacks(self):
        """
            Adds callbacks for added and removed tracks.
        """
        event.add_callback(self.on_add_tracks, 'tracks_added', self.playlist)
        event.add_callback(self.on_remove_tracks, 'tracks_removed',
            self.playlist)

    def _remove_selected_nodes(self):
        """
            Simply removes the selected nodes from the tree.  Does NOT remove
            tracks from the contained playlist
        """
        sel = self.list.get_selection()
        (model, paths) = sel.get_selected_rows()
        # Since we want to modify the model we make references to it
        # This allows us to remove rows without it messing up
        rows = []
        for path in paths:
            rows.append(gtk.TreeRowReference(model, path))
        for row in rows:
            iter = self.model.get_iter(row.get_path())
            #Also update the playlist we have
            track = self.model.get_value(iter, 0)
            self.model.remove(iter)

    def remove_selected_tracks(self):
        selection = self.list.get_selection()
        (model, paths) = selection.get_selected_rows()
        self.remove_rows(paths)

    def remove_rows(self, paths, playlist=True):
        if playlist:
            event.remove_callback(self.on_remove_tracks, 'tracks_removed',
                    self.playlist)
            ranges = []
            curstart = paths[0][0]
            last = curstart
            for i in paths[1:]:
                val = i[0]
                if val == last+1:
                    last += 1
                    continue
                else:
                    ranges.append((curstart, last))
                    curstart = val
                    last = val
            ranges.append((curstart, last))
            for start, end in ranges:
                self.playlist.remove_tracks(start, end)
            gobject.idle_add(event.add_callback, self.on_remove_tracks,
                'tracks_removed', self.playlist)

        iters = [self.model.get_iter(x) for x in paths]
        for row in iters:
            self.model.remove(row)

        self.list.set_cursor(paths[0][0])

        self.emit('track-count-changed', len(self.playlist))
        self.set_needs_save(True)

    def drag_data_delete(self, tv, context):
        """
            Called after a drag data operation is complete
            and we want to delete the source data
        """
        if context.drag_drop_succeeded():
            self._remove_selected_nodes()

    def drag_get_data(self, treeview, context, selection, target_id, etime):
        """
            Called when a drag source wants data for this drag operation
        """
        Playlist._is_drag_source = True

        trs = self.get_selected_tracks()
        for track in trs:
            guiutil.DragTreeView.dragged_data[track.get_loc_for_io()] = track

        locs = guiutil.get_urls_for(trs)
        selection.set_uris(locs)

    def setup_model(self, map):
        """
            Gets the array to build the two models
        """
        ar = [object, gtk.gdk.Pixbuf, gtk.gdk.Pixbuf]

        for item in map:
            ar.append(str)

        self.model = gtk.ListStore(*ar)
        self.list.set_model(self.model)

    def _setup_columns(self):
        """
            Sets up the columns for this table
        """

        self._col_count = 0

        col_ids = settings.get_option("gui/columns", [])

        if self._initial_column_ids:
            col_ids = self._initial_column_ids

        search_column = settings.get_option("gui/search_column", "Title")

        # make sure all the entries are good
        if col_ids:
            cols = []
            for col in col_ids:
                if col in self.COLUMNS:
                    cols.append(col)
            col_ids = cols

        if not col_ids:
            col_ids = self.default_columns

        self.append_map = col_ids
        self.setup_model(col_ids)

        count = 3
        first_col = True

        for col in col_ids:
            column = self.COLUMNS[col](self)
            cellr = column.renderer()

            if first_col:
                first_col = False
                pb = gtk.CellRendererPixbuf()
                pb.set_fixed_size(20, 20)
                pb.set_property('xalign', 0.0)
                stop_pb = gtk.CellRendererPixbuf()
                stop_pb.set_fixed_size(12, 12)
                col = gtk.TreeViewColumn(column.display)
                col.pack_start(pb, False)
                col.pack_start(stop_pb, False)
                col.pack_start(cellr, True)
                col.set_attributes(cellr, text=count)
                col.set_attributes(pb, pixbuf=1)
                col.set_attributes(stop_pb, pixbuf=2)
                col.set_cell_data_func(pb, self.icon_data_func)
                col.set_cell_data_func(stop_pb, self.stop_icon_data_func)
            else:
                col = gtk.TreeViewColumn(column.display, cellr, text=count)

            col.set_cell_data_func(cellr, column.data_func)
            column.set_properties(col, cellr)

            setting_name = "gui/col_width_%s" % column.id
            width = settings.get_option(setting_name,
                column.size)
            col.set_fixed_width(int(width))

            resizable = settings.get_option('gui/resizable_cols',
                False)

            if not self._is_queue:
                col.connect('clicked', self.set_sort_by)
                col.connect('notify::width', self.set_column_width)
            col.set_clickable(True)
            col.set_reorderable(True)
            col.set_resizable(False)
            col.set_sort_indicator(False)
            # hack to make sorting work right. does not sort.
            col.set_sort_order(gtk.SORT_DESCENDING)

            if not resizable:
                if column.id in ('title', 'artist', 'album', '__loc', 'genre'):
                    if column.id != 'genre':
                        col.set_expand(True)
                        col.set_fixed_width(1)
                    else:
                        col.set_fixed_width(80)
                    col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
                    cellr.set_property('ellipsize', pango.ELLIPSIZE_END)
                else:
                    col.set_sizing(gtk.TREE_VIEW_COLUMN_AUTOSIZE)
            else:
                col.set_resizable(True)
                col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)

            # Update which column to search for when columns are changed
            if column.display == search_column:
                self.list.set_search_column(count)
            col.set_widget(gtk.Label(column.display))
            col.get_widget().show()
            self.list.append_column(col)
            col.get_widget().get_ancestor(gtk.Button).connect('button_press_event',
                self.press_header)
            count = count + 1
        self.changed_id = self.list.connect('columns-changed', self.column_changed)

    def set_column_width(self, col, *e):
        """
            Called when the user resizes a column
        """
        if self._is_queue: return
        col_struct = self.column_by_display[col.get_title().decode('utf-8')]
        name = 'gui/col_width_%s' % col_struct.id
        w = col.get_width()
        if w != settings.get_option(name, -1):
            settings.set_option(name, w)

    # sort functions courtesy of listen (http://listengnome.free.fr), which
    # are in turn, courtesy of quodlibet.
    def set_sort_by(self, column):
        """
            Sets the sort column
        """
        title = column.get_title()
        for col in self.list.get_columns():
            if title == col.get_title().decode('utf-8'):
                order = column.get_sort_order()
                if order == gtk.SORT_ASCENDING:
                    order = gtk.SORT_DESCENDING
                else:
                    order = gtk.SORT_ASCENDING
                col.set_sort_indicator(True)
                col.set_sort_order(order)
            else:
                col.set_sort_indicator(False)
                col.set_sort_order(gtk.SORT_DESCENDING)

        trs = self.reorder_songs()
        self._set_tracks(trs)

        if not self.playlist.ordered_tracks: return
        try:
            curtrack = \
                self.playlist.ordered_tracks[self.playlist.get_current_pos()]
        except IndexError:
            curtrack = self.playlist.ordered_tracks[0]
        self.playlist.ordered_tracks = trs
        index = self.playlist.index(curtrack)
        self.playlist.set_current_pos(index)

    def return_order_tags(self, newtag = None):
        """
            Returns a list of tags, which sorting will be used to sort tracks
            If newtag isn't set, only returns the list, otherwise adds it to the
            head of the list and saves it into the settings
        """
        tags = ['artist', 'date', 'album', 'discnumber', 'tracknumber', 'title']

        if newtag:
            if newtag in tags:
                tags.remove (newtag)
            tags.insert (0, newtag)

        return tags

    def reorder_songs(self):
        """
            Resorts all songs
        """
        attr, reverse = self.get_sort_by()

        songs = self.playlist.search(self.search_keyword,
            tuple (self.return_order_tags (attr)))

        if reverse:
            songs.reverse()
        return songs

    def get_sort_by(self):
        """
            Gets the sort order
        """
        for col in self.list.get_columns():
            if col.get_sort_indicator():
                return (self.column_by_display[col.get_title().
                                               decode('utf-8')].id,
                    col.get_sort_order() == gtk.SORT_DESCENDING)
        return None, False

    def icon_data_func(self, col, cell, model, iter):
        """
            Sets track status (playing/paused/queued) icon
        """
        path = model.get_path(iter)
        item = model.get_value(iter, 0)
        image = None

        if path[0] == self.playlist.get_current_pos():
#        if item == self.player.current:
            if self.player.is_playing():
                image = self.playimg
            elif self.player.is_paused():
                image = self.pauseimg

        # queued items
        elif item in self.queue.ordered_tracks:
            index = self.queue.ordered_tracks.index(item)
            image = guiutil.get_text_icon(self.main.window,
                str(index + 1), 18, 18)

        cell.set_property('pixbuf', image)

    def stop_icon_data_func(self, col, cell, model, iter):
        """
            Sets "stop after this" icon
        """
        item = model.get_value(iter, 0)
        image = None
        if item == self.queue.stop_track:
            image = self.stopimg
        cell.set_property('pixbuf', image)

    def set_cell_weight(self, cell, item):
        """
            Sets a CellRendererText's "weight" property according to whether
            `item` is the currently playing track.
        """
        # Doesn't play well with multiple track instances
        # as the passed-in information doesn't let us get the index,
        # which we need to discriminate among instances.
        if item == self.player.current:
            weight = pango.WEIGHT_HEAVY
        else:
            weight = pango.WEIGHT_NORMAL
        cell.set_property('weight', weight)

    def press_header(self, widget, event):
        if event.button != 3:
            return False
        menu = self.builder.get_object('columns_menu_menu')
        menu.popup(None, None, None, event.button, event.time)
        return True

    def _print_playlist(self, banner = ''):
        """
            Debug - prints the current playlist to stdout
        """
        print banner
        trs = self.playlist.get_tracks()
        for track in trs:
            print track.get_loc_for_display()
        print '---Done printing playlist'

    def update_rating(self, w, e):
        """
            Called when the user clicks on the playlist. If the user
            clicked on rating column the rating of the selected track
            is updated.
        """
        rating_col_width = 0
        left_edge = 0
        steps = settings.get_option("miscellaneous/rating_steps", 5)
        icon_size = rating._rating_width / steps
        i = 0
        #calculate rating column size and position
        for col in self.append_map:
            gui_col = self.list.get_column(i)
            if col == "__rating":
                rating_col_width = gui_col.get_width()
                break
            else:
                left_edge = left_edge + gui_col.get_width()
            i = i + 1

        (x, y) = e.get_coords()
        #check if the click is within rating column and on a list entry
        if self.list.get_path_at_pos(int(x), int(y)) \
            and left_edge < x < left_edge + rating_col_width:
                track = self.get_selected_track()
                leftpadding = (rating_col_width - rating._rating_width) / 2
                i = int(math.ceil((x-left_edge-leftpadding)/icon_size))
                new_rating = float((100*i)/steps)
                if track.get_tag_raw('__rating') == new_rating:
                    track.set_tag_raw('__rating', 0.0)
                else:
                    track.set_tag_raw('__rating', new_rating)
                if hasattr(w, 'queue_draw'):
                    w.queue_draw()
                event.log_event('rating_changed', self, i)


class ConfirmCloseDialog(gtk.MessageDialog):
    """
        Shows the dialog to confirm closing of the playlist
    """
    def __init__(self, document_name):
        """
            Initializes the dialog
        """
        gtk.MessageDialog.__init__(self, type = gtk.MESSAGE_WARNING)

        self.set_title(_('Close %s' % document_name))
        self.set_markup(_('<b>Save changes to %s before closing?</b>') % document_name)
        self.format_secondary_text(_('Your changes will be lost if you don\'t save them'))

        self.add_buttons(_('Close Without Saving'), 100, gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                        gtk.STOCK_SAVE, 110)

    def run(self):
        self.show_all()
        response = gtk.Dialog.run(self)
        self.hide()
        return response

# vim: et sts=4 sw=4
