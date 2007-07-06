# Copyright (C) 2006 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 1, or (at your option)
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

import gtk, urllib, re, gobject
from xl import common, xlmisc, library
from gettext import gettext as _
import collection

class EmptyDriver(object):
    def __init__(self):
        self.all = library.TrackData()

    def search_tracks(self, *e):
        return self.all

    def disconnect(self):
        pass

    def connect(self, *e):
        pass

class DeviceTransferQueue(gtk.VBox):
    """ 
        Shows tracks that are waiting to be transferred to the iPod
    """
    def __init__(self, panel):
        """
            Initializes the queue
        """
        gtk.VBox.__init__(self)
        self.panel = panel
        self.set_border_width(0)
        self.set_spacing(3)
        self.set_size_request(-1, 250)
        self.songs = []
        self.transferring = False
        self.stopped = True

        label = gtk.Label(_("Transfer Queue"))
        label.set_alignment(0, .50)
        self.pack_start(label, False, True)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        view = gtk.TreeView()
        scroll.add(view)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        self.list = xlmisc.ListBox(view)
        self.pack_start(scroll, True, True)

        self.progress = gtk.ProgressBar()
        self.pack_start(self.progress, False, False)

        buttons = gtk.HBox()
        buttons.set_spacing(3)
        self.clear = gtk.Button()
        image = gtk.Image()
        image.set_from_stock('gtk-clear', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.clear.set_image(image)

        self.stop = gtk.Button()
        image = gtk.Image()
        image.set_from_stock('gtk-stop', gtk.ICON_SIZE_SMALL_TOOLBAR)
        self.stop.set_image(image)
        self.stop.connect('clicked', self.on_stop)

        self.transfer = gtk.Button(_("Transfer"))
        buttons.pack_end(self.transfer, False, False)
        buttons.pack_end(self.clear, False, False)
        buttons.pack_end(self.stop, False, False)
        self.clear.connect('clicked', self.on_clear)
        self.transfer.connect('clicked', self.start_transfer)

        self.pack_start(buttons, False, False)
        targets = [('text/uri-list', 0, 0)]
        self.list.list.drag_dest_set(gtk.DEST_DEFAULT_ALL, targets,
            gtk.gdk.ACTION_COPY)
        self.list.list.connect('drag_data_received', self.drag_data_received)

    def check_transfer(self):
        """
            Checks to see if a transfer is in progress, and if so, it throws
            an error
        """
        if self.transferring:
            common.error(self.panel.exaile.window, _('A transfer is in '
                'progress, please wait for it to stop before attempting '
                'to perform this operation.'))
            return False

        return True

    def on_stop(self, *e):
        """
            Stops the transfer
        """
        self.transferring = False
        self.stopped = True

    def on_clear(self, widget):
        """
            Clears the queue
        """
        if not self.check_transfer(): return
        self.panel.queue = None
        self.hide()
        self.destroy()

    @common.threaded
    def start_transfer(self, widget):
        """
            Runs the transfer
        """
        if self.transferring: return
        self.transferring = True
        self.stopped = False
        gobject.idle_add(self.panel.exaile.status.set_first, _("Starting "
            "transfer..."), 3000)
        items = self.list.rows[:]
        total = len(self.list.rows)
        self.panel.transferring = True
        driver = self.panel.driver
        count = 0
        while True:
            if self.stopped: return
            if not items: break
            item = items.pop()
            driver.put_item(item)
            per = float(count) / float(total)
            count += 1
            gobject.idle_add(self.update_progress, item, per)
            xlmisc.log("set percent to %s" % per)

        if self.stopped: return
        gobject.idle_add(self.progress.set_fraction, 1)
        gobject.idle_add(self.panel.exaile.status.set_first, _("Finishing"
            " transfer..."), 3000)
        gobject.idle_add(self.panel.transfer_done)
        self.transferring = False

    def update_progress(self, song, percent):
        """
            Updates the progress of the transfer
        """
        self.list.remove(song)
        self.progress.set_fraction(percent)

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        """ 
            Called when a track is dropped in the transfer queue
        """
        # just pass it on to the iPodPanel
        if not self.check_transfer(): return
        self.panel.drag_data_received(tv, context, x, y, selection, info,
            etime)

class DeviceDragItem(object):
    def __init__(self, track, target):
        self.track = track
        self.target = target

    def __str__(self):
        return str(self.track)

class DevicePanel(collection.CollectionPanel):
    """
        Collection panel that allows for different collection drivers
    """
    name = 'device'
    def __init__(self, exaile):
        collection.CollectionPanel.__init__(self, exaile)
        self.driver = None
        self.drivers = {}
        self.all = library.TrackData()
        self.tree = xlmisc.DragTreeView(self, True, True)
        self.tree.set_headers_visible(False)

        self.chooser = self.xml.get_widget('device_driver_chooser')
        self.track_count = self.xml.get_widget('device_track_count')
        self.connect_button = self.xml.get_widget('device_connect_button')
        self.connect_button.connect('clicked', self.change_driver)

        self.store = gtk.ListStore(str, object)
        cell = gtk.CellRendererText()
        self.chooser.pack_start(cell)
        self.chooser.add_attribute(cell, 'text', 0)
        self.chooser.set_model(self.store)

        container = self.xml.get_widget('%s_box' % self.name)

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.add(self.tree)
        scroll.set_shadow_type(gtk.SHADOW_IN)
        container.pack_start(scroll, True, True)
        container.reorder_child(scroll, 3)
        container.show_all()

        selection = self.tree.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        pb = gtk.CellRendererPixbuf()
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn('Text')
        col.pack_start(pb, False)
        col.pack_start(cell, True)
        col.set_attributes(pb, pixbuf=0)
        self.tree.append_column(col)
        col.set_cell_data_func(cell, self.track_data_func)
        self.update_drivers(True)
        self.transferring = False
        self.connected = False
        self.queue = None
        self.chooser.set_active(0)

    def done_loading_tree(self):
        """
            Called when the collection tree is done loading
        """
        if self.driver:
            if hasattr(self.driver, 'done_loading_tree'):
                self.driver.done_loading_tree()

    def show_device_panel_menu(self, widget, event, item):
        """
            Shows the device panel menu
        """
        if self.driver and hasattr(self.driver, 'get_menu'):
            menu = self.driver.get_menu(item, self.menu)
        else:
            menu = self.menu

        menu.popup(None, None, None, event.button, event.time)

    def remove_tracks(self, tracks):
        """ 
            Removes tracks from the current device
        """
        if not hasattr(self.driver, 'remove_tracks'):
            common.error(self.exaile.window, _("This device does "
                "not support removing tracks"))
            return

        self.driver.remove_tracks(tracks)

    def get_initial_root(self, model):
        if self.driver is not None and hasattr(self.driver, 
            'get_initial_root'):
            return getattr(self.driver, 'get_initial_root')(model)
        else:
            return None

    def drag_data_received(self, tv, context, x, y, selection, info, etime):
        self.tree.unset_rows_drag_dest()
        self.tree.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.tree.targets, 
            gtk.gdk.ACTION_COPY)
        if not self.connected:
            common.error(self.exaile.window, _("Not connected to any media"
                " device"))
            return
        path = self.tree.get_path_at_pos(x, y)

        target = None
        if path:
            iter = self.model.get_iter(path[0])
            target = self.model.get_value(iter, 1)

        loc = selection.get_uris()
        items = []
        for url in loc:
            url = urllib.unquote(url)
            m = re.search(r'^device_(\w+)://', url)
            if m:
                song = self.get_song(url)
            else:
                song = self.exaile.all_songs.for_path(url)

            if song:
                items.append(DeviceDragItem(song, target))

        if items:
            self.add_to_transfer_queue(items)

    def add_to_transfer_queue(self, items):
        """
            Adds to the device transfer queue
        """
        if hasattr(self.driver, 'check_transfer_items'):
            if not self.driver.check_transfer_items(items):
                return
        if not hasattr(self.driver, 'put_item'):
            common.error(self.exaile.window, _("The current device "
                " does not support transferring music."))
            return
        if self.transferring:
            common.error(self.exaile.window, _("There is a transfer "
                "currently in progress.  Please wait for it to "
                "finish"))
            return

        if not self.queue:
            self.queue_box = self.xml.get_widget('device_queue_box')
            self.queue = DeviceTransferQueue(self)
            self.queue_box.pack_start(self.queue, False, False)

        queue = self.queue.songs
        queue.extend(items)

        self.queue.list.set_rows(queue)
        if queue:
            self.queue.show_all()
        else:
            self.queue.hide()
            self.queue.destroy()
            self.queue = None

    def transfer_done(self):
        """
            called when the transfer is complete
        """
        if hasattr(self.driver, 'transfer_done'):
            self.driver.transfer_done()
        if self.queue:
            self.queue.hide()
            self.queue.destroy()
            self.queue = None
        self.transferring = None
        self.load_tree(True)

    def change_driver(self, button):
        """
            Changes the current driver
        """
        if self.driver and self.queue:
            if not self.queue.check_transfer():
                return
        if self.connected:
            self.driver.disconnect()
            self.driver = EmptyDriver()
            self.connected = False
            img = gtk.Image()
            img.set_from_stock('gtk-disconnect', gtk.ICON_SIZE_BUTTON)
            self.track_count.set_label(_("0 tracks"))
            self.load_tree(True)
            self.connect_button.set_image(img)
            return

        iter = self.chooser.get_active_iter()
        driver = self.store.get_value(iter, 1)
        if not isinstance(driver, EmptyDriver):
            self.connect(driver)
            img = gtk.Image()
            img.set_from_stock('gtk-connect', 
                gtk.ICON_SIZE_BUTTON)
            self.connect_button.set_image(img)

    def update_drivers(self, initial=False):
        """
            Updates the driver list
        """
        if not initial:
            self.exaile.show_device_panel(len(self.drivers) > 0)
        count = 1
        select = 0
        self.store.clear()
        self.store.append([_('None'), EmptyDriver()])

        for k, v in self.drivers.iteritems():
            if k == self.driver:
                select = count

            self.store.append([v, k])            

        if select > 0:
            self.chooser.disconnect(self.change_id)
            self.chooser.set_active(select)
            self.change_id = self.chooser.connect('changed', self.change_driver)
        else:
            self.chooser.set_active(0)

    def add_driver(self, driver, name):
        if not self.drivers.has_key(driver):
            self.drivers[driver] = name
        self.update_drivers()

    def remove_driver(self, driver):
        if self.drivers.has_key(driver):
            del self.drivers[driver]
        self.update_drivers()

    def connect(self, driver):
        self.track_count.set_label(_("Connecting..."))
        try:
            driver.connect(self)
        except:
            common.error(self.exaile.window, _("Error connecting to device"))
            xlmisc.log_exception()
            self.on_connect_complete(None)

    def on_error(self, error):
        """
            Called when there is an error in a device driver during connect
        """
        common.error(self.exaile.window, error)
        self.on_connect_complete(None)
        
    def on_connect_complete(self, driver):
        """ 
            Called when the connection is complete
        """
        self.driver = driver
        if not self.driver:
            self.driver = EmptyDriver()
            self.connected = False
            img = gtk.Image()
            img.set_from_stock('gtk-disconnect', gtk.ICON_SIZE_BUTTON)
            self.connect_button.set_image(img)
        else:
            self.connected = True
        self.track_count.set_label(_("%d tracks") % len(self.driver.all))

        self.load_tree()

    def search_tracks(self, keyword, all=None):
        if not self.driver: self.all = library.TrackData()
        else: self.all = self.driver.search_tracks(keyword)
        return self.all

    def get_driver_name(self):
        if not self.driver: return None
        return self.driver.name

    def get_song(self, loc):
        return self.all.for_path(loc.replace('device_%s://' % self.driver.name, ''))

    def load_tree(self, event=None):
        collection.CollectionPanel.load_tree(self, event)
        self.track_count.set_label(_("%d tracks") % len(self.driver.all))

