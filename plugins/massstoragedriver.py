#!/usr/bin/env python
# Copyright (C) 2006 Adam Olsen <arolsen@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from xl import media, library, xlmisc, db, common
import os, xl, gobject, gtk, shutil, os.path
import copy
import xl.plugins as plugins

PLUGIN_NAME = "Mass Storage Driver"
PLUGIN_AUTHORS = ['Adam Olsen <arolsen@gmail.com>']
PLUGIN_VERSION = '0.3.3'
PLUGIN_DESCRIPTION = r"""Mass Storage Driver for the Devices Panel"""
PLUGIN_ENABLED = False
PLUGIN_ICON = None

PLUGIN = None

def configure():
    """
        Shows the configuration dialog
    """
    exaile = APP
    dialog = plugins.PluginConfigDialog(exaile.window, PLUGIN_NAME)
    table = gtk.Table(1, 2)
    table.set_row_spacings(2)
    bottom = 0
    label = gtk.Label("Mount Point:      ")
    label.set_alignment(0.0, 0.5)

    table.attach(label, 0, 1, bottom, bottom + 1)

    location = exaile.settings.get_str("mount", plugin=plugins.name(__file__),
        default="/mnt/device")

    loc_entry = gtk.FileChooserButton("Location")
    loc_entry.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
    loc_entry.set_current_folder(location)
    table.attach(loc_entry, 1, 2, bottom, bottom + 1, gtk.SHRINK)

    save_loc = exaile.settings.get_str('save_loc',
        plugin=plugins.name(__file__), default='')

    bottom += 1
    label = gtk.Label("Transfer Save Location:")
    label.set_alignment(0.0, 0.5)
    table.attach(label, 0, 1, bottom, bottom + 1)

    save_entry = gtk.FileChooserButton("Save Directory")
    save_entry.set_action(gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER)
    save_entry.set_current_folder(save_loc)
    table.attach(save_entry, 1, 2, bottom, bottom + 1, gtk.SHRINK)

    dialog.child.pack_start(table)
    dialog.show_all()

    result = dialog.run()
    dialog.hide()
    if result == gtk.RESPONSE_OK:
        exaile.settings.set_str("mount", loc_entry.get_current_folder(),
            plugin=plugins.name(__file__))
        exaile.settings.set_str('save_loc', loc_entry.get_current_folder(),
            plugin=plugins.name(__file__))

class MassStorageTrack(media.Track):
    type = 'device'
    pass

class MassStorageDriver(plugins.DeviceDriver):
    name = "massstorage"

    def __init__(self):
        plugins.DeviceDriver.__init__(self)
        self.db = None
        self.exaile = APP
        self.dp = APP.device_panel
        self.stopped = False

    def check_transfer_items(self, items):
        self.save_loc = self.exaile.settings.get_str('save_loc', default='', 
            plugin=plugins.name(__file__))
        if not self.save_loc:
            common.error(APP.window, "You have not specified a directory "
                "to transfer your music in.  Please choose one in the "
                "configuration dialog")
            configure()
            return False

        return True

    def remove_tracks(self, tracks):
        for track in tracks:
            try:
                self.all.remove(tracks)
                os.remove(track.io_loc)
            except:
                xlmisc.log_exception()

    def put_item(self, item):
        (item, nothing) = (item.track, item.target)
        if self.find_dup(item): return
        loc = os.path.basename(item.io_loc)

        try:
            shutil.copy(item.io_loc, os.path.join(self.save_loc, loc))
        except:
            xlmisc.log_exception()

        item = copy.deepcopy(item)
        item.loc = os.path.join(self.save_loc, loc)
        self.all.append(item)

    def find_dup(self, song):
        items = ('artist', 'album', 'genre', 'title', 'year')
        for s in self.all:
            check = False
            for item in items:
                if getattr(s, item) != getattr(song, item):
                    check = True

            if check: continue
            return True
        return False

    def remove_tracks(self, tracks):
        """
            Removes tracks
        """
        for track in tracks:
            if track in self.all: self.all.remove(track)
            try:
                os.unlink(track.io_loc)
            except OSError:
                pass
            except:
                xlmisc.log_exception()

    @common.threaded
    def connect(self, panel):
        """
            Connects and scans the device
        """
        self.stopped = False

        self.mount = self.exaile.settings.get_str("mount",
            plugin=plugins.name(__file__), default="/mnt/device")
        self.all = library.TrackData()

        files = library.scan_dir(str(self.mount), exts=media.SUPPORTED_MEDIA)
        for i, loc in enumerate(files):
            if self.stopped:
                self.stopped = False
                return
            tr = library.read_track(None, self.all, loc,
                track_type=MassStorageTrack)
            if not tr: continue
            self.all.append(tr)

        print 'we have connected, and scanned %d files!' % len(files)
        gobject.idle_add(panel.on_connect_complete, self)

    def search_tracks(self, keyword):

        if keyword:
            check = []
            for track in self.all:
                for item in ('artist', 'album', 'title'):
                    attr = getattr(track, item)
                    if keyword.lower() in attr.lower():
                        check.append(track) 
        else:
            check = self.all
        new = [(a.artist, a.album, a.track, a.title, a) for a in check]
        new.sort()
        return library.TrackData([a[4] for a in new])

    def disconnect(self):
        self.stopped = True

def initialize():
    global PLUGIN

    PLUGIN = MassStorageDriver()
    APP.device_panel.add_driver(PLUGIN, PLUGIN_NAME)

    return True

def destroy():
    global PLUGIN

    if PLUGIN:
        APP.device_panel.remove_driver(PLUGIN)

    PLUGIN = None
