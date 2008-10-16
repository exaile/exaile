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

import gtk
from xlgui import guiutil, commondialogs
from xl import playlist

class GenericTrackMenu(guiutil.Menu):
    """
        A menu that can be subclassed to use on any widget that displays
        tracks and defines the "get_selected_tracks" method
    """
    def __init__(self, widget, queue):
        guiutil.Menu.__init__(self)
        self.widget = widget
        self.queue = queue

        self._add_queue_pixbuf()
        self._create_menu()

    def _create_menu(self):
        """
            Creates the menu
        """
        self.queue_item = self.append(_('Toggle Queue'), lambda *e: self.on_queue(),
            'exaile-queue-icon')

    def on_queue(self, selected=None):
        """
            Called when the user clicks the "toggle queue" item
        """
        if not selected:
            selected = self.widget.get_selected_tracks()
        current = self.queue.get_tracks()

        for track in selected:
            if track in current:
                current.remove(track)
            else:
                current.append(track)

        self.queue.clear()
        self.queue.add_tracks(current)
        if hasattr(self.widget, 'queue_draw'):
            self.widget.queue_draw()

    def _add_queue_pixbuf(self):
        """
            Creates the icon for "toggle queue"
        """
        window = gtk.Window()

        pixbuf = guiutil.get_text_icon(window, u'\u2610', 16, 16)
        icon_set = gtk.IconSet(pixbuf)

        factory = gtk.IconFactory()
        factory.add_default()
        factory.add('exaile-queue-icon', icon_set)

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
        self.append_separator()
        for name in self.playlist_manager.playlists:
            self.append(_(name), self.on_add_to_playlist, data = name)
            
        
    def on_add_new_playlist(self, selected = None):
        self.widget.controller.playlists_panel.add_new_playlist(self.widget.get_selected_tracks())
        
    def on_add_to_playlist(self, selected = None, pl_name = None):
        """
            Adds the selected tracks the playlist, saves the playlist
            and finally updates the playlist panel with the new tracks
        """
        pl = self.playlist_manager.get_playlist(pl_name)
        tracks = self.widget.get_selected_tracks()
        pl.add_tracks(tracks)
        self.playlist_manager.save_playlist(pl, overwrite = True)
        self.widget.controller.playlists_panel.update_playlist_node(pl)

    def popup(self, event):
        """
            Displays the menu
        """
        guiutil.Menu.popup(self, None, None, None, event.button, event.time)      

class PlaylistMenu(GenericTrackMenu):
    """
        Menu for xlgui.playlist.Playlist
    """
    def __init__(self, playlist):
        GenericTrackMenu.__init__(self, playlist,
            playlist.controller.exaile.queue)
        self.add_playlist_menu = AddToPlaylistMenu(playlist, playlist.controller.exaile.playlists)
        self.append_menu(_('Add to Playlist'), self.add_playlist_menu, 'gtk-add')
        self.append(_('Remove'), lambda *e: self.remove_selected_tracks(), 'gtk-remove')
                    
    def remove_selected_tracks(self, selected = None):
        """
            Removes the selected tracks from the playlist
            Note: does not update/save the playlist, user
            has to save the playlist themselves
        """
        self.widget.remove_selected_tracks()

class TrackSelectMenu(GenericTrackMenu):
    """
        Menu for any panel that operates on selecting tracks, IE, Files panel
        and the Collection panel
    """
    def __init__(self, panel, main):
        """
            Initializes the menu
        """
        self.main = main
        GenericTrackMenu.__init__(self, panel,
            panel.controller.exaile.queue)

    def _create_menu(self):
        """
            Actually adds the menu items
        """
        self.append_item = self.append(_('Append to Current'), lambda *e:
            self.on_append_items(), 'gtk-add')
        self.queue_item = self.append(_('Queue Items'), lambda *e: self.on_queue(),
            'exaile-queue-icon')

    def on_append_items(self, selected=None):
        """
            Appends the selected tracks to the current playlist
        """
        if not selected:
            selected = self.widget.get_selected_tracks()

        pl = self.main.get_selected_playlist()
        if pl:
            pl.playlist.add_tracks(selected, add_duplicates=False)

    def on_queue(self, selected=None):
        """
            Called when the user clicks the "toggle queue" item
        """
        if not selected:
            selected = self.widget.get_selected_tracks()
        pl = self.main.get_selected_playlist()
        self.queue.add_tracks(selected, add_duplicates=False)
        if pl:
            pl.playlist.add_tracks(selected, add_duplicates=False)
            pl.list.queue_draw()

# these are stubbs for now
FilesPanelMenu = TrackSelectMenu
CollectionPanelMenu = TrackSelectMenu
    
class PlaylistsPanelMenu(guiutil.Menu):
    """
        Menu for xlgui.panel.playlists.PlaylistsPanel, for when the
        user does not click on a playlist/track.  The default menu
    """
    def __init__(self, widget, radio=False):
        """
            @param widget: playlists panel widget
        """
        guiutil.Menu.__init__(self)
        self.widget = widget
        self.radio = radio
        self._create_playlist_menu()
        
    def _create_playlist_menu(self):
        if self.radio:
            self.append(_('Add Station'), lambda *e: self.on_add_playlist(),
                        'gtk-add')
        else: 
            self.append(_('Add Playlist'), lambda *e: self.on_add_playlist(),
                        'gtk-add')
            self.append(_('Add Smart Playlist'), lambda *e: self.on_add_smart_playlist(),
                        'gtk-add')
        
    def on_add_playlist(self, selected = None):
        self.widget.add_new_playlist()
    
    def on_add_smart_playlist(self, selected = None):
        self.widget.add_smart_playlist()

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
    def __init__(self, widget, main, smart=False):
        """
            @param widget: playlists panel widget
        """
        #Adds the menu options to add playlist
        radio = 'Radio' in self.__class__.__name__
        PlaylistsPanelMenu.__init__(self, widget, radio)
        self.append_separator()
        #Adds track menu options (like append, queue)
        TrackSelectMenu.__init__(self, widget, main)
        self.widget = widget
        self.smart = smart
        
        self.append_separator()
        self.append(_('Open'), lambda *e: self.on_open_playlist(),
                    'gtk-open')

        name = _('Rename')
        if self.smart:
            name = _('Edit')
        self.append(name, lambda *e: self.on_rename_playlist(),
                    'gtk-edit')
        self.append(_('Export'), lambda *e: self.on_export_playlist(),
                    'gtk-save')
        self.append_separator()
        self.append(_('Delete Playlist'), lambda *e: self.on_delete_playlist(), 
                    'gtk-remove') 
        
    def on_export_playlist(self, selected = None):
        """
            Asks the user where to save the file, then passes
            that information onto the widget to perform the save
            operation, export type is determined by the extension 
            entered
        """
        dialog = commondialogs.FileOperationDialog(_("Choose a file"),
            None, gtk.FILE_CHOOSER_ACTION_SAVE, 
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
            gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        
        extensions = { 'm3u' : _('M3U Playlist'), 
                                'pls' : _('PLS Playlist'),
                                'asx' : _('ASX Playlist'), 
                                'xspf' : _('XSPF Playlist') }
        
        dialog.add_extensions(extensions)
        
        #Find the name of currently selected playlist and put it in the name box
        selected_playlist = self.widget.get_selected_playlist()
        if selected_playlist is not None:
            dialog.set_current_name(selected_playlist.get_name())
        #dialog.set_current_folder(self.exaile.get_last_dir())

        result = dialog.run()
        if result == gtk.RESPONSE_OK:
            #TODO recover last directory from prefs
            #self.exaile.last_open_dir = dialog.get_current_folder()
            path = unicode(dialog.get_filename(), 'utf-8')
            try:
                self.widget.export_selected_playlist(path)
            except playlist.InvalidPlaylistTypeException:
                #TODO should we show an error or just append a default
                #extension?
                commondialogs.error(None, _('Invalid file extension, file not saved'))
        dialog.destroy()
                    
    def on_delete_playlist(self, selected = None):
        dialog = gtk.MessageDialog(None, 
            gtk.DIALOG_MODAL, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, 
            _("Are you sure you want to permanently delete the selected"
            " playlist?"))
        if dialog.run() == gtk.RESPONSE_YES:
            self.widget.remove_selected_playlist()
        dialog.destroy()
        
    def on_rename_playlist(self, selected = None):
        if self.smart:
            self.widget.edit_selected_smart_playlist()
            return

        # Ask for new name
        dialog = commondialogs.TextEntryDialog(
            _("Enter the new name you want for your playlist"),
            _("Rename Playlist"))
        result = dialog.run()
        if result == gtk.RESPONSE_OK:
            name = dialog.get_value()
            if not name == "":
                self.widget.rename_selected_playlist(name)
    
    def on_open_playlist(self, selected = None):
        self.widget.open_selected_playlist()
    
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
    def __init__(self, widget, main):
        PlaylistsPanelPlaylistMenu.__init__(self, widget, main)        
        
class PlaylistsPanelTrackMenu(guiutil.Menu):
    """
        Menu for xlgui.panel.playlists.PlaylistsPanel, for when the
        user right clicks on a track under a custom playlist
    """
    def __init__(self, widget):
        """
            @param widget: playlists panel widget
        """
        guiutil.Menu.__init__(self)
        self.widget = widget
        
        self.append(_('Remove'), lambda *e: self.on_remove_track(),
                    'gtk-remove')
        
    def on_remove_track(self, selected = None):
        self.widget.remove_selected_track()
    
    def popup(self, event):
        """
            Displays the menu
        """
        guiutil.Menu.popup(self, None, None, None, event.button, event.time)
