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
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

import logging
import time

from xl import common, event, player, settings, providers
from xl.common import classproperty
from xl.formatter import TrackFormatter
from xl.nls import gettext as _
from xlgui import icons
from xlgui.widgets import dialogs, rating, menu

logger = logging.getLogger(__name__)

DEFAULT_COLUMNS = ['tracknumber', 'title', 'album', 'artist', '__length']


class Column(Gtk.TreeViewColumn):
    name = ''
    display = ''
    menu_title = classproperty(lambda c: c.display)
    renderer = Gtk.CellRendererText
    formatter = classproperty(lambda c: TrackFormatter('$%s' % c.name))
    size = 10  # default size
    autoexpand = False  # whether to expand to fit space in Autosize mode
    datatype = str
    dataproperty = 'text'
    cellproperties = {}

    def __init__(self, container, player, font, size_ratio):
        if self.__class__ == Column:
            raise NotImplementedError(
                "Can't instantiate " "abstract class %s" % repr(self.__class__)
            )

        self._size_ratio = size_ratio
        self.container = container
        self.player = player
        self.settings_width_name = "gui/col_width_%s" % self.name
        self.cellrenderer = self.renderer()
        self.destroyed = False

        super(Column, self).__init__(self.display)
        self.props.min_width = 3

        self.pack_start(self.cellrenderer, True)
        self.set_cell_data_func(self.cellrenderer, self.data_func)

        try:
            self.cellrenderer.set_property('font-desc', font)
        except TypeError:
            pass  # not all cells have a font

        try:
            self.cellrenderer.set_property('ellipsize', Pango.EllipsizeMode.END)
        except TypeError:  # cellrenderer doesn't do ellipsize - eg. rating
            pass

        for name, val in self.cellproperties.items():
            self.cellrenderer.set_property(name, val)

        self.set_reorderable(True)
        self.set_clickable(True)
        self.set_sizing(Gtk.TreeViewColumnSizing.FIXED)  # needed for fixed-height mode
        self.set_sort_order(Gtk.SortType.DESCENDING)

        # hack to allow button press events on the header to be detected
        self.set_widget(Gtk.Label(label=self.display))

        # Save the width of the column when it changes; save the notify id so
        # we don't emit an event when we're programmatically setting the width
        self._width_notify = self.connect('notify::width', self.on_width_changed)
        self._setup_sizing()

        event.add_ui_callback(
            self.on_option_set, "gui_option_set", destroy_with=container
        )

    def on_option_set(self, typ, obj, data):
        if data in ("gui/resizable_cols", self.settings_width_name):
            self._setup_sizing()

    def on_width_changed(self, column, wid):
        # Don't call get_width in the delayed function; it can be incorrect.
        # See https://github.com/exaile/exaile/issues/580
        self._delayed_width_changed(self.get_width())

    @common.glib_wait(100)
    def _delayed_width_changed(self, width):
        if not self.destroyed and width != settings.get_option(
            self.settings_width_name, -1
        ):
            settings.set_option(self.settings_width_name, width)

    def _setup_sizing(self):
        with self.handler_block(self._width_notify):
            if settings.get_option('gui/resizable_cols', False):
                self.set_resizable(True)
                self.set_expand(False)
                width = settings.get_option(self.settings_width_name, self.size)
                self.set_fixed_width(width)
            else:
                self.set_resizable(False)
                if self.autoexpand:
                    self.set_expand(True)
                    self.set_fixed_width(1)
                else:
                    self.set_expand(False)
                    self.set_fixed_width(self.size)

    def set_size_ratio(self, ratio):
        self._size_ratio = ratio

    def get_size_ratio(self):
        '''Returns how much bigger or smaller an icon should be'''
        return self._size_ratio

    def data_func(self, col, cell, model, iter, user_data):
        # warning: this function gets called from the render function, so do as
        #          little work as possible!

        cache = model.get_value(iter, 1)

        text = cache.get(self.name)
        if text is None:
            track = model.get_value(iter, 0)
            text = self.formatter.format(track)
            cache[self.name] = text

        cell.props.text = text

    def __repr__(self):
        return '%s(%r, %r, %r)' % (
            self.__class__.__name__,
            self.name,
            self.display,
            self.size,
        )


class EditableColumn(Column):
    renderer = Gtk.CellRendererText

    def __init__(self, *args):
        Column.__init__(self, *args)
        self.cellrenderer.connect('edited', self.on_edited)
        self.cellrenderer.connect('editing-started', self.on_editing_started)
        self.cellrenderer.connect('editing-canceled', self._reset_editable)

    def could_edit(self, treeview, path, event):
        # Returns True if an edit could take place

        # The 'aligned area' seems to correspond to where the text actually
        # is rendered. If the coordinates don't overlap that, then we don't
        # allow the edit to occur. Conveniently, this should deal with RTL
        # issues as well (not tested)
        cell_area = treeview.get_cell_area(path, self)

        # Ensure the renderer text attribute is updated before finding
        # it's width
        model = treeview.get_model()
        iter = model.get_iter(path)
        self.data_func(self, self.cellrenderer, model, iter, None)

        aa = self.cellrenderer.get_aligned_area(treeview, 0, cell_area)
        return aa.x <= event.x <= aa.x + aa.width

    def start_editing(self, treeview, path):
        # We normally keep the cell renderer's `editable` False so it doesn't
        # trigger editing on double-click. To actually start editing, we have
        # to temporarily set it to True until the user finishes editing.
        self.cellrenderer.props.editable = True
        treeview.set_cursor_on_cell(path, self, self.cellrenderer, start_editing=True)

    def _reset_editable(self, cellrenderer):
        cellrenderer.props.editable = False

    def on_edited(self, cellrenderer, path, new_text):
        self._reset_editable(cellrenderer)

        # Undo newline escaping
        new_text = new_text.replace('\\n', '\n')

        validate = getattr(self, 'validate', None)
        if validate:
            try:
                new_text = validate(new_text)
            except ValueError:
                return

        # Update the track
        model = self.get_tree_view().get_model()
        iter = model.get_iter(path)
        track = model.get_value(iter, 0)

        if not track.set_tag_raw(self.name, new_text):
            return

        # Invalidate/redraw the value immediately because we know
        # it's just a single change
        model.get_value(iter, 1).clear()
        model.row_changed(path, iter)

        if not track.write_tags():
            dialogs.error(
                None,
                "Error writing tags to %s"
                % GObject.markup_escape_text(track.get_loc_for_io()),
            )

    def on_editing_started(self, cellrenderer, editable, path):
        # Retrieve text in original form
        model = self.get_tree_view().get_model()

        iter = model.get_iter(path)
        track = model.get_value(iter, 0)

        text = getattr(self, 'edit_formatter', self.formatter).format(track)

        # Escape newlines
        text = text.replace('\n', '\\n')

        # Set text
        editable.set_text(text)

        if hasattr(self, 'validate'):
            editable.connect('changed', self.on_editing_changed)

    def on_editing_changed(self, w):
        try:
            self.validate(w.get_text())
        except ValueError:
            w.get_style_context().add_class('warning')
        else:
            w.get_style_context().remove_class('warning')


class TrackNumberColumn(Column):
    name = 'tracknumber'
    # TRANSLATORS: Title of the track number column
    display = _('#')
    menu_title = _('Track Number')
    size = 30
    cellproperties = {'xalign': 1.0, 'width-chars': 4}


providers.register('playlist-columns', TrackNumberColumn)


class TitleColumn(EditableColumn):
    name = 'title'
    display = _('Title')
    size = 200
    autoexpand = True


providers.register('playlist-columns', TitleColumn)


class ArtistColumn(EditableColumn):
    name = 'artist'
    display = _('Artist')
    size = 150
    autoexpand = True


providers.register('playlist-columns', ArtistColumn)


class AlbumArtistColumn(EditableColumn):
    name = 'albumartist'
    display = _('Album artist')
    size = 150
    autoexpand = True


providers.register('playlist-columns', AlbumArtistColumn)


class ComposerColumn(EditableColumn):
    name = 'composer'
    display = _('Composer')
    size = 150
    autoexpand = True


providers.register('playlist-columns', ComposerColumn)


class AlbumColumn(EditableColumn):
    name = 'album'
    display = _('Album')
    size = 150
    autoexpand = True


providers.register('playlist-columns', AlbumColumn)


class LengthColumn(Column):
    name = '__length'
    display = _('Length')
    size = 50
    cellproperties = {'xalign': 1.0}


providers.register('playlist-columns', LengthColumn)


class DiscNumberColumn(Column):
    name = 'discnumber'
    display = _('Disc')
    menu_title = _('Disc Number')
    size = 40
    cellproperties = {'xalign': 1.0, 'width-chars': 2}


providers.register('playlist-columns', DiscNumberColumn)


class RatingColumn(Column):
    name = '__rating'
    display = _('Rating')
    renderer = rating.RatingCellRenderer
    dataproperty = 'rating'
    cellproperties = {'follow-state': False}

    def __init__(self, *args):
        Column.__init__(self, *args)
        self.cellrenderer.connect('rating-changed', self.on_rating_changed)
        self.cellrenderer.size_ratio = self.get_size_ratio()
        self.saved_model = None

    def data_func(self, col, cell, model, iter, user_data):
        track = model.get_value(iter, 0)
        cell.props.rating = track.get_rating()
        self.saved_model = model

    def __get_size(self):
        """
        Retrieves the optimal size
        """
        size = icons.MANAGER.pixbuf_from_rating(0, self.get_size_ratio()).get_width()
        size += 2  # FIXME: Find the source of this

        return size

    size = property(__get_size)

    def on_rating_changed(self, widget, path, rating):
        """
        Updates the rating of the selected track
        """
        iter = self.saved_model.get_iter(path)
        track = self.saved_model.get_value(iter, 0)
        oldrating = track.get_rating()

        if rating == oldrating:
            rating = 0

        rating = track.set_rating(rating)
        event.log_event('rating_changed', self, rating)


providers.register('playlist-columns', RatingColumn)


class DateColumn(Column):
    name = 'date'
    display = _('Date')
    size = 50


providers.register('playlist-columns', DateColumn)


class YearColumn(Column):
    name = 'year'
    display = _('Year')
    size = 45


providers.register('playlist-columns', YearColumn)


class GenreColumn(EditableColumn):
    name = 'genre'
    display = _('Genre')
    size = 100
    autoexpand = True


providers.register('playlist-columns', GenreColumn)


class BitrateColumn(Column):
    name = '__bitrate'
    display = _('Bitrate')
    size = 45
    cellproperties = {'xalign': 1.0}


providers.register('playlist-columns', BitrateColumn)


class IoLocColumn(Column):
    name = '__loc'
    display = _('Location')
    size = 200
    autoexpand = True


providers.register('playlist-columns', IoLocColumn)


class FilenameColumn(Column):
    name = '__basename'
    display = _('Filename')
    size = 200
    autoexpand = True


providers.register('playlist-columns', FilenameColumn)


class PlayCountColumn(Column):
    name = '__playcount'
    display = _('Playcount')
    size = 50
    cellproperties = {'xalign': 1.0}


providers.register('playlist-columns', PlayCountColumn)


class BPMColumn(EditableColumn):
    name = 'bpm'
    display = _('BPM')
    size = 40
    cellproperties = {'xalign': 1.0, 'editable': True}
    validate = lambda s, v: int(v)


providers.register('playlist-columns', BPMColumn)


class LanguageColumn(EditableColumn):
    name = 'language'
    display = _('Language')
    size = 100
    autoexpand = True


providers.register('playlist-columns', LanguageColumn)


class LastPlayedColumn(Column):
    name = '__last_played'
    display = _('Last played')
    size = 80


providers.register('playlist-columns', LastPlayedColumn)


class DateAddedColumn(Column):
    name = '__date_added'
    display = _('Date added')
    size = 80


providers.register('playlist-columns', DateAddedColumn)


class ScheduleTimeColumn(Column):
    name = 'schedule_time'
    display = _('Schedule')
    size = 80

    def __init__(self, *args):
        Column.__init__(self, *args)
        self.timeout_id = None

        event.add_ui_callback(
            self.on_queue_current_playlist_changed,
            'queue_current_playlist_changed',
            player.QUEUE,
        )
        event.add_ui_callback(
            self.on_playback_player_start, 'playback_player_start', player.PLAYER
        )
        event.add_ui_callback(
            self.on_playback_player_end, 'playback_player_end', player.PLAYER
        )

    def data_func(self, col, cell, model, iter, user_data):
        """
        Sets the schedule time if appropriate
        """
        text = None
        playlist = self.container.playlist

        # Only display the schedule time if
        # 1) there is playback at all
        # 2) this playlist is currently played
        # 3) playback is not in shuffle mode
        # 4) the current track is not repeated
        if (
            not self.player.is_stopped()
            and playlist is self.player.queue.current_playlist
            and playlist.shuffle_mode == 'disabled'
            and playlist.repeat_mode != 'track'
        ):
            track = model.get_value(iter, 0)
            position = playlist.index(track)
            current_position = playlist.current_position

            # 5) this track is after the currently played one
            if position > current_position:
                # The delay is the accumulated length of all tracks
                # between the currently playing and this one
                try:
                    delay = sum(
                        t.get_tag_raw('__length')
                        for t in playlist[current_position:position]
                    )
                except TypeError:
                    # on tracks with length == None, we cannot determine
                    # when later tracks will play
                    pass
                else:
                    # Subtract the time which already has passed
                    delay -= self.player.get_time()
                    # The schedule time is the current time plus delay
                    schedule_time = time.localtime(time.time() + delay)
                    text = time.strftime('%H:%M', schedule_time)

        cell.props.text = text

    def start_timer(self):
        """
        Enables realtime updates
        """
        timeout_id = self.timeout_id

        # Make sure to stop any timer still running
        if timeout_id is not None:
            GLib.source_remove(timeout_id)

        self.timeout_id = GLib.timeout_add_seconds(60, self.on_timeout)

    def stop_timer(self):
        """
        Disables realtime updates
        """
        timeout_id = self.timeout_id

        if timeout_id is not None:
            GLib.source_remove(timeout_id)
            self.timeout_id = None

        # Update once more
        self.on_timeout()

    def on_timeout(self):
        """
        Makes sure schedule times are updated in realtime
        """
        self.queue_resize()
        view = self.get_tree_view()
        if view is not None:
            view.queue_draw()
            return True

        self.timeout_id = None
        return False

    def on_queue_current_playlist_changed(self, e, queue, current_playlist):
        """
        Disables realtime updates for all playlists
        and re-enables them for the current playlist
        """
        self.stop_timer()

        if current_playlist is self.container.playlist:
            self.start_timer()

    def on_playback_player_start(self, e, player, track):
        """
        Enables realtime updates for the current playlist
        """
        self.stop_timer()

        if self.player.queue.current_playlist is self.container.playlist:
            logger.debug('Playback started, enabling realtime updates')
            self.start_timer()

    def on_playback_player_end(self, e, player, track):
        """
        Disables realtime updates for all playlists
        """
        self.stop_timer()


providers.register('playlist-columns', ScheduleTimeColumn)


class CommentColumn(EditableColumn):
    name = 'comment'
    display = _('Comment')
    size = 200
    autoexpand = True
    # Remove the newlines to fit into the vertical space of rows
    formatter = TrackFormatter('${comment:newlines=strip}')
    edit_formatter = TrackFormatter('$comment')
    cellproperties = {'editable': True}


providers.register('playlist-columns', CommentColumn)


class GroupingColumn(EditableColumn):
    name = 'grouping'
    display = _('Grouping')
    size = 200
    autoexpand = True


providers.register('playlist-columns', GroupingColumn)


def _validate_time(self, v):
    rv = 0
    m = 1
    for i in reversed(v.split(':')):
        i = int(i)
        if i < 0 or i > 59:
            raise ValueError
        rv += i * m
        m *= 60
    return rv


class StartOffsetColumn(EditableColumn):
    name = '__startoffset'
    display = _('Start Offset')
    size = 50
    cellproperties = {'xalign': 1.0, 'editable': True}
    validate = _validate_time


providers.register('playlist-columns', StartOffsetColumn)


class StopOffsetColumn(EditableColumn):
    name = '__stopoffset'
    display = _('Stop Offset')
    size = 50
    cellproperties = {'xalign': 1.0, 'editable': True}
    validate = _validate_time


providers.register('playlist-columns', StopOffsetColumn)


class WebsiteColumn(EditableColumn):
    name = 'website'
    display = _('Website')
    size = 200
    autoexpand = True


providers.register('playlist-columns', WebsiteColumn)


class ColumnMenuItem(menu.MenuItem):
    """
    A menu item dedicated to display the
    status of a column and change it
    """

    def __init__(self, column, after=None):
        """
        Sets up the menu item from a column description

        :param column: the playlist column
        :type column: :class:`Column`
        :param after: enumeration of menu
            items before this one
        :type after: list of strings
        """
        menu.MenuItem.__init__(self, column.name, self.factory, after)
        self.title = column.menu_title

    def factory(self, menu, parent, context):
        """
        Creates the menu item
        """
        item = Gtk.CheckMenuItem.new_with_label(self.title)
        active = self.is_selected(self.name, parent, context)
        item.set_active(active)
        item.connect('activate', self.on_item_activate, self.name, parent, context)

        return item

    def is_selected(self, name, parent, context):
        """
        Returns whether a column is selected

        :rtype: bool
        """
        return name in settings.get_option('gui/columns', DEFAULT_COLUMNS)

    def on_item_activate(self, menu_item, name, parent, context):
        """
        Updates the columns setting
        """
        columns = settings.get_option('gui/columns', DEFAULT_COLUMNS)

        if name in columns:
            columns.remove(name)
        else:
            columns.append(name)

        settings.set_option('gui/columns', columns)


def __register_playlist_columns_menuitems():
    """
    Registers standard menu items for playlist columns
    """

    def is_column_selected(name, parent, context):
        """
        Returns whether a menu item should be checked
        """
        return name in settings.get_option('gui/columns', DEFAULT_COLUMNS)

    def is_resizable(name, parent, context):
        """
        Returns whether manual or automatic sizing is requested
        """
        resizable = settings.get_option('gui/resizable_cols', False)

        if name == 'resizable':
            return resizable
        elif name == 'autosize':
            return not resizable

    def on_column_item_activate(menu_item, name, parent, context):
        """
        Updates columns setting
        """
        columns = settings.get_option('gui/columns', DEFAULT_COLUMNS)

        if name in columns:
            columns.remove(name)
        else:
            columns.append(name)

        settings.set_option('gui/columns', columns)

    def on_sizing_item_activate(menu_item, name, parent, context):
        """
        Updates column sizing setting
        """

        # Ignore the activation if the menu item is not actually active
        if not menu_item.get_active():
            return

        if name == 'resizable':
            settings.set_option('gui/resizable_cols', True)
        elif name == 'autosize':
            settings.set_option('gui/resizable_cols', False)

    columns = [
        'tracknumber',
        'title',
        'artist',
        'album',
        '__length',
        'genre',
        '__rating',
        'date',
    ]

    for provider in providers.get('playlist-columns'):
        if provider.name not in columns:
            columns += [provider.name]

    menu_items = []
    after = []

    for name in columns:
        column = providers.get_provider('playlist-columns', name)
        menu_item = ColumnMenuItem(column, after)
        menu_items += [menu_item]
        after = [menu_item.name]

    separator_item = menu.simple_separator('columns_separator', after)
    menu_items += [separator_item]
    after = [separator_item.name]

    sizing_item = menu.radio_menu_item(
        'resizable',
        after,
        _('_Resizable'),
        'column-sizing',
        is_resizable,
        on_sizing_item_activate,
    )
    menu_items += [sizing_item]
    after = [sizing_item.name]

    sizing_item = menu.radio_menu_item(
        'autosize',
        after,
        _('_Autosize'),
        'column-sizing',
        is_resizable,
        on_sizing_item_activate,
    )
    menu_items += [sizing_item]

    for menu_item in menu_items:
        providers.register('playlist-columns-menu', menu_item)


__register_playlist_columns_menuitems()
