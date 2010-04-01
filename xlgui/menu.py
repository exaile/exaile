# Copyright (C) 2008-2009 Adam Olsen
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

import gobject
import gtk

from xlgui import commondialogs, guiutil, icons, rating
from xl import event, playlist, xdg, settings
from xl.nls import gettext as _

#settings = settings.SettingsManager.settings

class GenericTrackMenu(guiutil.Menu):
    """
        A menu that can be subclassed to use on any widget that displays
        tracks and defines the "get_selected_tracks" method
    """
    __gsignals__ = {
        'rating-set': (gobject.SIGNAL_RUN_LAST, None, (int,)),
        'queue-items': (gobject.SIGNAL_RUN_LAST, None, ()),
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
        pixbuf = icons.MANAGER.pixbuf_from_text(u'\u2610', 16, 16)
        icons.MANAGER.add_stock_from_pixbuf('exaile-queue-icon', pixbuf)

    def popup(self, event):
        """
            Displays the menu
        """
        guiutil.Menu.popup(self, None, None, None, event.button, event.time)

class AddToPlaylistMenu(guiutil.Menu):
    """
        Menu item that expands to allow the user to add
        the selected tracks to an existing playlist (or the
        option to create a new playlist)
    """
    def __init__(self, widget, playlist_manager):
        """
            @param widget: widget that exposes
            get_selected_tracks() and returns a list of
            valid tracks
        """
        guiutil.Menu.__init__(self)
        self.widget = widget
        self.playlist_manager = playlist_manager
        self._create_add_playlist_menu()

    def _create_add_playlist_menu(self):
        self.append(_('New Playlist'), lambda *e: self.on_add_new_playlist(),
            'gtk-new')
        # As for the list of playlists, we have to redo it every time
        # the user right clicks
        self.add_dynamic_builder(self._create_playlist_menu_items)

    def _create_playlist_menu_items(self):
        playlists = self.playlist_manager.playlists
        if playlists: self.append_separator()
        for name in playlists:
            self.append(_(name), self.on_add_to_playlist, data = name)


    def on_add_new_playlist(self, selected = None):
        # TODO: use signals to do this stuff, instead of calling
        # xlgui.get_controller()
        import xlgui
        xlgui.get_controller().panels['playlists'].add_new_playlist(
            self.widget.get_selected_tracks())

    def on_add_to_playlist(self, selected = None, pl_name = None):
        """
            Adds the selected tracks the playlist, saves the playlist
            and finally updates the playlist panel with the new tracks
        """
        # TODO: use signals to do this stuff, instead of calling
        # xlgui.get_controller()
        import xlgui
        pl = self.playlist_manager.get_playlist(pl_name)
        tracks = self.widget.get_selected_tracks()
        pl.add_tracks(tracks)
        self.playlist_manager.save_playlist(pl, overwrite = True)
        xlgui.get_controller().panels['playlists'].update_playlist_node(pl)

    def popup(self, event):
        """
            Displays the menu
        """
        guiutil.Menu.popup(self, None, None, None, event.button, event.time)

class PlaylistMenu(GenericTrackMenu):
    """
        Menu for xlgui.playlist.Playlist
    """
    __gsignals__ = {
        'remove-items': (gobject.SIGNAL_RUN_LAST, None, ()),
        'properties': (gobject.SIGNAL_RUN_LAST, None, ()),
    }
    def __init__(self, playlist, playlists):
        GenericTrackMenu.__init__(self)
        self.playlist = playlist

        self.rating_item = guiutil.MenuRatingWidget(
            self.playlist.get_selected_tracks, self.playlist.get_tracks_rating)

        self.append_item(self.rating_item)

        self.add_playlist_menu = AddToPlaylistMenu(playlist, playlists)
        self.append_menu(_('Add to Custom Playlist'),
            self.add_playlist_menu, gtk.STOCK_ADD)
        self.append_separator()
        self.append(_('Remove'), lambda *e: self.remove_selected_tracks(),
            gtk.STOCK_REMOVE)
        self.append_separator()
        self.append(_('Properties'), lambda *e: self.emit('properties'),
            gtk.STOCK_PROPERTIES)

        self.playlist_tab_menu = None
        # Defer menu setup until exaile is loaded
        event.add_callback(self.on_exaile_loaded, 'gui_loaded')

    def on_exaile_loaded(self, event, exaile, nothing):
        """
            Finalizes the menu setup
        """
        tab = self.playlist.main.get_current_tab()
        if tab:
            self.playlist_tab_menu = PlaylistTabMenu(tab)
            self.playlist_tab_menu = self.append_menu(_('Playlist'),
                self.playlist_tab_menu)

    def remove_selected_tracks(self):
        """
            Removes the selected tracks from the playlist
            Note: does not update/save the playlist, user
            has to save the playlist themselves
        """
        self.emit('remove-items')

    def popup(self, event):
        """
            Displays the menu
        """
        from xlgui import main
        if self.playlist_tab_menu:
          pagecount = main.get_playlist_notebook().get_n_pages()
          if settings.get_option('gui/show_tabbar', True) or pagecount > 1:
              self.playlist_tab_menu.hide_all()
          else:
              if pagecount == 1:
                  self.playlist_tab_menu.show_all()
        self.rating_item.on_rating_change()
        GenericTrackMenu.popup(self, event)

class PlaylistTabMenu(guiutil.Menu):
    """
        Menu for playlist tabs
    """
    def __init__(self, tab, custom = False):
        """
            Initializes the menu
        """
        guiutil.Menu.__init__(self)
        self.append(_("_New Playlist"), tab.do_new_playlist, gtk.STOCK_NEW)
        self.append_separator()
        self.append(_("_Rename Playlist"), tab.do_rename, gtk.STOCK_EDIT)
        if not custom:
            self.append(_("_Save as Custom Playlist"), tab.do_save_custom, gtk.STOCK_SAVE)
        else:
            self.append(_("_Save Changes to Playlist"), tab.do_save_changes_to_custom, gtk.STOCK_SAVE)
            self.append(_("_Save as..."), tab.do_save_custom)
        self.append(_("C_lear All Tracks"), tab.do_clear, gtk.STOCK_CLEAR)
        self.append_separator()
        self.append(_("_Close Playlist"), tab.do_close, gtk.STOCK_CLOSE)

class TrackSelectMenu(GenericTrackMenu):
    """
        Menu for any panel that operates on selecting tracks, IE, Files panel
        and the Collection panel
    """
    __gsignals__ = {
        'append-items': (gobject.SIGNAL_RUN_LAST, None, ()),
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
        self.append_item = self.append(_('Append to Current'), lambda *e:
            self.on_append_items(), 'gtk-add')
        self.queue_item = self.append(_('Queue Items'), lambda *e: self.on_queue(),
            'exaile-queue-icon')
        self.append_separator()
        self.append(_('Properties'), lambda *e: self.emit('properties'),
            'gtk-properties')

    def on_append_items(self, selected=None):
        """
            Appends the selected tracks to the current playlist
        """
        self.emit('append-items')

    def on_queue(self, selected=None):
        """
            Called when the user clicks the "toggle queue" item
        """
        self.emit('queue-items')

class RatedTrackSelectMenu(TrackSelectMenu):
    """
        Menu for any panel that operates on selecting tracks
        including an option to rate tracks
    """
    def __init__(self, tree_selection, get_selected_tracks, get_tracks_rating):

        self.tree_selection = tree_selection
        self.rating_item = guiutil.MenuRatingWidget(
            get_selected_tracks, get_tracks_rating)

        TrackSelectMenu.__init__(self)

    def _create_menu(self):
        """
            Actually adds the menu items
        """
        TrackSelectMenu._create_menu(self)
        gtk.Menu.append(self, self.rating_item)
        self.rating_item.show_all()
        self.changed_id = -1


    def popup(self, event):
        """
            Displays the menu
        """
        self.rating_item.on_rating_change()
        self.changed_id = self.tree_selection.connect('changed', self.rating_item.on_rating_change)
        TrackSelectMenu.popup(self, event)

    def popdown(self, event):
        """
            Displays the menu
        """
        self.tree_selection.disconnect(self.changed_id)
        TrackSelectMenu.popdown(self, event)

class CollectionPanelMenu(RatedTrackSelectMenu):
    __gsignals__ = {
        'delete-items': (gobject.SIGNAL_RUN_LAST, None, ()),
    }
    def __init__(self, *args):
        RatedTrackSelectMenu.__init__(self, *args)

    def _create_menu(self):
        RatedTrackSelectMenu._create_menu(self)
        self.delete_item = self.append(_('Delete Track from Storage'),
                lambda *e: self.on_delete_track(), 'gtk-delete')

    def on_delete_track(self):
        self.emit('delete-items')



# these are stubbs for now
FilesPanelMenu = TrackSelectMenu


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
                        'gtk-new')
        else:
            self.append(_('New Playlist'), lambda *e: self.on_add_playlist(),
                        'gtk-new')
            self.append(_('New Smart Playlist'), lambda *e: self.on_add_smart_playlist(),
                        'gtk-new')

    def on_add_playlist(self, selected = None):
        self.emit('add-playlist')

    def on_add_smart_playlist(self, selected = None):
        self.emit('add-smart-playlist')

    def popup(self, event):
        """
            Displays the menu
        """
        guiutil.Menu.popup(self, None, None, None, event.button, event.time)

class PlaylistsPanelPlaylistMenu(TrackSelectMenu, PlaylistsPanelMenu):
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
        TrackSelectMenu.__init__(self)
        self.smart = smart

        self.append_separator()
        self.append(callback=lambda *e: self.on_open_playlist(),
                    stock_id=gtk.STOCK_OPEN)

        name = _('Rename')
        if self.smart:
            name = _('Edit')
        self.append(name, lambda *e: self.on_rename_playlist(),
                    gtk.STOCK_EDIT)
        self.append(_('Export'), lambda *e: self.on_export_playlist(),
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
        dialog = commondialogs.FileOperationDialog(_("Export as..."),
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
            #TODO recover last directory from prefs
            #self.exaile.last_open_dir = dialog.get_current_folder()
            path = unicode(dialog.get_filename(), 'utf-8')
            self.emit('export-playlist', path)
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
        dialog = commondialogs.TextEntryDialog(
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
                    'gtk-remove')

    def on_remove_track(self, selected = None):
        self.emit('remove-track')

    def popup(self, event):
        """
            Displays the menu
        """
        guiutil.Menu.popup(self, None, None, None, event.button, event.time)
