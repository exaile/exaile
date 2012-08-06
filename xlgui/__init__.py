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

__all__ = ['main', 'panel', 'playlist']

import glib
import gtk
import logging

gtk.gdk.threads_init()
gtk.gdk.threads_enter()

from xl import (
    common,
    player,
    settings,
    xdg
)
from xl.nls import gettext as _
from xlgui import guiutil

logger = logging.getLogger(__name__)

def mainloop():
    gtk.main()

def get_controller():
    return Main._main

class Main(object):
    """
        This is the main gui controller for exaile
    """
    _main = None
    def __init__(self, exaile):
        """
            Initializes the GUI

            @param exaile: The Exaile instance
        """
        from xlgui import icons, main, panel, tray, progress
        from xlgui.panel import collection, radio, playlists, files

        gtk.gdk.set_program_class("Exaile")

        self.exaile = exaile
        self.first_removed = False
        self.tray_icon = None
        self.panels = {}
        self.builder = gtk.Builder()
        self.builder.add_from_file(xdg.get_data_path('ui', 'main.ui'))
        self.progress_box = self.builder.get_object('progress_box')
        self.progress_manager = progress.ProgressManager(self.progress_box)

        for name in ('exaile', 'exaile-pause', 'exaile-play',
                     'folder-music', 'audio-x-generic',
                     'office-calendar', 'extension'):
            icons.MANAGER.add_icon_name_from_directory(name,
                xdg.get_data_path('images'))
        gtk.window_set_default_icon_name('exaile')

        for name in ('dynamic', 'repeat', 'shuffle'):
            icon_name = 'media-playlist-%s' % name
            icons.MANAGER.add_icon_name_from_directory(icon_name,
                xdg.get_data_path('images'))

        logger.info("Loading main window...")
        self.main = main.MainWindow(self, self.builder, exaile.collection)

        if self.exaile.options.StartMinimized:
            self.main.window.iconify()

        self.panel_notebook = self.builder.get_object('panel_notebook')
        self.play_toolbar = self.builder.get_object('play_toolbar')

        logger.info("Loading panels...")
        self.panels['collection'] = collection.CollectionPanel(self.main.window,
            exaile.collection, _show_collection_empty_message=True)
        self.panels['radio'] = radio.RadioPanel(self.main.window, exaile.collection,
            exaile.radio, exaile.stations)
        self.panels['playlists'] = playlists.PlaylistsPanel(self.main.window,
            exaile.playlists, exaile.smart_playlists, exaile.collection)
        self.panels['files'] = files.FilesPanel(self.main.window, exaile.collection)

        for panel in ('collection', 'radio', 'playlists', 'files'):
            self.add_panel(*self.panels[panel].get_panel())

        # add the device panels
        for device in self.exaile.devices.list_devices():
            if device.connected:
                self.add_device_panel(None, None, device)

        logger.info("Connecting panel events...")
        self.main._connect_panel_events()

        if settings.get_option('gui/use_tray', False):
            self.tray_icon = tray.TrayIcon(self.main)

        self.device_panels = {}

        from xl import event
        event.add_callback(self.add_device_panel, 'device_connected')
        event.add_callback(self.remove_device_panel, 'device_disconnected')
        event.add_callback(self.on_gui_loaded, 'gui_loaded')

        logger.info("Done loading main window...")
        Main._main = self

    def open_uris(self, uris, play=True):
        if len(uris) > 0:
            self.open_uri(uris[0], play=play)

        for uri in uris[1:]:
            self.open_uri(uri, play=False)

    def open_uri(self, uri, play=True):
        """
            Proxy for _open_uri
        """
        self._open_uri(uri, play)

    def _open_uri(self, uri, play=True):
        """
            Determines the type of a uri, imports it into a playlist, and
            starts playing it
        """
        from xl import playlist, trax

        if playlist.is_valid_playlist(uri):
            try:
                playlist = playlist.import_playlist(uri)
            except playlist.InvalidPlaylistTypeError:
                pass
            else:
                self.main.playlist_notebook.create_tab_from_playlist(playlist)

                if play:
                    player.QUEUE.current_playlist = playlist
                    player.QUEUE.current_playlist.current_position = 0
                    player.QUEUE.play(playlist[0])
        else:
            page = self.main.get_selected_page()
            column = page.view.get_sort_column()
            reverse = False
            sort_by = common.BASE_SORT_TAGS

            if column:
                reverse = column.get_sort_order() == gtk.SORT_DESCENDING
                sort_by = [column.name] + sort_by

            tracks = trax.get_tracks_from_uri(uri)
            tracks = trax.sort_tracks(sort_by, tracks, reverse=reverse)

            try:
                page.playlist.extend(tracks)
                page.playlist.current_position = len(page.playlist) - len(tracks)

                if play:
                    player.QUEUE.current_playlist = page.playlist
                    player.QUEUE.play(tracks[0])
            # Catch empty directories
            except IndexError:
                pass

    def show_cover_manager(self, *e):
        """
            Shows the cover manager
        """
        from xlgui.cover import CoverManager
        window = CoverManager(self.main.window,
            self.exaile.collection)

    def show_preferences(self):
        """
            Shows the preferences dialog
        """
        from xlgui.preferences import PreferencesDialog
        dialog = PreferencesDialog(self.main.window, self)
        dialog.run()

    def show_devices(self):
        from xlgui.devices import ManagerDialog
        dialog = ManagerDialog(self.main.window, self)
        dialog.run()

    def queue_manager(self, *e):
        self.main.playlist_notebook.show_queue()

    def collection_manager(self, *e):
        """
            Invokes the collection manager dialog
        """
        from xl.collection import Library
        from xlgui.collection import CollectionManagerDialog

        dialog = CollectionManagerDialog(self.main.window,
            self.exaile.collection)
        result = dialog.run()
        dialog.hide()

        if result == gtk.RESPONSE_APPLY:
            collection = self.exaile.collection
            collection.freeze_libraries()

            collection_libraries = [(l.location, l.monitored) \
                for l in collection.libraries.itervalues()]
            collection_libraries.sort()
            new_libraries = dialog.get_items()
            new_libraries.sort()

            if collection_libraries != new_libraries:
                collection_locations = [location \
                    for location, monitored in collection_libraries]
                new_locations = [location \
                    for location, monitored in new_libraries]

                if collection_locations != new_locations:
                    for location in new_locations:
                        if location not in collection_locations:
                            collection.add_library(Library(location))

                    removals = []

                    for location, library in collection.libraries.iteritems():
                        if location not in new_locations:
                            removals += [library]

                    map(collection.remove_library, removals)

                    self.on_rescan_collection()

                for location, monitored in new_libraries:
                    collection.libraries[location].monitored = monitored

            collection.thaw_libraries()

        dialog.destroy()

    def on_gui_loaded(self, event, object, nothing):
        """
            Allows plugins to be the last selected panel
        """
        try:
            last_selected_panel = settings.get_option(
                'gui/last_selected_panel', 'collection')
            panel = self.panels[last_selected_panel]._child
            panel_num = self.panel_notebook.page_num(panel)
            glib.idle_add(self.panel_notebook.set_current_page, panel_num)
            # Fix track info not displaying properly when resuming after a restart.
            self.main._update_track_information()
        except KeyError:
            pass

    def on_rescan_collection(self, *e):
        """
            Called when the user wishes to rescan the collection
        """
        libraries = self.exaile.collection.get_libraries()
        if not self.exaile.collection._scanning and len(libraries) > 0:
            from xl.collection import CollectionScanThread

            thread = CollectionScanThread(self.exaile.collection)
            thread.connect('done', self.on_rescan_done)
            self.progress_manager.add_monitor(thread,
                _("Scanning collection..."), gtk.STOCK_REFRESH)

    def on_rescan_done(self, thread):
        """
            Called when the rescan has finished
        """
        glib.idle_add(self.panels['collection'].load_tree)

    def on_randomize_playlist(self, *e):
        pl = self.main.get_selected_page()
        pl.playlist.randomize()

    def on_track_properties(self, *e):
        pl = self.main.get_selected_page()
        pl.view.show_properties_dialog()

    def add_panel(self, child, name):
        """
            Adds a panel to the panel notebook
        """
        label = gtk.Label(name)
        label.set_angle(90)
        self.panel_notebook.append_page(child, label)

    def remove_panel(self, child):
        for n in range(self.panel_notebook.get_n_pages()):
            if child == self.panel_notebook.get_nth_page(n):
                self.panel_notebook.remove_page(n)
                return
        raise ValueError("No such panel")

    def on_panel_switch(self, notebook, page, pagenum):
        """
            Saves the currently selected panel
        """
        if self.exaile.loading:
            return

        page = notebook.get_nth_page(pagenum)
        for i, panel in self.panels.items():
            if panel._child == page:
                settings.set_option('gui/last_selected_panel', i)
                return

    def quit(self):
        """
            Quits the gui, saving anything that needs to be saved
        """

        # save open tabs
        self.main.playlist_notebook.save_current_tabs()
        gtk.gdk.threads_leave()

    @guiutil.idle_add()
    def add_device_panel(self, type, obj, device):
        from xl.collection import CollectionScanThread
        from xlgui.panel.device import DevicePanel, FlatPlaylistDevicePanel
        import xlgui.panel

        paneltype = DevicePanel
        if hasattr(device, 'panel_type'):
            if device.panel_type == 'flatplaylist':
                paneltype = FlatPlaylistDevicePanel
            elif issubclass(device.panel_type, xlgui.panel.Panel):
                paneltype = device.panel_type

        panel = paneltype(self.main.window, self.main,
            device, device.get_name())

        sort = True
        panel.connect('append-items', lambda panel, items, play, sort=sort:
            self.main.on_append_items(items, play, sort=sort))
        panel.connect('queue-items', lambda panel, items, sort=sort:
            self.main.on_append_items(items, queue=True, sort=sort))
        panel.connect('replace-items', lambda panel, items, sort=sort:
            self.main.on_append_items(items, replace=True, sort=sort))

        self.device_panels[device.get_name()] = panel
        glib.idle_add(self.add_panel, *panel.get_panel())
        thread = CollectionScanThread(device.get_collection())
        thread.connect('done', panel.load_tree)
        self.progress_manager.add_monitor(thread,
            _("Scanning %s..." % device.name), gtk.STOCK_REFRESH)

    @guiutil.idle_add()
    def remove_device_panel(self, type, obj, device):
        try:
            self.remove_panel(
                    self.device_panels[device.get_name()].get_panel()[0])
        except ValueError:
            logger.debug("Couldn't remove panel for %s"%device.get_name())
        del self.device_panels[device.get_name()]

