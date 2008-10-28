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

from xl import xdg, event, cover, common
from xlgui import guiutil
import gtk, gobject, gtk.glade, time
import logging, traceback
logger = logging.getLogger(__name__)

from xl.nls import gettext as _

COVER_WIDTH = 100
NOCOVER_IMAGE = xdg.get_data_path("images/nocover.png")

class CoverManager(object):
    """
        Cover manager window
    """
    def __init__(self, parent, covers, collection):
        """
            Initializes the window
        """

        self.collection = collection
        self.manager = covers

        self.cover_nodes = {}
        self.covers = {}
        self._stopped = True

        self.xml = gtk.glade.XML(xdg.get_data_path('glade/covermanager.glade'),
            'CoverManager', 'exaile')

        self.window = self.xml.get_widget('CoverManager')
        self.window.set_transient_for(parent)

        self.icons = self.xml.get_widget('cover_icon_view')
        self.icons.connect('button-press-event', 
            self._on_button_press)
        self.progress = self.xml.get_widget('progress')
        self.stop_button = self.xml.get_widget('stop_button')
        self.model = gtk.ListStore(str, gtk.gdk.Pixbuf, object)
        self.icons.set_item_width(90)

        self.icons.set_text_column(0)
        self.icons.set_pixbuf_column(1)

        self._connect_events()
        self.window.show_all()
        gobject.idle_add(self._find_initial)
        self.menu = gtk.CoverMenu(self)

    def _on_button_press(self, button, event):
        """
            Called when someone clicks on the cover widget
        """
        if event.type == gtk.gdk._2BUTTON_PRESS:
            self.show_cover()
        elif event.button == 3:
            self.menu.popup(event)

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
        cover = self.covers[self.get_selected_cover()]
        window = CoverWindow(self.parent, cover)
        window.show_all()

    def fetch_cover(self, *e):
        pass

    def remove_cover(self, *e):
        pass

    def _find_initial(self):
        """
            Locates covers and sets the icons in the windows
        """
        tracks = self.collection.search('') # find all tracks

        items = list(set([('/'.join(t['artist']), '/'.join(t['album'])) for t
            in tracks if t['artist'] and t['album']]))
        self.items = items
        self.items.sort()

        nocover = gtk.gdk.pixbuf_new_from_file(NOCOVER_IMAGE)
        nocover = nocover.scale_simple(80, 80, gtk.gdk.INTERP_BILINEAR)
        self.nocover = nocover
        self.needs = 0
        for item in items:
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

            self.cover_nodes[item] = self.model.append(
                ["%s - %s" % (item[0], item[1]), 
                image, item])
            self.covers[item] = image
        self.icons.set_model(self.model)
        self.progress.set_text('%d covers to fetch' % self.needs)

    def _connect_events(self):
        """
            Connects the various events
        """
        self.xml.signal_autoconnect({
            'stop_button_clicked': self._toggle_find,
            'cancel_button_clicked': self._on_destroy
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
                c = self.manager.get_cover(
                    {
                        'artist': [item[0]],
                        'album': [item[1]],
                    }, update_track=True)
            except:
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

            # wait at least 1 second until the next attempt
            waittime = 1 - (time.time() - starttime)
            if waittime > 0: time.sleep(waittime)
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
        self.progress.set_text('%d covers to fetch' % self.needs)
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
        Represents the album art widget displayed by the track information
    """
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
        self.image.set_image(xdg.get_data_path('images/nocover.png'))
        self.add(self.image)
        self.image.show()
        
        self.connect('button-press-event', self._on_button_press)

        event.add_callback(self.on_playback_start, 'playback_start', player)
        event.add_callback(self.on_playback_end, 'playback_end', player)
        self.menu = CoverMenu(self)

    def show_cover(self):
        """
            Shows the current cover
        """
        window = CoverWindow(self.main.window, self.image.loc)
        window.show_all()

    def fetch_cover(self):
        """
            Fetches a cover for the current track
        """
        self.on_playback_start(None, self.main.player, None)

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
            window = CoverWindow(self.main.window, self.image.loc)
            window.show_all()
        elif event.button == 3:
            if self.player.current:
                self.menu.popup(event)

    @common.threaded
    def on_playback_start(self, type, player, object):
        """
            Called when playback starts.  Fetches album covers, and displays
            them
        """
        self.current_track = player.current

        try:
            cov = self.covers.get_cover(self.current_track,
                update_track=True)
        except cover.NoCoverFoundException:
            logger.warning("No covers found")
            self.image.set_image(xdg.get_data_path('images/nocover.png'))
            return

        if self.player.current == self.current_track:
            gobject.idle_add(self.image.set_image, cov)
            self.loc = cov

    def on_playback_end(self, type, player, object):
        """
            Called when playback stops.  Resets to the nocover image
        """
        self.image.set_image(xdg.get_data_path('images/nocover.png'))

class CoverWindow(object):
    """Shows the cover in a simple image viewer"""

    def __init__(self, parent, cover, title=''):
        """Initializes and shows the cover"""
        self.widgets = gtk.glade.XML(xdg.get_data_path('glade/coverwindow.glade'), 
            'CoverWindow', 'exaile')
        self.widgets.signal_autoconnect(self)
        self.cover_window = self.widgets.get_widget('CoverWindow')
        self.layout = self.widgets.get_widget('layout')
        self.toolbar = self.widgets.get_widget('toolbar')
        self.zoom_in = self.widgets.get_widget('zoom_in')
        self.zoom_in.connect('clicked', self.zoom_in_clicked)
        self.zoom_out = self.widgets.get_widget('zoom_out')
        self.zoom_out.connect('clicked', self.zoom_out_clicked)
        self.zoom_100 = self.widgets.get_widget('zoom_100')
        self.zoom_100.connect('clicked', self.zoom_100_clicked)
        self.zoom_fit = self.widgets.get_widget('zoom_fit')
        self.zoom_fit.connect('clicked', self.zoom_fit_clicked)
        self.image = self.widgets.get_widget('image')
        self.statusbar = self.widgets.get_widget('statusbar')
        self.scrolledwindow = self.widgets.get_widget('scrolledwindow')
        self.scrolledwindow.set_hadjustment(self.layout.get_hadjustment())
        self.scrolledwindow.set_vadjustment(self.layout.get_vadjustment())
        self.cover_window.set_title(title)
        self.cover_window.set_transient_for(parent)
        self.cover_window_width = 500
        self.cover_window_height = 500 + self.toolbar.size_request()[1] + \
                                   self.statusbar.size_request()[1]
        self.cover_window.set_default_size(self.cover_window_width, \
                                           self.cover_window_height)
        self.image_original_pixbuf = gtk.gdk.pixbuf_new_from_file(cover)
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
