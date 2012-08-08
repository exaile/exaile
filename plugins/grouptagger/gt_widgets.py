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

import re

from xl import common
from xl.nls import gettext as _

from xlgui import main
from xlgui.widgets import dialogs, menu

import gt_common

#
# GroupTaggerView signal 'changed' enum
#

# group was added to tagger
GT_GROUP_ADDED = object()
# group was deleted from tagger
GT_GROUP_DELETED = object()
# group was edited/toggled in tagger, pass none
GT_GROUP_EDITED = object()

GT_CATEGORY_ADDED = object()
GT_CATEGORY_DELETED = object()
GT_CATEGORY_EXPANDED = object()
GT_CATEGORY_COLLAPSED = object()
GT_CATEGORY_UPDATED = object()

# default group category
uncategorized = _('Uncategorized')


class GTShowTracksMenuItem(menu.MenuItem):
    def __init__(self, name, after):
        menu.MenuItem.__init__(self, name, None, after)
        
    def factory(self, menu, parent, context):
        
        groups = context['groups']
            
        if len(groups) == 0:
            display_name = _('Show tracks with selected')
        elif len(groups) == 1:
            display_name = _('Show tracks tagged with "%s"') % groups[0]
        else:
            display_name =  _('Show tracks with all selected')
        
        menuitem = gtk.MenuItem(display_name)
        menuitem.connect('activate', lambda *e: gt_common.create_all_search_playlist( context['groups'], parent.exaile ))
        return menuitem

class GroupTaggerContextMenu(menu.Menu):
    def __init__(self, tagger):
        menu.Menu.__init__(self, tagger)
        
    def get_context(self):
        context = common.LazyDict(self._parent)
        context['selected-rows'] = lambda name, parent: parent.get_selection().get_selected_rows()
        context['groups'] = lambda name, parent: parent.get_selected_groups( context['selected-rows'] )
        context['categories'] = lambda name, parent: parent.get_selected_categories( context['selected-rows'] )
        return context


class GroupTaggerView(gtk.TreeView):
    '''Treeview widget to display tag lists'''

    __gsignals__ = {
        
        'category-changed': (gobject.SIGNAL_ACTION, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT, gobject.TYPE_STRING) ),
        'category-edited': (gobject.SIGNAL_ACTION, gobject.TYPE_NONE, (gobject.TYPE_STRING, gobject.TYPE_STRING) ),
        'group-changed': (gobject.SIGNAL_ACTION, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT, gobject.TYPE_STRING) ),
        'group-edited': (gobject.SIGNAL_ACTION, gobject.TYPE_NONE, (gobject.TYPE_STRING, gobject.TYPE_STRING) ),
    }
    
    def __init__(self, exaile, model=None, editable=False):
    
        gtk.TreeView.__init__(self,None)
        
        self.exaile = exaile
        
        self.connect('notify::model', self.on_notify_model)
        
        self.set_model(model)
        self.set_enable_search( False )
        self.get_selection().set_mode( gtk.SELECTION_MULTIPLE )
        
        self._row_expanded_id = self.connect( 'row-expanded', self.on_row_expanded )
        self._row_collapsed_id = self.connect( 'row-collapsed', self.on_row_collapsed )
        
        if editable:
            self.set_reorderable(True)
        
        # Setup the first column, not shown by default
        cell = gtk.CellRendererToggle()
        cell.set_property( 'mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE )
        cell.set_activatable( True )
        cell.connect( 'toggled', self.on_toggle)
        
        self.click_column = gtk.TreeViewColumn( None, cell, active=0, visible=2 )
        
        # Setup the second column
        cell = gtk.CellRendererText()
        cell.set_property( 'editable', editable )
        if editable:
            cell.connect( 'edited', self.on_edit )
        
        self.append_column( gtk.TreeViewColumn( _('Group'), cell, text=1 ) )
        
        #
        # Menu setup
        #
        
        self.menu = GroupTaggerContextMenu(self)
        smi = menu.simple_menu_item
        sep = menu.simple_separator
        
        self.connect( 'popup-menu', self.on_popup_menu )
        self.connect( 'button-release-event', self.on_mouse_release )
            
        if editable:
            
            item = smi( 'addgrp', [], _('Add new group'), \
                        callback=self.on_menu_add_group )
            self.menu.add_item( item )
            
            item = smi( 'delgrp', ['addgrp'], _('Delete group'), \
                        callback=self.on_menu_delete_group, \
                        condition_fn=lambda n,p,c: False if len(c['groups']) == 0 else True)
            self.menu.add_item( item )
            
            self.menu.add_item( sep( 'sep1', ['delgrp'] ) )
           
            item = smi( 'addcat', ['sep1'], _('Add new category'), \
                        callback=self.on_menu_add_category )
            self.menu.add_item( item )
            
            item = smi( 'remcat', ['addcat'], _('Remove category'), \
                        callback=self.on_menu_del_category,
                        condition_fn=lambda n,p,c: False if len(c['categories']) == 0 else True)
            self.menu.add_item( item )
            
            self.menu.add_item( sep( 'sep2', ['remcat'] ) )
            
        
        self.menu.add_item( GTShowTracksMenuItem( 'sel', ['sep2'] ) )
            
        item = smi( 'selcust', ['sel'], _('Show tracks with selected (custom)'), \
                    callback=lambda w,n,p,c: gt_common.create_custom_search_playlist( c['groups'], exaile ),
                    condition_fn=lambda n,p,c: True if len(c['groups']) > 1 else False)
        self.menu.add_item( item )
                    
        # TODO:
        # - Create smart playlist from selected
            
        
    def show_click_column(self):
        if len(self.get_columns()) == 1:
            self.insert_column( self.click_column, 0)
            
    def hide_click_column(self):
        if len(self.get_columns()) == 2:
            self.remove_column( self.click_column )
    
    
    def on_notify_model(self, object, property_spec):
        model = self.get_model()
        if model:
            model.connect( 'row-changed', self.on_row_changed )
            model.connect( 'row-deleted', self.on_row_deleted )

        # TODO: what's the best way to disconnect when it's unset or changed?
    
    def on_edit( self, cell, path, new_text ):
        if new_text != "":
            model = self.get_model()
            old = model.change_name(path, new_text)
            
            if model.is_category(path):
                self.emit( 'category-edited', old, new_text )
            else:
                self.emit( 'group-changed', GT_GROUP_EDITED, old )
                
        
    def on_row_changed(self, model, path, iter):
        if self.get_model() and not model.is_category(path):
            category = model.get_category(path)
            if category is not None:
                self.emit( 'category-changed', GT_CATEGORY_UPDATED, category )
                self.expand_row(model[path].parent.path, True)
        
    def on_row_collapsed( self, widget, iter, path ):
        self.emit( 'category-changed', GT_CATEGORY_COLLAPSED, self.get_model().get_category(path) )
    
    def on_row_deleted(self, model, path):
        if self.get_model() and not model.is_category(path):
            category = model.get_category(path)
            if category is not None:
                self.emit( 'category-changed', GT_CATEGORY_UPDATED, category )
    
    def on_row_expanded( self, widget, iter, path ):
        self.emit( 'category-changed', GT_CATEGORY_EXPANDED, self.get_model().get_category(path) )
            
            
    def on_toggle( self, cell, path ):
        self.get_model()[path][0] = not cell.get_active()
        self.emit( 'group-changed', GT_GROUP_EDITED, None )
        
    def on_menu_add_group( self, widget, name, parent, context):
        # TODO: instead of dialog, just add a new thing, make it editable?
        input = dialogs.TextEntryDialog( _('New tag value?'), _('Enter new tag value'))
        
        if input.run() == gtk.RESPONSE_OK:
            group = input.get_value()
            
            if group != "":    
                model, paths = context['selected-rows']
                
                categories = context['categories']
                if len(categories):
                    category = categories[0]
                else:
                    category = uncategorized
                    
                if model.add_group( group, category, True ):
                    self.emit( 'group-changed', GT_GROUP_ADDED, group )
                else:
                    self.emit( 'group-changed', GT_GROUP_EDITED, None )                
        
    def on_menu_delete_group( self, widget, name, parent, context ):
        '''Menu says delete something'''
        
        model, paths = context['selected-rows']
        groups = model.delete_selected_groups( paths )
        
        for group in groups:
            self.emit( 'group-changed', GT_GROUP_DELETED, group )
        
    def on_menu_add_category(self, widget, name, parent, context):
        # TODO: instead of dialog, just add a new thing, make it editable?
        input = dialogs.TextEntryDialog( _('New Category?'), _('Enter new group category name'))
        
        if input.run() == gtk.RESPONSE_OK:
            category = input.get_value()
            
            if category != "":
                model, paths = context['selected-rows']
                if model.add_category( category ):
                    self.emit( 'category-changed', GT_CATEGORY_ADDED, category )
    
    def on_menu_del_category(self, widget, name, parent, context):
        
        model, paths = context['selected-rows']
        categories = model.delete_selected_categories( paths )
        
        for category, groups in categories.iteritems():
            self.emit( 'category-changed', GT_CATEGORY_DELETED, category )
            for group in groups:
                self.emit( 'group-changed', GT_GROUP_DELETED, group )
        
        
    def get_selected_groups(self, selected_rows):
        model, rows = selected_rows
        return model.get_selected_groups( rows )
        
    def get_selected_categories(self, selected_rows):
        model, rows = selected_rows
        return model.get_selected_categories( rows )

    def on_mouse_release(self, widget, event):    
        if event.button == 3:
            self.menu.popup(None, None, None, event.button, event.time)
            return True
        return False
     
    def on_popup_menu(self, widget):
        self.menu.popup(None, None, None, None, None)
        return True
        
    def sync_expanded(self):
        '''Syncs the expansion state stored in the model to the tree'''
        
        self.handler_block( self._row_expanded_id )
        self.handler_block( self._row_collapsed_id )
        
        for row in self.get_model():
            if row[0]:
                self.expand_row(row.path, True)
                
        self.handler_unblock( self._row_expanded_id )
        self.handler_unblock( self._row_collapsed_id )
    

gobject.type_register(GroupTaggerView)
        
        
        
class GroupTaggerTreeStore(gtk.TreeStore, gtk.TreeDragSource, gtk.TreeDragDest):
    '''
        The tree model for grouptagger
    
        Rows for categories: 
            [expanded, category name, False]
        Rows for groups:
            [selected, group name, True]
    '''
    
    def __init__(self):
        gtk.TreeStore.__init__( self, gobject.TYPE_BOOLEAN, \
                                gobject.TYPE_STRING, \
                                gobject.TYPE_BOOLEAN)
        self.set_sort_column_id( 1, gtk.SORT_ASCENDING )
        
    def add_category(self, category):
        '''Returns True if added new category, False otherwise'''
        
        for row in self:
            if row[1] == category:
                return False
    
        self.append( None, [True, category, False] )
        return True
        
    def add_group(self, group, category=uncategorized, selected=True):
        '''Returns True if added new group, False otherwise'''

        for row in self:
            if row[1] == category:
                for chrow in row.iterchildren():
                    if chrow[1] == group:
                        row[0] = selected
                        return False
                
                self.append( row.iter, [selected, group, True] )
                return True
        
        # add new category
        it = self.append(  None, [True, category, False] )
        # add value to that category
        self.append( it, [selected, group, True] )
        return True
        
    def change_name(self, path, name):
        old = self[path][1]
        self[path][1] = name
        return old
        
    def delete_selected_categories(self, paths):
        
        categories = {}
        iters = [self.get_iter(path) for path in paths if self[path].parent is None]
        
        for i in iters:
            if i is not None:
                groups = []
                for ch in self[i].iterchildren():
                    groups.append( ch[1] )
                categories[ self.get_value(i, 1) ] = groups
                self.remove(i)
        
        return categories
    
        
    def delete_selected_groups(self, paths):
        '''Deletes selected groups, returns a list of the removed groups'''
        groups = []
        iters = [self.get_iter(path) for path in paths if self[path].parent is not None]
        
        for i in iters:
            if i is not None:
                groups.append( self.get_value(i, 1) )
                self.remove(i)
                
        return groups
        
    def get_category(self, path):
        '''Given a path, return the category associated with that path'''
        if len(path) == 1:
            if len(self):
                return self[path][1]
        else:
            return self[(path[0],)][1]
        
            
    def get_category_groups(self, category):
        return [row[1] for row in self.iter_category(category)]
        
    def get_selected_groups(self, paths):
        '''rows is obtained from get_selection().get_rows()'''
        return [self[path][1] for path in paths if self[path].parent is not None]    
        
    def get_selected_categories(self, paths):
        '''rows is obtained from get_selection().get_rows()'''
        return [self[path][1] for path in paths if self[path].parent is None]    
        
    def is_category(self, path):
        return len(path) == 1
        
    def iter_active(self):
        '''Iterate over all groups with the checkbox on'''
        for row in self.iter_group_rows():
            if row[0] == True:
                yield row[1]

    def iter_category(self, category):
        '''Iterate over all rows of a category'''
        for row in self:
            if category == row[1]:
                for chrow in row.iterchildren():
                    yield chrow
                break
                
    def iter_group_rows(self):
        '''Iterate over all groups in the model, yields (selected, group, other)'''
        for row in self:
            for chrow in row.iterchildren():
                yield chrow

    def iter_groups(self):
        '''Iterate over all groups in the model, yields each group'''
        for row in self.iter_group_rows():
            yield row[1]
                
    
        
    #def has_group(self, group):
    #    for row in self:
    #        for chrow in row:
    #            if row[1] == group:
    #                return True
    #    return False
    
    def load(self, group_categories):
        '''
            input format:
            
            { category: [expanded, [(active, group), ... ]], ... }
        '''
        for category, (expanded, groups) in group_categories.iteritems():
            cat = self.append( None, [expanded, category, False] )
            for active, group in groups:
                self.append( cat, [active, group, True] )
    
    #
    # DND interface
    #
    
    def do_row_draggable(self, path):
        '''Only groups are draggable'''
        return self[path].parent is not None
        
    def do_row_drop_possible(self, dest_path, selection_data):
        '''Can only drag to different categories'''
        model, src_path = selection_data.tree_get_row_drag_data()
        return len(dest_path) == 2 and src_path[0] != dest_path[0]
    
gobject.type_register(GroupTaggerTreeStore)


class GroupTaggerWidget(gtk.VBox):
    '''Melds the tag view with an 'add' button'''

    def __init__(self, exaile):
        gtk.VBox.__init__(self)
        
        self.title = gtk.Label()
        self.artist = gtk.Label()
        self.view = GroupTaggerView( exaile, GroupTaggerTreeStore(), editable=True )
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

    def add_groups(self, groups):
        
        added = False
        
        self.view.freeze_child_notify()
        self.view.set_model( None )
        
        for group in groups:
            added = self.store.add_group( group, uncategorized, selected=False ) or added
        
        self.view.set_model( self.store )
        self.view.sync_expanded()
        
        if added:
            self.view.emit( 'category-changed', GT_CATEGORY_UPDATED, uncategorized )
        
        self.view.thaw_child_notify()
            
    def set_categories(self, groups, group_categories):
        '''
            groups: iterable
            group_categories: dict: key is category, value is (visible, list of groups)
        '''
        
        defaults = {}
        set_groups = set()
        
        # validate it
        for category, (visible, cgroups) in group_categories.iteritems():
            dcgroups = []
            for group in cgroups:
                if group not in set_groups:
                    dcgroups.append( (group in groups, group) )
                    set_groups.add( group )
                    
            defaults[category] = (visible, dcgroups)
                
        groups = set(groups).difference( set_groups )        
        if len(groups):
            defaults[uncategorized] = (True, [(True, group) for group in groups])
        
        self.view.freeze_child_notify()
        self.view.set_model( None )
        
        self.store.clear()
        
        self.store.load( defaults )
        
        self.view.set_model( self.store )
        self.view.sync_expanded()
        
        self.view.thaw_child_notify()

        
class GroupTaggerPanel(gtk.VBox):
    '''A panel that has all of the functionality in it'''

    def __init__(self, exaile):
    
        gtk.VBox.__init__(self)
    
        # add the tagger widget
        self.tagger = GroupTaggerWidget( exaile )
        
        # add the widgets to this page
        self.pack_start( self.tagger, expand=True ) 
        
        # exaile panel interface
        self._child = self

        

class AllTagsListView(gtk.TreeView):
    def __init__(self, model=None):
        gtk.TreeView.__init__(self, model)
        
        self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        
        # Setup the first column
        cell = gtk.CellRendererToggle()
        cell.set_property('mode', gtk.CELL_RENDERER_MODE_ACTIVATABLE)
        cell.set_activatable(True)
        cell.connect('toggled', self.on_toggle)
        
        self.append_column(gtk.TreeViewColumn(None, cell, active=0))
        
        # Setup the second column
        self.append_column(gtk.TreeViewColumn(_('Group'), gtk.CellRendererText(), text=1))
        
        self.connect('key_press_event', self.on_key_press)
    
    def on_key_press(self, widget, event):
        if event.keyval == gtk.keysyms.space:
            model, paths = self.get_selection().get_selected_rows()
            
            sel = False
            for path in paths:
                sel = model[path][0] or sel
                
            for path in paths:
                model[path][0] = not sel
    
    def on_toggle(self, cell, path):
        self.get_model()[path][0] = not cell.get_active()
    
    
class AllTagsListStore(gtk.ListStore):
    def __init__(self):
        gtk.ListStore.__init__(self, gobject.TYPE_BOOLEAN, gobject.TYPE_STRING)
        self.set_sort_column_id(1, gtk.SORT_ASCENDING)
    
    def add_group(self, group):
        self.append((False, group))
    
    def get_active_groups(self):
        return [row[1] for row in self if row[0] == True]
    
    
class AllTagsDialog( gtk.Window ):

    def __init__(self, exaile, callback):
    
        gtk.Window.__init__(self)
        self.set_title(_('Get all tags from collection'))
        self.set_resizable(True)
        self.set_size_request( 150, 400 ) 
        
        self.add(gtk.Frame())
        
        vbox = gtk.VBox()
        
        self._callback = callback
        
        self.model = AllTagsListStore()
        self.view = AllTagsListView()
        
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        scroll.add( self.view )
        scroll.hide()
        
        vbox.pack_start(scroll, True, True)
        
        button = gtk.Button(_('Add selected to choices'))
        button.connect('clicked', self.on_add_selected_to_choices)
        vbox.pack_end(button, False, False)
        
        self.child.add(vbox)
        
        # get the collection groups
        groups = gt_common.get_all_collection_groups(exaile.collection)
        for group in groups:
            self.model.add_group(group)
            
        self.view.set_model(self.model)
        self.show_all()
        
    def on_add_selected_to_choices(self, widget):
        self._callback(self.model.get_active_groups())


class GroupTaggerQueryDialog(gtk.Dialog):      
    '''
        Dialog used to allow the user to select the behavior of the query
        used to filter out tracks that match a particular characteristic
    '''
    
    def __init__(self, groups):
        
        gtk.Dialog.__init__(self, _('Show tracks with groups') )
        
        # setup combo box selections
        self.group_model = gtk.ListStore(gobject.TYPE_STRING)
        groups_set = gt_common.get_groups_from_categories()
        groups_set |= set(groups)
        
        for group in groups_set:
            self.group_model.append( [group] )
        
        self.combo_model = gtk.ListStore(gobject.TYPE_STRING)
        self.choices = [ _('Must have this tag [AND]'), _('May have this tag [OR]'), _('Must not have this tag [NOT]'), _('Ignored') ]
        for choice in self.choices:
            self.combo_model.append( [choice] )
        
        # setup table
        self.table = gtk.Table(rows=len(groups)+1, columns=2)
        
        self.table.attach(gtk.Label(_('Group')), 0, 1, 0, 1, ypadding=5)
        self.table.attach(gtk.Label(_('Selected Tracks')), 1, 2, 0, 1, ypadding=5)
        
        # TODO: Scrolled window
        self.combos = []
        
        # TODO: Add/remove groups to/from table
        
        for i,group in enumerate(sorted(groups)):
            
            # label
            gcombo = self._init_combo(self.group_model)
            gcombo.set_active(self._get_group_index(group))
            self.table.attach(gcombo, 0, 1, i+1, i+2, xpadding=3)
            
            # combo
            combo = self._init_combo(self.combo_model)
            combo.set_active(0)
            self.table.attach(combo, 1, 2, i+1, i+2)
            
            self.combos.append( (gcombo, combo) )
            
            
        self.vbox.pack_start(self.table)
        
        self.add_buttons(gtk.STOCK_OK, gtk.RESPONSE_OK, gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        self.show_all()

    def _init_combo(self, model):
        combo = gtk.ComboBox(model)
        cell = gtk.CellRendererText()
        combo.pack_start(cell, True)
        combo.add_attribute(cell, 'text', 0)
        return combo

    def _get_group_index(self, group):
        for i, row in enumerate(self.group_model): 
            if row[0] == group:
                return i
        return -1
            
        
    def get_search_params(self):
        '''Returns (name, search_string) from user selections'''
        
        and_p = [[], '']        # groups, name, re_string
        or_p = [[], '']
        not_p = [[], '']
        
        first = True
        name = 'Grouping: '
            
        # gather the data
        for gcombo, combo in self.combos:
            
            group = self.group_model[ gcombo.get_active() ][0]
            wsel = self.combo_model[ combo.get_active() ][0]

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

        return (name, regex)

 