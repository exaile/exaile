# -*- coding: utf-8 -*-
"""
Copyright (c) 2019 Fernando Póvoa (sbrubes)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import os.path
import re
import unicodedata

from collections import defaultdict
from datetime import datetime

from gi.repository import Gtk
from gi.repository import GdkPixbuf

import xl.event

from xl.nls import gettext as _
from xlgui.icons import MANAGER as ICONS_MANAGER

#: Icons cache
_ICONS = defaultdict(dict)

#: None value to additional_filter
ADDITIONAL_FILTER_NONE_VALUE = ('', [])

#: Milliseconds to a second
MS2SECOND = 1000

#: Milliseconds to a minute
MS2MINUTE = 60 * MS2SECOND

#: Milliseconds to a hour
MS2HOUR = 60 * MS2MINUTE

#: Milliseconds values array (Hour, Minute, Seconds)
MS2 = (MS2HOUR, MS2MINUTE, MS2SECOND)


def create_with(fnc_enter, fnc_exit):
    """
        Declares a WithClass object
        :param fnc_enter: function on enter
        :param fnc_exit: function on exit
        :return: WithClass
    """
    return WithClass(fnc_enter, fnc_exit)


def create_stacked_images_pixbuf(images, cover_width, offset_factor, overall_alpha):
    """
        Creates a stacked images effect
        Put a transparent frame on it (look for `border`)
        :param images: list of GdkPixbuf.Pixbuf
        :param cover_width: int
        :param offset_factor: float
        :param overall_alpha: int
        :return: GdkPixbuf.Pixbuf or None (if len(:param pixbuf_list:) == 0)
    """
    if len(images) == 0:
        return None

    # Sizes
    cover_side = cover_width
    cover_portion = int(cover_side * offset_factor)
    covers_square_side = (cover_side + cover_portion * (len(images) - 1))
    border = 4
    total_width = total_height = covers_square_side + (2 * border)

    # The result pixbuf
    result_pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8,
                                         total_width, total_height)
    result_pixbuf.fill(0x00000000)  # Fill with transparent background

    covers_area = result_pixbuf.new_subpixbuf(
        src_x=border, src_y=border,
        width=covers_square_side,
        height=covers_square_side
    )

    # Write covers
    for i, pixbuf in enumerate(images):
        dest = cover_portion * i  # Put in a diagonal
        pixbuf.composite(
            covers_area, 0, 0, covers_square_side, covers_square_side,
            dest, dest, 1, 1, GdkPixbuf.InterpType.HYPER, overall_alpha
        )

    return result_pixbuf


def get_default_view_pattern():
    """
        Default view pattern it's used in case it doesn't have other
        :return: str
    """

    def format_data(item, tooltip):
        """
            Helper to format tuples as str
            :param item: tuple
            :param tooltip: bool
            :return: str
        """
        title = tooltip
        res = ''
        if len(item) == 4 and tooltip:
            res += item[1] + '\\: '
            title = False

        res += '(?%s:' % item[0]

        if title:
            res += item[1] + '\\: '

        if len(item) > 2:
            if item[2]:
                res += item[2]
            else:
                res += '[' + item[0] + ']'

            if len(item) > 3:
                if tooltip:
                    res += '<br>'

                res += ')(!%s:' % item[0]
                res += '<i>%s</i>' % item[3]
        else:
            res += '[' + item[0] + ']'

        if tooltip:
            res += '<br>'

        res += ')'
        return res

    labels = {
        'album': '(:%s)' % _('Album'),
        'albumartist': '(:%s)' % _('Artist'),
        'genre': '(:%s)' % _('Genre'),
        'date': '(:%s)' % _('Date'),
    }

    unknown_text = _('Unknown')
    untitled_album = _('Untitled album')
    untitled_artist = _('Untitled artist')
    untitled_track = _('Untitled track')
    yes_text = '<i>%s</i>' % _('Yes')
    no_text = _('No')
    none_genre = '\\[%s\\]' % _('none')

    tags_list = (
        ('acoustid_fingerprint', _('AcoustID Fingerprint')),
        ('acoustid_id', _('AcoustID')),
        ('added', _('Added')),
        ('album', _('Album'), '[album](?albumdisambig: <i>\\([albumdisambig]\\)</i>)', untitled_album),
        ('album_id', _('Album Id')),
        ('albumartist', _('Album Artist'), '', untitled_artist),
        ('albumartist_credit', _('Album Artist Credit')),
        ('albumartists', _('Artists')),
        ('albums', _('Albums')),
        ('albumstatus', _('Release Status')),
        ('albumtype', _('Release Type')),
        ('arranger', _('Arranger')),
        ('artist_credit', _('Artist Credit'), '', untitled_artist),
        ('artist_sort', _('Artist Sort Order')),
        ('asin', _('ASIN')),
        ('bitdepth', _('Audio Bit Depth')),
        ('bitrate', _('Bitrate'), '[bitrate:,] bps'),
        ('bpm', _('BPM'), '[bpm:.0f]'),
        ('catalognum', _('Catalog Number')),
        ('channels', _('Channels')),
        ('comments', _('Comments')),
        ('comp', _('iTunes Compilation'), yes_text, no_text),
        ('composer', _('Composer')),
        ('country', _('Country')),
        ('disc', _('Disc'), '[disc](?disctotal:/[disctotal])'),
        ('disctitle', _('Disc Subtitle')),
        ('disctotal', _('Total Discs')),
        ('encoder', _('Encoded By')),
        ('format', _('File Format')),
        ('genre', _('Genre'), '', none_genre),
        ('grouping', _('Grouping')),
        ('initial_key', _('Initial Key')),
        ('label', _('Record Label')),
        ('language', _('Language')),
        ('length', _('Length')),
        ('lyricist', _('Lyricist')),
        ('lyrics', _('Lyrics'), yes_text, no_text),
        ('mb_albumartistid', _('MusicBrainz Release Artist Id'), '', unknown_text),
        ('mb_albumid', _('MusicBrainz Release Id'), '', unknown_text),
        ('mb_artistid', _('MusicBrainz Artist Id'), '', unknown_text),
        ('mb_releasegroupid', _('MusicBrainz Release Group Id'), '', unknown_text),
        ('media', _('Media')),
        ('mtime', _('Modification')),
        ('original_year', _('Original Release Date'),
         '[original_year:04d](?original_month:-[original_month:02d](?original_day:-[original_day:02d]))'),
        ('path', _('Path')),
        ('samplerate', _('Sampling Rate'), '[samplerate:,] Hz'),
        ('script', _('Script')),
        ('title', _('Track Title'), '', untitled_track),
        ('track', _('Track Number'), '[track](?tracktotal:/[tracktotal])'),
        ('tracks', _('Tracks')),
        ('tracktotal', _('Total Tracks'), '', unknown_text),
        ('year', _('Release Date'), '[year:04d](?month:-[month:02d](?day:-[day:02d]))'),
    )

    tags_for_tooltip = {i[0]: format_data(i, True) for i in tags_list}
    tags_for_tooltip['br'] = '<br>'

    tooltips = {
        'album': (
            'album', 'disctotal', 'tracktotal', 'albumartist_credit', 'br', 'original_year',
            'year', 'albumtype', 'albumstatus', 'script', 'language', 'label', 'catalognum',
            'country', 'media', 'br', 'grouping', 'comp', 'asin'
        ),
        'albumartist': ('albumartist', 'br', 'albums', 'tracks'),
        'genre': ('genre', 'br', 'albumartists', 'albums', 'tracks'),
        'original_year': ('original_year', 'br', 'albumartists', 'albums', 'tracks'),
        'title': (
            'title', 'track', 'br', 'album', 'disc', 'disctitle', 'br', 'artist_credit', 'composer',
            'lyricist', 'arranger', 'length', 'bitrate', 'samplerate', 'channels', 'format', 'bitdepth',
            'encoder', 'br', 'bpm', 'acoustid_id', 'acoustid_fingerprint', 'initial_key', 'genre',
            'lyrics', 'comments', 'br', 'added', 'mtime', 'path'
        )
    }

    tags_for_path = {i[0]: format_data(i, False) for i in tags_list}

    def get(field, label=False):
        """
            Helper to yield data
            :param field: str
            :param label: bool (default: False)
            :return: yield data
        """
        if label:
            yield labels[field]

        if field == 'title':
            yield '(disc)(track)'

        yield tags_for_path[field]
        yield '&'
        for i in tooltips[field]:
            yield tags_for_tooltip[i]

    def list_(*args):
        """
            Helper to transform items as list
            :param args: *args
            :return: list
        """
        def get_():
            """
                Helper to yield items
                :return: yield str
            """
            for i in args:
                for j in i:
                    yield j

        return list(get_())

    group_mark = ['%']
    end_pattern = ['']

    date = [labels['date'], '[original_year:04d]']
    return list_(
        # Artist
        get('albumartist', True), group_mark, get('album'), group_mark, get('title'), end_pattern,
        # Album
        get('album', True), group_mark, get('title'), end_pattern,
        # Genre - Artist
        get('genre', True), group_mark, get('albumartist', True), group_mark, get('title'), end_pattern,
        # Genre - Album
        get('genre', True), group_mark, get('album', True), group_mark, get('title'), end_pattern,
        # Date - Artist
        date, group_mark, get('albumartist', True), group_mark, get('album'), group_mark,
        get('title'), end_pattern,
        # Date - Album
        date, group_mark, get('album', True), group_mark, get('title'), end_pattern,
        # Artist - (Date - Album)
        get('albumartist', True), group_mark, date, [' - '], get('album', True), group_mark,
        get('title'), end_pattern,
    )


def get_database_path_from_beets_config():
    """
        Get database path from beets config
        :return: str or None - database file path
    """
    exp = re.compile(r'^library: *(.+) *$')
    try:
        with open(os.path.join(os.path.expanduser("~"), '.config/beets/config.yaml')) as f:
            for line in f:
                match_object = exp.match(line)
                if match_object:
                    return match_object.group(1)
    except IOError:
        pass

    return None


def get_error_icon(size):
    """
        Get error icon
        :param size: int
        :return: `GdkPixbuf.Pixbuf`
    """
    return get_icon('dialog-error', size)


def get_icon(name, size):
    """
        Get icon
        :param name: str - icon name
        :param size: int
        :return: GdkPixbuf.Pixbuf
    """
    if isinstance(size, Gtk.IconSize):
        size = Gtk.icon_size_lookup(size)[1]

    if size not in _ICONS[name]:
        _ICONS[name][size] = ICONS_MANAGER.pixbuf_from_icon_name(name, size)

    return _ICONS[name][size]


def normalize(o):
    """
        Normalize an object and return it as unicode
        :param o: object
        :return: normalized lower unicode
        :see: https://docs.python.org/2.7/library/unicodedata.html#unicodedata.normalize
    """
    s = '%05d' % o if isinstance(o, int) else o
    return unicodedata.normalize('NFKD', unicode(s)).encode('ascii', 'ignore').lower()


def represent_length_as_str(secs):
    """
        Represent length as str
        :param secs: float
        :return: str (as hhh:mm:ss)
    """
    ms = int(secs * MS2SECOND)

    vals = []
    for v in MS2:
        dv, ms = divmod(ms, v)
        vals.append('%02i' % dv)

    return ':'.join(vals)  # + ('.%03i' % ms)


def represent_timestamp_as_str(timestamp):
    """
        Represent timestamp as str
        :param timestamp: float
        :return: str
    """
    return datetime.fromtimestamp(timestamp).strftime("%x %X") if timestamp else ''


class Event:
    """
        Represents an event (see `xl.event`) as a Class
    """
    class _InternalClass:
        pass

    def __init__(self, name):
        """
            Constructor
            :param name: str - suffix to event \
            (it uses CONFIG.get_id() as a prefix)
        """
        self.name = name
        self.__global_object = Event._InternalClass()

    def connect(self, callback, obj=None):
        """
            Connect to event (add_ui_callback)
            :param callback: function
            :param obj: object to
            :return: None
        """
        if obj is None:
            obj = self.__global_object

        xl.event.add_ui_callback(callback, self.name, obj)

    def log(self, obj=None, data=None):
        """
            Log event
            :param obj: object to (None uses global)
            :param data: data
            :return: None
        """
        if obj is None:
            obj = self.__global_object

        xl.event.log_event(self.name, obj, data)


class FileFilter(Gtk.FileFilter):
    """
        A wrapper to Gtk.FileFilter
    """
    def __init__(self, name, patterns):
        """
            Constructor
            :param name: str
            :param patterns: list [str] (see `Gtk.FileFilter.add_pattern`)
        """
        Gtk.FileFilter.__init__(self)
        self.set_name(name)
        for i in patterns:
            self.add_pattern(i)


class PluginInfo:
        """
            A class to handle PLUGININFO files as dict
        """
        def __init__(self, base_dir):
            """
                Constructor
                :param base_dir: str - the plugins base dir
            """
            self.id = os.path.basename(base_dir)
            self.__dict_file = dict_file = {}
            with open(
                os.path.join(base_dir, 'PLUGININFO')
            ) as f:
                for line in f:
                    try:
                        key, val = line.split("=", 1)
                        # restricted eval - no bult-in funcs.
                        # marginally more secure.
                        dict_file[key] = eval(
                            val,
                            {'__builtins__': None, '_': _},
                            {}
                        )
                    except ValueError:
                        pass  # this happens on blank lines

        @property
        def name(self):
            """
                Accessor to 'Name' property
                :return: str
            """
            return self['Name']

        def __getitem__(self, item):
            """
                Gets info of PLUGININFO file

                Usage:
                    >>> PLUGIN_INFO["Authors"]
                    ['Fernando Póvoa <sbrubes@zoho.com>']

                :param item: str
                :return: as defined on PLUGININFO file (str, list...)
            """
            return self.__dict_file[item]


class SQLStatements:
    """
        Helper to build sql statements
    """
    def __init__(self, statement='', *args):
        """
            Constructor
            :param statement: str - statement
            :param args: arguments to be formatted ("statement % args")
        """
        self.__statements = []
        self.append(statement, *args)

    def append(self, statement, *args):
        """
            Append statement
            :param statement:
            :param args: arguments to be formatted ("statement % args")
            :return:
        """
        if statement:
            self.__statements.append(statement % args)

    @property
    def result(self):
        """
            Result
            :return: str - (statements joined by ' ')
        """
        return ' '.join(self.__statements)


class WithClass:
    """
        Generic enter/exit class
        :see: https://docs.python.org/2.5/whatsnew/pep-343.html
    """
    def __init__(self, fnc_enter, fnc_exit):
        """
            Constructor
            :param event: Event
        """
        self.fnc_enter = fnc_enter
        self.fnc_exit = fnc_exit

    def __enter__(self):
        """
            Enter
            :return: None
        """
        self.fnc_enter()

    def __exit__(self, _type, _value, _traceback):
        """
            Exit
            :param _type:
            :param _value:
            :param _traceback:
            :return: None
        """
        self.fnc_exit()
