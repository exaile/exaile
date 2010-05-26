# -*- coding: utf-8 -*-
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

import os.path
import threading
import time
import urllib
from urllib2 import urlparse

import gio
import glib
import gobject
import gtk
import pango

from xl import (
    common,
    covers,
    event,
    playlist,
    settings,
    trax,
    xdg,
)
from xl.formatter import (
    TrackFormatter,
    TrackNumberTagFormatter,
    LengthTagFormatter
)
from xl.nls import gettext as _
from xlgui import icons, rating
import xl.main

def _idle_callback(func, callback, *args, **kwargs):
    value = func(*args, **kwargs)
    if callback and callable(callback):
        callback(value)

def idle_add(callback=None):
    """
        A decorator that will wrap the function in a glib.idle_add call

        NOTE: Although this decorator will probably work in more cases than
        the gtkrun decorator does, you CANNOT expect to get a return value
        from the function that calls a function with this decorator.  Instead,
        you must use the callback parameter.  If the wrapped function returns
        a value, it will be passed in as a parameter to the callback function.

        @param callback: optional callback that will be called when the
            wrapped function is done running
    """
    def wrap(f):
        def wrapped(*args, **kwargs):
            glib.idle_add(_idle_callback, f, callback,
                *args, **kwargs)

        return wrapped
    return wrap

def gtkrun(f):
    """
        A decorator that will make any function run in gtk threadsafe mode

        ALL CODE MODIFYING THE UI SHOULD BE WRAPPED IN THIS
    """
    raise DeprecationWarning('We no longer need to use this '
        'function for xl/event.')
    def wrapper(*args, **kwargs):
        # if we're already in the main thread and you try to run
        # threads_enter, stuff will break horribly, so test for the main
        # thread and if we're currently in it we simply run the function
        if threading.currentThread().getName() == 'MainThread':
            return f(*args, **kwargs)
        else:
            gtk.gdk.threads_enter()
            try:
                return f(*args, **kwargs)
            finally:
                gtk.gdk.threads_leave()

    wrapper.__name__ = f.__name__
    wrapper.__dict__ = f.__dict__
    wrapper.__doc__ = f.__doc__

    return wrapper

def get_workarea_size():
    """
        Returns the height and width of the work area
    """
    rootwindow = gtk.gdk.get_default_root_window()
    workarea = gtk.gdk.atom_intern('_NET_WORKAREA')

    return rootwindow.property_get(workarea)[2][2:4] # W,H

def gtk_widget_replace(widget, replacement):
    """
        Replaces one widget with another and
        places it exactly at the original position

        :param widget: The original widget
        :type widget: :class:`gtk.Widget`
        :param replacement: The new widget
        :type widget: :class:`gtk.Widget`
    """
    parent = widget.get_parent()

    try:
        position = parent.get_children().index(widget)
    except AttributeError: # None, not gtk.Container
        return
    else:
        try:
            expand, fill, padding, pack_type = parent.query_child_packing(widget)
        except: # Not gtk.Box
            pass

        parent.remove(widget)
        replacement.unparent()
        parent.add(replacement)

        try:
            parent.set_child_packing(replacement, expand, fill, padding, pack_type)
            parent.reorder_child(replacement, position)
        except AttributeError: # Not gtk.Box
            pass

        replacement.show_all()

class ScalableImageWidget(gtk.Image):
    """
        Custom resizeable image widget
    """
    def __init__(self):
        """
            Initializes the image
        """
        self.loc = ''
        gtk.Image.__init__(self)

    def set_image_size(self, width, height):
        """
            Scales the size of the image
        """
        self.size = (width, height)

    def set_image(self, image, fill=False):
        """
            Sets the image
        """
        self.loc = gio.File(image).get_path()
        self.pixbuf = gtk.gdk.pixbuf_new_from_file(self.loc)

        self._set_image(self.pixbuf, fill)

    def set_image_data(self, data, fill=False):
        if not data:
            return

        self.pixbuf = icons.MANAGER.pixbuf_from_data(data)
        self._set_image(self.pixbuf, fill)

    def _set_image(self, pixbuf, fill=False):
        width, height = self.size
        if not fill:
            origw = float(pixbuf.get_width())
            origh = float(pixbuf.get_height())
            scale = min(width / origw, height / origh)
            width = int(origw * scale)
            height = int(origh * scale)
        self.width = width
        self.height = height
        scaled = pixbuf.scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)
        self.set_from_pixbuf(scaled)

        scaled = pixbuf = None

class DragTreeView(gtk.TreeView):
    """
        A TextView that does easy dragging/selecting/popup menu
    """
    targets = [("text/uri-list", 0, 0)]
    dragged_data = dict()

    def __init__(self, container, receive=True, source=True, drop_pos=None):
        """
            Initializes the tree and sets up the various callbacks
            :param container: The container to place the TreeView into
            :param receive: True if the TreeView should receive drag events
            :param source: True if the TreeView should send drag events
            :param drop_pos: Indicates where a drop operation should occur
                    w.r.t. existing entries: 'into', 'between', or None (both).
        """
        gtk.TreeView.__init__(self)
        self.container = container

        if source:
            self.drag_source_set(
                gtk.gdk.BUTTON1_MASK, self.targets,
                gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)

        if receive:
            self.drop_pos = drop_pos
            self.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets,
                gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_DEFAULT|
                gtk.gdk.ACTION_MOVE)
            self.connect('drag_data_received',
                self.container.drag_data_received)
            self.connect('drag_data_delete',
                self.container.drag_data_delete)
        self.receive = receive
        self.dragging = False
        self.show_cover_drag_icon = True
        self.connect('drag-begin', self.on_drag_begin)
        self.connect('drag-end', self.on_drag_end)
        self.connect('drag-motion', self.on_drag_motion)
        self.connect('button-release-event', self.on_button_release)
        self.connect('button-press-event', self.on_button_press)

        if source:
            self.connect('drag-data-get', self.container.drag_get_data)
            self.drag_source_set_icon_stock(gtk.STOCK_DND)

    def get_selected_tracks(self):
        """
            Returns the currently selected tracks (stub)
        """
        pass

    def on_button_release(self, button, event):
        """
            Called when a button is released
        """
        if event.button != 1 or self.dragging:
            self.dragging = False
            return True

        if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
            return True

        selection = self.get_selection()
        selection.unselect_all()

        path = self.get_path_at_pos(int(event.x), int(event.y))

        if not path:
            return False

        selection.select_path(path[0])

    def on_drag_end(self, list, context):
        """
            Called when the dnd is ended
        """
        self.dragging = False
        self.unset_rows_drag_dest()
        self.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets,
            gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)

    def on_drag_begin(self, widget, context):
        """
            Sets the cover of dragged tracks as drag icon
        """
        self.dragging = True
        context.drag_abort(gtk.get_current_event_time())

        self._on_drag_begin(widget, context)

    @common.threaded
    def _on_drag_begin(self, widget, context):
        """
            Async call counterpart to on_drag_begin, so that cover fetching
            doesn't block dragging.
        """
        if self.show_cover_drag_icon:
            tracks = self.get_selected_tracks()
            cover_manager = covers.MANAGER
            width = height = settings.get_option('gui/cover_width', 100)

            if tracks:
                tracks = trax.util.sort_tracks(['album', 'tracknumber'], tracks)
                pixbuf = None
                first_pixbuf = None
                albums = []

                for track in tracks:
                    album = track.get_tag_raw('album', join=True)
                    if album not in albums:
                        image_data = cover_manager.get_cover(track)
                        if image_data is not None:
                            pixbuf = icons.MANAGER.pixbuf_from_data(
                                image_data, (width, height))

                            if first_pixbuf is None:
                                first_pixbuf = pixbuf
                            albums += [album]

                            if len(albums) >= 2:
                                break

                if pixbuf is not None:
                    cover_pixbuf = pixbuf

                    if len(albums) > 1:
                        # Create stacked-cover effect
                        cover_pixbuf = gtk.gdk.Pixbuf(
                            gtk.gdk.COLORSPACE_RGB,
                            True,
                            8,
                            width + 10, height + 10
                        )

                        fill_pixbuf = cover_pixbuf.subpixbuf(
                            0, 0, width + 10, height + 10)
                        fill_pixbuf.fill(0x00000000) # Fill with transparent background

                        fill_pixbuf = cover_pixbuf.subpixbuf(
                            0, 0, width, height)
                        fill_pixbuf.fill(0xccccccff)

                        if first_pixbuf != pixbuf:
                            pixbuf.copy_area(
                                0, 0, width, height,
                                cover_pixbuf,
                                5, 5
                            )
                        else:
                            fill_pixbuf = cover_pixbuf.subpixbuf(
                                5, 5, width, height)
                            fill_pixbuf.fill(0x999999ff)

                        first_pixbuf.copy_area(
                            0, 0, width, height,
                            cover_pixbuf,
                            10, 10
                        )

                    glib.idle_add(self._set_drag_cover, context, cover_pixbuf)
        else:
            if self.get_selection().count_selected_rows() > 1:
                self.drag_source_set_icon_stock(gtk.STOCK_DND_MULTIPLE)
            else:
                self.drag_source_set_icon_stock(gtk.STOCK_DND)

    def _set_drag_cover(self, context, pixbuf):
        """
            Completes drag icon setup
        """
        context.set_icon_pixbuf(pixbuf, 0, 0)

    def on_drag_motion(self, treeview, context, x, y, timestamp):
        """
            Called when a row is dragged over this treeview
        """
        if not self.receive:
            return False
        self.enable_model_drag_dest(self.targets,
            gtk.gdk.ACTION_DEFAULT)
        if self.drop_pos is None:
            return False
        info = treeview.get_dest_row_at_pos(x, y)
        if not info:
            return False
        path, pos = info
        if self.drop_pos == 'into':
            # Only allow dropping into entries.
            if pos == gtk.TREE_VIEW_DROP_BEFORE:
                pos = gtk.TREE_VIEW_DROP_INTO_OR_BEFORE
            elif pos == gtk.TREE_VIEW_DROP_AFTER:
                pos = gtk.TREE_VIEW_DROP_INTO_OR_AFTER
        elif self.drop_pos == 'between':
            # Only allow dropping between entries.
            if pos == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE:
                pos = gtk.TREE_VIEW_DROP_BEFORE
            elif pos == gtk.TREE_VIEW_DROP_INTO_OR_AFTER:
                pos = gtk.TREE_VIEW_DROP_AFTER
        treeview.set_drag_dest_row(path, pos)
        context.drag_status(context.suggested_action, timestamp)
        return True

    def on_button_press(self, button, event):
        """
            The popup menu that is displayed when you right click in the
            playlist
        """
        selection = self.get_selection()
        (x, y) = event.get_coords()
        x = int(x)
        y = int(y)
        path = self.get_path_at_pos(x, y)

        if path:
            if event.button != 3:
                if event.type == gtk.gdk._2BUTTON_PRESS:
                    self.container.button_press(button, event)

                if selection.count_selected_rows() <= 1:
                    return False
                else:
                    if selection.path_is_selected(path[0]):
                        if event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                            selection.unselect_path(path[0])
                        return True
                    elif not event.state & (gtk.gdk.SHIFT_MASK|gtk.gdk.CONTROL_MASK):
                        return True
                    return False

            if not selection.count_selected_rows():
                selection.select_path(path[0])
        return self.container.button_press(button, event)

    #TODO maybe move this somewhere else? (along with _handle_unknown_drag_data)
    def get_drag_data(self, locs, compile_tracks = True, existing_tracks = []):
        """
            Handles the locations from drag data

            @param locs: locations we are dealing with (can
                be anything from a file to a folder)
            @param compile_tracks: if true any tracks in the playlists
                that are not found as tracks are added to the list of tracks
            @param existing_tracks: a list of tracks that have already
                been loaded from files (used to skip loading the dragged
                tracks from the filesystem)

            @returns: a 2 tuple in which the first part is a list of tracks
                and the second is a list of playlist (note: any files that are
                in a playlist are not added to the list of tracks, but a track could
                be both in as a found track and part of a playlist)
        """
        #TODO handle if they pass in existing tracks
        trs = []
        playlists = []
        for loc in locs:
            (found_tracks, found_playlist) = self._handle_unknown_drag_data(loc)
            trs.extend(found_tracks)
            playlists.extend(found_playlist)

        if compile_tracks:
            #Add any tracks in the playlist to the master list of tracks
            for playlist in playlists:
                for track in playlist.get_tracks():
                    if track not in trs:
                        trs.append(track)

        return (trs, playlists)

    def _handle_unknown_drag_data(self, loc):
        """
            Handles unknown drag data that has been recieved by
            drag_data_received.  Unknown drag data is classified as
            any loc (location) that is not in the collection of tracks
            (i.e. a new song, or a new playlist)

            @param loc:
                the location of the unknown drag data

            @returns: a 2 tuple in which the first part is a list of tracks
                and the second is a list of playlist
        """
        filetype = None
        info = urlparse.urlparse(loc)

        # don't use gio to test the filetype if it's a non-local file
        # (otherwise gio will try to connect to every remote url passed in and
        # cause the gui to hang)
        if info.scheme in ('file', ''):
            try:
                filetype = gio.File(loc).query_info(
                    'standard::type').get_file_type()
            except gio.Error:
                filetype = None

        if trax.is_valid_track(loc) or info.scheme not in ('file', ''):
            new_track = trax.Track(loc)
            return ([new_track],[])
        elif playlist.is_valid_playlist(loc):
            #User is dragging a playlist into the playlist list
            # so we add all of the songs in the playlist
            # to the list
            new_playlist = playlist.import_playlist(loc)
            return ([], [new_playlist])
        elif filetype == gio.FILE_TYPE_DIRECTORY:
            return (trax.get_tracks_from_uri(loc), [])
        else: #We don't know what they dropped
            return ([], [])

class SearchEntry(object):
    """
        A gtk.Entry that emits the "activated" signal when something has
        changed after the specified timeout
    """
    def __init__(self, entry=None, timeout=500):
        """
            Initializes the entry
        """
        self.entry = entry
        self.timeout = timeout
        self.change_id = None

        if self.entry is None:
            self.entry = gtk.Entry()

        self.entry.connect('changed', self.on_entry_changed)
        self.entry.connect('icon-press', self.on_entry_icon_press)

    def on_entry_changed(self, *e):
        """
            Called when the entry changes
        """
        if self.change_id:
            glib.source_remove(self.change_id)

        self.change_id = glib.timeout_add(self.timeout,
            self.entry_activate)

    def on_entry_icon_press(self, entry, icon_pos, event):
        """
            Clears the entry
        """
        self.entry.set_text('')

    def entry_activate(self, *e):
        """
            Emit the activate signal
        """
        self.entry.activate()

    def __getattr__(self, attr):
        """
            Tries to pass attribute requests
            to the internal entry item
        """
        return getattr(self.entry, attr)

class VolumeControl(gtk.Alignment):
    """
        Encapsulates a button and a slider to
        control the volume indicating the current
        status via icon and tooltip
    """
    def __init__(self):
        gtk.Alignment.__init__(self, xalign=1)

        self.restore_volume = settings.get_option('player/volume', 1)
        self.icon_names = ['low', 'medium', 'high']

        builder = gtk.Builder()
        builder.add_from_file(xdg.get_data_path('ui', 'widgets',
            'volume_control.ui'))
        builder.connect_signals(self)

        box = builder.get_object('volume_control')
        box.reparent(self)

        self.button = builder.get_object('button')
        self.button.add_events(gtk.gdk.KEY_PRESS_MASK)
        self.button_image = builder.get_object('button_image')
        self.slider = builder.get_object('slider')
        self.slider_adjustment = builder.get_object('slider_adjustment')
        self.__update(self.restore_volume)

        event.add_callback(self.on_option_set, 'player_option_set')

    def __update(self, volume):
        """
            Sets the volume level indicator
        """
        icon_name = 'audio-volume-muted'
        tooltip = _('Muted')

        if volume > 0:
            i = int(round(volume * 2))
            icon_name = 'audio-volume-%s' % self.icon_names[i]
            #TRANSLATORS: Volume percentage
            tooltip = _('%d%%') % (volume * 100)

        if volume == 1.0:
            tooltip = _('Full Volume')

        if volume > 0:
            self.button.set_active(False)

        self.button_image.set_from_icon_name(icon_name, gtk.ICON_SIZE_BUTTON)
        self.slider.set_value(volume)
        self.set_tooltip_text(tooltip)

    def on_scroll_event(self, widget, event):
        """
            Changes the volume on scrolling
        """
        page_increment = self.slider_adjustment.page_increment
        step_increment = self.slider_adjustment.step_increment
        value = self.slider.get_value()

        if event.direction == gtk.gdk.SCROLL_DOWN:
            if event.state & gtk.gdk.SHIFT_MASK:
                self.slider.set_value(value - page_increment)
            else:
                self.slider.set_value(value - step_increment)
            return True
        elif event.direction == gtk.gdk.SCROLL_UP:
            if event.state & gtk.gdk.SHIFT_MASK:
                self.slider.set_value(value + page_increment)
            else:
                self.slider.set_value(value + step_increment)
            return True

        return False

    def on_button_toggled(self, button):
        """
            Mutes or unmutes the volume
        """
        if button.get_active():
            self.restore_volume = settings.get_option('player/volume', 1)
            volume = 0
        else:
            volume = self.restore_volume

        if self.restore_volume > 0:
            settings.set_option('player/volume', volume)

    def on_slider_value_changed(self, slider):
        """
            Stores the preferred volume
        """
        settings.set_option('player/volume', slider.get_value())

    def on_slider_key_press_event(self, slider, event):
        """
            Changes the volume on key press
            while the slider is focussed
        """
        page_increment = slider.get_adjustment().page_increment
        step_increment = slider.get_adjustment().step_increment
        value = slider.get_value()

        if event.keyval == gtk.keysyms.Down:
            slider.set_value(value - step_increment)
            return True
        elif event.keyval == gtk.keysyms.Page_Down:
            slider.set_value(value - page_increment)
            return True
        elif event.keyval == gtk.keysyms.Up:
            slider.set_value(value + step_increment)
            return True
        elif event.keyval == gtk.keysyms.Page_Up:
            slider.set_value(value + page_increment)
            return True

        return False

    def on_option_set(self, event, sender, option):
        """
            Updates the volume indication
        """
        if option == 'player/volume':
            self.__update(settings.get_option(option, 1))

class Menu(gtk.Menu):
    """
        A proxy for making it easier to add icons to menu items
    """
    def __init__(self):
        """
            Initializes the menu
        """
        gtk.Menu.__init__(self)
        self._dynamic_builders = []    # list of (callback, args, kwargs)
        self._destroy_dynamic = []     # list of children added by dynamic
                                       # builders. Will be destroyed and
                                       # recreated at each map()
        self.connect('map', self._check_dynamic)

        self.show()

    def append_image(self, pixbuf, callback, data=None):
        """
            Appends a graphic as a menu item
        """
        item = gtk.MenuItem()
        image = gtk.Image()
        image.set_from_pixbuf(pixbuf)
        item.add(image)

        if callback: item.connect('activate', callback, data)
        gtk.Menu.append(self, item)
        item.show_all()
        return item

    def _insert(self, label=None, callback=None, stock_id=None, data=None, prepend=False):
        """
            Inserts a menu item (append by default)
        """
        if stock_id:
            if label:
                item = gtk.ImageMenuItem(label)
                image = gtk.image_new_from_stock(stock_id,
                    gtk.ICON_SIZE_MENU)
                item.set_image(image)
            else:
                item = gtk.ImageMenuItem(stock_id=stock_id)
        else:
            item = gtk.MenuItem(label)

        if callback: item.connect('activate', callback, data)

        if prepend:
            gtk.Menu.prepend(self, item)
        else:
            gtk.Menu.append(self, item)

        item.show_all()
        return item

    def append(self, label=None, callback=None, stock_id=None, data=None):
        """
            Appends a menu item
        """
        return self._insert(label, callback, stock_id, data)

    def prepend(self, label=None, callback=None, stock_id=None, data=None):
        """
            Prepends a menu item
        """
        return self._insert(label, callback, stock_id, data, prepend=True)

    def append_item(self, item):
        """
            Appends a menu item
        """
        gtk.Menu.append(self, item)
        item.show_all()

    def append_menu(self, label, menu, stock_id=None):
        """
            Appends a submenu
        """
        if stock_id:
            item = self.append(label, None, stock_id)
            item.set_submenu(menu)
            return item

        item = gtk.MenuItem(label)
        item.set_submenu(menu)
        item.show()
        gtk.Menu.append(self, item)

        return item

    def insert_menu(self, index, label, menu):
        """
            Inserts a menu at the specified index
        """
        item = gtk.MenuItem(label)
        item.set_submenu(menu)
        item.show()
        gtk.Menu.insert(self, item, index)

        return item

    def append_separator(self):
        """
            Adds a separator
        """
        item = gtk.SeparatorMenuItem()
        item.show()
        gtk.Menu.append(self, item)

    def add_dynamic_builder(self, callback, *args, **kwargs):
        """
            Adds a callback that will be run every time the menu is mapped,
            to add any items that change frequently. The items they add are
            destroyed and re-created with each map event.

        """
        self._dynamic_builders.append((callback, args, kwargs))

    def remove_dynamic_builder(self, callback):
        """
            Removes the given dynamic builder callback.
        """
        self._dynamic_builders = [ tuple for tuple in self._dynamic_builders
                                   if tuple[0] != callback ]

    def _check_dynamic(self, *args):
        """
           Deletes and builds again items added by the last batch of
           dynamic builder callbacks.
        """
        if self._destroy_dynamic:
            for child in self._destroy_dynamic:
                self.remove(child)
            self._destroy_dynamic = []

        if self._dynamic_builders:
            children_before = set(self.get_children())
            for callback, args, kwargs in self._dynamic_builders:
                callback(*args, **kwargs)
            self._destroy_dynamic = [ child for child in self.get_children()
                                      if child not in children_before ]

    def popup(self, *e):
        """
            Shows the menu
        """
        if len(e) == 1:
            event = e[0]
            gtk.Menu.popup(self, None, None, None, event.button, event.time)
        else:
            gtk.Menu.popup(self, *e)

class Statusbar(object):
    """
        Convenient access to multiple status labels
    """
    def __init__(self, status_bar):
        """
            Initialises the status bar
        """
        # The first child of the status bar is a frame containing a label. We
        # create an HBox, pack it inside the frame, and move the label and other
        # widgets of the status bar into it.
        self.status_bar = status_bar
        children = status_bar.get_children()
        frame = children[0]
        label = frame.child
        hbox = gtk.HBox(False, 0)
        frame.remove(label)
        hbox.pack_start(label, True, True)
        frame.add(hbox)

        for widget in children[1:]:
            # Bug in old PyGTK versions: Statusbar.remove hides
            # Container.remove.
            gtk.Container.remove(status_bar, widget)
            hbox.pack_start(widget, False, True)

        self.track_count_label = children[1]
        self.queue_count_label = children[2].child

        self.context_id = self.status_bar.get_context_id('status')
        self.message_ids = []

        self.status_bar.set_app_paintable(True)
        self.status_bar.connect('expose-event', self.on_expose_event)

    def set_status(self, status, timeout=0):
        """
            Sets the status message
        """
        self.message_ids += [self.status_bar.push(self.context_id, status)]

        if timeout > 0:
            glib.timeout_add_seconds(timeout, self.clear_status)

    def clear_status(self):
        """
            Clears the status message
        """
        try:
            for message_id in self.message_ids:
                self.status_bar.remove_message(self.context_id, message_id)
        except AttributeError:
            for message_id in self.message_ids:
                self.status_bar.remove(self.context_id, message_id)

        del self.message_ids[:]
        self.message_ids = []

    def set_track_count(self, playlist_count=0, collection_count=0):
        """
            Sets the track count
        """
        status = _("%(playlist_count)d showing, "
            "%(collection_count)d in collection") % {
            'playlist_count': playlist_count,
            'collection_count': collection_count
        }

        self.track_count_label.set_label(status)

    def set_queue_count(self, queue_count=0):
        """
            Sets the queue count
        """
        if queue_count > 0:
            self.queue_count_label.set_text(_("(%d queued)") % queue_count)
            self.queue_count_label.set_no_show_all(False)
            self.queue_count_label.show_all()
        else:
            self.queue_count_label.hide_all()
            self.queue_count_label.set_no_show_all(True)

    def get_grip_edge(self, widget):
        """
            Taken from GTK source, retrieves the
            preferred edge for the resize grip
        """
        if widget.get_direction() == gtk.TEXT_DIR_LTR:
            edge = gtk.gdk.WINDOW_EDGE_SOUTH_EAST
        else:
            edge = gtk.gdk.WINDOW_EDGE_SOUTH_WEST
        return edge

    def get_grip_rect(self, widget):
        """
            Taken from GTK source, retrieves the
            rectangle to draw the resize grip on
        """
        width = height = 18
        allocation = widget.get_allocation()

        width = min(width, allocation.width)
        height = min(height, allocation.height - widget.style.ythickness)

        if widget.get_direction() == gtk.TEXT_DIR_LTR:
            x = allocation.x + allocation.width - width
        else:
            x = allocation.x + widget.style.xthickness

        y = allocation.y + allocation.height - height

        return gtk.gdk.Rectangle(x, y, width, height)

    def on_expose_event(self, widget, event):
        """
            Override required to make alpha
            transparency work properly
        """
        if widget.get_has_resize_grip():
            edge = self.get_grip_edge(widget)
            rect = self.get_grip_rect(widget)

            widget.style.paint_resize_grip(
                widget.window,
                widget.get_state(),
                event.area,
                widget,
                'statusbar',
                edge,
                rect.x, rect.y,
                rect.width - widget.style.xthickness,
                rect.height - widget.style.ythickness
            )

            frame = widget.get_children()[0]
            box = frame.get_children()[0]
            box.send_expose(event) # Bypass frame

        return True

class MenuRatingWidget(gtk.MenuItem):
    """
        A rating widget that can be used as a menu entry

        @param: _get_tracks is a function that should return a list of tracks
           linked to this widget.

        @param: _get_tracks_rating is a function that should return an int
           representing the rating of the tracks which are meant to be linked to
           this widget. Should return 0 if two tracks have a different rating or
           if it contains over miscellaneous/rating_widget_tracks_limit tracks.
           Default limit: 100
    """

    def __init__(self, _get_tracks, _get_tracks_rating):
        gtk.MenuItem.__init__(self)

        self._get_tracks = _get_tracks
        self._get_tracks_rating = _get_tracks_rating
        self._last_calculated_rating = self._get_tracks_rating()

        self.hbox = gtk.HBox(spacing=3)
        self.hbox.pack_start(gtk.Label(_("Rating:")), False, False)
        self.image = gtk.image_new_from_pixbuf(
            self._get_rating_pixbuf(self._last_calculated_rating))
        self.hbox.pack_start(self.image, False, False, 12)

        self.add(self.hbox)

        self.connect('button-release-event', self._update_rating)
        self.connect('motion-notify-event', self._motion_notify)
        self.connect('leave-notify-event', self._leave_notify)

        # This may be useful when rating is changed from outside of the GUI
        event.add_callback(self.on_rating_change, 'rating_changed')

    def _motion_notify(self, widget, e):
        steps = settings.get_option('miscellaneous/rating_steps', 5)
        (x, y) = e.get_coords()
        try:
            (u, v) =  self.translate_coordinates(self.image, int(x), int(y))
        except ValueError: return

        if -12 <= u < 0:
            r = 0
        elif 0 <= u < steps*12:
            r = (u / 12) + 1
        else:
            r = -1

        if r >= 0:
            self.image.set_from_pixbuf(
                self._get_rating_pixbuf(r))
            self.queue_draw()

    def _leave_notify(self, widget, e):
        """
            Resets the rating if the widget
            is left without clicking
        """
        self.image.set_from_pixbuf(
            self._get_rating_pixbuf(self._last_calculated_rating))
        self.queue_draw()

    def _update_rating(self, widget, e):
        """
            Updates the rating of the tracks for this
            widget, meant to be used with a click event
        """
        event.remove_callback(self.on_rating_change, 'rating_changed')

        trs = self._get_tracks()
        if trs and trs[0]:
            steps = settings.get_option('miscellaneous/rating_steps', 5)
            (x, y) = e.get_coords()
            (u, v) =  self.translate_coordinates(self.image, int(x), int(y))
            if -12 <= u < 0:
                r = 0
            elif 0 <= u < steps*12:
                r = (u / 12) + 1
            else:
                r = -1

            if r >= 0:
                if r == self._last_calculated_rating:
                    r = 0

                for track in trs:
                    track.set_rating(r)

                event.log_event('rating_changed', self, r)
                self._last_calculated_rating = r

        event.add_callback(self.on_rating_change, 'rating_changed')

    def _get_rating_pixbuf(self, num):
        """
            Returns the pixbuf for num
        """
        return rating.rating_images[num]

    def on_rating_change(self, type = None, object = None, data = None):
        """
            Handles possible changes of track ratings
        """
        self._last_calculated_rating = self._get_tracks_rating()
        self.image.set_from_pixbuf(
            self._get_rating_pixbuf(self._last_calculated_rating))
        self.queue_draw ()

class TrackInfoPane(gtk.Alignment):
    """
        Displays cover art and track data
    """
    def __init__(self, display_progress=False, auto_update=False):
        """
            :param display_progress: Toggles the display
                of the playback indicator and progress bar
                if the current track is played
            :param auto_update: Toggles the automatic
                following of playback state and track changes
        """
        gtk.Alignment.__init__(self, xscale=1, yscale=1)

        builder = gtk.Builder()
        builder.add_from_file(xdg.get_data_path(
            'ui', 'widgets', 'track_info.ui'))

        info_box = builder.get_object('info_box')
        info_box.reparent(self)

        self._display_progress = display_progress
        self._auto_update = auto_update
        self._timer = None
        self.player = None
        self._track = None
        self._formatter = TrackFormatter(
            _('<span size="x-large" weight="bold">$title</span>\n'
              'by ${artist:compilate}\n'
              'from $album')
        )

        self.cover_image = builder.get_object('cover_image')
        self.info_label = builder.get_object('info_label')
        self.action_area = builder.get_object('action_area')
        self.progress_box = builder.get_object('progress_box')
        self.playback_image = builder.get_object('playback_image')
        self.progressbar = builder.get_object('progressbar')

        if self._auto_update:
            event.add_callback(self.on_playback_player_end,
                'playback_player_end')
            event.add_callback(self.on_playback_track_start,
                'playback_track_start')
            event.add_callback(self.on_playback_toggle_pause,
                'playback_toggle_pause')
            event.add_callback(self.on_playback_error,
                'playback_error')
            event.add_callback(self.on_track_tags_changed,
                'track_tags_changed')

        try:
            exaile = xl.main.exaile()
        except AttributeError:
            event.add_callback(self.on_exaile_loaded, 'exaile_loaded')
        else:
            self.on_exaile_loaded('exaile_loaded', exaile, None)

    def get_info_format(self):
        """
            Gets the current format used
            to display the track data

            :rtype: string
        """
        return self._formatter.get_property('format')

    def set_info_format(self, format):
        """
            Sets the format used to display the track data

            :param format: the format, see the documentation
                of :class:`string.Template` for details
            :type format: string
        """
        self._formatter.set_property('format', format)

    def get_display_progress(self):
        """
            Returns whether the progress indicator
            is currently visible or not
        """
        return self._display_progress

    def set_display_progress(self, display_progress):
        """
            Shows or hides the progress indicator. The
            indicator will not be displayed if the
            currently displayed track is not playing.

            :param display_progress: Whether to show
                or hide the progress indicator
            :type display_progress: bool
        """
        self._display_progress = display_progress

    def set_track(self, track):
        """
            Updates the data displayed in the info pane

            :param track: A track to take the data from,
                clears the info pane if track is None
            :type track: :class:`xl.trax.Track`
        """
        if track is None:
            self.clear()
            return

        self._track = track

        image_data = covers.MANAGER.get_cover(track, use_default=True)
        width = settings.get_option('gui/cover_width', 100)
        pixbuf = icons.MANAGER.pixbuf_from_data(image_data, (width, width))
        self.cover_image.set_from_pixbuf(pixbuf)

        self.info_label.set_markup(self._formatter.format(track, markup_escape=True))

        if self._display_progress:
            state = self.player.get_state()

            if track == self.player.current and not self.player.is_stopped():
                stock_id = gtk.STOCK_MEDIA_PLAY
                
                if self.player.is_paused():
                    stock_id = gtk.STOCK_MEDIA_PAUSE

                self.playback_image.set_from_stock(stock_id,
                    gtk.ICON_SIZE_SMALL_TOOLBAR)

                self.__show_progress()
            else:
                self.__hide_progress()

    def clear(self):
        """
            Resets the info pane
        """
        pixbuf = icons.MANAGER.pixbuf_from_data(
            covers.MANAGER.get_default_cover())
        self.cover_image.set_from_pixbuf(pixbuf)
        self.info_label.set_markup('<span size="x-large" '
            'weight="bold">%s</span>' % _('Not Playing'))

        if self._display_progress:
            self.__hide_progress()

    def get_action_area(self):
        """
            Retrieves the action area
            at the end of the pane

            :rtype: :class:`gtk.VBox`
        """
        return self.action_area

    def __enable_timer(self):
        """
            Enables the timer, if not already
        """
        if self._timer is not None:
            return

        milliseconds = settings.get_option(
            'gui/progress_update/millisecs', 1000)

        if milliseconds % 1000 == 0:
            self._timer = glib.timeout_add_seconds(milliseconds / 1000,
                self.__update_progress)
        else:
            self._timer = glib.timeout_add(milliseconds,
                self.__update_progress)

    def __disable_timer(self):
        """
            Disables the timer, if not already
        """
        if self._timer is None:
            return

        glib.source_remove(self._timer)
        self._timer = None

    def __show_progress(self):
        """
            Shows the progress area and enables
            updates of the progress bar
        """
        self.__enable_timer()
        self.progress_box.set_no_show_all(False)
        self.progress_box.set_property('visible', True)

    def __hide_progress(self):
        """
            Hides the progress area and disables
            updates of the progress bar
        """
        self.progress_box.set_property('visible', False)
        self.progress_box.set_no_show_all(True)
        self.__disable_timer()

    def __update_progress(self):
        """
            Updates the state of the progress bar
        """
        track = self.player.current

        if track is not self._track:
            self.__hide_progress()
            return False

        fraction = 0
        text = _('Not Playing')

        if track is not None:
            total = track.get_tag_raw('__length')

            if total is not None:
                current = self.player.get_time()
                text = '%d:%02d / %d:%02d' % \
                    (current // 60, current % 60,
                     total // 60, total % 60)

                if self.player.is_paused():
                    self.__disable_timer()
                    fraction = self.progressbar.get_fraction()
                elif self.player.is_playing():
                    self.__enable_timer()
                    fraction = self.player.get_progress()
            elif not track.is_local():
                self.__disable_timer()
                text = _('Streaming...')

        self.progressbar.set_fraction(fraction)
        self.progressbar.set_text(text)

        return True

    def on_playback_player_end(self, event, player, track):
        """
            Clears the info pane on playback end
        """
        self.clear()

    def on_playback_track_start(self, event, player, track):
        """
            Updates the info pane on track start
        """
        self.set_track(track)

    def on_playback_toggle_pause(self, event, player, track):
        """
            Updates the info pane on playback pause/resume
        """
        self.set_track(track)

    def on_playback_error(self, event, player, track):
        """
            Clears the info pane on playback errors
        """
        self.clear()

    def on_track_tags_changed(self, event, track, tag):
        """
            Updates the info pane on tag changes
        """
        if self.player is not None and \
           not self.player.is_stopped() and \
           track is self._track:
            self.set_track(track)

    def on_exaile_loaded(self, e, exaile, nothing):
        """
            Sets up references after controller is loaded
        """
        self.player = exaile.player

        current_track = self.player.current

        if self._auto_update and current_track is not None:
            self.set_track(current_track)
        else:
            self.clear()

        event.remove_callback(self.on_exaile_loaded, 'exaile_loaded')

class TrackListInfoPane(gtk.Alignment):
    """
        Displays cover art and data about a list of tracks
    """
    def __init__(self, display_tracklist=False):
        """
            :param display_tracklist: Whether to display
                a short list of tracks
        """
        gtk.Alignment.__init__(self)

        builder = gtk.Builder()
        builder.add_from_file(xdg.get_data_path(
            'ui', 'widgets', 'tracklist_info.ui'))

        info_box = builder.get_object('info_box')
        info_box.reparent(self)

        self._display_tracklist = display_tracklist

        self.cover_image = builder.get_object('cover_image')
        self.album_label = builder.get_object('album_label')
        self.artist_label = builder.get_object('artist_label')

        if self._display_tracklist:
            self.tracklist_table = builder.get_object('tracklist_table')
            self.tracklist_table.set_no_show_all(False)
            self.tracklist_table.set_property('visible', True)

            self.total_label = builder.get_object('total_label')
            self.total_label.set_no_show_all(False)
            self.total_label.set_property('visible', True)

            self.rownumber = 1
            self.pango_attributes = pango.AttrList()
            self.pango_attributes.insert(
                pango.AttrScale(pango.SCALE_SMALL, end_index=-1))
            self.pango_attributes.insert(
                pango.AttrStyle(pango.STYLE_ITALIC, end_index=-1))
            self.ellipse_pango_attributes = pango.AttrList()
            self.ellipse_pango_attributes.insert(
                pango.AttrWeight(pango.WEIGHT_BOLD, end_index=-1))

    def set_tracklist(self, tracks):
        """
            Updates the data displayed in the info pane
            :param tracks: A list of tracks to take the
                data from
        """
        tracks = trax.util.sort_tracks(['album', 'tracknumber'], tracks)

        image_data = covers.MANAGER.get_cover(tracks[0], use_default=True)
        width = settings.get_option('gui/cover_width', 100)
        pixbuf = icons.MANAGER.pixbuf_from_data(image_data, (width, width))
        self.cover_image.set_from_pixbuf(pixbuf)

        albums = []
        artists = []
        total_length = 0

        for track in tracks:
            albums += [track.get_tag_display('album')]
            artists += [track.get_tag_display('artist')]
            total_length += float(track.get_tag_raw('__length'))

        # Make unique
        albums = set(albums)
        artists = set(artists)

        if len(albums) == 1:
            self.album_label.set_text(albums.pop())
        else:
            self.album_label.set_text(_('Various'))

        if len(artists) == 1:
            self.artist_label.set_text(artists.pop())
        else:
            self.artist_label.set_text(_('Various Artists'))

        if self._display_tracklist:
            track_count = len(tracks)
            # Leaves us with a maximum of three tracks to display
            tracks = tracks[:3] + [None]

            for track in tracks:
                self.__append_row(track)

            self.tracklist_table.show_all()
            total_duration = LengthTagFormatter.format_value(total_length, 'long')

            text = _('%(track_count)d in total (%(total_duration)s)') % {
                'track_count': track_count,
                'total_duration': total_duration
            }

            self.total_label.set_text(text)

    def clear(self):
        """
            Resets the info pane
        """
        pixbuf = icons.MANAGER.pixbuf_from_data(
            covers.MANAGER.get_default_cover())
        self.cover_image.set_from_pixbuf(pixbuf)
        self.album_label.set_text('')
        self.artist_label.set_text('')

        if self._display_tracklist:
            items = self.tracklist_table.get_children()

            for item in items:
                self.tracklist_table.remove(item)
            self.rownumber = 1

            self.total_label.set_text('')

    def __append_row(self, track):
        """
            Appends a row to the internal
            track list table
            :param track: A track to build the row from,
                None to insert an ellipse
        """
        if track is None:
            ellipse_label = gtk.Label('⋮')
            ellipse_label.set_attributes(self.ellipse_pango_attributes)
            self.tracklist_table.attach(ellipse_label,
                1, 2, self.rownumber - 1, self.rownumber)
        else:
            tracknumber = track.get_tag_display('tracknumber')
            tracknumber = TrackNumberTagFormatter.format_value(tracknumber)
            tracknumber_label = gtk.Label(tracknumber)
            tracknumber_label.set_attributes(self.pango_attributes)
            tracknumber_label.props.xalign = 0
            self.tracklist_table.attach(tracknumber_label,
                0, 1, self.rownumber - 1, self.rownumber)

            title_label = gtk.Label(track.get_tag_display('title'))
            title_label.set_attributes(self.pango_attributes)
            self.tracklist_table.attach(title_label,
                1, 2, self.rownumber - 1, self.rownumber)

            length = float(track.get_tag_display('__length'))
            length = LengthTagFormatter.format_value(length, 'short')
            length_label = gtk.Label(length)
            length_label.set_attributes(self.pango_attributes)
            length_label.props.xalign = 0.9
            self.tracklist_table.attach(length_label,
                2, 3, self.rownumber - 1, self.rownumber)

        self.rownumber += 1

class ToolTip(object):
    """
        Custom tooltip class to allow for
        extended tooltip functionality
    """
    def __init__(self, parent, widget):
        """
            :param parent: the parent widget the tooltip
                should be attached to
            :param widget: the tooltip widget to be used
                for the tooltip
        """
        if self.__class__.__name__ == 'ToolTip':
            raise TypeError("cannot create instance of abstract "
                            "(non-instantiable) type `ToolTip'")

        self.__widget = widget
        self.__widget.unparent() # Just to be sure

        parent.set_has_tooltip(True)
        parent.connect('query-tooltip', self.on_query_tooltip)

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        """
            Puts the custom widget into the tooltip
        """
        tooltip.set_custom(self.__widget)

        return True

class TrackToolTip(ToolTip):
    """
        Track specific tooltip class, displays
        track data and progress indicators
    """
    def __init__(self, parent, display_progress=False, auto_update=False):
        """
            :param parent: the parent widget the tooltip
                should be attached to
            :param display_progress: Toggles the display
                of the playback indicator and progress bar
                if the current track is played
            :param auto_update: Toggles the automatic
                following of playback state and track changes
        """
        self.info_pane = TrackInfoPane(display_progress, auto_update)
        self.info_pane.set_padding(6, 6, 6, 6)
        self.info_pane.info_label.set_ellipsize(pango.ELLIPSIZE_NONE)

        ToolTip.__init__(self, parent, self.info_pane)
    
    def set_track(self, track):
        """
            Updates data displayed in the tooltip
            :param track: A track to take the data from,
                clears the tooltip if track is None
        """
        self.info_pane.set_track(track)

    def clear(self):
        """
            Resets the tooltip
        """
        self.info_pane.clear()

class TrackListToolTip(ToolTip):

    def __init__(self, parent, display_tracklist=False):
        """
            :param parent: the parent widget the tooltip
                should be attached to
            :param display_tracklist: Whether to display
                a short list of tracks
        """
        self.info_pane = TrackListInfoPane(display_tracklist)
        self.info_pane.set_padding(6, 6, 6, 6)

        ToolTip.__init__(self, parent, self.info_pane)

    def set_tracklist(self, tracks):
        self.info_pane.set_tracklist(tracks)

    def clear(self):
        self.info_pane.clear()

class RatingWidget(gtk.EventBox):
    """
        A rating widget which displays a row of
        images and allows for selecting the rating
    """
    __gproperties__ = {
        'rating': (
            gobject.TYPE_INT,
            'rating',
            'The selected rating',
            0, # Minimum
            65535, # Maximum
            0, # Default
            gobject.PARAM_READWRITE
        )
    }
    __gsignals__ = {
        'rating-changed': (
            gobject.SIGNAL_RUN_FIRST,
            gobject.TYPE_NONE,
            (gobject.TYPE_INT,)
        )
    }

    def __init__(self, rating=0, auto_update=True):
        """
            :param rating: the optional initial rating
            :type rating: int
            :param auto_update: whether to automatically
                retrieve the rating of the currently playing
                track if a rating was changed
            :type auto_update: bool
        """
        gtk.EventBox.__init__(self)

        self.set_visible_window(False)
        self.set_above_child(True)
        self.add_events(gtk.gdk.POINTER_MOTION_MASK)

        self._image = gtk.Image()
        self.add(self._image)

        self._rating = -1
        self.props.rating = rating

        self.connect('motion-notify-event', self.on_motion_notify_event)
        self.connect('leave-notify-event', self.on_leave_notify_event)
        self.connect('button-release-event', self.on_button_release_event)

        if auto_update:
            try:
                exaile = xl.main.exaile()
            except AttributeError:
                event.add_callback(self.on_exaile_loaded, 'exaile_loaded')
            else:
                self.on_exaile_loaded('exaile_loaded', exaile, None)

            for event_name in ('playback_track_start', 'playback_player_end',
                               'rating_changed'):
                event.add_callback(self.on_rating_update, event_name)

    def do_get_property(self, property):
        """
            Getter for custom properties
        """
        if property.name == 'rating':
            return self._rating
        else:
            raise AttributeError('unkown property %s' % property.name)

    def do_set_property(self, property, value):
        """
            Setter for custom properties
        """
        if property.name == 'rating':
            if value == self._rating:
                value = 0
            else:
                maximum = settings.get_option('miscellaneous/rating_steps', 5)
                value = max(0, value)
                value = min(value, maximum)

            self._rating = value
            self._image.set_from_pixbuf(
                icons.MANAGER.pixbuf_from_rating(value))
            self.emit('rating-changed', value)
        else:
            raise AttributeError('unkown property %s' % property.name)

    def destroy(self):
        """
            Cleanups
        """
        for event_name in ('playback_track_start', 'playback_player_start',
                           'rating_changed'):
            event.remove_callback(self.on_rating_update, event_name)

    def on_motion_notify_event(self, widget, event):
        """
            Temporarily updates the displayed rating
        """
        allocation = widget.get_allocation()
        maximum = settings.get_option('miscellaneous/rating_steps', 5)
        pixbuf_width = self._image.get_pixbuf().get_width()
        # Activate pixbuf if half of it has been passed
        threshold = (pixbuf_width / maximum) / 2
        position = (event.x + threshold) / allocation.width
        rating = int(position * maximum)

        self._image.set_from_pixbuf(
            icons.MANAGER.pixbuf_from_rating(rating))

    def on_leave_notify_event(self, widget, event):
        """
            Restores the original rating
        """
        self._image.set_from_pixbuf(
            icons.MANAGER.pixbuf_from_rating(self._rating))

    def on_button_release_event(self, widget, event):
        """
            Applies the selected rating
        """
        allocation = widget.get_allocation()
        maximum = settings.get_option('miscellaneous/rating_steps', 5)
        pixbuf_width = self._image.get_pixbuf().get_width()
        # Activate pixbuf if half of it has been passed
        threshold = (pixbuf_width / maximum) / 2
        position = (event.x + threshold) / allocation.width
        self.props.rating = int(position * maximum)

    def on_exaile_loaded(self, event_type, exaile, nothing):
        """
            Sets up the internal reference to the player
        """
        self.player = exaile.player
        self.on_rating_update('rating_changed', None, None)

        event.remove_callback(self.on_exaile_loaded, 'exaile_loaded')

    def on_rating_update(self, event_type, sender, data):
        """
            Updates the rating from the current track
        """
        if self.player.current is not None:
            self._rating = self.player.current.get_rating()
            self._image.set_from_pixbuf(
                icons.MANAGER.pixbuf_from_rating(self._rating))

            self.set_sensitive(True)
        else:
            self.set_sensitive(False)

class RatingMenuItem(gtk.MenuItem):
    """
        A menuitem containing a rating widget
    """
    __gproperties__ = {
        'rating': (
            gobject.TYPE_INT,
            'rating',
            'The selected rating',
            0, # Minimum
            65535, # Maximum
            0, # Default
            gobject.PARAM_READWRITE
        )
    }
    __gsignals__ = {
        'rating-changed': (
            gobject.SIGNAL_RUN_FIRST,
            gobject.TYPE_NONE,
            (gobject.TYPE_INT,)
        )
    }
    def __init__(self, rating=0, auto_update=True):
        """
            :param rating: the optional initial rating
            :type rating: int
            :param auto_update: whether to automatically
                retrieve the rating of the currently playing
                track if a rating was changed
            :type auto_update: bool
        """
        gtk.MenuItem.__init__(self)

        box = gtk.HBox(spacing=6)
        box.pack_start(gtk.Label(_('Rating:')), False, False)
        self.rating_widget = RatingWidget(rating, auto_update)
        box.pack_start(self.rating_widget, False, False)

        self.add(box)

        self.rating_widget.connect('rating-changed',
            self.on_rating_changed)
        self.connect('motion-notify-event',
            self.on_motion_notify_event)
        self.connect('leave-notify-event',
            self.on_leave_notify_event)
        self.connect('button-release-event',
            self.on_button_release_event)

    def do_get_property(self, property):
        """
            Getter for custom properties
        """
        if property.name == 'rating':
            return self.rating_widget.props.rating
        else:
            raise AttributeError('unkown property %s' % property.name)

    def do_set_property(self, property, value):
        """
            Setter for custom properties
        """
        if property.name == 'rating':
            self.rating_widget.props.rating = value
        else:
            raise AttributeError('unkown property %s' % property.name)

    def on_rating_changed(self, widget, rating):
        """
            Forwards the event
        """
        self.emit('rating-changed', rating)

    def on_motion_notify_event(self, widget, event):
        """
            Forwards the event to the rating widget
        """
        allocation = self.rating_widget.get_allocation()

        if allocation.x < event.x < allocation.x + allocation.width:
            x, y = widget.translate_coordinates(self.rating_widget,
                int(event.x), int(event.y))
            event.x, event.y = float(x), float(y)
            self.rating_widget.emit('motion-notify-event', event)

    def on_leave_notify_event(self, widget, event):
        """
            Forwards the event to the rating widget
        """
        self.rating_widget.emit('leave-notify-event', event)

    def on_button_release_event(self, widget, event):
        """
            Forwards the event to the rating widget
        """
        allocation = self.rating_widget.get_allocation()

        if allocation.x < event.x < allocation.x + allocation.width:
            x, y = widget.translate_coordinates(self.rating_widget,
                int(event.x), int(event.y))
            event.x, event.y = float(x), float(y)
            self.rating_widget.emit('button-release-event', event)

def finish(repeat=True):
    """
        Waits for current pending gtk events to finish
    """
    while gtk.events_pending():
        gtk.main_iteration()
        if not repeat: break

# vim: et sts=4 sw=4
