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
from xlgui import rating

logger = logging.getLogger(__name__)

"""
    If you want to add a column to the Playlist object, or to the view columns
    menu(s), you just define the class here and have it inherit from "Column".
    The rest will be done automatically
"""

# various column definitions
class Column(object):
    id = ''
    display = ''
    renderer = gtk.CellRendererText
    size = 10 # default size
    datatype = str
    dataproperty = 'text'
    cellproperties = {}

    def __init__(self, container):
        self.container = container
        if self.__class__.__name__ == 'Column':
            raise NotImplementedError("Can't instantiate "
                "abstract class xlgui.container.Column")

    @classmethod
    def get_formatter(cls):
        return TrackFormatter('$%s'%cls.id)

    def data_func(self, col, cell, model, iter):
        if type(cell) == gtk.CellRendererText:
            self.container.set_cell_weight(cell, iter)

    def __repr__(self):
        return '%s(%s, %s, %s)' % (self.__class__.__name__,
            `self.id`, `self.display`, `self.size`)

    def get_column(self, index):
        cellr = self.renderer()
        gcol = gtk.TreeViewColumn(self.display, cellr,
                **{self.dataproperty: index})
        gcol.set_cell_data_func(cellr, self.data_func)
        for name, val in self.cellproperties.iteritems():
            cellr.set_property(name, val)
        gcol.set_fixed_width(int(self.size))
        return gcol


class TrackNumberColumn(Column):
    size = '30'
    #TRANSLATORS: Title of the track number column
    display = _('#')
    id = 'tracknumber'
    cellproperties = {'xalign': 1.0}

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
    cellproperties = {'xalign': 1.0}

class DiscNumberColumn(Column):
    size = 30
    display = _('Disc')
    id = 'discnumber'
    cellproperties = {'xalign': 1.0}


class RatingFormatter(object):
    def format(self, track):
        idx = track.get_rating()
        try:
            return rating.rating_images[idx]
        except IndexError:
            logger.debug("IDX error! got %s." % idx)
            return rating.rating_images[0]

class RatingColumn(Column):
    display = _('Rating')
    renderer = gtk.CellRendererPixbuf
    id = '__rating'
    datatype = gtk.gdk.Pixbuf
    dataproperty = 'pixbuf'
    cellproperties = {'follow-state': False}

    @classmethod
    def get_formatter(cls):
        return RatingFormatter()

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
    cellproperties = {'xalign': 1.0}

class IoLocColumn(Column):
    size = 200
    display = _('Location')
    id = '__loc'

class FilenameColumn(Column):
    size = 200
    display = _('Filename')
    id = 'filename'

class PlayCountColumn(Column):
    size = 50
    display = _('Playcount')
    id = '__playcount'
    cellproperties = {'xalign': 1.0}

class BPMColumn(Column):
    size = 50
    display = _('BPM')
    id = 'bpm'
    cellproperties = {'xalign': 1.0}

class LastPlayedColumn(Column):
    size = 10
    display = _('Last played')
    id = '__last_played'



# this is where everything gets set up, including the menu items
COLUMNS = {}
FORMATTERS = {}

items = globals()
keys = items.keys()
for key in keys:
    if type(items[key]) == type and \
        'Column' in key and key != 'Column':
        item = items[key]
        COLUMNS[item.id] = item
        FORMATTERS[item.id] = item.get_formatter()

COLUMNS_BY_DISPLAY = {}
for col in COLUMNS.values():
    COLUMNS_BY_DISPLAY[col.display] = col

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
