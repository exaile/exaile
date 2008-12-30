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

from xl.nls import gettext as _
import gtk, gobject, urllib
from xl import xdg, common, track, trackdb
from xlgui import panel, guiutil, menu, playlist
from xl import xdg, common

TRACK_NUM = 300

class CollectionPanel(panel.Panel):
    """
        The collection panel
    """
    gladeinfo = ('collection_panel.glade', 'CollectionPanelWindow')
    orders = (
        ('artist', 'album', 'tracknumber', 'title'),
        ('album', 'tracknumber', 'title'),
        ('genre', 'artist', 'album', 'tracknumber', 'title'),
        ('genre', 'album', 'artist', 'tracknumber', 'title'),
        ('date', 'artist', 'album', 'tracknumber', 'title'),
        ('date', 'album', 'artist', 'tracknumber', 'title'),
        ('artist', 'date', 'album', 'tracknumber', 'title')
    )

    def __init__(self, controller, settings, collection):
        """
            Initializes the collection panel
        """
        panel.Panel.__init__(self, controller)
        self.rating_images = playlist.create_rating_images(64)

        self.collection = collection
        self.settings = settings
        self.use_alphabet = self.settings.get_option('gui/use_alphabet', True)
        self.filter = self.xml.get_widget('collection_search_entry')
        self.choice = self.xml.get_widget('collection_combo_box')

        self.start_count = 0
        self.keyword = ''
        self._setup_tree()
        self._setup_widgets()
        self._setup_images()
        self._connect_events()

        self.menu = menu.CollectionPanelMenu(self, controller.main)
        self.load_tree()

    def _setup_widgets(self):
        """
            Sets up the various widgets to be used in this panel
        """
        self.choice = self.xml.get_widget('collection_combo_box')
        active = self.settings.get_option('gui/collection_active_view', 0)
        self.choice.set_active(active)

        box = self.xml.get_widget('collection_search_box')
        self.filter = guiutil.SearchEntry()
        self.filter.connect('activate', self.on_search)
        box.pack_start(self.filter.entry, True, True)

    def _connect_events(self):
        """
            Uses signal_autoconnect to connect the various events
        """
        self.xml.signal_autoconnect({
            'on_collection_combo_box_changed': lambda *e: self.load_tree(),
            'on_refresh_button_clicked': lambda *e: self.load_tree()
        })

    def on_search(self, *e):
        """
            Searches tracks and reloads the tree
        """
        self.keyword = unicode(self.filter.get_text(), 'utf-8')
        self.start_count += 1
        self.load_tree()

    def _setup_images(self):
        """
            Sets up the various images that will be used in the tree
        """
        window = gtk.Window()
        self.artist_image = gtk.gdk.pixbuf_new_from_file(xdg.get_data_path("images/artist.png"))
        self.date_image = gtk.gdk.pixbuf_new_from_file(xdg.get_data_path('images/year.png'))
        self.album_image = window.render_icon('gtk-cdrom',
            gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.title_image = gtk.gdk.pixbuf_new_from_file(xdg.get_data_path('images/track.png'))
        self.genre_image = gtk.gdk.pixbuf_new_from_file(xdg.get_data_path('images/genre.png'))

    def drag_data_received(self, *e):
        """
            stubb
        """
        pass
    
    def drag_data_delete(self, *e):
        """
            stub
        """
        pass

    def drag_get_data(self, treeview, context, selection, target_id, etime):
        """
            Called when a drag source wants data for this drag operation
        """
        tracks = self.get_selected_tracks()
        for track in tracks:
            guiutil.DragTreeView.dragged_data[track.get_loc()] = track
        urls = self._get_urls_for(tracks)
        selection.set_uris(urls)

    def _get_urls_for(self, items):
        """
            Returns the items' URLs
        """
        return [urllib.quote(item.get_loc().encode(common.get_default_encoding()))
            for item in items]

    def _setup_tree(self):
        """
            Sets up the tree widget
        """
        self.tree = guiutil.DragTreeView(self)
        self.tree.set_headers_visible(False)
        container = self.xml.get_widget('CollectionPanel')
        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.add(self.tree)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        container.pack_start(scroll, True, True)
        container.show_all()

        selection = self.tree.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        pb = gtk.CellRendererPixbuf()
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn('Text')
        col.pack_start(pb, False)
        col.pack_start(cell, True)
        col.set_attributes(pb, pixbuf=0)
        col.set_attributes(cell, text=1)
        self.tree.append_column(col)

        self.tree.set_row_separator_func(
            lambda m, i: m.get_value(i, 1) is None)

        self.model = gtk.TreeStore(gtk.gdk.Pixbuf, str, str)
        self.model_blank = gtk.TreeStore(gtk.gdk.Pixbuf, str, str)

        self.tree.connect("row-expanded", self.on_expanded)

    def _find_tracks(self, iter):
        """
            finds tracks matching a given iter. returns a resultset.
        """
        search = " ".join(self.get_node_search_terms(iter))
        return self.collection.search(search) #, tracks=self.tracks) 
        
    def get_selected_tracks(self):
        """
            Finds all the selected tracks
        """

        selection = self.tree.get_selection()
        (model, paths) = selection.get_selected_rows()
        found = [] 
        for path in paths:
            iter = self.model.get_iter(path)
            newset = self._find_tracks(iter)
            found.append(newset)
    
        if not found: return None
        
        found = list(set(reduce(lambda x, y: list(x) + list(y), found)))
      
        return trackdb.sort_tracks(
            ('artist', 'date', 'album', 'discnumber', 'tracknumber'),
            found)

    #FIXME: this should probably be moved into the playlist part of the UI
    def append_to_playlist(self, item=None, event=None):
        """
            Adds items to the current playlist
        """
        add = self.get_selected_tracks()
        if not add: return

        pl = self.controller.main.get_selected_playlist()
        if pl:
            tracks = pl.playlist.get_tracks()
            found = []
            for track in add:
                if not track in tracks:
                    found.append(track)
            pl.playlist.add_tracks(found)


    def button_press(self, widget, event):
        """ 
            Called when the user clicks on the tree
        """
        selection = self.tree.get_selection()
        (x, y) = map(int, event.get_coords())
        path = self.tree.get_path_at_pos(x, y)
        if event.type == gtk.gdk._2BUTTON_PRESS:
            self.append_to_playlist()
            return False
        elif event.button == 3:
            selection = self.tree.get_selection()
            self.menu.popup(event)

    def on_expanded(self, tree, iter, path):
        if self.model.iter_n_children(iter) == 1 and \
            self.model.get_value(self.model.iter_children(iter), 1) == None:
            iter_sep = self.model.iter_children(iter)
            self.load_subtree(iter)
            self.model.remove(iter_sep)

    def get_node_keywords(self, parent):
        if not parent:
            return []
        if self.model.get_value(parent, 2):
            values = ["\a\a" + self.model.get_value(parent, 2)]
        else:
            values = [self.model.get_value(parent, 1)]
        iter = self.model.iter_parent(parent)
        newvals = self.get_node_keywords(iter)
        if values[0]:
            values = newvals + values
        else:
            values = newvals
        return values

    def get_node_search_terms(self, node):
        keywords = self.get_node_keywords(node)
        terms = []
        n = 0
        for field in self.order:
            if field == 'tracknumber':
                continue
            try:
                word = keywords[n]

                if word:
                    word = word#.replace("\"","\\\"")
                else:
                    n += 1
                    continue
                if word == _("Unknown"):
                    word = "__null__"

                if word.startswith('\a\a'): 
                    terms.append(word[2:])
                else:
                    terms.append("%s==\"%s\""%(field, word))
                n += 1
            except IndexError:
                break
        return terms

    def load_tree(self):
        self.current_start_count = self.start_count
        self.model.clear()
        self.tree.set_model(self.model_blank)

        self.root = None
        self.order = self.orders[self.choice.get_active()]

        # save the active view setting
        self.settings['gui/collection_active_view'] = self.choice.get_active()

        self.load_subtree(None)

        self.tree.set_model(self.model)
        self.controller.main.update_track_counts()

    def load_subtree(self, parent):
        if parent == None:
            depth = 0
        else:
            depth = self.model.iter_depth(parent) +1
        terms = self.get_node_search_terms(parent)
        if terms:
            search = " ".join(terms)
        else:
            search = ""
        if self.keyword.strip():
            search += " " + self.keyword
        try:
            if list(self.order).index("tracknumber") <= depth:
                depth += 1
        except ValueError:
            pass # tracknumber isnt in the list
        try:
            tag = self.order[depth]
            self.tracks = self.collection.search(search)
            values = self.collection.list_tag(tag, search, use_albumartist=False, sort=True)
        except IndexError:
            return # at the bottom of the tree
        try:
            image = getattr(self, "%s_image"%tag)
        except:
            image = None
        bottom = False
        if depth == len(self.order)-1:
            bottom = True

        unknown_items = []

        draw_seps = self.settings.get_option('gui/draw_separators', True)
        last_char = ''
        first = True
        for v in values:
            if not v:
                if depth == 0:
                    # if the value is unknown and this is the top level,
                    # append this item to the unknown list
                    unknown_items.append(v)
                    continue
                else:
                    v = _("Unknown")

            if depth == 0 and draw_seps:
                if not first:
                    check_val = v
                    if check_val.lower().startswith('the '):
                        check_val = check_val.replace('the ', '')
                    char = check_val.lower()[0]

                    # check to see if it's a number
                    if char.isdigit(): char = '0'

                    if char != last_char:
                        self.model.append(parent, [None, None, None])
                    last_char = char

            first = False
            iter = self.model.append(parent, [image, v, None])
            if not bottom:
                self.model.append(iter, [None, None, None])
            #self.load_subtree(iter, depth+1)

        # various
        if tag == 'artist':
            tracks = self.collection.search('! compilation==__null__')#,
                #tracks=self.tracks)
            if tracks:
                self.model.append(parent, [None, None, None])
                iter = self.model.append(parent, [image, _('Various Artists'), 
                    '! compilation==__null__'])
                self.model.append(iter, [None, None, None])

        if unknown_items:
            for v in unknown_items:
                if not v:
                    v = _('Unknown')
            iter = self.model.append(parent, [image, v, None])
            if not bottom:
                self.model.append(iter, [None, None, None])
