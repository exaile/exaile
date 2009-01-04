# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
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

import gtk
from xl.nls import gettext as _

"""
    If you want to add a column to the Playlist object, or to the view columns
    menu(s), you just define the class here and have it inherit from "Column".
    The rest will be done automatically
"""

# various column definitions
class Column(object):
    size = 10 # default size
    display = ''
    renderer = gtk.CellRendererText
    id = ''

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
        self.playlist.set_cell_weight(cell, item)

    def set_properties(self, col, cellr):
        return
    
    def __repr__(self):
        return '%s(%s, %s, %s)' % (self.__class__.__name__,
            `self.id`, `self.display`, `self.size`)

class TrackNumberColumn(Column):
    size = '30'
    display = _('#')
    id = 'tracknumber'

    def data_func(self, col, cell, model, iter):
        """
            Track number
        """
        item = model.get_value(iter, 0)

        track = item.get_track()
        if track == -1:
            cell.set_property('text', '')
        else:
            cell.set_property('text', track)
        self.playlist.set_cell_weight(cell, item)

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
    id = 'length'

    def data_func(self, col, cell, model, iter):
        """ 
            Formats the track length
        """
        item = model.get_value(iter, 0)
        try:
            seconds = item.get_duration()
            text = _("%d:%02d") % (seconds // 60, seconds % 60)
        except:
            text = _("0:00")
        cell.set_property('text', text)
        self.playlist.set_cell_weight(cell, item)

class DiscNumberColumn(Column):
    size = 30
    display = _('Disc')
    id = 'discnumber'

class RatingColumn(Column):
    size = 64 * 5
    display = _('Rating')
    renderer = gtk.CellRendererPixbuf
    id = 'rating'

    def data_func(self, col, cell, model, iter):
        item = model.get_value(iter, 0)
        if not item.get_rating(): return
        try:
            idx = item.get_rating() - 1
            cell.set_property('pixbuf', 
                self.playlist.rating_images[idx])
        except IndexError:
            print "idx_error"
            if idx > 5: idx = 5
            elif idx < 0: idx = 0
            cell.set_property('pixbuf', 
                self.playlist.rating_images[idx])

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
    id = 'bitrate'

    def data_func(self, col, cell, model, iter):
        """
            Shows the bitrate
        """
        item = model.get_value(iter, 0)
        cell.set_property('text', item.get_bitrate())
        self.playlist.set_cell_weight(cell, item)

class IoLocColumn(Column):
    size = 200
    display = _('Location')
    id = 'io_loc'

class FilenameColumn(Column):
    size = 200
    display = _('Filename')
    id = 'filename'

class PlayCountColumn(Column):
    size = 50
    display = _('Playcount')
    id = 'playcount'

    def set_properties(self, col, cellr):
        cellr.set_property('xalign', 1.0)

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
        'length', 'genre', 'rating', 'date']

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
