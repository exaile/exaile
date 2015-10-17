# Copyright (C) 2011 Dustin Spicuzza
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
from gi.repository import Gtk

import os
import os.path
import datetime
 
from xl import (
    event, 
    player,
    providers,
    settings,
    xdg
)

from xl.playlist import Playlist
from xl.nls import gettext as _

import xlgui
from xlgui import main
from xlgui.widgets import menu, dialogs
from xlgui.widgets.notebook import NotebookPage, NotebookTab
from xlgui.widgets.playlist import PlaylistView

import history_preferences

plugin = None

def get_preferences_pane():
    return history_preferences


def enable(exaile):
    '''Called on plugin enable'''
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)
        
def _enable(eventname, exaile, nothing):

    global plugin
    plugin = HistoryPlugin(exaile)
    
def disable(exaile):
    '''Called on plugin disable'''
    
    global plugin
    if plugin is not None:
        plugin.disable_plugin(exaile)
        plugin = None

def teardown(exaile):
    '''Called on exaile quit'''
    global plugin
    if plugin is not None:
        plugin.teardown_plugin(exaile)
        

class HistoryPlugin(object):
    '''Implements logic for plugin'''
    
    def __init__(self, exaile):
    
        self.exaile = exaile
    
        save_on_exit = settings.get_option('plugin/history/save_on_exit', history_preferences.save_on_exit_default)
        shown = settings.get_option('plugin/history/shown', False)
    
        # immutable playlist that stores everything we've played
        self.history_loc = os.path.join(xdg.get_data_dir(), 'history')
        
        self.history_playlist = HistoryPlaylist( player.PLAYER )
        
        if save_on_exit:
            self.history_playlist.load_from_location( self.history_loc )
        
        self.history_page = HistoryPlaylistPage( self.history_playlist, player.PLAYER )
        self.history_tab = NotebookTab(main.get_playlist_notebook(), self.history_page )
        
        # add menu item to 'view' to display our playlist 
        self.menu = menu.check_menu_item( 'history', '', _('Playback history'), \
            lambda *e: self.is_shown(), self.on_playback_history )
            
        providers.register( 'menubar-view-menu', self.menu )
        
        # add the history playlist to the primary notebook
        if save_on_exit and shown:
            self.show_history( True )
        
    def teardown_plugin(self, exaile):
        '''Called when exaile is exiting'''
        
        if settings.get_option('plugin/history/save_on_exit', history_preferences.save_on_exit_default ):
            self.history_playlist.save_to_location( self.history_loc )
            settings.set_option( 'plugin/history/shown', self.is_shown() )
        else:
            settings.set_option( 'plugin/history/shown', False )
            
        self.show_history(False)
    
    def disable_plugin(self, exaile):
    
        '''Called when the plugin is disabled'''
        if self.menu:
            providers.unregister( 'menubar-view-menu', self.menu )
            self.menu = None
            
        self.show_history(False)

        if os.path.exists( self.history_loc ):
        
            dialog = Gtk.MessageDialog( None, Gtk.DialogFlags.MODAL, Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO, 
                                        _('Erase stored history?') )
                
            if dialog.run() == Gtk.ResponseType.YES:
                try:
                    os.unlink( self.history_loc )
                except:
                    pass
                    
            dialog.destroy()
        
    def is_shown(self):
        return main.get_playlist_notebook().page_num( self.history_page ) != -1
    
    def on_playback_history(self, menu, name, parent, context):
        self.show_history( not self.is_shown() )
        
    def show_history(self, show):

        if show == self.is_shown():
            return
    
        if show:
            pn = main.get_playlist_notebook()
            pn.add_tab( self.history_tab, self.history_page  )
        else:
            self.history_tab.close()

        
class HistoryPlaylistPage( NotebookPage ):

    # add two buttons on the bottom: 'save to playlist', and
    # clear history. Use the dirty key to figure out if we 
    # warn about clearing history.. 
    
    menu_provider_name = 'history-tab-context-menu'
    reorderable = False
    
    def __init__(self, playlist, player):
        NotebookPage.__init__(self)
        
        self.playlist = playlist
        
        self.swindow = Gtk.ScrolledWindow()
        self.swindow.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.pack_start(self.swindow, True, True, 0)

        self.view = PlaylistView(self.playlist, player)
        self.swindow.add(self.view)
        
        hbox = Gtk.HButtonBox()
        
        button = Gtk.Button(stock=Gtk.STOCK_CLEAR)
        button.connect( 'clicked', self.on_clear_history )
        hbox.pack_start( button , True, True, 0)
        
        button = Gtk.Button(stock=Gtk.STOCK_SAVE)
        button.connect( 'clicked', self.on_save_history )
        hbox.pack_start( button , True, True, 0)
        
        align = Gtk.Alignment.new(1, 0, 0, 0)
        align.add( hbox )
        
        self.pack_start( align, False, False, 0 )
        
        self.show_all()
    
    ## NotebookPage API ##

    def get_page_name(self):
        return _("History")

    ## End NotebookPage ##
    
    def on_clear_history( self, widget ):
        self.playlist._clear()
    
    def on_save_history( self, widget ):
        self.save_history()
        
    def save_history(self):
    
        if len(self.playlist) == 0:
            return
    
        name = 'History %s' % datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
        playlists = xlgui.get_controller().get_panel('playlists')
        playlists.add_new_playlist( self.playlist, name )

    
def __create_history_tab_context_menu():
    smi = menu.simple_menu_item
    sep = menu.simple_separator
    items = []
    items.append(smi('save', [], _("Save History"), 'gtk-save',
        lambda w, n, o, c: o.save_history()))
    items.append(smi('clear', ['save'], _("_Clear History"), 'gtk-clear',
        lambda w, n, o, c: o.playlist._clear()))
    items.append(sep('tab-close-sep', ['clear']))
    items.append(smi('tab-close', ['tab-close-sep'], None, 'gtk-close',
        lambda w, n, o, c: o.tab.close()))
    
    for item in items:
        providers.register( 'history-tab-context-menu', item )
        
__create_history_tab_context_menu()
        
        
class HistoryPlaylist( Playlist ):

    def __init__(self, player):
        Playlist.__init__( self, _('History') )
        
        # catch the history
        event.add_callback( self.__on_playback_track_start, 'playback_track_start', player )
        
        if player.is_paused() or player.is_playing():
            self.__on_playback_track_start( 'playback_track_start', player, player.current )
        
    def __on_playback_track_start(self, event, player, track):
        '''Every time a track plays, add it to the playlist'''
    
        maxlen = int(settings.get_option( 'plugin/history/history_length', history_preferences.history_length_default ))
        if maxlen < 0:
            maxlen = 0
            settings.set_option( 'plugin/history/history_length', 0 )
        
        if len(self) >= maxlen-1:
            Playlist.__delitem__( self, slice(0, max(0, len(self)-(maxlen-1)), None) )

        Playlist.__setitem__( self, slice(len(self),len(self),None), [track] )
        
    def _clear(self):
        Playlist.__delitem__( self, slice(None, None, None) )
 
    #
    # Suppress undesirable playlist functions, history playlist is immutable
    #
    
    def clear(self):
        pass
        
    def set_shuffle_mode(self, mode):
        pass
    
    def set_repeat_mode(self, mode):
        pass
        
    def set_dynamic_mode(self, mode):
        pass
        
    def randomize(self, positions=None):
        pass
        
    def sort(self, tags, reverse=False):
        pass
        
    def __setitem__(self, i, value):
        pass
        
    def __delitem__(self, i):
        pass
        
    def append(self, other):
        pass
        
    def extend(self, other):
        pass
        
    def pop(self, i=-1):
        pass
        
