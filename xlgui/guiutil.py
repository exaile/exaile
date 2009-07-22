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

import gtk, os.path, urllib, time
import gtk.gdk, pango, gobject
from xl import xdg, track, playlist, common, settings, event
from xl.nls import gettext as _
import threading

try:
    import sexy
except ImportError:
    sexy = None

def gtkrun(f):
    """
        A decorator that will make any function run in gtk threadsafe mode

        ALL CODE MODIFYING THE UI SHOULD BE WRAPPED IN THIS
    """
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
        self.loc = image
        self.pixbuf = gtk.gdk.pixbuf_new_from_file(image)

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
            loc = loc.replace('file://', '')
            loc = urllib.unquote(loc)
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
        if loc in DragTreeView.dragged_data:
            new_track = DragTreeView.dragged_data[loc]
            del DragTreeView.dragged_data[loc]
            return ([new_track],[])
        elif track.is_valid_track(loc):
            new_track = track.Track(loc)
            return ([new_track],[])
        elif playlist.is_valid_playlist(loc):
            #User is dragging a playlist into the playlist list
            # so we add all of the songs in the playlist
            # to the list
            new_playlist = playlist.import_playlist(loc)
            return ([], [new_playlist])
        elif os.path.isdir(loc):
            #They dropped a folder
            new_tracks = [] 
            new_playlist = []
            for root, dirs, files in os.walk(loc):
                files.sort()
                for file in files:
                    full_path = os.path.join(root, file)
                    (found_tracks, found_playlist) = self._handle_unknown_drag_data(full_path)
                    new_tracks.extend(found_tracks)
                    new_playlist.extend(found_playlist) 
            return (new_tracks, new_playlist)
        else: #We don't know what they dropped
            return ([], [])

class EntryWithClearButton(object):
    """
        A gtk.Entry with a clear icon
    """
    def __init__(self):
        """
            Initializes the entry
        """
        if sexy:
            self.entry = sexy.IconEntry()
            image = gtk.Image()
            image.set_from_stock('gtk-clear', gtk.ICON_SIZE_SMALL_TOOLBAR)
            self.entry.set_icon(sexy.ICON_ENTRY_SECONDARY, image)
            self.entry.connect('icon-released', self.icon_released)
        else:
            self.entry = gtk.Entry()

    def icon_released(self, *e):
        """
            Called when the user clicks the entry icon
        """
        self.entry.set_text('')

    def __getattr__(self, attr):
        """
            If this object doesn't have the attribute, check the gtk.Entry for
            it
        """
        if attr == 'entry': return self.entry
        return getattr(self.entry, attr)

class SearchEntry(EntryWithClearButton):
    """
        A gtk.Entry that emits the "activated" signal when something has
        changed after the specified timeout
    """
    def __init__(self, timeout=500):
        """
            Initializes the entry
        """
        EntryWithClearButton.__init__(self)
        self.timeout = 500
        self.change_id = None

        self.entry.connect('changed', self.on_entry_changed)

    def on_entry_changed(self, *e):
        """
            Called when the entry changes
        """
        if self.change_id:
            gobject.source_remove(self.change_id)

        self.change_id = gobject.timeout_add(self.timeout,
            self.entry_activate)

    def entry_activate(self, *e):
        """
            Emit the activate signal
        """
        self.entry.emit('activate')

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

    def append(self, label, callback, stock_img=None, data=None):
        """
            Appends a menu item
        """
        if stock_img:
            item = gtk.ImageMenuItem(label)
            image = gtk.image_new_from_stock(stock_img,
                gtk.ICON_SIZE_MENU)
            item.set_image(image)
        else:
            item = gtk.MenuItem(label)

        if callback: item.connect('activate', callback, data)
        gtk.Menu.append(self, item)
        item.show_all()
        return item

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

class StatusBar(object):
    """
        A basic statusbar to replace gtk.StatusBar
    """
    def __init__(self, label):
        """
            Initializes the bar
            
            @param label: the gtk.Label to use for setting status messages
        """
        self.label = label

    def set_label(self, message, timeout=0):
        """
            Sets teh status label
        """
        self.label.set_label(message)
        if timeout:
            gobject.timeout_add(timeout, self.clear)

    def clear(self, *e):
        """
            Clears the label
        """
        self.label.set_label('')


class MenuRatingWidget(gtk.MenuItem):
    """
        A rating widget that can be used as a menu entry
    """

    def __init__(self, controller, _get_tracks):
        gtk.MenuItem.__init__(self)
        
        self.controller = controller
        self._get_tracks = _get_tracks
        
        self.hbox = gtk.HBox(spacing=3)
        self.hbox.pack_start(gtk.Label(_("Rating:")), False, False)
        self.image = gtk.image_new_from_pixbuf (self._get_rating_pixbuf(self._get_tracks()))
        self.hbox.pack_start(self.image, False, False, 12)
        
        self.add(self.hbox)
        
        self.connect('button-release-event', self._update_rating)
        event.add_callback(self.on_rating_change, 'rating_changed')
        event.add_callback(self.on_rating_change, 'exaile_loaded')


    def _update_rating(self, w, e):
        """
            Updates the rating of the tracks for this widget, meant to be used with a click event
        """
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
                if r == tracks[0].get_rating() and self._all_ratings_equal(tracks):
                    r = 0
                
                for track in tracks:
                    track.set_rating(r)
                
                event.log_event('rating_changed', self, r)


    def _all_ratings_equal(self, tracks = None):
        """
            Returns True if the rating of the tracks for this widget is equal
        """
        if not tracks:
            tracks = self._get_tracks()
            if not tracks:
                return False
        
        try:
            val = tracks[0].get_rating()
        except AttributeError:
            return False
        
        for track in tracks:
            if val != track.get_rating():
                return False
        
        return True


    def _get_rating_pixbuf(self, tracks):
        """
            Returns the pixbuf for the rating of the tracks if they're identical
            If they're not, returns a pixbuf for the rating 0
        """
        if not tracks:
            tracks = self._get_tracks()
            if not tracks:
                return self.controller.rating_images[0]
        
        if self._all_ratings_equal(tracks):
            try:
                return self.controller.rating_images[tracks[0].get_rating()]
            except IndexError:
                steps = settings.get_option('miscellaneous/rating_steps', 5)
                idx = tracks[0].get_rating()
                if idx > steps: idx = steps
                elif idx < 0: idx = 0
                return self.controller.rating_images[idx]
        else:
            return self.controller.rating_images[0]
            
    @gtkrun    
    def on_rating_change(self, type = None, object = None, data = None):
        """
            Handles possible changes of track ratings
        """
        self.image.set_from_pixbuf (self._get_rating_pixbuf (self._get_tracks()))
        self.realize()



def get_urls_for(items):
    """
        Returns the items' URLs
    """
    return [urllib.quote(item.get_loc().encode(common.get_default_encoding()))
        for item in items]
