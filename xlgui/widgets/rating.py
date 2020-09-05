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

from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk

from xl import event, settings
from xl.common import clamp
from xl.nls import gettext as _

from xlgui import icons


class RatingWidget(Gtk.EventBox):
    """
    A rating widget which displays a row of
    images and allows for selecting the rating
    """

    __gproperties__ = {
        'rating': (
            GObject.TYPE_INT,
            'rating',
            'The selected rating',
            0,  # Minimum
            65535,  # Maximum
            0,  # Default
            GObject.ParamFlags.READWRITE,
        )
    }
    __gsignals__ = {
        'rating-changed': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_INT,))
    }

    def __init__(self, rating=0, player=None):
        """
        :param rating: the optional initial rating
        :type rating: int
        :param player: If not None, this rating widget will automatically
                       update to reflect the rating of the current song
        :type player: xl.player.ExailePlayer
        """
        Gtk.EventBox.__init__(self)
        self._player = player

        self.set_visible_window(False)
        self.set_above_child(True)
        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.set_can_focus(True)

        self._image = Gtk.Image()
        self.add(self._image)

        self._rating = -1
        self.props.rating = rating

        if self._player is not None:

            event.add_ui_callback(
                self.on_rating_update, 'playback_track_start', self._player
            )
            event.add_ui_callback(
                self.on_rating_update, 'playback_track_end', self._player
            )
            event.add_ui_callback(self.on_rating_update, 'rating_changed')

            self.on_rating_update('rating_changed', None, None)

    def destroy(self):
        """
        Cleanups
        """
        if self._player is not None:
            event.remove_callback(
                self.on_rating_update, 'playback_track_start', self._player
            )
            event.remove_callback(
                self.on_rating_update, 'playback_track_end', self._player
            )
            event.remove_callback(self.on_rating_update, 'rating_changed')

    def do_get_property(self, property):
        """
        Getter for custom properties
        """
        if property.name == 'rating':
            return self._rating
        else:
            raise AttributeError('unknown property %s' % property.name)

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
            self._image.set_from_pixbuf(icons.MANAGER.pixbuf_from_rating(value).pixbuf)

            self.emit('rating-changed', value)
        else:
            raise AttributeError('unknown property %s' % property.name)

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
                detail='button',  # Borrow style from GtkButton
                x=event.area.x,
                y=event.area.y,
                width=event.area.width,
                height=event.area.height,
            )

        Gtk.EventBox.do_expose_event(self, event)

    def do_motion_notify_event(self, event):
        """
        Temporarily updates the displayed rating
        """
        if self.get_state_flags() & Gtk.StateType.INSENSITIVE:
            return

        allocation = self.get_allocation()
        maximum = settings.get_option('rating/maximum', 5)
        pixbuf_width = self._image.get_pixbuf().get_width()
        # Activate pixbuf if half of it has been passed
        threshold = (pixbuf_width / maximum) / 2
        position = (event.x + threshold) / allocation.width
        rating = int(position * maximum)

        self._image.set_from_pixbuf(icons.MANAGER.pixbuf_from_rating(rating).pixbuf)

    def do_leave_notify_event(self, event):
        """
        Restores the original rating
        """
        if self.get_state_flags() & Gtk.StateType.INSENSITIVE:
            return

        self._image.set_from_pixbuf(
            icons.MANAGER.pixbuf_from_rating(self._rating).pixbuf
        )

    def do_button_release_event(self, event):
        """
        Applies the selected rating
        """
        if self.get_state_flags() & Gtk.StateType.INSENSITIVE:
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
        if self.get_state_flags() & Gtk.StateType.INSENSITIVE:
            return

        if not event.get_state() & Gdk.ModifierType.MOD1_MASK:
            return

        if event.keyval in (Gdk.KEY_Up, Gdk.KEY_Right):
            rating = self.props.rating + 1
        elif event.keyval in (Gdk.KEY_Down, Gdk.KEY_Left):
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
            self._image.set_from_pixbuf(
                icons.MANAGER.pixbuf_from_rating(self._rating).pixbuf
            )
            self.set_sensitive(True)
        else:
            self.set_sensitive(False)


class RatingMenuItem(Gtk.MenuItem):
    """
    A menuitem containing a rating widget
    """

    __gproperties__ = {
        'rating': (
            GObject.TYPE_INT,
            'rating',
            'The selected rating',
            0,  # Minimum
            65535,  # Maximum
            0,  # Default
            GObject.ParamFlags.READWRITE,
        )
    }
    __gsignals__ = {
        'rating-changed': (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_INT,))
    }

    def __init__(self, rating=0, player=None):
        """
        :param rating: the optional initial rating
        :type rating: int
        :param player: If not None, this rating widget will automatically
                       update to reflect the rating of the current song
        :type player: xl.player.ExailePlayer
        """
        Gtk.MenuItem.__init__(self)

        box = Gtk.Box(spacing=6)
        box.pack_start(Gtk.Label(label=_('Rating:')), False, False, 0)
        self.rating_widget = RatingWidget(rating, player)
        box.pack_start(self.rating_widget, False, False, 0)

        self.add(box)

        self.rating_widget.connect('rating-changed', self.on_rating_changed)

    def do_get_property(self, property):
        """
        Getter for custom properties
        """
        if property.name == 'rating':
            return self.rating_widget.props.rating
        else:
            raise AttributeError('unknown property %s' % property.name)

    def do_set_property(self, property, value):
        """
        Setter for custom properties
        """
        if property.name == 'rating':
            self.rating_widget.props.rating = value
        else:
            raise AttributeError('unknown property %s' % property.name)

    def do_motion_notify_event(self, event):
        """
        Forwards the event to the rating widget
        """
        allocation = self.rating_widget.get_allocation()

        if allocation.x < event.x < allocation.x + allocation.width:
            x, y = self.translate_coordinates(
                self.rating_widget, int(event.x), int(event.y)
            )
            event.x, event.y = float(x), float(y)
            self.rating_widget.emit('motion-notify-event', event.copy())

    def do_leave_notify_event(self, event):
        """
        Forwards the event to the rating widget
        """
        self.rating_widget.emit('leave-notify-event', event.copy())

    def do_button_release_event(self, event):
        """
        Forwards the event to the rating widget
        """
        allocation = self.rating_widget.get_allocation()

        if allocation.x < event.x < allocation.x + allocation.width:
            x, y = self.translate_coordinates(
                self.rating_widget, int(event.x), int(event.y)
            )
            event.x, event.y = float(x), float(y)
            self.rating_widget.emit('button-release-event', event.copy())

    def on_rating_changed(self, widget, rating):
        """
        Forwards the event
        """
        self.emit('rating-changed', rating)


class RatingCellRenderer(Gtk.CellRendererPixbuf):
    """
    A cell renderer drawing rating images
    and allowing for selection of ratings
    """

    __gproperties__ = {
        'rating': (
            GObject.TYPE_INT,
            'Rating',
            'The selected rating',
            0,  # Minimum
            65535,  # Maximum
            0,  # Default
            GObject.ParamFlags.READWRITE,
        )
    }
    __gsignals__ = {
        'rating-changed': (
            GObject.SignalFlags.RUN_LAST,
            None,
            (GObject.TYPE_PYOBJECT, GObject.TYPE_INT),
        )
    }

    def __init__(self):
        Gtk.CellRendererPixbuf.__init__(self)
        self.props.mode = Gtk.CellRendererMode.ACTIVATABLE
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
            raise AttributeError('unknown property %s' % property.name)

    def do_set_property(self, property, value):
        """
        Setter for GObject properties
        """
        if property.name == 'rating':
            self.rating = value
            self.props.pixbuf = icons.MANAGER.pixbuf_from_rating(
                self.rating, self.size_ratio
            ).pixbuf
        else:
            raise AttributeError('unknown property %s' % property.name)

    def do_activate(self, event, widget, path, background_area, cell_area, flags):
        """
        Checks if a button press event did occur
        within the clickable rating image area
        """
        if event is None:  # Keyboard activation
            return

        # Locate click area at zero
        click_area = Gdk.Rectangle()
        click_area.x = 0
        click_area.y = self.props.ypad
        click_area.width = self.props.pixbuf.get_width()
        click_area.height = self.props.pixbuf.get_height()

        # Move event location relative to zero
        event.x -= cell_area.x + click_area.x
        event.y -= cell_area.y + click_area.y

        if 0 <= event.x <= click_area.width:
            fraction = event.x / click_area.width
            maximum = settings.get_option('rating/maximum', 5)
            rating = fraction * maximum + 1
            self.emit('rating-changed', (int(path),), rating)


'''
    No longer needed in GTK3?

    def do_render(self, context, widget, background_area,
                  cell_area, flags):
        """
            Renders the rating images
            (Overriden since Gtk.CellRendererPixbuf
             fails at vertical padding)
        """
        cell_area.width *= self.props.xalign
        cell_area.height *= self.props.yalign

        pixbuf_width = self.props.pixbuf.get_width() * self.props.xalign
        pixbuf_height = self.props.pixbuf.get_height() * self.props.yalign

        x = cell_area.x + cell_area.width - pixbuf_width
        y = cell_area.y + cell_area.height - pixbuf_height

        context.set_source_pixbuf(self.props.pixbuf, x, y)
        context.paint()
'''
