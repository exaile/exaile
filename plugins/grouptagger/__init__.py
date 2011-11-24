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


import os
import time
import gtk
import gobject
 
from xl import (
    event, 
    providers,
    player,
    settings
)

from xl.nls import gettext as _
from xlgui import guiutil
from xlgui.widgets import menu, dialogs

import gt_widgets

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
    
        self.panel = gt_widgets.GroupTaggerPanel()
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
        
        # trigger start event if exaile is currently playing something
        if player.PLAYER.is_playing():
            self.set_display_track( player.PLAYER.current )
        else:
            self.panel.tagger.set_groups( [(False, group) for group in get_default_groups()] )
    
    def disable_plugin(self, exaile):
        '''Called when the plugin is disabled'''
        
        if self.tools_menuitem:
            providers.unregister( 'menubar-tools-menu', self.tools_menuitem)
            self.tools_menuitem = None
            
        if self.tag.dialog:
            self.tag_dialog.destroy()
            self.tag_dialog = None
        
        # de-register the exaile events
        event.remove_callback( self.playback_track_start, 'playback_track_start' )
        
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
            
    def on_playlist_cursor_changed( self, type, playlist_view, context ):
        '''Called when an item in a playlist is selected'''
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
  
#
# Grouping field utility functions
#
  

def get_track_groups(track):
    '''
        Returns a set() of groups present in this track
    '''
    grouping = track.get_tag_raw('grouping', True)
    
    if grouping is not None:
        return set([ group.replace('_', ' ') for group in grouping.split()])
        
    return set()


def set_track_groups(track, groups):
    '''
        Given an array of groups, sets them on a track
        
        Returns true if successful, false if there was an error
    '''
    
    grouping = ' '.join( sorted( [ '_'.join( group.split() ) for group in groups ] ) )
    track.set_tag_raw( 'grouping', grouping )
    
    if not track.write_tags():
        dialogs.error( None, "Error writing tags to %s" % gobject.markup_escape_text(track.get_loc_for_io()) )
        return False
        
    return True


def get_default_groups():
    '''
        Returns a set() of groups stored in the settings that the user can
        easily select without having to retype it
    '''
    
    default_groups = settings.get_option( 'plugin/grouptagger/default_groups', set() )
    return set(default_groups)

    
    
def set_default_groups(groups):
    '''
        Stores the default groups as a list
    '''
    settings.set_option( 'plugin/grouptagger/default_groups', list(groups) )
    
    
def get_all_collection_groups( collection ):
    '''
        For a given collection of tracks, return all groups
        used within that collection
    '''
    groups = set()
    for track in collection:
        groups |= get_track_groups(track)
        
    return groups
    
    
class AllTagsDialog( gtk.Window ):

    def __init__(self, exaile):
    
        gtk.Window.__init__(self)
        self.set_title(_('Get all tags from collection'))
        self.set_resizable(True)
        self.set_size_request( 150, 400 ) 
        
        self.add(gtk.Frame())
        
        vbox = gtk.VBox()
        
        self.model = gt_widgets.GroupTaggerModel()
        self.view = gt_widgets.GroupTaggerView(None, editable=False)
        
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        scroll.add( self.view )
        scroll.hide()
        
        vbox.pack_start( scroll, True, True )
        
        button = gtk.Button(_('Add selected to choices'))
        button.connect('clicked', self.on_add_selected_to_choices )
        vbox.pack_end( button, False, False )
        
        self.child.add(vbox)
        
        # get the collection groups
        groups = get_all_collection_groups(exaile.collection)
        for group in groups:
            self.model.append( [False, group] )
            
        self.view.set_model( self.model )
        self.view.show_click_column()

        self.show_all()
        
    def on_add_selected_to_choices(self, widget):
        defaults = get_default_groups()
        for group in self.model.get_active_groups():
            defaults.add( group )
        set_default_groups( defaults )
#
# TODO: Fix these
#
 
        
def generate_playlist( group, playlist_name ):
    # creates a smart playlist based on a particular tag
    pass
    
def generate_playlists( ):

    # what this function does is create playlists based on all the tags present in the library
    tracks = get_all_tracks()
    
    groupset = set()
    
    # TODO: I wonder if there's a way we can cache this data, or
    # get exaile to do it for us.. 
    for track in tracks:
        groups = get_track_groups( track )
        groupset |= groups
        
    prefix = settings.get_option( 'plugins/grouptagger/auto-playlist-prefix', 'Auto-' )
    for group in groupset:
        playlist_name = prefix + group
        if playlist_name not in playlists:
            generate_playlist( group, playlist_name )
        

   

    
