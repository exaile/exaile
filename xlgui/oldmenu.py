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


"""
Old menu system.

This code is fully deprecated and should NOT be added to. Users of
oldmenu need to be rewritten to use widgets.menu instead.
"""

import gobject
import gtk

from xlgui import guiutil, icons
from xlgui.widgets import dialogs, rating
from xl import (
    common,
    event,
    playlist,
    settings,
    xdg
)
from xl.nls import gettext as _
from xl.trax.util import get_rating_from_tracks

class GenericTrackMenu(guiutil.Menu):
    """
        A menu that can be subclassed to use on any widget that displays
        tracks and defines the "get_selected_tracks" method
    """
    __gsignals__ = {
        'queue-items': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            ()
        ),
    }
    def __init__(self):
        guiutil.Menu.__init__(self)

        self._add_queue_pixbuf()
        self._create_menu()

    def _create_menu(self):
        """
            Creates the menu
        """
        self.queue_item = self.append(_('Toggle Queue'),
            lambda *e: self.on_queue(), 'exaile-queue-icon')

    def on_queue(self):
        """
            Called when the user clicks the "toggle queue" item
        """
        self.emit('queue-items')

    def _add_queue_pixbuf(self):
        """
            Creates the icon for "toggle queue"
        """
        pixbuf = icons.MANAGER.pixbuf_from_text(u'\u2610', (16, 16))
        icons.MANAGER.add_stock_from_pixbuf('exaile-queue-icon', pixbuf)

    def popup(self, event):
        """
            Displays the menu
        """
        guiutil.Menu.popup(self, None, None, None, event.button, event.time)

class TrackSelectMenu(GenericTrackMenu):
    """
        Menu for any panel that operates on selecting tracks, IE, Files panel
        and the Collection panel
    """
    __gsignals__ = {
        'append-items': (gobject.SIGNAL_RUN_LAST, None, ()),
        'replace-items': (gobject.SIGNAL_RUN_LAST, None, ()),
        'properties': (gobject.SIGNAL_RUN_LAST, None, ()),
    }
    def __init__(self):
        """
            Initializes the menu
        """
        GenericTrackMenu.__init__(self)

    def _create_menu(self):
        """
            Actually adds the menu items
        """
        self.append_item = self.append(_('Append to Current'),
            lambda *e: self.emit('append-items'), gtk.STOCK_ADD)
        self.replace_item = self.append(_('Replace Current'),
            lambda *e: self.emit('replace-items'))
        self.queue_item = self.append(_('Queue Items'),
            lambda *e: self.emit('queue-items'), 'exaile-queue-icon')
        self.append_separator()
        self.append(_('Properties'), lambda *e: self.emit('properties'),
            gtk.STOCK_PROPERTIES)

class RatedTrackSelectMenu(TrackSelectMenu):
    """
        Menu for any panel that operates on selecting tracks
        including an option to rate tracks
    """
    __gsignals__ = {
        'rating-changed': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            (gobject.TYPE_INT,)
        )
    }
    def __init__(self):
        self.rating_item = rating.RatingMenuItem()
        self._rating_changed_id = self.rating_item.connect('rating-changed',
            self.on_rating_changed)
        self._updating = False

        TrackSelectMenu.__init__(self)

    def _create_menu(self):
        """
            Actually adds the menu items
        """
        gtk.Menu.append(self, self.rating_item)
        self.rating_item.show_all()

        TrackSelectMenu._create_menu(self)

    def on_rating_changed(self, widget, rating):
        """
            Passes the 'rating-changed' signal
        """
        self.emit('rating-changed', rating)

        self.rating_item.disconnect(self._rating_changed_id)
        self.rating_item.props.rating = 0
        self._rating_changed_id = self.rating_item.connect('rating-changed',
            self.on_rating_changed)


class PlaylistsPanelMenu(guiutil.Menu):
    """
        Menu for xlgui.panel.playlists.PlaylistsPanel, for when the
        user does not click on a playlist/track.  The default menu
    """
    __gsignals__ = {
        'add-playlist': (gobject.SIGNAL_RUN_LAST, None, ()),
        'add-smart-playlist': (gobject.SIGNAL_RUN_LAST, None, ()),
    }
    def __init__(self, radio=False):
        """
            @param widget: playlists panel widget
        """
        guiutil.Menu.__init__(self)
        self.radio = radio
        self._create_playlist_menu()

    def _create_playlist_menu(self):
        if self.radio:
            self.append(_('New Station'), lambda *e: self.on_add_playlist(),
                        gtk.STOCK_NEW)
        else:
            self.append(_('New Playlist'), lambda *e: self.on_add_playlist(),
                        gtk.STOCK_NEW)
            self.append(_('New Smart Playlist'), lambda *e: self.on_add_smart_playlist(),
                        gtk.STOCK_NEW)

    def on_add_playlist(self, selected = None):
        self.emit('add-playlist')

    def on_add_smart_playlist(self, selected = None):
        self.emit('add-smart-playlist')

    def popup(self, event):
        """
            Displays the menu
        """
        guiutil.Menu.popup(self, None, None, None, event.button, event.time)

class PlaylistsPanelPlaylistMenu(RatedTrackSelectMenu, PlaylistsPanelMenu):
    """
        Menu for xlgui.panel.playlists.PlaylistsPanel, for
        when the user right clicks on an actual playlist
        entry
    """
    __gsignals__ = {
        # also inherits from TrackSelectMenu
        'add-playlist': (gobject.SIGNAL_RUN_LAST, None, ()),
        'add-smart-playlist': (gobject.SIGNAL_RUN_LAST, None, ()),
        'open-playlist': (gobject.SIGNAL_RUN_LAST, None, ()),
        'export-playlist': (gobject.SIGNAL_RUN_LAST, None, (str,)),
        'export-playlist-files': (gobject.SIGNAL_RUN_LAST, None, (str,)),
        'rename-playlist': (gobject.SIGNAL_RUN_LAST, None, (str,)),
        'remove-playlist': (gobject.SIGNAL_RUN_LAST, None, ()),
        'edit-playlist': (gobject.SIGNAL_RUN_LAST, None, ()),
    }

    def __init__(self, radio=False, smart=False):
        """
            @param widget: playlists panel widget
        """
        #Adds the menu options to add playlist
        PlaylistsPanelMenu.__init__(self, radio)
        self.append_separator()
        #Adds track menu options (like append, queue)
        RatedTrackSelectMenu.__init__(self)
        self.smart = smart

        self.append_separator()
        self.append(callback=lambda *e: self.on_open_playlist(),
                    stock_id=gtk.STOCK_OPEN)

        name = _('Rename')
        if self.smart:
            name = _('Edit')
        self.append(name, lambda *e: self.on_rename_playlist(),
                    gtk.STOCK_EDIT)
        self.append(_('Export Playlist'), lambda *e: self.on_export_playlist(),
                    gtk.STOCK_SAVE)
        self.append(_('Export Files'), lambda *e: self.on_export_playlist_files(),
                    gtk.STOCK_SAVE)
        self.append_separator()
        self.append(_('Delete Playlist'), lambda *e: self.on_delete_playlist(),
                    gtk.STOCK_DELETE)

    def on_export_playlist(self, selected = None):
        """
            Asks the user where to save the file, then passes
            that information onto the widget to perform the save
            operation, export type is determined by the extension
            entered
        """
        dialog = dialogs.FileOperationDialog(_("Export as..."),
            None, gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_SAVE, gtk.RESPONSE_OK))

        extensions = { 'm3u' : _('M3U Playlist'),
                                'pls' : _('PLS Playlist'),
                                'asx' : _('ASX Playlist'),
                                'xspf' : _('XSPF Playlist') }

        dialog.add_extensions(extensions)

        result = dialog.run()
        if result == gtk.RESPONSE_OK:
            #TODO recover last directory from preferences
            #self.exaile.last_open_dir = dialog.get_current_folder()
            path = unicode(dialog.get_filename(), 'utf-8')
            self.emit('export-playlist', path)
        dialog.destroy()
        
    def on_export_playlist_files(self, selected=None):
        '''
            Asks the user where to export the files, then copies
            the files to that directory
        '''
        dialog = dialogs.DirectoryOpenDialog(title=_('Choose directory to export files to'))
        dialog.set_select_multiple(False)
        dialog.connect( 'uris-selected', lambda widget, uris: self.emit('export-playlist-files', uris[0] ))
        dialog.run()
        dialog.destroy()
        

    def on_delete_playlist(self, selected = None):
        dialog = gtk.MessageDialog(None,
            gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,
            _("Are you sure you want to permanently delete the selected"
            " playlist?"))
        if dialog.run() == gtk.RESPONSE_YES:
            self.emit('remove-playlist')
        dialog.destroy()

    def on_rename_playlist(self, selected = None):
        if self.smart:
            self.emit('edit-playlist')
            return

        # Ask for new name
        dialog = dialogs.TextEntryDialog(
            _("Enter the new name you want for your playlist"),
            _("Rename Playlist"))
        result = dialog.run()
        if result == gtk.RESPONSE_OK:
            name = dialog.get_value()
            if not name == "":
                self.emit('rename-playlist', name)

    def on_open_playlist(self, selected = None):
        self.emit('open-playlist')

    def popup(self, event):
        """
            Displays the menu
        """
        guiutil.Menu.popup(self, None, None, None, event.button, event.time)

class RadioPanelPlaylistMenu(PlaylistsPanelPlaylistMenu):
    """
        Menu for xlgui.panel.playlists.RadioPanel, for
        when the user right clicks on an actual playlist
        entry
    """
    def __init__(self):
        PlaylistsPanelPlaylistMenu.__init__(self, radio=True)

class PlaylistsPanelTrackMenu(guiutil.Menu):
    """
        Menu for xlgui.panel.playlists.PlaylistsPanel, for when the
        user right clicks on a track under a custom playlist
    """
    __gsignals__ = {
        'remove-track': (gobject.SIGNAL_RUN_LAST, None, ()),
    }
    def __init__(self):
        """
            @param widget: playlists panel widget
        """
        guiutil.Menu.__init__(self)

        self.append(_('Remove'), lambda *e: self.on_remove_track(),
                    gtk.STOCK_REMOVE)

    def on_remove_track(self, selected = None):
        self.emit('remove-track')

    def popup(self, event):
        """
            Displays the menu
        """
        guiutil.Menu.popup(self, None, None, None, event.button, event.time)
