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

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from xl import event, formatter, main, settings, xdg
from xl.nls import gettext as _
import xlgui
from xlgui import cover, guiutil
from xlgui.widgets import playlist
from xlgui.widgets.playback import PlaybackProgressBar


class TrackInfoPane(Gtk.Bin):
    """
    Displays cover art and track data
    """

    def __init__(self, player):
        Gtk.Bin.__init__(self)
        self.__player = player

        builder = Gtk.Builder()
        builder.add_from_file(xdg.get_data_path('ui', 'widgets', 'track_info.ui'))

        info_box = builder.get_object('info_box')
        info_box.get_parent().remove(info_box)
        self.add(info_box)

        self.__auto_update = False
        self.__display_progress = False
        self.__formatter = formatter.TrackFormatter(
            _(
                '<span size="x-large" weight="bold">$title</span>\n'
                'by $artist\n'
                'from $album'
            )
        )
        self.__formatter.connect('notify::format', self.on_notify_format)
        self.__default_text = '<span size="x-large" ' 'weight="bold">%s</span>\n\n' % _(
            'Not Playing'
        )
        self.__cover_size = None
        self.__timer = None
        self.__track = None

        self.info_label = builder.get_object('info_label')
        self.action_area = builder.get_object('action_area')
        self.progress_box = builder.get_object('progress_box')
        self.playback_image = builder.get_object('playback_image')
        self.progressbar = PlaybackProgressBar(player)
        guiutil.gtk_widget_replace(builder.get_object('progressbar'), self.progressbar)

        self.cover = cover.CoverWidget(builder.get_object('cover_image'))
        self.cover.hide()
        self.cover.set_no_show_all(True)

        self.clear()
        self.__update_widget_state()

    def destroy(self):
        """
        Cleanups
        """
        # Make sure to disconnect callbacks
        self.set_auto_update(False)

        Gtk.Bin.destroy(self)

    def get_auto_update(self):
        """
        Gets whether the info pane shall
        be automatically updated or not

        :rtype: bool
        """
        return self.__auto_update

    def set_auto_update(self, auto_update):
        """
        Sets whether the info pane shall
        be automatically updated or not

        :param auto_update: enable or disable
            automatic updating
        :type auto_update: bool
        """
        if auto_update != self.__auto_update:
            self.__auto_update = auto_update

            p_evts = [
                'playback_player_end',
                'playback_track_start',
                'playback_toggle_pause',
                'playback_error',
            ]
            events = ['track_tags_changed', 'cover_set', 'cover_removed']

            if auto_update:
                for e in p_evts:
                    event.add_ui_callback(getattr(self, 'on_%s' % e), e, self.__player)
                for e in events:
                    event.add_ui_callback(getattr(self, 'on_%s' % e), e)

                self.set_track(self.__player.current)
            else:
                for e in p_evts:
                    event.remove_callback(getattr(self, 'on_%s' % e), e, self.__player)
                for e in events:
                    event.remove_callback(getattr(self, 'on_%s' % e), e)

    def get_cover_size(self):
        """
        Gets the preferred cover size

        :rtype: int
        """
        return self.__cover_size or settings.get_option('gui/cover_width', 100)

    def set_cover_size(self, cover_size):
        """
        Overrides the cover size to display,
        set to None to use global default

        :param cover_size: the preferred cover size
        :type cover_size: int
        """
        self.__cover_size = cover_size

    def get_default_text(self):
        """
        Gets the default text displayed
        when the playback is stopped

        :rtype: string
        """
        return self.__default_text

    def set_default_text(self, default_text):
        """
        Sets the default text displayed
        when the playback is stopped

        :param default_text: the new default text
        :type default_text: string
        """
        self.__default_text = default_text

    def get_display_progress(self):
        """
        Returns whether the progress indicator
        is currently visible or not

        :rtype: bool
        """
        return self.__display_progress

    def set_display_progress(self, display_progress):
        """
        Shows or hides the progress indicator. The
        indicator will not be displayed if the
        currently displayed track is not playing.

        :param display_progress: Whether to show
            or hide the progress indicator
        :type display_progress: bool
        """
        self.__display_progress = display_progress
        self.__update_widget_state()

    def get_info_format(self):
        """
        Gets the current format used
        to display the track data

        :rtype: string
        """
        return self.__formatter.props.format

    def set_info_format(self, format):
        """
        Sets the format used to display the track data

        :param format: the format, see the documentation
            of :class:`string.Template` for details
        :type format: string
        """
        self.__formatter.props.format = format

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

        self.__track = track

        self.cover.set_track(track)

        self.info_label.set_markup(self.__formatter.format(track, markup_escape=True))
        self.__update_widget_state()

    def __update_widget_state(self):
        if self.__display_progress:
            if self.__track == self.__player.current and not self.__player.is_stopped():

                if self.__player.is_paused():
                    icon_name = 'media-playback-pause'
                else:
                    icon_name = 'media-playback-start'
                self.playback_image.set_from_icon_name(
                    icon_name, Gtk.IconSize.SMALL_TOOLBAR
                )

            self.progress_box.set_no_show_all(False)
            self.progress_box.set_visible(True)
            self.progressbar.set_visible(True)
        else:
            self.progress_box.set_visible(False)
            self.progress_box.set_no_show_all(True)
            self.progressbar.set_visible(True)

    def clear(self):
        """
        Resets the info pane
        """

        self.cover.set_track(None)
        self.info_label.set_markup(self.__default_text)

        self.__track = None
        self.__update_widget_state()

    def get_action_area(self):
        """
        Retrieves the action area
        at the end of the pane

        :rtype: :class:`Gtk.Box`
        """
        return self.action_area

    def on_notify_format(self, formatter, format):
        """
        Updates the displayed data after format changes
        """
        if self.__track is not None:
            self.set_track(self.__track)

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

    def on_playback_error(self, event, player, message):
        """
        Clears the info pane on playback errors
        """
        self.clear()

    def on_track_tags_changed(self, event, track, tags):
        """
        Updates the info pane on tag changes
        """
        if (
            self.__player is not None
            and not self.__player.is_stopped()
            and track is self.__track
        ):
            self.set_track(track)

    def on_cover_set(self, event, covers, track):
        """
        Updates the info pane on cover set
        """
        if track is self.__track:
            self.set_track(track)

    def on_cover_removed(self, event, covers, track):
        """
        Updates the info pane on cover removal
        """
        if track is self.__track:
            self.set_track(track)


class ToolTip:
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
            raise TypeError(
                "cannot create instance of abstract "
                "(non-instantiable) type `ToolTip'"
            )

        self.__widget = widget
        self.__widget.unparent()  # Just to be sure

        parent.set_has_tooltip(True)
        parent.connect('query-tooltip', self.on_query_tooltip)

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        """
        Puts the custom widget into the tooltip
        """
        tooltip.set_custom(self.__widget)

        return True


class TrackToolTip(TrackInfoPane, ToolTip):
    """
    Track specific tooltip class, displays
    track data and progress indicators
    """

    def __init__(self, parent, player):
        """
        :param parent: the parent widget the tooltip
            should be attached to
        """
        TrackInfoPane.__init__(self, player)
        ToolTip.__init__(self, parent, self)

        self.set_border_width(6)
        self.info_label.set_ellipsize(Pango.EllipsizeMode.NONE)
        self.cover.set_no_show_all(False)
        self.cover.show_all()

    def destroy(self):
        """
        Cleanups
        """
        TrackInfoPane.destroy(self)


class StatusbarTextFormatter(formatter.Formatter):
    """
    A text formatter for status indicators
    """

    def __init__(self, format):
        """
        :param format: The initial format, see the documentation
            of string.Template for details
        :type format: string
        """
        formatter.Formatter.__init__(self, format)

        self._substitutions = {
            'collection_count': self.get_collection_count,
            'playlist_count': self.get_playlist_count,
            'playlist_duration': self.get_playlist_duration,
        }

    def get_collection_count(self):
        """
        Retrieves the collection count
        """
        return _('%d in collection') % main.exaile().collection.get_count()

    def get_playlist_count(self, selection='none'):
        """
        Retrieves the count of tracks in either the
        full playlist or the current selection

        :param selection: 'none' for playlist count only,
            'override' for selection count if tracks are selected,
            playlist count otherwise, 'only' for selection count only
        :type selection: string
        """
        page = xlgui.main.get_selected_page()

        if not isinstance(page, playlist.PlaylistPage):
            return ''

        playlist_count = len(page.playlist)
        selection_count = page.view.get_selection_count()

        if selection == 'none':
            count = playlist_count
            text = _('%d showing')
        elif selection == 'override':
            if selection_count > 1:
                count = selection_count
                text = _('%d selected')
            else:
                count = playlist_count
                text = _('%d showing')
        elif selection == 'only':
            if selection_count > 1:
                count = selection_count
                text = _('%d selected')
            else:
                count = 0
        else:
            raise ValueError(
                'Invalid argument "%s" passed to parameter '
                '"selection" for "playlist_count", possible arguments are '
                '"none", "override" and "only"' % selection
            )

        if count == 0:
            return ''

        return text % count

    def get_playlist_duration(self, format='short', selection='none'):
        """
        Retrieves the duration of all tracks in
        the playlist or within the selection

        :param format: Verbosity of the output
            Possible values are short, long or verbose
            yielding "1:02:42", "1h, 2m, 42s" or
            "1 hour, 2 minutes, 42 seconds"
        :type format: string
        :param selection: 'none' for playlist count only,
            'override' for selection count if tracks are selected,
            playlist count otherwise, 'only' for selection count only
        :type selection: string
        """
        page = xlgui.main.get_selected_page()

        if not isinstance(page, playlist.PlaylistPage):
            return ''

        playlist_duration = sum(t.get_tag_raw('__length') or 0 for t in page.playlist)
        selection_tracks = page.view.get_selected_tracks()
        selection_count = len(selection_tracks)
        selection_duration = sum(
            t.get_tag_raw('__length') or 0 for t in selection_tracks
        )

        if selection == 'none':
            duration = playlist_duration
        elif selection == 'override':
            if selection_count > 1:
                duration = selection_duration
            else:
                duration = playlist_duration
        elif selection == 'only':
            if selection_count > 1:
                duration = selection_duration
            else:
                duration = 0
        else:
            raise ValueError(
                'Invalid argument "%s" passed to parameter '
                '"selection" for "playlist_duration", possible arguments are '
                '"none", "override" and "only"' % selection
            )

        if duration == 0:
            return ''

        return formatter.LengthTagFormatter.format_value(duration, format)


class Statusbar:
    """
    Convenient access to multiple status labels
    """

    def __init__(self, status_bar):
        """
        Initialises the status bar
        """
        self.status_bar = status_bar
        self.formatter = StatusbarTextFormatter(
            settings.get_option(
                'gui/statusbar_info_format',
                '${playlist_count:selection=override, suffix= }'
                '${playlist_duration:selection=override, format=long, prefix=(, suffix=)\\, }'
                '$collection_count',
            )
        )

        self.info_label = Gtk.Label()

        box = self.status_bar.get_message_area()

        box.pack_end(self.info_label, False, True, 0)

        self.context_id = self.status_bar.get_context_id('status')
        self.message_ids = []

    def set_status(self, status, timeout=0):
        """
        Sets the status message
        """
        self.message_ids += [self.status_bar.push(self.context_id, status)]

        if timeout > 0:
            GLib.timeout_add_seconds(timeout, self.clear_status)

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

    def update_info(self):
        """
        Updates the info label text
        """
        self.info_label.set_label(self.formatter.format())


# TODO: Check if we can get a progress indicator in here somehow
class Splash:
    """
    A splash screen suitable for indicating startup;
    will automatically be destroyed after GUI startup
    """

    def __init__(self):
        builder = Gtk.Builder()
        builder.add_from_file(xdg.get_data_path('ui', 'splash.ui'))

        image = builder.get_object('splash_image')
        image.set_from_file(xdg.get_data_path('images', 'splash.png'))

        self.window = builder.get_object('SplashScreen')

    def destroy(self):
        """
        Destroys the splash screen
        """
        self.window.destroy()

    def show(self):
        """
        Shows the splash screen
        """
        # Show the splash screen without causing startup notification.
        Gtk.Window.set_auto_startup_notification(False)
        self.window.show_all()
        Gtk.Window.set_auto_startup_notification(True)

        # Ensure the splash is completely drawn before moving on
        while Gtk.events_pending():
            Gtk.main_iteration()

    def hide(self):
        """
        Hides the splash screen
        """
        self.window.hide()
