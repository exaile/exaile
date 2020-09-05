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
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

import re

from xl import common, settings
from xl.nls import gettext as _

from xlgui.widgets import dialogs, menu, notebook

from . import gt_common

#
# GroupTaggerView signal 'changed' enum
#

group_change = common.enum(
    added=object(), deleted=object(), edited=object()
)  # edited/toggled group

category_change = common.enum(
    added=object(),
    deleted=object(),
    expanded=object(),  # user expanded category display
    collapsed=object(),  # user collapsed category display
    updated=object(),
)  # added group, changed name

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
            display_name = _('Show tracks with all selected')

        menuitem = Gtk.MenuItem.new_with_mnemonic(display_name)
        menuitem.connect(
            'activate',
            lambda *e: gt_common.create_all_search_playlist(
                context['groups'], parent.exaile
            ),
        )
        return menuitem


class GroupTaggerContextMenu(menu.Menu):
    def __init__(self, tagger):
        menu.Menu.__init__(self, tagger)

    def get_context(self):
        return self._parent.get_context()


class GroupTaggerView(Gtk.TreeView):
    '''Treeview widget to display tag lists'''

    __gsignals__ = {
        'category-changed': (
            GObject.SignalFlags.ACTION,
            None,
            (GObject.TYPE_PYOBJECT, GObject.TYPE_STRING),
        ),
        'category-edited': (
            GObject.SignalFlags.ACTION,
            None,
            (GObject.TYPE_STRING, GObject.TYPE_STRING),
        ),
        'group-changed': (
            GObject.SignalFlags.ACTION,
            None,
            (GObject.TYPE_PYOBJECT, GObject.TYPE_STRING),
        ),
        'group-edited': (
            GObject.SignalFlags.ACTION,
            None,
            (GObject.TYPE_STRING, GObject.TYPE_STRING),
        ),
    }

    def __init__(self, exaile, model=None, editable=False):

        super(GroupTaggerView, self).__init__()

        self.exaile = exaile

        self.connect('notify::model', self.on_notify_model)

        self.set_model(model)
        self.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        self._row_expanded_id = self.connect('row-expanded', self.on_row_expanded)
        self._row_collapsed_id = self.connect('row-collapsed', self.on_row_collapsed)

        if editable:
            self.set_reorderable(True)

        # Setup the first column, not shown by default
        cell = Gtk.CellRendererToggle()
        cell.set_property('mode', Gtk.CellRendererMode.ACTIVATABLE)
        cell.set_activatable(True)
        cell.connect('toggled', self.on_toggle)

        self.click_column = Gtk.TreeViewColumn(None, cell, active=0, visible=2)

        # Setup the second column
        cell = Gtk.CellRendererText()
        cell.set_property('editable', editable)
        if editable:
            cell.connect('edited', self.on_edit)

        self.text_column = cell
        self.append_column(
            Gtk.TreeViewColumn(_('Tag'), self.text_column, text=1, weight=3)
        )

        #
        # Menu setup
        #

        self.menu = GroupTaggerContextMenu(self)
        smi = menu.simple_menu_item
        sep = menu.simple_separator

        self.connect('popup-menu', self.on_popup_menu)
        self.connect('button-press-event', self.on_button_press)

        if editable:

            item = smi('addgrp', [], _('Add new tag'), callback=self.on_menu_add_group)
            self.menu.add_item(item)

            item = smi(
                'delgrp',
                ['addgrp'],
                _('Delete tag'),
                callback=self.on_menu_delete_group,
                condition_fn=lambda n, p, c: False if len(c['groups']) == 0 else True,
            )
            self.menu.add_item(item)

            self.menu.add_item(sep('sep1', ['delgrp']))

            item = smi(
                'addcat',
                ['sep1'],
                _('Add new category'),
                callback=self.on_menu_add_category,
            )
            self.menu.add_item(item)

            item = smi(
                'remcat',
                ['addcat'],
                _('Remove category'),
                callback=self.on_menu_del_category,
                condition_fn=lambda n, p, c: False
                if len(c['categories']) == 0
                else True,
            )
            self.menu.add_item(item)

            self.menu.add_item(sep('sep2', ['remcat']))

        self.menu.add_item(GTShowTracksMenuItem('sel', ['sep2']))

        item = smi(
            'selcust',
            ['sel'],
            _('Show tracks with selected (custom)'),
            callback=lambda w, n, p, c: gt_common.create_custom_search_playlist(
                c['groups'], exaile
            ),
            condition_fn=lambda n, p, c: True if len(c['groups']) > 1 else False,
        )
        self.menu.add_item(item)

        # TODO:
        # - Create smart playlist from selected

    def set_model(self, model):
        super(GroupTaggerView, self).set_model(model)
        # this gets reset each time set_model is called... so we override
        self.set_search_column(1)

    def set_font(self, font):
        self.text_column.set_property('font-desc', font)
        model = self.get_model()
        self.set_model(None)
        self.set_model(model)
        self.sync_expanded()
        self.queue_draw()

    def get_context(self):
        '''Returns context parameter required by menus'''
        context = common.LazyDict(self)
        context[
            'selected-rows'
        ] = lambda name, parent: parent.get_selection().get_selected_rows()
        context['groups'] = lambda name, parent: parent.get_selected_groups(
            context['selected-rows']
        )
        context['categories'] = lambda name, parent: parent.get_selected_categories(
            context['selected-rows']
        )
        return context

    def show_click_column(self):
        if len(self.get_columns()) == 1:
            self.insert_column(self.click_column, 0)

    def hide_click_column(self):
        if len(self.get_columns()) == 2:
            self.remove_column(self.click_column)

    def on_notify_model(self, object, property_spec):
        model = self.get_model()
        if model:
            model.connect('row-changed', self.on_row_changed)
            model.connect('row-deleted', self.on_row_deleted)

        # TODO: what's the best way to disconnect when it's unset or changed?

    def on_edit(self, cell, path, new_text):
        if new_text != "":
            model = self.get_model()
            old = model.change_name(path, new_text)

            if model.is_category(path):
                self.emit('category-edited', old, new_text)
            else:
                self.emit('group-changed', group_change.edited, old)

    def on_row_changed(self, model, path, iter):
        if self.get_model() and not model.is_category(path):
            category = model.get_category(path)
            if category is not None:
                self.emit('category-changed', category_change.updated, category)
                self.expand_to_path(path)

    def on_row_collapsed(self, widget, iter, path):
        self.emit(
            'category-changed',
            category_change.collapsed,
            self.get_model().get_category(path),
        )

    def on_row_deleted(self, model, path):
        if self.get_model() and not model.is_category(path):
            category = model.get_category(path)
            if category is not None:
                self.emit('category-changed', category_change.updated, category)

    def on_row_expanded(self, widget, iter, path):
        self.emit(
            'category-changed',
            category_change.expanded,
            self.get_model().get_category(path),
        )

    def on_toggle(self, cell, path):
        self.get_model()[path][0] = not cell.get_active()
        self.emit('group-changed', group_change.edited, None)

    def on_menu_add_group(self, widget, name, parent, context):
        # TODO: instead of dialog, just add a new thing, make it editable?
        input = dialogs.TextEntryDialog(_('New tag value?'), _('Enter new tag value'))

        if input.run() == Gtk.ResponseType.OK:
            group = input.get_value()

            if group != "":
                model, paths = context['selected-rows']

                categories = context['categories']
                if len(categories):
                    category = categories[0]
                else:
                    category = uncategorized

                if model.add_group(group, category, True):
                    self.emit('group-changed', group_change.added, group)
                else:
                    self.emit('group-changed', group_change.edited, None)

                self.emit('category-changed', category_change.updated, category)

    def on_menu_delete_group(self, widget, name, parent, context):
        '''Menu says delete something'''

        model, paths = context['selected-rows']
        groups = model.delete_selected_groups(paths)

        for group in groups:
            self.emit('group-changed', group_change.deleted, group)

    def on_menu_add_category(self, widget, name, parent, context):
        # TODO: instead of dialog, just add a new thing, make it editable?
        input = dialogs.TextEntryDialog(
            _('New Category?'), _('Enter new category name')
        )

        if input.run() == Gtk.ResponseType.OK:
            category = input.get_value()

            if category != "":
                model, paths = context['selected-rows']
                if model.add_category(category):
                    self.emit('category-changed', category_change.added, category)

    def on_menu_del_category(self, widget, name, parent, context):

        model, paths = context['selected-rows']
        categories = model.delete_selected_categories(paths)

        for category, groups in categories.items():
            self.emit('category-changed', category_change.deleted, category)
            for group in groups:
                self.emit('group-changed', group_change.deleted, group)

    def get_selected_groups(self, selected_rows):
        model, rows = selected_rows
        return model.get_selected_groups(rows)

    def get_selected_categories(self, selected_rows):
        model, rows = selected_rows
        return model.get_selected_categories(rows)

    def on_button_press(self, widget, event):
        widget.do_button_press_event(widget, event)
        if event.triggers_context_menu():
            self.menu.popup(None, None, None, None, event.button, event.time)
        return True

    def on_popup_menu(self, widget):
        self.menu.popup(None, None, None, None, 0, 0)
        return True

    def sync_expanded(self):
        '''Syncs the expansion state stored in the model to the tree'''
        with self.handler_block(self._row_expanded_id):
            with self.handler_block(self._row_collapsed_id):
                for row in self.get_model():
                    if row[0]:
                        self.expand_row(row.path, True)


class GroupTaggerTreeStore(Gtk.TreeStore, Gtk.TreeDragSource, Gtk.TreeDragDest):
    """
    The tree model for grouptagger

    Rows for categories:
        [expanded, category name, False]
    Rows for groups:
        [selected, group name, True]
    """

    def __init__(self):
        super(GroupTaggerTreeStore, self).__init__(
            GObject.TYPE_BOOLEAN,
            GObject.TYPE_STRING,
            GObject.TYPE_BOOLEAN,
            GObject.TYPE_INT,
        )
        self.set_sort_column_id(1, Gtk.SortType.ASCENDING)

    def add_category(self, category):
        '''Returns True if added new category, False otherwise'''

        for row in self:
            if row[1] == category:
                return False

        self.append(None, [True, category, False, Pango.Weight.BOLD])
        return True

    def add_group(self, group, category=uncategorized, selected=True):
        '''Returns True if added new group, False otherwise'''

        for row in self:
            if row[1] == category:
                for chrow in row.iterchildren():
                    if chrow[1] == group:
                        row[0] = selected
                        return False

                self.append(row.iter, [selected, group, True, Pango.Weight.NORMAL])
                return True

        # add new category
        it = self.append(None, [True, category, False, Pango.Weight.BOLD])
        # add value to that category
        self.append(it, [selected, group, True, Pango.Weight.NORMAL])
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
                    groups.append(ch[1])
                categories[self.get_value(i, 1)] = groups
                self.remove(i)

        return categories

    def delete_selected_groups(self, paths):
        '''Deletes selected groups, returns a list of the removed groups'''
        groups = []
        iters = [self.get_iter(path) for path in paths if self[path].parent is not None]

        for i in iters:
            if i is not None:
                groups.append(self.get_value(i, 1))
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
            if row[0]:
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

    # def has_group(self, group):
    #    for row in self:
    #        for chrow in row:
    #            if row[1] == group:
    #                return True
    #    return False

    def load(self, group_categories):
        """
        input format:

        { category: [expanded, [(active, group), ... ]], ... }
        """
        for category, (expanded, groups) in group_categories.items():
            cat = self.append(None, [expanded, category, False, Pango.Weight.BOLD])
            for active, group in groups:
                self.append(cat, [active, group, True, Pango.Weight.NORMAL])

    #
    # DND interface
    #

    def do_row_draggable(self, path):
        '''Only groups are draggable'''
        return self[path].parent is not None

    def do_row_drop_possible(self, dest_path, selection_data):
        '''Can only drag to different categories'''
        _, _, src_path = Gtk.tree_get_row_drag_data(selection_data)
        return len(dest_path) == 2 and src_path[0] != dest_path[0]


class GroupTaggerWidget(Gtk.Box):
    '''Melds the tag view with an 'add' button'''

    def __init__(self, exaile):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)

        self.title = Gtk.Label()
        self.artist = Gtk.Label()
        self.view = GroupTaggerView(exaile, GroupTaggerTreeStore(), editable=True)
        self.store = self.view.get_model()

        self.tag_button = Gtk.Button(label=_('Add Tag'))
        self.tag_button.connect('clicked', self.on_add_tag_click)

        self.title.set_xalign(0)
        self.title.set_yalign(0.5)
        self.title.set_line_wrap(True)
        self.title.set_property('wrap-mode', Pango.WrapMode.WORD_CHAR)
        self.title.hide()

        self.artist.set_xalign(0)
        self.artist.set_yalign(0.5)
        self.artist.set_line_wrap(True)
        self.artist.set_property('wrap-mode', Pango.WrapMode.WORD_CHAR)
        self.artist.hide()

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.add(self.view)

        self.pack_start(self.title, False, True, 0)
        self.pack_start(self.artist, False, True, 0)
        self.pack_start(scroll, True, True, 0)
        self.pack_start(self.tag_button, False, True, 0)

    def on_add_tag_click(self, widget):
        self.view.on_menu_add_group(self.view, None, None, self.view.get_context())

    def set_font(self, font):
        self.view.set_font(font)

    def set_title(self, title):
        '''Sets the title for this widget. Hides title if title is None'''
        if title is None:
            self.title.hide()
        else:
            self.title.set_markup(
                '<big><b>' + GLib.markup_escape_text(title) + '</b></big>'
            )
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
            self.set_title(None)
            self.set_artist(None)
        else:
            self.set_title(track.get_tag_display('title'))
            self.set_artist(track.get_tag_display('artist'))

    def add_groups(self, groups):

        added = False

        self.view.freeze_child_notify()
        self.view.set_model(None)

        for group in groups:
            added = self.store.add_group(group, uncategorized, selected=False) or added

        self.view.set_model(self.store)
        self.view.sync_expanded()

        if added:
            self.view.emit('category-changed', category_change.updated, uncategorized)

        self.view.thaw_child_notify()

    def set_categories(self, groups, group_categories):
        """
        groups: iterable
        group_categories: dict: key is category, value is (visible, list of groups)
        """

        defaults = {}
        set_groups = set()  # this holds all groups that were found

        # validate it
        for category, (visible, cgroups) in group_categories.items():
            dcgroups = []
            for group in cgroups:
                if group not in set_groups:
                    dcgroups.append((group in groups, group))
                    set_groups.add(group)

            defaults[category] = (visible, dcgroups)

        # Add anything left over to uncategorized
        groups = set(groups).difference(set_groups)
        if len(groups):
            other = defaults.setdefault(uncategorized, (True, []))
            other[1].extend([(True, group) for group in groups])

        self.view.freeze_child_notify()
        self.view.set_model(None)

        self.store.clear()

        self.store.load(defaults)

        self.view.set_model(self.store)
        self.view.sync_expanded()

        self.view.thaw_child_notify()


class GroupTaggerPanel(notebook.NotebookPage):
    '''A panel that has all of the functionality in it'''

    menu_provider_name = 'panel-tab-context'

    def __init__(self, exaile):

        notebook.NotebookPage.__init__(self)

        # add the tagger widget
        self.tagger = GroupTaggerWidget(exaile)

        # add the widgets to this page
        self.pack_start(self.tagger, True, True, 0)

        self.name = 'grouptagger'

    def get_page_name(self):
        return _('GroupTagger')

    def get_panel(self):
        return self


class AllTagsListView(Gtk.TreeView):
    def __init__(self, model=None):
        Gtk.TreeView.__init__(self, model)

        self.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        # Setup the first column
        cell = Gtk.CellRendererToggle()
        cell.set_property('mode', Gtk.CellRendererMode.ACTIVATABLE)
        cell.set_activatable(True)
        cell.connect('toggled', self.on_toggle)

        self.append_column(Gtk.TreeViewColumn(None, cell, active=0))

        # Setup the second column
        self.append_column(
            Gtk.TreeViewColumn(_('Group'), Gtk.CellRendererText(), text=1)
        )

        self.connect('key_press_event', self.on_key_press)

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_space:
            model, paths = self.get_selection().get_selected_rows()

            sel = False
            for path in paths:
                sel = model[path][0] or sel

            for path in paths:
                model[path][0] = not sel

    def on_toggle(self, cell, path):
        self.get_model()[path][0] = not cell.get_active()


class AllTagsListStore(Gtk.ListStore):
    def __init__(self):
        Gtk.ListStore.__init__(self, GObject.TYPE_BOOLEAN, GObject.TYPE_STRING)
        self.set_sort_column_id(1, Gtk.SortType.ASCENDING)

    def add_group(self, group):
        self.append((False, group))

    def get_active_groups(self):
        return [row[1] for row in self if row[0]]


class AllTagsDialog(Gtk.Window):
    def __init__(self, exaile, callback):

        Gtk.Window.__init__(self)
        self.set_title(_('Get all tags from collection'))
        self.set_resizable(True)
        self.set_size_request(150, 400)

        self.add(Gtk.Frame())

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self._callback = callback

        self.model = AllTagsListStore()
        self.view = AllTagsListView()

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.add(self.view)
        scroll.hide()

        vbox.pack_start(scroll, True, True, 0)

        button = Gtk.Button(_('Add selected to choices'))
        button.connect('clicked', self.on_add_selected_to_choices)
        vbox.pack_end(button, False, False, 0)

        self.get_child().add(vbox)

        # get the collection groups
        groups = gt_common.get_all_collection_groups(exaile.collection)
        for group in groups:
            self.model.add_group(group)

        self.view.set_model(self.model)
        self.show_all()

    def on_add_selected_to_choices(self, widget):
        self._callback(self.model.get_active_groups())


class GroupTaggerQueryDialog(Gtk.Dialog):
    """
    Dialog used to allow the user to select the behavior of the query
    used to filter out tracks that match a particular characteristic
    """

    def __init__(self, groups):

        Gtk.Dialog.__init__(self, title=_('Show tracks with groups'))

        # setup combo box selections
        self.group_model = Gtk.ListStore(GObject.TYPE_STRING)
        groups_set = gt_common.get_groups_from_categories()
        groups_set |= set(groups)

        for group in groups_set:
            self.group_model.append([group])

        self.combo_model = Gtk.ListStore(GObject.TYPE_STRING)
        self.choices = [
            _('Must have this tag [AND]'),
            _('May have this tag [OR]'),
            _('Must not have this tag [NOT]'),
            _('Ignored'),
        ]
        for choice in self.choices:
            self.combo_model.append([choice])

        # setup table
        self.table = Gtk.Grid()

        self.table.attach(Gtk.Label(label=_('Group')), 0, 0, 1, 1)
        self.table.attach(Gtk.Label(label=_('Selected Tracks')), 1, 0, 1, 1)

        # TODO: Scrolled window
        self.combos = []

        # TODO: Add/remove groups to/from table

        for i, group in enumerate(sorted(groups)):

            # label
            gcombo = self._init_combo(self.group_model)
            gcombo.set_active(self._get_group_index(group))
            self.table.attach(gcombo, 0, i + 1, 1, 1)

            # combo
            combo = self._init_combo(self.combo_model)
            combo.set_active(0)
            self.table.attach(combo, 1, i + 1, 1, 1)

            self.combos.append((gcombo, combo))

        self.vbox.pack_start(self.table, True, True, 0)

        self.add_buttons(
            Gtk.STOCK_OK, Gtk.ResponseType.OK, Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL
        )
        self.show_all()

    def _init_combo(self, model):
        combo = Gtk.ComboBox.new_with_model(model)
        cell = Gtk.CellRendererText()
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

        and_p = [[], '']  # groups, name, re_string
        or_p = [[], '']
        not_p = [[], '']

        first = True
        tagname = settings.get_option(gt_common.tagname_option, 'grouping')
        name = '%s: ' % (tagname.title())

        # gather the data
        for gcombo, combo in self.combos:

            active_group = self.group_model[gcombo.get_active()][0]
            wsel = self.combo_model[combo.get_active()][0]

            if wsel == self.choices[0]:
                and_p[0].append(active_group)
            elif wsel == self.choices[1]:
                or_p[0].append(active_group)
            elif wsel == self.choices[2]:
                not_p[0].append(active_group)

        # create the AND conditions
        if len(and_p[0]):
            name += ' and '.join(and_p[0])
            first = False

            and_p[1] = ' '.join(
                [
                    '%s~"\\b%s\\b"' % (tagname, re.escape(group.replace(' ', '_')))
                    for group in and_p[0]
                ]
            )

        # create the NOT conditions
        if len(not_p[0]):
            if first:
                name += ' and not '.join(not_p[0])
            else:
                name += ' and ' + ' and '.join(['not ' + p for p in not_p[0]])
            first = False

            not_p[1] = ' ! %s~"%s"' % (
                tagname,
                '|'.join(
                    [
                        '\\b' + re.escape(group.replace(' ', '_')) + '\\b'
                        for group in not_p[0]
                    ]
                ),
            )

        # create the OR conditions
        if len(or_p[0]):
            if first:
                name += ' or '.join(or_p[0])
            elif len(or_p[0]) > 1:
                name += ' and (' + ' or '.join(or_p[0]) + ')'
            else:
                name += ' and ' + ' or '.join(or_p[0])

            or_p[1] = ' %s~"%s"' % (
                tagname,
                '|'.join(
                    [
                        '\\b' + re.escape(group.replace(' ', '_')) + '\\b'
                        for group in or_p[0]
                    ]
                ),
            )

        regex = (and_p[1] + or_p[1] + not_p[1]).strip()

        return (name, regex)


class GroupTaggerAddRemoveDialog(Gtk.Dialog):
    def __init__(self, add, tracks, exaile):

        self.add = add
        self.tracks = tracks

        if self.add:
            Gtk.Dialog.__init__(self, title=_("Add tags to all"))
        else:
            Gtk.Dialog.__init__(self, title=_("Remove tags from all"))

        self.add_buttons(Gtk.STOCK_APPLY, Gtk.ResponseType.APPLY)

        # add the tagger widget
        self.tagger = GroupTaggerWidget(exaile)
        self.tagger.set_artist(None)
        self.tagger.set_title(None)

        # add the widgets to this page
        box = self.get_content_area()
        box.pack_start(self.tagger, True, True, 0)

        self.tagger.view.show_click_column()
        self.show_all()

        # TODO: display the tracks being edited?

    def get_active(self):
        return list(self.tagger.view.get_model().iter_active())
