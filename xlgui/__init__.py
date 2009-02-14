# this program is free software; you can redistribute it and/or modify
# it under the terms of the gnu general public license as published by
# the free software foundation; either version 3, or (at your option)
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

__all__ = ['main', 'panel', 'playlist']

from xl.nls import gettext as _
import gtk, gtk.glade, gobject, logging
from xl import xdg, common, event

from xlgui import guiutil, prefs, plugins, cover

gtk.window_set_default_icon_from_file(xdg.get_data_path("images/icon.png"))
logger = logging.getLogger(__name__)

def mainloop():
    gtk.main()

class Main(object):
    """
        This is the main gui controller for exaile
    """
    def __init__(self, exaile):
        """ 
            Initializes the GUI

            @param exaile: The Exaile instance
        """
        import xl.main as xlmain
        from xlgui import main, panel, tray, progress
        from xlgui.panel import collection, radio, playlists, files

        self.exaile = exaile
        self.first_removed = False
        self.xml = gtk.glade.XML(xdg.get_data_path("glade/main.glade"),
            'ExaileWindow', 'exaile')
        self.progress_box = self.xml.get_widget('progress_box')
        self.progress_manager = progress.ProgressManager(self.progress_box)

        self.main = main.MainWindow(self, self.xml, exaile.settings, 
            exaile.collection,
            exaile.player, exaile.queue, exaile.covers)
        self.panel_notebook = self.xml.get_widget('panel_notebook')
        self.play_toolbar = self.xml.get_widget('play_toolbar')
        self._connect_events()

        self.collection_panel = collection.CollectionPanel(self,
            exaile.settings, exaile.collection)
        self.radio_panel = radio.RadioPanel(self, exaile.settings, 
            exaile.collection, exaile.radio, exaile.stations)
        self.playlists_panel = playlists.PlaylistsPanel(self,
            exaile.playlists, exaile.smart_playlists, exaile.collection)
        self.files_panel = files.FilesPanel(self, exaile.settings,
            exaile.collection)

        if exaile.settings.get_option('gui/use_tray', False):
            self.tray_icon = tray.TrayIcon(self)
        else:
            self.tray_icon = False

        tray.connect_events(self, exaile.settings)

        self.main.window.show_all()

    def _connect_events(self):
        """
            Connects the various events to their handlers
        """
        self.xml.signal_autoconnect({
            'on_about_item_activate': self.show_about_dialog,
            'on_scan_collection_item_activate': self.on_rescan_collection,
            'on_collection_manager_item_activate': self.collection_manager,
            'on_preferences_item_activate': lambda *e: self.show_preferences(),
            'on_plugins_item_activate': self.show_plugins,
            'on_album_art_item_activate': self.show_cover_manager,
            'on_open_item_activate': self.open_dialog,
        })

    def open_dialog(self, *e):
        """
            Shows a dialog for opening playlists and tracks
        """
        dialog = gtk.FileChooserDialog(_("Choose a file to open"),
            self.main.window, buttons=(_('Open'), gtk.RESPONSE_OK, 
            _('Cancel'), gtk.RESPONSE_CANCEL))
        dialog.set_position(gtk.WIN_POS_CENTER_ON_PARENT)

        result = dialog.run()
        dialog.hide()
        if result == gtk.RESPONSE_OK:
            files = dialog.get_filenames()
            for file in files:
                self.open_uri(file, play=False)

    def open_uri(self, uri, play=True):
        """
            Proxy for _play_uri
        """
        if self.exaile.loading:
            event.add_callback(lambda a, b, c, uri=uri, play=play: 
                self._open_uri(uri, play), 
                'exaile_loaded')
        else:
            self._open_uri(uri, play)

    def _open_uri(self, uri, play=True):
        """
            Determines the type of a uri, imports it into a playlist, and
            starts playing it
        """
        from xl import playlist, track
        if playlist.is_valid_playlist(uri):
            pl = playlist.import_playlist(uri)
            self.main.add_playlist(pl)
            if play:
                self.exaile.queue.play()
        else:
            pl = self.main.get_selected_playlist()
            tr = track.Track(uri)
            pl.playlist.add(tr)
            if play:
                self.exaile.queue.play(tr)

    def show_cover_manager(self, *e):
        """
            Shows the cover manager
        """
        window = cover.CoverManager(self.main.window, self.exaile.covers,
            self.exaile.collection)

    def show_plugins(self, *e):
        """
            Shows the plugins dialog
        """
        dialog = plugins.PluginManager(self, self.main.window, 
            self.exaile.plugins)
        dialog.dialog.show_all()

    def show_preferences(self, plugin_page=None):
        """
            Shows the preferences dialog
        """
        dialog = prefs.PreferencesDialog(self.main.window, self,
            plugin_page=plugin_page)
        dialog.run()

    def collection_manager(self, *e):
        """
            Invokes the collection manager dialog
        """
        from xl import collection
        from xlgui import collection as guicol
        dialog = guicol.CollectionManagerDialog(self.main.window,
            self, self.exaile.collection)
        result = dialog.run()
        dialog.dialog.hide()
        if result == gtk.RESPONSE_APPLY:
            items = dialog.get_items()
            dialog.destroy()
            for item in items:
                if not item in self.exaile.collection.libraries.keys():
                    self.exaile.collection.add_library(collection.Library(item))

            remove = []
            for k, library in self.exaile.collection.libraries.iteritems():
                if not k in items:
                    remove.append(library)

            map(self.exaile.collection.remove_library, remove)

            self.on_rescan_collection()

    def on_rescan_collection(self, *e):
        """
            Called when the user wishes to rescan the collection
        """
        from xlgui import collection as guicol
        thread = guicol.CollectionScanThread(self, self.exaile.collection)
        self.progress_manager.add_monitor(thread,
            _("Scanning collection..."), 'gtk-refresh')

    def add_panel(self, child, name):
        """
            Adds a panel to the panel notebook
        """
        label = gtk.Label(name)
        label.set_angle(90)
        self.panel_notebook.append_page(child, label)

        if not self.first_removed:
            self.first_removed = True

            # the first tab in the panel is a stub that just stops libglade from
            # complaining
            self.panel_notebook.remove_page(0)

    def show_about_dialog(self, *e):
        """
            Displays the about dialog
        """
        import xl.main as xlmain
        xml = gtk.glade.XML(xdg.get_data_path('glade/about_dialog.glade'),
            'AboutDialog', 'exaile')
        dialog = xml.get_widget('AboutDialog')
        logo = gtk.gdk.pixbuf_new_from_file(
            xdg.get_data_path('images/exailelogo.png'))
        dialog.set_logo(logo)
        # HACK: GTK+ < 2.12 (2007-09-14) use set_name.
        try:
            dialog.set_program_name(_("Exaile"))
        except AttributeError:
            dialog.set_name(_("Exaile"))
        dialog.set_version("\n" + str(xlmain.__version__))
        dialog.set_transient_for(self.main.window)
        dialog.run()
        dialog.destroy()
        
    def quit(self):
        """
            Quits the gui, saving anything that needs to be saved
        """

        # save open tabs
        self.main.save_current_tabs()

@guiutil.gtkrun
def show_splash(show=True):
    """
        Show a splash screen

        @param show: [bool] show the splash screen
    """
    if not show: return
    image = gtk.Image()
    image.set_from_file(xdg.get_data_path("images/splash.png"))
    xml = gtk.glade.XML(xdg.get_data_path("glade/splash.glade"), 'SplashScreen', 'exaile')
    splash_screen = xml.get_widget('SplashScreen')
    box = xml.get_widget('splash_box')
    box.pack_start(image, True, True)
    splash_screen.set_transient_for(None)
    splash_screen.show_all()

    #ensure that the splash gets completely drawn before we move on
    while gtk.events_pending():
        gtk.main_iteration()

    return splash_screen
