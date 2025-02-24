import os, json
from gi.repository import Gtk
from gi.repository import GLib

from xl.nls import gettext as _
from xl.metadata import tags
from xlgui.widgets import common, dialogs
from xl import settings

name = _('Custom Collections')
basedir = os.path.dirname(os.path.realpath(__file__))
ui = os.path.join(basedir, "cco_pane.ui")


def init(dialog, builder):
    prefs = eco_prefs(dialog, builder)


class eco_prefs:
    def __init__(self, dialog, builder):
        self.builder = builder
        self.parent = dialog.parent

        self.grid = self.builder.get_object('preferences_pane')
        self.model = self.builder.get_object('model')
        self.list = self.builder.get_object('orders_tree')

        self.list.connect("row-activated", self._on_row_activated)
        self.builder.connect_signals(self)

        name_column = builder.get_object('name_column')

        """Name column"""
        name_cellrenderer = Gtk.CellRendererText()
        name_column.pack_start(name_cellrenderer, True)
        name_column.add_attribute(name_cellrenderer, 'text', 0)

        """Edit button"""
        edit_cellrenderer = common.ClickableCellRendererPixbuf()
        edit_cellrenderer.props.icon_name = 'edit'
        edit_cellrenderer.props.xalign = 1
        edit_cellrenderer.props.width = 30
        edit_cellrenderer.connect('clicked', self._on_edit_cellrenderer_clicked)
        name_column.pack_start(edit_cellrenderer, False)

        """Trash can"""
        remove_cellrenderer = common.ClickableCellRendererPixbuf()
        remove_cellrenderer.props.icon_name = 'edit-delete'
        remove_cellrenderer.props.xalign = 1
        remove_cellrenderer.props.width = 30
        remove_cellrenderer.connect('clicked', self._on_remove_cellrenderer_clicked)
        name_column.pack_start(remove_cellrenderer, False)

        self.custom_orders = custom_orders()

        self._grid_refresh()

    def _on_button_add_clicked(self, w):
        self._order_edit(-1)

    def _grid_refresh(self):
        self.list.set_model(None)
        self.model.clear()

        i = 0
        for order in self.custom_orders:
            it = self.model.append(None, (order['name'], i))
            i += 1

        self.list.set_model(self.model)

    def _on_row_activated(self, model, path, iter):
        order_number = self.model[path][1]
        self._order_edit(order_number)

    def _on_edit_cellrenderer_clicked(self, cellrenderer, path: str):
        order_number = self.model[path][1]
        GLib.idle_add(self._order_edit, order_number)

    def _on_remove_cellrenderer_clicked(self, cellrenderer, path: str):
        order_number = self.model[path][1]
        GLib.idle_add(self._ask_for_delete_order, order_number)

    def _ask_for_delete_order(self, order_number: int):
        check = dialogs.yesno(self.parent, _('Really delete this order?'))
        if check != Gtk.ResponseType.YES:
            return
        del self.custom_orders[order_number]
        self._grid_refresh()

    def _order_edit(self, order_number):
        if order_number > -1:
            order = self.custom_orders[order_number]
        else:
            order = {'name': "", 'levels': '', 'display': ''}

        dialog = dialogs.MultiTextEntryDialog(
            self.parent, _("Add or edit custom order")
        )

        tag_data = tags.tag_data
        usable_tags = ''
        for k, v in tag_data.items():
            if v:
                usable_tags = (
                    usable_tags + v.tag_name + ' (' + v.translated_name + ')\n'
                )

        tree_level_hint = _(
            'Comma separated list of tags to use as nodes in the tree view. Right now it\'s not possible to use more than one tag per node.\n'
            'Every tag can be used.'
        )
        display_hint = _(
            'Comma separated list of the tags to use for displaying single tracks as leaves in the tree. Tags are joined with a hyphen.\n'
            'Every tag can be used.'
        )

        dialog.add_field(_("Name:"), order['name'], _('Name of your order'))
        dialog.add_field(_("Tree Levels:"), order['levels'], tree_level_hint)
        dialog.add_field(_("Display:"), order['display'], display_hint)

        result = dialog.run()
        dialog.hide()

        if result != Gtk.ResponseType.OK:
            return

        (name, levels, display) = dialog.get_values()

        order['name'] = name
        order['levels'] = levels
        order['display'] = display

        if order_number > -1:
            self.custom_orders[order_number] = order
        else:
            self.custom_orders.append(order)

        self._grid_refresh()


class custom_orders(list):
    settings_name = 'cco/orders'

    def __init__(self):
        super().__init__(self)
        setting = settings.get_option(self.settings_name, None)
        if setting is not None:
            orders = json.loads(setting)
            for order in orders:
                super().append(order)

    def append(self, entry):
        super().append(entry)
        js = json.dumps(self)
        settings.set_option(self.settings_name, js)

    def __delitem__(self, arg):
        super().__delitem__(arg)
        js = json.dumps(self)
        settings.set_option(self.settings_name, js)

    def __setitem__(self, index, entry):
        super().__setitem__(index, entry)
        js = json.dumps(self)
        settings.set_option(self.settings_name, js)
