# Copyright (C) 2008-2009 Adam Olsen 
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

# Here's where it all begins.....
#
# Holds the main Exaile class, whose instantiation starts up the entiriety 
# of Exaile and which also handles Exaile shutdown.
#
# Also takes care of parsing commandline options.

__version__ = '0.2.99.3+'

import locale, gettext

# set the locale to LANG, or the user's default
locale.setlocale(locale.LC_ALL, '')

# this installs _ into python's global namespace, so we don't have to
# explicitly import it elsewhere
#TODO: make this work
#gettext.install("exaile")

from xl.nls import gettext as _

from xl import common, xdg, event
import os, sys, logging, logging.handlers, time

# initiate the logger. logger params are set later
logger = logging.getLogger(__name__)

class Exaile(object):
    _exaile = None
    
    def __init__(self):
        """
            Initializes Exaile.
        """
        self.quitting = False
        self.loading = True
        (self.options, self.args) = self.get_options().parse_args()
        if self.options.ShowVersion:
            self.version()

        if self.options.UseDataDir:
            xdg.data_dirs.insert(1, self.options.UseDataDir)

        if self.options.DebugEvent:
            event.EVENT_MANAGER.use_logger = True

        #set up logging
        self.setup_logging()

        #initial mainloop setup. The actual loop is started later, if necessary
        self.mainloop_init()
        
        #initialize DbusManager
        if self.options.StartGui and self.options.Dbus:
            from xl import xldbus
            if xldbus.check_exit(self.options, self.args):
                sys.exit(0)
            self.dbus = xldbus.DbusManager(self)
        
        #load the rest.
        self.__init()

        # On SIGTERM, quit normally.
        import signal
        signal.signal(signal.SIGTERM, (lambda sig, stack: self.quit()))

        #run the GUIs mainloop, if needed
        if self.options.StartGui:
            import xlgui
            xlgui.mainloop()

    def __init(self):
        """
            Initializes Exaile
        """
        logger.info(_("Loading Exaile %s...") % __version__)

        logger.info(_("Loading settings..."))
        try:
            from xl import settings
        except common.VersionError:
            common.log_exception(log=logger)
            exit(1)
        
        # Splash screen
        if self.options.StartGui:
            self.__show_splash()

        firstrun = settings.get_option("general/first_run", True)

        if firstrun:
            try:
                sys.path.insert(0, xdg.get_data_path("migrations"))
                import migration_200907100931 as migrator
                del sys.path[0]
                migrator.migrate()
                del migrator
            except:
                common.log_exception(log=logger, 
                        message=_("Failed to migrate from 0.2.14"))

        # Initialize plugin manager
        if not self.options.SafeMode:
            from xl import plugins
            logger.info(_("Loading plugins..."))
            self.plugins = plugins.PluginsManager(self)
        else:
            from xl import plugins
            logger.info(_("Safe mode enabled, not loading plugins."))
            self.plugins = plugins.PluginsManager(self, load=False)

        # Initialize the collection
        logger.info(_("Loading collection..."))
        from xl import collection
        try:
            self.collection = collection.Collection("Collection",
                    location=os.path.join(xdg.get_data_dirs()[0], 'music.db'))
        except common.VersionError:
            common.log_exception(log=logger)
            exit(1)

        # Set up the player and playback queue
        from xl import player
        from xl.player import queue
        self.player = player.get_player()()
        self.queue = player.queue.PlayQueue(self.player, 
                location=os.path.join(xdg.get_data_dirs()[0], 'queue.state') )
        event.log_event("player_loaded", self, None)

        # Initalize playlist manager
        from xl import playlist
        self.playlists = playlist.PlaylistManager()
        self.smart_playlists = playlist.PlaylistManager('smart_playlists',
            playlist.SmartPlaylist)
        if firstrun:
            self._add_default_playlists() 
        event.log_event("playlists_loaded", self, None)

        # Initialize dynamic playlist support
        from xl import dynamic
        self.dynamic = dynamic.DynamicManager(self.collection)

        # Initalize device manager
        logger.info(_("Loading devices..."))
        from xl import devices
        self.devices = devices.DeviceManager()
        event.log_event("device_manager_ready", self, None)

        # Initialize HAL
        if self.options.Hal:
            from xl import hal
            self.hal = hal.HAL(self.devices)
            self.hal.connect()
        else:
            self.hal = None

        # Cover manager
        from xl import cover
        self.covers = cover.CoverManager(
                cache_dir=os.path.join(xdg.get_data_dirs()[0], "covers"))

        # Radio Manager
        from xl import radio
        self.stations = playlist.PlaylistManager('radio_stations')
        self.radio = radio.RadioManager()

        # Initialize lyrics manager
        from xl import lyrics
        self.lyrics = lyrics.LyricsManager()

        self.gui = None
        # Setup GUI
        if self.options.StartGui:
            logger.info(_("Loading interface..."))

            import xlgui
            self.gui = xlgui.Main(self)
            if self.options.StartMinimized:
                self.gui.main.window.iconify()
            self.gui.main.window.show_all()

            import gobject
            if self.splash is not None:
                gobject.idle_add(self.splash.destroy)
            event.log_event("gui_loaded", self, None)

        self.queue._restore_player_state(
                os.path.join(xdg.get_data_dirs()[0], 'player.state') )

        if self.gui:
            # Find out if the user just passed in a list of songs
            # TODO: find a better place to put this
            # using arg[2:] because arg[1:] will include --startgui
            args = [ os.path.abspath(arg) for arg in self.args ]
            if len(args) > 0:
                self.gui.open_uri(args[0], play=True)
            for arg in args[1:]:
                self.gui.open_uri(arg)

        if firstrun:
            settings.set_option("general/first_run", False)

        self.loading = False
        Exaile._exaile = self
        event.log_event("exaile_loaded", self, None)

    def __show_splash(self):
        """
            Displays the splash screen
        """
        import xlgui
        from xl import settings
        self.splash = xlgui.show_splash(show=settings.get_option('gui/use_splash', True))

    def setup_logging(self):
        console_format = "%(levelname)-8s: %(message)s"
        loglevel = logging.INFO
        if self.options.Debug:
            loglevel = logging.DEBUG
            console_format += " (%(name)s)" # add module name in debug mode
        elif self.options.Quiet:
            loglevel = logging.WARNING
        # logfile level should always be INFO or higher
        if self.options.Quiet:
            logfilelevel = logging.INFO
        else:
            logfilelevel = loglevel

        # logging to terminal
        logging.basicConfig(level=loglevel, format=console_format)

        # logging to file. this also automatically rotates the logs
        logfile = logging.handlers.RotatingFileHandler(
                os.path.join(xdg.get_config_dir(), "exaile.log"),
                mode='a', backupCount=5)
        logfile.doRollover() # each session gets its own file
        logfile.setLevel(logfilelevel)
        formatter = logging.Formatter('%(asctime)s %(levelname)-8s: %(message)s (%(name)s)', 
            datefmt="%m-%d %H:%M")
        logfile.setFormatter(formatter)
        logging.getLogger("").addHandler(logfile)

    def get_options(self):
        """
            Get the options for exaile
        """
        from optparse import OptionParser
        usage = "Usage: %prog [option...|uri]"
        p = OptionParser(usage=usage)
        
        # Playback options
        p.add_option("-n", "--next", dest="Next", action="store_true",
            default=False, help=_("Play the next track"))
        p.add_option("-p", "--prev", dest="Prev", action="store_true",
            default=False,   help=_("Play the previous track"))
        p.add_option("-s", "--stop", dest="Stop", action="store_true",
            default=False, help=_("Stop playback"))
        p.add_option("-a", "--play", dest="Play", action="store_true",
            default=False, help=_("Play"))
        p.add_option("-t", "--play-pause", dest="PlayPause", 
            action="store_true", default=False, help=_("Toggle Play or Pause"))

        # Current song options
        p.add_option("-q", "--query", dest="Query", action="store_true",
            default=False, help=_("Query player"))
        p.add_option("--gui-query", dest="GuiQuery", action="store_true",
            default=False, help=_("Show a popup of the currently playing track"))
        p.add_option("--get-title", dest="GetTitle", action="store_true",
            default=False, help=_("Print the title of current track"))
        p.add_option("--get-album", dest="GetAlbum", action="store_true",
            default=False, help=_("Print the album of current track"))
        p.add_option("--get-artist", dest="GetArtist", action="store_true",
            default=False, help=_("Print the artist of current track"))
        p.add_option("--get-length", dest="GetLength", action="store_true",
            default=False, help=_("Print the length of current track"))
        p.add_option('--set-rating', dest="SetRating", action='store',
            type='int', metavar='RATING', help=_('Set rating for current song'))
        p.add_option('--get-rating', dest='GetRating', action='store_true',
            default=False, help=_('Get rating for current song'))
        p.add_option("--current-position", dest="CurrentPosition", 
            action="store_true", default=False, 
            help=_("Print the position inside the current track as a percentage"))

        # Volume options
        p.add_option("-i", "--increase-vol", dest="IncreaseVolume", action="store", 
            type="int", metavar="VOL", help=_("Increases the volume by VOL%"))
        p.add_option("-l", "--decrease-vol", dest="DecreaseVolume", action="store",
            type="int", metavar="VOL", help=_("Decreases the volume by VOL%"))
        p.add_option("--get-volume", dest="GetVolume", action="store_true",
            default=False, help=_("Print the current volume percentage"))

        # Other options
        p.add_option("--new", dest="NewInstance", action="store_true",
            default=False, help=_("Start new instance"))
        p.add_option("--version", dest="ShowVersion", action="store_true")
        p.add_option("--start-minimized", dest="StartMinimized", action="store_true",
            default=False, help=_("Start Exaile minimized to tray, if possible"))
        p.add_option("--safemode", dest="SafeMode", action="store_true",
            default=False, help=_("Start in safe mode - sometimes useful "
            "when you're running into problems"))

        # development and debug options
        p.add_option("--datadir", dest="UseDataDir", help=_("Set data directory"))
        p.add_option("--debug", dest="Debug", action="store_true",
            default=False, help=_("Show debugging output"))
        p.add_option("--eventdebug", dest="DebugEvent", 
            action="store_true", default=False, 
            help=_("Enable debugging of xl.event. Generates LOTS of output"))
        p.add_option("--quiet", dest="Quiet", action="store_true",
            default=False, help=_("Reduce level of output"))
        p.add_option('--startgui', dest='StartGui', action='store_true',
            default=False)
        p.add_option('--no-dbus', dest='Dbus', action='store_false',
            default=True, help=_("Disable D-Bus support"))
        p.add_option('--no-hal', dest='Hal', action='store_false',
            default=True, help=_("Disable HAL support."))
        return p

    def version(self):
        print r"""   ____          _ __    __
  / __/_ _____ _(_) /__ / /
 / _/ \ \ / _ `/ / / -_)_/ 
/___//_\_\\_,_/_/_/\__(_)   v%s
"""%__version__
        exit()

    def _add_default_playlists(self):
        """
            Adds some default smart playlists to the playlist manager
        """
        from xl import playlist
        # entire playlist
        entire_lib = playlist.SmartPlaylist(_("Entire Library"),
            collection=self.collection) 
        self.smart_playlists.save_playlist(entire_lib, overwrite=True)

        # random playlists
        for count in (100, 300, 500):
            pl = playlist.SmartPlaylist(_("Random %d") % count,
                collection=self.collection)
            pl.set_return_limit(count)
            pl.set_random_sort(True)
            self.smart_playlists.save_playlist(pl, overwrite=True)

        # rating based playlists
        for item in (3, 4):
            pl = playlist.SmartPlaylist(_("Rating > %d") % item, 
                collection=self.collection)
            pl.add_param('__rating', '>', item)
            self.smart_playlists.save_playlist(pl, overwrite=True)

    def mainloop_init(self):
        import gobject
        gobject.threads_init()
        if self.options.Dbus:
            import dbus, dbus.mainloop.glib
            dbus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            dbus.mainloop.glib.threads_init()
            dbus.mainloop.glib.gthreads_init()
        if self.options.StartGui:
            import gtk
            gtk.gdk.threads_init()
        else:
            loop = gobject.MainLoop()
            context = loop.get_context()
            self.__mainloop(context)

    @common.threaded
    def __mainloop(self, context):
        while 1:
            try:
                context.iteration(True)
            except:
                pass

    def get_version(self):
        """
            Returns the current version
        """
        return __version__

    def quit(self):
        """
            exits Exaile normally.

            takes care of saving prefs, databases, etc.
        """
        if self.quitting: 
            return
        self.quitting = True
        logger.info(_("Exaile is shutting down..."))

        # stop the various idle based threads so they don't freak out when the
        # program exits.  Silly Python.
        event.IDLE_MANAGER.stop()
        for timer in event._TIMERS:
            timer.cancel()

        # this event should be used by plugins and modules that dont need
        # to be saved in any particular order. modules that might be 
        # touched by events triggered here should be added statically
        # below.
        event.log_event("quit_application", self, None, async=False)

        logger.info(_("Saving state..."))
        self.plugins.save_enabled()

        if self.gui:
            self.gui.quit()

        self.covers.save_cover_db()

        self.collection.save_to_location()
        
        #Save order of custom playlists
        self.playlists.save_order()
        self.stations.save_order()

        # save player, queue
        self.queue._save_player_state(
                os.path.join(xdg.get_data_dirs()[0], 'player.state') )
        self.queue.save_to_location(
                os.path.join(xdg.get_data_dirs()[0], 'queue.state') )
        self.player.stop()

        from xl import settings

        settings._SETTINGSMANAGER.save()

        logger.info(_("Bye!"))
        logging.shutdown()
        exit()

def exaile():
    if not Exaile._exaile:
        raise AttributeError(_("Exaile is not yet finished loading"
            ". Perhaps you should listen for the exaile_loaded"
            " signal?"))

    return Exaile._exaile

# vim: et sts=4 sw=4
