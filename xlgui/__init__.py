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

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

import logging

logger = logging.getLogger(__name__)

import os
import sys

from xl import common, player, providers, settings, version, xdg
from xl.nls import gettext as _
from xlgui import guiutil

version.register(
    "GTK+", "%s.%s.%s" % (Gtk.MAJOR_VERSION, Gtk.MINOR_VERSION, Gtk.MICRO_VERSION)
)
version.register("GTK+ theme", Gtk.Settings.get_default().props.gtk_theme_name)


def get_controller():
    return Main._main


class Main:
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

        Gdk.set_program_class("Exaile")  # For GNOME Shell

        # https://www.freedesktop.org/wiki/Software/PulseAudio/Documentation/Developer/Clients/ApplicationProperties/
        GLib.set_application_name("Exaile")
        os.environ['PULSE_PROP_media.role'] = 'music'

        self.exaile = exaile
        self.first_removed = False
        self.tray_icon = None

        self.builder = Gtk.Builder()
        self.builder.add_from_file(xdg.get_data_path('ui', 'main.ui'))
        self.progress_box = self.builder.get_object('progress_box')
        self.progress_manager = progress.ProgressManager(self.progress_box)

        add_icon = icons.MANAGER.add_icon_name_from_directory
        images_dir = xdg.get_data_path('images')

        exaile_icon_path = add_icon('exaile', images_dir)
        Gtk.Window.set_default_icon_name('exaile')
        if xdg.local_hack:
            # PulseAudio also attaches the above name to streams. However, if
            # Exaile is not installed, any app trying to display the icon won't
            # be able to find it just by name. The following is a hack to tell
            # PA the icon file path instead of the name; this only works on
            # some clients, e.g. pavucontrol.
            os.environ['PULSE_PROP_application.icon_name'] = exaile_icon_path

        for name in (
            'exaile-pause',
            'exaile-play',
            'office-calendar',
            'extension',
            'music-library',
            'artist',
            'genre',
        ):
            add_icon(name, images_dir)
        for name in ('dynamic', 'repeat', 'shuffle'):
            add_icon('media-playlist-' + name, images_dir)

        logger.info("Loading main window...")
        self.main = main.MainWindow(self, self.builder, exaile.collection)

        if self.exaile.options.StartMinimized:
            self.main.window.iconify()

        self.play_toolbar = self.builder.get_object('play_toolbar')

        panel_notebook = self.builder.get_object('panel_notebook')
        self.panel_notebook = panels.PanelNotebook(exaile, self)

        self.device_panels = {}

        # add the device panels
        for device in self.exaile.devices.get_devices():
            if device.connected:
                self.add_device_panel(None, None, device)

        logger.info("Connecting panel events...")
        self.main._connect_panel_events()

        guiutil.gtk_widget_replace(panel_notebook, self.panel_notebook)
        self.panel_notebook.get_parent().child_set_property(
            self.panel_notebook, 'shrink', False
        )

        if settings.get_option('gui/use_tray', False):
            if tray.is_supported():
                self.tray_icon = tray.TrayIcon(self.main)
            else:
                settings.set_option('gui/use_tray', False)
                logger.warning(
                    "Tray icons are not supported on your platform. Disabling tray icon."
                )

        from xl import event

        event.add_ui_callback(self.add_device_panel, 'device_connected')
        event.add_ui_callback(self.remove_device_panel, 'device_disconnected')
        event.add_ui_callback(self.on_gui_loaded, 'gui_loaded')

        logger.info("Done loading main window...")
        Main._main = self

        if sys.platform == 'darwin':
            self._setup_osx()

    def open_uris(self, uris, play=True):
        if len(uris) > 0:
            self.open_uri(uris[0], play=play)

            for uri in uris[1:]:
                self.open_uri(uri, play=False)

    def open_uri(self, uri, play=True):
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
                reverse = column.get_sort_order() == Gtk.SortType.DESCENDING
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

        CoverManager(self.main.window, self.exaile.collection)

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

        dialog = CollectionManagerDialog(self.main.window, self.exaile.collection)
        result = dialog.run()
        dialog.hide()

        if result == Gtk.ResponseType.APPLY:
            collection = self.exaile.collection
            collection.freeze_libraries()

            collection_libraries = sorted(
                (l.location, l.monitored, l.startup_scan)
                for l in collection.libraries.values()
            )
            new_libraries = sorted(dialog.get_items())

            if collection_libraries != new_libraries:
                collection_locations = [
                    location
                    for location, monitored, startup_scan in collection_libraries
                ]
                new_locations = [
                    location for location, monitored, startup_scan in new_libraries
                ]

                if collection_locations != new_locations:
                    for location in new_locations:
                        if location not in collection_locations:
                            collection.add_library(Library(location))

                    removals = []

                    for location, library in collection.libraries.items():
                        if location not in new_locations:
                            removals.append(library)

                    for removal in removals:
                        collection.remove_library(removal)

                    self.on_rescan_collection()

                for location, monitored, startup_scan in new_libraries:
                    collection.libraries[location].monitored = monitored
                    collection.libraries[location].startup_scan = startup_scan

            collection.thaw_libraries()

        dialog.destroy()

    def on_gui_loaded(self, event, object, nothing):

        # This has to be idle_add so that plugin panels can be configured
        GLib.idle_add(self.panel_notebook.on_gui_loaded)

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

            thread = CollectionScanThread(
                self.exaile.collection, startup_scan=startup, force_update=force_update
            )
            thread.connect('done', self.on_rescan_done)
            self.progress_manager.add_monitor(
                thread, _("Scanning collection..."), 'drive-harddisk'
            )

    def on_rescan_done(self, thread):
        """
        Called when the rescan has finished
        """
        GLib.idle_add(self.get_panel('collection').load_tree)

    def on_track_properties(self, *e):
        pl = self.main.get_selected_page()
        pl.view.show_properties_dialog()

    def get_active_panel(self):
        """
        Returns the provider object associated with the currently shown
        panel in the sidebar. May return None.
        """
        return self.panel_notebook.get_active_panel()

    def focus_panel(self, panel_name):
        """
        Focuses on a panel in the sidebar
        """
        self.panel_notebook.focus_panel(panel_name)

    def get_panel(self, panel_name):
        """
        Returns the provider object associated with a panel in the sidebar
        """
        return self.panel_notebook.panels[panel_name].panel

    def quit(self):
        """
        Quits the gui, saving anything that needs to be saved
        """

        # save open tabs
        self.main.playlist_container.save_current_tabs()

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

        panel = paneltype(self.main.window, self.main, device, device.get_name())

        do_sort = True
        panel.connect(
            'append-items',
            lambda _panel, items, play: self.main.on_append_items(
                items, play, sort=do_sort
            ),
        )
        panel.connect(
            'queue-items',
            lambda _panel, items: self.main.on_append_items(
                items, queue=True, sort=do_sort
            ),
        )
        panel.connect(
            'replace-items',
            lambda _panel, items: self.main.on_append_items(
                items, replace=True, sort=do_sort
            ),
        )

        self.device_panels[device.get_name()] = panel
        GLib.idle_add(providers.register, 'main-panel', panel)
        thread = CollectionScanThread(device.get_collection())
        thread.connect('done', panel.load_tree)
        self.progress_manager.add_monitor(
            thread, _("Scanning %s..." % device.name), 'drive-harddisk'
        )

    def remove_device_panel(self, type, obj, device):
        try:
            providers.unregister('main-panel', self.device_panels[device.get_name()])
        except ValueError:
            logger.debug("Couldn't remove panel for %s", device.get_name())
        del self.device_panels[device.get_name()]

    def _setup_osx(self):
        """
        Copied from Quod Libet, GPL v2 or later
        """

        from AppKit import NSObject, NSApplication
        import objc

        try:
            import gi

            gi.require_version('GtkosxApplication', '1.0')
            from gi.repository import GtkosxApplication
        except (ValueError, ImportError):
            logger.warning("importing GtkosxApplication failed, no native menus")
        else:
            osx_app = GtkosxApplication.Application()
            # self.main.setup_osx(osx_app)
            osx_app.ready()

        shared_app = NSApplication.sharedApplication()
        gtk_delegate = shared_app.delegate()

        other_self = self

        # TODO
        # Instead of quitting when the main window gets closed just hide it.
        # If the dock icon gets clicked we get
        # applicationShouldHandleReopen_hasVisibleWindows_ and show everything.
        class Delegate(NSObject):
            @objc.signature('B@:#B')
            def applicationShouldHandleReopen_hasVisibleWindows_(self, ns_app, flag):
                logger.debug("osx: handle reopen")
                # TODO
                # app.present()
                return True

            def applicationShouldTerminate_(self, sender):
                logger.debug("osx: block termination")
                other_self.main.quit()
                return False

            def applicationDockMenu_(self, sender):
                return gtk_delegate.applicationDockMenu_(sender)

            # def application_openFile_(self, sender, filename):
            #    return app.window.open_file(filename.encode("utf-8"))

        delegate = Delegate.alloc().init()
        delegate.retain()
        shared_app.setDelegate_(delegate)

        # QL shouldn't exit on window close, EF should
        # if window.get_is_persistent():
        #    window.connect(
        #        "delete-event", lambda window, event: window.hide() or True)
