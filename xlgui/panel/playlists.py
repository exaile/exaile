# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 3, or (at your option)
# any later version.
#
# this program is distributed in the hope that it will be useful,
# but without any warranty; without even the implied warranty of
# merchantability or fitness for a particular purpose.  see the
# gnu general public license for more details.
#
# you should have received a copy of the gnu general public license
# along with this program; if not, write to the free software
# foundation, inc., 675 mass ave, cambridge, ma 02139, usa.

import gtk, urllib, os.path, time
from xlgui import panel, guiutil, xdg, commondialogs
from xlgui import menu, filtergui
from xl import playlist
from xlgui.filtergui import MultiEntryField, EntryField
from gettext import gettext as _

N_ = lambda x: x

class EntrySecondsField(MultiEntryField):
    def __init__(self):
        MultiEntryField.__init__(self, n=1,
            labels=(None, _('seconds')),
            widths=(50,))

class EntryAndEntryField(MultiEntryField):
    def __init__(self):
        MultiEntryField.__init__(self, n=2,
            # TRANSLATORS: Logical AND used for smart playlists
            labels=(None, _('and'), None),
            widths=(50, 50))

class EntryDaysField(MultiEntryField):
    def __init__(self):
        MultiEntryField.__init__(self, n=1,
            labels=(None, _('days')),
            widths=(50,))

DATE_FIELDS = (_('seconds'), _('minutes'), _('hours'), _('days'), _('weeks'))
class SpinDateField(filtergui.SpinButtonAndComboField):
    def __init__(self):
        filtergui.SpinButtonAndComboField.__init__(self, 
            DATE_FIELDS)

class SpinSecondsField(filtergui.SpinLabelField):
    def __init__(self):
        filtergui.SpinLabelField.__init__(self, 
            _('seconds'))

class SpinRating(filtergui.SpinLabelField):
    def __init__(self):
        filtergui.SpinLabelField.__init__(self, '',
            8, -8)

class SpinNothing(filtergui.SpinLabelField):
    def __init__(self):
        filtergui.SpinLabelField.__init__(self, '')

CRITERIA = [
    (N_('Artist'), [
        # TRANSLATORS: True if haystack is equal to needle
        (N_('is'), EntryField),
        # TRANSLATORS: True if haystack is not equal to needle
        (N_('is not'), EntryField),
        # TRANSLATORS: True if haystack contains needle
        (N_('contains'), EntryField),
        # TRANSLATORS: True if haystack does not contain needle
        (N_('does not contain'), EntryField)
    ]),
    (N_('Album'), [
        (N_('is'), EntryField),
        (N_('is not'), EntryField),
        (N_('contains'), EntryField),
        (N_('does not contain'), EntryField),
    ]),
    (N_('Genre'), [
        (N_('is'), EntryField),
        (N_('is not'), EntryField),
        (N_('contains'), EntryField),
        (N_('does not contain'), EntryField),
    ]),
    (N_('Rating'), [
        # TRANSLATORS: Example: rating >= 5
        (N_('at least'), SpinRating),
        # TRANSLATORS: Example: rating <= 3
        (N_('at most'), SpinRating),
    ]),
    (N_('Number of Plays'), [
        (N_('at least'), SpinNothing),
        (N_('at most'), SpinNothing),
    ]),
    (N_('Year'), [
        # TRANSLATORS: Example: year < 1999
        (N_('before'), EntryField),
        # TRANSLATORS: Example: year > 2002
        (N_('after'), EntryField),
        # TRANSLATORS: Example: 1980 <= year <= 1987
        (N_('between'), EntryAndEntryField),
    ]),
    (N_('Length'), [
        (N_('at least'), SpinSecondsField),
        (N_('at most'), SpinSecondsField),
    ]),
#    (N_('Date Added'), [
        # TRANSLATORS: Example: track has been added in the last 2 days
#        (N_('in the last'), (SpinDateField, 
#            lambda x, i: day_calc(x, i, 'time_added'))),
        # TRANSLATORS: Example: track has not been added in the last 5 hours
#        (N_('not in the last'), (SpinDateField, 
#            lambda x, i: day_calc(x, i, 'time_added', '<'))),
#        ]),
#    (N_('Last Played'), [
#        (N_('in the last'), (SpinDateField, 
#            lambda x, i: day_calc(x, i, 'last_played'))),
#        (N_('not in the last'), (SpinDateField, 
#            lambda x, i: day_calc(x, i, 'last_played', '<'))),
#        ]),
    (N_('Location'), [
        (N_('is'), EntryField),
        (N_('is not'), EntryField),
        (N_('contains'), EntryField),
        (N_('does not contain'), EntryField),
    ]),
]

_TRANS = {
    'is': '==',
    'is not': '!==',
    'contains': '=',
    'does not contain': '!=',
    'at least': '>=',
    'at most': '<=',
    'before': '<',
    'after': '>',
    'between': '><',
}

class TrackWrapper(object):
    def __init__(self, track, playlist):
        self.track = track
        self.playlist = playlist

    def __str__(self):
        text = self.track['title']

        if text: text = ' / '.join(text)
        if text and self.track['artist']:
            text += " - " + ' / '.join(self.track['artist'])
        
        if not text: return self.track.get_loc()
        return text

class BasePlaylistPanelMixin(object):
    """
        Base playlist tree object.  

        Used by the radio and playlists panels to display playlists
    """
    def __init__(self):
        """
            Initializes the mixin
        """
        self.playlist_nodes = {}
        self.track_image = gtk.gdk.pixbuf_new_from_file(
            xdg.get_data_path('images/track.png'))

    def remove_selected_playlist(self):
        """
            Removes the selected playlist from the UI
            and from the underlying manager
        """
        selected_playlist = self.get_selected_playlist(raw=True)
        if selected_playlist is not None:
            if isinstance(selected_playlist, playlist.SmartPlaylist):
                self.smart_manager.remove_playlist(
                    selected_playlist.get_name())
            else:
                self.playlist_manager.remove_playlist(
                    selected_playlist.get_name())
            #remove from UI
            selection = self.tree.get_selection()
            (model, iter) = selection.get_selected()
            self.model.remove(iter)
        
    def rename_selected_playlist(self, name):
        """
            Renames the selected playlist
            
            @param name: the new name
        """
        pl = self.get_selected_playlist()
        if pl is not None:
            old_name = pl.get_name()
            selection = self.tree.get_selection()
            (model, iter) = selection.get_selected()
            model.set_value(iter, 1, name)
            pl.set_name(name)
            model.set_value(iter, 2, pl)
            #Update the manager aswell
            self.playlist_manager.rename_playlist(old_name, name)
        
    def open_selected_playlist(self):
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        self.open_item(self.tree, model.get_path(iter), None)
        
    def get_selected_playlist(self, raw=False):
        """
            Retrieves the currently selected playlist in
            the playlists panel.  If a non-playlist is
            selected it returns None
            
            @return: the playlist
        """
        item = self.get_selected_item(raw=raw)
        if isinstance(item, (playlist.Playlist,
            playlist.SmartPlaylist)):
            return item 
        else:
            return None
    
    def get_selected_track(self):
        item = self.get_selected_item()
        if isinstance(item, TrackWrapper):
            return item.track
        else:
            return None
    
    def get_selected_item(self, raw=False):
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        item = model.get_value(iter, 2)
        # for smart playlists
        if isinstance(item, playlist.SmartPlaylist):
            if raw: return item
            return item.get_playlist(self.collection)
        elif isinstance(item, playlist.Playlist) :
            return item
        elif isinstance(item, TrackWrapper):
            return item
        else:
            return None
            
    def get_selected_tracks(self):
        """
            Used by the menu, just basically gets the selected
            playlist and returns the tracks in it
        """
        pl = self.get_selected_playlist()
        if pl is not None:
            return pl.get_tracks()
        else:
            return self.get_selected_track()

        return None

    def open_item(self, tree, path, col):
        """
            Called when the user double clicks on a playlist,
            also called when the user double clicks on a track beneath
            a playlist.  When they active a track it opens the playlist
            and starts playing that track
        """
        iter = self.model.get_iter(path)
        item = self.model.get_value(iter, 2)
        if item is not None:
            if isinstance(item, (playlist.Playlist,
                playlist.SmartPlaylist)):
                # for smart playlists
                if hasattr(item, 'get_playlist'):
                    item = item.get_playlist(self.collection)
                else:
                    #Get an up to date copy
                    item = self.playlist_manager.get_playlist(item.get_name())
        
                self.controller.main.add_playlist(item)
            else:
                #Its a track
                pl = self.playlist_manager.get_playlist(item.playlist.get_name())
                pl.set_current_pos(pl.index(item.track))
                self.controller.main.add_playlist(pl)
                self.controller.exaile.queue.play(item.track)
                pass

    def add_new_playlist(self, tracks = []):
        dialog = commondialogs.TextEntryDialog(
                _("Enter the name you want for your new playlist"),
                _("New Playlist"))
        result = dialog.run()
        if result == gtk.RESPONSE_OK:
            name = dialog.get_value()
            if not name == "":
                #Create the playlist from all of the tracks
                new_playlist = playlist.Playlist(name)
                new_playlist.add_tracks(tracks)
                self.playlist_nodes[new_playlist] = \
                    self.model.append(self.custom, [self.playlist_image, name,  
                    new_playlist])
                self.tree.expand_row(self.model.get_path(self.custom), False)
                self._load_playlist_nodes(new_playlist)
                # We are adding a completely new playlist with tracks so we save it
                self.playlist_manager.save_playlist(new_playlist)  

    def _load_playlist_nodes(self, playlist):
        """
            Loads the playlist tracks into the node for the specified playlist
        """
        if not playlist in self.playlist_nodes: return

        expanded = self.tree.row_expanded(
            self.model.get_path(self.playlist_nodes[playlist]))

        self._clear_node(self.playlist_nodes[playlist])
        tracks = playlist.ordered_tracks
        parent = self.playlist_nodes[playlist]
        for track in tracks:
            if not track: continue
            wrapper = TrackWrapper(track, playlist)
            ar = [self.track_image, str(wrapper), wrapper]
            self.model.append(parent, ar)

        if expanded:
            self.tree.expand_row(
                self.model.get_path(self.playlist_nodes[playlist]), False)

    def remove_selected_track(self):
        """
            Removes the selected track from its playlist
            and saves the playlist
        """
        selection = self.tree.get_selection()
        (model, iter) = selection.get_selected()
        track = model.get_value(iter, 2)
        if isinstance(track, TrackWrapper):
            track.playlist.remove(track.playlist.index(track.track))
            #Update the list
            self.model.remove(iter)
            #TODO do we save the playlist after this??
            self.playlist_manager.save_playlist(track.playlist, overwrite=True)

class PlaylistsPanel(panel.Panel, BasePlaylistPanelMixin):
    """
        The playlists panel
    """
    gladeinfo = ('playlists_panel.glade', 'PlaylistsPanelWindow')

    def __init__(self, controller, playlist_manager, 
        smart_manager, collection):
        """
            Intializes the playlists panel

            @param controller:  The main gui controller
            @param playlist_manager:  The playlist manager
        """
        panel.Panel.__init__(self, controller)
        BasePlaylistPanelMixin.__init__(self)
        self.playlist_manager = playlist_manager
        self.smart_manager = smart_manager
        self.collection = collection
        self.box = self.xml.get_widget('playlists_box')
        
        self.playlist_name_info = 500
        self.track_target = ("text/uri-list", 0, 0)
        self.playlist_target = ("playlist_name", gtk.TARGET_SAME_WIDGET, self.playlist_name_info)
        self.deny_targets = [('',0,0)]
        
        self.tree = guiutil.DragTreeView(self, True, True)
        self.tree.connect('row-activated', self.open_item)
        self.tree.set_headers_visible(False)
        self.tree.connect('drag-motion', self.drag_motion)
        self.tree.drag_source_set(
                gtk.gdk.BUTTON1_MASK, [self.track_target, self.playlist_target],
                gtk.gdk.ACTION_COPY|gtk.gdk.ACTION_MOVE)

        self.scroll = gtk.ScrolledWindow()
        self.scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.scroll.add(self.tree)
        self.scroll.set_shadow_type(gtk.SHADOW_IN)
        self.box.pack_start(self.scroll, True, True)
        self.box.show_all()

        pb = gtk.CellRendererPixbuf()
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn('Text')
        col.pack_start(pb, False)
        col.pack_start(cell, True)
        col.set_attributes(pb, pixbuf=0)
        col.set_attributes(cell, text=1)
        self.tree.append_column(col)
        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, str, object)
        self.tree.set_model(self.model)

        # icons
        self.open_folder = guiutil.get_icon('gnome-fs-directory-accept')
        self.playlist_image = gtk.gdk.pixbuf_new_from_file(
            xdg.get_data_path('images/playlist.png'))

        # menus
        self.playlist_menu = menu.PlaylistsPanelPlaylistMenu(self, controller.main)
        self.smart_menu = menu.PlaylistsPanelPlaylistMenu(self,
            controller.main, smart=True)
        self.default_menu = menu.PlaylistsPanelMenu(self)
        self.track_menu = menu.PlaylistsPanelTrackMenu(self)

        self._load_playlists()

    def _load_playlists(self):
        """
            Loads the currently saved playlists
        """
        self.smart = self.model.append(None, [self.open_folder, 
            _("Smart Playlists"), None])
        
        self.custom = self.model.append(None, [self.open_folder, 
            _("Custom Playlists"), None])

        for name in self.smart_manager.playlists:
            self.model.append(self.smart, [self.playlist_image, name, 
                self.smart_manager.get_playlist(name)])
           
        for name in self.playlist_manager.playlists:
            playlist = self.playlist_manager.get_playlist(name)
            self.playlist_nodes[playlist] = self.model.append(
                self.custom, [self.playlist_image, name, playlist])
            self._load_playlist_nodes(playlist)

        self.tree.expand_row(self.model.get_path(self.smart), False)
        self.tree.expand_row(self.model.get_path(self.custom), False)
        
    def update_playlist_node(self, pl):
        """
            Updates the playlist node of the playlist
            to reflect any changes in it (i.e. tracks
            being added to the playlist)
            
            @param pl: the playlist to be updated
        """
        playlists = self.playlist_nodes.keys()
        for playlist in playlists:
            if playlist.get_name() == pl.get_name():
                node = self.playlist_nodes[playlist]
                del self.playlist_nodes[playlist]
                self.playlist_nodes[pl] = node
                self._load_playlist_nodes(pl)

    def add_smart_playlist(self):
        """
            Adds a new smart playlist
        """
        dialog = filtergui.FilterDialog(_('Add Smart Playlist'),
            CRITERIA)

        dialog.set_transient_for(self.controller.main.window)
        result = dialog.run()
        dialog.hide()
        if result == gtk.RESPONSE_ACCEPT:
            name = dialog.get_name()
            matchany = dialog.get_match_any()
            limit = dialog.get_limit()
            state = dialog.get_state()
            random = dialog.get_random()

            if not name:
                commondialogs.error(self.controller.main.window, _("You did "
                    "not enter a name for your playlist"))
                return

            try:
                pl = self.smart_manager.get_playlist(name)
                commondialogs.error(self.controller.main.window, _("The "
                    "playlist name you specified already exists."))
                return
            except ValueError:
                pass # playlist didn't exist

            pl = playlist.SmartPlaylist(name, self.collection)
            pl.set_or_match(matchany)
            pl.set_return_limit(limit)
            pl.set_random_sort(random)

            for item in state:
                (field, op) = item[0]
                value = item[1]
                pl.add_param(field.lower(), _TRANS[op], value)

            self.smart_manager.save_playlist(pl)
            self.model.append(self.smart, [self.playlist_image, name, pl])

    def edit_selected_smart_playlist(self):
        """
            Shows a dialog for editing the currently selected smart playlist
        """
        _REV = {}
        for k, v in _TRANS.iteritems():
            _REV[v] = k

        pl = self.get_selected_playlist(raw=True)
        if not isinstance(pl, playlist.SmartPlaylist): return

        params = pl.search_params
        state = []

        for param in params:
            (field, op, value) = param
            field = field.capitalize()

            state.append(([field, _REV[op]], value))

        state.reverse()

        dialog = filtergui.FilterDialog(_('Edit Smart Playlist'),
            CRITERIA)

        dialog.set_transient_for(self.controller.main.window)
        dialog.set_name(pl.get_name())
        dialog.set_match_any(pl.get_or_match())
        dialog.set_limit(pl.get_return_limit())
        dialog.set_random(pl.get_random_sort())

        dialog.set_state(state)

        result = dialog.run()
        dialog.hide()

        if result == gtk.RESPONSE_ACCEPT:
            name = dialog.get_name()
            matchany = dialog.get_match_any()
            limit = dialog.get_limit()
            state = dialog.get_state()
            random = dialog.get_random()

            if not name:
                commondialogs.error(self.controller.main.window, _("You did "
                    "not enter a name for your playlist"))
                return

            if not name == pl.name:
                try:
                    pl = self.smart_manager.get_playlist(name)
                    commondialogs.error(self.controller.main.window, _("The "
                        "playlist name you specified already exists."))
                    return
                except ValueError:
                    pass # playlist didn't exist
          
            self.smart_manager.remove_playlist(pl.get_name())
            pl = playlist.SmartPlaylist(name, self.collection)
            pl.set_or_match(matchany)
            pl.set_return_limit(limit)
            pl.set_random_sort(random)

            for item in state:
                (field, op) = item[0]
                value = item[1]
                pl.add_param(field.lower(), _TRANS[op], value)

            self.smart_manager.save_playlist(pl)

            selection = self.tree.get_selection()
            (model, iter) = selection.get_selected()
            model.set_value(iter, 1, name)
            model.set_value(iter, 2, pl)

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """
            Called when someone drags some thing onto the playlist panel
        """
        if info == self.playlist_name_info:
            # We are being dragged a playlist so 
            # we have to reorder them
            playlist_name = selection.get_text()
            drag_source = self.get_selected_playlist()
            #verify names
            if drag_source is not None:
                if drag_source.get_name() == playlist_name:
                    drop_info = tv.get_dest_row_at_pos(x, y)
                    drag_source_iter = self.playlist_nodes[drag_source]
                    if drop_info:
                        path, position = drop_info
                        drop_target_iter = self.model.get_iter(path)
                        drop_target = self.model.get_value(drop_target_iter, 2)
                        if position == gtk.TREE_VIEW_DROP_BEFORE:
                            #Put the playlist before drop_target
                            self.model.move_before(drag_source_iter, drop_target_iter)
                            self.playlist_manager.move(playlist_name, drop_target.get_name(), after = False)
                        else:
                            #put the playlist after drop_target
                            self.model.move_after(drag_source_iter, drop_target_iter)
                            self.playlist_manager.move(playlist_name, drop_target.get_name(), after = True)
            #Even though we are doing a move we still don't
            #call the delete method because we take care
            #of it above by moving instead of inserting/deleting
            context.finish(True, False, etime)
        else:
            self._drag_data_received_uris(tv, context, x, y, selection, info, etime)
                    
    def _drag_data_received_uris(self, tv, context, x, y, selection, info, etime):
        """
            Called by drag_data_received when the user drags URIs onto us
        """
        locs = list(selection.get_uris())
        drop_info = tv.get_dest_row_at_pos(x, y)
        if drop_info:
            path, position = drop_info
            iter = self.model.get_iter(path)
            drop_target = self.model.get_value(iter, 2)
            

            # if the current item is a track, use the parent playlist
            insert_index = None
            if isinstance(drop_target, TrackWrapper):
                current_playlist = drop_target.playlist
                drop_target_index = current_playlist.index(drop_target.track)
                #Adjust insert position based on drop position
                if (position == gtk.TREE_VIEW_DROP_BEFORE or
                    position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
                    #By default adding tracks inserts it before so we do not
                    #have to modify the insert index
                    insert_index =drop_target_index
                else:
                    #If we want to go after we have to append 1
                    insert_index = drop_target_index + 1
            else:
                current_playlist = drop_target;
                
            #Since the playlist do not have very good support for
            #duplicate tracks we have to perform some trickery
            #to make this work properly in all cases
            try:
                remove_track_index = current_playlist.index(self.get_selected_track())
            except:
                remove_track_index = None
            if insert_index is not None and remove_track_index is not None:
                #Since remove_track_index will be removed before
                #the new track is inserted we have to offset the
                #insert index
                 if insert_index > remove_track_index:
                     insert_index = insert_index - 1
                
            #Delete the track before adding the other one
            #so we do not get duplicates
            #right now the playlist does not support
            #duplicate tracks very well
            if context.action == gtk.gdk.ACTION_MOVE:
                #On a move action the second True makes the
                # drag_data_delete function called
                context.finish(True, True, etime)
            else:
                context.finish(True, False, etime)
                
            # Add the tracks we found to the internal playlist
            #TODO have it pass in existing tracks?
            (tracks, playlists) = self.tree.get_drag_data(locs)
            current_playlist.add_tracks(tracks, insert_index, False)
                
            self._load_playlist_nodes(current_playlist)
            
            # Do we save in the case when a user drags a file onto a playlist in the playlist panel?
            # note that the playlist does not have to be open for this to happen
            self.playlist_manager.save_playlist(current_playlist, overwrite=True)
        else:
            # If the user dragged files prompt for a new playlist name
            # else if they dragged a playlist add the playlist
            
            #We don't want the tracks in the playlists to be added to the
            # master tracks list so we pass in False
            (tracks, playlists) = self.tree.get_drag_data(locs, False)
            #First see if they dragged any playlist files
            for new_playlist in playlists:
                self.playlist_nodes[new_playlist] = self.model.append(self.custom, 
                    [self.playlist_image, new_playlist.get_name(), 
                    new_playlist])
                self._load_playlist_nodes(new_playlist)

                # We are adding a completely new playlist with tracks so we save it
                self.playlist_manager.save_playlist(new_playlist, overwrite=True)
                    
            #After processing playlist proceed to ask the user for the 
            #name of the new playlist to add and add the tracks to it
            if len(tracks) > 0:
                self.add_new_playlist(tracks) 

    def drag_data_delete(self,  tv, context):
        """
            Called after a drag data operation is complete
            and we want to delete the source data
        """
        if context.drag_drop_succeeded():
            self.remove_selected_track()
                
    def drag_get_data(self, tv, context, selection_data, info, time):
        """
            Called when someone drags something from the playlist
        """
        #TODO based on info determine what we set in selection_data
        if info == self.playlist_name_info:
            pl = self.get_selected_playlist()
            if pl is not None:
                selection_data.set(gtk.gdk.SELECTION_TYPE_STRING, 8, pl.get_name())
        else:
            pl = self.get_selected_playlist()
            if pl is not None:
                tracks = pl.get_tracks()
            else:
                tracks = [self.get_selected_tracks()]
               
            if not tracks: return
    
            for track in tracks:
                guiutil.DragTreeView.dragged_data[track.get_loc()] = track
            
            urls = guiutil.get_urls_for(tracks)
            selection_data.set_uris(urls)
        
    def drag_motion(self, tv, context, x, y, time):
        """
            Sets the appropriate drag action based on what we are hovering over
            
            hovering over playlists causes the copy action to occur
            hovering over tracks within the same playlist causes the move 
                action to occur
            hovering over tracks within different playlist causes the move action
                to occur
                
            Called on the destination widget
        """
        #Reset any target to be default to moving tracks
        self.tree.enable_model_drag_dest([self.track_target],
            gtk.gdk.ACTION_DEFAULT)
        #Determine where the drag is coming from
        dragging_playlist = False
        if tv == self.tree:
            selected_playlist = self.get_selected_playlist()
            if selected_playlist is not None:
                dragging_playlist = True
        
        #Find out where they are dropping onto 
        drop_info = tv.get_dest_row_at_pos(x, y)
        if drop_info:
            path, position = drop_info
            iter = self.model.get_iter(path)
            drop_target = self.model.get_value(iter, 2)
            
            if isinstance(drop_target, playlist.Playlist):
                if dragging_playlist:
                    #If we drag onto  we copy, if we drag between we move
                    if position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE or \
                        position == gtk.TREE_VIEW_DROP_INTO_OR_AFTER:
                        context.drag_status(gtk.gdk.ACTION_COPY, time)
                    else:
                        context.drag_status(gtk.gdk.ACTION_MOVE, time)
                        #Change target as well
                        self.tree.enable_model_drag_dest([self.playlist_target],
                                                         gtk.gdk.ACTION_DEFAULT)
                else:
                    context.drag_status(gtk.gdk.ACTION_COPY, time)
            elif isinstance(drop_target, TrackWrapper):
                #We are dragging onto another track
                #make it a move operation if we are only dragging
                # tracks within our widget
                # We do a copy if we are draggin from another playlist
                if context.get_source_widget() == tv and dragging_playlist == False:
                    context.drag_status(gtk.gdk.ACTION_MOVE, time)
                else:
                    context.drag_status(gtk.gdk.ACTION_COPY, time)
            else:
                #Prevent drop operation by changing the targets
                self.tree.enable_model_drag_dest(self.deny_targets,
                                                 gtk.gdk.ACTION_DEFAULT)
                return False
            return True
        else: #No drop info
            if dragging_playlist:
                context.drag_status(gtk.gdk.ACTION_MOVE, time)
                #Change target as well
                self.tree.enable_model_drag_dest([self.playlist_target],
                                                     gtk.gdk.ACTION_DEFAULT)

    def export_selected_playlist(self, path):
        """
            Exports the selected playlist to path
            
            @path where we we want it to be saved, with a 
                valid extension we support
        """
        pl = self.get_selected_playlist()
        if pl is not None:
            playlist.export_playlist(pl, path)
        
    def button_press(self, button, event):
        """
            Called when a button is pressed, is responsible
            for showing the context menu
        """
        if event.button == 3:
            (path, position) = self.tree.get_dest_row_at_pos(int(event.x), int(event.y))
            iter = self.model.get_iter(path)
            pl = self.model.get_value(iter, 2)
            #Based on what is selected determines what
            #menu we will show
            if isinstance(pl, playlist.Playlist):
                self.playlist_menu.popup(event)
            elif isinstance(pl, playlist.SmartPlaylist):
                self.smart_menu.popup(event)
            elif isinstance(pl, TrackWrapper):
                self.track_menu.popup(event)
            else:
                self.default_menu.popup(event)

    def _clear_node(self, node):
        """
            Clears a node of all children
        """
        iter = self.model.iter_children(node)
        while True:
            if not iter: break
            self.model.remove(iter)
            iter = self.model.iter_children(node)
