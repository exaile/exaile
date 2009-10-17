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

from xl import xdg, event, cover, common, metadata, settings
from xlgui import guiutil, commondialogs
import gtk, gobject, time
import logging, traceback
logger = logging.getLogger(__name__)

from xl.nls import gettext as _
import gobject

COVER_WIDTH = 100
NOCOVER_IMAGE = xdg.get_data_path("images", "nocover.png")

class CoverManager(object):
    """
        Cover manager window
    """
    def __init__(self, parent, covers, collection):
        """
            Initializes the window
        """

        self.parent = parent
        self.collection = collection
        self.manager = covers

        self.cover_nodes = {}
        self.covers = {}
        self.track_dict = {}
        self._stopped = True

        self.builder = gtk.Builder()
        self.builder.add_from_file(xdg.get_data_path('ui/covermanager.glade'))

        self.window = self.builder.get_object('CoverManager')
        self.window.set_transient_for(parent)

        self.icons = self.builder.get_object('cover_icon_view')
        self.icons.connect('button-press-event', 
            self._on_button_press)
        self.progress = self.builder.get_object('progress')
        self.stop_button = self.builder.get_object('stop_button')
        self.model = gtk.ListStore(str, gtk.gdk.Pixbuf, object)
        self.icons.set_item_width(100)

        self.icons.set_text_column(0)
        self.icons.set_pixbuf_column(1)

        self._connect_events()
        self.window.show_all()
        gobject.idle_add(self._find_initial)
        self.menu = CoverMenu(self)

    def _on_button_press(self, button, event):
        """
            Called when someone clicks on the cover widget
        """
        if event.type == gtk.gdk._2BUTTON_PRESS:
            self.show_cover()
        elif event.button == 3:
            self.menu.popup(event)

        # select the current icon
        x, y = map(int, event.get_coords())
        path = self.icons.get_path_at_pos(x, y)
        if not path: return

        self.icons.select_path(path)

    def get_selected_cover(self):
        """
            Returns the currently selected cover tuple
        """
        paths = self.icons.get_selected_items()
        if not paths: return
        path = paths[0]

        iter = self.model.get_iter(path)
        return self.model.get_value(iter, 2)

    def show_cover(self, *e):
        """
            Shows the currently selected cover
        """
        
        item = self._get_selected_item()
        c = self.manager.coverdb.get_cover(item[0], item[1])
        
        # if there is no cover, use the nocover image from the selected widget
        if c == None:
            cover = self.covers[self.get_selected_cover()]
        else:
            cover = gtk.gdk.pixbuf_new_from_file(c)
        
        window = CoverWindow(self.parent, cover)
        window.show_all()

    def fetch_cover(self):
        """
            Fetches a cover for the current track
        """
        item = self._get_selected_item()
        if not item: return
        track = self.track_dict[item[0]][item[1]][0]
        window = CoverChooser(self.window, 
            self.manager, track)
        window.connect('cover-chosen', self.on_cover_chosen)

    def on_cover_chosen(self, object, cover):
        paths = self.icons.get_selected_items()
        if not paths: return None
        path = paths[0]

        iter = self.model.get_iter(path)
        item = self.model.get_value(iter, 2)

        image = gtk.gdk.pixbuf_new_from_file(cover)
        image = image.scale_simple(80, 80, gtk.gdk.INTERP_BILINEAR)
        self.covers[item] = image
        self.model.set_value(iter, 1, image)

    def _get_selected_item(self):
        """
            Returns the selected item
        """
        paths = self.icons.get_selected_items()
        if not paths: return None
        path = paths[0]

        iter = self.model.get_iter(path)
        item = self.model.get_value(iter, 2)
        return item

    def remove_cover(self, *e):
        item = self._get_selected_item()
        paths = self.icons.get_selected_items()
        self.manager.coverdb.remove_cover(item[0], item[1])
        self.covers[item] = self.nocover
        if not paths: return
        iter = self.model.get_iter(paths[0])
        self.model.set_value(iter, 1, self.nocover)

    def _find_initial(self):
        """
            Locates covers and sets the icons in the windows
        """
        tracks = self.collection.search('') # find all tracks

        items = []
        for track in tracks:
            try:
                (artist, album) = track.get_album_tuple()
            except KeyError:
                continue
            except TypeError:
                continue

            if not album or not artist: continue

            if not artist in self.track_dict:
                self.track_dict[artist] = {}

            if not album in self.track_dict[artist]:
                self.track_dict[artist][album] = []

            self.track_dict[artist][album].append(track)
            items.append((artist, album))

        items = list(set(items))
        self.items = items
        self.items.sort()

        nocover = gtk.gdk.pixbuf_new_from_file(NOCOVER_IMAGE)
        nocover = nocover.scale_simple(80, 80, gtk.gdk.INTERP_BILINEAR)
        self.nocover = nocover
        self.needs = 0
        for item in items:
            if not item[0] or not item[1]: continue
            try:
                cover = self.manager.coverdb.get_cover(item[0], item[1])
            except TypeError:
                cover = None

            if cover:
                try:
                    image = gtk.gdk.pixbuf_new_from_file(cover)
                    image = image.scale_simple(80, 80, gtk.gdk.INTERP_BILINEAR)
                except:
                    image = nocover
            else:
                image = nocover

            if image == nocover:
                self.needs += 1

            display = "%s - %s" % (item[0], item[1])
            if self.track_dict[item[0]][item[1]][0]['__compilation']:
                display = item[1]

            self.cover_nodes[item] = self.model.append(
                [display, image, item])
            self.covers[item] = image
        self.icons.set_model(self.model)
        self.progress.set_text('%d covers to fetch' % self.needs)

    def _connect_events(self):
        """
            Connects the various events
        """
        self.builder.connect_signals({
            'on_stop_button_clicked': self._toggle_find,
            'on_cancel_button_clicked': self._on_destroy
        })

        self.window.connect('delete-event', self._on_destroy)

    @common.threaded
    def _find_covers(self):
        """
            Finds covers for albums that don't already have one
        """
        self.count = 0
        self._stopped = False
        for item in self.items:
            if self._stopped:
                gobject.idle_add(self._do_stop)
                return
            starttime = time.time()
            if not self.covers[item] == self.nocover:
                continue

            try:
                c = self.manager.get_cover(self.track_dict[item[0]][item[1]][0], 
                    update_track=True)
            except cover.NoCoverFoundException:
                continue
            except:
                traceback.print_exc()
                logger.warning("No cover found")
                c = None

            if c:
                logger.info(c)
                node = self.cover_nodes[item]

                try:
                    image = gtk.gdk.pixbuf_new_from_file(c)
                    image = image.scale_simple(80, 80, gtk.gdk.INTERP_BILINEAR)

                    gobject.idle_add(self.model.set_value, node, 1, image)
                except:
                    traceback.print_exc()
        
            gobject.idle_add(self.progress.set_fraction, float(self.count) /
                float(self.needs))
            gobject.idle_add(self.progress.set_text, "%s/%s fetched" % (self.count,
                self.needs))

            self.count += 1

            if self.count % 20 == 0:
                logger.info("Saving cover database")
                self.manager.save_cover_db()

        # we're done!
        gobject.idle_add(self._do_stop)

    def _calculate_needed(self):
        """
            Calculates the number of needed covers
        """
        self.needs = 0
        for item in self.items:
            cover = self.covers[item]
            if cover == self.nocover:
                self.needs += 1

    def _do_stop(self):
        """
            Actually stop the finder thread
        """
        self._calculate_needed()
        self.progress.set_text(_('%d covers to fetch') % self.needs)
        self.progress.set_fraction(0)
        self._stopped = True
        self.manager.save_cover_db()
        self.stop_button.set_use_stock(False)
        self.stop_button.set_label(_('Start'))
        self.stop_button.set_image(gtk.image_new_from_stock('gtk-yes',
            gtk.ICON_SIZE_BUTTON))

    def _on_destroy(self, *e):
        self._do_stop()
        self.window.hide()

    def _toggle_find(self, *e):
        """
            Toggles cover finding
        """
        if self._stopped:
            self.stop_button.set_use_stock(True)
            self.stop_button.set_label('gtk-stop')
            self._find_covers()
        else:
            self._stopped = True
            self.stop_button.set_use_stock(False)
            self.stop_button.set_label(_('Start'))
            self.stop_button.set_image(gtk.image_new_from_stock('gtk-yes',
                gtk.ICON_SIZE_BUTTON))

class CoverMenu(guiutil.Menu):
    """
        Cover menu
    """
    def __init__(self, widget):
        """
            Initializes the menu
        """
        guiutil.Menu.__init__(self)
        self.widget = widget
        
        self.append(_('Show Cover'), self.on_show_clicked)
        self.append(_('Fetch Cover'), self.on_fetch_clicked)
        self.append(_('Remove Cover'), self.on_remove_clicked)

    def on_show_clicked(self, *e):
        """
            Shows the current cover
        """
        self.widget.show_cover()

    def on_fetch_clicked(self, *e):
        self.widget.fetch_cover()

    def on_remove_clicked(self, *e):
        self.widget.remove_cover()

class CoverWidget(gtk.EventBox):
    """
        Represents the cover widget displayed by the track information
    """
    __gsignals__ = {
        'cover-found': (gobject.SIGNAL_RUN_LAST, None, (object,)),
    }
    def __init__(self, main, covers, player):
        """
            Initializes the widget

            @param main: The Main window
            @param player: the xl.player.Player object
        """
        gtk.EventBox.__init__(self)
        self.image = guiutil.ScalableImageWidget()
        self.main = main
        self.current_track = None
        self.covers = covers
        self.player = player

        self.image.set_image_size(COVER_WIDTH, COVER_WIDTH)
        self.image.set_image(NOCOVER_IMAGE)
        self.add(self.image)
        self.image.show()
        
        if main:
            self.connect('button-press-event', self._on_button_press)

        event.add_callback(self.on_playback_start, 
                'playback_track_start', player)
        event.add_callback(self.on_playback_end, 
                'playback_player_end', player)
        self.menu = CoverMenu(self)

    def destroy(self):
        event.remove_callback(self.on_playback_start, 
                'playback_track_start', player)
        event.remove_callback(self.on_playback_end, 
                'playback_player_end', player)

    def show_cover(self):
        """
            Shows the current cover
        """
        window = CoverWindow(self.main.window, self.image.pixbuf)
        window.show_all()

    def fetch_cover(self):
        """
            Fetches a cover for the current track
        """
        if not self.player.current: return
        window = CoverChooser(self.main.window, 
            self.covers,
            self.player.current) 
        window.connect('cover-chosen', self.on_cover_chosen)

    def on_cover_chosen(self, object, cover):
        self.image.set_image(cover)

    def remove_cover(self):
        """
            Removes the cover for the current track from the database
        """
        self.covers.remove_cover(self.player.current)
        self.on_playback_end(None, None, None)

    def _on_button_press(self, button, event):
        """
            Called when someone clicks on the cover widget
        """
        if event.type == gtk.gdk._2BUTTON_PRESS:
            window = CoverWindow(self.main.window, self.image.pixbuf)
            window.show_all()
        elif event.button == 3:
            if self.player.current:
                self.menu.popup(event)

    @common.threaded
    def on_playback_start(self, type, player, track):
        """
            Called when playback starts.  Fetches album covers, and displays
            them
        """
        self.current_track = track
        nocover = xdg.get_data_path('images/nocover.png')
        self.loc = nocover
        self.emit('cover-found', nocover)
        gobject.idle_add(self.image.set_image, xdg.get_data_path('images/nocover.png'))

        if (settings.get_option('covers/automatic_fetching', True)):
            try:
                cov = self.covers.get_cover(self.current_track,
                    update_track=True)
            except cover.NoCoverFoundException:
                logger.warning("No covers found")
                gobject.idle_add(self.image.set_image, xdg.get_data_path('images/nocover.png'))
                return
        else:
            try:
                item = track.get_album_tuple()
                if item[0] and item[1]: 
                    cov = self.coverdb.get_cover(item[0], item[1]) 
            except TypeError: # one of the fields is missing
                pass
            except AttributeError:
                pass
            
            if not cov:
                gobject.idle_add(self.image.set_image, xdg.get_data_path('images/nocover.png'))
                return

        if self.player.current == self.current_track:
            self.image.loc = cov
            gobject.idle_add(self.image.set_image_data, cover.get_cover_data(cov))
            self.loc = cov
            gobject.idle_add(self._fire_event)

    def _fire_event(self):
        self.emit('cover-found', self.loc)

    def on_playback_end(self, type, player, object):
        """
            Called when playback stops.  Resets to the nocover image
        """
        nocover = xdg.get_data_path('images/nocover.png')
        self.loc = nocover
        self.image.set_image(nocover)
        self.emit('cover-found', nocover)

class CoverWindow(object):
    """Shows the cover in a simple image viewer"""

    def __init__(self, parent, cover, title=''):
        """Initializes and shows the cover"""
        self.builder = gtk.Builder()
        self.builder.add_from_file(xdg.get_data_path('ui/coverwindow.glade'))
        self.builder.connect_signals(self)
        self.cover_window = self.builder.get_object('CoverWindow')
        self.layout = self.builder.get_object('layout')
        self.toolbar = self.builder.get_object('toolbar')
        self.zoom_in = self.builder.get_object('zoom_in')
        self.zoom_in.connect('clicked', self.zoom_in_clicked)
        self.zoom_out = self.builder.get_object('zoom_out')
        self.zoom_out.connect('clicked', self.zoom_out_clicked)
        self.zoom_100 = self.builder.get_object('zoom_100')
        self.zoom_100.connect('clicked', self.zoom_100_clicked)
        self.zoom_fit = self.builder.get_object('zoom_fit')
        self.zoom_fit.connect('clicked', self.zoom_fit_clicked)
        self.image = self.builder.get_object('image')
        self.statusbar = self.builder.get_object('statusbar')
        self.scrolledwindow = self.builder.get_object('scrolledwindow')
        self.scrolledwindow.set_hadjustment(self.layout.get_hadjustment())
        self.scrolledwindow.set_vadjustment(self.layout.get_vadjustment())
        self.cover_window.set_title(title)
        self.cover_window.set_transient_for(parent)
        self.cover_window_width = 500
        self.cover_window_height = 500 + self.toolbar.size_request()[1] + \
                                   self.statusbar.size_request()[1]
        self.cover_window.set_default_size(self.cover_window_width, \
                                           self.cover_window_height)
        if type(cover) == str or type(cover) == unicode:
            self.image_original_pixbuf = gtk.gdk.pixbuf_new_from_file(cover)
        else:
            self.image_original_pixbuf = cover

        self.image_pixbuf = self.image_original_pixbuf
        self.min_percent = 1
        self.max_percent = 500
        self.ratio = 1.5
        self.image_interp = gtk.gdk.INTERP_BILINEAR
        self.image_fitted = True
        self.set_ratio_to_fit()
        self.update_widgets()

    def show_all(self):
        self.cover_window.show_all()
 
    def available_image_width(self):
        """Returns the available horizontal space for the image"""
        return self.cover_window.get_size()[0]

    def available_image_height(self):
        """Returns the available vertical space for the image"""
        return self.cover_window.get_size()[1] - \
               self.toolbar.size_request()[1] - \
               self.statusbar.size_request()[1]

    def center_image(self):
        """Centers the image in the layout"""
        new_x = max(0, int((self.available_image_width() - \
                            self.image_pixbuf.get_width()) / 2))
        new_y = max(0, int((self.available_image_height() - \
                            self.image_pixbuf.get_height()) / 2))
        self.layout.move(self.image, new_x, new_y)

    def update_widgets(self):
        """Updates image, layout, scrolled window, tool bar and status bar"""
        if self.cover_window.window:
            self.cover_window.window.freeze_updates()
        self.apply_zoom()
        self.layout.set_size(self.image_pixbuf.get_width(), \
                             self.image_pixbuf.get_height())
        if self.image_fitted or \
           (self.image_pixbuf.get_width() == self.available_image_width() and \
           self.image_pixbuf.get_height() == self.available_image_height()):
            self.scrolledwindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_NEVER)
        else:
            self.scrolledwindow.set_policy(gtk.POLICY_AUTOMATIC,
                                           gtk.POLICY_AUTOMATIC)
        percent = int(100 * self.image_ratio)
        message = str(self.image_original_pixbuf.get_width()) + " x " + \
                      str(self.image_original_pixbuf.get_height()) + \
                      " pixels " + str(percent) + '%'
        self.zoom_in.set_sensitive(percent < self.max_percent)
        self.zoom_out.set_sensitive(percent > self.min_percent)
        self.statusbar.pop(self.statusbar.get_context_id(''))
        self.statusbar.push(self.statusbar.get_context_id(''), message)
        self.image.set_from_pixbuf(self.image_pixbuf)
        self.center_image()
        if self.cover_window.window:
            self.cover_window.window.thaw_updates()

    def apply_zoom(self):
        """Scales the image if needed"""
        new_width = int(self.image_original_pixbuf.get_width() * \
                        self.image_ratio)
        new_height = int(self.image_original_pixbuf.get_height() * \
                         self.image_ratio)
        if new_width != self.image_pixbuf.get_width() or \
           new_height != self.image_pixbuf.get_height(): 
            self.image_pixbuf = self.image_original_pixbuf.scale_simple(new_width, \
                                  new_height, self.image_interp)

    def set_ratio_to_fit(self):
        """Calculates and sets the needed ratio to show the full image"""
        width_ratio = float(self.image_original_pixbuf.get_width()) / \
                            self.available_image_width()
        height_ratio = float(self.image_original_pixbuf.get_height()) / \
                             self.available_image_height()
        self.image_ratio = 1 / max(1, width_ratio, height_ratio)

    def cover_window_destroy(self, widget):
        self.cover_window.destroy()

    def zoom_in_clicked(self, widget):
        self.image_fitted = False
        self.image_ratio *= self.ratio 
        self.update_widgets()

    def zoom_out_clicked(self, widget):
        self.image_fitted = False
        self.image_ratio *= 1 / self.ratio
        self.update_widgets()

    def zoom_100_clicked(self, widget):
        self.image_fitted = False
        self.image_ratio = 1
        self.update_widgets()

    def zoom_fit_clicked(self, widget):
        self.image_fitted = True
        self.set_ratio_to_fit()
        self.update_widgets()

    def cover_window_size_allocate(self, widget, allocation):
        if self.cover_window_width != allocation.width or \
           self.cover_window_height != allocation.height:
            if self.image_fitted:
                self.set_ratio_to_fit()
            self.update_widgets()
            self.cover_window_width = allocation.width
            self.cover_window_height = allocation.height

class CoverChooser(gobject.GObject):
    """
        Fetches all album covers for a string, and allows the user to choose
        one out of the list
    """
    __gsignals__ = {
        'cover-chosen': (gobject.SIGNAL_RUN_LAST, None, (str,)),
    }
    def __init__(self, parent, covers, track, search=None):
        """
            Expects the parent control, a track, an an optional search string
        """
        gobject.GObject.__init__(self)
        self.manager = covers
        self.parent = parent
        self.builder = gtk.Builder()
        self.builder.add_from_file(xdg.get_data_path('ui/coverchooser.glade'))
        self.window = self.builder.get_object('CoverChooser')

        try:
            tempartist = ' / '.join(track['artist'])
        except TypeError:
            tempartist = ''
        try:
            tempalbum = ' / '.join(track['album'])
        except TypeError:
            tempalbum = ''
        
        self.window.set_title("%s - %s" % (tempartist,tempalbum))
        self.window.set_transient_for(parent)

        self.track = track
        self.current = 0
        self.prev = self.builder.get_object('cover_back_button')
        self.prev.connect('clicked', self.go_prev)
        self.prev.set_sensitive(False)
        self.next = self.builder.get_object('cover_forward_button')
        self.next.connect('clicked', self.go_next)
        self.builder.get_object('cover_newsearch_button').connect('clicked',
            self.new_search)
        self.builder.get_object('cover_cancel_button').connect('clicked',
            lambda *e: self.window.destroy())
        self.ok = self.builder.get_object('cover_ok_button')
        self.ok.connect('clicked',
            self.on_ok)
        self.box = self.builder.get_object('cover_image_box')
        self.cover = guiutil.ScalableImageWidget()
        self.cover.set_image_size(350, 350)
        self.box.pack_start(self.cover, True, True)

        self.last_search = "%s - %s"  % (tempartist,tempalbum)

        self.fetch_cover(track)

    def new_search(self, widget=None):
        """
            Creates a new search string
        """
        dialog = commondialogs.TextEntryDialog(
            _("Enter the search text"), _("Enter the search text"))
        dialog.set_value(self.last_search)
        result = dialog.run()
        if result == gtk.RESPONSE_OK:
            self.last_search = dialog.get_value()
            self.window.hide()

            self.fetch_cover(self.last_search)

    @common.threaded
    def fetch_cover(self, search):
        """
            Searches for a cover
        """
        self.covers = []
        self.current = 0
        
        if type(search) == str or type(search) == unicode:
            covers = self.manager.search_covers(search)
        else:
            covers = self.manager.find_covers(search)

        if covers:
            self.covers = covers
            gobject.idle_add(self.show_cover, covers[0])
        else:
            commondialogs.error(self.parent, _('No covers found'))
            self.window.show_all()

    def on_ok(self, widget=None):
        """
            Chooses the current cover and saves it to the database
        """
        track = self.track
        cover = self.covers[self.current]

        self.manager.coverdb.set_cover(
            metadata.j(track['artist']),
            metadata.j(track['album']),
            cover)

        self.emit('cover-chosen', cover)
        self.window.destroy()

    def go_next(self, widget):
        """
            Shows the next cover
        """
        if self.current + 1 >= len(self.covers): return
        self.current = self.current + 1
        self.show_cover(self.covers[self.current])
        if self.current + 1 >= len(self.covers):
            self.next.set_sensitive(False)
        if self.current - 1 >= 0:
            self.prev.set_sensitive(True)

    def go_prev(self, widget):
        """
            Shows the previous cover
        """
        if self.current - 1 < 0: return
        self.current = self.current - 1
        self.show_cover(self.covers[self.current])

        if self.current + 1 < len(self.covers):
            self.next.set_sensitive(True)
        if self.current - 1 < 0:
            self.prev.set_sensitive(False)

    def show_cover(self, c):
        """
            Shows the current cover
        """
        logger.info(c)
        self.cover.set_image_data(cover.get_cover_data(c))
        self.window.show_all()
