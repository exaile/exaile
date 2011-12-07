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

#
# Grouping field utility functions
#


import gtk
import gobject

import os
import re
import time
 
from xl import (
    event, 
    providers,
    player,
    settings
)

from xl import playlist
from xl.nls import gettext as _
from xl.trax import search

from xlgui import guiutil, main
from xlgui.widgets import menu, dialogs

import gt_widgets 
 
  

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
    
    
def _create_search_playlist( name, search_string, exaile ):
    '''Create a playlist based on a search string'''
    tracks = [ x.track for x in search.search_tracks_from_string( exaile.collection, search_string ) ]
        
    # create the playlist
    pl = playlist.Playlist( name, tracks )
    main.get_playlist_notebook().create_tab_from_playlist( pl )
    
    
def create_all_search_playlist( groups, exaile ):
    '''Create a playlist of tracks that have all groups selected'''
    
    name = 'Grouping: ' + ' and '.join( groups )
    search_string = ' '.join( [ 'grouping~"\\b%s\\b"' % re.escape( group.replace(' ','_') ) for group in groups ] ) 
        
    _create_search_playlist( name, search_string, exaile )

    
def create_custom_search_playlist( groups, exaile ):
    '''Create a playlist based on groups, and user input in a shiny dialog'''

    dialog = GroupTaggerQueryDialog( groups )
    if dialog.run() == gtk.RESPONSE_OK:
        name, search_string = dialog.get_search_params()
        _create_search_playlist( name, search_string, exaile )

    dialog.destroy()
    
    
class AllTagsDialog( gtk.Window ):

    def __init__(self, exaile):
    
        gtk.Window.__init__(self)
        self.set_title(_('Get all tags from collection'))
        self.set_resizable(True)
        self.set_size_request( 150, 400 ) 
        
        self.add(gtk.Frame())
        
        vbox = gtk.VBox()
        
        self.model = gt_widgets.GroupTaggerModel()
        self.view = gt_widgets.GroupTaggerView(exaile, None, editable=False)
        
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


class GroupTaggerQueryDialog(gtk.Dialog):      
    '''
        Dialog used to allow the user to select the behavior of the query
        used to filter out tracks that match a particular characteristic
    '''
    
    def __init__(self, groups):
        
        gtk.Dialog.__init__(self, 'Show tracks with groups' )
        
        groups.sort()
        
        # setup combo box selection
        self.combo_model = gtk.ListStore( gobject.TYPE_STRING )
        self.choices = [ _('Must have this tag [AND]'), _('May have this tag [OR]'), _('Must not have this tag [NOT]'), _('Ignored') ]
        for choice in self.choices:
            self.combo_model.append( [choice] )
        
        # setup table
        self.table = gtk.Table(rows=len(groups)+1, columns=2)
        
        self.table.attach( gtk.Label( _('Group') ), 0, 1, 0, 1, ypadding=5)
        self.table.attach( gtk.Label( _('Selected Tracks') ), 1, 2, 0, 1, ypadding=5)
        
        # TODO: Scrolled window
        self.data = []
        
        i = 1
        for group in groups:
            
            # label
            self.table.attach( gtk.Label( group ), 0, 1, i, i+1, xpadding=3 )
            
            # combo
            combo = gtk.ComboBox( self.combo_model )
            cell = gtk.CellRendererText()
            combo.pack_start(cell, True)
            combo.add_attribute(cell, 'text', 0)
            combo.set_active(0)
            self.table.attach( combo, 1, 2, i, i+1 )
            
            self.data.append( (group, combo) )
            
            i += 1
            
        self.vbox.pack_start( self.table )
        
        self.add_buttons( gtk.STOCK_OK, gtk.RESPONSE_OK, gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL )
        self.show_all()


    def get_search_params(self):
        '''Returns (name, search_string) from user selections'''
        
        and_p = [[], '']        # groups, name, re_string
        or_p = [[], '']
        not_p = [[], '']
        
        first = True
        name = 'Grouping: '
            
        # gather the data
        for group, widget in self.data:
            
            wsel = self.combo_model[ widget.get_active() ][0]

            if wsel == self.choices[0]:
                and_p[0].append( group )
            elif wsel == self.choices[1]:
                or_p[0].append( group )
            elif wsel == self.choices[2]:
                not_p[0].append( group )
        
        # create the AND conditions
        if len(and_p[0]):
            name += ' and '.join( and_p[0] )
            first = False
            
            and_p[1] = ' '.join( [ 'grouping~"\\b%s\\b"' % re.escape( group.replace(' ','_') ) for group in and_p[0] ] ) 
            
        # create the NOT conditions
        if len(not_p[0]):
            if first:
                name += ' and not '.join( not_p[0] )
            else:
                name += ' and ' + ' and '.join( [ 'not ' + p for p in not_p[0]] )
            first = False
            
            not_p[1] = ' ! grouping~"%s"' % '|'.join( [ '\\b' + re.escape( group.replace(' ','_') ) + '\\b' for group in not_p[0] ] )
            
        # create the OR conditions
        if len(or_p[0]):
            if first:
                name += ' or '.join( or_p[0] )
            elif len(or_p[0]) > 1:
                name += ' and (' + ' or '.join( or_p[0] ) + ')'
            else:
                name += ' and ' + ' or '.join( or_p[0] )
        
            or_p[1] = ' grouping~"%s"' %  '|'.join( [ '\\b' + re.escape( group.replace(' ','_') ) + '\\b' for group in or_p[0] ] ) 
        
        regex = (and_p[1] + or_p[1] + not_p[1]).strip() 

        return ( name, regex )

 
