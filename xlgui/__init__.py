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

__all__ = ['main', 'panel', 'playlist']

import glib
import gtk
import logging

import sys

# This is needed for OpenBSD otherwise exaile freezes. However, some
# versions of glib on Win32 freeze if this is used. Go figure. 
if sys.platform != 'win32':
    gtk.gdk.threads_init()
    gtk.gdk.threads_enter()
    
if sys.platform == 'darwin':

    # When trying to load a font that doesn't exist, pango falls back to
    # 'Sans'. If that doesn't exist, it kills the program. Apparently, 
    # 'Sans' no longer exists as of osx 10.9, so we need to set the default
    # font to something more sensible else we crash.

    __settings = gtk.settings_get_default()
    __font_name = __settings.get_property('gtk-font-name')
    
    # font names that start with '.' aren't usable
    if __font_name.startswith('.'):
        __font_name = __font_name[1:]
    if ' DeskInterface ' in __font_name:
        __font_name = __font_name.replace(' DeskInterface ', ' ')
    if ' UI ' in __font_name:
        __font_name = __font_name.replace(' UI ', ' ')

    __settings.set_property('gtk-font-name', __font_name)

    __icon_theme = gtk.icon_theme_get_default()
    __icon_theme.append_search_path('/Library/Frameworks/GStreamer.framework/Versions/0.10/share/icons')

from xl import (
    common,
    player,
    providers,
    settings,
    xdg
)
from xl.nls import gettext as _
from xlgui import guiutil

logger = logging.getLogger(__name__)

def mainloop():
    from xl.externals.sigint import InterruptibleLoopContext
    
    with InterruptibleLoopContext(gtk.main_quit):
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
        from xlgui import icons, main, panels, tray, progress

        gtk.gdk.set_program_class("Exaile")

        self.exaile = exaile
        self.first_removed = False
        self.tray_icon = None
        
        self.builder = gtk.Builder()
        self.builder.add_from_file(xdg.get_data_path('ui', 'main.ui'))
        self.progress_box = self.builder.get_object('progress_box')
        self.progress_manager = progress.ProgressManager(self.progress_box)

        for name in ('exaile', 'exaile-pause', 'exaile-play',
                     'folder-music', 'audio-x-generic',
                     'office-calendar', 'extension',
                     'music-library', 'artist', 'genre'):
            icons.MANAGER.add_icon_name_from_directory(name,
                xdg.get_data_path('images'))
        gtk.window_set_default_icon_name('exaile')

        for name in ('dynamic', 'repeat', 'shuffle'):
            icon_name = 'media-playlist-%s' % name
            icons.MANAGER.add_icon_name_from_directory(icon_name,
                xdg.get_data_path('images'))
        
        logger.info("Using GTK+ %s" % '.'.join(map(str,gtk.gtk_version)))
        
        logger.info("Loading main window...")
        self.main = main.MainWindow(self, self.builder, exaile.collection)

        if self.exaile.options.StartMinimized:
            self.main.window.iconify()
        
        self.play_toolbar = self.builder.get_object('play_toolbar')

        panel_notebook = self.builder.get_object('panel_notebook')
        self.panel_notebook = panels.PanelNotebook(exaile, self)
        
        self.device_panels = {}

        # add the device panels
        for device in self.exaile.devices.list_devices():
            if device.connected:
                self.add_device_panel(None, None, device)
        
        logger.info("Connecting panel events...")
        self.main._connect_panel_events()
        
        guiutil.gtk_widget_replace(panel_notebook, 
                                   self.panel_notebook)

        if settings.get_option('gui/use_tray', False):
            self.tray_icon = tray.TrayIcon(self.main)
            
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
                self.main.playlist_container.create_tab_from_playlist(playlist)

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
        self.main.playlist_container.show_queue()

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

            collection_libraries = [(l.location, l.monitored, l.startup_scan) \
                for l in collection.libraries.itervalues()]
            collection_libraries.sort()
            new_libraries = dialog.get_items()
            new_libraries.sort()

            if collection_libraries != new_libraries:
                collection_locations = [location \
                    for location, monitored, startup_scan in collection_libraries]
                new_locations = [location \
                    for location, monitored, startup_scan in new_libraries]

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

                for location, monitored, startup_scan in new_libraries:
                    collection.libraries[location].monitored = monitored
                    collection.libraries[location].startup_scan = startup_scan

            collection.thaw_libraries()

        dialog.destroy()

    def on_gui_loaded(self, event, object, nothing):
        
        # This has to be idle_add so that plugin panels can be configured
        glib.idle_add(self.panel_notebook.on_gui_loaded)
        
        # Fix track info not displaying properly when resuming after a restart.
        self.main._update_track_information()

    def on_rescan_collection(self, *e):
        """
            Called when the user wishes to rescan the collection
        """
        self.rescan_collection_with_progress()
        
    def on_rescan_collection_forced(self, *e):
        """
            Called when the user wishes to rescan the collection slowly
        """
        self.rescan_collection_with_progress(force_update=True)
        
    def rescan_collection_with_progress(self, startup=False, force_update=False):
        
        libraries = self.exaile.collection.get_libraries()
        if not self.exaile.collection._scanning and len(libraries) > 0:
            from xl.collection import CollectionScanThread

            thread = CollectionScanThread(self.exaile.collection, startup_scan=startup,
                                          force_update=force_update)
            thread.connect('done', self.on_rescan_done)
            self.progress_manager.add_monitor(thread,
                _("Scanning collection..."), gtk.STOCK_REFRESH)

    def on_rescan_done(self, thread):
        """
            Called when the rescan has finished
        """
        glib.idle_add(self.get_panel('collection').load_tree)

    def on_track_properties(self, *e):
        pl = self.main.get_selected_page()
        pl.view.show_properties_dialog()
    
    def get_active_panel(self):
        '''
            Returns the provider object associated with the currently shown
            panel in the sidebar. May return None.
        '''
        return self.panel_notebook.get_active_panel()
    
    def focus_panel(self, panel_name):
        '''
            Focuses on a panel in the sidebar
        '''
        self.panel_notebook.focus_panel(panel_name)
        
    def get_panel(self, panel_name):
        '''
            Returns the provider object associated with a panel in the sidebar
        '''
        return self.panel_notebook.panels[panel_name].panel
    
    def quit(self):
        """
            Quits the gui, saving anything that needs to be saved
        """

        # save open tabs
        self.main.playlist_container.save_current_tabs()
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
        glib.idle_add(providers.register, 'main-panel', panel)
        thread = CollectionScanThread(device.get_collection())
        thread.connect('done', panel.load_tree)
        self.progress_manager.add_monitor(thread,
            _("Scanning %s..." % device.name), gtk.STOCK_REFRESH)

    @guiutil.idle_add()
    def remove_device_panel(self, type, obj, device):
        try:
            providers.unregister('main-panel',
                    self.device_panels[device.get_name()])
        except ValueError:
            logger.debug("Couldn't remove panel for %s"%device.get_name())
        del self.device_panels[device.get_name()]

