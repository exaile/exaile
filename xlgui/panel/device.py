# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 2, or (at your option)
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

import threading
import gtk, gobject
from xl.nls import gettext as _
from xl import event

from xlgui import panel
from xlgui.panel.collection import CollectionPanel
from xlgui.panel.flatplaylist import FlatPlaylistPanel


class DeviceTransferThread(threading.Thread):
    def __init__(self, device, main, panel):
        threading.Thread.__init__(self)
        self.setDaemon(True)

        self.device = device
        self.main = main
        self.panel = panel

    def stop_thread(self):
        self.device.transfer.cancel()

    def thread_complete(self):
        """
            Called when the thread has finished normally
        """
        gobject.idle_add(self.panel.load_tree)

    def progress_update(self, type, transfer, progress):
        event.log_event('progress_update', self, progress)

    def run(self):
        """
            Runs the thread
        """
        event.add_callback(self.progress_update, 'track_transfer_progress',
            self.device.transfer)
        try:
            self.device.start_transfer()
        finally:
            event.remove_callback(self.progress_update, 'track_transfer_progress',
                self.device.transfer)

class ReceptiveCollectionPanel(CollectionPanel):
    def drag_data_received(self, widget, context, x, y, data, info, stamp):
        uris = data.get_uris()
        tracks, playlists = self.tree.get_drag_data(uris)
        tracks = [ t for t in tracks if not \
                self.collection.loc_is_member(t.get_loc()) ]

        self.add_tracks_func(tracks)

    def add_tracks_func(self, tracks):
        locs = [ t['__loc'] for t in tracks ]
        # FIXME:
        lib = self.collection.get_libraries()[0]

        # TODO: there should be a queue for ipod and such devices,
        # otherwise you'll have to write the database on every track add and
        # that won't be good
        # this _needs_ to be asynchronous
        for l in locs:
            lib.add(l)

class DevicePanel(panel.Panel):
    """
        generic panel for devices
    """
    __gsignals__ = {
        'append-items': (gobject.SIGNAL_RUN_LAST, None, (object,)),
        'queue-items': (gobject.SIGNAL_RUN_LAST, None, (object,)),
        'collection-tree-loaded': (gobject.SIGNAL_RUN_LAST, None, ()),
    }

    gladeinfo = ('device_panel.glade', 'DevicePanelWindow')

    def __init__(self, parent, main, 
        device, name=None):

        panel.Panel.__init__(self, name)
        self.device = device
        self.main = main

        self.notebook = self.xml.get_widget("device_notebook")

        self.collectionpanel = ReceptiveCollectionPanel(parent,
            collection=device.collection, name=name)
        self.collectionpanel.add_tracks_func = self.add_tracks_func

        self.collectionpanel.connect('append-items',
            lambda *e: self.emit('append-items', *e[1:]))
        self.collectionpanel.connect('queue-items',
            lambda *e: self.emit('queue-items', *e[1:]))
        self.collectionpanel.connect('collection-tree-loaded',
            lambda *e: self.emit('collection-tree-loaded'))

    def add_tracks_func(self, tracks):
        self.device.add_tracks(tracks)
        thread = DeviceTransferThread(self.device, self.main, self)
        self.main.controller.progress_manager.add_monitor(thread, 
                _("Transferring to %s...")%self.name, 'gtk-go-up')

    def get_panel(self):
        return self.collectionpanel.get_panel()

    def add_panel(self, child, name):
        label = gtk.Label(name)
        self.notebook.append_page(child, label)

    def load_tree(self, *args):
        self.collectionpanel.load_tree(*args)

class FlatPlaylistDevicePanel(panel.Panel):
    __gsignals__ = {
        'append-items': (gobject.SIGNAL_RUN_LAST, None, (object,)),
        'queue-items': (gobject.SIGNAL_RUN_LAST, None, (object,)),
    }

    gladeinfo = ('device_panel.glade', 'DevicePanelWindow')

    def __init__(self, parent, main, 
        device, name=None):

        panel.Panel.__init__(self, name)
        self.device = device

        self.notebook = self.xml.get_widget("device_notebook")

        self.fppanel = FlatPlaylistPanel(parent, name)

        self.fppanel.connect('append-items',
            lambda *e: self.emit('append-items', *e[1:]))
        self.fppanel.connect('queue-items',
            lambda *e: self.emit('queue-items', *e[1:]))

    def get_panel(self):
        return self.fppanel.get_panel()

    def add_panel(self, child, name):
        label = gtk.Label(name)
        self.notebook.append_page(child, label)

    def load_tree(self, *e):
        # TODO: handle *all* the playlists
        self.fppanel.set_playlist(
            self.device.get_playlists()[0])
