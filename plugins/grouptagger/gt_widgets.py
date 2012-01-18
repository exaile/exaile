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
import pango
import glib

from xl.nls import gettext as _

from xlgui import main
from xlgui.widgets import dialogs

import gt_common

#
# GroupTaggerView signal 'changed' enum
#

# group was added to tagger
CHANGE_ADDED = object()
# group was deleted from tagger
CHANGE_DELETED = object()
# group was edited/toggled in tagger, pass none
CHANGE_OTHER = object()


class GroupTaggerView(gtk.TreeView):
    '''Treeview widget to display tag lists'''

    __gsignals__ = {
        # param1: see change enum above for the type of change, param2: value that changed
        'changed': (gobject.SIGNAL_ACTION, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT, gobject.TYPE_STRING) ),
    }
    
    def __init__(self, exaile, model=None, editable=False):
    
        gtk.TreeView.__init__(self,model)
        
        self.set_enable_search( False )
        self.get_selection().set_mode( gtk.SELECTION_MULTIPLE )
        
        # Setup the first column, not shown by default
        cell = gtk.CellRendererToggle()
        cell.set_property( 'mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE )
        cell.set_activatable( True )
        cell.connect( 'toggled', self.on_toggle)
        
        self.click_column = gtk.TreeViewColumn( None, cell, active=0 )
        
        # Setup the second column
        cell = gtk.CellRendererText()
        cell.set_property( 'editable', editable )
        if editable:
            cell.connect( 'edited', self.on_edit )
        
        self.append_column( gtk.TreeViewColumn( _('Group'), cell, text=1 ) )
        
        #
        # Menu setup
        #
        
        # menu items only shown when a single item selected
        self.single_selection_only = []
        # menu 
        self.multi_selection_only = []
        
        self.connect( 'popup-menu', self.on_popup_menu )
        self.connect( 'button-press-event', self.on_mouse_press )
            
        self.menu = gtk.Menu()
        
        if editable:
            
            item = gtk.MenuItem( _('Add new group') )
            item.connect( 'activate', self.on_menu_add_group )
            self.menu.add( item )
            
            item = gtk.MenuItem( _('Delete group') )
            item.connect( 'activate', self.on_menu_delete_group )
            self.menu.add( item )
            
            self.menu.add( gtk.SeparatorMenuItem() )
            
        item = gtk.MenuItem( 'x' )
        item.connect( 'activate', self.on_menu_show_tracks, exaile )
        self.menu.add( item )
        self._special_item = item
        
        item = gtk.MenuItem( _('Show tracks with selected (custom)') )
        item.connect( 'activate', self.on_menu_show_tracks_custom, exaile )
        self.menu.add( item )
        self.multi_selection_only.append( item )
        
        # TODO:
        # - Create smart playlist from selected
            
        self.menu.attach_to_widget(self, None)
        self.menu.show_all()
        
    def show_click_column(self):
        if len(self.get_columns()) == 1:
            self.insert_column( self.click_column, 0)
            
    def hide_click_column(self):
        if len(self.get_columns()) == 2:
            self.remove_column( self.click_column )
        
    def on_toggle( self, cell, path ):
        self.get_model()[path][0] = not cell.get_active()
        self.emit( 'changed', CHANGE_OTHER, None )
        
    def on_edit( self, cell, path, new_text ):
        if new_text != "":
            self.get_model()[path][1] = new_text
            self.emit( 'changed', CHANGE_OTHER, None )
        
    def on_menu_add_group( self, widget ):
        '''Menu says add something'''
        
        input = dialogs.TextEntryDialog( _('New tag value?'), _('Enter new tag value'))
        
        if input.run() == gtk.RESPONSE_OK:
            value = input.get_value()
            
            if value != "":
                model = self.get_model()
            
                # Don't insert duplicate values
                for row in model:
                    if row[1] == value:
                        row[0] = True
                        self.emit( 'changed', CHANGE_OTHER, None )
                        return
            
                model.append( [True, value] )
                self.emit('changed', CHANGE_ADDED, value )
        
    def on_menu_delete_group( self, widget ):
        '''Menu says delete something'''
        
        model, rows = self.get_selection().get_selected_rows()
        iters = []
        for row in rows:
            iters.append( model.get_iter( row ) )
        
        for i in iters:
            if i is not None:
                self.emit( 'changed', CHANGE_DELETED, model.get_value(i, 1) )
                model.remove(i)
            

            
    def on_menu_show_tracks( self, widget, exaile ):
        '''Menu to show all tracks that match a particular group'''
        
        model, rows = self.get_selection().get_selected_rows()
        groups = [model[row][1] for row in rows]
        
        gt_common.create_all_search_playlist( groups, exaile )
    
    def on_menu_show_tracks_custom( self, widget, exaile ):
        '''
            Menu to show all tracks that match a particular group,
            with custom AND/OR matching
        '''
    
        model, rows = self.get_selection().get_selected_rows()
        groups = [model[row][1] for row in rows]
        
        gt_common.create_custom_search_playlist( groups, exaile )
        
    def _adjust_menu(self):
    
        sel = self.get_selection()
    
        # if greater than one, hide some items
        if sel.count_selected_rows() <= 1:
            single_selection = True
            
            # special item
            model, rows = sel.get_selected_rows()
            if len(rows) == 1:
                self._special_item.set_label( _('Show tracks tagged with "%s"') % model[rows[0]][1] )
            else:
                self._special_item.set_label( _('Show tracks with selected') )
        else:
            single_selection = False
            self._special_item.set_label( _('Show tracks with all selected') )
            
        for item in self.single_selection_only:
            if single_selection:
                item.show()
            else:
                item.hide()
                
        for item in self.multi_selection_only:
            if single_selection:
                item.hide()
            else:
                item.show()
        
    def on_mouse_press(self, widget, event):
    
        if event.button == 3:
            
            # TODO: select item before showing the menu for it
            sel = self.get_selection()
            
            if sel.count_selected_rows() == 0:
                info = self.get_path_at_pos( int(event.x), int(event.y) )
                if info is not None:
                    self.grab_focus()
                    self.set_cursor( info[0], info[1], 0 )
            
            self._adjust_menu()
            self.menu.popup( None, None, None, event.button, event.time )
            return True
            
        return False
    
    def on_popup_menu(self, widget):
        self._adjust_menu()
        self.menu.popup( None, None, None, None, None )
        return True

gobject.type_register(GroupTaggerView)
        
class GroupTaggerModel(gtk.ListStore):
    '''Model for tagger'''
    
    def __init__(self):
        gtk.ListStore.__init__( self, gobject.TYPE_BOOLEAN, gobject.TYPE_STRING )
        self.set_sort_column_id( 1, gtk.SORT_ASCENDING )
        
        #self.set_default_sort_func( self._sort_func )
        #self.set_sort_column_id( -1, gtk.SORT_DESCENDING )
        
    def _sort_func(self, model, iter1, iter2):
        '''
            Sort the model first by enabled, then by group name
            
            --> This is a cool idea, but in practice it's *really* annoying
            to use if the list is constantly rearranging itself. 
        '''
    
        v0_b, v0_s = self.get( iter1, 0, 1 )
        v1_b, v1_s = self.get( iter2, 0, 1 )
    
        if v0_b == v1_b:
            if v0_s == v1_s:
                return 0
            elif v0_s > v1_s:
                return -1
            
            return 1
        
        elif v0_b is True:
            return 1
        
        return -1
        
    def get_active_groups(self):
        return [row[1] for row in self if row[0] == True ]
        
    def get_all_groups(self):
        return [row[1] for row in self]

    def has_group(self, group):
        for row in self:
            if row[1] == group:
                return True
        return False

class GroupTaggerWidget(gtk.VBox):
    '''Melds the tag view with an 'add' button'''

    def __init__(self, exaile):
        gtk.VBox.__init__(self)
        
        self.title = gtk.Label()
        self.artist = gtk.Label()
        self.view = GroupTaggerView( exaile, GroupTaggerModel(), editable=True )
        self.store = self.view.get_model()
        
        self.tag_button = gtk.Button( _('Add Group') )
        self.tag_button.connect( 'clicked', self.on_add_tag_click )
        
        self.title.set_alignment(0,0.5)
        self.title.set_line_wrap(True)
        self.title.hide()
        
        self.artist.set_alignment(0,0.5)
        self.artist.set_line_wrap(True)
        self.artist.hide()
        
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        scroll.add( self.view )
        
        self.pack_start( self.title, expand=False )
        self.pack_start( self.artist, expand=False )
        self.pack_start( scroll, True, True )
        self.pack_start( self.tag_button, expand=False )
        
    def on_add_tag_click(self, widget):
        self.view.on_menu_add_group( self.view )
            
    def set_title(self, title):
        '''Sets the title for this widget. Hides title if title is None'''
        if title is None:
            self.title.hide()
        else:
            self.title.set_markup('<big><b>' + glib.markup_escape_text(title) + '</b></big>')
            self.title.show()
            
    def set_artist(self, artist):
        '''Sets the author for this widget. Hides it if author is None'''
        if artist is None:
            self.artist.hide()
        else:
            self.artist.set_text('by ' + artist)
            self.artist.show()
            
    def set_track_info(self, track):
        '''Shortcut for set_title/set_artist'''
        if track is None:
            self.set_title( None )
            self.set_artist( None )
        else:
            self.set_title( track.get_tag_display( 'title' ) )
            self.set_artist( track.get_tag_display( 'artist' ) )

    def add_groups(self, groups, clear=False):
        '''
            Accepts an array of tuples in the form (Boolean, String), where
            the boolean is whether the group should be enabled, and string is
            the name of the group
            
            if clear is True:
                Clears the model, sets up model with data
            else:
                Adds them to the model if they are not already present
        '''
        
        self.view.freeze_child_notify()
        self.view.set_model( None )
        
        if clear:
            self.store.clear()
            
        for group in groups:
            if clear or not self.store.has_group( group[1] ): 
                self.store.append( group )
            
        self.view.set_model( self.store )
        self.view.thaw_child_notify()
            
    def set_groups(self, groups):
        '''
            Accepts an array of tuples in the form (Boolean, String), where
            the boolean is whether the group should be enabled, and string is
            the name of the group
        '''
        self.add_groups( groups, clear=True )
        

        
class GroupTaggerPanel(gtk.VBox):
    '''A panel that has all of the functionality in it'''

    def __init__(self, exaile):
    
        gtk.VBox.__init__(self)
    
        # add the tagger widget
        self.tagger = GroupTaggerWidget( exaile )
        
        # add the widgets to this page
        self.pack_start( self.tagger, expand=True ) 

