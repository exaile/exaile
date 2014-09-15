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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
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

import glib
import gobject
import gtk

from xl import event, settings
from xl.common import clamp
from xl.nls import gettext as _
import xl.main
from xlgui import icons

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
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            (gobject.TYPE_INT,)
        )
    }

    def __init__(self, rating=0, player=None):
        """
            :param rating: the optional initial rating
            :type rating: int
            :param player: If not None, this rating widget will automatically 
                           update to reflect the rating of the current song
            :type player: xl.player.ExailePlayer
        """
        gtk.EventBox.__init__(self)
        self._player = player
        
        self.set_visible_window(False)
        self.set_above_child(True)
        self.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.set_can_focus(True)

        self._image = gtk.Image()
        self.add(self._image)

        self._rating = -1
        self.props.rating = rating

        if self._player is not None:
        
            event.add_callback( self.on_rating_update, 'playback_track_start', self._player )
            event.add_callback( self.on_rating_update, 'playback_track_end', self._player )
            event.add_callback( self.on_rating_update, 'rating_changed')

            self.on_rating_update('rating_changed', None, None)

    def destroy(self):
        """
            Cleanups
        """
        if self._player is not None:
            event.remove_callback( self.on_rating_update, 'playback_track_start', self._player )
            event.remove_callback( self.on_rating_update, 'playback_track_end', self._player )
            event.remove_callback( self.on_rating_update, 'rating_changed')

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
                value = clamp(value, 0, settings.get_option('rating/maximum', 5))

            self._rating = value
            self._image.set_from_pixbuf(
                icons.MANAGER.pixbuf_from_rating(value).pixbuf)

            self.emit('rating-changed', value)
        else:
            raise AttributeError('unkown property %s' % property.name)

    def do_expose_event(self, event):
        """
            Takes care of painting the focus indicator
        """
        if self.is_focus():
            self.style.paint_focus(
                window=self.window,
                state_type=self.get_state(),
                area=event.area,
                widget=self,
                detail='button', # Borrow style from GtkButton
                x=event.area.x,
                y=event.area.y,
                width=event.area.width,
                height=event.area.height
            )

        gtk.EventBox.do_expose_event(self, event)

    def do_motion_notify_event(self, event):
        """
            Temporarily updates the displayed rating
        """
        if self.get_state() & gtk.STATE_INSENSITIVE:
            return

        allocation = self.get_allocation()
        maximum = settings.get_option('rating/maximum', 5)
        pixbuf_width = self._image.get_pixbuf().get_width()
        # Activate pixbuf if half of it has been passed
        threshold = (pixbuf_width / maximum) / 2
        position = (event.x + threshold) / allocation.width
        rating = int(position * maximum)

        self._image.set_from_pixbuf(
            icons.MANAGER.pixbuf_from_rating(rating).pixbuf)

    def do_leave_notify_event(self, event):
        """
            Restores the original rating
        """
        if self.get_state() & gtk.STATE_INSENSITIVE:
            return

        self._image.set_from_pixbuf(
            icons.MANAGER.pixbuf_from_rating(self._rating).pixbuf)

    def do_button_release_event(self, event):
        """
            Applies the selected rating
        """
        if self.get_state() & gtk.STATE_INSENSITIVE:
            return

        allocation = self.get_allocation()
        maximum = settings.get_option('rating/maximum', 5)
        pixbuf_width = self._image.get_pixbuf().get_width()
        # Activate pixbuf if half of it has been passed
        threshold = (pixbuf_width / maximum) / 2
        position = (event.x + threshold) / allocation.width
        self.props.rating = int(position * maximum)

    def do_key_press_event(self, event):
        """
            Changes the rating on keyboard interaction
            * Alt+Up/Right: increases the rating
            * Alt+Down/Left: decreases the rating
        """
        if self.get_state() & gtk.STATE_INSENSITIVE:
            return

        if not event.state & gtk.gdk.MOD1_MASK:
            return

        if event.keyval in (gtk.keysyms.Up, gtk.keysyms.Right):
            rating = self.props.rating + 1
        elif event.keyval in (gtk.keysyms.Down, gtk.keysyms.Left):
            rating = self.props.rating - 1
        else:
            return

        rating = max(0, rating)

        # Prevents unsetting rating if maximum is reached
        if rating == self.props.rating:
            return

        self.props.rating = rating

    def on_rating_update(self, event_type, sender, data):
        """
            Updates the rating from the current track
        """
        if self._player.current is not None:
            self._rating = self._player.current.get_rating()
            glib.idle_add(self._image.set_from_pixbuf,
                icons.MANAGER.pixbuf_from_rating(self._rating).pixbuf)
            glib.idle_add(self.set_sensitive, True)
        else:
            glib.idle_add(self.set_sensitive, False)

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
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            (gobject.TYPE_INT,)
        )
    }
    def __init__(self, rating=0, player=None):
        """
            :param rating: the optional initial rating
            :type rating: int
            :param player: If not None, this rating widget will automatically 
                           update to reflect the rating of the current song
            :type player: xl.player.ExailePlayer
        """
        gtk.MenuItem.__init__(self)

        box = gtk.HBox(spacing=6)
        box.pack_start(gtk.Label(_('Rating:')), False, False)
        self.rating_widget = RatingWidget(rating, player)
        box.pack_start(self.rating_widget, False, False)

        self.add(box)

        self.rating_widget.connect('rating-changed',
            self.on_rating_changed)

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

    def do_motion_notify_event(self, event):
        """
            Forwards the event to the rating widget
        """
        allocation = self.rating_widget.get_allocation()

        if allocation.x < event.x < allocation.x + allocation.width:
            x, y = self.translate_coordinates(self.rating_widget,
                int(event.x), int(event.y))
            event.x, event.y = float(x), float(y)
            # HACK: GI: event is not subclass of Gdk.Event.
            self.rating_widget.emit('motion-notify-event', gtk.gdk.Event(event))

    def do_leave_notify_event(self, event):
        """
            Forwards the event to the rating widget
        """
        # HACK: GI: event is not subclass of Gdk.Event.
        self.rating_widget.emit('leave-notify-event', gtk.gdk.Event(event))

    def do_button_release_event(self, event):
        """
            Forwards the event to the rating widget
        """
        allocation = self.rating_widget.get_allocation()

        if allocation.x < event.x < allocation.x + allocation.width:
            x, y = self.translate_coordinates(self.rating_widget,
                int(event.x), int(event.y))
            event.x, event.y = float(x), float(y)
            self.rating_widget.emit('button-release-event', event)

    def on_rating_changed(self, widget, rating):
        """
            Forwards the event
        """
        self.emit('rating-changed', rating)

class RatingCellRenderer(gtk.CellRendererPixbuf):
    """
        A cell renderer drawing rating images
        and allowing for selection of ratings
    """
    __gproperties__ = {
        'rating': (
            gobject.TYPE_INT,
            'Rating',
            'The selected rating',
            0, # Minimum
            65535, # Maximum
            0, # Default
            gobject.PARAM_READWRITE
        )
    }
    __gsignals__ = {
        'rating-changed': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            (gobject.TYPE_PYOBJECT, gobject.TYPE_INT)
        )
    }

    def __init__(self):
        gtk.CellRendererPixbuf.__init__(self)
        self.props.mode = gtk.CELL_RENDERER_MODE_ACTIVATABLE
        self.props.xalign = 0
        
        self.rating = 0
        self.size_ratio = 1

    def do_get_property(self, property):
        """
            Getter for GObject properties
        """
        if property.name == 'rating':
            return self.rating
        else:
            raise AttributeError('unkown property %s' % property.name)

    def do_set_property(self, property, value):
        """
            Setter for GObject properties
        """
        if property.name == 'rating':
            self.rating = value
            self.props.pixbuf = icons.MANAGER.pixbuf_from_rating(self.rating, self.size_ratio).pixbuf
        else:
            raise AttributeError('unkown property %s' % property.name)

    def do_activate(self, event, widget, path,
                    background_area, cell_area, flags):
        """
            Checks if a button press event did occur
            within the clickable rating image area
        """
        if event is None: # Keyboard activation
            return

        # Locate click area at zero
        click_area = gtk.gdk.Rectangle(
            x=0,
            y=self.props.ypad,
            width=self.props.pixbuf.get_width(),
            height=self.props.pixbuf.get_height()
        )

        # Move event location relative to zero
        event.x -= cell_area.x + click_area.x
        event.y -= cell_area.y + click_area.y

        if 0 <= event.x <= click_area.width and \
           0 <= event.y <= click_area.height:
            fraction = event.x / click_area.width
            maximum = settings.get_option('rating/maximum', 5)
            rating = fraction * maximum + 1
            self.emit('rating-changed', (int(path),), rating)

    def do_render(self, window, widget, background_area,
                  cell_area, expose_area, flags):
        """
            Renders the rating images
            (Overriden since gtk.CellRendererPixbuf
             fails at vertical padding)
        """
        cell_area.width *= self.props.xalign
        cell_area.height *= self.props.yalign

        pixbuf_width = self.props.pixbuf.get_width() * self.props.xalign
        pixbuf_height = self.props.pixbuf.get_height() * self.props.yalign

        x = cell_area.x + cell_area.width - pixbuf_width
        y = cell_area.y + cell_area.height - pixbuf_height

        context = window.cairo_create()
        context.set_source_pixbuf(self.props.pixbuf, x, y)
        context.paint()

