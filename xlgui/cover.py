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

import logging
import os
import os.path
import tempfile
import time
import threading
import traceback

import cairo
import gio
import glib
import gobject
import gtk

from xl import (
    common,
    event,
    metadata,
    providers,
    settings,
    xdg
)
from xl.covers import MANAGER as cover_manager
from xl.nls import gettext as _
import xlgui
from xlgui import (
    guiutil,
    icons
)
from xlgui.widgets import dialogs
logger = logging.getLogger(__name__)

class CoverManager(object):
    """
        Cover manager window
    """
    def __init__(self, parent, collection):
        """
            Initializes the window
        """
        self.parent = parent
        self.collection = collection

        self.cover_nodes = {}
        self.covers = {}
        self.track_dict = {}
        self._stopped = True

        self.builder = gtk.Builder()
        self.builder.add_from_file(xdg.get_data_path('ui/covermanager.ui'))

        self.window = self.builder.get_object('CoverManager')
        self.window.set_transient_for(parent)

        self.message = dialogs.MessageBar(
            parent=self.builder.get_object('content_area'),
            buttons=gtk.BUTTONS_CLOSE
        )

        self.icons = self.builder.get_object('cover_icon_view')
        self.icons.connect('button-press-event',
            self._on_button_press)
        self.progress = self.builder.get_object('progress')
        self.start_button = self.builder.get_object('start_button')
        self.model = gtk.ListStore(str, gtk.gdk.Pixbuf, object)
        self.icons.set_item_width(100)

        self.icons.set_text_column(0)
        self.icons.set_pixbuf_column(1)

        self.nocover = icons.MANAGER.pixbuf_from_data(
            cover_manager.get_default_cover(), (80, 80))

        self._connect_events()
        self.window.show_all()
        glib.idle_add(self._find_initial)
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
        if path:
            self.icons.select_path(path)

    def get_selected_cover(self):
        """
            Returns the currently selected cover tuple
        """
        paths = self.icons.get_selected_items()
        if paths:
            path = paths[0]
            iter = self.model.get_iter(path)
            return self.model.get_value(iter, 2)

    def show_cover(self, *e):
        """
            Shows the currently selected cover
        """
        item = self._get_selected_item()
        track = self.track_dict[item][0]
        cover_data = cover_manager.get_cover(track)

        pixbuf = icons.MANAGER.pixbuf_from_data(cover_data)

        if pixbuf:
            window = CoverWindow(self.parent, pixbuf,
                track.get_tag_display('title'))
            window.show_all()

    def fetch_cover(self):
        """
            Fetches a cover for the current track
        """
        item = self._get_selected_item()
        if item:
            track = self.track_dict[item][0]
            window = CoverChooser(self.window, track)
            window.connect('cover-chosen', self.on_cover_chosen)

    def on_cover_chosen(self, object, cover_data):
        paths = self.icons.get_selected_items()
        if not paths:
            return None
        row = self.model[paths[0]]
        item = row[2]

        pixbuf = icons.MANAGER.pixbuf_from_data(
            cover_data, (80, 80))
        self.covers[item] = pixbuf
        row[1] = pixbuf

    def _get_selected_item(self):
        """
            Returns the selected item
        """
        paths = self.icons.get_selected_items()
        if not paths:
            return None
        path = paths[0]
        iter = self.model.get_iter(path)
        item = self.model.get_value(iter, 2)
        return item

    def remove_cover(self, *e):
        item = self._get_selected_item()
        paths = self.icons.get_selected_items()
        track = self.track_dict[item][0]
        cover_manager.remove_cover(track)
        self.covers[item] = self.nocover
        if paths:
            iter = self.model.get_iter(paths[0])
            self.model.set_value(iter, 1, self.nocover)

    def _find_initial(self):
        """
            Locates covers and sets the icons in the windows
        """
        items = set()
        for track in self.collection:
            try:
                artist = track.get_tag_raw('artist')[0]
                album = track.get_tag_raw('album')[0]
            except TypeError:
                continue

            if not album or not artist:
                continue

            item = (artist, album)

            try:
                self.track_dict[item].append(track)
            except KeyError:
                self.track_dict[item] = [track]

            items.add(item)

        self.items = list(items)
        self.items.sort()

        self.needs = 0
        for item in self.items:
            cover_avail = cover_manager.get_cover(self.track_dict[item][0],
                set_only=True)

            if cover_avail:
                try:
                    image = icons.MANAGER.pixbuf_from_data(
                        cover_avail, size=(80,80))
                except glib.GError:
                    image = self.nocover
                    self.needs += 1
            else:
                image = self.nocover
                self.needs += 1

            display = "%s - %s" % item

            self.cover_nodes[item] = self.model.append([display, image, item])
            self.covers[item] = image
        self.icons.set_model(self.model)
        self.progress.set_text(_('%d covers to fetch') % self.needs)

    def _connect_events(self):
        """
            Connects the various events
        """
        self.builder.connect_signals({
            'on_close_button_clicked': self._on_destroy,
            'on_start_button_clicked': self._toggle_find,
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
                glib.idle_add(self._do_stop)
                return
            starttime = time.time()
            if not self.covers[item] == self.nocover:
                continue

            c = cover_manager.get_cover(self.track_dict[item][0],
                    save_cover=True)

            if c:
                node = self.cover_nodes[item]
                try:
                    image = icons.MANAGER.pixbuf_from_data(c, size=(80,80))
                except glib.GError:
                    c = None
                else:
                    glib.idle_add(self.model.set_value, node, 1, image)

            glib.idle_add(self.progress.set_fraction, float(self.count) /
                float(self.needs))
            glib.idle_add(self.progress.set_text, "%s/%s fetched" %
                    (self.count, self.needs))

            self.count += 1

            if self.count % 20 == 0:
                logger.debug("Saving cover database")
                cover_manager.save()

        glib.idle_add(self._do_stop)

    def _calculate_needed(self):
        """
            Calculates the number of needed covers
        """
        self.needs = 0
        for item in self.items:
            cvr = self.covers[item]
            if cvr == self.nocover:
                self.needs += 1

    def _do_stop(self):
        """
            Actually stop the finder thread
        """
        self._calculate_needed()
        self.progress.set_text(_('%d covers to fetch') % self.needs)
        self.progress.set_fraction(0)
        self._stopped = True
        cover_manager.save()
        self.start_button.set_use_stock(False)
        self.start_button.set_label(_('Start'))
        self.start_button.set_image(gtk.image_new_from_stock(gtk.STOCK_YES,
            gtk.ICON_SIZE_BUTTON))

    def _on_destroy(self, *e):
        self._do_stop()
        self.window.hide()

    def _toggle_find(self, *e):
        """
            Toggles cover finding
        """
        if self._stopped:
            self.start_button.set_use_stock(True)
            self.start_button.set_label(gtk.STOCK_STOP)
            self._find_covers()
        else:
            self._stopped = True
            self.start_button.set_use_stock(False)
            self.start_button.set_label(_('Start'))
            self.start_button.set_image(gtk.image_new_from_stock(gtk.STOCK_YES,
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
    def __init__(self, image, player):
        """
            Initializes the widget

            :param image: the image to wrap
            :type image: :class:`gtk.Image`
        """
        gtk.EventBox.__init__(self)
        self._player = player
        self.image = image
        self.cover_data = None
        self.menu = CoverMenu(self)
        self.parent_window = image.get_toplevel()
        self.filename = None

        guiutil.gtk_widget_replace(image, self)
        self.add(self.image)
        self.set_blank()
        self.image.show()

        event.add_callback(self.on_playback_start,
                'playback_track_start', self._player)
        event.add_callback(self.on_playback_end,
                'playback_player_end', self._player)
        event.add_callback(self.on_quit_application,
                'quit_application')

        if settings.get_option('gui/use_alpha', False):
            self.set_app_paintable(True)

    def destroy(self):
        """
            Cleanups
        """
        if self.filename is not None and os.path.exists(self.filename):
            os.remove(self.filename)
            self.filename = None

        event.remove_callback(self.on_playback_start,
                'playback_track_start', self._player)
        event.remove_callback(self.on_playback_end,
                'playback_player_end', self._player)
        event.remove_callback(self.on_quit_application,
                'quit-application')

    def show_cover(self):
        """
            Shows the current cover
        """
        if not self.cover_data:
            return

        pixbuf = icons.MANAGER.pixbuf_from_data(self.cover_data)

        if pixbuf:
            window = CoverWindow(self.parent_window, pixbuf,
                self._player.current.get_tag_display('title'))
            window.show_all()

    def fetch_cover(self):
        """
            Fetches a cover for the current track
        """
        current_track = self._player.current
        if not current_track: 
            return
            
        window = CoverChooser(self.parent_window, current_track)
        window.connect('cover-chosen', self.on_cover_chosen)

    def remove_cover(self):
        """
            Removes the cover for the current track from the database
        """
        cover_manager.remove_cover(self._player.current)
        self.set_blank()

    def set_blank(self):
        """
            Sets the default cover to display
        """
        pixbuf = icons.MANAGER.pixbuf_from_data(
            cover_manager.get_default_cover())
        self.image.set_from_pixbuf(pixbuf)
        self.set_drag_source_enabled(False)
        self.cover_data = None

        self.emit('cover-found', None)

    def set_drag_source_enabled(self, enabled):
        """
            Changes the behavior for drag and drop

            :param drag_enabled: Whether to  allow
                drag to other applications
            :type enabled: bool
        """
        if enabled == self.get_data('drag_source_enabled'):
            return

        if enabled:
            self.drag_source_set(gtk.gdk.BUTTON1_MASK,
                [('text/uri-list', 0, 0)],
                gtk.gdk.ACTION_DEFAULT |
                gtk.gdk.ACTION_MOVE
            )
        else:
            self.drag_source_unset()

        self.set_data('drag_source_enabled', enabled)

    def do_button_press_event(self, event):
        """
            Called when someone clicks on the cover widget
        """
        if self._player.current is None or self.parent_window is None:
            return

        if event.type == gtk.gdk._2BUTTON_PRESS:
            self.show_cover()
        elif event.button == 3:
            self.menu.popup(event)

    def do_expose_event(self, event):
        """
            Paints alpha transparency
        """
        opacity = 1 - settings.get_option('gui/transparency', 0.3)
        context = self.window.cairo_create()
        background = self.style.bg[gtk.STATE_NORMAL]
        context.set_source_rgba(
            float(background.red) / 256**2,
            float(background.green) / 256**2,
            float(background.blue) / 256**2,
            opacity
        )
        context.set_operator(cairo.OPERATOR_SOURCE)
        context.paint()

        gtk.EventBox.do_expose_event(self, event)

    def do_drag_begin(self, context):
        """
            Sets the cover as drag icon
        """
        self.drag_source_set_icon_pixbuf(self.image.get_pixbuf())

    def do_drag_data_get(self, context, selection, info, time):
        """
            Fills the selection with the current cover
        """
        if self.filename is None:
            self.filename = tempfile.mkstemp(prefix='exaile_cover_')[1]

        pixbuf = icons.MANAGER.pixbuf_from_data(self.cover_data)
        pixbuf.save(self.filename, 'png')
        selection.set_uris([gio.File(self.filename).get_uri()])

    def do_drag_data_delete(self, context):
        """
            Cleans up after drag from cover widget
        """
        if self.filename is not None and os.path.exists(self.filename):
            os.remove(self.filename)
            self.filename = None

    def do_drag_data_received(self, context, x, y, selection, info, time):
        """
            Sets the cover based on the dragged data
        """
        if self._player.current is not None:
            uri = selection.get_uris()[0]
            db_string = 'localfile:%s' % uri

            try:
                stream = gio.File(uri).read()
            except gio.Error:
                return

            self.cover_data = stream.read()
            width = settings.get_option('gui/cover_width', 100)
            pixbuf = icons.MANAGER.pixbuf_from_data(self.cover_data,
                (width, width))

            if pixbuf is not None:
                self.image.set_from_pixbuf(pixbuf)
                cover_manager.set_cover(self._player.current, db_string,
                    self.cover_data)

    def on_cover_chosen(self, object, cover_data):
        """
            Called when a cover is selected
            from the coverchooser
        """
        width = settings.get_option('gui/cover_width', 100)
        pixbuf = icons.MANAGER.pixbuf_from_data(cover_data, (width, width))
        self.image.set_from_pixbuf(pixbuf)
        self.set_drag_source_enabled(True)
        self.cover_data = cover_data

        self.emit('cover-found', pixbuf)

    @common.threaded
    def on_playback_start(self, type, player, track):
        """
            Called when playback starts.  Fetches album covers, and displays
            them
        """
        glib.idle_add(self.set_blank)
        glib.idle_add(self.drag_dest_set,
            gtk.DEST_DEFAULT_ALL,
            [('text/uri-list', 0, 0)],
            gtk.gdk.ACTION_COPY |
            gtk.gdk.ACTION_DEFAULT |
            gtk.gdk.ACTION_MOVE
        )

        fetch = not settings.get_option('covers/automatic_fetching', True)
        cover_data = cover_manager.get_cover(track, set_only=fetch)

        if not cover_data:
            return

        if player.current == track:
            glib.idle_add(self.on_cover_chosen, None, cover_data)

    def on_playback_end(self, type, player, object):
        """
            Called when playback stops.  Resets to the nocover image
        """
        glib.idle_add(self.drag_dest_unset)
        glib.idle_add(self.set_blank)

    def on_quit_application(self, type, exaile, nothing):
        """
            Cleans up temporary files
        """
        if self.filename is not None and os.path.exists(self.filename):
            os.remove(self.filename)
            self.filename = None

class CoverWindow(object):
    """Shows the cover in a simple image viewer"""

    def __init__(self, parent, pixbuf, title=None):
        """Initializes and shows the cover"""
        self.builder = gtk.Builder()
        self.builder.add_from_file(xdg.get_data_path('ui/coverwindow.ui'))
        self.builder.connect_signals(self)

        self.cover_window = self.builder.get_object('CoverWindow')
        self.layout = self.builder.get_object('layout')
        self.toolbar = self.builder.get_object('toolbar')
        self.zoom_in_button = self.builder.get_object('zoom_in_button')
        self.zoom_out_button = self.builder.get_object('zoom_out_button')
        self.zoom_100_button = self.builder.get_object('zoom_100_button')
        self.zoom_fit_button = self.builder.get_object('zoom_fit_button')
        self.close_button = self.builder.get_object('close_button')
        self.image = self.builder.get_object('image')
        self.statusbar = self.builder.get_object('statusbar')
        self.scrolledwindow = self.builder.get_object('scrolledwindow')
        self.scrolledwindow.set_hadjustment(self.layout.get_hadjustment())
        self.scrolledwindow.set_vadjustment(self.layout.get_vadjustment())

        if title is None:
            title = _('Cover')
        else:
            title = _('Cover for %s') % title

        self.cover_window.set_title(title)
        self.cover_window.set_transient_for(parent)
        self.cover_window_width = 500
        self.cover_window_height = 500 + self.toolbar.size_request()[1] + \
                                   self.statusbar.size_request()[1]
        self.cover_window.set_default_size(self.cover_window_width, \
                                           self.cover_window_height)

        self.image_original_pixbuf = pixbuf
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
        self.zoom_in_button.set_sensitive(percent < self.max_percent)
        self.zoom_out_button.set_sensitive(percent > self.min_percent)
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

    def on_zoom_in_button_clicked(self, widget):
        """
            Zooms into the image
        """
        self.image_fitted = False
        self.image_ratio *= self.ratio
        self.update_widgets()

    def on_zoom_out_button_clicked(self, widget):
        """
            Zooms out of the image
        """
        self.image_fitted = False
        self.image_ratio *= 1 / self.ratio
        self.update_widgets()

    def on_zoom_100_button_clicked(self, widget):
        """
            Restores the original image zoom
        """
        self.image_fitted = False
        self.image_ratio = 1
        self.update_widgets()

    def on_zoom_fit_button_clicked(self, widget):
        """
            Zooms the image to fit the window width
        """
        self.image_fitted = True
        self.set_ratio_to_fit()
        self.update_widgets()

    def on_close_button_clicked(self, widget):
        """
            Hides the window
        """
        self.cover_window.hide_all()

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
        'covers-fetched': (
            gobject.SIGNAL_RUN_LAST,
            None,
            (object,)
        ),
        'cover-chosen': (
            gobject.SIGNAL_RUN_LAST,
            None,
            (object,)
        ),
        'message': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_BOOLEAN,
            (gtk.MessageType, gobject.TYPE_STRING),
            gobject.signal_accumulator_true_handled
        )
    }
    def __init__(self, parent, track, search=None):
        """
            Expects the parent control, a track, an an optional search string
        """
        gobject.GObject.__init__(self)
        self.parent = parent
        self.builder = gtk.Builder()
        self.builder.add_from_file(xdg.get_data_path('ui/coverchooser.ui'))
        self.builder.connect_signals(self)
        self.window = self.builder.get_object('CoverChooser')

        tempartist = track.get_tag_display('artist')
        tempalbum = track.get_tag_display('album')
        self.window.set_title(_("Cover options for %(artist)s - %(album)s") % {
            'artist': tempartist,
            'album': tempalbum
        })
        self.window.set_transient_for(parent)

        self.message = dialogs.MessageBar(
            parent=self.builder.get_object('main_container'),
            buttons=gtk.BUTTONS_CLOSE
        )
        self.message.connect('response', self.on_message_response)

        self.track = track
        self.covers = []
        self.current = 0

        self.cover = guiutil.ScalableImageWidget()
        self.cover.set_image_size(350, 350)

        self.cover_image_box = self.builder.get_object('cover_image_box')

        self.loading_indicator = gtk.Alignment()
        self.loading_indicator.props.xalign = 0.5
        self.loading_indicator.props.yalign = 0.5
        self.loading_indicator.set_size_request(350, 350)
        self.cover_image_box.pack_start(self.loading_indicator)

        try:
            spinner = gtk.Spinner()
            spinner.set_size_request(100, 100)
            spinner.start()
            self.loading_indicator.add(spinner)
        except AttributeError: # Older than GTK 2.20 and PyGTK 2.22
            self.loading_indicator.add(gtk.Label(_('Loading...')))

        self.size_label = self.builder.get_object('size_label')
        self.source_label = self.builder.get_object('source_label')

        self.covers_model = self.builder.get_object('covers_model')
        self.previews_box = self.builder.get_object('previews_box')
        self.previews_box.set_no_show_all(True)
        self.previews_box.hide()

        self.set_button = self.builder.get_object('set_button')
        self.set_button.set_sensitive(False)

        self.last_search = "%s - %s"  % (tempartist, tempalbum)

        self.window.show_all()

        self.cancel_fetch = threading.Event()
        self.fetcher_thread = threading.Thread(target=self.fetch_cover, name='Coverfetcher')
        self.fetcher_thread.start()

    def fetch_cover(self):
        """
            Searches for covers for the current track
        """
        db_strings = cover_manager.find_covers(self.track)

        if db_strings:
            for db_string in db_strings:
                if self.cancel_fetch.is_set():
                    return

                coverdata = cover_manager.get_cover_data(db_string)
                # Pre-render everything for faster display later
                pixbuf = icons.MANAGER.pixbuf_from_data(coverdata)
                self.covers_model.append([
                    (db_string, coverdata),
                    pixbuf,
                    pixbuf.scale_simple(50, 50, gtk.gdk.INTERP_BILINEAR)
                ])

        self.emit('covers-fetched', db_strings)

    def do_covers_fetched(self, db_strings):
        """
            Finishes the dialog setup after all covers have been fetched
        """
        if self.cancel_fetch.is_set():
            return

        self.cover_image_box.remove(self.loading_indicator)

        if db_strings:
            self.cover_image_box.pack_start(self.cover, True, True)
            self.cover.show()
            self.set_button.set_sensitive(True)

            # Show thumbnail bar if more than one cover was found
            if len(db_strings) > 1:
                self.previews_box.set_no_show_all(False)
                self.previews_box.show_all()

            # Try to select the current cover of the track, fallback to first
            track_db_string = cover_manager.get_db_string(self.track)
            position = db_strings.index(track_db_string) if track_db_string in db_strings else 0
            self.previews_box.select_path((position,))
        else:
            self.builder.get_object('info_box').hide()
            self.builder.get_object('actions_box').hide()
            self.message.show_warning(
                _('No covers found.'),
                _('None of the enabled sources has a cover for this track, try enabling more sources.')
            )

    def on_cancel_button_clicked(self, button):
        """
            Closes the cover chooser
        """
        # Notify the fetcher thread to stop
        self.cancel_fetch.set()

        self.window.destroy()

    def on_set_button_clicked(self, button):
        """
            Chooses the current cover and saves it to the database
        """
        paths = self.previews_box.get_selected_items()

        if paths:
            path = paths[0]
            coverdata = self.covers_model[path][0]

            cover_manager.set_cover(self.track, coverdata[0], coverdata[1])

            self.emit('cover-chosen', coverdata[1])
            self.window.destroy()

    def on_previews_box_selection_changed(self, iconview):
        """
            Switches the currently displayed cover
        """
        paths = self.previews_box.get_selected_items()

        if paths:
            path = paths[0]
            db_string = self.covers_model[path][0]
            source = db_string[0].split(':', 1)[0]
            provider = providers.get_provider('covers', source)
            pixbuf = self.covers_model[path][1]

            self.cover.set_image_pixbuf(pixbuf)
            self.size_label.set_text(_('{width}x{height} pixels').format(
                width=pixbuf.get_width(), height=pixbuf.get_height()))
            # Display readable title of the provider, fallback to its name
            self.source_label.set_text(getattr(provider, 'title', source))

            self.set_button.set_sensitive(True)
        else:
            self.set_button.set_sensitive(False)

    def on_previews_box_item_activated(self, iconview, path):
        """
            Triggers selecting the current cover
        """
        self.set_button.clicked()

    def on_message_response(self, widget, response):
        """
            Handles the response for closing
        """
        if response == gtk.RESPONSE_CLOSE:
            self.window.destroy()

