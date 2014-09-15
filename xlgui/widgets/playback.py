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
import pango

from xl import (
    event,
    formatter,
    player,
    providers,
    settings,
    xdg
)
from xl.common import clamp
from xl.nls import gettext as _
from xlgui.widgets import menu

class ProgressBarFormatter(formatter.ProgressTextFormatter):
    """
        A formatter for progress bars
    """
    def __init__(self, player):
        formatter.ProgressTextFormatter.__init__(self, '', player)

        event.add_callback(self.on_option_set,
            'gui_option_set')
        self.on_option_set('gui_option_set', settings,
            'gui/progress_bar_text_format')

    def on_option_set(self, event, settings, option):
        """
            Updates the internal format on setting change
        """
        if option == 'gui/progress_bar_text_format':
            self.props.format = settings.get_option(
                'gui/progress_bar_text_format',
                '$current_time / $remaining_time')

class PlaybackProgressBar(gtk.ProgressBar):
    """
        Progress bar which automatically follows playback
    """
    def __init__(self, player):
        gtk.ProgressBar.__init__(self)
        self.__player = player
        
        self.reset()

        self.formatter = ProgressBarFormatter(player)
        self.__timer_id = None
        self.__events = ('playback_track_start', 'playback_player_end',
                         'playback_toggle_pause', 'playback_error')

        for e in self.__events:
            event.add_callback(getattr(self, 'on_%s' % e), e, self.__player)

    def destroy(self):
        """
            Cleanups
        """
        for e in self.__events:
            event.remove_callback(getattr(self, 'on_%s' % e), e, self.__player)

    def reset(self):
        """
            Resets the progress bar appearance
        """
        glib.idle_add(self.set_fraction, 0)
        glib.idle_add(self.set_text, _('Not Playing'))

    def __enable_timer(self):
        """
            Enables the update timer
        """
        if self.__timer_id is not None:
            return

        interval = settings.get_option('gui/progress_update_millisecs', 1000)

        if interval % 1000 == 0:
            self.__timer_id = glib.timeout_add_seconds(
                interval / 1000, self.on_timer)
        else:
            self.__timer_id = glib.timeout_add(
                interval, self.on_timer)

        self.on_timer()

    def __disable_timer(self):
        """
            Disables the update timer
        """
        if self.__timer_id is not None:
            glib.source_remove(self.__timer_id)
            self.__timer_id = None

    def on_timer(self):
        """
            Updates progress bar appearance
        """
        if self.__player.current is None:
            self.__disable_timer()
            self.reset()
            return False

        glib.idle_add(self.set_fraction, self.__player.get_progress())
        glib.idle_add(self.set_text, self.formatter.format())

        return True

    def on_playback_track_start(self, event_type, player, track):
        """
            Starts update timer
        """
        self.reset()
        self.__enable_timer()

    def on_playback_player_end(self, event_type, player, track):
        """
            Stops update timer
        """
        self.__disable_timer()
        self.reset()

    def on_playback_toggle_pause(self, event_type, player, track):
        """
            Starts or stops update timer
        """
        if player.is_playing():
            self.__enable_timer()
        elif player.is_paused():
            self.__disable_timer()

    def on_playback_error(self, event_type, player, message):
        """
            Stops update timer
        """
        self.__disable_timer()
        self.reset()

class Marker(gobject.GObject):
    """
        A marker pointing to a playback position
    """
    class Anchor(int):
        __gtype__ = gobject.TYPE_INT
        pass
    for i, a in enumerate('CENTER NORTH NORTH_WEST NORTH_EAST SOUTH SOUTH_WEST SOUTH_EAST WEST EAST'.split()):
        setattr(Anchor, a, Anchor(i))
    __gproperties__ = {
        'anchor': (
            Anchor,
            'anchor position',
            'The position the marker will be anchored',
            Anchor.CENTER, Anchor.EAST, Anchor.SOUTH,
            gobject.PARAM_READWRITE
        ),
        'color': (
            gtk.gdk.Color,
            'marker color',
            'Override color of the marker',
            gobject.PARAM_READWRITE
        ),
        'label': (
            gobject.TYPE_STRING,
            'marker label',
            'Textual description of the marker',
            None,
            gobject.PARAM_READWRITE
        ),
        'position': (
            gobject.TYPE_FLOAT,
            'marker position',
            'Relative position of the marker',
            0, 1, 0,
            gobject.PARAM_READWRITE
        ),
        'state': (
            gtk.StateType,
            'marker state',
            'The state of the marker',
            gtk.STATE_NORMAL,
            gobject.PARAM_READWRITE
        )
    }
    __gsignals__ = {
        'reached': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            ()
        )
    }

    def __init__(self, position=0):
        gobject.GObject.__init__(self)

        self.__values = {
            'anchor': gtk.Anchor.SOUTH,
            'color': None,
            'label': None,
            'position': 0,
            'state': gtk.STATE_NORMAL
        }

        self.props.position = position

    def __str__(self):
        """
            Informal representation
        """
        if self.props.label is not None:
            text = '%s (%g)' % (self.props.label, self.props.position)
        else:
            text = '%g' % self.props.position

        return text

    def __lt__(self, other):
        """
            Compares positions
        """
        return self.props.position < other.props.position

    def __gt__(self, other):
        """
            Compares positions
        """
        return self.props.position > other.props.position

    def do_get_property(self, gproperty):
        """
            Gets a GObject property
        """
        try:
            return self.__values[gproperty.name]
        except KeyError:
            raise AttributeError('unknown property %s' % property.name)

    def do_set_property(self, gproperty, value):
        """
            Sets a GObject property
        """
        try:
            self.__values[gproperty.name] = value
        except KeyError:
            raise AttributeError('unknown property %s' % property.name)

class MarkerManager(providers.ProviderHandler):
    """
        Enables management of playback markers; namely simple
        adding, removing and finding. It also takes care of
        emitting signals when a marker is reached during playback.
        
        TODO: This presumes there is only one player object present
        in exaile, and that markers can only be associated with
        the single player object. This class should probably be
        changed to be associated with a particular player (which
        requires some changes to the marker class)
    """
    def __init__(self):
        providers.ProviderHandler.__init__(self, 'playback-markers')

        self.__events = ('playback_track_start', 'playback_track_end')
        self.__timeout_id = None

        for e in self.__events:
            event.add_callback(getattr(self, 'on_%s' % e), e)

    def destroy(self):
        """
            Cleanups
        """
        for e in self.__events:
            event.remove_callback(getattr(self, 'on_%s' % e), e)

    def add_marker(self, position):
        """
            Creates a new marker for a playback position

            :param position: the playback position [0..1]
            :type position: float
            :returns: the new marker
            :rtype: :class:`Marker`
        """
        marker = Marker(position)
        # Provider compatibility
        marker.name = 'marker'
        providers.register('playback-markers', marker)

        return marker

    def remove_marker(self, marker):
        """
            Removes a playback marker

            :param marker: the marker
            :type marker: :class:`Marker`
        """
        providers.unregister('playback-markers', marker)

    def get_markers_at(self, position):
        """
            Gets all markers located at a position
 
            :param position: the mark position
            :type position: float
            :returns: (m1, m2, ...)
            :rtype: (:class:`Marker`, ...)
 
            * *m1*: the first marker
            * *m2*: the second marker
            * ...
        """
        # Reproduce value modifications
        position = Marker(position).props.position
        markers = ()

        for marker in providers.get('playback-markers'):
            if marker.props.position == position:
                markers += (marker,)

        return markers

    def on_playback_track_start(self, event, player, track):
        """
            Starts marker watching
        """
        if self.__timeout_id is not None:
            glib.source_remove(self.__timeout_id)

        self.__timeout_id = glib.timeout_add_seconds(1, self.on_timeout, player)

    def on_playback_track_end(self, event, player, track):
        """
            Stops marker watching
        """
        if self.__timeout_id is not None:
            glib.source_remove(self.__timeout_id)
            self.__timeout_id = None

    def on_timeout(self, player):
        """
            Triggers "reached" signal of markers
        """
        
        if player.current is None:
            return
        
        track_length = player.current.get_tag_raw('__length')

        if track_length is None:
            return True

        playback_time = player.get_time()
        reached_markers = (m for m in providers.get('playback-markers')
            if int(m.props.position * track_length) == playback_time)

        for marker in reached_markers:
            marker.emit('reached')

        return True

__MARKERMANAGER = MarkerManager()
add_marker = __MARKERMANAGER.add_marker
remove_marker = __MARKERMANAGER.remove_marker
get_markers_at = __MARKERMANAGER.get_markers_at

class SeekProgressBar(PlaybackProgressBar, providers.ProviderHandler):
    """
        Playback progress bar which allows for seeking
        and setting positional markers
    """
    __gproperties__ = {
        'marker-scale': (
            gobject.TYPE_FLOAT,
            'marker scale',
            'Scaling of markers',
            0, 1, 0.7,
            gobject.PARAM_READWRITE
        )
    }
    __gsignals__ = {
        'button-press-event': 'override',
        'button-release-event': 'override',
        'draw': 'override',
        'motion-notify-event': 'override',
        'notify': 'override',
        'key-press-event': 'override',
        'key-release-event': 'override',
        'marker-reached': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_BOOLEAN,
            (Marker,),
            gobject.signal_accumulator_true_handled
        )
    }

    def __init__(self, player, use_markers=True):
        '''
            TODO: markers aren't designed for more than one player, once 
            they are we can get rid of the use_markers option
        '''
        PlaybackProgressBar.__init__(self, player)
        
        self.__player = player
        self.__values = {'marker-scale': 0.7}
        self._seeking = False
        self._points = {}
        
        self._progressbar_menu = None
        
        if use_markers:
            self._progressbar_menu = ProgressBarContextMenu(self)
        
            self._marker_menu = MarkerContextMenu(self)
            self._marker_menu.connect('deactivate',
                self.on_marker_menu_deactivate)

            providers.ProviderHandler.__init__(self, 'playback-markers')

        self.add_events(gtk.gdk.BUTTON_PRESS_MASK |
                        gtk.gdk.BUTTON_RELEASE_MASK |
                        gtk.gdk.POINTER_MOTION_MASK |
                        gtk.gdk.LEAVE_NOTIFY_MASK)
        self.set_can_focus(True)

        self.connect('hierarchy-changed',
            self.on_hierarchy_changed)

    def get_label(self, marker):
        """
            Builds the most appropriate label
            markup to describe a marker

            :param marker: the marker
            :type marker: :class:`Marker`
            :returns: the label
            :rtype: string
        """
        markup = None

        if self.__player.current:
            length = self.__player.current.get_tag_raw('__length')

            if length is not None:
                length = length * marker.props.position
                length = formatter.LengthTagFormatter.format_value(length)

                if marker.props.label:
                    markup = '<b>%s</b> (%s)' % (marker.props.label, length)
                else:
                    markup = '%s' % length
        else:
            if marker.props.label:
                markup = '<b>%s</b> (%d%%)' % (
                    marker.props.label,
                    int(marker.props.position * 100)
                )
            else:
                markup = '%d%%' % int(marker.props.position * 100)

        return markup

    def _is_marker_hit(self, marker, check_x, check_y):
        """
            Checks whether a marker is hit by a point 

            :param marker: the marker
            :type marker: :class:`Marker`
            :param check_x: the x location to check
            :type check_x: float
            :param check_y: the y location to check
            :type check_y: float
            :returns: whether the marker was hit
            :rtype: bool
        """
        points = self._points[marker]
        x, y, width, height = self._get_bounding_box(points)

        if x <= check_x <= width and y <= check_y <= height:
            return True

        return False

    def _get_points(self, marker, width=None, height=None):
        """
            Calculates the points necessary
            to represent a marker

            :param marker: the marker
            :type marker: :class:`Marker`
            :param width: area width override
            :type width: int
            :param height: area height override
            :type height: int
            :returns: ((x1, y1), (x2, y2), ...)
            :rtype: ((float, float), ...)

            * *x1*: the x coordinate of the first point
            * *y1*: the y coordinate of the first point
            * *x2*: the x coordinate of the second point
            * *y2*: the y coordinate of the second point
            * ...
        """
        points = ()
        alloc = self.get_allocation()
        width = width or alloc.width
        height = height or alloc.height
        position = width * marker.props.position
        marker_scale = int(height * self.props.marker_scale)
        # Adjustment by half of the line width
        offset = self.props.marker_scale / 0.9 / 2

        if marker.props.anchor == Anchor.NORTH_WEST:
            points = (
                (position - offset, offset),
                (position + marker_scale * 0.75 - offset, offset),
                (position - offset, marker_scale * 0.75 + offset)
            )
        elif marker.props.anchor == Anchor.NORTH:
            points = (
                (position - offset, marker_scale / 2 + offset),
                (position + marker_scale / 2 - offset, offset),
                (position - marker_scale / 2 - offset, offset)
            )
        elif marker.props.anchor == Anchor.NORTH_EAST:
            points = (
                (position - marker_scale * 0.75 - offset, offset),
                (position - offset, offset),
                (position - offset, marker_scale * 0.75 + offset)
            )
        elif marker.props.anchor == Anchor.EAST:
            points = (
                (position - marker_scale / 2 - offset, height / 2 + offset),
                (position - offset, height / 2 - marker_scale / 2 + offset),
                (position - offset, height / 2 + marker_scale / 2 + offset)
            )
        elif marker.props.anchor == Anchor.SOUTH_EAST:
            points = (
                (position - offset, height - offset),
                (position - offset, height - marker_scale * 0.75 - offset),
                (position - marker_scale * 0.75 - offset, height - offset)
            )
        elif marker.props.anchor == Anchor.SOUTH:
            points = (
                (position - offset, height - marker_scale / 2 - offset),
                (position + marker_scale / 2 - offset, height - offset),
                (position - marker_scale / 2 - offset, height - offset)
            )
        elif marker.props.anchor == Anchor.SOUTH_WEST:
            points = (
                (position - offset, height - offset),
                (position + marker_scale * 0.75 - offset, height - offset),
                (position - offset, height - marker_scale * 0.75 - offset)
            )
        elif marker.props.anchor == Anchor.WEST:
            points = (
                (position + marker_scale / 2 - offset, height / 2 + offset),
                (position - offset, height / 2 - marker_scale / 2 + offset),
                (position - offset, height / 2 + marker_scale / 2 + offset)
            )
        elif marker.props.anchor == Anchor.CENTER:
            points = (
                (position - offset, height / 2 - marker_scale / 2 + offset),
                (position + marker_scale / 2 - offset, height / 2 + offset),
                (position - offset, height / 2 + marker_scale / 2 + offset),
                (position - marker_scale / 2 - offset, height / 2 + offset)
            )

        return points

    def _get_bounding_box(self, points):
        """
            Calculates the axis aligned bounding box
            of a sequence of points

            :param points: ((x1, y1), (x2, y2), ...)
            :type points: ((float, float), ...)
            :returns: (x, y, width, height)
            :rtype: (float, float, float, float)

            * *x*: the x coordinate of the box
            * *y*: the y coordinate of the box
            * *width*: the width of the box
            * *height*: the height of the box
        """
        xs, ys = zip(*points)
        return min(xs), min(ys), max(xs), max(ys)

    def seek(self, position):
        """
            Seeks within the current track
        """
        if self.__player.current:
            self.__player.set_progress(position)
            self.update_progress()
            
    def update_progress(self):
        '''
            Updates the progress bar and the time with data from the player
        '''
        
        if self.__player.current:
            length = self.__player.current.get_tag_raw('__length')
            
            if length is not None:
                position = float(self.__player.get_time())/length
                self.set_fraction(position)
                self.set_text(self.formatter.format(
                    current_time=length * position))

    def do_get_property(self, gproperty):
        """
            Gets a GObject property
        """
        try:
            return self.__values[gproperty.name]
        except KeyError:
            raise AttributeError('unknown property %s' % property.name)

    def do_set_property(self, gproperty, value):
        """
            Sets a GObject property
        """
        try:
            self.__values[gproperty.name] = value
        except KeyError:
            raise AttributeError('unknown property %s' % property.name)

    def do_notify(self, gproperty):
        """
            Reacts to GObject property changes
        """
        if gproperty.name == 'marker-scale':
            for marker in self._points.iterkeys():
                self._points[marker] = self._get_points(marker)
            self.queue_draw()

    def do_size_allocate(self, allocation):
        """
            Recalculates the marker points
        """
        oldallocation = self.get_allocation()

        gtk.ProgressBar.do_size_allocate(self, allocation)

        if allocation != oldallocation:
            for marker in self._points.iterkeys():
                self._points[marker] = self._get_points(marker)

    def do_draw(self, context):
        """
            Draws markers on top of the progress bar
        """
        gtk.ProgressBar.do_draw(self, context)

        if not self._points:
            return

        context.set_line_width(self.props.marker_scale / 0.9)

        for marker, points in self._points.iteritems():
            for x, y in points:
                context.line_to(x, y)
            context.close_path()

            if marker.props.state in (gtk.STATE_PRELIGHT, gtk.STATE_ACTIVE):
                context.set_source_color(self.style.fg[gtk.STATE_NORMAL])
            else:
                if marker.props.color is not None:
                    base = marker.props.color
                else:
                    base = self.style.base[marker.props.state]

                context.set_source_rgba(
                    base.red / 256.0**2,
                    base.green / 256.0**2,
                    base.blue / 256.0**2,
                    0.7
                )
            context.fill_preserve()

            if marker.props.state in (gtk.STATE_PRELIGHT, gtk.STATE_ACTIVE):
                context.set_source_color(self.style.fg[gtk.STATE_NORMAL])
            else:
                foreground = self.style.fg[marker.props.state]
                context.set_source_rgba(
                    foreground.red / 256.0**2,
                    foreground.green / 256.0**2,
                    foreground.blue / 256.0**2,
                    0.7
                )
            context.stroke()

    def do_button_press_event(self, event):
        """
            Prepares seeking
        """
        hit_markers = []

        for marker in self._points.iterkeys():
            if self._is_marker_hit(marker, event.x, event.y):
                if marker.props.state in (gtk.STATE_NORMAL,
                                          gtk.STATE_PRELIGHT):
                    marker.props.state = gtk.STATE_ACTIVE
                    hit_markers += [marker]

        hit_markers.sort()

        if event.button == 1:
            if self.__player.current is None:
                return True
            
            length = self.__player.current.get_tag_raw('__length')

            if length is None:
                return True

            if len(hit_markers) > 0:
                self.seek(hit_markers[0].props.position)
            else:
                fraction = event.x / self.get_allocation().width
                fraction = max(0, fraction)
                fraction = min(fraction, 1)

                self.set_fraction(fraction)
                self.set_text(_('Seeking: %s') % self.formatter.format(
                    current_time=length * fraction))
                self._seeking = True
        elif event.button == 3:
            if len(hit_markers) > 0:
                self._marker_menu.popup(event, tuple(hit_markers))
            elif self._progressbar_menu is not None:
                self._progressbar_menu.popup(event)

    def do_button_release_event(self, event):
        """
            Completes seeking
        """
        for marker in self._points.iterkeys():
            if marker.props.state == gtk.STATE_ACTIVE:
                marker.props.state = gtk.STATE_PRELIGHT

        if event.button == 1 and self._seeking:
            length = self.__player.current.get_tag_raw('__length')

            fraction = event.x / self.get_allocation().width
            fraction = max(0, fraction)
            fraction = min(fraction, 1)

            self.seek(fraction)
            self._seeking = False

    def do_motion_notify_event(self, event):
        """
            Updates progress bar while seeking
            and updates marker states on hover
        """
        self.set_tooltip_markup(None)

        if self._seeking:
            press_event = gtk.gdk.Event(gtk.gdk.BUTTON_PRESS)
            press_event.button = 1
            press_event.x = event.x
            press_event.y = event.y

            self.emit('button-press-event', press_event)
        else:
            hit_markers = []

            for marker in self._points.iterkeys():
                if self._is_marker_hit(marker, event.x, event.y):
                    if marker.props.state == gtk.STATE_NORMAL:
                        marker.props.state = gtk.STATE_PRELIGHT
                    hit_markers += [marker]
                else:
                    if marker.props.state == gtk.STATE_PRELIGHT:
                        marker.props.state = gtk.STATE_NORMAL

            if len(hit_markers) > 0:
                hit_markers.sort()
                markup = ', '.join([self.get_label(m) for m in hit_markers])
                self.set_tooltip_markup(markup)
                self.trigger_tooltip_query()

    def do_leave_notify_event(self, event):
        """
            Resets marker states
        """
        for marker in self._points.iterkeys():
            # Leave other states intact
            if marker.props.state == gtk.STATE_PRELIGHT:
                marker.props.state = gtk.STATE_NORMAL

    def do_key_press_event(self, event):
        """
            Prepares seeking via keyboard interaction
            * Alt+Up/Right: seek 1% forward
            * Alt+Down/Left: seek 1% backward
        """
        if self.get_state() & gtk.STATE_INSENSITIVE:
            return

        if not event.state & gtk.gdk.MOD1_MASK:
            return

        if event.keyval in (gtk.keysyms.Up, gtk.keysyms.Right):
            direction = 1
        elif event.keyval in (gtk.keysyms.Down, gtk.keysyms.Left):
            direction = -1
        else:
            return
        
        press_event = gtk.gdk.Event(gtk.gdk.BUTTON_PRESS)
        press_event.button = 1
        new_fraction = self.get_fraction() + 0.01 * direction
        alloc = self.get_allocation()
        press_event.x = alloc.width * new_fraction
        press_event.y = float(alloc.y)

        self.emit('button-press-event', press_event)

    def do_key_release_event(self, event):
        """
            Completes seeking via keyboard interaction
        """
        if not event.state & gtk.gdk.MOD1_MASK:
            return

        if event.keyval in (gtk.keysyms.Up, gtk.keysyms.Right):
            direction = 1
        elif event.keyval in (gtk.keysyms.Down, gtk.keysyms.Left):
            direction = -1
        else:
            return

        release_event = gtk.gdk.Event(gtk.gdk.BUTTON_RELEASE)
        release_event.button = 1
        new_fraction = self.get_fraction() + 0.01 * direction
        alloc = self.get_allocation()
        release_event.x = alloc.width * new_fraction
        release_event.y = float(alloc.y)

        self.emit('button-release-event', release_event)

    def on_hierarchy_changed(self, widget, old_toplevel):
        """
            Sets up editing cancel on toplevel focus out
        """
        self.get_toplevel().connect('focus-out-event',
            lambda w, e: self.emit('focus-out-event',
                # HACK: GI: Gdk.EventFocus is not subclass of Gdk.Event.
                gtk.gdk.Event(e)))

    def on_marker_menu_deactivate(self, menu):
        """
            Makes sure to reset states of
            previously selected markers
        """
        for marker in self._points:
            marker.props.state = gtk.STATE_NORMAL
        self.queue_draw()

    def on_marker_notify(self, marker, gproperty):
        """
            Recalculates marker points on position changes
        """
        if gproperty.name in ('anchor', 'position'):
            self._points[marker] = self._get_points(marker)
        self.queue_draw()

    def on_timer(self):
        """
            Prevents update while seeking
        """
        if self._seeking:
            return True

        return PlaybackProgressBar.on_timer(self)

    def on_provider_added(self, marker):
        """
            Calculates points after marker addition

            :param marker: the new marker
            :type marker: :class:`Marker`
        """
        notify_id = marker.connect('notify', self.on_marker_notify)
        marker.set_data('%s_notify_id' % id(self), notify_id)
        self._points[marker] = self._get_points(marker)
        self.queue_draw()

    def on_provider_removed(self, marker):
        """
            Removes points from internal cache

            :param marker: the marker
            :type marker: :class:`Marker`
        """
        notify_id = marker.get_data('%s_notify_id' % id(self))
        if notify_id is not None:
            marker.disconnect(notify_id)

        del self._points[marker]
        self.queue_draw()

class ProgressBarContextMenu(menu.ProviderMenu):
    """
        Progress bar specific context menu
    """
    def __init__(self, progressbar):
        """
            :param progressbar: the progress bar
            :type progressbar: :class:`PlaybackProgressBar`
        """
        menu.ProviderMenu.__init__(self,
            'progressbar-context-menu', progressbar)

        self._position = -1

    def get_context(self):
        """
            Retrieves the context
        """
        context = {'current-position': self._position}

        return context

    def popup(self, event):
        """
            Pops up the menu

            :param event: an event
            :type event: :class:`gtk.gdk.Event`
        """
        self._position = event.x / self._parent.get_allocation().width

        menu.ProviderMenu.popup(self, event)

class MarkerContextMenu(menu.ProviderMenu):
    """
        Marker specific context menu
    """
    def __init__(self, markerbar):
        """
            :param markerbar: the marker capable progress bar
            :type markerbar: :class:`SeekProgressBar`
        """
        menu.ProviderMenu.__init__(self,
            'playback-marker-context-menu', markerbar)

        self._markers = ()
        self._position = -1

    def regenerate_menu(self):
        """
            Builds the menu, with submenu if appropriate
        """
        for marker in self._markers:
            label = self._parent.get_label(marker)

            if label is None:
                continue

            markup_data = pango.parse_markup(label)
            label_item = gtk.MenuItem(markup_data[1])
            self.append(label_item)

            if len(self._markers) > 1:
                item_menu = gtk.Menu()
                label_item.set_submenu(item_menu)
            else:
                item_menu = self
                label_item.set_sensitive(False)
                self.append(gtk.SeparatorMenuItem())

            context = {
                'current-marker': marker,
                'selected-markers': self._markers,
                'current-position': self._position
            }

            for item in self._items:
                i = item.factory(self, self._parent, context)
                item_menu.append(i)

        self.show_all()

    def popup(self, event, markers):
        """
            Pops up the menu

            :param event: an event
            :type event: :class:`gtk.gdk.Event`
            :param markers: (m1, m2, ...)
            :type markers: (:class:`Marker`, ...)
        """
        self._markers = markers
        self._position = event.x / self._parent.get_allocation().width

        menu.ProviderMenu.popup(self, event)

class MoveMarkerMenuItem(menu.MenuItem):
    """
        Menu item allowing for movement of markers
    """
    def __init__(self, name, after, display_name=_('Move'),
                 icon_name=None):
        menu.MenuItem.__init__(self, name, None, after)

        self._parent = None
        self._display_name = display_name
        self._icon_name = icon_name
        self._marker = None
        self._reset_position = -1

    def factory(self, menu, parent, context):
        """
            Generates the menu item
        """
        self._parent = parent

        item = gtk.ImageMenuItem(self._display_name)

        if self._icon_name is not None:
            item.set_image(gtk.image_new_from_icon_name(
                self._icon_name, gtk.ICON_SIZE_MENU))

        item.connect('activate', self.on_activate, parent, context)

        parent.connect('button-press-event',
            self.on_parent_button_press_event)
        parent.connect('motion-notify-event',
            self.on_parent_motion_notify_event)
        parent.connect('focus-out-event',
            self.on_parent_focus_out_event)

        return item

    def move_begin(self, marker):
        """
            Captures the current marker for movement

            :param marker: the marker
            :type marker: :class:`Marker`
            :returns: whether a marker could be captured
            :rtype: bool
        """
        self.move_cancel()

        if marker is not None:
            self._marker = marker
            self._marker.props.state = gtk.STATE_ACTIVE
            self._reset_position = marker.props.position
            self._parent.props.window.set_cursor(
                gtk.gdk.Cursor(gtk.gdk.SB_H_DOUBLE_ARROW))

            return True

        return False

    def move_update(self, position):
        """
            Moves the marker

            :param position: the current marker position
            :type position: float
            :returns: whether a marker could be moved
            :rtype: bool
        """
        if self._marker is not None:
            self._marker.props.position = position
            label = self._parent.get_label(self._marker)
            self._parent.set_tooltip_markup(label)

            return True
        
        return False

    def move_finish(self):
        """
            Finishes movement and releases the marker

            :returns: whether the movement could be finished
            :rtype: bool
        """
        if self._marker is not None:
            self._marker.props.state = gtk.STATE_NORMAL
            self._marker = None
            self._reset_position = -1
            self._parent.props.window.set_cursor(None)

            return True

        return False

    def move_cancel(self):
        """
            Cancels movement and releases the marker

            :returns: whether the movement could be cancelled
            :rtype: bool
        """
        if self._marker is not None:
            self._marker.props.position = self._reset_position
            self._marker.props.state = gtk.STATE_NORMAL
            self._marker = None
            self._reset_position = -1
            self._parent.props.window.set_cursor(None)

            return True

        return False

    def on_activate(self, widget, parent, context):
        """
            Starts movement of markers
        """
        self.move_begin(context.get('current-marker', None))

    def on_parent_button_press_event(self, widget, event):
        """
            Finishes or cancels movement of markers
        """
        if event.button == 1:
            return self.move_finish()
        elif event.button == 3:
            return self.move_cancel()

        return False

    def on_parent_motion_notify_event(self, widget, event):
        """
            Moves markers
        """
        position = event.x / widget.get_allocation().width

        return self.move_update(position)

    def on_parent_focus_out_event(self, widget, event):
        """
            Cancels movement of markers
        """
        self.move_cancel()

class NewMarkerMenuItem(MoveMarkerMenuItem):
    """
        Menu item allowing for insertion
        and instant movement of a marker
    """
    def __init__(self, name, after):
        MoveMarkerMenuItem.__init__(self, name, after,
            _('New Marker'), gtk.STOCK_NEW)

    def move_cancel(self):
        """
            Cancels movement and insertion of the marker

            :param parent: the parent
            :type parent: :class:`SeekProgressBar`
            :returns: whether the movement could be cancelled
            :rtype: bool
        """
        if self._marker is not None:
            remove_marker(self._marker)
            self._marker = None
            self._reset_position = -1
            self._parent.props.window.set_cursor(None)

            return True

        return False

    def on_activate(self, widget, parent, context):
        """
            Inserts a new marker and starts movement
        """
        context['current-marker'] = add_marker(context['current-position'])
        MoveMarkerMenuItem.on_activate(self, widget, parent, context)

# XXX: Example implementation only
# Bookmarks: "Add bookmark" (1 new marker)
# A-B-Repeat: "Repeat" (2 new marker, NW, NE)
def __create_progressbar_context_menu():
    items = []

    items.append(NewMarkerMenuItem('new-marker', []))

    for item in items:
        providers.register('progressbar-context-menu', item)
__create_progressbar_context_menu()

def __create_marker_context_menu():
    items = []

    def on_jumpto_item_activate(widget, name, parent, context):
        #parent.seek(context['current-marker'].props.position)
        position = context['current-marker'].props.position
        player.PLAYER.set_progress(position)

    def on_remove_item_activate(widget, name, parent, context):
        providers.unregister('playback-markers', context['current-marker'])

    items.append(menu.simple_menu_item('jumpto-marker',
        [], icon_name=gtk.STOCK_JUMP_TO,
        callback=on_jumpto_item_activate))
    items.append(MoveMarkerMenuItem('move-marker',
        [items[-1].name]))
    items.append(menu.simple_menu_item('remove-marker',
        [items[-1].name], icon_name=gtk.STOCK_REMOVE,
        callback=on_remove_item_activate))

    for item in items:
        providers.register('playback-marker-context-menu', item)
__create_marker_context_menu()

class VolumeControl(gtk.Alignment):
    """
        Encapsulates a button and a slider to
        control the volume indicating the current
        status via icon and tooltip
    """
    def __init__(self, player):
        self.__volume_setting = '%s/volume' % player._name
        gtk.Alignment.__init__(self, xalign=1)

        self.restore_volume = settings.get_option(self.__volume_setting, 1)
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

        event.add_callback(self.on_option_set, '%s_option_set' % player._name)

    def __update(self, volume):
        """
            Sets the volume level indicator
        """
        icon_name = 'audio-volume-muted'
        tooltip = _('Muted')

        if volume > 0:
            i = clamp(int(round(volume * 2)), 0, len(self.icon_names) - 1)
            icon_name = 'audio-volume-%s' % self.icon_names[i]
            #TRANSLATORS: Volume percentage
            tooltip = _('%d%%') % (volume * 100)

        if volume == 1.0:
            tooltip = _('Full Volume')

        if volume > 0:
            self.button.set_active(False)

        self.button_image.set_from_icon_name(icon_name, gtk.ICON_SIZE_BUTTON)
        self.button.set_tooltip_text(tooltip)
        self.slider.set_value(volume)
        self.slider.set_tooltip_text(tooltip)

    def on_scroll_event(self, widget, event):
        """
            Changes the volume on scrolling
        """
        page_increment = self.slider_adjustment.props.page_increment
        step_increment = self.slider_adjustment.props.step_increment
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
        elif event.direction == gtk.gdk.SCROLL_SMOOTH:
            if event.state & gtk.gdk.SHIFT_MASK:
                self.slider.set_value(value - event.delta_y * page_increment)
            else:
                self.slider.set_value(value - event.delta_y * step_increment)
            return True

        return False

    def on_button_toggled(self, button):
        """
            Mutes or unmutes the volume
        """
        if button.get_active():
            self.restore_volume = settings.get_option(self.__volume_setting, 1)
            volume = 0
        else:
            volume = self.restore_volume

        if self.restore_volume > 0:
            settings.set_option(self.__volume_setting, volume)

    def on_slider_value_changed(self, slider):
        """
            Stores the preferred volume
        """
        settings.set_option(self.__volume_setting, slider.get_value())

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
        if option == self.__volume_setting:
            self.__update(settings.get_option(option, 1))



def playpause(player):
    if player.get_state() in ('playing', 'paused'):
        player.toggle_pause()
    else:
        from xlgui import main
        page = main.get_selected_playlist()
        if page:
            pl = page.playlist
            if len(pl) == 0:
                return
            try:
                idx = page.view.get_selected_paths()[0][0]
            except IndexError:
                idx = 0
            player.queue.set_current_playlist(pl)
            pl.current_position = idx
            player.queue.play(track=pl.current)


def PlayPauseMenuItem(name, player, after):
    def factory(menu, parent, context):
        if player.is_playing():
            stock_id = gtk.STOCK_MEDIA_PAUSE
        else:
            stock_id = gtk.STOCK_MEDIA_PLAY

        item = gtk.ImageMenuItem(stock_id)
        item.connect('activate', lambda *args: playpause( player ), name, parent, context)

        return item
    return menu.MenuItem(name, factory, after=after)

def NextMenuItem(name, player, after):
    return menu.simple_menu_item(name, after, icon_name=gtk.STOCK_MEDIA_NEXT,
        callback=lambda *args: player.queue.next() )

def PrevMenuItem(name, player, after):
    return menu.simple_menu_item(name, after, icon_name=gtk.STOCK_MEDIA_PREVIOUS,
        callback=lambda *args: player.queue.prev() )

def StopMenuItem(name, player, after):
    return menu.simple_menu_item(name, after, icon_name=gtk.STOCK_MEDIA_STOP,
        callback=lambda *args: player.stop() )

