import json

from xl import event, settings
from xlgui.panel.collection import Order, DEFAULT_ORDERS

from . import cco_prefs


class CustomCollectionOrders:
    """
    Plugin adds user defined orders to the collection panel
    """

    collection_panel = None
    custom_orders = []
    default_orders_count = None

    def enable(self, exaile):
        """
        Called on startup of exaile
        """
        self.exaile = exaile
        event.add_callback(self._on_orders_update, 'cco_option_set')
        event.add_callback(self._on_active_order_update, 'gui_option_set')

    def _on_orders_update(self, event_name, event_source, option):
        if option != 'cco/orders':
            return
        self.populate_orders()

    def _on_active_order_update(self, event_name, event_source, option):
        """
        Called when 'gui/collection_active_view' is updated.
        """
        if option != 'gui/collection_active_view':
            return

        set = settings.get_option('gui/collection_active_view')
        if set > -1:
            # This is necessary because if on startup the last active view is not allready there
            # 'gui/collection_active_view' will be updated to -1
            settings.set_option('cco/collection_active_view', set)

    def disable(self, exaile):
        pass

    def on_gui_loaded(self):
        """
        Called when the gui is loaded
        Before that there is no collection panel
        """
        self.collection_panel = self.exaile.gui.panel_notebook.panels[
            'collection'
        ].panel
        self.default_orders_count = len(DEFAULT_ORDERS)
        self.populate_orders()

    def populate_orders(self):
        setting = settings.get_option('cco/orders', None)
        if setting is None:
            return

        for order in self.custom_orders:
            self.collection_panel.orders.remove(order)
        self.custom_orders = []

        orders = json.loads(setting)

        for order in orders:
            levels = order['levels'].split(',')
            display = order['display'].split(',')

            final_sorting = display
            final_display = '$' + ' - $'.join(display)

            final = [final_sorting, final_display, final_sorting]
            levels.append(final)
            lvls = tuple(levels)

            new_order = Order(order['name'], lvls)
            self.collection_panel.orders.append(new_order)
            self.custom_orders.append(new_order)

        orders_count = len(self.collection_panel.orders) - 1
        active = settings.get_option('cco/collection_active_view')
        if orders_count < active:
            # In case the last active order is deleted set to last existing order
            active = orders_count
        settings.set_option('gui/collection_active_view', active)
        self.collection_panel.repopulate_choices()

    def get_preferences_pane(self):
        return cco_prefs


plugin_class = CustomCollectionOrders
