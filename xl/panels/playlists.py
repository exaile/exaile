# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

import os, random, re, urllib
from gettext import gettext as _
import gtk
from xl import common, xlmisc, filtergui, library
from xl.filtergui import MultiEntryField, EntryField
import xl.path

N_ = lambda x: x

def day_calc(x, inc, field, symbol='>='):
    import time
    values = {
        'seconds': 1,
        'minutes': 60,
        'hours': 60 * 60,
        'days': 60 * 60 * 24,
        'weeks': 60 * 60 * 24 * 7
    }

    seconds = int(x) * values[inc]
    t = time.time() - seconds
    t = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t))
    return "%s %s '%s'" % (field, symbol, t)

class EntrySecondsField(MultiEntryField):
    def __init__(self, result_generator):
        MultiEntryField.__init__(self, result_generator, n=1,
            labels=(None, _('seconds')),
            widths=(50,))

class EntryAndEntryField(MultiEntryField):
    def __init__(self, result_generator):
        MultiEntryField.__init__(self, result_generator, n=2,
            # TRANSLATORS: Logical AND used for smart playlists
            labels=(None, _('and'), None),
            widths=(50, 50))

class EntryDaysField(MultiEntryField):
    def __init__(self, result_generator):
        MultiEntryField.__init__(self, result_generator, n=1,
            labels=(None, _('days')),
            widths=(50,))

DATE_FIELDS = (_('seconds'), _('minutes'), _('hours'), _('days'), _('weeks'))
class SpinDateField(filtergui.SpinButtonAndComboField):
    def __init__(self, result_generator):
        filtergui.SpinButtonAndComboField.__init__(self, 
            result_generator, DATE_FIELDS)

class SpinSecondsField(filtergui.SpinLabelField):
    def __init__(self, result_generator):
        filtergui.SpinLabelField.__init__(self, result_generator, 
            _('seconds'))

class SpinRating(filtergui.SpinLabelField):
    def __init__(self, result_generator):
        filtergui.SpinLabelField.__init__(self, result_generator, '',
            8)

class SpinNothing(filtergui.SpinLabelField):
    def __init__(self, result_generator):
        filtergui.SpinLabelField.__init__(self, result_generator, '')

CRITERIA = [
    (N_('Artist'), [
        # TRANSLATORS: True if haystack is equal to needle
        (N_('is'), (EntryField, lambda x:
            'artists.name = "%s"' % x)),
        # TRANSLATORS: True if haystack is not equal to needle
        (N_('is not'), (EntryField, lambda x:
            'artists.name != "%s"' % x)),
        # TRANSLATORS: True if haystack contains needle
        (N_('contains'), (EntryField, lambda x:
            'artists.name LIKE "%%%s%%"' % x)),
        # TRANSLATORS: True if haystack does not contain needle
        (N_('does not contain'), (EntryField, lambda x:
            'artists.name NOT LIKE "%%%s%%"' % x)),
        ]),
    (N_('Album'), [
        (N_('is'), (EntryField, lambda x:
            'albums.name = "%s"' % x)),
        (N_('is not'), (EntryField, lambda x:
            'albums.name != "%s"' % x)),
        (N_('contains'), (EntryField, lambda x:
            'albums.name LIKE "%%%s%%"' % x)),
        (N_('does not contain'), (EntryField, lambda x:
            'albums.name NOT LIKE "%%%s%%"' % x)),
        ]),
    (N_('Genre'), [
        (N_('is'), (EntryField, lambda x:
            'genre = "%s"' % x)),
        (N_('is not'), (EntryField, lambda x:
            'genre != "%s"' % x)),
        (N_('contains'), (EntryField, lambda x:
            'genre LIKE "%%%s%%"' % x)),
        (N_('does not contain'), (EntryField, lambda x:
            'genre NOT LIKE "%%%s%%"' %x)),
        ]),
    (N_('User Rating'), [
        # TRANSLATORS: Example: rating >= 5
        (N_('at least'), (SpinRating, lambda x:
            'user_rating >= %s' % x)),
        # TRANSLATORS: Example: rating <= 3
        (N_('at most'), (SpinRating, lambda x:
            'user_rating <= %s' % x))]),
    (N_('System Rating'), [
        (N_('at least'), (SpinRating, lambda x:
            'rating >= %s' % x)),
        (N_('at most'), (SpinRating, lambda x:
            'rating <= %s' % x))
        ]),
    (N_('Number of Plays'), [
        (N_('at least'), (SpinNothing, lambda x:
            'plays >= %s' % x)),
        (N_('at most'), (SpinNothing, lambda x:
            'plays <= %s' %x))
        ]),
    (N_('Year'), [
        # TRANSLATORS: Example: year < 1999
        (N_('before'), (EntryField, lambda x:
            'year < %s' % x)),
        # TRANSLATORS: Example: year > 2002
        (N_('after'), (EntryField, lambda x:
            'year > %s' % x)),
        # TRANSLATORS: Example: 1980 <= year <= 1987
        (N_('between'), (EntryAndEntryField, lambda x, y:
            'year BETWEEN %s AND %s' % (x, y))),
        ]),
    (N_('Length'), [
        (N_('at least'), (SpinSecondsField, lambda x:
            'length >= %s' % x)),
        (N_('at most'), (SpinSecondsField, lambda x:
            'length <= %s' % x)),
        ]),
    (N_('Date Added'), [
        # TRANSLATORS: Example: track has been added in the last 2 days
        (N_('in the last'), (SpinDateField, 
            lambda x, i: day_calc(x, i, 'time_added'))),
        # TRANSLATORS: Example: track has not been added in the last 5 hours
        (N_('not in the last'), (SpinDateField, 
            lambda x, i: day_calc(x, i, 'time_added', '<'))),
        ]),
    (N_('Last Played'), [
        (N_('in the last'), (SpinDateField, 
            lambda x, i: day_calc(x, i, 'last_played'))),
        (N_('not in the last'), (SpinDateField, 
            lambda x, i: day_calc(x, i, 'last_played', '<'))),
        ]),
    (N_('Location'), [
        (N_('is'), (EntryField, lambda x:
            'paths.name = "%s"' % x)),
        (N_('is not'), (EntryField, lambda x:
            'paths.name != "%s"' % x)),
        (N_('contains'), (EntryField, lambda x:
            'paths.name LIKE "%%%s%%"' % x)),
        (N_('does not contain'), (EntryField, lambda x:
            'paths.name NOT LIKE "%%%s%%"' % x)),
        ])
    ]


class SmartPlaylist(object):
    def __init__(self, name, id):
        self.name = name
        self.id = id

    def __str__(self):
        return self.name

class BuiltinPlaylist(object):
    def __init__(self, name, sql):
        self.name = name
        self.sql = sql

    def __str__(self):
        return self.name

class CustomPlaylist(object):
    def __init__(self, name, id):
        self.name = name
        self.id = id

    def __str__(self):
        return self.name

class PlaylistsPanel(object):
    """ 
        The playlists panel 
    """
    def __init__(self, exaile):
        """
            Creates the playlist panel
        """
        self.exaile = exaile
        self.db = self.exaile.db
        self.xml = exaile.xml
        container = self.xml.get_widget('playlists_box')

        self.targets = [('text/uri-list', 0, 0)]
        self.tree = xlmisc.DragTreeView(self, True, False)
        self.tree.connect('row-activated', self.open_playlist)
        self.tree.set_headers_visible(False)

        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.tree)
        self.scroll.set_shadow_type(gtk.SHADOW_IN)
        container.pack_start(self.scroll, True, True)
        container.show_all()

        pb = gtk.CellRendererPixbuf()
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn('Text')
        col.pack_start(pb, False)
        col.pack_start(cell, True)
        col.set_attributes(pb, pixbuf=0)
        col.set_attributes(cell, text=1)
        self.tree.append_column(col)

    def load_playlists(self):
        """
            Loads the playlists
        """
        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, str, object)
        self.tree.set_model(self.model)
        self.open_folder = xlmisc.get_icon('gnome-fs-directory-accept')
        self.playlist_image = gtk.gdk.pixbuf_new_from_file(xl.path.get_data(
            'images', 'playlist.png'))
        self.smart_image = self.exaile.window.render_icon('gtk-execute',
            gtk.ICON_SIZE_MENU)
        self.smart = self.model.append(None, [self.open_folder, _("Smart"
            " Playlists"), None])

        smart_playlists = [
            (_('Entire Library'), "SELECT paths.name FROM artists, albums, tracks, paths WHERE " \
                "paths.id=tracks.path AND artists.id=tracks.artist AND " \
                "albums.id=tracks.albums ORDER BY LOWER(artists.name), " \
                "THE_CUTTER(albums.name)"),

            (_('Top 100'), "SELECT paths.name FROM tracks,paths WHERE " \
                "paths.id=tracks.path ORDER BY rating " \
                "DESC LIMIT 100"),

            (_('Highest Rated'), "SELECT paths.name FROM tracks,paths WHERE " \
                "tracks.path=paths.id " \
                "ORDER BY user_rating DESC " \
                "LIMIT 100"),

            (_('Most Played'), "SELECT paths.name FROM paths, tracks WHERE " \
                "tracks.path=paths.id ORDER " \
                "BY plays DESC LIMIT 100"),

            (_('Least Played'), "SELECT paths.name FROM paths, tracks WHERE " \
                "paths.id=tracks.path ORDER " \
                "BY plays ASC LIMIT 100"),

            (_('Rating > 5'), "SELECT paths.name FROM paths, tracks, artists, " \
                "albums " \
                "WHERE tracks.path=paths.id AND albums.id=tracks.album AND " \
                "artists.id=tracks.artist " \
                "AND user_rating > 5 " \
                "ORDER BY LOWER(artists.name), THE_CUTTER(albums.name), track"),
            
            (_('Rating > 3'), "SELECT paths.name FROM paths,tracks,artists,albums WHERE " \
                "tracks.path=paths.id AND albums.id=tracks.album AND " \
                "artists.id=tracks.artist AND user_rating > 3 " \
                "ORDER BY LOWER(artists.name), LOWER(albums.name), track"),

            (_('Newest 100'), "SELECT paths.name FROM paths,tracks WHERE " \
                "tracks.path=paths.id AND time_added!='' " \
                "ORDER BY time_added DESC " \
                "LIMIT 100"),

            (_('Random 100'), "SELECT paths.name FROM tracks,paths WHERE " \
                "paths.id=tracks.path"),
            (_('Random 500'), "SELECT paths.name FROM tracks,paths WHERE " \
                "paths.id=tracks.path"),
        ]

        # Add smart playlists
        def add_smart(parent, i):
            name, sql = smart_playlists[i]
            self.model.append(parent, [self.playlist_image, name,
                BuiltinPlaylist(name, sql)])

        add_smart(self.smart, 0)
        builtin = self.model.append(self.smart, [self.open_folder,
            _('Built In'), None])
        for i in xrange(1, len(smart_playlists)):
            add_smart(builtin, i)

        self.custom = self.model.append(None, [self.open_folder,
            _("Custom Playlists"), None])

        rows = self.db.select("SELECT name, id, type FROM playlists ORDER BY"
            " name")
        for row in rows:
            if not row[2]:
                self.model.append(self.custom, [self.playlist_image, row[0],
                    CustomPlaylist(row[0], row[1])])
            elif row[2] == 1:
                self.model.append(self.smart, [self.smart_image, row[0],
                    SmartPlaylist(row[0], row[1])])

        self.tree.expand_all()
        self.setup_menu()

    def setup_menu(self):
        """ 
            Sets up the popup menu for the playlist tree
        """
        self.menu = xlmisc.Menu()
        self.menu.append(_('Add Playlist'), self.on_add_playlist, 'gtk-add')
        self.menu.append(_('Add Smart Playlist'), self.on_add_smart_playlist, 
            'gtk-add')
        self.menu.append_separator()
        self.edit_item = self.menu.append(_('Edit'), self.edit_playlist,
            'gtk-edit')
        self.menu.append_separator()
        self.remove_item = self.menu.append(_('Delete Playlist'), 
            self.remove_playlist, 'gtk-remove')

    def edit_playlist(self, item, event):
        """
            Edits a playlist
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()

        obj = model.get_value(iter, 2)
        if not isinstance(obj, SmartPlaylist): return
        row = self.db.read_one('playlists', 'matchany, item_limit', 
            'id=?', (obj.id,))

        dialog = filtergui.FilterDialog(_('Edit Playlist'), CRITERIA)
        dialog.set_transient_for(self.exaile.window)

        dialog.set_name(obj.name)
        dialog.set_match_any(row[0])
        dialog.set_limit(row[1])

        state = []
        rows = self.db.select('SELECT crit1, crit2, filter FROM '
            'smart_playlist_items WHERE playlist=? ORDER BY line',
            (obj.id,))

        for row in rows:
            left = [row[0], row[1]]
            filter = eval(row[2])
            if len(filter) == 1:
                filter = filter[0]
            state.append((left, filter))

        print repr(state)

        dialog.set_state(state)

        result = dialog.run()
        dialog.hide()
        if result == gtk.RESPONSE_ACCEPT:
            name = dialog.get_name()
            if name != obj.name:
                row = self.db.read_one('playlists', 'matchany', 
                    'name=?', (name,))
                if row:
                    common.error(self.exaile.window, _("That playlist name "
                        "is already taken."))
                    return
            matchany = dialog.get_match_any()
            limit = dialog.get_limit()
            self.db.execute('UPDATE playlists SET name=?, matchany=?, item_limit=?WHERE '
                'id=?', (name, matchany, limit, obj.id))
            self.db.execute('DELETE FROM smart_playlist_items WHERE '
                'playlist=?', (obj.id,))

            count = 0
            for c, v in dialog.get_state():
                if type(v) != list:
                    v = list((v,))
                self.db.execute("INSERT INTO smart_playlist_items( "
                    "playlist, line, crit1, crit2, filter ) VALUES( "
                    " ?, ?, ?, ?, ? )", (obj.id, count, c[0], c[1],
                    repr(v)))
                count += 1

            self.db.commit()
            self.model.set_value(iter, 1, name)
            self.model.set_value(iter, 2, SmartPlaylist(name, obj.id))

        dialog.destroy()

    def on_add_smart_playlist(self, widget, event):
        """
            Adds a smart playlist
        """
        dialog = filtergui.FilterDialog(_('Add Smart Playlist'), CRITERIA)

        dialog.set_transient_for(self.exaile.window)
        result = dialog.run()
        if result == gtk.RESPONSE_ACCEPT:
            name = dialog.get_name()
            matchany = dialog.get_match_any()
            limit = dialog.get_limit()
            if not name: 
                common.error(self.exaile.window, _("You did not enter a "
                    "name for your playlist"))
                return
            row = self.db.read_one('playlists', 'name', 'name=?', (name,))
            if row:
                common.error(self.exaile.window, _("That playlist name "
                    "is already taken."))
                return
            dialog.hide()

            self.db.execute("INSERT INTO playlists( name, type, matchany, "
                " item_limit ) VALUES( ?, 1, ?, ? )", (name, matchany, limit))
            row = self.db.read_one('playlists', 'id', 'name=?', (name,))
            playlist_id = row[0]

            count = 0
            for c, v in dialog.get_state():
                if type(v) != list:
                    v = list((v,))
                self.db.execute("INSERT INTO smart_playlist_items( "
                    "playlist, line, crit1, crit2, filter ) VALUES( "
                    " ?, ?, ?, ?, ? )", (playlist_id, count, c[0], c[1],
                    repr(v)))
                count += 1

            self.db.commit()

            self.model.append(self.smart, [self.smart_image, name, 
                SmartPlaylist(name, playlist_id)])

        dialog.hide()
        dialog.destroy()

    def button_press(self, widget, event):
        """
            Called when the user clicks on the tree
        """
        selection = self.tree.get_selection()
        x, y = event.get_coords()
        x = int(x); y = int(y)
        delete_enabled = False
        edit_enabled = False
        if self.tree.get_path_at_pos(x, y):
            (path, col, x, y) = self.tree.get_path_at_pos(x, y)
            iter = self.model.get_iter(path)
            obj = self.model.get_value(iter, 2)
            self.edit_item.set_sensitive(edit_enabled)
            if isinstance(obj, CustomPlaylist) or \
                isinstance(obj, SmartPlaylist):
                delete_enabled = True
            if isinstance(obj, SmartPlaylist):
                edit_enabled = True

        self.remove_item.set_sensitive(delete_enabled)
        self.edit_item.set_sensitive(edit_enabled)

        if event.button == 3:
            self.menu.popup(None, None, None, event.button, event.time)

    def open_playlist(self, tree, path, col):
        """
            Called when the user double clicks on a tree item
        """
        iter = self.model.get_iter(path)
        obj = self.model.get_value(iter, 2)
        if isinstance(obj, BuiltinPlaylist):
            name = obj.name
            sql = obj.sql

            if name == 'Entire Library':    
                songs = self.exaile.all_songs
            elif name.startswith('Random'):
                songs = library.TrackData()
                for song in self.exaile.all_songs:
                    songs.append(song)

                random.shuffle(songs)
                    
                try:
                    number = int(name.replace('Random ', ''))
                except ValueError:
                    number = 100
                songs = library.TrackData(songs[:number])
            else:
                songs = library.search_tracks(self.exaile.window, 
                    self.db,
                    self.exaile.all_songs, None, None, sql)

            self.exaile.new_page(name, songs)

        elif isinstance(obj, SmartPlaylist):
            self.open_smart_playlist(obj.name, obj.id)

        elif isinstance(obj, CustomPlaylist):
            playlist = obj.name
            playlist_id = library.get_column_id(self.db, 'playlists', 'name', playlist)

            rows = self.db.select('SELECT paths.name FROM playlist_items,paths '
                'WHERE playlist_items.path=paths.id AND playlist=?',
                (playlist_id,))

            songs = library.TrackData()
            for row in rows:
                tr = library.read_track(self.db, self.exaile.all_songs, row[0])
                if tr:
                    songs.append(tr)

            self.playlist_songs = songs
            self.exaile.new_page(playlist, self.playlist_songs)
            self.exaile.on_search()
            self.exaile.tracks.playlist = playlist

    def open_smart_playlist(self, name, id):
        """
            Opens a smart playlist
        """
        row = self.db.read_one('playlists', 'matchany, item_limit', 'id=?', (id,))
        limit = row[1]
        rows = self.db.select("SELECT crit1, crit2, filter FROM "
            "smart_playlist_items WHERE playlist=? ORDER BY line", (id,))

        where = []
        andor = " AND "
        if row[0]: andor = ' OR '

        state = []

        for row in rows:
            left = [row[0], row[1]]
            filter = eval(row[2])
            if len(filter) == 1:
                filter = filter[0]
            state.append((left, filter))

        filter = filtergui.FilterWidget(CRITERIA)
        filter.set_state(state)
        where = filter.get_result()

        sql = """
            SELECT paths.name 
                FROM tracks,paths,artists,albums 
            WHERE 
                (
                    paths.id=tracks.path AND 
                    artists.id=tracks.artist AND 
                    albums.id=tracks.album
                ) 
                AND (%s) 
                ORDER BY 
                    LOWER(artists.name),
                    THE_CUTTER(albums.name), 
                    track, title
            """ % andor.join(where)
        xlmisc.log(sql)
        songs = library.search_tracks(self.exaile.window,
            self.db, self.exaile.all_songs, None, None, sql)

        # if a limit was set, shuffle the songs and only grab that amount
        if limit:
            random.shuffle(songs)
            songs = library.TrackData(songs[:limit])

        self.exaile.new_page(name, songs)

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
            Called when someone drags tracks to the smart playlists panel
        """
        path = self.tree.get_path_at_pos(x, y)
        error = ""
        if path: 
            iter = self.model.get_iter(path[0])
            obj = self.model.get_value(iter, 2)
        else:
            obj = None

        uris = selection.get_uris()
        songs = library.TrackData()
        for l in uris:
            l = urllib.unquote(l)
            m = re.search(r'^device_(\w+)://', l)
            if m:
                continue
            else:
                song = self.exaile.all_songs.for_path(l)
                if song: songs.append(song)

        if not isinstance(obj, CustomPlaylist): 
            self.on_add_playlist(self.remove_item, items=songs)
            return

        xlmisc.log("Adding tracks to playlist %s" % obj.name)
        if error:
            common.scrolledMessageDialog(self.exaile.window,
                error, _("The following errors did occur"))

        self.add_items_to_playlist(obj.name, songs)

    def remove_playlist(self, item, event):
        """
            Asks if the user really wants to delete the selected playlist, and
            then does so if they choose 'Yes'
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()

        obj = model.get_value(iter, 2)
        if not isinstance(obj, CustomPlaylist) and \
            not isinstance(obj, SmartPlaylist): return

        dialog = gtk.MessageDialog(self.exaile.window, 
            gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, 
            _("Are you sure you want to permanently delete the selected"
            " playlist?"))
        if dialog.run() == gtk.RESPONSE_YES:
            playlist = obj.name 
            p_id = library.get_column_id(self.db, 'playlists', 'name', playlist)
            self.db.execute("DELETE FROM playlists WHERE id=?", (p_id,))

            table = 'playlist_items'
            if isinstance(obj, SmartPlaylist):
                table = 'smart_playlist_items'
            self.db.execute("DELETE FROM %s WHERE playlist=?" % table,
                (p_id,))
            if library.PLAYLISTS.has_key(playlist):
                del library.PLAYLISTS[playlist]
            self.db.commit()
            
            self.model.remove(iter)
        dialog.destroy()

    def on_add_playlist(self, widget, event=None, items=None):
        """
            Adds a playlist to the database
        """
        dialog = common.TextEntryDialog(self.exaile.window, 
            _("Enter the name you want for your new playlist"),
            _("New Playlist"))
        result = dialog.run()
        if result == gtk.RESPONSE_OK:
            name = dialog.get_value()
            if name == "": return None
            c = self.db.record_count("playlists", "name=?", (name,))

            if c > 0:
                common.error(self.exaile.window, _("Playlist already exists."))
                return name

            playlist_id = library.get_column_id(self.db, 'playlists', 'name',
                name)
                
            self.model.append(self.custom, [self.playlist_image, name,
                CustomPlaylist(name, playlist_id)])
            self.tree.expand_all()

            if type(widget) == gtk.MenuItem:
                self.add_items_to_playlist(name, items)
            return name
        else: return None

    def add_items_to_playlist(self, playlist, songs=None):
        """
            Adds the selected tracks tot he playlist
        """
        if type(playlist) == gtk.MenuItem:
            playlist = playlist.get_child().get_label()

        if songs == None: songs = self.exaile.tracks.get_selected_tracks()
        playlist_id = library.get_column_id(self.db, 'playlists', 'name', playlist)

        for track in songs:
            if track.type == 'stream': continue
            path_id = library.get_column_id(self.db, 'paths', 'name', track.loc)
            self.db.execute("INSERT INTO playlist_items( playlist, path ) " \
                "VALUES( ?, ? )", (playlist_id, path_id))
        self.db.commit()

