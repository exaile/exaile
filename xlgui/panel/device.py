# Copyright (C) 2008-2010 Adam Olsen
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

from gi.repository import GObject
from gi.repository import Gtk

from xl import common, event
from xl.nls import gettext as _
from xlgui import panel
from xlgui.panel.collection import CollectionPanel
from xlgui.panel.flatplaylist import FlatPlaylistPanel


class DeviceTransferThread(common.ProgressThread):
    """
    Transfers tracks from devices
    """

    def __init__(self, device):
        common.ProgressThread.__init__(self)

        self.device = device

    def stop(self):
        """
        Stops the thread
        """
        self.device.transfer.cancel()
        common.ProgressThread.stop(self)

    def on_track_transfer_progress(self, type, transfer, progress):
        """
        Notifies about progress changes
        """
        if progress < 100:
            self.emit('progress-update', progress)
        else:
            self.emit('done')

    def run(self):
        """
        Runs the thread
        """
        event.add_ui_callback(
            self.on_track_transfer_progress,
            'track_transfer_progress',
            self.device.transfer,
        )
        try:
            self.device.start_transfer()
        finally:
            event.remove_callback(
                self.on_track_transfer_progress,
                'track_transfer_progress',
                self.device.transfer,
            )


class ReceptiveCollectionPanel(CollectionPanel):
    def drag_data_received(self, widget, context, x, y, data, info, stamp):
        uris = data.get_uris()
        tracks, playlists = self.tree.get_drag_data(uris)
        tracks = [
            t for t in tracks if not self.collection.loc_is_member(t.get_loc_for_io())
        ]

        self.add_tracks_func(tracks)

    def add_tracks_func(self, tracks):
        locs = [t['__loc'] for t in tracks]
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
        'append-items': (GObject.SignalFlags.RUN_LAST, None, (object, bool)),
        'replace-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'queue-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'collection-tree-loaded': (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    ui_info = ('device.ui', 'DevicePanel')

    def __init__(self, parent, main, device, name):

        label = device.get_name()
        panel.Panel.__init__(self, parent, name, label)
        self.device = device
        self.main = main

        self.notebook = self.builder.get_object("device_notebook")

        self.collectionpanel = ReceptiveCollectionPanel(
            parent, collection=device.collection, name=name, label=label
        )
        self.collectionpanel.add_tracks_func = self.add_tracks_func

        self.collectionpanel.connect(
            'append-items', lambda *e: self.emit('append-items', *e[1:])
        )
        self.collectionpanel.connect(
            'replace-items', lambda *e: self.emit('replace-items', *e[1:])
        )
        self.collectionpanel.connect(
            'queue-items', lambda *e: self.emit('queue-items', *e[1:])
        )
        self.collectionpanel.connect(
            'collection-tree-loaded', lambda *e: self.emit('collection-tree-loaded')
        )

    def add_tracks_func(self, tracks):
        self.device.add_tracks(tracks)
        thread = DeviceTransferThread(self.device)
        thread.connect('done', lambda *e: self.load_tree())
        self.main.controller.progress_manager.add_monitor(
            thread, _("Transferring to %s...") % self.name, 'drive-harddisk'
        )

    def get_panel(self):
        return self.collectionpanel.get_panel()

    def add_panel(self, child, name):
        label = Gtk.Label(label=name)
        self.notebook.append_page(child, label)

    def load_tree(self, *args):
        self.collectionpanel.load_tree(*args)


class FlatPlaylistDevicePanel(panel.Panel):
    __gsignals__ = {
        'append-items': (GObject.SignalFlags.RUN_LAST, None, (object, bool)),
        'replace-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
        'queue-items': (GObject.SignalFlags.RUN_LAST, None, (object,)),
    }

    ui_info = ('device.ui', 'DevicePanel')

    def __init__(self, parent, main, device, name):

        label = device.get_name()
        panel.Panel.__init__(self, parent, name, label)
        self.device = device
        self.main = main

        self.notebook = self.builder.get_object("device_notebook")

        self.fppanel = FlatPlaylistPanel(self, name, label)

        self.fppanel.connect(
            'append-items', lambda *e: self.emit('append-items', *e[1:])
        )
        self.fppanel.connect(
            'replace-items', lambda *e: self.emit('replace-items', *e[1:])
        )
        self.fppanel.connect('queue-items', lambda *e: self.emit('queue-items', *e[1:]))

    def get_panel(self):
        return self.fppanel.get_panel()

    def add_panel(self, child, name):
        label = Gtk.Label(label=name)
        self.notebook.append_page(child, label)

    def load_tree(self, *e):
        # TODO: handle *all* the playlists
        self.fppanel.set_playlist(self.device.get_playlists()[0])
