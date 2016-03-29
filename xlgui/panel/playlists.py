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


from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject


from xl import (
    common,
    event,
    main,
    playlist,
    radio,
    settings,
    trax
)
from xl.nls import gettext as _
from xlgui import (
    guiutil,
    icons,
    panel
)
from xlgui.panel import menus
from xlgui.widgets import (
    dialogs
)

from xlgui.widgets.common import DragTreeView
from xlgui.widgets.filter import *

import logging
logger = logging.getLogger(__name__)

def N_(x): return x

class EntrySecondsField(MultiEntryField):
    def __init__(self):
        MultiEntryField.__init__(self, (50, _('seconds')))

class EntryAndEntryField(MultiEntryField):
    def __init__(self):
        # TRANSLATORS: Logical AND used for smart playlists
        MultiEntryField.__init__(self, (50, _('and'), 50))

class EntryDaysField(MultiEntryField):
    def __init__(self):
        MultiEntryField.__init__(self, (50, _('days')))
        
class PlaylistField(ComboEntryField):
    def __init__(self):
        playlists = []
        playlists.extend(main.exaile().smart_playlists.list_playlists())
        playlists.extend(main.exaile().playlists.list_playlists())
        playlists.sort()
        ComboEntryField.__init__(self, playlists)

DATE_FIELDS = [
    N_('seconds'), N_('minutes'), N_('hours'), N_('days'), N_('weeks')]
class SpinDateField(SpinButtonAndComboField):
    def __init__(self):
        SpinButtonAndComboField.__init__(self, DATE_FIELDS)

class SpinSecondsField(SpinLabelField):
    def __init__(self):
        SpinLabelField.__init__(self, _('seconds'))

class SpinRating(SpinLabelField):
    def __init__(self):
        SpinLabelField.__init__(self, '', 
                settings.get_option("rating/maximum", 5), 0)

class SpinNothing(SpinLabelField):
    def __init__(self):
        SpinLabelField.__init__(self, '')

# This sets up the CRITERIA for all the available types of tags
# that exaile supports. The actual CRITERIA dict is populated 
# using xl.metadata.tags.tag_data.
#
# NOTE: The following strings are already marked for translation in _TRANS and
# _NMAP, and will be really translated by filtergui; no need to clutter the
# code here.
__criteria_types = {
    
    # TODO              
    'bitrate': None,
                    
    'image': None,
          
    'int': [
        ('is', SpinNothing),
        ('less than', SpinNothing),
        ('greater than', SpinNothing),
        ('between', EntryAndEntryField),
        ('at least', SpinNothing),
        ('at most', SpinNothing),
        ('is set', NullField),
        ('is not set', NullField),
    ],
          
    'location': [
        ('is', QuotedEntryField),
        ('is not', QuotedEntryField),
        ('contains', QuotedEntryField),
        ('does not contain', QuotedEntryField),
        ('regex', QuotedEntryField),
        ('not regex', QuotedEntryField),
    ],
    
    'text': [
        ('is', EntryField),
        ('is not', EntryField),
        ('contains', EntryField),
        ('does not contain', EntryField),
        ('regex', EntryField),
        ('not regex', EntryField),
        ('is set', NullField),
        ('is not set', NullField),
    ],
    
    'time': [
        ('at least', SpinSecondsField),
        ('at most', SpinSecondsField),
        ('is', SpinSecondsField),
        ('is not', SpinSecondsField),
    ],
                    
    'timestamp': [
        ('in the last', SpinDateField),
        ('not in the last', SpinDateField),
    ],  
}

# aliases
__criteria_types['datetime'] = __criteria_types['text'] # TODO: fix 
__criteria_types['multiline'] = __criteria_types['text']
__criteria_types['dblnum'] = __criteria_types['int']


# This gets populated below. Only add special tags/searches here.
CRITERIA = [
    ('Rating', [
        ('greater than', SpinRating),
        ('less than', SpinRating),
        ('at least', SpinRating),
        ('at most', SpinRating),
    ]),
   
    ('Playlist', [
        ('Track is in', PlaylistField),
        ('Track not in', PlaylistField),
    ])
]

# NOTE: We use N_ (fake gettext) because these strings are translated later by
# the filter GUI. If we use _ (real gettext) here, filtergui will try to
# translate already-translated strings, which makes no sense. This is partly due
# to the old design of storing untranslated strings (instead of operators) in
# the dynamic playlist database.

_TRANS = {
    # TRANSLATORS: True if haystack is equal to needle
    N_('is'): '==',
    # TRANSLATORS: True if haystack is not equal to needle
    N_('is not'): '!==',
    # TRANSLATORS: True if the specified tag is present (uses the NullField 
    # to compare to __null__)
    N_('is set'): '<!==>',
    # TRANSLATORS: True if the specified tag is not present (uses the NullField
    # to compare to __null__)
    N_('is not set'): '<==>',
    # TRANSLATORS: True if haystack contains needle
    N_('contains'): '=',
    # TRANSLATORS: True if haystack does not contain needle
    N_('does not contain'): '!=',
    # TRANSLATORS: True if haystack matches regular expression
    N_('regex'): '~',
    # TRANSLATORS: True if haystack does not match regular expression
    N_('not regex'): '!~',
    # TRANSLATORS: Example: rating >= 5
    N_('at least'): '>=',
    # TRANSLATORS: Example: rating <= 3
    N_('at most'): '<=',
    # TRANSLATORS: Example: year < 1999
    N_('before'): '<',
    # TRANSLATORS: Example: year > 2002
    N_('after'): '>',
    # TRANSLATORS: Example: 1980 <= year <= 1987
    N_('between'): '><',
    N_('greater than'): '>',
    N_('less than'): '<',
    # TRANSLATORS: Example: track has been added in the last 2 days
    N_('in the last'): '>=',
    # TRANSLATORS: Example: track has not been added in the last 5 hours
    N_('not in the last'): '<',
    # TRANSLATORS: True if a track is contained in the specified playlist
    N_('Track is in'): 'pin',
    # TRANSLATORS: True if a track is not contained in the specified playlist
    N_('Track not in'): '!pin',
}

# This table is a reverse lookup for the actual tag name from a display
# name.
# This gets populated below. Only add special tags/searches here.
_NMAP = {
    N_('Rating'): '__rating', # special
    N_('Playlist'): '__playlist', # not a real tag
}

# update the tables based on the globally stored tag list
def __update_maps():
    
    from xl.metadata.tags import tag_data
    
    for tag, data in tag_data.iteritems():
        
        if data is None:
            continue
        
        # don't catch this KeyError -- if it fails, fix it!
        criteria = __criteria_types[data.type]
        
        if criteria is None:
            continue
            
        CRITERIA.append((data.name, criteria))
        
        _NMAP[data.name] = tag

__update_maps()


class TrackWrapper(object):
    def __init__(self, track, playlist):
        self.track = track
        self.playlist = playlist

    def __unicode__(self):
        text = self.track.get_tag_raw('title')
        if text is not None:
            text = u' / '.join(text)
            
        if text:
            artists = self.track.get_tag_raw('artist')
            if artists:
                text += u' - ' + u' / '.join(artists)
            return text
        return self.track.get_loc_for_io()


class BasePlaylistPanelMixin(GObject.GObject):
    """
        Base playlist tree object.

        Used by the radio and playlists panels to display playlists
    """
    # HACK: Notice that this is not __gsignals__; descendants need to manually
    # merge this in. This is because new PyGObject doesn't like __gsignals__
    # coming from mixin. See:
    # * https://bugs.launchpad.net/bugs/714484
    # * http://www.daa.com.au/pipermail/pygtk/2011-February/019394.html
    _gsignals_ = {
        'playlist-selected': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'tracks-selected': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'append-items': (GObject.SignalFlags.RUN_LAST, None, (object, bool)),
        'replace-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'queue-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
    }
    def __init__(self):
        """
            Initializes the mixin
        """
        GObject.GObject.__init__(self)
        self.playlist_nodes = {} # {playlist: iter} cache for custom playlists
        self.track_image = icons.MANAGER.pixbuf_from_icon_name(
            'audio-x-generic', Gtk.IconSize.SMALL_TOOLBAR)
        # {Playlist: Gtk.Dialog} mapping to keep track of open "are you sure
        # you want to delete" dialogs
        self.deletion_dialogs = {}

    def remove_playlist(self, ignored=None):
        """
            Removes the selected playlist from the UI
            and from the underlying manager
        """
        selected_playlist = self.tree.get_selected_page(raw=True)
        if selected_playlist is None:
            return
        dialog = self.deletion_dialogs.get(selected_playlist)
        if dialog:
            dialog.present()
            return

        def on_response(dialog, response):
            if response == Gtk.ResponseType.YES:
                if isinstance(selected_playlist, playlist.SmartPlaylist):
                    self.smart_manager.remove_playlist(
                        selected_playlist.name)
                else:
                    self.playlist_manager.remove_playlist(
                        selected_playlist.name)
                    # Remove from {playlist: iter} cache.
                    del self.playlist_nodes[selected_playlist]
                # Remove from UI.
                selection = self.tree.get_selection()
                (model, iter) = selection.get_selected()
                self.model.remove(iter)
            del self.deletion_dialogs[selected_playlist]
            dialog.destroy()

        dialog = Gtk.MessageDialog(self.parent,
            Gtk.DialogFlags.DESTROY_WITH_PARENT,
            Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO,
            _('Delete the playlist "%s"?') % selected_playlist.name)
        dialog.connect('response', on_response)
        self.deletion_dialogs[selected_playlist] = dialog
        dialog.present()

    def rename_playlist(self, playlist):
        """
            Renames the playlist
        """
        
        if playlist is None:
            return
        
        # Ask for new name
        dialog = dialogs.TextEntryDialog(
            _("Enter the new name you want for your playlist"),
            _("Rename Playlist"), playlist.name)
        
        result = dialog.run()
        name = dialog.get_value()
        
        dialog.destroy()
        
        if result != Gtk.ResponseType.OK or name == '':
            return
                
        if name in self.playlist_manager.playlists:
            # name is already in use
            dialogs.error(self.parent, _("The "
                "playlist name you entered is already in use."))
            return

        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        model.set_value(iter, 1, name)
        
        # Update the manager aswell
        self.playlist_manager.rename_playlist(playlist, name)

    def open_selected_playlist(self):
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        self.open_item(self.tree, model.get_path(iter), None)

    def on_rating_changed(self, widget, rating):
        """
            Updates the rating of the selected tracks
        """
        tracks = self.get_selected_tracks()

        for track in tracks:
            track.set_rating(rating)

        maximum = settings.get_option('rating/maximum', 5)
        event.log_event('rating_changed', self, rating / maximum * 100)

    def open_item(self, tree, path, col):
        """
            Called when the user double clicks on a playlist,
            also called when the user double clicks on a track beneath
            a playlist.  When they active a track it opens the playlist
            and starts playing that track
        """
        iter = self.model.get_iter(path)
        item = self.model.get_value(iter, 2)
        if item is not None:
            if isinstance(item, (playlist.Playlist,
                playlist.SmartPlaylist)):
                # for smart playlists
                if hasattr(item, 'get_playlist'):
                    try:
                        item = item.get_playlist(self.collection)
                    except Exception as e:
                        logger.exception("Error loading smart playlist")
                        dialogs.error(self.parent, _("Error loading smart playlist: %s") % str(e))
                        return
                else:
                    #Get an up to date copy
                    item = self.playlist_manager.get_playlist(item.name)
                    #item.set_is_custom(True)

#                self.controller.main.add_playlist(item)
                self.emit('playlist-selected', item)
            else:
                self.emit('append-items', [item.track], True)

    def add_new_playlist(self, tracks=[], name = None):
        """
            Adds a new playlist to the list of playlists. If name is 
            None or the name conflicts with an existing playlist, the
            user will be queried for a new name.
            
            Returns the name of the new playlist, or None if it was
            not added.
        """

        do_add_playlist = False
        if name:
            if name in self.playlist_manager.playlists:
                name = dialogs.ask_for_playlist_name(
                    self.get_panel().get_toplevel(), self.playlist_manager, name)
        else:
            if tracks:
                artists = []
                composers = []
                albums = []

                for track in tracks:
                    artist = track.get_tag_display('artist',
                        artist_compilations=False)

                    if artist is not None:
                        artists += [artist]

                    composer = track.get_tag_display('composer',
                        artist_compilations=False)

                    if composer is not None:
                        composers += composer

                    album = track.get_tag_display('album')

                    if album is not None:
                        albums += album

                artists = list(set(artists))[:3]
                composers = list(set(composers))[:3]
                albums = list(set(albums))[:3]

                if len(artists) > 0:
                    name = artists[0]

                    if len(artists) > 2:
                        # TRANSLATORS: Playlist title suggestion with more 
                        # than two values
                        name = _('%(first)s, %(second)s and others') % {
                            'first': artists[0], 'second': artists[1]
                        }
                    elif len(artists) > 1:
                        # TRANSLATORS: Playlist title suggestion with two values
                        name = _('%(first)s and %(second)s') % {
                            'first': artists[0], 'second': artists[1]
                        }
                elif len(composers) > 0:
                    name = composers[0]

                    if len(composers) > 2:
                        # TRANSLATORS: Playlist title suggestion with more 
                        # than two values
                        name = _('%(first)s, %(second)s and others') % {
                            'first': composers[0], 'second': composers[1]
                        }
                    elif len(composers) > 1:
                        # TRANSLATORS: Playlist title suggestion with two values
                        name = _('%(first)s and %(second)s') % {
                            'first': composers[0], 'second': composers[1]
                        }
                elif len(albums) > 0:
                    name = albums[0]

                    if len(albums) > 2:
                        # TRANSLATORS: Playlist title suggestion with more 
                        # than two values
                        name = _('%(first)s, %(second)s and others') % {
                            'first': albums[0], 'second': albums[1]
                        }
                    elif len(albums) > 1:
                        # TRANSLATORS: Playlist title suggestion with two values
                        name = _('%(first)s and %(second)s') % {
                            'first': albums[0], 'second': albums[1]
                        }
                else:
                    name = ''

            name = dialogs.ask_for_playlist_name(
                self.get_panel().get_toplevel(), self.playlist_manager, name)
        
        if name is not None:
            #Create the playlist from all of the tracks
            new_playlist = playlist.Playlist(name)
            new_playlist.extend(tracks)
            # We are adding a completely new playlist with tracks so we save it
            self.playlist_manager.save_playlist(new_playlist)
            
        return name

    def _load_playlist_nodes(self, playlist):
        """
            Loads the playlist tracks into the node for the specified playlist
        """
        if not playlist in self.playlist_nodes: return

        expanded = self.tree.row_expanded(
            self.model.get_path(self.playlist_nodes[playlist]))

        self._clear_node(self.playlist_nodes[playlist])
        parent = self.playlist_nodes[playlist]
        for track in playlist:
            if not track: continue
            wrapper = TrackWrapper(track, playlist)
            row = (self.track_image, unicode(wrapper), wrapper)
            self.model.append(parent, row)

        if expanded:
            self.tree.expand_row(
                self.model.get_path(self.playlist_nodes[playlist]), False)

    def remove_selected_track(self):
        """
            Removes the selected track from its playlist
            and saves the playlist
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        track = model.get_value(iter, 2)
        if isinstance(track, TrackWrapper):
            del track.playlist[track.playlist.index(track.track)]
            #Update the list
            self.model.remove(iter)
            #TODO do we save the playlist after this??
            self.playlist_manager.save_playlist(track.playlist, overwrite=True)

class PlaylistsPanel(panel.Panel, BasePlaylistPanelMixin):
    """
        The playlists panel
    """
    __gsignals__ = BasePlaylistPanelMixin._gsignals_

    ui_info = ('playlists.ui', 'PlaylistsPanelWindow')

    def __init__(self, parent, playlist_manager,
        smart_manager, collection, name):
        """
            Intializes the playlists panel

            @param playlist_manager:  The playlist manager
        """
        panel.Panel.__init__(self, parent, name)
        BasePlaylistPanelMixin.__init__(self)
        self.playlist_manager = playlist_manager
        self.smart_manager = smart_manager
        self.collection = collection
        self.box = self.builder.get_object('playlists_box')
        
        self.playlist_name_info = 500
        self.track_target = Gtk.TargetEntry.new("text/uri-list", 0, 0)
        self.playlist_target = Gtk.TargetEntry.new("playlist_name", Gtk.TargetFlags.SAME_WIDGET, 
            self.playlist_name_info)
        self.deny_targets = [Gtk.TargetEntry.new('',0,0)]

        self.tree = PlaylistDragTreeView(self)
        self.tree.connect('row-activated', self.open_item)
        self.tree.set_headers_visible(False)
        self.tree.connect('drag-motion', self.drag_motion)
        self.tree.drag_source_set(
                Gdk.ModifierType.BUTTON1_MASK, [self.track_target, self.playlist_target],
                Gdk.DragAction.COPY|Gdk.DragAction.MOVE)

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.scroll.add(self.tree)
        self.scroll.set_shadow_type(Gtk.ShadowType.IN)
        self.box.pack_start(self.scroll, True, True, 0)
        self.box.show_all()

        pb = Gtk.CellRendererPixbuf()
        cell = Gtk.CellRendererText()
        if settings.get_option('gui/ellipsize_text_in_panels', False):
            from gi.repository import Pango
            cell.set_property( 'ellipsize-set', True)
            cell.set_property( 'ellipsize', Pango.EllipsizeMode.END)
        col = Gtk.TreeViewColumn('Text')
        col.pack_start(pb, False)
        col.pack_start(cell, True)
        col.set_attributes(pb, pixbuf=0)
        col.set_attributes(cell, text=1)
        self.tree.append_column(col)
        self.model = Gtk.TreeStore(GdkPixbuf.Pixbuf, str, object)
        self.tree.set_model(self.model)

        # icons
        self.folder = self.tree.render_icon(
            Gtk.STOCK_DIRECTORY, Gtk.IconSize.SMALL_TOOLBAR)
        self.playlist_image = icons.MANAGER.pixbuf_from_icon_name(
            'music-library', Gtk.IconSize.SMALL_TOOLBAR)

        # menus
        self.playlist_menu = menus.PlaylistsPanelPlaylistMenu(self)
        self.smart_menu = menus.PlaylistsPanelPlaylistMenu(self)
        self.default_menu = menus.PlaylistPanelMenu(self)
        
        self.track_menu = menus.TrackPanelMenu(self)
        
        self._connect_events()
        self._load_playlists()

    def _connect_events(self):
        event.add_ui_callback(self.refresh_playlists, 'track_tags_changed')
        event.add_ui_callback(self._on_playlist_added, 'playlist_added', self.playlist_manager)

        self.tree.connect('key-release-event', self.on_key_released)

    def _playlist_properties(self):
        pl = self.tree.get_selected_page(raw=True)
        if isinstance(pl, playlist.SmartPlaylist):
            self.edit_selected_smart_playlist()
    
    def refresh_playlists(self, type, track, tag):
        """
            wrapper so that multiple events dont cause multiple
            reloads in quick succession
        """
        if settings.get_option('gui/sync_on_tag_change', True) and \
            tag in ['title', 'artist']:
            self._refresh_playlists()

    @common.glib_wait(500)
    def _refresh_playlists(self):
        """
            Callback for when tags have changed and the playlists
            need refreshing.
        """
        if settings.get_option('gui/sync_on_tag_change', True):
            for playlist in self.playlist_nodes:
                self.update_playlist_node(playlist)
                
    def _on_playlist_added(self, type, object, playlist_name):
    
        new_playlist = self.playlist_manager.get_playlist(playlist_name)
    
        for plx in self.playlist_nodes:
            if plx.name == playlist_name:
                self.update_playlist_node(new_playlist)
                return
                
        self.playlist_nodes[new_playlist] = \
            self.model.append(self.custom, [self.playlist_image, playlist_name,
            new_playlist])
        self.tree.expand_row(self.model.get_path(self.custom), False)
        self._load_playlist_nodes(new_playlist)

    def _load_playlists(self):
        """
            Loads the currently saved playlists
        """
        self.smart = self.model.append(None, [self.folder,
            _("Smart Playlists"), None])

        self.custom = self.model.append(None, [self.folder,
            _("Custom Playlists"), None])

        names = self.smart_manager.playlists[:]
        names.sort()
        for name in names:
            self.model.append(self.smart, [self.playlist_image, name,
                self.smart_manager.get_playlist(name)])

        names = self.playlist_manager.playlists[:]
        names.sort()
        for name in names:
            playlist = self.playlist_manager.get_playlist(name)
            self.playlist_nodes[playlist] = self.model.append(
                self.custom, [self.playlist_image, name, playlist])
            self._load_playlist_nodes(playlist)

        self.tree.expand_row(self.model.get_path(self.smart), False)
        self.tree.expand_row(self.model.get_path(self.custom), False)

    def update_playlist_node(self, pl):
        """
            Updates the playlist node of the playlist
            to reflect any changes in it (i.e. tracks
            being added to the playlist)

            @param pl: the playlist to be updated
        """
        playlists = self.playlist_nodes.keys()
        for playlist in playlists:
            if playlist.name == pl.name:
                node = self.playlist_nodes[playlist]
                # Replace the playlist object in {playlist: iter} cache.
                del self.playlist_nodes[playlist]
                self.playlist_nodes[pl] = node
                # Replace the playlist object in tree model.
                self.model[node][2] = pl
                # Refresh the playlist subnodes.
                self._load_playlist_nodes(pl)

    def import_playlist(self):
        """
            Shows a dialog to ask the user to import a new playlist
        """
        
        def _on_playlists_selected(dialog, playlists):
            for playlist in playlists:
                self.add_new_playlist( playlist, playlist.name )
        
        dialog = dialogs.PlaylistImportDialog()
        dialog.connect('playlists-selected', _on_playlists_selected)
        dialog.show()
                
    def add_smart_playlist(self):
        """
            Adds a new smart playlist
        """
        dialog = FilterDialog(_('Add Smart Playlist'), self.parent,
            CRITERIA)

        dialog.set_transient_for(self.parent)
        
        # run the dialog until there is no error
        while self._run_add_smart_playlist(dialog) == False:
            pass
        
    def _run_add_smart_playlist(self, dialog):
        '''internal helper function'''
        
        result = dialog.run()
        dialog.hide()
        if result == Gtk.ResponseType.ACCEPT:
            name = dialog.get_name()
            matchany = dialog.get_match_any()
            limit = dialog.get_limit()
            state = dialog.get_state()
            random = dialog.get_random()

            if not name:
                dialogs.error(self.parent, _("You did "
                    "not enter a name for your playlist"))
                return False

            try:
                pl = self.smart_manager.get_playlist(name)
                dialogs.error(self.parent, _("The "
                    "playlist name you entered is already in use."))
                return False
            except ValueError:
                pass # playlist didn't exist

            pl = playlist.SmartPlaylist(name, self.collection)
            pl.set_or_match(matchany)
            pl.set_return_limit(limit)
            pl.set_random_sort(random)

            for item in state:
                (field, op) = item[0]
                value = item[1]
                pl.add_param(_NMAP[field], _TRANS[op], value)

            self.smart_manager.save_playlist(pl)
            self.model.append(self.smart, [self.playlist_image, name, pl])
            
        return True

    def edit_selected_smart_playlist(self):
        """
            Shows a dialog for editing the currently selected smart playlist
        """
        pl = self.tree.get_selected_page(raw=True)
        self.edit_smart_playlist(pl)
        
    def edit_smart_playlist(self, pl):
        """
            Shows a dialog for editing a smart playlist
        """
        if not isinstance(pl, playlist.SmartPlaylist): return

        _REV = {}
        for k, v in _TRANS.iteritems():
            _REV[v] = k

        _REV_NMAP = {}
        for k, v in _NMAP.iteritems():
            _REV_NMAP[v] = k

        params = pl.search_params
        state = []

        for param in params:
            (field, op, value) = param
            field = _REV_NMAP[field]

            state.append(([field, _REV[op]], value))

        state.reverse()

        dialog = FilterDialog(_('Edit Smart Playlist'), self.parent,
            CRITERIA)

        dialog.set_transient_for(self.parent)
        dialog.set_name(pl.name)
        dialog.set_match_any(pl.get_or_match())
        dialog.set_limit(pl.get_return_limit())
        dialog.set_random(pl.get_random_sort())

        dialog.set_state(state)
        
        # run the dialog until there is no error
        while self._run_edit_selected_smart_playlist(dialog) == False:
            pass

    def _run_edit_selected_smart_playlist(self, dialog):
        '''internal helper function'''
    
        result = dialog.run()
        dialog.hide()
        pl = self.tree.get_selected_page(raw=True)

        if result == Gtk.ResponseType.ACCEPT:
            name = dialog.get_name()
            matchany = dialog.get_match_any()
            limit = dialog.get_limit()
            state = dialog.get_state()
            random = dialog.get_random()

            if not name:
                dialogs.error(self.parent, _("You did "
                    "not enter a name for your playlist"))
                return False

            if not name == pl.name:
                try:
                    pl = self.smart_manager.get_playlist(name)
                    dialogs.error(self.parent, _("The "
                        "playlist name you entered is already in use."))
                    return False
                except ValueError:
                    pass # playlist didn't exist
            
            pl = playlist.SmartPlaylist(name, self.collection)
            pl.set_or_match(matchany)
            pl.set_return_limit(limit)
            pl.set_random_sort(random)

            for item in state:
                (field, op) = item[0]
                value = item[1]
                pl.add_param(_NMAP[field], _TRANS[op], value)

            self.smart_manager.remove_playlist(pl.name)
            self.smart_manager.save_playlist(pl)

            selection = self.tree.get_selection()
            (model, iter) = selection.get_selected()
            model.set_value(iter, 1, name)
            model.set_value(iter, 2, pl)
            
        return True

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
            Called when someone drags some thing onto the playlist panel
        """
        if info == self.playlist_name_info:
            # We are being dragged a playlist so
            # we have to reorder them
            playlist_name = selection.get_text()
            drag_source = self.tree.get_selected_page()
            # verify names
            if drag_source is not None:
                if drag_source.name == playlist_name:
                    drop_info = tv.get_dest_row_at_pos(x, y)
                    drag_source_iter = self.playlist_nodes[drag_source]
                    if drop_info:
                        path, position = drop_info
                        drop_target_iter = self.model.get_iter(path)
                        drop_target = self.model.get_value(drop_target_iter, 2)
                        if position == Gtk.TreeViewDropPosition.BEFORE:
                            # Put the playlist before drop_target
                            self.model.move_before(drag_source_iter, 
                                drop_target_iter)
                            self.playlist_manager.move(playlist_name, 
                                drop_target.name, after = False)
                        else:
                            # put the playlist after drop_target
                            self.model.move_after(drag_source_iter,
                                drop_target_iter)
                            self.playlist_manager.move(playlist_name,
                                drop_target.name, after = True)
            # Even though we are doing a move we still don't
            # call the delete method because we take care
            # of it above by moving instead of inserting/deleting
            context.finish(True, False, etime)
        else:
            self._drag_data_received_uris(tv, context, x, y, selection, 
                info, etime)

    def _drag_data_received_uris(self, tv, context, x, y, selection, 
        info, etime):
        """
            Called by drag_data_received when the user drags URIs onto us
        """
        locs = list(selection.get_uris())
        drop_info = tv.get_dest_row_at_pos(x, y)
        if drop_info:
            path, position = drop_info
            iter = self.model.get_iter(path)
            drop_target = self.model.get_value(iter, 2)


            # if the current item is a track, use the parent playlist
            insert_index = None
            if isinstance(drop_target, TrackWrapper):
                current_playlist = drop_target.playlist
                drop_target_index = current_playlist.index(drop_target.track)
                # Adjust insert position based on drop position
                if (position == Gtk.TreeViewDropPosition.BEFORE or
                    position == Gtk.TreeViewDropPosition.INTO_OR_BEFORE):
                    # By default adding tracks inserts it before so we do not
                    # have to modify the insert index
                    insert_index =drop_target_index
                else:
                    # If we want to go after we have to append 1
                    insert_index = drop_target_index + 1
            else:
                current_playlist = drop_target;

            # Since the playlist do not have very good support for
            # duplicate tracks we have to perform some trickery
            # to make this work properly in all cases
            try:
                remove_track_index = current_playlist.index(
                    self.tree.get_selected_track())
            except ValueError:
                remove_track_index = None
            if insert_index is not None and remove_track_index is not None:
                # Since remove_track_index will be removed before
                # the new track is inserted we have to offset the
                # insert index
                 if insert_index > remove_track_index:
                     insert_index = insert_index - 1

            # Delete the track before adding the other one
            # so we do not get duplicates
            # right now the playlist does not support
            # duplicate tracks very well
            if context.action == Gdk.DragAction.MOVE:
                #On a move action the second True makes the
                # drag_data_delete function called
                context.finish(True, True, etime)
            else:
                context.finish(True, False, etime)

            # Add the tracks we found to the internal playlist
            # TODO: have it pass in existing tracks?
            (tracks, playlists) = self.tree.get_drag_data(locs)
            
            if insert_index is not None:
                current_playlist[insert_index:insert_index] = tracks
            else:
                current_playlist.extend( tracks )

            self._load_playlist_nodes(current_playlist)

            # Do we save in the case when a user drags a file onto a playlist 
            # in the playlist panel? note that the playlist does not have to 
            # be open for this to happen
            self.playlist_manager.save_playlist(current_playlist, 
                overwrite=True)
        else:
            # If the user dragged files prompt for a new playlist name
            # else if they dragged a playlist add the playlist

            # We don't want the tracks in the playlists to be added to the
            # master tracks list so we pass in False
            (tracks, playlists) = self.tree.get_drag_data(locs, False)
            # First see if they dragged any playlist files
            for new_playlist in playlists:
                self.playlist_nodes[new_playlist] = self.model.append(
                    self.custom, [self.playlist_image, new_playlist.name,
                    new_playlist])
                self._load_playlist_nodes(new_playlist)

                # We are adding a completely new playlist with tracks so 
                # we save it
                self.playlist_manager.save_playlist(new_playlist, 
                    overwrite=True)

            # After processing playlist proceed to ask the user for the
            # name of the new playlist to add and add the tracks to it
            if len(tracks) > 0:
                self.add_new_playlist(tracks)

    def drag_data_delete(self,  tv, context):
        """
            Called after a drag data operation is complete
            and we want to delete the source data
        """
        if context.drag_drop_succeeded():
            self.remove_selected_track()

    def drag_get_data(self, tv, context, selection_data, info, time):
        """
            Called when someone drags something from the playlist
        """
        #TODO based on info determine what we set in selection_data
        if info == self.playlist_name_info:
            pl = self.tree.get_selected_page()
            if pl is not None:
                selection_data.set(Gdk.SELECTION_TYPE_STRING, 8, pl.name)
        else:
            pl = self.tree.get_selected_page()
            if pl is not None:
                tracks = pl[:]
            else:
                tracks = self.tree.get_selected_tracks()

            if not tracks: return

            for track in tracks:
                DragTreeView.dragged_data[track.get_loc_for_io()] = \
                    track

            uris = trax.util.get_uris_from_tracks(tracks)
            selection_data.set_uris(uris)

    def drag_motion(self, tv, context, x, y, time):
        """
            Sets the appropriate drag action based on what we are hovering over

            hovering over playlists causes the copy action to occur
            hovering over tracks within the same playlist causes the move
                action to occur
            hovering over tracks within different playlist causes the move 
                action to occur

            Called on the destination widget
        """
        # Reset any target to be default to moving tracks
        self.tree.enable_model_drag_dest([self.track_target],
            Gdk.DragAction.DEFAULT)
        # Determine where the drag is coming from
        dragging_playlist = False
        if tv == self.tree:
            selected_playlist = self.tree.get_selected_page()
            if selected_playlist is not None:
                dragging_playlist = True

        # Find out where they are dropping onto
        drop_info = tv.get_dest_row_at_pos(x, y)
        if drop_info:
            path, position = drop_info
            iter = self.model.get_iter(path)
            drop_target = self.model.get_value(iter, 2)

            if isinstance(drop_target, playlist.Playlist):
                if dragging_playlist:
                    # If we drag onto  we copy, if we drag between we move
                    if position == Gtk.TreeViewDropPosition.INTO_OR_BEFORE or \
                        position == Gtk.TreeViewDropPosition.INTO_OR_AFTER:
                        Gdk.drag_status(context, Gdk.DragAction.COPY, time)
                    else:
                        Gdk.drag_status(context, Gdk.DragAction.MOVE, time)
                        # Change target as well
                        self.tree.enable_model_drag_dest([self.playlist_target],
                                                         Gdk.DragAction.DEFAULT)
                else:
                    Gdk.drag_status(context, Gdk.DragAction.COPY, time)
            elif isinstance(drop_target, TrackWrapper):
                # We are dragging onto another track
                # make it a move operation if we are only dragging
                # tracks within our widget
                # We do a copy if we are draggin from another playlist
                if Gtk.drag_get_source_widget(context) == tv and \
                    dragging_playlist == False:
                    Gdk.drag_status(context, Gdk.DragAction.MOVE, time)
                else:
                    Gdk.drag_status(context, Gdk.DragAction.COPY, time)
            else:
                # Prevent drop operation by changing the targets
                self.tree.enable_model_drag_dest(self.deny_targets,
                                                 Gdk.DragAction.DEFAULT)
                return False
            return True
        else: # No drop info
            if dragging_playlist:
                context.drag_status(Gdk.DragAction.MOVE, time)
                # Change target as well
                self.tree.enable_model_drag_dest([self.playlist_target],
                                                     Gdk.DragAction.DEFAULT)

    # 
    #  TODO: remove these two functions, only kept for possible backwards
    #        compatibility
    # 

    def export_playlist(self, playlist):
        """
            Exports the selected playlist to path
        """
        dialogs.export_playlist_dialog(playlist)
            
    def export_playlist_files(self, playlist):
        '''
            Exports the playlist files to a URI
        '''
        dialogs.export_playlist_files(playlist)

    def on_key_released(self, widget, event):
        """
            Called when a key is released in the tree
        """
        if event.keyval == Gdk.KEY_Menu:
            (mods,paths) = self.tree.get_selection().get_selected_rows()
            if paths and paths[0]:
                iter = self.model.get_iter(paths[0])
                pl = self.model.get_value(iter, 2)
                #Based on what is selected determines what
                #menu we will show
                if isinstance(pl, playlist.Playlist):
                    Gtk.Menu.popup(self.playlist_menu, None, 
                        None, None, None, 0, event.time)
                elif isinstance(pl, playlist.SmartPlaylist):
                    Gtk.Menu.popup(self.smart_menu, None, 
                        None, None, None, 0, event.time)
                elif isinstance(pl, TrackWrapper):
                    Gtk.Menu.popup(self.track_menu, None, 
                        None, None, None, 0, event.time)
                else:
                    Gtk.Menu.popup(self.default_menu, None, 
                        None, None, None, 0, event.time)
            return True

        if event.keyval == Gdk.KEY_Left:
            (mods,paths) = self.tree.get_selection().get_selected_rows()
            if paths and paths[0]:
                self.tree.collapse_row(paths[0])
            return True

        if event.keyval == Gdk.KEY_Right:
            (mods,paths) = self.tree.get_selection().get_selected_rows()
            if paths and paths[0]:
                self.tree.expand_row(paths[0], False)
            return True

        if event.keyval == Gdk.KEY_Delete:
            (mods,paths) = self.tree.get_selection().get_selected_rows()
            if paths and paths[0]:
                iter = self.model.get_iter(paths[0])
                pl = self.model.get_value(iter, 2)
                #Based on what is selected determines what
                #menu we will show
                if isinstance(pl, playlist.Playlist) or \
                    isinstance(pl, playlist.SmartPlaylist):
                    self.remove_playlist(pl)
                elif isinstance(pl, TrackWrapper):
                    self.remove_selected_track()
            return True
        return False

    def button_release(self, button, event):
        """
            Called when a button is pressed, is responsible
            for showing the context menu
        """
        if event.button == 3:
            button_info = self.tree.get_dest_row_at_pos(
                int(event.x), int(event.y))
            if not button_info:
                return
            iter = self.model.get_iter(button_info[0])
            pl = self.model.get_value(iter, 2)
            #Based on what is selected determines what
            #menu we will show
            if isinstance(pl, playlist.Playlist):
                self.playlist_menu.popup(event)
            elif isinstance(pl, playlist.SmartPlaylist):
                self.smart_menu.popup(event)
            elif isinstance(pl, TrackWrapper):
                self.track_menu.popup(event)
            else:
                self.default_menu.popup(event)

    def _clear_node(self, node):
        """
            Clears a node of all children
        """
        iter = self.model.iter_children(node)
        while True:
            if not iter: break
            self.model.remove(iter)
            iter = self.model.iter_children(node)

class PlaylistDragTreeView(DragTreeView):
    """
        Custom DragTreeView to retrieve data from playlists
    """
    def __init__(self, container, receive=True, source=True):
        DragTreeView.__init__(self, container, receive, source)
        self.show_cover_drag_icon = False

    def get_selection_empty(self):
        '''Returns True if there are no selected items'''
        return self.get_selection().count_selected_rows() == 0

    def get_selected_tracks(self):
        """
            Used by the menu, just basically gets the selected
            playlist and returns the tracks in it
        """
        playlist = self.get_selected_page()

        if playlist is not None:
            return [track for track in playlist]
        else:
            return [self.get_selected_track()]

        return None

    def get_selected_page(self, raw=False):
        """
            Retrieves the currently selected playlist in
            the playlists panel.  If a non-playlist is
            selected it returns None

            @return: the playlist
        """
        item = self.get_selected_item(raw=raw)

        if isinstance(item, (playlist.Playlist,
            playlist.SmartPlaylist)):
            return item
        else:
            return None

    def get_selected_track(self):
        item = self.get_selected_item()

        if not item: return None

        if isinstance(item, TrackWrapper):
            return item.track
        else:
            return None

    def get_selected_item(self, raw=False):
        (model, iter) = self.get_selection().get_selected()

        if not iter: return None

        item = model.get_value(iter, 2)

        # for smart playlists
        if isinstance(item, playlist.SmartPlaylist):
            if raw: return item
            try:
                return item.get_playlist(self.container.collection)
            except:
                return None
        if isinstance(item, radio.RadioItem):
            if raw: return item
            return item.get_playlist()
        elif isinstance(item, playlist.Playlist):
            return item
        elif isinstance(item, TrackWrapper):
            return item
        else:
            return None

