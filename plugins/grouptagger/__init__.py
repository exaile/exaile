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

import gtk
import gobject

import os
import time
 
from xl import (
    event, 
    providers,
    player,
    settings
)

from xl.nls import gettext as _

from xlgui import guiutil, main
from xlgui.widgets import menu, dialogs

import gt_widgets
from gt_common import *

plugin = None


def enable(exaile):
    '''Called on plugin enable'''
    if exaile.loading:
        event.add_callback(_enable, 'gui_loaded')
    else:
        _enable(None, exaile, None)
        
def _enable(eventname, exaile, nothing):

    global plugin
    plugin = GroupTaggerPlugin(exaile)
    
def disable(exaile):
    '''Called on plugin disable'''
    
    global plugin
    if plugin is not None:
        plugin.disable_plugin(exaile)
        plugin = None
   
    
class GroupTaggerPlugin(object):
    '''Implements logic for plugin'''

    def __init__(self, exaile):
    
        self.track = None
        self.tag_dialog = None
    
        self.panel = gt_widgets.GroupTaggerPanel(exaile)
        self.panel.show_all()
        
        self.panel.tagger.view.connect( 'changed', self.on_group_changed )
        
        exaile.gui.add_panel( self.panel, _('GroupTagger') )
        
        # ok, register for some events
        event.add_callback( self.on_playback_track_start, 'playback_track_start' )
        event.add_callback( self.on_playlist_cursor_changed, 'playlist_cursor_changed' )
        event.add_callback( self.on_plugin_options_set, 'plugin_grouptagger_option_set' )
        
        # add our own submenu for functionality
        self.tools_submenu = menu.Menu( None, context_func=lambda p: exaile )
        
        self.tools_submenu.add_item( 
            menu.simple_menu_item( 'gt_get_tags', [], _('Get all tags in collection'),
                callback=self.on_get_tags_menu ) 
        )
        
        # group them together to make it not too long
        self.tools_menuitem = menu.simple_menu_item('grouptagger', ['plugin-sep'], 
                _('GroupTagger'), submenu=self.tools_submenu )
        providers.register( 'menubar-tools-menu', self.tools_menuitem )
        
        # playlist context menu items
        self.selectall_menuitem = menu.simple_menu_item( 'gt_search_all', ['rating'], 
                _('Show tracks with all tags'), callback=self.on_playlist_context_select_all_menu, callback_args=[exaile])
        providers.register( 'playlist-context-menu', self.selectall_menuitem )
        
        self.selectcustom_menuitem = menu.simple_menu_item( 'gt_search_custom', ['rating'], 
                _('Show tracks with tags (custom)'), callback=self.on_playlist_context_select_custom_menu, callback_args=[exaile])
        providers.register( 'playlist-context-menu', self.selectcustom_menuitem )
        
        # trigger start event if exaile is currently playing something
        if player.PLAYER.is_playing():
            self.set_display_track( player.PLAYER.current )
        else:
            self.panel.tagger.set_groups( [(False, group) for group in get_default_groups()] )
    
    def disable_plugin(self, exaile):
        '''Called when the plugin is disabled'''
        
        if self.tools_menuitem:
            providers.unregister( 'menubar-tools-menu', self.tools_menuitem)
            providers.unregister( 'playlist-context-menu', self.selectall_menuitem )
            providers.unregister( 'playlist-context-menu', self.selectcustom_menuitem )
            
            self.tools_menuitem = None
            self.selectall_menuitem = None
            self.selectcustom_menuitem = None
            
            
        if self.tag_dialog:
            self.tag_dialog.destroy()
            self.tag_dialog = None
        
        # de-register the exaile events
        event.remove_callback( self.on_playback_track_start, 'playback_track_start' )
        event.remove_callback( self.on_playlist_cursor_changed, 'playlist_cursor_changed' )
        event.remove_callback( self.on_plugin_options_set, 'plugin_grouptagger_option_set' )
        
        exaile.gui.remove_panel( self.panel )
        
    #
    # Menu callbacks
    #
    
    def on_get_tags_menu(self, widget, name, parent, exaile):
        
        if self.tag_dialog is None:
            self.tag_dialog = AllTagsDialog(exaile)
            self.tag_dialog.connect('delete-event', self.on_get_tags_menu_window_deleted)
            
        self.tag_dialog.show_all()
        
    def on_get_tags_menu_window_deleted(self, *args):
        self.tag_dialog = None
        
    #
    # Exaile events
    #
        
    @guiutil.idle_add()
    def on_playback_track_start(self, type, player, track):
        '''Called when a new track starts'''
        self.set_display_track( track )
        
        
    #def on_playlist_context_menu( self, menu, display_name, playlist_view, context ):
    #    '''Called when our context menu item is selected'''
    #    tracks = context['selected-tracks']
    #    if len(tracks) == 1:
    #        self.set_display_track( tracks[0] )
    
    def on_playlist_context_select_all_menu( self, menu, display_name, playlist_view, context, exaile ):
        '''Called when 'Select tracks with same groups' is selected'''
        tracks = context['selected-tracks']
        groups = set()
        
        for track in tracks:
            groups |= get_track_groups(track)
        
        if len(groups) > 0:
            create_all_search_playlist( groups, exaile )
        else:
            dialogs.error( 'No grouping tags found in selected tracks' )
        
    def on_playlist_context_select_custom_menu( self, menu, display_name, playlist_view, context, exaile ):
        '''Called when 'select tracks with similar groups (custom)' is selected'''
        tracks = context['selected-tracks']
        groups = set()
        
        for track in tracks:
            groups |= get_track_groups(track)
        
        if len(groups) > 0:
            create_custom_search_playlist( [group for group in groups], exaile )
        else:
            dialogs.error( 'No grouping tags found in selected tracks' )
        
    
    def on_playlist_cursor_changed( self, type, playlist_view, context ):
        '''Called when an item in a playlist is selected'''
        
        #TODO: Allow multiple tracks
        tracks = context['selected-tracks']
        if len(tracks) == 1:
            self.set_display_track( tracks[0] )
        

    def set_display_track(self, track):
        '''Updates the display with the tags/info for a particular track'''
        self.track = track
        
        # get the groups as a set
        track_groups = get_track_groups( track )
        
        # get the default groups
        default_groups = get_default_groups()
        
        # setup something appropriate to display
        groups = [(True, group) for group in track_groups]
        
        # add any defaults not present
        groups.extend( [ (False, group) for group in default_groups.difference( track_groups )] )
        
        # set them
        self.panel.tagger.view.show_click_column()
        self.panel.tagger.set_groups( groups )
        self.panel.tagger.set_track_info( track )
        
    #
    # Widget events
    #
        
    def on_group_changed(self, view, action, value):
        '''Called when a group is added/deleted/etc on the widget'''
        
        groups = view.get_model().get_active_groups()
        
        if self.track is not None:
            write_succeeded = set_track_groups( self.track, groups )
        
        #
        # use the action to determine how to update the global
        # defaults: If the user explcitly added/deleted objects,
        # then we add/remove those to/from the globals if required
        #
        
        if action == gt_widgets.CHANGE_ADDED or action == gt_widgets.CHANGE_DELETED:
        
            all_groups = get_default_groups()
            sz = len( all_groups )
        
            if action == gt_widgets.CHANGE_ADDED:
                all_groups.add( value )
            else:
                all_groups.discard( value )
        
            # if it changed, set it
            if sz != len( all_groups ):
                set_default_groups( all_groups )
        
        if self.track is not None and not write_succeeded:
            self.set_display_track( self.track )
  
    def on_plugin_options_set(self, manager, option, value):
        '''Called each time the default groups are set'''
        if value == 'plugin/grouptagger/default_groups':
            self.panel.tagger.add_groups( [(False, group) for group in get_default_groups()] )
  

    
