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

import glib
import gtk
import gobject
import pango
 
from xl import (
    event, 
    providers,
    player,
    settings
)

from xl.nls import gettext as _

from xlgui import guiutil
from xlgui.widgets import menu, dialogs

import gt_prefs
import gt_widgets
from gt_common import *

plugin = None


def get_preferences_pane():
    return gt_prefs

def enable(exaile):
    '''Called on plugin enable'''
    if exaile.loading:
        event.add_callback(_enable, 'gui_loaded')
    else:
        _enable(None, exaile, None)
        
def _enable(eventname, exaile, nothing):

    global plugin
    plugin = GroupTaggerPlugin(exaile)
    
    event.remove_callback(_enable, 'gui_loaded')
    
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
        
        migrate_settings()
    
        self.panel = gt_widgets.GroupTaggerPanel(exaile)
        self.panel.show_all()
        self.setup_panel_font(False)
        
        self.panel.tagger.view.connect( 'category-changed', self.on_category_change )
        self.panel.tagger.view.connect( 'category-edited', self.on_category_edited )
        self.panel.tagger.view.connect( 'group-changed', self.on_group_change )
        
        # add to exaile's panel interface
        exaile.gui.panels['grouptagger'] = self.panel
        exaile.gui.add_panel( self.panel, _('GroupTagger') )
        
        # ok, register for some events
        event.add_callback( self.on_playback_track_start, 'playback_track_start' )
        event.add_callback( self.on_playlist_cursor_changed, 'playlist_cursor_changed' )
        event.add_callback( self.on_plugin_options_set, 'plugin_grouptagger_option_set' )
        
        # add our own submenu for functionality
        self.tools_submenu = menu.Menu( None, context_func=lambda p: exaile )
        
        self.tools_submenu.add_item( 
            menu.simple_menu_item( 'gt_get_tags', [], _('Get all tags from collection'),
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
            self.panel.tagger.set_categories( [], get_group_categories() )
    
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
        
    def setup_panel_font(self, always_set):
        font = settings.get_option('plugin/grouptagger/panel_font', None)
        if font is None:
            if not always_set:
                return
            font = gt_prefs._get_system_default_font()
        else:
            font = pango.FontDescription(font)

        self.panel.tagger.set_font(font)
        
    #
    # Menu callbacks
    #
    
    def on_get_tags_menu(self, widget, name, parent, exaile):
        
        if self.tag_dialog is None:
            self.tag_dialog = gt_widgets.AllTagsDialog(exaile, self.panel.tagger.add_groups)
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
    
    def on_playlist_context_select_all_menu( self, menu, display_name, playlist_view, context, exaile ):
        '''Called when 'Select tracks with same groups' is selected'''
        tracks = context['selected-tracks']
        groups = set()
        
        for track in tracks:
            groups |= get_track_groups(track)
        
        if len(groups) > 0:
            create_all_search_playlist( groups, exaile )
        else:
            dialogs.error( None, 'No grouping tags found in selected tracks' )
        
    def on_playlist_context_select_custom_menu( self, menu, display_name, playlist_view, context, exaile ):
        '''Called when 'select tracks with similar groups (custom)' is selected'''
        tracks = context['selected-tracks']
        groups = set()
        
        for track in tracks:
            groups |= get_track_groups(track)
        
        if len(groups) > 0:
            create_custom_search_playlist( groups, exaile )
        else:
            dialogs.error( None, 'No grouping tags found in selected tracks' )
    
    def on_playlist_cursor_changed( self, type, playlist_view, context ):
        '''Called when an item in a playlist is selected'''
        
        #TODO: Allow multiple tracks
        tracks = context['selected-tracks']
        if len(tracks) == 1:
            self.set_display_track( tracks[0] )

    def set_display_track(self, track, force_update=False):
        '''Updates the display with the tags/info for a particular track'''
        
        if self.track == track and not force_update:
            return
            
        self.track = track
        
        # get the groups as a set
        track_groups = get_track_groups( track )
        
        # set them
        self.panel.tagger.view.show_click_column()
        self.panel.tagger.set_categories( track_groups, get_group_categories() )
        self.panel.tagger.set_track_info( track )
        
    #
    # Widget events
    #
    
    def on_category_change(self, view, action, category):
        '''Called when a category has something happen to it'''
    
        categories = get_group_categories()
    
        if action == gt_widgets.category_change.added:
            categories.setdefault(category, [True, []])
                
        elif action == gt_widgets.category_change.deleted:
            del categories[category]
            
        elif action == gt_widgets.category_change.collapsed:
            categories[category][0] = False
            
        elif action == gt_widgets.category_change.expanded:
            categories[category][0] = True
            
        elif action == gt_widgets.category_change.updated:
            v = categories.setdefault(category, [True, []])
            v[1] = view.get_model().get_category_groups(category)
            
        set_group_categories( categories )
    
    def on_category_edited(self, view, old_category, new_category):
        '''Called when a category name is edited'''
    
        categories = get_group_categories()
        categories[new_category] = categories.pop(old_category)
        set_group_categories( categories )
    
    def on_group_change(self, view, action, value):
        '''Called when a group is added/deleted/updated on the widget'''
        
        if self.track is not None:
            groups = view.get_model().iter_active()
            if not set_track_groups( self.track, groups ):
                self.set_display_track( self.track, force_update=True )
                
    def on_plugin_options_set(self, evtype, settings, option):
        '''Handles option changes'''
        if option == 'plugin/grouptagger/panel_font':
            glib.idle_add( self.setup_panel_font, True )
            
    
  
