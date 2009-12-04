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

import gtk, os.path, time, urllib
import gtk.gdk, pango, gobject, gio
from xl import xdg, track, playlist, common, settings, event
from xl.nls import gettext as _
import threading
from xlgui import rating
from urllib2 import urlparse

def _idle_callback(func, callback, *args, **kwargs):
    value = func(*args, **kwargs)
    if callback and callable(callback):
        callback(value)

def idle_add(callback=None):
    """
        A decorator that will wrap the function in a gobject.idle_add call

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
            gobject.idle_add(_idle_callback, f, callback,
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
        loader = gtk.gdk.PixbufLoader()
        loader.write(data)
        loader.close()
        self.pixbuf = loader.get_pixbuf()
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
    dragged_data = dict()
    def __init__(self, cont, receive=True, source=True):
        """
            Initializes the tree and sets up the various callbacks
        """
        gtk.TreeView.__init__(self)
        self.cont = cont

        self.targets = [("text/uri-list", 0, 0)]

        if source:
            self.drag_source_set(
                gtk.gdk.BUTTON1_MASK, self.targets,
                gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)

        if receive:
            self.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets,
                gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_DEFAULT|
                gtk.gdk.ACTION_MOVE)
            self.connect('drag_data_received',
                self.cont.drag_data_received)
            self.connect('drag_data_delete',
                self.cont.drag_data_delete)
        self.receive = receive
        self.dragging = False
        self.connect('drag_begin', self.drag_begin)
        self.connect('drag_end', self.drag_end)
        self.connect('drag_motion', self.drag_motion)
        self.connect('button_release_event', self.button_release)
        self.connect('button_press_event', self.button_press)

        if source:
            self.connect('drag_data_get', self.cont.drag_get_data)
            self.drag_source_set_icon_stock('gtk-dnd')

    def button_release(self, button, event):
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

        x, y = event.get_coords()
        x = int(x); y = int(y)

        path = self.get_path_at_pos(x, y)
        if not path: return False
        selection.select_path(path[0])

    def drag_end(self, list, context):
        """
            Called when the dnd is ended
        """
        self.dragging = False
        self.unset_rows_drag_dest()
        self.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.targets,
            gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)

    def drag_begin(self, list, context):
        """
            Called when dnd is started
        """
        self.dragging = True

        context.drag_abort(gtk.get_current_event_time())
        selection = self.get_selection()
        if selection.count_selected_rows() > 1:
            self.drag_source_set_icon_stock('gtk-dnd-multiple')
        else: self.drag_source_set_icon_stock('gtk-dnd')
        return False

    def drag_motion(self, treeview, context, x, y, timestamp):
        """
            Called when a row is dragged over this treeview
        """
        if not self.receive:
            return
        self.enable_model_drag_dest(self.targets,
            gtk.gdk.ACTION_DEFAULT)
        info = treeview.get_dest_row_at_pos(x, y)
        if not info: return
        treeview.set_drag_dest_row(info[0], info[1])

    def button_press(self, button, event):
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
                    self.cont.button_press(button, event)

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
        return self.cont.button_press(button, event)

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
        tracks = []
        playlists = []
        for loc in locs:
            (found_tracks, found_playlist) = self._handle_unknown_drag_data(loc)
            tracks.extend(found_tracks)
            playlists.extend(found_playlist)

        if compile_tracks:
            #Add any tracks in the playlist to the master list of tracks
            for playlist in playlists:
                for track in playlist.get_tracks():
                    if track not in tracks:
                        tracks.append(track)

        return (tracks, playlists)

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

        if track.is_valid_track(loc) or info.scheme not in ('file', ''):
            new_track = track.Track(loc)
            return ([new_track],[])
        elif playlist.is_valid_playlist(loc):
            #User is dragging a playlist into the playlist list
            # so we add all of the songs in the playlist
            # to the list
            new_playlist = playlist.import_playlist(loc)
            return ([], [new_playlist])
        elif filetype == gio.FILE_TYPE_DIRECTORY:
            return (track.get_tracks_from_uri(loc), [])
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
            gobject.source_remove(self.change_id)

        self.change_id = gobject.timeout_add(self.timeout,
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

def get_icon(id, size=gtk.ICON_SIZE_BUTTON):
    """
        Returns a stock icon for the specified id and size
    """
    theme = gtk.icon_theme_get_default()
    try:
        icon = theme.load_icon(id, size, gtk.ICON_LOOKUP_NO_SVG)
        if icon: return icon
    except gobject.GError:
        pass

    # If no stock icon exists for the specified ID, search in the "images" data
    # directory.
    path = xdg.get_data_path('images', id + '.png')

    # Fallback to the "track.png" file.
    if not path:
        path = xdg.get_data_path('images', 'track.png')

    return gtk.gdk.pixbuf_new_from_file(path)

class MuteButton(object):
    """
        Allows for immediate muting of the volume and
        indicates the current volume level via an icon
    """
    def __init__(self, button):
        self.button = button
        self.restore_volume = settings.get_option('player/volume', 1)
        self.icon_names = ['low', 'medium', 'high']

        self.button.connect('toggled', self.on_toggled)
        event.add_callback(self.on_setting_change, 'player_option_set')

    def update_volume_icon(self, volume):
        """
            Sets the volume level indicator
        """
        icon_name = 'audio-volume-muted'
        tooltip = _('Muted')

        if volume > 0:
            i = int(round(volume * 2))
            icon_name = 'audio-volume-%s' % self.icon_names[i]
            #TRANSLATORS: Volume percentage
            tooltip = '%d%%' % (volume * 100)

        if volume == 1.0:
            tooltip = _('Full Volume')

        self.button.child.set_from_icon_name(icon_name, gtk.ICON_SIZE_BUTTON)
        self.button.set_tooltip_text(tooltip)

    def on_toggled(self, button):
        """
            Mutes or unmutes the volume
        """
        if button.get_active():
            self.restore_volume = settings.get_option('player/volume', 1)
            volume = 0
        else:
            volume = self.restore_volume

        self.update_volume_icon(volume)

        if self.restore_volume > 0:
            settings.set_option('player/volume', volume)

    def on_setting_change(self, event, sender, option):
        """
            Saves the restore volume and
            changes the volume indicator
        """
        if option == 'player/volume':
            volume = settings.get_option(option, 1)

            if volume > 0:
                self.button.set_active(False)

            self.update_volume_icon(volume)

BITMAP_CACHE = dict()
def get_text_icon(widget, text, width, height, bgcolor='#456eac',
    bordercolor=None):
    """
        Gets a bitmap icon with the specified text, width, and height
    """
    if BITMAP_CACHE.has_key("%s - %sx%s - %s" % (text, width, height, bgcolor)):
        return BITMAP_CACHE["%s - %sx%s - %s" % (text, width, height, bgcolor)]

    default_visual = gtk.gdk.visual_get_system()
    pixmap = gtk.gdk.Pixmap(None, width, height, default_visual.depth)
    colormap = gtk.gdk.colormap_get_system()
    white = colormap.alloc_color(65535, 65535, 65535)
    black = colormap.alloc_color(0, 0, 0)
    pixmap.set_colormap(colormap)
    gc = pixmap.new_gc(foreground=black, background=white)

    if not bordercolor: bordercolor = black
    else:
        bordercolor = colormap.alloc_color(gtk.gdk.color_parse(bordercolor))
    gc.set_foreground(bordercolor)

    pixmap.draw_rectangle(gc, True, 0, 0, width, height)
    fg = colormap.alloc_color(gtk.gdk.color_parse(bgcolor))
    gc.set_foreground(fg)
    pixmap.draw_rectangle(gc, True, 1, 1, width - 2, height - 2)

    layout = widget.create_pango_layout(str(text))
    desc = pango.FontDescription("Sans 8")
    layout.set_font_description(desc)
    layout.set_alignment(pango.ALIGN_RIGHT)

    gc.set_foreground(white)
    inkRect, logicalRect = layout.get_pixel_extents()
    l, b, w, h = logicalRect
    x = ((width) / 2 - w / 2)
    y = ((height) / 2 - h / 2)
    pixmap.draw_layout(gc, x, y, layout)

    pixbuf = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8, width, height)
    pixbuf = pixbuf.get_from_drawable(pixmap, colormap, 0, 0, 0,
        0, width, height)

    BITMAP_CACHE["%s - %sx%s - %s" % (text, width, height, bgcolor)] = pixbuf
    return pixbuf

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

    def set_status(self, status, timeout=0):
        """
            Sets the status message
        """
        self.message_ids += [self.status_bar.push(self.context_id, status)]

        if timeout > 0:
            gobject.timeout_add(timeout, self.clear_status)

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

        tracks = self._get_tracks()
        if tracks and tracks[0]:
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

                for track in tracks:
                    track.set_rating (r)

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

def get_urls_for(items):
    """
        Returns the items' URLs
    """
    return [item.get_loc_for_io() for item in items]

def finish(repeat=True):
    """
        Waits for current pending gtk events to finish
    """
    while gtk.events_pending():
        gtk.main_iteration()
        if not repeat: break

def on_slider_key_press(widget, ev):
    """
        Called when the user presses a key when the volume bar is focused
    """
    # Modify default HScale up/down behaviour.
    incr = widget.get_adjustment().page_size
    if ev.keyval in (gtk.keysyms.Down, gtk.keysyms.Page_Down):
        widget.set_value(widget.get_value() - incr)
        return True
    elif ev.keyval in (gtk.keysyms.Up, gtk.keysyms.Page_Up):
        widget.set_value(widget.get_value() + incr)
        return True
    return False

