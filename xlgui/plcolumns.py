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
import gio
import gtk

from xl import settings
from xl.formatter import TrackFormatter
from xl.nls import gettext as _
from xlgui import icons

logger = logging.getLogger(__name__)

"""
    If you want to add a column to the Playlist object, or to the view columns
    menu(s), you just define the class here and have it inherit from "Column".
    The rest will be done automatically
"""

# various column definitions
class Column(object):
    __slots__ = ('id', 'display', 'renderer', 'size')

    id = ''
    display = ''
    renderer = gtk.CellRendererText
    size = 10 # default size
    formatter = TrackFormatter('')

    def __init__(self, playlist):
        self.playlist = playlist
        if self.__class__.__name__ == 'Column':
            raise NotImplementedError("Can't instantiate "
                "abstract class xlgui.playlist.Column")

    def data_func(self, col, cell, model, iter):
        """
            Generic data function
        """
        if not model.iter_is_valid(iter): return
        item = model.get_value(iter, 0)
        self.playlist.set_cell_weight(cell, item, iter)

    def set_properties(self, col, cellr):
        return

    def __repr__(self):
        return '%s(%s, %s, %s)' % (self.__class__.__name__,
            `self.id`, `self.display`, `self.size`)

class TrackNumberColumn(Column):
    size = '30'
    #TRANSLATORS: Title of the track number column
    display = _('#')
    id = 'tracknumber'

    def data_func(self, col, cell, model, iter):
        """
            Track number
        """
        track = model.get_value(iter, 0)

        self.formatter.set_property('format', '$%s' % self.id)
        cell.set_property('text', self.formatter.format(track))
        self.playlist.set_cell_weight(cell, track, iter)

    def set_properties(self, col, cellr):
        cellr.set_property('xalign', 1.0)

class TitleColumn(Column):
    size = 200
    display = _('Title')
    id = 'title'

class ArtistColumn(Column):
    size = 150
    display = _('Artist')
    id = 'artist'

class ComposerColumn(Column):
    size = 150
    display = _('Composer')
    id = 'composer'

class AlbumColumn(Column):
    size = 150
    display = _('Album')
    id = 'album'

class LengthColumn(Column):
    size = 50
    display = _('Length')
    id = '__length'

    def data_func(self, col, cell, model, iter):
        """
            Formats the track length
        """
        track = model.get_value(iter, 0)

        self.formatter.set_property('format', '$%s' % self.id)
        cell.set_property('text', self.formatter.format(track))
        self.playlist.set_cell_weight(cell, track, iter)

    def set_properties(self, col, cellr):
        cellr.set_property('xalign', 1.0)

class DiscNumberColumn(Column):
    size = 30
    display = _('Disc')
    id = 'discnumber'

    def data_func(self, col, cell, model, iter):
        """
            Disc number
        """
        track = model.get_value(iter, 0)

        disc = track.get_tag_display("discnumber")
        if disc is None:
            cell.set_property('text', '')
        else:
            cell.set_property('text', disc)
        self.playlist.set_cell_weight(cell, track, iter)

    def set_properties(self, col, cellr):
        cellr.set_property('xalign', 1.0)

class RatingColumn(Column):
    display = _('Rating')
    renderer = gtk.CellRendererPixbuf
    id = '__rating'

    def data_func(self, col, cell, model, iter):
        track = model.get_value(iter, 0)
        cell.props.pixbuf = icons.MANAGER.pixbuf_from_rating(
            track.get_rating())

    def set_properties(self, col, cellr):
        cellr.set_property('follow-state', False)
        col.set_attributes(cellr, pixbuf=1)

class DateColumn(Column):
    size = 50
    display = _('Date')
    id = 'date'

class GenreColumn(Column):
    size = 100
    display = _('Genre')
    id = 'genre'

class BitrateColumn(Column):
    size = 30
    display = _('Bitrate')
    id = '__bitrate'

    def data_func(self, col, cell, model, iter):
        """
            Shows the bitrate
        """
        track = model.get_value(iter, 0)
        cell.set_property('text', track.get_tag_display("__bitrate"))
        self.playlist.set_cell_weight(cell, track, iter)

    def set_properties(self, col, cellr):
        cellr.set_property('xalign', 1.0)

class IoLocColumn(Column):
    size = 200
    display = _('Location')
    id = '__loc'

class FilenameColumn(Column):
    size = 200
    display = _('Filename')
    id = 'filename'

    def data_func(self, col, cell, model, iter):
        track = model.get_value(iter, 0)

        self.formatter.set_property('format', '$%s' % self.id)
        cell.set_property('text', self.formatter.format(track))
        self.playlist.set_cell_weight(cell, track)

class PlayCountColumn(Column):
    size = 50
    display = _('Playcount')
    id = '__playcount'

    def set_properties(self, col, cellr):
        cellr.set_property('xalign', 1.0)

class BPMColumn(Column):
    size = 50
    display = _('BPM')
    id = 'bpm'

    def set_properties(self, col, cellr):
        cellr.set_property('xalign', 1.0)

class LastPlayedColumn(Column):
    size = 10
    display = _('Last played')
    id = '__last_played'

    def data_func(self, col, cell, model, iter):
        """
            Formats the last played time string
        """
        track = model.get_value(iter, 0)

        self.formatter.set_property('format', '$%s' % self.id)
        cell.set_property('text', self.formatter.format(track))
        self.playlist.set_cell_weight(cell, track, iter)

# this is where everything gets set up, including the menu items
COLUMNS = {}

items = globals()
keys = items.keys()
for key in keys:
    if type(items[key]) == type and \
        'Column' in key and key != 'Column':
        item = items[key]
        COLUMNS[item.id] = item

def setup_menu(menu, menu_items):
    items = ['tracknumber', 'title', 'artist', 'album',
        '__length', 'genre', '__rating', 'date']

    for key in COLUMNS.keys():
        if not key in items:
            items.append(key)

    for item in items:
        col = COLUMNS[item]
        display = col.display
        if col.id == 'tracknumber':
            display = _('Track Number')
        elif col.id == 'discnumber':
            display = _('Disc Number')

        menu_item = gtk.CheckMenuItem(display)
        menu_item.set_name('%s_col' % col.id)
        menu.insert(menu_item, items.index(item))

        menu_items[col.id] = menu_item
